---
phase: 31-mics-core-modern-pi-platform-bookworm-64-bit-python-3-11-lgpio-unattended-boot
plan: C1
type: execute
wave: 4
depends_on: ["31-01", "31-03"]
files_modified:
  - /home/ido/mics_core/autopilot/autopilot/utils/tick_extender.py
  - /home/ido/mics_core/autopilot/autopilot/utils/clock.py
  - /home/ido/mics_core/tests/test_tick_extender.py
  - /home/ido/mics_core/tests/test_mics_clock.py
autonomous: true
requirements: [PLAT-29, PLAT-30]
must_haves:
  truths:
    - "The 32-bit pigpio tick is reconstructed into a monotonic 64-bit microsecond counter that survives a wrap"
    - "A quiet stretch longer than a wrap cannot lose a wrap, because a heartbeat observes the tick at no more than half the wrap period"
    - "The wrap counter is correct when the heartbeat thread and the notify thread observe ticks concurrently"
    - "ONE calibrated tick to CLOCK_MONOTONIC relation exists, is re-fit periodically, and is read at call time by every caller — no scalar snapshot copies"
    - "A re-fit changes the RATE and never the VALUE, so the mapped timeline stays continuous and non-decreasing across a re-fit"
    - "A wall-clock step moves the derived UTC by exactly the step and moves no interval"
    - "Every failure is loud and counted; the clock never silently hands back a raw tick"
    - "All of the above is proven on a dev host with no Pi, no pigpiod and no pigpio installed"
  artifacts:
    - path: "/home/ido/mics_core/autopilot/autopilot/utils/tick_extender.py"
      provides: "Pure, thread-safe 32->64-bit tick extension with a half-range wrap rule and out-of-order tolerance"
      min_lines: 60
      contains: "class TickExtender"
    - path: "/home/ido/mics_core/autopilot/autopilot/utils/clock.py"
      provides: "The one MICS clock: heartbeat, calibrated tick<->CLOCK_MONOTONIC mapping, epoch offset, provenance constants, counters, loud failures"
      min_lines: 150
      contains: "CLOCK_REALTIME"
    - path: "/home/ido/mics_core/tests/test_tick_extender.py"
      provides: "Wrap, multi-wrap, out-of-order, duplicate and concurrency proofs against fake_pigpio"
      min_lines: 80
    - path: "/home/ido/mics_core/tests/test_mics_clock.py"
      provides: "Heartbeat, quiet-period-longer-than-a-wrap, continuity-preserving re-fit, clock-step immunity, loud-failure and single-offset proofs"
      min_lines: 120
  key_links:
    - from: "tests/fakes/fake_pigpio.py fire_edge() / simulate_wrap()"
      to: "TickExtender.extend()"
      via: "the injected 32-bit tick, delivered as pigpio's third positional callback argument"
      pattern: "fire_edge"
    - from: "MicsClock heartbeat thread"
      to: "pi.get_current_tick()"
      via: "a bracketed poll at <= half the 71.6-minute wrap period, fed through the SAME TickExtender under the SAME lock"
      pattern: "get_current_tick"
    - from: "MicsClock.observe()"
      to: "the calibrated mapping coefficients"
      via: "a lock-guarded read at call time, never a value copied out to a caller"
      pattern: "_mapping"
    - from: "MicsClock.to_utc_ns()"
      to: "CLOCK_REALTIME"
      via: "an epoch offset recomputed per call, in the only module under autopilot/ that names CLOCK_REALTIME"
      pattern: "CLOCK_REALTIME"
---

<objective>
Stage 3, part 1. Build the clean-room clock, and prove it against a wrap before anything depends on
it.

Purpose: `31-REVISED-SCOPE.md` §2 is a dated, falsifiable claim about a running system — the
deployed patched pigpio client jumps every GPIO timestamp **backwards by 4294.97 s every 71.6
minutes**, roughly 20 times a day, because its callback thread converts ticks with **no wrap
detection** (`pigpio.py:1206-1207`) and holds the sync offset **by value** (`:5264` -> `:1157`) so
the wrap-detecting re-sync on the `pi` object never reaches it. Every one of those lines is an
Autopilot patch. PLAT-28 deletes them. This plan writes what replaces them: a MICS-owned,
git-tracked, unit-tested clock that the rest of the phase reads.

Two modules, because they are two different kinds of thing and because a 300-line file is a file
nobody re-reads:

- `utils/tick_extender.py` — **pure arithmetic**, no threads of its own, no I/O, no clock reads.
  Turns a stream of 32-bit ticks seen in arrival order into a monotonic 64-bit microsecond counter.
  This is PLAT-29 and it is the part that is easy to get subtly wrong.
- `utils/clock.py` — **the one shared clock object**. Owns a `TickExtender`, the heartbeat thread,
  the calibrated tick <-> `CLOCK_MONOTONIC` relation, the per-call epoch offset, the provenance
  constants and the counters. This is PLAT-30.

Nothing is wired into the pilot here. C2 wires it into both event paths; C3 attaches it to a stock
`pigpio.pi()` in `pilot.py`. This plan is developed entirely on the dev host against plan 01's
`fake_pigpio` notification stream — no Pi, no `pigpiod`, no `pigpio` installed.

Output: two modules, two test modules, and a machine proof that a simulated wrap and a simulated
quiet-period-longer-than-a-wrap both come out the far side monotonic.
</objective>

<execution_context>
@/home/ido/.claude/get-shit-done/workflows/execute-plan.md
@/home/ido/.claude/get-shit-done/templates/summary.md
</execution_context>

