# 18 — MICS: the paper-facing feature inventory

**Written 2026-08-10.** Every capability that is genuinely MICS's own, Pi-side and backend, written so
a PI can lift it into a manuscript, with the honest bound on each claim.

**Primary source:** `.planning/16_FORK_HONEST_COMPARISON.md` (the synthesis of six independent
read-only audits), plus the per-domain audits it compresses. Where this document adds a mechanism
detail or a citation that doc 16 does not carry, that detail was re-verified against live source
during the preparation of this file.

---

## How to read this document

**What is in it.** Only capabilities the audit classified **MICS**. Anything the audit classified as
generic application foundation (any competent Python+ZMQ+pigpio rig lands there) or as an Autopilot
debt is excluded, and **Part C lists what was excluded and why** — the boundary was drawn
deliberately and is defensible in review.

**Authorship.** Ido Porat (`idopo`), Lior Segev, Noa (`noa`/`noale17`) and Inbar are all MICS lab
members. Every commit by any of them is MICS-team work. This document never splits credit
internally. Build era appears only where it is scientifically informative — chiefly that the
state-machine engine was built by hand on the Pi in 2024, eighteen months before any database layer
existed, which is what explains the architecture's shape (a runtime that was later *inverted* to be
driven by data, not a runtime designed top-down from a schema).

**The one rule on wording.** A claim that fails review is worse than a claim not made. Where a
capability is real but narrower than the draft manuscript implies, the **defensible** wording is
given, not the aspirational one.

**Status vocabulary.**

| Status | Meaning |
|---|---|
| **shipped** | True of the code today as written here. Claim it. |
| **shipped-but-narrower** | The capability exists; the drafted wording overstates it. Use the wording in the *Honest bound* row. |
| **one-fix-from-true** | Currently false as drafted, and a small, specified code change makes it true. Highest-value items in this document. |
| **planned** | Not executed. Do not write in the present tense. |

**The word "fork" must not appear.** The MICS repository predates the Autopilot import by nine
months (`f49dfe7` 2021-07-21 vs `30c8d3c` 2022-04-05); Autopilot was **vendored into an existing
repo**. Use *"vendored dependency"*.

---

## The three items that are one code change from claimable

These are worth more to the manuscript than any rewording. Each converts a currently-false sentence
into a true one.

| # | Claim it unlocks | Why it is false today | The change |
|---|---|---|---|
| **F2** | *"The driver code that ran this experiment is a versioned artifact recorded against the run."* | `session_runs` has **no version column** and there is no run↔version join table; what is stored is a *resolution policy* over mutable rows (`stable_version_id`, `active_version_id`, `toolkit_hardware_libs.default_version_id`, `task_definitions.hw_lib_versions`). Promote a new stable version and yesterday's run silently re-resolves to different source. | **One column.** Write the resolved `{lib_id: version_id, reason}` map onto the `session_runs` row at dispatch. **The orchestrator already holds exactly this map** at `orchestrator_station.py:947-950`, immediately before it sends `LOAD_HARDWARE_LIBS` (`:961-968`). This is the single highest-value change in the system for reproducibility claims. |
| **F1** | *"Static validation blocks dispatch of a provably-deadlocked task."* | Preflight advises, it does not block. `HardwareCheckModal.tsx:551` renders an always-enabled *Save & Start*; `PilotSessions.tsx:100-102` catches a preflight error with the comment *"proceed with start"* and falls through to `doStart`; there is no server-side re-check on the start path (`web_ui/app.py:244-280`); the orchestrator concedes it in its own comment — *"never block a run preflight cleared"* (`orchestrator_station.py:387-388`). | **~20 lines.** Re-run preflight inside `POST /runs/{run_id}/start` and return **409** on unresolved hard issues; disable the modal's start button while hard issues stand; stop the `catch` falling through. |
| **F5** | *"Events on a rig can be aligned to an external acquisition system (and, with a distributed pulse, across rigs) by a shared hardware edge."* | The one mechanism that could do this is wired and switched off. `gpio.TTL` (`gpio.py:1130-1159`) precompiles the pulse train into a pigpio stored script (`:1146`), but every driver call in the live toolkit is commented: `learning_cage.py:85-86` declares `TTL1`, and `:191-192` / `:208-210` are commented out, as is the duplicate pair in `mics_task.py:1594-1596`. Separately, NTP is dead code — `enable_ntp_and_wait` (`pilot.py:498-511`) and `disable_ntp` (`:514-515`) exist but both call sites are commented **in the very commit that introduced them** (`a008046`, sites `pilot.py:1138,1148`). | **A config change plus one demonstration run.** Re-enable the `TTL1` calls in the live toolkit path and record a session in which the same edge appears in both the MICS event stream and the external recorder. Note the residual: NTP would not fix this — network time is milliseconds, the shared edge is the mechanism. Cross-*rig* alignment additionally requires distributing that pulse to every rig, which is a wiring decision, not a code one. |

Three adjacent fixes are bug fixes rather than claim-converters, but each removes a silent failure a
reviewer could reproduce: **F3** — a non-`NTrials` `graduation_type` is accepted, stored, dispatched
and never fires (`api/main.py:1607-1660`, `:1750`); **F4** — the FDA `special: INC_TRIAL_COUNTER`
action is a silent no-op (`mics_task.py:786-789` sends `value={}`, and
`orchestrator_station.py:588-590` returns early on a falsy `value.get("subject")`); **F6** — MICS
reads Autopilot's `current_trial` key as *N required* where Autopilot documents it as a *resume
offset*, so any Autopilot-shaped protocol JSON is silently inert (`main.py:1646-1654`, `:1752`).

---

## Summary table

### Part A — Pi-side (MICS-Core)

| # | Feature | Status | One-line paper claim |
|---|---|---|---|
| A1 | Finite-state engine with named states and guarded transitions | shipped | Task control flow is an explicit, named state machine whose transitions are guards over named quantities, not branches buried in Python. |
| A2 | The whole task loaded from a JSON specification | shipped | The task specification is data: a ~520-line interpreter turns a stored JSON document into the executable automaton, with closed vocabularies and no `eval`. |
| A3 | Hot reload of a running task | shipped | A task's state machine can be replaced over the network mid-run without restarting the rig or losing the animal's position in the task. |
| A4 | Trigger queue — no dropped hardware events | shipped | Concurrent hardware events are serialised through a queue and none is discarded; this is a correctness fix to the inherited runtime, which dropped triggers on lock contention *and* wiped the trigger table after one fired. |
| A5 | Generator-based interruptible run loop | shipped | A state can be aborted mid-execution, so a stop command takes effect within the state rather than after it. |
| A6 | Automatic event-level logging | shipped-but-narrower | Output-driver methods are instrumented by decorator and input events by a single central handler, so the scientific record is produced by the framework rather than declared by the task author. |
| A7 | `View` — one uniform, named, synchronous read surface | shipped | Every quantity a transition may read has a string name and a non-blocking read, which is precisely what allows a condition to be data and to be validated before dispatch. |
| A8 | Trackers, flags and declared variables | shipped | Task-owned state (counters, booleans, trial counters, GUI-declared variables) lives in the same named namespace as hardware, and every write to it is logged. |
| A9 | Semantic hardware naming | shipped | Task logic refers to `reward_port`, not to a pin, and the friendly-name map is merged across the class hierarchy with per-definition overrides. |
| A10 | Per-run hardware-library shipping | shipped | The driver source a run will use is delivered from the database at dispatch, written to the rig and placed ahead of the installed package on the import path. |
| A11 | Microsecond event timebase | shipped-but-narrower | Every event on a rig is stamped from one shared GPIO-derived clock — *using Autopilot's forked pigpio, which must be credited; MICS contributes the single shared client and the event stream, not the microsecond capability.* |

### Part B — Backend (MICS-Portal)

| # | Feature | Status | One-line paper claim |
|---|---|---|---|
| B1 | 28-table relational model of colony, protocol and execution | shipped | Animals, projects, experiments, protocols, rigs, sessions, runs and progression are one queryable relational model rather than a file per animal. |
| B2 | Event stream with full run context on every document | shipped | Every event document carries its pilot, run, session, cohort and trajectory position, so any record can be traced back to the experimental context that produced it. |
| B3 | Task authoring without writing code | shipped-but-narrower | Composing and modifying task logic — states, transitions, conditions, actions, variables — no longer requires writing or deploying code; authoring a new hardware primitive still does. |
| B4 | One task, many rigs | shipped-but-narrower | A fully GUI-built task definition runs unchanged on rigs with different pin maps, driver classes and electrode counts, because every per-rig detail is resolved at load time from that rig's own configuration. |
| B5 | Drivers and rig configuration as versioned database artifacts | shipped | Driver source and rig hardware configuration are immutable, hash-addressed, syntax-gated database rows with a promotion lifecycle and a real on-rig import test. |
| B5b | Per-run record of the resolved version | **one-fix-from-true** | *(after F2)* The exact driver version that executed each run is recorded on the run. |
| B6 | Pre-dispatch static analysis, including a deadlock detector | shipped | The task graph is statically analysed before dispatch, including a sound detector for states whose every exit is blocked by a value frozen on entry — written for a real, dated silent hang. |
| B6b | Validation that blocks dispatch | **one-fix-from-true** | *(after F1)* A run whose task graph contains a provable deadlock cannot be dispatched. |
| B7 | Multi-subject sessions | shipped | The session is a first-class entity that groups several animals on several rigs, and cohort membership is stamped on every event. |
| B8 | Run modes: new / resume / restart | shipped | A run's lifecycle is modelled and queryable, with explicit semantics for resuming, restarting and starting fresh — and a re-run never inherits a stale graduation criterion. |
| B9 | A subject's experimental history, relationally | shipped-but-narrower | An animal's protocol history, weights, surgeries and project membership are answerable in SQL — questions that have no representation at all in a per-animal file. |
| B10 | Device leases | shipped | A shared external instrument is arbitrated by an atomic database lease so two rigs cannot command the same recorder. |
| B11 | MICS-Link — external-instrument transport | shipped-but-narrower | External software can push typed signals into a running task's state machine, with the wire-format adapter living in a versioned, per-toolkit artifact rather than in platform code. |
| B12 | Coordination state is durable rows; the UI is off the data path | shipped | Experimental progression lives in the database and data ingestion happens in a headless service — closing the browser cannot affect a running experiment or its record. |

---

# Part A — Pi-side (MICS-Core)

## A1 — Finite-state engine with named states and guarded transitions

**What it is.** The task's control flow is an explicit, named state machine: each state has a name,
and moving from one state to the next happens only when a stated condition over named quantities
becomes true.

**Mechanism.** `self.stages` is a `FiniteDeterministicAutomaton`
(`utils/FiniteDeterministicAutomaton.py`, 96 lines; installed at `mics_task.py:156`) holding a
transition table `{from_method: [(to_method, [predicates], description)]}` (`:8`, populated at
`:33`). `__next__` (`:67-89`) walks the outgoing transitions **in registration order** and returns
the first successor whose predicates *all* hold (`:79-80`); with no satisfied successor it raises
`StopIteration` (`:89`), which the run loop's `except`/`finally` turns into a clean task end
(`pilot.py:1234-1239`; the pattern is documented in-code at `mics_task.py:994-996`). An empty
predicate list is an unconditional transition, since `all([])` is `True`. State names are recovered
from the callable at `:73` and `:82`, which is why the JSON loader renames its synthesised closures
(`mics_task.py:980-982`). Every state entry, including the first, emits a `state_transition` event
(`transition_notify`, `:16-19`, called at `:75` and `:87`) and appends to an in-process `saga_trace`
(`:11,74,83`).

Guards are richer than a flat list. A transition may carry a **nested AND/OR condition tree**
compiled by `_build_tree_lambda` (`mics_task.py:1361-1392`: leaf detection `:1374-1376`, recursion
`:1383`, `_and_check` `:1386-1388`, `_or_check` `:1390-1392`), a **disjunctive-normal-form group
list** compiled to a single `any(all(...))` closure (`load_fda_from_json:1223-1238`), or the legacy
flat list ANDed by `__next__`. Comparison operators are a fixed 6-operator, 12-alias map
(`_COMPARE`, `mics_task.py:33-40`).

