"""Tests for dlc_link.live / dlc_link.live_cli / dlc_link.live_probe (Task 3, plan 38-01).

Imports changed from the pre-split layout: `build_parser`/`validate_connection_args`
now live in (and are exported from) `dlc_link.live_cli`, not `dlc_link.live` -- Task 3
moved the CLI out of `live.py` to keep it under the 300-line production-file limit.
Every pre-existing assertion below is unchanged; only the import paths moved.
"""
import inspect
import re
import sys
import types

import pytest

from dlc_link import live as live_module
from dlc_link import live_cli as live_cli_module
from dlc_link.config_read import from_explicit_list
from dlc_link.generate import generate
from dlc_link.live import (
    check_corner_geometry,
    compare_pose_order,
    main,
    run_video_loop,
)
from dlc_link.live_cli import build_parser, validate_connection_args


class _FakePacer:
    def __init__(self):
        self.calls = []

    def wait_until(self, t_rel):
        self.calls.append(t_rel)
        return 0.0

    def behind_count(self):
        return 0


class _FakeProcessor:
    def snapshot(self):
        return {"frames": 0}


class _NeverCloseLink:
    def close(self):
        raise AssertionError("run_video_loop must never call close() on link")

    def __exit__(self, *_args):
        raise AssertionError("run_video_loop must never call __exit__ on link")


# --- run_video_loop -----------------------------------------------------------------


def test_pacer_called_with_exact_offset_sequence():
    pacer = _FakePacer()
    infer_calls = []
    result = run_video_loop(
        _NeverCloseLink(), ["f1", "f2", "f3"], infer_calls.append, _FakeProcessor(), pacer, fps=10.0
    )
    assert pacer.calls == [1 / 10.0, 2 / 10.0, 3 / 10.0]
    assert infer_calls == ["f1", "f2", "f3"]
    assert result["frames_read"] == 3
    assert result["frames_inferred"] == 3


def test_infer_is_called_after_wait_until_for_each_frame():
    order = []

    class _OrderPacer(_FakePacer):
        def wait_until(self, t_rel):
            order.append(("wait", t_rel))
            return 0.0

    def infer(frame):
        order.append(("infer", frame))

    run_video_loop(_NeverCloseLink(), ["a", "b"], infer, _FakeProcessor(), _OrderPacer(), fps=5.0)
    assert order == [("wait", 0.2), ("infer", "a"), ("wait", 0.4), ("infer", "b")]


def test_max_frames_stops_the_loop_early():
    infer_calls = []
    result = run_video_loop(
        _NeverCloseLink(), ["a", "b", "c"], infer_calls.append, _FakeProcessor(), _FakePacer(),
        fps=1.0, max_frames=2,
    )
    assert infer_calls == ["a", "b"]
    assert result["frames_read"] == 2
    assert result["frames_inferred"] == 2


def test_empty_frame_iterable_returns_zeroed_counts_and_does_not_raise():
    result = run_video_loop(_NeverCloseLink(), [], lambda f: None, _FakeProcessor(), _FakePacer(), fps=30.0)
    assert result["frames_read"] == 0
    assert result["frames_inferred"] == 0


def test_returned_record_contains_the_processor_snapshot():
    result = run_video_loop(_NeverCloseLink(), ["a"], lambda f: None, _FakeProcessor(), _FakePacer(), fps=30.0)
    assert result["processor_snapshot"] == {"frames": 0}


def test_run_video_loop_never_closes_the_link():
    link = _NeverCloseLink()
    # No AssertionError means close()/__exit__ were never invoked.
    run_video_loop(link, ["a"], lambda f: None, _FakeProcessor(), _FakePacer(), fps=30.0)


def test_module_has_no_top_level_cv2_or_dlclive_import():
    source = inspect.getsource(live_module)
    header = source.split("\ndef ")[0]
    assert "import cv2" not in header
    assert "import dlclive" not in header
    assert "from dlclive" not in header


# --- run_video_loop: pacer=None (D-51, D-53) -----------------------------------------


