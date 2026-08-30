"""`Pacer` — the origin-relative, drift-free scheduler behind mics-link's replay driver
(Phase 34, Plan 07's cross-platform/vendor-neutrality amendment). Public because Phase
35's video frame loop needs the exact same scheduling `replay()` uses, rather than a
second implementation (the same argument that retired the second wire codec, SDK-10):

    pacer = Pacer("realtime"); pacer.start()
    for i, frame in enumerate(frames):
        pacer.wait_until(i / fps)
        adapter.push(model.infer(frame))

Origin-relative, not cumulative: every `wait_until(t_rel)` call measures against the ONE
`start()` timestamp, never against the previous call's target. Cumulative per-call sleeping
drifts (each call's own rounding error compounds); measuring from a fixed origin does not.

Falling behind (a slow inference step, a stalled iterator) never produces a negative sleep
and never bursts to catch up: `wait_until` simply returns `0.0` immediately and counts the
occurrence in `behind_count()`. No latency, jitter or drift number is computed or printed
anywhere in this module — Phase 28 owns timing claims (see `mics_link/replay.py` decision 5).

`clock` and `sleep` are injected (default `time.monotonic` / `time.sleep`) so callers —
this module's own tests, and `replay()` — can prove exact scheduling against a recording
fake, with no real waiting. Windows note (SDK-14f): `time.sleep()` resolution below Python
3.11 is ~15.6ms, so `realtime`/`scaled` pacing above roughly 60Hz is approximate on those
interpreters — this module states that limit rather than attempting to work around it.
"""
import time

_MODES = ("realtime", "scaled", "fast")


class Pacer:
    """Drift-free origin-relative scheduler. `mode`: `"realtime"` | `"scaled"` | `"fast"`."""

    def __init__(self, mode="realtime", scale=1.0, clock=time.monotonic, sleep=time.sleep):
        if mode not in _MODES:
            raise ValueError("Pacer: mode must be one of {}, got {!r}".format(_MODES, mode))
        if scale <= 0:
            raise ValueError("Pacer: scale must be > 0, got {!r}".format(scale))
        self.mode = mode
        self.scale = scale
        self._clock = clock
        self._sleep = sleep
        self._origin = None
        self._behind_count = 0

    def start(self):
        """Stamp the origin against `clock()`. `replay()` calls this once, at the first
        row; calling it again simply re-stamps the origin — `Pacer`'s own contract, not
        something a caller normally needs.
        """
        self._origin = self._clock()

    def wait_until(self, t_rel):
        """Sleep so that, measured from `start()`'s origin, `t_rel` seconds (divided by
        `scale` when `mode == "scaled"`) have elapsed. Returns the number of seconds
        actually slept — `0.0` if already at or past that point (never a negative sleep,
        never a catch-up burst; see `behind_count()`). `mode == "fast"` never sleeps and
        always returns `0.0`. Auto-starts the origin on first use if `start()` was never
        called explicitly.
        """
        if self.mode == "fast":
            return 0.0
        if self._origin is None:
            self.start()
        target_offset = t_rel / self.scale if self.mode == "scaled" else t_rel
        remaining = (self._origin + target_offset) - self._clock()
        if remaining <= 0:
            if remaining < 0:  # exactly on time is not "behind" (every first row is 0.0)
                self._behind_count += 1
            return 0.0
        self._sleep(remaining)
        return remaining

    def behind_count(self):
        """How many `wait_until` calls found the schedule already behind (remaining <= 0)
        — never how far behind, and never printed as a number by `replay()` (decision 5).
        """
        return self._behind_count
