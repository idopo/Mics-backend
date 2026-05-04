---
phase: 11-toolkit-redesign
verified: 2026-05-04T00:00:00Z
status: gaps_found
score: 9/9 must-haves verified (phase goal achieved); requirement ID mismatch flagged
re_verification:
  previous_status: passed
  previous_score: 9/9
  gaps_closed: []
  gaps_remaining: []
  regressions: []
gaps:
  - truth: "HW-17, HW-18, HW-19 as declared in 11-02/11-03 PLAN frontmatter match the features actually built"
    status: failed
    reason: |
      REQUIREMENTS.md assigns HW-17 (StateBodyPanel hardware dropdown + methods endpoint),
      HW-18 (PUT /api/hardware-libs re-extracts AST + diffs + scans FDA JSON + sets
      validation_status), and HW-19 (task_definitions validation_status/validation_message
      columns) to Phase 12 (Hardware-Aware FDA State Builder). None of these features were
      built in Phase 11. Plans 11-02 and 11-03 reused these IDs for unrelated features
      (dispatch-class resolution and hardware injection into START payload). The features
      built are correct and working but carry wrong requirement IDs in PLAN frontmatter.
    artifacts:
      - path: ".planning/phases/11-toolkit-redesign/11-02-PLAN.md"
        issue: "requirements: [HW-17, HW-18] — these IDs describe Phase 12 features, not what 11-02 built"
      - path: ".planning/phases/11-toolkit-redesign/11-03-PLAN.md"
        issue: "requirements: [HW-19] — this ID describes a Phase 12 feature (validation_status column), not what 11-03 built"
    missing:
      - "Either: add new requirement IDs in REQUIREMENTS.md for dispatch-class fix and hardware injection"
      - "Or: remove HW-17/18/19 claims from 11-02/11-03 PLAN frontmatter, leaving them as Phase 12 requirements"
      - "Confirm HW-17/18/19 remain unimplemented — do not mark as done"
---

# Phase 11: Toolkit Redesign Verification Report

**Phase Goal:** Backend-authored toolkits can be created, stored, and dispatched to the Pi with correct class instantiation and hardware injection; the toolkit UI is redesigned to reflect legacy vs backend-authored split.
**Verified:** 2026-05-04
**Status:** GAPS FOUND (requirement ID mismatch — phase goal itself is achieved)
**Re-verification:** Yes — previous VERIFICATION.md dated 2026-05-03 had status: passed for 9/9 HW-12-through-HW-16 truths. This re-verification adds HW-17, HW-18, HW-19 per the verification request and finds they are misassigned.

---

## Goal Achievement

The Phase 11 ROADMAP goal ("Toolkits are fully backend-defined...") is achieved. The 9 must-have truths from 11-01-PLAN.md are all still verified with no regressions. Plans 11-02 and 11-03 also delivered working features (dispatch-class fix + hardware injection). The gap is a **requirement ID bookkeeping error**: the IDs declared in the 11-02 and 11-03 PLAN frontmatter do not correspond to the features they built, and the real HW-17/18/19 features (Phase 12) were not built.

### Observable Truths (Phase 11 ROADMAP goal — from 11-01 must_haves)

| # | Truth | Status | Evidence |
|---|-------|--------|----------|
| 1 | `_put()` helper in mics_api_client | VERIFIED | `mics_api_client.py` line 49 — no regression |
| 2 | `task_toolkits` extended with 3 new columns | VERIFIED | `api/models.py` lines 605-607 — no regression |
| 3 | `run_toolkit_backend_authored_migrations()` called at startup | VERIFIED | `api/main.py` line 141 |
| 4 | `available_locked_states` table + HANDSHAKE both formats | VERIFIED | `AvailableLockedState` at models.py:721; orchestrator_station.py lines 139-168 |
| 5 | Legacy HANDSHAKE filename issue documented | VERIFIED | orchestrator_station.py lines 163-168 — no regression |
| 6 | Locked-states endpoints in `api/routers/locked_states.py` | VERIFIED | File exists, 135 lines — no regression |
| 7 | Backend-authored toolkit POST validates states + hw module IDs | VERIFIED | toolkits.py lines 261-283 — no regression |
| 8 | Toolkit UI: legacy vs backend-authored split + 5-step creation | VERIFIED | Toolkits.tsx lines 362-363 split; LegacyToolkitRow at line 66 |
| 9 | TaskEditor hw lib chips + HwLibVersionModal | VERIFIED | TaskEditor.tsx lines 22+119+455; HwLibVersionModal.tsx exists |

**Score (Phase 11 goal):** 9/9 truths verified. No regressions from previous verification.

### Additional Features Built in 11-02 and 11-03

These features are implemented correctly. They extend beyond the ROADMAP goal but carry wrong requirement IDs.