def test_pacer_none_never_calls_a_pacer_and_behind_count_is_none():
    class _PacerThatMustNotBeCalled:
        def wait_until(self, t_rel):
            raise AssertionError("pacer=None must never call wait_until")

        def behind_count(self):
            raise AssertionError("pacer=None must never call behind_count")

    result = run_video_loop(
        _NeverCloseLink(), ["a", "b"], lambda f: None, _FakeProcessor(), None, fps=30.0
    )
    assert result["behind_count"] is None  # is None, not a falsy check -- 0 is also falsy (D-53)


def test_pacer_none_is_not_the_same_as_a_falsy_pacer():
    # Guards against a regression that checks `if pacer:` instead of `if pacer is not None:`.
    result = run_video_loop(_NeverCloseLink(), [], lambda f: None, _FakeProcessor(), None, fps=30.0)
    assert result["behind_count"] is None


# --- run_video_loop: should_stop ------------------------------------------------------


def test_should_stop_true_immediately_returns_after_zero_inferences():
    infer_calls = []
    result = run_video_loop(
        _NeverCloseLink(), ["a", "b", "c"], infer_calls.append, _FakeProcessor(), None, fps=30.0,
        should_stop=lambda: True,
    )
    assert infer_calls == []
    assert result["frames_inferred"] == 0


def test_should_stop_checked_once_per_frame_before_inference():
    calls = []

    def should_stop():
        calls.append("should_stop")
        return False

    def infer(frame):
        calls.append(("infer", frame))

    run_video_loop(_NeverCloseLink(), ["a", "b", "c"], infer, _FakeProcessor(), None, fps=30.0,
                    should_stop=should_stop)
    assert calls == [
        "should_stop", ("infer", "a"),
        "should_stop", ("infer", "b"),
        "should_stop", ("infer", "c"),
    ]


def test_should_stop_call_count_equals_frames_considered():
    call_count = [0]

    def should_stop():
        call_count[0] += 1
        return call_count[0] > 2  # stop after the 2nd frame is considered

    result = run_video_loop(
        _NeverCloseLink(), ["a", "b", "c", "d"], lambda f: None, _FakeProcessor(), None, fps=30.0,
        should_stop=should_stop,
    )
    assert call_count[0] == 3  # 2 that allowed inference, 1 that stopped it
    assert result["frames_inferred"] == 2


# --- run_video_loop: observer ----------------------------------------------------------


def test_observer_called_once_per_inferred_frame_with_infer_result():
    observed = []

    def infer(frame):
        return frame.upper()

    run_video_loop(
        _NeverCloseLink(), ["a", "b"], infer, _FakeProcessor(), None, fps=30.0,
        observer=lambda frame, pose: observed.append((frame, pose)),
    )
    assert observed == [("a", "A"), ("b", "B")]


def test_observer_that_raises_is_counted_and_does_not_stop_the_loop():
    infer_calls = []

    def observer(frame, pose):
        raise RuntimeError("viewer blew up")

    result = run_video_loop(
        _NeverCloseLink(), ["a", "b", "c"], infer_calls.append, _FakeProcessor(), None, fps=30.0,
        observer=observer,
    )
    assert infer_calls == ["a", "b", "c"]
    assert result["frames_inferred"] == 3
    assert result["observer_errors"] == 3


def test_observer_none_by_default_does_not_change_existing_results():
    result = run_video_loop(_NeverCloseLink(), ["a"], lambda f: None, _FakeProcessor(), _FakePacer(), fps=30.0)
    assert result["observer_errors"] == 0


# --- run_video_loop: max_seconds -------------------------------------------------------


def test_max_seconds_stops_once_the_injected_clock_passes_the_deadline():
    clock_values = iter([0.0, 0.0, 1.0, 2.0, 3.0, 4.0])

    def clock():
        return next(clock_values)

    infer_calls = []
    result = run_video_loop(
        _NeverCloseLink(), ["a", "b", "c", "d", "e"], infer_calls.append, _FakeProcessor(), None,
        fps=30.0, max_seconds=1.5, clock=clock,
    )
    # loop_start=0.0 (1st clock() call); frame 'a' checked at 0.0 (2nd call, not yet past 1.5,
    # inferred); frame 'b' checked at 1.0 (3rd call, not past); frame 'c' checked at 2.0 (4th
    # call, past 1.5) -> stop before inferring 'c'.
    assert infer_calls == ["a", "b"]
    assert result["frames_inferred"] == 2


