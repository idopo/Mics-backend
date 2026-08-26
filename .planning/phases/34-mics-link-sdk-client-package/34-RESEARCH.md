# Phase 34: MICS-Link SDK Client Package - Research

**Researched:** 2026-08-26
**Domain:** Python client-library packaging (pip/git-subdirectory install), MessagePack wire
codec parity, ZMQ DEALER transport with a substitutable/testable seam, bounded non-blocking
producer/consumer queues, background reconnect + heartbeat + command-dispatch threading.
**Confidence:** HIGH (packaging and wire-parity claims below were empirically verified on this
host, not just read about; transport/threading design is HIGH-confidence pattern-matching
against the Pi's own already-proven `external_hardware_runtime.py` split; ZMQ reconnect-event
mechanics are MEDIUM — verified against docs/issue trackers, not exercised live yet).

## Summary

Phase 34 has an unusually strong head start: **the Pi side already solved every hard problem
this SDK needs to solve**, in `external_hardware_runtime.py` (`EgressWorker`, `LivenessPoller`,
`LifecycleRunner`) and `external_hardware_wire.py` (pure codec, socketless, dict-in/dict-out).
The SDK is not a green-field design — it is the same shape, mirrored onto the sender side, built
against a wire format that is already frozen and byte-stable. The single highest-value thing
this research did was verify, empirically, on this machine, that: (a) `msgpack.packb` produces
**byte-identical output** for the same dict under both `msgpack==1.0.5` (rig-pinned) and
`msgpack==1.2.1` (dev host) — the version-skew risk flagged in CONTEXT.md is real in principle
but does not manifest for this codec's usage pattern; and (b) the exact packaging shape CONTEXT.md
prescribes (`sdk/pyproject.toml`, `src/mics_link/`, `pip install "git+...#subdirectory=sdk"`,
`python -m build --wheel`) **works end-to-end today**, proven with a throwaway repo on this host.

The one real design fork the Pi side does not hand you an answer for is **SDK-07's
`on_state_change` callback**: a bare ZMQ DEALER reconnects transparently at the libzmq level with
no application-visible signal, so "connected/disconnected" must come from `zmq`'s socket-monitor
mechanism (an inproc PAIR socket emitting `ZMQ_EVENT_CONNECTED` / `ZMQ_EVENT_DISCONNECTED` /
`ZMQ_EVENT_CONNECT_RETRIED`). This is the one piece of the transport that cannot be faked away
entirely — but the *decision logic* driven by those events can and must be, mirroring exactly how
`ready_gate_decision()` and `LivenessPoller` keep pure decisions separate from thread plumbing.

The other overlooked-until-now finding: **the Pi has zero existing implementation of sending `CMD`
or receiving `ACK`** — `encode()`/`cmd_id` appear nowhere outside `external_hardware_wire.py`
itself. SDK-08 (dispatch inbound CMD, reply ACK) is real and must be built, but it can only be
proven this phase with **synthetic CMD frames the agent constructs**, never with a live
Pi-initiated round trip — there is no Pi-side sender of CMD to exercise it against, on the rig or
anywhere else, until a future phase builds one.

**Primary recommendation:** Mirror the Pi's codec/runtime split exactly (`wire.py` pure codec,
`transport.py` thin ZMQ glue behind a factory seam, `sender.py`/`heartbeat.py`/`reconnect.py`/
`commands.py` as pure, injectable-clock, injectable-thread state machines) — package it with
`setuptools` + PEP 621 `pyproject.toml` in a `src/` layout under `mics-backend/sdk/`, pin the
golden-frame corpus's canonical reference to `~/mics_core/.../external_hardware_wire.py` **per
user direction mid-research (2026-08-26): "we are working on the mics_core"** — this is the
platform this SDK is being built for going forward. Keep `~/pi-mirror/...` as a secondary
skip-if-absent parity check, since it is byte-identical today and is what the rig checkpoint's
own fixture (pilot 1) may still actually be running until its migration status is reconfirmed
(see Open Question 1 — pilot 1 was last confirmed on the old stack 2026-08-17, nine days stale
relative to this research).

## User Constraints

(Copied verbatim from `34-CONTEXT.md` — see that file for full prose; summarized structure below
for planner convenience. **This section, plus the full CONTEXT.md, is binding.**)

### Locked Decisions
- Distribution: primary `pip install "git+https://github.com/idopo/Mics-backend.git#subdirectory=sdk"`
  (public repo, no credentials); offline fallback is a `python -m build` wheel shipped alongside;
  bare `pip install mics-link` (PyPI) is explicitly deferred.
- API must be additive (3-4 lines into an existing loop), not architectural — no base class to
  inherit, no main-loop handoff.
- Device-neutral: nothing in `mics_link` may know what a keypoint is; Phase 35's DLC adapter must
  be writable from the README alone.
- Caller never configures a heartbeat number derived from the Pi's `stale_ms` — the SDK picks a
  safe default, overridable.
- `seq` is never surfaced to the caller; it is maintained (not reset) across reconnect.
- Lifecycle: context manager + explicit `close()`.
- Dtype rejection happens at the `send_signal`/`send_event` call site, not silently on the wire.
- Drops: readable counter AND rate-limited log, both on by default, plus an optional callback.
- `on_state_change` callback for connected/disconnected; ignoring it must be safe.
- No exception ever escapes into the caller's loop — absolute, applies to reconnect, CMD dispatch,
  and the drop path.
- Replay: accepts CSV and JSONL; three timing modes (real-time, scaled, as-fast-as-possible);
  malformed row is counted and skipped, never aborts the replay.
- Golden corpus canonical reference must be pinned to ONE named path (see Open Questions/decision
  below) — this phase must not edit `external_hardware_wire.py`.
- Driver cutover: `extlink_wire.py` deleted, `extlink_driver.py` imports the SDK, CLI/tests
  unchanged in behavior; the driver's distribution story (currently a hand-copied zip) now
  requires the SDK to be installed on the laptop running it.
- Testing: SDK is socketless-testable; the rig checkpoint is USER-RUN only.

