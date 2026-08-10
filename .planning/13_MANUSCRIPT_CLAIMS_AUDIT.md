# 13 — Manuscript claims audit: the draft vs. MICS with the roadmap complete

**Written 2026-08-06.** Draft audited: `MICS_ a Modular and Scalable Closed-Loop Experimental
Control.docx`. System state read live from the lab server (`mics-server`, `~/mics-backend`
branch `claude`, HEAD `f6aabd5`; `~/pi-mirror`), plus the live rig Elasticsearch cluster at
`132.77.73.217`.

**The assumption behind this document, stated once.** You asked me to compare the draft against
MICS *as it will be once every phase Ido planned is implemented* — i.e. phases 18, 19, 26, 27 and
28 landed, and 25 and 29 closed out. That is not today's system. Phases 18/19/26 are planned but
unexecuted; **27 and 28 have zero plans**, and 27 carries an unresolved external prerequisite (what
the Open Ephys ZMQ plugin actually publishes — sorted spikes or a computed rate — must be checked
on the rig before it can even be planned). So: everything in §2 below is what the paper *will be
able to say*, and each item needs its rig proof before it appears in a Results section in the
present tense. Everything in §3 and §4 is true regardless of the roadmap — those are the items
that will still be wrong on submission day if nobody changes them.

Sources read for this audit are listed in §7.

---

## 1. The major claims

These are the load-bearing claims — the ones the paper's novelty rests on. Everything downstream
is organised against them.

| | Claim | Where |
|---|---|---|
| **C1** | Local autonomous execution on the Core, separated from central definition/monitoring; execution does not depend on the network | Abstract, Results §1 |
| **C2** | Hardware abstraction: devices are modules exposing task-level commands; task logic is hardware-agnostic and portable across setups | Results §1–2 |
| **C3** | Task logic is an explicit, inspectable finite state machine ("Blueprint"); contingencies are edited at the state level, not rewritten in code | Results §2, Discussion |
| **C4** | **The key contribution**: three parallel abstractions (hardware / task logic / progression) unified into one executable specification that *persists across design, execution and data* | Results §2, Discussion |
| **C5** | Adaptive progression: "Trajectories" evaluate criteria per subject, can depend on performance, and can **branch or adapt dynamically** | Results §2, Table 1 |
| **C6** | Automatic comprehensive event logging; every event carries its experimental context (Core, subject, experiment name, run ID); ES + Kibana | Results §3 |
| **C7** | Relational metadata store, and pre-dispatch validation of the specification against **both the station and the subject** (implant type, genetic indicators) | Results §3 |
| **C8** | Multi-scale timing: local ms control, **hardware *and* network-mediated** external triggers as closed-loop inputs, delegation of high-frequency stimulation with MICS gating, and **periodic sync to a global reference** onto a unified timeline | Results §4 |
| **C9** | Fault tolerance: autonomous continuation, faults logged as events, three run-state modes (new/resume/restart), resume without loss of task context | Results §5 |
| **C10** | Virtual MICS: an Unreal digital twin in which **the same Blueprint executes**, plus mock event streams for building analysis pipelines pre-data | Results §6 |
| **C11** | Scaling: parallel Cores under one data infrastructure; Portal overview showing usage, **user identity**, and duration | Discussion |
| **C12** | Demonstrated across two very different paradigms with no redesign of logging/sync/monitoring | Results §7 |
| **C13** | Integrates with ephys, imaging, optogenetics, video tracking; closed loops in which neural activity and behavior influence one another | Abstract, Intro |
| **C14** | Table 1 positioning: MICS uniquely combines autonomous training + modularity + neural integration + adaptive progression | Table 1 |

---

## 2. Claims the completed roadmap makes true — and makes *stronger* than written

The draft was written against a thinner system. In this section the direction of the gap is
mostly the opposite of what you'd expect: the text is vaguer and weaker than what the finished
system does. These are rewrite opportunities, not corrections.

### 2.1 Network-mediated external input (C8, C13) — Phase 18, "MICS-Link"