# --- compare_pose_order ---------------------------------------------------------------


def test_compare_pose_order_match():
    verdict, _msg = compare_pose_order(["a", "b"], ["a", "b"])
    assert verdict == "match"


def test_compare_pose_order_mismatch():
    verdict, _msg = compare_pose_order(["a", "b"], ["b", "a"])
    assert verdict == "mismatch"


def test_compare_pose_order_not_discoverable():
    verdict, _msg = compare_pose_order(["a", "b"], None)
    assert verdict == "ordering-not-discoverable"


# --- check_corner_geometry -------------------------------------------------------------

_GOOD = {"NW": (0.1, 0.1), "NE": (0.9, 0.1), "SE": (0.9, 0.9), "SW": (0.1, 0.9)}
_CONF = {k: 0.99 for k in _GOOD}


def test_corner_geometry_pass():
    assert check_corner_geometry(_GOOD, _CONF, 0.05, 0.5)[0] == "PASS"


def test_corner_geometry_fail_on_swap_names_the_inequality():
    swapped = dict(_GOOD)
    swapped["NW"], swapped["NE"] = _GOOD["NE"], _GOOD["NW"]
    verdict, message = check_corner_geometry(swapped, _CONF, 0.05, 0.5)
    assert verdict == "FAIL"
    assert "NW.x" in message


def test_corner_geometry_unreliable_on_low_likelihood_names_corner():
    low = dict(_CONF)
    low["SE"] = 0.01
    verdict, message = check_corner_geometry(_GOOD, low, 0.05, 0.5)
    assert verdict == "UNRELIABLE"
    assert "SE" in message


def test_corner_geometry_unavailable_on_missing_corner():
    verdict, _msg = check_corner_geometry({"NW": (0.1, 0.1)}, {"NW": 0.9}, 0.05, 0.5)
    assert verdict == "UNAVAILABLE"


def test_corner_geometry_fails_below_margin_not_pass():
    tight = {"NW": (0.50, 0.1), "NE": (0.51, 0.1), "SE": (0.51, 0.9), "SW": (0.50, 0.9)}
    assert check_corner_geometry(tight, _CONF, 0.05, 0.5)[0] == "FAIL"


def test_median_corner_measurements_uses_median_not_mean_or_last_frame():
    from dlc_link.live_probe import _median_corner_measurements

    samples = {"NW": [(0.1, 0.5, 0.9), (0.2, 0.5, 0.9), (0.9, 0.5, 0.9)]}
    aggregated = _median_corner_measurements(samples)
    x = aggregated["NW"][0]
    assert x == 0.2  # median of [0.1, 0.2, 0.9]; mean would be 0.4, last-frame would be 0.9


# --- static source assertions ---------------------------------------------------------


def test_model_type_is_pytorch_never_base_tensorrt_or_lite():
    source = inspect.getsource(live_cli_module)
    assert 'model_type="pytorch"' in source or "model_type='pytorch'" in source
    assert "base" not in source.split("model_type")[1][:40]
    assert "tensorrt" not in source
    assert "lite" not in source


def test_wait_until_swap_comment_present():
    source = inspect.getsource(live_module)
    assert "one line" in source or "ONE line" in source
    assert "live camera" in source


def test_no_write_mode_open_or_file_handlers_in_live_source():
    combined = inspect.getsource(live_module) + inspect.getsource(live_cli_module)
    body = "\n".join(line for line in combined.splitlines() if not line.strip().startswith("#"))
    for bad in (r"open\([^)]*['\"][wa]", r"logging\.FileHandler", r"to_csv", r"savefig", r"NamedTemporaryFile"):
        assert re.search(bad, body) is None


