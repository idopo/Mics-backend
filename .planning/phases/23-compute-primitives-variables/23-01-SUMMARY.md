---
phase: 23-compute-primitives-variables
plan: 01
subsystem: testing
tags: [pytest, contract-tests, tdd, fastapi, compute-primitives, hardware-libs]

# Dependency graph
requires: []
provides:
  - "api/tests/test_hardware_lib_kind.py — CMP-12/19 contract: kind-column migration idempotency, seed_compute_ops_lib idempotency, POST /api/hardware-libs kind=compute/declared_imports behavior"
  - "api/tests/test_toolkit_dispatch.py — CMP-17 contract: resolve_lib_version_id chain (pin > toolkit_default > stable > active > none), get_dispatch_spec stable-over-active regression, list_toolkit_hardware_libs resolution-field regression"
  - "/home/ido/pi-mirror/tests/test_compute_ops.py — CMP-03/04/05 contract: Hardware-subclass release() enforcement, compute action dispatch/output/last-write-wins (USER-RUN)"
affects: [23-02-hardware-lib-kind-migration, 23-04-pi-compute-dispatch, 23-05-lib-version-resolution, 23-10-pi-deploy-and-rig-proof]

tech-stack:
  added: []
  patterns:
    - "Wave-0 contract tests: guard not-yet-existing symbols with function-body try/except ImportError -> pytest.skip (not module-level import), or pytest.importorskip called inside the test body when only some tests in a file need the guard"
    - "Module-level pytest.importorskip used only when EVERY test in the file targets the same not-yet-built module (test_toolkit_dispatch.py) — skips the whole file as one unit rather than erroring per-test"
    - "Route contract tests for not-yet-added request/response fields use @pytest.mark.xfail(strict=False) so the suite stays green while pinning the exact expected status code + message substring"

key-files:
  created:
    - api/tests/test_hardware_lib_kind.py
    - api/tests/test_toolkit_dispatch.py
    - /home/ido/pi-mirror/tests/test_compute_ops.py
  modified: []

key-decisions:
  - "Migration/seed tests import the not-yet-existing symbol inside the test body (try/except ImportError -> pytest.skip, or pytest.importorskip inline) rather than at module level, so a single missing symbol degrades one test to skip instead of erroring the whole file's collection"
  - "test_toolkit_dispatch.py is guarded by ONE module-level pytest.importorskip('lib_version_resolution') since every test in it (pure unit + route regression) depends on the same not-yet-built plan-23-05 artifact; route tests additionally carry their own xfail as a second layer for when the resolver lands before the routes are rewired"
  - "resolve_lib_version_id's mock db in test_toolkit_dispatch.py dispatches on table-name substrings (checking 'toolkit_hardware_libs' before the substring-colliding 'hardware_libs') rather than pinning an unverifiable exact query shape, since the real implementation doesn't exist yet"
  - "Route tests against POST /api/hardware-libs and GET /toolkits/{id}/hardware-libs mock the DB via unittest.mock.patch on each router's own _SA_SessionLocal (both routers create sessions directly, not via FastAPI Depends), while toolkit_dispatch.py's get_dispatch_spec/preflight_validate use the existing get_sa_session DI override pattern from test_view_key_preflight.py"
  - "test_compute_ops.py defines a two-method _Ops(Hardware) stand-in class in-module rather than importing the seed compute_ops.py, per the plan's HARD RULE against a second copy of DB-sourced code silently drifting from the deployed seed lib"

requirements-completed: [CMP-04, CMP-12, CMP-17, CMP-19]

# Metrics
duration: 35min
completed: 2026-08-03
---

# Phase 23 Plan 01: Wave 0 Contract Tests Summary

**Three Wave-0 contract test files for CMP-12/17/19/04 — kind-column migration, hardware-lib version-resolution chain, and Pi-side compute-action dispatch — all failing/skipping/xfailing today for the right reason, none of the production code they target exists yet.**

## Performance

- **Duration:** ~35 min
- **Started:** 2026-08-03 (session start)
- **Completed:** 2026-08-03T09:10:23Z
- **Tasks:** 3/3
- **Files modified:** 3 created (2 committed to mics-backend, 1 written to pi-mirror per pi_rules)

## Accomplishments

- `api/tests/test_hardware_lib_kind.py` (9 tests): 2 real-DB migration-idempotency tests, 2
  real-DB `seed_compute_ops_lib`/allowlist tests, 5 xfail route tests pinning the exact 422
  messages `POST /api/hardware-libs` must emit for `kind='compute'` without `release()`,
  `declared_imports=["numpy"]`, and `kind='banana'`. Verified: 4 skipped, 5 xfailed, 0 errors.
- `api/tests/test_toolkit_dispatch.py` (11 tests): 8 pure-unit tests pinning
  `resolve_lib_version_id`'s pin > toolkit_default > stable > active > none chain (every reason
  string covered at least once, plus a `toolkit_id=None` edge case), 1 non-xfail baseline proving
  the mocked-db harness against today's real behavior, 2 xfail regression tests for the
  stable-over-active dispatch-spec fix and the `resolved_version_id`/`resolved_state`/
  `resolution_reason` fields `list_toolkit_hardware_libs` must gain. Verified: whole module
  skips as one unit (module-level `importorskip`) since `api/lib_version_resolution.py` doesn't
  exist yet.
