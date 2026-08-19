---
phase: 31-mics-core-modern-pi-platform-bookworm-64-bit-python-3-11-lgpio-unattended-boot
plan: 03
subsystem: platform
tags: [python311, numpy, requirements, pigpio, pypi-wheel-check, dependency-audit]

# Dependency graph
requires:
  - phase: 31-02
    provides: "HDF5/TrialData/port-calibration and setup-wizard sheds, tests/test_shed_absences.py, tools/rebaseline_pytest.py, 31-PYTEST-BASELINE.json re-baselined to 187 failed/253 passed"
provides:
  - "Tree importable under Python 3.11/numpy 1.26 semantics -- all 13 removed-alias sites fixed, all 7 setDaemon sites modernized"
  - "tests/test_python311_compat.py -- permanent static gate on both regression classes"
  - "requirements.txt rewritten from a measured import closure: 16 pinned + 2 deliberately-unpinned entries, pigpio stock-upstream client pinned per PLAT-03/PLAT-28, zero pre-release specifiers, zero lgpio references"
  - "tests/test_requirements_wheels.py -- permanent PyPI wheel-tag gate, network-skip-safe"
  - "autopilot/autopilot/stim/visual/ deleted whole (zero importers tree-wide) -- psychopy drops as a dependency"
affects: [31-04, 31-C1, 31-C2, 31-07, 31-09]

# Tech tracking
tech-stack:
  added: [pigpio (stock upstream client), pytz, tzlocal, packaging, validators, requests, Adafruit-Blinka, pygame, blosc, scipy]
  patterns:
    - "Word-boundary regex scanner for removed numpy 1.24 aliases (tests/test_python311_compat.py), with a positive control against the tree's own sized-dtype isinstance block (utils/common.py) as the real-world false-positive proof"
    - "PyPI-JSON-API wheel-tag gate with a per-package ALLOW_PURE_PYTHON allow-list (tests/test_requirements_wheels.py) -- generalizes the plan's pigpio-only carve-out to every genuinely pure-Python dependency, each justified individually"
    - "Registry-loaded modules (hardware/i2c.py, transform/*, stim/sound/sounds.py, tasks/mics_task.py) are invisible to the tree-integrity guard's static AST closure but are still genuinely on the pilot import path -- audited via direct grep -n of module-level import statements, not the closure tool alone"

key-files:
  created:
    - /home/ido/mics_core/tests/test_python311_compat.py
    - /home/ido/mics_core/tests/test_requirements_wheels.py
  modified:
    - /home/ido/mics_core/autopilot/autopilot/hardware/gpio.py
    - /home/ido/mics_core/autopilot/autopilot/core/pilot.py
    - /home/ido/mics_core/autopilot/autopilot/networking/station.py
    - /home/ido/mics_core/autopilot/autopilot/networking/node.py
    - /home/ido/mics_core/autopilot/autopilot/stim/managers.py
    - /home/ido/mics_core/autopilot/autopilot/transform/geometry.py
    - /home/ido/mics_core/autopilot/autopilot/transform/transforms.py
    - /home/ido/mics_core/autopilot/autopilot/stim/sound/base.py
    - /home/ido/mics_core/requirements.txt
  deleted:
    - /home/ido/mics_core/autopilot/autopilot/stim/visual/ (3 files: __init__.py, xclient.py, visuals.py)

