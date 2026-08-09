# Phase 18 — Hardware Validation Log (consolidated rig checkpoint, plan 18-12)

**Date opened:** 2026-08-09

**Checkpoint runs (all 2026-08-09):** six runs on pilot 1 (`pilot_raspberry_lior`), session 115,
task_def 434, toolkit 100:

| Run | Window (recorded) | Driver | Result | Notes |
|---|---|---|---|---|
| 552 | 10:50:03–10:55:10 | driver on Linux dev host `132.77.73.125` | ✅ PASS | 20 transitions, `demo.alive` 4 events |
| 553 | 11:00:42–11:04:31 | driver on Mac (stale old copy) | ❌ FAIL — `EXTLINK_GATE_TIMEOUT` | `demo.alive` 0 events — driver still pushed the stale `dlc_cam1` source-id, dropped by the ROUTER's identity check |
| 554 | 11:05:45–11:06:05 | driver on Mac (current copy) | ✅ PASS | 8 transitions, `demo.alive` 4 |
| 555 | 11:06:24–11:07:41 | driver on Mac (current copy) | ❌ FAIL — `EXTLINK_GATE_TIMEOUT` | `demo.alive` 0 events — this time NOT a driver problem; the egress-probe race below |
| 556 | 11:13:38–11:20:38 | driver on Mac, lib v2 + coordinator's egress listener running | ✅ PASS | 587 ES docs, 32 transitions, 541 `Tracker`, 6 `Boolean_Tracker`, 1 `ExtlinkDemo` event |

No run 551 in scope.

**Status:** CHECKPOINT COMPLETE. Both failures (553/555) are fully diagnosed and root-caused —
**neither is a Phase 18 code defect** (see §0d). Per-requirement verdicts are in §5. **TEARDOWN
(step 11) WAS DELIBERATELY NOT RUN** — the user chose to keep this one curated demo lib rather
than remove it. See the boxed notice below and §3.

> ⚠ **TEARDOWN DEFERRED — READ BEFORE STARTING ANY FUTURE SESSION ON PILOT 1.**
> The demo fixture `ExtlinkDemo` (module 62, `role: "router_bind"`, `required: true`, listen
> port 5599, `source_id: "demo"`) is still assigned to toolkit 100 and configured on pilot 1.
> This is the plan's own documented footgun (§3): every subsequent REAL session on this pilot
> either preflight-fails or hangs the full 30s `wait_timeout_s` at the readiness gate waiting
> for a demo device nobody is running. This is not an oversight — the user asked to keep this
> one curated demo lib, and TEARDOWN is a pending decision, not a skipped step. §3 has the exact
> reversing commands ready to run whenever that decision is made. **A second standing dependency
> exists too:** a TCP echo listener (`scratchpad/egress_listener.py`) is still running on this
> dev host at `132.77.73.125:5597`. `ExtlinkDemo`'s egress probe depends on it — without it,
> `demo.alive` drops to `false` roughly 3 seconds into every run on this pilot (§0d). Both
> dependencies must be resolved together, or independently accepted, before the demo is left
> unattended.

**Scope of this document:** what is PROVEN on hardware vs. what remains UNPROVEN/DEFERRED, the
exact deploy manifest, the exact commands for every manual-only row of `18-VALIDATION.md`, and
the exact system state (ids) this checkpoint depends on.

Modelled on `.planning/phases/24-trigger-assignment-action-lists/24-HARDWARE-VALIDATION.md`.

**Security note:** an earlier revision of `/home/ido/extlink_rig_commands.txt` embedded the live
`MICS_API_TOKEN` JWT in plaintext. The coordinator replaced it with a `docker-compose.yml`
extraction one-liner plus a length sanity check; verified zero `eyJ` occurrences remain in either
artifact. **Never write the literal token into any file in this phase again.**

---

## 0. Registered fixture state (single consolidated demo lib)

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
   was flagged and then coordinator-patched to add `"host": "132.77.73.125"` and flip
   `"required"` back to `true` — restoring EXTLINK-13's and EXTLINK-17's rig-proof preconditions.
