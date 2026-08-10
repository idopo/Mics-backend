# 12 — Paper vs. live implementation (GSD phase audit)

**Checked 2026-08-05** against the lab server (`mics-server`, `~/mics-backend` branch `claude`,
commit `cb25e8a`) and `~/pi-mirror`. Paper draft:
`MICS_ a Modular and Scalable Closed-Loop Experimental Control.docx`.

Sources read: `.planning/ROADMAP.md`, `.planning/STATE.md`, `.planning/REQUIREMENTS.md`,
`.planning/phases/*`, `CLAUDE.md`, `api/models.py`, `api/main.py`,
`api/routers/toolkit_dispatch.py`, `web_ui/react-src/src/types/index.ts`,
`web_ui/react-src/src/pages/index/Index.tsx`,
`~/pi-mirror/autopilot/autopilot/core/pilot.py`,
`~/pi-mirror/autopilot/autopilot/data_handlers/ElasticSearchDataHandler.py`,
`~/pi-mirror/autopilot/autopilot/hardware/unreal.py`, `~/pi-mirror/autopilot/setup.py`.

---

## 1. The phases, one line each

Milestone M1 — "ToolKit + FDA Redesign + Pi Code Editor + Hardware Centralization".
22 live phases, 7 complete, 72% of plans done. **Phases 20–22 do not exist** (renumbered into 23).

| # | Phase | One-line description | Status |
|---|---|---|---|
| 1 | Pi Foundation | Pi loads a whole state machine from JSON (`load_fda_from_json`) instead of hardcoded Python; `validate_fda.py` CLI. | ▣ Archived (superseded by 9–17) |
| 2 | DB + API | Toolkit metadata captured from the Pi HANDSHAKE; task definitions created/edited/pushed over REST; `UPDATE_FDA` hot-reload. | ▣ Archived |
| 3 | Visual FDA Editor | Browser canvas (react-flow) for building states/transitions without writing Python. | ▣ Archived |
| 4 | Protocol Integration | Protocol steps point at task definitions, so FDA JSON flows DB → orchestrator → Pi. | ▣ Archived |
| 5–8 | Pi Code Editor arc | Monaco viewer, browser terminal, edit+restart, package sync — browse/edit Pi source without SSH. | ◌ Deferred, never started |
| 9 | HardwareLib Storage | Hardware driver files (e.g. `gpio.py`) stored+AST-validated in the DB and shipped to the Pi at task start. | ✓ Complete |
| 10 | Hardware Modules + Pilot Config | Named hardware modules in the DB, per-pilot pin/param bindings, `prefs.json` migrated in via HANDSHAKE. | ✓ Complete |
| 11 | Toolkit Redesign | Toolkits become backend-authored: assembled in the UI from locked states + hardware modules + flags + params. | ✓ Complete |
| 12 | Hardware-Aware FDA Builder | Editor offers module → method → typed args from the lib AST; flags task definitions broken by a lib change. | ✓ Complete |
| 13 | Pre-Run Cross-Check | Before START, the backend verifies the chosen pilot actually has every required hardware module configured. | ✓ Complete |
| 14 | Bug Backlog | Batched small fixes: hw-lib warning badges, toolkit-creation modal UX. | ✓ Complete |
| 15 | Compound Transition Conditions | Transitions can carry AND/OR condition groups (flat DNF) instead of one condition. | ✓ Complete |
| 16 | Recursive Condition Tree | Replaces flat DNF with arbitrarily nested AND/OR (Kibana-style builder) + Pi recursive evaluator. | ✓ Complete |
| 17 | Free-Form Pilot Hardware Config | Per-pilot hardware config becomes a free-form name-keyed dict mirroring `prefs.json`; preflight is the only alignment check. | ✓ Complete |
| 18 | **MICS-Link — Pi Transport + ExternalHardware** | The general substrate for external software/instruments to push data into the FDA: two transport roles (`router_bind`/`sub_connect`), per-lib `@decoder`, `ExternalHardware` base class, liveness split from staleness, egress queue, run lifecycle hooks, backend device lease. | ○ **Planned, not executed.** 12 plans, re-verified 2026-08-05 |
| 19 | Per-Pilot Device Health Surface | An external device going unreachable mid-run lights a warning on the pilot card while the session is still running. | ○ Pending, 0 plans |
| 23 | Compute Operations + Variables | Researcher can compute a value in a state, store it in a variable and transition on it; compute ops are versioned, user-extensible libs, every call logged. | ✓ Complete (10/12 plans; 11–12 added 2026-08-05) |
| 24 | Trigger Assignment Action Lists | A hardware trigger runs the same action vocabulary as a state's entry actions, assigned from the UI instead of hardcoded in Python. | ✓ Complete, rig-proven |
| 25 | Detector-Derived View Keys | Per-electrode keys (`LICKER0…3`) derived by the backend and pickable in the FDA editor; resolved per-pilot at preflight. | ◐ 5/6 plans (rig proof outstanding) |
| 26 | OpenEphys Device Control | MICS starts/stops the OE recording itself, names the save folder per subject/session, writes labelled markers, records the path back. Control only. | ○ Planned (13 plans), blocked on 18 |
| 27 | OpenEphys Firing Rate over ZMQ | Pi subscribes to the OE ZMQ plugin, decodes spikes in a versioned lib, maintains a windowed rate as an ordinary view key. | ○ Pending, 0 plans |
| 28 | TTL vs Network Sync Validation | Run TTL and network markers into one recording and quantify offset/jitter. Evidence only — **no cutover**. | ○ Pending, 0 plans |

