"""Source-specific capture setup and summary printing for `dlc-link-live`, split out of
`dlc_link.live_cli` to keep that module under the project's 300-line production-file
limit (D-51, D-52, D-53, D-54, D-55).

`cv2` is NEVER imported here at module scope -- `_open_file_source`/`_open_camera_source`
receive the already-imported `cv2` module from `dlc_link.live_cli.main`, which has done
that deferred import after all validation has passed.

Two small stand-ins live here too: `_DiscardingLink` (`--dry-run`) and `_NoOpProcessor`
plus `_no_op_infer` (`--capture-only`, D-54's baseline measurement -- no model loaded).
"""
import time

from dlc_link.capture import FrameReader
from dlc_link.latest import LatestSlot
from dlc_link.source import read_failure_is_terminal

# How long the camera frame generator sleeps between LatestSlot polls when the slot is
# empty. Short enough that a fast model is never starved waiting on this loop; not a
# per-frame timing figure -- it is never measured, printed or returned, only slept.
_SLOT_POLL_INTERVAL_S = 0.005


class _DiscardingLink:
    """--dry-run stand-in: counts and discards every send, connects to nothing."""

    def send_signal(self, name, value):
        return True


class _NoOpProcessor:
    """--capture-only stand-in: no signal map, no decimator, nothing sent. Counts
    only, per the DLC-10 rule every `snapshot()` in this package follows."""

    def snapshot(self):
        return {"frames": 0}


def _no_op_infer(frame):
    """--capture-only's `infer`: no model is loaded (D-54's baseline measurement)."""
    return None


def open_file_source(cv2, spec, args):
    """File source: today's path exactly -- synchronous generator, `fps` from
    `--fps` or the driver's own report. Returns `(cap, opened, error)`; `opened` is
    `(first_frame, fps, slot, reader, frames)` with `slot`/`reader` both `None`."""
    cap = cv2.VideoCapture(spec.capture_arg)
    ok, first_frame = cap.read()
    if not ok:
        return cap, None, "could not read the first frame of {}".format(spec.describe())
    fps = args.fps or cap.get(cv2.CAP_PROP_FPS)

    def _frames():
        yield first_frame
        while True:
            ok, frame = cap.read()
            if not ok:
                return
            yield frame

    return cap, (first_frame, fps, None, None, _frames()), None


def open_camera_source(cv2, spec, args):
    """Device/stream source: a `FrameReader` thread fills a `LatestSlot`; the frame
    generator takes from the slot, sleeping briefly when it is empty, and ends only
    once the reader has stopped AND the slot has been drained. `fps` is always `None`
    here -- this tool never paces a camera (D-51)."""
    cap = cv2.VideoCapture(spec.capture_arg)
    requested = cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)
    print("dlc-link-live: CAP_PROP_BUFFERSIZE requested=1 (set() returned {!r}), now={!r} "
          "(requested 1; many backends ignore this)".format(requested, cap.get(cv2.CAP_PROP_BUFFERSIZE)))
    print("dlc-link-live: CAP_PROP_FPS reported by the driver: {!r} -- NOT trusted and NOT "
          "used".format(cap.get(cv2.CAP_PROP_FPS)))

    ok, first_frame = cap.read()
    if not ok:
        return cap, None, "could not read the first frame of {}".format(spec.describe())

    slot = LatestSlot()
    reader = FrameReader(cap.read, slot, terminal_on_failure=read_failure_is_terminal(spec.kind),
                          read_retries=args.read_retries)
    reader.start()

    def _frames():
        yield first_frame
        while True:
            got, frame = slot.take()
            if got:
                yield frame
                continue
            if not reader.is_alive():
                got, frame = slot.take()
                if got:
                    yield frame
                return
            time.sleep(_SLOT_POLL_INTERVAL_S)

    return cap, (first_frame, None, slot, reader, _frames()), None


def print_summary(result, spec, duration_s, slot, reader, stopped_reason):
    """Prints counts and rates only -- no per-frame timing figure of any kind anywhere
    (DLC-10). `behind_count` prints `n/a (unpaced source)` rather than a structural
    zero (D-53); `frames_skipped` is the slot's `overwrites`, or `0` for a file."""
    behind_count = result["behind_count"]
    frames_skipped = slot.snapshot()["overwrites"] if slot is not None else 0
    print("dlc-link-live summary:")
    print("  source:          {}".format(spec.describe()))
    print("  frames_read:     {}".format(result["frames_read"]))
    print("  frames_inferred: {}".format(result["frames_inferred"]))
    print("  behind_count:    {}".format("n/a (unpaced source)" if behind_count is None else behind_count))
    print("  frames_skipped:  {}".format(frames_skipped))
    if reader is not None:
        print("  reader:          {}".format(reader.snapshot()))
    print("  observer_errors: {}".format(result["observer_errors"]))
    print("  stopped_reason:  {}".format(stopped_reason))
    print("  processor:       {}".format(result["processor_snapshot"]))
    print("  duration_s:      {:.3f}".format(duration_s))
    if duration_s > 0 and isinstance(result["frames_inferred"], int):
        print("  rate_frames_inferred_per_s: {:.3f}".format(result["frames_inferred"] / duration_s))
        print("  rate_frames_read_per_s:     {:.3f}".format(result["frames_read"] / duration_s))
