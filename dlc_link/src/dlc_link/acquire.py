"""Pure ffmpeg argv + tee-spec builder for the lab-computer acquisition recorder (D-88).

One `ffmpeg` invocation on the lab computer holds the camera (DirectShow access is
exclusive, `38-HARDWARE-VALIDATION.md` §8.4) and must do BOTH jobs at once: write a
segmented archival file and push the live feed to the vision box. This module decides
the exact argv for that invocation and nothing else decides it (follows `source.py`'s
precedent: pure, no `cv2`, no `subprocess`, no network, its own test file, importable
on a machine with no camera and no ffmpeg at all).

Two constraints D-88 itself does not state, both load-bearing here (see
`38-07-PLAN.md`'s `<constraint_D88_did_not_state>`):

1. **The `tee` muxer does ONE encode and fans out the SAME packets to every slave.**
   Differing codecs per leg is only reachable by mapping the video stream TWICE,
   encoding it twice, and giving each slave a `select=` option. The DEFAULT here is one
   encode, MJPEG, both legs; the two-stream `select=` form is an ESCALATION this module
   emits only when `delivery_codec` is given and differs from `file_codec` -- needed
   when the file leg is training data and the default MJPEG quality is not good enough
   for a model that has not been trained yet (this plan was reprioritised for exactly
   that reason: the footage recorded here IS the DeepLabCut training set, so file-leg
   quality is a first-class requirement, not a tuning knob to leave at the cheap
   default). Callers that want a cheap single-encode archive ask for it explicitly by
   leaving `delivery_codec` unset; the builder never silently gives the archival file
   the live feed's quality.
2. **The `tee` slave spec treats `\\` as an escape character and `:` as its own option
   separator.** A Windows absolute path placed inside one is silently mangled.
   `segment_pattern` is therefore REFUSED unless it is relative, uses forward slashes
   only, and contains none of `\\ : | [ ]` -- removing the drive letter, the
   backslashes and the colon from the spec entirely rather than escaping them. The
   caller sets ffmpeg's working directory (via `-WorkingDirectory` in the generated
   PowerShell) to make the relative pattern resolve where intended.

Third, not stated by D-88 either: `-v`/`-loglevel` is never emitted. `frame dropped` is
a warning the dshow demuxer prints at ffmpeg's DEFAULT verbosity; `-v error` would
suppress it and make the completeness test's third witness pass vacuously.
"""
from dataclasses import dataclass

_VALID_DELIVERY_FORMATS = ("mpjpeg", "mpegts")

# Characters the tee muxer's slave-spec grammar cannot carry in a segment pattern: `\`
# is its escape character, `:` separates `key=value` options, `|` separates slaves, and
# `[`/`]` bracket the option list. Any of these inside a filename is silently mangled
# rather than rejected by ffmpeg -- so this module refuses it instead of discovering it
# on the rig (amendment 3, D-88).
_TEE_UNSAFE_CHARS = ("\\", ":", "|", "[", "]")


class AcquireSpecError(ValueError):
    """Always names the offending field and the reason a human would need to fix it."""


@dataclass(frozen=True)
class AcquireSpec:
    """Everything needed to build one ffmpeg invocation. Pure data -- validated in
    `__post_init__` so an invalid spec can never reach `build_ffmpeg_argv`."""

    device: str
    segment_pattern: str
    segment_time_s: int
    segment_format: str = "matroska"
    rtbufsize: str = "100M"
    file_codec: str = "mjpeg"
    file_quality: str = "5"
    file_extra: tuple = ()
    delivery_url: str = None
    delivery_format: str = None
    delivery_codec: str = None
    delivery_extra: tuple = ()
    duration_s: int = None

    def __post_init__(self):
        _validate(self)

    @property
    def two_stream(self):
        """True only when the caller asked for a DIFFERENT delivery codec -- the
        escalation path (see module docstring point 1). `delivery_codec` unset, or
        equal to `file_codec`, stays on the cheap single-encode path."""
        return self.delivery_codec is not None and self.delivery_codec != self.file_codec


