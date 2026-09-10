"""Tests for `dlc_link.pilot_state` -- run identity from the orchestrator, FDA state
from ElasticSearch, both fail-soft (D-57, Task 2, plan 38-02).

`FakeOpener` records the URL, the body and the timeout it was given, and returns
queued canned payloads -- no real network call is ever made.
"""
import json

import pytest

from dlc_link.pilot_state import (
    RunIdentity,
    StateReading,
    fetch_fda_state,
    fetch_run_identity,
    parse_pilots_live,
    parse_state_transition,
)


class FakeOpener:
    """Callable `opener(url, data, timeout)` that records every call and returns
    queued responses in order. `raises` (if set) is raised instead of returning."""

    def __init__(self, responses=None, raises=None):
        self._responses = list(responses or [])
        self._raises = raises
        self.calls = []

    def __call__(self, url, data, timeout):
        self.calls.append({"url": url, "data": data, "timeout": timeout})
        if self._raises is not None:
            raise self._raises
        return self._responses.pop(0)


PILOTS_LIVE_PAYLOAD = {
    "RecordingBox": {
        "connected": True,
        "state": "RUNNING",
        "active_run": {
            "id": 588,
            "session_id": 231,
            "subject_key": "bp_s231_r588",
            "task_def_id": 626,
        },
        "updated_at": "2026-09-02T12:00:00+00:00",
    }
}


class TestParsePilotsLive:
    def test_returns_run_identity_with_all_fields(self):
        identity = parse_pilots_live(PILOTS_LIVE_PAYLOAD, "RecordingBox")
        assert identity.available is True
        assert identity.connected is True
        assert identity.coarse_state == "RUNNING"
        assert identity.run_id == 588
        assert identity.session_id == 231
        assert identity.subject_key == "bp_s231_r588"

    def test_pilot_absent_from_payload_is_unavailable_naming_the_pilot(self):
        identity = parse_pilots_live(PILOTS_LIVE_PAYLOAD, "GhostPilot")
        assert identity.available is False
        assert "GhostPilot" in identity.reason

    def test_active_run_null_is_available_but_idle(self):
        payload = {"RecordingBox": {"connected": True, "state": "IDLE", "active_run": None}}
        identity = parse_pilots_live(payload, "RecordingBox")
        assert identity.available is True
        assert identity.run_id is None
        assert "no active run" in identity.reason

    def test_non_dict_payload_is_unavailable_not_raised(self):
        identity = parse_pilots_live("not a dict", "RecordingBox")
        assert identity.available is False

    def test_non_dict_entry_is_unavailable_not_raised(self):
        identity = parse_pilots_live({"RecordingBox": "garbage"}, "RecordingBox")
        assert identity.available is False

    def test_non_dict_active_run_is_unavailable_not_raised(self):
        payload = {"RecordingBox": {"connected": True, "state": "RUNNING", "active_run": "garbage"}}
        identity = parse_pilots_live(payload, "RecordingBox")
        assert identity.available is False


STATE_TRANSITION_RESPONSE = {
    "hits": {
        "hits": [
            {"_source": {"event_data": {"current_state": "WAITING_POKE"}}},
        ]
    }
}


class TestParseStateTransition:
    def test_returns_current_state_of_first_hit(self):
        reading = parse_state_transition(STATE_TRANSITION_RESPONSE)
        assert reading.available is True
        assert reading.state == "WAITING_POKE"

    def test_empty_hits_is_unavailable(self):
        reading = parse_state_transition({"hits": {"hits": []}})
        assert reading.available is False
        assert "no state_transition document" in reading.reason

    def test_missing_current_state_is_unavailable_quoting_keys_found(self):
        response = {"hits": {"hits": [{"_source": {"event_data": {"something_else": 1}}}]}}
        reading = parse_state_transition(response)
        assert reading.available is False
        assert "something_else" in reading.reason

    def test_malformed_response_is_unavailable_not_raised(self):
        reading = parse_state_transition({"not": "the expected shape"})
        assert reading.available is False


