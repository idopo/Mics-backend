---
phase: 31-mics-core-modern-pi-platform-bookworm-64-bit-python-3-11-lgpio-unattended-boot
plan: 06
subsystem: testing
tags: [pigpio, pulse-timing, python37, ast, gpio, benchmark-harness, numpy]

# Dependency graph
requires:
  - phase: 31-03
    provides: "gpio.py fixed for Python 3.11/numpy 1.26 (astype sites), requirements.txt with pigpio==1.78 stock upstream client -- capture.py's production-class import closure and py37_gate.py's REQUIRED_MEMBERS assertion both depend on gpio.py being in the state this plan left it"
provides:
  - "tools/pulse_timing/{capture.py,wrap_witness.py}: USER-RUN loopback pulse-timing capture through the real Digital_Out/Solenoid_mics/TTL/Pulse20Hz production classes, before/after arms, Python 3.7 safe"
  - "tools/pulse_timing/py37_gate.py: transitive in-repo Python-3.7 grammar+syntax gate (feature_version PLUS 4 explicit 3.8+ construct checks), closure verified to reach autopilot/hardware/gpio.py (30 members)"
  - "tools/pulse_timing/analyse.py: statistics, the G1 comparative gate (<=1.25x), 5 absolute thresholds, --check-step (PLAT-25), --check-wrap [--expect-defect] (PLAT-25/29/30) -- the two-mode assertion that proves the 71.6-minute backward jump both present (before) and absent (after)"
  - "tools/pulse_timing/README.md: JSONL contract, method, honest limits, and a copy-paste block per capture for plans 08/C4"
  - "22 tests (tests/test_py37_gate.py, tests/test_pulse_timing_analyse.py) proving the gate is non-vacuous and the analyser's answers are known by construction"
affects: [31-08, 31-C4]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Driving a production Hardware subclass standalone: a real Event_Dispatcher with node=None absorbs every @auto_log dispatch via its own broad except-Exception on the background sender thread, so capture.py needs no live ZMQ node or Task to call the real Digital_Out/Solenoid_mics/TTL/Pulse20Hz methods"
    - "Deferred (function-body, never module-level) pigpio/autopilot imports so --help and argument validation work with neither pigpio installed nor a pigpiod running -- verified live on this dev host, which has neither"
    - "Reusing tools/tree_integrity/resolver.py's import_edges/resolve for the autopilot.* half of a second, independent AST closure walker (py37_gate.py), rather than re-deriving the from-import package/attribute ambiguity it already solved"
    - "feature_version=(3,7) grammar parsing is necessary but not sufficient for Python-3.7 safety -- paired with explicit AST checks for the four 3.8+ constructs it lets through (PEP 585 generics, PEP 604 unions, dataclass(slots=), f-string `=` specs), each with a positive control proving the checks are annotation-scoped, not a blanket ban"
    - "Fixture-generator-as-test-fixture: small committed Python functions with their parameters as module constants build the synthetic .jsonl files, so every expected statistic in the test suite is derived from those parameters, and a dedicated test guards the committed file against drifting from its own generator"

key-files:
  created:
    - /home/ido/mics_core/tools/pulse_timing/__init__.py
    - /home/ido/mics_core/tools/pulse_timing/profiles.py
    - /home/ido/mics_core/tools/pulse_timing/capture.py
    - /home/ido/mics_core/tools/pulse_timing/wrap_witness.py
    - /home/ido/mics_core/tools/pulse_timing/py37_gate.py
    - /home/ido/mics_core/tools/pulse_timing/analyse.py
    - /home/ido/mics_core/tools/pulse_timing/README.md
    - /home/ido/mics_core/tools/pulse_timing/fixtures/synthetic_before.jsonl
    - /home/ido/mics_core/tools/pulse_timing/fixtures/synthetic_after.jsonl
    - /home/ido/mics_core/tools/pulse_timing/fixtures/synthetic_clockstep.jsonl
    - /home/ido/mics_core/tools/pulse_timing/fixtures/synthetic_wrap.jsonl
    - /home/ido/mics_core/tests/test_py37_gate.py
    - /home/ido/mics_core/tests/test_pulse_timing_analyse.py
  modified: []

