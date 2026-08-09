"""Socket-free wire codec for the extlink driver (Phase 18, Plan 15).

Builds the same MessagePack envelope the Pi's `external_hardware_wire.py`
(plan 18-05, `encode()`) produces and decodes: same field names, same
`msgpack.packb(obj, use_bin_type=True)` call — matched deliberately, not
chosen independently, so a `raw=`/`use_bin_type=` mismatch can never turn a
signal name into bytes on the far end. This module owns every byte the
driver sends; no socket-library import here, ever (proven by
test_extlink_wire.py's AST-based hygiene guard and this plan's own
verification grep).

`now_ms()` is wall-clock time, deliberately. It is stamped as `ts_src` and
the Pi ignores it for FDA purposes (`ts_pi_recv` is canonical — see
18-CONTEXT.md "Transport + wire"), so the laptop's clock being wrong cannot
corrupt anything. Do not "fix" this to a monotonic clock — that would make
`ts_src` look comparable across machines when it never is (the laptop and
the rig are not NTP-synced to each other).
"""
import json
import time

import msgpack


def now_ms():
    """Wall-clock ms, not monotonic — see module docstring."""
    return int(time.time() * 1000)


def _envelope(kind, ts_ms, seq, **fields):
    payload = {
        "k": kind,
        "ts_src": now_ms() if ts_ms is None else ts_ms,
        "seq": seq,
    }
    payload.update(fields)
    return msgpack.packb(payload, use_bin_type=True)


def sig_frame(signal, value, seq, ts_ms=None):
    return _envelope("SIG", ts_ms, seq, sig=signal, v=value)


def evt_frame(event, payload, seq, ts_ms=None):
    return _envelope("EVT", ts_ms, seq, evt=event, p=payload)


def hb_frame(seq, ts_ms=None):
    return _envelope("HB", ts_ms, seq)


def coerce_value(token):
    """str -> int|float|bool|str|dict.

    Bools are real bools, checked with `isinstance(..., bool)` by the caller
    — the Pi's own `coerce_value` special-cases `bool` against Python's
    int-subclass trap (EXTLINK-12: `float(True) == 1.0`), so a driver that
    sent `1` for a bool signal would be silently dropped there with no
    visibility from the laptop. A `{...}` token is the one structured shape
    on the wire (the `@event` payload case) and parses as JSON. Everything
    else that isn't a number or a bool stays a plain string.
    """
    lowered = token.lower()
    if lowered in ("true", "false"):
        return lowered == "true"
    try:
        return int(token)
    except ValueError:
        pass
    try:
        return float(token)
    except ValueError:
        pass
    stripped = token.strip()
    if stripped.startswith("{") and stripped.endswith("}"):
        try:
            return json.loads(stripped)
        except ValueError:
            pass
    return token


def parse_command(line):
    """"name value" -> ("SIG"|"EVT", name, value); None on blank/no-value.

    A dict-valued token means EVT — a dict is the only structured payload on
    the wire, so it's the sole signal that distinguishes the two commands.
    Never raises: the driver's stdin loop must survive a stray Enter.
    """
    stripped = line.strip()
    if not stripped:
        return None
    parts = stripped.split(None, 1)
    if len(parts) < 2:
        return None
    name, rest = parts[0], parts[1].strip()
    if not rest:
        return None
    value = coerce_value(rest)
    kind = "EVT" if isinstance(value, dict) else "SIG"
    return (kind, name, value)
