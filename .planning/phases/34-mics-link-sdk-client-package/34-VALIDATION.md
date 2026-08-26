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
| **Config file** | created by plan **34-01** — `[tool.pytest.ini_options]` in `sdk/pyproject.toml`, with `addopts = -q -m "not zmq_loopback"` so the default run stays socketless |
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

Task IDs below are `{plan}-T{n}` and resolve to concrete tasks in the PLAN.md files created
2026-08-26. Each row's automated command is carried into that task's `<verify>` block.

| Task ID | Plan | Wave | Requirement | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|-----------|-------------------|-------------|--------|
| 34-01-T3 | 34-01 | 1 | SDK-01 (local install) | packaging smoke | `rm -rf /tmp/mics_link_pkgcheck && python3 -m pip install --no-build-isolation --no-deps --target /tmp/mics_link_pkgcheck ./sdk && PYTHONPATH=/tmp/mics_link_pkgcheck python3 -c "import mics_link"` | ❌ W1 | ⬜ pending |
| 34-08-T3 | 34-08 | 5 | SDK-01 (git subdir + wheel) | packaging smoke | `cd sdk && python3 -m build --wheel && ls dist/*.whl` then `python3 -m pip install --no-deps "git+file:///home/ido/mics-backend#subdirectory=sdk" --target /tmp/mics_link_gitcheck && PYTHONPATH=/tmp/mics_link_gitcheck python3 -c "import mics_link"` | ❌ W5 | ⬜ pending |
| 34-01-T2 | 34-01 | 1 | SDK-02 | unit | `cd sdk && python3 -m pytest -q tests/test_wire_parity.py` | ❌ W1 | ⬜ pending |
| 34-02-T2 | 34-02 | 2 | SDK-03 | unit | `cd sdk && python3 -m pytest -q tests/test_transport_config.py` | ❌ W1 | ⬜ pending |
| 34-02-T1 | 34-02 | 2 | SDK-04 | unit | `cd sdk && python3 -m pytest -q tests/test_dtype_validation.py` | ❌ W1 | ⬜ pending |
| 34-03-T1 | 34-03 | 2 | SDK-05 | unit | `cd sdk && python3 -m pytest -q tests/test_heartbeat_scheduling.py` | ❌ W1 | ⬜ pending |
| 34-02-T3 | 34-02 | 2 | SDK-06 | unit | `cd sdk && python3 -m pytest -q tests/test_sender_bounded_drop.py` | ❌ W1 | ⬜ pending |
| 34-03-T2 | 34-03 | 2 | SDK-07 (state machine) | unit | `cd sdk && python3 -m pytest -q tests/test_reconnect_state_machine.py` | ❌ W1 | ⬜ pending |
| 34-06-T1 | 34-06 | 3 | SDK-07 (seq continuity over fake transport) | unit | `cd sdk && python3 -m pytest -q tests/test_client_integration.py` | ❌ W1 | ⬜ pending |
| 34-06-T3 | 34-06 | 3 | SDK-07 (real monitor, loopback only) | integration, opt-in | `cd sdk && python3 -m pytest -q -m zmq_loopback tests/test_zmq_loopback.py` | ❌ W1 | ⬜ pending |
| 34-04-T1 + 34-04-T2 | 34-04 | 2 | SDK-08 | unit (synthetic frames ONLY — see below) | `cd sdk && python3 -m pytest -q tests/test_command_dispatch.py` | ❌ W1 | ⬜ pending |
| 34-06-T2 | 34-06 | 3 | SDK-09 | unit | `cd sdk && python3 -m pytest -q tests/test_lifecycle.py` | ❌ W1 | ⬜ pending |
| 34-05-T1 + 34-05-T2 | 34-05 | 3 | SDK-10 | unit + AST hygiene | `test ! -f tools/extlink_driver/extlink_wire.py && python3 -m pytest -q tools/extlink_driver/` | ✅ existing (retarget) | ⬜ pending |
| 34-01-T3 | 34-01 | 1 | SDK-11 | AST hygiene | `cd sdk && python3 -m pytest -q tests/test_import_hygiene.py` | ❌ W1 | ⬜ pending |
| 34-07-T1 + 34-07-T2 | 34-07 | 4 | SDK-12 | unit | `cd sdk && python3 -m pytest -q tests/test_replay.py` | ❌ W1 | ⬜ pending |
| 34-08-T2 | 34-08 | 5 | SDK-13 | contract test + manual read-through | `cd sdk && python3 -m pytest -q tests/test_readme_contract.py` (ten-line bar, mandatory sections, device-neutrality) + a human read of `sdk/README.md` | ❌ W5 | ⬜ pending |
| 34-09-T2 | 34-09 | 6 | SDK-01 (foreign machine) | USER-RUN | N/A — checkpoint, see Manual-Only Verifications | N/A | ⬜ pending |
| 34-09-T3 | 34-09 | 6 | SDK-03/04/05/06/07 (rig) | USER-RUN | N/A — checkpoint, see Manual-Only Verifications | N/A | ⬜ pending |
| 34-09-T4 | 34-09 | 6 | all — evidence recording | doc + full suite | `cd sdk && python3 -m pytest -q && python3 -m pytest -q tools/extlink_driver/` | ❌ W6 | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

