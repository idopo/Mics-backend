---
phase: 18-extlink-pi-transport
plan: 03
subsystem: testing
tags: [pytest, fastapi, ast, contract-first, preflight]

# Dependency graph
requires:
  - phase: 23-07
    provides: PREFLIGHT_ISSUE_KINDS frozenset + compute_lib_import_failed_issue RESERVED-SHAPE precedent in api/routers/toolkit_dispatch.py
provides:
  - Backend test contract for api/device_lease.py (EXTLINK-17 lease, EXTLINK-10 config validation, EXTLINK-18 role="none")
  - Backend test contract for api/extlink_ast.py (EXTLINK-09 @signal/@event/@command/@decoder extraction)
  - Pinned device_held / extlink_config_invalid issue shapes for plans 18-08/18-09 and HardwareCheckModal.tsx
affects: [18-07, 18-08, 18-09]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "importorskip-guarded contract tests: pytest.importorskip(module) as the FIRST statement of every test body lets a test file collect and SKIP cleanly before its target module exists, so a later implementation plan (18-07/18-08) is written against a fixed target"
    - "xfail(strict=False) layered on top of importorskip for route-level assertions that depend on a SECOND not-yet-landed wiring step (18-09), so the window between module-exists and route-wired shows XFAIL instead of FAIL"

key-files:
  created:
    - api/tests/test_hardware_libs_extlink.py
  modified:
    - api/tests/test_view_key_preflight.py

key-decisions:
  - "EXTLINK-09's target test file is NEW (api/tests/test_hardware_libs_extlink.py), not an extension of an existing file -- grep -rl \"extract_ast_metadata\" api/tests/ returned nothing, resolving 18-VALIDATION.md's open question"
  - "Lease/config-validation tests use a _LeaseFakeDb subclass of the existing FakeDb, dispatching generically on the substring \"device_leases\" (not exact SQL text) so plan 18-08's real query shape has room to differ from this fixture"
  - "Only 2 of the 19 lease tests are route-level (hit preflight_validate via the TestClient) and need xfail; the other 17 call device_lease functions directly and only need importorskip, so they will start PASSING as soon as 18-08 lands device_lease.py -- independent of 18-09's route wiring"
  - "PREFLIGHT_ISSUE_KINDS' completeness guard extended from 9 to 11 kinds (adds device_held, extlink_config_invalid), still guarded by pytest.importorskip so it doesn't fail today"

requirements-completed: [EXTLINK-09, EXTLINK-10, EXTLINK-17, EXTLINK-18]

# Metrics
duration: 20min
completed: 2026-08-09
---

# Phase 18 Plan 03: Device-lease + AST extractor backend test contracts Summary

**19 importorskip-guarded lease/config-validation tests plus 8 importorskip-guarded AST-extractor tests, pinning EXTLINK-09/10/17/18's shapes before either producer module exists — full backend suite stays at 359 passed with 27 new skips.**

## Performance

- **Duration:** ~20 min
- **Started:** 2026-08-09T07:00:00Z (approx.)
- **Completed:** 2026-08-09T07:21:00Z
- **Tasks:** 2
- **Files modified:** 2 (1 extended, 1 created)

## Accomplishments
- Pinned the device lease's five verification-map rows (EXTLINK-17) plus EXTLINK-10 config validation and EXTLINK-18's `role: "none"` control-only path, all as importorskip-guarded tests in `test_view_key_preflight.py` — the file plan 23-07 already extended twice, per 18-RESEARCH.md's addendum that every preflight ISSUE-KIND test lives there, not in `test_toolkit_dispatch.py`.
- Pinned the AST extractor's three verification-map rows (EXTLINK-09), including the Pitfall-5 bare-type-payload case that would crash a naive `ast.literal_eval`, in a new dedicated file since no existing test file owned `extract_ast_metadata`'s contract.
- Extended `PREFLIGHT_ISSUE_KINDS`' completeness guard to the two new kinds (`device_held`, `extlink_config_invalid`), fixing the exact dict shapes plans 18-08/18-09 and `HardwareCheckModal.tsx` must produce/consume.
- Verified the full backend suite is unaffected: 359 passed (same as pre-plan baseline) with 27 new skips (0 errors).

## Task Commits

Each task was committed atomically:

1. **Task 1: Device-lease + extlink-config preflight contract (EXTLINK-17, EXTLINK-10, EXTLINK-18)** - `d38e9bb` (test)
2. **Task 2: AST extractor contract for @signal/@event/@command/@decoder (EXTLINK-09)** - `2fabc2e` (test)

