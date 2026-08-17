---
phase: 31-mics-core-modern-pi-platform-bookworm-64-bit-python-3-11-lgpio-unattended-boot
plan: C2
type: execute
wave: 5
depends_on: ["31-C1", "31-03"]
files_modified:
  - /home/ido/mics_core/autopilot/autopilot/hardware/gpio.py
  - /home/ido/mics_core/autopilot/autopilot/hardware/__init__.py
  - /home/ido/mics_core/autopilot/autopilot/utils/common.py
  - /home/ido/mics_core/autopilot/autopilot/tasks/task.py
  - /home/ido/mics_core/autopilot/autopilot/utils/logging_utils.py
  - /home/ido/mics_core/autopilot/autopilot/networking/Event_Dispatcher.py
  - /home/ido/mics_core/tools/tree_protect_list.json
  - /home/ido/mics_core/tests/test_single_clock_invariant.py
  - /home/ido/mics_core/tests/test_event_dispatcher_clock.py
  - /home/ido/mics_core/tests/test_edge_timestamp_end_to_end.py
autonomous: true
requirements: [PLAT-18, PLAT-19, PLAT-27, PLAT-31]
must_haves:
  truths:
    - "assign_cb keeps its signature, so task.py:199 is not edited and the whole trigger layer is undisturbed"
    - "The raw 32-bit tick is converted to t_mono_ns inside assign_cb — the conversion site the deleted pigpio patch used to own"
    - "ONE injected edge on a Digital_Out fires BOTH dispatch routes and both payloads carry the SAME t_mono_ns"
    - "Both of those payloads are marked hardware-stamped, and a software-originated event is marked software-stamped"
    - "The edge-timestamp slot is keyed per edge with a generation counter and is not consumed by the first reader"
    - "A stale edge timestamp is never attached to a later, unrelated method call"
    - "localize_tz takes monotonic nanoseconds and rejects the old ISO-string form loudly"
    - "Every dispatched event carries a raw monotonic nanosecond field and a derived UTC field, and an interval survives a wall-clock step"
    - "The Phase 25 drop counters _dropped_no_clock and _dropped_on_send still exist by name and still count"
  artifacts:
    - path: "/home/ido/mics_core/autopilot/autopilot/hardware/gpio.py"
      provides: "assign_cb tick->t_mono_ns adapter and the per-edge generation-keyed slot, on BOTH Digital_Out and Digital_In"
      contains: "assign_cb"
    - path: "/home/ido/mics_core/autopilot/autopilot/networking/Event_Dispatcher.py"
      provides: "Dual-timebase dispatch with explicit provenance; no pigpio import; drop counters preserved"
      contains: "_dropped_no_clock"
    - path: "/home/ido/mics_core/tests/test_edge_timestamp_end_to_end.py"
      provides: "The mandatory PLAT-27 two-route assertion: one edge, two payloads, one integer, both hardware-stamped"
      min_lines: 90
    - path: "/home/ido/mics_core/tests/test_single_clock_invariant.py"
      provides: "assign_cb signature guard, adapter arity/identity, localize_tz contract, slot generation and staleness"
      min_lines: 100
  key_links:
    - from: "the raw 32-bit tick delivered by stock pigpio's callback"
      to: "MicsClock.observe()"
      via: "an adapter inside assign_cb, because the patched client's notification-thread conversion is deleted"
      pattern: "observe"
    - from: "the assign_cb adapter"
      to: "log_action's Hardware branch at logging_utils.py:97"
      via: "a per-hardware (t_mono_ns, mono_at_write_ns, generation) slot written once per edge and never cleared by a reader"
      pattern: "generation"
    - from: "Task.execute_trigger's pi_timestamp_mono_ns"
      to: "Event_Dispatcher.dispatch_event(ts_mono_ns=)"
      via: "an explicit argument at task.py:283, not a clock read at dispatch time"
      pattern: "ts_mono_ns"
    - from: "t_mono_ns"
      to: "t_utc_ns and the ISO pi_timestamp"
      via: "autopilot.utils.clock — the ONE epoch offset from plan C1, imported by both paths, never reimplemented"
      pattern: "utils.clock"
---

<objective>
Stage 3, part 2. Put both event paths on the one clock, and prove it with one edge.

Purpose: `CONTEXT.md` §13 is a user-stated phase requirement — *one clock aligns every event in the
system* — and `31-REVISED-SCOPE.md` §2 shows it is already broken in production ~20 times a day.
Plan C1 built the clock. This plan is the wiring, and the wiring is where the requirement is actually
won or lost: a phase that ports both halves correctly and never connects them ships two clocks while
claiming one, and nothing in the test suite notices.

**Read the corrected PLAT-27(a) before anything else.** An earlier draft of this phase described an
adapter absorbing lgpio's 4-argument `(chip, gpio, level, timestamp)` callback down to 3 arguments.
**That is withdrawn and must not be implemented.** Stock pigpio's callback is *already*
`(gpio, level, tick)`, so there is **no arity to absorb**. The adapter's real job is
**timestamp conversion**: stock pigpio delivers a **raw 32-bit tick**, and the conversion has to move
into `assign_cb` because the patched client did it inside pigpio's notification thread
(`pigpio.py:1239-1240`) and PLAT-28 deletes that patch. What changes is the **meaning of the third
positional argument** — from "an ISO-formatted string the patched client manufactured" to
"`CLOCK_MONOTONIC` nanoseconds from the one MICS clock" — which is exactly why `localize_tz`'s input
contract changes in the same plan.

Output: an adapter inside `assign_cb` on both classes, a generation-keyed edge slot, a dual-timebase
dispatcher with explicit provenance, one hand-edited manifest entry, and the mandatory two-route
regression test.
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
@.planning/phases/31-mics-core-modern-pi-platform-bookworm-64-bit-python-3-11-lgpio-unattended-boot/31-C1-SUMMARY.md

**Read `CONTEXT.md` §13 and `31-REVISED-SCOPE.md` §2 first — do not re-derive either.** §13 is the
user requirement; §2 is the verified audit of the deployed client. Then read `31-C1-SUMMARY.md` for
the clock's exact public surface; every call in this plan is against it.

<repo_boundary>
ALL code changes land in `/home/ido/mics_core` on branch **`phase-31-modern-pi-platform`**.
NEVER modify `/home/ido/mics-backend` source — only its `.planning/` documents.
</repo_boundary>

<pi_rules>
ABSOLUTE. These override anything else in this plan:
- **NEVER run git on the Pi. NEVER start or stop the pilot. NEVER run any Python file on the Pi.**
- Pi log files are 0 bytes **by design**.
- **`Message` and `hardware_state` are OFF LIMITS.** This matters concretely here:
  `logging_utils.py:95` reads `int(self.hardware_state)` and `:59-77` is a commented-out
  `hardware_state` block. **Reading is fine; editing is not.** Do not uncomment it, do not tidy it,
  do not touch `task.py:273`'s `hardware.hardware_state = level`. You are working inside both files.
