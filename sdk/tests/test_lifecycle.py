"""`MicsLink` deterministic lifecycle — context manager, close(), drain-or-abandon
(Phase 34, Plan 06, Task 2, SDK-09).
"""
import threading
import time

import pytest

from mics_link.client import MicsLink

from fake_transport import FakeTransport


class _BlockingTransport(FakeTransport):
    """A transport whose `send()` blocks until explicitly released — proves close()
    returns within a bounded time even against a permanently stuck transport call, without
    leaking a thread past the end of the test (the release lets the stuck call finish).

    (34-review CR-02) Also records whether `close()` ever arrives while a `send()` is
    genuinely in flight — the real unsafety `FakeTransport.close()` alone cannot model,
    since it just sets a flag and does not interact with a concurrently-blocked `send()`.
    """

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._release = threading.Event()
        self._send_in_flight = threading.Event()
        self.closed_while_send_in_flight = False

    def send(self, frame):
        self._send_in_flight.set()
        try:
            self._release.wait()
            super().send(frame)
        finally:
            self._send_in_flight.clear()

    def close(self):
        if self._send_in_flight.is_set():
            self.closed_while_send_in_flight = True
        super().close()

    def release(self):
        self._release.set()


def _wait_until(predicate, timeout_s, what="condition"):
    deadline = time.monotonic() + timeout_s
    while time.monotonic() < deadline:
        if predicate():
            return
        time.sleep(0.01)
    raise AssertionError("timed out after {}s waiting for: {}".format(timeout_s, what))


def test_context_manager_closes_transport_and_joins_thread_on_exit():
    transport = FakeTransport()
    with MicsLink(transport) as link:
        assert link.stats is not None  # yielded the client itself
    assert transport.closed is True
    assert link._thread.is_alive() is False


def test_context_manager_closes_even_when_body_raises_and_does_not_swallow_it():
    transport = FakeTransport()
    with pytest.raises(ValueError):
        with MicsLink(transport) as link:
            raise ValueError("boom")
    assert transport.closed is True


def test_close_twice_is_a_noop_and_raises_nothing():
    transport = FakeTransport()
    link = MicsLink(transport)
    link.close()
    link.close()  # must not raise
    assert transport.closed is True


def test_close_on_a_never_started_client_raises_nothing():
    transport = FakeTransport()
    link = MicsLink(transport, autostart=False)
    link.close()  # must not raise
    assert transport.closed is True


def test_drain_flushes_all_queued_frames_before_abandoning_anything():
    transport = FakeTransport()
    # autostart=False + queue all 5 frames BEFORE the IO thread ever runs its first
    # iteration: heartbeat.due() is unconditionally True on a client that has never sent
    # anything (mics_link.heartbeat's own documented contract), so starting the thread
    # before anything is queued would race a mandatory initial HB frame in ahead of these
    # 5 — queuing first makes the first iteration's drain step run before that check.
    link = MicsLink(transport, autostart=False, drain_timeout_s=2.0)
    for i in range(5):
        link.send_signal("x", i)
    link._start_io_thread()
    link.close()
    assert link.stats.sent == 5
    assert link.stats.abandoned == 0


def test_abandon_when_transport_blocks_past_drain_timeout():
    transport = _BlockingTransport()
    # autostart=False + queue all 5 frames before the IO thread's first iteration ever
    # runs: this makes the very first frame it pops (frame 0) the one that gets
    # permanently stuck in transport.send() — deterministically, not racing against
    # mics_link.heartbeat's "never sent yet -> always due" initial heartbeat. Frame 0 is
    # therefore neither sent nor abandoned: it is genuinely in flight, mirroring what a
    # real hung transport does to whatever message it was mid-send on when killed. The
    # other 4 frames never leave the queue and are abandoned.
    link = MicsLink(transport, autostart=False, drain_timeout_s=0.1, queue_size=16)
    for i in range(5):
        link.send_signal("x", i)
    link._start_io_thread()

    start = time.monotonic()
    close_thread = threading.Thread(target=link.close)
    close_thread.start()
    close_thread.join(timeout=5.0)
    elapsed = time.monotonic() - start

    assert close_thread.is_alive() is False
    assert elapsed < 2.0  # bounded — nowhere near drain_timeout_s * 5 frames
    assert link.stats.sent == 0
    assert link.stats.abandoned == 4

    # 34-review CR-02: close() must not tear the transport down while the IO thread is
    # still mid-send() on it. At this point the blocked send() has NOT been released yet,
    # so if close() had closed the transport unconditionally (the pre-fix behavior) it
    # would have done so while _send_in_flight was still set.
    assert transport.closed is False
    assert transport.closed_while_send_in_flight is False

    transport.release()  # let the permanently-stuck send() finish so no thread leaks
    # The IO thread's own loop now runs its finally and closes the transport itself, once
    # it has genuinely stopped touching it — never while send() was still in flight.
    _wait_until(lambda: transport.closed is True, timeout_s=2.0, what="transport to close")
    assert transport.closed_while_send_in_flight is False


def test_send_signal_after_close_returns_false_and_increments_dropped_never_raises():
    transport = FakeTransport()
    link = MicsLink(transport)
    link.close()
    result = link.send_signal("x", 1)
    assert result is False
    assert link.stats.dropped >= 1


def test_close_stops_the_command_worker_so_a_later_submit_never_runs():
    transport = FakeTransport()
    link = MicsLink(transport)
    ran = threading.Event()

    @link.command("stop")
    def _stop(args):
        ran.set()

    link.close()
    link._commands.submit({"cmd_id": 1, "name": "stop", "args": None, "ts_pi": 0})
    assert ran.wait(timeout=0.2) is False


def test_stats_snapshot_after_a_full_session_is_internally_consistent():
    transport = FakeTransport()
    link = MicsLink(transport, autostart=False, queue_size=256)
    for i in range(2):
        link.send_signal("x", i)
    link._io_once()  # sends the 2 queued frames
    for i in range(3):
        link.send_signal("y", i)
    # 3 more frames left pending — never drained before close()
    link.close()

    snap = link.stats.snapshot()
    pending = link._sender.pending()
    assert snap["enqueued"] == snap["sent"] + snap["dropped"] + snap["abandoned"] + pending
    assert snap["sent"] == 2
    assert snap["abandoned"] == 3
    assert snap["dropped"] == 0
    assert pending == 0


def test_close_from_a_second_thread_while_io_thread_running_completes_cleanly():
    transport = FakeTransport()
    link = MicsLink(transport)
    errors = []

    def _closer():
        try:
            link.close()
        except Exception as exc:  # pragma: no cover - assertion below is authoritative
            errors.append(exc)

    t = threading.Thread(target=_closer)
    t.start()
    t.join(timeout=5.0)
    assert t.is_alive() is False
    assert errors == []
    assert transport.closed is True


def test_close_docstring_states_the_drain_or_abandon_rule_verbatim():
    doc = MicsLink.close.__doc__
    assert "stops accepting new sends" in doc
    assert "drain_timeout_s" in doc
    assert "ABANDONS whatever remains" in doc
    assert "stats.abandoned" in doc
    assert "idempotent" in doc
    assert "never raises" in doc


def test_io_thread_is_created_as_a_daemon_thread():
    transport = FakeTransport()
    link = MicsLink(transport)
    assert link._thread.daemon is True
    link.close()