| Feature | Status | Evidence |
|---------|--------|----------|
| `class_name` column in `available_locked_states` | VERIFIED | `api/db.py` line 171 |
| `LockedStateUpsertPayload.class_name` + SQL binds | VERIFIED | locked_states.py line 23, 123-131 |
| `GET /api/toolkits/{id}/dispatch-class` endpoint | VERIFIED | toolkit_dispatch.py line 99 |
| `GET /api/toolkits/{id}/dispatch-spec` endpoint | VERIFIED | toolkit_dispatch.py line 26; three-query chain (module->lib->version) |
| toolkit_dispatch_router registered in api/main.py | VERIFIED | api/main.py lines 73+79 |
| `mics_api_client.get_toolkit_dispatch_class()` | VERIFIED | mics_api_client.py line 334 |
| `mics_api_client.get_toolkit_dispatch_spec()` | VERIFIED | mics_api_client.py line 338 |
| `task_type` override in `start_run()` (after `_build_*_task`) | VERIFIED | orchestrator_station.py lines 335-347 |
| `task_type` override in `_advance_run_step()` | VERIFIED | orchestrator_station.py lines 633-639 |
| `_inject_backend_toolkit_spec()` called in both start paths | VERIFIED | orchestrator_station.py lines 350, 640 |
| `ConditionBuilder` `hwModuleNames` prop + merged into hwOpts | VERIFIED | ConditionBuilder.tsx line 63 |
| `TaskEditor` fetches hw module names + passes to ConditionBuilder | VERIFIED | TaskEditor.tsx lines 119-122, 455 |
| Pi `mics_task` injection block (HARDWARE/FLAGS/PARAMS/PREFS_HARDWARE) | VERIFIED | mics_task.py lines 90-97 (before init_hardware()) |
| Pi `_resolve_hardware_classes()` | VERIFIED | mics_task.py lines 146-171 |
| Pi `_merge_prefs_hardware()` | VERIFIED | mics_task.py lines 173-179 |

---

### Required Artifacts

| Artifact | Expected | Status | Details |
|----------|----------|--------|---------|
| `api/models.py` | AvailableLockedState + TaskToolkit columns | VERIFIED | Lines 605-607, 721-731 |
| `api/db.py` | migrations incl. class_name column | VERIFIED | Line 171 |
| `api/main.py` | migration call + both routers registered | VERIFIED | Lines 73-79 |
| `api/routers/locked_states.py` | locked-states CRUD + class_name in upsert | VERIFIED | 135 lines; class_name at line 23 |
| `api/routers/toolkit_dispatch.py` | dispatch-class + dispatch-spec endpoints | VERIFIED | 124 lines; both endpoints present |
| `orchestrator/.../mics_api_client.py` | _put + upsert_locked_states + dispatch methods | VERIFIED | Lines 325-340 |
| `orchestrator/.../orchestrator_station.py` | class_name on upsert + override + inject | VERIFIED | Lines 147-168, 335-350, 633-640, 799-822 |
| `web_ui/.../Toolkits.tsx` | legacy/backend sections + 5-step modal | VERIFIED | Lines 362-363, 66, 219-222 |
| `web_ui/.../ConditionBuilder.tsx` | hwModuleNames prop + merged hwOpts | VERIFIED | Lines 50, 63 |
| `web_ui/.../TaskEditor.tsx` | hw module names query + prop pass-down | VERIFIED | Lines 22, 119-122, 455 |
| `~/pi-mirror/.../mics_task.py` | injection block + 2 helper methods | VERIFIED | Lines 83-97, 146-179 |

---

### Key Link Verification

| From | To | Via | Status | Details |
|------|----|-----|--------|---------|
| HANDSHAKE handler | `PUT /api/locked-states/{pilot_id}/{filename}` | `upsert_locked_states()` with class_name | WIRED | orchestrator_station.py lines 147-168 |
| `start_run()` | `GET /api/toolkits/{id}/dispatch-class` | `get_toolkit_dispatch_class()` | WIRED | orchestrator_station.py line 337; mics_api_client.py line 334 |
| `_advance_run_step()` | `GET /api/toolkits/{id}/dispatch-class` | same | WIRED | orchestrator_station.py line 633 |
| `_inject_backend_toolkit_spec()` | `GET /api/toolkits/{id}/dispatch-spec?pilot_id=...` | `get_toolkit_dispatch_spec()` | WIRED | orchestrator_station.py line 807; mics_api_client.py line 338 |
| `dispatch-spec` endpoint | `pilot_hardware_config` table | raw SQL (singular table name — plan had wrong plural) | WIRED | toolkit_dispatch.py line 81 |
| Pi `mics_task.__init__` | kwargs["HARDWARE"] | `_resolve_hardware_classes()` | WIRED | mics_task.py line 91 |
| Pi `mics_task.__init__` | kwargs["PREFS_HARDWARE"] | `_merge_prefs_hardware()` | WIRED | mics_task.py line 97 |

