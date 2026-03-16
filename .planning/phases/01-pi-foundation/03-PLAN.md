---
phase: 01-pi-foundation
plan: 03
type: execute
wave: 4
depends_on: [02]
files_modified:
  - ~/pi-mirror/autopilot/autopilot/tasks/mics_task.py
autonomous: true
requirements:
  - FDA-05
  - TRIG-01
  - TRIG-02
  - TRIG-03
  - TRIG-04
  - TRIG-05
must_haves:
  truths:
    - "_build_transition_lambda() is defined on mics_task and returns a callable lambda"
    - "apply_trigger_assignments() wires touch_detector and digital_input handlers correctly"
    - "All five TRIG-01–05 acceptance criteria can be manually verified on hardware"
  artifacts:
    - path: "~/pi-mirror/autopilot/autopilot/tasks/mics_task.py"
      contains: "_build_transition_lambda"
    - path: "~/pi-mirror/autopilot/autopilot/tasks/mics_task.py"
      contains: "apply_trigger_assignments"
  key_links:
    - from: "load_fda_from_json"
      to: "_build_transition_lambda"
      via: "transitions loop in Plan 02 calls this helper per transition"
    - from: "load_fda_from_json"
      to: "apply_trigger_assignments"
      via: "conditional call in Plan 02 after transitions loop"
title: "_build_transition_lambda() and apply_trigger_assignments()"
---

# Plan 03: _build_transition_lambda() and apply_trigger_assignments()

## Goal

Implement `_build_transition_lambda()` to convert a condition dict from FDA JSON into a Python lambda, and implement `apply_trigger_assignments()` to wire semantic view-update callbacks on top of the existing Hardware_Event logging path.

## Context

Plan 02's `load_fda_from_json()` calls `_build_transition_lambda(cond)` for every transition condition and calls `apply_trigger_assignments(definition)` at the end. This plan provides both.

### How triggers work in the existing codebase

`Task.init_hardware()` calls `hw.assign_cb(partial(self.handle_trigger, hardware=hw))` for every `is_trigger` hardware. `handle_trigger()` puts the event onto `self.event_queue`. `process_queue()` dequeues it and calls `execute_trigger()`.

`execute_trigger()` unconditionally:
1. Dispatches a `Hardware_Event` via `self.event_dispatcher` (this is always done regardless of trigger assignments)
2. Looks up `self.triggers[pin]` and calls each callback in the list

`self.triggers` is a plain dict. Values can be a single callable or a list of callables. `execute_trigger()` already normalizes: `triggers = self.triggers[pin] if isinstance(self.triggers[pin], list) else [self.triggers[pin]]`.

`apply_trigger_assignments()` adds NEW entries to `self.triggers[trigger_name]` (appending to the list if already populated). It never replaces the dict — it only extends it. The `Hardware_Event` dispatch in `execute_trigger()` always fires unconditionally for all triggers regardless of what is in `trigger_assignments`.

### Handler types

| Handler | Behavior |
|---|---|
| `"touch_detector"` | calls `hw.detect_change()` (reads MPR121 register), updates `self.view.view[f"{device_name}{channel}"]` for each channel that changed |
| `"digital_input"` | reads `hw.hardware_state` (already updated by `execute_trigger` before callbacks fire), sets `self.view.view[config["view_key"]] = hw.hardware_state` |
| `"log_only"` | no-op callback — only the unconditional Hardware_Event logging fires |
| `"default"` | no callback registered — the existing `handle_trigger` path fires naturally |

For `touch_detector`, the `Touch_Detector.detect_change()` method (line 831 of i2c.py) reads the MPR121 and returns changed channel values. After calling it, the `self.view.view[f"{device_name}{channel}"]` tracker `.set()` method should be called with the new value to update the view that FDA transition lambdas check.

### trigger_assignments JSON section

```json
"trigger_assignments": [
  {
    "trigger_name": "TOUCH_INT",
    "handler": "touch_detector",
    "config": {
      "hardware_ref": "lick_sensor",
      "emit_continuous": false
    }
  },
  {
    "trigger_name": "IR2",
    "handler": "digital_input",
    "config": {
      "view_key": "IR2"
    }
  }
]
```

`trigger_name` must match a key in `self.hardware[group][id]` — specifically the string used as the pin identifier in `self.triggers`. In the existing code, `pin_id` maps BCM→board→letter; `execute_trigger` is called with the letter key. Use the same letter as what appears in `self.triggers`.

## Tasks

<task id="03-1" title="Implement _build_transition_lambda()">

Add the following method to `mics_task`:

