# DeepLabCut -> MICS Runbook

The researcher-facing path from "my DeepLabCut model runs" to "I authored a transition on my
keypoint in the browser" — now including a live camera and an annotated live view. Nothing
below is collapsed, abbreviated into a script, or glossed over — DLC-13 makes an
un-collapsible, honest runbook a deliverable in its own right, and if a step is awkward, this
document says so rather than hiding it.

This runbook has two halves: the **vision-box half** (your DeepLabCut project, your conda env,
your exported model, your camera and your live view) and the **backend half** (the six MICS
steps that turn an uploaded lib into a picker option in the FDA editor). Read both before
running anything — the backend half explains an ordering trap the vision-box half cannot warn
you about on its own.

No sentence below claims a wire-timing number, a throughput figure, or any other rig
measurement that has not been made. Where a number depends on a real observation (the achieved
frame rate, the camera's delivered rate, the measured likelihood distribution, the confirmed
pose-array row order), this document tells you how and where to measure it, and says plainly
when that measurement has not happened yet rather than inventing one — plans 35-07/35-08 (model
signals) and 38-04/38-07 (camera and recording) are where those measurements actually happen;
this document is instructions, not results.

**This runbook is model-agnostic.** Every bodypart name, row count, and project path below that
comes from one specific project (nicknamed "MultiMice" in this document) is labelled as a
worked example, never as a requirement. If you are reading this with a different model, a
different camera, or a different bodypart selection, the numbered steps still apply — only the
names change, and the probe in Step 6 is what measures your names for you.

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
2. **Install everything into the clone with one command:**
   `python -m pip install "mics-dlc-link[live]"`. That single line pulls `mics-link` and
   `deeplabcut-live[pytorch]` in as dependencies — there is nothing to download by hand, no
   wheel to fetch off a share, and no lab repository to get access to. On the
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
6. **Probe the pose array FIRST — before generating anything. `--signal-map` is optional on this
   first probe, because there is no map yet to pass it.** The loop is:

   ```
   dlc-link-live --probe-pose --video <a project video> --model-path <the exported .pt>
   ```

   This prints the observed `pose.shape`, the row count, the discovered order (or a `NOT FOUND`
   line naming the attributes it tried), every column of row 0 (including any beyond the first
   three — see the note below), and a ready-to-paste `--pose-order a,b,c` line. **Copy that line
   verbatim into the next command:**

   ```
   dlc-link-generate --config <config.yaml> --source-id <your id> --bodyparts <...> \
     --pose-order <the line the probe printed> --out-dir <outside the project>
   ```

   **Then re-probe, this time WITH the generated `--signal-map`**, and confirm the two lines it
   now prints: `row_count_match=True` and `POSE_ORDER_SOURCE: 'probe'`. Those two together are
   the only honest confirmation that the map's assumed order matches what the runner actually
   produced.

   **Why this loop, and not a shortcut.** DLC-Live's own documentation states only that
   `single_animal=True` yields an array of shape `(num_bodyparts, 3)` — it does not say whether
   `num_bodyparts` is the small multianimal set or the full set including every unique bodypart,
   and it does not say what row order the array uses. The row order is **not programmatically
   discoverable** from the runner: `35-HARDWARE-VALIDATION.md` §4 tried the `cfg`, `dlc_config`
   and `pose_cfg` attributes on the constructed runner and found none of them. On the one project
   measured so far, the order was inferred INDIRECTLY — `config.yaml`'s `multianimalbodyparts`
   happened to be the only list in the project of the right length. **That is corroboration, not
   measurement, and a project with two lists of the same length gets no corroboration at all.**
   The adapter indexes `pose[i]` by position, so a wrong assumption about order sends the WRONG
   keypoint's numbers out under the RIGHT signal name — silently, because nothing about that
   failure looks broken. The probe-generate-reprobe loop above is how this project's numbers
   got measured instead of assumed, and it is now the documented normal path, not a recovery step.

   **One more thing the probe measures and you should read, not skip:** the observed pose array
   on the one project measured so far had **five columns, where DLC-Live's own documentation
   says three.** The probe prints all of them, labelling columns 0/1/2 as `x`/`y`/`likelihood`
   and anything beyond as `uncharacterised`. Nothing in this package reads the uncharacterised
   columns today; the probe prints them so the next model's array is measured, not assumed.

   **State the contingency plainly: if this probe shows the unique bodyparts are ABSENT, a
   signal declared on a unique bodypart is not reachable live at all** — see "What you can and
   cannot declare" below; this is not a `single_animal` flag to flip. **Write footprint: writes
   nothing; every number above is a printed line, never a file.**
