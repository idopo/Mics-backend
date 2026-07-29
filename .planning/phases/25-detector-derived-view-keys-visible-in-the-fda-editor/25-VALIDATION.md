---
phase: 25
slug: detector-derived-view-keys-visible-in-the-fda-editor
status: planned
nyquist_compliant: true
wave_0_complete: false
created: 2026-07-29
updated: 2026-07-29  # revised after plan-check iteration 1, then after the DVK-11 design change (iteration 2)
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
- **`web_ui/react-src/src/style.css` does not exist.** The stylesheet is `web_ui/static/style.css`
  (`.meta-pill` at line 1196). CLAUDE.md's "CSS" note is wrong on this point; plans 04 and 05 were
  corrected. Do not create the nonexistent file and do not invent class names.
- **`TaskEditor.tsx` loads its toolkit from `/api/toolkits/by-name/{name}`**, not
  `/api/toolkits/{id}` (`TaskEditor.tsx:20`, `:176-183` → `api/toolkits.ts:8`). Any API field the
  editor consumes must be asserted against that route, or a green check proves nothing about the
  editor.
- **`MICS_API_TOKEN` lives only in `mics_web_ui`.** Verified 2026-07-29: `docker exec mics_api
  printenv MICS_API_TOKEN` is empty, and there is no `.env` on the host. Every authenticated live
  read must run as `docker exec mics_web_ui python3 -c ...` against `http://api:8000`. A
  `curl -H "Authorization: Bearer $MICS_API_TOKEN"` from the host sends an empty token and returns
  `{"detail":"Not authenticated"}`.
- **Preflight is advisory, not a gate.** `HardwareCheckModal.handleStart`
  (`HardwareCheckModal.tsx:309-333`) always calls `onStart()`, and both callers
  (`PilotSessions.tsx:101`, `SubjectSessions.tsx:108`) treat preflight as non-blocking — Phase 13's
  deliberate decision. DVK-06's "fails before START" is satisfied by a readable REPORT before
  START. Nothing in Phase 25 adds a gate; a session that starts anyway is designed behaviour, not
  a defect.
- **`api/detector_keys.py` has no runtime coupling to `fda_validation.py`.** DVK-07's boundary is
  pinned behaviourally by plan 01 task 3's `_valid_flag_names` equality assertion, not by a
  source-text grep.

### React test path — mechanics (verified working this session, node v24.14.0)

Each of these was a failure before it was a rule:

- The module under test must be **`.mts`**, not `.ts`. **Corrected 2026-07-29 — the earlier stated
  reason was false and is left here so it is not re-derived:** Node does *not* reject a bare `.ts`.
  With no `"type": "module"` in `web_ui/react-src/package.json`, node v24.14.0 emits
  `MODULE_TYPELESS_PACKAGE_JSON`, reparses as ESM, and named imports of **real runtime exports**
  resolve fine (verified: 1 pass). `.mts` is kept because it is ESM by extension, unambiguous, and
  warning-free — not because `.ts` fails.
