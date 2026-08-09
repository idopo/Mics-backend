"""Tests for extlink_keys.py (Plan 18-13 Task 1, EXTLINK-19).

Pure — no DB, no TestClient. `module_extlink_signals` issues several distinct queries (unlike
`detector_keys.module_detector_channels`'s single query), so `FakeDb` here dispatches on a
distinctive substring of the query text rather than returning one canned row set for every call.

The `extlink` block fixture below is copied verbatim from 18-07-SUMMARY.md's "pinned for plan
18-10" shape: `{ClassName: {"signals": {name: {"dtype": ..., **kwargs}}}}`. It matches this
module's assumed accessor exactly — no adaptation was needed.
"""
from types import SimpleNamespace

import pytest

from extlink_keys import (
    derive_extlink_keys,
    extlink_signals_from_ast,
    has_extlink_block,
    module_extlink_signals,
)

# ---------------------------------------------------------------------------
# extlink_signals_from_ast — the 18-07-pinned ast_metadata.extlink shape
# ---------------------------------------------------------------------------

PINNED_EXTLINK_BLOCK = {
    "OpenEphysProbe": {
        "signals": {
            "firing_rate": {"dtype": "float", "default": 0.0, "stale_after_ms": 200, "stale_policy": "hold_last"},
        },
        "events": {"object_seen": {"payload": {"object": "str", "confidence": "float"}}},
        "commands": {"set_gain": {"args": [{"name": "gain", "dtype": "float"}], "returns": "bool"}},
        "decoder": "decode",
    }
}


def test_extlink_signals_from_ast_pinned_shape():
    ast_metadata = {"classes": {}, "extlink": PINNED_EXTLINK_BLOCK}
    assert extlink_signals_from_ast(ast_metadata) == [{"name": "firing_rate", "dtype": "float"}]


def test_extlink_signals_from_ast_multiple_classes_union_sorted_by_name():
    ast_metadata = {
        "extlink": {
            "ProbeA": {"signals": {"z_signal": {"dtype": "int"}}},
            "ProbeB": {"signals": {"a_signal": {"dtype": "float"}}},
        }
    }
    assert extlink_signals_from_ast(ast_metadata) == [
        {"name": "a_signal", "dtype": "float"},
        {"name": "z_signal", "dtype": "int"},
    ]


@pytest.mark.parametrize("ast_metadata", [
    None, {}, {"classes": {}}, {"extlink": None}, {"extlink": "not a dict"}, {"extlink": []},
])
def test_extlink_signals_from_ast_missing_or_malformed_block_returns_empty(ast_metadata):
    assert extlink_signals_from_ast(ast_metadata) == []


@pytest.mark.parametrize("bad_metadata", [1, "not a dict", [], True, object()])
def test_extlink_signals_from_ast_non_dict_input_never_raises(bad_metadata):
    assert extlink_signals_from_ast(bad_metadata) == []


def test_extlink_signals_from_ast_malformed_class_block_skipped_not_raised():
    ast_metadata = {"extlink": {"BadClass": "not a dict", "GoodClass": {"signals": {"ok": {"dtype": "int"}}}}}
    assert extlink_signals_from_ast(ast_metadata) == [{"name": "ok", "dtype": "int"}]


def test_extlink_signals_from_ast_malformed_signals_value_skipped_not_raised():
    ast_metadata = {"extlink": {"C": {"signals": "not a dict"}}}
    assert extlink_signals_from_ast(ast_metadata) == []


def test_extlink_signals_from_ast_signal_entry_not_dict_dtype_none():
    # A malformed signal value (e.g. a bare string instead of a kwargs dict) must not raise —
    # the signal name still surfaces, dtype degrades to None.
    ast_metadata = {"extlink": {"C": {"signals": {"weird": "not a dict"}}}}
    assert extlink_signals_from_ast(ast_metadata) == [{"name": "weird", "dtype": None}]


def test_extlink_signals_from_ast_dtype_not_string_becomes_none():
    ast_metadata = {"extlink": {"C": {"signals": {"s": {"dtype": None}}}}}
    assert extlink_signals_from_ast(ast_metadata) == [{"name": "s", "dtype": None}]


def test_has_extlink_block():
    assert has_extlink_block({"extlink": PINNED_EXTLINK_BLOCK}) is True
    assert has_extlink_block({"extlink": {}}) is False
    assert has_extlink_block({"classes": {}}) is False
    assert has_extlink_block(None) is False


# ---------------------------------------------------------------------------
# derive_extlink_keys — the `.alive` control-only guarantee
# ---------------------------------------------------------------------------

def test_derive_extlink_keys_signals_plus_alive():
    keys = derive_extlink_keys({"source_id": "dlc_cam1", "role": "sub_connect"}, ["left_paw_x", "right_paw_x"])
    assert keys == ["dlc_cam1.alive", "dlc_cam1.left_paw_x", "dlc_cam1.right_paw_x"]


