"""ZMQ DEALER transport seam (Phase 34, Plan 02, Task 2).

The ONE module in `mics_link` that touches the socket library — and even here, that import
happens ONLY inside function bodies, never at module scope (decision 7), so
`mics_link.transport` itself imports cleanly on a machine with no socket library installed
(SDK-11). This is stricter than "outside transport.py" and is what makes plan 34-01's
hygiene guard a whole-package invariant. It mirrors the existing driver's proven pattern
(`tools/extlink_driver/extlink_driver.py:_connect`) so `--help` works before pyzmq is
installed.

`Transport` is a documented, duck-typed base — deliberately NOT `typing.Protocol` (the SDK
targets Python 3.8 and `runtime_checkable` Protocols add nothing here) — so the seam is a
named contract in the source, not folklore. `FakeTransport` (tests/fake_transport.py) and
`ZmqTransport` both satisfy it; plan 34-06's client is built against this seam so every
non-codec test in this phase runs with zero sockets, zero network, zero Pi (SDK-11).

Role is `router_bind` ONLY (decision 6, SDK-03): the Pi binds a ROUTER, this DEALER dials
in. There is no `bind()` and no `sub_connect` support anywhere in this module — identity is
set exactly once, at construction, from `source_id`, and `source_id` has no public setter.
"""
from .errors import MicsLinkError

MONITOR_CONNECTED = "connected"
MONITOR_DISCONNECTED = "disconnected"
MONITOR_RETRIED = "retried"

_MIN_PORT = 1
_MAX_PORT = 65535


def endpoint(host, port):
    """(host, port) -> "tcp://{host}:{port}"."""
    return "tcp://{}:{}".format(host, port)


def validate_target(host, port, source_id):
    """Raise `MicsLinkError` for a bad (host, port, source_id) triple; return `None` when
    valid. Called BEFORE any socket exists — a bad target must never reach a socket
    factory (decision 6).
    """
    if not isinstance(host, str) or host.strip() == "":
        raise MicsLinkError(
            "validate_target: host must be a non-empty str, got {!r}".format(host)
        )
    if isinstance(port, bool) or not isinstance(port, int):
        raise MicsLinkError("validate_target: port must be an int, got {!r}".format(port))
    if not (_MIN_PORT <= port <= _MAX_PORT):
        raise MicsLinkError(
            "validate_target: port must be in 1..65535, got {!r}".format(port)
        )
    if not isinstance(source_id, str) or source_id.strip() == "":
        raise MicsLinkError(
            "validate_target: source_id must be a non-empty str, got {!r}".format(source_id)
        )
    return None


class Transport(object):
    """Documented duck-typed seam every transport (fake or real) must satisfy. Base-class
    bodies raise `NotImplementedError` so the contract is a named object in the source, not
    folklore recovered from reading `ZmqTransport`.
    """

    def send(self, frame):
        raise NotImplementedError

    def poll(self, timeout_ms):
        raise NotImplementedError

    def events(self):
        raise NotImplementedError

    def close(self):
        raise NotImplementedError

    @property
    def source_id(self):
        raise NotImplementedError


def _default_context_factory():
    """A PRIVATE context per `ZmqTransport` (never the process-wide `zmq.Context.instance()`
    singleton) — so `close()` can safely `term()` it without disturbing any other transport
    in the same process."""
    import zmq

    return zmq.Context()


def _default_socket_factory(context, host, port, source_id):
    """Creates a DEALER, sets IDENTITY once from `source_id`, connects — in that order
    (decision 6). `import zmq` happens HERE, inside this function body, never at module
    scope (decision 7).
    """
    import zmq

    socket = context.socket(zmq.DEALER)
    socket.setsockopt(zmq.IDENTITY, source_id.encode("utf-8"))
    socket.connect(endpoint(host, port))
    return socket


def _event_map():
    import zmq

    return {
        zmq.EVENT_CONNECTED: MONITOR_CONNECTED,
        zmq.EVENT_DISCONNECTED: MONITOR_DISCONNECTED,
        zmq.EVENT_CONNECT_RETRIED: MONITOR_RETRIED,
    }


