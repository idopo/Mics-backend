---
phase: 29-fda-builder-canvas-ux
plan: 07
subsystem: ui
tags: [react, react-flow, fda-canvas, typescript]

# Dependency graph
requires:
  - phase: 29-fda-builder-canvas-ux (plan 03)
    provides: fdaLayout.mts — columnRanks, layeredLayout, placeNewState, resolvePositions
  - phase: 29-fda-builder-canvas-ux (plan 06)
    provides: useLayoutPersistence.ts — seed/record/replaceAll/current, debounced ui_layout PUT
provides:
  - Both remaining index-grid node-placement sites (addState, toolkit-sync effect) now route
    through placeNewState — a new/synced node can never land on a positioned one
  - Pane-level right-click context menu on the canvas, reusing CanvasContextMenu (plan 29-01)
  - "Restore default layout" action that recomputes via layeredLayout and persists immediately
    via layout.replaceAll — survives a refresh, not just a redraw
affects: [29-08]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Node-placement mutations compute position first (placeNewState/layeredLayout), then
      call layout.record()/layout.replaceAll() alongside setNodes — placement and persistence
      always travel together at each call site"
    - "React state updaters (setNodes) stay pure — side effects (setFdaJson, layout.record) that
      used to run inside a setNodes updater now run outside it, before or after the call"

key-files:
  created: []
  modified:
    - web_ui/react-src/src/pages/task-editor/TaskEditor.tsx

key-decisions:
  - "Deleted states' layout-map entries are deliberately NOT pruned; resolvePositions already
    drops entries for states absent from the FDA on next load, so the stale key self-heals
    without needing cleanup logic in deleteState"
  - "restoreLayout uses layeredLayout, not resolvePositions — restore must DISCARD the stored
    arrangement, which is the entire point of the action"
  - "Optional viewport refit after restore (useReactFlow().fitView()) was explicitly skipped:
    no ReactFlowProvider exists anywhere in the tree, and adding one to support a single instance
    method would restructure beyond this plan's scope for a polish-only step"

requirements-completed: [CANVAS-08, CANVAS-09]

# Metrics
duration: 25min
completed: 2026-08-05
---

# Phase 29 Plan 07: Placement-Based Node Creation + Pane Restore Menu Summary

**Retired the last index-grid placement sites in `TaskEditor.tsx` and added a persisting "Restore default layout" action behind a new pane-level context menu.**

## Performance

- **Duration:** 25 min
- **Started:** 2026-08-05T15:14:17Z (after 29-06's final commit)
- **Completed:** 2026-08-05T15:17:49Z
- **Tasks:** 2
- **Files modified:** 1

## Accomplishments
- `addState` and the toolkit-sync effect both call `placeNewState(layout.current())` instead of
  `(i % 4) * 270, floor(i / 4) * 170` — the index grid is fully gone from `TaskEditor.tsx`
  (`grep -n "% 4) \* 270"` returns nothing)
- Both placement sites immediately call `layout.record(...)` so a newly created/synced node
  survives a refresh without needing a drag first
- The toolkit-sync effect's `missing`/placement computation was lifted outside the `setNodes`
  updater (it was calling `setFdaJson` from inside a `setNodes` updater — a pre-existing purity
  violation this plan was the natural moment to fix, since the placement call had to move out
  anyway)
- New `onPaneContextMenu` opens a `paneMenu`, rendered via the same `CanvasContextMenu` component
  the node menu already uses (one component, one style, `grep -c "<CanvasContextMenu"` = 2)
- `restoreLayout` recomputes via `layeredLayout` (discarding drift, not `resolvePositions`) and
  persists via `layout.replaceAll` (immediate PUT) — CANVAS-09's "the way back must persist" is
  satisfied by construction, not left to a later drag
- `onPaneClick` clears `paneMenu`; `onNodeContextMenu` clears `paneMenu` and `onPaneContextMenu`
  clears `ctxMenu`, so the two menus can never both be open
- `web_ui` container rebuilt and restarted; `main.js` mtime confirmed fresh (15:17), `/health`
  returns 200 — a servable bundle is ready for plan 29-08's checkpoint

## Task Commits

Each task was committed atomically:

1. **Task 1: Route both node-creation paths through placeNewState** - `8782bd0` (feat)
2. **Task 2: Pane context menu with a persisting "Restore default layout"** - `b020d31` (feat)

**Plan metadata:** (this commit, docs: complete plan)

## Files Created/Modified
- `web_ui/react-src/src/pages/task-editor/TaskEditor.tsx` - both node-creation paths route through
  `placeNewState`; new pane context menu with a persisting "Restore default layout" action

## Decisions Made
- Kept `existingCount`'s role narrowed to the `isFirst` check only, per the plan's Task 1
  instruction — the rest of its former use (the grid math) is gone
- Skipped the optional `useReactFlow().fitView()` viewport refit after restore: the codebase has
  no `ReactFlowProvider` anywhere (`grep -rn "ReactFlowProvider" src/` — no matches), and the plan
  explicitly said to skip rather than restructure the tree for this polish-only step

## Deviations from Plan

None - plan executed exactly as written, including the explicit-skip branch for the optional
viewport refit (which the plan itself treats as a valid outcome, not a deviation).

## Issues Encountered

One sequencing note, not an issue: `layeredLayout` was imported one commit early during drafting
(needed by Task 2, not Task 1) which would have failed Task 1's own `tsc -b` gate as an unused
import; caught before running Task 1's verification and the import was deferred to Task 2's
commit, keeping each task's diff self-contained and independently green.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness

`TaskEditor.tsx` is at **806 lines** (777 after Task 1's net −11, +29 for Task 2), against this
plan's own ≤850 gate and the phase's ≤873 cap — 67 lines of headroom remain. This was the last
planned `TaskEditor.tsx` diff of the phase per this plan's `<objective>`. Behavioural sign-off
(pane-menu styling matching the node menu, restore surviving a real refresh, a newly added state
never landing on an existing one) is deliberately left to plan 29-08's consolidated checkpoint, per
this plan's own `<verification>` block — not verified here beyond the automated gates.

---
*Phase: 29-fda-builder-canvas-ux*
*Completed: 2026-08-05*

## Self-Check: PASSED

- FOUND: .planning/phases/29-fda-builder-canvas-ux/29-07-SUMMARY.md
- FOUND: 8782bd0 (Task 1 commit)
- FOUND: b020d31 (Task 2 commit)