def test_derive_extlink_keys_zero_signals_yields_exactly_one_alive_key():
    keys = derive_extlink_keys({"source_id": "oe_ctl", "role": "none"}, [])
    assert keys == ["oe_ctl.alive"]


def test_derive_extlink_keys_lib_declaring_alive_signal_no_duplicate():
    keys = derive_extlink_keys({"source_id": "dlc_cam1"}, ["alive", "left_paw_x"])
    assert keys == ["dlc_cam1.alive", "dlc_cam1.left_paw_x"]


@pytest.mark.parametrize("config", [None, {}, {"source_id": None}, {"source_id": ""}, {"role": "sub_connect"}])
def test_derive_extlink_keys_missing_or_empty_source_id_returns_empty(config):
    assert derive_extlink_keys(config, ["a_signal"]) == []


@pytest.mark.parametrize("bad_config", [1, "not a dict", [], True])
def test_derive_extlink_keys_non_dict_config_never_raises(bad_config):
    assert derive_extlink_keys(bad_config, ["a_signal"]) == []


def test_derive_extlink_keys_differing_source_id_produces_different_key_set():
    keys_a = derive_extlink_keys({"source_id": "dlc_cam1"}, ["left_paw_x"])
    keys_b = derive_extlink_keys({"source_id": "dlc_cam2"}, ["left_paw_x"])
    assert keys_a != keys_b
    assert set(keys_a).isdisjoint(keys_b)


# ---------------------------------------------------------------------------
# module_extlink_signals — cross-pilot union + the source_id conflict rule
# ---------------------------------------------------------------------------

def _hw_row(id_, name, hardware_lib_id):
    return SimpleNamespace(id=id_, name=name, hardware_lib_id=hardware_lib_id)


def _lib_row(id_, stable_version_id=None, active_version_id=None):
    return SimpleNamespace(id=id_, stable_version_id=stable_version_id, active_version_id=active_version_id)


def _version_row(id_, ast_metadata):
    return SimpleNamespace(id=id_, ast_metadata=ast_metadata)


def _cfg_row(module_name, pilot_id, pilot_name, config):
    return SimpleNamespace(module_name=module_name, pilot_id=pilot_id, pilot_name=pilot_name, config=config)


class FakeDb:
    """Dispatches on a distinctive substring of the query text — module_extlink_signals issues
    hardware_modules / hardware_libs (via resolve_lib_versions) / hardware_lib_versions /
    pilot_hardware_config queries, unlike module_detector_channels's single query."""

    def __init__(self, *, hw_rows=(), lib_rows=(), version_rows=(), cfg_rows=()):
        self.hw_rows = list(hw_rows)
        self.lib_rows = {r.id: r for r in lib_rows}
        self.version_rows = {r.id: r for r in version_rows}
        self.cfg_rows = list(cfg_rows)
        self.execute_calls = 0

    def execute(self, query, params=None):
        self.execute_calls += 1
        sql = str(query)
        params = params or {}
        if "FROM hardware_modules" in sql:
            return SimpleNamespace(fetchall=lambda: self.hw_rows)
        if "stable_version_id, active_version_id FROM hardware_libs" in sql:
            return SimpleNamespace(fetchone=lambda: self.lib_rows.get(params.get("id")))
        if "state FROM hardware_lib_versions" in sql:
            row = self.version_rows.get(params.get("id"))
            return SimpleNamespace(fetchone=lambda: SimpleNamespace(state="stable") if row else None)
        if "id, ast_metadata FROM hardware_lib_versions" in sql:
            ids = set(params.get("ids", []))
            return SimpleNamespace(fetchall=lambda: [r for r in self.version_rows.values() if r.id in ids])
        if "FROM pilot_hardware_config" in sql:
            return SimpleNamespace(fetchall=lambda: self.cfg_rows)
        raise AssertionError(f"unexpected query in FakeDb: {sql}")


def test_two_pilots_same_source_id_no_conflict():
    db = FakeDb(
        hw_rows=[_hw_row(1, "DLC_CAM", 10)],
        lib_rows=[_lib_row(10, stable_version_id=100)],
        version_rows=[_version_row(100, {"extlink": {"DLC": {"signals": {"left_paw_x": {"dtype": "float"}}}}})],
        cfg_rows=[
            _cfg_row("DLC_CAM", 1, "pilot_a", {"role": "sub_connect", "source_id": "dlc_cam1"}),
            _cfg_row("DLC_CAM", 2, "pilot_b", {"role": "sub_connect", "source_id": "dlc_cam1"}),
        ],
    )
    result = module_extlink_signals(db, ["DLC_CAM"])
    assert len(result) == 1
    entry = result[0]
    assert entry["module_name"] == "DLC_CAM"
    assert entry["source_ids"] == ["dlc_cam1"]
    assert entry["signals"] == [{"name": "left_paw_x", "dtype": "float"}]
    assert entry["keys"] == ["dlc_cam1.alive", "dlc_cam1.left_paw_x"]
    assert entry["conflict"] is False
    assert len(entry["by_pilot"]) == 2


