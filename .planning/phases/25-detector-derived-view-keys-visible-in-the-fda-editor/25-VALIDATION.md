---
phase: 25
slug: detector-derived-view-keys-visible-in-the-fda-editor
status: planned
nyquist_compliant: true
wave_0_complete: false
created: 2026-07-29
updated: 2026-07-29
---

# Phase 25 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.
> No `25-RESEARCH.md` (research disabled in config) — infrastructure below was **verified live
> on 2026-07-29**, not inherited from a research doc.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework (backend)** | pytest + `fastapi.testclient.TestClient`. Suite exists and is green: **86 passed in 0.56 s** (re-verified 2026-07-29) |
| **Framework (Pi)** | pytest, stdlib-only test modules loaded via `importlib.util.spec_from_file_location`; no `pytest.ini` / `conftest.py` |
| **Framework (React)** | **Node's built-in runner** — `node --test` over `.mts` modules with native type stripping. Established by plan 04 task 1. No Vitest, no Jest, **zero new dependencies** |
| **Quick run (backend)** | `docker exec mics_api python3 -m pytest /app/tests/ -q` |
| **Quick run (React)** | `cd web_ui/react-src && npm run test:unit && npx tsc --noEmit` |
| **Quick run (Pi, agent)** | `python3 -m py_compile <file>` + `python3 -m pytest tests/test_fda_vocabulary.py tests/test_detector_view_keys.py -q` (stdlib-only modules) |
| **Full suite (backend)** | `docker compose up --build -d api && docker exec mics_api python3 -m pytest /app/tests/ -q` |
| **Full suite (Pi)** | `cd ~/Apps/mice_interactive_home_cage && python3 -m pytest tests/ -q` — **USER-RUN on the Pi** |
| **Estimated runtime** | backend < 5 s · React unit < 1 s · tsc ~15 s · Pi suite < 30 s |

### Confirmed constraints (do not re-discover)

- **Backend tests do NOT run on the dev host.** `cd api && python3 -m pytest tests/ -q` fails with
  `ModuleNotFoundError: No module named 'fastapi'` (verified 2026-07-29). They run **only** inside
  `mics_api`.
- **`mics_api` has NO bind mount.** `docker exec mics_api pytest` executes the *image's* code, so
  every backend test run must be preceded by `docker compose up --build -d api` or the result is
  meaningless — a green run can reflect code that is no longer on disk.
- **`autopilot` is not importable on the dev host** (missing `npyscreen` / `board` / `busio` /
  `PySide2` / `pigpio`; Blinka needs real Pi hardware detection). Any test that imports
  `autopilot.tasks.mics_task` or `autopilot.tasks.task` is **USER-RUN on the Pi**. Agent-runnable
  Pi feedback is limited to `py_compile` and stdlib-only modules loaded by file path.
- **Vite output is code-split.** Prove a React rebuild shipped by the changed content-hash filename
  (e.g. `TaskEditor-<hash>.js`), never by grepping `main.js`.

### React test path — mechanics (verified working this session, node v24.14.0)

Each of these was a failure before it was a rule:

- The module under test must be **`.mts`**, not `.ts`. `web_ui/react-src/package.json` has no
  `"type": "module"`, so Node treats a bare `.ts` as CommonJS and named imports fail with
  *"does not provide an export named …"*.
- Test files live in **`web_ui/react-src/tests/`**, outside `tsconfig.json`'s `include: ["src"]`,
  so `tsc` never sees the `node:test` / `node:assert` imports and `@types/node` is not required.
- `.tsx` consumers import with the explicit extension (`./detectorOptions.mts`); the repo already
  sets `allowImportingTsExtensions: true` + `noEmit: true`, and Vite resolves explicit paths.
  `npx tsc --noEmit` and `npx vite build` both verified clean with this arrangement.
- `node --test tests/` (directory form) does **not** pick up `.mts`. Use the quoted glob:
  `node --test "tests/**/*.test.mts"`.

Consequence: the *logic* deciding which keys are offered, how they are grouped, and whether a
stored key is unknown (DVK-03/04/05) is automatically tested. Only **rendering and interaction**
remain manual.

---

## Sampling Rate

