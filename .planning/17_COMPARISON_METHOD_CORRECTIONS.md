# 17 — Comparing MICS with Autopilot: a method correction and a corrected ledger

**Written 2026-08-10.** For the agent maintaining `12_PAPER_VS_IMPLEMENTATION.md`,
`13_MANUSCRIPT_CLAIMS_AUDIT.md`, `14_AUTOPILOT_VS_MICS.md` and `15_CLAIMS_VS_AUTOPILOT.md`.

**What this is.** `16_FORK_HONEST_COMPARISON.md` is the synthesis of six independent read-only
audits (runtime · transport & timing · hardware & logging · data model · coordination & authoring ·
provenance). Working through it, one pattern accounts for most of the places where doc 16 and docs
12–15 disagree — and it is a single, structural inference, not a set of unrelated slips. This
document names that inference, shows both directions in which it misfires, and then supplies the
corrected state of the system as a lookup table.

**What this is not.** Docs 12–15 are, on the whole, better evidence work than the comparison
sections of most methods papers ever receive. Doc 14 §1c is byte-verified on both ends of the wire
and is the single best-evidenced passage in the set. Doc 15 C8's `Transformer` warning is, in doc
16's assessment, the finding most likely to save the manuscript. Doc 12 §2.4 / doc 13 §4.7 contain a
self-correction on `run_id` that the audits singled out as exemplary — a document that publishes its
own reversal is doing the job properly. Part 2 below lists, specifically, what should survive
verbatim. Where this document corrects, it corrects a *method*; the evidence discipline underneath
it is the reason the corrections are even legible.

**Rule inherited from doc 16, and it governs everything here:** the only boundary the manuscript
defends is Autopilot vs MICS. Every citation below is `file:line` or a commit hash carried over from
doc 16 or its source audits.

---

## Part 1 — The methodological error, named

### 1.1 The inference

> **From "these bytes are unchanged from Autopilot" it does not follow that "this idea is
> Autopilot's."**

Docs 12–15 are built on a static three-way diff (upstream 0.4.4 → vendored-at-`30c8d3c` → today).
That is the right instrument for the question *what code did MICS write?* It is the wrong instrument
for the question *what did MICS invent?*, and the two questions look identical when the artifact in
front of you is a diff. The diff answers the first and is silently substituted for the second.

The substitution fails in both directions at once:

- **Forward:** a file that did not change gets credited to Autopilot *as a design contribution*,
  including code that any competent implementation of the same problem would have produced. The
  diff cannot distinguish "Autopilot thought of this" from "Autopilot, like everyone else, had to
  have one of these."
- **Backward:** a change that moves few lines but inverts the runtime contract registers as noise.
  The diff cannot distinguish "one line changed" from "the concurrency model changed."

Both halves push in the same direction — they inflate Autopilot's share and deflate MICS's — which
is why the resulting ledger reads as scrupulous rather than as skewed. That is exactly what makes
the failure mode hard to catch from inside.

### 1.2 Half one — over-crediting generic scaffolding

The clearest instances, each conceded to Autopilot somewhere in docs 14–15 and each belonging to
nobody (doc 16 §5):

| Conceded item | Why it is generic |
|---|---|
| `init_hardware()` — build devices from `HARDWARE` × `prefs['HARDWARE']` | A double `for` loop over two nested dicts calling a constructor and registering a callback (B1 `task.py:105-160`; today `task.py:150-215`). Bpod's `BpodObject` builds its module list from a config; pyControl instantiates from a board-definition file identically. |
| ROUTER/DEALER + a `{key: handler}` dispatch dict | ROUTER/DEALER with identity frames is literally the ZMQ guide's async client/server pattern, and a string→handler dict is the default shape of every message-driven daemon. B1 `pilot.py:185-193` has **7** such keys; MICS's own orchestrator-side table (`orchestrator/main.py:71-81`) was written fresh and merely names the same keys. |
| The `{id,to,sender,key,value,flags,ttl}` envelope **as an idea** | `Message.serialize()` is `json.dumps(self.__dict__)`. And `to`/`sender` are not even trustworthy routing: ZMQ's identity frame does the routing, and `RouterGateway._on_recv` overwrites `msg.sender` from frame 0 (`:177-178`). |
| `while True: next(self.task.stages)()` | The *contract* (an iterator of zero-arg callables) is a real if thin design choice — see §2.2. The loop around it is a loop. |
| A central coordinator talking to N executor nodes | "Autonomous nodes + a coordinator" is the oldest pattern in networked control: Med-PC, Bpod, IntelliCage and every SCADA stack have it (B1 `terminal.py:72,182,186`). |
| `class Hardware` with `name`/`group`, a `HARDWARE` dict keyed group→id, pins in a prefs file | You need a per-device object, a stable logical name so task code does not hardcode pin 35, and a per-rig file mapping name→pin. Forced by the problem. Bpod `PortArray`, pyControl board definitions, BControl `@hardware`, and `#define VALVE1 35` all land here (B1 `hardware/__init__.py:78-120`). |

**The test that separates generic from distinctive** (doc 16 §5) — two questions, and an item is
generic when the answers are *no* and *yes*:

1. Starting from a blank file with Python, ZMQ and pigpio, would a competent implementation have
   arrived somewhere **materially different**?
2. Does **every** comparable framework already have an equivalent (Bpod, pyControl, BControl,
   Bonsai, IntelliCage, any SCADA stack)?

**The external check, and it is the one most worth adopting as habit.** Before conceding an idea to
an upstream project, read what that project claims for itself. Autopilot's `CITATION.cff` at
`30c8d3c` claims **flexible hardware composition, timing performance, and cost on a swarm of cheap
Pis** — *"an order-of-magnitude performance improvement … while also being an order of magnitude
less costly to implement."* The Terminal appears in its README only as a row in a module table.
Autopilot does not claim a coordination topology, and it does not claim versatility as a
contribution. So:

- Doc 15 **C1** — *"separation of local execution from central coordination … this **is**
  Autopilot"* — concedes something Autopilot never claimed. The genuinely Autopilot part is
  narrower and should replace it: **local executor autonomy**, the commitment that the Pilot owns
  its task for the duration and keeps running if the coordinator dies (§2.2 below).
- Doc 15 **C12** — *"one architecture across paradigms … Autopilot designed and published for
  exactly this"*, marked ⊘ inherited — is a category error. **You cannot inherit versatility.**
  MICS's paradigm-independence comes from the FDA/toolkit model, which is MICS's own. That Autopilot
  is *also* general-purpose is a fact about a comparator, not a debt.
- Doc 15 **C11** — "scaling: parallel stations" — should be split: inherited *code* (MICS never had
  to write the client), not an inherited *idea*. Doc 14 §5.7 already gets this right and should be
  made load-bearing.

