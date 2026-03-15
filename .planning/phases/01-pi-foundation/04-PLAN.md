---
plan: 04
wave: 1
title: "pilot.py HANDSHAKE enrichment"
depends_on: []
files_modified:
  - ~/pi-mirror/autopilot/autopilot/core/pilot.py
autonomous: true
requirements:
  - HOT-02
  - FDA-12
---

# Plan 04: pilot.py HANDSHAKE enrichment

## Goal

Extend `extract_task_metadata()` in `pilot.py` to include `flags`, `semantic_hardware`, `stage_names`, `callable_methods`, and `required_packages` from the task class's new class attributes. The enriched payload flows through `handshake()` → ZMQ HANDSHAKE message → orchestrator → Phase 2's `task_toolkits` table.

## Context

`pilot.py`'s `extract_task_metadata()` currently returns:
```python
{
    "task_name": ...,
    "base_class": ...,
    "module": ...,
    "params": {...},    # normalized schema
    "hardware": {...},  # serialized HARDWARE dict
    "file_hash": ...
}
```

The orchestrator's HANDSHAKE handler reads this array and upserts into the `task_definitions` table. In Phase 2, a new `task_toolkits` table will be populated with the enriched fields. For Phase 1, the task is simply to include the new fields in the payload — the orchestrator ignores unknown keys gracefully (it just doesn't store them until Phase 2).

All five new fields come from class attributes added in Plan 01:
- `FLAGS` — already existed on `mics_task` and its subclasses
- `SEMANTIC_HARDWARE` — new, added in Plan 01 (defaults to `{}`)
- `STAGE_NAMES` — already existed on `Task` base class (list of strings)
- `CALLABLE_METHODS` — new, added in Plan 01 (defaults to `[]`)
- `REQUIRED_PACKAGES` — new, added in Plan 01 (defaults to `[]`)

This plan is independent of Plans 02 and 03 — it only reads class attributes and serializes them. It does not call `load_fda_from_json` and does not require the FDA loading machinery.

### FLAGS serialization

`FLAGS` is a class-level dict like:
```python
FLAGS = {
    "hits": {
        "type": Tracker.Counter_Tracker,
        "name": "hits",
        "initial_value": 0
    }
}
```

The `"type"` value is a Python class (e.g. `Tracker.Counter_Tracker`). It must be serialized to a string for JSON transport. Use the existing `serialize_class()` helper on `Pilot` — it returns `{"class_name": ..., "module": ..., "full_name": ...}` for class objects.

Serialized FLAGS format:
```json
{
  "hits": {
    "type": {"class_name": "Counter_Tracker", "module": "autopilot.utils.Tracker", "full_name": "..."},
    "name": "hits",
    "initial_value": 0
  }
}
```

### SEMANTIC_HARDWARE serialization

`SEMANTIC_HARDWARE` maps `str → (group, id)` where the value is a tuple. Tuples are not JSON-serializable. Serialize to `str → [group, id]` (list):
```json
{
  "reward_port": ["GPIO", "VALVE1"],
  "cue_audio":   ["Mixer", "AUDIO1"]
}
```

## Tasks

<task id="04-1" title="Add _serialize_flags() helper to Pilot">

In `~/pi-mirror/autopilot/autopilot/core/pilot.py`, add the following helper method to the `Pilot` class (after `serialize_hardware_dict()`, which is around line 284):

```python
def _serialize_flags(self, flags_dict: dict) -> dict:
    """
    Serialize a FLAGS class attribute dict for JSON transport.

    FLAGS values may contain Python class references (under "type" key).
    These are serialized using serialize_class() to {"class_name", "module", "full_name"}.
    All other values are left as-is (they must be JSON-serializable).

    Args:
        flags_dict: The task class's FLAGS class attribute.

    Returns:
        A JSON-serializable dict.
    """
    result = {}
    for flag_name, flag_info in flags_dict.items():
        serialized_info = {}
        for k, v in flag_info.items():
            if k == "type" and inspect.isclass(v):
                serialized_info[k] = self.serialize_class(v)
            else:
                serialized_info[k] = v
        result[flag_name] = serialized_info
    return result
```
</task>

<task id="04-2" title="Add _serialize_semantic_hardware() helper to Pilot" depends_on="04-1">

Add the following helper method to the `Pilot` class, immediately after `_serialize_flags()`:

```python
def _serialize_semantic_hardware(self, semantic_hw: dict) -> dict:
    """
    Serialize a SEMANTIC_HARDWARE class attribute for JSON transport.

    SEMANTIC_HARDWARE maps str → (group, id) tuple. Tuples are serialized as lists
    for JSON compatibility: str → [group, id].

    Args:
        semantic_hw: The task class's SEMANTIC_HARDWARE dict.

    Returns:
        A JSON-serializable dict with list values instead of tuple values.
    """
    return {k: list(v) for k, v in semantic_hw.items()}
```
</task>

<task id="04-3" title="Extend extract_task_metadata() to include enriched fields" depends_on="04-2">

In `~/pi-mirror/autopilot/autopilot/core/pilot.py`, locate `extract_task_metadata()`. Find the `return` statement at the end of the method (currently around line 364-371):