Inside a state, a **list of entry actions** runs once on entry (`_build_state_method:948-950`,
pre-built at load time), and any of those actions may be an **in-state conditional** — an `if`
action with `then`/`else` branches, nestable without limit
(`_build_if_action`, `mics_task.py:683-723`, recursion at `:708-709`).

`check_determinism` (`:38-44`) runs automatically on every `add_transition` (`:36`) and raises
`ValueError` naming both destinations when two outgoing transitions conflict.

**Why it matters scientifically.** The failure it prevents is the one every behaviour lab has lived
through: a task whose real logic is only knowable by reading the Python, so that "what the animal
actually experienced" is a claim about a file rather than a property of the record. Here the
trajectory through named states is emitted as events (`state_transition`), so the sequence of
experimental states is *in the data*, and the specification that produced it can be diffed between
animals and between days.

**What Autopilot does instead.** `self.stages = itertools.cycle(stage_list)` — a fixed ring with no
names, no conditions and no branching. A trial is exactly one lap; all branching lives in Python
inside a stage method, and nothing logs a per-stage event.

**Honest bound.** `check_determinism` is a **load-time spot-check, not a proof**. It *calls* the
predicates at registration time (`boolean_conflict:46-52`), reports a conflict only if both sides
evaluate true *at that moment*, uses `any(...)` where the evaluator uses `all(...)` (so its
semantics do not match `__next__`), and **swallows every exception and returns `False`** (`:51-52`)
— any guard that raises because the task is not yet fully initialised silently passes. Write
*"conflicting transitions are rejected when detectable at load time"*, **never** *"provably
deterministic"*. Also: transition order is significant and undocumented in the UI (first satisfied
wins), and the automaton's only backlog signal is a bare `print()` on the trigger queue depth
(`:84-86`).

**Build-era note (scientifically informative).** The automaton was authored by hand on the Pi —
`8b7bd7c`, 2024-08-18 — eighteen months before the database layer existed, and reached the
production branch byte-identical via `94fb000` (2024-11-11). What the 2026 work added is the
*inversion* (A2). Both halves are MICS's; conflating them makes the claim harder to defend.

**Status:** shipped.

---

## A2 — The whole task loaded from a JSON specification

**What it is.** The entire task — its states, what happens in each, what makes it advance, what its
variables are, and which hardware events do what — is a stored JSON document that the rig reads and
turns into a running program. No Python is written to define a task's logic.

**Mechanism.** `load_fda_from_json` (`mics_task.py:1060-1269`, 210 lines) fans out into six
builders: `_build_state_method` (`:878-986`, 109 L), `_build_action_callable` (`:725-876`, 152 L),
`_build_condition_operand` (`:597-681`, 85 L), `_build_if_action` (`:683-723`, 41 L),
`_build_transition_lambda` (`:1394-1436`, 43 L) and `_build_tree_lambda` (`:1361-1392`, 32 L) —
**523 lines of interpreter** turning a data document into executable closures.

Three properties make this a defensible engineering claim rather than a description:

1. **Closed vocabularies, enforced at load.** The action dispatch is a closed 8-branch table —
   `hardware`, `timer`, `compute`, `flag`, `special`, `method`, `if`, `view` — with a terminal
   `raise ValueError` at `:873-876`, and a second independent pre-validation loop in
   `_build_state_method:910-946`. Operands are six typed kinds (bare literal `:610-612`,
   `view_detector` `:620-645`, `view` `:647-651`, `tracker`/`flag` `:653-657`, `param` `:659-663`,
   `hardware` `:665-676`) with a catch-all `raise` at `:678-681`. Operators are the fixed
   `_COMPARE` map, enforced at `_build_if_action:698-702` and `_build_transition_lambda:1408-1412`.
   **A malformed document fails at load time with a named error, never mid-session.**
2. **No `eval` anywhere on the FDA path.** Verified by grep over `mics_task.py`,
   `FiniteDeterministicAutomaton.py` and `task.py` → 0 matches. Every guard and action is a
   pre-built Python closure over `operator`-module functions with default-argument capture. The only
   dynamic-code construct in `mics_task.py` is the `exec` at `:222`, which is the hardware-driver
   shipping path (A10), not condition or action evaluation.
3. **Triggers are assembled from the same vocabulary as state bodies.**
   `apply_trigger_assignments` (`:1438-1500`) builds each trigger's action list through
   `_build_action_callable` — the identical builder — so a new action type works inside a trigger
   with zero changes (docstring `:1443-1449`). Declared variables are one `Tracker` registered in
   *both* `self.flags` and `self.view.view` (`:1159-1174`), readable as `{"flag": name}` or
   `{"view": name}`, and any action may capture its result into one (`_validate_output_spec:562-574`
   validates the target exists at load; `_capture_output:576-579` writes it).

**Why it matters scientifically.** Three failures follow from a task being code. A protocol change
cannot be reviewed by anyone who does not read Python. There is no artefact to attach to a paper
that *is* the task. And nothing outside the file can check the task before an animal is in the box.
Making the specification data is the enabling condition for every one of B3, B4, B5, B6 and A3 — it
is the single architectural decision the rest of the system rests on.

**What Autopilot does instead.** The task is a Python class. `PARAMS` renders a parameter form and
`TrialData` declares a trial-table schema, but the *logic* is inaccessible: nothing outside the file
can inspect, validate, diff, render or edit it.

**Honest bound.** Adoption is light. Of 157 task definitions, **27 have a non-null `fda_json`**; the
highest-usage protocol steps have `task_definition_id IS NULL` and dispatch straight to a Python
plugin class (`elastic_test` ×39 steps, `AppetitveTaskReal` ×14). **Claim the capability; do not
imply the lab has migrated.** ⚠️ **This 27/157 figure is sourced to a live-database inventory for
which no SQL is recorded anywhere in `.planning/`.** Re-derive and date it before it appears in a
manuscript. Separately, `blocking` is read from the state definition at `:902` and then never used —
dead schema. And two save-gate holes let a definition save clean and never fire: `view` operands are
deliberately not checked by `validate_condition_operands`, and the runtime shape is `condition_tree`
with a bare literal on the right, not `condition` with `{"const": …}`.

**Status:** shipped.

---

## A3 — Hot reload of a running task

**What it is.** A task's state machine can be replaced while the task is running, and the animal
stays where it was in the task rather than being restarted from the beginning.

**Mechanism.** The backend pushes `UPDATE_FDA` over ZMQ (`orchestrator_station.py:982-997`); the Pi
handles it at `pilot.py:646-668` (key registered at `pilot.py:223`) and calls
`hot_update_fda(definition)` (`mics_task.py:1544-1586`). That method captures the current state's
*name* (`:1561-1568`), re-runs `load_fda_from_json` in full — which constructs a brand-new automaton
at `:1112` — and then re-points `current_method` by name match over the new state list
(`:1575-1584`). If the state no longer exists, the task restarts from the initial state. The pilot
acks with `HOT_RELOAD_ACK {'status': 'ok'|'error'}` (`:665`, `:666-668`).

Because the loader re-runs in full, the swap also rebuilds `_semantic_hw` (`:1130-1146`), the view
registrations of semantic hardware (`:1150-1151`), the **declared-variable registry, whose values
are deliberately reset** (`:1159-1174`, "*this is intended, not a bug*"), every state closure, the
initial state, every transition, the MICS-Link readiness gate (`:1252`) and all trigger assignments
(de-duplicated by `apply_trigger_assignments:1473-1480`).

**Why it matters scientifically.** The failure it prevents is throwing away a session. A parameter
typo or a mis-wired transition discovered ten minutes into a run otherwise costs the whole session —
and in a home-cage paradigm, a restarted session is not a resumed one: the animal's satiety,
motivation and time-of-day have all moved.

**What Autopilot does instead.** Edit a file on the Pi and restart the pilot process. Its
parameter-update RPC (`l_param`) is still `pass` — inherited *and* dead.

**Honest bound.** **There is no safe point and no lock.** The swap runs on the network-handler thread
while the stage thread may be mid-`wait_for_condition`, and that generator captured its outgoing
transition list *once, by value, before its loop* (`mics_task.py:489`) — so a state already blocking
keeps polling the **old** transitions until it returns. Consistency rests entirely on the GIL. What
is **not** swapped: `self.hardware` (no re-`init_hardware`), `prefs.HARDWARE`, `self.params`, flags
created by `init_flags()`, the trigger queue and its worker, the `Event_Dispatcher`, detector
trackers, and directly-assigned legacy triggers. A **failed** hot reload leaves the task with a
partially-rebuilt automaton — `load_fda_from_json` mutates in place from `:1112` and has no
rollback. Finally, `hot_update_fda`'s own docstring justifies its safety by reference to
`stage_block.wait()`, which is commented out (`pilot.py:1227`) — **do not reproduce that sentence as
a design claim.**

**Status:** shipped.

---

## A4 — The trigger queue: no dropped hardware events

**What it is.** Every hardware event — a lick, a beam break, a touch — is put on a queue and handled
in arrival order. None is thrown away.

**Mechanism, and the defect it fixes.** This is the most concrete engineering claim in the runtime,
because the diff proves both the defect and the fix. Inherited Autopilot 0.4.4 `handle_trigger` had
**two independent loss paths**:

```python
unlocked = self.trigger_lock.acquire(blocking=False)
if not unlocked:
    self.logger.debug('Trigger called, but trigger lock has not been released …')
    return                      # ← this trigger is DISCARDED
...
self.triggers[pin]()            # fire
self.triggers = {}              # ← every OTHER armed trigger is ALSO discarded
```

(B1 `tasks/task.py`; doc 16 cites `:279-306`, the extracted B1 file in the audit scratchpad puts the
same block at `b1_task.py:243-278` — ⚠️ **pin the line numbers with
`git show 30c8d3c:autopilot/autopilot/tasks/task.py` before publication**; the *code* is exactly as
quoted.)

So: a trigger arriving while the lock is held is dropped with a debug log, **and** after any one
trigger fires the whole trigger table is wiped, so a second physical event in the same stage has
nothing to call. For a home-cage rig where an animal can lick, break a beam and trip a touch sensor
within milliseconds, both are data loss.

Commit `c632674` (2025-02-02) replaced this with `self.event_queue = queue.Queue()` plus a daemon
worker (`task.py:153-155`); `handle_trigger` became one line — `self.event_queue.put((pin, level,
tick, hardware))` (`:373`) — and the wipe, the lock-return and `stage_block.set()` are all commented
out (`:369-372`, `:398-402`). `process_queue` (`:258-266`) drains the queue and serialises every
event through `execute_trigger` (`:268-307`). `event_queue` occurs **0 times** in Autopilot 0.4.4.

Two MICS additions ride on top. `execute_trigger` dispatches a `Hardware_Event` **before any
callback runs and whether or not a callback exists** (`:272-283`) — this is the central input
instrumentation of A6. And each callback is individually error-isolated (`:303-304`), with a failure
emitting a `TRIGGER_ACTION_ERROR` event (`_report_trigger_error`, `:309-333`) that is
total-by-construction (`:330-333`).

**Why it matters scientifically.** Silently dropped input events do not announce themselves — the
run completes, the file looks normal, and the lick count is simply wrong. There is no post-hoc way
to detect the loss. This is the failure mode most corrosive to a behavioural dataset, and the
inherited code had two of them.

**What Autopilot does instead.** The code above. Note the framing discipline: this is a correctness
fix to inherited code, stated as a diff, not a reliability judgement about someone else's software.

**Honest bound.** (i) **`process_queue` has no exception boundary** — the code's own docstring says
so: *"anything that escapes it kills trigger processing for the rest of the run (process_queue has
no handler … deliberately still open)"* (`task.py:312-314`). `_report_trigger_error` covers
exceptions from *callbacks* only; anything raised by the pre-callback `Hardware_Event` block
(`:272-283`) or by `inspect.signature` (`:294`) silently kills the worker thread. (ii) The queue is
**unbounded** (`task.py:153`, no `maxsize`) — a fast sensor plus a slow action list grows it without
limit and delays every trigger behind it; the only backlog signal in the system is a `print()`
(`FiniteDeterministicAutomaton.py:84-86`). (iii) One-shot trigger semantics — trigger fires,
stage advances — are deliberately broken by this change. Triggers are now persistent and orthogonal
to state advance. Better, but it *is* a changed contract; say so.

