from pathlib import Path

import pytest

from mics.config import SessionConfig, SESSIONS_ROOT, DEFAULTS
from mics.resolve import resolve_one, load_sessions, ResolvedSession

SHARE = Path(SESSIONS_ROOT)
needs_share = pytest.mark.skipif(not SHARE.exists(), reason="SMB share not mounted")


@needs_share
def test_resolve_m74s4_full():
    r = resolve_one(SessionConfig(key="m74s4", es_subject="m74_cue_reward", es_session=4))
    assert r.has_ephys
    assert r.record_node == "Record Node 110"
    assert r.has_spikes
    assert r.spike_kind == "pickle"
    assert r.spike_path.name == "spikes_m74s4.pkl"
    assert r.trigger_channel == DEFAULTS["trigger_channel"] == 17


@needs_share
def test_resolve_m74s1_inline_xls():
    r = resolve_one(SessionConfig(key="m74s1", es_subject="m74_cue_reward", es_session=1))
    assert r.has_ephys
    assert r.has_spikes
    assert r.spike_kind == "xls"
    assert r.spike_path.name == "processed.xls"


def test_resolve_events_only_no_ephys():
    # A key with no matching folder on the share resolves cleanly as events-only.
    r = resolve_one(SessionConfig(key="ghost_s99", es_subject="x", es_session=1))
    assert r.has_ephys is False
    assert r.has_spikes is False
    assert r.record_node is None
    assert "—" in r.summary()  # ephys shown as absent


@needs_share
def test_channel_override():
    r = resolve_one(
        SessionConfig(key="m74s4", es_subject="m74_cue_reward", es_session=4, trigger_channel=99)
    )
    assert r.trigger_channel == 99
    assert r.ttl_channel == DEFAULTS["ttl_channel"]  # untouched default


@needs_share
def test_summary_single_line():
    sessions = load_sessions(
        [SessionConfig(key="m74s4", es_subject="m74_cue_reward", es_session=4)]
    )
    assert len(sessions) == 1
    s = sessions[0].summary()
    assert isinstance(s, str) and "\n" not in s and s.strip()
    assert "m74s4" in s and "m74_cue_reward" in s
