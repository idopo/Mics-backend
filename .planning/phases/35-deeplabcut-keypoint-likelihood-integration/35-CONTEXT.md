# Phase 35: DeepLabCut Keypoint Likelihood Integration - Context

**Gathered:** 2026-08-31
**Status:** Ready for planning

<domain>
## Phase Boundary

A DeepLabCut model already trained and running on the lab's Windows vision box pushes per-keypoint
**likelihood AND normalised x/y coordinates** into a running task's View via the Phase 34
`mics-link` SDK, and an FDA transition **authored in the browser** fires on them. The vision box is
not otherwise connected to MICS: no camera trigger, no capture, no video into the system.

Fixed by ROADMAP.md and DLC-01..DLC-13. Discussion below clarifies HOW, never WHETHER to add more.

**The user's north star for this phase, in their own words (2026-08-31):**
> *"I only wish to test the dlc connection with the pi and have this end result of a generic way for
> all lab members to link their model to the pi."*

So the deliverable is the **path**, not the Gili model. MultiMice-Gili-2026-06-21 is the worked
example that proves the path; every artefact must generalise to the next lab member's model.

**Not in this phase:** running/training DeepLabCut itself, video into MICS, a batched wire frame,
latency/jitter measurement (Phase 28), `sub_connect`, closed-loop actuation beyond ordinary FDA
transitions, multi-animal identity tracking, a React UI for lib generation.

</domain>

<decisions>
## Implementation Decisions

### Target environment and model — CORRECTED, this supersedes all pre-2026-08-31 research

- **D-01: The target is `DEEPLABCUT` — DeepLabCut 3.0.0, PyTorch engine, Python 3.12.13**, NOT the
  `DEEPLABCUT223` env that earlier research profiled. Verified on the box 2026-08-31: torch 2.5.1
  (`cuda_built=11.8`), **`available=True` on an RTX 3060**, numpy 1.26.4, cv2 4.11, pandas 2.3.3,
  tables 3.11.1, ruamel.yaml 0.19.1. `pip check` clean. **All prior "the lab runs DLC 2.2.3 /
  TensorFlow / Python 3.8" analysis is void for this phase** — see
  `35-DLC-LIVE-NOTES.md` -> *"SUPERSEDING CORRECTION — 2026-08-31"*.
- **D-02: `model_type="pytorch"`.** `"base"` / `"tensorrt"` / `"lite"` are the TensorFlow-engine
  values and do not apply.
- **D-03: `deeplabcut-live` 1.1.0 is the version** — `requires_python = ">=3.10,<3.13"` and the env
  is 3.12.13. Install line `pip install "deeplabcut-live[pytorch]"`. Dependency-checked against the
  live env 2026-08-31: **the only package it adds is `colorcet`** (numpy<2 ✓1.26.4, tables>=3.8
  ✓3.11.1, timm>=1.0.7 ✓1.0.27, torch>=2.0 ✓2.5.1, torchvision>=0.15 ✓0.20.1, scipy>=1.9 ✓,
  einops ✓, dlclibrary>=0.0.6 ✓0.0.12, pandas ✓, opencv-python-headless ✓, ruamel.yaml ✓,
  py-cpuinfo ✓, tqdm ✓).
- **D-04: Install into a CLONED env** (`conda create -n <name> --clone DEEPLABCUT`). `DEEPLABCUT`
  holds the working DLC 3.0 training setup that produced the model; do not gamble it.
- **D-05: The SDK install is a dependency NO-OP on the target** — `pyzmq 27.1.0` and `msgpack 1.2.1`
  both exceed the `>=22` / `>=1.0` floors. SDK-14's "no upgrade proposed" is satisfied by
  construction, and no jupyter/spyder stack is disturbed.
- **D-06: `python -m mics_link.selfcheck` stays a mandatory first step in the runbook** even though
  `msgpack-numpy` is absent from the target env. It IS present in `DEEPLABCUT223` on the same box,
  and it is the only thing that makes silent wire corruption visible. (Note: the 2026-08-31 probe
  that reported `223` as PATCHED imported `msgpack_numpy` itself and so may have caused the patch —
  the reading is **contaminated and must not be cited as proof**; the corrected checker no longer
  imports it.)

### The model, and what it forces

