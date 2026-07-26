---
phase: 02-db-api
plan: "03"
subsystem: api
tags: [fastapi, sqlalchemy, postgresql, rest, crud, toolkit, fda]

# Dependency graph
requires:
  - phase: 02-db-api/02-01
    provides: task_toolkits and task_definitions DB schema with migrations
  - phase: 02-db-api/02-02
    provides: HANDSHAKE upserts to task_toolkits table (required for toolkit data)
provides:
  - GET /api/toolkits — list all toolkits with pilot_origins and fda_count
  - GET /api/toolkits/by-name/{name} — all hw_hash variants for a toolkit class
  - GET /api/toolkits/{id} — full toolkit detail
  - GET /api/toolkits/{id}/diff/{other_id} — semantic hardware diff between variants
  - GET /api/task-definitions — list all task definitions
  - POST /api/task-definitions — create with display_name, toolkit_name, fda_json
  - GET /api/task-definitions/{id} — full detail with fda_json round-trip
  - PUT /api/task-definitions/{id} — update fda_json and/or display_name
  - DELETE /api/task-definitions/{id} — unconditional delete
affects: [phase-03-fda-editor, phase-04-protocol-steps]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - APIRouter module in api/routers/ package — all new endpoints go in separate router files
    - Raw SQL for IF-NOT-EXISTS migrated columns (display_name, toolkit_name, fda_json not in ORM class)
    - app.include_router(router, prefix="/api") registration in main.py

key-files:
  created:
    - api/routers/__init__.py
    - api/routers/toolkits.py
    - api/tests/__init__.py
    - api/tests/test_toolkits_router.py
  modified:
    - api/main.py

key-decisions:
  - "All new endpoints go in api/routers/toolkits.py via APIRouter — api/main.py change is only the include_router call"
  - "toolkit_name, display_name, fda_json are migrated columns not in ORM class; all queries touching them use raw sa_text SQL"
  - "Task definition task_name is auto-generated as display_name + SHA256[:8] for uniqueness without requiring user input"
  - "fda_count queries group by toolkit_name (not toolkit_id) — multiple toolkit variants share the same name"

patterns-established:
  - "New API router pattern: create api/routers/X.py with APIRouter, register in main.py via app.include_router"
  - "Migrated column pattern: columns added via IF NOT EXISTS migrations are accessed via raw sa_text, not ORM attributes"

requirements-completed: [DB-03, DB-04, DB-05, DB-06, VAR-04, VAR-05]

# Metrics
duration: 12min
completed: 2026-03-22
---

# Phase 02 Plan 03: Toolkit and Task-Definition CRUD Router Summary

**9-endpoint FastAPI router for toolkit browsing and task-definition CRUD, using raw SQL for IF-NOT-EXISTS migrated columns**

## Performance

- **Duration:** ~12 min
- **Started:** 2026-03-22T16:00Z
- **Completed:** 2026-03-22T16:12Z
- **Tasks:** 3 (Task 0 RED, Task 1+2 GREEN, bug fix)
- **Files modified:** 5

## Accomplishments
- Created `api/routers/toolkits.py` with 9 endpoints accessible at `/api/toolkits` and `/api/task-definitions`
- GET /toolkits enriches each toolkit row with pilot_origins (pilot names) and fda_count
- POST /task-definitions stores fda_json as JSONB with round-trip fidelity verified
- api/main.py change is exactly 2 lines: import + include_router

## Task Commits

Each task was committed atomically:

1. **Task 0: Write failing tests** - `b8b25c5` (test — TDD RED, all 3 fail with 404/import error)
2. **Task 1+2: Create router with all 9 endpoints** - `feb1025` (feat)
3. **Bug fix: raw SQL for migrated columns** - `d030b80` (fix — auto-fixed per Rule 1)

**Plan metadata:** TBD (docs commit)

_Note: TDD tasks have multiple commits (test → feat → fix)_

## Files Created/Modified
- `api/routers/__init__.py` — makes routers a Python package
- `api/routers/toolkits.py` — 9-endpoint APIRouter module (263 lines)
- `api/tests/__init__.py` — test package init
- `api/tests/test_toolkits_router.py` — 3 smoke tests verifying routes exist
- `api/main.py` — 2-line addition: import + include_router

## Decisions Made
- `_SA_SessionLocal` (prefixed with `_`) used in router to avoid confusion with main.py's `SA_SessionLocal`; both use the same `engine` from `db.py`
- `/toolkits/by-name/{name}` registered before `/{toolkit_id}` to prevent FastAPI routing ambiguity with literal "by-name" segment

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Raw SQL required for migrated columns in fda_count queries**
- **Found during:** Task 1 (list_toolkits implementation)
- **Issue:** `TaskDefinition.toolkit_name` raised `AttributeError` at runtime — the column is added by IF NOT EXISTS migration and is NOT declared in the SQLAlchemy ORM class. ORM attribute access fails silently during class inspection but crashes at query time.
- **Fix:** Replaced all three ORM queries that referenced `TaskDefinition.toolkit_name` with raw `sa_text` SQL. Removed unused `func` import.
- **Files modified:** `api/routers/toolkits.py`
- **Verification:** `GET /api/toolkits` returns `[]` (no toolkits in DB yet) instead of 500 error
- **Committed in:** `d030b80` (fix commit)

---

**Total deviations:** 1 auto-fixed (Rule 1 - bug)
**Impact on plan:** Essential fix for correctness. No scope creep.

## Issues Encountered
- The plan's example code for `list_toolkits` used ORM queries (`db.query(TaskDefinition.toolkit_name, ...)`) that fail at runtime because `toolkit_name` is a migrated column absent from the ORM class. The plan context noted "new columns added by migration, not in ORM class" for POST but the same constraint applies to reads.

## User Setup Required
None - no external service configuration required.

## Next Phase Readiness
- All toolkit + task-definition CRUD surface is live
- Phase 3 (FDA editor GUI) can consume GET /toolkits and POST/PUT/GET/DELETE /task-definitions
- Phase 4 (protocol steps FK to task_definitions) will add DELETE guard when task_definition_id FK is established

## Self-Check: PASSED

- api/routers/toolkits.py: FOUND
- api/routers/__init__.py: FOUND
- api/tests/test_toolkits_router.py: FOUND
- 02-03-SUMMARY.md: FOUND
- Commit b8b25c5: FOUND
- Commit feb1025: FOUND
- Commit d030b80: FOUND

---
*Phase: 02-db-api*
*Completed: 2026-03-22*
