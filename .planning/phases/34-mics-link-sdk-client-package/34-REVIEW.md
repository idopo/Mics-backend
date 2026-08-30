---
phase: 34-mics-link-sdk-client-package
reviewed: 2026-08-30T00:00:00Z
depth: standard
files_reviewed: 37
files_reviewed_list:
  - sdk/src/mics_link/__init__.py
  - sdk/src/mics_link/client.py
  - sdk/src/mics_link/commands.py
  - sdk/src/mics_link/errors.py
  - sdk/src/mics_link/heartbeat.py
  - sdk/src/mics_link/reconnect.py
  - sdk/src/mics_link/replay.py
  - sdk/src/mics_link/replay_io.py
  - sdk/src/mics_link/selfcheck.py
  - sdk/src/mics_link/sender.py
  - sdk/src/mics_link/timing.py
  - sdk/src/mics_link/transport.py
  - sdk/src/mics_link/values.py
  - sdk/src/mics_link/wire.py
  - sdk/pyproject.toml
  - sdk/examples/ten_line_sender.py
  - sdk/examples/callback_sender.py
  - sdk/tests/conftest.py
  - sdk/tests/fake_transport.py
  - sdk/tests/pi_reference.py
  - sdk/tests/golden_frames.py
  - sdk/tests/generate_golden.py
  - sdk/tests/test_client_integration.py
  - sdk/tests/test_lifecycle.py
  - sdk/tests/test_sender_bounded_drop.py
  - sdk/tests/test_transport_config.py
  - sdk/tests/test_wire_parity.py
  - sdk/tests/test_import_hygiene.py
  - sdk/tests/test_replay.py
  - sdk/tests/test_command_dispatch.py
  - sdk/tests/test_public_api.py
  - sdk/tests/test_dtype_validation.py
  - sdk/tests/test_heartbeat_scheduling.py
  - sdk/tests/test_reconnect_state_machine.py
  - sdk/tests/test_selfcheck.py
  - sdk/tests/test_timing.py
  - sdk/tests/test_readme_contract.py
  - sdk/tests/test_zmq_loopback.py
findings:
  critical: 2
  warning: 3
  info: 2
  total: 7
status: issues_found
---

# Phase 34: Code Review Report

**Reviewed:** 2026-08-30
**Depth:** standard
**Files Reviewed:** 37
**Status:** issues_found

## Summary

The package is well-organized, stays inside the 300-line file cap on every module, has
no module-scope `zmq` import outside `transport.py`, and the wire-parity/dtype-validation/
replay test suites are unusually rigorous (byte-level golden-frame assertions, live
Pi-encoder interop, numpy-subclass traps explicitly pinned). All 274 offline tests pass.

Two BLOCKER-level defects were found, both in `client.py`'s IO thread / `close()` path —
exactly the area the phase's own priorities flagged as highest-risk. The first is a
genuine, deterministically-reproducible silent data-loss bug: when `transport.send()`
raises for any reason, the already-dequeued frame is discarded with **no** counter
incremented anywhere (`stats.sent`, `stats.dropped`, and `stats.abandoned` all stay at
their pre-failure values) — this is the exact "researcher's data quietly not arriving"
failure mode CONTEXT.md calls the SDK's worst case, and it directly violates the
stats invariant the test suite itself asserts elsewhere
(`enqueued == sent + dropped + abandoned + pending`). The second is a shutdown-ordering
race: `close()` closes the transport unconditionally after `thread.join(timeout=...)`,
without checking whether the IO thread actually stopped — if it hasn't (a stalled
`transport.send()`/`poll()` past `drain_timeout_s`), the transport is torn down while
still in use on another thread, which is unsafe for a real (non-fake) ZMQ socket.

Three WARNING-level issues and two INFO-level ones round out the report — see below.

## Critical Issues

### CR-01: `transport.send()` failure silently discards a frame with zero accounting

**File:** `sdk/src/mics_link/client.py:191-196` (`_drain_send_queue`), `sdk/src/mics_link/client.py:212-215` (`_send_frame`)

