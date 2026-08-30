"""Pure, socket-free wire codec for mics-link (Phase 34, Plan 01).

Mirrors `external_hardware_wire.py`'s `encode()` line for line (READ-ONLY reference at
`~/mics_core/autopilot/autopilot/hardware/external_hardware_wire.py`) — that similarity is
deliberate: every byte this module emits for SIG/EVT/HB/ACK must be identical to what the
Pi's own codec emits for the same fields (see `tests/test_wire_parity.py`, which pins this
byte-for-byte against a frozen corpus and a live-interop check).

No `zmq` import anywhere in this file, at module scope or nested (guarded by
`tests/test_import_hygiene.py`'s AST walk) — this module must import cleanly on a machine
with no pyzmq installed (SDK-11).

`ts_src` is deliberately wall-clock, not monotonic. The Pi ignores it for FDA purposes
(`ts_pi_recv`, stamped on arrival, is canonical) — do NOT "fix" this to a monotonic clock,
that would make it look comparable across two machines that are not NTP-synced to each
other. No latency is asserted anywhere in this phase (that's Phase 28).
"""
import time

import msgpack

WIRE_KINDS = frozenset({"SIG", "EVT", "HB", "ACK", "CMD"})

# The dtypes a caller may hand to sig_frame's `v` — order stated here is documentation
# only, it has no bearing on wire bytes.
ALLOWED_DTYPES = (int, float, bool, str)


def now_ms():
    """Wall-clock ms, deliberately NOT monotonic — see module docstring."""
    return int(time.time() * 1000)


def encode(kind, **fields):
    """Pack a wire envelope. Mirrors the Pi's encode() exactly: `payload.update(fields)`
    preserves kwarg insertion order, and `msgpack.packb` preserves dict order, so byte
    parity constrains call-site kwarg ORDER, not just the key set (decision 4). Raises
    ValueError for an unknown kind — a programmer error, never something arriving off the
    wire.
    """
    if kind not in WIRE_KINDS:
        raise ValueError("encode: unknown wire kind {!r}".format(kind))
    payload = {"k": kind}
    payload.update(fields)
    return msgpack.packb(payload, use_bin_type=True)


def decode_envelope(raw):
    """bytes -> envelope dict, or None on anything malformed. NEVER raises: msgpack raises
    different exception types across versions, and this SDK's callers must never have a
    corrupt frame take their loop down with it (mirrors the Pi's EXTLINK-08 posture).
    Unlike the Pi's version this takes no `stats` argument — the SDK's own callers own
    their own counters.
    """
    try:
        unpacked = msgpack.unpackb(raw, raw=False)
    except Exception:
        return None
    if not isinstance(unpacked, dict) or unpacked.get("k") not in WIRE_KINDS:
        return None
    return unpacked


def decode_cmd(raw):
    """bytes -> {"cmd_id", "name", "args", "ts_pi"} for a CMD frame, or None for anything
    else (wrong kind, or malformed — never raises).
    """
    envelope = decode_envelope(raw)
    if envelope is None or envelope.get("k") != "CMD":
        return None
    return {
        "cmd_id": envelope.get("cmd_id"),
        "name": envelope.get("name"),
        "args": envelope.get("args"),
        "ts_pi": envelope.get("ts_pi"),
    }


def sig_frame(signal, value, seq, ts_ms=None):
    """SIG {k, ts_src, seq, sig, v} — latest-value semantics. Field order matches decision
    4: ts_src, seq, sig, v.
    """
    return encode(
        "SIG",
        ts_src=now_ms() if ts_ms is None else ts_ms,
        seq=seq,
        sig=signal,
        v=value,
    )


def evt_frame(event, payload, seq, ts_ms=None):
    """EVT {k, ts_src, seq, evt, p} — event with payload. Field order: ts_src, seq, evt, p."""
    return encode(
        "EVT",
        ts_src=now_ms() if ts_ms is None else ts_ms,
        seq=seq,
        evt=event,
        p=payload,
    )


def hb_frame(seq, ts_ms=None):
    """HB {k, ts_src, seq} — heartbeat. Field order: ts_src, seq."""
    return encode("HB", ts_src=now_ms() if ts_ms is None else ts_ms, seq=seq)


def ack_frame(cmd_id, result, ts_ms=None):
    """ACK {k, ts_src, cmd_id, result} — command result, NO seq field. Field order:
    ts_src, cmd_id, result.
    """
    return encode(
        "ACK",
        ts_src=now_ms() if ts_ms is None else ts_ms,
        cmd_id=cmd_id,
        result=result,
    )


class SeqCounter(object):
    """Monotonic sender-side sequence. NO reset method, NO public setter — SDK-07 locks
    `seq` continuity across reconnect and CONTEXT.md locks `seq` as never surfaced to a
    caller for mutation. The only way to advance it is `next()`.
    """

    def __init__(self):
        self._value = -1

    def next(self):
        self._value += 1
        return self._value

    @property
    def value(self):
        return self._value