7. **Generate the lib and the signal map:**
   `dlc-link-generate --config <config.yaml> --source-id <your id> --bodyparts <comma list>
   --coords <comma list> --pose-order-file <from step 6> --out-dir <somewhere outside the
   project>`. The `--config` form (reading your real, uncopied `config.yaml` — reading is
   always fine) is the normal path; an explicit bodypart list with no `--config` at all is the
   documented fallback for when no config file is available yet. **`--bodyparts` is REQUIRED and
   there is deliberately no flag that emits every candidate.** The number of candidates your own
   project offers is `(multianimal bodyparts x individuals) + uniquebodyparts` — on the one
   project measured so far (`example, from the MultiMice project this was first proven on:` 10
   multianimal bodyparts x 5 individuals, plus 22 `uniquebodyparts`) that came to 72, and at a
   10 Hz per-signal decimation cap even the 22 unique parts alone would be 220 messages per second
   against a proven ~60 message/second envelope on that rig — an explicit, narrow selection is
   structural on any project with more than a handful of bodyparts, not a style preference specific
   to this one. Compute your own project's number from your own `config.yaml` before picking a
   list. **Write footprint: writes exactly two files (`<source-id>_lib.py`, `<source-id>_signals.py`)
   into `--out-dir`; refuses if `--out-dir` resolves inside the project directory it read
   `config.yaml` from, even when invoked from a shell whose current directory IS the project.**
8. **Measure the likelihood distribution before choosing a threshold.** Do not assume `> 0.9` (or
   any other number) means what it sounds like it means. Read YOUR OWN `config.yaml`'s `pcutoff` —
   `example, from the MultiMice project:` that project's `pcutoff` was `0.01`, two orders of
   magnitude below DeepLabCut's own `0.6` default, so a threshold picked from habit there would
   have fired never, or fired always, and either way would not have meant what its author
   intended. Whatever your own project's `pcutoff` is, read the threshold off the MEASURED
   likelihood distribution of the DECLARED bodyparts on a real video; plan 35-07 records that
   measurement for the MultiMice project's
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

Stated as fact, not preference. The first point below is a property of how a SPECIFIC model was
trained and may not apply to yours; the second is a property of DLC-Live's own PyTorch runner and
applies to every model, unconditionally.

- **Per-individual signals may be UNAVAILABLE live, not merely deferred — check your own
  `config.yaml`.** `example, from the MultiMice project:` that project's `config.yaml` set
  `identity: false` with `default_track_method: ellipse`. Under that configuration, individual
  identity is assigned **post-hoc**, by `convert_detections2tracklets` and `stitch_tracklets` — a
  batch step that runs AFTER inference on a whole video, which DLC-Live **does not run** during
  live inference. In live inference, the detection array's index order is unstable from one frame
  to the next, so a signal like `mouse3_nose_x` would silently refer to a DIFFERENT physical mouse
  from one frame to the next with no indication anything changed. This is the REASON, not a
  preference — a model trained with `identity: true` needs its own, separate evaluation before
  this restriction applies to it; do not assume your project inherits MultiMice's `identity: false`.
- **CORRECTED — `uniquebodyparts` are UNREACHABLE live, for every model, regardless of
  `single_animal`. Do not declare one; there is no flag that makes it work.** An earlier version
  of this document recommended `uniquebodyparts` as the best signals to declare first, reasoning
  that their single-instance construction sidesteps the identity-instability problem above.
  **That recommendation was wrong, and the rig proved it wrong.** DLC-Live's PyTorch runner
  reads only `get_predictions(outputs)["bodypart"]["poses"]` (`dlclive/pose_estimation_pytorch/
  runner.py:211`) and **discards** the model's second output head, `"unique_bodyparts"` —
  `single_animal` only selects which individual's assembly to return from the first head
  (`runner.py:223-228`); it does not change which head is read at all. So no `uniquebodypart` —
  not an LED, not an arena corner, not anything declared `unique: true` in your `config.yaml` —
  is ever reachable by a live MICS task, on any model, full stop.
  (`35-HARDWARE-VALIDATION.md` §3, Phase 35.) This is exactly why the correction matters: the
  unique bodyparts nonetheless LOOK available when you inspect an offline export, because
  `deeplabcut.analyze_videos` reads **both** heads and writes the unique bodyparts into the
  project's own `_el.h5` files under the individual literally named `single` — the same file you
  would open to sanity-check your model. Seeing them there tells you nothing about whether
  `dlc-link-live` can reach them; it cannot. **A reader that concatenates the second head onto the
  first is real, recorded future work that does not exist yet** — until it lands, treat every
  `uniquebodypart` as off-limits for a live signal, and declare only bodyparts from the
  multianimal/single-animal assembly that DLC-Live's runner actually returns. The arena-corner
  idea below, and any LED-style demo, fall under this correction.
