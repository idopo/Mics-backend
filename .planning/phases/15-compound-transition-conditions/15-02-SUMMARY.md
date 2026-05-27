---
phase: 15-compound-transition-conditions
plan: "02"
subsystem: ui
tags: [react, typescript, fda, task-editor, compound-conditions]

# Dependency graph
requires:
  - phase: 15-compound-transition-conditions plan 01
    provides: ConditionGroup type, updateTransitionGroups, condition_groups on FdaTransition
provides:
  - ConditionGroupsEditor React component (OR-of-AND groups editor)
  - ConditionRow named export from ConditionBuilder (reusable per-row editor with delete)
  - TaskEditor edge panel wired to ConditionGroupsEditor
affects: [task-editor, condition-editing, fda-transitions]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Flat DNF (OR-of-AND) compound condition editor using pure controlled React component"
    - "ConditionRow extracted as named export so compound and single-condition callers share identical UI"

key-files:
  created:
    - web_ui/react-src/src/components/ConditionGroupsEditor.tsx
  modified:
    - web_ui/react-src/src/components/ConditionBuilder.tsx
    - web_ui/react-src/src/pages/task-editor/TaskEditor.tsx

key-decisions:
  - "ConditionRow layout: delete button (×) placed alongside Right operand column (not floating) to avoid layout shifts when onDelete is present"
  - "ConditionGroupsEditor is fully controlled (no internal state); all mutations go through onChange prop"

patterns-established:
  - "Flat DNF: ConditionGroupsEditor renders OR-of-AND groups as bordered cards with OR/AND dividers"
  - "Named export pattern: extract ConditionRow from ConditionBuilder so compound editor reuses identical operand selectors"

requirements-completed: [COND-02]

# Metrics
duration: 2min
completed: 2026-05-27
---

# Phase 15, Plan 2: Compound Conditions — ConditionGroupsEditor UI Summary

**Kibana-style OR-of-AND compound condition editor wired into TaskEditor transition edge panel, reusing ConditionBuilder's operand selectors via extracted ConditionRow named export**

## Performance

- **Duration:** ~2 min
- **Started:** 2026-05-27T10:36:44Z
- **Completed:** 2026-05-27T10:38:28Z
- **Tasks:** 3 (Steps 1-3)
- **Files modified:** 3 (ConditionBuilder.tsx, ConditionGroupsEditor.tsx new, TaskEditor.tsx)

## Accomplishments
- Extracted `ConditionRow` as a named export from `ConditionBuilder` with optional `onDelete` prop — IfActionEditor callers unchanged because ConditionBuilder default export wraps ConditionRow transparently
- Created `ConditionGroupsEditor` pure controlled component: bordered group cards separated by OR dividers, AND dividers within a group, +AND and +OR group buttons, delete-last-condition removes group, empty groups array shows "unconditional" hint
- TaskEditor edge panel now shows full compound condition editor with source→target label; stopgap single-condition ConditionBuilder removed; TypeScript clean and build passes

## Task Commits

Each step was committed atomically:

1. **Steps 1-3: ConditionRow extraction + ConditionGroupsEditor + TaskEditor wiring** - `aa95618` (feat)

**Plan metadata:** pending (docs commit)

## Files Created/Modified
- `web_ui/react-src/src/components/ConditionBuilder.tsx` - Added `ConditionBuilderProps` and `ConditionRowProps` exported interfaces; extracted `ConditionRow` named export with optional `onDelete`; `ConditionBuilder` default export becomes thin wrapper
- `web_ui/react-src/src/components/ConditionGroupsEditor.tsx` - New file: OR-of-AND groups editor, pure controlled component
- `web_ui/react-src/src/pages/task-editor/TaskEditor.tsx` - Replaced stopgap `ConditionBuilder` in edge panel with `ConditionGroupsEditor`; removed unused `EMPTY_CONDITION` constant

## Decisions Made
- ConditionRow places the × delete button inline alongside the Right operand (not a separate row) to keep the per-condition UI compact and avoid layout shifts.
- ConditionGroupsEditor is fully controlled (no local state) — all mutations funnel through `onChange(groups)` so TaskEditor's `updateTransitionGroups` handles debounced auto-save uniformly.

## Deviations from Plan

None — plan executed exactly as written.

## Issues Encountered
None.

## User Setup Required
None - no external service configuration required.

## Next Phase Readiness
- Both Plan 1 (types + Pi DNF) and Plan 2 (UI) are complete — Phase 15 is done
- Compound OR-of-AND conditions fully functional: researchers can build multi-condition transitions in the task editor
- Edge labels correctly show `a ∧ b ∨ c` notation from Plan 1's `condLabel` function

---
*Phase: 15-compound-transition-conditions*
*Completed: 2026-05-27*
