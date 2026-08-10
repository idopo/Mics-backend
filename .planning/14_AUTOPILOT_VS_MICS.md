# 14 — Autopilot vs. MICS: what was inherited, what was replaced, and what to claim

**Written 2026-08-06**, from the live server: `~/pi-mirror/autopilot/` (vendored **auto-pi-lot
0.4.4**, `autopilot/__init__.py:2`; `setup.py:69,74,77` — Jonny Saunders, MPL-2.0) and
`~/mics-backend` (branch `claude`, HEAD `f6aabd5`). MICS is evaluated at roadmap completion
(phases 18, 19, 26, 27, 28 landed), but **only capabilities that have concrete implementation or
an approved plan are counted** — nothing here rests on aspiration.

---

## 1. The ledger: which files are whose

`auto_pi_lot.egg-info/SOURCES.txt` is the upstream packaging manifest, so it separates inherited
from added code without guesswork.

**Inherited and still load-bearing (unmodified or lightly modified):**
`core/pilot.py` · `core/loggers.py` · `networking/{station,node,message}.py` · `hardware/__init__.py` ·
`hardware/gpio.py` · `hardware/{i2c,cameras,usb}.py` · `prefs.py` · `utils/{registry,plugins,common,
requires,types,hydration,invoker,decorators,wiki}.py` · `tasks/task.py` · `exceptions.py` · `setup/`

**Inherited and dead in the MICS path** — present in the release, imported by nothing MICS runs:
`core/terminal.py` (997 lines) · `core/gui.py` (3,350) · `core/plots.py` (1,147) ·
`core/subject.py` (1,361) · `viz/` · `transform/` (9 modules) · most of `stim/` ·
`tasks/{nafc,gonogo,free_water,children,graduation,test}.py`. **≈6,855 lines of upstream
Terminal-side code carried but unused.**

**MICS-added inside the vendored package:**
`core/View.py` · `utils/{Tracker,Mics_Tracker,Event,Events,FiniteDeterministicAutomaton,
logging_utils,log_value,PeriodicTimer}.py` · `networking/Event_Dispatcher.py` ·
`data_handlers/{Data_Handler,ElasticSearchDataHandler}.py` ·
`tasks/{mics_task,fda_vocabulary,learning_cage,mics_cage_task,RecordingBox}.py` ·
`hardware/{mixer,timer,unreal}.py` · plus `gpio.Solenoid_mics`, `gpio.TTL`, `gpio.Pulse20Hz`.

**MICS edits *into* upstream files** — this is what makes the fork unmergeable:
`hardware/__init__.py` gained `Sensor`/`Effector` ABCs, `HardwareState`, and an `event_dispatcher`
constructor arg (`:87-100,132,150`); `gpio.py` gained `@auto_log` on `Digital_Out` (`:324`);
`tasks/task.py` gained the `Event_Dispatcher`, the `View`, `run_id`, `session_progress_index`,
`subjects`, and View registration inside `init_hardware` (`:132-138,203`); `core/pilot.py` gained
hardware-library shipping, FDA hot-reload, the pigpio clock block, and **had its data path commented
out**.

**MICS outside the package** — no Autopilot analogue exists: `api/` (~8,100 lines, **27 Postgres
tables**), `orchestrator/` (1,709 lines), `web_ui/` (84 TS/TSX modules).

---

## 1b. Measured: is `core/pilot.py` still Autopilot's process?

**Yes — extended in place, not rewritten.** Established 2026-08-06 by three-way diff, so this is
measurement rather than inference.

**The baselines.** `~/pi-mirror` retains the full project history (185 commits). Autopilot entered
on **2022-04-05** as a **git submodule** pinned to upstream commit `8ee5459` (`4b28bd7`, Lior Segev,
*"added dev branch of autopilot to my repo"*), then was flattened into the tree the same day
(`30c8d3c`, *"add autopilot dev branch"*). Official **`auto-pi-lot 0.4.4`** was downloaded from PyPI
for comparison.

**Step 1 — what was imported was vanilla upstream.**

| File | official 0.4.4 → at-import (2022-04-05) |
|---|---|
| `core/pilot.py` | **4 lines** differ |
| `core/terminal.py` | **4 lines** differ |
| `tasks/task.py`, `hardware/__init__.py`, `hardware/gpio.py`, `networking/station.py`, `networking/node.py` | **0 lines** differ |

So the starting point was Autopilot 0.4.4 itself, not a pre-modified variant.

**Step 2 — what MICS did to it over four years.**

| File | at-import | today | diff | original lines surviving |
|---|---|---|---|---|
| `networking/node.py` | 643 | 643 | **+0 / −0** | **100 %** — byte-identical |
| `networking/station.py` | 1,328 | 1,362 | +37 / −13 | ~99 % |
| `hardware/__init__.py` | 249 | 289 | +32 / −2 | ~99 % |
| `hardware/gpio.py` | 1,438 | 1,716 | +294 / −72 | ~95 % |
| `tasks/task.py` | 333 | 459 | +141 / −29 | ~91 % |
| `core/pilot.py` | 823 | 1,283 | **+415 / −29** | **~96 %** |
| `core/terminal.py` | 997 | 1,027 | +38 / −8 | ~99 % (**and dead**) |

`pilot.py` grew ~50 %, but only **29 of 823 original lines** were removed. The additions are
**adjacent**, not invasive: `_write_hardware_libs()` and `l_load_hardware_libs()` (library
shipping), `l_update_fda()` (hot reload), `extract_task_metadata()` / `serialize_hardware_dict()` /
`_serialize_flags()` / `_serialize_semantic_hardware()` / `discover_tasks_metadata()` (HANDSHAKE
introspection), `enable_ntp_and_wait()` / `disable_ntp()`, and the `pigpio.pi(sync_ticks=True)`
block. Two dictionary entries were added to `self.listens`. Autopilot's process model — start,
handshake, `l_start` → `run_task` in a thread, `while True: next(self.task.stages)()`, `l_stop` —
is untouched.