**Draft:** "MICS supports both hardware-level synchronization signals and network-mediated
communication… These signals can be incorporated into Blueprint logic as closed-loop triggers."

**Today:** only the hardware path (GPIO/TTL) exists. **After Phase 18** the network path exists,
and it is considerably more specific and more defensible than that sentence. Five design choices
worth putting in the paper, in experimentalist terms:

- **An external computation becomes an ordinary sensor.** An external signal registers as a View
  Tracker named `<source_id>.<signal>` and is read by the *same* call as a GPIO pin:
  `view.get_value("dlc_cam1.left_paw_x")`. Zero new call sites in task logic. This is the single
  cleanest sentence available for C4 — "whether a value comes from a beam-break, a random draw, a
  pose estimate or a firing rate, the task reads it the same way."
- **Two transport roles, so the other software doesn't have to change.** `router_bind` — a
  MICS-native client dials into the Pi. `sub_connect` — the Pi dials *out* to a foreign publisher
  (this is how Open Ephys works). A third role, `none`, covers control-only devices with no
  inbound data at all. Most integration claims in this literature quietly assume the other system
  will speak your protocol; MICS does not.
- **The adapter for a foreign format lives in a versioned lab library, not in platform code.**
  A per-library `@decoder` hook translates a third-party frame into declared signals. So when a
  vendor changes their wire format, a researcher fixes it in their own library and promotes a new
  version — no platform release, no waiting for a developer. This is a claim about *who can
  extend the system*, and it is the strongest form of the modularity argument (C2).
- **"Reachable" is separated from "fresh".** `<source_id>.alive` means the device is up;
  per-signal staleness governs whether its last value is still meaningful. For an experimentalist
  this is the difference between *the ephys rig died at 2 a.m.* and *the mouse simply isn't
  licking* — a single "is it working" flag conflates the two and is useless overnight.
- **A readiness gate before trial 1.** When a run needs an external device, MICS injects a
  synthetic pre-state and does not enter the researcher's first state until every required device
  reports *ready* (not merely reachable). Three guaranteed escapes: timeout, operator skip, STOP.
  Plainly: **no more sessions that ran beautifully and recorded nothing.**
- **A device lease.** One physical box = one lease, keyed on the normalized host. A second run
  targeting a held device is hard-blocked at preflight with the holder named (pilot, subject, run,
  since when). For a shared ephys or 2P rig serving several cages, this is what stops two
  experiments colliding at 3 a.m.

### 2.2 MICS drives the acquisition system (C13) — Phase 26

Absent from the draft entirely, and probably the most immediately compelling capability for the
target reader. After Phase 26:

- MICS takes Open Ephys from IDLE to RECORD itself at run start and back to IDLE at run end. The
  researcher never touches the OE GUI.
- The save folder is composed from run context (subject, session, run, pilot, timestamp), and is
  required to be unambiguous across rigs — **two pilots' data can never land in one folder**.
- Labelled markers (`cue_on`, `reward`) are written into the recording from a state entry action
  *or* a hardware trigger, dispatched as an ordinary action — no new concept in the editor.
- **The resolved recording path is written back into the MICS database and readable through the
  API.** Nobody transcribes a path by hand; post-hoc tooling asks the system where its own ephys
  data went.
- If the Pi crashes, a backend safety net stops the orphaned recording and releases the lease.

That set is a provenance story the draft's Discussion paragraph on provenance currently doesn't
tell, and it is concrete where that paragraph is abstract.

**One design-choice paragraph worth writing explicitly**, because reviewers of a methods paper
reward stated rationale: marker sends are **fire-and-forget with no retry**, FIFO-ordered per
device, on a bounded queue that drops the *newest* and records the loss as an event. The reason is
scientific, not engineering: a retried marker arrives with the wrong timestamp, and for alignment a
late marker is strictly worse than a missing one — it silently corrupts co-registration instead of
leaving a visible gap.

### 2.3 Closed loop on neural activity (C13, Intro) — Phase 27

