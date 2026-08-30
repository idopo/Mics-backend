"""Standalone Windows-install smoke test for mics-link (Phase 34, Plan 09 addition).

Proves a fresh `mics_link` install actually works the moment the wheel is installed --
NO Pi, NO rig, NO network peer required except this process's own loopback. Run it right
after `python -m pip install <wheel-or-git-url>` (sdk/README.md section 2) to catch a
broken interpreter, a msgpack-numpy patch, or a dead pyzmq before ever touching the rig:

    python windows_smoke.py

Exits 0 if every step PASSes, non-zero otherwise, with a final summary line. Ships OUTSIDE
the installed package, like ten_line_sender.py / callback_sender.py (`pyproject.toml`'s
`packages.find` only packages `src/mics_link`) -- copied from the repo alongside the
install instructions, not `pip install`-ed itself.

Windows-specific rules this file follows throughout (SDK-14), all load-bearing, not
stylistic: ASCII-only output (a box-drawing char, emoji or arrow raises UnicodeEncodeError
on a legacy console codepage and kills the report mid-run); no file opened here at all,
and if a future edit adds one it MUST use encoding="utf-8", newline=""; no
os.fork/signal.SIGALRM/resource/fcntl/termios/os.getuid anywhere (none exist on Windows);
no number here is a latency/jitter/round-trip claim (decision 2, 34-09-PLAN.md) -- only
counts and a plain wall-clock duration, never compared to anything on a Pi; runs under
Python 3.8 (no walrus-in-comprehension, no `match`, no `X | Y` unions).

Unlike ten_line_sender.py, this script deliberately reaches past `mics_link.__all__` into
the `wire`/`selfcheck`/`replay` submodules -- that IS the point of steps 5-7 below (proving
the codec, self-check guard and replay path work on THIS install), not a violation of the
public-API-only rule governing rig_checkpoint_sender.py's decision 1. None of those three
submodules is a private underscore name.
"""
import importlib.metadata
import importlib.util
import platform
import sys
import time

_PASS = "PASS"
_FAIL = "FAIL"

# Copied from sdk/tests/golden_frames.py (Phase 34, Plan 01) -- kept in sync BY HAND, and
# regenerated the same way (tests/generate_golden.py) if that corpus ever changes. tests/
# is not shipped inside the installed wheel, so this script carries its own frozen copy.
_EMBEDDED_GOLDEN = [
    {
        "kind": "SIG",
        "args": ("left_paw_x", 0.7),
        "kwargs": {"seq": 12, "ts_ms": 1700000000123},
        "hex": "85a16ba3534947a674735f737263cf0000018bcfe5687ba37365710ca3736967aa6c6566745f7061775f78a176cb3fe6666666666666",
    },
    {
        "kind": "EVT",
        "args": ("object_detected", {"object": "paw", "confidence": 0.9}),
        "kwargs": {"seq": 20, "ts_ms": 1700000000200},
        "hex": "85a16ba3455654a674735f737263cf0000018bcfe568c8a373657114a3657674af6f626a6563745f6465746563746564a17082a66f626a656374a3706177aa636f6e666964656e6365cb3feccccccccccccd",
    },
    {
        "kind": "HB",
        "args": (),
        "kwargs": {"seq": 99, "ts_ms": 1700000000300},
        "hex": "83a16ba24842a674735f737263cf0000018bcfe5692ca373657163",
    },
]


def _ascii_safe(text):
    """`detail` often echoes a raised exception's own message (e.g. mics_link.selfcheck's
    MicsLinkError is not guaranteed ASCII) -- this keeps THIS script's own console output
    ASCII-safe regardless, so a FAIL report can never itself crash on a legacy codepage.
    """
    return text.encode("ascii", errors="replace").decode("ascii")


def _report(step_name, ok, detail=""):
    status = _PASS if ok else _FAIL
    line = "[{}] {}".format(status, step_name)
    if detail:
        line += " -- {}".format(_ascii_safe(detail))
    print(line)
    return ok


def step_interpreter():
    print("sys.executable: {}".format(sys.executable))
    print("sys.version: {}".format(sys.version.replace("\n", " ")))
    print("platform.platform(): {}".format(platform.platform()))
    return _report("interpreter + platform report", True)


def step_import():
    try:
        import mics_link
    except Exception as exc:  # noqa: BLE001 -- report, never crash the whole smoke run
        return _report("import mics_link", False, "{}: {}".format(type(exc).__name__, exc))
    version = mics_link.__version__
    location = getattr(mics_link, "__file__", "<unknown>")
    print("mics_link.__version__: {}, __file__: {}".format(version, location))
    return _report("import mics_link", True)


def _check_dependency_versions():
    ok = True
    for dist_name in ("pyzmq", "msgpack"):
        try:
            print("{} version: {}".format(dist_name, importlib.metadata.version(dist_name)))
        except importlib.metadata.PackageNotFoundError:
            print("{} version: NOT FOUND via importlib.metadata".format(dist_name))
            ok = False
    if importlib.util.find_spec("msgpack_numpy") is not None:
        print(
            "WARNING: msgpack_numpy is importable here -- its patch() reassigns "
            "msgpack.packb/unpackb globally and can silently corrupt every frame this SDK "
            "sends. Step 4 (selfcheck) below is what detects that."
        )
    return ok


