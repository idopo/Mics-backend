"""DeepLabCut `.h5` export -> wide replay CSV converter (D-31, DLC-09).

`sdk/src/mics_link/replay_io.py` documents the wide contract this converter's write half
satisfies: a header of `t` plus one column per signal, every non-empty cell becomes one
`(t, signal, value)` tuple sharing that row's `t`, and an empty cell means "no sample" --
skipped SILENTLY, not a malformed row. An occluded tracked feature is the motivating case,
and this module turns a real occlusion (a below-threshold likelihood) into exactly that
empty-cell shape.

Two constraints split this module into a pure half and an impure half: (1) the HDF5
binding that `pandas.read_hdf` would otherwise prefer is ABSENT from the target env and
must never be added (D-09c) -- the read half (added in a later task) goes through the
PyTables backend instead; (2) the dev host has no `pandas` at all, so
`flatten_columns`/`rows_to_wide`/`write_wide_csv` below are pure and take plain Python
data -- no pandas import anywhere in this file yet.

Column names come from the loaded signal map (`dlc_link.signal_map.load_signal_map`)
exclusively -- this module never re-derives the bodypart-to-identifier transform that has
its one declaration site in `dlc_link.names`.

`main` is a thin re-export, same shape as `dlc_link.generate`/`dlc_link.generate_cli`: the
argparse CLI and the D-44 write-location refusal live in `dlc_link.convert_cli`, split out
to hold this file under the project's 300-line standard. `dlc-link-convert =
dlc_link.convert:main` (pyproject.toml) is unaffected.
"""
import sys

_RECOGNISED_COORDS = ("x", "y", "likelihood")
_LIKELIHOOD_SUFFIX = "_likelihood"
_X_SUFFIX = "_x"
_Y_SUFFIX = "_y"


class ConvertError(Exception):
    """Raised for every refusal in this module. Always names the input path or the
    offending column."""


def _to_plain(value):
    """numpy (or any array-scalar) -> the equivalent Python scalar, via `.item()` -- never
    `float(...)`, which would flatten an int/bool/float distinction. Anything else is
    returned unchanged. Mirrors `mics_link.values.as_scalar` without importing it (this
    package depends on `mics-link` as an ordinary third party, never a private helper)."""
    item = getattr(value, "item", None)
    return item() if callable(item) and not isinstance(value, (bytes, str)) else value


