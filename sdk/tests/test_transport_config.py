"""Transport seam, identity lock, and configuration validation (Phase 34, Plan 02, Task 2).

Proves SDK-03 (identity fixed at construction, no mutator, router_bind-only) and the
`Transport` seam contract entirely offline — `ZmqTransport` here is always constructed with
an injected `socket_factory`, never a real zmq socket.
"""
import os
import subprocess
import sys

import pytest

from fake_transport import FakeSocket, FakeTransport, fake_socket_factory
from mics_link.errors import MicsLinkError
from mics_link.transport import (
    MONITOR_CONNECTED,
    MONITOR_DISCONNECTED,
    MONITOR_RETRIED,
    Transport,
    ZmqTransport,
    endpoint,
    validate_target,
)


# --- endpoint ---


def test_endpoint_formats_tcp_url():
    assert endpoint("132.77.72.28", 5599) == "tcp://132.77.72.28:5599"


# --- validate_target ---


@pytest.mark.parametrize(
    "host,port,source_id",
    [
        ("h", 5599, ""),
        ("h", 5599, "   "),
        ("h", 5599, None),
        ("h", 5599, 123),
        ("h", 0, "demo"),
        ("h", 70000, "demo"),
        ("h", "5599", "demo"),
        ("", 5599, "demo"),
    ],
)
def test_validate_target_rejects_bad_input(host, port, source_id):
    with pytest.raises(MicsLinkError):
        validate_target(host, port, source_id)


def test_validate_target_accepts_valid_triple():
    assert validate_target("132.77.72.28", 5599, "demo") is None


# --- ZmqTransport construction order + identity lock ---


def test_zmq_transport_calls_socket_setsockopt_connect_in_order():
    fake_socket = FakeSocket()
    factory = fake_socket_factory(fake_socket)
    ZmqTransport("132.77.72.28", 5599, "demo", socket_factory=factory)

    assert fake_socket.calls == [
        ("socket", "DEALER"),
        ("setsockopt", "IDENTITY", b"demo"),
        ("connect", "tcp://132.77.72.28:5599"),
    ]


def test_zmq_transport_source_id_property_matches_construction():
    fake_socket = FakeSocket()
    factory = fake_socket_factory(fake_socket)
    transport = ZmqTransport("132.77.72.28", 5599, "demo", socket_factory=factory)

    assert transport.source_id == "demo"


def test_zmq_transport_source_id_has_no_public_setter():
    fake_socket = FakeSocket()
    factory = fake_socket_factory(fake_socket)
    transport = ZmqTransport("132.77.72.28", 5599, "demo", socket_factory=factory)

    with pytest.raises(AttributeError):
        transport.source_id = "other"


def test_zmq_transport_does_not_expose_raw_socket_publicly():
    """The only reference to the raw socket must be underscored/name-mangled — a public
    attribute holding it would re-invite `setsockopt(IDENTITY, ...)` from outside."""
    fake_socket = FakeSocket()
    factory = fake_socket_factory(fake_socket)
    transport = ZmqTransport("132.77.72.28", 5599, "demo", socket_factory=factory)

    public_attrs = [name for name in vars(transport) if not name.startswith("_")]
    for name in public_attrs:
        assert getattr(transport, name) is not fake_socket, (
            "public attribute {!r} exposes the raw socket".format(name)
        )


def test_zmq_transport_rejects_bad_target_before_socket_factory_runs():
    calls = []

    def factory(context, host, port, source_id):
        calls.append("called")
        return FakeSocket()

    with pytest.raises(MicsLinkError):
        ZmqTransport("h", 70000, "demo", socket_factory=factory)
    assert calls == []


# --- Transport seam satisfied by FakeTransport ---


def test_fake_transport_send_appends_to_sent():
    transport = FakeTransport()
    transport.send(b"frame1")
    transport.send(b"frame2")
    assert transport.sent == [b"frame1", b"frame2"]


def test_fake_transport_poll_returns_and_clears_inbound():
    transport = FakeTransport()
    transport.inbound = [b"a", b"b"]
    assert transport.poll(100) == [b"a", b"b"]
    assert transport.poll(100) == []


def test_fake_transport_events_returns_and_clears_pending_events():
    transport = FakeTransport()
    transport.pending_events = [MONITOR_CONNECTED]
    assert transport.events() == [MONITOR_CONNECTED]
    assert transport.events() == []


def test_fake_transport_close_sets_closed_true():
    transport = FakeTransport()
    assert transport.closed is False
    transport.close()
    assert transport.closed is True


def test_fake_transport_fail_next_raises_once_on_send():
    transport = FakeTransport()
    transport.fail_next = True
    with pytest.raises(RuntimeError):
        transport.send(b"frame")
    # fail_next is consumed — the next send succeeds normally
    transport.send(b"frame")
    assert transport.sent == [b"frame"]


def test_transport_base_class_methods_raise_not_implemented():
    base = Transport()
    with pytest.raises(NotImplementedError):
        base.send(b"x")
    with pytest.raises(NotImplementedError):
        base.poll(10)
    with pytest.raises(NotImplementedError):
        base.events()
    with pytest.raises(NotImplementedError):
        base.close()
    with pytest.raises(NotImplementedError):
        base.source_id  # noqa: B018 - property access is the point of the assertion


def test_monitor_constants_are_distinct_strings():
    assert len({MONITOR_CONNECTED, MONITOR_DISCONNECTED, MONITOR_RETRIED}) == 3


# --- import hygiene: mics_link.transport imports without zmq installed ---


def test_transport_module_importable_with_zmq_unavailable():
    script = (
        "import sys\n"
        "class _BlockZmq:\n"
        "    def find_module(self, name, path=None):\n"
        "        if name == 'zmq' or name.startswith('zmq.'):\n"
        "            raise ImportError('zmq blocked for hygiene test')\n"
        "        return None\n"
        "sys.meta_path.insert(0, _BlockZmq())\n"
        "import mics_link.transport\n"
        "print('OK')\n"
    )
    src_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "src"))
    result = subprocess.run(
        [sys.executable, "-c", script],
        cwd=src_dir,
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, result.stderr
    assert "OK" in result.stdout
