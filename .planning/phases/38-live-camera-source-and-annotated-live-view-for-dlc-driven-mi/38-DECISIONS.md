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

## D-65 — Frame-source TOPOLOGY is a named taxonomy, separate from source KIND

`38-CONTEXT.md` §3f. D-49 classifies how OpenCV *addresses* a source (`device` / `stream` / `file`).
It says nothing about where the camera physically is, and the rig's arrangement — camera in the rig
room, GPU on `YizharGPU12` elsewhere — is not expressible in that vocabulary. So topology is named
explicitly, and each topology **resolves to** a kind:

| ID | Topology | Resolves to | What has to exist |
|---|---|---|---|
| **T1** | Camera direct to the vision box (USB / CSI) | `device` | nothing; `--source 0` |
| **T2** | Camera holds a routable IP on the lab LAN | `stream` | IT admits the device — may be refused |
| **T3** | IP camera on a private segment behind the lab computer | `stream` | a TCP port-forward, or a subnet route, on the lab computer |
| **T4** | Camera USB-attached to the lab computer | `stream` | an MJPEG relay process on the lab computer |
| **T5** | Vendor-SDK camera (GigE Vision / USB3 Vision) | **none** | a capture shim; `cv2.VideoCapture` cannot open it |

**T1-T4 require no code change in `dlc_link`.** A forward and a relay both terminate in a URL, and
`classify_source` already routes a URL to `stream` on `<scheme>://` (plan 38-01), which already
means unpaced, already means the newest-frame reader, already means non-terminal read failures. This
is the whole reason topology can be discovered late without holding up plans 38-01 through 38-03:
the code is topology-blind by construction, and that property is now deliberate rather than
accidental.

**T5 is a STOP**, not a branch. It is added to Task 2's stop conditions in plan 38-04. The honest
next step is the vendor's own tooling and a `FrameReader`-shaped shim behind the injected-capture
seam that plan 38-01 already builds — separate work, not this phase.

T2 is recorded but **not designed around**: the researcher reports that lab IT may refuse an unknown
device on the network, so a plan that depends on T2 is a plan that can be vetoed by someone outside
this project. T3 and T4 both keep the camera off the lab VLAN entirely, which turns that constraint
from a risk into a non-issue — the only host IT sees is the lab computer, which is already approved.

## D-66 — A lab-computer hop forwards before it relays, relays in MJPEG, and never runs on the Pi

Given T3 or T4, three sub-decisions, in this order:

**1. T3 (the camera has an IP): forward one TCP port; do not route the subnet.** Both work. The
forward is one command on the lab computer and changes nothing on the camera or the vision box:

    netsh interface portproxy add v4tov4 listenaddress=<lab-lan-ip>
      listenport=8554 connectaddress=<camera-private-ip> connectport=554

Full routing costs a reboot (`IPEnableRouter`), a persistent static route on the vision box, **and a
default gateway set on the camera itself** — without which packets arrive and replies have nowhere
to go, presenting as a capture that opens and then hangs. Routing earns that cost only when UDP or
the camera's own web UI is needed; forwarding port 80 alongside 554 gets the web UI anyway.

**The gotcha is recorded because it is silent:** `portproxy` carries **TCP only**, and RTSP puts its
media on UDP by default. The capture opens and never delivers a frame. So a forwarded RTSP source
requires, on the vision box, `set OPENCV_FFMPEG_CAPTURE_OPTIONS=rtsp_transport;tcp` — which fits the
`set VAR=` idiom §7 already mandates. This goes in the runbook, not in a comment.

**2. T4 (no IP exists): relay MJPEG over HTTP, never H.264/RTSP.** Port-forwarding is meaningless
when there is no endpoint to forward to — a USB camera has no IP, no port, no socket. The relay
re-serves frames, and the codec choice is the whole decision: H.264's GOP structure and B-frames
make the encoder buffer several frames before emitting anything, which is structural and not tunable
away. MJPEG encodes and decodes each frame independently. The cost is bandwidth, and it is
affordable: 720p30 raw is ~663 Mbps and 1080p30 raw ~1.5 Gbps (which does not fit on 1GbE at all),
while MJPEG is roughly 10-20x smaller — ~30-70 Mbps at 720p30. Downscaling at the relay to the
model's actual input size removes the question entirely.

Prefer `ffmpeg` on the lab computer over a Python relay, so that machine does not acquire an
OpenCV/torch stack it has no other use for:

    ffmpeg -f dshow -i video="<device>" -c:v mjpeg -q:v 5
      -f mpjpeg -listen 1 http://0.0.0.0:8080/

**3. The relay never runs on the Pi.** RecordingBox (.213) is in the room and is therefore tempting.
It is also running the FDA, it is what phases 32 and 33 exist to keep alive unattended, and T-38-37
in plan 38-04 already names starving its Tornado IOLoop as a hazard to FDA timing and STOP. Video
encoding on that host trades the thing under test for convenience. This is a prohibition, not a
preference.

