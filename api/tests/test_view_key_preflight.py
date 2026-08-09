"""Tests for the FDA view-key/detector-ref scanner and per-pilot resolver (Plan 25-03).

Task 1: pure unit tests against detector_keys.scan_fda_view_keys / resolve_view_key_issues
directly — no DB, no TestClient, matching test_detector_keys.py's style.
Task 2: route-level tests for preflight_validate's new step 8, mocked-db.execute style.
Task 3: detector_channels/is_detector wiring on the toolkit and hardware-module read routes.
"""
from types import SimpleNamespace
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

from detector_keys import resolve_view_key_issues, scan_fda_view_keys

# ---------------------------------------------------------------------------
# Task 1 — scan_fda_view_keys: condition half is delegated, action half is new
# ---------------------------------------------------------------------------


def test_condition_tree_leaf_view_operand_found():
    fda = {"transitions": [{"condition_tree": {"left": {"view": "LICKER0"}, "op": "==", "right": 1}}]}
    results = scan_fda_view_keys(fda)
    assert len(results) == 1
    assert results[0] == {
        "location": "transitions[0].condition_tree.left",
        "kind": "operand",
        "value": "LICKER0",
        "ref": None,
        "channel": None,
    }


def test_condition_tree_nested_and_or_branch_locations_match_scan_fda_condition_operands():
    from fda_utils import scan_fda_condition_operands

    fda = {
        "transitions": [{
            "condition_tree": {
                "op": "AND",
                "children": [
                    {"op": "OR", "children": [
                        {"left": {"view": "LICKER0"}, "op": "==", "right": 1},
                        {"left": {"flag": "b"}, "op": "==", "right": 2},
                    ]},
                    {"left": {"view": "LICKER1"}, "op": "==", "right": 3},
                ],
            }
        }]
    }
    view_results = scan_fda_view_keys(fda)
    view_locations = {r["location"] for r in view_results}
    walker_locations = {r["location"] for r in scan_fda_condition_operands(fda)}
    # Every view-key location the scanner reports came verbatim from the shared walker.
    assert view_locations <= walker_locations
    assert "transitions[0].condition_tree.children[0].children[0].left" in view_locations
    assert "transitions[0].condition_tree.children[1].left" in view_locations
    assert len(view_results) == 2


def test_condition_groups_walked():
    fda = {
        "transitions": [{
            "condition_groups": [
                {"conditions": [{"left": {"view": "LICKER0"}, "op": "==", "right": 1}]},
            ]
        }]
    }
    results = scan_fda_view_keys(fda)
    assert results[0]["location"] == "transitions[0].condition_groups[0].conditions[0].left"
    assert results[0]["kind"] == "operand"


def test_legacy_flat_conditions_walked():
    fda = {"transitions": [{"conditions": [{"left": {"view": "LICKER0"}, "op": "==", "right": 1}]}]}
    results = scan_fda_view_keys(fda)
    assert results[0]["location"] == "transitions[0].conditions[0].left"


def test_wait_condition_walked():
    fda = {"states": {"wait": {"wait_condition": {"left": {"view": "LICKER0"}, "op": "==", "right": 1}}}}
    results = scan_fda_view_keys(fda)
    assert results[0]["location"] == "states.wait.wait_condition.left"


def test_tracker_operand_found_alongside_view():
    fda = {
        "transitions": [{
            "condition_tree": {"op": "AND", "children": [
                {"left": {"view": "LICKER0"}, "op": "==", "right": 1},
                {"left": {"tracker": "some_flag"}, "op": "==", "right": 2},
            ]}
        }]
    }
    results = scan_fda_view_keys(fda)
    kinds_values = {(r["kind"], r["value"]) for r in results}
    assert ("operand", "LICKER0") in kinds_values
    assert ("operand", "some_flag") in kinds_values


def test_view_detector_operand_yields_detector_kind():
    fda = {"transitions": [{"condition_tree": {"left": {"view_detector": {"ref": "MPR121", "channel": 2}}, "op": "==", "right": 1}}]}
    results = scan_fda_view_keys(fda)
    assert len(results) == 1
    assert results[0]["kind"] == "detector"
    assert results[0]["ref"] == "MPR121"
    assert results[0]["channel"] == 2
    assert results[0]["value"] is None


@pytest.mark.parametrize("vd", [
    {"channel": "2"},  # ref missing, channel not an int
    {"ref": "MPR121", "channel": "2"},  # channel a string
    {"ref": "", "channel": 2},  # empty ref
    {"ref": "MPR121", "channel": True},  # bool channel
    {"ref": "MPR121", "channel": -1},  # negative channel
    "MPR121",  # not even a dict
])
def test_malformed_view_detector_yields_nothing(vd):
    fda = {"transitions": [{"condition_tree": {"left": {"view_detector": vd}, "op": "==", "right": 1}}]}
    assert scan_fda_view_keys(fda) == []


def test_view_action_in_state_entry_actions_found_with_source_ref():
    fda = {
        "states": {
            "wait": {
                "entry_actions": [
                    {"type": "flag", "ref": "x"},
                    {"type": "view", "key_template": "{device_name}{pin_number}", "source_ref": "MPR121", "value": 1},
                ]
            }
        }
    }
    results = scan_fda_view_keys(fda)
    assert len(results) == 1
    assert results[0] == {
        "location": "states.wait.entry_actions[1].key_template",
        "kind": "key_template",
        "value": "{device_name}{pin_number}",
        "ref": "MPR121",
        "channel": None,
    }


def test_view_action_nested_in_if_then_found():
    fda = {
        "states": {
            "wait": {
                "entry_actions": [
                    {
                        "type": "if", "condition": {"left": 1, "op": "==", "right": 1},
                        "then": [{"type": "view", "key_template": "LICKER0", "source_ref": "MPR121", "value": 1}],
                        "else": [],
                    }
                ]
            }
        }
    }
    results = scan_fda_view_keys(fda)
    assert len(results) == 1
    assert results[0]["location"] == "states.wait.entry_actions[0].then[0].key_template"
    assert results[0]["value"] == "LICKER0"


def test_view_action_in_trigger_assignments_found():
    fda = {
        "trigger_assignments": [
            {
                "trigger_name": "TOUCH_INT",
                "actions": [
                    {"type": "flag", "ref": "x"},
                    {
                        "type": "if", "condition": {"left": 1, "op": "==", "right": 1},
                        "then": [{"type": "view", "key_template": "{device_name}{pin_number}", "source_ref": "MPR121", "value": 1}],
                        "else": [],
                    },
                ],
            }
        ]
    }
    results = scan_fda_view_keys(fda)
    assert len(results) == 1
    assert results[0]["location"] == "trigger_assignments[0].actions[1].then[0].key_template"
    assert results[0]["ref"] == "MPR121"


def test_non_view_operands_and_actions_not_returned():
    fda = {
        "transitions": [{"condition_tree": {"left": {"flag": "a"}, "op": "==", "right": {"param": "b"}}}],
        "states": {"s": {"entry_actions": [{"type": "hardware", "ref": "VALVE", "method": "open"}]}},
    }
    assert scan_fda_view_keys(fda) == []


