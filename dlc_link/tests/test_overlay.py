"""Tests for `dlc_link.overlay` -- parsing and evaluating the researcher's own
authored overlay threshold clauses (D-60, Task 1, plan 38-02)."""
import pytest

from dlc_link.overlay import Clause, OverlayError, evaluate, parse_overlay


class _FakeSignalMap:
    """Minimal stand-in for a loaded signal map: only the attribute `parse_overlay`
    reads (`SIGNAL_NAMES`)."""

    SIGNAL_NAMES = ["nose_likelihood", "nose_x", "nose_y", "tail_likelihood"]


class TestParseOverlayBasics:
    def test_two_clauses_preserve_operators_and_floats(self):
        clauses = parse_overlay("nose_x>0.50,nose_likelihood>0.6")
        assert clauses == [
            Clause(signal="nose_x", op=">", value=0.50, text="nose_x>0.50"),
            Clause(signal="nose_likelihood", op=">", value=0.6, text="nose_likelihood>0.6"),
        ]

    def test_tolerates_surrounding_whitespace(self):
        clauses = parse_overlay(" nose_x > 0.5 , nose_y < 0.9 ")
        assert [c.signal for c in clauses] == ["nose_x", "nose_y"]
        assert [c.op for c in clauses] == [">", "<"]
        assert [c.value for c in clauses] == [0.5, 0.9]

    @pytest.mark.parametrize("op", [">", "<", ">=", "<="])
    def test_accepts_every_supported_operator(self, op):
        clauses = parse_overlay("nose_x{}0.5".format(op))
        assert clauses[0].op == op

    def test_empty_string_raises(self):
        with pytest.raises(OverlayError):
            parse_overlay("")

    def test_empty_clause_raises(self):
        with pytest.raises(OverlayError):
            parse_overlay("nose_x>0.5,,nose_y>0.2")


class TestParseOverlayRejectsEquality:
    def test_rejects_bare_equals(self):
        with pytest.raises(OverlayError) as exc_info:
            parse_overlay("nose_x=0.5")
        message = str(exc_info.value)
        assert "nose_x=0.5" in message
        assert "never what was meant" in message

    def test_rejects_double_equals(self):
        with pytest.raises(OverlayError):
            parse_overlay("nose_x==0.5")

    def test_rejects_no_recognised_operator(self):
        with pytest.raises(OverlayError):
            parse_overlay("nose_x 0.5")

    def test_rejects_non_float_value(self):
        with pytest.raises(OverlayError):
            parse_overlay("nose_x>not-a-number")


class TestParseOverlayAgainstSignalMap:
    def test_refuses_undeclared_signal_and_lists_declared_names(self):
        with pytest.raises(OverlayError) as exc_info:
            parse_overlay("nose_zz>0.5", _FakeSignalMap())
        message = str(exc_info.value)
        assert "nose_zz" in message
        for declared in _FakeSignalMap.SIGNAL_NAMES:
            assert declared in message

    def test_accepts_declared_signal(self):
        clauses = parse_overlay("nose_x>0.5", _FakeSignalMap())
        assert clauses[0].signal == "nose_x"

    def test_no_signal_map_skips_the_declared_name_check(self):
        clauses = parse_overlay("anything_goes>0.5")
        assert clauses[0].signal == "anything_goes"


class TestEvaluate:
    def test_all_clauses_hold_returns_overall_true(self):
        clauses = parse_overlay("nose_x>0.50,nose_likelihood>0.6")
        overall, results = evaluate(clauses, {"nose_x": 0.6, "nose_likelihood": 0.7})
        assert overall is True
        assert [r for _, r in results] == [True, True]

    def test_one_clause_fails_returns_overall_false(self):
        clauses = parse_overlay("nose_x>0.50,nose_likelihood>0.6")
        overall, results = evaluate(clauses, {"nose_x": 0.1, "nose_likelihood": 0.7})
        assert overall is False
        assert [r for _, r in results] == [False, True]

    def test_missing_signal_evaluates_to_none_and_overall_false(self):
        clauses = parse_overlay("nose_x>0.50")
        overall, results = evaluate(clauses, {})
        assert results[0][1] is None
        assert overall is False

    def test_missing_signal_never_makes_overall_true(self):
        clauses = parse_overlay("nose_x>0.50,nose_y>0.1")
        overall, _ = evaluate(clauses, {"nose_x": 0.9})  # nose_x holds, nose_y missing
        assert overall is False

    def test_never_raises_on_empty_clause_list(self):
        overall, results = evaluate([], {"anything": 1})
        assert overall is True
        assert results == []

    @pytest.mark.parametrize(
        "op, value, threshold, expected",
        [
            (">", 0.6, 0.5, True),
            (">", 0.4, 0.5, False),
            ("<", 0.4, 0.5, True),
            ("<", 0.6, 0.5, False),
            (">=", 0.5, 0.5, True),
            ("<=", 0.5, 0.5, True),
        ],
    )
    def test_operator_semantics(self, op, value, threshold, expected):
        clauses = parse_overlay("nose_x{}{}".format(op, threshold))
        overall, results = evaluate(clauses, {"nose_x": value})
        assert results[0][1] is expected
        assert overall is expected


def test_module_has_no_third_party_imports():
    import dlc_link.overlay as module

    with open(module.__file__) as f:
        source = f.read()
    for forbidden in ("import cv2", "import numpy"):
        assert forbidden not in source
