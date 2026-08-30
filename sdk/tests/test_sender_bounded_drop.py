"""Bounded drop-NEWEST send queue (Phase 34, Plan 02, Task 3).

Proves SDK-06 entirely offline: a saturated queue never blocks the caller, never raises,
drops the NEWEST frame (not the oldest), and makes the loss visible via a readable counter,
a rate-limited log, and an optional callback.
"""
import logging
import time

import pytest

from mics_link.sender import BoundedSender, SenderStats, should_log_drop


# --- BoundedSender: basic bounded/drop-newest behaviour ---


def test_enqueue_returns_true_until_full_then_false():
    sender = BoundedSender(maxsize=3)
    results = [sender.enqueue(b"frame%d" % i) for i in range(4)]
    assert results == [True, True, True, False]
    assert sender.stats.enqueued == 3
    assert sender.stats.dropped == 1


def test_dropped_item_is_the_newest_not_the_oldest():
    sender = BoundedSender(maxsize=3)
    for i in range(1, 5):  # frames 1,2,3,4 — 4 is dropped
        sender.enqueue(b"frame%d" % i)

    assert sender.pop(timeout=0.01) == b"frame1"
    assert sender.pop(timeout=0.01) == b"frame2"
    assert sender.pop(timeout=0.01) == b"frame3"
    # frame4 is gone — nothing left to pop
    assert sender.pop(timeout=0.01) is None


def test_enqueue_never_blocks_on_full_queue():
    sender = BoundedSender(maxsize=2)
    sender.enqueue(b"a")
    sender.enqueue(b"b")
    start = time.monotonic()
    for _ in range(50):
        sender.enqueue(b"overflow")
    elapsed = time.monotonic() - start
    assert elapsed < 1.0  # generous bound; put_nowait never blocks


def test_enqueue_never_raises_on_full_queue():
    sender = BoundedSender(maxsize=1)
    sender.enqueue(b"a")
    # must not raise
    for _ in range(10):
        sender.enqueue(b"overflow")


# --- on_drop callback ---


def test_on_drop_called_with_dropped_frame():
    dropped_frames = []
    sender = BoundedSender(maxsize=1, on_drop=dropped_frames.append)
    sender.enqueue(b"kept")
    sender.enqueue(b"dropped")
    assert dropped_frames == [b"dropped"]


def test_on_drop_exception_does_not_propagate_and_dropped_still_increments():
    def raising_on_drop(frame):
        raise ValueError("boom")

    sender = BoundedSender(maxsize=1, on_drop=raising_on_drop)
    sender.enqueue(b"kept")
    sender.enqueue(b"dropped")  # must not raise
    assert sender.stats.dropped == 1


# --- should_log_drop: pure rate-limit decision ---


def test_should_log_drop_true_when_never_logged():
    assert should_log_drop(None, 100.0, 5.0) is True


def test_should_log_drop_false_within_interval():
    assert should_log_drop(100.0, 102.0, 5.0) is False


def test_should_log_drop_true_after_interval_elapses():
    assert should_log_drop(100.0, 105.0, 5.0) is True


# --- rate-limited drop logging with injected clock ---


def test_100_drops_within_one_interval_produce_exactly_one_log_record(caplog):
    clock = {"now": 0.0}
    sender = BoundedSender(
        maxsize=1, drop_log_interval_s=5.0, clock=lambda: clock["now"]
    )
    sender.enqueue(b"kept")
    with caplog.at_level(logging.WARNING, logger="mics_link"):
        for _ in range(100):
            sender.enqueue(b"overflow")
            clock["now"] += 0.01  # advance well within the 5s interval

    warning_records = [r for r in caplog.records if r.levelno == logging.WARNING]
    assert len(warning_records) == 1
    assert sender.stats.dropped == 100


def test_drop_log_reports_cumulative_total_across_suppressed_windows(caplog):
    """Decision 4: the log line reports the CUMULATIVE dropped count, not a per-window
    delta — so a reader who only ever sees the (rate-limited) log lines, never the raw
    counter, still learns the true total. Window 1's burst is suppressed after its first
    (logged) drop; once the interval elapses, window 2's first drop logs again — and that
    second line already reflects everything window 1 silently dropped, not just "+1".
    """
    clock = {"now": 0.0}
    sender = BoundedSender(maxsize=1, drop_log_interval_s=5.0, clock=lambda: clock["now"])
    sender.enqueue(b"kept")
    with caplog.at_level(logging.WARNING, logger="mics_link"):
        sender.enqueue(b"overflow")  # window 1: logs immediately, dropped == 1
        for _ in range(49):
            sender.enqueue(b"overflow")  # suppressed — still inside window 1
        clock["now"] = 10.0  # jump well past the 5s window
        sender.enqueue(b"overflow")  # window 2: logs again, dropped == 51 (cumulative)

    warning_records = [r for r in caplog.records if r.levelno == logging.WARNING]
    assert len(warning_records) == 2
    assert "1" in warning_records[0].getMessage()
    assert "51" in warning_records[1].getMessage()
    assert sender.stats.dropped == 51


def test_log_false_produces_zero_log_records_but_dropped_still_increments(caplog):
    sender = BoundedSender(maxsize=1, log=False)
    sender.enqueue(b"kept")
    with caplog.at_level(logging.WARNING, logger="mics_link"):
        for _ in range(10):
            sender.enqueue(b"overflow")

    assert caplog.records == []
    assert sender.stats.dropped == 10


# --- pop() ---


def test_pop_returns_none_on_empty_queue_without_raising_or_blocking_forever():
    sender = BoundedSender(maxsize=3)
    start = time.monotonic()
    result = sender.pop(timeout=0.01)
    elapsed = time.monotonic() - start
    assert result is None
    assert elapsed < 1.0


def test_pending_reflects_queue_depth():
    sender = BoundedSender(maxsize=5)
    assert sender.pending() == 0
    sender.enqueue(b"a")
    sender.enqueue(b"b")
    assert sender.pending() == 2
    sender.pop(timeout=0.01)
    assert sender.pending() == 1


# --- SenderStats ---


def test_stats_snapshot_returns_plain_dict():
    sender = BoundedSender(maxsize=3)
    sender.enqueue(b"a")
    snapshot = sender.stats.snapshot()
    assert isinstance(snapshot, dict)
    assert snapshot["enqueued"] == 1
    assert snapshot["dropped"] == 0
    assert "sent" in snapshot
    assert "abandoned" in snapshot


def test_stats_counters_are_plain_readable_attributes():
    stats = SenderStats()
    assert stats.enqueued == 0
    assert stats.sent == 0
    assert stats.dropped == 0
    assert stats.abandoned == 0
    stats.enqueued = 5
    assert stats.enqueued == 5
