"""`dlc-link-live`'s argparse definition and its two argument-level validators, split
out of `dlc_link.live_cli` to keep that module under the project's 300-line
production-file limit (D-49, D-51, D-54, D-55). Re-exported from `dlc_link.live_cli`
(`__all__` there includes `build_parser` and `validate_connection_args`), so this split
is an implementation detail -- callers import from `dlc_link.live_cli` either way.
"""
import argparse


def build_parser():
    parser = argparse.ArgumentParser(
        prog="dlc-link-live",
        description=(
            "USER-RUN paced video-file or camera loop through a trained DeepLabCut "
            "model, pushing declared signals into a mics-link client. Writes NOTHING "
            "anywhere by default (D-47)."
        ),
    )
    parser.add_argument(
        "--source", default=None,
        help="a device index ('0'), a stream URL (rtsp://...), or a file path -- "
             "classified automatically and printed before the capture is constructed",
    )
    parser.add_argument(
        "--video", default=None,
        help="deprecated alias for --source, kept working because it appears in "
             "RUNBOOK.md and researcher shell history (D-49). Giving both is an error.",
    )
    parser.add_argument(
        "--model-path", required=True,
        help="the .pt FILE produced by deeplabcut.export_model(...) -- NOT a directory "
             "and NOT the project directory (D-09)",
    )
    parser.add_argument("--signal-map", required=True, help="path to the generated <source_id>_signals.py")
    parser.add_argument("--host", default=None, help="required unless --dry-run, --probe-pose or --capture-only")
    parser.add_argument(
        "--port", type=int, default=None,
        help="required unless --dry-run, --probe-pose or --capture-only. Deliberately "
             "has NO default: the port belongs to a (pilot, source_id) row in "
             "pilot_hardware_config, not to this tool. Pilot 3 binds 5599 (ExtlinkDemo) "
             "and 5601 (dlc_cam1), so a wrong port reaches a DIFFERENT fixture that is "
             "listening rather than failing.",
    )
    parser.add_argument("--source-id", default=None, help="defaults to the loaded signal map's SOURCE_ID")
    parser.add_argument("--resize", type=float, default=None, help="passed to DLCLive")
    parser.add_argument("--max-frames", type=int, default=None)
    parser.add_argument(
        "--max-seconds", type=float, default=None,
        help="stop after this many seconds measured from the loop's own start -- the "
             "notebook-friendly bounded run (D-55)",
    )
    parser.add_argument(
        "--fps", type=float, default=None,
        help="override a FILE source's reported fps. Refused for a device/stream "
             "source -- see --min-rate (D-51)",
    )
    parser.add_argument(
        "--min-rate", type=float, default=None,
        help="frames/second threshold below which the run exits non-zero. Deliberately "
             "has NO default: the value comes from the researcher's own --capture-only "
             "baseline, never invented by this tool (D-54).",
    )
    parser.add_argument(
        "--read-retries", type=int, default=5,
        help="consecutive camera read failures tolerated before the run gives up. "
             "Applies to device/stream sources only -- a file's failed read is "
             "end-of-stream and ends the run on the first failure (D-55).",
    )
    parser.add_argument(
        "--capture-only", action="store_true",
        help="read frames and infer nothing, so a camera's own delivered rate can be "
             "measured without the model -- the --min-rate baseline (D-54). Needs no "
             "--host/--port.",
    )
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
    if args.dry_run or args.probe_pose or args.capture_only:
        return None
    missing = [name for name in ("host", "port") if getattr(args, name) is None]
    if not missing:
        return None
    return "{} required unless --dry-run, --probe-pose or --capture-only".format(
        " and ".join("--" + name for name in missing)
    )


def resolve_source(args):
    """Returns `(problem, value)`. `--source` and `--video` are the same idea under two
    names (D-49); giving both is ambiguous, giving neither leaves nothing to open."""
    if args.source is not None and args.video is not None:
        return "--source and --video may not both be given", None
    value = args.source if args.source is not None else args.video
    if value is None:
        return "--source (or its alias --video) is required", None
    return None, value
