"""Tests for mics_link.selfcheck (SDK-02 as amended, added per 34-01-PLAN.md amendment).

Not in this plan's original files_modified list — added as a Rule 2 deviation because the
amendment explicitly assigns this artifact to Task 1/2's scope and no later plan in the
phase claims it (checked 34-02 through 34-09).
"""
import msgpack

from golden_frames import GOLDEN_FRAMES

from mics_link import selfcheck as selfcheck_module
from mics_link.selfcheck import MicsLinkError, selfcheck


def test_known_frame_constant_matches_frozen_golden_corpus():
    # Deliberately duplicated data (selfcheck.py must be self-contained inside the
    # installed package, which does not ship tests/). This test is what keeps the two
    # copies from drifting silently.
    golden_sig = GOLDEN_FRAMES[0]
    assert golden_sig["kind"] == "SIG"
    fields = dict(golden_sig["fields"])
    assert selfcheck_module._KNOWN_SIG_FIELDS == {
        "sig": fields["sig"],
        "v": fields["v"],
        "seq": fields["seq"],
        "ts_src": fields["ts_src"],
    }
    assert selfcheck_module._KNOWN_SIG_HEX == golden_sig["hex"]


def test_selfcheck_passes_with_unpatched_msgpack():
    assert selfcheck() is True


def test_selfcheck_raises_and_names_culprit_when_msgpack_is_patched(monkeypatch):
    def fake_numpy_style_packb(obj, **kwargs):
        # Simulates msgpack_numpy.patch()'s effect: same call signature, different bytes.
        return b"\x00not-the-real-encoding"

    monkeypatch.setattr(msgpack, "packb", fake_numpy_style_packb)
    try:
        selfcheck()
        assert False, "expected MicsLinkError"
    except MicsLinkError as exc:
        assert "msgpack_numpy.patch()" in str(exc)
