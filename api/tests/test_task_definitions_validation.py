"""Hard-422 trigger-assignment and variables validation (Plan 24-02 Task 2).

Pure unit tests against fda_validation functions directly — no DB, no TestClient.
Route-level (POST/PUT 422) tests are added in Task 3.
"""
from types import SimpleNamespace

from fda_validation import collect_hard_errors, validate_trigger_assignments, validate_variables


def make_toolkit(
    semantic_hardware=None,
    flags=None,
    callable_methods=None,
    hardware_module_ids=None,
    is_backend_authored=False,
    trigger_sources=None,
    include_trigger_sources_attr=True,
):
    kwargs = dict(
        states=[],
        semantic_hardware=semantic_hardware or {},
        flags=flags or {},
        callable_methods=callable_methods or [],
        hardware_module_ids=hardware_module_ids or [],
        is_backend_authored=is_backend_authored,
    )
    if include_trigger_sources_attr:
        kwargs["trigger_sources"] = trigger_sources or []
    return SimpleNamespace(**kwargs)


CANONICAL_PAYLOAD = {
    "version": 2,
    "initial_state": "idle",
    "states": {"idle": {}},
    "transitions": [],
    "variables": {"pin_number": {}, "level": {}},
    "trigger_assignments": [
        {
            "trigger_name": "TOUCH_INT",
            "actions": [
                {
                    "type": "hardware", "ref": "MPR121", "method": "detect_change",
                    "args": [], "output": ["pin_number", "level"],
                },
                {
                    "type": "if",
                    "condition": {"left": {"flag": "pin_number"}, "op": "!=", "right": None},
                    "then": [
                        {"type": "view", "key_template": "LICKER{pin_number}", "value": {"flag": "level"}},
                    ],
                    "else": [],
                },
            ],
        }
    ],
}


# ---------------------------------------------------------------------------
# Backward compat
# ---------------------------------------------------------------------------

def test_absent_trigger_assignments_returns_no_errors():
    toolkit = make_toolkit()
    assert validate_trigger_assignments({}, toolkit) == []


def test_null_trigger_assignments_returns_no_errors():
    toolkit = make_toolkit()
    assert validate_trigger_assignments({"trigger_assignments": None}, toolkit) == []


def test_empty_trigger_assignments_returns_no_errors():
    toolkit = make_toolkit()
    assert validate_trigger_assignments({"trigger_assignments": []}, toolkit) == []


def test_collect_hard_errors_toolkit_none_returns_no_errors():
    assert collect_hard_errors(CANONICAL_PAYLOAD, None) == []


# ---------------------------------------------------------------------------
# Structural errors
# ---------------------------------------------------------------------------

def test_trigger_assignments_dict_instead_of_list_errors():
    toolkit = make_toolkit()
    errors = validate_trigger_assignments({"trigger_assignments": {"not": "a list"}}, toolkit)
    assert len(errors) == 1
    assert "dict" in errors[0]


def test_entry_missing_trigger_name_errors_naming_index():
    toolkit = make_toolkit()
    fda = {"trigger_assignments": [{"actions": [{"type": "special", "ref": "INC_TRIAL_COUNTER"}]}]}
    errors = validate_trigger_assignments(fda, toolkit)
    assert any("[0]" in e and "trigger_name" in e for e in errors)


def test_entry_empty_trigger_name_errors_naming_index():
    toolkit = make_toolkit()
    fda = {"trigger_assignments": [{"trigger_name": "  ", "actions": [{"type": "special", "ref": "INC_TRIAL_COUNTER"}]}]}
    errors = validate_trigger_assignments(fda, toolkit)
    assert any("[0]" in e and "trigger_name" in e for e in errors)


def test_unknown_trigger_name_errors_when_trigger_sources_known():
    toolkit = make_toolkit(trigger_sources=[{"hw_id": "TOUCH_INT"}])
    fda = {"trigger_assignments": [{"trigger_name": "BOGUS", "actions": [{"type": "special", "ref": "INC_TRIAL_COUNTER"}]}]}
    errors = validate_trigger_assignments(fda, toolkit)
    assert any("BOGUS" in e and "TOUCH_INT" in e for e in errors)


def test_unknown_trigger_name_not_enforced_when_trigger_sources_attr_absent():
    toolkit = make_toolkit(include_trigger_sources_attr=False)
    fda = {"trigger_assignments": [{"trigger_name": "BOGUS", "actions": [{"type": "special", "ref": "INC_TRIAL_COUNTER"}]}]}
    errors = validate_trigger_assignments(fda, toolkit)
    assert errors == []


def test_unknown_trigger_name_not_enforced_when_trigger_sources_empty():
    toolkit = make_toolkit(trigger_sources=[])
    fda = {"trigger_assignments": [{"trigger_name": "BOGUS", "actions": [{"type": "special", "ref": "INC_TRIAL_COUNTER"}]}]}
    errors = validate_trigger_assignments(fda, toolkit)
    assert errors == []