### Claude's Discretion
- Exact class/function naming, constructor vs. factory, module layout under `sdk/mics_link/`.
- Concrete heartbeat default interval and its derivation.
- Drop-log rate-limiting policy and counter/stats object shape.
- Replay file column schema and CLI invocation form.
- Internal seam design for the substitutable transport.
- README structure beyond SDK-13's mandatory content list.

### Deferred Ideas (OUT OF SCOPE)
- Publishing to PyPI / claiming the `mics-link` public name.
- Stub generation from a hardware lib's declared `@signal`s, bootstrap-zip endpoints, "Download
  SDK" GUI button (all three deferred from Phase 18).
- `sub_connect` support in the SDK.
- Latency/jitter measurement (Phase 28).
- Refreshing/retiring `extlink_driver_mac.zip` (only constraint here: don't reintroduce a second
  wire copy through it).

## Phase Requirements

| ID | Description | Research Support |
|----|-------------|-------------------|
| SDK-01 | Distributable `mics-link` pkg at `sdk/`, Python 3.8+, macOS/Win/Linux, only `pyzmq`+`msgpack`, not under `~/pi-mirror`/`~/mics_core` | Packaging section — empirically verified `src/` layout + setuptools + subdirectory git install + `python -m build` wheel, all working end-to-end on this host |
| SDK-02 | Wire parity enforced by a golden-frame corpus test, not review | Wire Parity Mechanics section — empirically verified msgpack 1.0.5 vs 1.2.1 byte-identical output; corpus design (frozen + live-interop dual test) below |
| SDK-03 | DEALER identity=`source_id`, `router_bind` only, impossible to send under a different identity | Architecture Patterns — identity fixed at construction, no mutator; `socket_plan`/`identity_ok` precedent in `external_hardware_wire.py` |
| SDK-04 | `send_signal`/`send_event`, `ts_src`+monotonic `seq` stamped by SDK, dtype rejected at call site | Architecture Patterns — codec module mirrors `resolve_dtype`/`coerce_value`, bool-vs-int-subclass pitfall carried over |
| SDK-05 | Background heartbeat keeping a quiet source alive, no caller action | Common Pitfalls / heartbeat default derivation — recommends 1s default against observed real `stale_ms=3000` fixture value |
| SDK-06 | Sends never block; bounded queue, drop-NEWEST, readable counter + surfaced loss | Don't Hand-Roll + Architecture — `queue.Queue(maxsize=N)` + `put_nowait`/`queue.Full`, directly mirrors proven `EgressWorker` |
| SDK-07 | Reconnect survivable: no exception escapes, `seq` maintained, `on_state_change` callback | Architecture Patterns + Common Pitfalls — ZMQ socket-monitor mechanics researched, known libzmq/pyzmq monitor-reconnect interaction flagged, pure-state-machine seam recommended |
| SDK-08 | Inbound CMD dispatched off hot path, ACK replied, handler exception -> error ACK | Architecture Patterns — critical finding: Pi has NO existing CMD-send/ACK-receive implementation anywhere; this can only be proven with synthetic frames, not a live Pi round trip |
| SDK-09 | Context manager + explicit `close()`, stated drain/abandon rule | Architecture Patterns — `EgressWorker.drain()`/`stop()` precedent |
| SDK-10 | Exactly one sender-side wire impl; `extlink_wire.py` deleted; driver retargeted, CLI/tests unchanged | Driver Cutover section — read all three driver files, lazy-import pattern documented, exact edit points identified |
| SDK-11 | Fully unit-testable, no socket/network/Pi | Validation Architecture + Architecture Patterns — seam design mirrors `external_hardware_wire.py`/`external_hardware_runtime.py` split verbatim |
| SDK-12 | Replay entry point: CSV/JSONL, real-time/scaled/as-fast-as-possible, malformed row counted not fatal | Code Examples — replay driver sketch, entry-point wiring via `[project.scripts]` |
| SDK-13 | README: install, rig prerequisites, exact `pilot_hardware_config.config` shape, 10-line sender, how to observe result | Code Examples + existing `tools/extlink_driver/README.md` structural precedent (read in full) |

## Standard Stack

