---
phase: 29-fda-builder-canvas-ux
plan: 06
subsystem: ui
tags: [react, react-flow, react-query, fda-editor, ui_layout]

# Dependency graph
requires:
  - phase: 29-fda-builder-canvas-ux (plan 01)
    provides: TaskEditor.tsx line-count headroom (873 -> 745), seededIdRef discipline
  - phase: 29-fda-builder-canvas-ux (plan 03)
    provides: fdaLayout.mts — resolvePositions, placeNewState, layeredLayout, columnRanks
  - phase: 29-fda-builder-canvas-ux (plan 04)
    provides: task_definitions.ui_layout column, layout-only PUT fast path, UiLayout type
  - phase: 29-fda-builder-canvas-ux (plan 05)
    provides: TransitionEdge.tsx, fdaToEdges geometry wiring
provides:
  - useLayoutPersistence.ts — debounced ui_layout PUT hook, fully separate from the FDA autosave
  - TaskEditor.tsx canvas-init hydration via resolvePositions(taskDef.ui_layout.nodes)
  - onNodeDragStop wired to layout.record — drags persist without touching fdaJson
affects: [29-07 (new-state placement + restore-default-layout action), 29-08 (consolidated checkpoint)]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Ref-backed persistence hook (positionsRef, not useState) so a drag never re-renders the editor or touches unrelated state"
    - "Layout-only PUT: payload carries ui_layout and nothing else, hitting the backend's fast path that skips FDA validation and leaves file_hash untouched"

key-files:
  created:
    - web_ui/react-src/src/pages/task-editor/useLayoutPersistence.ts
  modified:
    - web_ui/react-src/src/pages/task-editor/TaskEditor.tsx

key-decisions:
  - "600ms debounce on record() (drag), immediate PUT on replaceAll() (future 'Restore default layout' action in 29-07)"
  - "seed() never PUTs — the layered layout is deterministic from the FDA, so re-deriving it on next open costs nothing; the first write happens on first drag or first restore"
  - "No invalidateQueries in the layout mutation's onSuccess — would refetch on every drag and re-trigger the canvas-init effect's hydration, churning the whole editor"
  - "taskDef deliberately excluded from the canvas-init effect's dependency array (same rationale as the existing seededIdRef guard) — including it would re-hydrate positions and drop unsaved drags on every window-focus refetch"

requirements-completed: [CANVAS-05, CANVAS-07, CANVAS-10]

# Metrics
duration: ~20min
completed: 2026-08-05
---

# Phase 29 Plan 06: Layout Persistence Summary

**`useLayoutPersistence.ts` debounced `ui_layout` PUT hook, wired into `TaskEditor.tsx`'s canvas-init and drag paths, textually and behaviourally separate from the FDA autosave**

## Performance

- **Duration:** ~20 min
- **Completed:** 2026-08-05
- **Tasks:** 3
- **Files modified:** 2 (1 created, 1 modified)

## Accomplishments
- Stored node positions now hydrate on canvas init via `resolvePositions(states/transitions/initial, taskDef.ui_layout.nodes)` — the index-grid layout (`(i%4)*270, floor(i/4)*170`) is gone from `fdaToNodes`, replaced by a resolved-positions lookup
- Dragging a node calls `layout.record(...)` on `onNodeDragStop`, which merges the new position into a ref-backed map and PUTs `{ ui_layout: { nodes } }` after a 600ms debounce — verified live against task definition 186: `ui_layout` round-trips verbatim and `file_hash` is byte-identical before/after
- The drag path cannot touch the FDA autosave: no `setFdaJson`, no `setSavedMsg`, no `saveMutation.mutate` anywhere in the handler or the hook; `useLayoutPersistence.ts` contains none of `fdaJson`/`fda_json`/`savedMsg`/`invalidateQueries` (grep-verified)
- Layout status (`layout.layoutMsg`) renders as its own header `<span>`, next to but never overwriting `savedMsg`

## Task Commits

Each task was committed atomically:

