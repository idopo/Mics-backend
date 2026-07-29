"""Tests for detector_keys.py (Plan 25-01 Tasks 1-2) and fda_utils.scan_fda_condition_operands
(Plan 25-01 Task 3).

Pure — no DB, no TestClient (module_detector_channels tests use a FakeDb stub).
"""
from types import SimpleNamespace

import pytest

from detector_keys import derive_channels, derive_view_keys, module_detector_channels

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


# ---------------------------------------------------------------------------
# module_detector_channels — advisory cross-pilot union with surfaced disagreement
# (Plan 25-01 Task 2)
# ---------------------------------------------------------------------------

class FakeDb:
    """Stands in for the caller-owned SQLAlchemy session. `rows` are SimpleNamespace with
    module_name / pilot_id / pilot_name / config, matching what the real join returns."""

    def __init__(self, rows):
        self._rows = rows
        self.execute_calls = 0

    def execute(self, *_args, **_kwargs):
        self.execute_calls += 1
        return SimpleNamespace(fetchall=lambda: self._rows)


def _row(module_name, pilot_id, pilot_name, config):
    return SimpleNamespace(module_name=module_name, pilot_id=pilot_id, pilot_name=pilot_name, config=config)


def test_two_pilots_identical_config_no_conflict():
    rows = [
        _row("MPR121", 1, "pilot_a", {"device_name": "LICKER", "num_detectors": 4}),
        _row("MPR121", 2, "pilot_b", {"device_name": "LICKER", "num_detectors": 4}),
    ]
    result = module_detector_channels(FakeDb(rows), ["MPR121"])
    assert len(result) == 1
    entry = result[0]
    assert entry["module_name"] == "MPR121"
    assert entry["channels"] == [0, 1, 2, 3]
    assert entry["keys"] == ["LICKER0", "LICKER1", "LICKER2", "LICKER3"]
    assert entry["conflict"] is False
    assert len(entry["by_pilot"]) == 2


def test_two_pilots_differing_num_detectors_conflict_union_channels():
    rows = [
        _row("MPR121", 1, "pilot_a", {"device_name": "LICKER", "num_detectors": 4}),
        _row("MPR121", 2, "pilot_b", {"device_name": "LICKER", "num_detectors": 3}),
    ]
    entry = module_detector_channels(FakeDb(rows), ["MPR121"])[0]
    assert entry["channels"] == [0, 1, 2, 3]
    assert entry["keys"] == ["LICKER0", "LICKER1", "LICKER2", "LICKER3"]
    assert entry["conflict"] is True


def test_two_pilots_differing_first_channel_conflict_union_channels():
    rows = [
        _row("MPR121", 1, "pilot_a", {"device_name": "LICKER", "num_detectors": 4, "first_channel": 0}),
        _row("MPR121", 2, "pilot_b", {"device_name": "LICKER", "num_detectors": 4, "first_channel": 1}),
    ]
    entry = module_detector_channels(FakeDb(rows), ["MPR121"])[0]
    assert entry["channels"] == [0, 1, 2, 3, 4]
    assert entry["conflict"] is True


def test_two_pilots_differing_device_name_conflict_union_keys_and_device_names():
    rows = [
        _row("MPR121", 1, "pilot_a", {"device_name": "LICKER", "num_detectors": 2}),
        _row("MPR121", 2, "pilot_b", {"device_name": "TONGUE", "num_detectors": 2}),
    ]
    entry = module_detector_channels(FakeDb(rows), ["MPR121"])[0]
    assert entry["channels"] == [0, 1]
    assert entry["keys"] == ["LICKER0", "LICKER1", "TONGUE0", "TONGUE1"]
    assert entry["conflict"] is True
    assert entry["device_names"] == ["LICKER", "TONGUE"]


def test_single_pilot_named_tongue_device_names_never_hardcoded_to_licker():
    rows = [_row("MPR121", 1, "pilot_a", {"device_name": "TONGUE", "num_detectors": 2})]
    entry = module_detector_channels(FakeDb(rows), ["MPR121"])[0]
    assert entry["device_names"] == ["TONGUE"]
    assert entry["by_pilot"][0]["device_name"] == "TONGUE"


def test_one_pilot_configured_other_absent_is_not_a_conflict():
    rows = [_row("MPR121", 1, "pilot_a", {"device_name": "LICKER", "num_detectors": 4})]
    entry = module_detector_channels(FakeDb(rows), ["MPR121"])[0]
    assert entry["conflict"] is False
    assert len(entry["by_pilot"]) == 1


def test_module_deriving_nothing_anywhere_is_omitted():
    rows = [_row("TOUCH_INT", 1, "pilot_a", {"pin": 8, "pull": 1, "trigger": "B"})]
    assert module_detector_channels(FakeDb(rows), ["TOUCH_INT"]) == []


def test_empty_module_names_short_circuits_no_sql():
    db = FakeDb([])
    assert module_detector_channels(db, []) == []
    assert db.execute_calls == 0


def test_sort_order_module_name_pilot_name_channels_keys():
    rows = [
        _row("TONGUE_MOD", 1, "pilot_z", {"device_name": "TONGUE", "num_detectors": 1, "first_channel": 11}),
        _row("TONGUE_MOD", 1, "pilot_z", {"device_name": "TONGUE", "num_detectors": 1, "first_channel": 2}),
        _row("MPR121", 2, "pilot_b", {"device_name": "LICKER", "num_detectors": 2, "first_channel": 2}),
        _row("MPR121", 1, "pilot_a", {"device_name": "LICKER", "num_detectors": 2, "first_channel": 11}),
    ]
    result = module_detector_channels(FakeDb(rows), ["MPR121", "TONGUE_MOD"])
    assert [r["module_name"] for r in result] == ["MPR121", "TONGUE_MOD"]

    mpr = next(r for r in result if r["module_name"] == "MPR121")
    assert [p["pilot_name"] for p in mpr["by_pilot"]] == ["pilot_a", "pilot_b"]
    assert mpr["channels"] == [2, 3, 11, 12]
    # LICKER2 before LICKER11 — never lexicographic
    assert mpr["keys"] == ["LICKER2", "LICKER3", "LICKER11", "LICKER12"]
