#!/usr/bin/env python3
"""Read-only Elasticsearch verifier for a clock_probe run (Phase 31 Plan 12, Task 3).

    python3 tools/es_clock_check.py --run-id N --session S [--host 132.77.73.217:9200]

Isolates the run with `subject: bp_s<session>_r<run_id>` (trap 6 -- the index holds ~2.9 M
documents from other work), sorts by `t_mono_ns`, and reports each check (C1-C10) as a named
PASS/FAIL/N-A with the numbers that produced it -- a verifier that prints only PASS is not
evidence:

  C1 monotonic          -- INFORMATIONAL, never PASS. The query sorts by t_mono_ns, so "zero
                             backward steps" is a property of that sort, not of the clock, and
                             this check cannot fail. It reports the counts plus `seq_no_
                             inversions` (t_mono order vs ingest order), which is the honest
                             lead; C7 and C8 carry the real backward-jump signal.
  C2 wrap crossings      -- (max-min) t_mono_ns WITHIN ONE ts_source domain (hardware when
                             present) / one 32-bit tick wrap. Spanning both domains measured
                             the distance BETWEEN two clocks, not elapsed time: run 576's
                             11-minute soak reported 32.14 "wrap crossings" that were really
                             31.9997 wraps of hardware/software skew -- the defect, read as
                             evidence of a healthy soak. `--min-wrap-crossings 3` enforces a
                             floor; otherwise informational.
  C3 cross-route pairing -- every Mid_LED edge should land as exactly two documents (the
                             logging_utils.py:97 and task.py:283 routes). Grouped on the
                             EDGE, which the two routes put in DIFFERENT fields: route a
                             dispatches from inside the notify thread so its payload
                             `t_mono_ns` is the edge, while route b runs on the trigger
                             worker and puts the edge in
                             `event.event_data.pi_timestamp_mono_ns`, keeping its payload
                             timestamp for the queue receipt (see C10). Grouping on the
                             ES sort key alone would therefore pair nothing.
  C4 provenance           -- hardware docs carry ts_source=hardware AND a *_mono_ns field;
                             software/tracker docs carry ts_source=software.
  C5 plausibility         -- event.event_data.pi_timestamp parses inside the run's wall-clock
                             window +/- 60 s (catches both known corruptions: monotonic-as-epoch
                             and microsecond-as-nanosecond). The window is built from `timestamp`
                             (this index's field; `@timestamp` is the ECS spelling and is absent
                             here) and from SOFTWARE documents only -- a hardware document's
                             `timestamp` IS the rendered pi_timestamp, so including it lets a
                             corrupt clock vouch for itself. Reading the missing field name left
                             the window empty, the comparison loop never ran, and run 576
                             reported PASS over 135/135 documents stamped 38 h in the past.
                             Fails closed: no window means N/A, never PASS.
  C6 clock step           -- around a forced wall-clock step (--step-time-utc), t_utc_ns moves by
                             the step and no t_mono_ns interval moves.
  C7 drops                -- gaps > 2x the commanded --pulse-period-s in the edge-group stream.
  C8 single clock         -- the hardware and software t_mono_ns ranges must overlap. clock.py's
                             design is that the GPIO callback path and the dispatcher path read
                             ONE clock; run 576 had them 137437.6 s (31.9997 tick wraps) apart,
                             the tick extender seeding its wrap count at attach rather than
                             carrying the wraps already elapsed since boot, and every other
                             check still passed.
  C9 route level agreement -- the two documents describing ONE edge must agree about WHAT it
                             was, not only about when. C3 proves they share a t_mono_ns; run
                             576's Mid_LED paired perfectly (C3 1.0) while the two routes
                             reported OPPOSITE levels on 253 of 253 edges, because @log_action
                             read `hardware_state` before this edge's value had been written to
                             it and an alternating pulse makes a stale read the exact inverse.
                             Fails closed: no multi-document group means N/A, never PASS.
  C10 trigger queue latency -- `t_mono_ns - event.event_data.pi_timestamp_mono_ns` on the
                             trigger route: the time between the level changing and
                             execute_trigger dequeuing the message. That route carries two
                             instants precisely so this is measurable. It cannot be
                             negative -- an edge cannot be processed before it happened --
                             and a negative reading means the two fields are no longer on
                             one clock. Run 576 could not be measured at all: both fields
                             held the edge, so every latency read exactly 0. The
                             distribution is REPORTED, not gated; a ceiling would have to
                             be derived from these numbers rather than guessed. Fails
                             closed: nothing measured means N/A, never PASS.

READ-ONLY, always. This tool (and clock_check_es.py / clock_check_accumulator.py, which it
imports) runs against the index holding every experiment this lab has recorded (and, if pointed
at a local dev cluster, one other people are actively querying right now). The ONLY Elasticsearch
call anywhere in this module tree is `ReadOnlyESClient.search`, and the ONLY endpoint it ever
calls is `_search` -- no write, mutate, delete-by-query, or bulk call exists anywhere in this
tree.

Bounded resource use, deliberately, because a soak run crossing 3+ tick wraps is a very large
number of documents: `iter_run_documents` pages with `search_after` (fixed `--page-size`, never
materializing the whole run); `RunAccumulator` keeps only O(1) running state plus small
`--max-examples`-capped example lists; C6 buffers only documents within `--step-window-s` of the
forced step. Every ES call carries an explicit `--request-timeout`.

The default `--host` is the remote lab cluster (132.77.73.217:9200), NEVER localhost -- a local
ES instance on the machine this runs on may be a separate, independently-managed deployment
other people are actively using; pointing this tool at it is an explicit `--host` opt-in.

Usage:
    python3 tools/es_clock_check.py --run-id 12 --session 3 --pulse-period-s 1
    python3 tools/es_clock_check.py --run-id 13 --session 3 --pulse-period-s 5 \\
        --min-wrap-crossings 3 --step-time-utc 2026-08-24T14:03:00+00:00 --json soak.json
"""
from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone

from clock_check_accumulator import RunAccumulator
from clock_check_es import ReadOnlyESClient, iter_run_documents

DEFAULT_HOST = "132.77.73.217:9200"  # remote lab ES -- see module docstring, never localhost by default
DEFAULT_INDEX = "event_log_v2"
DEFAULT_PAGE_SIZE = 2000
DEFAULT_REQUEST_TIMEOUT_S = 30.0
DEFAULT_MAX_EXAMPLES = 50
DEFAULT_STEP_WINDOW_S = 180


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--run-id", type=int, required=True)
    parser.add_argument("--session", required=True)
    parser.add_argument("--host", default=DEFAULT_HOST, help=f"Elasticsearch host:port (default: {DEFAULT_HOST})")
    parser.add_argument("--index", default=DEFAULT_INDEX)
    parser.add_argument("--page-size", type=int, default=DEFAULT_PAGE_SIZE)
    parser.add_argument("--request-timeout", type=float, default=DEFAULT_REQUEST_TIMEOUT_S)
    parser.add_argument("--max-examples", type=int, default=DEFAULT_MAX_EXAMPLES)
    parser.add_argument(
        "--min-wrap-crossings", type=float, default=0.0,
        help="Fail C2 if the observed wrap-crossing count is below this. Leave at 0 (default) "
             "for the short probe, which cannot cross a wrap by design; pass 3 for the soak.",
    )
    parser.add_argument("--pulse-period-s", type=float, default=None, help="Commanded pulse period, for C7.")
    parser.add_argument(
        "--step-time-utc", default=None,
        help="ISO 8601 UTC time of the forced wall-clock step, for C6 (e.g. 2026-08-24T14:03:00+00:00).",
    )
    parser.add_argument("--step-window-s", type=float, default=DEFAULT_STEP_WINDOW_S)
    parser.add_argument("--json", dest="json_path", default=None, help="Write the full result as JSON here.")
    return parser


def _parse_step_time(raw: str | None) -> datetime | None:
    if not raw:
        return None
    step_time_utc = datetime.fromisoformat(raw)
    if step_time_utc.tzinfo is None:
        step_time_utc = step_time_utc.replace(tzinfo=timezone.utc)
    return step_time_utc


def _print_report(result: dict) -> None:
    print(f"subject={result['subject']}  total_docs={result['total_docs']}  host={result['host']}")
    for name, check in result["checks"].items():
        verdict = check.get("pass")
        label = "PASS" if verdict is True else "FAIL" if verdict is False else "N/A "
        detail = {k: v for k, v in check.items() if k not in ("pass", "examples")}
        print(f"[{label}] {name}: {detail}")
        examples = check.get("examples")
        if examples:
            print(f"         examples ({len(examples)} shown, capped): {examples[:5]}")


def main(argv: list[str] | None = None) -> int:
    args = _build_parser().parse_args(argv)
    step_time_utc = _parse_step_time(args.step_time_utc)

    subject = f"bp_s{args.session}_r{args.run_id}"  # trap 6 -- isolate the run, index holds ~2.9M docs
    client = ReadOnlyESClient(args.host, args.index, args.request_timeout)
    acc = RunAccumulator(
        pulse_period_s=args.pulse_period_s,
        step_time_utc=step_time_utc,
        step_window_s=args.step_window_s,
        max_examples=args.max_examples,
    )

    for doc in iter_run_documents(client, subject, args.page_size):
        acc.add(doc)

    checks = acc.finalize()
    if args.min_wrap_crossings > 0:
        checks["C2_wrap_crossings"]["pass"] = checks["C2_wrap_crossings"]["wrap_crossings"] >= args.min_wrap_crossings
        checks["C2_wrap_crossings"]["required"] = args.min_wrap_crossings

    result = {
        "subject": subject,
        "run_id": args.run_id,
        "session": args.session,
        "host": args.host,
        "index": args.index,
        "total_docs": acc.total_docs,
        "checks": checks,
    }

    _print_report(result)

    if args.json_path:
        with open(args.json_path, "w") as f:
            json.dump(result, f, indent=2, default=str)
        print(f"\nFull result written to {args.json_path}")

    hard_fail = any(c.get("pass") is False for c in checks.values())
    return 1 if hard_fail else 0


if __name__ == "__main__":
    sys.exit(main())