- **D-07: `single_animal=True`, always, in v1.** `MultiMice-Gili-2026-06-21` is a multi-animal
  PyTorch project (`dlc-models-pytorch/`, `evaluation-results-pytorch/`). DLC-Live's README,
  verbatim: *"As multi-animal models can be used with PyTorch, the shape of the `pose` array given
  to the processor may be `(num_individuals, num_keypoints, 3)`. Just call
  `DLCLive(..., single_animal=True)` and it will work."* So multi-animal is a one-flag problem, not
  a redesign. User, asked whether identity matters: *"so I don't care. but some models are
  multianimal yes."*
- **D-08: The adapter asserts `pose.ndim == 2` and refuses loudly otherwise.** The guard survives
  from the earlier research but its **rationale is inverted**: it no longer means "3-D is
  impossible with this lab's models" (it is entirely possible) — it means "this adapter requires
  `single_animal=True`". The error message must say that and name the flag, never blame the engine.
  Per-individual signal expansion is a named non-goal, recorded in `<deferred>`.
- **D-09: The project has NO `exported-models/` directory.** DLC-Live's `model_path` for pytorch is
  the **`.pt` file** produced by `deeplabcut.export_model(...)`, not a directory and not the project
  dir. **Export is a prerequisite step in the runbook, not a design question.** Budget for friction:
  DeepLabCut-live issue #137 and image.sc report DLC 3.0 exports emitting a single `.pt` while
  DLC-Live still complains about a missing pose_cfg. Treat this as the likely first real obstacle.
- **D-09b: GPU inference is PROVEN on the target, not assumed** (verified 2026-08-31 by an actual
  512x512 CUDA matmul): RTX 3060, driver 531.18, torch cuDNN 9.1.0, sm_86, 12.9 GB. So real fps is
  high and D-22's decimation is load-bearing. **Measure fps on this card before choosing a rate.**
- **D-09c: `h5py` is ABSENT from the target env; `tables` 3.11.1 is present.** The `.h5` -> wide
  replay converter (D-31) MUST read via `pandas.read_hdf` (PyTables backend), never `h5py`. Do not
  add an h5py dependency to the vision box.
- **D-09d: Something in the DeepLabCut 2.2.3 import chain patches `msgpack` globally** (verified
  2026-08-31 with a probe that does NOT import `msgpack_numpy`). Any sender importing DLC 2.x would
  have every frame silently numpy-extended and counted `malformed` on the Pi, invisibly. Does not
  affect the DLC 3.0 target env, but it is why D-06's `selfcheck` step is non-negotiable.
- **D-10: `config.yaml` has been requested and is not yet in hand.** It is an INPUT to the generator
  (bodypart list, `individuals`, `multianimalproject`), never a design blocker. `check_dlc.py`
  (delivered to the user 2026-08-31, read-only) reports exactly these fields plus the on-disk
  snapshots and each video's fps/resolution.

### The actual model — `config.yaml` READ 2026-08-31 (supersedes D-10's "not yet in hand")

Verbatim from `C:\Users\YizharGPU12\Desktop\Gili\MultiMice-Gili-2026-06-21\config.yaml`:

| Key | Value |
|---|---|
| `Task` / `scorer` / `date` | MultiMice / Gili / Jun21 |
| **`engine`** | **`pytorch`** — confirms D-02 from the project's own config |
| **`multianimalproject`** | **`true`** |
| **`identity`** | **`false`** |
| `individuals` | `1,2,3,4,5` — **five mice** |
| `multianimalbodyparts` (10) | nose, L_ear, L_eye, R_eye, R_ear, head_center, head_end, L_side, tail, R_side |
| `uniquebodyparts` (22) | **NW, NE, SE, SW**, **LED_off, LED_on**, Mic1_middle..Mic8_end |
| `bodyparts` | `MULTI!` (the maDLC sentinel — there is no flat list) |
| `pcutoff` | **0.01** |
| `default_net_type` / track method | resnet_50 / ellipse |
| `iteration` / `snapshotindex` | 0 / -1 |
| videos | 11 entries, 1280x960 and 1920x1080 |

- **D-37: `identity: false` makes per-individual signals technically UNAVAILABLE live, not merely
  deferred.** With `identity: false` and `default_track_method: ellipse`, individual identity is
  assigned **post-hoc** by `convert_detections2tracklets` + `stitch_tracklets` — a batch step
  DLC-Live does **not** run. So in live inference the detection index is unstable frame to frame.
  This upgrades D-07 from a user preference ("I don't care") to a **hard technical fact**: a
  `mouse3_nose_x` signal would silently change which animal it refers to between frames. Record
  this in the runbook as the reason, so nobody "adds it later" without re-reading it.
