# 15 — The manuscript's claims, tested against Autopilot

**Written 2026-08-06.** Companion to `13_MANUSCRIPT_CLAIMS_AUDIT.md` (claims vs. the MICS roadmap)
and `14_AUTOPILOT_VS_MICS.md` (system vs. system). This document asks the narrower and more
dangerous question:

> For each key feature the manuscript emphasises — **does it survive a reviewer who knows
> Autopilot?**

That reviewer is likely, because MICS is built on Autopilot (`14` §1b–1c) and Autopilot is in the
draft's own Table 1. Evidence below is from official **`auto-pi-lot 0.4.4`** (PyPI sdist, read
2026-08-06) and the live MICS system with the roadmap complete.

**Verdict key:** ✅ MICS-original · ◐ inherited concept, MICS extends the management layer ·
⊘ inherited outright, not a differentiator · ❌ MICS is behind Autopilot

---

## Summary table

| | Manuscript claim | Autopilot 0.4.4 | Verdict |
|---|---|---|---|
| C1 | Local execution / central coordination | **its core thesis** — Terminal + distributed Pilots | ⊘ |
| C2 | Hardware abstraction, hardware-agnostic task logic | `Hardware` base + `HARDWARE` dict + prefs + plugin registry | ◐ |
| C3 | Task logic as an inspectable FSM (Blueprint) | Python stage-methods, opaque to every other layer | ✅ |
| C4 | One representation persisting design→execution→data | partial: `PARAMS` → form, `TrialData` → schema, `History_Table` → change log | ◐ |
| C5 | Adaptive progression, performance-based, branching | `assign_protocol` + `graduate()` + **`Accuracy`** + `NTrials` | ❌ |
| C6 | Automatic logging of all hardware/state/system events | **none** — no auto-instrumentation anywhere | ✅ |
| C7 | Relational metadata + pre-dispatch validation | HDF5 per subject; **no pre-run validation** (a TODO) | ✅ |
| C8 | Multi-scale timing; hardware *and* network closed loop | **`Transformer` child** = networked closed loop; **no clock sync at all** | ◐ |
| C9 | Fault tolerance; new/resume/restart run modes | pilot survives Terminal loss; step/session persisted; no run modes | ◐ |
| C10 | Virtual MICS / digital twin | none | — *(neither system has what the draft claims)* |
| C11 | Scaling: parallel stations, one infrastructure | **its design** — many Pilots + Children per Terminal | ⊘ |
| C12 | One architecture across very different paradigms | designed and published for exactly this | ⊘ |
| C13 | Integration with ephys / imaging / opto / tracking | TTL out, cameras, transforms — **sync with, never control of** | ✅ |
| C14 | Table 1 positioning | — | needs rewriting |

**Four claims are clean wins (C3, C6, C7, C13). Three are inherited and currently presented as
MICS design decisions (C1, C11, C12). Two need reframing (C2, C8). One must be dropped (C5).**

---

## Claim by claim

### C1 — Separation of local execution from central coordination ⊘

**Autopilot:** this *is* Autopilot. A Terminal coordinates; each Pilot executes its task locally on
its own Pi and keeps running if the Terminal goes away. Multi-agent, networked, autonomous-local is
the framework's founding argument.

**MICS:** the same property, delivered by **the same code** — `core/pilot.py`, ~96 % of its original
lines intact, `networking/node.py` byte-identical (`14` §1b).

