---
phase: 14
plan: 2
subsystem: frontend
tags: [bug-fix, react, fda-editor, hw-lib, warning-badge, tooltip]
dependency_graph:
  requires: []
  provides: [hw-lib-warning-badge-stable]
  affects: [TaskEditor, StateNode, style.css]
tech_stack:
  added: []
  patterns: [CSS-hover-tooltip, react-query-invalidation]
key_files:
  modified:
    - web_ui/react-src/src/pages/task-editor/TaskEditor.tsx
    - web_ui/react-src/src/components/StateNode.tsx
    - web_ui/static/style.css
decisions:
  - CSS :hover tooltip chosen over React state tooltip to survive ReactFlow re-renders
  - style.css target is web_ui/static/style.css (not src/) - it is the global stylesheet served at /static/style.css
metrics:
  duration: ~5 minutes
  completed: "2026-05-24T08:56:26Z"
  tasks_completed: 2
  files_modified: 3
---

# Phase 14 Plan 2: Hw-lib Warning Badge Fixes Summary

**One-liner:** Fixed two bugs in the FDA editor's per-state "!" warning badge: stale validation state after pin save (BUG-03) and tooltip destroyed by ReactFlow re-renders (BUG-04).

## What Was Built

Two independent frontend bug fixes for the hw-lib deprecation warning system introduced in Phase 12-05:

**BUG-03 — Stale badges after pin change (`TaskEditor.tsx`)**

The `onSaved` callback in `HwLibVersionModal` only called `refetchPins()`, leaving the `['task-definition', numId]` query stale. After the backend ran `_revalidate_task_def` (triggered by the pin PUT/DELETE), the updated `validation_status` and `validation_message` sat in the DB unreachable. Added `qc.invalidateQueries({ queryKey: ['task-definition', numId] })` before `refetchPins()` so both queries refresh together.

**BUG-04 — Tooltip destroyed by ReactFlow re-renders (`StateNode.tsx` + `style.css`)**

The badge used `title={warning}` — a native browser tooltip. ReactFlow triggers node re-renders on hover (handle hit-testing), selection changes, and `setNodes` calls, each of which replaces the DOM node and kills the native tooltip. Replaced with a CSS `:hover` tooltip: inner `<span className="state-warning-tooltip">` revealed by `.state-warning-badge:hover .state-warning-tooltip { display: block }`. The `:hover` pseudo-class is browser-managed and survives React re-renders entirely.

## Tasks Completed

| # | Description | Commit |
|---|---|---|
| 1 | BUG-03: invalidate task-definition query on hw-lib pin save | 8c62f48 |
| 2 | BUG-04: CSS hover tooltip on state warning badge | 91cbb73 |

## Deviations from Plan

**1. [Rule 1 - Bug] CSS file location differs from plan spec**

- **Found during:** Task 2
- **Issue:** Plan referenced `web_ui/react-src/src/style.css` which does not exist. The React SPA has no CSS file in `src/` — styles are in `web_ui/static/style.css`, which is served as `/static/style.css` and linked from the HTML template.
- **Fix:** Added CSS rules to `web_ui/static/style.css` (the correct global stylesheet).
- **Files modified:** `web_ui/static/style.css`
- **Impact:** Functionally identical — the CSS is loaded in the same browser context.

## Self-Check: PASSED

All key files confirmed present. Both commits (8c62f48, 91cbb73) confirmed in git log. React build succeeded with 0 errors.
