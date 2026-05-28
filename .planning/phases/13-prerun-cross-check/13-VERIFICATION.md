---
phase: 13-prerun-cross-check
verified: 2026-05-28T00:00:00Z
status: human_needed
score: 5/5 must-haves verified
re_verification:
  previous_status: gaps_found
  previous_score: 4/5
  gaps_closed:
    - "POST /api/sessions/{id}/preflight-validate/{pilot_id} is now reachable — route decorator changed from '/api/sessions/...' to '/sessions/...' in toolkit_dispatch.py; FastAPI now registers at /api/sessions/... as intended"
  gaps_remaining: []
  regressions: []
human_verification:
  - test: "Session start UI with missing hardware module config"
    expected: "HardwareCheckModal appears listing the missing module; user can fill in key-value params and click Save & Start to proceed"
    why_human: "Requires a backend-authored toolkit with hardware modules configured, a pilot with missing config, and UI interaction"
  - test: "INC_TRIAL_COUNTER stable promotion in live run"
    expected: "After first trial of a backend-authored task, any beta hw lib versions are promoted to stable"
    why_human: "Requires live Pi run; can't verify the promotion fires without a real INC_TRIAL_COUNTER ZMQ message"
---

# Phase 13: Pre-Run Cross-Check Verification Report

**Phase Goal:** Before starting a task, backend verifies pilot has all required hardware configured. On issues, UI lets user fix inline. After a real trial run, hw lib versions are promoted to stable.
**Verified:** 2026-05-28
**Status:** human_needed — all automated checks pass; 2 items require live-system testing
**Re-verification:** Yes — after gap closure (routing bug fixed)

---

## Goal Achievement

### Observable Truths

| #  | Truth | Status | Evidence |
|----|-------|--------|----------|
| 1  | PUT /api/pilots/{pilot_id}/hardware-config/{module_id} injects class_name from HardwareModule into stored config | VERIFIED | `api/routers/pilot_hardware_config.py` line 57: `config_to_store = {**body.config, "class_name": module.class_name}` |
| 2  | seed endpoint stores class_name per row (from module record, not Pi-reported class key) | VERIFIED | `api/routers/pilot_hardware_config.py` lines 110–111: strips `"class"` key, sets `config["class_name"] = module.class_name` |
| 3  | POST /api/sessions/{id}/preflight-validate/{pilot_id} resolves task_definition_id server-side | VERIFIED | Route at `api/routers/toolkit_dispatch.py` line 143 now declared as `@router.post("/sessions/{session_id}/preflight-validate/{pilot_id}")`. Router included with `prefix="/api"` in `api/main.py` line 78. FastAPI registers endpoint at `/api/sessions/{session_id}/preflight-validate/{pilot_id}` — matches the web_ui proxy target. |
| 4  | class_mismatch check compares config.class_name to hardware_module.class_name; skipped if class_name absent in config (legacy rows) | VERIFIED | `api/routers/toolkit_dispatch.py` lines 262–275: `stored_class = cfg.get("class_name"); if stored_class is not None and stored_class != module.class_name:` |
| 5  | INC_TRIAL_COUNTER promotes active hw lib versions from beta → stable via promote_active_hw_libs_to_stable() | VERIFIED | `orchestrator_station.py` lines 563–579: try/except block after graduation check calls `self.api.promote_active_hw_libs_to_stable(active_run["toolkit_id"], pilot_key)`. `mics_api_client.py` lines 374–384: checks `active_state == "beta"`, calls PATCH mark-stable per lib |

**Score:** 5/5 truths verified

---

### Required Artifacts

| Artifact | Expected | Status | Details |
|----------|----------|--------|---------|
| `api/routers/pilot_hardware_config.py` | PUT upsert injects class_name; seed stores class_name | VERIFIED | Both endpoints confirmed; class_name injection present at lines 57 and 111 |
| `api/routers/toolkit_dispatch.py` | preflight-validate endpoint (POST /api/sessions/{id}/preflight-validate/{pilot_id}) | VERIFIED | Route corrected at line 143 — no `/api/` prefix in decorator; registered at correct path via router prefix |
| `web_ui/react-src/src/components/HardwareCheckModal.tsx` | New inline-fix modal | VERIFIED | Imported in SubjectSessions.tsx; handles all three issue types (missing, incomplete_config, class_mismatch) |
| `web_ui/react-src/src/pages/subject-sessions/SubjectSessions.tsx` | Preflight check + HardwareCheckModal integration | VERIFIED | HardwareCheckModal imported at lines 11 and 13; handleStart calls preflight POST, shows modal on ok:false |
| `orchestrator/orchestrator/orchestrator_station.py` | Stable promotion in _handle_inc_trial() | VERIFIED | Line 575: `self.api.promote_active_hw_libs_to_stable(...)` call confirmed |
| `orchestrator/orchestrator/mics/mics_api_client.py` | promote_active_hw_libs_to_stable() | VERIFIED | Function confirmed; filters to active_state=="beta" only; per-lib try/except |

---

### Key Link Verification