**Consequence.** Results §1 presents this as a MICS design decision ("We designed MICS to meet these
requirements by separating local execution from centralized definition and coordination"). A reader
who knows Autopilot reads that as claiming its architecture. **Rewrite as inheritance**: MICS adopts
Autopilot's distributed local-execution model and builds a definition/validation/provenance layer
above it. Nothing is lost — the paper's contribution was never the transport.

### C2 — Hardware abstraction and hardware-agnostic task logic ◐

**Autopilot:** already has the abstraction. `Hardware` base classes, devices declared in a task's
`HARDWARE` dict by logical group/id, bound to pins in `prefs.json`, resolved through a plugin
registry. A task written against `'PORTS'/'L'` already runs on a differently-wired rig.

**MICS:** the same class hierarchy (95 % of `gpio.py` intact), plus semantic names, per-channel
detector keys, and — the real change — **where the code and config live**: versioned rows in
Postgres, AST-validated, shipped per run, backend authoritative over `prefs`.

**Consequence.** "MICS represents devices as modules that expose abstract task-level commands" is
true of Autopilot too. The defensible claim is one level up: **not that hardware is abstracted, but
that hardware code and configuration are versioned, validated, centrally managed artifacts bound to
the run that used them.** Autopilot has abstraction without management; that is the gap MICS fills.

### C3 — Task logic as an explicit, inspectable finite state machine ✅

**Autopilot:** a task is a Python class — `STAGE_NAMES`, stage methods, `self.stages =
itertools.cycle(stage_list)`. Control flow lives inside Python. Nothing outside the file can
inspect, validate, diff, render or edit it; changing it means editing on the Pi and restarting.

**MICS:** the Blueprint is data. States, transitions, nested AND/OR condition trees, in-state `if`
branching, entry-action lists — stored, validated backend-side, rendered on a canvas, hot-reloaded
via `UPDATE_FDA` into a running task, and checked for transition determinism at build time.

**Consequence. This is MICS's strongest claim against Autopilot and it is clean.** Push it: the
difference is not "we also use state machines" (Bpod does) but *the task specification is a
first-class artifact that other layers can reason about* — which is what makes preflight, the visual
editor, versioning and hot-reload possible at all. Do note the honest trade-off (`14` §2.2):
Autopilot's Python tasks are unboundedly expressive; MICS's vocabulary is bounded by design, and the
escape hatches were deliberately rejected to preserve versioning and logging.

### C4 — One representation persisting across design, execution and data ◐

**Autopilot is not a blank slate here.** `PARAMS` is rendered as the Terminal's parameter form;
`TrialData` declares the data schema the trial table is built from; `History_Table` records every
protocol, parameter and step change with a timestamp. That is a genuine design→execution→data
thread, and a provenance mechanism.

**MICS:** the thread is wider and machine-checked — spec in Postgres, preflight before dispatch,
versioned libraries bound to runs, and an event stream where **every single event carries `run_id`
and `session_progress_index`**.

**Consequence.** Do not claim the *idea*; claim the *coverage and enforcement*. Autopilot's thread
covers parameters and declared columns and is enforced by convention. MICS's covers task logic,
hardware configuration, driver code versions and computations, and is enforced by validation that
blocks dispatch. Acknowledging `History_Table` in one clause costs nothing and inoculates the claim.

### C5 — Adaptive progression: performance-based, branching ❌

**Autopilot:** `Subject.assign_protocol(protocol, step_n)`, `graduate()` advancing the step, and two
graduation criteria — `NTrials` **and `Accuracy`** (rolling window, `threshold=0.75, window=500`,
`tasks/graduation.py:40-95`) — with every change written to `History_Table`.

**MICS:** `graduation_type` is evaluated at `api/main.py:1747` and **only `"NTrials"` is handled.**

**Consequence.** This is the one cell where MICS is behind its own foundation, and the cause is
structural: `Accuracy.update(row)` consumes trial rows, and MICS removed the trial-row path. **Drop
the claim.** Table 1 currently gives MICS "adaptive progression" and Autopilot "Partial" — the
reverse of the truth on this specific axis. What is safely claimable: progression is evaluated and
stored **per subject** in a queryable relational model, with explicit `new`/`resume`/`restart` run
modes; and MICS is strongly adaptive **within** a session (compute ops, variables, nested
conditions) where Autopilot's adaptivity is across sessions.

### C6 — Automatic, comprehensive event logging ✅

**Autopilot:** there is **no automatic hardware instrumentation** — a search of the 0.4.4 source for
`auto_log` / `log_action` returns nothing. You get Python debug logging, plus exactly the trial
columns the task author declared in `TrialData`. A question nobody anticipated is unanswerable, and
the raw hardware history does not exist.

**MICS:** `@auto_log` / `@log_action` instrument the driver methods themselves
(`utils/logging_utils.py:14,24`), so hardware actuations, tracker sets and state transitions are
recorded **without the author specifying anything**, each stamped with pilot, subject, session,
`run_id`, `task_type`, `session_progress_index` and cohort.

**Consequence. This is the cleanest functional novelty in the paper and it is trivially checkable.**
The draft states it ("Rather than requiring manual specification of what to record…") but does not
realise how sharp the contrast is — lead with it. State the trade-off honestly too (`14` §2.5):
MICS has **no trial table**; trials are reconstructed post hoc, which is a real cost Autopilot does
not pay.

### C7 — Relational metadata and validation before dispatch ✅

**Autopilot:** metadata is a per-subject HDF5 file. There is no relational model — no projects, no
cohorts, no researchers, no cross-subject query. And there is **no pre-run validation at all**:
`Terminal.toggle_start()` sends the task; the source's own comment says a "coherence checking
ritual" is a TODO.

**MICS:** 27 Postgres tables, and preflight with nine issue kinds today
(`toolkit_dispatch.py:153-163`), 11+ post-18/26 — including static analysis of the task graph: *a
transition reading a variable nothing upstream writes*, and *a state whose every exit is blocked by
a frozen variable*, i.e. a provable deadlock, caught before the animal is in the box.

**Consequence. The second clean win, and the most practically persuasive to an experimentalist.**
Frame it as the difference between finding a mis-specified task at 3 a.m. and being blocked at 5
p.m. Two corrections carry over from `13`: the *subject*-compatibility half of this claim does not
exist (no implant field, no subject check), and preflight is badly undersold at one clause.

### C8 — Multi-scale timing; hardware *and* network closed loop ◐

**This is the claim most at risk of being read as overstated, because Autopilot already does part
of it.**

**Autopilot has a networked closed loop.** The `Transformer` child (`tasks/children.py:179`) runs a
`transform` pipeline on a separate node — camera → pose → condition — and returns a **`TRIGGER`** to
the sender when the condition changes, or **streams** results continuously. Autopilot also has
`transform/` (9 modules) for real-time processing **on the Pi itself**, in-process, with no network
hop — a capability MICS does not have at all.

**Autopilot has no clock synchronisation.** No NTP, no tick alignment, nothing (searched 0.4.4).

**MICS adds:** generality — `sub_connect` lets the Pi dial *out* to a **foreign** publisher that
knows nothing about MICS, with the format adapter (`@decoder`) living in a versioned lab library;
typed signals; liveness split from staleness; a readiness gate; device leases. Plus
`pigpio.pi(sync_ticks=True)` for within-station tick alignment, and (Phase 27) `(ts_pi_recv,
oe_sample)` pairs for post-hoc co-registration.

**Consequence.** Do **not** imply that external computation influencing task flow over a network is
new — Autopilot shipped that in 2022. Claim the right thing: *any* external system can drive task
logic **without adopting MICS's protocol**, because the adapter is a versioned artifact a researcher
can author; and the resulting value is indistinguishable from a GPIO pin at the read site
(`view.get_value(...)`). Also note the architectural cost honestly: MICS's answer to "process a
video frame" is another computer, where Autopilot would do it in-process. And the global-clock
sentence must go regardless (`13` §3.1) — MICS's sync is within-station and the NTP calls are
commented out.

### C9 — Fault tolerance and run-state modes ◐

**Autopilot:** the pilot keeps executing if the Terminal drops (inherited, C1). `Subject` persists
protocol step and session number, so a run can be picked up manually. But there are no explicit run
modes, no fault events in a queryable stream, and no health surface.

**MICS:** explicit `new` / `resume` / `restart`, persisted `run_progress`, faults recorded as events
in the same stream as behaviour, and (Phase 19) a device-health badge that changes mid-run without a
page reload.

**Consequence.** A fair but **incremental** claim — say "explicit and recorded" rather than implying
Autopilot loses everything on interruption. The genuinely new part is that a *fault is a
first-class, queryable record* on the same timeline as behaviour.

### C10 — Virtual MICS / digital twin —

**Autopilot:** nothing comparable.

**MICS:** an Unreal OSC environment reachable only from the **legacy hardcoded task**; the
backend-authored Blueprint path has no UNREAL group and no phase reconnects it.

**Consequence.** Autopilot provides no cover here. The claim stands or falls on MICS's own evidence,
and as written ("the same Blueprint used in live experiments executes in this environment") it does
not hold. See `13` §3.4 — decide, don't reword.

### C11 — Scaling across stations under one infrastructure ⊘

**Autopilot:** many Pilots and Children coordinated by one Terminal is the framework's design.

**MICS:** same architecture, same code. What is MICS's: one relational + event store across all
rigs, browser-based concurrent access, and **device leases** arbitrating a shared instrument between
rigs — which Autopilot has no notion of.

**Consequence.** "Multiple MICS-Core units can operate in parallel while sharing the same monitoring
and data infrastructure" describes Autopilot equally. Move the claim to **the shared data and
management layer, and to resource arbitration**. Also cut "user identity" — it isn't there (`13`
§3.5).

