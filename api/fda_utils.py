# api/fda_utils.py
"""Shared utilities for scanning FDA JSON structures."""


def scan_fda_for_refs(fda_json: dict) -> list[dict]:
    """Recursively walk all states.entry_actions and trigger_assignments[*].actions,
    including type:if branches.

    Returns list of {scope, state_name, action_type, ref, method} for hardware/flag/timer/method
    actions. scope is "state" or "trigger"; state_name is the state name or trigger_name
    respectively (kept as the label field so existing consumers work unchanged). ref and method
    may be None depending on action type.
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
        if action_type in ("hardware", "flag", "timer", "method"):
            results.append({
                "scope": scope,
                "state_name": state_name,
                "action_type": action_type,
                "ref": action.get("ref") or action.get("action"),
                "method": action.get("method"),
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