<context>
@.planning/PROJECT.md
@.planning/ROADMAP.md
@.planning/STATE.md
@.planning/phases/31-mics-core-modern-pi-platform-bookworm-64-bit-python-3-11-lgpio-unattended-boot/31-REVISED-SCOPE.md
@.planning/phases/31-mics-core-modern-pi-platform-bookworm-64-bit-python-3-11-lgpio-unattended-boot/CONTEXT.md
@.planning/phases/31-mics-core-modern-pi-platform-bookworm-64-bit-python-3-11-lgpio-unattended-boot/31-VALIDATION.md
@.planning/phases/31-mics-core-modern-pi-platform-bookworm-64-bit-python-3-11-lgpio-unattended-boot/31-01-SUMMARY.md
@.planning/phases/31-mics-core-modern-pi-platform-bookworm-64-bit-python-3-11-lgpio-unattended-boot/31-03-SUMMARY.md

**Read `31-REVISED-SCOPE.md` §2 and §3 first, then `CONTEXT.md` §13.** §2 is the defect. §3 is the
design. §13 is the user-stated invariant this plan exists to make structurally true rather than
true-at-startup-and-decaying. `31-RESEARCH.md`'s lgpio material does **not** apply.

**Read `31-01-SUMMARY.md` before writing a single test.** It records the fake's public control API
(`fire_edge`, `simulate_wrap`, `set_tick`, `advance_tick`, `registration_count`) verbatim. Every
assertion in this plan is of the form "inject a tick, read a known 64-bit value back out", and all
of them are written against that API. Do not re-derive it from this plan's prose.

<repo_boundary>
ALL code changes land in `/home/ido/mics_core` on branch **`phase-31-modern-pi-platform`**.
NEVER modify `/home/ido/mics-backend` source — only its `.planning/` documents.
</repo_boundary>

<pi_rules>
ABSOLUTE. These override anything else in this plan:
- **NEVER run git on the Pi.** No commit/merge/push/pull/checkout/reset. No `rsync --delete`.
- **NEVER start or stop the pilot process. NEVER run any Python file on the Pi.**
- Pi log files are 0 bytes **by design**. Never "fix" them.
- `Message` and `hardware_state` classes are **off limits** to every sweep, refactor and lint pass.
  Neither is touched by this plan; do not go near them.
- SSH for reading/grepping is fine: `ssh -i ~/.ssh/pi_mics pi@132.77.72.28`.
- RTK-proxied grep can render a matching line blank. Re-verify every "unused"/"absent" claim with a
  counted `python3 -c` that prints `text.count(...)`, never a silent grep.
- **Do NOT `pip install pigpio` on the dev host.** Plan 01 deliberately kept it out of
  `requirements-dev.txt` so a test cannot import the real library by accident and pass against
  something the rig does not run.
</pi_rules>

<integrity_gate>
`cd /home/ido/mics_core && python3 tools/check_tree_integrity.py --strict` must exit 0 after EVERY
task. **NEVER `--rebaseline`.**

**None of this plan's four files is in the protected manifest** — verified 2026-08-17 against
`tools/tree_protect_list.json`, which carries 30 `baseline_sha256` entries, of which the only
clock-adjacent one is `autopilot/autopilot/networking/Event_Dispatcher.py` (C2's, not this plan's).
So `--strict` must be green at the end of each task with no manifest edit at all. If it is not, the
task went outside its file list.

`--final` is a separate, stricter gate and is expected to fail until C3 retires F3. Do not chase it
here.
</integrity_gate>

<verified_facts>
Verified; do not re-derive. Sources named so each can be re-checked.

| Fact | Value | Source |
|---|---|---|
| Notification record | `MSG_SIZ = 12`, `struct.unpack('HHII', msgbuf)` -> `(seq, flags, tick, level)` | deployed client, read 2026-08-17 |
| Tick width | **32 bits** — an `I` in the wire format. A 64-bit OS does not widen it | `31-REVISED-SCOPE.md` §2 |
| Wrap period | `2**32 / 1e6` = **4294.967296 s** = **71.582788 min** | arithmetic on the above |
| Dispatch | `_callback_thread.run()` -> `for cb in self.callbacks:` — ONE thread, ALL gpios, **sequential, in registration order** | deployed client |
| Callback signature | `func(gpio, level, tick)` — 3 positional args (stock pigpio, unchanged) | PLAT-27(a), corrected 2026-08-17 |
| Heartbeat source | `pi.get_current_tick()` — a socket round trip, so it must be bracketed | PLAT-29 |
| Underlying counter | The BCM System Timer is a **64-bit** free-running 1 MHz counter (`CLO`/`CHI`); pigpio exposes only the low half | `31-REVISED-SCOPE.md` §3 |
| `autopilot/` has no `clock.py` today | confirmed 2026-08-17: `autopilot/autopilot/utils/` contains no `clock.py` | direct `ls` |
| `CLOCK_REALTIME` sites under `autopilot/` today | **zero** — confirmed 2026-08-17 by a counted scan | direct scan |
| `localize_tz` today | `utils/common.py:329-334`, `datetime.strptime(time_str, "%Y-%m-%dT%H:%M:%S.%f")` | direct read |

**`localize_tz` is NOT this plan's to change.** C2 owns `utils/common.py`. What this plan owes C2 is
`to_utc_iso()` on the clock, so C2's `localize_tz` is a two-line delegation.
</verified_facts>

<clock_design>
## The design, stated before the code, because three parts of it are non-obvious

### 1. The half-range wrap rule, not `if tick < last: wraps += 1`

