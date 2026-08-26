"""RunAccumulator -- the incremental, bounded-memory pass over one clock_probe run's documents.

Split out of es_clock_check.py to keep each file under this repo's 300-line soft limit. See that
module's docstring for the C1-C7 check definitions this class computes.
"""
from __future__ import annotations

from datetime import datetime, timedelta
from typing import Any

from clock_check_es import NS_PER_TICK_WRAP, PLAUSIBILITY_WINDOW_S, get_nested, has_suffix_field, parse_pi_timestamp


class RunAccumulator:
    """One forward pass, O(1) (or small-bounded) memory per check -- never holds the whole run."""

    def __init__(
        self,
        pulse_period_s: float | None,
        step_time_utc: datetime | None,
        step_window_s: float,
        max_examples: int,
    ):
        self.total_docs = 0

        # C1 monotonic. NOTE the circularity: iter_run_documents sorts by t_mono_ns, so
        # `backward_count` over that stream is 0 by construction and cannot fail. The real
        # signal is whether t_mono order still agrees with INGEST order (_seq_no): a wrap
        # mishandled the way the deployed patched client did it hands out t_mono values that
        # collide with ones issued ~4295 s earlier, so later-ingested documents sort earlier.
        # Reported, not asserted -- the dispatcher's async send queue can reorder slightly on
        # its own, so an inversion is a lead to chase, not proof of a defect.
        self.prev_t_mono_ns: int | None = None
        self.prev_seq_no: int | None = None
        self.seq_no_inversions = 0
        self.backward_count = 0
        self.max_backward_step_ns = 0
        self.docs_with_t_mono_ns = 0

        # C2 wrap crossings / C8 single-clock. Tracked PER ts_source domain: a run whose
        # hardware and software paths sit on different timelines makes a whole-run (max-min)
        # span measure the distance BETWEEN the clocks, not elapsed time on either. Run 576
        # reported 32.14 "wrap crossings" for an 11-minute run -- that number was the defect
        # (31.9997 wraps of hardware/software skew), read as evidence of a healthy soak.
        self.min_t_mono_ns: int | None = None
        self.max_t_mono_ns: int | None = None
        self._domain_min: dict[str, int] = {}
        self._domain_max: dict[str, int] = {}

        # C3 cross-route pairing -- docs sorted by t_mono_ns, so same-value docs are contiguous;
        # finalize the previous group the instant the value changes. O(1) memory.
        self._group_key: int | None = None
        self._group_count = 0
        self._group_module: str | None = None
        self._group_has_record_event = False
        self.pair_groups_total = 0
        self.pair_groups_matched = 0  # groups where exactly 2 docs share the t_mono_ns
        # C3 is a PER-MODULE claim. The two routes exist because record=True registers a
        # record_event callback alongside the main one (Digital_Out.assign_cb). A module
        # configured record=False -- TOUCH_INT, the licker IRQ -- emits ONE document per
        # edge, correctly, and must not be counted as 40 dropped routes. Run 574: Mid_LED
        # 11 groups of 2, TOUCH_INT 40 groups of 1, reported as 11/51 FAIL on clean data.
        # Membership is decided by evidence (did this module ever emit a record_event
        # document?), never by assuming, so a dual-route module that LOSES a route still
        # fails instead of being quietly reclassified as single-route.
        self._module_group_sizes: dict[str, list[int]] = {}
        self._record_event_modules: set[str] = set()

        # C9 route-level agreement. C3 proves two documents describe ONE edge; nothing
        # proved they described it the SAME WAY. Run 576's Mid_LED paired perfectly (C3
        # 1.0) while the two routes reported OPPOSITE levels on 253 of 253 edges --
        # @log_action read hardware_state before this edge's value had been written to it,
        # so on an alternating pulse it reported the inverse every time.
        self._group_levels: list[Any] = []
        self.level_groups_checked = 0
        self.level_disagreements = 0
        self.level_examples: list[dict] = []

        # C4 provenance
        self.hardware_docs = 0
        self.software_docs = 0
        self.other_ts_source_docs = 0
        self.hardware_without_mono_field = 0

        # C5 plausibility
        self.pi_timestamp_checked = 0
        self._at_ts_min: datetime | None = None
        self._at_ts_max: datetime | None = None
        self._pi_ts_buffer: list[tuple[Any, Any]] = []  # (parsed pi_timestamp, raw value)

        # C6 clock step (only populated when step_time_utc given -- bounded window buffer)
        self.step_time_utc = step_time_utc
        self.step_window = timedelta(seconds=step_window_s) if step_time_utc else None
        self._step_buffer: list[dict] = []  # only docs within the window -- small by construction

        # C7 drops against the commanded pulse period
        self.pulse_period_ns = int(pulse_period_s * 1e9) if pulse_period_s else None
        self._prev_edge_group_t_mono_ns: int | None = None
        self.gap_count_over_2x = 0
        self.gap_examples: list[dict] = []

        self.max_examples = max_examples

    # -- per-document update -------------------------------------------------

    def add(self, doc: dict) -> None:
        source = doc.get("_source", {})
        self.total_docs += 1

        # ES returns the sort tuple [t_mono_ns, _seq_no]; the tiebreaker is ingest order.
        sort_key = doc.get("sort")
        if isinstance(sort_key, list) and len(sort_key) > 1 and isinstance(sort_key[1], int):
            seq_no = sort_key[1]
            if self.prev_seq_no is not None and seq_no < self.prev_seq_no:
                self.seq_no_inversions += 1
            self.prev_seq_no = seq_no

        t_mono = source.get("t_mono_ns")
        ts_source = source.get("ts_source")

        if isinstance(t_mono, (int, float)):
            t_mono = int(t_mono)
            self._update_monotonic_and_wrap(t_mono, ts_source)
            # C3/C7 group HARDWARE documents only. Both checks are claims about a commanded
            # hardware edge: C3 that one edge dispatches down two routes sharing a t_mono_ns,
            # C7 that no edge went missing. A software document is single-route by construction
            # and is not a pulse edge, so counting it here made C3's denominator the whole run.
            # Run 573 (the first real rig run) is the regression: 62 hardware edges, every one
            # perfectly paired, reported as pairing_rate 0.197 FAIL because the 252 software
            # documents each formed an unpairable singleton group.
            # C1 above deliberately still spans EVERY document -- a backward jump in a software
            # document is just as much a clock defect.
            if ts_source == "hardware":
                event_data = (source.get("event") or {}).get("event_data") or {}
                module = event_data.get("id")
                if self._group_key != t_mono:
                    self._finalize_pair_group()
                    self._group_key = t_mono
                    self._group_count = 0
                    self._group_module = module
                    self._group_levels = []
                    self._record_drop_gap(t_mono)
                self._group_count += 1
                self._group_levels.append((source.get("event") or {}).get("level"))
                if event_data.get("func_name") == "record_event":
                    self._group_has_record_event = True
                    if module is not None:
                        self._record_event_modules.add(module)
        elif ts_source == "hardware" and self._group_key is not None:
            # A hardware doc with no t_mono_ns closes out whatever group was open
            # (sort puts these last).
            self._finalize_pair_group()
            self._group_key = None

        self._update_provenance(source, ts_source)
        at_ts = self._update_plausibility_window(source, ts_source)
        self._buffer_step_window(source, t_mono, at_ts)

    def _update_monotonic_and_wrap(self, t_mono: int, ts_source: Any = None) -> None:
        self.docs_with_t_mono_ns += 1
        if isinstance(ts_source, str):
            lo = self._domain_min.get(ts_source)
            hi = self._domain_max.get(ts_source)
            if lo is None or t_mono < lo:
                self._domain_min[ts_source] = t_mono
            if hi is None or t_mono > hi:
                self._domain_max[ts_source] = t_mono
        if self.min_t_mono_ns is None or t_mono < self.min_t_mono_ns:
            self.min_t_mono_ns = t_mono
        if self.max_t_mono_ns is None or t_mono > self.max_t_mono_ns:
            self.max_t_mono_ns = t_mono
        if self.prev_t_mono_ns is not None and t_mono < self.prev_t_mono_ns:
            self.backward_count += 1
            step = self.prev_t_mono_ns - t_mono
            if step > self.max_backward_step_ns:
                self.max_backward_step_ns = step
        self.prev_t_mono_ns = t_mono

    def _update_provenance(self, source: dict, ts_source: Any) -> None:
        has_mono_field = has_suffix_field(source, "_mono_ns")
        if ts_source == "hardware":
            self.hardware_docs += 1
            if not has_mono_field:
                self.hardware_without_mono_field += 1
        elif ts_source == "software":
            self.software_docs += 1
        else:
            self.other_ts_source_docs += 1

    def _update_plausibility_window(self, source: dict, ts_source: Any = None) -> datetime | None:
        # Window ground truth is @timestamp (ES's own ingest-time clock), independent of the
        # pi_timestamp field under test -- this check never uses the value it validates as its
        # own ground truth.
        # `timestamp` is what event_log_v2 stores; `@timestamp` is the ECS spelling and is
        # absent from this index entirely. Reading only the missing name left the window None,
        # so C5's loop never ran and it reported PASS over 135/135 corrupt documents (run 576).
        at_ts_raw = source.get("timestamp")
        if at_ts_raw is None:
            at_ts_raw = source.get("@timestamp")
        at_ts = parse_pi_timestamp(at_ts_raw) if at_ts_raw is not None else None
        # Bounds come from SOFTWARE documents only. A hardware document's `timestamp` is the
        # rendered pi_timestamp -- the value under test -- so folding it into the window lets a
        # corrupt clock vouch for itself: run 576's window would stretch back over the same
        # 38 h the error moved the events, and every one would land "inside" it.
        if at_ts is not None and ts_source != "hardware":
            if self._at_ts_min is None or at_ts < self._at_ts_min:
                self._at_ts_min = at_ts
            if self._at_ts_max is None or at_ts > self._at_ts_max:
                self._at_ts_max = at_ts

        pi_ts_raw = get_nested(source, "event.event_data.pi_timestamp")
        if pi_ts_raw is not None:
            self.pi_timestamp_checked += 1
            # Buffered, not evaluated inline: the window bound (@timestamp min/max) is only
            # fully known after the full pass. Hard-capped regardless of run size.
            if len(self._pi_ts_buffer) < 200_000:
                self._pi_ts_buffer.append((parse_pi_timestamp(pi_ts_raw), pi_ts_raw))
        return at_ts

    def _buffer_step_window(self, source: dict, t_mono: Any, at_ts: datetime | None) -> None:
        if self.step_time_utc is None or at_ts is None:
            return
        if abs(at_ts - self.step_time_utc) <= self.step_window:
            self._step_buffer.append({
                "t_mono_ns": t_mono if isinstance(t_mono, int) else None,
                "t_utc_ns": source.get("t_utc_ns"),
                "@timestamp": at_ts.isoformat(),
            })

    def _record_drop_gap(self, t_mono: int) -> None:
        if not self.pulse_period_ns:
            return
        if self._prev_edge_group_t_mono_ns is not None:
            gap = t_mono - self._prev_edge_group_t_mono_ns
            if gap > 2 * self.pulse_period_ns:
                self.gap_count_over_2x += 1
                if len(self.gap_examples) < self.max_examples:
                    self.gap_examples.append({
                        "after_t_mono_ns": self._prev_edge_group_t_mono_ns,
                        "before_t_mono_ns": t_mono,
                        "gap_ns": gap,
                        "gap_s": gap / 1e9,
                    })
        self._prev_edge_group_t_mono_ns = t_mono

    def _finalize_pair_group(self) -> None:
        if self._group_key is None:
            return
        self._module_group_sizes.setdefault(self._group_module, []).append(self._group_count)
        self._judge_group_levels()
        self._group_has_record_event = False

    def _judge_group_levels(self) -> None:
        """C9, closed out with the group. Only a group that actually has two or more
        documents can disagree; a single-route module has nothing to compare against."""
        levels = [lvl for lvl in self._group_levels if lvl is not None]
        if len(levels) < 2:
            return
        self.level_groups_checked += 1
        if len(set(levels)) == 1:
            return
        self.level_disagreements += 1
        if len(self.level_examples) < self.max_examples:
            self.level_examples.append({
                "t_mono_ns": self._group_key,
                "module": self._group_module,
                "levels": levels,
            })

    # -- finalize / report -----------------------------------------------------

    def finalize(self) -> dict[str, Any]:
        self._finalize_pair_group()
        checks: dict[str, Any] = {}
        checks["C1_monotonic"] = self._check_c1()
        checks["C2_wrap_crossings"] = self._check_c2()
        checks["C3_cross_route_pairing"] = self._check_c3()
        checks["C4_provenance"] = self._check_c4()
        checks["C5_plausibility"] = self._check_c5()
        checks["C6_clock_step"] = self._check_c6()
        checks["C7_drops"] = self._check_c7()
        checks["C8_single_clock"] = self._check_c8()
        checks["C9_route_level_agreement"] = self._check_c9()
        return checks

    def _check_c9(self) -> dict[str, Any]:
        """Both documents for one edge must say the same thing about it.

        Fail-closed like C5: with no multi-document group there was nothing to compare,
        and an unevaluated check must never read as PASS.
        """
        return {
            "pass": (self.level_disagreements == 0) if self.level_groups_checked else None,
            "groups_checked": self.level_groups_checked,
            "disagreements": self.level_disagreements,
            "examples": self.level_examples,
        }

    def _check_c1(self) -> dict[str, Any]:
        return {
            # Informational, never PASS: see __init__: the query sorts by the very field this
            # counts, so "0 backward steps" is a property of the sort, not of the clock.
            "pass": None,
            "note": "vacuous under the t_mono_ns sort; C7/C8 carry the backward-jump signal",
            "backward_count": self.backward_count,
            "max_backward_step_ns": self.max_backward_step_ns,
            "docs_with_t_mono_ns": self.docs_with_t_mono_ns,
            "seq_no_inversions": self.seq_no_inversions,
        }

    def _check_c2(self) -> dict[str, Any]:
        # Wraps are a property of ONE timeline. Measured on the hardware domain, which is the
        # one carrying the extended tick; falls back to the widest single domain present.
        spans = {d: self._domain_max[d] - self._domain_min[d] for d in self._domain_min}
        domain = "hardware" if "hardware" in spans else (
            max(spans, key=lambda d: spans[d]) if spans else None
        )
        wrap_crossings = spans[domain] / NS_PER_TICK_WRAP if domain else 0.0
        return {
            "pass": None,  # informational unless the caller enforces --min-wrap-crossings
            "wrap_crossings": wrap_crossings,
            "measured_on_domain": domain,
            "min_t_mono_ns": self._domain_min.get(domain) if domain else None,
            "max_t_mono_ns": self._domain_max.get(domain) if domain else None,
        }

    def _check_c8(self) -> dict[str, Any]:
        """The single-clock invariant: both event paths must sit on ONE timeline.

        clock.py's whole design is that the GPIO callback path and the dispatcher path read
        the same clock. When they do, their t_mono_ns ranges overlap and the gap is 0. Run 576
        had them 137437.6 s apart -- 31.9997 tick wraps, the extender seeding its wrap count at
        attach instead of carrying the wraps already elapsed since boot -- and every other
        check still passed.
        """
        hw_lo, hw_hi = self._domain_min.get("hardware"), self._domain_max.get("hardware")
        sw_lo, sw_hi = self._domain_min.get("software"), self._domain_max.get("software")
        if hw_lo is None or sw_lo is None:
            return {"pass": None, "skipped": "run has only one ts_source domain",
                    "domain_gap_s": None}
        # 0 when the ranges overlap; otherwise the distance between them.
        gap_ns = max(0, max(hw_lo, sw_lo) - min(hw_hi, sw_hi))
        return {
            "pass": gap_ns < NS_PER_TICK_WRAP // 2,
            "domain_gap_s": gap_ns / 1e9,
            "domain_gap_wraps": gap_ns / NS_PER_TICK_WRAP,
            "hardware_range_ns": [hw_lo, hw_hi],
            "software_range_ns": [sw_lo, sw_hi],
        }

    def _check_c3(self) -> dict[str, Any]:
        """Pairing, counted only over modules PROVEN dual-route by their own documents."""
        total = matched = 0
        single_route = []
        for module, sizes in self._module_group_sizes.items():
            if module in self._record_event_modules:
                total += len(sizes)
                matched += sum(1 for n in sizes if n == 2)
            elif module is not None:
                single_route.append(module)
        self.pair_groups_total = total
        self.pair_groups_matched = matched
        pairing_rate = matched / total if total else None
        return {
            "pass": pairing_rate == 1.0 if pairing_rate is not None else None,
            "pairing_rate": pairing_rate,
            "groups_total": total,
            "groups_matched": matched,
            # Named, never silent: excluding data without saying so reads as "all paired".
            "single_route_modules": sorted(single_route),
        }

    def _check_c4(self) -> dict[str, Any]:
        return {
            "pass": self.hardware_without_mono_field == 0,
            "hardware_docs": self.hardware_docs,
            "software_docs": self.software_docs,
            "other_ts_source_docs": self.other_ts_source_docs,
            "hardware_without_mono_field": self.hardware_without_mono_field,
        }

    def _check_c5(self) -> dict[str, Any]:
        implausible = 0
        examples: list[dict] = []
        lo = hi = None
        if self._at_ts_min is not None and self._at_ts_max is not None:
            lo = self._at_ts_min - timedelta(seconds=PLAUSIBILITY_WINDOW_S)
            hi = self._at_ts_max + timedelta(seconds=PLAUSIBILITY_WINDOW_S)
            for parsed, raw in self._pi_ts_buffer:
                if parsed is None or not (lo <= parsed <= hi):
                    implausible += 1
                    if len(examples) < self.max_examples:
                        examples.append({"raw_pi_timestamp": raw, "parsed": parsed.isoformat() if parsed else None})
        # Fail-closed: with no window nothing was compared, and an unevaluated check must
        # never read as PASS -- that is precisely how the 38 h error survived a green run.
        verdict = None if lo is None else (implausible == 0 and self.pi_timestamp_checked > 0)
        return {
            "pass": verdict,
            "checked": self.pi_timestamp_checked,
            "implausible": implausible,
            "window_start": lo.isoformat() if lo is not None else None,
            "window_end": hi.isoformat() if hi is not None else None,
            "examples": examples,
        }

    def _check_c6(self) -> dict[str, Any]:
        if self.step_time_utc is None:
            return {"pass": None, "skipped": "no --step-time-utc given"}

        buf = sorted(
            (d for d in self._step_buffer if d["t_mono_ns"] is not None),
            key=lambda d: d["t_mono_ns"],
        )
        if len(buf) < 2:
            return {"pass": None, "skipped": "fewer than 2 documents in the step window"}

        step_iso = self.step_time_utc.isoformat()
        before = [d for d in buf if d["@timestamp"] < step_iso]
        after = [d for d in buf if d["@timestamp"] >= step_iso]
        if not before or not after:
            return {"pass": None, "skipped": "no documents on one side of the step boundary"}

        utc_ns_before = before[-1].get("t_utc_ns")
        utc_ns_after = after[0].get("t_utc_ns")
        utc_shift_s = (
            (utc_ns_after - utc_ns_before) / 1e9
            if isinstance(utc_ns_before, (int, float)) and isinstance(utc_ns_after, (int, float))
            else None
        )

        # Largest t_mono_ns interval anywhere in the window vs. the boundary interval itself.
        intervals = [buf[i + 1]["t_mono_ns"] - buf[i]["t_mono_ns"] for i in range(len(buf) - 1)]
        boundary_interval = after[0]["t_mono_ns"] - before[-1]["t_mono_ns"]
        max_interval = max(intervals) if intervals else 0

        return {
            "pass": max_interval == boundary_interval if intervals else None,
            "observed_utc_shift_s": utc_shift_s,
            "boundary_t_mono_ns_interval": boundary_interval,
            "max_t_mono_ns_interval_in_window": max_interval,
            "docs_in_window": len(buf),
        }

    def _check_c7(self) -> dict[str, Any]:
        return {
            "pass": self.gap_count_over_2x == 0 if self.pulse_period_ns else None,
            "skipped": None if self.pulse_period_ns else "no --pulse-period-s given",
            "pulse_period_s": (self.pulse_period_ns / 1e9) if self.pulse_period_ns else None,
            "gaps_over_2x_period": self.gap_count_over_2x,
            "examples": self.gap_examples,
        }
