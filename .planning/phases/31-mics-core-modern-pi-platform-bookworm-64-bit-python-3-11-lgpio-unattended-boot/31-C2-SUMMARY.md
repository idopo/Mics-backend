---
phase: 31-mics-core-modern-pi-platform-bookworm-64-bit-python-3-11-lgpio-unattended-boot
plan: C2
subsystem: platform
tags: [clock, timestamps, provenance, gpio, event-dispatch, concurrency, tdd, plat-18, plat-19, plat-27, plat-31]

# Dependency graph
requires:
  - phase: 31-01
    provides: "fake_pigpio + the conftest fixture; tools/pytest_delta.py; the frozen baseline"
  - phase: 31-03
    provides: "stock upstream pigpio pinned; the patched client's sync_ticks/synchronize/ticks_to_timestamp are gone"
  - phase: 31-06
    provides: "tools/pulse_timing/py37_gate.py -- the transitive Python-3.7 grammar gate this plan grew and re-ran"
  - phase: 31-C1
    provides: "autopilot/utils/clock.py (get_clock/observe/now_mono_ns/to_utc_ns/to_utc_iso/TS_HARDWARE/TS_SOFTWARE/ClockNotReady/ClockFault)"
provides:
  - "assign_cb's tick->t_mono_ns adapter on BOTH Digital_Out and Digital_In, signature unchanged, idempotent per edge"
  - "Hardware's per-edge timestamp slot: one atomic EdgeSlot under one per-object lock, generation-keyed, never consumed by a reader"
  - "Hardware._edge_source_for() -- a NON-claiming provenance lookup over the last 16 edges"
  - "Event_Dispatcher.dispatch_event(event, key, ts_mono_ns=, ts_source=) -- dual-timebase payload with explicit provenance, no pigpio"
  - "localize_tz(ts_mono_ns) delegating to the one clock, refusing the old ISO form loudly"
  - "tests/test_edge_timestamp_end_to_end.py -- the PLAT-27 two-route regression test (14 tests)"
  - "tests/test_single_clock_invariant.py (33) and tests/test_event_dispatcher_clock.py (21)"
affects: [31-C3, 31-C4, 31-08]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Per-EDGE idempotence keyed on (gpio, level, tick): one edge reaches N registrations separately, so conversion and slot publication are deduped by edge identity rather than counted per registration"
    - "The staleness bound travels INSIDE the published slot, so a reader can never apply a bound that belonged to a different publication"
    - "Provenance READ vs provenance CLAIM: execute_trigger reads (never claims) so it cannot take the @log_action bridge's turn"
    - "Structural lock proofs alongside the outcome proof, because CPython 3.12 makes the outcome proof vacuous (C1's finding, reproduced here)"
    - "Mutation testing every load-bearing invariant before claiming the suite proves it"

key-files:
  created:
    - /home/ido/mics_core/tests/test_single_clock_invariant.py
    - /home/ido/mics_core/tests/test_event_dispatcher_clock.py
    - /home/ido/mics_core/tests/test_edge_timestamp_end_to_end.py
  modified:
    - /home/ido/mics_core/autopilot/autopilot/hardware/gpio.py
    - /home/ido/mics_core/autopilot/autopilot/hardware/__init__.py
    - /home/ido/mics_core/autopilot/autopilot/utils/common.py
    - /home/ido/mics_core/autopilot/autopilot/utils/logging_utils.py
    - /home/ido/mics_core/autopilot/autopilot/tasks/task.py
    - /home/ido/mics_core/autopilot/autopilot/networking/Event_Dispatcher.py
    - /home/ido/mics_core/tools/tree_protect_list.json
    - /home/ido/mics_core/conftest.py
    - /home/ido/mics_core/tests/fakes/fake_pigpio.py
    - /home/ido/mics_core/tests/test_shed_absences.py

key-decisions:
  - "`timestamp` stays a float of POSIX epoch SECONDS. The orchestrator does datetime.fromtimestamp(data['timestamp'], tz=pytz.utc) at ElasticSearchDateHandler.py:48, so it is a number, not a datetime and not a string. The plan's contract table did not state the type; the consumer does."
  - "The payload is built at DISPATCH time, not in the sender thread. Deriving t_utc_ns behind a queue would let a backlog smear the timestamps, which is the class of defect this phase exists to remove."
  - "EdgeSlot is a 6-field namedtuple (value_ns, written_ns, generation, max_age_ns, key, source), not the plan's literal 3-tuple. The edge identity and the bound must travel atomically WITH the value, or the idempotence and staleness rules get applied with mismatched data."
  - "The slot lives on Hardware (hardware/__init__.py), not in gpio.py: logging_utils imports autopilot.hardware already, and importing gpio there would be a gpio<->logging_utils import cycle."
  - "Concurrency discipline: BOTH sides take the same per-object lock AND the slot is one atomic namedtuple rebind. The lock is not optional -- _last_attached_generation is a read-modify-write and two unguarded readers can both conclude they are first."
  - "Added Hardware._edge_source_for() + EDGE_SOURCE_MEMO=16. execute_trigger runs on a worker thread draining event_queue, so the slot may already describe a newer edge by the time it asks for provenance. It must not claim (the bridge's turn) and must not guess."
  - "Did NOT decorate Digital_In with @auto_log, and did not 'fix' @auto_log's partial coverage. Every IR beam-break, lick and touch line is a Digital_In; wrapping the class adds a Hardware_Event per METHOD CALL across the whole rig. Product decision, out of scope."
  - "The adapter's totality is scoped to the conversion and publication it adds. Exceptions raised by the registered callbacks keep today's propagation semantics -- a blanket catch there would silently swallow real bugs in record_event/handle_trigger and is outside this plan's fence."
  - "Did NOT edit tests/test_log_action_values.py or log_value.py to resolve the contradiction unblocking them exposed. Both are protected; it is a Rule 4 decision for the user. Accepted into the baseline with a typed reason and logged in deferred-items.md."

