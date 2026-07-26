---
phase: 24
slug: trigger-assignment-action-lists
status: approved
nyquist_compliant: true
wave_0_complete: true  # test creation is embedded per-task (TDD) in plans 01-04
created: 2026-07-26
---

# Phase 24 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.
> Derived from `24-RESEARCH.md` → "Validation Architecture".

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework (Pi)** | pytest — no `pytest.ini` / `conftest.py`; tests import `autopilot.tasks.mics_task` against `MagicMock` fake task instances (no hardware needed) |
| **Framework (backend)** | pytest + `fastapi.testclient.TestClient`; existing `api/tests/test_toolkits_router.py` is smoke-level only (38 lines) |
| **Framework (React)** | **none detected** in `web_ui/react-src/package.json` — no Vitest/Jest. UI verification is manual + `tsc --noEmit` |
| **Config file** | none in either `~/pi-mirror/tests/` or `api/tests/` — not a blocker |
| **Quick run (Pi, agent)** | `cd ~/pi-mirror && python3 -m pytest tests/test_fda_vocabulary.py -q` + `python3 -m py_compile <file>` |
| **Quick run (Pi, user)** | `cd ~/pi-mirror && python3 -m pytest tests/test_trigger_assignments.py -q` |
| **Quick run (backend)** | `cd /home/ido/mics-backend/api && python3 -m pytest tests/ -q` |
| **Quick run (React)** | `cd web_ui/react-src && npx tsc --noEmit` |
| **Full suite (Pi)** | `cd ~/pi-mirror && python3 -m pytest tests/ -q` |
| **Full suite (backend)** | `cd /home/ido/mics-backend/api && python3 -m pytest tests/ -q` |
| **Estimated runtime** | < 30 s per suite |

**Pi caveat — CONFIRMED during planning (2026-07-26):** `autopilot` is **NOT** importable on this dev
host. `from autopilot.tasks.mics_task import mics_task` fails on missing `npyscreen` / `board` /
`busio` / `PySide2` / `pigpio`, and installing them is a rabbit hole (CircuitPython Blinka needs real
Pi hardware detection). Therefore:
- `tests/test_trigger_assignments.py`, `tests/test_load_fda_from_json.py`, `tests/test_validate_fda.py`
  are **USER-RUN**.
- Agent-runnable Pi checks are `python3 -m py_compile <file>` **and** `pytest tests/test_fda_vocabulary.py`
  — Plan 01 creates `autopilot/autopilot/tasks/fda_vocabulary.py` as a deliberately stdlib-only module
  imported by the test via `importlib.util.spec_from_file_location`, so the pure helpers
  (`resolve_key_template`, `unpack_output`) and the vocabulary constants get real automated feedback.

**Backend — CONFIRMED runnable by the agent:** neither the host nor the `mics_api` container ships
pytest. Plan 02 Task 1 adds `pytest` + `httpx` to `api/requirements.txt` and installs them into the
running container. Verified command: `docker exec -w /app mics_api python -m pytest tests/ -q`
(4 existing tests pass).

**React — no test runner.** No Vitest/Jest in `web_ui/react-src/package.json`. Verification is
`npx tsc --noEmit` + `npm run build` + the Plan 07 manual checkpoints.

---

## Sampling Rate

- **After every task commit:** Pi — `py_compile` the touched file(s) (agent-run, established workflow). Backend — the relevant `pytest -k` slice. React — `tsc --noEmit`.
- **After every plan wave:** full `api/tests/` (agent-run); Pi `tests/test_trigger_assignments.py` + `tests/test_load_fda_from_json.py` (user-run if import fails locally).
- **Before `/gsd:verify-work`:** backend suite green, Pi `py_compile` clean, `tsc --noEmit` clean.
- **Max feedback latency:** ~30 s.

---

## Per-Task Verification Map

