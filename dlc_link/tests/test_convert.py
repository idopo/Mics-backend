"""Tests for dlc_link.convert (plan 35-05, Task 1: the pure flatten-and-write core).

These tests use hand-built column tuples and row tuples -- no pandas anywhere -- so they
prove the flatten-and-write core on a machine with no pandas installed. Task 2 adds
`read_h5` (pandas-dependent, guarded by `pytest.importorskip`) and the CLI to this file.
"""
import csv
from types import SimpleNamespace

import pytest

from dlc_link.convert import ConvertError, flatten_columns, rows_to_wide, write_wide_csv


def _smap(signals):
    return SimpleNamespace(SIGNALS=signals)


def _nose_left_paw_signals():
    return {
        "nose": {"index": 0, "signals": {"likelihood": "nose_likelihood", "x": "nose_x", "y": "nose_y"}},
        "left_paw": {
            "index": 1,
            "signals": {"likelihood": "left_paw_likelihood", "x": "left_paw_x", "y": "left_paw_y"},
        },
    }


# --- flatten_columns: 3-level single-animal -------------------------------------------


def test_three_level_single_animal_flattens_expected_names():
    columns = [
        ("scorerA", "nose", "x"),
        ("scorerA", "nose", "y"),
        ("scorerA", "nose", "likelihood"),
        ("scorerA", "left_paw", "x"),
        ("scorerA", "left_paw", "y"),
        ("scorerA", "left_paw", "likelihood"),
    ]
    position_to_name, counts = flatten_columns(columns, _smap(_nose_left_paw_signals()))
    assert position_to_name == {
        0: "nose_x",
        1: "nose_y",
        2: "nose_likelihood",
        3: "left_paw_x",
        4: "left_paw_y",
        5: "left_paw_likelihood",
    }
    assert counts == {"bodyparts_skipped_undeclared": 0, "coords_skipped_unrecognised": 0}


# --- flatten_columns: 4-level multi-animal, "single" only -----------------------------


def test_four_level_single_only_individual_flattens_identically_to_three_level():
    """This is the LED_on/LED_off unique-bodypart demo case: unique bodyparts live under
    the individual literally named 'single'."""
    signals = {
        "LED_on": {"index": 0, "signals": {"likelihood": "led_on_likelihood"}},
        "LED_off": {"index": 1, "signals": {"likelihood": "led_off_likelihood"}},
    }
    columns_4level = [
        ("scorerA", "single", "LED_on", "likelihood"),
        ("scorerA", "single", "LED_off", "likelihood"),
    ]
    columns_3level = [
        ("scorerA", "LED_on", "likelihood"),
        ("scorerA", "LED_off", "likelihood"),
    ]
    result_4, counts_4 = flatten_columns(columns_4level, _smap(signals))
    result_3, counts_3 = flatten_columns(columns_3level, _smap(signals))
    assert result_4 == result_3 == {0: "led_on_likelihood", 1: "led_off_likelihood"}
    assert counts_4 == counts_3


def test_four_level_single_plus_one_real_individual_accepted():
    signals = {
        "LED_on": {"index": 0, "signals": {"likelihood": "led_on_likelihood"}},
        "nose": {"index": 1, "signals": {"likelihood": "nose_likelihood", "x": "nose_x", "y": "nose_y"}},
    }
    columns = [
        ("scorerA", "single", "LED_on", "likelihood"),
        ("scorerA", "1", "nose", "x"),
        ("scorerA", "1", "nose", "y"),
        ("scorerA", "1", "nose", "likelihood"),
    ]
    position_to_name, _ = flatten_columns(columns, _smap(signals))
    assert position_to_name == {0: "led_on_likelihood", 1: "nose_x", 2: "nose_y", 3: "nose_likelihood"}


def test_four_level_two_real_individuals_raises_naming_single_animal_true():
    signals = {"nose": {"index": 0, "signals": {"likelihood": "nose_likelihood"}}}
    columns = [
        ("scorerA", "1", "nose", "likelihood"),
        ("scorerA", "2", "nose", "likelihood"),
    ]
    with pytest.raises(ConvertError) as excinfo:
        flatten_columns(columns, _smap(signals))
    message = str(excinfo.value)
    assert "single_animal=True" in message
    assert "'1'" in message and "'2'" in message


# --- flatten_columns: skip/raise rules -------------------------------------------------


def test_bodypart_in_file_but_not_in_map_is_skipped_and_counted():
    columns = [
        ("scorerA", "nose", "likelihood"),
        ("scorerA", "tail_base", "likelihood"),
    ]
    signals = {"nose": {"index": 0, "signals": {"likelihood": "nose_likelihood"}}}
    position_to_name, counts = flatten_columns(columns, _smap(signals))
    assert position_to_name == {0: "nose_likelihood"}
    assert counts["bodyparts_skipped_undeclared"] == 1