3. **A second lib version was added between runs 555 and 556.** Version id **137** (version
   number 2) adds one diagnostic method, `liveness_hook`, that returns `True` unconditionally.
   Nothing was pinned at either the toolkit rung or the task-definition rung, so v2 resolved
   automatically via the "active" rung with no config change and no redeploy — run 556 ran
   against it without anyone re-registering anything.

All ids below were confirmed live via read-only queries against the running `api` container and
its DB. Full backend suite green (435 passed, 1 skipped) at the time of this revision; preflight
was clean for sessions 113/110/107 on pilot 1 before the rig session began.

| Entity | id | Notes |
|---|---|---|
| Pilot (the rig) | 1 | `pilot_raspberry_lior`, ip `132.77.72.28` |
| Real sessions used for preflight checks | 113 / 110 / 107, all pilot 1 | all three returned `{"ok": true, "issues": []}` before the rig session |
| Toolkit (shared with real task def 186) | 100 | `source_less_toolkit`, backend-authored |
| Toolkit's `hardware_module_ids` **before this plan's Task 1** | `[1, 5, 6, 7, 8, 24]` | **restore to exactly this list at TEARDOWN** |
| Toolkit's `hardware_module_ids` **now** | `[1, 5, 6, 7, 8, 24, 62]` | |
| The ONE demo lib — `extlink_demo.py` / `ExtlinkDemo` | lib **177** | two versions now registered — see below |
| Lib version 1 | version **132** | original: two signals — `left_paw_x` (`return_default`, 200ms), `right_paw_x` (`hold_last`, 200ms) — one event `object_detected`, one `@command ping`, PLUS `on_run_start`/`on_run_stop`/`_egress_probe` (the egress-demo trio lifted verbatim from the original `DemoControl` design). Used for runs 552–555 |
| Lib version 2 | version **137** | adds `liveness_hook` returning `True` unconditionally — a diagnostic added between runs 555 and 556, **not pinned anywhere**, so it resolved automatically. Used for run 556 |
| Module | hardware_modules id **62**, name `ExtlinkDemo` | |
| pilot_hardware_config | id **21**, name `ExtlinkDemo` | `{"class_name":"ExtlinkDemo","role":"router_bind","listen_port":5599,"host":"132.77.73.125","source_id":"demo","stale_ms":3000,"required":true,"wait_timeout_s":30,"egress_fail_threshold":3}` |
| `extlink_demo` task definition | **434**, `task_name` `extlink_demo-c8ecda5c` | toolkit 100. Two transitions **authored via the API by the coordinator, NOT by opening the FDA editor's picker** — see the EXTLINK-19 caveat in §5. `condition_tree` shapes (exact, read back live): `wait->armed`: `{"op":">","left":{"view":"demo.left_paw_x"},"right":0.5}`; `armed->fired`: `{"op":"<","left":{"view":"demo.left_paw_x"},"right":0.2}`; `fired->wait`: unconditional. **No terminal state, by design** — the FDA cycles forever until stopped manually (item 10 in §6) |
| Dev machine (runs `extlink_smoke.py`/`extlink_driver.py`/curl/`nc`) | `132.77.73.125` | = `TERMINALIP` in the Pi's own prefs; also `ExtlinkDemo`'s configured `host` |

**`required: true` behavioral consequence:** a run on pilot 1 blocks at the readiness gate for up
to `wait_timeout_s` (30s) and then FAILS if `demo`'s `router_bind` source is not already
connected AND its egress probe is reachable (see §0d). This is exactly what runs 553/555
demonstrate.

**Extlink signal aggregation** (`GET /api/toolkits/100` → `extlink_signals`):
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
This is what the FDA editor's picker should offer: option group **`demo signals`** (source_ids
has length 1, so the group label is `${source_id} signals`, not the module name), items
`left_paw_x (float)`, `right_paw_x (float)`.

### 0a. Deliberate scope reduction (confirmed, user-approved) — do not re-litigate

The user was told and confirmed: collapsing to one `router_bind`-only lib leaves the following
**permanently UNPROVEN in this checkpoint session**, with no fixture left to exercise them.

