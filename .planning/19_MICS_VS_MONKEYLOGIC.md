# MICS vs NIMH MonkeyLogic — talk preparation

**Audience:** a talk at which **Yoav Livneh (Weizmann, Brain Sciences)** will be present — a
MonkeyLogic user doing closed-loop work.
**Purpose:** what each system can and cannot do, how easy each is to use, where the data lives,
and — the part that actually matters — **what it costs to change each one**, on a scale, not as
yes/no.

---

## 0. How to read this

Every factual claim carries a confidence marker. Do not put an unmarked claim on a slide.

| Mark | Meaning |
|---|---|
| **[V]** | Verified against a primary source — MonkeyLogic v2.4.0 distribution source / official docs / the papers / the NIMH forum, or MICS source at `file:line` |
| **[C]** | A concession. True, and it costs us something. Say it before you are asked |
| **[U]** | Unverified. Do **not** say it on stage |

Two governing rules, inherited from `17_COMPARISON_METHOD_CORRECTIONS.md`:

1. **The discipline that forbids over-claiming for MICS forbids under-crediting MonkeyLogic.**
   MonkeyLogic is mature, actively maintained, free, and excellent at what it was built for.
   Say that first and mean it.
2. **For every "we have X", ask: is it executed, on a rig, today?** Built-and-never-deployed is
   not a capability. This document separates the two everywhere.

---

## 1. The whole difference, explained simply

**One sentence:** MonkeyLogic is a *program you write* that runs one experiment perfectly on one
computer; MICS is a *form you fill in* that runs many experiments, on many machines, for months,
and remembers everything.

Neither is the better program. They answer different questions.

| | **MonkeyLogic** | **MICS** |
|---|---|---|
| **What is a task?** | A recipe you **write in code** | A recipe you **fill in on a form** |
| **Where does it live?** | One kitchen | A restaurant chain with a head office |
| **What gets saved?** | A photo album — one photo per trial | A security camera — one long stream |
| **How does it keep time?** | A **metronome** — do this exactly on the beat | A **doorbell** — do this the moment that happens |
| **Who can use it?** | Someone who writes MATLAB | Anyone who can use a website |
| **What can it plug into?** | One brand of hardware, and it just works | Anything — but you build the adapter |
| **Who's in the room?** | A scientist, watching | Nobody. It runs all night |
| **What does it remember?** | This session | The animal's whole life |
| **How grown-up is it?** | 18 years old, 174 releases | In-house, still being built |

**The trade in one line:** MonkeyLogic gives you *unlimited freedom inside one session*, because
a task is code and code can do anything. MICS gives you *unlimited memory across sessions*,
because a task is data and data can be stored, searched, checked and re-run. Each pays for the
other's strength.

## 2. What NIMH MonkeyLogic is — say this first, and generously

NIMH MonkeyLogic (NIMH ML) is a free, MATLAB-based system for behavioral control and data
acquisition. A scientist writes a trial as a plain MATLAB script — in the language they already
use for analysis — and executes it with frame-locked stimulus control, 1 kHz behavioral sampling,
and sub-millisecond event marking to a neural acquisition system. **[V]**

- Object-oriented rewrite of Asaad & Eskandar's MonkeyLogic (2008), itself descended from NIH
  CORTEX. The handoff from the Asaad/Freedman labs to NIMH was cooperative. **[V]**
- Maintained by **Jaewon Hwang**, Staff Scientist, LN/NIMH. **[V]**
- **Genuinely, actively maintained:** current release **v2.4.0 (Mar 27 2026)**; **174 dated
  releases** in `changes.txt`; the maintainer personally answers a forum with **2,025 Q&A
  posts** (1,017 of them his own). **[V]**
- **Costs nothing. Requires no MATLAB toolboxes.** Runs with no hardware at all in simulation
  mode. **[V]**
- Citations: 132 (Hwang et al. 2019), 149 (Asaad & Eskandar 2008a). **[V]**

**What it is genuinely best-in-class at** — concede all of this without hedging:

1. **Frame-locked visual stimulus control with the tooling to prove it** — a video latency test,
   a **Photodiode Tuner**, and **10 bundled benchmark tasks** in `task/benchmark/`. Very few
   systems ship their own measurement harness. **[V]**
2. **Eye tracking as a first-class citizen** — monocular/binocular, voltage or TCP/IP, five
   vendor integrations, two calibration methods, online drift correction, mid-session
   recalibration hotkeys, a degrees-of-visual-angle coordinate system with tangent correction
   beyond 20°. **[V]**
3. **Neural alignment via strobed event codes** — configurable strobe spec (default T1 = T2 =
   125 µs), reserved codes 9/18 bracketing each trial, documented pitfalls. **[V]**
4. **A rich built-in behavioral vocabulary** — `WaitThenHold`, `FreeThenHold`, `LooseHold`,
   `MultiTarget`, `ComplementaryWindow`, `BlinkDetector`, `RandomDotMotion`, `SineGrating`, RF
   mappers, `RewardScheduler`, `DragAndDrop`, `CurveTracer`. >50 built-in adapters. **[V]**
5. **`mlplayer`** — full trial replay and video export, reconstructed from stored adapter initial
   conditions. **[V]**
6. **Longevity** — ML1 scripts from 2008 still run. **[V]**

---

## 2a. The nine real differences — the spine of the talk

Each one: the plain version first, then what is actually true underneath.

---

### 1. A task is **code** vs. a task is **data**

*Plain:* Theirs is a recipe you write out yourself, so you can cook anything. Ours is a form you
fill in, so the kitchen can read it, check it, copy it and change it while you're cooking.

*Underneath:* A MonkeyLogic task is a MATLAB script fused at run time into a generated function
(`embed_timingfile.m`). Anything MATLAB can do, the task can do. **[V]** A MICS task is an FDA
stored as JSON in Postgres, interpreted by a ~520-line interpreter with closed vocabularies and
**no `eval`**, content-addressed by sha256. **[V]**

**This single difference generates almost every other one.** Because MICS tasks are data they can
be: authored in a GUI with no deploy, hashed, diffed, hot-reloaded over the network, and
**statically analysed — including a sound deadlock detector**. Because MonkeyLogic tasks are code
they can be: anything at all, but never inspected, never checked before running, and **never
stored** — `embed_timingfile.m` compiles the script and never writes the text, so the task source
is *not* in the data file. **[V]**

**Cost of change.** New task in MonkeyLogic: **write a script (level 2)** — but any task at all.
New task in MICS: **fill in a form (level 0)** — but only within the vocabulary. New *vocabulary*
in MICS: write Python (level 2).

---

### 2. One machine vs. a distributed system

*Plain:* Theirs is one kitchen. Ours is a chain of kitchens with a head office.

*Underneath:* MonkeyLogic is **one single-threaded MATLAB process, one GUI, one PC**, and you
cannot run two instances — maintainer, Apr 2025: *"Unfortunately it does not work in that way,
mostly because of the graphics."* N rigs = N Windows PCs, each with two monitors. **[V]** MICS is
Postgres + an orchestrator + N Raspberry Pis over ZMQ + Elasticsearch + Redis, with atomic device
leases and a web UI. **[V]**

**What each buys.** Theirs: no network, no queues, one clock, far fewer failure modes — a genuine
robustness advantage that is easy to sneer at and shouldn't be. Ours: many rigs and many animals
coordinated from one place, remote monitoring, and unattended operation.
**What each costs.** Theirs: no remote control at all — *"you can run tasks on a desktop with two
monitors but just with long cables"* (maintainer, Jan 2026). **[V]** Ours: unbounded event queues
with print-only drop counters, a 50,000-cap trial queue that drops with a warning and no counter,
and no exception boundary on the trigger worker. **[C]**

---

### 3. The **trial** vs. the **event**

*Plain:* MonkeyLogic keeps a **diary with one page per trial**. MICS keeps a **notebook where it
writes down every single thing the moment it happens**, forever, and never draws a line between
trials.

**The diary.** When a MonkeyLogic trial ends, it writes the page and starts a new one. The page
already has: which condition this was, what the animal did, whether that was right or wrong, how
long it took, every event code with its time, and the sensor squiggles for that trial. Then the
file is appended to disk **between trials, never during one** — so writing to disk can never make
a trial late. **[V]**

**The notebook.** MICS writes one line per happening — *"light on", "lick", "lick", "valve open",
"beam broken"* — as an Elasticsearch document, ~2.92M of them. Nobody ever writes "trial 12
ended". **[V]**

#### Correction, verified live against the event store (2026-08-19)

**An earlier draft of this document said MICS "loses the trial" and that outcome / choice / RT are
"recorded nowhere". That was wrong.** Queried directly against `event_log_v2` (2,921,653 docs):

| event type | docs |
|---|---|
| `state_transition` | **930,063** |
| `false_alarm` | 12,191 |
| `trial` | 12,511 |
| `Trial_Tracker` | 9,505 |
| `miss` | 6,030 |
| `hit` | 6,012 |
| `TRIAL` / `trail_onset` | 212 / 80 |

So: **trial boundaries are logged, outcomes are logged, and every FDA state transition is
logged** — the largest single event type in the store. Because the whole state path is recorded,
MICS can in principle reconstruct something *richer* than a per-trial outcome code: not just
"this was a false alarm" but the entire route the animal took through the task. **[V]**

And the centralisation point is real and was under-sold: because this is one database rather than
a file on a rig PC, **you can query it across animals and rigs while the experiment is still
running.** MonkeyLogic structurally cannot — the file is local and `behaviorsummary.m` takes one
filename. **[V]**

#### What actually survives: convention, not schema

The honest gap is much narrower than "no trials", and it is this — **the data is there, the
guarantee is not.** Verified payload shapes, all from live documents:

```
hit          → event_data: {"hit": 1}
false_alarm  → event_data: {"value": 1}
trial        → event_data: {"value": 1}
trail_onset  → event_data: {"trail_num": 5}
```

**Four different shapes for the same class of fact.** Add to that: the `trial` / `trail` spelling
split and the `trial` / `TRIAL` / `Trial_Tracker` case split; **no `correct_rejection` anywhere in
the vocabulary**, so the fourth cell of a go/no-go confusion matrix is inferred rather than
recorded; and `session` / `task_type` present on some documents and absent on others. **[V]**

Most importantly: **only 8,673 documents out of 2.92M carry a trial number.** A lick does not say
which trial it belongs to. Reconstructing "trial N" means windowing between boundary events by
timestamp — genuinely easy, and the user is right that it is easy, but it is a **join, not a
lookup**, and it depends on the task author having emitted the boundary at all. **[C]**