**The 29 removed lines are exactly the data path**, and they are the leftovers worth cleaning:
`h5f, table, row = self.open_file()`, `self.node.send('T','DATA',data)`, the `TrialData` row-fill
and `table.flush()` block, and `self.stage_block.wait()`. Most survive as commented-out code rather
than deletions (~44 commented-code lines in `pilot.py`, 29 in `task.py`, 53 in `gpio.py`).

**Answer: it is Autopilot's process, wearing Autopilot's name legitimately.** Nothing here supports
"we rewrote it and kept the terminology."

**To reproduce these numbers** (the baselines were built in a temp dir, not committed — rebuild them
in a scratch directory, never in this repo or on the server):

```bash
# 1. official upstream 0.4.4 from PyPI
curl -sL -o ap.tgz https://files.pythonhosted.org/packages/90/00/\
1708fca42c8e6b380f2bee6a570acd87c534ed5521af14b5bcd875d4ac48/auto-pi-lot-0.4.4.tar.gz
tar xzf ap.tgz            # → auto-pi-lot-0.4.4/autopilot/...

# 2. the vendored tree as first imported (vanilla), and as it is today
ssh mics-server 'cd ~/pi-mirror && git show 30c8d3c:autopilot/autopilot/core/pilot.py' > atimport_pilot.py
ssh mics-server 'cat ~/pi-mirror/autopilot/autopilot/core/pilot.py'                     > current_pilot.py

# 3. three-way diff
diff -u auto-pi-lot-0.4.4/autopilot/core/pilot.py atimport_pilot.py   # ≈0 → import was vanilla
diff -u atimport_pilot.py current_pilot.py                            # what MICS changed
```

Key commits in `~/pi-mirror`: `4b28bd7` (submodule pinned to upstream `8ee5459`, 2022-04-05) and
`30c8d3c` (flattened into the tree the same day). The orchestrator's vendored copy is at
`~/mics-backend/orchestrator/orchestrator/networking/`.

## 1c. Is the orchestrator's "Pilot_Station format" real, or naming inertia?

**Real, and structural.** The evidence is on both ends of the wire:

- **Pi side:** `networking/node.py` is **byte-identical to upstream 0.4.4** (+0/−0). The pilot
  instantiates upstream `Pilot_Station()` and `Net_Node(...)` (`pilot.py:229,235`). MICS did not
  reimplement the client.
- **Orchestrator side:** MICS vendored Autopilot's networking into
  `orchestrator/orchestrator/networking/`. `message.py` there is **byte-identical to upstream
  0.4.4** (269 lines, +0/−0) — the *same serialization class* runs on both ends. `station.py` was
  cut from 1,328 lines to 255: upstream's base `Station` retained, its `Terminal_Station` and
  `Pilot_Station` subclasses dropped. `node.py` cut from 643 to 176.

So `RouterGateway.py:16`'s self-description — *"speaks legacy Pilot_Station format"* — is an
accurate statement of a live dependency, not a stale comment. The frame layout, the `Message`
envelope, the key-dispatch model and the CONFIRM/resend semantics are Autopilot's, because the Pi
genuinely runs Autopilot's networking code and the orchestrator genuinely runs Autopilot's
`Message`.

What *is* MICS's own is the **peer**: upstream's `Terminal_Station` was discarded and `RouterGateway`
written in its place, because the Terminal it served does not exist here. That is the honest
summary — **MICS replaced Autopilot's server, not Autopilot's protocol.** The word "orchestrator"
is a new name for a component Autopilot has no equivalent of; the *format* it speaks is inherited
fact.

---

## 2. Feature-by-feature

Ratings are **de facto** — what the code does today, not what either project intends.

### 2.1 Process and transport

| | Autopilot 0.4.4 | MICS (roadmap complete) |
|---|---|---|
| **Pi process** | `core/pilot.py`, ZMQ `Pilot_Station` + `Net_Node`, Tornado IOLoop | **The same file, same classes.** Launched by `run_pilot.sh` → `python3 autopilot/autopilot/core/pilot.py -f prefs.json` |
| **Wire protocol** | `Message` envelope, ROUTER/DEALER, key-dispatched handlers | **Unchanged.** MICS's `RouterGateway.py:16` documents itself as speaking *"legacy Pilot_Station format"*, and MICS vendored `networking/{message,node,station}.py` into the orchestrator to do it |
| **Message vocabulary** | START, STOP, PARAM, CALIBRATE_PORT, CALIBRATE_RESULT, BANDWIDTH, STREAM_VIDEO | Same 8, **+2**: `UPDATE_FDA`, `LOAD_HARDWARE_LIBS` (`pilot.py:215-225`) |

**Strength (both):** a proven, low-ceremony ZMQ layer; MICS got multi-station networking for free.
**Weakness (both):** best-effort delivery with a confirm/resend loop and no ordering guarantee
across keys; MICS inherited this and had to build its *own* FIFO egress queue in Phase 18 rather
than fix it upstream. **Weakness (MICS):** it is now committed to a protocol whose upstream
implementation it has forked away from.

**Verdict: pure inheritance.** MICS did not re-architect the transport; it re-implemented the peer
on the other end of it.

### 2.2 Task logic authoring — *the largest divergence*