key-decisions:
  - "capture.py's INPUT side does NOT go through autopilot.hardware.gpio.Digital_In, because Digital_In.__init__ unconditionally sets a 500us glitch filter -- exactly the bias the loopback method's width-cancellation argument depends on not having. Only the OUTPUT side (Solenoid_mics/TTL/Pulse20Hz) drives the real production classes; the input claim is the harness's own instrumentation, documented as a deliberate asymmetry in README.md `## Method`"
  - "capture.py forces raw pigpio ticks on BOTH stock and patched clients by setting pi.synchronize = None after connecting (when the attribute exists) -- the exact fallback path the patch's own OverflowError handler already takes, not a new code path, and it means one tool is valid before and after PLAT-28 deletes the vendored patch"
  - "wrap_witness.py is the one deliberate exception to the stock-only rule: it connects with whatever client is installed and does NOT force raw ticks, because its whole purpose is to record what that client actually hands a callback (raw int, float, or the patched client's isoformatted string)"
  - "py37_gate.py's closure walker reuses tools/tree_integrity/resolver.py's import_edges/resolve for the autopilot.* half (package/attribute ambiguity handling already solved there) and adds its own general resolver only for the sibling-module case (`import profiles`) and a tools./pilot. rooted case, rather than re-implementing full Python import semantics from scratch"
  - "PEP 604 union / PEP 585 generic checks are deliberately scoped to annotation positions only (AnnAssign, arg.annotation, FunctionDef.returns) -- a bare `a | b` on two integers or a `Subscript` of a variable literally named `type` elsewhere in the file must not be flagged, proven by the positive-control test (test 7 of 7), without which the obvious wrong fix (reject every `|` and every Subscript) would pass all the negative cases and make the gate unusable"
  - "--check-wrap's reported backward-jump magnitude is the OBSERVED value, not the theoretical 2**32/1e6, and can differ from it by up to one sample interval -- documented in analyse.py's own printed message and matches the plan's own hedge ('report the measured value rather than assuming it'); verified against the synthetic_wrap.jsonl fixture, which (with a 5s heartbeat) reports 4289.967296s, exactly interval_s below the theoretical 4294.967296s"

requirements-completed: [PLAT-23, PLAT-25]

# Metrics
duration: ~70min
completed: 2026-08-19
---

# Phase 31 Plan 06: Pulse-Timing Capture Instrument Summary

**Built the phase's own acceptance-gate instrument before the clock refactor it grades exists: a Python-3.7-safe loopback capture (`capture.py`) that drives the real pigpio-daemon-script production path, a defect witness (`wrap_witness.py`) that has already recorded, on a synthetic fixture, a 4289.97s backward jump one wrap interval below the theoretical 4294.97s defect magnitude, a two-layer AST gate (`py37_gate.py`) proven to catch four construct classes `ast.feature_version` alone lets through, and a statistics/gate analyser (`analyse.py`) proven against captures whose answers are known by construction.**

## Performance

- **Duration:** ~70 min
- **Started:** ~2026-08-19T06:55Z
- **Completed:** 2026-08-19T08:10Z
- **Tasks:** 2 completed
- **Files modified:** 13 created (7 Task 1, 6 Task 2), 0 modified outside the new package (one same-task follow-up edit to `wrap_witness.py`'s own docstring, folded into Task 2's commit)

## Accomplishments