def test_bodypart_in_map_but_not_in_file_raises_naming_it():
    columns = [("scorerA", "nose", "likelihood")]
    signals = {
        "nose": {"index": 0, "signals": {"likelihood": "nose_likelihood"}},
        "left_paw": {"index": 1, "signals": {"likelihood": "left_paw_likelihood"}},
    }
    with pytest.raises(ConvertError) as excinfo:
        flatten_columns(columns, _smap(signals))
    assert "left_paw" in str(excinfo.value)


def test_coord_z_is_skipped_and_counted():
    columns = [
        ("scorerA", "nose", "likelihood"),
        ("scorerA", "nose", "z"),
    ]
    signals = {"nose": {"index": 0, "signals": {"likelihood": "nose_likelihood"}}}
    position_to_name, counts = flatten_columns(columns, _smap(signals))
    assert position_to_name == {0: "nose_likelihood"}
    assert counts["coords_skipped_unrecognised"] == 1


def test_no_produced_column_is_named_signal():
    columns = [("scorerA", "nose", "likelihood")]
    signals = {"nose": {"index": 0, "signals": {"likelihood": "signal"}}}
    with pytest.raises(ConvertError) as excinfo:
        flatten_columns(columns, _smap(signals))
    assert "signal" in str(excinfo.value)


# --- rows_to_wide -----------------------------------------------------------------------


def test_rows_to_wide_t_values_are_index_over_fps():
    position_to_name = {0: "nose_likelihood"}
    rows = [(0.9,), (0.8,), (0.7,)]
    out = list(rows_to_wide(rows, position_to_name, fps=10))
    assert [t for t, _ in out] == [0.0, 0.1, 0.2]


def test_rows_to_wide_start_t_offsets_the_schedule():
    position_to_name = {0: "nose_likelihood"}
    rows = [(0.9,)]
    out = list(rows_to_wide(rows, position_to_name, fps=10, start_t=5.0))
    assert out[0][0] == 5.0


def test_rows_to_wide_rejects_non_positive_fps():
    with pytest.raises(ConvertError):
        list(rows_to_wide([(0.9,)], {0: "nose_likelihood"}, fps=0))


def test_rows_to_wide_below_threshold_emits_empty_xy_but_populated_likelihood():
    position_to_name = {0: "nose_x", 1: "nose_y", 2: "nose_likelihood"}
    rows = [
        (0.5, 0.6, 0.95),  # confident
        (0.5, 0.6, 0.02),  # occluded: below threshold
        (0.5, 0.6, 0.91),  # confident again
    ]
    out = list(rows_to_wide(rows, position_to_name, fps=1, likelihood_threshold=0.5))
    confident, occluded, confident_again = out
    assert confident[1] == {"nose_x": 0.5, "nose_y": 0.6, "nose_likelihood": 0.95}
    assert occluded[1] == {"nose_likelihood": 0.02}
    assert "nose_x" not in occluded[1]
    assert "nose_y" not in occluded[1]
    assert confident_again[1] == {"nose_x": 0.5, "nose_y": 0.6, "nose_likelihood": 0.91}


def test_rows_to_wide_no_threshold_never_suppresses():
    position_to_name = {0: "nose_x", 1: "nose_y", 2: "nose_likelihood"}
    rows = [(0.5, 0.6, 0.01)]
    out = list(rows_to_wide(rows, position_to_name, fps=1, likelihood_threshold=None))
    assert out[0][1] == {"nose_x": 0.5, "nose_y": 0.6, "nose_likelihood": 0.01}


# --- write_wide_csv ----------------------------------------------------------------------


def test_write_wide_csv_header_first_field_is_t_and_no_field_is_signal(tmp_path):
    path = tmp_path / "out.csv"
    write_wide_csv(path, ["nose_x", "nose_likelihood"], [(0.0, {"nose_x": 0.5, "nose_likelihood": 0.9})])
    with open(path, newline="", encoding="utf-8") as handle:
        header = next(csv.reader(handle))
    assert header[0] == "t"
    assert "signal" not in header


def test_write_wide_csv_absent_value_writes_zero_length_field(tmp_path):
    path = tmp_path / "out.csv"
    write_wide_csv(
        path,
        ["nose_x", "nose_y", "nose_likelihood"],
        [(0.0, {"nose_likelihood": 0.02})],
    )
    with open(path, newline="", encoding="utf-8") as handle:
        reader = csv.DictReader(handle)
        row = next(reader)
    assert row["nose_x"] == ""
    assert row["nose_y"] == ""
    assert row["nose_likelihood"] == "0.02"


def test_write_wide_csv_returns_rows_written_count(tmp_path):
    path = tmp_path / "out.csv"
    n = write_wide_csv(path, ["nose_likelihood"], [(0.0, {"nose_likelihood": 0.9}), (0.1, {"nose_likelihood": 0.8})])
    assert n == 2


def test_write_wide_csv_sorts_header_names(tmp_path):
    path = tmp_path / "out.csv"
    write_wide_csv(path, ["nose_y", "nose_x"], [(0.0, {"nose_x": 1.0, "nose_y": 2.0})])
    with open(path, newline="", encoding="utf-8") as handle:
        header = next(csv.reader(handle))
    assert header == ["t", "nose_x", "nose_y"]
