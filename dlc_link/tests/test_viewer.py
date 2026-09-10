"""Tests for `dlc_link.viewer` -- three threads, one `LatestSlot` each way, no path
back to the sender (Task 1, plan 38-03)."""
import os
import time

from dlc_link.overlay import parse_overlay
from dlc_link.pilot_state import RunIdentity, StateReading
from dlc_link.viewer import StatusBlock, Viewer, render_primitives


# --- fakes -------------------------------------------------------------------------


class _SignalMap:
    """2 bodyparts over a 3-row pose; `nose` has coords, `tail` does not -- same
    shape as plan 38-02's `_SignalMap3Row`."""

    SIGNAL_NAMES = ["nose_likelihood", "nose_x", "nose_y", "tail_likelihood"]
    SIGNALS = {
        "nose": {
            "index": 0,
            "coords": True,
            "signals": {"likelihood": "nose_likelihood", "x": "nose_x", "y": "nose_y"},
        },
        "tail": {
            "index": 2,
            "coords": False,
            "signals": {"likelihood": "tail_likelihood"},
        },
    }


def _pose(nose_likelihood=0.9, tail_likelihood=0.9):
    return [
        [100.0, 200.0, nose_likelihood, 0.0, 0.0],
        [0.0, 0.0, 0.0, 0.0, 0.0],
        [50.0, 60.0, tail_likelihood, 0.0, 0.0],
    ]


class _FakeFrame:
    """Stands in for a numpy frame: `.copy()` returns a distinct object, and every
    drawn-on instance records draw calls so a test can tell original from copy."""

    def __init__(self, tag):
        self.tag = tag

    def copy(self):
        return _FakeFrame(self.tag + "-copy")


class _RecordingBackend:
    def __init__(self):
        self.circle_calls = []
        self.text_calls = []
        self.line_calls = []

    def circle(self, frame, center, radius, color, thickness):
        self.circle_calls.append((frame, center, radius, color, thickness))

    def text(self, frame, text, position, color):
        self.text_calls.append((frame, text, position, color))

    def line(self, frame, start, end, color):
        self.line_calls.append((frame, start, end, color))

    def calls(self):
        return self.circle_calls + self.text_calls + self.line_calls


class _RaisingBackend:
    def circle(self, *a, **k):
        raise RuntimeError("backend exploded")

    def text(self, *a, **k):
        raise RuntimeError("backend exploded")

    def line(self, *a, **k):
        raise RuntimeError("backend exploded")


class _FakeEncoder:
    """Callable `(frame, quality) -> (ok, bytes)`. `always_fail` makes every call
    report failure without raising, to exercise the `encode_errors` path."""

    def __init__(self, always_fail=False):
        self.calls = []
        self.always_fail = always_fail

    def __call__(self, frame, quality):
        self.calls.append((frame, quality))
        if self.always_fail:
            return False, None
        return True, b"fake-jpeg-bytes"


class _FakePoller:
    def __init__(self, identities, states=None):
        self._identities = list(identities)
        self._states = list(states or [])
        self.identity_calls = 0
        self.state_calls = []

    def fetch_run_identity(self):
        self.identity_calls += 1
        if self._identities:
            return self._identities.pop(0)
        return self._identities_default()

    def _identities_default(self):
        return RunIdentity(available=False, reason="exhausted")

    def fetch_fda_state(self, subject_key):
        self.state_calls.append(subject_key)
        if self._states:
            return self._states.pop(0)
        return StateReading(available=False, reason="exhausted")


class _FakeSleep:
    def __init__(self):
        self.calls = []

    def __call__(self, seconds):
        self.calls.append(seconds)


def _wait_until(predicate, timeout=2.0, interval=0.005):
    deadline = time.time() + timeout
    while time.time() < deadline:
        if predicate():
            return True
        time.sleep(interval)
    return predicate()


def _make_viewer(**overrides):
    kwargs = dict(
        signal_map=_SignalMap,
        frame_width=640,
        frame_height=480,
        min_likelihood=0.6,
    )
    # Default backend/encoder are fakes, never cv2 -- this dev host has no cv2
    # installed, and the whole point of injecting both is that the viewer never
    # requires it to be importable to run its threads.
    kwargs.setdefault("backend", _RecordingBackend())
    kwargs.setdefault("encoder", _FakeEncoder())
    kwargs.update(overrides)
    return Viewer(**kwargs)


# --- push: the entire hot-path body -------------------------------------------------


def test_push_calls_neither_backend_nor_encoder():
    backend = _RecordingBackend()
    encoder = _FakeEncoder()
    viewer = _make_viewer(backend=backend, encoder=encoder)
    viewer.push(_FakeFrame("a"), _pose())
    assert backend.calls() == []
    assert encoder.calls == []


def test_100_pushes_with_render_thread_stopped_leave_overwrites_at_99():
    viewer = _make_viewer()
    for _ in range(100):
        viewer.push(_FakeFrame("x"), _pose())
    assert viewer.snapshot()["frames"]["overwrites"] == 99
    assert viewer.push_errors == 0


