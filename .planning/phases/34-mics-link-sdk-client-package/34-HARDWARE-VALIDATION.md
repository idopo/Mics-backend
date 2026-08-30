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

## 3. Results

| # | Observation | Requirement | RESULT |
|---|---|---|---|
| A | Transition — FDA cycles `wait -> armed -> fired -> wait` | success criterion 3 | ⬜ pending |
| B | Quiet — `demo.alive` stays true 20s while `demo.left_paw_x` goes stale | success criterion 5 (SDK-05) | ⬜ pending |
| C | Soak — pilot stays up, FDA keeps transitioning, `stats.dropped` reported, ES keeps up | success criterion 12 (SDK-06) | ⬜ pending |
| D | Reconnect — sender survives a pilot restart without being restarted, `seq` climbs across it | success criterion 6 (SDK-07) | ⬜ pending |
| P1 | TCP echo listener state on `132.77.73.125:5597` | precondition | ⬜ pending |
| P2 | Pilot 1's confirmed platform (`pi-mirror` / `mics_core`) | precondition | ⬜ pending |
| Install | Foreign-machine install — dependency list, import works | SDK-01 | ✅ PASS (2026-08-30, Windows box `YizharGPU12`) |
| SDK-14 | Windows install — env used, pip's full output, `pip check`, selfcheck, Python version | SDK-14 | ✅ PASS (2026-08-30) — `windows_smoke.py` 7/7, see §3a |
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

---

## 3a. SDK-14 Windows checkpoint — PASSED 2026-08-30

Run by the user on the lab Windows box, in a dedicated conda env, verbatim:

```
(mics-link) C:\MICS>python windows_smoke.py
sys.executable: C:\Users\YizharGPU12\.conda\envs\mics-link\python.exe
sys.version: 3.11.16 | packaged by conda-forge | (main, Aug 21 2026, 22:37:11) [MSC v.1944 64 bit (AMD64)]
platform.platform(): Windows-10-10.0.19044-SP0
[PASS] interpreter + platform report

mics_link.__version__: 0.1.0, __file__: C:\Users\YizharGPU12\.conda\envs\mics-link\Lib\site-packages\mics_link\__init__.py
[PASS] import mics_link

pyzmq version: 27.2.0
msgpack version: 1.2.2
[PASS] numpy not required -- numpy is not in sys.modules
[PASS] mics-link declares no numpy dependency
[PASS] dependency closure

[PASS] mics_link.selfcheck.selfcheck() -- OK

[PASS] wire parity: SIG
[PASS] wire parity: EVT
[PASS] wire parity: HB

[PASS] loopback round trip -- pyzmq send/receive over tcp://127.0.0.1 works

[PASS] replay smoke -- sent 2 row(s) via mics_link.replay.replay

SUMMARY: 7/7 steps passed
```

**Environment:** Windows 10 (10.0.19044), Python 3.11.16 conda-forge, conda env `mics-link`,
pyzmq 27.2.0, msgpack 1.2.2. Installed from the `py3-none-any` wheel copied off
`\\isi.storwis.weizmann.ac.il\labs\yizharlab\Mics\sdk`.

### What this PROVES on Windows
- The wheel installs and imports on Windows with no compilation step (`py3-none-any` holds).
- Byte-exact wire parity against the frozen golden corpus holds on Windows — SIG, EVT, HB.
- `selfcheck()` passes: msgpack is unpatched in that env, so emitted frames are not numpy-extended.
- A real pyzmq `tcp://127.0.0.1` bind + round trip works — no firewall block, no `ipc://` dependency.
- The replay path runs in-process.
- No POSIX-only API (`fork`, `SIGALRM`, `fcntl`, `termios`, `getuid`) is reached on the import or
  send paths, since none exist on Windows and the run completed.

### What this does NOT prove — still open
- **The dependency no-op claim (SDK-01 as amended) is UNTESTED.** This was a fresh env, so pip
  installed pyzmq 27.2.0 and msgpack 1.2.2 from scratch — the correct result for an empty env, but
  it exercises nothing. The actual requirement is that installing into an environment that ALREADY
  has pyzmq/msgpack upgrades neither. That can only be tested in the real DLC env
  (the inspected example carried Python 3.8.19 / pyzmq 22.3.0 / msgpack 1.0.3).
- **`msgpack-numpy` was absent** from this env, so the selfcheck's failure path was not exercised
  here — only its success path. The DLC env is where that guard actually earns its place.
- **Legacy console codepage was not stressed.** The output is ASCII-only by construction and the
  library's four non-ASCII runtime messages were fixed (commit `f26d888`), but this console did not
  force a `cp437` failure, and no error message was actually printed during a passing run.
- **`mics-link-replay` console-script PATH resolution (SDK-14e) is untested** — `windows_smoke.py`
  calls `replay()` in-process, never via the console entry point in `<env>\Scripts\`.
- **Nothing here touched a Pi.** Observations A-D remain pending.

### Defect found by this run
The script's closing line was hardcoded to `"This is a LINUX run..."` and therefore printed a false
platform claim on Windows — visible in the user's output above, which reads `LINUX` on a Windows 10
box. Left unfixed it would have entered this very document as false evidence. Now derived from
`platform.system()`; on Windows it reads `"This is a WINDOWS run -- the SDK-14 cross-OS checkpoint
itself."` Both branches verified against a real install.
