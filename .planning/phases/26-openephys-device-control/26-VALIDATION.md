---
phase: 26
slug: openephys-device-control
status: approved
nyquist_compliant: true
wave_0_complete: false
created: 2026-08-03
---

# Phase 26 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.
> Derived from `26-RESEARCH.md` § Validation Architecture. Read that section for rationale.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework (backend)** | pytest, inside the `api` docker container |
| **Framework (Pi mirror, agent-runnable)** | pytest — **only for files with ZERO `autopilot.*` imports** |
| **Framework (Pi, USER-RUN)** | pytest on the rig, for anything importing `autopilot.*` |
| **Config file** | none — **no new dependencies this phase** |
| **Quick run (backend)** | `docker compose exec api python -m pytest -q api/tests/test_openephys_client.py` |
| **Quick run (Pi mirror)** | `cd ~/pi-mirror && python3 -m pytest -q tests/test_openephys_markers.py` |
| **Full suite (backend)** | `docker compose exec api python -m pytest -q` |
| **Full suite (Pi)** | **USER-RUN**: `cd ~/Apps/mice_interactive_home_cage && python3 -m pytest tests/ -q` |
| **Estimated runtime** | backend ~30s; Pi-mirror units ~2s |

### No new dependencies (contrast with Phase 18)

`requests==2.27.1` is already pinned in `~/pi-mirror/environment.yml` and already imported elsewhere
on the Pi; `httpx` is already an `api/` dependency. **There is no user-run pip step in this phase** —
unlike Phase 18's msgpack gap.

### Hard constraint, inherited from Phase 18

`import autopilot.*` fails on the dev host (`npyscreen` missing). Any test touching the real
`OpenEphys` / `ExternalHardware` class is USER-RUN.

> **Design requirement:** keep OE REST call construction — URL building, payload shapes,
> mode-transition decisions, already-recording detection, folder-token resolution — in
> **`autopilot`-free** functions (`openephys_client.py` on the Pi side, mirroring
> `api/openephys_client.py` by name deliberately). The `ExternalHardware`-coupled glue (constructor,
> `.bind()`, egress wiring) stays USER-RUN. Without this split the REST logic is untestable by the
> agent, exactly as Phase 18 found for its wire/runtime code.

**⚠ Rebuild gotcha:** the `api` container has **no bind mount** — new test files are invisible to a
running container. Run `docker compose up --build api` before trusting a backend test result.
Re-verify this at plan time rather than assuming.

---

## Sampling Rate

- **After every task commit:** the specific test file touched
- **After every plan wave:** `docker compose exec api python -m pytest -q` (rebuild first) + every
  new `autopilot`-free Pi test file as a batch
- **Before `/gsd:verify-work`:** full backend suite green + agent-runnable Pi-mirror tests green +
  the single consolidated rig checkpoint confirmed by the user
- **Max feedback latency:** ~30s backend, ~2s Pi-mirror

---

## Per-Task Verification Map

Task IDs are assigned at planning. The contract below is **requirement → test**; every row must be
claimed by some task.