def _validate(spec):
    if not spec.device or not spec.device.strip():
        raise AcquireSpecError("device must not be empty")

    _validate_segment_pattern(spec.segment_pattern)

    if spec.duration_s is not None and spec.duration_s <= 0:
        raise AcquireSpecError(
            "duration_s must be positive when set, got {!r}".format(spec.duration_s)
        )

    if (spec.delivery_url is None) != (spec.delivery_format is None):
        raise AcquireSpecError(
            "delivery_url and delivery_format must be set together (both or neither) -- "
            "got delivery_url={!r} delivery_format={!r}".format(
                spec.delivery_url, spec.delivery_format
            )
        )

    if spec.delivery_format is not None and spec.delivery_format not in _VALID_DELIVERY_FORMATS:
        raise AcquireSpecError(
            "delivery_format must be one of {!r}, got {!r}".format(
                _VALID_DELIVERY_FORMATS, spec.delivery_format
            )
        )


def _validate_segment_pattern(pattern):
    if not pattern:
        raise AcquireSpecError("segment_pattern must not be empty")

    for ch in _TEE_UNSAFE_CHARS:
        if ch in pattern:
            raise AcquireSpecError(
                "segment_pattern {!r} contains {!r} -- the tee muxer treats '\\\\' as an "
                "escape character and ':' / '|' / '[' / ']' as its own option syntax, so "
                "a Windows absolute path (or any of these characters) inside a tee slave "
                "spec is silently mangled. Pass a RELATIVE pattern with forward slashes "
                "only and set ffmpeg's working directory instead.".format(pattern, ch)
            )

    if pattern.startswith("/"):
        raise AcquireSpecError(
            "segment_pattern {!r} is absolute -- the tee muxer's slave spec silently "
            "mangles a path placed inside it. Pass a RELATIVE pattern instead and set "
            "ffmpeg's working directory.".format(pattern)
        )

    if "%" not in pattern:
        raise AcquireSpecError(
            "segment_pattern {!r} has no '%' strftime pattern -- with strftime=1 a "
            "non-templated name would make every restart overwrite the same file, which "
            "is the exact overwrite-on-restart ambiguity segmenting exists to remove. "
            "Include a strftime pattern such as %Y%m%d-%H%M%S.".format(pattern)
        )


def _slave_options(opts):
    """Deterministic `[k=v:k=v:...]` rendering -- sorted key order, so the builder's
    output can be diffed against a checked-in reference script rather than only
    matched on substrings."""
    return "[{}]".format(":".join("{}={}".format(k, opts[k]) for k in sorted(opts)))


def _format_select(select):
    """A single stream index is unquoted (`select=0`); a multi-index list is escaped
    with single quotes (`select='0,1'`) because the tee muxer's option grammar uses `,`
    to separate a list and escaping it is what keeps a future multi-index slave
    unambiguous."""
    if isinstance(select, int):
        return str(select)
    return "'{}'".format(",".join(str(i) for i in select))


def _segment_slave_options(spec, select=None):
    opts = {
        "f": "segment",
        "reset_timestamps": "1",
        "segment_format": spec.segment_format,
        "segment_time": str(spec.segment_time_s),
        "strftime": "1",
    }
    if select is not None:
        opts["select"] = _format_select(select)
    return opts


_H264_ENCODERS = ("libx264", "h264_nvenc", "h264_qsv", "h264_amf", "h264_mf")


def _is_h264(codec):
    return codec in _H264_ENCODERS


def _needs_global_header(spec):
    """True when any leg's codec stores parameter sets in the container header."""
    codecs = [spec.file_codec]
    if spec.delivery_codec is not None:
        codecs.append(spec.delivery_codec)
    return any(_is_h264(c) for c in codecs)


def _delivery_slave_options(spec, select=None):
    opts = {"f": spec.delivery_format, "onfail": "ignore"}
    if select is not None:
        opts["select"] = _format_select(select)
    # `-flags +global_header` (added in build_ffmpeg_argv so matroska can write its header)
    # moves H.264 parameter sets out of the bitstream; MPEG-TS needs them back inline or
    # the stream is undecodable. This bsf restores them for this slave only.
    delivery_codec = spec.delivery_codec or spec.file_codec
    if spec.delivery_format == "mpegts" and _is_h264(delivery_codec):
        opts["bsfs/v"] = "h264_mp4toannexb"
    return opts