`31-REVISED-SCOPE.md` §3 states the naive rule, and it is correct **for a strictly ordered stream**.
The stream here is not quite strictly ordered: the notify thread and the **heartbeat thread** both
feed the extender, and a heartbeat sample taken microseconds before an edge can reach the extender
microseconds *after* it. Under the naive rule that single 50 µs backward step would be counted as a
**wrap** and every subsequent timestamp would be 4294.97 s too late — the exact defect this phase
exists to delete, reintroduced by our own code.

Use the standard half-range rule instead:

```
delta_forward = (tick32 - last_tick) & 0xFFFFFFFF
if delta_forward < 2**31:                 # ordinary forward progress, wrap included
    if tick32 < last_tick:
        wraps += 1
    last_tick = tick32
    return wraps * 2**32 + tick32
else:                                     # backward by less than 2**31: out of order or duplicate
    out_of_order += 1
    epoch = wraps - 1 if tick32 > last_tick else wraps
    return epoch * 2**32 + tick32         # do NOT advance last_tick, do NOT count a wrap
```

**The price of the rule, and it is the reason PLAT-29 has a heartbeat clause:** a gap larger than
`2**31` µs = **35.79 minutes** between two consecutive observations is *structurally ambiguous* —
the extender cannot tell a 36-minute forward jump from a backward one. That is not a defect of the
rule; it is the information content of a 32-bit field. The heartbeat is what guarantees the gap is
never that large.

### 2. The heartbeat interval is bounded by construction, not by convention

PLAT-29: "no more than half the 71.6 min wrap period". Half is **2147.48 s**. The constructor
**raises `ValueError`** naming PLAT-29 if asked for a longer interval, so the bound cannot be
loosened by editing a default. Ship the default at **600 s (10 minutes)** — comfortably inside the
bound, cheap (one socket round trip every ten minutes), and it also keeps the calibration window
fresh enough to re-fit meaningfully within a session.

The heartbeat sample MUST go through the **same** `TickExtender` under the **same** lock as the
notify thread. A heartbeat that read `get_current_tick()` into a separate variable and compared it
locally would observe the wrap and fail to record it, which is precisely the shape of the bug being
replaced.

### 3. The mapping: bracketed sampling, least squares, and continuity-preserving re-fits

The relation is `t_mono_ns = a * tick64_us + b`, with `a` ideally exactly `1000.0`. Both counters are
free-running off the same crystal, so `a` is near-fixed; the fit exists to absorb the small residual
and to give `b` a real value.

**Bracketing.** `pi.get_current_tick()` is a socket round trip. Read `CLOCK_MONOTONIC` immediately
before and immediately after, use the midpoint, and record the bracket width. Reject the sample if
the bracket exceeds `max_bracket_ns` (default **2 ms**) and count `bracket_rejected`. Bracket noise
affects **`b` only**, which is common-mode: it shifts every event identically and therefore does not
touch a single interval. Say that in the module docstring — it is the property the science depends
on, and it is the honest answer to "but the socket round trip is jittery".

**Re-fitting.** Keep a rolling window of the last `window` (default 64) accepted samples. Re-fit when
the window holds >= 2 samples spanning >= `min_span_s` (default 60 s). Reject a fit whose slope
deviates from 1000.0 ns/µs by more than `max_ppm` (default 200 ppm), or whose slope is <= 0; count
`fit_rejected`, log loudly, and keep the previous mapping.

**Continuity is mandatory and is the part a naive implementation gets wrong.** Installing a new
`(a, b)` pair naively steps the output at the switch-over, which would put a backward jump into the
very series C4 asserts has none. So a re-fit is applied **re-anchored**: pick `t_anchor` = the most
recently observed `tick64`, and set

```
b_new = (a_old * t_anchor + b_old) - a_new * t_anchor
```

so `f_new(t_anchor) == f_old(t_anchor)` exactly. **A re-fit may change the rate; it may never change
the value.** Assert it in a test.

**Bootstrap.** Before the first accepted bracketed sample there is no mapping and `observe()` raises
`ClockNotReady`. After the first, bootstrap with `a = 1000.0` and `b` from that sample. It never
returns a raw tick — that silent revert (`pigpio.py:1214`) is the thing PLAT-30 names.

### 4. Failure policy: degrade to SOFTWARE, never to a raw tick, always counted and flagged

Three distinct failure classes, three distinct behaviours, all loud:

| Class | Exception | Meaning | What callers do (C2) |
|---|---|---|---|
| Not yet calibrated | `ClockNotReady` | first seconds after `attach()` | fall back to `now_mono_ns()`, mark the event **software**-stamped, count |
| Mapping fault | `ClockFault` | the extended tick went backwards, or the mapping is gone after having existed | same, plus a loud log at the 1/10/100/every-500 cadence |
| Patched client | `PatchedClientError` | the loaded `pigpio` carries `synchronize` / `ticks_to_timestamp` / accepts `sync_ticks=` | refuse to `attach()` at all — this is the PLAT-28 runtime guard |

Degrading to a **software-read `CLOCK_MONOTONIC`** that is *marked as software* (PLAT-31) is honest
and analysable. Degrading to a **raw tick presented as a timestamp** is the deployed defect. The
difference is the whole point, and a test asserts the clock never does the second.

### 5. One object, read at call time

`get_clock()` returns a module-level singleton. `observe()` reads the mapping coefficients **under
the lock at call time**. There is no accessor that hands a caller a coefficient, an offset or a
`_sync_offset`-shaped scalar to hold — that is the `pigpio.py:5264` -> `:1157` defect written down.
The machine form of this requirement is `mapping_generation`, an integer incremented on every
installed fit: a test forces a re-fit and asserts that two *independent* callers both observe the
new generation on their next call.