| | Autopilot | MICS |
|---|---|---|
| **Unit of a task** | One Python class per task (`Nafc`, `GoNoGo`) | One interpreter class, `mics_task` (1,487 lines), executing JSON |
| **Structure** | `STAGE_NAMES` + stage methods; `self.stages = itertools.cycle(stage_list)` — a trial is one pass through the cycle | `self.stages` is a `FiniteDeterministicAutomaton` object: named states, guarded transitions, entry-action lists |
| **Who writes it** | A programmer, in Python, on the Pi | A researcher, in a browser canvas; JSON validated backend-side, dispatched to the Pi |
| **Parameters** | `PARAMS` odict rendered as a form by the Terminal GUI | DB-stored params/flags/variables; typed operand pickers built from library AST metadata |
| **Conditions** | Python inside the stage method | Arbitrarily nested AND/OR `condition_tree` (`mics_task.py:1105`), plus recursive in-state `if` actions (`:646-694`) |
| **Computation** | Arbitrary Python — full expressive freedom | `type:"compute"` ops from **versioned, user-authored compute libraries**; every call logged as op + result |
| **Changing a task** | Edit file on the Pi, restart the pilot | Edit in browser; `UPDATE_FDA` hot-reloads into the running task (`pilot.py:646`) |
| **Determinism check** | none | `check_determinism()` rejects conflicting transitions at build time (`FiniteDeterministicAutomaton.py:37`) |

**Autopilot strength:** unbounded expressiveness. Anything Python can do, a stage method can do —
and for an unusual paradigm that is a real advantage MICS does not fully match.
**Autopilot weakness:** the task is opaque to every other layer. Nothing can validate it, diff it,
version it, or render it; changing it means SSH and a restart; and the person who can change the
task is the person who can write Python.
**MICS strength:** the task becomes *data* — inspectable, validatable, versioned, renderable,
hot-swappable, and editable by the experimentalist who owns the science.
**MICS weakness:** expressiveness is now bounded by the vocabulary. The escape hatches (inline
Python in a state, an `expr` operand) were **deliberately rejected** in Phase 23 because they
forfeit versioning and logging. So a genuinely novel computation requires authoring a compute
library — cheaper than a platform release, but not as cheap as typing a line of Python.

**Verdict: replacement, not extension.** MICS keeps the *contract* (`self.stages` yields callables;
`stage_block`) and inverts the *model*.

### 2.3 Hardware modules and their adaptation

| | Autopilot | MICS |
|---|---|---|
| **Base classes** | `Hardware`, `GPIO`, `Digital_Out`, `Digital_In`, `PWM`, `LED_RGB`, `Solenoid` (`gpio.py`, 1,716 lines) | **The same classes**, plus `Solenoid_mics`, `TTL`, `Pulse20Hz`, `mixer.AUDIO`, `timer`, `unreal` |
| **Where driver code lives** | On the Pi: package dir or `PLUGINDIR`, imported by `utils/plugins.py` | **In Postgres** (`hardware_libs` / `hardware_lib_versions`), AST-validated at upload, shipped per run to `~/apps/hardware_overrides` and injected into `sys.path` (`pilot.py:36-46`) |
| **Versioning** | Filesystem + whatever git the lab keeps | `unvalidated → beta → stable` with `stable_at` / `stable_reason` (`'user'` \| `'protocol_run'`) / `stable_pilot` (`models.py:647-653`); pinned per toolkit; resolution pin → toolkit default → latest stable → preflight failure |
| **Pin/param config** | Hand-edited `prefs.json` on each Pi | `pilot_hardware_config` in the DB, sent per run; **the backend is authoritative** and fully replaces a group (`mics_task.py:194-201`) |
| **How a task names a device** | `HARDWARE` dict keyed by group/id | Same dict — **populated from the DB**, plus `SEMANTIC_HARDWARE` friendly names introspected off the class at HANDSHAKE (`pilot.py:328,427`) |
| **Per-channel addressing** | none | Detector-derived view keys (`LICKER0…3`) from declared `first_channel` + count, resolved per pilot at preflight (Phase 25) |
| **Reading a device in task logic** | `self.hardware['GROUP']['ID'].read()` | `view.get_value(name)` — one call for GPIO, I2C, variables, compute results and (Phase 18) external software |

**Autopilot strength:** dead simple. A driver is a file; a plugin is a file in a directory; there
is nothing to deploy.
**Autopilot weakness:** *nothing knows what is on any Pi.* Drift between rigs is invisible until an
experiment behaves differently, and `prefs.json` on eight Pis is eight independent sources of
truth. There is no record of which driver version produced which data.
**MICS strength:** the rig's configuration and its driver code are both first-class, versioned,
queryable records, and a run carries the version that produced it. This is the single most
defensible reproducibility claim MICS has.
**MICS weakness:** a heavier loop for a one-line driver fix (upload → version → promote → dispatch),
and a new failure mode Autopilot does not have — a lib that imports on the dev box but not on the
Pi's Python 3.7.3, which is exactly why `compute_lib_import_failed` exists as a reserved preflight
kind.

**Verdict: inherited base, inverted provisioning.** The class hierarchy is Autopilot's; where the
code lives and who is allowed to change it is entirely MICS.

### 2.4 Terminal vs. Portal

| | Autopilot Terminal | MICS Portal |
|---|---|---|
| **Form** | PySide desktop GUI on one machine (`terminal.py` 997 + `gui.py` 3,350 + `plots.py` 1,147) | Browser SPA over three services: `api`, `orchestrator`, `web_ui` (84 TS/TSX modules) |
| **Status in MICS** | **imported by nothing** — dead code in the release | — |
| **Task authoring** | none — renders a `PARAMS` form for a task someone wrote in Python | Visual FDA canvas: states, transitions, nested conditions, typed operand pickers, layout persisted with the task (`ui_layout`) |
| **Pre-run validation** | none | Preflight, **9 issue kinds** (`toolkit_dispatch.py:153-163`), 11+ after Phases 18/26 — including *a transition reading a variable nothing writes* and *a state whose every exit is blocked*, i.e. a provable deadlock |
| **Live monitoring** | per-subject trial plots, live, in the GUI | pilot grid (connected / state / active run / elapsed), device-health badge (Phase 19), Kibana for everything else |
| **Multi-user** | one desktop, one operator | web, concurrent; **but no user identity on the pilot grid** — `PilotLive` is `{connected, state, active_run, updated_at}` |
| **Resource arbitration** | none | Device lease keyed on normalized host; hard-blocks a second run and names the holder (Phase 18) |

