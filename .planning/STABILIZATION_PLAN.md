# MICS — Stabilization Plan Before Ephys Integration

**Prepared:** 2026-07-26
**Purpose:** discussion document — what has to happen before the system is "robust and operational", and in what order, ahead of the Open Ephys integration.

---

## Executive summary

Phases 9–17 delivered the full hardware-centralization + visual FDA editor arc, and were
manually validated on the live system. Two things stand between us and a system researchers
can drive end-to-end without a developer:

1. **Trigger assignment** — visible in the task editor UI, implemented on the Pi, but the
   backend validation layer was never built and the feature has never been run end-to-end.
2. **Compute primitives + variables** — fully planned (Phase 23), not implemented. Until it
   lands, any task needing a random target, a delay draw, or a trial counter must be written
   in Python, which defeats the purpose of the visual editor.

Agreed order:

| | Track | What it buys | Rough size |
|---|---|---|---|
| **1** | Trigger Assignment — validate + test (new phase) | Finishes a half-delivered feature already visible in the UI | M |
| **2** | Compute Primitives + Variables (Phase 23, planned) | Tasks with randomness/counters without writing Python | L |
| — | **Decision point — review before proceeding** | | |
| **3** | MICS-Link transport (Phase 18, planned) | The generic "external software → task" channel | L |
| **4** | Open Ephys on top of MICS-Link (new phase) | Closed-loop neural control, no TTL cable | M–L |

Tracks 1–2 are stabilization: they close the gap between what the UI promises and what the
system can actually do. Tracks 3–4 are the new science capability and are deliberately
gated behind that review.

Appendix A lists known gaps that are real but not on the critical path.

---

## Track 1 — Trigger Assignment: finish and test

**Status today:** the UI panel exists (`web_ui/react-src/src/components/TriggerAssignmentPanel.tsx`,
161 lines, wired into `TaskEditor.tsx`). The Pi runtime exists —
`apply_trigger_assignments()` plus `_build_touch_detector_callback` / `_build_digital_input_callback`
in `mics_task.py`, with a 12 KB unit-test file (`~/pi-mirror/tests/test_trigger_assignments.py`).
**The middle layer — backend validation — does not exist, and the feature has never been
exercised end-to-end.**

**What the feature does:** lets a researcher say from the UI "when trigger X fires, also run
the touch-detector read-out and update the view", instead of that wiring living in the task's
Python. It is the last piece of "configure a task without editing Python" on the input side.

**The core problem:** `trigger_assignments` is the only part of the FDA JSON the API does not
validate. States, transitions, hardware refs and actions all get a 422 on save. A bad trigger
handler or a bad `hardware_ref` sails through save and raises `ValueError` on the Pi *at
session start* — i.e. discovered in front of an animal, not at the desk.

**Work items:**

| # | Item | Where |
|---|---|---|
| 1.1 | Validate `trigger_assignments` on save: handler in the allowed set; `hardware_ref` resolves in the toolkit's `SEMANTIC_HARDWARE`; required config keys present per handler type → 422 instead of a Pi crash | `api/routers/toolkits.py`, `api/fda_utils.py` |
| 1.2 | Include trigger `hardware_ref`s in the recursive reference scanner, so a hardware-lib version change flags the task definitions that use them | `api/fda_utils.py` |
| 1.3 | Keep the UI handler list in sync with the Pi's (`default`, `log_only`, `touch_detector`, `digital_input`) — today these are two independently hard-coded lists that can silently diverge. Serve the list from the backend, or at minimum add a cross-check | `TriggerAssignmentPanel.tsx` |
| 1.4 | **End-to-end live test**: assign a touch-detector handler from the UI → push to the Pi → confirm the view tracker updates on a real touch → confirm a transition gated on it fires | Pi + UI |
| 1.5 | Same for `digital_input` | Pi + UI |
| 1.6 | Negative tests: unknown handler, bad `hardware_ref`, missing config key — all rejected at save time, with a message that names the offending assignment | UI |
| 1.7 | Confirm backward compatibility: a task definition with no `trigger_assignments` section leaves `self.triggers` untouched (the documented contract) | Pi |

