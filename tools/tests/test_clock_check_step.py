"""C6, the wall-clock step check, rebuilt 2026-08-26 after three defects were found in it.

The claim under test is PLAT-25/PLAT-34's, and it has two halves:

    a wall-clock step MUST move derived UTC by the step
    a wall-clock step MUST move no logged interval

The old implementation could not test either. Reproduced against a HEALTHY synthetic rig
before this rewrite:

  1. It split before/after with `d["@timestamp"] < step_iso` -- a STRING compare of ISO
     timestamps carrying different UTC offsets. event_log_v2 writes `+03:00` and
     `--step-time-utc` is UTC, so '2026-08-26T15:00:00+03:00' < '2026-08-26T12:00:00+00:00'
     compares '15' against '12'. Every document sorted "after", `before` came back empty,
     and C6 returned N/A on every real run.
  2. Its window admitted a document by that document's OWN rendered timestamp -- the value
     the step moves. A +1 h step puts the far side 3600 s outside the default 180 s window,
     so the window could never hold both sides of the thing it exists to bracket.
  3. `pass = (max_interval == boundary_interval)` was backwards. With ordinary jitter the
     largest interval is some other interval, so a healthy rig FAILED (boundary 5.000 s,
     max 5.008 s); and a rig where the step HAD leaked into t_mono makes the boundary the
     max, so it PASSED.

The rebuild works on `offset = t_utc_ns - t_mono_ns`, the epoch offset at the moment each
document was stamped. That series is flat except at a step, so the step LOCATES ITSELF and
nothing has to be compared against a wall-clock string at all.
"""
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from clock_check_accumulator import RunAccumulator

STEP_UTC = datetime(2026, 8, 26, 12, 0, 0, tzinfo=timezone.utc)
BASE_MONO = 100_000_000_000_000
PULSE_NS = 5_000_000_000
STEP_AT = 10
OFFSET0 = int(STEP_UTC.timestamp() * 1e9) - (BASE_MONO + STEP_AT * PULSE_NS)
JITTER = [0, 3_000_000, -2_000_000, 8_000_000, 1_000_000]   # +/- a few ms, like a real rig
TZ3 = timezone(timedelta(hours=3))                          # what event_log_v2 actually writes


def _build(step_ns=3_600_000_000_000, *, jitter=True, leak_into_mono=False, n=20, tz=TZ3):
    """A run that crosses one wall-clock step.

    `leak_into_mono` is the DEFECT the check exists to catch: the step also moved the
    monotonic timeline, so an interval moved.
    """
    docs, mono = [], BASE_MONO
    for i in range(n):
        if i:
            mono += PULSE_NS + (JITTER[i % len(JITTER)] if jitter else 0)
            if leak_into_mono and i == STEP_AT:
                mono += step_ns
        utc = mono + OFFSET0 + (step_ns if i >= STEP_AT else 0)
        stamped = datetime.fromtimestamp(utc / 1e9, tz=timezone.utc).astimezone(tz)
        docs.append({"_source": {
            "t_mono_ns": mono, "t_utc_ns": utc, "ts_source": "hardware",
            "timestamp": stamped.isoformat(),
            "event": {"event_type": "gpio.Digital_Out",
                      "event_data": {"id": "Mid_LED"}, "level": i % 2}}})
    return docs


def _c6(docs, *, step_time_utc=STEP_UTC, pulse_period_s=5.0, step_window_s=180.0):
    acc = RunAccumulator(pulse_period_s=pulse_period_s, step_time_utc=step_time_utc,
                         step_window_s=step_window_s, max_examples=5)
    for doc in docs:
        acc.add(doc)
    return acc.finalize()["C6_clock_step"]


# -- the two halves of the claim ------------------------------------------------------

def test_a_healthy_step_moves_utc_by_the_step_and_moves_no_interval():
    check = _c6(_build())
    assert check["pass"] is True
    assert check["steps_detected"] == 1
    assert abs(check["largest_step_s"] - 3600.0) < 0.01
    assert check["intervals_disturbed"] == 0


def test_a_step_that_leaked_into_the_monotonic_timeline_fails():
    """The defect C6 exists to catch: derived UTC moved AND so did a logged interval."""
    check = _c6(_build(leak_into_mono=True))
    assert check["pass"] is False
    assert check["intervals_disturbed"] == 1
    assert check["examples"]


# -- the three defects, each pinned so it cannot come back ----------------------------

