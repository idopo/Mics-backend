"""`MicsLink` IO thread driven over `FakeTransport` (Phase 34, Plan 06, Task 1).

Every test here constructs `MicsLink(FakeTransport(), autostart=False, ...)` and drives one
loop iteration at a time via the package-private `_io_once()` — no test depends on sleeping
or a real background thread. Real-thread lifecycle (context manager, `close()`, daemon-ness)
is Task 2's `test_lifecycle.py`; the one real socket in the whole suite is Task 3's
`test_zmq_loopback.py`.
"""
import threading

from mics_link import wire
from mics_link.client import MicsLink
from mics_link.errors import InvalidValueError
from mics_link.transport import MONITOR_CONNECTED, MONITOR_DISCONNECTED, MONITOR_RETRIED

from fake_transport import FakeTransport


def _decode(raw):
    return wire.decode_envelope(raw)


# --- send_signal / send_event over the fake ---


def test_send_signal_enqueues_and_io_once_delivers_a_sig_frame():
    transport = FakeTransport()
    link = MicsLink(transport, autostart=False)
    assert link.send_signal("left_paw_x", 0.7) is True
    link._io_once()
    assert len(transport.sent) == 1
    decoded = _decode(transport.sent[0])
    assert decoded["k"] == "SIG"
    assert decoded["sig"] == "left_paw_x"
    assert decoded["v"] == 0.7
    assert decoded["seq"] == 0
    assert isinstance(decoded["ts_src"], int)


def test_send_signal_invalid_value_raises_and_enqueues_nothing():
    transport = FakeTransport()
    link = MicsLink(transport, autostart=False)
    try:
        link.send_signal("x", None)
        assert False, "expected InvalidValueError"
    except InvalidValueError:
        pass
    assert link._sender.pending() == 0


def test_send_event_produces_evt_frame_with_payload_intact():
    transport = FakeTransport()
    link = MicsLink(transport, autostart=False)
    assert link.send_event("object_detected", {"object": "paw"}) is True
    link._io_once()
    decoded = _decode(transport.sent[0])
    assert decoded["k"] == "EVT"
    assert decoded["evt"] == "object_detected"
    assert decoded["p"] == {"object": "paw"}


def test_seq_increments_across_mixed_traffic_and_is_never_public():
    transport = FakeTransport()
    link = MicsLink(transport, autostart=False, heartbeat_s=9999.0)
    link.send_signal("a", 1)
    link.send_event("b", {})
    link.send_signal("c", 2)
    link._io_once()
    seqs = [_decode(f)["seq"] for f in transport.sent]
    assert seqs == [0, 1, 2]
    assert not any("seq" in n for n in dir(link) if not n.startswith("_"))


# --- no exception ever escapes the IO thread ---


def test_transport_send_failure_does_not_raise_and_next_send_succeeds():
    transport = FakeTransport()
    link = MicsLink(transport, autostart=False)
    link.send_signal("a", 1)
    transport.fail_next = True
    link._io_once()  # swallowed — frame lost, no retry
    assert transport.sent == []

    # 34-review CR-01: the dequeued-but-unsent frame must be COUNTED, not silently gone.
    # This is the exact scenario the review found un-caught: this test previously proved
    # only that no exception escaped and that transport.sent stayed empty — it never
    # checked a single counter, so the frame's loss went unaccounted-for even though this
    # test passed. `send_failed` is the dedicated counter for "attempted and lost"; it is
    # distinct from `dropped` (never left the queue) and the enqueued==sent+dropped+
    # abandoned+send_failed+pending invariant tests assert elsewhere must hold here too.
    snap = link.stats.snapshot()
    assert snap["enqueued"] == 1
    assert snap["sent"] == 0
    assert snap["dropped"] == 0
    assert snap["abandoned"] == 0
    assert snap["send_failed"] == 1
    pending = link._sender.pending()
    assert pending == 0
    assert snap["enqueued"] == (
        snap["sent"] + snap["dropped"] + snap["abandoned"] + snap["send_failed"] + pending
    )

    link.send_signal("b", 2)
    link._io_once()
    assert len(transport.sent) == 1
    assert _decode(transport.sent[0])["sig"] == "b"
    assert link.stats.snapshot()["sent"] == 1


# --- monitor events -> on_state_change edges ---


def test_monitor_connected_event_fires_on_state_change_true_once():
    calls = []
    transport = FakeTransport()
    link = MicsLink(transport, autostart=False, on_state_change=calls.append)
    transport.pending_events = [MONITOR_CONNECTED]
    link._io_once()
    assert calls == [True]
    transport.pending_events = [MONITOR_CONNECTED]
    link._io_once()
    assert calls == [True]  # no second edge from an identical event


