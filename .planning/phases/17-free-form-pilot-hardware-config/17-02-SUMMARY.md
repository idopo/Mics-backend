---
phase: 17-free-form-pilot-hardware-config
plan: "02"
subsystem: api+frontend
tags: [sql-fix, react, typescript, hardware-config, free-form]
dependency_graph:
  requires: [17-01]
  provides: [name-keyed dispatch SQL, free-form PilotHardwareConfig page, name-keyed HardwareCheckModal]
  affects:
    - api/routers/toolkit_dispatch.py
    - api/routers/hardware_modules.py
    - web_ui/react-src/src/types/index.ts
    - web_ui/react-src/src/api/hardware_modules.ts
    - web_ui/react-src/src/components/HardwareCheckModal.tsx
    - web_ui/react-src/src/pages/hardware-modules/PilotHardwareConfig.tsx
tech_stack:
  added: []
  patterns: [name-keyed SQL lookup, free-form table editor, JSON textarea inline edit]
key_files:
  created: []
  modified:
    - api/routers/toolkit_dispatch.py
    - api/routers/hardware_modules.py
    - web_ui/react-src/src/types/index.ts
    - web_ui/react-src/src/api/hardware_modules.ts
    - web_ui/react-src/src/components/HardwareCheckModal.tsx
    - web_ui/react-src/src/pages/hardware-modules/PilotHardwareConfig.tsx
decisions:
  - "HardwareCheckModal pendingEdits keyed by module_name (string) — was module_id (number)"
  - "class_name not stripped before PUT — caller includes it in config as-is per Phase 17-01 decision"
  - "PilotHardwareConfig rewritten to show pilot_hardware_config rows directly (not hardware_modules registry)"
  - "Delete hardware module no longer cascade-deletes pilot_hardware_config rows"
metrics:
  duration_minutes: 5
  completed_date: "2026-05-28"
  tasks_completed: 3
  tasks_total: 3
  files_modified: 6
---

# Phase 17 Plan 02: Free-Form Frontend + Name-Keyed SQL Summary

**One-liner:** Completed the name-keyed decoupling — dispatch/preflight SQL now use name instead of hardware_module_id, and the React config page becomes a free-form JSON editor mirroring Pi prefs.json.

## Tasks Completed

| Task | Name | Commit | Files |
|------|------|--------|-------|
| 1 | Fix dispatch and preflight SQL + remove cascade delete | 8e43fda | api/routers/toolkit_dispatch.py, api/routers/hardware_modules.py |
| 2 | Update TypeScript types + API client + HardwareCheckModal | 56e1965 | types/index.ts, api/hardware_modules.ts, HardwareCheckModal.tsx, PilotHardwareConfig.tsx (interim) |
| 3 | Rewrite PilotHardwareConfig.tsx — free-form table + Add Entry form | 3a47b6a | PilotHardwareConfig.tsx |

## What Was Built

**Backend SQL fixes** — Both `pilot_hardware_config` lookups in `toolkit_dispatch.py` now use `WHERE pilot_id = :pid AND name = :name` instead of `hardware_module_id = :mid`. This ensures dispatch spec and preflight validation match by the free-form name key, not the module registry FK. The cascade-delete of `pilot_hardware_config` rows on module deletion was removed from `hardware_modules.py` — config rows now survive module registry changes.

**TypeScript types** — `PilotHardwareConfigRow.hardware_module_id: number` replaced by `name: string`. All callers updated.

**API client** — `upsertPilotHardwareConfig(pilotId, name, config)` and `deletePilotHardwareConfig(pilotId, name)` now accept `name: string` and use `encodeURIComponent(name)` in the URL.

**HardwareCheckModal** — `pendingEdits` switched from `Record<number, ...>` to `Record<string, ...>` keyed by `module_name`. The `handleStart` loop reads `pendingEdits[issue.module_name]` and sends PUT to `encodeURIComponent(issue.module_name)`. The `delete configToSave['class_name']` line removed — config stored as-is including class_name.

**PilotHardwareConfig page (full rewrite)** — Now shows `pilot_hardware_config` rows directly (not the hardware_modules registry). Features:
- Table: Name | class_name badge | Params summary (up to 4 key:value pairs) | Edit/Delete
- Row edit mode: inline JSON `<textarea>` with parse error display
- Add Entry form: free-form name input + optional module pre-fill picker (sets class_name template) + JSON `<textarea>`
- Mutations invalidate `['pilot-hardware-config', pid]`
- Under 315 lines

## Verification Results

```
# SQL assertion — no old patterns remain
dispatch.py OK
hardware_modules.py OK

# TypeScript build
✓ built in 1.67s (0 errors)

# Success criteria checks
grep 'hardware_module_id = :mid' toolkit_dispatch.py → 0 matches
grep 'filter_by(hardware_module_id=module_id).delete()' hardware_modules.py → 0 matches
PilotHardwareConfigRow has name: string — VERIFIED
HardwareCheckModal PUT uses encodeURIComponent(issue.module_name) — VERIFIED
class_name not stripped — VERIFIED
```

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 - Blocking] PilotHardwareConfig.tsx had build errors from Task 2 type changes**
- **Found during:** Task 2 build verification
- **Issue:** The existing PilotHardwareConfig.tsx still used `hardware_module_id` key and passed `moduleId: number` to the API functions after the type change in Task 2, causing 2 TypeScript errors.
- **Fix:** Applied interim compatibility fixes (rename key to `name`, thread `moduleName` through `saveRow`/`startEdit`) to unblock the Task 2 build. Task 3 then did the full rewrite.
- **Files modified:** web_ui/react-src/src/pages/hardware-modules/PilotHardwareConfig.tsx (interim fix committed with Task 2, then rewritten in Task 3)
- **Commit:** 56e1965 (interim), 3a47b6a (final rewrite)

## Self-Check: PASSED

- api/routers/toolkit_dispatch.py has `name = :name` (2 occurrences) — FOUND
- api/routers/toolkit_dispatch.py has zero `hardware_module_id = :mid` — CONFIRMED
- api/routers/hardware_modules.py has no cascade delete — CONFIRMED
- web_ui/react-src/src/types/index.ts has `name: string` in PilotHardwareConfigRow — FOUND
- HardwareCheckModal.tsx uses `encodeURIComponent(issue.module_name)` — FOUND
- HardwareCheckModal.tsx has no `delete configToSave['class_name']` — CONFIRMED
- PilotHardwareConfig.tsx rewritten as free-form table — FOUND
- Commits 8e43fda, 56e1965, 3a47b6a exist — VERIFIED
- TypeScript build exits 0 — VERIFIED
