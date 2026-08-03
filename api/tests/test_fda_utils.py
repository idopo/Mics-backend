"""Tests for fda_utils.scan_fda_for_refs and ref_label (Plan 24-02 Task 1)."""
from fda_utils import ref_label, scan_fda_for_refs
from variable_scan import scan_variable_readers, scan_variable_writers, variable_never_written_issues


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


# ---------------------------------------------------------------------------
# variable_scan.scan_variable_writers (Plan 23-03 Task 3, CMP-15 backend)
# ---------------------------------------------------------------------------

def test_writer_from_compute_action_output():
    fda = {
        "variables": {"target": {}},
        "states": {"roll": {"entry_actions": [
            {"type": "compute", "ref": "COMPUTE", "method": "random_bool", "output": "target"},
        ]}},
    }
    writers = scan_variable_writers(fda)
    assert writers == {"target": ["states.roll.entry_actions[0]"]}


def test_writer_from_output_list_records_every_name():
    fda = {
        "variables": {"pin_number": {}, "level": {}},
        "trigger_assignments": [{
            "trigger_name": "TOUCH_INT",
            "actions": [{"type": "hardware", "ref": "MPR121", "method": "detect_change", "output": ["pin_number", "level"]}],
        }],
    }
    writers = scan_variable_writers(fda)
    assert set(writers) == {"pin_number", "level"}


def test_writer_from_flag_action_ref():
    fda = {
        "variables": {"lever_pressed": {}},
        "states": {"idle": {"entry_actions": [{"type": "flag", "ref": "lever_pressed"}]}},
    }
    writers = scan_variable_writers(fda)
    assert "lever_pressed" in writers


def test_writer_from_initial_value_declaration():
    fda = {"variables": {"counter": {"initial_value": 0}}}
    writers = scan_variable_writers(fda)
    assert writers == {"counter": ["variables.counter"]}


def test_writer_initial_value_none_does_not_count():
    fda = {"variables": {"counter": {"initial_value": None}}}
    assert scan_variable_writers(fda) == {}


def test_writer_recurses_into_if_then_and_else():
    fda = {
        "variables": {"a": {}, "b": {}},
        "trigger_assignments": [{
            "trigger_name": "TOUCH_INT",
            "actions": [{
                "type": "if", "condition": {},
                "then": [{"type": "compute", "ref": "COMPUTE", "method": "m", "output": "a"}],
                "else": [{"type": "compute", "ref": "COMPUTE", "method": "m", "output": "b"}],
            }],
        }],
    }
    writers = scan_variable_writers(fda)
    assert set(writers) == {"a", "b"}


def test_writers_empty_when_variables_registry_absent():
    assert scan_variable_writers({"states": {}}) == {}


def test_writers_never_raises_on_malformed_states():
    fda = {"variables": {"x": {}}, "states": "not a dict or list"}
    assert scan_variable_writers(fda) == {}


def test_writers_never_raises_on_non_dict_fda_json():
    assert scan_variable_writers("not a dict") == {}
    assert scan_variable_writers(None) == {}


# ---------------------------------------------------------------------------
# variable_scan.scan_variable_readers
# ---------------------------------------------------------------------------

def test_reader_from_condition_view_operand():
    fda = {
        "variables": {"target": {}},
        "transitions": [{"condition_tree": {"left": {"view": "target"}, "op": "==", "right": 1}}],
    }
    readers = scan_variable_readers(fda)
    assert readers == {"target": ["transitions[0].condition_tree.left"]}


def test_reader_from_condition_flag_operand():
    fda = {
        "variables": {"target": {}},
        "transitions": [{"condition_tree": {"left": {"flag": "target"}, "op": "==", "right": 1}}],
    }
    assert "target" in scan_variable_readers(fda)


def test_reader_from_view_action_key_template_token():
    fda = {
        "variables": {"pin_number": {}},
        "trigger_assignments": [{
            "trigger_name": "TOUCH_INT",
            "actions": [{"type": "view", "key_template": "LICKER{pin_number}", "value": 1}],
        }],
    }
    readers = scan_variable_readers(fda)
    assert "pin_number" in readers
    assert readers["pin_number"][0].endswith(".key_template")


def test_reader_from_compute_action_args():
    fda = {
        "variables": {"counter": {}},
        "states": {"roll": {"entry_actions": [
            {"type": "compute", "ref": "COMPUTE", "method": "add", "args": [{"flag": "counter"}, 1], "output": "counter"},
        ]}},
    }
    readers = scan_variable_readers(fda)
    assert "counter" in readers


def test_reader_from_hardware_action_kwargs():
    fda = {
        "variables": {"level": {}},
        "trigger_assignments": [{
            "trigger_name": "TOUCH_INT",
            "actions": [{"type": "hardware", "ref": "LED", "method": "set", "kwargs": {"value": {"flag": "level"}}}],
        }],
    }
    assert "level" in scan_variable_readers(fda)


def test_readers_empty_when_variables_registry_absent():
    fda = {"transitions": [{"condition_tree": {"left": {"view": "target"}, "op": "==", "right": 1}}]}
    assert scan_variable_readers(fda) == {}


def test_readers_ignore_names_not_declared_as_variables():
    fda = {
        "variables": {"pin_number": {}},
        "transitions": [{"condition_tree": {"left": {"flag": "trial_counter"}, "op": "==", "right": 1}}],
    }
    assert scan_variable_readers(fda) == {}


def test_readers_never_raises_on_non_dict_fda_json():
    assert scan_variable_readers("nope") == {}


# ---------------------------------------------------------------------------
# variable_scan.variable_never_written_issues
# ---------------------------------------------------------------------------

def test_variable_read_but_never_written_is_flagged():
    fda = {
        "variables": {"target": {}},
        "transitions": [{"condition_tree": {"left": {"view": "target"}, "op": "==", "right": 1}}],
    }
    issues = variable_never_written_issues(fda)
    assert len(issues) == 1
    issue = issues[0]
    assert issue["issue"] == "variable_never_written"
    assert issue["variable"] == "target"
    assert issue["module_id"] is None
    assert issue["location"] == "transitions[0].condition_tree.left"
    assert "target" in issue["detail"]


def test_variable_written_only_by_initial_value_and_read_is_not_flagged():
    fda = {
        "variables": {"counter": {"initial_value": 0}},
        "transitions": [{"condition_tree": {"left": {"view": "counter"}, "op": ">", "right": 0}}],
    }
    assert variable_never_written_issues(fda) == []


def test_self_referencing_counter_arg_and_output_not_flagged():
    """add(counter, 1) -> counter: counter is both a reader (its own arg) and a writer (the
    action's own output) — the supported counter pattern must not be flagged."""
    fda = {
        "variables": {"counter": {}},
        "trigger_assignments": [{
            "trigger_name": "TOUCH_INT",
            "actions": [
                {"type": "compute", "ref": "COMPUTE", "method": "add",
                 "args": [{"flag": "counter"}, 1], "output": "counter"},
            ],
        }],
    }
    assert variable_never_written_issues(fda) == []


def test_empty_variables_registry_returns_empty_list():
    assert variable_never_written_issues({"states": {}}) == []
    assert variable_never_written_issues({"variables": {}}) == []


def test_non_dict_fda_json_returns_empty_list_never_raises():
    assert variable_never_written_issues(None) == []
    assert variable_never_written_issues("nope") == []
    assert variable_never_written_issues([]) == []