### C12 — One architecture across very different paradigms ⊘

**Autopilot:** built and published for exactly this — freely-moving and head-fixed, operant and
psychophysics, with a plugin ecosystem.

**MICS:** the two-paradigm demonstration is real and worth reporting as evidence for MICS. But
*versatility itself* is not a differentiator against Autopilot.

**Consequence.** Report the demonstration as evidence that the **abstraction stack** survives a
paradigm change (new hardware, no redesign of logging/sync/monitoring) — not as evidence that MICS
is uniquely versatile.

### C13 — Integration with neural recording, imaging, optogenetics, tracking ✅

**Autopilot:** TTL out through GPIO, camera classes, transforms, `Transformer` children. It can
**synchronise with** an acquisition system. It cannot **control** one, does not know where the
recording landed, and takes no neural data back into the task.

**MICS (post 26/27):** drives Open Ephys IDLE→RECORD itself; composes the save folder from run
context so two rigs' data can never merge; writes labelled markers into the recording as ordinary
actions; **persists the recording path back into the database**; stops an orphaned recording via a
backend safety net when a Pi crashes; and ingests windowed firing rate as an ordinary view key a
transition can gate on.

**Consequence. The third clean win, and the most compelling to the target reader.** The one-line
framing: *Autopilot synchronises with your acquisition system; MICS operates it, labels it, records
where its data went, and can read from it.* Everything here is unexecuted roadmap — it needs rig
proof before it appears in the present tense (`13` §2.2–2.3).

