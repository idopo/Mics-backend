---
phase: 12-hardware-fda-builder
plan: "05"
subsystem: api
tags: [fastapi, sqlalchemy, react, typescript, hardware-libs, version-pinning, validation]

requires:
  - phase: 12-hardware-fda-builder
    provides: hw lib versioning system, TaskDefinitionHwLibPin model, set/delete pin endpoints

provides:
  - Task defs auto-pinned to stable/active hw lib version at creation
  - _validate_task_definition reads pinned version AST when task_def_id provided
  - Pin set/delete immediately re-validates task def
  - HardwareLibDetail no longer shows Restore this version button

affects: [12-hardware-fda-builder, task-definitions, hw-lib-validation]

tech-stack:
  added: []
  patterns:
    - "_revalidate_task_def helper centralizes post-pin validation in hardware_libs router"
    - "Lazy import of _validate_task_definition avoids circular dependency between routers"

key-files:
  created: []
  modified:
    - api/routers/toolkits.py
    - api/routers/hardware_libs.py
    - web_ui/react-src/src/pages/hardware-libs/HardwareLibDetail.tsx

key-decisions:
  - "Lazy import `from routers.toolkits import _validate_task_definition` inside _revalidate_task_def to avoid circular import at module load time"
  - "Auto-pin uses stable_version_id falling back to active_version_id — stable is always preferred since it has passed testing"

patterns-established:
  - "Pin-aware validation: _validate_task_definition checks TaskDefinitionHwLibPin before falling back to active lib AST"

requirements-completed: []

duration: 8min
completed: 2026-05-24
---

# Phase 12, Plan 05: Hardware Lib Version Pinning Fixes Summary

**Three version-pinning bugs fixed: task defs auto-pin at creation, validation reads pinned AST, pin changes immediately re-validate; Restore button removed**

## Performance

- **Duration:** ~8 min
- **Started:** 2026-05-24T06:36:00Z
- **Completed:** 2026-05-24T06:44:32Z
- **Tasks:** 4 fixes (committed together as one atomic change)
- **Files modified:** 3

## Accomplishments
- Fix 1: New task definitions now auto-pin to stable (or active) version of each hw lib linked to the toolkit at creation time, so uploading a new lib version never silently moves existing task defs
- Fix 2: `_validate_task_definition` accepts an optional `task_def_id`; when provided, it reads `ast_metadata` from the pinned `HardwareLibVersion` row instead of the lib's active-version metadata
- Fix 3: `set_hw_lib_pin` and `delete_hw_lib_pin` both call `_revalidate_task_def` after committing the pin change, so validation_status updates immediately without a separate save
- Fix 4: "Restore this version" button removed from HardwareLibDetail — the button was conceptually wrong given the pin-at-creation model

## Task Commits

1. **All 4 fixes** - `d99954f` (fix)

**Plan metadata:** (this commit)

## Files Created/Modified
- `api/routers/toolkits.py` - Added HardwareLib/HardwareLibVersion/ToolkitHardwareLib/TaskDefinitionHwLibPin imports; auto-pin block in create_task_definition; updated _validate_task_definition signature + AST loading block; pass defn_id at call site in update_task_definition
- `api/routers/hardware_libs.py` - Added json/sa_text top-level imports; added _revalidate_task_def helper; called after set_hw_lib_pin and delete_hw_lib_pin commits
- `web_ui/react-src/src/pages/hardware-libs/HardwareLibDetail.tsx` - Removed rollback import, rollbackMutation, and Restore this version JSX button

## Decisions Made
- Lazy import `from routers.toolkits import _validate_task_definition` inside `_revalidate_task_def` body to avoid circular import between the two router modules at load time
- Auto-pin prefers `stable_version_id` over `active_version_id` — stable version has passed testing, so it's the right frozen baseline

## Deviations from Plan

None - plan executed exactly as written.

## Issues Encountered
None — all 4 fixes were straightforward; React build and Python AST parse both passed cleanly.

## User Setup Required
None - no external service configuration required.

## Next Phase Readiness
- Version pinning system is now correct end-to-end: create pins, validation respects pins, pin changes re-validate immediately
- Phase 12 verification can now be run against all five plans

---
*Phase: 12-hardware-fda-builder*
*Completed: 2026-05-24*