def test_no_actions_key_errors():
    toolkit = make_toolkit()
    fda = {"trigger_assignments": [{"trigger_name": "TOUCH_INT"}]}
    errors = validate_trigger_assignments(fda, toolkit)
    assert any("actions" in e for e in errors)


def test_actions_null_errors():
    toolkit = make_toolkit()
    fda = {"trigger_assignments": [{"trigger_name": "TOUCH_INT", "actions": None}]}
    errors = validate_trigger_assignments(fda, toolkit)
    assert any("actions" in e for e in errors)


def test_actions_empty_list_errors():
    toolkit = make_toolkit()
    fda = {"trigger_assignments": [{"trigger_name": "TOUCH_INT", "actions": []}]}
    errors = validate_trigger_assignments(fda, toolkit)
    assert any("actions" in e for e in errors)


def test_legacy_handler_only_entry_errors_actions_required():
    toolkit = make_toolkit()
    fda = {"trigger_assignments": [{"trigger_name": "TOUCH_INT", "handler": "touch_detector", "config": {}}]}
    errors = validate_trigger_assignments(fda, toolkit)
    assert any("actions" in e for e in errors)


def test_actions_not_a_list_errors():
    toolkit = make_toolkit()
    fda = {"trigger_assignments": [{"trigger_name": "TOUCH_INT", "actions": {"not": "a list"}}]}
    errors = validate_trigger_assignments(fda, toolkit)
    assert any("actions" in e for e in errors)


def test_unknown_extra_keys_ignored():
    toolkit = make_toolkit()
    fda = {
        "trigger_assignments": [
            {
                "trigger_name": "TOUCH_INT",
                "handler": "touch_detector",
                "config": {"hardware_ref": "x"},
                "actions": [{"type": "special", "ref": "INC_TRIAL_COUNTER"}],
            }
        ]
    }
    assert validate_trigger_assignments(fda, toolkit) == []


# ---------------------------------------------------------------------------
# Action errors
# ---------------------------------------------------------------------------

def test_unknown_action_type_errors_listing_allowed_types():
    toolkit = make_toolkit()
    fda = {"trigger_assignments": [{"trigger_name": "TOUCH_INT", "actions": [{"type": "telepathy"}]}]}
    errors = validate_trigger_assignments(fda, toolkit)
    assert len(errors) == 1
    for kind in ("hardware", "flag", "timer", "special", "method", "if", "view"):
        assert kind in errors[0]


def test_unknown_hardware_ref_errors_when_semantic_hardware_known():
    toolkit = make_toolkit(semantic_hardware={"MPR121": ["I2C", "MPR121"]})
    fda = {
        "trigger_assignments": [
            {"trigger_name": "TOUCH_INT", "actions": [{"type": "hardware", "ref": "NOPE", "method": "x"}]}
        ]
    }
    errors = validate_trigger_assignments(fda, toolkit)
    assert any("NOPE" in e for e in errors)


def test_direct_ref_hardware_action_with_group_key_skips_ref_check():
    toolkit = make_toolkit(semantic_hardware={"MPR121": ["I2C", "MPR121"]}, is_backend_authored=True)
    fda = {
        "trigger_assignments": [
            {
                "trigger_name": "TOUCH_INT",
                "actions": [{"type": "hardware", "group": "I2C", "ref": "NOPE", "method": "x"}],
            }
        ]
    }
    assert validate_trigger_assignments(fda, toolkit) == []


def test_method_ref_not_in_callable_methods_errors():
    toolkit = make_toolkit(callable_methods=["detectedLick"])
    fda = {
        "trigger_assignments": [
            {"trigger_name": "TOUCH_INT", "actions": [{"type": "method", "ref": "notCallable"}]}
        ]
    }
    errors = validate_trigger_assignments(fda, toolkit)
    assert any("notCallable" in e for e in errors)


def test_special_unknown_ref_errors_naming_inc_trial_counter():
    toolkit = make_toolkit()
    fda = {"trigger_assignments": [{"trigger_name": "TOUCH_INT", "actions": [{"type": "special", "ref": "BOOM"}]}]}
    errors = validate_trigger_assignments(fda, toolkit)
    assert any("INC_TRIAL_COUNTER" in e for e in errors)


def test_flag_ref_not_declared_errors():
    toolkit = make_toolkit(flags={"trial_counter": {}})
    fda = {"trigger_assignments": [{"trigger_name": "TOUCH_INT", "actions": [{"type": "flag", "ref": "ghost"}]}]}
    errors = validate_trigger_assignments(fda, toolkit)
    assert any("ghost" in e for e in errors)


