"""Tests for dlc_link.capture.FrameReader (Task 2, plan 38-01)."""
import inspect
import time

from dlc_link import capture as capture_module
from dlc_link.capture import FrameReader
from dlc_link.latest import LatestSlot


class _FakeSleep:
    def __init__(self):
        self.calls = []

    def __call__(self, seconds):
        self.calls.append(seconds)


def _wait_until_stopped(reader, max_iterations=200):
    iterations = 0
    while reader.is_alive() and iterations < max_iterations:
        time.sleep(0.005)
        iterations += 1
    return iterations < max_iterations


def _queued_read(frames):
    queue = list(frames)

    def read():
        if queue:
            return queue.pop(0)
        return False, None

    return read


# --- terminal-on-failure (file-like) source ----------------------------------------


def test_terminal_source_stops_on_first_failure_with_end_of_stream_reason():
    slot = LatestSlot()
    frames = [(True, "f1"), (True, "f2"), (True, "f3"), (True, "f4"), (True, "f5")]
    read = _queued_read(frames)
    sleep = _FakeSleep()
    reader = FrameReader(read, slot, terminal_on_failure=True, read_retries=3, sleep=sleep)
    reader.start()
    assert _wait_until_stopped(reader)
    assert reader.stopped_reason == "end-of-stream"
    assert reader.frames_read == 5


# --- non-terminal (camera-like) source ----------------------------------------------


def test_non_terminal_source_retries_and_exhausts_after_read_retries():
    slot = LatestSlot()
    read = _queued_read([])  # always (False, None)
    sleep = _FakeSleep()
    reader = FrameReader(read, slot, terminal_on_failure=False, read_retries=3, sleep=sleep)
    reader.start()
    assert _wait_until_stopped(reader)
    assert reader.stopped_reason == "read-failures-exhausted"
    assert reader.read_failures == 3
    assert len(sleep.calls) == 2  # one sleep between each pair of failures, none after the last


def test_single_failure_then_successes_resets_consecutive_count():
    # 1 failure, then successes forever (never exhausts). read_retries=3 would stop the
    # run after 3 CONSECUTIVE failures; the single leading failure must not count
    # towards that threshold once a success resets it.
    queue = [(False, None), (True, "a"), (True, "b")]

    def read():
        if queue:
            return queue.pop(0)
        return True, "holding"  # every subsequent read succeeds, never a failure again

    slot = LatestSlot()
    sleep = _FakeSleep()
    reader = FrameReader(read, slot, terminal_on_failure=False, read_retries=3, sleep=sleep)
    reader.start()
    deadline = time.time() + 2.0
    while reader.frames_read < 2 and time.time() < deadline:
        time.sleep(0.005)
    reader.stop()
    assert _wait_until_stopped(reader)
    assert reader.read_failures == 1
    assert reader.stopped_reason != "read-failures-exhausted"


def test_frame_reader_stop_is_idempotent_called_twice():
    slot = LatestSlot()
    read = _queued_read([])
    reader = FrameReader(read, slot, terminal_on_failure=False, read_retries=100, sleep=_FakeSleep())
    reader.start()
    reader.stop()
    reader.stop()  # must not raise
    assert _wait_until_stopped(reader)


def test_frame_reader_stop_before_start_raises_nothing():
    slot = LatestSlot()
    read = _queued_read([])
    reader = FrameReader(read, slot, terminal_on_failure=False, read_retries=100, sleep=_FakeSleep())
    reader.stop()  # must not raise, even though start() was never called


def test_frame_reader_cooperative_stop_sets_stopped_reason():
    def read():
        return True, "a"  # always succeeds; stop() is the only way this thread ends

    slot = LatestSlot()
    reader = FrameReader(read, slot, terminal_on_failure=False, read_retries=100, sleep=_FakeSleep())
    reader.start()
    time.sleep(0.02)
    reader.stop()
    assert _wait_until_stopped(reader)
    assert reader.stopped_reason == "stopped"


# --- exceptions from read() ----------------------------------------------------------


def test_read_exception_is_counted_and_thread_keeps_running():
    calls = {"n": 0}

    def read():
        calls["n"] += 1
        if calls["n"] <= 2:
            raise RuntimeError("driver hiccup")
        return True, "ok-frame"

    slot = LatestSlot()
    reader = FrameReader(read, slot, terminal_on_failure=False, read_retries=10, sleep=_FakeSleep())
    reader.start()
    # Let it process a few frames, then stop cooperatively.
    deadline = time.time() + 2.0
    while reader.frames_read < 1 and time.time() < deadline:
        time.sleep(0.005)
    reader.stop()
    assert _wait_until_stopped(reader)
    assert reader.read_exceptions == 2
    assert reader.frames_read >= 1


# --- puts land in the slot, never release() ------------------------------------------


def test_successful_reads_land_in_the_slot():
    slot = LatestSlot()
    read = _queued_read([(True, "f1"), (True, "f2")])
    reader = FrameReader(read, slot, terminal_on_failure=True, read_retries=3, sleep=_FakeSleep())
    reader.start()
    assert _wait_until_stopped(reader)
    assert slot.snapshot()["puts"] == 2


def test_frame_reader_module_never_calls_release():
    # Checks actual call sites (`.release(`), never the prose describing the rule in
    # the module docstring -- a plain substring check on the whole module would match
    # that prose and false-positive.
    import ast

    tree = ast.parse(inspect.getsource(capture_module))
    release_calls = [
        node for node in ast.walk(tree)
        if isinstance(node, ast.Call)
        and isinstance(node.func, ast.Attribute)
        and node.func.attr == "release"
    ]
    assert release_calls == []


def test_frame_reader_module_has_no_cv2_import():
    source_text = inspect.getsource(capture_module)
    assert "import cv2" not in source_text
