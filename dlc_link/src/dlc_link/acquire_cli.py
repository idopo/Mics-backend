"""`dlc-link-relay` -- prints the lab-computer acquisition recorder's ffmpeg argv and
PowerShell supervisor (D-88). This module's entire job is producing text; it never
starts ffmpeg, never touches a camera, and never opens a network connection. A
researcher pastes its output into a PowerShell session on a DIFFERENT machine.

Imports nothing outside the standard library and `dlc_link`, so `--help` works in a
kit-only install with no `cv2`, `torch` or `dlclive` present. The DLC-project write
guard is the SAME one `dlc-link-generate` and `dlc-link-convert` already apply
(`dlc_link.generate_cli._check_out_dir_not_in_project`) -- composed with
`dlc_link.convert_cli._find_dlc_project_root`'s sibling-`config.yaml` walk-up, since
this tool (unlike `dlc-link-generate`) takes no `--config` to read a project directory
from directly.
"""
import argparse
import os
import sys

from dlc_link.acquire import AcquireSpec, AcquireSpecError, build_ffmpeg_argv
from dlc_link.acquire_supervisor import build_supervisor_ps1, render_argv_lines
from dlc_link.convert_cli import _find_dlc_project_root
from dlc_link.generate import GenerationError
from dlc_link.generate_cli import _check_out_dir_not_in_project

# Candidate -> AcquireSpec.delivery_format. No default (D-88 amendment): the measured
# answer lives in 38-ACQUISITION-VALIDATION.md Sec3, and a default here would be exactly
# the invented-number mistake --min-rate (dlc-link-live) exists to refuse.
_TRANSPORT_FORMATS = {"mpjpeg-tcp": "mpjpeg", "mpegts-udp": "mpegts"}

# The measured ffmpeg location on BOTH rig machines (38-HARDWARE-VALIDATION.md Sec2.2).
# Not a secret endpoint or device name -- a convenience default a researcher can always
# override with --ffmpeg-path; the PowerShell $env: expression is what makes it resolve
# under whichever account runs the supervisor.
_DEFAULT_FFMPEG_PATH_EXPR = '"$env:USERPROFILE\\ffmpeg\\ffmpeg-9.0.1-essentials_build\\bin\\ffmpeg.exe"'
_DEFAULT_WORKING_DIR_EXPR = '"."'
_DEFAULT_LOG_DIR_EXPR = '".\\log"'


def _check_out_not_in_dlc_project(out_path):
    """D-44/D-46, via the shared guard: refuse `--out` when its directory resolves
    inside a DLC project root (a sibling `config.yaml` found by walking up from it)."""
    out_dir = os.path.dirname(os.path.abspath(out_path)) or "."
    project_root = _find_dlc_project_root(out_dir)
    _check_out_dir_not_in_project(out_dir, project_root)


def _ps_string(value):
    """Wrap a plain value the researcher typed (a path, not a PowerShell expression)
    in a double-quoted PowerShell string literal, so `$env:`-style expressions stay
    usable while a literal backslash path still works unescaped."""
    return '"{}"'.format(str(value).replace('"', '`"'))


