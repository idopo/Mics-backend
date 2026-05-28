---
phase: 13
plan: 1
subsystem: api, orchestrator, web_ui
tags: [hardware, preflight, validation, session-start, stable-promotion]
dependency_graph:
  requires: [Phase 09, Phase 10, Phase 11, Phase 12]
  provides: [HW-21, HW-22, HW-23, HW-24]
  affects: [SubjectSessions, pilot_hardware_config, toolkit_dispatch, orchestrator]
tech_stack:
  added: []
  patterns:
    - Preflight endpoint resolves task_definition_id server-side (client cannot reliably know it)
    - class_name injected by PUT endpoint from DB record (authoritative), not user input
    - Stable promotion wrapped in try/except — trial increment must never fail due to promotion error
key_files:
  created:
    - web_ui/react-src/src/components/HardwareCheckModal.tsx
  modified:
    - api/routers/pilot_hardware_config.py
    - api/routers/toolkit_dispatch.py
    - web_ui/app.py
    - web_ui/react-src/src/pages/subject-sessions/SubjectSessions.tsx
    - orchestrator/orchestrator/orchestrator_station.py
decisions:
  - class_name injected on every PUT call (not just first time) so re-saves preserve it
  - preflight network failure is non-blocking — error caught silently, start proceeds
  - promotion fires after graduation check (step may have advanced before we modify lib state)
  - class_mismatch check skipped when class_name absent in config (legacy rows)
metrics:
  duration: 20m
  completed: 2026-05-28
  tasks_completed: 4
  files_modified: 5
  files_created: 1
---

# Phase 13 Plan 1: Pre-Run Cross-Check Summary

**One-liner:** Pre-run hardware preflight gate with inline fix modal and beta→stable hw lib promotion on first trial.

## What Was Built

### Step 0: `class_name` injection in `pilot_hardware_config`

`PUT /api/pilots/{pilot_id}/hardware-config/{module_id}` now fetches the `HardwareModule` record and injects `class_name` from DB (authoritative) into the stored config. The seed endpoint does the same — strips the Pi-reported `"class"` key and replaces it with DB-authoritative `class_name`. This enables the `class_mismatch` check in the preflight endpoint.

### Step 1: `POST /api/sessions/{id}/preflight-validate/{pilot_id}`

New endpoint in `api/routers/toolkit_dispatch.py`. Server-side resolution chain:
1. session → subject_protocol_run → protocol_id
2. protocol step at current_step_idx → task_definition_id  
3. task_definition → toolkit_id
4. toolkit → is_backend_authored + hardware_module_ids
5. Per module: check pilot_hardware_config for missing / incomplete_config / class_mismatch

Returns `{ok, issues[]}` where each issue has `module_id` (so React can call PUT directly). Non-backend-authored sessions return `{ok: true, skip_reason: "not_backend_authored"}`.

### Step 2: `HardwareCheckModal` + SubjectSessions preflight integration

`HardwareCheckModal.tsx`: inline-fix modal with per-issue editable forms:
- `missing`: key-value add-row inputs for new config
- `incomplete_config`: editable inputs for existing config fields  
- `class_mismatch`: single `class_name` text input pre-filled with stored (wrong) value, expected value shown

"Save & Start" button calls `PUT /api/pilots/{pilotId}/hardware-config/{moduleId}` for each issue (strips `class_name` from payload — API injects it from DB), then calls `onStart()`. No automatic recheck.

`SubjectSessions.tsx`: `handleStart` runs preflight POST before calling `startSessionOnPilot`. If `ok: false`, shows modal instead of starting. Network errors on preflight are swallowed so a broken preflight endpoint never blocks session start.

Web UI proxy: explicit route `POST /api/sessions/{id}/preflight-validate/{pilot_id}` added to `web_ui/app.py` (required because the catch-all strips `/api/` prefix).

### Step 3: Stable promotion on `INC_TRIAL_COUNTER`

`_handle_inc_trial()` in `orchestrator_station.py` now calls `promote_active_hw_libs_to_stable()` after the trial increment + graduation check. Resolves pilot_key via `run["pilot_id"]` → `get_pilot()` → `resolve_pilot_key()`, then reads `toolkit_id` from in-memory `active_run` state. Only `beta` libs are promoted. Wrapped in try/except — promotion failure logs but never interrupts trial counting.

`promote_active_hw_libs_to_stable()` was already implemented correctly in `mics_api_client.py` (checks `active_state == "beta"`, calls `PATCH /api/hardware-libs/{id}/mark-stable`).

## Commits

| Task | Commit | Description |
|---|---|---|
| Step 0 | `fe258ea` | Inject class_name into pilot_hardware_config on upsert and seed |
| Step 1 | `b9e1f1b` | Add POST preflight-validate endpoint |
| Step 2 | `027b89c` | HardwareCheckModal + SubjectSessions preflight integration |
| Step 3 | `ab7d4bd` | Stable promotion on INC_TRIAL_COUNTER |

## Deviations from Plan

None — plan executed exactly as written.

The `promote_active_hw_libs_to_stable()` method referenced in the plan was already implemented in a previous session in `mics_api_client.py` (using `active_state` field, which is correct per the `/toolkits/{id}/hardware-libs` API response shape). No re-implementation needed.

## Self-Check: PASSED

- api/routers/pilot_hardware_config.py: FOUND
- api/routers/toolkit_dispatch.py: FOUND
- web_ui/react-src/src/components/HardwareCheckModal.tsx: FOUND
- web_ui/react-src/src/pages/subject-sessions/SubjectSessions.tsx: FOUND
- orchestrator/orchestrator/orchestrator_station.py: FOUND
- Commits fe258ea, b9e1f1b, 027b89c, ab7d4bd: all present