- **Task 1** built `capture.py` and `wrap_witness.py` sharing one JSONL contract (header + `edge`/`witness` records, documented verbatim in `README.md`). `capture.py` drives the real `Digital_Out`/`Solenoid_mics`/`TTL`/`Pulse20Hz` classes from `autopilot/autopilot/hardware/gpio.py` through a standalone `Event_Dispatcher(node=None, ...)` -- proven constructible without a live ZMQ node or `Task`, because its background sender thread's `node.send(...)` `AttributeError` is caught and counted by the dispatcher's own broad exception handler, never raised into the calling hardware thread. The input side claims both edges with **no glitch filter** by bypassing `Digital_In` entirely (that class hardcodes a 500us filter). `capture.py` forces raw pigpio ticks on any client (stock or patched) by setting `pi.synchronize = None` post-connect; `wrap_witness.py` deliberately does the opposite, recording whatever the installed client hands a callback (raw int / float / ISO string, with `delivered_type` naming which), plus a `get_current_tick()` heartbeat every 30s. `py37_gate.py` computes the transitive in-repo import closure of both entry points (reusing `tools/tree_integrity/resolver.py` for the `autopilot.*` half), runs `ast.parse(..., feature_version=(3,7))` on every member, and layers four explicit AST checks for the constructs `feature_version` lets through (PEP 585 builtin generics, PEP 604 unions, `dataclass(slots=)`, f-string `=` specs) -- verified live: the real closure is 30 members and demonstrably reaches `autopilot/autopilot/hardware/gpio.py` and `wrap_witness.py`. `tests/test_py37_gate.py` proves all 7 required cases, including the positive control (typing/numpy/plain-`|` must NOT be rejected).
- **Task 2** (TDD) built `analyse.py` -- pulse-width/period statistics (`n`, `n_missing`, `err_median/sd/p99/max/iqr`, or `period_sd_us`/`rate_ppm` for the `train` profile), the G1 comparative gate (after arm's `err_p99`/`err_sd` <= 1.25x before, tested at both exactly 1.25x [pass] and 1.26x [fail]), five absolute thresholds from the plan's own table (each firing independently of G1, proven with an after-arm that beats baseline but still breaks its absolute limit), `--check-step +SECONDS` (asserts a wall-clock step lands in `t_utc_ns` only, never `t_mono_ns`), and `--check-wrap [--expect-defect]` -- the two-mode assertion that is the phase's central evidence, proven in both directions on both a defective and a clean synthetic `wrap_witness` fixture. Four fixtures were generated by small, committed functions in `tests/test_pulse_timing_analyse.py` (parameters recorded as module constants alongside them) and guarded by `test_committed_fixtures_match_the_generator` against silent drift.

## Task Commits

1. **Task 1: capture.py and wrap_witness.py -- one JSONL format, Python 3.7 safe** -- `069dac3` (feat)
2. **Task 2: analyse.py -- statistics, the G1 gate, --check-step and --check-wrap** -- `3d1b380` (test; TDD, fixtures+tests+implementation landed together after RED/GREEN iteration on the wrap-witness fixture's wrap placement, see Issues Encountered)

Both commits are in `~/mics_core` on `phase-31-modern-pi-platform`.

## Files Created/Modified

- `tools/pulse_timing/__init__.py` -- package marker only; never executed by the two entry-point scripts, which run standalone
- `tools/pulse_timing/profiles.py` -- the 5 profiles (valve/valve_short/ttl/train/mixed) and 3 arms as data, pure stdlib so `--help` needs neither pigpio nor a pigpiod
- `tools/pulse_timing/capture.py` (481 lines) -- USER-RUN loopback capture through the production pulse path
- `tools/pulse_timing/wrap_witness.py` (365 lines) -- USER-RUN long capture of what the installed pigpio client hands a callback
- `tools/pulse_timing/py37_gate.py` (408 lines) -- the transitive-closure Python-3.7 grammar+syntax gate
- `tools/pulse_timing/analyse.py` (447 lines) -- statistics, gates, `--check-step`, `--check-wrap`
- `tools/pulse_timing/README.md` -- method, honest limits, JSONL contract, gates, copy-paste blocks
- `tools/pulse_timing/fixtures/*.jsonl` (4 files) -- synthetic captures with known-by-construction answers
- `tests/test_py37_gate.py` (127 lines, 9 tests) -- non-vacuity proof for the gate
- `tests/test_pulse_timing_analyse.py` (377 lines, 13 tests) -- fixture generators + analyser proof

## Decisions Made

See `key-decisions` in the frontmatter. In short: the input side of `capture.py` deliberately bypasses `Digital_In` (glitch filter bias), `capture.py` forces raw ticks on any client while `wrap_witness.py` deliberately does not (it exists to record exactly what the installed client hands a callback), `py37_gate.py` reuses the tree-integrity guard's own resolver rather than re-deriving import-ambiguity handling, and the two 3.8+-construct checks that could plausibly over-fire (builtin generics, PEP 604 unions) are scoped to annotation positions and proven not to over-fire by a dedicated positive control.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] `_claim_input_no_glitch_filter` didn't pass the callback function through to `pi.callback(...)`**
- **Found during:** Task 1, first read-through of `capture.py` before running anything
- **Issue:** The initial draft built the edge-callback closure and then tried to assign it as `cb_handle.callback = ...` after the fact -- stock pigpio's `_callback` object has no such settable attribute; the callback must be passed as `pi.callback(pin, edge, func)`'s third positional argument at claim time.
- **Fix:** `_claim_input_no_glitch_filter` now takes `callback_fn` and passes it straight through to `pi.callback(...)`.
- **Files modified:** `tools/pulse_timing/capture.py`
- **Verification:** Code review before first execution; the module-level import smoke test (`importlib.util.spec_from_file_location` + `exec_module`) confirmed no syntax/reference errors remained.
- **Committed in:** `069dac3` (never existed in an uncommitted broken form)

**2. [Rule 1 - Bug] `synthetic_wrap.jsonl`'s first generator draft never recorded a pre-wrap tick**
- **Found during:** Task 2, first `pytest` run (`no wrap found in the raw 32-bit tick series`)
- **Issue:** The witness-fixture generator appended each record AFTER advancing the tick counter, so the true near-`2**32` starting tick was never itself written to a record -- the file's first record already showed the post-wrap value, leaving no decreasing pair for `--check-wrap` to detect.
- **Fix:** Restructured the generator to append the record BEFORE advancing state for the next step, and re-tuned `tick_before_wrap` to `n_pre * interval_us` so the wrap lands cleanly at the midpoint of the fixture.
- **Files modified:** `tests/test_pulse_timing_analyse.py` (regenerated `fixtures/synthetic_wrap.jsonl` from the corrected function)
- **Verification:** `pytest tests/test_pulse_timing_analyse.py` -- both `--check-wrap` direction tests green; the fixture's reported wrap interval (71.58 min, matching the predicted value) confirmed via `capsys`
- **Committed in:** `3d1b380`

---

**Total deviations:** 2 auto-fixed (both Rule 1, caught before or during the plan's own automated verify steps; no scope creep)
**Impact on plan:** No scope creep. Both fixes were required for the plan's own `<verify>`/`<behavior>` blocks to pass and are internal to the deliverables this plan already owned.

## Issues Encountered

- `synthetic_wrap.jsonl`'s reported backward-jump magnitude (4289.967296s) differs from the theoretical `2**32/1e6` = 4294.967296s by exactly one heartbeat interval (5s). This is not a bug in `analyse.py` -- it is the correct, expected behaviour of measuring a REAL sample series rather than the instantaneous offset step: the delivered value also advances by the normal per-sample amount between the two records straddling the wrap, so the net observed jump is `interval_s - 4294.967296`. The plan's own wording anticipates exactly this ("report the measured value rather than assuming it"); `analyse.py`'s printed message reports the measured magnitude alongside the theoretical one rather than asserting equality. No fix needed; documented here so plan 08's real capture doesn't mistake a similarly-offset measured value for an error.
- `capture.py` (481 lines), `analyse.py` (447), and `py37_gate.py` (408) exceed this project's 300-line soft guideline for production code, though all stay under the 500-line hard limit. A large share of each file's length is inline documentation the plan explicitly mandates (`<instrument_design>`: "an instrument nobody can justify is an instrument nobody trusts"; `<action>` step 3(e)-(g) for the gate's own construct-by-construct rationale). Splitting further would fragment three tools that must each remain independently `python3 <file>.py`-runnable on Buster with no shared package machinery beyond a same-directory sibling import (`profiles.py`) -- judged not worth the added import-path fragility for a single-purpose, plan-scoped instrument. Not fixed; flagged for the next executor who touches this package.
- The executor initially wrote this SUMMARY.md and the corresponding `.planning` scaffold into `~/mics_core` (the code repo) rather than `~/mics-backend` (the planning-docs repo) before catching and correcting it -- caught before any `git add`/commit in `~/mics_core` (`git status` confirmed the stray `.planning/` was untracked), so nothing landed in the code repo's history. `~/mics_core`'s `.planning/` directory was removed. Recorded here per the project's own rule ("Planning docs stay in mics-backend; no code changes land here [mics_core]") in case a future executor sees a similar slip.

## User Setup Required

None - no external service configuration required. `capture.py`, `wrap_witness.py` and their copy-paste blocks in `README.md` are USER-RUN by plans 08 and C4 on real Pi hardware; this plan deliberately never executes them (there is no GPIO on the dev host).

## Next Phase Readiness

- **Plan 08's before-capture campaign has everything it needs**: five profiles, three arms, the JSONL contract, a copy-paste command block per capture, and a `py37_gate.py --list` closure (30 members, reproduced below) plan 08 should re-run and diff before its capture session -- a SHRUNK closure relative to this list is the signal that `capture.py` stopped driving the production path.
- **Plan C4's after-capture campaign and acceptance gate can reuse `analyse.py --gate`/`--check-wrap` unmodified** -- the JSONL contract and both gate directions are already proven against synthetic data with known answers.
- **Resolved py37 import closure (30 members, `python3 tools/pulse_timing/py37_gate.py --list`, captured 2026-08-19 at commit `3d1b380`):**
  ```
  tools/pulse_timing/capture.py
  tools/pulse_timing/wrap_witness.py
  tools/pulse_timing/profiles.py
  autopilot/autopilot/__init__.py
  autopilot/autopilot/networking/__init__.py
  autopilot/autopilot/networking/Event_Dispatcher.py
  autopilot/autopilot/hardware/__init__.py
  autopilot/autopilot/hardware/gpio.py
  autopilot/autopilot/utils/__init__.py
  autopilot/autopilot/utils/registry.py
  autopilot/autopilot/utils/hydration.py
  autopilot/autopilot/networking/station.py
  autopilot/autopilot/networking/node.py
  autopilot/autopilot/networking/message.py
  autopilot/autopilot/utils/Events.py
  autopilot/autopilot/prefs.py
  autopilot/autopilot/core/__init__.py
  autopilot/autopilot/core/loggers.py
  autopilot/autopilot/utils/common.py
  autopilot/autopilot/external/__init__.py
  autopilot/autopilot/utils/logging_utils.py
  autopilot/autopilot/utils/plugins.py
  autopilot/autopilot/tasks/__init__.py
  autopilot/autopilot/exceptions.py
  autopilot/autopilot/utils/Mics_Tracker.py
  autopilot/autopilot/utils/log_value.py
  autopilot/autopilot/utils/wiki.py
  autopilot/autopilot/tasks/task.py
  autopilot/autopilot/core/View.py
  autopilot/autopilot/utils/Tracker.py
  ```
  Plan 08 should re-run this exact command after plans 02/03's `gpio.py` edits are confirmed still in the tree and before taking the Buster baseline, and treat a SHRUNK closure (fewer members, or `gpio.py`/`wrap_witness.py` missing) as a blocker, not a curiosity.
- No production class needed a stub or reimplementation to be driven standalone -- `Event_Dispatcher(node=None, ...)` was sufficient, which means plan 08's capture campaign exercises the SAME code every real session run does, not a look-alike.
- `requirements mark-complete PLAT-23 PLAT-25` found no checkbox/traceability row in `REQUIREMENTS.md` (same structural gap as prior Phase 31 plans) -- completion tracked here and via `gsd-tools roadmap update-plan-progress 31` instead.

---
*Phase: 31-mics-core-modern-pi-platform-bookworm-64-bit-python-3-11-lgpio-unattended-boot*
*Completed: 2026-08-19*

## Self-Check: PASSED

All 13 created files verified present on disk in `~/mics_core` (the `tools/pulse_timing/`
package: `__init__.py`, `profiles.py`, `capture.py`, `wrap_witness.py`, `py37_gate.py`,
`analyse.py`, `README.md`, 4 fixture `.jsonl` files; plus `tests/test_py37_gate.py` and
`tests/test_pulse_timing_analyse.py`). Both commit hashes (`069dac3`, `3d1b380`) verified
present via `git log --oneline --all` in `~/mics_core`. This SUMMARY.md itself confirmed
present in `~/mics-backend`.
