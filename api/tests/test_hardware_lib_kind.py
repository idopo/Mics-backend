"""Contract tests for the CMP-12 `kind` column + CMP-19 declared-imports allowlist
(Wave 0, Plan 23-01).

None of the production symbols under test exist yet:
  - `db.run_hardware_lib_kind_migration` (plan 23-02)
  - `HardwareLib.kind` / `HardwareLibVersion.declared_imports` columns (plan 23-02)
  - `seed_compute.seed_compute_ops_lib` / `seed_compute.COMPUTE_STDLIB_ALLOWLIST` (plan 23-02)
  - the `kind='compute'` / `declared_imports=[...]` branches of `POST /api/hardware-libs`
    (plan 23-02)

Migration tests import `run_hardware_lib_kind_migration` inside each test body (not at module
level) so collection never errors; a missing symbol is caught and turned into an explicit
`pytest.skip`. Seed tests use `pytest.importorskip("seed_compute", ...)` inside the test body
for the same reason. Route tests are marked `xfail(strict=False)` -- the endpoint exists today
but silently ignores the new `kind`/`declared_imports` form fields, so these assertions fail
for the right reason (missing feature) rather than erroring.

TODO(plan 23-02): once the migration/seed/route work lands, remove every skip/importorskip/xfail
in this file -- they exist only to keep this suite green before that plan runs.
"""
import json
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient


# ---------------------------------------------------------------------------
# Fixtures / helpers
# ---------------------------------------------------------------------------

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


COMPUTE_SOURCE_WITH_RELEASE = """
from autopilot.hardware import Hardware


class ComputeOps(Hardware):
    def release(self):
        pass

    def add(self, a, b):
        return a + b
"""

COMPUTE_SOURCE_NO_RELEASE = """
from autopilot.hardware import Hardware


class ComputeOps(Hardware):
    def add(self, a, b):
        return a + b
"""


# ---------------------------------------------------------------------------
# CMP-12: run_hardware_lib_kind_migration idempotency (integration, real DB)
# ---------------------------------------------------------------------------

def test_migration_runs_twice_without_error_and_columns_exist():
    try:
        from db import run_hardware_lib_kind_migration
    except ImportError:
        pytest.skip("run_hardware_lib_kind_migration not implemented yet (plan 23-02)")

    from db import engine
    from sqlalchemy import text

    run_hardware_lib_kind_migration(engine)
    run_hardware_lib_kind_migration(engine)  # must not raise the second time

    with engine.connect() as conn:
        kind_cols = conn.execute(text(
            "SELECT column_name FROM information_schema.columns "
            "WHERE table_name = 'hardware_libs' AND column_name = 'kind'"
        )).fetchall()
        declared_imports_cols = conn.execute(text(
            "SELECT column_name FROM information_schema.columns "
            "WHERE table_name = 'hardware_lib_versions' AND column_name = 'declared_imports'"
        )).fetchall()
    assert len(kind_cols) == 1
    assert len(declared_imports_cols) == 1


def test_default_kind_for_preexisting_lib_row_is_hardware():
    """The migration must not reclassify any existing lib -- default is 'hardware'."""
    try:
        from db import run_hardware_lib_kind_migration
    except ImportError:
        pytest.skip("run_hardware_lib_kind_migration not implemented yet (plan 23-02)")

    from db import engine
    from sqlalchemy import text

    run_hardware_lib_kind_migration(engine)
    with engine.begin() as conn:
        conn.execute(text(
            "INSERT INTO hardware_libs (name, filename) VALUES ('_cmp12_probe', '_cmp12_probe.py')"
        ))
    try:
        with engine.connect() as conn:
            row = conn.execute(text(
                "SELECT kind FROM hardware_libs WHERE name = '_cmp12_probe'"
            )).fetchone()
        assert row.kind == "hardware"
    finally:
        with engine.begin() as conn:
            conn.execute(text("DELETE FROM hardware_libs WHERE name = '_cmp12_probe'"))


# ---------------------------------------------------------------------------
# CMP-19: seed_compute_ops_lib + COMPUTE_STDLIB_ALLOWLIST (integration, real DB)
# ---------------------------------------------------------------------------