def test_push_never_raises_even_on_a_pathological_frame():
    class _Explodes:
        def copy(self):
            raise RuntimeError("no copy for you")

    viewer = _make_viewer()
    viewer.push(_Explodes(), _pose())  # must not raise
    assert viewer.snapshot()["frames"]["puts"] == 1


# --- render thread: newest frame -> draw plan -> backend -> encoder -> output slot --


def test_render_thread_renders_and_encodes_pushed_frame():
    backend = _RecordingBackend()
    encoder = _FakeEncoder()
    viewer = _make_viewer(backend=backend, encoder=encoder, sleep=_FakeSleep())
    viewer.start()
    try:
        viewer.push(_FakeFrame("a"), _pose())
        assert _wait_until(lambda: encoder.calls)
        got, jpeg_bytes = viewer._jpeg.take()
        assert got
        assert jpeg_bytes == b"fake-jpeg-bytes"
        assert backend.calls()  # at least one primitive was dispatched
    finally:
        viewer.stop()


def test_pushed_frame_object_is_not_the_object_the_backend_received():
    backend = _RecordingBackend()
    viewer = _make_viewer(backend=backend, sleep=_FakeSleep())
    viewer.start()
    try:
        original = _FakeFrame("original")
        viewer.push(original, _pose())
        assert _wait_until(lambda: backend.calls())
        seen_frame = backend.calls()[0][0]
        assert seen_frame is not original
        assert seen_frame.tag == "original-copy"
    finally:
        viewer.stop()


def test_render_backend_raising_increments_render_errors_and_thread_stays_alive():
    viewer = _make_viewer(backend=_RaisingBackend(), sleep=_FakeSleep())
    viewer.start()
    try:
        viewer.push(_FakeFrame("a"), _pose())
        viewer.push(_FakeFrame("b"), _pose())
        assert _wait_until(lambda: viewer.render_errors >= 1)
        assert viewer._render_thread.is_alive()
    finally:
        viewer.stop()


def test_encoder_failure_increments_encode_errors_and_thread_stays_alive():
    encoder = _FakeEncoder(always_fail=True)
    viewer = _make_viewer(encoder=encoder, backend=_RecordingBackend(), sleep=_FakeSleep())
    viewer.start()
    try:
        viewer.push(_FakeFrame("a"), _pose())
        assert _wait_until(lambda: viewer.encode_errors >= 1)
        assert viewer._render_thread.is_alive()
    finally:
        viewer.stop()


def test_render_errors_count_one_per_failed_frame_not_per_primitive():
    # Each pushed-and-processed frame produces several primitives (a circle + a label
    # for `nose`, a label for `tail`); a backend raising on the FIRST primitive it
    # sees must still count exactly one `render_errors` per frame, not one per
    # primitive -- `render_primitives` does not swallow per-primitive exceptions.
    backend = _RaisingBackend()
    viewer = _make_viewer(backend=backend, sleep=_FakeSleep())
    viewer.start()
    try:
        for _ in range(3):
            before = viewer.render_errors
            viewer.push(_FakeFrame("f"), _pose())
            assert _wait_until(lambda: viewer.render_errors == before + 1)
    finally:
        viewer.stop()


def test_render_thread_catches_a_frame_that_cannot_be_copied():
    class _UncopyableFrame:
        def copy(self):
            raise RuntimeError("buffer already reused")

    viewer = _make_viewer(backend=_RecordingBackend(), sleep=_FakeSleep())
    viewer.start()
    try:
        viewer.push(_UncopyableFrame(), _pose())
        assert _wait_until(lambda: viewer.render_errors >= 1)
        assert viewer._render_thread.is_alive()
    finally:
        viewer.stop()


# --- poller thread -------------------------------------------------------------------


def test_poller_skips_fetch_fda_state_when_no_active_run():
    identity = RunIdentity(available=True, reason="no active run", subject_key=None)
    poller = _FakePoller(identities=[identity])
    viewer = _make_viewer(poller=poller, sleep=_FakeSleep(), poll_interval_s=0.0)
    viewer.start()
    try:
        assert _wait_until(lambda: poller.identity_calls >= 1)
        time.sleep(0.02)
        assert poller.state_calls == []
    finally:
        viewer.stop()


def test_poller_calls_fetch_fda_state_with_subject_key_from_run_identity():
    identity = RunIdentity(available=True, reason="", run_id=5, session_id=9, subject_key="bp_s9_r5")
    state = StateReading(available=True, reason="", state="WAIT_TRIAL")
    poller = _FakePoller(identities=[identity], states=[state])
    viewer = _make_viewer(poller=poller, sleep=_FakeSleep(), poll_interval_s=0.0)
    viewer.start()
    try:
        assert _wait_until(lambda: poller.state_calls == ["bp_s9_r5"])
    finally:
        viewer.stop()


