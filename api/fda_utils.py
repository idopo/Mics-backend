# api/fda_utils.py
"""Shared utilities for scanning FDA JSON structures."""


def scan_fda_for_refs(fda_json: dict) -> list[dict]:
    """Recursively walk all states.entry_actions, including type:if branches.

    Returns list of {state_name, action_type, ref, method} for hardware/flag/timer/method actions.
    Only populated fields are included — ref and method may be None depending on action type.
    """
    results = []
    states = fda_json.get("states", {})
    if not isinstance(states, dict):
        return results
    for state_name, state_body in states.items():
        if not isinstance(state_body, dict):
            continue
        results.extend(_scan_actions(state_name, state_body.get("entry_actions") or []))
    return results


def _scan_actions(state_name: str, actions: list[dict]) -> list[dict]:
    results = []
    for action in actions:
        if not isinstance(action, dict):
            continue
        action_type = action.get("type")
        if action_type in ("hardware", "flag", "timer", "method"):
            results.append({
                "state_name": state_name,
                "action_type": action_type,
                "ref": action.get("ref") or action.get("action"),
                "method": action.get("method"),
            })
        elif action_type == "if":
            results.extend(_scan_actions(state_name, action.get("then") or []))
            results.extend(_scan_actions(state_name, action.get("else") or []))
    return results
