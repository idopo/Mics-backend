"""Tests for dlc_link.acquire_supervisor (Task 1, plan 38-07)."""
import inspect
import re

from dlc_link import acquire_supervisor as supervisor_module
from dlc_link.acquire_supervisor import build_supervisor_ps1, render_argv_lines

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
        '"log"',
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


def test_builds_argument_array_and_invokes_ffmpeg_with_the_call_operator():
    text = _build()
    assert re.search(r"^\$a=@\(", text, re.MULTILINE)
    assert "$a+=@(" in text
    assert "& $ff @a" in text


def test_never_uses_start_process_argument_list():
    # Windows PowerShell 5.1 joins -ArgumentList elements with spaces and quotes none of
    # them, so 'video=DMK 33GP1300 [BR2_UP]' reaches ffmpeg as three arguments. The call
    # operator quotes an element containing spaces.
    text = _build()
    assert "Start-Process" not in text
    assert "ArgumentList" not in text


def test_every_attempt_gets_its_own_ffreport_log_at_info_level():
    # The log is witness 3 of the completeness test. FFREPORT is ffmpeg writing its own
    # log, so no PowerShell stderr redirection (which wraps native stderr in error
    # records on 5.1) is involved. level=32 is info: `frame dropped` warnings survive.
    text = _build()
    loop_body = text[text.index("while ("):]
    assert "$stamp" in loop_body
    assert '$env:FFREPORT = "file=$lg/acq-$stamp-attempt${attempt}.log:level=32"' in loop_body
    assert "RedirectStandardError" not in text


def test_runs_inside_the_segment_directory():
    text = _build()
    assert '$wd = "."' in text
    push = text.index("Push-Location $wd")
    assert push < text.index("while (")
    assert "Pop-Location" in text[text.index("while ("):]


def test_a_clean_exit_is_not_restarted():
    # Exit 0 is ffmpeg finishing on purpose ('q' pressed or -t reached); restarting it
    # would start a new recording nobody asked for.
    text = _build()
    loop_body = text[text.index("while ("):]
    assert "$lastExit = $LASTEXITCODE" in loop_body
    assert "if ($lastExit -eq 0) { break }" in loop_body


def test_restart_loop_bounded_and_reports_attempt_number_and_previous_exit_code():
    text = _build(max_restarts=3)
    assert "$maxRestarts = 3" in text
    assert "while ($attempt -lt $maxRestarts)" in text
    assert "restart attempt $attempt after previous exit code $lastExit" in text


def test_final_line_names_exit_code_and_log_path():
    text = _build()
    assert re.search(r"stopped after.*exit code.*log", text, re.IGNORECASE)


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


def test_module_has_no_hardcoded_endpoint_or_device_literal():
    source_text = inspect.getsource(supervisor_module)
    for forbidden in ("132.77.", "DMK ", "8080", "http://", "tcp://", "udp://"):
        assert forbidden not in source_text, "found forbidden literal {!r}".format(forbidden)


def test_long_token_reconstructs_exactly_across_declaration_lines():
    """The tee spec is one token with the file leg and delivery leg both inside it --
    long enough on its own to exceed a single array-assignment line. The declaration
    lines must reconstruct it byte-for-byte when concatenated."""
    long_value = (
        "[f=segment:reset_timestamps=1:segment_format=matroska:segment_time=20:strftime=1]"
        "rig-%Y%m%d-%H%M%S.mkv|[f=mpjpeg:onfail=ignore]tcp://198.51.100.7:9001"
    )
    text = build_supervisor_ps1(
        '"$env:USERPROFILE\\ffmpeg\\ffmpeg.exe"',
        ["-f", "tee", long_value],
        '"."', '".\\log"', 3, 5,
    )
    assert "$t0 = '" in text
    assert "$t0 += '" in text
    for line in text.splitlines():
        assert len(line) < 100


def _ps_single_quoted_value(decl_line):
    """Pulls the raw (un-escaped-back) value out of a `$var = '...'` / `$var += '...'`
    declaration line, reversing the doubled-single-quote escaping this module applies."""
    value = decl_line.split("'", 1)[1][:-1]  # strip up to the opening quote and the trailing one
    return value.replace("''", "'")


def test_render_argv_lines_long_token_reconstructs_to_the_exact_original_value():
    long_value = "x" * 40 + "'" + "y" * 80  # includes an embedded single quote on purpose
    decl_lines, array_lines = render_argv_lines(["-f", "tee", long_value])
    assert any(line.startswith("$t0 = '") for line in decl_lines)
    reconstructed = "".join(_ps_single_quoted_value(line) for line in decl_lines)
    assert reconstructed == long_value
    assert "$t0" in ",".join(array_lines)
