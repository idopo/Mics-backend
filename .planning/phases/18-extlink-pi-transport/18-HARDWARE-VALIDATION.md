# Phase 18 — Hardware Validation Log (consolidated rig checkpoint, plan 18-12)

**Date opened:** 2026-08-09
**Status:** Task 1/2 preparation complete (agent-side). Checkpoint (Task 3) NOT YET RUN by the
user. RESULT columns below are placeholders until the checkpoint executes.
**Scope of this document:** what is PROVEN on hardware vs. what remains UNPROVEN, the exact
deploy manifest, the exact commands for every manual-only row of `18-VALIDATION.md`, and the
exact system state (ids) this checkpoint depends on.

Modelled on `.planning/phases/24-trigger-assignment-action-lists/24-HARDWARE-VALIDATION.md`.

---

## 0. Registered fixture state (agent-prepared, before the checkpoint)

All ids below were created via the running `api` container's HTTP surface — **no repository
file was modified to create them**, per this plan's Task 1 scope. Full backend suite green
(435 passed, 1 skipped) after registration; `GET /api/device-leases` returns `[]`.

| Entity | id | Notes |
|---|---|---|
| Pilot (the rig) | 1 | `pilot_raspberry_lior`, ip `132.77.72.28` |
| Real session used for preflight checks | session 113 / pilot 1 | last real run: run 551, 2026-08-05 |
| Toolkit (shared with real task def 186) | 100 | `source_less_toolkit`, backend-authored |
| Toolkit's `hardware_module_ids` **before** this plan | `[1, 5, 6, 7, 8, 24]` | **restore to exactly this list at TEARDOWN** |
| Toolkit's `hardware_module_ids` **after** this plan | `[1, 5, 6, 7, 8, 24, 59, 60, 61]` | |
| Lib A — `extlink_demo_dealer.py` / `DemoDealer` | lib 162, good version 119 (only version) | `router_bind`, signals `left_paw_x` (return_default, 200ms) / `right_paw_x` (hold_last, 200ms), event `object_detected` |
| Lib B — `extlink_demo_control.py` / `DemoControl` | lib 163, good version **125** (v3), broken version **122** (v2), superseded good v1=120 | `role: "none"`, zero signals, `@command ping`, `liveness_hook` override, PLUS `on_run_start`/`on_run_stop`/`_egress_probe` (added after v1 — see deviation note below). `active_version_id` is currently **125** — both the toolkit link (`default_version_id=125`) and task-def 434's own `hw_lib_versions` pin (`"163": 125`) resolve to 125 (good) unless explicitly repinned (step 6b) |
| Lib C — `extlink_demo_sub.py` / `DemoSub` | lib 164, good version 121 (only version) | `sub_connect`, `@decoder decode` parses `extlink_smoke.py publish`'s JSON-header + float32-body frame pair, one signal `probe_value` |
| Module — Lib A | hardware_modules id **59**, name `ExtlinkDemoDealer` | |
| Module — Lib B | hardware_modules id **60**, name `ExtlinkDemoControl` | |
| Module — Lib C | hardware_modules id **61**, name `ExtlinkDemoSub` | |
| pilot_hardware_config — Lib A | id 18, name `ExtlinkDemoDealer` | `{"class_name":"DemoDealer","role":"router_bind","listen_port":5599,"source_id":"dlc_cam1","stale_ms":3000,"required":true,"wait_timeout_s":30,"egress_fail_threshold":3}` |
| pilot_hardware_config — Lib B | id 19, name `ExtlinkDemoControl` | `{"class_name":"DemoControl","role":"none","host":"132.77.73.125","source_id":"oe_ctl","stale_ms":3000,"required":true,"wait_timeout_s":30,"egress_fail_threshold":3}` — `host` doubles as the egress-demo probe target (fixed port 5597, hardcoded in the class as `_EGRESS_PORT`) |
| pilot_hardware_config — Lib C | id 20, name `ExtlinkDemoSub` | `{"class_name":"DemoSub","role":"sub_connect","host":"132.77.73.125","connect_port":5598,"source_id":"oe_demo","stale_ms":3000,"required":false,"wait_timeout_s":30,"egress_fail_threshold":3}` |
| `extlink_demo` task definition | **434**, `task_name` `extlink_demo-c8ecda5c` | toolkit 100; `hw_lib_versions` pinned `{"162":119,"163":125,"164":121, ...pre-existing toolkit libs}`; the two signal-gated transitions (`wait->armed`, `armed->fired`) are **deliberately absent** — step 1b authors them in the browser |
| Dev machine (runs `extlink_smoke.py`/`extlink_driver.py`/curl/`nc`) | `132.77.73.125` | = `TERMINALIP` in the Pi's own prefs; same host this checkpoint's prep ran from |