| Req | Behavior | Test Type | Automated Command | File Exists |
|-----|----------|-----------|-------------------|-------------|
| TRIGA-01 | `actions` list built via `_build_action_callable`; same load-time `ValueError` on bad type/ref | unit (Pi) | `pytest tests/test_trigger_assignments.py -k actions -q` | ❌ W0 |
| TRIGA-02 | Composed callable declares `level`/`tick`; `{"trigger":…}` resolves via `_resolve_arg` | unit (Pi) | `pytest tests/test_trigger_assignments.py -k trigger_context -q` | ❌ W0 |
| TRIGA-03 | `view` action writes `self.view.view[key]`, accepts `pi_timestamp` | unit (Pi) | `pytest tests/test_trigger_assignments.py -k view_action -q` | ❌ W0 |
| TRIGA-04 | `output` capture (single name + list-unpack for tuple returns) | unit (Pi) | `pytest tests/test_load_fda_from_json.py -k variables -q` | ❌ W0 |
| TRIGA-05 | `detectedLick` equivalence: `(idx, level)` → `LICKER{idx}.set(level, pi_timestamp=tick)` | unit (Pi) | `pytest tests/test_trigger_assignments.py -k detect_lick -q` | ❌ W0 |
| TRIGA-06 | Backward compat: every existing test in `test_trigger_assignments.py` still passes **unmodified**, except the one asserting the wrong `detect_change` contract (see below) | unit (Pi) | `pytest tests/test_trigger_assignments.py -q` | ✅ exists (346 lines) |
| TRIGA-07 | PUT/POST with invalid `trigger_assignments` → **422** | unit (backend) | `pytest tests/test_task_definitions_validation.py -k trigger -q` | ❌ W0 |
| TRIGA-08 | `scan_fda_for_refs` includes trigger action refs | unit (backend) | `pytest tests/test_fda_utils.py -q` | ❌ W0 |
| TRIGA-09 | Trigger panel hosts `ActionEditor` per action | manual + typecheck | `npx tsc --noEmit` + visual check | n/a |
| TRIGA-10 | Backend 422 fires on an action/handler type React shouldn't have sent | unit (backend) | covered by TRIGA-07 file | ❌ W0 |
| TRIGA-11 | **Rig proof** — lick detection via UI action list, no `detectedLick` on the class | manual (hardware) | user-run session on the real pilot | n/a |

*Status legend: ⬜ pending · ✅ green · ❌ red · W0 = created in Wave 0*

---

## Wave 0 Requirements

- [ ] `~/pi-mirror/tests/test_trigger_assignments.py` — **extend** with the `actions` branch, `view` action, `output` capture, `{"trigger":…}` resolution, and a `detectedLick`-equivalence test. Do not delete existing tests (TRIGA-06).
- [ ] `~/pi-mirror/tests/test_trigger_assignments.py:317-345` — **correct** `test_apply_trigger_assignments_touch_detector_callback_updates_view`: its mock (`detect_change.return_value = [1, 0]`) encodes a contract the hardware never had. Real return is `(changed_index, new_value)` per `hardware/i2c.py:842`. **Fix the test and the handler — never `i2c.py`.**
- [ ] `~/pi-mirror/tests/test_load_fda_from_json.py` — extend with `variables` registry instantiation tests.
- [ ] `api/tests/test_fda_utils.py` — **new file**; `scan_fda_for_refs` has zero tests today.
- [ ] `api/tests/test_task_definitions_validation.py` — **new file**; hard-422 trigger validation.

---

## Manual-Only Verifications

| Behavior | Req | Why Manual | Test Instructions |
|----------|-----|------------|-------------------|
| Trigger panel renders the shared `ActionEditor`; adding/removing/reordering actions round-trips through save | TRIGA-09 | No React test runner configured in `react-src` | Rebuild web_ui, open `/react/task-editor/:id`, add a trigger assignment with 2+ actions, save, reload, confirm identical |
| **Rig proof** — lick detection driven by a UI-assigned action list with `detectedLick` removed from the task class | TRIGA-11 | Requires real MPR121 + GPIO interrupt on the pilot. Project hard rule: agent never runs Python on the Pi, never starts/stops the pilot | Agent supplies commands; **user** syncs `~/pi-mirror/` → Pi, restarts the pilot, starts a session, touches each of the 4 electrodes, confirms `LICKER0…LICKER3` update correctly in the view / ES |
| Negative case — invalid assignment rejected at **save**, not at session start | TRIGA-11 | End-to-end across UI → API → DB | In the editor, set a bad `hardware_ref`, save, confirm a 422 with a message naming the offending assignment |

---

## Validation Sign-Off

- [x] All tasks have `<automated>` verify or a Wave 0 dependency
- [x] Sampling continuity: no 3 consecutive tasks without automated verify
- [x] Wave 0 covers all ❌ references above
- [x] No watch-mode flags
- [x] Feedback latency < 30 s
- [x] `nyquist_compliant: true` set in frontmatter

**Approval:** approved 2026-07-26 during `/gsd:plan-phase 24`.

**Where each Wave 0 item landed:**
| Wave 0 item | Plan / Task |
|---|---|
| `tests/test_fda_vocabulary.py` (new, agent-runnable) | 24-01 Task 1 |
| `tests/test_load_fda_from_json.py` — `variables` tests | 24-01 Task 2 |
| `tests/test_trigger_assignments.py` — `view` / `output` / `trigger_context` | 24-01 Task 3 |
| `tests/test_trigger_assignments.py` — `actions` branch tests | 24-04 Task 1 |
| `tests/test_trigger_assignments.py:317-345` — corrected `detect_change` contract | 24-04 Task 2 |
| `tests/test_validate_fda.py` — trigger action validation | 24-04 Task 3 |
| `api/tests/test_fda_utils.py` (new) | 24-02 Task 1 |
| `api/tests/test_task_definitions_validation.py` (new) | 24-02 Tasks 2 + 3 |
| pytest available to the agent at all | 24-02 Task 1 (api/requirements.txt) |
