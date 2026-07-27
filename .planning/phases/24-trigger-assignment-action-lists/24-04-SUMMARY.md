---
phase: 24-trigger-assignment-action-lists
plan: 04
subsystem: pi-fda-runtime
tags: [autopilot, mics_task, trigger-assignments, fda-json-v2, validate-fda, separation-principle]

# Dependency graph
requires: ["24-01"]
provides:
  - "_build_trigger_action_list — the ONLY path from a trigger_assignments entry to a registered callback, built entirely from _build_action_callable"
  - "handler-free apply_trigger_assignments: (trigger_name, actions) only, idempotent on hot-reload via _fda_trigger_callbacks bookkeeping"
  - "detectedLick-equivalence test proving the reference case runs as a plain action list with zero lick-specific runtime code"
  - "tools/validate_fda.py single-sourced against autopilot.tasks.fda_vocabulary; trigger actions validated through the same _validate_actions_list the state loop uses"
affects: [24-02, 24-05, 24-06, 24-07, 24-08, phase-23-compute-primitives-variables, phase-25-detector-derived-view-keys]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Idempotent re-apply bookkeeping (_fda_trigger_callbacks dict) so hot-reload removes exactly what a previous apply_trigger_assignments call added, never stacking duplicate callbacks"
    - "Trigger callback is a thin composition over _build_action_callable — zero action-dispatch logic of its own, so new action types (Phase 23's compute) work inside a trigger with no Phase 24 rework"
    - "validate_fda.py's _validate_actions_list gained context_kind/allow_trigger_context params so ONE helper validates both state entry_actions and trigger actions, with per-context error labels and trigger-context-arg gating"

key-files:
  modified:
    - /home/ido/pi-mirror/autopilot/autopilot/tasks/mics_task.py
    - /home/ido/pi-mirror/tests/test_trigger_assignments.py
    - /home/ido/pi-mirror/tools/validate_fda.py
    - /home/ido/pi-mirror/tests/test_validate_fda.py

key-decisions:
  - "_resolve_renamed_trigger_refs (mics_task.py) is left in place as a harmless no-op for any orphaned legacy config.hardware_ref row, rather than deleted — it is called unconditionally from load_fda_from_json and deleting it would be an unrelated blast-radius increase for a method that simply never matches anything against the new actions-only shape. Its docstring was corrected to stop referencing the now-deleted _build_touch_detector_callback."
  - "Idempotent hot-reload tracked via a new self._fda_trigger_callbacks dict (trigger_name -> [callbacks appended by the last apply_trigger_assignments call]), diffed and removed at the top of every call, after the absent/empty backward-compat guard so that contract stays exactly as documented"
  - "tools/validate_fda.py's cmd_rename_hw_ref bulk-rename subcommand was left untouched (out of Task 3's scope) even though its TRIGGER_ASSIGNMENTS_SQL statement is now a no-op against current-format rows — logged in deferred-items.md rather than fixed, since it is a separate code path from validate() and not part of this plan's <files_modified>/interfaces scope"

requirements-completed: [TRIGA-01, TRIGA-02, TRIGA-06, TRIGA-10]

# Metrics
duration: ~50min
completed: 2026-07-27
---

# Phase 24 Plan 04: Trigger Assignment Action Lists — Handler-Free Runtime Summary

**Deleted the two hard-coded `touch_detector`/`digital_input` trigger handlers and replaced them with `_build_trigger_action_list`, which builds a trigger's callback purely from `_build_action_callable` — the same builder a state body uses — proving the separation principle (trigger mechanism vs. hardware-specific action list) end to end in tests, then single-sourced `tools/validate_fda.py`'s action vocabulary against the shared `fda_vocabulary` module.**

## Performance

- **Duration:** ~50 min
- **Tasks:** 3/3 completed
- **Files modified:** 4, all in `/home/ido/pi-mirror/` (a separate git repository from `mics-backend`; see Task Commits below)

## Accomplishments

### Task 1 — Handler-free `apply_trigger_assignments` + `_build_trigger_action_list`

