# Phase 38 Context — Live camera source + annotated live view

Written 2026-09-02, straight out of the Phase 35 rig session. Everything here was observed, not
assumed; where something is inferred rather than measured it says so.

---

## 1. What the researcher actually wants

> "Something I can run next week when I have the camera up and running filming the setup. If I can
> see the annotated video on the screen (in like a Jupyter notebook) that would be great. Make a
> nice product where one can run the live model on the live camera and look where the mouse goes
> while the task is running on the Pi."

Read that as **three** deliverables, not one:

1. A **camera** frame source (not a file).
2. A **viewer** — annotated frames, live, in a notebook, next to the pilot's FDA state.
3. A **model-agnostic** path, so it works for the next model and the next bodypart selection
   without re-deriving anything by hand.

The deadline is real: the camera is being installed and the researcher expects to run this the
week of **2026-09-08**. A plan that delivers (1) and (2) for one camera beats a plan that delivers
a general framework late.

---

## 2. What is already proven and must not be re-litigated

Phase 35's rig session (`35-HARDWARE-VALIDATION.md`, commit `8d724b0`, runs 587 and 588) proved
the entire chain **downstream of the frame source**:

```
video file -> DLCLive inference (GPU) -> DLCProcessor -> decimation
           -> mics-link ZMQ -> pilot 3 :5601 -> dlc_cam1 lib -> FDA -> ElasticSearch
```

Run 588: 232 `state_transition` documents, `nose_x` median 0.509, `nose_y` 0.448, likelihood 0.786.
None of that changes in this phase. The only new thing is where frames come from and who can see
them.

Live DB objects, still current:

| Object | Value |
|---|---|
| Hardware lib | 243 `dlc_cam1` v2 (id **189**) — `nose_likelihood`, `nose_x`, `nose_y` |
| Task definition | 626 `dlc_demo`, toolkit 157, pins `{"45": 41, "243": 189}` |
| Pilot config row | 41, `router_bind`, port **5601**, `required: false`, `stale_ms` 3000, `egress_fail_threshold` 3 |

---

## 3. The five concrete gaps, with file references

### 3a. Camera capture cannot be opened at all

`dlc_link/src/dlc_link/live.py:229`:

```python
cap = cv2.VideoCapture(args.video)
```

`--video` is declared with no `type=`, so it is always a `str`. `cv2.VideoCapture` treats a string
as a path and an **int** as a device index, so `--video 0` opens a *file* named `0` and fails.

- **Local camera** needs the argument coerced to `int` when it is all digits.
- **RTSP/HTTP stream URLs already work today, unchanged**, because those are strings by design.
  If the rig camera can expose a stream URL, that is the zero-code path and should be tried first.
- Naming: `--video` is now a misnomer. Consider `--source` with `--video` kept as an alias, or
  accept that renaming a flag mid-flight costs more than it buys. Planner's call, but state it.

### 3b. Pacing inverts

`live.py:272-283`: a `Pacer("realtime")` plus `fps = args.fps or cap.get(cv2.CAP_PROP_FPS)`.

`--fps` exists because a video **file** runs unpaced — `cap.read()` returns instantly and the loop
would blast frames at whatever the GPU manages. Phase 35 used `--fps 30` for exactly this.

A camera is the opposite: `cap.read()` blocks until the sensor delivers, so the camera paces
itself and an additional pacer double-throttles. Worse, **cameras frequently misreport
`CAP_PROP_FPS`** (0, 30 regardless of actual, or a nominal max), so the fallback cannot be trusted
either. The plan needs an explicit answer for what paces a camera source, and it is probably
"nothing".

### 3c. Real-time keep-up becomes a correctness property

With a file, slow inference just means the run takes longer — no information is lost. With a
camera, frames the loop cannot service are **gone**, signals go stale, and `stale_ms: 3000` on the
pilot config means the Pi starts serving defaults.

`run_video_loop` already returns `behind_count` and it is already printed in the summary
(`live.py:296-305`). What is missing is that no one has ever measured it against a real camera,
and there is no threshold at which the tool says "this camera is too fast for this model on this
GPU". That number is the phase's honest pass/fail criterion.

