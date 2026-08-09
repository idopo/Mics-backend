# Phase 18 — Hardware Validation Log (consolidated rig checkpoint, plan 18-12)

**Date opened:** 2026-08-09
**Status:** Rewritten twice after mid-flight scope decisions — first, the fixture set was
consolidated from three demo libs to one; then the coordinator patched that one fixture's config
(`host` added, `required` flipped back to `true`) to restore three rows this agent had flagged as
silently lost. Task 1/2 preparation complete (agent-side). Checkpoint (Task 3) NOT YET RUN by the
user. RESULT columns below are placeholders until the checkpoint executes.
**Scope of this document:** what is PROVEN on hardware vs. what remains UNPROVEN, the exact
deploy manifest, the exact commands for every manual-only row of `18-VALIDATION.md`, and the
exact system state (ids) this checkpoint depends on.

Modelled on `.planning/phases/24-trigger-assignment-action-lists/24-HARDWARE-VALIDATION.md`.

**Security note:** an earlier revision of `/home/ido/extlink_rig_commands.txt` embedded the live
`MICS_API_TOKEN` JWT in plaintext. The coordinator replaced it with a `docker-compose.yml`
extraction one-liner plus a length sanity check; verified zero `eyJ` occurrences remain in either
artifact. **Never write the literal token into any file in this phase again.**

---

## 0. Registered fixture state (single consolidated demo lib, config since repatched)

**What changed and why, in order:**
1. The original preparation registered three demo libs (`DemoDealer`/router_bind,
   `DemoControl`/role-none, `DemoSub`/sub_connect). The user found the FDA editor's lib picker
   unusable at 60 entries, traced most of it to an unrelated pre-existing bug
   (`api/tests/test_hardware_libs_extlink.py`'s two route-level tests leaked 2 lib rows per
   `pytest` run against the real dev DB — ~50 orphaned rows over the phase), and — separately —
   made a deliberate, confirmed scope decision to collapse this plan's three demo fixtures into
   ONE. **The coordinator (not this agent) purged the 51 orphaned rows, fixed the test leak
   (commit `84612af`), and built the single consolidated lib** (`ExtlinkDemo`, lib 177 / module
   62 / pilot config 21).
2. That single fixture's config initially carried `"required": false` and no `"host"` key. This
   agent flagged (not fixed) two consequences the user had not been told about: EXTLINK-13's
   readiness-gate proof requires `required: true`, and EXTLINK-17's lease proof plus a
   correctly-targeted EXTLINK-15 egress probe both require a `host`. **The coordinator confirmed
   both flags were correct and patched pilot config 21** to add `"host": "132.77.73.125"` and
   flip `"required"` back to `true` — verified: `validate_extlink_config` permits `host` on
   `router_bind` (only `listen_port` is required for that role), and preflight for sessions
   113/110 stayed `{"ok": true, "issues": []}` after the patch.

This agent performed none of the DB/API mutations described above (three separate rounds, all
coordinator-applied) — this section and `/home/ido/extlink_rig_commands.txt` are kept in sync
with each round by re-reading live state, never by re-deriving it from memory.

All ids below were confirmed live via read-only queries against the running `api` container and
its DB, immediately before this revision. Full backend suite green (435 passed, 1 skipped);
`GET /api/device-leases` returns `[]`; preflight clean for sessions 113/110/107 on pilot 1.