**Status:** shipped.

---

## A5 — Generator-based interruptible run loop

**What it is.** A stop command takes effect inside the current state rather than after it, so a
researcher (or a fault handler) can halt a task without waiting for whatever the animal is currently
doing to finish.

**Mechanism.** A state body returns a generator; the pilot's run loop consumes it and checks a
running flag between yields (`pilot.py:1188-1197`, esp. `:1194-1195`), plus a loop-bottom check at
`:1231-1232`. Commit `23e6bf7` (2025-03-18) rewrote the loop for this and added `import types` in
the same change. The partner primitive is `wait_for_condition` (`mics_task.py:482-495`), which polls
the current state's outgoing transitions, returns on the first satisfied one, and otherwise
`time.sleep(0.0005)` then `yield`. Every GUI-built state ends in `return self.wait_for_condition()`
(`:978`), and MICS-Link's readiness gate reuses the same loop rather than adding a second polling
engine (`:989-992`).

**Why it matters scientifically.** In a home-cage rig, states are long — waiting for an animal to
approach a port can be minutes. An atomic stage means a stop request, a hardware fault or an
end-of-day shutdown is deferred for the whole of that wait, which in practice means data collected
after the experimenter believed the session had ended.

**What Autopilot does instead.** The stage method is atomic: once entered it must return.

**Honest bound.** This trades CPU for interruptibility, and the trade has a number attached. The
500 µs sleep exists specifically to yield the GIL to the trigger worker (the comment at `:494` says
so), which makes it a **busy-poll on the stage thread**. So **the actual state-latency floor of the
FDA is ~250 µs expected / ~500 µs worst case, plus guard-evaluation cost, plus Linux `sleep`
granularity (typically ≳1 ms of jitter under load)**. That floor is *nominal, not measured* — own the
number rather than implying "event-driven". Two clarifications that protect the claim: the floor
applies to the FDA's **reaction**, not to the **record** — an event's timestamp is taken in the
callback thread (A11), so a lick's recorded time does not inherit the poll latency. And Autopilot's
`stage_block` — a zero-cost `threading.Event` wait — is not "kept": it is dead (`task.py:119` `=
None`; `pilot.py:1227`, `task.py:307,402` commented). Write *"structurally preserved, semantically
re-based"*, never *"untouched"*.

**Status:** shipped.

---

## A6 — Automatic event-level logging

**What it is.** The instrument records what it did, without the task author having to declare in
advance which measurements matter.

**Mechanism.** `auto_log(cls)` (`utils/logging_utils.py:8-12`) is a class decorator that re-binds
every non-underscore callable through `log_action`; `log_action` (`:15-101`) branches on the
receiver type and emits either a `Hardware_Event`
(`event_type=self.hardware_type`, `level=int(self.hardware_state)`, `:85-97`) or a tracker `Event`
(`:25-55`). `Event_Dispatcher.dispatch_event` (`Event_Dispatcher.py:65-100`) then samples the pigpio
tick **synchronously in the calling thread** (`:77`) and hands the event to a daemon sender thread
(`:28-32`, `:100`), which wraps it in a fixed envelope (`:38-49`):

```
pilot · subject · session · run_id · task_type · timestamp ·
continuous · session_progress_index · subjects  (+ event: {event_type, event_data[, level]})
```

The design rationale is worth quoting in Methods verbatim (`:70-75`): *"Capture timestamp NOW in the
calling thread — preserves pigpio-clock precision. The tick MUST come from pigpio: it is the single
clock for the whole log system, so there is deliberately NO fallback timebase … If the tick cannot
be read the event is dropped rather than stamped from another clock. What must not happen is
raising: the caller is a hardware/tracker callback, and an exception here unwinds it before its
remaining writes … can run."*

Inputs reach the record by a **second, central** mechanism: `Task.execute_trigger` dispatches a
`Hardware_Event` for every queued trigger before any callback runs (`task.py:272-283`).

**Why it matters scientifically.** The inversion is from *the task describes its data* to *the
instrument describes itself*. Under the former, anything the author did not think to declare is
simply absent from the record forever; under the latter, an analysis question nobody anticipated at
design time is still answerable from the archive. This is what makes the Elasticsearch corpus exist
at all.

**What Autopilot does instead.** `auto_log|log_action` return **0 matches across 518 files** of the
0.4.4 sdist — the single most checkable claim in the paper. Autopilot's `core/loggers.py` is 175
lines of `RotatingFileHandler` *debug* logging that never touches the ZMQ path; its scientific record
is `node.send('T','DATA', <a row of the task's own TrialData>)`, declared column by column by the
task author.

**Honest bound — this is the claim most likely to be over-worded.** `@auto_log` appears **exactly
once repo-wide**: `gpio.py:324`, on `Digital_Out`. `log_action` is hand-applied 13 more times (8 in
`Tracker.py`, 3 in `mixer.py`, 2 in `timer.py`). Not covered: `GPIO` and `Digital_In` (**no sensor
reads are auto-logged**); every `Digital_Out` subclass override, because `auto_log` walks
`cls.__dict__` — `PWM.set`, `TTL.set` (overrides without `super()`, fully invisible),
`LED_RGB.set`, `Solenoid_mics`, `Pulse20Hz`; **all of `i2c.py`, which imports `log_action` at `:11`
and applies it zero times — so the capacitive lickometer itself is not decorator-logged**;
underscore methods; and properties (a `property` is not `callable`, so `:10` skips it). Lick
detection reaches the record by a *third* path again — `learning_cage.detectedLick` (`:167-176`)
writes the view, and `Tracker.set` is `@log_action`.

> **Defensible wording:** *"Output-driver methods are instrumented by decorator and input events by a
> single central handler, so the record is produced by the framework rather than declared by the task
> author."*
> **Indefensible wording:** *"All hardware events are logged automatically."* A reviewer who opens
> `gpio.py` finds one decorator.

Two corpus artefacts must be disclosed alongside it (see Part D): the **`*_and_notify` double-emit**
— all eight helpers double, not six (`mics_task.py:396-403,405-409,419-433,444-451,453-456,459-463,
465-473`) — and the **dual `event_type` vocabulary** (`logging_utils.py:91` vs `mics_task.py:385`).
Also: the drop counters `_dropped_no_clock`/`_dropped_on_send` (`Event_Dispatcher.py:24-26`) are
**in-process only, never dispatched, never persisted**, so *"did every event make it home?"* is
answerable only by attaching to a live process; and `stop()` joins the sender thread with a 2 s
timeout (`:60-63`), so a slow drain at task end silently truncates.

**Status:** shipped-but-narrower.

---

## A7 — `View`: one uniform, named read surface

**What it is.** Everything a task's logic can read — a lick sensor, a valve's state, a counter, a
declared variable — is reachable by a single string name through one call.

**Mechanism.** `core/View.py` is 44 lines: a plain dict plus one reader,
`get_value(name) → self.view[name].get_state()` (`:43-44`). Three kinds of object end up in it, all
answering `get_state()` — raw `Hardware` inserted by `Task.init_hardware` (`task.py:204`) and by the
semantic-name registration (`mics_task.py:1150-1151`); per-channel detector `Tracker`s
(`mics_task.py:365`); and flag/variable `Tracker`s (`:379`, `:1174`). `Hardware.get_state` is
`hardware/__init__.py:152-153`; `Tracker.get_state` is `Tracker.py:25-26`. That duck-typed pair is
the entire mechanism.

**Why it matters scientifically.** The contribution is not the code — it is the **invariant**: every
quantity a transition may read has (i) a string name, (ii) a synchronous non-blocking read and
(iii) — because every writer is `@log_action`-decorated — a logged write. That is exactly what lets
an FDA condition be *data* (`{"view": "LICKER2"}`, `mics_task.py:647-651`) instead of a Python
lambda over hardware objects, which in turn is what lets the backend validate a transition before
dispatch (`view_key_unresolved`, `variable_never_written`, `state_wait_unsatisfiable` —
`toolkit_dispatch.py:160-165`). **Remove `View` and the GUI-authored task cannot exist.** The right
posture in review: *yes, it is a dict, and that is a virtue — it is the cheapest possible
implementation of the invariant that makes the task graph a validatable data structure.*

**What Autopilot does instead.** Nothing comparable — no view, no named-value registry. Its answer
is "read the hardware object directly inside your Python stage method."

**Honest bound.** The uniformity is **not enforced**. `self.view.view` is a plain dict holding raw
`Hardware` objects whose `.set()` can physically actuate a device, and `mics_task.py:855-861` is a
runtime `TypeError` guard documenting exactly that hazard — a patch over a missing type boundary.
`get_value` has **no `KeyError` handling** (`View.py:43-44`), so a missing key is an uncaught
exception inside a transition lambda on the stage thread. Reads are **unsynchronised**: trigger
callbacks write on the worker thread while `wait_for_condition` polls on the stage thread, and
correctness rests on CPython dict atomicity, not a lock. And there is an inconsistency worth knowing
before a reviewer finds it: the `hardware` *operand* reads `_hw.value` (`:675`) while `_resolve_arg`'s
`view` branch reads `.get_state()` with an explicit correction comment (`:557-559`).

**Status:** shipped.

---

## A8 — Trackers, flags and declared variables

**What it is.** The task's own state — trial counters, boolean flags, arbitrary variables declared
in the editor — lives in the same named namespace as hardware, and every change to it is recorded.

**Mechanism.** `Tracker` (`utils/Tracker.py`, 100 lines) and its subclasses `Boolean_Tracker`
(`:28-47`), `Counter_Tracker` (`:50-68`) and `Trial_Tracker` (`:71-98`) each carry a name, a value,
an `event_dispatcher` and a `get_state()`. `increment` and `set` are `@log_action`-decorated
(`:15`, `:20`, `:37`, `:43`, `:59`, `:64`, `:81`, `:94`), so a state change to task-owned state
produces an event exactly as a hardware action does. `Trial_Tracker.increment` is special: it
dispatches with `key='INC_TRIAL_COUNTER'` (`:91`) rather than the default `'CONTINUOUS'` and adds
`trial_num` to the payload (`:84-86`) — this is the path that reaches the backend's graduation
check. A toolkit declares its own flags in `FLAGS` and `init_flags` registers each one **twice, as
the same object**, in `self.flags` and `self.view.view` (`mics_task.py:367-379`, esp. `:378-379`);
backend-supplied flag types are mapped from strings by `_resolve_flags` (`:273-299`). GUI-declared
variables use the identical double registration (`:1173-1174`). `Mics_Tracker`
(`utils/Mics_Tracker.py`, 4 lines) is a pure marker base whose only job is the `isinstance` dispatch
at `logging_utils.py:25`.

**Why it matters scientifically.** The failure it prevents is task state being invisible. Any
quantity the task itself computes — trials completed, a probabilistic draw, a running criterion — is
otherwise a Python local that never leaves the process, so a post-hoc analysis cannot tell whether
the task believed what the analyst believes. Registering the same object in both the flag namespace
and the read namespace is what makes such a quantity simultaneously writable by an action, readable
by a guard, validatable by the backend, and visible in the event stream.

**What Autopilot does instead.** Task state is Python instance attributes; only what `TrialData`
declares reaches the record, and it reaches it once per trial rather than at the moment it changes.

**Honest bound.** `log_action`'s tracker branch only emits for method names `increment` and `set`
(`logging_utils.py:30-39`); **any other decorated method returns early without logging**, so
`Boolean_Tracker.toggle` is decorated (`Tracker.py:37`) and silently emits nothing. The dispatcher
lookup is unguarded — `getattr(self, 'event_dispatcher', None)` (`:22`) can be `None` and `:55`/`:97`
call it unconditionally, raising inside the driver call. And `Mics_Tracker.__init__` is missing
`self` (`Mics_Tracker.py:2-4`) — dead-wrong code sitting in the type-dispatch spine of the logging
system, harmless only because no subclass ever calls it.

**Status:** shipped.

---

## A9 — Semantic hardware naming

**What it is.** Task logic names a *reward port*, not GPIO pin 35. Each rig's own configuration says
what a reward port is on that rig.