**The defensible claim, and the one to make on stage:**

> MonkeyLogic *guarantees* every trial in every task ever written has a `TrialError` and a
> `ReactionTime`, in a documented format. MICS *records whatever the task author chose to emit,
> under whatever name they chose.* The trial is not lost — the **schema** is.

That reframing also points at the cheap fix: **standardise the trial and outcome event
vocabulary** (one spelling, one payload shape, a trial number stamped on every document). That is
far less work than "build a trials table", and it converts an existing strength into a
guaranteed one.

### 4. A **metronome** vs. a **doorbell**

*Plain:* A metronome goes tick-tick-tick and you must do your thing exactly on every tick,
forever, never late. A doorbell does nothing at all until somebody presses it — then you jump up
and answer. MonkeyLogic is a metronome. MICS is a doorbell.

**The metronome.** MonkeyLogic's screen ticks 60 times a second and its sensors tick **exactly
1,000 times a second internally, no matter what the menu says**. The frame loop deliberately
**waits** for the tick (`mglpresent()` blocks on vblank). Everything is on a schedule. **[V]**

**The doorbell.** MICS's task engine sits in a loop asking *"has anything happened?"* every half a
millisecond (`time.sleep(0.0005)`), and acts the moment something does. There is **no periodic
schedule at all**. **[V]**

#### What each one is genuinely good at

**The metronome can promise the future — and know when it looked.**

- *Know when it looked:* if you sample at exactly 1 kHz, sample #3,000 is exactly 3.000 s in. You
  can lay it against anything — a microscope, an electrode, another rig.
- *Promise the future:* "the picture will change at exactly this moment." You need that to show a
  moving pattern, or to line up with a camera taking 31 pictures a second.
- *Know when it failed:* it counts dropped ticks, can event-code them, and shows drawing time
  live on screen. **[V]**

**The doorbell never makes anything wait.**

- If the animal responds, you act now — not at the next tick.
- It fits behaviour that is **self-paced and unpredictable**, which is exactly what an animal
  alone in a home cage for three days produces. There are no trials to tick through.

#### What each one costs

**The metronome's cost is granularity.** If the animal responds just *after* a tick, nothing can
happen until the next one — **16.7 ms later**. The paper concedes it outright: *"the occurrence
of the fixation may not be known until the next frame."* Sub-frame work needs the v1
`eyejoytrack` path, which polls at ~1 ms but **cannot redraw the screen**. **[V]**

#### Correction: three things MICS already does that a metronome is often credited with

Do not concede these — they are verified. **[V]**

1. **Microsecond timestamping.** GPIO edges are timestamped by pigpio's **DMA sampler**,
   independently of when Python gets round to handling them. For *digital edges* this is
   arguably better than MonkeyLogic's CPU-clock event timing. (Credit the forked pigpio for it,
   not MICS.) Phase 31's clock work makes it monotonic and wrap-safe — **though it is deployed on
   no rig yet.**
2. **Receiving someone else's metronome.** An external frame clock or sync pulse is just a digital
   input; MICS can timestamp every tick of it. Sync-*in* is not the gap.
3. **Hardware-timed output.** `gpio.py:627` precompiles a pulse series with pigpio
   `store_script()` and fires it with `run_script()` (`:684`) — it executes on the pigpio daemon,
   **not in Python**. That is the same idea as preloading a waveform into an NI board's buffer,
   which is exactly what MonkeyLogic's maintainer says is mandatory for sub-ms output.

So "MICS can't do precise timing" is **not** the right claim, and would be easy to refute.

#### What the metronome actually buys that MICS has no answer for

Only two things — but they are real, and they are the honest answer to *"so what is a metronome
for?"*

**(1) Continuous analog signals. MICS has no analog input at all. [C]**
An analog voltage — eye position, pupil diameter, force, EMG, a spike-rate DAC from a neural
system — has **no edges to trigger on**. There is no event. You must sample it on a regular grid
or you simply do not have the signal. MonkeyLogic samples **16 analog channels at exactly 1 kHz,
always, regardless of the menu setting**. **[V]** MICS is entirely digital: verified, there is
**not one ADC, analog-input or fixed-rate sampler class** anywhere in the hardware layer (24
hardware classes across `gpio.py`, `i2c.py`, `mixer.py`, `timer.py`, `external_hardware*`).
This is the single cleanest capability gap in the whole comparison.

**(2) A record of the silence. [C]**
This is the deep one. In an **event** stream, "no event" is ambiguous — it means *nothing
happened*, or *the detector didn't fire*, or *the event was dropped*. On a **guaranteed 1 kHz
grid** you hold a sample for every millisecond, so you can positively see that nothing happened.
That distinction matters more for MICS than for most systems, because MICS has known silent drop
paths: the trial queue is capped at 50,000 and **drops with a `logger.warning` and no counter**,
and the event queues carry print-only drop counters. **A dropped event and a quiet animal look
identical in the record.**

> **The metronome records the silence. The doorbell only records the rings.**
> That, plus continuous analog, is the whole of what it buys — not timestamp precision, and not
> the ability to sync to something else.

#### The punchline

> **"Fast" and "on time" are not the same thing.**
> A doorbell answered in 5 ms on average but occasionally 46 ms is *fast but not punctual*.
> A metronome that is always exactly on the beat but only beats 60 times a second is *punctual
> but not fast*.
> Which you need depends on whether your experiment is driven by the **apparatus** (metronome) or
> by the **animal** (doorbell).

**And you can have both — both systems do.** MonkeyLogic pairs its frame loop with `eyejoytrack`
for ~1 ms reactive polling. MICS pairs its reactive loop with hardware libs that own their own
threads (§3a). Neither is purely one thing; the difference is which one is the *default*, and
therefore which one the rest of the system is shaped around.

#### A symmetry worth noticing: both have a two-clock problem

Neither system runs on one clock, and both know it.

- **MonkeyLogic:** *"ML2 uses the CPU clock to time events, while analog signals are digitized
  based on the NI board's clock… which results in a missing/extra sample every few minutes."*
  `mlconcatenate` corrects it offline, and the maintainer's advice is to feed everything into the
  neural acquisition system so all samples share one clock. **[V]**
- **MICS:** every hardware document carries **two** timestamps — the envelope `timestamp`,
  inflated by queue latency (+5.2–6.5 ms mean, 144 ms max), and `event_data.pi_timestamp`, the
  actual edge. **Using the envelope one to measure response latency measures the queue, not the
  animal.** **[C]**

If someone raises clocks, this symmetry is the fair answer: *everyone* has this problem; the
question is only whether the system tells you about it. Theirs documents it. Ours does not yet.

### 5. Who is allowed to build an experiment

*Plain:* Theirs needs someone who can program. Ours needs someone who can use a website.

*Underneath:* MonkeyLogic's GUI is excellent — screen geometry, pixels-per-degree, I/O
assignment, strobe spec, calibration, latency test, photodiode tuner, block logic, ITI, error
handling — but it is a **configuration** GUI. Asaad et al. 2013 say it outright: *"no
drag-and-drop creation of behavioral tasks."* **[V]** MICS authors states, transitions, nested
AND/OR conditions, action lists, variables, 13 compute primitives and trigger assignments **in
the GUI, with no code and no deploy**. **[V]**

**What each costs.** Theirs: a non-programmer can *run* a session and change parameters, but
cannot build or modify a task. Ours: a researcher can build a task, but is bounded by the
vocabulary until someone writes Python (see §3a).

---

### 6. One brand of hardware vs. any hardware you can wire

*Plain:* Theirs works with one brand of tools, and works beautifully. Ours works with anything,
but you make the tool yourself.

*Underneath:* MonkeyLogic speaks **National Instruments DAQ only** — the 2019 paper's *"expanded
hardware support is on our roadmap"* is still unfulfilled in v2.4 (2026). Parallel port, sound
card and Arduino are also supported for simple jobs. **[V]** MICS drives arbitrary GPIO / I2C /
SPI on a Pi, with driver source stored as **immutable hash-addressed DB rows** with a promotion
lifecycle and a real on-rig import test. **[V]**

**What each buys.** Theirs: buy the standard board, it works, everyone else has the same one, and
it is genuinely well-engineered — sub-ms analog output *because the waveform is preloaded into
the board's buffer*. Ours: wire anything, and know exactly which driver version exists.
**What each costs.** Theirs: two independent stimulation channels require **two DAQ boards**; no
non-NI hardware, ever. **[V]** Ours: you own every driver, and **the driver version is not yet
recorded against the run** (one column). **[C]**

---

### 7. Someone is watching vs. nobody is watching

*Plain:* Theirs assumes a scientist is sitting there. Ours assumes the building is empty.

*Underneath:* MonkeyLogic's live control screen shows a replica of the subject screen with eye
trace, event timeline, performance bars, frame interval and drawing time; the pause menu lets you
switch block, recalibrate, give manual reward, trim reward duration ±10 ms and **edit task
variables mid-session**. **[V]** It has **no autostart, no watchdog and no crash recovery**;
forum search for "unattended" returns zero results; the one published home-cage deployment ran
~90 min/day with staff moving animals. **[V]** MICS is built for the opposite: unattended,
multi-day, nobody present. **[C]** *— but concede that the unattended-boot systemd work is built
and running on no rig yet.*

---

### 8. The session vs. the animal's whole life

*Plain:* Theirs remembers the meal. Ours remembers the animal.

*Underneath:* MonkeyLogic has **no subject database**. Per-subject state is variables named
`MLConfig_<subject>` inside one `*_cfg2.mat` file next to the task; forum searches for "database"
and "training stages" return zero substantive hits. **[V]** MICS has 28 Postgres tables —
subjects, **weight measurements**, **surgeries**, projects, experiments, researchers, IACUC
protocols, protocols and steps, sessions and runs. **[V]**

**What each costs.** Theirs: every cross-day, cross-animal question is a spreadsheet. Ours: only
`NTrials` graduation actually fires (`api/main.py:1750`, a bare `if` with no else branch), so the
progression logic that should exploit all that structure is barely used. **[C]**

---

### 8b. A self-contained **application** vs. an **integration layer**

*Plain:* MonkeyLogic is one program that tries to do everything itself, and does it well. MICS is
a switchboard — its answer to "can you do X?" is usually *"we plug X in and keep it on our
clock."* **If it can't beat you, it joins you.**

