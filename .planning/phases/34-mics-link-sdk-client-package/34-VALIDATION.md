---
phase: 34
slug: mics-link-sdk-client-package
status: draft
nyquist_compliant: false
wave_0_complete: false
created: 2026-08-26
---

# Phase 34 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.
> Derived from `34-RESEARCH.md` § Validation Architecture.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest — `sdk/` gets its own self-contained, socketless test run, independent of the Docker `api` suite (`docker compose exec -T api python -m pytest -q tests/`) |
| **Config file** | none yet — Wave 0 creates `[tool.pytest.ini_options]` in `sdk/pyproject.toml` |
| **Quick run command** | `cd sdk && python3 -m pytest -q` |
| **Full suite command** | `cd sdk && python3 -m pytest -q && python3 -m pytest -q tools/extlink_driver/` |
| **Estimated runtime** | ~5 seconds (whole suite is offline; no socket, no network, no rig) |

**Environment note:** the `sdk/` suite runs on the dev host directly, NOT in the api container.
It needs `pyzmq msgpack pytest build` available to whatever interpreter runs it. The rig
checkpoint is a separate, non-pytest, USER-RUN activity — it is never an automated command.

---

## Sampling Rate

- **After every task commit:** Run `cd sdk && python3 -m pytest -q` (whole suite — small and
  fully offline, no reason to subset)
- **After every plan wave:** Run the full suite command above, including the retargeted driver
  tests
- **Before `/gsd:verify-work`:** Full offline suite green, THEN the USER-RUN rig checklist
- **Max feedback latency:** ~5 seconds

---

## Per-Task Verification Map

Task IDs are assigned at plan time. This map is keyed by requirement; the planner MUST attach
each row to a concrete task ID and carry the automated command into that task's `<verify>` block.

| Task ID | Plan | Wave | Requirement | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|-----------|-------------------|-------------|--------|
| TBD | TBD | 0 | SDK-01 | packaging smoke | `pip install "git+file://$(pwd)#subdirectory=sdk" --target /tmp/mics_link_check && python3 -c "import mics_link"` | ❌ W0 | ⬜ pending |
| TBD | TBD | 1 | SDK-02 | unit | `cd sdk && python3 -m pytest -q tests/test_wire_parity.py` | ❌ W0 | ⬜ pending |
| TBD | TBD | 1 | SDK-03 | unit | `cd sdk && python3 -m pytest -q tests/test_transport_config.py` | ❌ W0 | ⬜ pending |
| TBD | TBD | 1 | SDK-04 | unit | `cd sdk && python3 -m pytest -q tests/test_dtype_validation.py` | ❌ W0 | ⬜ pending |
| TBD | TBD | 2 | SDK-05 | unit | `cd sdk && python3 -m pytest -q tests/test_heartbeat_scheduling.py` | ❌ W0 | ⬜ pending |
| TBD | TBD | 2 | SDK-06 | unit | `cd sdk && python3 -m pytest -q tests/test_sender_bounded_drop.py` | ❌ W0 | ⬜ pending |
| TBD | TBD | 2 | SDK-07 | unit | `cd sdk && python3 -m pytest -q tests/test_reconnect_state_machine.py` | ❌ W0 | ⬜ pending |
| TBD | TBD | 2 | SDK-08 | unit | `cd sdk && python3 -m pytest -q tests/test_command_dispatch.py` | ❌ W0 | ⬜ pending |
| TBD | TBD | 2 | SDK-09 | unit | `cd sdk && python3 -m pytest -q tests/test_lifecycle.py` | ❌ W0 | ⬜ pending |
| TBD | TBD | 3 | SDK-10 | unit + AST hygiene | `python3 -m pytest -q tools/extlink_driver/` | ✅ existing (retarget) | ⬜ pending |
| TBD | TBD | 1 | SDK-11 | AST hygiene | `cd sdk && python3 -m pytest -q tests/test_import_hygiene.py` | ❌ W0 | ⬜ pending |
| TBD | TBD | 3 | SDK-12 | unit | `cd sdk && python3 -m pytest -q tests/test_replay.py` | ❌ W0 | ⬜ pending |
| TBD | TBD | 3 | SDK-13 | manual review | N/A — checklist item in the plan's own review pass | N/A | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

**Sampling continuity:** every requirement except SDK-13 has an automated command. SDK-13
(README completeness) is inherently a read-through; it is the only manual-only offline item and
it does not create three consecutive unautomated tasks.

