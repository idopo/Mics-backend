#!/usr/bin/env python3
"""Regenerates sdk/tests/golden_frames.py's GOLDEN_FRAMES corpus (Phase 34, Plan 01).

This is a standalone, RUNNABLE script, not a test. It loads the CANONICAL Pi reference
module (`pi_reference.CANONICAL_PI_WIRE_PATH`) and calls *its own* `encode()` with fixed,
hardcoded inputs — never a live clock, never `mics_link.wire` — so the frozen corpus is
provably derived from the Pi's real codec, not from the SDK's own (possibly-wrong) mirror
of it.

The corpus is regenerated ONLY by re-running this script against the pinned canonical
reference and pasting its output into golden_frames.py. It is never hand-edited.

Run from the sdk/ directory:
    cd sdk && python3 tests/generate_golden.py
"""
import os
import sys

sys.path.insert(0, os.path.dirname(__file__))

from pi_reference import CANONICAL_PI_WIRE_PATH, load_pi_wire  # noqa: E402


# Fixed inputs, one row per wire kind, plus a value-variety set for SIG (EXTLINK-12's
# int-subclass trap: bool must be exercised at the byte level, not just == True).
FRAME_SPECS = [
    {
        "kind": "SIG",
        "fields": [("ts_src", 1700000000123), ("seq", 12), ("sig", "left_paw_x"), ("v", 0.7)],
        "note": "float value",
    },
    {
        "kind": "SIG",
        "fields": [("ts_src", 1700000000124), ("seq", 13), ("sig", "trial_count"), ("v", 3)],
        "note": "int value",
    },
    {
        "kind": "SIG",
        "fields": [("ts_src", 1700000000125), ("seq", 14), ("sig", "door_open"), ("v", True)],
        "note": "bool value (must NOT pack as int)",
    },
    {
        "kind": "SIG",
        "fields": [("ts_src", 1700000000126), ("seq", 15), ("sig", "state_name"), ("v", "active")],
        "note": "str value",
    },
    {
        "kind": "EVT",
        "fields": [
            ("ts_src", 1700000000200),
            ("seq", 20),
            ("evt", "object_detected"),
            ("p", {"object": "paw", "confidence": 0.9}),
        ],
        "note": "event with dict payload",
    },
    {
        "kind": "HB",
        "fields": [("ts_src", 1700000000300), ("seq", 99)],
        "note": "heartbeat, no other fields",
    },
    {
        "kind": "ACK",
        "fields": [
            ("ts_src", 1700000000400),
            ("cmd_id", "cmd-001"),
            ("result", {"status": "ok"}),
        ],
        "note": "command result, NO seq field",
    },
    {
        "kind": "CMD",
        "fields": [
            ("ts_pi", 1700000000500),
            ("cmd_id", "cmd-002"),
            ("name", "set_reward"),
            ("args", {"amount": 1}),
        ],
        "note": "Pi -> SDK only, decode-only direction",
    },
]


def generate():
    pi_wire = load_pi_wire(CANONICAL_PI_WIRE_PATH)
    rows = []
    for spec in FRAME_SPECS:
        kwargs = dict(spec["fields"])
        raw = pi_wire.encode(spec["kind"], **kwargs)
        rows.append(
            {
                "kind": spec["kind"],
                "fields": spec["fields"],
                "hex": raw.hex(),
                "note": spec["note"],
            }
        )
    return rows


def main():
    for row in generate():
        print("    {")
        print('        "kind": {!r},'.format(row["kind"]))
        print('        "fields": {!r},'.format(row["fields"]))
        print('        "hex": {!r},'.format(row["hex"]))
        print('        "note": {!r},'.format(row["note"]))
        print("    },")


if __name__ == "__main__":
    main()