**Wave 0 note:** the original draft assumed a separate Wave 0. There is none — plan **34-01
(Wave 1)** IS the wave-0 deliverable: it creates `sdk/pyproject.toml`, the package skeleton, the
`tests/` root, `tests/pi_reference.py`, `tests/golden_frames.py` + its generator, and the pytest
config. `tests/fake_transport.py` is created by plan **34-02** (Wave 2) alongside the seam it
substitutes, because it must implement that seam's exact interface.

**Sampling continuity:** every requirement except SDK-13's read-through half has an automated
command, and no three consecutive tasks in any plan lack an `<automated>` verify. The only
manual-only offline item is the README read-through (34-08), and it sits beside an automated
contract test in the same plan.

**SDK-08 evidence caveat, restated here so it cannot be lost:** the automated command above proves
SDK-08 with **synthetic CMD frames built by the Pi's own `encode()`**. It is NOT a live Pi-initiated
round trip, because no Pi-side CMD sender exists anywhere in either autopilot tree. Plan 34-09 must
record this in `34-HARDWARE-VALIDATION.md`, and `/gsd:verify-work` must not be told SDK-08 was
rig-proven.

---

## Wave 0 Requirements (delivered by plan 34-01, Wave 1)

- [ ] `sdk/pyproject.toml` — build metadata, `src/` layout, setuptools backend, `requires-python
      >=3.8`, deps pinned to exactly `pyzmq` + `msgpack`
- [ ] `sdk/src/mics_link/` — package skeleton
- [ ] `sdk/tests/` — test package root
- [ ] `sdk/tests/fake_transport.py` — the in-memory seam substitute every non-codec test depends on
- [ ] `sdk/tests/golden_frames.py` — frozen corpus + the generation script that produced it
- [ ] **Pin the canonical golden-corpus reference path BEFORE writing `test_wire_parity.py`,
      not after.** Per direct user direction (2026-08-26, *"we are working on mics_core"*):
      **primary = `~/mics_core/autopilot/autopilot/hardware/external_hardware_wire.py`**, with
      `~/pi-mirror/...` kept as a skip-if-absent secondary drift check. The two are byte-identical
      today, so this fixes which path the test pins, not the corpus bytes. Note this **reverses**
      the original research recommendation, which had pinned pi-mirror on the basis of pilot 1's
      stack — see the reconfirmation row under Manual-Only Verifications.
- [ ] Framework install: `python3 -m pip install pyzmq msgpack pytest build` in whatever
      environment runs `sdk/`'s tests (separate from the Docker api environment)

---

## Manual-Only Verifications

### Preconditions — both must be satisfied BEFORE any rig row below

**P1 — the standing egress listener.** The `ExtlinkDemo` fixture Phase 18 deliberately left
standing requires a TCP echo listener on the dev host at `132.77.73.125:5597`. Without it,
`demo.alive` flips false ~3s into a run after three egress-probe failures and the readiness gate
times out — silently sabotaging every liveness observation here. See `18-HARDWARE-VALIDATION.md`
§0d/§3.

> ⚠ **That listener is NOT the orchestrator.** It was verified live as a standalone throwaway
> script (`scratchpad/egress_listener.py`, running since the Phase 18 session on 2026-08-09). The
> orchestrator is a separate process on `MSGPORT 5560`. If the listener ever needs restarting,
> restarting or killing the orchestrator is **not** the fix and would be a damaging misstep.

**P2 — reconfirm pilot 1's stack before trusting any rig result.** The record that pilot 1
(`132.77.72.28`, this phase's checkpoint target) still runs the old `pi-mirror` stack dates from
2026-08-17 — nine days stale as of this phase. If pilot 1 has not in fact migrated to `mics_core`,
the checkpoint exercises `pi-mirror`'s runtime regardless of which file the golden corpus is
pinned against. **USER-RUN** — only the user may inspect the Pi. Do not assume either state.

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| Reconfirm pilot 1's platform (P2) | — (evidence scoping) | Only the user may touch the Pi | State whether pilot 1 (`132.77.72.28`) runs `pi-mirror` or `mics_core` today. Reading over SSH is fine; the agent runs nothing on the Pi. Report: which stack |
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
