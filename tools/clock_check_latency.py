"""C10's trigger-queue latency tracker, in one pass and O(1) memory.

Split out of clock_check_accumulator.py, which was past this repo's file-size ceiling.

WHAT IS BEING MEASURED. The trigger route is the only route carrying two instants:

    event.event_data.pi_timestamp_mono_ns   when the level changed
    t_mono_ns                               when the message came off the trigger queue

Their difference exists to expose the delay between a GPIO interrupt and the trigger
worker actually handling it.

WHY IT MAY BE NEGATIVE, AND WHY THAT IS NOT A DEFECT. The two numbers are not produced the
same way. The edge is a pigpio tick MAPPED onto CLOCK_MONOTONIC through the calibrated
affine fit; the receipt is a RAW `clock_gettime(CLOCK_MONOTONIC)`. The fit has bounded
prediction error, so a mapped edge can land a few milliseconds ahead of a raw read taken
just after it, and the difference goes negative. The physical statement "an edge cannot be
dequeued before it happened" is true of the instants and NOT of these two derived numbers.

Run 578 measured this for the first time -- nothing before it could, because both fields
held the same number. The latency drifted linearly from +2.4 ms at t=0 to -2.5 ms at
t=590 s: 8.5 ppm, which is the BOOTSTRAP mapping's slope of exactly 1000.0 ns/us being
wrong by the true tick-to-CLOCK_MONOTONIC rate ratio on this Pi, before the first re-fit
lands at heartbeat_s = 600 s.

So this reports `drift_ppm` -- an O(1) least-squares slope of latency against edge time --
which measures exactly that residual rate error and should collapse toward zero once the
mapping re-fits. It gates only on GROSS breakage, because a threshold tight enough to
catch anything else would be a guess.
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
        """How fast the latency itself is moving -- the mapping's residual rate error.

        A healthy re-fitted mapping sits near zero. Run 578's first 10 minutes read about
        -8.5 ppm, the bootstrap slope's error before the first re-fit.
        """
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
            # Gates on GROSS breakage only. The sign is deliberately NOT gated: the edge is
            # a MAPPED tick and the receipt is a RAW clock read, so the fit's bounded
            # prediction error can legitimately put the edge a few ms ahead. See the module
            # docstring. Fails closed: nothing measured means N/A, never PASS.
            "pass": (self.over_bound == 0) if self.measured else None,
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
