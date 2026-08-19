---
phase: 31-mics-core-modern-pi-platform-bookworm-64-bit-python-3-11-lgpio-unattended-boot
plan: C1
subsystem: platform
tags: [clock, timestamps, tick-wrap, concurrency, calibration, tdd, plat-28, plat-29, plat-30, plat-31]

# Dependency graph
requires:
  - phase: 31-01
    provides: "phase-31-modern-pi-platform branch, /home/ido/.venvs/mics_core_dev, tools/pytest_delta.py, tests/fakes/fake_pigpio.py + the fake_pigpio fixture"
  - phase: 31-03
    provides: "stock upstream pigpio client pinned in requirements.txt; the patched client (sync_ticks/synchronize/ticks_to_timestamp) is gone"
provides:
  - "autopilot/utils/tick_extender.py -- pure, thread-safe 32->64-bit tick extension with the four-case half-range rule and MAX_OUT_OF_ORDER_US as an explicit discriminator"
  - "autopilot/utils/clock.py -- the ONE MicsClock: heartbeat, single calibrated mapping, per-call epoch offset, provenance constants, counters, loud failures"
  - "autopilot/utils/clock_calibration.py -- TickMapping in point-slope form, so a re-fit re-anchors EXACTLY (rate changes, value never does)"
  - "autopilot/utils/clock_guard.py -- PLAT-28 runtime backstop: refuse to attach to a patched GPIO client"
  - "tests/test_tick_extender.py (25 tests) and tests/test_mics_clock.py (30 tests), all green with no Pi, no pigpiod and no pigpio installed"
affects: [31-C2, 31-C3, 31-C4]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Point-slope mapping (slope, anchor_us, anchor_ns) instead of slope-intercept, so re-anchoring is bit-exact rather than approximate in floating point"
    - "extend() returns the fixed 2-tuple (value_us, ambiguous); extend_full() adds out_of_order atomically for the one caller that needs per-observation Case C detection"
    - "Structural lock proofs (instrumented __enter__, and a blocked second thread) alongside the outcome proof, because CPython 3.12 makes the outcome proof vacuous"
    - "Mutation testing every load-bearing invariant before claiming the test suite proves it"

key-files:
  created:
    - /home/ido/mics_core/autopilot/autopilot/utils/tick_extender.py
    - /home/ido/mics_core/autopilot/autopilot/utils/clock.py
    - /home/ido/mics_core/autopilot/autopilot/utils/clock_calibration.py
    - /home/ido/mics_core/autopilot/autopilot/utils/clock_guard.py
    - /home/ido/mics_core/tests/test_tick_extender.py
    - /home/ido/mics_core/tests/test_mics_clock.py
  modified: []

key-decisions:
  - "extend() returns a 2-tuple, not the 3-tuple <clock_design> §1 specifies -- the plan contradicts itself and its own Task 1 <verify> gate hard-asserts len(r) == 2. Resolved with extend_full(), which returns (value_us, ambiguous, out_of_order) atomically, so §4's non-racing requirement is met without a counters() diff."
  - "The mapping is stored in point-slope form (slope, anchor_us, anchor_ns), NOT the plan's literal b_new = (a_old*t + b_old) - a_new*t. That formula is only approximately continuous in IEEE754; point-slope makes f_new(anchor) == f_old(anchor) bit-exact, which is what the continuity test asserts."
  - "clock.py was split into three modules rather than shipping 416 lines. The plan sanctions a split and nominates the heartbeat sampler; the heartbeat is tightly coupled to the extender and the clock lock, so the mapping (clock_calibration.py) and the PLAT-28 guard (clock_guard.py) were extracted instead -- lower coupling, same line saving."
  - "Added seeds and forward counters to the extender. The plan's claim that 'the three counters plus wraps account for the whole input stream' is arithmetically false: wraps counts only the subset of Case B/D calls that rolled over. With seeds+forward, seeds+forward+duplicates+out_of_order+ambiguous_gap == calls is a checkable identity, and a test asserts it."
  - "min_span_s is measured on the TICK axis, not wall time, so the re-fit trigger is deterministic under test and independent of dev-host scheduling."
  - "MEASURED: on CPython 3.12.3 the outcome-based concurrency test cannot distinguish a locked extender from an unlocked one (wraps == 1 in 60/60 trials unlocked; 0 lost updates in 800_000 contended `+=`). Two structural lock proofs were added that DO fail deterministically without the lock."

