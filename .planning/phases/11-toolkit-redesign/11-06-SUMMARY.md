---
phase: "11"
plan: "06"
subsystem: toolkit-creation
tags: [hardware-libs, versioning, modal, migration]
dependency_graph:
  requires: [Phase 11-01]
  provides: [toolkit-hw-lib-version-selection]
  affects: [task-editor-hw-lib-chips]
tech_stack:
  added: []
  patterns: [idempotent-column-migration, lazy-version-fetch, promise-all-post-creation]
key_files:
  created:
    - web_ui/react-src/src/pages/toolkits/CreationModal.tsx
  modified:
    - api/models.py
    - api/db.py
    - api/main.py
    - api/routers/hardware_libs.py
    - web_ui/react-src/src/api/hardware_libs.ts
    - web_ui/react-src/src/pages/toolkits/Toolkits.tsx
decisions:
  - CreationModal extracted to separate file to keep Toolkits.tsx under 300-line limit (was 520 after hw libs step added)
metrics:
  duration: "5m"
  completed: "2026-05-14"
  tasks_completed: 3
  files_modified: 7
---

# Phase 11 Plan 06: Hardware Library Selection During Toolkit Creation Summary

**One-liner:** Toolkit creation now supports linking hardware libs with per-lib version selection (defaulting to stable), stored as `default_version_id` on the link row and immediately available in TaskEditor chips.

## Tasks Completed

| # | Task | Commit | Files |
|---|------|--------|-------|
| 1 | Backend model + migration + startup | 0386bfc | api/models.py, api/db.py, api/main.py |
| 2 | Router: accept/store version_id; return in GET | 8e818ef | api/routers/hardware_libs.py |
| 3 | 6-step CreationModal with hw lib step + post-creation linking | 07a8ae5 | CreationModal.tsx, Toolkits.tsx, hardware_libs.ts |

## What Was Built

### Backend
- `ToolkitHardwareLib.default_version_id` — nullable FK column to `hardware_lib_versions.id`
- `run_toolkit_hw_lib_version_migration()` — idempotent `ADD COLUMN IF NOT EXISTS` migration called at API startup
- `LinkLibBody.version_id: Optional[int]` — new field; POST stores it; idempotent branch updates if provided
- `GET /api/toolkits/{id}/hardware-libs` — now includes `default_version_id` per entry (from link row, not lib row)

### Frontend
- `linkLib()` helper in `api/hardware_libs.ts` — `POST /api/toolkits/{id}/hardware-libs` with `{ hardware_lib_id, version_id }`
- `CreationModal.tsx` (extracted) — 6-step modal, step 3 = hardware library selection
  - Checkboxes per lib; checking a lib triggers lazy `listVersions()` fetch
  - Version dropdown pre-selects `stable_version_id ?? active_version_id ?? null`
  - Option labels show `★ stable` marker for stable version
  - Post-creation `Promise.all` links all checked libs before `onCreated()` fires
- Old steps renumbered: HW Modules 3→4, Flags 4→5, Params 5→6; header shows "Step N of 6"

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 2 - File size limit] Extracted CreationModal to separate file**
- **Found during:** Task 3 (after inserting hw libs step, Toolkits.tsx reached 520 lines)
- **Issue:** Adding step 3 JSX pushed Toolkits.tsx from 451 to 520 lines, breaching the 500-line hard limit
- **Fix:** Moved entire `CreationModal` function and `TRACKER_TYPES` constant to `CreationModal.tsx`, imported with named export; Toolkits.tsx now 259 lines, CreationModal.tsx 260 lines
- **Files modified:** CreationModal.tsx (created), Toolkits.tsx (import added, component removed)
- **Commit:** 07a8ae5

## Verification

- API migration confirmed: `toolkit_hardware_libs` columns = `['toolkit_id', 'hardware_lib_id', 'default_version_id']`
- React build: successful (`✓ built in 1.76s`, no TypeScript errors)
- Toolkits.tsx: 259 lines (under 300-line guideline)
- CreationModal.tsx: 260 lines (under 300-line guideline)

## Self-Check: PASSED