**Why this needs its own GSD phase:** 1.4 and 1.5 run code paths that have never executed
against real hardware. Expect runtime findings, and budget a fix cycle after the first live
test rather than assuming a clean pass.

---

## Track 2 — Compute Primitives + Variables (Phase 23)

**Status:** fully planned, not implemented. Three plans written (23-01 Pi runtime, 23-02
backend validation, 23-03 GUI) plus a context document. Requirements CMP-01–06, CMP-10–15.

**What it does:** lets a GUI-built task compute values at state entry — a random target side,
a random delay, a trial counter, arithmetic over those — and route on them in transitions.
13 curated primitives (`random_choice`, `random_int`, `random_float`, `random_bool`, `assign`,
`add`, `subtract`, `multiply`, `divide`, `modulo`, `minimum`, `maximum`, `clamp`), stdlib
`random`/`math` only, so no new package dependency on the Pi.

Design decisions already locked: variables are untyped scratch slots declared in a top-level
`variables` registry and instantiated as ordinary Trackers in both `flags` and `view` — so
transitions read them through the existing operand path with zero new read code. Last-write-wins
on state re-entry (matches current instance-attribute behaviour across trials). Branching stays
in FDA transitions; the primitives produce values only. The `expr` free-text escape hatch was
deliberately decoupled and deferred.

**Three waves, each independently testable:**

| Wave | Scope | Key deliverable |
|---|---|---|
| 23-01 | Pi runtime | `variables` parsed at FDA load, instantiated as Trackers; `compute` entry-action; new `compute_primitives.py`; hot-reload instantiates newly-added variables before rebuilding transitions |
| 23-02 | Backend validation + storage | 422 on undeclared `output`, on name collision with `FLAGS`/`SEMANTIC_HARDWARE`/view keys, on a transition reading an undeclared variable; compute library stored as a `hardware_libs` row (reuses Phase-9 versioning + AST, no new table) |
| 23-03 | GUI | `compute` action editor in `StateBodyPanel` with primitive picker + per-arg inputs; typing a new `output` auto-declares the variable; condition-builder operand dropdown picks it up immediately |

**Acceptance shape:** a GUI-built task declares `variables: { target: {} }`, computes
`random_bool(0.5) → target` on trial onset, and two transitions gated on `target == true` /
`target == false` both fire across trials on a real Pi.

---

## Decision point

After tracks 1 and 2, review before committing to the MICS-Link arc. Suggested gate: a full
session runs end-to-end on a real Pi — GUI-built task with nested conditions, backend-supplied
hardware config, pre-run check passing, trigger assignment active, a computed variable driving
a branch, graduation firing — with no manual intervention.

---

## Track 3 — MICS-Link: Pi transport + ExternalHardware (Phase 18)

**Status:** fully planned, not implemented. Two large plans (18-01 ≈55 KB, 18-02 ≈67 KB) plus
a 19 KB context document. Requirements EXTLINK-01–13.

**What it does:** gives the Pi a structured, crash-safe input channel so external software on
another computer can push data *into* a running task. An author writes one `ExternalHardware`
subclass with `@signal` / `@event` / `@command` decorators and uploads it as an ordinary
hardware library — it then flows through the existing hardware-lib → hardware-module →
pilot-config → toolkit-dispatch → preflight pipeline with **no new DB tables and no new
dispatch shape**. Every signal automatically becomes readable via the existing
`view.get_value("source.signal")` API, so FDA transitions gate on external data with **zero
new call sites**.

Design already locked: one ZMQ ROUTER socket per instance on its own port; identity-checked
so only the configured `source_id` is accepted; MessagePack wire format; per-signal staleness
policy (`hold_last` / `return_default` / `return_none`); heartbeat-driven `<source>.alive`
tracker; a readiness gate with three escape paths so a task can never hang waiting on a dead
external source; malformed messages dropped and logged, never raised into the event loop.

**Recommendation — swap the reference consumer.** The plan currently names DeepLabCut as the
reference integration (Phase 22) with Open Ephys as a later recipe. I'd invert that: make
Open Ephys the first real consumer. The ephys integration has an immediate scientific payoff
and a stable, well-documented API on the other side; DeepLabCut adds a live pose-estimation
pipeline as an extra moving part we don't need yet. Phase 18 itself is consumer-agnostic —
only the reference integration changes.

