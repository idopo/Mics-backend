"""Tests for dlc_link.source (Task 1, plan 38-01)."""
import inspect

import pytest

from dlc_link import source as source_module
from dlc_link.source import (
    SourceError,
    SourceSpec,
    classify_source,
    fps_refusal,
    pacing_for,
    read_failure_is_terminal,
)


# --- classify_source -------------------------------------------------------------


def test_all_digits_classifies_as_device_with_int_arg():
    spec = classify_source("0")
    assert spec.kind == "device"
    assert type(spec.capture_arg) is int
    assert spec.capture_arg == 0


def test_multi_digit_classifies_as_device():
    spec = classify_source("12")
    assert spec.kind == "device"
    assert type(spec.capture_arg) is int
    assert spec.capture_arg == 12


def test_leading_zeros_all_digits_is_still_device():
    spec = classify_source("00")
    assert spec.kind == "device"
    assert type(spec.capture_arg) is int
    assert spec.capture_arg == 0


def test_rtsp_url_classifies_as_stream_unchanged():
    spec = classify_source("rtsp://cam/stream")
    assert spec.kind == "stream"
    assert spec.capture_arg == "rtsp://cam/stream"


def test_http_url_classifies_as_stream_unchanged():
    spec = classify_source("http://1.2.3.4:8080/video")
    assert spec.kind == "stream"
    assert spec.capture_arg == "http://1.2.3.4:8080/video"


def test_windows_path_classifies_as_file_not_stream():
    spec = classify_source("C:\\videos\\Config1_5mice.mp4")
    assert spec.kind == "file"
    assert spec.capture_arg == "C:\\videos\\Config1_5mice.mp4"


def test_posix_path_classifies_as_file():
    spec = classify_source("/home/x/clip.mp4")
    assert spec.kind == "file"


def test_empty_string_raises_source_error():
    with pytest.raises(SourceError):
        classify_source("")


def test_whitespace_only_raises_source_error():
    with pytest.raises(SourceError):
        classify_source("   ")


def test_negative_device_index_raises_source_error_naming_the_reason():
    with pytest.raises(SourceError) as exc_info:
        classify_source("-1")
    assert "negative" in str(exc_info.value)


# --- pacing_for / read_failure_is_terminal ----------------------------------------


def test_pacing_for_file_is_true():
    assert pacing_for("file") is True


def test_pacing_for_device_is_false():
    assert pacing_for("device") is False


def test_pacing_for_stream_is_false():
    assert pacing_for("stream") is False


def test_read_failure_is_terminal_for_file_is_true():
    assert read_failure_is_terminal("file") is True


def test_read_failure_is_terminal_for_device_is_false():
    assert read_failure_is_terminal("device") is False


def test_read_failure_is_terminal_for_stream_is_false():
    assert read_failure_is_terminal("stream") is False


# --- fps_refusal -------------------------------------------------------------------


def test_fps_refusal_on_camera_names_the_source_kind():
    message = fps_refusal("device", 30.0)
    assert message is not None
    assert "device" in message


def test_fps_refusal_on_stream_names_the_source_kind():
    message = fps_refusal("stream", 30.0)
    assert message is not None
    assert "stream" in message


def test_fps_refusal_on_file_is_none():
    assert fps_refusal("file", 30.0) is None


def test_fps_refusal_with_no_fps_is_none_even_for_a_camera():
    assert fps_refusal("device", None) is None


# --- static source assertions -------------------------------------------------------


def test_module_has_no_cv2_or_dlclive_import():
    source_text = inspect.getsource(source_module)
    assert "import cv2" not in source_text
    assert "import dlclive" not in source_text
    assert "from dlclive" not in source_text


def test_describe_for_device_contains_the_typed_digits():
    spec = classify_source("12")
    assert "12" in spec.describe()


def test_describe_for_stream_contains_the_url():
    spec = classify_source("rtsp://cam/stream")
    assert "rtsp://cam/stream" in spec.describe()


def test_describe_for_file_contains_the_path():
    spec = classify_source("/home/x/clip.mp4")
    assert "/home/x/clip.mp4" in spec.describe()


def test_sourcespec_is_constructible_directly():
    # SourceSpec is a plain, directly-constructible record -- not a closed enum --
    # so a future fourth kind (D-75) is an addition, not a refactor of every consumer.
    spec = SourceSpec(kind="device", capture_arg=0, original="0")
    assert spec.kind == "device"
