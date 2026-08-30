"""RED-phase tests for `mics_link.heartbeat` — pure scheduling over an injected clock.

No `time.sleep` anywhere here: every scenario advances a fake clock explicitly. That is
deliberate (see the amendment in 34-03-PLAN.md) — a real-sleep-based test would pass on
this dev host and then flake on a Windows box running Python < 3.11, where `time.sleep()`
resolution is ~15.6 ms. Do not "improve" these into real sleeps.
"""
from mics_link.heartbeat import DEFAULT_HEARTBEAT_S, HeartbeatSchedule, heartbeat_due


def test_heartbeat_due_when_nothing_sent_yet():
    assert heartbeat_due(now=0.0, last_send_at=None, interval_s=1.0) is True


def test_heartbeat_not_due_before_interval_elapses():
    assert heartbeat_due(now=10.5, last_send_at=10.0, interval_s=1.0) is False


def test_heartbeat_due_on_inclusive_boundary():
    assert heartbeat_due(now=11.0, last_send_at=10.0, interval_s=1.0) is True


def test_heartbeat_due_after_interval_elapses():
    assert heartbeat_due(now=11.5, last_send_at=10.0, interval_s=1.0) is True


def test_default_heartbeat_interval_is_one_second():
    assert DEFAULT_HEARTBEAT_S == 1.0


def test_heartbeat_due_is_pure_and_mutates_nothing():
    class Sentinel:
        pass

    sentinel = Sentinel()
    before = dict(sentinel.__dict__)
    result_a = heartbeat_due(now=11.5, last_send_at=10.0, interval_s=1.0)
    result_b = heartbeat_due(now=11.5, last_send_at=10.0, interval_s=1.0)
    assert result_a == result_b
    assert sentinel.__dict__ == before


class FakeClock:
    """A callable clock a test can move forward explicitly — never wall time."""

    def __init__(self, start=0.0):
        self.now = start

    def __call__(self):
        return self.now

    def advance(self, delta):
        self.now += delta


def test_schedule_due_at_construction_with_nothing_sent():
    clock = FakeClock(start=0.0)
    schedule = HeartbeatSchedule(clock=clock)
    assert schedule.due() is True


def test_schedule_note_sent_suppresses_until_interval_elapses():
    clock = FakeClock(start=0.0)
    schedule = HeartbeatSchedule(clock=clock)
    schedule.note_sent()
    clock.advance(0.5)
    assert schedule.due() is False
    clock.advance(0.5)
    assert schedule.due() is True


def test_schedule_burst_of_note_sent_keeps_due_false_throughout():
    """Decision 2: traffic (SIG/EVT/ACK) suppresses the heartbeat — a 60Hz sender never
    needs to inject a separate HB frame while it is already talking."""
    clock = FakeClock(start=0.0)
    schedule = HeartbeatSchedule(clock=clock, interval_s=1.0)
    frame_interval = 1.0 / 60.0
    for _ in range(120):  # ~2s of 60Hz traffic, well past a naive 1s interval
        clock.advance(frame_interval)
        schedule.note_sent()
        assert schedule.due() is False


def test_schedule_honours_interval_override():
    clock = FakeClock(start=0.0)
    schedule = HeartbeatSchedule(interval_s=0.25, clock=clock)
    assert schedule.interval_s == 0.25
    schedule.note_sent()
    clock.advance(0.2)
    assert schedule.due() is False
    clock.advance(0.05)
    assert schedule.due() is True


def test_schedule_due_accepts_explicit_now_argument():
    clock = FakeClock(start=0.0)
    schedule = HeartbeatSchedule(clock=clock, interval_s=1.0)
    schedule.note_sent(now=5.0)
    assert schedule.due(now=5.5) is False
    assert schedule.due(now=6.0) is True