- **A reference-frame normalisation using detected landmarks (e.g. arena corners) is a deferred
  idea, not a v1 feature — do not declare it, and see the correction above for why it cannot work
  via a `uniquebodypart` regardless.** Using detected landmarks as a normalisation reference frame
  (a coordinate expressed relative to the arena rather than the raw frame buffer) is a real idea
  for later, but it requires those landmarks to be reliably and CURRENTLY reachable, which
  `uniquebodyparts` are not. For now, coordinates are normalised by dividing by the frame's own
  width and height, which is simpler and already implemented. This is a deliberate deferral, not
  an oversight.

---

## CAMERA — pointing `dlc-link-live` at a live feed instead of a file

Everything in the numbered steps above works unchanged with `--video <file>`. This section is
what changes when the frame source is a camera instead.

- **`--source` takes a device index (`0`), a stream URL (`rtsp://...`, `http://...`), or a file
  path** — classified automatically and printed before the capture is constructed. `--video`
  still works as a deprecated alias (kept because it is in shell history); giving both is an
  error. **Try a stream URL first if your camera or its vendor software offers one at all** — a
  URL needs no new code in this package, because `--source` already resolves it to the same
  `stream` kind a network camera gets.
- **A camera paces itself; `--fps` is refused for one.** `--fps` exists to override a FILE's
  reported rate and is meaningless for a device that delivers frames at its own pace — passing it
  with `--source 0` or a stream URL is an immediate error naming the reason, not a silently
  ignored flag. `CAP_PROP_FPS` is printed for information but is **never trusted** as a rate —
  read the next point instead.
- **Measure the delivered rate with `--capture-only` BEFORE running the model, and derive
  `--min-rate` from that measurement — never from a spec sheet, a driver default, or a container's
  own default framerate.** `--capture-only` loads no model at all; it reads frames and counts them,
  which is what the baseline has to be. The arithmetic: run `--capture-only` for a known
  `--max-seconds`, read `frames_read / duration_s` off the printed summary — that is your baseline.
  Then run again WITH the model loaded, over the same duration, and read `frames_inferred /
  duration_s` — that is your achieved rate. `--min-rate` has no default **on purpose**: the
  threshold is yours to set from your own two numbers, never invented by this tool. A reasonable
  starting point is some margin below the achieved rate (so a normal run does not trip the warning)
  but above the point where the pipeline is visibly falling behind (`frames_skipped` climbing).

  **The number for this rig has not been measured yet.** `38-HARDWARE-VALIDATION.md` §3/§4 record
  the procedure above against the `DMK 33GP1300` camera through the MJPEG relay (topology T4/T5a,
  below) and are `pending` as of this writing — plan 38-04's rig session is where that measurement
  happens. Until that table is filled in, run the procedure yourself and write your own number down
  before relying on `--min-rate` for anything unattended. Do not borrow the camera's own
  configured rate (30 fps on this rig, per `38-HARDWARE-VALIDATION.md` §2.5) as a substitute — that
  is what the camera SENDS, not what the vision box's own pipeline can sustain once a relay hop and
  a model are both in the path, and the two numbers are measured differently for exactly that
  reason.
- **`frames_skipped` is what the pipeline could not service — a non-zero value is normal, not an
  error.** The single-slot reader (`LatestSlot`) keeps only the newest frame by design, so any
  frame the render/inference side was too slow to consume is overwritten, not queued; that count
  is the honest keep-up instrument, not a defect counter. **Inference load and ZMQ/decimation load
  are different limits and must not be conflated:** the decimator's own per-signal Hz cap governs
  what actually reaches the wire regardless of how fast frames arrive, so a camera delivering faster
  than the decimation cap needs is not "wasted" — it is simply thinned downstream, same as a file
  source would be.
- **A camera run ends in one of four ways, and all four close the link and release the device**:
  `--max-frames` reached, `--max-seconds` reached, `should_stop`/`Ctrl-C`, or (camera-specific)
  consecutive read failures exceeding `--read-retries` — a camera gets bounded retry on a
  transient read failure where a file source stops on the very first one, because a file's failed
  read means end-of-stream and a camera's might not.
- **Write footprint: `dlc-link-live` still writes nothing at all, camera or not.** Every number in
  this section is a printed line; no log, no cache, no frame is ever saved to disk by this tool.

---

## TOPOLOGY — where the camera is, not just how to address it

The section above assumes `--source` can already reach your camera. It frequently cannot, not
because of a missing flag but because of where the two machines physically are: the box running
the model need not be anywhere near the rig, and lab IT may refuse to admit an unknown device to
the network at all. Topology is a separate question from source KIND (`device`/`stream`/`file`),
and each topology resolves to exactly one kind:

