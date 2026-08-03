"""Contract tests for the CMP-17 hardware-lib version-resolution chain (Wave 0, Plan 23-01).

`api/lib_version_resolution.py` does not exist yet -- built by plan 23-05, which also rewires
`get_dispatch_spec` (api/routers/toolkit_dispatch.py) and `list_toolkit_hardware_libs`
(api/routers/hardware_libs.py) to call it. The whole module is guarded by
`pytest.importorskip("lib_version_resolution")` below; the two route-level regression tests
carry their own `xfail` marker as a second layer, since the routes and the resolver are built
by the same plan but not necessarily in the same commit.

TODO(plan 23-05): remove the module-level importorskip once `api/lib_version_resolution.py`
lands, and remove the two `xfail` markers once `get_dispatch_spec`/`list_toolkit_hardware_libs`
are rewired onto the chain (stable-over-active ordering; resolved_version_id/resolved_state/
resolution_reason on the toolkit hardware-libs list).
"""
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient

lib_version_resolution = pytest.importorskip(
    "lib_version_resolution",
    reason="CMP-17: api/lib_version_resolution.py not implemented until plan 23-05",
)
resolve_lib_version_id = lib_version_resolution.resolve_lib_version_id


@pytest.fixture(autouse=True)
def _clear_dependency_overrides():
    yield
    from main import app
    app.dependency_overrides.clear()


def auth_headers():
    return {"Authorization": "Bearer test-token"}


# ---------------------------------------------------------------------------
# Task 2, Part 1 -- resolve_lib_version_id: pure unit tests, one per chain rung.
#
# db is a mock whose .execute(query, params) dispatches on a distinguishing substring of
# the table name in `query` (most-specific first, since "toolkit_hardware_libs" itself
# contains "hardware_libs" as a substring). The exact column list a real implementation
# selects is not pinned here -- only the chain ORDER and the (id, reason) return contract
# plan 23-05 must preserve.
# ---------------------------------------------------------------------------

class _Result:
    def __init__(self, one=None):
        self._one = one

    def fetchone(self):
        return self._one


def _db_stub(*, toolkit_default_row=None, lib_row=None, version_row=None):
    def _execute(query, params=None):
        sql = " ".join(str(query).split())
        if "toolkit_hardware_libs" in sql:
            return _Result(toolkit_default_row)
        if "hardware_lib_versions" in sql:
            return _Result(version_row)
        if "hardware_libs" in sql:
            return _Result(lib_row)
        return _Result(None)

    db = MagicMock()
    db.execute.side_effect = _execute
    return db


def test_pin_wins_over_everything():
    db = _db_stub()  # no rows needed -- pin short-circuits before any query
    version_id, reason = resolve_lib_version_id(db, lib_id=10, toolkit_id=5, pinned_version_id=999)
    assert (version_id, reason) == (999, "pin")


def test_toolkit_default_wins_when_no_pin():
    db = _db_stub(toolkit_default_row=SimpleNamespace(default_version_id=42))
    version_id, reason = resolve_lib_version_id(db, lib_id=10, toolkit_id=5, pinned_version_id=None)
    assert (version_id, reason) == (42, "toolkit_default")


def test_stable_wins_when_no_pin_no_toolkit_default():
    db = _db_stub(lib_row=SimpleNamespace(stable_version_id=55, active_version_id=100))
    version_id, reason = resolve_lib_version_id(db, lib_id=10, toolkit_id=5, pinned_version_id=None)
    assert (version_id, reason) == (55, "stable")


def test_active_wins_when_state_beta_and_no_stable():
    db = _db_stub(
        lib_row=SimpleNamespace(stable_version_id=None, active_version_id=100),
        version_row=SimpleNamespace(id=100, state="beta"),
    )
    version_id, reason = resolve_lib_version_id(db, lib_id=10, toolkit_id=5, pinned_version_id=None)
    assert (version_id, reason) == (100, "active")


