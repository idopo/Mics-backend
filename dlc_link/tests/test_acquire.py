"""Tests for dlc_link.acquire (Task 1, plan 38-07).

No fixture needs a camera, ffmpeg, a network or a Windows host -- every test here runs
on the Linux dev host against pure functions.
"""
import inspect
import itertools

import pytest

from dlc_link import acquire as acquire_module
from dlc_link.acquire import (
    AcquireSpec,
    AcquireSpecError,
    build_ffmpeg_argv,
    build_tee_spec,
)


def _spec(**overrides):
    kwargs = dict(
        device="DMK 33GP1300 [BR2_UP]",
        segment_pattern="rig-%Y%m%d-%H%M%S.mkv",
        segment_time_s=20,
    )
    kwargs.update(overrides)
    return AcquireSpec(**kwargs)


def _delivery_matrix():
    """Every (delivery on/off, transport, encode-form, duration) combination the
    invariant tests below must hold for."""
    rows = [_spec()]  # no delivery at all
    rows.append(_spec(duration_s=60))
    for fmt in ("mpjpeg", "mpegts"):
        rows.append(_spec(delivery_url="tcp://198.51.100.7:9001", delivery_format=fmt))
        rows.append(_spec(delivery_url="tcp://198.51.100.7:9001", delivery_format=fmt, duration_s=120))
        rows.append(
            _spec(
                delivery_url="tcp://198.51.100.7:9001",
                delivery_format=fmt,
                delivery_codec="h264_nvenc",
                delivery_extra=("-g", "1"),
            )
        )
    return rows


# --- invariants that must hold for EVERY accepted AcquireSpec -----------------------


@pytest.mark.parametrize("spec", _delivery_matrix())
def test_no_token_or_tee_spec_substring_contains_listen(spec):
    argv = build_ffmpeg_argv(spec)
    for token in argv:
        assert "listen" not in token.lower()


@pytest.mark.parametrize("spec", _delivery_matrix())
def test_no_verbosity_flag_is_ever_emitted(spec):
    argv = build_ffmpeg_argv(spec)
    assert "-v" not in argv
    assert "-loglevel" not in argv


@pytest.mark.parametrize("spec", [s for s in _delivery_matrix() if s.delivery_url])
def test_file_slave_has_no_onfail_and_delivery_slave_has_onfail_ignore(spec):
    tee_spec = build_tee_spec(spec)
    file_slave, delivery_slave = tee_spec.split("|", 1)
    assert "onfail" not in file_slave
    assert "onfail=ignore" in delivery_slave


@pytest.mark.parametrize("spec", [s for s in _delivery_matrix() if s.delivery_url])
def test_tee_spec_has_no_backslash_and_no_pipe_inside_a_filename(spec):
    tee_spec = build_tee_spec(spec)
    assert "\\" not in tee_spec
    file_slave, delivery_slave = tee_spec.split("|", 1)
    # The filename/url portion is whatever follows the closing ']' of the option list.
    filename = file_slave.split("]", 1)[1]
    url = delivery_slave.split("]", 1)[1]
    assert "|" not in filename
    assert "|" not in url


@pytest.mark.parametrize("spec", _delivery_matrix())
def test_build_ffmpeg_argv_returns_a_list_of_str_never_a_joined_string(spec):
    argv = build_ffmpeg_argv(spec)
    assert isinstance(argv, list)
    for token in argv:
        assert isinstance(token, str)


@pytest.mark.parametrize("spec", _delivery_matrix())
def test_dshow_input_options_precede_any_output_option(spec):
    argv = build_ffmpeg_argv(spec)
    assert argv[:7] == [
        "-hide_banner", "-f", "dshow", "-rtbufsize", spec.rtbufsize, "-i", "video={}".format(spec.device),
    ]
    output_flag_index = next(i for i, tok in enumerate(argv) if tok == "-f" and i > 2)
    assert output_flag_index >= 7


@pytest.mark.parametrize("spec", [s for s in _delivery_matrix() if not s.two_stream])
def test_fps_mode_passthrough_exactly_once_bare_in_single_encode_form(spec):
    argv = build_ffmpeg_argv(spec)
    assert argv.count("-fps_mode") == 1
    idx = argv.index("-fps_mode")
    assert argv[idx + 1] == "passthrough"
    assert "-fps_mode:v:0" not in argv
    assert "-fps_mode:v:1" not in argv


@pytest.mark.parametrize("spec", [s for s in _delivery_matrix() if s.two_stream])
def test_fps_mode_is_per_stream_exactly_once_each_in_two_stream_form(spec):
    argv = build_ffmpeg_argv(spec)
    assert argv.count("-fps_mode:v:0") == 1
    assert argv.count("-fps_mode:v:1") == 1
    assert "-fps_mode" not in argv


@pytest.mark.parametrize("spec", [s for s in _delivery_matrix() if s.delivery_url])
def test_segment_slave_carries_the_required_options(spec):
    tee_spec = build_tee_spec(spec)
    file_slave = tee_spec.split("|", 1)[0]
    assert "f=segment" in file_slave
    assert "segment_time={}".format(spec.segment_time_s) in file_slave
    assert "reset_timestamps=1" in file_slave
    assert "strftime=1" in file_slave
    assert "segment_format={}".format(spec.segment_format) in file_slave


# --- shape ---------------------------------------------------------------------------


def test_no_delivery_produces_plain_segment_output_with_no_tee_token():
    spec = _spec()
    argv = build_ffmpeg_argv(spec)
    assert "-f" in argv
    assert "tee" not in argv
    f_indices = [i for i, tok in enumerate(argv) if tok == "-f"]
    output_f_index = f_indices[-1]
    assert argv[output_f_index + 1] == "segment"


