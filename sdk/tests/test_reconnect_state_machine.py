"""RED-phase tests for `mics_link.reconnect` — pure connect/disconnect state machine
over synthetic monitor events. No zmq socket, no monitor thread, no clock: `next_state`
and `ConnectionState.apply` are exercised with plain string events only.
"""
import logging

from mics_link.reconnect import (
    MONITOR_CONNECTED,
    MONITOR_DISCONNECTED,
    MONITOR_RETRIED,
    STATE_CONNECTED,
    STATE_DISCONNECTED,
    ConnectionState,
    next_state,
)


def test_disconnected_plus_connected_event_yields_connected():
    assert next_state(STATE_DISCONNECTED, MONITOR_CONNECTED) == STATE_CONNECTED


def test_connected_plus_disconnected_event_yields_disconnected():
    assert next_state(STATE_CONNECTED, MONITOR_DISCONNECTED) == STATE_DISCONNECTED


def test_connected_plus_connected_event_is_idempotent():
    assert next_state(STATE_CONNECTED, MONITOR_CONNECTED) == STATE_CONNECTED


def test_retried_event_never_changes_state():
    """Decision 4: MONITOR_RETRIED is libzmq's per-attempt backoff signal, not an edge."""
    assert next_state(STATE_CONNECTED, MONITOR_RETRIED) == STATE_CONNECTED
    assert next_state(STATE_DISCONNECTED, MONITOR_RETRIED) == STATE_DISCONNECTED


def test_unknown_event_leaves_state_unchanged():
    assert next_state(STATE_CONNECTED, "some_unmapped_event") == STATE_CONNECTED
    assert next_state(STATE_DISCONNECTED, "some_unmapped_event") == STATE_DISCONNECTED


def test_connection_state_starts_disconnected():
    cs = ConnectionState()
    assert cs.state == STATE_DISCONNECTED
    assert cs.connected is False


def test_apply_all_produces_exactly_three_edge_callbacks():
    """The full Pi-restart story in one assertion: connect, stay connected through a
    retry storm, drop, retry again, then reconnect — exactly 3 real edges."""
    calls = []
    cs = ConnectionState(on_state_change=calls.append)
    events = [
        MONITOR_CONNECTED,
        MONITOR_CONNECTED,
        MONITOR_RETRIED,
        MONITOR_DISCONNECTED,
        MONITOR_RETRIED,
        MONITOR_RETRIED,
        MONITOR_CONNECTED,
    ]
    cs.apply_all(events)
    assert calls == [True, False, True]


def test_apply_returns_true_only_on_edges():
    cs = ConnectionState()
    assert cs.apply(MONITOR_CONNECTED) is True
    assert cs.apply(MONITOR_CONNECTED) is False
    assert cs.apply(MONITOR_RETRIED) is False
    assert cs.apply(MONITOR_DISCONNECTED) is True
    assert cs.apply(MONITOR_RETRIED) is False


def test_none_callback_is_safe():
    cs = ConnectionState(on_state_change=None)
    cs.apply_all([
        MONITOR_CONNECTED,
        MONITOR_CONNECTED,
        MONITOR_RETRIED,
        MONITOR_DISCONNECTED,
        MONITOR_RETRIED,
        MONITOR_RETRIED,
        MONITOR_CONNECTED,
    ])
    assert cs.state == STATE_CONNECTED


def test_raising_callback_does_not_propagate_and_state_still_advances(caplog):
    def bad_callback(connected):
        raise RuntimeError("boom")

    cs = ConnectionState(on_state_change=bad_callback)
    with caplog.at_level(logging.WARNING):
        edge = cs.apply(MONITOR_CONNECTED)  # must not raise
    assert edge is True
    assert cs.state == STATE_CONNECTED
    assert any(record.levelno == logging.WARNING for record in caplog.records)


def test_retries_counter_counts_retried_events_and_does_not_affect_state():
    cs = ConnectionState()
    cs.apply_all([MONITOR_RETRIED, MONITOR_RETRIED, MONITOR_CONNECTED, MONITOR_RETRIED])
    assert cs.retries == 3
    assert cs.state == STATE_CONNECTED


def test_module_never_references_a_sequence_counter():
    """Decision 6: reconnect.py must not touch, own, or reference `seq` at all — the only
    place the literal token `seq` may appear is inside the decision-6 comment near `apply`."""
    import inspect

    import mics_link.reconnect as reconnect_module

    source = inspect.getsource(reconnect_module)
    lines_with_seq = [line for line in source.splitlines() if "seq" in line]
    for line in lines_with_seq:
        stripped = line.strip()
        assert stripped.startswith("#") or stripped.startswith('"""') or '"""' in line or "'" in line, (
            "Found non-comment reference to seq in reconnect.py: %r" % line
        )