| Entity | id | Notes |
|---|---|---|
| Pilot (the rig) | 1 | `pilot_raspberry_lior`, ip `132.77.72.28` |
| Real sessions used for preflight checks | 113 / 110 / 107, all pilot 1 | all three return `{"ok": true, "issues": []}` |
| Toolkit (shared with real task def 186) | 100 | `source_less_toolkit`, backend-authored |
| Toolkit's `hardware_module_ids` **before this plan's Task 1** | `[1, 5, 6, 7, 8, 24]` | **restore to exactly this list at TEARDOWN** |
| Toolkit's `hardware_module_ids` **now** | `[1, 5, 6, 7, 8, 24, 62]` | |
| The ONE demo lib — `extlink_demo.py` / `ExtlinkDemo` | lib **177**, version **132** (only version, state `beta`, not promoted stable) | `role: "router_bind"`. Two signals — `left_paw_x` (`return_default`, 200ms), `right_paw_x` (`hold_last`, 200ms) — one event `object_detected`, one `@command ping`, PLUS `on_run_start`/`on_run_stop`/`_egress_probe` (the egress-demo trio originally written for `DemoControl`, lifted in verbatim) |
| Module | hardware_modules id **62**, name `ExtlinkDemo` | |
| pilot_hardware_config — **current (post-repatch)** | id **21**, name `ExtlinkDemo` | `{"class_name":"ExtlinkDemo","role":"router_bind","listen_port":5599,"host":"132.77.73.125","source_id":"demo","stale_ms":3000,"required":true,"wait_timeout_s":30,"egress_fail_threshold":3}` — confirmed live via `GET /api/pilots/1/hardware-config` |
| `extlink_demo` task definition | **434**, `task_name` `extlink_demo-c8ecda5c` | toolkit 100. `hw_lib_versions` still carries stale dead keys `{"162":119,"163":125,"164":121}` from the deleted 3-lib set (harmless — those lib ids are unlinked from the toolkit, so `resolve_lib_version_id` never looks them up; lib 177 itself resolves via the "active" rung since it has no toolkit-default pin and no stable version). The two signal-gated transitions (`wait->armed`, `armed->fired`) are **still deliberately absent** — step 1b authors them in the browser, against `demo.left_paw_x`/`demo.right_paw_x` — **and must stay unauthored; see §0c** |
| Dev machine (runs `extlink_smoke.py`/`extlink_driver.py`/curl/`nc`) | `132.77.73.125` | = `TERMINALIP` in the Pi's own prefs; also `ExtlinkDemo`'s configured `host` now |

**`required: true` behavioral consequence (new, since the repatch):** a run on pilot 1 will now
block at the readiness gate for up to `wait_timeout_s` (30s) and then FAIL if `demo`'s
`router_bind` source is not already connected. Step 1's probe (or step 8b's hand driver) must be
started **before** starting any run on this pilot from here on — noted inline at steps 1, 5, 7.

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
**permanently UNPROVEN in this checkpoint session**, with no fixture left to exercise them. This
is the ONLY scope reduction still in effect — the two extra ones this agent flagged (§0b, below)
were subsequently fixed by the coordinator's repatch and no longer apply.

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

### 0b. Two additional consequences this agent flagged — RESOLVED by the coordinator's repatch

*Kept as a historical record; both issues below are fixed as of this revision, not open.*

1. `ExtlinkDemo`'s config originally carried `"required": false`, which meant
   `_install_extlink_gate` never installed the readiness pre-state (`_extlink_required` is
   populated only from `required: true` configs, `mics_task.py:179-200`), silently costing
   EXTLINK-13's rig proof (step 5) beyond what the user had agreed to. **Fixed:** the coordinator
   flipped `required` to `true`. Step 5 is back to PENDING.
