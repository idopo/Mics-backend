"""DLCProcessor -- the dlclive-compatible callback that pushes declared signals into a
mics_link client (DLC-07, D-32..D-34).

**Base-class resolution is a deliberate testability seam, not a defensive accident.**
`from dlclive import Processor as _Base` is attempted at import time; when `dlclive` is
absent (every dev host in this repo, and any CI runner) `_Base` falls back to `object`
and `DLCLIVE_AVAILABLE` is `False`. `DLCProcessor.__init__` calls `super().__init__()`
unconditionally, which is correct against either base -- `dlclive.Processor.__init__`
and `object.__init__` both accept zero arguments. This is what lets the whole adapter be
unit-tested with no dlclive, no camera library, no torch and no GPU installed.

**The client is injected, never constructed or closed here (rule 1, D-32).**
`dlclive.Processor` has no guaranteed teardown hook: `save()` is called by the DLC-Live
GUI, not by `DLCLive`, so a client created inside a `Processor`'s constructor might never
be closed. The caller builds `link` inside its own `with connect(...)` block
(`sdk/examples/callback_sender.py`'s rule 1) and hands it to `DLCProcessor(link, ...)`.

**Every pose value crosses the wire through `mics_link.values.as_scalar`, never a bare
Python numeric coercion (D-34).** Every pose value is a numpy scalar; `numpy.float64` IS
a `float` subclass, so an `isinstance` check lets it through only for msgpack to raise an
un-catchable `TypeError` on the IO thread later -- an invisible failure. `as_scalar`
(`.item()`) is the documented, opt-in conversion that preserves the int/bool/float
distinction instead of flattening it.

**`process()` never raises for a per-signal problem (T-35-14).** It runs synchronously on
DLC's own inference thread, inside `get_pose()` -> `_post_process_pose()`
(`self.pose = self.processor.process(self.pose, **kwargs)`) -- a raise here stops
inference on the researcher's own machine mid-experiment. `PoseShapeError` is the one
deliberate exception: it is a programming error (the caller passed the wrong pose shape,
or the signal map was generated against the wrong row order) that must be fixed once,
before the run means anything, never a runtime condition to recover from per-frame.
"""
from mics_link.errors import InvalidValueError
from mics_link.values import as_scalar

from dlc_link.decimate import RECOMMENDED_DEFAULTS, Decimator

try:
    from dlclive import Processor as _Base

    DLCLIVE_AVAILABLE = True
except ImportError:
    _Base = object
    DLCLIVE_AVAILABLE = False


class PoseShapeError(Exception):
    """Raised once, at the pose-shape guard -- never for a per-signal value problem."""


def _default_decimator(signal_map):
    """A `Decimator` seeded from `RECOMMENDED_DEFAULTS`, keyed by the map's REAL emitted
    signal names -- never a placeholder name, since the decimator's per-name state would
    otherwise never match what `process()` actually sends.
    """
    deadband = {}
    min_interval_ms = {}
    for entry in signal_map.SIGNALS.values():
        names = entry["signals"]
        deadband[names["likelihood"]] = RECOMMENDED_DEFAULTS["likelihood_deadband"]
        min_interval_ms[names["likelihood"]] = RECOMMENDED_DEFAULTS["min_interval_ms"]
        if entry["coords"]:
            for axis in ("x", "y"):
                deadband[names[axis]] = RECOMMENDED_DEFAULTS["coordinate_deadband"]
                min_interval_ms[names[axis]] = RECOMMENDED_DEFAULTS["min_interval_ms"]
    return Decimator(deadband=deadband, min_interval_ms=min_interval_ms)


