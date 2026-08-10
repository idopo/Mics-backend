# 16 — MICS vs. Autopilot: the honest comparison

**Written 2026-08-10.** Synthesis of six independent read-only audits (runtime · transport &
timing · hardware & logging · data model · coordination & authoring · provenance) plus a critique
of `12_PAPER_VS_IMPLEMENTATION.md`, `13_MANUSCRIPT_CLAIMS_AUDIT.md`, `14_AUTOPILOT_VS_MICS.md`
and `15_CLAIMS_VS_AUTOPILOT.md`. **This document supersedes those four wherever they disagree.**

**Baselines.** **B1** = vanilla `auto-pi-lot 0.4.4` at `30c8d3c` (2022-04-05, the vendoring
commit), cross-checked against the official PyPI sdist. **Today** = `~/pi-mirror` at `7d22408`
plus the uncommitted working tree, and `~/mics-backend` on `claude`.

**One rule governs the whole document: the only boundary the manuscript defends is Autopilot vs
MICS.** Ido Porat, Lior Segev, Noa and Inbar are all MICS team members; every commit by any of
them is MICS work. Dates appear below only where they say something about how the system evolved
(e.g. "built by hand on the Pi in 2025, before the database layer existed"), never to decide what
MICS may claim.

**Citation discipline.** Every substantive claim carries a `file:line` or a commit hash taken from
one of the audits. Where no source audit supplied one, the claim is marked **[unsourced]**.

---

## 1. Executive summary

### The one sentence

> **MICS is a different system built on Autopilot's Pi runtime: it runs Autopilot's daemon,
> Autopilot's ZMQ transport, Autopilot's hardware driver library and Autopilot's pigpio clock, and
> on top of them it replaces Autopilot's task model, data model, provisioning model and
> coordination layer outright.**

Two supporting facts that bound this in both directions. Below the Pi process boundary the
dependency is total — delete `autopilot/` and nothing starts (`pilot.py` is Autopilot's file;
`networking/node.py` and `networking/message.py` are byte-identical to 0.4.4 on **both** ends of
the wire). Above it, essentially nothing survives: 35 vendored upstream modules totalling ≈11,900
lines ship in the release and are executed by nothing, including the entire Terminal, GUI, plotting
and subject-file stack.

The word **"fork" should not be used.** The MICS repository predates the Autopilot import by nine
months (`f49dfe7`, 2021-07-21 vs `4b28bd7`→`30c8d3c`, 2022-04-05); Autopilot was **vendored into an
existing repo**, not forked from. Use *"vendored dependency"*.

### Clean wins — claim these hard

| Claim | Why it survives a hostile reviewer |
|---|---|
| **The task specification is data, not code** | `fda_json` JSONB, content-addressed by sha256 (`api/db.py:62-67`; `routers/toolkits.py:605-609`); executed directly by `load_fda_from_json` (`mics_task.py:1060-1269`). Autopilot's task is a Python class no other layer can read. |
| **Automatic event-level instrumentation** | `auto_log`/`log_action` return **0 matches across 518 files** of the 0.4.4 sdist. The single most checkable claim in the paper — *provided it is worded per §3.2.* |
| **Pre-dispatch static analysis of the task graph** | 11 preflight kinds (`toolkit_dispatch.py:155-167`), including a sound deadlock detector (`api/wait_analysis.py`) whose docstring names the real incident it was written for (task def 186, run 541). Autopilot has no pre-run validation and **no TODO expressing an intent to add one** (verified twice). |
| **The trigger queue** | A correctness fix to inherited Autopilot code: B1 `task.py:279-306` drops concurrent triggers *and* wipes the whole trigger table after one fires. `c632674` replaced it with a queue + worker thread. The diff proves both the defect and the fix. |
| **Driver code and rig configuration as versioned, centrally resolved database artifacts** | `hardware_libs`/`hardware_lib_versions` with sha256, promotion states and an on-Pi import test (`models.py:639-655`; `pilot.py:680-691`). Autopilot's answer is a file on eight Pis and no record of which one ran. |
| **The session as a first-class entity spanning subjects and rigs** | `sessions`/`session_runs`/`run_progress` (`models.py:410-481`). Autopilot can run four animals concurrently but has **no entity that groups them** — `session` is a private integer in each subject's HDF5 attrs. |

### Claims that must be dropped or reworded before submission

