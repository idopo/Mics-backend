---
phase: 16-recursive-condition-tree
plan: "01"
subsystem: ui
tags: [react, typescript, fda, condition-tree, recursive]

requires:
  - phase: 15-compound-transition-conditions
    provides: ConditionGroup, FdaCondition, ConditionGroupsEditor flat DNF UI

provides:
  - ConditionNode recursive union type (leaf FdaCondition | AND/OR branch)
  - isConditionBranch type guard
  - FdaTransition.condition_tree optional field (Phase 16+ canonical)
  - ConditionGroupsEditor rewritten as recursive tree editor with +AND/+OR per leaf

affects:
  - 16-02-PLAN (TaskEditor full migration to condition_tree)
  - Pi evaluation (will read condition_tree in Phase 16-03)

tech-stack:
  added: []
  patterns:
    - "Pure tree mutation helpers (updateNode, deleteNode, addAndSibling, addOrSibling) as module-level functions above component"
    - "Depth-based background opacity for nested branch containers"
    - "groupsToTree/treeToGroups adapters at callsite for backward-compat legacy bridge"

key-files:
  created: []
  modified:
    - web_ui/react-src/src/types/index.ts
    - web_ui/react-src/src/components/ConditionGroupsEditor.tsx
    - web_ui/react-src/src/pages/task-editor/TaskEditor.tsx

key-decisions:
  - "TaskEditor callsite bridged with groupsToTree/treeToGroups adapters instead of doing full migration in Plan 01 — full migration is Plan 02's scope"
  - "ConditionNode discriminated by presence of 'children' key: leaf has no children, branch has op AND|OR plus children array"

requirements-completed: [COND-06, COND-08]

duration: 3min
completed: 2026-05-27
---

# Phase 16 Plan 01: Recursive ConditionNode Type + Tree Editor Summary

**ConditionNode recursive type added to types/index.ts and ConditionGroupsEditor rewritten as depth-shaded +AND/+OR tree editor with pure functional mutation helpers**

## Performance

- **Duration:** 3 min
- **Started:** 2026-05-27T11:28:03Z
- **Completed:** 2026-05-27T11:31:00Z
- **Tasks:** 2
- **Files modified:** 3

## Accomplishments
- Exported `ConditionNode` union type (FdaCondition leaf | `{op:'AND'|'OR', children:ConditionNode[]}` branch) and `isConditionBranch` type guard from `types/index.ts`
- Added `condition_tree?: ConditionNode` to `FdaTransition` as the Phase 16+ canonical field alongside legacy `condition_groups` and `conditions`
- Rewrote `ConditionGroupsEditor.tsx` (163 lines) with recursive `renderNode`, depth-based background opacity, and +AND/+OR buttons on each leaf row
- Single-child branch collapse and empty-branch pruning implemented in `deleteNode`
- TypeScript compiles clean with 0 errors

## Task Commits

1. **Task 1: Add ConditionNode type and condition_tree to FdaTransition** - `236512b` (feat)
2. **Task 2: Rewrite ConditionGroupsEditor.tsx as recursive ConditionTreeEditor** - `c8538b8` (feat)

## Files Created/Modified
- `web_ui/react-src/src/types/index.ts` - Added ConditionNode type, isConditionBranch guard, condition_tree field on FdaTransition
- `web_ui/react-src/src/components/ConditionGroupsEditor.tsx` - Full rewrite: recursive tree editor with pure mutation helpers
- `web_ui/react-src/src/pages/task-editor/TaskEditor.tsx` - Added groupsToTree/treeToGroups adapters, updated ConditionGroupsEditor callsite

## Decisions Made
- TaskEditor callsite uses `groupsToTree`/`treeToGroups` adapters to bridge legacy `condition_groups` storage while the full `condition_tree` migration happens in Plan 02
- `ConditionNode` leaf type is a raw `FdaCondition` (not wrapped) — discriminated by absence of `children` key, guarded by `isConditionBranch`

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Fixed TypeScript errors in TaskEditor.tsx callsite after ConditionGroupsEditor props change**
- **Found during:** Task 2 (rewrite ConditionGroupsEditor)
- **Issue:** Changing `groups: ConditionGroup[]` to `tree: ConditionNode | null` in Props left two TypeScript errors in TaskEditor.tsx callsite
- **Fix:** Added `groupsToTree`/`treeToGroups` adapter functions to TaskEditor.tsx and updated the callsite to use new `tree` prop with DNF conversion round-trip
- **Files modified:** `web_ui/react-src/src/pages/task-editor/TaskEditor.tsx`
- **Verification:** `tsc --noEmit` passes with 0 errors after fix
- **Committed in:** `c8538b8` (part of Task 2 commit)

---

**Total deviations:** 1 auto-fixed (Rule 1 - bug)
**Impact on plan:** Essential for TypeScript correctness. TaskEditor adapter is temporary — Plan 02 will do full migration to condition_tree storage.

## Issues Encountered
None beyond the callsite TypeScript errors handled by deviation.

## Next Phase Readiness
- `ConditionNode` type and `ConditionGroupsEditor` recursive editor ready for Plan 02 (TaskEditor full migration)
- `isConditionBranch` guard available for Pi evaluation code in Plan 16-03
- Legacy `condition_groups` path preserved for full backward compatibility

---
*Phase: 16-recursive-condition-tree*
*Completed: 2026-05-27*
