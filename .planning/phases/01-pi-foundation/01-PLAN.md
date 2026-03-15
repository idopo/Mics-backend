---
plan: 01
wave: 2
title: "mics_task class attributes and __init__ hook"
depends_on: [06]
files_modified:
  - ~/pi-mirror/autopilot/autopilot/tasks/mics_task.py
autonomous: true
requirements:
  - FDA-01
  - FDA-04
  - FDA-10
  - FDA-11
  - FDA-12
  - HOT-02
---

# Plan 01: mics_task class attributes and __init__ hook

## Goal

Add `SEMANTIC_HARDWARE`, `CALLABLE_METHODS`, and `REQUIRED_PACKAGES` class attributes to `mics_task`, and wire the optional `state_machine` kwarg detection in `__init__` so that JSON-driven FDA loading is triggered only when the kwarg is present.

## Context

This plan establishes the foundation that all other Pi Foundation plans build on. It does not yet implement `load_fda_from_json()` (Plan 02) — it only adds the class attributes and the detection hook. Existing tasks boot unchanged because the hook is conditional on `kwargs.get('state_machine')` returning a truthy value.

`mics_task.__init__` currently ends with `self.stages = FiniteDeterministicAutomaton(...)` and `return`. The hook is inserted **after** that line so the FDA object already exists before we call `load_fda_from_json()` in Plan 02.

The three class attributes are developer-defined public API on each toolkit subclass. They are intentionally declared with empty defaults on `mics_task` so subclasses without them still function.

## Tasks

<task id="01-1" title="Add SEMANTIC_HARDWARE class attribute">

In `~/pi-mirror/autopilot/autopilot/tasks/mics_task.py`, inside the `mics_task` class body, directly below the existing `FLAGS = {}` class attribute (line 33), add:

```python
SEMANTIC_HARDWARE: dict = {}
"""
Maps developer-assigned friendly names to (group, id) tuples identifying a hardware
object in self.hardware. Example:
    SEMANTIC_HARDWARE = {
        "reward_port": ("GPIO", "VALVE1"),
        "cue_led":     ("GPIO", "LED2"),
        "lick_sensor": ("i2c",  "LICKER1"),
    }
Keys are the strings used as "ref" in entry_actions with type "hardware".
Values are (group_key, id_key) where group_key matches a top-level key in self.HARDWARE
and id_key matches the pin/id within that group.
Developer-defined per toolkit — NOT editable from the GUI.
"""

CALLABLE_METHODS: list = []
"""
List of Python method name strings that may be called as entry_action building blocks
from a GUI-constructed state body (type: "method" action).
Example:
    CALLABLE_METHODS = ["randomize_iti_duration", "compute_catch_trial"]
Only methods explicitly listed here can appear as type:"method" actions in FDA JSON.
load_fda_from_json() raises a descriptive ValueError at load time if an action references
a name not in this list.
"""

REQUIRED_PACKAGES: list = []
"""
List of pip-installable package specifiers required at runtime.
Example:
    REQUIRED_PACKAGES = ["numpy>=1.21", "pyserial"]
Shipped in HANDSHAKE payload; consumed by Phase 8 (packages tab) to detect missing deps.
"""
```

Backward-compat note: All three default to empty collection, so existing subclasses that do not define them continue to work without modification.
</task>

<task id="01-2" title="Add state_machine kwarg detection hook in __init__" depends_on="01-1">

In `~/pi-mirror/autopilot/autopilot/tasks/mics_task.py`, inside `mics_task.__init__`, locate the final two lines:

```python
        self.stages = FiniteDeterministicAutomaton(self.event_queue, self.event_dispatcher)
        return
```

Replace them with:

```python
        self.stages = FiniteDeterministicAutomaton(self.event_queue, self.event_dispatcher)

        # Optional JSON-driven FDA: if a state_machine definition was passed as a kwarg,
        # load it now. This replaces the hardcoded stages.add_method / add_transition calls
        # that subclass __init__ methods normally perform. If absent, subclass __init__
        # proceeds normally — full backward compatibility.
        _state_machine_def = kwargs.get('state_machine')
        if _state_machine_def:
            self.load_fda_from_json(_state_machine_def)
        return
```

Backward-compat note: `kwargs.get('state_machine')` returns `None` for all existing task invocations (orchestrator never sends this key until Phase 2). The `if` guard means the `load_fda_from_json()` call path is completely unreachable for existing tasks. No behavior change.

Important: `load_fda_from_json` is defined in Plan 02. This call will raise `AttributeError` if a test passes `state_machine=...` before Plan 02 is deployed — that is intentional and expected. Do not stub the method here.
</task>

## Verification

**Before any Pi test — deploy to Pi:**
```bash
cd ~/pi-mirror && ./tools/deploy_pi.sh
```
This syncs `~/pi-mirror/autopilot/` to the Pi and restarts the pilot process. All on-Pi tests below require this step first. (Plan 06 must be complete before Plan 01 verification.)

1. After deploying, start any existing task (e.g. `AppetitiveTaskReal`) without passing `state_machine` kwarg. Confirm it boots and runs identically to before — no `AttributeError`, no behavior change.

2. Inspect the class:
   ```python
   from autopilot.tasks.mics_task import mics_task
   assert hasattr(mics_task, 'SEMANTIC_HARDWARE')
   assert hasattr(mics_task, 'CALLABLE_METHODS')
   assert hasattr(mics_task, 'REQUIRED_PACKAGES')
   assert mics_task.SEMANTIC_HARDWARE == {}
   assert mics_task.CALLABLE_METHODS == []
   assert mics_task.REQUIRED_PACKAGES == []
   ```

3. Confirm that `AppetitveTaskReal` (which defines `FLAGS`) still has `FLAGS` accessible and that the new attrs don't shadow it.

4. Grep for any syntax errors: `python -m py_compile autopilot/autopilot/tasks/mics_task.py` should exit 0.

## must_haves
- [ ] Backward compat: existing tasks boot without `state_machine` kwarg — no behavior change
- [ ] `SEMANTIC_HARDWARE`, `CALLABLE_METHODS`, `REQUIRED_PACKAGES` present as class attrs on `mics_task` with correct empty defaults
- [ ] `load_fda_from_json()` is NOT called when `state_machine` kwarg is absent
- [ ] `state_machine` kwarg presence (truthy dict) triggers `load_fda_from_json()` call
- [ ] `mics_task.py` compiles without syntax errors
