# Phase 35 — DLC-Live execution model: verified notes

**Gathered:** 2026-08-30, during the Phase 34 DLC-fit review.
**Status:** pre-planning notes. NOT a plan. Feeds `/gsd-discuss-phase 35`.

## Decisions ALREADY TAKEN — do not re-ask in `/gsd-discuss-phase 35`

Four are the user's own words or direct choices from the 2026-08-30 session. Everything else in
this file is *evidence*, which is research material, not decisions — a CONTEXT records what the
user decided, and only these four qualify so far.

1. **The lab runs DeepLabCut 2.2.3** — the TensorFlow engine, not PyTorch. Fixes `model_type="base"`,
   2-D pose only, `export_model` first, `pose_cfg.yaml` as the bodypart source.
2. **Offline prerecorded movie FIRST, live camera after — and the design must serve both.**
   *"as a first phase will probably use an offline prerecorded movie with the trained model but need
   to be able to work with both."* This is why `Pacer` is public in Phase 34.
3. **The vision box is Windows, and cross-OS is a requirement, not a nicety.** *"since this is
   science we are doing and sadly windows is super used."* Drove SDK-14.
4. **x/y coordinates are in scope, not likelihood-only.** *"would love to see x y coordinates not
   just likelihood since this is a big part of dlc in the first place."* Drove the DLC-03 amendment
   and the likelihood-as-guard pattern below.

**Still genuinely open** (real questions for discuss-phase, not settled by anything here): whether
to build a fresh Python 3.10–3.12 env (unlocking `deeplabcut-live` 1.1.0) or stay on 3.8 with
1.0.4; which bodyparts to declare and at what decimated rate; whether the offline-movie runner is
the live adapter verbatim or a separate entry point; and whether the deadband/Hz cap lives in the
adapter or somewhere reusable.

---

Verified against `DeepLabCut/DeepLabCut-live` source (`dlclive/dlclive.py`,
`dlclive/benchmark.py`, `dlclive/processor/`), not from memory.

---

## How a trained model is actually executed

```python
from dlclive import DLCLive, Processor

class MicsProcessor(Processor):
    def process(self, pose, **kwargs):     # pose: np.ndarray
        return pose                        # MUST return it — DLC assigns self.pose from this

live = DLCLive(
    model_path,                # exported model directory
    model_type="pytorch",      # "base" (TF), "pytorch", "tensorrt", "tflite"
    processor=MicsProcessor(),
    resize=0.5,
    single_animal=True,
)
live.init_inference(first_frame)           # warm-up; returns a pose too
while True:
    ret, frame = cap.read()
    pose = live.get_pose(frame)            # calls processor.process(pose, **kwargs) INSIDE
live.close()
```

`DLCLive.__init__` full signature: `(model_path, model_type="base", precision="FP32",
tf_config=None, single_animal=True, device=None, top_down_config=None, top_down_dynamic=None,
cropping=None, dynamic=(False, 0.5, 10), resize=None, convert2rgb=True, processor=None,
display=False, pcutoff=0.5, display_radius=3, display_cmap="bmy")`.

## Five facts that shape the Phase 35 adapter

1. **`process()` runs synchronously on the inference thread, once per frame.** `get_pose()` calls
   `_post_process_pose()`, which does `self.pose = self.processor.process(self.pose, **kwargs)`
   with the kwargs forwarded from the original `get_pose()` call. The researcher does not own the
   call site. Phase 34's SDK-15 exists for exactly this. Corollary: the adapter must **not** open
   or close a `MicsLink` inside the Processor — `Processor` has no guaranteed teardown hook
   (`save()` is invoked by the DLC-Live GUI, not by `DLCLive`). Own the client outside, in a
   `with connect(...)` block, and pass it in.
2. **Pose shape:** `(n_bodyparts, 3)` = `x, y, likelihood`. DLC-03's `<keypoint>_likelihood` is
   column 2. The 3-D `(n_detections, n_bodyparts, 3)` multi-animal shape arrives only with the
   **PyTorch** engine (DLC 3.0) — **this lab's DLC 2.2.3 models cannot produce it**, so the adapter
   needs no branch for it in v1. Guard rather than support: assert `pose.ndim == 2` and fail loudly
   with a message naming the engine, so a future 3.0 model does not silently index the wrong axis.
3. **Every value is a numpy scalar.** Phase 34's `mics_link.values.as_scalar` is the documented
   conversion (`.item()`); `float(...)` is NOT the recommended fix — it flattens int/bool/float.
4. **A video FILE runs unpaced.** `benchmark.py` reads with `cv2.VideoCapture` and infers as fast
   as the model allows, with no real-time pacing. The user's first workflow is a prerecorded movie
   through the trained model, so the frame loop must be paced with `mics_link.timing.Pacer` at the
   video's native FPS — otherwise DLC-05's `stale_after_ms` is exercised at a timebase unrelated to
   the live case and the run proves the wrong thing.
