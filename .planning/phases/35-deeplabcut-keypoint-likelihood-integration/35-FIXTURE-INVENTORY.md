# Phase 35 Plan 06 — DLC Fixture Inventory

**Date:** 2026-08-31
**Status:** LIVE — every row below exists in the shared database, created entirely through
existing endpoints, on a NEW toolkit that leaves every real task definition's dispatch
untouched (T-35-27).

**PROVISIONAL notice, read first:** the uploaded lib's row order (`POSE_ORDER`) is
`config-declared-UNVERIFIED` (D-42). Plan 35-07's `--probe-pose` run against the real model is
the authority on whether `single_animal=True` actually returns the 22 unique bodyparts
(including `LED_on`/`LED_off`) in this order. If the probe disagrees, the lib and map MUST be
regenerated with `--pose-order`/`--pose-order-file` and re-uploaded (a new version on hardware
lib 243, or a new lib) before any rig observation built on it means anything.

---

## 1. Fixture inventory (created by this plan)

| Entity | id | Notes |
|---|---|---|
| Hardware lib | 243 | `dlc_cam1` / `dlc_cam1_lib.py`, `kind=hardware`, `active_version_id=184`, `active_state=beta` |
| Hardware lib version | 184 | version_number 1 of lib 243; `sha256`/`LIB_SHA256` `184496c8b5b54ca4a0d7623049d1a2de5c47539d3007bd58ea728e745067840a` |
| Hardware module | 73 | `dlc_cam1`, `hardware_lib_id=243`, `class_name=DlcCam1` |
| Toolkit | 157 | `dlc_demo`, backend-authored, cloned from toolkit 100's shape (`states=[]`, `locked_state_source=null`, no flags/params_schema); `hardware_module_ids=[73, 24]` — 24 (`COMPUTE`) was auto-attached by `attach_compute_defaults` (every backend-authored toolkit gets it; not requested by this plan, not removable via the create endpoint, and harmless — pilot 3 already carries a `COMPUTE` config row, id 32) |
| `pilot_hardware_config` row | 41 | pilot 3, name `dlc_cam1`: `{"class_name":"DlcCam1","role":"router_bind","listen_port":5601,"host":"132.77.73.125","source_id":"dlc_cam1","stale_ms":3000,"required":false,"wait_timeout_s":30}` |
| Task definition | 626 | `dlc_demo-26dcf910`, toolkit_id 157, `hw_lib_versions={"45":41,"243":184}` (45 = auto-attached Compute Ops, 243 = the pinned DLC lib) |

**Toolkit-hardware-lib link (not a new row type, recorded for teardown):** toolkit 157 links
hardware libs 45 (`Compute Ops`, auto-attached) and 243 (`dlc_cam1`, this plan).

**Toolkit 100 is UNCHANGED.** Its linked-lib id set was `{7, 8, 9, 10, 11, 45, 177}` before this
plan ran and is `{7, 8, 9, 10, 11, 45, 177}` after (`GET /api/toolkits/100/hardware-libs`,
checked both before Task 1 and again after Task 2 completed) — the DLC lib was never linked
there, per T-35-27.

---

## 2. Generation record (Task 1, step 1)

- **Config source used:** `dlc_link/tests/fixtures/dlc3_multianimal_config.yaml`, the
  transcription plan 35-03 committed. **This is NOT the real project file** —
  `C:\Users\YizharGPU12\Desktop\Gili\MultiMice-Gili-2026-06-21\config.yaml` is on the Windows
  vision box and is not reachable from this dev host (confirmed this session: no SMB mount, no
  UNC path resolves). The recorded `CONFIG_SHA256`
  (`d4176a8e9c58154cc9885899f2829ef58ece1ef6047533bb5a39eccea0662843`) is the **transcription's**
  hash, not the real file's. The transcription is a verbatim key table transcribed from
  `35-CONTEXT.md`'s "The actual model — config.yaml READ 2026-08-31" section, per D-10's
  documented escape hatch — it is not `from_explicit_list` degraded provenance (`--config` was
  passed, so `source_format` records `'config.yaml'`, not `'explicit-list'`).
- **Command:**
  ```
  PYTHONPATH=dlc_link/src python3 -m dlc_link.generate_cli \
    --config dlc_link/tests/fixtures/dlc3_multianimal_config.yaml \
    --bodyparts LED_on,LED_off --coords LED_on \
    --source-id dlc_cam1 --stale-after-ms 200 --liveness-hook clock-consistent \
    --out-dir .planning/phases/35-deeplabcut-keypoint-likelihood-integration/fixtures \
    --allow-signals 6
  ```