The Introduction promises "closed-loop interactions in which neural activity and behavior
dynamically influence one another." The Results demonstrate a *behavior→optogenetics* loop only.
After Phase 27 the neural→task direction becomes real: the Pi subscribes to the OE ZMQ plugin,
decodes spikes inside the versioned library's `@decoder`, maintains a windowed rate per unit, and
exposes it as an ordinary view key (`oe.unit_A001_1.rate`) that a transition can gate on.

Caveats to state rather than gloss:
- Units of interest and the rate window are **declared in the pilot's configuration, not
  discovered at runtime** — sorted unit IDs only exist if sorting is configured upstream in OE.
- Rate estimation runs on a periodic callback, never per-spike on the task thread.
- **Raw continuous data at 30 kHz is explicitly out of scope** and rejected by design. Say so; it
  pre-empts the obvious reviewer question about bandwidth.
- The external prerequisite is still open: it must be confirmed on the rig whether the plugin
  publishes sorted spikes or an already-computed rate. The two lead to materially different
  designs.

### 2.4 The timing figure (C8, "Fig. X") — Phase 28

"Quantitative measurements of timing precision across these pathways are presented in Fig. X" is
Phase 28, which has no plans yet. Two things the paper must get right about it:

- It is **evidence, not a cutover**. The TTL cable stays in place; both paths run into one
  recording so they are compared within a single clock rather than across sessions. Any decision
  to remove the cable is later and separate.
- Report a **distribution of offset and jitter over a real session, not a single number**, and
  state plainly whether network-only alignment meets the tolerance of the experiments actually
  being run.

Phase 27 also supplies the other half of the temporal story: `(ts_pi_recv, oe_sample_number)`
pairs logged at a steady cadence for the whole run, sufficient to fit clock drift post hoc. That
is *software co-registration*, and it is the honest mechanism behind the paper's "unified temporal
reference" — see §3.1, where the draft names a mechanism that does not run.

### 2.5 Fault tolerance gets its missing half (C9) — Phase 19

Today a device failure is *recorded*; it is not *surfaced*. After Phase 19, any `<device>.alive`
flip lights a warning on the pilot card **while the session is still running**, without a page
reload. Two properties worth a clause each: it is keyed on the `.alive` name suffix rather than on
a device class, so a second kind of device lights the same indicator with no further work; and it
**never auto-aborts** — the task author gates on liveness if the experiment requires it. That is a
deliberate choice (an automatic abort on a transient network blip would end a night of training)
and it belongs in the Fault-Tolerant Operation section.

---

## 3. Claims that stay wrong after every planned phase lands

Nothing in phases 18–29 touches any of these. If they aren't changed, they are wrong at
submission.

### 3.1 "Periodic synchronization with a global reference" — not running

**Draft (C8):** "Periodic synchronization with a global reference enables alignment of events
across experimental stations and external systems onto a unified experimental timeline."

**What runs** (`~/pi-mirror/autopilot/autopilot/core/pilot.py:1139,1145`):
`pigpio.pi(sync_ticks=True)` followed by `self.pi.synchronize()`. That aligns the microsecond tick
counter to the Pi's *own* system clock — **within-station**. `enable_ntp_and_wait()` and
`disable_ntp()` exist at `:498` and `:514`, and **both call sites are commented out** (`:1138`,
`:1148`). There is no periodic global re-sync anywhere in the run path, and no phase adds one.

**The fix is not to weaken the claim — it is to describe the two mechanisms you actually have**,
both defensible: (i) a shared hardware TTL line, which is why Phase 28 exists to measure against
it; and (ii) post-Phase-27 software co-registration by logging Pi-receive timestamps against
acquisition sample numbers and fitting drift post hoc. Written that way the paragraph is stronger
and survives a reviewer who knows what NTP on a Raspberry Pi is actually worth.

### 3.2 Trajectories do not branch, and progression is not performance-based

