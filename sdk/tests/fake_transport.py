"""In-memory `Transport` substitute (Phase 34, Plan 02, Task 2) — every non-codec test in
this phase depends on this so it can run with zero sockets, zero network, zero Pi (SDK-11).
"""


class FakeSocket:
    """Records every zmq-shaped call a real DEALER socket would receive, in order, so
    `test_transport_config.py` can assert on identity-lock and connect-order behaviour
    without ever touching zmq. Symbolic string tokens ("DEALER", "IDENTITY") stand in for
    the real zmq constants — this class never imports zmq.
    """

    def __init__(self):
        self.calls = []
        self.identity = None
        self.connected_to = None
        self.closed = False
        self.linger = None

    def setsockopt(self, option, value):
        self.calls.append(("setsockopt", option, value))
        if option == "IDENTITY":
            self.identity = value
        elif option == "LINGER":
            self.linger = value

    def connect(self, target):
        self.calls.append(("connect", target))
        self.connected_to = target

    def close(self):
        self.closed = True


def fake_socket_factory(fake_socket):
    """Builds a `socket_factory(context, host, port, source_id)` matching `ZmqTransport`'s
    injectable seam. Records a "socket(DEALER)" call, then setsockopt(IDENTITY, ...), then
    connect(...) onto `fake_socket.calls` — the same order the real default factory
    performs them in, so tests can assert order without a real zmq socket.
    """

    def factory(context, host, port, source_id):
        fake_socket.calls.append(("socket", "DEALER"))
        fake_socket.setsockopt("IDENTITY", source_id.encode("utf-8"))
        fake_socket.connect("tcp://{}:{}".format(host, port))
        return fake_socket

    return factory


class FakeTransport:
    """In-memory implementation of the `Transport` seam — no socket, no network, no Pi.
    `send()` appends to `.sent`; `poll()` drains and returns `.inbound`; `events()` drains
    and returns `.pending_events`; `close()` sets `.closed = True`. `fail_next = True` makes
    the NEXT `send()` raise once (for plan 34-06 to prove no exception escapes the caller).
    """

    def __init__(self, source_id="fake"):
        self._source_id = source_id
        self.sent = []
        self.inbound = []
        self.pending_events = []
        self.closed = False
        self.fail_next = False

    @property
    def source_id(self):
        return self._source_id

    def send(self, frame):
        if self.fail_next:
            self.fail_next = False
            raise RuntimeError("FakeTransport: forced send failure")
        self.sent.append(frame)

    def poll(self, timeout_ms=0):
        frames, self.inbound = self.inbound, []
        return frames

    def events(self):
        events, self.pending_events = self.pending_events, []
        return events

    def close(self):
        self.closed = True
