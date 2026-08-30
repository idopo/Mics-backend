"""Detects a globally-patched msgpack before it silently corrupts every frame we send
(SDK-02 as amended, 34-01-PLAN.md's cross-platform/vendor-neutrality amendment).

`msgpack-numpy` is commonly present in scientific Python environments that patch msgpack
globally (verified against an inspected scientific-computing conda environment) and its
`msgpack_numpy.patch()` reassigns
`msgpack.packb`/`unpackb`/`Packer`/`Unpacker` at MODULE level — binding `msgpack.packb`
inside `wire.py` at import time does NOT dodge it (verified against msgpack_numpy's own
source). If anything else in the researcher's process calls `patch()`, every frame
`mics_link` emits silently becomes numpy-extended and the Pi's decoder counts it
`malformed`, with no visible symptom on this side.

Usage:
    python -m mics_link.selfcheck        # CLI, exits 1 with a message on failure
    from mics_link.selfcheck import selfcheck
    selfcheck()                          # called once inside connect() (plan 34-06)

`MicsLinkError` is imported from `mics_link.errors` — the package's single home for every
exception `mics_link` raises (34-06 merge reconciliation: this module used to define its own
unrelated `MicsLinkError` class, which meant `except mics_link.MicsLinkError` around
`commands.py`/`transport.py` silently missed selfcheck failures). See
`tests/test_public_api.py` for the cross-module isinstance proof.
"""
import sys

from . import wire
from .errors import MicsLinkError

# One known SIG frame + its frozen expected hex. Deliberately duplicated (not imported)
# from tests/golden_frames.py's first entry: this module ships inside the installed
# package and tests/ does not, so it must be self-contained. Kept in sync by
# tests/test_selfcheck.py, which asserts this constant equals GOLDEN_FRAMES[0].
_KNOWN_SIG_FIELDS = {"sig": "left_paw_x", "v": 0.7, "seq": 12, "ts_src": 1700000000123}
_KNOWN_SIG_HEX = (
    "85a16ba3534947a674735f737263cf0000018bcfe5687ba37365710ca3736967"
    "aa6c6566745f7061775f78a176cb3fe6666666666666"
)


def selfcheck():
    """Pack the known SIG frame and compare against the frozen expected hex. Raises
    MicsLinkError naming msgpack_numpy.patch() as the likely cause, plus the observed vs
    expected hex, on any mismatch. Returns True on success.
    """
    observed = wire.sig_frame(
        _KNOWN_SIG_FIELDS["sig"],
        _KNOWN_SIG_FIELDS["v"],
        seq=_KNOWN_SIG_FIELDS["seq"],
        ts_ms=_KNOWN_SIG_FIELDS["ts_src"],
    )
    expected = bytes.fromhex(_KNOWN_SIG_HEX)
    if observed != expected:
        raise MicsLinkError(
            "mics_link.selfcheck: wire codec produced unexpected bytes for a known frame. "
            "This usually means msgpack_numpy.patch() (or something else) has reassigned "
            "msgpack.packb/unpackb globally somewhere in this process - msgpack-numpy is "
            "common in scientific Python environments and does exactly this. "
            "observed={} expected={}".format(observed.hex(), expected.hex())
        )
    return True


def main():
    try:
        selfcheck()
    except MicsLinkError as exc:
        print("FAIL: {}".format(exc), file=sys.stderr)
        sys.exit(1)
    print("OK")


if __name__ == "__main__":
    main()