patterns-established:
  - "TDD RED/GREEN per module, then a mutation pass: every load-bearing invariant is broken deliberately and the suite must catch it before the invariant is claimed proven"
  - "Fault / activity / reported-not-asserted counter classification stated in the module docstring, so C4 asserts only the fault class"

requirements-completed: [PLAT-29, PLAT-30]

# Metrics
duration: ~35min
completed: 2026-08-19
---

# Phase 31 Plan C1: Clean-Room Clock (TickExtender + MicsClock) Summary

**Built and proved the MICS-owned replacement for the patched pigpio clock layer: a pure four-case
32->64-bit tick extender that reads a >half-range forward gap FORWARD (flagged, non-latching) instead
of emitting the -2147.48 s step the naive rule produces, and a single calibrated
tick<->CLOCK_MONOTONIC clock whose re-fits change the rate and never the value, whose epoch offset is
recomputed per call, and which never hands back a raw tick — all green on a dev host with no Pi, no
pigpiod and no pigpio installed.**

## Performance

- **Duration:** ~35 min (08:05–08:40 UTC)
- **Tasks:** 2 completed (both TDD)
- **Commits:** 5
- **Files created:** 6 (4 modules, 2 test modules); **files modified:** 0

## Task Commits

1. **Task 1: TickExtender** — TDD: `5710d3d` (test, RED) → `f9c8aca` (feat, GREEN) → `a898f85` (fix:
   real lock proofs + counter accounting, after a mutation pass showed the concurrency test was vacuous)
2. **Task 2: MicsClock** — TDD: `fa6ea75` (test, RED) → `9fc8837` (feat, GREEN)

All in `/home/ido/mics_core` on `phase-31-modern-pi-platform`. `main` untouched; nothing pushed.

## Public surface, verbatim (C2 and C4 are written against this)

### `autopilot/autopilot/utils/tick_extender.py` (179 lines)

```
TICK_WRAP           = 2 ** 32          # 4294.967296 s = 71.582788 min
TICK_HALF           = 2 ** 31
MAX_OUT_OF_ORDER_US = 2_000_000

class TickExtender:
    __init__(self)
    extend(self, tick32)        -> (value_us: int, ambiguous: bool)
    extend_full(self, tick32)   -> (value_us: int, ambiguous: bool, out_of_order: bool)
    counters(self)              -> dict   # wraps, out_of_order, duplicates,
                                          # ambiguous_gap, seeds, forward
    snapshot(self)              -> (wraps: int, last_tick: int)
    # raises ValueError naming the 32-bit field for tick32 outside [0, 2**32)
```

**The return shape is `(int, bool)`, confirmed.** `<clock_design>` §1 specifies a 3-tuple while Task
1's `<behavior>`, `<done>` and `<verify>` all specify a 2-tuple (the verify gate hard-asserts
`len(r) == 2`). The verify gate is authoritative, so `extend()` is the 2-tuple; `extend_full()`
carries the third element **atomically with the value it describes**, which is what §4's correction
actually requires — `MicsClock.observe()` never takes a `counters()` diff around `extend()`.

**`MAX_OUT_OF_ORDER_US = 2_000_000` (2 s), two-sided justification as required.** *Lower side:* the
only two feeders are the notify thread and the heartbeat thread, both inside one process reading one
socket, so real inter-thread skew is microseconds to low milliseconds — 2 s is ~3 orders of magnitude
of headroom over the worst plausible scheduler stall. *Upper side:* it is ~1000x below the 2147.48 s
backward step the alternative reading of a half-range-crossing delta would imply. Anything past the
bound is not a backward step; it is a forward gap the field is too narrow to express.

### `autopilot/autopilot/utils/clock.py` (299 lines)

