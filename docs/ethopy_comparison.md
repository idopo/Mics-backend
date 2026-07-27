# MICS vs EthoPy — System Comparison

A neutral, evidence-based comparison of two behavioral-experiment platforms.

- **EthoPy** — Evangelou et al., *Cell Reports Methods* 6, 101421 (June 2026), ef-lab.
  An accessible, DataJoint-backed platform whose primary use case is autonomous,
  high-throughput home-cage behavioral training.
- **MICS** — orchestrator + Pi-based system in this repository. Task logic is a
  declarative finite-deterministic automaton (FDA) defined in the backend and pushed
  to thin-client Pis; events stream to Elasticsearch over a Postgres-anchored core.

**Method / sources.** EthoPy statements are taken from direct inspection of its source
(`exp_core.py`, `iface_core.py`, `interfaces/RPPorts.py`, `interfaces/Arduino.py`,
`core/logger.py`, `utils/timer.py`, `behaviors/multi_port.py`, `core/behavior.py`) and the
paper, with file:line references. MICS statements describe its system architecture and design.
The goal is to characterize **design trade-offs**, not to rank the systems — the right choice
depends on the experiment.

---

## At a glance

| Axis | EthoPy | MICS |
|---|---|---|
| Task definition | Hand-written Python; transitions return state-name strings | Declarative FDA JSON, built/edited in GUI, pushed to Pi |
| Hardware declaration | DB `SetupConfiguration` + node-local `Channels` map | Centralized hardware libs / semantic hardware in backend |
| Hardware control in a state | Call `self.beh` / `self.stim` / `self.interface` (shared dict) | State entry actions on semantic hardware refs |
| GPIO edge capture | Lick = RISING only; Proximity = BOTH; software debounce | Edge capture with hardware-timestamped events |
| Action sequencing | Fire-and-forget output + timed wait / software flag | Non-blocking; transition gates on software flag (open-loop) or observed hardware/view change (closed-loop) |
| Clock | `time.time()` wall-clock, integer-ms, non-monotonic | Single GPIO oscillator; edge-accurate, single domain |
| Event timestamp | Stamped in Python callback (observation time) | Stamped at the hardware edge |
| Event ordering | Cross-thread races; insertion by priority, not time | Edge-ordered capture |
| Ephys sync | Optional (`sync=False` default); one stimulus-gate TTL line | (See §8) |
| Data model | DataJoint (MySQL), one typed/FK/hashed model | Postgres core + Elasticsearch, PK-propagation bridge |
| Subject identity | Integer `animal_id`, no Subject table/FK root | First-class Subject entity with FKs |
| Deployment | Pip per node + MariaDB/DataJoint server | Single `docker compose` stack |

Details and evidence follow.

---

## 1. Task / state-machine definition

**EthoPy.** A task is a single Python file. States are classes; the machine registers
them via `self.__class__.__subclasses__()` (`exp_core.py:256`) — **direct subclasses only**.
Each state implements `entry/run/next/exit`; `next()` returns the **name of the next state
as a string** (`exp_core.py:70`; e.g. `exp_matchport.py:127`). The string is validated only
**at runtime**, on the transition itself (`exp_core.py:145`: `if next_state not in self.states: raise KeyError`).
The transition graph is implicit, distributed across the `next()` methods; there is no GUI
(the paper notes a builder "may be introduced in future releases").

**MICS.** Task logic is a declarative FDA expressed as JSON, assembled and edited in a visual
builder, stored in the backend, and pushed to the Pi. States and transitions are data, not code.

**Trade-off.** EthoPy maximizes in-line expressivity (arbitrary Python anywhere) at the cost of
a graph that can only be read by tracing code, transitions that fail at runtime rather than at
author time, and a subclass-registration rule that silently drops grandchild states. MICS makes
the graph explicit, validatable, and editable without code, at the cost of needing the logic to
fit the declarative model (and a builder to maintain).

## 2. Hardware declaration & addressing

**EthoPy.** Declaring a port requires **two places**: (a) the DB `SetupConfiguration.Port`
table — logical port id, `type` (`Lick`/`Proximity`), and `ready/response/reward/invert` flags,
keyed by `setup_conf_idx` (`iface_core.py:354`); and (b) a **node-local** `Channels` config that
maps logical port → physical BCM pin (`RPPorts.py:38`, `local_conf.get("Channels")`). A firing pin
is mapped back to a logical `Port` by reverse lookup through that local map
(`_channel2port`, `iface_core.py:282`). Tasks address hardware **semantically** (`give_liquid(port=1)`),
never by pin number.

**MICS.** Hardware is declared centrally in the backend (hardware libraries / semantic hardware),
and semantic names resolve to pins on the Pi. The declaration travels with the pushed definition
rather than living in per-node local files.