- **The real cause of the *"does not provide an export named …"* failure: importing a types-only
  module as a value import.** `src/types/index.ts` has no runtime exports at all after type
  stripping, so `import { DetectorChannelGroup } from '../types/index.ts'` throws at test time.
  Use `import type { … }`, which is erased before evaluation. Verified passing under
  `node --test "tests/**/*.test.mts"` with `npx tsc --noEmit` and `npx vite build` clean.
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
| 01-T1 `derive_channels` + `derive_view_keys` | 25-01 | 1 | DVK-01, DVK-09 | unit (pure) | `docker exec mics_api python3 -m pytest /app/tests/test_detector_keys.py -q` | created by task | ⬜ pending |
| 01-T2 `module_detector_channels` | 25-01 | 1 | DVK-02 | unit (fake db) | `docker exec mics_api python3 -m pytest /app/tests/test_detector_keys.py -q` | created by task | ⬜ pending |
| 01-T3 `scan_fda_condition_operands` (the ONE walker) | 25-01 | 1 | DVK-06, DVK-11 | unit (pure) | `docker exec mics_api python3 -m pytest /app/tests/ -q` | extends `api/fda_utils.py` | ⬜ pending |
| 01-T4 DVK-11 save gate + DVK-07 regression | 25-01 | 1 | DVK-07, DVK-11 | unit | `docker exec mics_api python3 -m pytest /app/tests/ -q` | extends existing | ⬜ pending |
| 02-T1 `detector_view_keys` + `detector_channel_key` (Pi) | 25-02 | 1 | DVK-01, DVK-09 | unit (stdlib, **agent-runnable**) | `cd /home/ido/pi-mirror && python3 -m pytest tests/test_detector_view_keys.py tests/test_fda_vocabulary.py -q` | created by task | ⬜ pending |
| 02-T2 `check_for_detectors` | 25-02 | 1 | DVK-09 | py_compile (agent) + **user-run Pi suite** | `cd /home/ido/pi-mirror && python3 -m py_compile autopilot/autopilot/tasks/mics_task.py` | extends existing | ⬜ pending |
| 02-T3 `execute_trigger` guard | 25-02 | 1 | DVK-10 | py_compile (agent) + **user-run Pi suite** | `cd /home/ido/pi-mirror && python3 -m py_compile autopilot/autopilot/tasks/task.py` | created by task | ⬜ pending |
| 02-T4 `view_detector` operand branch | 25-02 | 1 | DVK-11 | unit (stdlib, **agent-runnable**: `parse_view_detector_operand`) + **user-run Pi suite** (resolution) | `cd /home/ido/pi-mirror && python3 -m pytest tests/test_detector_view_keys.py tests/test_fda_vocabulary.py -q` | extends 02-T1 file + created by task | ⬜ pending |
| 03-T1 scanner + resolver | 25-03 | 2 | DVK-06, DVK-11 | unit (pure) | `docker exec mics_api python3 -m pytest /app/tests/test_view_key_preflight.py -q` | created by task | ⬜ pending |
| 03-T2 preflight wiring | 25-03 | 2 | DVK-06, DVK-11 | route (mocked db) | `docker exec mics_api python3 -m pytest /app/tests/ -q` | extends 03-T1 file | ⬜ pending |
| 03-T3 `detector_channels` + `is_detector` | 25-03 | 2 | DVK-02 | unit + live assert on **both** read routes (must show `channels`) | `docker exec mics_api python3 -m pytest /app/tests/ -q` then an inline python assert that `detector_channels` carries MPR121 `channels`+`keys`+`device_names` on `/api/toolkits/100` **and** `/api/toolkits/by-name/source_less_toolkit` (full command in 25-03 task 3) | extends existing | ⬜ pending |
| 04-T1 `detectorOptions.mts` | 25-04 | 3 | DVK-03, DVK-04, DVK-05, DVK-07, DVK-11 | unit (**node:test**), incl. the operand round trip | `cd web_ui/react-src && npm run test:unit && npx tsc --noEmit` | created by task | ⬜ pending |
| 04-T2 grouped picker + threading | 25-04 | 3 | DVK-03, DVK-05, DVK-07, DVK-11 | unit + typecheck + build | `cd web_ui/react-src && npm run test:unit && npx tsc --noEmit && npx vite build` | extends 04-T1 file | ⬜ pending |
| 04-T3 `key_template` suggestions | 25-04 | 3 | DVK-04, DVK-05 | unit + typecheck + build | `cd web_ui/react-src && npm run test:unit && npx tsc --noEmit && npx vite build` | extends 04-T1 file | ⬜ pending |
| 05-T1 `view_key_unresolved` render (both shapes) | 25-05 | 3 | DVK-06, DVK-11 | typecheck + build (**manual-only render**) | `cd web_ui/react-src && npx tsc --noEmit && npx vite build` | n/a | ⬜ pending |
| 05-T2 `first_channel` affordance | 25-05 | 3 | DVK-09 | typecheck + build (**manual-only render**) | `cd web_ui/react-src && npx tsc --noEmit && npx vite build` | n/a | ⬜ pending |
| 06-T1 deploy + rebuild | 25-06 | 4 | DVK-08 | full suites | `docker exec mics_api python3 -m pytest /app/tests/ -q && cd web_ui/react-src && npm run test:unit && npx tsc --noEmit` | n/a | ⬜ pending |
| 06-T2 Pi suite + restart | 25-06 | 4 | DVK-09, DVK-10, DVK-11 | **checkpoint: human-action** | USER-RUN: `cd ~/Apps/mice_interactive_home_cage && python3 -m pytest tests/ -q` | n/a | ⬜ pending |
| 06-T3 rig proof (incl. the `device_name` rename) | 25-06 | 4 | DVK-03, DVK-04, DVK-05, DVK-06, DVK-08, DVK-09, DVK-10, DVK-11 | **checkpoint: human-verify** | none — live hardware | n/a | ⬜ pending |

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
      After the DVK-11 design change this module also owns the operand round trip
      (`viewOperandToOptionValue` / `optionValueToViewOperand`), which is the riskiest logic in the
      phase and is therefore the piece with the strongest automated signal.

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| Detector channels render in the view-operand `<select>`, grouped and labelled by `device_name` | DVK-03 | Rendering has no automated path; the *option-building logic* IS covered by `detectorOptions.test.mts` | Plan 06 task 3 step 2: open the FDA editor on toolkit 100, confirm a **"LICKER channels"** group (from `device_name`, not the module name) listing "MPR121 — channel 1…4 (→ LICKER1…4)", separate from the hardware group holding `MPR121` |
| Picking a channel stores `{"view_detector": {ref, channel}}` and no per-pilot name | DVK-11 | The encode/decode pair IS unit-tested; that the *rendered picker* wires to it is not | Plan 06 task 3 step 2: read the saved definition back via `GET /api/task-definitions/<id>` and confirm the operand shape and that `LICKER` appears nowhere in that transition |
| A stored definition survives a `device_name` rename byte-identical and still fires | DVK-11 | Requires a live pilot config change + a rig run | Plan 06 task 3 step 5: rename `LICKER`→`TONGUE`, do not touch the definition, compare `fda_json` SHAs, re-run and confirm `TONGUE2` moves and the transition fires |
| `key_template` suggestion pills render and insert | DVK-04 | Rendering only; suggestion *contents* covered by `buildKeyTemplateSuggestions` tests | Plan 06 task 3 step 2: confirm `{device_name}`, the variables, and the literal keys are pickable, and the input is still typeable |
| Stored unknown key stays editable, shows "(unknown)", and survives a save round trip | DVK-05 | Rendering only; `isKnownViewOption` covered by unit test. **This is DVK-05's only behavioural proof** — the unit test proves the predicate, not the round trip | Plan 06 task 3 step 2, final bullet. **Scope narrowed 2026-07-29:** DVK-05 covers keys the backend cannot model, **not** legacy detector keys — all 149 rows were walked and none stores one. The proof therefore uses a free-text key the toolkit does not declare (`SOME_PY_TRACKER`), not a stale `LICKER0` |
| `view_key_unresolved` issue renders in `HardwareCheckModal` — BOTH shapes | DVK-06, DVK-11 | No React render test | Plan 06 task 3 step 3: one out-of-range detector channel (detector-led form) and one literal unknown key (key-led form) |
| The preflight modal writes no config for a view-key issue | DVK-06 | Requires a live PUT path | Plan 06 task 3 step 3: after cancelling the modal, re-read the MPR121 row and confirm it is unchanged |
| `first_channel` field + live key preview | DVK-09 | No React render test | Plan 06 task 3 step 1, confirmed by reading the DB row back |
| Pi suite green after the `mics_task` / `task.py` changes | DVK-09, DVK-10 | `autopilot` unimportable on the dev host | USER-RUN: `cd ~/Apps/mice_interactive_home_cage && python3 -m pytest tests/ -q` |
| Channel 4's writes land in `LICKER4`; no cross-talk | DVK-09 | Requires live MPR121 + spouts | Plan 06 task 3 step 4 |
| A failing trigger action logs an error naming the key | DVK-10 | Requires a live trigger firing | Plan 06 task 3 step 5 |
| Rig proof: a transition declared as "MPR121 — channel 2" fires | DVK-08, DVK-11 | Requires live MPR121 + spouts | Plan 06 task 3 step 4 |

