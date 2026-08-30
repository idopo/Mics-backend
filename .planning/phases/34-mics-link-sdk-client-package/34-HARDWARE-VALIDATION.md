# Phase 34 — Hardware Validation Log (rig checkpoint, plan 34-09)

**Date opened:** 2026-08-30 (Task 1 skeleton — results not yet collected)

**Status:** SKELETON ONLY. Tasks 2-4 of `34-09-PLAN.md` are `checkpoint:human-action` /
`checkpoint:human-verify` gates requiring the user physically at the rig and at a Windows
machine — every row in §3 below is `⬜ pending` until the user runs the checks and reports
back. This document is modelled on
`.planning/phases/18-extlink-pi-transport/18-HARDWARE-VALIDATION.md`.

**Scope of this document:** what is PROVEN on hardware vs. what remains UNPROVEN/DEFERRED,
the exact commands for every USER-RUN row of `34-VALIDATION.md`'s Per-Task Verification Map,
and the exact system state (ids) this checkpoint depends on.

---

## 0. Preconditions

Two preconditions will silently sabotage this checkpoint if skipped. Both are USER-checked
in Task 2 before any rig run in Task 3.

### P1 — The TCP echo listener on `132.77.73.125:5597` must be up

`ExtlinkDemo`'s egress probe targets it. Without it, three failed probes at 1/s trip
`egress_fail_threshold: 3` and `demo.alive` flips FALSE roughly 3.0 seconds into every run —
which makes every liveness observation in this checkpoint garbage and makes the readiness
gate time out. This was diagnosed live in Phase 18 runs 553/555/556
(`18-HARDWARE-VALIDATION.md` §0d/§3).

> ⚠ **This listener is NOT the orchestrator.** It is a standalone throwaway script
> (`scratchpad/egress_listener.py`) that has been running on the dev host since the Phase 18
> session on 2026-08-09, bound to `0.0.0.0:5597`. The orchestrator is a different process on
> `MSGPORT` **5560**. Restarting, killing or "fixing" the orchestrator is NOT the remedy for
> a down listener and would be a damaging misstep. If 5597 is closed, start a plain TCP echo
> listener on that port and leave the orchestrator alone.

**Reported state:** ⬜ pending — not yet checked.
**If restarted, with what:** ⬜ pending.

### P2 — Pilot 1's platform must be RECONFIRMED, not assumed

The claim that pilot 1 (`132.77.72.28`) still runs the old `pi-mirror` stack is dated
2026-08-17 — stale relative to the user's 2026-08-26 direction that *"we are working on
mics_core"*. The golden corpus is pinned to
`~/mics_core/.../external_hardware_wire.py` (plan 34-01), but if pilot 1 has not migrated,
this checkpoint exercises `pi-mirror`'s runtime regardless of which file the corpus names.
The two files were byte-identical on 2026-08-26, so this is not expected to change any
outcome — but it changes what the evidence MEANS, and it must be stated, not assumed either
way.

**Reported platform:** ⬜ pending — `pi-mirror` / `mics_core` / other (user to state which).

---

## 1. Fixture inventory (already standing, nothing modified by this phase)

| Entity | id | Notes |
|---|---|---|
| Pilot (the rig) | 1 | `pilot_raspberry_lior`, ip `132.77.72.28` |
| Toolkit | 100 | shared with real task def 186 |
| Hardware module | 62 | `ExtlinkDemo` |
| Hardware lib | 177 | `extlink_demo.py` / `ExtlinkDemo` |
| `pilot_hardware_config` row | 21 | `{"class_name":"ExtlinkDemo","role":"router_bind","listen_port":5599,"host":"132.77.73.125","source_id":"demo","stale_ms":3000,"required":true,"wait_timeout_s":30,"egress_fail_threshold":3}` |
| Task definition | 434 | `extlink_demo` — `wait -> armed` on `demo.left_paw_x > 0.5`, `armed -> fired` on `demo.left_paw_x < 0.2`, `fired -> wait` unconditional, no terminal state |

**Nothing in this inventory is modified, deployed, torn down or restarted by this phase**
beyond the pilot restart the USER performs for the SDK-07 row (decision 4,
`34-09-PLAN.md`). Teardown of this fixture remains a separate, still-open user decision
(see `18-HARDWARE-VALIDATION.md` §3).

---

## 2. The exact commands (ready to copy)

**A. Transition (success criterion 3):**

    python3 sdk/examples/rig_checkpoint_sender.py --mode transition

