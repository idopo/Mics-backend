"""mics-link — a socket-free-to-import client SDK for streaming signals and events from a
researcher's own process (e.g. a DeepLabCut-Live inference loop) to a MICS pilot over ZMQ.

Everything a README-only reader's ``from mics_link import ...`` needs is re-exported here,
and nothing else is — every name below is documented in ``sdk/README.md`` (plan 34-08).

    from mics_link import connect

    with connect(pilot_host, pilot_port, "demo") as link:
        for frame in my_existing_camera_loop():
            link.send_signal("left_paw_x", frame.x)

``as_scalar`` (``mics_link.values.as_scalar``) is deliberately NOT re-exported here even
though an earlier plan's amendment suggested it should be — a researcher who needs it can
still ``from mics_link.values import as_scalar``.

``Pacer`` (``mics_link.timing.Pacer``) IS re-exported (plan 34-07's "DLC-Live and Windows"
amendment, dated after 34-06 locked ``__all__`` to six names — this is that lock's one
documented, amendment-mandated addition): Phase 35's video frame loop needs the exact same
origin-relative scheduler ``replay()`` uses, rather than a second implementation.
"""
from .client import MicsLink
from .errors import InvalidValueError, MicsLinkError
from .timing import Pacer

# Aliased on import (not `from .selfcheck import selfcheck`): binding the plain name
# `selfcheck` at package-root scope would overwrite the `mics_link.selfcheck` SUBMODULE
# reference that importing it sets up, breaking `from mics_link import selfcheck as
# selfcheck_module` in tests/test_selfcheck.py (34-01) — `selfcheck` isn't part of this
# plan's public surface anyway (not in `__all__`).
from .selfcheck import selfcheck as _run_selfcheck
from .sender import SenderStats
from .transport import ZmqTransport, validate_target

__version__ = "0.1.0"

__all__ = [
    "connect",
    "MicsLink",
    "MicsLinkError",
    "InvalidValueError",
    "SenderStats",
    "Pacer",
    "__version__",
]


def connect(host, port, source_id, **kwargs):
    """Validate ``(host, port, source_id)``, run `mics_link.selfcheck` (detects a globally
    msgpack-numpy-patched process before it silently corrupts every frame), build a
    `ZmqTransport`, and return a connected `MicsLink`. Any extra keyword argument is passed
    straight through to `MicsLink.__init__` (``heartbeat_s``, ``on_state_change``, ...).

    Validation runs BEFORE any socket is created — a bad host/port/source_id raises
    `MicsLinkError` without ever touching zmq.

    IMPORTANT: the ``on_state_change`` callback's ``True`` argument does NOT mean the Pi is
    accepting your identity — it means only that the DEALER's TCP-level connection to the
    Pi's ROUTER is up. ROUTER-level identity acceptance is a separate layer this SDK cannot
    observe from the sender side: a mismatched ``source_id`` is dropped by the Pi with no
    NAK (EXTLINK-02).
    """
    validate_target(host, port, source_id)
    _run_selfcheck()
    transport = ZmqTransport(host, port, source_id)
    return MicsLink(transport, **kwargs)
