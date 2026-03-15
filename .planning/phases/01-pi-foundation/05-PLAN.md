---
plan: 05
wave: 1
title: "validate_fda.py CLI validation tool"
depends_on: []
files_modified: []
files_created:
  - ~/pi-mirror/tools/validate_fda.py
autonomous: true
requirements:
  - FDA-08
---

# Plan 05: validate_fda.py CLI validation tool

## Goal

Create a standalone CLI tool at `~/pi-mirror/tools/validate_fda.py` that validates an FDA v2 JSON file against a given toolkit class, exiting 0 on success and 1 with specific error messages on failure.

## Context

This tool is used by developers before deploying a new FDA JSON to detect structural errors without needing a running Pi. It imports the toolkit class directly, inspects its attributes, and checks the JSON for consistency. It does NOT instantiate the task (which would require hardware and pigpio).

The tool is independent of Plans 01–04 but benefits from understanding the attribute structure they define. It can be written and used in parallel.

### Validations performed

1. **Version check**: `definition.get('version') == 2`
2. **initial_state**: must be a key in `definition['states']`
3. **Passthrough states**: for each state with no `entry_actions`, the toolkit class must have a method of that name. Check `hasattr(cls, state_name)` and `callable(getattr(cls, state_name))`.
4. **entry_actions: type "method"**: `ref` must be in `cls.CALLABLE_METHODS`
5. **entry_actions: type "hardware"**: `ref` must be a key in `cls.SEMANTIC_HARDWARE`
6. **entry_actions: type "flag"**: `ref` must be a key in `cls.FLAGS`
7. **entry_actions: type "special"**: `ref` must be in `["INC_TRIAL_COUNTER"]`
8. **entry_actions: type "timer"**: `ref` must be a key in `cls.SEMANTIC_HARDWARE` (timers are also semantic hardware entries)
9. **Transition states**: `from` and `to` names must be in `definition['states']`
10. **Condition view keys**: `view` in condition must be either a key in `cls.SEMANTIC_HARDWARE` OR a key in `cls.FLAGS` OR a key in `cls.PARAMS` (all accessible via `self.view.view` at runtime)
11. **Condition ops**: must be in `["eq", "ne", "lt", "le", "gt", "ge"]`
12. **Condition rhs**: if `{"param": key}`, `key` must be in `cls.PARAMS`; if `{"flag": key}`, `key` must be in `cls.FLAGS`; if `{"now": ...}` — OK; literals are always OK
13. **return_data**: if `{"flag": key}`, `key` in `cls.FLAGS`; if `{"param": key}`, `key` in `cls.PARAMS`
14. **Duplicate state names**: each state name should appear exactly once in `definition['states']` (JSON object keys are unique by spec but deserializing with `json.loads` deduplicates — warn if input has duplicates)
15. **trigger_assignments**: each `trigger_name` must match a key in `cls.HARDWARE` group values (i.e. a hardware pin letter); `handler` must be in `["touch_detector", "digital_input", "log_only", "default"]`

### Error format

Print errors to stderr as:
```
ERROR [state 'trial_onset' action[2]]: type:'method' ref 'nonexistent_method' not in CALLABLE_METHODS
ERROR [transition 'state_wait_time_window' → 'state_unknown']: 'to' state not found in states dict
```

Print summary: `Validation PASSED (N states, M transitions)` or `Validation FAILED (K errors)`.

### CLI interface

```
python tools/validate_fda.py <toolkit_module_path_or_name> <fda_json_file>
```

Examples:
```bash
python tools/validate_fda.py AppetitiveTaskReal fda_v2.json
python tools/validate_fda.py autopilot.tasks.some_toolkit.SomeTask fda_v2.json
```

Toolkit lookup: try `autopilot.get_task(toolkit_name)` first (matches registered plugin class name). If that fails, try `importlib.import_module` on the full dotted path and `getattr` the last component.

## Tasks

<task id="05-1" title="Create tools/ directory and validate_fda.py">

Create the directory `~/pi-mirror/tools/` if it does not exist.

Create `~/pi-mirror/tools/validate_fda.py` with the following content:

