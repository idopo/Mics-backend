"""Tests for dlc_link.convert / dlc_link.convert_cli (plan 35-05).

Task 1's tests use hand-built column tuples and row tuples -- no pandas anywhere -- so
they prove the flatten-and-write core on a machine with no pandas installed. Task 2 adds
`read_h5` (pandas-dependent, guarded by `pytest.importorskip` -- these SKIP on this dev
host, which is correct and expected, never mistake the skip for a broken test) and the
`dlc-link-convert` CLI (`dlc_link.convert_cli`).
"""
import csv
import os
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


# --- read_h5: pandas-dependent, expected to SKIP on this dev host -----------------------
# pandas and tables are both absent from this dev host (verified: `import pandas` and
# `import tables` both raise ModuleNotFoundError). The pytest.importorskip calls below make
# these tests SKIP here, which is correct and expected -- do not mistake the skip for a
# broken test. They exercise read_h5 for real wherever pandas/tables ARE installed (e.g.
# the vision box's DEEPLABCUT env, per 35-DLC-LIVE-NOTES.md).


def test_read_h5_round_trips_a_multiindex_dataframe(tmp_path):
    pandas = pytest.importorskip("pandas")
    pytest.importorskip("tables")
    from dlc_link.convert import read_h5

    columns = pandas.MultiIndex.from_tuples(
        [("scorerA", "nose", "x"), ("scorerA", "nose", "likelihood")],
        names=["scorer", "bodyparts", "coords"],
    )
    frame = pandas.DataFrame([[0.5, 0.9], [0.6, 0.8]], columns=columns)
    path = tmp_path / "export.h5"
    frame.to_hdf(path, key="df", mode="w")

    columns_out, rows_out = read_h5(path)
    assert columns_out == [("scorerA", "nose", "x"), ("scorerA", "nose", "likelihood")]
    rows_list = list(rows_out)
    assert rows_list == [(0.5, 0.9), (0.6, 0.8)]
    assert all(type(v) is float for row in rows_list for v in row)


def test_read_h5_multiple_keys_without_key_flag_raises_listing_keys(tmp_path):
    pandas = pytest.importorskip("pandas")
    pytest.importorskip("tables")
    from dlc_link.convert import ConvertError, read_h5

    path = tmp_path / "export.h5"
    pandas.DataFrame({"a": [1]}).to_hdf(path, key="one", mode="w")
    pandas.DataFrame({"a": [2]}).to_hdf(path, key="two", mode="a")

    with pytest.raises(ConvertError) as excinfo:
        read_h5(path)
    assert "--key" in str(excinfo.value)


def test_read_h5_with_key_selects_the_named_dataset(tmp_path):
    pandas = pytest.importorskip("pandas")
    pytest.importorskip("tables")
    from dlc_link.convert import read_h5

    path = tmp_path / "export.h5"
    pandas.DataFrame({"a": [1]}).to_hdf(path, key="one", mode="w")
    pandas.DataFrame({"a": [2]}).to_hdf(path, key="two", mode="a")

    columns_out, rows_out = read_h5(path, key="two")
    assert columns_out == [("a",)] or columns_out == ["a"]
    assert list(rows_out) == [(2,)]