@pytest.mark.parametrize("fda", [
    {"states": ["not", "a", "dict"]},
    {"transitions": [None]},
    {"states": {"s": {"entry_actions": "not a list"}}},
    {"states": {"s": {"entry_actions": ["not a dict"]}}},
    {"trigger_assignments": [{"trigger_name": "T", "actions": ["not a dict"]}]},
    {},
    None,
    "not even a dict",
])
def test_malformed_input_never_raises(fda):
    scan_fda_view_keys(fda)


# ---------------------------------------------------------------------------
# Task 1 — resolve_view_key_issues
# ---------------------------------------------------------------------------


def _detector_fda(ref="MPR121", channel=5):
    return {"transitions": [{"condition_tree": {"left": {"view_detector": {"ref": ref, "channel": channel}}, "op": "==", "right": 1}}]}


def _view_fda(key):
    return {"transitions": [{"condition_tree": {"left": {"view": key}, "op": "==", "right": 1}}]}


def _key_template_fda(template, source_ref="MPR121"):
    return {
        "states": {
            "s": {"entry_actions": [{"type": "view", "key_template": template, "source_ref": source_ref, "value": 1}]}
        }
    }


def test_literal_key_in_valid_set_no_issue():
    fda = _view_fda("lever_pressed")
    assert resolve_view_key_issues(fda, valid_keys={"lever_pressed"}, device_names={}, module_channels={}, detector_keys=[]) == []


def test_literal_key_not_in_valid_set_one_issue_with_available_keys():
    fda = _view_fda("LICKER0")
    issues = resolve_view_key_issues(
        fda, valid_keys={"LICKER1", "LICKER2", "LICKER3", "LICKER4"}, device_names={},
        module_channels={"MPR121": [1, 2, 3, 4]}, detector_keys=["LICKER1", "LICKER2", "LICKER3", "LICKER4"],
    )
    assert len(issues) == 1
    assert issues[0]["issue"] == "view_key_unresolved"
    assert issues[0]["key"] == "LICKER0"
    assert issues[0]["available_keys"] == ["LICKER1", "LICKER2", "LICKER3", "LICKER4"]
    assert "detector" not in issues[0]
    assert "available_channels" not in issues[0]


@pytest.mark.parametrize("key", ["toolkit_flag_x", "declared_var", "trial_counter", "MPR121"])
def test_four_non_detector_sources_of_a_real_view_key_no_issue(key):
    fda = _view_fda(key)
    valid_keys = {"toolkit_flag_x", "declared_var", "trial_counter", "MPR121"}
    assert resolve_view_key_issues(fda, valid_keys=valid_keys, device_names={}, module_channels={}, detector_keys=[]) == []


def test_dvk11_in_range_no_issue():
    fda = _detector_fda(channel=2)
    issues = resolve_view_key_issues(
        fda, valid_keys=set(), device_names={"MPR121": "LICKER"},
        module_channels={"MPR121": [1, 2, 3, 4]}, detector_keys=["LICKER1", "LICKER2", "LICKER3", "LICKER4"],
    )
    assert issues == []


def test_dvk11_out_of_range_one_issue_with_detector_and_resolved_key():
    fda = _detector_fda(channel=5)
    issues = resolve_view_key_issues(
        fda, valid_keys=set(), device_names={"MPR121": "LICKER"},
        module_channels={"MPR121": [1, 2, 3, 4]}, detector_keys=["LICKER1", "LICKER2", "LICKER3", "LICKER4"],
    )
    assert len(issues) == 1
    issue = issues[0]
    assert issue["issue"] == "view_key_unresolved"
    assert issue["detector"] == {"ref": "MPR121", "channel": 5}
    assert issue["available_channels"] == [1, 2, 3, 4]
    assert issue["key"] == "LICKER5"
    assert issue["available_keys"] == ["LICKER1", "LICKER2", "LICKER3", "LICKER4"]


def test_dvk09_dvk11_combined_regression_channel_zero_out_of_range():
    """The exact wiring that lost 9 events on the rig (runs 480/481), now expressed the
    DVK-11 way: MPR121 wired at channels 1-4, a definition referencing channel 0."""
    fda = _detector_fda(ref="MPR121", channel=0)
    issues = resolve_view_key_issues(
        fda, valid_keys=set(), device_names={"MPR121": "LICKER"},
        module_channels={"MPR121": [1, 2, 3, 4]}, detector_keys=["LICKER1", "LICKER2", "LICKER3", "LICKER4"],
    )
    assert len(issues) == 1
    assert issues[0]["detector"]["channel"] == 0


def test_detector_ref_in_skip_modules_no_issue_even_out_of_range():
    fda = _detector_fda(channel=5)
    issues = resolve_view_key_issues(
        fda, valid_keys=set(), device_names={"MPR121": "LICKER"},
        module_channels={"MPR121": [1, 2, 3, 4]}, detector_keys=["LICKER1"], skip_modules={"MPR121"},
    )
    assert issues == []


def test_detector_ref_absent_from_module_channels_no_issue():
    fda = _detector_fda(ref="MPR121", channel=5)
    issues = resolve_view_key_issues(fda, valid_keys=set(), device_names={}, module_channels={}, detector_keys=[])
    assert issues == []


def test_device_name_pin_number_template_resolvable_source_ref_no_issue():
    fda = _key_template_fda("{device_name}{pin_number}", source_ref="MPR121")
    issues = resolve_view_key_issues(
        fda, valid_keys=set(), device_names={"MPR121": "LICKER"}, module_channels={}, detector_keys=[],
    )
    assert issues == []


def test_device_name_pin_number_template_unresolvable_source_ref_one_issue():
    fda = _key_template_fda("{device_name}{pin_number}", source_ref="GHOST")
    issues = resolve_view_key_issues(
        fda, valid_keys=set(), device_names={"MPR121": "LICKER"}, module_channels={}, detector_keys=[],
    )
    assert len(issues) == 1
    assert issues[0]["module_name"] == "GHOST"
    assert "detector" not in issues[0]


def test_device_name_2_resolves_and_checked_against_valid_set_no_issue():
    fda = _key_template_fda("{device_name}2", source_ref="MPR121")
    issues = resolve_view_key_issues(
        fda, valid_keys={"LICKER1", "LICKER2", "LICKER3", "LICKER4"},
        device_names={"MPR121": "LICKER"}, module_channels={}, detector_keys=[],
    )
    assert issues == []


def test_device_name_2_resolves_and_checked_against_valid_set_one_issue_naming_licker2():
    fda = _key_template_fda("{device_name}2", source_ref="MPR121")
    issues = resolve_view_key_issues(
        fda, valid_keys={"LICKER1", "LICKER3", "LICKER4"},
        device_names={"MPR121": "LICKER"}, module_channels={}, detector_keys=[],
    )
    assert len(issues) == 1
    assert issues[0]["key"] == "LICKER2"