```python
def _build_transition_lambda(self, cond: dict):
    """
    Build a zero-argument callable (lambda) from a single transition condition dict.

    Condition dict schema:
      {
        "view":  "<view key>",     required — key into self.view.view
        "op":    "<operator>",     required — one of eq/ne/lt/le/gt/ge
        "rhs":   <value or ref>    required — right-hand side, passed through _resolve_arg
      }

    The returned lambda captures self, view_key, op_fn, and rhs_spec at construction time
    (default-arg capture to avoid late-binding).

    Returns:
        callable: zero-arg function that evaluates the condition against current view state.

    Raises:
        ValueError: At load time if op string is not in OP_MAP.
        KeyError:   At runtime if view_key is not in self.view.view (indicates missing
                    hardware or flag registration — programmer error, not user error).
    """
    import operator as _op

    OP_MAP = {
        "eq": _op.eq,
        "ne": _op.ne,
        "lt": _op.lt,
        "le": _op.le,
        "gt": _op.gt,
        "ge": _op.ge,
    }

    view_key = cond["view"]
    op_str   = cond["op"]
    rhs_spec = cond["rhs"]   # may be a literal or {"param":...} / {"flag":...}

    if op_str not in OP_MAP:
        raise ValueError(
            f"_build_transition_lambda: unknown op '{op_str}'. "
            f"Allowed: {list(OP_MAP.keys())}"
        )

    op_fn = OP_MAP[op_str]

    # Default-arg capture: view_key, op_fn, rhs_spec are bound at lambda creation time.
    # rhs_spec is NOT pre-resolved — it is resolved at each evaluation so that
    # {"param": "..."} always returns the current param value.
    def _transition_check(
        _view_key=view_key,
        _op_fn=op_fn,
        _rhs_spec=rhs_spec,
    ):
        current = self.view.get_value(_view_key)
        rhs     = self._resolve_arg(_rhs_spec)
        return _op_fn(current, rhs)

    return _transition_check
```

Note: `self.view.get_value(key)` calls `self.view.view[key].get_state()`. Hardware objects stored in `self.view.view` return their `hardware_state` attribute via `get_state()`. Flag Trackers return `.value`. The condition lambda re-evaluates on every call — it is not cached.
</task>

<task id="03-2" title="Implement apply_trigger_assignments()" depends_on="03-1">

Add the following method to `mics_task`:

```python
def apply_trigger_assignments(self, definition: dict):
    """
    Wire semantic view-update callbacks for trigger hardware based on the
    'trigger_assignments' section of the FDA JSON.

    This method ONLY adds additional callbacks to self.triggers[trigger_name].
    It does NOT replace or remove the existing Hardware_Event dispatch path in
    execute_trigger() — that always fires unconditionally for all triggers.

    If 'trigger_assignments' is absent from definition or is empty, this method
    returns immediately without modifying self.triggers (full backward compat).

    Args:
        definition: FDA JSON dict (the same dict passed to load_fda_from_json).
                    Any deprecated config.hardware_ref names will have already been
                    resolved by _resolve_renamed_trigger_refs before this is called.
    """
    assignments = definition.get("trigger_assignments")
    if not assignments:
        return  # Backward compat: no trigger_assignments → self.triggers unchanged

    for assignment in assignments:
        trigger_name = assignment["trigger_name"]
        handler_type = assignment["handler"]
        config       = assignment.get("config", {})

        if handler_type in ("default", "log_only"):
            # "default": the existing handle_trigger path fires naturally — no extra callback.
            # "log_only": same — only the unconditional Hardware_Event logging applies.
            continue

        elif handler_type == "touch_detector":
            callback = self._build_touch_detector_callback(trigger_name, config)

        elif handler_type == "digital_input":
            callback = self._build_digital_input_callback(trigger_name, config)

        else:
            raise ValueError(
                f"apply_trigger_assignments: unknown handler type '{handler_type}' "
                f"for trigger '{trigger_name}'. "
                f"Allowed: default, log_only, touch_detector, digital_input"
            )

        # Append to self.triggers — execute_trigger() already normalizes single callable
        # vs list, but we normalize here to always use lists for consistency.
        if trigger_name not in self.triggers:
            self.triggers[trigger_name] = []
        elif not isinstance(self.triggers[trigger_name], list):
            self.triggers[trigger_name] = [self.triggers[trigger_name]]
        self.triggers[trigger_name].append(callback)

def _build_touch_detector_callback(self, trigger_name: str, config: dict):
    """
    Build a callback for touch detector hardware (MPR121).

    Calls hw.detect_change() to read the current channel values from the device,
    then updates each per-channel view tracker to reflect the new state.
    Optionally emits a CONTINUOUS event (controlled by config["emit_continuous"]).

    config keys:
      hardware_ref (str):    Semantic name in self._semantic_hw — must be a Touch_Detector.
                             Any deprecated name will have been resolved by
                             _resolve_renamed_trigger_refs before this is called.
      emit_continuous (bool, optional): If True, dispatch a CONTINUOUS event after updating
                                         view. Default False.

    The callback signature is () → None (no positional args).
    execute_trigger() calls it without args (see task.py execute_trigger signature handling).
    """
    hw_ref          = config["hardware_ref"]
    emit_continuous = config.get("emit_continuous", False)

    # Validate at assignment time
    if hw_ref not in self._semantic_hw:
        raise ValueError(
            f"_build_touch_detector_callback: hardware_ref '{hw_ref}' not in _semantic_hw. "
            f"Available: {list(self._semantic_hw.keys())}"
        )
    hw = self._semantic_hw[hw_ref]

    def _touch_callback():
        # detect_change() reads MPR121 registers and returns list of (channel_idx, new_value)
        # or a channel-indexed array depending on implementation.
        # After calling, update view trackers for each channel.
        changed = hw.detect_change()
        # Touch_Detector has num_detectors channels, device_name attribute.
        # View trackers are keyed as "{device_name}{channel_idx}" (see check_for_detectors).
        if changed is not None:
            if hasattr(hw, 'num_detectors'):
                # detect_change() returns new values for all channels as a list/array
                for i in range(hw.num_detectors):
                    key = f"{hw.device_name}{i}"
                    if key in self.view.view:
                        try:
                            new_val = changed[i]
                            self.view.view[key].set(new_val)
                        except (IndexError, TypeError):
                            pass
        if emit_continuous:
            from autopilot.utils.Events import Event
            self.event_dispatcher.dispatch_event(
                Event(event_type="CONTINUOUS", event_data={"source": hw.device_name})
            )

    return _touch_callback

def _build_digital_input_callback(self, trigger_name: str, config: dict):
    """
    Build a callback for digital input hardware (GPIO beam-break, IR sensor).

    Reads the hardware's current hardware_state (already updated by execute_trigger
    before callbacks fire) and copies it into self.view.view[view_key].

    config keys:
      view_key (str): Key in self.view.view to update.

    The Hardware_Event is dispatched unconditionally by execute_trigger() before
    this callback fires — this callback only ensures the view stays in sync for
    FDA transition lambdas that read self.view.get_value(view_key).
    """
    view_key = config["view_key"]

    # Find the hardware object for this trigger to read its state.
    # We need to look it up at callback build time via self.hardware.
    # trigger_name is the pin letter (e.g. "IR2"), which is a key in some hw group.
    hw_obj = None
    for group_vals in self.hardware.values():
        if trigger_name in group_vals:
            hw_obj = group_vals[trigger_name]
            break

    if hw_obj is None:
        self.logger.warning(
            f"_build_digital_input_callback: trigger_name '{trigger_name}' not found "
            f"in any hardware group. View update will not occur."
        )

    def _digital_input_callback():
        if hw_obj is not None and view_key in self.view.view:
            # hardware_state has already been updated by execute_trigger()
            self.view.view[view_key].set(hw_obj.hardware_state)

    return _digital_input_callback
```