### Core
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|---------------|
| `pyzmq` | >=25 (dev host has 27.1.0; rig's Pi side runs libzmq via its own zmq install) | ZMQ DEALER transport | Same dependency `tools/extlink_driver/` already requires; only viable route to a ZMQ ROUTER |
| `msgpack` | >=1.0 (dev host 1.2.1; rig pinned 1.0.5) | Wire codec | Locked by the frozen Pi-side envelope; verified byte-identical across this version spread |

### Supporting (build-time only, not runtime deps)
| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| `setuptools` | >=61 | PEP 621 build backend | Declared in `[build-system]`; not a runtime dependency of installed users |
| `build` | latest | Produces the offline-fallback wheel | `python -m build --wheel` from `sdk/`, verified working |
| `pytest` | project already uses it | SDK's own test suite | Consistent with the rest of the repo's Python testing |

### Alternatives Considered
| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| `setuptools` build backend | `hatchling` | Hatchling is leaner and trendier for new pure-Python packages, but its default file-inclusion is VCS(.gitignore)-aware "magic" that needs to be gotten right for a *subdirectory* build inside a larger monorepo; `setuptools` with an explicit `packages.find(where=["src"])` has zero ambiguity and was the one actually verified end-to-end here. Given this is the **first** `pyproject.toml`-based package in this repo (see Anti-Patterns), predictability wins over leanness. |
| `queue.Queue` for bounded sender | `queue.SimpleQueue` / custom ring buffer | `SimpleQueue` has no `maxsize` (can't express "bounded, drop-newest" natively); a custom ring buffer duplicates what `queue.Queue(maxsize=N)` + `put_nowait()`/`queue.Full` already gives for free, and diverges from the Pi's own already-proven `EgressWorker` pattern for no benefit |
| ZMQ socket-monitor for connect/disconnect | Pure heartbeat-timeout inference | No Pi-side ACK exists for HB (fire-and-forget), so the SDK has no application-level echo to time out on; the *only* code-visible connect/disconnect signal available is the monitor. Heartbeat-timeout inference could still serve as a **belt-and-suspenders backstop** (e.g. "no send has succeeded in N heartbeat intervals") layered on top |

**Installation (for the SDK's own `pyproject.toml`):**
```bash
python3 -m pip install pyzmq msgpack
```
Users of the SDK need nothing else. Contributors building it locally additionally need
`python3 -m pip install build pytest`.

## Architecture Patterns

### Recommended Project Structure
```
mics-backend/sdk/
├── pyproject.toml          # self-contained; no path references above sdk/
├── README.md                # SDK-13's deliverable
├── src/
│   └── mics_link/
│       ├── __init__.py       # public API surface: Link/Client, exceptions
│       ├── wire.py           # pure codec — mirrors external_hardware_wire.py's shape
│       ├── transport.py      # ZMQ DEALER glue behind a factory/seam (the ONE untestable-offline sliver)
│       ├── sender.py         # bounded queue + drop-newest worker (mirrors EgressWorker)
│       ├── heartbeat.py       # interval scheduling, pure + injectable clock
│       ├── reconnect.py       # pure state machine consuming monitor events
│       ├── commands.py        # inbound CMD dispatch + ACK reply, off hot path
│       ├── client.py          # wires the pieces together; context manager + close()
│       └── replay.py          # SDK-12 entry point (console_script)
└── tests/
    ├── golden_frames.py       # frozen corpus (see Wire Parity section)
    ├── test_wire_parity.py
    ├── test_sender_bounded_drop.py
    ├── test_heartbeat_scheduling.py
    ├── test_reconnect_state_machine.py
    ├── test_command_dispatch.py
    ├── test_replay.py
    └── fake_transport.py       # in-memory substitute implementing transport.py's seam
```
Every module above stays comfortably under the repo's 300-line production-file limit if split
this way — this is exactly the granularity `external_hardware_wire.py` (291 lines) /
`external_hardware_runtime.py` (299 lines) already settled on for the same problem.

### Pattern 1: Codec as pure functions (mirror `external_hardware_wire.py`)
**What:** `encode(kind, **fields)` / `decode_envelope(raw)` with zero I/O, zero threading, zero
`zmq` import — exactly the Pi's module.
**When to use:** Always, for anything wire-format-related. This is what makes SDK-02's parity
test possible at all.
**Example (Pi's own function, reusable almost verbatim as the SDK's encoder core):**
```python
# Source: ~/mics_core/autopilot/autopilot/hardware/external_hardware_wire.py:63-69
def encode(kind, **fields):
    if kind not in WIRE_KINDS:
        raise ValueError("encode: unknown wire kind {!r}".format(kind))
    payload = {"k": kind}
    payload.update(fields)
    return msgpack.packb(payload, use_bin_type=True)
```
**Critical constraint:** field order in the resulting dict is the **kwarg order at the call
site**, because `payload.update(fields)` preserves `**fields`'s insertion order, which Python
builds from the order keyword arguments were passed. The SDK's own call sites must pass kwargs in
the exact documented order per kind (`ts_src, seq, sig, v` for SIG; `ts_src, seq, evt, p` for EVT;
`ts_src, seq` for HB; `ts_src, cmd_id, result` for ACK) to guarantee byte-for-byte parity, not just
same-key-set parity.

### Pattern 2: Transport behind a factory seam (mirror `socket_plan` + `.bind()`)
**What:** A `transport.py` that exposes a small interface (`send(bytes)`, `poll(timeout) ->
[frames]`, `close()`) implemented once for real ZMQ and once as an in-memory fake for tests.
Everything above this seam (`sender.py`, `heartbeat.py`, `reconnect.py`, `commands.py`) takes the
seam as a constructor argument and is tested exclusively against the fake.
**When to use:** This IS the SDK-11 requirement; it is not optional plumbing, it is the load-bearing
design decision of the whole package.
**Precedent:** `external_hardware_runtime.py`'s `EgressWorker.__init__(self, send_fn, ...)` already
takes "how to actually send" as an injected callable rather than importing a transport — same idea,
one level up.

### Pattern 3: Pure decision functions + thin thread wrappers (mirror `LivenessPoller`/`ready_gate_decision`)
**What:** Keep every stateful *decision* (should we heartbeat now? did we just transition
connected->disconnected? does this CMD name have a handler?) as a plain function/small class taking
explicit inputs (clock value, event, registry) and returning an explicit output — no socket, no
thread, inside the function body.
**When to use:** For `reconnect.py`'s state machine and `heartbeat.py`'s "is it time yet" check.
**Example (the exact style to follow):**
```python
# Source: ~/mics_core/autopilot/autopilot/hardware/external_hardware_runtime.py:202-211
def ready_gate_decision(all_ready, skip_requested, elapsed_s, timeout_s):
    if all_ready:
        return GATE_PROCEED
    if skip_requested:
        return GATE_SKIP
    if elapsed_s >= timeout_s:
        return GATE_TIMEOUT
    return GATE_WAIT
```
A `reconnect.py` analog: `def next_state(current_state, monitor_event) -> new_state`, unit-tested
with a list of synthetic monitor events, zero sockets involved.

### Pattern 4: Bounded queue, drop-NEWEST (mirror `EgressWorker`)
**What:** `queue.Queue(maxsize=N)`; producer calls `put_nowait()`, catches `queue.Full`, increments
a counter, calls an optional `on_drop` callback, returns `False` — never blocks, never raises to
the caller.
**Example (verbatim-reusable shape):**
```python
# Source: ~/mics_core/autopilot/autopilot/hardware/external_hardware_runtime.py:44-56
def enqueue(self, item):
    try:
        self._queue.put_nowait(item)
        return True
    except queue.Full:
        self.dropped += 1
        if self._on_drop is not None:
            try:
                self._on_drop(item)
            except Exception:
                pass
        return False
```
This is literally SDK-06's specification. Do not invent a ring buffer or a different drop policy —
this is the proven, already-reviewed answer to the identical constraint on the other side of the
wire (EXTLINK-15).

### Pattern 5: One IO thread owns the socket; dispatch handlers run elsewhere
**What:** ZMQ sockets are not thread-safe — exactly one thread may call `send`/`recv`/`poll` on a
given socket. That thread's loop: poll for (a) outbound queue having an item, (b) inbound frames
arriving, (c) heartbeat interval elapsed, (d) monitor events — using `zmq.Poller` across the DEALER
socket and the monitor's PAIR socket together. **Command handlers must NOT run inline on this
thread** — a slow or hanging researcher-supplied handler would stall heartbeats, reconnection
detection, and outbound draining all at once. Hand each decoded CMD to a small dedicated worker
(a single background thread or a 1-worker `ThreadPoolExecutor` is enough; SDK-08 doesn't require
concurrency, just isolation) that runs the handler, catches all exceptions, and enqueues the ACK
frame back onto the same bounded outbound queue everything else uses.
**Why this matters:** it is the direct mechanism by which SDK-08 ("runs off the caller's hot path")
and SDK-07 ("no exception ever escapes") are satisfied simultaneously without a second socket.

### Anti-Patterns to Avoid
- **Reaching for `hatchling`'s default file discovery inside a monorepo subdirectory** without
  testing it — VCS-aware auto-inclusion can silently pull in files outside `sdk/` or (more often)
  silently exclude something you needed, and there is no existing example of it in this repo to
  copy from. `setuptools` with an explicit `where=["src"]` was the one actually verified.
- **Adding a first `pyproject.toml` without flagging the deviation.** This repo's own Python rules
  say "this project uses `requirements.txt` (not pyproject.toml)." That rule is about the
  *services* (api/orchestrator/web_ui, deployed via Docker); `sdk/` is a **redistributable PyPI-
  style package** for machines outside this repo entirely, which `pyproject.toml` exists
  specifically for. State this exception explicitly in the plan rather than silently contradicting
  the stated convention.
- **Trying to detect "connected" via `stale_ms`/heartbeat-ack timing alone.** There is no ACK for
  HB on this wire (fire-and-forget by design, per EXTLINK-15's philosophy carried over) — timeout-
  based inference can only ever tell you "we haven't heard back in a while," never "we are
  currently connected," and conflating the two will produce a callback that lies during a slow-but-
  fine network as readily as during a real drop.
- **Building the reconnect/heartbeat/command state machines as methods entangled with the ZMQ
  socket object itself.** If `next_state()` or `is_heartbeat_due()` needs a live socket to be
  called, SDK-11 is violated by construction. Every such function must take its inputs as plain
  arguments (event, elapsed time, clock) and return plain outputs.

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|--------------|-----|
| MessagePack encode/decode | A second hand-rolled envelope builder (this is exactly what `extlink_wire.py` was and SDK-10 deletes) | `msgpack.packb(obj, use_bin_type=True)` / `msgpack.unpackb(raw, raw=False)`, called with the Pi's exact field order | Two independent implementations of one envelope is the drift Phase 18 already produced once; SDK-02 exists specifically to make a repeat impossible |
| Bounded producer/consumer with drop policy | A custom ring buffer or `deque(maxlen=N)` (silently drops the OLDEST, the wrong end per EXTLINK-15/SDK-06) | `queue.Queue(maxsize=N)` + `put_nowait()` / `queue.Full` | `deque(maxlen=N)` on `.append()` silently evicts from the opposite end you want; `queue.Queue` gives correct blocking/non-blocking semantics and thread-safety for free |
| Connect/disconnect detection on a DEALER | Polling `socket.getsockopt` or timing sends by hand | `zmq_socket_monitor()` / `Socket.monitor()` inproc PAIR socket, decoding `ZMQ_EVENT_*` | This is the only mechanism libzmq exposes for this; nothing else observes it |
| CSV/JSONL parsing for replay | Hand-rolled line splitting | `csv.DictReader` / `json.loads` per line (stdlib only, no new dependency) | Stdlib already handles quoting, escaping, and malformed-line detection cleanly; a hand-rolled splitter would need to reinvent CSV quoting rules to be robust |

**Key insight:** every "don't hand-roll" item above already has a hand-rolled failed-or-fragile
precedent *somewhere in this same codebase or its history* (`extlink_wire.py` itself, the pilot's
already-fixed egress-drop-oldest-vs-newest distinction) — this phase's job is largely "don't repeat
that," not "invent something new."

## Common Pitfalls

### Pitfall 1: Kwarg order drift breaking byte parity silently
**What goes wrong:** SDK's `encode()` wrapper is called with fields in a different order than the
Pi's documented envelope order (e.g. `v=value, sig=name` instead of `sig=name, v=value`) — the
resulting dict has the same keys and decodes fine, but the *bytes* differ, and a naive test that
only asserts `unpackb(sdk_bytes) == unpackb(pi_bytes)` would pass while SDK-02's actual "byte-for-
byte" requirement silently fails.
**Why it happens:** MessagePack (like Python dicts) is order-sensitive at the byte level even
though the *decoded* value is order-independent; it's easy to write a test that checks the decoded
dict and believe you've checked the bytes.
**How to avoid:** SDK-02's test must assert on the raw `bytes` (`==` on the packed output, or hex
comparison), not just on the unpacked dict, for at least one representative frame per kind.
**Warning signs:** A parity test that calls `msgpack.unpackb` on both sides before comparing is
testing the wrong thing.

### Pitfall 2: `bool`-as-`int` silently miscoerced (already-known trap, must be re-verified on the SDK side)
**What goes wrong:** `send_signal("armed", 1)` intended to mean `True` for a `bool`-typed signal;
Python's `isinstance(1, bool)` is `False` but `bool(1) is True`, so a naive coercion path could
"succeed" with the wrong semantic, or (worse) a value intended as `int` `1` gets silently treated
as bool-truthy somewhere in dtype validation.
**Why it happens:** `bool` is a subclass of `int` in Python; `float(True) == 1.0` and `int(True) ==
1` both succeed without error, hiding a type mismatch that should have been rejected.
**How to avoid:** Reuse the Pi's exact special-casing at the SDK's own dtype-rejection call site
(SDK-04): check `isinstance(value, bool)` explicitly before/instead of any `dtype(value)` coercion
attempt, exactly as `coerce_value()` in `external_hardware_wire.py:87-99` does.
**Warning signs:** A test that only checks `int`/`float`/`str` rejection paths and never exercises
"an int passed where a bool signal is declared" or vice versa.

### Pitfall 3: ZMQ socket-monitor interacting badly with libzmq's own reconnect timer
**What goes wrong:** Attaching a monitor socket to a DEALER has been reported (libzmq #3745,
pyzmq #1340) to interfere with automatic reconnection under some version/idle-duration
combinations — the exact mechanism this SDK needs for SDK-07's `on_state_change` callback.
**Why it happens:** The monitor PAIR socket shares internal reconnect-timer bookkeeping with the
monitored socket in some libzmq versions; specific reports describe failure after ~90s of
bilateral silence.
**How to avoid:** (1) Keep the *decision logic* (reconnect.py) fully separated from the *event
source* (the monitor), so if the monitor mechanism needs to be swapped for something else later,
only the thin glue changes. (2) Before relying on this in production, run an explicit manual
reconnect-survives-monitor smoke test against the actual `pyzmq==27.1.0` (dev host) — this is a
MEDIUM-confidence finding from issue trackers, not verified live in this research pass, and should
be an early implementation task, not an assumption carried silently into the plan.
**Warning signs:** A sender that stops reconnecting after a Pi restart specifically when it has
been idle a while beforehand.

### Pitfall 4: Assuming SDK-08 can be proven on the rig
**What goes wrong:** Planning a rig-checkpoint step that expects a live Pi-initiated `CMD` ->
SDK `ACK` round trip to prove SDK-08 end-to-end.
**Why it happens:** The wire envelope table lists `CMD` as a real, documented frame kind, which
reads as "this already works on the Pi, just consume it" — but grepping the entire `mics_core` and
`pi-mirror` autopilot trees for `cmd_id`/`"CMD"` usage outside `external_hardware_wire.py` itself
returns **nothing**. No Pi-side code sends a `CMD` frame or processes an `ACK` anywhere in this
codebase today.
**How to avoid:** Scope SDK-08's verification to agent-driven synthetic-frame tests only (construct
a raw `CMD` envelope with the Pi's own `encode()`, feed it to the SDK's decoder + dispatcher,
assert the resulting `ACK` bytes decode correctly) and say so explicitly in the plan, rather than
silently expecting the rig checkpoint to touch this path.
**Warning signs:** A plan task that reads "verify CMD/ACK round-trip on the rig" with no Pi-side
sender identified to originate the CMD.

### Pitfall 5: `identity_ok`-style mismatches are invisible from the sender by design
**What goes wrong:** A researcher typos `source_id` (or the SDK lets it drift from the identity
actually set on the socket) and every frame is silently dropped by the Pi's ROUTER — EXTLINK-02
explicitly makes this drop invisible to the sender (there is no rejection frame sent back).
**Why it happens:** ZMQ ROUTER sockets simply discard frames from an unrecognized identity; there
is no NAK.
**How to avoid:** SDK-03 requires the API make it *impossible* to send under any identity but the
configured `source_id` — enforce this by only ever setting `zmq.IDENTITY` once, at construction,
with no public setter, and document in the README that "connected" (via `on_state_change`) does
NOT mean "the Pi is accepting my identity" — TCP-level connection and ROUTER-level identity
acceptance are different layers and only the former is observable from the sender side.
**Warning signs:** README or docstring language implying `on_state_change(True)` means "the Pi
is receiving my signals" — it only means the TCP session exists.

## Code Examples

### Wire codec call-site order (matches documented envelope field order)
```python
# Illustrative — matches external_hardware_wire.py's WIRE_KINDS field order for byte parity.
def encode_sig(source_id_unused, ts_src, seq, sig, v):
    # kwarg order below is load-bearing: ts_src, seq, sig, v
    return encode("SIG", ts_src=ts_src, seq=seq, sig=sig, v=v)
```

### Golden-frame corpus shape (SDK-02)
```python
# tests/golden_frames.py — frozen, checked into git. One entry per wire kind, generated ONCE
# against the pinned Pi reference (see Open Questions for the path decision) and never
# hand-edited afterward; regenerate only by re-running the generation script against the
# pinned reference file and re-freezing.
GOLDEN_FRAMES = [
    {
        "kind": "SIG",
        "fields": {"ts_src": 1_700_000_000_123, "seq": 12, "sig": "left_paw_x", "v": 0.7},
        "hex": "<frozen hex captured from the pinned reference's encode()>",
    },
    # ... EVT, HB, ACK similarly; CMD included for the decode-only direction
]
```
Two tests consume this corpus:
1. **Frozen-corpus test** (`sdk` alone, no Pi tree needed): `mics_link.wire.encode(kind, **fields)
   == bytes.fromhex(hex)` for every entry — proves the SDK's own encoder hasn't regressed, works
   even if the Pi tree is unavailable.
2. **Live-interop test** (skipped if the pinned Pi path doesn't exist on this machine, exactly
   like `test_extlink_wire.py` already does): load the Pi's real module by path
   (`importlib.util.spec_from_file_location`), call **its** `encode()` with the same fields, and
   assert the result is byte-identical to `mics_link.wire.encode()`'s output right now — this is
   what makes "changing either side without the other fails a test" literally true, not just true
   of the frozen snapshot.

### Replay entry point sketch (SDK-12)
```python
# src/mics_link/replay.py — sketch, not final code
import csv, json, time

def read_rows(path):
    """Yields (t, signal, value) dicts; malformed rows are counted, never raised."""
    opener = _jsonl_rows if path.endswith(".jsonl") else _csv_rows
    yield from opener(path)

def replay(link, rows, mode="realtime", scale=1.0):
    """mode: 'realtime' | 'scaled' | 'fast'. Sleeps between rows unless mode == 'fast'."""
    start_wall = time.monotonic()
    start_t = None
    for row in rows:
        if start_t is None:
            start_t = row["t"]
        if mode != "fast":
            target_offset = (row["t"] - start_t) / (scale if mode == "scaled" else 1.0)
            elapsed = time.monotonic() - start_wall
            if target_offset > elapsed:
                time.sleep(target_offset - elapsed)
        link.send_signal(row["signal"], row["value"])
```
Wired as a console script:
```toml
# pyproject.toml
[project.scripts]
mics-link-replay = "mics_link.replay:main"
```

### Verified packaging shape (empirically tested on this host, 2026-08-26)
```toml
# sdk/pyproject.toml
[build-system]
requires = ["setuptools>=61.0"]
build-backend = "setuptools.build_meta"

[project]
name = "mics-link"
version = "0.1.0"
description = "MICS-Link SDK: push signals/events from any machine into a MICS pilot's FDA"
requires-python = ">=3.8"
dependencies = ["pyzmq", "msgpack"]

[project.scripts]
mics-link-replay = "mics_link.replay:main"

[tool.setuptools.packages.find]
where = ["src"]
```
Verified: `pip install "git+file://<repo>#subdirectory=sdk"` (stand-in for the real `https://`
form) installs cleanly into an isolated venv, `import mics_link` works, and files under a sibling
`other_stuff/` directory in the same repo are never touched or required. Also verified: `python -m
build --wheel` from inside `sdk/` produces `mics_link-0.1.0-py3-none-any.whl` with no additional
configuration — satisfies SDK-13's offline-fallback deliverable directly.

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|-------------------|---------------|--------|
| `tools/extlink_driver/extlink_wire.py` (hand-rolled sender codec, driver-only) | `mics_link.wire` (packaged, parity-tested, reusable by any sender) | This phase (SDK-10) | Eliminates the exact "two hand-written implementations of one envelope" drift Phase 18 already produced once |
| Driver installed via hand-copied `extlink_driver_mac.zip` + sibling `extlink_wire.py` | Driver imports an installed `mics_link` package | This phase | Driver's own docs/zip need the SDK install line added; zip must not reintroduce a second wire copy (deferred decision on retiring the zip itself) |
| No packaging precedent for redistributable Python in this repo (`requirements.txt` only) | First `pyproject.toml`-based, pip-installable package (`sdk/`) | This phase | Deliberate, justified exception to the project's stated "no pyproject.toml" convention — scoped narrowly to code meant to run OUTSIDE this repo's Docker services |

**Deprecated/outdated:** none — this is new territory for the repo, not a migration from an old
API.

## Open Questions

1. **RESOLVED mid-research by explicit user direction (2026-08-26): "we are working on the
   mics_core."** Which path is the canonical golden-corpus reference: `~/pi-mirror/...` or
   `~/mics_core/...`?
   - What we know: both copies were verified byte-identical on 2026-08-26. The existing
     `test_extlink_wire.py` already hardcodes the `pi-mirror` path. The phase's own "Files to
     change" list in ROADMAP.md names the `mics_core` path as the read-only reference. The user
     has now stated directly that `mics_core` is the platform this work targets. Pilot 1
     (`132.77.72.28`), the rig this phase's own checkpoint has historically run the ten-line
     sender against, was last confirmed **on the old stack** as of 2026-08-17 project memory
     ("the working pilot... do not touch"; migration only completed on `.213`) — nine days stale
     relative to this research and to the user's mid-research direction. Phase 35's roadmap
     section separately flags this exact ambiguity as an **open decision to settle before Phase
     35's planning**, written against `mics_core` prospectively — Phase 34 now settles it the
     same way, per the user.
   - What's unclear: whether pilot 1's migration status has changed since 2026-08-17 (i.e.
     whether the phase's own rig checkpoint will actually run against a `mics_core`-based pilot,
     or whether the checkpoint still targets old-stack pilot 1 while the *code* is written against
     `mics_core`). **This must be confirmed before the rig-checkpoint step of the plan is
     finalized** — if pilot 1 is still old-stack, the checkpoint is exercising `pi-mirror`'s
     runtime regardless of which reference the golden corpus is pinned to, and that mismatch
     should be stated in the plan rather than discovered during the checkpoint.
   - Recommendation: **pin the primary/named canonical reference to `~/mics_core/...`** (per user
     direction), and **keep a secondary interop test against `~/pi-mirror/...` that
     skip-if-absent** rather than fails, explicitly asserting the two stay identical for as long as
     both exist — this still catches silent drift between the two trees for free, but now names
     the forward-looking platform as the source of truth. Separately, confirm which actual pilot
     backs this phase's rig checkpoint before finalizing that step. State this as a decision in
     the plan, don't
     inherit the inconsistency.

2. **Does the reconnect-detection mechanism (ZMQ socket monitor) actually survive a real Pi
   restart with the exact `pyzmq==27.1.0`/libzmq present on this dev host?**
   - What we know: the general mechanism (`Socket.monitor()`, `ZMQ_EVENT_*`) is documented and
     standard; known interaction issues with libzmq's own reconnect timer exist in the tracker
     history, but the specific reports describe long-idle (~90s) edge cases on unspecified older
     version combinations.
   - What's unclear: whether this specific pyzmq/libzmq pairing on this dev host and the rig's
     libzmq are affected.
   - Recommendation: build the reconnect state machine fully mockable/testable first (per SDK-11);
     treat the actual monitor-wiring smoke test as an early, explicit implementation task with its
     own pass/fail, not an assumption folded silently into "SDK-07 done."

3. **What exactly should the SDK's default heartbeat interval be?**
   - What we know: the one real fixture observed (`ExtlinkDemo`, pilot config id 21) uses
     `stale_ms: 3000`; the Pi's own liveness poller checks at `stale_ms / 2`. CONTEXT.md locks the
     principle ("safe default, overridable") but leaves the number to discretion.
   - What's unclear: whether 3000ms is representative of typical lab usage going forward, or just
     this one demo fixture.
   - Recommendation: default to **1.0s**, which keeps a source alive under `stale_ms` values as
     low as ~3s even allowing for one dropped/delayed heartbeat (a 1:3 heartbeat:timeout ratio is
     the standard keepalive convention), while remaining cheap enough not to matter at larger
     `stale_ms`. Document in the README that a Pi configured with a smaller `stale_ms` than ~3s
     needs the caller to override the interval explicitly.

## Validation Architecture

### Test Framework
| Property | Value |
|----------|-------|
| Framework | pytest (already the project standard; `sdk/` gets its own self-contained test run, independent of `docker compose exec api pytest`) |
| Config file | none yet — Wave 0 creates `sdk/pytest.ini` or relies on `pyproject.toml`'s `[tool.pytest.ini_options]` |
| Quick run command | `cd sdk && python3 -m pytest -q` |
| Full suite command | `cd sdk && python3 -m pytest -q` (no split needed — the whole suite is socketless and fast; the rig checkpoint is a separate, non-pytest, USER-RUN activity) |

### Phase Requirements -> Test Map

**Agent-testable offline (dev host, no rig, no socket):**

| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|--------------------|--------------|
| SDK-01 | Package installs, imports, only 2 deps | packaging smoke | `pip install "git+file://$(pwd)#subdirectory=sdk" --target /tmp/x && python3 -c "import mics_link"` (or an equivalent CI-style build+install check) | ❌ Wave 0 |
| SDK-02 | Wire parity, frozen + live interop | unit | `python3 -m pytest -q sdk/tests/test_wire_parity.py` | ❌ Wave 0 |
| SDK-03 | Identity fixed at construction, no mutator; `socket_plan`-style config -> ROUTER-bind-only shape rejected otherwise | unit | `python3 -m pytest -q sdk/tests/test_transport_config.py` | ❌ Wave 0 |
| SDK-04 | dtype rejection at call site incl. bool-vs-int trap | unit | `python3 -m pytest -q sdk/tests/test_dtype_validation.py` | ❌ Wave 0 |
| SDK-05 | Heartbeat scheduling (pure "is it due" function against injected clock) | unit | `python3 -m pytest -q sdk/tests/test_heartbeat_scheduling.py` | ❌ Wave 0 |
| SDK-06 | Bounded queue, drop-NEWEST, counter increments, callback fires | unit | `python3 -m pytest -q sdk/tests/test_sender_bounded_drop.py` | ❌ Wave 0 |
| SDK-07 | Reconnect state machine transitions correctly on synthetic monitor events; no exception escapes | unit | `python3 -m pytest -q sdk/tests/test_reconnect_state_machine.py` | ❌ Wave 0 |
| SDK-08 | Synthetic CMD frame -> dispatched off hot path -> correct ACK bytes; raising handler -> error ACK, no crash | unit | `python3 -m pytest -q sdk/tests/test_command_dispatch.py` | ❌ Wave 0 |
| SDK-09 | Context manager enter/exit calls close(); close() drains-or-abandons per stated rule | unit | `python3 -m pytest -q sdk/tests/test_lifecycle.py` | ❌ Wave 0 |
| SDK-10 | `extlink_wire.py` deleted; `extlink_driver.py` imports SDK; existing driver tests still pass unchanged | unit + hygiene (AST import check reused from `test_extlink_wire.py`) | `python3 -m pytest -q tools/extlink_driver/` | ✅ existing tests to retarget |
| SDK-11 | Whole suite runs with `zmq` uninstalled/unavailable except transport-glue-specific tests | hygiene | AST-based "no zmq at module scope outside transport.py" test, reusing `test_wire_module_never_imports_zmq`'s pattern | ❌ Wave 0 (adapt existing pattern) |
| SDK-12 | Replay: CSV + JSONL, three timing modes, malformed row counted not fatal | unit | `python3 -m pytest -q sdk/tests/test_replay.py` | ❌ Wave 0 |
| SDK-13 | README completeness (manual read-through, not automatable) | manual review | N/A — checklist item in the plan's own review pass | N/A |

**USER-RUN rig checkpoints (agent supplies commands, user runs and reports):**

| Req ID | Behavior | What the user runs | What they report |
|--------|----------|----------------------|--------------------|
| Precondition | `ExtlinkDemo` fixture's standing egress-probe dependency | Confirm/restart the TCP echo listener (`scratchpad/egress_listener.py`, confirmed live during this research: `python3 egress_listener.py`, PID bound to `0.0.0.0:5597` — a standalone throwaway script, **not** the orchestrator, which listens on port 5560/`MSGPORT` instead) on `132.77.73.125:5597` **before** anything else in this checklist | Listener is up; `demo.alive` does not flip false ~3s into the run |
| Precondition | Confirm which platform actually backs the rig checkpoint | Verify pilot 1 (`132.77.72.28`)'s current migration status before running the ten-line-sender checkpoint — project memory's "untouched" status is dated 2026-08-17 and may be stale now that the user has confirmed work targets `mics_core` | Either pilot 1 is confirmed still old-stack (checkpoint exercises `pi-mirror`'s runtime) or it has migrated (checkpoint exercises `mics_core`'s runtime) — state which, don't assume |
| SDK-01 (real install) | Install on a genuinely separate machine | `pip install "git+https://github.com/idopo/Mics-backend.git#subdirectory=sdk"` on a non-dev-host machine (or a fresh venv standing in for one), then `python3 -c "import mics_link"` | Install succeeds with only `pyzmq`+`msgpack` pulled in; import works |
| SDK-03/04/06/07 (integration, real socket) + phase success criterion 3 | Ten-line sender drives a real FDA transition | Agent supplies a ten-line script targeting pilot 1 (`--pi-host 132.77.72.28`, port 5599, `source_id: demo`, using the existing `extlink_demo` task def 434 with its two hand-authored transitions per `tools/extlink_driver/README.md`) | State changes visible in ES for `wait->armed->fired->wait` |
| SDK-06 (soak / overflow) + phase success criterion 12 | Sustained send at the arc's real target rate, bounded queue drop under saturation | Agent supplies a rate/duration invocation (mirroring `extlink_driver.py --rate`) | Pilot stays up, FDA keeps transitioning, drop counter reported, ES ingestion keeps up |
| SDK-05 | Heartbeat keeps `demo.alive` true through a quiet period exceeding `stale_ms` | User runs the sender, sends nothing for >3x the fixture's `stale_ms` (3000ms), watches `demo.alive` | `demo.alive` stays true throughout; individual signals go stale under their own policy |
| SDK-07 (reconnect) | Pi restart mid-session | User restarts the pilot process (their own action, never the agent's) while the sender keeps running | Sender logs a disconnect then reconnect via `on_state_change`; sending resumes with no restart of the sender process; `seq` in ES-visible frames keeps climbing rather than resetting to 0 |
| **NOT rig-testable this phase** | SDK-08 end-to-end CMD/ACK from a live Pi-initiated command | N/A — no Pi-side sender of `CMD` exists anywhere in this codebase today | Document explicitly in the phase's own validation log: SDK-08 is proven only by synthetic-frame unit tests |

### Sampling Rate
- **Per task commit:** `cd sdk && python3 -m pytest -q` (whole suite — it's small and fully
  offline, no reason to subset)
- **Per wave merge:** same command, plus the driver's retargeted tests: `python3 -m pytest -q
  tools/extlink_driver/`
- **Phase gate:** full offline suite green, THEN the USER-RUN rig checklist above, before
  `/gsd:verify-work`

### Wave 0 Gaps
- [ ] `sdk/pyproject.toml`, `sdk/src/mics_link/` skeleton, `sdk/tests/` — none of this exists yet;
      the whole package is Wave 0's first deliverable.
- [ ] `sdk/tests/golden_frames.py` — frozen corpus generation script + frozen values, run once
      against the pinned `~/pi-mirror/.../external_hardware_wire.py`.
- [ ] `sdk/tests/fake_transport.py` — the in-memory seam substitute every non-codec test depends on.
- [ ] Decide and document the canonical golden-corpus path (Open Question 1 — RESOLVED to `mics_core`
      per user direction 2026-08-26, `pi-mirror` kept as secondary skip-if-absent) before writing
      `test_wire_parity.py`, not after.
- [ ] Confirm the standing `132.77.73.125:5597` TCP echo listener dependency before any rig
      checkpoint step — it will silently sabotage `demo.alive` observations otherwise (see
      `18-HARDWARE-VALIDATION.md` §0d).
- [ ] Framework install: `python3 -m pip install pyzmq msgpack pytest build` in whatever
      environment runs `sdk/`'s tests (separate from the Docker `api` test environment).

## Sources

### Primary (HIGH confidence — empirically verified on this host during this research pass)
- `/home/ido/mics_core/autopilot/autopilot/hardware/external_hardware_wire.py` — read in full;
  frozen wire spec, codec functions, dtype/role/liveness helpers
- `/home/ido/mics_core/autopilot/autopilot/hardware/external_hardware_runtime.py` — read in full;
  `EgressWorker`, `LifecycleRunner`, `LivenessPoller`, `ready_gate_decision`, `bind_steps`
- `diff` of `~/mics_core/.../external_hardware_wire.py` vs `~/pi-mirror/.../external_hardware_wire.py`
  — confirmed byte-identical (`[ok] Files are identical`), re-verified 2026-08-26
- Direct execution on this host: `msgpack.packb()` with identical input dict produced **identical
  hex bytes** under `msgpack==1.0.5` (isolated venv) and `msgpack==1.2.1` (system) —
  `85a16ba3534947a674735f7372637ba373657101a3736967a178a176cb3fe6666666666666` both times
- Direct execution on this host: end-to-end `pip install "git+file://.../repo#subdirectory=sdk"`
  against a throwaway git repo with a sibling `other_stuff/` directory — installed cleanly,
  imported correctly, did not require or touch the sibling directory
- Direct execution on this host: `python -m build --wheel` from the same throwaway `sdk/`
  directory produced a working `.whl`
- `grep -rln "\"CMD\"\|cmd_id" ~/mics_core/autopilot/ ~/pi-mirror/autopilot/` — confirmed CMD/ACK
  sending is implemented NOWHERE outside the wire codec module itself
- `tools/extlink_driver/extlink_wire.py`, `extlink_driver.py`, `test_extlink_wire.py`, `README.md`
  — all read in full
- `.planning/phases/18-extlink-pi-transport/18-HARDWARE-VALIDATION.md` — read for the standing
  `132.77.73.125:5597` egress-listener dependency and the confirmed pilot-1/old-stack fact
  (`132.77.72.28`, "the working pilot... do not touch")
- `.planning/phases/34-mics-link-sdk-client-package/34-CONTEXT.md`, `.planning/REQUIREMENTS.md`
  (SDK-01..13), `.planning/ROADMAP.md` (Phase 34/35 sections) — read in full

### Secondary (MEDIUM confidence)
- ZMQ socket-monitor mechanics and `ZMQ_EVENT_*` constants — cross-referenced libzmq/pyzmq
  official docs and man pages via WebSearch, not exercised live against this specific rig's libzmq
- Known libzmq/pyzmq issues where a monitor socket interferes with automatic reconnection
  (zeromq/libzmq#3745, zeromq/pyzmq#1340) — read via WebSearch summaries of the issue trackers,
  not independently reproduced here
- Packaging best-practice guidance (src-layout, setuptools vs hatchling tradeoffs) — WebSearch,
  cross-checked against the empirical POC above which used setuptools successfully

### Tertiary (LOW confidence)
- General "pip install git subdirectory" pitfall summaries from WebSearch aggregator articles —
  superseded by this research's own working empirical reproduction above; kept only as background
  context on private-repo/auth edge cases (not applicable here since the repo is public)

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH — pyzmq/msgpack are the pre-existing, already-mandated dependencies;
  packaging shape empirically proven end-to-end on this host
- Architecture: HIGH — every major seam mirrors an already-built, already-reviewed Pi-side
  equivalent (`external_hardware_wire.py`/`external_hardware_runtime.py`); the one genuinely new
  piece (ZMQ socket monitor for reconnect events) is MEDIUM, clearly flagged
- Pitfalls: HIGH for the wire-parity/bool-coercion/identity-invisibility pitfalls (all directly
  observed in this codebase's existing code and its own Phase 18 validation log); MEDIUM for the
  ZMQ-monitor-vs-reconnect interaction (issue-tracker sourced, not reproduced live)

**Research date:** 2026-08-26
**Valid until:** 30 days for the packaging/wire-parity findings (stable, protocol-level facts,
empirically reproduced); re-verify the ZMQ-monitor reconnect behavior against whatever `pyzmq`
version is actually pinned in `sdk/pyproject.toml` at implementation time, since that risk is
version-sensitive.