Note also that doc 14 §5 and doc 15 C1 contradict each other on the coordination question; doc 16
§5 is the adjudication.

**Why over-crediting is not the safe error.** It reads as generosity, but it decalibrates the whole
ledger: a reviewer who sees `init_hardware()` conceded as an Autopilot contribution has no way to
tell that the pigpio stored-script waveform layer two paragraphs later is a *real* one. Conceding
everything makes the genuine concessions worthless as evidence of good faith.

### 1.3 Half two — blindness to small-diff / large-consequence change

**The trigger queue is the sharpest case, and it is absent from all four documents.** It is
plausibly the largest single change to runtime behaviour in the entire fork, and it barely moves a
line count.

Autopilot's B1 `task.py:279-306`:

```python
unlocked = self.trigger_lock.acquire(blocking=False)
if not unlocked:
    self.logger.debug('Trigger called, but trigger lock has not been released …')
    return                      # ← the trigger is DISCARDED
...
self.triggers[pin]()            # fire
self.triggers = {}              # ← every other armed trigger is ALSO discarded
```

Two independent data losses: triggers arriving under lock contention are dropped, and after one
fires the entire trigger table is wiped. For a home-cage rig where a mouse can lick, break an IR
beam and trip a touch sensor within milliseconds, both are lost behavioural events. `c632674`
(Lior Segev, 2025-02-02) replaced this with `self.event_queue = queue.Queue()` plus a daemon
`process_queue` worker (`task.py:129-133,254-266`), reducing `handle_trigger` to one line:
`self.event_queue.put((pin, level, tick, hardware))` (`:373`). Nothing is dropped; everything is
serialised in arrival order. `event_queue` occurs **0 times** in 0.4.4.

This is both a correctness fix to inherited Autopilot code *and* the most concrete engineering claim
available in the runtime section — and a line-diff renders it as a modest edit to one file, which is
why it did not surface. (Its honest bounds, which should travel with any claim: `process_queue` has
no exception boundary, so anything escaping `execute_trigger` kills trigger processing for the rest
of the run; the queue is unbounded and the FDA only *prints* on backlog,
`FiniteDeterministicAutomaton.py:84-86`.)

**Two more instances of the same shape:**

- **`self.stages`: `itertools.cycle` → FDA.** Autopilot's `self.stages` is a fixed ring with no
  names, no conditions and no branching; a trial is exactly one lap, and branching lives in Python
  inside a stage method. MICS's is a `FiniteDeterministicAutomaton` (`FiniteDeterministicAutomaton.py:5-96`)
  walking a transition table `{method: [(next_method, [predicates], description)]}`. A different
  computational object — but because the FDA implements `__iter__`/`__next__` purely so that
  Autopilot's `next(self.task.stages)()` keeps working, the *diff at the call site is zero*. Doc 14
  §1b's *"the process model … is untouched"* is true of the silhouette and false of the body:
  `23e6bf7` (2025-03-18) rewrote the loop to detect `types.GeneratorType` and abort a state
  mid-execution on `self.running` (`pilot.py:1188-1197`); `import types` was added by that very
  commit. Correct phrasing: **"structurally preserved, semantically re-based."**
- **`stage_block` is dead, not kept.** Doc 14 §2.2's *"MICS keeps the contract (`self.stages` yields
  callables; `stage_block`)"* is right on the first half and wrong on the second: `task.py:119` is
  `self.stage_block = None`, `mics_task.py:104` swallows the kwarg, and `pilot.py:1227`,
  `task.py:307,402` are all commented out. Autopilot's actual concurrency contract — zero-cost
  blocking on a `threading.Event` — was replaced by a 500 µs busy-poll (`wait_for_condition`,
  `mics_task.py:482-495`). `mics_task.py:1553`'s docstring still claims otherwise and probably
  seeded the error; the comment is worth fixing too. The surviving contract is exactly *"`self.stages`
  is an iterator of zero-argument callables"* — one line, and worth saying it is one line.

### 1.4 A small static diff can sit under a complete architectural inversion

The general form, with the concrete instances:

- **`core/pilot.py` retains 95.0 % of its original lines** (823 → 1,283; +501/−41), which reads as
  "still Autopilot's process." Inside those 41 removed and a handful of commented lines are: the
  `DATA` send to the Terminal (`pilot.py:1210`, commented at `53f86ab`), the `TrialData` row-fill
  and `table.flush()`, the local HDF5 write (`pilot.py:999-1054`, orphaned at `490121e`), and
  `stage_block.wait()` (`pilot.py:1227`). The scientific data path and the stage-advance concurrency
  primitive both live in that 5 %. Doc 14's gloss *"the 29 removed lines are exactly the data path"*
  is close, but one of them is `stage_block.wait()`, which is not the data path at all and should be
  listed separately.
- **The UI's removal from the data path produces no diff in any Autopilot file at all.** In B1,
  `terminal.py:595` — the Qt window object — holds the open HDF5 handles. In MICS, ingestion is
  wholly inside the orchestrator (`orchestrator_station.py:245-249,554` → ES) and `web_ui/app.py:42,67`
  is read-only. This is the one genuinely load-bearing architectural inversion in the system (doc 14
  §5.2 identifies it correctly), and it is invisible to a line-diff because it consists of code
  *not* being where it used to be.
- **Progression state moved from a Qt object's memory to durable rows** — `run_progress.current_step_idx`,
  `session_runs.status`, Redis `pilot:<key>` (`orchestrator_station.py:187-235`) — against
  Autopilot, whose entire persistent coordination state is `pilot_db.json` (pilot→subject/IP only).
  Again: no upstream file changed.
- **The inverse trap: "inherited" can mean "shipped and never executed."** 35 vendored upstream
  modules totalling **≈11,900 lines** ship in the release and are run by nothing — the entire
  Terminal, GUI, plotting and subject-file stack. A diff files these under "inherited, unchanged";
  an import-closure or call-graph analysis files them under "dead weight." The two readings support
  opposite sentences in a manuscript.

**Practical consequence:** a diff is a starting point, never a verdict. Every "inherited" row needs a
second question — *is it executed?* — and every "unchanged" row needs a third — *did its meaning
change around it?*

---

## Part 2 — Where the original documents were right

### 2.1 Passages that should survive verbatim

These were re-verified during the audit and should be carried into any successor document unchanged
except where noted:

