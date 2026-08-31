"""`dlc-link-generate`'s argparse CLI, plus the D-44/D-46 write-location refusal.

Split out from `dlc_link.generate` to hold that module under its line budget (coding
standard: production files under 300 lines). `dlc_link.generate.main` re-exports `main`
from here so the declared console script keeps its `dlc_link.generate:main` target.
"""
import argparse
import os
import sys

from dlc_link.config_read import (
    ConfigReadError,
    from_explicit_list,
    read_dlc_config,
    read_pose_cfg,
)
from dlc_link.decimate import RECOMMENDED_DEFAULTS
from dlc_link.generate import GenerationError, generate
from dlc_link.names import flat_signal_names


def _resolved(path):
    return os.path.normcase(os.path.realpath(path))


def _build_parser():
    parser = argparse.ArgumentParser(
        prog="dlc-link-generate",
        description=(
            "Turn a DeepLabCut config.yaml (or pose_cfg.yaml) plus an explicit bodypart "
            "selection into a paired ExternalHardware lib source and signal map."
        ),
    )
    config_group = parser.add_mutually_exclusive_group()
    config_group.add_argument(
        "--config", metavar="PATH",
        help=(
            "Path to a DLC 3.0 pytorch config.yaml. READING this file is fine even when "
            "it points straight at the user's real, uncopied DLC project directory -- "
            "only WRITING into that directory is refused (see --out-dir)."
        ),
    )
    config_group.add_argument(
        "--pose-cfg", metavar="PATH",
        help=(
            "Path to a TensorFlow-engine exported pose_cfg.yaml (all_joints_names). "
            "Reading is fine; see --out-dir for the write restriction."
        ),
    )
    parser.add_argument(
        "--bodyparts", required=True, metavar="a,b,c",
        help=(
            "REQUIRED, comma-separated original bodypart names to emit signals for. "
            "There is deliberately no flag that emits every candidate (D-39)."
        ),
    )
    pose_order_group = parser.add_mutually_exclusive_group()
    pose_order_group.add_argument("--pose-order", metavar="a,b,c")
    pose_order_group.add_argument("--pose-order-file", metavar="PATH")
    parser.add_argument("--allow-signals", type=int, default=6, metavar="N")
    parser.add_argument("--coords", default="", metavar="a,b")
    parser.add_argument("--source-id", required=True)
    parser.add_argument("--stale-after-ms", type=int, default=100)
    parser.add_argument("--class-name", default=None)
    parser.add_argument(
        "--out-dir", required=True, metavar="PATH",
        help=(
            "REQUIRED -- specifically not a default of '.'. The two generated files are "
            "written here. Must be neither the --config/--pose-cfg directory nor a "
            "descendant of it (D-44/D-46): writing into the user's DLC project directory "
            "is refused even though reading it is fine."
        ),
    )
    parser.add_argument(
        "--liveness-hook", choices=("clock-consistent", "substrate-default"), default="clock-consistent"
    )
    parser.add_argument("--list-bodyparts", action="store_true")
    parser.add_argument("--force", action="store_true")
    return parser


def _resolve_source_and_config_dir(args):
    if args.config:
        return read_dlc_config(args.config), os.path.dirname(os.path.abspath(args.config))
    if args.pose_cfg:
        return read_pose_cfg(args.pose_cfg), os.path.dirname(os.path.abspath(args.pose_cfg))
    bodyparts = [b.strip() for b in args.bodyparts.split(",") if b.strip()]
    print(
        "warning: neither --config nor --pose-cfg given; provenance is degraded to "
        "'explicit-list'. Pass --config/--pose-cfg for real provenance.",
        file=sys.stderr,
    )
    return from_explicit_list(bodyparts), None


def _resolve_pose_order(args, source):
    if args.pose_order:
        return [p.strip() for p in args.pose_order.split(",") if p.strip()], "probe"
    if args.pose_order_file:
        with open(args.pose_order_file) as handle:
            order = [
                line.strip() for line in handle
                if line.strip() and not line.strip().startswith("#")
            ]
        return order, "probe"

    if source.multianimal:
        order = list(source.multianimal_bodyparts) + list(source.unique_bodyparts)
    else:
        order = list(source.bodyparts) + list(source.unique_bodyparts)
    print(
        "WARNING: no --pose-order/--pose-order-file given. Falling back to the config's "
        "DECLARED order, which is NOT known to be the model runner's actual pose-array "
        "row order (D-42, open empirical question). DLC-Live's own documentation states "
        "only that single_animal=True yields (num_bodyparts, 3) and says nothing about "
        "whether that is 10 rows or 32 nor about their order. An index taken from the "
        "wrong order sends the wrong keypoint's numbers under the right name.",
        file=sys.stderr,
    )
    return order, "config-declared-UNVERIFIED"


def _check_out_dir_not_in_project(out_dir, config_dir):
    if config_dir is None:
        return
    out_dir_resolved = _resolved(out_dir)
    config_dir_resolved = _resolved(config_dir)
    common = os.path.commonpath([out_dir_resolved, config_dir_resolved])
    if common == config_dir_resolved:
        raise GenerationError(
            "--out-dir {!r} (resolved: {!r}) is the config's own directory, or a "
            "descendant of it (resolved: {!r}) -- D-44: the user's DLC project directory "
            "is read-only by explicit user requirement. Choose a scratch directory "
            "outside the project.".format(out_dir, out_dir_resolved, config_dir_resolved)
        )


def main(argv=None):
    args = _build_parser().parse_args(argv)
    source, config_dir = _resolve_source_and_config_dir(args)

    if args.list_bodyparts:
        for name, cls in source.candidate_names():
            print("{}\t{}".format(name, cls))
        return 0

    wanted = [b.strip() for b in args.bodyparts.split(",") if b.strip()]
    coords_for = {c.strip() for c in args.coords.split(",") if c.strip()}
    pose_order, pose_order_source = _resolve_pose_order(args, source)

    try:
        _check_out_dir_not_in_project(args.out_dir, config_dir)
        result = generate(
            source=source, pose_order=pose_order, pose_order_source=pose_order_source,
            wanted=wanted, coords_for=coords_for, source_id=args.source_id,
            stale_after_ms=args.stale_after_ms, class_name=args.class_name,
            liveness_hook=args.liveness_hook, allow_signals=args.allow_signals,
        )
    except (GenerationError, ConfigReadError) as exc:
        print("error: {}".format(exc), file=sys.stderr)
        return 1

    lib_path = os.path.join(args.out_dir, "{}_lib.py".format(args.source_id))
    map_path = os.path.join(args.out_dir, "{}_signals.py".format(args.source_id))

    if not args.force:
        for path in (lib_path, map_path):
            if os.path.exists(path):
                print("error: {} already exists; pass --force to overwrite".format(path), file=sys.stderr)
                return 1

    os.makedirs(args.out_dir, exist_ok=True)
    with open(lib_path, "w") as handle:
        handle.write(result.lib_source)
    with open(map_path, "w") as handle:
        handle.write(result.map_source)

    signal_names = flat_signal_names(result.name_map)
    hz_cap = 1000.0 / RECOMMENDED_DEFAULTS["min_interval_ms"]
    print("Wrote {}".format(lib_path))
    print("Wrote {}".format(map_path))
    print("Signals ({}): {}".format(len(signal_names), sorted(signal_names)))
    print(
        "Budget arithmetic: {} signals x {:g} Hz per-signal cap = {:g} msg/s "
        "(see dlc_link.decimate.RECOMMENDED_DEFAULTS).".format(
            len(signal_names), hz_cap, len(signal_names) * hz_cap
        )
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