*Underneath:* this is a genuine architectural difference, not a euphemism for a missing feature,
and it changes what the right question is. Asking *"does MICS have an eye tracker / a
spectrometer / a treadmill / an ephys system?"* is usually the wrong question. The right one is
**"can MICS ingest it, keep it on one timebase, and let a non-programmer gate a state transition
on it?"**

**The mechanism is Phase 18 (MICS-Link), 15 plans, all shipped. [V]** What it provides:

- **Three transport roles** — `router_bind` (the device connects to us), `sub_connect` (we
  subscribe to a foreign publisher), and `none` (control-only, e.g. polling a device's HTTP
  status) — chosen by config, with no port invented and no silent fallback.
- A typed **msgpack wire format** with declared dtypes, value coercion and envelope decoding.
- **Liveness and staleness** as first-class concepts (`resolve_stale_value`,
  `validate_role_liveness`) — the system knows when an external source has gone quiet, which is
  exactly the failure mode that kills naive integrations.
- **Decoder isolation** — a raising decoder never propagates.
- And the part that matters most here: external values land in the view as **trackers named
  uniformly by `source_id`**, *"identical view-key naming across all roles"*. So a foreign
  signal becomes an ordinary view key, usable in a GUI-authored transition exactly like a lick.

**Why this is a real answer and not a dodge.** MonkeyLogic does the same thing where it must —
its eye trackers arrive over TCP/IP, its LSL inlet subscribes to a foreign publisher. The
difference is that for MonkeyLogic integration is the exception, and for MICS it is the
architecture. Note the consequence, verified from their own docs: **MonkeyLogic's TCP/IP eye
trackers have no sample clock and are polled on a ~1 ms software timer.** **[V]** A MICS
integration is therefore not a lesser move — and if the device emits a sync pulse, MICS can stamp
it in microseconds on the same clock as everything else.

**And it is demonstrated on hardware, cross-machine. [V]** A reference driver exists
(`extlink_driver.py` + `extlink_wire.py`, ~10 KB, pyzmq + msgpack) and has been run **from a Mac
against a live state machine on a Pi rig** over LAN — `pilot_hardware_config` id 21, task
definition 434, port 5599, `source_id` `demo`. What was actually exercised:

- **Pose-style view keys streamed into a running task**: `left_paw_x`, `right_paw_x`, and
  `object_detected` as a **dict event** — i.e. exactly the shape a vision or tracking system
  produces. This is the eye-tracking argument made concrete, not hypothetical.
- **Both staleness policies, on hardware**: after ~5 s of silence `left_paw_x` falls to 0.0
  (`return_default`) while `right_paw_x` holds at 0.8 (`hold_last`). Liveness is real behaviour,
  not just a code path.
- **A sustained 60 Hz soak for 2 minutes** (EXTLINK-20), plus a 5 Hz ramp crossing thresholds in
  both directions.
- **A required-device gate**: the Pi's ROUTER socket exists only while a run is active, and the
  config is `"required": true` with a 30 s window — so the run genuinely depends on the foreign
  device being there.

**The remaining honest limits. [C]**
1. The demonstrated role is **`router_bind`** (the foreign device connects to the Pi).
   **`sub_connect`** — subscribing to a foreign publisher — is still unit-tested only.
2. **Latency was deliberately not instrumented** — the driver notes *"No latency number is
   printed on purpose."* On a shared LAN segment it is reported as low, but that is an
   impression, not a measurement. **Say "it works at 60 Hz sustained"; do not quote a latency.**
3. The driver is an **untracked zip in the repo root**, not committed. Commit it.

### 9. Eighteen years old vs. still being built

*Plain:* Theirs has been around long enough that everything is worn smooth. Ours has sharp edges.

*Underneath:* MonkeyLogic: **174 dated releases**, current v2.4.0 (Mar 2026), one named
maintainer answering 2,025 forum posts personally, **281 papers** citing it in Europe PMC full
text, and ML1 scripts from 2008 that still run. It is also **bus-factor 1**, has no public
repository and no licence, and the legacy Asaad ecosystem is dead. **[V]** MICS: in-house,
phases still executing, several of its best pieces **built and deployed nowhere**, and no test
touches `api/main.py` (2,246 lines). **[C]**

> **The fair summary, and a good line to say out loud:** they optimised for *depth in one
> session*; we optimised for *breadth across sessions*. Their weaknesses are all at the edges of
> the session — before it, after it, next door to it. Ours are all **inside** it.

## 3. What MICS is

A database-backed system for **unattended, multi-day, multi-rig rodent behaviour in the home
cage**. Researchers define subjects, projects, experiments, protocols and task state machines in
a web UI; an orchestrator dispatches runs to Raspberry Pi rigs over ZMQ and streams every event
to Elasticsearch. **[V]**

The architectural bet, and the thing that is actually novel: **the task is data, not code.**
A task is a finite deterministic automaton authored in a GUI and stored as JSON in Postgres —
states, transitions, nested AND/OR conditions, action lists, variables, compute primitives,
trigger assignments — interpreted on the Pi by a ~520-line interpreter with closed vocabularies
and **no `eval`**, content-addressed by sha256. **[V]**

Around that: a colony database (28 Postgres tables including subjects, weights, surgeries,
projects, experiments, protocols, IACUC), hardware drivers as immutable hash-addressed DB rows
with a promotion lifecycle and a real on-rig import test, atomic device leases, a static
analyser with a **sound deadlock detector**, and hot reload of a running task's state machine
over the network. **[V]**

---

## 3a. How you extend each system — and why MICS's ceiling is higher than it looks

This is the part most comparisons get wrong, so be precise about it.

**Extending MonkeyLogic:** write a MATLAB **adapter** from `ext/ADAPTER_TEMPLATE.m` with
`init / analyze / draw / fini`. It joins the frame loop as a first-class citizen and can do
anything MATLAB can do. **[V]** Constraints: the constructor must take exactly one argument or
`mlplayer` replay breaks; `goodmonkey` inside an adapter must be `'nonblocking'`; and the
framework will not count for you — *"The scene framework analyzes input frame by frame, so it is
not possible to detect the 50th pulse as soon as it occurs."* **[V]** Also: *"NIMH ML does not
collect data automatically in the background. You should handle everything yourself."* **[V]**

**Extending MICS:** write a **hardware lib** in Python. The mechanism, verified end to end:

- A hardware object may run **its own thread** — already done in
  `hardware/external_hardware_runtime.py` (`threading.Thread`, three call sites). **[V]**
- It exposes state through `get_state()` (`hardware/external_hardware.py:157`,
  `hardware/__init__.py:152`). **[V]**
- It is registered **directly into the view**: `self.view.view[friendly_name] = hw`
  (`tasks/mics_task.py:1138`). The view is deliberately heterogeneous — the code says so at
  `:842` — holding Trackers *and* raw Hardware objects. **[V]**
- FDA transition conditions written in the GUI as `{"view": "friendly_name"}` resolve through
  `View.get_value()` → the object's `get_state()`
  (`core/View.py:43`, `tasks/mics_task.py:1136-1138`). **[V]**
- Drivers ship as **hash-addressed DB rows** with a promotion lifecycle and an on-rig import
  test, and the orchestrator sends `LOAD_HARDWARE_LIBS` before `START`. **[V]**

**So the extension story is: a hardware lib listens on its own thread, publishes state into the
view, and thereby drives conditions and transitions in a GUI-authored task.** That is an existing,
exercised pattern — not a hypothetical.

**Why this matters for the talk.** It means MICS's vocabulary ceiling is *soft*. Anything you can
express as "a thing with state that changes" becomes usable by non-programmers in the GUI the
moment one person writes the driver. A screen is not a special case: **it is a hardware lib that
happens to own a display.** The tree already contains an unused PsychoPy `Grating` on its own
thread — see the box below — so wrapping it as a hardware lib exposing `get_state()` is the
natural shape.

> **The unused grating.** `autopilot/autopilot/stim/visual/visuals.py` (218 L, inherited from
> Autopilot) contains a `Grating` class taking `angle, freq, rate, phase, mask, pos, size,
> duration`, running on **its own thread**, drawing through PsychoPy and **blocking on vblank**
> via `win.flip()`, with frame-interval logging for skipped-frame diagnostics. **[V]**
> It is completely dead: nothing imports it, the `VISUAL` config key it guards on is never set,
> **psychopy is not a declared dependency**, and the installer prompt for it is commented out
> (`autopilot/setup/scripts.py:104`). Its own docstring says *"still very alpha"*. **[V]**
> The remaining work is **install + wire + calibrate degrees-of-visual-angle + give it an FDA
> vocabulary + verify with a photodiode** — days-to-weeks, not architecture. Credit Autopilot.
>
> **One precise correction worth keeping:** frame-lock does **not** come from a GPIO trigger. A
> consumer LCD's refresh is not a wire you can read from a pin; it lives in the graphics driver,
> and you get it by blocking on vblank. GPIO triggers do the other two jobs — reading responses
> in, and exchanging sync pulses with an imaging system's frame clock.

**Say it this way, and it is both honest and strong:** *"Adding a new capability to MICS is a
driver written once by a programmer, after which everyone else uses it from a form. Adding one to
MonkeyLogic is a MATLAB class written once by a programmer, after which everyone else writes
MATLAB."*

**Do not overstate it.** Two honest limits: **[C]**
1. Nobody has yet written a hardware lib that owns a display, so the visual path is unproven
   end to end.
2. Extending the **vocabulary of the FDA itself** — new condition kinds, new action types — is a
   change across schema, editor and interpreter, not just a driver.

## 3b. Analog signals in MICS — how you'd answer that question

Yoav's lab relies on continuous analog signals, so expect this question. **The gap is real: MICS
has no analog input today** — verified, not one ADC or fixed-rate sampler among the 24 hardware
classes. **[C]** But the answer is *"here is how it plugs in"*, not *"we can't"*.

Keep the answer at three layers. That is enough to sound like you have thought about it, which
you have.

**1. The Pi needs an ADC — that's a board, not a rewrite.**
The Pi has no analog input, so you add one over I2C or SPI: a cheap ADS1115-class chip for
low-rate work, or a proper Pi DAQ HAT (e.g. an MCC 118-class board) for genuine multi-channel
kHz sampling. **[U — no board has been selected or tested]**

**The one design point worth naming out loud, because it is where a naive version fails:**
*who clocks the conversion?* If Python calls `read()` in a loop you inherit Python's jitter and
you have rebuilt the doorbell. You want either an ADC that converts on its own clock and raises a
data-ready line into a GPIO pin — in which case **pigpio timestamps each conversion in
microseconds and MICS's existing strength does the timing** — or a HAT with a hardware-clocked
buffered scan, which is the real analogue of how the NI board works.