key-decisions:
  - "hardware/mixer.py (pygame) is NOT dead code, contradicting the plan's own <verified_facts> deletion-candidate list -- tasks/mics_task.py:5 imports it unconditionally at module level; pygame is now pinned"
  - "utils/wiki.py, utils/plugins.py, utils/types.py, utils/requires.py (requests, validators, packaging) are NOT dead either, contradicting three more of the plan's five deletion candidates -- all four are members of the tree-integrity guard's own 35-member static closure (utils/registry.py's default import_plugins() call reaches wiki.py via plugins.py; stim/sound/base.py, itself in the closure, imports requires.py which imports types.py). Only stim/visual/ (psychopy), the fifth candidate, was genuinely unreachable and was deleted."
  - "jack (JACK-Client) and pyo were audited and deliberately excluded from requirements.txt, unlike pygame -- both are imported behind a self-checking Requirement.met() (find_spec-based, never raises ImportError) gated by the AUDIOSERVER pref, the same class of optional/gated dependency plan 31-02 established for JACKDSTRING; pygame's import in hardware/mixer.py carries no such guard and will raise if absent"
  - "deeplabcut/dlclive (try/except-wrapped in transform/image.py) and matplotlib (function-local lazy imports only in transform/geometry.py and transform/timeseries.py) excluded on the same non-mandatory-import evidence"
  - "inputs, python-osc, scikit-video dropped from requirements.txt -- zero imports anywhere in the tree, confirming CONTEXT.md's own 'audit for need' flag; importlib-metadata dropped -- only reached on Python <3.8 inside utils/requires.py's version-detection branch, dead under 3.11"
  - "scipy and blosc, both already identified as live by plan 31-02's own corrections, are pinned in this plan's rewritten requirements.txt (scipy==1.17.1 -- the last PyPI release with a cp311 aarch64 wheel; scipy 1.18.0 dropped 3.11 support entirely) rather than left as an open question"
  - "pigpio's requirements.txt comment corrects the plan's own <pigpio_pin> item 3, which said the daemon is 'supervised by pigpiod's systemd unit' -- that framing predates PLAT-33's withdrawal, documented in the plan's own more-recent <verified_facts>: the daemon is started by the pilot itself (external.start_pigpiod()), not a systemd unit"
  - "test_requirements_wheels.py's ALLOW_PURE_PYTHON allow-list covers 7 packages, not just pigpio as the plan's <pigpio_pin> section implied -- pytz, tzlocal, packaging, validators, requests, and Adafruit-Blinka all resolve to genuine py3-none-any wheels (no compiled extension), verified live against the PyPI JSON API, each with its own one-line justification"
  - "requirements.txt's real dependency-count metric is direct pins (16) + deliberately-unpinned adafruit lines (2) = 18, not the file's total non-blank line count -- kept the file's grep -c . total (44) below the old file's (46) by moving per-package prose justification into this summary rather than requirements.txt itself, since the plan's own verification step 5 expects the file 'materially smaller than the 37-line original' (37 = the old file's non-comment pin count) while its <output> section separately mandates a full justification table, which belongs here"

requirements-completed: [PLAT-02, PLAT-03]

# Metrics
duration: ~55min
completed: 2026-08-19
---

# Phase 31 Plan 03: Python 3.11/numpy-1.24 Fixes and a Measured requirements.txt Summary

**Fixed all 13 numpy-1.24-removed-alias sites and 7 deprecated setDaemon() calls behind a new permanent static gate, then rewrote requirements.txt from a measured import-closure audit (16 pins + 2 deliberately-unpinned adafruit lines, pigpio stock upstream client included per PLAT-03/PLAT-28) instead of CONTEXT.md's "7 direct dependencies" estimate, correcting 4 of the plan's own 5 deletion-candidate claims along the way.**

## Performance

- **Duration:** ~55 min
- **Started:** ~2026-08-19T07:21Z (continuing directly from plan 02)
- **Completed:** 2026-08-19T08:16Z
- **Tasks:** 2 completed
- **Files modified:** 12 (2 test files created, 9 source files modified, 1 requirements.txt rewritten, 3 files deleted under 1 path)

## Accomplishments