**Issue:** `_drain_send_queue` pops a frame off `BoundedSender`'s queue (removing it) and
then calls `_send_frame(frame)`, which calls `self._transport.send(frame)` with no
`try/except` of its own. If `transport.send()` raises — a real possibility for
`ZmqTransport` (e.g. `zmq.ZMQError` from a torn-down context, a closed socket, or any
other send-time failure) — the exception propagates out of `_drain_send_queue` and is
caught only by `_io_once()`'s outer `try/except Exception: self._log_io_error()`. By the
time that happens, the frame is already gone from the queue (it was `pop()`-ed before the
failing `send()` call) and `self._sender.stats.sent += 1` (the next line in `_send_frame`)
never executes. The frame is not counted as `sent`, not counted as `dropped`, not counted
as `abandoned` — it simply vanishes.

Verified with a standalone repro against the shipped code:
```
before:            {'enqueued': 1, 'sent': 0, 'dropped': 0, 'abandoned': 0}
after send raises:  transport.sent == []   (nothing reached the wire)
after send raises: {'enqueued': 1, 'sent': 0, 'dropped': 0, 'abandoned': 0}   pending: 0
```
`enqueued (1) != sent + dropped + abandoned + pending (0)` — the exact invariant
`tests/test_lifecycle.py::test_stats_snapshot_after_a_full_session_is_internally_consistent`
asserts elsewhere in the suite is silently violated by this path, and no test in the suite
catches it: `tests/test_client_integration.py::test_transport_send_failure_does_not_raise_and_next_send_succeeds`
(lines 77-88) proves only that `_io_once()` doesn't raise and that `transport.sent == []`
— its own comment says *"swallowed — frame lost, no retry"* but the test never asserts
`link.stats.dropped` or any other counter changed, so the silent loss shipped un-caught by
the phase's own test suite.

This is precisely the failure mode CONTEXT.md and the review brief call out as the worst
case for this SDK: a researcher's signal is gone with no visible symptom (no exception,
no log line naming a drop — only a generic rate-limited "IO loop iteration failed"
warning that never says a frame was lost or which one).

