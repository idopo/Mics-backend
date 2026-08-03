---
phase: 23
slug: compute-primitives-variables
status: draft
nyquist_compliant: false
wave_0_complete: false
created: 2026-08-03
---

# Phase 23 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

**Note:** `CLAUDE.md` says "No automated test suite" — that is **stale**. Verified 2026-08-03:
`api/tests/` holds 7 test modules and `~/pi-mirror/tests/` holds 12. Extend these; do not create
parallel structures.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework (backend)** | pytest, run in the `api` container |
| **Framework (Pi)** | pytest — but `autopilot` is **unimportable on the dev host** (`npyscreen` missing). Only stdlib-only test files are agent-runnable; the rest are **USER-RUN on the Pi**. |
| **Framework (React)** | `tsc --noEmit` + `npm run build`; `node --test` for pure `.mts` modules (precedent: `src/components/detectorOptions.mts`, Phase 25-04) |
| **Config file** | none dedicated — existing `api/tests/`, `~/pi-mirror/tests/`, `web_ui/react-src/package.json` |
| **Quick run command** | `docker compose exec api python -m pytest -q api/tests/<touched>.py` |
| **Full suite command** | `docker compose exec api python -m pytest -q` + `cd web_ui/react-src && npx tsc --noEmit && npm run build` |
| **Estimated runtime** | ~30s backend, ~40s React build |

---

## Sampling Rate

- **After every task commit:** `docker compose exec api python -m pytest -q <touched test file>` (backend) · `cd ~/pi-mirror && python3 -m py_compile <touched file>` (Pi, syntax-only, agent-runnable) · `npx tsc --noEmit` (React)
- **After every plan wave:** full backend suite + `npm run build`. Pi suite is **USER-RUN**, requested explicitly at each Pi-touching wave boundary — never run silently by the agent.
- **Before `/gsd:verify-work`:** backend + React green, AND user has confirmed the Pi suite passed and the gonogo-translation fired both branches on the rig with **both** event types visible in ES.
- **Max feedback latency:** 40 seconds (agent-runnable portion)

---

## Per-Task Verification Map

Test targets **verified to exist** 2026-08-03 — extend these files, do not create duplicates.

