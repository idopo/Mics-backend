# DeepLabCut -> MICS Runbook

The researcher-facing path from "my DeepLabCut model runs" to "I authored a transition on my
keypoint in the browser." Nothing below is collapsed, abbreviated into a script, or glossed
over — DLC-13 makes an un-collapsible, honest runbook a deliverable in its own right, and if a
step is awkward, this document says so rather than hiding it.

This runbook has two halves: the **vision-box half** (your DeepLabCut project, your conda env,
your exported model) and the **backend half** (the six MICS steps that turn an uploaded lib
into a picker option in the FDA editor). Read both before running anything — the backend half
explains an ordering trap the vision-box half cannot warn you about on its own.

No sentence below claims a wire-timing number, a throughput figure, or any other rig
measurement that has not been made. Where a number depends on a real observation (the achieved
frame rate, the measured likelihood distribution, the confirmed pose-array row order), this
document tells you how and where to measure it — plans 35-07/35-08 are where those measurements
actually happen, and this document is instructions, not results.

---

## Your project directory is never written to

This is a standing requirement, and it is where this runbook opens because everything else
below makes no sense without it: **nothing in this workflow writes to, creates in, or modifies
your DeepLabCut project directory.** Your project directory is **never written to**.

Make the distinction explicit, now, because the rest of this section depends on it: **reading
your project is fine. Only writing is prohibited.** A tool that opens `config.yaml` to read your
bodypart list has done nothing wrong. A tool that writes a new file anywhere under your project
tree — even a log file, even a cache — has.

