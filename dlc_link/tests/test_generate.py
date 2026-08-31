"""Tests for dlc_link.generate / dlc_link.generate_cli / dlc_link.templates (Task 2, plan 35-03)."""
import ast
import hashlib
import os

import pytest

from dlc_link.config_read import SentinelSelectedError, read_dlc_config
from dlc_link.generate import GenerationError, _validate_rendered_lib, generate
from dlc_link.generate_cli import main
from dlc_link.names import flat_signal_names

FIXTURES = os.path.join(os.path.dirname(__file__), "fixtures")
MADLC_CONFIG = os.path.join(FIXTURES, "dlc3_multianimal_config.yaml")
POSE_ORDER_FILE = os.path.join(FIXTURES, "pose_order_declared.txt")

_NO_EGRESS_MARKERS = ("self.send(", "_egress_probe", "def on_run_start", "def on_run_stop")


def _pose_order():
    with open(POSE_ORDER_FILE) as handle:
        return [
            line.strip() for line in handle if line.strip() and not line.strip().startswith("#")
        ]


def _source():
    return read_dlc_config(MADLC_CONFIG)


def _exec_source(source_text):
    namespace = {}
    exec(compile(source_text, "<generated>", "exec"), namespace)
    return namespace


def _snapshot(path):
    """{relpath: size} for every file under `path`, for a before/after comparison."""
    snap = {}
    for root, _dirs, files in os.walk(path):
        for name in files:
            full = os.path.join(root, name)
            snap[os.path.relpath(full, path)] = os.path.getsize(full)
    return snap


def test_two_bodyparts_one_with_coords_yields_four_signals():
    result = generate(
        source=_source(), pose_order=_pose_order(), pose_order_source="probe",
        wanted=["LED_on", "LED_off"], coords_for={"LED_on"}, source_id="dlc_cam1",
    )
    names = flat_signal_names(result.name_map)
    assert sorted(names) == ["led_off_likelihood", "led_on_likelihood", "led_on_x", "led_on_y"]


def test_wanted_covering_every_candidate_raises_d39():
    source = _source()
    every_name = list(source.multianimal_bodyparts) + list(source.unique_bodyparts)
    with pytest.raises(GenerationError) as excinfo:
        generate(
            source=source, pose_order=_pose_order(), pose_order_source="probe",
            wanted=every_name, coords_for=set(), source_id="dlc_cam1", allow_signals=1000,
        )
    message = str(excinfo.value)
    assert "D-39" in message
    assert "72" in message


def test_allow_signals_budget_exceeded_and_override():
    source = _source()
    wanted = ["LED_on", "LED_off", "NW", "NE", "SE", "SW", "nose"]
    with pytest.raises(GenerationError) as excinfo:
        generate(
            source=source, pose_order=_pose_order(), pose_order_source="probe",
            wanted=wanted, coords_for={"LED_on", "NW"}, source_id="dlc_cam1",
        )
    assert "allow-signals" in str(excinfo.value)
    result = generate(
        source=source, pose_order=_pose_order(), pose_order_source="probe",
        wanted=wanted, coords_for={"LED_on", "NW"}, source_id="dlc_cam1", allow_signals=20,
    )
    # 5 likelihood-only signals + 2 signals with coords (3 each) = 5 + 6 = 11.
    assert len(flat_signal_names(result.name_map)) == 11


def test_empty_wanted_raises():
    with pytest.raises(GenerationError):
        generate(
            source=_source(), pose_order=_pose_order(), pose_order_source="probe",
            wanted=[], coords_for=set(), source_id="dlc_cam1",
        )


def test_bodyparts_flag_absent_is_argparse_error(tmp_path):
    with pytest.raises(SystemExit):
        main(["--source-id", "dlc_cam1", "--out-dir", str(tmp_path)])


def test_pose_order_recorded_and_indices_match():
    pose_order = _pose_order()
    result = generate(
        source=_source(), pose_order=pose_order, pose_order_source="probe",
        wanted=["LED_on", "LED_off"], coords_for=set(), source_id="dlc_cam1",
    )
    for bodypart, entry in result.name_map.items():
        assert entry["index"] == pose_order.index(bodypart)