def test_the_index_timezone_does_not_hide_the_step():
    """Defect 1. event_log_v2 writes +03:00; --step-time-utc is UTC. The old string
    compare put every document on the same side and returned N/A on every real run."""
    for tz in (TZ3, timezone.utc, timezone(timedelta(hours=-7))):
        check = _c6(_build(tz=tz))
        assert check["pass"] is True, "tz %s hid the step: %r" % (tz, check)
        assert check["steps_detected"] == 1


def test_a_one_hour_step_is_found_with_the_default_window():
    """Defect 2. The old window admitted a document by its OWN rendered timestamp -- the
    value the step moves -- so a +1 h step threw the far side 3600 s outside a 180 s
    window and the window could never hold both sides of the step it brackets."""
    check = _c6(_build(3_600_000_000_000), step_window_s=180.0)
    assert check["pass"] is True
    assert abs(check["largest_step_s"] - 3600.0) < 0.01


def test_ordinary_jitter_does_not_fail_a_healthy_rig():
    """Defect 3. `max_interval == boundary_interval` failed on a correct rig the moment
    any other interval happened to be the largest -- boundary 5.000 s, max 5.008 s."""
    assert _c6(_build(jitter=True))["pass"] is True
    assert _c6(_build(jitter=False))["pass"] is True


def test_a_backwards_step_is_caught_too():
    """chrony can step in either direction, and PLAT-25 names both."""
    check = _c6(_build(-3_600_000_000_000))
    assert check["pass"] is True
    assert abs(check["largest_step_s"] + 3600.0) < 0.01


def test_two_steps_are_both_judged():
    """Stopping chrony, stepping, then restarting it can make chrony step BACK rather than
    slew, so a campaign can legitimately contain two. The monotonic timeline must survive
    both, so only t_utc_ns moves here -- t_mono_ns stays on its own 5 s cadence."""
    docs = _build(30_000_000_000, n=30)
    for doc in docs[20:]:                        # chrony steps the offset back at pulse 20
        doc["_source"]["t_utc_ns"] -= 30_000_000_000
    check = _c6(docs, step_window_s=100000.0)
    assert check["steps_detected"] == 2
    assert check["intervals_disturbed"] == 0
    assert check["pass"] is True


def test_a_second_step_that_disturbs_an_interval_still_fails():
    """Non-vacuity for the case above: two steps means two chances to move the timeline,
    and BOTH are judged, not just the first."""
    docs = _build(30_000_000_000, n=30)
    for doc in docs[20:]:
        doc["_source"]["t_utc_ns"] -= 30_000_000_000
        doc["_source"]["t_mono_ns"] += 200_000_000_000   # the step leaked, at the SECOND one
    check = _c6(docs, step_window_s=100000.0)
    assert check["steps_detected"] == 2
    assert check["intervals_disturbed"] == 1
    assert check["pass"] is False


# -- fail-closed, like C5 / C9 / C10 --------------------------------------------------

def test_a_run_with_no_step_is_not_reported_as_pass():
    """An unevaluated check reading PASS is how run 576's 38 h error survived a green run."""
    check = _c6(_build(0))
    assert check["pass"] is None
    assert check["steps_detected"] == 0
    assert "no wall-clock step" in check["skipped"]


def test_no_step_time_given_still_finds_and_judges_the_step():
    """The step locates itself in the offset series, so --step-time-utc is a CROSS-CHECK
    rather than the thing the window is built from. Recording the minute by hand at the
    rig, under time pressure, is exactly the input that goes wrong."""
    check = _c6(_build(), step_time_utc=None)
    assert check["pass"] is True
    assert check["steps_detected"] == 1
    assert check["near_declared_step_time"] is None


def test_a_declared_step_time_that_does_not_match_is_reported_not_swallowed():
    wrong = STEP_UTC + timedelta(hours=6)
    check = _c6(_build(), step_time_utc=wrong, step_window_s=180.0)
    assert check["near_declared_step_time"] is False
    assert check["pass"] is False, "a step nowhere near the declared time must not pass"


def test_without_a_pulse_period_the_interval_half_cannot_be_judged():
    """`--pulse-period-s` is what 'no interval moved' is measured against. Without it the
    check reports the step and refuses to claim the second half."""
    check = _c6(_build(), pulse_period_s=None)
    assert check["pass"] is None
    assert check["steps_detected"] == 1
    assert "pulse-period" in check["skipped"]
