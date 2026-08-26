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


# The trigger route's payload timestamp is the QUEUE-RECEIPT read, not the edge, so the
# two documents for one edge no longer share a t_mono_ns and no longer sort adjacent.
DEFAULT_QUEUE_LATENCY_NS = 380_000


def _doc(t_mono: int, ts_source: str, *, route: str = "record_event",
         level: int = 1, module: str = "Mid_LED",
         queue_latency_ns: int = DEFAULT_QUEUE_LATENCY_NS) -> dict:
    """One event_log_v2 document, in the field shape the rig writes.

    `t_mono` is the EDGE for every caller. For the trigger route the emitted payload
    timestamp is `t_mono + queue_latency_ns` and its ts_source is forced to `software`,
    because that read is the dispatcher's own -- which is the whole point of that route
    carrying two instants.
    """
    event_data: dict = {"id": module}
    payload_t_mono = t_mono
    payload_source = ts_source
    if route == "record_event":
        event_data.update({"result": None, "func_name": "record_event"})
    else:
        event_data.update({
            "pi_timestamp": "2026-08-24T18:13:30.976265+03:00",
            "pi_timestamp_mono_ns": t_mono,
            "pi_timestamp_source": ts_source,
        })
        payload_t_mono = t_mono + queue_latency_ns
        payload_source = "software"
    return {
        "_source": {
            "t_mono_ns": payload_t_mono,
            "t_utc_ns": 1787584410976265902 + payload_t_mono,
            "ts_source": payload_source,
            "event": {"event_type": "gpio.Digital_Out", "event_data": event_data,
                      "level": level},
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
    docs.sort(key=lambda d: d["_source"]["t_mono_ns"])   # iter_run_documents' own sort
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


def test_c4_counts_the_trigger_routes_payload_read_as_the_software_read_it_is():
    """62 record_event documents are hardware-stamped -- their payload timestamp IS the
    edge. The 62 trigger-route documents are software-stamped, because their payload
    timestamp is the queue-receipt read; the edge they also carry keeps its own
    provenance in `pi_timestamp_source`. Before 2026-08-26 both were hardware (124/252),
    which is what claiming one instant twice looks like in a provenance count."""
    c4 = _feed(_run_573_shape())["C4_provenance"]
    assert c4["hardware_docs"] == 62
    assert c4["software_docs"] == 252 + 62
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
    # BOTH documents for the victim edge have to go. They no longer share a t_mono_ns --
    # only route a's payload timestamp is the edge -- so the edge each document belongs
    # to is the thing to select on, exactly as the accumulator now groups on it.
    def edge_of(doc):
        data = doc["_source"]["event"]["event_data"]
        if "pi_timestamp_mono_ns" in data:
            return data["pi_timestamp_mono_ns"]
        return doc["_source"]["t_mono_ns"] if doc["_source"]["ts_source"] == "hardware" else None

    edge_ts = sorted({e for e in (edge_of(d) for d in docs) if e is not None})
    victims = set(edge_ts[len(edge_ts) // 2:][:2])
    thinned = [d for d in docs if edge_of(d) not in victims]
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
    docs.sort(key=lambda d: d["_source"]["t_mono_ns"])   # iter_run_documents' own sort
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
    docs.sort(key=lambda d: d["_source"]["t_mono_ns"])   # iter_run_documents' own sort
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


# ---------------------------------------------------------------------------
# C9 -- run 576's OTHER defect, and the one no check here was looking for.
#
# Every Mid_LED edge landed as two documents sharing one t_mono_ns, so C3 reported a
# perfect pairing_rate of 1.0. The two documents carried OPPOSITE levels, on 253 of 253
# edges: `@log_action` read `hardware_state` before anything had written this edge's
# value to it, so on an alternating pulse it reported the inverse every time. Agreeing
# about WHEN an edge happened and disagreeing about WHAT it was is not a paired edge.
# ---------------------------------------------------------------------------


def test_c9_passes_when_both_routes_report_the_same_level():
    result = _feed(_run_573_shape())
    check = result["C9_route_level_agreement"]
    assert check["pass"] is True
    assert check["groups_checked"] == 62
    assert check["disagreements"] == 0


def test_c9_catches_run_576s_inverted_log_action_route():
    docs = []
    t = 7_073_688_308_588
    for i in range(10):
        edge_t = t + i * 5_000_000_000
        level = 1 - (i % 2)
        docs.append(_doc(edge_t, "hardware", route="record_event", level=1 - level))
        docs.append(_doc(edge_t, "hardware", route="pi_timestamp", level=level))
    check = _feed(docs)["C9_route_level_agreement"]
    assert check["pass"] is False
    assert check["disagreements"] == 10
    assert check["examples"], "a disagreement must name the edge it was found on"


def test_c9_is_not_reported_as_pass_when_there_was_nothing_to_check():
    """An unevaluated check reading PASS is how the 38 h error survived a green run."""
    docs = [_doc(1_000_000_000 + i, "software") for i in range(5)]
    check = _feed(docs)["C9_route_level_agreement"]
    assert check["pass"] is None
    assert check["groups_checked"] == 0


# ---------------------------------------------------------------------------
# C10 -- the trigger route's two instants, 2026-08-26.
#
# `event_data.pi_timestamp_mono_ns` is when the level changed; the payload's own
# `t_mono_ns` is when the message came off the trigger queue. Their difference is the
# queue latency, and it is the reason that route carries both. It cannot be negative:
# an edge cannot be dequeued before it happened.
#
# Note what this also proves about C3/C9: those two documents no longer share a
# t_mono_ns, so grouping on the sort key alone would pair nothing at all.
# ---------------------------------------------------------------------------


def test_c10_measures_the_trigger_queue_latency():
    check = _feed(_run_573_shape())["C10_trigger_queue_latency"]
    assert check["pass"] is True
    assert check["measured"] == 62
    assert check["negative"] == 0
    assert check["min_ns"] == check["max_ns"] == DEFAULT_QUEUE_LATENCY_NS


def test_c10_counts_a_small_negative_latency_without_failing_on_it():
    """The edge is a MAPPED tick and the receipt is a RAW clock read, so the fit's bounded
    prediction error can legitimately put the edge a few ms ahead of the read taken just
    after it. Run 578 measured exactly this -- 48 of its first 108 edges read negative --
    and it was the bootstrap slope, not a defect. Counted and reported, never gated."""
    docs = _run_573_shape(n_edges=4, n_software=0)
    docs += [_doc(3_839_296_775_883 + 99_000_000_000, "hardware",
                  route="pi_timestamp", queue_latency_ns=-5_000_000)]
    check = _feed(docs)["C10_trigger_queue_latency"]
    assert check["pass"] is True
    assert check["negative"] == 1
    assert check["over_1s_bound"] == 0


def test_c10_fails_on_a_gap_no_mapping_error_could_explain():
    """The shape it does still catch: a mapping on the wrong timeline. Run 576 had the two
    paths 137437 s apart. The 1 s bound is derived -- DEFAULT_MAX_PPM (200) x
    DEFAULT_HEARTBEAT_S (600 s) = 120 ms of worst legitimate drift, cleared ~8x."""
    docs = _run_573_shape(n_edges=4, n_software=0)
    docs += [_doc(3_839_296_775_883 + 99_000_000_000, "hardware",
                  route="pi_timestamp", queue_latency_ns=137_437_000_000_000)]
    check = _feed(docs)["C10_trigger_queue_latency"]
    assert check["pass"] is False
    assert check["over_1s_bound"] == 1
    assert check["examples"]


def test_c10_measures_the_mappings_residual_rate_error_as_drift_ppm():
    """Run 578's finding, and the reason drift_ppm exists: latency slid from +2.4 ms at
    t=0 to -2.5 ms at t=590 s, a linear -8.5 ppm, which is the BOOTSTRAP mapping's slope of
    exactly 1000.0 ns/us being wrong before the first re-fit at heartbeat_s = 600 s. A
    re-fitted mapping sits near zero."""
    docs, t = [], 3_839_296_775_883
    for i in range(60):                       # 1 Hz edges; latency slides 10 us per second
        edge = t + i * 1_000_000_000
        docs.append(_doc(edge, "hardware", route="record_event"))
        docs.append(_doc(edge, "hardware", route="pi_timestamp",
                         queue_latency_ns=2_000_000 - i * 10_000))
    docs.sort(key=lambda d: d["_source"]["t_mono_ns"])
    check = _feed(docs)["C10_trigger_queue_latency"]
    assert check["pass"] is True
    # 10_000 ns of latency per 1 s of edge time == 1e-5 s/s == 10 ppm.
    assert abs(check["drift_ppm"] - (-10.0)) < 0.01


def test_c10_reports_no_drift_for_a_steady_latency():
    check = _feed(_run_573_shape())["C10_trigger_queue_latency"]
    assert abs(check["drift_ppm"]) < 1e-6


def test_c10_names_a_run_whose_two_instants_have_collapsed_into_one():
    """Run 576's shape and the signature of a Pi still on pre-2026-08-26 code: both
    timestamp fields hold the edge, so every latency reads exactly 0. Not a clock defect
    and not a FAIL -- a deploy signal, and it must be visible rather than inferred."""
    docs = _run_573_shape(n_edges=8, n_software=0)
    docs = [d for d in docs
            if "pi_timestamp_mono_ns" not in d["_source"]["event"]["event_data"]] + [
        _doc(3_839_296_775_883 + i * 1_000_000_000, "hardware",
             route="pi_timestamp", queue_latency_ns=0) for i in range(8)]
    check = _feed(docs)["C10_trigger_queue_latency"]
    assert check["pass"] is True
    assert check["all_zero_the_two_instants_have_collapsed"] is True


def test_c10_does_not_cry_collapse_on_a_healthy_run():
    check = _feed(_run_573_shape())["C10_trigger_queue_latency"]
    assert check["all_zero_the_two_instants_have_collapsed"] is False


def test_c10_is_not_reported_as_pass_when_there_was_nothing_to_measure():
    docs = [_doc(1_000_000_000 + i, "software") for i in range(5)]
    check = _feed(docs)["C10_trigger_queue_latency"]
    assert check["pass"] is None
    assert check["measured"] == 0


def test_c3_still_pairs_when_the_two_routes_do_not_share_a_t_mono_ns():
    """The regression the two-instant change would otherwise cause: grouping on the ES
    sort key pairs nothing, because only route a's t_mono_ns is the edge."""
    result = _feed(_run_573_shape())
    assert result["C3_cross_route_pairing"]["pass"] is True
    assert result["C3_cross_route_pairing"]["groups_matched"] == 62
    assert result["C9_route_level_agreement"]["groups_checked"] == 62


def test_c9_still_catches_an_inversion_across_the_latency_gap():
    docs = []
    t = 7_073_688_308_588
    for i in range(10):
        edge_t = t + i * 5_000_000_000
        level = 1 - (i % 2)
        docs.append(_doc(edge_t, "hardware", route="record_event", level=1 - level))
        docs.append(_doc(edge_t, "hardware", route="pi_timestamp", level=level))
    docs.sort(key=lambda d: d["_source"]["t_mono_ns"])
    check = _feed(docs)["C9_route_level_agreement"]
    assert check["pass"] is False
    assert check["disagreements"] == 10