def test_delivery_with_codec_unset_emits_one_encode_for_both_legs():
    spec = _spec(delivery_url="tcp://198.51.100.7:9001", delivery_format="mpegts")
    argv = build_ffmpeg_argv(spec)
    assert argv.count("-c:v") == 1
    assert "-map" not in argv
    assert "-c:v:0" not in argv
    assert "-c:v:1" not in argv


def test_delivery_with_codec_equal_to_file_codec_is_also_single_encode():
    spec = _spec(
        delivery_url="tcp://198.51.100.7:9001", delivery_format="mpegts", delivery_codec="mjpeg",
    )
    argv = build_ffmpeg_argv(spec)
    assert argv.count("-c:v") == 1
    assert "-map" not in argv


def test_delivery_with_different_codec_emits_two_stream_form():
    spec = _spec(
        delivery_url="tcp://198.51.100.7:9001", delivery_format="mpegts", delivery_codec="h264_nvenc",
    )
    argv = build_ffmpeg_argv(spec)
    assert argv.count("-map") == 2
    assert argv.count("0:v") == 2
    assert "-c:v:0" in argv
    assert "-c:v:1" in argv
    tee_spec = build_tee_spec(spec)
    file_slave, delivery_slave = tee_spec.split("|", 1)
    assert "select=0" in file_slave
    assert "select=1" in delivery_slave


def test_select_is_unquoted_for_a_single_index_and_quoted_for_multiple():
    from dlc_link.acquire import _format_select
    assert _format_select(0) == "0"
    assert _format_select(1) == "1"
    assert _format_select((0, 1)) == "'0,1'"


def test_duration_emits_dash_t_immediately_before_output_flag():
    spec = _spec(duration_s=60)
    argv = build_ffmpeg_argv(spec)
    t_index = argv.index("-t")
    assert argv[t_index + 1] == "60"
    # The next thing after the duration pair is the output '-f'.
    assert argv[t_index + 2] == "-f"


def test_duration_unset_emits_nothing():
    spec = _spec()
    argv = build_ffmpeg_argv(spec)
    assert "-t" not in argv


def test_file_extra_and_delivery_extra_passed_through_verbatim_in_order():
    spec = _spec(
        delivery_url="tcp://198.51.100.7:9001",
        delivery_format="mpegts",
        delivery_codec="h264_nvenc",
        file_extra=("-pix_fmt", "yuvj420p"),
        delivery_extra=("-g", "1"),
    )
    argv = build_ffmpeg_argv(spec)
    file_extra_idx = argv.index("-pix_fmt")
    assert argv[file_extra_idx:file_extra_idx + 2] == ["-pix_fmt", "yuvj420p"]
    delivery_extra_idx = argv.index("-g")
    assert argv[delivery_extra_idx:delivery_extra_idx + 2] == ["-g", "1"]
    # file_extra must appear after the file codec flag, before the delivery codec flag.
    assert argv.index("-c:v:0") < file_extra_idx < argv.index("-c:v:1") < delivery_extra_idx


# --- refusals --------------------------------------------------------------------------


@pytest.mark.parametrize("bad_char", ["\\", ":", "|", "[", "]"])
def test_segment_pattern_with_tee_unsafe_char_is_refused(bad_char):
    with pytest.raises(AcquireSpecError, match="tee"):
        _spec(segment_pattern="rig{}-%Y%m%d.mkv".format(bad_char))


def test_absolute_segment_pattern_is_refused():
    with pytest.raises(AcquireSpecError, match="absolute"):
        _spec(segment_pattern="/rig-%Y%m%d.mkv")


def test_segment_pattern_with_no_strftime_percent_is_refused():
    with pytest.raises(AcquireSpecError, match="strftime|overwrite"):
        _spec(segment_pattern="rig.mkv")


def test_delivery_url_without_delivery_format_is_refused():
    with pytest.raises(AcquireSpecError):
        _spec(delivery_url="tcp://198.51.100.7:9001")


def test_delivery_format_without_delivery_url_is_refused():
    with pytest.raises(AcquireSpecError):
        _spec(delivery_format="mpegts")


def test_unknown_delivery_format_is_refused():
    with pytest.raises(AcquireSpecError):
        _spec(delivery_url="tcp://198.51.100.7:9001", delivery_format="rtsp")


def test_empty_device_is_refused():
    with pytest.raises(AcquireSpecError):
        _spec(device="")


def test_whitespace_only_device_is_refused():
    with pytest.raises(AcquireSpecError):
        _spec(device="   ")


@pytest.mark.parametrize("bad_duration", [0, -1, -60])
def test_non_positive_duration_is_refused(bad_duration):
    with pytest.raises(AcquireSpecError):
        _spec(duration_s=bad_duration)


# --- nothing hardcoded -----------------------------------------------------------------


def test_acquire_module_has_no_hardcoded_endpoint_or_device_literal():
    source_text = inspect.getsource(acquire_module)
    for forbidden in ("132.77.", "DMK ", "8080", "http://", "tcp://", "udp://"):
        assert forbidden not in source_text, "found forbidden literal {!r}".format(forbidden)


def test_acquire_module_has_no_drive_letter_literal():
    source_text = inspect.getsource(acquire_module)
    assert "D:" not in source_text


# --- build_tee_spec misuse --------------------------------------------------------------


def test_build_tee_spec_without_delivery_url_raises():
    spec = _spec()
    with pytest.raises(AcquireSpecError):
        build_tee_spec(spec)
