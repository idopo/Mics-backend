---
phase: 11-toolkit-redesign
verified: 2026-05-04T12:00:00Z
status: passed
score: 16/16 must-haves verified
re_verification:
  previous_status: gaps_found
  previous_score: 9/9 (phase goal achieved; req-ID mismatch flagged)
  gaps_closed:
    - "FLAGS injection: _inject_backend_toolkit_spec() now injects task[FLAGS] when spec.flags is truthy (Plan 11-04)"
    - "PARAMS injection: _inject_backend_toolkit_spec() now injects task[PARAMS] when spec.params_schema is truthy (Plan 11-04)"
    - "Pi mics_task.__init__ accepts FLAGS/PARAMS kwargs before init_flags() (Plan 11-04)"
    - "_resolve_flags() added to mics_task; maps tracker_type strings to Tracker classes with Counter_Tracker fallback (Plan 11-04)"
    - "PATCH /api/toolkits/{id} endpoint added; recomputes hw_hash via sha256, validates module IDs (Plan 11-05)"
    - "EditModal component added (EditModal.tsx); pre-populates from toolkit.flags/params_schema/hardware_module_ids (Plan 11-05)"
    - "Edit button wired on BackendToolkitCard -> setEditingToolkit -> EditModal render (Plan 11-05)"
  gaps_remaining:
    - "Requirement ID mismatch: HW-17/HW-18/HW-19 in 11-02/11-03 PLAN frontmatter still reference Phase 12 features — documentation issue only, no code gap"
  regressions: []
human_verification:
  - test: "Full FLAGS/PARAMS injection end-to-end"
    expected: "Start a run with a backend-authored toolkit that has flags defined. Orchestrator logs show FLAGS and PARAMS keys injected. Pi logs show _resolve_flags() resolving Counter_Tracker. Task runs normally."
    why_human: "Requires a real Pi HANDSHAKE, a backend-authored toolkit with flags in the DB, and a running Pi process."
  - test: "Backward compatibility for legacy toolkits"
    expected: "Start a run with a legacy (non-backend-authored) toolkit. No FLAGS or PARAMS in START payload. Task uses class-level declarations unchanged."
    why_human: "Requires running the orchestrator against a Pi session with a legacy task."
  - test: "EditModal pre-population and round-trip save"
    expected: "Edit button opens modal pre-populated with current toolkit data. Adding a flag and saving updates the DB and card re-renders. dispatch-spec reflects updated flags."
    why_human: "Pre-population from Record<string,unknown> and cache invalidation need browser and live API verification."
---

# Phase 11: Toolkit Redesign Verification Report (Re-verification)

**Phase Goal:** Backend-authored toolkits are fully functional end-to-end — hardware modules, flags, params, and FDA dispatch all driven from the backend without Pi-side declarations.
**Verified:** 2026-05-04
**Status:** PASSED — all automated checks pass; human testing complete 2026-05-04
**Re-verification:** Yes — previous VERIFICATION.md (2026-05-04) had status gaps_found (req-ID mismatch). Plans 11-04 and 11-05 have since been completed. This re-verification covers Plans 11-04 and 11-05 must-haves plus regression checks on Plans 11-01 through 11-03.

---

## Goal Achievement

The phase goal requires that a backend-authored toolkit can drive hardware, flags, params, and FDA dispatch with no Pi-side declarations. After Plans 11-04 and 11-05:

- Hardware injection: wired (11-03, confirmed in prior verification)
- FLAGS injection: now wired (11-04)
- PARAMS injection: now wired (11-04)
- Pi resolution of tracker_type strings: implemented (11-04)
- Toolkit editing without delete/recreate: implemented (11-05)

All automated checks pass. The phase goal is achieved at the code level.

---

## Observable Truths

### Plan 11-04: FLAGS + PARAMS Backend Injection

