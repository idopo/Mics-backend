"""Tests for dlc_link.processor (Task 2, plan 35-04)."""
import pytest

from dlc_link.config_read import from_explicit_list
from dlc_link.decimate import DecimateStats, Decimator
from dlc_link.generate import generate
from dlc_link.processor import DLCLIVE_AVAILABLE, DLCProcessor, PoseShapeError
from dlc_link.signal_map import load_signal_map
from mics_link.errors import InvalidValueError


class FakeLink:
    """Records every `send_signal` call; optionally cycles a fixed accept/drop pattern."""

    def __init__(self, accept_pattern=None):
        self.calls = []
        self._accept_pattern = accept_pattern
        self._i = 0

    def send_signal(self, name, value):
        self.calls.append((name, value))
        if self._accept_pattern is None:
            return True
        result = self._accept_pattern[self._i % len(self._accept_pattern)]
        self._i += 1
        return result


class RejectingLink(FakeLink):
    """Raises InvalidValueError for any signal name in `reject_names`."""

    def __init__(self, reject_names):
        super().__init__()
        self._reject_names = set(reject_names)

    def send_signal(self, name, value):
        self.calls.append((name, value))
        if name in self._reject_names:
            raise InvalidValueError("rejected for test")
        return True


class _AlwaysSuppressDecimator:
    def __init__(self):
        self.stats = DecimateStats()

    def should_send(self, name, value):
        self.stats.considered += 1
        self.stats.suppressed_deadband += 1
        return False


class _CountingList(list):
    """Wraps a list, counting `len()` calls -- used to prove the row-count guard reads
    the expected length exactly once (at construction), never per frame."""

    def __init__(self, *args):
        super().__init__(*args)
        self.len_calls = 0

    def __len__(self):
        self.len_calls += 1
        return super().__len__()


def _build_map(
    tmp_path,
    wanted=("nose", "tail"),
    coords_for=("nose",),
    pose_order=("nose", "tail"),
    pose_order_source="probe",
    name="dlc_cam1_signals.py",
):
    source = from_explicit_list(list(pose_order))
    result = generate(
        source=source,
        pose_order=list(pose_order),
        pose_order_source=pose_order_source,
        wanted=list(wanted),
        coords_for=set(coords_for),
        source_id="dlc_cam1",
    )
    path = tmp_path / name
    path.write_text(result.map_source)
    return load_signal_map(path)


def test_import_with_no_dlclive_reports_unavailable():
    assert DLCLIVE_AVAILABLE is False


def test_two_bodyparts_yields_expected_names_in_likelihood_first_order(tmp_path):
    smap = _build_map(tmp_path)
    link = FakeLink()
    processor = DLCProcessor(link, smap, frame_width=100, frame_height=100)
    pose = [[10.0, 20.0, 0.9], [30.0, 40.0, 0.8]]
    result = processor.process(pose)
    names = [name for name, _value in link.calls]
    assert names == ["nose_likelihood", "nose_x", "nose_y", "tail_likelihood"]
    assert result is pose


def test_normalisation_is_resolution_independent(tmp_path):
    smap = _build_map(tmp_path, wanted=("nose",), coords_for=("nose",), pose_order=("nose",))

    link_a = FakeLink()
    DLCProcessor(link_a, smap, frame_width=1280, frame_height=960).process([[640.0, 480.0, 0.9]])

    link_b = FakeLink()
    DLCProcessor(link_b, smap, frame_width=1920, frame_height=1080).process([[960.0, 540.0, 0.9]])

    assert dict(link_a.calls)["nose_x"] == dict(link_b.calls)["nose_x"] == 0.5
    assert dict(link_a.calls)["nose_y"] == dict(link_b.calls)["nose_y"] == 0.5


def test_values_are_native_float_with_numpy_array(tmp_path):
    numpy = pytest.importorskip("numpy")
    smap = _build_map(tmp_path, wanted=("nose",), coords_for=("nose",), pose_order=("nose",))
    link = FakeLink()
    pose = numpy.array([[10.0, 20.0, 0.9]], dtype=numpy.float64)
    DLCProcessor(link, smap, frame_width=100, frame_height=100).process(pose)
    assert link.calls
    for _name, value in link.calls:
        assert type(value) is float


def test_values_are_native_float_with_plain_python_list(tmp_path):
    smap = _build_map(tmp_path, wanted=("nose",), coords_for=("nose",), pose_order=("nose",))
    link = FakeLink()
    DLCProcessor(link, smap, frame_width=100, frame_height=100).process([[10.0, 20.0, 0.9]])
    assert link.calls
    for _name, value in link.calls:
        assert type(value) is float


def test_3d_pose_raises_pose_shape_error(tmp_path):
    numpy = pytest.importorskip("numpy")
    smap = _build_map(tmp_path, wanted=("nose",), coords_for=("nose",), pose_order=("nose",))
    processor = DLCProcessor(FakeLink(), smap, frame_width=100, frame_height=100)
    pose = numpy.zeros((2, 1, 3))
    with pytest.raises(PoseShapeError) as excinfo:
        processor.process(pose)
    message = str(excinfo.value)
    assert "single_animal=True" in message
    assert "stitch_tracklets" in message


