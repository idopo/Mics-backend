# api/fda_utils.py
"""Shared utilities for scanning FDA JSON structures."""


def scan_fda_for_refs(fda_json: dict) -> list[dict]:
    """Recursively walk all states.entry_actions and trigger_assignments[*].actions,
    including type:if branches.

    Returns list of {scope, state_name, action_type, ref, method, output} for
    hardware/flag/timer/method/compute actions. scope is "state" or "trigger"; state_name is the
    state name or trigger_name respectively (kept as the label field so existing consumers work
    unchanged). ref and method may be None depending on action type. `output` (CMP-11) is the
    declared output name/list or None — both the soft drift-badge path
    (routers/toolkits.py::_validate_task_definition) and the hw-lib-update impact scan
    (hardware_libs.py::_flag_broken_task_defs) need it to see compute output names.
    """
    results = []
    states = fda_json.get("states", {})
    if isinstance(states, dict):
        for state_name, state_body in states.items():
            if not isinstance(state_body, dict):
                continue
            results.extend(_scan_actions(state_name, state_body.get("entry_actions") or [], scope="state"))

    trigger_assignments = fda_json.get("trigger_assignments")
    if isinstance(trigger_assignments, list):
        for ta in trigger_assignments:
            if not isinstance(ta, dict):
                continue
            results.extend(_scan_actions(
                ta.get("trigger_name") or "?", ta.get("actions") or [], scope="trigger"))

    return results


def _scan_actions(state_name: str, actions: list[dict], scope: str = "state") -> list[dict]:
    results = []
    for action in actions:
        if not isinstance(action, dict):
            continue
        action_type = action.get("type")
        if action_type in ("hardware", "flag", "timer", "method", "compute"):
            results.append({
                "scope": scope,
                "state_name": state_name,
                "action_type": action_type,
                "ref": action.get("ref") or action.get("action"),
                "method": action.get("method"),
                "output": action.get("output"),
            })
        elif action_type == "if":
            results.extend(_scan_actions(state_name, action.get("then") or [], scope=scope))
            results.extend(_scan_actions(state_name, action.get("else") or [], scope=scope))
    return results


def ref_label(entry: dict) -> str:
    """User-facing prefix for a scanner result. Trigger-scoped labels deliberately do NOT
    match TaskEditor.parseStateWarnings' /^State '(...)': / regex."""
    if entry.get("scope") == "trigger":
        return f"Trigger '{entry['state_name']}'"
    return f"State '{entry['state_name']}'"


def scan_fda_condition_operands(fda_json: dict) -> list[dict]:
    """Every condition operand (left/right) in the FDA definition. Never raises.

    Exists because scan_fda_for_refs (above) walks states[*].entry_actions and
    trigger_assignments[*].actions only and NEVER sees transition conditions. Two consumers need
    the identical walk of transitions.condition_tree / condition_groups / conditions,
    states[*].wait_condition, and `if`-action conditions inside both entry_actions and
    trigger_assignments[*].actions: Plan 25-01 Task 4's save-time 422 pass and plan 03's
    preflight resolver. Independent sibling of scan_fda_for_refs — does not touch it.

    -> [{"location": "transitions[0].condition_tree.left", "operand": {...}}, ...]
    Literal operands (numbers, strings, null) are returned untouched — the caller decides what
    to ignore.
    """
    if not isinstance(fda_json, dict):
        return []
    results: list[dict] = []

    states = fda_json.get("states")
    if isinstance(states, dict):
        items = list(states.items())
    elif isinstance(states, list):
        items = [
            (s.get("name") or f"[{i}]", s) if isinstance(s, dict) else (f"[{i}]", None)
            for i, s in enumerate(states)
        ]
    else:
        items = []
    for state_name, state_body in items:
        if not isinstance(state_body, dict):
            continue
        wait_condition = state_body.get("wait_condition")
        if wait_condition is not None:
            results.extend(_scan_condition(f"states.{state_name}.wait_condition", wait_condition))
        results.extend(_scan_action_conditions(f"states.{state_name}.entry_actions", state_body.get("entry_actions")))

    transitions = fda_json.get("transitions")
    if isinstance(transitions, list):
        for i, transition in enumerate(transitions):
            if not isinstance(transition, dict):
                continue
            base = f"transitions[{i}]"
            if "condition_tree" in transition:
                results.extend(_scan_condition_node(f"{base}.condition_tree", transition.get("condition_tree")))
            for gi, group in enumerate(transition.get("condition_groups") or []):
                if not isinstance(group, dict):
                    continue
                for ci, cond in enumerate(group.get("conditions") or []):
                    results.extend(_scan_condition(f"{base}.condition_groups[{gi}].conditions[{ci}]", cond))
            for ci, cond in enumerate(transition.get("conditions") or []):
                results.extend(_scan_condition(f"{base}.conditions[{ci}]", cond))

    trigger_assignments = fda_json.get("trigger_assignments")
    if isinstance(trigger_assignments, list):
        for i, ta in enumerate(trigger_assignments):
            if not isinstance(ta, dict):
                continue
            results.extend(_scan_action_conditions(f"trigger_assignments[{i}].actions", ta.get("actions")))

    return results


def _scan_condition(location: str, condition) -> list[dict]:
    """A leaf FdaCondition {left, op, right} -> up to two operand entries."""
    if not isinstance(condition, dict):
        return []
    results = []
    if "left" in condition:
        results.append({"location": f"{location}.left", "operand": condition.get("left")})
    if "right" in condition:
        results.append({"location": f"{location}.right", "operand": condition.get("right")})
    return results


def _scan_condition_node(location: str, node) -> list[dict]:
    """A condition_tree node: a leaf FdaCondition, or {op: AND|OR, children: [...]}."""
    if not isinstance(node, dict):
        return []
    children = node.get("children")
    if isinstance(children, list):
        results = []
        for i, child in enumerate(children):
            results.extend(_scan_condition_node(f"{location}.children[{i}]", child))
        return results
    return _scan_condition(location, node)


def _scan_action_conditions(location: str, actions) -> list[dict]:
    """Walk a list of FdaAction, recursing into type:if's own condition plus then/else branches."""
    if not isinstance(actions, list):
        return []
    results = []
    for i, action in enumerate(actions):
        if not isinstance(action, dict):
            continue
        if action.get("type") == "if":
            condition = action.get("condition")
            if condition is not None:
                results.extend(_scan_condition(f"{location}[{i}].condition", condition))
            results.extend(_scan_action_conditions(f"{location}[{i}].then", action.get("then")))
            results.extend(_scan_action_conditions(f"{location}[{i}].else", action.get("else")))
    return results
