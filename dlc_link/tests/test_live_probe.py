"""Tests for `dlc_link.live_probe.run_probe_pose` (plan 38-05, D-62).

Drives `run_probe_pose` directly against a fake `DLCLive` class, a fake capture and a
fake pose -- a list of lists, no numpy required -- per the plan's own instruction. No
`cv2`/`dlclive` import anywhere in this file; `run_probe_pose` never imports either
itself (they are handed in as `dclive_cls`/`cap`, already resolved by the caller).
"""
import types

from dlc_link.live_probe import run_probe_pose


def _args(geometry_parts="NW,NE,SE,SW", geometry_frames=1, geometry_margin=0.05,
          geometry_min_likelihood=0.5, resize=None, model_path="model.pt"):
    """A bare namespace carrying only what `run_probe_pose` reads -- deliberately no
    `host`/`port` attributes, so any access to either would raise `AttributeError`
    and fail the test, proving the probe needs no address to run."""
    return types.SimpleNamespace(
        model_path=model_path, resize=resize, geometry_parts=geometry_parts,
        geometry_frames=geometry_frames, geometry_margin=geometry_margin,
        geometry_min_likelihood=geometry_min_likelihood,
    )


def _dclive_cls(pose, order=None, order_attr="cfg"):
    """Builds a fake `DLCLive` class. `order`, when given, is exposed under
    `order_attr` as `{"all_joints_names": [...]}` -- the shape `_discover_pose_order`
    recognises. `pose` is returned verbatim from both `init_inference` and `get_pose`."""

    class _FakeDLCLive:
        def __init__(self, model_path, **kwargs):
            self.model_path = model_path
            self.kwargs = kwargs
            if order is not None:
                setattr(self, order_attr, {"all_joints_names": list(order)})

        def init_inference(self, _frame):
            return pose

        def get_pose(self, _frame):
            return pose

    return _FakeDLCLive


class _NeverReadCap:
    """A capture that raises if `.read()` is ever called -- proves the probe never
    reads a second frame when `--geometry-frames` is 1 (the default)."""

    def read(self):
        raise AssertionError("run_probe_pose must not read a second frame when geometry_frames=1")


def _smap(order):
    return types.SimpleNamespace(POSE_ORDER=list(order), POSE_ORDER_SOURCE="probe")


_THREE_ROW_POSE = [[10.0, 20.0, 0.9], [30.0, 40.0, 0.8], [50.0, 60.0, 0.7]]
_FIVE_COL_ROW0 = [10.0, 20.0, 0.9, 1.23, 4.56]
_FIVE_COL_POSE = [_FIVE_COL_ROW0, [30.0, 40.0, 0.8, 0.0, 0.0]]


# --- no --signal-map: the chicken-and-egg this plan closes (D-62) -------------------


def test_probe_runs_with_no_signal_map_and_exits_0(capsys):
    exit_code = run_probe_pose(
        _args(), None, _dclive_cls(_THREE_ROW_POSE, order=["a", "b", "c"]),
        _NeverReadCap(), "frame0", 100.0, 100.0,
    )
    assert exit_code == 0


def test_no_signal_map_prints_shape_and_row_count(capsys):
    run_probe_pose(
        _args(), None, _dclive_cls(_THREE_ROW_POSE, order=["a", "b", "c"]),
        _NeverReadCap(), "frame0", 100.0, 100.0,
    )
    out = capsys.readouterr().out
    assert "pose row count: 3" in out
    assert "discovered order: ['a', 'b', 'c']" in out


def test_no_signal_map_prints_no_verdict_or_pose_order_comparison(capsys):
    run_probe_pose(
        _args(), None, _dclive_cls(_THREE_ROW_POSE, order=["a", "b", "c"]),
        _NeverReadCap(), "frame0", 100.0, 100.0,
    )
    out = capsys.readouterr().out
    assert "VERDICT" not in out
    assert "signal map POSE_ORDER" not in out
    assert "POSE_ORDER_SOURCE" not in out


def test_no_signal_map_no_order_discovered_prints_not_found(capsys):
    run_probe_pose(
        _args(), None, _dclive_cls(_THREE_ROW_POSE, order=None),
        _NeverReadCap(), "frame0", 100.0, 100.0,
    )
    out = capsys.readouterr().out
    assert "bodypart ordering: NOT FOUND" in out
    assert "VERDICT" not in out


# --- the paste-ready --pose-order line (D-62's whole point) -------------------------


def test_discovered_order_produces_paste_ready_pose_order_line(capsys):
    run_probe_pose(
        _args(), None, _dclive_cls(_THREE_ROW_POSE, order=["nose", "tail", "ear"]),
        _NeverReadCap(), "frame0", 100.0, 100.0,
    )
    out = capsys.readouterr().out
    assert "--pose-order nose,tail,ear" in out
    # comma-joined, no spaces -- paste-ready means paste-ready.
    assert "--pose-order nose, tail, ear" not in out


