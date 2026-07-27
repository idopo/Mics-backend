"""Hard-422 trigger-assignment and variables validation (Plan 24-02 Task 2 + 3).

Task 2: pure unit tests against fda_validation functions directly — no DB, no TestClient.
Task 3: route-level (POST/PUT 422) tests, following the fixture style of
test_toolkits_router.py.
"""
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from fda_validation import (
    collect_hard_errors,
    validate_state_actions,
    validate_trigger_assignments,
    validate_variables,
)


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
                        {
                            "type": "view", "key_template": "{device_name}{pin_number}",
                            "source_ref": "MPR121", "value": {"flag": "level"},
                        },
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


# ---------------------------------------------------------------------------
# Task 3 — route-level 422 tests (PUT/POST /api/task-definitions)
# ---------------------------------------------------------------------------

def auth_headers():
    return {"Authorization": "Bearer test-token"}


@pytest.fixture
def client():
    from auth import verify_token
    from main import app
    app.dependency_overrides[verify_token] = lambda: {"sub": "test"}
    yield TestClient(app)
    app.dependency_overrides.clear()


def make_db_mock(defn=None, toolkit=None):
    """MagicMock standing in for the OrmSession `_SA_SessionLocal()` returns.

    `db.query(Model)` is dispatched by model class so the route code's TaskDefinition lookup
    and fda_validation.reject_if_hard_errors' TaskToolkit lookup each get the right stub.
    """
    from models import TaskDefinition, TaskToolkit

    mock_db = MagicMock()

    def _query(model):
        q = MagicMock()
        if model is TaskDefinition:
            q.filter.return_value.one_or_none.return_value = defn
        elif model is TaskToolkit:
            q.filter.return_value.one_or_none.return_value = toolkit
        else:
            q.filter.return_value.one_or_none.return_value = None
            q.filter.return_value.all.return_value = []
        return q

    mock_db.query.side_effect = _query
    mock_db.execute.return_value.fetchone.return_value = None
    mock_db.execute.return_value.fetchall.return_value = []
    return mock_db


def make_defn_mock(defn_id=1, toolkit_id=5):
    defn = MagicMock()
    defn.id = defn_id
    defn.toolkit_id = toolkit_id
    return defn


def test_put_bad_trigger_hardware_ref_returns_422_not_200_broken(client):
    defn = make_defn_mock()
    toolkit = make_toolkit(semantic_hardware={"MPR121": ["I2C", "MPR121"]})
    mock_db = make_db_mock(defn=defn, toolkit=toolkit)
    payload = {
        "fda_json": {
            "states": {},
            "trigger_assignments": [
                {"trigger_name": "TOUCH_INT", "actions": [{"type": "hardware", "ref": "NOPE", "method": "x"}]}
            ],
        }
    }
    with patch("routers.toolkits._SA_SessionLocal") as mock_factory:
        mock_factory.return_value = mock_db
        resp = client.put("/api/task-definitions/1", json=payload, headers=auth_headers())

    assert resp.status_code == 422
    body = resp.json()
    assert "validation_status" not in body
    assert any("NOPE" in e for e in body["detail"]["errors"])


def test_post_unsupported_action_type_returns_422(client):
    toolkit = make_toolkit()
    mock_db = make_db_mock(defn=None, toolkit=toolkit)
    payload = {
        "display_name": "test",
        "toolkit_name": "AppetitiveTaskReal",
        "toolkit_id": 5,
        "fda_json": {
            "states": {},
            "trigger_assignments": [
                {"trigger_name": "TOUCH_INT", "actions": [{"type": "telepathy"}]}
            ],
        },
    }
    with patch("routers.toolkits._SA_SessionLocal") as mock_factory:
        mock_factory.return_value = mock_db
        resp = client.post("/api/task-definitions", json=payload, headers=auth_headers())

    assert resp.status_code == 422
    assert any("telepathy" in e for e in resp.json()["detail"]["errors"])