Execution order: 24 → 25 → 23 → review → 18 → 26 → 27 → 28.

---

## 2. Inconsistencies with the paper draft

Ordered by how much trouble each would cause at review.

### 2.1 Autopilot is not credited as the foundation — it is listed as a competitor

`~/pi-mirror/autopilot/` is the **wehr-lab Autopilot package** (`setup.py:69` `name="auto-pi-lot"`,
`author="Jonny Saunders"`, MPL-2.0), extended with MICS task/hardware modules. The Core imports it
directly (`from autopilot.hardware import Hardware`, `autopilot/core/pilot.py`).

The draft puts Autopilot in Table 1 as a comparison system and in the Discussion as a parallel
approach ("frameworks such as Autopilot and behaviorMate emphasize modular and distributed
integration"), and nowhere states that MICS-Core is built on it. Add an explicit statement in
Results/Methods, cite the Autopilot paper, and honour the MPL-2.0 notice in the code release.
(Autopilot is also absent from `POSTER_KNOWLEDGE_BASE.md` and `analysis/FINDINGS.md` — this is a
project-wide omission, not just the manuscript's.)

### 2.2 Network-mediated external input is described as existing; it is Phase 18, not built

Draft: "MICS supports both hardware-level synchronization signals and network-mediated
communication… These signals can be incorporated into Blueprint logic as closed-loop triggers"
(Results, Adaptive Multi-Scale Timing), echoed in the Discussion.

Implementation: hardware-level (GPIO/TTL) input is real. The network path is **Phase 18
(MICS-Link)** — 12 plans, plan-checker passed 2026-08-05, **not executed**. Its first consumers
(26 OpenEphys control, 27 firing rate over ZMQ) are pending, 27/28 have no plans at all. Write
this in the future/planned voice, or restrict the claim to the TTL path.

Also in that paragraph: a bare URL is left in the sentence — "…such as pose estimation, and
https://www.nature.com/articles/s41467-025-64856-3".

### 2.3 The global clock claim overstates what runs

Draft: "Periodic synchronization with a global reference enables alignment of events across
experimental stations and external systems onto a unified experimental timeline."

Implementation (`autopilot/core/pilot.py:1134-1150`): the active mechanism is
`pigpio.pi(sync_ticks=True)` + `self.pi.synchronize()` — aligning the microsecond tick counter to
the Pi's own system clock, i.e. **within-station**. `enable_ntp_and_wait()` / `disable_ntp()` exist
but **both calls are commented out**. There is no periodic global re-sync in the run path, and
Phase 28 exists precisely to measure whether network alignment is good enough to replace the TTL
cable. "Fig. X" for timing quantification is that unstarted phase.

### 2.4 Event context: no experiment name in the event log

> **CORRECTED 2026-08-06 — the `run_id` half of this finding was wrong.** It was written from the
> historical `restored-*` indices. The *current* envelope does carry `run_id`. Verified live on the
> rig cluster `132.77.73.217`: `event_log_v2`'s mapped top-level fields are `continuous, event,
> pilot, run_id, session, session_progress_index, subject, subjects, task_type, timestamp`, and the
> newest document carries `run_id: 551`. Written by
> `~/pi-mirror/autopilot/autopilot/networking/Event_Dispatcher.py:38-48`, sourced from
> `autopilot/tasks/task.py:132,138`. See `13_MANUSCRIPT_CLAIMS_AUDIT.md` §4.7.

Draft: "each event is indexed with its associated experimental context, including the Core unit,
subject identity, experiment name, and run ID."

The run ID claim is correct for current data. What is genuinely absent is the **experiment name**.
The envelope also carries two fields the draft does not claim: `session_progress_index` (the
trajectory step position, stamped on every event) and `subjects` (the cohort).

**The analysis caveat stands, and matters for Methods.** The analysed corpus —
`restored-event_log_v2` on `132.77.73.125` — predates this: its mapping is only `continuous, event,
pilot, session, subject, task_type, timestamp`, with **no `run_id`**. For that data, run context is
still recovered by joining on subject + task type + time window
(`03_POSTGRES_TO_ES_JOIN.md`, `04_ES_SCHEMA.md`). So the paper's behavioral figures come from data
that lacks the identifier the Methods will describe — name the index per figure.

Related, for Methods/data availability: the Pi's live ES handler points at
**132.77.73.217** (`ElasticSearchDataHandler.py:13`, the dev host), while the analysed corpus is
the `restored-*` indices on **132.77.73.125**.

### 2.5 Subject-compatibility checking is not implemented

Draft: "The Portal then verifies that this specification is compatible with the assigned system and
subjects", and "Subject compatibility is evaluated based on attributes stored in the database, such
as implant type or genetic indicators".

Preflight validates hardware and FDA references only — `PREFLIGHT_ISSUE_KINDS`
(`api/routers/toolkit_dispatch.py:153-163`) is `missing`, `incomplete_config`, `class_mismatch`,
`fda_ref_unresolved`, `view_key_unresolved`, `variable_never_written`, `lib_version_unresolved`,
`compute_lib_import_failed`, `state_wait_unsatisfiable`. No subject-attribute check exists, and
`grep -i implant` over `api/`, the React source and the roadmap returns **nothing**. `Subject`
(`api/models.py:30-63`) does hold strain, genotype, sex, dob, rfid — so "genetic indicators" is
storable but not *checked*. Drop the implant example and say attributes are recorded, or move the
whole claim to future work.

### 2.6 Trajectory adaptivity is stronger in the text than in the code

Draft: progression criteria "evaluated individually for each subject, allowing progression to depend
on performance or behavioral patterns rather than follow a fixed sequence… trajectories can branch
or adapt dynamically". Table 1 lists MICS as "adaptive progression".

Implementation: `run_progress.graduation_type` is checked at `api/main.py:1747` and the only
evaluated type is **`NTrials`** — a trial count, incremented by an explicit `INC_TRIAL_COUNTER` from
the task. No accuracy/performance criterion, no branching. Per-subject *progress* is genuinely
independent (each subject carries its own `current_step`), so "evaluated individually per subject"
is fair; "depend on performance" and "branch" are not yet true.

### 2.7 Portal overview: no user identity on the pilot grid

Draft: "a real-time overview of all connected Cores, including their current usage, user identity,
and experiment duration".

`PilotLive` is exactly `{connected, state, active_run, updated_at}` (`types/index.ts:1`) and the card
renders session, subject, elapsed time and a STOP button (`pages/index/Index.tsx`). Researchers exist
as a table and as `Subject.lead_researcher_id`, but no user identity reaches the pilot grid. Cut
"user identity" or say who *owns the subject* rather than who is using the Core.

### 2.8 Virtual MICS is narrower than described

What exists: `autopilot/hardware/unreal.py` — OSC-based `LED`, `DOOR`, `AIR_PUFF` classes talking to
an Unreal OSC server — driven by the legacy hardcoded task `mics_cage_task.py` (`group_name =
'UNREAL'`). Backend-authored toolkits explicitly have **no UNREAL group at all**
(`24-CONTEXT.md:213`), so the claim that "the same Blueprint used in live experiments executes in
this environment" does not hold for the current backend-authored FDA path. I also found no code
generating mock event streams for downstream pipelines — confirm with whoever owns the Unreal side
before that sentence stays.

### 2.9 Terminology: the paper's names and the system's names disagree

| Paper | System | Note |
|---|---|---|
| Blueprint | task definition / FDA (`fda_json`) | **`Blueprint` is already taken** in the code — it means a session spanning pilots (`api/main.py:851, 920, 1316`). Two meanings in one project. |
| Trajectory | protocol (`protocol_templates` + steps + graduation) | "Trajectory" appears nowhere in the code, and the poster says "Protocols & graduation". |
| MICS-Core | pilot | consistent enough |
| MICS-Portal | three services: `api`, `orchestrator`, `web_ui` | the Portal is a UI over a stack, not one component |
| "Modular Interactive Control System" | "Mice Interactive Cage System" (`.planning/PROJECT.md:5`) | pick one expansion and fix the other |

Renaming for the paper is legitimate — but decide it deliberately, and either add a glossary mapping
or rename in the repo, or the software release and the paper will read as two systems.

---

## 3. What checks out

- Local FSM execution on the Pi, hardware evaluated in the same loop — yes.
- Hardware abstraction as modules with task-level commands, hardware-agnostic task logic — yes,
  phases 9→13 + 17 (`hardware_libs` → `hardware_modules` → `pilot_hardware_config` → dispatch).
- Portal verifies hardware compatibility before dispatch — yes, Phase 13 preflight.
- Autonomous local execution independent of the network once started — yes.
- Automatic logging of hardware activity, state transitions and system events, no manual
  specification — yes; ES + Kibana as described.
- Relational store of task specs, hardware configs, params, flags and subject attributes — yes.
- **Run-state modes `new` / `resume` / `restart`** — implemented exactly as described
  (`api/models.py:584`, `api/main.py:1264,1279`).
- Persisted stage/step position enabling resume without losing context — yes (`run_progress`).
- Parallel Cores under one monitoring and data infrastructure — yes.
- Modifying contingencies at state level (generalization by reassigning cues, extinction by changing
  the outcome state) — supported by the FDA model, and matching task plugins exist
  (`Genralization.py`, `ExtinctionAUDIO.py`, `ExtinctionLED.py`).

## 4. Editorial odds and ends

- Table numbering: the Introduction cites "Table 1", the table is headed "Table X … (in progress)",
  its caption says "Table X", and a second stub "Table 6: Comparing mics with other systems" sits
  further down. Same for the timing figure — "Fig. X" in the text, "Figure 4B" in the figure list.
- Typo: "internal flags represent discrete values **unpated** during execution" → "updated".
- Table 1, MICS row: "Flexible task design across paradigms **and species**" — only mice are shown.
