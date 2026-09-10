"""`dlc-link-live`'s argparse and `main()`, split out of `dlc_link.live` to keep that
module under the project's 300-line production-file limit (same split precedent as
`dlc_link.generate`/`generate_cli`, plan 35-03; D-49, D-51, D-54, D-55).

`cv2` and `dlclive` are imported ONLY inside `main()` (and `--probe-pose`'s helper),
never at module scope, so `main([...])` can be driven all the way to a validation
refusal -- a bad `--source`/`--fps` combination, a missing `--host` -- on a dev host
with neither installed, proving the refusal happens before the deferred import.

Source-specific capture setup and summary printing live in `dlc_link.live_sources`;
the argparse definition and its two argument-level validators live in
`dlc_link.live_cli_args` (a second and third split, for the same 300-line reason) and
are re-exported here so `dlc_link.live_cli.build_parser`/`validate_connection_args`
keep working for every caller -- the split is an implementation detail.

**D-47: this tool writes NOTHING, anywhere, by default.** `DLCLive(..., display=False)`
is pinned explicitly at its call site (never left to its own default) because the
researcher's shell sits INSIDE their read-only DeepLabCut project directory (D-44) --
anything this tool wrote relative to the current working directory would land there.
"""
import sys
import time

from mics_link import Pacer, connect
from mics_link.errors import MicsLinkError

from dlc_link import viewer_cli
from dlc_link.live import run_video_loop
from dlc_link.live_cli_args import (
    build_parser,
    resolve_source,
    validate_connection_args,
    validate_view_args,
)
from dlc_link.live_sources import (
    _DiscardingLink,
    _NoOpProcessor,
    _no_op_infer,
    open_camera_source,
    open_file_source,
    print_summary,
)
from dlc_link.processor import DLCProcessor
from dlc_link.signal_map import SignalMapError, assert_pairs_with, load_signal_map
from dlc_link.source import SourceError, classify_source, fps_refusal
from dlc_link.view_sinks import SinkError

__all__ = ["main", "build_parser", "validate_connection_args"]


def _build_processor_and_infer(args, spec, smap, width, height, first_frame, DLCLive):
    """Returns `(link, processor, live, infer)`. `live` is `None` for `--capture-only`
    (D-54's baseline: no model loaded). Lets `MicsLinkError` propagate -- the caller
    reports it and exits; host/port are already validated before this is reached."""
    if args.capture_only:
        return None, _NoOpProcessor(), None, _no_op_infer

    if args.dry_run:
        link = _DiscardingLink()
    else:
        link = connect(args.host, args.port, args.source_id or smap.SOURCE_ID)

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
    return link, processor, live, live.get_pose


def _run_and_close(link, frames, infer, processor, pacer, fps, args, cap, reader, live, viewer=None, sink=None):
    """Runs the loop, then ALWAYS stops the viewer and sink, the reader, `live`, and
    releases `cap` -- in that order, before a capture a thread is still reading is
    released (T-38-05) -- even on a `KeyboardInterrupt` (D-55)."""
    interrupted = False
    start = time.monotonic()
    try:
        try:
            result = run_video_loop(
                link, frames, infer, processor, pacer, fps, max_frames=args.max_frames,
                max_seconds=args.max_seconds, observer=viewer.push if viewer is not None else None,
            )
        except KeyboardInterrupt:
            interrupted = True
            result = {
                "frames_read": "n/a (interrupted)", "frames_inferred": "n/a (interrupted)",
                "behind_count": None if pacer is None else pacer.behind_count(),
                "observer_errors": 0, "processor_snapshot": processor.snapshot(),
            }
    finally:
        # D-56: the viewer and its sink never backpressure the sender, but they are
        # still stopped FIRST -- before the reader thread that feeds them.
        if viewer is not None:
            viewer.stop()
        if sink is not None:
            sink.stop()
        if reader is not None:
            reader.stop()
        if live is not None:
            live.close()
        cap.release()
    duration_s = time.monotonic() - start

    if interrupted:
        stopped_reason = "interrupted"
    elif reader is not None:
        stopped_reason = reader.stopped_reason
    else:
        stopped_reason = "completed"
    return result, duration_s, stopped_reason