`epoch_offset_ns()` is recomputed per call as
`clock_gettime_ns(CLOCK_REALTIME) - clock_gettime_ns(CLOCK_MONOTONIC)` — two vDSO reads, tens of
nanoseconds, and the only form that stays correct across a wall-clock step. `clock.py` must be the
**only** module under `autopilot/` that names `CLOCK_REALTIME`; a counted scan asserts it.

**Do not switch to `CLOCK_MONOTONIC_RAW`.** `CLOCK_MONOTONIC` is *slewed* by NTP but never stepped
and never runs backwards. For this rig the slew is desirable — chrony's frequency discipline improves
the long-run rate accuracy of inter-event intervals — and the absence of steps is what makes 24/7
safe. Write that in the docstring so nobody "fixes" it.

### 6. Provenance constants live here (PLAT-31's vocabulary, C2's plumbing)

`TS_HARDWARE = "hardware"` and `TS_SOFTWARE = "software"`, exported from `clock.py`. C2 stamps every
dispatched event with one of them. Defining them once, here, is what stops two spellings reaching
Elasticsearch.

### 7. Counters (the surface C4's PLAT-32 accounting reads)

`counters()` returns a plain dict, safe to log and to serialise: `wraps`, `out_of_order`,
`duplicates`, `ambiguous_gap`, `heartbeat_missed`, `bracket_rejected`, `fit_rejected`, `refits`,
`convert_failed`, `monotonic_violation`, plus `last_fit_ppm`, `last_bracket_ns`,
`mapping_generation`. **`ambiguous_gap` is the load-bearing one**: it increments whenever two
consecutive observations are more than `2**31` µs apart, i.e. whenever the heartbeat failed to do its
job and the extension for that observation is not trustworthy. C4 asserts it is zero across the soak.

</clock_design>
</context>

<tasks>

<task type="auto" tdd="true">
  <name>Task 1: TickExtender — the 32-to-64-bit reconstruction, proven across a wrap</name>
  <files>
    /home/ido/mics_core/autopilot/autopilot/utils/tick_extender.py
    /home/ido/mics_core/tests/test_tick_extender.py
  </files>
  <behavior>
    Written against plan 01's `fake_pigpio` (see `31-01-SUMMARY.md` for the exact API).

    - **Identity before any wrap.** A rising sequence of ticks injected with `fire_edge` comes back
      out equal to the injected integer. `extend(0)` on a fresh extender returns `0`.
    - **One wrap.** `simulate_wrap(pre_us=1000)` then `advance_tick` past it: the extended output
      **increases by exactly the elapsed microseconds** across the wrap, `counters()['wraps'] == 1`,
      and the output series is strictly increasing. Assert the actual numbers, not "it went up".
    - **Three wraps** (the PLAT-29 acceptance shape, reproduced in microseconds): `wraps == 3`,
      the series is strictly increasing, and `out[-1] - out[0]` equals the true elapsed microseconds
      summed from the injections. **Zero backward jumps.**
    - **Out-of-order tolerance — the test that stops us reintroducing the defect we are deleting.**
      Inject `t`, then `t - 50`, then `t + 100`. The middle value must NOT be treated as a wrap:
      `wraps` stays 0, `out_of_order == 1`, the middle output is `t - 50` (not `t - 50 + 2**32`),
      the third output is `t + 100`, and `_last_tick` was not rewound.
    - **Out-of-order across a wrap boundary.** Immediately after a wrap, a late sample carrying a
      pre-wrap tick is mapped into the **previous** epoch, not the new one. Assert the exact value.
    - **Duplicate tick.** The same tick twice returns the same output twice, counts `duplicates`,
      and does not count a wrap.
    - **A forward gap larger than 2**31 µs is reported, not silently mis-extended.** Inject `t`, then
      `t + 2**31 + 1000` (mod 2**32). The extender still returns a value, and it flags the
      observation: the caller-visible signal is that `extend` returns `(value, ambiguous=True)` or
      sets a per-call flag the clock can read — choose one shape and document it, but the ambiguity
      must be **visible to the caller**, because `MicsClock` turns it into the `ambiguous_gap`
      counter C4 asserts is zero. A silently-plausible wrong number here is the whole failure mode.
    - **Range.** `extend(2**32)` and `extend(-1)` raise `ValueError` naming the 32-bit field. This is
      a loud failure, not a clamp.
    - **Thread safety.** Two threads driving `extend()` across a single simulated wrap, several
      thousand iterations, with a `threading.Barrier` to force overlap: `wraps == 1` exactly. A
      lock-free implementation double-counts here and the test is what catches it.
    - **`extend()` never raises for any in-range input**, including `0`, `2**32 - 1`, and a tick
      equal to `_last_tick`.
    - The extender performs **no clock reads and starts no threads**. A test asserts the module does
      not import `threading.Thread`-based timers and that `clock_gettime` appears zero times in the
      source — counted, printed.
  </behavior>
  <action>
    1. Write `tests/test_tick_extender.py` FIRST and watch every case fail against the absent module.
       Use the `fake_pigpio` fixture from plan 01's `conftest.py` for the injection cases, and direct
       `extend()` calls for the range and concurrency cases. Do NOT `pip install pigpio`.

    2. Write `autopilot/autopilot/utils/tick_extender.py`. Standard library only.
       - Module constants `TICK_WRAP = 2 ** 32` and `TICK_HALF = 2 ** 31`, with a comment giving
         `TICK_WRAP / 1e6 = 4294.967296 s = 71.582788 min` and naming the wire format
         (`struct.unpack('HHII', ...)`, the tick is the `I`) as the reason the field is 32 bits and a
         64-bit OS does not widen it.
       - `class TickExtender` with a `threading.Lock`, `extend(tick32)`, `counters()` and a
         `snapshot()` returning `(wraps, last_tick)` for tests and for the summary. No public setter
         for `wraps` — the counter is derived, never assigned from outside.
       - Implement the half-range rule from `<clock_design>` §1 **verbatim**. Put the rule's
         derivation in the docstring, including the 35.79-minute ambiguity limit and a pointer to
         PLAT-29's heartbeat clause as its mitigation. The next reader must be able to see why this
         is not `if tick < last`.
       - Keep the module under 150 lines. It is arithmetic; if it is longer, something belongs in
         `clock.py`.

    3. Do NOT import `pigpio` here, and do not read any clock. This module is pure so that the wrap
       logic can be tested exhaustively without a fake, a thread or a timer.
  </action>
  <verify>
    <automated>cd /home/ido/mics_core && /home/ido/.venvs/mics_core_dev/bin/python -m pytest -q tests/test_tick_extender.py --tb=short && /home/ido/.venvs/mics_core_dev/bin/python -c "
