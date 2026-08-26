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
    # `pass` is deliberately None, not True: iter_run_documents sorts by t_mono_ns, so zero
    # backward steps is a property of that sort and never of the clock. The coverage claim
    # this test makes -- C1 spans software documents too -- lives in docs_with_t_mono_ns.
    assert c1["pass"] is None


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


# ---------------------------------------------------------------------------
# C3 is a per-module claim: only record=True hardware has two routes
# ---------------------------------------------------------------------------
# Run 574 added the licker and C3 went red again at 11/51, on clean data:
#
#   Mid_LED    11 groups of 2   record_event + pi_timestamp   (record=True)
#   TOUCH_INT  40 groups of 1   pi_timestamp only             (record=False)
#
# The dual-route pairing exists because record=True registers a record_event callback
# via assign_cb. TOUCH_INT is configured record=False -- one document per edge is
# CORRECT for it, not a dropped route.


def _hw_doc(t_mono: int, module: str, route: str) -> dict:
    ed = {"id": module}
    if route == "record_event":
        ed.update({"result": None, "func_name": "record_event"})
    else:
        ed.update({"pi_timestamp": "2026-08-24T18:56:05.1+03:00",
                   "pi_timestamp_mono_ns": t_mono, "pi_timestamp_source": "hardware"})
    return {"_source": {"t_mono_ns": t_mono, "t_utc_ns": 1787584410000000000 + t_mono,
                        "ts_source": "hardware",
                        "event": {"event_type": "gpio.X", "event_data": ed}}}


def _run_574_shape(n_pulse=11, n_touch=40):
    docs = []
    t = 6_393_644_457_519
    for i in range(n_pulse):                      # Mid_LED: record=True -> BOTH routes
        et = t + i * 1_000_000_000
        docs.append(_hw_doc(et, "Mid_LED", "record_event"))
        docs.append(_hw_doc(et, "Mid_LED", "pi_timestamp"))
    for j in range(n_touch):                      # TOUCH_INT: record=False -> ONE route
        docs.append(_hw_doc(t + 250_000_000 + j * 200_000_000, "TOUCH_INT", "pi_timestamp"))
    docs.sort(key=lambda d: d["_source"]["t_mono_ns"])
    return docs


def test_c3_ignores_single_route_hardware():
    """TOUCH_INT's 40 unpairable edges must not fail a run in which every dual-route
    edge paired perfectly."""
    c3 = _feed(_run_574_shape())["C3_cross_route_pairing"]
    assert c3["groups_total"] == 11, "only record=True modules belong in the denominator"
    assert c3["groups_matched"] == 11
    assert c3["pairing_rate"] == 1.0
    assert c3["pass"] is True


def test_c3_still_fails_when_a_dual_route_module_loses_a_route():
    """The failure C3 exists for, and the one the fix must not hide: Mid_LED is known
    dual-route, so a Mid_LED edge missing its record_event half is a real defect --
    it must NOT be silently reclassified as single-route."""
    docs = _run_574_shape()
    victim = next(d for d in docs
                  if d["_source"]["event"]["event_data"].get("func_name") == "record_event")
    docs.remove(victim)
    c3 = _feed(docs)["C3_cross_route_pairing"]
    assert c3["groups_total"] == 11
    assert c3["groups_matched"] == 10
    assert c3["pass"] is False


def test_c3_reports_which_modules_were_single_route():
    """Silence about excluded data reads as 'everything paired'. Name what was left out."""
    c3 = _feed(_run_574_shape())["C3_cross_route_pairing"]
    assert "TOUCH_INT" in (c3.get("single_route_modules") or []), c3
    assert "Mid_LED" not in (c3.get("single_route_modules") or [])


# ---------------------------------------------------------------------------
# Run 576 (RecordingBox, 2026-08-26, clock_probe_soak on Mid_LED).
#
# The hardware timeline sat 137437.61 s -- 31.9997 tick wraps -- BEHIND the software
# timeline, so every `pi_timestamp` rendered ~38 h before the run started. C5 exists to
# catch exactly that and reported PASS on 135/135 corrupt documents, because it reads
# `@timestamp`, a field this index does not have (its field is `timestamp`). With no
# window, C5's loop never ran, `implausible` stayed 0, and `pass` was True.
# ---------------------------------------------------------------------------