**2. The driver is a hardware lib — the mechanism already exists (§3a).**
An ADC driver would run on its own thread, expose `get_state()`, and be registered into the view,
after which a researcher can use it in the GUI with no code. The design choice: `get_state()`
should **not** return the raw stream — the FDA needs scalars to compare. It returns derived
values (last value, above/below threshold, rolling mean over a window, "sustained for N ms"),
which is exactly what the existing detector and compute-primitive machinery already consumes. So
the analog signal becomes usable in a GUI-authored transition like any other view key.

**3. Storing the raw stream needs batching — and MICS has done this before.**
Naming the trap is the credible part: 1 kHz on one channel for one hour is 3.6M samples, larger
than the entire current event index. **One document per sample is fatal.** The answer is one
document per *block* of samples, each with its own timestamp.

MICS has actually run this: a `STREAM_BATCH` event type appears in the live index (July 2025),
carrying an `entries` array of individually timestamped samples at roughly 600–750 Hz on two
channels. **[V]** Be honest about its status — the task that produced it lived under
`terminal/plugins/`, had no backend or DB usage, and was **deleted in Phase 30**. So this is a
demonstrated pattern recoverable from git history, **not** something in the tree today. **[C]**

### Keeping one clock when you add an ADC — the part that makes the answer defensible

**Name the trap first, because it is the same trap MonkeyLogic fell into.** Every ADC HAT has its
own crystal. If you let it free-run and then *assume* "sample N happened at N/1000 s", you have
two clocks that drift apart — which is exactly what NIMH documents about itself: *"ML2 uses the
CPU clock to time events, while analog signals are digitized based on the NI board's clock…
which results in a missing/extra sample every few minutes"*, corrected offline by
`mlconcatenate`. **[V]** Adding a HAT naively means **inheriting the defect we would otherwise be
in a position to point at.**

MICS's whole timing story is that pigpio's DMA sampler timestamps GPIO edges in microseconds
against the Pi's own clock. The design goal is therefore: **every analog sample must carry a
timestamp on that same Pi clock.** Three ways to get there, in increasing order of elegance:

**(a) Timestamp the data-ready line — simplest, and probably the right first move.**
Let the ADC convert on its own oscillator, but wire its **DRDY / data-ready** pin into a GPIO
input. pigpio timestamps every DRDY edge in µs on the Pi clock. Now every sample has a Pi-clock
time, and the ADC's drift stops being an unknown offset — it shows up harmlessly as a
slowly-varying sample interval that you have *measured* rather than assumed.

> Worth noticing: this is **better than MonkeyLogic's position**, not merely equal to it. They
> assume the NI clock is regular and discover the discrepancy offline. Measuring each conversion
> against the same clock as every lick and TTL means there is nothing to reconcile afterwards.

Cost: one GPIO pin, and a DRDY edge rate equal to the sample rate. Use those edges **only** as
timestamps — never emit one event per edge, or you recreate the document explosion from §3b.

**(b) Let the Pi clock the conversions — one clock by construction.**
If the ADC accepts an external convert-start (many SPI parts do), generate that clock from the Pi
with a **pigpio waveform** — DMA-driven, hardware-timed, not Python. Then conversions happen at
instants the Pi *defined*, and there is genuinely only one clock; the ADC is a slave. This reuses
the mechanism MICS already relies on for hardware-timed output (`store_script`/`run_script`,
`gpio.py:627,684`). The constraint is that something must service the SPI read after each
conversion, which is why a part with a FIFO matters.

**(c) Feed the HAT the Pi's clock directly.** Some DAQ HATs take an external clock input. A
hardware-PWM pin can supply it. Then it is one physical oscillator and the question disappears.
Best if the board supports it. **[U — depends entirely on board choice]**

**At high rates, anchor rather than stamp every sample.** Above ~10 kHz, timestamping each
conversion is wasteful. Timestamp every *N*th sample — typically the FIFO half-full interrupt —
and interpolate between anchors. You are then continuously measuring the ADC's true rate against
the Pi clock, which is what serious DAQ integration does and what lets you *report* drift instead
of suffering it.

**Record the provenance.** Phase 31's clock work introduces `t_mono_ns`, `t_utc_ns` and
`ts_source` on events. An analog stream should carry `ts_source` naming which of the above
produced the timestamp (`drdy_edge`, `pi_clocked`, `interpolated`). That is what makes a
single-clock claim auditable rather than rhetorical. **[C]** — the backend has **zero awareness**
of those fields today.

**The prerequisite — assumed met by the talk, but say it plainly.** All of this rests on the Pi
tick being handled correctly. On the *old* client, ticks were converted with no wrap detection,
so GPIO timestamps jumped backwards 4294.97 s every 71.6 minutes. Phase 31 replaces that with a
wrap-safe monotonic clock that **refuses to run on the old client**, and this document assumes
Phase 31 is validated on hardware before the talk. **If it is, say so with the hardware
validation in hand; if it slips, do not claim single-clock analog** — the whole scheme depends on
it. Either way, mentioning the defect and its fix unprompted buys more credibility than any
capability claim.

### The HAT + GPIO sync trick — explained simply

*Plain:* The measuring machine has its own wristwatch, and it runs slightly fast. Instead of
arguing with its watch, you make it **tap you on the shoulder every time it takes a
measurement** — and *you* write down the time, on your watch. Now every measurement is on your
clock, and its wonky watch never matters.

That tap on the shoulder is a real wire. It is called the **data-ready pin**, it goes into a
GPIO pin, and pigpio stamps it in microseconds — the same clock that stamps every lick, every
beam break and every sync pulse.

**Why this is the clever bit, not just the workable bit:**

- You never *assume* "sample 3,000 happened at 3.000 seconds." You **know** when each one
  happened, because you wrote it down yourself.
- The ADC's drift stops being an error and becomes a **measurement** — the shoulder-taps just
  arrive a hair apart from what you expected, and you can see it.
- Nothing has to be reconciled afterwards. MonkeyLogic runs `mlconcatenate` offline precisely
  because it *didn't* do this.

*If you want to go further:* let the Pi tap the ADC instead — the Pi generates the "take a
measurement now" signal from a hardware timer, so conversions happen at moments the Pi chose.
Then there is only one clock by construction, and nothing to correct at all.

**One rule that must not be broken:** the shoulder-taps are for *timestamps only*. Never log one
event per tap — at 1 kHz that is 3.6 M documents an hour, more than the entire index. Stamp the
samples, batch them into blocks, ship one document per block.

---

### The multi-clock reality of a MonkeyLogic rig — verified, and useful

Worth knowing precisely, because it is easy to get wrong in the room.

**It is not Arduinos.** The Arduino in MonkeyLogic is **reward only** and optional — *"Arduino for
Reward"*, sending TTL to reward devices on digital pins D2–D12, over USB or BLE. It is not the
general hardware layer; NI DAQ is. **[V]** Do not claim otherwise.

**But the underlying instinct is right, and the real evidence is stronger.** From NIMH's own docs:

1. **Multiple NI boards are supported, and sometimes required.** *"NIMH ML can use multiple
   boards, but it does not require two NI boards unlike the original MonkeyLogic."* **[V]** And
   *"Two independent stimulations will require two DAQ boards."* **[V]** Each board carries its
   own sample clock.
2. **A whole class of inputs has no sample clock at all.** Verbatim: *"For those devices that do
   not have a sample clock (**NI digital input**, parallel port, touchscreen, USB joystick,
   TCP/IP eye tracker, keyboard, mouse), NIMH DAQ performs **millisecond-resolution data
   acquisition based on a software timer**."* **[V]**
3. **And the CPU/board split they document themselves** — CPU clock for events, NI clock for
   analog, *"a missing/extra sample every few minutes"*. **[V]**

**So a MonkeyLogic rig is genuinely a multi-timebase system:** the CPU clock, one or more NI board
clocks, a ~1 ms software timer for digital and peripheral inputs, the display's vblank, and an
Arduino's own clock if reward runs through one.

**Why this matters — the strongest timing point available to you. [V]**
The famous 1 kHz is the **analog** path. **Digital input is software-timed at 0.99 ± 0.22 ms.**
Most behavioural responses — lick contacts, beam breaks, levers, buttons — are digital. MICS
timestamps digital edges with pigpio's **DMA sampler in microseconds**, in hardware, independent
of Python, on **one** timebase shared by every pin on the rig.

> **The honest, careful phrasing:** *"For digital events — which is most of behaviour — we
> timestamp in hardware at microsecond resolution on a single clock. Their digital input is
> polled by a software timer at about a millisecond, with a fifth of a millisecond of jitter,
> and their rig carries several clocks that have to be reconciled afterwards."*
>
> **Then immediately concede the other half, or it is over-claiming:** *timestamping* is not
> *reacting*. Our measured end-to-end reaction is ~5 ms with a 46 ms tail. We know when things
> happened far better than we can act on them quickly.

**Also flag analog *out*, because a holography lab will need it.** MICS has no DAC either;
`gpio.py` has PWM but no analog output. For laser-intensity command you would add an I2C DAC or
filter a hardware PWM. What MICS *does* have today is hardware-timed digital pulse trains —
pulses are precompiled into a pigpio script and run on the daemon rather than in Python
(`gpio.py:627,684`) — which is how a great deal of optogenetics is actually gated. **[V]**

**The pattern generalises — say it once and it covers every "do you support X?" question.**
Two parts, always: **a TTL for time, a link for data.** A sync or strobe pulse into GPIO puts the
device on the Pi's clock at microsecond resolution; MICS-Link carries the payload in as a view
key a non-programmer can build a transition on (§8b). Analog, eye tracking, ephys and a camera
are all the same shape. That is what "MICS is an integration layer" means concretely.

**And a useful thing to say back to him:** a lot of a head-fixed two-photon rig is already
digital — the frame clock is a TTL, capacitive lick detection is a threshold, a running wheel is
a quadrature encoder. The genuinely analog needs are narrower: a photodiode for stimulus-onset
verification, a continuous laser-intensity command, and any true continuous sensor. Worth asking
which of those he actually needs before anyone buys a board.

**Honest bottom line for the talk:** *"Analog is the one capability MonkeyLogic has that we have
no version of at all. It is an ADC board plus a driver, and the driver pattern is one we use
already — but nobody has built it, so I'd be guessing at the numbers."* **[C]**

