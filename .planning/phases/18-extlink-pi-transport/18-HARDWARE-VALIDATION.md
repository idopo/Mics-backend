# Phase 18 — Hardware Validation Log (consolidated rig checkpoint, plan 18-12)

**Date opened:** 2026-08-09
**Status:** Rewritten after a mid-flight scope decision — the fixture set was consolidated from
three demo libs to one. Task 1/2 preparation complete (agent-side, twice: once for the original
3-lib set, once revised for the 1-lib set). Checkpoint (Task 3) NOT YET RUN by the user. RESULT
columns below are placeholders until the checkpoint executes.
**Scope of this document:** what is PROVEN on hardware vs. what remains UNPROVEN, the exact
deploy manifest, the exact commands for every manual-only row of `18-VALIDATION.md`, and the
exact system state (ids) this checkpoint depends on.

Modelled on `.planning/phases/24-trigger-assignment-action-lists/24-HARDWARE-VALIDATION.md`.

---

## 0. Registered fixture state (revised — single consolidated demo lib)

**What changed and why:** the original preparation registered three demo libs
(`DemoDealer`/router_bind, `DemoControl`/role-none, `DemoSub`/sub_connect). The user reviewed the
FDA editor's lib picker, found it unusable at 60 entries, and traced the bulk of that to an
unrelated pre-existing bug: `api/tests/test_hardware_libs_extlink.py`'s two route-level tests
uploaded a lib each run and never deleted it, leaking 2 rows per `pytest` invocation against the
real dev DB (~25 suite runs across the phase → 50 orphaned rows, plus one leftover from 18-13's
own live verification). **The coordinator (not this agent) purged the 51 orphaned rows, fixed the
test leak (commit `84612af`, verified stable across two full-suite reruns), and — as a deliberate
additional scope decision, confirmed by the user after being told what it costs — collapsed this
plan's three demo fixtures into ONE.** This agent performed none of those DB/API changes; this
section (and `/home/ido/extlink_rig_commands.txt`) is rewritten to describe that resulting state
and to flag two consequences the user was not told about (see §0b).

All ids below were confirmed live via read-only queries against the running `api` container and
its DB, immediately before this rewrite. Full backend suite green (435 passed, 1 skipped);
`GET /api/device-leases` returns `[]`; preflight clean for sessions 113/110/107 on pilot 1.

| Entity | id | Notes |
|---|---|---|
| Pilot (the rig) | 1 | `pilot_raspberry_lior`, ip `132.77.72.28` |
| Real sessions used for preflight checks | 113 / 110 / 107, all pilot 1 | all three return `{"ok": true, "issues": []}` |
| Toolkit (shared with real task def 186) | 100 | `source_less_toolkit`, backend-authored |
| Toolkit's `hardware_module_ids` **before this plan's Task 1** | `[1, 5, 6, 7, 8, 24]` | **restore to exactly this list at TEARDOWN** |
| Toolkit's `hardware_module_ids` **now** | `[1, 5, 6, 7, 8, 24, 62]` | (was briefly `[..., 59, 60, 61]` under the 3-lib design; the coordinator repatched it to `62` after deleting 59/60/61) |
| The ONE demo lib — `extlink_demo.py` / `ExtlinkDemo` | lib **177**, version **132** (only version, state `beta`, not promoted stable) | `role: "router_bind"`. Two signals — `left_paw_x` (`return_default`, 200ms), `right_paw_x` (`hold_last`, 200ms) — one event `object_detected`, one `@command ping`, PLUS `on_run_start`/`on_run_stop`/`_egress_probe` (the egress-demo trio originally written for `DemoControl`, lifted in verbatim — see §0b for the bug this introduces) |
| Module | hardware_modules id **62**, name `ExtlinkDemo` | |
| pilot_hardware_config | id **21**, name `ExtlinkDemo` | `{"class_name":"ExtlinkDemo","role":"router_bind","listen_port":5599,"source_id":"demo","stale_ms":3000,"required":false,"wait_timeout_s":30,"egress_fail_threshold":3}` — **no `host` key** (see §0b) |
| `extlink_demo` task definition | **434**, `task_name` `extlink_demo-c8ecda5c` | toolkit 100. `hw_lib_versions` still carries stale dead keys `{"162":119,"163":125,"164":121}` from the deleted 3-lib set (harmless — those lib ids are unlinked from the toolkit, so `resolve_lib_version_id` never looks them up; lib 177 itself resolves via the "active" rung since it has no toolkit-default pin and no stable version). The two signal-gated transitions (`wait->armed`, `armed->fired`) are **still deliberately absent** — step 1b authors them in the browser, now against `demo.left_paw_x`/`demo.right_paw_x` |
| Dev machine (runs `extlink_smoke.py`/`extlink_driver.py`/curl) | `132.77.73.125` | = `TERMINALIP` in the Pi's own prefs |

