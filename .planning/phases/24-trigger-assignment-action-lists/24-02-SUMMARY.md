---
phase: 24-trigger-assignment-action-lists
plan: 02
subsystem: api
tags: [fastapi, pytest, fda-validation, trigger-assignments]

# Dependency graph
requires:
  - phase: 24 (Plan 01)
    provides: FDA-JSON-v2 vocabulary decisions (view action, output capture, trigger context) that this plan's validator mirrors
provides:
  - "api/fda_utils.scan_fda_for_refs extended over trigger_assignments[*].actions (scope-tagged results)"
  - "api/fda_validation.py — validate_variables, validate_trigger_assignments, collect_hard_errors, reject_if_hard_errors"
  - "Hard 422 gate wired into POST/PUT /api/task-definitions, fully separate from the soft _validate_task_definition drift-badge path"
  - "pytest + httpx runnable in the mics_api container (api/requirements.txt + docker exec pip install)"
affects: [24-03, 24-04, 24-08, 23]

# Tech tracking
tech-stack:
  added: [pytest, httpx (api test dependencies)]
  patterns:
    - "scope-tagged scanner results (scope: state|trigger) with a shared ref_label() formatter so trigger-scoped messages never match the React canvas' /^State '...': / regex"
    - "hard-422 validation lives in a dedicated module (fda_validation.py) separate from soft drift-detection (_validate_task_definition), called via a 2-line reject_if_hard_errors(db, fda, toolkit_id) helper to keep routers/toolkits.py's net growth minimal"

key-files:
  created:
    - api/fda_validation.py
    - api/tests/test_fda_utils.py
    - api/tests/test_task_definitions_validation.py
  modified:
    - api/requirements.txt
    - api/fda_utils.py
    - api/routers/toolkits.py
    - api/routers/hardware_libs.py

key-decisions:
  - "known_hw for hardware/timer ref checks is set(semantic_hardware.keys()) only; actions carrying an explicit 'group' key (direct-ref/GUI-built format) skip the ref check entirely, since that path resolves via self.hardware[group][ref] on the Pi and this module deliberately has no DB access to join hardware_module_ids to friendly names"
  - "trigger_name is validated against toolkit.trigger_sources only when that attribute exists AND is non-empty (getattr(toolkit, 'trigger_sources', None) or []) — pre-Plan-08 toolkits are never falsely rejected"
  - "view action key_template is validated for shape only (non-empty string, every {token} names a declared variable/flag) — key RESOLUTION stays out of scope, deferred to Phase 13's pilot-specific preflight per 24-CONTEXT.md"
  - "reject_if_hard_errors(db, fda, toolkit_id) extracted into fda_validation.py (not toolkits.py) so each of the two call sites is a single line — net growth on toolkits.py is 6 lines against a 15-line budget"

requirements-completed: [TRIGA-07, TRIGA-08, TRIGA-10]

# Metrics
duration: ~25min
completed: 2026-07-27
---

# Phase 24 Plan 02: Trigger-Assignment Hard Validation Summary

**New `api/fda_validation.py` gives `trigger_assignments` its first-ever backend validation — a bad hardware ref, an unsupported action type, or a handler-only legacy entry now returns 422 at save time instead of a Pi `ValueError` at session start.**

## Performance

- **Duration:** ~25 min
- **Completed:** 2026-07-27T12:14:00Z
- **Tasks:** 3
- **Files modified:** 7 (4 modified, 3 new)

## Accomplishments
- `fda_utils.scan_fda_for_refs` now walks `trigger_assignments[*].actions` with the same `_scan_actions` recursion used for state `entry_actions`, tagging every result with `scope: "state"|"trigger"` and exposing a `ref_label()` helper so trigger-scoped drift messages never collide with the React canvas' state-warning regex.
- New `api/fda_validation.py` (184 lines, no router imports) is the single hard-422 enforcement point for the trigger action vocabulary: structural checks (trigger_name required/non-empty, unknown trigger_name against `toolkit.trigger_sources` when known, `actions` required now that the `handler` enum is gone) plus per-action checks (unknown type, unresolvable hardware/method/special/flag ref, `view` key_template shape, `output` slot declaration, `{"trigger": ...}` arg/kwarg key validation) and a `variables`/toolkit-flag collision check.
- Wired into both `POST /api/task-definitions` and `PUT /api/task-definitions/{id}` via a 2-line `reject_if_hard_errors(db, fda, toolkit_id)` call each — `routers/toolkits.py` grew by only 6 net lines (budget was 15). The existing soft `_validate_task_definition` (state-body hw-lib-drift badge, always 200) is untouched.
- `pytest`/`httpx` now installed in the running `mics_api` container and added to `api/requirements.txt`; the API test suite went from 4 tests to 56, all passing.

