---
plan: 02
wave: 2
title: "load_fda_from_json() and _build_state_method() with all three modes"
depends_on: [01]
files_modified:
  - ~/pi-mirror/autopilot/autopilot/tasks/mics_task.py
autonomous: true
requirements:
  - FDA-01
  - FDA-02
  - FDA-03
  - FDA-05
  - FDA-06
  - FDA-07
  - FDA-10
  - FDA-11
---

# Plan 02: load_fda_from_json() and _build_state_method()

## Goal

Implement `load_fda_from_json()` on `mics_task` that accepts a v1 or v2 FDA JSON dict, resolves semantic hardware references (v2 only), builds state methods for all three modes (passthrough / GUI-built / hybrid), sets up the `FiniteDeterministicAutomaton`, and registers transitions. Also implement `_resolve_arg()` and `_build_state_method()` as helpers.

## Context

After Plan 01, calling `load_fda_from_json(definition)` raises `AttributeError`. This plan implements the method body. `_build_transition_lambda()` and `apply_trigger_assignments()` are in Plan 03. This plan calls `apply_trigger_assignments()` as a stub-tolerant call: if the method does not yet exist, the `if "trigger_assignments" in definition` block can simply be left as a TODO comment that Plan 03 fills in.

The `FiniteDeterministicAutomaton` (FDA) is NOT modified. Its API is:
- `add_method(bound_method)` — registers a callable
- `add_transition(from_method, to_method, expr_list, trans_description)` — registers a transition
- `set_initial_method(method)` — sets the starting state

The FDA stores methods by reference (not by name). Transitions stored as `(to_method, expr_list, description)` keyed by `from_method` object. `__next__` iterates by checking `all(expr() for expr in expr_list)`.

### FDA v2 JSON structure

```json
{
  "version": 2,
  "initial_state": "prepare_session",
  "semantic_hardware_overrides": {},
  "states": {
    "prepare_session": {},
    "trial_onset": {
      "entry_actions": [
        {"type": "method", "ref": "randomize_iti_duration"},
        {"type": "flag",   "ref": "hit_trial",   "method": "set",       "args": [false]},
        {"type": "flag",   "ref": "trial",        "method": "increment", "args": []},
        {"type": "special","ref": "INC_TRIAL_COUNTER"}
      ],
      "blocking": "stage_block",
      "return_data": {
        "trial_num": {"flag": "trial"}
      }
    },
    "stimulus": {
      "entry_actions": [
        {"type": "hardware", "ref": "cue_audio", "method": "set_by_filename",
         "args": ["alt_blip8.wav"], "kwargs": {"volume": 0.009}}
      ],
      "blocking": "stage_block"
    }
  },
  "transitions": [
    {
      "from": "prepare_session",
      "to":   "trial_onset",
      "conditions": [],
      "description": ""
    },
    {
      "from": "state_wait_time_window",
      "to":   "state_start_time_window_to_reward",
      "conditions": [
        {"view": "IR2", "op": "eq", "rhs": true}
      ],
      "description": "mouse performed nose poke"
    }
  ],
  "trigger_assignments": []
}
```

### Entry action types

| `type` | Required fields | What it does |
|---|---|---|
| `"hardware"` | `ref` (semantic name), `method` (string), `args` (list), optional `kwargs` (dict) | `self._semantic_hw[ref].method(*resolved_args, **resolved_kwargs)` |
| `"flag"` | `ref` (flag name in `self.flags`), `method` (`"set"`, `"increment"`, `"reset"`), `args` (list) | `self.flags[ref].method(*resolved_args)` |
| `"timer"` | `ref` (semantic name of timer hw), `method` (`"set"`, `"cancel"`), `args` | delegates to hardware method |
| `"special"` | `ref` one of `["INC_TRIAL_COUNTER"]` | `INC_TRIAL_COUNTER`: sends a ZMQ INC_TRIAL_COUNTER message via `self.node.send('T', 'INC_TRIAL_COUNTER', {})` |
| `"method"` | `ref` (Python method name), optional `args` (list) | calls `getattr(self, ref)(*resolved_args)` — `ref` must be in `CALLABLE_METHODS` |

### Condition operators