def test_row_count_mismatch_raises_naming_both_numbers(tmp_path):
    smap = _build_map(tmp_path, wanted=("nose",), coords_for=("nose",), pose_order=("nose", "tail"))
    processor = DLCProcessor(FakeLink(), smap, frame_width=100, frame_height=100)
    with pytest.raises(PoseShapeError) as excinfo:
        processor.process([[10.0, 20.0, 0.9]])
    message = str(excinfo.value)
    assert "2" in message
    assert "1" in message


def test_row_count_mismatch_names_probe_when_unverified(tmp_path):
    smap = _build_map(
        tmp_path,
        wanted=("nose",),
        coords_for=("nose",),
        pose_order=("nose", "tail"),
        pose_order_source="config-declared-UNVERIFIED",
    )
    processor = DLCProcessor(FakeLink(), smap, frame_width=100, frame_height=100)
    with pytest.raises(PoseShapeError) as excinfo:
        processor.process([[10.0, 20.0, 0.9]])
    assert "35-07" in str(excinfo.value)


def test_row_count_check_reads_pose_order_length_only_once(tmp_path):
    smap = _build_map(tmp_path, wanted=("nose",), coords_for=set(), pose_order=("nose",))
    smap.POSE_ORDER = _CountingList(smap.POSE_ORDER)
    processor = DLCProcessor(FakeLink(), smap, frame_width=100, frame_height=100)
    for _ in range(5):
        processor.process([[10.0, 20.0, 0.9]])
    assert smap.POSE_ORDER.len_calls == 1


def test_process_returns_identical_object(tmp_path):
    smap = _build_map(tmp_path, wanted=("nose",), coords_for=set(), pose_order=("nose",))
    processor = DLCProcessor(FakeLink(), smap, frame_width=100, frame_height=100)
    pose = [[10.0, 20.0, 0.9]]
    assert processor.process(pose) is pose


def test_dropped_send_increments_counter_and_calls_on_drop(tmp_path):
    smap = _build_map(tmp_path, wanted=("nose",), coords_for=set(), pose_order=("nose",))
    link = FakeLink(accept_pattern=[False])
    dropped = []
    processor = DLCProcessor(
        link, smap, frame_width=100, frame_height=100, on_drop=dropped.append, decimator=Decimator()
    )
    processor.process([[10.0, 20.0, 0.9]])
    assert processor.signals_dropped == 1
    assert dropped == ["nose_likelihood"]


def test_out_of_range_coordinate_sent_unclamped(tmp_path):
    smap = _build_map(tmp_path, wanted=("nose",), coords_for=("nose",), pose_order=("nose",))
    link = FakeLink()
    processor = DLCProcessor(link, smap, frame_width=100, frame_height=100)
    processor.process([[150.0, 20.0, 0.9]])
    assert dict(link.calls)["nose_x"] == 1.5
    assert processor.out_of_frame == 1


def test_decimator_that_suppresses_everything_yields_zero_sends(tmp_path):
    smap = _build_map(tmp_path, wanted=("nose",), coords_for=("nose",), pose_order=("nose",))
    link = FakeLink()
    processor = DLCProcessor(
        link, smap, frame_width=100, frame_height=100, decimator=_AlwaysSuppressDecimator()
    )
    processor.process([[10.0, 20.0, 0.9]])
    assert link.calls == []
    assert processor.signals_suppressed > 0


def test_invalid_value_error_increments_values_rejected_and_does_not_propagate(tmp_path):
    smap = _build_map(tmp_path, wanted=("nose",), coords_for=set(), pose_order=("nose",))
    link = RejectingLink(reject_names={"nose_likelihood"})
    processor = DLCProcessor(link, smap, frame_width=100, frame_height=100)
    pose = [[10.0, 20.0, 0.9]]
    result = processor.process(pose)
    assert processor.values_rejected == 1
    assert result is pose


def test_save_returns_true_without_touching_link(tmp_path):
    smap = _build_map(tmp_path, wanted=("nose",), coords_for=set(), pose_order=("nose",))
    link = FakeLink()
    processor = DLCProcessor(link, smap, frame_width=100, frame_height=100)
    assert processor.save() is True
    assert link.calls == []


def test_snapshot_keys_contain_no_timing_words(tmp_path):
    smap = _build_map(tmp_path, wanted=("nose",), coords_for=set(), pose_order=("nose",))
    processor = DLCProcessor(FakeLink(), smap, frame_width=100, frame_height=100)
    processor.process([[10.0, 20.0, 0.9]])
    snapshot = processor.snapshot()
    forbidden = ("latency", "jitter", "drift", "elapsed", "duration")
    for key in snapshot:
        assert not any(word in key.lower() for word in forbidden)