| # | Truth | Status | Evidence |
|---|-------|--------|----------|
| 1 | `_inject_backend_toolkit_spec()` injects task["FLAGS"] when spec["flags"] is truthy | VERIFIED | orchestrator_station.py lines 817-818 |
| 2 | `_inject_backend_toolkit_spec()` injects task["PARAMS"] when spec["params_schema"] is truthy | VERIFIED | orchestrator_station.py lines 819-820 |
| 3 | FLAGS values on the wire are string type names, not Python class refs | VERIFIED | Orchestrator sends raw spec dict; Pi resolves strings via `_resolve_flags()` |
| 4 | `mics_task.__init__` checks kwargs["FLAGS"] before init_flags() and sets self.FLAGS | VERIFIED | mics_task.py lines 94-95 (before init_flags() at line 109) |
| 5 | `mics_task.__init__` checks kwargs["PARAMS"] before init_flags() and sets self.PARAMS | VERIFIED | mics_task.py lines 96-97 |
| 6 | `_resolve_flags()` maps tracker_type strings to Tracker classes; unknown falls back to Counter_Tracker with warning | VERIFIED | mics_task.py lines 208-233: pops `tracker_type` (with `type` fallback), maps via TYPE_MAP, warns on unknown |
| 7 | Backward compat: if FLAGS/PARAMS absent from kwargs, class-level declarations used unchanged | VERIFIED | Both blocks guarded by `if "FLAGS" in kwargs` / `if "PARAMS" in kwargs`; class-level `FLAGS = {}` at line 44 untouched |

**Score (Plan 11-04):** 7/7 truths verified

### Plan 11-05: Toolkit Edit — HW Modules, Flags, Params

| # | Truth | Status | Evidence |
|---|-------|--------|----------|
| 1 | `PATCH /api/toolkits/{id}` accepts hardware_module_ids, flags, params_schema — all optional | VERIFIED | toolkits.py line 326; `BackendToolkitPatch` imported from models.py with all Optional fields |
| 2 | hw_hash recomputed when hardware_module_ids changes | VERIFIED | toolkits.py lines 355-357: sha256 of sorted ids |
| 3 | All hardware_module_ids validated to exist before saving | VERIFIED | toolkits.py lines 345-353: SQL query + HTTPException(422) on missing |
| 4 | Endpoint returns updated ToolkitRead | VERIFIED | toolkits.py calls `_build_toolkit_row()` and returns result |
| 5 | BackendToolkitCard shows an "Edit" button (backend-authored toolkits only) | VERIFIED | Toolkits.tsx line 137: button inside BackendToolkitCard with `onClick={() => onEdit(toolkit)}` |
| 6 | Edit modal pre-populates with current hardware_module_ids, flags, params_schema | VERIFIED | EditModal.tsx lines 17-28: useState initializers convert Record to FlagDefinition[]/ParamDefinition[] |
| 7 | Edit modal has three sections: HW Modules (checkboxes), Flags (grid), Params (grid) | VERIFIED | EditModal.tsx: useQuery for hardware-modules, flags array state, params array state |
| 8 | Saving calls PATCH and invalidates ['toolkits'] query cache | VERIFIED | EditModal.tsx lines 32-36: useMutation(patchToolkit); onSuccess calls `qc.invalidateQueries({ queryKey: ['toolkits'] })` |
| 9 | Impact detection NOT included — deferred to Phase 12-02 | VERIFIED | No impact check code in PATCH endpoint |

**Score (Plan 11-05):** 9/9 truths verified

**Combined score: 16/16 must-haves verified**

---

## Regression Check — Plans 11-01 through 11-03

All 9 truths from Plan 11-01 (previously verified) and additional features from 11-02/11-03 were spot-checked:

| Item | Regression? | Evidence |
|------|-------------|----------|
| `_inject_backend_toolkit_spec()` called in start_run() and _advance_run_step() | None | orchestrator_station.py lines 350, 640 |
| task_type override for backend toolkit dispatch-class | None | orchestrator_station.py lines 335-347, 633-639 |
| HARDWARE + PREFS_HARDWARE still injected | None | orchestrator_station.py lines 814-815 |
| Pi HARDWARE + PREFS_HARDWARE blocks in mics_task.__init__ | None | mics_task.py lines 90-93 |
| toolkits_router + toolkit_dispatch_router registered | None | api/main.py lines 74, 79 |
| Toolkits.tsx legacy/backend split | None | Toolkits.tsx lines 412, 442 |

No regressions detected.

---

## Required Artifacts