def test_put_legacy_handler_only_no_actions_returns_422(client):
    defn = make_defn_mock()
    toolkit = make_toolkit()
    mock_db = make_db_mock(defn=defn, toolkit=toolkit)
    payload = {
        "fda_json": {
            "states": {},
            "trigger_assignments": [
                {"trigger_name": "TOUCH_INT", "handler": "touch_detector", "config": {"hardware_ref": "MPR121"}}
            ],
        }
    }
    with patch("routers.toolkits._SA_SessionLocal") as mock_factory:
        mock_factory.return_value = mock_db
        resp = client.put("/api/task-definitions/1", json=payload, headers=auth_headers())

    assert resp.status_code == 422
    assert any("actions" in e for e in resp.json()["detail"]["errors"])


def test_put_empty_trigger_name_returns_422(client):
    defn = make_defn_mock()
    toolkit = make_toolkit()
    mock_db = make_db_mock(defn=defn, toolkit=toolkit)
    payload = {
        "fda_json": {
            "states": {},
            "trigger_assignments": [
                {"trigger_name": "", "actions": [{"type": "special", "ref": "INC_TRIAL_COUNTER"}]}
            ],
        }
    }
    with patch("routers.toolkits._SA_SessionLocal") as mock_factory:
        mock_factory.return_value = mock_db
        resp = client.put("/api/task-definitions/1", json=payload, headers=auth_headers())

    assert resp.status_code == 422
    assert any("trigger_name" in e for e in resp.json()["detail"]["errors"])


def test_put_absent_trigger_assignments_still_saves_200(client):
    defn = make_defn_mock()
    toolkit = make_toolkit()
    mock_db = make_db_mock(defn=defn, toolkit=toolkit)
    payload = {"fda_json": {"states": {"idle": {}}}}
    with patch("routers.toolkits._SA_SessionLocal") as mock_factory:
        mock_factory.return_value = mock_db
        resp = client.put("/api/task-definitions/1", json=payload, headers=auth_headers())

    assert resp.status_code == 200
    assert resp.json()["validation_status"] == "ok"


def test_put_state_body_hw_drift_still_200_broken(client):
    """Proves the soft _validate_task_definition path was not repurposed by the hard gate."""
    defn = make_defn_mock()
    toolkit = make_toolkit(flags={})
    mock_db = make_db_mock(defn=defn, toolkit=toolkit)
    payload = {
        "fda_json": {
            "states": {
                "reward": {"entry_actions": [{"type": "flag", "ref": "ghost_flag"}]},
            }
        }
    }
    with patch("routers.toolkits._SA_SessionLocal") as mock_factory:
        mock_factory.return_value = mock_db
        resp = client.put("/api/task-definitions/1", json=payload, headers=auth_headers())

    assert resp.status_code == 200
    assert resp.json()["validation_status"] == "broken"


# --- Backend-authored module refs (TRIGA-07 gap found during live validation) ---
# A backend-authored toolkit declares its hardware as Modules rows, not SEMANTIC_HARDWARE.
# Without these, known_hw was empty for such a toolkit and EVERY hardware ref passed.

def _trigger_fda(ref):
    return {
        "version": 2, "initial_state": "s", "states": {"s": {}}, "transitions": [],
        "trigger_assignments": [
            {"trigger_name": "TOUCH_INT",
             "actions": [{"type": "hardware", "ref": ref, "method": "set"}]}
        ],
    }


def test_backend_authored_unknown_module_ref_rejected():
    toolkit = make_toolkit(is_backend_authored=True, hardware_module_ids=[1, 2])
    errors = validate_trigger_assignments(
        _trigger_fda("NOPE_NOT_REAL"), toolkit, module_names={"Right_LED", "Solenoid"}
    )
    assert any("unknown hardware ref 'NOPE_NOT_REAL'" in e for e in errors), errors


def test_backend_authored_known_module_ref_accepted():
    toolkit = make_toolkit(is_backend_authored=True, hardware_module_ids=[1, 2])
    errors = validate_trigger_assignments(
        _trigger_fda("Right_LED"), toolkit, module_names={"Right_LED", "Solenoid"}
    )
    assert errors == [], errors


def test_module_names_union_with_semantic_hardware():
    """Both naming schemes resolve — a toolkit may carry SEMANTIC_HARDWARE and Modules."""
    toolkit = make_toolkit(semantic_hardware={"MPR121": ["I2C", "MPR121"]}, is_backend_authored=True)
    assert validate_trigger_assignments(_trigger_fda("MPR121"), toolkit, module_names={"Right_LED"}) == []
    assert validate_trigger_assignments(_trigger_fda("Right_LED"), toolkit, module_names={"Right_LED"}) == []