- **After every backend task commit:** `docker compose up --build -d api && docker exec mics_api python3 -m pytest /app/tests/ -q`
- **After every React task commit:** `npm run test:unit && npx tsc --noEmit`
- **After every Pi task commit:** `python3 -m py_compile <changed file>` + the stdlib-only Pi suite (agent) — full Pi suite is user-run
- **After every plan wave:** full backend suite + React unit + `tsc --noEmit`
- **Before `/gsd:verify-work`:** backend suite green, React unit green, `tsc --noEmit` clean, Pi suite user-run green, rig evidence recorded
- **Max feedback latency:** ~20 s (backend rebuild dominates)

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|-----------|-------------------|-------------|--------|
| 01-T1 `derive_view_keys` | 25-01 | 1 | DVK-01, DVK-09 | unit (pure) | `docker exec mics_api python3 -m pytest /app/tests/test_detector_keys.py -q` | created by task | ⬜ pending |
| 01-T2 `module_detector_channels` | 25-01 | 1 | DVK-02 | unit (fake db) | `docker exec mics_api python3 -m pytest /app/tests/test_detector_keys.py -q` | created by task | ⬜ pending |
| 01-T3 DVK-07 regression | 25-01 | 1 | DVK-07 | unit | `docker exec mics_api python3 -m pytest /app/tests/ -q` | extends existing | ⬜ pending |
| 02-T1 `detector_view_keys` (Pi) | 25-02 | 1 | DVK-01, DVK-09 | unit (stdlib, **agent-runnable**) | `cd /home/ido/pi-mirror && python3 -m pytest tests/test_detector_view_keys.py tests/test_fda_vocabulary.py -q` | created by task | ⬜ pending |
| 02-T2 `check_for_detectors` | 25-02 | 1 | DVK-09 | py_compile (agent) + **user-run Pi suite** | `cd /home/ido/pi-mirror && python3 -m py_compile autopilot/autopilot/tasks/mics_task.py` | extends existing | ⬜ pending |
| 02-T3 `execute_trigger` guard | 25-02 | 1 | DVK-10 | py_compile (agent) + **user-run Pi suite** | `cd /home/ido/pi-mirror && python3 -m py_compile autopilot/autopilot/tasks/task.py` | created by task | ⬜ pending |
| 03-T1 scanner + resolver | 25-03 | 2 | DVK-06 | unit (pure) | `docker exec mics_api python3 -m pytest /app/tests/test_view_key_preflight.py -q` | created by task | ⬜ pending |
| 03-T2 preflight wiring | 25-03 | 2 | DVK-06 | route (mocked db) | `docker exec mics_api python3 -m pytest /app/tests/ -q` | extends 03-T1 file | ⬜ pending |
| 03-T3 `detector_channels` + `is_detector` | 25-03 | 2 | DVK-02 | unit + live curl | `docker exec mics_api python3 -m pytest /app/tests/ -q` | extends existing | ⬜ pending |
| 04-T1 `detectorOptions.mts` | 25-04 | 3 | DVK-03, DVK-04, DVK-05, DVK-07 | unit (**node:test**) | `cd web_ui/react-src && npm run test:unit && npx tsc --noEmit` | created by task | ⬜ pending |
| 04-T2 grouped picker + threading | 25-04 | 3 | DVK-03, DVK-05, DVK-07 | unit + typecheck + build | `cd web_ui/react-src && npm run test:unit && npx tsc --noEmit && npx vite build` | extends 04-T1 file | ⬜ pending |
| 04-T3 `key_template` suggestions | 25-04 | 3 | DVK-04, DVK-05 | unit + typecheck + build | `cd web_ui/react-src && npm run test:unit && npx tsc --noEmit && npx vite build` | extends 04-T1 file | ⬜ pending |
| 05-T1 `view_key_unresolved` render | 25-05 | 3 | DVK-06 | typecheck + build (**manual-only render**) | `cd web_ui/react-src && npx tsc --noEmit && npx vite build` | n/a | ⬜ pending |
| 05-T2 `first_channel` affordance | 25-05 | 3 | DVK-09 | typecheck + build (**manual-only render**) | `cd web_ui/react-src && npx tsc --noEmit && npx vite build` | n/a | ⬜ pending |
| 06-T1 deploy + rebuild | 25-06 | 4 | DVK-08 | full suites | `docker exec mics_api python3 -m pytest /app/tests/ -q && cd web_ui/react-src && npm run test:unit && npx tsc --noEmit` | n/a | ⬜ pending |
| 06-T2 Pi suite + restart | 25-06 | 4 | DVK-09, DVK-10 | **checkpoint: human-action** | USER-RUN: `cd ~/Apps/mice_interactive_home_cage && python3 -m pytest tests/ -q` | n/a | ⬜ pending |
| 06-T3 rig proof | 25-06 | 4 | DVK-08, DVK-09, DVK-10 | **checkpoint: human-verify** | none — live hardware | n/a | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

