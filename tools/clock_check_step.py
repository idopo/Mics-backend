"""C6's wall-clock-step detector, in one pass and O(1) memory.

Split out of clock_check_accumulator.py, which is already past this repo's file-size
ceiling. See tools/tests/test_clock_check_step.py for the three defects in the previous
implementation that this replaces.

THE IDEA. Every document carries both `t_mono_ns` and `t_utc_ns`, and the pilot derives
the second from the first with an epoch offset recomputed per call:

    offset = t_utc_ns - t_mono_ns  ==  CLOCK_REALTIME - CLOCK_MONOTONIC, at stamp time

That series is FLAT to within chrony's slew -- microseconds -- because both clocks
advance together. A wall-clock step is the only thing that moves it, and it moves it by
exactly the step. So the step LOCATES ITSELF: nothing has to be compared against a
wall-clock string, no window has to be built from the very field the step displaces, and
`--step-time-utc` becomes a cross-check rather than the input everything depends on.
(Recording that minute by hand at the rig, under time pressure, is exactly the input that
goes wrong.)

PLAT-25/PLAT-34's claim has two halves and this checks both:

  * derived UTC moved by the step        -- the offset jump, reported as `largest_step_s`
  * no logged interval moved             -- the `t_mono_ns` interval ACROSS each jump must
                                            stay inside the commanded pulse period, like
                                            any other interval. A step that leaked into
                                            the monotonic timeline shows up here and
                                            nowhere else.
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

STEP_DETECT_NS = 1_000_000_000
"""How big an epoch-offset change counts as a STEP rather than as slew, in ns (1 s).

Bounded on both sides. chrony disciplines frequency, so between two documents seconds
apart the offset moves by microseconds -- 1 s is ~6 orders of magnitude above that and
cannot fire on slew. And it is far below any step worth forcing on a rig (the campaign
uses an hour), so a real step cannot hide under it.
"""

INTERVAL_TOLERANCE = 2.0
"""A `t_mono_ns` interval across a step may be at most this many pulse periods.

The same `> 2x` idiom C7 uses for drops, and for the same reason: one dropped edge leaves
exactly 2x, so the boundary is excluded deliberately and ordinary jitter cannot
false-positive. A step that leaked into the monotonic timeline moves the interval by the
whole step -- 3600 s against a 5 s period -- so nothing subtle is being asked of this.
"""


class StepDetector:
    """One forward pass over documents already sorted by `t_mono_ns`. O(1) memory."""

    def __init__(self, pulse_period_ns: int | None, step_time_utc: datetime | None,
                 step_window_s: float, max_examples: int):
        self.pulse_period_ns = pulse_period_ns
        self.step_time_utc = step_time_utc
        self.step_window_s = step_window_s
        self.max_examples = max_examples

        self._prev_mono_ns: int | None = None
        self._prev_offset_ns: int | None = None

        self.steps_detected = 0
        self.intervals_disturbed = 0
        self.largest_step_ns = 0
        self.examples: list[dict] = []
        self._step_utc_ns: list[int] = []

    def add(self, source: dict) -> None:
        t_mono = source.get("t_mono_ns")
        t_utc = source.get("t_utc_ns")
        if not isinstance(t_mono, (int, float)) or not isinstance(t_utc, (int, float)):
            return
        t_mono, t_utc = int(t_mono), int(t_utc)
        offset = t_utc - t_mono

        prev_mono, prev_offset = self._prev_mono_ns, self._prev_offset_ns
        self._prev_mono_ns, self._prev_offset_ns = t_mono, t_utc - t_mono
        if prev_offset is None or prev_mono is None:
            return

        jump = offset - prev_offset
        if abs(jump) < STEP_DETECT_NS:
            return

        self.steps_detected += 1
        if abs(jump) > abs(self.largest_step_ns):
            self.largest_step_ns = jump
        if len(self._step_utc_ns) < 64:                 # bounded; only used for the cross-check
            self._step_utc_ns.append(t_utc - jump)      # the step's own moment, pre-step frame

        interval = t_mono - prev_mono
        disturbed = (self.pulse_period_ns is not None
                     and interval > INTERVAL_TOLERANCE * self.pulse_period_ns)
        if disturbed:
            self.intervals_disturbed += 1
        if len(self.examples) < self.max_examples:
            self.examples.append({
                "step_s": jump / 1e9,
                "t_mono_ns_before": prev_mono,
                "t_mono_ns_after": t_mono,
                "interval_across_the_step_ns": interval,
                "interval_disturbed": bool(disturbed),
            })

    # -- report ---------------------------------------------------------------

    def _near_declared_step_time(self) -> bool | None:
        """None when no --step-time-utc was given; otherwise did any detected step land
        within --step-window-s of it. A mismatch is REPORTED, never swallowed: a step at
        the wrong moment is a different event from the one the operator forced."""
        if self.step_time_utc is None or not self._step_utc_ns:
            return None
        declared_ns = int(self.step_time_utc.timestamp() * 1e9)
        window_ns = int(self.step_window_s * 1e9)
        return any(abs(ns - declared_ns) <= window_ns for ns in self._step_utc_ns)

    def result(self) -> dict[str, Any]:
        near = self._near_declared_step_time()
        common = {
            "steps_detected": self.steps_detected,
            "largest_step_s": self.largest_step_ns / 1e9 if self.steps_detected else None,
            "intervals_disturbed": self.intervals_disturbed,
            "near_declared_step_time": near,
            "step_moments_utc": [
                datetime.fromtimestamp(ns / 1e9, tz=timezone.utc).isoformat()
                for ns in self._step_utc_ns[:self.max_examples]
            ],
            "examples": self.examples,
        }
        # Fail closed, like C5 / C9 / C10: an unevaluated check must never read PASS.
        if self.steps_detected == 0:
            return dict(common, **{
                "pass": None,
                "skipped": "no wall-clock step of at least %.0f s appears in this run"
                           % (STEP_DETECT_NS / 1e9),
            })
        if self.pulse_period_ns is None:
            return dict(common, **{
                "pass": None,
                "skipped": "the step was found, but 'no interval moved' is measured "
                           "against --pulse-period-s and none was given",
            })
        verdict = self.intervals_disturbed == 0 and near is not False
        return dict(common, **{"pass": verdict, "skipped": None})