**Mechanism.** A toolkit declares `SEMANTIC_HARDWARE = {"reward_port": ("GPIO","VALVE1"), "cue_led":
("GPIO","LED2"), "lick_sensor": ("i2c","LICKER1")}` (`mics_task.py:67-79`), plus
`SEMANTIC_HARDWARE_RENAMES` for deprecated names (`:81-88`). At load, both maps are merged **across
the whole MRO, base → derived, using `cls.__dict__` rather than `getattr`**, so a subclass adding
entries cannot shadow a parent's (`load_fda_from_json:1114-1128`); per-**definition** overrides
(`semantic_hardware_overrides`) are applied last (`:1121-1122`), so the stored document has final
say. Resolution to real objects raises a load-time `KeyError` naming the missing group/id
(`:1130-1139`). Modules-group ids are additionally registered directly so GUI-built definitions can
use module names as refs (`:1141-1146`), and every semantic name is registered in the view so
`{"view": "cue_led"}` resolves (`:1148-1151`). Renames are applied to both states
(`_resolve_renamed_hw_refs`, `:1271-1310`) and triggers (`_resolve_renamed_trigger_refs`,
`:1312-1359`).

The multi-electrode case is handled by the same principle. `check_for_detectors`
(`mics_task.py:301-365`) derives per-channel view keys from that rig's declared `first_channel` and
`num_detectors`, with the invariant that **the tracker name always equals the raw hardware channel
index** — `LICKER1` is seeded from `curr_vals[1]`, never `curr_vals[0]` (docstring `:316-319`). A
condition names `{"ref": "MPR121", "channel": 2}` and the per-pilot literal `"LICKER"` never appears
in a task definition; the shared derivation `detector_channel_key` is used at build time
(`_build_condition_operand:620-645`) and the device name is resolved from the action's own source
hardware **at call time** in `view` actions (`:807-811`, whose comment states the rule: *"the literal
'LICKER' is per-pilot data … not something a task definition may hard-code"*).

**Why it matters scientifically.** The failure it prevents is a protocol that is silently
rig-specific. Renaming a hardware group, or moving an animal to the rig next door with a different
pin map, otherwise breaks every stored protocol that named the old thing — and breaks it *silently*,
because a wrong pin still actuates something. Semantic naming plus load-time resolution turns that
into a named error before the run starts.

**What Autopilot does instead.** Task code names `self.hardware['PORTS']['L']` directly. There is no
indirection and no rename map.

**Honest bound.** Detector capability is checked by **duck typing, not `isinstance`**
(`_has_detector_capability`, `mics_task.py:43-58`) — and the docstring records why, which is a real
silent-data-loss incident: a detector shipped from the database is `exec`'d into a fresh namespace,
so it is a *different class object* from the module's own class, and *"identity matching yields zero
detectors, no LICKER trackers, and a view action that writes a key which does not exist: no
exception, no data."* Also, the channel-count check raises at **task construction**, not at preflight
(`:350-357`), so this particular misconfiguration surfaces later than the others. And renames only
work **forward** and only if the toolkit author maintains the map.

**Status:** shipped.

---

## A10 — Per-run hardware-library shipping and `sys.path` injection

**What it is.** The driver code a run will use is sent to the rig from the database at dispatch time,
rather than being whatever happens to be installed on that rig.

**Mechanism.** The orchestrator sends `LOAD_HARDWARE_LIBS` **before** `START`
(`orchestrator_station.py:925-968`, send at `:961-968`, logged with filename, `version_id` and the
resolution `reason` at `:957-960`). The Pi's handler (`pilot.py:670-691`, key registered at `:224`)
writes each lib to `~/apps/hardware_overrides` and does
`sys.path.insert(0, override_dir)` — **ahead of the installed package** (`pilot.py:36-46`, insert at
`:42`), at module level, above the `autopilot` import. `mics_task._resolve_hardware_classes`
(`:206-231`) then `exec`s each source into a **fresh namespace** (`:221-223`) before
`init_hardware()` runs (`__init__:111-112`, `:128`). `_merge_prefs_hardware` (`:233-252`) replaces
**whole prefs groups** — its docstring is the authoritative-backend statement: *"The backend is
authoritative: any group it sends fully replaces the Pi's prefs.json entries for that group, so
removed entries don't silently persist"* (`:234-239`); groups absent from the payload are left
alone. Finally the Pi round-trips a **real `importlib.import_module` on the target rig**, bound to a
`version_id`, back as `HARDWARE_LIB_TEST_RESULT` (`pilot.py:680-691` →
`orchestrator_station.py:970-980` → `hardware_libs.py:519-538`).

**Why it matters scientifically.** The failure it prevents is drift across a rig fleet. With drivers
as files on eight Pis, the answer to "which valve-timing code ran this cohort?" is a guess, and the
divergence is invisible because every rig still runs. Shipping the source per run makes the rig's
executable state a function of the dispatch, not of its own history — and the on-rig import test
means a version is marked usable only after the machine that will run it has actually imported it.

**What Autopilot does instead.** `PLUGINDIR` plus files on each Pi, and nothing anywhere records
which file ran.

**Honest bound.** (i) **The `exec` is unsandboxed** (`mics_task.py:222`); the upload gate is
`ast.parse` + `py_compile(doraise=True)` (`hardware_libs.py:91-107`), a *syntax* check. Anyone who
can POST a hardware lib gets code execution on every Pi running a toolkit that uses it. This belongs
in limitations, not claims. (ii) Files persist in `~/apps/hardware_overrides` across runs and nothing
cleans them up. (iii) The DB's initial content came from the file it replaces —
`pilot_hardware_config` is seeded from the Pi's `prefs.json` at HANDSHAKE
(`orchestrator_station.py:140-142`). (iv) **Scope the claim to hardware libraries.** Task *classes*
still resolve through Autopilot's plugin registry (`pilot.py:526`, `:593`; `utils/plugins.py`;
`AUTOPLUGIN=true`; 28 files in `pilot/plugins/`), as do legacy hardware groups
(`task.py:182-184`). Correct sentence: *"driver code for backend-managed modules is delivered from
the database; task classes and legacy hardware groups still resolve from the Pi's plugin directory
and prefs."* Anything stronger is falsifiable in one grep. (v) There is **no record on the run of
which version was shipped** — see **F2** and B5b.

**Status:** shipped (with F2 outstanding for the provenance half).

---

## A11 — The microsecond event timebase

**What it is.** Every event recorded on a rig is stamped from one shared, microsecond-resolution
clock derived from the GPIO hardware, so events within a rig are ordered and spaced accurately.

**Mechanism, and the credit clause.** ⚠️ **The microsecond capability is Autopilot's, not MICS's, and
the manuscript must say so.** Autopilot pins a **forked pigpio**
(`autopilot/requirements/requirements_pilot.txt:18` — the line is *identical at `30c8d3c`*) whose
documented purpose is stated in Autopilot's own README: *"Timestamps from GPIO events are now
microsecond-precise thanks to some modifications to the pigpio library"* (`README.md:130`; echoed at
`gpio.py:7` and `:790`). `synchronize()` and `ticks_to_timestamp()` are **that fork's API** — neither
name is defined anywhere in either repository, only called. **MICS must not claim microsecond
timestamping as its own contribution.** It is a library dependency, not architecture; credit it in a
clause and move on.

What MICS adds, and may claim: **one shared, synchronised pigpio client per run, threaded into every
device.** `pilot.py:1139` opens `pigpio.pi(sync_ticks=True)`, `:1145` calls `synchronize()` once
before any hardware is constructed, and `:1159` passes the single client into the task
(`task.py:135-137` raises if it is absent; `:138`, `:191`, `:194` thread it into the dispatcher and
every device). Autopilot lets each hardware object open its own connection. MICS also adds **the
event stream to put the clock into** — Autopilot has no per-event stream at all — and a careful
detail worth a clause: a **thread-local trigger context** (`mics_task.py:1515-1519`, `:1530-1539`)
so that every tracker write occurring inside a trigger is stamped with **that trigger's firing
edge**, not with the time the write happened (`:864-869`), with the hand-written analogue at
`learning_cage.py:174`. The analysis-grade time is `event_data.pi_timestamp`, carried from the GPIO
edge through `handle_trigger(pin, level, tick, hardware)` (`task.py:335`, `:373`) into
`execute_trigger` (`:275-276`).

**Why it matters scientifically.** Behavioural latencies — lick-to-reward, cue-to-response — are the
measurement. A timebase sampled when a software log call happened rather than when the edge occurred
measures the software, not the animal.

**What Autopilot does instead.** It *supplies* this timebase. Do not write *"Autopilot has no clock
synchronisation"* — that is false, and false in the direction that flatters us. Write: *"Autopilot
provides within-station tick↔wall-clock alignment and no cross-machine synchronisation; MICS wires
that clock into a per-event stream Autopilot has no equivalent of."*

**Honest bound.**
- **Two clocks appear on one document.** The envelope `timestamp` (`Event_Dispatcher.py:44`) is the
  tick sampled at `dispatch_event` time (`:77`) — i.e. when the log call was made — while
  `event_data.pi_timestamp` is the GPIO edge itself. The gap between them is the trigger-queue
  latency, which is **queue-depth-dependent and unbounded** (the queue has no `maxsize`). Anyone
  using `timestamp` for lick latencies is measuring the queue. Publish the rule with the corpus.
- **Two representations under one field name.** `task.py:275` passes the tick through `localize_tz`
  (`utils/common.py:329-334`), which parses an **ISO string**, while `mics_task.py:867-869` injects
  the **raw** `_trigger_ctx.tick` with no conversion.
- **The fork has no in-repo provenance.** `synchronize()`/`ticks_to_timestamp()` are called and
  nowhere defined; pigpio is not vendored. For the paper this needs an external citation (fork URL +
  commit) **that does not currently exist in the repository** — 🔶 *unsourced, must be obtained.*
  Relatedly, pigpio's tick is a 32-bit µs counter that wraps at ~71.6 minutes and nothing in this
  tree handles the wrap, so whatever handles it lives in the fork.
- **The alignment is established once per run and never re-established** (`:1145`), and the wall
  clock is neither synchronised before a run nor frozen during it, because both NTP call sites are
  commented out (`pilot.py:1138`, `:1148`).
- **There is no cross-rig or cross-instrument timeline.** See **F5**, Part C and Part D.

**Status:** shipped-but-narrower (credit clause mandatory).

---

# Part B — Backend (MICS-Portal)

## B1 — The relational model: colony, protocol and execution in one schema

**What it is.** Animals, the people responsible for them, the projects and experiments they belong
to, their surgeries and weights, the ethics protocol they run under, the rigs, the sessions, the
individual runs and each run's progression are all rows in one database that can be queried
together.

**Mechanism.** **28 Postgres tables** in `api/models.py` (833 lines), split 12 SQLModel /
16 SQLAlchemy, with both metadata trees created at startup (`api/main.py:136,139`) and two tables
additionally created by raw SQL for migration on existing deployments (`api/db.py:176`, `:299`).

*Colony / science domain (SQLModel, 12):* `subjects` (`:31`), `subject_protocol_runs` (`:67`),
`protocol_templates` (`:83`), `protocol_step_templates` (`:92`), `researchers` (`:115`),
`iacuc_protocols` (`:124`), `projects` (`:133`), `experiments` (`:145`), `experiment_protocols`
(`:155`), `subject_projects` (`:161`), `weight_measurements` (`:167`), `subject_surgeries` (`:176`).

*Rig / execution domain (SQLAlchemy, 16):* `pilots` (`:374`), `sessions` (`:410`), `session_runs`
(`:432`), `run_progress` (`:468`), `task_definitions` (`:510`), `task_inheritance` (`:532`),
`pilot_task_capabilities` (`:548`), `task_toolkits` (`:593`), `toolkit_pilot_origins` (`:619`),
`hardware_lib_versions` (`:640`), `hardware_libs` (`:658`), `toolkit_hardware_libs` (`:680`),
`hardware_modules` (`:696`), `pilot_hardware_config` (`:708`), `device_leases` (`:727`),
`available_locked_states` (`:745`).

