"""Two render sinks -- the notebook the researcher asked for by name, and a
localhost-only MJPEG browser fallback that needs nothing installed (D-58, D-59).

Both sinks read the newest JPEG from the `Viewer`'s own output `LatestSlot`
(`viewer.jpeg_slot`) and the current status text from `viewer.status.lines` -- neither
sink imports `dlc_link.viewer`, so the render core stays sink-agnostic and a third sink
later touches no drawing code. Neither sink may block the viewer: a sink that cannot
keep up simply shows an older frame, and that is correct behaviour, never a defect.

**Nothing in this module imports, at module scope, any package outside the standard
library.** `IPython` is imported lazily, inside `NotebookSink.__init__`, and its
absence is a handled condition -- naming the `mjpeg` sink as the answer that needs
nothing installed -- never a hard dependency. That is the whole reason the second sink
exists: Jupyter pulls in `pyzmq`, and `RUNBOOK.md` step 2 already makes a proposed
`pyzmq` change a STOP condition because `mics-link`'s own transport is `pyzmq` (D-59).
"""
import http.server
import threading
import time

__all__ = ["NotebookSink", "MjpegSink", "SinkError"]


class SinkError(Exception):
    """Raised for every refusal in this module. Always actionable."""


class NotebookSink:
    """Displays the newest JPEG plus the status lines in the cell that drives it
    (Task 3's notebook: a foreground loop calling `update()` while `dlc-link-live`
    runs on a background thread). Writes no file; never raises from `update()`."""

    def __init__(self, jpeg_slot, status_lines):
        try:
            from IPython.display import Image, clear_output, display
        except ImportError as exc:
            raise SinkError(
                "IPython is not installed in this environment ({}: {}). Use "
                "`--view-sink mjpeg` instead -- it opens in any browser on the vision "
                "box and needs nothing installed.".format(type(exc).__name__, exc)
            ) from None
        self._clear_output = clear_output
        self._display = display
        self._Image = Image
        self._jpeg_slot = jpeg_slot
        self._status_lines = status_lines
        self._last_jpeg = None
        self.display_errors = 0

    def start(self):
        pass  # nothing to open; kept for lifecycle symmetry with MjpegSink

    def update(self):
        """Clears the previous output, displays the newest JPEG (or the last one
        successfully received, if nothing new arrived since the last call) plus the
        current status lines. A display failure is counted, never raised."""
        try:
            got, jpeg_bytes = self._jpeg_slot.take()
            if got:
                self._last_jpeg = jpeg_bytes
            self._clear_output(wait=True)
            if self._last_jpeg is not None:
                self._display(self._Image(data=self._last_jpeg))
            for line in self._status_lines():
                print(line)
        except Exception:
            self.display_errors += 1

    def stop(self):
        pass  # nothing to release


class MjpegSink:
    """stdlib `http.server.ThreadingHTTPServer`, bound to `127.0.0.1` only -- never
    reachable from the network. `/` serves a minimal HTML page with the status lines
    and an `<img src="/stream">`; `/stream` serves `multipart/x-mixed-replace`,
    writing the newest JPEG from the slot in a loop with a small sleep. Writes no
    file. A client disconnect (`BrokenPipeError`/`ConnectionResetError`) is a normal
    event: counted, never fatal to the server.
    """

    _BOUNDARY = "dlc-link-live-frame"

    def __init__(self, jpeg_slot, status_lines, port, host="127.0.0.1", frame_interval_s=0.05):
        self._jpeg_slot = jpeg_slot
        self._status_lines = status_lines
        self._frame_interval_s = frame_interval_s
        self._last_jpeg = None
        self.disconnects = 0
        self._server = http.server.ThreadingHTTPServer((host, port), self._build_handler())
        self._thread = None

    @property
    def port(self):
        return self._server.server_address[1]

    def url(self):
        return "http://{}:{}/".format(self._server.server_address[0], self.port)

    def start(self):
        if self._thread is not None:
            return
        self._thread = threading.Thread(target=self._server.serve_forever, daemon=True)
        self._thread.start()

    def stop(self):
        """Idempotent: `shutdown()`/`server_close()` on an already-stopped server is
        safe and releases the port."""
        self._server.shutdown()
        self._server.server_close()

    def _build_handler(self):
        sink = self

        class _Handler(http.server.BaseHTTPRequestHandler):
            def log_message(self, *args, **kwargs):
                pass  # stdout stays clean of per-request noise (DLC-10's vocabulary
                # does not apply here, but the instinct -- no incidental machinery
                # output -- does)

            def do_GET(self):
                if self.path == "/stream":
                    sink._serve_stream(self)
                else:
                    sink._serve_index(self)

        return _Handler

    def _serve_index(self, handler):
        body = (
            "<html><body><pre>{}</pre><img src=\"/stream\"></body></html>".format(
                "\n".join(self._status_lines())
            ).encode("utf-8")
        )
        handler.send_response(200)
        handler.send_header("Content-Type", "text/html")
        handler.send_header("Content-Length", str(len(body)))
        handler.end_headers()
        handler.wfile.write(body)

    def _serve_stream(self, handler):
        handler.send_response(200)
        handler.send_header(
            "Content-Type", "multipart/x-mixed-replace; boundary={}".format(self._BOUNDARY)
        )
        handler.end_headers()
        try:
            while True:
                got, jpeg_bytes = self._jpeg_slot.take()
                if got:
                    self._last_jpeg = jpeg_bytes
                if self._last_jpeg is not None:
                    handler.wfile.write("--{}\r\n".format(self._BOUNDARY).encode("ascii"))
                    handler.wfile.write(b"Content-Type: image/jpeg\r\n")
                    handler.wfile.write(
                        "Content-Length: {}\r\n\r\n".format(len(self._last_jpeg)).encode("ascii")
                    )
                    handler.wfile.write(self._last_jpeg)
                    handler.wfile.write(b"\r\n")
                time.sleep(self._frame_interval_s)
        except (BrokenPipeError, ConnectionResetError):
            self.disconnects += 1