---

## Track 4 — Open Ephys integration (new phase, after track 3)

Per `docs/open_ephys_integration.md`. Treat Open Ephys as just another piece of hardware in a
MICS task — startable, stoppable and readable from software, with **no cable between the two
systems**.

| Channel | Direction | Protocol | Purpose |
|---|---|---|---|
| Control | MICS → Open Ephys | HTTP REST, port 37497 | start/stop acquisition + recording, set save path per subject/session, inject event markers |
| Data | Open Ephys → MICS | ZMQ stream, default port 5556 | live spikes, events, continuous signal |

**Work items:**

| # | Item | Description |
|---|---|---|
| 4.1 | Open Ephys control module | Start/stop/record via the REST API, wired into the MICS session lifecycle so the researcher never touches the Open Ephys GUI |
| 4.2 | ZMQ subscriber as an `ExternalHardware` subclass | Spikes/events arrive as MICS-Link signals; `view.get_value("spike_rate")` behaves like any other sensor |
| 4.3 | Event markers replacing the TTL cable | MICS sends each behavioural event as a timestamped network message that Open Ephys records inline; inbound messages carry Open Ephys sample numbers, so both clocks co-register in software |
| 4.4 | Closed-loop demonstration | An FDA transition (reward, light, state change) driven by live spiking — the capability the current wired setup cannot offer |
| 4.5 | Alignment validation against the offline pipeline | Compare network-derived alignment against `session aligner/OpenEphysProcessor.py` output on the same recording, to quantify jitter rather than assume it |

**Trade-off to state plainly:** a hardware TTL has near-zero, deterministic latency; network
messages carry sub-millisecond to few-millisecond jitter. For behavioural alignment this is
within tolerance. If an experiment ever needs hardware-grade precision, we keep a single TTL
as a periodic sync heartbeat and use the network path for everything else. Item 4.5 exists to
measure this.

**Dependency note:** only 4.2 and 4.4 genuinely need track 3. Items 4.1 and 4.3 are plain HTTP
and could be prototyped independently — that alone already removes the TTL cable, if there is
schedule pressure on the ephys side.

---

## Appendix A — Known gaps, not on the critical path

**A.1 — `api/main.py` is 2233 lines.** Our standard is 300 lines/file, hard limit 500. This is
the main API surface and now the riskiest file to touch: wide blast radius, no test coverage.
The `api/routers/` split pattern already exists and is used by the newer routers; the remaining
route groups should follow.

**A.2 — Effectively no backend test coverage.** `api/tests/` contains one 1.3 KB file. The Pi
side is considerably better (5 test files, including a 27 KB suite for FDA loading). Every
backend regression is currently caught by a human clicking through the UI. Minimum viable fix:
smoke tests over the session-start path — task-definition save/validate, toolkit dispatch,
preflight, session start.

**A.3 — Planning documents have drifted.** `REQUIREMENTS.md` traceability marks phases 1–13 and
BUG-05–07 as "Pending" though all are complete; `ROADMAP.md`'s phase-summary table has
goal/status columns swapped in several rows; `STATE.md` still reads "Phase 1 next, 89%";
`.claude/backlog/BACKLOG.md` lists four superseded tasks. Cheap to fix, and this is the
document a new person would read first.

**A.4 — Manual validation of phases 12–17 is not recorded.** The work was done on the live
system, but each phase's VERIFICATION.md still carries an open "Human Verification Required"
list (20 items across phases 12–17). Marking those closed costs little and prevents the same
question being re-asked later.

**A.5 — `CLAUDE.md` is out of date.** Claims all API routes live in `main.py` and that there is
no automated test suite — both now wrong (`api/routers/`, `api/tests/` exist) — and several
top-level directories are undocumented.

---

## Open questions for discussion

1. **DeepLabCut or Open Ephys as the first MICS-Link consumer?** (Recommendation: Open Ephys.)
2. **How much test automation do we want?** Zero backend tests is the status quo; a smoke suite
   over the session-start path is the minimum I would argue for.
3. **Timeline pressure on ephys** — if there is a hard deadline, 4.1/4.3 (REST control + event
   markers) can be prototyped independently of MICS-Link and already remove the TTL cable.