**Autopilot strength:** live per-trial psychometric plotting, in the loop, with zero setup — genuinely
useful and something MICS **lost**. Kibana is better across sessions and worse at "is this animal
doing the task right now".
**Autopilot weakness:** single-operator desktop app; no validation; no scheduling; no notion of a
cohort, project or IACUC protocol.
**MICS strength:** the Portal validates before it dispatches. That is the difference between
discovering a mis-specified task at 3 a.m. and being blocked at 5 p.m. Plus a real relational
model — 27 tables covering subjects, projects, experiments, surgeries, weights, researchers,
protocols, toolkits, libraries and per-pilot config.
**MICS weakness:** three services, Docker, Postgres, Redis and Elasticsearch to stand up. Autopilot
needs a Pi and a laptop. For a lab wanting one rig, MICS's operational cost is real and should be
stated honestly in the paper.

**Verdict: total replacement.** Not one line of the Terminal survives in the MICS path.

### 2.5 Data handling

| | Autopilot | MICS |
|---|---|---|
| **Primary store** | Per-subject **HDF5** (`core/subject.py`, 1,361 lines) — protocol, history, weights, graduation state, trial tables | **Postgres** (27 tables) for structure + **Elasticsearch** for the event stream |
| **What the Pi writes** | trial rows → `node.send('T','DATA',data)` → Terminal → HDF5; plus a local `local.h5` mirror | **Both are commented out** (`pilot.py:1175` `open_file`, `:1207` `node.send('T','DATA')`) |
| **Granularity** | one row per trial, schema declared as `TrialData(tables.IsDescription)` | one document per **event** — every hardware call, tracker set, state transition, system report |
| **Who decides what's recorded** | the task author, by declaring `TrialData` columns | nobody — `@log_action`/`@auto_log` instrument the driver methods themselves (`logging_utils.py:14,24`) |
| **Context per record** | subject + protocol step, implicit in file location | `pilot, subject, session, run_id, task_type, timestamp, continuous, session_progress_index, subjects` (`Event_Dispatcher.py:38-48`) |
| **Trial structure** | given, by construction | **derived post hoc** from the event stream |

**Autopilot strength:** a trial table is what analysis actually wants, and you get it for free,
self-describing, in one portable file per subject.
**Autopilot weakness:** you only ever get what the author thought to declare. A question nobody
anticipated is unanswerable, and the raw hardware history is gone.
**MICS strength:** nothing is discarded. Every hardware actuation and state change is on the
record with full run context, so trials can be re-cut years later under a different definition —
and `session_progress_index` stamps the protocol step onto every single event.
**MICS weakness, and it is a real one:** there is **no trial table**. Every analysis begins by
reconstructing trials from events, which is why this repo needs `context/06_TRIAL_STRUCTURE.md`
and a `trial-structure` skill at all. The corpus also carries two incompatible event vocabularies
and a schema that changed under it. Autopilot's model has neither problem.

**Verdict: total replacement, with a genuine trade-off** — completeness bought at the cost of
derivability.

### 2.6 Progression across sessions — **where MICS regressed**

| | Autopilot | MICS |
|---|---|---|
| **Model** | protocol = list of task steps with graduation criteria, stored per subject | `protocol_templates` + `protocol_step_templates` + per-subject `run_progress` in Postgres |
| **Criteria implemented** | **`NTrials`** *and* **`Accuracy`** — rolling window, `threshold=0.75, window=500` (`tasks/graduation.py:40-95`) | **`NTrials` only** — `api/main.py:1747` evaluates no other value |
| **Per-subject state** | in the subject's HDF5 file | `run_progress.current_step`, plus `new`/`resume`/`restart` run modes |

This is the one dimension where the fork is **behind its own foundation**, and the cause is
structural rather than an oversight: Autopilot's `Accuracy.update(row)` consumes trial rows, and
MICS disabled the trial-row path. Performance-based graduation cannot be re-added without either a
trial abstraction or a compute-op that scores outcomes into a variable the backend can read.

**Consequence for the manuscript:** the draft's "progression can depend on performance" and
Table 1's "adaptive progression" are not merely unbuilt — they describe something **the system MICS
is built on already had and MICS traded away**. If a reviewer knows Autopilot, this is the second
thing they will notice after the attribution. See `13_MANUSCRIPT_CLAIMS_AUDIT.md` §3.2.

### 2.7 External systems and closed loop

| | Autopilot | MICS (post Phases 18/26/27) |
|---|---|---|
| **Real-time on-Pi processing** | `transform/` — 9 composable modules (geometry, image, logical, selection, timeseries, units) | **unused**; MICS computes on external machines and ingests results |
| **External software → task** | no defined path | MICS-Link: `router_bind` / `sub_connect` / `none` roles, per-library `@decoder`, signals as ordinary view keys |
| **Acquisition control** | none | OE driven IDLE→RECORD, run-derived save folder, labelled markers, **recording path written back to the DB**, backend safety net on Pi crash |
| **Neural data → task** | none | windowed firing rate per declared unit as a view key |
| **Cross-clock alignment** | none | TTL, plus `(ts_pi_recv, oe_sample)` pairs logged for post-hoc drift fitting |
| **Device health** | none | `<source_id>.alive`, split from signal staleness, surfaced on the pilot card |

**Autopilot strength:** `transform/` is a real capability MICS has no equivalent for — closed-loop
processing *on the Pi*, in the same process, with no network hop.
**MICS strength:** everything above the wire. But note the architectural cost: MICS's answer to
"process a video frame" is *another computer*, which adds a network hop and a clock to reconcile
where Autopilot would have done it in-process.