class TestFetchRunIdentity:
    def test_opener_raising_returns_unavailable_with_exception_text(self):
        opener = FakeOpener(raises=OSError("connection refused"))
        identity = fetch_run_identity("http://orch:9000", "RecordingBox", opener=opener)
        assert isinstance(identity, RunIdentity)
        assert identity.available is False
        assert "connection refused" in identity.reason

    def test_opener_returning_non_json_returns_unavailable_naming_parse_failure(self):
        opener = FakeOpener(responses=[b"not json at all {{{"])
        identity = fetch_run_identity("http://orch:9000", "RecordingBox", opener=opener)
        assert identity.available is False
        assert "JSON" in identity.reason or "Decode" in identity.reason

    def test_well_formed_payload_missing_pilot_returns_unavailable(self):
        opener = FakeOpener(responses=[json.dumps(PILOTS_LIVE_PAYLOAD).encode()])
        identity = fetch_run_identity("http://orch:9000", "GhostPilot", opener=opener)
        assert identity.available is False
        assert "GhostPilot" in identity.reason

    def test_happy_path_parses_through(self):
        opener = FakeOpener(responses=[json.dumps(PILOTS_LIVE_PAYLOAD).encode()])
        identity = fetch_run_identity("http://orch:9000", "RecordingBox", opener=opener)
        assert identity.available is True
        assert identity.subject_key == "bp_s231_r588"

    def test_passes_non_none_timeout_to_opener(self):
        opener = FakeOpener(responses=[json.dumps(PILOTS_LIVE_PAYLOAD).encode()])
        fetch_run_identity("http://orch:9000", "RecordingBox", timeout_s=3.5, opener=opener)
        assert opener.calls[0]["timeout"] == 3.5
        assert opener.calls[0]["timeout"] is not None

    def test_url_is_pilots_live_under_base_url(self):
        opener = FakeOpener(responses=[json.dumps(PILOTS_LIVE_PAYLOAD).encode()])
        fetch_run_identity("http://orch:9000", "RecordingBox", opener=opener)
        assert opener.calls[0]["url"] == "http://orch:9000/pilots/live"


class TestFetchFdaState:
    def test_opener_raising_returns_unavailable_with_exception_text(self):
        opener = FakeOpener(raises=OSError("timed out"))
        reading = fetch_fda_state("http://es:9200", "event_log_v2", "bp_s231_r588", opener=opener)
        assert isinstance(reading, StateReading)
        assert reading.available is False
        assert "timed out" in reading.reason

    def test_opener_returning_non_json_returns_unavailable_naming_parse_failure(self):
        opener = FakeOpener(responses=[b"{not json"])
        reading = fetch_fda_state("http://es:9200", "event_log_v2", "bp_s231_r588", opener=opener)
        assert reading.available is False

    def test_happy_path_parses_through(self):
        opener = FakeOpener(responses=[json.dumps(STATE_TRANSITION_RESPONSE).encode()])
        reading = fetch_fda_state("http://es:9200", "event_log_v2", "bp_s231_r588", opener=opener)
        assert reading.available is True
        assert reading.state == "WAITING_POKE"

    def test_passes_non_none_timeout_to_opener(self):
        opener = FakeOpener(responses=[json.dumps(STATE_TRANSITION_RESPONSE).encode()])
        fetch_fda_state("http://es:9200", "event_log_v2", "bp_s231_r588", timeout_s=1.5, opener=opener)
        assert opener.calls[0]["timeout"] == 1.5
        assert opener.calls[0]["timeout"] is not None

    def test_search_body_contains_state_transition_filter_and_exact_subject_key(self):
        opener = FakeOpener(responses=[json.dumps(STATE_TRANSITION_RESPONSE).encode()])
        fetch_fda_state("http://es:9200", "event_log_v2", "bp_s231_r588", opener=opener)
        body = json.loads(opener.calls[0]["data"])
        filters = body["query"]["bool"]["filter"]
        assert {"term": {"event_type": "state_transition"}} in filters
        assert {"term": {"subject": "bp_s231_r588"}} in filters

    def test_url_is_index_search_under_es_url(self):
        opener = FakeOpener(responses=[json.dumps(STATE_TRANSITION_RESPONSE).encode()])
        fetch_fda_state("http://es:9200", "event_log_v2", "bp_s231_r588", opener=opener)
        assert opener.calls[0]["url"] == "http://es:9200/event_log_v2/_search"


class TestStateReadingRender:
    def test_available_renders_fda_state_with_name(self):
        reading = StateReading(available=True, reason="", state="WAITING_POKE")
        assert reading.render() == "FDA state: WAITING_POKE"

    def test_unavailable_renders_unavailable_with_reason(self):
        reading = StateReading(available=False, reason="no state_transition document was found")
        rendered = reading.render()
        assert "unavailable" in rendered
        assert "no state_transition document was found" in rendered


def test_module_has_no_third_party_imports():
    import dlc_link.pilot_state as module

    with open(module.__file__) as f:
        source = f.read()
    for forbidden in ("import cv2", "import numpy", "import requests"):
        assert forbidden not in source
