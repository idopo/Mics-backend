"""Pure source classification and the pacing/termination policy that follows from it
(D-49, D-51, D-54, D-55).

`cv2.VideoCapture` treats an `int` argument as a device index and a `str` argument as a
path or URL. `dlc_link.live`'s `--video` flag was declared with no `type=`, so it was
always a `str`, and `--video 0` opened a FILE named `0` and failed to read a first frame
(`38-CONTEXT.md` §3a) -- the defect this module exists to fix, named here at the fix
rather than left implicit.

Pure: no `cv2`, no `dlclive`, no I/O, no threads. Importable on a machine with neither
library installed, so the classification itself is unit-testable on the dev host.

Windows note: `C:\\videos\\clip.mp4` contains a colon but is not a URL -- the `://`
requirement (not a bare `:`) is what keeps a drive letter out of the `stream` branch.

**Forward note added 2026-09-06 (D-75) -- recorded, deliberately NOT implemented here.**
The rig's camera turned out to be a GigE Vision device (`DMK 33GP1300`), which
`cv2.VideoCapture` cannot open under any of the three kinds below. If that resolves to
T5b, a FOURTH kind -- a GenICam handle such as `tcam:5810436`, addressed by serial --
will be needed, fed through this module's injected-capture seam by the vendor's own
Windows SDK (The Imaging Source's `imagingcontrol4`), NOT by aravis (a Linux/GObject
stack, wrong for this vision box). `tcam:5810436` contains a colon but no `://`, so today
it falls through to `file` and produces the confusing "cannot read first frame" this
module otherwise prevents -- a half-guessed branch for an undesigned kind would be worse
than that documented fall-through, so none is added here. `SourceSpec.kind` is kept a
plain string rather than a closed enum for exactly this reason: a fourth value is an
addition, not a refactor of every consumer.
"""

_STREAM_SCHEMES = ("rtsp", "rtsps", "http", "https", "udp", "tcp", "rtmp")


class SourceError(Exception):
    """Always quotes the offending argument."""


class SourceSpec:
    """Immutable record of how a `--source`/`--video` argument was classified.

    `kind`: `"device"` / `"stream"` / `"file"`. `capture_arg`: an `int` for `device`,
    the original `str` otherwise -- exactly what `cv2.VideoCapture(...)` should receive.
    `original`: what the researcher typed, unchanged, for error messages and logging.
    """

    __slots__ = ("kind", "capture_arg", "original")

    def __init__(self, kind, capture_arg, original):
        self.kind = kind
        self.capture_arg = capture_arg
        self.original = original

    def describe(self):
        """One-line human string printed by the CLI BEFORE the capture is constructed,
        so a misread argument is visible rather than inferred from whether it worked."""
        if self.kind == "device":
            return "device index {}".format(self.capture_arg)
        if self.kind == "stream":
            return "stream URL {}".format(self.capture_arg)
        return "file {}".format(self.capture_arg)

    def __repr__(self):
        return "SourceSpec(kind={!r}, capture_arg={!r}, original={!r})".format(
            self.kind, self.capture_arg, self.original
        )


def classify_source(value):
    """Classify a `--source`/`--video` argument into a `SourceSpec`.

    - empty or whitespace-only -> `SourceError`
    - a leading `-` followed by digits -> `SourceError` naming that a device index may
      not be negative (rather than falling through to `file` and producing a confusing
      "cannot read first frame")
    - all-digits (`value.strip().isdigit()`) -> `device`, `capture_arg = int(value)`
    - a URL scheme in rtsp/rtsps/http/https/udp/tcp/rtmp, matched case-insensitively on
      `<scheme>://` -> `stream`
    - anything else -> `file`. Existence is NOT checked here -- that is `cv2`'s problem
      to report, and this function stays pure and testable on a host where the path
      does not exist.
    """
    if value is None or not value.strip():
        raise SourceError("source value {!r} is empty".format(value))

    stripped = value.strip()

    if stripped[0] == "-" and stripped[1:].isdigit():
        raise SourceError(
            "source value {!r}: a device index may not be negative".format(value)
        )

    if stripped.isdigit():
        return SourceSpec(kind="device", capture_arg=int(stripped), original=value)

    lowered = stripped.lower()
    for scheme in _STREAM_SCHEMES:
        if lowered.startswith(scheme + "://"):
            return SourceSpec(kind="stream", capture_arg=value, original=value)

    return SourceSpec(kind="file", capture_arg=value, original=value)


def pacing_for(kind):
    """`True` for `file` only (D-51). A file runs unpaced because `cap.read()` returns
    instantly; a camera paces itself because `cap.read()` blocks on the sensor, and
    stacking a pacer on a camera double-throttles."""
    return kind == "file"


def read_failure_is_terminal(kind):
    """`True` for `file` only (D-55). A file's failed read is end-of-file; a camera's is
    a hiccup -- transient, and retried rather than treated as the end of the run."""
    return kind == "file"


def fps_refusal(kind, fps):
    """`None` when `--fps` is acceptable for this source kind, otherwise the exact
    message the CLI prints to stderr and exits on.

    Names the source kind, says a camera paces itself, says `CAP_PROP_FPS` is not
    trusted for a camera either, and points at `--min-rate` as the flag that actually
    expresses a rate expectation for a camera (D-51, D-54). This exists because the
    Phase 35 command line the researcher will copy contains `--fps 30`, and silently
    honouring it on a 60 Hz camera would halve the model's view of the animal with
    nothing on screen to say so.
    """
    if kind == "file" or fps is None:
        return None
    return (
        "--fps is refused for a {} source: a camera paces itself (cap.read() blocks on "
        "the sensor) and cap.get(CAP_PROP_FPS) is not trusted for a camera either -- use "
        "--min-rate to express a rate expectation for a camera instead.".format(kind)
    )