The conflict this creates: `deeplabcut.export_model(...)` has **no output-path parameter**. It
always writes into `<project>/exported-models-pytorch/` (the PyTorch engine's directory; the TensorFlow engine used `exported-models/`), and DLC-Live's `model_path` for the PyTorch
engine needs exactly that export's `.pt` file. Export cannot be run against the original
project without writing into it. The resolution is to run the export — **and only the
export** — against a **copy**:

1. **Copy a MINIMAL subset of your project to a scratch location outside it**, e.g.
   `C:\dlc-work\MyProject-copy`. The minimal set is `config.yaml`, `dlc-models-pytorch/`, and
   `training-datasets/` — the files `export_model` needs to locate your trained network and its
   training metadata. **Deliberately exclude** `videos/` and `labeled-data/`: they are large,
   `export_model` does not read them, and copying them wastes disk and time for nothing. This
   minimal set is the standard shape DeepLabCut's own export step expects; your rig session
   (plan 35-07) is where it gets its first real exercise against this project's actual export —
   if your own `export_model` run names an additional missing path, add that specific directory
   to the copy. Never point the export at the original project to work around a missing path.
   **Write footprint: creates a new directory tree outside your project; touches nothing inside
   the original project.**
2. **Edit `project_path:` in the COPY's `config.yaml`** to the copy's own location. This step is
   **not optional**, and skipping it does not fail loudly — it fails by looking like it worked.
   DeepLabCut resolves every relative path (models, training data, evaluation results) from
   `project_path`. A copied `config.yaml` that still carries the ORIGINAL project's
   `project_path` value will happily read and write back into the original project while
   appearing to operate on the copy — the exact write this whole section exists to prevent, and
   the hardest version of it to notice, because nothing raises an error. Use `check_dlc.py`
   (delivered separately, read-only) to confirm: it emits a `[WARN]` on exactly this
   `project_path`/actual-location mismatch. **Write footprint: modifies one line in the COPY's
   `config.yaml`; the original `config.yaml` is untouched.**
3. **Run `export_model` (and any other writing step) against the COPY, never the original.**
   With `project_path` corrected in step 2, everything DeepLabCut writes — the
   `exported-models-pytorch/` directory, any evaluation output — lands inside the copy. **Write
   footprint: writes into `<copy>/exported-models-pytorch/` and nowhere else; the original project
   directory receives zero writes.**

**Do not copy your videos.** Every video read in this workflow — `cv2.VideoCapture`,
`DLCLive`'s inference calls, `deeplabcut.analyze_videos`'s `videos` argument — is read-only.
Because the copy's `project_path` now points at the copy while your videos remain under the
ORIGINAL project (you did not copy `videos/`), **pass ABSOLUTE paths to every video you
reference** in every DLC and adapter call. A relative path would resolve against the copy's
`project_path`, where `videos/` does not exist. **Write footprint of reading a video file:
writes nothing.**

**`dlc-link-generate` needs no copy at all.** It reads `config.yaml` — a few kilobytes — and
writes only into the directory you name with `--out-dir`. It never touches
`exported-models-pytorch/`, never touches your training data, and never needs the model export to have
happened yet. Point it at your REAL project's `config.yaml` and give it an `--out-dir` outside
that project; requiring a copy to generate a lib would be a pointless obstacle invented for no
reason — the copy above exists for the export step and nothing else.

`deeplabcut.analyze_videos` writes **next to the video by default** — a `.h5`/`.csv`/`.pickle`
alongside whatever file you pass it, wherever that file lives. Run it against the copy (so
`project_path` resolves correctly) and always pass an explicit `destfolder=` argument pointing
outside both the copy and the original — otherwise its output lands inside whichever directory
holds the video, which for an absolute path into your ORIGINAL project's `videos/` means writing
into the original project.

**Every command in this runbook states what it writes and where, or says "writes nothing."** A
step below without that annotation is a defect in this document, not a hint that the step is
safe by omission.

Summarised, for the three CLI tools this package ships:

- `dlc-link-generate` **requires** an explicit `--out-dir` (no default of `.`) and **refuses to
  write inside the project it read** — including when you run it from a shell sitting inside
  that project directory, which is exactly where your prompt usually is.
- `dlc-link-live` **writes nothing at all**, anywhere, ever. It reads frames and sends signals
  over the network; counts go to stdout.
- `dlc-link-convert` **requires** an explicit `--out` path and refuses a path inside a project,
  the same way `dlc-link-generate` does.

---

## The numbered steps (vision-box half)

1. **Clone the DeepLabCut environment before installing anything.**
   `conda create -n <name> --clone DEEPLABCUT`. Why: `DEEPLABCUT` holds the working DLC 3.0
   training setup that produced your model — installing new packages into it directly gambles
   that working setup on a dependency conflict you cannot predict in advance. **Write footprint:
   writes into the new cloned conda environment only; the source `DEEPLABCUT` environment is
   read, never modified.**
2. **Install `deeplabcut-live[pytorch]`, `mics-link`, and `dlc-link` into the clone.** On the
   verified target environment, the `mics-link` install is a dependency **no-op** — its
   `pyzmq`/`msgpack` floors are already exceeded by what DeepLabCut 3.0 itself requires — and the
   only package `deeplabcut-live` adds on top is `colorcet`. **If `pip` proposes to UPGRADE
   `pyzmq`, stop and report it before proceeding** — Jupyter, IPython, Spyder and napari all
   depend on `pyzmq`, and an upgrade there risks breaking tools you use for everything else.
   **Write footprint: writes into the cloned conda environment's site-packages only.**
3. **Run `python -m mics_link.selfcheck` and treat it as mandatory, not optional.** Something in
   the DeepLabCut 2.2.3 import chain patches `msgpack` globally; a sender process that ever
   imports DLC 2.x would have every frame it sends silently corrupted (numpy-extended and
   counted `malformed` on the Pi) with **nothing visible from the sender's own output**. Your
   target DLC 3.0 environment does not carry this hazard, but `selfcheck` is the only way to
   confirm that for YOUR actual environment rather than assume it. **Write footprint: writes
   nothing; prints a pass/fail report to stdout.**
4. **Export the model:** `deeplabcut.export_model(...)`, run against the COPY (see the section
   above). For the PyTorch engine, `model_path` (DLC-Live's constructor argument) is the
   resulting **`.pt` FILE** — not a directory, and not the project directory. A DLC 3.0 project
   typically has no `exported-models-pytorch/` directory until this step creates one. **The directory is named `exported-models-pytorch`, NOT `exported-models`** — verified on the real project 2026-09-02; searching for `exported-models` alone finds nothing and makes a successful export look like a silent no-op. Budget time for
   this being the first real obstacle: DeepLabCut-Live issue #137 and an image.sc report both
   describe DLC 3.0 exports emitting a single `.pt` file while DLC-Live still complains about a
   missing `pose_cfg` — if you hit this, it is a known rough edge, not something you configured
   wrong. **Write footprint: writes into `<copy>/exported-models-pytorch/` only (see the copy section
   above); nothing in the original project is touched.**
5. **Measure the achieved frame rate before choosing a decimation rate.** Do not assume a rate
   from a spec sheet. GPU inference on the target card is proven fast, which makes decimation
   MORE load-bearing, not less — a higher real fps means more signals per second arrive at the
   adapter before the decimator's Hz cap thins them out, so knowing the real number first is what
   makes the decimation setting meaningful rather than a guess. **Write footprint: writes
   nothing; the measurement is a printed number, not a file.**
6. **Probe the pose array before generating anything, using `dlc-link-live --probe-pose --video
   <a project video> --model-path <the exported .pt>`.** This step exists because DLC-Live's own
   documentation states only that `single_animal=True` yields an array of shape
   `(num_bodyparts, 3)` — it does **not** say whether `num_bodyparts` is the small multianimal
   set or the full set including every unique bodypart, and it does not say what row order the
   array uses. The adapter indexes `pose[i]` by position, so a wrong assumption about order sends
   the WRONG keypoint's numbers out under the RIGHT signal name — silently, because nothing about
   that failure looks broken. **State the contingency plainly: if this probe shows the unique
   bodyparts are ABSENT under `single_animal=True`, generating signals for a unique bodypart (like
   the LED demo below) needs `single_animal=False` plus explicit detection selection instead —
   that is a deliberate design change to make at this point, not something to discover mid-run.**
   **Write footprint: writes nothing; prints the observed pose shape and row order to stdout.**
7. **Generate the lib and the signal map:**
   `dlc-link-generate --config <config.yaml> --source-id <your id> --bodyparts <comma list>
   --coords <comma list> --pose-order-file <from step 6> --out-dir <somewhere outside the
   project>`. The `--config` form (reading your real, uncopied `config.yaml` — reading is
   always fine) is the normal path; an explicit bodypart list with no `--config` at all is the
   documented fallback for when no config file is available yet. **`--bodyparts` is REQUIRED and
   there is deliberately no flag that emits every candidate**: this project alone offers **72**
   candidate keypoints (10 multianimal bodyparts × 5 individuals, plus 22 `uniquebodyparts`), and
   at a 10 Hz per-signal decimation cap even just the 22 unique parts would be 220 messages per
   second against a proven ~60 message/second envelope — an explicit, narrow selection is
   structural, not a style preference. **Write footprint: writes exactly two files
   (`<source-id>_lib.py`, `<source-id>_signals.py`) into `--out-dir`; refuses if `--out-dir`
   resolves inside the project directory it read `config.yaml` from, even when invoked from a
   shell whose current directory IS the project.**
8. **Measure the likelihood distribution before choosing a threshold.** Do not assume `> 0.9` (or
   any other number) means what it sounds like it means. This project's `config.yaml` sets
   `pcutoff: 0.01` — two orders of magnitude below DeepLabCut's own `0.6` default — so a
   threshold picked from habit may fire never, or fire always, and either way it will not mean
   what its author intended. Read the threshold off the MEASURED likelihood distribution of the
   DECLARED bodyparts on a real video; plan 35-07 records that measurement for this project's
   demo signals. **Write footprint: writes nothing; the measurement is a printed distribution
   summary, not a file.**

---

## Ports: there is no default, and that is deliberate

`--port` has no default value. Passing `--host` without `--port` is an immediate
`exit 2`, before the model loads.

That is not an oversight to be tidied up later. A single pilot binds one extlink socket
**per `source_id`**, and pilot 3 currently binds two:

| Port | `source_id` | Lib |
|---|---|---|
| 5599 | `demo` | `ExtlinkDemo` (lib 177) |
| 5601 | `dlc_cam1` | the DLC lib (lib 243) |

Both are real, bound, listening sockets. So sending DLC keypoints to 5599 does not fail —
it succeeds, into the wrong fixture. The connection is accepted, the frames are consumed,
and the lib you meant to feed stays empty while the model appears broken. A wrong-but-open
port is far more expensive to debug than a closed one, which is why the tool refuses to
guess.

The port is a property of the `pilot_hardware_config` row for that `(pilot, source_id)`
pair — not of this tool, and not of the lib. Read it from the pilot's hardware config
before a run; the same lib attached to a second pilot, or a second camera on this one,
gets a different number. `--dry-run` and `--probe-pose` connect to nothing and need no
port at all.

## What `<source_id>.alive` actually means

Short, and load-bearing — a researcher gating an FDA transition on `alive` will read it as "the
sending computer is reachable." That is not the whole story, and getting this wrong costs a real
debugging session.

- **`alive` is a CONJUNCTION**, not a pure inbound-liveness flag. The substrate computes
  `liveness_alive and not _egress_failed` (`external_hardware_binding.py:141`) — so a module
  that performs its OWN outbound probe can have its `alive` pulled false by that probe failing,
  **even while inbound signal data is arriving completely normally.** The exact same value gates
  whether a run is even allowed to start, because the readiness check (`is_ready()`) defaults to
  this same `alive` flag.
- **This failure mode is invisible from the signal data itself.** Your keypoint signals keep
  updating normally; only the `alive` tracker goes false, for a reason that has nothing to do
  with your keypoints. Phase 18 hit exactly this and it cost a real diagnosis session — recorded
  here so the next reader does not pay for it twice.
- **The outbound probe is LIB-SOURCE behaviour, never a config setting.** The substrate always
  builds the machinery capable of tracking an egress failure, for every module, unconditionally
  — but that machinery stays permanently inert unless the lib's own code actively enqueues
  something to send outbound. No key in `pilot_hardware_config` turns a probe on or off. The
  standing `ExtlinkDemo` fixture (a DIFFERENT lib from the one this runbook generates) hardcodes
  its own outbound probe and its own port; that is a property of THAT lib's source code, not of
  the substrate or of any config value.
- **The generated DeepLabCut lib enqueues nothing outbound**, so for it, `alive` genuinely
  DOES collapse to pure inbound liveness: false means the vision box stopped reaching the Pi, and
  nothing else. This is a property of what the generated lib's source code contains — no
  `self.send(...)` call anywhere in it — not a general guarantee about the `alive` key. **If you
  ever add outbound traffic to a DeepLabCut lib later, you inherit the conjunction, and `alive`
  stops meaning what it means today.** `_egress_failed` starts `False` at construction and can
  only ever change if the lib enqueues something that then fails — a lib that enqueues nothing
  can never make it leave `False`.
- **`alive` and staleness answer different questions, and they are not interchangeable.** A
  keypoint signal going STALE (governed by `stale_after_ms`) already gives correct fail-safe
  behaviour regardless of WHY the data stopped — sender died, animal walked out of frame,
  tracking lost the keypoint. `alive`'s job is to say WHY data stopped, when it does. **Gate
  safety-critical behaviour on staleness. Gate diagnosis on `alive`.**

---

## What you can and cannot declare

Stated as fact, not preference — these are properties of how this project's model was trained,
not stylistic choices this runbook is recommending.

- **Per-individual signals are technically UNAVAILABLE live, not merely deferred.** This
  project's `config.yaml` sets `identity: false` with `default_track_method: ellipse`. Under that
  configuration, individual identity is assigned **post-hoc**, by
  `convert_detections2tracklets` and `stitch_tracklets` — a batch step that runs AFTER inference
  on a whole video, which DLC-Live **does not run** during live inference. In live inference,
  the detection array's index order is unstable from one frame to the next, so a signal like
  `mouse3_nose_x` would silently refer to a DIFFERENT physical mouse from one frame to the next
  with no indication anything changed. This is the REASON, not a preference — a model trained
  with `identity: true` would need its own, separate evaluation before this restriction applies
  to it.
- **`uniquebodyparts` are the ideal signals to declare in v1.** They are single-instance by
  construction — there is exactly one `LED_on`, exactly one arena corner named `NW` — so the
  identity-instability problem above **cannot apply to them at all.** This project's 22
  `uniquebodyparts` include `LED_on`/`LED_off` (used by the demo below, because an operator can
  drive them deterministically without needing an animal to cooperate) and the four arena
  corners `NW`/`NE`/`SE`/`SW`.
- **The arena corners are a deferred idea, not a v1 feature — do not declare them.** Using the
  corners as a normalisation reference frame (a coordinate expressed relative to the arena
  rather than the raw frame buffer) is a real, recorded idea for later, but it requires the
  corners to be reliably detected first and adds its own failure mode on top of everything above.
  For now, coordinates are normalised by dividing by the frame's own width and height, which is
  simpler and already implemented. This is a deliberate deferral, not an oversight — do not
  "helpfully" add `NW`/`NE`/`SE`/`SW` signals to a lib without re-reading this paragraph first.

---

## The backend half — the six steps, with the exact calls

Every step below has a corresponding entity and exact payload recorded in
`.planning/phases/35-deeplabcut-keypoint-likelihood-integration/35-FIXTURE-INVENTORY.md`, from
this project's own standing `dlc_cam1` fixture.

1. **Upload the lib version.** `POST /api/hardware-libs`, multipart form with `name`, the
   generated `<source_id>_lib.py` as `file`, `kind=hardware`, `declared_imports=[]`. **Write
   footprint: creates one `hardware_libs` row and one `hardware_lib_versions` row in the shared
   database — no filesystem write anywhere.**
2. **Register the hardware module.** `POST /api/hardware-modules` with `name`,
   `hardware_lib_id` (from step 1), and `class_name` matching the class the generator emitted.
   **Write footprint: creates one `hardware_modules` database row.**
3. **Create the `pilot_hardware_config` row.** `PUT /api/pilots/{pilot_id}/hardware-config/{name}`
   with the exact config shape (`class_name`, `role: "router_bind"`, `listen_port`, `host`,
   `source_id`, `stale_ms`, `required`, `wait_timeout_s`) — see the fixture inventory for a
   worked example. **This is the step the next section names as the hidden ordering
   requirement — read it before skipping ahead.** **Write footprint: creates or updates one
   `pilot_hardware_config` database row for the named pilot.**
4. **Select the toolkit.** Either link the module onto an existing backend-authored toolkit's
   `hardware_module_ids`, or create a new toolkit that includes it (`POST /api/toolkits`) plus
   `POST /toolkits/{toolkit_id}/hardware-libs` to link the lib. **Prefer a NEW toolkit for a new
   external device** rather than adding it to a toolkit any real, currently-running task
   definition already dispatches on — config rows are matched by module NAME against a
   toolkit's module set, so adding a socket-binding module to a shared toolkit puts it on the
   dispatch path of every task definition that already uses that toolkit. **Write footprint:
   creates one `task_toolkits` row (new-toolkit path) and/or one `toolkit_hardware_libs`
   database row — no filesystem write.**
5. **Run preflight.** The dispatch/preflight machinery (`api/routers/toolkit_dispatch.py`)
   resolves the toolkit's linked libs against each pilot's config rows before a run starts,
   catching a missing or malformed config before it becomes a mid-run failure. **Write
   footprint: writes nothing; read-only validation against already-created rows.**
6. **Author the transition, in the browser.** Open the FDA editor for a task definition on this
   toolkit; the DeepLabCut module's signals appear as `<source_id>.<signal_name>` options in the
   condition-builder's operand picker (`ConditionBuilder.tsx`/`ArgInput.tsx`, both of which read
   `toolkit.extlink_signals`). Build a condition ANDing a coordinate with its own likelihood (see
   the worked example below), save, and the save-time gate returns a `422` if you reference a
   view key the module never declared. **Write footprint: writes one `fda_json` update to the
   task definition's database row via the editor's own save action — no filesystem write.**

---

## The obstacle, named

DLC-13 says plainly: if a runbook cannot be written short and linear, that finding is itself the
deliverable. Here is the finding, named rather than papered over.

**The ordering above is FORCED, and it is non-obvious.** The function that turns a module's
signals into the FDA editor's pickable view keys (`derive_extlink_keys`) returns an **empty
list** unless the pilot's `pilot_hardware_config` row for that module has a non-empty string
`source_id`. Signal NAMES are pilot-invariant — they come straight from the lib's own AST, so
they exist the moment the lib is uploaded — but the KEYS the picker actually offers are not
pilot-invariant at all; they do not exist until step 3 above has happened for a specific pilot.
**A researcher who completes steps 1 and 2 (upload the lib, register the module) and then goes
straight to the FDA editor sees a silently EMPTY picker, with no error message telling them
why.** Nothing in the editor says "no pilot config row exists for this module yet." The picker
simply has nothing to offer, and looks exactly the way it would look if the whole feature were
broken.

Concretely: this is a **six-step path**, of which **three steps have no UI affordance
connecting them to the next one** (nothing links the hardware-lib upload page to "now go create
a pilot config row," nothing links a bare config row to "now go pick a toolkit"), and none of
the six steps tells the researcher what the next one is.

**What would fix this, and why it is deliberately NOT fixed here:** either (a) a single
`POST /api/dlc/register` endpoint collapsing the lib-upload, module-registration, and
config-row-creation steps into one atomic call, or (b) an explicit empty-picker message in the
editor itself, along the lines of "no pilot config row exists for this module on this pilot."
Both are recorded as deferred ideas in `35-CONTEXT.md`, revisited only now that this obstacle
has an exact name and mechanism rather than being folklore passed from one confused researcher
to the next.

---

## Start order, and the worked coordinate condition

**Start order depends on the config row's `required` field, in both directions:**

- `required: true` — the readiness gate blocks a run from starting until this source connects
  (up to `wait_timeout_s`), and FAILS the run if it never does. **Start the sender BEFORE
  starting the run.**
- `required: false` — the run does not wait for this source at all. **Start the run FIRST, then
  the sender** — the opposite order from the `required: true` case. This project's standing
  `dlc_cam1` fixture on pilot 3 is configured `required: false`, so **run first, then sender**
  is the order that applies there.

**The worked coordinate condition (D-19).** Coordinates use `stale_policy="hold_last"`, which
means a coordinate signal alone is unsafe to gate on — its value survives past the moment
tracking is actually lost, silently. Likelihood uses `stale_policy="return_default"` with
`default=0.0`, which is safe to compare in either direction (0.0 always means "no confidence").
**Every condition reading a coordinate must be ANDed with that same keypoint's own likelihood
signal:**

```
dlc_cam1.led_on_likelihood > 0.6  AND  dlc_cam1.led_on_x > 0.3
```

Never gate a transition on a coordinate alone.

**Replay, for reproducing a run without the camera.** `mics-link-replay` plays a recorded
`(t, signal, value)` file through the SDK client at real time, a scaled rate, or as fast as
possible — the same mechanism `sdk/README.md` §7 documents for any device. Use it to re-run a
recorded DeepLabCut session's signals deterministically, without the vision box or the model
present, for debugging an FDA transition after the fact.
