"""Tests for dlc_link.latest.LatestSlot (Task 2, plan 38-01)."""
import threading
import time

from dlc_link.latest import LatestSlot


def test_fresh_slot_reports_zero_counts():
    slot = LatestSlot()
    assert slot.snapshot() == {"puts": 0, "takes": 0, "overwrites": 0}


def test_fresh_slot_take_returns_nothing_yet_sentinel():
    slot = LatestSlot()
    ok, item = slot.take()
    assert ok is False
    assert item is None


def test_put_then_take_yields_the_item():
    slot = LatestSlot()
    slot.put("a")
    ok, item = slot.take()
    assert ok is True
    assert item == "a"
    assert slot.snapshot()["takes"] == 1
    assert slot.snapshot()["overwrites"] == 0


def test_two_puts_without_take_drops_the_oldest_not_the_newest():
    slot = LatestSlot()
    slot.put("a")
    slot.put("b")
    ok, item = slot.take()
    assert ok is True
    assert item == "b"
    assert slot.snapshot()["overwrites"] == 1


def test_second_take_with_no_intervening_put_reports_nothing_new():
    slot = LatestSlot()
    slot.put("a")
    slot.take()
    ok, item = slot.take()
    assert ok is False
    assert item is None


def test_put_never_blocks_or_raises_for_many_consecutive_puts():
    slot = LatestSlot()
    for i in range(1000):
        slot.put(i)
    assert slot.snapshot()["puts"] == 1000
    assert slot.snapshot()["overwrites"] == 999


def test_snapshot_keys_are_exactly_puts_takes_overwrites():
    slot = LatestSlot()
    slot.put("a")
    slot.take()
    assert set(slot.snapshot().keys()) == {"puts", "takes", "overwrites"}


def test_concurrent_puts_and_takes_lose_nothing_uncounted():
    slot = LatestSlot()
    stop = threading.Event()

    def producer():
        for i in range(500):
            slot.put(i)

    def consumer():
        while not stop.is_set():
            slot.take()

    consumer_thread = threading.Thread(target=consumer)
    consumer_thread.start()
    producer_thread = threading.Thread(target=producer)
    producer_thread.start()
    producer_thread.join()
    time.sleep(0.05)
    stop.set()
    consumer_thread.join()

    # Drain whatever is left sitting in the slot so the invariant holds exactly:
    # every put is either taken, overwritten, or still sitting in the slot -- nothing
    # was ever lost without being counted one way or the other.
    slot.take()
    snap = slot.snapshot()
    assert snap["puts"] == snap["takes"] + snap["overwrites"]
