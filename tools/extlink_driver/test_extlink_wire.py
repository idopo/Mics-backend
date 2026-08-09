"""Socket-free tests for extlink_wire.py (Phase 18, Plan 15).

No `zmq` import anywhere in this file or in the module under test — `zmq` is
absent from this dev host, only `msgpack` is installed (plan 18-01). Run with:
    python3 -m pytest -q tools/extlink_driver/

The interop test loads the Pi's REAL wire module by path
(`importlib.util.spec_from_file_location`, the established
autopilot-free-module pattern) and feeds it driver-built frames, so the
frame format is proven byte-compatible rather than merely self-consistent.
"""
import ast
import importlib.util
import os

import msgpack
import pytest

from extlink_wire import (
    coerce_value,
    evt_frame,
    hb_frame,
    now_ms,
    parse_command,
    sig_frame,
)

PI_WIRE_PATH = "/home/ido/pi-mirror/autopilot/autopilot/hardware/external_hardware_wire.py"


# --- coerce_value ---


def test_coerce_value_float():
    assert coerce_value("0.7") == 0.7
    assert isinstance(coerce_value("0.7"), float)


def test_coerce_value_int():
    assert coerce_value("3") == 3
    assert isinstance(coerce_value("3"), int)
    assert not isinstance(coerce_value("3"), bool)


def test_coerce_value_negative_int():
    assert coerce_value("-2") == -2
    assert isinstance(coerce_value("-2"), int)


def test_coerce_value_bool_true_case_insensitive():
    for token in ("true", "True", "TRUE", "tRuE"):
        value = coerce_value(token)
        assert value is True
        assert isinstance(value, bool)


def test_coerce_value_bool_false_case_insensitive():
    for token in ("false", "False", "FALSE"):
        value = coerce_value(token)
        assert value is False
        assert isinstance(value, bool)


def test_coerce_value_bool_is_real_bool_not_int():
    # EXTLINK-12's int-subclass trap: a driver sending 1 for a bool signal
    # would be silently dropped by _dispatch_sig with no visibility from the
    # laptop. Pinning isinstance(..., bool) explicitly, not just == True.
    assert isinstance(coerce_value("true"), bool)
    assert isinstance(coerce_value("false"), bool)


def test_coerce_value_json_dict():
    value = coerce_value('{"object": "paw", "confidence": 0.9}')
    assert value == {"object": "paw", "confidence": 0.9}
    assert isinstance(value, dict)


def test_coerce_value_plain_string_fallback():
    assert coerce_value("armed") == "armed"
    assert isinstance(coerce_value("armed"), str)


# --- parse_command ---


def test_parse_command_signal():
    assert parse_command("left_paw_x 0.7") == ("SIG", "left_paw_x", 0.7)


def test_parse_command_event_dict_payload():
    line = 'object_detected {"object": "paw", "confidence": 0.9}'
    kind, name, value = parse_command(line)
    assert kind == "EVT"
    assert name == "object_detected"
    assert value == {"object": "paw", "confidence": 0.9}


def test_parse_command_blank_line_returns_none():
    assert parse_command("") is None
    assert parse_command("   ") is None


def test_parse_command_no_value_returns_none():
    assert parse_command("left_paw_x") is None
    assert parse_command("left_paw_x   ") is None


def test_parse_command_whitespace_tolerated():
    assert parse_command("   left_paw_x   0.7   ") == ("SIG", "left_paw_x", 0.7)


def test_parse_command_value_may_contain_spaces():
    line = 'object_detected {"object": "paw hand", "confidence": 0.9}'
    kind, name, value = parse_command(line)
    assert kind == "EVT"
    assert value == {"object": "paw hand", "confidence": 0.9}


def test_parse_command_never_raises_on_garbage():
    # Must never crash on a stray Enter or unparseable junk.
    for line in ("", "\n", "   \t  ", "just_a_name"):
        parse_command(line)  # no exception