1. **Doc 14 §1c, in full.** Byte-verified on both ends of the wire: `networking/node.py` and
   `networking/message.py` are byte-identical to upstream 0.4.4 on the Pi, and `message.py` is
   byte-identical *again* in `mics-backend/orchestrator/orchestrator/networking/`. Its conclusion —
   ***"MICS replaced Autopilot's server, not Autopilot's protocol"*** — is exactly right, and
   `RouterGateway.py:16`'s self-description (*"speaks legacy Pilot_Station format"*) is an accurate
   statement of a live dependency rather than a stale comment. **Add one qualification (doc 16 §4.4):
   the dependency is shallow.** MICS uses only `key`, `value` and two flags — no ndarrays, no
   multi-hop `routes`, no `expand_arrays`. Replacing the envelope would touch three Pi files the lab
   has already shown it will patch plus two methods in `RouterGateway`, roughly a day. Convenience,
   not lock-in. Say *"we run Autopilot's networking layer unchanged"*, not *"we build on Autopilot's
   messaging architecture."*
2. **Doc 14 §4's four reasons to disclose the dependency** — especially #1 (checkable in thirty
   seconds: the release ships `LICENSE`, `CITATION.cff`, `setup.py`) and #2 (MPL-2.0 file-level
   copyleft). Extend #2's file list per §3.1 below, and replace the word *"fork"* with *"vendored
   dependency"* throughout — the MICS repository predates the Autopilot import by nine months
   (`f49dfe7`, 2021-07-21 vs `4b28bd7`→`30c8d3c`, 2022-04-05), so Autopilot was vendored **into** an
   existing repo, not forked from. Doc 14 §4's own conclusion (*"Not a fork of Autopilot"*) is
   correct while its repeated vocabulary invites the genealogy its own history contradicts.
3. **Doc 14 §5.8's tone warning and its model paragraph.** Write the architecture, never a
   reliability claim about someone else's software. The Terminal's design assumption is stated in its
   own source (`l_ping` docstring, `terminal.py:605`), which makes the non-adversarial framing both
   truthful and generous. The model paragraph — *"the interface can therefore be closed, restarted or
   replaced without affecting either data capture or experimental progression"* — is defensible,
   checkable and says everything the lab's experience taught. Keep it.
4. **Doc 15 C8's `Transformer` warning** — *do not imply that external computation influencing task
   flow over a network is new.* Doc 16 calls this the single most useful sentence in the four
   documents. Autopilot shipped a networked closed loop (`tasks/children.py:179`) **and** in-process
   on-Pi computation (`transform/`) in 2022. MICS-Link is more *general* (a foreign publisher needs
   no MICS code, only a `@decoder`) but strictly more expensive. **Claim generality, not novelty.**
5. **Doc 14 §2.6 / doc 15 C5 on `Accuracy`** — verified line for line. Strengthen with two further
   defects (§3.4 below): the silent no-op on a non-`NTrials` graduation type, and the inverted
   `current_trial` semantics.
