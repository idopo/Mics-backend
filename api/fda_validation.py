"""Hard (422-worthy) validation for trigger_assignments and variables in FDA JSON.

Phase 24 dropped the old `handler` enum: a `trigger_assignments` entry carries `trigger_name`
plus `actions` and nothing else. This is the ONE enforcement point for the trigger action
vocabulary across four runtimes (Pi `_build_action_callable`, the Pi CLI `validate_fda.py`,
React's `ActionEditor`, and this module). True cross-language single-sourcing would need
codegen (out of scope — see 24-RESEARCH.md's note on TRIGA-10); the honest fix is that THIS
module is the enforcement point, so React/Pi vocabulary drift fails at save time with a 422
instead of silently at Pi session start.

Deliberately separate from the SOFT `_validate_task_definition` in `routers/toolkits.py`
(state-body hw-lib-drift badge, always 200). This module's callers raise HTTPException(422).

View-key RESOLUTION is out of scope here — only key_template SHAPE is checked (non-empty
string, every `{token}` names a declared variable/flag). Valid keys like LICKER0..LICKER3 are
derived at runtime from a specific pilot's prefs.json (device_name x num_detectors via
check_for_detectors), so resolving here would falsely reject a definition targeting a
differently configured pilot. Authoritative resolution belongs to Phase 13's pilot-specific
preflight (api/routers/toolkit_dispatch.py::preflight_validate), which keys off pilot_id and
reads pilot_hardware_config — the only place that knows a given pilot's hardware shape.
"""
import re

from fastapi import HTTPException

from models import TaskToolkit

VALID_ACTION_TYPES = {"hardware", "flag", "timer", "special", "method", "if", "view"}
VALID_SPECIALS = {"INC_TRIAL_COUNTER"}
VALID_TRIGGER_CONTEXT_KEYS = {"level", "tick"}
# No handler constant: the `handler` enum was dropped in Phase 24. `actions` is the only vocabulary.


def validate_variables(fda_json: dict, toolkit) -> list[str]:
    """Validate the top-level `variables` registry. Empty/absent = no errors."""
    if toolkit is None:
        return []
    variables = fda_json.get("variables")
    if not variables:
        return []
    if not isinstance(variables, dict):
        return [f"variables must be an object, got {type(variables).__name__}"]

    flag_names = set((toolkit.flags or {}).keys())
    return [
        f"variable '{name}' collides with an existing toolkit flag"
        for name in variables
        if name in flag_names
    ]


def validate_trigger_assignments(fda_json: dict, toolkit) -> list[str]:
    """Validate `trigger_assignments`. Absent/null/[] is backward-compatible and returns []."""
    if toolkit is None:
        return []
    trigger_assignments = fda_json.get("trigger_assignments")
    if not trigger_assignments:
        return []
    if not isinstance(trigger_assignments, list):
        return [f"trigger_assignments must be a list, got {type(trigger_assignments).__name__}"]

    known_hw = set((toolkit.semantic_hardware or {}).keys())
    callable_methods = set(getattr(toolkit, "callable_methods", None) or [])
    valid_names = _valid_flag_names(fda_json, toolkit)
    # Enforce only when the toolkit reports trigger_sources (Plan 08's column) AND it is
    # non-empty — same posture as callable_methods. getattr(..., None) so this works on a
    # toolkit predating the column entirely.
    trigger_sources = {t["hw_id"] for t in (getattr(toolkit, "trigger_sources", None) or [])}

    errors: list[str] = []
    for i, ta in enumerate(trigger_assignments):
        if not isinstance(ta, dict):
            errors.append(f"trigger_assignments[{i}]: must be an object")
            continue

        raw_name = ta.get("trigger_name")
        if not isinstance(raw_name, str) or not raw_name.strip():
            errors.append(f"trigger_assignments[{i}]: trigger_name is required and must be a non-empty string")
            label = f"[{i}]"
        else:
            label = raw_name
            if trigger_sources and raw_name not in trigger_sources:
                errors.append(
                    f"Trigger '{raw_name}': unknown trigger_name. "
                    f"Valid trigger sources: {sorted(trigger_sources)}"
                )

        actions = ta.get("actions")
        if not actions:
            errors.append(
                f"Trigger '{label}': actions is required (the `handler` enum is gone, "
                f"`actions` is the only vocabulary)"
            )
            continue
        if not isinstance(actions, list):
            errors.append(f"Trigger '{label}': actions must be a list")
            continue

        for j, action in enumerate(actions):
            errors.extend(_validate_action(label, j, action, known_hw, callable_methods, valid_names))

    return errors


