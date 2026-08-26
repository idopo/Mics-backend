"""C10's trigger-queue latency tracker, in one pass and O(1) memory.

Split out of clock_check_accumulator.py, which was past this repo's file-size ceiling.

WHAT IS BEING MEASURED. The trigger route is the only route carrying two instants:

    event.event_data.pi_timestamp_mono_ns   when the level changed
    t_mono_ns                               when the message came off the trigger queue

Their difference exists to expose the delay between a GPIO interrupt and the trigger
worker actually handling it.

IT CANNOT BE NEGATIVE, and that became true on 2026-08-26. Both ends now come off the SAME
counter: the edge is a pigpio tick captured at interrupt time, the receipt is a pigpio tick
read at dequeue, and both are mapped through the same fit. The difference is therefore a
real elapsed interval, and an edge cannot be dequeued before it happened. A negative
reading means the two ends are no longer on one counter.

It USED to be negative routinely, and that history is why this file exists. While the
receipt came from a raw `clock_gettime(CLOCK_MONOTONIC)` the two ends sat on the two
different physical counters this board has, ~10 ppm apart. Run 578 measured 48 negatives
in its first 108 edges, drifting linearly from +2.4 ms at t=0 to -2.5 ms at t=590 s -- the
bootstrap mapping's slope of exactly 1000.0 ns/us being wrong by the true rate ratio, until
the first re-fit landed at heartbeat_s = 600 s and flattened it to -0.16 ppm.

`drift_ppm` -- an O(1) least-squares slope of latency against edge time -- is kept from
that episode, but READ IT WITH CARE now: it measured the mapping's residual rate error only
BECAUSE the two ends were on different counters. On one counter that error is common-mode
and cancels exactly, so what is left is the trend of the queue delay itself -- a
heavy-tailed quantity (run 579: p50 2.86 ms, max 14.6 ms) whose least-squares slope over a
short window is mostly noise. Run 579's whole-run value was +21.6 ppm and its 25 s segments
read -32.8, -22.1, -26.0, +37.1, +44.8: the SIGN FLIPS, which is how you tell. A real rate
error does not (run 578 pre-re-fit: -10.53 then -11.52). Judge it on consistency across
segments, never on one number.
"""
from __future__ import annotations

from typing import Any

MAX_ABS_LATENCY_NS = 1_000_000_000
"""How far apart the edge and the queue receipt may be, in ns (1 s).

Derived, not guessed. The mapping's worst legitimate prediction error is its rate
tolerance times the gap between re-fits -- `DEFAULT_MAX_PPM` (200) x `DEFAULT_HEARTBEAT_S`
(600 s) = 120 ms -- plus whatever the trigger queue itself is backed up by. 1 s clears
that by ~8x and is still ~3 orders of magnitude below the shape this catches: a mapping on
the wrong timeline, which run 576 had at 137437 s.
"""


class LatencyTracker:
    """One forward pass. O(1) memory: five running sums and a bounded example list."""

    def __init__(self, max_examples: int):
        self.max_examples = max_examples
        self.measured = 0
        self.negative = 0
        self.over_bound = 0
        self.min_ns: int | None = None
        self.max_ns: int | None = None
        self._sum_ns = 0
        self.examples: list[dict] = []

        # Least squares of latency against edge time, accumulated in O(1). `_x0` re-bases
        # the edge axis on the first sample: t_mono_ns is ~1.6e14 and squaring it raw
        # loses the fit in float noise.
        self._x0: int | None = None
        self._n = 0
        self._sx = 0.0
        self._sy = 0.0
        self._sxy = 0.0
        self._sxx = 0.0

    def add(self, edge_ns: int, received_ns: int, module: Any = None) -> None:
        latency = received_ns - edge_ns
        self.measured += 1
        self._sum_ns += latency
        if self.min_ns is None or latency < self.min_ns:
            self.min_ns = latency
        if self.max_ns is None or latency > self.max_ns:
            self.max_ns = latency
        if latency < 0:
            self.negative += 1
            if len(self.examples) < self.max_examples:
                self.examples.append({
                    "pi_timestamp_mono_ns": edge_ns,
                    "t_mono_ns": received_ns,
                    "latency_ns": latency,
                    "module": module,
                    "why": "dequeued before its own edge -- the two ends are not on one counter",
                })

        if self._x0 is None:
            self._x0 = edge_ns
        x = (edge_ns - self._x0) / 1e9          # seconds into the run
        y = latency / 1e9                       # seconds of latency
        self._n += 1
        self._sx += x
        self._sy += y
        self._sxy += x * y
        self._sxx += x * x

        if abs(latency) > MAX_ABS_LATENCY_NS:
            self.over_bound += 1
            if len(self.examples) < self.max_examples:
                self.examples.append({
                    "pi_timestamp_mono_ns": edge_ns,
                    "t_mono_ns": received_ns,
                    "latency_ns": latency,
                    "module": module,
                })

    def drift_ppm(self) -> float | None:
        """How fast the latency itself is moving. See the module docstring before reading
        it as a rate error: since both ends came onto one counter the mapping's error
        cancels, and a short window's slope is dominated by queue-delay noise."""
        if self._n < 3:
            return None
        denom = self._n * self._sxx - self._sx * self._sx
        if denom <= 0:
            return None
        slope = (self._n * self._sxy - self._sx * self._sy) / denom   # s of latency per s
        return slope * 1e6

    def result(self) -> dict[str, Any]:
        mean = (self._sum_ns / self.measured) if self.measured else None
        # A run where every latency is exactly 0 is not a clock defect, it is a DEPLOY
        # signal: that Pi still passes the edge as its own payload timestamp. Run 576
        # reads 253 measured / min 0 / max 0; run 573, 62 of them.
        all_zero = bool(self.measured) and self.min_ns == 0 and self.max_ns == 0
        return {
            # Both ends come off the ONE counter now, so a negative interval is not a
            # tolerance question -- it means they no longer do. Gated again as of
            # mics_core 43f7b7b; see the module docstring for why it was ungated between
            # 65a38b5 and here. Fails closed: nothing measured means N/A, never PASS.
            "pass": (self.over_bound == 0 and self.negative == 0) if self.measured else None,
            "measured": self.measured,
            "over_1s_bound": self.over_bound,
            "negative": self.negative,
            "min_ns": self.min_ns,
            "mean_ns": mean,
            "max_ns": self.max_ns,
            "drift_ppm": self.drift_ppm(),
            "all_zero_the_two_instants_have_collapsed": all_zero,
            "examples": self.examples,
        }