## Task Commits

1. **Task 1: Make the api test suite runnable, extend scan_fda_for_refs over trigger actions** - `533fd3d` (test)
2. **Task 2: New api/fda_validation.py — hard-422 trigger-assignment and variables validation** - `47c78d5` (feat)
3. **Task 3: Wire the hard-422 gate into POST and PUT task-definitions** - `7c48c6f` (feat)

_All three tasks were TDD or test-first: each new test file was copied into the running container and confirmed to fail (ImportError / ModuleNotFoundError) before the corresponding implementation was written._

## Files Created/Modified
- `api/fda_validation.py` - new: `validate_variables`, `validate_trigger_assignments`, `collect_hard_errors`, `reject_if_hard_errors`
- `api/fda_utils.py` - `scan_fda_for_refs`/`_scan_actions` gained `scope`; new `ref_label()` helper
- `api/routers/toolkits.py` - `ref_label` used in `_flag_broken_defs_for_toolkit` and `_validate_task_definition`; `reject_if_hard_errors` called in `create_task_definition` and `update_task_definition`
- `api/routers/hardware_libs.py` - impact-scan formatter uses `ref_label`
- `api/requirements.txt` - added `pytest`, `httpx`
- `api/tests/test_fda_utils.py` - new, 12 tests
- `api/tests/test_task_definitions_validation.py` - new, 40 tests (34 unit + 6 route-level)

## Decisions Made
- `known_hw` for hardware/timer refs is `semantic_hardware` keys only; direct-ref (`"group"`-carrying) actions skip the ref check entirely rather than attempting a DB join `fda_validation.py` deliberately doesn't have. See key-decisions above for full rationale.
- `trigger_name` enforcement against `toolkit.trigger_sources` uses `getattr(..., None) or []`, so it is a no-op on any toolkit that predates Plan 08's column — tested explicitly with a stub toolkit lacking the attribute at all.
- `view` action validation stops at key_template *shape*; resolution is explicitly deferred to Phase 13, matching 24-CONTEXT.md's instruction not to validate against the (advisory, non-authoritative) `detector_view_keys` column here.
- Extracted `reject_if_hard_errors` into `fda_validation.py` rather than inlining the toolkit lookup + raise at both call sites in `toolkits.py`, to stay well under the 15-line growth budget (actual: 6 lines) and avoid duplicating the same 6 lines twice.

## Deviations from Plan

None — plan executed exactly as written. All three tasks matched their `<behavior>`/`<action>` specs; no Rule 1-4 fixes were needed, and no auth gates were encountered.

## Issues Encountered
- `docker-compose.yml` mounts no volume for `api/` (COPY-at-build-time Dockerfile), so iterative TDD required `docker cp` of each changed file into the running `mics_api` container between edit and test run, rather than relying on live-reload. All files were verified byte-identical between host and container before finalizing (`diff -q` check), except `api/requirements.txt` itself — which was intentionally left as a host-only record of the dependency, since `pytest`/`httpx` were installed into the running container directly via `pip install` per the plan's `<test_environment>` instructions, not via image rebuild.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness
- `api/fda_validation.py` is the extension point Plan 23 (Compute Primitives) is expected to append to (`collect_hard_errors` docstring says so explicitly).
- Plan 04 (Pi-side `actions` branch) and Plan 08 (trigger_sources HANDSHAKE column) can now rely on this backend gate rejecting drift at save time; Plan 08 landing the `trigger_sources` column on `TaskToolkit` will automatically activate the currently-dormant `unknown trigger_name` enforcement (already tested against both a toolkit with and without the attribute).
- Full `api/tests/` suite green (56 passed) — see verification output below.

## Verification Output

```
$ docker exec -w /app mics_api python -m pytest tests/ -q
............................................................ (abridged)
56 passed, 7 warnings in 0.54s
```

`git diff --stat -- api/routers/toolkits.py` across this plan's three task commits: 6 net lines added (budget ≤15).

---
*Phase: 24-trigger-assignment-action-lists*
*Completed: 2026-07-27*

## Self-Check: PASSED

All created files and commit hashes verified present on disk / in git log.