def test_omitting_pose_order_sets_unverified_and_warns(tmp_path, capsys):
    exit_code = main(
        [
            "--config", MADLC_CONFIG, "--source-id", "dlc_cam1",
            "--bodyparts", "LED_on,LED_off", "--out-dir", str(tmp_path),
        ]
    )
    assert exit_code == 0
    assert "D-42" in capsys.readouterr().err
    namespace = _exec_source((tmp_path / "dlc_cam1_signals.py").read_text())
    assert namespace["POSE_ORDER_SOURCE"] == "config-declared-UNVERIFIED"


def test_supplying_pose_order_sets_probe(tmp_path):
    exit_code = main(
        [
            "--config", MADLC_CONFIG, "--source-id", "dlc_cam1",
            "--bodyparts", "LED_on,LED_off", "--pose-order-file", POSE_ORDER_FILE,
            "--out-dir", str(tmp_path),
        ]
    )
    assert exit_code == 0
    namespace = _exec_source((tmp_path / "dlc_cam1_signals.py").read_text())
    assert namespace["POSE_ORDER_SOURCE"] == "probe"


def test_wanted_sentinel_raises_with_sentinel_quoted():
    with pytest.raises(SentinelSelectedError, match="MULTI!"):
        generate(
            source=_source(), pose_order=_pose_order(), pose_order_source="probe",
            wanted=["MULTI!"], coords_for=set(), source_id="dlc_cam1",
        )


def test_real_config_led_selection_exact_signal_set():
    result = generate(
        source=_source(), pose_order=_pose_order(), pose_order_source="probe",
        wanted=["LED_on", "LED_off"], coords_for={"LED_on"}, source_id="dlc_cam1",
    )
    assert sorted(flat_signal_names(result.name_map)) == [
        "led_off_likelihood", "led_on_likelihood", "led_on_x", "led_on_y",
    ]


def test_out_dir_equal_to_config_dir_raises_d44(capsys):
    before = _snapshot(FIXTURES)
    exit_code = main(
        [
            "--config", MADLC_CONFIG, "--source-id", "dlc_cam1", "--bodyparts", "LED_on",
            "--pose-order-file", POSE_ORDER_FILE, "--out-dir", FIXTURES,
        ]
    )
    assert exit_code == 1
    assert "D-44" in capsys.readouterr().err
    assert _snapshot(FIXTURES) == before


def test_out_dir_two_level_descendant_raises_d44(capsys):
    before = _snapshot(FIXTURES)
    descendant = os.path.join(FIXTURES, "a", "b")
    exit_code = main(
        [
            "--config", MADLC_CONFIG, "--source-id", "dlc_cam1", "--bodyparts", "LED_on",
            "--pose-order-file", POSE_ORDER_FILE, "--out-dir", descendant,
        ]
    )
    assert exit_code == 1
    assert "D-44" in capsys.readouterr().err
    assert not os.path.exists(descendant)
    assert _snapshot(FIXTURES) == before


def test_out_dir_sibling_with_shared_prefix_succeeds(tmp_path):
    project_dir = tmp_path / "MultiMice"
    project_dir.mkdir()
    config_path = project_dir / "config.yaml"
    config_path.write_text(open(MADLC_CONFIG).read())
    out_dir = tmp_path / "MultiMice-out"
    exit_code = main(
        [
            "--config", str(config_path), "--source-id", "dlc_cam1", "--bodyparts", "LED_on",
            "--pose-order-file", POSE_ORDER_FILE, "--out-dir", str(out_dir),
        ]
    )
    assert exit_code == 0
    assert (out_dir / "dlc_cam1_lib.py").exists()


def test_out_dir_outside_project_succeeds_and_writes(tmp_path):
    exit_code = main(
        [
            "--config", MADLC_CONFIG, "--source-id", "dlc_cam1", "--bodyparts", "LED_on",
            "--pose-order-file", POSE_ORDER_FILE, "--out-dir", str(tmp_path),
        ]
    )
    assert exit_code == 0
    assert (tmp_path / "dlc_cam1_lib.py").exists()
    assert (tmp_path / "dlc_cam1_signals.py").exists()


def test_out_dir_missing_is_argparse_error_and_writes_nothing():
    with pytest.raises(SystemExit):
        main(["--config", MADLC_CONFIG, "--source-id", "dlc_cam1", "--bodyparts", "LED_on"])