```python
#!/usr/bin/env python3
"""
validate_fda.py — Validate an FDA v2 JSON file against a toolkit class.

Usage:
    python tools/validate_fda.py <ToolkitClassName> <fda_json_file>

Exit codes:
    0 — validation passed
    1 — validation failed (errors printed to stderr)
    2 — usage error (wrong arguments, file not found, class not importable)

Examples:
    python tools/validate_fda.py AppetitveTaskReal appetitive_v2.json
    python tools/validate_fda.py autopilot.tasks.mics_task.mics_task fda.json
"""

import sys
import os
import json
import importlib
import argparse
from typing import List, Tuple


VALID_OPS      = {"eq", "ne", "lt", "le", "gt", "ge"}
VALID_HANDLERS = {"touch_detector", "digital_input", "log_only", "default"}
VALID_SPECIALS = {"INC_TRIAL_COUNTER"}
VALID_ACTIONS  = {"hardware", "flag", "timer", "special", "method"}


def load_toolkit_class(name_or_path: str):
    """
    Load a toolkit class by registered task name or by fully-qualified dotted path.
    Returns the class object or raises SystemExit(2).
    """
    # First: try autopilot task registry (works for plugin task classes)
    try:
        # Add autopilot paths if needed
        sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
        import autopilot
        cls = autopilot.get_task(name_or_path)
        if cls is not None:
            return cls
    except Exception:
        pass

    # Second: try importlib with dotted path (e.g. "autopilot.tasks.mics_task.mics_task")
    if "." in name_or_path:
        parts = name_or_path.rsplit(".", 1)
        try:
            mod = importlib.import_module(parts[0])
            cls = getattr(mod, parts[1])
            return cls
        except (ImportError, AttributeError) as e:
            print(f"ERROR: Could not import class '{name_or_path}': {e}", file=sys.stderr)
            sys.exit(2)

    print(
        f"ERROR: Could not find toolkit class '{name_or_path}'. "
        f"Provide either a registered task name or a fully-qualified dotted path.",
        file=sys.stderr,
    )
    sys.exit(2)


def get_class_attr_keys(cls, attr: str) -> set:
    """Return set of keys from a class dict attribute, or empty set if absent."""
    val = getattr(cls, attr, None)
    if val is None:
        return set()
    if isinstance(val, dict):
        return set(val.keys())
    return set()


def get_class_attr_list(cls, attr: str) -> list:
    """Return list from a class list attribute, or empty list if absent."""
    val = getattr(cls, attr, None)
    if val is None:
        return []
    return list(val)


def collect_view_keys(cls) -> set:
    """
    Collect all valid view keys accessible at runtime:
    - SEMANTIC_HARDWARE keys (hardware objects)
    - FLAGS keys (flag trackers)
    - PARAMS keys (also accessible via view for some tasks)
    Hardware pin IDs are also accessible but we cannot enumerate all without instantiation.
    We accept SEMANTIC_HARDWARE + FLAGS + PARAMS as the safe conservative set.
    """
    keys = set()
    keys.update(get_class_attr_keys(cls, "SEMANTIC_HARDWARE"))
    keys.update(get_class_attr_keys(cls, "FLAGS"))
    # PARAMS keys are accessible in view (hardware objects keyed by pin id are also there,
    # but we can't enumerate without instantiation — allow any HARDWARE group/pin key too)
    params = getattr(cls, "PARAMS", {})
    if params:
        keys.update(params.keys())
    # Also add HARDWARE pin ids (group→{id: ...})
    hardware = getattr(cls, "HARDWARE", {})
    for group_vals in hardware.values():
        if isinstance(group_vals, dict):
            keys.update(group_vals.keys())
    return keys


def validate_fda(cls, definition: dict) -> List[str]:
    """
    Validate FDA definition dict against toolkit class.
    Returns list of error strings (empty = valid).
    """
    errors = []

    # ── Version ─────────────────────────────────────────────────────────────────────
    version = definition.get("version")
    if version != 2:
        errors.append(f"[root]: 'version' must be 2, got {version!r}")
        return errors  # Cannot continue without v2 structure

    states_def   = definition.get("states", {})
    transitions  = definition.get("transitions", [])
    trigger_asgn = definition.get("trigger_assignments", [])
    initial      = definition.get("initial_state")

    semantic_hw_keys  = get_class_attr_keys(cls, "SEMANTIC_HARDWARE")
    flag_keys         = get_class_attr_keys(cls, "FLAGS")
    callable_methods  = set(get_class_attr_list(cls, "CALLABLE_METHODS"))
    params_keys       = set(getattr(cls, "PARAMS", {}).keys()) if hasattr(cls, "PARAMS") else set()
    valid_view_keys   = collect_view_keys(cls)
    state_names       = set(states_def.keys())

    # ── initial_state ────────────────────────────────────────────────────────────────
    if not initial:
        errors.append("[root]: 'initial_state' is required")
    elif initial not in state_names:
        errors.append(
            f"[root]: initial_state '{initial}' not in states dict. "
            f"Available: {sorted(state_names)}"
        )

    # ── States ───────────────────────────────────────────────────────────────────────
    for state_name, state_def in states_def.items():
        entry_actions = state_def.get("entry_actions") or []
        return_data   = state_def.get("return_data") or {}
        blocking      = state_def.get("blocking")

        # Passthrough: no entry_actions → must have a method of that name on the class
        if not entry_actions:
            if not (hasattr(cls, state_name) and callable(getattr(cls, state_name))):
                errors.append(
                    f"[state '{state_name}']: no entry_actions (passthrough) but class "
                    f"'{cls.__name__}' has no callable method '{state_name}'"
                )
            continue  # Skip action validation for passthrough states

        # Validate blocking value
        if blocking is not None and blocking not in ("stage_block",):
            errors.append(
                f"[state '{state_name}']: unknown 'blocking' value {blocking!r}. "
                f"Allowed: 'stage_block' or absent/null"
            )

        # Validate each action
        for i, action in enumerate(entry_actions):
            loc = f"[state '{state_name}' action[{i}]]"
            atype = action.get("type")
            ref   = action.get("ref", "")

            if atype not in VALID_ACTIONS:
                errors.append(
                    f"{loc}: unknown action type {atype!r}. Allowed: {sorted(VALID_ACTIONS)}"
                )
                continue

            if atype == "hardware":
                if ref not in semantic_hw_keys:
                    errors.append(
                        f"{loc}: type:'hardware' ref '{ref}' not in SEMANTIC_HARDWARE. "
                        f"Available: {sorted(semantic_hw_keys)}"
                    )
                if not action.get("method"):
                    errors.append(f"{loc}: type:'hardware' missing 'method' field")

            elif atype == "flag":
                if ref not in flag_keys:
                    errors.append(
                        f"{loc}: type:'flag' ref '{ref}' not in FLAGS. "
                        f"Available: {sorted(flag_keys)}"
                    )

            elif atype == "timer":
                if ref not in semantic_hw_keys:
                    errors.append(
                        f"{loc}: type:'timer' ref '{ref}' not in SEMANTIC_HARDWARE. "
                        f"Available: {sorted(semantic_hw_keys)}"
                    )

            elif atype == "special":
                if ref not in VALID_SPECIALS:
                    errors.append(
                        f"{loc}: type:'special' ref '{ref}' not in {sorted(VALID_SPECIALS)}"
                    )

            elif atype == "method":
                if ref not in callable_methods:
                    errors.append(
                        f"{loc}: type:'method' ref '{ref}' not in CALLABLE_METHODS. "
                        f"Available: {sorted(callable_methods)}"
                    )

            # Validate arg refs
            for j, arg in enumerate(action.get("args", [])):
                _validate_arg_ref(arg, loc + f" args[{j}]", flag_keys, params_keys, errors)
            for kw_key, kw_val in action.get("kwargs", {}).items():
                _validate_arg_ref(kw_val, loc + f" kwargs['{kw_key}']", flag_keys, params_keys, errors)

        # Validate return_data
        for rd_key, rd_val in return_data.items():
            loc = f"[state '{state_name}' return_data['{rd_key}']]"
            if isinstance(rd_val, dict):
                if "flag" in rd_val:
                    if rd_val["flag"] not in flag_keys:
                        errors.append(
                            f"{loc}: flag ref '{rd_val['flag']}' not in FLAGS"
                        )
                elif "param" in rd_val:
                    if rd_val["param"] not in params_keys:
                        errors.append(
                            f"{loc}: param ref '{rd_val['param']}' not in PARAMS"
                        )
                elif "now" not in rd_val:
                    errors.append(
                        f"{loc}: unknown return_data value spec {rd_val!r}"
                    )

    # ── Transitions ──────────────────────────────────────────────────────────────────
    for t_idx, trans in enumerate(transitions):
        from_name   = trans.get("from", "")
        to_name     = trans.get("to", "")
        conditions  = trans.get("conditions", [])
        loc         = f"[transition[{t_idx}] '{from_name}' → '{to_name}']"

        if from_name not in state_names:
            errors.append(f"{loc}: 'from' state '{from_name}' not in states dict")
        if to_name not in state_names:
            errors.append(f"{loc}: 'to' state '{to_name}' not in states dict")

        for c_idx, cond in enumerate(conditions):
            cloc = loc + f" condition[{c_idx}]"
            view_key = cond.get("view", "")
            op_str   = cond.get("op", "")
            rhs      = cond.get("rhs")

            # view key validation — allow unknown keys with a warning (hardware pin ids
            # that are in prefs but not in class attrs cannot be checked statically)
            if view_key not in valid_view_keys:
                errors.append(
                    f"{cloc}: view key '{view_key}' not found in SEMANTIC_HARDWARE, "
                    f"FLAGS, PARAMS, or HARDWARE pin ids. "
                    f"(If this is a hardware pin letter like 'IR2', ensure it appears "
                    f"in cls.HARDWARE)"
                )

            if op_str not in VALID_OPS:
                errors.append(
                    f"{cloc}: unknown op '{op_str}'. Allowed: {sorted(VALID_OPS)}"
                )

            _validate_arg_ref(rhs, cloc + " rhs", flag_keys, params_keys, errors)

    # ── Trigger assignments ───────────────────────────────────────────────────────────
    hardware = getattr(cls, "HARDWARE", {})
    hw_pin_ids = set()
    for group_vals in hardware.values():
        if isinstance(group_vals, dict):
            hw_pin_ids.update(group_vals.keys())

    for ta_idx, assignment in enumerate(trigger_asgn):
        trigger_name = assignment.get("trigger_name", "")
        handler_type = assignment.get("handler", "")
        loc = f"[trigger_assignment[{ta_idx}] trigger='{trigger_name}']"

        if handler_type not in VALID_HANDLERS:
            errors.append(
                f"{loc}: unknown handler '{handler_type}'. Allowed: {sorted(VALID_HANDLERS)}"
            )

        # trigger_name must correspond to a known hardware pin id
        if trigger_name not in hw_pin_ids:
            errors.append(
                f"{loc}: trigger_name '{trigger_name}' not found in any HARDWARE group. "
                f"Available pin ids: {sorted(hw_pin_ids)}"
            )

    return errors


def _validate_arg_ref(arg, loc: str, flag_keys: set, params_keys: set, errors: List[str]):
    """Validate a single arg/rhs value that may be a literal or a ref dict."""
    if not isinstance(arg, dict):
        return  # literal — always OK
    if "param" in arg:
        if arg["param"] not in params_keys:
            errors.append(
                f"{loc}: param ref '{arg['param']}' not in PARAMS. "
                f"Available: {sorted(params_keys)}"
            )
    elif "flag" in arg:
        if arg["flag"] not in flag_keys:
            errors.append(
                f"{loc}: flag ref '{arg['flag']}' not in FLAGS. "
                f"Available: {sorted(flag_keys)}"
            )
    elif "now" in arg:
        pass  # always valid
    else:
        errors.append(f"{loc}: unrecognized arg dict {arg!r}")


def main():
    parser = argparse.ArgumentParser(
        description="Validate an FDA v2 JSON file against a toolkit class.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    parser.add_argument(
        "toolkit",
        help="Toolkit class name (registered) or fully-qualified dotted path",
    )
    parser.add_argument(
        "fda_json",
        help="Path to the FDA v2 JSON file",
    )
    parser.add_argument(
        "--verbose", "-v",
        action="store_true",
        help="Print additional info (state count, transition count, toolkit attrs)",
    )
    args = parser.parse_args()

    # Load JSON
    if not os.path.exists(args.fda_json):
        print(f"ERROR: File not found: {args.fda_json}", file=sys.stderr)
        sys.exit(2)
    try:
        with open(args.fda_json) as f:
            definition = json.load(f)
    except json.JSONDecodeError as e:
        print(f"ERROR: Invalid JSON in '{args.fda_json}': {e}", file=sys.stderr)
        sys.exit(2)

    # Load toolkit class
    cls = load_toolkit_class(args.toolkit)

    if args.verbose:
        print(f"Toolkit: {cls.__name__} ({cls.__module__})")
        print(f"  SEMANTIC_HARDWARE keys: {sorted(get_class_attr_keys(cls, 'SEMANTIC_HARDWARE'))}")
        print(f"  FLAGS keys:             {sorted(get_class_attr_keys(cls, 'FLAGS'))}")
        print(f"  CALLABLE_METHODS:       {get_class_attr_list(cls, 'CALLABLE_METHODS')}")
        print(f"  REQUIRED_PACKAGES:      {get_class_attr_list(cls, 'REQUIRED_PACKAGES')}")
        print()

    # Validate
    errors = validate_fda(cls, definition)

    states_count      = len(definition.get("states", {}))
    transitions_count = len(definition.get("transitions", []))

    if errors:
        for err in errors:
            print(f"ERROR {err}", file=sys.stderr)
        print(
            f"\nValidation FAILED ({len(errors)} error{'s' if len(errors) != 1 else ''}, "
            f"{states_count} states, {transitions_count} transitions)",
            file=sys.stderr,
        )
        sys.exit(1)
    else:
        print(
            f"Validation PASSED ({states_count} states, {transitions_count} transitions)"
        )
        sys.exit(0)


if __name__ == "__main__":
    main()
```
</task>