---

## Validation Sign-Off

- [x] All tasks have an `<automated>` verify or an explicit manual-only justification with a named
      checkpoint that covers it
- [x] **Sampling continuity:** no 3 consecutive tasks without an automated verify.
      Longest run without a *behavioural* automated check is **2**, in two places:
      (a) plan 02's tasks 2 and 3 (`py_compile` only), bracketed by 02-T1's real stdlib unit tests
      before and 02-T4's real stdlib unit tests after;
      (b) plan 05's two tasks (typecheck + build only), immediately followed by plan 06 task 1's
      three full suites.
      **This was the binding constraint on the DVK-11 revision.** Adding 02-T4 naively would have
      made 02-T2/T3/T4 three consecutive `py_compile`-only tasks. It was resolved by moving the
      operand's shape rules into `fda_vocabulary.parse_view_detector_operand` — stdlib-only,
      loadable by file path, therefore agent-runnable — so 02-T4 carries real unit tests. The
      constraint changed the design, not the claim.
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

---

## Revision log

**Iteration 1 (2026-07-29) — plan-checker feedback applied.** Six factual claims were checked
against the real code; two were wrong and are corrected above and in the plans:

| Ref | Change | Files |
|---|---|---|
| B1 | `detector_channels` must be fed at **every** `_build_toolkit_row` call site that has `caps` — **121/123, 166, 195/196** — not just two. Line 166 is `get_toolkits_by_name`, the only route `TaskEditor.tsx` uses. Automated assertion now covers `/api/toolkits/by-name/source_less_toolkit`, run from `mics_web_ui`. 248/361/506 documented as intentionally `[]` | 25-03, this file |
| B1-follow-up | The checker's supporting claim that *"patch responses are used to refresh the editor's toolkit"* was checked and **does not hold** — `EditModal.tsx:32-33` discards the PATCH body and invalidates `['toolkits']` instead. Plan 03 records the verified behaviour, not the claim, and leaves 506 unfed with the evidence attached | 25-03 |
| S1 | `import type { DetectorChannelGroup }` — a value import of a types-only module fails at test time. Fallback paragraph deleted | 25-04, this file |
| S2 | `is_detector` resolved in the **edit** flow by `modules.find(m => m.name === row.name)`; renders nothing when no module matches | 25-05 |
| S3 | The whole trigger error-report body is wrapped in its own `try/except` — `dispatch_event` calls `pi.get_current_tick()` and is not total | 25-02 |
| S4 | DVK-05's round-trip step actually written into plan 06 task 3 step 2 | 25-06, this file |
| S5 | Pre-edit mirror-Pi `diff` (git-free, no pull) is now plan 02 task 1 step 0 | 25-02, 25-06 |
| S6 | `issues.map` React key made unique — one `view_key_unresolved` issue per key means duplicate `module_name`s | 25-05 |
| N1 | The "`.ts` is CommonJS, named imports fail" rule was **false**; corrected reason recorded, `.mts` kept | 25-04, this file |
| N2 | `web_ui/react-src/src/style.css` does not exist; real path is `web_ui/static/style.css:1196` | 25-04, 25-05, this file |
| N3 | `module_names` collected from `rows` **before** `hw_introspect.py:150-151`'s `if not row.source_code: continue` | 25-03 |
| N4 | Step 8 nests inside step 7's `if td_full and td_full.fda_json:` — `already_flagged` is scoped there | 25-03 |
| N5 | Plan 06 step 5 uses `first_channel: 2` + the canonical template so it reaches the runtime `KeyError` instead of the preflight modal | 25-06 |
| N6 | Preflight's advisory nature stated in plan 05 and plan 06's success criteria | 25-05, 25-06, this file |
| N7 | Citations corrected: `fda_validation.py:14-20` / `:30-33`; `prefs` not `autopilot_prefs`; `Event_Dispatcher.py:55-62` | 25-01, 25-02, 25-03 |
| N8 | Plan 01 frontmatter gains DVK-09; plan 06 gains DVK-03/04/05/06 as its manual verification home, matching the map | 25-01, 25-06, this file |