def test_key_template_with_only_runtime_token_alone_no_issue():
    fda = _key_template_fda("{some_variable}", source_ref=None)
    issues = resolve_view_key_issues(fda, valid_keys=set(), device_names={}, module_channels={}, detector_keys=[])
    assert issues == []


def test_dvk09_literal_regression_no_detector_field():
    fda = _view_fda("LICKER0")
    issues = resolve_view_key_issues(
        fda, valid_keys={"LICKER1", "LICKER2", "LICKER3", "LICKER4"}, device_names={},
        module_channels={}, detector_keys=["LICKER1", "LICKER2", "LICKER3", "LICKER4"],
    )
    assert len(issues) == 1
    assert "detector" not in issues[0]
    assert issues[0]["key"] == "LICKER0"


def test_key_template_no_tokens_treated_as_operand():
    fda = _key_template_fda("LICKER0", source_ref="MPR121")
    issues = resolve_view_key_issues(
        fda, valid_keys={"LICKER1", "LICKER2", "LICKER3", "LICKER4"}, device_names={},
        module_channels={}, detector_keys=["LICKER1", "LICKER2", "LICKER3", "LICKER4"],
    )
    assert len(issues) == 1
    assert issues[0]["key"] == "LICKER0"
    assert issues[0]["module_name"] == "MPR121"


# ---------------------------------------------------------------------------
# Task 2 — route-level: preflight_validate step 8 (DVK-06/11), mocked-db.execute style
# (fixture pattern follows test_task_definitions_validation.py's DVK-07 section)
# ---------------------------------------------------------------------------


class _Result:
    """Stands in for what `db.execute(...)` returns — `.fetchone()` / `.fetchall()` only,
    matching the real SQLAlchemy CursorResult surface preflight_validate actually calls."""

    def __init__(self, one=None, many=None):
        self._one = one
        self._many = many or []

    def fetchone(self):
        return self._one

    def fetchall(self):
        return self._many


class FakeDb:
    """SQL-text-dispatching stub for preflight_validate's raw `db.execute()` calls. Matches on
    distinguishing substrings/params rather than call order, so a test scoped to one branch
    does not break when a different branch's query changes.
    """

    def __init__(
        self, *, run_row=None, spr_row=None, step_row=None, td_row=None,
        toolkit_row=None, existing_configs=None, modules=None, configs=None, td_full=None,
        lib_row=None, lib_meta_row=None, hw_versions_row=None,
    ):
        self.run_row = run_row
        self.spr_row = spr_row
        self.step_row = step_row
        self.td_row = td_row
        self.toolkit_row = toolkit_row
        self.existing_configs = existing_configs or []
        self.modules = modules or {}  # hardware_module id -> SimpleNamespace(id, name, class_name)
        self.configs = configs or {}  # module name -> SimpleNamespace(config=dict)
        self.td_full = td_full
        self.lib_row = lib_row  # SimpleNamespace(stable_version_id, active_version_id)
        self.lib_meta_row = lib_meta_row  # SimpleNamespace(name, filename)
        self.hw_versions_row = hw_versions_row

    def commit(self):
        """No-op — Plan 23-07 Task 1's self-heal path calls db.commit() after provisioning."""

    def execute(self, query, params=None):
        sql = " ".join(str(query).split())
        params = params or {}

        if "FROM session_runs sr" in sql:
            return _Result(one=self.run_row)
        if "FROM subject_protocol_runs" in sql:
            return _Result(one=self.spr_row)
        if "FROM protocol_step_templates" in sql:
            return _Result(one=self.step_row)
        if "toolkit_id FROM task_definitions" in sql:
            return _Result(one=self.td_row)
        if "hw_lib_versions FROM task_definitions" in sql:
            return _Result(one=self.hw_versions_row)
        if "FROM task_toolkits" in sql:
            return _Result(one=self.toolkit_row)
        if "fda_json FROM task_definitions" in sql:
            return _Result(one=self.td_full)
        if sql.startswith("SELECT name, config FROM pilot_hardware_config"):
            return _Result(many=self.existing_configs)
        if sql.startswith("SELECT default_version_id FROM toolkit_hardware_libs"):
            return _Result(one=None)  # no toolkit-level pin default exercised by these tests
        if sql.startswith("SELECT stable_version_id, active_version_id FROM hardware_libs"):
            return _Result(one=self.lib_row)
        if sql.startswith("SELECT state FROM hardware_lib_versions"):
            return _Result(one=None)  # active rung not exercised; tests use pin/stable/none only
        if sql.startswith("SELECT name, filename FROM hardware_libs"):
            return _Result(one=self.lib_meta_row)
        if sql.startswith("SELECT id, name, class_name, hardware_lib_id FROM hardware_modules"):
            return _Result(one=self.modules.get(params.get("id")))
        if sql.startswith("SELECT name, class_name FROM hardware_modules"):
            return _Result(one=self.modules.get(params.get("id")))
        if "FROM pilot_hardware_config" in sql and "name = :name" in sql:
            return _Result(one=self.configs.get(params.get("name")))
        return _Result()


def _module(module_id, name, class_name, hardware_lib_id=None):
    return SimpleNamespace(id=module_id, name=name, class_name=class_name, hardware_lib_id=hardware_lib_id)


def _config(config_dict):
    return SimpleNamespace(config=config_dict)


MPR121_CONFIG = {"device_name": "LICKER", "num_detectors": 4, "first_channel": 1, "class_name": "Touch_Detector"}


def _backend_toolkit_scenario(fda_json, mpr121_config=MPR121_CONFIG, flags=None, module_ids=None, lib_row=None):
    module_ids = module_ids if module_ids is not None else [7]
    return FakeDb(
        run_row=None,
        spr_row=SimpleNamespace(protocol_id=1),
        step_row=SimpleNamespace(task_definition_id=42),
        td_row=SimpleNamespace(toolkit_id=5),
        toolkit_row=SimpleNamespace(is_backend_authored=True, hardware_module_ids=module_ids, flags=flags or {}),
        # preflight_validate indexes these rows positionally (row[0], row[1]) — tuples, not dicts.
        existing_configs=([("MPR121", mpr121_config)] if mpr121_config is not None else []),
        modules={7: _module(7, "MPR121", "Touch_Detector", hardware_lib_id=10)},
        configs=({"MPR121": _config(mpr121_config)} if mpr121_config is not None else {}),
        td_full=SimpleNamespace(fda_json=fda_json),
        # Resolves cleanly (reason="stable") by default so pre-existing tests don't pick up a
        # spurious lib_version_unresolved issue; override to exercise that path explicitly.
        lib_row=lib_row if lib_row is not None else SimpleNamespace(stable_version_id=500, active_version_id=None),
    )


@pytest.fixture(autouse=True)
def _clear_dependency_overrides():
    yield
    from main import app
    app.dependency_overrides.clear()


def _client_for(fake_db):
    from auth import verify_token
    from main import app
    from routers.toolkit_dispatch import get_sa_session
    app.dependency_overrides[verify_token] = lambda: {"sub": "test"}
    app.dependency_overrides[get_sa_session] = lambda: fake_db
    return TestClient(app)