def test_no_discoverable_order_produces_row_placeholder_and_positions_warning(capsys):
    run_probe_pose(
        _args(), None, _dclive_cls(_THREE_ROW_POSE, order=None),
        _NeverReadCap(), "frame0", 100.0, 100.0,
    )
    out = capsys.readouterr().out
    assert "--pose-order row_0,row_1,row_2" in out
    assert "POSITIONS" in out
    assert "not names" in out.lower() or "never assumed from position" in out


def test_next_command_line_is_printed(capsys):
    run_probe_pose(
        _args(), None, _dclive_cls(_THREE_ROW_POSE, order=["a", "b", "c"]),
        _NeverReadCap(), "frame0", 100.0, 100.0,
    )
    out = capsys.readouterr().out
    assert "dlc-link-generate" in out
    assert "--pose-order" in out
    assert "--out-dir" in out


# --- every column of row 0, including the uncharacterised ones ---------------------


def test_five_column_pose_prints_two_uncharacterised_column_lines(capsys):
    run_probe_pose(
        _args(), None, _dclive_cls(_FIVE_COL_POSE, order=["a", "b"]),
        _NeverReadCap(), "frame0", 100.0, 100.0,
    )
    out = capsys.readouterr().out
    assert out.count("uncharacterised") == 2
    assert "column [3]" in out and "column [4]" in out


def test_three_column_pose_prints_no_uncharacterised_lines(capsys):
    run_probe_pose(
        _args(), None, _dclive_cls(_THREE_ROW_POSE, order=["a", "b", "c"]),
        _NeverReadCap(), "frame0", 100.0, 100.0,
    )
    out = capsys.readouterr().out
    assert "uncharacterised" not in out


def test_row0_columns_0_1_2_labelled_x_y_likelihood(capsys):
    run_probe_pose(
        _args(), None, _dclive_cls(_THREE_ROW_POSE, order=["a", "b", "c"]),
        _NeverReadCap(), "frame0", 100.0, 100.0,
    )
    out = capsys.readouterr().out
    assert "column [0] (x)" in out
    assert "column [1] (y)" in out
    assert "column [2] (likelihood)" in out


# --- WITH --signal-map: today's behaviour, unchanged (acceptance criteria) ---------


def test_with_signal_map_verdict_line_still_present(capsys):
    run_probe_pose(
        _args(), _smap(["a", "b", "c"]), _dclive_cls(_THREE_ROW_POSE, order=["a", "b", "c"]),
        _NeverReadCap(), "frame0", 100.0, 100.0,
    )
    out = capsys.readouterr().out
    assert "VERDICT: row_count_match=True ordering=match" in out
    assert "signal map POSE_ORDER: ['a', 'b', 'c']" in out
    assert "POSE_ORDER_SOURCE: 'probe'" in out


def test_with_signal_map_mismatch_is_reported(capsys):
    run_probe_pose(
        _args(), _smap(["x", "y", "z"]), _dclive_cls(_THREE_ROW_POSE, order=["a", "b", "c"]),
        _NeverReadCap(), "frame0", 100.0, 100.0,
    )
    out = capsys.readouterr().out
    assert "VERDICT: row_count_match=True ordering=mismatch" in out


def test_with_signal_map_still_prints_pose_order_line_too(capsys):
    """The paste-ready line and the uncharacterised-column printing are general --
    they are not gated on the ABSENCE of a signal map, only the VERDICT comparison is."""
    run_probe_pose(
        _args(), _smap(["a", "b", "c"]), _dclive_cls(_THREE_ROW_POSE, order=["a", "b", "c"]),
        _NeverReadCap(), "frame0", 100.0, 100.0,
    )
    out = capsys.readouterr().out
    assert "--pose-order a,b,c" in out


# --- the probe never connects to a Pi, with or without a map -----------------------


def test_probe_needs_no_host_or_port_attribute_on_args():
    # _args() deliberately carries no host/port; a successful run proves neither is
    # ever read by run_probe_pose.
    exit_code = run_probe_pose(
        _args(), None, _dclive_cls(_THREE_ROW_POSE, order=["a", "b", "c"]),
        _NeverReadCap(), "frame0", 100.0, 100.0,
    )
    assert exit_code == 0


def test_corner_geometry_still_unavailable_with_no_map_when_order_undiscovered(capsys):
    run_probe_pose(
        _args(), None, _dclive_cls(_THREE_ROW_POSE, order=None),
        _NeverReadCap(), "frame0", 100.0, 100.0,
    )
    out = capsys.readouterr().out
    assert "CORNER GEOMETRY: UNAVAILABLE -- bodypart ordering was not discovered" in out