### 2.8 Timing and stimulus delivery

| | Autopilot | MICS |
|---|---|---|
| **Audio** | `stim/sound/` — **jack** or **pyo** server, designed for low-latency sample-accurate playback | `hardware/mixer.py` — **pygame `mixer`, `buffer=1024`** |
| **Visual** | `stim/visual/` psychopy-backed | not used |
| **Clock** | pigpio ticks | same: `pigpio.pi(sync_ticks=True)` + `synchronize()` (`pilot.py:1139,1145`) — within-station; the NTP calls exist and are **commented out** (`:1138,1148`) |

**This is a de facto regression.** MICS swapped a purpose-built low-latency audio stack for pygame.
For a 150 ms tone cue that is fine; for auditory work needing sub-millisecond onset precision it is
not, and the paper should not imply otherwise. If reviewers ask about cue-onset jitter, this is the
answer they will get — worth measuring in Phase 28's session while the instrumentation is out.

---

## 3. Scorecard

| Dimension | Autopilot | MICS | Who wins, de facto |
|---|---|---|---|
| Pi process / ZMQ transport | ✅ solid | inherited | **tie — same code** |
| Hardware driver base classes | ✅ mature | inherited + extended | **tie — same code** |
| Hardware provisioning & versioning | ❌ files + hand-edited prefs | ✅ DB, versioned, promoted, per-run | **MICS, decisively** |
| Task authoring expressiveness | ✅ arbitrary Python | ◐ bounded vocabulary | **Autopilot** |
| Task authoring accessibility | ❌ programmer + SSH + restart | ✅ browser, hot-reload | **MICS, decisively** |
| Pre-run validation | ❌ none | ✅ 9→11+ preflight kinds incl. deadlock detection | **MICS, decisively** |
| Live per-trial visualization | ✅ built-in plots | ◐ Kibana + pilot grid | **Autopilot** |
| Cross-session / cohort management | ❌ HDF5 per subject | ✅ 27-table relational model | **MICS, decisively** |
| Trial-level data model | ✅ declared trial tables | ❌ none — derived post hoc | **Autopilot** |
| Completeness of record | ❌ only declared columns | ✅ every event, full run context | **MICS** |
| Progression criteria | ✅ NTrials **+ Accuracy** | ❌ NTrials only | **Autopilot** |
| On-Pi real-time processing | ✅ `transform/` | ❌ none | **Autopilot** |
| External instrument integration | ❌ none | ✅ MICS-Link + OE control | **MICS, decisively** |
| Multi-rig arbitration | ❌ none | ✅ device lease, preflight block | **MICS** |
| Audio timing precision | ✅ jack/pyo | ❌ pygame mixer | **Autopilot** |
| Deployment cost | ✅ Pi + laptop | ❌ Docker/Postgres/Redis/ES | **Autopilot** |
| Provenance of the code that ran | ❌ none | ✅ versioned libs bound to runs | **MICS, decisively** |

Roughly: **MICS wins the definition, validation, provenance and integration layers; Autopilot wins
the execution-primitive and analysis-convenience layers.** That split is not accidental — it is
precisely the boundary MICS chose to build across.

---

## 4. The verdict: "foundation" or "different system"?

**Both claims are true of different layers, and the layer boundary is the Pi process boundary.**

**Below it, "foundation" is not a framing — it is a dependency.** The process that runs the
experiment *is* `autopilot/core/pilot.py`. The transport is `Pilot_Station`/`Net_Node`/`Message`,
so completely that MICS's own orchestrator documents itself as speaking *"legacy Pilot_Station
format"* and vendors Autopilot's networking modules to do it. `mics_task` subclasses Autopilot's
`Task` and honours its `self.stages` / `stage_block` contract. The hardware hierarchy is
Autopilot's, with MICS's loggers decorating it in place. The prefs system still resolves hardware
at `init_hardware` — MICS overwrites its contents per run rather than replacing the mechanism.
Delete Autopilot and nothing runs.

**Above it, "different system" is fair.** The Terminal, the subject store, the data model, the task
model and the provisioning model are all replaced, not extended — ~6,855 lines of upstream
Terminal-side code sit unused in the release while 27 Postgres tables, ~8,100 lines of API, an
orchestrator and 84 frontend modules do that job differently. Autopilot's data path is not
refactored in MICS; it is *commented out*.

So: **MICS is a different system built on Autopilot's Pi runtime.** Not a fork of Autopilot, and
not an independent system that happens to resemble it.

### Why the paper should claim "built on", not "effectively independent"

1. **It is checkable in thirty seconds.** The release ships `auto_pi_lot`'s `LICENSE`,
   `CITATION.cff` and `setup.py`. A reviewer who opens it finds Autopilot, and any framing that
   implied otherwise is then read as concealment rather than simplification.
2. **MPL-2.0 is file-level copyleft, and MICS modified upstream files** — `pilot.py`, `task.py`,
   `hardware/__init__.py`, `gpio.py`. Those files must keep their notices and ship under MPL. This
   is a legal fact, not a positioning choice, and it will be visible at code release regardless of
   what the manuscript says.
3. **It costs nothing scientifically, and it sharpens the contribution.** "We built a
   definition, validation and provenance layer on a proven distributed Pi runtime" locates the
   novelty exactly where the paper argues it is (§5 of `13_MANUSCRIPT_CLAIMS_AUDIT.md`). Claiming
   the transport layer too would invite scrutiny of the part MICS didn't build.
4. **The divergence argument cuts the other way too.** "MICS is Autopilot with a web UI" would be
   equally wrong — the task model, data model and provisioning model are all inverted. The precise
   phrase is *"built on Autopilot's Pi runtime"*, not *"built on Autopilot"*.