def auth_headers():
    return {"Authorization": "Bearer test-token"}


def _preflight(fake_db, session_id=1, pilot_id=1):
    client = _client_for(fake_db)
    return client.post(f"/api/sessions/{session_id}/preflight-validate/{pilot_id}", headers=auth_headers())


def test_out_of_range_channel_returns_one_view_key_unresolved_issue_with_detector_field():
    fda = _detector_fda(ref="MPR121", channel=5)
    resp = _preflight(_backend_toolkit_scenario(fda))
    assert resp.status_code == 200
    body = resp.json()
    assert body["ok"] is False
    assert len(body["issues"]) == 1
    assert body["issues"][0]["issue"] == "view_key_unresolved"
    assert body["issues"][0]["detector"] == {"ref": "MPR121", "channel": 5}


def test_in_range_channel_no_new_issue():
    fda = _detector_fda(ref="MPR121", channel=2)
    resp = _preflight(_backend_toolkit_scenario(fda))
    assert resp.status_code == 200
    body = resp.json()
    assert body["ok"] is True
    assert body["issues"] == []


def test_literal_key_pilot_cannot_produce_one_issue_no_detector_field():
    fda = _view_fda("LICKER0")
    resp = _preflight(_backend_toolkit_scenario(fda))
    body = resp.json()
    assert body["ok"] is False
    assert len(body["issues"]) == 1
    assert body["issues"][0]["issue"] == "view_key_unresolved"
    assert "detector" not in body["issues"][0]


def test_canonical_device_name_pin_number_template_resolvable_no_new_issue():
    fda = _key_template_fda("{device_name}{pin_number}", source_ref="MPR121")
    resp = _preflight(_backend_toolkit_scenario(fda))
    body = resp.json()
    assert body["ok"] is True
    assert body["issues"] == []


def test_canonical_device_name_pin_number_template_unresolvable_device_name_one_issue():
    """The MPR121 config row exists (so step 6 stays clean) but carries no device_name — the
    {device_name} token this template needs has nothing to resolve against on this pilot."""
    config_no_device_name = {"class_name": "Touch_Detector", "address": True}
    fda = _key_template_fda("{device_name}{pin_number}", source_ref="MPR121")
    resp = _preflight(_backend_toolkit_scenario(fda, mpr121_config=config_no_device_name))
    body = resp.json()
    assert body["ok"] is False
    assert len(body["issues"]) == 1
    assert body["issues"][0]["issue"] == "view_key_unresolved"
    assert body["issues"][0]["module_name"] == "MPR121"


def test_non_backend_authored_toolkit_unchanged_early_return():
    fake_db = FakeDb(
        run_row=None,
        spr_row=SimpleNamespace(protocol_id=1),
        step_row=SimpleNamespace(task_definition_id=42),
        td_row=SimpleNamespace(toolkit_id=5),
        toolkit_row=SimpleNamespace(is_backend_authored=False, hardware_module_ids=[], flags={}),
    )
    resp = _preflight(fake_db)
    body = resp.json()
    assert body == {"ok": True, "issues": [], "skip_reason": "not_backend_authored"}


def test_no_task_definition_unchanged_early_return():
    fake_db = FakeDb(
        run_row=None,
        spr_row=SimpleNamespace(protocol_id=1),
        step_row=SimpleNamespace(task_definition_id=None),
    )
    resp = _preflight(fake_db)
    body = resp.json()
    assert body == {"ok": True, "issues": [], "skip_reason": "not_backend_authored"}


def test_fda_json_none_step6_issues_only_no_exception_logged():
    fake_db = _backend_toolkit_scenario(fda_json=None, mpr121_config=None)
    with patch("routers.toolkit_dispatch.logger.warning") as mock_warn:
        resp = _preflight(fake_db)
    body = resp.json()
    assert body["ok"] is False
    assert len(body["issues"]) == 1
    assert body["issues"][0]["issue"] == "missing"
    mock_warn.assert_not_called()


def test_module_already_flagged_missing_no_duplicate_view_key_unresolved_issue():
    """R3: a `view_detector` naming a module the pilot has no config row for is reported once
    (step 6's `missing`), not twice."""
    fda = _detector_fda(ref="MPR121", channel=5)
    resp = _preflight(_backend_toolkit_scenario(fda, mpr121_config=None))
    body = resp.json()
    assert body["ok"] is False
    assert len(body["issues"]) == 1
    assert body["issues"][0]["issue"] == "missing"


def test_malformed_toolkit_flags_row_returns_200_with_step6_issues_only_and_logs_warning():
    """A malformed config row (toolkit.flags not a dict) must not 500 — step 8 degrades to
    'no new issue' and logs, per the plan's try/except mandate."""
    fda = _view_fda("LICKER0")
    with patch("routers.toolkit_dispatch.logger.warning") as mock_warn:
        resp = _preflight(_backend_toolkit_scenario(fda, flags="not a dict"))
    assert resp.status_code == 200
    body = resp.json()
    assert body["ok"] is True
    assert body["issues"] == []
    mock_warn.assert_called_once()


# ---------------------------------------------------------------------------
# CMP-15/23-07 Task 2 — step 9 (variable_never_written), lib_version_unresolved,
# PREFLIGHT_ISSUE_KINDS + compute_lib_import_failed_issue
# ---------------------------------------------------------------------------


def test_variable_read_never_written_yields_one_issue_with_reader_location():
    fda = {
        "variables": {"target": {"initial_value": None}},
        "transitions": [{"condition_tree": {"left": {"view": "target"}, "op": "==", "right": 1}}],
    }
    resp = _preflight(_backend_toolkit_scenario(fda, mpr121_config=None))
    body = resp.json()
    var_issues = [i for i in body["issues"] if i["issue"] == "variable_never_written"]
    assert len(var_issues) == 1
    assert var_issues[0]["variable"] == "target"
    assert var_issues[0]["location"] == "transitions[0].condition_tree.left"


def test_variable_written_by_compute_action_no_variable_never_written_issue():
    fda = {
        "variables": {"target": {"initial_value": None}},
        "transitions": [{"condition_tree": {"left": {"view": "target"}, "op": "==", "right": 1}}],
        "states": {
            "s": {"entry_actions": [
                {"type": "compute", "ref": "ComputeMod", "method": "add", "output": "target"},
            ]}
        },
    }
    resp = _preflight(_backend_toolkit_scenario(fda, mpr121_config=None))
    body = resp.json()
    assert [i for i in body["issues"] if i["issue"] == "variable_never_written"] == []


def test_variable_scan_exception_does_not_raise_returns_other_issues():
    fda = {"variables": {"target": {}}, "transitions": []}
    with patch("routers.toolkit_dispatch.variable_never_written_issues", side_effect=Exception("boom")), \
         patch("routers.toolkit_dispatch.logger.warning") as mock_warn:
        resp = _preflight(_backend_toolkit_scenario(fda, mpr121_config=None))
    assert resp.status_code == 200
    body = resp.json()
    assert body["ok"] is False
    assert body["issues"][0]["issue"] == "missing"
    mock_warn.assert_called_once()