**Deviation (Rule 2 — missing critical functionality, found during Task 1 preparation): none of
the three demo libs as originally specified ever call `self.send()`.** `_extlink_commands` is
populated by the `@command` decorator but nothing in the currently-deployed code auto-dispatches
a command through egress, `extlink_demo_fda.json` deliberately carries no entry actions (plan
18-15's own design — not to be changed here), and there is no live "call a hardware method
on demand" endpoint anywhere in the app. Without an addition, EXTLINK-15's step 8
(egress-under-latency) would have literally nothing to observe on the rig. Fixed by adding a
self-contained `on_run_start`/`on_run_stop`/`_egress_probe` trio to `DemoControl` (uploaded as
lib 163's version 125, now the pinned "good" version everywhere v1/120 previously was): once per
run, a daemon thread enqueues one zero-arg egress callable per second for the run's duration,
each opening a plain TCP connection to `self.host:5597` and waiting up to 5s for a reply byte.
Idempotent across `LifecycleRunner`'s `on_run_start` retries (guarded by `_egress_thread is
None`), cleanly stopped in `on_run_stop`. See step 8 in the checklist below for exactly how to
make this probe fail fast (nothing listening — quick `alive` flip) vs fail slow (`nc -l 5597`
that never replies — queue actually builds before it drops).

**Lib B / broken-variant detail (EXTLINK-18 unhappy path, step 6b):** `PUT /api/hardware-libs/163`
uploaded the liveness-override-less `DemoControl` as version 122. Confirmed live:
`ast_metadata.extlink.DemoControl == {"signals": {}, "events": {}, "commands": {"ping": ...},
"decoder": null}` — **identical shape to the good version** except the class body itself. This is
the documented, intentional AST-extractor blind spot: it has no opinion about `liveness_hook`,
so upload never 422s on this. The construction-time `ValueError` only fires when the Pi actually
imports and instantiates the class, which is exactly what step 6b proves.

**Config validation live-proof (all three deliberate breakages), run against session 113 / pilot 1:**

| Breakage | `POST /preflight-validate` result | Restored result |
|---|---|---|
| Lib A `wait_timeout_s: null` | `extlink_config_invalid`: `"'wait_timeout_s' must be an int in [5, 600], got None"` | `{"ok": true, "issues": []}` |
| Lib B `host` dropped (role `none`) | `extlink_config_invalid`: `"role 'none' still requires 'host' (egress target / lease key)"` | `{"ok": true, "issues": []}` |
| Lib B config, neither `listen_port` nor `connect_port` (baseline, not a breakage) | clean — `{"ok": true, "issues": []}` | n/a — this IS the EXTLINK-18 live proof that no port is demanded |

**One fixture bug found and fixed during Task 1 (Rule 1 — bug in this plan's own authored
config, not the application):** the plan text's literal Lib C config omits `egress_fail_threshold`,
but `api/device_lease.py::validate_extlink_config` requires it unconditionally for every
extlink-shaped config regardless of role. First preflight run correctly caught this
(`extlink_config_invalid: 'egress_fail_threshold' must be a positive number, got None`) —
fixed by adding `"egress_fail_threshold": 3` to Lib C's `pilot_hardware_config` row (id 20,
shown above already corrected). Re-verified clean afterward. Not a defect in `device_lease.py`
itself — that unconditional requirement is intentional (EXTLINK-15's failure-threshold), the
plan's own literal example config for Lib C was simply incomplete.

**Pre-existing DB debris found, NOT this plan's fixtures, logged not fixed (see
`deferred-items.md`):** a leftover `DLC_CAM1` hardware_modules row (id 25, inert), ~25 duplicate
`oe_probe_extlink`/`weird_splat_signal` hardware_libs rows from `test_hardware_libs_extlink.py`'s
route-level tests running against the real dev DB, and task_definition 344 /
toolkit 118 (`Plan1813Extlink*`) that 18-13-SUMMARY claimed was deleted but was not. None collide
with this plan's own names/ids and none are attached to any pilot config or toolkit, so none can
affect this checkpoint or a real session.

---

## 1. Deploy manifest

Exact rsync file list, from `18-11-SUMMARY.md`'s "Next Phase Readiness" section (all paths
relative to the Pi's code root, `~/Apps/mice_interactive_home_cage/`):

```
autopilot/autopilot/tasks/mics_task.py
autopilot/autopilot/hardware/external_hardware.py
autopilot/autopilot/hardware/external_hardware_wire.py
autopilot/autopilot/hardware/external_hardware_runtime.py
autopilot/autopilot/hardware/external_hardware_ingress.py
autopilot/autopilot/hardware/external_hardware_binding.py
requirements.txt
autopilot/requirements.txt
```

`scripts/dev/extlink_smoke.py` is **NOT** in this list — it is a dev-machine-only tool, never
rsynced to the Pi (its own docstring says so twice).

**Never `rsync --delete`.** Sync only these eight files.

### msgpack pin

`msgpack==1.0.5` (resolved live against the rig's Python 3.7.3 venv by plan 18-04 — piwheels
armv7l cp37 wheel via `pip install "msgpack<1.1"`). Both `requirements.txt` and
`autopilot/requirements.txt` in the mirror carry this pin. Step 0 below re-verifies it importable
post-deploy.

### Pre-deploy verification (agent-performed, read-only SSH, before any file is written)

`md5sum` on the Pi vs the mirror, run 2026-08-09 immediately before this document was written:

| File | Pi md5 | Mirror md5 | Verdict |
|---|---|---|---|
| `autopilot/autopilot/tasks/mics_task.py` | `e227317365561dbaca20e9c079ba45fd` | `06c6b8621ea614e8e318cfe8ae0784fd` | **DIFFERS — expected**, this is Phase 18's own edit (18-11) awaiting deploy |
| `autopilot/autopilot/hardware/external_hardware.py` | *(file does not exist on the Pi)* | `766b6360817d9b7cb1ad5ecf0576ff22` | **NEW file — expected**, first deploy of the substrate |
| `autopilot/autopilot/hardware/external_hardware_wire.py` | *(does not exist)* | `76dd4f8dae27ca207720bd2980260928` | **NEW — expected** |
| `autopilot/autopilot/hardware/external_hardware_runtime.py` | *(does not exist)* | `cbc5ad480b56a96ebafa110f01230308` | **NEW — expected** |
| `autopilot/autopilot/hardware/external_hardware_ingress.py` | *(does not exist)* | `02131508390683ac12c35fdccb2ecb87` | **NEW — expected** |
| `autopilot/autopilot/hardware/external_hardware_binding.py` | *(does not exist)* | `009e2c607e665c91184086a8e8701eff` | **NEW — expected** |
| `requirements.txt` | `63c7e320a92614cec9904c49fc8e968e` | `1f35f93610fa58f0fa628e6d10cf6a09` | **DIFFERS — expected**, the msgpack pin |
| `autopilot/requirements.txt` | `f57ce31233019b9fdc91397569b3ca30` | `a7f7b10b42c778ecd00c0133001d559c` | **DIFFERS — expected**, same pin |

No pre-existing, unexplained drift found: every diff is exactly what this deploy is meant to
introduce. Clear to sync.

---

## 2. Manual-only checklist (USER-RUN on the rig) — commands and expected outputs

All fourteen numbered steps below are also written, in copy-paste order with no prose, to
`/home/ido/extlink_rig_commands.txt` for the user to run without retyping anything. This section
is the same content with the expected-output rationale attached.

RESULT column is filled in by Task 4 after the checkpoint runs.

| # | Step | RESULT |
|---|---|---|
| 0 | Deploy + restart + msgpack check | ⬜ PENDING |
| 1 | `router_bind` end-to-end | ⬜ PENDING |
| 1b | Author the gated transitions in the browser | ⬜ PENDING |
| 2 | `sub_connect` end-to-end | ⬜ PENDING |
| 3 | Stale policy + liveness split | ⬜ PENDING |
| 4 | Malformed input | ⬜ PENDING |
| 5 | Readiness gate, three exits | ⬜ PENDING |
| 6 | Control-only module, role none, no socket | ⬜ PENDING |
| 6b | Same module WITHOUT liveness override fails loudly | ⬜ PENDING |
| 7 | Lifecycle on all three teardown paths | ⬜ PENDING |
| 8 | Egress under real latency | ⬜ PENDING |
| 8b | Hand-driving + soak from the laptop | ⬜ PENDING |
| 9 | Lease from a genuine pilot disconnect | ⬜ PENDING |
| 10 | Pi test suite | ⬜ PENDING |
| 11 | TEARDOWN | ⬜ PENDING (**mandatory**) |

See `/home/ido/extlink_rig_commands.txt` for the exact commands. Each step's full rationale is in
`18-12-PLAN.md`'s `<how-to-verify>` block (Task 3) — this document exists so the ids are concrete,
not so the rationale is duplicated.

---

## 3. TEARDOWN (checkpoint step 11) — MANDATORY, exact reversing commands

`ExtlinkDemoControl` is registered `required: true` **on purpose** (to prove a control-only
module fully participates in the readiness gate). Left assigned to pilot 1 / toolkit 100, every
subsequent REAL session on this rig either preflight-fails or hangs the full `wait_timeout_s`
(30s) waiting for a demo device nobody is running — and there will be nothing pointing at the
cause weeks later. **This section may only be skipped if the user explicitly says the rig stays
in demo configuration — record that decision here if so, in bold, at the top of this section.**

```bash
export MICS_API_TOKEN="<same token used throughout>"

# 1. Delete the three demo pilot_hardware_config rows (name-keyed)
curl -s -X DELETE "http://localhost:8000/api/pilots/1/hardware-config/ExtlinkDemoDealer" -H "Authorization: Bearer $MICS_API_TOKEN"
curl -s -X DELETE "http://localhost:8000/api/pilots/1/hardware-config/ExtlinkDemoControl" -H "Authorization: Bearer $MICS_API_TOKEN"
curl -s -X DELETE "http://localhost:8000/api/pilots/1/hardware-config/ExtlinkDemoSub" -H "Authorization: Bearer $MICS_API_TOKEN"

# 2. Restore toolkit 100's hardware_module_ids to the EXACT pre-plan value (not [])
curl -s -X PATCH "http://localhost:8000/api/toolkits/100" -H "Authorization: Bearer $MICS_API_TOKEN" -H "Content-Type: application/json" \
  -d '{"hardware_module_ids":[1,5,6,7,8,24]}'

# 3. Confirm no lease is held
curl -s "http://localhost:8000/api/device-leases" -H "Authorization: Bearer $MICS_API_TOKEN"

# 4. Re-run preflight for a REAL session on this pilot -- the one output that actually proves
#    the rig is usable again
curl -s -X POST "http://localhost:8000/api/sessions/113/preflight-validate/1" -H "Authorization: Bearer $MICS_API_TOKEN"
```

Expected: step 1 all `{"deleted": true}`; step 2 returns `"hardware_module_ids": [1,5,6,7,8,24]`;
step 3 returns `[]`; step 4 returns `{"ok": true, "issues": []}`.

The demo hardware libs (162/163/164), their versions, the hardware_modules rows (59/60/61), and
the `extlink_demo` task definition (434) may all stay — they are inert unless assigned to a
toolkit's `hardware_module_ids` / a pilot's config, which teardown just removed.

---

## 4. Explicitly NOT an acceptance criterion

**Do not assert that a CONTINUOUS event exists in ES for `on_run_stop()` itself.**
`event_dispatcher.stop()` runs *before* `task.end()`/`release()` in `pilot.py`'s teardown, so that
event provably races a sender thread that may already have exited. Stop is verified by EFFECT —
device idle, lease released, log line present — never by an ES record.

---

## 5. Proven / Unproven (filled in by Task 4, after the checkpoint)

*Not yet run. Every row below is UNPROVEN until Task 4 records real checkpoint output.*

| Requirement | Behavior | Status |
|---|---|---|
| EXTLINK-01/02/05/11 | `router_bind` end-to-end + identity-mismatch drop | ⬜ UNPROVEN |
| EXTLINK-19 | Signal-gated transition authored in the browser picker | ⬜ UNPROVEN |
| EXTLINK-14 | `sub_connect` end-to-end via a live PUB + `@decoder` | ⬜ UNPROVEN |
| EXTLINK-06/07 | Stale policy split + liveness independent of staleness | ⬜ UNPROVEN |
| EXTLINK-08 | Malformed input dropped, no traceback | ⬜ UNPROVEN |
| EXTLINK-13 | Readiness gate, three exits | ⬜ UNPROVEN |
| EXTLINK-18 (happy) | Control-only module, no socket, participates in gate | ⬜ UNPROVEN |
| EXTLINK-18 (unhappy) | Same module without liveness override fails at construction | ⬜ UNPROVEN |
| EXTLINK-16 | Lifecycle hooks on all three teardown paths | ⬜ UNPROVEN |
| EXTLINK-15 | Egress under real latency, bounded queue, alive flips | ⬜ UNPROVEN |
| EXTLINK-20 | Hand driver + ~60Hz soak from a non-Pi machine | ⬜ UNPROVEN |
| EXTLINK-17 | Lease from a genuine pilot disconnect + force-release + `device_held` | ⬜ UNPROVEN |
| — | Pi test suite (standing gap since Phase 24) | ⬜ UNPROVEN |
| — | TEARDOWN — demo fixtures removed, real preflight clean | ⬜ UNPROVEN |

**Residual risk (restate regardless of outcome above):** Phase 18's lease safety net releases the
lease row and lets the run be marked errored, but does **not** command the foreign device to
stop. A crashed pilot can leave an external recorder running until a human notices. Phase 26
decides whether OpenEphys needs its own additional reconciliation.

---

*Phase: 18-extlink-pi-transport*
*Prepared: 2026-08-09 (Tasks 1-2). Checkpoint (Task 3) and results (Task 4) pending.*