**Trade-off.** Both abstract pins behind logical/semantic names. EthoPy splits the declaration
across a DB table and a per-node local file, which keeps wiring node-specific but creates a second
source of truth that can drift between machines. MICS centralizes the declaration, reducing drift
at the cost of a backend round-trip to change wiring.

## 3. Hardware control from within a state

**EthoPy.** Every state receives `self.interface`, `self.beh`, `self.stim` through the shared
"Borg" state dict (`exp_core.py:50-62`). Three layers are available: `self.interface` for low-level
verbs (`give_liquid`, `give_odor`, `opto_stim`, `give_sound`, `sync_out`, `in_position`), `self.beh`
for behavior-level actions that wrap actuation + logging (`reward`, `punish`, `is_licking`,
`get_response`, `is_correct`), and `self.stim` for stimuli. The intended pattern is to call
`self.beh`/`self.stim`; dropping to `self.interface` directly is allowed. Concrete actuation lives
in the interface subclass: `beh.reward()` → `self.interface.give_liquid(port)`
(`multi_port.py:70,90`) → thread-pool pulse on the resolved pin.

**MICS.** A state's entry actions invoke methods on semantic hardware references; the resolution to
concrete hardware happens on the Pi.

**Trade-off.** Both expose hardware through a named, semantic API rather than raw pins. EthoPy's
shared-dict injection is simple and makes context ubiquitous, but the same shared mutable dict means
any state can read/write any attribute (no isolation).

## 4. Event capture: GPIO edges & debounce

**EthoPy.** Edge handling is hardcoded per category in `RPPorts.__init__`:

- **Lick** — `add_event_detect(..., GPIO.RISING, bouncetime=100)`. Only the **onset** is captured;
  lick offset/duration is not logged via interrupt. Two licks within 100 ms collapse to one.
- **Proximity** — `add_event_detect(..., GPIO.BOTH, bouncetime=50)`. **Both** edges logged
  (`in_position:1` / `in_position:0`), matching the paper's "proximity on and off."
- **Sync-in** — `GPIO.BOTH, bouncetime=20`.

Edge type and debounce are fixed in code, not configurable per port.

**MICS.** Edge capture is hardware-timestamped; both transitions of an input can be captured as
events.

**Trade-off.** EthoPy's per-category defaults are simple but opinionated: getting lick offsets, or a
different debounce, means editing the interface class. The software debounce also bounds achievable
event rate.

## 5. Action sequencing (open-loop vs closed-loop)

**EthoPy.** Outputs are **fire-and-forget**: `give_liquid` submits to a 4-worker `ThreadPoolExecutor`
and returns immediately (`RPPorts.py:30,77`). There is no completion event. Sequencing "do B after A"
is expressed with a **software boolean plus a timed wait** — e.g. the Reward state transitions on
`self.rewarded` (meaning "reward was *dispatched*") or, failing that, when `state_timer.elapsed_time()
>= reward_duration` (`exp_matchport.py:163-180`). The guarantee is "probably completed within a time
budget," timed by the software clock.

**MICS.** The same dependency is expressed as **two states**, where the transition condition observes
the **actual hardware/view change** rather than the command. For hardware, the view is updated by the
GPIO callback firing on the real edge; the design updates the view first, then proceeds, to minimize
the reaction gap. For software-only signals the state variable changes synchronously (real-time).

