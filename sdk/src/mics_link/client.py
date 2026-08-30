"""`MicsLink` — the public client (Phase 34, Plan 06). One IO thread wires together
`transport` + `sender` + `heartbeat` + `reconnect` + `commands`, behind a context manager
and an explicit `close()`.

Does not import a socket library, at module scope or nested — the transport is injected;
`connect()` (`mics_link/__init__.py`) is the only place a real transport is constructed.
This module stays importable with no socket library installed (SDK-11), matching the rest
of the package.

**Exactly ONE thread ever touches the transport: the IO thread** (decision 1). ZMQ sockets
are not thread-safe. The caller's thread (and the command worker) only ever call
`BoundedSender.enqueue`, which is a `queue.Queue` operation and IS thread-safe. If a future
reader is tempted to send directly from `send_signal` "just for the ACK path", this comment
is why they must not — the command worker's `ack_sink` is also `sender.enqueue`.

**`send_signal`/`send_event` are thread-safe, non-blocking, perform no I/O, hold no lock
across a network call, and are safe to call before a connection exists and while
disconnected** (SDK-15): they are called from a foreign library's callback thread at frame
rate (e.g. a vendor inference SDK's per-frame callback, invoked synchronously on that
library's own worker thread once per frame). The only shared mutable state on that call
path — the `SeqCounter` and `BoundedSender`'s stats — is protected by small locks for
exactly this reason.

**No exception ever escapes the IO thread, absolute** (decision 3). `send_signal`/
`send_event` may raise `InvalidValueError` — that is the ONE deliberate exception, SDK-04's
call-site contract, and a programmer error the researcher fixes once, not a runtime
condition. Everything else — transport failures, monitor hiccups, callback exceptions,
handler exceptions, encode failures — is caught, logged (rate-limited) and the current IO
loop iteration is abandoned; the next iteration runs normally.

`on_state_change(True)` does NOT mean the Pi is accepting your identity — only that the
DEALER's TCP-level connection to the Pi's ROUTER is up. ROUTER-level identity acceptance is
a separate layer this SDK cannot observe from the sender side (EXTLINK-02: the Pi drops a
mismatched identity with no NAK).
"""
import logging
import threading
import time

from . import wire
from .commands import CommandRegistry, CommandWorker
from .heartbeat import DEFAULT_HEARTBEAT_S, HeartbeatSchedule
from .reconnect import ConnectionState
from .sender import BoundedSender, should_log_drop
from .values import validate_payload, validate_value

_logger = logging.getLogger("mics_link")

# Bounds inbound and heartbeat from starving under a saturating producer (decision 2b).
_MAX_FRAMES_PER_IO_ITERATION = 64

# Rate limit for the "IO loop iteration failed" warning — mirrors sender.py's own
# rate-limited drop log so a runaway transport cannot flood the researcher's own logger.
_IO_ERROR_LOG_INTERVAL_S = 5.0


