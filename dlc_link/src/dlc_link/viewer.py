"""`Viewer` -- three threads, one `LatestSlot` each way, no path back to the sender
(D-56, D-57; the rule that outranks every other goal in this plan).

`push(frame, pose)` runs on DLC's own inference thread, inside `get_pose()` ->
`_post_process_pose()` (`dlc_link.processor.DLCProcessor.process`, `processor.py:25-32`)
-- a raise there stops inference on the researcher's machine mid-experiment. So `push`
does exactly one thing: a non-blocking `LatestSlot.put`. Drawing, encoding, HTTP and
state polling all happen on two OTHER threads this class owns, so a slow, absent or
crashed viewer changes nothing about what the sender sends.

**No `cv2` import at module scope.** The render backend and the JPEG encoder are both
built lazily, inside a function, exactly as `dlc_link.live` defers its imports -- this
module and its tests import and run on a host with no cv2 and no IPython.

`StatusBlock` and the default no-op poller live in `dlc_link.viewer_status` (split out
to keep this module under the project's 300-line limit, same precedent as
`dlc_link.live`/`live_cli`) and are re-exported here.
"""
import threading
import time

from dlc_link.annotate import build_draw_plan
from dlc_link.latest import LatestSlot
from dlc_link.pilot_state import RunIdentity, StateReading
from dlc_link.viewer_status import StatusBlock, _NullPoller

__all__ = ["Viewer", "render_primitives", "StatusBlock"]

# How long the render thread sleeps when the frame slot is empty. Not a per-frame
# timing figure -- never measured, printed or returned, only slept. Same idiom as
# `dlc_link.live_sources._SLOT_POLL_INTERVAL_S`.
_RENDER_POLL_INTERVAL_S = 0.01


def render_primitives(frame, primitives, backend):
    """Dispatch each primitive, in the order given, to `backend.circle` / `.text` /
    `.line`. An unknown `kind` is counted, never raised on. Pure dispatch -- no drawing
    math lives here, that is `dlc_link.annotate`. A backend that raises propagates to
    the caller, which is how the render loop counts a whole frame as one `render_errors`."""
    counts = {"circle": 0, "text": 0, "line": 0, "unknown": 0}
    for primitive in primitives:
        if primitive.kind == "circle":
            backend.circle(frame, primitive.center, primitive.radius, primitive.color, primitive.thickness)
            counts["circle"] += 1
        elif primitive.kind == "text":
            backend.text(frame, primitive.text, primitive.position, primitive.color)
            counts["text"] += 1
        elif primitive.kind == "line":
            backend.line(frame, primitive.start, primitive.end, primitive.color)
            counts["line"] += 1
        else:
            counts["unknown"] += 1
    return counts


def _cv2_backend():
    """Imports `cv2` inside this function -- never at module scope. cv2's interactive
    window-display call does not exist in `opencv-python-headless` and is not what
    this package renders through; installing `opencv-python` beside it would clobber
    the DLC stack's own build (D-58)."""
    import cv2

    class _Cv2Backend:
        def circle(self, frame, center, radius, color, thickness):
            cv2.circle(frame, center, radius, color or (255, 255, 255), thickness)

        def text(self, frame, text, position, color):
            cv2.putText(
                frame, text, position, cv2.FONT_HERSHEY_SIMPLEX, 0.4, color or (255, 255, 255), 1,
            )

        def line(self, frame, start, end, color):
            cv2.line(frame, start, end, color or (255, 255, 255), 1)

    return _Cv2Backend()


def _default_encoder():
    """Imports `cv2` inside this function, returning a callable `(frame, quality) ->
    (ok, bytes)` around `cv2.imencode` -- the only encoder this package ever uses."""
    import cv2

    def _encode(frame, quality):
        ok, buf = cv2.imencode(".jpg", frame, [int(cv2.IMWRITE_JPEG_QUALITY), quality])
        if not ok:
            return False, None
        return True, buf.tobytes()

    return _encode


