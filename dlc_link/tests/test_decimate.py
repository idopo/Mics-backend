"""Tests for `dlc_link.decimate` — deadband + per-signal Hz cap decimator (D-20, D-22).

Uses a `FakeClock` so every test is deterministic and none of them sleep for real.
"""
from dlc_link.decimate import Decimator


class FakeClock:
    """Injectable clock exposing `advance(seconds)`; mirrors the seam
    `mics_link.timing.Pacer` uses for `clock`/`sleep` injection."""

    def __init__(self, start=0.0):
        self._now = start

    def advance(self, seconds):
        self._now += seconds

    def __call__(self):
        return self._now


class TestFirstSample:
    def test_first_sample_always_passes(self):
        clock = FakeClock()
        dec = Decimator(clock=clock)
        assert dec.should_send("nose_x", 0.5) is True
        assert dec.stats.snapshot() == {
            "considered": 1,
            "passed": 1,
            "suppressed_deadband": 0,
            "suppressed_rate": 0,
        }


class TestRateCheckedBeforeDeadband:
    def test_sample_inside_both_windows_is_suppressed_as_rate(self):
        clock = FakeClock()
        dec = Decimator(default_deadband=0.5, default_min_interval_ms=100, clock=clock)
        dec.should_send("nose_x", 0.0)  # first sample passes
        clock.advance(0.01)  # 10ms later: inside both the rate window and the deadband
        result = dec.should_send("nose_x", 0.01)
        assert result is False
        assert dec.stats.suppressed_rate == 1
        assert dec.stats.suppressed_deadband == 0

    def test_sample_outside_rate_but_inside_deadband_is_suppressed_as_deadband(self):
        clock = FakeClock()
        dec = Decimator(default_deadband=0.5, default_min_interval_ms=100, clock=clock)
        dec.should_send("nose_x", 0.0)
        clock.advance(0.2)  # 200ms later: outside the 100ms rate window
        result = dec.should_send("nose_x", 0.01)  # inside the 0.5 deadband
        assert result is False
        assert dec.stats.suppressed_deadband == 1
        assert dec.stats.suppressed_rate == 0

    def test_sample_outside_both_passes(self):
        clock = FakeClock()
        dec = Decimator(default_deadband=0.01, default_min_interval_ms=100, clock=clock)
        dec.should_send("nose_x", 0.0)
        clock.advance(0.2)
        result = dec.should_send("nose_x", 1.0)
        assert result is True
        assert dec.stats.passed == 2


class TestReferenceIsLastPassedNotLastConsidered:
    def test_reference_is_last_passed_value(self):
        clock = FakeClock()
        dec = Decimator(default_deadband=0.002, default_min_interval_ms=0, clock=clock)
        results = [
            dec.should_send("nose_x", v) for v in (0.000, 0.001, 0.002, 0.003)
        ]
        assert results == [True, False, False, True]
        assert dec.stats.passed == 2

    def test_sub_deadband_drift_eventually_passes_against_the_last_passed_value(self):
        clock = FakeClock()
        dec = Decimator(default_deadband=0.005, default_min_interval_ms=0, clock=clock)
        # Each step moves by 0.001, comfortably under the 0.005 deadband when measured
        # against the immediately preceding sample -- but the reference is the last
        # PASSED value (0.000), so the cumulative drift eventually clears it.
        values = [0.000, 0.001, 0.002, 0.003, 0.004, 0.005, 0.006]
        results = [dec.should_send("nose_x", v) for v in values]
        assert results[0] is True  # first sample
        assert True in results[1:]  # some later sample eventually passes


class TestPerNameOverride:
    def test_per_name_override_beats_the_default(self):
        clock = FakeClock()
        dec = Decimator(
            deadband={"nose_x": 0.5},
            default_deadband=0.0,
            default_min_interval_ms=0,
            clock=clock,
        )
        dec.should_send("nose_x", 0.0)
        result = dec.should_send("nose_x", 0.1)  # would fail default (0.0) but passes override
        assert result is False
        assert dec.stats.suppressed_deadband == 1


class TestNonNumericValues:
    def test_str_value_bypasses_deadband_but_obeys_rate_cap(self):
        clock = FakeClock()
        dec = Decimator(default_deadband=0.0, default_min_interval_ms=100, clock=clock)
        dec.should_send("state", "idle")
        clock.advance(0.01)
        result = dec.should_send("state", "moving")
        assert result is False
        assert dec.stats.suppressed_rate == 1
        assert dec.stats.suppressed_deadband == 0

    def test_str_value_passes_once_rate_window_clears(self):
        clock = FakeClock()
        dec = Decimator(default_deadband=0.0, default_min_interval_ms=100, clock=clock)
        dec.should_send("state", "idle")
        clock.advance(0.2)
        result = dec.should_send("state", "moving")
        assert result is True


class TestReset:
    def test_reset_clears_counters_and_per_name_memory(self):
        clock = FakeClock()
        dec = Decimator(default_deadband=0.5, default_min_interval_ms=0, clock=clock)
        dec.should_send("nose_x", 0.0)
        dec.should_send("nose_x", 0.1)  # suppressed
        dec.reset()
        assert dec.stats.snapshot() == {
            "considered": 0,
            "passed": 0,
            "suppressed_deadband": 0,
            "suppressed_rate": 0,
        }
        # Per-name memory cleared too: the next sample for "nose_x" is treated as first.
        assert dec.should_send("nose_x", 999.0) is True


class TestSnapshotShape:
    def test_snapshot_returns_exactly_the_four_counter_keys(self):
        clock = FakeClock()
        dec = Decimator(clock=clock)
        dec.should_send("nose_x", 0.0)
        snapshot = dec.stats.snapshot()
        assert set(snapshot) == {
            "considered",
            "passed",
            "suppressed_deadband",
            "suppressed_rate",
        }
        assert not any("duration" in key or "ms" in key for key in snapshot)
