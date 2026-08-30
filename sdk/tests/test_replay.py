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
import re

import pytest

import mics_link.replay as replay_module
from mics_link.client import MicsLink
from mics_link.errors import MicsLinkError
from mics_link.replay import ReplayStats, main, read_rows, replay

from fake_transport import FakeTransport

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


# ============================================================================
# Task 2: timing modes, replay(), main() and the console-script entry point
# ============================================================================


def _paced_clock_and_sleep(start=0.0):
    box = [start]
    calls = []

    def clock():
        return box[0]

    def sleep(seconds):
        calls.append(seconds)
        box[0] += seconds

    return clock, sleep, calls


def _link(**kwargs):
    kwargs.setdefault("heartbeat_s", 9999.0)  # keep the mandatory initial HB off the wire
    transport = FakeTransport()
    return MicsLink(transport, autostart=False, **kwargs), transport


# --- three timing modes, driven through replay() directly ---


def test_replay_fast_mode_never_sleeps_and_sends_every_row():
    link, transport = _link()
    calls = []
    rows = [(0.0, "a", 1), (0.5, "b", 2), (1.5, "c", 3)]
    stats = replay(link, rows, mode="fast", sleep=lambda s: calls.append(s))
    assert calls == []
    assert stats.sent == 3
    link._io_once()
    assert len(transport.sent) == 3


def test_replay_realtime_mode_sleeps_expected_origin_relative_deltas():
    link, _transport = _link()
    clock, sleep, calls = _paced_clock_and_sleep()
    rows = [(0.0, "a", 1), (0.5, "b", 2), (1.5, "c", 3)]
    replay(link, rows, mode="realtime", sleep=sleep, clock=clock)
    assert calls == pytest.approx([0.5, 1.0])


def test_replay_scaled_mode_scale_2_halves_the_sleeps():
    link, _transport = _link()
    clock, sleep, calls = _paced_clock_and_sleep()
    rows = [(0.0, "a", 1), (0.5, "b", 2), (1.5, "c", 3)]
    replay(link, rows, mode="scaled", scale=2.0, sleep=sleep, clock=clock)
    assert calls == pytest.approx([0.25, 0.5])


def test_replay_scaled_mode_scale_half_doubles_the_sleeps():
    link, _transport = _link()
    clock, sleep, calls = _paced_clock_and_sleep()
    rows = [(0.0, "a", 1), (0.5, "b", 2), (1.5, "c", 3)]
    replay(link, rows, mode="scaled", scale=0.5, sleep=sleep, clock=clock)
    assert calls == pytest.approx([1.0, 2.0])


def test_replay_falling_behind_sends_every_row_with_no_negative_sleep():
    link, _transport = _link()
    box = [0.0]
    calls = []

    def clock():
        return box[0]

    def sleep(seconds):
        calls.append(seconds)
        box[0] += seconds

    def _rows():
        yield (0.0, "a", 1)
        box[0] += 10.0  # a slow iteration eats into the schedule on its own
        yield (0.5, "b", 2)

    stats = replay(link, _rows(), mode="realtime", sleep=sleep, clock=clock)
    assert calls == []
    assert stats.sent == 2


# --- ReplayStats: reader + sender counters share one object ---


def test_replay_stats_over_sample_csv_all_sent_none_dropped_or_rejected():
    link, _transport = _link()
    stats = ReplayStats()
    rows = read_rows(_fixture("replay_sample.csv"), stats=stats)
    replay(link, rows, mode="fast", stats=stats)
    assert stats.rows_read == 5
    assert stats.sent == 5
    assert stats.dropped == 0
    assert stats.rejected == 0


def test_replay_continues_past_a_dropped_row_when_the_queue_is_full():
    link, _transport = _link(queue_size=1)
    rows = [(0.0, "a", 1), (0.0, "b", 2), (0.0, "c", 3)]
    stats = replay(link, rows, mode="fast")
    assert stats.sent == 1
    assert stats.dropped == 2


def test_replay_continues_past_a_rejected_value_and_invalid_value_error_never_escapes():
    link, _transport = _link()
    rows = [(0.0, "a", 1), (0.1, "bad", [1, 2]), (0.2, "c", 3)]
    stats = replay(link, rows, mode="fast")  # must not raise InvalidValueError
    assert stats.rejected == 1
    assert stats.sent == 2


# --- main() / CLI ---


def test_main_fast_mode_returns_zero_and_prints_counts_with_no_timing_claim(
    monkeypatch, capsys
):
    link, _transport = _link()
    monkeypatch.setattr(replay_module, "connect", lambda *a, **k: link)
    rc = main(
        [
            "--host", "h", "--port", "5599", "--source-id", "demo",
            "--file", _fixture("replay_sample.csv"), "--mode", "fast",
        ]
    )
    assert rc == 0
    out = capsys.readouterr().out
    assert "sent" in out and "rows_malformed" in out
    assert re.search(r"laten|jitter|drift|ms\b", out, re.IGNORECASE) is None


def test_main_rejects_non_positive_scale_with_clear_message_and_nonzero_exit(capsys):
    rc = main(
        [
            "--host", "h", "--port", "5599", "--source-id", "demo",
            "--file", _fixture("replay_sample.csv"), "--mode", "scaled", "--scale", "0",
        ]
    )
    assert rc != 0
    assert "scale" in capsys.readouterr().err.lower()


@pytest.mark.parametrize("mode", ["realtime", "fast"])
def test_main_rejects_non_positive_scale_outside_scaled_mode_too(mode, capsys):
    """WR-03: main()'s docstring says "never raises", but the old guard only checked
    `--scale` when `--mode scaled` — Pacer itself validates scale unconditionally, so
    `--mode realtime`/`--mode fast` with a bad scale reached Pacer.__init__ and raised an
    uncaught ValueError instead of the documented clean exit(2) + stderr message.
    """
    rc = main(
        [
            "--host", "h", "--port", "5599", "--source-id", "demo",
            "--file", _fixture("replay_sample.csv"), "--mode", mode, "--scale", "-1",
        ]
    )
    assert rc != 0
    assert "scale" in capsys.readouterr().err.lower()


def test_main_nonexistent_file_exits_nonzero_with_clear_message(tmp_path, capsys):
    rc = main(
        [
            "--host", "h", "--port", "5599", "--source-id", "demo",
            "--file", str(tmp_path / "does_not_exist.csv"),
        ]
    )
    assert rc != 0
    assert "not found" in capsys.readouterr().err.lower()


def test_help_exits_zero_and_never_reaches_connect(monkeypatch):
    def _boom(*_args, **_kwargs):
        raise AssertionError("connect() must not be called for --help")

    monkeypatch.setattr(replay_module, "connect", _boom)
    with pytest.raises(SystemExit) as exc_info:
        main(["--help"])
    assert exc_info.value.code == 0


def test_main_entry_point_resolves_from_pyproject():
    """`mics-link-replay = mics_link.replay:main` (pyproject.toml [project.scripts]) — the
    dangling entry point plan 34-01 declared. Proves the target actually exists and is
    callable, without requiring an install.
    """
    assert callable(replay_module.main)