## 4. Capability matrix — with cost of change

The scale. Use it verbally; it is the spine of the talk.

| Level | Meaning |
|---|---|
| **0 — Built in** | Do it today, from the GUI or a config file, no code |
| **1 — Config** | One setting, one column, one demo run |
| **2 — Module** | Write code inside the framework. Days, not weeks. The framework survives |
| **3 — Buy** | Requires hardware, or an external program written and integrated |
| **4 — Architectural** | Weeks-to-months, or not feasible within the framework at all |

### 4a. The rig: stimulus, sensing, trials

| Capability | MonkeyLogic | MICS |
|---|---|---|
| Frame-accurate **visual** stimuli | **0** — the core competence **[V]** | **2–3** — a **complete, unused `Grating` implementation already exists** in the tree (`autopilot/autopilot/stim/visual/visuals.py`, 218 L): PsychoPy-backed, own thread, vsync-blocking `flip()`, frame-interval logging, and exactly the parameters needed (orientation, spatial freq, drift rate, phase, duration). It is **dead** — nothing imports it, `VISUAL` is never set in any config, psychopy is not a declared dependency, and the installer prompt for it is commented out. Cost is **wiring + stack install + calibration**, not architecture **[C]** |
| Auditory cue | **1** — ~40 ms XAudio2; <10 ms via WASAPI shared, manual driver swap **[V]** | **2** — pygame `buffer=1024`, WAV decoded from SD **inside the cue call** **[C]** |
| Lick / poke / beam detection | **0** — 16 AI @ 1 kHz, 10 buttons **[V]** | **0** — MPR121 capacitive licker, IR beams, GPIO, all as GUI trigger assignments **[V]** |
| **Continuous analog input** | **0** — 16 channels at **exactly 1 kHz, always** **[V]** | **3** — **none at all**; no ADC among the 24 hardware classes. Needs a board + a driver; driver pattern exists (§3b) **[C]** |
| Analog output (e.g. laser intensity) | **0** — 4 stimulation AO, sub-ms because preloaded **[V]** | **3** — no DAC; hardware-timed *digital* pulse trains exist via precompiled pigpio scripts **[C]** |
| Eye tracking | **0** — five vendors, calibration, drift correction, visual-angle coordinates **[V]** | **2–3 by integration, not by building one** — MICS does not aim to replace a tracker. Frame-strobe TTL into GPIO for µs timing + MICS-Link `sub_connect` for the gaze stream → an ordinary view key (§8b). Unproven on hardware **[C]** |
| Reward delivery | **0** — reward function, `RewardScheduler`, manual reward hotkey, ±10 ms trim **[V]** | **0** — valve driver, GUI action lists **[V]** |
| **Per-trial record** (outcome, RT, condition, stimulus id) | **0** — guaranteed for every task ever written, in a documented format **[V]** | **1** — trial boundaries, `hit`/`miss`/`false_alarm` and **930k `state_transition` events are all logged**; what is missing is the *guarantee* — four payload shapes, `trial`/`trail` split, no `correct_rejection`, and a trial number on only 8,673 of 2.92M docs. Fix is **standardising the event vocabulary**, not building a trials table **[C]** |
| Live per-trial plotting | **0** — control screen, performance bars, RT histogram, custom `userplot` **[V]** | **2** — **no charting library at all** in the SPA **[C]** |
| Timing verification harness | **0** — photodiode tuner + 10 benchmark tasks **[V]** | **2** — `tools/pulse_timing/` exists with named gates, but **all four committed fixtures are synthetic** **[C]** |

### 4b. Sync and closed loop

| Capability | MonkeyLogic | MICS |
|---|---|---|
| Strobed event codes to a neural system | **1** — assign Behavioral Codes + Strobe Bit; codes 9/18; T1=T2=125 µs **[V]** | **1** — `gpio.TTL` exists and precompiles its pulse into a stored script, but **every driver call in the live toolkit is commented out**; one config change plus one demo run **[C]** |
| Read a neural signal **in the loop** | **1** if it is an analog voltage (16 AI @ 1 kHz) or an **LSL inlet** (official since v2.2.22, Dec 2021); **2** for a vendor SDK **[V]** | **4 today** — phases 26 (Open Ephys device control, 13 plans) and 27 (firing rate over ZMQ) are **0% executed**. The MICS-Link `sub_connect` role is unit-tested but **has never run on hardware** **[C]** |
| Stimulation gated on behaviour, within the loop | **0** — `ClosedLoopStimulator` shipped as example 13 since **Nov 2017** **[V]** | **0** — GUI action lists + trigger assignments fire outputs on detector events **[V]** |
| Loop granularity | **one screen frame (16.7 ms @ 60 Hz)** in v2; ~1 ms sub-frame in v1 `eyejoytrack`, which cannot redraw **[V]** | no frames; busy-poll floor `time.sleep(0.0005)` ≈ 250 µs expected / 500 µs worst — **but the only measured round trip is ~5 ms** (§5) **[C]** |
| Two independent stimulation channels | **3** — "Two independent stimulations will require two DAQ boards" **[V]** | **0** — independent GPIO channels **[V]** |
| Two-photon **holographic** closed loop | **4** — not its job **[V]** | **4** — not its job **[V]** |

### 4c. The colony and the days before the rig — where MICS lives

| Capability | MonkeyLogic | MICS |
|---|---|---|
| Task authoring **without writing code** | **4** — there is no GUI task builder; Asaad et al. 2013 state it plainly: *"no drag-and-drop creation of behavioral tasks"* **[V]** | **0** — states, transitions, nested AND/OR conditions, action lists, variables, 13 compute primitives, trigger assignments, all in the GUI **[V]** (authoring a **new hardware primitive** still needs Python) |
| Change a parameter mid-session without code | **0** — `editable()` + the `V` key in the pause menu, typed widgets, persisted per subject, logged to `VariableChanges`. Genuinely good **[V]** | **0/1** — hot reload of a running FDA over ZMQ, but **no UI button, no safe point, no lock** **[C]** |
| Subject / colony database | **3–4** — none. Per-subject state is variables named `MLConfig_<subject>` inside one `*_cfg2.mat` next to the task. Forum searches for "database" return **zero** substantive hits **[V]** | **0** — 28 Postgres tables; subjects, projects, experiments, researchers, IACUC protocols **[V]** |
| **Body weight tracking** | **3** — not a concept **[V]** | **0** — `weight_measurements` table, `GET/POST /subjects/{id}/weights`, surfaced in the subject detail UI **[V]**. *Caveat:* date-granularity only, no baseline-% computation, no restriction-protocol enforcement, no alerting **[C]** |
| **Surgery record** | **3** — not a concept **[V]** | **0** — `subject_surgeries` table + endpoints **[V]** |
| Staged training with graduation criteria | **2** — write a MATLAB function; published precedent exists (Calapai-style: 19 training steps, auto-advance at ≥80% over 10 trials, regression at ≤20%) **[V]** | **0 for trial-count, 2 for anything else** — **only `NTrials` graduation actually fires**; any other type silently never fires. Adding Accuracy is ~50 lines plus a UI field **[C]** |
| Cross-session / cross-subject query layer | **3** — `behaviorsummary.m` takes exactly **one** filename; every lab writes its own MATLAB **[V]** | **0** — Postgres + Elasticsearch, ~2.92M event docs **[V]** |
| Remote monitoring | **2** for notifications (`alert_function.Slack.m`); real-time remote control **4** — maintainer, Jan 2026: *"you can run tasks on a desktop with two monitors but just with long cables"* **[V]** | **0** — web UI, live WebSocket pilot state **[V]** |
| Multiple rigs coordinated from one place | **4** — one instance per PC. Maintainer, Apr 2025: *"Unfortunately it does not work in that way, mostly because of the graphics."* N rigs = N Windows PCs **[V]** | **0** — orchestrator, atomic device leases, session spanning animals and rigs **[V]** (claim the entity, **never** the concurrency) |
| Unattended 24/7 operation | **4** — no autostart, no watchdog, no crash recovery. Forum search for "unattended": zero results **[V]** | **0** — the design centre **[V]**. *Caveat:* the systemd/unattended-boot work (Phase 31) is **built and running on no rig** **[C]** |
| Non-NI DAQ hardware | **4** — NI-DAQmx only; the 2019 "expanded hardware support is on our roadmap" is still unfulfilled in v2.4 **[V]** | **0** — arbitrary GPIO/I2C/SPI, drivers as versioned DB rows **[V]** |
| Linux / macOS | **4** — Windows x64 only, ARM unsupported **[V]** | **0** — Linux-native **[V]** |

### 4d. Provenance and data safety

| Capability | MonkeyLogic | MICS |
|---|---|---|
| Config provenance in the data | **0** — every file stores the complete `MLConfig`: `MLVersion`, `MLPath`, `Screen`, `System`, calibration matrices, every I/O assignment; optionally the **stimulus files themselves** (`SaveStimuli`) **[V]** | **0** for the task — FDA JSON is content-addressed by sha256 in the DB **[V]** |
| **Task source code** in the data | **3** — **not stored.** `embed_timingfile.m` compiles the timing script into a runtime function and never writes the text **[V]** | **0** — the state machine *is* the stored artefact **[V]** |
| Driver/firmware version bound to the run | — | **1** — **no version column today**; the orchestrator already holds the map at dispatch, so it is one column **[C]** |
| Backup of the behavioural record | **2** — a local file on the control PC; backup is your problem, but it is one file you can copy **[V]** | **1 — and currently broken.** The nightly ES snapshot targets the wrong host; the live ~2.92M-doc index has **no automated backup**, and the Pi keeps no local copy **[C]** |

---

## 5. Timing — the honest numbers, both sides

### MonkeyLogic (Hwang et al. 2019, Table 1, ML2 medians) **[V]**

| Measure | ML2 |
|---|---|
| Timestamp interval | 5.55 µs (resolution 0.29 µs, QueryPerformanceCounter) |
| **Event marker** | **0.18 ms** |
| Analog stimulation | −0.05 ms |
| Sound (on-board) | 39.92 ms (→ <10 ms with WASAPI shared, since v2.2) |
| Photodiode (visual) | −0.03 ms |
| Trial entry+exit | ~22 ms |
| Software timer | 0.99 ± 0.22 ms |

**But carry their caveats too — they are honest about them, so you should be:**

- NIMH itself: *"MonkeyLogic is not a true real-time system like DOS Cortex, it is fast enough
  for most behavioral work…"* **[V]**
