"""Replay entry point (Phase 34, Plan 07, SDK-12). Two halves, matching the plan's two
tasks: reader (CSV/JSONL -> (t, signal, value) tuples, this file's top section) and
timing/CLI (`replay()`/`main()`, lower section — `mics_link.timing.Pacer` itself has its
own dedicated `test_timing.py`, mirroring how `heartbeat.py` gets `test_heartbeat_scheduling.py`).

Every timing test here uses an injected recording `sleep` and a fake `clock` — nothing in
this suite actually waits. The client is always driven as `MicsLink(FakeTransport(),
autostart=False)`, pumping `_io_once()` by hand where a test needs to see what actually
reached the transport, not just what `send_signal` returned.
"""
import inspect
import os

import pytest

from mics_link.errors import MicsLinkError
from mics_link.replay import ReplayStats, read_rows

FIXTURES = os.path.join(os.path.dirname(__file__), "fixtures")


def _fixture(name):
    return os.path.join(FIXTURES, name)


def _rows(path):
    return list(read_rows(path))


# --- long format: CSV and JSONL agree ---


def test_long_csv_reads_five_rows_with_exact_python_types():
    rows = _rows(_fixture("replay_sample.csv"))
    assert len(rows) == 5
    t, signal, value = rows[0]
    assert t == pytest.approx(0.0)
    assert signal == "nose_p"
    assert type(value) is float and value == pytest.approx(0.98)
    # row 2 (index 2): int
    assert rows[2][1] == "count" and type(rows[2][2]) is int and rows[2][2] == 3
    # row 3 (index 3): bool — must be bool, not 1/0
    assert rows[3][1] == "visible" and type(rows[3][2]) is bool and rows[3][2] is True
    # row 4 (index 4): string
    assert rows[4][1] == "label" and type(rows[4][2]) is str and rows[4][2] == "left"


def test_long_jsonl_reads_identically_to_long_csv():
    csv_rows = _rows(_fixture("replay_sample.csv"))
    jsonl_rows = _rows(_fixture("replay_sample.jsonl"))
    assert csv_rows == jsonl_rows
    for _, _, value in jsonl_rows:
        assert type(value) in (float, int, bool, str)


def test_wide_csv_produces_the_same_tuples_as_long_csv():
    long_rows = _rows(_fixture("replay_sample.csv"))
    wide_rows = _rows(_fixture("replay_sample_wide.csv"))
    assert wide_rows == long_rows


def test_wide_jsonl_produces_the_same_tuples_as_long_csv():
    long_rows = _rows(_fixture("replay_sample.csv"))
    wide_rows = _rows(_fixture("replay_sample_wide.jsonl"))
    assert wide_rows == long_rows


def test_wide_csv_empty_cell_is_skipped_silently_not_malformed():
    stats = ReplayStats()
    rows = list(read_rows(_fixture("replay_sample_wide.csv"), stats=stats))
    assert len(rows) == 5  # 2 signals @ t=0.00 + 3 signals @ t=0.03, no empty-cell tuples
    assert stats.rows_malformed == 0


def test_ambiguous_wide_header_with_a_column_named_signal_raises(tmp_path):
    path = tmp_path / "ambiguous.csv"
    path.write_text("t,signal,other\n0.0,x,1\n", encoding="utf-8", newline="")
    with pytest.raises(MicsLinkError):
        list(read_rows(path))


# --- column order / extra columns (decision 1) ---


def test_column_order_signal_t_value_still_reads_correctly(tmp_path):
    path = tmp_path / "reordered.csv"
    path.write_text("signal,t,value\nfoo,1.5,2.5\n", encoding="utf-8", newline="")
    rows = _rows(path)
    assert rows == [(1.5, "foo", 2.5)]


def test_extra_column_is_ignored_not_an_error(tmp_path):
    path = tmp_path / "extra.csv"
    path.write_text(
        "t,signal,value,confidence\n0.0,foo,1.0,0.99\n", encoding="utf-8", newline=""
    )
    stats = ReplayStats()
    rows = list(read_rows(path, stats=stats))
    assert rows == [(0.0, "foo", 1.0)]
    assert stats.rows_malformed == 0


# --- malformed rows never abort a replay (decision 3) ---


def test_malformed_csv_yields_only_good_rows_with_accurate_count():
    stats = ReplayStats()
    rows = list(read_rows(_fixture("replay_malformed.csv"), stats=stats))
    assert [r[1] for r in rows] == ["good1", "good2"]
    assert stats.rows_malformed == 4
    assert stats.rows_read == 2


def test_jsonl_line_that_is_not_json_counts_one_malformed_row_and_continues(tmp_path):
    path = tmp_path / "bad.jsonl"
    path.write_text(
        'not json at all\n{"t": 0.0, "signal": "ok", "value": 1}\n', encoding="utf-8"
    )
    stats = ReplayStats()
    rows = list(read_rows(path, stats=stats))
    assert rows == [(0.0, "ok", 1)]
    assert stats.rows_malformed == 1


def test_jsonl_dict_value_is_malformed_not_an_event(tmp_path):
    path = tmp_path / "evt_shaped.jsonl"
    path.write_text(
        '{"t": 0.0, "signal": "ok", "value": 1}\n'
        '{"t": 0.1, "signal": "bad", "value": {"nested": true}}\n',
        encoding="utf-8",
    )
    stats = ReplayStats()
    rows = list(read_rows(path, stats=stats))
    assert rows == [(0.0, "ok", 1)]
    assert stats.rows_malformed == 1


# --- empty files (decision 3) ---


def test_empty_file_yields_zero_rows_no_exception(tmp_path):
    path = tmp_path / "empty.csv"
    path.write_text("", encoding="utf-8", newline="")
    assert _rows(path) == []


def test_header_only_csv_yields_zero_rows_no_exception(tmp_path):
    path = tmp_path / "header_only.csv"
    path.write_text("t,signal,value\n", encoding="utf-8", newline="")
    assert _rows(path) == []


# --- missing file is fatal, a bad row is not (decision 3) ---


def test_nonexistent_file_raises_mics_link_error_on_iteration(tmp_path):
    missing = tmp_path / "does_not_exist.csv"
    with pytest.raises(MicsLinkError):
        list(read_rows(missing))


# --- read_rows is a generator, not a list (memory-bounded reading) ---


def test_read_rows_is_a_generator_not_a_list():
    result = read_rows(_fixture("replay_sample.csv"))
    assert inspect.isgenerator(result)


# --- Windows correctness: utf-8 + newline='', pathlib, case-insensitive suffix, spaces ---


def test_path_with_a_space_reads_correctly(tmp_path):
    sub = tmp_path / "dir with space"
    sub.mkdir()
    path = sub / "sample file.csv"
    path.write_text("t,signal,value\n0.0,foo,1.0\n", encoding="utf-8", newline="")
    assert _rows(path) == [(0.0, "foo", 1.0)]


def test_suffix_dispatch_is_case_insensitive(tmp_path):
    path = tmp_path / "SAMPLE.JSONL"
    path.write_text('{"t": 0.0, "signal": "foo", "value": 1}\n', encoding="utf-8")
    assert _rows(path) == [(0.0, "foo", 1)]


def test_read_rows_accepts_a_plain_str_path_not_only_pathlike():
    rows = _rows(str(_fixture("replay_sample.csv")))
    assert len(rows) == 5