---

## Wave 0 Requirements

- [ ] `sdk/pyproject.toml` — build metadata, `src/` layout, setuptools backend, `requires-python
      >=3.8`, deps pinned to exactly `pyzmq` + `msgpack`
- [ ] `sdk/src/mics_link/` — package skeleton
- [ ] `sdk/tests/` — test package root
- [ ] `sdk/tests/fake_transport.py` — the in-memory seam substitute every non-codec test depends on
- [ ] `sdk/tests/golden_frames.py` — frozen corpus + the generation script that produced it
- [ ] **Decide and document the canonical golden-corpus reference path BEFORE writing
      `test_wire_parity.py`, not after.** Research recommends
      `~/pi-mirror/autopilot/autopilot/hardware/external_hardware_wire.py` — pilot 1
      (`132.77.72.28`, this phase's own rig target) is confirmed still on the old pi-mirror
      stack, and the existing driver test already sets that precedent. Keep `~/mics_core/...`
      as a skip-if-absent secondary drift check.
- [ ] Framework install: `python3 -m pip install pyzmq msgpack pytest build` in whatever
      environment runs `sdk/`'s tests (separate from the Docker api environment)

---

## Manual-Only Verifications

**Precondition — must be satisfied BEFORE any rig row below.** The `ExtlinkDemo` fixture Phase 18
deliberately left standing requires a TCP echo listener on the dev host at `132.77.73.125:5597`.
Without it, `demo.alive` flips false ~3s into a run after three egress-probe failures and the
readiness gate times out — which will silently sabotage every liveness observation here. See
`18-HARDWARE-VALIDATION.md` §0d/§3.

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| Install on a genuinely foreign machine | SDK-01 | Needs a host that has never seen MICS; dev host cannot prove it | `pip install "git+https://github.com/idopo/Mics-backend.git#subdirectory=sdk"` on a non-dev-host machine (or a fresh venv standing in), then `python3 -c "import mics_link"`. Report: install succeeds, only `pyzmq`+`msgpack` pulled in, import works |
| Ten-line sender drives a real FDA transition | SDK-03/04/06/07 + success criterion 3 | Requires the live rig and ES | Agent supplies a ten-line script targeting pilot 1 (`--pi-host 132.77.72.28`, port 5599, `source_id: demo`, against `extlink_demo` task def 434). Report: `wait→armed→fired→wait` visible in ES |
| Soak at the arc's real rate | SDK-06 + success criterion 12 | Requires the live rig, real session length | Agent supplies a rate/duration invocation mirroring `extlink_driver.py --rate`. Report: pilot stays up, FDA keeps transitioning, drop counter reported, ES ingestion keeps up. **No latency number is printed or claimed** (Phase 28) |
| Heartbeat keeps a quiet source alive | SDK-05 | Requires observing `demo.alive` on the rig | User runs the sender, sends nothing for >3× the fixture's `stale_ms` (3000ms). Report: `demo.alive` stays true throughout while individual signals go stale under their own policy |
| Pi restart mid-session | SDK-07 | Only the USER may restart the pilot process | User restarts the pilot while the sender keeps running. Report: `on_state_change` logs disconnect then reconnect, sending resumes with no sender restart, `seq` keeps climbing rather than resetting |

### ⚠ Explicitly NOT rig-testable this phase

**SDK-08 (inbound CMD → ACK) has no live counterpart.** Research grepped both autopilot trees and
found **zero** implementation of Pi-side `CMD` sending or `ACK` receiving anywhere outside the wire
codec module. There is no Pi-initiated round trip to test against on the rig today. SDK-08 is
therefore proven **only by synthetic-frame unit tests** this phase. This is a real, permanent
limitation of the phase's evidence — it must be stated in the phase's verification log rather than
papered over, and `/gsd:verify-work` must not be told SDK-08 was rig-proven.

---

## Validation Sign-Off

- [ ] All tasks have `<automated>` verify or Wave 0 dependencies
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify
- [ ] Wave 0 covers all MISSING references
- [ ] No watch-mode flags
- [ ] Feedback latency < 10s
- [ ] Canonical golden-corpus path decided and written into the parity test
- [ ] SDK-08's synthetic-only evidence explicitly recorded, not implied as rig-proven
- [ ] `nyquist_compliant: true` set in frontmatter

**Approval:** pending
