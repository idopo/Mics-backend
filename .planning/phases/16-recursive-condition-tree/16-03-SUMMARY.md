---
phase: 16-recursive-condition-tree
plan: "03"
subsystem: pi
tags: [python, fda, condition-tree, mics_task, pi]

# Dependency graph
requires:
  - phase: 15-compound-transition-conditions
    provides: condition_groups DNF evaluation path in mics_task.py
provides:
  - _build_tree_lambda() recursive condition evaluator in mics_task.py
  - Three-way fallback chain: condition_tree → condition_groups → conditions[]
affects: [16-recursive-condition-tree]

# Tech tracking
tech-stack:
  added: []
  patterns: [recursive lambda builder with default-arg closure capture, three-way backward-compat fallback chain]

key-files:
  created: []
  modified:
    - ~/pi-mirror/autopilot/autopilot/tasks/mics_task.py

key-decisions:
  - "Leaf node detection uses 'op' not in ('AND','OR') — handles both unified {left/op/right} and legacy {view/op/rhs} formats without extra keys"
  - "Default-arg capture (fns=child_fns) used in _and_check and _or_check to avoid late-binding closure bugs"
  - "condition_tree = None fallback to condition_groups = None fallback to conditions[] preserves all prior behavior exactly"

patterns-established:
  - "Recursive _build_tree_lambda(): leaf delegates to _build_transition_lambda(); AND/OR branches recurse with all()/any()"
  - "Three-way fallback chain in transition registration loop: primary (condition_tree) → Phase 15 (condition_groups) → legacy (conditions[])"

requirements-completed: [COND-09]

# Metrics
duration: 10min
completed: 2026-05-27
---

# Phase 16 Plan 03: Pi Recursive Condition Tree Evaluator Summary

**`_build_tree_lambda()` added to mics_task.py with recursive all()/any() evaluation and three-way fallback chain preserving Phase 15 DNF and legacy flat-conditions paths**

## Performance

- **Duration:** ~10 min
- **Started:** 2026-05-27
- **Completed:** 2026-05-27
- **Tasks:** 1
- **Files modified:** 1

## Accomplishments
- Added `_build_tree_lambda()` method before `_build_transition_lambda()` in mics_task.py — handles leaf nodes, AND-branches (all()), and OR-branches (any()) with default-arg capture
- Updated transition registration loop in `load_fda_from_json()` with three-way fallback: `condition_tree` (Phase 16+) → `condition_groups` (Phase 15 DNF) → `conditions[]` (legacy)
- Syntax check passes (`python3 -m py_compile`)

## Task Commits

Each task was committed atomically:

1. **Task 1: Add _build_tree_lambda and update transition registration** - `7d22408` (feat) — pi-mirror repo

**Plan metadata:** (docs: complete plan — mics-backend repo)

## Files Created/Modified
- `~/pi-mirror/autopilot/autopilot/tasks/mics_task.py` - Added `_build_tree_lambda()` method (32 lines) and updated transition registration loop with three-way fallback chain (+4 lines net)

## Decisions Made
- Leaf node detection uses `'op' not in node or node['op'] not in ('AND', 'OR')` — this naturally handles both the unified format (`left`/`op`/`right` where op is a comparison operator) and legacy format (`view`/`op`/`rhs`) without needing to check for `left` key explicitly
- Default-arg capture (`fns=child_fns`) in `_and_check` and `_or_check` avoids Python late-binding closure issues (same pattern already used for `_dnf` in Phase 15)
- `condition_tree = None` check uses `is not None` so an empty-but-present tree object is still handled (would build a lambda from an empty-children branch → returns `lambda: True`)

## Deviations from Plan

None - plan executed exactly as written.

## Issues Encountered
- `python` command not found on this system (Linux); used `python3 -m py_compile` instead — exits 0.

## User Setup Required
None - no external service configuration required. Pi deploy via `~/pi-mirror/tools/deploy_pi.sh` is a separate operational step.

## Next Phase Readiness
- Pi evaluator now supports `condition_tree` as primary path; ready for Phase 16 plan 04 (migration / normaliseTransition update)
- Backward compat fully preserved: existing Phase 15 `condition_groups` FDAs evaluate identically; legacy `conditions[]` FDAs evaluate identically

---
*Phase: 16-recursive-condition-tree*
*Completed: 2026-05-27*
