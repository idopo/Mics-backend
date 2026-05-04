---
phase: "11"
plan: "02"
subsystem: toolkit-dispatch
tags: [backend-authored, dispatch-class, handshake, condition-builder, orchestrator]
dependency_graph:
  requires: [Phase 11-01]
  provides: [class_name in available_locked_states, dispatch-class endpoint, task_type override in orchestrator, hw module names in condition builder]
  affects: [api, orchestrator, web_ui]
tech_stack:
  added: []
  patterns: [router-per-domain split when file exceeds 500 lines, toolkit_id resolution before START payload]
key_files:
  created:
    - api/routers/toolkit_dispatch.py
  modified:
    - api/db.py
    - api/routers/locked_states.py
    - api/main.py
    - orchestrator/orchestrator/mics/mics_api_client.py
    - orchestrator/orchestrator/orchestrator_station.py
    - web_ui/react-src/src/components/ConditionBuilder.tsx
    - web_ui/react-src/src/pages/task-editor/TaskEditor.tsx
decisions:
  - class_name stored in available_locked_states; new format carries it per-entry, legacy format derives it from task_type
  - Dispatch endpoint in separate router (toolkits.py already >500 lines)
  - task_type override placed after _build_*_task to respect its re-assertion at lines 686/745
  - hwModuleNames fetched in TaskEditor via Promise.all on individual module IDs (toolkit stores only ids, not names)
metrics:
  duration_seconds: 282
  completed_date: "2026-05-04"
  tasks_completed: 10
  files_modified: 7
  files_created: 1
---

# Phase 11 Plan 02: Pi Dispatch Class Fix + Condition Builder HW Modules Summary

**One-liner:** class_name stored per locked state from HANDSHAKE; orchestrator overrides task_type for backend-authored toolkits; condition builder now shows hw module names alongside semantic_hardware keys.

## Tasks Completed

| Task | Description | Commit |
|------|-------------|--------|
| Steps 1-2 | DB migration: class_name column + LockedStateUpsertPayload update | b0787fe |
| Steps 3-4 | HANDSHAKE handler passes class_name; MicsApiClient signature updated | b42ace1 |
| Steps 5-6 | New toolkit_dispatch router + register in main.py | bbab917 |
| Step 7 | get_toolkit_dispatch_class added to MicsApiClient | 64dbafb |
| Step 8 | task_type override in start_run() + _advance_run_step() | d00dacd |
| Steps 9-10 | ConditionBuilder hwModuleNames prop; TaskEditor fetches + passes | cd67528 |

## What Was Built

**Part A — Pi Dispatch Class Fix:**
- `ALTER TABLE available_locked_states ADD COLUMN IF NOT EXISTS class_name VARCHAR` in `run_toolkit_backend_authored_migrations()`
- `LockedStateUpsertPayload` gains `class_name: str | None = None`; UPDATE/INSERT SQL binds `:cn`
- HANDSHAKE handler: new format reads `entry.get("class_name")`; legacy format uses `task_type` as class_name
- `mics_api_client.upsert_locked_states()` extended to accept and forward `class_name`
- New file `api/routers/toolkit_dispatch.py`: `GET /api/toolkits/{id}/dispatch-class` — looks up `locked_state_source` from `task_toolkits`, then fetches `class_name` from `available_locked_states`; falls back to `"mics_task"`
- `api/main.py`: `app.include_router(toolkit_dispatch_router, prefix="/api")`
- `mics_api_client.get_toolkit_dispatch_class(toolkit_id)` added
- `orchestrator_station.start_run()`: after toolkit_id resolution block, calls dispatch-class and overrides `task["task_type"]` if `is_backend_authored`
- `orchestrator_station._advance_run_step()`: same pattern for next step's task_definition_id

**Part B — Condition Builder HW Modules:**
- `ConditionBuilder` component: `hwModuleNames?: string[]` prop; `hwOpts` now merges both `semantic_hardware` keys and module names
- `OperandEditor` likewise receives `hwModuleNames` and passes it to the merged array
- `TaskEditor`: imports `getHardwareModule`; `useQuery` fetches each hw module by id when `toolkit.hardware_module_ids.length > 0`; `hwModuleNames` derived from results; passed as prop to `ConditionBuilder`

## Deviations from Plan

None — plan executed exactly as written.

## Verification

- TypeScript compilation: clean (`npx tsc --noEmit` — 0 errors)
- React build: clean (`npm run build` — built in 1.66s)
- Runtime verification (Docker build + manual test) delegated to user per plan's manual UI test instruction

## Self-Check: PASSED

- api/routers/toolkit_dispatch.py: FOUND
- api/db.py modified with class_name migration: FOUND
- api/main.py includes toolkit_dispatch_router: FOUND
- Commit b0787fe (steps 1-2): FOUND
- Commit b42ace1 (steps 3-4): FOUND
- Commit bbab917 (steps 5-6): FOUND
- Commit 64dbafb (step 7): FOUND
- Commit d00dacd (step 8): FOUND
- Commit cd67528 (steps 9-10): FOUND
