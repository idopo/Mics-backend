"""Tests for dlc_link.acquire_cli -- the `dlc-link-relay` console script (Task 2,
plan 38-07)."""
import ast
import inspect
import itertools
import os
import tomllib

import pytest

from dlc_link import acquire_cli as acquire_cli_module
from dlc_link.acquire_cli import main

_HERE = os.path.dirname(__file__)
_DLC_LINK_ROOT = os.path.abspath(os.path.join(_HERE, ".."))

# The EXACT placeholder parameter set scripts/mics-acquire.ps1 was generated with.
# Documentation-range address (RFC 5737) and a generic device name -- never the rig's.
_REFERENCE_ARGV = [
    "--device", "Generic Video Device",
    "--segment-pattern", "mics-acq-%Y%m%d-%H%M%S.mkv",
    "--segment-time", "20",
    "--delivery", "tcp://198.51.100.7:9001",
    "--transport", "mpjpeg-tcp",
    "--max-restarts", "5",
    "--print", "supervisor",
]


def _run(argv, capsys):
    rc = main(argv)
    out = capsys.readouterr().out
    return rc, out


def _snapshot(directory):
    return {
        os.path.relpath(os.path.join(root, name), directory)
        for root, _, files in os.walk(directory)
        for name in files
    }


# --- writes nothing by default -------------------------------------------------------


def test_default_invocation_writes_no_file(tmp_path, capsys):
    before = _snapshot(str(tmp_path))
    cwd = os.getcwd()
    os.chdir(str(tmp_path))
    try:
        rc, out = _run(["--device", "X", "--segment-pattern", "r-%Y%m%d.mkv"], capsys)
    finally:
        os.chdir(cwd)
    after = _snapshot(str(tmp_path))
    assert rc == 0
    assert before == after
    assert "-hide_banner" in out
    assert "$a=@(" in out


def test_default_print_mode_is_argv_and_includes_powershell_block(capsys):
    rc, out = _run(["--device", "X", "--segment-pattern", "r-%Y%m%d.mkv"], capsys)
    assert rc == 0
    assert "-hide_banner" in out
    assert "$a=@(" in out
    assert "Start-Process" not in out  # supervisor body not printed in default mode


def test_print_supervisor_shows_the_full_script(capsys):
    rc, out = _run(
        ["--device", "X", "--segment-pattern", "r-%Y%m%d.mkv", "--print", "supervisor"], capsys,
    )
    assert rc == 0
    assert "Start-Process @sp" in out
    assert "New-Item -ItemType Directory" in out


def test_print_both_shows_both_with_a_labelled_separator(capsys):
    rc, out = _run(
        ["--device", "X", "--segment-pattern", "r-%Y%m%d.mkv", "--print", "both"], capsys,
    )
    assert rc == 0
    assert "$a=@(" in out
    assert "Start-Process @sp" in out
    assert "# --- supervisor ---" in out


def test_printed_powershell_block_longest_line_under_100(capsys):
    """Only the PowerShell array block (and the full supervisor) is promised to be
    paste-safe -- the raw 'one token per line' dump is for human readability and is
    deliberately not chunked (a human reads one ffmpeg flag per line either way)."""
    rc, out = _run(
        [
            "--device", "DMK 33GP1300 [BR2_UP]", "--segment-pattern", "rig-%Y%m%d-%H%M%S.mkv",
            "--delivery", "tcp://198.51.100.7:9001", "--transport", "mpjpeg-tcp",
            "--print", "both",
        ],
        capsys,
    )
    assert rc == 0
    powershell_lines = [
        line for line in out.splitlines()
        if line.startswith("$") or line.startswith("New-Item") or line.startswith("Write-Host")
        or line.strip().startswith("$") or line.strip() in ("{", "}")
    ]
    assert powershell_lines
    for line in powershell_lines:
        assert len(line) < 100


# --- --out is the only writing path ---------------------------------------------------


def test_out_writes_the_supervisor_and_echoes_the_absolute_path(tmp_path, capsys):
    out_path = tmp_path / "sup.ps1"
    rc, out = _run(
        ["--device", "X", "--segment-pattern", "r-%Y%m%d.mkv", "--out", str(out_path)], capsys,
    )
    assert rc == 0
    assert str(out_path.resolve()) in out
    assert out_path.exists()
    assert "Start-Process @sp" in out_path.read_text()


def test_out_inside_a_dlc_project_directory_is_refused(tmp_path, capsys):
    project_dir = tmp_path / "my_dlc_project"
    project_dir.mkdir()
    (project_dir / "config.yaml").write_text("bodyparts: []\n")
    out_path = project_dir / "sup.ps1"
    rc, out = _run(
        ["--device", "X", "--segment-pattern", "r-%Y%m%d.mkv", "--out", str(out_path)], capsys,
    )
    assert rc == 1
    assert not out_path.exists()


def test_out_inside_a_descendant_of_a_dlc_project_directory_is_refused(tmp_path, capsys):
    project_dir = tmp_path / "my_dlc_project"
    sub_dir = project_dir / "scratch"
    sub_dir.mkdir(parents=True)
    (project_dir / "config.yaml").write_text("bodyparts: []\n")
    out_path = sub_dir / "sup.ps1"
    rc, out = _run(
        ["--device", "X", "--segment-pattern", "r-%Y%m%d.mkv", "--out", str(out_path)], capsys,
    )
    assert rc == 1
    assert not out_path.exists()


