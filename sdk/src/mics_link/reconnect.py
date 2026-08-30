"""Pure connect/disconnect state machine over synthetic monitor events (Phase 34, Plan 03).

Mirrors `ready_gate_decision`'s style (READ-ONLY reference at
`~/mics_core/autopilot/autopilot/hardware/external_hardware_runtime.py:202-211`): a plain
function taking explicit inputs and returning an explicit output, with all socket/monitor
plumbing living somewhere else entirely (plan 34-06). `next_state` is callable with no
socket, no clock and no object graph — the underlying messaging library's numeric event
ids are translated to the three strings below inside `transport.py`, never inside this
module.

The MONITOR_* constants are re-exported from `transport.py` (34-06 merge reconciliation —
plan 34-02's `transport.py` had not landed in this worktree when this module was first
written, so a second, independently-maintained copy briefly existed here; `transport.py` is
the single owner now, since it is where the messaging library's numeric event ids are
actually translated into these three strings). Importing `transport.py` does not pull the
socket library in here: its own module scope only imports `.errors`, and every socket-
library reference in that file lives inside a function body — this module stays importable
with no socket library installed.
"""
import logging

from .transport import MONITOR_CONNECTED, MONITOR_DISCONNECTED, MONITOR_RETRIED

STATE_DISCONNECTED = "disconnected"
STATE_CONNECTED = "connected"

_TRANSITIONS = {
    (STATE_DISCONNECTED, MONITOR_CONNECTED): STATE_CONNECTED,
    (STATE_CONNECTED, MONITOR_DISCONNECTED): STATE_DISCONNECTED,
    # MONITOR_RETRIED is intentionally absent from this table (decision 4): the underlying
    # messaging library emits a retry event on every backoff attempt, and treating it as a
    # disconnect would produce a stream of spurious edges during normal reconnection. Any
    # state + RETRIED falls through to "unknown event" below and stays unchanged.
}

_logger = logging.getLogger(__name__)


def next_state(current, event):
    """Pure. Unknown events (including MONITOR_RETRIED) return `current` unchanged."""
    return _TRANSITIONS.get((current, event), current)


class ConnectionState:
    """Wraps `next_state` with edge-triggered notification.

    `on_state_change(connected: bool)` fires ONLY on real transitions (decision 3) — a
    single bool, so `lambda ok: print(ok)` is a complete, correct caller. A callback that
    raises is caught and logged at warning level (decision 5); it never breaks the caller's
    IO loop, and passing `on_state_change=None` is always safe.

    This class owns no sequence counter and never will (decision 6): `seq` continuity
    across a reconnect is a structural guarantee of `wire.SeqCounter` (no reset method
    exists), not something this state machine enforces or could accidentally break. Do not
    add a reset call here.
    """

    def __init__(self, on_state_change=None, logger=None, initial=STATE_DISCONNECTED):
        self._on_state_change = on_state_change
        self._logger = logger or _logger
        self._state = initial
        self.retries = 0

    @property
    def state(self):
        return self._state

    @property
    def connected(self):
        return self._state == STATE_CONNECTED

    def apply(self, event):
        """Returns True iff this event caused a real edge."""
        if event == MONITOR_RETRIED:
            self.retries += 1
            return False
        new_state = next_state(self._state, event)
        if new_state == self._state:
            return False
        self._state = new_state
        self._fire(new_state == STATE_CONNECTED)
        return True

    def apply_all(self, events):
        for event in events:
            self.apply(event)

    def _fire(self, connected):
        if self._on_state_change is None:
            return
        try:
            self._on_state_change(connected)
        except Exception:
            self._logger.warning(
                "on_state_change callback raised", exc_info=True
            )
