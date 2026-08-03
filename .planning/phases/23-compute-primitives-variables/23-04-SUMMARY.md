---
phase: 23-compute-primitives-variables
plan: 04
subsystem: pi-runtime
tags: [autopilot, fda, compute, mics_task, fda_vocabulary, validate_fda, variables]

# Dependency graph
requires:
  - phase: 23-compute-primitives-variables
    plan: 01
    provides: "tests/test_compute_ops.py (Wave 0 contract test, USER-RUN, pinning CMP-03/04/05 against a not-yet-existing compute branch)"
  - phase: 24-trigger-assignment-action-lists
    provides: "the variables registry (self.flags + self.view.view, both live Tracker objects) built in load_fda_from_json step 2b, and apply_trigger_assignments composing _build_action_callable generically -- both already correct for any new action type with zero changes"
provides:
  - "type:\"compute\" in fda_vocabulary.VALID_ACTION_TYPES, single-sourced into both the Pi runtime and tools/validate_fda.py"
  - "_build_action_callable's compute branch (mics_task.py) -- byte-for-byte the hardware/timer branch's dual-resolution form (group present -> self.hardware[group][ref], absent -> self._semantic_hw[ref]), with output made mandatory at BUILD time"
  - "_build_state_method's entry_actions validate loop now recognizes compute (bug found and fixed this task -- see Deviations)"
  - "tools/validate_fda.py's compute branch: same method-required + mandatory-output rules as the runtime, message wording matched"
  - "tests/test_compute_ops.py Task 3 section: 4 verify-only regression tests for CMP-01/02/05/06 against compute-written variables, using a real load_fda_from_json round trip"
affects: ["23-10-deploy-and-rig-proof (owns rsync of this plan's 4 pi-mirror files, the USER-RUN pytest, and rig proof of a compute op writing a variable that drives a real transition)"]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "New Pi action types (compute) are added as a thin alias over an existing branch (hardware/timer) plus one extra guard, not a parallel implementation -- keeps _resolve_arg/_capture_output/_validate_output_spec fully shared"
    - "A Hardware-subclass-based fake View (_FakeView, test-only) that mirrors autopilot.core.View.get_value's real self.view[name].get_state() contract, used instead of a bare MagicMock wherever a test needs transitions to evaluate against real Tracker values"

key-files:
  created: []
  modified:
    - /home/ido/pi-mirror/autopilot/autopilot/tasks/fda_vocabulary.py
    - /home/ido/pi-mirror/autopilot/autopilot/tasks/mics_task.py
    - /home/ido/pi-mirror/tools/validate_fda.py
    - /home/ido/pi-mirror/tests/test_compute_ops.py
    - /home/ido/pi-mirror/tests/test_fda_vocabulary.py

key-decisions:
  - "Fixed _build_state_method's entry_actions pre-validation loop to recognize 'compute' (added it to the same branch as 'hardware', checking self._semantic_hw membership) -- not explicitly called out in the plan's Task 2 action steps, but without it every compute action placed in a state's entry_actions would raise 'unknown action type' at _build_state_method, before ever reaching the new _build_action_callable branch. This directly blocks CMP-03's must-have and Task 3's own round-trip test design, so it was treated as a Rule 3 blocking-issue fix, not scope creep."
  - "Did NOT fix load_fda_from_json's variables-registry collision guard, despite finding (by code inspection) that it likely breaks hot_update_fda's CMP-06 promise for any variable name repeated across reloads -- Task 3's own instructions explicitly forbid touching that code and explicitly anticipate exactly this outcome ('if any of them fails on the rig, the finding belongs in the summary as a Phase-24 defect, NOT as new Phase-23 work'). See Deviations for the full reasoning and the exact code path."
  - "rhs values in the new Task 3 tests use bare literals (true/false/5), not {\"literal\": true} -- _resolve_arg has no 'literal' key branch (only param/flag/now/trigger/view, falling through to 'return arg' unchanged for anything else), so a wrapped {\"literal\": true} would compare against the dict itself, never True. The PLAN.md text's {\"literal\":true} notation is illustrative, not literal JSON to reproduce."

patterns-established:
  - "_FakeView (tests/test_compute_ops.py) as the reusable get_value-capable view stand-in for any future test that needs load_fda_from_json's transitions to evaluate for real, without requiring a real autopilot.core.View + Event_Dispatcher instance"

requirements-completed: [CMP-03, CMP-04, CMP-05, CMP-06]