def test_read_h5_absent_pandas_raises_naming_convert_extra(monkeypatch):
    import builtins

    from dlc_link.convert import ConvertError, read_h5

    real_import = builtins.__import__

    def _fake_import(name, *args, **kwargs):
        if name == "pandas":
            raise ImportError("no module named pandas")
        return real_import(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", _fake_import)
    with pytest.raises(ConvertError) as excinfo:
        read_h5("/nonexistent.h5")
    assert "convert" in str(excinfo.value)


def test_convert_module_has_no_h5py_reference():
    here = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    convert_py = os.path.join(here, "src", "dlc_link", "convert.py")
    with open(convert_py) as handle:
        text = handle.read()
    assert "h5py" not in text


# --- dlc-link-convert CLI: --help, argparse requiredness --------------------------------


def test_cli_help_lists_every_required_flag(capsys):
    from dlc_link.convert_cli import main as convert_main

    with pytest.raises(SystemExit) as excinfo:
        convert_main(["--help"])
    assert excinfo.value.code == 0
    out = capsys.readouterr().out
    for flag in (
        "--h5", "--signal-map", "--fps", "--out", "--key",
        "--likelihood-threshold", "--start-t", "--max-rows",
    ):
        assert flag in out


def test_cli_help_names_pcutoff_and_no_default_for_likelihood_threshold(capsys):
    from dlc_link.convert_cli import main as convert_main

    with pytest.raises(SystemExit):
        convert_main(["--help"])
    out = capsys.readouterr().out
    assert "pcutoff" in out
    assert "no default" in out.lower()


def test_cli_out_is_required_and_writes_nothing(tmp_path, monkeypatch):
    from dlc_link.convert_cli import main as convert_main

    empty_dir = tmp_path / "empty"
    empty_dir.mkdir()
    monkeypatch.chdir(empty_dir)
    with pytest.raises(SystemExit):
        convert_main(["--h5", "whatever.h5", "--signal-map", "whatever_signals.py", "--fps", "30"])
    assert list(empty_dir.iterdir()) == []


def test_cli_summary_has_no_latency_jitter_drift_or_elapsed_wording():
    here = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    convert_cli_py = os.path.join(here, "src", "dlc_link", "convert_cli.py")
    with open(convert_cli_py) as handle:
        text = handle.read().lower()
    for banned in ("latency", "jitter", "drift", "elapsed"):
        assert banned not in text


# --- D-44: refuse to write inside the DLC project (or a project root above the .h5) -----


def _snapshot(path):
    """{relpath: size} for every file under `path`, for a before/after comparison."""
    snap = {}
    for root, _dirs, files in os.walk(path):
        for name in files:
            full = os.path.join(root, name)
            snap[os.path.relpath(full, path)] = os.path.getsize(full)
    return snap


def test_out_inside_h5_own_directory_raises_d44(tmp_path):
    from dlc_link.convert_cli import _check_out_not_in_dlc_project

    project_dir = tmp_path / "project"
    project_dir.mkdir()
    before = _snapshot(project_dir)
    h5_path = project_dir / "videos" / "export.h5"
    h5_path.parent.mkdir(parents=True)
    out_path = h5_path.parent / "out.csv"
    with pytest.raises(ConvertError) as excinfo:
        _check_out_not_in_dlc_project(str(out_path), str(h5_path))
    assert "D-44" in str(excinfo.value)
    assert _snapshot(project_dir) == before


def test_out_inside_ancestor_project_root_detected_by_sibling_config_raises_d44(tmp_path):
    from dlc_link.convert_cli import _check_out_not_in_dlc_project

    project_dir = tmp_path / "MultiMice"
    (project_dir / "videos").mkdir(parents=True)
    (project_dir / "config.yaml").write_text("bodyparts: [nose]\n")
    before = _snapshot(project_dir)
    h5_path = project_dir / "videos" / "export.h5"
    out_path = project_dir / "scratch" / "out.csv"  # under the project root, not the h5's own dir
    with pytest.raises(ConvertError) as excinfo:
        _check_out_not_in_dlc_project(str(out_path), str(h5_path))
    assert "D-44" in str(excinfo.value)
    assert _snapshot(project_dir) == before


def test_out_outside_project_and_outside_h5_dir_succeeds(tmp_path):
    from dlc_link.convert_cli import _check_out_not_in_dlc_project

    project_dir = tmp_path / "MultiMice"
    (project_dir / "videos").mkdir(parents=True)
    (project_dir / "config.yaml").write_text("bodyparts: [nose]\n")
    h5_path = project_dir / "videos" / "export.h5"
    out_path = tmp_path / "scratch" / "out.csv"  # sibling of the project, not inside it
    _check_out_not_in_dlc_project(str(out_path), str(h5_path))  # must not raise


# --- Atomic write: temp file lives beside --out, never in cwd or the system temp root ----


def test_write_atomically_never_touches_cwd(tmp_path, monkeypatch):
    from dlc_link.convert_cli import _write_atomically

    empty_cwd = tmp_path / "empty_cwd"
    empty_cwd.mkdir()
    out_dir = tmp_path / "output"
    out_dir.mkdir()
    out_path = out_dir / "out.csv"
    monkeypatch.chdir(empty_cwd)

    rows_written = _write_atomically(str(out_path), ["nose_x"], [(0.0, {"nose_x": 0.5})])

    assert rows_written == 1
    assert out_path.exists()
    assert list(empty_cwd.iterdir()) == []
    assert set(os.listdir(out_dir)) == {"out.csv"}