def _build_parser():
    parser = argparse.ArgumentParser(
        prog="dlc-link-relay",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        description=(
            "Pure text generator for the lab-computer acquisition recorder (D-88): "
            "prints the exact ffmpeg argv and the PowerShell supervisor for a researcher "
            "to paste on a DIFFERENT machine. This tool never runs ffmpeg, never touches "
            "a camera and never opens a network connection -- it writes NOTHING unless "
            "--out is given."
        ),
        epilog=(
            "Before running the printed command: IC Capture must be CLOSED (DirectShow "
            "access is exclusive, 38-HARDWARE-VALIDATION.md Sec8.4). Exposure, gain and "
            "the ROI are set in IC Capture FIRST and are inherited by a fresh ffmpeg; "
            "adjusting them mid-session means stopping the recorder and reopening IC "
            "Capture. This command itself writes nothing unless --out is given."
        ),
    )
    parser.add_argument(
        "--device", default=None, metavar="NAME",
        help="the DirectShow friendly name (e.g. the rig camera's label). No default -- "
             "required. Writes nothing.",
    )
    parser.add_argument(
        "--segment-pattern", required=True, metavar="PATTERN",
        help="RELATIVE filename with a strftime pattern, forward slashes only -- e.g. "
             "'rig-%%Y%%m%%d-%%H%%M%%S.mkv'. Refused if absolute or tee-unsafe "
             "(AcquireSpecError explains why). Writes nothing itself.",
    )
    parser.add_argument("--segment-time", type=int, default=20, metavar="SECONDS",
                         help="segment_time passed to ffmpeg's segment muxer. Writes nothing.")
    parser.add_argument("--segment-format", default="matroska", help="writes nothing")
    parser.add_argument("--rtbufsize", default="100M", help="writes nothing")
    parser.add_argument("--file-codec", default="mjpeg", help="the archival (file leg) encoder. Writes nothing.")
    parser.add_argument("--file-quality", default="5", metavar="Q",
                         help="-q:v for an mjpeg file leg; ignored for h264_*. Writes nothing.")
    parser.add_argument(
        "--file-extra", nargs="*", default=(), metavar="FLAG",
        help="extra ffmpeg flags for the file leg, passed through verbatim after its "
             "codec flag (e.g. --file-extra -g 1). Writes nothing itself.",
    )
    parser.add_argument(
        "--delivery", dest="delivery_url", default=None, metavar="URL",
        help="the delivery leg's URL. Requires --transport. Writes nothing itself -- "
             "ffmpeg is what opens the connection, not this tool.",
    )
    parser.add_argument(
        "--transport", choices=sorted(_TRANSPORT_FORMATS), default=None,
        help="REQUIRED with --delivery, no default on purpose: the measured answer is "
             "38-ACQUISITION-VALIDATION.md Sec3, decided on which candidate cannot stall "
             "the file leg under a slow consumer -- never assume one.",
    )
    parser.add_argument(
        "--delivery-codec", default=None, metavar="CODEC",
        help="unset (default) keeps the cheap single-encode form -- one MJPEG encode "
             "feeds both legs. Set this to something other than --file-codec to escalate "
             "to the two-stream select= form, e.g. when the file leg is DeepLabCut "
             "training footage and the default MJPEG quality is not good enough for a "
             "model that has not been trained yet -- the archival leg should never "
             "silently inherit the delivery leg's cheap quality. Writes nothing itself.",
    )
    parser.add_argument(
        "--delivery-extra", nargs="*", default=(), metavar="FLAG",
        help="extra ffmpeg flags for the delivery leg, verbatim (e.g. -g 1 for an "
             "all-intra escalation). Writes nothing itself.",
    )
    parser.add_argument("--duration", type=int, default=None, metavar="SECONDS",
                         help="-t, placed before the output. Unset runs until stopped. Writes nothing.")
    parser.add_argument(
        "--max-restarts", type=int, default=5, metavar="N",
        help="bounds the generated supervisor's restart loop. Writes nothing itself.",
    )
    parser.add_argument(
        "--restart-delay", type=float, default=5.0, metavar="SECONDS",
        help="Start-Sleep before each restart attempt after the first. Writes nothing itself.",
    )
    parser.add_argument(
        "--ffmpeg-path", default=None, metavar="PATH",
        help="overrides the default '$env:USERPROFILE\\ffmpeg\\...\\ffmpeg.exe' (the "
             "measured location on both rig machines, 38-HARDWARE-VALIDATION.md Sec2.2). "
             "Writes nothing itself.",
    )
    parser.add_argument(
        "--working-dir", default=None, metavar="PATH",
        help="the supervisor's -WorkingDirectory -- where segments land, since "
             "--segment-pattern must be relative. Defaults to '.'. Writes nothing itself.",
    )
    parser.add_argument(
        "--log-dir", default=None, metavar="PATH",
        help="where each restart attempt's own log file is written. Defaults to '.\\log'. "
             "Writes nothing itself.",
    )
    parser.add_argument(
        "--print", dest="print_mode", choices=("argv", "supervisor", "both"), default="argv",
        help="'argv' (default): the ffmpeg argv one token per line plus a paste-ready "
             "PowerShell array block. 'supervisor': the full generated supervisor text. "
             "'both': both, with a labelled separator. Writes nothing -- this only "
             "selects what goes to stdout.",
    )
    parser.add_argument(
        "--out", default=None, metavar="PATH",
        help="the ONLY way this command writes anything: writes the supervisor text to "
             "PATH and echoes the absolute path written. Refused inside a DeepLabCut "
             "project directory by the same shared guard dlc-link-generate uses.",
    )
    return parser


