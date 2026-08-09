---
phase: 18-extlink-pi-transport
plan: 15
subsystem: pi-hardware
tags: [msgpack, wire-codec, cli, dealer, zmq, cross-platform, fda-demo]

# Dependency graph
requires:
  - phase: 18-extlink-pi-transport
    provides: "external_hardware_wire.py's encode()/decode_envelope() (plan 18-05) — the byte format this driver's wire module reproduces and interops against"
provides:
  - "tools/extlink_driver/ — a socket-free wire codec, a cross-platform DEALER CLI (interactive/--sweep/--rate), a throwaway extlink_demo FDA, and a researcher-facing README"
affects: [18-12]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "zmq/msgpack imported only inside mode handlers (never module scope) so --help works before either dependency is installed — the same deferred-import trick plan 18-11's extlink_smoke.py uses."
    - "extlink_wire.py duplicates (does not import) the Pi's wire codec, matched field-for-field and packing-option-for-packing-option (msgpack.packb(..., use_bin_type=True)) rather than sharing code, since the laptop has no pi-mirror checkout."

key-files:
  created:
    - tools/extlink_driver/extlink_wire.py
    - tools/extlink_driver/test_extlink_wire.py
    - tools/extlink_driver/extlink_driver.py
    - tools/extlink_driver/extlink_demo_fda.json
    - tools/extlink_driver/README.md

key-decisions:
  - "coerce_value/parse_command live in extlink_wire.py (not extlink_driver.py) so the whole command-parsing/framing half is provable with zero sockets — the interop test loads the Pi's REAL external_hardware_wire.py by path and feeds it driver-built frames; all three interop cases PASSED (not skipped)."
  - "The docstring's own prose could not contain the literal substring 'zmq' — the plan's own verification is a literal `grep -c zmq`, stricter than an AST-only guard. Reworded to 'socket-library import' once discovered by that grep failing, mirroring 18-05's identical fix for the word 'autopilot'."
  - "--sweep implements a genuine triangle wave (20 steps up, 20 steps down, looped until --seconds elapses) rather than a sine or linear one-shot ramp, so a threshold anywhere inside [--min, --max] is provably crossed in both directions every cycle, satisfying the plan's own must_haves truth."
  - "--rate sends the running seq counter as the signal value (not a fixed/random value) — the soak's whole point is throughput and queue behavior, not any particular payload; no dtype assumption is made since the driver doesn't know the FDA's declared type for an arbitrary --signal."
  - "extlink_demo_fda.json's own description field carries the authoring instructions but must never contain the literal signal name 'left_paw_x' (the task's own automated verify greps the JSON blob for it) — the concrete option-group label, item label, and threshold values live only in README.md, keeping the JSON provably inert."

patterns-established: []

requirements-completed: [EXTLINK-20]

# Metrics
duration: ~12min
completed: 2026-08-09
---

# Phase 18 Plan 15: `tools/extlink_driver/` — cross-platform hand driver + demo FDA Summary

**A socket-free, byte-verified MessagePack wire module; a `zmq`/`msgpack`-deferred-import DEALER CLI with interactive/`--sweep`/`--rate` modes; and a deliberately inert three-state demo FDA whose two signal-gated transitions must be authored by hand in the browser — the tool a researcher runs on their own laptop to watch a rig's state machine respond to a typed value.**

## Performance

- **Duration:** ~12 min (file reads/research + implementation; commit span 08:22:12Z–08:26:37Z)
- **Started:** 2026-08-09T08:15:00Z (approx)
- **Completed:** 2026-08-09T08:27:00Z
- **Tasks:** 3 (Task 1 `tdd="true"`, Tasks 2/3 `type="auto"`)
- **Files modified:** 5 (all new, all under `tools/extlink_driver/`)

## Accomplishments

- **Task 1 (`extlink_wire.py`, TDD):** Wrote `test_extlink_wire.py` first (25 tests) and watched it
  fail with `ModuleNotFoundError: No module named 'extlink_wire'` — genuine RED. Implemented
  `now_ms`/`sig_frame`/`evt_frame`/`hb_frame`/`coerce_value`/`parse_command` (101 lines,
  stdlib + `msgpack` only). `coerce_value` returns real `bool`s (not `int`s) for `"true"`/`"false"`
  case-insensitively, parses a `{...}` token as JSON (the `@event` payload case), and falls back to
  numeric-then-string. `parse_command` never raises on a blank line or garbage input. The interop
  test loads the Pi's real `external_hardware_wire.py` by path
  (`importlib.util.spec_from_file_location`) and feeds it `sig_frame`/`evt_frame`/`hb_frame` output
  through its own `decode_envelope`/`DecodeStats` — all three **PASSED, not skipped**. 25/25 tests
  green; `grep -c zmq extlink_wire.py` = 0.
- **Task 2 (`extlink_driver.py`):** 175-line argparse CLI with `--pi-host`/`--listen-port`/
  `--source-id` (all required) and a mutually exclusive `--sweep SIGNAL` / `--rate N` group
  (interactive stdin is the default when neither is given). `zmq` and `extlink_wire` (which pulls in
  `msgpack`) are imported only inside `_connect`/`_import_wire`, called from each mode handler —
  never at module scope — so `--help` prints and exits 0 on this dev host, which has no `zmq`
  installed. Interactive mode uses blocking `input("> ")`, echoes
  `sent SIG left_paw_x = 0.7 (seq 12)`, and exits cleanly on `EOFError`/`KeyboardInterrupt`.
  `--sweep` is a genuine 20-step-up/20-step-down triangle wave, looping until `--seconds` elapses.
  `--rate` sends the shared `seq` counter as the value at `1/rate`-second intervals, printing a
  once-a-second progress line and a final `done: sent N messages in Xs` — **no latency number
  anywhere**. Portability grep (`termios|curses|fcntl|os.fork|/dev/tty`) is clean. Verified the
  three mode handlers' internal logic (sweep triangle bounds, rate counter, `--rate` without
  `--signal` failing loudly) against a fake in-process `zmq` module before committing.
