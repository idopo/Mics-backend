"""Tests for fda_utils.scan_fda_for_refs and ref_label (Plan 24-02 Task 1)."""
from fda_utils import ref_label, scan_fda_for_refs


# ---------------------------------------------------------------------------
# scan_fda_for_refs — states (regression, must not change)
# ---------------------------------------------------------------------------

def test_state_hardware_action_returns_one_state_scoped_result():
    fda = {
        "states": {
            "reward": {
                "entry_actions": [
                    {"type": "hardware", "ref": "VALVE", "method": "open"},
                ]
            }
        }
    }
    results = scan_fda_for_refs(fda)
    assert len(results) == 1
    assert results[0]["scope"] == "state"
    assert results[0]["state_name"] == "reward"
    assert results[0]["ref"] == "VALVE"


def test_state_nested_if_then_else_branches_are_walked():
    fda = {
        "states": {
            "idle": {
                "entry_actions": [
                    {
                        "type": "if",
                        "condition": {},
                        "then": [{"type": "hardware", "ref": "A", "method": "m"}],
                        "else": [{"type": "hardware", "ref": "B", "method": "m"}],
                    }
                ]
            }
        }
    }
    results = scan_fda_for_refs(fda)
    refs = {r["ref"] for r in results}
    assert refs == {"A", "B"}
    assert all(r["scope"] == "state" for r in results)


# ---------------------------------------------------------------------------
# scan_fda_for_refs — triggers (new)
# ---------------------------------------------------------------------------

def test_trigger_hardware_action_returns_one_trigger_scoped_result():
    fda = {
        "trigger_assignments": [
            {
                "trigger_name": "TOUCH_INT",
                "actions": [
                    {"type": "hardware", "ref": "MPR121", "method": "detect_change"},
                ],
            }
        ]
    }
    results = scan_fda_for_refs(fda)
    assert len(results) == 1
    assert results[0]["scope"] == "trigger"
    assert results[0]["state_name"] == "TOUCH_INT"
    assert results[0]["ref"] == "MPR121"
    assert results[0]["method"] == "detect_change"


def test_trigger_if_then_else_hardware_refs_both_returned():
    fda = {
        "trigger_assignments": [
            {
                "trigger_name": "TOUCH_INT",
                "actions": [
                    {
                        "type": "if",
                        "condition": {},
                        "then": [{"type": "hardware", "ref": "A", "method": "m"}],
                        "else": [{"type": "hardware", "ref": "B", "method": "m"}],
                    }
                ],
            }
        ]
    }
    results = scan_fda_for_refs(fda)
    refs = {r["ref"] for r in results}
    assert refs == {"A", "B"}
    assert all(r["scope"] == "trigger" for r in results)


def test_legacy_handler_only_entry_contributes_no_results():
    fda = {
        "trigger_assignments": [
            {"trigger_name": "TOUCH_INT", "handler": "touch_detector", "config": {}}
        ]
    }
    assert scan_fda_for_refs(fda) == []


def test_trigger_assignments_absent_returns_no_results_no_exception():
    assert scan_fda_for_refs({}) == []


def test_trigger_assignments_null_returns_no_results_no_exception():
    assert scan_fda_for_refs({"trigger_assignments": None}) == []


def test_trigger_assignments_not_a_list_returns_no_results_no_exception():
    assert scan_fda_for_refs({"trigger_assignments": {"not": "a list"}}) == []


def test_view_action_contributes_no_ref_result():
    fda = {
        "trigger_assignments": [
            {
                "trigger_name": "TOUCH_INT",
                "actions": [
                    {"type": "view", "key_template": "LICKER{pin_number}", "value": {"flag": "level"}},
                ],
            }
        ]
    }
    assert scan_fda_for_refs(fda) == []


# ---------------------------------------------------------------------------
# scan_fda_for_refs — compute actions (Plan 23-03 Task 1, CMP-11)
# ---------------------------------------------------------------------------

def test_state_compute_action_returns_ref_method_and_output():
    fda = {
        "states": {
            "roll": {
                "entry_actions": [
                    {"type": "compute", "ref": "COMPUTE", "method": "random_bool", "args": [0.5], "output": "target"},
                ]
            }
        }
    }
    results = scan_fda_for_refs(fda)
    assert len(results) == 1
    entry = results[0]
    assert entry["scope"] == "state"
    assert entry["action_type"] == "compute"
    assert entry["ref"] == "COMPUTE"
    assert entry["method"] == "random_bool"
    assert entry["output"] == "target"


def test_trigger_compute_action_returns_one_trigger_scoped_result():
    fda = {
        "trigger_assignments": [
            {
                "trigger_name": "TOUCH_INT",
                "actions": [
                    {"type": "compute", "ref": "COMPUTE", "method": "add", "args": [1], "output": "counter"},
                ],
            }
        ]
    }
    results = scan_fda_for_refs(fda)
    assert len(results) == 1
    assert results[0]["scope"] == "trigger"
    assert results[0]["action_type"] == "compute"
    assert results[0]["output"] == "counter"


def test_compute_action_in_if_then_and_else_branches_both_returned():
    fda = {
        "trigger_assignments": [
            {
                "trigger_name": "TOUCH_INT",
                "actions": [
                    {
                        "type": "if",
                        "condition": {},
                        "then": [{"type": "compute", "ref": "COMPUTE", "method": "add", "output": "a"}],
                        "else": [{"type": "compute", "ref": "COMPUTE", "method": "sub", "output": "b"}],
                    }
                ],
            }
        ]
    }
    results = scan_fda_for_refs(fda)
    outputs = {r["output"] for r in results}
    assert outputs == {"a", "b"}
    assert all(r["action_type"] == "compute" for r in results)


def test_hardware_action_output_key_present_and_none_when_absent():
    """Existing hardware-action entries now carry `output` too — None when not declared."""
    fda = {"states": {"reward": {"entry_actions": [{"type": "hardware", "ref": "VALVE", "method": "open"}]}}}
    results = scan_fda_for_refs(fda)
    assert results[0]["output"] is None


# ---------------------------------------------------------------------------
# ref_label
# ---------------------------------------------------------------------------

def test_ref_label_state_scope():
    assert ref_label({"scope": "state", "state_name": "reward"}) == "State 'reward'"


def test_ref_label_trigger_scope():
    assert ref_label({"scope": "trigger", "state_name": "TOUCH_INT"}) == "Trigger 'TOUCH_INT'"


def test_ref_label_defaults_to_state_form_when_scope_absent():
    assert ref_label({"state_name": "legacy"}) == "State 'legacy'"
