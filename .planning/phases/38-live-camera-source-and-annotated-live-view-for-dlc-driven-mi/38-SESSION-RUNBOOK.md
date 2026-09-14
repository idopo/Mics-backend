# Phase 38 — Pipeline session runbook (capture → record → model → MICS)

One page, in the order you run it. Written 2026-09-14. Every PowerShell block is short `$var=`
lines — paste one block at a time. Each block says what it writes.

**Goal of this session:** prove the whole chain runs at once — the camera records to disk on the lab
computer, the same frames reach the GPU box, the model runs on them, and keypoint signals reach pilot
3 and land in ElasticSearch. The model is the Phase 35 MultiMice model: it was not trained on this
camera, so **the keypoints will be wrong, and that is fine.** This session tests the plumbing, not
the detections.

| Machine | Address | Runs |
|---|---|---|
| LAB computer | `132.77.73.214` | the camera + one ffmpeg process (records AND sends) |
| GPU box | `132.77.73.217` | `dlc-link-live` (model, viewer, sender); ElasticSearch is also here |
| Pilot 3 `RecordingBox` | `132.77.73.213` | the `dlc_demo` task; listens for signals on port `5601` |
| Backend | `132.77.73.125` | orchestrator `:9000` |

**What was verified before this runbook was written (container, 2026-09-14):** the exact recorder
arguments below, with a synthetic mono 704x680 30 fps source in place of the camera, recorded
1200/1200 frames over 40 s into four segments with 0 drops, while `dlc-link-live` read the UDP copy
at 30.0 frames/s; the recording kept going after the reader exited; the MP4 remux kept every frame;
the viewer rendered annotated frames and polled the orchestrator. **Not verifiable there, so the
first real test is this session:** the DirectShow camera itself, the Windows firewall, and the real
model on the GPU.

---

## 0. Before anything (both machines)

**0.1 — Ask Inbar.** IC Capture on the lab computer records her data. This session takes the camera
for as long as it runs.

**0.2 — LAB: set the camera, then close IC Capture.** Exposure, gain and ROI are set in IC Capture
and stay in the driver; ffmpeg inherits them. **IC Capture must be fully closed** — the camera
allows one program at a time. Note the exposure/gain values you left it on.

**0.3 — GPU: a fresh environment, installed from PyPI.** Do **not** upgrade the existing
`mics-dlc` env: it holds the 0.1.0 wheel from the share, installed under the package's old name
`dlc-link`, and installing `mics-dlc-link` on top leaves two packages owning the same `dlc_link`
files. Leave `mics-dlc` untouched as the fallback. (0.2.0 is also unfit: it crashes at the end of
every stream run and its viewer never shows the FDA state.)

Writes: a new conda env `mics-dlc-pypi` (the clone copies DEEPLABCUT; the source env is only read).

```powershell
conda create -n mics-dlc-pypi --clone DEEPLABCUT
conda activate mics-dlc-pypi
python -m pip install --dry-run "mics-dlc-link[live]==0.2.1"
```

