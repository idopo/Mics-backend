"""Pure heartbeat scheduling against an injected clock (Phase 34, Plan 03).

Stdlib-only, no socket-library import, no concurrency primitives, no blocking wait of any
kind anywhere in this module — `clock` is injected (defaults to `time.monotonic`) so plan
34-06's IO worker decides when to poll `due()` and this module never blocks or sends
anything itself. It never builds a wire frame either; the caller passes the result to
`mics_link.wire.hb_frame(...)` when `due()` says so.

`DEFAULT_HEARTBEAT_S = 1.0` derivation (decision 1): the one real fixture observed on the
rig (`ExtlinkDemo`, `pilot_hardware_config` row 21) declares `stale_ms: 3000`, and the Pi's
own liveness poller checks at `stale_ms / 2`. A 1:3 heartbeat:timeout ratio is the standard
keepalive convention and survives one dropped or delayed heartbeat. The caller must never
have to look this number up in a database row — it is a constructor kwarg with this safe
default. A Pi configured with `stale_ms` below ~3s needs an explicit `interval_s` override.

1.0s is also well above Windows' pre-3.11 wait-timer granularity (~15.6ms, the default
WinAPI timer period) — the vision box may run Python 3.9/3.10 on Windows (SDK-14), so the
default interval must stay irrelevant to that granularity by a wide margin. This module
itself never waits or pauses execution, but the value is chosen so that whatever caller
loop polls `due()` on a coarse timer still behaves correctly.

Decision 2's rationale: the Pi's `default_liveness` check is `(now - last_msg_ts_ms) <
stale_ms` over ALL inbound messages, not heartbeats specifically — so a sender already
streaming SIG/EVT/ACK traffic does not also need to inject a separate HB frame. `note_sent`
must therefore be called on EVERY outbound frame of any kind, and `due()` suppresses the
heartbeat while that traffic keeps `last_send_at` fresh. This is a real load reduction for
the Phase 35 soak, not a micro-optimisation.
"""
import time

DEFAULT_HEARTBEAT_S = 1.0


def heartbeat_due(now, last_send_at, interval_s):
    """Pure. `last_send_at` is the monotonic time of the LAST OUTBOUND FRAME of any kind
    (SIG/EVT/HB/ACK), not just the last heartbeat. `None` means nothing has ever been sent,
    which is always due. The boundary is inclusive: `now - last_send_at >= interval_s`.
    Mutates nothing — safe to call repeatedly with identical arguments.
    """
    if last_send_at is None:
        return True
    return (now - last_send_at) >= interval_s


class HeartbeatSchedule:
    """Stateful convenience wrapper around `heartbeat_due` + an injected clock.

    `note_sent` must be called on EVERY outbound frame (see decision 2), not just actual
    heartbeats — that is what lets traffic suppress the heartbeat.
    """

    def __init__(self, interval_s=DEFAULT_HEARTBEAT_S, clock=time.monotonic):
        self.interval_s = interval_s
        self._clock = clock
        self._last_send_at = None

    def due(self, now=None):
        if now is None:
            now = self._clock()
        return heartbeat_due(now, self._last_send_at, self.interval_s)

    def note_sent(self, now=None):
        if now is None:
            now = self._clock()
        self._last_send_at = now
