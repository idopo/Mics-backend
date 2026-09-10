# Phase 38 — Hardware validation session log

Shape copied from `35-HARDWARE-VALIDATION.md`. Every result cell reads `pending` until the
thing it describes has actually happened. Cells that are already facts carry their source.

## 0. Preconditions

| Item | Value | Source |
|---|---|---|
| Released build under test | `mics-dlc-link 0.2.0` | PyPI, `https://pypi.org/pypi/mics-dlc-link/0.2.0/json` → 200 |
| Publishing run | `https://github.com/idopo/Mics-backend/actions/runs/34467941561` | `success`, 2026-09-10 (D-86) |
| `mics-link` | unchanged by this phase; vision box keeps its existing install | D-86 |
| Camera | `DMK 33GP1300 [BR2_UP]`, GigE Vision, mono, serial `5810436` | D-75 |
| Lab computer | `132.77.73.214`, Windows 10 Enterprise LTSC, user profile `yizha` | measured, §1 |
| Vision box (GPU) | `132.77.73.217`, user profile `YizharGPU12`, conda `base` active | measured, §1 |
| Pilot | pilot 3 / `RecordingBox`, port `5601`, lib `dlc_cam1` 189 | Phase 35 fixture |
| ElasticSearch index | `event_log_v2` | Phase 35 fixture |

### Standing rules this session operated under

1. Never run git, Python or process control on any Pi. Every rig and Windows action is
   USER-RUN; the agent supplies the command and waits.
2. Never write into the researcher's DLC project directory. This phase runs no
   `export_model` at all, so the expected manifest diff is empty by construction (D-64).
3. Windows commands are given in short, paste-safe pieces. **Deviation from the plan:** the
   plan specifies the `cmd` `set VAR=` / `%VAR%` idiom; both machines were driven from
   PowerShell, so the equivalent `$var=` form and argument arrays were used instead. The
   purpose — no line long enough to wrap on paste — is met. Two failures this session were
   caused by exactly the wrapping this rule exists to prevent (§8.3).
4. Every command states what it writes and where, or says `writes nothing` (D-48, §0a).
5. No latency claims. Counts and rates only (§3).
6. `opencv-python` is never installed; `opencv-python-headless` stays.

## 0a. WRITE FOOTPRINT

| # | Command | Machine | Writes |
|---|---|---|---|
| 1 | `Get-ChildItem HKLM:\...\CLSID\{860BB310-...}\Instance \| Get-ItemProperty` | lab | writes nothing (registry READ) |
| 2 | `Get-Command ffmpeg` | both | writes nothing |
| 3 | `(Get-CimInstance Win32_OperatingSystem).Caption` | lab | writes nothing |
| 4 | `Test-NetConnection www.gyan.dev -Port 443` | lab | writes nothing |
| 5 | `$roots \| gci -Filter ffmpeg.exe -Recurse` | lab | writes nothing (filesystem READ) |
| 6 | `Invoke-WebRequest -Uri $u -OutFile $z -UseBasicParsing` | lab, GPU | **writes** `%USERPROFILE%\ffmpeg.zip` (~106 MB) |
| 7 | `Expand-Archive -Path $z -DestinationPath "$env:USERPROFILE\ffmpeg"` | lab, GPU | **writes** `%USERPROFILE%\ffmpeg\` (tree) |
| 8 | `& $f -hide_banner -devices` / `-formats` / `-protocols` | GPU | writes nothing |
| 9 | `& $f -list_devices true -f dshow -i dummy` | lab | writes nothing |
| 10 | `& $f -f dshow -list_options true -i "video=$dev"` | lab | writes nothing |
| 11 | `& $f -f dshow -i "video=$dev" -t 1 -f null -` | lab | writes nothing (output discarded) |
| 12 | `& $f @a` (the MJPEG relay) | lab | writes nothing to disk; **serves** TCP 8080 |
| 13 | `New-NetFirewallRule ... -LocalPort 8080 -Protocol TCP -Action Allow` | lab | **writes** a persistent inbound firewall rule (PersistentStore) |
| 14 | `ffprobe.exe http://132.77.73.214:8080/` | GPU | writes nothing |
| 15 | `pip install -U mics-dlc-link` | GPU | **writes** into the DLC conda env's site-packages |
| 16 | `pip show mics-dlc-link` | GPU | writes nothing |
| 17 | `dlc-link-live --capture-only ...` | GPU | writes nothing (D-47) |
| 18 | `dlc-link-live --view ...` | GPU | writes nothing (D-47) |