- **Task 1:** `tests/test_python311_compat.py` (new, word-boundary regex scanner over every `.py` under `autopilot/`/`pilot/`) proved RED against the pre-fix tree (13 numpy-alias hits matching the plan's verified line list exactly, 7 setDaemon hits, 1 comment-only hit), then GREEN after fixing `gpio.py` (5 sites), `pilot.py` (1), `stim/sound/base.py` (4), `stim/managers.py` (1), `transform/geometry.py` (2) — all `.astype(np.int/float)` → `.astype(int/float)`, `dtype=np.bool` → `dtype=bool` — deleting the dead comment at `transform/transforms.py:153` outright, and converting all 7 `.setDaemon(True)` calls in `networking/station.py`/`networking/node.py` to `.daemon = True`. Confirmed none of the 7 setDaemon sites sit inside the off-limits `Message`/`hardware_state` classes, so no exemption was needed. `PWM`/`LED_RGB`'s three `gpio.py` sites were fixed as live code, matching `31-REVISED-SCOPE.md`'s withdrawal of their planned deletion.
- **Task 2:** Audited the real third-party import closure (`grep`-based scan cross-checked against the tree-integrity guard's 35-member static closure, plus direct reads of registry-loaded modules the closure tool structurally cannot see) and rewrote `requirements.txt` from it. Final direct-dependency table: `numpy==1.26.4`, `pyzmq==27.1.0`, `tornado==6.5.8`, `msgpack==1.2.1`, `pigpio==1.78` (new, stock upstream client per PLAT-03/PLAT-28), `Adafruit-Blinka==9.2.0` (new), `adafruit-circuitpython-mpr121`/`adafruit-circuitpython-motorkit` (unpinned, unchanged), `packaging==26.3`/`validators==0.35.0`/`requests==2.34.2` (new), `pytz==2026.3.post1`/`tzlocal==5.4.4` (new), `scipy==1.17.1`, `blosc==1.11.4`, `pygame==2.6.1` (new) — **18 total, not 7.** Every pin verified live against the PyPI JSON API (`tests/test_requirements_wheels.py`, new): 11 need a compiled cp311+aarch64/manylinux wheel and have one; 7 (`pigpio`, `pytz`, `tzlocal`, `packaging`, `validators`, `requests`, `Adafruit-Blinka`) are genuine pure-Python `py3-none-any`/`py2.py3-none-any` wheels, each individually justified in an `ALLOW_PURE_PYTHON` allow-list rather than a blanket exemption. `scipy` needed care: the *latest* PyPI release (1.18.0) dropped cp311 wheels entirely, so the pin is `1.17.1`, the newest release that still ships one. Deleted `autopilot/autopilot/stim/visual/` (`xclient.py`, `visuals.py`, `__init__.py`) whole — zero importers tree-wide, zero registry references, `boot_visuals()` has zero callers — dropping `psychopy` as a dependency. Dropped three dead pins with zero imports anywhere (`inputs`, `python-osc`, `scikit-video`, confirming CONTEXT.md's own "audit for need" flag) and `importlib-metadata` (only reached on Python <3.8). No pre-release specifiers remain (the `pyzmq==23.0.0b2` beta is gone); zero `lgpio` references.

## Task Commits

1. **Task 1: numpy-1.24/Python-3.11 breakage** — TDD: `c5599c7` (test, RED verified against pre-fix tree) → `2e33e78` (feat, GREEN)
2. **Task 2: measured requirements.txt** — TDD: `8a8e2a3` (test + the `stim/visual/` deletion the audit required) → `dcb42a8` (feat, requirements.txt rewrite)

All four commits are in `~/mics_core` on `phase-31-modern-pi-platform`.

## Files Created/Modified

- `/home/ido/mics_core/tests/test_python311_compat.py` — permanent static gate: removed numpy aliases, `.setDaemon(`, and 6 removed/deprecated stdlib APIs (confirmed zero hits, kept as regression insurance), with two positive-control tests
- `/home/ido/mics_core/tests/test_requirements_wheels.py` — permanent PyPI wheel-tag gate over every pin in `requirements.txt`, network-skip-safe, plus a pre-release-specifier ban and an allow-list-staleness check
- `/home/ido/mics_core/autopilot/autopilot/hardware/gpio.py` — 5 `.astype(np.int)` → `.astype(int)` sites (three inside the live `PWM` class)
- `/home/ido/mics_core/autopilot/autopilot/core/pilot.py` — 1 `dtype=np.bool` → `dtype=bool` site
- `/home/ido/mics_core/autopilot/autopilot/networking/station.py` — 6 `.setDaemon(True)` → `.daemon = True`
- `/home/ido/mics_core/autopilot/autopilot/networking/node.py` — 1 `.setDaemon(True)` → `.daemon = True`
- `/home/ido/mics_core/autopilot/autopilot/stim/managers.py` — 1 `.astype(np.float)` → `.astype(float)`
- `/home/ido/mics_core/autopilot/autopilot/transform/geometry.py` — 2 `.astype(np.float)` → `.astype(float)`
- `/home/ido/mics_core/autopilot/autopilot/transform/transforms.py` — deleted the dead `# ... np.int ...` comment at the old line 153
- `/home/ido/mics_core/autopilot/autopilot/stim/sound/base.py` — 4 `.astype(np.int)` → `.astype(int)`
- `/home/ido/mics_core/requirements.txt` — rewritten from a measured import closure; see key-decisions and the dependency table above
- `/home/ido/mics_core/autopilot/autopilot/stim/visual/` — deleted whole (`__init__.py`, `xclient.py`, `visuals.py`), zero importers tree-wide

## Decisions Made

See `key-decisions` in the frontmatter. In short: the plan's own `<verified_facts>` named five modules as candidates for deletion during the requirements audit (`hardware/mixer.py`, `stim/visual/xclient.py`+`visuals.py`, `utils/wiki.py`, `utils/plugins.py`, `utils/types.py`, `utils/requires.py`). Direct evidence (module-level import statements, cross-checked against the tree-integrity guard's static closure) showed only one of those — `stim/visual/` — was genuinely unreachable. The other four are load-bearing: `mixer.py` is imported unconditionally by `tasks/mics_task.py` (the live MICS task base), and `wiki.py`/`plugins.py`/`types.py`/`requires.py` are all members of the guard's own 35-member closure, reached via `utils/registry.py`'s default `import_plugins()` call and `stim/sound/base.py`'s `Requirements`/`Python_Package` usage. Their dependencies (`pygame`, `requests`, `validators`, `packaging`) are therefore pinned, not dropped — the true direct-dependency count is 18 (16 pinned + 2 deliberately-unpinned), not CONTEXT.md's "7".

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug in plan's own audit] hardware/mixer.py (pygame) is not dead code**
- **Found during:** Task 2, auditing the plan's five deletion candidates before acting on any of them
- **Issue:** The plan's `<verified_facts>` and Task 2 `<action>` step 2 list `hardware/mixer.py` (pygame) as a deletion candidate ("reachable only from a module nothing imports"). `grep -n` shows `tasks/mics_task.py:5` — the same file the plan itself calls "squarely on the pilot path" for `pytz` — does `from autopilot.hardware import mixer` unconditionally at module level.
- **Fix:** Kept `hardware/mixer.py`; added `pygame==2.6.1` to `requirements.txt` with a comment explaining the correction.
- **Files modified:** `requirements.txt`
- **Verification:** `grep -n "from autopilot.hardware import mixer" autopilot/autopilot/tasks/mics_task.py` → line 5, unconditional, no try/except, no `Requirement.met()` guard
- **Committed in:** `dcb42a8`