| ID | Topology | Resolves to | What has to exist |
|---|---|---|---|
| T1 | Camera direct to the vision box (USB/CSI) | `device` | nothing — `--source 0` |
| T2 | Camera holds a routable IP on the lab LAN | `stream` | IT admits the device — may be refused |
| T3 | IP camera on a private segment behind a lab computer | `stream` | a TCP port-forward on the lab computer — **does not carry a GigE Vision camera: GVCP/GVSP are both UDP, and `netsh portproxy` is TCP only, so there is nothing to forward** |
| T4 | Camera attached to a lab computer (USB or vendor-wrapped GigE) | `stream` | an MJPEG relay process on the lab computer |
| T5 | Vendor-SDK camera (GigE Vision/USB3 Vision) | splits — see below | T5a: nothing, resolves to T4. T5b: a GenICam capture shim; `cv2.VideoCapture` cannot open this camera at all |
| T6 | Ethernet camera moved to the vision box | `device`/local | a NIC on the vision box on the camera's own subnet |

**Lead with the reassuring half: T1-T4, and T5a, need NO special support from this tool, because
every one of them resolves to either a bare device INDEX or an ordinary URL** — a forward and a
relay both terminate in a URL, a direct camera terminates in an index, and `--source` already
takes either — the code is topology-blind by construction. **T5b is not a matter of finding the
right flag.** It is a STOP:
`cv2.VideoCapture` cannot open a vendor-SDK camera under any flag, and the honest next step is the
vendor's own GenICam tooling plus a capture shim — separate work, not a runbook workaround.

### Worked example: this rig hit T5, and it resolved to T5a

The installed camera is a `DMK 33GP1300` — The Imaging Source, monochrome, GigE Vision, serial
`5810436` — chosen because walking through how IT resolved is more useful to the next reader than
a topology diagram alone.

1. **Read the model string before touching a cable.** `DMK` = mono, `DFK` = colour; `33G` = GigE
   Vision, `33U` = USB3 Vision; the trailing number is the serial, and it is the handle a GenICam
   library selects the device by. Classify your own camera from its label before assuming a
   failed capture means anything about topology.
2. **Run `ffmpeg -list_devices true -f dshow -i dummy` FIRST — before describing any shim.** This
   is the one command that decides T5a vs T5b. Vendor DirectShow wrappers exist — The Imaging
   Source ships one — and where one is installed, the camera presents as an ordinary capture
   device and the T4 relay works with **no code change at all**. This command writes nothing to
   disk; `Error opening input file dummy` at the end is the command's normal, expected ending, not
   a failure.
3. **The port-forward does not rescue this class of camera.** GVCP (control) and GVSP (stream) are
   both **UDP**, discovery is broadcast, and `netsh portproxy` carries TCP only — T3 is
   inapplicable to a GigE Vision camera for exactly this reason, stated here and in the table above
   so it is not rediscovered by trying it.
4. **T6 is usually the right answer when the wrapper is ABSENT.** GigE travels over an ordinary
   Ethernet cable, so moving that cable to the vision box (or adding a NIC there) removes the lab
   computer, the relay, and the unsupervised second process from the path entirely. Two standing
   requirements: same L2 segment, and MTU 9000. **GigE Vision packet loss shows up as dropped
   frames, not as an error** — the `--capture-only` baseline above is what catches that, not a log
   line.

Two facts about this class of camera specifically, because nothing else will surface them:

- **A mono camera needs a 3-channel expansion before DLC.** State it as a required step; a model
  trained on colour footage will also behave differently on mono input, for reasons no plumbing
  fixes.
- **GigE Vision allows one primary application plus multicast monitors.** If acquisition software
  must keep recording while MICS also reads the feed, that is the escape hatch — a configuration
  change on the recorder, not a fight over the device, and not something a DirectShow camera can
  offer at all.

### Three things that belong here verbatim, because each is a silent failure