- Their download page tells every user to measure their own rig. **[V]**
- A user measured event-code→photodiode at **50.87 ± 6.20 ms**, reduced to 18.2 ms only after
  re-cabling (forum 3,2144, Jan 2026). The published −0.03 ms is a *software* measurement at
  raster start; **panel lag is yours to characterise** — published LCD lag 2.10–24.78 ms. **[V]**
- **Split clocks:** *"ML2 uses the CPU clock to time events, while analog signals are digitized
  based on the NI board's clock… which results in a missing/extra sample every few minutes."*
  `mlconcatenate` corrects it offline. The maintainer's own advice is to feed everything into the
  neural acquisition system so all samples share one clock. **[V]**

### MICS — say this exactly, or not at all **[C]**

The only instrumented measurement in the archive is an **LED2 loopback**: an output pin's own
edges re-observed by pigpiod's DMA sampler.

| run | n | mean / median / σ / p95 / p99 / max (ms) |
|---|---|---|
| **401** | 1409 | **5.20 / 4.83 / 2.29 / 7.36 / 13.7 / 46.0** |
| 400 | 1459 | 5.19 / 4.94 / 1.83 / 7.19 / 10.1 / 37.8 |
| 386 | 2194 | 6.78 / 6.19 / 3.42 / 10.9 / 19.5 / 65.2 |
| 359 | 4001 | 11.37 / 9.56 / 10.17 / 19.6 / 59.7 / 164.1 |

**Four caveats that must travel with these numbers every time:**

1. All of it **predates the latency fixes** (commit `53f86ab`, 2026-04-29; the data is
   2026-04-13→16). **There is no post-fix measurement.**
2. The analysis notebook defaults to `RUN_ID = 359`, not 401, and stores no outputs — **the
   published figure is not reproducible from the repo**.
3. **Lick→water and valve latency have never been measured.** Poster captions reading
   "command → valve" and "lick → water" are both LED loopback.
4. The longest continuously-instrumented stretch in the entire archive is **5.7 minutes.**

### The clock defect — decide in advance whether you raise it

Source-certain, empirically unobserved, **fixed in code that runs on no rig**: the deployed
pigpio client converts ticks with **no wrap detection** and holds the offset by value, so every
GPIO timestamp jumps backwards 4294.97 s every 71.6 minutes — ~20×/day. The `mics_core`
replacement (`clock.py`, `tick_extender.py`, `clock_calibration.py`) fixes it and *refuses to run
on the old client*, but has **no measured numbers** and is deployed nowhere. **[C]**

Also: NTP is commented out on every deployed rig — so **do not claim a unified timeline across
rigs.** **[C]**

---

## 6. Closed loop — what each actually does

**MonkeyLogic. [V]**

- The **scene framework is the loop.** Every screen frame: `DAQ.peekfront()` →
  `ML_Tracker.acquire()` → `Adapter.analyze()` → `Adapter.draw()` → `mglrendergraphic()` →
  flip + eventmarker → `mglpresent()` (blocks on vblank). Loop period = one refresh.
- The paper states the trade-off exactly: *"the occurrence of the fixation may not be known until
  the next frame, although the time of the fixation can still be calculated online accurately."*
- **An official closed-loop example has shipped since Nov 2017** — `ClosedLoopStimulator.m`
  preloads the waveform into the NI AO buffer, arms it, and triggers/stops it per frame. Loop
  input is **eye position**, not neural data.
- **Two real neural-in-loop paths exist:** 16 General Input analog channels @ 1 kHz (a spike-rate
  DAC or threshold TTL), and the **LSL inlet**.
- The maintainer's *recommended* route for neural-driven adaptation is **between trials**, via
  `userloop` / `alert_function`: *"You can still do the calculation during the ITI… Some people
  are already doing the analysis that you mentioned with NIMH ML."* Budget: default ITI 2000 ms.
- Why preloading is mandatory, in his words: *"As a general purpose machine, a Windows PC cannot
  provide that kind of timing accuracy that stimulation output requires, which is why a dedicated
  device, like the analog output board, is necessary."*
- Optogenetics: official **Blackrock 64-channel LED driver** adapter; `BlackrockLED_shot` takes
  ~11 ms to switch all LEDs (sequential); durations must be multiples of 2 ms.

**MICS. [V] + [C]**

- Closed loop is expressed **in the state machine**: detector events → trigger assignments →
  action lists → outputs, authored in the GUI, no code, hot-reloadable over the network.
- The trigger queue was a **correctness fix to inherited code that dropped events** — a real
  contribution. **[V]**
- **[C]** There is **no exception boundary on the trigger worker**: one raise kills all input
  handling, silently.
- **[C]** The `trial_queue` is bounded at 50,000 and **drops on full with only a
  `logger.warning` and no counter** — a data-loss path on the graduation-critical channel.
- **[C]** No neural signal enters the loop today. Phases 26/27 are planned, 0% executed.

**Neither system does two-photon holographic closed loop.** That lives in the microscope
software. Do not imply otherwise in either direction. For context on where hard NHP loops
actually live: Zaaimi et al., *Nat Biomed Eng* 2022 ran theirs on a **dsPIC30F6012A at 30 MHz** —
not on a PC. **[V]**

---

## 7. Where the data lives

**MonkeyLogic [V]** — a **local file on the control PC**, opened once per session and appended
after every trial. Formats: **BHV2** (default; byte layout publicly documented for third-party
readers), BHVZ, HDF5, MAT. **Disk I/O happens between trials, not during them** — a real
architectural strength. Per-trial record includes `Trial, Block, Condition, TrialError,
ReactionTime, AbsoluteTrialStartTime, BehavioralCodes{CodeTimes,CodeNumbers}, AnalogData{Eye,
Joystick, Touch, PhotoDiode, General, Button, LSL}, ObjectStatusRecord, RewardRecord, UserVars,
VariableChanges, TaskObject, CycleRate`. No central database, no networked storage, no
versioning, no cross-session query layer.

Critical documented pitfall to quote if trial alignment comes up: *"the timestamps of those codes
are just the times that the codes were sent to the neural recording system and not the actual
start time and end time of a trial… To get precise trial intervals, use the
`AbsoluteTrialStartTime` field."*

**MICS [V] + [C]** — Postgres (28 tables) for structure; Elasticsearch `event_log_v2` for events,
~2.92M docs, **one document per event**; Redis for live pilot state.

- **[C]** The ES host is **hardcoded**; Redis keys have **no TTL on anything**.
- **[C]** Five live columns are absent from the ORM and reachable only by raw SQL — including
  `task_definitions.fda_json`, so **the entire task state machine is invisible to the ORM**.
- **[C]** No index template: 399 dynamically-inferred leaf fields, and both `trial_num` **and**
  `trail_num` exist.
- **[C]** `subject` in ES is a run key `bp_s{session}_r{run}`, **not an animal**.
- **[C]** Two timestamps per hardware doc: the envelope `timestamp` (queue-latency-inflated,
  +5.2–6.5 ms mean, max 144 ms) and `event_data.pi_timestamp` (the actual edge). **Using
  `timestamp` for lick latencies measures the queue.** `mics_core` fixes this with
  `t_mono_ns`/`t_utc_ns`/`ts_source` — which **the backend has zero awareness of**.

---

## 8. Ease of use — who can do what, without code

| Task | MonkeyLogic | MICS |
|---|---|---|
| Run a session | Anyone: load conditions file, type subject, hit RUN **[V]** | Anyone: web UI **[V]** |
| Change a parameter mid-session | Anyone: the `V` key in the pause menu, typed widgets **[V]** | Anyone: hot reload — but no button, no safe point **[C]** |
| Author a **new task** | **Write MATLAB.** The DMS example is ~60 lines; Asaad's 2008 DMS was 43 **[V]** | **GUI, no code** **[V]** |
| Add a training stage / graduation rule | Write a MATLAB function **[V]** | GUI — but only `NTrials` actually fires **[C]** |
| Add a new hardware primitive | Write a MATLAB adapter from `ADAPTER_TEMPLATE.m` **[V]** | Write Python, then promote the driver through the lifecycle **[V]** |

MonkeyLogic's GUI covers screen geometry and pixels-per-degree, all I/O channel assignment,
strobe spec, reward args, eye/joystick calibration, I/O test, latency test, photodiode tuner,
block/condition logic, ITI, error handling, `userplot`, filename templating, and per-subject
settings. **It is a very good configuration GUI. It is not a task builder.** That distinction is
your single strongest ergonomic point — make it precisely, and do not overstate it.

---

## 9. Cost per rig — be careful here

| Item | USD |
|---|---|
| NIMH MonkeyLogic | **$0** |
| Required MATLAB toolboxes | **$0** |
| MATLAB **academic** perpetual | **$550** (annual $330) |
| Campus TAH agreement | **$0 at point of use** |
| NI PCIe-6323 + SCB-68A + cable | ~$2,185 |
| Rig PC | ~$1,300–2,500 |
| Two displays | ~$260 |
| **One academic rig** | **≈ $4,300–4,900** |
| **Eight academic rigs** | **≈ $34,400–39,200** — of which MATLAB is **$4,400, or $0 under TAH** |

> **Do not run the "MATLAB licensing makes this expensive to scale" argument in front of an
> academic.** The numbers do not support it: the **NI DAQ front-end costs 4× the MATLAB seat**.
> It only bites under commercial licensing ($10,500/concurrent seat). **[V]**

Also note: Raspberry Pi 5 is no longer cheap either — 4 GB $110–130, 8 GB $175–200, 16 GB ~$305
as of Aug 2026, after three memory-driven price rises. **[V]**

---

## 10. Concede these before you are asked

Leading with these buys you the credibility to make the strong claims in §11.

1. **MICS records trials by convention, not by schema.** The events are there (boundaries,
   `hit`/`miss`/`false_alarm`, 930k state transitions) — but under inconsistent names and payload
   shapes, with a trial number on <0.3% of documents. A MonkeyLogic user gets a *guaranteed*
   per-trial record. Concede the guarantee, not the data.
2. **No *working* visual stimuli and no eye tracking** — though an unused, never-run PsychoPy
   `Grating` class does sit in the tree (§3a). Concede that it has never run; do not concede that
   it would be hard.
3. **Only `NTrials` graduation actually fires.** Autopilot — the foundation MICS was built on —
   had `NTrials` **and** `Accuracy`. We are behind our own foundation here.
4. **No live plotting; no charting library at all in the SPA.**
5. **Preflight does not block a bad run** — the code concedes it in its own comment.
6. **No post-fix timing measurement**, and the published timing figure is not reproducible from
   the repo.
