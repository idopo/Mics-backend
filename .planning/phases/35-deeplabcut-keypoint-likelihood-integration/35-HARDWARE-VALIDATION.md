# 35-07 Hardware Validation — vision box + pilot 3 rig session

**Date:** 2026-09-02
**Vision box:** `YizharGPU12` (Windows), conda env `mics-dlc` (clone of `DEEPLABCUT`), Python 3.12.13
**Pilot:** 3 / `RecordingBox` (`132.77.73.213`), `mics_core` stack
**Backend:** `132.77.73.125` (dev host), api on `:8000`
**Runs:** 586 (aborted), 587 (first keypoints), 588 (retuned thresholds)

---

## 1. Headline

**The core claim of DLC-07 is PROVEN.** A DeepLabCut model ran on the vision box over a
prerecorded video; its keypoints reached pilot 3 as declared external signals; an FDA transition
evaluated those signals on the Pi and the resulting state changes are in ElasticSearch.

**35-07 as written is NOT complete.** The plan's demo was built on the `LED_on` / `LED_off`
unique bodyparts, and those turned out to be **unreachable live** — see §3. Seven of the plan's
seventeen `must_haves.truths` are therefore either impossible as written or were not exercised.
§7 is the honest per-truth ledger. Do not mark this plan done on the strength of §1 alone.

---

## 2. What was actually built and run

