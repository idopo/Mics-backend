"""Tests for dlc_link.config_read (Task 1, plan 35-03)."""
import os

import pytest

from dlc_link.config_read import (
    BodypartSource,
    ConfigReadError,
    SentinelSelectedError,
    UnknownBodypartsError,
    from_explicit_list,
    load_yaml,
    read_dlc_config,
    read_pose_cfg,
    select,
    warn_multianimal_identity,
)

FIXTURES = os.path.join(os.path.dirname(__file__), "fixtures")
MADLC_CONFIG = os.path.join(FIXTURES, "dlc3_multianimal_config.yaml")
SINGLE_CONFIG = os.path.join(FIXTURES, "dlc3_singleanimal_config.yaml")
TF_POSE_CFG = os.path.join(FIXTURES, "tf_pose_cfg.yaml")


def test_load_yaml_via_pyyaml_fallback():
    # The dev host has PyYAML and no ruamel.yaml -- this exercises that fallback path.
    data = load_yaml(MADLC_CONFIG)
    assert isinstance(data, dict)
    assert data["engine"] == "pytorch"


def test_madlc_reads_three_sources_and_sentinel():
    source = read_dlc_config(MADLC_CONFIG)
    assert source.multianimal is True
    assert source.engine == "pytorch"
    assert source.source_format == "config.yaml"
    assert source.bodyparts_sentinel == "MULTI!"
    assert source.bodyparts == [], "flat bodyparts must stay empty on a maDLC project"
    assert len(source.multianimal_bodyparts) == 10
    assert len(source.unique_bodyparts) == 22
    assert "LED_on" in source.unique_bodyparts
    assert "NW" in source.unique_bodyparts
    assert source.individuals and len(source.individuals) == 5
    assert source.identity is False


def test_madlc_sentinel_never_iterated():
    source = read_dlc_config(MADLC_CONFIG)
    for char in "MULTI!":
        assert char not in source.multianimal_bodyparts
        assert char not in source.unique_bodyparts


def test_madlc_candidate_count_is_72():
    source = read_dlc_config(MADLC_CONFIG)
    assert source.candidate_count() == 72


def test_madlc_sha256_is_hex64_and_stable():
    source1 = read_dlc_config(MADLC_CONFIG)
    source2 = read_dlc_config(MADLC_CONFIG)
    assert source1.sha256 and len(source1.sha256) == 64
    assert source1.sha256 == source2.sha256


def test_select_sentinel_raises_with_sentinel_quoted():
    source = read_dlc_config(MADLC_CONFIG)
    with pytest.raises(SentinelSelectedError, match="MULTI!"):
        select(source, ["MULTI!"])


def test_select_returns_class_per_wanted_name():
    source = read_dlc_config(MADLC_CONFIG)
    result = select(source, ["nose", "LED_on"])
    assert result == [("nose", "multianimal"), ("LED_on", "unique")]


def test_select_unknown_name_raises_and_lists_available():
    source = read_dlc_config(MADLC_CONFIG)
    with pytest.raises(UnknownBodypartsError) as excinfo:
        select(source, ["not_a_part"])
    message = str(excinfo.value)
    assert "not_a_part" in message
    assert "LED_on" in message or "nose" in message


def test_warn_multianimal_identity_false_names_stitch_tracklets():
    source = read_dlc_config(MADLC_CONFIG)
    warning = warn_multianimal_identity(source)
    assert warning is not None
    assert "stitch_tracklets" in warning


def test_warn_multianimal_identity_true_is_none():
    source = read_dlc_config(SINGLE_CONFIG)
    # Single-animal source: multianimal is False, so no warning regardless of identity.
    assert warn_multianimal_identity(source) is None


def test_read_dlc_config_single_animal_flat_list():
    source = read_dlc_config(SINGLE_CONFIG)
    assert source.multianimal is False
    assert source.bodyparts == ["nose", "left_ear", "right_ear", "tail_base"]
    assert source.unique_bodyparts == ["arena_center"]
    assert source.bodyparts_sentinel is None
    assert source.individuals is None


def test_read_pose_cfg_tensorflow():
    source = read_pose_cfg(TF_POSE_CFG)
    assert source.engine == "tensorflow"
    assert source.source_format == "pose_cfg.yaml"
    assert source.multianimal is False
    assert source.bodyparts == ["nose", "left_paw", "right_paw", "tail_tip"]
    assert source.individuals is None


def test_read_pose_cfg_missing_key_raises():
    import tempfile

    with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as handle:
        handle.write("dataset: x\n")
        path = handle.name
    try:
        with pytest.raises(ConfigReadError):
            read_pose_cfg(path)
    finally:
        os.remove(path)


def test_from_explicit_list_is_labelled_and_unhashed():
    source = from_explicit_list(["nose", "tail"])
    assert source.source_format == "explicit-list"
    assert source.engine == "unknown"
    assert source.path is None
    assert source.sha256 is None
    assert source.bodyparts == ["nose", "tail"]


def test_bodypartsource_is_frozen():
    source = from_explicit_list(["nose"])
    with pytest.raises(Exception):
        source.bodyparts = ["tail"]
