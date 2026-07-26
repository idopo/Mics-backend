---
phase: 02-db-api
plan: "01"
subsystem: database
tags: [postgres, sqlalchemy, migrations, toolkit, fda]

# Dependency graph
requires: []
provides:
  - task_toolkits table with UniqueConstraint on (name, hw_hash)
  - toolkit_pilot_origins table with UniqueConstraint on (toolkit_id, pilot_id)
  - task_definitions.toolkit_name, .display_name, .fda_json columns
  - TaskToolkit, ToolkitPilotOrigin SQLAlchemy models in api/models.py
  - TaskToolkitRead, TaskDefinitionCreate, TaskDefinitionUpdate, TaskDefinitionRead Pydantic schemas
  - run_toolkit_migrations() idempotent migration function in api/db.py
affects: [02-02, 02-03, 02-04]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "IF NOT EXISTS column migration pattern extended to toolkit tables"
    - "UniqueConstraint via __table_args__ tuple on SQLAlchemy models"

key-files:
  created: []
  modified:
    - api/models.py
    - api/db.py
    - api/main.py

key-decisions:
  - "Toolkit schema stored in task_toolkits separate from task_definitions — allows multiple FDAs per toolkit"
  - "fda_json stored as JSONB in task_definitions (not task_toolkits) — each FDA variant is a definition row"
  - "Literal import added to models.py (was missing, used at line 575 but only worked via main.py import)"

patterns-established:
  - "New SQLAlchemy table migrations use run_*_migrations() pattern with IF NOT EXISTS — safe on existing production DB"
  - "New tables inheriting from Base are auto-created by Base.metadata.create_all(engine) in startup()"

requirements-completed: [DB-01, DB-02, VAR-01, VAR-02, VAR-03]

# Metrics
duration: 15min
completed: 2026-03-22
---

# Phase 02 Plan 01: DB Schema Foundation Summary

**SQLAlchemy models + idempotent Postgres migrations for task_toolkits and toolkit_pilot_origins tables, with toolkit_name/display_name/fda_json columns added to task_definitions**

## Performance

- **Duration:** ~15 min
- **Started:** 2026-03-22T15:45:00Z
- **Completed:** 2026-03-22T16:00:00Z
- **Tasks:** 2
- **Files modified:** 3

## Accomplishments
- Created `task_toolkits` table (12 columns, UniqueConstraint on name+hw_hash) via Base.metadata.create_all
- Created `toolkit_pilot_origins` table (FK to task_toolkits and pilots, UniqueConstraint on toolkit+pilot)
- Added `toolkit_name`, `display_name`, `fda_json` columns to `task_definitions` via IF NOT EXISTS migration
- All Pydantic schemas for toolkit CRUD added (TaskToolkitRead, TaskDefinitionCreate/Update/Read)
- API startup verified idempotent — restart produces no errors

## Task Commits

Each task was committed atomically:

1. **Task 1: Add TaskToolkit and ToolkitPilotOrigin SQLAlchemy models** - `ca8e6ab` (feat)
2. **Task 2: Add run_toolkit_migrations() and wire into startup** - `7264b97` (feat)

**Plan metadata:** (docs commit follows)

## Files Created/Modified
- `api/models.py` - Added TaskToolkit, ToolkitPilotOrigin, TaskToolkitRead, TaskDefinitionCreate/Update/Read; fixed Literal and UniqueConstraint imports
- `api/db.py` - Added run_toolkit_migrations() function
- `api/main.py` - Imported run_toolkit_migrations + new model classes; called run_toolkit_migrations(engine) in startup()

## Decisions Made
- `fda_json` column type is JSONB (in Postgres) not TEXT — enables efficient JSON querying in later phases
- Pydantic schemas added in this plan even though endpoints come in plan 03 — avoids import churn later
- Added missing `Literal` import to models.py (pre-existing oversight; `Literal` was used at line 575 but imported only in main.py, which worked accidentally)

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Added missing Literal import to models.py**
- **Found during:** Task 1 (model file review)
- **Issue:** `Literal` used in `StartOnPilotPayload` at line 575 of models.py but not imported in models.py — only worked because main.py imported `Literal` from typing first
- **Fix:** Added `Literal` to the `from typing import ...` line in models.py
- **Files modified:** api/models.py
- **Verification:** Import succeeds in isolated context
- **Committed in:** ca8e6ab (Task 1 commit)

---

**Total deviations:** 1 auto-fixed (Rule 1 - pre-existing missing import)
**Impact on plan:** Minor correctness fix. No scope creep.

## Issues Encountered
None beyond the Literal import fix above.

## User Setup Required
None - no external service configuration required. Migrations run automatically on API startup.

## Next Phase Readiness
- task_toolkits and toolkit_pilot_origins tables ready for HANDSHAKE processor (plan 02-02)
- task_definitions.toolkit_name/display_name/fda_json columns ready for FDA CRUD endpoints (plan 02-03)
- All Pydantic schemas ready for API endpoint scaffolding

---
*Phase: 02-db-api*
*Completed: 2026-03-22*