def test_poller_failure_renders_unavailable_and_never_blocks_frame_thread():
    class _RaisingPoller:
        def fetch_run_identity(self):
            raise ConnectionError("no route to host")

        def fetch_fda_state(self, subject_key):
            raise AssertionError("must not be called")

    backend = _RecordingBackend()
    viewer = _make_viewer(poller=_RaisingPoller(), backend=backend, sleep=_FakeSleep(), poll_interval_s=0.0)
    viewer.start()
    try:
        viewer.push(_FakeFrame("a"), _pose())
        assert _wait_until(lambda: backend.calls())  # frame thread unaffected
        assert _wait_until(
            lambda: "unavailable - ConnectionError: no route to host" in "\n".join(viewer.status.lines())
        )
    finally:
        viewer.stop()


# --- StatusBlock ----------------------------------------------------------------------


def test_status_block_lines_cover_the_required_fields():
    status = StatusBlock(source_description="rtsp://cam")
    status.update_frame_counts(
        frames_read=10, frames_inferred=8, frames_skipped=2, observer_errors=0, render_errors=1,
    )
    status.update_run_identity(
        RunIdentity(available=True, reason="", run_id=5, session_id=9, subject_key="bp_s9_r5")
    )
    status.update_state_reading(StateReading(available=True, reason="", state="WAIT_TRIAL"))
    lines = status.lines()
    blob = "\n".join(lines)
    assert "rtsp://cam" in blob
    assert "frames read: 10" in blob
    assert "render_errors: 1" in blob
    assert "run_id: 5" in blob
    assert "session_id: 9" in blob
    assert "bp_s9_r5" in blob
    assert "FDA state: WAIT_TRIAL" in blob


def test_status_block_never_shows_a_previously_fetched_state_as_current():
    status = StatusBlock()
    status.update_state_reading(StateReading(available=True, reason="", state="WAIT_TRIAL"))
    assert "FDA state: WAIT_TRIAL" in status.lines()
    status.update_state_reading(StateReading(available=False, reason="timeout"))
    blob = "\n".join(status.lines())
    assert "WAIT_TRIAL" not in blob
    assert "unavailable - timeout" in blob


def test_status_block_stale_state_before_any_successful_poll():
    status = StatusBlock()
    assert status.stale_state is True
    assert "not yet polled" in "\n".join(status.lines())
    status.update_state_reading(StateReading(available=True, reason="", state="X"))
    assert status.stale_state is False


# --- render_primitives ----------------------------------------------------------------


def test_render_primitives_dispatches_in_order_and_counts_unknown():
    from dlc_link.annotate import DrawPrimitive

    backend = _RecordingBackend()
    primitives = [
        DrawPrimitive(kind="circle", center=(1, 2), color=(0, 0, 0), radius=3, thickness=1),
        DrawPrimitive(kind="text", text="hi", position=(0, 0), color=None),
        DrawPrimitive(kind="line", start=(0, 0), end=(1, 1), color=None),
        DrawPrimitive(kind="sparkle"),
    ]
    counts = render_primitives("frame", primitives, backend)
    assert counts == {"circle": 1, "text": 1, "line": 1, "unknown": 1}
    assert backend.circle_calls and backend.text_calls and backend.line_calls


# --- lifecycle -------------------------------------------------------------------------


def test_stop_before_start_raises_nothing():
    viewer = _make_viewer()
    viewer.stop()  # must not raise


def test_stop_called_twice_raises_nothing():
    viewer = _make_viewer(sleep=_FakeSleep())
    viewer.start()
    viewer.stop()
    viewer.stop()  # must not raise


def test_snapshot_has_no_duration_or_latency_shaped_key_or_value():
    viewer = _make_viewer()
    viewer.push(_FakeFrame("a"), _pose())
    snap = viewer.snapshot()
    forbidden = ("duration", "latency", "elapsed", "_ms", "timestamp")

    def _walk(value):
        if isinstance(value, dict):
            for key, inner in value.items():
                for word in forbidden:
                    assert word not in key.lower()
                _walk(inner)
        elif isinstance(value, str):
            for word in forbidden:
                assert word not in value.lower()

    _walk(snap)


# --- source hygiene ---------------------------------------------------------------------


def test_source_has_no_imshow_and_no_module_scope_cv2_import():
    path = os.path.join(os.path.dirname(__file__), "..", "src", "dlc_link", "viewer.py")
    with open(path) as handle:
        lines = handle.readlines()
    assert not any("imshow" in line for line in lines)
    assert not any(line.startswith("import cv2") or line.startswith("from cv2") for line in lines)


def test_overlay_clause_drives_overlay_values_from_the_same_normalised_numbers():
    clauses = parse_overlay("nose_x>0.1", _SignalMap)
    backend = _RecordingBackend()
    viewer = _make_viewer(backend=backend, overlay_clauses=clauses, sleep=_FakeSleep())
    viewer.start()
    try:
        viewer.push(_FakeFrame("a"), _pose())
        assert _wait_until(lambda: backend.line_calls)
    finally:
        viewer.stop()