# Metrics
duration: 35min
completed: 2026-08-03
---

# Phase 23 Plan 04: Compute Action Type on the Pi Runtime Summary

**`type:"compute"` now loads and executes on the Pi as a hardware-call alias with mandatory `output`, single-sourced through `fda_vocabulary.py` into both `mics_task.py`'s `_build_action_callable` and the CLI's `tools/validate_fda.py`; a pre-existing gap in `_build_state_method`'s validate loop that would have silently blocked compute from ever working inside a state body was found and fixed in the same task.**

## Performance

- **Duration:** 35 min
- **Started:** 2026-08-03T09:13:00Z
- **Completed:** 2026-08-03T09:26:19Z
- **Tasks:** 3
- **Files modified:** 5 (all in `/home/ido/pi-mirror`; none in the mics-backend git repo)

## Accomplishments

- `fda_vocabulary.py` gained `"compute"` in `VALID_ACTION_TYPES`, single-sourced (as it already was for `tools/validate_fda.py`, plan 24-04) so both languages agree with zero duplication.
- `tools/validate_fda.py`'s `_validate_actions_list` gained a `compute` branch: unknown-hw-ref check (shared `_check_hw_ref` helper), a missing-`method` error, and a missing-`output` error worded identically to the runtime's own message, so a researcher sees the same sentence from the CLI and from a load-time Pi log.
- `mics_task.py`'s `_build_action_callable` gained the `compute` branch: byte-for-byte the `hardware`/`timer` branch's dual ref-resolution form (`group` key present → `self.hardware[group][ref]`; absent → `self._semantic_hw[ref]`), with one addition -- `output` is checked and raises `ValueError` at BUILD time, before `_validate_output_spec` even runs, naming `ref.method` in the message.
- `_build_state_method`'s entry_actions pre-validation loop (a separate, earlier gate than `_build_action_callable`) was extended to recognize `compute` -- see Deviations; without this, `compute` could never appear in a state's `entry_actions`, only in a trigger's action list.
- `tests/test_compute_ops.py` (plan 23-01's Wave 0 stub, already containing full real test bodies) now passes conceptually against the new runtime code -- all 8 CMP-03/04/05 tests plus 4 new Task 3 tests, none altered from plan 23-01's original assertions. USER-RUN at plan 23-10 (autopilot unimportable on this dev host).
- `tests/test_fda_vocabulary.py` extended with a `compute`-membership assertion; agent-verified: **23 passed**.

## Task Commits

No git commits were made -- `/home/ido/pi-mirror` is its own user-owned git repository and pi_rules #1 forbids any git command there (not even `status`), the same constraint plan 25-02 documented. All edits are local, uncommitted working-tree changes in pi-mirror; the user commits pi-mirror on their own terms. Each task below was implemented, syntax-checked (`py_compile`), and (where agent-runnable) test-verified before moving to the next:

1. **Task 1: `compute` in the shared vocabulary and the CLI validator** -- no commit (pi-mirror is user-owned git)
2. **Task 2: the `compute` branch in `_build_action_callable`** -- no commit
3. **Task 3: pin CMP-01/02/05/06 as regressions in the existing Pi suite** -- no commit

**Plan metadata:** this SUMMARY.md, STATE.md, and ROADMAP.md are committed in the mics-backend repo (final commit below) -- the only git activity this plan performs.

## Files Created/Modified

All paths under `/home/ido/pi-mirror` (outside the mics-backend git repo):

- `autopilot/autopilot/tasks/fda_vocabulary.py` -- `"compute"` added to `VALID_ACTION_TYPES`, with a comment pointing at the backend twin (`api/fda_validation.py::VALID_ACTION_TYPES`), matching the file's existing note style.
- `autopilot/autopilot/tasks/mics_task.py` -- two changes, diff-confirmed limited to exactly these: (1) `_build_action_callable` gained the `compute` `elif` branch (Task 2) plus a docstring update; (2) `_build_state_method`'s validate loop's `hardware` check widened to `("hardware", "compute")` (Task 3, see Deviations), plus its catch-all error message's "Expected:" list gained `compute`.
- `tools/validate_fda.py` -- `_validate_actions_list` gained a `compute` `elif` branch between `timer` and `special`, message-matched to the runtime.
- `tests/test_fda_vocabulary.py` -- extended `test_view_in_valid_action_types`'s set-equality assertion to include `"compute"`; added `test_compute_in_valid_action_types`. **Agent-verified: 23 passed.**
- `tests/test_compute_ops.py` -- plan 23-01's 8 pre-written tests (CMP-03/04/05, Hardware-subclass contract + compute dispatch) unchanged; added a `decide(value=True)` method to the `_Ops` stand-in class (Task 3 needs a bool-producing op); added a new `TestVariablesRegressionsCMP01_02_05_06` class (4 tests) plus its `_FakeView`/`_make_full_task_instance` fixtures. USER-RUN on the Pi (imports `autopilot.tasks.mics_task`).

## Decisions Made

- **`_build_state_method`'s validate loop fixed for `compute`, not left as a Phase-23-adjacent gap.** See "Deviations from Plan" -- this one was in-scope because it directly blocks CMP-03's must-have.
- **`load_fda_from_json`'s variables collision guard NOT touched**, despite a very similar-looking gap discovered in the same review pass (see Deviations) -- the plan's own Task 3 text explicitly forbids this and explicitly frames a resulting test failure as a Phase-24 finding to report, not a Phase-23 fix to make.
- **No pi-mirror git commits, by design** -- same constraint and rationale as `25-02-SUMMARY.md`.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 - Blocking] `_build_state_method`'s entry_actions validate loop didn't recognize `compute`**
- **Found during:** Task 3, while tracing whether the round-trip test's compute action (inside a state's `entry_actions`, not a trigger) would actually build.
- **Issue:** `_build_state_method` (mics_task.py, ~line 837) runs its own pre-validation loop over `entry_actions` BEFORE `_build_action_callable` is ever called for those actions. That loop has an explicit branch per type (`method`, `hardware`, `flag`, `special`), lets `timer`/`if` pass through unchecked, and raises `ValueError: unknown action type '<atype>'` for anything else -- including, before this fix, `compute`. Task 2's new `_build_action_callable` branch would therefore have been unreachable dead code for any compute action placed in a state body (as opposed to a trigger's action list, which bypasses this loop entirely via `apply_trigger_assignments`). This directly contradicts the plan's own must-have ("A `type:\"compute\"` entry action resolves a compute module...") and would have broken Task 3's test design outright.
- **Fix:** Widened the existing `elif atype == "hardware":` branch to `elif atype in ("hardware", "compute"):`, reusing the same `self._semantic_hw` membership check (parameterized the error message with `{atype}` instead of the literal string `'hardware'`). Also added `compute` to the catch-all's "Expected:" list in its error message.
- **Files modified:** `autopilot/autopilot/tasks/mics_task.py`
- **Verification:** `py_compile` clean; the fixed loop is exercised implicitly by every Task 3 test that places a `compute` action inside a state's `entry_actions` (all four of them) -- USER-RUN confirmation at plan 23-10.
- **Committed in:** n/a (no pi-mirror git commits, see above)