def test_no_latency_or_jitter_outside_comments_in_live_source():
    from dlc_link import live_cli_args, live_sources

    combined = "\n".join(
        inspect.getsource(m) for m in (live_module, live_cli_module, live_cli_args, live_sources)
    )
    body = "\n".join(line for line in combined.splitlines() if not line.strip().startswith("#"))
    assert not re.search(r"latency|jitter|drift", body, re.IGNORECASE)


def test_dlclive_display_pinned_off_with_d47_comment():
    source = inspect.getsource(live_cli_module)
    assert "display=False" in source
    assert "D-47" in source


def test_probe_pose_documented_as_needing_no_host():
    help_text = build_parser().format_help()
    assert "--probe-pose" in help_text
    assert "no --host" in help_text or "needs no --host" in help_text


def test_help_documents_probe_pose_and_geometry_flags_never_connecting():
    help_text = build_parser().format_help()
    for flag in ("--probe-pose", "--geometry-parts", "--geometry-frames", "--geometry-margin",
                 "--geometry-min-likelihood"):
        assert flag in help_text
    assert "Never" in help_text or "never" in help_text


def test_corner_geometry_limit_stated_in_source():
    from dlc_link import live_probe

    source = inspect.getsource(live_module) + inspect.getsource(live_probe)
    assert "35-07" in source
    assert "complement" in source


def test_live_py_is_under_300_lines():
    source_lines = inspect.getsource(live_module).splitlines()
    assert len(source_lines) < 300


def test_live_main_and_live_cli_main_agree_on_help():
    with pytest.raises(SystemExit) as live_exit:
        main(["--help"])
    with pytest.raises(SystemExit) as cli_exit:
        live_cli_module.main(["--help"])
    assert live_exit.value.code == cli_exit.value.code == 0


# --- D-47: nothing is written, with cv2/dlclive faked in via sys.modules -------------


def _install_fake_cv2_dlclive(monkeypatch, frames, fps=30.0, width=100.0, height=100.0,
                               buffersize_get=1.0, track=None):
    fake_cv2 = types.ModuleType("cv2")
    fake_cv2.CAP_PROP_FRAME_WIDTH = "W"
    fake_cv2.CAP_PROP_FRAME_HEIGHT = "H"
    fake_cv2.CAP_PROP_FPS = "FPS"
    fake_cv2.CAP_PROP_BUFFERSIZE = "BUF"

    class _Cap:
        def __init__(self, _path):
            self._frames = list(frames)
            self._i = 0

        def read(self):
            if self._i >= len(self._frames):
                return False, None
            frame = self._frames[self._i]
            self._i += 1
            return True, frame

        def get(self, prop):
            return {"W": width, "H": height, "FPS": fps, "BUF": buffersize_get}[prop]

        def set(self, prop, value):
            return True

        def release(self):
            pass

    fake_cv2.VideoCapture = _Cap
    monkeypatch.setitem(sys.modules, "cv2", fake_cv2)

    fake_dlclive = types.ModuleType("dlclive")

    class _FakeDLCLive:
        def __init__(self, _model_path, **kwargs):
            self.kwargs = kwargs
            self._processor = kwargs.get("processor")
            if track is not None:
                track.append(self)

        def _infer(self):
            pose = [[10.0, 10.0, 0.9]]
            if self._processor is not None:
                self._processor.process(pose)
            return pose

        def init_inference(self, _frame):
            return self._infer()

        def get_pose(self, _frame):
            return self._infer()

        def close(self):
            pass

    fake_dlclive.DLCLive = _FakeDLCLive
    monkeypatch.setitem(sys.modules, "dlclive", fake_dlclive)


def _write_signal_map(assets_dir):
    source = from_explicit_list(["nose"])
    result = generate(
        source=source, pose_order=["nose"], pose_order_source="probe",
        wanted=["nose"], coords_for={"nose"}, source_id="dlc_cam1",
    )
    smap_path = assets_dir / "dlc_cam1_signals.py"
    smap_path.write_text(result.map_source)
    return smap_path


