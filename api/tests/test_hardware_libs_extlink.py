"""Contract tests for the @signal/@event/@command/@decoder AST extractor (EXTLINK-09, plan 18-07).

Two halves, mirroring test_view_key_preflight.py:
1. Pure unit tests against `extract_extlink_metadata` directly -- no DB, no TestClient. Guarded
   by `pytest.importorskip("extlink_ast")` as the first statement of each test body, since
   `api/extlink_ast.py` does not exist until plan 18-07.
2. One route-level round-trip test through `POST /api/hardware-libs`, additionally marked
   `xfail(strict=False)` since `extract_ast_metadata` (api/routers/hardware_libs.py) does not
   call `extract_extlink_metadata` until plan 18-07 wires the two together.

Target-file resolution (an open question in 18-VALIDATION.md): `grep -rl "extract_ast_metadata"
api/tests/` returns nothing today -- no existing test file owns extract_ast_metadata's contract,
so this is a new dedicated file rather than an extension of one.
"""
import ast

import pytest

# ---------------------------------------------------------------------------
# Source fixtures -- each is a realistic ExternalHardware subclass body. The extractor works on
# text (never imports the module), so the base class need not exist for the test to be meaningful.
# ---------------------------------------------------------------------------

SIGNAL_SOURCE = '''
from external_hardware import ExternalHardware, signal


class BodyTracker(ExternalHardware):
    @signal(default=0.0, stale_after_ms=200, stale_policy="hold_last")
    def left_paw_x(self) -> float:
        pass
'''

SIGNAL_NO_ANNOTATION_SOURCE = '''
from external_hardware import ExternalHardware, signal


class BodyTracker(ExternalHardware):
    @signal(default=0.0, stale_after_ms=200, stale_policy="hold_last")
    def left_paw_x(self):
        pass
'''

PAYLOAD_BARE_TYPES_SOURCE = '''
from external_hardware import ExternalHardware, event


class Detector(ExternalHardware):
    @event(payload={"object": str, "confidence": float})
    def object_seen(self):
        pass
'''

COMMAND_SOURCE = '''
from external_hardware import ExternalHardware, command


class Amp(ExternalHardware):
    @command
    def set_gain(self, gain: float, unit: str = "dB") -> bool:
        pass
'''

DECODER_SOURCE = '''
from external_hardware import ExternalHardware, decoder


class Receiver(ExternalHardware):
    @decoder
    def decode(self, frames):
        pass
'''

NO_DECODER_SOURCE = '''
from external_hardware import ExternalHardware, command


class Receiver(ExternalHardware):
    @command
    def ping(self) -> bool:
        pass
'''

ZERO_SIGNAL_SOURCE = '''
from external_hardware import ExternalHardware, command, decoder


class OEControl(ExternalHardware):
    @command
    def start_recording(self) -> bool:
        pass

    @decoder
    def decode(self, frames):
        pass
'''

PLAIN_HARDWARE_SOURCE = '''
from autopilot.hardware.gpio import Digital_Out


class Valve(Digital_Out):
    def open(self):
        pass
'''


# ---------------------------------------------------------------------------
# Pure unit tests
# ---------------------------------------------------------------------------

def test_extlink_extract_signal_decorator_literal_kwargs():
    pytest.importorskip("extlink_ast")
    from extlink_ast import extract_extlink_metadata

    meta = extract_extlink_metadata(SIGNAL_SOURCE)
    assert meta["BodyTracker"]["signals"]["left_paw_x"] == {
        "dtype": "float", "default": 0.0, "stale_after_ms": 200, "stale_policy": "hold_last",
    }


def test_extlink_extract_signal_dtype_falls_back_to_default_when_no_annotation():
    pytest.importorskip("extlink_ast")
    from extlink_ast import extract_extlink_metadata

    meta = extract_extlink_metadata(SIGNAL_NO_ANNOTATION_SOURCE)
    assert meta["BodyTracker"]["signals"]["left_paw_x"]["dtype"] == "float"


def test_extlink_payload_bare_types():
    pytest.importorskip("extlink_ast")
    from extlink_ast import extract_extlink_metadata

    meta = extract_extlink_metadata(PAYLOAD_BARE_TYPES_SOURCE)
    assert meta["Detector"]["events"]["object_seen"]["payload"] == {
        "object": "str", "confidence": "float",
    }

    # Pitfall 5: ast.literal_eval on the equivalent literal dict genuinely raises, because bare
    # type names (`str`, `float`) parse as ast.Name nodes, not literals. This documents why the
    # extractor cannot use it and must not raise on this snippet.
    payload_node = ast.parse('{"object": str, "confidence": float}', mode="eval")
    with pytest.raises(ValueError):
        ast.literal_eval(payload_node)