def test_two_pilots_differing_source_id_is_a_conflict_keys_are_union():
    db = FakeDb(
        hw_rows=[_hw_row(1, "DLC_CAM", 10)],
        lib_rows=[_lib_row(10, stable_version_id=100)],
        version_rows=[_version_row(100, {"extlink": {"DLC": {"signals": {"left_paw_x": {"dtype": "float"}}}}})],
        cfg_rows=[
            _cfg_row("DLC_CAM", 1, "pilot_a", {"role": "sub_connect", "source_id": "dlc_cam1"}),
            _cfg_row("DLC_CAM", 2, "pilot_b", {"role": "sub_connect", "source_id": "dlc_cam2"}),
        ],
    )
    entry = module_extlink_signals(db, ["DLC_CAM"])[0]
    assert entry["source_ids"] == ["dlc_cam1", "dlc_cam2"]
    assert entry["conflict"] is True
    assert entry["keys"] == [
        "dlc_cam1.alive", "dlc_cam1.left_paw_x", "dlc_cam2.alive", "dlc_cam2.left_paw_x",
    ]
    by_pilot_keys = {p["pilot_name"]: p["keys"] for p in entry["by_pilot"]}
    assert by_pilot_keys["pilot_a"] == ["dlc_cam1.alive", "dlc_cam1.left_paw_x"]
    assert by_pilot_keys["pilot_b"] == ["dlc_cam2.alive", "dlc_cam2.left_paw_x"]


def test_control_only_module_zero_signals_yields_alive_only():
    # No ast_metadata resolvable at all (lib has no stable/active version) — the module still
    # qualifies as external purely because the config carries role+source_id (EXTLINK-18).
    db = FakeDb(
        hw_rows=[_hw_row(1, "OE_CTL", 20)],
        lib_rows=[_lib_row(20)],  # no stable/active version -> resolves to (None, "none")
        version_rows=[],
        cfg_rows=[_cfg_row("OE_CTL", 1, "pilot_a", {"role": "none", "source_id": "oe_ctl"})],
    )
    result = module_extlink_signals(db, ["OE_CTL"])
    assert len(result) == 1
    entry = result[0]
    assert entry["signals"] == []
    assert entry["keys"] == ["oe_ctl.alive"]
    assert entry["conflict"] is False


def test_config_without_role_or_source_id_and_no_ast_block_is_not_external():
    db = FakeDb(
        hw_rows=[_hw_row(1, "MPR121", 30)],
        lib_rows=[_lib_row(30)],
        version_rows=[],
        cfg_rows=[_cfg_row("MPR121", 1, "pilot_a", {"device_name": "LICKER", "num_detectors": 4})],
    )
    assert module_extlink_signals(db, ["MPR121"]) == []


def test_one_pilot_configured_other_absent_is_not_a_conflict():
    db = FakeDb(
        hw_rows=[_hw_row(1, "DLC_CAM", 10)],
        lib_rows=[_lib_row(10, stable_version_id=100)],
        version_rows=[_version_row(100, {"extlink": {"DLC": {"signals": {"x": {"dtype": "float"}}}}})],
        cfg_rows=[_cfg_row("DLC_CAM", 1, "pilot_a", {"role": "sub_connect", "source_id": "dlc_cam1"})],
    )
    entry = module_extlink_signals(db, ["DLC_CAM"])[0]
    assert entry["conflict"] is False
    assert len(entry["by_pilot"]) == 1


def test_empty_module_names_short_circuits_no_sql():
    db = FakeDb()
    assert module_extlink_signals(db, []) == []
    assert db.execute_calls == 0


def test_sort_order_module_name_and_deterministic_signal_union():
    db = FakeDb(
        hw_rows=[_hw_row(1, "DLC_CAM", 10), _hw_row(2, "OE_CTL", 20)],
        lib_rows=[_lib_row(10, stable_version_id=100), _lib_row(20, stable_version_id=200)],
        version_rows=[
            _version_row(100, {"extlink": {"DLC": {"signals": {"x": {"dtype": "float"}}}}}),
            _version_row(200, {"extlink": {"OE": {"signals": {"firing_rate": {"dtype": "float"}}}}}),
        ],
        cfg_rows=[
            _cfg_row("OE_CTL", 1, "pilot_a", {"role": "sub_connect", "source_id": "oe1"}),
            _cfg_row("DLC_CAM", 1, "pilot_a", {"role": "sub_connect", "source_id": "dlc1"}),
        ],
    )
    result = module_extlink_signals(db, ["DLC_CAM", "OE_CTL"])
    assert [r["module_name"] for r in result] == ["DLC_CAM", "OE_CTL"]
