---
phase: 16-recursive-condition-tree
plan: "02"
subsystem: ui
tags: [react, typescript, fda, condition-tree, migration]

requires:
  - phase: 16-recursive-condition-tree
    plan: "01"
    provides: ConditionNode type, isConditionBranch guard, ConditionGroupsEditor tree props

provides:
  - TaskEditor.tsx fully migrated to condition_tree storage
  - normaliseTransition handles all 3 legacy formats and migrates to condition_tree on load
  - condLabel renders parenthesized tree labels (A ∨ B) ∧ C
  - updateTransitionTree writes condition_tree, clears condition_groups
  - Re-save always writes condition_tree (never condition_groups back to server)

affects:
  - 16-03-PLAN (Pi evaluation will read condition_tree)

tech-stack:
  added: []
  patterns:
    - "3-way migration chain in normaliseTransition: condition_tree (as-is) → condition_groups→OR-of-AND → conditions[]→AND-leaf"
    - "Recursive renderTreeLabel with parenthesization based on operator precedence"
    - "updateTransitionTree writes condition_tree and clears condition_groups in one atomic update"

key-files:
  created: []
  modified:
    - web_ui/react-src/src/pages/task-editor/TaskEditor.tsx

key-decisions:
  - "normaliseTransition accepts Record<string,unknown> at the function level; callsite casts FdaTransition via 'as unknown as' to handle legacy stored data"
  - "FdaOperand import added to handle type-safe right-operand construction in legacy conditions[] migration path"
  - "groupsToTree/treeToGroups adapter functions removed entirely — no longer needed after full migration"

requirements-completed: [COND-07, COND-10]

duration: 2min
completed: 2026-05-27
---

# Phase 16 Plan 02: TaskEditor Migration to condition_tree Summary

**TaskEditor fully migrated to condition_tree: 3-way legacy migration in normaliseTransition, parenthesized condLabel via renderTreeLabel, and updateTransitionTree replacing updateTransitionGroups**

## Performance

- **Duration:** 2 min
- **Started:** 2026-05-27T11:33:07Z
- **Completed:** 2026-05-27T11:35:29Z
- **Tasks:** 1
- **Files modified:** 1

## Accomplishments
- `normaliseTransition` rewritten with 3-way migration chain: `condition_tree` present → use as-is; `condition_groups` → convert to OR-of-AND tree; `conditions[]` → single AND-leaf or undefined
- `condLabel` replaced: now calls recursive `renderTreeLabel` which adds parentheses when OR is nested inside AND (or AND inside OR)
- `updateTransitionGroups` removed; `updateTransitionTree` added — writes `condition_tree` and sets `condition_groups: undefined` in one step
- `ConditionGroupsEditor` call site updated: `tree={selectedTransition.condition_tree ?? null}` and `onChange={tree => updateTransitionTree(...)}`
- New transitions created without `condition_groups` field (`{ from, to }` only = unconditional)
- `groupsToTree`/`treeToGroups` adapter functions from Plan 01 bridge removed entirely
- TypeScript compiles clean; React build succeeds

## Task Commits

1. **Task 1: Update imports, normaliseTransition, condLabel, and updateTransitionTree** - `ca5d76d` (feat)

## Files Created/Modified
- `web_ui/react-src/src/pages/task-editor/TaskEditor.tsx` - Full migration: normaliseTransition, condLabel, updateTransitionTree, ConditionGroupsEditor callsite

## Decisions Made
- `normaliseTransition` signature changed from `any` to `Record<string, unknown>` for stricter typing; callsite in `normaliseFda` casts `FdaTransition` via `as unknown as Record<string, unknown>` to satisfy the type checker while handling legacy stored data correctly
- `FdaOperand` added to imports to type-safely construct the `right` operand in the legacy `conditions[]` migration path

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Fixed 3 TypeScript errors introduced by new normaliseTransition signature**
- **Found during:** Task 1 (first tsc run after changes)
- **Issue 1:** `c as FdaCondition` — `Record<string, unknown>` cannot be directly cast to `FdaCondition`; required `c as unknown as FdaCondition`
- **Issue 2:** `c.rhs ?? 0` — `unknown` type not assignable to `FdaOperand`; required explicit `as FdaOperand` cast
- **Issue 3:** `normaliseFda` callsite — `FdaTransition` not assignable to `Record<string, unknown>` (index signature missing); required `t as unknown as Record<string, unknown>` cast
- **Fix:** Applied three targeted casts; added `FdaOperand` to type imports
- **Files modified:** `web_ui/react-src/src/pages/task-editor/TaskEditor.tsx`
- **Verification:** `tsc --noEmit` passes with 0 errors after fix

---

**Total deviations:** 1 auto-fixed (Rule 1 - TypeScript errors)
**Impact on plan:** No behavioral change; casts are correct given the legacy data being processed.

## Issues Encountered
None beyond the TypeScript type errors handled by deviation.

## Next Phase Readiness
- TaskEditor fully stores `condition_tree` on every save/re-save
- Legacy `condition_groups` and `conditions[]` data migrates to `condition_tree` on first load
- Pi evaluation (Plan 16-03) can now read `condition_tree` from stored FDA JSON

---
*Phase: 16-recursive-condition-tree*
*Completed: 2026-05-27*
