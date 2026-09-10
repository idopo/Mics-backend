"""LatestSlot -- a single-slot, drop-oldest holder that counts what it drops
(D-52, D-53).

The inference loop must always receive the NEWEST frame. With a plain in-loop
`cap.read()` and a backend that buffers, a slow model reads progressively older
frames: nothing is dropped, nothing is counted, and the Pi is fed the past while
everything looks healthy. `LatestSlot` is the fix: `put()` always replaces whatever is
there, and `overwrites` IS the count of frames the pipeline could not service. With a
file that number is zero by construction; with a camera it is the honest keep-up
instrument, and it exists because `behind_count` cannot be one for an unpaced source
(D-53).

Two consumers, stated here so nobody adds a third mechanism later: the camera reader
(`dlc_link.capture.FrameReader`, plan 38-01) and the viewer tap (plan 38-03).

DLC-10: no field on `snapshot()` may be added whose name or value could be read as a
per-frame timing figure of any kind -- the same rule `dlc_link.decimate.DecimateStats`
carries, applied here because this class is the camera-side analogue of it. Counts
only, always: `puts`, `takes`, `overwrites`.
"""
import threading

_NOTHING_YET = object()


class LatestSlot:
    """A single-slot, drop-oldest holder guarded by a `threading.Lock`."""

    def __init__(self):
        self._lock = threading.Lock()
        self._item = _NOTHING_YET
        self.puts = 0
        self.takes = 0
        self.overwrites = 0

    def put(self, item):
        """Replace whatever is in the slot. Never blocks, never raises. Increments
        `overwrites` when it replaced an item that had not yet been taken."""
        with self._lock:
            if self._item is not _NOTHING_YET:
                self.overwrites += 1
            self._item = item
            self.puts += 1

    def take(self):
        """Returns `(True, item)` when something new is waiting, `(False, None)`
        otherwise -- a second consecutive `take()` with no intervening `put()` reports
        "nothing new" rather than re-yielding the previous item."""
        with self._lock:
            if self._item is _NOTHING_YET:
                return False, None
            item = self._item
            self._item = _NOTHING_YET
            self.takes += 1
            return True, item

    def snapshot(self):
        """Exactly `{"puts", "takes", "overwrites"}` and nothing else."""
        return {"puts": self.puts, "takes": self.takes, "overwrites": self.overwrites}
