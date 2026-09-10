"""`--view`'s wiring for `dlc-link-live`, split out of `dlc_link.live_cli` to keep
that module under the project's 300-line production-file limit (same split precedent
as `dlc_link.live`/`live_cli`, plan 38-01).

`dlc_link.viewer` and `dlc_link.view_sinks` import no `cv2` at module scope, so this
module is safe to import unconditionally from `live_cli.py` -- nothing here needs the
deferred-import dance `main()` does for `cv2`/`dlclive`.
"""
from dlc_link.overlay import OverlayError, parse_overlay
from dlc_link.pilot_state import (
    RunIdentity,
    StateReading,
    fetch_fda_state,
    fetch_run_identity,
)
from dlc_link.view_sinks import MjpegSink, NotebookSink
from dlc_link.viewer import Viewer


class _OrchestratorEsPoller:
    """Binds `--pilot`/`--orchestrator-url`/`--es-url`/`--es-index` into the two-call
    shape `Viewer`'s poll thread expects (D-57). Every part that was not configured
    renders `unavailable - not configured` rather than attempting a request --
    reachability of either from the vision box is unverified until plan 38-04 (D-57),
    so the viewer must work with either, both, or neither."""

    def __init__(self, orchestrator_url, pilot_name, es_url, es_index, timeout_s=2.0):
        self._orchestrator_url = orchestrator_url
        self._pilot_name = pilot_name
        self._es_url = es_url
        self._es_index = es_index
        self._timeout_s = timeout_s

    def fetch_run_identity(self):
        if not self._orchestrator_url or not self._pilot_name:
            return RunIdentity(
                available=False, reason="not configured (--pilot / --orchestrator-url)"
            )
        return fetch_run_identity(self._orchestrator_url, self._pilot_name, timeout_s=self._timeout_s)

    def fetch_fda_state(self, subject_key):
        if not self._es_url:
            return StateReading(available=False, reason="not configured (--es-url)")
        return fetch_fda_state(self._es_url, self._es_index, subject_key, timeout_s=self._timeout_s)


def parse_overlay_clauses(args, smap):
    """Returns `(problem, clauses)`. `problem` is a ready-to-print message (naming the
    declared signal names) when `--overlay` does not parse against `smap`; both are
    `None` when `--overlay` was not given at all. Checked before any heavy import."""
    if not args.overlay:
        return None, None
    try:
        return None, parse_overlay(args.overlay, smap)
    except OverlayError as exc:
        return str(exc), None


def build_viewer(args, smap, overlay_clauses, width, height, source_description):
    """Constructs (but does not start) the `Viewer` for `--view`. Called only when
    `args.view` is true -- a headless run must construct no `Viewer` and start no
    thread at all."""
    poller = _OrchestratorEsPoller(args.orchestrator_url, args.pilot, args.es_url, args.es_index)
    return Viewer(
        smap, width, height, args.view_min_likelihood,
        overlay_clauses=overlay_clauses, poller=poller, source_description=source_description,
    )


def build_sink(args, viewer):
    """Returns a started sink. Raises `dlc_link.view_sinks.SinkError` (the caller
    prints it and names `--view-sink mjpeg`) when the notebook sink was requested and
    IPython is absent."""
    if args.view_sink == "mjpeg":
        sink = MjpegSink(viewer.jpeg_slot, viewer.status.lines, args.view_port)
    else:
        sink = NotebookSink(viewer.jpeg_slot, viewer.status.lines)
    sink.start()
    return sink


def describe_sink(args, sink):
    """The `view:` line printed immediately after `source:` -- the researcher should
    not have to guess the URL."""
    if args.view_sink == "mjpeg":
        return "view: mjpeg sink -- open {} in a browser on this machine".format(sink.url())
    return "view: notebook sink -- run the notebook's display-loop cell"
