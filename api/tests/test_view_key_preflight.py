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
        if "FROM task_toolkits" in sql:
            return _Result(one=self.toolkit_row)
        if "fda_json FROM task_definitions" in sql:
            return _Result(one=self.td_full)
        if sql.startswith("SELECT name, config FROM pilot_hardware_config"):
            return _Result(many=self.existing_configs)
        if sql.startswith("SELECT id, name, class_name FROM hardware_modules"):
            return _Result(one=self.modules.get(params.get("id")))
        if sql.startswith("SELECT name, class_name FROM hardware_modules"):
            return _Result(one=self.modules.get(params.get("id")))
        if "FROM pilot_hardware_config" in sql and "name = :name" in sql:
            return _Result(one=self.configs.get(params.get("name")))
        return _Result()


def _module(module_id, name, class_name):
    return SimpleNamespace(id=module_id, name=name, class_name=class_name)


def _config(config_dict):
    return SimpleNamespace(config=config_dict)


MPR121_CONFIG = {"device_name": "LICKER", "num_detectors": 4, "first_channel": 1, "class_name": "Touch_Detector"}


def _backend_toolkit_scenario(fda_json, mpr121_config=MPR121_CONFIG, flags=None, module_ids=None):
    module_ids = module_ids if module_ids is not None else [7]
    return FakeDb(
        run_row=None,
        spr_row=SimpleNamespace(protocol_id=1),
        step_row=SimpleNamespace(task_definition_id=42),
        td_row=SimpleNamespace(toolkit_id=5),
        toolkit_row=SimpleNamespace(is_backend_authored=True, hardware_module_ids=module_ids, flags=flags or {}),
        # preflight_validate indexes these rows positionally (row[0], row[1]) — tuples, not dicts.
        existing_configs=([("MPR121", mpr121_config)] if mpr121_config is not None else []),
        modules={7: _module(7, "MPR121", "Touch_Detector")},
        configs=({"MPR121": _config(mpr121_config)} if mpr121_config is not None else {}),
        td_full=SimpleNamespace(fda_json=fda_json),
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


def test_toolkit_hw_capabilities_module_names_survives_row_with_no_source_code():
    from hw_introspect import toolkit_hw_capabilities

    class _FakeRows:
        def __init__(self, rows):
            self._rows = rows

        def fetchall(self):
            return self._rows

    class _FakeDb:
        def __init__(self, rows):
            self._rows = rows

        def execute(self, *_a, **_kw):
            return _FakeRows(self._rows)

    rows = [SimpleNamespace(id=1, name="TOUCH_INT", class_name="Digital_In", source_code=None)]
    caps = toolkit_hw_capabilities(_FakeDb(rows), [1])
    assert caps["module_names"] == ["TOUCH_INT"]
    assert caps["module_methods"] == {}  # source_code=None -> skipped by the per-row guard


def test_toolkit_hw_capabilities_module_names_present_on_both_returns():
    from hw_introspect import toolkit_hw_capabilities

    empty_path = toolkit_hw_capabilities(None, [])
    assert "module_names" in empty_path
    assert empty_path["module_names"] == []

    class _FakeRows:
        def __init__(self, rows):
            self._rows = rows

        def fetchall(self):
            return self._rows

    class _FakeDb:
        def __init__(self, rows):
            self._rows = rows

        def execute(self, *_a, **_kw):
            return _FakeRows(self._rows)

    rows = [SimpleNamespace(id=7, name="MPR121", class_name="Touch_Detector", source_code="class Touch_Detector:\n    pass\n")]
    non_empty_path = toolkit_hw_capabilities(_FakeDb(rows), [7])
    assert "module_names" in non_empty_path
    assert non_empty_path["module_names"] == ["MPR121"]
