---
phase: 15-compound-transition-conditions
plan: "01"
subsystem: ui
tags: [react, typescript, fda, conditions, pi, python]

# Dependency graph
requires: []
provides:
  - ConditionGroup type in TypeScript (AND-within-group)
  - FdaTransition extended with condition_groups? DNF field
  - normaliseTransition() migrates legacy conditions[] → condition_groups at load time
  - condLabel() renders compound a ∧ b ∨ c expressions
  - updateTransitionGroups() replaces single-condition handler
  - Pi load_fda_from_json() evaluates condition_groups as OR-of-ANDs
  - Legacy conditions[] transitions still work on Pi (backward compat)
affects: [15-02, task-editor, pi-evaluation]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "DNF (Disjunctive Normal Form): condition_groups is OR of AND-groups; single _dnf callable wraps all groups"
    - "Auto-migration: normaliseTransition always produces condition_groups, legacy conditions[] dropped from in-memory state"
    - "Stopgap UI wiring: ConditionBuilder reads condition_groups[0].conditions[0] until Plan 2 builds ConditionGroupsEditor"

key-files:
  created: []
  modified:
    - web_ui/react-src/src/types/index.ts
    - web_ui/react-src/src/pages/task-editor/TaskEditor.tsx
    - ~/pi-mirror/autopilot/autopilot/tasks/mics_task.py

key-decisions:
  - "Pi DNF uses single _dnf callable with default arg capture to avoid late-binding closures in loop"
  - "normaliseTransition drops legacy conditions field from in-memory state; Pi still reads it from stored JSON via legacy fallback"
  - "Empty condition_groups [] = unconditional (not [{conditions:[]}]) so ConditionGroupsEditor shows hint instead of empty group card"

patterns-established:
  - "condition_groups DNF pattern: any(all(c() for c in g) for g in gfns)"

requirements-completed: [COND-01, COND-03, COND-04, COND-05]

# Metrics
duration: 2min
completed: 2026-05-27
---

# Phase 15, Plan 1: Compound Conditions — Schema, Migration, Pi Evaluation Summary

**ConditionGroup DNF type wired end-to-end: TypeScript schema extended, legacy FDA auto-migrated, Pi evaluates OR-of-ANDs with backward compat for flat conditions[]**

## Performance

- **Duration:** ~2 min
- **Started:** 2026-05-27T10:32:42Z
- **Completed:** 2026-05-27T10:34:32Z
- **Tasks:** 5 (Steps 1-5; Step 6 removed from plan)
- **Files modified:** 3 (types/index.ts, TaskEditor.tsx, mics_task.py)

## Accomplishments

- `ConditionGroup` interface added; `FdaTransition` now has `condition_groups?` (canonical) and `conditions?` (legacy)
- `normaliseTransition()` always produces `condition_groups` from any legacy shape, dropping `conditions` from in-memory state
- `condLabel()` renders full DNF notation (`a ∧ b ∨ c`) and `(unconditional)` for empty groups
- `updateTransitionGroups()` replaces `updateTransitionCondition()` — operates on full group array
- Pi `load_fda_from_json()` handles both new `condition_groups` (DNF) and legacy `conditions[]` (backward compat)

## Task Commits

1. **Step 1: Add ConditionGroup type + extend FdaTransition** - `3e6586f` (feat)
2. **Steps 2-4: normaliseTransition, condLabel, updateTransitionGroups, stopgap wiring** - `38a7b16` (feat)
3. **Step 5: Pi load_fda_from_json DNF evaluation** - `01b52e8` in pi-mirror repo (feat)

## Files Created/Modified

- `web_ui/react-src/src/types/index.ts` - Added `ConditionGroup` interface; `FdaTransition.condition_groups?` + `conditions?` (legacy)
- `web_ui/react-src/src/pages/task-editor/TaskEditor.tsx` - `normaliseTransition`, `condLabel`, `updateTransitionGroups`, stopgap ConditionBuilder wiring, `ConditionGroup` import
- `~/pi-mirror/autopilot/autopilot/tasks/mics_task.py` - Transition loop handles `condition_groups` DNF; legacy `conditions[]` fallback intact

## Decisions Made

- Pi DNF wraps all groups in a single `_dnf` callable using a default-arg capture (`gfns=group_fns`) to avoid Python late-binding closure bug in loops
- `normaliseTransition` drops `conditions` from in-memory state; the Pi still reads it from stored JSON (old task defs not yet re-saved) via the legacy branch
- Empty `condition_groups: []` means unconditional — consistent with the "no conditions" interpretation needed by the upcoming `ConditionGroupsEditor`
- Step 6 (API validation) was correctly identified as not needed — `_validate_fda_against_toolkit` explicitly skips condition refs

## Deviations from Plan

None - plan executed exactly as written. Step 6 was already marked REMOVED in the plan.

## Issues Encountered

- pi-mirror is a separate git repository (`/home/ido/pi-mirror`), not a subdirectory of mics-backend. Committed Task 5 to pi-mirror repo directly rather than mics-backend.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness

- Plan 2 can now build `ConditionGroupsEditor` React component against the established `ConditionGroup[]` type
- Stopgap wiring in TaskEditor ensures the editor remains functional with single conditions until Plan 2 lands
- Pi is ready to evaluate new-format `condition_groups` from re-saved task definitions immediately

---
*Phase: 15-compound-transition-conditions*
*Completed: 2026-05-27*