def test_cwd_inside_project_absolute_out_dir_writes_only_there(tmp_path, monkeypatch):
    before = _snapshot(FIXTURES)
    monkeypatch.chdir(FIXTURES)
    exit_code = main(
        [
            "--config", "dlc3_multianimal_config.yaml", "--source-id", "dlc_cam1",
            "--bodyparts", "LED_on", "--pose-order-file", "pose_order_declared.txt",
            "--out-dir", str(tmp_path),
        ]
    )
    assert exit_code == 0
    assert _snapshot(FIXTURES) == before
    assert (tmp_path / "dlc_cam1_lib.py").exists()


def test_madlc_identity_false_prints_stitch_tracklets_warning(tmp_path, capsys):
    main(
        [
            "--config", MADLC_CONFIG, "--source-id", "dlc_cam1", "--bodyparts", "LED_on",
            "--pose-order-file", POSE_ORDER_FILE, "--out-dir", str(tmp_path),
        ]
    )
    assert "stitch_tracklets" in capsys.readouterr().err


@pytest.mark.parametrize("liveness_hook", ["clock-consistent", "substrate-default"])
@pytest.mark.parametrize("coords_for", [set(), {"LED_on"}])
def test_no_egress_markers_in_rendered_source(liveness_hook, coords_for):
    result = generate(
        source=_source(), pose_order=_pose_order(), pose_order_source="probe",
        wanted=["LED_on", "LED_off"], coords_for=coords_for, source_id="dlc_cam1",
        liveness_hook=liveness_hook,
    )
    for marker in _NO_EGRESS_MARKERS:
        assert marker not in result.lib_source


def test_stale_after_ms_zero_raises_never_stale():
    with pytest.raises(GenerationError, match="NEVER STALE"):
        generate(
            source=_source(), pose_order=_pose_order(), pose_order_source="probe",
            wanted=["LED_on"], coords_for=set(), source_id="dlc_cam1", stale_after_ms=0,
        )


def test_validate_rendered_lib_rejects_illegal_stale_policy():
    bad_source = (
        "from autopilot.hardware.external_hardware import ExternalHardware, signal\n\n\n"
        "class DlcCam1(ExternalHardware):\n"
        '    @signal(default=0.0, stale_after_ms=100, stale_policy="oops")\n'
        "    def led_on_likelihood(self) -> float:\n"
        "        pass\n"
    )
    with pytest.raises(GenerationError) as excinfo:
        _validate_rendered_lib(bad_source, {"led_on_likelihood"})
    message = str(excinfo.value)
    assert "hold_last" in message and "return_default" in message and "return_none" in message


def test_validate_rendered_lib_rejects_return_none():
    bad_source = (
        "from autopilot.hardware.external_hardware import ExternalHardware, signal\n\n\n"
        "class DlcCam1(ExternalHardware):\n"
        '    @signal(default=0.0, stale_after_ms=100, stale_policy="return_none")\n'
        "    def led_on_x(self) -> float:\n"
        "        pass\n"
    )
    with pytest.raises(GenerationError, match="TypeError"):
        _validate_rendered_lib(bad_source, {"led_on_x"})


def test_validate_rendered_lib_rejects_zero_stale_after_ms():
    bad_source = (
        "from autopilot.hardware.external_hardware import ExternalHardware, signal\n\n\n"
        "class DlcCam1(ExternalHardware):\n"
        '    @signal(default=0.0, stale_after_ms=0, stale_policy="hold_last")\n'
        "    def led_on_x(self) -> float:\n"
        "        pass\n"
    )
    with pytest.raises(GenerationError, match="NEVER STALE"):
        _validate_rendered_lib(bad_source, {"led_on_x"})


def test_source_id_1cam_raises_but_dlc_cam1_succeeds():
    with pytest.raises(GenerationError):
        generate(
            source=_source(), pose_order=_pose_order(), pose_order_source="probe",
            wanted=["LED_on"], coords_for=set(), source_id="1cam",
        )
    result = generate(
        source=_source(), pose_order=_pose_order(), pose_order_source="probe",
        wanted=["LED_on"], coords_for=set(), source_id="dlc_cam1",
    )
    assert result.lib_source


def test_malicious_bodypart_string_refused_not_emitted():
    with pytest.raises(Exception):
        generate(
            source=_source(), pose_order=_pose_order(), pose_order_source="probe",
            wanted=['nose"""'], coords_for=set(), source_id="dlc_cam1",
        )


def test_rendered_lib_ast_parses():
    result = generate(
        source=_source(), pose_order=_pose_order(), pose_order_source="probe",
        wanted=["LED_on"], coords_for=set(), source_id="dlc_cam1",
    )
    ast.parse(result.lib_source)