def _build_spec(args):
    return AcquireSpec(
        device=args.device,
        segment_pattern=args.segment_pattern,
        segment_time_s=args.segment_time,
        segment_format=args.segment_format,
        rtbufsize=args.rtbufsize,
        file_codec=args.file_codec,
        file_quality=args.file_quality,
        file_extra=tuple(args.file_extra),
        delivery_url=args.delivery_url,
        delivery_format=_TRANSPORT_FORMATS.get(args.transport),
        delivery_codec=args.delivery_codec,
        delivery_extra=tuple(args.delivery_extra),
        duration_s=args.duration,
    )


def _print_argv_block(argv_tokens):
    print("# ffmpeg argv, one token per line -- writes nothing, this is text only:")
    for token in argv_tokens:
        print(token)
    print()
    print("# paste-ready PowerShell argument array:")
    decl_lines, array_lines = render_argv_lines(argv_tokens)
    for line in decl_lines + array_lines:
        print(line)


def main(argv=None):
    parser = _build_parser()
    args = parser.parse_args(argv)

    if not args.device:
        parser.error(
            "--device is required. Get the exact DirectShow friendly name with: "
            "ffmpeg -list_devices true -f dshow -i dummy (writes nothing; "
            "'Error opening input file dummy' at the end is expected)"
        )

    if args.delivery_url is not None and args.transport is None:
        parser.error(
            "--delivery was given without --transport -- see --transport's help for "
            "why there is no default"
        )

    try:
        spec = _build_spec(args)
    except AcquireSpecError as exc:
        print("error: {}".format(exc), file=sys.stderr)
        return 1

    argv_tokens = build_ffmpeg_argv(spec)
    supervisor_text = build_supervisor_ps1(
        _ps_string(args.ffmpeg_path) if args.ffmpeg_path is not None else _DEFAULT_FFMPEG_PATH_EXPR,
        argv_tokens,
        _ps_string(args.working_dir) if args.working_dir is not None else _DEFAULT_WORKING_DIR_EXPR,
        _ps_string(args.log_dir) if args.log_dir is not None else _DEFAULT_LOG_DIR_EXPR,
        args.max_restarts,
        args.restart_delay,
    )

    if args.out is not None:
        try:
            _check_out_not_in_dlc_project(args.out)
        except GenerationError as exc:
            print("error: {}".format(exc), file=sys.stderr)
            return 1
        out_path = os.path.abspath(args.out)
        with open(out_path, "w") as handle:
            handle.write(supervisor_text)
        print("Wrote {}".format(out_path))

    if args.print_mode in ("argv", "both"):
        _print_argv_block(argv_tokens)
    if args.print_mode == "both":
        print()
        print("# --- supervisor ---")
    if args.print_mode in ("supervisor", "both"):
        print(supervisor_text, end="")

    return 0


if __name__ == "__main__":
    sys.exit(main())