1. **"Periodic synchronization with a global reference … a unified experimental timeline."**
   Events from different rigs do **not** share a timeline. NTP is commented out — in the very
   commit that introduced it (`a008046`) — each Pi's `synchronize()` anchors to its *own* wall
   clock, and the repo says so itself (`ROADMAP.md:496`: *"those machines are not NTP-synced to
   each other"*).
2. **"Preflight hard-blocks."** It does not block anything. `HardwareCheckModal.tsx:551`'s start
   button is always enabled; `PilotSessions.tsx:100-102` proceeds on a preflight *error*; there is
   no server-side re-check on the start path; `orchestrator_station.py:387-388` says *"never block
   a run preflight cleared."* **A ~20-line change makes this claim true.** See §6-F1.
3. **"The driver code that ran your experiment is a versioned artifact recorded against the run."**
   `session_runs` has **no version column** and there is no run↔version join table. What is
   recorded is a *resolution policy* over mutable state; editing a task definition's pins
   afterwards silently rewrites the answer for every historical run. **A one-column change makes
   this claim true.** See §6-F2.
4. **Performance-based / adaptive progression.** MICS evaluates only `NTrials` (`api/main.py:1750`).
   Autopilot has `NTrials` **and** `Accuracy` (`graduation.py:40-95`). Table 1 currently reverses
   the truth on this axis. Drop it.
5. **"Autopilot has no clock synchronisation."** False, and false in the direction that flatters
   us. Autopilot pins a **forked pigpio** (`requirements_pilot.txt:18`, *identical line at
   `30c8d3c`*) whose documented purpose is microsecond-precise GPIO timestamps
   (`README.md:130`). `synchronize()` and `ticks_to_timestamp()` are that fork's API. **MICS's
   entire timebase is a borrowed Autopilot artifact.**
6. **Sample-accurate audio.** MICS swapped jack/pyo (`FS=192000`, `-p16`, RT prio 75) for pygame
   `mixer.init(buffer=1024)` and loads the WAV from the SD card *inside* the cue call
   (`mixer.py:19,25-27`). A ~100–500× nominal latency difference.
7. **"Multiple users can operate the facility concurrently."** They can *view* concurrently. One
   shared service JWT, no user identity anywhere, no pilot busy-check, unauthenticated WebSocket.

### The real debts — short list

Only five things are genuinely Autopilot's and genuinely load-bearing:

1. **The forked pigpio timebase** — µs-precise, wall-clock-aligned GPIO timestamps. Not
   replaceable without real work.
2. **`gpio.py`'s pigpio stored-script waveform layer** (`gpio.py:519-793`) — pulse trains that
   run in the pigpio daemon, off the Python GIL. Every MICS valve pulse rides on it unmodified.
3. **1,438 lines of working, tested pigpio drivers** on which every MICS effector is a subclass.
4. **Local executor autonomy** — the Pilot owns its task for the duration and keeps running if the
   coordinator dies. A design commitment, not a shape, and MICS gets it for free.
5. **The MPL-2.0 file-level obligation** on ten upstream files MICS modified in place (§4.1).

Everything else the old docs conceded — the coordination topology, the wire protocol *as an idea*,
`init_hardware()`, the `Hardware`/prefs abstraction, "scaling to many Pis", "one architecture
across paradigms" — is generic engineering that belongs to nobody. §5.

### The highest-value items in this document

Six small code changes convert a currently-false claim into a true one. They are flagged **F1–F6**
in §6 and are worth more to the manuscript than any rewording.

---

## 2. The three-way ledger

**Verdicts.** **GENERIC** — any competent Python+ZMQ+pigpio rig from scratch lands here; no
conceptual novelty and not an Autopilot trademark; MICS should neither claim it nor concede it.
Where MICS nonetheless *runs Autopilot's bytes*, the row is marked **(code dep)** — a code
dependency is not an idea dependency. **AUTOPILOT** — distinctive design MICS depends on and must
credit. **MICS** — real new capability or architectural inversion. **REGRESSION** — something
Autopilot had that MICS lost, or a cost of MICS's design.

### 2.1 Process and execution

| Capability | Verdict | Evidence | One-line justification |
|---|---|---|---|
| Pi daemon bootstrap: prefs parse, logging, pigpio init, networking thread, `state`/`update_state` | **GENERIC (code dep)** | `pilot.py:168-261`; B1 `pilot.py:141-260` | pyControl's `pycboard`, Bpod's `BpodObject` and every homegrown rig daemon have a structural equivalent. |
| `self.listens` = `{key: bound method}` dispatch | **GENERIC (code dep)** | `pilot.py:214-225`; B1 `pilot.py:185-193` (**7** keys) | A string→handler dict is the default shape of every message-driven daemon. |
| `l_start` / `l_stop` / `l_param` RPC surface | **GENERIC (code dep)** | `pilot.py:565,615,693`; B1 `:274,324,355` | Minimum viable RPC. `l_param` is still `pass` — inherited *and* dead. |
| `run_task` on its own `threading.Thread` | **GENERIC (code dep)** | `pilot.py:601`; B1 `pilot.py:311` | Running the experiment off the network thread is forced by the problem. |
| **`self.stages` is an iterator of zero-arg callables; `while True: next(stages)()`** | **AUTOPILOT** (thin but real) | B1 `pilot.py:756`; today `pilot.py:1183` | A genuine design choice — an iterator of bound methods rather than a `step()`/callback API — and MICS still honours it. See §4.9 for how thin, and why it still mattered. |
| **Local executor autonomy** — the Pilot owns its task for the duration; coordinator loss does not stop it | **AUTOPILOT** | `CITATION.cff` (B1); `core/pilot.py` inherited essentially intact | A commitment, not a topology. MICS relies on it wholly and never re-litigates it. |
| Autopilot plugin registry resolving `task_type` | **AUTOPILOT** (still live) | `pilot.py:526,593`; `utils/plugins.py:21-88`; `prefs.json AUTOPLUGIN=true`; **28 files** in `pilot/plugins/` | Delete `utils/plugins.py`/`registry.py` and no task starts. The docs imply this was replaced; only *hardware libs* were. |
| `PARAMS` / `HARDWARE` / `TrialData` / `PLOT` class-attribute manifests | **GENERIC (code dep)** | B1 `task.py:22-60` | Bpod has `SettingsMenu`, pyControl has module-level params + a board file. |
| `init_hardware()` — construct devices from `HARDWARE` × `prefs['HARDWARE']` | **GENERIC (code dep)** | B1 `task.py:105-160`; today `task.py:150-215` | A double `for` loop over two nested dicts calling a constructor. Autopilot's own paper does not claim it. |
| `hw.is_trigger → hw.assign_cb(handle_trigger)` single central callback | **GENERIC (code dep)** | B1 `task.py:130-132` | pigpio gives one callback per pin; funnelling them is the obvious move. |
| **`FiniteDeterministicAutomaton` as `self.stages`** — named states, guarded transitions | **MICS** | `FiniteDeterministicAutomaton.py:5-96`; `8b7bd7c` (2024-08-18), on the mainline via `94fb000` | Autopilot: `itertools.cycle(stage_list)` — a fixed ring, no names, no conditions. A different computational object. |
| `saga_trace` + `state_transition` event on every state entry | **MICS** | `FiniteDeterministicAutomaton.py:11,16-19,74,83`; `851f8b4` | Autopilot logs nothing per stage. |
| `check_determinism()` / `boolean_conflict()` | **MICS** (bounded) | `FiniteDeterministicAutomaton.py:38-52` | Real, but it *calls* the predicates at registration and swallows every exception (`:51-52`). Load-time spot-check, not static analysis. |
| **Generator-based interruptible states** | **MICS** | `pilot.py:1188-1197`; `23e6bf7` (2025-03-18); `import types` added by that commit | Autopilot's stage method is atomic; MICS's can be aborted mid-execution by clearing `self.running`. |
| `wait_for_condition()` — the polling primitive that replaced `stage_block` | **MICS** (with a cost) | `mics_task.py:482-495` (500 µs sleep) | Cooperative polling by the state, not an `Event` set by a trigger. Trades CPU for interruptibility. |
| Per-trigger error isolation + `TRIGGER_ACTION_ERROR` event | **MICS** | `task.py:309-334` | New. |
| `STAGE_NAMES` manual list → class introspection | **MICS** (small) | `pilot.py:456-463` | Derived from the class instead of maintained by hand. |
| **`stage_block`** — zero-cost blocking on a `threading.Event` | **REGRESSION** (fully dead) | `task.py:119` `= None`; `mics_task.py:104` swallows the kwarg; `pilot.py:1227`, `task.py:307,402` commented | Autopilot's actual concurrency contract, replaced by a 500 µs busy-poll. `mics_task.py:1553`'s docstring still claims otherwise. |
| One-shot trigger semantics (trigger fires → advances the stage) | **REGRESSION** (deliberate) | B1 `task.py:302-306`; today `task.py:398,402` commented | Triggers are now persistent and orthogonal to state advance. Better, but it *is* a broken contract. |
| Arbitrary Python inside a stage | **REGRESSION** (deliberate) | `mics_task.py:914-919` `CALLABLE_METHODS` whitelist | A novel computation needs a versioned compute library, not a line of Python. Real cost; say so. |
| `tasks/children.py` — `Transformer`/`Wheel_Child`/`Video_Child` pilot federation | **AUTOPILOT**, unused | `children.py:179`; sole tree reference is `utils/registry.py:42`; `prefs.json LINEAGE="PARENT"`, no children | A genuine AP concept MICS inherits and does not use. |
| ~233 lines of inherited handlers wired into `listens` and never exercised | **REGRESSION** (dead weight) | `pilot.py:705-947` — `l_cal_port`, `calibrate_port`, `l_cal_result`, `l_bandwidth`, `l_stream_video`, `calibration_curve` | Of 823 inherited `pilot.py` lines, **~330 belong to methods MICS never calls**. |

### 2.2 Transport

| Capability | Verdict | Evidence | One-line justification |
|---|---|---|---|
| ZMQ ROUTER/DEALER + JSON envelope `{id,to,sender,key,value,flags,ttl}` | **GENERIC (hard code dep)** | `networking/message.py` **byte-identical** to B1 on the Pi **and** in the orchestrator | ROUTER/DEALER with identity frames is literally the ZMQ guide's async client/server pattern; `serialize()` is `json.dumps(self.__dict__)`. |
| `{key: handler}` dispatch on the orchestrator side | **GENERIC (ours)** | `orchestrator/main.py:71-81` | Written fresh; names the same keys. |
| CONFIRM + outbox + TTL-decrementing resend | **GENERIC (code dep + reimplemented)** | B1 `node.py:72,221-223,336-366`; MICS copy `RouterGateway.py:29,49,152-154,192-238` | App-level ack over ZMQ. MICS reproduced the semantics faithfully **including the weaknesses** (no ordering, 10 s resend, `ttl=2`). |
| **Transparent ndarray compression** — base64'd `blosc.pack_array` through `json.dumps(default=)` / `object_pairs_hook`, `expand_arrays` lazy decompress | **AUTOPILOT** | `message.py:75-78,157-184,265`; `requirements.txt blosc==1.10.6` | The genuinely non-obvious part of `Message`, and a real design idea for a video-carrying rig bus. **MICS runs it and never sends an ndarray.** Credit it; do not claim it. |
| **`flags` protocol** (`NOREPEAT`, `NOLOG`, `MINPRINT`) | **AUTOPILOT** (minor but live) | `message.py:35-40`; MICS depends at `station.py:1106,1154`, `RouterGateway.py:152,192` | Per-message opt-out of ack and of logging so a 30 Hz stream does not drown the outbox. MICS uses it today. |
| Multi-hop routing / `routes` / `l_forward` | **AUTOPILOT**, unused as routing | `station.py:498-560,1325-1329` | MICS reuses `l_forward` as a local dispatcher only. |
| `Net_Node.get_stream()` — bounded, batched, compressed streaming | **AUTOPILOT**, unused | `node.py:468-610`; importers are `cameras.py`, `tasks/test.py` only | MICS re-invented bounded-queue egress in Phase 18 while this sat unused in the same tree. |
| `RouterGateway` — orchestrator-side ROUTER peer | **MICS** (fresh code, inherited semantics) | `RouterGateway.py:1-239` | Replaces Autopilot's `Terminal_Station`, which served a Terminal that does not exist here. |
| Handshake watchdog (re-HANDSHAKE after >21 s without PING) | **MICS** | `station.py:1328-1375`; `pilot.py:229-230` | The only reason a pilot recovers from an orchestrator restart. |
| `UPDATE_FDA` / `LOAD_HARDWARE_LIBS` / `INC_TRIAL_COUNTER` keys | **MICS** | `station.py:1078-1079`; `pilot.py:222-223`; `0aa62f2` | +2 pilot keys on a 7-key vocabulary, plus one inbound key. |
| `OrchestratorState` thread-safe live registry | **GENERIC (ours)** | `state.py:7-109` | `RLock` + dicts. Competent, unremarkable. |
| Backend queues (`data_queue`/`trial_queue`, bounded 50 000) | **GENERIC (ours)** | `orchestrator_station.py:55-56,554-585` | Decouples the IOLoop from ES/HTTP. |
| Orchestrator's vendored `node.py` (176 L) + `station.py` (255 L) | **REGRESSION** (dead code) | nothing imports them; `RouterGateway.py:10` imports only `message.py` | Two unused re-implementations shipped in the image. Doc 14 §1c describes them as if live. |
| `BANDWIDTH` / `STREAM_VIDEO` | **REGRESSION** (dead both ends) | handlers `pilot.py:221-222,811-856`; only senders are Autopilot's Qt GUI | Nothing in the orchestrator emits either. |

### 2.3 Hardware

| Capability | Verdict | Evidence | One-line justification |
|---|---|---|---|
| `class Hardware` with `name`/`group`; `HARDWARE` dict keyed group→id; pins in `prefs.json` | **GENERIC (code dep)** | B1 `hardware/__init__.py:78-120`; `task.py:150-181` | Bpod `PortArray`, pyControl board definition, BControl `@hardware`, and `#define VALVE1 35` all land here. |
| BCM↔board pin translation table | **GENERIC (code dep)** | B1 `hardware/__init__.py:57-75` | Pinout arithmetic, cited to a public diagram in its own docstring. |
| pigpio as the GPIO layer | **GENERIC** | `Event_Dispatcher.py:77` | pigpio is *the* choice for µs Pi GPIO. Not an Autopilot design contribution. |
| **pigpio stored-script waveform layer** — `_series_script` / `store_series` / `series` / `_stop_script` | **AUTOPILOT** | `gpio.py:519-793`; MICS depends at `gpio.py:1632` (`Solenoid.open`) and `:1691-1706` (`Pulse20Hz`) | Compiles a waveform into a pigpio script so pulse timing leaves the Python GIL. The strongest hardware-domain debt; MICS added ~0 lines and would have to reinvent it. |
| **Forked pigpio** — µs-precise, isoformatted GPIO callback timestamps; `synchronize()`; `ticks_to_timestamp()` | **AUTOPILOT** | `requirements/requirements_pilot.txt:18` (**identical line at `30c8d3c`**); `README.md:130`; `gpio.py:7,790`; `ticks_to_timestamp` appears in the repo **only as call sites** in `Event_Dispatcher.py` | MICS's entire timebase is a borrowed Autopilot artifact. §4.2. |
| 1,438 lines of tested drivers: `GPIO`/`Digital_Out`/`Digital_In`/`PWM`/`LED_RGB`/`Solenoid` | **AUTOPILOT** (engineering, not concept) | `gpio.py`; ~94 % of original lines retained | MICS's `Solenoid_mics`/`TTL`/`Pulse20Hz` are all `Digital_Out` subclasses. |
| `Camera` base class (used by `MLX90640`) | **AUTOPILOT**, load-bearing import | `i2c.py:8,580`; `hardware/cameras.py` +0/−0 | The capability is unused; the **import is not removable** — deleting it breaks every I2C import. |
| `transform/` — 10 composable real-time modules | **AUTOPILOT**, capability unused, **import load-bearing** | `i2c.py:9,474` imports `IMU_Orientation`, `Spheroid` at module scope | Honest wording: *"Autopilot's on-Pi real-time transform pipeline is not used by MICS"*, **not** *"MICS does not depend on `transform/`."* |
| `HardwareState` IntEnum + `get_state()` + `reverse_view()` | **MICS** | `hardware/__init__.py:80-85,152-153,286-288` | What makes a hardware object readable as a view key. |
| `Sensor` / `Effector` ABCs + auto initial state | **MICS** | `hardware/__init__.py:87-101`; `cde16ca` | Thin (one abstract method each) but load-bearing for the View/logging design. |
| `event_dispatcher` ctor arg on every `Hardware` | **MICS** | `hardware/__init__.py:132,150`; `bb393c4` | B1 is `def __init__(self, name=None, group=None, **kwargs)`. |
| `i2c.MPR121`, `Motor_Shield_Hat`, `Motor_Shield_Hat_extend`, `Touch_Detector` | **MICS** | `i2c.py:799,892,949,973` | The capacitive-lickometer and motor stack the lab's science runs on. Doc 14 files `i2c.py` under "inherited". |
| `gpio.TTL` (Master-8 train), `Solenoid_mics`, `Pulse20Hz`; `mixer.py`, `timer.py`, `unreal.py` | **MICS** | `gpio.py:1130,1640,1650`; `hardware/{mixer,timer,unreal}.py` | All absent at B1. |
| **Driver source in Postgres**: versioned, AST+`py_compile` gated at upload, shipped per run, `exec`'d on the Pi | **MICS** | `models.py:639-676`; `hardware_libs.py:53-107`; `pilot.py:36-46,670-691`; `mics_task.py:206-231` | Autopilot's answer is `PLUGINDIR` + files, and nothing anywhere records which file ran. |
| `SEMANTIC_HARDWARE` + `SEMANTIC_HARDWARE_RENAMES` — friendly-name indirection | **MICS** | `mics_task.py:67-88,1114-1151`; `learning_cage.py:130` | Autopilot names `self.hardware['PORTS']['L']` directly; renaming a group breaks every stored protocol. |
| `pilot_hardware_config` — backend-authoritative, fully replaces a prefs group per run | **MICS** | `models.py:707-716`; `mics_task.py:233-252` | The Pi's `prefs.json` is no longer the source of truth. |
| Detector-derived per-channel view keys (`LICKER0…N`) | **MICS** | `mics_task.py:301-365` | Individual spouts of a multi-electrode lickometer are addressable, and a mis-declared channel fails preflight. |
| `stim/sound` (jack/pyo, `FS=192000`, `-p16`, RT prio 75) → pygame `mixer.init(buffer=1024)` | **REGRESSION** | `mixer.py:19`; `jackclient.py:165-167`; `prefs.json AUDIOSERVER=false` | ~100–500× nominal output latency, plus a per-trial SD-card WAV decode inside the cue call (`mixer.py:25-27`). |
| `self.hardware_type = kwargs['type']` unguarded | **REGRESSION** | `hardware/__init__.py:149` | Vanilla allowed `Digital_Out(pin=7)`; today that raises `KeyError`. Every construction path must go through prefs. |
| `hardware/usb.py` (358 L) | **REGRESSION** (dead) | only importers are `children.py:17` and a vendored test | Doc 14 files it under "inherited and still load-bearing". |

### 2.4 Logging and data

| Capability | Verdict | Evidence | One-line justification |
|---|---|---|---|
| Python `logging` + `RotatingFileHandler` debug logs | **GENERIC (code dep)** | B1 `core/loggers.py` (175 L) | Developer debug logging; produces no scientific record and never touches the ZMQ path. |
| Per-subject HDF5 file as the unit of persistence | **GENERIC** | B1 `subject.py:41-58,63,132` | The standard lab convention of 2015–2022 (Bpod `.mat`-per-session, pyControl, BControl). |
| Per-subject monotonic session counter | **GENERIC** | B1 `subject.py:170,699-708` | An integer in `/info._v_attrs`. Purely subject-local. |
| Weights table | **GENERIC** | B1 `subject.py:1205-1298` | Every rodent lab records weights. |
| `Accuracy` graduation criterion itself | **GENERIC** | B1 `graduation.py:40-93` | 50 lines of `deque` + `np.mean`, and hobbled — `window=500` means it cannot fire before 500 trials. |
| **The task class as schema authority** — `TrialData(tables.IsDescription)` → materialised trial tables, with auto-injected `session`/`trial_num` and stim-derived columns | **AUTOPILOT** | `task.py:103-105`; `subject.py:496-536,499-531` | The analysis artefact is produced as a side effect of declaring the task. MICS's `task_definitions.params` is its lineal descendant. |
| **`History_Table`** — append-only in-band change log of every protocol/param/step change | **AUTOPILOT** | `subject.py:325-392,1312-1326` | Distinctive for its era, and the honest ancestor of MICS's provenance argument. |
| **`past_protocols`** — superseded protocol JSON archived, not overwritten | **AUTOPILOT** | `subject.py:584-610` | **MICS has no equivalent** — `protocol_templates` rows are mutated in place. Volunteering this makes the rest credible. |
| Graduation plumbing: object built from protocol JSON, fed declared columns, history trimmed at step change | **AUTOPILOT** | `subject.py:611-762`, esp. `:656-682`, `:746-754` | The careful part: a subject stepped back down is not graduated by stale data. |
| `Data_Handler` sink ABC | **AUTOPILOT-derived shape** | `Data_Handler.py:5-38` vs `subject.py:611,781,940,950` | A verbatim extraction of `Subject`'s sink lifecycle — same four methods, same attributes. Interface inherited, implementation replaced. |
| **`@auto_log` / `@log_action`** — driver methods instrumented by decorator | **MICS** | `logging_utils.py:8-12,15-99`; applied `gpio.py:32,324`; `bb393c4` | **0 matches for `auto_log\|log_action` across 518 files of the 0.4.4 sdist.** Built by hand on the Pi in 2025, before the database layer existed. |
| Central input instrumentation in `Task.execute_trigger` | **MICS** | `task.py:267-278` | Every trigger emits a `Hardware_Event` *before* any callback runs — logged whether or not a callback exists. |
| **`Event` / `Hardware_Event` / `Event_Dispatcher`** — one task-agnostic envelope | **MICS** | `Event_Dispatcher.py:38-49`; `1b17efc`, `d07c331` | `git ls-tree 30c8d3c` on `networking/` and `utils/` lists neither file. The inversion from *the task describes its data* to *the instrument describes itself*. |
| **Trigger event queue** — no dropped hardware events | **MICS**, a correctness fix to Autopilot | `task.py:129-133,254-266,335-373`; `c632674` | B1 dropped triggers on lock contention **and** wiped `self.triggers` after one fired. §3.3. |
| Async egress queue + drop counters on the event path | **MICS** | `Event_Dispatcher.py:28-32,51-58,78-86` | A blocking `node.send` can no longer stall a hardware callback. |
| One ES document per event, envelope-stamped with `run_id` and `session_progress_index` | **MICS** | `Event_Dispatcher.py:38-49`; `34ee67b` | Every record names its run and its trajectory step. |
| 28-table Postgres relational model (12 SQLModel + 16 SQLAlchemy) | **MICS** | `api/models.py`; two also created by raw SQL at `api/db.py:176,299` | Autopilot has one HDF5 per subject and no cross-subject query of any kind. |
| Session as a first-class entity spanning subjects **and** rigs | **MICS** | `main.py:783-842`; `models.py:431-463`; `main.py:1330-1337` (`FOR UPDATE` on `run_counter`) | Autopilot runs four animals at once routinely; it has **no entity that groups them**. |
| `new` / `resume` / `restart` run modes + `_strip_graduation_from_overrides` | **MICS** | `main.py:1267-1309,1577-1605`; `models.py:461` | A re-run deliberately does not inherit a stale graduation criterion. |
| Versioned lib promotion `unvalidated→beta→stable` + sha256 + on-Pi import test + single resolution chain | **MICS** | `models.py:639-655`; `lib_version_resolution.py:23-92`; `pilot.py:680-691` | Genuine, and large, relative to a file on eight Pis. See §3.6 for the two bounds. |
| **No trial table, no trial record** | **REGRESSION** (accepted trade-off) | 28 tables, none named `trials`; ES holds one doc per *event* | Trial boundaries are recoverable (`Trial_Tracker.increment`); trial *outcomes* are not recorded anywhere. |
| **Performance-based graduation** | **REGRESSION** | `api/main.py:1750` — `if prog.graduation_type == "NTrials"` and nothing else | The one axis where MICS is behind its own foundation. §6. |
| Local durability of data on the Pi | **REGRESSION** | `pilot.py:999-1054` `open_file` orphaned (`490121e`); `:1204-1223` row-fill commented (`53f86ab`) | Autopilot wrote trials to HDF5 *before* sending anything. A network partition mid-run now loses the run. |
| Autopilot's rotating debug log | **REGRESSION** (deliberate) | `core/loggers.py` diff: `mode='a'`→`'w'` ×2 + `doRollover()`; `prefs.json LOGLEVEL=ERROR` | Pi log files are always 0 bytes. Intentional in the lab, but it *is* a lost capability. |
| ES ingestion robustness | **REGRESSION**-ish | `ElasticSearchDateHandler.py` — one `client.index()` per doc, no bulk, no retry, no dead-letter, `except: print` (`:55-56`); host hardcoded `:17,74` | Relevant only if the paper says anything about data integrity. |

### 2.5 Coordination and authoring

| Capability | Verdict | Evidence | One-line justification |
|---|---|---|---|
| Central coordinator ↔ N distributed executors | **GENERIC** | B1 `terminal.py:72,182,186` | Every web app, CI runner pool and print spooler has it. Autopilot's own `CITATION.cff` claims **flexible hardware composition, timing performance and cost** — not a coordination topology. |
| **Uniform agent/networking substrate** shared by Terminal, Pilot and Child (incl. a plot widget as a first-class network peer) | **AUTOPILOT** | B1 `networking/{station,node,message}.py`; `plots.py:231` | One message vocabulary across heterogeneous agent roles. Real design work; MICS retains the wire format. |
| Qt Terminal as a program | **GENERIC**, dead in MICS | `terminal.py:72` `class Terminal(QtWidgets.QMainWindow)` | A desktop GUI holding a device list is not a scientific contribution. Its *placement on the data path* is the consequential decision — and the one MICS reverses. |
| Parameter form rendered from a task's `PARAMS`; `Protocol_Wizard`, `Graduation_Widget` | **GENERIC / AUTOPILOT-adjacent** | `gui.py:867,1201,1374` | Composes steps and sets numbers over a task **someone already wrote in Python**. Not a task-authoring system. |
| Water-port calibration (results shipped back to the Pi), bandwidth test, plugin manager, batch reassign, weights table | **AUTOPILOT-adjacent**, genuinely useful | `gui.py:2153,1661,2673,2422,2577`; `terminal.py:835-866` | A decade of operational tooling MICS replicates almost none of. Concede it. |
| **Live per-trial plotting**, configured from the task's own `PLOT` dict, fed by an independent ZMQ subscription | **AUTOPILOT** — **MICS lost it** | `plots.py:129,231,291-388`; primitives `Point:501 Line:544 Segment:566 Roll_Mean:599 Shaded:639` | The task declares how it should be visualised and a live plot appears with zero setup. Nothing equivalent exists in 84 TS/TSX modules. |
| Pre-run validation of any kind | **absent in Autopilot** (verified twice) | `terminal.py:516-573` read in full; `git show 30c8d3c:…/terminal.py \| grep -niE "valid\|verif\|preflight"` → **exit 1** | Autopilot has none **and no TODO expressing an intent to add one.** Do not cite the `:565` "coherence checking ritual" TODO — it concerns post-stop data reconciliation. |
| **The UI is not in the data path** | **MICS** (architectural) | ingest wholly inside the orchestrator: `orchestrator_station.py:245-249,554` → ES; `web_ui/app.py:42,67` is read-only | The exact inverse of B1 `terminal.py:595`, where the Qt window object holds the open HDF5 handles. |
| **Coordination state is durable rows, not a window** | **MICS** (architectural) | `run_progress.current_step_idx`, `session_runs.status`; Redis `pilot:<key>` at `orchestrator_station.py:187-235` | Autopilot's entire persistent coordination state is `pilot_db.json` — pilot→subject/IP only. Progression lives in a Qt object's memory. |
| **Task logic as data** — `fda_json` JSONB, content-addressed | **MICS** (architectural) | `api/db.py:62-67`; `routers/toolkits.py:605-609` | The enabling condition for preflight, the editor, versioning and hot reload. |
| Visual FDA canvas: react-flow states/edges, nested AND/OR trees, 7 action types, 4 arg modes, variables with output capture, trigger→action bindings | **MICS** | `TaskEditor.tsx` (806 L); `ConditionGroupsEditor.tsx`; `ActionEditor.tsx:198-221`; `TriggerAssignmentPanel.tsx` (399 L) | No Autopilot counterpart at any level. |
| **Pre-dispatch static analysis** — 11 kinds, 2 real analyses incl. a sound deadlock detector | **MICS** | `toolkit_dispatch.py:155-167`; `api/variable_scan.py`; `api/wait_analysis.py` | `state_wait_unsatisfiable` is the strongest single item in the audit. §3.8. |
| Hot reload of a running task | **MICS** | `mics_task.py:1544-1584`; `pilot.py:646-668`; `orchestrator_station.py:982-997` | Autopilot requires editing a file on the Pi and restarting. |
| Device lease with correct DB-level atomicity | **MICS**, narrow | `api/device_lease.py:184-202`; `UNIQUE(host)` at `api/db.py:294-311`; `orchestrator_station.py:386-396,459-466,999-1045` | `INSERT … ON CONFLICT DO NOTHING` + read-back, not a Python check-then-act race. **Keyed on an external device host, not on a pilot.** |
| **Preflight enforcement** | **absent** | `HardwareCheckModal.tsx:551` always-enabled; `PilotSessions.tsx:100-102` proceeds on error; no server-side call site on the start path; `orchestrator_station.py:387-388` | The claim "preflight hard-blocks" is false of the code today. §6-F1. |
| **Multi-user arbitration** | **absent** | one shared JWT `sub:"mics-terminal"` (`api/auth.py:20`), payload discarded; no busy-check in `POST /session-runs` (`main.py:1236-1345`); `await ws.accept()` unconditional (`web_ui/app.py:51`) | Two users can start two runs on one pilot. Zero hits for `multi-user\|RBAC\|per-user` across the planning docs. |
| 111 REST routes, FastAPI, JWT, React SPA, WebSocket, Docker | **GENERIC (ours)** — *not a contribution* | `api/` 8,976 non-test lines + 8 routers; `web_ui/react-src` 84 modules / 13,055 lines / 18 routes | Scope and a technology choice. Buys remote access and concurrent viewing; buys no claim. Say so first. |
| Relational colony model (projects, experiments, researchers, surgeries, IACUC) | **MICS** — product feature | `main.py:166-688`; `models.py:114-181` | Real capability, ordinary engineering. Claim it as facility management, not as architecture. |
| Deployment cost | **REGRESSION** | 7 containers, **zero resource limits**, plus external ES and Postgres and Redis | Autopilot needs a Pi and a laptop. Concede it. |

### 2.6 Timing

| Capability | Verdict | Evidence | One-line justification |
|---|---|---|---|
| **Microsecond-precise, wall-clock-aligned GPIO timestamps** | **AUTOPILOT** | `requirements_pilot.txt:18` at `30c8d3c`; `README.md:130`; `gpio.py:7,790` | The forked pigpio *is* the timebase. §4.2. |
| `pigpio.pi(sync_ticks=True)` + one shared `synchronize()`d client threaded into every device | **MICS wiring on an AUTOPILOT capability** | `pilot.py:1139-1150,1159`; `task.py:189`; `a008046` (2026-01-25) | Autopilot lets each hardware object open its own connection. MICS adds the *call*, not the capability. |
| pigpio-tick timestamps carried in the event stream | **MICS** | `Event_Dispatcher.py:44,77`; `a008046` | Autopilot has no per-event stream to put a clock into. |
| Thread-local `_trigger_ctx` — hardware actions inside a trigger inherit the firing edge's tick | **MICS** | `mics_task.py:1511-1539,865-869` | Careful, and worth a clause. |
| `pi_timestamp` = the true GPIO edge, carried on the trigger queue | **MICS** | `task.py:275-276`; `localize_tz` `utils/common.py:329-334` | The incoming `tick` is already an ISO string — that is the forked pigpio's doing. |
| **Two clocks in one document** | **REGRESSION / hazard** | envelope `timestamp` sampled *after* the action completes (`logging_utils.py:79,97`) vs `event_data.pi_timestamp` = the edge (`task.py:275-276`) | They are not the same instant; the gap is the trigger-queue latency, which is unbounded and unmeasured. |
| NTP alignment | **absent — dead code** | `pilot.py:498,514` defined; `:1138,:1148` both commented, **in the commit that introduced them** (`a008046`) | "The NTP calls exist and are commented out" should read *"were never enabled."* |
| **Cross-machine / cross-rig clock sync** | **absent in both systems** | per-Pi `synchronize()`; per-host `get_localzone()` (`common.py:332`); backend re-stamps to one zone (`ElasticSearchDateHandler.py:48-51`); `ROADMAP.md:496` | The single finding most likely to cost the paper a claim. |
| `gpio.TTL` shared-edge alignment to an external recorder | **MICS**, **switched off** | `gpio.py:1130` (`2e545d0`); `learning_cage.py:85-86` declares `TTL1`, `:191`, `:208` commented; `mics_task.py:1594` likewise | The only mechanism that *could* align a Pi to an external recorder is wired and disabled in the live path. §6-F5. |
| Pre-2026-01-25 events carry `datetime.now().timestamp()` | **archive fact** | `git show origin/MICS_main:…/Event_Dispatcher.py` | Material for any analysis spanning the archive, and recorded nowhere. |

---

## 3. What MICS genuinely contributes

### 3.1 The FDA / Blueprint as data rather than code

**Mechanism.** `self.stages` is a `FiniteDeterministicAutomaton` (`mics_task.py:156`) whose
`__next__` walks a transition table `{method: [(next_method, [predicates], description)]}` and
returns the first successor whose predicates all hold, raising `StopIteration` — which `run_task`'s
`finally` turns into a clean task end (`FiniteDeterministicAutomaton.py:67-89`). That automaton is
then built **from a JSON document**: `load_fda_from_json` (`mics_task.py:1060-1269`, 210 lines)
fans out into `_build_state_method` (109 L), `_build_action_callable` (152 L),
`_build_condition_operand` (85 L), `_build_if_action` (41 L), `_build_transition_lambda` (43 L) and
`_build_tree_lambda` (32 L) — roughly **520 lines of interpreter** turning a data document into
executable closures. Guards are arbitrary AND/OR trees over typed operands
(`view`/`tracker`/`flag`/`param`/`hardware`/literal). Triggers are assembled from the *same* action
vocabulary as state bodies (`apply_trigger_assignments`, `:1438-1500`). The whole machine can be
swapped into a live task over ZMQ (`hot_update_fda` `:1544-1584`; `pilot.py:646-668`).

**Evidence it is new.** Autopilot's task is `self.stages = itertools.cycle(stage_list)` — a fixed
ring with no names, no conditions and no branching; a trial is exactly one lap, and branching lives
in Python inside a stage method. Nothing outside the file can inspect, validate, diff, render or
edit it.

**The honest bound.** Three things must be said or a reviewer will say them.
- **The FDA object predates the database layer by 18 months.** It was authored by hand on the Pi
  (`8b7bd7c`, 2024-08-18) and reached the production branch via `94fb000` (2024-11-11) as a
  byte-identical copy. What the 2026 work added is the *inversion* — the automaton loaded from a
  data document. Both halves are MICS's; conflating them makes the claim harder to defend, not
  easier.
- **`check_determinism` is a load-time spot-check, not a proof.** It *calls* the predicates at
  `add_transition` time and reports a conflict only if both evaluate true then, and it swallows
  every exception and returns `False` (`FiniteDeterministicAutomaton.py:46-52`). Write *"conflicting
  transitions are rejected when detectable at load time"*, never *"provably deterministic."*
- **Adoption is light.** Of 157 task definitions, **27 have a non-null `fda_json`**; the
  highest-usage protocol steps have `task_definition_id IS NULL` and dispatch straight to a Python
  plugin class (`elastic_test` ×39 steps, `AppetitveTaskReal` ×14). Claim the capability; do not
  imply the lab has migrated.

### 3.2 Automatic event-level logging

**Mechanism.** `auto_log(cls)` (`logging_utils.py:8-12`) is a class decorator that re-binds every
non-underscore callable through `log_action`; `log_action` (`:15-99`) branches on the receiver and
emits a `Hardware_Event` (`event_type=self.hardware_type`, `level=int(self.hardware_state)`) or a
tracker `Event`. `Event_Dispatcher._sender_loop` then wraps it in a fixed envelope — `pilot,
subject, session, run_id, task_type, timestamp, continuous, session_progress_index, subjects`
(`Event_Dispatcher.py:38-49`) — with the timestamp taken as a pigpio tick **synchronously in the
calling thread** (`:77`) and the send queued to a daemon thread.

**Evidence.** `auto_log|log_action` → **0 matches, 518 files searched** over the extracted 0.4.4
tree. Autopilot's `core/loggers.py` is 175 lines of `RotatingFileHandler` debug logging that never
touches the ZMQ path; its scientific record is `node.send('T','DATA', <a row of the task's own
`TrialData`>)`, declared column by column by the task author. **The inversion is from *the task
describes its data* to *the instrument describes itself*** — and it is what makes the ES corpus
exist at all.

**The honest bound — this is the claim most likely to be over-worded.** `@auto_log` appears
**exactly once repo-wide**: `gpio.py:324`, on `Digital_Out`. `Digital_In` is undecorated. `i2c.py`
*imports* `log_action` at `:11` and uses it **zero times** — the licker itself is not
decorator-logged. Subclass overrides escape (`TTL.set`, `PWM.set`, `LED_RGB.set`,
`Pulse20Hz.start/stop`), as do underscore methods and properties. Inputs reach the record by a
**second** mechanism (`Task.execute_trigger` dispatching a `Hardware_Event` for every queued
trigger, `task.py:267-278`) and lick detection by a **third** (`learning_cage.detectedLick` writing
the View → `Tracker.set` is `@log_action`).

> **Defensible wording:** *"Output-driver methods are instrumented by decorator and input events by
> a single central handler, so the record is produced by the framework rather than declared by the
> task author."*
> **Indefensible wording:** *"All hardware events are logged automatically."* A reviewer who opens
> `gpio.py` finds one decorator.

Two corpus artefacts must be disclosed with it: the `*_and_notify` **double-emit**
(`mics_task.py:396-403,419-433,444-451,465-473` — any naive reward or LED-onset count is 2×) and
the **dual `event_type` vocabulary** (`hardware_type` `"gpio.Solenoid_mics"` from the auto-log path
vs `group` `"VALVE"` from the explicit path, `logging_utils.py:91` vs `mics_task.py:385`). Doc 14
correctly notes "two incompatible event vocabularies" as a corpus property; **this is its
mechanism**, and it is a code-level fact, not historical schema drift.

### 3.3 The trigger queue and the generator run loop

**The trigger queue is a correctness fix to inherited Autopilot code**, and it is the most concrete
engineering claim in the runtime section. B1 `task.py:279-306`:

```python
unlocked = self.trigger_lock.acquire(blocking=False)
if not unlocked:
    self.logger.debug('Trigger called, but trigger lock has not been released …')
    return                      # ← the trigger is DISCARDED
...
self.triggers[pin]()            # fire
self.triggers = {}              # ← every other armed trigger is ALSO discarded
```

Two independent losses: triggers arriving under contention are dropped, and after one fires the
whole trigger table is wiped. For a home-cage rig where a mouse can lick, break an IR beam and trip
a touch sensor within milliseconds, both are data loss. `c632674` replaced this with
`self.event_queue = queue.Queue()` + a daemon `process_queue` worker (`task.py:129-133,254-266`),
and `handle_trigger` became one line: `self.event_queue.put((pin, level, tick, hardware))`
(`:373`). Nothing is dropped; everything is serialised in arrival order. `event_queue` occurs
**0 times** in 0.4.4.

**The generator run loop.** `23e6bf7` rewrote `run_task`'s body to detect
`isinstance(result_obj, types.GeneratorType)` and consume it with a `self.running` check
(`pilot.py:1188-1197`), so a state can be aborted mid-execution. Autopilot's stage method is
atomic: once entered it must return. `import types` was added by that very commit.

**The honest bound.** (i) `process_queue` has **no exception boundary** — anything escaping
`execute_trigger` kills trigger processing for the rest of the run, which the code's own docstring
flags as deliberately open. (ii) The queue is unbounded; the FDA only *prints* a warning when it
notices a backlog (`FiniteDeterministicAutomaton.py:84-86`). (iii) The generator loop's partner,
`wait_for_condition`, is a **500 µs busy-poll** (`mics_task.py:482-495`) that trades CPU for
interruptibility where Autopilot's `Event.wait()` cost nothing while idle. That 500 µs is the
actual state-latency floor of the FDA — own the number rather than implying "event-driven".
(iv) Autopilot's `stage_block` is not "kept" — it is dead (`task.py:119` `= None`; `pilot.py:1227`
and `task.py:307,402` commented). Say *"structurally preserved, semantically re-based"*, not
*"untouched"*.