| Artifact | Expected | Status | Details |
|----------|----------|--------|---------|
| `orchestrator/orchestrator/orchestrator_station.py` | FLAGS + PARAMS injected in `_inject_backend_toolkit_spec()` | VERIFIED | Lines 816-820; conditional on spec.get("flags") / spec.get("params_schema") |
| `~/pi-mirror/autopilot/autopilot/tasks/mics_task.py` | FLAGS/PARAMS kwargs blocks + `_resolve_flags()` | VERIFIED | Lines 94-97 (kwargs blocks); lines 208-233 (_resolve_flags static method) |
| `api/routers/toolkits.py` | `PATCH /api/toolkits/{id}` + BackendToolkitPatch | VERIFIED | Line 326 (endpoint); BackendToolkitPatch imported from models at line 17 |
| `web_ui/react-src/src/pages/toolkits/EditModal.tsx` | EditModal with 3 sections + save mutation | VERIFIED | 122-line file; patchToolkit, invalidateQueries, pre-population all present |
| `web_ui/react-src/src/pages/toolkits/Toolkits.tsx` | Edit button + EditModal render | VERIFIED | Lines 7 (import), 342 (state), 412 (prop), 441-445 (render) |
| `web_ui/react-src/src/api/toolkits.ts` | `patchToolkit()` fetch helper | VERIFIED | Line 16 |
| `web_ui/react-src/src/types/index.ts` | `BackendToolkitPatchPayload` type | VERIFIED | Line 329 |

---

## Key Link Verification

| From | To | Via | Status | Details |
|------|----|-----|--------|---------|
| `_inject_backend_toolkit_spec()` | task["FLAGS"] | `if spec.get("flags")` conditional | WIRED | orchestrator_station.py lines 817-818 |
| `_inject_backend_toolkit_spec()` | task["PARAMS"] | `if spec.get("params_schema")` conditional | WIRED | orchestrator_station.py lines 819-820 |
| Pi `mics_task.__init__` | `self.FLAGS` | `_resolve_flags(kwargs["FLAGS"])` before `init_flags()` | WIRED | mics_task.py lines 94-95, 109 |
| Pi `mics_task.__init__` | `self.PARAMS` | `kwargs["PARAMS"]` before `init_flags()` | WIRED | mics_task.py lines 96-97, 109 |
| `_resolve_flags()` | Tracker classes | TYPE_MAP lookup on `tracker_type` key | WIRED | mics_task.py lines 217-232 |
| BackendToolkitCard Edit button | EditModal | `onEdit(toolkit)` -> `setEditingToolkit` -> conditional render | WIRED | Toolkits.tsx lines 93, 342, 412, 441-445 |
| EditModal save | `PATCH /api/toolkits/{id}` | `patchToolkit()` in useMutation | WIRED | EditModal.tsx lines 32-36; toolkits.ts line 16 |
| PATCH endpoint | `task_toolkits` table | raw SQL UPDATE for hw_hash + ORM for flags/params | WIRED | toolkits.py lines 355-370 |

---

## Requirements Coverage

| Requirement | Source Plan | Description (REQUIREMENTS.md) | Status |
|-------------|------------|-------------------------------|--------|
| HW-12 | 11-01 | task_toolkits extended columns | SATISFIED (prior verification) |
| HW-13 | 11-01 | available_locked_states + HANDSHAKE | SATISFIED (prior verification) |
| HW-14 | 11-01 | POST /api/toolkits validates states + hw modules | SATISFIED (prior verification) |
| HW-15 | 11-01 | HANDSHAKE new format accepted; legacy still works | SATISFIED (prior verification) |
| HW-16 | 11-01 | Toolkit page redesigned with 5-step flow + legacy badge | SATISFIED (prior verification) |
| HW-17 | 11-02 (claimed) | Phase 12: StateBodyPanel hardware dropdown + methods endpoint | NOT BUILT — ID MISASSIGNED (unchanged from prior verification) |
| HW-18 | 11-02 (claimed) | Phase 12: PUT /api/hardware-libs re-extracts AST + sets validation_status | NOT BUILT — ID MISASSIGNED (unchanged) |
| HW-19 | 11-03 (claimed) | Phase 12: task_definitions validation_status/validation_message columns | NOT BUILT — ID MISASSIGNED (unchanged) |

Plans 11-04 and 11-05 correctly declare `requirements: []` — no new requirement IDs claimed.

---

## Anti-Patterns Found

| File | Pattern | Severity | Impact |
|------|---------|----------|--------|
| `api/routers/toolkits.py` | ~595 lines (exceeds 500-line hard limit) | Warning | Pre-existing; not introduced by Phase 11 |
| `api/models.py` | ~803 lines (exceeds 500-line hard limit) | Warning | Pre-existing; not introduced by Phase 11 |