def test_lib_version_unresolved_emitted_when_resolution_is_none():
    fake_db = _backend_toolkit_scenario(
        fda_json=None, mpr121_config=MPR121_CONFIG,
        lib_row=SimpleNamespace(stable_version_id=None, active_version_id=None),
    )
    fake_db.lib_meta_row = SimpleNamespace(name="mpr121_lib", filename="mpr121.py")
    resp = _preflight(fake_db)
    body = resp.json()
    lib_issues = [i for i in body["issues"] if i["issue"] == "lib_version_unresolved"]
    assert len(lib_issues) == 1
    assert lib_issues[0]["module_name"] == "MPR121"
    assert "mpr121.py" in lib_issues[0]["detail"]


def test_lib_version_resolved_no_lib_version_unresolved_issue():
    resp = _preflight(_backend_toolkit_scenario(fda_json=None, mpr121_config=MPR121_CONFIG))
    body = resp.json()
    assert [i for i in body["issues"] if i["issue"] == "lib_version_unresolved"] == []


def test_preflight_issue_kinds_frozenset_is_complete():
    """Pinned so a new kind cannot be added without also being surfaced in the UI — the
    `PreflightIssue` union and NON_CONFIG_ISSUES in HardwareCheckModal.tsx must match."""
    from routers.toolkit_dispatch import PREFLIGHT_ISSUE_KINDS
    assert len(PREFLIGHT_ISSUE_KINDS) == 11
    assert "variable_never_written" in PREFLIGHT_ISSUE_KINDS
    assert "lib_version_unresolved" in PREFLIGHT_ISSUE_KINDS
    assert "compute_lib_import_failed" in PREFLIGHT_ISSUE_KINDS
    assert "state_wait_unsatisfiable" in PREFLIGHT_ISSUE_KINDS
    assert "device_held" in PREFLIGHT_ISSUE_KINDS
    assert "extlink_config_invalid" in PREFLIGHT_ISSUE_KINDS


def test_compute_lib_import_failed_issue_constructor_shape():
    from routers.toolkit_dispatch import compute_lib_import_failed_issue
    issue = compute_lib_import_failed_issue("ComputeMod", "compute_ops.py", "ImportError: no module named foo")
    assert issue["issue"] == "compute_lib_import_failed"
    assert issue["module_name"] == "ComputeMod"
    assert issue["lib_filename"] == "compute_ops.py"
    assert "foo" in issue["detail"]


# ---------------------------------------------------------------------------
# CMP-15/23-07 Task 1 — compute-aware step 6: no false positive, self-healing config
# ---------------------------------------------------------------------------


def _compute_toolkit_scenario(fda_json, config=None, class_name="ComputeOps"):
    """Same shape as _backend_toolkit_scenario, but for a lone compute module."""
    return FakeDb(
        run_row=None,
        spr_row=SimpleNamespace(protocol_id=1),
        step_row=SimpleNamespace(task_definition_id=42),
        td_row=SimpleNamespace(toolkit_id=5),
        toolkit_row=SimpleNamespace(is_backend_authored=True, hardware_module_ids=[9], flags={}),
        existing_configs=([("ComputeMod", config)] if config is not None else []),
        modules={9: _module(9, "ComputeMod", class_name, hardware_lib_id=20)},
        configs=({"ComputeMod": _config(config)} if config is not None else {}),
        td_full=SimpleNamespace(fda_json=fda_json),
        lib_row=SimpleNamespace(stable_version_id=800, active_version_id=None),
    )


def test_compute_module_empty_config_no_incomplete_config_issue():
    fake_db = _compute_toolkit_scenario(fda_json=None, config={"class_name": "ComputeOps"})
    with patch("routers.toolkit_dispatch.compute_module_names", return_value={"ComputeMod": "ComputeOps"}):
        resp = _preflight(fake_db)
    body = resp.json()
    assert body["ok"] is True
    assert body["issues"] == []


def test_hardware_module_empty_config_still_incomplete_config():
    fake_db = _backend_toolkit_scenario(fda_json=None, mpr121_config={"class_name": "Touch_Detector"})
    resp = _preflight(fake_db)  # compute_module_names not patched -> real call -> {} (not compute)
    body = resp.json()
    assert body["ok"] is False
    assert len(body["issues"]) == 1
    assert body["issues"][0]["issue"] == "incomplete_config"


def test_compute_module_wrong_class_name_still_class_mismatch():
    fake_db = _compute_toolkit_scenario(fda_json=None, config={"class_name": "WrongClass"})
    with patch("routers.toolkit_dispatch.compute_module_names", return_value={"ComputeMod": "ComputeOps"}):
        resp = _preflight(fake_db)
    body = resp.json()
    assert body["ok"] is False
    assert len(body["issues"]) == 1
    assert body["issues"][0]["issue"] == "class_mismatch"
    assert body["issues"][0]["stored_class"] == "WrongClass"


def test_compute_module_missing_config_row_self_heals_before_loop():
    fake_db = _compute_toolkit_scenario(fda_json=None, config=None)

    def fake_provision(db, module_ids, pilot_ids=None):
        db.configs["ComputeMod"] = _config({"class_name": "ComputeOps"})
        return [(pilot_ids[0], "ComputeMod")]

    with patch("routers.toolkit_dispatch.compute_module_names", return_value={"ComputeMod": "ComputeOps"}), \
         patch("routers.toolkit_dispatch.provision_compute_configs", side_effect=fake_provision):
        resp = _preflight(fake_db)
    body = resp.json()
    assert body["ok"] is True
    assert body["issues"] == []


def test_hardware_module_missing_config_row_still_missing():
    fake_db = _backend_toolkit_scenario(fda_json=None, mpr121_config=None)
    resp = _preflight(fake_db)
    body = resp.json()
    assert body["ok"] is False
    assert body["issues"][0]["issue"] == "missing"


def test_compute_provisioning_raises_does_not_fail_request():
    fake_db = _compute_toolkit_scenario(fda_json=None, config=None)
    with patch("routers.toolkit_dispatch.compute_module_names", return_value={"ComputeMod": "ComputeOps"}), \
         patch("routers.toolkit_dispatch.provision_compute_configs", side_effect=RuntimeError("boom")), \
         patch("routers.toolkit_dispatch.logger.warning") as mock_warn:
        resp = _preflight(fake_db)
    assert resp.status_code == 200
    body = resp.json()
    assert body["issues"][0]["issue"] == "missing"  # provisioning failed, row still absent
    mock_warn.assert_called_once()


# ---------------------------------------------------------------------------
# Task 3 — detector_channels on the toolkit read; is_detector on the module read;
# toolkit_hw_capabilities carrying module_names on BOTH returns
# ---------------------------------------------------------------------------