def test_no_known_hardware_at_all_still_permissive():
    """Classic toolkit with neither semantic_hardware nor modules keeps the lenient posture."""
    toolkit = make_toolkit()
    assert validate_trigger_assignments(_trigger_fda("anything"), toolkit) == []


# ---------------------------------------------------------------------------
# TRIGA-16 (Plan 08 Task 2): hardware/timer action `method` validation
# ---------------------------------------------------------------------------

def _hw_action(ref="MPR121", method="detect_change", action_type="hardware"):
    return {"type": action_type, "ref": ref, "method": method}


def test_empty_method_string_errors_naming_ref_and_trigger():
    toolkit = make_toolkit()
    fda = {"trigger_assignments": [{"trigger_name": "TOUCH_INT", "actions": [_hw_action(method="")]}]}
    errors = validate_trigger_assignments(fda, toolkit)
    assert any("MPR121" in e and "TOUCH_INT" in e for e in errors)


def test_missing_method_key_errors():
    toolkit = make_toolkit()
    action = {"type": "hardware", "ref": "MPR121"}
    fda = {"trigger_assignments": [{"trigger_name": "TOUCH_INT", "actions": [action]}]}
    errors = validate_trigger_assignments(fda, toolkit)
    assert any("MPR121" in e for e in errors)


def test_whitespace_only_method_errors():
    toolkit = make_toolkit()
    fda = {"trigger_assignments": [{"trigger_name": "TOUCH_INT", "actions": [_hw_action(method="   ")]}]}
    errors = validate_trigger_assignments(fda, toolkit)
    assert any("MPR121" in e for e in errors)


def test_non_string_method_errors():
    toolkit = make_toolkit()
    action = {"type": "hardware", "ref": "MPR121", "method": 42}
    fda = {"trigger_assignments": [{"trigger_name": "TOUCH_INT", "actions": [action]}]}
    errors = validate_trigger_assignments(fda, toolkit)
    assert any("MPR121" in e for e in errors)


def test_timer_action_empty_method_errors():
    toolkit = make_toolkit()
    fda = {
        "trigger_assignments": [
            {"trigger_name": "TOUCH_INT", "actions": [_hw_action(action_type="timer", method="")]}
        ]
    }
    errors = validate_trigger_assignments(fda, toolkit)
    assert any("MPR121" in e for e in errors)


def test_known_good_hardware_action_passes():
    toolkit = make_toolkit()
    fda = {"trigger_assignments": [{"trigger_name": "TOUCH_INT", "actions": [_hw_action()]}]}
    assert validate_trigger_assignments(fda, toolkit) == []


def test_state_entry_action_empty_method_errors_naming_state_and_index():
    toolkit = make_toolkit()
    fda = {"states": {"reward": {"entry_actions": [_hw_action(method="")]}}}
    errors = validate_state_actions(fda, toolkit)
    assert any("reward" in e and "action[0]" in e and "MPR121" in e for e in errors)


def test_state_entry_actions_supports_both_dict_and_list_states_shapes():
    toolkit = make_toolkit()
    dict_fda = {"states": {"idle": {"entry_actions": []}, "reward": {"entry_actions": [_hw_action(method="")]}}}
    list_fda = {"states": [{"name": "idle", "entry_actions": []}, {"name": "reward", "entry_actions": [_hw_action(method="")]}]}
    assert any("reward" in e for e in validate_state_actions(dict_fda, toolkit))
    assert any("reward" in e for e in validate_state_actions(list_fda, toolkit))


def test_state_entry_action_good_method_passes():
    toolkit = make_toolkit()
    fda = {"states": {"reward": {"entry_actions": [_hw_action()]}}}
    assert validate_state_actions(fda, toolkit) == []


def test_state_entry_action_unrelated_flag_ref_stays_soft_not_hard():
    """method_only scoping: a broken flag ref in a state body must NOT hard-422 here — that
    stays with the soft drift-badge path (_validate_task_definition)."""
    toolkit = make_toolkit()
    fda = {"states": {"reward": {"entry_actions": [{"type": "flag", "ref": "ghost_flag"}]}}}
    assert validate_state_actions(fda, toolkit) == []


