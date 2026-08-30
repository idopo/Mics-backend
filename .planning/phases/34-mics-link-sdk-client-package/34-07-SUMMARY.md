---
phase: 34-mics-link-sdk-client-package
plan: 07
subsystem: sdk
tags: [replay, csv, jsonl, timing, cli, console-script, wide-format]

# Dependency graph
requires: ["34-01", "34-02", "34-06"]
provides:
  - "mics_link.replay.read_rows/ReplayStats/replay/main — CSV/JSONL replay driver (long + wide shapes), the phase's own regression vehicle and Phase 35's camera/model/animal-free proof mechanism"
  - "mics_link.timing.Pacer — public, origin-relative, drift-free scheduler (realtime/scaled/fast); re-exported from mics_link.__all__ for Phase 35's video frame loop"
  - "mics-link-replay console_script (pyproject.toml [project.scripts], declared dangling in 34-01) is now a real, installable entry point"
affects: [34-08, 34-09, 35]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Shape detection by header/keys, never a flag: long (t,signal,value) vs wide (t + one column per signal) is decided once per file from the CSV header or JSONL's first record's keys; a 'signal' column without 'value' is an ambiguous file-level MicsLinkError, not a row error"
    - "JSONL wide records derive their signal columns PER LINE from that line's own keys (not a fixed list from the first record) — lets an occluded keypoint be omitted entirely rather than sent as an empty placeholder; CSV wide format keeps a fixed column list since a CSV row cannot vary shape"
    - "Origin-relative Pacer: every wait_until(t_rel) measures against the ONE start() timestamp, never against the previous call — falling behind returns 0.0 immediately (no negative sleep, no catch-up burst) and is counted, never printed as a number"
    - "replay() takes a link, never creates one — testable against MicsLink(FakeTransport()) with no socket; main() is the only place connect() is called, inside a with block"
    - "ReplayStats is one object shared by the reader (rows_read/rows_malformed) and the sender (sent/dropped/rejected) — main() passes the SAME instance into both read_rows() and replay()"

key-files:
  created:
    - sdk/src/mics_link/replay_io.py
    - sdk/src/mics_link/replay.py
    - sdk/src/mics_link/timing.py
    - sdk/tests/test_replay.py
    - sdk/tests/test_timing.py
    - sdk/tests/fixtures/replay_sample.csv
    - sdk/tests/fixtures/replay_sample.jsonl
    - sdk/tests/fixtures/replay_sample_wide.csv
    - sdk/tests/fixtures/replay_sample_wide.jsonl
    - sdk/tests/fixtures/replay_malformed.csv
  modified:
    - sdk/src/mics_link/__init__.py
    - sdk/tests/test_public_api.py

key-decisions:
  - "Reader logic split into mics_link/replay_io.py, re-exported unchanged from mics_link/replay.py (read_rows/ReplayStats still resolve from mics_link.replay) — sanctioned by this plan's own Task 2 <action> block ('If replay.py approaches 300 lines, split the reader...'), applied proactively rather than waiting to hit the limit, since the reader logic (CSV+JSONL x long+wide) is a large, self-contained concern deserving its own module and test file (mirrors heartbeat.py/test_heartbeat_scheduling.py's existing one-module-one-test-file pattern)."
  - "A dict-shaped CSV value (a `{...}` cell) is detected by a dedicated read_rows-level check (_is_dict_shaped), independent of coerce_token — coerce_token(allow_json_dict=False) would otherwise pass such text through as an ordinary, VALID string (str is an allowed dtype), silently admitting exactly the EVT-shaped content decision 8 rules out of scope. JSONL gets this for free from json.loads's native typing (type(value) is dict check)."
  - "Pacer.wait_until distinguishes 'exactly on time' (remaining == 0, true for every schedule's first row) from 'genuinely behind' (remaining < 0) for behind_count() purposes — both return 0.0 (no sleep either way), but only the latter increments the counter. An earlier draft counted both, which double-counted the always-on-time first row as 'behind' and failed its own test."
  - "ReplayStats.sent/dropped in replay() reflect send_signal's ENQUEUE outcome (True/False), not MicsLink's own internal stats.sent (actual-transport-delivery count) — these are deliberately different counters at different layers; replay() only observes what the client's public API returns, matching decision 6 (replay() never touches the transport)."

requirements-completed: [SDK-12]

# Metrics
duration: ~70min
completed: 2026-08-30
---

# Phase 34 Plan 07: Replay driver — CSV/JSONL reader, Pacer, console entry point Summary

**A CSV/JSONL replay driver that plays a recorded `(t, signal, value)` file — in either a long `t,signal,value` shape or a wide `t` + one-column-per-signal shape, detected by header not a flag — through the public `mics_link` client at real time, at a scale factor, or as fast as possible, via a now-real `mics-link-replay` console command and a newly public `mics_link.timing.Pacer` that Phase 35's video frame loop will reuse unchanged.**

