"""`dlc-link-convert`'s argparse CLI, plus the D-44/D-46 write-location refusal and the
atomic-write mechanics.

Split out from `dlc_link.convert` to hold that module under its line budget (coding
standard: production files under 300 lines) -- the same shape as
`dlc_link.generate`/`dlc_link.generate_cli`. `dlc_link.convert.main` re-exports `main` from
here so the declared console script (`dlc-link-convert = dlc_link.convert:main`,
pyproject.toml) keeps its target.
"""
import argparse
import itertools
import os
import sys
import tempfile

from dlc_link.convert import ConvertError, flatten_columns, read_h5, rows_to_wide, write_wide_csv
from dlc_link.signal_map import SignalMapError, load_signal_map


def _resolved(path):
    return os.path.normcase(os.path.realpath(path))


def _find_dlc_project_root(directory):
    """Walk up from `directory` (inclusive); return the first ancestor containing a
    sibling `config.yaml` (a DLC project root), or `None` if none is found before the
    filesystem root."""
    current = os.path.abspath(directory)
    while True:
        if os.path.isfile(os.path.join(current, "config.yaml")):
            return current
        parent = os.path.dirname(current)
        if parent == current:
            return None
        current = parent


def _check_out_not_in_dlc_project(out_path, h5_path):
    """D-44: refuse `--out` when it resolves inside the `.h5`'s own directory, or inside a
    DLC project root detected by a sibling `config.yaml` anywhere above it. Uses
    `os.path.realpath` + `os.path.normcase` + `os.path.commonpath` -- the same rule
    `dlc_link.generate_cli._check_out_dir_not_in_project` applies, for the same reason: the
    user's shell prompt sits inside their project directory, so a cwd-relative output path
    lands there."""
    out_dir = os.path.dirname(os.path.abspath(out_path)) or "."
    out_dir_resolved = _resolved(out_dir)
    h5_dir = os.path.dirname(os.path.abspath(h5_path))
    h5_dir_resolved = _resolved(h5_dir)
    project_root = _find_dlc_project_root(h5_dir)

    boundaries = {h5_dir_resolved}
    if project_root is not None:
        boundaries.add(_resolved(project_root))

    for boundary in boundaries:
        common = os.path.commonpath([out_dir_resolved, boundary])
        if common == boundary:
            raise ConvertError(
                "D-44: --out {!r} (directory {!r}) resolves inside {!r}, which is either "
                "the .h5's own directory or a DLC project root (detected by a sibling "
                "config.yaml) -- the user's DLC project directory is read-only by "
                "explicit requirement. Choose a scratch directory outside the "
                "project.".format(out_path, out_dir_resolved, boundary)
            )


def _build_parser():
    parser = argparse.ArgumentParser(
        prog="dlc-link-convert",
        description=(
            "Convert a DeepLabCut .h5 export into a wide (t + one column per signal) "
            "replay CSV that mics-link-replay plays back at real time."
        ),
    )
    parser.add_argument("--h5", required=True, metavar="PATH", help="path to the DeepLabCut .h5 export")
    parser.add_argument(
        "--signal-map", required=True, metavar="PATH",
        help="path to the generated <source_id>_signals.py",
    )
    parser.add_argument(
        "--fps", required=True, type=float, metavar="N",
        help=(
            "the .h5 export carries no time column; time is reconstructed as "
            "index/fps. Use the fps of the VIDEO the model was run over, not an "
            "arbitrary rate."
        ),
    )
    parser.add_argument(
        "--out", required=True, metavar="PATH",
        help="REQUIRED -- the output wide CSV path. Specifically not a cwd-relative default.",
    )
    parser.add_argument("--key", default=None, help="HDF store key, when the .h5 holds more than one dataset")
    parser.add_argument(
        "--likelihood-threshold", type=float, default=None, metavar="P",
        help=(
            "DELIBERATELY NO DEFAULT: this project's pcutoff is 0.01, two orders of "
            "magnitude below DeepLabCut's own 0.6 default, so neither hardcoded value is "
            "safe here. The value comes from the measured likelihood distribution "
            "(D-41), which plan 35-07 records."
        ),
    )
    parser.add_argument("--start-t", type=float, default=0.0)
    parser.add_argument("--max-rows", type=int, default=None)
    return parser


def _write_atomically(out_path, header_names, rows):
    """Write through a temporary file in the SAME directory as `out_path`, then rename it
    into place, so an interrupted conversion cannot leave a half-written CSV -- never
    through a temporary file in the current working directory or the system temp root,
    either of which could be inside the project or on a different volume from `out_path`."""
    out_dir = os.path.dirname(os.path.abspath(out_path)) or "."
    os.makedirs(out_dir, exist_ok=True)
    fd, tmp_path = tempfile.mkstemp(dir=out_dir, prefix=".dlc-link-convert-", suffix=".tmp")
    os.close(fd)
    try:
        rows_written = write_wide_csv(tmp_path, header_names, rows)
        os.replace(tmp_path, out_path)
    except Exception:
        if os.path.exists(tmp_path):
            os.remove(tmp_path)
        raise
    return rows_written


def _print_summary(args, smap, counts, header_names, rows_written, cells_emptied):
    print("WRITE FOOTPRINT: {}".format(os.path.abspath(args.out)))
    print("dlc-link-convert summary:")
    print("  rows_written:                 {}".format(rows_written))
    print("  columns_written:              {}".format(len(header_names)))
    print("  bodyparts_skipped_undeclared: {}".format(counts["bodyparts_skipped_undeclared"]))
    print("  coords_skipped_unrecognised:  {}".format(counts["coords_skipped_unrecognised"]))
    print("  cells_emptied_by_likelihood:  {}".format(cells_emptied))
    print(
        "Next: mics-link-replay --host <PI_HOST> --port <PORT> --source-id {} --file {} "
        "--mode realtime".format(smap.SOURCE_ID, os.path.abspath(args.out))
    )


def main(argv=None):
    args = _build_parser().parse_args(argv)

    try:
        _check_out_not_in_dlc_project(args.out, args.h5)
        smap = load_signal_map(args.signal_map)
        columns, rows = read_h5(args.h5, key=args.key)
        position_to_name, counts = flatten_columns(columns, smap)
        if args.max_rows is not None:
            rows = itertools.islice(rows, args.max_rows)

        header_names = sorted(set(position_to_name.values()))
        wide_rows = rows_to_wide(
            rows, position_to_name, args.fps,
            likelihood_threshold=args.likelihood_threshold, start_t=args.start_t,
        )

        cells_emptied = 0

        def _counted_rows():
            nonlocal cells_emptied
            for t, values in wide_rows:
                cells_emptied += len(header_names) - len(values)
                yield t, values

        rows_written = _write_atomically(args.out, header_names, _counted_rows())
    except (ConvertError, SignalMapError) as exc:
        print("dlc-link-convert: {}".format(exc), file=sys.stderr)
        return 1

    _print_summary(args, smap, counts, header_names, rows_written, cells_emptied)
    return 0


if __name__ == "__main__":
    sys.exit(main())
