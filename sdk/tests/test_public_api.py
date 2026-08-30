"""`mics_link`'s public API surface — the file a README-only reader's `from mics_link
import ...` resolves against (Phase 34, Plan 06, Task 3). Entirely socketless: `connect()`'s
own validation must run and raise BEFORE any transport/socket is constructed.

Not named in 34-06-PLAN.md's `files_modified` (only `test_zmq_loopback.py` is) — Task 3's
own `<behavior>` block describes both a socketless half and the real-socket loopback half,
and the socketless half needs its own module. Documented as a deviation in the plan
SUMMARY.
"""
import inspect

import pytest

import mics_link
from mics_link.commands import CommandRegistry, dispatch


def test_public_names_import_from_the_package_root():
    from mics_link import (  # noqa: F401
        InvalidValueError,
        MicsLink,
        MicsLinkError,
        SenderStats,
        connect,
    )


def test_all_contains_exactly_the_documented_names_plus_version():
    assert set(mics_link.__all__) == {
        "connect",
        "MicsLink",
        "MicsLinkError",
        "InvalidValueError",
        "SenderStats",
        "__version__",
    }


def test_connect_validates_target_before_any_socket_exists():
    """A bad port must raise from validate_target — before a ZmqTransport (and therefore a
    socket) is ever constructed. Proven by blocking zmq's import: if connect() tried to
    build a transport first, the failure mode would be an ImportError, not MicsLinkError.
    """
    import sys

    class _BlockZmq:
        def find_module(self, name, path=None):
            if name == "zmq" or name.startswith("zmq."):
                raise ImportError("zmq blocked for this test")
            return None

    finder = _BlockZmq()
    sys.meta_path.insert(0, finder)
    try:
        with pytest.raises(mics_link.MicsLinkError):
            mics_link.connect("h", 0, "demo")
    finally:
        sys.meta_path.remove(finder)


def test_connect_signature_accepts_host_port_source_id_and_kwargs():
    sig = inspect.signature(mics_link.connect)
    params = list(sig.parameters.values())
    assert [p.name for p in params[:3]] == ["host", "port", "source_id"]
    assert any(p.kind == inspect.Parameter.VAR_KEYWORD for p in params)


def test_connect_docstring_states_the_identity_acceptance_caveat():
    doc = mics_link.connect.__doc__
    assert "does NOT mean" in doc
    assert "identity" in doc


# --- 34-06 mandatory merge reconciliation: exactly one MicsLinkError ---


def test_every_raised_error_is_the_single_package_root_mics_link_error():
    """commands.py, transport.py and selfcheck.py used to define (or import) two
    UNRELATED MicsLinkError classes — commands.py from .selfcheck, transport.py from
    .errors — so `except mics_link.MicsLinkError` only ever caught half the failures.
    Proves the fix: an error raised by each of the three modules is an instance of the
    ONE class exported from the package root.
    """
    registry = CommandRegistry()
    try:
        registry.register("dup", lambda args: None)
        registry.register("dup", lambda args: None)
        assert False, "expected mics_link.MicsLinkError"
    except mics_link.MicsLinkError:
        pass

    from mics_link.transport import validate_target

    try:
        validate_target("h", 0, "demo")
        assert False, "expected mics_link.MicsLinkError"
    except mics_link.MicsLinkError:
        pass

    from mics_link.selfcheck import selfcheck

    import mics_link.wire as wire_module

    original_encode = wire_module.encode
    wire_module.encode = lambda *a, **k: b"corrupted"
    try:
        selfcheck()
        assert False, "expected mics_link.MicsLinkError"
    except mics_link.MicsLinkError:
        pass
    finally:
        wire_module.encode = original_encode

    # dispatch() itself never raises MicsLinkError (decision 2 of 34-04) — the unification
    # is about the TYPE existing in one place, which the three raises above already prove.
    assert dispatch is not None