**Nyquist re-confirmed after the revision:** 17 map rows, 17 real tasks, still one-to-one. No task
was added, removed, split or merged. Two verify commands changed (03-T3 gained the by-name
assertion; nothing else), both still automated, both still under the latency budget. The sampling
continuity argument is unchanged — plan 05's two typecheck-only tasks remain the longest run
without a behavioural automated check, still bracketed by 04-T3 before and 06-T1's three full
suites after.

**Iteration 2 (2026-07-29) — DVK-11 design change (user-rejected the stored-literal-key design).**
A condition operand now stores `{"view_detector": {"ref", "channel"}}`; the Pi resolves the name.
Authority: `25-CONTEXT.md` D1-D6.

| Ref | Change | Files |
|---|---|---|
| D-01 | `module_detector_channels` gains `channels` (the indices) alongside `keys` — an index is what is stored, and the editor must not recover it by stripping digits (CONTEXT D6) | 25-01, 25-03, 25-04, 25-06 |
| D-02 | New task 01-T3: `scan_fda_condition_operands` in `api/fda_utils.py` — ONE condition walker for both the 422 pass and preflight. Verified this session: `scan_fda_for_refs` walks actions only and **never sees transition conditions** | 25-01, 25-03 |
| D-03 | New task 01-T4: DVK-11 save-time 422 in `api/fda_validation.py`. Placed there, not in preflight, because "is `ref` a detector" is a **toolkit** fact and `toolkit_hw_capabilities` already returns `detector_refs` (`hw_introspect.py:164-168`) — currently computed and thrown away at `fda_validation.py:190`. Zero new queries. Channel RANGE stays in preflight | 25-01, 25-03 |
| D-04 | New task 02-T4: the Pi's `view_detector` branch, resolving **once at build time**. Justified by verified ordering (`__init__` runs `check_for_detectors` at :127 before `load_fda_from_json` at :161; `_semantic_hw` built at :922 before transitions at :991) and by `View.get_value` raising a **bare** `KeyError` (`core/View.py:43-44`) that names nothing | 25-02 |
| D-05 | `fda_vocabulary.parse_view_detector_operand` added so 02-T4 has agent-runnable coverage — otherwise 02-T2/T3/T4 would be three consecutive `py_compile`-only tasks and `nyquist_compliant` would be false | 25-02, this file |
| D-06 | Editor: the `<select>` stays **string-valued**; `detectorOptions.mts` owns a token ⇄ operand pair (`viewOperandToOptionValue` / `optionValueToViewOperand`) resolved by **membership in the backend's own data**, not by parsing. Zero prop-shape change, and `ConditionBuilder.tsx:85`'s keep-current-value escape works verbatim | 25-04 |
| D-07 | `operandLabel` and `getOperandType` must learn `view_detector`, or every edge label and the `StateBodyPanel` wait-condition summary renders `?`. `setType` must use a resolved display key or `''`, or switching a detector operand to `flag` writes the token into the flag name | 25-04 |
| D-08 | An out-of-range channel **reuses** `view_key_unresolved` (CONTEXT left the choice to Claude) with new optional `detector` / `available_channels` fields — one modal branch, two shapes | 25-03, 25-05 |
| D-09 | DVK-05 narrowed to keys the backend cannot model. **No migration, no dual-read, no back-compat shim** — CONTEXT D3 walked all 149 rows and none stores a detector key. Every "migrate old LICKER0" framing removed | 25-04, 25-06, this file |
| D-10 | Plan 06's headline assertion is now the **rename proof**: `device_name` LICKER→TONGUE, definition untouched and `fda_json` SHA identical, transition still fires, editor relabels. Plus a stored-shape assertion that `LICKER` appears nowhere in the saved transition | 25-06 |
| D-11 | Task count 17 → 19 (01 and 02 each gain one). Requirement coverage re-checked: DVK-01…DVK-11 each appear in at least one plan's `requirements` | all |

**Nyquist re-confirmed after iteration 2:** 19 map rows, 19 real tasks, one-to-one. Every task has
an `<automated>` verify. Longest run without a behavioural automated check is 2 (see Sign-Off).
Feedback latency unchanged.

**Approval:** planner-signed 2026-07-29 · revised after plan-check iteration 1 · revised after the
DVK-11 design change (iteration 2), 2026-07-29