patterns-established:
  - "Route identification by payload CONTENT, never by arrival order, when two asynchronous dispatch routes must be compared"
  - "A 'the case actually happened' companion test beside every invariant-style concurrency assertion, so the invariant cannot pass vacuously"

requirements-completed: [PLAT-18, PLAT-19, PLAT-27, PLAT-31]

# Metrics
duration: ~35min
completed: 2026-08-19
---

# Phase 31 Plan C2: One Clock, Both Event Paths Summary

**Wired plan C1's clock into both of the rig's event paths and proved it with one edge: a single
injected transition on a `record=True` `Digital_Out` now fires both dispatch routes — the
`@log_action` bridge and `Task.execute_trigger` — and both payloads carry the *same* converted
integer as `t_mono_ns`, both marked hardware-stamped, with `assign_cb`'s signature and `task.py`'s
registration line untouched. `Event_Dispatcher` no longer imports pigpio at all, which as a side
effect un-blocked 36 tests that had been dark since Phase 25.**

## Performance

- **Duration:** ~35 min (08:47–09:20 UTC)
- **Tasks:** 3 completed (all TDD)
- **Commits:** 5 in `~/mics_core` + 1 in the planning repo
- **Tests added:** 68 (33 + 21 + 14), all green
- **Files:** 3 created, 10 modified

## Task Commits

1. **Task 1: the `assign_cb` adapter, the edge slot, `localize_tz`, `pi_timestamp`** — TDD:
   `199c595` (test, RED — 21 of 33 failing) → `09d32e1` (feat, GREEN)
2. **Task 2: dual-timebase dispatch, the `@log_action` bridge, the one manifest entry** — TDD:
   `97cca37` (test, RED — 17 of 21 failing/erroring) → `b4c7f45` (feat, GREEN)
3. **Task 3: the mandatory PLAT-27 assertion** — `79bd267` (test; the two-route case failed first,
   which is the bug this plan exists to fix)

Planning repo: `a354322` (re-baseline + `deferred-items.md`).
All on `phase-31-modern-pi-platform` in `/home/ido/mics_core`. `main` untouched, nothing pushed,
tag `phase-31-buster-before-arm` untouched.

## `assign_cb` — before and after

```
BEFORE (both classes):  (self, callback_fn, add=True, evented=False, manual_trigger=None)
AFTER  (both classes):  (self, callback_fn, add=True, evented=False, manual_trigger=None)
```

Rendered-string identical, asserted as a rendered string so a "harmless" reorder fails. The
registration seam is provably untouched: `task.py`'s
`hw.assign_cb(partial(self.handle_trigger, hardware=hw))` still appears **exactly once**, byte for
byte, and `git diff` shows no change to that line. **There is no arity change in this port** —
stock pigpio's callback is already `(gpio, level, tick)`; what changed is the *meaning* of the
third argument, from a string the patched fork manufactured to `CLOCK_MONOTONIC` nanoseconds.

**The adapter's shape** (`gpio.py`, `_edge_timestamp_adapter(hardware, callback_fn)`), registered
by both classes' `assign_cb` in place of the bare `callback_fn`:

1. build the edge key `(gpio, level, tick)`;
2. `hardware._edge_timestamp_for(key)` — if this edge was already converted by another
   registration, reuse that integer and do nothing else;
3. otherwise `get_clock().observe(tick)`; on `ClockNotReady` / `ClockFault` (or anything else) fall
   back to `get_clock().now_mono_ns()`, mark the edge `TS_SOFTWARE`, bump the named counter
   `gpio.edge_clock_fallbacks()` and log at the 1/10/100/every-500 cadence. **A raw tick is never
   passed on as a timestamp, and nothing raises into pigpio's notify thread** — an exception there
   kills every subsequent event for every GPIO;
4. `hardware._stamp_edge(key, t_mono_ns, source, EDGE_SLOT_MAX_AGE_NS)` — publishes once per edge;
5. `callback_fn(gpio, level, t_mono_ns)` — **3 positional arguments, no kwargs**, asserted.

`self.callbacks` still holds the returned pigpio callback object, so `clear_cb()`'s `.cancel()`
works unchanged, and `add=True` still appends.

## The edge slot as implemented