### Concretely, for the manuscript

- **Results/Methods**, one sentence: MICS-Core extends the Autopilot framework (Saunders & Wehr),
  which supplies the Raspberry Pi process, its ZMQ transport and its hardware driver base classes;
  MICS replaces Autopilot's Terminal, subject-file data model and Python-authored task model with a
  database-backed definition, validation and provenance layer and an event-stream record.
- **Cite the Autopilot paper**, and carry the MPL-2.0 notice in the code release.
- **Table 1:** keep the Autopilot row, and mark the relationship in the caption rather than
  presenting it as an arms-length comparator. Comparing MICS to Autopilot without disclosure reads
  as comparing a system to its own dependency.
- **Do not claim adaptive/performance-based progression** (§2.6 above) — Autopilot has it and MICS
  does not, so this is the worst possible cell in which to claim an advantage.
- **Do not imply sample-accurate audio** (§2.8) unless the pygame path is measured.

### One risk worth recording (continued below in §5–§7)

The vendored tree is a **hand-modified copy of 0.4.4 with MICS phase commits landing directly on
it** (`git log` in `~/pi-mirror/autopilot` shows `feat(16-03)`, `feat(15-01)` on the vendored
source). There is no upstream-merge path and no contribution flowing back. That is a maintenance
liability, and it also means any statement about contributing to Autopilot would not currently be
true.

---

## 5. Terminal vs. Portal — why these are not the same "central coordination"

§2.4 compared them as feature lists. This section is the architectural argument, because the
manuscript currently treats "central coordination" as one concept that MICS inherited and
re-skinned. It is not. **Autopilot's Terminal and MICS's Portal coordinate different things, own
different responsibilities, and fail differently.**

Everything below marked *(source)* is read from `auto-pi-lot 0.4.4`. The lab's operational
experience is marked *(lab)* and should be framed as motivation, never as a measured claim about
Autopilot — see the tone warning at the end.

### 5.1 The structural difference in one sentence

**In Autopilot, coordination is a property of a desktop GUI process. In MICS, coordination is a
property of a database and a set of services; the browser is only a view onto it.**

*(source)* `class Terminal(QtWidgets.QMainWindow)` (`core/terminal.py:72`). The coordinating object
**is a Qt main window**. Everything below follows from that one fact.

### 5.2 Who owns the data

| | Terminal | Portal |
|---|---|---|
| Who persists behavioural data | **the GUI process** — `Terminal.l_data()` calls `self.subjects[name].save_data(value)` (`terminal.py:576-594`); the window object holds the open HDF5 handles | **nobody in the UI** — the Pi streams events to the orchestrator, which indexes to Elasticsearch. The browser reads; it never writes data |
| Path if the UI is absent | the Pi's `local.h5` mirror only | irrelevant — the UI was never in the data path |
| Consequence of UI loss | in-flight trial data has no writer | data continues to land |

*(source)* This is the load-bearing difference. In Autopilot the Pi *sends data to the GUI to be
saved*; a window and a data store are the same process. In MICS the data path does not pass through
any user interface at all. **The Portal is not a more reliable Terminal — it is not in the same
position in the system.**

### 5.3 Who owns progression

*(source)* `Terminal.l_data()` also runs the entire progression loop, inside the GUI's message
handler: check `did_graduate` → send `STOP` → `stop_run()` → `graduate()` → `prepare_run()` →
**`time.sleep(5)`** → send `START`. The sleep carries its own FIXME: *"Don't hardcode wait time,
wait until we get confirmation that the running task has fully unloaded."*

So in Autopilot: a blocking sleep in a GUI event handler sits between one task ending and the next
beginning, and if the window dies inside that window, the subject is left mid-transition with the
Terminal's in-memory notion of its step gone.

In MICS: progression is rows — `run_progress.current_step`, `session_runs`, explicit
`new`/`resume`/`restart` modes. The step is a durable fact, not a variable in a running GUI. Any
service, or a later session, can read where a subject got to.

### 5.4 What survives a restart

| | Terminal | Portal |
|---|---|---|
| Persistent coordination state | `pilot_db.json` — pilot → subject/IP mapping only (`terminal.py:411-432`) | Postgres: pilots, sessions, runs, run_progress, toolkits, per-pilot hardware config, lib versions, leases |
| Notion of "what is running right now" | in the GUI's memory | Redis + `/pilots/live`, read by anything |
| Liveness detection | **none** — `Terminal.l_ping()` is an empty method whose docstring says *"Reminder to implement heartbeating… Currently unused, as Terminal Net_Node stability hasn't been a problem"* | orchestrator heartbeat + `_redis_touch`; device liveness split from staleness (Phase 18); mid-run health badge (Phase 19) |
| Restarting the UI mid-session | reconstructs from `pilot_db.json`; run state is gone | reconnects to state it never owned |

*(source)* That `l_ping` docstring is worth quoting internally: Autopilot's design explicitly
assumes Terminal stability rather than detecting its absence. That assumption is reasonable for
session-based experiments with an operator present. It is the wrong assumption for unattended
home-cage training running for weeks — which is exactly MICS's use case, and the honest,
non-adversarial way to explain why the architecture had to change.

*(lab)* In practice the Terminal crashed, data was lost with it, and a run could not be restarted
cleanly without overwriting or power-cycling the Pi.

### 5.5 Functional differences

