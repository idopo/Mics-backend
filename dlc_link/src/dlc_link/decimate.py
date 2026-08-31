"""Deadband + per-signal Hz cap decimator (D-20, D-22).

Deadband and rate policy are the CALLER's responsibility, not `mics_link`'s — the SDK's
`sdk/examples/callback_sender.py` rule 3 states this directly ("decimation and rate
policy are the caller's, not mics_link's"), and `sdk/`'s device-neutrality guard bans
DLC vocabulary there anyway (D-20). This module is genuinely new code: no deadband or
rate-cap implementation exists anywhere else in this repo. The only thing copied from
an analog is the testability shape — a constructor-injected `clock`, exactly as
`mics_link.timing.Pacer` injects its `clock`/`sleep` — so tests drive it with a fake
and never sleep for real.

**`DecimateStats` carries counts only, and nothing else (DLC-10).** No duration, gap,
or elapsed-time figure of any kind is computed, printed or stored anywhere in this
module -- Phase 28 owns timing claims. (Spelled out with the specific prohibited terms
in the comment above `DecimateStats`, below.)

**Why the defaults matter (D-21, D-22).** The Pi has no ingress queue: `ZMQStream(...
).on_recv` runs decode + tracker update + dispatch SYNCHRONOUSLY on the shared Tornado
IOLoop, which also serves the pilot's orchestrator DEALER and the STOP channel. A
high-rate sender therefore does not overflow a buffer — it starves that IOLoop,
degrading FDA transition timing and STOP responsiveness. Separately, every accepted
signal triggers one `@log_action`-driven CONTINUOUS ElasticSearch event: a strict 1:1
amplification, so the message rate IS the ElasticSearch write load. `RECOMMENDED_DEFAULTS`
below is sized against both of those facts, not against the retracted "256-entry queue"
figure: 2 bodyparts x 3 signals (likelihood, x, y) at 10 Hz decimated = 60 messages/sec,
which is Phase 18's proven envelope.
"""
import time

RECOMMENDED_DEFAULTS = {
    # Likelihood deadband: DLC's own pcutoff on this project is 0.01, two orders of
    # magnitude below the 0.6 default -- 0.02 is a coarse-enough band to suppress
    # jitter without hiding a real confidence swing.
    "likelihood_deadband": 0.02,
    # Coordinate deadband: coordinates are normalised 0..1 per D-18, so 0.002 is
    # about two pixels on a one-thousand-pixel-wide frame.
    "coordinate_deadband": 0.002,
    # Per-signal cap: 100ms == 10Hz.
    "min_interval_ms": 100,
}
# Budget arithmetic (D-22): 2 bodyparts x 3 signals (likelihood, x, y) each capped at
# 10Hz = 2 * 3 * 10 = 60 messages/sec -- Phase 18's proven envelope. This is
# load-bearing for two reasons (D-21): the Pi's shared Tornado IOLoop, which also
# carries the STOP channel, has no ingress queue and runs decode+dispatch
# synchronously, so a high rate starves it rather than merely queuing; and every
# accepted signal is a 1:1 amplification into one ElasticSearch CONTINUOUS event, so
# the message rate directly IS the ElasticSearch write load.


# DLC-10: no field on this class may be added whose name or value could be read as a
# latency, jitter or drift figure. Counts only, always.
class DecimateStats:
    """Per-reason counters only -- see the DLC-10 comment directly above this class."""

    __slots__ = ("considered", "passed", "suppressed_deadband", "suppressed_rate")

    def __init__(self):
        self.considered = 0
        self.passed = 0
        self.suppressed_deadband = 0
        self.suppressed_rate = 0

    def snapshot(self) -> dict:
        return {
            "considered": self.considered,
            "passed": self.passed,
            "suppressed_deadband": self.suppressed_deadband,
            "suppressed_rate": self.suppressed_rate,
        }

    def reset(self):
        self.considered = 0
        self.passed = 0
        self.suppressed_deadband = 0
        self.suppressed_rate = 0


class Decimator:
    """Per-signal-name deadband + Hz cap, with an injected clock for testability.

    `deadband` and `min_interval_ms` are per-signal-name override dicts; a name not
    present in either falls back to `default_deadband` / `default_min_interval_ms`.
    `clock` mirrors `mics_link.timing.Pacer`'s injection seam so tests drive it with a
    fake and never sleep.
    """

    def __init__(
        self,
        deadband=None,
        min_interval_ms=None,
        default_deadband=0.0,
        default_min_interval_ms=0,
        clock=time.monotonic,
    ):
        self._deadband = dict(deadband or {})
        self._min_interval_ms = dict(min_interval_ms or {})
        self._default_deadband = default_deadband
        self._default_min_interval_ms = default_min_interval_ms
        self._clock = clock
        self.stats = DecimateStats()
        self._last_passed_value = {}
        self._last_passed_send_time = {}

    def _deadband_for(self, name: str) -> float:
        return self._deadband.get(name, self._default_deadband)

    def _min_interval_ms_for(self, name: str) -> float:
        return self._min_interval_ms.get(name, self._default_min_interval_ms)

    def should_send(self, name: str, value) -> bool:
        """Decide whether `value` for signal `name` should be sent.

        Order matters: (1) a name's first sample always passes -- there is no
        previous value or send time to compare against; (2) the rate cap is checked
        BEFORE the deadband; (3) the deadband is checked only for numeric values.
        Rate-cap and deadband state are always recorded against the last PASSED send,
        never against the last considered sample -- otherwise a run of suppressed
        samples silently slides the reference and the signal never updates again.
        """
        self.stats.considered += 1
        now = self._clock()

        if name not in self._last_passed_send_time:
            self._record_pass(name, value, now)
            return True

        min_interval_ms = self._min_interval_ms_for(name)
        if min_interval_ms > 0:
            since_last_pass_ms = (now - self._last_passed_send_time[name]) * 1000.0
            if since_last_pass_ms < min_interval_ms:
                self.stats.suppressed_rate += 1
                return False

        if isinstance(value, (int, float)) and not isinstance(value, bool):
            last_value = self._last_passed_value[name]
            if abs(value - last_value) <= self._deadband_for(name):
                self.stats.suppressed_deadband += 1
                return False

        self._record_pass(name, value, now)
        return True

    def _record_pass(self, name, value, now):
        self.stats.passed += 1
        self._last_passed_value[name] = value
        self._last_passed_send_time[name] = now

    def reset(self):
        """Clear per-name state and counters, so a long-running process can start a
        fresh accounting window per run."""
        self.stats.reset()
        self._last_passed_value.clear()
        self._last_passed_send_time.clear()