```python
EdgeSlot = namedtuple("EdgeSlot", "value_ns written_ns generation max_age_ns key source")
```

- **Generation-keyed, not consumed.** `_claim_edge_timestamp()` hands the value over iff the slot
  is non-empty, its generation is not one this reader already attached, and its age is within the
  bound published with it. It records the generation and **never clears the slot**. Invalidation is
  by generation and by age, never by consumption.
- **Written once per EDGE, not once per registration.** One edge reaches every registration on the
  pin separately, so idempotence is keyed on `(gpio, level, tick)` at two levels: the adapter's
  pre-check and `_stamp_edge`'s re-check under the lock. After one edge on a two-registration
  object, `generation` is **1**, not 2 (asserted; and the mutation that removes *both* guards makes
  it 2 and fails the test).
- **`Task.execute_trigger` does not claim the slot.** It already holds the value as its third
  positional argument and passes it explicitly.

**Deviation from the plan's literal 3-tuple, and why.** The plan specifies
`(t_mono_ns, mono_at_write_ns, generation)`. The implemented tuple adds `max_age_ns`, `key` and
`source`. All three have to arrive *atomically with the value they describe*: a bound read
separately could belong to a different publication, an edge identity read separately could dedupe
the wrong edge, and provenance read separately could label the wrong instant. It is still ONE
immutable object published by ONE name rebind, which is the property the plan actually requires.

### Staleness bound — `EDGE_SLOT_MAX_AGE_NS = 2_000_000` (2 ms), sandwiched on both sides

- **Lower side:** the reader runs inside the same callback invocation chain as the write — the
  adapter publishes, then calls `record_event`, which *is* the wrapped method — so real latency is
  microseconds. 2 ms is ~3 orders of magnitude of headroom for a loaded `SCHED_OTHER` scheduler.
- **Upper side:** ~3 orders of magnitude *below* the shortest inter-trial interval on this rig, so
  a stale slot can never bridge two trials.

The plan's number was kept unchanged; both halves of its derivation are in a comment beside the
constant, because the failure mode a reader must understand is that reusing an old edge timestamp
is **worse** than a software stamp — a wrong hardware-stamped value is indistinguishable from a
correct one once it is in Elasticsearch.

### Concurrency discipline actually chosen: BOTH

The slot is written from pigpio's notify thread and read from the task thread on every
`set()`/`toggle()`. The plan offers "atomic tuple publication" or "one lock around both sides" and
sanctions doing both. **Both are in force:**

1. one atomic rebind of an immutable `EdgeSlot` — there is no field to write separately; and
2. one per-object `threading.Lock` around the write **and** the read, because
   `_last_attached_generation` is a read-modify-write and two unguarded readers can both conclude
   they are first.

The choice is stated in the module comment next to the constant and next to the methods, so the
next reader does not have to infer it. The lock is created in `Hardware.__init__` with a
double-checked lazy fallback for any object that skipped it.

**This is where the outcome proof has no teeth, and it was caught by mutation.** Removing the slot
lock entirely left all 66 tests in this plan's three modules **green** — CPython 3.12.3's
specializing interpreter makes these read-modify-writes incidentally atomic, exactly as C1 measured
for the `TickExtender`. On Buster's Python 3.7.3 (plan 08's baseline) it would not be, which is
precisely why the lock stays. Two **structural** proofs were added and both fail deterministically
with the lock removed: each slot method enters the lock exactly once per call (instrumented
`__enter__`), and a second thread blocks while it is held.

## The corrected `isoformat` inventory

The plan corrected an earlier draft's two-site inventory to three. **The three-site count is right;
two of the three attributions are not.** Measured on the live tree (`gpio.py`, 1651 lines before
this plan — not the 1692 the plan states, because plans 02/03 edited it first):

| Site | Plan says | Actually | Disposition |
|---|---|---|---|
| `gpio.py:7` | module docstring pointing at the patched pigpio fork installed by `setup_pilot.sh` | **confirmed** — the load-bearing one, a standing written instruction to reinstall the fork PLAT-28 deletes | **rewritten**, replaced by a `Warning::` block naming the by-value-offset defect and the runtime guard |
| `gpio.py:892` | `Digital_Out.assign_cb` | **`Digital_In.assign_cb`** | rewritten |
| `gpio.py:946` | `Digital_In.record_event` | **confirmed** | rewritten |
| `Digital_Out.assign_cb` | "rewrite" | documented **no** timestamp at all (a 3-line docstring) | contract **added**, along with the full `Args:` block |
| `Digital_In.assign_cb` | "add" | it was the `:892` site — a contract to **correct**, not add | rewritten |
| `Hardware.assign_cb` (`hardware/__init__.py`) | zero `isoformat`/`timestamp` occurrences | **confirmed** | contract **added** |

`gpio.py` now contains **zero** `isoformat` occurrences and **5** `CLOCK_MONOTONIC` occurrences;
`hardware/__init__.py` names `CLOCK_MONOTONIC` 5 times. The bare names `ticks_to_timestamp` and
`synchronize` survive **once each**, in the module docstring's warning against reinstalling the
fork; the tests assert the absence of *calls* (`.ticks_to_timestamp(`, `.synchronize(`,
`sync_ticks=`), which is the property that matters.