class MicsLink:
    """One IO thread that owns the transport, drains the bounded send queue, emits
    heartbeats, translates monitor events into `on_state_change` edges, and hands inbound
    CMDs to the command worker.

    `send_signal`/`send_event` enqueue only — they never touch the transport directly (see
    module docstring, decision 1). `_io_once()` is one loop iteration, exposed as a
    package-private method so tests can drive it deterministically with no real thread and
    no sleeping; `_io_loop()` just calls it in a `while not stopped` loop on the IO thread.
    """

    def __init__(
        self,
        transport,
        *,
        heartbeat_s=DEFAULT_HEARTBEAT_S,
        queue_size=256,
        on_drop=None,
        on_state_change=None,
        log=True,
        logger=None,
        drain_timeout_s=2.0,
        poll_ms=50,
        clock=time.monotonic,
        thread_factory=threading.Thread,
        autostart=True,
    ):
        self._transport = transport
        self._logger = logger if logger is not None else _logger
        self._clock = clock
        self._poll_ms = poll_ms
        self._drain_timeout_s = drain_timeout_s
        self._thread_factory = thread_factory

        self._seq = wire.SeqCounter()
        self._seq_lock = threading.Lock()
        self._sender = BoundedSender(
            maxsize=queue_size, on_drop=on_drop, log=log, logger=self._logger, clock=clock
        )
        self._heartbeat = HeartbeatSchedule(interval_s=heartbeat_s, clock=clock)
        self._connection = ConnectionState(on_state_change=on_state_change, logger=self._logger)
        self._registry = CommandRegistry()
        self._commands = CommandWorker(
            self._registry, self._sender.enqueue, thread_factory=thread_factory,
            logger=self._logger,
        )

        self.ignored_inbound = 0
        self._accepting = True
        self._last_io_error_log_at = None

        self._stop = threading.Event()
        self._thread = None
        self._closed = False
        self._close_lock = threading.Lock()

        self._commands.start()
        if autostart:
            self._start_io_thread()

    # --- public send/receive surface ---

    def send_signal(self, name, value):
        """Enqueue a SIG frame. Returns `True` if accepted onto the send queue, `False` if
        dropped (queue full, or the client is closed). Raises `InvalidValueError` — the one
        deliberate exception — if `value`'s exact type is not one of the four allowed
        dtypes. Thread-safe; safe to call before a connection exists and while disconnected.
        """
        value = validate_value(name, value)
        if not self._accepting:
            self._sender.record_external_drop()
            return False
        with self._seq_lock:
            seq = self._seq.next()
        frame = wire.sig_frame(name, value, seq)
        return self._sender.enqueue(frame)

    def send_event(self, name, payload):
        """Enqueue an EVT frame. Same accept/drop/raise contract as `send_signal`."""
        payload = validate_payload(name, payload)
        if not self._accepting:
            self._sender.record_external_drop()
            return False
        with self._seq_lock:
            seq = self._seq.next()
        frame = wire.evt_frame(name, payload, seq)
        return self._sender.enqueue(frame)

    def command(self, name):
        """``@link.command("stop")`` registers the decorated function as the handler for an
        inbound CMD named ``"stop"`` and returns it UNCHANGED."""
        return self._registry.decorator(name)

    # --- properties ---

    @property
    def stats(self):
        return self._sender.stats

    @property
    def connected(self):
        return self._connection.connected

    @property
    def source_id(self):
        return self._transport.source_id

    # --- IO thread ---

    def _start_io_thread(self):
        self._thread = self._thread_factory(target=self._io_loop, name="MicsLinkIO")
        self._thread.daemon = True
        self._thread.start()

    def _io_loop(self):
        while not self._stop.is_set():
            self._io_once()

    def _io_once(self):
        """One iteration of decision 2's loop, wrapped in the try/except of decision 3 —
        exposed package-private so tests can drive it deterministically with no thread and
        no sleeping.
        """
        try:
            self._process_events()
            self._drain_send_queue()
            self._process_inbound()
            self._maybe_heartbeat()
        except Exception:
            self._log_io_error()

    def _process_events(self):
        self._connection.apply_all(self._transport.events())

    def _drain_send_queue(self):
        for _ in range(_MAX_FRAMES_PER_IO_ITERATION):
            frame = self._sender.pop(timeout=0)
            if frame is None:
                return
            self._send_frame(frame)

    def _process_inbound(self):
        for raw in self._transport.poll(self._poll_ms):
            cmd = wire.decode_cmd(raw)
            if cmd is None:
                self.ignored_inbound += 1
                continue
            self._commands.submit(cmd)

    def _maybe_heartbeat(self):
        if self._heartbeat.due(self._clock()):
            with self._seq_lock:
                seq = self._seq.next()
            self._send_frame(wire.hb_frame(seq))

    def _send_frame(self, frame):
        """`frame` has already left the bounded queue (34-review CR-01): if
        `transport.send()` raises, the frame is not silently gone — it is counted in
        `stats.send_failed` before the exception is re-raised for `_io_once()`'s existing
        handler to log (rate-limited) and move on to the next iteration.
        """
        try:
            self._transport.send(frame)
        except Exception:
            self._sender.record_send_failure()
            raise
        self._sender.stats.sent += 1
        self._heartbeat.note_sent(self._clock())

    def _log_io_error(self):
        now = self._clock()
        if should_log_drop(self._last_io_error_log_at, now, _IO_ERROR_LOG_INTERVAL_S):
            self._last_io_error_log_at = now
            self._logger.warning("mics_link: IO loop iteration failed", exc_info=True)

    # --- lifecycle ---

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()
        return False

    def close(self):
        """close() stops accepting new sends, gives the IO thread up to `drain_timeout_s`
        (default 2.0s) to flush the queue, then ABANDONS whatever remains and records the
        count in `stats.abandoned`, stops the command worker, and closes the transport
        (LINGER=0). close() is idempotent, is safe to call from any thread, and never raises.
        After close(), send_signal returns False and increments stats.dropped rather than
        raising — a researcher's loop that outlives the `with` block must not crash.
        """
        with self._close_lock:
            if self._closed:
                return
            self._closed = True
        self._accepting = False

        if self._thread is not None:
            deadline = self._clock() + self._drain_timeout_s
            while self._sender.pending() > 0 and self._clock() < deadline:
                time.sleep(0.01)
        self._stop.set()
        if self._thread is not None:
            self._thread.join(timeout=self._drain_timeout_s)

        abandoned = 0
        while True:
            frame = self._sender.pop(timeout=0)
            if frame is None:
                break
            abandoned += 1
        if abandoned:
            self._sender.stats.abandoned += abandoned

        self._commands.stop(timeout=self._drain_timeout_s)

        try:
            self._transport.close()
        except Exception:
            self._logger.warning("mics_link: transport.close raised", exc_info=True)