Load-bearing columns for the paper: `sessions(id, name, created_at, label, run_counter)` (`:409-420`);
`session_runs(id, session_id, pilot_id, subject_key, status, started_at, ended_at, error_type,
error_message, mode, overrides, session_run_index)` (`:431-463`) with `status ∈
{RUNNING, STOPPED, COMPLETED, ERROR, PENDING}` (`:423-428`); `run_progress(id, run_id,
current_step_idx, current_trial, graduation_type, graduation_params, updated_at,
session_progress_index)` (`:467-481`). Note the table backing "toolkits" is named `task_toolkits`
(`:592-615`), carrying `semantic_hardware`, `callable_methods`, `states`, `flags`, `params_schema`,
`required_packages` and a `UniqueConstraint(name, hw_hash)`.

**Why it matters scientifically.** The failure it prevents is the *unaskable question*. With one
file per animal, "which animals in this cohort ran this protocol version on rigs that had driver X"
is not an expensive query — it has no representation. Making colony, protocol and execution one
schema converts curation questions from archaeology into SQL, and it is what allows the ethics
protocol, the responsible researcher and the surgical history to be attached to the animal rather
than to a spreadsheet beside it.

**What Autopilot does instead.** One HDF5 file per subject and no cross-subject query of any kind.
Its persistent coordination state is `pilot_db.json` — pilot → subject/IP, nothing more.

**Honest bound.** **The dual-ORM seam is a scar, not a design.** Three joins are bare integers with
no foreign key: `SubjectProtocolRun.session_id` (`models.py:75`), `Subject.lead_researcher_id`
(`:56`, with the in-code comment *"bare int — no FK constraint (no migration for existing DBs)"*) and
`ProtocolStepTemplate.task_definition_id` (`:107`). **The most important join in the system —
session ↔ subject — is not enforced by the database.** It is convention, not constraint. Say so; a
reviewer who opens the schema will find it in a minute. Also state the count as **28 and date it**:
27 was correct on 2026-08-06, and the 28th (`device_leases`) landed 2026-08-09.

**Status:** shipped.

---

## B2 — The event stream, with full run context on every document

**What it is.** Every recorded event carries, on the document itself, which rig produced it, which
run and session it belongs to, which animals were in that session, and where the animal was in its
training trajectory.

**Mechanism.** Elasticsearch `event_log_v2` receives one document per event. The envelope is stamped
on the Pi (`Event_Dispatcher.py:38-49`) with `pilot, subject, session, run_id, task_type, timestamp,
continuous, session_progress_index, subjects` plus the event body; the orchestrator attaches session
context (`_attach_session_context`, `orchestrator_station.py:1175-1210`) and owns ingestion entirely
(`:245-249`, `:554`). The Pi writes to no database — its sole egress is ZMQ.

**Why it matters scientifically.** The failure it prevents is a corpus that cannot be re-segmented.
When context lives in filenames or in a lab notebook, an analysis that wants to pool by cohort, by
trajectory step or by rig has to reconstruct the mapping — and every reconstruction is a place where
a mislabelled animal enters the dataset. Stamping `run_id` and `session_progress_index` on the
document means every record names its run and its position in the training trajectory, and cohort
membership is recoverable from the event stream alone.

**What Autopilot does instead.** Its record is a row of the task's declared `TrialData` written into
that animal's own HDF5 file. The context is the file path.

**Honest bound.**
- **`subject` in Elasticsearch is a run key, not an animal**: `bp_s{session_id}_r{run_id}`
  (`main.py:1375`, `:1305`). The animals are in the `subjects` list. Anyone reusing the corpus will
  read it as an animal ID. **Document it or rename it.**
- **Drop "experiment name."** The envelope's mapped top-level fields are exactly
  `continuous, event, pilot, run_id, session, session_progress_index, subject, subjects, task_type,
  timestamp`. `run_id` *is* there; experiment name is not.
- **Methods caveat that must survive to the manuscript:** the historically analysed corpus
  (`restored-event_log_v2` on `.125`) has **no `run_id` field** — name the index per figure.
- Ingestion robustness is thin if the paper says anything about data integrity: one `client.index()`
  per document, no bulk, no retry, no dead-letter, `except: print`
  (`ElasticSearchDateHandler.py:55-56`), host hardcoded (`:17`, `:74`).
- Two event vocabularies and the `*_and_notify` double-emit are properties of this corpus — Part D.

**Status:** shipped.

---

## B3 — Task authoring without writing code

**What it is.** A researcher builds a task by drawing states on a canvas, choosing what happens in
each state, and stating the conditions that move the animal from one to the next — then saves it and
runs it.

**Mechanism, verified end to end.** Author on a react-flow canvas (`pages/task-editor/TaskEditor.tsx`,
806 lines; `<ReactFlow>` at `:585-626`, transitions drawn by dragging via `onConnect` at `:287`/`:592`,
debounced autosave at `:266`) supported by `TriggerAssignmentPanel.tsx` (399 L), `ActionEditor.tsx`
(333 L), `ConditionGroupsEditor.tsx` (230 L), `ArgInput.tsx` (219 L), `ConditionBuilder.tsx` (198 L),
`VariablesPanel.tsx` (159 L), `OutputCapture.tsx` (92 L) and `argModes.mts` (75 L). The editor offers
**seven author-selectable action types** (`ActionEditor.tsx:204-220`: hardware, trial counter, flag,
compute, view, method, if — `special` renders read-only as a legacy chip at `:180-189`) against a
closed backend vocabulary of eight (`api/fda_validation.py:43`) and the Pi's closed 8-branch table
(`mics_task.py:725-876`). Each action argument is set in one of **four offered modes**
(`argModes.mts:67`: literal, param, view, trigger; a fifth, `flag`, exists only to round-trip an
already-stored operand, `:65-66`) with user-facing tooltips at `:57-63`.

`POST/PUT /task-definitions` (`routers/toolkits.py:597`, `:840`) runs `reject_if_hard_errors`
(`api/fda_validation.py:300-331`, five passes against closed vocabularies) **before writing**, 422s
on hard failure, and marks soft failures `validation_status='broken'`. The stored FDA is
content-addressed: `file_hash = sha256(json.dumps(fda_json, sort_keys=True))`
(`routers/toolkits.py:605-609`); the `fda_json` JSONB column itself is migration-created
(`api/db.py:65`).

**Why it matters scientifically.** The failure it prevents is the queue at the programmer's desk.
When every protocol variant needs a code change, the set of experiments that get run is bounded by
one person's availability, pilot variants do not get tried, and the version that ran is whatever was
on the rig that week. Composition-as-data also means a protocol change is reviewable by the PI who
designed the experiment, not only by whoever can read the class.

**What Autopilot does instead.** `Protocol_Wizard` and `Graduation_Widget` (`gui.py:1201`, `:1374`)
compose steps and set numbers **over a task someone already wrote in Python**. That is a parameter
form, not a task-authoring system — but state it fairly: it is a decade of genuinely useful
operational tooling.

**Honest bound — two sentences the manuscript must absorb.**
1. **"No code" is precise only for state-machine composition.** The primitive layer is Python, and
   the system ships a **CodeMirror Python editor in the browser**
   (`HardwareLibDetail.tsx:4-6,236-243`) whose output the Pi `exec`s (`mics_task.py:222`). **That
   relocates the coding into the browser; it does not eliminate it.** A Python class must also still
   exist on the Pi to be the `task_type` (`toolkit_dispatch.py:143,149` falls back to `mics_task`),
   and `pilot/plugins/` holds 28–29 hand-written task files. **Defensible:** *"composing and
   modifying task logic — states, transitions, conditions, actions, variables — no longer requires
   writing or deploying code; authoring a new hardware primitive still does."*
2. **Adoption is light** — 27 of 157 task definitions have a non-null `fda_json` (⚠️ re-derive and
   date this figure; no SQL is recorded). Definitions **179 / 181 / 185** are the genuine
   zero-Python demonstrations; definitions 124, 155 and 157 are 100 % passthrough name-lists over
   Python methods. **Be precise about which experiments were run which way.**

What still requires Python, stated plainly: hardware drivers, compute ops, Pi task plugins, and any
graduation criterion beyond `NTrials` (the UI offers only `NTrials`, `ProtocolsCreate.tsx:97-99`).

**Status:** shipped-but-narrower.

---

## B4 — One task definition, many rigs

**What it is.** The same stored task runs on a different rig — different pins, different driver
classes, a different number of lick electrodes — without editing it.

**Mechanism.** Four mechanisms make this true, and it is worth naming all four because "portable"
without them is an assertion:

1. **Semantic hardware resolved per class and merged across the MRO** so a subclass cannot shadow a
   parent (`mics_task.py:1114-1128`), with per-definition overrides applied last (`:1121-1122`).
2. **Per-pilot `pilot_hardware_config`**, keyed `(pilot_id, name)` (`models.py:707-715`), which
   **replaces whole prefs groups** on the rig at load (`_merge_prefs_hardware`,
   `mics_task.py:233-252`) — the Pi's `prefs.json` is no longer the source of truth.
3. **Driver classes shipped from the database** per run (A10), so "the class named `Solenoid_mics`"
   means the same source on every rig in the fleet.
4. **Detector view keys derived from that rig's declared `first_channel` + `num_detectors`**
   (`mics_task.py:301-365`), so `LICKER0..3` on one rig and `LICKER4..7` on another both resolve from
   the same `{"ref": "MPR121", "channel": 2}`.

**Why it matters scientifically.** The failure it prevents is fleet divergence: the same nominal
protocol quietly becoming N slightly different protocols, one per rig, with the differences
invisible in the data. It is also what makes a rig fungible — an animal can be moved to another box
mid-cohort without a protocol edit.

**What Autopilot does instead.** Per-rig `prefs.json` maps a logical name to a pin, which handles the
pin-map half. It has no answer for driver-code divergence, no rename indirection, and no per-channel
key derivation.

**Honest bound — scope it to fully GUI-built definitions**, and name the five ways it still breaks:
**passthrough states**, whose behaviour is a Python method on *that Pi's* class (`mics_task.py:906`);
**`CALLABLE_METHODS`**, which fails at load with `ValueError` if the target class does not whitelist
the name (`:914-919`); **detector channel keys**, where a different electrode count or device name
yields different keys — and this one fails at *task construction*, not preflight (`:350-357`);
**non-`Modules` hardware**, reachable only through a semantic alias (`:1141-1146`); and **rename
maps**, which work only forward and only if maintained (plus hardcoded trigger wiring in base
classes, e.g. the literal `'TOUCH_INT'` at `learning_cage.py:139`).

**Status:** shipped-but-narrower.

---

## B5 — Drivers and rig configuration as versioned, validated database artifacts

**What it is.** The code that drives a valve or reads a lickometer, and the configuration that says
which pin it uses on which rig, are versioned records in the database with a review lifecycle —
not files edited in place on eight machines.

**Mechanism.** `hardware_lib_versions` rows (`models.py:639-654`) carry `version_number`,
`source_code` (Text), `sha256_hash`, `state ∈ {unvalidated, beta, stable}`, `ast_metadata`,
`declared_imports`, `stable_at`, `stable_reason ∈ {user, protocol_run}`, `stable_pilot` and
`validation_error`; `hardware_libs` (`:657-676`) points at an `active_version_id` and a
`stable_version_id`. Upload is gated by `ast.parse` + `py_compile(doraise=True)`
(`routers/hardware_libs.py:91-107`), and the extracted AST structure becomes what the task editor
offers the author. Resolution is centralised in **one** implementation — `pin → toolkit_default →
stable → active → none` (`lib_version_resolution.py:33-92`), whose docstring documents the exact bug
of having previously had two divergent copies — with `lib_version_unresolved` raised at preflight.
Dispatch embeds `class_name` + `source_code` in START (`toolkit_dispatch.py:36-122`), and the rig
round-trips a **real import test bound to a `version_id`** (A10). Rig configuration is the parallel
artifact: `pilot_hardware_config(pilot_id, name, config JSON)` with
`UniqueConstraint(pilot_id, name)` (`models.py:707-715`).

**Why it matters scientifically.** The failure it prevents is the unanswerable methods question. When
a driver is a file on a rig, "was the valve-open routine the same for cohort 1 and cohort 2?" has no
answer, and the honest Methods section can only describe the *intent*. Immutable version rows,
content hashes, rollback-as-new-version rather than mutation, and a promotion state that only
advances after the target machine has actually imported the code, together make the executable
history of the fleet a queryable record.

**What Autopilot does instead.** A driver is a file on eight Pis, and **nothing anywhere records
which one ran**. Against that baseline this is a genuine and large advance — but see the bound.