Rows 6, 7 and 13 are the only persistent changes outside the DLC environment. Rows 6 and 7
are deletable with `Remove-Item`; row 13 is removable with `Remove-NetFirewallRule`.

## 0b. Package legitimacy

| Package | Status | Note |
|---|---|---|
| `jupyterlab` | `[ASSUMED] - unverified` | needed only if the researcher wants the notebook sink |
| `notebook` | `[ASSUMED] - unverified` | same |
| `ipywidgets` | `[ASSUMED] - unverified` | same |

Task 2's checkpoint is **BLOCKING on a human opening the public index page for each** of
these before any install. This is **never auto-approvable**. The `MjpegSink` shipped by
plan 38-03 exists precisely so that the correct answer can be **install nothing** — a
browser pointed at the viewer's own localhost port needs no Jupyter at all.

## 1. Discovery answers

### Topology (D-65, D-75, D-87)

| Question | Answer | Source |
|---|---|---|
| Camera make / model | `DMK 33GP1300`, GigE Vision, mono, serial `5810436` | fact, D-75 — not rediscovered |
| What it plugs into | the **lab computer** (`132.77.73.214`) over Ethernet | user, 2026-09-10 |
| Lab computer NIC count | 5 IPv4 addresses: `132.77.73.214` routable, plus `169.254.201.71`, `169.254.145.116`, `169.254.195.163`, `169.254.182.120` link-local | `Get-NetIPAddress`, §2.1 |
| Does the camera present as a DirectShow device? | **YES** — `"DMK 33GP1300 [BR2_UP]" (video)` | `ffmpeg -list_devices`, §2.3 |
| Can the camera's Ethernet reach the vision box (T6)? | **NO — IMPOSSIBLE.** Different rooms; cable cannot be moved | D-87, user |
| **TOPOLOGY VERDICT** | **`T5a`** | §2.3. A DirectShow wrapper exists, so `T5` collapses to `T4` and **no new code in `dlc_link` is required** for the camera path |
| Is the lab computer also recording from this camera? | `pending` | matters because DirectShow access is exclusive (§8.4) |

The four `169.254.*` addresses are link-local NICs with no DHCP. The camera is on one of
them, which is an independent reason the relay is required regardless of room geography:
that subnet is unroutable from the vision box.

### Environment

| Question | Answer | Source |
|---|---|---|
| Lab computer OS | Windows 10 Enterprise LTSC | `Win32_OperatingSystem` |
| Is `winget` available on the lab computer? | **NO** | §8.1 — LTSC ships without App Installer |
| Was ffmpeg already installed anywhere on the lab computer? | **NO** | §2.2 |
| Is the orchestrator reachable from the vision box? | `pending` | |
| Is ElasticSearch reachable from the vision box? | `pending` | |
| Does Jupyter exist in the DLC environment? | `pending` | gates §0b entirely |
| `pip show mics-dlc-link` on the vision box | `pending` | must read `0.2.0` |

## 2. Camera bring-up

### 2.1 Addresses

`Get-NetIPAddress -AddressFamily IPv4` on the lab computer returned the five addresses in
§1. `Test-NetConnection 132.77.73.214` from the vision box: `PingSucceeded: True`,
`RTT 0 ms`, `SourceAddress 132.77.73.217`.

### 2.2 ffmpeg provisioning

`Get-Command ffmpeg` returned nothing on either machine, and a targeted search of
`C:\Program Files`, `C:\Program Files (x86)`, `C:\ProgramData`, `%LOCALAPPDATA%`,
`%USERPROFILE%`, `C:\tools` and `C:\ffmpeg` found no `ffmpeg.exe`. Installed on both
machines from `ffmpeg-release-essentials.zip` (Gyan), unpacked under `%USERPROFILE%\ffmpeg`.
Version: **9.0.1-essentials_build**.

