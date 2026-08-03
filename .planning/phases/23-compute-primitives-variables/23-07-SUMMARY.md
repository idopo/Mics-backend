---
phase: 23-compute-primitives-variables
plan: 07
subsystem: api
tags: [preflight, compute-primitives, variables, fastapi, sqlalchemy]

# Dependency graph
requires:
  - phase: 23-compute-primitives-variables
    provides: "23-02 compute-lib storage substrate (compute_provisioning.py, hardware_libs.kind); 23-03 variable_scan.py analysis functions; 23-05 lib_version_resolution.py resolver chain"
provides:
  - "Compute-aware preflight step 6: no spurious incomplete_config warning on a compute module's intentionally-empty config, self-heals a missing compute config row before the loop runs"
  - "class_mismatch now reachable for compute modules (previously short-circuited by the incomplete_config branch's early continue)"
  - "Preflight step 9: variable_never_written issue (CMP-15) — a transition reading a variable nothing writes anywhere in the FDA, with the reader's location"
  - "Preflight step 6 lib_version_unresolved issue (CMP-17 rung 5) — a module whose hardware lib has no deployable version, naming module and lib filename"
  - "PREFLIGHT_ISSUE_KINDS frozenset (8 kinds) + compute_lib_import_failed_issue reserved constructor (CMP-19c)"
  - "GET /api/task-definitions/{id}/variable-usage — writers/readers/never_written/initial_value per declared variable"
affects: [23-09, 23-10]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "New router (task_def_inspect.py) follows toolkit_dispatch.py's own get_sa_session Depends pattern (not pilot_hardware_config.py's bare with-block), specifically so it is testable via app.dependency_overrides like every other route in this test file"
    - "Independent per-module checks (lib_version_unresolved) placed before any early `continue` in the step-6 loop so they fire regardless of config presence/absence"

key-files:
  created:
    - api/routers/task_def_inspect.py
  modified:
    - api/routers/toolkit_dispatch.py
    - api/main.py
    - api/tests/test_view_key_preflight.py

key-decisions:
  - "Gated the incomplete_config check on compute_module_names(db, module_ids) rather than checking hardware_libs.kind inline per-module — reuses the same helper get_dispatch_spec already imports, one query for the whole module set"
  - "lib_version_unresolved is checked unconditionally per module (before the cfg_row fetch), independent of missing/incomplete_config, so a module missing BOTH a config row and a deployable lib version gets both issues, not just one"
  - "task_def_inspect.py uses a Depends(get_sa_session) generator (toolkit_dispatch.py's shape) instead of pilot_hardware_config.py's `with _SA_SessionLocal() as session:` — required for the mocked-db.execute TestClient pattern this test file already uses everywhere else"

patterns-established:
  - "PREFLIGHT_ISSUE_KINDS frozenset in toolkit_dispatch.py is the single source of truth for issue-kind strings; plan 23-09 must mirror it in HardwareCheckModal.tsx::PreflightIssue"

requirements-completed: [CMP-15, CMP-17, CMP-19]

# Metrics
duration: ~25min
completed: 2026-08-03
---

# Phase 23 Plan 07: Preflight Truth for Compute + Variable Usage Route Summary

**Preflight no longer cries wolf on a compute module's empty config, self-heals a missing one, reports unwritten-variable reads and undeployable lib versions by name, and exposes a variable-usage route for the editor.**

## Performance

- **Duration:** ~25 min
- **Started:** 2026-08-03T10:11Z (session start)
- **Completed:** 2026-08-03T10:29Z
- **Tasks:** 3/3 completed
- **Files modified:** 4 (1 created, 3 modified)

## Accomplishments
- `preflight_validate` step 6 is compute-aware: a compute module's `{"class_name": ...}`-only config is complete, not incomplete; a hardware module's identical shape is still flagged; `class_mismatch` fires for compute modules too; a missing compute config row self-heals via `provision_compute_configs` before the loop runs (non-blocking).
- Two new preflight issue kinds land: `variable_never_written` (step 9, CMP-15) and `lib_version_unresolved` (step 6, CMP-17 rung 5) — both wired through `PREFLIGHT_ISSUE_KINDS`, a documented 8-kind frozenset that also registers the reserved `compute_lib_import_failed` shape (CMP-19c).
- `GET /api/task-definitions/{id}/variable-usage` (new `api/routers/task_def_inspect.py`, 63 lines) gives the FDA editor's read-only inspector writers/readers/never_written/initial_value per declared variable, live-verified against real task definitions 186 (populated) and 187 (empty), plus a 404 on an unknown id.

## Task Commits

Each task was committed atomically:

1. **Task 1: compute-aware step 6 — no false positive, self-healing config** - `f957545` (fix)
2. **Task 2: step 9 — variable_never_written, plus the two new issue kinds** - `b80b81f` (feat)
3. **Task 3: the variable-usage read route** - `8df43cb` (feat)