- **Task 3 (`extlink_demo_fda.json` + `README.md`):** The demo FDA has exactly the three required
  states (`wait` initial, `armed`, `fired`), one unconditional `fired -> wait` transition, and **no**
  entry actions and **no** occurrence of any signal name (verified both by the plan's own JSON-blob
  grep-equivalent assertion and by eye). Verified against the REAL save gate, not a stand-in: copied
  the file into the running `api` container and called
  `fda_validation.collect_hard_errors(fda_json, SimpleNamespace(flags={}, semantic_hardware={},
  hardware_module_ids=[]))` — **zero errors**, confirming the stub-toolkit path plan text
  anticipated works as written; no fallback to a structural-only assertion was needed.
  `README.md` gives the three copy-pasteable invocations against plan 18-12's `dlc_cam1`/
  `132.77.72.28:5599` demo module (verbatim from `18-12-PLAN.md`'s own checkpoint text), the
  option-group/item-label recipe for authoring the two gated transitions in the browser
  (`"dlc_cam1 signals"` group, `"left_paw_x (float)"` item — cross-checked against `18-14-SUMMARY.md`,
  which landed concurrently and confirmed the exact `"<name> (<dtype>)"` label pattern), the
  no-latency rationale verbatim from this plan's own constraints, and the soak's four observable
  pass/fail criteria.

## Task Commits

1. **Task 1: `extlink_wire.py` — every byte, no socket** - `48a4c07` (test)
2. **Task 2: `extlink_driver.py` — DEALER, stdin loop, `--sweep`, `--rate`** - `537107a` (feat)
3. **Task 3: The `extlink_demo` FDA + a README written for someone on a Mac** - `54d6785` (feat)

**Plan metadata:** committed separately (this SUMMARY.md + STATE.md + ROADMAP.md).

## Files Created/Modified

- `tools/extlink_driver/extlink_wire.py` (101 lines) - socket-free frame construction + stdin command parsing
- `tools/extlink_driver/test_extlink_wire.py` (231 lines) - 25 tests, including 3 interop tests against the Pi's real decoder
- `tools/extlink_driver/extlink_driver.py` (175 lines) - argparse DEALER CLI, three mutually exclusive modes
- `tools/extlink_driver/extlink_demo_fda.json` - inert wait/armed/fired demo task definition
- `tools/extlink_driver/README.md` - install, three invocations, transition-authoring recipe, no-latency rationale, soak recipe

## Decisions Made

See `key-decisions` in frontmatter: the literal-`zmq`-in-docstring grep fix, the triangle-wave
`--sweep` implementation, the `--rate` payload choice, and the demo FDA's description-vs-README
split to keep the signal name out of the shipped JSON.

## Deviations from Plan

None — plan executed exactly as written. One near-miss caught by the plan's own verification
before it became a deviation: `extlink_wire.py`'s first draft mentioned "zmq" in prose inside its
own docstring (explaining why it doesn't import it), which the plan's literal `grep -c zmq`
verification step (correctly) flagged. Reworded to "socket-library import" — a text-only change,
re-verified with a full pytest re-run confirming no test behavior changed.

## Issues Encountered

`/home/ido/pi-mirror/scripts/dev/extlink_smoke.py` (plan 18-11's deliverable, executing
concurrently with this plan) did not yet exist when this plan's overall `<verification>` block's
`ls` step was run — that script belongs to plan 18-11's own scope and files_modified, not this
plan's. Not fixed here; noted for the orchestrator, no action needed from this plan.

## User Setup Required

None — no external service configuration required. All three tasks are agent-runnable with no
socket and no rig contact; `pyzmq`/`msgpack` installation on the researcher's actual laptop is a
documented step in the deliverable README itself, not a setup step for this execution.

## Next Phase Readiness

- All three of plan 18-12's checkpoint invocations (interactive, `--sweep`, `--rate`) are ready to
  run against the real rig once plan 18-12's Task 1 registers the `dlc_cam1` module and the
  `extlink_demo` task definition, as `18-12-PLAN.md`'s own text already assumes.
- The demo FDA's two gated transitions remain deliberately unauthored — plan 18-12's checkpoint
  step 1b is the step that adds them, in the browser, which is the actual EXTLINK-19 proof.
- `gsd-tools requirements mark-complete EXTLINK-20` found no checkbox/traceability row in
  `REQUIREMENTS.md` (same known gap as every prior EXTLINK plan) — completion tracked via this
  SUMMARY, STATE.md, and `roadmap update-plan-progress 18` instead.
- No blockers.

---
*Phase: 18-extlink-pi-transport*
*Completed: 2026-08-09*

## Self-Check: PASSED

All 5 deliverable files verified present on disk (`extlink_wire.py`, `test_extlink_wire.py`,
`extlink_driver.py`, `extlink_demo_fda.json`, `README.md` under `tools/extlink_driver/`), plus
this SUMMARY.md. All 3 task commit hashes (`48a4c07`, `537107a`, `54d6785`) verified present in
`git log`. Fresh `python3 -m pytest -q tools/extlink_driver/` re-run: 25 passed, 0 skipped, 0
failed, including all 3 interop tests against the Pi's real `external_hardware_wire.py`.