# --- frame construction ---


def test_sig_frame_round_trips():
    frame = sig_frame("left_paw_x", 0.7, seq=12)
    unpacked = msgpack.unpackb(frame, raw=False)
    assert unpacked["k"] == "SIG"
    assert unpacked["sig"] == "left_paw_x"
    assert unpacked["v"] == 0.7
    assert unpacked["seq"] == 12
    assert isinstance(unpacked["ts_src"], int)


def test_evt_frame_round_trips():
    payload = {"object": "paw", "confidence": 0.9}
    frame = evt_frame("object_detected", payload, seq=3)
    unpacked = msgpack.unpackb(frame, raw=False)
    assert unpacked["k"] == "EVT"
    assert unpacked["evt"] == "object_detected"
    assert unpacked["p"] == payload
    assert unpacked["seq"] == 3


def test_hb_frame_round_trips():
    frame = hb_frame(seq=99)
    unpacked = msgpack.unpackb(frame, raw=False)
    assert unpacked["k"] == "HB"
    assert unpacked["seq"] == 99
    assert isinstance(unpacked["ts_src"], int)


def test_seq_carried_verbatim():
    for seq in (0, 1, 12345):
        unpacked = msgpack.unpackb(sig_frame("s", 1, seq=seq), raw=False)
        assert unpacked["seq"] == seq


def test_ts_ms_defaults_to_now_ms_when_omitted():
    before = now_ms()
    unpacked = msgpack.unpackb(sig_frame("s", 1, seq=0), raw=False)
    after = now_ms()
    assert before <= unpacked["ts_src"] <= after


def test_ts_ms_explicit_value_used_verbatim():
    unpacked = msgpack.unpackb(sig_frame("s", 1, seq=0, ts_ms=1000), raw=False)
    assert unpacked["ts_src"] == 1000


# --- interop: the Pi's real decoder must accept these frames ---


def _load_pi_wire_module():
    if not os.path.exists(PI_WIRE_PATH):
        pytest.skip("Pi wire module not found at {} — cannot run interop test".format(PI_WIRE_PATH))
    spec = importlib.util.spec_from_file_location("ehw", PI_WIRE_PATH)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_interop_sig_frame_decoded_by_pi_wire_module():
    ehw = _load_pi_wire_module()
    stats = ehw.DecodeStats()
    envelope = ehw.decode_envelope(sig_frame("left_paw_x", 0.7, seq=12), stats)
    assert envelope is not None
    assert stats.malformed == 0
    assert envelope["k"] == "SIG"
    assert envelope["sig"] == "left_paw_x"
    assert envelope["v"] == 0.7
    assert envelope["seq"] == 12


def test_interop_evt_frame_decoded_by_pi_wire_module():
    ehw = _load_pi_wire_module()
    stats = ehw.DecodeStats()
    payload = {"object": "paw", "confidence": 0.9}
    envelope = ehw.decode_envelope(evt_frame("object_detected", payload, seq=3), stats)
    assert envelope is not None
    assert stats.malformed == 0
    assert envelope["k"] == "EVT"
    assert envelope["evt"] == "object_detected"
    assert envelope["p"] == payload


def test_interop_hb_frame_decoded_by_pi_wire_module():
    ehw = _load_pi_wire_module()
    stats = ehw.DecodeStats()
    envelope = ehw.decode_envelope(hb_frame(seq=99), stats)
    assert envelope is not None
    assert stats.malformed == 0
    assert envelope["k"] == "HB"
    assert envelope["seq"] == 99


# --- hygiene ---


def test_wire_module_never_imports_zmq():
    src = open(os.path.join(os.path.dirname(__file__), "extlink_wire.py")).read()
    assert "zmq" not in src
    tree = ast.parse(src)
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            assert not any(alias.name.startswith("zmq") for alias in node.names)
        if isinstance(node, ast.ImportFrom):
            assert not (node.module or "").startswith("zmq")
