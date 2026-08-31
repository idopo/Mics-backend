"""The paced video-file loop and the dlc-link-live CLI (D-29, D-30, D-42, D-47).

`run_video_loop` IS the live pipeline with a file substituted for a camera: pacing at the
video's native fps is what makes `stale_after_ms` exercised on the same timebase a real
camera will produce later. `cv2` and `dlclive` are imported ONLY inside `main()` (and
`--probe-pose`'s helper), never at module scope, so this module and its pure functions
(`run_video_loop`, `compare_pose_order`, `check_corner_geometry`) stay importable and
testable with neither library installed.

**D-47: this tool writes NOTHING, anywhere, by default.** No log file, no stats file, no
cache, no DLC-Live output artefact, no temporary file beside the video or the model.
Every count goes to stdout. `DLCLive(..., display=False)` is pinned explicitly at the
call site (never left to its own default) because the researcher's shell sits INSIDE
their read-only DeepLabCut project directory (D-44) -- anything this tool wrote
relative to the current working directory would land there. Of the documented
`DLCLive.__init__` arguments, `display` is the only one capable of showing, saving,
caching or exporting anything; `display_radius`/`display_cmap` are cosmetic and inert
once `display=False`. No `--write-*` flag ships; if one is ever added, its target must be
refused inside the model's or the video's directory, the same way `dlc_link.generate`
refuses `--out-dir` (D-46).
"""
import argparse
import sys
import time

from mics_link import Pacer, connect
from mics_link.errors import MicsLinkError

from dlc_link.processor import DLCProcessor
from dlc_link.signal_map import SignalMapError, assert_pairs_with, load_signal_map

__all__ = ["run_video_loop", "main", "compare_pose_order", "check_corner_geometry"]

_CORNERS = ("NW", "NE", "SE", "SW")


def run_video_loop(link, frames, infer, processor, pacer, fps, max_frames=None):
    """Drive `infer(frame)` once per frame from `frames`, paced at `fps`. `link` is
    accepted for lifecycle parity with the caller's `with connect(...)` block but is
    NEVER touched here -- `processor` (which already owns `link`) is what actually sends.
    Returns a counts-only record: `frames_read`, `frames_inferred`, `behind_count` (from
    `pacer`), and `processor.snapshot()`. Never creates or closes `link`.
    """
    frames_read = 0
    frames_inferred = 0
    for frame in frames:
        if max_frames is not None and frames_read >= max_frames:
            break
        frames_read += 1
        # D-29: dropping this ONE line is the entire change required to swap in a
        # live camera later -- everything else in this loop is identical either way.
        pacer.wait_until(frames_read / fps)
        infer(frame)
        frames_inferred += 1
    return {
        "frames_read": frames_read,
        "frames_inferred": frames_inferred,
        "behind_count": pacer.behind_count(),
        "processor_snapshot": processor.snapshot(),
    }


def compare_pose_order(expected_order, observed_order):
    """Pure. `expected_order` is the signal map's `POSE_ORDER`; `observed_order` is
    whatever ordering `--probe-pose` discovered on the constructed `DLCLive` runner (or
    `None` when nothing was found). Returns `(verdict, message)`, verdict one of
    `"match"`, `"mismatch"`, `"ordering-not-discoverable"`.
    """
    if observed_order is None:
        return (
            "ordering-not-discoverable",
            "no bodypart-ordering attribute was found on the constructed DLCLive runner",
        )
    if list(expected_order) == list(observed_order):
        return "match", "POSE_ORDER matches the discovered ordering ({} entries)".format(
            len(observed_order)
        )
    if len(expected_order) != len(observed_order):
        return "mismatch", "row count differs: POSE_ORDER has {}, discovered has {}".format(
            len(expected_order), len(observed_order)
        )
    return "mismatch", "same length ({}) but different order".format(len(expected_order))