def test_map_signal_names_equal_extracted_from_lib():
    result = generate(
        source=_source(), pose_order=_pose_order(), pose_order_source="probe",
        wanted=["LED_on", "LED_off"], coords_for={"LED_on"}, source_id="dlc_cam1",
    )
    namespace = _exec_source(result.map_source)
    assert sorted(namespace["SIGNAL_NAMES"]) == sorted(flat_signal_names(result.name_map))


def test_lib_sha256_matches_same_invocation():
    result = generate(
        source=_source(), pose_order=_pose_order(), pose_order_source="probe",
        wanted=["LED_on"], coords_for=set(), source_id="dlc_cam1",
    )
    namespace = _exec_source(result.map_source)
    assert namespace["LIB_SHA256"] == hashlib.sha256(result.lib_source.encode("utf-8")).hexdigest()


def test_liveness_hook_clock_consistent_emits_method():
    result = generate(
        source=_source(), pose_order=_pose_order(), pose_order_source="probe",
        wanted=["LED_on"], coords_for=set(), source_id="dlc_cam1",
        liveness_hook="clock-consistent",
    )
    assert "def liveness_hook(self, last_msg_ts_ms, now_ms, stale_ms):" in result.lib_source


def test_liveness_hook_substrate_default_emits_none():
    result = generate(
        source=_source(), pose_order=_pose_order(), pose_order_source="probe",
        wanted=["LED_on"], coords_for=set(), source_id="dlc_cam1",
        liveness_hook="substrate-default",
    )
    assert "def liveness_hook" not in result.lib_source


def test_no_release_override_no_command_decorator():
    result = generate(
        source=_source(), pose_order=_pose_order(), pose_order_source="probe",
        wanted=["LED_on"], coords_for=set(), source_id="dlc_cam1",
    )
    assert "def release" not in result.lib_source
    assert "@command" not in result.lib_source


def test_list_bodyparts_writes_no_file(tmp_path):
    exit_code = main(
        [
            "--config", MADLC_CONFIG, "--source-id", "dlc_cam1", "--bodyparts", "LED_on",
            "--out-dir", str(tmp_path), "--list-bodyparts",
        ]
    )
    assert exit_code == 0
    assert list(tmp_path.iterdir()) == []


def test_rerun_without_force_errors_and_leaves_files_unchanged(tmp_path):
    argv = [
        "--config", MADLC_CONFIG, "--source-id", "dlc_cam1", "--bodyparts", "LED_on",
        "--pose-order-file", POSE_ORDER_FILE, "--out-dir", str(tmp_path),
    ]
    assert main(argv) == 0
    contents_before = (tmp_path / "dlc_cam1_lib.py").read_text()
    assert main(argv) == 1
    assert (tmp_path / "dlc_cam1_lib.py").read_text() == contents_before


def test_config_and_pose_cfg_are_mutually_exclusive():
    with pytest.raises(SystemExit):
        main(
            [
                "--config", MADLC_CONFIG, "--pose-cfg", MADLC_CONFIG,
                "--source-id", "dlc_cam1", "--bodyparts", "LED_on", "--out-dir", "/tmp",
            ]
        )


def test_no_config_flag_falls_back_to_explicit_list_with_warning(tmp_path, capsys):
    # explicit-list mode is exempt from the D-39 "must not select every candidate"
    # gate (there is no larger config-declared universe to narrow from -- the source's
    # own candidate list IS --bodyparts, by construction), so selecting everything here
    # is expected to succeed.
    exit_code = main(
        [
            "--source-id", "dlc_cam1", "--bodyparts", "nose,tail",
            "--pose-order", "nose,tail", "--out-dir", str(tmp_path),
        ]
    )
    assert exit_code == 0
    assert "explicit-list" in capsys.readouterr().err
    namespace = _exec_source((tmp_path / "dlc_cam1_signals.py").read_text())
    assert namespace["SOURCE_FORMAT"] == "explicit-list"


def test_budget_print_contains_no_latency_jitter_drift_words(tmp_path, capsys):
    main(
        [
            "--config", MADLC_CONFIG, "--source-id", "dlc_cam1", "--bodyparts", "LED_on",
            "--pose-order-file", POSE_ORDER_FILE, "--out-dir", str(tmp_path),
        ]
    )
    stdout = capsys.readouterr().out.lower()
    for banned in ("latency", "jitter", "drift"):
        assert banned not in stdout