def test_active_wins_when_state_stable_and_no_stable_pin():
    db = _db_stub(
        lib_row=SimpleNamespace(stable_version_id=None, active_version_id=100),
        version_row=SimpleNamespace(id=100, state="stable"),
    )
    version_id, reason = resolve_lib_version_id(db, lib_id=10, toolkit_id=5, pinned_version_id=None)
    assert (version_id, reason) == (100, "active")


def test_none_when_active_state_unvalidated_and_no_stable():
    """Today this is a silent skip with a log warning -- CMP-17 turns it into a preflight issue."""
    db = _db_stub(
        lib_row=SimpleNamespace(stable_version_id=None, active_version_id=100),
        version_row=SimpleNamespace(id=100, state="unvalidated"),
    )
    version_id, reason = resolve_lib_version_id(db, lib_id=10, toolkit_id=5, pinned_version_id=None)
    assert (version_id, reason) == (None, "none")


def test_none_when_nothing_at_all():
    db = _db_stub()
    version_id, reason = resolve_lib_version_id(db, lib_id=10, toolkit_id=5, pinned_version_id=None)
    assert (version_id, reason) == (None, "none")


def test_toolkit_id_none_skips_toolkit_default_rung():
    """A lib not linked to any specific toolkit (toolkit_id=None) must not attempt the
    toolkit_default rung and fall through to stable/active/none."""
    db = _db_stub(lib_row=SimpleNamespace(stable_version_id=55, active_version_id=100))
    version_id, reason = resolve_lib_version_id(db, lib_id=10, toolkit_id=None, pinned_version_id=None)
    assert (version_id, reason) == (55, "stable")


# ---------------------------------------------------------------------------
# Task 2, Part 2 -- route-level regression tests, mocked-db.execute style
# (fixture pattern follows test_view_key_preflight.py's toolkit_dispatch section)
# ---------------------------------------------------------------------------

class FakeDispatchDb:
    """SQL-text-dispatching stub matching get_dispatch_spec's raw db.execute() calls."""

    def __init__(self, *, toolkit_row=None, module_row=None, td_row=None, lib_row=None,
                 version_by_id=None, cfg_row=None):
        self.toolkit_row = toolkit_row
        self.module_row = module_row
        self.td_row = td_row
        self.lib_row = lib_row
        self.version_by_id = version_by_id or {}
        self.cfg_row = cfg_row

    def execute(self, query, params=None):
        sql = " ".join(str(query).split())
        params = params or {}
        if sql.startswith("SELECT id, hardware_module_ids, flags, params_schema, is_backend_authored"):
            return _Result(self.toolkit_row)
        if sql.startswith("SELECT id, name, class_name, hardware_lib_id"):
            return _Result(self.module_row)
        if sql.startswith("SELECT hw_lib_versions"):
            return _Result(self.td_row)
        if "SELECT active_version_id FROM hardware_libs" in sql or "SELECT stable_version_id" in sql:
            return _Result(self.lib_row)
        if sql.startswith("SELECT source_code FROM hardware_lib_versions"):
            return _Result(self.version_by_id.get(params.get("id")))
        if sql.startswith("SELECT config FROM pilot_hardware_config"):
            return _Result(self.cfg_row)
        return _Result(None)


def _client_for(fake_db):
    from auth import verify_token
    from main import app
    from routers.toolkit_dispatch import get_sa_session
    app.dependency_overrides[verify_token] = lambda: {"sub": "test"}
    app.dependency_overrides[get_sa_session] = lambda: fake_db
    return TestClient(app)


def test_dispatch_spec_emits_active_source_when_no_stable_today_baseline():
    """Baseline (not xfail): with no stable version, today's chain already resolves via
    active -- proves the FakeDispatchDb harness itself, unaffected by CMP-17."""
    toolkit_row = SimpleNamespace(id=5, hardware_module_ids=[7], flags={}, params_schema={}, is_backend_authored=True)
    module_row = SimpleNamespace(id=7, name="MPR121", class_name="Touch_Detector", hardware_lib_id=10)
    lib_row = SimpleNamespace(active_version_id=100, stable_version_id=None)
    version_by_id = {100: SimpleNamespace(source_code="ACTIVE_SOURCE")}
    fake_db = FakeDispatchDb(toolkit_row=toolkit_row, module_row=module_row, lib_row=lib_row, version_by_id=version_by_id)
    resp = _client_for(fake_db).get("/api/toolkits/5/dispatch-spec?pilot_id=1", headers=auth_headers())
    assert resp.status_code == 200
    assert resp.json()["hardware"]["Modules"]["MPR121"]["MPR121"]["source_code"] == "ACTIVE_SOURCE"


