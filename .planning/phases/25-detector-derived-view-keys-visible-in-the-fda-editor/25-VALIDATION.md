---
phase: 25
slug: detector-derived-view-keys-visible-in-the-fda-editor
status: draft
nyquist_compliant: false
wave_0_complete: false
created: 2026-07-29
---

# Phase 25 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.
> No `25-RESEARCH.md` (research disabled in config) — infrastructure below was **verified live
> on 2026-07-29**, not inherited from a research doc.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework (backend)** | pytest + `fastapi.testclient.TestClient`. Suite exists and is green: **86 passed in 0.65 s** (verified 2026-07-29) |
| **Framework (Pi)** | pytest, stdlib-only test modules loaded via `importlib.util.spec_from_file_location`; no `pytest.ini` / `conftest.py` |
| **Framework (React)** | **none** — no Vitest/Jest in `web_ui/react-src/package.json`. UI verification is `tsc --noEmit` + manual |
| **Quick run (backend)** | `docker exec mics_api python3 -m pytest /app/tests/ -q` |
| **Quick run (React)** | `cd web_ui/react-src && npx tsc --noEmit` |
| **Quick run (Pi, agent)** | `python3 -m py_compile <file>` + `python3 -m pytest tests/test_fda_vocabulary.py -q` (stdlib-only module) |
| **Full suite (backend)** | `docker exec mics_api python3 -m pytest /app/tests/ -q` |
| **Full suite (Pi)** | `cd ~/Apps/mice_interactive_home_cage && python3 -m pytest tests/ -q` — **USER-RUN on the Pi** |
| **Estimated runtime** | backend < 5 s · tsc ~15 s · Pi suite < 30 s |

### Confirmed constraints (do not re-discover)

- **Backend tests do NOT run on the dev host.** `cd api && python3 -m pytest tests/ -q` fails with
  `ModuleNotFoundError: No module named 'fastapi'` (verified 2026-07-29). They run **only** inside
  `mics_api`.
- **`mics_api` has NO bind mount.** `docker exec mics_api pytest` executes the *image's* code, so
  every backend test run must be preceded by `docker compose up --build -d api` or the result is
  meaningless — a green run can reflect code that is no longer on disk.
- **`autopilot` is not importable on the dev host** (missing `npyscreen` / `board` / `busio` /
  `PySide2` / `pigpio`; Blinka needs real Pi hardware detection). Any test that imports
  `autopilot.tasks.mics_task` is **USER-RUN on the Pi**. Agent-runnable Pi feedback is limited to
  `py_compile` and stdlib-only modules loaded by file path.
- **Vite output is code-split.** Prove a React rebuild shipped by the changed content-hash filename
  (e.g. `TaskEditor-<hash>.js`), never by grepping `main.js`.

---

## Sampling Rate

- **After every backend task commit:** `docker compose up --build -d api && docker exec mics_api python3 -m pytest /app/tests/ -q`
- **After every React task commit:** `npx tsc --noEmit`
- **After every Pi task commit:** `python3 -m py_compile <changed file>` (agent) — full Pi suite is user-run
- **After every plan wave:** full backend suite + `tsc --noEmit`
- **Before `/gsd:verify-work`:** backend suite green, `tsc --noEmit` clean, Pi suite user-run green
- **Max feedback latency:** ~20 s (backend rebuild dominates)

---

## Per-Task Verification Map

> Filled by `gsd-planner`. Every task must map to an automated command or an explicit
> Wave 0 / manual-only entry.

| Task ID | Plan | Wave | Requirement | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|-----------|-------------------|-------------|--------|
| TBD | | | | | | | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

- [ ] Backend: existing `api/tests/` infrastructure covers DVK-01/02/06/07 — new test modules only,
      no framework install needed.
- [ ] Pi: `check_for_detectors` change (DVK-09) needs a test that does **not** import `mics_task`
      wholesale, or it becomes user-run-only and loses agent feedback. Planner must decide.
- [ ] React: no framework. DVK-03/04/05 UI behaviour has **no automated path** — plan must either
      accept manual-only or scope a minimal Vitest setup as an explicit task.

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| Detector keys appear in view-operand `<select>` | DVK-03 | No React test framework | Open `/react/task-editor`, attach MPR121 toolkit, open a transition condition, confirm `LICKER1…LICKER4` listed and grouped as channels |
| `key_template` offers prefix + token completion | DVK-04 | No React test framework | In the trigger `view` action, confirm the detector prefix and `{pin_number}` completion are pickable, not typed |
| Stored unknown key stays editable + flagged | DVK-05 | No React test framework | Open a definition referencing a key outside the derived set; confirm value is preserved and marked unknown |
| Rig proof: transition on a licker key fires | DVK-08 | Requires live MPR121 + spouts | Declare a transition on `LICKER2`, save, pass preflight, run on `pilot_raspberry_lior`, confirm firing in ES |
| Pi suite green after DVK-09 change | DVK-09 | `autopilot` unimportable on dev host | USER-RUN: `cd ~/Apps/mice_interactive_home_cage && python3 -m pytest tests/ -q` |

---

## Validation Sign-Off

- [ ] All tasks have `<automated>` verify or Wave 0 dependencies
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify
- [ ] Wave 0 covers all MISSING references
- [ ] No watch-mode flags
- [ ] Feedback latency < 20s
- [ ] `nyquist_compliant: true` set in frontmatter

**Approval:** pending
