---
phase: 01-pi-foundation
type: execute
must_haves:
  truths:
    - "load_fda_from_json() handles v1 and v2 FDA JSON formats"
    - "Deprecated ref in SEMANTIC_HARDWARE_RENAMES resolves transparently with deprecation warning logged"
    - "INC_TRIAL_COUNTER special action sends ZMQ message"
    - "Passthrough states return original bound method"
  artifacts:
    - path: "~/pi-mirror/autopilot/autopilot/tasks/mics_task.py"
      contains: "_resolve_renamed_hw_refs"
  key_links:
    - from: "load_fda_from_json"
      to: "_resolve_renamed_hw_refs"
      via: "per-state call before _build_state_method"
plan: 02
wave: 3
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
  - FDA-13
  - FDA-15
  - FDA-16
---

# Plan 02: load_fda_from_json() and _build_state_method()

## Goal

Implement `load_fda_from_json()` on `mics_task` that accepts a v1 or v2 FDA JSON dict, resolves semantic hardware references (v2 only) with transparent fallback via `SEMANTIC_HARDWARE_RENAMES`, builds state methods for all three modes (passthrough / GUI-built / hybrid), sets up the `FiniteDeterministicAutomaton`, and registers transitions. Also implement `_resolve_arg()` and `_build_state_method()` as helpers.

## TDD Requirement

**Step 0 — Write failing tests before implementing.** Per `quality-guardrails.md`, no production code without a failing test first.

Create `~/pi-mirror/tests/test_load_fda_from_json.py` covering:
- `load_fda_from_json(v1_dict)` — v1 format passes through to legacy stages unchanged
- `load_fda_from_json(v2_dict)` — states added to FDA, transitions registered
- Deprecated `ref` in `SEMANTIC_HARDWARE_RENAMES` resolves transparently with logged warning
- Unknown ref raises `ValueError` with descriptive message
- Passthrough state (no `entry_actions`) returns original bound method

Mock: `self.view`, `self.hardware`, `self.stages` (FDA), `self.flags`. Use `unittest.mock.MagicMock`.

Run `python3 -m pytest -q tests/test_load_fda_from_json.py` and **confirm failure** before implementing.

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

<task id="02-4" title="params-as-props: set self.<param_name> after param resolution" depends_on="02-3">

In `load_fda_from_json()`, after params have been resolved (the task receives `self.params` populated by `Task.__init__` from kwargs), add a loop that sets each param as a direct instance attribute:

```python
# ── After v1 normalization, before step 1 (FDA reset) ────────────────────────────────
# FDA-15: expose resolved params as direct instance attrs so toolkit methods can use
# self.open_duration instead of self._resolve_arg({"param": "open_duration"}).
# Guard: only set attrs whose names are declared in self.PARAMS to avoid clobbering
# existing instance attrs (e.g. self.stages, self.flags, self.hardware).
params_declared = set(getattr(self.__class__, 'PARAMS', {}).keys())
for param_name, value in (getattr(self, 'params', {}) or {}).items():
    if param_name in params_declared:
        setattr(self, param_name, value)
```

Place this block at the start of `load_fda_from_json()`, after the v1 normalization / version-check block and before step 1 (FDA reset).

Notes:
- `self.params` is the plain dict set by `Task.__init__`; it contains the resolved runtime values.
- The guard `param_name in params_declared` ensures we never overwrite `self.flags`, `self.stages`, etc., even if a param happened to be named the same.
- Toolkit methods that use `self.open_duration` directly will now find the value without calling `_resolve_arg`.
</task>

<task id="02-5" title="_build_if_action() and _build_action_callable() helpers" depends_on="02-4">

Add three new methods to `mics_task` and update `_build_state_method()` to use them (FDA-16).

### Step 1: add module-level `_COMPARE` dict

Near the top of `mics_task.py`, after the imports (alongside `OP_MAP` if it exists, or near other module-level constants):

```python
import operator as _operator

_COMPARE = {
    "==": _operator.eq,
    "!=": _operator.ne,
    ">=": _operator.ge,
    "<=": _operator.le,
    ">":  _operator.gt,
    "<":  _operator.lt,
}
```

### Step 2: add `_build_condition_operand()` helper

Add this method to `mics_task` after `_resolve_arg()`:

