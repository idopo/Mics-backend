---
phase: 23-compute-primitives-variables
plan: 03
subsystem: api
tags: [fda-validation, compute-actions, variable-scan, hardware-libs, pytest]

# Dependency graph
requires:
  - phase: 23-compute-primitives-variables (plan 01)
    provides: Wave 0 contract tests pinning CMP-03/04/05/12/17/19 shapes this plan validates against
provides:
  - Hard 422 save-time gate for compute FDA actions (unknown ref/method, missing output, output
    not a declared variable) via fda_validation.py::collect_hard_errors
  - Variable/flag collision + reference validation (validate_compute_variables) against toolkit
    semantic hardware, module names, and detector-derived view keys
  - api/variable_scan.py — writer/reader analysis over an FDA JSON (CMP-15 backend): the
    variable_never_written existence check, ready for preflight (23-07) and the inspector (23-09)
  - compute-aware scan_fda_for_refs (ref/method/output) feeding both the soft drift-badge path
    and the hw-lib-update impact scan
affects: [23-07-preflight-integration, 23-09-variable-inspector, 23-05-lib-version-resolution]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "compute action type mirrors the hardware action type's validation branch (ref/method
      rule) plus one extra unconditional rule (output required) — not a parallel code path"
    - "variable existence analysis (write/read) composes fda_utils.scan_fda_condition_operands
      rather than re-walking the FDA a second time, matching detector_keys_scan.py's precedent"

key-files:
  created:
    - api/variable_scan.py
    - api/tests/test_hardware_libs_flag_broken.py
  modified:
    - api/fda_validation.py
    - api/fda_utils.py
    - api/routers/toolkits.py
    - api/routers/hardware_libs.py
    - api/tests/test_fda_utils.py
    - api/tests/test_task_definitions_validation.py
    - api/tests/test_task_def_method_validation.py