def build_tee_spec(spec):
    """`[k=v:...]<relative-file-pattern>|[k=v:...]<delivery-url>`.

    The file slave NEVER carries `onfail` -- if the recording fails, the run should
    stop being believed (D-88). The delivery slave ALWAYS carries `onfail=ignore` --
    a dead network, a powered-off vision box or a crashed DLC run costs the live view
    and nothing else.
    """
    if spec.delivery_url is None:
        raise AcquireSpecError(
            "build_tee_spec requires delivery_url -- use the plain '-f segment' form "
            "(build_ffmpeg_argv with no delivery leg) when there is no delivery"
        )

    select_file = 0 if spec.two_stream else None
    select_delivery = 1 if spec.two_stream else None

    file_slave = _slave_options(_segment_slave_options(spec, select=select_file))
    delivery_slave = _slave_options(_delivery_slave_options(spec, select=select_delivery))

    return "{}{}|{}{}".format(file_slave, spec.segment_pattern, delivery_slave, spec.delivery_url)


def _encode_flags(spec):
    """The `-c:v`/`-q:v`/extra flags, for either the single-encode or two-stream form.
    `-q:v` is emitted only for the `mjpeg` codec -- it is meaningless for an `h264_*`
    encoder, whose quality knob (if any) belongs in `file_extra`/`delivery_extra`
    instead (module docstring point 1)."""
    if not spec.two_stream:
        flags = ["-c:v", spec.file_codec]
        if spec.file_codec == "mjpeg":
            flags += ["-q:v", spec.file_quality]
        flags += list(spec.file_extra)
        flags += list(spec.delivery_extra)
        return flags

    flags = ["-c:v:0", spec.file_codec]
    if spec.file_codec == "mjpeg":
        flags += ["-q:v:0", spec.file_quality]
    flags += list(spec.file_extra)
    flags += ["-c:v:1", spec.delivery_codec]
    if spec.delivery_codec == "mjpeg":
        flags += ["-q:v:1", spec.file_quality]
    flags += list(spec.delivery_extra)
    return flags


def build_ffmpeg_argv(spec):
    """The full argv, as a `list[str]` -- never a joined string, so no shell-quoting
    question can arise for whoever runs it. Order matters and is asserted by this
    module's own tests: ffmpeg's input options must precede `-i`, and the codec/
    fps_mode/duration options must precede the output (`-f tee` or `-f segment`)."""
    argv = ["-hide_banner", "-f", "dshow", "-rtbufsize", spec.rtbufsize, "-i", "video={}".format(spec.device)]

    # The tee muxer needs an EXPLICIT -map: ffmpeg's automatic stream selection does not
    # apply to it, and without one the tee output carries no streams and dies with
    # "Output file does not contain any stream". Reproduced on the rig 2026-09-10 on the
    # first real single-encode invocation. A plain single output needs no -map.
    if spec.two_stream:
        argv += ["-map", "0:v", "-map", "0:v"]
    elif spec.delivery_url is not None:
        argv += ["-map", "0:v"]

    argv += _encode_flags(spec)

    # Matroska carries H.264 parameter sets in the container header, so libx264 must be
    # told to emit them out-of-band; MPEG-TS wants them back inline, which is what
    # h264_mp4toannexb (added to that slave in build_tee_spec) restores. Without this the
    # segment slave fails with "error writing header: Invalid data found when processing
    # input" -- verified, and verified fixed, 2026-09-10.
    if spec.delivery_url is not None and _needs_global_header(spec):
        argv += ["-flags", "+global_header"]

    if spec.two_stream:
        argv += ["-fps_mode:v:0", "passthrough", "-fps_mode:v:1", "passthrough"]
    else:
        argv += ["-fps_mode", "passthrough"]

    if spec.duration_s is not None:
        argv += ["-t", str(spec.duration_s)]

    if spec.delivery_url is not None:
        argv += ["-f", "tee", build_tee_spec(spec)]
    else:
        argv += [
            "-f", "segment",
            "-segment_time", str(spec.segment_time_s),
            "-reset_timestamps", "1",
            "-strftime", "1",
            "-segment_format", spec.segment_format,
            spec.segment_pattern,
        ]

    return argv