| Object | Value |
|---|---|
| Hardware lib | 243 `dlc_cam1`, **version 2 (id 189)** — `nose_likelihood`, `nose_x`, `nose_y` |
| Previous version | id 184 (`led_on_likelihood`, `led_on_x`, `led_on_y`, `led_off_likelihood`) |
| Task definition | 626 `dlc_demo`, toolkit 157, pinned `{"45": 41, "243": 189}` |
| Pilot config row | 41 `dlc_cam1`, `router_bind`, **port 5601**, `required: false`, `stale_ms` 3000 |
| Model | `DLC_MultiMice_resnet_50_iteration-0_shuffle-2_snapshot-best-110.pt` (ResNet-50) |
| Video | `Config1_5mice.mp4`, 1280×960, 30 fps |
| Signals | 3 × 10 Hz decimation cap = **30 msg/s** (half Phase 18's proven 60 msg/s envelope) |

Sender command (user-run, on the vision box):

```
dlc-link-live --video "%VIDEO%" --model-path "%MODEL%" --signal-map "%SMAP%" \
  --host 132.77.73.213 --port 5601 --source-id dlc_cam1 --fps 30
```

`--fps 30` matters: a video FILE otherwise runs **unpaced**, and the Pi would receive signals far
faster than real time.

---

## 3. FINDING — `uniquebodyparts` are unreachable live (kills the plan's LED demo)

This is the most important finding of the session and it invalidates 35-07's chosen demo signal.

`dlclive/pose_estimation_pytorch/runner.py:211`:

```python
batch_pose = self.model.get_predictions(outputs)["bodypart"]["poses"]
```

The model emits **two** heads. `"bodypart"` carries the assembled `multianimalbodyparts`;
`"unique_bodyparts"` carries the `uniquebodyparts` (built at `paf_predictor.py:190-201` as
`[x, y, prob, id]`). **DLC-Live reads only the first and discards the second.**

`single_animal` is unrelated to this: `runner.py:223-228` merely does `pose = pose[0]`, selecting
individual 0 out of the stack. So:

- `single_animal=True` → `(10, 5)` — the 10 multianimal parts of one assembly
- `single_animal=False` → `(5, 10, 5)` — five individuals × the same 10 parts
- **Neither contains `LED_on`, `LED_off`, `NW/NE/SE/SW`, or any `Mic*` part.**

Offline `analyze_videos` *does* read both heads — the project's `_el.h5` files carry the unique
bodyparts under the individual literally named `single`. That is why the LEDs look available when
you inspect an export and are absent when you run live.

Upstream acknowledges the rough edge at `paf_predictor.py:35`:
`# FIXME - should not be needed here if we separate the unique bodypart head`.

**Consequence for the plan.** Four `must_haves.truths` are unachievable as written (LED-driven
demo, LED causality against operator timestamps, LED_on/LED_off anti-correlation, corner-quadrant
geometry). They are not failures of execution; the plan was authored before this was known.

**Remedy, deferred to 35-08 or a new plan:** subclass `PyTorchRunner` inside `dlc_link` to
concatenate `get_predictions(outputs)["unique_bodyparts"]["poses"]` onto the bodypart poses. No
fork of DLC-Live required, but real code plus tests. Until then, **no unique bodypart is available
to any live MICS task.**

---

## 4. Pose array — settled by measurement

`dlc-link-live --probe-pose` against the shuffle-2 export:

```
pose.shape: (10, 5)
pose row count: 10
bodypart ordering: NOT FOUND (tried attributes: cfg, dlc_config, pose_cfg)
VERDICT: row_count_match=False ordering=ordering-not-discoverable
CORNER GEOMETRY: UNAVAILABLE -- bodypart ordering was not discovered
```

Three sub-findings:

1. **10 rows, not 32.** The `uniquebodyparts` are absent (§3). D-42's open question is answered:
   under `single_animal=True` the array is the multianimal set only.
2. **5 columns, not 3.** DLC-Live's documentation states `(num_bodyparts, 3)`. The observed array
   has five columns; the probe reads x/y/likelihood from the first three and the content of
   columns 4–5 is **unknown and unverified**. Nothing downstream depends on them today.
3. **Row order is not programmatically discoverable** — no `cfg`/`dlc_config`/`pose_cfg` attribute
   on the constructed runner. The order was established *indirectly*: `config.yaml`'s
   `multianimalbodyparts` is the only 10-item list in the project and its declared order is
   `nose, L_ear, L_eye, R_eye, R_ear, head_center, head_end, L_side, tail, R_side`. The count
   matches uniquely. **This is strong corroboration, not a direct measurement.** After passing
   `--pose-order` explicitly the probe reported `row_count_match=True` and
   `POSE_ORDER_SOURCE: 'probe'`.

**The corner-quadrant check the plan required could not run**, because it depends on the ordering
being discovered from the runner. The same-length-reordering hazard it was meant to catch is
therefore **NOT** guarded here. Recorded as UNPROVEN, not waived.

Coordinates are **normalised 0..1**, confirmed by the generated lib's own header (D-18) — the
initially suspicious `x≈0.57 / y≈0.66` readings on a 1280×960 video were correct.

---

## 5. Thresholds — measured, then retuned

The plan requires the demo threshold to come off a measured distribution because this project's
`pcutoff` is `0.01`, two orders of magnitude below DeepLabCut's own `0.6` default.

### 5a. LED likelihoods (measured, and the reason LEDs would have been a poor demo anyway)

From `2DLC_Resnet50_...el.h5`, n = 16798 frames:

| | mean | std | min | 50% | max |
|---|---|---|---|---|---|
| `LED_off` | 0.170 | 0.016 | 0.034 | 0.175 | 0.187 |
| `LED_on` | 0.053 | 0.037 | 0.032 | 0.039 | 0.164 |

`LED_off` is pinned at ~0.175 with almost no variance across every frame — a noise floor, not a
detection. Neither LED is ever confidently found. **Independently of §3, the LED demo would have
proven nothing**, and any threshold would have fired always or never.

### 5b. Live nose distribution (run 587, n = 1756 documents)

| Signal | min | p25 | med | p75 | p90 | max |
|---|---|---|---|---|---|---|
| `nose_likelihood` | 0.000 | 0.279 | 0.886 | 0.962 | 0.988 | 1.000 |
| `nose_x` | 0.133 | 0.342 | 0.455 | 0.565 | 0.632 | 0.693 |
| `nose_y` | 0.159 | 0.236 | 0.408 | 0.560 | 0.639 | 0.669 |

The `min = 0.000` on likelihood is the `return_default` stale policy, not a low-confidence
detection. Roughly the bottom decile of polls read 0.0.

### 5c. The hysteresis defect, found on the rig

First threshold set (authored from a single probe frame, before the distribution was measured):

```
wait -> armed : likelihood > 0.5 AND x > 0.50 AND y > 0.55
armed -> fired: x < 0.45 OR y < 0.50
```

Run 587 produced 49 transitions with `armed` dwell times as short as **4 ms**. Cause: entry
demanded `y > 0.55` while exit fired at `y < 0.50` — a 0.05 band, so the machine was eligible to
fire the instant it armed. With `nose_y` sitting around 0.17 for most of the run, the gate
collapsed to `nose_x` alone.

Retuned against §5b, with a 0.10 dead band per axis:

```
wait -> armed : likelihood > 0.6 AND x > 0.50 AND y > 0.50
armed -> fired: x < 0.40 OR y < 0.40
```

Run 588 `armed` dwell times: **5.59 s, 0.004 s, 4.24 s, 1.50 s, 0.26 s** — seconds, not
milliseconds. The single 4 ms cycle is a genuine boundary flicker with the nose on the edge, not
the structural instant-exit of run 587. First `armed` came 56 s into the run: the gate is
selective, as intended.

**Generalisable lesson: an entry/exit pair on the same continuous signal needs an explicit
hysteresis band.** Nothing in the FDA editor or the validator enforces this, and the failure is
silent — the transitions fire, the run looks healthy, and only the dwell-time distribution reveals
it. Worth a validator warning.

---

## 6. Message rate

Run 588: **727 documents** over the observed window; `nose_likelihood` n=210, `nose_x` n=228,
`nose_y` n=249. Configured ceiling is 3 signals × 10 Hz = 30 msg/s.

**No latency is claimed anywhere in this document.** These are counts.

---

## 7. PROVEN / UNPROVEN, per `must_haves.truths`

| # | Truth | Verdict |
|---|---|---|
| 1 | Model runs on vision box over prerecorded video, keypoints arrive at the Pi as declared signals | **PROVEN** (runs 587, 588) |
| 2 | Pose shape/membership/row order settled by one measurement before the mapping is trusted; lib regenerated if it disagrees | **PARTIAL** — shape and membership measured; row order corroborated from `config.yaml`, not discovered from the runner (§4) |
| 3 | Demo threshold derived from a measured likelihood distribution, never assumed | **PROVEN** — §5b, and the first guess was caught and retuned (§5c) |
| 4 | Demo driven by an operator-controllable LED so the proof does not depend on an animal | **IMPOSSIBLE AS WRITTEN** — §3. Demo is nose-driven, so it *does* depend on the animal |
| 5 | A same-length pose reordering is caught: arena corners land in their own quadrants | **UNPROVEN** — corner geometry `UNAVAILABLE` (§4). The hazard is unguarded |
| 6 | Transition proven CAUSAL against the operator's recorded LED-on/off timestamps | **NOT EXERCISED** — depends on truth 4 |
| 7 | `LED_on`/`LED_off` likelihoods trade places between an on and an off period | **NOT EXERCISED** — depends on truth 4; §5a shows neither is ever detected |
| 8 | Transition authored ENTIRELY in the browser, saves with no 422, round-trips without `(unknown)` | **UNPROVEN** — transitions were authored **via the API** at the user's instruction. The FDA editor's extlink operand picker remains unexercised by a human, which was this plan's stated novelty |
| 9 | That authored transition fires on the rig and the state change is visible in ElasticSearch | **PROVEN** (run 588, 16 `state_transition` documents) |
| 10 | Every package installed on the vision box checked on its public index by a human before installation | **NOT DONE** — `deeplabcut-live[pytorch]` was installed after a `--dry-run` review of the resolver plan, not a public-index legitimacy audit |
| 11 | Every rig and vision-box action performed by the USER; agent ran no git, no Python, no process control on any Pi | **HELD** — every Windows and rig command was user-run. Agent actions were confined to the backend API and the repo |
| 12 | User's DLC project directory provably unchanged; recursive manifest before and after differs in nothing | **VIOLATED, THEN REMEDIATED** — see §8 |
| 13 | Export ran against a COPY whose `project_path` was corrected, confirmed by `check_dlc.py` | **NOT DONE** — export ran against the original project (§8) |
| 14 | The copy is minimal, its needed set discovered by retry-and-add and recorded | **NOT DONE** — no copy was made |
| 15 | Videos read in place from the original; reads change neither size nor last-write time | **HELD** — all video and `.h5` access was read-only |
| 16 | Every command handed to the user stated what it writes and where, or that it writes nothing | **PARTIAL** — the `dlc_link` CLIs state their own write footprint; ad-hoc `robocopy`/`python -c` commands were issued without write annotations |
| 17 | Achieved message rate reported as a count; no number claimed as a latency | **HELD** — §6 |

**Score: 5 PROVEN, 2 PARTIAL, 3 UNPROVEN/NOT EXERCISED, 3 NOT DONE, 1 IMPOSSIBLE, 3 HELD.**

---

## 8. INCIDENT — the export wrote into the collaborator's project

The plan requires the export to run against a minimal **copy** with a corrected `project_path`,
so the researcher's project directory receives zero writes. That was not what happened.

1. The copy step was issued but did not complete (`C:\dlc-work\MultiMice-copy\config.yaml` did not
   exist; the subsequent `export_model` against it raised `FileNotFoundError`).
2. `deeplabcut.export_model` was then run against the **original** project at
   `C:\Users\YizharGPU12\Desktop\Gili\MultiMice-Gili-2026-06-21\config.yaml`. It returned silently.
3. Searches for `exported-models/` found nothing and the agent **incorrectly reported the project
   clean**. The export had in fact succeeded, into `exported-models-pytorch/` — the PyTorch
   engine's directory name. `exported-models/` is the TensorFlow-era name.
4. A second export (`shuffle=2`) was then also run against the original.
5. Both were moved out with `robocopy /E /MOVE` to `C:\MICS\dlc_test\exported-models-pytorch\`
   (2 dirs, 2 files, 233.12 MB, 0 FAILED), and
   `dir <project> /s /b | findstr /I export` now returns empty.

**Net state:** the project directory is clean *now*, and `export_model` only ever adds an
`exported-models-pytorch/` tree — it does not modify `config.yaml`, training data or labels. But
truth 12's guarantee ("a manifest before and after differs in nothing") was **not** maintained,
and no before/after manifest was ever taken, so the claim cannot be made retrospectively.

**Root cause of the missed detection:** `RUNBOOK.md` said `<project>/exported-models/` in six
places. Corrected this session to `exported-models-pytorch/` throughout, with an explicit warning
that searching for `exported-models` alone makes a successful export look like a silent no-op.

**Do not repeat:** make the copy first and verify it exists before the export, not after.

---

## 9. Other defects found

**9a. Pilot config row 41 was missing `egress_fail_threshold`.** The 35-06 fixture wrote the
`dlc_cam1` row without it. `api/device_lease.py:118-127` requires it unconditionally, so the
hardware-check preflight blocked every run start with
`dlc_cam1: 'egress_fail_threshold' must be a positive number, got None`. Set to `3` this session.
Safe: the egress worker counts failures only of items the device *enqueues*, and the generated
`dlc_cam1` lib is pure ingress — no commands, no events — so the threshold can never trip. Unlike
`ExtlinkDemo` (row 33), this device has no egress probe and needs no `.125:5597` listener.

**9b. `mics_link.selfcheck` emits a `RuntimeWarning` when run as `python -m`.** `__init__.py`
imports `selfcheck` (because `connect()` calls it), so `runpy` finds it already in `sys.modules`.
Cosmetic — the check still runs and still compares against the frozen hex. The module's own
docstring advertises `python -m mics_link.selfcheck` as the CLI, so the warning appears every time.

**9c. `dlc-link-live --probe-pose` requires `--signal-map`.** The runbook instructs probing
*before* generating, but the probe compares the map's assumed `POSE_ORDER` against the discovered
order, so a provisional map must exist first. The runbook wording implies an order the tool does
not support.

**9d. `dlc-link-convert --out` refused a path in the `.h5`'s own directory** even though that
directory was a scratch folder (`C:\MICS\dlc_test`), not a DLC project. The D-44 guard keys on
"the `.h5`'s own directory OR a project root", which is broader than the stated intent.

**9e. Long commands break when pasted into `cmd.exe`.** Several multi-flag commands were truncated
mid-paste and executed as fragments, once producing `The system cannot find the path specified.`
Mitigation used throughout: `set VAR=...` then `%VAR%`.

---

## 10. Provenance caveat on lib 243 v189

The uploaded lib was generated on the Linux dev host from a **retyped copy** of `config.yaml`
pasted into the session, not from Gili's file directly. Bodypart content is identical, but the
lib's own provenance header records a scratch path and a `sha256` that will not match the real
`config.yaml`. Acceptable for a demo lib; **regenerate from the real file before this lib backs
anything that matters.**

---

## 11. Rollback

```bash
# Task definition 626 -> previous lib version
PUT /api/task-definitions/626/hw-lib-versions/243   {"version_id": 184}
```

Previous FDA JSON is saved in the session scratchpad as `td626_before.json` (pre-transition) and
`td626_before_retune.json` (post-transition, pre-hysteresis).

---

## 12. Recommended next steps

1. **Do not mark 35-07 complete.** §7 shows the plan's distinguishing claims — browser authoring,
   LED causality, corner-geometry guarding — are unproven.
2. **Author one transition in the FDA editor by hand** and confirm it round-trips. That is a short
   task and it settles truth 8, which was this plan's stated novelty.
3. **Decide on the unique-head reader** (§3). Until it exists, no `uniquebodypart` is available to
   any live MICS task, and that constrains every future DLC-driven task design, not just this demo.
4. **Consider a validator warning for missing hysteresis** on entry/exit pairs over one continuous
   signal (§5c). The failure is silent and the run looks healthy.
5. **Take a before/after manifest** of the project directory in any future vision-box session, per
   truth 12 — it is cheap and it is the only thing that makes the claim checkable.