## Performance

- **Duration:** ~70 min
- **Started:** 2026-08-30 (after worktree base correction to `3e06a9b`, an unrelated ~3-commit ancestor state)
- **Completed:** 2026-08-30
- **Tasks:** 2/2 completed, each as a TDD RED -> GREEN pair
- **Files modified:** 10 created, 2 modified

## Accomplishments

- **`mics_link.replay_io.read_rows`** is a generator (never a list) that reads a CSV or
  JSONL file, dispatching on suffix case-insensitively, and yields `(t: float, signal: str,
  value)` tuples for both a **long** shape (`t,signal,value` columns/keys, column order and
  extra columns ignored) and, per the 2026-08-30 "DLC-Live and Windows" amendment, a **wide**
  shape (`t` + one column per signal, one non-empty cell per tuple, an empty cell skipped
  silently as "no sample this frame" — the occluded-keypoint case). Shape is detected from
  the header/keys, never a flag; a `signal` column without `value` is a file-level
  `MicsLinkError` naming the ambiguity, not a row error.
- **A malformed row never aborts a replay** (decision 3): missing column/key, unparseable
  `t`, empty `signal`, unparseable JSON, or a `{...}`-shaped value (EVT-shaped content is
  explicitly out of scope, decision 8) are counted in `stats.rows_malformed` and skipped.
  `sdk/tests/fixtures/replay_malformed.csv` proves all four failure modes plus 2 good rows
  in one file, with an exact `rows_malformed == 4` count and zero exceptions.
- **Wide and long fixtures produce byte-identical `(t, signal, value)` send sequences**
  (`replay_sample.csv`/`.jsonl` vs `replay_sample_wide.csv`/`.jsonl`) — proven by an
  equality assertion between the two reads, satisfying the amendment's explicit acceptance
  bar.
- **`mics_link.timing.Pacer`** (new public module, exported from `mics_link.__all__`) is
  the origin-relative, drift-free scheduler: every `wait_until(t_rel)` measures from the one
  `start()` timestamp, never cumulatively. `realtime`/`scaled` sleep durations are proven to
  the millisecond against an injected recording clock+sleep (`[0.5, 1.0]` at scale 1.0,
  halved at scale 2.0, doubled at scale 0.5, all with zero real waiting). Falling behind (a
  10s clock jump between rows, simulating a slow model-inference step) produces **zero**
  sleep calls, **no** negative sleep, and is counted via `behind_count()` — never printed as
  a number.
- **`mics_link.replay.replay(link, rows, ...)`** takes an existing `link` (decision 6) and
  drives `send_signal` per row, tolerating a full queue (`stats.dropped`) and a rejected
  value (`InvalidValueError` caught, `stats.rejected`) without ever aborting or letting the
  exception escape — proven by a queue-size-1 test and a list-shaped value test.
- **`main()`** is the CLI: `mics-link-replay --host H --port P --source-id S --file PATH
  [--mode realtime|scaled|fast] [--scale N] [--heartbeat-s N] [--queue-size N]`. `--scale
  <= 0` under `--mode scaled` and a missing `--file` both exit non-zero with a clear
  stderr message; `--help` is proven to exit 0 **without ever calling `connect()`**
  (`connect` monkeypatched to raise if invoked). The printed summary is COUNTS plus a plain
  `duration_s` — proven by regex to contain no `laten|jitter|drift|ms\b` substring anywhere
  (decision 5).