RUN_576_SW_MONO = 144_511_302_033_164          # CLOCK_MONOTONIC ns, Pi up ~40 h
RUN_576_DOMAIN_GAP_NS = 137_437_614_792_000    # hardware ran 31.9997 wraps behind
RUN_576_HW_MONO = RUN_576_SW_MONO - RUN_576_DOMAIN_GAP_NS


def _dated_doc(t_mono: int, ts_source: str, wall: str, *, pi_timestamp: str | None = None) -> dict:
    """A document in the field shape event_log_v2 actually stores: `timestamp`, not `@timestamp`."""
    ed: dict = {"id": "Mid_LED"}
    if pi_timestamp is not None:
        ed.update({"pi_timestamp": pi_timestamp, "pi_timestamp_mono_ns": t_mono,
                   "pi_timestamp_source": "hardware"})
    else:
        ed.update({"result": None, "func_name": "set"})
    return {"_source": {"t_mono_ns": t_mono, "t_utc_ns": 1787725082981523127,
                        "ts_source": ts_source, "timestamp": wall,
                        "event": {"event_type": "gpio.Digital_Out", "event_data": ed}}}


def _run_576_shape(n: int = 20) -> list[dict]:
    """n software commands stamped 2026-08-26, n hardware edges stamped 2026-08-24."""
    docs = []
    for i in range(n):
        docs.append(_dated_doc(RUN_576_HW_MONO + i * 5_000_000_000, "hardware",
                               "2026-08-24T19:07:25.367799+03:00",
                               pi_timestamp="2026-08-24T19:07:25.367799+03:00"))
        docs.append(_dated_doc(RUN_576_SW_MONO + i * 5_000_000_000, "software",
                               "2026-08-26T09:18:02.932809+03:00"))
    docs.sort(key=lambda d: d["_source"]["t_mono_ns"])
    return docs


def test_c5_reads_the_timestamp_field_this_index_actually_has():
    """Every pi_timestamp is ~38 h outside the run window -- C5 must FAIL, not pass vacuously."""
    c5 = _feed(_run_576_shape())["C5_plausibility"]
    assert c5["window_start"] is not None, "no window means C5 checked nothing"
    assert c5["checked"] == 20
    assert c5["implausible"] == 20
    assert c5["pass"] is False


def test_c5_never_reports_pass_without_a_window():
    """Fail-closed: a run whose documents carry no usable wall clock is N/A, never PASS."""
    docs = [{"_source": {"t_mono_ns": RUN_576_HW_MONO, "ts_source": "hardware",
                         "event": {"event_type": "gpio.Digital_Out",
                                   "event_data": {"id": "Mid_LED",
                                                  "pi_timestamp": "2026-08-24T19:07:25.3+03:00",
                                                  "pi_timestamp_mono_ns": RUN_576_HW_MONO}}}}]
    c5 = _feed(docs)["C5_plausibility"]
    assert c5["pass"] is not True, "an unevaluated check must never read as PASS"


def test_c2_counts_wraps_inside_one_clock_domain():
    """(max-min) across BOTH domains measured the 32-wrap defect and reported it as
    32 healthy wrap crossings -- the bug disguised as the evidence it was meant to be."""
    c2 = _feed(_run_576_shape())["C2_wrap_crossings"]
    assert c2["wrap_crossings"] < 1.0, "20 edges 5 s apart cross no wrap"


def test_single_clock_invariant_catches_disjoint_domains():
    """The hardware and software timelines must overlap. Run 576's were 38 h apart."""
    c8 = _feed(_run_576_shape())["C8_single_clock"]
    assert c8["pass"] is False
    assert c8["domain_gap_s"] > 137_000


def test_single_clock_invariant_passes_when_both_paths_share_a_timeline():
    docs = []
    for i in range(10):
        t = RUN_576_SW_MONO + i * 5_000_000_000
        docs.append(_dated_doc(t, "hardware", "2026-08-26T09:18:02.9+03:00",
                               pi_timestamp="2026-08-26T09:18:02.9+03:00"))
        docs.append(_dated_doc(t + 400_000, "software", "2026-08-26T09:18:02.9+03:00"))
    docs.sort(key=lambda d: d["_source"]["t_mono_ns"])
    c8 = _feed(docs)["C8_single_clock"]
    assert c8["pass"] is True, c8