class Viewer:
    """Frames and poses become annotated JPEG bytes on threads the sender never waits
    for. `signal_map`/`frame_width`/`frame_height`/`min_likelihood` drive
    `annotate.build_draw_plan` exactly as the processor's own pixel convention does
    (`processor.py:105-116`); `overlay_clauses` is the researcher's own authored
    threshold set (D-60); `poller` is an object exposing `fetch_run_identity()` and
    `fetch_fda_state(subject_key)`, pre-bound to whatever URLs the caller configured
    (or `None`, meaning nothing is configured); `backend`/`encoder` default to cv2,
    built lazily so this class imports with no cv2 installed; `sink`, when given, is
    notified with `.update()` after every successful render -- a convenience push on
    top of the pull model both sinks also support by reading `Viewer`'s own slots.
    """

    def __init__(
        self,
        signal_map,
        frame_width,
        frame_height,
        min_likelihood,
        overlay_clauses=None,
        poller=None,
        backend=None,
        encoder=None,
        sink=None,
        jpeg_quality=70,
        poll_interval_s=1.0,
        source_description="",
        sleep=time.sleep,
    ):
        self._signal_map = signal_map
        self._frame_width = frame_width
        self._frame_height = frame_height
        self._min_likelihood = min_likelihood
        self._overlay_clauses = overlay_clauses
        self._poller = poller or _NullPoller()
        self._backend = backend
        self._encoder = encoder
        self._sink = sink
        self._jpeg_quality = jpeg_quality
        self._poll_interval_s = poll_interval_s
        self._sleep = sleep

        self._frames = LatestSlot()
        self._jpeg = LatestSlot()
        self.status = StatusBlock(source_description)

        self.push_errors = 0
        self.render_errors = 0
        self.encode_errors = 0
        self._frames_rendered = 0

        self._stop_flag = threading.Event()
        self._render_thread = None
        self._poll_thread = None
        self._started = False

    def push(self, frame, pose):
        """The ENTIRE hot-path body. No encoding, no drawing, no network -- a single
        non-blocking `LatestSlot.put`. Wrapped in a bare `try/except` anyway so a
        pathological input can never reach DLC's inference thread as an exception."""
        try:
            self._frames.put((frame, pose))
        except Exception:
            self.push_errors += 1

    def start(self):
        if self._started:
            return
        self._started = True
        self._render_thread = threading.Thread(target=self._render_loop, daemon=True)
        self._poll_thread = threading.Thread(target=self._poll_loop, daemon=True)
        self._render_thread.start()
        self._poll_thread.start()

    def stop(self):
        """Idempotent; safe before `start()`; joins both threads within a bounded
        number of iterations."""
        self._stop_flag.set()
        if self._render_thread is not None:
            self._render_thread.join(timeout=2.0)
        if self._poll_thread is not None:
            self._poll_thread.join(timeout=2.0)

    def snapshot(self):
        """Counts only: no duration, no per-frame timing, nothing readable as a
        latency, anywhere in this dict (DLC-10, carried)."""
        return {
            "push_errors": self.push_errors,
            "render_errors": self.render_errors,
            "encode_errors": self.encode_errors,
            "frames": self._frames.snapshot(),
            "jpeg": self._jpeg.snapshot(),
        }

    def _overlay_values_from_pose(self, pose):
        """The `{signal_name: value}` dict the overlay's HOLDS verdict is computed
        from -- the SAME normalised numbers `DLCProcessor.process` sends over the wire
        (`processor.py:110-111`), never re-derived differently here."""
        if not self._overlay_clauses:
            return None
        values = {}
        for entry in self._signal_map.SIGNALS.values():
            index = entry["index"]
            if index >= len(pose):
                continue
            row = pose[index]
            values[entry["signals"]["likelihood"]] = row[2]
            if entry["coords"]:
                values[entry["signals"]["x"]] = row[0] / self._frame_width
                values[entry["signals"]["y"]] = row[1] / self._frame_height
        return values

    def _publish_status(self):
        snap = self._frames.snapshot()
        self.status.update_frame_counts(
            frames_read=snap["puts"],
            frames_inferred=self._frames_rendered,
            frames_skipped=snap["overwrites"],
            observer_errors=self.push_errors,
            render_errors=self.render_errors,
        )

    def _render_loop(self):
        backend = self._backend or _cv2_backend()
        encoder = self._encoder or _default_encoder()
        while not self._stop_flag.is_set():
            got, item = self._frames.take()
            if not got:
                self._sleep(_RENDER_POLL_INTERVAL_S)
                self._publish_status()
                continue

            frame, pose = item
            try:
                # DLCLive reuses buffers: drawing into a frame inference may still
                # reference is how a viewer silently corrupts the thing it observes
                # (T-38-24). If the copy is unaffordable, drop more frames -- never
                # draw in place.
                drawn = frame.copy()
                overlay_values = self._overlay_values_from_pose(pose)
                plan = build_draw_plan(
                    pose, self._signal_map, self._frame_width, self._frame_height,
                    self._min_likelihood, overlay_clauses=self._overlay_clauses,
                    overlay_values=overlay_values,
                )
                render_primitives(drawn, plan.primitives, backend)
            except Exception:
                self.render_errors += 1
                self._publish_status()
                continue

            try:
                ok, jpeg_bytes = encoder(drawn, self._jpeg_quality)
            except Exception:
                ok, jpeg_bytes = False, None
            if not ok:
                self.encode_errors += 1
                self._publish_status()
                continue

            self._jpeg.put(jpeg_bytes)
            self._frames_rendered += 1
            if self._sink is not None:
                try:
                    self._sink.update()
                except Exception:
                    pass
            self._publish_status()

    def _poll_loop(self):
        while not self._stop_flag.is_set():
            try:
                identity = self._poller.fetch_run_identity()
            except Exception as exc:
                identity = RunIdentity(available=False, reason="{}: {}".format(type(exc).__name__, exc))
            self.status.update_run_identity(identity)

            if identity.available and identity.subject_key:
                try:
                    state = self._poller.fetch_fda_state(identity.subject_key)
                except Exception as exc:
                    state = StateReading(available=False, reason="{}: {}".format(type(exc).__name__, exc))
            else:
                # No active run: there is no subject to query, so the state is
                # unavailable for THIS poll round -- a stale value from a past run
                # must not keep showing as current (D-57).
                state = StateReading(available=False, reason="no active run")
            self.status.update_state_reading(state)

            self._sleep(self._poll_interval_s)
