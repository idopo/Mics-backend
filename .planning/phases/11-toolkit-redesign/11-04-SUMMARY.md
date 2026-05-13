---
phase: 11
plan: 4
subsystem: orchestrator, pi-mics-task
tags: [flags, params, injection, tracker, backend-toolkit]
dependency_graph:
  requires: [11-03]
  provides: [backend-FLAGS-PARAMS-injection]
  affects: [orchestrator_station.py, mics_task.py]
tech_stack:
  added: []
  patterns: [string-to-class-resolver, backward-compat-kwargs]
key_files:
  created: []
  modified:
    - orchestrator/orchestrator/orchestrator_station.py
    - ~/pi-mirror/autopilot/autopilot/tasks/mics_task.py
decisions:
  - "_resolve_flags() reads 'tracker_type' key (DB storage format) with 'type' as fallback — handles both formats for resilience"
  - "logging import inside _resolve_flags() uses 'import logging as _logging' to avoid shadowing the module-level logging"
metrics:
  duration_minutes: 3
  completed_date: "2026-05-04"
  tasks_completed: 4
  files_modified: 2
---

# Phase 11 Plan 4: FLAGS + PARAMS Backend Injection Summary

**One-liner:** Backend now sends FLAGS (tracker_type strings) and PARAMS into the Pi START payload; Pi resolves strings to Tracker classes via `_resolve_flags()` before `init_flags()` runs.

---

## What Was Built

Phase 11-03 claimed FLAGS/PARAMS injection but left a suppression comment in the orchestrator and no corresponding Pi handling. This plan closes that gap completely.

### Step 1: Orchestrator — inject FLAGS and PARAMS

**File:** `orchestrator/orchestrator/orchestrator_station.py`
**Method:** `_inject_backend_toolkit_spec()`

Replaced the suppression comment with conditional injection:
- `task["FLAGS"] = spec["flags"]` when `spec.get("flags")` is truthy
- `task["PARAMS"] = spec["params_schema"]` when `spec.get("params_schema")` is truthy
- FLAGS values remain as strings on the wire ("Counter_Tracker" etc.); Pi resolves them

**Commit:** cfb267b

### Steps 2+3: Pi — accept FLAGS/PARAMS + `_resolve_flags()`

**File:** `~/pi-mirror/autopilot/autopilot/tasks/mics_task.py`

In `__init__`, after the HARDWARE/PREFS_HARDWARE blocks:
```python
if "FLAGS" in kwargs:
    self.FLAGS = self._resolve_flags(kwargs["FLAGS"])
if "PARAMS" in kwargs:
    self.PARAMS = kwargs["PARAMS"]
```

New static method `_resolve_flags()` added after `_coerce_hw_value()`:
- Reads `tracker_type` key (DB storage format) with `type` as fallback
- Maps string names to `Counter_Tracker`, `Boolean_Tracker`, `Trial_Tracker` (imported directly at module level)
- Unknown type strings fall back to `Counter_Tracker` with `logger.warning`
- Removes `tracker_type` key and sets `type` = the actual class (what `init_flags()` expects)

**Commit:** 3657a64 (pi-mirror repo)

### Step 4: Deploy to Pi

Deployed via rsync with SSH key. MD5 sums verified to match on both sides:
`f917432a15f1afe69650c8d7276778c2`

---

## Backward Compatibility

If `FLAGS`/`PARAMS` are absent from kwargs (non-backend-authored toolkit), class-level declarations are used unchanged. No behavior change for existing tasks.

---

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] tracker_type key mismatch**
- **Found during:** Implementation review before coding
- **Issue:** Plan's `_resolve_flags()` used `spec.get("type", "Counter_Tracker")` but the DB stores flags with `tracker_type` key (not `type`). The `init_flags()` method expects `type` = actual class.
- **Fix:** `_resolve_flags()` pops `tracker_type` first (with `type` as fallback for resilience), then sets `type` = the resolved class. Both keys handled correctly.
- **Files modified:** `~/pi-mirror/autopilot/autopilot/tasks/mics_task.py`
- **Commit:** 3657a64

---

## Post-Deploy Bug Fix (discovered during human testing, 2026-05-04)

**Bug:** `_resolve_flags()` TYPE_MAP referenced `Tracker.Counter_Tracker`, `Tracker.Boolean_Tracker`, `Tracker.Trial_Tracker` — but `mics_task.py` imports `Tracker` as the **class** (`from autopilot.utils.Tracker import Tracker`), not the module. Those subclasses are module-level definitions in `Tracker.py`, not class attributes, so the reference raised `AttributeError: type object 'Tracker' has no attribute 'Counter_Tracker'` on the first run.

Note: `elastic_test.py` uses `from autopilot.utils import Tracker` (imports the **module**), so `Tracker.Counter_Tracker` works there — the bug was specific to `mics_task.py`'s import style.

**Fix:** Updated `mics_task.py` import to `from autopilot.utils.Tracker import Tracker, Counter_Tracker, Boolean_Tracker, Trial_Tracker` and updated TYPE_MAP to reference the classes directly (no `Tracker.` prefix).

- **File:** `~/pi-mirror/autopilot/autopilot/tasks/mics_task.py`
- **Deployed:** rsync + md5 verified (`37d401bba8a28af84968bb50ed7aa992`)

---

## Self-Check: PASSED

- [x] `orchestrator/orchestrator/orchestrator_station.py` — modified, committed cfb267b
- [x] `~/pi-mirror/autopilot/autopilot/tasks/mics_task.py` — modified, committed 3657a64, deployed to Pi; post-deploy import fix deployed (md5: 37d401bba8a28af84968bb50ed7aa992)
- [x] MD5 sums match between local mirror and Pi
- [x] Both files pass `python3 -m py_compile` syntax check
- [x] Human-verified: backend-authored toolkit with flag runs successfully on Pi
