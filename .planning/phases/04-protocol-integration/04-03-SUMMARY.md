---
phase: 04-protocol-integration
plan: 03
subsystem: api
tags: [orchestrator, fda-injection, toolkit, task-definitions, sqlalchemy, canonical]

# Dependency graph
requires:
  - phase: 04-protocol-integration plan 01
    provides: task_definition_id as top-level field on protocol steps; DB column added
  - phase: 04-protocol-integration plan 02
    provides: task_toolkits table, task_definitions CRUD, visual FDA editor

provides:
  - Orchestrator reads task_definition_id from step["task_definition_id"] (top-level) — FDA injection end-to-end wired
  - is_canonical column on task_toolkits with run_canonical_migrations()
  - needs_migration column on task_definitions with run_canonical_migrations()
  - PATCH /api/toolkits/{id}/set-canonical endpoint marks canonical variant, flags task definitions
  - GET /api/toolkits response includes is_canonical per toolkit
  - GET /api/task-definitions response includes needs_migration per definition

affects: [05-pi-editor, orchestrator, toolkits-page]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - run_canonical_migrations() follows existing IF NOT EXISTS pattern from run_toolkit_migrations()
    - set-canonical endpoint uses bulk ORM update + raw SQL for migrated columns (same pattern as other toolkit endpoints)

key-files:
  created: []
  modified:
    - orchestrator/orchestrator/orchestrator_station.py
    - api/models.py
    - api/db.py
    - api/routers/toolkits.py
    - api/main.py

key-decisions:
  - "set-canonical conservatively flags ALL task_definitions for toolkit name as needs_migration=True — no toolkit_id FK on task_definitions so we cannot distinguish which variant each definition was built for"
  - "is_canonical added as ORM Column on TaskToolkit model; needs_migration added as ORM Column on TaskDefinition model — both columns also added via run_canonical_migrations() for existing DBs"

patterns-established:
  - "Migrated Boolean columns use server_default='false' + default=False on ORM Column for both fresh and existing DB compat"

requirements-completed: [PROTO-02, PROTO-04, VAR-07]

# Metrics
duration: 5min
completed: 2026-03-24
---

# Phase 04 Plan 03: FDA Injection End-to-End + VAR-07 Canonical Variant Summary

**Orchestrator reads task_definition_id from top-level step field to inject fda_json into Pi START payload; PATCH /api/toolkits/{id}/set-canonical marks canonical toolkit variant and flags task definitions for migration review**

## Performance

- **Duration:** 5 min
- **Started:** 2026-03-24T07:59:12Z
- **Completed:** 2026-03-24T08:05:00Z
- **Tasks:** 2
- **Files modified:** 5

## Accomplishments
- Fixed FDA injection in orchestrator: `task_def_id = step.get("task_definition_id")` replaces the old `(step.get("params") or {}).get("task_definition_id")` that never worked (task_definition_id was never stored in params)
- Added `is_canonical` to task_toolkits and `needs_migration` to task_definitions via safe IF NOT EXISTS migration
- Implemented PATCH /api/toolkits/{id}/set-canonical that atomically marks one variant canonical and flags all task definitions for that toolkit name as needs_migration=True
- All toolkit list and detail responses now include `is_canonical`; task definitions list includes `needs_migration`

## Task Commits

1. **Task 1: Fix orchestrator — read task_definition_id from top-level step field** - `ce611ab` (fix)
2. **Task 2: VAR-07 — is_canonical migration + set-canonical endpoint + needs_migration flag** - `754082b` (feat)

**Plan metadata:** (docs commit below)

## Files Created/Modified
- `orchestrator/orchestrator/orchestrator_station.py` - Two lines fixed in _build_first_step_task and _build_step_task
- `api/models.py` - Added Boolean import; is_canonical to TaskToolkit; needs_migration to TaskDefinition
- `api/db.py` - Added run_canonical_migrations() function
- `api/routers/toolkits.py` - Added is_canonical to _build_toolkit_row; set-canonical endpoint; needs_migration in list_task_definitions
- `api/main.py` - Import and call run_canonical_migrations() at startup

## Decisions Made
- set-canonical marks ALL task definitions for the toolkit name as needs_migration=True (conservative). No toolkit_id FK exists on task_definitions (only toolkit_name TEXT), so we cannot determine which definitions were built against which variant — user must review.
- is_canonical and needs_migration are added both as ORM Column declarations (for fresh DB create_all) and via run_canonical_migrations() (for existing DBs), matching the established dual-path migration pattern.

## Deviations from Plan

None - plan executed exactly as written.

## Issues Encountered
None — both tasks straightforward; DB column additions were safe idempotent migrations.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness
- Phase 4 protocol integration is complete: task_definition_id flows from DB → API → orchestrator → Pi START payload
- VAR-07 canonical variant marking is implemented and verified
- Frontend (toolkits page from 03-03) can now show is_canonical badge and call set-canonical endpoint
- No blockers for Phase 5 (Pi Editor)

---
*Phase: 04-protocol-integration*
*Completed: 2026-03-24*