2. `ExtlinkDemo`'s config originally had no `"host"` key, which (a) meant
   `orchestrator_station.py::_acquire_device_leases` (`if not host: continue`) would never
   acquire a lease for it — EXTLINK-17 (step 9) unprovable outright — and (b) meant the lifted-in
   `_egress_probe`'s `socket.create_connection((self.host, 5597), ...)` would resolve `self.host
   = None` to the Pi's own loopback address, missing the dev-machine listener EXTLINK-15 (step 8)
   describes. **Fixed:** the coordinator added `"host": "132.77.73.125"` to config 21. Steps 8
   and 9 are back to PENDING, using the ORIGINAL dev-machine-listener instructions (the
   Pi-local-listener workaround this agent had drafted is no longer needed and has been removed
   from the commands file).

### 0c. New finding — the save gate does not validate `{"view": ...}` operands (document, do not fix)

Probed by the coordinator with a throwaway scratch task definition (ids 478/479, created and
deleted, no residue):
- `POST /api/task-definitions` with a transition condition `{"view": "demo.left_paw_x"}` →
  **ACCEPTED** (correct — a real key).
- The identical POST with `{"view": "demo.no_such_signal"}` → **ALSO ACCEPTED**, not rejected.

**Root cause, verified by reading `api/fda_validation.py`:** `reject_if_hard_errors` wires
`extlink_keys` into `validate_compute_variables` only (line ~296/328). `validate_condition_operands`
(line 172) explicitly and by design ignores every `{"view": ...}` operand — its own docstring:
"Every other operand shape ... is ignored here — this pass adds exactly one rule and must not
become a general operand validator." It only hard-validates `{"view_detector": ...}` operands.
An unknown extlink key is therefore caught when used as a COMPUTE VARIABLE, but never when used
inside a TRANSITION CONDITION. Plan 18-13's own save-gate verification used a compute variable,
which is why this gap was never noticed until now.

**User-visible consequence:** a typo in the signal name at step 1b (e.g. `demo.left_pawx`) saves
cleanly with no 422, and the authored transition then silently never fires — on the rig this is
indistinguishable from "the transport is broken." **Not fixed here** (out of this plan's scope —
a save-gate change belongs to plan 18-13's territory, and modifying `validate_condition_operands`
to become a general operand validator is explicitly what that function's own docstring forbids).
Step 1b below adds an explicit read-back verification sub-step so the checkpoint catches this
class of mistake without depending on the save gate to.

**Telling the two failure classes apart, at step 1b:** task definition 434 is deliberately left
with its two transitions unauthored so that authoring them in the browser is the actual proof
plan 18-14's picker renders and writes the correct key — **do not curl them in**, that would
defeat the entire point of the step. The backend's save gate is confirmed (above) to accept a
transition naming a nonexistent signal, so: if the picker itself fails (no `demo signals` group,
or the item doesn't produce a working operand), that is a **picker bug** (plan 18-14). If the
picker works and the read-back verification at step 1b still finds an unknown key, that would
point at the **save gate** instead (this section's gap). They are two different failure classes;
step 1b's instructions tell the user which one they hit.

---

## 1. Deploy manifest — ALREADY DEPLOYED

The eight-file manifest below was already synced and the pilot already restarted. This section is
kept as the historical record and for step 0's now-purely-confirmatory re-check — **do not
re-issue these as new instructions.**

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
| 1 | `router_bind` end-to-end (`source_id` now `demo`; start the source before any run — `required:true`) | ⬜ PENDING |
| 1b | Author the gated transitions in the browser (`demo signals` group) + read-back verification against the save-gate gap (§0c) | ⬜ PENDING |
| 2 | ~~`sub_connect` end-to-end~~ | ⬛ **UNPROVEN by deliberate scope decision — see §0a** |
| 3 | Stale policy + liveness split | ⬜ PENDING |
| 4 | Malformed input | ⬜ PENDING |
| 5 | Readiness gate, three exits (`required:true` again — no longer blocked) | ⬜ PENDING |
| 6 | ~~Control-only module, role none, no socket~~ | ⬛ **UNPROVEN by deliberate scope decision — see §0a** |
| 6b | ~~Same module WITHOUT liveness override~~ | ⬛ **UNPROVEN by deliberate scope decision — see §0a** |
| 7 | Lifecycle on all three teardown paths | ⬜ PENDING |
| 8 | Egress under real latency (probe now correctly targets this dev machine's port 5597 — no workaround needed) | ⬜ PENDING |
| 8b | Hand-driving + soak from the laptop (`source_id` now `demo`) | ⬜ PENDING |
| 9 | Lease from a genuine pilot disconnect (`host` present again — no longer blocked) | ⬜ PENDING |
| 10 | Pi test suite | ⬜ PENDING |
| 11 | TEARDOWN | ⬜ PENDING (**mandatory**) |

Steps 2/6/6b are the only ones left permanently UNPROVEN (not deleted from this table) — the
user's actual, confirmed scope decision. Steps 5/8/9 were briefly UNPROVEN in an earlier revision
of this document but are back to PENDING after the coordinator's config repatch (§0b).

---

## 3. TEARDOWN (checkpoint step 11) — MANDATORY, exact reversing commands

`ExtlinkDemo` (module 62 / lib 177 / pilot config 21 / task definition 434) is this plan's ONLY
fixture now. It is `required: true` again (§0b) — left assigned to pilot 1 / toolkit 100, every
subsequent REAL session on this rig either preflight-fails or hangs the full 30s `wait_timeout_s`
waiting for a demo device nobody is running, so full removal (not just unlinking) is mandatory,
not optional cleanup.

```bash
export MICS_API_TOKEN=$(grep -h "MICS_API_TOKEN" /home/ido/mics-backend/docker-compose.yml | head -1 | sed 's/.*MICS_API_TOKEN[=:] *//;s/["'"'"']//g')

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