class ZmqTransport(Transport):
    """Real ZMQ DEALER transport. `socket_factory`/`context_factory` are the injectable
    seam plan 34-06 tests against with a fake; production uses the module defaults, both of
    which import zmq lazily (decision 7).
    """

    def __init__(self, host, port, source_id, socket_factory=None, context_factory=None):
        validate_target(host, port, source_id)
        self._source_id = source_id
        self._endpoint = endpoint(host, port)
        context_factory = context_factory or _default_context_factory
        socket_factory = socket_factory or _default_socket_factory
        self._context = context_factory()
        # The socket reference is intentionally underscored-only: no public attribute may
        # re-invite `setsockopt(IDENTITY, ...)` from outside this class.
        self._socket = socket_factory(self._context, host, port, source_id)
        self._monitor = self._attach_monitor()
        self._closed = False

    @property
    def source_id(self):
        return self._source_id

    def _attach_monitor(self):
        """Attaches a socket monitor PAIR socket via `get_monitor_socket()`; returns the
        monitor socket, or `None` if the injected socket has no monitor support (e.g. a
        fake socket in tests) — `events()` then always returns `[]`, never raising. This is
        the ONE medium-confidence mechanism in this phase (34-RESEARCH.md Open Question 2 /
        Pitfall 3): kept trivial and side-effect free here, exercised live only by plan
        34-06's loopback smoke.
        """
        get_monitor = getattr(self._socket, "get_monitor_socket", None)
        if not callable(get_monitor):
            return None
        try:
            import zmq

            return get_monitor(events=zmq.EVENT_ALL)
        except Exception:
            return None

    def send(self, frame):
        """Non-blocking (WR-01): passes `zmq.NOBLOCK` so a stalled peer raises `zmq.Again`
        instead of blocking the IO thread indefinitely — the caller (`client.py`'s
        `_send_frame`, CR-01) treats any exception here, `zmq.Again` included, as a lost
        send to count, not something to retry or block on.
        """
        import zmq

        self._socket.send(frame, zmq.NOBLOCK)

    def poll(self, timeout_ms):
        """Returns a list of inbound frames, `[]` on timeout. Swallows `zmq.Again`."""
        import zmq

        poller = zmq.Poller()
        poller.register(self._socket, zmq.POLLIN)
        frames = []
        ready = dict(poller.poll(timeout=timeout_ms))
        if self._socket in ready:
            while True:
                try:
                    frames.append(self._socket.recv(zmq.NOBLOCK))
                except zmq.Again:
                    break
        return frames

    def events(self):
        """Drains the monitor PAIR socket non-blockingly, mapping libzmq event ids to the
        three MONITOR_* strings. `[]` when nothing pending or no monitor attached.
        Unmapped event ids are ignored. NEVER raises — a monitor hiccup must never take
        down the IO thread.
        """
        if self._monitor is None:
            return []
        try:
            import zmq
            from zmq.utils.monitor import recv_monitor_message

            event_map = _event_map()
        except Exception:
            return []
        results = []
        try:
            while self._monitor.poll(timeout=0, flags=zmq.POLLIN):
                msg = recv_monitor_message(self._monitor)
                mapped = event_map.get(msg.get("event"))
                if mapped is not None:
                    results.append(mapped)
        except Exception:
            pass
        return results

    def close(self):
        """Idempotent. `LINGER=0` so a killed sender leaves no half-open connection against
        the Pi's ROUTER (SDK-09); terminates the private context this instance created.
        """
        if self._closed:
            return
        self._closed = True
        if self._monitor is not None:
            try:
                self._monitor.close()
            except Exception:
                pass
        try:
            import zmq

            self._socket.setsockopt(zmq.LINGER, 0)
        except Exception:
            pass
        try:
            self._socket.close()
        except Exception:
            pass
        try:
            self._context.term()
        except Exception:
            pass