def test_extlink_extract_command_args_and_return():
    pytest.importorskip("extlink_ast")
    from extlink_ast import extract_extlink_metadata

    meta = extract_extlink_metadata(COMMAND_SOURCE)
    cmd = meta["Amp"]["commands"]["set_gain"]
    assert cmd["args"] == [{"name": "gain", "dtype": "float"}, {"name": "unit", "dtype": "str"}]
    assert cmd["returns"] == "bool"


def test_extlink_extract_decoder_flag():
    pytest.importorskip("extlink_ast")
    from extlink_ast import extract_extlink_metadata

    meta = extract_extlink_metadata(DECODER_SOURCE)
    assert meta["Receiver"]["decoder"] == "decode"

    no_decoder_meta = extract_extlink_metadata(NO_DECODER_SOURCE)
    assert no_decoder_meta["Receiver"]["decoder"] is None


def test_extlink_zero_signal_class_is_legal():
    pytest.importorskip("extlink_ast")
    from extlink_ast import extract_extlink_metadata

    meta = extract_extlink_metadata(ZERO_SIGNAL_SOURCE)
    assert meta["OEControl"]["signals"] == {}
    assert meta["OEControl"]["decoder"] == "decode"


def test_extlink_absent_for_plain_hardware_class():
    pytest.importorskip("extlink_ast")
    from extlink_ast import extract_extlink_metadata

    meta = extract_extlink_metadata(PLAIN_HARDWARE_SOURCE)
    assert "Valve" not in meta or "extlink" not in meta.get("Valve", {})

    # Existing (non-extlink) libs' ast_metadata must stay byte-identical after this feature
    # lands -- extract_ast_metadata itself is untouched by this test file.
    from routers.hardware_libs import extract_ast_metadata

    existing_meta = extract_ast_metadata(PLAIN_HARDWARE_SOURCE)
    assert "extlink" not in existing_meta


# ---------------------------------------------------------------------------
# Route-level round trip: POST /api/hardware-libs stores an `extlink` block in ast_metadata
# ---------------------------------------------------------------------------

EXTLINK_UPLOAD_SOURCE = '''
from external_hardware import ExternalHardware, command, signal


class OpenEphysProbe(ExternalHardware):
    @signal(default=0.0, stale_after_ms=200, stale_policy="hold_last")
    def firing_rate(self) -> float:
        pass

    @command
    def start_recording(self) -> bool:
        pass
'''


@pytest.fixture(autouse=True)
def _clear_dependency_overrides():
    yield
    from main import app
    app.dependency_overrides.clear()


def _client():
    from fastapi.testclient import TestClient

    from auth import verify_token
    from main import app
    app.dependency_overrides[verify_token] = lambda: {"sub": "test"}
    return TestClient(app)


def auth_headers():
    return {"Authorization": "Bearer test-token"}


def test_extlink_upload_round_trip():
    pytest.importorskip("extlink_ast")
    resp = _client().post(
        "/api/hardware-libs",
        data={"name": "oe_probe_extlink", "kind": "hardware"},
        files={"file": ("oe_probe_extlink.py", EXTLINK_UPLOAD_SOURCE, "text/x-python")},
        headers=auth_headers(),
    )
    assert resp.status_code in (200, 201)
    body = resp.json()
    ast_metadata = body["ast_metadata"]
    assert "classes" in ast_metadata  # existing block unaffected
    assert ast_metadata["extlink"]["OpenEphysProbe"]["signals"]["firing_rate"]["dtype"] == "float"
    assert "start_recording" in ast_metadata["extlink"]["OpenEphysProbe"]["commands"]


SIGNAL_SPLAT_SOURCE = '''
from external_hardware import ExternalHardware, signal

_SIGNAL_KWARGS = {"default": 0.0}


class Weird(ExternalHardware):
    @signal(**_SIGNAL_KWARGS)
    def odd(self) -> float:
        pass
'''


def test_extlink_signal_splat_kwargs_does_not_block_upload():
    """`@signal(**kwargs)` is a splat -- nothing sensible can extract from it. The upload must
    still succeed 200 with the `classes` block intact; extlink extraction failures are narrowly
    caught and logged, never allowed to 500 the whole upload."""
    pytest.importorskip("extlink_ast")
    resp = _client().post(
        "/api/hardware-libs",
        data={"name": "weird_splat_signal", "kind": "hardware"},
        files={"file": ("weird_splat_signal.py", SIGNAL_SPLAT_SOURCE, "text/x-python")},
        headers=auth_headers(),
    )
    assert resp.status_code in (200, 201)
    assert "classes" in resp.json()["ast_metadata"]