_Both tasks were `tdd="true"` in the plan, but since the target modules (`device_lease.py`, `extlink_ast.py`) don't exist until later plans, there is no RED→GREEN cycle to run here — every new test is guarded to SKIP today by design. Verification was collection + skip-count assertions, not a pass/fail cycle._

## Files Created/Modified
- `api/tests/test_view_key_preflight.py` - Appended 19 `lease`-named tests (device_lease module contract: `normalize_host`, `is_extlink_config`, `validate_extlink_config`, `preflight_device_lease_issues`, `force_release`, `reconcile_leases`) plus the extended `PREFLIGHT_ISSUE_KINDS` guard. Includes `_LeaseFakeDb` (subclass of the existing `FakeDb`, not an edit to it) with an in-memory `device_leases` table.
- `api/tests/test_hardware_libs_extlink.py` - New file, 8 tests for `extract_extlink_metadata` (`api/extlink_ast.py`, plan 18-07): signal/event/command/decoder extraction, the bare-type payload pitfall, zero-signal control-only classes, non-extlink-class inertness, and one xfailed route-level upload round trip.

## Decisions Made
- **New file for EXTLINK-09** (not an extension): `grep -rl "extract_ast_metadata" api/tests/` returned nothing before this plan — no test file's ownership was being displaced.
- **`_LeaseFakeDb` dispatches on the substring `"device_leases"`, not exact SQL text**: since `device_lease.py` doesn't exist yet, pinning exact query text would over-constrain plan 18-08's implementation. The fixture supports SELECT-by-host, SELECT-all, INSERT (upsert), and DELETE against an in-memory dict, giving 18-08 freedom in its actual column list / predicate order.
- **Only 2 tests marked `xfail`**: `test_lease_blocks_second_run_same_host` and `test_lease_preflight_role_none_module_is_clean`, because these are the only two tests that exercise the real `/preflight-validate` HTTP route (via the existing `_preflight()` helper) rather than calling a `device_lease` function directly. The other 17 lease tests will start passing the moment `device_lease.py` exists (18-08), independent of the route-wiring plan (18-09).
- **`device_held` issue's `holder` dict and `detail` string shape** pinned by `test_lease_blocks_second_run_same_host`: `holder` carries at minimum `pilot_name` and `acquired_at`; `detail` names the holding pilot and (subject/run id). This is the exact shape `HardwareCheckModal.tsx` must mirror in plan 18-09.
- **Pre-plan baseline recorded**: `359 passed, 1 skipped`. **Post-plan**: `359 passed, 28 skipped` (27 new skips: 19 lease + 8 extlink-AST, 0 errors, 0 regressions).

## Deviations from Plan

None - plan executed exactly as written. Both tasks' automated `<verify>` blocks passed on the first attempt (`-k lease` selected 19 SKIPPED tests, `-k role_none` selected 5, `test_hardware_libs_extlink.py` collected 8 tests all SKIPPED, full suite green at 359 passed).

## Issues Encountered
None. One environment note (not a deviation): the plan's `<verify>` blocks use the path `api/tests/test_view_key_preflight.py` relative to the repo root, but the in-container pytest invocation path is `tests/test_view_key_preflight.py` (per this repo's `CLAUDE.md` — the api container's workdir is `/app` with `api/` copied as its contents). Ran verification with the correct in-container path; no code or test content changed as a result.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness
- Plan 18-07 (`api/extlink_ast.py`) can now be implemented directly against `test_hardware_libs_extlink.py`'s 8 pinned cases — remove the `pytest.importorskip("extlink_ast")` guards and the file's xfail marker as each lands.
- Plan 18-08 (`api/device_lease.py`) can be implemented directly against 17 of the 19 lease tests (everything except the 2 route-level ones) — remove `pytest.importorskip("device_lease")` guards as functions land.
- Plan 18-09 (route wiring into `preflight_validate`) removes the 2 remaining `xfail` markers once the lease/config checks are added to the route, and must update `PREFLIGHT_ISSUE_KINDS` to the 11-kind set this plan already pinned.
- No blockers for Wave 1 (18-05/06/07/08), which was already scheduled to run in parallel with this plan per the phase's wave structure.

---
*Phase: 18-extlink-pi-transport*
*Completed: 2026-08-09*

## Self-Check: PASSED

- FOUND: api/tests/test_view_key_preflight.py
- FOUND: api/tests/test_hardware_libs_extlink.py
- FOUND: .planning/phases/18-extlink-pi-transport/18-03-SUMMARY.md
- FOUND: d38e9bb (task 1 commit)
- FOUND: 2fabc2e (task 2 commit)
