"""Contract tests for the CMP-12 `kind` column + CMP-19 declared-imports allowlist.

Landed by plan 23-02: `db.run_hardware_lib_kind_migration`, `HardwareLib.kind` /
`HardwareLibVersion.declared_imports`, `seed_compute.seed_compute_ops_lib` /
`seed_compute.COMPUTE_STDLIB_ALLOWLIST`, and the `kind='compute'` / `declared_imports=[...]`
branches of `POST /api/hardware-libs`. Every skip/importorskip/xfail from the Wave-0 (plan 23-01)
version of this file is gone -- every assertion below is a real pass.
"""
import json
from unittest.mock import patch

from fastapi.testclient import TestClient
import pytest


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
    from db import run_hardware_lib_kind_migration, engine
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
    from db import run_hardware_lib_kind_migration, engine
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
    import pytest
    import seed_compute
    from db import engine
    from sqlalchemy import text

    # The live api service seeds this exact row at boot, against this same DB -- clear it
    # first so "first call creates" is provable rather than an artifact of container startup.
    with engine.begin() as conn:
        lib_id = conn.execute(text(
            "SELECT id FROM hardware_libs WHERE filename = 'compute_ops.py'"
        )).scalar()
        # Every toolkit now links the compute lib, so on a dev DB this teardown would delete
        # a lib/module real toolkits point at -- re-seeding mints NEW ids and silently leaves
        # their toolkit_hardware_libs + hardware_module_ids dangling. The FK on
        # default_version_id catches it today; that is luck, not protection. Only run the
        # destructive path on a DB where nothing depends on the lib (fresh DB / CI).
        if lib_id:
            referencing = conn.execute(text(
                "SELECT COUNT(*) FROM toolkit_hardware_libs WHERE hardware_lib_id = :id"
            ), {"id": lib_id}).scalar()
            if referencing:
                pytest.skip(
                    f"compute lib {lib_id} is linked by {referencing} toolkit(s) — refusing to "
                    "delete real wiring; run on a fresh DB to prove first-call-creates"
                )
        if lib_id:
            conn.execute(text("DELETE FROM hardware_modules WHERE hardware_lib_id = :id"), {"id": lib_id})
            conn.execute(text(
                "UPDATE hardware_libs SET active_version_id = NULL, stable_version_id = NULL WHERE id = :id"
            ), {"id": lib_id})
            conn.execute(text("DELETE FROM hardware_lib_versions WHERE hardware_lib_id = :id"), {"id": lib_id})
            conn.execute(text("DELETE FROM hardware_libs WHERE id = :id"), {"id": lib_id})

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
    import seed_compute

    assert "random" in seed_compute.COMPUTE_STDLIB_ALLOWLIST
    assert "math" in seed_compute.COMPUTE_STDLIB_ALLOWLIST
    assert "numpy" not in seed_compute.COMPUTE_STDLIB_ALLOWLIST


# ---------------------------------------------------------------------------
# CMP-12/19 route contract: POST /api/hardware-libs kind= / declared_imports=
# ---------------------------------------------------------------------------

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


def test_upload_lib_kind_banana_is_422():
    with patch("routers.hardware_libs._SA_SessionLocal"):
        resp = _client().post(
            "/api/hardware-libs",
            data={"name": "banana_probe", "kind": "banana"},
            files={"file": ("banana_probe.py", COMPUTE_SOURCE_WITH_RELEASE, "text/x-python")},
            headers=auth_headers(),
        )
    assert resp.status_code == 422


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


# ---------------------------------------------------------------------------
# CMP-04/19: seed compute lib source behaviour -- exec'd with stubbed autopilot modules
# ---------------------------------------------------------------------------

def _load_seed_ops_class():
    """Exec the seed source with stub `autopilot.hardware`/`autopilot.utils.logging_utils`
    modules injected into sys.modules, so the seed ops are testable even though `autopilot`
    is unimportable on this host. Returns the exec'd `ComputeOps` class."""
    import sys
    import types
    from pathlib import Path

    class _StubHardware:
        def release(self):
            raise Exception("The release method was not overridden by the subclass!")

    autopilot_mod = types.ModuleType("autopilot")
    autopilot_hardware_mod = types.ModuleType("autopilot.hardware")
    autopilot_hardware_mod.Hardware = _StubHardware
    autopilot_utils_mod = types.ModuleType("autopilot.utils")
    autopilot_logging_mod = types.ModuleType("autopilot.utils.logging_utils")
    autopilot_logging_mod.log_action = lambda f: f

    saved = {
        k: sys.modules.get(k)
        for k in ("autopilot", "autopilot.hardware", "autopilot.utils", "autopilot.utils.logging_utils")
    }
    sys.modules["autopilot"] = autopilot_mod
    sys.modules["autopilot.hardware"] = autopilot_hardware_mod
    sys.modules["autopilot.utils"] = autopilot_utils_mod
    sys.modules["autopilot.utils.logging_utils"] = autopilot_logging_mod
    try:
        source = (Path(__file__).parent.parent / "seed_libs" / "compute_ops.py").read_text()
        namespace: dict = {}
        exec(compile(source, "compute_ops.py", "exec"), namespace)
        return namespace["ComputeOps"]
    finally:
        for k, v in saved.items():
            if v is None:
                sys.modules.pop(k, None)
            else:
                sys.modules[k] = v


