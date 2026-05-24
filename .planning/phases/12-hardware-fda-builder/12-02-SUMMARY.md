---
phase: 12
plan: "02"
subsystem: backend
tags: [validation, impact-detection, hardware-libs, toolkits, task-definitions]
dependency_graph:
  requires: [Phase 10, Phase 11, Phase 12 Plan 01]
  provides: [validation_status on task_definitions, impact scan on lib/toolkit PUT]
  affects: [api/routers/hardware_libs.py, api/routers/toolkits.py, api/fda_utils.py]
tech_stack:
  added: []
  patterns:
    - AST diff for removed method detection
    - Pin-aware impact scan (pinned task defs insulated from active-version changes)
    - Re-validation on every task definition save
key_files:
  created:
    - api/fda_utils.py
  modified:
    - api/routers/hardware_libs.py
    - api/routers/toolkits.py
decisions:
  - scan_fda_for_refs placed in api/fda_utils.py for shared use by both hardware_libs and toolkits routers
  - validation_message passed as None in SQL params; SQLAlchemy text() handles None as SQL NULL
  - Classic toolkits (no hardware_module_ids) skip hardware ref validation in _validate_task_definition
  - _validate_task_definition always runs on PUT even when only display_name changes (consistent, cheap)
metrics:
  duration: "6m"
  completed_date: "2026-05-24"
  tasks_completed: 5
  files_modified: 3
---

# Phase 12 Plan 02: Impact Detection + Broken Definition Backend Summary

Backend detects when hardware lib or toolkit changes break existing task definitions and flags them; task definition save re-validates automatically.

## What Was Built

**api/fda_utils.py (new)**
`scan_fda_for_refs(fda_json)` recursively walks all `states.entry_actions` including `type:if` branches, returning a flat list of `{state_name, action_type, ref, method}` entries for hardware/flag/timer/method actions.

**api/routers/hardware_libs.py (Step 3)**
`PUT /hardware-libs/{id}` now:
1. Captures old AST metadata before creating new version
2. Calls `_diff_removed_methods()` to find methods present in old AST but absent in new
3. Calls `_flag_broken_task_defs()` to scan linked task definitions
   - Skips any definition pinned to a specific version (insulated from active-version changes)
   - Scans `fda_json` via `scan_fda_for_refs()` for `type:hardware` refs matching removed methods
   - Flags matching definitions with `validation_status = 'broken'`
4. Response includes `impact.removed_methods` and `impact.affected_definition_ids`

**api/routers/toolkits.py (Steps 4 & 5)**

Step 4 — `PATCH /toolkits/{id}` now:
1. Captures old `hardware_module_ids` and `flags` before updates
2. After commit, computes removed flag names and removed module names (via DB lookup for module IDs → names)
3. Calls `_flag_broken_defs_for_toolkit()` to flag definitions that reference removed flags/modules
4. Response includes `impact.removed_flags`, `impact.removed_modules`, `impact.affected_definition_ids`

Step 5 — `PUT /task-definitions/{id}` now:
1. After applying payload updates, calls `_validate_task_definition()` with effective FDA + toolkit
2. `_validate_task_definition()` checks:
   - Flag refs: flag name must exist in toolkit's current flags
   - Hardware refs: module name must be in toolkit's hardware_module_ids; method must exist in lib's AST
3. Sets `validation_status = 'ok'` (all refs valid) or `'broken'` (first broken ref found)
4. Response includes `validation_status`

## Steps Already Complete Before This Plan

- Step 1: `validation_status` + `validation_message` columns added to `TaskDefinition` model; `run_task_definition_validation_migrations()` in `db.py`; called in `api/main.py` startup
- `GET /api/task-definitions` and `GET /api/task-definitions/{id}` already included `validation_status` + `validation_message` in responses

## Deviations from Plan

None - plan executed exactly as written.

**Note:** `hardware_libs.py` and `toolkits.py` were already over the 500-line limit before this plan's changes (690 and 691 lines respectively). Adding impact scan logic pushes them to 794 and 861 lines. Refactoring these files to meet the size limit was deferred as it constitutes an architectural decision out of scope for this plan.

## Self-Check

Verified:
- `GET http://localhost:8000/api/task-definitions/180` returns `validation_status: "ok"`, `validation_message: null`
- `GET http://localhost:8000/api/task-definitions` returns 138 definitions all with `validation_status` field
- `PUT /api/task-definitions/180` with `{"display_name": "mics_task"}` returns `{"status": "ok", "id": 180, "validation_status": "ok"}`
- `GET http://localhost:8000/api/hardware-libs` returns 5 libs normally
- No runtime errors in Docker logs
- All 3 Python files parse without syntax errors
