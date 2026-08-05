"""Contract tests for CANVAS-05/06: task_definitions.ui_layout.

Layout lives in a column deliberately separate from `fda_json` (`29-CONTEXT.md` locked decision
1) so a canvas node drag never rewrites `file_hash` (content-hashed, shipped to the Pi) and never
triggers FDA re-validation (CANVAS-10). These tests prove both directions against the real DB:
a layout-only PUT must leave `file_hash`/`validation_status` untouched and must survive an FDA
that would otherwise fail validation; an `fda_json` PUT must still rehash.
"""
import json
from unittest.mock import patch

from fastapi.testclient import TestClient
import pytest


@pytest.fixture(autouse=True)
def _clear_dependency_overrides():
    yield
    from main import app
    app.dependency_overrides.clear()


def _client():
    from auth import verify_token
    from main import app
    app.dependency_overrides[verify_token] = lambda: {"sub": "test"}
    return TestClient(app)


def auth_headers():
    return {"Authorization": "Bearer test-token"}


MINIMAL_FDA = {"states": {"IDLE": {"transitions": []}}, "start_state": "IDLE"}
CHANGED_FDA = {"states": {"IDLE": {"transitions": []}, "DONE": {"transitions": []}}, "start_state": "IDLE"}


@pytest.fixture
def task_def():
    """POST a minimal, toolkit-less task definition (no hard-error surface); delete on teardown."""
    resp = _client().post(
        "/api/task-definitions",
        json={"display_name": "_ui_layout_probe", "toolkit_name": "_probe_toolkit", "fda_json": MINIMAL_FDA},
        headers=auth_headers(),
    )
    assert resp.status_code == 201, resp.text
    body = resp.json()
    yield body
    _client().delete(f"/api/task-definitions/{body['id']}", headers=auth_headers())


def _get(defn_id):
    resp = _client().get(f"/api/task-definitions/{defn_id}", headers=auth_headers())
    assert resp.status_code == 200, resp.text
    return resp.json()


def test_layout_only_put_round_trips_deep_equal(task_def):
    layout = {"nodes": {"CUE": {"x": 10, "y": 20}}}
    resp = _client().put(
        f"/api/task-definitions/{task_def['id']}", json={"ui_layout": layout}, headers=auth_headers(),
    )
    assert resp.status_code == 200, resp.text

    got = _get(task_def["id"])
    assert got["ui_layout"] == layout


def test_layout_only_put_leaves_file_hash_byte_identical(task_def):
    before = _get(task_def["id"])["file_hash"]
    resp = _client().put(
        f"/api/task-definitions/{task_def['id']}",
        json={"ui_layout": {"nodes": {"CUE": {"x": 1, "y": 2}}}},
        headers=auth_headers(),
    )
    assert resp.status_code == 200, resp.text
    after = _get(task_def["id"])["file_hash"]
    assert after == before


def test_fda_json_put_changes_file_hash(task_def):
    before = _get(task_def["id"])["file_hash"]
    resp = _client().put(
        f"/api/task-definitions/{task_def['id']}", json={"fda_json": CHANGED_FDA}, headers=auth_headers(),
    )
    assert resp.status_code == 200, resp.text
    after = _get(task_def["id"])["file_hash"]
    assert after != before


def test_layout_only_put_does_not_change_validation_status_or_message(task_def):
    before = _get(task_def["id"])
    resp = _client().put(
        f"/api/task-definitions/{task_def['id']}",
        json={"ui_layout": {"nodes": {"CUE": {"x": 3, "y": 4}}}},
        headers=auth_headers(),
    )
    assert resp.status_code == 200, resp.text
    after = _get(task_def["id"])
    assert after["validation_status"] == before["validation_status"]
    assert after["validation_message"] == before["validation_message"]


def test_layout_only_put_survives_fda_that_would_fail_validation(task_def):
    """CANVAS-10: a node drag must never be rejected because of unrelated FDA state."""
    with patch("routers.toolkits.reject_if_hard_errors", side_effect=Exception("would 422 on an FDA edit")):
        resp = _client().put(
            f"/api/task-definitions/{task_def['id']}",
            json={"ui_layout": {"nodes": {"CUE": {"x": 5, "y": 6}}}},
            headers=auth_headers(),
        )
    assert resp.status_code == 200, resp.text


def test_put_with_both_fda_json_and_ui_layout_writes_both_and_rehashes(task_def):
    before = _get(task_def["id"])["file_hash"]
    layout = {"nodes": {"CUE": {"x": 7, "y": 8}}}
    resp = _client().put(
        f"/api/task-definitions/{task_def['id']}",
        json={"fda_json": CHANGED_FDA, "ui_layout": layout},
        headers=auth_headers(),
    )
    assert resp.status_code == 200, resp.text

    got = _get(task_def["id"])
    assert got["file_hash"] != before
    assert got["ui_layout"] == layout
    assert got["fda_json"] == CHANGED_FDA


def test_get_on_definition_never_arranged_returns_ui_layout_none(task_def):
    got = _get(task_def["id"])
    assert got["ui_layout"] is None