**B. Quiet / heartbeat (success criterion 5, SDK-05):**

    python3 sdk/examples/rig_checkpoint_sender.py --mode quiet --seconds 20

**C. Soak at the arc's real rate (success criterion 12, SDK-06):**

    python3 sdk/examples/rig_checkpoint_sender.py --mode soak --rate 60 --seconds 30

**D. Pi restart mid-session (success criterion 6, SDK-07):**

    python3 sdk/examples/rig_checkpoint_sender.py --mode reconnect --seconds 120

**Foreign-machine install (Task 2 step 3):**

    pip install "git+https://github.com/idopo/Mics-backend.git#subdirectory=sdk"
    python3 -c "import mics_link; print(mics_link.__version__)"

**SDK-14 Windows install (into the user's chosen DLC-adjacent env, on the Windows box):**

    conda activate <THE ENV>
    python -m pip install https://github.com/idopo/Mics-backend/releases/download/sdk-v0.1.0/mics_link-0.1.0-py3-none-any.whl
    python -m mics_link.selfcheck
    python -m pip check

**SDK-14 Windows replay + rig send (Task 3 step E, with `extlink_demo` standing):**

    python -m mics_link.replay --host 132.77.72.28 --port 5599 --source-id demo ^
        --file C:\path with a space\replay_sample.csv --mode realtime

---

## 3. Results — all `⬜ pending`

| # | Observation | Requirement | RESULT |
|---|---|---|---|
| A | Transition — FDA cycles `wait -> armed -> fired -> wait` | success criterion 3 | ⬜ pending |
| B | Quiet — `demo.alive` stays true 20s while `demo.left_paw_x` goes stale | success criterion 5 (SDK-05) | ⬜ pending |
| C | Soak — pilot stays up, FDA keeps transitioning, `stats.dropped` reported, ES keeps up | success criterion 12 (SDK-06) | ⬜ pending |
| D | Reconnect — sender survives a pilot restart without being restarted, `seq` climbs across it | success criterion 6 (SDK-07) | ⬜ pending |
| P1 | TCP echo listener state on `132.77.73.125:5597` | precondition | ⬜ pending |
| P2 | Pilot 1's confirmed platform (`pi-mirror` / `mics_core`) | precondition | ⬜ pending |
| Install | Foreign-machine install — dependency list, import works | SDK-01 | ⬜ pending |
| SDK-14 | Windows install — env used, pip's full output, `pip check`, selfcheck, Python version | SDK-14 | ⬜ pending |
| SDK-14e | Windows replay + rig send — console command resolution, spaced path, ASCII summary, FDA cycle, Ctrl+C behaviour | SDK-14 | ⬜ pending |

---

## 4. PROVEN vs UNPROVEN/DEFERRED

**PROVEN (rig):** ⬜ pending — filled in from §3 once the user reports.

**PROVEN (offline only):** SDK-02 (wire parity), SDK-09 (lifecycle), SDK-11 (socketless
testability), SDK-10 (driver cutover / deletion), SDK-12 (replay), SDK-13 (README
contract) — see `34-VALIDATION.md`'s Per-Task Verification Map for the exact automated
command behind each.

**UNPROVEN — permanent limitation: SDK-08.** There is zero Pi-side `CMD`-send /
`ACK`-receive implementation anywhere in either autopilot tree — `cmd_id` and `"CMD"`
appear nowhere outside `external_hardware_wire.py` itself. There is no Pi-initiated round
trip to test against. SDK-08's evidence is synthetic-frame unit tests (plan 34-04,
`tests/test_command_dispatch.py`) and that is a REAL, PERMANENT limitation of this phase,
recorded as such. `/gsd:verify-work` must not be told SDK-08 was rig-proven.

**DEFERRED:** latency/jitter measurement (Phase 28), `sub_connect` support, PyPI
publication, stub generation, bootstrap-zip endpoints, the "Download SDK" GUI button, and
the fate of `extlink_driver_mac.zip`.

---

## 5. Findings the user reported that this phase does not fix

⬜ pending — populated verbatim from the user's Task 2/3 reports, findings only, never
silently absorbed (decision 5, `34-09-PLAN.md`).

---

*Phase: 34-mics-link-sdk-client-package*
*Prepared: 2026-08-30 (Task 1 — structure only). Tasks 2-4 (checkpoints + evidence
recording) are USER-RUN and remain open.*