| From | To | Via | Status | Details |
|------|----|-----|--------|---------|
| SubjectSessions.tsx handleStart | POST /api/sessions/{id}/preflight-validate/{pid} | apiFetch | WIRED | React sends correct path; web_ui proxy at `web_ui/app.py` line 605 forwards to `API_URL/api/sessions/{session_id}/preflight-validate/{pilot_id}`; API now registers route at that path |
| web_ui/app.py proxy | api/routers/toolkit_dispatch.py preflight_validate | http://api:8000/api/sessions/... | WIRED | Proxy sends to `API_URL + /api/sessions/.../preflight-validate/...`; endpoint now correctly registered at `/api/sessions/...` (route decorator line 143 has no redundant `/api/` prefix) |
| HardwareCheckModal handleStart | PUT /api/pilots/{pilotId}/hardware-config/{moduleId} | apiFetch | WIRED | `apiFetch('/api/pilots/${pilotId}/hardware-config/${issue.module_id}', {method:'PUT',...})` — matches registered route |
| orchestrator _handle_inc_trial | promote_active_hw_libs_to_stable | self.api.promote... | WIRED | Lines 574–577: active_run.toolkit_id → self.api.promote_active_hw_libs_to_stable(...) |
| promote_active_hw_libs_to_stable | PATCH /api/hardware-libs/{id}/mark-stable | self._patch | WIRED | mics_api_client.py lines 379–381 |

---

### Requirements Coverage

| Requirement | Source Plan | Description | Status | Evidence |
|-------------|------------|-------------|--------|----------|
| HW-21 | 13-01-PLAN.md | POST /api/task-definitions/{id}/validate-for-pilot/{pilot_id}: hardware cross-check endpoint | SATISFIED | Implemented as session-based endpoint `/api/sessions/{id}/preflight-validate/{pilot_id}` (intentional design deviation — session-based resolution avoids UI needing to know task_definition_id). Routing bug fixed; endpoint reachable. |
| HW-22 | 13-01-PLAN.md | Session start UI calls validate-for-pilot before START; issues modal | SATISFIED | SubjectSessions.tsx calls preflight before start, shows HardwareCheckModal on ok:false. Route now reachable — no longer blocked by routing bug. |
| HW-23 | 13-01-PLAN.md | Orchestrator sends resolved hardware config dict to Pi before START; Pi init_hardware uses it if present, falls back to HARDWARE class constant | SATISFIED | Implemented via _inject_backend_toolkit_spec → PREFS_HARDWARE in START payload. Pi mics_task.py _merge_prefs_hardware handles merge. |
| HW-24 | 13-01-PLAN.md | Pi init_hardware accepts received_hw_config kwarg: dynamically imports class from override dir | SATISFIED | Implemented via _resolve_hardware_classes (exec(source_code) from dispatch-spec). Class stored in HARDWARE dict. |

---

### Anti-Patterns Found

None. No TODO/FIXME/placeholder comments, no empty return stubs, no console.log-only implementations. The routing anti-pattern (double `/api/` prefix) from the initial verification has been resolved.

---

### Human Verification Required

#### 1. HardwareCheckModal inline fix flow

**Test:** With a backend-authored toolkit that has hardware modules, start a session on a pilot that has no config for one of those modules. Click Start.
**Expected:** HardwareCheckModal appears listing the module as "missing". Enter a key-value pair (e.g., `pin: 7`). Click "Save & Start". Session starts, new config row exists in pilot_hardware_config.
**Why human:** Requires configured backend-authored toolkit + pilot setup; UI interaction needed.

#### 2. Stable promotion on real trial

**Test:** Run a backend-authored task on a Pi until INC_TRIAL_COUNTER fires. Check hw lib state before and after.
**Expected:** Any hw lib versions with `active_state == "beta"` attached to the toolkit are promoted to `active_state == "stable"` via PATCH /api/hardware-libs/{id}/mark-stable.
**Why human:** Requires live Pi with hardware and a running task session.

---

### Re-verification Summary

The single blocker gap from initial verification has been resolved. The route decorator in `api/routers/toolkit_dispatch.py` line 143 was changed from `/api/sessions/{session_id}/preflight-validate/{pilot_id}` to `/sessions/{session_id}/preflight-validate/{pilot_id}`. With the router registered under `prefix="/api"` in `api/main.py`, FastAPI now correctly exposes the endpoint at `/api/sessions/{session_id}/preflight-validate/{pilot_id}` — exactly the path the web_ui proxy (line 605 of `web_ui/app.py`) and the React client target.

Quick regression checks on all 4 previously-passing truths confirmed no regressions:
- class_name injection in PUT and seed endpoints: unchanged (lines 57, 111 of pilot_hardware_config.py)
- class_mismatch check skipping legacy rows: unchanged (lines 262–275 of toolkit_dispatch.py)
- stable promotion call in orchestrator: unchanged (line 575 of orchestrator_station.py)
- HardwareCheckModal wiring in SubjectSessions.tsx: unchanged (imports at lines 11, 13)

All 5 truths now verified. Phase goal is achieved at the code level. Two human-verification items remain, requiring live-system access.

---

_Verified: 2026-05-28_
_Verifier: Claude (gsd-verifier)_