Map `op` string → Python operator:
```python
OP_MAP = {
    "eq":  operator.eq,
    "ne":  operator.ne,
    "lt":  operator.lt,
    "le":  operator.le,
    "gt":  operator.gt,
    "ge":  operator.ge,
}
```

### return_data value forms

- `{"flag": "flag_name"}` → `self.flags["flag_name"].value`
- `{"param": "param_name"}` → `self.params["param_name"]`
- `{"now": true}` → `datetime.now(jerusalem_tz).isoformat()`
- literal string/number → used directly

## Tasks

<task id="02-1" title="Add import operator at top of mics_task.py">

In `~/pi-mirror/autopilot/autopilot/tasks/mics_task.py`, add `import operator` to the imports section (alongside the existing `import random`, `import threading`, etc.).

This is needed by `_build_transition_lambda()` in Plan 03, but add it here since this plan adds the method stubs that reference the op map.
</task>

<task id="02-2" title="Implement _resolve_arg()" depends_on="02-1">

Add the following method to `mics_task` (after the existing helper methods, before the `############## STATES ###################` comment):

```python
def _resolve_arg(self, arg):
    """
    Resolve a single entry_action argument to its runtime value.

    Supported forms:
      {"param": "name"}  → self.params["name"]       (task parameter)
      {"flag":  "name"}  → self.flags["name"].value   (flag current value)
      {"now":   True}    → datetime.now(jerusalem_tz).isoformat()
      anything else      → returned as-is (literal int/float/str/bool/None)
    """
    if isinstance(arg, dict):
        if "param" in arg:
            key = arg["param"]
            if not hasattr(self, 'params') or key not in self.params:
                raise KeyError(
                    f"_resolve_arg: param '{key}' not found in self.params. "
                    f"Available: {list(getattr(self, 'params', {}).keys())}"
                )
            return self.params[key]
        if "flag" in arg:
            key = arg["flag"]
            if key not in self.flags:
                raise KeyError(
                    f"_resolve_arg: flag '{key}' not found in self.flags. "
                    f"Available: {list(self.flags.keys())}"
                )
            return self.flags[key].value
        if "now" in arg:
            return datetime.now(jerusalem_tz).isoformat()
    return arg
```

Note: `self.params` is set by the `Task` base class from `kwargs`. It is a plain dict of `{param_name: value}` passed at instantiation time. If the task was not given a param that is referenced in FDA JSON, raise a descriptive `KeyError` at load time (not silently at runtime).
</task>

<task id="02-3" title="Implement _build_state_method()" depends_on="02-2">

Add the following method to `mics_task`:

```python
def _build_state_method(self, name: str, state_def: dict):
    """
    Build a bound callable for the named FDA state.

    Three modes:
      1. Passthrough: state_def has no entry_actions (empty/absent) AND self has a method
         of that name → return getattr(self, name) directly. The Python method runs as-is.
      2. GUI-built: entry_actions present, no type:'method' actions → all behavior in JSON.
      3. Hybrid: entry_actions present with type:'method' actions → JSON delegates to
         Python callable(s) listed in CALLABLE_METHODS.

    Args:
        name:      State name string (matches a key in definition['states']).
        state_def: Dict from definition['states'][name]. May be empty {}.

    Returns:
        A bound callable suitable for FDA.add_method().

    Raises:
        ValueError: At load time if a type:'method' action references a name not in
                    self.CALLABLE_METHODS, or if a type:'hardware' action uses an unknown
                    semantic ref, or if type:'flag' action uses an unknown flag name.
    """
    entry_actions = state_def.get("entry_actions") or []
    blocking      = state_def.get("blocking")           # "stage_block" or None/absent
    return_data   = state_def.get("return_data") or {}

    # ── Mode 1: Passthrough ──────────────────────────────────────────────────────────
    if not entry_actions and hasattr(self, name):
        return getattr(self, name)

    # ── Validate entry_actions at load time ─────────────────────────────────────────
    for i, action in enumerate(entry_actions):
        atype = action.get("type")
        ref   = action.get("ref", "")

        if atype == "method":
            if ref not in self.__class__.CALLABLE_METHODS:
                raise ValueError(
                    f"State '{name}' action[{i}]: type:'method' ref '{ref}' is not in "
                    f"{self.__class__.__name__}.CALLABLE_METHODS = {self.__class__.CALLABLE_METHODS}"
                )
        elif atype == "hardware":
            if ref not in self._semantic_hw:
                raise ValueError(
                    f"State '{name}' action[{i}]: type:'hardware' ref '{ref}' not found in "
                    f"_semantic_hw. Available: {list(self._semantic_hw.keys())}"
                )
        elif atype == "flag":
            if ref not in self.flags:
                raise ValueError(
                    f"State '{name}' action[{i}]: type:'flag' ref '{ref}' not found in "
                    f"self.flags. Available: {list(self.flags.keys())}"
                )
        elif atype == "special":
            if ref not in ("INC_TRIAL_COUNTER",):
                raise ValueError(
                    f"State '{name}' action[{i}]: unknown special ref '{ref}'. "
                    f"Known: ['INC_TRIAL_COUNTER']"
                )
        elif atype not in ("timer",):
            raise ValueError(
                f"State '{name}' action[{i}]: unknown action type '{atype}'. "
                f"Expected: hardware, flag, timer, special, method"
            )

    # ── Modes 2 & 3: build a closure ────────────────────────────────────────────────
    # Capture by default-arg to avoid late-binding bugs in loop contexts.
    def _state_fn(
        _entry_actions=entry_actions,
        _blocking=blocking,
        _return_data=return_data,
        _name=name,
    ):
        # Execute each action in order
        for action in _entry_actions:
            atype = action.get("type")
            ref   = action.get("ref", "")
            args  = [self._resolve_arg(a) for a in action.get("args", [])]
            kwargs = {k: self._resolve_arg(v) for k, v in action.get("kwargs", {}).items()}

            if atype == "hardware":
                hw  = self._semantic_hw[ref]
                method_name = action["method"]
                getattr(hw, method_name)(*args, **kwargs)

            elif atype == "flag":
                flag = self.flags[ref]
                method_name = action["method"]
                getattr(flag, method_name)(*args)

            elif atype == "timer":
                hw  = self._semantic_hw[ref]
                method_name = action["method"]
                getattr(hw, method_name)(*args, **kwargs)

            elif atype == "special":
                if ref == "INC_TRIAL_COUNTER":
                    self.node.send('T', 'INC_TRIAL_COUNTER', {})

            elif atype == "method":
                # Hybrid mode: call Python toolkit method
                getattr(self, ref)(*args)

        # Collect return_data
        data = {}
        for key, val_spec in _return_data.items():
            if isinstance(val_spec, dict):
                if "flag" in val_spec:
                    data[key] = self.flags[val_spec["flag"]].value
                elif "param" in val_spec:
                    data[key] = self.params[val_spec["param"]]
                elif "now" in val_spec:
                    data[key] = datetime.now(jerusalem_tz).isoformat()
                else:
                    data[key] = val_spec
            else:
                data[key] = val_spec

        # Blocking behavior
        if _blocking == "stage_block":
            return self.wait_for_condition()

        return data if data else None

    # Rename function for readable FDA trace logs
    _state_fn.__name__ = name
    _state_fn.__qualname__ = f"{self.__class__.__name__}.{name}"

    # Bind to self so FDA introspection works the same as a regular bound method
    import types as _types
    return _types.MethodType(_state_fn, self)
```

Key notes:
- The closure captures `entry_actions`, `blocking`, `return_data`, and `name` by default-arg to avoid late-binding bugs when this method is called in a loop over states.
- `wait_for_condition()` is a generator-based method that already exists on `mics_task`. Returning its result from the state function satisfies the pilot's `isinstance(result_obj, types.GeneratorType)` check in `run_task`.
- `INC_TRIAL_COUNTER` sends via `self.node` — `self.node` is available because `Task.__init__` sets `self.node = kwargs['node']`.
</task>

<task id="02-4" title="Implement load_fda_from_json()" depends_on="02-3">

Add the following method to `mics_task`:

```python
def load_fda_from_json(self, definition: dict):
    """
    Load a complete FDA state machine from a v1 or v2 JSON definition dict.

    Replaces any state methods and transitions previously added to self.stages.
    Safe to call at task start (before the first run_task iteration).

    v1 format: states is a list of state name strings (all passthrough), no
    semantic_hardware_overrides or trigger_assignments.
    v2 format: states is a dict mapping name → state_def, full feature set.

    Args:
        definition: FDA JSON dict. 'version' key is optional (defaults to 1).
                    See plan docs for schema.

    Raises:
        ValueError:  Unknown version, missing initial_state, unknown state name, etc.
        KeyError:    SEMANTIC_HARDWARE ref or param ref not found.
        RuntimeError: If called after the task has already started executing states.
    """
    version = definition.get("version", 1)

    # ── v1 normalization ─────────────────────────────────────────────────────────────
    # v1 states is a list of name strings. Convert to a dict of empty state_defs so
    # the rest of this method handles both versions identically. Passthrough mode
    # (_build_state_method with empty {}) will use getattr(self, name).
    # v1 has no semantic_hardware_overrides or trigger_assignments — those sections
    # are simply absent, so the later steps below will skip them correctly.
    if version == 1:
        raw_states = definition.get("states", [])
        if not isinstance(raw_states, list):
            raise ValueError(
                f"load_fda_from_json: version=1 expects 'states' to be a list of "
                f"state name strings, got {type(raw_states).__name__}."
            )
        definition = dict(definition)          # shallow copy — don't mutate caller's dict
        definition["states"] = {name: {} for name in raw_states}
    elif version != 2:
        raise ValueError(
            f"load_fda_from_json: unsupported FDA version={version}. "
            f"Supported versions: 1, 2."
        )

    # ── 1. Reset the existing FDA ────────────────────────────────────────────────────
    # Replace self.stages with a fresh instance so stale methods/transitions don't leak.
    self.stages = FiniteDeterministicAutomaton(self.event_queue, self.event_dispatcher)

    # ── 2. Build semantic hardware map ──────────────────────────────────────────────
    # Start from toolkit class attribute, then apply any per-definition overrides.
    base_semantic = dict(self.__class__.SEMANTIC_HARDWARE)
    overrides = definition.get("semantic_hardware_overrides") or {}
    base_semantic.update(overrides)

    self._semantic_hw = {}
    for friendly_name, (group, hw_id) in base_semantic.items():
        try:
            self._semantic_hw[friendly_name] = self.hardware[group][hw_id]
        except KeyError:
            raise KeyError(
                f"load_fda_from_json: SEMANTIC_HARDWARE entry '{friendly_name}' "
                f"references hardware['{group}']['{hw_id}'] which does not exist. "
                f"Available groups: {list(self.hardware.keys())}"
            )

    # ── 3. Build state methods ───────────────────────────────────────────────────────
    states_def = definition.get("states", {})
    if not states_def:
        raise ValueError("load_fda_from_json: 'states' dict is absent or empty.")

    state_method_map = {}  # name → bound method, for transition lookup below
    for state_name, state_def in states_def.items():
        method = self._build_state_method(state_name, state_def)
        self.stages.add_method(method)
        state_method_map[state_name] = method

    # ── 4. Set initial state ─────────────────────────────────────────────────────────
    initial = definition.get("initial_state")
    if not initial:
        raise ValueError("load_fda_from_json: 'initial_state' is required.")
    if initial not in state_method_map:
        raise ValueError(
            f"load_fda_from_json: initial_state '{initial}' is not in states dict. "
            f"Available states: {list(state_method_map.keys())}"
        )
    self.stages.set_initial_method(state_method_map[initial])

    # ── 5. Register transitions ──────────────────────────────────────────────────────
    for trans in definition.get("transitions", []):
        from_name = trans["from"]
        to_name   = trans["to"]
        conditions = trans.get("conditions", [])
        description = trans.get("description", "")

        if from_name not in state_method_map:
            raise ValueError(
                f"load_fda_from_json: transition 'from' state '{from_name}' not in states dict."
            )
        if to_name not in state_method_map:
            raise ValueError(
                f"load_fda_from_json: transition 'to' state '{to_name}' not in states dict."
            )

        expr_list = [
            self._build_transition_lambda(cond) for cond in conditions
        ]
        self.stages.add_transition(
            state_method_map[from_name],
            state_method_map[to_name],
            expr_list,
            trans_description=description,
        )

    # ── 6. Apply trigger assignments ────────────────────────────────────────────────
    # Defined in Plan 03. Call is conditional so this method works before Plan 03 is deployed.
    if hasattr(self, 'apply_trigger_assignments'):
        self.apply_trigger_assignments(definition)

    # ── 7. Store registry for future hot-reload ──────────────────────────────────────
    self._fda_definition = definition
    self._state_method_registry = state_method_map

    self.logger.info(
        f"load_fda_from_json: loaded {len(states_def)} states, "
        f"{len(definition.get('transitions', []))} transitions."
    )
```