```python
def _build_condition_operand(self, operand) -> callable:
    """
    Return a zero-arg callable that evaluates one side of an if-action condition.

    Supported forms:
      {"tracker": "name"}  → self.flags["name"].value  (tracker/flag value)
      {"flag": "name"}     → self.flags["name"].value  (alias for tracker)
      {"param": "name"}    → self.params["name"]       (resolved param value)
      {"hardware": "ref"}  → self._semantic_hw["ref"].value  (hardware state)
      bare literal         → returns the literal directly (int/float/str/bool/None)
    """
    if not isinstance(operand, dict):
        val = operand
        return lambda: val

    if "tracker" in operand or "flag" in operand:
        key = operand.get("tracker") or operand.get("flag")
        def _read_flag(_key=key):
            return self.flags[_key].value
        return _read_flag

    if "param" in operand:
        key = operand["param"]
        def _read_param(_key=key):
            return self.params[_key]
        return _read_param

    if "hardware" in operand:
        ref = operand["hardware"]
        hw  = self._semantic_hw[ref]
        def _read_hw(_hw=hw):
            return _hw.value
        return _read_hw

    raise ValueError(
        f"_build_condition_operand: unrecognized operand form {operand!r}. "
        f"Expected: {{tracker/flag/param/hardware: name}} or a bare literal."
    )
```

### Step 3: add `_build_if_action()` helper

```python
def _build_if_action(self, action: dict) -> callable:
    """
    Build a zero-arg callable for a type:'if' action (FDA-16).

    At runtime the callable:
      1. Evaluates condition.left and condition.right
      2. Applies condition.op
      3. Executes 'then' branch if True, 'else' branch if False
      4. Supports unlimited nesting: then/else arrays may contain type:'if' actions,
         handled recursively via _build_action_callable.

    Raises ValueError at load time if condition.op is unknown or a nested ref is invalid.
    """
    cond = action["condition"]
    op_str = cond["op"]
    if op_str not in _COMPARE:
        raise ValueError(
            f"_build_if_action: unknown condition op '{op_str}'. "
            f"Allowed: {sorted(_COMPARE.keys())}"
        )

    left_fn  = self._build_condition_operand(cond["left"])
    right_fn = self._build_condition_operand(cond["right"])
    compare  = _COMPARE[op_str]

    then_callables = [self._build_action_callable(a) for a in action.get("then", [])]
    else_callables = [self._build_action_callable(a) for a in action.get("else", [])]

    def _run_if(
        _left_fn=left_fn,
        _right_fn=right_fn,
        _compare=compare,
        _then=then_callables,
        _else=else_callables,
    ):
        l, r = _left_fn(), _right_fn()
        branch = _then if _compare(l, r) else _else
        for fn in branch:
            fn()

    return _run_if
```

### Step 4: add `_build_action_callable()` dispatcher

```python
def _build_action_callable(self, action: dict) -> callable:
    """
    Dispatch a single entry_action dict to the appropriate builder.
    Returns a zero-arg callable. Handles: hardware, flag, timer, special, method, if.
    Raises ValueError at load time for unknown type or invalid ref.
    """
    atype = action.get("type")
    if atype == "if":
        return self._build_if_action(action)

    ref    = action.get("ref", "")
    method = action.get("method", "")

    if atype in ("hardware", "timer"):
        hw = self._semantic_hw[ref]
        def _hw_call(_hw=hw, _method=method, _action=action):
            args   = [self._resolve_arg(a) for a in _action.get("args", [])]
            kwargs = {k: self._resolve_arg(v) for k, v in _action.get("kwargs", {}).items()}
            getattr(_hw, _method)(*args, **kwargs)
        return _hw_call

    elif atype == "flag":
        flag = self.flags[ref]
        def _flag_call(_flag=flag, _method=method, _action=action):
            args = [self._resolve_arg(a) for a in _action.get("args", [])]
            getattr(_flag, _method)(*args)
        return _flag_call

    elif atype == "special":
        if ref == "INC_TRIAL_COUNTER":
            def _inc():
                self.node.send('T', 'INC_TRIAL_COUNTER', {})
            return _inc
        raise ValueError(f"_build_action_callable: unknown special ref '{ref}'")

    elif atype == "method":
        def _method_call(_ref=ref, _action=action):
            args = [self._resolve_arg(a) for a in _action.get("args", [])]
            getattr(self, _ref)(*args)
        return _method_call

    raise ValueError(
        f"_build_action_callable: unknown action type '{atype}'. "
        f"Expected: hardware, flag, timer, special, method, if"
    )
```

### Step 5: update `_build_state_method()` to use `_build_action_callable()`

Replace the per-action dispatch inside the `_state_fn` closure with pre-built callables:

