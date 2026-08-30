"""CSV/JSONL reader for mics-link's replay driver (Phase 34, Plan 07). Pure and
socket-free: reads a recorded `(t, signal, value)` file and yields the same tuple shape
`replay()` (mics_link/replay.py) consumes — split out of that module per its own <action>
block ("split the reader into mics_link/replay_io.py") to keep both files under the
project's 300-line cap; `read_rows`/`ReplayStats` stay importable from `mics_link.replay`
via re-export, so the public interface `<interfaces>` names is unaffected by the split.

Two file shapes, detected by header/keys, never by a flag (SDK-12 as amended 2026-08-30):
  long: columns/keys are exactly t, signal, value (extra columns ignored)
  wide: a "t" column plus one column per signal; every non-empty cell in a row becomes one
        (t, signal, value) tuple sharing that row's t. An empty cell is skipped SILENTLY —
        it means "no sample" (an occluded DLC keypoint is the motivating case), not a
        malformed row.
A header/keys containing "signal" without "value" is AMBIGUOUS (looks wide, but "signal" is
also the long format's own column name) and raises `MicsLinkError` — a file-level error,
not a row error.

A malformed row is counted (`stats.rows_malformed`) and skipped, never fatal (decision 3):
missing column/key, unparseable t, empty signal, unparseable JSON line, or a `{...}`-shaped
value (EVT-shaped content is out of scope here — decision 8, `mics_link/replay.py`). Only a
missing FILE raises, and only once the caller starts iterating (`read_rows` is a generator;
see `mics_link/replay.py`'s module docstring for why a missing file is fatal but a bad row
is not).

Windows correctness (SDK-14c/e): every file is opened with `encoding="utf-8"`, and CSV
additionally with `newline=""`; paths accept `str` or `os.PathLike` and are normalised
through `pathlib.Path`; suffix dispatch is case-insensitive (`Path(p).suffix.lower()`).
"""
import csv
import json
from pathlib import Path

from .errors import MicsLinkError
from .values import coerce_token


class ReplayStats:
    """Counts only — no latency/jitter/drift number anywhere (decision 5,
    `mics_link/replay.py`). `rows_read`/`rows_malformed` are filled in by `read_rows`;
    `sent`/`dropped`/`rejected` are filled in by `replay()` as it drives the client. One
    instance is shared across both by the caller (`main()` is the worked example).
    """

    def __init__(self):
        self.rows_read = 0
        self.rows_malformed = 0
        self.sent = 0
        self.dropped = 0
        self.rejected = 0

    def snapshot(self):
        return {
            "rows_read": self.rows_read,
            "rows_malformed": self.rows_malformed,
            "sent": self.sent,
            "dropped": self.dropped,
            "rejected": self.rejected,
        }


def read_rows(path, stats=None):
    """Generator yielding `(t: float, signal: str, value)` tuples from `path`. Dispatches
    on suffix, case-insensitively: `.jsonl`/`.json` -> JSONL, anything else -> CSV. Never
    raises for a bad ROW (see module docstring); raises `MicsLinkError` for a missing file
    or an ambiguous header — but, being a generator function, only once the caller starts
    iterating, not at call time (`inspect.isgenerator(read_rows(path))` is true immediately;
    nothing in this function's body runs before the first `next()`).
    """
    if stats is None:
        stats = ReplayStats()
    path = Path(path)
    if not path.exists():
        raise MicsLinkError("mics-link-replay: file not found: {}".format(path))
    if path.suffix.lower() in (".jsonl", ".json"):
        yield from _read_jsonl(path, stats)
    else:
        yield from _read_csv(path, stats)


# --- shape detection, shared by CSV headers and JSONL's first-record keys ---


def _detect_shape(field_names):
    fields = set(field_names)
    if "t" not in fields:
        raise MicsLinkError("mics-link-replay: header/keys missing required 't' column")
    if "value" in fields and "signal" in fields:
        return "long", None
    if "signal" in fields:
        raise MicsLinkError(
            "mics-link-replay: ambiguous header — a column named 'signal' is present "
            "without 'value', so this cannot be told apart from a wide (t + one column "
            "per signal) file that happens to have a signal named 'signal'"
        )
    return "wide", [name for name in field_names if name != "t"]