Notes on the FDA reset (step 1):
- `self.stages` is assigned a fresh `FiniteDeterministicAutomaton` instance. This works because `self.stages` is an instance attribute set in `mics_task.__init__` — a new assignment replaces it cleanly.
- Hot-reload between runs (Phase 2): the orchestrator includes fresh `fda_json` in each START payload. When `l_start` creates a new task instance, `mics_task.__init__` creates a fresh `self.stages`, then the hook calls `load_fda_from_json()`. No mid-execution replacement needed.

Notes on `_build_transition_lambda`:
- Called here but defined in Plan 03. The call is inside the method body, so Python does not resolve it at class definition time — only at call time. Deploying this method before Plan 03 will cause an `AttributeError` only if `transitions` are non-empty AND `conditions` list is non-empty. Passthrough states with empty `conditions: []` will work. Full testing requires Plan 03.
</task>

## Verification

**Before any Pi test — deploy to Pi:**
```bash
cd ~/pi-mirror && ./tools/deploy_pi.sh
```
Sync `~/pi-mirror/autopilot/` to the Pi and restart the pilot process before running any on-Pi test below. Steps 1–2 can be run locally in `~/pi-mirror/`; steps 3+ require the Pi.

1. `python -m py_compile autopilot/autopilot/tasks/mics_task.py` exits 0.

2. Existing task starts without `state_machine` kwarg — identical behavior, no errors.

3. Start a task with a minimal v2 JSON that has only passthrough states (all `{}`):
   ```python
   definition = {
     "version": 2,
     "initial_state": "prepare_session",
     "states": {"prepare_session": {}},
     "transitions": []
   }
   task = AppetitveTaskReal(..., state_machine=definition)
   ```
   Confirm `task.stages.initial_method` is `task.prepare_session` (the original method).

4. Start a task with a v2 JSON that has a GUI-built state with `entry_actions` and `blocking: "stage_block"`. The generated state function should be callable and return a generator.

5. Start a task with a v1 JSON (states as a list):
   ```python
   definition = {
     "version": 1,
     "initial_state": "prepare_session",
     "states": ["prepare_session", "trial_onset", "stimulus", "state_lick"],
     "transitions": [
       {"from": "prepare_session", "to": "trial_onset", "conditions": []}
     ]
   }
   task = AppetitveTaskReal(..., state_machine=definition)
   ```
   Confirm all four states are registered and `task.stages.initial_method` is `task.prepare_session`.

6. Verify `load_fda_from_json` raises `ValueError` for an unsupported version (e.g., version=3).

7. Verify `_resolve_arg({"param": "ITI_center"})` returns the correct value when `self.params` is set.

## must_haves
- [ ] Backward compat: tasks without `state_machine` kwarg are completely unaffected
- [ ] `load_fda_from_json(definition)` handles version=1 (states as list) by normalizing to `{name: {}}` dict before processing
- [ ] v1 format: all states treated as passthrough (Mode 1), no `semantic_hardware_overrides` or `trigger_assignments` required
- [ ] `load_fda_from_json(definition)` raises `ValueError` for unsupported version (not 1 or 2) with clear message
- [ ] Passthrough states (empty `{}` or no `entry_actions`) return the original bound method via `getattr(self, name)`
- [ ] GUI-built state with `blocking: "stage_block"` returns a generator (via `wait_for_condition()`)
- [ ] GUI-built state without `blocking` returns `None` or data dict
- [ ] `type: "method"` action raises `ValueError` at load time if ref not in `CALLABLE_METHODS`
- [ ] `_semantic_hw` map built correctly from `SEMANTIC_HARDWARE` + overrides
- [ ] All state methods registered via `stages.add_method()` before any `add_transition()` call
- [ ] `INC_TRIAL_COUNTER` special action calls `self.node.send('T', 'INC_TRIAL_COUNTER', {})`