- **D-38: `uniquebodyparts` are the ideal v1 signals, and the demo should use them.** They are
  single-instance by construction, so they carry **no identity ambiguity at all** — the exact
  problem D-37 describes does not apply to them. Two are especially valuable:
  **(a) `LED_on` / `LED_off`** — an operator-controllable, deterministic trigger. Gating the demo
  FDA on `LED_on` likelihood gives a repeatable rig test that does not require an animal to
  cooperate, which is a strictly better first proof than waiting for a mouse to move. It also
  exercises D-19's `likelihood AND x/y` pattern honestly.
  **(b) `NW` / `NE` / `SE` / `SW`** — the arena corners. These are a candidate normalisation
  reference frame that is a property of the arena rather than of the frame buffer, which is what
  D-18 is reaching for. **Not adopted in v1** — D-18's divide-by-frame-dimensions stands, because
  corner-based normalisation needs the corners to be reliably detected and adds a failure mode.
  Recorded as a deferred enhancement.
- **D-39: 72 candidate keypoints exist** (10 multianimal x 5 individuals + 22 unique). Against
  D-22's ~60 msg/s budget this makes selective declaration structural, not advisory. The generator
  must therefore REQUIRE an explicit bodypart selection and refuse to emit all of them.
- **D-40: The generator must read THREE sources, not one.** `config.yaml` may carry
  `bodyparts` (single-animal flat list), `multianimalbodyparts` + `individuals`, and
  `uniquebodyparts` — and in a maDLC project `bodyparts` is the literal string `MULTI!`, which is a
  sentinel, **not a list**. A generator that reads `bodyparts` naively gets the string `"MULTI!"`
  and emits garbage. D-13 previously named only the multianimal case; this corrects it.
- **D-41: Do NOT assume a `> 0.9` likelihood threshold is meaningful.** The project sets
  `pcutoff: 0.01`, two orders of magnitude below DeepLabCut's 0.6 default. The demo transition's
  threshold must be chosen from the **measured** likelihood distribution of the declared bodyparts
  on a real video, not picked a priori. Add measuring it as an explicit task.
- **D-42: OPEN EMPIRICAL QUESTION — does `single_animal=True` return the unique bodyparts?**
  DLC-Live's docs state only that the array becomes `(num_bodyparts, 3)`; they do **not** say
  whether `num_bodyparts` is the 10 multianimal parts, or 32 (10 + 22 unique), nor the row order.
  Row order is load-bearing — the adapter indexes `pose[i]` by position. **This must be settled by
  running `init_inference` once and printing `pose.shape` before any signal mapping is written**,
  not by assumption. If unique parts are absent under `single_animal=True`, D-38's LED demo needs
  `single_animal=False` plus explicit detection selection, which changes the adapter's shape.

### Declaration path — the core "generic way for anyone" deliverable (DLC-02, DLC-13)

- **D-11: A CLI generator, `config.yaml` -> hardware-lib source.** Shape:
  `python -m dlc_link.generate --config <config.yaml> --source-id dlc_cam1 --bodyparts nose,tail`.
  It emits (a) the `ExternalHardware` subclass source the researcher pastes into the hardware-lib
  upload page, and (b) a **machine-readable bodypart -> signal-name map that the adapter IMPORTS**.
  Chosen over a browser upload page (which would drag frontend work into a phase that otherwise has
  none) and over both-at-once.
- **D-12: One declaration site, enforced by construction.** DLC bodypart names are arbitrary user
  strings (`"left ear"`, `"tail-base"`, `"Nose"`). The generator owns the name -> Python-identifier
  transform and **emits** the mapping; the adapter imports it. Neither side may re-derive it. An
  undeclared name is dropped Pi-side as `unknown_name` and is **invisible from the sender**, so a
  divergence here is a silent total failure.
- **D-13: The generator records which engine/format a lib version came from.** DLC 3.0 pytorch reads
  `multianimalbodyparts`/`individuals` from `config.yaml`; a TF 2.x project reads `all_joints_names`
  from an exported `pose_cfg.yaml`. Same generator, different readers, recorded provenance.