def test_unknown_method_accepted_when_class_open():
    toolkit = make_toolkit()
    module_methods = {"MPR121": ({"detect_change", "read"}, False)}  # closed=False: imported base
    fda = {
        "trigger_assignments": [
            {"trigger_name": "TOUCH_INT", "actions": [_hw_action(method="mystery_method")]}
        ]
    }
    assert validate_trigger_assignments(fda, toolkit, module_methods=module_methods) == []


def test_unknown_method_rejected_when_class_closed():
    toolkit = make_toolkit()
    module_methods = {"MPR121": ({"detect_change", "read"}, True)}  # closed=True: no external base
    fda = {
        "trigger_assignments": [
            {"trigger_name": "TOUCH_INT", "actions": [_hw_action(method="mystery_method")]}
        ]
    }
    errors = validate_trigger_assignments(fda, toolkit, module_methods=module_methods)
    assert any("mystery_method" in e for e in errors)


# ---------------------------------------------------------------------------
# {device_name} runtime token + source_ref (TRIGA-17/18, Plan 08 Task 2)
# ---------------------------------------------------------------------------

def test_device_name_token_with_source_ref_and_declared_variable_is_ok():
    toolkit = make_toolkit(semantic_hardware={"MPR121": ["I2C", "MPR121"]})
    fda = {
        "variables": {"pin_number": {}},
        "trigger_assignments": [
            {
                "trigger_name": "TOUCH_INT",
                "actions": [
                    {"type": "view", "key_template": "{device_name}{pin_number}", "source_ref": "MPR121", "value": 1},
                ],
            }
        ],
    }
    assert validate_trigger_assignments(fda, toolkit) == []


def test_device_name_token_without_source_ref_errors_naming_device_name():
    toolkit = make_toolkit()
    fda = {
        "variables": {"pin_number": {}},
        "trigger_assignments": [
            {
                "trigger_name": "TOUCH_INT",
                "actions": [{"type": "view", "key_template": "{device_name}{pin_number}", "value": 1}],
            }
        ],
    }
    errors = validate_trigger_assignments(fda, toolkit)
    assert any("device_name" in e for e in errors)


def test_source_ref_naming_unknown_hardware_errors():
    toolkit = make_toolkit(semantic_hardware={"MPR121": ["I2C", "MPR121"]})
    fda = {
        "variables": {"pin_number": {}},
        "trigger_assignments": [
            {
                "trigger_name": "TOUCH_INT",
                "actions": [
                    {
                        "type": "view", "key_template": "{device_name}{pin_number}",
                        "source_ref": "GHOST_DEVICE", "value": 1,
                    },
                ],
            }
        ],
    }
    errors = validate_trigger_assignments(fda, toolkit)
    assert any("GHOST_DEVICE" in e for e in errors)


def test_canonical_payload_with_device_name_token_validates_clean():
    toolkit = make_toolkit(semantic_hardware={"MPR121": ["I2C", "MPR121"]})
    assert collect_hard_errors(CANONICAL_PAYLOAD, toolkit) == []


# ---------------------------------------------------------------------------
# Task 3 (Plan 08) — route-level: method-less hardware action returns 422
# ---------------------------------------------------------------------------

def test_put_method_less_hardware_action_returns_422_not_200_broken(client):
    defn = make_defn_mock()
    toolkit = make_toolkit(semantic_hardware={"MPR121": ["I2C", "MPR121"]})
    mock_db = make_db_mock(defn=defn, toolkit=toolkit)
    payload = {
        "fda_json": {
            "states": {},
            "trigger_assignments": [
                {"trigger_name": "TOUCH_INT", "actions": [{"type": "hardware", "ref": "MPR121", "method": ""}]}
            ],
        }
    }
    with patch("routers.toolkits._SA_SessionLocal") as mock_factory:
        mock_factory.return_value = mock_db
        resp = client.put("/api/task-definitions/1", json=payload, headers=auth_headers())

    assert resp.status_code == 422
    assert any("MPR121" in e for e in resp.json()["detail"]["errors"])