## Python 3.7 closure: it grew, and the gate was actually run

| | closure members |
|---|---|
| before this plan | **30** |
| after `gpio.py` imports `autopilot.utils.clock` | **34** |

The four new members are `utils/clock.py`, `utils/clock_calibration.py`, `utils/clock_guard.py` and
`utils/tick_extender.py` — C1 wrote them to 3.7 grammar and gated them inline because at that point
nothing imported them. `python3 tools/pulse_timing/py37_gate.py` exits **0** on all 34, so the 3.7
constraint on the clock modules is now enforced by the real gate rather than by an inline promise.

## `@auto_log` coverage, enumerated from `Digital_Out.__dict__` at run time

**12 methods** (not trusted from any plan; a test enumerates and asserts them):

```
assign_cb  clear_cb  delete_all_scripts  delete_script  pulse  record_event
release    series    set                 store_series   toggle turn
```

`Digital_In.__dict__` has **zero** wrapped methods, and this plan deliberately left it that way.
Every IR beam-break, lick and touch line on the rig is a `Digital_In`; decorating the class would
add a `Hardware_Event` per *method call* across the whole rig. That is a product decision, not a
port detail. The input path still reaches Elasticsearch through `record_event` and through
`execute_trigger`. Subclass overrides (`Solenoid.open`, `TTL.set`, `Pulse20Hz.start`, `PWM.set`,
`LED_RGB.set`) remain unwrapped, unchanged.

One consequence worth knowing: `assign_cb` is itself in that wrapped set, so **registering a
trigger dispatches an event**. The end-to-end harness has to let both asynchronous stages go idle
before taking its baseline, or every payload count is off by one.

## The dual-timebase contract

| Field | Clock | Use for | Never use for |
|---|---|---|---|
| `t_mono_ns` (int) | the one MICS clock, derived from the DMA-sampled tick at the edge | **all** interval / latency / rate analysis within a session | joining across machines |
| `t_utc_ns` (int) / `timestamp` (float s) | derived per event through `utils.clock`'s per-call epoch offset | display, joining to backend/session records | interval analysis across a clock step |
| `ts_source` (`"hardware"`/`"software"`) | — | telling a DMA-sampled edge from a scheduler read | assuming uniform precision |

Proven, both directions: dispatch A, step `CLOCK_REALTIME` by **±3600 s**, dispatch B —
`B.t_mono_ns - A.t_mono_ns` is *exactly* the real elapsed monotonic interval, while
`B.t_utc_ns - A.t_utc_ns` differs by exactly `elapsed + step`. The UTC movement is asserted as
**correct behaviour**, which is what keeps the claim honest.

**Honest boundary**, written into the `Event_Dispatcher` module docstring so the claim cannot
inflate: this makes each rig's *own* timing robust and puts both of its event paths on one
timeline. It does **not** synchronise a rig's clock to the backend's or to an ephys system — that
needs chrony slewing (plan 05) plus the TTL hardware pulse as cross-device ground truth, which is
Phase 28's territory. And software-originated events do not acquire hardware precision by being on
the same timeline; they become *comparable*.

### The `timestamp` key: kept, and its TYPE is now pinned by a checked consumer

**Kept**, per the plan — but the plan's table describes it only as "the derived UTC" and does not
say what type that is. It is a **float of POSIX epoch seconds**, and that is not a free choice:

| Consumer checked | What it does with `timestamp` |
|---|---|
| `orchestrator/orchestrator/data_handlers/ElasticSearchDateHandler.py:48` | `datetime.fromtimestamp(data["timestamp"], tz=pytz.utc)` — **requires a number**; a string or a `datetime` raises |
| `ElasticSearchDateHandler.py:51` | replaces it with the Asia/Jerusalem `datetime` actually indexed into ES |
| `ElasticSearchDateHandler.py:113` (`_summarize_data`) | prints it only |
| `orchestrator/RouterGateway.py:123` | `msg.get_timestamp()` — the ZMQ envelope's own timestamp, unrelated |

So `timestamp = t_utc_ns / 1e9`. Float64 at 1.7e9 s resolves to ~238 ns, which is *exactly* the
precision the field had before and is why `t_utc_ns` (int) is added beside it rather than replacing
it. Renaming or retyping it would break every live Elasticsearch query and the orchestrator, for no
gain. A test pins both the type and the `t_utc_ns/1e9` relationship.

The payload keeps **every** key it had (`pilot`, `subject`, `session`, `run_id`, `task_type`,
`timestamp`, `continuous`, `session_progress_index`, `subjects`, `event`) and adds **exactly**
three; a test asserts the key set is that union and nothing else.

## `localize_tz` and the one epoch offset

```python
localize_tz(ts_mono_ns: int) -> str      # tz-aware ISO 8601, local zone
localize_tz("2026-08-17T10:00:00.000000") -> TypeError naming the change and Phase 31
```

