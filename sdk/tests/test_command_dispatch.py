"""Command-dispatch tests for mics_link.commands (Phase 34, Plan 04).

Every CMD frame here is built with the PI's real encoder, loaded via
``pi_reference.load_pi_wire(CANONICAL_PI_WIRE_PATH)`` — synthetic frames, but not
self-referential (the plan's own SDK-08 scope-honesty requirement: there is ZERO Pi-side
CMD-sender anywhere in either autopilot tree, so this is the only evidence that can exist
this phase). Skip-if-absent, same posture as ``test_wire_parity.py``.
"""
import threading

import pytest

from pi_reference import CANONICAL_PI_WIRE_PATH, load_pi_wire

from mics_link import wire
from mics_link.commands import ACK_ERROR, ACK_OK, CommandRegistry, CommandWorker, dispatch
from mics_link.selfcheck import MicsLinkError


def _pi_cmd(pi, cmd_id, name, args, ts_pi=1700000000500):
    """Build a CMD frame with the Pi's own encoder, then decode it with the SDK's own
    decode_cmd — exactly the boundary dispatch is fed across in plan 34-06's real wiring.
    """
    raw = pi.encode("CMD", ts_pi=ts_pi, cmd_id=cmd_id, name=name, args=args)
    return wire.decode_cmd(raw)


def _decode_ack(pi, ack_bytes):
    stats = pi.DecodeStats()
    envelope = pi.decode_envelope(ack_bytes, stats)
    return envelope, stats


# --- Task 1: registry + pure dispatch ---


def test_registered_handler_receives_args_and_dispatch_reaches_it():
    pi = load_pi_wire(CANONICAL_PI_WIRE_PATH)
    registry = CommandRegistry()
    received = {}

    def stop_handler(args):
        received["args"] = args
        return None

    registry.register("stop", stop_handler)
    cmd = _pi_cmd(pi, "cmd-001", "stop", {"reason": "user"})

    ack_bytes = dispatch(registry, cmd)

    assert received["args"] == {"reason": "user"}
    envelope, stats = _decode_ack(pi, ack_bytes)
    assert stats.malformed == 0
    assert envelope["k"] == "ACK"


@pytest.mark.parametrize("cmd_id", ["cmd-str-001", 42])
def test_success_ack_shape_and_cmd_id_round_trips(cmd_id):
    pi = load_pi_wire(CANONICAL_PI_WIRE_PATH)
    registry = CommandRegistry()
    registry.register("answer", lambda args: 42)
    cmd = _pi_cmd(pi, cmd_id, "answer", {})

    ack_bytes = dispatch(registry, cmd)

    envelope, stats = _decode_ack(pi, ack_bytes)
    assert stats.malformed == 0
    assert envelope["k"] == "ACK"
    assert isinstance(envelope["ts_src"], int)
    assert envelope["cmd_id"] == cmd_id
    assert envelope["result"] == {ACK_OK: True, "value": 42}


def test_ack_envelope_has_no_seq_key():
    pi = load_pi_wire(CANONICAL_PI_WIRE_PATH)
    registry = CommandRegistry()
    registry.register("noop", lambda args: None)
    cmd = _pi_cmd(pi, "cmd-noop", "noop", {})

    envelope, _stats = _decode_ack(pi, dispatch(registry, cmd))

    assert "seq" not in envelope


def test_handler_raising_yields_error_ack_and_dispatch_returns_normally():
    pi = load_pi_wire(CANONICAL_PI_WIRE_PATH)
    registry = CommandRegistry()

    def boom_handler(args):
        raise ValueError("boom")

    registry.register("boom", boom_handler)
    cmd = _pi_cmd(pi, "cmd-boom", "boom", {})

    ack_bytes = dispatch(registry, cmd)

    envelope, stats = _decode_ack(pi, ack_bytes)
    assert stats.malformed == 0
    assert envelope["result"] == {ACK_OK: False, ACK_ERROR: "ValueError: boom"}


def test_unregistered_command_yields_unknown_command_error():
    pi = load_pi_wire(CANONICAL_PI_WIRE_PATH)
    registry = CommandRegistry()
    cmd = _pi_cmd(pi, "cmd-nope", "nope", {})

    envelope, stats = _decode_ack(pi, dispatch(registry, cmd))

    assert stats.malformed == 0
    assert envelope["result"] == {ACK_OK: False, ACK_ERROR: "unknown command: nope"}


def test_unencodable_result_yields_valid_error_ack():
    pi = load_pi_wire(CANONICAL_PI_WIRE_PATH)
    registry = CommandRegistry()

    class _Unencodable(object):
        pass

    registry.register("bad_return", lambda args: _Unencodable())
    cmd = _pi_cmd(pi, "cmd-bad", "bad_return", {})

    ack_bytes = dispatch(registry, cmd)

    envelope, stats = _decode_ack(pi, ack_bytes)
    assert stats.malformed == 0
    assert envelope["result"][ACK_OK] is False
    assert envelope["result"][ACK_ERROR].startswith("unencodable result:")


def test_keyboard_interrupt_propagates_out_of_dispatch():
    pi = load_pi_wire(CANONICAL_PI_WIRE_PATH)
    registry = CommandRegistry()

    def interrupting_handler(args):
        raise KeyboardInterrupt()

    registry.register("interrupt", interrupting_handler)
    cmd = _pi_cmd(pi, "cmd-int", "interrupt", {})

    with pytest.raises(KeyboardInterrupt):
        dispatch(registry, cmd)


