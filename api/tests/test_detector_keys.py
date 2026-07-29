"""Tests for detector_keys.py (Plan 25-01 Tasks 1-2) and fda_utils.scan_fda_condition_operands
(Plan 25-01 Task 3).

Pure — no DB, no TestClient (module_detector_channels tests use a FakeDb stub).
"""
import pytest

from detector_keys import derive_channels, derive_view_keys

# ---------------------------------------------------------------------------
# GOLDEN DERIVATION TABLE — identical in plan 02's Pi twin
# (~/pi-mirror/tests/test_detector_view_keys.py). Change one, change both.
# ---------------------------------------------------------------------------

GOLDEN_CASES = [
    ({"device_name": "LICKER", "num_detectors": 4}, [0, 1, 2, 3], ["LICKER0", "LICKER1", "LICKER2", "LICKER3"]),
    ({"device_name": "LICKER", "num_detectors": 4, "first_channel": 0}, [0, 1, 2, 3], ["LICKER0", "LICKER1", "LICKER2", "LICKER3"]),
    ({"device_name": "LICKER", "num_detectors": 4, "first_channel": None}, [0, 1, 2, 3], ["LICKER0", "LICKER1", "LICKER2", "LICKER3"]),
    ({"device_name": "LICKER", "num_detectors": 4, "first_channel": 1}, [1, 2, 3, 4], ["LICKER1", "LICKER2", "LICKER3", "LICKER4"]),
    ({"device_name": "LICKER", "num_detectors": 1, "first_channel": 11}, [11], ["LICKER11"]),
    ({"device_name": "TONGUE", "num_detectors": 2, "first_channel": 3}, [3, 4], ["TONGUE3", "TONGUE4"]),
    ({"device_name": "LICKER", "num_detectors": "4", "first_channel": "1"}, [1, 2, 3, 4], ["LICKER1", "LICKER2", "LICKER3", "LICKER4"]),
    ({"device_name": "LICKER"}, [], []),
    ({"num_detectors": 4}, [], []),
    ({"device_name": "", "num_detectors": 4}, [], []),
    ({"device_name": "LICKER", "num_detectors": 0}, [], []),
    ({"device_name": "LICKER", "num_detectors": -1}, [], []),
    ({"device_name": "LICKER", "num_detectors": True}, [], []),
    ({"device_name": "LICKER", "num_detectors": 4, "first_channel": -1}, [], []),
    ({"device_name": "LICKER", "num_detectors": 4, "first_channel": "x"}, [], []),
    ({"device_name": "LICKER", "num_detectors": 4, "first_channel": True}, [], []),
    ({}, [], []),
    (None, [], []),
]


@pytest.mark.parametrize("config,expected_channels,expected_keys", GOLDEN_CASES)
def test_golden_table(config, expected_channels, expected_keys):
    assert derive_channels(config) == expected_channels
    assert derive_view_keys(config) == expected_keys
    assert len(derive_channels(config)) == len(derive_view_keys(config))


def test_extra_config_keys_ignored():
    config = {
        "device_name": "LICKER", "num_detectors": 4, "class_name": "Touch_Detector",
        "address": True, "name": "MPR121", "type": "I2C", "group": "Modules",
    }
    assert derive_channels(config) == [0, 1, 2, 3]
    assert derive_view_keys(config) == ["LICKER0", "LICKER1", "LICKER2", "LICKER3"]


@pytest.mark.parametrize("bad_input", [1, "not a dict", [], True, 3.5, object()])
def test_non_dict_input_never_raises(bad_input):
    assert derive_channels(bad_input) == []
    assert derive_view_keys(bad_input) == []