```python
    return {
        "task_name": cls.__name__,
        "base_class": base_task,
        "module": cls.__module__,
        "params": merged_params,
        "hardware": hardware,
        "file_hash": file_hash
    }
```

Replace it with:

```python
    # FLAGS: class attr on mics_task subclasses; default {} on base Task
    flags_raw = {}
    if hasattr(cls, "FLAGS"):
        try:
            flags_raw = dict(cls.FLAGS)
        except Exception:
            self.logger.warning(f"Failed reading FLAGS from {cls.__name__}")
    serialized_flags = self._serialize_flags(flags_raw)

    # SEMANTIC_HARDWARE: developer-defined friendly names → (group, id)
    semantic_hw_raw = {}
    if hasattr(cls, "SEMANTIC_HARDWARE"):
        try:
            semantic_hw_raw = dict(cls.SEMANTIC_HARDWARE)
        except Exception:
            self.logger.warning(f"Failed reading SEMANTIC_HARDWARE from {cls.__name__}")
    serialized_semantic_hw = self._serialize_semantic_hardware(semantic_hw_raw)

    # STAGE_NAMES: already a list of strings, safe to include directly
    stage_names = []
    if hasattr(cls, "STAGE_NAMES"):
        try:
            stage_names = list(cls.STAGE_NAMES)
        except Exception:
            self.logger.warning(f"Failed reading STAGE_NAMES from {cls.__name__}")

    # CALLABLE_METHODS: list of method name strings; defaults to [] if not defined
    callable_methods = []
    if hasattr(cls, "CALLABLE_METHODS"):
        try:
            callable_methods = list(cls.CALLABLE_METHODS)
        except Exception:
            self.logger.warning(f"Failed reading CALLABLE_METHODS from {cls.__name__}")

    # REQUIRED_PACKAGES: list of pip specifier strings; defaults to [] if not defined
    required_packages = []
    if hasattr(cls, "REQUIRED_PACKAGES"):
        try:
            required_packages = list(cls.REQUIRED_PACKAGES)
        except Exception:
            self.logger.warning(f"Failed reading REQUIRED_PACKAGES from {cls.__name__}")

    return {
        "task_name": cls.__name__,
        "base_class": base_task,
        "module": cls.__module__,
        "params": merged_params,
        "hardware": hardware,
        "file_hash": file_hash,
        # Enriched toolkit fields (HOT-02, FDA-12):
        "flags": serialized_flags,
        "semantic_hardware": serialized_semantic_hw,
        "stage_names": stage_names,
        "callable_methods": callable_methods,
        "required_packages": required_packages,
    }
```

Backward-compat note: the orchestrator's current HANDSHAKE handler (`upsert_pilot_tasks`) accesses known fields by name. Unknown extra keys in the task metadata dict are ignored. Adding new keys does not break any existing handler.
</task>

## Verification

1. `python -m py_compile autopilot/autopilot/core/pilot.py` exits 0.

2. In a test environment (not on Pi), import and call `extract_task_metadata` with a minimal mock class that has all the new attributes:
   ```python
   from autopilot.utils import Tracker
   class MockTask:
       __name__ = "MockTask"
       FLAGS = {"hits": {"type": Tracker.Counter_Tracker, "name": "hits", "initial_value": 0}}
       SEMANTIC_HARDWARE = {"reward_port": ("GPIO", "VALVE1")}
       STAGE_NAMES = ["prepare_session", "trial_onset"]
       CALLABLE_METHODS = ["randomize_iti"]
       REQUIRED_PACKAGES = ["numpy>=1.21"]
       PARAMS = {}
       HARDWARE = {}
   ```
   Confirm the returned dict has all seven expected keys, and that `flags["hits"]["type"]` is a dict (not a class), and `semantic_hardware["reward_port"]` is `["GPIO", "VALVE1"]` (list).

3. Start the Pi pilot process and inspect the HANDSHAKE ZMQ message received by the orchestrator. Confirm tasks array contains the new fields for `AppetitveTaskReal`:
   - `flags` has keys `hits`, `misses`, `false_alarms`, etc.
   - `semantic_hardware` is `{}` (since `AppetitveTaskReal` does not yet define `SEMANTIC_HARDWARE`)
   - `callable_methods` is `[]`
   - `required_packages` is `[]`

4. Confirm existing orchestrator HANDSHAKE handler does not error on the enriched payload.

## must_haves
- [ ] Backward compat: orchestrator HANDSHAKE handler ignores new keys gracefully
- [ ] `FLAGS` dict serialized with class references as dicts (not Python class objects)
- [ ] `SEMANTIC_HARDWARE` tuples serialized as lists
- [ ] `STAGE_NAMES`, `CALLABLE_METHODS`, `REQUIRED_PACKAGES` serialized as plain lists
- [ ] All five new fields present even if class does not define them (defaults to empty collections)
- [ ] No exception raised for classes that don't inherit from `mics_task` (e.g. old `Task` subclasses that have none of the new attrs)
- [ ] `pilot.py` compiles without syntax errors