class DLCProcessor(_Base):
    """A `dlclive.Processor` subclass (or a plain object when `dlclive` is absent) that
    reads `signal_map.SIGNALS` -- never re-derives a name -- and sends every declared
    bodypart's likelihood (always) and normalised x/y coordinates (when declared) through
    `link.send_signal`.
    """

    def __init__(self, link, signal_map, frame_width, frame_height, decimator=None, on_drop=None):
        super().__init__()
        self._link = link
        self._signal_map = signal_map
        self._frame_width = frame_width
        self._frame_height = frame_height
        self._on_drop = on_drop
        self._decimator = decimator if decimator is not None else _default_decimator(signal_map)

        self.frames = 0
        self.signals_considered = 0
        self.signals_sent = 0
        self.signals_dropped = 0
        self.signals_suppressed = 0
        self.out_of_frame = 0
        self.values_rejected = 0

        # D-42's row-count guard is a per-frame hot path; the expected length is computed
        # exactly once here, at construction, and never recomputed from POSE_ORDER again.
        self._expected_row_count = len(signal_map.POSE_ORDER)
        self._row_count_checked = False

    def process(self, pose, **kwargs):
        self.frames += 1
        self._check_rank(pose)
        if not self._row_count_checked:
            self._check_row_count(pose)
            self._row_count_checked = True

        for entry in self._signal_map.SIGNALS.values():
            row = pose[entry["index"]]
            likelihood = as_scalar(row[2])
            self._maybe_send(entry["signals"]["likelihood"], likelihood)
            if entry["coords"]:
                x = as_scalar(row[0]) / self._frame_width
                y = as_scalar(row[1]) / self._frame_height
                if not (0.0 <= x <= 1.0 and 0.0 <= y <= 1.0):
                    self.out_of_frame += 1
                self._maybe_send(entry["signals"]["x"], x)
                self._maybe_send(entry["signals"]["y"], y)

        return pose

    def _check_rank(self, pose):
        ndim = getattr(pose, "ndim", None)
        if ndim is None or ndim == 2:
            return
        raise PoseShapeError(
            "DLCProcessor requires single_animal=True: observed pose.ndim={} (shape "
            "{!r}). Multi-animal PyTorch models are fully supported by DLC-Live and "
            "(num_individuals, num_keypoints, 3) is a legitimate shape this adapter "
            "refuses BY CHOICE, not because the engine cannot produce it. This project "
            "sets identity: false with default_track_method='ellipse', so individual "
            "identity is assigned post-hoc by convert_detections2tracklets and "
            "stitch_tracklets -- a batch step DLC-Live never runs live -- so a "
            "per-individual signal would silently change which animal it refers to "
            "between frames. Pass single_animal=True to DLCLive(...).".format(
                ndim, getattr(pose, "shape", None)
            )
        )

    def _check_row_count(self, pose):
        row_count = len(pose)
        if row_count == self._expected_row_count:
            return
        message = (
            "pose row count {} does not match len(POSE_ORDER) {} -- every index in the "
            "signal map was taken from POSE_ORDER, so a length mismatch means the map's "
            "indices point at the wrong keypoints.".format(row_count, self._expected_row_count)
        )
        if getattr(self._signal_map, "POSE_ORDER_SOURCE", None) == "config-declared-UNVERIFIED":
            message += (
                " POSE_ORDER_SOURCE is 'config-declared-UNVERIFIED': run plan 35-07's "
                "probe (dlc-link-live --probe-pose) to settle the real row order before "
                "trusting this map."
            )
        raise PoseShapeError(message)

    def _maybe_send(self, name, value):
        self.signals_considered += 1
        if not self._decimator.should_send(name, value):
            self.signals_suppressed += 1
            return
        try:
            accepted = self._link.send_signal(name, value)
        except InvalidValueError:
            self.values_rejected += 1
            return
        if accepted:
            self.signals_sent += 1
        else:
            self.signals_dropped += 1
            if self._on_drop is not None:
                self._on_drop(name)

    def snapshot(self):
        """Counters only (frames/considered/sent/dropped/suppressed/out_of_frame/
        rejected) plus the decimator's own counts -- no duration, rate or per-frame
        timing figure anywhere (DLC-10). A frame lost at ZMQ's high-water mark is
        counted nowhere on the Pi, so this snapshot is the only end-to-end drop
        accounting that exists (D-21(ii))."""
        data = {
            "frames": self.frames,
            "signals_considered": self.signals_considered,
            "signals_sent": self.signals_sent,
            "signals_dropped": self.signals_dropped,
            "signals_suppressed": self.signals_suppressed,
            "out_of_frame": self.out_of_frame,
            "values_rejected": self.values_rejected,
        }
        data.update(self._decimator.stats.snapshot())
        return data

    def save(self, filename=None):
        """No-op returning True. Exists because the DLC-Live GUI calls `save()`;
        `DLCLive` itself never does. Deliberately does not touch `link` -- closing it
        here would violate rule 1 (the caller's `with connect(...)` block owns it)."""
        return True