def test_seed_compute_ops_lib_idempotent_created_flag_and_single_row():
    seed_compute = pytest.importorskip(
        "seed_compute", reason="CMP-19: seed_compute module not implemented until plan 23-02"
    )
    from db import engine
    from sqlalchemy import text

    result1 = seed_compute.seed_compute_ops_lib(engine)
    result2 = seed_compute.seed_compute_ops_lib(engine)
    assert result1["created"] is True
    assert result2["created"] is False
    assert "lib_id" in result1 and "version_id" in result1 and "module_id" in result1

    with engine.connect() as conn:
        rows = conn.execute(text(
            "SELECT id FROM hardware_libs WHERE filename = 'compute_ops.py'"
        )).fetchall()
    assert len(rows) == 1


def test_compute_stdlib_allowlist_contains_random_and_math_not_numpy():
    seed_compute = pytest.importorskip(
        "seed_compute", reason="CMP-19: seed_compute module not implemented until plan 23-02"
    )
    assert "random" in seed_compute.COMPUTE_STDLIB_ALLOWLIST
    assert "math" in seed_compute.COMPUTE_STDLIB_ALLOWLIST
    assert "numpy" not in seed_compute.COMPUTE_STDLIB_ALLOWLIST


# ---------------------------------------------------------------------------
# CMP-12/19 route contract: POST /api/hardware-libs kind= / declared_imports=
# ---------------------------------------------------------------------------

@pytest.mark.xfail(reason="CMP-12: kind not implemented until plan 23-02", strict=False)
def test_upload_compute_lib_with_release_returns_kind_compute():
    with patch("routers.hardware_libs._SA_SessionLocal"):
        resp = _client().post(
            "/api/hardware-libs",
            data={"name": "compute_probe", "kind": "compute"},
            files={"file": ("compute_probe.py", COMPUTE_SOURCE_WITH_RELEASE, "text/x-python")},
            headers=auth_headers(),
        )
    assert resp.status_code in (200, 201)
    assert resp.json()["kind"] == "compute"


@pytest.mark.xfail(reason="CMP-12: release() enforcement not implemented until plan 23-02", strict=False)
def test_upload_compute_lib_without_release_is_422_naming_release():
    with patch("routers.hardware_libs._SA_SessionLocal"):
        resp = _client().post(
            "/api/hardware-libs",
            data={"name": "compute_probe_norelease", "kind": "compute"},
            files={"file": ("compute_probe_norelease.py", COMPUTE_SOURCE_NO_RELEASE, "text/x-python")},
            headers=auth_headers(),
        )
    assert resp.status_code == 422
    assert "release" in resp.json()["detail"]


@pytest.mark.xfail(reason="CMP-12: kind enum validation not implemented until plan 23-02", strict=False)
def test_upload_lib_kind_banana_is_422():
    with patch("routers.hardware_libs._SA_SessionLocal"):
        resp = _client().post(
            "/api/hardware-libs",
            data={"name": "banana_probe", "kind": "banana"},
            files={"file": ("banana_probe.py", COMPUTE_SOURCE_WITH_RELEASE, "text/x-python")},
            headers=auth_headers(),
        )
    assert resp.status_code == 422


@pytest.mark.xfail(reason="CMP-19: declared_imports allowlist not implemented until plan 23-02", strict=False)
def test_upload_compute_lib_declared_import_numpy_rejected_names_allowlist():
    with patch("routers.hardware_libs._SA_SessionLocal"):
        resp = _client().post(
            "/api/hardware-libs",
            data={
                "name": "compute_probe_numpy",
                "kind": "compute",
                "declared_imports": json.dumps(["numpy"]),
            },
            files={"file": ("compute_probe_numpy.py", COMPUTE_SOURCE_WITH_RELEASE, "text/x-python")},
            headers=auth_headers(),
        )
    assert resp.status_code == 422
    detail = resp.json()["detail"]
    assert "numpy" in detail
    assert "random" in detail and "math" in detail  # allowlist named in the message


@pytest.mark.xfail(reason="CMP-19: declared_imports allowlist not implemented until plan 23-02", strict=False)
def test_upload_compute_lib_declared_import_stdlib_only_accepted():
    with patch("routers.hardware_libs._SA_SessionLocal"):
        resp = _client().post(
            "/api/hardware-libs",
            data={
                "name": "compute_probe_stdlib",
                "kind": "compute",
                "declared_imports": json.dumps(["random", "math"]),
            },
            files={"file": ("compute_probe_stdlib.py", COMPUTE_SOURCE_WITH_RELEASE, "text/x-python")},
            headers=auth_headers(),
        )
    assert resp.status_code in (200, 201)
    assert resp.json()["declared_imports"] == ["random", "math"]