7. **The live behavioural index has no automated backup.**
8. **Several of the best pieces are built and deployed nowhere** — the modern clock, the systemd
   unattended-boot units, MICS-Link `sub_connect`.
9. **No test touches `api/main.py`** (2,246 lines — session start, run mode and graduation paths
   are untested).

---

## 11. Claim cards

**SAFE to claim on stage [V]**

- Task specification is **data, not code** — ~520-line interpreter, closed vocabularies, no
  `eval`, sha256 content-addressed.
- **GUI authoring** of states, transitions, nested AND/OR conditions, action lists, variables,
  13 compute primitives and trigger assignments **without writing or deploying code**
  (add: "authoring a new hardware primitive still needs Python").
- **Hot reload** of a running task's FDA over the network (add: "no UI button, no safe point").
- The trigger queue as a **correctness fix** to inherited code that dropped events.
- Static analysis with a **sound deadlock detector** — name the dated incident: task def 186,
  run 541, a `rand` drawn on entry with the only exit requiring `>= 0.5`; the task parked forever
  while the pilot kept logging licks. Say **"surfaces to the operator"**, never "blocks".
- Driver source as **immutable hash-addressed DB rows** with a promotion lifecycle and a real
  on-rig import test.
- The **session as a first-class entity** spanning animals and rigs (claim the entity, never the
  concurrency).
- **UI off the data path.** **Atomic device leases.**
- **Body weight and surgery records** as first-class subject data.
- MICS-Link demonstrated on hardware — **claim generality, not novelty** (Autopilot shipped a
  networked closed loop in 2022).

**NOT safe — do not say these**

- "MICS has a guaranteed per-trial schema." (It has the events; it lacks the guarantee.)
- "Preflight blocks a bad run."
- "Driver version is recorded against the run."
- "Adaptive progression." / "A unified timeline across rigs."
- "Microsecond timestamping is ours" (credit the forked pigpio).
- "All hardware events are logged automatically" (one `@auto_log` repo-wide; `i2c.py` imports
  `log_action` and applies it **zero** times).
- **Any** Open Ephys / closed-loop-neural capability in the present tense.
- A **latency figure** for MICS-Link — it was deliberately never instrumented. (The *capability* is safe: a foreign driver streaming into a live state machine at 60 Hz sustained is demonstrated Mac→Pi. Only the number is missing.)
- "We subscribe to foreign publishers" in the present tense — `router_bind` is demonstrated; `sub_connect` is unit-tested only.
- "Wireless BLE optogenetics" (zero BlueBerry/`bleak` code in either tree).
- "Low-latency audio." / "Data is backed up."
- Any number from the LED2 notebook as reproducible.

---

## 11b. Where MICS could credibly top MonkeyLogic — and where it could not

Assembled from the challenges raised while writing this document, each of which held up under
checking. This is the forward-looking half of the talk, and it is stronger than the ledger
suggested when I started.

### Cheap steps with real leverage

| Step | Effort | What it wins |
|---|---|---|
| **Accuracy / two-sided graduation** | ~50 lines + a UI field | They require a MATLAB function for this. We would have it in a GUI. Also unblocks the most common real training rule |
| **Standardise the trial + outcome event vocabulary** | one convention, one migration | Converts data we *already collect* into a **guarantee**. One spelling, one payload shape, a trial number stamped on every document |
| **Land the Phase 31 clock on a rig** | in flight | Prerequisite for everything below, and turns µs digital timestamping from a claim into a measured fact |
| **ADC HAT + data-ready GPIO sync** | a board + a hardware lib | Analog input with **per-sample Pi-clock timestamps** — arguably a *better* answer than their two-clock reconciliation, because drift is measured rather than corrected offline |
| **Wire the existing PsychoPy `Grating`** | install + calibrate + FDA vocabulary | Visual stimuli that a **non-programmer can author in a GUI** — something MonkeyLogic explicitly does not offer |
| **Driver version bound to the run** | one column | Provenance they do not have at all: their data file stores config but **never the task source** |
| **Live per-trial plotting** | one module | Closes a real gap; they have a good live control screen |
| **Commit the MICS-Link reference driver + instrument the round trip** | it already exists and runs; add a timestamp echo | The integration loop is already demonstrated Mac→Pi at 60 Hz sustained. All that is missing is a **number** and a tracked file — the cheapest credibility win on the list |
| **Back up the live index** | config | Not a feature — an existing hole |

### The three places MICS would genuinely be ahead

1. **Digital timestamping on one clock.** Their digital input is a **~1 ms software timer with
   ±0.22 ms jitter**, across a rig carrying several clocks. Pigpio's DMA sampler stamps every pin
   in microseconds on one timebase. Most of behaviour is digital. **[V]**
2. **Authoring without code.** Their GUI configures; it does not build tasks — *"no drag-and-drop
   creation of behavioral tasks"*. Ours builds them, and the task is stored, hashable, statically
   analysable and hot-reloadable. **[V]**
3. **Everything above the session.** Colony, weights, surgeries, protocols, many rigs, unattended
   operation, and a live queryable database instead of one file per session on one PC. **[V]**

### Where MICS would not lead — say these too

1. **Eye tracking — as a *built-in*.** Five vendor integrations, two calibration methods, drift
   correction and a visual-angle coordinate system are two decades of work, and MICS should not
   try to reproduce them. **But this belongs in the "integrate" column, not the "lose" column**
   (§8b): a camera or commercial tracker emitting a frame-strobe TTL gives µs-accurate timing on
   the Pi clock, and MICS-Link `sub_connect` carries the gaze stream into the view as an ordinary
   key a non-programmer can gate a transition on. That is not far-fetched — it is the same
   two-part pattern as the ADC (**TTL for time, link for data**), it has already been run
   Mac→Pi with paw-coordinate keys at 60 Hz (§8b), and MonkeyLogic's own TCP/IP trackers are
   software-timed at ~1 ms. What stays out of reach near-term is *gaze-contingent
   display* at frame latency, which needs the display path and proven loop latency too.
2. **The bundled behavioural vocabulary.** `WaitThenHold`, `RandomDotMotion`, RF mappers,
   `CurveTracer` and 50+ adapters represent two decades of accumulated primate psychophysics.
3. **Maturity and reach.** 174 releases, 281 papers, one maintainer who answers every forum post,
   and 2008 scripts that still run.
4. **Their own measurement harness.** A photodiode tuner and 10 benchmark tasks. Until MICS has
   real fixtures instead of synthetic ones, this is a fair hit and should be conceded.

> **The line that ties it together:** *"They are ahead where two decades of one problem domain
> compound — the eye, the visual primitives, the installed base. We are ahead where the
> architecture is younger and cleaner — one clock across every pin, tasks as data instead of
> code, and everything above the single session. Most of the gap on our side is a short list of
> known, costed work; most of the gap on theirs is time."*

## 12. Questions to be ready for — and how to answer

*Written against the Livneh case (Appendix A) because that is the room, but questions 8–16 are
the general ones any MonkeyLogic user will ask.*

*Ordered by how likely he is to ask them.*

**1. "My science is about need states. How would this help me?"**
The question to want — but answer it narrowly, because he trains in MonkeyLogic too (Appendix A). Do
**not** offer to train his mice: his training task is the same visual discrimination, on the same
screen. What MICS offers is the **record-keeping and protocol layer** his rig has no concept of:
per-animal weight curves against a baseline (his criterion is literally 80% / 85% of body
weight), surgery records, projects, experiments, IACUC linkage, and cross-session querying across
animals and rigs. And one capability that is precisely his: a **two-sided accuracy graduation
rule**. Open by asking how his lab currently tracks restriction — if the answer is a spreadsheet,
you have the conversation. Do not assume it is.

**2. "Can it sync to my two-photon frame clock?"**
Honest: **`gpio.TTL` exists and precompiles its pulse into a stored script, but every driver call
in the live toolkit is commented out.** So: one config change plus one demo run — cost level 1,
not zero, and not demonstrated. Their side, for contrast: strobed codes are one config change and
completely routine. Do not bluff this one; he will ask for the jitter number and there isn't one.

**3. "What's your lick-to-reward latency?"**
**It has never been measured.** The only instrumented number is a 5.20 ms mean / 46 ms max LED
loopback, taken before the latency fixes and never repeated. Say exactly that. Then say what you
would measure and how — that answer lands better than a number he cannot check.

**3b. "Do you handle analog signals?"** *(Expect this — his lab depends on them.)*
Straight answer: **no, not today — it is the one MonkeyLogic capability we have no version of.**
Then show you have thought about it, in three beats: the Pi needs an **ADC board**; the driver is
an ordinary MICS hardware lib that publishes derived values (threshold crossed, rolling mean)
into the view so it becomes usable in the GUI; and the raw stream must be **batched** into blocks
of timestamped samples, because one document per sample at 1 kHz would dwarf the entire existing
index. Note that MICS has run a batched-stream path before (`STREAM_BATCH`, July 2025) though
that code was later deleted. Then turn it around: ask which signals he genuinely needs analog
for — the frame clock, capacitive licking and a running wheel are all digital. See §3b.

**4. "Can I do closed-loop photostimulation based on activity?"**
Not in MICS today, and not really in MonkeyLogic either — his holography loop lives in the
microscope software. What MonkeyLogic *can* do is take a spike-rate analog voltage or an LSL
stream into a 1 kHz input and act on it within a frame. MICS cannot: phases 26/27 are planned,
zero executed. **Present tense: no.**

**5. "How is a trial defined and recorded in your system?"** *(His figures are all hit / miss /
false-alarm / correct-rejection — and MICS does log the first three as events.)*
The trial boundary is declared **inside the state machine** as an increment action, authored in
the GUI. The durable state is a counter, `run_progress.current_trial`. **There is no trials
table** — no outcome, no RT, no stimulus id. Concede fully, then note the cost: one module plus a
schema decision.

**6. "I have visual cues. Can you present them?"**
Not today — but the answer is less bleak than it looks (§3a). A PsychoPy-backed `Grating` class
with the right parameters already exists in the tree, vsync-blocked on its own thread; it has
simply never been installed, wired or calibrated. Say "not today, and here is exactly what it
would take", not "we can't". His rig still keeps MonkeyLogic — but for **ergonomic and
sync-maturity** reasons, not because the pixels are impossible.