```python
# Pre-build all action callables at load time
action_callables = [self._build_action_callable(a) for a in entry_actions]

def _state_fn(
    _callables=action_callables,
    _blocking=blocking,
    _return_data=return_data,
    _name=name,
):
    for fn in _callables:
        fn()

    # Collect return_data (unchanged)
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

    if _blocking == "stage_block":
        return self.wait_for_condition()
    return data if data else None
```

Also update the load-time validation block: add `"if"` to the known types so the check doesn't reject it. Change:
```python
elif atype not in ("timer",):
```
to:
```python
elif atype not in ("timer", "if"):
```

Notes:
- Pre-building callables at load time means `_build_if_action` validates all nested refs recursively when `load_fda_from_json()` is called — any unknown ref raises `ValueError` at load time, not lazily at runtime.
- The `_COMPARE` dict is module-level to avoid recreating it on every `load_fda_from_json` call.
- `_build_condition_operand` uses default-arg capture (`lambda: val`, `_key=key`) to avoid late-binding closure bugs.
</task>

<task id="02-6" title="Implement load_fda_from_json() with SEMANTIC_HARDWARE_RENAMES fallback" depends_on="02-5">

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

    # Build the rename map for transparent backward-compat resolution (FDA-13).
    rename_map = dict(getattr(self.__class__, 'SEMANTIC_HARDWARE_RENAMES', {}))

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
        # Before building the state, resolve any deprecated hardware refs in entry_actions
        # via SEMANTIC_HARDWARE_RENAMES so _build_state_method sees only current names.
        resolved_state_def = self._resolve_renamed_hw_refs(state_def, rename_map)
        method = self._build_state_method(state_name, resolved_state_def)
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


def _resolve_renamed_hw_refs(self, state_def: dict, rename_map: dict) -> dict:
    """
    Return a copy of state_def with deprecated hardware/timer ref names replaced by their
    current names via rename_map (sourced from SEMANTIC_HARDWARE_RENAMES). Logs a
    deprecation warning for each renamed ref encountered.

    Rewrites:
    - entry_actions items with type 'hardware' or 'timer'
    - trigger_assignments items where config.hardware_ref appears in the rename map

    Returns state_def unchanged (by reference) if no renames are needed.

    Note: trigger_assignments rewriting is done in load_fda_from_json (not per-state),
    but this helper also accepts a full definition dict for that purpose — see
    _resolve_renamed_trigger_refs for the trigger_assignments pass.
    """
    if not rename_map:
        return state_def

    entry_actions = state_def.get("entry_actions")
    if not entry_actions:
        return state_def

    needs_rewrite = any(
        action.get("type") in ("hardware", "timer")
        and action.get("ref", "") in rename_map
        for action in entry_actions
    )
    if not needs_rewrite:
        return state_def

    # Shallow copy — only rewrite the entry_actions list
    new_actions = []
    for action in entry_actions:
        atype = action.get("type")
        ref   = action.get("ref", "")
        if atype in ("hardware", "timer") and ref in rename_map:
            new_name = rename_map[ref]
            self.logger.warning(
                f"Semantic hardware ref '{ref}' is deprecated, use '{new_name}' instead"
            )
            action = dict(action)   # shallow copy of the action dict
            action["ref"] = new_name
        new_actions.append(action)

    new_state_def = dict(state_def)
    new_state_def["entry_actions"] = new_actions
    return new_state_def


def _resolve_renamed_trigger_refs(self, definition: dict, rename_map: dict) -> dict:
    """
    Return a copy of definition with deprecated hardware ref names in
    trigger_assignments[*].config.hardware_ref replaced via rename_map.

    This prevents _build_touch_detector_callback from raising KeyError at load time
    when a trigger_assignment references a semantic name that has been renamed.
    Logs a deprecation warning for each renamed ref encountered.

    Returns definition unchanged (by reference) if no renames are needed.
    """
    if not rename_map:
        return definition

    assignments = definition.get("trigger_assignments")
    if not assignments:
        return definition

    needs_rewrite = any(
        assignment.get("config", {}).get("hardware_ref", "") in rename_map
        for assignment in assignments
    )
    if not needs_rewrite:
        return definition

    new_assignments = []
    for assignment in assignments:
        config = assignment.get("config", {})
        hw_ref = config.get("hardware_ref", "")
        if hw_ref and hw_ref in rename_map:
            new_name = rename_map[hw_ref]
            self.logger.warning(
                f"trigger_assignments config.hardware_ref '{hw_ref}' is deprecated, "
                f"use '{new_name}' instead"
            )
            new_config = dict(config)
            new_config["hardware_ref"] = new_name
            assignment = dict(assignment)
            assignment["config"] = new_config
        new_assignments.append(assignment)

    new_definition = dict(definition)
    new_definition["trigger_assignments"] = new_assignments
    return new_definition
