---
phase: 04-protocol-integration
plan: 01
subsystem: database, api
tags: [postgres, sqlmodel, sqlalchemy, fastapi, migration]

# Dependency graph
requires: []
provides:
  - "protocol_step_templates.task_definition_id nullable INTEGER column with FK to task_definitions.id"
  - "ProtocolStepTemplate ORM model with task_definition_id field"
  - "ProtocolStepTemplateCreate accepts task_definition_id"
  - "GET /protocols and GET /protocols/{id} return task_definition_id per step"
  - "POST /protocols saves task_definition_id per step"
affects:
  - 04-02-frontend-task-definition-selector
  - 04-03-orchestrator-fda-injection

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "bare Optional[int] (no SQLModel FK) for cross-ORM FK references (task_definitions is SQLAlchemy-owned; SQLModel cannot resolve it at model definition time)"

key-files:
  created: []
  modified:
    - api/db.py
    - api/models.py
    - api/main.py

key-decisions:
  - "task_definition_id uses bare Optional[int] without SQLModel foreign_key= because task_definitions table is owned by SQLAlchemy Base; SQLModel FK resolution fails at startup. Migration function enforces the DB-level constraint."

patterns-established:
  - "Cross-ORM FK pattern: SQLModel field uses bare Optional[int]; DB constraint added via migration function; same pattern as Subject.lead_researcher_id"

requirements-completed: [PROTO-01, PROTO-03]

# Metrics
duration: 15min
completed: 2026-03-24
---

# Phase 04 Plan 01: Protocol-TaskDefinition FK Link Summary

**Nullable task_definition_id INTEGER FK added to protocol_step_templates via safe migration, flowing through protocol create and read API endpoints**

## Performance

- **Duration:** 15 min
- **Started:** 2026-03-24T07:50:00Z
- **Completed:** 2026-03-24T08:05:00Z
- **Tasks:** 2
- **Files modified:** 3

## Accomplishments
- `run_protocol_migrations()` adds `task_definition_id INTEGER REFERENCES task_definitions(id) ON DELETE SET NULL` with `IF NOT EXISTS` safety
- `ProtocolStepTemplate` and `ProtocolStepTemplateCreate` both carry the new field
- `create_protocol()` saves `task_definition_id` from the request payload
- All protocol read endpoints (GET /protocols, GET /protocols/{id}) return `task_definition_id` per step

## Task Commits

Each task was committed atomically:

1. **Task 1: DB migration + model extension** - `e3c9ef3` (feat)
2. **Task 2: Wire task_definition_id through create and read API paths** - `1f5bdb7` (feat)

## Files Created/Modified
- `api/db.py` - Added `run_protocol_migrations()` function
- `api/models.py` - Added `task_definition_id: Optional[int] = None` to `ProtocolStepTemplate` and `ProtocolStepTemplateCreate`
- `api/main.py` - Import and call `run_protocol_migrations(engine)` at startup; pass `task_definition_id` in `create_protocol()`

## Decisions Made
- Used bare `Optional[int]` without `foreign_key=` in SQLModel for `task_definition_id`. The `task_definitions` table is SQLAlchemy-owned; SQLModel cannot resolve cross-ORM FK references at model definition time and raises `NoReferencedTableError`. The DB-level FK constraint is enforced by the migration function. Same pattern already used for `Subject.lead_researcher_id`.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Removed SQLModel foreign_key= on task_definition_id**
- **Found during:** Task 2 (API verification)
- **Issue:** Plan specified `Field(default=None, foreign_key="task_definitions.id")` but this caused `sqlalchemy.exc.NoReferencedTableError` at API startup. The `task_definitions` table is registered under the SQLAlchemy Base, not the SQLModel metadata, so SQLModel cannot resolve it.
- **Fix:** Changed to `Optional[int] = None` (bare field, no FK kwarg). The DB-level FK constraint is still enforced by `run_protocol_migrations()`.
- **Files modified:** `api/models.py`
- **Verification:** API starts cleanly; `POST /protocols` and `GET /protocols/{id}` return `task_definition_id` field correctly.
- **Committed in:** `1f5bdb7` (Task 2 commit)

---

**Total deviations:** 1 auto-fixed (1 bug)
**Impact on plan:** Fix required for correct operation. DB FK constraint preserved via migration. No scope change.

## Issues Encountered
- Cross-ORM FK declaration incompatibility. See Deviations section.

## Next Phase Readiness
- Column exists in DB, flows through API — 04-02 (frontend step-to-definition selector) and 04-03 (orchestrator FDA injection) can proceed.
- Existing protocols unaffected (task_definition_id is NULL for all legacy rows).

---
*Phase: 04-protocol-integration*
*Completed: 2026-03-24*
