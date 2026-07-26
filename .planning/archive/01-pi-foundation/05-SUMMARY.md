---
phase: 01-pi-foundation
plan: 05
subsystem: tooling
tags: [python, cli, fda, validation, jsonb, postgresql, tdd]

# Dependency graph
requires: []
provides:
  - validate_fda.py CLI tool for FDA v2 JSON validation against toolkit classes
  - rename-hw-ref subcommand for bulk JSONB updates in task_definitions
  - if-action recursive validation (FDA-17) with condition operand checks
affects: [02-db-api, developer workflow for FDA authoring]

# Tech tracking
tech-stack:
  added: [psycopg2 (DB access in rename-hw-ref), pytest (test runner)]
  patterns:
    - "TDD: write failing tests first (RED), then implement (GREEN)"
    - "Shared action-validation loop extracted to _validate_actions_list() for recursion support"
    - "Deprecation warnings vs errors: SEMANTIC_HARDWARE_RENAMES entries warn, unknown refs error"

key-files:
  created:
    - ~/pi-mirror/tools/validate_fda.py
    - ~/pi-mirror/tests/test_validate_fda.py
  modified: []

key-decisions:
  - "validate() signature is validate(definition, cls) — definition first, class second"
  - "if-action recursion: _validate_actions_list() shared by state loop and then/else branches"
  - "JSONB rename runs two statements in single transaction with LIKE guards for efficiency"
  - "trigger_name pin id validation deferred gracefully when HARDWARE attr is absent/empty"

patterns-established:
  - "Error format: ERROR [state 'name' action[N]]: description"
  - "Warning format: WARNING [location]: description"
  - "Exit codes: 0=success, 1=validation error, 2=usage/connection error"

requirements-completed: [FDA-08, FDA-14, FDA-17]

# Metrics
duration: 4min
completed: 2026-03-22
---

# Phase 01 Plan 05: validate_fda.py CLI Validation Tool Summary

**Standalone developer CLI (~/pi-mirror/tools/validate_fda.py) that validates FDA v2 JSON against toolkit class attributes and bulk-renames semantic hardware refs in PostgreSQL JSONB via psycopg2**

## Performance

- **Duration:** 4 min
- **Started:** 2026-03-22T15:04:49Z
- **Completed:** 2026-03-22T15:09:13Z
- **Tasks:** 2 (05-1 and 05-2 implemented together in one commit)
- **Files created:** 2

## Accomplishments
- `validate` subcommand validates 16 rules: version, initial_state, passthrough states, entry_actions (hardware/flag/timer/special/method/if), transitions, trigger_assignments, condition view keys
- `rename-hw-ref` subcommand runs two JSONB UPDATE statements in a single transaction covering both `entry_actions[*].ref` and `trigger_assignments[*].config.hardware_ref`
- FDA-17: `type: "if"` actions recursively validated — condition operands (tracker/flag/param/hardware) and nested then/else branches validated to unlimited depth
- 15 unit tests covering all validation rules; all pass

## Task Commits

Tasks 05-1 and 05-2 implemented together in a single atomic commit (both produce content in the same file):

1. **Tasks 05-1 + 05-2: Create tools/validate_fda.py with all subcommands and if-action support** - `d9b6300` (feat) — in pi-mirror repo

## Files Created/Modified
- `~/pi-mirror/tools/validate_fda.py` - Full CLI tool: validate subcommand, rename-hw-ref subcommand, if-action recursive validation
- `~/pi-mirror/tests/test_validate_fda.py` - 15 unit tests covering core validation rules and FDA-17

## Decisions Made
- `validate()` takes `(definition, cls)` — definition dict first, class second — matching the test signature from PLAN.md
- Tasks 05-1 and 05-2 implemented in a single file/commit since 05-2 was purely additive to the same file
- pytest installed in the mics_api Docker container for running tests (no system-level pip available on host)

## Deviations from Plan

None - plan executed exactly as written. All 16 validation rules implemented. All must_haves satisfied.

## Issues Encountered
- Host system has no pip/venv available — pytest was installed inside the mics_api Docker container (`docker exec mics_api pip install pytest`) and tests run there
- `validate()` signature clarification: plan's test code uses `validate(definition, cls)` (definition first), which was implemented as-is

## User Setup Required
None - no external service configuration required. Tool runs locally against DATABASE_URL env var (only needed for rename-hw-ref subcommand).

## Next Phase Readiness
- validate_fda.py is ready for use by developers before any FDA JSON deployment
- rename-hw-ref requires DATABASE_URL set to the api service DSN and the task_definitions table to exist (Phase 2 creates it)
- No blockers for subsequent plans

## Self-Check: PASSED
- FOUND: ~/pi-mirror/tools/validate_fda.py
- FOUND: ~/pi-mirror/tests/test_validate_fda.py
- FOUND: .planning/phases/01-pi-foundation/05-SUMMARY.md
- FOUND: commit d9b6300 (pi-mirror repo)

---
*Phase: 01-pi-foundation*
*Completed: 2026-03-22*