def test_build_toolkit_row_detector_channels_is_a_list_even_with_default_caps():
    from routers.toolkits import _build_toolkit_row

    t = SimpleNamespace(
        id=1, name="X", hw_hash="h", states=[], flags={}, params_schema={}, semantic_hardware={},
        callable_methods=[], required_packages=[], file_hash="f", created_at=None, updated_at=None,
        is_canonical=False, is_backend_authored=False, hardware_module_ids=[], locked_state_source=None,
    )
    row = _build_toolkit_row(t, {}, 0)  # no caps, no detector_channels passed
    assert row["detector_channels"] == []


class _FakeRows:
    def __init__(self, rows):
        self._rows = rows

    def fetchall(self):
        return self._rows


class _FakeOne:
    def __init__(self, row):
        self._row = row

    def fetchone(self):
        return self._row


class _FakeIntrospectDb:
    """SQL-text-dispatching stub for toolkit_hw_capabilities' two-step query (Plan 23-05):
    module rows, then the resolver's own pin/toolkit_default/stable/active queries, then the
    final batch source-code fetch."""

    def __init__(self, module_rows, lib_row=None, active_state=None, source_by_id=None):
        self.module_rows = module_rows
        self.lib_row = lib_row
        self.active_state = active_state
        self.source_by_id = source_by_id or {}

    def execute(self, query, params=None):
        sql = " ".join(str(query).split())
        params = params or {}
        if sql.startswith("SELECT hm.id, hm.name, hm.class_name, hm.hardware_lib_id"):
            return _FakeRows(self.module_rows)
        if sql.startswith("SELECT default_version_id FROM toolkit_hardware_libs"):
            return _FakeOne(None)
        if sql.startswith("SELECT stable_version_id, active_version_id FROM hardware_libs"):
            return _FakeOne(self.lib_row)
        if sql.startswith("SELECT state FROM hardware_lib_versions"):
            return _FakeOne(SimpleNamespace(state=self.active_state) if self.active_state else None)
        if sql.startswith("SELECT id, source_code FROM hardware_lib_versions"):
            ids = params.get("ids", [])
            return _FakeRows([
                SimpleNamespace(id=i, source_code=self.source_by_id[i])
                for i in ids if i in self.source_by_id
            ])
        return _FakeRows([])


def test_toolkit_hw_capabilities_module_names_survives_row_with_no_source_code():
    from hw_introspect import toolkit_hw_capabilities

    rows = [SimpleNamespace(id=1, name="TOUCH_INT", class_name="Digital_In", hardware_lib_id=99)]
    # No lib_row -> resolver returns (None, "none") -> module is unresolvable.
    caps = toolkit_hw_capabilities(_FakeIntrospectDb(rows), [1])
    assert caps["module_names"] == ["TOUCH_INT"]
    assert caps["module_methods"] == {}  # unresolvable version -> skipped by the per-row guard


def test_toolkit_hw_capabilities_module_names_present_on_both_returns():
    from hw_introspect import toolkit_hw_capabilities

    empty_path = toolkit_hw_capabilities(None, [])
    assert "module_names" in empty_path
    assert empty_path["module_names"] == []

    rows = [SimpleNamespace(id=7, name="MPR121", class_name="Touch_Detector", hardware_lib_id=10)]
    lib_row = SimpleNamespace(stable_version_id=None, active_version_id=100)
    db = _FakeIntrospectDb(
        rows, lib_row=lib_row, active_state="beta",
        source_by_id={100: "class Touch_Detector:\n    pass\n"},
    )
    non_empty_path = toolkit_hw_capabilities(db, [7])
    assert "module_names" in non_empty_path
    assert non_empty_path["module_names"] == ["MPR121"]


# ---------------------------------------------------------------------------
# CMP-15/23-07 Task 3 — GET /api/task-definitions/{id}/variable-usage
# ---------------------------------------------------------------------------


class _FakeTaskDefDb:
    """SQL-text-dispatching stub for task_def_inspect's one raw query."""

    def __init__(self, td_row=None):
        self.td_row = td_row

    def execute(self, query, params=None):
        sql = " ".join(str(query).split())
        if sql.startswith("SELECT fda_json FROM task_definitions"):
            return _Result(one=self.td_row)
        return _Result()

    def close(self):
        pass


def _variable_usage_client(fake_db):
    from auth import verify_token
    from main import app
    from routers.task_def_inspect import get_sa_session
    app.dependency_overrides[verify_token] = lambda: {"sub": "test"}
    app.dependency_overrides[get_sa_session] = lambda: fake_db
    return TestClient(app)


def test_variable_usage_returns_writers_readers_never_written_initial_value():
    fda = {
        "variables": {"target": {"initial_value": None}, "lever_count": {"initial_value": 0}},
        "transitions": [{"condition_tree": {"left": {"view": "target"}, "op": "==", "right": 1}}],
    }
    client = _variable_usage_client(_FakeTaskDefDb(td_row=SimpleNamespace(fda_json=fda)))
    resp = client.get("/api/task-definitions/187/variable-usage", headers=auth_headers())
    assert resp.status_code == 200
    body = resp.json()
    assert set(body["variables"].keys()) == {"target", "lever_count"}
    assert body["variables"]["target"]["readers"] == ["transitions[0].condition_tree.left"]
    assert body["variables"]["target"]["writers"] == []
    assert body["variables"]["target"]["never_written"] is True
    assert body["variables"]["target"]["initial_value"] is None
    assert body["variables"]["lever_count"]["never_written"] is False  # initial_value writes it
    assert body["variables"]["lever_count"]["initial_value"] == 0


def test_variable_usage_404_for_unknown_task_definition():
    client = _variable_usage_client(_FakeTaskDefDb(td_row=None))
    resp = client.get("/api/task-definitions/9999/variable-usage", headers=auth_headers())
    assert resp.status_code == 404


def test_variable_usage_no_fda_json_returns_empty_variables():
    client = _variable_usage_client(_FakeTaskDefDb(td_row=SimpleNamespace(fda_json=None)))
    resp = client.get("/api/task-definitions/187/variable-usage", headers=auth_headers())
    assert resp.status_code == 200
    assert resp.json() == {"variables": {}}


def test_variable_usage_no_variables_key_returns_empty_variables():
    client = _variable_usage_client(_FakeTaskDefDb(td_row=SimpleNamespace(fda_json={"states": {}})))
    resp = client.get("/api/task-definitions/187/variable-usage", headers=auth_headers())
    assert resp.status_code == 200
    assert resp.json() == {"variables": {}}


def test_variable_usage_requires_auth():
    from main import app
    client = TestClient(app)
    resp = client.get("/api/task-definitions/187/variable-usage")
    assert resp.status_code in (401, 403)