def check_corner_geometry(positions, likelihoods, margin, min_likelihood):
    """Pure geometric ordering check (T-35-16c): the four arena corners must land in
    their own quadrants, in normalised image coordinates with y increasing DOWNWARD.
    `positions`: `{"NW": (x, y), ...}`. `likelihoods`: `{"NW": float, ...}`. Returns
    `(verdict, message)`; verdict is exactly one of `PASS`/`FAIL`/`UNRELIABLE`/
    `UNAVAILABLE`.

    LIMIT, stated here and in `--probe-pose`'s printed output: this pins the ordering at
    four positions. A permutation that leaves all four corners in place but swaps two
    OTHER parts (LED_on with LED_off, say) still passes it. Plan 35-07 Task 3's
    independent temporal check against the operator's own LED actions is the complement,
    not a superset -- neither check subsumes the other.
    """
    missing = [c for c in _CORNERS if c not in positions or c not in likelihoods]
    if missing:
        return "UNAVAILABLE", "corner(s) not resolved against the discovered pose order: {}".format(
            missing
        )

    unreliable = [c for c in _CORNERS if likelihoods[c] < min_likelihood]
    if unreliable:
        details = ", ".join("{}={!r}".format(c, likelihoods[c]) for c in unreliable)
        return "UNRELIABLE", (
            "corner(s) below --geometry-min-likelihood={}: {} -- this is NOT a pass and "
            "NOT an ordering failure; the corners were not detected confidently enough "
            "to test the ordering on this frame. Re-run with --geometry-frames 30 or a "
            "different video segment.".format(min_likelihood, details)
        )

    nw, ne, se, sw = positions["NW"], positions["NE"], positions["SE"], positions["SW"]
    checks = [
        ("NW.x < NE.x", ne[0] - nw[0]),
        ("SW.x < SE.x", se[0] - sw[0]),
        ("NW.y < SW.y", sw[1] - nw[1]),
        ("NE.y < SE.y", se[1] - ne[1]),
    ]
    failures = [
        "{} holds by {:.4f}, needs >= {:.4f} margin".format(label, diff, margin)
        for label, diff in checks
        if diff < margin
    ]
    if failures:
        return "FAIL", "; ".join(failures)
    return "PASS", "all four corner inequalities hold with margin >= {}".format(margin)


class _DiscardingLink:
    """--dry-run stand-in: counts and discards every send, connects to nothing."""

    def send_signal(self, name, value):
        return True


def _build_parser():
    parser = argparse.ArgumentParser(
        prog="dlc-link-live",
        description=(
            "USER-RUN paced video-file loop through a trained DeepLabCut model, pushing "
            "declared signals into a mics-link client. Writes NOTHING anywhere by "
            "default (D-47)."
        ),
    )
    parser.add_argument("--video", required=True, help="path to the prerecorded video (D-29 workflow A)")
    parser.add_argument(
        "--model-path", required=True,
        help="the .pt FILE produced by deeplabcut.export_model(...) -- NOT a directory "
             "and NOT the project directory (D-09)",
    )
    parser.add_argument("--signal-map", required=True, help="path to the generated <source_id>_signals.py")
    parser.add_argument("--host", default=None, help="required unless --dry-run or --probe-pose")
    parser.add_argument(
        "--port", type=int, default=None,
        help="required unless --dry-run or --probe-pose. Deliberately has NO default: "
             "the port belongs to a (pilot, source_id) row in pilot_hardware_config, not "
             "to this tool. Pilot 3 binds 5599 (ExtlinkDemo) and 5601 (dlc_cam1), so a "
             "wrong port reaches a DIFFERENT fixture that is listening rather than failing.",
    )
    parser.add_argument("--source-id", default=None, help="defaults to the loaded signal map's SOURCE_ID")
    parser.add_argument("--resize", type=float, default=None, help="passed to DLCLive")
    parser.add_argument("--max-frames", type=int, default=None)
    parser.add_argument("--fps", type=float, default=None, help="override the video's reported fps")
    parser.add_argument(
        "--verify-lib", default=None, metavar="PATH",
        help="assert the signal map pairs with this lib source before connecting",
    )
    parser.add_argument(
        "--dry-run", action="store_true",
        help="run the loop with a link that counts and discards; connects to nothing",
    )
    parser.add_argument(
        "--probe-pose", action="store_true",
        help="D-42's probe: read the first frame, run inference once, print pose.shape "
             "and bodypart ordering, run the corner-geometry check, then exit. Never "
             "connects to the Pi and sends nothing -- needs no --host.",
    )
    parser.add_argument("--geometry-parts", default="NW,NE,SE,SW")
    parser.add_argument("--geometry-frames", type=int, default=1, help="use 30 when a corner is marginal")
    parser.add_argument("--geometry-margin", type=float, default=0.05)
    parser.add_argument("--geometry-min-likelihood", type=float, default=0.5)
    return parser