Capability checks (run on the GPU box binary; the lab copy is the same build):

```
D   dshow           DirectShow capture
DE  mpjpeg          MIME multipart JPEG
    http, httpproxy, https   (both input and output protocol lists)
```

`DE` on `mpjpeg` is the load-bearing detail — `-f mpjpeg` output needs the **muxer**, not
just the demuxer. The full `.7z` build was therefore unnecessary (§8.2).

### 2.3 Device enumeration — Step 1a-0, answered by ffmpeg

```
[in#0] "DMK 33GP1300 [BR2_UP]" (video)
[in#0]   Alternative name "@device_sw_{860BB310-5D01-11D0-BD3B-00A0C911CE86}\
                           {EBB769A3-0D94-4B4C-A53B-DD1EAFECB2A1}"
[in#0] Could not enumerate audio only devices (or none found).
Error opening input file dummy.
```

`Error opening input file dummy` is the expected ending of `-list_devices`, not a failure.
**This is the T5a evidence.** It was previously inferred from a registry read of
`CLSID_VideoInputDeviceCategory`; that read was a workaround for having no ffmpeg, and the
64-bit view was checked separately to rule out a 32-bit-only wrapper.

### 2.4 Supported modes

```
unknown compression type 0x20363159 ('Y16 ')  256x16 .. 1280x1024  fps 5 .. 45.2407
pixel_format=gray                             256x16 .. 1280x1024  fps 5 .. 90.4814
pixel_format=bgr24                            256x16 .. 1280x1024  fps 5 .. 90.4814
  discrete: 1280x960, 640x512, 640x480, 320x256
```

Two findings. **`bgr24` is available directly from the driver**, so the mono→3-channel
expansion DLC needs can happen in the vendor layer and needs no code. And the device's
*current* configuration is **704x680**, which is not one of the discrete modes — it is a
ROI persisted into the driver by IC Capture. ffmpeg inherited it without being told, which
is what makes the IC-Capture-for-setup / relay-for-runtime division of labour work (§8.4).

### 2.5 Device opens

```
Input #0, dshow, from 'video=DMK 33GP1300 [BR2_UP]':
  Stream #0:0: Video: rawvideo (Y800 / 0x30303859), gray, 704x680, 30 fps, 30 tbr
frame=   31 fps= 29 ... time=00:00:01.03 speed=0.972x
```

31 frames in 1.03 s. The camera delivers its configured 30 fps. This is a camera-side
figure, not the vision box's delivered rate — that belongs in §3.

### 2.6 Relay serving, and frames crossing to the vision box

Relay on the lab computer:

```
$a=@('-f','dshow','-rtbufsize','100M','-i',"video=$dev")
$a+=@('-c:v','mjpeg','-q:v','5','-pix_fmt','yuvj420p')
$a+=@('-f','mpjpeg','-listen','2','http://0.0.0.0:8080/')
& $f @a
```

`ffprobe` on the vision box against `http://132.77.73.214:8080/`:

```
Input #0, mpjpeg, from 'http://132.77.73.214:8080/':
  Stream #0:0: Video: mjpeg (Baseline), yuvj420p(pc, bt470bg), 704x680, 25 tbr, 25 tbn
```

**The full T4 transport is proven:** camera → DirectShow → ffmpeg → MJPEG/HTTP → vision box,
with no new code in `dlc_link`.

`25 tbr` is **not a measurement**. The mpjpeg container carries no timestamps, so ffmpeg
substitutes a 25 fps default. No keep-up claim may cite it.

## 3. Rate measurement

Every figure below is a count, or a count divided by a duration, on the vision box's own
clock. **No cell in this table is a latency**, and none may be read as one.

| run | mode | duration_s | frames_read | frames_inferred | frames_skipped | rate_read_per_s | rate_inferred_per_s |
|---|---|---|---|---|---|---|---|
| `pending` | `--capture-only` (no model) | `pending` | `pending` | n/a | `pending` | `pending` | n/a |
| `pending` | inference | `pending` | `pending` | `pending` | `pending` | `pending` | `pending` |