def test_dry_run_leaves_an_empty_current_directory_untouched(tmp_path, monkeypatch, tmp_path_factory):
    assets = tmp_path_factory.mktemp("assets_dry_run")
    source = from_explicit_list(["nose"])
    result = generate(
        source=source, pose_order=["nose"], pose_order_source="probe",
        wanted=["nose"], coords_for=set(), source_id="dlc_cam1",
    )
    smap_path = assets / "dlc_cam1_signals.py"
    smap_path.write_text(result.map_source)

    _install_fake_cv2_dlclive(monkeypatch, frames=["frame1", "frame2"])
    monkeypatch.chdir(tmp_path)

    before = sorted(p.name for p in tmp_path.iterdir())
    exit_code = main(
        [
            "--video", "video.mp4", "--model-path", "model.pt",
            "--signal-map", str(smap_path), "--dry-run", "--max-frames", "1",
        ]
    )
    after = sorted(p.name for p in tmp_path.iterdir())
    assert exit_code == 0
    assert before == after == []


def test_probe_pose_leaves_an_empty_current_directory_untouched(tmp_path, monkeypatch, tmp_path_factory):
    assets = tmp_path_factory.mktemp("assets_probe_pose")
    source = from_explicit_list(["nose"])
    result = generate(
        source=source, pose_order=["nose"], pose_order_source="probe",
        wanted=["nose"], coords_for=set(), source_id="dlc_cam1",
    )
    smap_path = assets / "dlc_cam1_signals.py"
    smap_path.write_text(result.map_source)

    _install_fake_cv2_dlclive(monkeypatch, frames=["frame1"])
    monkeypatch.chdir(tmp_path)

    before = sorted(p.name for p in tmp_path.iterdir())
    exit_code = main(
        [
            "--video", "video.mp4", "--model-path", "model.pt",
            "--signal-map", str(smap_path), "--probe-pose",
        ]
    )
    after = sorted(p.name for p in tmp_path.iterdir())
    assert exit_code == 0
    assert before == after == []


def test_dry_run_processes_frames_through_the_real_processor(tmp_path, monkeypatch, tmp_path_factory):
    """End-to-end (fakes only): --dry-run drives a real DLCProcessor against the fake
    DLCLive/cv2, proving the whole wiring (not just argparse) never touches the network
    or the filesystem."""
    assets = tmp_path_factory.mktemp("assets_dry_run_e2e")
    smap_path = _write_signal_map(assets)

    _install_fake_cv2_dlclive(monkeypatch, frames=["frame1", "frame2", "frame3"])
    monkeypatch.chdir(tmp_path)

    exit_code = main(
        [
            "--video", "video.mp4", "--model-path", "model.pt",
            "--signal-map", str(smap_path), "--dry-run", "--max-frames", "2",
        ]
    )
    assert exit_code == 0


# --- camera source: CLI-level behaviour (D-49, D-51, D-52, D-53, D-55) --------------


def test_source_zero_with_fps_refuses_naming_source_kind_before_any_import(tmp_path, tmp_path_factory):
    assets = tmp_path_factory.mktemp("assets_fps_refusal")
    smap_path = _write_signal_map(assets)
    # Deliberately NOT calling _install_fake_cv2_dlclive: no cv2/dlclive in sys.modules
    # for this test, proving the refusal fires before the deferred import is reached.
    assert "cv2" not in sys.modules

    exit_code = main(
        [
            "--source", "0", "--fps", "30", "--model-path", "m",
            "--signal-map", str(smap_path), "--dry-run",
        ]
    )
    assert exit_code != 0
    assert "cv2" not in sys.modules


def test_source_and_video_together_exits_2_naming_both_flags():
    exit_code = main(
        [
            "--source", "a", "--video", "b", "--model-path", "m",
            "--signal-map", "unused.py", "--dry-run",
        ]
    )
    assert exit_code == 2


def test_camera_summary_reports_behind_count_na_and_frames_skipped(tmp_path, monkeypatch, tmp_path_factory, capsys):
    assets = tmp_path_factory.mktemp("assets_camera_summary")
    smap_path = _write_signal_map(assets)
    # More frames than max_frames, so LatestSlot overwrites at least once.
    _install_fake_cv2_dlclive(monkeypatch, frames=["f{}".format(i) for i in range(10)])

    exit_code = main(
        [
            "--source", "0", "--model-path", "m", "--signal-map", str(smap_path),
            "--dry-run", "--max-frames", "1",
        ]
    )
    out = capsys.readouterr().out
    assert exit_code == 0
    assert "behind_count:    n/a (unpaced source)" in out
    assert "frames_skipped:" in out