- **Bodyparts declared:** `LED_on` (coordinates enabled), `LED_off` (likelihood only) — both
  `uniquebodyparts` (class `unique`), per D-38. **No** `NW`/`NE`/`SE`/`SW`, no multianimal
  bodypart.
- **Signals emitted (exactly 4):** `led_on_likelihood`, `led_on_x`, `led_on_y`,
  `led_off_likelihood`. At the decimator's 10 Hz per-signal cap: 4 × 10 Hz = 40 msg/s, inside
  the proven ~60 msg/s envelope (D-22).
- **Pose order:** generated WITHOUT `--pose-order`/`--pose-order-file`.
  `POSE_ORDER_SOURCE = 'config-declared-UNVERIFIED'`. `POSE_ORDER` is the config's declared
  order (10 multianimal parts, then 22 unique parts — `LED_off` at index 14, `LED_on` at index
  15). **This lib is PROVISIONAL on plan 35-07's D-42 probe** — see the notice at the top of
  this document.
- **Files kept for byte-comparison** (the exact bytes uploaded):
  `.planning/phases/35-deeplabcut-keypoint-likelihood-integration/fixtures/dlc_cam1_lib.py`
  (sha256 `184496c8b5b54ca4a0d7623049d1a2de5c47539d3007bd58ea728e745067840a`) and
  `dlc_cam1_signals.py`. Verified byte-identical to the uploaded lib's stored
  `active_version` source (compared this session).

---

## 3. `dlc.alive` is pure inbound liveness — the five substrate citations, verified live

The generated lib source contains **zero** occurrences of `self.send(`, `_egress_probe`,
`def on_run_start`, `def on_run_stop` (grepped against the API-stored `source_code` for version
184, this session — matches the `_validate_rendered_lib` gate that already ran at generation
time). Because a lib that enqueues nothing can never flip `_egress_failed` True,
`recompute_alive`'s conjunction collapses to inbound liveness alone for this module. The five
citations below were read directly from `/home/ido/mics_core/autopilot/autopilot/hardware/`
this session (read-only):

1. **`external_hardware_binding.py:141`** — `recompute_alive`:
   `new_value = liveness_alive and not owner._egress_failed`. `alive` IS a conjunction.
2. **`external_hardware_binding.py:106-112`** (`bind_egress`) — `EgressWorker` is ALWAYS
   constructed for every module (`send_fn=lambda fn: fn()`), regardless of whether the lib ever
   enqueues anything. No config key gates this construction.
3. **`external_hardware.py:186-188`** (`ExternalHardware.send`) — the ONLY enqueue path
   (`self._egress.enqueue(item)`). The substrate itself never calls it; only a lib's own code
   can. The generated DLC lib has no such call.
4. **`external_hardware.py:143`** — `self._egress_failed = False` at construction. Since
   nothing is ever enqueued for this lib, `_on_egress_alive_change`
   (`external_hardware_binding.py:131-133`, the only writer of `_egress_failed`) is never
   invoked, so the value can never leave `False`.