def validate_connection_args(args):
    """Return a problem string when the run will connect but cannot address a socket.

    Checked before the heavy cv2/dlclive imports so a missing flag reports in
    milliseconds rather than after a model load -- and so it is testable on a host
    with neither installed.
    """
    if args.dry_run or args.probe_pose:
        return None
    missing = [name for name in ("host", "port") if getattr(args, name) is None]
    if not missing:
        return None
    return "{} required unless --dry-run or --probe-pose".format(
        " and ".join("--" + name for name in missing)
    )


def main(argv=None):
    args = _build_parser().parse_args(argv)

    problem = validate_connection_args(args)
    if problem:
        print("dlc-link-live: {}".format(problem), file=sys.stderr)
        return 2

    try:
        smap = load_signal_map(args.signal_map)
    except SignalMapError as exc:
        print("dlc-link-live: {}".format(exc), file=sys.stderr)
        return 1

    if args.verify_lib:
        with open(args.verify_lib) as handle:
            lib_source = handle.read()
        try:
            assert_pairs_with(smap, lib_source)
        except SignalMapError as exc:
            print("dlc-link-live: --verify-lib failed: {}".format(exc), file=sys.stderr)
            return 1

    import cv2  # deferred: dlc_link.live must import with no camera library installed
    from dlclive import DLCLive

    cap = cv2.VideoCapture(args.video)
    ok, first_frame = cap.read()
    if not ok:
        print("dlc-link-live: could not read the first frame of {}".format(args.video), file=sys.stderr)
        return 1

    width = cap.get(cv2.CAP_PROP_FRAME_WIDTH)
    height = cap.get(cv2.CAP_PROP_FRAME_HEIGHT)
    fps = args.fps or cap.get(cv2.CAP_PROP_FPS)
    if args.resize:
        width *= args.resize
        height *= args.resize

    if args.probe_pose:
        # Lazy import: dlc_link.live_probe imports compare_pose_order/check_corner_geometry
        # FROM this module, so importing it at module scope here would be circular.
        from dlc_link.live_probe import run_probe_pose

        return run_probe_pose(args, smap, DLCLive, cap, first_frame, width, height)

    source_id = args.source_id or smap.SOURCE_ID
    if args.dry_run:
        link = _DiscardingLink()
    else:
        # host/port already validated by validate_connection_args() before any import.
        try:
            link = connect(args.host, args.port, source_id)
        except MicsLinkError as exc:
            print("dlc-link-live: {}".format(exc), file=sys.stderr)
            return 1

    processor = DLCProcessor(link, smap, frame_width=width, frame_height=height)
    live = DLCLive(
        args.model_path,
        model_type="pytorch",  # D-01/D-02: this project is a PyTorch export.
        single_animal=True,  # D-07: refused-3-D is enforced downstream by DLCProcessor.
        processor=processor,
        resize=args.resize,
        display=False,  # D-47: pinned explicitly, never left to DLCLive's own default.
    )
    live.init_inference(first_frame)

    pacer = Pacer("realtime")
    pacer.start()
    remaining_frames = [first_frame]

    def _frames():
        while remaining_frames:
            yield remaining_frames.pop()
        while True:
            ok, frame = cap.read()
            if not ok:
                return
            yield frame

    start = time.monotonic()
    try:
        result = run_video_loop(
            link, _frames(), lambda frame: live.get_pose(frame), processor, pacer, fps,
            max_frames=args.max_frames,
        )
    finally:
        live.close()
        cap.release()
    duration_s = time.monotonic() - start

    print("dlc-link-live summary:")
    print("  frames_read:     {}".format(result["frames_read"]))
    print("  frames_inferred: {}".format(result["frames_inferred"]))
    print("  behind_count:    {}".format(result["behind_count"]))
    print("  processor:       {}".format(result["processor_snapshot"]))
    if not args.dry_run:
        print("  link.stats:      {}".format(link.stats.snapshot()))
        link.close()
    print("  duration_s:      {:.3f}".format(duration_s))
    print(
        "  reminder: start this sender BEFORE the run when the pilot's config row has "
        "required: true, and AFTER the run when it has required: false (D-27) -- pilot "
        "3's row is required: false, so the correct order there is run first, then "
        "sender."
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