Two lines of delegation to `autopilot.utils.clock.to_utc_iso` plus the guard. The return **type is
unchanged**, so no Elasticsearch field changes type. Sub-microsecond precision survives the trip in
(two values 1000 ns apart do not collapse). `CLOCK_REALTIME` still appears in **exactly one** file
under `autopilot/autopilot/` — `utils/clock.py` — asserted by a counted scan in the test suite *and*
in the plan's verify.

`pytz`, `tzlocal.get_localzone` and `datetime` were removed from `common.py` after a repo-wide
counted scan proved each had exactly one occurrence there (its own import) and no other user
anywhere in the tree. `TIMEZONE = "Asia/Jerusalem"` was **kept**: it is a declarative constant, not
a second clock.

## `Event_Dispatcher` — what changed

- `import pigpio`, `get_current_tick`, `ticks_to_timestamp`: **0 / 0 / 0** occurrences (counted,
  printed by the verify).
- `dispatch_event(event, key='CONTINUOUS', ts_mono_ns=None, ts_source=None)`. With `ts_mono_ns`
  given the payload's `t_mono_ns` is **exactly** that integer (identity, tested). Without it the
  dispatcher reads `get_clock().now_mono_ns()` and marks the event `"software"`.
- **The payload is now built at dispatch time**, not in the sender thread. Deriving `t_utc_ns`
  behind a queue would let a backlog silently smear the timestamps — the same class of defect this
  phase exists to remove. `_sender_loop` is now only `node.send(...)`, plus `task_done()` so the
  queue is deterministically drainable.
- **Never raises** on any runtime path: a clock that raises, a queue that refuses, `None` fields —
  each asserted by running a statement after the call. The one deliberate exception is the
  pre-existing `isinstance(event, Event)` `TypeError`, which is a caller *contract* violation, not
  a runtime condition; it predates the phase and `test_execute_trigger_guard.py` depends on callers
  tolerating it. Everything after that guard is total.

### The commented-out payload duplicate at `:89-94`

**Deleted.** It was a verbatim copy of the old payload, including
`self.pi.ticks_to_timestamp(tick, isoformat=False)` — a stale duplicate of a method that no longer
exists, sitting beside a changed implementation. Leaving it would have been a trap for the next
reader.

### `_dropped_no_clock`'s narrowed meaning

Both counters survive **by name** and still increment (`tools/tree_integrity/manifest.py
check_event_dispatcher()` asserts both independently, and so do two tests here). `_dropped_no_clock`
used to count a failed pigpiod IPC round trip — a socket call to read the daemon's tick, which
could genuinely fail. A `CLOCK_MONOTONIC` read cannot realistically fail, so it now counts the
"**the clock refused to convert this event**" path. The name is kept because what it answers — *how
many events were dropped rather than stamped from another clock?* — is unchanged. This is written
in a comment beside the counter, because a counter whose meaning silently changed is worse than a
renamed one.

`_dropped_on_send` additionally now counts a queue that refuses the `put`, which the unbounded
`queue.Queue` never does in production but which makes the containment testable.

## The manifest: exactly one entry, by hand

```
autopilot/autopilot/networking/Event_Dispatcher.py
  baseline_sha256  1bfadc3313f3...  ->  d0ef29ec5334...
  reason: Phase 31 plan C2 — dual-timebase dispatch with provenance, PLAT-18/19/27/31
```

`--strict` flagged **exactly one** file before the edit, which is the manifest working correctly and
proves no earlier plan had silently modified a protected file. One `baseline_sha256` *value* was
edited by hand; `git diff -U0` on the manifest shows **2 changed lines** (one `-`, one `+`).
`protected` stays 30, `baseline_sha256` stays 30, `known_dangling` stays 1, no other digest moved.
**`--rebaseline` was not run.** The reason is in the commit message.

`external_hardware_binding.py:118` and `external_hardware_ingress.py:45` were **not touched** —
`git diff --name-only` on both is empty. That is right on the merits, not for convenience: both
dispatch **network** events, and a ZMQ frame from another computer has no hardware edge behind it.
They pass no `ts_mono_ns`, so the fallback policy marks them software-stamped for free, which is the
truthful answer.

## Verification (all fresh, this run)

| Gate | Result |
|---|---|
| `pytest tests/test_single_clock_invariant.py tests/test_event_dispatcher_clock.py tests/test_edge_timestamp_end_to_end.py` | **68 passed** (33 + 21 + 14) |
| `pytest tests/test_execute_trigger_guard.py` (protected, unmodified) | **11 passed** |
| `pytest tests/test_log_value.py` (protected, unmodified) | **18 passed** |
| `pytest tests/test_log_action_values.py` (protected, unmodified) | 9 passed, 1 failed — see Deviations |
| `git diff` on all five protected test files | **empty** |
| Full tree `pytest tests/` | 152 failed / **494 passed** (was 187 / 381) |
| `tools/pytest_delta.py` | `new failures: 0`, exit 0 |
| `tools/rebaseline_pytest.py --check-only` | `baseline is clean (0 unaccepted new failures)` |
| `tools/check_tree_integrity.py --strict` | `39 closure members, 30 protected files, 1 known-dangling, 0 violations`, exit 0 |
| `tools/pulse_timing/py37_gate.py` | exit 0 on **34** members, closure grew from 30 |
| `isoformat` in `gpio.py` | **0** |
| `CLOCK_REALTIME` under `autopilot/autopilot/` | exactly `['utils/clock.py']` |
| `import pigpio` / `get_current_tick` / `ticks_to_timestamp` in `Event_Dispatcher.py` | 0 / 0 / 0 |
| `@auto_log` / bare `auto_log` in `gpio.py` | 1 / 2 (unchanged — `Digital_In` NOT decorated) |
| `tree_protect_list.json` changed lines | 2 |