def test_flag_ref_declared_via_variables_is_ok():
    toolkit = make_toolkit()
    fda = {
        "variables": {"pin_number": {}},
        "trigger_assignments": [{"trigger_name": "TOUCH_INT", "actions": [{"type": "flag", "ref": "pin_number"}]}],
    }
    assert validate_trigger_assignments(fda, toolkit) == []


def test_view_action_no_key_template_errors():
    toolkit = make_toolkit()
    fda = {"trigger_assignments": [{"trigger_name": "TOUCH_INT", "actions": [{"type": "view"}]}]}
    errors = validate_trigger_assignments(fda, toolkit)
    assert any("key_template" in e for e in errors)


def test_view_action_key_template_token_not_declared_errors_naming_ghost():
    toolkit = make_toolkit()
    fda = {
        "trigger_assignments": [
            {
                "trigger_name": "TOUCH_INT",
                "actions": [{"type": "view", "key_template": "LICKER{ghost}", "value": {"flag": "level"}}],
            }
        ]
    }
    errors = validate_trigger_assignments(fda, toolkit)
    assert any("ghost" in e for e in errors)


def test_if_action_recurses_into_then_and_else_reporting_both():
    toolkit = make_toolkit()
    fda = {
        "trigger_assignments": [
            {
                "trigger_name": "TOUCH_INT",
                "actions": [
                    {
                        "type": "if",
                        "condition": {},
                        "then": [{"type": "flag", "ref": "ghost_then"}],
                        "else": [{"type": "flag", "ref": "ghost_else"}],
                    }
                ],
            }
        ]
    }
    errors = validate_trigger_assignments(fda, toolkit)
    assert any("ghost_then" in e for e in errors)
    assert any("ghost_else" in e for e in errors)


def test_output_string_not_declared_errors_naming_ghost():
    toolkit = make_toolkit()
    fda = {
        "trigger_assignments": [
            {
                "trigger_name": "TOUCH_INT",
                "actions": [{"type": "special", "ref": "INC_TRIAL_COUNTER", "output": "ghost"}],
            }
        ]
    }
    errors = validate_trigger_assignments(fda, toolkit)
    assert any("ghost" in e for e in errors)


def test_output_list_partial_not_declared_errors_naming_only_ghost():
    toolkit = make_toolkit()
    fda = {
        "variables": {"ok": {}},
        "trigger_assignments": [
            {
                "trigger_name": "TOUCH_INT",
                "actions": [{"type": "special", "ref": "INC_TRIAL_COUNTER", "output": ["ok", "ghost"]}],
            }
        ],
    }
    errors = validate_trigger_assignments(fda, toolkit)
    assert any("ghost" in e for e in errors)
    assert not any("'ok'" in e for e in errors)


def test_args_kwargs_bad_trigger_key_errors_listing_level_tick():
    toolkit = make_toolkit(flags={"trial_counter": {}})
    fda = {
        "trigger_assignments": [
            {
                "trigger_name": "TOUCH_INT",
                "actions": [
                    {"type": "flag", "ref": "trial_counter", "args": [{"trigger": "bogus"}]},
                ],
            }
        ]
    }
    errors = validate_trigger_assignments(fda, toolkit)
    assert any("bogus" in e and "level" in e and "tick" in e for e in errors)


def test_args_kwargs_valid_trigger_key_is_ok():
    toolkit = make_toolkit(flags={"trial_counter": {}})
    fda = {
        "trigger_assignments": [
            {
                "trigger_name": "TOUCH_INT",
                "actions": [
                    {"type": "flag", "ref": "trial_counter", "kwargs": {"pi_timestamp": {"trigger": "tick"}}},
                ],
            }
        ]
    }
    assert validate_trigger_assignments(fda, toolkit) == []


# ---------------------------------------------------------------------------
# Variables errors
# ---------------------------------------------------------------------------

def test_variables_list_instead_of_dict_errors():
    toolkit = make_toolkit()
    errors = validate_variables({"variables": ["not", "a", "dict"]}, toolkit)
    assert len(errors) == 1
    assert "list" in errors[0]


def test_variable_colliding_with_toolkit_flag_errors_naming_it():
    toolkit = make_toolkit(flags={"trial_counter": {}})
    errors = validate_variables({"variables": {"trial_counter": {}}}, toolkit)
    assert any("trial_counter" in e for e in errors)


def test_variables_no_collision_is_ok():
    toolkit = make_toolkit(flags={"trial_counter": {}})
    assert validate_variables({"variables": {"pin_number": {}}}, toolkit) == []


# ---------------------------------------------------------------------------
# Happy path
# ---------------------------------------------------------------------------

def test_canonical_lick_payload_against_toolkit_with_mpr121_returns_no_errors():
    toolkit = make_toolkit(semantic_hardware={"MPR121": ["I2C", "MPR121"]})
    assert collect_hard_errors(CANONICAL_PAYLOAD, toolkit) == []