**Extlink signal aggregation, confirmed live** (`GET /api/toolkits/100` → `extlink_signals`):
```json
[{
  "module_name": "ExtlinkDemo", "source_ids": ["demo"],
  "signals": [{"name": "left_paw_x", "dtype": "float"}, {"name": "right_paw_x", "dtype": "float"}],
  "keys": ["demo.alive", "demo.left_paw_x", "demo.right_paw_x"],
  "conflict": false,
  "by_pilot": [{"pilot_id": 1, "pilot_name": "pilot_raspberry_lior", "source_id": "demo",
                "keys": ["demo.alive", "demo.left_paw_x", "demo.right_paw_x"]}]
}]
```
This is what the FDA editor's picker should offer at step 1b: option group **`demo signals`**
(source_ids has length 1, so the group label is `${source_id} signals`, not the module name),
items `left_paw_x (float)`, `right_paw_x (float)`.

### 0a. Deliberate scope reduction (confirmed, user-approved) — do not re-litigate

The user was told and confirmed: collapsing to one `router_bind`-only lib leaves the following
**permanently UNPROVEN in this checkpoint session**, with no fixture left to exercise them:

- **`role: "none"` (control-only, no inbound socket) end-to-end on the real rig** (EXTLINK-18,
  happy path) — no `role: "none"` module exists anymore.
- **The SAME control-only lib WITHOUT its `liveness_hook` failing at construction** (EXTLINK-18,
  unhappy path / the liveness-override-mandatory rule) — same reason; there is also no broken
  lib version left to repin to (the old broken `DemoControl` v122 belonged to the now-deleted
  lib 163).