def flatten_columns(columns, signal_map):
    """Take a DeepLabCut `.h5` export's column labels -- a list of 3-level
    `(scorer, bodypart, coord)` tuples, or a 4-level `(scorer, individual, bodypart, coord)`
    tuple for a multi-animal export -- and return an ordered `{position: signal_name}`
    mapping, using only names present in `signal_map.SIGNALS`.

    Rules (see this module's docstring and the plan's D-37/D-38 references for why):
    - The scorer level is ignored; a `.h5` carries exactly one and its name is an
      implementation detail of the training run.
    - A `coord` outside `x`/`y`/`likelihood` is skipped and counted
      (`coords_skipped_unrecognised`).
    - A bodypart present in the file but absent from `signal_map.SIGNALS` is skipped and
      counted (`bodyparts_skipped_undeclared`) -- the researcher declared a subset on
      purpose (DLC-03: coordinates are opt-in per keypoint).
    - A bodypart present in `signal_map.SIGNALS` but absent from the file raises
      `ConvertError` naming it: a map/model mismatch, and silently emitting an all-empty
      column would produce a replay that proves nothing.
    - A 4-level (multi-animal) export is accepted only when the only individuals present
      are `single` and at most one real individual (DeepLabCut writes unique bodyparts
      under the individual literally named `single`, per-animal parts under each real
      individual). More than one real individual raises `ConvertError` naming
      `single_animal=True` and listing the individuals found -- with `identity: false`,
      `stitch_tracklets` assigns per-individual identity post-hoc, which DLC-Live never
      runs, so a per-individual column is not a stable identity even inside one file.
      Columns under `single`, or under the single accepted real individual, map by
      bodypart name exactly as the 3-level case does.

    Returns `(position_to_name, counts)` where `counts` is a plain dict with keys
    `bodyparts_skipped_undeclared` and `coords_skipped_unrecognised`.
    """
    signals = signal_map.SIGNALS
    counts = {"bodyparts_skipped_undeclared": 0, "coords_skipped_unrecognised": 0}
    position_to_name = {}
    seen_bodyparts = set()

    if columns:
        level_count = len(columns[0])
        if level_count not in (3, 4):
            raise ConvertError(
                "unsupported column MultiIndex depth {} -- expected 3 (scorer, bodypart, "
                "coord) or 4 (scorer, individual, bodypart, coord)".format(level_count)
            )
        if level_count == 4:
            individuals = {column[1] for column in columns}
            real_individuals = sorted(individual for individual in individuals if individual != "single")
            if len(real_individuals) > 1:
                raise ConvertError(
                    "single_animal=True is required, but this export declares multiple "
                    "real individuals {!r} (plus 'single' if present) -- with identity: "
                    "false, stitch_tracklets assigns per-individual identity post-hoc, "
                    "which DLC-Live never runs, so a per-individual column is not a "
                    "stable identity even inside one file".format(sorted(individuals))
                )

    for position, column in enumerate(columns):
        if len(column) == 3:
            _scorer, bodypart, coord = column
        else:
            _scorer, _individual, bodypart, coord = column

        if coord not in _RECOGNISED_COORDS:
            counts["coords_skipped_unrecognised"] += 1
            continue
        if bodypart not in signals:
            counts["bodyparts_skipped_undeclared"] += 1
            continue

        seen_bodyparts.add(bodypart)
        name = signals[bodypart]["signals"].get(coord)
        if name is None:
            # e.g. this bodypart has no x/y declared (coords=False in the generator).
            counts["coords_skipped_unrecognised"] += 1
            continue

        # Belt-and-braces (T-35 name gate duplication, deliberate): replay_io._detect_shape
        # treats a header containing "signal" without "value" as AMBIGUOUS and raises at
        # read time. dlc_link.names already makes this impossible upstream; this assertion
        # exists so a future change to that gate fails loudly here too.
        if name == "signal":
            raise ConvertError(
                "signal_map declares a signal literally named 'signal' for bodypart {!r} "
                "-- replay_io._detect_shape treats a header containing 'signal' without "
                "'value' as AMBIGUOUS and would refuse this file at read time".format(bodypart)
            )
        position_to_name[position] = name

    missing = set(signals) - seen_bodyparts
    if missing:
        raise ConvertError(
            "bodypart(s) {!r} are declared in the signal map but absent from the .h5 "
            "export -- a map/model mismatch; emitting an all-empty column would produce "
            "a replay that proves nothing".format(sorted(missing))
        )

    return position_to_name, counts


def _likelihood_groups(position_to_name):
    """Group already-emitted signal NAMES by the suffix convention
    `dlc_link.names.signal_names_for` documents (`<ident>_likelihood`, `<ident>_x`,
    `<ident>_y`) so a below-threshold likelihood can blank its own bodypart's x/y cells.
    This parses the CONVENTION of already-generated, already-safe identifiers -- it does
    not re-derive an identifier from a researcher-authored bodypart string (the D-12/
    T-35-01 boundary that has exactly one declaration site, `dlc_link.names`)."""
    name_to_position = {name: position for position, name in position_to_name.items()}
    groups = {}
    for position, name in position_to_name.items():
        if name.endswith(_LIKELIHOOD_SUFFIX):
            base = name[: -len(_LIKELIHOOD_SUFFIX)]
            groups[base] = {
                "likelihood": position,
                "x": name_to_position.get(base + _X_SUFFIX),
                "y": name_to_position.get(base + _Y_SUFFIX),
            }
    return groups


