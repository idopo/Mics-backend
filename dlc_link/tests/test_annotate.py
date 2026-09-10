"""Tests for `dlc_link.annotate` -- pure pose -> draw-primitive planning (D-61, Task 1,
plan 38-02)."""
import pytest

from dlc_link.annotate import CONFIDENT, UNCONFIDENT, build_draw_plan
from dlc_link.overlay import parse_overlay


class _SignalMap3Row:
    """A fake signal map declaring 2 bodyparts over a 3-row pose; `nose` has coords,
    `tail` does not."""

    SIGNAL_NAMES = ["nose_likelihood", "nose_x", "nose_y", "tail_likelihood"]
    SIGNALS = {
        "nose": {
            "index": 0,
            "coords": True,
            "signals": {"likelihood": "nose_likelihood", "x": "nose_x", "y": "nose_y"},
        },
        "tail": {
            "index": 2,
            "coords": False,
            "signals": {"likelihood": "tail_likelihood"},
        },
    }


class _SignalMap14Row:
    """Same declared bodyparts as `_SignalMap3Row`, but indexed into a 14-row pose --
    same code path, D-61's proof that nothing hardcodes a row count."""

    SIGNAL_NAMES = ["nose_likelihood", "nose_x", "nose_y", "tail_likelihood"]
    SIGNALS = {
        "nose": {
            "index": 0,
            "coords": True,
            "signals": {"likelihood": "nose_likelihood", "x": "nose_x", "y": "nose_y"},
        },
        "tail": {
            "index": 13,
            "coords": False,
            "signals": {"likelihood": "tail_likelihood"},
        },
    }


def _pose_3row(nose_likelihood=0.9, tail_likelihood=0.9):
    # [x, y, likelihood, col3, col4] -- columns 3/4 are uncharacterised and never read.
    return [
        [100.0, 200.0, nose_likelihood, 0.0, 0.0],
        [0.0, 0.0, 0.0, 0.0, 0.0],
        [50.0, 60.0, tail_likelihood, 0.0, 0.0],
    ]


def _pose_14row(nose_likelihood=0.9, tail_likelihood=0.9):
    rows = [[0.0, 0.0, 0.0, 0.0, 0.0] for _ in range(14)]
    rows[0] = [100.0, 200.0, nose_likelihood, 0.0, 0.0]
    rows[13] = [50.0, 60.0, tail_likelihood, 0.0, 0.0]
    return rows


class TestRowCountIndependence:
    @pytest.mark.parametrize(
        "signal_map, pose",
        [
            (_SignalMap3Row(), _pose_3row()),
            (_SignalMap14Row(), _pose_14row()),
        ],
    )
    def test_build_draw_plan_over_any_row_count(self, signal_map, pose):
        plan = build_draw_plan(pose, signal_map, 640, 480, min_likelihood=0.5)
        assert plan.problems == []
        kinds = [p.kind for p in plan.primitives]
        assert kinds.count("circle") == 1  # nose only -- tail has no coords
        assert kinds.count("text") == 2  # one label per declared keypoint


class TestProblemsOnIndexOverflow:
    def test_index_beyond_pose_length_is_reported_not_raised(self):
        signal_map = _SignalMap14Row()  # tail index 13
        short_pose = _pose_3row()  # only 3 rows
        plan = build_draw_plan(short_pose, signal_map, 640, 480, min_likelihood=0.5)
        assert len(plan.problems) == 1
        assert "tail" in plan.problems[0]
        assert "13" in plan.problems[0]
        assert "3" in plan.problems[0]
        # nose (index 0) is still drawn despite tail's problem.
        assert any(p.kind == "circle" for p in plan.primitives)


class TestConfidenceStyling:
    def test_likelihood_at_or_above_floor_is_confident_and_still_drawn(self):
        pose = _pose_3row(nose_likelihood=0.5)
        plan = build_draw_plan(pose, _SignalMap3Row(), 640, 480, min_likelihood=0.5)
        circle = next(p for p in plan.primitives if p.kind == "circle")
        assert circle.color == CONFIDENT["color"]

    def test_likelihood_below_floor_is_unconfident_and_still_drawn(self):
        pose = _pose_3row(nose_likelihood=0.2)
        plan = build_draw_plan(pose, _SignalMap3Row(), 640, 480, min_likelihood=0.5)
        circle = next(p for p in plan.primitives if p.kind == "circle")
        assert circle.color == UNCONFIDENT["color"]

    def test_colours_are_not_the_red_green_pair(self):
        # BGR: plain red is (0, 0, 255), plain green is (0, 255, 0).
        assert CONFIDENT["color"] not in ((0, 0, 255), (0, 255, 0))
        assert UNCONFIDENT["color"] not in ((0, 0, 255), (0, 255, 0))


