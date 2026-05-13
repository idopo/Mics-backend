---
phase: 12-hardware-fda-builder
plan: "03"
subsystem: ui
tags: [react, typescript, fastapi, fda-builder, bug-fix]

requires:
  - phase: 12-hardware-fda-builder plan 01
    provides: StateBodyPanel, ActionEditor, ArgInput, TaskEditor all exist

provides:
  - addAction() initializes ref to first hw module (methods fetch immediately)
  - bool arg select normalized — value ? 'true' : 'false'
  - _normalize_flags() injects trial_counter Trial_Tracker if none exists
  - ActionEditor trial section shows static label (not dropdown) when only one trial flag
  - load_fda_from_json() auto-creates trial_counter Trial_Tracker if missing
  - TaskEditor auto-saves fdaJson changes after 1500ms debounce

affects: [12-hardware-fda-builder, pi-deploy]

tech-stack:
  added: []
  patterns:
    - "useRef + setTimeout debounce for auto-save (avoids stale closure via saveMutation.mutate)"
    - "value ? 'true' : 'false' for coercing numeric 0/1 to bool select options"

key-files:
  created: []
  modified:
    - web_ui/react-src/src/components/StateBodyPanel.tsx
    - web_ui/react-src/src/components/ArgInput.tsx
    - api/routers/toolkits.py
    - web_ui/react-src/src/components/ActionEditor.tsx
    - web_ui/react-src/src/pages/task-editor/TaskEditor.tsx
    - ~/pi-mirror/autopilot/autopilot/tasks/mics_task.py

key-decisions:
  - "trial_counter injection is server-side in _normalize_flags() — every toolkit response always has it, UI never needs to handle the 0-trial-flags case"
  - "auto-save uses fdaJson as dep not editName — name changes intentionally excluded from debounce (user may still be typing)"

requirements-completed: [HW-17, HW-18, HW-19, HW-20]

duration: 3min
completed: 2026-05-13
---

# Phase 12, Plan 3: FDA Builder Bug Fixes Summary

**Four FDA builder usability bugs fixed: method fetch on Add Action, bool arg normalization, implicit trial counter with static label, and 1500ms debounced auto-save**

## Performance

- **Duration:** ~3 min
- **Started:** 2026-05-13T11:41:46Z
- **Completed:** 2026-05-13T11:44:44Z
- **Tasks:** 4 bugs fixed (6 file changes across 2 repos)
- **Files modified:** 6

## Accomplishments

- Bug 1: `addAction()` in StateBodyPanel now initializes ref to the first hw module attached to the toolkit, so ActionEditor's `useEffect` fires and the method dropdown populates immediately
- Bug 2: `ArgInput` bool select uses `value ? 'true' : 'false'` instead of `String(value)`, so stored numeric `0`/`1` values render correctly as `false`/`true`
- Bug 3a: `_normalize_flags()` in toolkits.py auto-injects `trial_counter: Trial_Tracker` if no Trial_Tracker exists — every toolkit GET response now always has one; Bug 3b: ActionEditor shows a static monospace label (not a select dropdown) when `trialFlagKeys.length === 1`; Bug 3c: `load_fda_from_json()` on Pi auto-creates `trial_counter` if missing for backward compat
- Bug 4: TaskEditor gains a 1500ms debounced auto-save on `fdaJson` changes (only after canvas init), showing `Unsaved…` during the debounce window and `Saved ✓` on success

## Task Commits

1. **Bug 1: addAction initializes ref to first hw module** - `0801026` (fix)
2. **Bug 2: bool arg select normalizes numeric 0/1** - `c13bb80` (fix)
3. **Bug 3: trial counter auto-inject + static label** - `a216748` (fix)
4. **Bug 4: debounced auto-save on fdaJson change** - `2b001f3` (fix)
5. **Pi Bug 3c: auto-create trial_counter in load_fda_from_json** - `5e61914` (fix, pi-mirror repo)

## Files Created/Modified

- `web_ui/react-src/src/components/StateBodyPanel.tsx` - Removed stale `DEFAULT_ACTION` const; `addAction()` computes initial action from first attached hw module
- `web_ui/react-src/src/components/ArgInput.tsx` - Bool select: `value ? 'true' : 'false'` instead of `String(value)`
- `api/routers/toolkits.py` - `_normalize_flags()` appends `trial_counter` Trial_Tracker if none present
- `web_ui/react-src/src/components/ActionEditor.tsx` - Trial section shows static label when `trialFlagKeys.length === 1`
- `web_ui/react-src/src/pages/task-editor/TaskEditor.tsx` - Added `useRef` + auto-save debounce effect on `fdaJson`
- `~/pi-mirror/autopilot/autopilot/tasks/mics_task.py` - `load_fda_from_json()` auto-creates `trial_counter` Trial_Tracker if missing

## Decisions Made

- trial_counter injection is server-side in `_normalize_flags()` — every toolkit response always has it, so the UI never needs to handle the 0-trial-flags branch
- auto-save depends on `fdaJson` only (not `editName`) — name changes are excluded from the debounce since the user may still be typing; name is saved with the next fdaJson change or on manual Save
- Pi auto-creation imports `Trial_Tracker` inline to avoid a module-level import that could fail if Tracker module path changes

## Deviations from Plan

None - plan executed exactly as written.

## Issues Encountered

None. Build passed cleanly on first attempt. Pi syntax check passed.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness

- All four FDA builder usability bugs resolved
- Task editor auto-saves on every edit; no data loss on refresh
- trial_counter is always present in toolkit responses — ActionEditor and Pi both handle it implicitly
- Ready for end-to-end testing via task editor UI

---
*Phase: 12-hardware-fda-builder*
*Completed: 2026-05-13*