Read the "Would install" line. **Expected: `mics-dlc-link`, `mics-link`, `deeplabcut-live`, and
possibly `colorcet`.** If it lists `numpy`, `torch`, `torchvision`, `pyzmq`, or `opencv-python`
(without `-headless`), stop and tell me. Otherwise (writes: `mics-dlc-pypi`'s site-packages):

```powershell
python -m pip install "mics-dlc-link[live]==0.2.1"
python -m mics_link.selfcheck
pip show mics-dlc-link mics-link
pip list | Select-String 'dlc|opencv|pyzmq|torch'
```

Pass: `mics-dlc-link` is `Version: 0.2.1`; selfcheck passes; the list shows exactly one OpenCV
package and it is `opencv-python-headless`, and no line for plain `dlc-link`. **Every GPU step below
runs in `mics-dlc-pypi`** — activate it in each new window.

**0.4 — GPU: manifest of the DLC project directory, before** (writes one CSV in your home folder,
outside the project):

```powershell
$proj = 'C:\path\to\the\DLC\project'
$rows = Get-ChildItem $proj -Recurse -File
$rows | Select-Object FullName,Length,LastWriteTime | Export-Csv "$HOME\manifest-before.csv"
$rows.Count
```

**0.5 — GPU: open UDP 5000 for the lab computer only.** Elevated PowerShell. Writes one persistent
firewall rule.

```powershell
Get-NetUDPEndpoint -LocalPort 5000 -ErrorAction SilentlyContinue
$fw = @{DisplayName='MICS camera UDP 5000'; Direction='Inbound'; Protocol='UDP'}
$fw += @{LocalPort=5000; RemoteAddress='132.77.73.214'; Action='Allow'}
New-NetFirewallRule @fw
```

The first line must print **nothing** (port free). If it prints a row, stop — pick another port and
change `5000` everywhere below.

**0.6 — GPU: can it reach the orchestrator?** Writes nothing.

```powershell
Invoke-RestMethod http://132.77.73.125:9000/pilots/live | ConvertTo-Json -Depth 4
```

Pass: JSON with `RecordingBox` and `"connected": true`.

---

## 1. LAB — start recording (and sending)

**1.1 — A folder for this session** (writes: the folder):

```powershell
$rec = 'D:\MICS\recordings\2026-09-pipeline-test'
New-Item -ItemType Directory -Force $rec | Out-Null
Set-Location $rec
New-Item -ItemType Directory -Force log | Out-Null
```

**1.2 — The recorder.** One ffmpeg: file first, network copy second. Writes `rig-<time>.mkv` every
10 minutes into `$rec`, and ffmpeg's own log into `$rec\log`. Sends UDP to the GPU box.

```powershell
$f = "$env:USERPROFILE\ffmpeg\ffmpeg-9.0.1-essentials_build\bin\ffmpeg.exe"
$dst = 'udp://132.77.73.217:5000?pkt_size=1316'
$t0 = '[f=segment:reset_timestamps=1:segment_format=matroska:segment_time=600:strftime=1]'
$t0 += 'rig-%Y%m%d-%H%M%S.mkv|[bsfs/v=h264_mp4toannexb:f=mpegts:onfail=ignore]'
$t0 += $dst
$dev = 'video=DMK 33GP1300 [BR2_UP]'
```

```powershell
$a=@('-hide_banner','-f','dshow','-rtbufsize','100M','-i',$dev)
$a+=@('-map','0:v','-c:v','libx264','-preset','veryfast','-crf','18')
$a+=@('-pix_fmt','yuv420p','-g','30','-flags','+global_header')
$a+=@('-fps_mode','passthrough','-f','tee',$t0)
$env:FFREPORT = 'file=log/rig-%t.log:level=32'
& $f @a
```

These are exactly the arguments `dlc-link-relay` generates (checked token for token). Leave this
window running. **To stop recording later: press `q` in this window** — that closes the last segment
cleanly.

**1.3 — Is it recording?** In a second PowerShell window, twice, ~15 s apart. Writes nothing.

```powershell
Get-ChildItem 'D:\MICS\recordings\2026-09-pipeline-test\*.mkv' | Select-Object Name,Length
```

Pass: a `rig-*.mkv` whose `Length` grows. If ffmpeg instead printed
`Could not run graph ... device already in use`, IC Capture is still open (step 0.2).

---

## 2. GPU — are frames arriving? Then measure the rate with no model

**2.1 — Look at the stream with ffplay** (no Python involved; writes nothing):

```powershell
$fp = "$env:USERPROFILE\ffmpeg\ffmpeg-9.0.1-essentials_build\bin\ffplay.exe"
& $fp -hide_banner -fflags nobuffer 'udp://0.0.0.0:5000?timeout=5000000'
```

Pass: the rig picture appears within a few seconds (a keyframe arrives every second). **Close the
ffplay window before 2.2** — only one program can listen on UDP 5000. If nothing appears after
~10 s, the firewall (0.5) or the recorder (1.2) is the problem; stop and tell me.

**2.2 — Baseline: 60 s, no model** (writes nothing):

```powershell
$src = 'udp://0.0.0.0:5000?timeout=5000000&overrun_nonfatal=1&fifo_size=50000'
dlc-link-live --capture-only --source $src --max-seconds 60
```

`timeout=5000000` is required, not optional: without it a stopped stream hangs the run forever with
no summary. **Copy the whole `dlc-link-live summary:` block to me.** The numbers that matter:
`frames_read`, `frames_skipped`, `duration_s`, `rate_frames_read_per_s`.

---

## 3. GPU — model + live view, nothing sent to the Pi

Writes nothing (`--dry-run` discards signals). Use the same model and signal-map files as Phase 35.

```powershell
$model = 'C:\path\to\DLC_MultiMice_resnet_50_iteration-0_shuffle-2_snapshot-best-110.pt'
$smap = 'C:\path\to\dlc_cam1_signals.py'
$ov = 'nose_x>0.50,nose_y>0.50,nose_likelihood>0.6'
```

```powershell
$v=@('--source',$src,'--model-path',$model,'--signal-map',$smap,'--dry-run')
$v+=@('--view','--view-sink','mjpeg','--view-port','8090','--view-min-likelihood','0.6')
$v+=@('--overlay',$ov,'--max-seconds','120')
dlc-link-live @v
```

When it prints `view: mjpeg sink -- open http://127.0.0.1:8090/`, open that address in a browser
**on the GPU box**. The picture updates live; the text above it is a snapshot — refresh to update
it. Expect a marker labelled `nose <likelihood>` somewhere wrong; the two top-left lines
(`condition: ...`, `overlay: authored locally ...`) confirm the overlay is drawn.

**Copy the summary to me.** Compare `rate_frames_inferred_per_s` with 2.2's
`rate_frames_read_per_s`: that ratio is the keep-up number `--min-rate` will later be set from.

---

## 4. Pilot + GPU — the full chain

**4.1 — Start the run first.** Pilot 3's `dlc_cam1` config is `required: false`, so the run goes
first and the sender second. In the web UI, start a new run of **session 122 on `RecordingBox`**
(the `dlc_demo` session used for runs 587/588). If you prefer the API:
`POST /api/sessions/122/start-on-pilot` with `{"pilot_id": 3, "mode": "new"}`.

**4.2 — Start the sender** (writes nothing on disk; sends signals to `132.77.73.213:5601`):

```powershell
$v=@('--source',$src,'--model-path',$model,'--signal-map',$smap)
$v+=@('--host','132.77.73.213','--port','5601','--source-id','dlc_cam1')
$v+=@('--view','--view-sink','mjpeg','--view-port','8090','--view-min-likelihood','0.6')
$v+=@('--overlay',$ov,'--pilot','RecordingBox')
$v+=@('--orchestrator-url','http://132.77.73.125:9000')
$v+=@('--es-url','http://132.77.73.217:9200','--max-seconds','300')
dlc-link-live @v
```

Refresh `http://127.0.0.1:8090/` a few times during the run: the `run:` line should name the run
id, and `FDA state:` should show `wait` (or `armed`/`fired` if the wrong keypoints happen to cross the
thresholds — they may never do so, and that is not a failure of the chain).

**4.3 — After the 300 s:** stop the run in the UI. Send me the sender summary (it now includes a
`link.stats:` line) and the run id. **I will count the `dlc_cam1.*` documents for that run in
ElasticSearch** — that count, not an FDA transition, is the proof that signals reached the Pi.

---

## 5. LAB — stop recording and check nothing was lost

**5.1 — Stop:** press `q` in the recorder window (step 1.2).

**5.2 — Three witnesses** (second window; writes nothing):

```powershell
Set-Location 'D:\MICS\recordings\2026-09-pipeline-test'
$log = Get-ChildItem log\rig-*.log | Sort-Object LastWriteTime | Select-Object -Last 1
$hits = Select-String -Path $log.FullName -Pattern 'frame=\s*(\d+)' -AllMatches
"W1 ffmpeg frames: " + @($hits)[-1].Matches[-1].Groups[1].Value
"W3 dropped lines: " + (Select-String -Path $log.FullName -Pattern 'frame dropped').Count
```

```powershell
$fq = "$env:USERPROFILE\ffmpeg\ffmpeg-9.0.1-essentials_build\bin\ffprobe.exe"
$pr = @('-v','error','-count_frames','-select_streams','v:0')
$pr += @('-show_entries','stream=nb_read_frames','-of','csv=p=0')
$tot = 0
foreach ($s in Get-ChildItem rig-*.mkv) {
  $n = & $fq @pr $s.FullName
  "$($s.Name) $n"
  $tot += [int]$n
}
"W2 frames in files: $tot"
```

Pass: **W1 = W2** and **W3 = 0**. The GPU's `frames_read` values from steps 2-4 are each lower than
W1 — expected, because each GPU run covered only part of the recording. Send me all three numbers.
Under auto-exposure, W2 below `30 × seconds recorded` is not a loss by itself (see
`dlc_link/RUNBOOK.md` ACQUISITION §8).

**5.3 — Disk rate:** the size of one full 10-minute segment × 6 = GB per hour on this camera. Tell
me the number; the synthetic tests bracket it between ~0.7 GB/h (a static picture) and ~21 GB/h
(pure noise).

**5.4 — MP4 copies, if wanted** (writes one `.mp4` next to each `.mkv`; no re-encode, no quality
loss):

```powershell
foreach ($s in Get-ChildItem rig-*.mkv) {
  $out = $s.FullName -replace '\.mkv$', '.mp4'
  & $f -hide_banner -v error -i $s.FullName -c copy -movflags +faststart $out
}
```

Why `.mkv` first: an MP4 that is not closed cleanly (crash, power cut) is unreadable, while a
`.mkv` segment stays readable up to its last frame.

---

## 6. Close out

**6.1 — GPU: manifest, after** (writes one CSV in your home folder), then compare:

```powershell
$rows = Get-ChildItem $proj -Recurse -File
$rows | Select-Object FullName,Length,LastWriteTime | Export-Csv "$HOME\manifest-after.csv"
$before = Import-Csv "$HOME\manifest-before.csv"
$after = Import-Csv "$HOME\manifest-after.csv"
Compare-Object $before $after -Property FullName,Length,LastWriteTime
```

Pass: **no output**.

**6.2 — Give the camera back:** reopen IC Capture and confirm it shows the live image.

**6.3 — Optional rollback on the GPU box** (elevated): `Remove-NetFirewallRule -DisplayName 'MICS
camera UDP 5000'`. Leave it if you will run this again.

---

## If something fails

| Symptom | Where | Likely cause |
|---|---|---|
| `Could not run graph ... device already in use` | LAB 1.2 | IC Capture still open |
| `.mkv` does not grow | LAB 1.3 | recorder not running — read its window |
| ffplay shows nothing | GPU 2.1 | firewall rule (0.5) or wrong address in `$dst` |
| `could not read the first frame` | GPU 2.2+ | ffplay still open on port 5000, or no stream |
| run ends `read-failures-exhausted` | GPU | the stream stopped for >5 s — check the recorder window |
| `FDA state: unavailable - no state_transition document was found` | viewer | run started without the `dlc_demo` FDA, or nothing logged yet |
| `run: no active run` | viewer | run not started, or wrong `--pilot` name |

Send me the exact error text; do not retry with changed flags first.
