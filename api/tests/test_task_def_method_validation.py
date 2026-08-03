"""_validate_task_definition resolves hardware methods through a class's in-file ancestors.

The soft drift-badge path (validation_status ok/broken) used to read the FLAT per-class
`ast_metadata`, which lists only the methods written in a class's own body. Real hardware
modules point at subclasses — module 'MPR121' has class_name 'Touch_Detector', and
`Touch_Detector(MPR121)` defines only `__init__` — so every inherited method was reported
missing and the task definition sat permanently badged `broken`.

These tests pin the resolved behaviour and the conservative `closed` rule that replaces it:
an absent method is only an error when the class's whole ancestor chain was resolvable in
that one source file.
"""
from types import SimpleNamespace

from routers.toolkits import _validate_task_definition

# Modelled on the real i2c.py shape: Touch_Detector inherits detect_change from MPR121,
# and MPR121's own base (Hardware) is imported, so the chain is never closed.
I2C_SRC = '''
from hardware.base import Hardware

class MPR121(Hardware):
    def detect_change(self):
        pass

    def read(self):
        pass

class Touch_Detector(MPR121):
    def __init__(self, address=True, num_detectors=1, device_name=None):
        pass
'''

# No bases at all -> the resolved method set IS exhaustive, so an absent name is a real error.
STANDALONE_SRC = '''
class Standalone:
    def foo(self):
        pass
'''


class _Result:
    """Stands in for what `db.execute(...)` returns — only `.fetchone()` / `.fetchall()`."""

    def __init__(self, one=None, many=None):
        self._one = one
        self._many = many or []

    def fetchone(self):
        return self._one

    def fetchall(self):
        return self._many


class _Query:
    def __init__(self, result):
        self._result = result

    def filter(self, *_args, **_kwargs):
        return self

    def one_or_none(self):
        return self._result


class FakeDb:
    """SQL-text-dispatching stub, matching on distinguishing substrings rather than call order
    so a test scoped to one branch survives an unrelated query changing."""

    def __init__(
        self, *, toolkit=None, modules=(), hw_lib_versions=None,
        version_sources=None, active_sources=None,
    ):
        self.toolkit = toolkit
        self.modules = list(modules)                    # rows: .name .class_name .hardware_lib_id
        self.hw_lib_versions = hw_lib_versions          # task_definitions.hw_lib_versions pin map
        self.version_sources = version_sources or {}    # version id -> source_code
        self.active_sources = active_sources or {}      # lib id -> active version's source_code

    def query(self, _model):
        return _Query(self.toolkit)

    def execute(self, query, params=None):
        sql = " ".join(str(query).split())
        params = params or {}
        if "FROM hardware_modules" in sql:
            return _Result(many=self.modules)
        if "hw_lib_versions FROM task_definitions" in sql:
            return _Result(one=SimpleNamespace(hw_lib_versions=self.hw_lib_versions))
        if "FROM hardware_libs l" in sql:
            src = self.active_sources.get(params.get("id"))
            return _Result(one=SimpleNamespace(source_code=src) if src is not None else None)
        if "FROM hardware_lib_versions WHERE id" in sql:
            src = self.version_sources.get(params.get("id"))
            return _Result(one=SimpleNamespace(source_code=src) if src is not None else None)
        return _Result()


def _module(name, class_name, lib_id=9):
    return SimpleNamespace(name=name, class_name=class_name, hardware_lib_id=lib_id)


def _toolkit(flags=None, module_ids=(7,)):
    return SimpleNamespace(flags=flags or {}, hardware_module_ids=list(module_ids))


def _fda(ref="MPR121", method="detect_change"):
    return {
        "version": 2,
        "initial_state": "idle",
        "states": {"idle": {}},
        "transitions": [],
        "trigger_assignments": [
            {
                "trigger_name": "TOUCH_INT",
                "actions": [{"type": "hardware", "ref": ref, "method": method, "args": []}],
            }
        ],
    }


def _fda_compute(ref="COMPUTE", method="add", output="target"):
    return {
        "version": 2,
        "initial_state": "idle",
        "states": {"idle": {}},
        "transitions": [],
        "trigger_assignments": [
            {
                "trigger_name": "TOUCH_INT",
                "actions": [{"type": "compute", "ref": ref, "method": method, "args": [], "output": output}],
            }
        ],
    }


COMPUTE_SRC = '''
class ComputeOps:
    def add(self, a, b):
        return a + b
'''


# ---------------------------------------------------------------------------
# The regression this change fixes
# ---------------------------------------------------------------------------

def test_method_inherited_from_in_file_base_is_not_reported_missing():
    """The exact live case: module MPR121 -> class Touch_Detector -> detect_change on MPR121."""
    db = FakeDb(
        toolkit=_toolkit(),
        modules=[_module("MPR121", "Touch_Detector")],
        active_sources={9: I2C_SRC},
    )
    assert _validate_task_definition(db, _fda(), toolkit_id=100) == ("ok", None)


def test_method_defined_on_the_class_itself_still_resolves():
    db = FakeDb(
        toolkit=_toolkit(),
        modules=[_module("MPR121", "MPR121")],
        active_sources={9: I2C_SRC},
    )
    assert _validate_task_definition(db, _fda(), toolkit_id=100) == ("ok", None)


# ---------------------------------------------------------------------------
# The conservative rule: report only when the ancestor chain is closed
# ---------------------------------------------------------------------------

