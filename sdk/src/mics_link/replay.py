"""Replay entry point (Phase 34, Plan 07, SDK-12): plays a recorded `(t, signal, value)`
file through a `mics_link` client at real time, at a scale factor, or as fast as possible.
This is the phase's own regression vehicle and the mechanism by which Phase 35 is proven
without a camera, a trained model or an animal — and afterwards, the way a model-driven
task is re-run deterministically.

`replay()` takes a `link`, it does not create one (decision 6) — `main()` builds it via the
public `mics_link.connect(...)` inside a `with` block, so SDK-09's lifecycle applies and
`replay()` itself stays testable against `MicsLink(FakeTransport())` with no socket.
`sleep`/`clock` are injected into the `Pacer` (`mics_link/timing.py`) so the timing modes
are provable in milliseconds against a recording fake, never a real wait (decision 7).

NO latency, jitter, drift or achieved-rate-vs-target number is computed, printed or
asserted anywhere in this module (decision 5) — the final summary is COUNTS plus a plain
wall-clock duration, never labelled as a latency. `mics_link.timing.Pacer` owns and
documents the scheduling contract ("falling behind never bursts") this module depends on.

EVT replay is explicitly out of scope (decision 8): a `value` that parses as a JSON object
is a malformed ROW, handled in `mics_link/replay_io.py`, never an event — stated here too
so nobody "improves" this into EVT replay without a requirement.

`read_rows`/`ReplayStats` are implemented in `mics_link/replay_io.py` and re-exported here
unchanged — the split keeps both files under the project's 300-line cap; every name this
module's own `<interfaces>` block promises (`ReplayStats`, `read_rows`, `replay`, `main`)
still resolves from `mics_link.replay`, split or not.
"""
import argparse
import sys
import time
from pathlib import Path

from . import connect
from .errors import InvalidValueError, MicsLinkError
from .replay_io import ReplayStats, read_rows  # noqa: F401 (re-exported, see docstring)
from .timing import Pacer

__all__ = ["ReplayStats", "read_rows", "replay", "main"]


def replay(link, rows, mode="realtime", scale=1.0, stats=None, sleep=time.sleep, clock=time.monotonic):
    """Drive `link.send_signal(signal, value)` for every `(t, signal, value)` in `rows`
    (typically `read_rows(path, stats=stats)` — pass the SAME `stats` object to both so
    reader and sender counts land in one place). Paced by a `Pacer` in `mode` ("realtime" |
    "scaled" | "fast"); the FIRST row's `t` is the schedule's origin (decision 1) — an
    absolute epoch, a relative offset, or a frame timestamp all work unchanged.

    Never raises: `InvalidValueError` — the one exception `send_signal` may raise — is
    caught here and counted in `stats.rejected`; a queue-full `False` return is counted in
    `stats.dropped`. Either way the replay CONTINUES to the end of `rows`. Returns the
    (possibly caller-supplied) `ReplayStats`.
    """
    if stats is None:
        stats = ReplayStats()
    pacer = Pacer(mode=mode, scale=scale, clock=clock, sleep=sleep)
    origin_t = None
    for t, signal, value in rows:
        if origin_t is None:
            origin_t = t
            pacer.start()
        pacer.wait_until(t - origin_t)
        try:
            accepted = link.send_signal(signal, value)
        except InvalidValueError:
            stats.rejected += 1
            continue
        if accepted:
            stats.sent += 1
        else:
            stats.dropped += 1
    return stats


def _build_parser():
    parser = argparse.ArgumentParser(
        prog="mics-link-replay",
        description="Replay a recorded (t, signal, value) file through a mics-link client.",
    )
    parser.add_argument("--host", required=True, help="Pi hostname or IP")
    parser.add_argument("--port", required=True, type=int, help="Pi's router_bind port")
    parser.add_argument(
        "--source-id", required=True, help="must match the rig's pilot_hardware_config"
    )
    parser.add_argument(
        "--file", required=True, help="path to a (t, signal, value) CSV or JSONL file"
    )
    parser.add_argument("--mode", choices=("realtime", "scaled", "fast"), default="realtime")
    parser.add_argument("--scale", type=float, default=1.0, help="only used with --mode scaled")
    parser.add_argument("--heartbeat-s", type=float, default=None)
    parser.add_argument("--queue-size", type=int, default=None)
    return parser


def _format_summary(stats, duration_s):
    counts = stats.snapshot()
    return "\n".join(
        [
            "mics-link-replay summary:",
            "  rows_read:      {}".format(counts["rows_read"]),
            "  rows_malformed: {}".format(counts["rows_malformed"]),
            "  sent:           {}".format(counts["sent"]),
            "  dropped:        {}".format(counts["dropped"]),
            "  rejected:       {}".format(counts["rejected"]),
            "  duration_s:     {:.3f}".format(duration_s),
        ]
    )


def main(argv=None):
    """CLI entry point — `console_script mics-link-replay`, and the `python -m
    mics_link.replay` fallback documented for Windows environments where `<env>\\Scripts\\`
    may not be on PATH (SDK-14h). Argument parsing (including `--help`) always runs before
    `connect(...)` is ever reached, so `--help` works with no socket library importable.
    Returns an int exit code; never raises.
    """
    args = _build_parser().parse_args(argv)

    if args.scale <= 0:
        # (WR-03) Pacer validates scale unconditionally regardless of mode (timing.py), so
        # this guard must too — gating it on `--mode scaled` let `--mode realtime`/`--mode
        # fast` with a non-positive scale reach Pacer.__init__ and raise an uncaught
        # ValueError, contradicting main()'s own "never raises" contract.
        print(
            "mics-link-replay: --scale must be > 0, got {}".format(args.scale),
            file=sys.stderr,
        )
        return 2

    file_path = Path(args.file)
    if not file_path.exists():
        print("mics-link-replay: file not found: {}".format(file_path), file=sys.stderr)
        return 2

    kwargs = {}
    if args.heartbeat_s is not None:
        kwargs["heartbeat_s"] = args.heartbeat_s
    if args.queue_size is not None:
        kwargs["queue_size"] = args.queue_size

    stats = ReplayStats()
    start = time.monotonic()
    try:
        with connect(args.host, args.port, args.source_id, **kwargs) as link:
            rows = read_rows(file_path, stats=stats)
            replay(link, rows, mode=args.mode, scale=args.scale, stats=stats)
    except MicsLinkError as exc:
        print("mics-link-replay: {}".format(exc), file=sys.stderr)
        return 1
    duration_s = time.monotonic() - start
    print(_format_summary(stats, duration_s))
    return 0


if __name__ == "__main__":
    sys.exit(main())