- **`role: "none"` (control-only, no inbound socket) end-to-end on the real rig** (EXTLINK-18,
  happy path) — no `role: "none"` module exists anymore.
- **The SAME control-only lib WITHOUT its `liveness_hook` failing at construction** (EXTLINK-18,
  unhappy path / the liveness-override-mandatory rule) — same reason; no broken lib version
  remains to repin to.
- **`sub_connect` end-to-end against a live PUB, `@decoder` translating a foreign frame**
  (EXTLINK-14's rig-only half) — no `sub_connect` module exists anymore.

These three rows are marked UNPROVEN in §5 with this reason, not silently dropped. The underlying
mechanisms remain agent-tested (unit-level, `-k role_none`/`-k control_only`/`-k role_selection`
in the Pi-mirror suite, per `18-VALIDATION.md`) — only the rig end-to-end proof is what's lost.

### 0b. Two earlier consequences — resolved before the rig session

*Historical record; both fixed before run 552.*

1. `ExtlinkDemo`'s config originally carried `"required": false`, which would have silently
   cost EXTLINK-13's rig proof. **Fixed:** flipped to `true`.
2. `ExtlinkDemo`'s config originally had no `"host"` key, which would have made EXTLINK-17
   unprovable and misdirected the `_egress_probe` at the Pi's own loopback. **Fixed:** added
   `"host": "132.77.73.125"`.

### 0c. The save gate does not validate `{"view": ...}` operands (document, do not fix)

Probed with a throwaway scratch task definition (ids 478/479, created and deleted, no residue):
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

**User-visible consequence:** a typo in the signal name (e.g. `demo.left_pawx`) saves cleanly
with no 422, and the authored transition then silently never fires — on the rig this is
indistinguishable from "the transport is broken." **Not fixed here** (out of this plan's scope —
a save-gate change belongs to plan 18-13's territory, and modifying `validate_condition_operands`
to become a general operand validator is explicitly what that function's own docstring forbids).

**A second, related trap found this session (§6 item 4):** the runtime condition shape is
`condition_tree` with a **bare literal** on the right (`{"op":">","left":{"view":"..."},"right":0.5}`),
NOT `condition` with `{"const": 0.5}`. The save gate accepts the wrong shape silently too — a
transition can save, validate ok, and never fire because the shape itself was wrong, a second
and independent way to hit the same user-visible symptom as the typo case above.

### 0d. Root cause of the 553/555 failures — fully diagnosed, NOT a Phase 18 code bug

`recompute_alive` (`external_hardware_binding.py:131`) computes
`new_value = liveness_alive and not owner._egress_failed`. When the coordinator consolidated
three fixtures into one, it folded `DemoControl`'s `_egress_probe` into `ExtlinkDemo` and added a
`host` field pointing at `132.77.73.125:5597`, where **nothing was listening** at the time of
runs 553/555. Three failed probes at 1/s tripped `egress_fail_threshold: 3`, forcing
`demo.alive` to `false` roughly 3.0s into every run. Gate opening then became a race between the
gate's alive sample and that 3-second timer: 552/554 sampled in time (their gates opened before
the probe had failed three times), 553/555 did not.

**Proof, observed live in run 556 with no restart or redeploy of anything on the Pi:**
- `demo.alive` went `1` at `14:13:39.019`, then `0` at `14:13:42.022` — exactly 3.0s later,
  matching `egress_fail_threshold: 3` at 1 probe/s.
- The coordinator started a TCP echo listener on `132.77.73.125:5597` at `11:15:25Z`.
- `demo.alive` returned to `1` at `14:15:25.040` — the same second the listener came up, nothing
  else changed.
- The Pi was confirmed probing at exactly 1/s (the listener served 10 probes in 10s).

**This behavior is correct by design, not a bug:** a device whose outbound channel is dead is
not alive. The defect was the coordinator's fixture configuration (an egress probe target with
no listener), not the phase's code. Recorded as such — **not counted against any Phase 18
requirement.**