```
TS_HARDWARE = "hardware"
TS_SOFTWARE = "software"
DEFAULT_HEARTBEAT_S    = 600.0
DEFAULT_MAX_BRACKET_NS = 2_000_000

class ClockNotReady(Exception)      # not calibrated yet
class ClockFault(Exception)         # this observation is untrustworthy; carries no value
class PatchedClientError(Exception) # re-exported from clock_guard

class MicsClock:
    __init__(self, heartbeat_s=600.0, window=64, min_span_s=60.0,
             max_bracket_ns=2_000_000, max_ppm=200.0)
    attach(self, pi)                -> None      # raises PatchedClientError / TypeError / RuntimeError
    stop(self)                      -> None      # idempotent
    observe(self, tick32)           -> int       # ns on the monotonic timeline; or raises
    now_mono_ns(self)               -> int
    to_utc_ns(self, t_mono_ns)      -> int
    to_utc_iso(self, t_mono_ns)     -> str       # tz-aware ISO 8601, local zone
    counters(self)                  -> dict
    mapping_generation              -> int       # read-only property
    _heartbeat_once(self)           -> bool      # public-for-tests
    # attributes: heartbeat_s, max_bracket_ns

get_clock()             -> MicsClock   # lazily-created module singleton
reset_clock_for_tests() -> None
```

### `autopilot/autopilot/utils/clock_calibration.py` (138 lines)

```
NS_PER_US = 1000.0 ; DEFAULT_WINDOW = 64 ; DEFAULT_MIN_SPAN_S = 60.0 ; DEFAULT_MAX_PPM = 200.0
BOOTSTRAP = "bootstrap" ; REFIT = "refit" ; REJECTED = "rejected" ; PENDING = "pending"

fit_slope(samples) -> float or None

class TickMapping:
    __init__(self, window=64, min_span_s=60.0, max_ppm=200.0)
    ready                       -> bool   (property)
    generation                  -> int    (property)
    record(self, tick_us, mono_ns) -> str  # one of the four outcome constants
    to_ns(self, tick_us)        -> float  # lock-guarded read AT CALL TIME
    snapshot(self)              -> (slope, anchor_us, anchor_ns) or None
    counters(self)              -> dict   # refits, fit_rejected, last_fit_ppm
```

### `autopilot/autopilot/utils/clock_guard.py` (40 lines)

```
PATCHED_ATTRIBUTES = ("synchronize", "ticks_to_timestamp")
PATCHED_KWARG      = "sync_ticks"
class PatchedClientError(Exception)
guard_patched_client(pi) -> None   # raises PatchedClientError naming the offending name
```

## Chosen defaults, one sentence of justification each

| Default | Value | Why |
|---|---|---|
| `heartbeat_s` | **600.0 s** | Comfortably inside PLAT-29's `TICK_HALF/1e6 = 2147.48 s` bound (3.6x margin), one socket round trip per ten minutes, and fresh enough to re-fit meaningfully within a session. The constructor **raises `ValueError` naming PLAT-29** above the bound, so it cannot be loosened by editing a default. |
| `window` | **64** samples | At the 600 s default that is a ~10.7-hour rolling window — long enough that the fit is dominated by the crystal rather than by bracket noise, short enough to follow a slow thermal drift. |
| `min_span_s` | **60.0 s** | A fit over less than a minute is dominated by the few-microsecond bracket, so no fit is attempted until the window spans a minute **on the tick axis** (tick axis, not wall time, so the trigger is deterministic under test). |
| `max_bracket_ns` | **2_000_000** (2 ms) | Measured brackets on this dev host are 3.0–6.9 µs (below); 2 ms is ~300x that, so it rejects only a genuinely descheduled sample and never normal jitter. Bracket noise moves the mapping's offset only — common-mode, cancels in every interval. |
| `max_ppm` | **200.0** | A Pi crystal is specified to tens of ppm and both counters run off it, so 200 ppm is generous for a real fit and still rejects a fit corrupted by a bad sample; a rejection keeps the previous mapping and does **not** move `mapping_generation`. |

## `counters()` — the complete key set (C4's PLAT-32 read-out) and its three classes

| Key | Class | Source |
|---|---|---|
| `ambiguous_gap` | **fault** — zero on a clean run, C4 asserts it | extender (Case D) |
| `heartbeat_missed` | **fault** | clock |
| `convert_failed` | **fault** | clock |
| `monotonic_violation` | **fault** | clock |
| `wraps` | activity | extender |
| `out_of_order` | activity | extender (Case C) |
| `duplicates` | activity | extender (Case A) |
| `seeds` | activity | extender (first call) |
| `forward` | activity | extender (Case B) |
| `refits` | activity | mapping |
| `bracket_rejected` | **reported, not asserted** | clock |
| `fit_rejected` | **reported, not asserted** | mapping |
| `last_fit_ppm` | diagnostic (float) | mapping |
| `last_bracket_ns` | diagnostic (int) | clock |
| `mapping_generation` | diagnostic (int) | mapping |

