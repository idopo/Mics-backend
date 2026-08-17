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
    - "A forward gap larger than the half range is read FORWARD and flagged, never as a 2147-second backward step, and it does not latch"
    - "A plausible out-of-order sample and an implausible one are told apart by a stated distance bound, not by sharing one branch"
    - "A quiet stretch longer than a wrap cannot lose a wrap, because a heartbeat observes the tick at no more than half the wrap period"
    - "The wrap counter is correct when the heartbeat thread and the notify thread observe ticks concurrently"
    - "ONE calibrated tick to CLOCK_MONOTONIC relation exists, is re-fit periodically, and is read at call time by every caller — no scalar snapshot copies"
    - "A re-fit changes the RATE and never the VALUE, so the mapped timeline stays continuous and non-decreasing across a re-fit"
    - "A wall-clock step moves the derived UTC by exactly the step and moves no interval"
    - "Every failure is loud and counted; the clock never silently hands back a raw tick"
    - "All of the above is proven on a dev host with no Pi, no pigpiod and no pigpio installed"
  artifacts:
    - path: "/home/ido/mics_core/autopilot/autopilot/utils/tick_extender.py"
      provides: "Pure, thread-safe 32->64-bit tick extension: four-case half-range rule (duplicate / forward / out-of-order / ambiguous-forward) with a stated plausibility bound"
      min_lines: 60
      contains: "MAX_OUT_OF_ORDER_US"
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

<branch_guard>
**Assert the branch before committing anything.** All Phase 31 code lands on
`phase-31-modern-pi-platform` in `/home/ido/mics_core`, published to `origin` by plan 01. Before the
first commit of this plan, run `git branch --show-current` and confirm it is that branch — if it is
not, STOP and do not commit. Never `git checkout main`, never merge into `main`, never force-push,
and never push `main`. Integration to `main` is the user's decision after the C4 acceptance gate.
</branch_guard>

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

So use a half-range rule. But the half-range rule has a second branch, and **the obvious way to write
that branch is itself wrong in the same class as the defect being deleted.** *(Corrected 2026-08-17.
An earlier draft of this plan printed a 10-line rule and told you to implement it "verbatim". It was
run: fed `t` and then `t + 2**31 + 1000` — a case this plan's own `<behavior>` requires — it emitted
a **−2147.48 s step**, and because it never advanced `last_tick` it stayed in that branch for the
next ~35.79 minutes and then resumed one epoch out. Do not implement the old rule. What follows is
the corrected one, and it is a specification, not code to transcribe.)*

**The corrected rule, stated as four cases with an explicit discriminator between C and D:**

```
delta_forward = (tick32 - last_tick) & 0xFFFFFFFF        # 0 .. 2**32 - 1

# --- Case A: duplicate ------------------------------------------------------
if delta_forward == 0:
    duplicates += 1
    # same tick, same answer; do not advance, do not count a wrap
    return (wraps * TICK_WRAP + tick32, False)

# --- Case B: ordinary forward progress, wrap included -----------------------
if delta_forward <= TICK_HALF:
    if tick32 < last_tick:
        wraps += 1                                        # the modular counter rolled over
    last_tick = tick32
    return (wraps * TICK_WRAP + tick32, False)

# --- delta_forward > TICK_HALF: the sample is BEHIND last_tick, modulo 2**32.
#     Two physically different things look identical here, so DISCRIMINATE on distance.
delta_backward = TICK_WRAP - delta_forward                # 1 .. TICK_HALF - 1

# --- Case C: a plausible out-of-order sample --------------------------------
if delta_backward <= MAX_OUT_OF_ORDER_US:
    out_of_order += 1
    epoch = wraps - 1 if tick32 > last_tick else wraps
    return (epoch * TICK_WRAP + tick32, False)            # do NOT advance last_tick, do NOT count a wrap

# --- Case D: a backward step too large to be real ---------------------------
#     An ordered 1 MHz hardware counter does not go backwards by seconds. The only reading
#     consistent with the hardware is a genuine FORWARD gap larger than the half-range.
ambiguous_gap += 1
if tick32 < last_tick:
    wraps += 1
last_tick = tick32
return (wraps * TICK_WRAP + tick32, True)                 # ambiguous=True; advanced, so it does not latch
```

