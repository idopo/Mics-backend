"""The ONE test in the whole suite that opens a real socket (Phase 34, Plan 06, Task 3).

Deselected by default (`addopts = -m "not zmq_loopback"`, plan 34-01). Binds a real
`zmq.ROUTER` on `tcp://127.0.0.1:<ephemeral>` — this dev host's own loopback, never a rig,
never a lab subnet address — and drives a real `mics_link.connect()` DEALER against it. Answers
34-RESEARCH.md Open Question 2 (does the socket monitor actually report connect/disconnect
on this host's pyzmq, given libzmq#3745 / pyzmq#1340?) before plan 34-09 asks a human to
restart a pilot.

Binding a TCP listener may prompt Windows Defender Firewall on first run on a Windows host
— this is part of why the test stays opt-in.
"""
import time

import pytest

zmq = pytest.importorskip("zmq")

import mics_link
from mics_link import wire

pytestmark = pytest.mark.zmq_loopback


def _wait_until(predicate, timeout_s, what):
    deadline = time.monotonic() + timeout_s
    while time.monotonic() < deadline:
        if predicate():
            return
        time.sleep(0.02)
    raise AssertionError("timed out after {}s waiting for: {}".format(timeout_s, what))


def _bind_router(context, port=0):
    router = context.socket(zmq.ROUTER)
    router.setsockopt(zmq.LINGER, 0)
    router.bind("tcp://127.0.0.1:{}".format(port))
    endpoint = router.getsockopt(zmq.LAST_ENDPOINT).decode()
    bound_port = int(endpoint.rsplit(":", 1)[1])
    return router, bound_port


def _drain_sig_frames(router, expected, timeout_s):
    """Drains frames off the router until `expected` SIG-kind frames have been seen,
    returning `(identity, seq)` for each SIG frame only. A single unavoidable HB frame may
    legitimately arrive first — `mics_link.heartbeat`'s own documented contract is that a
    client which has never sent anything is immediately due for one heartbeat, regardless
    of the configured interval — so this filters by kind instead of assuming position 0..N
    are all SIG.
    """
    sig_results = []
    poller = zmq.Poller()
    poller.register(router, zmq.POLLIN)
    deadline = time.monotonic() + timeout_s
    while len(sig_results) < expected and time.monotonic() < deadline:
        ready = dict(poller.poll(timeout=100))
        if router in ready:
            identity, payload = router.recv_multipart()
            envelope = wire.decode_envelope(payload)
            if envelope is not None and envelope["k"] == "SIG":
                sig_results.append((identity, envelope["seq"]))
    if len(sig_results) < expected:
        raise AssertionError(
            "timed out waiting for {} SIG frame(s) at the router, got {}".format(
                expected, len(sig_results)
            )
        )
    return sig_results


def test_zmq_monitor_reports_connect_disconnect_reconnect_over_real_loopback_socket():
    """127.0.0.1 only, ephemeral port only, LINGER=0 everywhere, closed in `finally` —
    never touches any lab subnet or rig address.
    """
    context = zmq.Context()
    router, port = _bind_router(context)
    router2 = None
    link = None
    states = []
    try:
        # heartbeat_s pinned huge: the module's own contract fires ONE heartbeat
        # unconditionally on first send-opportunity regardless of interval (nothing has
        # ever been sent yet), but never again after that on this interval — pinning it
        # this high keeps that to exactly one, instead of one per second while this test's
        # bounded waits poll for the CONNECTED edge over the real network stack.
        link = mics_link.connect(
            "127.0.0.1", port, "demo", on_state_change=states.append, heartbeat_s=9999.0
        )
        _wait_until(lambda: link.connected, timeout_s=5.0, what="initial on_state_change(True)")
        assert states == [True]

        for i in range(3):
            assert link.send_signal("x", i) is True
        received = _drain_sig_frames(router, expected=3, timeout_s=5.0)
        for identity, _seq in received:
            assert identity == b"demo"
        seqs = [seq for _identity, seq in received]
        assert seqs == sorted(seqs)
        assert len(set(seqs)) == 3  # strictly increasing, no duplicates

        router.close()
        _wait_until(
            lambda: link.connected is False, timeout_s=10.0,
            what="on_state_change(False) after the router closed",
        )
        assert states == [True, False]

        router2 = context.socket(zmq.ROUTER)
        router2.setsockopt(zmq.LINGER, 0)
        router2.bind("tcp://127.0.0.1:{}".format(port))
        _wait_until(
            lambda: link.connected is True, timeout_s=10.0,
            what="on_state_change(True) after the router re-bound on the same port",
        )
        assert states == [True, False, True]

        for i in range(3, 6):
            assert link.send_signal("x", i) is True
        received2 = _drain_sig_frames(router2, expected=3, timeout_s=5.0)
        seqs2 = [seq for _identity, seq in received2]
        # Continues from where it left off — no reset back to 0 across the reconnect.
        assert min(seqs2) > max(seqs)
        assert seqs2 == sorted(seqs2)
        assert len(set(seqs2)) == 3
    finally:
        if link is not None:
            link.close()
        try:
            router.close()
        except Exception:
            pass
        if router2 is not None:
            try:
                router2.close()
            except Exception:
                pass
        context.term()