- **`mics-link-replay` is no longer a dangling entry point.** Installed into an isolated
  `--target` directory with `--no-deps` (exactly the plan's own verification command), the
  script exists and — with its dependency path on `PYTHONPATH` — actually runs (`--help`
  prints correctly); `python -m mics_link.replay` (the documented Windows fallback,
  SDK-14h) also works standalone.
- **`Pacer` is re-exported from `mics_link.__all__`**, growing 34-06's locked 6-name set to
  7 (see Deviations) — Phase 35's video frame loop can now `from mics_link import Pacer`
  exactly as the README (plan 34-08) will document.

## Task Commits

Each task followed the RED -> GREEN TDD cycle:

1. **Task 1 RED: failing CSV/JSONL reader tests + 5 fixture files** - `91408d3` (test)
2. **Task 1 GREEN: mics_link/replay_io.py + re-exporting mics_link/replay.py** - `ea8042c` (feat)
3. **Task 2 RED: failing Pacer tests + replay()/main() tests** - `3847e2f` (test)
4. **Task 2 GREEN: mics_link/timing.py + replay()/main() + __init__.py + test_public_api.py** - `423d9a2` (feat)

## Files Created/Modified

- `sdk/src/mics_link/replay_io.py` (231 lines, new) - `ReplayStats`, `read_rows`, CSV/JSONL
  parsing, long/wide shape detection, dict-shaped-value rejection
- `sdk/src/mics_link/replay.py` (152 lines, new) - `replay()`, `main()`, argparse CLI
  surface, summary formatting; re-exports `ReplayStats`/`read_rows` from `replay_io`
- `sdk/src/mics_link/timing.py` (78 lines, new) - `Pacer`: `start()`, `wait_until()`,
  `behind_count()`
- `sdk/src/mics_link/__init__.py` - `Pacer` added to imports and `__all__` (6 -> 7 names)
- `sdk/tests/test_replay.py` (31 tests) - reader half (Task 1) + timing/CLI half (Task 2)
- `sdk/tests/test_timing.py` (8 tests) - `Pacer`'s three modes, falling-behind, validation
- `sdk/tests/test_public_api.py` - `__all__` lock updated to include `Pacer`
- `sdk/tests/fixtures/replay_sample.csv`, `.jsonl` - 5-row long-format sample (float, int,
  bool, str values)
- `sdk/tests/fixtures/replay_sample_wide.csv`, `.jsonl` - the same 5 tuples in wide shape
- `sdk/tests/fixtures/replay_malformed.csv` - 2 good + 4 deliberately malformed rows

## Final File Schema (verbatim, for plan 34-08's README)

**Long (one row per sample):**
```csv
t,signal,value
0.00,nose_p,0.98
0.00,tail_p,0.41
0.03,count,3
0.03,visible,true
0.03,label,left
```
JSONL: one `{"t": ..., "signal": ..., "value": ...}` object per line, same 5 records.

**Wide (one row per timestamp, one column per signal — the DLC-export-shaped case):**
```csv
t,nose_p,tail_p,count,visible,label
0.00,0.98,0.41,,,
0.03,,,3,true,left
```
JSONL: one `{"t": ..., <signal>: <value>, ...}` object per line; a signal can simply be
omitted from a line instead of sent as an empty value.

Both shapes above produce the byte-identical `(t, signal, value)` send sequence.

## CLI Surface (verbatim, for plan 34-08's README)

```
mics-link-replay --host H --port P --source-id S --file PATH
                 [--mode realtime|scaled|fast] [--scale 2.0]
                 [--heartbeat-s 1.0] [--queue-size 256]
```
Windows fallback when the console script isn't on PATH: `python -m mics_link.replay ...`
(same arguments).

## Console Script — Confirmed Resolved

```
$ rm -rf /tmp/mics_link_replaycheck
$ python3 -m pip install --no-build-isolation --no-deps --target /tmp/mics_link_replaycheck ./sdk
Successfully installed mics-link-0.1.0
$ test -x /tmp/mics_link_replaycheck/bin/mics-link-replay -o -f /tmp/mics_link_replaycheck/bin/mics-link-replay
console script installed
$ PYTHONPATH=/tmp/mics_link_replaycheck /tmp/mics_link_replaycheck/bin/mics-link-replay --help
usage: mics-link-replay [-h] --host HOST --port PORT --source-id SOURCE_ID ...
```
The `pyproject.toml [project.scripts]` entry `mics-link-replay = "mics_link.replay:main"`
(declared dangling in plan 34-01) now resolves to a real, callable target.

## Decisions Made

See `key-decisions` in the frontmatter for: why the reader split into `replay_io.py` was
done proactively rather than at the 300-line trigger; why a dict-shaped CSV value needs its
own detection separate from `coerce_token`; why `Pacer.behind_count()` excludes the
always-on-time first row; and why `ReplayStats.sent`/`dropped` are enqueue-level counts,
not the client's own transport-level `stats.sent`.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] JSONL wide-format signal columns computed from the FIRST record's keys
broke on records with different key sets**
- **Found during:** Task 1, first run of `test_wide_jsonl_produces_the_same_tuples_as_long_csv`
- **Issue:** The initial implementation determined `signal_columns` once (from the first
  JSONL record's keys, mirroring the CSV header) and reused that fixed list for every
  subsequent record. `replay_sample_wide.jsonl`'s two records have genuinely different key
  sets (`{t, nose_p, tail_p}` then `{t, count, visible, label}}`) — exactly the
  occluded-keypoint case the wide format exists for — so the second record's real keys were
  never in the fixed list and were silently skipped: only 2 of the expected 5 tuples were
  yielded.
- **Fix:** For JSONL specifically, a wide record's signal columns are now derived from
  THAT record's own keys (minus `t`), not a fixed list — the shape decision (long vs wide)
  is still made once from the first record, but the actual column set is per-line. CSV
  keeps a fixed column list from the header, since a CSV row's shape cannot vary by
  definition.
- **Files modified:** `sdk/src/mics_link/replay_io.py`
- **Verification:** `test_wide_jsonl_produces_the_same_tuples_as_long_csv` passes; full
  `sdk/` suite green
- **Committed in:** `ea8042c` (found and fixed before the GREEN commit, so no separate
  fix-commit was needed)

**2. [Rule 1 - Bug] `Pacer.behind_count()` counted the always-on-time first `wait_until`
call as "behind"**
- **Found during:** Task 2, first run of `test_falling_behind_produces_no_negative_sleep_and_counts_it`
- **Issue:** The first draft incremented `behind_count` whenever `remaining <= 0`. Every
  schedule's first row has `remaining == 0` by construction (it sends at the origin), which
  the test correctly treats as "on time", not "behind" — the draft's `<=` conflated the two,
  producing `behind_count() == 2` instead of the expected `1` for a test with one on-time
  row and one genuinely-overdue row.
- **Fix:** Only `remaining < 0` (strictly negative) increments `behind_count`; `remaining
  == 0` still returns `0.0` (no sleep needed either way) but is not counted as behind.
- **Files modified:** `sdk/src/mics_link/timing.py`
- **Verification:** `cd sdk && python3 -m pytest -q tests/test_timing.py` — all 8 tests pass
- **Committed in:** `423d9a2`

### Amendment-mandated additions beyond this plan's own `files_modified`

**3. [Rule 2 - amendment-mandated] `mics_link/timing.py`, wide-format fixtures, and
`mics_link/replay_io.py` are not in this plan's frontmatter `files_modified` list, and
`mics_link/__init__.py` + `sdk/tests/test_public_api.py` are modified though untouched by
this plan's own file list**
- **Found during:** reading the plan's own "AMENDED 2026-08-30" block before starting
- **Issue:** The plan's frontmatter `files_modified` predates the same-day amendment, which
  explicitly requires a new public `mics_link/timing.py` module, two new wide-format
  fixture pairs, `Pacer` re-exported from `mics_link.__all__`, and (as a direct consequence)
  an update to 34-06's `test_public_api.py` `__all__` lock — none of which the frontmatter
  lists, because the amendment text says so verbatim and post-dates the frontmatter.
- **Resolution:** All five are implemented exactly as the amendment specifies; the
  amendment's own text ("These override anything below that contradicts them") is the
  authorization, not an independent judgment call. `replay_io.py` (the reader split) is
  additionally sanctioned by this plan's own Task 2 `<action>` block, not just the
  amendment.
- **Files affected:** `sdk/src/mics_link/timing.py` (new), `sdk/src/mics_link/replay_io.py`
  (new), `sdk/tests/fixtures/replay_sample_wide.csv`/`.jsonl` (new),
  `sdk/src/mics_link/__init__.py` (modified), `sdk/tests/test_public_api.py` (modified)
- **Committed in:** `ea8042c` (replay_io.py, wide fixtures), `423d9a2` (timing.py,
  `__init__.py`, `test_public_api.py`)

---

**Total deviations:** 2 self-caught bugs (both Rule 1, fixed before their respective GREEN
commits, no separate fix-commits needed) + 1 amendment-mandated scope addition (Rule 2,
explicitly authorized by the plan's own amendment text). No deviation changed a decision
this plan itself locked; all were necessary for correctness or were directly mandated by
the plan's own text.

## Issues Encountered

None beyond the two self-caught deviations above, both found and fixed during normal TDD
execution before their GREEN commits.

## User Setup Required

None — no external service configuration required. `main()`'s real network path (`connect`)
is never exercised by this plan's own test suite; every test drives `replay()` directly
against `MicsLink(FakeTransport())` or monkeypatches `connect` for the `main()`/CLI tests.

## Next Phase Readiness

`mics_link.replay.{read_rows, ReplayStats, replay, main}` and `mics_link.timing.Pacer` are
the complete, tested SDK-12 surface. Plan 34-08 (README) can document the file schema, CLI
surface, and `Pacer` usage verbatim from this summary's "Final File Schema"/"CLI Surface"
sections above. Plan 34-09's rig checkpoint can use `mics-link-replay` directly against the
`ExtlinkDemo` fixture. Phase 35's DLC adapter can `from mics_link import Pacer` and pace its
video frame loop with the exact same scheduler this plan's tests already prove. No blockers.

---
*Phase: 34-mics-link-sdk-client-package*
*Completed: 2026-08-30*

## Self-Check: PASSED

All 10 claimed files verified present on disk (`sdk/src/mics_link/replay_io.py`,
`sdk/src/mics_link/replay.py`, `sdk/src/mics_link/timing.py`, `sdk/tests/test_replay.py`,
`sdk/tests/test_timing.py`, and the 5 fixture files). All 4 task commits (`91408d3`,
`ea8042c`, `3847e2f`, `423d9a2`) verified present in `git log`. Full `sdk/` suite: 227 tests
green (188 baseline + 39 new), ~2.5s.