# ---------------------------------------------------------------------------
# Plan 18-03 — device-lease + extlink-config preflight contract (EXTLINK-17,
# EXTLINK-10, EXTLINK-18). `api/device_lease.py` (plan 18-08) and `preflight_validate` step 11
# (plan 18-08 task 2) now both exist, so every test below is live -- the `pytest.importorskip
# ("device_lease")` guards are kept as a harmless first statement (module always resolves now)
# rather than pulled, since they cost nothing and would only matter again if this file were ever
# run against a checkout that predates 18-08. The two route-level tests' `xfail` markers (they
# hit the real preflight-validate HTTP route rather than calling a device_lease function
# directly) were removed here, in plan 18-08 task 2, once step 11 made them pass. Plan 18-09 adds
# its OWN xfail-then-remove tests for the force-release/reconcile HTTP endpoints it builds
# (`api/routers/device_leases.py`) -- those endpoints do not exist yet at this point in the phase.
#
# Residual-risk boundary (so no later plan over-promises): Phase 18's safety net releases the
# lease row and marks the run errored. It does NOT reach out to the foreign device to stop it --
# the backend has no channel to an arbitrary device's control API by design ("the Pi owns both
# channels" is locked). Device-side cleanup after a pilot crash is Phase 26's decision.
# ---------------------------------------------------------------------------


class _LeaseResult:
    """Like `_Result`, but also exposes `.rowcount` for a DELETE-style call, since we don't
    know yet whether 18-08's `force_release` reads `.fetchone()` or `.rowcount`."""

    def __init__(self, one=None, many=None, rowcount=0):
        self._one = one
        self._many = many or []
        self.rowcount = rowcount

    def fetchone(self):
        return self._one

    def fetchall(self):
        return self._many


class _LeaseFakeDb(FakeDb):
    """Extends `FakeDb` (per the plan's instruction: subclass, don't edit the existing class)
    with an in-memory `device_leases` table keyed by normalized host. Dispatches generically on
    the substring "device_leases" so 18-08's exact column list / predicate order is free to
    differ from this fixture -- only the CRUD shape (insert-or-replace one row per host,
    select-by-host, select-all, delete-by-host) is pinned.
    """

    def __init__(self, *, leases=None, **kwargs):
        super().__init__(**kwargs)
        # normalized host -> dict(pilot_id, pilot_name, session_id, run_id, subject_key, acquired_at)
        self._leases = dict(leases or {})

    def execute(self, query, params=None):
        sql = " ".join(str(query).split())
        params = params or {}
        if "device_leases" in sql:
            upper = sql.upper()
            if upper.startswith("SELECT") and "host" in params:
                row = self._leases.get(params["host"])
                return _LeaseResult(one=SimpleNamespace(host=params["host"], **row) if row else None)
            if upper.startswith("SELECT"):
                rows = [SimpleNamespace(host=h, **v) for h, v in self._leases.items()]
                return _LeaseResult(many=rows)
            if upper.startswith("INSERT"):
                host = params.get("host")
                self._leases[host] = {
                    "pilot_id": params.get("pilot_id"),
                    "pilot_name": params.get("pilot_name"),
                    "session_id": params.get("session_id"),
                    "run_id": params.get("run_id"),
                    "subject_key": params.get("subject_key"),
                    "acquired_at": params.get("acquired_at", "2026-08-09T00:00:00Z"),
                }
                return _LeaseResult(rowcount=1)
            if upper.startswith("DELETE"):
                host = params.get("host")
                existed = host in self._leases
                self._leases.pop(host, None)
                return _LeaseResult(one=(1 if existed else None), rowcount=1 if existed else 0)
            return _LeaseResult()
        return super().execute(query, params)

    def commit(self):
        pass


_VALID_EXTLINK_CONFIG = {
    "class_name": "OE_Control", "role": "sub_connect", "host": "132.77.9.9",
    "connect_port": 5556, "source_id": "oe", "stale_ms": 3000, "required": True,
    "wait_timeout_s": 60, "egress_fail_threshold": 3,
}

_ROLE_NONE_CONFIG = {
    "class_name": "OE_Control", "role": "none", "host": "132.77.9.9",
    "source_id": "oe", "stale_ms": 3000, "required": True,
    "wait_timeout_s": 60, "egress_fail_threshold": 3,
}


def _oe_control_scenario(fda_json=None, config=None, module_class_name="OE_Control"):
    cfg = config if config is not None else _ROLE_NONE_CONFIG
    return FakeDb(
        run_row=None,
        spr_row=SimpleNamespace(protocol_id=1),
        step_row=SimpleNamespace(task_definition_id=42),
        td_row=SimpleNamespace(toolkit_id=5),
        toolkit_row=SimpleNamespace(is_backend_authored=True, hardware_module_ids=[8], flags={}),
        existing_configs=[("OE", cfg)],
        modules={8: _module(8, "OE", module_class_name, hardware_lib_id=11)},
        configs={"OE": _config(cfg)},
        td_full=SimpleNamespace(fda_json=fda_json or {}),
        lib_row=SimpleNamespace(stable_version_id=600, active_version_id=None),
    )


# --- Lease arbitration (EXTLINK-17) -----------------------------------------


def test_lease_blocks_second_run_same_host():
    pytest.importorskip("device_lease")
    from device_lease import normalize_host

    host = "132.77.9.9"
    config_a = {**_VALID_EXTLINK_CONFIG, "host": host}
    fake_db = _LeaseFakeDb(
        leases={normalize_host(host): {
            "pilot_id": 99, "pilot_name": "pilot-A", "session_id": 1, "run_id": 501,
            "subject_key": "bp_s1_r501", "acquired_at": "2026-08-09T10:00:00Z",
        }},
        run_row=None,
        spr_row=SimpleNamespace(protocol_id=1),
        step_row=SimpleNamespace(task_definition_id=42),
        td_row=SimpleNamespace(toolkit_id=5),
        toolkit_row=SimpleNamespace(is_backend_authored=True, hardware_module_ids=[8], flags={}),
        existing_configs=[("OE", config_a)],
        modules={8: _module(8, "OE", "OE_Control", hardware_lib_id=11)},
        configs={"OE": _config(config_a)},
        td_full=SimpleNamespace(fda_json={}),
        lib_row=SimpleNamespace(stable_version_id=600, active_version_id=None),
    )
    resp = _preflight(fake_db, pilot_id=2)  # pilot B -- not the holder (pilot_id 99)
    assert resp.status_code == 200
    body = resp.json()
    assert body["ok"] is False
    held = [i for i in body["issues"] if i["issue"] == "device_held"]
    assert len(held) == 1
    detail = held[0]["detail"]
    assert "pilot-A" in detail
    assert "bp_s1_r501" in detail or "501" in detail
    holder = held[0]["holder"]
    assert holder["pilot_name"] == "pilot-A"
    assert "acquired_at" in holder


def test_lease_key_is_host_not_host_port():
    pytest.importorskip("device_lease")
    from device_lease import normalize_host

    assert normalize_host("132.77.9.9:37497") == normalize_host("http://132.77.9.9:5556/")


def test_lease_not_reported_for_the_holding_pilot_itself():
    pytest.importorskip("device_lease")
    from device_lease import normalize_host, preflight_device_lease_issues

    host = "132.77.9.9"
    fake_db = _LeaseFakeDb(leases={normalize_host(host): {
        "pilot_id": 7, "pilot_name": "pilot-A", "session_id": 1, "run_id": 501,
        "subject_key": "bp_s1_r501", "acquired_at": "2026-08-09T10:00:00Z",
    }})
    modules = [_module(8, "OE", "OE_Control", hardware_lib_id=11)]
    configs = {"OE": {**_VALID_EXTLINK_CONFIG, "host": host}}
    issues = preflight_device_lease_issues(fake_db, pilot_id=7, modules=modules, configs=configs)
    assert issues == []


