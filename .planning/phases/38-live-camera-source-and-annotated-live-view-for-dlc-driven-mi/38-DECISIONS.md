# Phase 38 — Planning decisions

Written 2026-09-02 by the planner, from `38-CONTEXT.md`. **Every open question in `38-CONTEXT.md`
§9 is answered here.** None is left for the executor to decide mid-flight, and where an answer
depends on a fact only the rig can supply, the fact-finding is an early TASK (plan 38-04) rather
than a blocking assumption.

Decision IDs continue Phase 35's sequence (which ended at D-48), because these plans reference
D-27, D-29, D-42, D-44, D-46, D-47 and D-48 directly and a second numbering space would make those
references ambiguous.

---

## D-49 — One `--source` flag; `--video` kept as a working alias

`--video` is now a misnomer (`38-CONTEXT.md` §3a). `--source` becomes the canonical flag and
`--video` stays as an alias writing to the same `dest`, because:

- `--video` appears in `RUNBOOK.md`, in `35-HARDWARE-VALIDATION.md` §2, and in the researcher's
  own shell history. Breaking it buys a tidier flag and costs a failed paste on a Windows box
  during the one week the camera is up.
- Passing BOTH is an error (`exit 2`), not a silent precedence rule.

The classification (`device` / `stream` / `file`) is **decided in a pure function and printed**
before `cv2.VideoCapture` is constructed, so `--source 0` reporting `device index 0` is visible
rather than inferred from whether it worked.

## D-50 — The stream URL is tried FIRST, with the wheel already installed on the vision box

An RTSP/HTTP URL is a `str`, which is exactly what `cv2.VideoCapture` already receives, so **a
stream URL works today with `dlc-link` 0.1.0, unchanged**. Plan 38-04's first checkpoint therefore
asks the researcher to try the URL with the build already on the box, before any new wheel is
staged. If the camera exposes a usable stream, the researcher has a working camera run on day one
and every code change in this phase becomes an improvement rather than a prerequisite.

This does **not** make device-index support optional. The coercion is a handful of lines, the
answer may arrive after the code is frozen, and a USB camera plugged into the vision box is the
likelier physical arrangement. Both ship; only the ORDER of proving them is decided by the rig.

## D-51 — Pacing is a property of the source, not a flag default

- `file` → paced, exactly as today (`Pacer("realtime")` at `fps`). Unchanged behaviour, because
  an unpaced file blasts frames and Phase 35's whole proof rests on `--fps 30`.
- `device` / `stream` → **never paced by this tool.** `cap.read()` blocks on the sensor; a pacer
  on top of that double-throttles.
- `--fps` together with a camera source is a **refusal with a message that says why**, not a
  silent override. A researcher who copies the Phase 35 command line verbatim (it contains
  `--fps 30`) must be told, not quietly given a 30 Hz cap on a 60 Hz camera.
- `cap.get(CAP_PROP_FPS)` is **never** used as a fallback for a camera source. Cameras
  misreport it (`38-CONTEXT.md` §3b); it is printed as an observation, labelled unverified, and
  used for nothing.

## D-52 — A camera is read by a reader thread into a single-slot holder

The inference loop must always receive the **newest** frame. With a plain in-loop `cap.read()`
and a backend that buffers, a slow model reads progressively older frames: nothing is dropped,
nothing is counted, and the Pi is fed the past while everything looks healthy.

So for `device`/`stream` sources a dedicated reader thread calls `cap.read()` in a loop and puts
each frame into a **single-slot, drop-oldest holder** (`LatestSlot`). The inference loop takes
from that holder. The holder counts `overwrites` — and `overwrites` **is** the count of frames the
pipeline could not service. That is a real, honest keep-up number that does not exist today.

`cv2.CAP_PROP_BUFFERSIZE = 1` is attempted as well and its post-set value reported, because many
backends silently ignore it. It is a belt-and-braces measure; the holder is the actual mechanism.

File sources keep today's synchronous in-loop read. No thread, no behaviour change.

## D-53 — `behind_count` is reported as `n/a` for camera sources, never as `0`