5. **A DLC export is not a `(t, signal, value)` file.** DLC writes `.h5`; its CSV carries a 3-row
   `scorer` / `bodyparts` / `coords` MultiIndex header. **Phase 35 owns that converter** — it must
   not enter `mics_link`, whose device-neutrality test bans `deeplabcut` / `keypoint` / `bodypart` /
   `pose` / `\bdlc\b` under `sdk/`. Phase 34's replay reader accepts a **wide** file
   (`t` + one column per signal), which is the natural conversion target: ~36k rows for a 20-min
   30 fps 8-bodypart export instead of ~864k.

## Environment / OS — CORRECTED 2026-08-30: this lab runs **DeepLabCut 2.2.3**

The user stated the lab uses **DLC 2.2.3**. That is the **TensorFlow** era (PyPI upload
2022-10-09; `tensorflow>=2.0`, `numpy>=1.18.5`; the PyTorch engine did not arrive until DLC 3.0).
Everything below follows from that and **supersedes** any earlier "PyTorch backend" assumption.

- **`model_type="base"`, never `"pytorch"`.** A 2.2.3 model is a TF graph. `"tflite"` and
  `"tensorrt"` are the other legal values; `"pytorch"` is not applicable.
- **The model must be EXPORTED first.** `deeplabcut.export_model(...)` produces
  `exported-models/DLC_<net>_<task>_<date>_shuffle<n>_<snapshot>/` containing the `.pb` file(s)
  **and `pose_cfg.yaml`**. DLC-Live is pointed at *that* directory, not the training project.
  Pointing it at the project dir is the single most common setup failure (DeepLabCut-live issue
  #22 is exactly `pose_cfg.yaml was not found`). Put this in the runbook (DLC-13d).
- **The bodypart list for DLC-02's generator is `all_joints_names` in that exported
  `pose_cfg.yaml`.** A concrete, checked-in-able input file. Note the format is engine-specific:
  a future DLC 3.0 PyTorch export differs, so the generator should record which engine a lib
  version was generated from.
- **Python version — the real constraint, and it is tight:**

  | dlclive | requires_python | notes |
  |---|---|---|
  | 1.1.0 (Feb 2026, current) | `>=3.10,<3.13` | Windows `[tf]` extra pins `tensorflow>=2.7,<=2.10` for Python<3.11 |
  | 1.0.2 / 1.0.3 / 1.0.4 (2022–23) | older | the contemporaries of DLC 2.2.3; run on Python 3.7/3.8 |

  So the vision box is realistically **Python 3.10** (current dlclive + TF on Windows) or **3.8**
  (period-correct dlclive 1.0.x). TF has no native Windows GPU support after 2.10, which pushes a
  GPU box to Python 3.10 specifically.
- **Phase 34's `requires-python = ">=3.8"` floor is therefore correct and load-bearing, not
  theoretical.** A 3.9+ floor would break the 1.0.x configuration; a 3.11+ floor would break both.
- **⚠ Dependency lower bounds must be LOW, not merely un-capped.** `pyzmq 27.2.0` requires Python
  `>=3.9`, so a floor of `pyzmq>=27` is unresolvable on a Python 3.8 box — an un-capped but
  *too-high* lower bound fails exactly the same way an upper cap would. Plan 34-01 must pick floors
  that actually resolve on the minimum supported Python and **verify it**, e.g.
  `python -m pip download --no-deps --python-version 3.8 --only-binary=:all: mics-link`.
- **numpy:** dlclive 1.1.0 pins `numpy<2,>=1.20`; DLC 2.2.3 wants `numpy>=1.18.5`. The env holds
  numpy 1.2x. `mics_link` never depends on numpy, and `as_scalar`'s `.item()` behaves identically
  on numpy 1.x — so nothing here is at risk, but it is why the no-numpy rule is a correctness
  property rather than packaging tidiness.
- `mics_link` must install into that environment with `python -m pip check` clean — Phase 34's
  34-09 Windows checkpoint.

## What Phase 34 now hands Phase 35 (all added 2026-08-30)

| Handed over | Requirement | Why Phase 35 needs it |
|---|---|---|
| `send_signal` safe from a foreign callback thread at frame rate | SDK-15 | `Processor.process` is that thread |
| `mics_link.values.as_scalar` | SDK-04 (amended) | every pose value is a numpy scalar |
| `mics_link.timing.Pacer` | SDK-12 (amended) | pace a video-file frame loop to real time |
| Wide replay files | SDK-12 (amended) | the sane conversion target for a DLC export |
| `sdk/examples/callback_sender.py` | SDK-15 | the push shape DLC imposes, documented device-neutrally |
| Windows-proven install + replay | SDK-14 | the vision box is Windows |

## Still open for `/gsd-discuss-phase 35`

- Multi-animal: refuse, or pick a detection?
- Where the deadband + Hz cap live (DLC-04) — in the adapter, or as a reusable `mics_link` piece?
  Leaning adapter: a deadband is a decimation policy, and the SDK has no opinion on rates.
- Whether the offline-movie run reuses the live adapter verbatim (it should — that is the point of
  pacing it) or is a separate entry point.

---

# Pi-side ingress — read before sizing anything (verified 2026-08-30)

Read directly from `external_hardware_ingress.py`, `external_hardware.py` and
`external_hardware_binding.py` in **both** `~/pi-mirror` and `~/mics_core`. The two ingress files
differ (mics_core adds one-clock timestamping, PLAT-31/34) but the **ingress structure is identical**.

## ⚠ There is no ingress queue. The "bounded at 256" figure is wrong.

`STATE.md` and **DLC-04** both state *"the Pi's ingress queue is bounded at 256."* That is not what
the code does:

- `external_hardware.py` creates `self._recv_buffer = collections.deque(maxlen=256)`.
- `external_hardware_ingress.py` does `owner._recv_buffer.append(raw)` — and **nothing anywhere in
  either tree ever reads it.** It is an append-only rolling ring of raw frames, presumably for
  forensics. It buffers nothing and bounds nothing.
- The only real bounded queue in the substrate is the **egress** one:
  `EgressWorker(maxsize=64)` (`external_hardware_runtime.py:26`, wired at
  `external_hardware_binding.py:103`) — drop-NEWEST **and counted**. That is outbound, not inbound.

**What actually happens on ingress:** `bind_socket` wires
`ZMQStream(sock, ioloop).on_recv(owner._on_recv)`, and `on_recv` runs the whole path —
`identity_ok` → `decode_envelope` → `apply_envelope` → `tracker.set(value)` → event dispatch —
**synchronously on the Tornado IOLoop thread**, inline, per message. No queue, no worker, no
backpressure.

**Three consequences DLC-04 and DLC-10 must be re-derived from:**

1. **The failure mode at high rate is IOLoop starvation, not queue overflow.** The ingress
   docstring says it outright: *"that loop also serves every other module's ingress and the pilot's
   own orchestrator DEALER, so one traceback here takes the STOP channel down with it."* Saturating
   it degrades **FDA timing and the STOP path**, which is far worse than losing a keypoint sample.
   The soak must watch FDA transition timing and STOP responsiveness, not just a drop counter.
2. **Overflow drops are silent and uncounted.** `DecodeStats` counts `malformed` /
   `unknown_name` / `type_mismatch` — all of which require the frame to have *arrived*. A frame
   discarded at ZMQ's socket high-water mark is counted **nowhere**. DLC-04's *"a drop is
   acceptable; a silent drop is not"* is therefore **not satisfiable on the Pi side as built** —
   the sender's own `stats.dropped` (SDK-06) is the only drop accounting that exists end to end.
   Either accept that and say so, or add ingress counting — which is a Phase 18 amendment, not a
   quiet edit here.
3. **Every accepted SIG costs one logged ES event.** `owner._trackers[name].set(value)` carries
   `@log_action`, so it dispatches a CONTINUOUS event *"for free"* (the code's own comment).
   8 bodyparts x 30 fps = 240 msg/s in becomes **240 ES events/s out, per pilot**. That is the
   ingestion load DLC-10's soak has to survive, and it is a 1:1 amplification nobody has costed.

Arithmetic worth writing into the phase: 8 keypoints, likelihood only, 30 fps = **240 msg/s**
against a proven envelope of ~60 msg/s. With `x`/`y` opt-in (DLC-03) it is 720 msg/s. Decimation
(DLC-04) is mandatory, not a tuning knob — but size it against the IOLoop and ES, not against 256.

## Four Pi-side traps for the DLC-02 generator

1. **`stale_after_ms == 0` means NEVER stale** (`resolve_stale_value`). If the generator's default
   is 0, **DLC-05's entire occlusion-safety semantic vanishes silently** and a latched
   `nose_likelihood > 0.9` stays latched forever. The generator must require an explicit non-zero
   value, and preflight should reject 0 on a DLC lib.
2. **`stale_policy` is validated at READ time, and it RAISES.** `resolve_stale_value` is the one
   ingress-adjacent function that raises rather than counts — an unknown policy string is a
   `ValueError` **inside FDA evaluation, on the rig, mid-run**. Legal values are exactly
   `hold_last` / `return_default` / `return_none`. A generator typo is a run-killer, so validate at
   generation time.
3. **An undeclared signal name is dropped and counted `unknown_name` — invisible from the sender.**
   DLC bodypart names are arbitrary user strings (`"left ear"`, `"tail-base"`, `"Nose"`); the
   generator must turn them into valid Python identifiers, and **the adapter must apply the exact
   same transform** or every frame is silently discarded. DLC-13(a)'s "one declaration site" should
   mean the generator emits the bodypart→signal-name mapping and the adapter *imports* it — never
   that both re-derive it.
4. **`ALLOWED_DTYPES` is enforced at class-build time** (`resolve_dtype`, `TypeError`) from the
   annotation, else `type(default)`. A generated `@signal` with neither is a hard failure at lib
   import on the Pi. `coerce_value` then calls `dtype(raw)` on ingress, so a `float`-declared
   signal fed an int coerces fine — but a `bool`-declared signal fed `1` is a counted
   `type_mismatch`, invisible to the sender (Phase 34 already documents this).

## Standing risks Phase 35 inherits (not new, but easy to rediscover the hard way)

- **EXTLINK-19's picker: CHECKED 2026-08-30 — it works. The ⚠ SPLIT VERDICT is STALE.**
  Traced the whole chain against the **live DB and live API**, not just the source:

  | Link | Evidence |
  |---|---|
  | `ast_metadata.extlink` -> signals | lib version 177 yields `left_paw_x`, `right_paw_x` (both `float`) |
  | signals x `pilot_hardware_config.source_id` -> keys | `module_extlink_signals` returns `demo.alive`, `demo.left_paw_x`, `demo.right_paw_x`, `conflict: false`, with `by_pilot` provenance for pilots 1 and 3 |
  | API -> browser | `GET /api/toolkits/by-name/source_less_toolkit` (the call `TaskEditor.tsx:94` actually makes) returns `extlink_signals` populated |
  | toolkit -> picker | **both** call sites pass it: `ConditionBuilder.tsx:50` and `ArgInput.tsx:38`, each `buildViewOptions(..., toolkit?.extlink_signals ?? [])` — so the condition builder *and* the action-argument picker are covered, which is what EXTLINK-19 requires |
  | save gate | `reject_if_hard_errors(db, <fda with {"view":"demo.left_paw_x"}>, 100)` -> **accepted, no 422**; the same FDA with `demo.nose_typo` -> `422 references unknown variable/flag` |
  | tests | 150 backend (`test_extlink_keys` / `test_view_key_preflight` / `test_hardware_libs_extlink`) + 193 frontend, all green; 9 frontend tests are extlink-specific, incl. `.alive` labelling, conflict warnings, `isKnownViewOption`, and operand round-trip |

  **What remains genuinely unproven is narrow:** a human opening the editor in a browser and
  *seeing* the option render, pick and save. Every layer beneath that is verified. That is a
  two-minute manual check, not a build — Phase 35 should schedule it as a UAT step, not budget
  Phase 18 repair work inside its critical path.

- **⚠ ORDERING CONSTRAINT the picker imposes on DLC-13d's runbook.** `derive_extlink_keys` returns
  `[]` unless `config["source_id"]` is a non-empty string in a **`pilot_hardware_config` row**.
  Signal *names* are pilot-invariant (from the lib's AST), but the *keys* are not — no config row
  means no `source_id` means **an empty picker**, with no error to explain it. So the runbook order
  is forced: upload lib -> register module -> **create the pilot config row** -> only then are the
  keys authorable. A researcher who uploads a DLC lib and goes straight to the FDA editor sees
  nothing and has no idea why. Worth an explicit empty-state message in the picker; note it as
  DLC-13(d) evidence.
- **`required: true` on the pilot config row** blocks the run at the readiness gate for
  `wait_timeout_s` and then FAILS it if the sender is not connected. Operationally: **start the
  vision box (or the movie replay) BEFORE starting the run.** Same for the offline-movie workflow.
- **Hardware libs execute from the DB, not from the Pi checkout** (project memory,
  `hardware_lib_versions.source_code`, pinned per task-def via `hw_lib_versions`). A `git pull` on
  the Pi does **not** deploy a regenerated DLC lib. This is good news for DLC-02 — "one lib version
  per trained model" already has a working pinning mechanism and needs no new one.
- **The `ExtlinkDemo` egress-listener dependency (`132.77.73.125:5597`) is NOT inherited.** It
  belongs to that demo module's own outbound-probe config. Phase 35's module chooses its own
  liveness story; do not copy the prerequisite in by reflex.
- **`INC_TRIAL_COUNTER` is a silent no-op from a GUI-built task definition** (project memory,
  proven on run 562 — it sends `{}` and the orchestrator drops it on the missing `subject` key).
  DLC-08 requires the demo FDA be authored **in the browser**. If that FDA is ever expected to
  graduate a subject, it cannot. Design the DLC demo task so graduation is not on its path, or fix
  the counter first — decide deliberately.
- **Which Pi stack backs the rig checkpoint is still open** (Phase 34's P2). The wire module is
  byte-identical across `pi-mirror` and `mics_core`, but the **ingress module is not** — mics_core
  adds one-clock timestamping. Confirm the target pilot's stack before interpreting any timing
  observation.

---

# A real DLC 2.2.3 environment — `DEEPLABCUT223` (inspected 2026-08-30)

Conda list supplied by the user, who then clarified: **"not necessarily going to run it from that
particular env — just wanted to share."** So treat this as a **worked example of the environment
class**, not as the committed target. It is still the best evidence available of what a real
DLC 2.2.3 box looks like, and every constraint below is stated so it survives a different env.

| Fact | Value | Why it matters |
|---|---|---|
| Python | **3.8.19** | Confirms the SDK's `>=3.8` floor. Rules out `deeplabcut-live` >= 1.1.0 (`>=3.10`). Fixes `time.sleep` granularity at **~15.6 ms** (SDK-14f). |
| deeplabcut | **2.2.3** | TensorFlow engine. `model_type="base"`, 2-D pose only. |
| tensorflow / keras | **2.7.0** | Inside `deeplabcut-live` 1.0.4's `>=2.7.0,<=2.10` pin — compatible. |
| numpy | **1.21.5** | `.item()` / `as_scalar` behaves as documented. |
| **pyzmq** | **22.3.0 — ALREADY INSTALLED** | SDK floor must be `pyzmq>=22`. See the warning below. |
| **msgpack** | **1.0.3 — ALREADY INSTALLED** | SDK floor `msgpack>=1.0`. Adds a 4th point to the wire version matrix (1.0.3 / 1.0.5 Pi / 1.2.1 dev host). |
| **msgpack-numpy** | **0.4.7.1 — INSTALLED** | ⚠ wire-corruption vector. See below. |
| opencv-python | 4.5.5.62 (+headless 4.10) | `cv2.VideoCapture` available for the movie workflow. |
| pandas / tables / h5py | 1.3.5 / 3.7.0 / 3.6.0 | The DLC `.h5` -> flat converter has its dependencies already. |
| **deeplabcut-live** | **NOT INSTALLED** | ⚠ blocking prerequisite. See below. |
| CUDA stack | cuda-version 12.6, cudnn 8.9.7, torch 1.13.1 | ⚠ mismatched with TF 2.7 — see below. |

## ⚠ 1. Installing the SDK must NOT upgrade pyzmq — in ANY env

Generalises beyond this box: Jupyter, IPython, Spyder and napari all depend on pyzmq, so a
scientific environment usually already has it. A dependency floor above what is installed turns
*"install our SDK"* into *"upgrade the researcher's notebook stack"*. This env makes the risk
concrete — `pyzmq 22.3.0` with `jupyter-client 7.1.2`, `ipykernel 6.8.0`, `notebook 6.4.8`,
`qtconsole 5.2.2`, `spyder-kernels 2.2.1` and `spyder 5.2.2` all sitting on it. Floors are therefore
`pyzmq>=22`, `msgpack>=1.0`. Where those packages already exist the install must be a **no-op for
dependencies**; in a fresh env, pip installing both is the correct outcome.

## ⚠ 2. `msgpack-numpy` can silently corrupt every frame

`msgpack_numpy.patch()` reassigns `msgpack.packb`, `unpackb`, `Packer` **and** `Unpacker` at module
level (verified in its source — binding the `Packer` class at import does not dodge it). If
anything in the researcher's process calls `patch()`, every `mics_link` frame becomes
numpy-extended, the Pi counts it `malformed`, and **nothing is visible from the sender**. It is
installed in this env unprompted, which is what makes it a realistic hazard rather than a
hypothetical — and the selfcheck defends against any msgpack anomaly, not just this package, so it
earns its place whichever env is used. Phase 34 now ships
`python -m mics_link.selfcheck` (frozen-golden-hex comparison, also run inside `connect()`) so a
patched environment fails loudly. **Run it first on this box before debugging anything else.**

## ⚠ 3. `deeplabcut-live` is not installed — and the current release cannot be

`deeplabcut-live 1.1.0` requires Python `>=3.10,<3.13`; this env is 3.8.19. **If a fresh env is
built on Python 3.10–3.12 instead, `deeplabcut-live 1.1.0` becomes available and this whole section
is moot — decide which route before planning Phase 35.** For a 3.8/3.9 env the version to install
is **`deeplabcut-live==1.0.4`** (May 2023, `requires_python = ">=3.7.1,<3.11"`, classifiers include
3.8, pins `tensorflow>=2.7.0,<=2.10` — TF 2.7.0 fits).

Checked its dependency list against this env: `numpy>=1.20,<2.0` ✓ 1.21.5 · `pandas>=1.3,<2.0` ✓
1.3.5 · `tables>=3.6,<4.0` ✓ 3.7.0 · `opencv-python-headless>=4.5,<5.0` ✓ 4.10.0.84 ·
`dlclibrary>=0.0.2` ✓ 0.0.2 · `ruamel.yaml>=0.17.20,<0.18.0` ✓ 0.17.20 · `Pillow>=8.0.0` ✓ 9.0.0 ·
`py-cpuinfo>=5.0.0` ✓ 9.0.0 · `tqdm>=4.62.3,<5.0.0` ✓ 4.62.3. **The only package it would add is
`colorcet`.** So the install is close to risk-free — but do it in a **cloned env** first, because
this one holds a working DLC 2.2.3 training setup and is not worth gambling.

## ⚠ 4. Worth confirming: is inference on GPU or CPU?

TF 2.7 on Windows wants CUDA 11.2 / cuDNN 8.1 and looks for `cudart64_110.dll`; this env carries
conda `cuda-version 12.6` and `cudnn 8.9.7.29` (and `torch 1.13.1`, which wants 11.6/11.7). None of
those match TF 2.7, so **inference may be running on CPU**. Not a problem to fix here — but it sets
the achievable frame rate, which is the input to DLC-04's decimation budget and decides what "real
time" means when pacing a prerecorded movie. Measure the actual fps with
`dlclive.benchmark_videos` before sizing anything.

---

# Worked end-to-end example — coordinates AND likelihood

Deliberately **not** placed in Phase 34: `34-08-PLAN.md` Task 2 enforces a device-neutrality
guard that bans `deeplabcut`, `keypoint`, `bodypart`, `pose` and `\bdlc\b` anywhere under `sdk/`,
and a DLC example there would fail that test — correctly. Phase 34 gets the device-neutral
*shape* (see its `callback_sender.py` spec); the DLC flesh lives here.

## ⚠ Read first: why coordinates need a likelihood guard

`FiniteDeterministicAutomaton.__next__` evaluates transitions as
`if all(expr() for expr in expr_list)` — **completely unguarded** (verified 2026-08-30), and
`_build_transition_lambda` compares with a raw `operator.gt`. Therefore:

- **`stale_policy="return_none"` on a coordinate is a task-killer.** A stale read returns `None`,
  `None > 0.5` raises `TypeError`, and it propagates out of `__next__`. Never use it on anything
  a transition compares numerically.
- **`stale_policy="return_default"` with a numeric sentinel cannot be made safe either.** No single
  value is safe in both directions: `default=-1.0` makes `nose_x > 0.6` correctly False when
  tracking is lost, but makes `nose_x < 0.2` **fire falsely**. Whatever sentinel you pick, one
  comparison direction is wrong.
- **The only correct pattern: coordinates use `hold_last`, and every transition that reads a
  coordinate is ANDed with that keypoint's likelihood.** Likelihood keeps
  `return_default` + `0.0`, which IS safe in both directions because 0.0 is genuinely "no
  confidence". The FDA already supports this — condition groups evaluate `any(all(...))`.

This upgrades DLC-03's likelihood signal from "the cheap one to send" to **the guard that makes
coordinates usable at all**. It is not optional when x/y are declared.

## The hardware lib (Pi side — generated per DLC-02)

```python
"""Keypoints from a DeepLabCut model on the vision box. Coordinates are NORMALISED 0..1."""
from autopilot.hardware.external_hardware import ExternalHardware, command, event, signal


class DLCCam1(ExternalHardware):

    # Likelihood: return_default 0.0 is SAFE in both comparison directions — 0.0 really is
    # "no confidence". This is the guard every coordinate condition must be ANDed with.
    @signal(default=0.0, stale_after_ms=100, stale_policy="return_default")
    def nose_likelihood(self) -> float:
        pass

    # Coordinates: hold_last. NOT return_none (None crashes the FDA's raw comparison) and NOT
    # a numeric sentinel (no value is safe for both ">" and "<"). Safety comes from the AND.
    @signal(default=0.0, stale_after_ms=100, stale_policy="hold_last")
    def nose_x(self) -> float:
        pass

    @signal(default=0.0, stale_after_ms=100, stale_policy="hold_last")
    def nose_y(self) -> float:
        pass

    @signal(default=0.0, stale_after_ms=100, stale_policy="return_default")
    def left_paw_likelihood(self) -> float:
        pass

    @signal(default=0.0, stale_after_ms=100, stale_policy="hold_last")
    def left_paw_x(self) -> float:
        pass

    @signal(default=0.0, stale_after_ms=100, stale_policy="hold_last")
    def left_paw_y(self) -> float:
        pass

    @event(payload={"bodypart": str, "likelihood": float})
    def keypoint_lost(self):
        pass

    @command
    def reset_tracker(self) -> None:
        pass
```

**Why normalised 0..1 and not raw pixels:** `DLCLive(resize=0.5)` returns coordinates in the
*resized* frame. A transition authored as `nose_x > 300` silently changes meaning the day someone
adjusts `resize`, swaps the camera, or crops. Normalising in the adapter makes the FDA condition a
property of the arena, not of the current inference settings. Divide by the frame width/height the
adapter already has.

## The sender (vision box — Phase 34 SDK)

```python
import cv2, itertools
from dlclive import DLCLive, Processor
from mics_link import connect
from mics_link.values import as_scalar

BODYPARTS = ["nose", "left_paw"]          # order MUST match the model's pose_cfg.yaml
MOVE_EPS  = 0.002                          # deadband: ~2 px on a 1000 px frame

class MicsProcessor(Processor):
    def __init__(self, link, width, height):
        self.link, self.w, self.h = link, width, height
        self.last = {}

    def process(self, pose, **kwargs):     # DLC calls this per frame, on ITS thread
        for i, part in enumerate(BODYPARTS):
            x, y, p = (as_scalar(v) for v in pose[i])
            self.link.send_signal(part + "_likelihood", p)
            nx, ny = x / self.w, y / self.h
            prev = self.last.get(part)
            if prev is None or abs(nx - prev[0]) > MOVE_EPS or abs(ny - prev[1]) > MOVE_EPS:
                self.link.send_signal(part + "_x", nx)
                self.link.send_signal(part + "_y", ny)
                self.last[part] = (nx, ny)
        return pose                        # MUST return the pose

cap = cv2.VideoCapture("session_2026_08_30.mp4")   # or 0 for a live camera
w   = cap.get(cv2.CAP_PROP_FRAME_WIDTH)
h   = cap.get(cv2.CAP_PROP_FRAME_HEIGHT)
fps = cap.get(cv2.CAP_PROP_FPS)

with connect("132.77.72.28", 5599, "dlc_cam1") as link:

    @link.command("reset_tracker")         # the Pi can call back into you
    def _reset():
        return True

    live = DLCLive(MODEL_DIR, model_type="base", processor=MicsProcessor(link, w, h))
    ok, frame = cap.read()
    live.init_inference(frame)

    from mics_link.timing import Pacer     # a FILE plays as fast as the model chews it
    pacer = Pacer("realtime"); pacer.start()
    for i in itertools.count(1):
        ok, frame = cap.read()
        if not ok:
            break
        pacer.wait_until(i / fps)          # drop this line for a live camera
        live.get_pose(frame)

    live.close()
    print(link.stats.snapshot())           # sent / dropped — never silent
```

## The transition you then author in the browser

With the config row in place, the editor's picker offers a `dlc_cam1 signals` group. The safe
shape is always a **group of two**:

```
nose_likelihood  >  0.9        AND        nose_x  >  0.6
```

Tracking lost -> likelihood goes stale -> `return_default` 0.0 -> the AND is False -> `nose_x`'s
held-last value is never consulted. That is DLC-05's occlusion safety extended to coordinates.

## Message budget with x/y (DLC-04)

The wire carries **one scalar per `SIG`** — there is no batched frame. Against the ~60 msg/s
envelope Phase 18 proved:

| Declared | Rate | vs envelope |
|---|---|---|
| 8 bodyparts, likelihood only, 30 fps | 240 msg/s | 4x over |
| 8 bodyparts x (x, y, likelihood), 30 fps | **720 msg/s** | **12x over** |
| 2 bodyparts x 3, 30 fps | 180 msg/s | 3x over |
| **2 bodyparts x 3, 10 fps (decimated)** | **60 msg/s** | **at envelope** |
| 2 bodyparts x 3, 10 fps + deadband | < 60 msg/s | under |

So coordinates are affordable — the constraint is not "likelihood only", it is **declare only the
bodyparts you will actually gate on, and decimate**. The deadband above helps most for x/y
precisely because coordinates jitter every frame while likelihood often does not. Remember each
accepted `SIG` also emits one CONTINUOUS ES event, so these numbers are the ES load too.


---

# ⚠⚠ SUPERSEDING CORRECTION — 2026-08-31

**Everything above that rests on "the lab runs DeepLabCut 2.2.3 / TensorFlow / Python 3.8" is
WRONG for the model Phase 35 will actually integrate.** The 2.2.3 material is retained because
`DEEPLABCUT223` still exists on the box and its hazards (msgpack-numpy, pyzmq 22) are real for
*that* env — but it is NOT the target. Read this section first; where it conflicts with anything
above, this wins.

## The model Phase 35 targets

`C:\Users\YizharGPU12\Desktop\Gili\MultiMice-Gili-2026-06-21` (user-supplied listing, 2026-08-31):
`config.yaml`, `dlc-models/`, **`dlc-models-pytorch/`**, **`evaluation-results-pytorch/`**,
`labeled-data/`, `training-datasets/`, `videos/`. **No `exported-models/`.**

`dlc-models-pytorch/` and `evaluation-results-pytorch/` only exist for the **PyTorch engine**, so
this project was trained by the `DEEPLABCUT` env, not `DEEPLABCUT223`. The name (`MultiMice`)
indicates a **multi-animal** project.

## There are TWO DLC envs on that box — the earlier inspection profiled the wrong one

| | `DEEPLABCUT223` (inspected 2026-08-30) | **`DEEPLABCUT` (inspected 2026-08-31 — THE TARGET)** |
|---|---|---|
| Python | 3.8.19 | **3.12.13** |
| deeplabcut | 2.2.3 | **3.0.0** |
| engine | TensorFlow 2.7.0 | **PyTorch 2.5.1 (`py3.12_cuda11.8_cudnn9`)** |
| GPU | CUDA 12.6 vs TF 2.7 -> likely CPU-only | torch cu118 + nvidia cu118 runtime -> **real GPU** |
| numpy | 1.21.5 | 1.26.4 |
| pyzmq | 22.3.0 | **27.1.0** |
| msgpack | 1.0.3 | **1.2.1** |
| msgpack-numpy | **0.4.7.1 INSTALLED (hazard)** | **absent** |
| opencv | 4.5.5 / headless 4.10 | 4.11.0.86 (+headless) |
| pandas / tables | 1.3.5 / 3.7.0 | 2.3.3 / 3.11.1 |
| deeplabcut-live | not installed | **not installed** |
| also present | jupyter/spyder stack on pyzmq | napari 0.6.6 + napari-deeplabcut, PySide6 6.11.1, timm 1.0.27, dlclibrary 0.0.12 |

## What this changes

1. **`model_type="pytorch"`, not `"base"`.** Legal values (verified in `dlclive.py` docstring):
   PyTorch engine -> `["pytorch"]`; TensorFlow engine -> `["base", "tensorrt", "lite"]`.
2. **`deeplabcut-live 1.1.0` IS installable** — `requires_python = ">=3.10,<3.13"` and the env is
   3.12.13. The whole "you are stuck on 1.0.4" analysis above is VOID for this env.
   Install line: `pip install "deeplabcut-live[pytorch]"`.
   Dependency check against this env (PyPI metadata, verified 2026-08-31): `numpy<2,>=1.20` ✓1.26.4
   · `pandas!=1.5.0,>=1.0.1` ✓2.3.3 · `tables>=3.8` ✓3.11.1 · `opencv-python-headless>=4.5` ✓4.11 ·
   `scipy>=1.9` ✓1.17.1 · `einops>=0.6.1` ✓0.8.2 · `timm>=1.0.7` ✓1.0.27 · `dlclibrary>=0.0.6`
   ✓0.0.12 · `ruamel.yaml>=0.17.20` ✓0.19.1 · `Pillow` ✓ · `py-cpuinfo` ✓9.0.0 · `tqdm` ✓ ·
   `[pytorch]` extra: `torch>=2.0.0` ✓2.5.1, `torchvision>=0.15` ✓0.20.1.
   **The only package it adds is `colorcet`.** Still install into a CLONED env — this one holds a
   working DLC 3.0 training setup.
3. **`model_path` for pytorch is the `.pt` FILE** produced by `deeplabcut.export_model(...)`, NOT a
   directory and NOT the project dir (README, verified 2026-08-31). The project has **no
   `exported-models/`**, so **export is a prerequisite step in the runbook**, not a design question.
   Known upstream friction: DeepLabCut-live issue #137 / image.sc — a DLC 3.0 export emits a single
   `.pt` and DLC-Live can still complain about a missing pose_cfg. **Budget for this being the
   first real obstacle**; it is the DLC 3.0 analogue of the 2.2.3 `pose_cfg.yaml was not found`
   trap, not a different problem.
4. **Multi-animal is a ONE-FLAG problem, not a redesign.** README, verbatim: *"As multi-animal
   models can be used with PyTorch, the shape of the `pose` array given to the processor may be
   `(num_individuals, num_keypoints, 3)`. Just call `DLCLive(..., single_animal=True)` and it will
   work."* So v1 sets `single_animal=True` and receives `(n_bodyparts, 3)`.
   **The `assert pose.ndim == 2` guard recommended above is still right, but its rationale is
   inverted**: it no longer means "3-D is impossible with this lab's models" (it is entirely
   possible) — it means "the adapter requires `single_animal=True` and refuses loudly if someone
   turns it off". The error message must say that, not blame the engine.
5. **The SDK install is a dependency no-op here** — `pyzmq 27.1.0` and `msgpack 1.2.1` both exceed
   the `>=22` / `>=1.0` floors. SDK-14's "no upgrade proposed" is satisfied by construction.
6. **`msgpack-numpy` is NOT in this env**, so the silent wire-corruption vector is absent for the
   target. `python -m mics_link.selfcheck` stays in the runbook anyway — it is the only thing that
   makes that class of failure visible, and `DEEPLABCUT223` on the same box still carries it.
7. **GPU inference is real**, unlike the 223 env's mismatched stack. That RAISES achievable fps,
   which makes DLC-04's decimation MORE load-bearing, not less. Measure real fps before sizing.
8. **The generator's bodypart source changes.** For a DLC 3.0 multi-animal project it is
   `config.yaml`'s `multianimalbodyparts` (+ `individuals`), not a TF `pose_cfg.yaml`'s
   `all_joints_names`. The generator must record which engine/format a lib version came from.
   **`config.yaml` has been requested from the user and is not yet in hand** — it is an INPUT to
   the generator, not a design blocker.

## User decisions, 2026-08-31 session (add to the four already recorded at the top of this file)

5. **The deliverable is a GENERIC path, not a Gili-specific one.** *"I only wish to test the dlc
   connection with the pi and have this end result of a generic way for all lab members to link
   their model to the pi."* Multi-animal identity is explicitly NOT wanted in v1 — *"so I don't
   care. but some models are multianimal yes"* -> `single_animal=True`, refuse 3-D loudly, and
   leave per-individual expansion as a named, non-blocking extension.
6. **First proof = an FDA transition, not just signals arriving.** *"a model notifying a certain
   x y and a high likelihood should fire a transition."* So the coordinates-ANDed-with-likelihood
   pattern (DLC-03(c)) is exercised in the FIRST rig checkpoint, not deferred.
7. **Camera is explicitly a non-blocker.** Prerecorded video from the project's `videos/` dir is
   the v1 input; live camera is a later, non-blocking step. Confirms decision 2.

## Phase 34 gaps Phase 35 inherits (from `34-HARDWARE-VALIDATION.md`, runs 582/583/584)

- **Observation B — SDK-05 heartbeat/liveness is UNPROVEN on hardware.** Hardware lib 177 v2
  hardcodes `liveness_hook -> True`, so `demo.alive` would read true with the sender switched off.
  **DLC-06 ("liveness and tracking-loss are distinct and both gateable") cannot be satisfied until
  this is fixed** — a v3 of the lib with the override removed. Note the override's own docstring
  says the default path "reported not-alive while `on_recv` was demonstrably stamping
  `_last_msg_ts_ms`", so removing it may resurface a real bug. **This is on Phase 35's critical
  path and needs its own plan step.**
- **Observation D — SDK-07 reconnect is NOT EXERCISED on hardware**, and `seq` is not in the ES
  payload so it is not verifiable there. Cheaper equivalent found: `.213` binds 5599 only for the
  duration of a run, so stop-run -> start-new-run exercises the reconnect FSM identically without
  touching the pilot service.
- Observation C (soak) PASSED at 60Hz/30s; Observation A (transition fires) PASSED on runs 582/583.