**Carried hazard, recorded not solved:** a relay is a second always-on process on a second machine
in a 24/7 unattended rig, with no supervision story in this phase. `38-CONTEXT.md` §6 has no row for
the lab computer. If T4 is the answer, that host becomes phase-32/33 surface and should be recorded
as such rather than discovered later.

**No latency figure appears in this decision or anywhere downstream of it.** The mechanism above is
an argument about *where buffering comes from*, not a measurement. The only numbers this phase may
report remain D-54's counts and rates, and a hop simply becomes part of the baseline that D-54's
`--capture-only` run measures. Clock-domain comparison stays Phase 28's.

## D-67 — Topology is discovered FIRST, on the lab computer, before the wheel is built

D-65's branch decides whether the phase's premise holds at all (T5 falsifies it), and it is answered
by looking at hardware rather than by running anything this phase builds. It therefore moves to the
**front** of plan 38-04's checkpoint, ahead of the manifest, the wheel install and the stream test,
and it is explicitly a question about the **lab computer**, not the vision box — which is where the
plan previously pointed every discovery command.

The three questions that resolve everything, in order:

1. What is the camera's **make and model**? (Answers T5 vs everything else. An `arp -a` MAC prefix
   will do if the label is not to hand.)
2. What does the camera physically plug into, and does the lab computer's `ipconfig /all` show one
   NIC or two? (One NIC + USB → T4. Two NICs with a private range on the second → T3.)
3. Is the lab computer **also recording** from that camera? (`38-CONTEXT.md` §3f: DirectShow devices
   are typically exclusive-access, so under T4 a relay and a local recording cannot both hold the
   device. Resolutions, in preference order: the acquisition software already exposes a stream; or
   one `ffmpeg` invocation serves the network *and* writes the local file from a single capture; or,
   last resort, a virtual-camera splitter.)

These are questions, not commands, and none of them writes anything or needs the 0.2.0 wheel. Asking
them at the top costs nothing and can save the phase a week — against a 2026-09-08 deadline that is
the whole point.

**Address-space note for whoever configures T3:** use RFC1918 (`192.168.x`, `10.x`, `172.16-31.x`)
for the private segment. A camera addressed out of public space — `1.0.0.5` and the like — silently
breaks the lab computer's route to the real hosts in that range, months later and far from the cause.

---

## D-75 — The camera is identified: it is T5, and T5 splits in two

**Added 2026-09-06, after D-67's question 1 was answered from the camera's own label rather than
from the rig.** Numbered D-75, not D-68, deliberately: plan 38-06 §"Decisions registry" reserves
D-65 through D-74 for its own set, and D-65/D-66/D-67 above were written into that reserved range
before anyone noticed. That collision is recorded here and left for whoever executes 38-06 to
resolve; this decision does not make it worse.

### The fact

The acquisition software on the lab computer reports the device as:

    name:  Image Source
    model: DMK 33GP1300  BR2_UP  5810436
    mode:  live, 30 fps

Decoding the model string:

| Token | Meaning |
|---|---|
| `DMK` | **Monochrome.** (`DFK` would be the colour variant.) |
| `33G` | The Imaging Source 33-series, **GigE Vision** — GenICam over Ethernet. |
| `P1300` | 1280×1024 global-shutter sensor. |
| `5810436` | Serial number — this is the handle `tcam`/`aravis` select the device by. |
| `BR2_UP` | Vendor firmware/variant tag; nothing depends on it. |
| "Image Source" | The Imaging Source's own stack (IC Capture / tiscamera) is what currently holds the device. |

### The verdict

**Topology is D-65 T5.** `cv2.VideoCapture` cannot open this camera by any value of `--source`,
locally or remotely. It speaks GVCP (control, UDP 3956) and GVSP (stream, UDP), with broadcast
discovery. There is no RTSP URL, no HTTP URL, and no `/dev/video` node.

D-67's question 1 is **closed**. Questions 2 and 3 (what it plugs into; whether the lab computer is
also recording) remain open and are still asked at the front of plan 38-04.

### What this strikes out

- **T2 and T3 are dead for this camera, not merely unattractive.** D-66 part 1 — the
  `netsh portproxy` forward and the `OPENCV_FFMPEG_CAPTURE_OPTIONS=rtsp_transport;tcp` gotcha that
  goes with it — carries **TCP only**, and this camera puts both its control channel and its stream
  on **UDP**. There is nothing to forward. That whole branch is inapplicable and plan 38-04's Step
  1a T3 half is gated off.
- **D-50's "try the stream URL first" shortcut does not apply.** There is no URL to try. Plan
  38-04's Step 1b is inapplicable unless the dshow probe below succeeds first.