def _is_dict_shaped(text):
    """True if `text` parses as a JSON object — an EVT-shaped value, out of scope here
    (decision 8, `mics_link/replay.py`). `coerce_token(..., allow_json_dict=False)` would
    otherwise happily pass such text through as an ordinary (valid) string, silently
    admitting exactly the content this check exists to reject as malformed.
    """
    stripped = text.strip()
    if not (stripped.startswith("{") and stripped.endswith("}")):
        return False
    try:
        return isinstance(json.loads(stripped), dict)
    except ValueError:
        return False


# --- CSV ---


def _read_csv(path, stats):
    with open(path, "r", newline="", encoding="utf-8") as handle:
        reader = csv.DictReader(handle)
        if reader.fieldnames is None:
            return
        shape, signal_columns = _detect_shape(reader.fieldnames)
        for row in reader:
            tuples = (
                _parse_long_csv_row(row)
                if shape == "long"
                else _parse_wide_csv_row(row, signal_columns)
            )
            if tuples is None:
                stats.rows_malformed += 1
                continue
            stats.rows_read += 1
            for tup in tuples:
                yield tup


def _parse_long_csv_row(row):
    raw_t, raw_signal, raw_value = row.get("t"), row.get("signal"), row.get("value")
    if not raw_t or not raw_signal or not raw_value:
        return None
    if _is_dict_shaped(raw_value):
        return None
    try:
        t = float(raw_t)
    except (TypeError, ValueError):
        return None
    return [(t, raw_signal, coerce_token(raw_value, allow_json_dict=False))]


def _parse_wide_csv_row(row, signal_columns):
    raw_t = row.get("t")
    if not raw_t:
        return None
    try:
        t = float(raw_t)
    except (TypeError, ValueError):
        return None
    tuples = []
    for column in signal_columns:
        raw_value = row.get(column)
        if not raw_value or not raw_value.strip():
            continue  # empty cell: no sample this row, not a malformed row
        tuples.append((t, column, coerce_token(raw_value, allow_json_dict=False)))
    return tuples


# --- JSONL ---


def _read_jsonl(path, stats):
    # Shape (long vs wide) is decided ONCE, from the first parseable record's keys — a
    # file-level property, mirroring the CSV header. Unlike CSV, a wide JSONL record's OWN
    # key set is used per-line for its signal columns (not a fixed list from the first
    # record): JSON, unlike a CSV row, can simply omit a key for an occluded keypoint, and
    # forcing every line to carry every column seen on line one would defeat that.
    shape = None
    with open(path, "r", encoding="utf-8") as handle:
        for line in handle:
            line = line.strip()
            if not line:
                continue
            try:
                record = json.loads(line)
            except ValueError:
                stats.rows_malformed += 1
                continue
            if not isinstance(record, dict):
                stats.rows_malformed += 1
                continue
            if shape is None:
                shape, _ = _detect_shape(list(record.keys()))
            tuples = (
                _parse_long_json_record(record)
                if shape == "long"
                else _parse_wide_json_record(record)
            )
            if tuples is None:
                stats.rows_malformed += 1
                continue
            stats.rows_read += 1
            for tup in tuples:
                yield tup


def _parse_long_json_record(record):
    if "t" not in record or "signal" not in record or "value" not in record:
        return None
    signal, value = record["signal"], record["value"]
    if not isinstance(signal, str) or not signal or type(value) is dict:
        return None
    try:
        t = float(record["t"])
    except (TypeError, ValueError):
        return None
    return [(t, signal, value)]


def _parse_wide_json_record(record):
    if "t" not in record:
        return None
    try:
        t = float(record["t"])
    except (TypeError, ValueError):
        return None
    tuples = []
    for key, value in record.items():
        if key == "t":
            continue
        if value is None or value == "":
            continue  # empty cell equivalent: no sample this row
        tuples.append((t, key, value))
    return tuples
