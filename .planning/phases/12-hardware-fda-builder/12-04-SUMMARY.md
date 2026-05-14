---
phase: 12-hardware-fda-builder
plan: "04"
subsystem: ui
tags: [react, typescript, reactflow, fda, task-editor]

requires:
  - phase: 12-hardware-fda-builder
    plan: "03"
    provides: FDA builder with StateNode, TaskEditor, and ReactFlow canvas

provides:
  - Auto-set initial_state when first state is added to empty FDA
  - Right-click context menu on state nodes with "Set as Initial State" and "Delete State"
  - setInitialState() handler updates fdaJson.initial_state and all node isInitial flags
  - deleteState() clears initial_state when initial state is deleted, prunes orphaned transitions
  - Validation warning and Save-button block when states exist but initial_state is unset

affects: [fda-builder, task-editor, sourceless-toolkits]

tech-stack:
  added: []
  patterns:
    - "Context menu via fixed-positioned div rendered outside ReactFlow, dismisses on mouseLeave or pane click"
    - "Derived boolean missingInitial gates both UI warning and save mutation"

key-files:
  created: []
  modified:
    - web_ui/react-src/src/pages/task-editor/TaskEditor.tsx

key-decisions:
  - "Context menu renders as fixed-positioned sibling of ReactFlow (not inside canvas) — avoids transform/coordinate issues"
  - "Delete State exposed via context menu rather than a panel button — keeps right panel clean and avoids accidental deletion"
  - "Auto-save still fires when initial_state is missing (fdaJson changes), but manual Save is blocked — partial state is preserved without requiring user to re-enter work"

patterns-established:
  - "Fragment wrapper required when ternary branch returns ReactFlow + sibling overlay"

requirements-completed: [HW-21]

duration: 7min
completed: 2026-05-14
---

# Phase 12, Plan 4: Initial State Selection for Sourceless Toolkits Summary

**Right-click context menu on FDA states lets users set/delete initial state, with auto-assignment on first add and a save-blocking warning when unset**

## Performance

- **Duration:** 7 min
- **Started:** 2026-05-14T07:25:00Z
- **Completed:** 2026-05-14T07:32:00Z
- **Tasks:** 1 (4 fixes in a single cohesive change)
- **Files modified:** 1

## Accomplishments

- First state added to an empty FDA is auto-set as `initial_state` (INIT badge appears immediately)
- Right-click on any state node shows context menu with "Set as Initial State" and "Delete State"
- `setInitialState()` updates both `fdaJson.initial_state` and all node `isInitial` flags without a full canvas re-sync
- `deleteState()` removes the state, prunes orphaned transitions and edges, and clears `initial_state` if it was the deleted state
- Warning "No initial state set — right-click a state to set one" appears in header when states exist but initial is unset
- Save button is disabled (and save mutation blocked) when `missingInitial` is true

## Task Commits

1. **All 4 fixes (auto-initial, context menu, delete-state, validation)** - `6671de3` (feat)

## Files Created/Modified

- `web_ui/react-src/src/pages/task-editor/TaskEditor.tsx` — All 4 fixes: addState() auto-initial, ctxMenu state + onNodeContextMenu, setInitialState(), deleteState(), missingInitial warning + save block

## Decisions Made

- Context menu renders as a `position: fixed` div outside the ReactFlow canvas hierarchy — avoids ReactFlow transform coordinate complexity
- "Delete State" was added to the context menu as an unplanned but natural companion to "Set as Initial State" — the context menu was the right place for destructive node actions
- Fragment wrapper `<>...</>` added around ReactFlow + context menu overlay because a ternary branch cannot return two sibling elements without a root

## Deviations from Plan

### Auto-added (companion feature)

**1. [Rule 2 - Missing Critical] Added "Delete State" to context menu**
- **Found during:** Fix 2 (context menu implementation)
- **Issue:** Plan only specified "Set as Initial State" in the context menu, but a context menu with only one action is unusual UX and state deletion had no other access point in the UI
- **Fix:** Added "Delete State" button (red color) to the context menu, calling the new `deleteState()` function
- **Files modified:** TaskEditor.tsx
- **Verification:** Build passes, deleteState() correctly removes node, edges, and transitions
- **Committed in:** 6671de3

---

**Total deviations:** 1 auto-added (missing critical UX)
**Impact on plan:** Minor scope addition — delete state via context menu is a natural companion to set-as-initial and doesn't affect any other plans.

## Issues Encountered

- JSX compilation error: ternary branch returning `<ReactFlow>` + `{ctxMenu && ...}` without a wrapper — fixed by wrapping in a React fragment `<>...</>`

## Next Phase Readiness

- Phase 12 complete — all 4 plans done
- `initial_state` is now always valid when the FDA reaches the Pi (Fix 4 blocks saves, Pi's `ValueError` is the backstop)
- No further FDA builder plans in phase 12

---
*Phase: 12-hardware-fda-builder*
*Completed: 2026-05-14*