- **Do NOT `pip install pigpio` on the dev host.** Everything here is driven by plan 01's fake.
- RTK-proxied grep can render a matching line blank. Prove every absence with a counted `python3 -c`
  printing `text.count(...)`.
</pi_rules>

<integrity_gate>
`cd /home/ido/mics_core && python3 tools/check_tree_integrity.py --strict` must exit 0 at the end of
EVERY task. **NEVER `--rebaseline`.** `--final` is a separate gate, expected to fail until C3.

**Exactly one protected file is touched by this plan, and the manifest edit is budgeted into the
same task as the edit** so no task ever ends with `--strict` red.

Verified 2026-08-17 against `tools/tree_protect_list.json` (30 `protected`, 30 `baseline_sha256`,
1 `known_dangling`):

| This plan's file | Protected? |
|---|---|
| `autopilot/autopilot/networking/Event_Dispatcher.py` | **YES — `baseline_sha256`. Task 2 edits it AND updates its one manifest entry, in the same task and the same commit.** |
| `autopilot/autopilot/hardware/gpio.py` | no |
| `autopilot/autopilot/hardware/__init__.py` | no |
| `autopilot/autopilot/utils/common.py` | no |
| `autopilot/autopilot/utils/logging_utils.py` | no |
| `autopilot/autopilot/tasks/task.py` | no |

**The independent second guard:** `tools/tree_integrity/manifest.py check_event_dispatcher()`
requires the Phase 25 drop counters `_dropped_no_clock` and `_dropped_on_send` to survive **by
name**. They are real fixes (`25-HARDWARE-VALIDATION.md:365-375`) and this plan must not regress
them. `_dropped_no_clock`'s *meaning* narrows here — say so in a comment and in the summary; a
counter whose meaning silently changed is worse than a renamed one.

**Protected tests that must keep passing UNMODIFIED** (do not edit them, do not touch their manifest
entries): `tests/test_log_action_values.py`, `tests/test_execute_trigger_guard.py`,
`tests/test_trigger_assignments.py`, `tests/test_log_value.py`, `tests/test_load_fda_from_json.py`.
`test_execute_trigger_guard.py` calls `execute_trigger` with `hardware=None`, and the `localize_tz`
call sits inside `if hardware and isinstance(hardware, Hardware):`, so it never reaches the changed
lines. If it fails, the change went outside this plan's fence.

**Deliberately OUT of scope, on the merits and not for convenience:**
`autopilot/autopilot/hardware/external_hardware_binding.py:118` and
`external_hardware_ingress.py:45` also call `dispatch_event`. Both are **protected**, and both
dispatch **network** events — a ZMQ frame from another computer has no hardware edge behind it.
The fallback policy covers them correctly and they get marked software-stamped for free. Editing
either would mean two more manifest digests and would break Task 2's one-entry assertion.
</integrity_gate>

<verified_call_sites>
Line numbers verified by direct read on 2026-08-17. **Plans 02 and 03 edit `gpio.py`, `task.py` and
`pilot.py` before this plan runs, so re-grep before editing** — the landmarks are named so you can
find them after they shift.

**`gpio.py` (1692 lines today):**

| Site | What is there |
|---|---|
| `:324` / `:325` | `@auto_log` decorating **`Digital_Out` only** |
| `:343` | `Digital_Out.is_trigger = True` |
| `:347` | `Digital_Out.__init__(..., record=True, ...)` — default ON |
| `:359` | `self.assign_cb(self.record_event, add=True, evented=False)` — the self-registration |
| `:380` | `Digital_Out.assign_cb(self, callback_fn, add=True, evented=False, manual_trigger=None)` |
| `:419` | `Digital_Out.clear_cb` |
| `:428` | `Digital_Out.record_event(self, pin, level, timestamp)` |
| `:815` | `class Digital_In` — **no `@auto_log` decorator** |
| `:843` | `Digital_In.is_trigger = True` |
| `:869` | `self.assign_cb(self.record_event, ...)` |
| `:879` | `Digital_In.assign_cb` — same signature |
| `:928` / `:939` | `Digital_In.clear_cb` / `record_event` |

**`hardware/__init__.py:166`** — the abstract `Hardware.assign_cb(self, trigger_fn)`, whose docstring
currently promises "an isoformatted timestamp". **Update all three docstrings.** A contract
documented in one of two places is how the next person gets it wrong.

**`task.py`:**

| Site | What is there |
|---|---|
| `:17` | `from autopilot.utils.common import localize_tz` |
| `:199` | `hw.assign_cb(partial(self.handle_trigger, hardware=hw))` — **the seam. Do not edit this line.** |
| `:268` | `def execute_trigger(self, pin, level, tick, hardware)` |
| `:273` | `hardware.hardware_state = level` — **off limits, leave byte-identical** |
| `:275` | `tick = localize_tz(tick)` — rebinds in place |
| `:276` | `event_data = {"id": hardware.name, "pi_timestamp": tick}` |
| `:283` | `self.event_dispatcher.dispatch_event(event)` — **the second bridge** |
| `:335` | `def handle_trigger(self, pin, level=None, tick=None, hardware=None)` |

**`logging_utils.py` (102 lines):** `auto_log` at `:8`, `log_action` at `:15`, dispatch at **`:55`**
(the `Mics_Tracker` branch — always software-stamped) and **`:97`** (the `Hardware` branch — **the
bridge**). `:92-95` builds the `Hardware_Event`; `:95` reads `int(self.hardware_state)`.

**`Event_Dispatcher.py`:** `import pigpio` at `:3`; `self.pi` at `:16`; `_dropped_no_clock` /
`_dropped_on_send` at `:25`/`:26`; `_sender_loop`'s
`'timestamp': self.pi.ticks_to_timestamp(msg["tick"], isoformat=False)` at `:44`;
`def dispatch_event(self, event, key='CONTINUOUS')` at `:65`; `tick = self.pi.get_current_tick()` at
`:77` inside a try/except that increments `_dropped_no_clock`, logs at the 1/10/100/every-500 cadence
and **returns without dispatching**; a large commented-out payload duplicate at `:89-94`.

**Preserve two properties of `dispatch_event` that are deliberate, not accidental:** it must
**never raise** (the caller is a hardware/tracker callback, and an exception unwinds it before its
remaining writes — e.g. the view update a transition depends on — can run), and there is **no
fallback timebase** in the sense of stamping from a *different* clock. Falling back to a
software-read `CLOCK_MONOTONIC` **that is marked software-stamped** is not that; it is PLAT-31
working. Falling back to a raw tick presented as a timestamp is the deployed defect. Keep the first,
never do the second.
</verified_call_sites>

<the_two_routes>
## One `Digital_Out` edge fires TWO separately-registered callbacks. This is the normal case.

Verified against the current tree; it is the configuration of every LED, valve, odour and TTL pin on
the rig, not an edge case:

