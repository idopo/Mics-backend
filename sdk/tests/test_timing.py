"""`mics_link.timing.Pacer` — the origin-relative, drift-free scheduler behind the replay
driver (Phase 34, Plan 07, "DLC-Live and Windows" amendment, SDK-12 amended). Public
because Phase 35's video frame loop needs the exact same scheduling `replay()` uses.

Every test injects both `clock` and `sleep` — nothing here ever waits for real. Timing
tests pair a fake clock with a `sleep` that advances that SAME clock by exactly what was
"slept" (mirroring a real clock during a real sleep); the "falling behind" test instead
advances the clock independently, simulating a slow iteration (e.g. a model inference step)
that eats into the schedule on its own.
"""
import pytest

from mics_link.timing import Pacer


def _paced_clock_and_sleep(start=0.0):
    """A fake clock + a sleep that advances that SAME clock by exactly what it "slept" —
    the shape real time has, with zero real waiting.
    """
    box = [start]
    calls = []

    def clock():
        return box[0]

    def sleep(seconds):
        calls.append(seconds)
        box[0] += seconds

    return clock, sleep, calls


# --- fast: never sleeps ---


def test_fast_mode_never_sleeps_regardless_of_t():
    calls = []
    pacer = Pacer(mode="fast", sleep=lambda s: calls.append(s))
    pacer.start()
    for t in (0.0, 0.5, 1.5, 100.0):
        assert pacer.wait_until(t) == 0.0
    assert calls == []
    assert pacer.behind_count() == 0


# --- realtime / scaled: origin-relative, drift-free ---


def test_realtime_mode_sleeps_the_expected_origin_relative_deltas():
    clock, sleep, calls = _paced_clock_and_sleep()
    pacer = Pacer(mode="realtime", clock=clock, sleep=sleep)
    pacer.start()
    for t in (0.0, 0.5, 1.5):
        pacer.wait_until(t)
    assert calls == pytest.approx([0.5, 1.0])


def test_scaled_mode_scale_2_halves_the_sleeps():
    clock, sleep, calls = _paced_clock_and_sleep()
    pacer = Pacer(mode="scaled", scale=2.0, clock=clock, sleep=sleep)
    pacer.start()
    for t in (0.0, 0.5, 1.5):
        pacer.wait_until(t)
    assert calls == pytest.approx([0.25, 0.5])


def test_scaled_mode_scale_half_doubles_the_sleeps():
    clock, sleep, calls = _paced_clock_and_sleep()
    pacer = Pacer(mode="scaled", scale=0.5, clock=clock, sleep=sleep)
    pacer.start()
    for t in (0.0, 0.5, 1.5):
        pacer.wait_until(t)
    assert calls == pytest.approx([1.0, 2.0])


# --- falling behind never bursts and never sleeps negative ---


def test_falling_behind_produces_no_negative_sleep_and_counts_it():
    box = [0.0]
    calls = []

    def clock():
        return box[0]

    def sleep(seconds):
        calls.append(seconds)
        box[0] += seconds

    pacer = Pacer(mode="realtime", clock=clock, sleep=sleep)
    pacer.start()
    pacer.wait_until(0.0)  # on time, no sleep call
    box[0] += 10.0  # a slow iteration eats into the schedule on its own
    slept = pacer.wait_until(0.5)  # now hopelessly overdue
    assert slept == 0.0
    assert calls == []  # no sleep call at all for the overdue row
    assert pacer.behind_count() == 1


# --- start()/wait_until() lifecycle ---


def test_wait_until_auto_starts_the_origin_if_start_never_called():
    clock, sleep, calls = _paced_clock_and_sleep(start=5.0)
    pacer = Pacer(mode="realtime", clock=clock, sleep=sleep)
    assert pacer.wait_until(0.0) == 0.0
    assert calls == []


# --- constructor validation ---


def test_invalid_mode_raises_value_error():
    with pytest.raises(ValueError):
        Pacer(mode="turbo")


def test_non_positive_scale_raises_value_error():
    with pytest.raises(ValueError):
        Pacer(mode="scaled", scale=0)
    with pytest.raises(ValueError):
        Pacer(mode="scaled", scale=-1.0)