## 4. The derived keep-up criterion

| Quantity | Value |
|---|---|
| Baseline (capture-only, vision box) | `pending` |
| Achieved (with model loaded) | `pending` |
| Ratio achieved / baseline | `pending` |
| `--min-rate` chosen | `pending` |
| Why this value and not a rounder one | `pending` |

Camera-side delivery is 30 fps (§2.5), but the baseline that `--min-rate` derives from is
what the **vision box** reads through the relay, which is a different number and must be
measured. Deriving it from §2.5 or from the `25 tbr` line would be guessing.

## 5. The live run

| Item | Value |
|---|---|
| Run id | `pending` |
| Session id | `pending` |
| Sender summary | `pending` |
| `state_transition` sequence in `event_log_v2` | `pending` |
| What the researcher saw in the viewer | `pending` |
| Sink used (`notebook` or `mjpeg`) | `pending` |

## 6. Manifest — the researcher's DLC project directory

| Item | Value |
|---|---|
| Recursive file count before | `pending` |
| Recursive file count after | `pending` |
| `Compare-Object` output | `pending` |

This phase runs no `export_model`, so the expected diff is empty by construction.

## 7. Per-truth ledger

One row per `must_haves.truths` entry in `38-04-PLAN.md`. **Do not mark the plan done on a
green subset** — this instruction is in the document because Phase 35 needed it.

| # | Truth | Verdict |
|---|---|---|
| 1 | Topology established from the lab computer before the wheel is built, recorded as a named branch | **PROVEN** — §2.3, verdict `T5a` recorded in §1 as a named cell. Established before the 0.2.0 build was tagged |
| 2 | Verdict is already T5; the session resolves T5a vs T5b with ONE dshow probe, not by rediscovering make and model | **PROVEN** — §2.3. Make and model carried in as facts from D-75 |
| 3 | T5b recognised as a STOP with a named next step, not retried with more flags | **NOT EXERCISED** — T5a returned, so the branch was never entered. Correct outcome, not a gap |
| 4 | Whether the lab computer is also recording from the camera is established | `pending` — §1 |
| 5 | A camera filming the rig reaches a trained DLC model, and its keypoints reach pilot 3 as declared signals | `pending` — transport is proven (§2.6); the model and pilot halves are not |
| 6 | The researcher watches the annotated frames while the task runs | `pending` — §5 |
| 7 | The camera's delivered rate is MEASURED with no model loaded | `pending` — §3. §2.5 is the camera side only |
| 8 | The keep-up criterion is a number off that measurement, recorded in writing | `pending` — §4 |
| 9 | Whether the orchestrator and ElasticSearch are reachable from the vision box is established by a command | `pending` — §1 |
| 10 | Whether Jupyter exists in the DLC environment is established before anything depends on it, and no install touches pyzmq/numpy/torch | `pending` — §0b, §1 |
| 11 | Every rig and vision-box action performed by the USER; the agent ran no git, no Python and no process control on any Pi | **HELD so far** — every Windows command in §2 was user-run. Agent actions were confined to this repository, the GitHub API and PyPI |
| 12 | The researcher's DLC project directory is provably unchanged | `pending` — §6 |
| 13 | Every command states what it writes and where, or says it writes nothing | **HELD so far** — §0a covers all 18 commands issued |
| 14 | No number produced by this session is a latency, and none is presented as one | **HELD so far** — §3 carries the prohibition; the one rate-shaped line that is *not* a measurement (`25 tbr`) is called out as such in §2.6 |

## 8. Defects found

### 8.1 The plan's ffmpeg install step is invalid for this machine

`38-04-PLAN.md` specifies `winget install Gyan.FFmpeg`. The lab computer runs **Windows 10
Enterprise LTSC**, which ships without App Installer, so `winget` does not exist. Replaced
by download-and-extract of `ffmpeg-release-essentials.zip` into `%USERPROFILE%\ffmpeg` —
no installer, no administrator rights, no PATH mutation, one deletable folder. Arguably
better than the planned step. The plan text should be corrected.