| Requirement | Behavior | Test Type | Target File | Automated Command | Exists |
|---|---|---|---|---|---|
| CMP-01/02 | `variables` registry already built — verify only, no new code | unit (Pi) | `~/pi-mirror/tests/test_load_fda_from_json.py` | USER-RUN | ✅ |
| CMP-03 | `type:"compute"` dispatches + captures `output`; `output` **mandatory** (unlike `hardware`/`method`) | unit (Pi) | `~/pi-mirror/tests/test_load_fda_from_json.py` + `test_fda_vocabulary.py` (vocabulary is stdlib-only → agent-runnable) | `cd ~/pi-mirror && python3 -m pytest -q tests/test_fda_vocabulary.py` | ✅ |
| CMP-04 | Compute class subclasses `Hardware`, overrides `release()`, seed ops correct | unit (Pi) | new `~/pi-mirror/tests/test_compute_ops.py` | USER-RUN | ❌ **W0** |
| CMP-05 | Last-write-wins on state re-entry | unit (Pi) | `~/pi-mirror/tests/test_load_fda_from_json.py` | USER-RUN | ✅ |
| CMP-06 | Hot-reload re-creates variables before rebuilding transitions | unit (Pi) | `~/pi-mirror/tests/test_load_fda_from_json.py` | USER-RUN | ✅ |
| CMP-10 | Hard 422: undeclared `output`, name collision, undeclared variable ref | unit + route | `api/tests/test_task_definitions_validation.py` (already imports `validate_variables`) | `docker compose exec api python -m pytest -q api/tests/test_task_definitions_validation.py -k compute` | ✅ |
| CMP-11 | Ref scanner returns `compute` `output` names | unit | `api/tests/test_fda_utils.py` | `docker compose exec api python -m pytest -q api/tests/test_fda_utils.py` | ✅ |
| CMP-12 | `kind` column migration is idempotent (run twice, no error) | integration | new `api/tests/test_hardware_lib_kind.py` | `docker compose exec api python -m pytest -q api/tests/test_hardware_lib_kind.py` | ❌ **W0** |
| CMP-13/18 | Compute action row; `kind` filter chip | build + manual | `web_ui/react-src` | `npx tsc --noEmit && npm run build` | ✅ (manual click-through is the acceptance step) |
| CMP-14 | Operand dropdown already lists task `variables` — **verify only** (built in 24-08) | manual | — | click-through | ✅ |
| CMP-15 | `variable_never_written` preflight issue (v1 = existence check) | unit | `api/tests/test_view_key_preflight.py` (sibling of `view_key_unresolved`) | `docker compose exec api python -m pytest -q api/tests/test_view_key_preflight.py -k never_written` | ✅ |
| CMP-16 | **Both** events per compute call: `Hardware_Event` (op+args) **and** `Tracker` set (result) | unit (Pi) + rig | `~/pi-mirror/tests/test_log_action_values.py` | USER-RUN + ES query on rig | ✅ |
| CMP-17 | Resolution chain pin → toolkit default → **stable** → preflight issue, at **both** sites | unit | new `api/tests/test_toolkit_dispatch.py` | `docker compose exec api python -m pytest -q api/tests/test_toolkit_dispatch.py` | ❌ **W0** |
| CMP-17b | `hw_introspect` unified onto the same chain | unit | `api/tests/test_hw_introspect.py` | `docker compose exec api python -m pytest -q api/tests/test_hw_introspect.py` | ✅ |
| CMP-19 | Declared-deps field; stdlib-only enforcement; `compute_lib_import_failed` reserved | unit | `api/tests/test_hardware_lib_kind.py` + `test_view_key_preflight.py` | (see above) | ❌ **W0** |
| — | Auto-provisioned `pilot_hardware_config` row for `kind='compute'`; `incomplete_config` must **not** false-positive on a zero-param compute config | unit | `api/tests/test_view_key_preflight.py` | `docker compose exec api python -m pytest -q api/tests/test_view_key_preflight.py -k compute` | ✅ |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

- [ ] `api/tests/test_toolkit_dispatch.py` — no test file targets `api/routers/toolkit_dispatch.py` today, and CMP-17's more consequential fix lives there (it decides which `source_code` is exec'd).
- [ ] `api/tests/test_hardware_lib_kind.py` — `kind` column migration idempotency + declared-deps validation (CMP-12, CMP-19).
- [ ] `~/pi-mirror/tests/test_compute_ops.py` — compute class contract (`Hardware` subclass, `release()` override, seed op behavior). **USER-RUN.**
- [ ] Framework install: **none needed** — pytest and the React toolchain are already present.

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|---|---|---|---|
| Both event types reach ES per compute call | CMP-16 | Requires live ES + a real task run on the rig | User runs the gonogo-translation task; query ES via the `es-query` skill for the `Hardware_Event` (op + args) and the `Tracker` set (result) on the same trial |
| Both guarded branches fire across trials | CMP-03/05 | Requires a real multi-trial run | User runs the task; confirm both `target==true` and `target==false` transitions fire, recomputed once per entry |
| Researcher-authored compute lib works end to end | Phase goal / CMP-12/17 | Acceptance is a human workflow, not an assertion | Create a lib in the hardware-lib editor → promote to stable → link to toolkit → confirm ops appear in the GUI picker → run on rig, **with no platform code change** |
| Compute action row + `kind` filter chip are uncluttered | CMP-13/18 | Subjective UI acceptance | Click-through: action-type list gains exactly **one** entry; libs page gains one chip; no new page or nav entry |

---

## Validation Sign-Off

- [ ] All tasks have `<automated>` verify or a Wave 0 dependency
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify
- [ ] Wave 0 covers all ❌ references above
- [ ] No watch-mode flags
- [ ] Feedback latency < 40s
- [ ] `nyquist_compliant: true` set in frontmatter

**Approval:** pending