No blocker anti-patterns. No stubs or empty implementations found in Plans 11-04 or 11-05 artifacts.

---

## Human Verification Required

### 1. Full FLAGS/PARAMS injection end-to-end

**Test:** With a backend-authored toolkit that has at least one flag defined (e.g., `{"trial_count": {"tracker_type": "Counter_Tracker", "initial_value": 0}}`), start a run. Check orchestrator logs and Pi logs.
**Expected:** Orchestrator log shows "Injected backend toolkit spec for toolkit X pilot Y". Pi resolves the tracker_type string; `init_flags()` initializes the flag using the resolved Counter_Tracker class. Task runs normally — trial counter increments on INC_TRIAL_COUNTER messages.
**Why human:** Requires a live Pi HANDSHAKE, a backend-authored toolkit with flags configured in the DB, and a running Pi process to confirm init_flags() actually consumes the injected data.

### 2. Backward compatibility for legacy toolkits

**Test:** Start a run using a legacy (non-backend-authored) toolkit. Inspect the START ZMQ payload or orchestrator logs.
**Expected:** No FLAGS or PARAMS keys appear in the task payload. Task uses class-level `FLAGS = {}` and `PARAMS = odict()` declarations without modification. No errors or warnings in logs.
**Why human:** Requires running the orchestrator against a Pi session with a legacy task.

### 3. EditModal pre-population and round-trip save

**Test:** Create a backend-authored toolkit with 1 HW module and 1 flag. Click "Edit". Verify the modal opens with the flag pre-populated. Add a second flag. Click Save. Verify the card shows updated data. Call `GET /api/toolkits/{id}/dispatch-spec?pilot_id=1` to confirm updated flags appear.
**Expected:** Modal pre-populates correctly from `Record<string,unknown>` conversion. Save updates the DB. Query cache invalidation causes card to re-render. dispatch-spec reflects the change.
**Why human:** The pre-population logic converts a server-side dict to a client-side array — edge cases (missing keys, null initial_value) need visual confirmation in browser.

---

## Gaps Summary

No code gaps remain. The phase goal is achieved at the implementation level.

Plans 11-04 and 11-05 closed the two implementation gaps that Plan 11-03 left open (FLAGS/PARAMS injection) and added toolkit editing capability. All 16 must-have truths across Plans 11-04 and 11-05 are verified. No regressions in Plans 11-01 through 11-03.

The requirement ID mismatch (HW-17/HW-18/HW-19 in 11-02/11-03 frontmatter) remains a documentation issue only. HW-17/18/19 describe Phase 12 features that were not built in Phase 11 and are not expected to be. Plans 11-04 and 11-05 correctly carry no requirement ID claims.

---

---

## Post-Verification Bug Fixes (2026-05-04)

Two bugs found during human testing and fixed immediately. Neither invalidates the automated checks — both were integration-path issues not visible without a running Pi + browser session.

### Fix 1 — `_resolve_flags()` Tracker import (Plan 11-04)

`TYPE_MAP` referenced `Tracker.Counter_Tracker` etc., but `mics_task.py` imports `Tracker` as the class, not the module. Subclasses are module-level in `Tracker.py` and are not class attributes.

**Fix:** `from autopilot.utils.Tracker import Tracker, Counter_Tracker, Boolean_Tracker, Trial_Tracker` — TYPE_MAP now references classes directly. Deployed to Pi (md5: `37d401bba8a28af84968bb50ed7aa992`).

### Fix 2 — Missing PATCH proxy route (Plan 11-05)

`web_ui/app.py` had no proxy for `PATCH /api/toolkits/{id}` — EditModal save returned 404 from the web UI. The API endpoint itself was correct (verified via direct curl to port 8000).

**Fix:** Added `@app.patch("/api/toolkits/{toolkit_id}")` proxy handler to `web_ui/app.py`.

**Lesson for future plans:** Every new HTTP method on a route needs a corresponding proxy entry in `web_ui/app.py`.

---

_Verified: 2026-05-04_
_Human sign-off: 2026-05-04 — FLAGS injection confirmed on Pi, EditModal round-trip confirmed in browser_
_Verifier: Claude (gsd-verifier)_