`behind_count` is a `Pacer` counter (`sdk/src/mics_link/timing.py`). With no pacer there are no
`wait_until` calls, so it is structurally `0` — and a `0` printed next to the words "behind count"
reads as a pass. Camera runs print `behind_count: n/a (unpaced source)` and print
`frames_skipped` (D-52's overwrite count) instead.

## D-54 — The keep-up criterion is derived from a measurement; `--min-rate` has NO default

`38-CONTEXT.md` §9.5, and the same discipline `--likelihood-threshold` already follows (D-41):
Phase 35 guessed a threshold once and was wrong once.

The measurement is two runs over the same source for the same duration:

1. **baseline** — `--capture-only` (read frames, no inference, no sending): the rate the camera
   actually delivers. This is the number `CAP_PROP_FPS` cannot be trusted to give.
2. **with inference** — the ordinary run: `frames_inferred / duration_s`.

The reported keep-up figures are `frames_inferred/duration_s`, `frames_read/duration_s`,
`frames_skipped`, and the ratio against the baseline. `--min-rate` (frames/second) has **no
default**: when supplied, a run whose achieved inference rate falls below it prints a WARN line and
exits non-zero. The value is written into `RUNBOOK.md` (plan 38-05) only after 38-04 measures it,
and if 38-04 does not happen the runbook says "not yet measured" rather than carrying a guess.

These are counts and rates over one clock. **No latency is computed, printed or implied anywhere**
(carried from DLC-10).

## D-55 — A camera run terminates deliberately, four ways

`_frames()` ends only when `cap.read()` fails, which for a camera means never
(`38-CONTEXT.md` §3e). The four stops:

- `--max-frames` (exists today)
- `--max-seconds` (new; the notebook-friendly bounded run)
- a cooperative `should_stop()` callable, checked once per frame — this is what the notebook's
  `stop()` button and "interrupt the kernel" both drive
- `KeyboardInterrupt`, which must still run the existing `finally` that closes `live` and the
  capture device

And the inverse: a **transient** camera read failure must NOT end the run. `--read-retries`
(bounded, small default) retries before giving up; a `file` source's end-of-stream still ends the
run cleanly on the first failure, exactly as today. The two sources need opposite behaviour on the
same signal, which is why D-49's classification has to exist before this can be written.

## D-56 — The viewer shares the sender's process

Answering `38-CONTEXT.md` §9.3. Same process, because:

- the frame and the pose are both already in the loop; a second process needs a frame transport
  (shared memory or another ZMQ socket) that is new code with new failure modes, for no gain
- the researcher asked for one thing to start, not two

The coupling is bounded by one rule, which is a hard acceptance criterion: **the viewer can never
backpressure the sender and can never raise into the inference thread.** Frames reach the view
through a second `LatestSlot` (drop-oldest, non-blocking put); a slow, absent or crashed viewer
changes nothing about what the sender sends. The viewer's own exceptions are caught, counted and
displayed, never propagated.

## D-57 — Run identity from the orchestrator; the FDA state name from ElasticSearch

Answering `38-CONTEXT.md` §9.2. **Both**, with different jobs, because of a verified fact that
makes "poll the orchestrator, it is simpler" wrong on its own:

`GET /pilots/live`'s `state` field is the **pilot's coarse state**, not the FDA state.
`orchestrator/orchestrator/orchestrator_station.py:236-253` (`on_state`) writes whatever the pilot
reports into `redis pilot:<name> state`, and `orchestrator/orchestrator/api.py:24-56` reads it back
with a default of `UNKNOWN`; lines 214-228 seed it as `IDLE`/`RUNNING`. There is no FDA state name
anywhere in that payload.

The FDA state name exists only in ElasticSearch. `FiniteDeterministicAutomaton.py:17` emits
`Event(event_type='state_transition', event_data={"current_state": next_state_name})` — verified in
the Pi tree — and Phase 35 run 588 landed those documents in `event_log_v2` on `132.77.73.217`.

So:

| Source | Supplies | Rate |
|---|---|---|
| `GET http://<orchestrator>:9000/pilots/live` (no auth; `main.py:90` binds `0.0.0.0:9000`) | `connected`, coarse `state`, and `active_run` with `id`, `session_id`, `subject_key` | ~1 Hz |
| ES `event_log_v2` on `132.77.73.217:9200`, filtered by the `subject_key` the orchestrator just handed over, `event_type: state_transition`, newest first | `event_data.current_state` — the FDA state name | ~1 Hz |

The orchestrator hands over `subject_key` **verbatim**, which is what builds the ES filter — so
the viewer never has to reconstruct `bp_s<session>_r<run>` itself. That is the concrete reason both
are used rather than one.

Failure is shown, never hidden: either source unreachable renders as
`FDA state: unavailable — <reason>`. A previously-fetched value is **never** displayed as if it
were current. This is the same semantic as the phase-35 staleness rule and it is not negotiable:
the viewer exists to be trusted while an animal is in the rig.

Reachability of both from the vision box is **unverified** and is a discovery item in plan 38-04,
not an assumption. The viewer runs with either, both, or neither.

## D-58 — Two render sinks: in-notebook, and a localhost-only MJPEG server

`cv2.imshow` does not exist in `opencv-python-headless` 4.11.0.86, `opencv-python` must never be
installed beside it, and `DLCLive(display=False)` stays pinned (D-47). All three are carried
constraints, not choices.

- **Notebook sink (primary)** — `IPython.display` with JPEG bytes from `cv2.imencode`. This is
  what the researcher asked for by name.
- **MJPEG sink (fallback)** — stdlib `http.server` in a thread, bound to `127.0.0.1` only,
  serving `multipart/x-mixed-replace`. Writes nothing, needs no Jupyter, opens in any browser on
  the vision box.

The MJPEG sink is not gold-plating; it is the mitigation for D-59's hazard. It is ~60 lines and it
removes the phase's largest schedule risk entirely.

The **render core is sink-agnostic**: it produces JPEG bytes plus a status dict. Adding a third
sink later touches no drawing code.

## D-59 — Jupyter presence is discovered; any install is dry-run first and may not touch pyzmq

Answering `38-CONTEXT.md` §9.4. `jupyterlab`/`notebook`/`ipywidgets` are **unverified** in
`mics-dlc`. Plan 38-04 checks before anything depends on them.

The hazard is specific, not vague: **Jupyter depends on `pyzmq`**, and `RUNBOOK.md` step 2 already
says in writing that a proposed `pyzmq` upgrade is a STOP condition — `mics-link`'s own transport
is `pyzmq`. So any Jupyter install is `python -m pip install --dry-run` first, and is **refused**
if the resolver proposes to install, upgrade or downgrade `pyzmq`, `numpy` or `torch`. If it is
refused, D-58's MJPEG sink is the answer and nothing is installed at all.

## D-60 — The overlay carries the researcher's own numbers, and says so

The FDA's authored thresholds live in the task definition's `fda_json` on the backend. This phase
does **not** parse them, because doing so couples the vision box to a backend schema that Phase 37
is about to move out of this repo, for a display nicety.

Instead `--overlay "nose_x>0.50,nose_y>0.50,nose_likelihood>0.6"` draws the researcher's own
authored numbers as threshold lines and colours the keypoint when the clause set holds. The viewer
**labels this** `overlay: authored locally, not read from the task definition` so nobody mistakes
it for the Pi's ground truth. Honest and cheap beats coupled and impressive.

## D-61 — Nothing hardcodes a row count or a bodypart name

`38-CONTEXT.md` §5's unique-bodypart-head reader is explicitly out of scope, and this phase must
not build anything that reader would have to undo. Concretely, when a `PyTorchRunner` subclass
later concatenates the unique head, **the pose row count changes and nothing else does**:

- `POSE_ORDER` stays the single source of row order (the processor's guard already keys on it)
- the probe prints the OBSERVED row count; it never asserts 10
- the annotator draws whatever the signal map declares, for any row count

Proven by a test that annotates a 3-row pose and a 14-row pose with no code change.

## D-62 — `--probe-pose` no longer requires `--signal-map`

Defect 9c in `35-HARDWARE-VALIDATION.md`: the runbook says probe *before* generating, but the
probe compares against the map that generating produces. Fixed **in code, not in prose**:
`--signal-map` becomes optional under `--probe-pose`. Without it the probe prints the shape, the
row count, the discovered order (or that there is none), every column of row 0 including the two
uncharacterised ones (§4 sub-finding 2), and a paste-ready `--pose-order a,b,c` string. With it,
today's comparison still runs.

## D-63 — Version bump to 0.2.0, wheel rebuilt, staged by the USER

Distribution is by wheel over SMB (`38-CONTEXT.md` §6), not git. `dlc-link` **0.1.0** is already
installed on the vision box, so re-publishing 0.1.0 makes `pip install` a possible no-op and makes
`pip show dlc-link` useless as evidence of which build is running. The version becomes **0.2.0**;
`pip show dlc-link` then proves it.

The agent builds the wheel on the dev host and records its `sha256`. The **user** copies it to
`\\isi.storwis.weizmann.ac.il\labs\yizharlab\Mics\wheel\` and installs it. `mics-link` is
unchanged by this phase and is neither rebuilt nor restaged.

## D-64 — A before/after manifest of the DLC project directory is mandatory

`35-HARDWARE-VALIDATION.md` §8: the export wrote into the collaborator's project and truth 12's
guarantee could not be made retrospectively because no manifest was ever taken. Every vision-box
session in this phase takes one before and one after, and `Compare-Object` returning empty is a
recorded result, not an assumption. This phase runs no `export_model` at all — the model is
already exported — so the expected diff is empty by construction, which is exactly why the proof
is cheap here and worth establishing as the habit.
