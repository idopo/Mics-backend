---
phase: 11
plan: 3
subsystem: toolkit-dispatch
tags: [dispatch-spec, backend-authored, hardware-injection, pi-mics_task]
dependency_graph:
  requires: [Phase 11-02]
  provides: [dynamic HARDWARE/FLAGS/PARAMS injection for backend-authored toolkits]
  affects: [orchestrator/orchestrator_station.py, api/routers/toolkit_dispatch.py, pi-mirror/mics_task.py]
tech_stack:
  added: []
  patterns: [three-query chain (module→lib→version), instance-attr shadowing, non-fatal injection]
key_files:
  created: []
  modified:
    - api/routers/toolkit_dispatch.py
    - orchestrator/orchestrator/mics/mics_api_client.py
    - orchestrator/orchestrator/orchestrator_station.py
    - ~/pi-mirror/autopilot/autopilot/tasks/mics_task.py
decisions:
  - task_type left to dispatch-class override — _inject_backend_toolkit_spec does not set task_type
  - injection call placed inside if next_toolkit_id block in _advance_run_step (shares non-fatal exception handler)
  - pilot_hardware_config table name is singular (plan had plural — corrected)
metrics:
  duration_seconds: 378
  completed_date: "2026-05-04"
  tasks_completed: 4
  files_modified: 4
---

# Phase 11 Plan 3: Dynamic HARDWARE Dispatch (Backend-Authored Instantiation) Summary

**One-liner:** Backend-authored toolkits now inject HARDWARE dict (with source code), prefs pin config, FLAGS, and PARAMS into the START payload so the Pi instantiates task hardware without any Pi-side source file.

## Tasks Completed

| Task | Name | Commit | Files |
|------|------|--------|-------|
| 1 | GET /api/toolkits/{id}/dispatch-spec endpoint | 74e3252 | api/routers/toolkit_dispatch.py |
| 2 | MicsApiClient.get_toolkit_dispatch_spec | 07e0981 | orchestrator/orchestrator/mics/mics_api_client.py |
| 3 | _inject_backend_toolkit_spec helper + wiring | cb263ab | orchestrator/orchestrator/orchestrator_station.py |
| 4 | Pi mics_task injection block + helper methods | (pi-mirror) | ~/pi-mirror/autopilot/autopilot/tasks/mics_task.py |

## What Was Built

### API: `GET /api/toolkits/{id}/dispatch-spec?pilot_id={id}`

New endpoint in `api/routers/toolkit_dispatch.py`. For each hardware module in the toolkit:
1. Fetches HardwareModule by ID
2. Fetches HardwareLib by `module.hardware_lib_id` (two explicit queries — no ORM FK relationship)
3. Fetches HardwareLibVersion by `lib.active_version_id`
4. Fetches per-pilot pin config from `pilot_hardware_config` (singular — plan had wrong name)

Returns: `{ hardware, prefs_hardware, flags, params_schema, is_backend_authored }`

### Orchestrator: `_inject_backend_toolkit_spec()`

New helper in `orchestrator_station.py`. Non-fatal — logs and returns on any API error. Called:
- In `start_run()` after the dispatch-class override block, using `run_meta["pilot_id"]`
- In `_advance_run_step()` inside the `if next_toolkit_id` block, using `run["pilot_id"]`

Intentionally does NOT set `task_type` — the dispatch-class override (Phase 11-02) owns that exclusively.

### Pi: `mics_task.__init__` injection block

Added between `super().__init__()` and `self.init_hardware()`. Checks for `HARDWARE`, `FLAGS`, `PARAMS`, `PREFS_HARDWARE` in kwargs (sent by orchestrator in START payload). Sets instance attributes before `init_hardware()` runs — Python instance attrs shadow the class-level attrs inherited from subclasses like `learning_cage`.

Two helper methods added:
- `_resolve_hardware_classes(hardware_dict)` — execs `source_code` strings to get live classes
- `_merge_prefs_hardware(prefs_hw)` — merges backend pin config into `autopilot.prefs.HARDWARE`

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Fixed `self.session` reference in `get_toolkit_dispatch_class`**
- **Found during:** Task 2
- **Issue:** `get_toolkit_dispatch_class` in mics_api_client.py used `self.session.get()` but the class uses bare `requests.get()` with `self.headers` — `self.session` doesn't exist
- **Fix:** Changed to use `self._get()` helper, consistent with all other methods
- **Files modified:** orchestrator/orchestrator/mics/mics_api_client.py
- **Commit:** 07e0981

**2. [Rule 1 - Bug] Corrected `pilot_hardware_configs` table name to singular**
- **Found during:** Task 1
- **Issue:** Plan specified `pilot_hardware_configs` (plural) but actual table is `pilot_hardware_config` (singular, verified via `PilotHardwareConfig.__tablename__`)
- **Fix:** Used correct singular name in SQL query
- **Files modified:** api/routers/toolkit_dispatch.py
- **Commit:** 74e3252

## Verification

- `GET /api/toolkits/1/dispatch-spec?pilot_id=1` returns HTTP 200 with correct shape
- `GET /api/toolkits/1/dispatch-class` still returns HTTP 200 (regression check passed)
- Pi `mics_task.py` passes `python3 -m py_compile` syntax check
- Pi changes written to `~/pi-mirror/autopilot/autopilot/tasks/mics_task.py` (outside mics-backend git repo)

## Deploy Command (user must run)

To deploy Pi changes:
```bash
rsync -av -e "ssh -i ~/.ssh/pi_mics" \
  ~/pi-mirror/autopilot/autopilot/tasks/mics_task.py \
  pi@132.77.72.28:~/Apps/mice_interactive_home_cage/autopilot/autopilot/tasks/mics_task.py
```

## Manual Integration Test (after deploy)

Create a backend-authored toolkit with `class_name = "elastic_test"`, attach HW modules with source code, configure pin config for the pilot, then start a run. Confirm:
- Orchestrator logs show `Injected backend toolkit spec for toolkit ...`
- Pi `init_hardware()` uses injected HARDWARE dict (not `learning_cage.HARDWARE`)
- FLAGS and PARAMS are overridden correctly at task start

## Self-Check: PASSED

- api/routers/toolkit_dispatch.py: modified (dispatch-spec endpoint added)
- orchestrator/orchestrator/mics/mics_api_client.py: modified (get_toolkit_dispatch_spec added, bug fixed)
- orchestrator/orchestrator/orchestrator_station.py: modified (_inject_backend_toolkit_spec + wiring)
- ~/pi-mirror/autopilot/autopilot/tasks/mics_task.py: modified (syntax OK)
- Commits 74e3252, 07e0981, cb263ab verified in git log