def collect_hard_errors(fda_json: dict, toolkit) -> list[str]:
    """Every hard (422-worthy) error for this FDA. Phase 23 appends its compute checks here."""
    if not fda_json or toolkit is None:
        return []
    return validate_variables(fda_json, toolkit) + validate_trigger_assignments(fda_json, toolkit)


def reject_if_hard_errors(db, fda_json: dict, toolkit_id: int | None) -> None:
    """Raise HTTPException(422) if fda_json has hard trigger-assignment/variable errors.

    Looks up the toolkit itself so both POST and PUT call sites in routers/toolkits.py stay to
    a single line each — toolkits.py's net-growth budget for this plan is tight (<=15 lines).
    """
    if not fda_json:
        return
    toolkit = db.query(TaskToolkit).filter(TaskToolkit.id == toolkit_id).one_or_none() if toolkit_id else None
    errors = collect_hard_errors(fda_json, toolkit)
    if errors:
        raise HTTPException(422, detail={"errors": errors})


def _valid_flag_names(fda_json: dict, toolkit) -> set[str]:
    """Names usable as a flag ref / output slot / key_template token / condition operand."""
    return (
        set((toolkit.flags or {}).keys())
        | set((fda_json.get("variables") or {}).keys())
        | {"trial_counter"}
    )


def _validate_action(trigger_label, idx, action, known_hw, callable_methods, valid_names) -> list[str]:
    if not isinstance(action, dict):
        return [f"Trigger '{trigger_label}' action[{idx}]: action must be an object"]

    action_type = action.get("type")
    if action_type not in VALID_ACTION_TYPES:
        return [
            f"Trigger '{trigger_label}' action[{idx}]: unknown action type '{action_type}'. "
            f"Allowed: {', '.join(sorted(VALID_ACTION_TYPES))}"
        ]

    if action_type == "if":
        errors: list[str] = []
        for j, sub in enumerate(action.get("then") or []):
            errors.extend(_validate_action(trigger_label, f"{idx}.then[{j}]", sub, known_hw, callable_methods, valid_names))
        for j, sub in enumerate(action.get("else") or []):
            errors.extend(_validate_action(trigger_label, f"{idx}.else[{j}]", sub, known_hw, callable_methods, valid_names))
        return errors

    errors = []
    ref = action.get("ref")

    if action_type in ("hardware", "timer"):
        # An explicit "group" key is direct-ref (GUI-built) format — _build_action_callable
        # resolves it via self.hardware[group][ref], which this module cannot verify without
        # a DB join to hardware_modules. Skip, matching _validate_fda_against_toolkit's posture.
        if "group" not in action and known_hw and ref not in known_hw:
            errors.append(f"Trigger '{trigger_label}' action[{idx}]: unknown hardware ref '{ref}'")
    elif action_type == "method":
        if callable_methods and ref not in callable_methods:
            errors.append(f"Trigger '{trigger_label}' action[{idx}]: method '{ref}' not in toolkit callable_methods")
    elif action_type == "special":
        if ref not in VALID_SPECIALS:
            errors.append(
                f"Trigger '{trigger_label}' action[{idx}]: unknown special '{ref}'. "
                f"Allowed: {', '.join(sorted(VALID_SPECIALS))}"
            )
    elif action_type == "flag":
        if ref not in valid_names:
            errors.append(f"Trigger '{trigger_label}' action[{idx}]: flag '{ref}' not declared")
    elif action_type == "view":
        key_template = action.get("key_template")
        if not key_template or not isinstance(key_template, str):
            errors.append(f"Trigger '{trigger_label}' action[{idx}]: view action requires a key_template")
        else:
            for token in re.findall(r"\{(\w+)\}", key_template):
                if token not in valid_names:
                    errors.append(
                        f"Trigger '{trigger_label}' action[{idx}]: key_template token '{token}' not declared"
                    )

    output = action.get("output")
    if output is not None:
        names = output if isinstance(output, list) else [output]
        for name in names:
            if name not in valid_names:
                errors.append(f"Trigger '{trigger_label}' action[{idx}]: output slot '{name}' not declared")

    for operand in list(action.get("args") or []) + list((action.get("kwargs") or {}).values()):
        if isinstance(operand, dict) and "trigger" in operand:
            key = operand["trigger"]
            if key not in VALID_TRIGGER_CONTEXT_KEYS:
                errors.append(
                    f"Trigger '{trigger_label}' action[{idx}]: unknown trigger context key '{key}'. "
                    f"Allowed: {', '.join(sorted(VALID_TRIGGER_CONTEXT_KEYS))}"
                )

    return errors
