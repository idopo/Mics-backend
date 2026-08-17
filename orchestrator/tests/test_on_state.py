"""Tests for on_state() persisting the state the pilot reports.

Before this, on_state() only refreshed updated_at and discarded msg.value, so
/pilots/live fell back to its "UNKNOWN" default for any pilot that had never
started a run, and _wait_for_idle() could never observe IDLE.
"""
from types import SimpleNamespace
from unittest.mock import MagicMock


def _station(redis=None):
    from orchestrator.orchestrator_station import OrchestratorStation

    station = object.__new__(OrchestratorStation)
    station.state = MagicMock()
    station.redis = MagicMock() if redis is None else redis
    return station


def _msg(sender, value):
    return SimpleNamespace(sender=sender, value=value)


def test_on_state_persists_string_state_to_redis():
    station = _station()

    station.on_state(_msg("RecordingBox", "IDLE"))

    station.redis.hset.assert_any_call("pilot:RecordingBox", "state", "IDLE")


def test_on_state_updates_in_memory_state_for_wait_for_idle():
    station = _station()

    station.on_state(_msg("RecordingBox", "IDLE"))

    station.state.set_state.assert_called_once_with("RecordingBox", "IDLE")


def test_on_state_accepts_dict_payload():
    """Older pilots push a bare string; a dict payload must work too."""
    station = _station()

    station.on_state(_msg("RecordingBox", {"state": "RUNNING"}))

    station.redis.hset.assert_any_call("pilot:RecordingBox", "state", "RUNNING")
    station.state.set_state.assert_called_once_with("RecordingBox", "RUNNING")


def test_on_state_still_refreshes_updated_at():
    station = _station()

    station.on_state(_msg("RecordingBox", "IDLE"))

    keys = [c.args[0] for c in station.redis.hset.call_args_list]
    assert "pilot:RecordingBox" in keys
    mappings = [c.kwargs.get("mapping", {}) for c in station.redis.hset.call_args_list]
    assert any("updated_at" in m for m in mappings)


def test_on_state_ignores_empty_payload():
    """An empty STATE must not overwrite a known state with nothing."""
    station = _station()

    station.on_state(_msg("RecordingBox", None))

    station.state.set_state.assert_not_called()
    for call in station.redis.hset.call_args_list:
        assert "state" not in call.args
        assert "state" not in call.kwargs.get("mapping", {})


def test_on_state_survives_redis_not_configured():
    station = _station(redis=None)
    station.redis = None

    station.on_state(_msg("RecordingBox", "IDLE"))

    station.state.set_state.assert_called_once_with("RecordingBox", "IDLE")