### 3.4 View / Tracker / flags

**Mechanism.** `View` (`core/View.py`, 44 lines) is a `dict[str, object]` plus one reader:
`get_value(name)` → `self.view[name].get_state()` (`:43-44`). Three kinds of object end up in it —
raw `Hardware` inserted by `Task.init_hardware` (`task.py:204`), `Tracker`s for detector channels
(`mics_task.py:365`), and `Tracker`s for GUI-declared flags and variables (`:379`). All three
answer `get_state()`. `FLAGS` + `init_flags()` (`mics_task.py`, `17489dd`) declare the task's own
boolean state in the same namespace.

**Why it is load-bearing despite being a dict.** The contribution is not the code — it is the
**invariant**: every quantity a transition may read has (i) a string name, (ii) a synchronous
non-blocking read, and (iii) — because every writer is `@log_action`-decorated — a logged write.
That is precisely what allows an FDA condition to be *data* (`{"view": "LICKER2"}`,
`mics_task.py:647-651`) instead of a Python lambda over hardware objects, which in turn is what
allows the backend to validate a transition before dispatch (`view_key_unresolved`,
`variable_never_written`, `state_wait_unsatisfiable`). **Remove `View` and the GUI-authored FDA
cannot exist.** Autopilot has no equivalent at all — its answer is "read the hardware object
directly inside your Python stage method."