| Requirement | Behavior | Test Type | Automated Command | File Exists |
|---|---|---|---|---|
| EPHYS-01 | `set_mode(host, port, "RECORD")` issues `PUT /api/status` with body `{"mode":"RECORD"}` | unit (backend + Pi, mocked HTTP) | `docker compose exec api python -m pytest -q api/tests/test_openephys_client.py -k set_mode` | ❌ W0 |
| EPHYS-01 | A faked `GET /api/status` returning `{"mode":"RECORD"}` makes `on_run_start` **refuse without ever calling** `PUT /api/status` — proves "never take over" | unit (backend + Pi) | `... -k already_recording` | ❌ W0 |
| EPHYS-01 | Recording-config PUT body contains only real OE fields (`parent_directory`, `base_text`, `prepend_text`, `append_text`, `default_record_engine`, `start_new_directory`) — never an invented one | unit (backend + Pi) | `... -k recording_config_payload` | ❌ W0 |
| EPHYS-02 | Folder template resolves all tokens (`{project}/{experiment}/{subject}/{session}/{run}/{date}`) against a seeded fixture chain | unit (backend) | `docker compose exec api python -m pytest -q api/tests/test_artifact_path_resolution.py` | ❌ W0 |
| EPHYS-02 | A template containing an unknown token is **rejected at save with 422 naming the token** | unit (backend) | `... -k rejects_unknown_token` | ❌ W0 |
| EPHYS-02 | A subject in two projects resolves **deterministically and does not raise** — the locked "pick first, make it visible" rule | unit (backend) | `... -k ambiguous_project` | ❌ W0 |
| EPHYS-02 | Ambiguous resolution **emits a warning** and the chosen project/experiment is reported | unit (backend) | `... -k ambiguous_warns` | ❌ W0 |
| EPHYS-03 | New recording table migration is **idempotent** (run twice, same result) | unit (backend) | `docker compose exec api python -m pytest -q api/tests/ -k openephys_migration` — **confirm the existing migration-test filename first:** `grep -rl run_hardware_lib_kind_migration api/tests/` | ❌ W0 (extend) |
| EPHYS-03 | Resolved path + timestamps + host + project/experiment snapshot + coverage flag round-trip through the API | unit (backend) | `... -k recording_record_roundtrip` | ❌ W0 |
| EPHYS-03 | **Resolved path is READ BACK** from `GET /api/recording` (`experiment_number`/`recording_number`), never predicted | unit (backend + Pi, mocked HTTP) | `... -k resolved_path_read_back` | ❌ W0 |
| EPHYS-03 | Collision: a second run resolving to an already-recorded `resolved_path` surfaces the preflight issue instead of overwriting | unit (backend) | `... -k collision` | ❌ W0 |
| EPHYS-04 | `send_marker("reward", run=123, trial=45)` builds `{"text": "reward\|run=123\|trial=45"}` for `PUT /api/message` | unit (Pi mirror, agent) | `cd ~/pi-mirror && python3 -m pytest -q tests/test_openephys_markers.py -k payload` | ❌ W0 |
| EPHYS-04 | `send_marker()` **enqueues and returns immediately** — never blocks the caller | unit (Pi mirror, agent, fake egress) | `... -k enqueues_not_blocks` | ❌ W0 |
| EPHYS-04 | The dual-log fires **regardless of whether the HTTP send later succeeds** — the positive record survives total network failure | unit (Pi mirror, agent) | `... -k logged_regardless` | ❌ W0 |
| EPHYS-04 | Run-start and run-stop markers are emitted automatically, bracketing the recording | unit (Pi mirror, agent) | `... -k auto_brackets` | ❌ W0 |
| EPHYS-05 | A device unreachable surfaces a **device-neutral** `external_device_unreachable` issue carrying the device name — **not** an OE-specific kind, and not an unhandled 500 | unit (backend) | `docker compose exec api python -m pytest -q api/tests/test_toolkit_dispatch.py -k external_device` | ❌ W0 (extend) |
| **GENERIC** | The artifact table, path resolver, collision check, and preflight kinds contain **no Open Ephys knowledge** — asserted by a test that resolves a path and writes an artifact record for a fabricated non-OE device | unit (backend) | `docker compose exec api python -m pytest -q api/tests/test_artifact_path_resolution.py -k device_neutral` | ❌ W0 |
| EPHYS-05 | Already-recording surfaces its own distinct preflight issue | unit (backend) | `... -k already_recording_issue` | ❌ W0 (extend) |
| EPHYS-05 | New issue kinds are registered in `PREFLIGHT_ISSUE_KINDS` **and** mirrored in `HardwareCheckModal.tsx`'s `PreflightIssue` union | unit (backend) + read | `... -k issue_kinds_registered` | ❌ W0 (extend) |
| EPHYS-01/03 | Backend force-stop: reconciliation detecting an unclean run end issues the IDLE call **and** releases the lease | unit (backend, mocked HTTP) | `... -k force_stop` | ❌ W0 |
| EPHYS-01/02 | **`role: "none"` liveness contract (Phase 18 EXTLINK-07/18).** `OpenEphys` declares a class-level `liveness_hook`; absent, the module raises at construction rather than hanging the readiness gate. Asserted structurally on the **stored** lib source, so a drifted seed is caught here rather than on the rig | unit (backend, AST) | `docker compose exec api python -m pytest -q api/tests/test_seed_openephys.py -k liveness_hook` | ❌ **26-10** (wave 3, not W0 — nothing consumes it earlier) |
| EPHYS-01 | **Mid-run recording loss flips `alive`** (`26-CONTEXT.md` locked Bad-state decision). `liveness_hook` is composite: reachable AND, while a run is active, still in `RECORD`. A box that answers `GET /api/status` but has dropped out of RECORD must read `alive=false`, and the behavioural session must keep running | unit (Pi-mirror, pure `liveness_ok(status, run_active)`, fake status dicts) | `cd /home/ido/pi-mirror && python3 -m pytest -q tests/test_openephys_client.py -k liveness_ok` | ❌ W0 (26-02 contract) |
| EPHYS-01–05 | Consolidated rig checkpoint (see below), **including step 4a** — liveness vs readiness are genuinely distinct on real hardware, the outbound status poll flips `alive` when the box is powered off, STOP stays responsive while the poll hits an unreachable host (proving the poll is off the shared IOLoop), and the construction rule holds | manual + rig | USER-RUN | N/A |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

