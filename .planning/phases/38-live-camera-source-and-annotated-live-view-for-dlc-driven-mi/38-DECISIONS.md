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

> **SUPERSEDED IN PART, 2026-09-06 — see D-75.** The camera is a GigE Vision `DMK 33GP1300`, which
> exposes **no stream URL at all**, so this decision's premise does not hold for this rig. Two
> sentences below are now false and must not be acted on: plan 38-04's first checkpoint step is the
> `-list_devices` dshow probe, **not** a URL test; and "a USB camera plugged into the vision box is
> the likelier physical arrangement" is contradicted by the camera's own label. A URL becomes
> relevant again only on the **T5a** branch, where it is the MJPEG relay's URL rather than the
> camera's. The reasoning below remains correct as a general rule and is kept for the next camera.

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

> **AMENDED by D-86 (2026-09-10).** The version-bump reasoning below stands unchanged and is now
> enforced by the index. The distribution MECHANICS below — build a wheel on the dev host, hash it,
> copy it to the SMB share — are superseded: the package is released to PyPI by tag. Read D-86 with
> this decision.

`dlc-link` **0.1.0** is already installed on the vision box, so re-publishing 0.1.0 makes
`pip install` a possible no-op and makes `pip show` useless as evidence of which build is running.
The version becomes **0.2.0**; `pip show mics-dlc-link` then proves it. (Under D-86 a re-upload of
0.1.0 is not merely a no-op but is refused by PyPI outright — the index now enforces what this
decision could previously only ask for.)

~~The agent builds the wheel on the dev host and records its `sha256`. The **user** copies it to the
SMB share and installs it.~~ Superseded by D-86: the agent commits the bump and pushes a tag;
`.github/workflows/publish-clients.yml` builds and uploads; the user runs
`pip install --upgrade mics-dlc-link`. `mics-link` is unchanged by this phase and is neither
rebumped nor re-released.

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
| **T5** | Vendor-SDK camera (GigE Vision / USB3 Vision) | **none** | a capture shim; `cv2.VideoCapture` cannot open it — **but see D-75: T5 splits into T5a/T5b** |
| **T6** | Ethernet camera moved to the vision box (added by D-75) | shim, local | a NIC on the vision box on the camera's subnet |

**T1-T4 require no code change in `dlc_link`.** A forward and a relay both terminate in a URL, and
`classify_source` already routes a URL to `stream` on `<scheme>://` (plan 38-01), which already
means unpaced, already means the newest-frame reader, already means non-terminal read failures. This
is the whole reason topology can be discovered late without holding up plans 38-01 through 38-03:
the code is topology-blind by construction, and that property is now deliberate rather than
accidental.

**T5 is a STOP**, not a branch. It is added to Task 2's stop conditions in plan 38-04.
**[REVISED 2026-09-06 — D-75.]** This is the rig's actual topology, and T5 turned out to have two
outcomes, not one: **T5a** (a vendor DirectShow wrapper exists, the camera presents as an ordinary
capture device, and the T4 relay works with no code change) and **T5b** (no wrapper; the shim below
is required and the phase stops). Read "T5 is a STOP" as "T5b is a STOP". The honest
next step is the vendor's own tooling and a `FrameReader`-shaped shim behind the injected-capture
seam that plan 38-01 already builds — separate work, not this phase.

T2 is recorded but **not designed around**: the researcher reports that lab IT may refuse an unknown
device on the network, so a plan that depends on T2 is a plan that can be vetoed by someone outside
this project. T3 and T4 both keep the camera off the lab VLAN entirely, which turns that constraint
from a risk into a non-issue — the only host IT sees is the lab computer, which is already approved.

## D-66 — A lab-computer hop forwards before it relays, relays in MJPEG, and never runs on the Pi

Given T3 or T4, three sub-decisions, in this order:

> **INAPPLICABLE TO THIS RIG, 2026-09-06 — D-75.** Part 1 below assumes an RTSP endpoint reachable
> over TCP. GigE Vision puts both GVCP (control, UDP 3956) and GVSP (stream) on **UDP**, with
> broadcast discovery, and `netsh portproxy` carries TCP only — so there is nothing to forward and
> the `rtsp_transport;tcp` gotcha cannot arise. Part 1 is kept for a future IP camera. **Part 2 (the
> MJPEG relay) does still apply**, and is the T5a path.

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