```
one edge on a Digital_Out pin
  |- registration 1: self.record_event            (registered gpio.py:359, from __init__, record=True by default at :347)
  |     `- @auto_log wrapper -> log_action -> dispatch_event      (logging_utils.py:97)
  `- registration 2: partial(handle_trigger, hardware=hw)   (registered task.py:199, because is_trigger is True at :343)
        `- Task.handle_trigger -> Task.execute_trigger -> dispatch_event   (task.py:283)
```

`fake_pigpio.fire_edge` returns the number of registrations it invoked, and for this configuration it
**must return 2**. A test that sees 1 has found a lost registration — most likely `record=False`
leaking in, or an `assign_cb` that replaced instead of appended.

### The slot rule: keyed per EDGE, generation-counted, NOT consumed by the first reader

`@log_action` wraps a **method call**, not an edge, so when it fires there is no `t_mono_ns` in
scope. It needs somewhere to read the edge time from. The obvious shape — "write a last-edge slot,
the first reader clears it" — is wrong here, and PLAT-27's corollary says so explicitly. Both failure
modes are silent:

- **Consume-on-read.** With two dispatches per edge, the second finds an empty slot and is marked
  software-stamped — a scheduler time on an interrupt event, and the cross-path assertion then either
  fails or passes on the wrong one of the two.
- **Write once per registration** (twice per edge, to compensate). One write survives un-consumed and
  attaches to the next unrelated `Digital_Out.set()` / `toggle()` inside the staleness window. The
  pin is an **output**, so that is routine, not rare. The result is a wrong hardware-stamped
  timestamp **indistinguishable from a correct one in Elasticsearch.**

**The rule:**

1. The `assign_cb` adapter writes the slot **once per edge**, *before* invoking any registration, as
   `(t_mono_ns, mono_at_write_ns, generation)`. `generation` is a per-hardware-object counter
   incremented once per edge.
2. `log_action`'s `Hardware` branch (`:97`) **reads** the slot and attaches `t_mono_ns` **iff** the
   slot's age is within `EDGE_SLOT_MAX_AGE_NS` **and** its `generation` is not one this reader has
   already attached.
3. It records the generation it attached; it does **not** clear the slot. Invalidation is by
   generation and by age, never by consumption.
4. `Task.execute_trigger` does **not** read the slot. It already has the value as its third
   positional argument and passes it explicitly. The slot exists solely for the `@log_action` bridge.

**Staleness bound: `EDGE_SLOT_MAX_AGE_NS = 2_000_000` (2 ms).** Derivation, and it belongs in a
comment next to the constant: the reader runs inside the same callback invocation chain as the write
(the adapter writes, then calls `record_event`, which *is* the wrapped method), so the real latency is
microseconds; 2 ms is ~3 orders of magnitude of headroom for a loaded `SCHED_OTHER` scheduler, and it
is ~3 orders of magnitude *below* the shortest inter-trial interval on this rig, so a stale slot can
never bridge two trials. If you choose a different number, justify it on both sides of that sandwich
and record it in the summary.

### `@auto_log` coverage — do NOT "fix" it

`@auto_log` iterates `cls.__dict__`, so it wraps only methods defined on `Digital_Out` **itself**.
`Digital_In` carries no decorator at all, and the subclass overrides (`Solenoid.open`, `TTL.set`,
`Pulse20Hz.start`, `PWM.set`, `LED_RGB.set`) are not wrapped. **Do not decorate `Digital_In`.** Every
IR beam-break, lick and touch line is a `Digital_In`; wrapping the class would add a `Hardware_Event`
per method call across the whole rig. That is a product decision, not a port detail, and it is out of
scope. The input path reaches Elasticsearch through `record_event` and through `execute_trigger`.
Enumerate the actually-wrapped set from `cls.__dict__` at execution time and record it in the summary
rather than trusting any list in a plan.
</the_two_routes>

<the_contracts>
## What each edited surface must look like afterwards

**`assign_cb` — signature unchanged, adapter inside.**
`(self, callback_fn, add=True, evented=False, manual_trigger=None)` on both classes, parameter names,
order and defaults identical. `task.py:199` is not edited. The adapter is a small local function
registered with `self.pig.callback(...)` that:
1. converts the raw tick via the one clock — `t_mono_ns = get_clock().observe(tick)`;
2. on `ClockNotReady` / `ClockFault`, falls back to `get_clock().now_mono_ns()`, marks this edge
   **software**-stamped, increments a named counter and logs at the 1/10/100/every-500 cadence. It
   **never** passes the raw tick on as if it were a timestamp, and it **never** raises out of the
   callback — an exception in pigpio's notify thread kills every subsequent event for every GPIO;
3. writes the per-edge slot (see `<the_two_routes>`), once, before dispatching;
4. calls `callback_fn(gpio, level, t_mono_ns)` — **3 positional arguments**, unchanged arity.
Keep the returned callback object in `self.callbacks` so `clear_cb()`'s `.cancel()` still works, and
keep `add=True` **appending** rather than replacing — that is the property `task.py:199` relies on.

**`localize_tz` (`utils/common.py:329-334`) — contract changed deliberately.**
Takes `CLOCK_MONOTONIC` nanoseconds (int) and delegates to `autopilot.utils.clock.to_utc_iso`.
Returns a tz-aware ISO string, **the same return type as today**, so no Elasticsearch field changes
type. Given a `str` it raises `TypeError` with a message naming the change and the phase. Silent
acceptance of the old form is the failure mode: it would produce a plausible-looking wrong timestamp
nobody would ever catch. Do **not** reimplement the epoch offset here; if `pytz`/`tzlocal` become
unused in `common.py`, remove those imports only after a counted check proves no other use.

**`Task.execute_trigger` — one new name, one new field, one new argument.**
`:273` stays byte-identical. `:275` still rebinds `tick` to the ISO string, because the rebound value
is what downstream user triggers receive at `:293-300` via `trig(tick=...)` and that contract is
preserved. Bind the raw integer to a **separate** name first so it survives into `event_data` as
`pi_timestamp_mono_ns`, add `pi_timestamp_source`, and pass `ts_mono_ns=` and `ts_source=` explicitly
at `:283`. Without that last argument the callback path emits a hardware-stamped `pi_timestamp`
beside a software-stamped `t_mono_ns` — two instants in one record.

**`Event_Dispatcher.dispatch_event(event, key='CONTINUOUS', ts_mono_ns=None, ts_source=None)`.**
With `ts_mono_ns` given, the payload's `t_mono_ns` is **exactly** that integer. Without it, the
dispatcher reads `get_clock().now_mono_ns()` and marks the event `TS_SOFTWARE`. `import pigpio`,
`get_current_tick` and `ticks_to_timestamp` all go.

**The payload key decision, and it is not free.** `timestamp` is consumed downstream by the
orchestrator and by Elasticsearch. **Keep `timestamp`** as the derived UTC (now produced from
`t_mono_ns` through `utils.clock`) and **add** `t_mono_ns`, `t_utc_ns` and `ts_source`. Renaming
breaks live ES queries and the orchestrator for no gain. Record the decision and its reasoning in the
summary; if you conclude otherwise, say why and name every consumer you checked.

**The dual-timebase contract**, into the `Event_Dispatcher` module docstring and the summary:

| Field | Clock | Use for | Never use for |
|---|---|---|---|
| `t_mono_ns` | the one MICS clock, derived from the DMA-sampled tick at the edge | **all** interval / latency / rate analysis within a session | joining across machines |
| `t_utc_ns` / `timestamp` | derived per event through `utils.clock`'s per-call epoch offset | display, joining to backend/session records | interval analysis across a clock step |
| `ts_source` | `"hardware"` or `"software"` | telling a DMA-sampled edge from a scheduler read | assuming uniform precision |

**Honest boundary, into the same docstring so the claim cannot inflate:** this makes each rig's *own*
timing robust and puts both of its event paths on one timeline. It does **not** synchronise a rig's
clock to the backend's or to an ephys system — that needs chrony slewing (plan 05) plus the TTL
hardware pulse as cross-device ground truth, which is Phase 28's territory. And **software-originated
events do not acquire hardware precision** by being on the same timeline; they become *comparable*,
which is why PLAT-31 makes the distinction a field rather than a footnote.
</the_contracts>
</context>

<tasks>

<task type="auto" tdd="true">
  <name>Task 1: The assign_cb adapter, the edge slot, localize_tz and pi_timestamp</name>
  <files>
    /home/ido/mics_core/autopilot/autopilot/hardware/gpio.py
    /home/ido/mics_core/autopilot/autopilot/hardware/__init__.py
    /home/ido/mics_core/autopilot/autopilot/utils/common.py
    /home/ido/mics_core/autopilot/autopilot/tasks/task.py
    /home/ido/mics_core/tests/test_single_clock_invariant.py
  </files>
  <behavior>
    Driven by plan 01's `fake_pigpio` fixture. **Do not `pip install pigpio`.**

    **The seam survives — these are the assertions that stop the trigger layer being disturbed.**
    - `inspect.signature(Digital_In.assign_cb)` and `inspect.signature(Digital_Out.assign_cb)` render
      **identically** to `(self, callback_fn, add=True, evented=False, manual_trigger=None)`. Assert
      the rendered string, so a "harmless" reorder fails.
    - `git diff` touches **zero** lines of `task.py:199`. Assert by reading the file and counting the
      exact registration form `hw.assign_cb(partial(self.handle_trigger, hardware=hw))` — it must
      still be present exactly once.
    - A callback registered through `assign_cb` and then fired by `fake_pigpio.fire_edge(gpio, level,
      tick)` is invoked with exactly **3 positional args and no kwargs**. Capture `*args, **kwargs`
      and assert `len(args) == 3` and `kwargs == {}`. **There is no arity change here** — this
      assertion exists to prove the adapter did not invent one.
    - `args[0]` is the **BCM pin**, `args[1]` the level, `args[2]` the converted `t_mono_ns` — and
      `args[2]` is **not** the raw tick. Inject a tick and a clock calibrated so the two differ
      by a known amount; assert `args[2]` equals `get_clock().observe`-equivalent value, not `tick`.
    - `level == 2` (watchdog timeout) reaches the registered callback with 3 args like any other
      level; the adapter does not swallow it.
    - `assign_cb(..., add=True)` **appends**. Registering a second callback leaves the first live and
      `registration_count(pin)` becomes 2.
    - `clear_cb()` still cancels what it registered: `registration_count(pin)` drops accordingly.
    - `record_event(pin, level, timestamp)` keeps its three-parameter signature on both classes.

    **Two registrations, one edge.**
    - Construct a `Digital_Out` with `record=True` (the default) and additionally register
      `partial(handle_trigger, hardware=hw)` — the exact form from `task.py:199`. `fire_edge` returns
      **2**. **Both** invocations receive the **same** `t_mono_ns`, equal to a single conversion of
      the injected tick. An adapter that converted per registration fails this.

    **The slot.**
    - After one edge, the slot on that object holds `(t_mono_ns, mono_at_write_ns, generation)` with
      `generation == 1`; after a second edge, `generation == 2` and the timestamp updated.
    - The slot is written **once per edge**, not once per registration: after one edge on a
      two-registration object, `generation` is 1, not 2.
    - **Per-object isolation:** an edge on pin A does not change the slot on the object owning pin B.
    - The adapter does **not** clear the slot after invoking the registrations.

    **`localize_tz`.**
    - `localize_tz(1_700_000_000_123_456_789)` returns a tz-aware ISO string, equal to
      `utils.clock.to_utc_iso` of the same value.
    - `localize_tz("2026-08-17T10:00:00.000000")` raises `TypeError` whose message names the change
      and the phase. Assert the message, not just the type.
    - Two `ts_ns` values 1000 ns apart do not collapse to the same ISO string — sub-microsecond
      precision is not lost on the way in.
    - A counted scan proves `CLOCK_REALTIME` still appears in **exactly one** file under
      `autopilot/autopilot/`, and that file is `utils/clock.py`. Reintroducing the expression here
      would satisfy "correct" and fail "one offset".

    **`execute_trigger`.**
    - With a real `Hardware`, `execute_trigger(pin, level, ts_ns, hardware)` builds
      `event_data["pi_timestamp"]` as the ISO string, `event_data["pi_timestamp_mono_ns"]` as the
      injected integer **unchanged** (identity, not approximation), and
      `event_data["pi_timestamp_source"] == "hardware"`.
    - Downstream user triggers still receive the **ISO string** via `trig(tick=...)` — assert it, so
      the `:275` rebinding contract is provably preserved.
    - `execute_trigger(..., hardware=None)` behaves exactly as before and never calls `localize_tz`.
    - `tests/test_execute_trigger_guard.py` and `tests/test_trigger_assignments.py` (**both
      protected**) pass **unmodified**.

    **Failure containment.**
    - With the clock forced into `ClockNotReady`, one edge still reaches both registrations, the
      third argument is a software-read monotonic value, the adapter's fallback counter incremented,
      and **nothing raised out of `fire_edge`**. `fake_pigpio` deliberately propagates exceptions out
      of `fire_edge` (plan 01), so a raise here would fail the test — which is the point.
  </behavior>
  <action>
    1. Write `tests/test_single_clock_invariant.py` FIRST. The two that must fail loudly before you
       implement anything are the `localize_tz(str)` -> `TypeError` case and the "both registrations
       receive the same converted value" case.

    2. Add the adapter **inside** `assign_cb` on `Digital_Out` (`gpio.py:380`) and `Digital_In`
       (`gpio.py:879`). **Both**, not one — a half-ported pair is exactly the silent failure PLAT-27
       exists to prevent. Import the clock as
       `from autopilot.utils.clock import get_clock, TS_HARDWARE, TS_SOFTWARE` and define
       `EDGE_SLOT_MAX_AGE_NS = 2_000_000` as a module constant in `gpio.py` with the derivation from
       `<the_two_routes>` as its comment.

    3. Update **three** docstrings so the contract is stated everywhere it is promised:
       `Digital_Out.assign_cb`, `Digital_In.assign_cb`, and the abstract `Hardware.assign_cb` at
       `hardware/__init__.py:166`. All three currently promise "an isoformatted timestamp"; all three
       must now promise `CLOCK_MONOTONIC` nanoseconds from `autopilot.utils.clock`.

    4. Rewrite `localize_tz` (`utils/common.py:329-334`) per `<the_contracts>`. Two lines of
       delegation plus the `TypeError` guard. Do not add a second epoch offset.

    5. Edit `Task.execute_trigger` per `<the_contracts>`: bind the raw integer to a separate name
       before `:275` rebinds `tick`, add the two new `event_data` keys, and leave `:273`
       byte-identical. **Do not touch `task.py:283` in this task** — Task 2 owns the dispatcher
       signature and wires that argument. At the end of this task `execute_trigger` carries the raw
       value on the event but the dispatcher does not yet receive it; that interim state is expected
       and is what Task 3's assertion later closes.

    6. Do **not** touch `Event_Dispatcher.py`, `logging_utils.py`, or either
       `external_hardware_*` file. Task 2 owns the first two; the third pair is out of scope on the
       merits.
  </action>
  <verify>
    <automated>cd /home/ido/mics_core && /home/ido/.venvs/mics_core_dev/bin/python -m pytest -q tests/test_single_clock_invariant.py tests/test_execute_trigger_guard.py tests/test_trigger_assignments.py tests/test_log_action_values.py tests/test_load_fda_from_json.py --tb=short && /home/ido/.venvs/mics_core_dev/bin/python -c "
import inspect, pathlib, sys
sys.path.insert(0, '.')
task_src = pathlib.Path('autopilot/autopilot/tasks/task.py').read_text()
seam = 'hw.assign_cb(partial(self.handle_trigger, hardware=hw))'
print('task.py:199 seam occurrences:', task_src.count(seam))
if task_src.count(seam) != 1:
    sys.exit('the task.py:199 registration seam was edited or lost; assign_cb must keep its signature so this line never changes')
print('pi_timestamp_mono_ns occurrences in task.py:', task_src.count('pi_timestamp_mono_ns'))
print('pi_timestamp_source occurrences in task.py:', task_src.count('pi_timestamp_source'))
if task_src.count('pi_timestamp_mono_ns') < 1 or task_src.count('pi_timestamp_source') < 1:
    sys.exit('execute_trigger must carry the raw monotonic value and its provenance on event_data')
print('hardware.hardware_state = level occurrences:', task_src.count('hardware.hardware_state = level'))
if task_src.count('hardware.hardware_state = level') != 1:
    sys.exit('task.py:273 hardware_state assignment changed - hardware_state is OFF LIMITS')
root = pathlib.Path('autopilot/autopilot')
hits = sorted(str(p) for p in root.rglob('*.py') if 'CLOCK_REALTIME' in p.read_text(errors='ignore'))
print('CLOCK_REALTIME files under autopilot/:', hits)
if hits != ['autopilot/autopilot/utils/clock.py']:
    sys.exit('a second epoch offset appeared; PLAT-27 requires exactly one: %r' % (hits,))
from autopilot.autopilot.hardware.gpio import Digital_In, Digital_Out
want = '(self, callback_fn, add=True, evented=False, manual_trigger=None)'
for cls in (Digital_In, Digital_Out):
    got = '(self, ' + str(inspect.signature(cls.assign_cb)).lstrip('(')
    got = str(inspect.signature(cls.assign_cb))
    print(cls.__name__ + '.assign_cb signature:', got)
    if 'callback_fn' not in got or 'add=True' not in got or 'evented=False' not in got or 'manual_trigger=None' not in got:
        sys.exit('%s.assign_cb signature changed: %s' % (cls.__name__, got))
gsrc = pathlib.Path('autopilot/autopilot/hardware/gpio.py').read_text()
print('EDGE_SLOT_MAX_AGE_NS occurrences in gpio.py:', gsrc.count('EDGE_SLOT_MAX_AGE_NS'))
if gsrc.count('EDGE_SLOT_MAX_AGE_NS') < 2:
    sys.exit('the staleness bound must be a named module constant used by the adapter')
print('assign_cb adapter sites ok')
from autopilot.autopilot.utils.common import localize_tz
try:
    localize_tz('2026-08-17T10:00:00.000000')
except TypeError as exc:
    if 'monotonic' not in str(exc).lower():
        sys.exit('the localize_tz TypeError must name the contract change; got %r' % str(exc))
    print('localize_tz rejects the old ISO form:', str(exc)[:90])
else:
    raise AssertionError('localize_tz still accepts an ISO string - it would produce a plausible wrong timestamp')
" && /home/ido/.venvs/mics_core_dev/bin/python tools/pytest_delta.py && python3 tools/check_tree_integrity.py --strict</automated>
  </verify>
  <done>Both `assign_cb` signatures render unchanged; `task.py:199` is provably untouched; the adapter converts the raw tick through the one clock and delivers exactly 3 positional args; one edge on a `record=True` `Digital_Out` with a `handle_trigger` registration makes `fire_edge` return 2 and hands both registrations the SAME converted integer; the slot is generation-keyed, written once per edge, per-object isolated and not cleared by a reader; `localize_tz` takes monotonic ns and rejects a string with a message naming the change; `CLOCK_REALTIME` is still exactly one file; all five protected tests pass unmodified; delta gate `new failures: 0`; `--strict` exit 0.</done>
</task>

<task type="auto" tdd="true">
  <name>Task 2: Dual-timebase dispatch with provenance, the @log_action bridge, and the one manifest entry</name>
  <files>
    /home/ido/mics_core/autopilot/autopilot/networking/Event_Dispatcher.py
    /home/ido/mics_core/autopilot/autopilot/utils/logging_utils.py
    /home/ido/mics_core/autopilot/autopilot/tasks/task.py
    /home/ido/mics_core/tools/tree_protect_list.json
    /home/ido/mics_core/tests/test_event_dispatcher_clock.py
  </files>
  <behavior>
    - `dispatch_event(event, key, ts_mono_ns=12345, ts_source="hardware")` produces a payload whose
      `t_mono_ns` is **exactly 12345**. Identity, not approximation.
    - `dispatch_event(event, key)` with no `ts_mono_ns` reads the clock, and the payload's
      `ts_source` is `"software"`. The `Mics_Tracker` branch at `logging_utils.py:55` must always
      take this path — a tracker increment is not an interrupt and must not borrow one.
    - `t_utc_ns` is produced by calling `autopilot.utils.clock`, not by a local copy of the
      expression. A test monkeypatches the shared module's conversion and asserts the dispatcher's
      `t_utc_ns` moves with it; if it does not, a second offset was introduced.
    - **The clock-step test, which is the phase's central claim in miniature.** Dispatch A, simulate
      a **+3600 s** `CLOCK_REALTIME` step, dispatch B: `B.t_mono_ns - A.t_mono_ns` equals the real
      elapsed monotonic interval — **unaffected** — while `B.t_utc_ns - A.t_utc_ns` differs by
      ~3600e9. Then repeat with **-3600 s**. Both directions, and the UTC movement is asserted as
      **correct behaviour**, which is what keeps the claim honest.
    - `dispatch_event` **never raises**, for any input, including a `None` event field, a full queue,
      and a clock forced to raise. A test calls it inside a function that has a subsequent statement
      and asserts the subsequent statement ran.
    - `_dropped_no_clock` and `_dropped_on_send` still exist by name, still increment on their
      respective failures, and still log at the 1/10/100/every-500 cadence.
    - `import pigpio` is gone from the file, and neither `get_current_tick` nor `ticks_to_timestamp`
      appears anywhere in it. Counted assertions, printed.
    - The payload keeps every existing key (`pilot`, `subject`, `session`, `run_id`, `task_type`,
      `continuous`, `session_progress_index`, `subjects`, `event`, `timestamp`) and **adds**
      `t_mono_ns`, `t_utc_ns`, `ts_source`.
    - **The `@log_action` bridge.** A `Hardware` dispatch at `:97` whose object has a fresh slot
      attaches that `t_mono_ns` and marks `"hardware"`. With **no** slot it falls back and marks
      `"software"`.
    - **Staleness.** Set a slot, advance the monotonic clock past `EDGE_SLOT_MAX_AGE_NS`, dispatch:
      the stale value must **not** appear in the payload and the event is software-stamped. Reusing
      an old edge timestamp is worse than a software stamp, because it is indistinguishable from a
      good one once it is in Elasticsearch.
    - **Generation reuse.** After an edge has been attached once by this reader, a *later, unrelated*
      `Digital_Out.set()` inside the staleness window is **software**-stamped. This is the case
      consume-on-read was trying to protect and the generation counter protects properly.
    - `tests/test_log_action_values.py` (**protected**) passes **unmodified**.
    - After the manifest edit, `--strict` is green: exactly one `baseline_sha256` value changed, the
      `protected` list is unchanged at 30, and `known_dangling` is unchanged at 1.
  </behavior>
  <action>
    1. Write `tests/test_event_dispatcher_clock.py` first and watch it fail.

    2. Rewrite `dispatch_event` and `_sender_loop` per `<the_contracts>`. Remove `import pigpio`,
       `get_current_tick` and `ticks_to_timestamp`. Derive `t_utc_ns` and `timestamp` by calling
       `autopilot.utils.clock` — **do not** re-derive the offset here; C1's module is the one site
       and Task 1's verify asserts it.

    3. Keep `_dropped_no_clock` and `_dropped_on_send` by name and keep the cadence. Add a code
       comment recording that `_dropped_no_clock`'s meaning **narrows**: a `CLOCK_MONOTONIC` read
       cannot realistically fail, so the counter now guards the "clock refused to convert" path
       rather than an IPC round trip. `tools/tree_integrity/manifest.py check_event_dispatcher()`
       asserts both names independently — keep them.

    4. Resolve the commented-out payload duplicate at `:89-94`: delete it or reinstate it, and say
       which in the summary. Do not leave a stale duplicate beside a changed implementation.

    5. Implement the slot **reader** on `log_action`'s `Hardware` branch at `logging_utils.py:97`,
       per `<the_two_routes>` rule 2/3. Leave the `Mics_Tracker` branch at `:55` on the
       software-stamped path. **Do not touch `:95`'s `int(self.hardware_state)` or the commented
       `hardware_state` block at `:59-77`** — `hardware_state` is off limits and you are inside the
       file.

    6. Wire `task.py:283`: pass `ts_mono_ns=` and `ts_source=` from the values Task 1 put on the
       event. One argument each. Change nothing else in `execute_trigger`.

    7. **Update the manifest, by hand, for exactly one entry, in this task and this commit.**
       `--strict` is now failing with `protected file MODIFIED:
       autopilot/autopilot/networking/Event_Dispatcher.py`. That is the manifest working correctly.
       - Recompute the digest:
         `python3 -c "import hashlib;print(hashlib.sha256(open('autopilot/autopilot/networking/Event_Dispatcher.py','rb').read()).hexdigest())"`
       - Edit **that one key** under `baseline_sha256`. Change nothing else — not `protected`, not
         `reserved_absent`, not `known_dangling`, not `scan_skip`, not `runtime_generated`, not any
         other digest. `git diff` the file before committing and confirm exactly one value changed.
       - The commit message must name the file, the old and new digest prefixes, and the reason
         (`Phase 31 plan C2: dual-timebase dispatch with provenance, PLAT-18/19/27/31`). The
         manifest's whole value is that a change to a protected file is a documented event.
       - **Do not run `--rebaseline`.** If more than one file is flagged, stop: that means an earlier
         plan modified a protected file without recording it, and the right move is to find out which
         and why, not to bulk-overwrite the evidence. Exactly one protected file changes in this plan.
  </action>
  <verify>
    <automated>cd /home/ido/mics_core && /home/ido/.venvs/mics_core_dev/bin/python -m pytest -q tests/test_event_dispatcher_clock.py tests/test_single_clock_invariant.py tests/test_log_action_values.py tests/test_execute_trigger_guard.py tests/test_log_value.py --tb=short && /home/ido/.venvs/mics_core_dev/bin/python -c "
import json, pathlib, subprocess, sys
ed = pathlib.Path('autopilot/autopilot/networking/Event_Dispatcher.py').read_text()
for banned in ('import pigpio', 'get_current_tick', 'ticks_to_timestamp'):
    print('%r occurrences in Event_Dispatcher.py: %d' % (banned, ed.count(banned)))
    if ed.count(banned):
        sys.exit('Event_Dispatcher.py still references %r' % banned)
for keep in ('_dropped_no_clock', '_dropped_on_send', 't_mono_ns', 't_utc_ns', 'ts_source'):
    print('%r occurrences in Event_Dispatcher.py: %d' % (keep, ed.count(keep)))
    if ed.count(keep) == 0:
        sys.exit('Event_Dispatcher.py lost %r - manifest.py check_event_dispatcher() and PLAT-19/31 require it' % keep)
lu = pathlib.Path('autopilot/autopilot/utils/logging_utils.py').read_text()
print('int(self.hardware_state) occurrences in logging_utils.py:', lu.count('int(self.hardware_state)'))
if lu.count('int(self.hardware_state)') != 1:
    sys.exit('logging_utils.py:95 hardware_state read changed - hardware_state is OFF LIMITS')
tk = pathlib.Path('autopilot/autopilot/tasks/task.py').read_text()
print('ts_mono_ns occurrences in task.py:', tk.count('ts_mono_ns'))
if tk.count('ts_mono_ns') < 1:
    sys.exit('task.py:283 does not pass ts_mono_ns= - the callback path would emit a hardware-stamped pi_timestamp beside a software-stamped t_mono_ns')
m = json.load(open('tools/tree_protect_list.json'))
print('protected:', len(m['protected']), 'baseline_sha256:', len(m['baseline_sha256']), 'known_dangling:', len(m['known_dangling']))
if len(m['protected']) != 30 or len(m['baseline_sha256']) != 30 or len(m['known_dangling']) != 1:
    sys.exit('the manifest shape changed; only ONE digest VALUE may move')
d = subprocess.run(['git', 'diff', '-U0', '--', 'tools/tree_protect_list.json'], capture_output=True, text=True).stdout
changed = [l for l in d.splitlines() if l[:1] in '+-' and l[:3] not in ('+++', '---')]
print('tree_protect_list.json changed lines:', len(changed))
if len(changed) > 2:
    sys.exit('more than one manifest entry changed: %r' % changed)
" && /home/ido/.venvs/mics_core_dev/bin/python -c "
import subprocess, sys
r = subprocess.run(['git', 'diff', '--name-only', '--',
                    'autopilot/autopilot/hardware/external_hardware_binding.py',
                    'autopilot/autopilot/hardware/external_hardware_ingress.py'],
                   capture_output=True, text=True)
print('protected external_hardware files in the diff:', repr(r.stdout.strip()))
if r.stdout.strip():
    sys.exit('a protected external_hardware file was modified; it is out of scope on the merits')
" && /home/ido/.venvs/mics_core_dev/bin/python tools/pytest_delta.py && python3 tools/check_tree_integrity.py --strict</automated>
  </verify>
  <done>`dispatch_event` carries `ts_mono_ns` through by identity and marks provenance; both clock-step directions are proven to move UTC and not intervals; `dispatch_event` provably never raises; both Phase 25 drop counters survive by name with the narrowed meaning commented; `import pigpio` / `get_current_tick` / `ticks_to_timestamp` are gone by counted assertion; the `@log_action` bridge attaches a fresh slot, refuses a stale one and refuses a reused generation; `logging_utils.py:95` and the `hardware_state` block are untouched; exactly one `baseline_sha256` value changed by hand with the reason in the commit message and no `--rebaseline`; `--strict` exits 0; delta gate `new failures: 0`.</done>
</task>

<task type="auto" tdd="true">
  <name>Task 3: The mandatory PLAT-27 assertion — one edge, two routes, one integer</name>
  <files>
    /home/ido/mics_core/tests/test_edge_timestamp_end_to_end.py
    /home/ido/mics_core/autopilot/autopilot/hardware/gpio.py
    /home/ido/mics_core/autopilot/autopilot/utils/logging_utils.py
    /home/ido/mics_core/autopilot/autopilot/tasks/task.py
  </files>
  <behavior>
    This is PLAT-27's closure and `CONTEXT.md` §13's regression test. It is written last because it
    needs both halves, and it is the assertion the whole plan exists to make possible.

    **The two-route test — and it must span the TWO REAL DISPATCH ROUTES, not two fields on one
    route.** Construct a `Digital_Out` the way the rig configures them: `record=True` (the default at
    `gpio.py:347`, so `record_event` self-registers at `:359`) plus
    `partial(handle_trigger, hardware=hw)` (registered at `task.py:199` because `is_trigger` is
    `True` at `:343`). Inject **ONE** edge with a known tick via `fake_pigpio.fire_edge`. Assert:

    1. `fire_edge` returns **2** — both registrations are live.
    2. **Two** payloads were dispatched: one through `logging_utils.py:97` (the `@log_action`
       bridge), one through `task.py:283` (`execute_trigger`). Identify them by route, not by order.
    3. **Both** payloads' `t_mono_ns` equal the single converted value of the injected tick.
       **Exactly.** Not "close to".
    4. **Both** payloads' `ts_source` is `"hardware"`. If `execute_trigger` were left dispatching
       without `ts_mono_ns=`, or if the slot were single-shot, one of these is `"software"` and this
       is what catches it.
    5. `event_data["pi_timestamp_mono_ns"]` on the `execute_trigger` event equals the same integer.

    **Why the two-route form and not the older one.** Comparing `event_data["pi_timestamp_mono_ns"]`
    against `payload["t_mono_ns"]` alone is **not sufficient**: Task 2 sets the second *from* the
    first, in the same function, so that is one route and two fields. It only catches
    "`execute_trigger` forgot the argument". The requirement is that **both event paths** take their
    timestamp from the same value, and the two paths are `logging_utils.py:97` and `task.py:283`.

    **Keep the `t_utc` half — that one IS two independent conversions.** Assert that
    `event_data["pi_timestamp"]` (the ISO string, produced by `localize_tz` -> `utils.clock` on the
    `execute_trigger` path) and the payload's `t_utc_ns` (produced by `Event_Dispatcher` -> the same
    `utils.clock`) decode to the same instant, within a tolerance covering the two vDSO reads on each
    side. Two call sites, one module: this is the assertion a second epoch offset would break, and it
    is worth keeping precisely because it is not tautological.

    **Provenance completeness (PLAT-31).**
    - A software-originated dispatch — the `Mics_Tracker` branch at `logging_utils.py:55`, and an
      `INC_TRIAL_COUNTER` from `utils/Tracker.py:91` — carries `ts_source == "software"`.
    - **Every** dispatched payload in the whole test run carries a `ts_source` key with one of the
      two constants. Collect every payload the test produced and assert the key is present and valid
      on all of them. An event with no provenance is the failure PLAT-31 exists to prevent.

    **The two cases the slot rule exists for, asserted end to end.**
    - **Staleness:** after the edge, advance the monotonic clock past `EDGE_SLOT_MAX_AGE_NS` and call
      `Digital_Out.set()`. Its payload is `"software"` and does **not** carry the earlier
      `t_mono_ns`.
    - **Generation reuse:** immediately after the edge (inside the window), call
      `Digital_Out.set()`. Its payload is `"software"` — the generation was already attached.
    - **Per-object isolation:** an edge on pin A does not stamp an event from the object on pin B.

    **Failure containment, end to end.** With the clock forced to raise, one edge still produces two
    payloads, both marked `"software"`, both with a sane monotonic value, the fallback counters
    incremented, and nothing raised out of `fire_edge`.
  </behavior>
  <action>
    1. Write `tests/test_edge_timestamp_end_to_end.py`. Watch the two-route assertion fail first if
       anything is missing — that failure IS the bug this plan exists to fix, so see it before you
       fix it.

    2. If an assertion fails, fix the **implementation**, not the assertion. The three files listed
       alongside the test are there because a genuine gap may surface here (most likely: the slot
       reader's generation bookkeeping, or a route that dispatches before the slot is written). Any
       change you make to them must keep every Task 1 and Task 2 assertion green — re-run both test
       modules, not just this one.

    3. Enumerate, from `Digital_Out.__dict__` at run time, exactly which methods `@auto_log` wraps,
       and record the list in the summary. Do not trust any list written in a plan, including this
       one. **Do not decorate `Digital_In`** — see `<the_two_routes>`.

    4. Record in the summary the honest limit of this test, because C4 has to carry it forward: a
       dev-host test with an injected tick says nothing about whether the two paths are still aligned
       after hours of continuous operation, which is **precisely the way the current design fails**.
       That is what C4's soak is for, and the two pieces of evidence are complementary, not
       redundant.
  </action>
  <verify>
    <automated>cd /home/ido/mics_core && /home/ido/.venvs/mics_core_dev/bin/python -m pytest -q tests/test_edge_timestamp_end_to_end.py tests/test_single_clock_invariant.py tests/test_event_dispatcher_clock.py tests/test_mics_clock.py tests/test_tick_extender.py --tb=short && /home/ido/.venvs/mics_core_dev/bin/python -m pytest -q tests/test_log_action_values.py tests/test_execute_trigger_guard.py tests/test_trigger_assignments.py tests/test_log_value.py tests/test_load_fda_from_json.py --tb=short && /home/ido/.venvs/mics_core_dev/bin/python -c "
import pathlib, sys
t = pathlib.Path('tests/test_edge_timestamp_end_to_end.py').read_text()
for needed in ('fire_edge', 'logging_utils', 'task.py:283', 'ts_source', 'pi_timestamp_mono_ns', 'hardware'):
    print('%r occurrences in the end-to-end test: %d' % (needed, t.count(needed)))
    if t.count(needed) == 0:
        sys.exit('the PLAT-27 test does not reference %r - it is not spanning the two real routes' % needed)
if t.count('== 2') + t.count('== 2,') == 0:
    sys.exit('the test never asserts fire_edge returned 2; one edge must reach BOTH registrations')
src = pathlib.Path('autopilot/autopilot/hardware/gpio.py').read_text()
print('@auto_log occurrences in gpio.py:', src.count('@auto_log'))
if src.count('@auto_log') != 2:
    sys.exit('@auto_log count changed from 2 (the import at :32 and the Digital_Out decorator at :324); Digital_In must NOT be decorated')
" && /home/ido/.venvs/mics_core_dev/bin/python tools/pytest_delta.py && python3 tools/check_tree_integrity.py --strict</automated>
  </verify>
  <done>One injected edge on a `record=True` + `is_trigger` `Digital_Out` makes `fire_edge` return 2 and produces TWO payloads — the `logging_utils.py:97` route and the `task.py:283` route — both carrying the same converted integer as `t_mono_ns` and both marked `"hardware"`; the ISO `pi_timestamp` and the payload `t_utc_ns` decode to the same instant across two independent `utils.clock` call sites; every payload in the run carries a valid `ts_source`; staleness, generation-reuse and per-object isolation all fall back to `"software"`; the clock-raises case produces two software-stamped payloads and raises nothing out of `fire_edge`; `@auto_log` still appears exactly twice in `gpio.py`; all five protected tests pass unmodified; delta gate `new failures: 0`; `--strict` exit 0.</done>
</task>

</tasks>

<verification>
1. `/home/ido/.venvs/mics_core_dev/bin/python -m pytest -q tests/test_single_clock_invariant.py tests/test_event_dispatcher_clock.py tests/test_edge_timestamp_end_to_end.py` -> pass
2. `/home/ido/.venvs/mics_core_dev/bin/python -m pytest -q tests/test_log_action_values.py tests/test_execute_trigger_guard.py tests/test_trigger_assignments.py` -> pass, all three **unmodified**
3. `python3 -c "import pathlib,sys; t=pathlib.Path('/home/ido/mics_core/autopilot/autopilot/networking/Event_Dispatcher.py').read_text(); print({k: t.count(k) for k in ('import pigpio','get_current_tick','ticks_to_timestamp','_dropped_no_clock','_dropped_on_send','t_mono_ns','ts_source')}); sys.exit(0 if t.count('import pigpio')==0 and t.count('get_current_tick')==0 and t.count('ticks_to_timestamp')==0 and t.count('_dropped_no_clock')>0 and t.count('_dropped_on_send')>0 else 'Event_Dispatcher contract broken')"`
   -> exit 0
4. `python3 -c "import pathlib,sys; root=pathlib.Path('/home/ido/mics_core/autopilot/autopilot'); hits=sorted(str(p) for p in root.rglob('*.py') if 'CLOCK_REALTIME' in p.read_text(errors='ignore')); print(hits); sys.exit(0 if len(hits)==1 else 'more than one epoch offset')"`
   -> exit 0
5. `git -C /home/ido/mics_core diff --stat tools/tree_protect_list.json` -> 1 file, ~1 line
6. `git -C /home/ido/mics_core diff --name-only autopilot/autopilot/hardware/external_hardware_binding.py autopilot/autopilot/hardware/external_hardware_ingress.py` -> **empty**
7. `python3 tools/check_tree_integrity.py --strict` -> exit 0, `30 protected files`, `1 known-dangling exemptions held`, `0 violations`
</verification>

<success_criteria>
- `assign_cb` keeps its signature and its 3-argument contract, so `task.py:199` and the whole trigger
  layer are undisturbed. The conversion moved into `assign_cb` because that is where the deleted
  patch used to do it.
- **PLAT-27 closed:** one injected edge fires both dispatch routes, both payloads carry the same
  integer as `t_mono_ns`, and both are marked hardware-stamped — asserted across the two routes, not
  across two fields on one route.
- The edge slot is keyed per edge with a generation counter and is not consumed by the first reader,
  so neither a second dispatch nor a later unrelated `set()` gets a wrong hardware-looking timestamp.
- `localize_tz` takes monotonic nanoseconds and rejects the old form loudly rather than producing a
  plausible wrong answer.
- Every event carries a monotonic field, a derived UTC field and an explicit provenance flag, and a
  wall-clock step in either direction provably moves the UTC and not the interval.
- Exactly one protected file changed, with one hand-edited manifest entry and a reason in the commit
  message. No `--rebaseline`.
</success_criteria>

<output>
After completion, create
`.planning/phases/31-mics-core-modern-pi-platform-bookworm-64-bit-python-3-11-lgpio-unattended-boot/31-C2-SUMMARY.md`.

Include:
- the `assign_cb` signature **before and after** (they must match), and the adapter's shape;
- the edge-slot design as implemented — generation-keyed, not consumed — and the **staleness bound
  with its two-sided justification**;
- the `@auto_log` coverage list enumerated from `Digital_Out.__dict__` at run time, plus the explicit
  decision NOT to decorate `Digital_In` and why;
- the dual-timebase contract table and the decision on the `timestamp` key's backward compatibility,
  with the consumers checked;
- the new `localize_tz` contract and confirmation that `autopilot/utils/clock.py` is still the only
  `CLOCK_REALTIME` site in the pilot import path;
- the fate of the commented-out payload duplicate at `Event_Dispatcher.py:89-94`;
- the narrowed meaning of `_dropped_no_clock`;
- the old and new sha256 prefixes for the single manifest entry;
- confirmation that neither protected `external_hardware_*` file was touched, and why that is right
  on the merits;
- the **honest limit** of the two-route test, for C4 to carry into its "not proven here" section.
</output>
