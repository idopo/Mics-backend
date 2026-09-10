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
    # Not argparse-required: --capture-only loads no model and builds no processor
    # (live_cli.py's _build_processor_and_infer returns live=None), so demanding either
    # path would force two values that are never read just to measure D-54's baseline.
    # validate_connection_args enforces them for every mode that DOES read them.
    parser.add_argument(
        "--model-path", default=None,
        help="the .pt FILE produced by deeplabcut.export_model(...) -- NOT a directory "
             "and NOT the project directory (D-09). Required unless --capture-only",
    )
    parser.add_argument(
        "--signal-map", default=None,
        help="path to the generated <source_id>_signals.py. Required unless "
             "--capture-only or --probe-pose",
    )
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
    parser.add_argument(
        "--view", action="store_true",
        help="render annotated frames in a notebook or a localhost browser (D-56). "
             "Off by default -- a headless run must stay exactly as cheap as it is "
             "today; starts no extra thread when absent.",
    )
    parser.add_argument(
        "--view-sink", choices=("notebook", "mjpeg"), default="notebook",
        help="where the annotated view is rendered (D-58): 'notebook' needs IPython; "
             "'mjpeg' needs nothing installed and opens in any browser on this machine.",
    )
    parser.add_argument(
        "--view-port", type=int, default=None,
        help="required when --view-sink mjpeg is chosen. Deliberately has NO default, "
             "for the same reason --port has none: a port that is open but wrong is "
             "more expensive to debug than one that is closed.",
    )
    parser.add_argument(
        "--view-min-likelihood", type=float, default=None,
        help="required with --view. The value comes from the researcher's own "
             "measured likelihood distribution (D-41, 35-HARDWARE-VALIDATION.md §5b) "
             "-- this tool refuses to invent one.",
    )
    parser.add_argument(
        "--overlay", default=None,
        help="researcher-authored threshold clauses, e.g. "
             "'nose_x>0.50,nose_likelihood>0.6' (D-60). Parsed before any heavy "
             "import, so a typo'd signal name fails in milliseconds and lists the "
             "declared names. Labelled on every frame as authored locally, never the "
             "FDA's own ground truth.",
    )
    parser.add_argument("--pilot", default=None, help="the pilot name as the orchestrator keys it, e.g. 'RecordingBox'")
    parser.add_argument("--orchestrator-url", default=None, help="e.g. http://<orchestrator-host>:9000")
    parser.add_argument("--es-url", default=None, help="e.g. http://<elasticsearch-host>:9200")
    parser.add_argument("--es-index", default="event_log_v2")
    return parser


def validate_view_args(args):
    """Return a problem string when `--view`'s flags are inconsistent. Checked before
    the heavy cv2/dlclive imports, same reason as `validate_connection_args`.

    `--view-sink mjpeg` is checked whenever it was chosen, regardless of `--view`
    itself -- choosing a sink and then forgetting the port it needs is a mistake worth
    catching immediately rather than only once `--view` is also added.
    """
    if args.view_sink == "mjpeg" and args.view_port is None:
        return "--view-port is required when --view-sink mjpeg is chosen"
    if args.view and args.view_min_likelihood is None:
        return "--view-min-likelihood is required with --view"
    return None


def validate_connection_args(args):
    """Return a problem string when the run will connect but cannot address a socket.

    Checked before the heavy cv2/dlclive imports so a missing flag reports in
    milliseconds rather than after a model load -- and so it is testable on a host
    with neither installed.
    """
    # --capture-only reads neither path; --probe-pose loads the model but needs no map.
    if not args.capture_only:
        needed = ["model_path"] if args.probe_pose else ["model_path", "signal_map"]
        absent = [n for n in needed if getattr(args, n) is None]
        if absent:
            return "{} required unless --capture-only".format(
                " and ".join("--" + n.replace("_", "-") for n in absent)
            )

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