## Verification

1. Create a minimal valid v2 JSON file `test_valid.json`:
   ```json
   {
     "version": 2,
     "initial_state": "prepare_session",
     "states": {
       "prepare_session": {},
       "trial_onset": {}
     },
     "transitions": [
       {"from": "prepare_session", "to": "trial_onset", "conditions": [], "description": ""}
     ],
     "trigger_assignments": []
   }
   ```
   Run: `python tools/validate_fda.py AppetitveTaskReal test_valid.json`
   Expected: `Validation PASSED (2 states, 1 transitions)`, exit code 0.

2. Create an invalid JSON with unknown state ref in transition:
   ```json
   {
     "version": 2,
     "initial_state": "prepare_session",
     "states": {"prepare_session": {}},
     "transitions": [
       {"from": "prepare_session", "to": "nonexistent_state", "conditions": []}
     ]
   }
   ```
   Expected: exit code 1, error message mentioning `'to' state 'nonexistent_state' not in states dict`.

3. Create a JSON with a `type: "method"` action referencing a non-existent callable:
   ```json
   {
     "version": 2,
     "initial_state": "trial_onset",
     "states": {
       "trial_onset": {
         "entry_actions": [{"type": "method", "ref": "nonexistent_fn", "args": []}]
       }
     },
     "transitions": []
   }
   ```
   Expected: exit code 1, error mentioning `ref 'nonexistent_fn' not in CALLABLE_METHODS`.

4. Run with `--verbose` flag to confirm toolkit attrs are printed.

5. Run with a non-existent JSON file — expect exit code 2 with "File not found" message.

## must_haves
- [ ] Exit 0 on valid FDA JSON
- [ ] Exit 1 with specific per-error messages for all validation failures listed in the plan
- [ ] Exit 2 for usage errors (missing file, bad class name)
- [ ] Passthrough state missing Python method raises error with state name
- [ ] `type: "method"` ref not in `CALLABLE_METHODS` raises error with state name and action index
- [ ] Unknown transition `to`/`from` state names report state name and transition index
- [ ] Does not instantiate the task class (no hardware required)
- [ ] Tool is executable as `python tools/validate_fda.py ClassName file.json`