Related: the Phase 35 budget arithmetic is `3 signals × 10 Hz = 30 msg/s` against a proven
~60 msg/s envelope. Decimation caps the *outbound* rate, so a faster camera does not increase ZMQ
load — it increases *inference* load. Those are different limits and the plan should not conflate
them.

### 3d. There is no viewer, and the obvious way to build one is blocked

Hard environment constraint, verified on the vision box:

- The env has **`opencv-python-headless` 4.11.0.86**, which ships **no `imshow`**.
- It must **not** be replaced with `opencv-python`. Both packages provide the same `cv2` module;
  installing both means whichever landed last wins and the other's files are clobbered. The whole
  DLC stack in that env sits on the headless build.

So the viewer renders **in-notebook** — `IPython.display` with JPEG-encoded frames, or an
equivalent — never a `cv2` window.

Also: `live.py:268` pins `display=False` on the `DLCLive` constructor deliberately (D-47, "never
left to DLCLive's own default"). **Do not turn that on** as a shortcut to a viewer; DLC-Live's own
display is a separate mechanism with its own behaviour and the pin exists for a reason.

What the viewer should show, per the researcher's own words ("look where the mouse goes while the
task is running on the Pi"):

- the live frame with the declared keypoints drawn on it, each annotated with its likelihood
- some visual indication of the ROI / threshold the FDA is gating on, so the researcher can see
  *why* it fires
- the pilot's current FDA state, live
- a frames-read / frames-inferred / behind counter, so keep-up (3c) is visible rather than
  inferred after the fact

Where the FDA state comes from is an open design question: the orchestrator exposes
`GET /pilots/live` (used throughout the Phase 35 session and returns `active_run` with `id`,
`session_id`, `subject_key`, `task_def_id`), and ElasticSearch has the `state_transition`
documents. Polling the orchestrator is simpler; ES is authoritative. Pick one and say why.

### 3e. The frame loop never terminates on a camera

`live.py:276-283`:

```python
def _frames():
    while remaining_frames:
        yield remaining_frames.pop()
    while True:
        ok, frame = cap.read()
        if not ok:
            return
        yield frame
```

For a file, `cap.read()` eventually fails and the loop ends cleanly, printing the summary. A
camera never returns `not ok` under normal operation, so the only stops are `--max-frames` and
Ctrl-C. In a notebook, Ctrl-C is not the natural gesture — interrupting the kernel is, and that
needs to leave the ZMQ link and the capture device closed properly. Note that `live.py` already
uses `try/finally` around the loop for `live.close()` / `cap.release()`, which helps.

---

## 4. Model-agnostic: what makes this hard

The pose row order is **not discoverable** from the DLC-Live runner — Phase 35's probe reported
`bodypart ordering: NOT FOUND (tried attributes: cfg, dlc_config, pose_cfg)`. For the MultiMice
model the order was established *indirectly*: `config.yaml`'s `multianimalbodyparts` is the only
10-item list in the project and the pose array had exactly 10 rows, so the mapping was
corroborated rather than measured.

That reasoning does not generalise. A different project may have several same-length lists, or a
single-animal project where `bodyparts` is flat. So for any new model the researcher must run:

```
probe  ->  read the row count and order  ->  dlc-link-generate --pose-order ...  ->  re-probe
```

and confirm `row_count_match=True` and `POSE_ORDER_SOURCE: 'probe'`. Today that loop lives in a
runbook written around one project, and one step of it (`--probe-pose` requiring `--signal-map`)
reads as a contradiction — the runbook says probe before generating, but the probe compares
against a map that generation produces. The chicken-and-egg is real and should be documented or
removed.

Also carried from Phase 35 §4: `pose.shape` was `(10, 5)` where DLC-Live's docs say
`(num_bodyparts, 3)`. The probe reads x/y/likelihood from the first three columns; **what columns
4 and 5 carry is unknown**. Nothing depends on them today, but a different model might order them
differently and nothing would notice.

---

## 5. Carried constraint — NOT in this phase

DLC-Live's PyTorch runner reads only the bodypart head:

```python
# dlclive/pose_estimation_pytorch/runner.py:211
batch_pose = self.model.get_predictions(outputs)["bodypart"]["poses"]
```

The `"unique_bodyparts"` head (built at `paf_predictor.py:190-201` as `[x, y, prob, id]`) is
discarded. `single_animal` is unrelated — `runner.py:223-228` merely does `pose = pose[0]`.

Consequence: **`uniquebodyparts` — LEDs, arena corners, microphone markers — are unreachable by
any live MICS task**, regardless of `single_animal`. Offline `analyze_videos` reads both heads,
which is why they appear in `_el.h5` under the individual named `single` and look available.

Fixing this means subclassing `PyTorchRunner` inside `dlc_link` to concatenate the unique head.
**That is separate work and explicitly not this phase**, but the plan should not design anything
that would have to be undone when it lands.

---

## 6. Environment facts (vision box), verified

| Item | Value |
|---|---|
| Host / env | `YizharGPU12`, conda env `mics-dlc`, clone of `DEEPLABCUT` |
| Python | 3.12.13 |
| torch / torchvision | 2.5.1 / 0.20.1 (CUDA, RTX 3060) |
| deeplabcut-live | 1.1.0 (installed 2026-09-02; pulled only `colorcet`) |
| opencv | `opencv-python-headless` 4.11.0.86 — **no imshow** |
| numpy | 1.26.4 (`<2` pinned by deeplabcut-live) |
| pandas / tables | 2.3.3 / 3.11.1 |
| `mics-link` / `dlc-link` | 0.1.0, installed from wheels |
| Wheel staging | `\\isi.storwis.weizmann.ac.il\labs\yizharlab\Mics\wheel\` (both wheels, verified byte-identical to `~/mics-dist/`) |
| Jupyter | **NOT verified present in `mics-dlc`.** The notebook viewer may need `jupyterlab`/`notebook` + `ipywidgets` installed. Check before planning around it, and dry-run any install — this env's torch must not be disturbed. |

Distribution is by **wheel over SMB**, not git — the repo is public and `origin/claude` is far
behind. Any new code in `dlc_link/` reaches the vision box as a rebuilt wheel.

---

## 7. Process constraints (standing project rules)

- **Never run git, Python, or process control on any Pi.** Hand the user the command and wait.
- **Never write into a researcher's DLC project directory.** Reading is always fine. Phase 35
  violated this (see `35-HARDWARE-VALIDATION.md` §8) because `export_model` writes
  `exported-models-pytorch/` and the copy step was skipped. Take a manifest before and after.
- The vision box is a **Windows** machine driven by the user; every command must be
  copy-pasteable into `cmd.exe`. Long single-line commands **break on paste** — the Phase 35
  session hit this repeatedly and worked around it with `set VAR=...` then `%VAR%`. Plans that
  hand the user long commands should use that idiom.
- State the **write footprint** of every command handed over, or say it writes nothing. The
  `dlc_link` CLIs already do this; ad-hoc commands must too.
- **No latency claims anywhere.** Counts and rates only. Clock-domain comparison belongs to
  Phase 28.

---

## 8. Sequencing

Must land **before Phase 37**, which extracts `sdk/` + `dlc_link/` into a dedicated client repo.
This phase modifies `dlc_link/` substantially; doing it after the extraction means doing it twice
or doing it in a repo the backend no longer owns.

Depends on Phase 35. Phase 35 is itself **not yet verified** — its `35-07` and `35-08` remain
open, and `35-HARDWARE-VALIDATION.md` §7 records 3 UNPROVEN and 3 NOT DONE truths. Phase 38 does
not need those closed to proceed, since it builds on what was proven (the chain works), not on
what was not (browser authoring, corner geometry, copy discipline).

---

## 9. Open questions for planning

1. **Stream URL or device index first?** If the rig camera exposes RTSP, most of gap 3a
   disappears. Worth establishing before designing around device indices.
2. **Where does the viewer get FDA state** — poll the orchestrator's `/pilots/live`, or read
   `state_transition` documents from ES? Simpler vs authoritative.
3. **Does the viewer run in the same process as the sender, or alongside it?** Same-process is
   simpler to keep in sync but couples the notebook's liveness to the sender's. Alongside is more
   robust but needs a way to share frames.
4. **Is Jupyter even installed** in `mics-dlc`? (§6.) If not, the install must be dry-run first.
5. **What is the acceptance criterion for keep-up?** `behind_count == 0` is probably too strict
   for a real camera; some non-zero rate is fine. The number should come off a measurement, not a
   guess — the same discipline Phase 35 applied to likelihood thresholds after guessing wrong.