import pathlib, sys, threading
sys.path.insert(0, '.')
src = pathlib.Path('autopilot/autopilot/utils/tick_extender.py').read_text()
print('clock_gettime occurrences in tick_extender.py:', src.count('clock_gettime'))
print('pigpio occurrences in tick_extender.py:', src.count('pigpio'))
if src.count('clock_gettime') or src.count('pigpio'):
    sys.exit('tick_extender must be pure: no clock reads, no pigpio import')
from autopilot.autopilot.utils.tick_extender import TickExtender, TICK_WRAP, TICK_HALF
if TICK_WRAP != 2**32 or TICK_HALF != 2**31:
    sys.exit('TICK_WRAP/TICK_HALF wrong: %r %r' % (TICK_WRAP, TICK_HALF))
e = TickExtender()
seq = [10, 20, 30]
out = [e.extend(t) if not isinstance(e.extend, type(None)) else None for t in []]
e = TickExtender()
vals = []
for t in (10, 20, 30):
    r = e.extend(t)
    vals.append(r[0] if isinstance(r, tuple) else r)
if vals != [10, 20, 30]:
    sys.exit('identity before wrap broken: %r' % (vals,))
e = TickExtender()
pre = TICK_WRAP - 1000
r = e.extend(pre); a = r[0] if isinstance(r, tuple) else r
r = e.extend(500);  b = r[0] if isinstance(r, tuple) else r
if b - a != 1500:
    sys.exit('wrap extension wrong: expected +1500 us across the wrap, got %d (a=%d b=%d)' % (b - a, a, b))
if e.counters()['wraps'] != 1:
    sys.exit('wrap not counted exactly once: %r' % e.counters())
e = TickExtender()
base = 1_000_000
r = e.extend(base);      x0 = r[0] if isinstance(r, tuple) else r
r = e.extend(base - 50); x1 = r[0] if isinstance(r, tuple) else r
r = e.extend(base + 100);x2 = r[0] if isinstance(r, tuple) else r
if e.counters()['wraps'] != 0:
    sys.exit('a 50 us backward step was counted as a WRAP - this is the exact defect being deleted: %r' % e.counters())
if x1 != base - 50 or x2 != base + 100:
    sys.exit('out-of-order handling wrong: %r %r %r' % (x0, x1, x2))
if e.counters()['out_of_order'] != 1:
    sys.exit('out_of_order not counted: %r' % e.counters())
for bad in (TICK_WRAP, -1):
    try:
        e.extend(bad)
    except ValueError:
        pass
    else:
        raise AssertionError('extend(%r) was accepted; the tick is a 32-bit protocol field' % bad)
e = TickExtender()
bar = threading.Barrier(2)
def hammer(start):
    bar.wait()
    for i in range(3000):
        e.extend((start + i) % TICK_WRAP)
th = [threading.Thread(target=hammer, args=(TICK_WRAP - 1500,)), threading.Thread(target=hammer, args=(TICK_WRAP - 1500,))]
[t.start() for t in th]; [t.join() for t in th]
if e.counters()['wraps'] != 1:
    sys.exit('concurrent extend() double-counted the wrap: %r - the lock is missing or wrong' % e.counters())
print('tick_extender ok: identity, single wrap +1500us, out-of-order not a wrap, range rejected, concurrent wraps==1')
" && /home/ido/.venvs/mics_core_dev/bin/python tools/pytest_delta.py && python3 tools/check_tree_integrity.py --strict</automated>
  </verify>
  <done>`tests/test_tick_extender.py` passes every case in `<behavior>`, including three wraps with zero backward jumps, the out-of-order-is-not-a-wrap case both mid-epoch and across a wrap boundary, the visible ambiguity flag on a gap > 2**31 µs, the `ValueError` range guard, and the two-thread concurrency case landing on `wraps == 1`; the module contains zero `clock_gettime` and zero `pigpio` occurrences by counted assertion; delta gate reports `new failures: 0`; `--strict` exit 0.</done>
</task>