- **D-14: Generated-and-uploaded, not seeded.** DLC-02 fixes "one lib version per trained model",
  which is inherently per-user and per-model — so a first-party seeded lib in `api/seed_libs/`
  (Phase 26's precedent) is the wrong mechanism for real models. A single generated demo lib backs
  the rig checkpoint. Hardware libs already execute from `hardware_lib_versions.source_code` with
  per-task-def pinning, so "one lib version per model" needs no new machinery.
- **D-15: Generator-time validation is mandatory, because these fail late and lethally.**
  (a) `stale_after_ms == 0` means NEVER stale — it silently deletes DLC-05's whole occlusion
  semantic, so the generator must require an explicit non-zero value;
  (b) `stale_policy` is validated at READ time and **raises `ValueError` inside FDA evaluation,
  on the rig, mid-run** — legal values are exactly `hold_last` / `return_default` / `return_none`,
  so a typo is a run-killer and must be caught at generation;
  (c) `ALLOWED_DTYPES` is enforced at class-build time, so a `@signal` with neither annotation nor
  typed default is a hard failure at lib import on the Pi.

### Signal semantics (DLC-03, DLC-05)

- **D-16: Likelihood uses `stale_policy="return_default"`, `default=0.0`.** Safe in both comparison
  directions because 0.0 genuinely means "no confidence".
- **D-17: Coordinates use `stale_policy="hold_last"`, and every transition reading a coordinate is
  ANDed with that keypoint's likelihood.** This is forced, not stylistic:
  `FiniteDeterministicAutomaton.__next__` evaluates `all(expr() for expr in expr_list)` **unguarded**
  and `_build_transition_lambda` uses a raw `operator.gt`. Therefore `return_none` is a task-killer
  (`None > 0.5` raises `TypeError` out of `__next__`), and no numeric sentinel is safe in both
  directions (`default=-1.0` makes `nose_x > 0.6` correctly False on tracking loss but makes
  `nose_x < 0.2` **fire falsely**). The likelihood signal is therefore **the guard that makes
  coordinates usable at all**, not merely the cheap one.
- **D-18: Coordinates are NORMALISED 0..1**, divided by the frame width/height the adapter already
  holds. `DLCLive(resize=...)` returns coordinates in the *resized* frame, so `nose_x > 300` would
  silently change meaning whenever resize, camera or crop changes.
- **D-19: The first rig proof exercises the ANDed coordinate pattern, not likelihood alone.** User:
  *"a model notifying a certain x y and a high likelihood should fire a transition."*

### Decimation (DLC-04)

- **D-20: Deadband + per-signal Hz cap live in the DLC adapter, not in `mics_link`.** A deadband is
  a decimation policy and the SDK has no opinion on rates; `sdk/`'s device-neutrality guard
  (34-08 Task 2) bans DLC vocabulary there anyway.
- **D-21: Size decimation against the IOLoop and ES, NOT against "256".** The oft-cited "the Pi's
  ingress queue is bounded at 256" is **false** — `_recv_buffer = deque(maxlen=256)` is append-only
  and never read, and `ZMQStream(...).on_recv` runs decode + `tracker.set()` + dispatch
  **synchronously on the Tornado IOLoop** that also serves the pilot's orchestrator DEALER and the
  STOP channel. Consequences the plan must carry: (i) the high-rate failure mode is **IOLoop
  starvation degrading FDA timing and STOP responsiveness**, so the soak must watch transition
  timing and STOP, not just a counter; (ii) a frame lost at ZMQ's high-water mark is counted
  **nowhere**, so the sender's own `stats.dropped` is the only end-to-end drop accounting that
  exists — DLC-04's "no silent drops" is **not satisfiable Pi-side as built**, and the phase must
  say so rather than imply otherwise; (iii) every accepted `SIG` carries `@log_action` and emits one
  CONTINUOUS ES event — a **1:1 amplification**, so 240 msg/s in is 240 ES events/s out per pilot.
- **D-22: Budget target ~60 msg/s** (Phase 18's proven envelope): 2 bodyparts x (x, y, likelihood)
  at 10 Hz decimated = 60 msg/s. Undecimated is 240 (likelihood-only, 8 parts, 30 fps) to 720
  (8 parts x 3, 30 fps). **Measure real GPU fps first** — the RTX 3060 makes achievable fps higher
  than the earlier CPU-bound assumption, which makes decimation MORE load-bearing, not less.

### Liveness — a Phase 34 debt this phase must clear (DLC-06)

- **D-23: Fix `liveness_hook` in this phase, as its own plan step.** Phase 34 observation B is
  **INCONCLUSIVE**: hardware lib 177 v2 hardcodes `def liveness_hook(...): return True`
  ("DIAGNOSTIC OVERRIDE (v2)"), so `demo.alive` would read true with the sender switched off.
  SDK-05 is therefore unproven on hardware and DLC-06 cannot be satisfied on top of it.
  Cut a v3 with the override removed and re-run the quiet test.
- **D-24: Budget for the fix resurfacing a real bug.** The override's own docstring says the default
  path *"reported not-alive while `on_recv` was demonstrably stamping `_last_msg_ts_ms`, stranding
  the readiness gate in 2 of 4 rig runs"*. Removing it may re-expose that. **This is an
  investigation, not a checkbox** — plan it with room to debug.

### Rig checkpoint

- **D-25: Pilot 3 / RecordingBox (.213) is the target.** Phase 34 runs 582/583/584 succeeded there,
  so the extlink path is already proven live on that stack. Record which stack backed each
  observation — the ingress module differs between `pi-mirror` and `mics_core` (the latter adds
  one-clock timestamping), even though the wire module is byte-identical.
- **D-26: Reconnect (SDK-07 / Phase 34 observation D) is tested by stop-run -> start-new-run, NOT by
  restarting the pilot.** `.213` binds 5599 only for the duration of a run, so the client cannot
  tell the two apart. This avoids touching the pilot service at all. Note `seq` is **not** in the ES
  payload, so continuity is verified from the sender's own `CONNECTED`/`DISCONNECTED` output plus
  data resuming after the gap — the 34-09 instruction to verify seq in ES cannot be followed.
- **D-27: Start the sender BEFORE starting the run.** `required: true` on the pilot config row
  blocks at the readiness gate for `wait_timeout_s` and then FAILS the run if the sender is not
  connected. Applies to the offline-movie workflow identically.
- **D-28: Design the demo task so graduation is not on its path.** `INC_TRIAL_COUNTER` from a
  GUI-built task definition is a **silent no-op** (it sends `{}`; the orchestrator drops it on the
  missing `subject` key — proven on run 562), and DLC-08 requires the FDA be authored in the
  browser. Either keep graduation off the demo's path or fix the counter first — deliberately,
  not by accident.

### Cross-talk scope — a RECORDED DEVIATION from roadmap criterion 10 (user decision 2026-08-31)

- **D-43: DLC-11's cross-talk proof runs TWO `source_id`s on ONE pilot (pilot 3), not on two
  pilots.** Roadmap success criterion 10 says "a second DLC module on a **second pilot** does not
  cross-talk." No plan provisions a second pilot, and the user chose this deviation deliberately
  after it was surfaced by the plan checker — it is **not** an oversight and must not be recorded
  as one.
  **Rationale:** the isolation mechanism that could actually fail is the ROUTER identity check plus
  tracker-prefix namespacing, and **neither is per-pilot** — both are per-`source_id` within one
  pilot's module set. Two `source_id`s with two tracker prefixes and two disjoint view-key sets on
  one pilot therefore exercises the real code path. A second pilot would add a second OS process
  and a second network peer, which the substrate already isolates for unrelated reasons.
  **Verification wording:** close DLC-11 as PROVEN for the same-pilot dual-`source_id` case and
  state in the same sentence that the roadmap's literal "second pilot" wording was NOT exercised,
  with this decision cited. Do not silently reword the criterion.
  **Rejected alternative, recorded so it is not re-litigated:** provisioning pilot 1 (.72.28) would
  satisfy the wording literally and would additionally be a cross-stack test (pilot 1 runs the
  older `pi-mirror` ingress, which stamps `_last_msg_ts_ms` from `time.time()` rather than the
  one-clock mapping — see D-23/D-24). It was declined for setup cost. If a cross-stack observation
  is ever wanted, that is the cheapest route to it.

### Workflow shape and ordering

- **D-29: Live-shaped first, converter second.** (A) video file -> `DLCLive` Processor -> `mics_link`,
  paced with `mics_link.timing.Pacer` at the video's native fps. That IS the live pipeline with a
  file substituted for a camera, so the camera later becomes a one-line swap. Then (B) the DLC
  `.h5` -> **wide** `(t, col-per-signal)` replay file -> `mics-link-replay`, which is the no-GPU
  regression test DLC-09 requires. Both ship; A is the first proof.
- **D-30: Pacing is mandatory for the file workflow.** `cv2.VideoCapture` on a file yields frames as
  fast as the model consumes them; unpaced, DLC-05's `stale_after_ms` is exercised at a timebase
  unrelated to the live case and the run proves the wrong thing.
- **D-31: The `.h5` -> flat converter belongs to Phase 35, never to `mics_link`.** A DLC export is a
  3-row scorer/bodyparts/coords MultiIndex, not a `(t, signal, value)` file. The wide replay format
  is the natural target: ~36k rows for a 20-min 30 fps 8-bodypart export instead of ~864k. The SDK's
  device-neutrality guard bans the converter from `sdk/` and is correct to.
- **D-32: The adapter never opens or closes a `MicsLink` inside the Processor.** `Processor` has no
  guaranteed teardown (`save()` is called by the DLC-Live GUI, not by `DLCLive`). Own the client
  outside in a `with connect(...)` block and pass it in.
- **D-33: `send_signal` is called from DLC's inference thread**, synchronously, once per frame,
  inside `get_pose()` -> `_post_process_pose()`. SDK-15 exists for exactly this. `process()` MUST
  return the pose.
- **D-34: Convert with `mics_link.values.as_scalar` (`.item()`), never `float(...)`.** Every pose
  value is a numpy scalar; `numpy.float64` IS a `float` subclass, so an `isinstance` check passes it
  into msgpack, which cannot pack it — turning a call-site error into an invisible IO-thread
  failure. `.item()` preserves int/bool/float; `float()` flattens them.

### Runbook (DLC-13d)

- **D-35: Document all six steps honestly; collapse none.** The path is upload lib -> register
  module -> create pilot config row -> toolkit selection -> preflight -> author. No new backend
  endpoint and no generated setup script in this phase. DLC-13 explicitly says *"if the runbook
  cannot be written short and linear, that finding is itself the deliverable"* — so **record which
  step is the obstacle** rather than papering over it. Keeps the phase about DLC and adds zero new
  backend surface.
- **D-36: The runbook order is FORCED and must be stated.** `derive_extlink_keys` returns `[]`
  unless `config["source_id"]` is a non-empty string in a **`pilot_hardware_config` row**. Signal
  *names* are pilot-invariant (from the lib's AST) but the *keys* are not. With no config row the
  FDA editor's picker is **silently EMPTY with no error to explain it**. A researcher who uploads a
  lib and goes straight to the editor sees nothing and cannot tell why.

### Claude's Discretion

- Exact module layout under `mics-backend/dlc_link/`, CLI flag spelling, generator template
  mechanics, deadband/Hz-cap defaults (subject to D-22's budget), and test structure.
- Which bodyparts the demo lib declares — the user explicitly does not care
  (*"I don't care... generic"*). Pick a small set consistent with D-22 and driven by `config.yaml`.
- Plan decomposition and wave assignment.

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### This phase
- `.planning/phases/35-deeplabcut-keypoint-likelihood-integration/35-DLC-LIVE-NOTES.md` — verified
  DLC-Live execution model, Pi-side ingress truth, generator traps, worked end-to-end example,
  message-rate table. **Read the "SUPERSEDING CORRECTION — 2026-08-31" section FIRST**; everything
  above it that assumes DLC 2.2.3 / TensorFlow / Python 3.8 is void for this phase.
- `.planning/REQUIREMENTS.md` §"DeepLabCut Keypoint Integration (DLC)" — DLC-01..DLC-13.
- `.planning/ROADMAP.md` §"Phase 35" — goal, 11 success criteria, files-to-change, NOT-in-scope.

### Phase 34 (the SDK this phase consumes)
- `.planning/phases/34-mics-link-sdk-client-package/34-CONTEXT.md` — the additive/device-neutral
  north star and the public-API principles.
- `.planning/phases/34-mics-link-sdk-client-package/34-HARDWARE-VALIDATION.md` — **§3d is
  load-bearing**: observation C PASS, **B INCONCLUSIVE (drives D-23/D-24)**, **D NOT EXERCISED
  (drives D-26)**.
- `.planning/phases/34-mics-link-sdk-client-package/34-VERIFICATION.md` — 10/15 criteria verified
  locally; which 5 need hardware.
- `sdk/README.md` — the public API surface the adapter is written against. **Phase 35's adapter must
  be writable using only what this documents** (34-CONTEXT's device-neutrality test).
- `sdk/src/mics_link/__init__.py` — `connect`, `MicsLink`, `SenderStats`, `Pacer`; note
  `as_scalar` is NOT re-exported (import from `mics_link.values`).
- `sdk/examples/callback_sender.py` — the device-neutral shape of the Processor callback.
- `sdk/examples/rig_checkpoint_sender.py` — the pattern the DLC rig checkpoint script follows.

### Backend integration points
- `api/extlink_keys.py` — `derive_extlink_keys`, `module_extlink_signals` (source of D-36's
  ordering constraint).
- `api/fda_validation.py` — the save gate that 422s an undeclared view key.
- `api/routers/toolkits.py` — puts `extlink_signals` on the toolkit payload the editor fetches.
- `web_ui/react-src/src/components/ConditionBuilder.tsx:50` and
  `web_ui/react-src/src/components/ArgInput.tsx:38` — both pass `toolkit.extlink_signals` into
  `buildViewOptions`; both must be exercised for DLC-08.
- `api/seed_libs/compute_ops.py` — the only existing seeded-lib precedent (rejected as the delivery
  mechanism by D-14, but the reference for lib source shape).

### Pi substrate (READ-ONLY — never edited by this phase, per DLC-01)
- `~/mics_core/autopilot/autopilot/hardware/external_hardware.py` — `@signal` / `@event` /
  `@command`, `ALLOWED_DTYPES`, `resolve_dtype`, `resolve_stale_value`, `liveness_hook`,
  `_recv_buffer`.
- `~/mics_core/autopilot/autopilot/hardware/external_hardware_ingress.py` — the synchronous
  IOLoop ingress path (source of D-21).
- `~/mics_core/autopilot/autopilot/hardware/external_hardware_wire.py` — the locked envelope the
  SDK is byte-parity-tested against.

### Upstream (external)
- DeepLabCut-Live README — `pip install deeplabcut-live[pytorch]`, `model_path` = the `.pt` from
  `export_model`, and the `single_animal=True` multi-animal statement quoted in D-07.
- DeepLabCut-Live issue #137 / image.sc "export_model exporting only one file" — the DLC 3.0
  export/pose_cfg friction D-09 budgets for.

### Project rules that constrain execution
- `CLAUDE.md` §"Pi / Orchestrator Integration" and the standing hard rules: **the agent never runs
  git on the Pi, never starts/stops the pilot process, and never runs Python on the Pi.** Every rig
  action is user-run; the agent supplies exact commands and the user reports back.

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- **The whole `mics_link` SDK** — `connect()`, bounded non-blocking `send_signal`, `SenderStats`,
  heartbeat, reconnect FSM, `Pacer`, `values.as_scalar`, `replay()` + wide-file reader, and
  `selfcheck`. Phase 35 writes zero transport code.
- **`sdk/examples/rig_checkpoint_sender.py`** — the proven shape of a user-run rig script.
- **The hardware-lib pipeline** (Phases 9/10/11/13/17) — versioned lib source in
  `hardware_lib_versions.source_code`, per-task-def pinning via `hw_lib_versions`, AST metadata
  extraction, module registration, pilot config rows, toolkit dispatch, preflight. DLC-01 requires
  the DLC lib be an ordinary customer of all of it.
- **`ExtlinkDemo` / lib 177 / task def 434 / toolkit 100** — the standing fixture; the model for
  the DLC module's own rows, and the thing D-23 must fix a v3 of.

### Established Patterns
- **Signals declared statically by decorator, extracted by AST.** A config-driven signal set would
  be invisible to the editor picker (DLC-02). This is why the generator emits source rather than
  the lib reading a config.
- **Hardware libs execute from the DB, not the Pi checkout.** A `git pull` on the Pi does NOT deploy
  a regenerated lib. Good news for "one lib version per trained model" — the pinning already exists.
- **Soft rig verification posture.** Backend/SDK edits are agent-driven; every rig and vision-box
  action is user-run and reported back.

### Integration Points
- `mics-backend/dlc_link/` (**new, a SEPARATE package — NOT inside `sdk/`**). 34-08 Task 2 fails the
  build if `deeplabcut`, `keypoint`, `bodypart`, `pose` or `\bdlc\b` appears anywhere under `sdk/`,
  including README and examples. Extending the SDK with a DLC adapter would fail that test, and
  correctly so.
- `mics-backend/tools/` or `dlc_link/generate.py` — the lib-source generator.
- Data rows created at the rig checkpoint, not code: `hardware_lib_versions`, `hardware_modules`,
  `pilot_hardware_config`, a toolkit, and a `dlc_demo` task definition.
- A researcher-facing runbook — the Pi-side counterpart to `sdk/README.md`.

</code_context>

<specifics>
## Specific Ideas

- **The model:** `C:\Users\YizharGPU12\Desktop\Gili\MultiMice-Gili-2026-06-21` — a DLC 3.0 PyTorch
  multi-animal project. Contains `config.yaml`, `dlc-models/`, `dlc-models-pytorch/`,
  `evaluation-results-pytorch/`, `labeled-data/`, `training-datasets/`, `videos/`. **No
  `exported-models/`.** Videos in `videos/` are the offline input for D-29's workflow A.
- **The vision box:** Windows, `C:\Users\YizharGPU12\.conda\envs\`. Two DLC envs — `DEEPLABCUT`
  (the target) and `DEEPLABCUT223` (TF 2.2.3, Python 3.8, GPU-capable, carries `msgpack-numpy`).
- **Diagnostics delivered to the user 2026-08-31** (read-only, run per env):
  `check_env.py` (interpreter, DLC engine, GPU driver + CUDA/cuDNN DLL loadability + a real
  512x512 GPU matmul, wire deps, msgpack-numpy patch state, mics_link selfcheck) and
  `check_dlc.py` (config.yaml bodyparts/individuals, on-disk snapshots, exported-models presence,
  per-video fps/resolution; `--infer` opt-in to actually run the model). **`check_dlc.py`'s output
  is a planning input** — it supplies the generator's bodypart list and the measured fps that sizes
  D-22's decimation budget.
- **Two corrections worth carrying:** (1) `DEEPLABCUT223`'s TensorFlow **does** see the GPU
  (`gpus=1`) — an earlier prediction of CPU-only was wrong; (2) that env's `torch 1.13.1+cpu` is
  incidental baggage in a TF env, not a fault.

</specifics>

<deferred>
## Deferred Ideas

- **Per-individual multi-animal signals** (`mouse1_nose_x`, `mouse2_nose_x`). Explicitly out for v1
  per D-07. Inherits DLC's identity-tracking instability, where a swapped identity becomes a *wrong*
  FDA transition rather than merely a stale one — a different and worse failure mode than occlusion.
  Its own phase if ever wanted.
- **A browser page for lib generation** — upload `config.yaml`, tick bodyparts, backend creates lib
  + module + config row. Rejected for this phase (D-11) to keep frontend work out; the natural
  follow-on once the CLI generator proves the shape.
- **`POST /api/dlc/register`** collapsing lib+module+config into one atomic call, or a generated
  `setup_<source_id>.py`. Rejected by D-35; revisit only after the runbook names which step is
  actually the obstacle.
- **Ingress-side drop counting on the Pi.** D-21(ii) shows "no silent drops" is unsatisfiable
  Pi-side as built. Fixing it is a **Phase 18 amendment with its own contract tests**, not a quiet
  edit here.
- **A batched multi-signal wire frame.** Explicitly out of scope in ROADMAP; a Phase 18 amendment if
  decimation ever proves insufficient.
- **`hardware_libs.stable_version_id` for lib 8 still points at the `np.int`-broken v4**, and task
  defs 186/179 remain pinned to broken versions. Recorded in `OPEN-ITEMS-2026-08-30.md` §3; not this
  phase's work, but the preflight lib test not catching it (a module that imports but whose classes
  crash on instantiate) is a live hazard for any lib this phase adds.
- **Live camera input.** User confirmed non-blocking. D-29's workflow A is deliberately structured so
  the camera is a one-line swap (drop the `Pacer.wait_until` call).

### Reviewed Todos (not folded)
- **"Fix stale React bundle trap in web_ui static output"** (2026-08-05, area `ui`, score 0.9) — not
  folded, but **planning must note the hazard**: DLC-08 requires the first-ever human click through
  the FDA editor's extlink picker, and a stale React bundle would make a working picker look broken.
  Verify the bundle is current before concluding anything from a browser observation.
- **"Reinstate CMP-24a and CMP-24c Pi view-mirror fixes"** (2026-08-05, area `pi`, score 0.9) —
  keyword match only; unrelated to extlink signal ingestion. Deferred.

</deferred>

---

*Phase: 35-deeplabcut-keypoint-likelihood-integration*
*Context gathered: 2026-08-31*
