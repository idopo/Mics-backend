"""Tests for `dlc_link.view_sinks` -- the notebook sink and the localhost-only MJPEG
sink, both fed from one `LatestSlot` of JPEG bytes (Task 2, plan 38-03)."""
import sys
import types
import urllib.request

import pytest

from dlc_link.latest import LatestSlot
from dlc_link.view_sinks import MjpegSink, NotebookSink, SinkError


def _status_lines():
    return ["source: fake", "frames read: 1  rendered: 1  skipped: 0"]


# --- NotebookSink --------------------------------------------------------------------


class _FakeIPythonDisplay:
    """Records `clear_output`/`display`/`Image` calls; swapped into `sys.modules` for
    the duration of one test."""

    def __init__(self, raise_on_display=False):
        self.clear_output_calls = []
        self.display_calls = []
        self.image_calls = []
        self._raise_on_display = raise_on_display

    def clear_output(self, wait=False):
        self.clear_output_calls.append(wait)

    def display(self, obj):
        if self._raise_on_display:
            raise RuntimeError("display backend exploded")
        self.display_calls.append(obj)

    def Image(self, data=None):
        self.image_calls.append(data)
        return ("Image", data)


@pytest.fixture
def fake_ipython(request):
    """Installs a fake `IPython`/`IPython.display` pair into `sys.modules`, removing
    both afterwards regardless of test outcome."""
    raise_on_display = getattr(request, "param", False)
    fake_display_module = _FakeIPythonDisplay(raise_on_display=raise_on_display)
    ipython_pkg = types.ModuleType("IPython")
    display_mod = types.ModuleType("IPython.display")
    display_mod.clear_output = fake_display_module.clear_output
    display_mod.display = fake_display_module.display
    display_mod.Image = fake_display_module.Image
    ipython_pkg.display = display_mod

    previous = {name: sys.modules.get(name) for name in ("IPython", "IPython.display")}
    sys.modules["IPython"] = ipython_pkg
    sys.modules["IPython.display"] = display_mod
    try:
        yield fake_display_module
    finally:
        for name, module in previous.items():
            if module is None:
                sys.modules.pop(name, None)
            else:
                sys.modules[name] = module


def test_notebook_sink_update_clears_and_displays_jpeg_and_status(fake_ipython):
    slot = LatestSlot()
    slot.put(b"jpeg-bytes")
    sink = NotebookSink(slot, _status_lines)
    sink.update()
    assert fake_ipython.clear_output_calls == [True]
    assert fake_ipython.image_calls == [b"jpeg-bytes"]
    assert sink.display_errors == 0


def test_notebook_sink_shows_last_jpeg_when_nothing_new_arrived(fake_ipython):
    slot = LatestSlot()
    slot.put(b"first")
    sink = NotebookSink(slot, _status_lines)
    sink.update()
    sink.update()  # nothing new put into the slot between calls
    assert fake_ipython.image_calls == [b"first", b"first"]


@pytest.mark.parametrize("fake_ipython", [True], indirect=True)
def test_notebook_sink_display_failure_is_counted_not_raised(fake_ipython):
    slot = LatestSlot()
    slot.put(b"jpeg-bytes")
    sink = NotebookSink(slot, _status_lines)
    sink.update()  # must not raise
    assert sink.display_errors == 1


def test_notebook_sink_raises_sink_error_when_ipython_absent():
    previous = {name: sys.modules.pop(name, None) for name in ("IPython", "IPython.display")}
    try:
        with pytest.raises(SinkError) as excinfo:
            NotebookSink(LatestSlot(), _status_lines)
        assert "mjpeg" in str(excinfo.value)
    finally:
        for name, module in previous.items():
            if module is not None:
                sys.modules[name] = module


def test_notebook_sink_never_writes_a_file(tmp_path, fake_ipython, monkeypatch):
    monkeypatch.chdir(tmp_path)
    slot = LatestSlot()
    slot.put(b"jpeg-bytes")
    sink = NotebookSink(slot, _status_lines)
    sink.update()
    assert list(tmp_path.iterdir()) == []


# --- MjpegSink ------------------------------------------------------------------------


@pytest.fixture
def mjpeg_sink():
    slot = LatestSlot()
    slot.put(b"\xff\xd8\xff\xd9")  # a trivial (fake) JPEG payload
    sink = MjpegSink(slot, _status_lines, port=0, frame_interval_s=0.01)
    sink.start()
    try:
        yield sink, slot
    finally:
        sink.stop()


def test_mjpeg_sink_binds_localhost_only_and_reports_its_port(mjpeg_sink):
    sink, _ = mjpeg_sink
    assert sink.port != 0
    assert sink.url() == "http://127.0.0.1:{}/".format(sink.port)


def test_mjpeg_sink_index_page_contains_status_line_and_img_tag(mjpeg_sink):
    sink, _ = mjpeg_sink
    with urllib.request.urlopen(sink.url(), timeout=2.0) as response:
        body = response.read().decode("utf-8")
    assert "frames read: 1" in body
    assert '<img src="/stream">' in body


def test_mjpeg_sink_stream_is_multipart_and_carries_a_jpeg_boundary(mjpeg_sink):
    sink, _ = mjpeg_sink
    request = urllib.request.Request(sink.url() + "stream")
    with urllib.request.urlopen(request, timeout=2.0) as response:
        assert response.headers.get("Content-Type", "").startswith("multipart/x-mixed-replace")
        chunk = response.read(256)
    assert sink._BOUNDARY.encode("ascii") in chunk
    assert b"Content-Type: image/jpeg" in chunk


def test_mjpeg_sink_survives_a_client_disconnecting_mid_stream(mjpeg_sink):
    sink, _ = mjpeg_sink
    request = urllib.request.Request(sink.url() + "stream")
    response = urllib.request.urlopen(request, timeout=2.0)
    response.read(64)
    response.close()  # disconnect mid-stream

    # The server must still be serving afterwards -- a second, independent request.
    with urllib.request.urlopen(sink.url(), timeout=2.0) as second:
        assert second.status == 200


def test_mjpeg_sink_stop_is_idempotent():
    slot = LatestSlot()
    sink = MjpegSink(slot, _status_lines, port=0)
    sink.start()
    sink.stop()
    sink.stop()  # must not raise


def test_mjpeg_sink_never_writes_a_file(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    slot = LatestSlot()
    slot.put(b"\xff\xd8\xff\xd9")
    sink = MjpegSink(slot, _status_lines, port=0, frame_interval_s=0.01)
    sink.start()
    try:
        with urllib.request.urlopen(sink.url(), timeout=2.0) as response:
            response.read()
    finally:
        sink.stop()
    assert list(tmp_path.iterdir()) == []


# --- source hygiene --------------------------------------------------------------------


def test_module_imports_nothing_outside_stdlib_at_module_scope():
    import ast
    import os

    path = os.path.join(os.path.dirname(__file__), "..", "src", "dlc_link", "view_sinks.py")
    with open(path) as handle:
        tree = ast.parse(handle.read())
    stdlib = {"http", "threading", "time"}
    for node in ast.iter_child_nodes(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                assert alias.name.split(".")[0] in stdlib
        elif isinstance(node, ast.ImportFrom):
            assert node.module is None or node.module.split(".")[0] in stdlib