- [x] **Backend:** existing `api/tests/` infrastructure covers DVK-01/02/06/07 — new test modules
      only, no framework install needed. **Resolved:** plans 01 and 03 add
      `test_detector_keys.py` and `test_view_key_preflight.py`, both pure (no live DB, no
      TestClient), following `test_hw_introspect.py`'s style.
- [x] **Pi:** `check_for_detectors` (DVK-09) needed a test that does not import `mics_task`
      wholesale, or it becomes user-run-only and loses agent feedback. **Resolved:** the derivation
      itself moves into `autopilot/tasks/fda_vocabulary.py`, which is stdlib-only by design and is
      loaded by file path in tests — so `tests/test_detector_view_keys.py` (plan 02 task 1) runs on
      the dev host and gives agent-level feedback on the naming half of DVK-09. The
      `curr_vals` **indexing** half still imports `mics_task` and is user-run (plan 06 task 2) plus
      rig-proven (plan 06 task 3, "channel 4 lands in LICKER4").
- [x] **React:** no framework existed. **Resolved without adding one:** plan 04 task 1 is the
      React Wave 0 — it creates `src/components/detectorOptions.mts` (pure) and
      `tests/detectorOptions.test.mts`, run by Node's built-in test runner with native type
      stripping. Zero dependencies, no Docker/vite/tsconfig change. Verified working this session.
      **Plan 04 task 1 must complete before 04-T2/T3 and before plan 05's UI work is trusted.**

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| Detector keys render in the view-operand `<select>`, grouped as channels | DVK-03 | Rendering has no automated path; the *option-building logic* IS covered by `detectorOptions.test.mts` | Plan 06 task 3 step 2: open the FDA editor on toolkit 100, confirm a "MPR121 channels" group listing `LICKER1…LICKER4`, separate from the hardware group holding `MPR121` |
| `key_template` suggestion pills render and insert | DVK-04 | Rendering only; suggestion *contents* covered by `buildKeyTemplateSuggestions` tests | Plan 06 task 3 step 2: confirm `{device_name}`, the variables, and the literal keys are pickable, and the input is still typeable |
| Stored unknown key stays editable and shows "(unknown)" | DVK-05 | Rendering only; `isKnownViewKey` covered by unit test | Plan 06 task 3 step 2: open a definition referencing a key outside the derived set; confirm the value is preserved, marked unknown, and survives a re-save |
| `view_key_unresolved` issue renders in `HardwareCheckModal` | DVK-06 | No React render test | Plan 06 task 3 step 3 |
| The preflight modal writes no config for a view-key issue | DVK-06 | Requires a live PUT path | Plan 06 task 3 step 3: after cancelling the modal, re-read the MPR121 row and confirm it is unchanged |
| `first_channel` field + live key preview | DVK-09 | No React render test | Plan 06 task 3 step 1, confirmed by reading the DB row back |
| Pi suite green after the `mics_task` / `task.py` changes | DVK-09, DVK-10 | `autopilot` unimportable on the dev host | USER-RUN: `cd ~/Apps/mice_interactive_home_cage && python3 -m pytest tests/ -q` |
| Channel 4's writes land in `LICKER4`; no cross-talk | DVK-09 | Requires live MPR121 + spouts | Plan 06 task 3 step 4 |
| A failing trigger action logs an error naming the key | DVK-10 | Requires a live trigger firing | Plan 06 task 3 step 5 |
| Rig proof: a transition on a licker key fires | DVK-08 | Requires live MPR121 + spouts | Plan 06 task 3 step 4 |

---

## Validation Sign-Off

- [x] All tasks have an `<automated>` verify or an explicit manual-only justification with a named
      checkpoint that covers it
- [x] **Sampling continuity:** no 3 consecutive tasks without an automated verify.
      Longest run without a *behavioural* automated check is plan 05's two tasks (typecheck +
      build only), immediately followed by plan 06 task 1's three full suites — 2 tasks, under the
      limit. Plan 02's tasks 2 and 3 have `py_compile` plus a same-plan stdlib suite, and are
      bracketed by 02-T1's real unit tests and 06-T2's user-run suite.
- [x] Wave 0 covers all MISSING references — no task's verify command references a test file that
      no plan creates
- [x] No watch-mode flags
- [x] Feedback latency < 20 s
- [x] `nyquist_compliant: true` set in frontmatter

**Caveat recorded honestly:** DVK-09's `curr_vals` indexing and all of DVK-10's behaviour have
**no agent-runnable automated check** — both live in modules that import `autopilot`. They are
covered by a user-run suite and by an explicit rig assertion, which is the strongest available
signal on this system, not by continuous sampling. Plan 02's summary must say so rather than
implying `py_compile` proved anything behavioural.

**Approval:** planner-signed 2026-07-29