### Mutation pass — every load-bearing invariant broken deliberately first

| Mutation | Caught by |
|---|---|
| `execute_trigger` drops `ts_mono_ns=` | `test_execute_trigger_passes_its_value_through_to_the_dispatcher` |
| Adapter converts per registration (pre-check removed) | the two fallback-counter tests (`observe()` runs twice) |
| Slot consumed by the first reader | `test_an_uncalibrated_clock_still_delivers_both_registrations_software_stamped` |
| Generation bookkeeping removed (attach always) | `test_a_generation_already_attached_is_not_attached_again` |
| Staleness bound removed | both staleness tests |
| Provenance memo removed | `test_a_broken_clock_still_produces_two_software_stamped_payloads` |
| **Both** per-edge idempotence guards removed | `test_the_slot_is_written_once_per_edge_not_once_per_registration` (generation becomes 2) + 3 more |
| Slot lock removed entirely | **NOT** caught by any outcome test — see below |

Removing the lock left all 66 outcome tests green. That is the CPython 3.12 finding C1 documented,
reproduced here for the slot: the specializing interpreter makes these read-modify-writes
incidentally atomic on this host. Two structural proofs were added; both fail deterministically with
the lock removed. **A concurrency test that has never failed proves nothing.**

One invariant is guaranteed *structurally* rather than by a test: field-by-field publication is
impossible because `EdgeSlot` is an immutable namedtuple and there is no field to write separately.

## Deviations from Plan

### Auto-fixed

**1. [Rule 3 — Blocking] `fake_pigpio` could not construct a real `Digital_Out`/`Digital_In`**
- **Found during:** Task 1, before writing the first test.
- **Issue:** `gpio.py` reads `pigpio.PUD_UP/PUD_DOWN/PUD_OFF/INPUT/OUTPUT` and two
  `PI_SCRIPT_*` constants at **module import time**, inside `try: import pigpio ... except
  ImportError`. A missing *attribute* raises `AttributeError`, which that guard does not catch, so
  importing `gpio` against the fake failed outright. Beyond that, `Digital_Out.__init__` calls
  `set_mode`, `set_pad_strength` and `get_pad_strength`, none of which the fake had.
- **Fix:** extended `tests/fakes/fake_pigpio.py` with the six constants, the two script-state
  constants, and the 17 recording methods `gpio.py` actually calls (enumerated by regex over
  `self.pig.<name>`, not guessed). All are recorded into `.calls`; `reset()` clears the new state.
  No `sync_ticks`/`synchronize`/`ticks_to_timestamp` — the fake still models the **stock** client.
- **Committed in:** `199c595`

**2. [Rule 3 — Blocking] `gpio.py` snapshots `ENABLED` at import, making `fake_pigpio` tests
order-dependent**
- **Found during:** Task 2, on the first full-tree run: 24 of this plan's own tests failed in the
  suite while passing in isolation, with `RuntimeError: pigpio could not be imported`.
- **Issue:** whichever test module imports `autopilot.hardware.gpio` first decides `ENABLED` for the
  whole process. Before this plan the point was moot (`Event_Dispatcher`'s unconditional
  `import pigpio` made every such import fail hard); removing it made the ordering visible.
- **Fix:** `conftest.py`'s `_install_fake_pigpio()` now evicts `autopilot.hardware.gpio` for the
  fixture's lifetime and **restores the original module object afterwards**, so a `fake_pigpio` test
  always gets a fake-bound module and no other test's view changes. Fixed at the source rather than
  duplicated into each test module.
- **Committed in:** `b4c7f45`

**3. [Rule 2 — Missing critical correctness] `execute_trigger` had no way to know its value's
provenance**
- **Found during:** Task 2, wiring `ts_source=` at the dispatcher call.
- **Issue:** the plan says `execute_trigger` must mark `pi_timestamp_source`, and Task 3 requires
  both payloads to be `"software"` when the clock is broken — but it also (correctly) forbids
  `execute_trigger` from reading the slot, which is the `@log_action` bridge's turn. Defaulting to
  `"hardware"` would be a guess, and `execute_trigger` runs on a worker thread draining
  `Task.event_queue`, so by the time it asks, the slot may already describe a newer edge.
- **Fix:** `Hardware._edge_source_for(value_ns)` — a **non-claiming** lookup over the last
  `EDGE_SOURCE_MEMO = 16` edges, under the same lock, that never touches the generation
  bookkeeping. Exact for any realistic trigger-queue backlog; falls back to `TS_HARDWARE` only once
  an edge has aged out of the memo entirely.