Critical invariant: `Hardware_Event` dispatch in `execute_trigger()` always fires for all GPIO edges, regardless of what `apply_trigger_assignments()` registers. These callbacks are purely additive — they keep the view in sync so FDA transition lambdas see accurate values.
</task>

## Verification

**Before any Pi test — deploy to Pi:**
```bash
cd ~/pi-mirror && ./tools/deploy_pi.sh
```
Steps 1–3 can be run locally in `~/pi-mirror/`. Steps 4+ (trigger callback and touch detector tests) require deploying to the Pi first and triggering real GPIO edges.

1. `python -m py_compile autopilot/autopilot/tasks/mics_task.py` exits 0.

2. Test `_build_transition_lambda` in isolation:
   ```python
   # With a mock task that has self.view.get_value("IR2") = True:
   cond = {"view": "IR2", "op": "eq", "rhs": True}
   fn = task._build_transition_lambda(cond)
   assert fn() == True
   ```

3. Test `_build_transition_lambda` with param-ref rhs:
   ```python
   # self.params["threshold"] = 5, self.view.get_value("lick_count") = 5
   cond = {"view": "lick_count", "op": "ge", "rhs": {"param": "threshold"}}
   fn = task._build_transition_lambda(cond)
   assert fn() == True
   ```

4. Test that a full v2 JSON with non-empty conditions loads and the FDA transitions evaluate correctly.

5. Test `apply_trigger_assignments` with empty `trigger_assignments: []` → `self.triggers` unchanged.

6. Test `apply_trigger_assignments` with `handler: "default"` → no entry added to `self.triggers`.

7. Test `apply_trigger_assignments` with `handler: "digital_input"` → callback appended to `self.triggers["IR2"]`.

8. Simulate a GPIO edge on a digital_input trigger: after the callback fires, confirm `self.view.get_value("IR2")` returns the updated state.

9. Verify `Hardware_Event` is dispatched (by checking `event_dispatcher.dispatch_event` was called) regardless of whether trigger_assignments is configured or not.

## must_haves
- [ ] Backward compat: `trigger_assignments` absent → `self.triggers` is not modified
- [ ] `_build_transition_lambda` raises `ValueError` at load time for unknown op string
- [ ] `_build_transition_lambda` uses default-arg capture (no late-binding bugs in loops)
- [ ] `apply_trigger_assignments` only appends to `self.triggers` — never replaces or clears
- [ ] `Hardware_Event` dispatch in `execute_trigger()` is NOT modified — fires unconditionally
- [ ] `touch_detector` handler calls `hw.detect_change()` and updates per-channel view trackers
- [ ] `digital_input` handler updates `self.view.view[view_key]` with current hardware_state
- [ ] `handler: "default"` and `handler: "log_only"` — no callback registered
- [ ] Unknown handler type raises `ValueError` at assignment time with descriptive message