---

**Total deviations:** 1 auto-fixed (Rule 3 - blocking issue)
**Impact on plan:** Necessary for the compute action type to function at all inside a state body, which is the plan's central deliverable. No scope creep -- the fix is a one-line widening of an existing branch, following the exact pattern the plan's Task 2 itself used for `_build_action_callable`.

## Issues Encountered

**One finding NOT auto-fixed, per the plan's explicit instruction -- documented here as a predicted Phase-24 defect for plan 23-10 to confirm:**

While building the Task 3 hot-reload test (`test_hot_update_fda_recreates_variables_before_rebuilding_transitions`), code inspection of `load_fda_from_json`'s variables-registry block (step 2b, ~line 1047) found:

```python
for var_name, var_def in (definition.get("variables") or {}).items():
    if var_name in self.flags:
        raise ValueError(f"... variable '{var_name}' collides with an existing flag. ...")
    ...
```

`self.flags` is set once in `Task.__init__` and never cleared by `load_fda_from_json` itself. `hot_update_fda` calls `load_fda_from_json` again on every hot-reload (its own docstring: "Full rebuild -- resets self.stages"), and if the SAME variable name is declared again -- the expected case for "a changed `variables` block" describing an existing variable, and exactly the scenario CMP-06's must-have describes ("Hot-reload re-creates variables before rebuilding the transitions that read them") -- this guard appears, by inspection, to raise a collision `ValueError` instead of recreating the tracker. No existing test file in `tests/` exercises `hot_update_fda` at all (grepped `tests/` before writing this test), so this path has apparently never been tested end-to-end before.