15 keys. **C4 must assert only the four fault counters.** A blanket "all zero" claim contradicts this
plan's own tests: the re-fit-rejection scenario deliberately drives `fit_rejected` to 1, and `wraps` /
`out_of_order` / `duplicates` / `seeds` / `forward` / `refits` all move on a correct run.
`seeds + forward + duplicates + out_of_order + ambiguous_gap == number of extend() calls` is an
exact identity and is asserted by a test.

## Measured calibration (so C4 has a reference for the real hardware fit)

Driven through `fake_pigpio` with the tick derived from the real `CLOCK_MONOTONIC` at exactly
1 µs/µs, 30 samples over 3.0 s, `min_span_s=1.0`:

```
fitted slope          : 999.992692 ns/us
last_fit_ppm          : -7.31 ppm
refits                : 21     fit_rejected: 0     bracket_rejected: 0
bracket ns min/med/max: 3018 / 3541 / 6875
fault counters        : all zero
mapping_generation    : 22
```

Two caveats for C4. (1) The **-7.31 ppm is an artifact of the harness**, not of the algorithm: the
fake's tick is *derived* from `CLOCK_MONOTONIC` with integer-microsecond truncation and is read
inside a ~3.5 µs bracket, so the residual is quantisation, not oscillator error. On the rig the tick
is an independent 1 MHz hardware counter and the fit should land far closer to 1000.000. (2) The
**3–7 µs bracket is a function call, not a socket round trip** — expect the real `pigpiod` round trip
to be tens to hundreds of microseconds, still two to three orders of magnitude inside
`max_bracket_ns`.

## Nothing in the pilot import path imports the clock yet — deliberately

Verified with the plan's own counted scan (verification step 5, exit 0):

```
pilot-path importers of utils.clock: []
```

`autopilot/` behaves exactly as it did before this plan. C2 wires the clock into both event paths;
C3 attaches it to a stock `pigpio.pi()` in `pilot.py`.

## Verification (all fresh, this run)

| Gate | Result |
|---|---|
| `pytest -q tests/test_tick_extender.py tests/test_mics_clock.py` | **55 passed** (25 + 30) |
| Full tree `pytest tests/` | **187 failed, 353 passed** — 187 is the frozen baseline, unchanged |
| `tools/pytest_delta.py` | `new failures: 0`, exit 0 |
| `tools/check_tree_integrity.py --strict` | `35 closure members, 30 protected files, 0 violations`, exit 0, **no manifest edit** |
| Task 1 inline verify (identity, wrap +1500 µs, Case C not a wrap, Case D forward+flagged+non-latching, discriminator both sides, duplicates, range guard, concurrent `wraps == 1`) | pass |
| Task 2 inline verify (single `CLOCK_REALTIME` site, PLAT-29 bound, patched-client refusal, `ClockNotReady`, exact 1e9 ns interval, complete counters, zero fault counters) | pass |
| `CLOCK_REALTIME` counted scan under `autopilot/autopilot/` | exactly `['utils/clock.py']` |
| Banned strings in `clock.py` (`import pigpio`, `sync_offset`, `def synchronize`, `CLOCK_MONOTONIC_RAW`) | 0 / 0 / 0 / 0 |
| Python 3.7 grammar gate + the four constructs `feature_version` waves through | pass on **all four** modules (the plan's script covers two; extended to the two new ones) |
| Line budgets | `tick_extender.py` **179** (< 180), `clock.py` **299** (< 300) |

### Mutation pass — every load-bearing invariant was broken deliberately and the suite caught it

| Mutation | Caught by |
|---|---|
| Naive coefficient swap (no re-anchoring) | `test_a_refit_changes_the_rate_and_never_the_value` |
| Delivered series not clamped on an out-of-order sample | `test_a_genuine_out_of_order_sample_is_clamped_and_does_not_raise` |
| Heartbeat stops feeding the extender (PLAT-29 made decorative) | `test_a_quiet_stretch_longer_than_a_wrap_loses_nothing_when_the_heartbeat_runs` + 4 re-fit tests |
| Epoch offset cached once (the by-value snapshot defect) | both wall-clock-step cases + `test_the_epoch_offset_is_recomputed_per_call` |
| Case C not distinguished from a real monotonic violation | `test_a_genuine_out_of_order_sample_is_clamped_and_does_not_raise` |
| `with self._lock:` removed from `extend_full()` | the two structural lock tests (**not** the outcome test — see below) |

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Plan self-contradiction] `extend()` return arity: 2-tuple vs 3-tuple**
- **Found during:** Task 1, before writing a line of code
- **Issue:** `<clock_design>` §1 states `extend(tick32) -> (value_us, ambiguous, out_of_order)` and §4
  depends on "the third element of `extend()`'s return". Task 1's `<behavior>` ("Every return is a
  2-tuple `(int, bool)`"), its `<done>`, the `<output>` section, and the Task 1 `<verify>` gate
  (`len(r) == 2`, `sys.exit` otherwise) all state a 2-tuple. Both cannot hold.
