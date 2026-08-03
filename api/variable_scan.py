# api/variable_scan.py
"""Variable write/read analysis over FDA JSON — the CMP-15 backend (Plan 23-03 Task 3).

v1 semantics, stated explicitly because it is a real narrowing: this is an EXISTENCE check —
does ANY action anywhere in the FDA write this variable — not graph REACHABILITY from
`initial_state`. True reachability (is there a path from the initial state through the
transition graph that reaches a writer before the reader fires) would need to assume the FDA's
guard semantics resolve deterministically over a graph that can contain cycles; that confidence
is not what this check claims, and building it is a materially larger undertaking than the rest
of this phase. A future refinement to true reachability is possible — it would walk
`transitions` from `fda_json["initial_state"]`, collect the write-set reachable up to each
state, and diff each reader's enclosing state against that set — but CMP-15's literal text only
asks for existence, so that refinement is deferred, not attempted here.

Composes `fda_utils.scan_fda_condition_operands` — does not walk the FDA a second time.
`detector_keys_scan.py` is the precedent for a sibling analysis module living in its own file
rather than growing `fda_utils.py` past its line budget.

Not wired into `preflight_validate` here — plan 23-07 owns `toolkit_dispatch.py`. This module
delivers the analysis functions only.
"""
import re

from fda_utils import scan_fda_condition_operands


def _actions_from_states(fda_json: dict) -> list[tuple[str, list]]:
    states = fda_json.get("states")
    if isinstance(states, dict):
        return [(name, body.get("entry_actions") or []) for name, body in states.items() if isinstance(body, dict)]
    if isinstance(states, list):
        return [
            (s.get("name") or f"[{i}]", s.get("entry_actions") or [])
            for i, s in enumerate(states) if isinstance(s, dict)
        ]
    return []


def _walk_actions(location_prefix: str, actions, visit) -> None:
    """Call visit(location, action) for every action, recursing into `if` then/else branches."""
    if not isinstance(actions, list):
        return
    for i, action in enumerate(actions):
        if not isinstance(action, dict):
            continue
        location = f"{location_prefix}[{i}]"
        visit(location, action)
        if action.get("type") == "if":
            _walk_actions(f"{location}.then", action.get("then"), visit)
            _walk_actions(f"{location}.else", action.get("else"), visit)


def _walk_all_actions(fda_json: dict, visit) -> None:
    for state_name, actions in _actions_from_states(fda_json):
        _walk_actions(f"states.{state_name}.entry_actions", actions, visit)

    trigger_assignments = fda_json.get("trigger_assignments")
    if isinstance(trigger_assignments, list):
        for i, ta in enumerate(trigger_assignments):
            if not isinstance(ta, dict):
                continue
            _walk_actions(f"trigger_assignments[{i}].actions", ta.get("actions"), visit)


def scan_variable_writers(fda_json: dict) -> dict[str, list[str]]:
    """{var: [locations]} for every action with an `output` naming that variable
    (states[*].entry_actions + trigger_assignments[*].actions, recursing `if` then/else), PLUS
    `flag` actions whose `ref` is the variable, PLUS variables declared with a non-None
    `initial_value` (location "variables.<name>"). Never raises; [] on absent/malformed input.
    """
    if not isinstance(fda_json, dict):
        return {}
    variables = fda_json.get("variables")
    if not isinstance(variables, dict) or not variables:
        return {}

    writers: dict[str, list[str]] = {}

    def record(name, location):
        if isinstance(name, str) and name in variables:
            writers.setdefault(name, []).append(location)

    def visit(location, action):
        output = action.get("output")
        if output:
            for name in (output if isinstance(output, list) else [output]):
                record(name, location)
        if action.get("type") == "flag":
            record(action.get("ref"), location)

    _walk_all_actions(fda_json, visit)

    for name, spec in variables.items():
        if isinstance(spec, dict) and spec.get("initial_value") is not None:
            writers.setdefault(name, []).append(f"variables.{name}")

    return writers


def scan_variable_readers(fda_json: dict) -> dict[str, list[str]]:
    """{var: [locations]} from `scan_fda_condition_operands`' `{"view"/"flag": name}` operands
    naming a declared variable, PLUS `{name}` tokens inside a `view` action's `key_template`,
    PLUS operands used as `compute`/`hardware` action `args`/`kwargs`. Never raises.
    """
    if not isinstance(fda_json, dict):
        return {}
    variables = fda_json.get("variables")
    if not isinstance(variables, dict) or not variables:
        return {}

    readers: dict[str, list[str]] = {}

    def record(name, location):
        if isinstance(name, str) and name in variables:
            readers.setdefault(name, []).append(location)

    for entry in scan_fda_condition_operands(fda_json):
        operand = entry["operand"]
        if not isinstance(operand, dict):
            continue
        if "view" in operand:
            record(operand["view"], entry["location"])
        elif "flag" in operand:
            record(operand["flag"], entry["location"])

    def visit(location, action):
        if action.get("type") == "view":
            key_template = action.get("key_template")
            if isinstance(key_template, str):
                for token in re.findall(r"\{(\w+)\}", key_template):
                    record(token, f"{location}.key_template")
        if action.get("type") in ("hardware", "compute"):
            operands = list(action.get("args") or []) + list((action.get("kwargs") or {}).values())
            for operand in operands:
                if not isinstance(operand, dict):
                    continue
                if "flag" in operand:
                    record(operand["flag"], f"{location}.args")
                elif "view" in operand:
                    record(operand["view"], f"{location}.args")

    _walk_all_actions(fda_json, visit)
    return readers


def variable_never_written_issues(fda_json: dict) -> list[dict]:
    """One issue dict per variable with >=1 reader and 0 writers.

    Shape matches the `PreflightIssue` union in `HardwareCheckModal.tsx` so it renders through
    Phase 25's existing path once a future plan wires this in.
    """
    if not isinstance(fda_json, dict):
        return []
    writers = scan_variable_writers(fda_json)
    readers = scan_variable_readers(fda_json)

    issues = []
    for var, locations in readers.items():
        if var in writers:
            continue
        issues.append({
            "module_id": None,
            "module_name": var,
            "issue": "variable_never_written",
            "variable": var,
            "location": locations[0],
            "detail": (
                f"Transition reads variable '{var}' but no compute/flag action anywhere "
                f"writes it — the guard will always compare against None"
            ),
        })
    return issues