**Draft (C5, and Table 1's "adaptive progression"):** criteria "evaluated individually for each
subject, allowing progression to depend on performance or behavioral patterns rather than follow a
fixed sequence… trajectories can branch or adapt dynamically."

**Implementation:** `run_progress.graduation_type` is evaluated at `api/main.py:1747`, and the
only value handled is **`"NTrials"`** — a trial count incremented by an explicit counter action.
No accuracy criterion, no branching. Nothing in `ROADMAP.md` or `REQUIREMENTS.md` adds one.

What *is* true and is worth claiming instead: **progression is tracked and evaluated per subject**
— each subject carries its own `current_step` and advances on its own schedule, which is precisely
what matters for unsupervised home-cage training and is a real contrast with fixed-schedule
systems.

Note the genuinely interesting nuance, which the draft misses in both directions: **MICS is now
strongly adaptive *within* a session** (compute operations, variables, nested conditions, in-state
branching — §4.2/§4.3) **and count-based *across* sessions**. That is an accurate, specific and
defensible sentence. "Trajectories can branch" should move to future work or be cut, and the
Table 1 cell should be softened accordingly.

### 3.3 Subject-compatibility checking does not exist

**Draft (C7):** "The Portal then verifies that this specification is compatible with the assigned
system and subjects", and "Subject compatibility is evaluated based on attributes stored in the
database, such as implant type or genetic indicators."

**Implementation:** `PREFLIGHT_ISSUE_KINDS` (`api/routers/toolkit_dispatch.py:153-163`) contains
nine kinds, all concerning hardware, FDA references, view keys, variables and library versions.
There is no subject-attribute check of any kind. `Subject` (`api/models.py:30-63`) holds strain,
genotype, sex, dob, rfid, lead researcher, housing — **there is no implant field at all**. No
planned phase adds this.

Fix: say subject attributes are *recorded* and available for assignment and analysis; describe the
automated check as being over hardware, task references and device availability — which, per §4.6,
is far more substantial than the draft currently claims. Drop "implant type" specifically.

### 3.4 Virtual MICS — the gap is widening, not closing

**Draft (C10):** "The same Blueprint used in live experiments executes in this environment", plus
simulated event streams for pre-building analysis pipelines, plus virtual devices ahead of
hardware.

**What exists:** `~/pi-mirror/autopilot/autopilot/hardware/unreal.py` — OSC-based `LED`, `DOOR`,
`ODOR`, `REWARD_VALVE`, `AIR_PUFF`, `AUDIO`, `MOTORIZED_REWARD` and an `OSCSERVER` class talking to
an Unreal server. It is referenced only from the **legacy hardcoded task**
`autopilot/tasks/mics_cage_task.py`. The backend-authored toolkit path — which is where the whole
rest of the system now lives — has no UNREAL group.

So the claim that the same Blueprint executes in the virtual environment does not hold for the
current Blueprint path, **and no phase in the roadmap reconnects it**. Because everything else has
migrated to backend-authored toolkits, the distance between the two grows with each landed phase. I
also found no code generating mock event streams for downstream pipelines (searched `~/pi-mirror`
and `~/mics-backend/api`).

Three options, and this is a decision for whoever owns the Unreal work rather than something to
paper over: (a) demote to a supplementary figure describing the environment honestly as a
hardware-simulation harness for the legacy task path; (b) do the work to run backend-authored FDAs
against simulated hardware; or (c) cut. Reviewers of a methods paper will ask for a demonstration
of a "digital twin", so an unqualified claim here is a liability.

### 3.5 "User identity" is not on the Portal grid

**Draft (C11):** a real-time overview of connected Cores "including their current usage, user
identity, and experiment duration".

`PilotLive` is exactly `{connected, state, active_run, updated_at}`
(`web_ui/react-src/src/types/index.ts:1`); after Phase 19 it gains `device_health`. Never a user.
Researchers exist as a table and as `Subject.lead_researcher_id`, but no user identity reaches the
pilot grid, and no phase adds one. Cut it, or reframe as *who owns the subject* rather than *who is
using the Core*.

### 3.6 Autopilot is the foundation, and the draft lists it as a competitor

**This is the highest-risk item in the manuscript.**

`~/pi-mirror/autopilot/` is the wehr-lab **Autopilot** package — `setup.py:69` `name="auto-pi-lot"`,
`:74` `author="Jonny Saunders"`, `:77` `license="MPL-2.0"` — extended with MICS task and hardware
modules. MICS-Core imports it directly (`from autopilot.hardware import Hardware`). The draft puts
Autopilot in Table 1 as a comparison system and in the Discussion as a parallel approach
("frameworks such as Autopilot and behaviorMate emphasize modular and distributed integration"),
and nowhere states that MICS-Core is built on it.

A reviewer who knows Autopilot will notice. The fix costs little and the resulting story is
perfectly good: MICS is a definition, validation, provenance and integration layer built **on top
of** Autopilot's distributed Pi substrate. State it explicitly in Results/Methods, cite the
Autopilot paper, adjust the Table 1 row (you cannot compare against your own foundation in the same
row-space without saying so), and honour the MPL-2.0 notice in the code release. This is a
project-wide omission, not just the manuscript's — Autopilot is also absent from
`POSTER_KNOWLEDGE_BASE.md` and `analysis/FINDINGS.md`.

### 3.7 Terminology: the paper and the system name things differently

| Paper | System | Note |
|---|---|---|
| Blueprint | task definition / FDA (`fda_json`) | **`Blueprint` is already taken in the code** — it means a session spanning pilots (`api/main.py:920` `launch_session_blueprint`, `:1316`, `:1905`). Two meanings, one project. |
| Trajectory | protocol (`protocol_templates` + steps + graduation) | "Trajectory" appears nowhere in the code |
| MICS-Core | pilot | consistent enough |
| MICS-Portal | three services: `api`, `orchestrator`, `web_ui` | the Portal is a UI over a stack, not one component |
| "**Modular** Interactive Control System" | "**Mice** Interactive Cage System" (`.planning/PROJECT.md:5`) | pick one expansion and fix the other |

Renaming for publication is legitimate. But decide it deliberately and add a three-line glossary in
Methods mapping paper-name → code-name, or the software release and the paper will read as two
different systems.

---

## 4. What the finished system does that the draft never claims

This is the most useful section for the rewrite. The draft undersells MICS in exactly the areas
its target readers — experimentalists and data scientists — care most about.

### 4.1 Device drivers are versioned, promotable, researcher-authored artifacts

`hardware_libs` / `hardware_lib_versions` carry `state: unvalidated | beta | stable`
(`api/models.py:647`), with promotion recorded as `stable_at`, `stable_reason` (`'user'` or
**`'protocol_run'`**) and `stable_pilot` (`:651-653`). Libraries are AST-validated at upload,
pinned per toolkit, and resolved through pin → toolkit default → latest stable → preflight failure.

In plain terms, and this is a *stronger* provenance claim than anything currently in the draft:
**the driver code that ran your experiment is a versioned artifact recorded against the run, and a
driver can earn "stable" by having actually carried a protocol run.** That is the answer to "could
you re-run this experiment in two years", and right now the paper doesn't give it.

### 4.2 Compute operations and variables (Phase 23 — complete, rig-proven)

A researcher can compute a value inside a state, store it in a named variable, and transition on it
— `random_bool(0.5) → target`, `add(counter, 1) → counter` — without a developer editing locked
source. Compute libraries use the *same substrate* as hardware libraries: versioned, promotable,
AST-validated, user-authored, shipped to the Pi at run start. Every call is logged as a pair of
events — one carrying the operation, one carrying the result.

This is what turns trial-by-trial randomisation, staircases and counters into part of the *task
specification* rather than something hidden in Python. The draft's one sentence — "internal flags
represent discrete values [updated] during execution" — is now a thin description of a much richer
facility.

*Known limitation to disclose:* compute-operation **arguments** are not yet in the event log
(CMP-16 partial). The operation and its result are logged; the argument values are not.

### 4.3 Contingencies of realistic complexity are expressible in the editor

Transitions carry arbitrarily nested AND/OR condition trees (`condition_tree`,
`~/pi-mirror/autopilot/autopilot/tasks/mics_task.py:1105`; Phases 15→16), and state bodies support
a recursive `type:"if"` action with unlimited nesting (`mics_task.py:646-694`). The draft says
"rule-based transitions", which reads as one condition per arrow. The accurate statement is more
impressive and directly supports C3: **realistic multi-condition contingencies are built in the
visual editor, not written in code.**

### 4.4 Hardware triggers run the full action vocabulary (Phase 24 — rig-proven)

A hardware trigger executes the same action list as a state's entry actions, assigned from the UI
rather than hardcoded. Rig evidence: runs 478/480/481, 144 triggers, 63 licker writes, 0
correctness errors. Meaning: *"when the beam breaks, do these five things"* is configuration.

### 4.5 Per-electrode addressing (Phase 25)

Detector channels (`LICKER0…3`) are derived by the backend from the pilot's declared wiring
(`first_channel` + count), offered in the editor's operand pickers, and resolved per-pilot at
preflight. Concretely: individual spouts of a multi-electrode lickometer are addressable in task
logic, and a mis-declared channel **fails preflight instead of silently discarding a live spout** —
which is the bug that created this phase, so it is an honest "we found this on the rig" story.

### 4.6 Preflight is a real static-analysis pass, not a hardware check

Nine issue kinds today (`api/routers/toolkit_dispatch.py:153-163`), rising past eleven with the
device-lease and device-unreachable kinds from Phases 18/26. It catches: no configuration for a
required module; an empty configuration; a class mismatch; a task action referencing a name the
pilot has no configuration for; a view or detector operand that resolves to no real key; **a
transition that reads a variable nothing upstream ever writes**; no deployable library version; a
compute library that failed to import; and **a state whose every exit is blocked by a frozen
variable** — a provable deadlock, caught before the animal is in the box.

The draft gives this one clause ("verifies that this specification is compatible with the assigned
system"). This is the paper's real answer to *"how do you stop a mis-specified overnight session
from wasting a week"*, and it deserves a paragraph.

### 4.7 The event envelope is richer than the draft says — and yesterday's note about `run_id` was wrong

Verified live on the rig cluster (`132.77.73.217`, `event_log_v2`): the mapped top-level fields are
`continuous, event, pilot, run_id, session, session_progress_index, subject, subjects, task_type,
timestamp`, and the most recent document carries `run_id: 551`. Written by
`~/pi-mirror/autopilot/autopilot/networking/Event_Dispatcher.py:38-48`, sourced from
`autopilot/tasks/task.py:132,138`.

So **the draft's "run ID" claim is correct** — this corrects `context/12_PAPER_VS_IMPLEMENTATION.md`
§2.4, which was written from the historical indices. What is genuinely absent is **experiment
name**. And the envelope carries two things the draft doesn't claim: `session_progress_index`,
which stamps **the trajectory step position onto every single event**, and `subjects`, the cohort.
That is C4 — the representation persisting into the data — demonstrated at the level of the
individual record, and it is the best single piece of evidence for the paper's central claim.

**Methods caveat that must be stated.** The analysed corpus is `restored-event_log_v2` on
`132.77.73.125` (4,413,736 documents), whose mapping has only `continuous, event, pilot, session,
subject, task_type, timestamp` — **no `run_id`**. The behavioral figures therefore come from data
that does *not* carry the identifier the Methods will describe. Name the index per figure.

### 4.8 The stored task carries its own diagram (Phase 29)

Task definitions now persist their editor layout (`ui_layout` JSONB). Minor, but it means the
picture of the state machine is part of the stored artifact — the figure in the paper and the thing
running on the rig are the same object. Worth a clause in a figure caption, not a Results
paragraph.

---

## 5. The consequence for the paper's argument

The draft's stated key contribution — "unifying these layers within a single representation that
persists across design, execution, and data" — is still the right claim against the completed
system. But the draft argues it almost entirely at the level of the *task*.

The strongest version, and the one the code now supports, is this: **the same substrate — a
versioned, AST-validated, promotable library shipped to the rig at run start — carries device
drivers, computations, and third-party protocol adapters alike; and anything that crosses into the
task, whether a GPIO pin, a random draw, a pose estimate or a firing rate, arrives through one
call: `view.get_value(name)`.** One read surface, one extension mechanism, one provenance trail,
one validation pass over all of it.

That is sharper and more defensible than "we combine the strengths of Bpod, Bonsai, IntelliCage and
Autopilot", which invites a feature-checklist argument the authors do not need to have — and which,
given §3.6, they especially should not have about Autopilot.

**A second, structural point.** With all phases landed, the weak part of the paper is the
*demonstration*, not the architecture. Two paradigms are shown, and neither exercises MICS-Link,
acquisition control, or a neural-gated closed loop. If phases 26–28 are complete by submission,
Figures 4B/5 should carry the network-vs-TTL offset distribution and at least one transition gated
on a firing rate. That converts the paper's largest architectural claims from assertion into
demonstration, which is what Nature Methods is buying.

---

## 6. Editorial and structural

- **A bare URL is left in the Results text**: "…such as pose estimation, and
  `https://www.nature.com/articles/s41467-025-64856-3`". Replace with a citation.
- **Table numbering is inconsistent**: the Introduction cites "Table 1"; the table is headed
  "Table X … (in progress)"; its caption says "Table X"; and a second stub, "Table 6: Comparing
  mics with other systems", sits further down. Same for the timing figure — "Fig. X" in the text,
  "Figure 4B" in the figure list.
- **Typo**: "internal flags represent discrete values **unpated** during execution" → "updated".
- **Table 1, MICS row**: "Flexible task design across paradigms **and species**" — only mice are
  shown. Also "adaptive progression" needs softening per §3.2, and the Autopilot row needs the
  disclosure from §3.6.
- **The cartoon panel prompts and the duplicated Panel 7/9 blocks** are working notes still living
  in the manuscript file.
- **Data availability** should name the indices and distinguish them: `restored-event_log_v2`
  (`132.77.73.125`, historical, no `run_id`, **two coexisting event vocabularies**) from
  `event_log_v2` on the rig cluster (`132.77.73.217`, current envelope). Note that the Pi's live ES
  handler is hardcoded to `132.77.73.217` at `ElasticSearchDataHandler.py:13`.
- **The two event vocabularies** — flat (`IR`, `LICKER`, `VALVE1`, `AUDIO`) vs namespaced
  (`gpio.Digital_In`, `gpio.Solenoid_mics`, `mixer.AUDIO`) — coexist in the analysed corpus. Anyone
  reproducing the behavioral figures from released data must be told this; it belongs in data
  availability or a supplementary note. See `context/05_EVENT_SEMANTICS.md`.

---

## 7. Sources read (2026-08-06)

**Server, `~/mics-backend`** (HEAD `f6aabd5`): `.planning/ROADMAP.md`, `.planning/STATE.md`,
`.planning/REQUIREMENTS.md`, `.planning/phases/` (18, 19, 25, 26, 27, 28, 29), `api/main.py`,
`api/models.py`, `api/routers/toolkit_dispatch.py`, `orchestrator/orchestrator/api.py`,
`web_ui/react-src/src/types/index.ts`.

**Server, `~/pi-mirror`**: `autopilot/setup.py`, `autopilot/autopilot/core/pilot.py`,
`autopilot/autopilot/tasks/task.py`, `autopilot/autopilot/tasks/mics_task.py`,
`autopilot/autopilot/networking/Event_Dispatcher.py`, `autopilot/autopilot/utils/Event.py`,
`autopilot/autopilot/utils/logging_utils.py`,
`autopilot/autopilot/data_handlers/ElasticSearchDataHandler.py`,
`autopilot/autopilot/hardware/unreal.py`.

**Live Elasticsearch**: `132.77.73.217` `event_log_v2` mapping + most recent document;
`132.77.73.125` index list, `event_log_v2` mapping and sample document.

**Local**: the draft `.docx`, `context/12_PAPER_VS_IMPLEMENTATION.md` (2026-08-05) — corrected here
on `run_id`, see §4.7.