- **Fix:** `extend()` returns the 2-tuple (the verify gate is authoritative and was run as written);
  `extend_full()` returns the 3-tuple and is what `MicsClock.observe()` calls. §4's actual
  requirement — that the out-of-order flag arrive **atomically with the value**, never via a
  `counters()` diff that races the heartbeat thread — is fully met.
- **Files:** `tick_extender.py`, both test modules
- **Committed in:** `f9c8aca`

**2. [Rule 1 - Plan formula is not exact] Mapping stored point-slope, not slope-intercept**
- **Found during:** Task 2, designing the continuity test
- **Issue:** The plan's re-anchor formula `b_new = (a_old*t_anchor + b_old) - a_new*t_anchor` gives
  `f_new(t_anchor) == f_old(t_anchor)` only in exact arithmetic. In IEEE754, `x + (y - x)` is not
  generally `y`, so the plan's own requirement ("identical before and after, **to the nanosecond**")
  would be met only approximately, and the test asserting it would be asserting a tolerance.
- **Fix:** store `(slope, anchor_us, anchor_ns)` and evaluate `slope*(t - anchor_us) + anchor_ns`. A
  re-fit sets `anchor_ns` to the OLD mapping evaluated at the new anchor, so `f_new(anchor)` is
  literally that same float — bit-exact. The test asserts `==`, not a tolerance, and passes.
- **Files:** `clock_calibration.py`
- **Committed in:** `9fc8837`

**3. [Rule 3 - Blocking: line budget] `clock.py` split into three modules**
- **Found during:** Task 2
- **Issue:** A single `clock.py` implementing everything came to **416 lines**, past the plan's 300
  gate and the project's coding standard.
- **Fix:** The plan sanctions splitting and nominates "the heartbeat sampler" as the third module.
  The heartbeat is the *most* coupled piece (it must share the extender and the clock's lock with
  `observe()`), so the two genuinely low-coupling pieces were extracted instead:
  `clock_calibration.py` (the mapping: window, fit, re-anchor, generation) and `clock_guard.py` (the
  PLAT-28 runtime backstop). `clock.py` is now 299 lines and still owns the one instance of each.
- **Files:** `clock.py`, `clock_calibration.py`, `clock_guard.py`
- **Committed in:** `9fc8837`

**4. [Rule 2 - Missing critical accounting] `seeds` and `forward` counters added**
- **Found during:** Task 1
- **Issue:** `<clock_design>` §7 asserts "the three counters plus `wraps` account for the whole input
  stream". That is arithmetically false: `wraps` counts only the subset of Case B/D calls on which
  the modular counter rolled over, and the seeding call is counted nowhere. The identity C4's PLAT-32
  table depends on could not be checked.
- **Fix:** added `seeds` (the first call) and `forward` (Case B) to the extender's counters, making
  `seeds + forward + duplicates + out_of_order + ambiguous_gap == calls` an exact, tested identity.
  Both are **activity** counters. `MicsClock.counters()` plumbs them through.
- **Files:** `tick_extender.py`, `clock.py` docstring, `tests/test_tick_extender.py`
- **Committed in:** `a898f85`

**5. [Rule 1 - Vacuous test] The concurrency proof had no teeth on CPython 3.12**
- **Found during:** Task 1, mutation pass
- **Issue:** The plan's two-thread `wraps == 1` proof passed **identically with the lock removed**.
  Measured on this dev host (CPython 3.12.3): unlocked `extend()` gives `wraps == 1` in **60/60**
  trials at `sys.setswitchinterval(1e-6)`, and a plain contended `d["n"] += 1` loses **0 of 800_000**
  increments. The specializing interpreter makes these read-modify-writes incidentally atomic, so no
  outcome test on this host can distinguish locked from unlocked. On Buster's Python 3.7.3 (plan 08's
  baseline) it would not be, which is exactly why the lock stays.