**Fix:** Wrap the transport call in `_send_frame` and treat a send failure as a drop,
not a swallowed exception:
```python
def _send_frame(self, frame):
    try:
        self._transport.send(frame)
    except Exception:
        self._sender.stats.dropped += 1  # or a dedicated send_failed counter
        raise  # let _io_once()'s existing handler log it, loop continues next iteration
    self._sender.stats.sent += 1
    self._heartbeat.note_sent(self._clock())
```
(Increment under `BoundedSender`'s existing `_stats_lock` via a small helper method rather
than poking `stats.dropped` directly from `client.py`, to keep the counter's only writer
inside `sender.py` as the module's own docstring promises.)

### CR-02: `close()` can tear down the transport while the IO thread is still using it

**File:** `sdk/src/mics_link/client.py:246-252`, `sdk/src/mics_link/client.py:265-268`

**Issue:** `close()`'s shutdown sequence is:
```python
self._stop.set()
if self._thread is not None:
    self._thread.join(timeout=self._drain_timeout_s)   # (1) may time out
...
self._transport.close()                                 # (2) runs unconditionally
```
`Thread.join(timeout=...)` returning does **not** mean the thread has stopped — it only
means the timeout elapsed or the thread finished, and the code never checks
`self._thread.is_alive()` afterward. `tests/test_lifecycle.py::test_abandon_when_transport_blocks_past_drain_timeout`
(lines 79-104) explicitly exercises exactly this scenario (a `transport.send()` call that
never returns) and confirms `close()` returns in bounded time while frame 0 is "genuinely
in flight" on the still-running IO thread — but the test's `_BlockingTransport.close()` is
inherited unchanged from `FakeTransport` and does nothing but set a flag, so it never
actually interacts with the concurrently-blocked `send()` call. It proves `close()`
returns promptly; it does not prove `close()` is safe to call while the IO thread is
still inside a transport call.

For the real `ZmqTransport` (`sdk/src/mics_link/transport.py:199-224`), `close()` calls
`self._socket.setsockopt(zmq.LINGER, 0)` and `self._socket.close()` (and terminates the
context) with no coordination with the IO thread at all. If the IO thread is still
blocked inside `self._socket.send(frame)` or `poller.poll(...)` at that moment (which can
happen if `transport.send()` itself blocks — see WR-01 — or if `poll_ms`/`drain_timeout_s`
are configured such that the poll doesn't return before the join deadline), one thread is
closing a ZMQ socket while another thread is concurrently calling into it. ZMQ sockets are
documented as not safe for concurrent use from more than one thread; closing a socket
while another thread is mid-call on it is undefined behavior, not merely a slow shutdown.
Under default settings (`poll_ms=50`, `drain_timeout_s=2.0`) this window is narrow, but
nothing in the code prevents a user (or a future default change) from widening it, and
the fake-transport test suite currently cannot catch this class of bug because
`FakeTransport.close()` doesn't model the real unsafety.

**Fix:** After `join()` times out, check `self._thread.is_alive()`. If still alive, do
**not** call `self._transport.close()` from this thread — either skip the transport
close and log a warning ("IO thread did not stop within drain_timeout_s; transport left
open to avoid closing it out from under a running thread"), or have the IO thread itself
own closing the transport once it actually exits (e.g. `_io_loop`'s `finally` block calls
`self._transport.close()`, and `close()` only ever *asks* via `self._stop.set()` +
`join()`, never closes the socket directly from a foreign thread).

## Warnings

### WR-01: `ZmqTransport.send()` has no non-blocking flag or timeout

**File:** `sdk/src/mics_link/transport.py:154-155`

**Issue:** `send(self, frame): self._socket.send(frame)` calls the default (blocking)
`Socket.send()`. Under the shipped default `queue_size=256` this is unlikely to matter in
practice (well below ZMQ's default `SNDHWM` of 1000), but there is no code-level guard
tying `queue_size` to the socket's HWM, and nothing stops a caller from raising
`queue_size` above 1000 (a plausible move for someone doing the SDK-06 soak/overflow
checkpoint at high throughput) or from a slow/partitioned peer eventually filling the
internal ZMQ buffer. If `send()` ever blocks, it blocks the single IO thread that also
owns heartbeats, reconnect-event processing, and CMD dispatch draining — defeating SDK-06's
"sends never block" guarantee at the transport layer, and compounding CR-02 above (a
blocked `send()` is the most likely real-world way the IO thread ends up still alive past
`drain_timeout_s`).

**Fix:** Set an explicit `zmq.SNDTIMEO` (or use `zmq.NOBLOCK` and treat `zmq.Again` as a
drop, same policy as the bounded queue already uses) so a stalled peer can never turn into
an indefinitely blocked IO thread.

### WR-02: Inbound CMD drops (`CommandWorker.dropped`) are never surfaced via `MicsLink.stats`

**File:** `sdk/src/mics_link/commands.py:145-155`, `sdk/src/mics_link/client.py:99-102, 152-154`

**Issue:** `CommandWorker.submit()` increments `self.dropped` when its 32-slot inbox is
full (newest command dropped, per its own docstring), but `MicsLink` never reads
`self._commands.dropped` anywhere — the public `stats` property (`client.py:152-154`)
only returns `self._sender.stats`. A flood of inbound CMD frames that overflows the
command worker's inbox is therefore a silent loss with no counter a researcher can ever
observe, the same class of problem CR-01 fixes for the outbound path. Low real-world
likelihood today (no Pi-side CMD sender exists yet, per the phase's own scope-honesty
note), but the gap is real and will matter the moment SDK-08's Pi-side counterpart ships.

**Fix:** Expose it, e.g. add `commands_dropped` to `SenderStats.snapshot()`'s caller-facing
dict or a second small stats object on `MicsLink`, so `link.stats` (or a sibling property)
reports both outbound and inbound loss.

### WR-03: `mics-link-replay`'s `main()` can raise an uncaught `ValueError`, contradicting its own "never raises" contract

**File:** `sdk/src/mics_link/replay.py:117-124`, `sdk/src/mics_link/replay.py:108-113` (docstring), `sdk/src/mics_link/timing.py:37-38`

**Issue:** `main()`'s docstring states "Returns an int exit code; never raises." The only
validation it performs on `--scale` is gated on `args.mode == "scaled"`:
```python
if args.mode == "scaled" and args.scale <= 0:
    ...
    return 2
```
`Pacer.__init__` (`timing.py:37-38`), however, validates `scale <= 0` unconditionally,
regardless of `mode`. `--mode realtime --scale -1` (or `--mode fast --scale 0`) sails past
`main()`'s guard, reaches `replay(link, rows, mode=args.mode, scale=args.scale, ...)` →
`Pacer(mode=mode, scale=scale, ...)`, and raises `ValueError`, which `main()`'s
`except MicsLinkError` does not catch. Reproduced directly against the shipped CLI:
```
$ mics-link-replay --host h --port 5599 --source-id demo --file <csv> --mode realtime --scale -1
Traceback (most recent call last):
  ...
  File ".../timing.py", line 38, in __init__
    raise ValueError("Pacer: scale must be > 0, got {!r}".format(scale))
ValueError: Pacer: scale must be > 0, got -1.0
```
A researcher running the replay CLI unattended gets a raw traceback instead of the
documented "clear message and nonzero exit" (the exact UX `test_main_rejects_non_positive_scale_with_clear_message_and_nonzero_exit`
proves only for `--mode scaled`). The `with connect(...) as link:` context manager does
still close cleanly on the way out (no resource leak), but the CLI's own contract is
broken for two of its three modes.

**Fix:** Validate `args.scale > 0` unconditionally in `main()` (or catch `ValueError`
alongside `MicsLinkError` around the `replay(...)` call) so every mode gets the same clean
`return 2` + stderr message path.

## Info

### IN-01: Wide-format JSONL parsing doesn't reject EVT-shaped (dict) values the way long-format does

**File:** `sdk/src/mics_link/replay_io.py:204-231`

**Issue:** `_parse_long_json_record` explicitly rejects a record whose `value` is a dict
(`type(value) is dict` → `return None`, counted `rows_malformed`) because a dict-shaped
value is EVT-shaped content, explicitly out of scope per `replay.py`'s decision 8.
`_parse_wide_json_record` has no equivalent check — a wide record like
`{"t": 0, "x": {"nested": true}}` passes through as a `(t, "x", {"nested": true})` tuple.
It doesn't reach the wire (`link.send_signal` → `validate_value` raises `InvalidValueError`,
counted `stats.rejected` by `replay()`), so there's no data-loss risk, but it means the
same conceptual "malformed input" is reported through two different counters
(`rows_malformed` for long, `rejected` for wide) depending on which format the file
happens to be, which is inconsistent and will confuse anyone debugging a replay summary.

**Fix:** Either accept the inconsistency explicitly in a comment (the wide path is
per-column, and a dict value could arguably be a legitimate signal payload attempt rather
than an EVT-shaped ambiguity, since wide format has no `signal`/`value` column names to
collide with) or apply the same dict-rejection check for symmetry.

### IN-02: `CommandWorker.submit()`'s `self.dropped += 1` is an unlocked compound increment

**File:** `sdk/src/mics_link/commands.py:145-155`

**Issue:** `self.dropped += 1` (line 154) is a plain, unsynchronized read-modify-write —
the same class of bug `BoundedSender.enqueue`'s `stats.enqueued`/`stats.dropped` counters
were fixed for during this phase (per the module's own `_stats_lock` and its docstring
explaining why). Under the current shipped wiring, `CommandWorker.submit()` is only ever
called from `MicsLink._process_inbound()` on the single IO thread, so this is not
currently reachable concurrently and is not a live bug today. It is, however, a latent
landmine: `submit()` is not marked private, nothing in its docstring states "single-caller
only," and if a future change (or a researcher reading the class as a general-purpose
queue) calls it from more than one thread, the counter can silently lose updates exactly
like the pre-fix `BoundedSender` did.

**Fix:** Either add a small lock around the increment (cheap, and matches the pattern
already established in `sender.py`) or document `submit()` as single-caller-only in its
docstring so the invariant is explicit rather than accidental.

---

_Reviewed: 2026-08-30_
_Reviewer: Claude (gsd-code-reviewer)_
_Depth: standard_
