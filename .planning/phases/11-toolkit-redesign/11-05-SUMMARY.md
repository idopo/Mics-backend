---
phase: 11
plan: 05
subsystem: toolkit-ui
tags: [toolkit, backend-authored, patch, edit-modal, react, fastapi]
dependency_graph:
  requires: [Phase 11-01]
  provides: [PATCH /api/toolkits/{id}, EditModal component]
  affects: [toolkits page, toolkit dispatch spec]
tech_stack:
  added: []
  patterns: [inline PATCH endpoint with raw SQL for jsonb column, modal pre-population from Record<string,unknown>]
key_files:
  created:
    - web_ui/react-src/src/pages/toolkits/EditModal.tsx
  modified:
    - api/models.py
    - api/routers/toolkits.py
    - web_ui/react-src/src/api/toolkits.ts
    - web_ui/react-src/src/types/index.ts
    - web_ui/react-src/src/pages/toolkits/Toolkits.tsx
decisions:
  - EditModal extracted to separate file to keep Toolkits.tsx under 500-line production limit
  - PATCH endpoint returns 400 (not 403) for legacy toolkits to match existing error convention in codebase
  - hw_hash recomputed with sha256 (matching POST endpoint) not md5 (plan pseudocode used md5)
metrics:
  duration_seconds: 287
  completed_date: "2026-05-04"
  tasks_completed: 4
  files_changed: 5
---

# Phase 11 Plan 05: Toolkit Edit — HW Modules, Flags, Params Summary

**One-liner:** PATCH endpoint + Edit modal to update hardware_module_ids, flags, and params_schema on backend-authored toolkits without delete/recreate.

## Tasks Completed

| Task | Description | Commit |
|------|-------------|--------|
| 1 | Backend — PATCH /api/toolkits/{id} endpoint + BackendToolkitPatch model | 3da9d32 |
| 2 | UI — BackendToolkitPatchPayload type + patchToolkit() fetch helper | 5a84cab |
| 3+4 | UI — Edit button on BackendToolkitCard + EditModal component | 21610f5 |

## What Was Built

### Backend (Step 1)

`BackendToolkitPatch` Pydantic model added to `api/models.py`:
- `hardware_module_ids: Optional[List[int]]`
- `flags: Optional[List[FlagDefinition]]`
- `params_schema: Optional[List[ParamDefinition]]`

`PATCH /api/toolkits/{toolkit_id}` endpoint in `api/routers/toolkits.py`:
- 404 if toolkit not found; 400 if not backend-authored
- If `hardware_module_ids` provided: validates all IDs exist, recomputes `hw_hash` via sha256, updates via raw SQL (jsonb column)
- If `flags` provided: converts list → dict format and updates ORM field
- If `params_schema` provided: converts list → dict format and updates ORM field
- Returns updated toolkit via `_build_toolkit_row()`

### Frontend (Steps 2-4)

`BackendToolkitPatchPayload` interface added to `types/index.ts`.
`patchToolkit(id, payload)` function added to `api/toolkits.ts`.

`EditModal` (new file `EditModal.tsx`):
- Pre-populates from toolkit's current `hardware_module_ids`, `flags`, `params_schema`
- Three stacked sections: HW Modules (checkboxes), Flags (editable grid), Params (editable grid)
- Saves via `patchToolkit()` → invalidates `['toolkits']` cache → closes
- Inline error display if PATCH fails

`BackendToolkitCard` updated with "Edit" button that opens `EditModal`.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 2 - File size] Extracted EditModal to separate file**
- **Found during:** Step 4
- **Issue:** Adding EditModal inline would push Toolkits.tsx to 566 lines, exceeding the 500-line hard limit
- **Fix:** Extracted `EditModal` to `web_ui/react-src/src/pages/toolkits/EditModal.tsx` (122 lines)
- **Files modified:** EditModal.tsx (created), Toolkits.tsx (import added)

**2. [Rule 1 - Bug] Used sha256 instead of plan's md5 for hw_hash**
- **Found during:** Step 1
- **Issue:** Plan pseudocode used `hashlib.md5` but the existing `create_backend_toolkit` endpoint uses `sha256` — using md5 would create an inconsistency
- **Fix:** Used sha256 to match existing POST behavior

## Self-Check: PASSED

All files created/modified exist on disk. All commits (3da9d32, 5a84cab, 21610f5) verified in git log. Key symbols (patch_backend_toolkit, BackendToolkitPatch, patchToolkit, BackendToolkitPatchPayload) verified in source files. Build succeeded (npm run build exit 0).