- **Fix:** kept the outcome test, labelled it necessary-but-not-sufficient with the measurement in
  its docstring, and added two **structural** proofs that fail deterministically without the lock:
  `extend()` acquires it exactly once per call (instrumented `__enter__`), and a second thread blocks
  while it is held. Both were verified to fail with `with self._lock:` removed and pass with it.
- **Files:** `tick_extender.py` (docstring), `tests/test_tick_extender.py`
- **Committed in:** `a898f85`

**6. [Rule 1 - Test bugs, mine] Two defective assertions in `test_mics_clock.py`**
- **Found during:** Task 2 GREEN
- **Issue:** (a) the end-to-end wrap test asserted `seen[-1] - seen[0] == 10_000_000_000` ns for ten
  1000 µs steps, which is 10_000_000 ns. (b) the wall-clock-step test re-observed an **earlier** tick
  after a later one to prove the monotonic timeline had not moved — but `observe()` clamps a genuine
  out-of-order sample **by design**, so the round trip could never hold.
- **Fix:** corrected the arithmetic; restated the step test on the **latest** tick (a duplicate, Case
  A), which proves the same property without fighting the clamp.
- **Files:** `tests/test_mics_clock.py`
- **Committed in:** `9fc8837`

### Corrections to the plan's own text, recorded for the next reader

- The plan's `<verified_facts>` and design are otherwise accurate and were used as written. The
  quiet-period numbers it corrected on 2026-08-17 (`3_000_000_000` µs for the negative control,
  interleaved heartbeats for the positive one) are right: `3_000_000_000` lands in the Case D window
  `(2_147_483_648, 4_292_967_296]`, and the earlier `2_100_000_000` would have taken Case B.
- `min_span_s` is measured on the **tick axis**. The plan does not say which axis; wall time would
  have made the re-fit trigger dependent on dev-host scheduling and untestable without sleeping.

---

**Total deviations:** 6 auto-fixed (2 plan self-contradictions, 1 non-exact plan formula, 1 blocking
line budget, 1 missing accounting, 1 vacuous + 2 defective tests). **Zero Rule 4 escalations.**
**Impact on plan:** no scope change. Every `must_have`, `artifact`, `key_link`, `<done>` clause and
`<verification>` step is satisfied as written; two extra modules and two extra counters exist.

## Issues Encountered

- None blocking. The only surprise was the CPython 3.12 atomicity finding above, which changed how
  the concurrency property is proven but not the implementation.

## User Setup Required

None.

## Next Phase Readiness

- **C2** can import `from autopilot.utils.clock import get_clock, TS_HARDWARE, TS_SOFTWARE,
  ClockNotReady, ClockFault` and stamp both event paths. `to_utc_iso()` exists so `localize_tz`
  becomes a two-line delegation, as the plan promised.
- **C3** attaches via `get_clock().attach(pi)` against a **stock** `pigpio.pi()`. If the rig's
  virtualenv still carries the patched client, `attach()` raises `PatchedClientError` naming the
  attribute rather than silently building on it.
- **C4** reads `counters()`; it must assert only the **four fault counters** are zero. The measured
  slope and bracket figures above are the dev-host reference to compare the rig's real fit against.
- **Carried forward, unchanged:** the 187 pre-existing failures remain pigpio-blocked
  (`Event_Dispatcher.py:3`). This plan adds 55 passing tests and zero new failures; it does not and
  cannot reduce that count, because nothing here is wired into the pilot import path yet.

---
*Phase: 31-mics-core-modern-pi-platform-bookworm-64-bit-python-3-11-lgpio-unattended-boot*
*Completed: 2026-08-19*

## Self-Check: PASSED

All 6 created source/test paths verified present on disk; the SUMMARY itself verified present; all
5 commit hashes (`5710d3d`, `f9c8aca`, `a898f85`, `fa6ea75`, `9fc8837`) verified present in
`~/mics_core` via `git log --oneline --all`; test counts re-measured (25 + 30 = 55 passed); branch
re-asserted as `phase-31-modern-pi-platform`.