- **Forwarded RTSP over a TCP-only port-forward needs, on the vision box:**

  ```
  set OPENCV_FFMPEG_CAPTURE_OPTIONS=rtsp_transport;tcp
  ```

  — `netsh portproxy` carries TCP only and RTSP media defaults to UDP, so without this the capture
  opens and simply never delivers a frame; no error names the cause. The forward itself, on the lab
  computer (cmd's `set VAR=` then `%VAR%` idiom, so nothing wraps mid-paste):

  ```
  set LISTENIP=<lab-lan-ip>
  set CAMIP=<camera-private-ip>
  netsh interface portproxy add v4tov4 listenaddress=%LISTENIP% listenport=8554 connectaddress=%CAMIP% connectport=554
  ```

  and its undo: `netsh interface portproxy delete v4tov4 listenaddress=%LISTENIP% listenport=8554`.
  **Write footprint: the `add` rule persists until deleted; the `delete` command removes it; the
  `OPENCV_FFMPEG_CAPTURE_OPTIONS` line is a process-local environment variable and writes nothing.**
  (Per this rig's own worked example above, this is T3's case and does not apply to a GigE Vision
  camera — kept here for the IP-camera case it does apply to.)
- **Relay in MJPEG, never H.264/RTSP — per-frame coding means no GOP buffering to wait on.** The
  relay PUSHES the feed to whatever is listening for it, rather than waiting to be asked —
  `set DEV=`/`%DEV%` keeps the device name out of a long wrapped line:

  ```
  set DEV=<device>
  ffmpeg -f dshow -i video="%DEV%" -c:v mjpeg -q:v 5 -f mpjpeg tcp://<listener-ip>:<port>
  ```

  **Why pushed, not a blocking wait for a client:** see the ACQUISITION section below for the named
  trap this avoids and the full reasoning (D-88). Downscaling at the relay to the model's input
  size is free bandwidth saved, not a quality compromise worth avoiding.
- **A USB/DirectShow camera is usually exclusive-access: the relay and any other recorder cannot
  both hold it.** If the lab computer is also recording from the camera with separate software, a
  relay started alongside it fails with a message indistinguishable from an unsupported capture
  mode — a one-second `ffmpeg ... -t 1 -f null -` probe tells the two apart. **When this machine
  must both record an archival file AND relay live — which is this runbook's NORMAL case now, not
  an edge case — see the ACQUISITION section below: one `ffmpeg` process, a `tee` fan-out to a
  segmented file and a pushed delivery leg, and a generated PowerShell supervisor. Never two
  processes, and never a flag that blocks the file from growing.** A GigE Vision camera has the
  extra multicast-monitor escape hatch a DirectShow device does not (above).
- **Never install a GStreamer-enabled OpenCV to reach a machine-vision camera.** This is the same
  second-`cv2` clobber the live-view section below forbids for a different reason — `cv2.VideoCapture`
  does not need it, because a GenICam library hands frames over as plain numpy arrays, and the
  vendor's own DirectShow wrapper is what gets `cv2` there in the T5a case anyway.

**Prove any URL in VLC before `dlc-link-live` ever sees it.** Opening the same URL in VLC Media
Player separates a wrong network path from a wrong tool's flag in about ten seconds, and costs
nothing to try first. **The relay must never run on the Pi** — the Pi is running the FDA, and
video encoding on that host trades the thing under test for convenience; this is the same
prohibition `D-66` states for the sender itself.

No latency figure appears in this section, and none should be added to it: everything above is
about where buffering comes from, not a measurement of how long it takes. The only numbers this
runbook ever reports are the measured rates in the CAMERA section above.

---

## ACQUISITION — recording the footage, not just relaying it (D-88)

Every Windows command in this section is short `$var=` assignments plus an argument array
(`$a=@(...)` then `Start-Process -FilePath $ff -ArgumentList $a`), never one long line. Long
single lines wrap on paste in a Windows terminal, and that wrapping caused two real failures in
the 2026-09-10 rig session (`38-HARDWARE-VALIDATION.md` rule 3, defect 8.3). `dlc-link-relay`
(below) generates exactly this shape for you — you are not expected to hand-write it.

**The trap, named once here and nowhere else in this document:** a listening output blocks
ffmpeg's output initialisation until a client connects, and ffmpeg does not finish opening ANY
of its outputs until initialisation completes. So a combined record-and-relay invocation that
listens for its delivery leg **does not begin recording until somebody is watching** — with no
error, and a file that simply never grows. For an archival record that is the worst available
failure mode, and it is the reason this section's recorder always PUSHES its delivery leg instead.

### 1. Why the relay now records

Acquisition is MICS's own deliverable now, not IC Capture's by-product. One consequence: the
footage survives a dead network, a powered-off vision box, a crashed DLC run, and a closed
notebook — all four of which cost the session under the old relay-only arrangement, because none
of them is allowed to touch the file leg.

### 2. The precondition — read this before running anything

DirectShow access is **exclusive** (`38-HARDWARE-VALIDATION.md` §8.4): IC Capture and this
recorder cannot both hold the camera. Before starting:

- **Close IC Capture.** The error it leaves behind if you do not (`Could not run graph ...`) is
  the same one an unsupported capture mode produces — a one-second `ffmpeg ... -t 1 -f null -`
  probe is how you tell the two apart.
- **Set exposure, gain and the ROI in IC Capture FIRST, then close it.** Camera properties are
  vendor-only; a fresh ffmpeg inherits whatever IC Capture left in the driver (§2.4). Adjusting
  any of them mid-session means stopping the recorder, reopening IC Capture, changing the value,
  closing IC Capture again, and restarting the recorder — never editing them while ffmpeg holds
  the device.
- **Ask before taking the camera if it is already recording someone else's data.** On this rig,
  IC Capture is configured to record to `D:\Inbar\Data\MethodsCourse\...` for a different
  researcher's work. Starting this recorder takes that instrument. Confirm with the owner first;
  this is a social precondition, not a technical one, and it is first on purpose.

### 3. The shape of the command

One `ffmpeg` invocation, fanned out through the **`tee` muxer** — never two plain `-map` outputs,
because two plain outputs would share ffmpeg's muxing loop and a blocked delivery sink would
backpressure the file sink too, stalling the recording for the same reason a listening output
does. The file leg (`-f segment`, a relative, strftime-templated filename pattern) is PRIMARY and
carries **no** `onfail` — if the recording fails, the run should stop being believed. The
delivery leg carries **`onfail=ignore`**, so a dead network, a powered-off vision box or a
crashed DLC run costs the live view and nothing else:

```
dlc-link-relay --device "<DirectShow friendly name>" --segment-pattern "rig-%Y%m%d-%H%M%S.mkv" ^
  --segment-time 20 --delivery "tcp://<vision-box-ip>:<port>" --transport mpjpeg-tcp
```

`dlc-link-relay` writes NOTHING by default — it prints the ffmpeg argv and a paste-ready
PowerShell array block, for you to run on the lab computer. `--transport` has **no default** on
purpose: the measured answer (which candidate cannot stall the file leg under a slow consumer,
not merely a dead one — `onfail=ignore` only covers a FAILED sink) lives in
`38-ACQUISITION-VALIDATION.md` §3. Do not assume one.

### 4. `-fps_mode passthrough` is mandatory, not tuning

ffmpeg's default frame-rate handling may duplicate or drop frames to fit a constant output rate.
With that in play, "were all frames saved?" has no answerable form — the file's frame count would
no longer correspond to what the camera delivered. `dlc-link-relay` always emits `-fps_mode
passthrough` (per-stream in the two-stream escalation below); there is no flag that removes it.

### 5. Segmented output, and the MJPEG/training-footage quality choice

The file leg is **segmented** (`-f segment`), so a restart opens a NEW file instead of leaving
one truncated file of ambiguous length. Matroska, because every MJPEG frame is a keyframe, so a
segment cut is exact and a truncated segment is still readable — a truncated MP4 can be missing
its index instead.

**The footage this recorder writes IS the DeepLabCut training set for this camera** — there is no
trained model for it yet, and the file leg's quality is therefore a first-class requirement, not
a tuning knob to leave at the cheap default. `tee` performs only ONE encode per mapped stream, so
the delivery leg's cheap MJPEG quality and the file leg's archival quality are the SAME encode
unless you ask for otherwise: pass `--delivery-codec` (different from `--file-codec`) to escalate
to the two-stream `select=` form, which maps the video stream twice and encodes it twice — one
stream per leg, each independently tunable via `--file-extra`/`--delivery-extra`. Leave
`--delivery-codec` unset for the cheap single-encode form; never let the archival file silently
inherit the delivery leg's quality just because that was the path of least resistance.

### 6. The supervisor — PowerShell, never an interpreted-language runtime

The lab computer has no Python environment and D-66 chose ffmpeg specifically so it would never
need one. The restart supervisor is therefore **PowerShell text**, and `dlc_link` GENERATES it on
a different machine — it never runs there:

```
dlc-link-relay --device "<name>" --segment-pattern "rig-%Y%m%d-%H%M%S.mkv" --segment-time 20 ^
  --delivery "tcp://<vision-box-ip>:<port>" --transport mpjpeg-tcp --max-restarts 3 ^
  --print supervisor --out .\mics-acquire-rig.ps1
```

*Writes: one file, at the path this command echoes.* Run the generated `.ps1` on the lab
computer. Every restart attempt gets its OWN `-RedirectStandardError` log file (named with a
timestamp and the attempt number) because that log is witness 3 of the completeness procedure
below and `-RedirectStandardError` truncates on each new run — reusing one path would lose every
attempt but the last. The restart loop is bounded (`--max-restarts`) and prints the exit code and
the log path when it gives up, rather than spinning on a camera that is permanently gone.
`scripts/mics-acquire.ps1` in this repository is a checked-in reference copy, held
byte-identical to the generator's own output by a test — never hand-edit it.

### 7. The completeness procedure

Run after any session, or while reviewing one. Four independent witnesses, two of them from a
DIFFERENT machine than the other two:

| Witness | What it is | Where it comes from | Machine |
|---|---|---|---|
| W1 | ffmpeg's final `frame=` total | the captured log's last `^frame=` line | lab computer |
| W2 | summed `nb_read_frames` over every segment | `ffprobe -count_frames` | lab computer |
| W3 | count of `frame dropped` lines | the same captured log | lab computer |
| W4 | `frames_read` from `dlc-link-live`'s own summary | its printed output | vision box |

**Capture the log at ffmpeg's DEFAULT verbosity.** Never pass `-v error` to the recorder — that
would suppress `frame dropped` entirely and make W3 pass vacuously, which is the worst kind of
green. `dlc-link-relay`'s builder never emits `-v`/`-loglevel` for exactly this reason.

Apply this decision table as written — do not widen any tolerance after the fact:

| Observation | Verdict |
|---|---|
| `W1 != W2` | DEFECT — the muxer or the disk lost frames ffmpeg believed it had written. |
| `W3 > 0` | DEFECT — frames were delivered by the camera and lost at the capture buffer; the encoder or the disk cannot keep up. |
| `W3 == 0` and `W1 == W2` and `W2 < 30 × duration` | The camera delivered fewer frames than nominal. Under auto-exposure this is NOT a loss — record the delivered rate (`W2 / duration_s`) together with the exposure state. |
| `W4 > W1` | DEFECT, and an impossible one — the consumer cannot have read more frames than the recorder muxed. Re-check both numbers come from the same interval. |
| `W4 < W1` | EXPECTED, not a defect — the delivery leg is droppable by design (`LatestSlot` keeps only the newest frame). This is the simultaneity witness, not an equality. |

The measured transport, encoder, and both completeness runs (auto-exposure as found, and with
exposure pinned) are recorded in `38-ACQUISITION-VALIDATION.md` §3–§5, attributed there rather
than guessed here.

### 8. The auto-exposure caveat

Auto-exposure and auto-gain are **ON** on this rig (`Auto Reference 173`, from the `.iccf`). Once
exposure passes roughly 33 ms the camera cannot sustain 30 fps, so the expected frame count for a
run is "the rate actually delivered over that interval", never a constant `30 × duration` — a
shortfall under auto-exposure is not automatically a dropped frame (see the decision table
above). Pinning exposure before a session is how the nominal comparison becomes sharp; that is a
rig decision made in IC Capture, never a code change. Exposure cannot be read DURING a run without
the vendor SDK — record it before the run and after, and say so rather than implying live
visibility you do not have.

### 9. What this does not deliver

**Simultaneous IC Capture and MICS acquisition.** That remains D-75's multicast-monitor hatch — it
needs the vendor GenICam stack (`imagingcontrol4`) and the CAM-17 / T5b build this phase avoided.
Recording at the source makes IC Capture *less* necessary (the footage exists without it) but does
not make it concurrent. Stated once, here.

### 10. Write footprints, and rollback

Every `dlc-link-relay` invocation above writes nothing unless `--out` is given; the commands you
paste into PowerShell are what actually writes segments and logs, and `38-ACQUISITION-VALIDATION.md`
§0a records one row per command issued on the rig with its write footprint. To roll back: stop
ffmpeg, reopen IC Capture and confirm it reacquires the camera, delete the segment and log
directories, remove any firewall rule the chosen transport needed, restore the camera's original
auto-exposure/auto-gain settings if you changed them for a pinned-exposure run, and delete the
generated supervisor script.

No latency, jitter or drift figure appears anywhere in this section, and none should be added:
everything above is counts, sums and counts-per-second, never a timing measurement.

---

## LIVE VIEW — watching the annotated frames while the task runs

- **`--view` turns on rendering; `--view-sink notebook` or `--view-sink mjpeg` chooses where.**
  `notebook` needs IPython and renders inside a running Jupyter cell. `mjpeg` needs **nothing
  installed** — it is a stdlib `http.server` bound to `127.0.0.1` ONLY, opened in any browser on
  the SAME machine running `dlc-link-live`. Choose `mjpeg` whenever you are unsure Jupyter is safe
  to install into your DLC environment (see `python -m mics_link.selfcheck`'s pyzmq-upgrade warning
  in the numbered steps above — the same caution applies to any new package in that environment).
- **Never install `opencv-python` to get a viewer window.** This environment ships
  `opencv-python-headless`, which has no `imshow` — both packages provide the same `cv2` import
  name, and whichever installs SECOND silently overwrites the first, taking the whole DLC stack
  down with it (the exact defect class `35-HARDWARE-VALIDATION.md` warns about for this
  environment generally). Both shipped sinks render without any interactive display window at
  all — `DLCLive(display=False)` stays pinned in this tool's own code and is not something
  installing a different OpenCV would change.
- **The overlay is YOUR OWN authored numbers, and every frame says so.** `--overlay
  "nose_x>0.50,nose_likelihood>0.6"` is parsed and evaluated locally by this tool, never read from
  the task definition's own `fda_json` — the Pi evaluates its own FDA conditions independently,
  from its own tracker values, and the two can legitimately disagree for a moment (different
  poll times, different thresholds, or simply because the overlay is a debugging aid and the FDA
  condition is the ground truth the run actually gates on). Every frame with an overlay carries the
  label "authored locally, not read from the task definition" for exactly this reason.
- **Telling "the model lost the mouse" from "the viewer stopped" from "the FDA state is
  unavailable" apart matters, and the status block is what tells them apart.** A keypoint reading
  `likelihood≈0.0` is the model saying it cannot find that bodypart on THIS frame — the viewer and
  the sender are both still running. The viewer's OWN status (not a keypoint value) going stale
  means the render thread itself stopped, which is a different failure with a different fix. The
  FDA state line reading "unavailable" means the poll to the orchestrator or ElasticSearch failed
  or returned nothing — it does not mean the run stopped, and `pilot_state.py`'s fail-soft
  fetchers never show a stale reading as current specifically so this distinction stays legible.
- **The FDA state comes from TWO sources, not one, and that is why it needs both to show anything
  at all.** The orchestrator's own `state` field (`GET /pilots/live`) carries only the pilot's
  COARSE `IDLE`/`RUNNING` status — it has no idea what FDA state the run is currently in. The FDA
  state NAME itself comes from a `state_transition` document in ElasticSearch, and the
  orchestrator is what supplies the `subject_key` that filters that ElasticSearch query down to
  the right run. Both `--orchestrator-url` and `--es-url` are optional, and the viewer works with
  either, both, or neither configured — it just shows progressively less of this picture.
- **Write footprint: unchanged from the rest of this tool.** Neither sink writes a file; the
  `mjpeg` sink serves a socket and nothing else.

---

## KNOWN ROUGH EDGES

Named here rather than left for the next reader to rediscover at cost:

- **`uniquebodyparts` are unreachable live**, for every model — see the correction above. The
  reader that would change this is real, recorded future work that does not exist yet.
- **`mics_link.selfcheck` emits a cosmetic `RuntimeWarning` when run as `python -m
  mics_link.selfcheck`.** `__init__.py` already imports `selfcheck` (because `connect()` calls it),
  so `runpy` finds the module already loaded. The check still runs and still compares against the
  frozen hash; the warning is noise, not a failure (`35-HARDWARE-VALIDATION.md` §9b).
- **`dlc-link-convert --out` refuses a path inside the `.h5`'s own directory, even when that
  directory is a scratch folder and not a DLC project at all** (§9d). The guard keys on "the
  `.h5`'s own directory OR a project root," which is broader than its intent. **Not fixed in this
  phase.** Pass `--out` to a directory elsewhere.
- **Long multi-flag commands break when pasted into `cmd.exe`** (§9e) — a paste can truncate
  mid-line and execute a fragment, sometimes producing `The system cannot find the path
  specified.` with no indication why. Mitigation used throughout this document: `set VAR=...` then
  `%VAR%`, never one long inline command.
- **An entry/exit transition pair on the same continuous signal needs an explicit hysteresis
  band, and nothing in the FDA editor or validator enforces this** (§5c). Without one, the
  transitions fire, the run LOOKS healthy, and only the `armed`-state dwell-time distribution
  reveals the fault — run 587's first attempt produced dwell times as short as 4 ms from a 0.05
  band; the corrected version below used a 0.10 dead band per axis and produced dwell times in
  whole seconds:

  ```
  wait -> armed : likelihood > 0.6 AND x > 0.50 AND y > 0.50
  armed -> fired: x < 0.40 OR y < 0.40
  ```

  This is a property of any entry/exit pair on a continuous signal, not of this project's
  particular thresholds — pick your own numbers off your own measured distribution (the numbered
  steps above), but leave a comparable dead band between the entry and exit conditions.

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
  the sender** — the opposite order from the `required: true` case. `example, from the MultiMice
  project:` that project's standing `dlc_cam1` fixture on pilot 3 is configured `required: false`,
  so run first, then sender was the order that applied there; read YOUR OWN `source_id`'s config
  row before assuming the same order applies to yours.

**The worked coordinate condition (D-19).** Coordinates use `stale_policy="hold_last"`, which
means a coordinate signal alone is unsafe to gate on — its value survives past the moment
tracking is actually lost, silently. Likelihood uses `stale_policy="return_default"` with
`default=0.0`, which is safe to compare in either direction (0.0 always means "no confidence").
**Every condition reading a coordinate must be ANDed with that same keypoint's own likelihood
signal.** A worked example, using a reachable multianimal/single-animal bodypart (never a
`uniquebodypart` — see the correction above) and a placeholder `<source_id>`:

```
<source_id>.nose_likelihood > 0.6  AND  <source_id>.nose_x > 0.3
```

Substitute your own declared `source_id` and bodypart name; `nose` here is an example, not a
requirement. Never gate a transition on a coordinate alone.

**Replay, for reproducing a run without the camera.** `mics-link-replay` plays a recorded
`(t, signal, value)` file through the SDK client at real time, a scaled rate, or as fast as
possible — the same mechanism `sdk/README.md` §7 documents for any device. Use it to re-run a
recorded DeepLabCut session's signals deterministically, without the vision box or the model
present, for debugging an FDA transition after the fact.