# --- --delivery / --transport pairing -------------------------------------------------


def test_delivery_without_transport_exits_2(capsys):
    with pytest.raises(SystemExit) as excinfo:
        main(["--device", "X", "--segment-pattern", "r-%Y%m%d.mkv", "--delivery", "tcp://198.51.100.7:9001"])
    assert excinfo.value.code == 2
    err = capsys.readouterr().err
    assert "--transport" in err


def test_transport_has_no_default_and_help_cites_the_validation_doc():
    parser = acquire_cli_module._build_parser()
    help_text = parser.format_help()
    assert "38-ACQUISITION-VALIDATION.md" in help_text
    transport_action = next(a for a in parser._actions if a.dest == "transport")
    assert transport_action.default is None


# --- missing --device ------------------------------------------------------------------


def test_missing_device_exits_2_naming_the_discovery_command(capsys):
    with pytest.raises(SystemExit) as excinfo:
        main(["--segment-pattern", "r-%Y%m%d.mkv"])
    assert excinfo.value.code == 2
    err = capsys.readouterr().err
    assert "-list_devices" in err
    assert "dshow" in err


# --- no flag combination can produce -listen -------------------------------------------

_TRANSPORT_CHOICES = ["mpjpeg-tcp", "mpegts-udp"]
_CODEC_CHOICES = [None, "mjpeg", "h264_nvenc"]


@pytest.mark.parametrize(
    "transport,delivery_codec", list(itertools.product(_TRANSPORT_CHOICES, _CODEC_CHOICES))
)
def test_no_flag_combination_emits_listen(transport, delivery_codec, capsys):
    argv = [
        "--device", "X", "--segment-pattern", "r-%Y%m%d.mkv",
        "--delivery", "tcp://198.51.100.7:9001", "--transport", transport,
    ]
    if delivery_codec is not None:
        argv += ["--delivery-codec", delivery_codec]
    rc, out = _run(argv, capsys)
    assert rc == 0
    assert "listen" not in out.lower()


def test_no_flag_combination_emits_listen_without_delivery(capsys):
    rc, out = _run(["--device", "X", "--segment-pattern", "r-%Y%m%d.mkv", "--print", "both"], capsys)
    assert rc == 0
    assert "listen" not in out.lower()


# --- import surface ---------------------------------------------------------------------


_STDLIB_TOP_LEVEL_IMPORTS = {"argparse", "os", "sys"}
_FORBIDDEN_MODULES = ("cv2", "numpy", "torch", "dlclive", "mics_link")


def test_module_imports_only_stdlib_and_dlc_link():
    source_text = inspect.getsource(acquire_cli_module)
    tree = ast.parse(source_text)
    modules = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            modules += [alias.name for alias in node.names]
        elif isinstance(node, ast.ImportFrom) and node.module:
            modules.append(node.module)

    assert modules, "expected at least one import statement"
    for module in modules:
        top_level = module.split(".")[0]
        assert top_level not in _FORBIDDEN_MODULES
        assert module.startswith("dlc_link") or top_level in _STDLIB_TOP_LEVEL_IMPORTS, module


def test_help_works_with_no_cv2_torch_or_dlclive_importable(capsys):
    # The module itself never imports them; asserted structurally above. Here we just
    # confirm --help succeeds without error, which is what "works in a kit-only
    # install" means operationally.
    with pytest.raises(SystemExit) as excinfo:
        main(["--help"])
    assert excinfo.value.code == 0


# --- no rig address literal ----------------------------------------------------------


def test_module_has_no_132_address_literal():
    source_text = inspect.getsource(acquire_cli_module)
    assert "132.77." not in source_text


# --- pyproject entry point -------------------------------------------------------------


def test_pyproject_declares_dlc_link_relay_and_keeps_existing_entries():
    with open(os.path.join(_DLC_LINK_ROOT, "pyproject.toml"), "rb") as handle:
        data = tomllib.load(handle)
    scripts = data["project"]["scripts"]
    assert scripts["dlc-link-relay"] == "dlc_link.acquire_cli:main"
    assert scripts["dlc-link-generate"] == "dlc_link.generate:main"
    assert scripts["dlc-link-convert"] == "dlc_link.convert:main"
    assert scripts["dlc-link-live"] == "dlc_link.live:main"


# --- reference script is byte-identical to the generator -------------------------------


def test_reference_script_is_byte_identical_to_generator_output(tmp_path, capsys):
    generated_path = tmp_path / "generated.ps1"
    rc, _ = _run(_REFERENCE_ARGV + ["--out", str(generated_path)], capsys)
    assert rc == 0
    reference_path = os.path.join(_DLC_LINK_ROOT, "scripts", "mics-acquire.ps1")
    with open(reference_path, "rb") as handle:
        reference_bytes = handle.read()
    assert generated_path.read_bytes() == reference_bytes


def test_reference_script_uses_documentation_range_address_and_no_rig_literal():
    reference_path = os.path.join(_DLC_LINK_ROOT, "scripts", "mics-acquire.ps1")
    with open(reference_path) as handle:
        text = handle.read()
    assert "198.51.100." in text
    assert "132.77." not in text
    assert "DMK" not in text


def test_reference_script_has_no_line_over_99_characters():
    reference_path = os.path.join(_DLC_LINK_ROOT, "scripts", "mics-acquire.ps1")
    with open(reference_path) as handle:
        for line in handle:
            assert len(line.rstrip("\n")) <= 99