**7. "Where does the data go, and can I get it into MATLAB/Python aligned to my imaging frames?"**
Postgres + Elasticsearch, one document per event, ~2.92M docs. Queryable across sessions and
animals — which `behaviorsummary.m` cannot do at all. But warn him about the trap **before** he
hits it: there are two timestamps per hardware document, and the envelope one is inflated by
queue latency (+5.2–6.5 ms mean, 144 ms max). He must use `event_data.pi_timestamp`.

**8. "Can a student change a parameter mid-session without touching code?"**
Both yes. Theirs is better engineered: `editable()` + the `V` key in the pause menu, typed widgets, persisted
per subject, logged to `VariableChanges`. Ours hot-reloads the whole state machine over the
network — more powerful, less safe: no button, no safe point, no lock. Say both halves.

**9. "How many animals per computer?"**
Theirs: exactly one, and it's structural — the maintainer's own words, *"mostly because of the
graphics"*. N rigs = N Windows PCs, each with two monitors. Ours: one orchestrator, many rigs,
atomic device leases, a web UI. **This is the strongest structural contrast in the talk.** State
their number from the maintainer's quote, not from an assumption.

**10. "Can I train animals automatically, overnight, in the home cage?"**
Theirs: no — no autostart, no watchdog, no crash recovery, zero forum results for "unattended";
the published home-cage MonkeyLogic deployment ran ~90 min/day with staff moving animals. Ours:
that is the design centre. But concede that the unattended-boot work is **built and running on no
rig yet**, and that only `NTrials` graduation actually fires.

**11. "What does the experimenter see live?"**
Theirs, and it is good: subject-screen replica with eye trace, event timeline, performance bars,
live frame interval and drawing time, custom `userplot`. Ours: live pilot state over WebSocket,
and **no plots at all**. Concede.

**12. "Is your timing verifiable?"**
Fair hit, and the fairest one he can land. They ship a photodiode tuner and 10 benchmark tasks.
We have a harness with named gates in `tools/pulse_timing/` — and **all four committed fixtures
are synthetic**. The right answer is to name what you'd measure on hardware and by when.

**13. "What happens when something overruns or crashes?"**
Theirs: skipped frames, counted, optionally event-coded, `DiscardSkippedFrames` configurable,
drawing time on screen. Ours: unbounded event queues with print-only drop counters, a 50,000-cap
trial queue that drops with a warning and no counter, no exception boundary on the trigger
worker, and **no output fail-safe — pins keep their last state after the pilot dies**, so a
solenoid can stay open. Concede all of it. He runs water-restricted animals; he will care.

**14. "Who maintains it, and what happens when the student leaves?"**
The fairest reciprocal question you will get, and it cuts both ways. Theirs: one NIMH staff
scientist, no public repo, no licence, distributed as a zip — but 174 releases, quarterly, and
2008 scripts still run. Ours: answer honestly about the bus factor, and point at what reduces it
— tasks as data rather than code, drivers as hash-addressed rows, a static analyser.

**15. "What's the migration cost from my existing task code?"**
High, and mostly not technical — it is institutional knowledge. Don't pretend otherwise. The
migration worth proposing is not his task; it is his **colony records and his training pipeline**.

**16. "Why not Bpod / pyControl / Autopilot?"**
Be ready, and be accurate: MICS is built on Autopilot's foundation, which shipped a networked
closed loop in 2022 — **claim generality, not novelty**. pyControl reports running **24 setups in
parallel** from one computer. The MICS differentiators to name are the GUI-authored state
machine as stored data, the colony/protocol database, and the driver-provenance lifecycle.

---

## 13. Two attack lines that do NOT survive checking

Both are tempting. Neither is true. Using either in front of this audience will cost you the room.

1. **"MATLAB licensing makes MonkeyLogic expensive to scale."** False in an academic setting —
   $550/seat, often $0 under a campus TAH agreement, and the NI board costs 4× more.
2. **"MonkeyLogic can't do closed loop."** False. It has shipped a working closed-loop
   stimulation example since **November 2017**.

The defensible structural claims are: **one animal per PC**, **one screen frame of loop
granularity**, **no data layer above the file**, and **no unattended-operation story** — each
backed by a direct quote from the maintainer or from the source.

---

## 14. Still unverified — do not put these on a slide

- Research for this document was **cut off mid-execution by a session token limit.** The
  MonkeyLogic write-up is solid on what it read directly (the v2.4.0 distribution source,
  `changes.txt`, the docs tree, the forum, both papers) and **thin on third-party and comparative
  claims**.
- **No documented example of spike-rate readback into the MonkeyLogic frame loop.** LSL and
  analog input make it architecturally possible; no published instance was found.
- **No TDT, Ripple or xippmex integration evidence** — zero forum hits for all three.
- ~~Rodent use / which software the Livneh lab uses~~ — **RESOLVED, both verified** from his own
  *Cell Rep* 2024 STAR Methods and a second mouse paper in *Nat Neurosci* 2024. See §1.
- Achievable end-to-end closed-loop latency (neural → LSL → MATLAB frame → stimulation) is not
  published by anyone.
- **MICS-Link round-trip latency is unmeasured on our side too** — deliberately so. The loop is
  demonstrated Mac→Pi at 60 Hz sustained; the number does not exist. Instrumenting it is one of
  the cheapest wins on the §11b list.
- Size of the MonkeyLogic installed base — citation counts (132/149) are the only proxy.
- A systematic sweep of comparison tables in the Bpod / Autopilot / Bonsai / EthoPy / BControl
  methods papers was **not completed**.

---

## 15. Not for the talk — but urgent

The nightly Elasticsearch snapshot targets `host.docker.internal:9200`, which is the machine
holding only a stub index and an old restore. **The live ~2.92M-document index has no automated
backup, and the Pi keeps no local copy** (the HDF5 path was removed). That is a single
un-backed-up copy of the lab's entire behavioural record.

---

# Appendix A — Case study: the Livneh lab (one application, not the spine)

Livneh lab (Weizmann, Dept. of Brain Sciences) — brain–body communication and interoception.

**The rodent question is settled: yes, MonkeyLogic is used for head-fixed mice, and he is one of
those users. [V]**

Livneh et al., *Cell Rep* 2024, "Stereotyped goal-directed manifold dynamics in the insular
cortex" (PMC11063631), STAR Methods, verbatim:

> *"Behavioral training was performed using MonkeyLogic and MonkeyLogic2
> (https://monkeylogic.nimh.nih.gov/)."*

Its Key Resources Table lists **MonkeyLogic** (Asaad & Eskandar 2008) **and MonkeyLogic2**
(NIMH), alongside MATLAB R2015b/2019a and **Scanbox** (Neurolabware). Organism:
**Mouse, C57BL/6J**. So he uses MonkeyLogic for **training**, not only for the imaging session.

He is not alone. Independent confirmation, also mice: *"The behavioral protocol was implemented
using MATLAB (version R2018a) and the MATLAB toolbox MonkeyLogic (version 2, build 206) to
control a data acquisition device (National Instruments, PCIe-6323) with a break-out panel
(BNC-2090A). Time-stamped behavioral event codes were sent to the photometry recording system."*
— *Nat Neurosci* 2024, striatal dopamine in mice (PMC11001585). **[V]**

**The nuance worth knowing.** The NIMH forum has **zero** posts matching "mice", "rodent" or
"rat" — verified against a positive control on the same search ("monkey" → 22 threads, "eyelink"
→ 12, "macaque" and "marmoset" → 1 each); "mouse" returns only *computer*-mouse threads. Europe
PMC full text, by contrast, returns **281 papers** citing MonkeyLogic and **49** that also
mention mice. So rodent labs use it quietly and never post. Absence of forum evidence was not
absence of use — a good caution to carry into the talk.

### His actual paradigm — all [V], from the 2024 Methods

| | |
|---|---|
| Preparation | Head-fixed mice, headpost + **2 mm microprism** over mid-insular cortex |
| Need state | Water-restricted to **~80% of pre-restriction body weight**, or food-restricted to **~85% of free-feeding weight** |
| Cue | **Square-wave drifting gratings on an LCD screen** — 2 Hz, **0.04 cycles/degree**, full-field, **80% contrast**; food cue 0°, aversive 270°, neutral 135° |
| Trial | Grating for **2 s**, then a **2 s** response window. Only the **first lick** triggers delivery |
| Lickspout | **Two adjacent tubes**, so the tongue contacts both on every lick |
| Outcomes | Water (~2–3 µL) · Ensure (~5 µL, 0.0075 cal) · 1 M NaCl · quinine |
| **Training criterion** | **>80% correct on the appetitive cue (usually 90–95%) AND <50% licking on aversive (usually 20–30%)** |
| Imaging | Neurolabware resonant-scanning 2P, tiltable scanhead, **31 frames/s**, 1154×512 px, 20× 0.45 NA air, 540×360 µm FOV, 90–200 µm deep |
| Session shape | 30-min runs; depth re-adjusted between runs for z-drift <7 µm. Satiation: consecutive runs until the mouse voluntarily stops, then a "quenched" run. Hunger: ~180 trials, then ad-lib Ensure for 45–75 min |

### What this changes about the pitch — read this carefully

The tempting frame is: *"MonkeyLogic runs his rig; MICS runs the weeks before the rig."*

**For Livneh specifically, that frame is half wrong, and he will catch it.** His *training* is the
same visual discrimination task, on the same screen, in MonkeyLogic. There is no non-visual
pre-rig phase for MICS to take over. So do not offer to train his mice.

What survives, and it is still real:

- **The restriction schedule is the independent variable, and it is bookkeeping.** 80% and 85% of
  body weight, tracked per animal, per day, against a baseline. MICS has `weight_measurements`
  and `subject_surgeries` as first-class tables with endpoints and UI. His lab almost certainly
  does this in a spreadsheet.
- **His graduation rule is exactly the one MICS cannot express.** ">80% on go-cues AND <50% on
  no-go cues" is a two-sided accuracy criterion. MICS supports **only** `NTrials` — verified:
  `api/main.py:1750` is a bare `if prog.graduation_type == "NTrials":` with **no else branch**,
  so any other type silently never graduates. This is the single most concrete, cheapest, most
  targeted gap in the whole comparison (~50 lines + a UI field), and it is *his* criterion.
- **Cross-session, cross-animal querying.** `behaviorsummary.m` takes exactly one filename.
- **Colony, project, experiment, researcher and IACUC records.** MonkeyLogic has no concept of
  any of them.

Pitch the **record-keeping and protocol layer**, not the training layer. And ask him what he
actually does about restriction bookkeeping — do not assume.