<task type="auto" tdd="true">
  <name>Task 2: MicsClock — heartbeat, one calibrated mapping, loud failures, counters</name>
  <files>
    /home/ido/mics_core/autopilot/autopilot/utils/clock.py
    /home/ido/mics_core/tests/test_mics_clock.py
  </files>
  <behavior>
    Written against `fake_pigpio`. **No test may sleep for a heartbeat**; `_heartbeat_once()` is a
    public-for-tests method the suite calls directly, and the background thread is only started by
    `attach()` and only exercised by the concurrency case.

    **Construction and attach.**
    - `MicsClock(heartbeat_s=3000)` raises `ValueError` whose message names PLAT-29 and quotes the
      2147.48 s bound. The bound is `TICK_HALF / 1e6`, derived, not typed as a literal.
    - `attach(fake_pigpio.pi())` succeeds and starts exactly one heartbeat thread; `stop()` is
      idempotent and joins it.
    - **The PLAT-28 runtime guard.** `attach()` on a stub carrying `synchronize` raises
      `PatchedClientError` naming the attribute; likewise for `ticks_to_timestamp`; likewise for a
      client class whose `__init__` accepts `sync_ticks`. Three separate cases, three separate
      stubs. These three names are where 100% of the deployed clock defects live
      (`31-REVISED-SCOPE.md` §2) and the clock must refuse to run on top of them.

    **Bootstrap and the no-raw-tick rule.**
    - Before any accepted sample, `observe(tick)` raises `ClockNotReady`. It does **not** return the
      raw tick, and it does not return `None`. A test asserts the exception type and that the raised
      message names the fallback policy.
    - After one `_heartbeat_once()`, `observe(tick)` returns an int. Two ticks 1_000_000 µs apart
      return values 1_000_000_000 ns apart to within 1 µs.

    **The wrap, end to end through the clock.**
    - `simulate_wrap()` + `advance_tick` + `fire_edge` on a registered callback that calls
      `observe()`: the returned `t_mono_ns` series is **strictly increasing across the wrap**, and
      `counters()['wraps'] == 1`.
    - **Quiet period longer than a wrap — the case PLAT-29's heartbeat exists for.** Positive
      control: `set_tick(2**32 - 1000)`, `_heartbeat_once()`, `advance_tick(2_100_000_000)` (past a
      wrap, comfortably beyond `2**31` µs) with **no edges at all**, then `_heartbeat_once()` twice
      more at intervals inside the bound, then `fire_edge`. The final `t_mono_ns` is greater than
      the pre-quiet one and `ambiguous_gap == 0`. Negative control: the identical sequence with the
      heartbeat **not** called during the quiet stretch yields `ambiguous_gap >= 1`. Without the
      negative control the heartbeat could be deleted and this test would still pass, which would
      make PLAT-29 decorative.

    **One mapping, read at call time — the machine form of "no scalar snapshot copies".**
    - Force a re-fit that changes the slope by +100 ppm. Assert:
      1. `mapping_generation` incremented;
      2. **continuity** — the mapped value at the anchor tick is **identical** before and after,
         to the nanosecond;
      3. two independent callers (simulating C2's two event paths — one calling `observe()` from a
         registered `fire_edge` callback, one calling it directly) both see the new
         `mapping_generation` on their next call. No caller holds a coefficient.
    - A test asserts `clock.py` exposes **no** function or attribute that returns a mapping
      coefficient or an offset for a caller to keep. Assert by name: there is no public
      `sync_offset`, no `get_offset`, no `synchronize`. The point is that the defect being replaced
      is exactly "a correct offset, copied once, never refreshed".
    - Re-fit rejection: a fitted slope 5000 ppm off is rejected, `fit_rejected` increments, the
      previous mapping is retained, and `mapping_generation` does **not** move.
    - Monotonicity across a re-fit: a series of observations spanning a forced re-fit is strictly
      non-decreasing. This is the property C4's `--check-wrap` asserts over 3.6 hours; assert it here
      in milliseconds.

    **Wall-clock step immunity.**
    - Patch `time.clock_gettime_ns` so `CLOCK_REALTIME` jumps +3600 s between two calls. Assert
      `observe()` of the same tick returns the **same** `t_mono_ns`, `to_utc_ns` of that value moves
      by **exactly** 3600e9, and the interval between two observed ticks is unchanged. Then repeat
      with a **backward** step of -3600 s and assert the same three things. Forwards only is half a
      test, and PLAT-25 requires both directions.
    - `to_utc_iso(t_mono_ns)` returns a tz-aware ISO string in the local zone; two `t_mono_ns` values
      1000 ns apart do not collapse to the same string.

    **Loud failures, never a raw tick.**
    - Monkeypatch the extender so it returns a decreasing value: `observe()` raises `ClockFault`,
      increments `monotonic_violation`, and the raised value is **not** the raw tick. A test asserts
      the exception carries neither the raw tick nor a plausible timestamp — the caller must be
      unable to mistake the failure for a result.
    - `counters()` returns every key listed in `<clock_design>` §7, all integers (except the two
      `last_*` diagnostics), and all zero on a clean run.
    - `TS_HARDWARE == "hardware"` and `TS_SOFTWARE == "software"` are importable from `clock`.

    **The single-offset invariant.**
    - A counted scan asserts `CLOCK_REALTIME` appears in **exactly one** file under
      `autopilot/autopilot/` and that file is `utils/clock.py`. `tools/pulse_timing/` is excluded —
      it is a standalone Python-3.7 instrument, not part of the pilot import path.

    **Concurrency.**
    - The real heartbeat thread running at `heartbeat_s=0.01` alongside a loop firing edges across a
      simulated wrap yields `wraps == 1` and a strictly non-decreasing `t_mono_ns` series. This is
      the only test that starts the thread; keep it short and deterministic in its assertions
      (monotonicity and `wraps`, not timing).
  </behavior>
  <action>
    1. Write `tests/test_mics_clock.py` FIRST. The three that must fail loudly before you implement
       anything are: `PatchedClientError` on a stub with `synchronize`, `ClockNotReady` before
       calibration, and the quiet-period **negative** control.

    2. Write `autopilot/autopilot/utils/clock.py` from `<clock_design>`. Standard library plus
       `pytz`/`tzlocal` (both already declared — `pytz` at `mics_task.py:1`, `tzlocal` at
       `utils/common.py:18`, and plan 03 pinned both). Do **not** import `pigpio`: the clock takes a
       client object and calls `get_current_tick()` on it, which is what makes it testable against
       the fake and library-independent for whatever backend follows pigpio.

       Public surface, and keep it this small:
       `TS_HARDWARE`, `TS_SOFTWARE`, `ClockNotReady`, `ClockFault`, `PatchedClientError`,
       `MicsClock` with `attach(pi)`, `stop()`, `observe(tick32) -> int`, `now_mono_ns() -> int`,
       `to_utc_ns(t_mono_ns) -> int`, `to_utc_iso(t_mono_ns) -> str`, `counters() -> dict`,
       `mapping_generation` (read-only property), `_heartbeat_once()` (documented as
       public-for-tests), plus module-level `get_clock()` and `reset_clock_for_tests()`.

       Write into the module docstring, because each of these is a thing someone will otherwise
       "fix": that this is the ONE clock for the whole tree; that the epoch offset is recomputed per
       call and must never be cached, with a one-line pointer to `31-REVISED-SCOPE.md` §2's snapshot
       defect; that `CLOCK_MONOTONIC` is slewed by NTP but never stepped, which is the property being
       relied on, and that `CLOCK_MONOTONIC_RAW` is deliberately NOT used; that bracket noise moves
       `b` only and is therefore common-mode and cancels in every interval; and that a re-fit changes
       the rate and never the value.

       Keep the file under 300 lines (project coding standard). If it will not fit, the heartbeat
       sampler is the natural third module — say so in the summary rather than shipping a 400-line
       file.

    3. `get_clock()` is a lazily-created module singleton. `reset_clock_for_tests()` stops and
       discards it. Do NOT construct a clock at import time — an import-time thread is how a test
       suite acquires a background thread it never asked for.

    4. Do **not** touch `utils/common.py`, `task.py`, `gpio.py`, `logging_utils.py` or
       `Event_Dispatcher.py`. C2 owns all five. This plan ships a module and its tests; nothing in
       the pilot imports it yet, and that is correct — `autopilot/` still runs exactly as it did.

    5. Record in the summary, verbatim, the public surface above and the chosen defaults
       (`heartbeat_s`, `window`, `min_span_s`, `max_bracket_ns`, `max_ppm`). C2 and C4 are written
       against them.
  </action>
  <verify>
    <automated>cd /home/ido/mics_core && /home/ido/.venvs/mics_core_dev/bin/python -m pytest -q tests/test_mics_clock.py tests/test_tick_extender.py --tb=short && /home/ido/.venvs/mics_core_dev/bin/python -c "