---

### Requirements Coverage

| Requirement | Source Plan | Description (from REQUIREMENTS.md) | Status | Evidence |
|-------------|------------|-------------------------------------|--------|----------|
| HW-12 | 11-01-PLAN.md | task_toolkits extended columns | SATISFIED | models.py + db.py migration |
| HW-13 | 11-01-PLAN.md | available_locked_states table + HANDSHAKE | SATISFIED | models.py, orchestrator_station.py |
| HW-14 | 11-01-PLAN.md | POST /api/toolkits validates states + hw modules | SATISFIED | toolkits.py lines 261-283 |
| HW-15 | 11-01-PLAN.md | HANDSHAKE new format accepted; legacy still works | SATISFIED | orchestrator_station.py lines 139-168 |
| HW-16 | 11-01-PLAN.md | Toolkit page redesigned with 5-step flow + legacy badge | SATISFIED | Toolkits.tsx |
| HW-17 | 11-02-PLAN.md (claimed) | REQUIREMENTS.md Phase 12: StateBodyPanel hardware dropdown + `GET /api/hardware-modules/{id}/methods` | NOT BUILT — ID MISASSIGNED | 11-02 built dispatch-class resolution instead. No hardware-modules methods endpoint exists. |
| HW-18 | 11-02-PLAN.md (claimed) | REQUIREMENTS.md Phase 12: `PUT /api/hardware-libs/{id}` re-extracts AST, diffs, scans FDA JSON, sets validation_status | NOT BUILT — ID MISASSIGNED | No such endpoint built in Phase 11. |
| HW-19 | 11-03-PLAN.md (claimed) | REQUIREMENTS.md Phase 12: task_definitions gains validation_status + validation_message columns | NOT BUILT — ID MISASSIGNED | No validation_status column added in Phase 11. |

**Orphaned requirement IDs:** HW-17, HW-18, HW-19 are claimed by Phase 11 plans but describe Phase 12 features. The features actually built in 11-02/11-03 have no matching IDs in REQUIREMENTS.md.

---

### Anti-Patterns Found

| File | Line | Pattern | Severity | Impact |
|------|------|---------|----------|--------|
| `api/routers/toolkits.py` | — | ~595 lines (hard limit 500) | Warning | Pre-existing; documented in SUMMARY |
| `api/models.py` | — | ~803 lines (hard limit 500) | Warning | Pre-existing; documented in SUMMARY |

No blocker anti-patterns. No stubs or empty implementations found.

---

### Human Verification Required

#### 1. Full backend-authored toolkit dispatch end-to-end

**Test:** Create a backend-authored toolkit with at least one hardware module that has an active lib version and a pilot hardware config entry. Start a run. Check orchestrator logs.
**Expected:** Log lines "Overriding task_type to ... for backend toolkit ..." and "Injected backend toolkit spec for toolkit ...". Pi receives START payload with HARDWARE dict containing source_code.
**Why human:** Requires real Pi HANDSHAKE data, a configured pilot hardware config row, and a running Pi.

#### 2. ConditionBuilder hw module names in dropdown

**Test:** Open TaskEditor for a task definition whose toolkit has hardware_module_ids set. Open the condition builder and check the HW type dropdown.
**Expected:** Module names from the toolkit appear alongside semantic_hardware keys.
**Why human:** Requires test data with a toolkit that has hardware_module_ids populated.

---

### Gaps Summary

**Phase 11 ROADMAP goal (HW-12 through HW-16) is fully achieved with no regressions.**

Plans 11-02 and 11-03 delivered working features beyond the ROADMAP goal (dispatch-class resolution, hardware injection into START payload, Pi-side injection hooks). These features are correct and all key links are wired.

**The gap is requirement ID tracking.** Plans 11-02 and 11-03 declared `requirements: [HW-17, HW-18]` and `requirements: [HW-19]` in their frontmatter, but REQUIREMENTS.md assigns those IDs to Phase 12 (Hardware-Aware FDA State Builder) with completely different descriptions. The real HW-17/18/19 features were NOT built:
- HW-17: No `GET /api/hardware-modules/{id}/methods` endpoint exists
- HW-18: No AST re-extraction or validation_status update on `PUT /api/hardware-libs/{id}`
- HW-19: No `validation_status` or `validation_message` columns in `task_definitions`

**Recommended fix:** Remove HW-17/18/19 from the Phase 11 PLAN frontmatter (or add a note that they are misassigned). The features built in 11-02/11-03 should either get new requirement IDs or be treated as untracked extensions. HW-17/18/19 remain Phase 12 work.

---

_Verified: 2026-05-04_
_Verifier: Claude (gsd-verifier)_
