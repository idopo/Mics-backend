"""Regression coverage for `_flag_broken_task_defs`' action_type filter (Plan 23-03 Task 1).

CMP-11 widened `fda_utils.scan_fda_for_refs` to also emit "compute" entries. This function has
its own, second, action_type filter (it does not consume the scanner's full output verbatim) —
without widening it too, a compute-op rename/removal would scan-see the reference but never flag
the dependent task definition, silently defeating the truth this plan pins: "Renaming or removing
a compute op flags every task definition that used it."
"""
from types import SimpleNamespace
from unittest.mock import MagicMock

from models import TaskDefinition, ToolkitHardwareLib
from routers.hardware_libs import _flag_broken_task_defs


def _mock_db(fda_by_task_def_id: dict[int, dict]):
    mock_db = MagicMock()
    toolkit_link = SimpleNamespace(toolkit_id=5)
    task_defs = [SimpleNamespace(id=i, toolkit_id=5) for i in fda_by_task_def_id]

    def _query(model):
        q = MagicMock()
        if model is ToolkitHardwareLib:
            q.filter.return_value.all.return_value = [toolkit_link]
        elif model is TaskDefinition:
            q.filter.return_value.all.return_value = task_defs
        else:
            q.filter.return_value.all.return_value = []
        return q

    def _execute(query, params=None):
        sql = " ".join(str(query).split())
        result = MagicMock()
        if "SELECT fda_json FROM task_definitions" in sql:
            fda = fda_by_task_def_id.get(params["id"])
            result.fetchone.return_value = SimpleNamespace(fda_json=fda) if fda is not None else None
        return result

    mock_db.query.side_effect = _query
    mock_db.execute.side_effect = _execute
    return mock_db


def test_hardware_op_removal_flags_dependent_task_def_regression():
    fda = {
        "trigger_assignments": [
            {"trigger_name": "TOUCH_INT", "actions": [{"type": "hardware", "ref": "MPR121", "method": "gone"}]}
        ]
    }
    db = _mock_db({1: fda})
    affected = _flag_broken_task_defs(db, lib_id=9, removed_methods={"Touch_Detector": {"gone"}})
    assert affected == [1]


def test_compute_op_removal_flags_dependent_task_def():
    fda = {
        "states": {
            "roll": {"entry_actions": [{"type": "compute", "ref": "COMPUTE", "method": "gone", "output": "x"}]}
        }
    }
    db = _mock_db({1: fda})
    affected = _flag_broken_task_defs(db, lib_id=9, removed_methods={"ComputeOps": {"gone"}})
    assert affected == [1]


def test_compute_op_still_present_does_not_flag():
    fda = {
        "states": {
            "roll": {"entry_actions": [{"type": "compute", "ref": "COMPUTE", "method": "still_here", "output": "x"}]}
        }
    }
    db = _mock_db({1: fda})
    affected = _flag_broken_task_defs(db, lib_id=9, removed_methods={"ComputeOps": {"gone"}})
    assert affected == []
