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

        # C1 monotonic
        self.prev_t_mono_ns: int | None = None
        self.backward_count = 0
        self.max_backward_step_ns = 0
        self.docs_with_t_mono_ns = 0

        # C2 wrap crossings
        self.min_t_mono_ns: int | None = None
        self.max_t_mono_ns: int | None = None

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

        t_mono = source.get("t_mono_ns")
        ts_source = source.get("ts_source")

        if isinstance(t_mono, (int, float)):
            t_mono = int(t_mono)
            self._update_monotonic_and_wrap(t_mono)
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
                    self._record_drop_gap(t_mono)
                self._group_count += 1
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
        at_ts = self._update_plausibility_window(source)
        self._buffer_step_window(source, t_mono, at_ts)

    def _update_monotonic_and_wrap(self, t_mono: int) -> None:
        self.docs_with_t_mono_ns += 1
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

    def _update_plausibility_window(self, source: dict) -> datetime | None:
        # Window ground truth is @timestamp (ES's own ingest-time clock), independent of the
        # pi_timestamp field under test -- this check never uses the value it validates as its
        # own ground truth.
        at_ts_raw = source.get("@timestamp")
        at_ts = parse_pi_timestamp(at_ts_raw) if at_ts_raw is not None else None
        if at_ts is not None:
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
        self._group_has_record_event = False

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
        return checks

    def _check_c1(self) -> dict[str, Any]:
        return {
            "pass": self.backward_count == 0,
            "backward_count": self.backward_count,
            "max_backward_step_ns": self.max_backward_step_ns,
            "docs_with_t_mono_ns": self.docs_with_t_mono_ns,
        }

    def _check_c2(self) -> dict[str, Any]:
        wrap_crossings = 0.0
        if self.min_t_mono_ns is not None and self.max_t_mono_ns is not None:
            wrap_crossings = (self.max_t_mono_ns - self.min_t_mono_ns) / NS_PER_TICK_WRAP
        return {
            "pass": None,  # informational unless the caller enforces --min-wrap-crossings
            "wrap_crossings": wrap_crossings,
            "min_t_mono_ns": self.min_t_mono_ns,
            "max_t_mono_ns": self.max_t_mono_ns,
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
        return {
            "pass": implausible == 0 and self.pi_timestamp_checked > 0,
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