import pathlib, sys, time
sys.path.insert(0, '.'); sys.path.insert(0, 'tests')
root = pathlib.Path('autopilot/autopilot')
hits = sorted(str(p) for p in root.rglob('*.py') if 'CLOCK_REALTIME' in p.read_text(errors='ignore'))
print('CLOCK_REALTIME files under autopilot/:', hits)
if hits != ['autopilot/autopilot/utils/clock.py']:
    sys.exit('CLOCK_REALTIME must appear in exactly one module (utils/clock.py); found %r' % (hits,))
src = pathlib.Path('autopilot/autopilot/utils/clock.py').read_text()
for banned in ('import pigpio', 'sync_offset', 'def synchronize', 'CLOCK_MONOTONIC_RAW'):
    print('%r occurrences in clock.py: %d' % (banned, src.count(banned)))
    if src.count(banned):
        sys.exit('clock.py contains %r - see the design notes for why each of these is forbidden' % banned)
from autopilot.autopilot.utils.clock import (MicsClock, ClockNotReady, ClockFault,
                                             PatchedClientError, TS_HARDWARE, TS_SOFTWARE)
from autopilot.autopilot.utils.tick_extender import TICK_HALF, TICK_WRAP
if (TS_HARDWARE, TS_SOFTWARE) != ('hardware', 'software'):
    sys.exit('provenance constants wrong: %r %r' % (TS_HARDWARE, TS_SOFTWARE))
try:
    MicsClock(heartbeat_s=3000)
except ValueError as exc:
    if 'PLAT-29' not in str(exc):
        sys.exit('the heartbeat bound error must name PLAT-29; got %r' % str(exc))
else:
    raise AssertionError('a 3000 s heartbeat was accepted; the bound is TICK_HALF/1e6 = %.2f s' % (TICK_HALF / 1e6))
class Patched:
    def synchronize(self): pass
    def get_current_tick(self): return 0
try:
    MicsClock().attach(Patched())
except PatchedClientError as exc:
    print('patched-client guard fired:', str(exc)[:90])
else:
    raise AssertionError('attach() accepted a client carrying synchronize() - that is the Autopilot patch PLAT-28 deletes')
from fakes import fake_pigpio as f
c = MicsClock(heartbeat_s=600.0)
try:
    c.observe(1234)
except ClockNotReady:
    pass
else:
    raise AssertionError('observe() returned before calibration; it must raise ClockNotReady, never a raw tick')
