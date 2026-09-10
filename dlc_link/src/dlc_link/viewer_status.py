"""`StatusBlock` and the default no-op poller, split out of `dlc_link.viewer` to keep
that module under the project's 300-line production-file limit (same split precedent
as `dlc_link.live`/`live_cli`, plan 38-01). Re-exported from `dlc_link.viewer`
(`__all__` there includes `StatusBlock`), so this split is an implementation detail --
callers import from `dlc_link.viewer` either way.
"""
import time

from dlc_link.pilot_state import RunIdentity, StateReading


class _NullPoller:
    """Default poller when none is injected: immediately unavailable, naming the fact
    that no pilot/orchestrator/ES config was given -- never attempts a network call.
    'The viewer must be useful with no backend reachable at all' (plan interfaces)."""

    def fetch_run_identity(self):
        return RunIdentity(available=False, reason="not configured")

    def fetch_fda_state(self, subject_key):
        return StateReading(available=False, reason="not configured")


class StatusBlock:
    """Accumulates counts and readings and renders them as short strings (D-57).

    `stale_state` covers exactly one thing: the poller has not succeeded even once
    since the viewer started. It never renders a previously-fetched FDA state as
    current -- `pilot_state.StateReading` never caches one, and every poll round
    replaces whatever reading was here before, available or not.
    """

    def __init__(self, source_description="", clock=time.monotonic):
        self.source_description = source_description
        self._clock = clock
        self._started_at = clock()
        self.frames_read = 0
        self.frames_inferred = 0
        self.frames_skipped = 0
        self.observer_errors = 0
        self.render_errors = 0
        self._run_identity = None
        self._state_reading = None
        self._state_ever_available = False

    @property
    def stale_state(self):
        return not self._state_ever_available

    def update_frame_counts(self, frames_read, frames_inferred, frames_skipped, observer_errors, render_errors):
        self.frames_read = frames_read
        self.frames_inferred = frames_inferred
        self.frames_skipped = frames_skipped
        self.observer_errors = observer_errors
        self.render_errors = render_errors

    def update_run_identity(self, identity):
        self._run_identity = identity

    def update_state_reading(self, reading):
        self._state_reading = reading
        if reading is not None and reading.available:
            self._state_ever_available = True

    def lines(self):
        elapsed = self._clock() - self._started_at
        out = [
            "source: {}".format(self.source_description),
            "frames read: {}  rendered: {}  skipped: {}".format(
                self.frames_read, self.frames_inferred, self.frames_skipped
            ),
        ]
        if elapsed > 0:
            out.append(
                "rate: {:.2f} read/s, {:.2f} rendered/s".format(
                    self.frames_read / elapsed, self.frames_inferred / elapsed
                )
            )
        out.append(
            "observer_errors: {}  render_errors: {}".format(self.observer_errors, self.render_errors)
        )

        identity = self._run_identity
        if identity is None:
            out.append("run: unavailable - not yet polled")
        elif not identity.available:
            out.append("run: unavailable - {}".format(identity.reason))
        elif identity.run_id is None:
            out.append("run: no active run")
        else:
            out.append(
                "run_id: {}  session_id: {}  subject_key: {}".format(
                    identity.run_id, identity.session_id, identity.subject_key
                )
            )

        if self.stale_state:
            out.append("FDA state: unavailable - not yet polled")
        else:
            out.append(self._state_reading.render())
        return out
