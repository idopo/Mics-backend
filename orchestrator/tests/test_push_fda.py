"""Tests for push_hot_reload() and UPDATE_FDA ZMQ message delivery."""
from unittest.mock import MagicMock
import pytest


def test_push_hot_reload_calls_gateway_send():
    from orchestrator.orchestrator_station import OrchestratorStation

    station = object.__new__(OrchestratorStation)
    station.state = MagicMock()
    station.state.resolve_pilot_key.return_value = "T"
    station.gateway = MagicMock()

    station.push_hot_reload("T", {"states": {"iti": {}}})

    station.gateway.send.assert_called_once_with("T", "UPDATE_FDA", {"states": {"iti": {}}})


def test_push_hot_reload_raises_when_pilot_not_found():
    from orchestrator.orchestrator_station import OrchestratorStation

    station = object.__new__(OrchestratorStation)
    station.state = MagicMock()
    # resolve_pilot_key raises KeyError when pilot not in state
    station.state.resolve_pilot_key.side_effect = KeyError("not found")
    station.gateway = MagicMock()

    with pytest.raises(ValueError, match="not found"):
        station.push_hot_reload("unknown_pilot", {})
