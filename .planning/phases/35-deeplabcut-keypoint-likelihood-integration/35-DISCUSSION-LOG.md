# Phase 35: DeepLabCut Keypoint Likelihood Integration - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in CONTEXT.md — this log preserves the alternatives considered.

**Date:** 2026-08-31
**Phase:** 35-deeplabcut-keypoint-likelihood-integration
**Areas discussed:** Multi-animal handling, First proof, Target environment, Declaration path,
Liveness debt, Target rig, Decimation location, Runbook collapsing, Offline workflow shape

---

## Pre-discussion correction (not a gray area — a factual reset)

Before any question was asked, the user's model-directory listing invalidated the research
baseline. `35-DLC-LIVE-NOTES.md` had been written against "the lab runs DeepLabCut 2.2.3 /
TensorFlow / Python 3.8". The listing showed `dlc-models-pytorch/` and
`evaluation-results-pytorch/`, which only exist for the DLC 3.x PyTorch engine. The user then
supplied `conda list` for a second env (`DEEPLABCUT`: Python 3.12.13, DLC 3.0.0, torch 2.5.1) and
asked *"what are the diff im kinda surprised it worked with that env"* — confirming two DLC envs
exist on the box and the earlier inspection had profiled the wrong one.

A "SUPERSEDING CORRECTION — 2026-08-31" section was appended to `35-DLC-LIVE-NOTES.md` before
planning, so the stale premises cannot mislead downstream agents.

---

## Multi-animal handling

| Option | Description | Selected |
|--------|-------------|----------|
| One animal at a time | Multi-animal model, single subject on the rig; take the single/best detection | |
| Multiple, identity matters | Per-individual signals (`mouse1_nose_x`, ...) | |
| Multiple, identity does not matter | Aggregates only (n_detections, any-animal-in-zone) | |
| **Free text** | *"multipple but right now I only wish to test the dlc connection with the pi and habe this end result of a generic way for all lab members to link thier midel to the pi so I dont care. but some models are multianimal yes"* | ✓ |

**User's choice:** free-text — the deliverable is the generic path, not multi-animal identity.
**Notes:** Resolved by upstream evidence rather than by preference. DLC-Live's README states that
`single_animal=True` collapses `(num_individuals, num_keypoints, 3)` to `(num_keypoints, 3)`, so
multi-animal is a one-flag problem in v1. Per-individual expansion deferred (identity swaps produce
*wrong* transitions, a worse failure mode than occlusion).

---

## First proof

| Option | Description | Selected |
|--------|-------------|----------|
| FDA transition on a live pilot | Paced video -> DLC -> mics-link -> pilot -> transition fires, seen in ES | ✓ |
| Signals visible, no FDA yet | Stop at "keypoints arrive as trackers" | |
| Offline only — convert to a replay file first | `.h5` -> wide CSV -> `mics-link-replay` | |

**User's choice:** free-text — *"a model notifing a cetrain x y and a high likeleehood should fire a
transition. just example"*
**Notes:** Names x/y AND likelihood together, so the ANDed coordinate+likelihood guard (DLC-03(c))
is exercised in the FIRST checkpoint rather than deferred.

---

## Target environment

| Option | Description | Selected |
|--------|-------------|----------|
| New env, Python 3.10-3.12 + DLC 3.x | Matches the pytorch model; unlocks deeplabcut-live 1.1.0 | ✓ |
| Keep DEEPLABCUT223 (Python 3.8, TF) | Period-correct, forces deeplabcut-live 1.0.4 | |
| Support both | Adapter branches on pose.ndim and model_type | |

**User's choice:** supplied the `DEEPLABCUT` conda list, which resolved the question empirically.
**Notes:** Python 3.12.13 sits inside `deeplabcut-live` 1.1.0's `>=3.10,<3.13`. `pyzmq 27.1.0` and
`msgpack 1.2.1` already exceed the SDK floors, so installation is a dependency no-op. Verified on
the box: RTX 3060, `torch.cuda.is_available()` True, `pip check` clean.

---

## Declaration path (the "generic way for anyone" deliverable)

| Option | Description | Selected |
|--------|-------------|----------|
| CLI generator: config.yaml -> lib source | `python -m dlc_link.generate ...` emits lib source + signal-name map | ✓ |
| Browser: upload config.yaml, backend generates | React page creating lib + module + config row | |
| Both — CLI first, browser wraps it later | Generator as a library, CLI now, page later | |

**User's choice:** CLI generator (recommended option).
**Notes:** Keeps frontend work out of a phase that otherwise has none. The generator must EMIT the
bodypart -> Python-identifier map that the adapter imports; re-deriving it on both sides would make
every frame silently droppable as `unknown_name`.

---

## Liveness debt from Phase 34