def _check_numpy_not_required():
    """numpy was not pulled in importing mics_link, and (when metadata is discoverable)
    mics-link's OWN declared dependencies never name numpy."""
    ok = "numpy" not in sys.modules
    _report(
        "numpy not required",
        ok,
        "numpy is not in sys.modules" if ok else "numpy is loaded in sys.modules",
    )
    try:
        requires = importlib.metadata.requires("mics-link") or []
    except importlib.metadata.PackageNotFoundError:
        print(
            "mics-link distribution metadata not found (running from an uncommitted source "
            "checkout, not an installed wheel) -- skipping the declared-requires check."
        )
        return ok
    numpy_declared = any("numpy" in requirement.lower() for requirement in requires)
    detail = "requires: {}".format(requires) if numpy_declared else ""
    declared_ok = _report("mics-link declares no numpy dependency", not numpy_declared, detail)
    return ok and declared_ok


def step_dependency_closure():
    versions_ok = _check_dependency_versions()
    import mics_link  # noqa: F401 -- already proven importable by step_import

    numpy_ok = _check_numpy_not_required()
    return _report("dependency closure", versions_ok and numpy_ok)


def step_selfcheck():
    import mics_link.selfcheck

    try:
        mics_link.selfcheck.selfcheck()
    except Exception as exc:  # noqa: BLE001
        return _report(
            "mics_link.selfcheck.selfcheck()", False, "{}: {}".format(type(exc).__name__, exc)
        )
    return _report("mics_link.selfcheck.selfcheck()", True, "OK")


def step_wire_parity():
    from mics_link import wire

    builders = {"SIG": wire.sig_frame, "EVT": wire.evt_frame, "HB": wire.hb_frame}
    ok = True
    for row in _EMBEDDED_GOLDEN:
        observed = builders[row["kind"]](*row["args"], **row["kwargs"])
        expected = bytes.fromhex(row["hex"])
        matched = observed == expected
        detail = "" if matched else "observed={} expected={}".format(observed.hex(), expected.hex())
        ok = _report("wire parity: {}".format(row["kind"]), matched, detail) and ok
    return ok


def _bind_loopback_router():
    """tcp:// only (ipc:// does not exist on Windows). Bind port 0, read back the
    ephemeral port zmq actually chose -- never hardcode one."""
    import zmq

    context = zmq.Context()
    router = context.socket(zmq.ROUTER)
    router.setsockopt(zmq.LINGER, 0)
    router.bind("tcp://127.0.0.1:0")
    endpoint = router.getsockopt(zmq.LAST_ENDPOINT).decode()
    port = int(endpoint.rsplit(":", 1)[1])
    return context, router, port


def _wait_connected(link, timeout_s=5.0):
    deadline = time.monotonic() + timeout_s
    while not link.connected and time.monotonic() < deadline:
        time.sleep(0.02)
    return link.connected


def _teardown(link, router, context):
    """Every exception here is swallowed -- a broken teardown must never mask a step's
    own PASS/FAIL result."""
    if link is not None:
        link.close()
    if router is not None:
        try:
            router.close()
        except Exception:  # noqa: BLE001
            pass
    if context is not None:
        context.term()


def step_loopback_round_trip():
    import mics_link
    import zmq
    from mics_link import wire

    context = router = link = None
    try:
        context, router, port = _bind_loopback_router()
        link = mics_link.connect("127.0.0.1", port, "winsmoke", heartbeat_s=9999.0)
        if not _wait_connected(link):
            return _report("loopback round trip", False, "client never reported CONNECTED")
        if not link.send_signal("smoke_signal", 42):
            return _report("loopback round trip", False, "send_signal returned False (queue full)")

        poller = zmq.Poller()
        poller.register(router, zmq.POLLIN)
        deadline = time.monotonic() + 5.0
        envelope = None
        while time.monotonic() < deadline:
            ready = dict(poller.poll(timeout=100))
            if router in ready:
                _identity, payload = router.recv_multipart()
                decoded = wire.decode_envelope(payload)
                if decoded is not None and decoded.get("k") == "SIG":
                    envelope = decoded
                    break
        if envelope is None:
            return _report("loopback round trip", False, "timed out waiting for a SIG frame")
        if envelope.get("sig") != "smoke_signal" or envelope.get("v") != 42:
            return _report(
                "loopback round trip", False, "unexpected frame contents: {}".format(envelope)
            )
        return _report("loopback round trip", True, "pyzmq send/receive over tcp://127.0.0.1 works")
    finally:
        _teardown(link, router, context)


def step_replay_smoke():
    import mics_link
    from mics_link.replay import replay

    context = router = link = None
    try:
        context, router, port = _bind_loopback_router()
        link = mics_link.connect("127.0.0.1", port, "winsmoke_replay", heartbeat_s=9999.0)
        if not _wait_connected(link):
            return _report("replay smoke", False, "client never reported CONNECTED")

        rows = [(0.0, "replay_signal", 1), (0.01, "replay_signal", 2)]
        stats = replay(link, rows, mode="fast")
        if stats.sent != len(rows):
            return _report(
                "replay smoke", False, "expected {} sent, got {}".format(len(rows), stats.sent)
            )
        return _report(
            "replay smoke", True, "sent {} row(s) via mics_link.replay.replay".format(stats.sent)
        )
    finally:
        _teardown(link, router, context)


def main():
    steps = [
        step_interpreter,
        step_import,
        step_dependency_closure,
        step_selfcheck,
        step_wire_parity,
        step_loopback_round_trip,
        step_replay_smoke,
    ]
    results = []
    for step in steps:
        try:
            results.append(bool(step()))
        except Exception as exc:  # noqa: BLE001 -- one broken step must not kill the rest
            _report(step.__name__, False, "unhandled {}: {}".format(type(exc).__name__, exc))
            results.append(False)
        print("")

    passed = sum(1 for r in results if r)
    total = len(results)
    print("SUMMARY: {}/{} steps passed".format(passed, total))
    if passed == total:
        print("This is a LINUX run. A Windows run of this same file is the actual checkpoint.")
        return 0
    return 1


if __name__ == "__main__":
    sys.exit(main())