1. ~~What is the camera's **make and model**?~~ **ANSWERED 2026-09-06 — D-75.** `DMK 33GP1300`,
   The Imaging Source, monochrome, GigE Vision, serial `5810436`. The verdict is T5. Do not re-ask
   this and do not run `arp -a`. The question that replaces it is D-75's dshow probe, which resolves
   T5a against T5b.
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
| `5810436` | Serial number — this is the handle a GenICam library (the vendor's `imagingcontrol4`, or `tcam`/`aravis` on Linux) selects the device by. |
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

**The discriminator, run on the lab computer 2026-09-10. ANSWER: T5a.** No longer `pending`.

`ffmpeg` turned out not to be installed on that machine, so the probe went at the same source
ffmpeg's own dshow enumerator walks — the DirectShow *Video Capture Sources* registry category,
64-bit view — which needs no install and writes nothing:

    Get-ChildItem 'HKLM:\SOFTWARE\Classes\CLSID\{860BB310-5D01-11d0-BD3B-00A0C911CE86}\Instance' | Get-ItemProperty | Select-Object -ExpandProperty FriendlyName

Returned verbatim:

    DMK 33GP1300 [BR2_UP]

**The vendor's DirectShow wrapper IS installed. T5a. T5 collapses to T4, `cv2.VideoCapture` can open
this camera, and no capture shim is needed.** The four "consequences for the code, if T5b" below are
therefore NOT triggered for this camera — keep them for a future rig with a different one.

The device name to use is `DMK 33GP1300 [BR2_UP]`, square brackets included. Caveat worth carrying:
ffmpeg prints its own device names and may differ from the registry FriendlyName in whitespace, so
if `-i video="..."` fails, get ffmpeg's exact spelling (`winget install Gyan.FFmpeg`) before
suspecting the camera.

**Second data point, same day — the VISION BOX baseline.** The identical query run on
`YizharGPU12` (identified by its `C:\Users\YizharGPU12` profile and the `(base)` conda prompt)
fails with *"Cannot find path ... because it does not exist"*. The category key is **absent, not
empty**: `YizharGPU12` has **no DirectShow video capture filters registered at all** — no webcam, no
vendor driver.

Three consequences, and the first two are the useful ones:

1. **The two machines are confirmed distinct**, as `38-CONTEXT.md` §3f already described. The lab
   computer holds the camera and the wrapper; the vision box holds the GPU and DeepLabCut.
2. **T6 is NOT already satisfied.** Making it true needs BOTH halves — the camera's Ethernet moved
   to `YizharGPU12` AND The Imaging Source driver installed there — and only then does re-running
   this query decide it. A "no" today is not evidence against T6; it is the expected baseline for a
   machine with no camera attached.
3. **`--source 0` on the vision box finds nothing today.** Any step that assumes a local device
   index on that machine is wrong until T6 is actually built.

T5a is unaffected: it only ever required the wrapper on the machine physically holding the camera,
which is what makes the T4 relay path work with no new code in `dlc_link`.

The 32-bit (`WOW6432Node`) view was never cleanly read — not a blocker, since the 64-bit
registration is what a 64-bit Python needs, but check it before assuming a 32-bit tool can open the
device.

### T6 — the topology that did not exist before we knew the model

GigE means the camera travels over an **Ethernet cable**, which USB never did. So there is a sixth
arrangement, and it is strictly better than every hop:

| ID | Topology | Resolves to | What has to exist |
|---|---|---|---|
| **T6** | Camera's Ethernet moved to (or a second NIC added on) the **vision box** | shim, local | a NIC on the vision box on the camera's subnet |

T6 removes the lab computer from the path entirely, which kills D-66's carried hazard outright —
no second always-on relay process on an unsupervised machine, no host that phase 32/33 would have
to adopt. **If T5b is the answer, T6 is the arrangement to build; do not build a relay for a camera
that can simply be plugged in elsewhere.**

**T6 may need no shim at all — run the probe a SECOND time.** The vision box is **Windows**
(`38-CONTEXT.md` §6: `cmd.exe`, `set VAR=`, `ipconfig`, SMB UNC staging). If The Imaging Source's
driver registers DirectShow devices on the lab computer, it will do the same on `YizharGPU12` once
installed there. So after moving the cable and installing the vendor driver on the vision box, run

    ffmpeg -list_devices true -f dshow -i dummy

**on the vision box**. If the camera appears, T6 collapses to **T1** — `--source 0`, the device-index
path plan 38-01 already builds — and no shim, no relay and no fourth source kind are needed at all.
That is the cheapest possible outcome in the whole phase and it costs one command to check. Only if
that probe fails does the T5b shim below become real work.

Standard GigE Vision requirements apply and are cheap: a dedicated NIC, camera and NIC on the same
L2 segment, and MTU 9000 (jumbo frames). Packet loss on a GigE Vision link presents as **dropped
frames, not as an error**, which is exactly what D-54's `--capture-only` baseline run is for.

### Four consequences for the code, if T5b

1. **Use the VENDOR's own Windows SDK, not aravis, and never route the shim through OpenCV.**

   **Corrected 2026-09-06.** An earlier draft of this decision named `aravis` via PyGObject as the
   grabber. That is a Linux-first, GObject-centric stack, and **the vision box is Windows**
   (`38-CONTEXT.md` §6). Aravis on Windows means MSYS2 and a GObject introspection stack dropped
   next to a conda environment whose `torch` must not be disturbed — the wrong first choice by a
   wide margin.

   The order to try, cheapest first:

   1. **The vendor's DirectShow wrapper on the vision box** — see T6 above. If the camera enumerates,
      there is nothing to write: `--source 0` and the existing device-index path.
   2. **The Imaging Source's IC Imaging Control 4 Python bindings** (`imagingcontrol4`), which is
      the vendor's supported Windows API for their own GigE cameras and hands over frames as numpy
      arrays. This is what the shim should be built on if one is needed.
   3. **aravis** — kept **only** as the fallback if the vision box is ever moved to Linux. Not the
      Windows answer.

   Whichever supplies the frames, they arrive as numpy arrays and go straight through the seam plan
   38-01 builds. **Never** via `cv2.VideoCapture(..., cv2.CAP_GSTREAMER)`: `opencv-python-headless`
   from PyPI is built **without** GStreamer, so `"tcambin serial=5810436 ! ... ! appsink"` will
   fail, and installing a GStreamer-enabled OpenCV build beside it is exactly the second-`cv2`
   clobber D-58 prohibits by name.
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
Both the vendor SDK and aravis support attaching as a monitor. So if the existing capture software must keep
recording during MICS runs, the answer is multicast monitoring — a configuration change on the
recorder, not a rewrite, and not a fight over the device.

Order of preference if recording must continue: **multicast monitor** → **one capture with two
sinks** (D-66 part 2's single-`ffmpeg`-invocation rule) → a virtual-camera splitter, last resort.

---

## Reserved decision-ID ranges — read before appending

This file is appended to by more than one plan, and the ranges have already collided once. Before
adding a decision, take the next free ID from this table and update it.

| Range | Owner | Status |
|---|---|---|
| D-27 … D-48 | Phase 35 | closed |
| D-49 … D-64 | Phase 38 planning (2026-09-02) | closed |
| D-65 … D-67 | Phase 38 topology (D-65 taxonomy, D-66 lab-computer hop, D-67 discovery order) | **in this file** |
| D-68 … D-74 | *free* | — |
| D-75 | Phase 38 camera identity / T5 split | **in this file** |
| **D-76 … D-85** | **plan 38-06's decision set** | **reserved — 38-06 originally said D-65..D-74, which double-booked the topology decisions; it is renumbered to this range** |
| D-86 … D-88 | Phase 38 execution (D-86 PyPI, D-87 T6 impossible, D-88 acquisition at source) | **in this file** |
| D-89+ | *free* | — |

**Threat IDs collide the same way.** `T-38-40` … `T-38-44` are used by plan 38-05 (pose row order,
runbook attribution, keep-up number, `opencv-python`, project writes). Plan 38-06's threat block is
renumbered to **T-38-60 … T-38-71**. Plan 38-07's threat block is `T-38-72` … `T-38-76`. Take new threat IDs from `T-38-77` onward.

**Format, for anything appended here:** a level-2 heading, `## D-NN — <title>`. Not bold, not a
list item. Any automated check that greps for these entries must match `^## D-`.

## D-86 — Distribution is PyPI, not the SMB share; the SMB path is retired

**Decided 2026-09-10 by the user, and already IMPLEMENTED — this is a record of a shipped fact, not
a proposal.** `mics-link` 0.1.0 and `mics-dlc-link` 0.1.0 are live on PyPI. Verified from a clean
venv outside the repo with no local index: `python -m pip install mics-dlc-link` resolves
`mics-link` transitively and all three console scripts run.

**What the researcher now types**, on a machine with no lab network, no repo access and no share:

```
python -m pip install "mics-dlc-link[live]"
```

**Supersedes** D-63's distribution mechanics (build a wheel on the dev host, hash it, copy it to
`\\isi.storwis.weizmann.ac.il\labs\yizharlab\Mics\wheel\`) and D-80's "the wheel is staged and
installed by the USER". It does NOT supersede either decision's version-bump reasoning, which is
now enforced by the index rather than merely asked for: PyPI is immutable, so re-uploading an
existing version is refused outright.

**The distribution was RENAMED `dlc-link` -> `mics-dlc-link`.** The import package is still
`dlc_link` and the console scripts are still `dlc-link-generate` / `-convert` / `-live`. Only the
name you `pip install` changed. Unprefixed `dlc-link` is NOT ours — if a project by that name ever
appears on PyPI, installing it is precisely the near-miss the package-legitimacy checks exist to
catch, and every threat row that used to reason about SMB transit now reasons about this instead.

**Releasing** is a tag push — `mics-link-v*` -> `sdk/`, `mics-dlc-link-v*` -> `dlc_link/` — handled
by `.github/workflows/publish-clients.yml` under PyPI Trusted Publishing (OIDC; no stored token).
The workflow refuses to publish if the tag version and the `pyproject.toml` version disagree, if
`twine check` fails, or if a `132.77.*` lab address reappears in the built artifacts. Full
procedure, including the environment-collision trap that cost two failed runs, is in `RELEASING.md`
at the repo root.

**Each package needs its own GitHub environment** (`pypi`, `pypi-dlc`) and its PyPI publisher must
be pinned to it. PyPI mints one project-scoped token per OIDC exchange, so two publishers with
identical repository+workflow claims are ambiguous and the upload fails naming the *other* project.

**What this does NOT change.** Plan 38-06's gap 1 stays open and stays this phase's job: the
notebook must be inside the built wheel via `[tool.setuptools.package-data]`. A file the wheel does
not contain does not reach the user, whether the wheel arrives from an index or a file share — and
under PyPI the audience is wider, not narrower. The SMB share survives only as break-glass for an
air-gapped machine, and even then the documented path is `pip download` / `pip install --no-index
--find-links`, which fetches the same artifact the index serves.

## D-87 — T6 is impossible; T4 is the architecture, and the relay is permanent

**Decided 2026-09-10 by the user, on a physical fact that no design can argue with:** the camera is
in the rig room and `YizharGPU12` is in a different room. The Ethernet cannot be moved and a NIC on
the vision box reaches nothing. **T6 is closed as IMPOSSIBLE, not deferred.**

Combined with D-75's T5a verdict, the topology is settled:

**T4 — the camera is opened on the LAB COMPUTER via the vendor's DirectShow wrapper, and frames
reach the vision box over the network.** This needs no new code in `dlc_link`, which is exactly what
the T5a probe bought. Plans 38-01 through 38-06 already build this path; nothing is rewritten by
this decision.

### The cost T6 would have removed, now permanent — and it is not this phase's to absorb

A relay process runs **always-on, on the lab computer, unsupervised**. D-75 named this as T6's
motivation ("no second always-on relay process on an unsupervised machine, no host that phase 32/33
would have to adopt"). T6 is gone, so that hazard is now a standing property of the system:

- If the relay dies, the vision box sees a stalled or absent stream. The keypoint signals then go
  **stale**, and stale signals on the Pi resolve through each signal's declared `stale_policy` —
  `return_default` or `hold_last` — which means **an FDA can keep evaluating and a run can keep
  going while nothing is actually watching the animal**. That is the same class of silent failure
  as run 581, and it is the reason this is written down rather than left as an operational detail.
- Nothing restarts it. `deploy/mics-pilot.service`'s `Restart=always` covers the Pi, not a Windows
  process on a third machine.
- **Phase 32 does not currently cover this host.** Its scope is the Pi, the orchestrator, the API
  and the UI. A relay on the lab computer is a fourth failure domain, and Phase 32's crash
  classification cannot see it.

**Not this phase's job to fix** — 38's goal is a working camera and a live view, and widening it
here would delay the thing the researcher is waiting for. But it must not be discovered later as a
surprise. The concrete follow-ups, for whoever plans the next unattended-operation slice:

1. The relay needs a supervisor on the lab computer (a scheduled task or service with restart), or
2. `dlc-link-live` needs to treat a dead relay as a **loud** failure rather than an absent frame —
   `behind_count` and the reader-thread skip counter already exist as the instruments, and 38-01
   builds them, so this is a threshold-and-exit question rather than new machinery, or
3. the pilot side must refuse to run when a `required` extlink source has gone stale beyond its
   window, which is a Phase 18 / Phase 32 substrate question and not a `dlc_link` one.

### The one alternative that survives, recorded so it is not rediscovered

The camera could instead be admitted to the lab LAN and read **directly** by a GenICam client on the
vision box — the two machines are on the same VLAN and segment (`38-CONTEXT.md` §3f), so no
forwarding is involved and D-75's "TCP-only portproxy" objection does not apply to it.

It is **not** recommended, and it is strictly more work than T4: it needs lab IT to admit the camera
as an unknown device (which the researcher has said may be refused) AND the `imagingcontrol4` vendor
shim — i.e. the whole T5b build that T5a just made unnecessary. Its only advantage is removing the
relay. Revisit it only if the relay's unsupervised-host problem proves worse in practice than
writing the shim.

---

## D-88 — Acquisition is recorded at the SOURCE, and delivery stops being a listener

**Decided 2026-09-10 by the user, after the T4 transport was proven working:** the rig must "be ready
for acquisition" — i.e. the footage must be saved, not merely streamed. That turns out to be
incompatible with the relay as built, for a reason that is easy to miss and silent when it bites.

### The trap

`-listen 1` blocks output initialisation until a client connects. ffmpeg does not finish opening
**any** output until initialisation completes, so a single invocation with both an HTTP-listen output
and a file output **does not begin recording until somebody is watching**. There is no error; the
file simply does not grow. For an archival record that is the worst available failure mode.

Two ffmpeg processes are not an escape: DirectShow access is exclusive (2026-09-10, §8.4 of
`38-HARDWARE-VALIDATION.md`), so the recorder and the relay MUST be the same process. D-66 part 2's
one-capture-two-sinks rule was right; what it did not anticipate is that `-listen` makes that
arrangement unusable.

### The decision

The lab computer's single `ffmpeg` invocation takes **the file as its primary output** and **pushes**
the live feed to the vision box rather than waiting to be asked for it.

This decouples acquisition from delivery, which is the substantive win: a dead network, a powered-off
vision box, a crashed DLC run or a closed notebook no longer costs footage. Under the current
arrangement every one of those loses the session.

### The fan-out primitive, and why it is not two `-map` outputs

Two plain outputs share ffmpeg's muxing loop, so a blocked or dead delivery sink backpressures the
FILE sink as well — the recording stalls because nobody is watching, which is the same class of
silent failure `-listen` produces. The fan-out is therefore the **`tee` muxer with `onfail=ignore`**
on the network leg only:

    -fps_mode passthrough -f tee "[f=segment:...]<file>|[f=mpegts:onfail=ignore]<url>"

`onfail=ignore` makes the network leg droppable by construction: a powered-off vision box, a crashed
DLC run or a pulled cable costs the live view and nothing else. The file leg has no `onfail` and must
never get one — if the recording fails, the run should stop being believed.

**`-fps_mode passthrough` is mandatory, not tuning.** ffmpeg's default frame-rate handling may
duplicate or drop frames to fit a constant output rate. With that in play, "were all frames saved?"
has no answerable form, because the file's frame count no longer corresponds to what the camera
delivered.

**Transport is decided by measurement in plan 38-07 Task 1, not here.** Two candidates:

| Candidate | Blocks on a consumer? | Under congestion |
|---|---|---|
| `-f mpegts udp://<vision-box>:<port>` | never | lossy — drops become broken frames |
| `-f mpjpeg tcp://<vision-box>:<port>` (vision box listens) | no, but needs a listener and an inbound rule on the GPU box instead | TCP degrades gracefully |

D-66's reason for MJPEG over H.264 — per-frame coding, no GOP buffering — is unchanged and binds
whichever transport wins for the DELIVERY leg. What changes is only who initiates the connection.
It does not bind the FILE leg, which is an archival artifact rather than a live one and may use
H.264 — the format IC Capture's own recorder is configured for (`MediaFoundation h.264`, MP4).

**The encoder is chosen by measurement.** If the file leg's encoder cannot keep up on that machine it
backpressures the capture and frames are dropped at the source — the exact failure this decision
exists to prevent. MJPEG is the safe fallback (cheap, larger files); the Gyan build also carries
`h264_nvenc`, `h264_qsv` and `h264_amf` if a hardware encoder is present.

### Supervision

The recorder gets a restart wrapper. **Restarting is safe**, and this is a measured fact rather than
an assumption: exposure, gain and the 704x680 ROI persist in the vendor driver, and ffmpeg inherited
them without being told (`38-HARDWARE-VALIDATION.md` §2.4). A restarted recorder comes back
configured.

Two constraints on how:

1. **The lab computer must stay Python-free.** D-66 chose `ffmpeg` over a Python relay precisely so
   that machine would not acquire an environment to maintain, and it has none today. The supervisor
   is therefore **PowerShell**, and `dlc_link` *generates* it rather than running on that host.
2. **Segmented output** (`-f segment`), so a restart opens a new file instead of leaving one
   truncated file of ambiguous length.

### Completeness is a test, not a claim

Replacing IC Capture moves the footage from being someone else's by-product to being this system's
deliverable, so "all frames were saved" has to be checkable. For a run of known duration, **while the
model is running**:

1. ffmpeg's own final `frame=` total,
2. `ffprobe -count_frames`'s `nb_read_frames` over the written segments,
3. zero `frame dropped` lines in the captured ffmpeg log,
4. and agreement with the configured rate over that duration,

must all line up, and the consumer's own `frames_read` is the fourth independent witness. Any
disagreement is a defect, not a rounding artifact. This is why the ffmpeg log must be captured to a
file rather than left in a console buffer.

**One standing caveat on (4):** the camera's auto-exposure and auto-gain are ON (`Auto Reference
173`, `Auto Functions ROI` preset 2, from the rig's `.iccf`). Auto-exposure lengthens exposure time
in dim light, and once it passes ~33 ms the camera cannot sustain 30 fps. So the expected count is
"the rate actually delivered over this interval", not a constant 30 x duration, and a shortfall is
not automatically a dropped frame. Pinning exposure for runs is the way to make (4) sharp; that is a
rig decision for the researcher, not a code change.

### What this does NOT solve

Simultaneous IC Capture and MICS acquisition. That remains D-75's multicast-monitor hatch, which
needs the vendor GigE stack (`imagingcontrol4`) and therefore the CAM-17 / T5b build this phase
avoided — plus lab IT admitting the camera and the switch doing IGMP sanely. Recording at the source
makes IC Capture *less* necessary (the footage exists without it) but does not make it concurrent.