**Honest bound — this is the paper's most dangerous over-claim if worded loosely.**
- ⚠️ **`session_runs` has no version column and there is no run↔version join table.** Its twelve
  columns are listed in B1; none is a version. What is recorded is **the resolution policy**, not the
  resolution: reconstructing what ran means replaying the chain against `stable_version_id` /
  `active_version_id` / `toolkit_hardware_libs.default_version_id` / `task_definitions.hw_lib_versions`
  — **all mutable after the run**. Promote a new stable and yesterday's run silently re-resolves to
  different source. **Defensible today:** *"the resolution is deterministic and the pin is recorded on
  the specification"* — **not** *"recorded against the run."* **F2 fixes this with one column.**
- **`stable_reason='protocol_run'` means less than the label suggests.**
  `promote_active_hw_libs_to_stable` is called from the **`INC_TRIAL_COUNTER` handler**
  (`orchestrator_station.py:599-614`) — on *every trial increment*, not at run completion — and
  `mark_stable` promotes `lib.active_version_id` (`hardware_libs.py:541-563`), **not** the version
  dispatched for this run. Upload a new version mid-session and the newly active one is stamped
  `protocol_run` on the next trial, credited with a run it never participated in. Stop describing it
  as "earned by carrying a run."
- **The `exec()` is unsandboxed** (A10) — limitations, not claims.
- **The database was seeded from the file it replaces** (`orchestrator_station.py:140-142`).

**Status:** shipped. **B5b (per-run version provenance): one-fix-from-true — F2.**

---

## B6 — Pre-dispatch static validation, including the deadlock detector

**What it is.** Before a task is sent to a rig, the system checks the task graph for problems a human
would not catch by reading it — including states the animal could enter and never leave.

**Mechanism.** `PREFLIGHT_ISSUE_KINDS` (`api/routers/toolkit_dispatch.py:155-167`) holds **11**
kinds; `compute_lib_import_failed` is explicitly RESERVED and never emitted (`:163`, shape builder
`:170-179`), so **10 are emittable**:

| Kind | What it checks | Emit site |
|---|---|---|
| `missing` | no `pilot_hardware_config` row for a required module | `:350-359` |
| `incomplete_config` | a module's config has no keys beyond `class_name` | `:389-397` |
| `class_mismatch` | stored `class_name` ≠ the module's declared class | `:400-413` |
| `fda_ref_unresolved` | an FDA hardware action refs a name this pilot has no config for | `:415-439` |
| `view_key_unresolved` | a view/detector operand resolves to no real key on this pilot | `:447-474` |
| `variable_never_written` | a transition reads a variable nothing ever writes | `:478-484` |
| `lib_version_unresolved` | no beta/stable version is deployable for a library | `:321-340` |
| `state_wait_unsatisfiable` | **every** exit from a state is blocked by a value frozen on entry | `:488-494` |
| `device_held` | another pilot's run already holds this external device's lease | `:496-499` |
| `extlink_config_invalid` | an external-instrument module's config fails field validation | `:496-499` |
| *(reserved)* `compute_lib_import_failed` | — | never emitted |

Two of these are real static analyses. **`variable_never_written`** (`api/variable_scan.py`) walks
every state's `entry_actions` *and* `trigger_assignments`, recursing into `if`/`then`/`else`
(`:39-62`), collecting writers from `output` slots, `flag` actions and non-null `initial_value` —
and **its own docstring (`:4-13`) states its narrowing: it is an *existence* check, not graph
reachability.** Quote that self-limitation rather than paper over it.

**`state_wait_unsatisfiable`** (`api/wait_analysis.py`) is the strongest single item in the audit.
Entry actions run once on entry, so a wait condition reading a variable those actions wrote can never
change. The pass computes each state's entry-frozen write set, then requires that **every** outgoing
transition be blocked by a frozen comparison, descending only AND branches (an OR could be satisfied
elsewhere) and exempting complementary operator pairs (`>=`/`<`, `>`/`<=`, `==`/`!=`) so a legitimate
probabilistic branch is not reported. **A sound, deliberately conservative deadlock detector** — and
its docstring names the real, dated in-the-wild incident it was written for: **task definition 186,
run 541**, where `rand` drew `my_rand` on entry, the only exit required `my_rand >= 0.5`, and every
low draw parked the task permanently *while the pilot went on logging licks*. That anecdote is the
strongest available: a silent hang that produced a plausible-looking, useless session.

Every analysis step is wrapped in its own try/except that logs and continues (`:478-499`), so a scan
failure degrades to "no issue", never a 500.

**Why it matters scientifically.** Wasted animal time is not recoverable, and a hung task is worse
than a crashed one: the crash is visible, the hang produces a file. Static analysis before dispatch
is the only point at which such a defect can be caught without an animal in the box.

**What Autopilot does instead — verified twice.** `toggle_start()` (`terminal.py:516-573`) prompts for
a weight, calls `prepare_run()` and sends `START`. A regex for `valid|verif|preflight|precondition`
over `git show 30c8d3c:…/terminal.py` returns **exit 1, zero matches**. Autopilot has no pre-run
validation **and no TODO expressing an intent to add one** — do *not* cite the `:565` "coherence
checking ritual" TODO, which sits in the *stopping* branch and concerns post-hoc data reconciliation.

**Honest bound — this is a code bug, not a wording problem. Preflight does not block.** See **F1**.
Defensible today: **"MICS performs static analysis of the task graph before dispatch and surfaces
provable deadlocks to the operator."** Also: `variable_never_written` must lose the word "upstream"
(it is existence, not reachability), and `compute_lib_import_failed` is advertised protection that
does not exist.

**Status:** shipped (analysis) · **one-fix-from-true (enforcement) — F1.**

---

## B7 — Multi-subject sessions

**What it is.** A session is one experimental event that can span several animals on several rigs,
and every event knows which cohort it came from.

**Mechanism.** Three layers. `_start_session_for_pending_subjects` (`api/main.py:783-842`) allocates
**one** `session_id` and creates one `SubjectProtocolRun` per subject. `session_runs`
(`models.py:431-463`) attaches N *executions* to that session, each on its own `pilot_id`, each with
a `session_run_index` allocated under `SELECT … FOR UPDATE` on `Session.run_counter`
(`main.py:1330-1337`) — so a session spans rigs. And the `subjects` list is stamped onto **every
Elasticsearch document** (`_attach_session_context`, `orchestrator_station.py:1175-1210` →
`Event_Dispatcher.py:47`), so cohort membership is recoverable from the event stream alone.

**Why it matters scientifically.** The unit of a home-cage experiment is the cohort-day, not the
animal-run. Without an entity for it, "this cohort's session 12" is a phrase in a lab notebook that
analysis code has to re-derive from timestamps — and re-derive differently in every script.

**What Autopilot does instead.** State this **generously and precisely**, because the naive contrast
is wrong: `Terminal` holds a dict of concurrent `Subject` objects and running four animals at once
was routine. What does not exist is any entity that *groups* them — `session` is a private per-subject
integer in `/info._v_attrs` (`subject.py:170`, `:699-708`), so mouse A's session 5 and mouse B's
session 5 are unrelated integers. **Claim the session as an entity; never claim the concurrency.**

**Honest bound.** The session ↔ subject link is **convention, not constraint**:
`SubjectProtocolRun.session_id` is a bare int with no foreign key (`models.py:75`). And the
per-document `subject` field is a run key, not an animal (B2).

**Status:** shipped.

---

## B8 — Run modes: new / resume / restart

**What it is.** Restarting an interrupted run, resuming it where it left off, and starting a fresh one
are three explicit, different operations with stated consequences.

**Mechanism.** `SessionRun.mode` (`models.py:461`, default `"new"`) is dispatched at
`api/main.py:1243`, after a recoverable-run lookup (`:1248-1262`, filtered to `STOPPED`/`ERROR` and
skipped entirely when mode is `new`). **`resume`** (`:1267-1277`) reuses the row, sets it back to
`PENDING`, clears the error fields and keeps `run_progress` and `session_run_index` by construction —
with an explicit comment that overrides are deliberately *not* touched (`:1274`). **`restart`**
(`:1282-1309`) creates a new row with the **same index** (`:1284`, `:1299`) and inherits overrides
when the caller sends none (`:1288-1290`). **`new`** (`:1312-1344`) creates the session row if
absent, increments `run_counter` under `SELECT … FOR UPDATE`, and does **not** inherit overrides —
the rule is written in the code (`:1339-1343`).

The non-obvious correctness decision worth a clause: `_strip_graduation_from_overrides`
(`main.py:1577-1605`) deletes any inherited `graduation` key, **so a re-run never silently inherits a
stale criterion.**

**Why it matters scientifically.** A rig hiccup two hours into a session is routine, and the wrong
recovery quietly changes the experiment: a "resume" that re-zeroes the trial counter inflates
training exposure, and a "restart" that inherits yesterday's graduation threshold advances an animal
on the wrong evidence. Naming the three operations and giving each explicit progression semantics is
what makes the training history trustworthy.

**What Autopilot does instead.** State this generously too: because `step` and `session` live in the
animal's file rather than in memory, Autopilot **resumes by construction** and never loses
progression to a crash. **MICS's advance is that the lifecycle is modelled and queryable, not that
state survives at all.**

**Honest bound.** These are lifecycle semantics, not scientific adaptivity — do not let them stand in
for the (dropped) adaptive-progression claim. And there is **no pilot busy-check**: the only
`pilot_id` filter in the endpoint is inside the recoverable lookup, and nothing queries for an
existing `PENDING`/`RUNNING` run, so two users can start two runs on one rig (`main.py:1236-1345`).

**Status:** shipped.

---

## B9 — A subject's experimental history, relationally

**What it is.** An animal's identity, biology, responsible researcher, ethics protocol, surgeries,
weights, project membership and protocol history are one connected record.

**Mechanism.** `subjects` (`models.py:30-63`) carries strain, genotype, parents, DOB, sex, RFID,
arrival date, quarantine state, location, holding conditions and group information alongside the
current run and next protocol. Around it: `weight_measurements` (`:166-172`), `subject_surgeries`
(`:175-181`), `subject_projects` (`:160-163`), `projects` → `iacuc_protocols` (`:132-141`, `:123-129`),
`researchers` (`:114-120`), `experiments` (`:144-151`), `experiment_protocols` (`:154-157`), and the
protocol history in `subject_protocol_runs` (`:66-79`). Endpoints:
`GET /subjects/{id}/detail` (`main.py:517-547`) returns weights, surgeries and projects;
`GET /subjects/{name}/runs` (`:191-207`) returns the animal's protocol runs ordered by session.

**Why it matters scientifically.** Colony metadata that lives beside the data instead of inside it is
where cohort-level errors are born — the wrong genotype attached to the wrong animal, a weight series
that cannot be joined to the training curve, an ethics protocol number reconstructed at
submission time. Making it one schema means these are constraints and joins, not conventions.

**Honest bound — and it changes one drafted sentence.** ⚠️ **"A simple query finds all experiments for
a given subject" does not survive contact with the schema.** There is **no `subject_experiments`
table**, and no endpoint answers it: `GET /subjects/{id}/detail` returns projects, not experiments.
Two joins exist and neither is the claimed one — the *membership* path (`subjects ⋈ subject_projects
⋈ projects ⋈ experiments`) returns the **projects'** experiments, an over-approximation; the
*participation* path (`subjects ⋈ subject_protocol_runs ⋈ protocol_templates ⋈ experiment_protocols
⋈ experiments`) is four joins and ambiguous the moment one protocol is attached to two experiments,
which nothing prevents. **Pick a different illustration** — the underlying axis still wins decisively,
because in Autopilot the question is not merely expensive, it is **unaskable**: there is no
experiment concept at all, and any cross-subject question means opening N HDF5 files and parsing
`/history/history` rows by hand.

**Status:** shipped-but-narrower.

---

## B10 — Device leases

**What it is.** When several rigs are configured to talk to the same external instrument, only one
run at a time is allowed to command it.

