---
phase: 31-mics-core-modern-pi-platform-bookworm-64-bit-python-3-11-lgpio-unattended-boot
plan: 02
subsystem: testing
tags: [dependency-cleanup, hdf5, pytables, port-calibration, pyside2, npyscreen, pytest, ci-gate]

# Dependency graph
requires:
  - phase: 31-01
    provides: "Dev-host pytest instrument, tools/pytest_delta.py baseline-relative gate, 31-PYTEST-BASELINE.json (179 failing), tests/fakes/fake_pigpio.py"
provides:
  - "HDF5/TrialData and port-calibration code paths deleted from task.py/pilot.py/gpio.py/prefs.py"
  - "Setup wizard (npyscreen/PySide2/pyqtgraph GUI toolkit chain, autopilot/autopilot/setup/, autopilot/setup.py) deleted whole"
  - "tests/test_shed_absences.py — permanent static gate, 7 tests, banning reappearance of both subsystems"
  - "tools/rebaseline_pytest.py — the sole sanctioned baseline-rewrite path, refuses unaccepted new failures"
  - "31-PYTEST-BASELINE.json re-baselined: 179/208 -> 187/253, prior capture preserved under superseded"
affects: [31-03, 31-04, 31-C1, 31-C2, 31-C3, 31-C4]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Static shed-absence gate (tests/test_shed_absences.py): tree-wide bans for strings verified to have zero legitimate uses outside the deleted subsystem, scoped bans (specific files only) for strings with live unrelated consumers elsewhere in the tree"
    - "Baseline rewrite requires a typed reason: tools/rebaseline_pytest.py refuses to write on any new failing node id unless named via --allow-new with --reason, recorded in accepted_new_failures"

key-files:
  created:
    - /home/ido/mics_core/tests/test_shed_absences.py
    - /home/ido/mics_core/tools/rebaseline_pytest.py
    - /home/ido/mics_core/tests/test_rebaseline_pytest.py
  modified:
    - /home/ido/mics_core/autopilot/autopilot/tasks/task.py
    - /home/ido/mics_core/autopilot/autopilot/core/pilot.py
    - /home/ido/mics_core/autopilot/autopilot/hardware/gpio.py
    - /home/ido/mics_core/autopilot/autopilot/prefs.py
    - /home/ido/mics_core/autopilot/autopilot/__init__.py
    - /home/ido/mics_core/autopilot/autopilot/external/__init__.py
    - /home/ido/mics_core/conftest.py
    - /home/ido/mics_core/tools/tree_integrity/final_checks.py
    - /home/ido/mics-backend/.planning/phases/31-mics-core-modern-pi-platform-bookworm-64-bit-python-3-11-lgpio-unattended-boot/31-PYTEST-BASELINE.json
  deleted:
    - /home/ido/mics_core/autopilot/autopilot/setup/ (7 files)
    - /home/ido/mics_core/autopilot/setup.py

key-decisions:
  - "scipy/blosc are NOT tree-wide-unreachable as CONTEXT.md/the plan claimed — scipy is independently used by hardware/i2c.py, stim/sound/sounds.py, transform/geometry.py, transform/timeseries.py (none touched by this plan); blosc by networking/message.py (protected Message class), networking/__init__.py and networking/station.py for numpy-array wire compression. Banned only within the four HDF5/calibration shed files, not tree-wide."
  - "pilot/prefs.json's audio keys (JACKDSTRING, ALSA_NPERIODS, NCHANNELS, OUTCHANNELS, FS) were NOT deleted, contradicting the plan's own <behavior> ban list — external/__init__.py:start_jackd() and stim/sound/jackclient.py are live (AUDIOSERVER-gated) readers of them, in files this plan does not touch. The plan's own conditional instruction ('remove ... only if grep -rn shows no live consumer') resolves to keep once that grep is actually run."
  - "conftest.py's collect_ignore keeps test_log_action_values.py (not un-ignored as the plan's <behavior> asked) — empirically a genuine COLLECTION ERROR via Tracker -> logging_utils -> Event_Dispatcher:3's unconditional import pigpio, which aborts pytest's whole-tree collection. test_compute_ops.py was safely un-ignored (collects, 8/12 individual failures, no collection error)."
  - "The 8 newly-visible test_compute_ops.py failures were accepted into the re-baselined JSON via --allow-new/--reason after individually verifying (--tb=short) each fails on the identical ModuleNotFoundError: No module named 'pigpio' as the other 179 baseline failures — pre-existing debt, not damage this plan caused."
  - "l_cal_result and calibration_curve (pilot.py) were deleted beyond the plan's literal <verified_deletion_map>, which named only calibrate_port/compute_calibration — calibration_curve was never called from anywhere and was the actual reason pandas/scipy.stats.linregress remained top-level imports in pilot.py, directly contradicting the plan's own dependency-floor claim."

