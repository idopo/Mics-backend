"""RunAccumulator checks, built from the shape of the first real rig run (run 573).

Run 573 (RecordingBox, 2026-08-24, clock_probe_short on Mid_LED, 62 s) produced exactly:
  - 62 groups of 2 documents, both ts_source=hardware, sharing one t_mono_ns
    (the logging_utils.py:97 `record_event` route and the task.py:283 `pi_timestamp` route)
  - 252 single-document groups, all ts_source=software

That is a perfect cross-route result -- every hardware edge landed as exactly two documents --
yet C3 reported pairing_rate 0.197 FAIL, because software documents were being counted in the
pairing denominator. C3's claim (see es_clock_check.py's module docstring) is about *hardware
edges*; software documents are single-route by construction and can never pair.

Run with:  python3 -m pytest -q tools/tests/
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from clock_check_accumulator import RunAccumulator


def _doc(t_mono: int, ts_source: str, *, route: str = "record_event") -> dict:
    """One event_log_v2 document, in the field shape run 573 actually wrote."""
    event_data: dict = {"id": "Mid_LED"}
    if route == "record_event":
        event_data.update({"result": None, "func_name": "record_event"})
    else:
        event_data.update({
            "pi_timestamp": "2026-08-24T18:13:30.976265+03:00",
            "pi_timestamp_mono_ns": t_mono,
            "pi_timestamp_source": "hardware",
        })
    return {
        "_source": {
            "t_mono_ns": t_mono,
            "t_utc_ns": 1787584410976265902 + t_mono,
            "ts_source": ts_source,
            "event": {"event_type": "gpio.Digital_Out", "event_data": event_data},
        }
    }


def _run_573_shape(n_edges: int = 62, n_software: int = 252) -> list[dict]:
    """Documents in `iter_run_documents` order: sorted by t_mono_ns ascending."""
    docs = []
    t = 3_839_296_775_883
    for i in range(n_edges):
        edge_t = t + i * 1_000_000_000  # ~1 Hz edges
        docs.append(_doc(edge_t, "hardware", route="record_event"))
        docs.append(_doc(edge_t, "hardware", route="pi_timestamp"))
    # software documents each carry their own distinct t_mono_ns
    for j in range(n_software):
        docs.append(_doc(t + 500_000_000 + j * 7_000_000, "software"))
    docs.sort(key=lambda d: d["_source"]["t_mono_ns"])
    return docs


def _feed(docs: list[dict], *, pulse_period_s: float | None = None) -> dict:
    acc = RunAccumulator(
        pulse_period_s=pulse_period_s,
        step_time_utc=None,
        step_window_s=30.0,
        max_examples=5,
    )
    for d in docs:
        acc.add(d)
    return acc.finalize()


def test_c3_passes_when_every_hardware_edge_is_paired():
    """The regression this file exists for: 62/62 hardware edges paired is a PASS."""
    report = _feed(_run_573_shape())
    c3 = report["C3_cross_route_pairing"]
    assert c3["groups_total"] == 62, "software docs must not enter the pairing denominator"
    assert c3["groups_matched"] == 62
    assert c3["pairing_rate"] == 1.0
    assert c3["pass"] is True


def test_c3_still_fails_on_a_genuinely_unpaired_hardware_edge():
    """Guard against 'fixing' C3 into something that can never fail: drop one route of one
    edge and the check must go red."""
    docs = _run_573_shape()
    # remove the second route of the first hardware edge
    first_t = min(d["_source"]["t_mono_ns"] for d in docs if d["_source"]["ts_source"] == "hardware")
    hardware_at_first = [
        d for d in docs
        if d["_source"]["ts_source"] == "hardware" and d["_source"]["t_mono_ns"] == first_t
    ]
    docs.remove(hardware_at_first[-1])

    c3 = _feed(docs)["C3_cross_route_pairing"]
    assert c3["groups_total"] == 62
    assert c3["groups_matched"] == 61
    assert c3["pass"] is False


def test_c1_still_sees_every_document():
    """C3's denominator narrowed to hardware; C1 monotonicity must still span ALL documents --
    a backward jump in a software document is just as much a clock defect."""
    report = _feed(_run_573_shape())
    c1 = report["C1_monotonic"]
    assert c1["docs_with_t_mono_ns"] == 62 * 2 + 252
    assert c1["backward_count"] == 0
    assert c1["pass"] is True


def test_c4_provenance_counts_are_unchanged():
    c4 = _feed(_run_573_shape())["C4_provenance"]
    assert c4["hardware_docs"] == 124
    assert c4["software_docs"] == 252
    assert c4["other_ts_source_docs"] == 0
    assert c4["hardware_without_mono_field"] == 0


def test_c7_drop_gaps_measure_hardware_edges_only():
    """C7 asks whether a commanded pulse edge went missing. Software documents are not pulse
    edges, so they must not close the gap between two hardware edges."""
    docs = _run_573_shape()
    c7 = _feed(docs, pulse_period_s=1.0)["C7_drops"]
    assert c7["gaps_over_2x_period"] == 0

    # Drop two CONSECUTIVE edges -> a 3 s gap at a 1 s period. Two are needed, not one:
    # a single dropped edge leaves exactly 2 x period, and the check is `> 2x`, which
    # deliberately excludes the boundary so ordinary jitter cannot false-positive.
    edge_ts = sorted({
        d["_source"]["t_mono_ns"] for d in docs if d["_source"]["ts_source"] == "hardware"
    })
    victims = set(edge_ts[len(edge_ts) // 2:][:2])
    thinned = [
        d for d in docs
        if not (d["_source"]["ts_source"] == "hardware"
                and d["_source"]["t_mono_ns"] in victims)
    ]
    c7_gap = _feed(thinned, pulse_period_s=1.0)["C7_drops"]
    assert c7_gap["gaps_over_2x_period"] == 1, (
        "the 252 software documents must not close the gap left by the missing edges"
    )