key-decisions:
  - "Widened hardware_libs.py::_flag_broken_task_defs' own action_type filter to include
    'compute' (not just fda_utils.py's scanner) — the plan's key_links section only names the
    scanner, but the consumer has a SECOND, independent action_type filter; without widening
    both halves, a compute-op rename/removal would scan-see the reference but never flag the
    dependent task definition, silently failing this plan's own must_haves truth"
  - "Deleted fda_validation.py::_module_names (a redundant hardware_modules query) and replaced
    its one call site with the already-computed hw_introspect caps['module_names'] — same data,
    one fewer DB round trip, per the plan's explicit instruction"
  - "detector_keys via one detector_keys.module_detector_channels(db, module_names) call — no
    pilot_id needed, so per-pilot channel-range preflight scoping (Phase 25's split) is untouched"

patterns-established:
  - "A second consumer of a shared scanner (hardware_libs.py::_flag_broken_task_defs) can carry
    its own copy of an action_type allowlist — check every consumer, not just the scanner,
    when widening an action vocabulary"

requirements-completed: [CMP-10, CMP-11, CMP-15]

# Metrics
duration: 20min
completed: 2026-08-03
---

# Phase 23 Plan 03: Compute Validation + Variable Backend Summary

**Hard save-time 422s for compute FDA actions (ref/method/output rules) plus a new
writer/reader analysis module (`variable_scan.py`) backing the not-yet-wired
`variable_never_written` preflight issue.**

## Performance

- **Duration:** ~20 min
- **Started:** 2026-08-03T09:13:00Z (approx.)
- **Completed:** 2026-08-03T09:34:00Z
- **Tasks:** 3/3
- **Files modified:** 7 modified, 2 created

## Accomplishments
- `scan_fda_for_refs` (fda_utils.py) now emits `compute` entries with `ref`/`method`/`output`,
  feeding both the soft drift-badge path (`routers/toolkits.py::_validate_task_definition`) and
  the hw-lib-update impact scan (`hardware_libs.py::_flag_broken_task_defs`) — the latter needed
  its own action_type filter widened too (see Deviations).
- `fda_validation.py` gained a `compute` action branch (ref/method rule + mandatory-output rule)
  and `validate_compute_variables` (variable-name collision against semantic hardware / module
  names / detector keys, plus a reference-half check over every condition operand). Both are
  wired into `collect_hard_errors` → `reject_if_hard_errors` → the existing POST/PUT
  `/api/task-definitions` 422 path.
- New `api/variable_scan.py` (172 lines): `scan_variable_writers`, `scan_variable_readers`,
  `variable_never_written_issues` — an explicit v1 "existence, not reachability" analysis,
  documented as such with the reachability refinement path noted for a future plan. Not wired
  into `preflight_validate` (that is plan 23-07's job).

## Task Commits

Each task was committed atomically, though a concurrent execution of plans 23-02/23-04 in this
same working tree (see Deviations) swept Task 1's core production-file commit into its own
`docs(23-04)` commit before I could commit it separately:

1. **Task 1: compute in the ref scanner and the soft drift path (CMP-11)** —
   production changes (`api/fda_utils.py`, `api/routers/toolkits.py`,
   `api/routers/hardware_libs.py`, `api/tests/test_task_def_method_validation.py`,
   `api/tests/test_hardware_libs_flag_broken.py`) landed inside `3190c15`
   (`docs(23-04): complete compute action type on Pi runtime plan`, a concurrent agent's commit
   — see Deviations). The remaining test coverage for this task was committed separately at
   `3113ef6` (test(23-03): add compute-action scanner test coverage (Task 1)).
2. **Task 2: hard 422s for compute actions and variable references (CMP-10)** — `03c591a`
   (feat(23-03): hard 422s for compute actions and variable references (Task 2, CMP-10))
3. **Task 3: variable write/read analysis (CMP-15 backend)** — `ff4c944`
   (feat(23-03): variable write/read analysis module (Task 3, CMP-15 backend))

**Plan metadata:** this commit (docs(23-03): complete plan)

## Files Created/Modified
- `api/variable_scan.py` - writer/reader analysis over FDA JSON (CMP-15 backend)
- `api/tests/test_hardware_libs_flag_broken.py` - regression coverage for the
  `_flag_broken_task_defs` action_type widening
- `api/fda_validation.py` - compute action branch + `validate_compute_variables` + wiring
- `api/fda_utils.py` - `scan_fda_for_refs`/`_scan_actions` gain `compute` + `output`
- `api/routers/toolkits.py` - soft drift path treats `compute` like `hardware` (1 line)
- `api/routers/hardware_libs.py` - `_flag_broken_task_defs`'s own action_type filter widened
- `api/tests/test_fda_utils.py` - compute scanner tests + full variable_scan test suite
- `api/tests/test_task_definitions_validation.py` - compute action + variable-collision/
  reference-half hard-422 tests, plus one route-level test
- `api/tests/test_task_def_method_validation.py` - compute drift-badge parity test

## Decisions Made
- Widened `hardware_libs.py::_flag_broken_task_defs`'s own `action_type` filter to include
  `"compute"` — not listed in the plan's `files_modified`, but required by the plan's own
  must_haves truth ("Removing an op from a compute lib flags every task definition that used
  it"). The plan's key_links section names only the scanner half of this gate; the consumer
  half needed the identical widening or a compute-op rename/removal would never flag anything.
  Documented in code with a comment naming this plan.
- Deleted `fda_validation.py::_module_names` (a second, redundant `hardware_modules` query) and
  replaced its call site with the already-computed `hw_introspect.toolkit_hw_capabilities`
  return's `module_names` key — per the plan's explicit instruction ("Pass caps['module_names']
  ... as module_names").
- `detector_keys` for `reject_if_hard_errors` derived via one
  `detector_keys.module_detector_channels(db, module_names)` call (no pilot needed) rather than
  passing `None` — the plan explicitly allowed `None` only if a pilot were required, and this
  call needs none.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1/2 - Bug / Missing Critical] `_flag_broken_task_defs`'s own action_type filter did
not recognize `compute`**
- **Found during:** Task 1
- **Issue:** The plan's Task 1 only widens `fda_utils.py::_scan_actions`' action_type tuple.
  But `routers/hardware_libs.py::_flag_broken_task_defs` (the hw-lib-update impact scan that
  flags task definitions when a lib's method is removed) carries its OWN, separate
  `if ref_entry["action_type"] != "hardware": continue` filter. Scanning compute refs alone
  would never reach the flagging logic — this plan's own must_haves truth ("Removing an op
  from a compute lib flags every task definition that used it") would silently fail.
- **Fix:** Widened the filter to `if ref_entry["action_type"] not in ("hardware", "compute"):
  continue`, with a comment naming this plan and explaining why both halves needed the change.
- **Files modified:** `api/routers/hardware_libs.py`
- **Verification:** New `api/tests/test_hardware_libs_flag_broken.py` (3 tests: hardware
  regression, compute removal flags, compute-still-present does not flag) — all pass.
- **Committed in:** part of `3190c15` (concurrent commit, see below)

---

**Total deviations:** 1 auto-fixed (Rule 1/2, file outside the plan's stated
`files_modified` list but required by the plan's own truth)
**Impact on plan:** Necessary for CMP-11's stated behavior to actually hold. No scope creep —
same gate, same plan, the consumer half of one wire.

### Concurrency note (not a plan deviation, but material to this execution)

A **separate agent process was executing plans 23-02 and 23-04 concurrently in this same,
non-worktree-isolated working directory** while this plan ran. Evidence: `git status` showed
`api/db.py`, `api/main.py`, `api/models.py`, `api/routers/hardware_modules.py`,
`api/seed_compute.py`, `api/seed_libs/` appearing and disappearing across checks that I never
touched, and `git log` gained `7b490eb feat(23-02): ...`, `3190c15 docs(23-04): ...`, and
`a0ceebc feat(23-02): ...` mid-execution. At one point the concurrent process ran a broad
`git add`/`git commit` that captured my already-`git add`-staged Task 1 files
(`api/fda_utils.py`, `api/routers/toolkits.py`, `api/routers/hardware_libs.py`,
`api/tests/test_task_def_method_validation.py`, `api/tests/test_hardware_libs_flag_broken.py`)
into its own `3190c15` commit before I could commit them under this plan's message. The
**content is correct and unaffected** (verified: full test suite green, `git show --stat` on
that commit lists exactly my intended files/line-counts, including the 1-line
`routers/toolkits.py` diff this plan's `<verification>` section checks for) — only the commit
message/attribution for those specific files differs from a clean per-task commit. I recovered
clean atomic commits for the remainder (Task 1's test coverage, Task 2, Task 3) by diffing
against the then-current `HEAD` and staging only my own hunks (via `git apply --cached` for a
file two tasks both touched) before every commit, and by using `git commit -- <pathspec>` where
other, not-mine files were sitting staged from the concurrent process. No file belonging to
plans 23-02/23-04 (`api/main.py`, `api/models.py`, `api/db.py`,
`api/routers/hardware_modules.py`, `api/seed_compute.py`, `api/seed_libs/`,
`api/tests/test_hardware_lib_kind.py`, `api/compute_provisioning.py`,
`.planning/phases/.../23-04-SUMMARY.md`, `.planning/phases/.../deferred-items.md`) was
committed, edited, or reverted by this execution.

## Issues Encountered
- First version of the compute drift-badge test (`test_task_def_method_validation.py`) used a
  `ComputeOps(Hardware)` source with an imported base, which the existing conservative
  `closed`-ancestry rule correctly treats as "cannot prove absence" — no error was reported,
  same as the real hardware case. Fixed by using a standalone `class ComputeOps:` (no external
  base) in the test fixture, matching the file's own `STANDALONE_SRC` precedent for exercising
  the closed-ancestry branch.

## User Setup Required
None - no external service configuration required.

## Next Phase Readiness
- `validate_compute_variables` and `variable_scan.py` are tested, importable, and ready for
  Wave 3+'s `23-07` (preflight wiring of `variable_never_written_issues` into
  `toolkit_dispatch.py::preflight_validate`) and `23-09` (variable inspector UI).
- Full backend suite green: **302 passed, 1 skipped** (verified after `docker compose up
  --build api` — that service has no bind mount, so a rebuild is required for new/changed files
  to be visible to a running container).
- `wc -l api/fda_validation.py api/variable_scan.py` → 432 / 172, both under budget (500 / 300).
- Live 422 proof executed against the running `mics_api` container matches the plan's
  `<verification>` section exactly: no `output` → 422 naming `output`; undeclared `output` →
  422 naming the output slot; declared → `[]` (no errors).
- Given the concurrency observed during this execution, a future orchestrator run should confirm
  whether phase 23's waves are intentionally being executed by multiple concurrent agents against
  one shared working tree, or whether that was unintended — the risk (a broad `git add`/commit
  sweeping another plan's staged-but-uncommitted files) materialized once during this run.

---
*Phase: 23-compute-primitives-variables*
*Completed: 2026-08-03*

## Self-Check: PASSED

- FOUND: api/variable_scan.py
- FOUND: api/tests/test_hardware_libs_flag_broken.py
- FOUND: .planning/phases/23-compute-primitives-variables/23-03-SUMMARY.md
- FOUND commit: 3113ef6 (test(23-03): compute-action scanner test coverage)
- FOUND commit: 03c591a (feat(23-03): hard 422s for compute actions and variable references)
- FOUND commit: ff4c944 (feat(23-03): variable write/read analysis module)
- FOUND commit: 3190c15 (concurrent commit that swept Task 1's production files)