def test_seed_ops_class_defines_release_and_exactly_thirteen_public_ops():
    cls = _load_seed_ops_class()
    ops = cls()
    ops.release()  # must not raise

    public_methods = {
        name for name in vars(cls)
        if not name.startswith("_") and callable(getattr(cls, name)) and name != "release"
    }
    assert public_methods == {
        "random_choice", "random_int", "random_float", "random_bool", "assign",
        "add", "subtract", "multiply", "divide", "modulo", "minimum", "maximum", "clamp",
    }
    # No comparison/boolean-logic ops -- branching stays in FDA transitions (CONTEXT, locked).
    assert not any(name.startswith(("eq", "compare", "and_", "or_", "not_")) for name in public_methods)


def test_seed_ops_numeric_and_random_behaviour():
    cls = _load_seed_ops_class()
    ops = cls()

    assert ops.add(2, 3) == 5
    assert ops.subtract(5, 3) == 2
    assert ops.multiply(2, 3) == 6
    with pytest.raises(ZeroDivisionError):
        ops.divide(1, 0)
    with pytest.raises(ZeroDivisionError):
        ops.modulo(1, 0)
    assert ops.divide(6, 3) == 2
    assert ops.modulo(7, 3) == 1
    assert ops.clamp(5, 0, 3) == 3
    assert ops.clamp(-1, 0, 3) == 0
    assert ops.minimum(2, 5) == 2
    assert ops.maximum(2, 5) == 5
    x = object()
    assert ops.assign(x) is x
    assert ops.random_bool(1.0) is True
    assert ops.random_bool(0.0) is False
    assert ops.random_int(3, 3) == 3
    assert ops.random_choice(["a"]) == "a"
    assert ops.random_float(1.0, 1.0) == 1.0


# ---------------------------------------------------------------------------
# CMP-04/12: compute_provisioning -- auto-provision the per-pilot config row a compute
# module needs before it will instantiate on the Pi. Mocked db.execute, dispatching on a
# distinguishing substring of the table name (style matches test_toolkit_dispatch.py's _db_stub).
# ---------------------------------------------------------------------------

class _Rows:
    def __init__(self, rows):
        self._rows = rows

    def fetchall(self):
        return self._rows


def _provisioning_db(*, module_rows=None, pilot_rows=None, existing_rows=None, inserted=None):
    from unittest.mock import MagicMock
    from types import SimpleNamespace

    module_rows = module_rows or []
    pilot_rows = pilot_rows or []
    existing_rows = existing_rows or []
    inserted = inserted if inserted is not None else []

    def _execute(query, params=None):
        sql = " ".join(str(query).split())
        if sql.startswith("SELECT hm.name, hm.class_name"):
            return _Rows(module_rows)
        if sql.startswith("SELECT id FROM pilots"):
            return _Rows(pilot_rows)
        if sql.startswith("SELECT pilot_id, name FROM pilot_hardware_config"):
            return _Rows(existing_rows)
        if sql.startswith("INSERT INTO pilot_hardware_config"):
            inserted.append((params["pilot_id"], params["name"], params["config"]))
            return _Rows([])
        return _Rows([])

    db = MagicMock()
    db.execute.side_effect = _execute
    return db, inserted


def test_compute_module_names_returns_only_compute_kind_modules():
    from compute_provisioning import compute_module_names
    from types import SimpleNamespace

    db, _ = _provisioning_db(module_rows=[SimpleNamespace(name="COMPUTE", class_name="ComputeOps")])
    assert compute_module_names(db, [10]) == {"COMPUTE": "ComputeOps"}


def test_compute_module_names_empty_when_no_module_ids():
    from compute_provisioning import compute_module_names

    db, _ = _provisioning_db()
    assert compute_module_names(db, []) == {}


def test_provision_compute_configs_creates_row_per_pilot():
    from compute_provisioning import provision_compute_configs
    from types import SimpleNamespace

    db, inserted = _provisioning_db(
        module_rows=[SimpleNamespace(name="COMPUTE", class_name="ComputeOps")],
        pilot_rows=[SimpleNamespace(id=1), SimpleNamespace(id=2)],
        existing_rows=[],
    )
    created = provision_compute_configs(db, [10])
    assert set(created) == {(1, "COMPUTE"), (2, "COMPUTE")}
    assert len(inserted) == 2
    assert json.loads(inserted[0][2]) == {"class_name": "ComputeOps"}


def test_provision_compute_configs_skips_existing_row_even_with_extra_keys():
    from compute_provisioning import provision_compute_configs
    from types import SimpleNamespace

    db, inserted = _provisioning_db(
        module_rows=[SimpleNamespace(name="COMPUTE", class_name="ComputeOps")],
        pilot_rows=[SimpleNamespace(id=1), SimpleNamespace(id=2)],
        existing_rows=[SimpleNamespace(pilot_id=1, name="COMPUTE")],
    )
    created = provision_compute_configs(db, [10])
    assert created == [(2, "COMPUTE")]
    assert len(inserted) == 1