- **`sub_connect` end-to-end against a live PUB, `@decoder` translating a foreign frame**
  (EXTLINK-14's rig-only half) — no `sub_connect` module exists anymore.

These three rows are marked UNPROVEN in §5 with this reason, not silently dropped. The underlying
mechanisms remain agent-tested (unit-level, `-k role_none`/`-k control_only`/`-k role_selection`
in the Pi-mirror suite, per `18-VALIDATION.md`) — only the rig end-to-end proof is what's lost.

### 0b. Two ADDITIONAL consequences found by this agent, NOT part of the user's decision — flagged, not fixed

The user was told the cost was "role none and sub_connect become unproven." Reading the actual
consolidated fixture and the orchestrator/gate code that consumes it, two more rows are also now
blocked — for reasons that were not part of what the user was told, so they are flagged here
rather than silently absorbed into the same "accepted" bucket.

**1. `ExtlinkDemo`'s config carries `"required": false`, so the readiness-gate pre-state never
installs — EXTLINK-13 (readiness gate, all three exits) cannot be exercised at all.**
`_install_extlink_gate` (`mics_task.py`) is a true no-op whenever `gate_timeout_s(...)` returns 0,
which it does whenever `self._extlink_required` is empty — and that list is populated ONLY from
`required: true` configs (`mics_task.py:179-200`). With the sole remaining fixture at
`required: false`, `_extlink_required` is empty for both `extlink_demo` (434) and the real task
def 186, so `_wait_extlink_ready` is never installed on this pilot at all right now. `required:
false` was a reasonable, deliberate choice on its own (it stops a demo device from blocking a
real 30s wait when nobody's running the driver) — but it has this side effect, which was not
called out. **Not fixed here.** If the user wants EXTLINK-13 proven this session, config 21's
`required` needs to be flipped to `true` for the duration of that one test and back afterward —
a decision only they can make, since it reintroduces the exact blocking behavior `required: false`
was chosen to avoid.

**2. `ExtlinkDemo`'s config has no `"host"` key at all, which blocks TWO things, not one:**
- **EXTLINK-17 (device lease from a genuine pilot disconnect) cannot be exercised — at all, not
  just weakened.** `orchestrator_station.py::_acquire_device_leases` skips any `PREFS_HARDWARE`
  entry whose `cfg.get("host")` is falsy (`if not host: continue`) — by design, since the lease
  key IS the host and there is nothing to arbitrate without one. In the original 3-lib design,
  step 9's lease test was carried entirely by `DemoControl`'s `host: "132.77.73.125"` (role
  `none`), which is exactly the module the user's decision removed. Nothing in the surviving
  `router_bind` fixture declares a host (router_bind's transport doesn't need one), so **no
  lease will ever be acquired on this pilot for any of these fixtures**, full stop.
- **EXTLINK-15's egress-under-latency probe (step 8) is misdirected, not blocked, but will not
  do what the instructions say.** `_egress_probe` (lifted verbatim from `DemoControl` into
  `ExtlinkDemo`) does `socket.create_connection((self.host, 5597), ...)`. With no `host` key,
  `self.host` is `None` on the Pi. Verified directly: `socket.create_connection((None, 5597))`
  resolves `None` to the loopback address, so **the probe will target the Pi's OWN
  `127.0.0.1:5597`, not the dev machine at `132.77.73.125`** — a listener on the dev machine (as
  originally instructed) will never be reached at all. This is caught by `EgressWorker`'s broad
  `except Exception`, so it fails safe (no crash), but it is not the test the plan describes.

Both of these share one root cause and one candidate fix: **add `"host": "132.77.73.125"` to
`pilot_hardware_config` id 21.** Router_bind's transport does not need it, but the lease mechanism
and a correctly-targeted egress probe both do. **Not applied here** — the coordinator's
instruction was explicit ("do not re-register anything"), and this is a real trade-off the user
should decide on, not something to quietly patch back in. Step 8 below is rewritten with a
workaround that works TODAY without that field (run the listener on the Pi itself, over SSH);
step 9 has no such workaround and is marked UNPROVEN outright.

---

## 1. Deploy manifest — ALREADY DEPLOYED

The eight-file manifest below was already synced and the pilot already restarted (confirmed by
the coordinator: "8 manifest files, all md5-verified... user has restarted the pilot"). This
section is kept as the historical record and for step 0's now-purely-confirmatory re-check — **do
not re-issue these as new instructions.**

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

`scripts/dev/extlink_smoke.py` was **NOT** part of this manifest — dev-machine-only tool, never
rsynced to the Pi.

### msgpack pin

`msgpack==1.0.5` (resolved live against the rig's Python 3.7.3 venv by plan 18-04). Step 0 below
re-confirms it importable post-deploy — a verification, not a re-install instruction.

### Pre-deploy verification (agent-performed, read-only SSH, recorded before the deploy happened)

| File | Pi md5 (pre-deploy) | Mirror md5 | Verdict |
|---|---|---|---|
| `autopilot/autopilot/tasks/mics_task.py` | `e227317365561dbaca20e9c079ba45fd` | `06c6b8621ea614e8e318cfe8ae0784fd` | DIFFERED — expected, Phase 18's own edit awaiting deploy |
| `autopilot/autopilot/hardware/external_hardware.py` | *(did not exist on the Pi)* | `766b6360817d9b7cb1ad5ecf0576ff22` | NEW file — expected |
| `autopilot/autopilot/hardware/external_hardware_wire.py` | *(did not exist)* | `76dd4f8dae27ca207720bd2980260928` | NEW — expected |
| `autopilot/autopilot/hardware/external_hardware_runtime.py` | *(did not exist)* | `cbc5ad480b56a96ebafa110f01230308` | NEW — expected |
| `autopilot/autopilot/hardware/external_hardware_ingress.py` | *(did not exist)* | `02131508390683ac12c35fdccb2ecb87` | NEW — expected |
| `autopilot/autopilot/hardware/external_hardware_binding.py` | *(did not exist)* | `009e2c607e665c91184086a8e8701eff` | NEW — expected |
| `requirements.txt` | `63c7e320a92614cec9904c49fc8e968e` | `1f35f93610fa58f0fa628e6d10cf6a09` | DIFFERED — expected, msgpack pin |
| `autopilot/requirements.txt` | `f57ce31233019b9fdc91397569b3ca30` | `a7f7b10b42c778ecd00c0133001d559c` | DIFFERED — expected, same pin |

No pre-existing, unexplained drift was found at the time of this diff.

---

## 2. Manual-only checklist (USER-RUN on the rig) — commands and expected outputs

All steps below are also written, in copy-paste order with no prose, to
`/home/ido/extlink_rig_commands.txt`. RESULT column is filled in by Task 4 after the checkpoint.

| # | Step | RESULT |
|---|---|---|
| 0 | Confirm deploy + pilot up (already deployed — verification only) | ⬜ PENDING |
| 1 | `router_bind` end-to-end (`source_id` now `demo`) | ⬜ PENDING |
| 1b | Author the gated transitions in the browser (`demo signals` group) | ⬜ PENDING |
| 2 | ~~`sub_connect` end-to-end~~ | ⬛ **UNPROVEN by deliberate scope decision — see §0a** |
| 3 | Stale policy + liveness split | ⬜ PENDING |
| 4 | Malformed input | ⬜ PENDING |
| 5 | ~~Readiness gate, three exits~~ | ⬛ **UNPROVEN — `required:false` never installs the gate — see §0b.1** |
| 6 | ~~Control-only module, role none, no socket~~ | ⬛ **UNPROVEN by deliberate scope decision — see §0a** |
| 6b | ~~Same module WITHOUT liveness override~~ | ⬛ **UNPROVEN by deliberate scope decision — see §0a** |
| 7 | Lifecycle on all three teardown paths | ⬜ PENDING |
| 8 | Egress under real latency (probe targets Pi's own loopback — see §0b.2) | ⬜ PENDING (workaround: run listener on the Pi itself) |
| 8b | Hand-driving + soak from the laptop (`source_id` now `demo`) | ⬜ PENDING |
| 9 | ~~Lease from a genuine pilot disconnect~~ | ⬛ **UNPROVEN — config has no `host`, no lease is ever acquired — see §0b.2** |
| 10 | Pi test suite | ⬜ PENDING |
| 11 | TEARDOWN | ⬜ PENDING (**mandatory**) |

Steps 2/5/6/6b/9 are left in this table (not deleted) precisely so they are not silently dropped
from the record — each carries its own reason and a pointer to §0a/§0b.

---

## 3. TEARDOWN (checkpoint step 11) — MANDATORY, exact reversing commands

`ExtlinkDemo` (module 62 / lib 177 / pilot config 21 / task definition 434) is this plan's ONLY
fixture now. Left assigned to pilot 1 / toolkit 100, it is `required: false` so it will not block
a real session's readiness gate — but its `source_id`/module still pollute the toolkit's picker
and `extlink_signals` output for every future editing session on this toolkit, so full removal
(not just unlinking) is still the right default.

```bash
export MICS_API_TOKEN="<same token used throughout>"

# 1. Delete the pilot_hardware_config row
curl -s -X DELETE "http://localhost:8000/api/pilots/1/hardware-config/ExtlinkDemo" -H "Authorization: Bearer $MICS_API_TOKEN"

# 2. Restore toolkit 100's hardware_module_ids to the EXACT pre-plan value (not [])
curl -s -X PATCH "http://localhost:8000/api/toolkits/100" -H "Authorization: Bearer $MICS_API_TOKEN" -H "Content-Type: application/json" \
  -d '{"hardware_module_ids":[1,5,6,7,8,24]}'

# 3. Unlink the lib from the toolkit (required before the lib itself can be deleted)
curl -s -X DELETE "http://localhost:8000/api/toolkits/100/hardware-libs/177" -H "Authorization: Bearer $MICS_API_TOKEN"

# 4. Delete the hardware_modules row (must precede deleting the lib -- FK)
curl -s -X DELETE "http://localhost:8000/api/hardware-modules/62" -H "Authorization: Bearer $MICS_API_TOKEN"

# 5. Delete the lib itself (cascades to its one version)
curl -s -X DELETE "http://localhost:8000/api/hardware-libs/177" -H "Authorization: Bearer $MICS_API_TOKEN"

# 6. Delete the extlink_demo task definition
curl -s -X DELETE "http://localhost:8000/api/task-definitions/434" -H "Authorization: Bearer $MICS_API_TOKEN"

# 7. Confirm no lease is held
curl -s "http://localhost:8000/api/device-leases" -H "Authorization: Bearer $MICS_API_TOKEN"

# 8. Re-run preflight for the three REAL sessions -- the output that actually proves the rig is
#    usable again
curl -s -X POST "http://localhost:8000/api/sessions/113/preflight-validate/1" -H "Authorization: Bearer $MICS_API_TOKEN"
curl -s -X POST "http://localhost:8000/api/sessions/110/preflight-validate/1" -H "Authorization: Bearer $MICS_API_TOKEN"
curl -s -X POST "http://localhost:8000/api/sessions/107/preflight-validate/1" -H "Authorization: Bearer $MICS_API_TOKEN"
```

Expected: step 1 `{"deleted": true}`; step 2 returns `"hardware_module_ids": [1,5,6,7,8,24]`;
steps 3-6 each `{"deleted": ...}` (or `{"toolkit_id":100,"hardware_lib_id":177}`-shaped for step
3); step 7 returns `[]`; step 8's three calls all return `{"ok": true, "issues": []}`.

**This section may only be skipped if the user explicitly says the rig stays in demo
configuration — record that decision here, in bold, at the top of this section, if so.**

---

## 4. Explicitly NOT an acceptance criterion

**Do not assert that a CONTINUOUS event exists in ES for `on_run_stop()` itself.**
`event_dispatcher.stop()` runs *before* `task.end()`/`release()` in `pilot.py`'s teardown, so that
event provably races a sender thread that may already have exited. Stop is verified by EFFECT —
device idle, lease released, log line present — never by an ES record.

---

## 5. Proven / Unproven (filled in by Task 4, after the checkpoint)

*Checkpoint not yet run. Rows marked ⬛ are UNPROVEN by scope decision / structural consequence,
independent of whether the checkpoint runs — see §0a/§0b for why. All other rows are ⬜ PENDING
until Task 4 records real checkpoint output.*

| Requirement | Behavior | Status |
|---|---|---|
| EXTLINK-01/02/05/11 | `router_bind` end-to-end + identity-mismatch drop | ⬜ PENDING |
| EXTLINK-19 | Signal-gated transition authored in the browser picker | ⬜ PENDING |
| EXTLINK-14 | `sub_connect` end-to-end via a live PUB + `@decoder` | ⬛ UNPROVEN — deliberate scope decision, no `sub_connect` fixture remains (§0a) |
| EXTLINK-06/07 | Stale policy split + liveness independent of staleness | ⬜ PENDING |
| EXTLINK-08 | Malformed input dropped, no traceback | ⬜ PENDING |
| EXTLINK-13 | Readiness gate, three exits | ⬛ UNPROVEN — `required:false` means the gate never installs (§0b.1) |
| EXTLINK-18 (happy) | Control-only module, no socket, participates in gate | ⬛ UNPROVEN — deliberate scope decision, no `role:"none"` fixture remains (§0a) |
| EXTLINK-18 (unhappy) | Same module without liveness override fails at construction | ⬛ UNPROVEN — same reason (§0a) |
| EXTLINK-16 | Lifecycle hooks on all three teardown paths | ⬜ PENDING |
| EXTLINK-15 | Egress under real latency, bounded queue, alive flips | ⬜ PENDING — provable, but only via the Pi-local-listener workaround (§0b.2); the dev-machine listener the plan originally described will not be reached |
| EXTLINK-20 | Hand driver + ~60Hz soak from a non-Pi machine | ⬜ PENDING |
| EXTLINK-17 | Lease from a genuine pilot disconnect + force-release + `device_held` | ⬛ UNPROVEN — the surviving fixture has no `host`, so no lease is ever acquired for it; nothing to disconnect (§0b.2) |
| — | Pi test suite (standing gap since Phase 24) | ⬜ PENDING |
| — | TEARDOWN — demo fixtures removed, real preflight clean | ⬜ PENDING |

**Residual risk (restate regardless of outcome above):** Phase 18's lease safety net releases the
lease row and lets the run be marked errored, but does **not** command the foreign device to
stop. A crashed pilot can leave an external recorder running until a human notices. Phase 26
decides whether OpenEphys needs its own additional reconciliation.

---

*Phase: 18-extlink-pi-transport*
*Prepared: 2026-08-09 (Tasks 1-2, revised after the single-lib consolidation). Checkpoint (Task 3)
and results (Task 4) pending.*