**Mechanism.** `api/device_lease.py` (293 lines). The lease key is a **normalised host**, not
`host:port` — `normalize_host` (`:36-48`) collapses `"132.77.9.9:37497"`, `"http://132.77.9.9:5556/"`,
`" 132.77.9.9 "` and `"132.77.9.9"` to one key, with the rationale in its docstring: *"Same box on
two ports must be one lease — a `host:port` key would let a second pilot's HTTP-only config quietly
admit a conflicting ZMQ config for the same physical device."* `acquire_lease` (`:176-202`) is an
`INSERT … ON CONFLICT (host) DO NOTHING` followed by a commit and a **read-back**, returning
`(lease["pilot_id"] == pilot_id, lease)` — so atomicity is enforced by a Postgres `UNIQUE` constraint
(`models.py:730`; raw migration `api/db.py:294-312`, wired at `main.py:153`), **never by a
check-then-act in Python**. There is **no TTL**: expiry is reconciliation-driven — `reconcile_leases`
(`:233-263`) releases a lease whose holding pilot is absent from the heartbeat map or whose heartbeat
is older than 90 s, and is pure over an injected map so it is testable with a fabricated timestamp.
The orchestrator acquires at run start (`orchestrator_station.py:386-396`, `_acquire_device_leases`
`:889-923`), releases on clean stop (`:459-466`) and on `TASK_ERROR` (`:513-521`), and runs the
reconcile loop every 15 s (`:999-1045`, interval at `:19`).

**Why it matters scientifically.** Two rigs issuing RECORD to the same acquisition box clobber each
other's session — and the loser is not obviously the loser: both experiments appear to have run. The
Pi cannot arbitrate this itself, because it does not know other rigs exist; the arbitration has to be
central, and it has to be atomic.

**What Autopilot does instead.** Nothing — there is no shared-instrument concept.

**Honest bound.** ⚠️ **The lease is keyed on an external device's host, not on a pilot. It stops two
rigs clobbering one recorder; it does not arbitrate rigs** — there is still no pilot busy-check (B8).
And the module's own docstring states the residual risk: reconciliation *"does NOT reach out to the
foreign device and command it to stop — the backend has no channel to an arbitrary device's control
API, by design"*, so **a crashed pilot can leave an external recorder running until a human notices**
(`:9-14`).

**Status:** shipped, narrow.

---

## B11 — MICS-Link: external instruments as first-class inputs

**What it is.** External software — a pose tracker, an ephys acquisition system — can push values
into a running task, and the task's transitions can read them exactly as they read a lick sensor.

**Mechanism.** Five Pi-side modules, 1,040 lines, with a strict layering rule stated in the source
(`external_hardware_wire.py:3-8`): `external_hardware.py` (239 L, the author-facing
`ExternalHardware` base and four decorators), `external_hardware_wire.py` (290 L, pure logic — codec,
dtypes, roles, stale policy), `external_hardware_runtime.py` (298 L, `EgressWorker`,
`LifecycleRunner`, `LivenessPoller`, readiness gate), `external_hardware_binding.py` (150 L, real
sockets), `external_hardware_ingress.py` (63 L, the ingress firewall).

Three transport roles are *described* by a pure function before any socket exists
(`socket_plan`, `:190-223`): `router_bind` (the Pi binds a ROUTER on `listen_port` and checks
identity), `sub_connect` (the Pi dials out with a SUB socket to a foreign publisher), and `none`
(control-only, **no inbound socket at all** — for a device whose entire inbound story is an outbound
poll, `:182-187`). A missing role raises rather than defaulting (`:223`). The wire format is a
msgpack envelope with five kinds — SIG / EVT / HB / ACK / CMD (`:13-21`) — and a closed dtype set
`{float, int, bool, str}` (`:30`).

The design idea worth claiming is the **`@decoder`**: a per-library hook that translates a foreign
frame into declared signal/event updates, **living in the versioned hardware library rather than in
platform code** (requirement text, `REQUIREMENTS.md:302`), so a third-party wire format is a
promotable per-toolkit artifact a researcher can fix without a platform release. Decorators attach
metadata only (`external_hardware.py:45-61`), are collected across the MRO at class-build time
(`:83-110`), and are extracted **by AST on the backend without importing the module**
(`api/extlink_ast.py:9`, `:82`, `:110-111`). A foreign decoder's output is routed through the *same*
declared-name check and dtype coercion as native frames — *"no special dispensation for a foreign
source"* — and any exception it raises is caught, counted malformed and returns `[]`, because *"the
decoder is a researcher-editable versioned lib and WILL raise eventually"* (`:264-275`).

Egress is a FIFO, bounded, single-thread worker whose documented policy deserves quoting in a methods
paper (`external_hardware_runtime.py:15-24`): **no retry, ever — "a retried marker lands at the WRONG
timestamp, corrupting co-registration"** — and overflow drops the **newest** item and records the
loss, because *"the oldest items are nearest delivery and evicting them tears a hole mid-sequence."*
Liveness has exactly one writer (`recompute_alive`, `external_hardware_binding.py:131-140`), and a
`role:"none"` device is **structurally** kept in the readiness gate rather than special-cased
(`bind_steps`, `runtime:231-239`).

**Rig checkpoint (2026-08-09):** pilot 1, session 115, task_def 434, toolkit 100. Runs 552 ✅
(20 transitions), 553 ❌ (stale driver identity rejected by the ROUTER identity check), 554 ✅,
555 ❌, 556 ✅ (**587 ES documents, 32 transitions**, lib v2). The two failures were root-caused to
fixture misconfiguration — an egress probe pointed at a port with no listener — and proven *not* to
be a code defect by flipping `demo.alive` false and back live, without a restart.

**Why it matters scientifically.** Closed-loop behavioural experiments increasingly depend on
software the rig framework does not own — pose estimation, spike sorting, stimulus generators.
Requiring each of them to be ported into the framework is what keeps closed loops rare. Making the
adapter a versioned per-toolkit artifact means a foreign publisher needs **no MICS code at all**, only
a decoder that lives beside the toolkit that uses it.

**What Autopilot does instead — and this is the fairness clause that most protects the manuscript.**
Autopilot shipped a **networked closed loop in 2022**: `tasks/children.py:179` plus nine to ten
`transform/` modules — camera → transform pipeline → `TRIGGER` back to the requesting node, or a
continuous stream — *and* in-process on-Pi computation. It is unused in MICS (`utils/registry.py:42`
is the only reference; `LINEAGE="PARENT"` with no children). **Do not imply that external computation
influencing task flow over a network is new.** MICS-Link is more *general* — a foreign publisher needs
no MICS code, only a decoder — but strictly more expensive: MICS's answer to "process a video frame"
is another computer, which adds a hop and a clock domain. **Claim generality, not novelty.**

**Honest bound.**
- ⚠️ **`sub_connect` (EXTLINK-14) is UNPROVEN on hardware** — a deliberate single-library scope
  reduction; no `sub_connect` fixture remains, and the mechanism is agent-unit-tested only.
  **`sub_connect` is exactly the transport an Open Ephys integration needs, so the foreign-publisher
  path must not be claimed as demonstrated.** `role:"none"` (EXTLINK-18) is likewise unproven on
  hardware; browser-picker authoring (EXTLINK-19) and the ~60 Hz soak (EXTLINK-20) are unproven — the
  two transitions on task definition 434 were authored **through the API by the coordinator, not the
  FDA editor**.
- ⚠️ **Arithmetic discrepancy to resolve before citing:** every internal document says "six runs" and
  lists **five** run IDs (552–556), with "no run 551 in scope". Fix or drop the count.
- **Standing operational dependency:** the demo fixture was deliberately left on pilot 1, so every
  subsequent real session on that rig either preflight-fails or waits out the full 30 s timeout, and a
  TCP echo listener must keep running on `132.77.73.125:5597` or liveness flips false.
- Two save-gate holes let an unknown external key save clean and never fire (`view` operands are not
  validated; the runtime shape is `condition_tree` with a bare literal, not `condition` with
  `{"const": …}`). Both are recorded as **not fixed**.

**Status:** shipped-but-narrower (2026-08-09).

---

## B12 — Coordination state is durable rows, and the UI is off the data path

**What it is.** What a running experiment is doing, and where each animal is in its training, live in
the database; the browser only looks at them. Closing the window cannot affect a run or its record.

**Mechanism.** Ingestion is wholly inside the headless orchestrator
(`orchestrator_station.py:245-249`, `:554` → Elasticsearch); `web_ui/app.py:42,67` is read-only.
Progression is durable rows — `run_progress.current_step_idx`, `session_runs.status` — with live rig
state in Redis (`orchestrator_station.py:187-235`).

**Why it matters scientifically.** This is the one genuinely load-bearing architectural inversion.
In the inherited design the Qt window object **holds the open HDF5 handles** (`terminal.py:595`),
which makes the GUI a single point of failure for the data, ties data integrity to a desktop session,
and makes remote operation impossible without remote-desktop software. The lab's own response to that
design's `time.sleep(5)` FIXME was to raise it to `time.sleep(10)` (`terminal.py:629`, FIXME text
unchanged) — **the most persuasive single line available for why coordination moved out of the GUI,
and it is the lab's own.**

**What Autopilot does instead.** `pilot_db.json` (pilot → subject/IP) is its entire persistent
coordination state; progression lives in a Qt object's memory, and the Terminal is on the data path.
State it as a **choice**, not an invention — the framing MICS argues against needs to be a design
decision someone made, and Autopilot's own source states its assumptions plainly.

**Honest bound.** Do not let this slide into "it's a web app now", which buys remote access and
concurrent *viewing* and buys no scientific claim (Part C). And **concurrent viewing is not
concurrent operation** — see Part C on multi-user.

**Status:** shipped.

---

# Part C — Deliberately excluded

The boundary was drawn on two tests: **(i)** starting from a blank file with Python, ZMQ and pigpio,
would a competent implementation have arrived somewhere materially different? **(ii)** does every
comparable framework (Bpod, pyControl, BControl, Bonsai, IntelliCage, any SCADA stack) already have
an equivalent? Where the answer is *no* and *yes*, nobody owns it — and crediting Autopilot for it
**weakens** the credit MICS genuinely owes, because it makes the whole ledger look uncalibrated.

The load-bearing external fact: **Autopilot's own published claim (`CITATION.cff` at `30c8d3c`) is
about flexible hardware composition, timing performance and cost on a swarm of cheap Pis.** The
Terminal appears in its README only as a row in a module table. The coordination topology is not
Autopilot's thesis.

### C1 — Generic application foundation (claimed by nobody)

| Excluded | Why |
|---|---|
| 111 REST routes, FastAPI, JWT, React SPA (84 modules / 13,055 lines / 18 routes), WebSocket, Docker | Scope and a technology choice. Buys remote access and concurrent viewing; buys no claim. **Say so first — a reviewer will otherwise say it for you.** |
| Central coordinator ↔ N distributed executors | The oldest pattern in networked control. Every web app, CI runner pool and print spooler has it. |
| `{key: handler}` message dispatch; `l_start`/`l_stop` RPC; the daemon shell (parse prefs, init logging, init pigpio, spawn a network thread, run the task in a thread) | The default shape of every message-driven daemon. |
| A JSON envelope with `{to, sender, key, value, id}` plus an ACK, **as an idea** | `Message.serialize()` is `json.dumps(self.__dict__)`. (The *literal class* running on both ends is a real code debt — C2.) |
| `init_hardware()`; the `Hardware` / `HARDWARE`-dict / prefs abstraction; BCM↔board pin translation | A double `for` loop over two nested dicts calling a constructor. Bpod `PortArray`, pyControl board definitions, BControl `@hardware` and `#define VALVE1 35` all land here. |
| Per-subject HDF5 as the unit of persistence; a per-subject session counter; a weights table | The standard lab convention of 2015–2022. |
| The `Accuracy` graduation *criterion* itself | 50 lines of `deque` + `np.mean` (`graduation.py:40-93`). |
| The Qt Terminal **as a program** | A desktop GUI holding a device list is not a scientific contribution. Its *placement on the data path* is the consequential decision — and that is B12. |
| `OrchestratorState`; the backend queues; pigpio as the GPIO layer | Competent, unremarkable engineering; ours, and not a contribution. |

### C2 — Genuine Autopilot debts (credit these, do not claim them)

Only five things are genuinely Autopilot's *and* genuinely load-bearing:

1. **The forked pigpio timebase** — µs-precise, wall-clock-aligned GPIO timestamps
   (`requirements_pilot.txt:18`; `README.md:130`; `gpio.py:7,790`). Not replaceable without real
   work. See A11.
2. **`gpio.py`'s pigpio stored-script waveform layer** (`gpio.py:519-793`) — pulse trains compiled
   into the pigpio daemon, off the Python GIL. Every MICS valve pulse rides on it unmodified
   (`Solenoid.open` `:1632`, `Pulse20Hz` `:1691-1706`). **MICS added ~0 lines and would have to
   reinvent it.** Name *this*, rather than ceding "hardware abstraction" wholesale.
3. **1,438 lines of working, tested pigpio drivers**, ~94 % of original lines retained; every MICS
   effector is a `Digital_Out` subclass.
4. **Local executor autonomy** — the Pilot owns its task for the duration and keeps running if the
   coordinator dies. A design commitment, not a topology; MICS inherits `core/pilot.py` essentially
   intact and gets it free.
5. **The MPL-2.0 file-level obligation** on ten upstream files MICS modified in place. A legal fact,
   visible at code release regardless of what the manuscript says.

Also credited, not claimed: **transparent ndarray compression** (`message.py:75-78,157-184` — the
genuinely non-obvious idea in `Message`; MICS never sends an ndarray); the **`flags` protocol**
(`NOREPEAT`/`NOLOG`/`MINPRINT`, `message.py:35-40`, and MICS depends on both today); **`Net_Node` and
`Message` byte-identical on both ends** of the wire; the **plugin registry**, still on the live task
resolution path (`pilot.py:526,593`); **`TrialData` / `History_Table` / `past_protocols`** — a genuine
design→execution→data thread, and **MICS has no equivalent of `past_protocols`** (`protocol_templates`
rows are mutated in place), which is worth volunteering because it makes the rest credible; and
**live per-trial plotting** (`plots.py`), which MICS lost outright — see Part D.

Disclose the dependency **in the Table 1 caption**. Comparing a system to its own foundation without
saying so is the highest-risk item in the manuscript. And **strengthen Autopilot's row**: it has a
plugin registry, on-Pi real-time transforms and networked closed-loop children. Understating your own
dependency reads worse than understating a competitor.

### C3 — Unexecuted roadmap work (do not write in the present tense)

Phase 19 (3 plans, planned 2026-08-05, unexecuted); Phase 26 (13 plans, unexecuted, no longer blocked
now that 18 is done); Phases 27 and 28 (0 plans); Phase 30 (exists, not yet planned). The
`ROADMAP.md` summary table is column-shifted for several rows — **read `STATE.md`, not the ROADMAP
table.** Anything described as "the device-health badge (Phase 19)" reports planned work as existing
and must be deleted.

### C4 — Claims the audit found unsupportable

| Dropped claim | Why it fails |
|---|---|
| **"Periodic synchronization with a global reference … a unified experimental timeline"** across stations | Events from different rigs do **not** share a timeline. NTP is commented out **in the commit that introduced it** (`a008046`; sites `pilot.py:1138,1148`); each Pi's `synchronize()` anchors to its *own* wall clock; each host stamps its own local zone (`common.py:332`) while the backend re-stamps everything into one zone (`ElasticSearchDateHandler.py:48-51`), *hiding* per-rig offsets; and the repo says so itself (`ROADMAP.md:496`: *"those machines are not NTP-synced to each other"*). **Replacement wording:** *"All events from a rig are stamped from a single, GPIO-derived clock, giving microsecond-resolution ordering within a rig; alignment across rigs or to external acquisition systems is achieved by a shared TTL pulse, not by network time synchronisation."* — and that pulse is currently switched off (**F5**). |
| **Performance-based / adaptive progression; trajectories that branch on performance** | MICS evaluates only `NTrials` (`api/main.py:1750`). **Autopilot has `NTrials` *and* `Accuracy`.** Table 1 currently reverses the truth on this axis. **Claimable instead:** progression is evaluated and stored **per subject** in a queryable relational model with explicit run modes; and MICS is strongly adaptive **within** a session (compute ops, variables, nested conditions) where Autopilot's adaptivity is across sessions. |
| **"Multiple users can operate the facility concurrently"; per-user identity** | One shared service JWT with the payload discarded (`api/auth.py:20`); no busy-check on `POST /session-runs` so two users can start two runs on one rig (`main.py:1236-1345`); unauthenticated WebSocket (`web_ui/app.py:51`); zero planning-doc hits for `multi-user|RBAC|per-user`. **Claimable:** concurrent *viewing* and remote access. |
| **Sample-accurate / low-latency audio** | MICS swapped jack/pyo (`FS=192000`, `-p16`, RT priority 75) for pygame `mixer.init(buffer=1024)` (`mixer.py:19`), and **loads and decodes the WAV from the SD card inside the cue call** (`:25-27`); audio-off is a `threading.Timer` (`:33-34`), not the sample end. ~23–46 ms vs ~0.083 ms/period nominal. For a 150 ms tone this is fine — but quote a **measured** number, never a derived one. |
| **"The same Blueprint used in live experiments executes in the virtual environment"** (digital twin) | `unreal.py`'s only consumer is the legacy `mics_cage_task.py`; backend-authored toolkits have no UNREAL group, no phase reconnects them, and no mock-event-stream generator was found — the distance grows with every landed phase. **Decide, don't reword:** demote to a supplementary figure describing a hardware-simulation harness for the legacy path, do the work, or cut. |
| **"Preflight hard-blocks"** | False as coded — **F1**. Reworded and retained as B6. |
| **"Driver code … recorded against the run"** | False as coded — **F2**. Reworded and retained as B5. |
| **"All hardware events are logged automatically"** | One decorator repo-wide — reworded and retained as A6. |
| **"The Portal verifies compatibility with the assigned system *and subjects* (implant type, genetic indicators)"** | No subject-attribute check exists in any of the 11 preflight kinds; `implant` returns **zero** hits across `api/`, the React source and the planning docs; `Subject` has no implant field. Say attributes are *recorded*; describe the check as over hardware, task references, view keys, variables, library versions and device availability. |
| **"Each event is indexed with … experiment name"** | Not a mapped field (B2). `run_id` *is*. |
| **"A simple query finds all experiments for a given subject"** | No such table, join or endpoint (B9). Replace the illustration; the axis still wins. |
| **"Autopilot has no clock synchronisation"** | False, and false in the direction that flatters us (A11, C2). Strike it. |

---

# Part D — The trade-offs to own in the Discussion

Volunteering these is what makes Part A and Part B credible. Each is a real cost of a real decision.

**1. There is no trial table and no trial record.** Twenty-eight tables, none named `trials`;
Elasticsearch holds one document per *event*. Trial *boundaries* are recoverable
(`Trial_Tracker.increment` emits a document keyed `INC_TRIAL_COUNTER`, `Tracker.py:81-92`), but the
trial as a record with outcome columns — correct/incorrect, choice, reaction time, stimulus identity
— is recorded nowhere. **Every analysis begins by reconstructing trials under a definition that lives
in analysis code rather than in the data.** Concede this *first*, then make the completeness case:
Autopilot's `TrialData` produced the analysis artefact as a side effect of declaring the task, and
that is a genuine thing MICS gave up.

**2. Expressiveness is bounded by the vocabulary.** Arbitrary Python inside a state is gone: actions
are a closed 8-branch table, methods must be whitelisted in `CALLABLE_METHODS`
(`mics_task.py:914-919`), operators are six. A novel computation now needs a versioned compute
library, not a line of Python. That is the price of validatability and it should be stated as a
price.

**3. Deployment cost.** Seven containers with **zero resource limits declared**, plus external
Elasticsearch, Postgres and Redis. **Autopilot needs a Pi and a laptop.** For a lab that wants one
rig on a bench, MICS is the wrong tool, and saying so is more persuasive than not.

**4. Live per-trial plotting is gone.** Autopilot's `Plot` (`plots.py:129`) opens **its own network
node** (`:231`) and receives `START`/`DATA`/`STOP` **directly from the Pi** — it is a peer on the
network, not a view over the coordinator's memory — reads the task's own `PLOT` declaration and
instantiates the declared primitives (`Point`, `Line`, `Segment`, `Roll_Mean`, `Shaded`) plus a
chance line and optional video. **The task declares how it should be visualised and a live per-trial
plot appears with zero configuration.** Nothing comparable exists in 84 TS/TSX modules. Lost with it:
water-port calibration with results shipped back to the Pi, the bandwidth test, batch protocol
reassignment, the video stream. **Concede this in the same paragraph that claims a monitoring
improvement** — the concession is what makes the claim credible.

**5. Local durability on the rig is gone, so a mid-run network partition loses data.** Autopilot wrote
trials to HDF5 *before* sending anything. MICS disabled the Pi's local write (`490121e`, 2024-12-31)
and later the `DATA` send itself (`53f86ab`, 2026-04-29). Two consequences: the Pi's sole egress is
now the network, and there is no local mirror to reconcile against. **Date this carefully** —
*"replaced"* is right, *"removed"* is not: `subject.py`'s writer is still live code reachable from
the (dead) Terminal, `import tables` remains a hard startup dependency of a file that writes no HDF5,
and the lab was still *maintaining* the HDF5 writer as late as 2025-09 (`cca9c4f`). Relatedly:
Autopilot's rotating debug log was **traded away, not merely supplemented** — Pi log files are
0 bytes by design (`core/loggers.py` `mode='w'` ×2 plus `doRollover()`; `LOGLEVEL=ERROR`), so a
reviewer looking for a rig-side audit trail will find nothing.

**6. The audio path is a regression.** See C4. Do not imply low latency; if audio timing matters to a
result, measure it.

**7. Two event vocabularies in one index, and a double-emit.** One valve produces documents typed
`gpio.Solenoid_mics` (from the decorator path, `logging_utils.py:91`) **and** `VALVE` (from the
explicit path, `mics_task.py:385`), with trackers typed by class name, the FDA typing
`state_transition`, and ad-hoc types besides — **nothing unifies them but `event_data.id`.** That is
the mechanism behind "two event vocabularies in one index"; it is a code-level fact, not historical
schema drift. And **all eight `*_and_notify` helpers emit the same physical action twice**
(`mics_task.py:396-403, 405-409, 419-433, 444-451, 453-456, 459-463, 465-473`), so **any naive count
of reward deliveries or LED onsets over the event index is 2×.** Publish the de-duplication rule with
the corpus.

**Also worth conceding in one sentence each, if space allows:** the FDA's state-advance latency floor
is a 500 µs busy-poll, not an event wait (A5); both the trigger queue and the event send queue are
unbounded and their drop counters are in-process only (A4, A6); database-sourced Python is `exec`'d
on the rig with no sandbox (A10); Elasticsearch ingestion has no bulk, retry or dead-letter path
(B2); and three secrets are committed in plaintext in `docker-compose.yml`, which must be fixed
before anyone else deploys this.

---

## Appendix — citation hygiene

Every `file:line` above is taken from `.planning/16_FORK_HONEST_COMPARISON.md` or from the six
per-domain audits it synthesises; where this document adds a citation doc 16 does not carry, that
citation was re-verified against live source during preparation. **Nothing here is invented.** Three
items are flagged as needing work before publication and are marked in place:

1. 🔶 **The forked pigpio has no in-repo provenance.** `synchronize()` and `ticks_to_timestamp()` are
   called and nowhere defined; pigpio is not vendored. A11's credit clause needs an external citation
   (fork URL + commit) that does not currently exist in the repository.
2. ⚠️ **The 27/157 FDA-adoption figure has no recorded query.** Re-derive and date it.
3. ⚠️ **The MICS-Link checkpoint says "six runs" and lists five IDs.** Resolve or drop the count.

Two tooling hazards that nearly produced false findings during the audit, recorded so they are not
repeated: `rg` is not installed on this host and bare `grep` is hook-rewritten to a token-compressing
proxy that reports a missing binary as `0 matches` and can render a real matching line **blank** —
**never assert a symbol is unused from a filtered grep.** And for provenance work, `git log -S… --all`
and `git blame` on HEAD are both **wrong** in the Pi repository, which contains three disjoint root
commits; the checked-out branch shares no ancestry with the lab history. Determine every provenance
claim against an explicit ref-set.