c.attach(f.pi())
f.set_tick(1_000_000); c._heartbeat_once()
f.set_tick(61_000_000); c._heartbeat_once()
a = c.observe(61_000_000)
b = c.observe(62_000_000)
if abs((b - a) - 1_000_000_000) > 1000:
    sys.exit('interval wrong across the mapping: expected 1e9 ns, got %d' % (b - a))
real_utc = c.to_utc_ns(a)
gen0 = c.mapping_generation
ctr = c.counters()
for k in ('wraps', 'out_of_order', 'ambiguous_gap', 'heartbeat_missed', 'bracket_rejected',
          'fit_rejected', 'refits', 'convert_failed', 'monotonic_violation', 'mapping_generation'):
    if k not in ctr:
        sys.exit('counters() is missing %r - C4 reads this dict for PLAT-32' % k)
print('counters:', {k: ctr[k] for k in sorted(ctr)})
if ctr['ambiguous_gap'] or ctr['monotonic_violation'] or ctr['convert_failed']:
    sys.exit('a clean run produced failure counters: %r' % ctr)
c.stop(); c.stop()
print('mics_clock ok: single CLOCK_REALTIME site, PLAT-29 bound enforced, patched-client refused, ClockNotReady before calibration, 1e9 ns interval exact, counters complete')
" && /home/ido/.venvs/mics_core_dev/bin/python tools/pytest_delta.py && python3 tools/check_tree_integrity.py --strict</automated>
  </verify>
  <done>`tests/test_mics_clock.py` passes every case in `<behavior>`, including all three `PatchedClientError` stubs, both directions of the forced wall-clock step, the continuity-preserving re-fit asserted to the nanosecond, the two-caller `mapping_generation` proof, and BOTH the positive and negative quiet-period controls; `CLOCK_REALTIME` appears in exactly one file under `autopilot/` by counted scan; `clock.py` contains zero occurrences of `import pigpio`, `sync_offset`, `def synchronize` and `CLOCK_MONOTONIC_RAW`; `counters()` carries every key C4 reads; delta gate reports `new failures: 0`; `--strict` exit 0 with no manifest edit.</done>
</task>

</tasks>

<verification>
1. `cd /home/ido/mics_core && /home/ido/.venvs/mics_core_dev/bin/python -m pytest -q tests/test_tick_extender.py tests/test_mics_clock.py` -> pass
2. `/home/ido/.venvs/mics_core_dev/bin/python tools/pytest_delta.py` -> exit 0, `new failures: 0`
3. `python3 tools/check_tree_integrity.py --strict` -> exit 0, `30 protected files`, `0 violations`,
   **no manifest edit in this plan's diff**
4. `python3 -c "import pathlib,sys; root=pathlib.Path('/home/ido/mics_core/autopilot/autopilot'); hits=sorted(str(p) for p in root.rglob('*.py') if 'CLOCK_REALTIME' in p.read_text(errors='ignore')); print(hits); sys.exit(0 if len(hits)==1 and hits[0].endswith('utils/clock.py') else 'not exactly one CLOCK_REALTIME site')"`
   -> exit 0
5. `python3 -c "import pathlib,sys; p=pathlib.Path('/home/ido/mics_core'); n=sum(1 for f in (p/'autopilot').rglob('*.py') if 'from autopilot.utils.clock' in f.read_text(errors='ignore') or 'utils.clock' in f.read_text(errors='ignore')); print('pilot-path importers of utils.clock:', n); sys.exit(0 if n==0 else 'C1 wired the clock into the pilot; that is C2/C3 work')"`
   -> exit 0. **Nothing imports the clock yet, deliberately.**
6. `wc -l /home/ido/mics_core/autopilot/autopilot/utils/clock.py /home/ido/mics_core/autopilot/autopilot/utils/tick_extender.py`
   -> under 300 and under 150 respectively
</verification>

<success_criteria>
- A monotonic 64-bit microsecond counter is reconstructed from the 32-bit wire field, proven across
  three simulated wraps with zero backward jumps and proven not to mistake a 50 µs out-of-order
  sample for a 71.6-minute wrap.
- A quiet stretch longer than a wrap cannot lose a wrap, and the negative control proves the
  heartbeat is what buys that rather than an accident of the test.
- One calibrated mapping exists, is re-fit with continuity, and is read at call time by every caller.
  No API hands out a coefficient for a caller to cache, because a cached copy IS the defect.
- A wall-clock step in either direction moves the derived UTC by exactly the step and moves no
  interval.
- Every failure raises a named exception and increments a named counter. The clock never returns a
  raw tick presented as a timestamp.
- Zero production wiring. `autopilot/` behaves exactly as it did; C2 and C3 do the connecting.
</success_criteria>

<output>
After completion, create
`.planning/phases/31-mics-core-modern-pi-platform-bookworm-64-bit-python-3-11-lgpio-unattended-boot/31-C1-SUMMARY.md`.

Record verbatim, because C2 and C4 are written against them:
- the full public surface of `clock.py` and `tick_extender.py` (names, signatures, exception types);
- the chosen defaults for `heartbeat_s`, `window`, `min_span_s`, `max_bracket_ns`, `max_ppm`, and one
  sentence of justification each;
- the exact shape chosen for the ambiguity signal out of `extend()` (return tuple vs per-call flag);
- the complete key set returned by `counters()`, which is C4's PLAT-32 read-out;
- the measured slope and bracket width from the fake-driven calibration, so C4 has something to
  compare the real hardware fit against;
- an explicit statement that nothing in the pilot import path imports the clock yet.
</output>