@pytest.mark.xfail(reason="CMP-17: dispatch-spec still emits active, not stable, until plan 23-05", strict=False)
def test_dispatch_spec_emits_stable_source_when_stable_exists_and_no_pin():
    """The regression test: today's route emits the ACTIVE version's source_code even when a
    STABLE version exists and no pin is given. CMP-17 changes that ordering."""
    toolkit_row = SimpleNamespace(id=5, hardware_module_ids=[7], flags={}, params_schema={}, is_backend_authored=True)
    module_row = SimpleNamespace(id=7, name="MPR121", class_name="Touch_Detector", hardware_lib_id=10)
    lib_row = SimpleNamespace(active_version_id=100, stable_version_id=101)
    version_by_id = {
        100: SimpleNamespace(source_code="ACTIVE_SOURCE"),
        101: SimpleNamespace(source_code="STABLE_SOURCE"),
    }
    fake_db = FakeDispatchDb(toolkit_row=toolkit_row, module_row=module_row, lib_row=lib_row, version_by_id=version_by_id)
    resp = _client_for(fake_db).get("/api/toolkits/5/dispatch-spec?pilot_id=1", headers=auth_headers())
    assert resp.status_code == 200
    assert resp.json()["hardware"]["Modules"]["MPR121"]["MPR121"]["source_code"] == "STABLE_SOURCE"


@pytest.mark.xfail(reason="CMP-17: resolved_version_id/resolved_state/resolution_reason not implemented until plan 23-05", strict=False)
def test_toolkit_hardware_libs_carries_resolution_fields_per_lib():
    """GET /toolkits/{id}/hardware-libs?task_def_id=N must carry resolved_version_id,
    resolved_state and resolution_reason per lib. list_toolkit_hardware_libs lives in
    hardware_libs.py (ORM-session style, not the raw-SQL get_sa_session DI toolkit_dispatch.py
    uses), so it is mocked via _SA_SessionLocal per that module's own convention."""
    from models import HardwareLib, HardwareLibVersion, TaskToolkit

    lib = SimpleNamespace(
        id=10, name="compute_ops", filename="compute_ops.py", ast_metadata=None,
        active_version_id=100, stable_version_id=None, created_at=None, updated_at=None,
    )
    active_version = SimpleNamespace(
        id=100, hardware_lib_id=10, version_number=1, source_code="ACTIVE", sha256_hash="x",
        state="beta", ast_metadata=None, created_at=None, stable_at=None, stable_reason=None,
        stable_pilot=None, validation_error=None,
    )
    link = SimpleNamespace(hardware_lib_id=10, default_version_id=None)

    def _get(model, id_):
        if model is TaskToolkit:
            return SimpleNamespace(id=5)
        if model is HardwareLib:
            return lib
        if model is HardwareLibVersion:
            return active_version if id_ == 100 else None
        return None

    mock_db = MagicMock()
    mock_db.get.side_effect = _get
    mock_db.query.return_value.filter.return_value.all.return_value = [link]

    from auth import verify_token
    from main import app
    app.dependency_overrides[verify_token] = lambda: {"sub": "test"}
    with patch("routers.hardware_libs._SA_SessionLocal", return_value=mock_db):
        resp = TestClient(app).get("/api/toolkits/5/hardware-libs?task_def_id=42", headers=auth_headers())

    assert resp.status_code == 200
    entry = resp.json()["libs"][0]
    assert "resolved_version_id" in entry
    assert "resolved_state" in entry
    assert "resolution_reason" in entry