def main(argv=None, on_viewer_ready=None):
    """`on_viewer_ready(viewer, sink)`, when given, is called once both are
    constructed and started (only reached when `--view` is given). This is the one
    hook `dlc_link.notebooks.live_view`'s background-thread `main()` call needs: the
    notebook's own foreground cell captures `viewer`/`sink` through it, because
    IPython's `display()`/`clear_output()` are meant to be driven from the kernel's
    own execution thread, never from this function's background thread. A raising
    callback is caught and ignored -- the sender must never depend on a notebook
    cell's own correctness."""
    args = build_parser().parse_args(argv)

    source_problem, source_value = resolve_source(args)
    if source_problem:
        print("dlc-link-live: {}".format(source_problem), file=sys.stderr)
        return 2

    problem = validate_connection_args(args)
    if problem:
        print("dlc-link-live: {}".format(problem), file=sys.stderr)
        return 2

    view_problem = validate_view_args(args)
    if view_problem:
        print("dlc-link-live: {}".format(view_problem), file=sys.stderr)
        return 2

    try:
        spec = classify_source(source_value)
    except SourceError as exc:
        print("dlc-link-live: {}".format(exc), file=sys.stderr)
        return 2
    print("dlc-link-live: source: {}".format(spec.describe()))

    fps_problem = fps_refusal(spec.kind, args.fps)
    if fps_problem:
        print("dlc-link-live: {}".format(fps_problem), file=sys.stderr)
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

    # D-60: parsed before any heavy import, so a typo'd signal name fails in
    # milliseconds and lists the declared names -- regardless of --view, because a
    # malformed --overlay is a mistake worth catching immediately either way.
    overlay_problem, overlay_clauses = viewer_cli.parse_overlay_clauses(args, smap)
    if overlay_problem:
        print("dlc-link-live: --overlay: {}".format(overlay_problem), file=sys.stderr)
        return 1

    import cv2  # deferred: main() must import with no camera library installed
    from dlclive import DLCLive

    opener = open_file_source if spec.kind == "file" else open_camera_source
    cap, opened, open_error = opener(cv2, spec, args)
    if open_error:
        print("dlc-link-live: {}".format(open_error), file=sys.stderr)
        return 1
    first_frame, fps, slot, reader, frames = opened

    width = cap.get(cv2.CAP_PROP_FRAME_WIDTH)
    height = cap.get(cv2.CAP_PROP_FRAME_HEIGHT)
    if args.resize:
        width *= args.resize
        height *= args.resize

    if args.probe_pose:
        # Lazy import: dlc_link.live_probe imports compare_pose_order/check_corner_geometry
        # FROM dlc_link.live, so importing it at module scope here would be circular.
        from dlc_link.live_probe import run_probe_pose

        return run_probe_pose(args, smap, DLCLive, cap, first_frame, width, height)

    pacer = Pacer("realtime") if spec.kind == "file" else None
    try:
        link, processor, live, infer = _build_processor_and_infer(
            args, spec, smap, width, height, first_frame, DLCLive
        )
    except MicsLinkError as exc:
        print("dlc-link-live: {}".format(exc), file=sys.stderr)
        cap.release()
        return 1

    viewer, sink = None, None
    if args.view:
        viewer = viewer_cli.build_viewer(args, smap, overlay_clauses, width, height, spec.describe())
        try:
            sink = viewer_cli.build_sink(args, viewer)
        except SinkError as exc:
            print("dlc-link-live: {}".format(exc), file=sys.stderr)
            if reader is not None:
                reader.stop()
            if live is not None:
                live.close()
            cap.release()
            return 1
        print("dlc-link-live: {}".format(viewer_cli.describe_sink(args, sink)))
        viewer.start()
        if on_viewer_ready is not None:
            try:
                on_viewer_ready(viewer, sink)
            except Exception:
                pass  # a notebook cell's own bug must never affect the sender

    result, duration_s, stopped_reason = _run_and_close(
        link, frames, infer, processor, pacer, fps, args, cap, reader, live, viewer=viewer, sink=sink
    )

    print_summary(result, spec, duration_s, slot, reader, stopped_reason)
    if viewer is not None:
        print("  viewer:          {}".format(viewer.snapshot()))
    if not args.dry_run and not args.capture_only and link is not None:
        print("  link.stats:      {}".format(link.stats.snapshot()))
        link.close()
    print(
        "  reminder: start this sender BEFORE the run when the pilot's config row has "
        "required: true, and AFTER the run when it has required: false (D-27) -- pilot "
        "3's row is required: false, so the correct order there is run first, then "
        "sender."
    )

    if args.min_rate is not None and isinstance(result["frames_inferred"], int) and duration_s > 0:
        achieved = result["frames_inferred"] / duration_s
        if achieved < args.min_rate:
            print(
                "dlc-link-live: WARN: achieved {:.3f} frames/s, below the --min-rate {:.3f} "
                "frames/s YOU supplied (this tool invents no threshold of its own -- "
                "D-54)".format(achieved, args.min_rate),
                file=sys.stderr,
            )
            return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