- Rewrote `apply_trigger_assignments` (`mics_task.py`): the `if/elif` handler chain
  (`default`/`log_only`/`touch_detector`/`digital_input`) is gone. An assignment is now
  `(trigger_name, actions)`; a missing or empty `actions` list — including a legacy
  `handler`-only shape (task definition 185's shape) — raises `ValueError` naming the
  trigger, with no mention of "handler" in the message.
- Added `_build_trigger_action_list`: builds `action_callables = [self._build_action_callable(a) for a in actions]` (the SAME builder a state body uses — zero action-dispatch logic added here) and composes ONE callable that declares `level=None, tick=None` (satisfying `execute_trigger`'s `inspect.signature` dispatch, `task.py:285-296`), publishes them on the thread-local `self._trigger_ctx` (created lazily via the same `hasattr` guard Plan 01's `_resolve_arg` already uses) for the duration of the action list, and clears both in a `finally` regardless of whether an action raised.
- **Deleted `_build_touch_detector_callback` and `_build_digital_input_callback` entirely** (~86 lines) — including the buggy `changed[i]` per-channel indexing that never matched the real `MPR121.detect_change()` 2-tuple contract, and its test that only passed against a mock encoding the wrong contract.
- Added idempotent re-apply bookkeeping: `self._fda_trigger_callbacks` (trigger_name → list of callbacks appended by the last call) is diffed and removed at the top of every `apply_trigger_assignments` call — placed AFTER the absent/empty backward-compat guard, so hot-reload (`hot_update_fda` → `load_fda_from_json` → `apply_trigger_assignments` again) leaves exactly one callback per trigger, never a growing stack, while the "absent/empty leaves `self.triggers` untouched" contract stays exactly as documented.
- Corrected a dangling docstring reference: `_resolve_renamed_trigger_refs` (a legacy rename-map helper, left in place as a no-op for the new `actions`-only shape — see Decisions) referenced `_build_touch_detector_callback` by name; updated to explain it is now a legacy no-op.
- Wrote 9 new `test_apply_trigger_assignments_actions_*` tests, rewrote
  `test_apply_trigger_assignments_normalizes_scalar_trigger` (same name, body now driven by
  `actions` instead of `digital_input`/`config`), and added 3 `test_trigger_context_*`
  lifetime tests (thread-local cleared in a `finally` even when an action raises; no
  staleness leaking into a later state-body `view` action; `None` on a genuinely different
  thread that never ran a trigger) — 13 tests touched/added for Task 1 in total. Deleted the
  8 handler-specific tests the interfaces table marked for deletion; kept the 7
  `_build_transition_lambda` tests and the 2 absent/empty-contract tests completely
  unmodified.

### Task 2 — `detectedLick`-equivalence tests

- Added 4 `test_detect_lick_equivalence_*` tests driving the canonical action-list payload
  (`hardware` action calling `MPR121.detect_change()` with `output: ["pin_number", "level"]`,
  then an `if pin_number != None` guard around a `view` action templated
  `"LICKER{pin_number}"`) verbatim from the plan/`.claude/docs/trigger_action_lists.md`
  shape:
  - electrode 2 fires → `LICKER2.set(1, pi_timestamp="T")` exactly once; `LICKER0/1/3` never touched; `detect_change()` called exactly once; `flags["pin_number"].value == 2`, `flags["level"].value == 1` afterward.
  - the `(None, None)` no-change sentinel → no `LICKER*` tracker written at all, `detect_change()` still called once.
  - electrode index varying 0→3 across four successive fires → each fire writes only its own `LICKER{n}` (per-invocation key resolution, not cached at build time).
  - no tick stashed → `.set(1)` called with no `pi_timestamp` kwarg at all (the implicit-timestamp path, not a JSON field).
  - There is deliberately no assertion in these tests about handlers, MPR121 branches, or touch-specific code paths — because none exist any more. That absence is the acceptance criterion.
- Used a lightweight `_FlagTracker` stub (not a `Tracker` subclass, since flags are never `isinstance`-checked) for `pin_number`/`level` to avoid `Tracker.set()`'s `@log_action` decorator, which requires a working `event_dispatcher` the test fixture doesn't provide — and `MagicMock(spec=Tracker)` for the `LICKER0..3` view targets (matching the file's existing convention), since the `view` action's runtime `isinstance(target, Tracker)` guard requires that.

### Task 3 — Single-sourced `tools/validate_fda.py` against `fda_vocabulary`

- Replaced the locally-declared `VALID_HANDLERS`/`VALID_SPECIALS`/`VALID_ACTIONS` constants
  with `from autopilot.tasks.fda_vocabulary import VALID_ACTION_TYPES as VALID_ACTIONS, VALID_SPECIALS, VALID_TRIGGER_CONTEXT_KEYS` — the same module `mics_task.py` imports, so the two Pi-side copies of the action vocabulary cannot drift. `VALID_HANDLERS` is deleted outright (not imported): there is no handler vocabulary any more.
- Rewrote the `trigger_assignments` validation block: `trigger_name` must be a non-empty string (and, if non-empty, a known `HARDWARE` pin id); `actions` must be a non-empty list; every action then runs through the SAME `_validate_actions_list` helper the state loop uses, with a new `context_kind="trigger"` param that changes only the error-message label (`[trigger '...']` vs `[state '...']`) and `allow_trigger_context=True`, which is the only thing that makes a `{"trigger": "level"|"tick"}` arg legal — validated everywhere else (state bodies) as an error.
- Added a top-level `variables` section validator: must be a dict of `str -> dict`; a name colliding with an existing `FLAGS` entry is an error; valid variable names are folded into the same `flag_keys` set used for `flag` refs, `output` targets, and `view` `key_template` tokens throughout the file (since variables and flags share one namespace, `self.flags`, at runtime per Plan 01).
- Added `output` validation (`hardware`/`timer`/`method` actions): must be a string or list of strings, every name a declared variable/flag.
- Added `view`-action validation: non-empty `key_template`; every `{token}` in it must name a declared variable/flag; its `value` field runs through the same arg-ref validator as any other action's args/kwargs (including the new trigger-context gating).
- Extended `tests/test_validate_fda.py`: deleted the 2 handler-enum tests
  (`test_deprecated_trigger_assignment_hardware_ref_is_warning`,
  `test_unknown_trigger_assignment_hardware_ref_is_error`); added 9 new tests covering a
  valid trigger action list, an unknown action type inside a trigger (error naming the
  trigger), an empty `trigger_name`, a missing `actions` key, an undeclared `output` slot, an
  undeclared `key_template` token, an unknown `{"trigger": "bogus"}` key, and both sides of
  the trigger-context gate (`{"trigger": "level"}` valid inside a trigger action list,
  rejected inside a state body).

## Separation-Principle Verification (phase gate)

All agent-runnable, re-run at the end of this session:

```
$ python3 -m py_compile autopilot/autopilot/tasks/mics_task.py tools/validate_fda.py \
    tests/test_trigger_assignments.py tests/test_validate_fda.py
COMPILE_OK (exit 0, all 4 files)

$ grep -c "touch_detector\|digital_input" autopilot/autopilot/tasks/mics_task.py
0

$ grep -c "Touch_Detector" autopilot/autopilot/tasks/mics_task.py
4   # lines 17 (import), 250/257/261 (check_for_detectors docstring/body) — untouched by this plan

$ grep -c "VALID_HANDLERS" tools/validate_fda.py
0

$ grep -c "^def test_build_transition_lambda" tests/test_trigger_assignments.py
7   # unmodified, as required

$ grep -c "^def test_detect_lick_equivalence" tests/test_trigger_assignments.py
4   # >= 3 required
```

**i2c.py / task.py byte-identical (verified via SSH diff, per the substitution instruction —
the plan's own `git -C /home/ido/pi-mirror status --porcelain` verify line was NOT run, since
git in `/home/ido/pi-mirror` is forbidden):**

```
$ diff <(ssh -i ~/.ssh/pi_mics pi@132.77.72.28 'cat ~/Apps/mice_interactive_home_cage/autopilot/autopilot/hardware/i2c.py') /home/ido/pi-mirror/autopilot/autopilot/hardware/i2c.py && echo I2C_IDENTICAL
I2C_IDENTICAL

$ diff <(ssh -i ~/.ssh/pi_mics pi@132.77.72.28 'cat ~/Apps/mice_interactive_home_cage/autopilot/autopilot/tasks/task.py') /home/ido/pi-mirror/autopilot/autopilot/tasks/task.py && echo TASK_PY_IDENTICAL
TASK_PY_IDENTICAL
```

**Net line count removed from `mics_task.py`:** the `apply_trigger_assignments` +
`_build_touch_detector_callback` + `_build_digital_input_callback` block shrank from 139
lines to the new `apply_trigger_assignments` + `_build_trigger_action_list` block at 106
lines (**-33 lines**); the `_resolve_renamed_trigger_refs` docstring correction added 2
lines. **Net: -31 lines removed** from `mics_task.py` in this plan, on top of Plan 01's
already-landed additions.

## Task Commits

This plan's `files_modified` are entirely under `/home/ido/pi-mirror/`, a separate git
repository from `mics-backend`, per the project's hard rule (agent never commits in
`pi-mirror`; the user reviews and commits mirror changes at their discretion). No per-task
commits were made there — consistent with how 24-01 through 24-03 were handled. Only this
plan's metadata (this SUMMARY, STATE.md, ROADMAP.md) is committed in `mics-backend`, as a
single commit after this summary.

1. **Task 1** — handler-free `apply_trigger_assignments` + `_build_trigger_action_list`;
   both handler builders deleted. Verified via `py_compile` and the grep gates above.
2. **Task 2** — `detectedLick`-equivalence tests (4, named `test_detect_lick_equivalence_*`).
   Verified via `py_compile` and grep for the canonical payload markers.
3. **Task 3** — `tools/validate_fda.py` single-sourced against `fda_vocabulary`; trigger
   `actions`/`view`/`output`/trigger-context validation added; `VALID_HANDLERS` deleted.
   Verified via `py_compile` and grep gates.

## Pi files edited this session

/home/ido/pi-mirror/autopilot/autopilot/tasks/mics_task.py
/home/ido/pi-mirror/tests/test_trigger_assignments.py
/home/ido/pi-mirror/tools/validate_fda.py
/home/ido/pi-mirror/tests/test_validate_fda.py

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Dangling docstring reference to a deleted method**
- **Found during:** Task 1, immediately after deleting `_build_touch_detector_callback`.
- **Issue:** `_resolve_renamed_trigger_refs`'s docstring referenced
  `_build_touch_detector_callback` by name ("Prevents `_build_touch_detector_callback` from
  raising KeyError..."), which is now deleted, and the method's whole premise
  (`assignment.get("config", {}).get("hardware_ref", "")`) is now a permanent no-op since
  `config` doesn't exist on current-format `trigger_assignments` entries.
- **Fix:** Corrected the docstring to describe the method as a legacy no-op kept only for
  any stray pre-Phase-24 row still carrying `config.hardware_ref`; left the method's body
  and its single call site in `load_fda_from_json` untouched (harmless — it will simply
  never match against the new shape, and deleting it was not requested by the plan and
  would have been an unrelated blast-radius increase).
- **Files modified:** `/home/ido/pi-mirror/autopilot/autopilot/tasks/mics_task.py`
- **Verification:** `py_compile` clean; grep confirms no remaining lowercase
  `touch_detector`/`digital_input` identifier anywhere in the file.

**2. [Substitution per orchestrator instruction] i2c.py verification method**
- **Found during:** start of session.
- **Issue:** The plan's own `<verify>` step 5 specifies
  `git -C /home/ido/pi-mirror status --porcelain autopilot/autopilot/hardware/i2c.py
  autopilot/autopilot/tasks/task.py`, but running git in `/home/ido/pi-mirror` is forbidden
  by this session's binding orchestrator instructions (which override the plan file).
- **Fix:** Used the SSH-diff substitution specified by the orchestrator instead (see
  Separation-Principle Verification above), for both `i2c.py` and `task.py`. Both confirmed
  byte-identical to the live Pi.
- **Files modified:** none (verification-only).

**Total deviations:** 2 (1 auto-fixed per Rule 1, 1 verification-method substitution per
explicit binding instruction). No scope creep: both are corrective/verification-only, not
new functionality.

### Deferred (out of scope, logged not fixed)

**`tools/validate_fda.py`'s `cmd_rename_hw_ref` bulk-rename subcommand still targets the
legacy `config.hardware_ref` shape** — its `TRIGGER_ASSIGNMENTS_SQL` statement is now a
silent no-op against current-format `trigger_assignments` rows (they have no `config` key).
This is a separate code path from `validate()`, outside Task 3's `<files_modified>`/interfaces
scope. Logged in
`.planning/phases/24-trigger-assignment-action-lists/deferred-items.md` with a suggested
fix for a future plan (extend the entry_actions-style SQL to also walk
`trigger_assignments[*].actions`).

## Issues Encountered

- **`autopilot` is not importable on this dev host** (confirmed by 24-01 and reconfirmed
  here: `ModuleNotFoundError: No module named 'npyscreen'`), so
  `tests/test_trigger_assignments.py` and `tests/test_validate_fda.py` could not be executed
  by the agent this session — both are marked **USER-RUN** per the plan's own `<verify>`
  blocks and `24-VALIDATION.md`. All new/rewritten tests were verified by (a) `py_compile`
  (syntax-clean) and (b) careful manual tracing of each assertion against the actual
  implementation (documented inline above and in each test's docstring). Two USER-RUN
  commands to get real pass/fail signal:
  ```
  cd ~/pi-mirror && python3 -m pytest tests/test_trigger_assignments.py -q
  cd ~/pi-mirror && python3 -m pytest tests/test_validate_fda.py -q
  ```

## User Setup Required

None — no external service configuration required. As with Plans 01–03, this plan's
Pi-mirror changes are **uncommitted** in `/home/ido/pi-mirror` (agent never commits there
per hard rule). Recommended before Plan 05/06/07 continue:

1. Review the diffs in `/home/ido/pi-mirror` and commit at your discretion.
2. Run the two USER-RUN pytest commands above for real pass/fail signal on all new tests
   (17 tests touched/added in `test_trigger_assignments.py` this session: 9 new
   `actions_*` + 1 rewritten `normalizes_scalar_trigger` + 3 new `trigger_context_*`
   lifetime + 4 new `detect_lick_equivalence_*`; 9 new tests in `test_validate_fda.py`).
3. **Do not rig-test the lick path (`TOUCH_INT`) between this plan and Plan 06** — see the
   plan's own `⚠ DO NOT RIG-TEST` note: `learning_cage.__init__` still sets
   `self.triggers['TOUCH_INT'] = [self.detectedLick]` until Plan 06 unregisters it, and
   `MPR121.detect_change()` consumes the edge unconditionally on first call, so whichever
   callback fires first (still `detectedLick`, appended first) silently starves the new
   action-list callback of the edge. A manual early smoke signal (per the plan) is a
   distinct-event test action that does NOT call `detect_change()`, e.g. an LED `hardware`
   action reading `{"trigger": "level"}`.

## Next Phase Readiness

Plan 05 (React `ActionEditor` hosted inside `TriggerAssignmentPanel`, per its own SUMMARY
already landed — `24-05-SUMMARY.md` exists) and Plan 06 (unregister
`learning_cage`'s `TOUCH_INT` → `detectedLick`, capability-based `check_for_detectors`,
TRIGA-12) can now build on: a fully handler-free `apply_trigger_assignments`, the
`_build_trigger_action_list` mechanism proven against the canonical lick payload, and a
`validate_fda.py` that will 422/error on any legacy `handler`-only stored definition (task
definition 185's shape) rather than silently accepting it.

No blockers. Two open items for the user (both listed above): run the USER-RUN pytest
suites, and avoid rig-testing `TOUCH_INT` until Plan 06 lands.

---
*Phase: 24-trigger-assignment-action-lists*
*Completed: 2026-07-27*

## Self-Check: PASSED

All 6 files confirmed present on disk (4 in `/home/ido/pi-mirror/`, plus this SUMMARY.md and
`deferred-items.md` in `mics-backend`). No mics-backend task commits exist to verify
(Pi-mirror is a separate, non-committable repo per hard rule; see "Task Commits" above). All
grep/py_compile gates re-run and confirmed passing at time of writing (see
"Separation-Principle Verification" above).