def rows_to_wide(rows, position_to_name, fps, likelihood_threshold=None, start_t=0.0):
    """Yield `(t, {signal_name: value})` for each row in `rows` (an iterable of positional
    row tuples aligned with `position_to_name`'s positions).

    `t` is `start_t + index / fps`: the `.h5` export has no time column, so time is
    reconstructed from the frame index and the video's fps -- pass the fps of the VIDEO the
    model was run over, not an arbitrary rate.

    When `likelihood_threshold` is given, a bodypart whose likelihood for that row is below
    it emits EMPTY cells for that bodypart's `x` and `y` -- not a zero, not a hold -- which
    is exactly the "no sample" semantic `replay_io` documents, and is how an occlusion
    survives the round trip. The likelihood column itself is always emitted with its real
    value; suppressing it would delete the very signal that tells the FDA the keypoint is
    untrusted.
    """
    if fps <= 0:
        raise ConvertError("fps must be > 0, got {!r}".format(fps))

    groups = _likelihood_groups(position_to_name) if likelihood_threshold is not None else {}

    for index, row in enumerate(rows):
        t = start_t + index / fps
        suppressed = set()
        if likelihood_threshold is not None:
            for group in groups.values():
                likelihood_position = group["likelihood"]
                likelihood = row[likelihood_position]
                if likelihood is not None and likelihood < likelihood_threshold:
                    for coord_key in ("x", "y"):
                        position = group[coord_key]
                        if position is not None:
                            suppressed.add(position)

        values = {}
        for position, name in position_to_name.items():
            if position in suppressed:
                continue
            raw = row[position]
            if raw is None:
                continue
            values[name] = raw
        yield t, values


def write_wide_csv(path, header_names, rows, newline_utf8=True):
    """Write the wide replay CSV: header `t` followed by `header_names` in a stable sorted
    order, then one row per `(t, values)` in `rows`. Opens with `encoding="utf-8"` and
    `newline=""` (default `newline_utf8=True`) exactly as `replay_io` reads them -- Windows
    correctness, SDK-14c/e, since the vision box is a Windows machine. An absent value
    writes an EMPTY cell, never the string `None`, `nan` or `0`. Returns the number of rows
    written.
    """
    import csv

    sorted_names = sorted(header_names)
    open_kwargs = {"mode": "w"}
    if newline_utf8:
        open_kwargs["encoding"] = "utf-8"
        open_kwargs["newline"] = ""

    rows_written = 0
    with open(path, **open_kwargs) as handle:
        writer = csv.writer(handle)
        writer.writerow(["t"] + sorted_names)
        for t, values in rows:
            row = [str(t)]
            for name in sorted_names:
                value = values.get(name)
                row.append("" if value is None else str(value))
            writer.writerow(row)
            rows_written += 1
    return rows_written


def read_h5(path, key=None):
    """Read a DeepLabCut `.h5` export via `pandas.read_hdf` (the PyTables/"tables" backend
    -- the other common HDF5 binding is deliberately never imported, D-09c: it is absent
    from the target env and adding it there is avoidable). Returns
    `(list_of_column_tuples, iterator_of_row_tuples)` -- the column index and every row
    value are converted to plain Python via `_to_plain` (`.item()`), so nothing pandas- or
    numpy-typed crosses back into the pure core above.

    Raises `ConvertError`, naming `path`: when `pandas` cannot be imported (naming the
    `convert` extra to install); when the store holds more than one dataset and no `key`
    was given (listing the available keys and naming `--key`); or for any other
    `pandas.read_hdf` failure.
    """
    try:
        import pandas
    except ImportError as exc:
        raise ConvertError(
            "{}: pandas is required to read a DeepLabCut .h5 export; install the "
            '"convert" extra (python -m pip install "mics-dlc-link[convert]") -- ({})'.format(
                path, exc
            )
        )

    try:
        dataframe = pandas.read_hdf(path, key=key) if key else pandas.read_hdf(path)
    except ValueError as exc:
        message = str(exc)
        if "key" in message.lower():
            try:
                with pandas.HDFStore(path, mode="r") as store:
                    keys = list(store.keys())
            except Exception:
                keys = []
            raise ConvertError(
                "{}: the HDF5 store holds more than one dataset (keys: {!r}); pass --key "
                "to select one".format(path, keys)
            )
        raise ConvertError("{}: pandas.read_hdf failed: {}".format(path, exc))
    except Exception as exc:
        raise ConvertError("{}: pandas.read_hdf failed: {}".format(path, exc))

    columns = [tuple(_to_plain(level) for level in column) for column in dataframe.columns]
    rows = (
        tuple(_to_plain(value) for value in row)
        for row in dataframe.itertuples(index=False, name=None)
    )
    return columns, rows


def main(argv=None):
    """Thin re-export so `dlc-link-convert = dlc_link.convert:main` (pyproject.toml) keeps
    working; the real CLI lives in `dlc_link.convert_cli` (import deferred to avoid a
    module-load-time circular import, since that module imports from here)."""
    from dlc_link.convert_cli import main as _main

    return _main(argv)


if __name__ == "__main__":
    sys.exit(main())