_No TDD multi-commit split was used — tests and implementation landed together per task, per this plan's own `tdd="true"` tag interpreted as "write the test alongside the behavior it pins," consistent with how plans 23-05/23-06 executed._

## Files Created/Modified
- `api/routers/toolkit_dispatch.py` (376 → 459 lines) - compute-aware step 6 gate + self-heal; step 9 `variable_never_written`; step-6 `lib_version_unresolved`; `PREFLIGHT_ISSUE_KINDS` + `compute_lib_import_failed_issue`
- `api/routers/task_def_inspect.py` (new, 63 lines) - `GET /task-definitions/{id}/variable-usage`
- `api/main.py` - 2-line diff: import + `include_router` for the new router
- `api/tests/test_view_key_preflight.py` - 19 new tests (7 Task 1, 7 Task 2, 5 Task 3) plus `FakeDb`/`_module`/`_backend_toolkit_scenario` fixture extensions (`hardware_lib_id`, `lib_row`, `lib_meta_row`, `hw_versions_row`, `commit()`) needed to keep all pre-existing tests green under the new per-module lib-resolution query

## Decisions Made
- Placed the `lib_version_unresolved` check before the cfg_row fetch in step 6's loop (not gated behind the missing/incomplete_config branches) — CMP-17's "no deployable version" is orthogonal to whether a pilot has configured the module at all, so both issues can legitimately co-occur for the same module.
- `task_def_inspect.py` uses a `Depends(get_sa_session)` generator matching `toolkit_dispatch.py`'s own shape rather than `pilot_hardware_config.py`'s bare `with _SA_SessionLocal() as session:` block — the plan's own instruction to test this route "in the mocked-`db.execute` TestClient style already used" in this file requires an overridable dependency; the with-block pattern isn't mockable via `app.dependency_overrides`.
- Extended `_backend_toolkit_scenario`/`_compute_toolkit_scenario`/`_module`/`FakeDb` with `hardware_lib_id`/`lib_row` defaults that resolve cleanly (`reason="stable"`) so introducing the per-module lib-version resolution into step 6 didn't require touching every pre-existing test's assertions — only the shared fixtures.

## Deviations from Plan

None — plan executed exactly as written. Both budget notes were honored: `toolkit_dispatch.py` ended at 459 lines (under the 470 threshold that would have required extracting the step-6 loop into a helper, and under the 500 hard limit); `task_def_inspect.py` at 63 lines (under the 70-line target and 100-line hard limit); `api/main.py`'s diff is exactly 2 lines.

## Issues Encountered

None requiring problem-solving beyond routine fixture maintenance (documented above under Decisions Made).

## User Setup Required

None - no external service configuration required.

## Verification Evidence

- Full backend suite: **332 passed** (`docker compose exec -T api python -m pytest -q`), run after all three tasks landed.
- `test_view_key_preflight.py` alone: 74 passed (was 55 pre-plan; +19 new, 0 broken).
- Live: `GET /api/task-definitions/186/variable-usage` returns populated `writers`/`readers` for `level`/`pin_number`; `GET /api/task-definitions/187/variable-usage` returns `{"variables": {}}`; unknown id 999999 returns 404.
- Live regression: `POST /api/sessions/113/preflight-validate/1` (a real backend-authored session/pilot pair) returns `{"ok": true, "issues": []}` — no spurious issue introduced by the compute-aware gate, the new lib-version resolution, or the variable scan against this toolkit's real FDA.
- `wc -l`: `toolkit_dispatch.py` 459, `task_def_inspect.py` 63 — both under budget.

## Next Phase Readiness
- CMP-15's backend half (save-time gate from 23-03 + preflight surfacing here) is complete; CMP-17's dispatch-time resolver (23-05) now also backs preflight's own per-module check.
- `PREFLIGHT_ISSUE_KINDS` and the variable-usage route are the two artifacts plan 23-09 (FDA editor UI) consumes directly — its `HardwareCheckModal.tsx::PreflightIssue` union must be extended to match the 8 kinds enumerated here.
- `compute_lib_import_failed_issue` is registered but unused — nothing on the Pi side reports a compute-lib import failure back to this endpoint yet; that wiring is out of this plan's scope (CMP-19c reserves the shape only).

---
*Phase: 23-compute-primitives-variables*
*Completed: 2026-08-03*

## Self-Check: PASSED

- FOUND: api/routers/task_def_inspect.py
- FOUND: .planning/phases/23-compute-primitives-variables/23-07-SUMMARY.md
- FOUND commit f957545 (Task 1)
- FOUND commit b80b81f (Task 2)
- FOUND commit 8df43cb (Task 3)
