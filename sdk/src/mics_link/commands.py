"""Decode an inbound CMD, dispatch it off the hot path, reply ACK (Phase 34, Plan 04, SDK-08).

**Scope honesty:** there is ZERO Pi-side implementation of sending `CMD` or receiving `ACK`
anywhere in either autopilot tree — `cmd_id` and `"CMD"` appear nowhere outside
`external_hardware_wire.py` itself. Verified with (kept as plain prose, not a literal
grep pattern, to avoid an invalid escape sequence in this docstring):
    ripgrep for the tokens cmd_id and CMD across ~/mics_core/autopilot/ and
    ~/pi-mirror/autopilot/ — both return zero matches outside external_hardware_wire.py.
There is therefore no live round trip to test this module against, on the rig or
anywhere else — SDK-08 is proven this phase by synthetic frames only (built with the Pi's
own encoder in `tests/test_command_dispatch.py`, never hand-typed). Do not go looking for a
Pi-side CMD sender; it does not exist yet.

Two pieces, kept in one file (see the `<action>` size note in 34-04-PLAN.md for the split
trigger):
  - `CommandRegistry` + `dispatch`: pure apart from calling the handler. Bytes in, bytes out.
  - `CommandWorker`: the isolation mechanism (34-RESEARCH.md Pattern 5) — handlers run on one
    dedicated thread, never the IO thread that owns the socket, never the caller's thread.

This module does not import a socket library (module scope or nested) and does not import
`transport.py` — dispatch takes a decoded CMD dict in and returns ACK bytes out; the socket
is somebody else's problem (plan 34-06).
"""
import queue
import threading

from . import wire
from .selfcheck import MicsLinkError

# Key names used inside the ACK `result` dict (decision 1 in 34-04-PLAN.md):
#   success:          {ACK_OK: True, "value": <handler return>}
#   handler raised:    {ACK_OK: False, ACK_ERROR: "<ExcType>: <message>"}
#   unknown command:   {ACK_OK: False, ACK_ERROR: "unknown command: <name>"}
#   unencodable value: {ACK_OK: False, ACK_ERROR: "unencodable result: <ExcType>: <message>"}
ACK_OK = "ok"
ACK_ERROR = "error"


class CommandRegistry(object):
    """Name -> handler map. Registration is a setup-time concern; duplicate names are a
    programmer error (decision 6), not something to silently overwrite.
    """

    def __init__(self):
        self._handlers = {}

    def register(self, name, handler):
        if name in self._handlers:
            raise MicsLinkError(
                "CommandRegistry.register: {!r} is already registered".format(name)
            )
        self._handlers[name] = handler

    def decorator(self, name):
        """``@registry.decorator("stop")`` registers the function under ``name`` and returns
        it UNCHANGED, so the researcher's own module still has a plain callable ``stop``.
        """

        def _register(fn):
            self.register(name, fn)
            return fn

        return _register

    def get(self, name):
        return self._handlers.get(name)

    def names(self):
        return list(self._handlers)


def _unknown_command_result(name):
    return {ACK_OK: False, ACK_ERROR: "unknown command: {}".format(name)}


def _handler_raised_result(exc):
    return {ACK_OK: False, ACK_ERROR: "{}: {}".format(type(exc).__name__, exc)}


def _unencodable_result(exc):
    return {
        ACK_OK: False,
        ACK_ERROR: "unencodable result: {}: {}".format(type(exc).__name__, exc),
    }


def dispatch(registry, cmd, ts_fn=wire.now_ms):
    """Decoded CMD dict -> ACK frame bytes. PURE apart from calling the handler.

    NEVER raises, with one deliberate exception (decision 2): `KeyboardInterrupt`/
    `SystemExit` are BaseException, not Exception, and are allowed to propagate so a
    researcher's Ctrl-C still works even mid-command. Everything else — unknown command,
    a raising handler, a handler whose return value msgpack cannot pack — is caught and
    turned into a valid error ACK instead. These are three explicit branches (not one broad
    `except`) so a rig log can tell them apart.
    """
    cmd_id = cmd.get("cmd_id")
    name = cmd.get("name")
    handler = registry.get(name)

    if handler is None:
        return wire.ack_frame(cmd_id, _unknown_command_result(name), ts_ms=ts_fn())

    try:
        value = handler(cmd.get("args"))
    except Exception as exc:
        return wire.ack_frame(cmd_id, _handler_raised_result(exc), ts_ms=ts_fn())

    # Encoding is itself inside the recoverable path (decision 3): a handler returning
    # something msgpack cannot pack (a numpy array, a socket, ...) must still produce a
    # valid error ACK here, not an unhandled exception on the worker thread.
    try:
        return wire.ack_frame(cmd_id, {ACK_OK: True, "value": value}, ts_ms=ts_fn())
    except Exception as exc:
        return wire.ack_frame(cmd_id, _unencodable_result(exc), ts_ms=ts_fn())


class CommandWorker(object):
    """One dedicated daemon thread. Handlers run HERE — never on the IO thread that owns the
    socket, never on the caller's `submit()` thread (34-RESEARCH.md Pattern 5, decision 4).

    Loop shape mirrors `EgressWorker._run` in `external_hardware_runtime.py`
    (`queue.get(timeout=0.1)` + a `threading.Event` stop flag) — a known-good shape rather
    than a novel one, same reasoning as SDK-06's `BoundedSender`.

    The inbox is bounded and drops the NEWEST command on overflow (decision 5), same policy
    as `BoundedSender`/`EgressWorker`: a flood of commands must not grow memory without
    bound, and evicting an already-queued item would tear a hole in command ordering.
    """

    def __init__(self, registry, ack_sink, maxsize=32, thread_factory=threading.Thread,
                 logger=None):
        self._registry = registry
        self._ack_sink = ack_sink
        self._logger = logger
        self._queue = queue.Queue(maxsize=maxsize)
        self._thread_factory = thread_factory
        self._thread = None
        self._stop_event = threading.Event()
        self._lock = threading.Lock()
        self._started = False
        self._stopped = False
        self.dropped = 0

    def submit(self, cmd):
        """Never blocks, never raises. Returns False (and increments `dropped`) when the
        inbox is full — the newest command is the one dropped, the queued ones are left
        alone.
        """
        try:
            self._queue.put_nowait(cmd)
            return True
        except queue.Full:
            self.dropped += 1
            return False

    def start(self):
        with self._lock:
            if self._started:
                return
            self._started = True
        self._thread = self._thread_factory(target=self._run, name="CommandWorker")
        self._thread.daemon = True
        self._thread.start()

    def stop(self, timeout=2.0):
        """Idempotent. A worker that was never started has no thread to join."""
        with self._lock:
            if self._stopped:
                return
            self._stopped = True
        self._stop_event.set()
        if self._thread is not None:
            self._thread.join(timeout=timeout)

    def _run(self):
        while True:
            try:
                cmd = self._queue.get(timeout=0.1)
            except queue.Empty:
                if self._stop_event.is_set():
                    return
                continue
            self._handle(cmd)

    def _handle(self, cmd):
        ack_bytes = dispatch(self._registry, cmd)
        # dispatch() itself never raises (KeyboardInterrupt/SystemExit aside — a handler
        # deliberately raising one of those on this dedicated thread is expected to end the
        # thread, not be swallowed). The sink call is wrapped separately: plan 34-06 passes
        # `BoundedSender.enqueue`, which returns False rather than raising, but "no exception
        # ever escapes this worker" must hold even against a future sink that does raise.
        try:
            self._ack_sink(ack_bytes)
        except Exception:
            if self._logger is not None:
                self._logger.exception("CommandWorker: ack_sink raised")