| Function | Terminal | Portal |
|---|---|---|
| Define a task | ✗ — renders a `PARAMS` form for a task someone wrote in Python | ✓ visual Blueprint canvas: states, transitions, nested conditions, typed operand pickers |
| Edit a running task | ✗ — edit on the Pi, restart the pilot | ✓ `UPDATE_FDA` hot-reload into the live task |
| Validate before dispatch | ✗ — `toggle_start()` sends; a "coherence checking ritual" is a TODO | ✓ preflight, 9→11+ issue kinds, including provable-deadlock detection |
| Manage hardware config | ✗ — hand-edit `prefs.json` on each Pi | ✓ DB-held, versioned, backend-authoritative, shipped per run |
| Live per-trial plots | ✓ built in (`plots.py`) | ✗ — **Terminal wins here**; Kibana is better across sessions, worse at "is this animal doing the task right now" |
| Cohort / project / colony model | ✗ — one HDF5 per subject | ✓ 27 tables incl. projects, experiments, researchers, surgeries, weights, IACUC |
| Arbitrate a shared instrument | ✗ | ✓ device lease, hard-blocks at preflight and names the holder |

### 5.6 Operational differences

| | Terminal | Portal |
|---|---|---|
| Where you must be | at the machine running the GUI (`DISPLAY=:0`; `run_terminal.sh` sets it) | any browser on the network |
| Concurrent users | one window, one operator | many, concurrently |
| Restart cost | restarting the UI *is* restarting coordination and the data writer | restarting `web_ui` touches nothing that matters; services restart independently |
| Deployment | a Pi and a laptop | Docker: Postgres, Redis, Elasticsearch, three services — **Autopilot wins on setup cost, and the paper should concede this** |
| Upgrades | replace the app | services version independently; task definitions and libs version *inside* the system |

### 5.7 Scalability differences

- **Stations.** Both scale to many Pis — this is Autopilot's design and MICS inherits it (`15` C11).
  Not a differentiator.
- **Operators.** Terminal: one. Portal: many, and remotely. This *is* a differentiator, and is what
  a shared facility actually needs.
- **Data.** Terminal: N subjects → N HDF5 files, and cross-subject questions are a scripting job.
  Portal: one relational store + one event index, so cohort-level questions are queries. **This is
  the scalability claim worth making** — it scales in *analysis*, not just in rig count.
- **Instruments.** Terminal: no concept of a resource shared between rigs. Portal: leases.
- **The failure surface as N grows.** Terminal: one process is the single point of failure for all
  N stations' data and progression. Portal: each Pi is independent; losing a service loses
  monitoring, not execution and not data.

### 5.8 How to phrase this in the paper — a warning

Do **not** write that Autopilot's Terminal is unreliable. Three reasons: it invites a defensive
reviewer, it is an unmeasured claim, and MICS depends on Autopilot's code so the criticism partly
lands on MICS. Also note that the Terminal's design assumption — an operator present, session-based
experiments — is *stated in its own source* and is perfectly reasonable for what it was built for.

Write the **architecture**, and let the consequence be obvious:

> In Autopilot, the coordinating process is also the process that persists behavioural data and
> advances subjects through their protocol. MICS separates these: data is written by a service the
> user interface is not part of, and a subject's position in its trajectory is a database record
> rather than in-memory state. The interface can therefore be closed, restarted or replaced without
> affecting either data capture or experimental progression — a property that matters when
> experiments run unattended for weeks.

That sentence is defensible, non-adversarial, checkable, and says everything the lab's experience
taught, without making a reliability claim about anyone's software.

---

## 6. Rewrite instructions — the hardware-abstraction section

