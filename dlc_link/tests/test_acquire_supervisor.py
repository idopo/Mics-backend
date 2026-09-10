"""Tests for dlc_link.acquire_supervisor (Task 1, plan 38-07)."""
import inspect
import re

from dlc_link import acquire_supervisor as supervisor_module
from dlc_link.acquire_supervisor import build_supervisor_ps1

_ARGV = [
    "-hide_banner", "-f", "dshow", "-rtbufsize", "100M", "-i", "video=DMK 33GP1300 [BR2_UP]",
    "-c:v", "mjpeg", "-q:v", "5", "-fps_mode", "passthrough", "-t", "60",
    "-f", "segment", "-segment_time", "20", "-reset_timestamps", "1", "-strftime", "1",
    "-segment_format", "matroska", "rig-%Y%m%d-%H%M%S.mkv",
]


def _build(max_restarts=3, restart_delay_s=5):
    return build_supervisor_ps1(
        '"$env:USERPROFILE\\ffmpeg\\ffmpeg-9.0.1-essentials_build\\bin\\ffmpeg.exe"',
        _ARGV,
        '"."',
        '".\\log"',
        max_restarts,
        restart_delay_s,
    )


def test_longest_line_is_under_100_characters():
    text = _build()
    for line in text.splitlines():
        assert len(line) < 100, "line too long ({}): {!r}".format(len(line), line)


def test_no_python_pip_or_conda_token():
    text = _build().lower()
    assert "python" not in text
    assert "py " not in text
    assert "pip" not in text
    assert "conda" not in text


def test_builds_argument_array_with_short_assignments_and_invokes_via_start_process():
    text = _build()
    assert re.search(r"^\$a=@\(", text, re.MULTILINE)
    assert "$a+=@(" in text
    assert "Start-Process @sp" in text
    assert "-FilePath=$ff" in text.replace(" ", "") or "FilePath=$ff" in text
    assert "-ArgumentList $a" in text or "ArgumentList=$a" in text


def test_every_attempt_gets_its_own_redirect_standard_error_path():
    text = _build()
    assert "-RedirectStandardError" in text
    assert "$attempt" in text
    assert "$stamp" in text
    # The log path is built fresh inside the loop body (one per iteration), not once outside it.
    loop_start = text.index("while (")
    loop_body = text[loop_start:]
    assert "$err = Join-Path" in loop_body


def test_no_new_window_and_wait_used():
    text = _build()
    assert "-NoNewWindow" in text
    assert "-Wait" in text


def test_working_directory_set_to_the_segment_directory_var():
    text = _build()
    assert "WorkingDirectory=$wd" in text
    assert '$wd = "."' in text


def test_restart_loop_bounded_and_reports_attempt_number_and_previous_exit_code():
    text = _build(max_restarts=3)
    assert "$maxRestarts = 3" in text
    assert "while ($attempt -lt $maxRestarts)" in text
    assert "restart attempt $attempt after previous exit code $lastExit" in text


def test_gives_up_line_names_exit_code_and_log_path():
    text = _build()
    assert re.search(r"gave up.*exit code.*log", text, re.IGNORECASE)


def test_ends_with_write_host_lines_naming_segment_and_log_directory():
    text = _build().rstrip("\n")
    lines = text.splitlines()
    assert "segment directory: $wd" in lines[-2]
    assert "log directory: $lg" in lines[-1]


def test_longest_line_stays_under_budget_with_a_long_device_name_and_many_tokens():
    long_argv = _ARGV + ["-extra-flag-with-a-long-value", "some/really/long/value/for/testing/width"]
    text = build_supervisor_ps1(
        '"$env:USERPROFILE\\ffmpeg\\ffmpeg-9.0.1-essentials_build\\bin\\ffmpeg.exe"',
        long_argv, '"."', '".\\log"', 5, 10,
    )
    for line in text.splitlines():
        assert len(line) < 100


def test_module_has_no_subprocess_or_os_import():
    source_text = inspect.getsource(supervisor_module)
    assert "import subprocess" not in source_text
    assert "import os" not in source_text