- **Verified by mutation:** deleting the memo makes the broken-clock end-to-end case fail.
- **Committed in:** `b4c7f45`

**4. [Rule 1 — Plan inventory wrong] `gpio.py:892` is `Digital_In.assign_cb`, not
`Digital_Out.assign_cb`**
- **Found during:** Task 1, by direct read.
- **Issue:** the plan's corrected inventory says `:892` is `Digital_Out.assign_cb` and that
  `Digital_In.assign_cb` "makes no timestamp claim". It is the other way round: `:892` sits in
  `Digital_In.assign_cb`, and `Digital_Out.assign_cb` had a 3-line docstring documenting nothing.
- **Fix:** all three `isoformat` sites rewritten (the count the plan cares about is right, and it is
  now 0) and the contract **added** to `Digital_Out.assign_cb` and `Hardware.assign_cb`. The plan's
  counted gate passes either way; the inventory is corrected here so the next reader is not
  misdirected.

**5. [Rule 1 — Plan under-specified a load-bearing type] `timestamp` is POSIX epoch seconds**
- **Found during:** Task 2, before writing the dispatcher.
- **Issue:** the plan says keep `timestamp` as "the derived UTC" without saying what type. The
  removed line produced `self.pi.ticks_to_timestamp(tick, isoformat=False)`, whose type is not
  documented anywhere in this repo.
- **Fix:** resolved from the consumer, not from the producer:
  `ElasticSearchDateHandler.py:48` does `datetime.fromtimestamp(data["timestamp"], tz=pytz.utc)`,
  which requires a **number**. `timestamp = t_utc_ns / 1e9`. Every consumer of the key in
  `orchestrator/` was checked and is listed above. A test pins the type and the relationship.

**6. [Rule 3 — Blocking] `conftest.py`'s `collect_ignore` and plan 02's assertion about it**
- **Issue:** `tests/test_log_action_values.py` was ignored solely because `Event_Dispatcher.py:3`'s
  `import pigpio` was a **collection error** (which aborts the whole `tests/` run). This plan
  removes that import, so the reason is gone. `tests/test_shed_absences.py` (plan 02, not protected)
  asserted the entry was present.
- **Fix:** `collect_ignore = []` with the history written down, and plan 02's assertion inverted to
  pin the thing still worth pinning — neither module may quietly reappear, because a module that is
  ignored is a module whose failures nobody sees.

**7. [Rule 1 — my own test bugs] Three defective assertions/harness races, found and fixed**
- `test_a_claimed_generation_is_not_handed_out_twice` used `record=True`, so the `@log_action`
  bridge had already claimed generation 1 by the time the test claimed it. Rebuilt with
  `record=False` and an explicit registration; the end-to-end file covers the `record=True` case.
- The end-to-end harness cleared its payload baseline before the dispatcher's sender thread had
  flushed `assign_cb`'s own (auto-logged) event, so a plain `wait_for(2)` could be satisfied by two
  payloads from one route. Added `settle()` and `wait_for_both_routes()` — the two-route test now
  waits on the **routes**, not on a count.
- `Digital_In` built without `trigger=` leaves `trigger_edge` at `None` and (unlike `Digital_Out`)
  its `assign_cb` has no `EITHER_EDGE` safety net, so callbacks register on a `None` edge mask. That
  is **pre-existing** and outside this plan's fence; the test helper passes `trigger='B'` explicitly
  and says why.

**8. [Housekeeping] `pytz` / `tzlocal` / `datetime` removed from `common.py`**
- Removed only after a repo-wide counted scan proved each had exactly one occurrence there (its own
  import) and no other user in `autopilot/`, `tools/`, `pilot/` or `tests/`. `TIMEZONE` kept.

### Escalated rather than fixed — needs the user

**9. [Rule 4] `tests/test_log_action_values.py` contradicts `autopilot/utils/log_value.py`. Both are
PROTECTED.**
- **Surfaced (not caused) by** removing `Event_Dispatcher.py`'s `import pigpio`: that import was a
  collection error, so the module had been dark since Phase 25. It now collects — **9 of its 10
  tests pass**.
- The failing one asserts `event_data["value"] == "baseline"` for a non-numeric `Tracker.set`. That
  was the Phase 25 contract. Phase 26 (CMP-16) then deliberately changed it:
  `log_value.coerce_for_event` diverts non-numbers to `value_str` and leaves `value` `None`, because
  `event.event_data.value` is mapped `long` in `event_log_v2` and a bare non-numeric string makes
  Elasticsearch reject the **whole document** (proven live, run 549).
- **Neither file was edited.** The failure is recorded in `31-PYTEST-BASELINE.json` under
  `accepted_new_failures` with the full reason, via `tools/rebaseline_pytest.py` (the only
  sanctioned path, which preserves the prior document verbatim under `superseded`), and logged in
  `deferred-items.md` with a suggested resolution. No C2 code is implicated: `logging_utils`'
  `Mics_Tracker` branch is byte-identical.

### Recorded for the next reader