```

After adding both methods, update `load_fda_from_json` step 6 to resolve renamed trigger refs before calling `apply_trigger_assignments`. Replace the step 6 block with:

```python
    # ── 6. Apply trigger assignments ────────────────────────────────────────────────
    # Resolve deprecated hardware_ref names in trigger_assignments before wiring.
    if rename_map and definition.get("trigger_assignments"):
        definition = self._resolve_renamed_trigger_refs(definition, rename_map)
    # Defined in Plan 03. Call is conditional so this method works before Plan 03 is deployed.
    if hasattr(self, 'apply_trigger_assignments'):
        self.apply_trigger_assignments(definition)
```

Notes on the FDA reset (step 1):
- `self.stages` is assigned a fresh `FiniteDeterministicAutomaton` instance. This works because `self.stages` is an instance attribute set in `mics_task.__init__` — a new assignment replaces it cleanly.
- Hot-reload between runs (Phase 2): the orchestrator includes fresh `fda_json` in each START payload. When `l_start` creates a new task instance, `mics_task.__init__` creates a fresh `self.stages`, then the hook calls `load_fda_from_json()`. No mid-execution replacement needed.

Notes on `_build_transition_lambda`:
- Called here but defined in Plan 03. The call is inside the method body, so Python does not resolve it at class definition time — only at call time. Deploying this method before Plan 03 will cause an `AttributeError` only if `transitions` are non-empty AND `conditions` list is non-empty. Passthrough states with empty `conditions: []` will work. Full testing requires Plan 03.

Notes on `_resolve_renamed_hw_refs` (FDA-13):
- Called per-state before `_build_state_method`, so the validation inside `_build_state_method` always sees the resolved (current) ref name in `_semantic_hw` — not the deprecated name.
- Deprecation warning is emitted once per action per `load_fda_from_json()` call (i.e. once per task start), not once per state execution.
- Does not mutate the caller's definition dict — creates shallow copies only of dicts that need rewriting.

Notes on `_resolve_renamed_trigger_refs` (WARNING-4 fix):
- Called in step 6 before `apply_trigger_assignments`, ensuring `_build_touch_detector_callback` never sees deprecated names in `config.hardware_ref`.
- Only rewrites assignments whose `config.hardware_ref` appears in the rename map — all others pass through unchanged.
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

8. Verify SEMANTIC_HARDWARE_RENAMES resolution (FDA-13):
   Define a toolkit subclass with:
   ```python
   SEMANTIC_HARDWARE = {"water_delivery": ("GPIO", "SOLENOID1")}
   SEMANTIC_HARDWARE_RENAMES = {"reward_port": "water_delivery"}
   ```
   Load a v2 FDA JSON with `"ref": "reward_port"` in an entry_action. Confirm:
   - Task starts without `KeyError`
   - A deprecation warning is logged: `"Semantic hardware ref 'reward_port' is deprecated, use 'water_delivery' instead"`
   - The action dispatches to the correct `water_delivery` hardware object

9. Verify `_resolve_renamed_trigger_refs` (WARNING-4 fix):
   Using the same toolkit above, load a v2 FDA JSON with a `trigger_assignments` entry where
   `config.hardware_ref` is `"reward_port"`. Confirm:
   - Task starts without `KeyError` in `_build_touch_detector_callback`
   - A deprecation warning is logged for the trigger_assignments rename
   - The callback resolves to the `water_delivery` hardware object

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
- [ ] Deprecated ref in `SEMANTIC_HARDWARE_RENAMES` resolves transparently; deprecation warning logged; no error raised (FDA-13)
- [ ] `_resolve_renamed_hw_refs` does not mutate the caller's definition dict
- [ ] Deprecated `config.hardware_ref` in `trigger_assignments` resolves transparently before `apply_trigger_assignments` is called (WARNING-4 fix)
- [ ] After `load_fda_from_json()`, `self.<param_name>` is set for every param declared in `PARAMS`; attrs not in `PARAMS` are not overwritten (FDA-15)
- [ ] `type: "if"` action with `condition.op >= ` and `then` branch executes correctly when condition is true; `else` executes when false (FDA-16)
- [ ] Nested `type: "if"` inside a `then` or `else` array executes correctly (recursive, FDA-16)
- [ ] Unknown `condition.op` raises `ValueError` at load time with clear message (FDA-16)
- [ ] `python3 -m pytest -q tests/test_load_fda_from_json.py` — all tests pass
- [ ] `ruff check autopilot/autopilot/tasks/mics_task.py` — zero errors