**Run 553's failure has a second, independent contributing cause:** the driver still used the
stale `dlc_cam1` source-id (fixed in commit `7dbdf3d`, but not yet picked up by that Mac copy at
the time), so its frames were dropped by the ROUTER's identity check regardless of the egress
race. Run 555, by contrast, used the current driver and failed purely on the egress race.

### 0e. Two earlier coordinator claims — retracted

1. **"Float values are truncated" — FALSE.** `coerce_for_event` deliberately writes a
   long-safe `value` alongside a lossless `value_raw`; `Tracker.set` stores the float
   unmodified. Verified this session against real ES documents (`demo.left_paw_x` `value_raw`
   entries carry full float precision, e.g. the settle-to-default `0.0` and hand-driven values).
2. **"Phase 18 has a genuine liveness bug" — FALSE.** See §0d — the alive flips in runs
   553/555/556 are the egress-probe design working exactly as intended against a
   fixture-configuration gap, not a code defect.

Both retractions are recorded here so a future reader does not act on the earlier, wrong claims.

### 0f. Type coverage, run 556

| Type | Signal / event | Evidence | Verdict |
|---|---|---|---|
| float + `return_default` | `demo.left_paw_x` | 541 `Tracker` events; falls to `0.0` and is re-written every ~1.5s by the stale sweep once input stops | ✅ PROVEN |
| float + `hold_last` | `demo.right_paw_x` | set once to `0.8` at `14:19:06.931`, never rewritten afterward | ✅ PROVEN (this is EXTLINK-06's second half) |
| dict event | `object_detected` | fired at `14:19:25.113`, `event_type` `ExtlinkDemo`, payload `{"object":"paw","confidence":0.9}` intact (str + float) | ✅ PROVEN |
| bool | `demo.alive` | exercised across both failure (§0d) and recovery | ✅ PROVEN |
| `@command ping` | — | never sent, no run exercised it | ⬛ UNPROVEN |

### 0g. Readiness gate, directly observed (run 556)

```
14:13:39.019  demo.alive = 1
14:13:39.026  state -> _wait_extlink_ready
14:13:39.028  state -> wait
```
The gate held for ~2ms and then released — this is a direct log-line observation, not an
inference from "the run could not have started otherwise" (that was the best available evidence
in an earlier revision of this document; run 556 supersedes it with a real trace). This proves
only the **proceed** exit; the `EXTLINK_SKIP_WAIT` exit and the timeout-abort exit were not
exercised this session (see §5).

---

## 1. Deploy manifest — ALREADY DEPLOYED

The eight-file manifest below was already synced and the pilot already restarted. This section is
kept as the historical record — **do not re-issue these as new instructions.**

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

`msgpack==1.0.5` (resolved live against the rig's Python 3.7.3 venv by plan 18-04). Importable
post-deploy — confirmed.

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

## 2. Manual-only checklist (USER-RUN on the rig) — final results

All steps were also written, in copy-paste order, to `/home/ido/extlink_rig_commands.txt`.

| # | Step | RESULT |
|---|---|---|
| 0 | Confirm deploy + pilot up | ✅ PROVEN — all six runs started/stopped against the deployed code; pilot returned to IDLE/connected after every run |
| 1 | `router_bind` end-to-end (`source_id` `demo`) | ✅ PROVEN — runs 552/554/556 all show repeating armed/fired transition cycles driven by real pushed values. Identity-mismatch-drop sub-case not separately exercised as a positive test, but run 553's failure is partial evidence the identity check is live (stale `dlc_cam1` identity was silently dropped) |
| 1b | Author the gated transitions in the browser (`demo signals` group) + read-back verification | ⚠ **NOT PROVEN AS SPECIFIED** — transitions on task def 434 were authored via the API by the coordinator, not by opening the FDA editor's picker (§0). The data-layer shape is confirmed correct and the transitions fired live 40+ times across three successful runs — but the browser-authoring path itself (plan 18-14's UI) is UNPROVEN this session. See §5 |
| 2 | `sub_connect` end-to-end | ⬛ UNPROVEN — deliberate scope decision, no `sub_connect` fixture remains (§0a) |
| 3 | Stale policy + liveness split | ⚠ PARTIAL — EXTLINK-06 fully PROVEN this session (both `return_default` and `hold_last`, §0f). EXTLINK-07 (liveness independent of *signal staleness*, as a directed test) UNPROVEN — not exercised as originally planned; the alive flips observed in §0d were driven by the egress probe, not by stopping the signal source, so they demonstrate EXTLINK-15 rather than EXTLINK-07 |
| 4 | Malformed input | ⬛ UNPROVEN — not exercised this session |
| 5 | Readiness gate, three exits | ⚠ PARTIAL — the **proceed** exit is PROVEN by **direct observation** in run 556 (§0g, log-line trace, not inference). The `EXTLINK_SKIP_WAIT` exit and the timeout-abort exit were not exercised |
| 6 | Control-only module, role none, no socket | ⬛ UNPROVEN — deliberate scope decision, no `role:"none"` fixture remains (§0a) |
| 6b | Same module WITHOUT liveness override | ⬛ UNPROVEN — deliberate scope decision, same reason (§0a) |
| 7 | Lifecycle on all three teardown paths | ⚠ PARTIAL — normal-completion / clean-stop path ✅ PROVEN across four runs (552/554/555/556 all returned pilot to IDLE with no stranded device lease); `EXTLINK_GATE_TIMEOUT` aborts (553/555) also completed cleanly, which is itself evidence the gate's own timeout-abort path tears down without stranding anything. STOP-button-mid-run and induced-task-exception paths were NOT exercised — still UNPROVEN as those specific sub-cases |
| 8 | Egress under real latency | ✅ PROVEN — more thoroughly than the plan called for. Failure detection (3 consecutive probe failures → `alive=false` at exactly the 3.0s boundary), the threshold trip itself, AND recovery (alive flips back to `true` the same second a listener starts) were all directly observed in run 556 (§0d). FDA timing was visibly unaffected throughout — the armed/fired cycle kept running through the alive-false window |
| 8b | Hand-driving + soak from the laptop | ⚠ PARTIAL — hand-driving from a **real Mac laptop over Wi-Fi** ✅ PROVEN (runs 554/556, superseding the earlier "Mac unreachable" substitution). The mandated **~60Hz soak was NOT run** — only interactive/lower-rate driving — so EXTLINK-20's soak claim specifically is UNPROVEN |
| 9 | Lease from a genuine pilot disconnect | ⬛ UNPROVEN — not exercised this session (no kill-pilot-process test run; the observed clean-stop lease behavior in step 7 is a different code path) |
| 10 | Pi test suite | ⬛ UNPROVEN — not exercised this session |
| 11 | TEARDOWN | ⛔ **DEFERRED — pending user decision, not run.** See the boxed notice at the top of this document and §3 |

---

## 3. TEARDOWN (checkpoint step 11) — MANDATORY WHEN RUN, exact reversing commands

`ExtlinkDemo` (module 62 / lib 177 / pilot config 21 / task definition 434) is this plan's ONLY
fixture. It is `required: true` — left assigned to pilot 1 / toolkit 100, every subsequent REAL
session on this rig either preflight-fails or hangs the full 30s `wait_timeout_s` waiting for a
demo device nobody is running, so full removal (not just unlinking) would be mandatory the moment
the user decides to stop keeping the demo around. **As of this revision the user has chosen to
keep it; teardown remains a pending decision, not a completed or skipped step.**

**Standing dependency noted alongside teardown:** a TCP echo listener
(`scratchpad/egress_listener.py`) is running on this dev host at `132.77.73.125:5597`, keeping
`ExtlinkDemo`'s egress probe satisfied. If that listener is ever stopped without also stopping or
reconfiguring the demo fixture, `demo.alive` will drop ~3s into any future run on this pilot,
exactly as it did in runs 553/555 (§0d). Two options exist, both currently open: (a) keep the
listener running indefinitely alongside the demo lib, or (b) strip `_egress_probe` from the lib
so the demo no longer depends on anything outside the Pi. Neither has been decided.

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

# 5. Delete the lib itself (cascades to both versions, 132 and 137)
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

# 9. (only if option (a) above is abandoned) stop the standing egress listener
#    on this dev host — scratchpad/egress_listener.py — once nothing depends on it
```

Expected: step 1 `{"deleted": true}`; step 2 returns `"hardware_module_ids": [1,5,6,7,8,24]`;
steps 3-6 each `{"deleted": ...}` (or `{"toolkit_id":100,"hardware_lib_id":177}`-shaped for step
3); step 7 returns `[]`; step 8's three calls all return `{"ok": true, "issues": []}`.

**This section is currently skipped because the user explicitly said the rig stays in demo
configuration.** That decision is recorded here, in this section, per the plan's own instruction.

---

## 4. Explicitly NOT an acceptance criterion

**Do not assert that a CONTINUOUS event exists in ES for `on_run_stop()` itself.**
`event_dispatcher.stop()` runs *before* `task.end()`/`release()` in `pilot.py`'s teardown, so that
event provably races a sender thread that may already have exited. Stop is verified by EFFECT —
device idle, lease released, log line present — never by an ES record.

---

## 5. Proven / Unproven / Deferred (final)

| Requirement | Behavior | Status |
|---|---|---|
| EXTLINK-01/02/05/11 | `router_bind` end-to-end (bind, push, transition fires) | ✅ **PROVEN** — runs 552/554/556. Identity-mismatch-drop not separately exercised as a positive test |
| EXTLINK-06 | Both stale policies (`return_default` AND `hold_last`) | ✅ **PROVEN** — both directly observed in run 556 (§0f) |
| EXTLINK-07 | Liveness independent of signal staleness, as a directed test | ⬛ **UNPROVEN** — not exercised as originally planned this session (see §3 row 3's note; the observed alive flips were egress-driven, not signal-staleness-driven) |
| EXTLINK-08 | Malformed input dropped, no traceback | ⬛ **UNPROVEN** — not exercised this session |
| EXTLINK-13 | Readiness gate, three exits | ✅ **PROVEN (proceed exit only, directly observed, run 556 §0g)** — `EXTLINK_SKIP_WAIT` and the timeout-abort exit were NOT exercised and remain UNPROVEN |
| EXTLINK-14 | `sub_connect` end-to-end via a live PUB + `@decoder` | ⬛ **UNPROVEN** — deliberate scope decision, no `sub_connect` fixture remains (§0a) |
| EXTLINK-15 | Egress under real conditions: failure detection, threshold trip, recovery | ✅ **PROVEN** — proven more thoroughly than the plan's own test called for (§0d); FDA timing visibly unaffected throughout |
| EXTLINK-16 | Lifecycle hooks on all three teardown paths | ✅ **PROVEN (normal-completion / clean-stop path only)** — four clean stops across runs 552/554/555/556, no stranded lease. STOP-button-mid-run and induced-task-exception paths were NOT exercised and remain UNPROVEN as those specific sub-cases |
| EXTLINK-17 | Lease from a genuine pilot disconnect + force-release + `device_held` | ⬛ **UNPROVEN** — not exercised this session |
| EXTLINK-18 (happy) | Control-only module, no socket, participates in gate | ⬛ **UNPROVEN** — deliberate scope decision, no `role:"none"` fixture remains (§0a) |
| EXTLINK-18 (unhappy) | Same module without liveness override fails at construction | ⬛ **UNPROVEN** — same reason (§0a) |
| EXTLINK-19 | Signal-gated transition authored in the browser picker, saved, round-tripped, and fires at runtime | ⚠ **SPLIT VERDICT.** Runtime execution of a signal-gated transition — ✅ PROVEN (fired repeatedly across three successful runs, both the `>0.5`/`<0.2` pair). Authoring it via the FDA editor's picker in the browser — ⬛ UNPROVEN this session; the two transitions on task def 434 were authored via the API by the coordinator, not the picker (§0). Plan 18-14's UI itself was not clicked |
| EXTLINK-20 | Hand driver from a non-Pi machine + ~60Hz soak | ⚠ **SPLIT VERDICT.** Hand-driving the FDA from a real Mac laptop over Wi-Fi — ✅ PROVEN (runs 554/556). The mandated ~60Hz soak — ⬛ UNPROVEN, not run this session |
| — | `@command ping` | ⬛ **UNPROVEN** — never sent in any of the six runs (§0f) |
| — | Pi test suite (standing gap since Phase 24) | ⬛ **UNPROVEN** — not exercised this session |
| — | TEARDOWN — demo fixtures removed, real preflight clean | ⛔ **DEFERRED** — user chose to keep the demo lib. Exact reversing commands are ready in §3 whenever the decision changes |
| — | Transition-condition operand validation gap (§0c) | documented, not a pass/fail row |
| — | `condition_tree` bare-literal shape trap (§0c, §6 item 4) | documented, not a pass/fail row |

**Residual risk (restate regardless of outcome above):** Phase 18's lease safety net releases the
lease row and lets the run be marked errored, but does **not** command the foreign device to
stop. A crashed pilot can leave an external recorder running until a human notices. Phase 26
decides whether OpenEphys needs its own additional reconciliation.

---

## 6. Other findings (all coordinator-verified this session)

| # | Finding | Status | Commit / evidence |
|---|---|---|---|
| 1 | Hardware-lib test leak: two tests in `api/tests/test_hardware_libs_extlink.py` POSTed a lib per run and never deleted it, against the dev DB; 51 orphan rows accumulated, burying the 9 real libs | ✅ FIXED | `84612af`, verified stable across two consecutive full-suite runs |
| 2 | `delete_hardware_lib` guards toolkit links but NOT `hardware_modules` references — returns a raw psycopg2 `ForeignKeyViolation` as a 500 instead of a clean 409 | ⛔ NOT FIXED | known defect, out of this plan's scope |
| 3 | Save-gate gap: `validate_condition_operands` ignores every `{"view": ...}` operand by design; `extlink_keys` is wired only into `validate_compute_variables`. An unknown extlink key in a transition condition saves 200 and silently never fires | ⛔ NOT FIXED | verified by probe (scratch task defs 478/479, both deleted); §0c |
| 4 | The runtime condition shape is `condition_tree` with a bare literal on the right, NOT `condition` with `{"const": ...}`. The save gate accepts the wrong shape silently too — a second, independent way to author a transition that saves clean and never fires | ⛔ NOT FIXED | documented as a trap; §0c |
| 5 | `tools/extlink_driver/README.md` documented the stale source-id `dlc_cam1` in 6 places; a DEALER using it is dropped by the ROUTER. Run 553's failure is partly attributable to a stale Mac copy predating this fix | ✅ FIXED | `7dbdf3d` |
| 6 | The command sheet's standalone step-1 probe is invalid by construction: the ROUTER binds inside `init_hardware()` at RUN start, so a probe with no run in progress reports PASS against a port with no listener | documented | not a defect, a command-sheet correction |
| 7 | Toolkit 100 held dangling `hardware_module_ids` (59/60/61) pointing at deleted modules; the API permitted it | ✅ REPOINTED | repointed to 62 |
| 8 | `demo.alive` is double-logged (two identical `Boolean_Tracker` events per change, same millisecond) in every run — harmless for correctness, doubles ES volume for that key | unexplained | logged for awareness, not chased further |
| 9 | `stale_ms 3000` vs a ~1.5s sweep cadence makes `alive` marginal; usable as a gate (sampled once at entry) but would chatter as a transition condition | documented | design note, not a defect |
| 10 | Task def 434 has no terminal state by design — it cycles forever until stopped manually | documented | not a defect |

---

*Phase: 18-extlink-pi-transport*
*Prepared: 2026-08-09. Rewritten a final time after the six-run rig session (Tasks 1-2 prepared
the fixtures and command sheet; the checkpoint (Task 3) ran six times; this revision (Task 4)
records the final verdicts, root-caused both failures, retracted two earlier wrong claims, and
left teardown deferred per the user's own decision).*