*Checkpoint not yet run. Rows marked ⬛ are UNPROVEN by deliberate scope decision (§0a) and stay
that way regardless of whether the checkpoint runs. All other rows are ⬜ PENDING until Task 4
records real checkpoint output — including EXTLINK-13/15/17, which were briefly also UNPROVEN in
an earlier revision but are back to PENDING after the coordinator's config repatch (§0b).*

| Requirement | Behavior | Status |
|---|---|---|
| EXTLINK-01/02/05/11 | `router_bind` end-to-end + identity-mismatch drop | ⬜ PENDING |
| EXTLINK-19 | Signal-gated transition authored in the browser picker (+ read-back verification, §0c) | ⬜ PENDING |
| EXTLINK-14 | `sub_connect` end-to-end via a live PUB + `@decoder` | ⬛ UNPROVEN — deliberate scope decision, no `sub_connect` fixture remains (§0a) |
| EXTLINK-06/07 | Stale policy split + liveness independent of staleness | ⬜ PENDING |
| EXTLINK-08 | Malformed input dropped, no traceback | ⬜ PENDING |
| EXTLINK-13 | Readiness gate, three exits | ⬜ PENDING — `required:true` restored, gate installs normally again |
| EXTLINK-18 (happy) | Control-only module, no socket, participates in gate | ⬛ UNPROVEN — deliberate scope decision, no `role:"none"` fixture remains (§0a) |
| EXTLINK-18 (unhappy) | Same module without liveness override fails at construction | ⬛ UNPROVEN — same reason (§0a) |
| EXTLINK-16 | Lifecycle hooks on all three teardown paths | ⬜ PENDING |
| EXTLINK-15 | Egress under real latency, bounded queue, alive flips | ⬜ PENDING — `host` restored, probe now correctly targets the dev machine |
| EXTLINK-20 | Hand driver + ~60Hz soak from a non-Pi machine | ⬜ PENDING |
| EXTLINK-17 | Lease from a genuine pilot disconnect + force-release + `device_held` | ⬜ PENDING — `host` restored, lease is acquirable again |
| — | Pi test suite (standing gap since Phase 24) | ⬜ PENDING |
| — | TEARDOWN — demo fixtures removed, real preflight clean | ⬜ PENDING |
| — | Transition-condition operand validation gap (§0c) | documented, not a checkpoint pass/fail row — read-back verification folded into step 1b |

**Residual risk (restate regardless of outcome above):** Phase 18's lease safety net releases the
lease row and lets the run be marked errored, but does **not** command the foreign device to
stop. A crashed pilot can leave an external recorder running until a human notices. Phase 26
decides whether OpenEphys needs its own additional reconciliation.

---

*Phase: 18-extlink-pi-transport*
*Prepared: 2026-08-09 (Tasks 1-2, revised twice: single-lib consolidation, then the coordinator's
config repatch + the §0c validation-gap finding). Checkpoint (Task 3) and results (Task 4)
pending.*