def test_duplicate_registration_raises_mics_link_error():
    registry = CommandRegistry()
    registry.register("dup", lambda args: None)
    with pytest.raises(MicsLinkError):
        registry.register("dup", lambda args: None)


def test_decorator_registers_and_returns_function_unchanged():
    registry = CommandRegistry()

    @registry.decorator("ping")
    def ping(args):
        return "pong"

    assert registry.get("ping") is ping
    assert "ping" in registry.names()


def test_decode_cmd_returns_none_for_non_cmd_frame():
    sig = wire.sig_frame("s", 1, seq=0)
    assert wire.decode_cmd(sig) is None


# --- Task 2: isolated command worker thread ---


def test_submit_returns_immediately_ack_appears_after_handler_unblocks():
    registry = CommandRegistry()
    release = threading.Event()

    def blocking_handler(args):
        release.wait(timeout=2.0)
        return "released"

    registry.register("block", blocking_handler)
    acks = []
    worker = CommandWorker(registry, acks.append)
    worker.start()
    try:
        pi = load_pi_wire(CANONICAL_PI_WIRE_PATH)
        cmd = _pi_cmd(pi, "cmd-block", "block", {})

        submitted = worker.submit(cmd)

        assert submitted is True
        assert acks == []  # handler still blocked, no ACK yet

        release.set()
        deadline = threading.Event()
        # Bounded wait for the ACK to land, no time.sleep polling loop.
        for _ in range(200):
            if acks:
                break
            deadline.wait(0.01)
        assert len(acks) == 1
    finally:
        worker.stop(timeout=2.0)


def test_handler_runs_on_dedicated_thread_not_submitter_or_io_thread():
    registry = CommandRegistry()
    recorded = {}
    done = threading.Event()

    def recording_handler(args):
        recorded["thread_name"] = threading.current_thread().name
        done.set()
        return None

    registry.register("whoami", recording_handler)
    worker = CommandWorker(registry, lambda ack: True, thread_factory=threading.Thread)
    worker.start()
    try:
        pi = load_pi_wire(CANONICAL_PI_WIRE_PATH)
        cmd = _pi_cmd(pi, "cmd-whoami", "whoami", {})
        submitter_name = threading.current_thread().name

        worker.submit(cmd)
        assert done.wait(timeout=2.0)

        assert recorded["thread_name"] != submitter_name
    finally:
        worker.stop(timeout=2.0)


def test_raising_handler_does_not_kill_worker_subsequent_commands_still_ack():
    registry = CommandRegistry()

    def boom_handler(args):
        raise RuntimeError("kaboom")

    def ok_handler(args):
        return "fine"

    registry.register("boom", boom_handler)
    registry.register("ok", ok_handler)
    acks = []
    ack_event = threading.Event()

    def sink(ack_bytes):
        acks.append(ack_bytes)
        if len(acks) >= 2:
            ack_event.set()
        return True

    worker = CommandWorker(registry, sink)
    worker.start()
    try:
        pi = load_pi_wire(CANONICAL_PI_WIRE_PATH)
        worker.submit(_pi_cmd(pi, "cmd-boom2", "boom", {}))
        worker.submit(_pi_cmd(pi, "cmd-ok2", "ok", {}))

        assert ack_event.wait(timeout=2.0)
        assert len(acks) == 2
    finally:
        worker.stop(timeout=2.0)


def test_submit_on_full_inbox_returns_false_and_increments_dropped():
    registry = CommandRegistry()
    registry.register("noop", lambda args: None)
    worker = CommandWorker(registry, lambda ack: True, maxsize=2)
    # Worker deliberately not started: the inbox fills without anything draining it.
    pi = load_pi_wire(CANONICAL_PI_WIRE_PATH)
    cmd = _pi_cmd(pi, "cmd-full", "noop", {})

    assert worker.submit(cmd) is True
    assert worker.submit(cmd) is True
    assert worker.submit(cmd) is False

    assert worker.dropped == 1


def test_stop_joins_thread_and_is_idempotent():
    registry = CommandRegistry()
    registry.register("noop", lambda args: None)
    worker = CommandWorker(registry, lambda ack: True)
    worker.start()

    worker.stop(timeout=2.0)
    worker.stop(timeout=2.0)  # second stop() is a no-op, must not raise


def test_stop_on_never_started_worker_does_not_raise():
    registry = CommandRegistry()
    worker = CommandWorker(registry, lambda ack: True)
    worker.stop(timeout=1.0)


def test_ack_sink_returning_false_does_not_raise_or_kill_worker():
    registry = CommandRegistry()
    registry.register("noop", lambda args: None)
    processed = threading.Event()
    calls = []

    def failing_sink(ack_bytes):
        calls.append(ack_bytes)
        processed.set()
        return False

    worker = CommandWorker(registry, failing_sink)
    worker.start()
    try:
        pi = load_pi_wire(CANONICAL_PI_WIRE_PATH)
        cmd = _pi_cmd(pi, "cmd-sinkfail", "noop", {})
        worker.submit(cmd)
        assert processed.wait(timeout=2.0)
        assert len(calls) == 1
    finally:
        worker.stop(timeout=2.0)