**The honest bound.** The uniformity is *not enforced*: `self.view.view` is a plain dict holding
raw `Hardware` objects whose `.set()` can physically actuate a device, and `mics_task.py:855-861`
is a runtime guard documenting exactly that hazard — a patch over a missing type boundary.
`get_value` has no `KeyError` handling. Reads are **unsynchronised** (trigger callbacks write on
the worker thread while `wait_for_condition` polls on the stage thread); correctness rests on
CPython dict atomicity, not a lock. And `Mics_Tracker.__init__` is missing `self`
(`Mics_Tracker.py:2-4`) — dead-wrong code sitting in the logging system's type-dispatch spine.
The right posture: *yes, it is a dict, and that is a virtue — it is the cheapest possible
implementation of the invariant that makes the FDA a validatable data structure.*

### 3.5 The relational + event-stream data model replacing per-subject HDF5

**Mechanism.** 28 Postgres tables (`api/models.py`; two also created by raw SQL at
`api/db.py:176,299`) split into a colony/science domain (12, SQLModel) and a rig/execution domain
(16, SQLAlchemy). Elasticsearch `event_log_v2` receives one document per event, envelope-stamped
per §3.2. The Pi writes to no database — its sole egress is ZMQ.

**What was displaced, and when.** Two separate events, sixteen months apart. `490121e` (2024-12-31)
commented out the Pi's local `local.h5` write; `53f86ab` (2026-04-29) commented out
`self.node.send('T','DATA',data)` (`pilot.py:1210`). Verified by a per-ref sweep of 30 commits: the
`DATA` send is **live at every one of them**, including `5704cb5`, and first commented at
`53f86ab`. So *"MICS replaced HDF5"* is true of today and false of the version the lab ran for most
of 2025 — and during that period the lab was still *maintaining* the HDF5 writer (`cca9c4f`,
2025-09-14, adapted `subject.py`'s trial branch to the new MICS event envelope). "Replaced" is
right; **"removed" is not** — `subject.py`'s writer is still live code reachable from the Qt
Terminal, and `import tables` at `pilot.py:24` remains a hard startup dependency of a file that
writes no HDF5.

**The honest bound.**
- **There is no trial table and no trial document.** Trial *boundaries* are recoverable
  (`Trial_Tracker.increment` emits a `CONTINUOUS` doc); the trial as a record with outcome columns
  — correct/incorrect, choice, reaction time, stimulus identity — is recorded nowhere, and every
  analysis begins by reconstructing trials under a definition that lives in analysis code rather
  than in the data. Concede this **first**, then make the completeness case.
- **The `subject` field in ES is a run key, not an animal**: `bp_s{session_id}_r{run_id}`
  (`main.py:1375`). The animal is in the `subjects` list. Anyone reusing the corpus will read it as
  an animal ID. Document it or rename it.
- **The dual-ORM seam is a scar, not a design.** `SubjectProtocolRun.session_id` is a bare int with
  no FK (`models.py:75`), as are `Subject.lead_researcher_id` (`:56`) and
  `ProtocolStepTemplate.task_definition_id` (`:107`). **The most important join in the system —
  session ↔ subject — is not enforced by the database.**
- **"A simple query finds all experiments for a subject" does not survive contact with the schema.**
  There is no `subject_experiments` table; the membership path (`subjects ⋈ subject_projects ⋈
  projects ⋈ experiments`) returns the *projects'* experiments, and **no endpoint exposes it** —
  `GET /subjects/{id}/detail` (`main.py:512-547`) returns projects, not experiments. Pick a
  different illustration; the underlying contrast (in Autopilot the question is *unaskable*) still
  wins the axis decisively.

### 3.6 Hardware drivers and configuration as versioned database artifacts

**Mechanism.** `hardware_lib_versions` rows carry `version_number`, `source_code`, `sha256_hash`,
`state ∈ {unvalidated, beta, stable}`, `ast_metadata`, `declared_imports`, `stable_at`,
`stable_reason ∈ {user, protocol_run}`, `stable_pilot`, `validation_error` (`models.py:639-655`).
Upload is gated by `ast.parse` + `py_compile(doraise=True)` (`hardware_libs.py:91-107`) and the AST
structure becomes what the task editor offers. Resolution is centralised in one implementation:
`pin → toolkit_default → stable → active → none` (`lib_version_resolution.py:33-92`), with
`lib_version_unresolved` blocking at preflight. Dispatch embeds `class_name` + `source_code` in
START (`toolkit_dispatch.py:36-122`), the orchestrator sends `LOAD_HARDWARE_LIBS` first
(`orchestrator_station.py:925-968`), the Pi writes them to `~/apps/hardware_overrides` and
`sys.path.insert` (`pilot.py:36-46`), and `mics_task._resolve_hardware_classes` `exec`s each source
into a fresh namespace (`:206-231`). `_merge_prefs_hardware` (`:233-252`) then **replaces whole
prefs groups** — the backend is authoritative. The Pi round-trips a real `importlib.import_module`
result back as `HARDWARE_LIB_TEST_RESULT` (`pilot.py:680-691`).

**What is strong and should be claimed:** per-version sha256; immutable version rows;
rollback-as-new-version rather than mutation; a real on-Pi import test bound to a `version_id`; one
resolution implementation (whose docstring documents the exact bug of having had two divergent
copies); and 11 machine-checked preflight kinds. Against Autopilot — where a driver is a file on
eight Pis and *nothing anywhere records which one ran* — this is a genuine, large advance.

**The honest bound, and it is the paper's most dangerous over-claim.**
- **`session_runs` has no version column and there is no run↔version join table.** Its 12 columns
  are `id, session_id, pilot_id, subject_key, status, started_at, ended_at, error_type,
  error_message, mode, overrides, session_run_index`. What is recorded is **the resolution
  policy**, not the resolution. Reconstructing what ran means replaying the chain against
  `stable_version_id` / `active_version_id` / `toolkit_hardware_libs.default_version_id` /
  `task_definitions.hw_lib_versions` — **all mutable after the run**. Promote a new stable and
  yesterday's run silently re-resolves to different source. **Defensible sentence:** *"the
  resolution is deterministic and the pin is recorded on the specification"*, not *"recorded
  against the run."* **F2 fixes this with one column.**
- **`stable_reason='protocol_run'` means less than the label suggests.**
  `promote_active_hw_libs_to_stable` is called from the **`INC_TRIAL_COUNTER` handler**
  (`orchestrator_station.py:599-614`) — i.e. on *every trial increment*, not at run completion —
  and `mark_stable` promotes `lib.active_version_id` (`hardware_libs.py:541-563`), **not** the
  version that was dispatched for this run. Upload a new version mid-session and the newly active
  one is stamped `protocol_run` on the next trial, credited with a run it never participated in.
- **The `exec()` is unsandboxed.** `mics_task.py:222` runs arbitrary database-sourced Python on the
  rig; the upload gate is a *syntax* check. Anyone who can POST a hardware lib gets code execution
  on every Pi running a toolkit that uses it. Belongs in limitations, not claims.
- **The DB's initial content came from the file it replaces** — `pilot_hardware_config` is seeded
  from the Pi's `prefs.json` at HANDSHAKE (`orchestrator_station.py:140-142`).

### 3.7 Task authoring without code, and one task on multiple rigs

**Mechanism, verified end to end.** Author on a react-flow canvas → `POST/PUT /task-definitions`
runs `reject_if_hard_errors` (`fda_validation.py:300-331`, five passes against closed
vocabularies, 422 on hard failure) *before* writing → orchestrator resolves the toolkit, injects
`HARDWARE`/`PREFS_HARDWARE`/`FLAGS`/`PARAMS`, sends `LOAD_HARDWARE_LIBS`, then START with
`task["state_machine"] = fda_json` → the Pi builds the automaton. Action dispatch is a **closed
8-branch table** and operators a fixed 6-entry map; every unrecognised value raises `ValueError`
**at load time**, not mid-run. **The FDA path contains no `eval`.**

Multi-rig portability rests on four mechanisms: `SEMANTIC_HARDWARE` resolved per-class and merged
across the MRO so a subclass cannot shadow a parent (`mics_task.py:1117-1139`), with
per-definition overrides; per-pilot `pilot_hardware_config` keyed `(pilot_id, name)`;
driver classes shipped from the DB; and detector view keys derived from that pilot's declared
`first_channel` + `num_detectors` so `LICKER0..3` on one rig and `LICKER4..7` on another both
resolve.

**The honest bound — two sentences the manuscript must absorb.**
1. **"No code" is precise only for state-machine composition.** The primitive layer is Python, and
   the system ships a **CodeMirror Python editor in the browser**
   (`HardwareLibDetail.tsx:4-6,236-243`) whose output the Pi `exec`s. **That relocates the coding
   into the browser; it does not eliminate it.** Defensible: *"composing and modifying task logic —
   states, transitions, conditions, actions, variables — no longer requires writing or deploying
   code; authoring a new hardware primitive still does."* A **Python class must also still exist on
   the Pi** to be the `task_type` (`toolkit_dispatch.py:143,149` falls back to `mics_task`), and
   `pilot/plugins/` holds 28–29 hand-written task files.
2. **"The same task runs on multiple rigs with zero code change" must be scoped to fully GUI-built
   definitions.** Five named ways it still breaks: passthrough states, whose behaviour is a Python
   method on *that Pi's* class (`mics_task.py:906`); `CALLABLE_METHODS`, which fails at load with
   `ValueError` if the target class does not whitelist the name (`:914-919`); detector channel keys,
   where a different electrode count or device name yields different view keys; non-`Modules`
   hardware reachable only through a semantic alias (`:1141-1146`); and rename maps that only work
   forward and only if maintained. Also: `check_for_detectors` raises `ValueError` at task
   construction if `read()` returns fewer channels than declared (`:351-357`) — a failure at
   construction, not at preflight.

Measured over the live database, most stored FDAs are still name-lists over Python methods
(definitions 124, 155, 157 are 100 % passthrough); definitions **179 / 181 / 185** are the genuine
zero-Python demonstrations. Be precise about which experiments were run which way.

### 3.8 Pre-dispatch static validation, including the deadlock detector

**Mechanism.** `PREFLIGHT_ISSUE_KINDS` (`toolkit_dispatch.py:155-167`) holds **11** kinds;
`compute_lib_import_failed` is explicitly RESERVED and never emitted (`:170-179`), so **10 are
emittable**. Four are existence/equality checks (`missing`, `incomplete_config`, `class_mismatch`,
`lib_version_unresolved`); two are name resolution over the task graph (`fda_ref_unresolved`
`:415-439`, `view_key_unresolved` `:447-474`); two are runtime/field checks (`device_held`,
`extlink_config_invalid`); and **two are real static analyses**:

- **`variable_never_written`** (`api/variable_scan.py`) walks every state's `entry_actions` *and*
  `trigger_assignments`, recursing into `if`/`then`/`else` (`:39-62`), collecting writers from
  `output` slots, `flag` actions and non-null `initial_value`. **Its own docstring (`:4-13`) states
  the narrowing: this is an *existence* check, not graph reachability.** Quote that self-limitation
  rather than paper over it — it is evidence of disciplined engineering and it pre-empts the
  reviewer who would otherwise find the gap. (Doc 15 C7's "a variable nothing **upstream** writes"
  must lose the word "upstream".)
- **`state_wait_unsatisfiable`** (`api/wait_analysis.py`) is the strongest single item in the whole
  audit. `entry_actions` run once on entry, so a wait condition reading a variable those actions
  wrote can never change. The pass computes each state's entry-frozen write set, then requires that
  **every** outgoing transition be blocked by a frozen comparison, descending only AND branches (an
  OR can be satisfied elsewhere) and exempting complementary operator pairs (`>=`/`<`, `>`/`<=`,
  `==`/`!=`) so a legitimate probabilistic branch is not reported. A **sound, deliberately
  conservative deadlock detector**, and its docstring names the real in-the-wild incident it was
  written for: **task def 186, run 541** — `rand` drew `my_rand` on entry, the only exit required
  `my_rand >= 0.5`, and every low draw parked the task permanently while the pilot went on logging
  licks.

**Autopilot's side, verified twice:** `toggle_start()` (`terminal.py:516-573`) prompts for a
weight, calls `prepare_run()` and sends `START`. A regex for `valid|verif|preflight|precondition`
over `git show 30c8d3c:…/terminal.py` returns **exit 1, zero matches**. Autopilot has no pre-run
validation and no expressed intent to add one.

**The honest bound — and it is a code bug, not a wording problem.** **Preflight does not block.**
`HardwareCheckModal.tsx:551` renders an always-enabled *Save & Start*;
`PilotSessions.tsx:100-102` catches a preflight *network error* with the comment *"proceed with
start"* and falls through to `doStart`; and there is **no server-side re-check** on the start path
(`web_ui/app.py:244-280` goes straight to `POST {ORCHESTRATOR}/runs/{id}/start`). The orchestrator
concedes it in its own comment: *"Never fatal: preflight already gated this run… never block a run
preflight cleared"* (`orchestrator_station.py:387-388`). Defensible today: **"MICS performs static
analysis of the task graph before dispatch and surfaces provable deadlocks to the operator."**
See **F1**.

### 3.9 Run modes and multi-subject sessions

**Run modes.** `SessionRun.mode` (`models.py:461`, default `"new"`) dispatched at `main.py:1268`
(resume: reuse the row, keep `run_progress` and `session_run_index`), `:1281` (restart: new row,
**same** index, overrides inherited) and `:1312` (new: fresh row, `run_counter` incremented,
overrides *not* inherited). The non-obvious correctness decision worth a clause:
`_strip_graduation_from_overrides` (`main.py:1577-1605`) deletes any inherited `graduation` key, so
a re-run never silently inherits a stale criterion.

**Multi-subject sessions.** `_start_session_for_pending_subjects` (`main.py:783-842`) allocates
**one** `session_id` and one `SubjectProtocolRun` per subject; `session_runs` attaches N executions
to it, each on its own pilot, each with an index allocated under `SELECT … FOR UPDATE`
(`main.py:1330-1337`); and the `subjects` list is stamped onto **every ES document**, so cohort
membership is recoverable from the event stream alone.

**The honest bound.** The contrast is **not** "impossible in Autopilot" — `Terminal` holds a dict
of concurrent `Subject` objects and running four animals at once was routine. What does not exist
in Autopilot is any entity that *groups* them: `session` is a private per-subject integer in
`/info._v_attrs`, so mouse A's session 5 and mouse B's session 5 are unrelated. **Claim the session
as an entity, never the concurrency.** And Autopilot's `resume` equivalent should be stated
generously: because `step` and `session` live in the file rather than in memory, Autopilot resumes
*by construction* and never loses progression to a crash. MICS's advance is that the lifecycle is
**modelled and queryable**, not that state survives at all.

---

## 4. What we genuinely rely on from Autopilot

This section is deliberately unsparing. Each item is a distinctive Autopilot artifact MICS depends
on and did not build.

### 4.1 The vendored package is a hard code dependency and an MPL-2.0 obligation

The tree at import was **vanilla 0.4.4** — `node.py`, `station.py`, `task.py`,
`hardware/__init__.py`, `gpio.py` all 0-diff against the PyPI sdist, `pilot.py` and `terminal.py`
+4/−1 each. MICS then modified upstream files **in place**. MPL-2.0 is **file-level** copyleft:
those files must keep their notices and ship under MPL. This is a legal fact, not a positioning
choice, and it is visible at code release regardless of what the manuscript says.

**The complete list of modified upstream files** (vanilla → today; the old docs name four):

| File | churn | live on the MICS path? |
|---|---|---|
| `core/pilot.py` | +501/−41 (823→1,283) | yes |
| `hardware/gpio.py` | +361/−83 (1,438→1,716) | yes |
| `hardware/i2c.py` | +179/−3 committed; +197/−3 incl. working tree | yes |
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

### 4.2 The forked pigpio — MICS's entire timebase

`autopilot/requirements/requirements_pilot.txt:18` pins
`pigpio @ https://github.com/sneakers-the-rat/pigpio/tarball/master` — Autopilot's own author's
fork — and the line is **identical at `30c8d3c`**. `README.md:130` states the purpose:
*"Timestamps from GPIO events are now microsecond-precise thanks to some modifications to the pigpio
library"*, echoed at `gpio.py:7` (*"returns isoformatted timestamps rather than tick numbers in
callbacks"*) and `gpio.py:790`. `synchronize()` and `ticks_to_timestamp()` are **that fork's API**:
neither name appears anywhere in either repo except as call sites in `Event_Dispatcher.py`, and no
`pigpio.py` exists on disk to grep.

So Autopilot supplies **tick ↔ wall-clock alignment within one Pi, at microsecond resolution**.
MICS adds the *call* (`pigpio.pi(sync_ticks=True)` + `self.pi.synchronize()`, `pilot.py:1139,1145`)
and, genuinely, the *event stream to put it in* — but not the capability. **This must be credited
loudly, and doc 15 C8's "Autopilot has no clock synchronisation … searched 0.4.4" must be struck.**
That search covered the Python package, not its pinned dependencies.

### 4.3 `gpio.py` and its pigpio stored-script waveform layer

1,438 lines of tested pigpio drivers, ~94 % of the original lines retained. The specifically
non-obvious part is `Digital_Out._series_script` / `store_series` / `series` / `_stop_script`
(`gpio.py:519-793`), which compiles a waveform into a **pigpio stored script** so the pulse train
runs in the pigpio daemon, entirely off the Python GIL. `Solenoid.open` (`gpio.py:1632`) and
`Pulse20Hz._build_script` (`:1691-1706`) both ride on it; **MICS added ~0 lines to this machinery
and would have to reinvent it.** Name this, rather than ceding "hardware abstraction" wholesale —
the abstraction is generic (§5), the timing layer is not.

### 4.4 `Pilot_Station` / `Net_Node` / `Message` — byte-identical on both ends

`message.py` and `node.py` are byte-identical to 0.4.4 on the Pi, and `message.py` is byte-identical
again in `mics-backend/orchestrator/orchestrator/networking/`. The Pi genuinely runs unmodified
`Station.push` (`station.py:384` `send_multipart([push_id, msg.to, msg_enc])`) and unmodified
`handle_listen`, so `RouterGateway.py:16`'s self-description — *"speaks legacy Pilot_Station
format"* — is an accurate statement of a live dependency, not a stale comment. **Doc 14 §1c is the
best-evidenced section in the four documents and should be kept.**

**One qualification the old docs miss: the dependency is shallow.** MICS uses only `key`, `value`
and two flags. No ndarrays, no multi-hop `routes`, no `expand_arrays`. Replacing the envelope would
touch three Pi files the lab has already shown it will patch plus two methods in `RouterGateway` —
roughly a day. **Convenience, not lock-in.** Say "we run Autopilot's networking layer unchanged",
not "we build on Autopilot's messaging architecture."

### 4.5 The `flags` protocol

`NOREPEAT` / `NOLOG` / `MINPRINT` (`message.py:35-40`) — per-message opt-out of ack and of logging,
so a high-rate stream does not drown the logger or the outbox. Small, but genuinely thoughtful, and
**MICS depends on both today**: the 5 s state ping carries `{'NOLOG': True}`
(`station.py:1106,1154`) and `RouterGateway` honours `NOREPEAT` on both paths (`:152,192`). Neither
old doc mentions it.

### 4.6 Transparent ndarray compression (credit, do not claim)

`json.dumps(msg, default=self._serialize_numpy)` + `json.loads(…, object_pairs_hook=…)`
(`message.py:76,265`) with base64'd `blosc.pack_array` (`:167`) makes a video frame a first-class
message value with no caller ceremony, and `expand_arrays=False` by default (`:75-78,178-184`)
defers the expensive decompression. This is the non-obvious design idea in `Message`. **MICS never
sends an ndarray** — we inherit the code and none of the value. Credit it in one clause and move on.

### 4.7 The plugin registry is still on the live task-resolution path

Doc 14 §2.3 contrasts *"driver code lives on the Pi, imported by `utils/plugins.py` | MICS — in
Postgres"*. That is true of **hardware libraries only**. Task classes still resolve through
Autopilot's registry: `autopilot.get_task(class_name=None, plugins=True, ast=True)`
(`pilot.py:526`, the HANDSHAKE introspection that populates the backend's own task catalogue) and
`autopilot.get_task(value['task_type'])` (`:593`, the START path), against **28 files** in
`pilot/plugins/`, with `prefs.json AUTOPLUGIN=true`. Legacy hardware groups (`GPIO`, `I2C`,
`Timers`, `Mixer`, `UNREAL`) likewise still resolve via `autopilot.get_hardware(handler_string)`
from prefs (`task.py:182-184`). **Delete `utils/plugins.py`/`registry.py` and no task starts.**

Correct sentence: *"driver code for backend-managed modules is delivered from the database; task
classes and legacy hardware groups still resolve from the Pi's plugin dir and prefs."* Anything
stronger is falsifiable in one grep.

### 4.8 Local executor autonomy

Autopilot's founding commitment is that the Pilot is **not a dumb worker awaiting instructions** —
it owns its task for the duration and keeps running when the coordinator dies. MICS inherits
`core/pilot.py` essentially intact and gets this property for free. It is a real design
contribution, distinct from the generic coordinator-plus-workers *topology* (§5), and it is what
the manuscript should credit when it means "C1". Note that Autopilot backed this commitment with a
local `local.h5` mirror that MICS disabled — see §4.11.

### 4.9 The `self.stages` contract and the execution driver

The FDA implements `__iter__`/`__next__` purely so Autopilot's `next(self.task.stages)()` keeps
working; delete those two dunder methods, add `self.stages.step()`, and the FDA is unchanged. So the
contract is thin — **one line**. But the honest reading cuts the other way too: **MICS never had to
design an execution driver.** `run_task` — the thread, the loop, the exception boundary, the
`finally` that calls `task.end()` and clears pigpio scripts — is Autopilot's, and the FDA slotted
into it because Autopilot's contract was permissive enough. A real, if modest, benefit.

### 4.10 `TrialData` / `History_Table` / `past_protocols` — a genuine design→execution→data thread

`PARAMS` is rendered as the Terminal's parameter form; `TrialData` declares the schema the trial
table is built from, with `session` and `trial_num` auto-injected and stimulus parameters
synthesised into columns (`subject.py:499-531`); `History_Table` records every protocol, parameter
and step change with a timestamp; and `past_protocols` **archives** superseded protocol JSON rather
than overwriting it (`subject.py:584-610`). The graduation plumbing is careful in a way worth
naming: it trims the history it feeds the criterion to trials *after the last step change*
(`:656-682`), so a subject stepped back down is not graduated by stale data.

**MICS has no equivalent of `past_protocols` — `protocol_templates` rows are mutated in place.**
Volunteering that makes the rest of the "one representation" argument unassailable. The right
framing (doc 14 §7.3, keep it) is **template vs contract** and the two words **scope** and
**enforcement**, not "we have a unified representation and others don't".

### 4.11 `Accuracy` graduation, and the inherited `current_trial` semantics

`tasks/graduation.py:40` `class Accuracy(Graduation)`, defaults `threshold=0.75, window=500` at
`:48`, `NTrials` at `:96`. MICS evaluates only `NTrials` (`api/main.py:1750`). Calibrate the
concession accurately: `Accuracy` is 50 lines and cannot fire before 500 trials at its default
window — **real and configurable, not a sophisticated controller.** Do not over-dramatise the loss;
do not claim the reverse.

**The non-obvious debt underneath it**, which the old docs miss because it looks like MICS's own
code: Autopilot's `NTrials.__init__(n_trials, current_trial=0)` documents `current_trial` as *"If
not starting from zero, start from here"* — a **resume offset**. MICS reads the same key as the
**threshold** (`main.py:1752`), and its precedence chain prefers `current_trial` over `n_trials`
(`:1646-1654`). So an Autopilot-shaped protocol resolves to `n = 0`, fails `n_required > 0`, and
**never graduates**. Inherited name, inverted meaning. Worth a line in Methods and worth fixing in
the schema (**F6**).

### 4.12 `transform/` + the `Transformer` child — the finding most likely to save the manuscript

`tasks/children.py:179` plus nine to ten `transform/` modules. Autopilot shipped a **networked
closed loop** — camera → transform pipeline → `TRIGGER` back to the requesting node, or continuous
stream — **and** in-process on-Pi computation, in 2022. Verified unused in MICS: the only reference
to `children` in the tree is the registry string at `utils/registry.py:42`, and `prefs.json` sets
`LINEAGE="PARENT"` with no children configured.

Doc 15 C8's warning — *"do not imply that external computation influencing task flow over a network
is new"* — is the single most useful sentence in the four documents. **Keep it verbatim.** MICS-Link
is more *general* (a foreign publisher needs no MICS code, only a `@decoder`) but strictly more
expensive: MICS's answer to "process a video frame" is another computer, which adds a hop and a
clock domain. **Claim generality, not novelty.**

Note the required precision (§2.3): `transform/` is unused as a *capability* but is a **hard import
dependency** — `i2c.py:9` imports `IMU_Orientation`/`Spheroid` at module scope. The same is true of
`cameras.py`, whose `Camera` class is the base of `MLX90640` (`i2c.py:8,580`). Do not describe
either as removable.

### 4.13 `stim/sound` — jack/pyo

`stim/sound/jackclient.py`, `pyoserver.py`, configured at `FS=192000`, `ALSA_NPERIODS=3`,
`-p16`, realtime priority 75, HiFiBerry DAC. MICS sets `AUDIOSERVER=false` and uses pygame
`mixer.init(buffer=1024)` (`mixer.py:19`). §6 states the numbers.

### 4.14 Live per-trial plotting

`core/plots.py`, 1,109 lines. `Plot` (`:129`) opens **its own `Net_Node` with identity
`P_{pilot}`** (`:231`) and receives `START`/`DATA`/`STOP` **directly from the Pi** — it is a peer on
the network, not a view over the Terminal's memory. On `START` it reads
`autopilot.get_task(task_type).PLOT` and instantiates the declared primitives (`Point`, `Line`,
`Segment`, `Roll_Mean`, `Shaded`) plus a chance line and optional video. **The task declares how it
should be visualised and a live per-trial plot appears with zero configuration.** MICS has nothing
comparable in 84 TS/TSX modules. Concede it in the same paragraph that claims a monitoring
improvement — the concession is what makes the claim credible. Also lost with it: water-port
calibration with results shipped back to the Pi, bandwidth test, weights table, batch protocol
reassign, video stream.

---

## 5. What is merely generic

These are the items the old docs conceded to Autopilot that should be conceded to **nobody**. Two
tests decide each: **(i)** starting from a blank file with Python, ZMQ and pigpio, would a competent
implementation have arrived somewhere materially different? **(ii)** does every comparable
framework already have an equivalent (Bpod, pyControl, BControl, Bonsai, IntelliCage, any SCADA
stack)? Where the answer is *no* and *yes*, nobody owns it — and crediting Autopilot for it
**weakens** the credit MICS genuinely owes, because it makes the whole ledger look uncalibrated.

The load-bearing external fact: **Autopilot's own published claim (`CITATION.cff` at `30c8d3c`) is
about flexible hardware composition, timing performance and cost on a swarm of cheap Pis** — *"an
order-of-magnitude performance improvement … while also being an order of magnitude less costly to
implement"*. The Terminal appears in the README only as a row in a module table. **The
coordination topology is not Autopilot's thesis, and conceding it to Autopilot inflates its
contribution and cheapens the real one.**

| Conceded as Autopilot's | Should be | Reasoning that survives challenge |
|---|---|---|
| **C1 — "separation of local execution from central coordination … this *is* Autopilot"** (doc 15) | **GENERIC**, except for **local executor autonomy**, which *is* AUTOPILOT (§4.8) | "Autonomous nodes + a coordinator" is the oldest pattern in networked control — Med-PC, Bpod, IntelliCage and every SCADA stack have it. Autopilot's distinctive part is the *commitment* that the executor owns its task, plus the *specific Pi realization* MICS runs. Name that; do not hand over a design principle nobody owns. **Note doc 14 §5 and doc 15 C1 contradict each other on this; this is the adjudication.** |
| The **wire protocol as an idea** (doc 14 §2.1 "Unchanged … the frame layout, the envelope, the key-dispatch model and CONFIRM/resend semantics are Autopilot's") | **GENERIC idea / AUTOPILOT code** | Split the claim. Running *this literal serialization class on both ends* is a verified code debt and must be credited. That "a JSON envelope with `{to,sender,key,value,id}` plus an ACK" or "a `{key: handler}` dict" is an Autopilot *design contribution* is not defensible — every ZMQ daemon has both, and `Message.serialize()` is `json.dumps(self.__dict__)`. Tellingly, the `to`/`sender` fields are not even trustworthy routing: ZMQ's identity frame does the routing and `RouterGateway._on_recv` overwrites `msg.sender` from frame 0 (`:177-178`). |
| `init_hardware()` — construct devices from `HARDWARE` × prefs | **GENERIC** | It is a double `for` loop over two nested dicts calling a constructor and registering a callback (B1 `task.py:105-160`). Bpod's `BpodObject` builds its module list from a config; pyControl instantiates from a board-definition file identically. Not on Autopilot's own list of contributions. |
| The `Hardware` / `HARDWARE`-dict / prefs **abstraction** | **GENERIC** | You need a per-device object, a stable logical name so task code does not hardcode pin 35, and a per-rig file mapping name→pin. Forced by the problem. Bpod `PortArray`, pyControl board definitions, BControl `@hardware`, and `#define VALVE1 35` all land here. **What is Autopilot's is the pigpio stored-script timing layer inside it (§4.3) — name that instead.** |
| `{key: handler}` dispatch dict | **GENERIC** | The default shape of every message-driven program. MICS's own dispatch table is written fresh and merely names the same keys. |
| The daemon **shell** — parse prefs, init logging, init pigpio, spawn a networking thread, run the task in a thread | **GENERIC** | Generic daemon boilerplate. Note that doc 14's claim that the *loop* is "untouched" is separately **false** (§6). |
| **C11 — "Scaling: parallel stations"** (doc 15, ⊘) | **GENERIC idea / AUTOPILOT code** | Many clients, one server, is not an idea anyone owns. What *is* Autopilot's is that MICS never had to write the client. Say that; do not concede "scaling" as a concept. Doc 14 §5.7 already gets this right — make it load-bearing. |
| **C12 — "One architecture across paradigms … Autopilot designed and published for exactly this"** (doc 15, ⊘) | **MICS** — the ⊘ is a category error | **You cannot inherit versatility.** MICS's paradigm-independence comes from the FDA/toolkit model, which is MICS's own. That Autopilot is also general-purpose is a fact about a comparator, not a debt. Marking C12 "inherited outright" gives away a claim MICS earned. |
| Per-subject HDF5 file as the unit of persistence | **GENERIC** | The standard lab convention of 2015–2022. PyTables plus a `/data /history /info` tree is competent engineering, not a claimable invention — *and the parts that are genuinely Autopilot's (`TrialData` as schema authority, `History_Table`, `past_protocols`) should be conceded loudly instead, per §4.10.* |
| The `Accuracy` **criterion** | **GENERIC** | 50 lines of `deque` + `np.mean` (`graduation.py:40-93`). The AP part is the *substrate that feeds it* — the trial rows, the `COLS` injection, the step-change trimming. |
| The Qt Terminal **as a program** | **GENERIC**, and dead here | A desktop GUI holding a device list is not a scientific contribution. Its *placement on the data path* is the consequential design decision — and that is what MICS's contribution argues against, so MICS needs it stated as a *choice*, not as an invention. |
| 111 REST routes / React SPA / Docker / JWT | **GENERIC (MICS's own)** — *not a contribution* | "It's a web app now" buys remote access and concurrent viewing. Operationally valuable, scientifically uninteresting. A reviewer will make this point; the paper is stronger for making it first. |

---

## 6. Claims to drop, soften, or fix

**F1–F6 are flagged: each is a small code change that converts a currently-false claim into a true
one. These are the highest-value items in this document.**

| Claim as drafted | Status | Corrected wording, or the required fix |
|---|---|---|
| *"Periodic synchronization with a global reference enables alignment of events across experimental stations … onto a unified experimental timeline."* | **FALSE — drop** | Events from different rigs do **not** share a timeline. Each Pi's `synchronize()` anchors ticks to *its own* `time.time()`; NTP is commented out **in the commit that introduced it** (`a008046`; sites `pilot.py:1138,1148`); `localize_tz` stamps each host's local zone (`common.py:332`) while the backend re-stamps everything into one zone (`ElasticSearchDateHandler.py:48-51`), *hiding* per-Pi offsets; and `ROADMAP.md:496` says the machines are not NTP-synced to each other. **Write:** *"All events from a rig are stamped from a single, GPIO-derived clock, giving microsecond-resolution ordering within a rig; alignment across rigs or to external acquisition systems is achieved by a shared TTL pulse, not by network time synchronisation."* |
| *"Preflight hard-blocks a second run"* / *"validation that blocks dispatch"* (doc 14 §2.4, §5.5, §7.2; doc 15 C7) | **FALSE as coded** | **F1 — fix the code, ~20 lines:** re-run preflight inside `POST /runs/{run_id}/start` and return 409 on unresolved hard issues; disable `HardwareCheckModal.tsx:551`'s button while hard issues stand; stop `PilotSessions.tsx:100-102` falling through to `doStart` on a preflight error. Until then write *"MICS performs static analysis of the task graph before dispatch and surfaces provable deadlocks to the operator."* |
| *"The driver code that ran your experiment is a versioned artifact recorded against the run"* / *"versioned libs bound to runs"* (doc 13 §4.1; doc 14 §7.2, §2.3, scorecard) | **OVER-CLAIM — the most dangerous in the set** | **F2 — fix the code, one column:** write the resolved `{lib_id: version_id, reason}` map onto the `session_runs` row at dispatch; the orchestrator already holds it at `orchestrator_station.py:947-950`. Until then: *"the resolution is deterministic and the pin is recorded on the specification"*, **not** "against the run". Also stop describing `stable_reason='protocol_run'` as "earned by carrying a run" — it promotes `active_version_id` on every trial increment (§3.6). |
| *"Adaptive progression; trajectories can branch or depend on performance"* (C5, Table 1) | **DROP** | `api/main.py:1750` evaluates only `NTrials`. Autopilot has `NTrials` **and** `Accuracy`. **Claimable instead:** progression is evaluated and stored **per subject** in a queryable relational model with explicit `new`/`resume`/`restart` modes; and MICS is strongly adaptive **within** a session (compute ops, variables, nested conditions) where Autopilot's adaptivity is across sessions. **F3 — fix the code:** at minimum, 422 on a non-`NTrials` `graduation_type` at `_coerce_graduation` (`main.py:1607-1660`) so a step cannot be silently inert. |
| *"Autopilot has no clock synchronisation. No NTP, no tick alignment, nothing (searched 0.4.4)"* (doc 15 C8) | **FALSE, and flattering to us — strike it** | Autopilot ships a forked pigpio (`requirements_pilot.txt:18` at `30c8d3c`; `README.md:130`; `gpio.py:7,790`) giving µs-precise, isoformatted GPIO timestamps plus `synchronize()`/`ticks_to_timestamp()`. **Write:** *"Autopilot provides within-station tick↔wall-clock alignment and no cross-machine synchronisation."* And MICS *"wires Autopilot's pigpio clock into a per-event stream Autopilot has no equivalent of."* |
| *"Sample-accurate / low-latency audio"* (implied) | **DO NOT IMPLY** | pygame `mixer.init(buffer=1024)` at 44.1 kHz ⇒ ~23 ms/buffer, SDL queues ≥2 ⇒ **~23–46 ms**, vs Autopilot's configured `-p16` at `FS=192000` ⇒ ~0.083 ms/period at RT prio 75. Worse for jitter: `AUDIO.set` **loads and decodes the WAV from the SD card inside the cue call** (`mixer.py:25-27`), and audio-off is a `threading.Timer` (`:33-34`), not the sample end. For a 150 ms tone this is fine; quote a measured number, never a derived one. |
| *"Autopilot's process model … `while True: next(self.task.stages)()` … is untouched"* (doc 14 §1b) | **FALSE in substance** | The silhouette survives; the body does not. `23e6bf7` rewrote it to detect `types.GeneratorType` and abort mid-state on `self.running` (`pilot.py:1188-1197`), and `pilot.py:1227` is `# self.stage_block.wait()`. **Write:** *"structurally preserved, semantically re-based"* — and credit the rewrite as MICS's. |
| *"MICS keeps the contract (`self.stages` yields callables; `stage_block`)"* (doc 14 §2.2) | **FALSE for `stage_block`** | `task.py:119` `self.stage_block = None`; `mics_task.py:104` swallows the kwarg; `task.py:307,402` and `pilot.py:1227` all commented. **Delete `stage_block` from the sentence.** The surviving contract is exactly *"`self.stages` is an iterator of zero-argument callables"* — one line, and worth saying it is one line. (`mics_task.py:1553`'s docstring still claims otherwise and probably seeded this error — fix the comment too.) |
| *"No code is required to write a task"* | **SOFTEN** | Precise only for state-machine composition. A **CodeMirror Python editor** ships in the browser (`HardwareLibDetail.tsx:4-6,236-243`) and its output is `exec`'d on the Pi (`mics_task.py:222`); a Python class must still exist on the Pi to be the `task_type`. **Write:** *"composing and modifying task logic no longer requires writing or deploying code; authoring a new hardware primitive still does."* |
| *"The same task runs on multiple rigs with zero code change"* | **SCOPE IT** | True of fully GUI-built definitions. Five named failure modes: passthrough states, `CALLABLE_METHODS`, detector channel keys, non-`Modules` name resolution, unmaintained rename maps (§3.7). |
| *"All hardware events are logged automatically"* / *"the driver methods themselves"* (doc 14 §2.5; doc 15 C6) | **SOFTEN** | `@auto_log` appears **once** (`gpio.py:324`). `Digital_In` is undecorated; `i2c.py` imports `log_action` and uses it zero times. **Write:** *"output-driver methods are instrumented by decorator and input events by a single central handler in `Task.execute_trigger`."* Disclose the `*_and_notify` double-emit and the dual `event_type` vocabulary alongside it. |
| *"MICS uniquely combines … a provably deterministic state machine"* | **SOFTEN** | `check_determinism` calls the predicates at registration and swallows exceptions (`FiniteDeterministicAutomaton.py:46-52`). **Write:** *"conflicting transitions are rejected when detectable at load time."* |
| *"Multiple users can operate the facility concurrently"* / *"user identity"* on the pilot grid (C11; doc 12 §2.7; doc 14 §2.4, §5.6) | **DROP** | One shared service JWT with the payload discarded (`api/auth.py:20`); no busy-check on `POST /session-runs` (`main.py:1236-1345`) so **two users can start two runs on one pilot**; unauthenticated WebSocket (`web_ui/app.py:51`); zero planning-doc hits for `multi-user\|RBAC\|per-user`. `PilotLive` is exactly `{connected, state, active_run, updated_at}`. **Claimable:** concurrent *viewing*, remote access. |
| *"The Portal verifies compatibility with the assigned system **and subjects** (implant type, genetic indicators)"* (C7) | **DROP the subject half** | No subject-attribute check exists in any of the 11 preflight kinds; `implant` returns **zero** hits across `api/`, the React source and the planning docs; `Subject` (`models.py:31-63`) has no implant field. Say attributes are *recorded*; describe the check as over hardware, task references, view keys, variables, library versions and device availability. |
| *"The same Blueprint used in live experiments executes in the virtual environment"* (C10) | **DECIDE, don't reword** | `unreal.py`'s only consumer is the legacy `mics_cage_task.py` (`group_name='UNREAL'` at `:30`); backend-authored toolkits have no UNREAL group and no phase reconnects them, so the distance grows with every landed phase. No mock-event-stream generator was found. Options: demote to a supplementary figure describing a hardware-simulation harness for the legacy path; do the work; or cut. |
| *"MICS replaced Autopilot's HDF5 data model"* | **DATE IT** | Two disabling events sixteen months apart (`490121e` 2024-12-31 local HDF5; `53f86ab` 2026-04-29 the `DATA` send), and the writer was still being *maintained* in 2025-09 (`cca9c4f`). `subject.py` is still live code reachable from the Terminal and `import tables` is still a hard startup dependency. **"Replaced" is right; "removed" is not.** |
| *"Driver code lives in Postgres"* implying the plugin path was replaced (doc 14 §2.3) | **SCOPE IT** | True for hardware libs; **false for task classes** — `pilot.py:526,593` still resolve every task through Autopilot's registry against 28 plugin files. §4.7. |
| *"MICS inherited a weak transport and had to build its **own** FIFO egress queue in Phase 18 rather than fix it upstream"* (doc 14 §2.1) | **MISATTRIBUTION — delete or rewrite** | Phase 18's `EgressWorker` (`external_hardware_runtime.py:14-102`) is **on the Pi**, serves **MICS-Link external devices** over a separate socket, and fixes none of the Autopilot transport's weaknesses. If a "MICS built its own queue" sentence is wanted, the referents are the `Event_Dispatcher` sender thread (`Event_Dispatcher.py:28-32`) and the trigger queue (`c632674`). |
| *"Each event is indexed with … experiment name"* (C6) | **DROP "experiment name"** | The envelope's mapped top-level fields are `continuous, event, pilot, run_id, session, session_progress_index, subject, subjects, task_type, timestamp`. `run_id` **is** there (doc 12 §2.4's original note was wrong and doc 13 §4.7 corrects it). Experiment name is not. **Methods caveat that must survive:** the analysed corpus (`restored-event_log_v2` on `.125`) has **no `run_id`** — name the index per figure. |
| *"A simple query finds all experiments for a given subject"* (C7 illustration) | **REPLACE the illustration** | No `subject_experiments` table; the membership path returns the *projects'* experiments; no endpoint exposes it (`main.py:512-547` returns projects). The underlying axis is still a decisive MICS win — pick a different example. |
| C1 / C11 / C12 attributions (doc 15) | **REVISE per §5** | Attribute **local executor autonomy** to Autopilot, not "central coordination"; keep C11 as inherited *code*, not an inherited *idea*; **reclaim C12** — versatility cannot be inherited. |
| Phase 18 in the future tense (all four docs) | **NOW FALSE — Phase 18 SHIPPED** | `STATE.md` (`last_updated 2026-08-09`): **COMPLETE, 15/15 plans**, six-run rig checkpoint (pilot 1 / session 115 / task_def 434, runs 552–556; 552/554/556 PASS). Corroborated live: `device_leases` exists as the 28th table (`api/db.py:299`); `device_held` and `extlink_config_invalid` are in `PREFLIGHT_ISSUE_KINDS`; five `external_hardware*.py` modules exist on the Pi. **But the caveats must survive the rewrite:** `sub_connect` (EXTLINK-14) and `role:"none"` (EXTLINK-18) remain **UNPROVEN on hardware** — `sub_connect` is exactly the transport Open Ephys needs, so the foreign-publisher path cannot be claimed; browser-picker authoring (EXTLINK-19) and the ~60 Hz soak (EXTLINK-20) are unproven; and a TCP echo listener must keep running on `132.77.73.125:5597` or `demo.alive` flips false. |
| The word **"fork"** throughout doc 14 | **REPLACE with "vendored dependency"** | The repo predates the Autopilot import by nine months and Autopilot was vendored *into* it (`4b28bd7` submodule → `30c8d3c` flattened, same day). Doc 14 §4's own conclusion *"Not a fork of Autopilot"* is correct while its repeated word *"fork"* invites the genealogy the history contradicts. |
| *"TTL provides cross-device alignment"* (implied by C8/C13) | **NOT DEMONSTRABLE TODAY** | **F5 — fix the config:** `learning_cage.py:85-86` declares `TTL1` but every driver call is commented (`:191`, `:208`; `mics_task.py:1594` likewise); only the legacy `mics_cage_task.py:424` still drives it. The one mechanism that could deliver cross-device alignment is wired and switched off in the live path. |
| Autopilot's row in Table 1 ("Partial" autonomous training, "Moderate" neural integration) | **STRENGTHEN Autopilot's row** | Understating your own dependency reads worse than understating a competitor. Autopilot has a plugin registry, on-Pi real-time transforms and networked closed-loop children. Also **disclose the dependency in the caption** — comparing a system to its own foundation without saying so is the highest-risk item in the manuscript. |
| *"a transition reading a variable nothing **upstream** writes"* (doc 15 C7) | **DELETE "upstream"** | `variable_scan.py:4-13` disclaims reachability explicitly — it is an **existence** check. The deadlock detector (`wait_analysis.py`) is the genuinely strong result and deserves the emphasis. |
| *"Autopilot's source says a 'coherence checking ritual' is a TODO"* cited as intent to validate (doc 15 C7) | **MISREADS THE TODO — drop it** | `terminal.py:565` sits in the *stopping* branch and concerns post-hoc data reconciliation. The cleaner statement: Autopilot has no pre-run validation **and expresses no intent to add one.** |
| — | **F4** | **`INC_TRIAL_COUNTER` as an FDA `special` action is a silent no-op.** `mics_task.py:786-789` sends `value={}` bypassing `Event_Dispatcher`; `orchestrator_station.py:588-590` returns early when `value.get("subject")` is falsy. Route it through `Event_Dispatcher` (or inject the subject). Until fixed, a Blueprint author can wire it, see no error, and get a run that never graduates. |
| — | **F6** | **Rename the graduation threshold key** from `current_trial` to `n_trials` in the schema and the precedence chain (`main.py:1646-1654,1752`). Removes an interop trap in which any Autopilot-shaped protocol JSON is silently inert. |

---

## 7. Corrections to docs 12–15

Every figure below was re-measured. Where the old docs' method is the likely cause, it is named.

### 7.1 Churn figures (doc 14 §1b)

| Doc 14 claim | Measured | Note |
|---|---|---|
| `core/pilot.py` **+415/−29**, *"only 29 of 823 original lines removed"*, *"~96 % surviving"* | **+501/−41**; 41 of 823 removed ⇒ **95.0 %** | 823 + 501 − 41 = 1,283 ✓ |
| `core/terminal.py` *"at import 997 → today 1,027, +38/−8"* | **at import 966 → today 997, +44/−12** | Both columns wrong: the doc's 997 is *today's* count shifted one column left. |
| `hardware/gpio.py` +294/−72 | **+361/−83** | |
| `tasks/task.py` 333 → **459**, +141/−29 | **333 → 427 committed, +125/−31**; **459 is the uncommitted working tree** (+157/−31) | The doc mixes a working-tree LOC with a committed-diff count. |
| `hardware/__init__.py` +32/−2 | **+44/−3** | |
| `networking/station.py` +37/−13 | **+47/−14** | |
| `hardware/i2c.py` filed under *"inherited … unmodified or lightly modified"* | **+179/−3 committed, +197/−3 with the working tree**, with four MICS classes (`MPR121`, `Motor_Shield_Hat`, `Motor_Shield_Hat_extend`, `Touch_Detector`) | `cameras.py` and `usb.py` really are +0/−0; grouping `i2c.py` with them misstates it. `usb.py` is also **dead**, not load-bearing. |
| *"The 29 removed lines are exactly the data path"* | 41 removed; ~29 are data path, the rest blank lines, two `logger.debug` calls, a `listens` entry, a `hello` dict line, a camera exception log — **and one is `stage_block.wait()`, which is not the data path at all** | `stage_block.wait()` is Autopilot's stage-advance concurrency primitive. List it separately. |
| *"~44 commented-code lines in `pilot.py`, 29 in `task.py`, 53 in `gpio.py`"* | **Not reproducible** — a naive regex gives 136 / 57 / 123 (it over-counts prose); Phase 30's own audit puts the whole-repo figure at 244 (`ROADMAP.md:40`) | Treat as unverified rather than wrong. |
| **Likely cause of the above** | The reproduction recipe mixes a **committed** blob (`30c8d3c:…`) with a `cat` of the **working tree**, silently folding in 39 uncommitted paths (incl. `log_value.py`, `fda_vocabulary.py`, five `external_hardware*.py`, +513 lines of `mics_task.py`) | Pin both sides to commits. |

### 7.2 Dead-code totals

- **"≈6,855 lines of upstream Terminal-side code carried but unused"** is wrong and understated.
  6,855 is exactly `terminal.py 997 + gui.py 3,350 + plots.py 1,147 + subject.py 1,361`, but the
  sentence sits under a list that also names `viz/`, `transform/`, most of `stim/` and six upstream
  task modules.
- **Adjudicated figure: ≈11,900 LOC across 35 upstream modules**, from an AST import-closure rooted
  at `core/pilot.py`, `tasks/{mics_task,learning_cage,task}.py`, `autopilot/__init__.py` and every
  file in `pilot/plugins/` (98 modules total; 59 reachable / 20,105 LOC, 39 unreachable / 12,171
  LOC, of which 4 modules / 253 LOC are MICS-added and dead). Audit 07 independently arrived at
  ≈14,000 by summing doc 14's own list; **prefer 11,900 because it has an explicit, reproducible
  method.**
- **Caveat, stated as such:** the closure is import-based, so it over-counts as "reachable"
  `hardware/cameras.py` (2,051), `transform/{geometry,timeseries,transforms}.py` (1,523) and
  `stim/sound/*` (1,266) — imported by reachable modules but not exercised by any MICS task. A
  call-graph analysis would push the dead total toward **~16,700**. **Honest range: ≈11,900 to
  ≈16,700.** 6,855 is definitely wrong.
- Largest single modules: `core/gui.py` 3,350 · `core/subject.py` 1,361 · `core/plots.py` 1,147 ·
  `core/terminal.py` 997 · `stim/managers.py` 615 · `tasks/test.py` 460 · `tasks/nafc.py` 458 ·
  `stim/sound/sounds.py` 445 · `hardware/usb.py` 358 · `tasks/children.py` 356.
- **A category the ledgers lack: MICS-added-but-dead** — `Data_Handler.py` (39),
  `ElasticSearchDataHandler.py` (63, importable only from the dead Terminal), `RecordingBox.py`
  (117), `utils/Event.py` (34, superseded by `Events.py`) = **253 LOC**.
- The doc 14 §1 dead list also omits `hardware/usb.py` (358), `stim/managers.py` (615),
  `stim/sound/sounds.py` (445), `stim/visual/*` (233), `setup/request_helpers.py` (124),
  `core/{reward,styles}.py` (152), `utils/invoker.py` (51).

### 7.3 Counts and line references

| Doc claim | Correct |
|---|---|
| "27 Postgres tables" (doc 14 §1, §2.4, §5.5; doc 15 C7) | **28** — the 28th is `device_leases`, created by Phase 18 on 2026-08-09 (`api/db.py:299`). 27 was correct on 2026-08-06. Split: 12 SQLModel + 16 SQLAlchemy; two are additionally created by raw SQL at `api/db.py:176,299`. |
| "Preflight: nine issue kinds, `toolkit_dispatch.py:153-163`" (docs 12, 13, 14, 15) | **11 kinds at `:155-167`**; `compute_lib_import_failed` is RESERVED and never emitted (`:170-179`), so **10 are emittable**. Doc 13 §4.6 lists it among what preflight "catches" — it does not. |
| Graduation at `api/main.py:1747` (docs 12, 13, 14, 15) | **`api/main.py:1750`**. Substance correct; no other evaluator exists in `api/` or `orchestrator/`. |
| `logging_utils.py:14,24` for `auto_log`/`log_action` (docs 13, 14, 15) | **`:8`** and **`:15`**. |
| "Message vocabulary: same **8**, +2" (doc 14 §2.1) | Upstream `Pilot.listens` has **7** keys (B1 `pilot.py:185-193`); MICS has **9** (`pilot.py:214-225`, new keys at `:223-224`). The cited range `:215-225` is off by one. The *inbound* orchestrator vocabulary is separately larger — `HANDSHAKE, STATE, PING, DATA, CONTINUOUS, STREAM, INC_TRIAL_COUNTER, TASK_ERROR, HARDWARE_LIB_TEST_RESULT` (`orchestrator/main.py:71-81`), the last three MICS additions. |
| `mics_task.py` "1,487 lines"; `condition_tree` at `:1105`; `if` actions `:646-694`; `check_determinism` at `FDA.py:37` (doc 14 §2.2; doc 13 §4.3) | **~1,601 lines** today (Phase 18 added ~116). `condition_tree` is read at **`:1216-1221`**, `_build_tree_lambda` at **`:1361`**, the `type:"if"` builder spans **`:685-733`**. `check_determinism` is **defined at `:38`**, called at `:36`. |
| `mics_task.py:194-201` for backend-authoritative prefs (doc 14 §2.3) | **`:233-252`** (`_merge_prefs_hardware`); `:194-201` is now the extlink bind loop. |
| `pilot.py:328,427` for SEMANTIC_HARDWARE introspection (doc 14 §2.3) | **`:326-339`** (`_serialize_semantic_hardware`) and **`:430-451`**. |
| `terminal.py:576-594` for `l_data` (doc 14 §5.2) | B1 **`:579-606`**; HEAD **`:596-630`**. The doc's range matches neither. |
| `pilot.py:1207` for the `DATA` send (doc 14 §2.5) | **`:1210`** (`:1207` is `# data['subject'] = self.subject`). |
| `Blueprint` collision at `api/main.py:851, 920, 1316, 1905` (docs 12, 13) | Substance correct, lines stale by ~3: `launch_session_blueprint` **`:923`**, `"blueprint_launched"` `:946`, `Blueprint {id}` `:1319-1320` and `:1908-1909`, headers `:854`, `:1224`. |
| Run-mode branches at `main.py:1264,1279` (doc 12 §3) | **`:1268`, `:1281`** (and `:1312` for `new`). |
| `Event_Dispatcher.py:38-48` for the envelope (doc 14 §2.5) | **`:38-49`**. Add the gloss the row omits: **`subject` holds `bp_s{session}_r{run}`, a run key, not an animal** (`main.py:1375`); the animal is in the `subjects` list. |
| `api/` ~8,100 lines · `orchestrator/` 1,709 (doc 14 §1, §4) | `api/` non-test = **8,976**; `orchestrator/` = **1,830** top-level, **3,116** with subpackages, **of which ~700 are vendored Autopilot**. `web_ui/` 84 TS/TSX/MTS modules ✓ (13,055 lines, 18 SPA routes). |
| Doc 14 §1: *"MICS outside the package — no Autopilot analogue exists: … `orchestrator/`"* | **Contradicts doc 14 §1c two pages later.** The orchestrator *vendors* ~700 lines of Autopilot networking including a byte-identical `message.py`. §1c is right; §1's ledger is wrong. |
| Doc 14 §1c: *"`node.py` cut from 643 to 176"*, *"`station.py` cut from 1,328 to 255"* | Those two orchestrator files are **dead code** — nothing imports them; only `message.py` is imported (`RouterGateway.py:10`). Rewrite as *"the orchestrator vendored `message.py` (byte-identical) and carries two unused trimmed copies."* |
| Doc 14 §1b: *"`~/pi-mirror` retains the full project history (185 commits)"* | 185 is right **across all refs**, but it is not one history: **three disjoint roots**, and the checked-out branch (`hw_libs`, 18 commits) has **no merge base at all** with `origin/MICS_main` (104 commits). Neither `30c8d3c` nor `origin/MICS_main` is an ancestor of HEAD. Any reproduction via `git log`/`git blame` on HEAD will be wrong; the objects are all present, so the *content* comparisons stand. This caveat belongs in §1b's method note, and it is the real maintenance liability the §4 risk paragraph should describe: **two unrelated histories of the same tree, not one fork drifting from upstream.** |

### 7.4 Phase status and tense

| Item | Doc claim | Reality |
|---|---|---|
| Doc 12 header | "22 live phases, 7 complete, 72 % of plans" | **24 phases, 8 complete, 64/85 plans, 76 %** (`STATE.md`, `last_updated 2026-08-09`). |
| **Phase 30 (Pi Repo Cleanup)** | absent from all four docs | Exists, not yet planned. |
| Phase 18 | "○ Planned, not executed" (doc 12 §1, §2.2); "planned but unexecuted" (doc 13); "or an approved plan" (doc 14 §1); doc 15 C8 "MICS adds:" | **COMPLETE 2026-08-09, 15/15 plans**, with the four caveats in §6. |
| Phase 19 | doc 12: "○ Pending, **0 plans**" | **3 plans** (`19-01/02/03`, planned 2026-08-05), still unexecuted. Doc 14 §2.4's "device-health badge (Phase 19)" reports planned work as existing — delete it. |
| Phase 26 | "blocked on 18" | No longer blocked (18 is done). 13 plans, unexecuted. |
| Phases 25 / 29 | 5/6 and 7/8 | Correct. Doc 13 §4.8's present tense on `ui_layout` is **correct** — plan 29-04 landed the JSONB column. |
| Phases 27 / 28 | 0 plans | Correct. |
| `ROADMAP.md`'s own summary table | — | Column-shifted for rows 11–14, 16, 18 (`STATE.md:1665` records the corruption), and Phase 18's checkboxes are stale. **Read `STATE.md`, not the ROADMAP table.** |
| Two `STATE.md` claims — "float values are truncated"; "Phase 18 has a genuine liveness bug" | — | **Formally retracted as false.** Withdraw them if they reached any working note. |

### 7.5 What the old docs get right and should be kept verbatim

1. **Doc 14 §1c in full** — byte-verified on both ends of the wire; *"MICS replaced Autopilot's
   server, not Autopilot's protocol."* Add only the depth qualification (§4.4).
2. **Doc 14 §4's four reasons to disclose the dependency**, especially #1 (checkable in thirty
   seconds — the release ships `LICENSE`, `CITATION.cff`, `setup.py`) and #2 (MPL-2.0 file-level
   copyleft). Extend #2's file list per §4.1 and replace *"fork"* with *"vendored dependency"*.
3. **Doc 14 §5.8's tone warning and its model paragraph** — write the architecture, never a
   reliability claim about someone else's software. The Terminal's design assumption is stated in
   its own source (`l_ping` docstring, `terminal.py:605`), which makes the non-adversarial framing
   both truthful and generous.
4. **Doc 15 C8's `Transformer` warning** — the finding most likely to save the manuscript.
5. **Doc 14 §2.6 / doc 15 C5 on `Accuracy`** — verified line for line; strengthen with the two
   extra defects (silent no-op on non-`NTrials`; inverted `current_trial`).
6. **Doc 14 §7.1–§7.5** — "template vs contract", the concession that
   `PARAMS`/`TrialData`/`History_Table` is a genuine design→execution→data thread, and the
   scope/enforcement reframing. The most intellectually honest passage in the set. One correction
   inside it: §7.2's fifth bullet must be softened per **F2**.
7. **Doc 14 §6** (hardware-abstraction rewrite instructions), including *"Never imply Autopilot
   lacks abstraction"*. Correct diagnosis: abstraction is not the novelty, **management of the
   abstraction is**. Trim §6.3 item 1's implicit run-binding claim.
8. **Doc 14 §5.2 and §5.7.** §5.2 identifies the one genuinely load-bearing architectural
   inversion (the UI's position relative to the data path). §5.7 correctly refuses to claim
   station-scaling as MICS's — make it load-bearing.
9. **Doc 13 §3.1's positive fix** — do not weaken the global-clock claim, replace it with the two
   mechanisms that actually exist.
10. **Doc 12 §2.4 / doc 13 §4.7's self-correction on `run_id`**, including the Methods caveat that
    the analysed corpus lacks the field the Methods will describe. Both the correction and the
    willingness to publish it are exemplary.
11. **A verified detail worth reusing:** the lab's own response to the Terminal's `time.sleep(5)`
    FIXME was to raise it to `time.sleep(10)` (`terminal.py:629`, FIXME text unchanged). It is the
    most persuasive single line available for why coordination moved out of the GUI, and it is the
    lab's own.

---

## 8. Open bugs found during the audit

**These are live defects in the running system, separate from the manuscript discussion.** They are
listed in rough order of scientific impact.

### 8.1 Silent-failure bugs — a run looks configured and does the wrong thing

| # | Defect | Evidence | Consequence |
|---|---|---|---|
| **B1** | **A non-`NTrials` `graduation_type` is accepted, stored, dispatched and silently never fires.** `_coerce_graduation` passes any `type` string through; `:1750` compares `== "NTrials"` only; there is no `else`, no 422, no log line. | `api/main.py:1607-1660`, `:1735`, `:1750`, `:1808` | A researcher configures an `Accuracy` step, sees no error, and the subject never advances. Worse than an unimplemented feature. **(F3)** |
| **B2** | **The FDA `special: INC_TRIAL_COUNTER` action is a silent no-op.** `mics_task.py:788` sends `self.node.send('T','INC_TRIAL_COUNTER', {})`, bypassing `Event_Dispatcher`, so no envelope is injected; `_handle_inc_trial`'s first two lines are `subject_key = value.get("subject")` / `if not subject_key: return`. It is accepted by validation (`api/fda_validation.py:44 VALID_SPECIALS`). | `mics_task.py:786-789`; `orchestrator_station.py:588-590`; `station.py:244-300` | A Blueprint author wires it, sees no error, and gets a run that never increments and never graduates. The working alternative is the flag form (`{"type":"flag","ref":"trial_counter","method":"increment"}`), which routes through `Trial_Tracker`. **(F4)** |
| **B3** | **`current_trial` is read as *N required*** while Autopilot documents the same key as a *resume offset*, and MICS's precedence chain prefers it over `n_trials`. | `main.py:1646-1654`, `:1752`; `graduation.py:103-105` | Any Autopilot-shaped protocol JSON resolves to `n = 0` → `n_required > 0` fails → **never graduates**, silently. **(F6)** |
| **B4** | **Preflight advises but never blocks.** Always-enabled start button; a `catch` that proceeds on preflight error; no server-side re-check on the start path. | `HardwareCheckModal.tsx:551`; `PilotSessions.tsx:100-102`; `web_ui/app.py:244-280`; `orchestrator_station.py:387-388` | A provable deadlock can be dispatched with one extra click. **(F1)** |
| **B5** | **No per-run record of the resolved library version**, and post-hoc promotion silently rewrites the answer for historical runs. | `session_runs` has 12 columns, none a version; `lib_version_resolution.py:33-92` replays against mutable state | The reproducibility claim is about policy, not record. **(F2)** |
| **B6** | **`promote_active_hw_libs_to_stable` runs on every `INC_TRIAL_COUNTER`** and promotes `lib.active_version_id`, not the version dispatched for the run. | `orchestrator_station.py:599-614`; `mics_api_client.py:370-379`; `hardware_libs.py:541-563` | `stable_reason='protocol_run'` can be stamped on a version that never participated in a run. |
| **B7** | **`*_and_notify` double-emit.** `set_and_notify`, `pulse_and_notify`, `open_and_notify`, `set_timmer_and_notify`, `cancel_timer_and_notify` and `increment_and_notify` all log the same physical action twice — once via the decorator, once via the explicit notify. | `mics_task.py:396-403,419-433,444-451,465-473`; `logging_utils.py`; `timer.py:19,28` | **Any naive count of reward deliveries or LED onsets over the event index is 2×.** Publish the de-duplication rule with the corpus. |
| **B8** | **Dual `event_type` vocabulary for the same device** — `hardware_type` (`"gpio.Solenoid_mics"`) from the auto-log path, `group` (`"VALVE"`) from the explicit path, class name from the tracker path, `"state_transition"` from the FDA. Nothing unifies them but `event_data.id`. | `logging_utils.py:91,54`; `mics_task.py:385`; `task.py:277`; `FiniteDeterministicAutomaton.py:17` | The mechanism behind "two event vocabularies in one index" — a code-level fact, not historical drift. |
| **B9** | **`compute_lib_import_failed` is RESERVED and never emitted**, while docs list it among what preflight catches. | `toolkit_dispatch.py:163,170-179` | Advertised protection that does not exist. |

### 8.2 Robustness and correctness defects

| # | Defect | Evidence |
|---|---|---|
| **B10** | `process_queue` has **no exception boundary** around `execute_trigger`; anything escaping kills trigger processing for the rest of the run. The queue is also unbounded, and the FDA only `print`s a warning on backlog. | `task.py:254-262`; `FiniteDeterministicAutomaton.py:84-86` |
| **B11** | Drop counters `_dropped_no_clock` / `_dropped_on_send` are **in-process only** — never dispatched, never persisted. "Did every event make it home?" is answerable only by attaching to a live process. | `Event_Dispatcher.py:24-26,51-58,78-88` |
| **B12** | `state.is_connected` **ignores liveness entirely** and returns "connected" for any pilot ever seen; its comment ("TEMP: Pi doesn't send ping/state yet") is wrong — the Pi pushes STATE every 5 s. `snapshot()` answers the same question correctly. Two answers, one question. | `state.py:53-57` vs `station.py:1089-1112`; `state.py:60-75` |
| **B13** | The View is written on the trigger worker thread and polled on the stage thread with **no lock**; correctness rests on CPython dict atomicity. `View.get_value` has no `KeyError` handling — a missing key is an uncaught exception inside a transition lambda. | `task.py` `execute_trigger`; `mics_task.py:489-495`; `View.py:43-44` |
| **B14** | `Hardware.__init__` does an unguarded `kwargs['type']`; vanilla allowed `Digital_Out(pin=7)`, today that raises `KeyError`. A regression in testability and direct instantiation. | `hardware/__init__.py:149` |
| **B15** | `HardwareState` aliases collapse: `CLOSED=0, UNTOUCHED=0, OPENED=1, TOUCHED=1`, so `HardwareState.UNTOUCHED is HardwareState.CLOSED`. The semantic distinction the names promise does not exist at runtime. | `hardware/__init__.py:80-85` |
| **B16** | `Pulse20Hz` sets `self.frequency = 60.0` and is bound to `GPIO.LED1` in the live `pilot/prefs.json`. Naming bug or config bug; either way it should not appear in a hardware description unexamined. | `gpio.py:1679` |
| **B17** | `Mics_Tracker.__init__` is missing `self` — dead-wrong code sitting in the type-dispatch spine of the logging system. Never called, so never fails. | `Mics_Tracker.py:2-4` |
| **B18** | `mixer.set_by_filename`'s `else` branch references an undefined name `e` in its f-string — `NameError` on any unknown filename. | `mixer.py:54` |
| **B19** | The session ↔ subject join is **not enforced by the database**: `SubjectProtocolRun.session_id` is a bare int with no FK, as are `Subject.lead_researcher_id` and `ProtocolStepTemplate.task_definition_id`. | `models.py:75`, `:56`, `:107` |
| **B20** | **No pilot busy-check** on run start. The only `pilot_id` filter sits inside the recoverable-run lookup (`STOPPED`/`ERROR`); nothing queries for an existing `PENDING`/`RUNNING` run. Two users can start two runs on one pilot. | `api/main.py:1236-1345`, `:1254`, `:1330-1335` |

### 8.3 Security surface (fix before anyone else deploys this)

| # | Defect | Evidence |
|---|---|---|
| **B21** | **`exec()` of database-sourced Python on the rig with no sandbox.** The upload gate is `ast.parse` + `py_compile` — a *syntax* check. Anyone who can POST a hardware lib gets code execution on every Pi running a toolkit that uses it. | `mics_task.py:222`; `hardware_libs.py:91-107` |
| **B22** | **Unauthenticated WebSocket** — `await ws.accept()` is unconditional, no token, no origin check, while the server-side client silently attaches the privileged API token. The orchestrator's five routes, **including `POST /runs/{run_id}/start`, have no auth at all.** | `web_ui/app.py:49-93`, `:51` |
| **B23** | Three secrets committed in plaintext: `POSTGRES_PASSWORD: change_me` (L11), `JWT_SECRET: pishoto` (L30), `MICS_API_TOKEN` (L59). | `docker-compose.yml` |
| **B24** | Elasticsearch host hardcoded in three places, no env var, no prefs key. | `orchestrator/main.py:61`; `ElasticSearchDateHandler.py:17,74`; Pi copy `ElasticSearchDataHandler.py:13` |
| **B25** | 7 containers with **zero resource limits declared**. | `docker-compose.yml` |

### 8.4 Not bugs — deliberate, but worth recording

- **Pi log files are always 0 bytes** by design: `core/loggers.py` uses `mode='w'` twice plus
  `doRollover()`, and `prefs.json` sets `LOGLEVEL=ERROR`. Do not "fix" it — but note that
  Autopilot's rotating debug log was **traded away, not merely supplemented**, and a reviewer
  looking for a Pi-side audit trail will find nothing.
- **Phase 18's `EgressWorker` never retries**, because *"a retried marker lands at the WRONG
  timestamp, corrupting co-registration"*, and drops the **newest** on overflow because *"the
  oldest items are nearest delivery and evicting them tears a hole mid-sequence"*
  (`external_hardware_runtime.py:21-23`). A genuinely good scientific-instrument decision, and
  worth quoting as stated rationale in a methods paper.
- **A standing operational dependency from Phase 18's rig checkpoint:** a TCP echo listener must
  keep running on `132.77.73.125:5597` or `demo.alive` flips false. Two of six checkpoint runs
  failed with `EXTLINK_GATE_TIMEOUT`, root-caused to fixture misconfiguration.

---

## Appendix — how absence was established, and one tooling hazard

Every *absence* claim in the audits underlying this document was established with **`/usr/bin/grep`
(the real binary, absolute path)** and corroborated a second way — by reading the file, by
`git show <ref>:<path> | /usr/bin/grep`, or by a live Postgres `information_schema` query.

**The hazard, recorded because it nearly produced false findings twice.** `rg` is not installed on
this host, and bare `grep` is hook-rewritten to a token-compressing proxy that reports a missing
binary as `0 matches` and can render a real matching line **blank**. Two live examples from this
audit: `rg -n "FLAGS|self\.flags" mics_task.py` returned **"0 matches"** for a file with **31**
matching lines, and the proxy rewrote `INC_TRIAL_COUNTER` to `n` inside one search. `git log` is
truncated by the same proxy — `git log --reverse origin/MICS_main` printed 50 lines where
`git rev-list --count` reports 104.

**Never assert that a symbol or import is unused from a filtered grep.** The `Camera` class
(`i2c.py:8,580`, the base of `MLX90640`) was nearly deleted on exactly this evidence, which would
have silently killed the pilot.

For provenance work specifically: `git log -S… --all` and `git blame` on HEAD are both **wrong** in
this repository, because it contains three disjoint root commits and the checked-out branch shares
no ancestry with the lab history. Every provenance claim in the source audits was determined against
an explicit ref-set, never `--all` and never HEAD.