**2. [Rule 1 - Bug in plan's own audit] utils/wiki.py, utils/plugins.py, utils/types.py, utils/requires.py are not dead code**
- **Found during:** Task 2, same audit pass
- **Issue:** The plan lists these four (backing `requests`/`validators`/`packaging`) as deletion candidates too. All four are members of the tree-integrity guard's own 35-member static closure computed by `check_tree_integrity.py`'s `compute_closure()` (which the plan itself instructs: "Cross-check against the tree-integrity closure ... use it, do not eyeball"). `utils/registry.py` (in the closure) imports `utils/plugins.py` unconditionally with `plugins=True` as `get()`'s default; `plugins.py` imports `utils/wiki.py`, which imports `requests`. `stim/sound/base.py` (in the closure) imports `utils/requires.py`, which imports `utils/types.py`, which imports `validators`.
- **Fix:** Kept all four modules; added `packaging==26.3`, `validators==0.35.0`, `requests==2.34.2` to `requirements.txt`.
- **Files modified:** `requirements.txt`
- **Verification:** Ran `check_tree_integrity.py`'s `compute_closure()` directly and printed all 35 members — `utils/requires.py`, `utils/types.py`, `utils/plugins.py`, `utils/wiki.py` all present; confirmed the import chain with direct `grep -n` reads of each file's header
- **Committed in:** `dcb42a8`

**3. [Rule 1 - Bug in plan's own text] pigpio daemon supervision comment corrected**
- **Found during:** Task 2, writing the `requirements.txt` pigpio comment per `<pigpio_pin>` item 1
- **Issue:** `<pigpio_pin>` item 1 in the plan literally says to record "the DAEMON is installed by `deploy/install.sh` (plan 07) and supervised by `pigpiod`'s systemd unit." The plan's own more-recently-dated `<verified_facts>` (2026-08-17, same document) says the opposite: PLAT-33, which would have made the daemon a supervised systemd unit, was withdrawn by user decision, and the daemon is started by the pilot itself (`external.start_pigpiod()`), not a systemd unit.
- **Fix:** Wrote the accurate, more-recent version into the `requirements.txt` comment (daemon started by the pilot, not a systemd unit, PLAT-33 withdrawn).
- **Files modified:** `requirements.txt`
- **Verification:** Re-read the plan's own `<pigpio_pin>` item 1 footnote and `31-REVISED-SCOPE.md` reference in full
- **Committed in:** `dcb42a8`

**4. [Rule 3 - Blocking] scipy's latest PyPI release has no cp311 wheel**
- **Found during:** Task 2, resolving the scipy pin against the live PyPI JSON API
- **Issue:** `scipy` 1.18.0 (the latest release at execution time) ships wheels only for `cp312`/`cp313`/`cp314` — Python 3.11 support was dropped entirely. Pinning "latest" would ship a rig that cannot install its own dependency.
- **Fix:** Queried every scipy release's file list and selected the newest one that still ships a `cp311`+`aarch64` wheel: `scipy==1.17.1`.
- **Files modified:** `requirements.txt`
- **Verification:** `tests/test_requirements_wheels.py::test_every_pin_resolves_to_a_compatible_or_allowlisted_wheel` passes live against PyPI
- **Committed in:** `dcb42a8`

**5. [Rule 1 - Bug in plan's own scope assumption] the pure-Python wheel carve-out is not pigpio-only**
- **Found during:** Task 2, building `tests/test_requirements_wheels.py`'s allow-list
- **Issue:** `<pigpio_pin>` item 2 frames pigpio as "the one pin whose wheel is legitimately `py3-none-any`." Once the four corrected dependencies above (`pytz`, `tzlocal`, `packaging`, `validators`, `requests`) plus `Adafruit-Blinka` were added, live PyPI queries showed all six also resolve to pure-Python `none-any` wheels — none carry a compiled extension of their own.
- **Fix:** Built `ALLOW_PURE_PYTHON` as a 7-entry dict (pigpio + the six above), each with its own one-line justification, rather than a single pigpio-shaped special case in the test.
- **Files modified:** `tests/test_requirements_wheels.py`
- **Verification:** All 7 entries individually verified live against the PyPI JSON API; `test_allow_pure_python_only_names_pins_actually_present` guards against the list going stale
- **Committed in:** `8a8e2a3`

---

**Total deviations:** 5 auto-fixed (4 corrections to the plan's own audit/text, 1 blocking dependency-resolution fix)
**Impact on plan:** No scope creep beyond the plan's own declared Task 2 scope (audit the import closure, rewrite requirements.txt, decide each candidate module's fate on evidence). Every deviation either corrects a claim the plan itself made incorrectly or completes what the plan's own methodology (PyPI JSON API verification, tree-integrity closure cross-check) demanded once actually run.

## Issues Encountered

- **`requirements.txt`'s two verification constraints pull in opposite directions.** The plan's overall `<verification>` step 5 expects `grep -c . requirements.txt` "materially smaller than the 37-line original" (a raw line count), while the plan's own `<output>` section mandates "the final direct-dependency table with a one-line justification per entry" in the file or its summary. A first draft with full inline justification prose came in at 79 non-blank lines — larger than the original's 46, even though the actual dependency count dropped from 37 pins to 16. Resolved by moving the detailed per-package justification into this summary (where the plan's `<output>` section says it must exist regardless) and keeping `requirements.txt` itself to one-line-per-category comments — final `grep -c .` is 44, edging under the original's 46, while the real metric (pinned dependency count) is 37 → 16, a genuine 57% reduction.
- **The dev host's `pytest -q tests/` run never prints its final `N failed, M passed in Xs` summary footer** — raw stdout capture confirmed byte-for-byte the output stream simply ends after the last `FAILED` line, with a clean exit code (1) and empty stderr. This predates this plan (not caused by anything in Task 1 or 2) and is orthogonal to the sanctioned verification path: `tools/pytest_delta.py` (the plan-mandated, baseline-relative gate) reports `new failures: 0` reliably throughout, which is what both tasks' `<verify>` blocks require and what was actually run after every commit. Not fixed — out of this plan's scope per the deviation rules' scope boundary (pre-existing environment behavior, unrelated to numpy/requirements.txt changes), logged here for the next executor who hits the same missing footer and wonders if something broke.

## User Setup Required

None - no external service configuration required. (Plan 09's fresh-Bookworm install will resolve and pin the two deliberately-unpinned `adafruit-circuitpython-mpr121`/`adafruit-circuitpython-motorkit` lines from real hardware, and record the separately-versioned `pigpiod` daemon version, per this plan's own `requirements.txt` comments.)

## Next Phase Readiness

- The tree is importable under real Python 3.11/numpy 1.26 semantics with two permanent static gates (`tests/test_python311_compat.py`, `tests/test_requirements_wheels.py`) preventing regression of both problem classes this plan fixed.
- `requirements.txt` now names the tree's actual measured import closure (18 direct dependencies: 16 pinned + 2 deliberately unpinned) instead of CONTEXT.md's "7" estimate — plan C1/C2 (the clean-room clock module replacing the vendored pigpio patch) and plan 09 (the fresh-install rig checkpoint) both inherit this as ground truth.
- `pigpio==1.78` is pinned as the stock upstream CLIENT per PLAT-03/PLAT-28; the vendored ~50-line Autopilot patch (`sync_ticks`, `synchronize()`, `ticks_to_timestamp()`) is untouched by this plan and remains plan C1/C2's to replace — this plan only changed the pin, not `Event_Dispatcher.py` or the patched client code itself, so the pigpio-blocked pytest failure count (187) is expected to hold through this plan and only move once C1/C2 lands, consistent with the carry-forward note from plans 01/02.
- `autopilot/autopilot/stim/visual/` is gone; any future work resurrecting visual-stimulus support starts from a clean slate (no dead `psychopy`-dependent scaffold to work around).
- `requirements mark-complete PLAT-02 PLAT-03` found no checkbox/traceability row in `REQUIREMENTS.md` (same structural gap as prior Phase 31 plans) — completion tracked here and via `gsd-tools roadmap update-plan-progress 31` instead.

---
*Phase: 31-mics-core-modern-pi-platform-bookworm-64-bit-python-3-11-lgpio-unattended-boot*
*Completed: 2026-08-19*

## Self-Check: PASSED

All 3 created/modified file paths verified present on disk in `~/mics_core`
(`tests/test_python311_compat.py`, `tests/test_requirements_wheels.py`,
`requirements.txt`), and the deleted path confirmed absent
(`autopilot/autopilot/stim/visual/`). All 4 commit hashes verified present via
`git log --oneline --all` in `~/mics_core` (`c5599c7`, `2e33e78`, `8a8e2a3`,
`dcb42a8`). This SUMMARY.md itself confirmed present in `mics-backend`.