- `/home/ido/pi-mirror/tests/test_compute_ops.py` (8 tests, USER-RUN): pins Research Pitfall 7
  (`Hardware.__init__`'s bare `kwargs['type']`) and Pitfall 3 (`release()` must be overridden or
  `Task.end()` raises on every run), plus the compute action's build-time `output`-required
  behavior, the `group`-present/absent dual resolution form, and last-write-wins re-invocation.
  Compiles cleanly (`python3 -m py_compile`); not deployed or run — USER-RUN belongs to plan
  23-10.
- Full backend suite confirmed green after both new files: **231 passed, 5 skipped, 5 xfailed**,
  no errors — verified both before and after `docker compose up --build api` (the api service has
  no bind mount; new test files require a rebuild to appear in the running container).

## Task Commits

1. **Task 1: Contract tests for the `kind` column and declared-imports (CMP-12, CMP-19)** -
   `3b242f5` (test)
2. **Task 2: Contract tests for the CMP-17 version-resolution chain** - `487637a` (test)
3. **Task 3: Pi-side compute contract test (USER-RUN)** - no mics-backend commit; file lives in
   `/home/ido/pi-mirror` (its own user-owned git repo — pi_rules forbid any git command there,
   per prior phase 25 precedent)

**Plan metadata:** (this commit, made after this summary)

## Files Created/Modified

- `api/tests/test_hardware_lib_kind.py` - CMP-12/19 contract: migration idempotency (real DB),
  `seed_compute_ops_lib` idempotency (real DB), 5 xfail route tests for `kind='compute'`/
  `declared_imports`
- `api/tests/test_toolkit_dispatch.py` - CMP-17 contract: `resolve_lib_version_id` chain (8 pure
  unit tests), `get_dispatch_spec`/`list_toolkit_hardware_libs` route regressions, module-level
  `importorskip`
- `/home/ido/pi-mirror/tests/test_compute_ops.py` - CMP-03/04/05 contract: Hardware-subclass
  `release()` enforcement, compute action dispatch/output/last-write-wins (USER-RUN, not deployed)

## Decisions Made

See `key-decisions` in frontmatter. Summary: guard styles differ per file based on whether all
tests share one not-yet-built dependency (module-level `importorskip` in
`test_toolkit_dispatch.py`) versus a mix of already-real DB integration tests plus not-yet-real
route tests (per-test guards in `test_hardware_lib_kind.py`); DB mocking target is the router's
own `_SA_SessionLocal` for `hardware_libs.py` (no DI) versus the `get_sa_session` FastAPI
dependency override already established in `toolkit_dispatch.py`/`test_view_key_preflight.py`.

## Deviations from Plan

None — plan executed exactly as written. One clarification made during execution: the plan's
instruction to guard Task 1's seed tests with `pytest.importorskip("seed_compute")` "at the top"
was interpreted as inside each seed test's body (not true module level), since a true
module-level `importorskip` would have skipped the migration tests too — those import
`run_hardware_lib_kind_migration` independently and are meant to run for real (and did, as real
DB integration tests) the moment plan 23-02 adds that symbol, without waiting on `seed_compute.py`
to exist as well.

## Issues Encountered

The `api` service in `docker-compose.yml` has no bind mount (image built via `COPY . .` at build
time) — new test files added on the host were invisible to `docker compose exec api pytest`
until the image was rebuilt. Worked around during verification with `docker cp` into the running
container (no image change), then ran a full `docker compose up --build api` afterward so the
committed test files are actually part of the running image, matching this repo's own
`docker compose up --build api` convention from `CLAUDE.md`.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness

- All three Wave-0 ❌ targets from `23-VALIDATION.md` now have a file on disk with real
  assertions; `23-VALIDATION.md`'s "Wave 0 Requirements" checklist items are all satisfied.
- Plan 23-02 (kind-column migration + `seed_compute.py` + declared-imports enforcement) can
  proceed knowing exactly which assertions in `test_hardware_lib_kind.py` its final task must
  turn from skip/xfail to pass — no separate test-writing pass needed for CMP-12/19.
- Plan 23-05 (lib-version-resolution chain + route rewiring) has the full
  `resolve_lib_version_id` contract in `test_toolkit_dispatch.py`, including the exact
  `(version_id, reason)` tuple shape and all five reason strings, plus the two route-level
  regressions (stable-over-active source_code, resolution fields on the toolkit hardware-libs
  list) it must satisfy.
- Plan 23-04 (Pi `_build_action_callable` "compute" branch + `fda_vocabulary.VALID_ACTION_TYPES`)
  has `test_compute_ops.py` as its acceptance contract; plan 23-10 owns actually running it on
  the Pi and deploying it.
- No pi-mirror files other than the new `tests/test_compute_ops.py` were touched this plan.

---
*Phase: 23-compute-primitives-variables*
*Completed: 2026-08-03*

## Self-Check: PASSED

- FOUND: api/tests/test_hardware_lib_kind.py
- FOUND: api/tests/test_toolkit_dispatch.py
- FOUND: .planning/phases/23-compute-primitives-variables/23-01-SUMMARY.md
- FOUND: /home/ido/pi-mirror/tests/test_compute_ops.py
- FOUND commit: 3b242f5
- FOUND commit: 487637a