The current text ("MICS represents devices as modules that expose abstract task-level commands and
translate them into the communication code required to control the device") describes **Autopilot**
as accurately as it describes MICS. Autopilot has a `Hardware` base class, a `HARDWARE` dict of
logical group/id names, pin binding in `prefs.json`, and a plugin registry. Abstraction is not the
novelty. **Management of the abstraction is.**

### 6.1 Vocabulary — words to use, words to drop

**Drop these** (they describe the inherited layer, and a reviewer will recognise it):
*abstracts devices · interchangeable functional units · hardware-agnostic task logic ·
device-specific communication protocols · translates into low-level commands ·
modular abstraction of device control*

**Use these** (they describe what MICS added):

| Instead of | Write |
|---|---|
| "abstracts hardware" | "**governs** hardware definitions" |
| "modules" | "**versioned device libraries**" |
| "configuration" | "**per-station binding, held centrally and applied per run**" |
| "flexible" | "**validated**", "**reproducible**", "**auditable**" |
| "can be modified" | "**changes are versioned and attributable**" |
| "supports different setups" | "**a station's capabilities are declared, checked, and recorded**" |

Load-bearing nouns for this section: **library, version, promotion, binding, declaration,
preflight, provenance, authority.** Load-bearing verbs: **declare, validate, resolve, ship, pin,
promote, record, block.**

### 6.2 Tone

- **Concrete over architectural.** Not "a modular abstraction layer decouples logic from
  implementation" but "the driver code that ran this session is a specific stored version, and the
  system will not start a session whose hardware it cannot resolve."
- **Lead with the failure it prevents.** Every claim in this section is best introduced by the
  problem: eight rigs drifting apart; a driver edited on one Pi and not another; nobody knowing
  which version produced last month's data.
- **Own the trade-off in one clause.** The loop is heavier than editing a file on the Pi. Saying so
  earns the rest.
- **Never imply Autopilot lacks abstraction.** It has it. MICS adds the layer that makes it
  manageable at scale.

### 6.3 The specific features to name

Name these, in roughly this order — each is checkable in the code and none is claimed by Autopilot:

1. **A device driver is a stored, versioned artifact**, not a file on a Pi
   (`hardware_libs` / `hardware_lib_versions`).
2. **Versions have a promotion state** — `unvalidated → beta → stable` — and a driver can reach
   `stable` **by having carried a real protocol run** (`stable_reason = 'protocol_run'`). This is
   the sentence to build the section around: *validation status is earned by use, and recorded.*
3. **Code is checked before it is accepted** — AST validation at upload; the declared interface
   (methods, arguments, types) is extracted and becomes what the task editor offers.
4. **Per-station binding is centrally held and backend-authoritative** — `pilot_hardware_config`,
   sent at run start, fully replacing what is on the Pi, so a station cannot silently drift.
5. **A task refers to devices by role, not by wiring** — semantic names, and per-channel detector
   keys (`LICKER0…3`) resolved per station at preflight, so a mis-declared channel is an error
   rather than a silently discarded electrode.
6. **The system refuses to start what it cannot resolve** — preflight blocks on missing modules,
   class mismatches, unresolvable references and unavailable library versions.
7. **The read surface is uniform** — `view.get_value(name)` returns a beam-break, a computed
   variable, or an external measurement identically. *(This belongs to the unified-representation
   argument too — see §7.)*
8. **A new device type is added by a researcher, not by a platform release** — same upload,
   versioning and promotion path as any other library.

### 6.4 A model paragraph

> Behavioural rigs diverge. A driver edited on one station to fix a valve is not the driver running
> on the next bench, and after a few months no record survives of which code produced which data.
> MICS treats device drivers as stored, versioned artifacts rather than files on a controller: a
> driver is uploaded, checked for a valid interface, and advances through explicit states —
> unvalidated, beta, stable — where "stable" can be earned by having carried a complete protocol
> run. Each station declares its own bindings, held centrally and applied at the start of every run,
> so a station's configuration cannot drift unobserved. A task refers to devices by their
> experimental role, and the system resolves those references against the assigned station before
> the session begins, refusing to start when a required device is missing or a reference cannot be
> resolved. The cost is a heavier loop than editing a file on the controller; the return is that
> every session carries an unambiguous record of the code and configuration that produced it.

---

## 7. "One representation across design, execution and data" — what it actually means

The manuscript names this as its key contribution but argues it abstractly. Autopilot *also* has a
version of it, which is why the claim needs sharpening rather than repeating. Here is the functional
difference in plain terms.

### 7.1 What "one representation" means in Autopilot

Autopilot threads three things from design into data, by **convention**:

- **`PARAMS`** — an ordered dict in the task file. The Terminal renders it as the parameter form,
  and the values chosen are stored with the subject. *Design → interface → record.*
- **`TrialData`** — a PyTables schema in the same task file. It defines the columns of the trial
  table. *Design → data schema.*
- **`History_Table`** — every protocol, parameter and step change, timestamped, per subject.
  *A real change log.*

**Intuitively:** in Autopilot, the task file is the single source of truth, and the interface and the
data table are *generated from it*. That is a genuine unified representation, and the draft should
acknowledge it.

**But it is thin in three specific ways:**
1. **It covers only what the author declared.** `TrialData` has the columns someone thought to add.
   Anything else that happened is simply not in the record.
2. **It stops at the task file's edge.** The *logic* is Python — not represented, not comparable,
   not recorded. Two sessions can run visibly different behaviour with identical `PARAMS`, and the
   record cannot tell them apart. Neither is the *driver code* represented: `local.h5` does not know
   which version of `gpio.py` was on the Pi.
3. **Nothing enforces it.** It is a convention between a task file and a GUI. If they disagree,
   nothing objects — the experiment simply runs and records something misleading.

### 7.2 What "one representation" means in MICS

MICS moves the source of truth out of the task file and into a store that every layer reads from,
and adds **enforcement**.

- **Design.** The Blueprint is JSON — states, transitions, conditions, actions. Not code *about* the
  experiment; a **description of it** that other software can read.
- **Validation.** That description is checked before dispatch: do the referenced devices exist on
  this station, do the view keys resolve, does every variable a transition reads get written
  upstream, is any state a dead end. The representation is *enforced*, not assumed.
- **Execution.** The Pi runs that same description — it does not run generated or hand-written code
  derived from it. The FDA object *is* the Blueprint, instantiated.
- **Data.** Every event carries `run_id` and `session_progress_index`, so each record names the run
  and the trajectory step it belongs to. The description that produced the data is recoverable from
  the data.
- **Code provenance.** The driver and compute libraries are versioned artifacts bound to the run, so
  "which code produced this" is answerable — the one link Autopilot has no way to make.

### 7.3 The difference, in intuitive terms

**Autopilot's version is a *template*. MICS's version is a *contract*.**

A template says: here is the form the interface should take and the table the data should go in.
Fill it in. If you fill it in inconsistently — or do something the template never described —
nothing notices.

A contract says: this is what will run, on this station, with these devices, this logic, these
versions. Before anything starts, the terms are checked against reality; if they don't hold, the
session does not begin. While it runs, everything that happens is recorded against the terms. After
it ends, the record names the contract it was run under.

Three questions make the difference concrete:

| Question | Autopilot | MICS |
|---|---|---|
| *"What parameters was this session run with?"* | ✓ in the subject file | ✓ in the run record |
| *"What were the actual contingencies — what led to what?"* | ✗ it was Python; only the author knows | ✓ the Blueprint is stored, versioned and renderable |
| *"Which driver code was on the rig that night?"* | ✗ unanswerable | ✓ pinned version, recorded against the run |

### 7.4 The one-line claim

> In Autopilot the task file is the source of truth and the interface and data schema are derived
> from it by convention. In MICS the specification is the source of truth for every layer, it is
> checked against the assigned station before a session starts, and the record each session leaves
> names the specification, the trajectory step and the code versions that produced it.

### 7.5 Framing note

Do not argue this as "we have a unified representation and others don't". Argue **scope and
enforcement**:

- **Scope** — Autopilot's representation covers *parameters and declared columns*. MICS's covers
  *parameters, task logic, hardware bindings, computations, and code versions*.
- **Enforcement** — Autopilot's is a convention; MICS's is validated before dispatch and stamped
  onto every record.

Those two words carry the whole contribution, and neither can be contested by someone who knows
Autopilot well.