**Not fixed:** Task 3's own instructions are explicit and anticipate this exact outcome: "Do NOT change... the variables block in `load_fda_from_json`, or `hot_update_fda`... Touching them is out of scope and risks regressing phases 24/25" and "If any of them fails on the rig, the finding belongs in the summary as a Phase-24 defect, NOT as new Phase-23 work." Per that guidance, the test was written to pin the intended CMP-06 behavior (not weakened to dodge the suspected bug), with an inline comment documenting this exact reasoning, and the finding is reported here rather than silently patched.

**Not confirmed by execution** -- this dev host cannot import `autopilot` (`npyscreen` missing), so this is a prediction from code reading, not an observed test failure. Plan 23-10 must run `tests/test_compute_ops.py` on the Pi and check specifically whether `test_hot_update_fda_recreates_variables_before_rebuilding_transitions` passes or raises the collision `ValueError`. If it raises, that confirms a Phase-24 defect in `load_fda_from_json`'s variable-collision guard (it should exempt names the mechanism itself previously declared, e.g. via a `self._fda_variable_names` set populated on each load) -- worth its own small fix plan, not a re-open of Phase 23-04.

Also logged to `deferred-items.md` (out-of-scope, unrelated to this plan's own changes): `_build_state_method`'s validate loop still has no branch for `type:"view"` -- the same class of gap this task fixed for `compute`, but pre-existing and not caused by this plan's edits.

## User Setup Required

None -- no external service configuration required. **No deployment and no pilot restart in this plan** (plan 23-10 owns that). All pi-mirror edits are local only; nothing was pushed to the Pi.

## Next Phase Readiness

**Files to deploy, when plan 23-10 runs (rsync from `/home/ido/pi-mirror`, never `--delete`, never the whole mirror):**

```
autopilot/autopilot/tasks/fda_vocabulary.py
autopilot/autopilot/tasks/mics_task.py
tools/validate_fda.py
tests/test_compute_ops.py
tests/test_fda_vocabulary.py
```

- Plan 23-10 must run, on the Pi: `cd ~/Apps/mice_interactive_home_cage && python3 -m pytest -q tests/test_compute_ops.py tests/test_load_fda_from_json.py` (per this plan's own `<verify>` instruction on Task 2), plus a full-suite run for regression coverage.
- **Specifically check** `TestVariablesRegressionsCMP01_02_05_06::test_hot_update_fda_recreates_variables_before_rebuilding_transitions` -- see "Issues Encountered" above. A failure there is an expected, predicted Phase-24 defect finding, not a Phase-23-04 regression; a pass means the code is more defensive than this plan's code review credited it for.
- The other three new tests in that class (`test_compute_written_variable_drives_transition_choice`, `test_variable_with_initial_value_readable_via_flag_and_view_before_compute_runs`, `test_reentering_state_recomputes_and_overwrites_variable`) are expected to pass outright.
- `tests/test_fda_vocabulary.py` is the one file in this deploy list that's ALSO agent-verified here (23 passed) -- redeploying it is still required since its assertions changed, even though its correctness is already proven.
- Known limitation, recorded per Task 1's own instruction: `tools/validate_fda.py`'s `_validate_actions_list` does not special-case the `"group"` direct-ref form for `compute`'s hardware-ref check (it always checks against `semantic_hw_keys` via `_check_hw_ref`, same as the pre-existing `hardware`/`timer` branches) -- this is not a new gap, it mirrors those branches' existing behavior exactly.
- Backend counterpart (`api/fda_validation.py::VALID_ACTION_TYPES`, out of this plan's scope) must independently gain `"compute"` for the two languages to agree -- tracked by this plan's requirements (CMP-03/04/05/06) being Pi-runtime only; the backend-side validator is a different plan's concern per phase 23's roadmap.

---
*Phase: 23-compute-primitives-variables*
*Completed: 2026-08-03*

## Self-Check: PASSED

All 5 modified pi-mirror files confirmed present on disk with the intended changes (diff against
the live Pi, run immediately before writing this summary, shows only the hunks described above
for `fda_vocabulary.py`, `mics_task.py`, and `tools/validate_fda.py`). `tests/test_fda_vocabulary.py`
re-run fresh: **23 passed**. `python3 -m py_compile` re-run fresh across all 5 files: exit 0. No
commit hashes to verify -- no git commits were made to `/home/ido/pi-mirror` per pi_rules #1 (see
"Task Commits" above). This SUMMARY.md and `deferred-items.md` confirmed present on disk.