def test_full_pi_restart_sequence_preserves_seq_continuity():
    calls = []
    transport = FakeTransport()
    link = MicsLink(transport, autostart=False, on_state_change=calls.append,
                     heartbeat_s=9999.0)
    link._io_once()  # consumes the mandatory "nothing ever sent yet" initial heartbeat
    transport.sent = []  # start the scenario below from a clean slate

    transport.pending_events = [MONITOR_CONNECTED]
    link._io_once()
    for i in range(3):
        link.send_signal("s", i)
    link._io_once()

    transport.pending_events = [MONITOR_DISCONNECTED]
    link._io_once()
    for i in range(3, 5):
        link.send_signal("s", i)
    link._io_once()

    transport.pending_events = [MONITOR_RETRIED, MONITOR_CONNECTED]
    link._io_once()
    for i in range(5, 8):
        link.send_signal("s", i)
    link._io_once()

    assert calls == [True, False, True]
    seqs = [_decode(f)["seq"] for f in transport.sent]
    assert len(seqs) == 8
    # Strictly increasing, contiguous, and never reset back to a lower value across the
    # disconnect/reconnect edge — this is SDK-07's whole claim in one assertion.
    assert seqs == list(range(seqs[0], seqs[0] + len(seqs)))


# --- heartbeat: due when idle, suppressed by traffic ---


def test_heartbeat_fires_once_per_interval_when_idle():
    clock = {"t": 0.0}
    transport = FakeTransport()
    link = MicsLink(transport, autostart=False, heartbeat_s=1.0, clock=lambda: clock["t"])
    link._io_once()  # first call: nothing sent yet, due() is True on a never-sent client
    assert len(transport.sent) == 1
    assert _decode(transport.sent[0])["k"] == "HB"

    clock["t"] += 0.5
    link._io_once()
    assert len(transport.sent) == 1  # not due yet

    clock["t"] += 0.6
    link._io_once()
    assert len(transport.sent) == 2
    assert _decode(transport.sent[1])["k"] == "HB"


def test_heartbeat_suppressed_by_faster_signal_traffic():
    clock = {"t": 0.0}
    transport = FakeTransport()
    link = MicsLink(transport, autostart=False, heartbeat_s=1.0, clock=lambda: clock["t"])
    for _ in range(20):
        clock["t"] += 0.05
        link.send_signal("x", 1)
        link._io_once()
    kinds = {_decode(f)["k"] for f in transport.sent}
    assert kinds == {"SIG"}  # no HB ever emitted — traffic kept last_send_at fresh


# --- inbound CMD -> handler -> ACK; non-CMD inbound is ignored ---


def test_inbound_cmd_dispatches_to_handler_and_acks():
    transport = FakeTransport()
    link = MicsLink(transport, autostart=False, heartbeat_s=9999.0)
    ran = threading.Event()

    @link.command("stop")
    def _stop(args):
        ran.set()
        return "ok"

    cmd_frame = wire.encode("CMD", cmd_id=7, name="stop", args=None, ts_pi=123)
    transport.inbound = [cmd_frame]
    link._io_once()
    assert ran.wait(timeout=2.0)

    link._io_once()  # ack_sink enqueues; this drains it to the transport
    acks = [f for f in transport.sent if _decode(f)["k"] == "ACK"]
    assert len(acks) == 1
    decoded = _decode(acks[0])
    assert decoded["cmd_id"] == 7
    assert decoded["result"] == {"ok": True, "value": "ok"}


def test_non_cmd_inbound_frame_is_ignored_and_counted():
    transport = FakeTransport()
    link = MicsLink(transport, autostart=False)
    sig_frame = wire.sig_frame("x", 1, seq=0)
    transport.inbound = [sig_frame]
    assert link.ignored_inbound == 0
    link._io_once()
    assert link.ignored_inbound == 1


def test_command_decorator_registers_and_returns_function_unchanged():
    transport = FakeTransport()
    link = MicsLink(transport, autostart=False)

    def handler(args):
        return None

    returned = link.command("stop")(handler)
    assert returned is handler


# --- SDK-15: concurrent, foreign-thread call site ---


def test_concurrent_senders_from_8_threads_produce_no_duplicate_or_out_of_order_seq():
    transport = FakeTransport()
    link = MicsLink(transport, autostart=False, queue_size=4096, heartbeat_s=9999.0)
    errors = []

    def _worker():
        try:
            for i in range(500):
                link.send_signal("x", i)
        except Exception as exc:  # pragma: no cover - assertion below is authoritative
            errors.append(exc)

    threads = [threading.Thread(target=_worker) for _ in range(8)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    assert errors == []
    assert link.stats.enqueued + link.stats.dropped == 4000

    while link._sender.pending() > 0:
        link._io_once()

    seqs = [_decode(f)["seq"] for f in transport.sent]
    assert len(seqs) == len(set(seqs))
    assert seqs == sorted(seqs)


def test_send_signal_before_and_while_disconnected_never_raises():
    transport = FakeTransport()
    link = MicsLink(transport, autostart=False)
    # Never connected (no MONITOR_CONNECTED event has ever fired).
    result = link.send_signal("x", 1)
    assert result in (True, False)

    # Explicitly driven to disconnected.
    transport.pending_events = [MONITOR_DISCONNECTED]
    link._io_once()
    assert link.connected is False
    result = link.send_signal("y", 2)
    assert result in (True, False)