def test_provision_compute_configs_called_twice_second_call_creates_nothing():
    from compute_provisioning import provision_compute_configs
    from types import SimpleNamespace

    module_rows = [SimpleNamespace(name="COMPUTE", class_name="ComputeOps")]
    pilot_rows = [SimpleNamespace(id=1)]

    db1, inserted1 = _provisioning_db(module_rows=module_rows, pilot_rows=pilot_rows, existing_rows=[])
    first = provision_compute_configs(db1, [10])
    assert first == [(1, "COMPUTE")]

    # Second call sees the row the first call "created" as already-existing.
    db2, inserted2 = _provisioning_db(
        module_rows=module_rows, pilot_rows=pilot_rows,
        existing_rows=[SimpleNamespace(pilot_id=1, name="COMPUTE")],
    )
    second = provision_compute_configs(db2, [10])
    assert second == []
    assert inserted2 == []


def test_provision_compute_configs_never_provisions_hardware_kind_module():
    from compute_provisioning import provision_compute_configs

    # module_rows empty -- the SQL join filters on hl.kind = 'compute', so a hardware-kind
    # module id never surfaces from compute_module_names in the first place.
    db, inserted = _provisioning_db(module_rows=[], pilot_rows=[])
    created = provision_compute_configs(db, [99])
    assert created == []
    assert inserted == []


# ---------------------------------------------------------------------------
# Every toolkit ships with the compute lib (user decision, 2026-08-03): linking is
# not a per-toolkit opt-in. `attach_compute_defaults` is the single seam both
# creation sites call -- POST /toolkits (backend-authored) and the HANDSHAKE upsert.
# Reachability needs BOTH halves (compute_provisioning docstring): the
# toolkit_hardware_libs row (version pinning + LOAD_HARDWARE_LIBS) AND the module id
# in hardware_module_ids (Pi reachability as self.hardware["Modules"][ref]).
# ---------------------------------------------------------------------------

def _attach_db(*, lib_rows=None, module_rows=None, existing_links=None, hmids=None, calls=None):
    from unittest.mock import MagicMock
    from types import SimpleNamespace

    lib_rows = lib_rows or []
    module_rows = module_rows or []
    existing_links = existing_links or []
    calls = calls if calls is not None else []
    state = {"hmids": hmids if hmids is not None else []}

    def _execute(query, params=None):
        sql = " ".join(str(query).split())
        if sql.startswith("SELECT id FROM hardware_libs WHERE kind = 'compute'"):
            return _Rows(lib_rows)
        if sql.startswith("SELECT hm.id FROM hardware_modules hm"):
            return _Rows(module_rows)
        if sql.startswith("SELECT hardware_lib_id FROM toolkit_hardware_libs"):
            return _Rows(existing_links)
        if sql.startswith("SELECT hardware_module_ids FROM task_toolkits"):
            return _Rows([SimpleNamespace(hardware_module_ids=state["hmids"])])
        if sql.startswith("INSERT INTO toolkit_hardware_libs"):
            calls.append(("link", params["toolkit_id"], params["hardware_lib_id"]))
            return _Rows([])
        if sql.startswith("UPDATE task_toolkits SET hardware_module_ids"):
            calls.append(("hmids", params["id"], params["hmids"]))
            return _Rows([])
        return _Rows([])

    db = MagicMock()
    db.execute.side_effect = _execute
    return db, calls


def test_attach_compute_defaults_links_lib_and_adds_module_id():
    from compute_provisioning import attach_compute_defaults
    from types import SimpleNamespace
    import json

    db, calls = _attach_db(
        lib_rows=[SimpleNamespace(id=45)],
        module_rows=[SimpleNamespace(id=24)],
        hmids=[1, 5],
    )
    attach_compute_defaults(db, toolkit_id=100)

    assert ("link", 100, 45) in calls
    hmids_call = [c for c in calls if c[0] == "hmids"]
    assert hmids_call, "compute module id must be added to hardware_module_ids"
    assert sorted(json.loads(hmids_call[0][2])) == [1, 5, 24]


def test_attach_compute_defaults_is_idempotent():
    """Re-running must not duplicate the link row or re-add the module id."""
    from compute_provisioning import attach_compute_defaults
    from types import SimpleNamespace

    db, calls = _attach_db(
        lib_rows=[SimpleNamespace(id=45)],
        module_rows=[SimpleNamespace(id=24)],
        existing_links=[SimpleNamespace(hardware_lib_id=45)],
        hmids=[1, 5, 24],
    )
    attach_compute_defaults(db, toolkit_id=100)

    assert not [c for c in calls if c[0] == "link"]
    assert not [c for c in calls if c[0] == "hmids"]


def test_attach_compute_defaults_noop_without_compute_lib():
    """A fresh DB that has not seeded Compute Ops yet must not crash toolkit creation."""
    from compute_provisioning import attach_compute_defaults

    db, calls = _attach_db(lib_rows=[], module_rows=[])
    attach_compute_defaults(db, toolkit_id=100)
    assert calls == []