def test_file_summary_reports_a_numeric_behind_count(tmp_path, monkeypatch, tmp_path_factory, capsys):
    assets = tmp_path_factory.mktemp("assets_file_summary")
    smap_path = _write_signal_map(assets)
    _install_fake_cv2_dlclive(monkeypatch, frames=["f1", "f2"])

    exit_code = main(
        [
            "--video", "video.mp4", "--model-path", "m", "--signal-map", str(smap_path),
            "--dry-run", "--max-frames", "1",
        ]
    )
    out = capsys.readouterr().out
    assert exit_code == 0
    assert "behind_count:    0" in out
    assert "n/a" not in out.split("behind_count:")[1].split("\n")[0]


def test_min_rate_below_achieved_exits_non_zero(tmp_path, monkeypatch, tmp_path_factory):
    assets = tmp_path_factory.mktemp("assets_min_rate")
    smap_path = _write_signal_map(assets)
    _install_fake_cv2_dlclive(monkeypatch, frames=["f1", "f2", "f3"])

    exit_code = main(
        [
            "--video", "video.mp4", "--model-path", "m", "--signal-map", str(smap_path),
            "--dry-run", "--max-frames", "3", "--min-rate", "1000000",
        ]
    )
    assert exit_code != 0


def test_no_min_rate_leaves_exit_code_unchanged(tmp_path, monkeypatch, tmp_path_factory):
    assets = tmp_path_factory.mktemp("assets_no_min_rate")
    smap_path = _write_signal_map(assets)
    _install_fake_cv2_dlclive(monkeypatch, frames=["f1", "f2", "f3"])

    exit_code = main(
        [
            "--video", "video.mp4", "--model-path", "m", "--signal-map", str(smap_path),
            "--dry-run", "--max-frames", "3",
        ]
    )
    assert exit_code == 0


def test_capture_only_constructs_no_dlclive_and_sends_nothing(tmp_path, monkeypatch, tmp_path_factory):
    assets = tmp_path_factory.mktemp("assets_capture_only")
    smap_path = _write_signal_map(assets)
    constructed = []
    _install_fake_cv2_dlclive(monkeypatch, frames=["f1", "f2", "f3"], track=constructed)

    exit_code = main(
        [
            "--source", "0", "--model-path", "m", "--signal-map", str(smap_path),
            "--capture-only", "--max-frames", "2",
        ]
    )
    assert exit_code == 0
    assert constructed == []  # no DLCLive instance was ever constructed


def test_capture_only_needs_neither_host_nor_port(tmp_path, monkeypatch, tmp_path_factory):
    assets = tmp_path_factory.mktemp("assets_capture_only_no_host")
    smap_path = _write_signal_map(assets)
    _install_fake_cv2_dlclive(monkeypatch, frames=["f1"])

    exit_code = main(
        [
            "--source", "0", "--model-path", "m", "--signal-map", str(smap_path),
            "--capture-only", "--max-frames", "1",
        ]
    )
    assert exit_code == 0


# --- connection-argument validation (port/host trap) -------------------------
# Pilot 3 binds TWO extlink consumers: 5599 (ExtlinkDemo/"demo") and 5601
# (dlc_cam1) -- 35-FIXTURE-INVENTORY.md:131. A silent --port default therefore
# does not merely miss; it delivers to a DIFFERENT fixture that is genuinely
# listening, so the send succeeds and the intended lib stays empty. The port
# belongs to a (pilot, source_id) row in pilot_hardware_config, not to this
# tool, so there is no correct default to pick -- it must be stated.


def _parsed(*argv):
    base = [
        "--video", "clip.mp4",
        "--model-path", "model.pt",
        "--signal-map", "sig.py",
    ]
    return build_parser().parse_args(base + list(argv))


def test_port_has_no_silent_default():
    assert _parsed().port is None


