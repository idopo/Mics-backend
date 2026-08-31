"""Tests for `dlc_link.names` — the single bodypart-string to Python-identifier
transform (D-12) and its safety gate (T-35-01, T-35-02, T-35-02b).
"""
import re

import pytest

from dlc_link.names import (
    InvalidBodypartName,
    build_name_map,
    flat_signal_names,
    signal_names_for,
    to_identifier,
)

_VALID_IDENT = re.compile(r"^[a-z][a-z0-9_]*$")


class TestToIdentifierHappyPath:
    def test_space_becomes_underscore(self):
        assert to_identifier("left ear") == "left_ear"

    def test_hyphen_becomes_underscore(self):
        assert to_identifier("tail-base") == "tail_base"

    def test_lowercased(self):
        assert to_identifier("Nose") == "nose"

    def test_double_space_collapses_to_one_underscore(self):
        assert to_identifier("snout  2") == "snout_2"

    def test_leading_trailing_underscores_stripped(self):
        assert to_identifier("__nose__") == "nose"


class TestToIdentifierRejections:
    def test_leading_digit_raises_rather_than_prefixing(self):
        with pytest.raises(InvalidBodypartName):
            to_identifier("2nd_paw")

    def test_empty_string_raises(self):
        with pytest.raises(InvalidBodypartName):
            to_identifier("")

    def test_only_symbols_raises(self):
        with pytest.raises(InvalidBodypartName):
            to_identifier("!!!")

    def test_python_keyword_raises(self):
        with pytest.raises(InvalidBodypartName):
            to_identifier("class")

    def test_reserved_alive_raises(self):
        with pytest.raises(InvalidBodypartName):
            to_identifier("alive")


class TestBuildNameMapCollisions:
    def test_collision_names_both_originals_and_the_identifier(self):
        with pytest.raises(InvalidBodypartName) as excinfo:
            build_name_map(["left ear", "left-ear"], ["left ear"], set())
        message = str(excinfo.value)
        assert "left ear" in message
        assert "left-ear" in message
        assert "left_ear" in message

    def test_wanted_absent_from_pose_order_lists_pose_order_contents(self):
        pose_order = ["a", "b", "c", "d", "e"]
        with pytest.raises(InvalidBodypartName) as excinfo:
            build_name_map(pose_order, ["not_in_the_model"], set())
        message = str(excinfo.value)
        assert "not_in_the_model" in message
        for entry in pose_order:
            assert entry in message

    def test_coords_for_not_subset_of_wanted_raises(self):
        pose_order = ["a", "b", "c", "d", "e"]
        with pytest.raises(InvalidBodypartName):
            build_name_map(pose_order, ["a"], {"b"})


class TestBuildNameMapIndexing:
    def test_indices_come_from_pose_order_not_from_filtered_selection(self):
        pose_order = ["a", "b", "c", "d", "e"]
        wanted = ["d", "e"]
        name_map = build_name_map(pose_order, wanted, set())
        assert name_map["d"]["index"] == 3
        assert name_map["e"]["index"] == 4

    def test_coords_flag_and_signals_shape(self):
        pose_order = ["nose", "tail"]
        name_map = build_name_map(pose_order, ["nose", "tail"], {"nose"})
        assert name_map["nose"]["coords"] is True
        assert name_map["nose"]["signals"] == {
            "likelihood": "nose_likelihood",
            "x": "nose_x",
            "y": "nose_y",
        }
        assert name_map["tail"]["coords"] is False
        assert name_map["tail"]["signals"] == {"likelihood": "tail_likelihood"}


class TestSignalNamesFor:
    def test_likelihood_only_when_coords_false(self):
        assert signal_names_for("nose", coords=False) == ["nose_likelihood"]

    def test_likelihood_and_xy_when_coords_true(self):
        assert signal_names_for("nose", coords=True) == [
            "nose_likelihood",
            "nose_x",
            "nose_y",
        ]


class TestFlatSignalNames:
    def test_sorted_and_deduplicated(self):
        pose_order = ["nose", "tail"]
        name_map = build_name_map(pose_order, ["nose", "tail"], {"nose", "tail"})
        names = flat_signal_names(name_map)
        assert names == sorted(names)
        assert len(names) == len(set(names))
        assert names == [
            "nose_likelihood",
            "nose_x",
            "nose_y",
            "tail_likelihood",
            "tail_x",
            "tail_y",
        ]


class TestEveryProducedNameIsSafe:
    def test_every_produced_name_matches_the_identifier_regex(self):
        pose_order = ["left ear", "tail-base", "Nose", "snout  2", "__nose2__"]
        name_map = build_name_map(pose_order, pose_order, set(pose_order))
        for name in flat_signal_names(name_map):
            assert _VALID_IDENT.match(name), name