- **Plan line numbers had all shifted** (plans 02/03 ran first): `gpio.py` was 1651 lines, not 1692;
  `task.py:199` is `:180`; `:268` is `:242`; `:273` is `:247`; `:275` is `:249`; `:283` is `:277`.
  Every landmark named in the plan was found by content, and the plan's own advice to re-grep was
  the right call.
- **The plan's Task 1 `<verify>` is not satisfiable at Task 1.** It chains
  `pytest tests/test_log_action_values.py tests/test_execute_trigger_guard.py ...` with `&&`, but
  all five protected tests were pigpio-blocked until **Task 2** removed the import. Task 1's verify
  was run in full except for that clause (with the protected files asserted unmodified and at their
  baseline state instead); Task 2's run has them genuinely passing.
- **The 187-failure baseline was stale by the end of Task 2.** Removing the pigpio import fixed
  **36** previously-blocked tests. Re-baselined to 152 failed / 480 passed via
  `tools/rebaseline_pytest.py`, never `--rebaseline`.
- **`ModuleNotFoundError: No module named 'board'` has surfaced**, exactly as `31-01-SUMMARY`
  predicted for "whichever later plan first unblocks that chain". It now blocks
  `tests/test_load_fda_from_json.py` and most of `tests/test_trigger_assignments.py` — the **same
  node ids** that were pigpio-blocked before, so not new failures, just failing one link further
  down. `board`/`busio` are `adafruit-blinka`, genuinely Pi-only. Logged in `deferred-items.md`.

---

**Total deviations:** 8 auto-fixed (2 blocking, 1 missing-correctness, 2 plan corrections, 1
housekeeping, 1 collect-ignore, 1 set of my own test bugs) + **1 Rule 4 escalation** documented and
deferred rather than papered over. **No scope change:** every `must_have`, `artifact`, `key_link`,
`<done>` clause and `<verification>` step is satisfied.

## The honest limit of the two-route test — C4 must carry this forward

`tests/test_edge_timestamp_end_to_end.py` proves the two paths take their timestamp from the same
value **for one injected edge on a dev host**. It says **nothing** about whether they are still
aligned after hours of continuous operation — and that is *precisely* the way the current design
fails: the deployed client's two paths agree perfectly until the first 71.6-minute tick wrap and are
4294.97 s apart from then on. A test that injects one edge would have passed against the defective
client too.

What is *not* proven here, and what C4's soak must establish:

1. that the alignment survives at least one real tick wrap (the `TickExtender` is unit-tested for
   this in C1, but not in situ through `assign_cb` on real hardware);
2. that the heartbeat keeps the extender fed across a genuinely quiet stretch on the rig, where
   `observe()` is not being called by any edge;
3. that the mapping's re-fits stay inside `max_ppm` against a real 1 MHz hardware counter rather
   than the fake's `CLOCK_MONOTONIC`-derived tick (C1 measured -7.31 ppm as a harness artifact);
4. that `edge_clock_fallbacks()` stays at whatever it reaches during the pre-calibration window and
   does not keep climbing.

The two pieces of evidence are complementary, not redundant.

## Issues Encountered

- The CPython 3.12 lock-atomicity finding (above) — changed how the property is proven, not the
  implementation.
- One real ordering hazard in the test harness (`gpio.ENABLED` snapshotting), fixed at the source in
  `conftest.py` rather than worked around per test module.

## User Setup Required

None.

## Next Phase Readiness

- **C3** attaches the clock: `get_clock().attach(pi)` in `pilot.py` against a **stock**
  `pigpio.pi()`. Everything downstream of that is already wired — until `attach()` is called,
  `observe()` raises `ClockNotReady` and every edge is honestly marked `"software"` with
  `gpio.edge_clock_fallbacks()` counting them. That is the current state of the tree and it is safe.
- **C4** reads `get_clock().counters()` (assert only the four **fault** counters, per C1) and
  `gpio.edge_clock_fallbacks()`. The soak must close the four gaps listed above.
- **Plan 08** takes the Buster baseline on Python 3.7.3; `py37_gate.py` now covers the clock modules
  through `gpio.py`'s import, so that constraint is enforced rather than promised.
- **Carried forward:** the `board`/`adafruit-blinka` blocker and the
  `test_log_action_values.py` vs `log_value.py` contradiction, both in `deferred-items.md`.

---
*Phase: 31-mics-core-modern-pi-platform-bookworm-64-bit-python-3-11-lgpio-unattended-boot*
*Completed: 2026-08-19*

## Self-Check: PASSED

All 3 created and 10 modified paths verified present on disk; the SUMMARY, `deferred-items.md` and
the re-written `31-PYTEST-BASELINE.json` verified present; all 5 `~/mics_core` commit hashes
(`199c595`, `09d32e1`, `97cca37`, `b4c7f45`, `79bd267`) and the planning-repo commit (`a354322`)
verified present via `git log --oneline --all`; branch re-asserted as
`phase-31-modern-pi-platform`; working tree clean; test counts re-measured this run
(33 + 21 + 14 = 68 passed, full tree 152 failed / 494 passed, `pytest_delta.py` `new failures: 0`,
`--strict` 0 violations, `py37_gate.py` exit 0 on 34 members).