def test_unknown_method_not_reported_when_ancestry_escapes_the_file():
    """Touch_Detector -> MPR121 -> Hardware(imported). Hardware's own methods are invisible in
    this source, so an absent name proves nothing and must not be reported."""
    db = FakeDb(
        toolkit=_toolkit(),
        modules=[_module("MPR121", "Touch_Detector")],
        active_sources={9: I2C_SRC},
    )
    assert _validate_task_definition(db, _fda(method="release"), toolkit_id=100) == ("ok", None)


def test_unknown_method_reported_when_ancestry_is_closed():
    """Guards against the fix degenerating into "never report anything"."""
    db = FakeDb(
        toolkit=_toolkit(),
        modules=[_module("Widget", "Standalone")],
        active_sources={9: STANDALONE_SRC},
    )
    status, message = _validate_task_definition(db, _fda(ref="Widget", method="bar"), toolkit_id=100)
    assert status == "broken"
    assert message == "Trigger 'TOUCH_INT': Widget.bar not found in lib (class Standalone)"


def test_known_method_on_closed_class_is_ok():
    db = FakeDb(
        toolkit=_toolkit(),
        modules=[_module("Widget", "Standalone")],
        active_sources={9: STANDALONE_SRC},
    )
    assert _validate_task_definition(db, _fda(ref="Widget", method="foo"), toolkit_id=100) == ("ok", None)


# ---------------------------------------------------------------------------
# Source selection: pinned version, then the lib's active version
# ---------------------------------------------------------------------------

def test_pinned_lib_version_source_is_preferred_over_the_active_one():
    """The pin decides: Touch_Detector exists only in the pinned version's source."""
    db = FakeDb(
        toolkit=_toolkit(),
        modules=[_module("MPR121", "Touch_Detector")],
        hw_lib_versions={"9": 26},
        version_sources={26: I2C_SRC},
        active_sources={9: STANDALONE_SRC},
    )
    assert _validate_task_definition(db, _fda(), toolkit_id=100, task_def_id=186) == ("ok", None)


def test_falls_back_to_active_version_when_the_pinned_row_is_gone():
    db = FakeDb(
        toolkit=_toolkit(),
        modules=[_module("MPR121", "Touch_Detector")],
        hw_lib_versions={"9": 999},          # version row deleted
        version_sources={},
        active_sources={9: I2C_SRC},
    )
    assert _validate_task_definition(db, _fda(), toolkit_id=100, task_def_id=186) == ("ok", None)


def test_no_source_anywhere_skips_method_checking_entirely():
    db = FakeDb(
        toolkit=_toolkit(),
        modules=[_module("MPR121", "Touch_Detector")],
        active_sources={},
    )
    assert _validate_task_definition(db, _fda(method="whatever"), toolkit_id=100) == ("ok", None)


# ---------------------------------------------------------------------------
# Checks that must survive unchanged
# ---------------------------------------------------------------------------

def test_class_missing_from_source_is_still_reported():
    db = FakeDb(
        toolkit=_toolkit(),
        modules=[_module("MPR121", "Ghost_Class")],
        active_sources={9: I2C_SRC},
    )
    status, message = _validate_task_definition(db, _fda(), toolkit_id=100)
    assert status == "broken"
    assert message == "Trigger 'TOUCH_INT': class 'Ghost_Class' not found in lib AST"


def test_hardware_ref_outside_the_toolkit_is_still_reported():
    db = FakeDb(
        toolkit=_toolkit(),
        modules=[_module("MPR121", "Touch_Detector")],
        active_sources={9: I2C_SRC},
    )
    status, message = _validate_task_definition(db, _fda(ref="Ghost_Module"), toolkit_id=100)
    assert status == "broken"
    assert message == "Trigger 'TOUCH_INT': hardware module 'Ghost_Module' not in toolkit modules"


def test_flag_drift_is_still_reported():
    fda = {
        "version": 2,
        "initial_state": "idle",
        "states": {"idle": {"entry_actions": [{"type": "flag", "ref": "ghost_flag"}]}},
        "transitions": [],
    }
    db = FakeDb(
        toolkit=_toolkit(flags={"real_flag": {}}),
        modules=[_module("MPR121", "Touch_Detector")],
        active_sources={9: I2C_SRC},
    )
    status, message = _validate_task_definition(db, fda, toolkit_id=100)
    assert status == "broken"
    assert "flag 'ghost_flag' not in toolkit flags" in message


def test_no_toolkit_context_returns_ok():
    assert _validate_task_definition(FakeDb(), _fda(), toolkit_id=None) == ("ok", None)
    assert _validate_task_definition(FakeDb(toolkit=None), _fda(), toolkit_id=100) == ("ok", None)


# ---------------------------------------------------------------------------
# CMP-11 (Plan 23-03): compute actions follow the same drift-badge rule as hardware
# ---------------------------------------------------------------------------

def test_compute_action_unknown_method_reported_same_as_hardware():
    """A compute lib IS a hardware_modules row — module 'COMPUTE' -> class 'ComputeOps'."""
    db = FakeDb(
        toolkit=_toolkit(),
        modules=[_module("COMPUTE", "ComputeOps")],
        active_sources={9: COMPUTE_SRC},
    )
    status, message = _validate_task_definition(db, _fda_compute(method="mystery"), toolkit_id=100)
    assert status == "broken"
    assert message == "Trigger 'TOUCH_INT': COMPUTE.mystery not found in lib (class ComputeOps)"


def test_compute_action_known_method_is_ok():
    db = FakeDb(
        toolkit=_toolkit(),
        modules=[_module("COMPUTE", "ComputeOps")],
        active_sources={9: COMPUTE_SRC},
    )
    assert _validate_task_definition(db, _fda_compute(method="add"), toolkit_id=100) == ("ok", None)
