"""Tests for the FDA view-key/detector-ref scanner and per-pilot resolver (Plan 25-03).

Task 1: pure unit tests against detector_keys.scan_fda_view_keys / resolve_view_key_issues
directly — no DB, no TestClient, matching test_detector_keys.py's style.
Task 2: route-level tests for preflight_validate's new step 8, mocked-db.execute style.
Task 3: detector_channels/is_detector wiring on the toolkit and hardware-module read routes.
"""
from types import SimpleNamespace

import pytest

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
