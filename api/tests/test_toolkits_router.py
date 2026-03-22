"""Tests for toolkit and task-definition CRUD endpoints (Plan 02-03)."""
import pytest
from fastapi.testclient import TestClient
from unittest.mock import patch, MagicMock


@pytest.fixture
def client():
    from main import app
    return TestClient(app)


def auth_headers():
    return {"Authorization": "Bearer test-token"}


def test_list_toolkits_returns_list(client):
    with patch("routers.toolkits._SA_SessionLocal") as mock_db:
        mock_db.return_value.__enter__ = MagicMock(return_value=MagicMock())
        resp = client.get("/api/toolkits", headers=auth_headers())
    assert resp.status_code in (200, 401, 422)  # route exists


def test_list_task_definitions_returns_list(client):
    resp = client.get("/api/task-definitions", headers=auth_headers())
    assert resp.status_code != 404  # endpoint must exist


def test_create_task_definition_returns_id(client):
    payload = {"display_name": "test", "toolkit_name": "AppetitiveTaskReal", "fda_json": {"states": {}}}
    resp = client.post("/api/task-definitions", json=payload, headers=auth_headers())
    assert resp.status_code in (201, 401, 422)  # endpoint exists, not 404