requirements-completed: [PLAT-01]

# Metrics
duration: ~30min
completed: 2026-08-19
---

# Phase 31 Plan 02: Delete the HDF5/TrialData, Port-Calibration and Setup-Wizard Subsystems Summary

**Deleted HDF5/TrialData, port-calibration, and the npyscreen/PySide2/pyqtgraph setup-wizard from `~/mics_core`'s pilot import path, added a permanent static absence gate (`tests/test_shed_absences.py`) and a baseline-rewrite tool that refuses unaccepted new failures (`tools/rebaseline_pytest.py`), and re-baselined the pytest suite (179/208 → 187/253, 8 newly-visible pre-existing pigpio failures accepted with a typed reason, 0 fixed as expected).**

## Performance

- **Duration:** ~30 min
- **Started:** ~2026-08-19T06:50Z (approx, continuing directly from plan 01)
- **Completed:** 2026-08-19T07:19Z
- **Tasks:** 3 completed
- **Files modified:** 17 (3 created in mics_core, 9 modified in mics_core, 8 files deleted under 2 paths, 1 modified in mics-backend)

## Accomplishments

- `task.py`/`pilot.py`/`gpio.py`/`prefs.py`: deleted `import tables`, both `TrialData` class definitions, the `NaturalNameWarning` filter, the write-only `hasattr(self.task, 'TrialData')` branch, `Solenoid.dur_from_vol` + its `vol`-driven `__init__` branch, and the whole port-calibration subsystem (`l_cal_port`/`calibrate_port`/`l_cal_result`/`calibration_curve` + their `CALIBRATE_PORT`/`CALIBRATE_RESULT` dispatch entries) — `calibration_curve` was never called from anywhere and is why `pandas`/`scipy.stats.linregress` were still top-level imports in `pilot.py`, a finding beyond the plan's own line-numbered audit
- `autopilot/autopilot/setup/` (7 files, 1,290 lines) and `autopilot/setup.py` (102 lines) deleted whole; `autopilot/__init__.py`'s `from autopilot.setup import setup_autopilot` removed; four prose references reworded (argparse help, two docstrings, one `ImportError` message)
- `tests/test_shed_absences.py`: 7 tests, tree-wide bans for strings verified to have zero legitimate uses outside the shed, scoped bans (four specific files) for `scipy`/`blosc` which have live unrelated consumers elsewhere, two dynamic import-with-blocked-modules proofs (`tables`; `npyscreen`/`PySide2`/`shiboken2`/`pyqtgraph`), one `f2_prefs` behavior-preservation test
- `tools/rebaseline_pytest.py` (TDD'd, 9/9 unit tests green): the only sanctioned way to rewrite a baseline — refuses to write on any new failing node id without an explicit `--allow-new NODE_ID --reason TEXT`, preserves the prior capture verbatim under `superseded` (including any chain it already carried), refuses to run at all on a collection error, `--check-only` for read-only verification
- `31-PYTEST-BASELINE.json` re-baselined for real: 179 failed/208 passed → 187 failed/253 passed. The 8 new node ids (all in `tests/test_compute_ops.py`, un-`collect_ignore`d this plan) were individually verified with `--tb=short` to fail on the identical `ModuleNotFoundError: No module named 'pigpio'` as the other 179 — accepted with a typed reason, not silently promoted to "expected"
- `tools/tree_integrity/final_checks.py`'s `f2_prefs` `PORT_CALIBRATION` row kept with a comment recording it is now belt-and-braces, per the plan's explicit instruction not to weaken the guard
- `--strict` clean throughout: 40 → 35 closure members (the 5 deleted setup-wizard modules), 30 protected files and 1 known-dangling exemption unchanged, 0 violations at every checkpoint

## Task Commits

Each task was committed atomically (TDD RED/GREEN pairs where applicable):

1. **Task 1: Delete HDF5/TrialData and port-calibration, update the F2 guard** — TDD: `886eabf` (test, RED) → `d8cb498` (feat, GREEN)
2. **Task 2: Delete the setup wizard and dead audio configuration** — TDD: `9db689d` (test, RED, bundled with the already-`git rm`-staged setup/ deletion — see Issues Encountered) → `a75ec0b` (feat, GREEN)
3. **Task 3: Build `tools/rebaseline_pytest.py` and re-baseline** — `2b4950f` (feat, mics_core) → `6e06e28` (plan, mics-backend — `31-PYTEST-BASELINE.json` is a planning artifact per the repo boundary rule)

All commits above are in `~/mics_core` on `phase-31-modern-pi-platform`, except `6e06e28` which is in `mics-backend`.

## Files Created/Modified

- `/home/ido/mics_core/tests/test_shed_absences.py` — permanent static gate (7 tests), tree-wide + scoped absence sets, two dynamic-import proofs, `f2_prefs` behavior test
- `/home/ido/mics_core/tools/rebaseline_pytest.py` — sole sanctioned baseline-rewrite tool
- `/home/ido/mics_core/tests/test_rebaseline_pytest.py` — 9 unit tests against a stubbed subprocess
- `/home/ido/mics_core/autopilot/autopilot/tasks/task.py` — `tables` import/class gone; `set_reward`'s `dur_from_vol` calls replaced with a direct duration=20ms fallback (fixing a latent bug where the single-port branch set `.duration` on the port name string, not the hardware object)
- `/home/ido/mics_core/autopilot/autopilot/core/pilot.py` — `tables`/`pandas`/`scipy` imports, `NaturalNameWarning` filter, write-only `trial_data` branch, and the whole calibration handler set gone; setup-wizard import gone; one prose reword
- `/home/ido/mics_core/autopilot/autopilot/hardware/gpio.py` — `dur_from_vol` and its `vol` branch gone (duration handling unchanged); one prose reword
- `/home/ido/mics_core/autopilot/autopilot/prefs.py` — calibration-file-loading block and `compute_calibration` gone; one prose reword
- `/home/ido/mics_core/autopilot/autopilot/__init__.py` — setup-wizard import line gone, other three re-exports untouched
- `/home/ido/mics_core/autopilot/autopilot/external/__init__.py` — one `ImportError` message reworded
- `/home/ido/mics_core/conftest.py` — `collect_ignore` narrowed to one entry with an honest, rewritten reason
- `/home/ido/mics_core/tools/tree_integrity/final_checks.py` — `f2_prefs`'s `PORT_CALIBRATION` row commented as belt-and-braces
- `/home/ido/mics-backend/.planning/phases/.../31-PYTEST-BASELINE.json` — re-baselined
- `/home/ido/mics_core/autopilot/autopilot/setup/` (7 files) and `/home/ido/mics_core/autopilot/setup.py` — deleted whole

## Decisions Made

See `key-decisions` in the frontmatter. In short: two of the plan's own absence-ban strings (`import blosc`/`import scipy` tree-wide, and separately `JACKDSTRING`/`sndrpihifiberry`) were narrowed or dropped after empirically finding live, unrelated consumers the plan itself said not to touch this wave (`stim/sound/`, `networking/message.py`). `calibration_curve`/`l_cal_result` were deleted beyond the plan's literal file/line list because they're the same dead subsystem and the actual reason the plan's own "scipy/pandas drop out of pilot.py" claim would otherwise have been false. `test_log_action_values.py` stays `collect_ignore`d (only `test_compute_ops.py` was safely un-ignored) after empirically finding the former is a genuine pytest collection error, not an individual test failure — un-ignoring it would have broken every chained gate in the phase.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug in plan's own audit] scipy/blosc tree-wide absence claim was false**
- **Found during:** Task 1, writing `tests/test_shed_absences.py`'s RED state
- **Issue:** `CONTEXT.md` §3 and the plan's own Task 1 `<behavior>` assert deleting the HDF5/calibration code drops `scipy`/`blosc`/`pandas`/`numexpr` from the runtime set entirely, and ask for a tree-wide absence gate on `import scipy`/`from scipy`/`import blosc`. Empirically false for two of the four: `scipy` is independently imported by `hardware/i2c.py`, `stim/sound/sounds.py`, `transform/geometry.py`, `transform/timeseries.py` (none touched by this plan — CONTEXT.md §4 itself lists three of these as *surviving* Python-3.11 fixups); `blosc` by `networking/message.py` (the protected `Message` class), `networking/__init__.py` and `networking/station.py` for numpy-array wire compression, unrelated to HDF5.
- **Fix:** Scoped `import scipy`/`from scipy`/`import blosc` absence checks to the four shed files only (`task.py`, `pilot.py`, `gpio.py`, `prefs.py`); kept `numexpr` tree-wide (verified zero uses anywhere, a transitive pip dep only) and added `import pandas` tree-wide (genuinely zero uses outside the two shed files, beyond the plan's own literal string list, closing a gap in its own claim).
- **Files modified:** `tests/test_shed_absences.py`
- **Verification:** `grep -rln` for each string before deciding; full docstring correction recorded in the test file itself
- **Committed in:** `886eabf`/`9db689d`

**2. [Rule 1 - Bug in plan's own audit] JACKDSTRING/sndrpihifiberry have live consumers**
- **Found during:** Task 2, deciding the `pilot/prefs.json` audio-key deletion
- **Issue:** The plan's Task 2 `<behavior>` bans `JACKDSTRING`/`sndrpihifiberry` tree-wide and its `<action>` says to delete them from `pilot/prefs.json`, on the premise (CONTEXT.md: "AUDIOSERVER: false ... dead weight, delete rather than port") that nothing reads them. `grep -rn` found live readers: `external/__init__.py:start_jackd()` and `stim/sound/jackclient.py` (plus `sounds.py`/`base.py`/`pyoserver.py` for the other audio keys), all gated behind `AUDIOSERVER` (currently `false`) but not deleted this plan (`stim/sound/` is explicitly plan 03's call per the plan's own `<verified_deletion_map>`).
- **Fix:** Kept all seven audio keys in `pilot/prefs.json` unedited (`ALSA_NPERIODS`, `AUDIOSERVER`, `FS`, `JACKDSTRING`, `NCHANNELS`, `OUTCHANNELS`, `SOUNDDIR`); did not add `JACKDSTRING`/`sndrpihifiberry` to the absence gate. This is literally what the plan's own conditional instruction ("remove ... only if grep -rn shows no live consumer") resolves to once that grep is run.
- **Files modified:** none (a non-edit is the fix)
- **Verification:** `grep -rn` output recorded in `tests/test_shed_absences.py`'s module docstring
- **Committed in:** `9db689d` (documented in the test file; `pilot/prefs.json` itself was never touched)

**3. [Rule 3 - Blocking] test_log_action_values.py cannot be safely un-ignored**
- **Found during:** Task 2, empirically running the suite with `collect_ignore` fully cleared
- **Issue:** The plan's `<behavior>` says both `test_compute_ops.py` and `test_log_action_values.py` "now COLLECT and run on the dev host." Empirically, un-ignoring `test_log_action_values.py` is a genuine pytest COLLECTION ERROR (`Tracker -> logging_utils -> Event_Dispatcher.py:3`'s unconditional `import pigpio`), which aborts collection for the entire `tests/` directory and breaks every gate that chains on it (including this same task's own `<verify>` block).
- **Fix:** Kept `test_log_action_values.py` in `collect_ignore` with a rewritten, honest reason (distinguishing it from `test_compute_ops.py`'s different failure mode); un-ignored only `test_compute_ops.py` (verified: collects cleanly, 4 pass/8 fail, matching `31-01-SUMMARY.md`'s own pre-recorded split exactly).
- **Files modified:** `conftest.py`
- **Verification:** `pytest tests/test_log_action_values.py` → collection error, traceback recorded; `pytest tests/test_compute_ops.py` → 4 passed, 8 failed, no collection error
- **Committed in:** `a75ec0b`

**4. [Rule 1 - Bug in plan's own audit] `calibration_curve`/`l_cal_result` were the real reason scipy/pandas stayed in pilot.py**
- **Found during:** Task 1, confirming the RED shed-absence test
- **Issue:** The plan's `<verified_deletion_map>` names only `calibrate_port`/`compute_calibration` for deletion from `pilot.py`, but `pilot.py` also had `l_cal_result` (saves raw calibration results to `port_calibration.json`) and `calibration_curve` (computes a duration-from-volume LUT via `pandas`/`scipy.stats.linregress` — never called from anywhere, verified) as module-level `import pandas as pd`/`from scipy.stats import linregress`. Leaving them would have made the plan's own "scipy disappears from pilot.py" claim false.
- **Fix:** Deleted `l_cal_result`, `calibration_curve`, and their `CALIBRATE_PORT`/`CALIBRATE_RESULT` dispatch entries alongside `calibrate_port`/`l_cal_port`, in the same commit as the rest of the port-calibration subsystem.
- **Files modified:** `autopilot/autopilot/core/pilot.py`
- **Verification:** `grep -rn "compute_calibration\|calibration_curve"` zero hits post-deletion; full suite still 179 failed/0 new after this specific change
- **Committed in:** `d8cb498`

**5. [Rule 1 - Bug] Latent AttributeError-on-string-name in `Task.set_reward`**
- **Found during:** Task 1, rewriting `set_reward`'s `dur_from_vol` calls (forced by the shed-absence test literally banning the string "dur_from_vol" anywhere in the tree)
- **Issue:** The single-port branch's `except AttributeError` handler did `port.duration = 20.0` where `port` was the function's string parameter (the port *name*), not the hardware object — setting an attribute on a `str` raises `AttributeError` again, uncaught, inside the except block itself. Never observed in practice because `PORT_CALIBRATION` was always absent (doubly-dead per CONTEXT.md), so the original `dur_from_vol` call always failed first with the SAME exception type, silently.
- **Fix:** Rewrote both branches to always fall back to `duration = 20.0` directly (no `dur_from_vol` call exists anymore) on the correct hardware object (`self.hardware['PORTS'][port]`, not the string `port`).
- **Files modified:** `autopilot/autopilot/tasks/task.py`
- **Verification:** Full suite run post-edit, 0 new failures relative to baseline
- **Committed in:** `d8cb498`

---

**Total deviations:** 5 auto-fixed (4 corrections to the plan's own audit/premises, 1 latent bug fix)
**Impact on plan:** No scope creep beyond the same two subsystems (port-calibration, setup-wizard) the plan already targeted. All five deviations either narrow an over-broad claim to what's actually true (documented, not silently absorbed) or complete the plan's own stated goal ("scipy disappears from pilot.py") where its literal file/line list fell short.

## Issues Encountered

- **Failure count went UP, not "dramatically lower than 179" as the plan's own overall `<verification>` step 2 states.** Measured: 187 failed / 253 passed (was 179 failed / 233 passed at the end of plan 01). Two additive, both expected and explained: (a) the carry-forward note from wave 1 is explicit that pigpio, not HDF5/calibration/npyscreen, is the actual remaining blocker for all 179 pre-existing failures, and this plan does not touch `Event_Dispatcher.py` (that's plan C2's job) — "if the count does not move, that is the expected result"; (b) Task 2 legitimately un-ignores `test_compute_ops.py`, adding 8 newly-visible, individually-verified pre-existing pigpio failures. `tools/pytest_delta.py` and `--strict` both confirm 0 *unexpected* regressions throughout — the plan's overall verification line 2 is stale, written before wave 1's empirical correction was known, and is called out here rather than silently satisfied by rounding up.
- **Task 2's git staging mixed a test commit with the setup/-directory deletion.** `git rm -r autopilot/autopilot/setup autopilot/setup.py` was run once (during RED-state engineering) and its staged deletion was still present when `git add tests/test_shed_absences.py && git commit` ran for the "test" commit, so commit `9db689d` (nominally "test") also carries the 8 deleted setup-wizard files. No functional impact — the deletion is real and correct either way — but the RED/GREEN commit split is less clean than Task 1's. Noted for transparency, not re-done (re-splitting after the fact would rewrite history unnecessarily).
- **Task 2's own literal `<verify>` chain cannot pass at its own commit boundary**, by the plan's own design: it un-ignores a pigpio-blocked module (adding new failing node ids) AND requires `pytest_delta.py` to report 0 new failures against the still-frozen Wave-0 baseline in the same breath — impossible until Task 3's re-baseline runs. Ran the substantively equivalent check instead (new-failures set == exactly the 8 expected `test_compute_ops.py` node ids, individually verified against `31-01-SUMMARY.md`'s pre-recorded split) and proceeded; Task 3 then closed the gap for real.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness

- Runtime dependency floor is materially smaller: `tables`, `blosc`(from this plan's own files)`, `numexpr`, `pandas`, `npyscreen`, `PySide2`, `shiboken2`, `pyqtgraph` are all gone from the pilot import path (module-scoped for scipy/blosc, see Decisions). `scipy` remains a genuine dependency via `hardware/i2c.py`/`stim/sound/`/`transform/` — plan 03's dependency audit inherits this as ground truth, not the CONTEXT.md claim.
- `tests/test_shed_absences.py` is the permanent regression gate for both subsystems deleted this plan; plan 03 (or later) can extend it the same way (tree-wide vs. scoped bans, decided on `grep -rn` evidence, not on a subsystem's name) rather than starting fresh.
- `tools/rebaseline_pytest.py` is the sole sanctioned re-baseline path from here forward — plan C1/C2 (the clean-room clock module, which touches `Event_Dispatcher.py` and is expected to finally move the 179/187-failing pigpio-blocked count) should use it, not a hand-edited JSON.
- `pilot/prefs.json`'s audio keys were deliberately left untouched — plan 03's `stim/sound/` dependency audit is the right place to revisit `AUDIOSERVER`/`JACKDSTRING`/etc. as a single decision, now that this plan has established they are NOT dead code (contrary to CONTEXT.md), just currently unreached.
- `test_log_action_values.py` remains `collect_ignore`d for a pigpio reason, not an npyscreen one — whichever plan (C1/C2) removes `Event_Dispatcher.py:3`'s unconditional `import pigpio` should expect to un-ignore it then, and should expect the failing-node-id count to actually move for the first time in the phase.

---
*Phase: 31-mics-core-modern-pi-platform-bookworm-64-bit-python-3-11-lgpio-unattended-boot*
*Completed: 2026-08-19*

## Self-Check: PASSED

All 13 created/modified file paths verified present on disk (and both deleted paths
confirmed absent: `autopilot/autopilot/setup/`, `autopilot/setup.py`). All 6 commit
hashes verified present via `git log --oneline --all` (`886eabf`, `d8cb498`,
`9db689d`, `a75ec0b`, `2b4950f` in `mics_core`; `6e06e28` in `mics-backend`).