### C14 — Table 1 ✅ needs rewriting

Three specific defects, all Autopilot-related:

1. **Autopilot is the foundation and appears as a peer.** Disclose it in the caption (`14` §4).
2. **MICS is credited with "adaptive progression"** it does not have and Autopilot does (C5).
   Reverse or remove.
3. **Autopilot's row understates it** on the axes where it is genuinely strong — "Partial"
   autonomous training and "Moderate" neural integration undersell a framework with a plugin
   registry, on-Pi real-time transforms and networked closed-loop children. Understating your own
   dependency reads worse than understating a competitor.

Consider replacing the "Modular / distributed architecture" column with something that actually
separates MICS from Autopilot — e.g. *"task specification is a validated, versioned artifact"* or
*"automatic event-level provenance"* — since on modularity and distribution the two are the same
system.

---

## What to do with this

**Lead with C3, C6, C7, C13.** Four claims that are clean, checkable, and land squarely on what an
experimentalist feels: *the task is an artifact you can inspect and edit; everything is recorded
without you asking; a bad specification is blocked before the animal is in the box; and the
acquisition system is operated rather than merely synchronised with.*

**Reframe C2, C4, C8, C9** one level up — from the capability to the **management, coverage and
enforcement** of it.

**Attribute C1, C11, C12** to Autopilot and stop presenting them as MICS design decisions. They cost
nothing to give away and their retention is the fastest way to lose a reviewer's trust in
everything else.

**Drop C5.** And fix Table 1.
