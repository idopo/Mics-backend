---
phase: "11"
plan: "01"
subsystem: toolkit-redesign
tags: [toolkits, backend-authored, locked-states, hw-lib-pins, orchestrator, react]
dependency_graph:
  requires: [Phase 10 (hardware_modules table)]
  provides: [available_locked_states table, POST /api/toolkits backend-authored, locked-states API, hw lib pin UI]
  affects: [Toolkits UI, TaskEditor UI, HANDSHAKE handler, MicsApiClient]
tech_stack:
  added: [available_locked_states PostgreSQL table, api/routers/locked_states.py]
  patterns: [backend-authored toolkit creation, HANDSHAKE dual-format (new + legacy), hw lib pin version management]
key_files:
  created:
    - api/routers/locked_states.py
    - web_ui/react-src/src/pages/task-editor/HwLibVersionModal.tsx
  modified:
    - api/models.py
    - api/db.py
    - api/main.py
    - api/routers/toolkits.py
    - orchestrator/orchestrator/mics/mics_api_client.py
    - orchestrator/orchestrator/orchestrator_station.py
    - web_ui/react-src/src/pages/toolkits/Toolkits.tsx
    - web_ui/react-src/src/pages/task-editor/TaskEditor.tsx
    - web_ui/react-src/src/api/toolkits.ts
    - web_ui/react-src/src/api/hardware_libs.ts
    - web_ui/react-src/src/types/index.ts
decisions:
  - Legacy HANDSHAKE: reconstruct filename as f"{task_type}.py" and mark is_legacy_filename=True; detect by uppercase chars in stem
  - HwLibVersionModal: scanFdaForLibRefs returns all hw/timer refs (not filtered by lib) since module→lib resolution would require extra fetches
  - toolkit.is_backend_authored discriminates sections in Toolkits UI (not separate endpoints)
metrics:
  duration: "6m 30s"
  completed: "2026-05-03"
  tasks_completed: 9
  files_changed: 11
---

# Phase 11 Plan 1: Toolkit Redesign (Backend-Authored) Summary

Backend-authored toolkits with locked-state selection from HANDSHAKE-announced Pi task files, 5-step creation UI, and hw lib version pinning panel in TaskEditor.

## Completed Tasks

| # | Task | Commit | Key Files |
|---|------|--------|-----------|
| 1 | _put() helper + upsert_locked_states() in MicsApiClient | c5da150 | mics_api_client.py |
| 2-4 | task_toolkits columns + AvailableLockedState model + migration | 9f8921d | models.py, db.py, main.py |
| 5 | HANDSHAKE upserts available_locked_states (new + legacy) | 878db8a | orchestrator_station.py |
| 6 | locked-states router (GET/PUT) | ea3e26f | api/routers/locked_states.py |
| 7 | POST /api/toolkits backend-authored creation | 77f9443 | toolkits.py, models.py |
| 8 | Toolkits UI redesign + 5-step creation modal | 7b163c0 | Toolkits.tsx, toolkits.ts, types/index.ts |
| 9 | TaskEditor hw lib chips + HwLibVersionModal | d166a65 | TaskEditor.tsx, HwLibVersionModal.tsx, hardware_libs.ts |

## What Was Built

**Backend:**
- `AvailableLockedState` table (pilot_id, task_filename, state_names, is_legacy_filename)
- `run_toolkit_backend_authored_migrations()`: adds hardware_module_ids/locked_state_source/is_backend_authored columns to task_toolkits + creates available_locked_states table
- `GET /api/locked-states` — all entries grouped by task_filename with pilot list
- `PUT /api/locked-states/{pilot_id}/{task_filename}` — upsert (orchestrator internal, called from HANDSHAKE)
- `POST /api/toolkits` — backend-authored toolkit creation with validation against available_locked_states and hardware_modules
- HANDSHAKE now populates available_locked_states: new format (task_files array) and legacy format (STAGE_NAMES + task_type → reconstructed filename)
- `_put()` helper + `upsert_locked_states()` in MicsApiClient

**Frontend:**
- Toolkits UI: two sections — "Backend-Authored" (cards) + "Legacy" (compact rows with "legacy" badge)
- "+ New Toolkit" button opens 5-step modal: Name+file → Select states → HW modules → Flags → Params
- Legacy filename warning shown when source file was reconstructed from class name
- TaskEditor header: hw lib pin chips per toolkit-linked lib (filename + version + state badge)
- Click chip → HwLibVersionModal: version dropdown, AST diff warnings panel, Set Pin / Revert to active

## Deviations from Plan

### Auto-fixed Issues

None.

### Deferred Items

**1. [File size] api/routers/toolkits.py at 595 lines (hard limit: 500)**
- Found during: Step 7
- Issue: Adding POST /api/toolkits endpoint pushed file from 514 to 595 lines
- The plan explicitly directs this endpoint to go in toolkits.py; splitting further would require a separate backend-toolkit router
- Deferred to next refactor opportunity; document in deferred-items

**2. [File size] api/models.py at 803 lines (hard limit: 500)**
- Pre-existing issue; adding new models grew it further
- Needs split into separate modules (orm_models.py, pydantic_schemas.py, etc.)
- Deferred

**3. [Design] HwLibVersionModal toolkit parameter removed**
- The toolkit prop was declared but unused (can't resolve module→lib filename mapping without extra fetches)
- Removed from function signature to fix TypeScript unused-variable error
- FDA scan returns all hw/timer refs rather than filtering by specific lib (conservative: shows more potential breakage, not less)

## Self-Check: PASSED

All 7 task commits verified present. All key files (locked_states.py, HwLibVersionModal.tsx, SUMMARY.md) verified on disk. TypeScript compilation clean. React build succeeded.