| Option | Description | Selected |
|--------|-------------|----------|
| Fix it in this phase, own plan step | Cut lib 177 v3 without the `liveness_hook -> True` override, re-run the quiet test | ✓ |
| Give the new DLC lib a correct hook, leave 177 alone | Prove DLC-06 on new code only | |
| Record as UNPROVEN and move on | Ship with the gap documented | |

**User's choice:** fix it in this phase (recommended option).
**Notes:** Risk was stated before the choice and accepted: the override's own docstring says the
default path "reported not-alive while `on_recv` was demonstrably stamping `_last_msg_ts_ms`,
stranding the readiness gate in 2 of 4 rig runs", so removing it may resurface a real bug. Planned
as an investigation with debugging room, not a checkbox.

---

## Target rig

| Option | Description | Selected |
|--------|-------------|----------|
| Pilot 3 / RecordingBox (.213) | Where Phase 34 runs 582/583/584 succeeded; binds 5599 per-run | ✓ |
| Pilot 1 (.72.28) | Original ExtlinkDemo fixture; older pi-mirror stack | |
| You pick / confirm at the rig | Settle during planning | |

**User's choice:** Pilot 3 / RecordingBox.
**Notes:** Also supplies the cheap reconnect test — stop-run/start-new-run is indistinguishable from
a pilot restart to the client, so SDK-07 can be exercised without touching the pilot service.

---

## Decimation location

| Option | Description | Selected |
|--------|-------------|----------|
| In the DLC adapter | Deadband is a decimation policy; SDK has no opinion on rates | ✓ |
| As a reusable piece in mics_link | Generic filter any noisy-scalar sender wants | |
| Both — generic filter in SDK, policy in adapter | Cleanest separation, needs a Phase 34 amendment | |

**User's choice:** in the DLC adapter (recommended option).
**Notes:** Also the only option compatible with `sdk/`'s device-neutrality guard without reopening
Phase 34's public API.

---

## Runbook collapsing

| Option | Description | Selected |
|--------|-------------|----------|
| Document all six, collapse none | Honest numbered runbook; record which step is the obstacle | ✓ |
| Add one endpoint doing lib+module+config | `POST /api/dlc/register`, six steps -> three | |
| Generator emits a setup script calling the existing API | Collapses steps without new backend surface | |

**User's choice:** document all six (recommended option).
**Notes:** Matches DLC-13(d)'s own instruction that an un-collapsible runbook is itself the
deliverable. Zero new backend surface; the phase stays about DLC.

---

## Offline workflow shape

| Option | Description | Selected |
|--------|-------------|----------|
| Live-shaped first, converter second | Video -> DLCLive Processor -> mics_link, Pacer-paced; then `.h5` -> wide CSV -> replay | ✓ |
| Converter first, live-shaped second | Prove the Pi path with no DLC install at all | |
| Only the live-shaped one | Drops DLC-09's no-GPU regression test | |

**User's choice:** live-shaped first (recommended option).
**Notes:** Workflow A is the live pipeline with a file substituted for a camera, so the camera later
becomes a one-line change (drop `Pacer.wait_until`). Both A and B ship.

---

## Side thread (not a phase decision)

The user asked mid-discussion for a way to validate both conda envs generally, then for GPU library
coverage specifically. Two read-only diagnostics were delivered: `check_env.py` (interpreter, DLC
engine, `nvidia-smi`, CUDA/cuDNN DLL loadability, a real GPU matmul, wire deps, msgpack-numpy patch
state, mics_link selfcheck) and `check_dlc.py` (config.yaml contents, on-disk snapshots,
exported-models presence, per-video fps; `--infer` opt-in). Their output is a planning input, not
just hygiene — the bodypart list feeds the generator and the measured fps sizes the decimation
budget.

Two readings from the first run were corrected rather than reported as findings: `DEEPLABCUT223`'s
TensorFlow **does** see the GPU (an earlier CPU-only prediction was wrong), and that env's
`torch 1.13.1+cpu` is incidental baggage in a TF env rather than a fault. A third, the
`msgpack-numpy PATCHED` reading, was **withdrawn as contaminated** — the probe imported
`msgpack_numpy` itself and may have caused the patch it reported. The checker was fixed to detect
presence via `find_spec` without importing.

---

## Claude's Discretion

- Module layout under `mics-backend/dlc_link/`, CLI flag spelling, generator template mechanics.
- Deadband and Hz-cap defaults, subject to the ~60 msg/s budget.
- Which bodyparts the demo lib declares — user explicitly did not care.
- Plan decomposition and wave assignment.

## Deferred Ideas

- Per-individual multi-animal signals.
- A browser page for lib generation.
- `POST /api/dlc/register` or a generated setup script.
- Ingress-side drop counting on the Pi (a Phase 18 amendment).
- A batched multi-signal wire frame.
- Live camera input (deliberately a one-line swap from workflow A).
