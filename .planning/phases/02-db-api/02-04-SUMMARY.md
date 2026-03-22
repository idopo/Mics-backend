---
phase: 02-db-api
plan: "04"
subsystem: orchestrator-push
tags: [fda, zmq, hot-reload, push, validation]
dependency_graph:
  requires: [02-02, 02-03]
  provides: [push-fda-endpoint, state-machine-injection, fda-validation]
  affects: [api/routers/toolkits.py, orchestrator/orchestrator/api.py, orchestrator/orchestrator/orchestrator_station.py, orchestrator/orchestrator/mics/mics_api_client.py]
tech_stack:
  added: []
  patterns: [urllib-stdlib-for-internal-http, non-fatal-injection, tdd-unit-tests]
key_files:
  created:
    - orchestrator/tests/__init__.py
    - orchestrator/tests/test_push_fda.py
  modified:
    - api/routers/toolkits.py
    - orchestrator/orchestrator/api.py
    - orchestrator/orchestrator/orchestrator_station.py
    - orchestrator/orchestrator/mics/mics_api_client.py
    - api/tests/test_toolkits_router.py
decisions:
  - Used stdlib urllib.request instead of requests in api container (requests not in api/requirements.txt; avoids new dependency)
  - resolve_pilot_key raises KeyError (not returns None) — catch KeyError, re-raise ValueError in push_hot_reload
  - state_machine injection is non-fatal — log exception and continue if get_task_definition() fails
  - Validation skipped (not errored) when toolkit_name not in DB — Pi may not have connected yet
metrics:
  duration_seconds: 372
  completed_date: "2026-03-22"
  tasks_completed: 3
  files_modified: 7
---

# Phase 02 Plan 04: Push-to-Pilot Flow and state_machine Injection Summary

**One-liner:** UPDATE_FDA ZMQ hot-reload delivery via orchestrator REST bridge, with fda_json state/hardware validation and non-fatal state_machine injection at session start.

## What Was Built

This plan completes the end-to-end FDA delivery loop:

1. **POST /task-definitions/{id}/push** (api/routers/toolkits.py) — validates fda_json state names and hardware refs against the toolkit, then forwards to orchestrator via POST /push-fda
2. **POST /push-fda** (orchestrator/orchestrator/api.py) — receives pilot_name + fda_json and calls station.push_hot_reload()
3. **push_hot_reload()** (orchestrator/orchestrator/orchestrator_station.py) — resolves pilot ZMQ key, sends UPDATE_FDA message via gateway.send()
4. **get_task_definition()** (orchestrator/orchestrator/mics/mics_api_client.py) — fetches task definition from api by id; returns None on failure
5. **state_machine injection** in _build_first_step_task() and _build_step_task() — when step.params.task_definition_id is present, fetches fda_json and injects as task["state_machine"] in START payload

## Tasks Completed

| Task | Name | Commit | Key Files |
|------|------|--------|-----------|
| 0 | TDD RED: write failing tests | fdc1655 | orchestrator/tests/test_push_fda.py, api/tests/test_toolkits_router.py |
| 1 | push_hot_reload() + POST /push-fda | c241e4e | orchestrator/orchestrator/orchestrator_station.py, orchestrator/orchestrator/api.py |
| 2 | push endpoint + validation + state_machine injection | 8ee7ae6 | api/routers/toolkits.py, orchestrator/orchestrator/orchestrator_station.py, orchestrator/orchestrator/mics/mics_api_client.py |

## Verification Evidence

- `_validate_fda_against_toolkit()` unit tests: unknown state → `["Unknown state: 'badstate' not in toolkit states"]`; unknown hw ref → `["State 'iti': unknown hardware ref 'unknown_hw'"]`; valid fda → `[]`
- All 4 api/tests/test_toolkits_router.py tests pass (including test_push_endpoint_exists)
- push_hot_reload() unit tests pass in orchestrator container: gateway.send called with UPDATE_FDA; ValueError raised when pilot not in state
- POST /api/task-definitions/99999/push → `{"detail":"Task definition not found"}` (404)
- POST /api/task-definitions/100/push → 503 when orchestrator not reachable (expected; orchestrator DNS in same compose network)

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 - Blocking] stdlib urllib instead of requests**
- **Found during:** Task 2 — api container startup failed with `ModuleNotFoundError: No module named 'requests'`
- **Issue:** api/requirements.txt does not include requests; plan used requests for the orchestrator HTTP call
- **Fix:** Replaced with stdlib `urllib.request` and `urllib.error` — equivalent functionality, zero new dependencies
- **Files modified:** api/routers/toolkits.py
- **Commit:** 8ee7ae6

**2. [Rule 1 - Bug] resolve_pilot_key raises KeyError, not returns None**
- **Found during:** Task 1 — reading state.py: resolve_pilot_key raises KeyError on line 103, not returns None
- **Plan assumption:** "if it raises RuntimeError, catch it and re-raise as ValueError"
- **Fix:** Catch KeyError (not RuntimeError) and re-raise as ValueError in push_hot_reload()
- **Files modified:** orchestrator/orchestrator/orchestrator_station.py
- **Commit:** c241e4e

## Self-Check: PASSED

All 7 created/modified files found on disk. All 3 task commits exist in git history.