**Trade-off.** Both systems run **non-blocking** polling loops — neither stalls a thread waiting on
actuation. The difference is *what a transition can be conditioned on*. EthoPy conditions on a software
boolean ("command issued") plus a timed wait, because no completion signal exists; that is open-loop
regardless of how the timer is tuned. MICS conditions each transition on whatever you author: a software
flag for an **immediate, open-loop** advance (matching EthoPy's non-blocking behavior), or an **observed
real hardware/view change** for a **closed-loop, self-correcting** advance that makes the dependency
explicit in the graph and avoids conservative padding. So MICS is a **superset** — non-blocking either
way, with the closed-loop option available per transition when completion is observable. The residual
cost of the closed-loop path is the control-decision dispatch latency inherent to any software state
machine; for an unsensable pure output, both systems fall back to a timer, and MICS is only ahead there
if that timer is hardware-confirmed.

## 6. Clock & event timestamping

**EthoPy.** One timer underlies all timing: `Timer` wraps `time.time()` and returns
`int((time.time() - start) * 1000)` (`utils/timer.py`) — a **wall-clock, integer-millisecond,
non-monotonic** clock (it can step or slew with NTP). Every logged event is stamped at the moment
`log()` runs through a single chokepoint (`logger.py:425`). GPIO events are stamped **inside the Python
callback** (`_lick_port_activated`: `self.resp_tmst = self.logger.logger_timer.elapsed_time()`;
behavioral activity: `behavior.py:204`). RPi.GPIO does not pass a hardware timestamp, so the recorded
time is **when Python handled the edge**, after GIL scheduling and the debounce window — observation
time, not edge time. The paper's "~1.4 ms" is best-case PTP cross-machine precision on RP4 software
timestamping; "1.2 ms" is lick→valve actuation latency — neither is single-event edge-timestamp accuracy.

**MICS.** A single GPIO oscillator generates the timestamp at the hardware edge, in one clock domain —
edge-accurate and drift-free, decoupled from any software-handler latency.

**Trade-off.** EthoPy's single software clock is simple and "good enough" for trial-level, ms-tolerant
behavioral analysis, and degrades gracefully there. It is not suited to sub-millisecond timing, and its
non-monotonic base clock means a single global time mapping is unsafe across NTP adjustments. MICS pays
for a hardware-timed design and gets recording-grade timestamps without an external clock.

## 7. Concurrency & event ordering

**EthoPy.** Inputs arrive on **independent RPi.GPIO callback threads** (one per `add_event_detect`,
including one per lick port), outputs run on a `ThreadPoolExecutor`, DB writes drain on a **single**
inserter thread (`logger.py:162`), and a state-machine thread runs the loop — all under one GIL. Because
each event is stamped when its callback executes, two near-simultaneous inputs on different threads can
be stamped **out of physical order** (the physically-second edge may be scheduled first). Under CPU load
the edge→stamp latency grows and becomes more variable. The insert queue is a `PriorityQueue` ordered by
a **priority field only** (`PrioritizedItem`, `logger.py:1053-1067`); equal priorities are not FIFO-tie-broken,
and failed inserts re-queue at `priority+2` (`logger.py:289`) — so **row order ≠ event order**. Analysis must
sort by the `time` field, which recovers ordering only when the stamped times themselves are not inverted.
(Causally-chained events — e.g. lick → reward through the single state-machine thread — stay ordered, but by
control flow, not by any timestamp guarantee.)

**MICS.** Events are captured edge-ordered with hardware timestamps, so ordering of fast/simultaneous
events does not depend on thread scheduling.

**Trade-off.** EthoPy's model is fine for ms-tolerant analysis but unreliable for fine-grained sequencing
of near-simultaneous events, and it degrades exactly under the high event rates where ordering matters most.

## 8. Recording synchronization (TTL / ephys)

**EthoPy.** Synchronization is **opt-in and off by default** (`sync = False`, `exp_core.py:168`); all TTL
machinery is gated behind it. When enabled there are three lines: **`Sync.out`** — a single line set HIGH at
stimulus onset / LOW at offset (`stimulus.py:161,166` → `RPPorts.py:94`), recorded by the acquisition system at
its hardware clock; **`Sync.in`** — incoming pulses (e.g. 2P frame triggers) stamped in **software**
(`_sync_in` → `logger_timer`, `bouncetime=20`); and **`Sync.rec`** — a recording-active handshake that gates
session start/stop. There is no per-event outbound TTL. Alignment is offline: the stimulus edges (present in both
clocks) anchor a mapping, and DB-only events (licks, rewards, states) are **interpolated** across the software
clock between anchors.

To obtain hardware precision for a *specific* event, the practical approach is to **physically tap that signal
into the acquisition system's digital input** (e.g. lick comparator, valve drive, opto trigger), so the DAQ
records the real edge and the software timestamp becomes only a label for matching. Each tapped signal also
becomes an additional alignment anchor. Tapping every event is unnecessary unless every event must be
hardware-precise.

**MICS.** Event times are captured at the hardware edge in one clock domain, so behavioral events are
recording-grade without an opt-in mode or an external clock; there is no second clock to reconcile and no
interpolation gap across the session.

**Trade-off.** EthoPy's TTL scheme is sound and standard: TTL-marked events are hardware-precise on the
acquisition clock and immune to the software clock and NTP; the exposure is on **un-tapped, DB-only events
interpolated across `time.time()`**, which grows with session length and shrinks with anchor density. The
engineering burden (which signals to tap, DAQ channel count, dual-clock reconciliation) is on the user. MICS
removes that burden by stamping at the source, at the cost of the hardware-timed design.

## 9. Graduation / curriculum

**EthoPy.** Within-session adaptive difficulty via a staircase (accuracy or d-prime, with anti-bias)
(`exp_core.py:704-728`, `Block` dataclass). Cross-session curriculum progression is manual (changing `task_idx`).

**MICS.** First-class cross-session, per-subject protocol-step graduation, persisted in the backend.

**Trade-off.** EthoPy's within-session staircase (and its d-prime + anti-bias logic) is mature and worth
borrowing for within-step difficulty; MICS owns the cross-session curriculum dimension EthoPy leaves manual.

## 10. Transport / control plane

**EthoPy.** Inter-node coordination is via a DB-polled `Control` table; the paper states there is no built-in
protocol for real-time inter-instance communication. Pose estimation (DLC) runs on a GPU-equipped node.

**MICS.** ZMQ real-time messaging + Redis state + thin-client Pis; definitions and commands are pushed.

**Trade-off.** EthoPy's DB-polling control is simple and needs no extra services, but is not a real-time control
plane. MICS's messaging plane is real-time at the cost of running the ZMQ/Redis infrastructure.

## 11. Code provenance & drift

**EthoPy.** The task is resolved from a **node-local path** (`resolve_task`), so the same `task_idx` can run
different code on different machines. This is mitigated by recording, **per session**, the full task file as a
blob plus git hash and an `is_dirty` flag (`Session.Task`/`Session.Version`, `exp_core.py:1001-1020`;
`logger.py:762-790`).

**MICS.** The definition lives in the backend and is pushed to the Pi (thin client), so there is a single source
of truth; actual transitions (not just parameters) are known centrally.

**Trade-off.** EthoPy's per-session snapshot gives strong *after-the-fact* provenance even though code is local;
MICS's push model is *drift-proof by construction* but depends on the backend being authoritative. EthoPy's
`is_dirty`/content-hash-per-session idea is worth adopting at the run level in any system.

## 12. Deployment

**EthoPy.** Pip install per node, plus a separate MariaDB/DataJoint server, plugin-path configuration, and a
GPU/Ubuntu box for DLC.

**MICS.** A single `docker compose` stack (api / orchestrator / web_ui / backup).

**Trade-off.** EthoPy's components are independently installable (flexible, but more moving parts to stand up);
MICS trades that flexibility for one-command bring-up.

## 13. Data model

**EthoPy.** DataJoint on MySQL — **one** rigorous model for everything: enforced typing, primary/foreign keys,
content-hashed conditions, and reproducible computed-table pipelines (`exp_core.py:988+`).

**MICS.** Postgres relational core + Elasticsearch event store, connected by **authoritative primary-key
propagation**: `run_id` / `subject` / `session_id` are minted at the core and stamped into every ES document, so
the two stores form one connected graph.

**Trade-off.** This is the axis where EthoPy's uniform, schema-on-write rigor on the **event/analysis layer** is a
genuine, enduring strength (everything typed, keyed, hashed, reproducible in one system). MICS has comparable
relational rigor on its Postgres core and bridges to a schema-on-read event store via key propagation; whether
stable ES event types ever warrant declared schemas is an open design question rather than a deficiency.

## 14. Administration & subject identity

**EthoPy.** Subject is a bare integer `animal_id` (`Session` schema) — no Subject table, no attributes, no parent
entity; downstream foreign keys rest on this unenforced root. No projects/researchers/IACUC/protocol entities.

**MICS.** First-class Subject (with bio/weights/surgeries), Projects/Experiments, Researchers, IACUC, multi-step
Protocols, with real foreign keys and an admin UI.

**Trade-off.** EthoPy keeps identity minimal, which is lightweight but leaves the identity root unenforced; MICS
provides a richer, FK-backed administrative model at the cost of more schema.

---

## Choosing between them

- **EthoPy fits** autonomous, high-throughput, low-cost **home-cage behavioral training** where ms-tolerant
  timing is sufficient, a single uniform (DataJoint) data model is valued, full Python expressivity per task is
  desired, and recording — if any — is added selectively with TTL taps into a DAQ.
- **MICS fits** workflows that want **declarative, GUI-built/validated task logic**, **closed-loop sequencing on
  observed hardware state**, **edge-accurate timestamps in every session without a second clock**, real-time
  multi-node control, and a richer subject/project/IACUC administrative model.

The systems make different bets. EthoPy pushes precision and provenance engineering to the user and the
acquisition hardware in exchange for simplicity and uniform data rigor; MICS solves timing and sequencing at the
source and centralizes definitions in exchange for more infrastructure. The deepest recurring theme across timing,
concurrency, and sequencing is **observe-vs-infer**: EthoPy records software observations (a timestamp taken in a
callback, a boolean meaning "command issued," a timer standing in for completion), while MICS reacts to and records
the hardware event itself. The more an experiment depends on precise timing, strict event ordering, or guaranteed
sequencing, the more that distinction matters.

## Worth borrowing from EthoPy (regardless of platform)

- Per-run content hash + `is_dirty` provenance (record exact-definition fingerprint on the run row).
- Within-session **d-prime + anti-bias staircase** for difficulty control.
- Per-session **frozen hardware configuration** snapshot.
- The formal **latency-budget characterization** methodology (their Figure S1).
- **NWB export** for downstream interoperability.