**Why Case D is the whole point.** Without the discriminator, a 50 µs out-of-order sample and a
>35.79-minute forward gap take the identical path — and the old rule took the *out-of-order* path for
both, so a real forward gap became a large backward step **that never healed**, because `last_tick`
was never advanced. Case D advances, so the very next sample is back in Case B: the error is bounded
to one observation instead of latching for 35.79 minutes. And it is **flagged**, which is what
`MicsClock` turns into the `ambiguous_gap` counter C4 asserts is zero.

**The plausibility bound.** `MAX_OUT_OF_ORDER_US = 2_000_000` (2 s), a module constant with this
derivation as its comment. The only two feeders are pigpio's notify thread and the heartbeat thread,
both inside one process reading one socket; real inter-thread skew is microseconds to low
milliseconds. 2 s is ~3 orders of magnitude of headroom over the worst plausible scheduler stall, and
~1000× below the **2147.48 s** backward step the alternative reading would imply. Anything past it is
not a backward step; it is a forward gap the field is too narrow to express. If you choose a
different number, justify it on **both** sides of that sandwich and record it in the summary.

**Monotonicity of the return value — state this precisely, because the two branches differ.**

- Cases A, B and D **never** return a value below the previous return. In D that is by construction:
  advancing `last_tick` and adding the modular delta moves the output strictly forward.
- Case C **may** return a value below the previous return, and that is **correct, not a violation**:
  the sample genuinely was taken earlier, and reporting its real time is the entire purpose of
  out-of-order handling. `extend()` reports when the sample happened; it does not manufacture a
  monotonic series. The caller that needs a non-decreasing series is `MicsClock.observe()` — see §4.

Put all of the above in the module docstring. The next reader must be able to see why this is not
`if tick < last`, and equally why Case D is not Case C.

**The residual ambiguity, and it is the reason PLAT-29 has a heartbeat clause.** With the
discriminator in place, the extender still cannot distinguish a genuine forward gap of nearly a full
wrap — `TICK_WRAP - 1_000_000` µs, one second short of 4294.97 s — from a 1 s backward out-of-order
sample. The first would be misread as the second. What it *can* now do is get every gap between `TICK_HALF` and `TICK_WRAP - MAX_OUT_OF_ORDER_US`
right, and flag it. The structural limit is the information content of a 32-bit field, not a defect
of the rule, and the heartbeat is what guarantees the gap is never large enough to reach it.

**The return shape is fixed: `extend(tick32) -> (value_us: int, ambiguous: bool)`.** Not a per-call
flag on the object, not an out-parameter. `ambiguous` is `True` only in Case D. A tuple is chosen
because the ambiguity belongs to the *observation*, and a flag read separately from the value can be
read for the wrong one under two threads.

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

**How `observe()` handles §1's Case C, so `ClockFault` does not fire on correct behaviour.**
`extend()` legitimately returns a value below its previous return for a plausible out-of-order
sample. `observe()` must therefore distinguish two things that look alike:

- **Out-of-order** — the extender's `out_of_order` counter moved on this call. `observe()` returns a
  value **clamped to its own previous return** (so the delivered series is non-decreasing, which is
  what C4's `--check-wrap` asserts over 3.6 hours) and does **not** raise. Nothing is wrong; a sample
  arrived late by microseconds.
- **A real monotonic violation** — the extended tick moved backwards **without** the extender
  flagging out-of-order. That is a broken extender or a corrupted state, so `observe()` increments
  `monotonic_violation` and raises `ClockFault`.

Both branches get a test. Without the distinction, every heartbeat that interleaves with an edge
would raise `ClockFault` and the clock would spend the soak in degraded mode while reporting nothing
wrong.

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
`mapping_generation`. **`ambiguous_gap` is the load-bearing one**: it counts §1's Case D — an
observation whose backward distance was too large to be a real backward step, so it was read as a
forward gap beyond the half-range. That means the heartbeat failed to do its job and **that
observation's extension is a best reading, not a fact**. C4 asserts it is zero across the soak.

**`duplicates` counts §1's Case A** and `out_of_order` counts **Case C**; every call lands in exactly
one of A/B/C/D, so the three counters plus `wraps` account for the whole input stream. If you
implement a case without its counter, the accounting stops adding up and C4's PLAT-32 table silently
loses a category.

**Which counters are zero on a clean run — be precise, because a blanket claim is wrong.**
`wraps`, `out_of_order`, `duplicates` and `refits` are *expected* to move; they are activity, not
faults. The **fault** counters — `ambiguous_gap`, `heartbeat_missed`, `convert_failed`,
`monotonic_violation` — must be zero on a clean run, and that is what tests and C4 assert.
`bracket_rejected` and `fit_rejected` sit in between: a single rejected sample on a loaded host is
normal and is **not** a failure, which is why they are reported with counts rather than asserted
zero. Say which class each counter is in, in the docstring and in the summary.

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
    - **Out-of-order tolerance (§1 Case C) — the test that stops us reintroducing the defect we are
      deleting.** Inject `t`, then `t - 50`, then `t + 100`. The middle value must NOT be treated as
      a wrap: `wraps` stays 0, `out_of_order == 1`, `ambiguous` is `False`, the middle output is
      `t - 50` (not `t - 50 + 2**32`), the third output is `t + 100`, and `_last_tick` was not
      rewound. **The middle output being below the previous one is correct here** — see
      `<clock_design>` §1's monotonicity note; the sample really was taken earlier, and it is
      `MicsClock.observe()` that clamps for the delivered series.
    - **Out-of-order across a wrap boundary.** Immediately after a wrap, a late sample carrying a
      pre-wrap tick is mapped into the **previous** epoch, not the new one. Assert the exact value.
    - **Duplicate tick (§1 Case A).** The same tick twice returns the same output twice, increments
      `duplicates` to exactly 1, does not count a wrap, does not touch `out_of_order` or
      `ambiguous_gap`, and returns `ambiguous is False`. **`duplicates` must actually increment** —
      a duplicate whose `delta_forward` is 0 falls through the forward branch and looks like normal
      progress, so a rule without Case A leaves this counter permanently zero and the counter set
      stops accounting for the whole input stream.
    - **A forward gap larger than `2**31` µs is read FORWARD, flagged, and does not latch (§1 Case
      D).** This is the case the old rule got wrong and it deserves four assertions, not one. Inject
      `t`, then `t + 2**31 + 1000` (mod `2**32`), then `t + 2**31 + 2000`:
      1. the second call returns `(value, True)` — `ambiguous` is `True` and `ambiguous_gap == 1`;
      2. the second output is **greater** than the first by **exactly** `2**31 + 1000`. Assert the
         number. A `-2147.48 s` step here is the defect this correction exists to prevent, and it is
         the same magnitude and the same shape as the production defect the phase is deleting;
      3. `_last_tick` **advanced**, so the third call is ordinary Case B: `ambiguous` is `False`,
         `ambiguous_gap` stays 1, and the output is the second plus exactly 1000. The old rule stayed
         wrong for ~35.79 minutes because it never advanced; this asserts the error is bounded to one
         observation;
      4. `out_of_order` did **not** move — Case D is not Case C, and a test that let them share a
         counter could not tell them apart.
    - **The discriminator, from the other side.** Inject `t`, then `t - MAX_OUT_OF_ORDER_US + 1000`
      (just inside the bound): Case C, `out_of_order == 1`, `ambiguous_gap == 0`. Then on a fresh
      extender inject `t`, then a tick whose backward distance is `MAX_OUT_OF_ORDER_US + 1000` (just
      outside): Case D, `ambiguous_gap == 1`, `out_of_order == 0`. Two injections either side of one
      constant is what proves the discriminator exists rather than being implied.
    - **Range.** `extend(2**32)` and `extend(-1)` raise `ValueError` naming the 32-bit field. This is
      a loud failure, not a clamp.
    - **Thread safety.** Two threads driving `extend()` across a single simulated wrap, several
      thousand iterations, with a `threading.Barrier` to force overlap: `wraps == 1` exactly. A
      lock-free implementation double-counts here and the test is what catches it.
    - **`extend()` never raises for any in-range input**, including `0`, `2**32 - 1`, and a tick
      equal to `_last_tick`.
    - **Every return is a 2-tuple `(int, bool)`.** Assert the shape on a call from each of the four
      cases, so no branch can quietly return a bare int.
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
       - Module constant `MAX_OUT_OF_ORDER_US = 2_000_000`, with `<clock_design>` §1's two-sided
         derivation as its comment.
       - Implement the four-case rule from `<clock_design>` §1. **It is a specification, not code to
         transcribe** — the pseudocode names the branches and the counters, and you own the actual
         Python. What is NOT negotiable: all four cases exist, each has its own counter, Case D
         advances `last_tick` and returns `ambiguous=True`, and Case C does not advance. Put the
         derivation in the docstring, including the 35.79-minute ambiguity limit, the plausibility
         bound, and a pointer to PLAT-29's heartbeat clause as the mitigation. The next reader must
         be able to see why this is not `if tick < last`, and why Case D is not Case C.
       - **Python 3.7 grammar, and this is not optional even though the dev host is 3.12.3.** Both of
         this plan's modules are pulled into plan 06's `py37_gate.py` closure the moment C2 adds
         `from autopilot.utils.clock import ...` to `gpio.py` — the gate walks `capture.py`'s
         transitive in-repo closure, which reaches `gpio.py`, and plan 08 takes the Buster baseline
         on Python **3.7.3**. So: no builtin generics in annotations (`list[str]`), no PEP-604 unions
         (`int | None`), no `dict` merge `|`, no `dataclass(slots=True)`, no walrus, no `match`, no
         positional-only `/`, no f-string `=` specifier. `time.clock_gettime_ns` is 3.7+ and is fine.
         Task 2's gate parses both modules with `ast.parse(..., feature_version=(3, 7))` **plus**
         explicit checks for the four constructs `feature_version` waves through — see
         `31-06-PLAN.md`'s objective for why the grammar check alone is insufficient. The gate is
         inline here rather than a call to `py37_gate.py` because plan 06 is in the **same wave** as
         this plan and its script may not exist yet, and because at this point nothing imports the
         clock, so `py37_gate.py`'s closure would not reach these two files anyway. C2 runs the real
         `py37_gate.py`, where the closure does reach them.
       - Keep the module under 180 lines. It is arithmetic — four branches, four counters and a
         docstring; if it is longer, something belongs in `clock.py`. *(Raised from 150 on
         2026-08-17: the corrected rule has two more branches and a derivation that has to be
         written down, and a cramped line budget is how the derivation gets dropped.)*

    3. Do NOT import `pigpio` here, and do not read any clock. This module is pure so that the wrap
       logic can be tested exhaustively without a fake, a thread or a timer.
  </action>
  <verify>
    <automated>cd /home/ido/mics_core && /home/ido/.venvs/mics_core_dev/bin/python -m pytest -q tests/test_tick_extender.py --tb=short && /home/ido/.venvs/mics_core_dev/bin/python -c "
import pathlib, sys, threading
# conftest.py:9 puts <repo>/autopilot on sys.path, so the package is autopilot.utils.*, NOT
# autopilot.autopilot.utils.* — there is no autopilot/__init__.py and no autopilot/utils/ at the repo
# root. Path STRINGS below still say autopilot/autopilot/..., which is correct: that is the filesystem.
sys.path.insert(0, 'autopilot')
src = pathlib.Path('autopilot/autopilot/utils/tick_extender.py').read_text()
print('clock_gettime occurrences in tick_extender.py:', src.count('clock_gettime'))
print('pigpio occurrences in tick_extender.py:', src.count('pigpio'))
if src.count('clock_gettime') or src.count('pigpio'):
    sys.exit('tick_extender must be pure: no clock reads, no pigpio import')
from autopilot.utils.tick_extender import TickExtender, TICK_WRAP, TICK_HALF, MAX_OUT_OF_ORDER_US
if TICK_WRAP != 2**32 or TICK_HALF != 2**31:
    sys.exit('TICK_WRAP/TICK_HALF wrong: %r %r' % (TICK_WRAP, TICK_HALF))
if not (0 < MAX_OUT_OF_ORDER_US < TICK_HALF):
    sys.exit('MAX_OUT_OF_ORDER_US must be a positive bound well inside the half range; got %r' % (MAX_OUT_OF_ORDER_US,))
def one(e, tick):
    r = e.extend(tick)
    if not (isinstance(r, tuple) and len(r) == 2 and isinstance(r[0], int) and isinstance(r[1], bool)):
        sys.exit('extend() must return (int, bool); got %r' % (r,))
    return r
e = TickExtender()
vals = [one(e, t)[0] for t in (10, 20, 30)]
if vals != [10, 20, 30]:
    sys.exit('identity before wrap broken: %r' % (vals,))
# --- Case B across a wrap -------------------------------------------------------------
e = TickExtender()
a, _ = one(e, TICK_WRAP - 1000)
b, _ = one(e, 500)
if b - a != 1500:
    sys.exit('wrap extension wrong: expected +1500 us across the wrap, got %d (a=%d b=%d)' % (b - a, a, b))
if e.counters()['wraps'] != 1:
    sys.exit('wrap not counted exactly once: %r' % e.counters())
# --- Case C: a 50 us backward step is NOT a wrap ---------------------------------------
e = TickExtender()
base = 1_000_000
x0, f0 = one(e, base)
x1, f1 = one(e, base - 50)
x2, f2 = one(e, base + 100)
if e.counters()['wraps'] != 0:
    sys.exit('a 50 us backward step was counted as a WRAP - this is the exact defect being deleted: %r' % e.counters())
if x1 != base - 50 or x2 != base + 100:
    sys.exit('out-of-order handling wrong: %r %r %r' % (x0, x1, x2))
if e.counters()['out_of_order'] != 1 or e.counters()['ambiguous_gap'] != 0 or f1:
    sys.exit('Case C must count out_of_order only, with ambiguous False: %r flags=%r' % (e.counters(), (f0, f1, f2)))
# --- Case D: a >2**31 us FORWARD gap is read forward, flagged, and does not latch -------
e = TickExtender()
t0 = 1_000_000
d0, g0 = one(e, t0)
d1, g1 = one(e, (t0 + TICK_HALF + 1000) % TICK_WRAP)
d2, g2 = one(e, (t0 + TICK_HALF + 2000) % TICK_WRAP)
if d1 - d0 != TICK_HALF + 1000:
    sys.exit('Case D emitted a %+.2f s step instead of +%d us - this is the -2147.48 s defect the corrected rule exists to prevent' % ((d1 - d0) / 1e6, TICK_HALF + 1000))
if not g1:
    sys.exit('Case D did not set ambiguous=True, so MicsClock can never raise ambiguous_gap and C4 asserts a counter that never moves')
if e.counters()['ambiguous_gap'] != 1 or e.counters()['out_of_order'] != 0:
    sys.exit('Case D must count ambiguous_gap and NOT out_of_order: %r' % e.counters())
if d2 - d1 != 1000 or g2:
    sys.exit('Case D latched: last_tick was not advanced, so the next ordinary sample is still wrong (%d, ambiguous=%r)' % (d2 - d1, g2))
# --- the discriminator, from both sides -------------------------------------------------
e = TickExtender()
one(e, t0); _, gin = one(e, (t0 - (MAX_OUT_OF_ORDER_US - 1000)) % TICK_WRAP)
if gin or e.counters()['out_of_order'] != 1 or e.counters()['ambiguous_gap'] != 0:
    sys.exit('a backward step just INSIDE MAX_OUT_OF_ORDER_US must be Case C: %r' % e.counters())
e = TickExtender()
one(e, t0); _, gout = one(e, (t0 - (MAX_OUT_OF_ORDER_US + 1000)) % TICK_WRAP)
if not gout or e.counters()['ambiguous_gap'] != 1 or e.counters()['out_of_order'] != 0:
    sys.exit('a backward step just OUTSIDE MAX_OUT_OF_ORDER_US must be Case D: %r' % e.counters())
# --- Case A: duplicate ------------------------------------------------------------------
e = TickExtender()
p0, _ = one(e, t0)
p1, ga = one(e, t0)
if p1 != p0 or ga or e.counters()['duplicates'] != 1 or e.counters()['wraps'] or e.counters()['out_of_order']:
    sys.exit('duplicate tick must return the same value and increment duplicates only: %r %r %r' % (p0, p1, e.counters()))
# --- range guard ------------------------------------------------------------------------
for bad in (TICK_WRAP, -1):
    try:
        e.extend(bad)
    except ValueError:
        pass
    else:
        raise AssertionError('extend(%r) was accepted; the tick is a 32-bit protocol field' % bad)
# --- concurrency ------------------------------------------------------------------------
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
print('tick_extender ok: identity, single wrap +1500us, Case C not a wrap, Case D forward+flagged+non-latching, discriminator both sides, duplicates counted, range rejected, concurrent wraps==1')
" && /home/ido/.venvs/mics_core_dev/bin/python tools/pytest_delta.py && python3 tools/check_tree_integrity.py --strict</automated>
  </verify>
  <done>`tests/test_tick_extender.py` passes every case in `<behavior>`, including three wraps with zero backward jumps; the Case C out-of-order-is-not-a-wrap case both mid-epoch and across a wrap boundary; **Case D asserted four ways** — `ambiguous=True`, a forward step of exactly `2**31 + 1000` µs (not a −2147.48 s step), `last_tick` advanced so it does not latch, and `out_of_order` untouched; the discriminator proven from both sides of `MAX_OUT_OF_ORDER_US`; `duplicates` proven to actually increment; every return a `(int, bool)` tuple; the `ValueError` range guard; and the two-thread concurrency case landing on `wraps == 1`; the module contains zero `clock_gettime` and zero `pigpio` occurrences by counted assertion; delta gate reports `new failures: 0`; `--strict` exit 0.</done>
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
    - Monkeypatch the extender so it returns a decreasing value **without** flagging out-of-order:
      `observe()` raises `ClockFault`, increments `monotonic_violation`, and the raised value is
      **not** the raw tick. A test asserts the exception carries neither the raw tick nor a plausible
      timestamp — the caller must be unable to mistake the failure for a result.
    - **The companion case, and it is what stops the fault firing on correct behaviour.** Feed a
      genuine `<clock_design>` §1 Case C sequence (`t`, `t - 50`, `t + 100`) through `observe()`:
      the delivered series is **non-decreasing** (the middle call is clamped to the previous return),
      `out_of_order` is 1, `monotonic_violation` stays **0**, and **nothing raises**. Without this
      test, every heartbeat that interleaves with an edge would raise `ClockFault` and the soak would
      run degraded while reporting nothing wrong.
    - **`ambiguous_gap` is plumbed from the extender, not recomputed.** Feed a §1 Case D sequence
      through `observe()` and assert `counters()['ambiguous_gap']` moved by exactly 1 and the
      delivered value went **forward**. C4 asserts this counter is zero over the soak; a counter the
      clock never increments would make that assertion vacuous.
    - `counters()` returns every key listed in `<clock_design>` §7, all integers (except the two
      `last_*` diagnostics). On a clean run the **fault** counters — `ambiguous_gap`,
      `heartbeat_missed`, `convert_failed`, `monotonic_violation` — are zero. `wraps`,
      `out_of_order`, `duplicates` and `refits` are activity counters and may be non-zero; asserting
      them zero would fail on a correct run. `bracket_rejected` and `fit_rejected` are **reported,
      not asserted**: the re-fit scenario below deliberately drives `fit_rejected` to 1, so a blanket
      "all zero" claim contradicts this plan's own test. See `<clock_design>` §7 for the three
      classes.
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
import ast, pathlib, re, sys, time
# conftest.py:9 puts <repo>/autopilot on sys.path -> the package is autopilot.utils.*, never
# autopilot.autopilot.utils.*. Path STRINGS keep the autopilot/autopilot/... filesystem form.
sys.path.insert(0, 'autopilot'); sys.path.insert(0, 'tests')
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
# --- PLAT/py37: both modules enter plan 06's py37_gate closure at C2, and plan 08's baseline runs
# --- on Buster's Python 3.7.3. Grammar AND the four constructs feature_version waves through.
for rel in ('autopilot/autopilot/utils/clock.py', 'autopilot/autopilot/utils/tick_extender.py'):
    txt = pathlib.Path(rel).read_text()
    try:
        tree = ast.parse(txt, filename=rel, feature_version=(3, 7))
    except SyntaxError as exc:
        sys.exit('%s does not parse under Python 3.7 grammar: %s' % (rel, exc))
    bad = []
    for n in ast.walk(tree):
        if isinstance(n, ast.Subscript) and isinstance(n.value, ast.Name) and n.value.id in (
                'list', 'dict', 'set', 'tuple', 'frozenset', 'type'):
            bad.append('PEP 585 builtin generic %s[...] at line %d' % (n.value.id, n.lineno))
        if isinstance(n, ast.BinOp) and isinstance(n.op, ast.BitOr):
            bad.append('PEP 604 union / dict-merge | at line %d' % n.lineno)
        for kw in getattr(n, 'keywords', []) or []:
            if kw.arg == 'slots':
                bad.append('dataclass(slots=) at line %d' % n.lineno)
    for m in re.finditer(r'''f["'][^"']*\{[^{}]+=\}''', txt):
        bad.append('f-string = specifier (3.8+) at offset %d' % m.start())
    if bad:
        sys.exit('%s uses constructs that raise TypeError on Buster Python 3.7.3: %r' % (rel, bad))
    print('%s parses under feature_version=(3,7) with no 3.9/3.10 constructs' % rel)
from autopilot.utils.clock import (MicsClock, ClockNotReady, ClockFault,
                                   PatchedClientError, TS_HARDWARE, TS_SOFTWARE)
from autopilot.utils.tick_extender import TICK_HALF, TICK_WRAP
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
fault = ('ambiguous_gap', 'heartbeat_missed', 'convert_failed', 'monotonic_violation')
hot = {k: ctr[k] for k in fault if ctr[k]}
if hot:
    sys.exit('a clean run produced FAULT counters: %r (activity counters wraps/out_of_order/duplicates/refits and the reported-not-asserted bracket_rejected/fit_rejected are exempt)' % hot)
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
5. `python3 -c "import pathlib,sys; p=pathlib.Path('/home/ido/mics_core'); skip={'clock.py','tick_extender.py'}; hits=[str(f) for f in (p/'autopilot').rglob('*.py') if f.name not in skip and 'utils.clock' in f.read_text(errors='ignore')]; print('pilot-path importers of utils.clock:', hits); sys.exit(0 if not hits else 'C1 wired the clock into the pilot; that is C2/C3 work')"`
   -> exit 0. **Nothing imports the clock yet, deliberately.** The two modules this plan writes are
   **excluded by name**: `clock.py` is asked to name itself in its own docstring, and
   `tick_extender.py` is asked to point at it, so including them would make this scan fail on a
   correct implementation.
6. `wc -l /home/ido/mics_core/autopilot/autopilot/utils/clock.py /home/ido/mics_core/autopilot/autopilot/utils/tick_extender.py`
   -> under 300 and under 180 respectively
</verification>

<success_criteria>
- A monotonic 64-bit microsecond counter is reconstructed from the 32-bit wire field, proven across
  three simulated wraps with zero backward jumps and proven not to mistake a 50 µs out-of-order
  sample for a 71.6-minute wrap.
- The other half of that, which the first version of this plan got wrong: a forward gap larger than
  the half range is read **forward** and flagged, not as a −2147.48 s step, and it does **not**
  latch — asserted on the step size, the flag, the counter and the following sample.
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
- confirmation that `extend()` returns `(value_us: int, ambiguous: bool)` — the shape is fixed by
  `<clock_design>` §1, not chosen at execution time — and the value of `MAX_OUT_OF_ORDER_US` with
  its two-sided justification;
- which of `<clock_design>` §7's three counter classes each key belongs to (fault / activity /
  reported-not-asserted), because C4 asserts only the fault class;
- the complete key set returned by `counters()`, which is C4's PLAT-32 read-out;
- the measured slope and bracket width from the fake-driven calibration, so C4 has something to
  compare the real hardware fit against;
- an explicit statement that nothing in the pilot import path imports the clock yet.
</output>