def test_force_release_lease_clears_the_issue():
    pytest.importorskip("device_lease")
    from device_lease import force_release, normalize_host, preflight_device_lease_issues

    host = "132.77.9.9"
    fake_db = _LeaseFakeDb(leases={normalize_host(host): {
        "pilot_id": 7, "pilot_name": "pilot-A", "session_id": 1, "run_id": 501,
        "subject_key": "bp_s1_r501", "acquired_at": "2026-08-09T10:00:00Z",
    }})
    modules = [_module(8, "OE", "OE_Control", hardware_lib_id=11)]
    configs = {"OE": {**_VALID_EXTLINK_CONFIG, "host": host}}

    before = preflight_device_lease_issues(fake_db, pilot_id=2, modules=modules, configs=configs)
    assert len(before) == 1

    assert force_release(fake_db, host) is True

    after = preflight_device_lease_issues(fake_db, pilot_id=2, modules=modules, configs=configs)
    assert after == []


def test_lease_reconciliation_releases_on_stale_heartbeat():
    pytest.importorskip("device_lease")
    from datetime import datetime, timedelta, timezone

    from device_lease import normalize_host, reconcile_leases

    host = "132.77.9.9"
    now = datetime.now(timezone.utc)
    stale_ts = (now - timedelta(minutes=10)).isoformat()
    fresh_ts = now.isoformat()

    fake_db = _LeaseFakeDb(leases={
        normalize_host(host): {
            "pilot_id": 1, "pilot_name": "pilot-A", "session_id": 1, "run_id": 501,
            "subject_key": "bp_s1_r501", "acquired_at": stale_ts,
        },
        normalize_host("132.77.9.10"): {
            "pilot_id": 2, "pilot_name": "pilot-B", "session_id": 2, "run_id": 502,
            "subject_key": "bp_s2_r502", "acquired_at": fresh_ts,
        },
        normalize_host("132.77.9.11"): {
            "pilot_id": 3, "pilot_name": "pilot-absent", "session_id": 3, "run_id": 503,
            "subject_key": "bp_s3_r503", "acquired_at": fresh_ts,
        },
    })
    # pilot-A has a STALE heartbeat, pilot-B a FRESH one, pilot-absent has no entry at all.
    heartbeats = {"pilot-A": stale_ts, "pilot-B": fresh_ts}

    released = reconcile_leases(fake_db, heartbeats, now=now, stale_after_s=90)
    released_hosts = {r["host"] for r in released}
    assert normalize_host(host) in released_hosts          # stale heartbeat -> released
    assert normalize_host("132.77.9.11") in released_hosts  # absent from map -> released
    assert normalize_host("132.77.9.10") not in released_hosts  # fresh heartbeat -> held
    assert all("pilot" in r for r in released)


def test_lease_issue_kind_registered():
    pytest.importorskip("device_lease")
    from routers.toolkit_dispatch import PREFLIGHT_ISSUE_KINDS

    assert "device_held" in PREFLIGHT_ISSUE_KINDS
    assert "extlink_config_invalid" in PREFLIGHT_ISSUE_KINDS
    # A future kind cannot be added without a conscious update here AND in HardwareCheckModal.tsx.
    expected = {
        "missing", "incomplete_config", "class_mismatch", "fda_ref_unresolved",
        "view_key_unresolved", "variable_never_written", "lib_version_unresolved",
        "compute_lib_import_failed", "state_wait_unsatisfiable",
        "device_held", "extlink_config_invalid",
    }
    assert PREFLIGHT_ISSUE_KINDS == expected


# --- extlink config validation (EXTLINK-10) ---------------------------------


@pytest.mark.parametrize("overrides,offending_field", [
    ({"wait_timeout_s": None}, "wait_timeout_s"),
    ({"wait_timeout_s": 3}, "wait_timeout_s"),
    ({"wait_timeout_s": 900}, "wait_timeout_s"),
    ({"role": "banana"}, "role"),
    ({"role": "sub_connect", "host": None}, "host"),
    ({"role": "router_bind"}, "listen_port"),
])
def test_lease_extlink_config_invalid_field(overrides, offending_field):
    pytest.importorskip("device_lease")
    from device_lease import validate_extlink_config

    cfg = {**_VALID_EXTLINK_CONFIG, **overrides}
    issues = validate_extlink_config("OE", 1, cfg)
    assert len(issues) == 1
    assert issues[0]["issue"] == "extlink_config_invalid"
    assert offending_field in issues[0]["detail"]


def test_lease_extlink_config_valid_row_emits_nothing():
    pytest.importorskip("device_lease")
    from device_lease import validate_extlink_config

    assert validate_extlink_config("OE", 1, _VALID_EXTLINK_CONFIG) == []


def test_lease_non_extlink_module_config_emits_nothing():
    pytest.importorskip("device_lease")
    from device_lease import is_extlink_config, validate_extlink_config

    cfg = {"class_name": "Touch_Detector", "device_name": "LICKER"}
    assert is_extlink_config(cfg) is False
    assert validate_extlink_config("LICKER", 1, cfg) == []


# --- role "none" -- control-only, no inbound transport (EXTLINK-18) ---------


def test_lease_extlink_config_role_none_accepts_neither_port():
    pytest.importorskip("device_lease")
    from device_lease import validate_extlink_config

    issues = validate_extlink_config("OE", 1, _ROLE_NONE_CONFIG)
    assert issues == []
    assert not any(
        "listen_port" in i.get("detail", "") or "connect_port" in i.get("detail", "")
        for i in issues
    )


def test_lease_extlink_config_role_none_is_a_recognised_role():
    pytest.importorskip("device_lease")
    from device_lease import is_extlink_config

    assert is_extlink_config(_ROLE_NONE_CONFIG) is True


def test_lease_extlink_config_role_none_requires_host():
    pytest.importorskip("device_lease")
    from device_lease import validate_extlink_config

    cfg = {**_ROLE_NONE_CONFIG, "host": None}
    issues = validate_extlink_config("OE", 1, cfg)
    assert len(issues) == 1
    assert "host" in issues[0]["detail"]


def test_lease_extlink_config_role_absent_is_not_role_none():
    pytest.importorskip("device_lease")
    from device_lease import is_extlink_config, validate_extlink_config

    cfg = {"class_name": "OE_Control", "host": "132.77.9.9"}
    assert is_extlink_config(cfg) is False
    assert validate_extlink_config("OE", 1, cfg) == []


def test_lease_preflight_role_none_module_is_clean():
    pytest.importorskip("device_lease")
    resp = _preflight(_oe_control_scenario())
    assert resp.status_code == 200
    body = resp.json()
    assert body["ok"] is True
    assert not any(i["issue"] == "extlink_config_invalid" for i in body["issues"])