class TestLabels:
    def test_every_keypoint_label_names_bodypart_and_likelihood_to_three_decimals(self):
        pose = _pose_3row(nose_likelihood=0.786123, tail_likelihood=0.4)
        plan = build_draw_plan(pose, _SignalMap3Row(), 640, 480, min_likelihood=0.5)
        texts = [p.text for p in plan.primitives if p.kind == "text"]
        assert "nose 0.786" in texts
        assert "tail 0.400" in texts

    def test_keypoint_without_coords_gets_label_but_no_marker(self):
        pose = _pose_3row()
        plan = build_draw_plan(pose, _SignalMap3Row(), 640, 480, min_likelihood=0.5)
        tail_texts = [p for p in plan.primitives if p.kind == "text" and "tail" in (p.text or "")]
        assert len(tail_texts) == 1
        # Only `nose` has coords declared, so exactly one circle total -- `tail`
        # contributes none.
        circles = [p for p in plan.primitives if p.kind == "circle"]
        assert len(circles) == 1


class TestIntegerCoordinates:
    def test_every_primitive_coordinate_field_is_int(self):
        pose = _pose_3row()
        overlay = parse_overlay("nose_x>0.50,nose_likelihood>0.6")
        plan = build_draw_plan(
            pose,
            _SignalMap3Row(),
            640,
            480,
            min_likelihood=0.5,
            overlay_clauses=overlay,
            overlay_values={"nose_x": 0.6, "nose_likelihood": 0.7},
        )
        for primitive in plan.primitives:
            for field_name in ("center", "position", "start", "end"):
                value = getattr(primitive, field_name)
                if value is not None:
                    for coordinate in value:
                        assert isinstance(coordinate, int)


class TestOverlayLines:
    def test_x_clause_produces_vertical_line_at_scaled_pixel_threshold(self):
        overlay = parse_overlay("nose_x>0.50")
        pose = _pose_3row()
        plan = build_draw_plan(pose, _SignalMap3Row(), 640, 480, min_likelihood=0.5, overlay_clauses=overlay)
        lines = [p for p in plan.primitives if p.kind == "line"]
        assert len(lines) == 1
        assert lines[0].start == (320, 0)  # 0.50 * 640
        assert lines[0].end == (320, 480)

    def test_y_clause_produces_horizontal_line_at_scaled_pixel_threshold(self):
        overlay = parse_overlay("nose_y>0.25")
        pose = _pose_3row()
        plan = build_draw_plan(pose, _SignalMap3Row(), 640, 480, min_likelihood=0.5, overlay_clauses=overlay)
        lines = [p for p in plan.primitives if p.kind == "line"]
        assert len(lines) == 1
        assert lines[0].start == (0, 120)  # 0.25 * 480
        assert lines[0].end == (640, 120)

    def test_likelihood_clause_produces_no_line(self):
        overlay = parse_overlay("nose_likelihood>0.6")
        pose = _pose_3row()
        plan = build_draw_plan(pose, _SignalMap3Row(), 640, 480, min_likelihood=0.5, overlay_clauses=overlay)
        assert not any(p.kind == "line" for p in plan.primitives)

    def test_line_carries_a_text_label_with_the_clause_as_typed(self):
        overlay = parse_overlay("nose_x>0.50")
        pose = _pose_3row()
        plan = build_draw_plan(pose, _SignalMap3Row(), 640, 480, min_likelihood=0.5, overlay_clauses=overlay)
        texts = [p.text for p in plan.primitives if p.kind == "text"]
        assert "nose_x>0.50" in texts


class TestOverlayHonestyLabel:
    def test_overlay_values_emits_condition_and_honesty_line(self):
        overlay = parse_overlay("nose_x>0.50,nose_likelihood>0.6")
        pose = _pose_3row()
        plan = build_draw_plan(
            pose,
            _SignalMap3Row(),
            640,
            480,
            min_likelihood=0.5,
            overlay_clauses=overlay,
            overlay_values={"nose_x": 0.6, "nose_likelihood": 0.7},
        )
        texts = [p.text for p in plan.primitives if p.kind == "text"]
        assert "condition: HOLDS" in texts
        assert "overlay: authored locally, not read from the task definition" in texts

    def test_condition_not_holding_is_reported_honestly(self):
        overlay = parse_overlay("nose_x>0.99")
        pose = _pose_3row()
        plan = build_draw_plan(
            pose,
            _SignalMap3Row(),
            640,
            480,
            min_likelihood=0.5,
            overlay_clauses=overlay,
            overlay_values={"nose_x": 0.1},
        )
        texts = [p.text for p in plan.primitives if p.kind == "text"]
        assert "condition: does not hold" in texts

    def test_no_overlay_values_means_no_condition_line(self):
        overlay = parse_overlay("nose_x>0.50")
        pose = _pose_3row()
        plan = build_draw_plan(pose, _SignalMap3Row(), 640, 480, min_likelihood=0.5, overlay_clauses=overlay)
        texts = [p.text for p in plan.primitives if p.kind == "text"]
        assert not any(t.startswith("condition:") for t in texts)


def test_module_has_no_third_party_imports():
    import dlc_link.annotate as module

    with open(module.__file__) as f:
        source = f.read()
    for forbidden in ("import cv2", "import numpy"):
        assert forbidden not in source


def test_authored_locally_string_present_in_source():
    import dlc_link.annotate as module

    with open(module.__file__) as f:
        source = f.read()
    assert source.count("authored locally") >= 1
