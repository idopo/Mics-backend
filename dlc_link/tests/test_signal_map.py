"""Tests for dlc_link.signal_map (Task 1, plan 35-04)."""
import os
import re

import pytest

from dlc_link.config_read import read_dlc_config
from dlc_link.generate import generate
from dlc_link.names import flat_signal_names
from dlc_link.signal_map import SignalMapError, assert_pairs_with, load_signal_map

FIXTURES = os.path.join(os.path.dirname(__file__), "fixtures")
MADLC_CONFIG = os.path.join(FIXTURES, "dlc3_multianimal_config.yaml")
POSE_ORDER_FILE = os.path.join(FIXTURES, "pose_order_declared.txt")


def _pose_order():
    with open(POSE_ORDER_FILE) as handle:
        return [
            line.strip() for line in handle if line.strip() and not line.strip().startswith("#")
        ]


def _generate(**overrides):
    kwargs = dict(
        source=read_dlc_config(MADLC_CONFIG),
        pose_order=_pose_order(),
        pose_order_source="probe",
        wanted=["LED_on", "LED_off"],
        coords_for={"LED_on"},
        source_id="dlc_cam1",
    )
    kwargs.update(overrides)
    return generate(**kwargs)


def _write_map(tmp_path, map_source, name="dlc_cam1_signals.py"):
    path = tmp_path / name
    path.write_text(map_source)
    return path


def _corrupt_line(source, prefix, replacement):
    """Replace the single line starting with `prefix` (mirrors what
    `render_signal_map` emits: one `NAME = ...` statement per line)."""
    pattern = re.compile(r"^{}.*$".format(re.escape(prefix)), re.MULTILINE)
    new_source, count = pattern.subn(replacement, source, count=1)
    assert count == 1, "expected exactly one line starting with {!r}".format(prefix)
    return new_source


def test_round_trip_all_constants(tmp_path):
    result = _generate()
    path = _write_map(tmp_path, result.map_source)
    smap = load_signal_map(path)

    assert smap.SOURCE_ID == "dlc_cam1"
    assert smap.CLASS_NAME == result.provenance["class_name"]
    assert set(smap.SIGNAL_NAMES) == set(flat_signal_names(result.name_map))
    assert smap.LIB_SHA256 == result.lib_sha256
    assert smap.POSE_ORDER == _pose_order()
    assert smap.POSE_ORDER_SOURCE == "probe"
    assert smap.ENGINE == "pytorch"


def test_corrupted_signal_names_raises(tmp_path):
    result = _generate()
    corrupted = _corrupt_line(result.map_source, "SIGNAL_NAMES = ", "SIGNAL_NAMES = ['bogus_signal']")
    path = _write_map(tmp_path, corrupted)
    with pytest.raises(SignalMapError):
        load_signal_map(path)


def test_duplicated_index_raises(tmp_path):
    result = _generate()
    signals = {k: dict(v) for k, v in result.name_map.items()}
    bodyparts = list(signals)
    signals[bodyparts[1]]["index"] = signals[bodyparts[0]]["index"]
    corrupted = _corrupt_line(result.map_source, "SIGNALS = ", "SIGNALS = {!r}".format(signals))
    path = _write_map(tmp_path, corrupted)
    with pytest.raises(SignalMapError):
        load_signal_map(path)


def test_missing_required_constant_raises(tmp_path):
    result = _generate()
    corrupted = _corrupt_line(result.map_source, "LIB_SHA256 = ", "")
    path = _write_map(tmp_path, corrupted)
    with pytest.raises(SignalMapError):
        load_signal_map(path)


def test_signals_not_a_dict_raises(tmp_path):
    result = _generate()
    corrupted = _corrupt_line(result.map_source, "SIGNALS = ", "SIGNALS = ['not', 'a', 'dict']")
    path = _write_map(tmp_path, corrupted)
    with pytest.raises(SignalMapError):
        load_signal_map(path)


def test_unparseable_file_raises(tmp_path):
    path = tmp_path / "broken_signals.py"
    path.write_text("this is not ( valid python")
    with pytest.raises(SignalMapError):
        load_signal_map(path)


def test_assert_pairs_with_passes_for_paired_source_and_raises_for_mismatch(tmp_path):
    result = _generate()
    path = _write_map(tmp_path, result.map_source)
    smap = load_signal_map(path)

    assert_pairs_with(smap, result.lib_source)  # must not raise

    last_char = result.lib_source[-1]
    flipped = "X" if last_char != "X" else "Y"
    corrupted_lib = result.lib_source[:-1] + flipped
    with pytest.raises(SignalMapError):
        assert_pairs_with(smap, corrupted_lib)


def test_loader_never_rederives_a_name():
    import inspect

    from dlc_link import signal_map

    source = inspect.getsource(signal_map)
    # The loader reads what the generator emitted; it never re-derives a bodypart name.
    assert "to_ident" not in source
    assert "build_name_map" not in source