5. **`external_hardware.py:118`** — `self.host = kwargs.get("host")`, stored and read by
   nothing in `external_hardware_binding.py` or `external_hardware_runtime.py` (grepped this
   session: zero matches for `host` in either file). `external_hardware_wire.py`'s
   `socket_plan` reads `host` ONLY for the `sub_connect` role (lines 198-200); a `router_bind`
   module (this fixture's role) binds `tcp://0.0.0.0:<listen_port>` (line 213) and never
   touches `host` at all.

**Posture in words:** `dlc_cam1.alive` reflects inbound liveness only, **because the generated
lib enqueues no egress item** — not because of anything in its `pilot_hardware_config` row. The
egress probe that WOULD drag `alive` false on an unrelated outbound failure (as it does for the
standing `ExtlinkDemo`/lib 177 fixture, which hardcodes its own probe against `.125:5597`) is
lib-source behaviour that no config key turns on or off. `host` is carried in this fixture's
config row purely for shape-parity with row 33 (`ExtlinkDemo`'s own config) and for a future
lib that DOES add a probe — it is unused by this module today.
`egress_fail_threshold` was **omitted** from the config row (confirmed: `GET
/api/pilots/3/hardware-config` shows no such key on the `dlc_cam1` row) as **tidiness, not the
safety mechanism** — it is inert for a lib that never enqueues (citation 3-4 above are the
actual guarantee), and the guarantee is generator-level (`_validate_rendered_lib`'s
`_NO_EGRESS_MARKERS` gate, plan 35-03), re-asserted here against the stored source rather than
trusted from the generator alone.

All five readings held. No egress dependency was found.

---

## 4. Task 1 automated verification (run live, this session)

```
$ curl .../api/pilots/3/hardware-config → dlc_cam1 row: source_id=dlc_cam1, role=router_bind,
  listen_port=5601, required=false, stale_ms=3000, no egress_fail_threshold key
  → "pilot 3 config row ok, no egress key"
$ router_bind ports on pilot 3: {5599 (ExtlinkDemo/"demo"), 5601 (dlc_cam1)} — no collision
$ source_ids on pilot 3 with a non-null value: {"demo", "dlc_cam1"} — no collision
  (the plan's literal verify snippet naively compares len(sids)==len(set(sids)) over EVERY
  row including the many rows with no source_id key at all, which collapse to a shared `None`
  in the set and would always "fail" that literal script on this live system regardless of
  this plan's changes — a pre-existing quirk in the verify script's own wording, not a real
  collision. The real invariant — no two NON-NULL source_ids collide — holds, checked by hand
  above.)
$ curl .../api/hardware-modules → module "dlc_cam1": hardware_lib_id=243, class_name=DlcCam1
$ curl .../api/hardware-libs/243 → source contains none of self.send(/_egress_probe/
  on_run_start/on_run_stop → "dlc lib has no egress path: alive is inbound-only"
$ curl .../api/task-definitions/626 → fda_json contains zero 'dlc_cam1.' and zero
  'INC_TRIAL_COUNTER' substrings
$ curl .../api/toolkits/100/hardware-libs → lib id set {7,8,9,10,11,45,177}, unchanged
```

**Deviation (Rule 1 — self-defeating description text):** the task definition's first-draft
`description` field literally contained the substring `"INC_TRIAL_COUNTER"` (stating, in
prose, that the file does NOT use it) — which trips the acceptance criterion's own substring
grep, exactly the same class of self-referential bug plan 35-03 hit with `@command` in a
comment. Reworded to "no trial-graduation special action" (same meaning, no longer matching).
Fixed via `PUT /api/task-definitions/626` before any other Task 2 work; the fda_json's
structural content (states/transitions/toolkit) was never wrong, only the prose.

---

## 5. Task 2 — the picker's data path, proven before a browser opens

**`GET /api/toolkits/by-name/dlc_demo`** (the exact call `TaskEditor.tsx:176-183` makes) —
`extlink_signals` block, recorded verbatim:

```json
[
  {
    "module_name": "dlc_cam1",
    "source_ids": ["dlc_cam1"],
    "signals": [
      {"name": "led_off_likelihood", "dtype": "float"},
      {"name": "led_on_likelihood", "dtype": "float"},
      {"name": "led_on_x", "dtype": "float"},
      {"name": "led_on_y", "dtype": "float"}
    ],
    "keys": [
      "dlc_cam1.alive",
      "dlc_cam1.led_off_likelihood",
      "dlc_cam1.led_on_likelihood",
      "dlc_cam1.led_on_x",
      "dlc_cam1.led_on_y"
    ],
    "conflict": false,
    "by_pilot": [
      {"pilot_id": 3, "pilot_name": "RecordingBox", "source_id": "dlc_cam1",
       "keys": ["dlc_cam1.alive", "dlc_cam1.led_off_likelihood", "dlc_cam1.led_on_likelihood",
                "dlc_cam1.led_on_x", "dlc_cam1.led_on_y"]}
    ]
  }
]
```

This is what `ConditionBuilder.tsx`/`ArgInput.tsx` render into the operand picker via
`buildViewOptions(toolkit.extlink_signals)`. All five keys are present, pilot-3 provenance is
attached, and `conflict` is `false`.

**D-36's ordering constraint, demonstrated against the LIVE system** (read-only computation,
no write; run inside the `mics_api` container so `derive_extlink_keys`'s real `sqlalchemy`
import resolves, no stub, no vendored logic):

```
config WITH source_id="dlc_cam1"    -> ['dlc_cam1.alive', 'dlc_cam1.led_off_likelihood',
                                         'dlc_cam1.led_on_likelihood', 'dlc_cam1.led_on_x',
                                         'dlc_cam1.led_on_y']
config WITHOUT the source_id key    -> []
```

Confirms in writing, against the real fetched config and the real function, that a researcher
who uploads a lib and module but skips the `pilot_hardware_config` row gets a **silently empty
picker with no error** — exactly D-36's finding.

**Save-gate rejection, exercised for THIS module** — `PUT` of task definition 626 with an added
transition `wait -> armed` on `{"view": "dlc_cam1.made_up_signal"} > 0.5`:

```
HTTP 422
{"detail": {"errors": ["transitions[1].condition_tree.left: references unknown variable/flag
  'dlc_cam1.made_up_signal'"]}}
```

The definition was then restored via a second `PUT` with the exact pre-test `fda_json`, and a
subsequent `GET` confirmed the restored `fda_json` is Python-equality-identical to the
pre-test capture (captured to a scratch file before the test, diffed after).

**React bundle freshness** (D-08 stale-bundle hazard, ruled out without a rebuild):
`web_ui/static/react/` is gitignored build output and does not exist in this worktree
checkout, so a direct hash comparison against a fresh `npm run build` was not performed here
(this plan does not install `node_modules`, per the package-manager-install exclusion in the
deviation rules — installing `node_modules` fresh is not this plan's job and was not
attempted). Instead: (1) `git log -1 -- web_ui/react-src/src` shows commit `3a41458` ("feat
(18-14): wire extlink signals into condition builder", 2026-08-09) is the LAST commit touching
any file under `web_ui/react-src/src` — nothing has changed there since, and nothing in this
plan touches it either (`git status --porcelain web_ui/react-src/src/` is empty); (2) the
LIVE `mics_web_ui` container's served bundle was grepped directly:
`docker exec mics_web_ui grep -rl extlink_signals /app/static/react/` finds it in
`TaskEditor-BQgUsRGT.js` — the feature the picker needs is demonstrably present in the
currently-served bundle, not merely in source. The stale-bundle hazard is therefore ruled out
by content, not by timestamp (the image's `Created` timestamp of 08:22:33 vs. the commit's
08:23:11 is 38 seconds apart in the "wrong" direction, which would be a false-positive staleness
signal by naive timestamp diffing alone — this is why the grep-for-content check, not a
timestamp comparison, is the check actually relied on here).

`git status --porcelain api/ web_ui/react-src/src/` — empty, confirmed after Task 2.

---

## 6. Deliberately absent

**The gated transition (`wait -> armed` on `dlc_cam1.led_on_likelihood`/`led_on_x`/`led_on_y`,
and `armed -> fired` closing the loop) is deliberately NOT in task definition 626.** Only the
unconditional `fired -> wait` transition ships here, exactly mirroring task definition 434's
precedent (plan 18-15) and for the identical reason: DLC-08 requires the transition be authored
**entirely in the browser**, and the first real human click through the extlink picker happens
in **plan 35-07**, nowhere else. Authoring it here via the API would prove nothing about the
picker and would burn that phase's only chance to exercise it.

The threshold for that transition is **also deliberately not chosen here** — D-41 requires it
be read off the MEASURED likelihood distribution of `led_on_likelihood`/`led_off_likelihood` on
a real video (this project's `pcutoff: 0.01` is two orders of magnitude below DeepLabCut's 0.6
default, so no threshold picked a priori would be trustworthy). Plan 35-07 measures it.

---

## 7. Teardown (reverse dependency order)

| Step | Action | Endpoint / method |
|---|---|---|
| 1 | Delete task definition 626 | `DELETE /api/task-definitions/626` |
| 2 | Unlink DLC lib from toolkit 157 | `DELETE /api/toolkits/157/hardware-libs/243` |
| 3 | Delete pilot 3's `dlc_cam1` config row | `DELETE /api/pilots/3/hardware-config/dlc_cam1` |
| 4 | Delete hardware module 73 (`dlc_cam1`) | **No DELETE endpoint exists for hardware_modules.** Direct SQL only: `DELETE FROM hardware_modules WHERE id = 73;` — same gap already recorded for the `ExtlinkDemo` fixture in `18-HARDWARE-VALIDATION.md` §3 ("teardown remains a separate, still-open user decision"), not new to this plan. |
| 5 | Delete hardware lib 243 (`dlc_cam1`) and its version 184 | `DELETE /api/hardware-libs/243` (works once step 4 is done; the endpoint refuses while any toolkit link remains, which step 2 already cleared) |
| 6 | Delete toolkit 157 (`dlc_demo`) | **No DELETE endpoint exists for toolkits.** Direct SQL only, after step 2: `DELETE FROM toolkit_hardware_libs WHERE toolkit_id = 157; DELETE FROM task_toolkits WHERE id = 157;` |

Step 4's and step 6's SQL are recorded for completeness but were **not executed** — this
fixture is meant to stand through plans 35-07/35-08/35-09, per this plan's objective.

---

## 8. What plan 35-07 measures / decides, not this plan

- The `--probe-pose` D-42 result (does `single_animal=True` return the 22 unique bodyparts, and
  in what order). If it disagrees with `POSE_ORDER`/`POSE_ORDER_SOURCE` above, regenerate with
  `--pose-order`/`--pose-order-file` and re-upload as a new version.
- The measured likelihood distribution of `led_on_likelihood`/`led_off_likelihood`, which sets
  the demo transition's threshold (D-41).
- The FIRST human click through the FDA editor's picker for `dlc_cam1.*`, authoring the gated
  `wait -> armed -> fired` transitions this plan deliberately left out.