def test_port_required_when_actually_connecting():
    problem = validate_connection_args(_parsed("--host", "10.0.0.5"))
    assert problem is not None
    assert "--port" in problem


def test_host_still_required_when_actually_connecting():
    problem = validate_connection_args(_parsed("--port", "5601"))
    assert problem is not None
    assert "--host" in problem


def test_host_and_port_together_are_accepted():
    assert validate_connection_args(
        _parsed("--host", "10.0.0.5", "--port", "5601")
    ) is None


@pytest.mark.parametrize("flag", ["--dry-run", "--probe-pose", "--capture-only"])
def test_offline_modes_need_neither_host_nor_port(flag):
    assert validate_connection_args(_parsed(flag)) is None


# --- --view wiring (Task 3, plan 38-03) ----------------------------------------------


def test_view_sink_mjpeg_without_view_port_exits_2():
    exit_code = main(
        [
            "--video", "clip.mp4", "--model-path", "m", "--signal-map", "s.py",
            "--dry-run", "--view-sink", "mjpeg",
        ]
    )
    assert exit_code == 2


def test_view_without_view_min_likelihood_exits_2():
    exit_code = main(
        ["--video", "clip.mp4", "--model-path", "m", "--signal-map", "s.py", "--dry-run", "--view"]
    )
    assert exit_code == 2


def test_overlay_naming_an_undeclared_signal_exits_non_zero_before_any_cv2_import(
    tmp_path_factory,
):
    assets = tmp_path_factory.mktemp("assets_overlay_refusal")
    smap_path = _write_signal_map(assets)
    assert "cv2" not in sys.modules

    exit_code = main(
        [
            "--video", "clip.mp4", "--model-path", "m", "--signal-map", str(smap_path),
            "--dry-run", "--overlay", "nose_zz>0.5",
        ]
    )
    assert exit_code != 0
    assert "cv2" not in sys.modules


def test_view_absent_constructs_no_viewer(tmp_path_factory, monkeypatch):
    assets = tmp_path_factory.mktemp("assets_no_view")
    smap_path = _write_signal_map(assets)
    _install_fake_cv2_dlclive(monkeypatch, frames=["f1", "f2"])

    from dlc_link import viewer as viewer_module

    def _must_not_be_constructed(*_args, **_kwargs):
        raise AssertionError("Viewer must not be constructed when --view is absent")

    monkeypatch.setattr(viewer_module.Viewer, "__init__", _must_not_be_constructed)

    exit_code = main(
        [
            "--video", "clip.mp4", "--model-path", "m", "--signal-map", str(smap_path),
            "--dry-run", "--max-frames", "2",
        ]
    )
    assert exit_code == 0


# --- D-54's baseline must be runnable with no model and no signal map -------------
#
# `--capture-only` exists to measure what the CAMERA delivers with nothing loaded, and
# it already returns `live=None` and a `_NoOpProcessor` (live_cli.py:55). But argparse
# still demanded `--model-path` and `--signal-map`, and `load_signal_map` ran
# unconditionally -- so measuring the baseline required inventing two paths that are
# never read. Found 2026-09-10 while preparing the rig's baseline run; same class as the
# `--probe-pose` chicken-and-egg plan 38-05 fixes.


def test_capture_only_parses_without_model_path_or_signal_map():
    args = build_parser().parse_args(["--capture-only", "--source", "0"])
    assert args.capture_only is True
    assert args.model_path is None
    assert args.signal_map is None


def test_model_path_and_signal_map_still_required_without_capture_only():
    problem = validate_connection_args(
        build_parser().parse_args(["--source", "0", "--host", "h", "--port", "1"])
    )
    assert problem is not None
    assert "--model-path" in problem and "--signal-map" in problem


def test_capture_only_does_not_require_them_in_validation():
    assert (
        validate_connection_args(
            build_parser().parse_args(["--capture-only", "--source", "0"])
        )
        is None
    )


def test_probe_pose_still_requires_a_model_path():
    problem = validate_connection_args(
        build_parser().parse_args(["--probe-pose", "--source", "0"])
    )
    assert problem is not None
    assert "--model-path" in problem