1. **Task 1: useLayoutPersistence hook** - `b215f24` (feat)
2. **Task 2: Hydrate positions on canvas init** - `176465c` (feat)
3. **Task 3: Persist drags, and prove the FDA path is untouched** - `971bdd7` (feat)

## Files Created/Modified
- `web_ui/react-src/src/pages/task-editor/useLayoutPersistence.ts` (73 lines) - ref-backed position map with `seed`/`record`/`replaceAll`/`current`, 600ms debounce, its own `layoutMsg` status string, no invalidateQueries
- `web_ui/react-src/src/pages/task-editor/TaskEditor.tsx` (763 -> 788 lines) - `fdaToNodes` takes a resolved positions map; canvas-init effect calls `layout.seed(resolvePositions(...))` before building nodes; `onNodeDragStop` calls `layout.record(...)`; layout status span added to header

## Decisions Made
- 600ms debounce chosen for `record()` (drag), distinct from the FDA autosave's 1500ms — a drag is a single discrete gesture, not a stream of incremental edits, so a shorter debounce feels responsive without spamming PUTs on rapid successive drags
- `replaceAll()` is implemented and exported but not yet called from `TaskEditor.tsx` — it exists for plan 29-07's "Restore default layout" action, per the plan's stated interface contract
- Task definition **186** used for the live curl round-trip (matches the id referenced elsewhere in this phase's STATE.md history); its layout was left as `{"CUE":{"x":11,"y":22}}` afterward per the plan's explicit allowance ("Restore the real layout afterwards, or leave it — plan 29-07's restore action fixes it")

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Removed literal `fdaJson` token from a doc comment in the new hook**
- **Found during:** Task 1 verification
- **Issue:** The hook's top-of-file docstring explained the separation rationale using the literal word `` `fdaJson` `` in prose, which the plan's own automated verify grep (`! grep -nE "fdaJson|fda_json|savedMsg|invalidateQueries"`) flagged as a false-positive match — the file's actual code contained no such reference, but the comment text did.
- **Fix:** Reworded the comment to say "the FDA state" instead of naming the identifier literally; no code or behavior change.
- **Files modified:** web_ui/react-src/src/pages/task-editor/useLayoutPersistence.ts
- **Verification:** Re-ran the grep — zero matches; `tsc -b` and `npm run build` still clean.
- **Committed in:** b215f24 (Task 1 commit)

---

**Total deviations:** 1 auto-fixed (1 bug — a doc-comment wording issue caught by the plan's own verification grep, not a functional defect)
**Impact on plan:** No scope creep; purely comment wording to satisfy the plan's literal verification command.

## Issues Encountered
None.

## User Setup Required
None - no external service configuration required.

## Next Phase Readiness
- `useLayoutPersistence`'s `LayoutPersistence` surface (`current`/`seed`/`record`/`replaceAll`/`layoutMsg`) is pinned and ready for plan 29-07, which needs `replaceAll` for the "Restore default layout" action and `current`/`record` for new-state placement (`placeNewState` from `fdaLayout.mts`)
- `TaskEditor.tsx` is at 788 lines, 42 lines of headroom remain under this plan's own 830-line gate and well under the phase's 873-line cap; plan 29-07 estimated needing ~15
- The two other index-grid sites (`addState`, the toolkit-sync effect) are untouched, confirmed by `grep -c "% 4) \* 270"` returning exactly 2 — both are plan 29-07's to fix
- The CANVAS-10 negative case (drag persists while the FDA autosave is held by an incomplete trigger/half-built action) is a human-verify step and is deliberately deferred to plan 29-08's consolidated checkpoint, per this plan's own `<verification>` block
- `docker compose up --build web_ui` was run and the container is serving a fresh, correctly-timestamped bundle, so the servable state plan 29-08 needs is already in place

---
*Phase: 29-fda-builder-canvas-ux*
*Completed: 2026-08-05*

## Self-Check: PASSED

All created/modified files found on disk; all three task commit hashes (b215f24, 176465c,
971bdd7) found in git history.
