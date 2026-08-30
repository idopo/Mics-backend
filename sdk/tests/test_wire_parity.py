"""Wire-parity tests for mics_link.wire (Phase 34, Plan 01).

Three groups, per the plan:
1. Frozen-corpus: mics_link.wire's raw bytes == the frozen GOLDEN_FRAMES hex. Byte
   comparisons only — never unpack-then-compare, which would test the wrong thing
   (34-RESEARCH.md Pitfall 1: two independently-buggy encoders can still agree once
   round-tripped through the same decoder).
2. Live-interop against CANONICAL_PI_WIRE_PATH: skip-if-absent.
3. Secondary drift against SECONDARY_PI_WIRE_PATH: skip-if-absent.
"""
import msgpack
import pytest

from golden_frames import GOLDEN_FRAMES
from pi_reference import CANONICAL_PI_WIRE_PATH, SECONDARY_PI_WIRE_PATH, load_pi_wire

from mics_link import wire


def _build_frame(row):
    """Build a GOLDEN_FRAMES row via mics_link.wire's public builders, using the row's own
    field order as the source of truth for what to pass."""
    fields = dict(row["fields"])
    kind = row["kind"]
    if kind == "SIG":
        return wire.sig_frame(fields["sig"], fields["v"], seq=fields["seq"], ts_ms=fields["ts_src"])
    if kind == "EVT":
        return wire.evt_frame(fields["evt"], fields["p"], seq=fields["seq"], ts_ms=fields["ts_src"])
    if kind == "HB":
        return wire.hb_frame(seq=fields["seq"], ts_ms=fields["ts_src"])
    if kind == "ACK":
        return wire.ack_frame(fields["cmd_id"], fields["result"], ts_ms=fields["ts_src"])
    if kind == "CMD":
        # CMD is Pi -> SDK only; mics_link never sends it, but encode() must still be able
        # to build one (mirrors the Pi's generic encode(), used here only to prove parity).
        return wire.encode("CMD", **fields)
    raise AssertionError("unknown golden frame kind {!r}".format(kind))


# --- Group 1: frozen-corpus tests, no Pi tree required ---


@pytest.mark.parametrize("row", GOLDEN_FRAMES, ids=[r["kind"] + ":" + r["note"] for r in GOLDEN_FRAMES])
def test_frame_matches_frozen_golden_hex(row):
    frame = _build_frame(row)
    assert isinstance(frame, bytes)
    assert frame == bytes.fromhex(row["hex"])


def test_encode_unknown_kind_raises_value_error():
    with pytest.raises(ValueError):
        wire.encode("NOPE")


def test_ts_ms_none_stamps_now_ms():
    before = wire.now_ms()
    frame = wire.sig_frame("s", 1, seq=0)
    after = wire.now_ms()
    unpacked = msgpack.unpackb(frame, raw=False)
    assert before <= unpacked["ts_src"] <= after


def test_ts_ms_explicit_used_verbatim():
    frame = wire.sig_frame("s", 1, seq=0, ts_ms=1000)
    unpacked = msgpack.unpackb(frame, raw=False)
    assert unpacked["ts_src"] == 1000


def test_decode_envelope_returns_none_never_raises_on_garbage():
    for raw in (b"", b"\xc1", msgpack.packb(5)):
        assert wire.decode_envelope(raw) is None


def test_decode_envelope_none_on_garbage_bytes():
    assert wire.decode_envelope(b"\xc1garbage") is None


def test_decode_cmd_returns_four_fields():
    frame = wire.encode("CMD", ts_pi=123, cmd_id="c1", name="set_reward", args={"amount": 1})
    result = wire.decode_cmd(frame)
    assert result == {"cmd_id": "c1", "name": "set_reward", "args": {"amount": 1}, "ts_pi": 123}


def test_decode_cmd_returns_none_for_non_cmd_frame():
    frame = wire.sig_frame("s", 1, seq=0)
    assert wire.decode_cmd(frame) is None


def test_decode_cmd_returns_none_on_garbage():
    assert wire.decode_cmd(b"\xc1garbage") is None


def test_seq_counter_yields_monotonic_sequence():
    counter = wire.SeqCounter()
    assert [counter.next() for _ in range(3)] == [0, 1, 2]


def test_seq_counter_has_no_public_reset_or_setter():
    counter = wire.SeqCounter()
    counter.next()
    for name in dir(counter):
        if name.startswith("_"):
            continue
        assert not name.startswith("reset"), "unexpected public reset method: {}".format(name)
        assert not name.startswith("set_"), "unexpected public setter: {}".format(name)
    assert not hasattr(wire.SeqCounter, "seq")


def test_seq_counter_value_property_reflects_last_issued():
    counter = wire.SeqCounter()
    first = counter.next()
    assert counter.value == first
    second = counter.next()
    assert counter.value == second == first + 1


# --- Group 2: live-interop against the canonical Pi reference, skip-if-absent ---


def test_interop_pi_encode_matches_sdk_encode_for_every_kind():
    pi_wire = load_pi_wire(CANONICAL_PI_WIRE_PATH)
    for row in GOLDEN_FRAMES:
        pi_frame = pi_wire.encode(row["kind"], **dict(row["fields"]))
        sdk_frame = _build_frame(row)
        assert pi_frame == sdk_frame, "mismatch for {}".format(row["note"])


def test_interop_pi_decode_accepts_sdk_frames():
    pi_wire = load_pi_wire(CANONICAL_PI_WIRE_PATH)
    for row in GOLDEN_FRAMES:
        if row["kind"] == "CMD":
            continue  # CMD is Pi -> SDK only; the Pi never decodes its own CMD frames
        stats = pi_wire.DecodeStats()
        frame = _build_frame(row)
        envelope = pi_wire.decode_envelope(frame, stats)
        assert envelope is not None
        assert stats.malformed == 0
        assert envelope["k"] == row["kind"]


# --- Group 3: secondary drift check against pi-mirror, skip-if-absent ---


def test_secondary_pi_tree_agrees_with_canonical():
    canonical = load_pi_wire(CANONICAL_PI_WIRE_PATH)
    secondary = load_pi_wire(SECONDARY_PI_WIRE_PATH)
    for row in GOLDEN_FRAMES:
        kwargs = dict(row["fields"])
        assert canonical.encode(row["kind"], **kwargs) == secondary.encode(row["kind"], **kwargs)
