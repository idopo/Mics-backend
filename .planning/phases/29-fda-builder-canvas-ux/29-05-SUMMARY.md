---
phase: 29-fda-builder-canvas-ux
plan: 05
subsystem: ui
tags: [react-flow, svg, canvas, task-editor, typescript]

# Dependency graph
requires:
  - phase: 29-fda-builder-canvas-ux
    provides: "edgeGeometry.mts (assignEdgeGeometry, quadraticPath, selfLoopPath, backEdgePath) from plan 29-02; columnRanks BFS from fdaLayout.mts (plan 29-03)"
provides:
  - "TransitionEdge.tsx — custom react-flow edge component rendering pair/self/back geometry"
  - "fdaToEdges joining columnRanks + assignEdgeGeometry, the single place the two Wave-1 modules meet"
  - "edgeTypes={transition: TransitionEdge} registered on <ReactFlow>, markerEnd via MarkerType.ArrowClosed"
affects: ["29-06", "29-07", "29-08"]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Custom react-flow edge reads geometry from data.geometry (computed once in fdaToEdges), never recomputes bow/loop/back-edge maths inline"
    - "Edge component guards NaN sourceX/Y/targetX/Y (handle-less initial state) by returning null rather than emitting a NaN SVG path"

key-files:
  created:
    - web_ui/react-src/src/pages/task-editor/TransitionEdge.tsx
  modified:
    - web_ui/react-src/src/pages/task-editor/TaskEditor.tsx

key-decisions:
  - "TransitionEdge falls back to a DEFAULT_GEOMETRY (kind:'pair', offset:0, labelT:0.5, backSpan:0) when data.geometry is absent, so a stale edge degrades to a straight line instead of crashing"
  - "Edge identity e-${index} and all four parseInt(...replace('e-','')) parse sites left untouched — confirmed 4 matches after the edit"

patterns-established:
  - "TaskEditor.tsx is the single join point between edgeGeometry.mts and fdaLayout.mts (assignEdgeGeometry(transitions, ranks)); neither .mts module imports the other"

requirements-completed: [CANVAS-01, CANVAS-02, CANVAS-03, CANVAS-04, CANVAS-13]

duration: 12min
completed: 2026-08-05
---

# Phase 29 Plan 05: Custom TransitionEdge Rendering Summary

**Replaced react-flow's default straight-line edges with a custom `TransitionEdge` component that bows bidirectional pairs apart, loops self-transitions, routes back-edges as return paths, and orients every arrowhead along its own curve's tangent — all geometry imported from plan 29-02's `edgeGeometry.mts`, none reimplemented.**

## Performance

- **Duration:** 12 min
- **Started:** 2026-08-05T15:03:00Z (approx, first commit 15:04:20Z)
- **Completed:** 2026-08-05T15:05:32Z
- **Tasks:** 2
- **Files modified:** 2 (1 created, 1 modified)

## Accomplishments
- New `TransitionEdge.tsx` (78 lines) renders exactly one `<BaseEdge>` per edge, branching on `geometry.kind` (`pair` / `self` / `back`) using only the four imported path helpers (`quadraticControlPoint`/`quadraticPath`/`pointOnQuadratic`, `selfLoopPath`, `backEdgePath`) — `grep -n "Math\."` returns nothing, confirming no curve maths landed in the component
- `fdaToEdges` in `TaskEditor.tsx` now computes `columnRanks(...)` (plan 29-03's BFS) and feeds it into `assignEdgeGeometry(...)` (plan 29-02), storing the per-index result on each edge's `data.geometry`
- Every edge gets `type: 'transition'` and `markerEnd: EDGE_MARKER` (`MarkerType.ArrowClosed`); `edgeTypes={transition: TransitionEdge}` registered on `<ReactFlow>`
- `onConnect`'s temporary edge also gets `type`/`markerEnd` so it renders correctly for the one render before the transitions effect replaces it with the real geometry-bearing edge

## Task Commits

Each task was committed atomically:

1. **Task 1: TransitionEdge component** - `54d4c41` (feat)
2. **Task 2: Wire fdaToEdges to the geometry module and register the edge type** - `8b44fa5` (feat)

**Plan metadata:** (this commit)

## Files Created/Modified
- `web_ui/react-src/src/pages/task-editor/TransitionEdge.tsx` - new default-exported react-flow edge component (78 lines); guards NaN coordinates, branches pair/self/back, forwards `markerEnd`/`label`/`labelStyle` unchanged to `BaseEdge`
- `web_ui/react-src/src/pages/task-editor/TaskEditor.tsx` - `fdaToEdges` now joins `columnRanks` + `assignEdgeGeometry`; `edgeTypes`/`EDGE_MARKER`/`EDGE_STROKE` constants added at module scope; `edgeTypes` prop added to `<ReactFlow>`; `onConnect`'s temp edge gets `type`/`markerEnd`. **745 → 763 lines** (+18, under the plan's ≤808 gate)

## Decisions Made
- Kept `TransitionEdge`'s fallback geometry (`DEFAULT_GEOMETRY`) as a plain module-level constant rather than constructing it inline per-render, matching the plan's "fall back to a straight-line default" instruction literally
- `assignEdgeGeometry`'s returned entries are indexed identically to the input transitions array (`geometry[i]` for transition `i`), used directly without an extra lookup map — this is the plan's own stated guarantee, verified by the existing `edgeGeometry.test.mts` suite (all 182 tests, including this module's, pass)

## Deviations from Plan

None - plan executed exactly as written. Both `<verify>` blocks (typecheck + build + line-count for Task 1; tests + typecheck + build + line-count for Task 2) passed on the first attempt with no fixes required.

## Issues Encountered

None.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness

- `TaskEditor.tsx` is at 763 lines, 45 lines of headroom remaining under the phase gate of 873 (plans 29-06/07 each budgeted ~20 lines)
- Visual confirmation of the bowed arcs, arrowhead tangents, and self-loops is deliberately deferred to plan 29-08's consolidated checkpoint — `docker compose up --build web_ui` was NOT run here, per this plan's own `<verification>` instruction
- Edge identity contract (`e-${index}`, 4 `parseInt` parse sites) confirmed intact — no downstream plan needs to re-verify this before touching edge-related code again

---
*Phase: 29-fda-builder-canvas-ux*
*Completed: 2026-08-05*

## Self-Check: PASSED

- FOUND: web_ui/react-src/src/pages/task-editor/TransitionEdge.tsx
- FOUND: .planning/phases/29-fda-builder-canvas-ux/29-05-SUMMARY.md
- FOUND commit: 54d4c41 (Task 1)
- FOUND commit: 8b44fa5 (Task 2)