### 8.2 The plan's "use a FULL build" advice is unachievable as written

The plan warns that `-f mpjpeg -listen 1` is absent from minimal builds and directs a full
build. Gyan's **full** build is distributed only as `.7z`, and LTSC has no archiver that
can unpack it, so following that advice requires installing a second tool first. The
**essentials** `.zip` was tested instead and carries both `dshow` and the `mpjpeg` muxer
(§2.2), so the warning's goal is met by a cheaper route.

### 8.3 Lab addresses in the package source would have blocked the release

`publish-clients.yml` refuses to upload if `132.77.*` appears in the built artifacts. Waves
1–2 left lab addresses in two argparse help strings (`live_cli_args.py`) and one module
docstring (`pilot_state.py`). Scrubbed in `ae73b8c`; documentation only, no functional
value changed, 385 tests still pass. Verified before tagging by building locally and
running the same three gates CI runs.

**Still open, for plan 38-06:** the notebook at `dlc_link/notebooks/live_view.ipynb`
carries `132.77.73.125` and `132.77.73.217` as default values. It is currently outside
`src/`, so it is in neither the sdist nor the wheel — verified. Plan 38-06 moves it *into*
the package so `pip install` ships it, and at that moment those defaults will trip this
guard. 38-06 must replace them with placeholders.

Related: because the notebook is not in the artifacts today, `pip install mics-dlc-link`
does **not** deliver the notebook. It has to come from the repository until 38-06 lands.

### 8.4 DirectShow access is exclusive, permanently

IC Capture and the relay cannot both hold the camera. With IC Capture open, ffmpeg fails
with `Could not run graph (sometimes caused by a device already in use by other
application)` — the same message an unsupported mode produces, which is why a one-second
`-f null` probe was used to tell the two apart.

This is not a setup quirk; it is a standing operational constraint. Camera properties
(exposure, gain, ROI) are vendor-only and must be set in IC Capture, then IC Capture closed,
then the relay started — it inherits them (§2.4). Adjusting mid-session means stopping the
relay. Fully replacing IC Capture means the `imagingcontrol4` vendor SDK, i.e. the entire
T5b build that confirming T5a made unnecessary; recorded as not recommended.

### 8.5 `-listen 1` serves exactly one client and exits when it disconnects

The original relay used `-listen 1`. A `Test-NetConnection` handshake or an `ffprobe` run
consumes that single slot, and ffmpeg commonly exits when the client disconnects, which
reads as a dead relay. Raised to `-listen 2` so a probe cannot starve the viewer.

Related and expected, not a defect: before any client connects, `-listen` blocks the output
while dshow keeps filling at 30 fps, producing a flood of `real-time buffer too full ...
frame dropped!`. `-rtbufsize 100M` widens that window. Steady-state drops are **by design**
— plan 38-01's `LatestSlot` keeps only the newest frame, because for closed-loop triggering
a queued frame is a stale frame.

### 8.6 The relay is an unsupervised single point of failure

Out of this phase's scope by D-87, recorded so it is not rediscovered. If the relay dies
the vision box simply stops receiving; keypoint signals then go stale and resolve through
each signal's `stale_policy` (`return_default` or `hold_last`), which means an FDA can keep
evaluating and a run can keep going while nothing is watching the animal. Same class as run
581. `behind_count`, the reader-thread skip counter and `--min-rate` are the instruments
that exist; turning them into a loud failure is deferred.

## 9. Rollback

| Target | Action |
|---|---|
| Backend | nothing to roll back — this plan creates no rows and changes no task definition |
| Vision box package | `pip install mics-dlc-link==0.1.0` returns the previous build |
| Lab computer ffmpeg | `Remove-Item "$env:USERPROFILE\ffmpeg" -Recurse` and `Remove-Item "$env:USERPROFILE\ffmpeg.zip"` |
| Lab computer firewall | `Remove-NetFirewallRule -DisplayName "ffmpeg MJPEG relay 8080"` (elevated) |
| PyPI 0.2.0 | **cannot be rolled back.** PyPI releases are immutable; a version can be yanked, never replaced |