- [ ] `api/tests/test_openephys_client.py` — new — EPHYS-01, mocked HTTP
- [ ] `api/tests/test_artifact_path_resolution.py` — new — EPHYS-02 tokens + collision + ambiguity,
      **plus the device-neutrality assertion** (resolve a path and write an artifact record for a
      fabricated non-OE device, proving no Open Ephys knowledge leaked into the shared layer)
- [ ] Extend the existing DB-migration test file — EPHYS-03 migration idempotency.
      **Confirm the filename first:** `grep -rl run_hardware_lib_kind_migration api/tests/`
- [ ] `~/pi-mirror/tests/test_openephys_markers.py` — new, `autopilot`-free (fakes only) — EPHYS-04.
      **Depends on Phase 18's `EgressWorker`/`ExternalHardware` existing.** Phase 18 executes first
      in the roadmap order, so this should be satisfied — if not, this file covers marker-payload
      construction only and defers the enqueue-integration assertions.
- [ ] Extend `api/tests/test_toolkit_dispatch.py` — EPHYS-05 preflight issue kinds
- [ ] Extend `PREFLIGHT_ISSUE_KINDS` + `HardwareCheckModal.tsx`'s `PreflightIssue` union — always
      together, per the two-file rule established by Phase 23 plan 07
- [ ] Confirm whether `docker compose exec api` sees new test files without a rebuild — Phase 23's
      summaries indicate the `api` service has no bind mount. Verify, don't assume.

*No dependency installs required this phase.*

---

## Manual-Only Verifications

**One consolidated rig checkpoint.** Per the Pi operational rules the agent never runs git on the Pi,
never starts/stops the pilot, and never runs Python on the Pi — every item is a command handed to the
**user**. Do not schedule a second rig visit for this phase.

| Behavior | Requirement | Why Manual | Test Instructions |
|---|---|---|---|
| **OE REST surface confirmation** — do the documented endpoints/fields match this lab's actual OE version? | EPHYS-01/02 | Every field name here came from official docs fetched during research, never probed against the lab's instance | `curl` round-trip: `GET /api/status`, `GET`/`PUT /api/recording`. **Do this BEFORE path-construction code is finalized, not after** |
| **Directory-naming convention** — `Record Node 102` vs `Record_Node_102`, and how prepend/base/append compose | EPHYS-02/03 | Undocumented; a third-party source disagrees with the official docs' example | Inspect an actual recording folder on the OE machine |
| **`experiment_number`/`recording_number` behaviour across runs** | EPHYS-03 | Undocumented whether counters reset per directory change | Start two MICS-driven runs back to back; record both pairs |
| **Full `on_run_start`/`on_run_stop` through real teardown** with a real OE box | EPHYS-01 | Requires the real `pilot.py::run_task` loop and a live device | Normal completion, STOP, induced exception |
| **Backend force-stop from a genuinely crashed pilot** | EPHYS-01 | Unit test uses a fabricated stale timestamp; this proves the real path | Kill the pilot mid-run; confirm OE returns to IDLE and the lease releases |

### Explicitly NOT acceptance criteria for this phase

- **A marker actually landing inside a real OE recording.** Phase 26 proves the marker was *sent and
  logged*; proving it *landed* is Phase 28's TTL-vs-network measurement, by design.
- **`on_run_stop()` emitting a CONTINUOUS event visible in ES** — inherited from Phase 18;
  `event_dispatcher.stop()` races ahead of `task.end()`. Verify stop by effect (OE idle, lease
  released).
- **Collision with a folder created by hand in the OE GUI.** The REST API has no directory-listing
  endpoint, so the collision check is MICS-side only. This gap is accepted and documented, not tested.

---

## Validation Sign-Off

- [ ] All tasks have `<automated>` verify or a Wave 0 dependency
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify
- [ ] Wave 0 covers all ❌ references above
- [ ] The `autopilot`-free `openephys_client.py` split is honoured on the Pi side
- [ ] The REST-surface rig confirmation happens BEFORE path-construction code is finalized
- [ ] Every manual-only row lands in the single consolidated rig checkpoint
- [ ] No watch-mode flags
- [ ] Feedback latency < 30s
- [ ] `nyquist_compliant: true` set in frontmatter

**Approval:** approved at planning (2026-08-03) — 13 plans, 4 waves.

> **One deliberate deviation from the checklist above.** The *OE REST surface confirmation* row does
> NOT land in the single consolidated rig checkpoint. It is plan **26-03**, in wave 1, because it
> gates path-construction code (plans 26-06 / 26-07 / 26-10) — folding it into the end-of-phase
> session would invert that dependency. Every OTHER manual-only row is in the one consolidated
> checkpoint, plan **26-13**. Two user-facing rig/browser touchpoints exist in total: 26-03 (curl
> probe, no rig hardware beyond the OE box) and 26-13 (the rig session); plan 26-12 adds a browser
> confirmation that needs no rig at all.
