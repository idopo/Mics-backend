"""DLC-09's regression test: prove `dlc_link.convert`'s output is consumable by the REAL
reader `sdk/src/mics_link/replay_io.py` uses, and drivable by the REAL `mics_link.replay`
driver -- no reimplementation of either. This is the artefact that lets the whole DLC path
be replayed with no camera, no GPU and no trained model (plan 35-05, Task 3).
"""
import os

from dlc_link.config_read import read_dlc_config
from dlc_link.convert import flatten_columns, rows_to_wide, write_wide_csv
from dlc_link.generate import generate
from dlc_link.signal_map import load_signal_map

from mics_link.replay import replay
from mics_link.replay_io import read_rows

FIXTURES = os.path.join(os.path.dirname(__file__), "fixtures")
MADLC_CONFIG = os.path.join(FIXTURES, "dlc3_multianimal_config.yaml")
POSE_ORDER_FILE = os.path.join(FIXTURES, "pose_order_declared.txt")

FPS = 10
LIKELIHOOD_THRESHOLD = 0.5

# Six frames: confident (0, 1), occluded below threshold (2, 3), confident again (4, 5).
_NOSE_LIKELIHOODS = [0.95, 0.93, 0.02, 0.01, 0.90, 0.92]
_LED_ON_LIKELIHOOD = 0.9
_NOSE_XY = (0.5, 0.5)


class _FakeLink:
    """The minimal surface `replay()` needs: `send_signal(signal, value) -> bool`. Never
    drops or rejects, so `stats.sent` equals exactly the number of non-empty cells fed to
    it -- this is a fake link, not a reimplementation of `read_rows`/`replay` themselves."""

    def __init__(self):
        self.sent = []

    def send_signal(self, signal, value):
        self.sent.append((signal, value))
        return True


def _pose_order():
    with open(POSE_ORDER_FILE) as handle:
        return [
            line.strip() for line in handle if line.strip() and not line.strip().startswith("#")
        ]


def _generated_signal_map(tmp_path):
    """Two bodyparts, one with coordinates (`nose`) and one likelihood-only (`LED_on`) --
    generated for real via `dlc_link.generate.generate`, written to disk, and loaded back
    via `dlc_link.signal_map.load_signal_map`, exactly the path the adapter/converter use
    in production. Never a hand-built stand-in."""
    result = generate(
        source=read_dlc_config(MADLC_CONFIG),
        pose_order=_pose_order(),
        pose_order_source="probe",
        wanted=["nose", "LED_on"],
        coords_for={"nose"},
        source_id="dlc_cam1",
    )
    map_path = tmp_path / "dlc_cam1_signals.py"
    map_path.write_text(result.map_source)
    return load_signal_map(map_path)


def _dlc_columns():
    return [
        ("scorerA", "nose", "x"),
        ("scorerA", "nose", "y"),
        ("scorerA", "nose", "likelihood"),
        ("scorerA", "LED_on", "likelihood"),
    ]


def _dlc_rows():
    x, y = _NOSE_XY
    return [(x, y, likelihood, _LED_ON_LIKELIHOOD) for likelihood in _NOSE_LIKELIHOODS]


def _convert(tmp_path, smap):
    position_to_name, counts = flatten_columns(_dlc_columns(), smap)
    assert counts == {"bodyparts_skipped_undeclared": 0, "coords_skipped_unrecognised": 0}
    header_names = sorted(set(position_to_name.values()))
    wide_rows = rows_to_wide(
        _dlc_rows(), position_to_name, fps=FPS, likelihood_threshold=LIKELIHOOD_THRESHOLD
    )
    out_path = tmp_path / "replay.csv"
    rows_written = write_wide_csv(out_path, header_names, wide_rows)
    assert rows_written == len(_NOSE_LIKELIHOODS)
    return out_path, header_names


def test_converter_output_round_trips_through_the_real_replay_reader(tmp_path):
    smap = _generated_signal_map(tmp_path)
    out_path, header_names = _convert(tmp_path, smap)

    stats_holder = {}
    from mics_link.replay_io import ReplayStats

    stats = ReplayStats()
    tuples = list(read_rows(out_path, stats=stats))
    stats_holder["stats"] = stats

    assert stats.rows_malformed == 0

    # every emitted signal name is a declared signal from the generated map
    for _t, signal, _value in tuples:
        assert signal in smap.SIGNAL_NAMES

    # t values ascend by 1/fps
    ts = sorted(set(t for t, _s, _v in tuples))
    assert ts == [round(i / FPS, 10) for i in range(len(_NOSE_LIKELIHOODS))]

    # the occluded stretch (frames 2, 3 -> t=0.2, 0.3) yields likelihood tuples but NO
    # x/y tuples for those timestamps
    occluded_ts = {round(2 / FPS, 10), round(3 / FPS, 10)}
    for t, signal, _value in tuples:
        if round(t, 10) in occluded_ts:
            assert signal in ("nose_likelihood", "led_on_likelihood")
            assert signal not in ("nose_x", "nose_y")

    # confident frames (0, 1, 4, 5) DO carry nose_x/nose_y tuples
    confident_ts = {round(i / FPS, 10) for i in (0, 1, 4, 5)}
    for t_target in confident_ts:
        signals_at_t = {signal for t, signal, _v in tuples if round(t, 10) == t_target}
        assert {"nose_x", "nose_y", "nose_likelihood", "led_on_likelihood"} == signals_at_t


def test_header_detected_as_wide_not_ambiguous_and_a_populated_row_shares_one_t(tmp_path):
    smap = _generated_signal_map(tmp_path)
    out_path, _header_names = _convert(tmp_path, smap)

    # read_rows must not raise (a wide header is correctly detected, never "ambiguous")
    tuples = list(read_rows(out_path))
    assert tuples  # non-empty: read_rows did not silently produce nothing

    # a confident row (t=0.0) has three populated cells (nose_x, nose_y, nose_likelihood)
    # sharing exactly one t, plus led_on_likelihood -- four total, one shared t
    first_row_tuples = [tup for tup in tuples if round(tup[0], 10) == 0.0]
    assert len(first_row_tuples) == 4
    assert len({t for t, _s, _v in first_row_tuples}) == 1


def test_replay_drives_a_fake_link_and_counts_match_non_empty_cells(tmp_path):
    smap = _generated_signal_map(tmp_path)
    out_path, _header_names = _convert(tmp_path, smap)

    from mics_link.replay_io import ReplayStats

    stats = ReplayStats()
    rows = read_rows(out_path, stats=stats)
    link = _FakeLink()
    replay(link, rows, mode="fast", stats=stats)

    # 4 confident frames x 4 signals + 2 occluded frames x 2 signals (likelihood only)
    expected_non_empty_cells = 4 * 4 + 2 * 2
    assert stats.sent == expected_non_empty_cells
    assert stats.rejected == 0
    assert len(link.sent) == expected_non_empty_cells


def test_wide_file_line_count_is_frame_count_plus_one_not_frame_times_signals(tmp_path):
    """D-31's size arithmetic: for N frames and M signals, the wide file has N+1 lines,
    while the long-format equivalent would have N*M+1. This must fail loudly if a future
    change turns the writer into a long-format writer."""
    smap = _generated_signal_map(tmp_path)
    out_path, header_names = _convert(tmp_path, smap)

    with open(out_path, encoding="utf-8") as handle:
        line_count = sum(1 for _ in handle)

    n_frames = len(_NOSE_LIKELIHOODS)
    m_signals = len(header_names)
    assert line_count == n_frames + 1
    assert line_count != n_frames * m_signals + 1