### What survives, and the branch that now matters

T5 is **not one outcome**. It splits, and the discriminator is one command that has not been run
yet (the researcher does not have the lab computer to hand as of 2026-09-06):

**T5a — The Imaging Source ships a Windows DirectShow wrapper.** This is unusual among
machine-vision vendors and it is the reason T5 is no longer automatically fatal: if the wrapper is
installed, the camera already looks like an ordinary capture device to every Windows application,
and D-66 part 2's MJPEG relay works **with no new code in `dlc_link` at all**. T5a collapses to
**T4** and the phase proceeds exactly as planned.

**T5b — no wrapper, or the wrapper cannot be shared.** Then a capture shim is required behind plan
38-01's injected-capture seam. This is the STOP for the phase as currently planned, and it is
separate work.

**The discriminator, to be run on the lab computer when it is available:**

    ffmpeg -list_devices true -f dshow -i dummy

If a device resembling `DMK 33GP1300` appears in the video list → **T5a**. If only unrelated devices
(or none) appear → **T5b**. This costs one command, writes nothing, and decides whether any new code
is needed. It is the first thing to run and it is recorded as `pending` until then.

### T6 — the topology that did not exist before we knew the model

GigE means the camera travels over an **Ethernet cable**, which USB never did. So there is a sixth
arrangement, and it is strictly better than every hop:

| ID | Topology | Resolves to | What has to exist |
|---|---|---|---|
| **T6** | Camera's Ethernet moved to (or a second NIC added on) the **vision box** | shim, local | a NIC on the vision box on the camera's subnet |

T6 removes the lab computer from the path entirely, which kills D-66's carried hazard outright —
no second always-on relay process on an unsupervised machine, no host that phase 32/33 would have
to adopt. It still needs the T5b shim, but it needs nothing else. **If T5b is the answer, T6 is the
arrangement to build; do not build a relay for a camera that can simply be plugged in elsewhere.**

Standard GigE Vision requirements apply and are cheap: a dedicated NIC, camera and NIC on the same
L2 segment, and MTU 9000 (jumbo frames). Packet loss on a GigE Vision link presents as **dropped
frames, not as an error**, which is exactly what D-54's `--capture-only` baseline run is for.

### Four consequences for the code, if T5b

1. **Do not route the shim through OpenCV.** `opencv-python-headless` from PyPI is built **without**
   GStreamer, so `cv2.VideoCapture("tcambin serial=5810436 ! ... ! appsink", cv2.CAP_GSTREAMER)`
   will fail; and installing a GStreamer-enabled OpenCV build beside it is exactly the second-`cv2`
   clobber D-58 prohibits by name. Pull buffers from **aravis via PyGObject** straight into numpy
   and hand those to the existing pipeline. The seam plan 38-01 builds is what receives them.
2. **The frames are Mono8.** DLC expects three channels. A gray→3-channel expansion is a **required**
   step before `Processor` sees the frame, not an optimisation. Separately and independently: if the
   exported model was trained on colour video from a different camera, live accuracy will differ for
   reasons no amount of plumbing fixes. That is a model question for the researcher, recorded here
   so it is not discovered as a bug.
3. **`--source` grows a fourth kind.** A serial is not a URL and must not be classified as `stream`;
   `--source tcam:5810436` (or equivalent) is its own kind. D-49's rule stands unchanged — the
   classification is decided in a pure function and **printed** before any device is opened.
4. **Everything downstream is unaffected.** D-51 (never paced), D-52 (`LatestSlot`, newest frame),
   D-53 (`behind_count: n/a`), D-54 (measured baseline), D-55 (four terminations) were all written
   to be blind to where frames come from, and they are. This decision changes the grabber and
   nothing else.

### Bandwidth is a non-issue at this rate

1280 × 1024 × 1 byte (Mono8) × 30 fps ≈ **39 MB/s ≈ 315 Mbps**. That fits 1 GbE comfortably, so no
downscaling is required at the relay or at the shim, and D-66's downscale suggestion is unnecessary
for this camera. Recorded so nobody adds a resize that costs frames for no reason.

### Exclusive access has an escape hatch a USB camera never had

GigE Vision permits **one primary (control) application** at a time — so D-67's question 3 is still
architecture-deciding. But unlike DirectShow, the standard also defines **multicast**: the primary
application streams to a multicast group and further clients attach **read-only as monitors**.
Aravis supports opening a device in monitor mode. So if the existing capture software must keep
recording during MICS runs, the answer is multicast monitoring — a configuration change on the
recorder, not a rewrite, and not a fight over the device.

Order of preference if recording must continue: **multicast monitor** → **one capture with two
sinks** (D-66 part 2's single-`ffmpeg`-invocation rule) → a virtual-camera splitter, last resort.