6. **Doc 14 §7.1–§7.5.** The **template vs contract** framing, the concession that
   `PARAMS`/`TrialData`/`History_Table` is a genuine design→execution→data thread, and the
   **scope / enforcement** reframing (*"do not argue this as 'we have a unified representation and
   others don't'"*) — doc 16 calls this the most intellectually honest passage in the set. One
   correction inside it: §7.2's fifth bullet, and §7.3's third table row (*"Which driver code was on
   the rig that night?" → "✓ pinned version, recorded against the run"*) must be softened — the
   version is recorded against the **specification**, not the run. See §3.4/F2.
7. **Doc 14 §6** (hardware-abstraction rewrite instructions), including *"Never imply Autopilot lacks
   abstraction."* The diagnosis is correct and is the key to the whole hardware section: **abstraction
   is not the novelty; management of the abstraction is.** Trim §6.3 item 1's implicit run-binding
   claim.
8. **Doc 14 §5.2 and §5.7.** §5.2 identifies the one genuinely load-bearing architectural inversion
   (the UI's position relative to the data path). §5.7 correctly refuses to claim station-scaling as
   MICS's.
9. **Doc 13 §3.1's positive fix** — do not weaken the global-clock claim, replace it with the two
   mechanisms that actually exist.
10. **Doc 12 §2.4 / doc 13 §4.7's self-correction on `run_id`**, including the Methods caveat that
    the analysed corpus lacks the field the Methods will describe. Both the correction and the
    willingness to publish it are exemplary.
11. **One verified detail worth reusing:** the lab's own response to the Terminal's `time.sleep(5)`
    FIXME was to raise it to `time.sleep(10)` (`terminal.py:629`, FIXME text unchanged). It is the
    most persuasive single line available for why coordination moved out of the GUI — and it is the
    lab's own, which is what makes it usable without criticising anyone's software.

### 2.2 Genuine Autopilot debts the originals identified correctly

- **The vendored package is a hard code dependency.** Delete `autopilot/` and nothing starts.
  `pilot.py` is Autopilot's file; `networking/node.py` and `networking/message.py` are byte-identical
  to 0.4.4 on **both** ends of the wire.
- **1,438 lines of working, tested pigpio drivers** (`gpio.py`), ~94 % of original lines retained;
  every MICS effector is a `Digital_Out` subclass.
- **`TrialData` as schema authority** (`task.py:103-105`; `subject.py:496-536`) — the analysis
  artefact produced as a side effect of declaring the task. MICS's `task_definitions.params` is its
  lineal descendant.
- **`History_Table`** (`subject.py:325-392,1312-1326`) — an append-only in-band change log of every
  protocol/param/step change, distinctive for its era and the honest ancestor of MICS's provenance
  argument.
- **Live per-trial plotting** (`core/plots.py`) — `Plot` (`:129`) opens **its own `Net_Node` with
  identity `P_{pilot}`** (`:231`) and receives `START`/`DATA`/`STOP` directly from the Pi. The task
  declares how it should be visualised (`PLOT`) and a live plot appears with zero configuration.
  **MICS lost this**, and has nothing comparable in 84 TS/TSX modules.
- **`Accuracy` graduation** (`graduation.py:40-95`) — MICS evaluates only `NTrials`
  (`api/main.py:1750`). This is the one axis where MICS is behind its own foundation, and Table 1
  currently reverses the truth on it.
- **The absence of pre-run validation in Autopilot**, verified twice: `terminal.py:516-573` read in
  full, and `git show 30c8d3c:…/terminal.py | grep -niE "valid|verif|preflight"` → **exit 1**. One
  refinement: doc 15 C7 cites `terminal.py:565`'s "coherence checking ritual" TODO as evidence of
  intent to validate; that TODO sits in the *stopping* branch and concerns post-hoc data
  reconciliation. The cleaner and stronger statement is that Autopilot has no pre-run validation
  **and expresses no intent to add one.**

### 2.3 Genuine Autopilot debts the originals missed

Six, and each is missed for the same structural reason — none of them is visible as a *change*:

1. **The forked pigpio timebase.** See §2.4; it is the most consequential of the six.
2. **`gpio.py`'s pigpio stored-script waveform layer** — `Digital_Out._series_script` /
   `store_series` / `series` / `_stop_script` (`gpio.py:519-793`) compiles a waveform into a pigpio
   *stored script* so the pulse train runs inside the pigpio daemon, entirely off the Python GIL.
   `Solenoid.open` (`gpio.py:1632`) and `Pulse20Hz._build_script` (`:1691-1706`) both ride on it.
   **MICS added ~0 lines to this machinery and would have to reinvent it.** This is the item to name
   instead of ceding "hardware abstraction" wholesale — the abstraction is generic (§1.2), the timing
   layer is not.
3. **The plugin registry is still on the live task-resolution path.** Doc 14 §2.3's contrast
   (*"driver code lives on the Pi, imported by `utils/plugins.py` | MICS — in Postgres"*) is true of
   **hardware libraries only**. Task classes still resolve through Autopilot's registry:
   `autopilot.get_task(class_name=None, plugins=True, ast=True)` (`pilot.py:526`, the HANDSHAKE
   introspection that populates the backend's own task catalogue) and
   `autopilot.get_task(value['task_type'])` (`:593`, the START path), against **28 files** in
   `pilot/plugins/` with `prefs.json AUTOPLUGIN=true`. Legacy hardware groups (`GPIO`, `I2C`,
   `Timers`, `Mixer`, `UNREAL`) likewise still resolve via `autopilot.get_hardware(handler_string)`
   from prefs (`task.py:182-184`). **Delete `utils/plugins.py`/`registry.py` and no task starts.**
   Correct sentence: *"driver code for backend-managed modules is delivered from the database; task
   classes and legacy hardware groups still resolve from the Pi's plugin dir and prefs."*
4. **The `flags` protocol** — `NOREPEAT` / `NOLOG` / `MINPRINT` (`message.py:35-40`), per-message
   opt-out of ack and of logging so a high-rate stream does not drown the outbox or the logger.
   Small, genuinely thoughtful, and **MICS depends on both today**: the 5 s state ping carries
   `{'NOLOG': True}` (`station.py:1106,1154`) and `RouterGateway` honours `NOREPEAT` on both paths
   (`:152,192`). Mentioned in none of the four documents.
5. **The inherited `current_trial` semantics**, missed precisely because it looks like MICS's own
   code. Autopilot's `NTrials.__init__(n_trials, current_trial=0)` documents `current_trial` as
   *"If not starting from zero, start from here"* — a **resume offset**. MICS reads the same key as
   the **threshold** (`main.py:1752`), and its precedence chain prefers `current_trial` over
   `n_trials` (`:1646-1654`). An Autopilot-shaped protocol therefore resolves to `n = 0`, fails
   `n_required > 0`, and **never graduates**, silently. Inherited name, inverted meaning: worth a
   line in Methods and worth fixing in the schema.
6. **MPL-2.0 covers ten modified upstream files, not four.** MPL-2.0 is *file-level* copyleft, so
   every upstream file MICS modified in place must keep its notices and ship under MPL. This is a
   legal fact visible at code release regardless of what the manuscript says. The complete list is in
   §3.1.

Also worth crediting in one clause and then dropping: **transparent ndarray compression**
(`message.py:75-78,157-184,265`; `requirements.txt blosc==1.10.6`) — base64'd `blosc.pack_array`
through `json.dumps(default=)` with `expand_arrays=False` lazy decompression. It is the genuinely
non-obvious design idea inside `Message`, and **MICS runs it and never sends an ndarray.** Credit;
do not claim.

### 2.4 On the forked pigpio — the exact framing

This one needs care in both directions, because it is easy to overstate into an architectural debt
and equally easy to wave away.

**The facts.** `autopilot/setup.py:82` (and identically `autopilot/requirements/requirements_pilot.txt:18`,
**the line is identical at `30c8d3c`**) pins `pigpio @ git+https://github.com/sneakers-the-rat/pigpio`.
`sneakers-the-rat` is Jonny Saunders, Autopilot's author. Autopilot's `README.md:130` claims the
capability explicitly: *"Timestamps from GPIO events are now microsecond-precise thanks to some
modifications to the pigpio library"*, echoed at `gpio.py:7` (*"returns isoformatted timestamps
rather than tick numbers in callbacks"*) and `gpio.py:790`. `synchronize()` and
`ticks_to_timestamp()` are **that fork's API**: neither name appears anywhere in either repository
except as call sites in `Event_Dispatcher.py`, and no `pigpio.py` exists on disk to grep — which is
exactly why a search of the Autopilot *package* returns nothing and looks conclusive.

**The framing.** It is **a library dependency authored by Autopilot's author — credit it in one
clause — but it is not architecture.** Autopilot supplies tick ↔ wall-clock alignment *within one
Pi*, at microsecond resolution. MICS adds the *call* (`pigpio.pi(sync_ticks=True)` +
`self.pi.synchronize()`, `pilot.py:1139,1145`) and, genuinely, the *event stream to put it in*
(`Event_Dispatcher.py:44,77`) — Autopilot has no per-event stream to place a clock into. **Conceding
this costs MICS nothing architectural.**

**What must change as a result.** Doc 15 C8's *"Autopilot has no clock synchronisation. No NTP, no
tick alignment, nothing (searched 0.4.4)"* must be struck — it is false, and false in the direction
that flatters MICS, which is the worst kind of error to leave in a manuscript. The search was sound;
it covered the Python package and not its pinned dependencies. Replacement wording: *"Autopilot
provides within-station tick↔wall-clock alignment and no cross-machine synchronisation"*, and MICS
*"wires Autopilot's pigpio clock into a per-event stream Autopilot has no equivalent of."*

**And the symmetric correction on MICS's side, which is larger:** MICS has no cross-rig timeline
either. Each Pi's `synchronize()` anchors to its *own* wall clock; NTP is commented out in the very
commit that introduced it (`a008046`; sites `pilot.py:1138,1148`); `localize_tz` stamps each host's
local zone (`common.py:332`) while the backend re-stamps everything into one zone
(`ElasticSearchDateHandler.py:48-51`), *hiding* per-Pi offsets; and `ROADMAP.md:496` says so
outright — *"those machines are not NTP-synced to each other."* The claim *"periodic synchronization
with a global reference … a unified experimental timeline"* must be dropped.

---

## Part 3 — Corrected state of the system

### 3.0 The three-way ledger, compressed

Full version: doc 16 §2 (six sub-tables). Verdicts: **GENERIC** — claim nothing, concede nothing;
where MICS nonetheless runs Autopilot's bytes it is marked *(code dep)*, and **a code dependency is
not an idea dependency**. **AUTOPILOT** — distinctive design MICS depends on and must credit.
**MICS** — real new capability or architectural inversion.

**GENERIC — concede to nobody**

Daemon bootstrap (prefs, logging, pigpio init, networking thread) *(code dep)* · `{key: handler}`
dispatch *(code dep)* · `l_start`/`l_stop`/`l_param` RPC *(code dep)* · `run_task` on its own thread
*(code dep)* · `PARAMS`/`HARDWARE`/`TrialData`/`PLOT` class-attribute manifests *(code dep)* ·
`init_hardware()` *(code dep)* · central-callback funnelling of trigger pins *(code dep)* · the
`Hardware`/`HARDWARE`-dict/prefs abstraction *(code dep)* · BCM↔board pin table *(code dep)* ·
pigpio as the GPIO layer · the ZMQ envelope **as an idea** *(hard code dep)* · CONFIRM + outbox +
TTL resend · coordinator ↔ N executors · the Qt Terminal *as a program* · parameter forms rendered
from `PARAMS` · per-subject HDF5 as the unit of persistence · per-subject session counter · weights
table · the `Accuracy` *criterion* itself (50 lines of `deque` + `np.mean`) · Python `logging` +
`RotatingFileHandler` · MICS's own `OrchestratorState`, backend queues, 111 REST routes, React SPA,
JWT, Docker — **generic and MICS's own, and not a contribution**; say so first and the rest reads as
calibrated.

**AUTOPILOT — credit these**

Forked pigpio timebase (§2.4) · `gpio.py`'s pigpio stored-script waveform layer (`gpio.py:519-793`) ·
1,438 lines of tested pigpio drivers · local executor autonomy (a commitment, not a topology;
`CITATION.cff`, `core/pilot.py` inherited intact) · `self.stages` as an iterator of zero-arg callables
(thin — one line — but real) · the uniform agent/networking substrate shared by Terminal, Pilot and
Child, including a plot widget as a first-class network peer (`plots.py:231`) · the `flags` protocol
· transparent ndarray compression (credit, do not claim; unused by MICS) · the plugin registry, still
live on the task path · `TrialData` as schema authority · `History_Table` · `past_protocols`
(`subject.py:584-610`) — **MICS has no equivalent; `protocol_templates` rows are mutated in place, and
volunteering that makes the rest credible** · the graduation plumbing that trims history at a step
change (`subject.py:656-682`) so a subject stepped back down is not graduated by stale data ·
`Data_Handler`'s sink shape (a verbatim extraction of `Subject`'s sink lifecycle) · live per-trial
plotting + the operational tooling around it (port calibration with results shipped back to the Pi,
bandwidth test, plugin manager, batch reassign) · `transform/` + the `Transformer` child · `stim/sound`
jack/pyo at `FS=192000`, `-p16`, RT prio 75 · the MPL-2.0 obligation on ten files.

**MICS — claim these**

`FiniteDeterministicAutomaton` as `self.stages`, and the FDA **loaded from a JSON document** —
`fda_json` JSONB content-addressed by sha256 (`api/db.py:62-67`; `routers/toolkits.py:605-609`),
executed by ~520 lines of interpreter (`mics_task.py:1060-1269` and its helpers) · `saga_trace` +
`state_transition` on every state entry · generator-based interruptible states (`pilot.py:1188-1197`)
· **the trigger queue** (`c632674`) · per-trigger error isolation + `TRIGGER_ACTION_ERROR` ·
`@auto_log`/`@log_action` (`logging_utils.py:8-12,15-99`) — **0 matches for `auto_log|log_action`
across 518 files of the 0.4.4 sdist**, the single most checkable claim available · central input
instrumentation in `Task.execute_trigger` (`task.py:267-278`) · `Event`/`Hardware_Event`/
`Event_Dispatcher` — the inversion from *the task describes its data* to *the instrument describes
itself* · async egress queue + drop counters · one ES document per event stamped with `run_id` and
`session_progress_index` · `View`/`Tracker`/`FLAGS` — the invariant (string name + synchronous
non-blocking read + logged write) **without which the GUI-authored FDA cannot exist** ·
`HardwareState` IntEnum, `Sensor`/`Effector` ABCs, `event_dispatcher` ctor arg · `i2c.MPR121`,
`Motor_Shield_Hat`, `Touch_Detector`, `gpio.TTL`, `Solenoid_mics`, `Pulse20Hz`, `mixer.py`,
`timer.py`, `unreal.py` · driver source in Postgres, versioned/promoted/sha256'd with an on-Pi import
test · `SEMANTIC_HARDWARE` + renames · `pilot_hardware_config` (backend-authoritative prefs) ·
detector-derived per-channel view keys · 28-table Postgres model · **the session as a first-class
entity spanning subjects and rigs** (`models.py:410-481`) — Autopilot runs four animals at once
routinely but has **no entity that groups them**; claim the session, never the concurrency ·
`new`/`resume`/`restart` modes + `_strip_graduation_from_overrides` · **the UI off the data path** ·
**coordination state as durable rows** · the visual FDA canvas · **pre-dispatch static analysis** —
11 kinds (`toolkit_dispatch.py:155-167`) including `variable_never_written` and the sound deadlock
detector `state_wait_unsatisfiable` (`api/wait_analysis.py`), whose docstring names the real incident
it was written for (task def 186, run 541) · hot reload of a running task · the device lease
(`api/device_lease.py:184-202`, `UNIQUE(host)` at `api/db.py:294-311`) · handshake watchdog ·
`UPDATE_FDA` / `LOAD_HARDWARE_LIBS` / `INC_TRIAL_COUNTER`.

### 3.1 Authorship — settled

The provenance audit recorded `Ido Porat` (idoporat@Idos-MacBook-Pro.local, 2 commits) and `idopo`
(idoaomer@gmail.com, 19 commits) as **UNDETERMINED from git** — different email, different machine,
19 months apart, no `.mailmap`, no overlapping address, no co-author trailer. That was the correct
conclusion *from git alone*. It has since been settled out of band, and the settled facts govern:

- **`Ido Porat` = `idopo` = one person.** Treat every commit under either identity as his.
- **The `noa` / `noale17` commits are Ido and Noa working jointly.** This resolves audit 06 §2.7's
  open question about `53f86ab` (2026-04-29, a 692-file / +78,222-line bulk `git add .` whose edits
  demonstrably have more than one author, three of them verbatim the fixes specified in idopo's
  Pi-timing analysis 14 days earlier). Per-edit attribution inside it remains undeterminable from
  git — and no longer matters.
- **Ido Porat, Lior Segev, Noa and Inbar are all MICS lab members.** Every commit by any of them is
  MICS-team work. Lior Segev is the largest single contributor by commit count (117 of 185).

**The internal era split is history, never a basis for deciding what MICS may claim.** Dates belong
in the analysis only where they say something about *how the system evolved* — e.g. "the auto-logging
decorators were built by hand on the Pi in 2025, before the database layer existed" — never as a
boundary of ownership. There is exactly one boundary the manuscript defends: Autopilot vs MICS.

**One dated fact worth keeping, for the opposite reason.** The FDA class is MICS-team work from
**`8b7bd7c`, 2024-08-18** (Ido Porat), reaching the production branch via `94fb000` (Lior,
2024-11-11) as a byte-identical copy; 78 % of its original 67 lines survive in today's 96-line file.
It **predates the database layer by 18 months**. This matters because the FDA claim has two halves —
the automaton, and the *inversion* that loads it from a data document (`17e67d7`/`f5c4821`/`3aefcf3`,
2026-03-22) — and **both halves are MICS's**. Conflating them makes the claim harder to defend, not
easier; a reviewer who finds the 2024 date and reads it as a concession has been handed the
opportunity by the conflation.

### 3.2 Repository topology traps

**These will corrupt any future provenance analysis run against `/home/ido/pi-mirror`, silently.**

- **The repository has three disjoint root commits.** Verified:

  | Root | Date | Reachable from |
  |---|---|---|
  | `af2a03f` | 2021-07-21 | `origin/MICS_main` — **the real history** |
  | `4ea5338` | 2025-07-06 | `origin/second_setup` **only** |
  | `a3431c2` | 2026-03-22 | `hw_libs` (**the checked-out branch**), `master`, `statemachine_gui`, `origin/claude_ui_FDA`, `origin/hw_libs`, `origin/statemachine_gui` |

  The checked-out branch is an **orphan re-init**. `git merge-base --is-ancestor 30c8d3c hw_libs` →
  **NO**; `git merge-base --is-ancestor 30c8d3c origin/MICS_main` → **YES**;
  `git merge-base --is-ancestor 4ea5338 hw_libs` → **NO**. So **`30c8d3c` is not an ancestor of
  HEAD**, and neither is `origin/MICS_main`. (Precision worth carrying: HEAD's own root is
  `a3431c2`; `4ea5338` is a *different* orphan re-init reachable only from `origin/second_setup`.
  Both are orphans; only `a3431c2` is HEAD's.)
- **Consequences, both of which produce confident wrong answers rather than errors.**
  `git log -S… --all` reports the squash commits (`4ea5338`, `a3431c2`, `c756124`, `4f85d2c`,
  `53f86ab`, `8cb6a34`) as "introducing" lab code they merely re-imported; and **`git blame` on HEAD
  attributes ~78,000 lines of lab work to one 2026 commit** (`53f86ab`, +78,222 lines).
- **The correct method** is the one the audits used: determine every "introducing commit" against an
  explicit lab ref-set — never `--all`, never HEAD. The set is 23 refs:
  `origin/MICS_main origin/FDA_stateMachine origin/FDA_task origin/FDA_cleanup origin/Noa_FDA_cage
  origin/wip_inbar origin/db_setup origin/main origin/event_queue origin/event_logging
  origin/fda_real_cage origin/autonotify origin/ttl_sync origin/ADC_licker
  origin/multi_process_stage_mgmt origin/first_mics_box origin/RecBox origin/new-gui
  origin/fix-elastic-handler origin/event_logging_temp origin/gpio_out_pi_time_change_in_handshake
  origin/youri_pi origin/trace_fear_task`.
  185 commits total: 104 on `origin/MICS_main`, 81 off-mainline across 25 topic branches. **All
  objects are present, so content comparisons (`git show <ref>:<path>`) are sound** — it is only
  ancestry-based tooling that lies. Doc 14 §1b's *"`~/pi-mirror` retains the full project history
  (185 commits)"* is right on the count and wrong on "a history": it is **two unrelated histories of
  the same tree**, which is also the real maintenance liability §4's risk paragraph should describe.
- **`rg` is not installed on this host**, and bare `grep` is hook-rewritten to a token-compressing
  proxy that reports a missing binary as **`0 matches`** and can render a real matching line
  **blank**. Two live examples from the audit: `rg -n "FLAGS|self\.flags" mics_task.py` returned
  *"0 matches"* for a file with **31** matching lines, and the proxy rewrote `INC_TRIAL_COUNTER` to
  `n` inside one search. **Never assert that a symbol or import is unused from a filtered grep.** The
  `Camera` class (`i2c.py:8,580`, the base of `MLX90640`) was nearly deleted on exactly that evidence,
  which would have silently killed the pilot. Use `/usr/bin/grep` by absolute path, and corroborate a
  second way — read the file, `git show <ref>:<path> | /usr/bin/grep`, or a live Postgres
  `information_schema` query.
- **`git log` output is truncated by the same proxy** — `git log --reverse origin/MICS_main` printed
  50 lines where `git rev-list --count` reports 104. Cross-check counts with `rev-list --count`.

### 3.3 Vendored-file inventory (replaces the "four modified files" list)

Ten upstream files were modified in place, not four. All ten carry the MPL-2.0 file-level obligation.

| File | churn (vanilla → today) | live on the MICS path? |
|---|---|---|
| `core/pilot.py` | +501/−41 (823→1,283) | yes |
| `hardware/gpio.py` | +361/−83 (1,438→1,716) | yes |
| `hardware/i2c.py` | +179/−3 committed; +197/−3 with working tree | yes |
| `tasks/task.py` | +125/−31 committed (333→427); +157/−31 to the working tree (→459) | yes |
| `core/subject.py` | +56/−48 | **no — dead** |
| `core/plots.py` | +52/−14 | **no — dead** |
| `networking/station.py` | +47/−14 | yes |
| `hardware/__init__.py` | +44/−3 | yes |
| `core/terminal.py` | +44/−12 (966→997) | **no — dead** |
| `core/loggers.py` | +15/−7 | yes |

Byte-identical to upstream and still shipped: `networking/node.py` (643), `networking/message.py`
(269), `core/gui.py` (3,350), `hardware/cameras.py` (2,051), `hardware/usb.py` (357), `prefs.py`
(770).

### 3.4 Numbers that do not reproduce

Re-measured; where the old method is the likely cause it is named.

**Churn (doc 14 §1b).** The reproduction recipe mixed a **committed** blob (`30c8d3c:…`) with a
`cat` of the **working tree**, silently folding in 39 uncommitted paths (`log_value.py`,
`fda_vocabulary.py`, five `external_hardware*.py`, +513 lines of `mics_task.py`). **Pin both sides to
commits.**

| Doc 14 | Measured |
|---|---|
| `core/pilot.py` +415/−29, *"~96 % surviving"* | **+501/−41** ⇒ 95.0 % (823 + 501 − 41 = 1,283 ✓) |
| `core/terminal.py` "at import 997 → today 1,027, +38/−8" | **at import 966 → today 997, +44/−12** (the doc's 997 is *today's* count shifted one column left) |
| `hardware/gpio.py` +294/−72 | **+361/−83** |
| `tasks/task.py` 333 → 459, +141/−29 | **333 → 427 committed, +125/−31**; 459 is the *uncommitted working tree* (+157/−31) |
| `hardware/__init__.py` +32/−2 | **+44/−3** |
| `networking/station.py` +37/−13 | **+47/−14** |
| `hardware/i2c.py` filed as "inherited … unmodified or lightly modified" | **+179/−3 committed**, with four MICS classes (`MPR121`, `Motor_Shield_Hat`, `Motor_Shield_Hat_extend`, `Touch_Detector`). `cameras.py` and `usb.py` really are +0/−0; grouping `i2c.py` with them misstates it — and `usb.py` is **dead**, not load-bearing |
| "~44 / 29 / 53 commented-code lines in `pilot.py` / `task.py` / `gpio.py`" | **Not reproducible.** A naive regex gives 136/57/123 (it over-counts prose); Phase 30's own audit puts the whole-repo figure at 244 (`ROADMAP.md:40`). Treat as unverified rather than wrong |

**Dead upstream LOC.** *"≈6,855 lines of Terminal-side code carried but unused"* is wrong and
understated — 6,855 is exactly `terminal.py 997 + gui.py 3,350 + plots.py 1,147 + subject.py 1,361`,
but the sentence sits under a list that also names `viz/`, `transform/`, most of `stim/` and six
upstream task modules. **Adjudicated figure: ≈11,900 LOC across 35 upstream modules**, from an AST
import-closure rooted at `core/pilot.py`, `tasks/{mics_task,learning_cage,task}.py`,
`autopilot/__init__.py` and every file in `pilot/plugins/` (98 modules; 59 reachable / 20,105 LOC,
39 unreachable / 12,171 LOC). Prefer 11,900 over audit 07's independent ≈14,000 because it has an
explicit reproducible method. **Stated caveat:** the closure is import-based and over-counts as
"reachable" `hardware/cameras.py` (2,051), `transform/{geometry,timeseries,transforms}.py` (1,523)
and `stim/sound/*` (1,266) — imported by reachable modules, exercised by no MICS task. A call-graph
analysis pushes the total toward ~16,700. **Honest range: ≈11,900–16,700.** Also missing from doc
14 §1's dead list: `hardware/usb.py` (358), `stim/managers.py` (615), `stim/sound/sounds.py` (445),
`stim/visual/*` (233), `setup/request_helpers.py` (124), `core/{reward,styles}.py` (152),
`utils/invoker.py` (51). And a category the ledgers lack entirely: **MICS-added-but-dead** —
`Data_Handler.py` (39), `ElasticSearchDataHandler.py` (63), `RecordingBox.py` (117),
`utils/Event.py` (34) = **253 LOC**.

**Counts and line references.**

| Doc claim | Correct |
|---|---|
| "27 Postgres tables" (doc 14 §1, §2.4, §5.5; doc 15 C7) | **28** — the 28th is `device_leases`, created by Phase 18 on 2026-08-09 (`api/db.py:299`). 27 was correct on 2026-08-06. Split: 12 SQLModel + 16 SQLAlchemy |
| "Preflight: nine issue kinds, `toolkit_dispatch.py:153-163`" (docs 12–15) | **11 kinds at `:155-167`**; `compute_lib_import_failed` is RESERVED and never emitted (`:170-179`), so **10 are emittable**. Doc 13 §4.6 lists it among what preflight "catches" — it does not |
| Graduation at `api/main.py:1747` (docs 12–15) | **`api/main.py:1750`**. Substance correct; no other evaluator exists in `api/` or `orchestrator/` |
| `logging_utils.py:14,24` for `auto_log`/`log_action` (docs 13–15) | **`:8`** and **`:15`** |
| "Message vocabulary: same **8**, +2" (doc 14 §2.1) | Upstream `Pilot.listens` has **7** keys (B1 `pilot.py:185-193`); MICS has **9** (`pilot.py:214-225`, new keys at `:223-224`). The cited range `:215-225` is off by one. The *inbound* orchestrator vocabulary is separately larger (`orchestrator/main.py:71-81`) |
| `mics_task.py` "1,487 lines"; `condition_tree` at `:1105`; `if` actions `:646-694`; `check_determinism` at `FDA.py:37` | **~1,601 lines** today. `condition_tree` read at **`:1216-1221`**, `_build_tree_lambda` at **`:1361`**, the `type:"if"` builder spans **`:685-733`**; `check_determinism` **defined at `:38`**, called at `:36` |
| `mics_task.py:194-201` for backend-authoritative prefs | **`:233-252`** (`_merge_prefs_hardware`); `:194-201` is now the extlink bind loop |
| `pilot.py:328,427` for SEMANTIC_HARDWARE introspection | **`:326-339`** and **`:430-451`** |
| `terminal.py:576-594` for `l_data` (doc 14 §5.2) | B1 **`:579-606`**; HEAD **`:596-630`** |
| `pilot.py:1207` for the `DATA` send | **`:1210`** (`:1207` is `# data['subject'] = self.subject`) |
| `Blueprint` collision at `api/main.py:851, 920, 1316, 1905` | Substance correct, lines stale by ~3: `:923`, `:946`, `:1319-1320`, `:1908-1909`, `:854`, `:1224` |
| Run-mode branches at `main.py:1264,1279` | **`:1268`, `:1281`** (and `:1312` for `new`) |
| `Event_Dispatcher.py:38-48` for the envelope | **`:38-49`** — and add the gloss: **`subject` holds `bp_s{session}_r{run}`, a run key, not an animal** (`main.py:1375`); the animal is in the `subjects` list |
| `api/` ~8,100 lines · `orchestrator/` 1,709 | `api/` non-test = **8,976**; `orchestrator/` **1,830** top-level, **3,116** with subpackages, **of which ~700 are vendored Autopilot** |
| Doc 14 §1: *"MICS outside the package — no Autopilot analogue: … `orchestrator/`"* | **Contradicts doc 14 §1c two pages later** — the orchestrator *vendors* ~700 lines of Autopilot networking including a byte-identical `message.py`. §1c is right; §1's ledger row is wrong |
| Doc 14 §1c: *"`node.py` cut 643→176", "`station.py` cut 1,328→255"* | Those two orchestrator files are **dead code** — nothing imports them; only `message.py` is imported (`RouterGateway.py:10`). Rewrite as *"the orchestrator vendored `message.py` (byte-identical) and carries two unused trimmed copies"* |

**Two claims formally retracted** from working notes if they reached any: *"float values are
truncated"* and *"Phase 18 has a genuine liveness bug."* Both false.

### 3.5 Phase status and tense

All four documents write Phase 18 in the future tense. **Phase 18 shipped on 2026-08-09** — `STATE.md`
(`last_updated 2026-08-09`) records **COMPLETE, 15/15 plans**, with a six-run rig checkpoint (pilot 1
/ session 115 / task_def 434, runs 552–556; 552/554/556 PASS). Corroborated live: `device_leases`
exists as the 28th table (`api/db.py:299`); `device_held` and `extlink_config_invalid` are in
`PREFLIGHT_ISSUE_KINDS`; five `external_hardware*.py` modules exist on the Pi.

**What within it remains unproven on hardware, and must survive any rewrite:**

- **`sub_connect` (EXTLINK-14) — UNPROVEN on hardware.** This is exactly the transport Open Ephys
  needs, so **the foreign-publisher path cannot be claimed.**
- **`role:"none"` (EXTLINK-18) — unproven.**
- **Browser-picker authoring (EXTLINK-19) and the ~60 Hz soak (EXTLINK-20) — unproven.**
- **A standing operational dependency:** a TCP echo listener must keep running on
  `132.77.73.125:5597` or `demo.alive` flips false. Two of the six checkpoint runs failed with
  `EXTLINK_GATE_TIMEOUT`, root-caused to fixture misconfiguration.

Other status corrections: doc 12's header ("22 live phases, 7 complete, 72 %") → **24 phases, 8
complete, 64/85 plans, 76 %**. **Phase 19** is not "0 plans" — it has 3 (`19-01/02/03`, planned
2026-08-05), still unexecuted, so doc 14 §2.4's "device-health badge (Phase 19)" reports planned work
as existing and should be deleted. **Phase 26** is no longer blocked on 18 (13 plans, unexecuted).
**Phase 30 (Pi Repo Cleanup)** exists and is absent from all four documents. Phases 25/29 (5/6 and
7/8) and 27/28 (0 plans) are correct, and doc 13 §4.8's present tense on `ui_layout` is correct —
plan 29-04 landed the JSONB column.

**Read `STATE.md`, not the ROADMAP table**: `ROADMAP.md`'s summary table is column-shifted for rows
11–14, 16 and 18 (`STATE.md:1665` records the corruption) and Phase 18's checkboxes there are stale.

### 3.6 Six code changes that convert a false claim into a true one

Listed because they are worth more to the manuscript than any rewording (doc 16 §6, F1–F6):

| | Fix | Converts |
|---|---|---|
| **F1** | Re-run preflight inside `POST /runs/{run_id}/start` → 409 on unresolved hard issues; disable `HardwareCheckModal.tsx:551`'s button; stop `PilotSessions.tsx:100-102` falling through to `doStart` on error (~20 lines) | *"preflight hard-blocks"* — false today; `orchestrator_station.py:387-388` concedes it in its own comment |
| **F2** | Write the resolved `{lib_id: version_id, reason}` map onto the `session_runs` row at dispatch — the orchestrator already holds it at `orchestrator_station.py:947-950` (one column) | *"the driver code that ran your experiment is a versioned artifact recorded against the run"* — the most dangerous over-claim in the set |
| **F3** | 422 on a non-`NTrials` `graduation_type` at `_coerce_graduation` (`main.py:1607-1660`) | a silently inert protocol step |
| **F4** | Route the FDA `special: INC_TRIAL_COUNTER` action through `Event_Dispatcher` (or inject the subject) — `mics_task.py:786-789` sends `value={}`; `orchestrator_station.py:588-590` returns early on a falsy subject | a Blueprint action that is a silent no-op |
| **F5** | Re-enable `TTL1` in the live path — `learning_cage.py:85-86` declares it, `:191`/`:208` and `mics_task.py:1594` are commented | *"TTL provides cross-device alignment"* |
| **F6** | Rename the graduation threshold key `current_trial` → `n_trials` (`main.py:1646-1654,1752`) | the inherited-semantics trap of §2.3.5 |

---

## Part 4 — Standing rules for future comparisons

1. **Classify by conceptual novelty, not by diff size.** Ask the two questions of §1.2 — *would a
   competent from-scratch implementation have landed somewhere materially different?* and *does every
   comparable framework already have one?* — before assigning any row to Autopilot. A diff tells you
   who typed the bytes; it does not tell you who had the idea.
2. **Check the upstream project's own claimed contributions before conceding one.** `CITATION.cff`,
   README, and the paper. If the upstream authors do not claim it, you are conceding something nobody
   is asking for — and doing so decalibrates every concession you *do* make.
3. **Check pinned dependencies, not just the package.** The forked pigpio was missed by an
   exhaustive, correct search of the Autopilot Python package, because the capability lives in
   `setup.py:82` / `requirements_pilot.txt:18`. Read `setup.py`, `requirements*.txt`, submodules and
   vendored trees before writing "X has no Y."
4. **Verify absence with a real grep and a second independent method.** `/usr/bin/grep` by absolute
   path (never `rg`, never bare `grep` under the proxy), corroborated by reading the file, by
   `git show <ref>:<path> | /usr/bin/grep`, or by a live database query. Include a **positive
   control** in the same sweep — a symbol you know is present — so the search proves itself. The
   audit's absence claims were all established this way; 36 MICS symbols returned 0 vanilla files
   against 14 positive controls returning 1–7.
5. **Verify phase status before writing in the present or future tense.** Read `STATE.md`, not
   `ROADMAP.md`, and record the date you read it. Four documents describe a shipped phase as planned
   because they were written days before it landed — an entirely ordinary way to be wrong, and one
   that a dated status line prevents.
6. **Separate code dependency from idea dependency, explicitly, in the ledger's vocabulary.** *"We
   run Autopilot's networking layer unchanged"* is a verified fact and a fair concession. *"We build
   on Autopilot's messaging architecture"* concedes a design contribution that `json.dumps(self.__dict__)`
   does not support. Mark inherited-code-but-generic-idea rows as **GENERIC (code dep)** so the two
   never merge.
7. **For every "inherited" row, ask whether it executes; for every "unchanged" row, ask whether its
   meaning changed around it.** These two questions catch, respectively, the ≈11,900 lines of dead
   upstream code and the trigger queue.
8. **Prefer a figure with a reproducible method over a larger figure without one**, and publish the
   method and its caveat alongside it (as with 11,900 vs 14,000, and the honest 11,900–16,700 range).
   Pin both sides of any diff to commits — never diff a commit against a working tree.
