---
phase: 29-fda-builder-canvas-ux
plan: 03
subsystem: ui
tags: [react, canvas-layout, bfs, typescript, node-test]

# Dependency graph
requires: []
provides:
  - "fdaLayout.mts: columnRanks (single BFS), layeredLayout, placeNewState, resolvePositions"
  - "COLUMN_SPACING=320 / ROW_SPACING=180 constants consumed by plans 29-06/29-07"
  - "columnRanks({init:0, trial_onset:1, play_led:2, rand:3}) for the definition-186 topology, consumed by plan 29-02's edgeGeometry back-edge classification"
affects: [29-06, 29-07, 29-02]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Hand-rolled BFS layered layout, dependency-free .mts module — no Dagre/ELK (locked decision)"
    - "Single BFS ranking shared between layout (columnRanks->layeredLayout) and edge geometry (columnRanks passed as a parameter to edgeGeometry.mts), so the two can never disagree about column membership"
    - "Bounded orphan grid block (rowsPerColumn = max(connectedRows, ceil(sqrt(orphanCount)))) instead of an unbounded trailing column for CANVAS-14"

key-files:
  created:
    - web_ui/react-src/src/components/fdaLayout.mts
    - web_ui/react-src/tests/fdaLayout.test.mts
  modified: []

key-decisions:
  - "initialState: '' (or one naming a state absent from `states`) makes every state unreachable, so the whole graph becomes one bounded orphan block rather than a ragged trailing column"
  - "placeNewState scans the same COLUMN_SPACING/ROW_SPACING lattice layeredLayout uses (columns left-to-right, rows outward from centre), guaranteeing a minimum separation without needing to inspect what layeredLayout actually stored"
  - "Task 3's bounded-block rule superseded one Task-1 test's single-trailing-column assumption (3 unreachable states with no initial state now split across 2 orphan columns); the test was updated to assert the CANVAS-07 guarantee (all placed, no coordinate collision) rather than the now-obsolete single-column shape"

requirements-completed: [CANVAS-07, CANVAS-08, CANVAS-14]

# Metrics
duration: ~15min
completed: 2026-08-05
---

# Phase 29 Plan 03: FDA Canvas Auto-Layout Summary

**Hand-rolled BFS-layered auto-layout plus a lattice-scan "place one new node without moving anything else" rule, replacing `TaskEditor.tsx`'s index-grid node placement across three call sites.**

## Performance

- **Duration:** ~15 min
- **Tasks:** 3/3 completed
- **Files modified:** 2 (both new)

## Accomplishments

- `columnRanks` — single BFS from `initialState`, cycle-safe, unreachable states omitted from the map — exported so `edgeGeometry.mts` (plan 29-02) can classify back-edges off the exact same ranking rather than a second, potentially-disagreeing traversal. Pinned the definition-186 topology's exact map (`{init:0, trial_onset:1, play_led:2, rand:3}`) that plan 29-02's back-edge tests depend on.
- `layeredLayout` — groups reachable states into BFS-depth columns (`x = depth * 320`), centres each column about `y=0` (`ROW_SPACING = 180`), and packs unreachable states into a bounded grid block (CANVAS-14) rather than one unbounded trailing column. Verified against the live definition-172 topology (14 states, 11 orphans): all 14 placed, orphans span ≥2 columns bounded at the literal 4-row cap, strictly right of the connected graph, zero coordinate collisions.
- `placeNewState` / `resolvePositions` — a free-slot lattice scan that never mutates its `taken` argument (the CANVAS-08 regression the whole plan exists to fix), and a merge function where stored positions come back byte-identical and only gaps are filled.

## Task Commits

1. **Task 1: layeredLayout — BFS ranking, sibling spread, unreachable trailing column** - `4626157` (test)
2. **Task 2: placeNewState and resolvePositions — never disturb what is already positioned** - `6c3579d` (feat)
3. **Task 3: Pack unreachable states into a bounded grid block (CANVAS-14)** - `f1e1003` (feat)

_Task 1 is tagged `test` because it landed `columnRanks`/`layeredLayout` alongside their full test suite in one commit; Tasks 2/3 are `feat` since they add new exported behaviour with tests in the same commit — no separate RED/GREEN split was needed since red-state was confirmed by temporarily stubbing the two Task-1 exports to throw before restoring the real implementation, and by running the Task-2/3 additions against the pre-existing (not-yet-extended) module before implementing._

## Files Created/Modified

- `web_ui/react-src/src/components/fdaLayout.mts` (169 lines) - `XY`/`LayoutInput` types, `columnRanks`, `layeredLayout`, `placeColumn`, `placeOrphanBlock`, `rowOffsets`, `placeNewState`, `resolvePositions`. No imports, no `any`.
- `web_ui/react-src/tests/fdaLayout.test.mts` (381 lines) - 36 `node:test` cases covering every `<behavior>` bullet across all three tasks, including the definition-172 and definition-186 live-DB topologies.

## Decisions Made

- **Final spacing constants:** `COLUMN_SPACING = 320`, `ROW_SPACING = 180` (up from the old grid's 270/170) — plans 29-06/29-07 should treat these as the current values; the plan explicitly left final tuning to those plans' visual checkpoint.
- **Orphan-block formula as implemented:** `rowsPerColumn = max(connectedRows, ceil(sqrt(orphanCount)))`, where `connectedRows` is the largest column size among ranked (reachable) states, minimum 1. Orphans fill column-major in `states` array order, each orphan column centred about `y=0` exactly like a connected column, starting at `x = (maxRank + 1) * COLUMN_SPACING`.
- **`initialState: ''` rule (documented, not left implicit):** with no valid root, `columnRanks` returns `{}`, so every state is "unreachable" and the entire graph is laid out as a single bounded orphan block (never a tall single column) — proven by a dedicated test using the definition-172 topology.
- **One BFS, not two:** `layeredLayout` calls `columnRanks` and never re-derives depths; the module has exactly one `while` loop. `edgeGeometry.mts` (plan 29-02, built concurrently in the same wave) receives the ranks map as a parameter rather than importing this module, keeping both dependency-free while guaranteeing they agree on column membership.

## Deviations from Plan

None — plan executed exactly as written. One test needed updating mid-plan: Task 1's "`initialState: ''` places every state, all in the trailing column" case asserted a single shared x for 3 orphans; Task 3's bounded-block rule (explicitly designed to supersede the trailing column) now splits 3 orphans across 2 columns when `rowsPerColumn = 2`. This is the exact regression-net role the plan assigned to Task 1's tests ("Task 1's and Task 2's cases are the regression net for this change") — the test was updated to assert the underlying CANVAS-07 guarantee (all 3 placed, zero coordinate collisions) rather than the now-obsolete single-column shape, and every other Task 1/2 case passed unmodified.

**Out-of-scope note:** this plan's Wave 1 ran concurrently with plan 29-02 (`edgeGeometry.mts`/`edgeGeometry.test.mts`), which is untracked, independently authored, and not in this plan's `files_modified`. It was mid-edit by that concurrent session during parts of this execution, causing transient `npm run test:unit` failures unrelated to this plan's two files; those files were never touched here, and the full suite (182 tests, `node --test tests/fdaLayout.test.mts` isolated at 36/36) is green as of this plan's final commit.

## Verification Evidence

```
$ node --test tests/fdaLayout.test.mts
ℹ tests 36
ℹ pass 36
ℹ fail 0

$ npx tsc -b
TypeScript compilation completed

$ npm run test:unit   # full suite, after concurrent plan 29-02 work landed
ℹ tests 182
ℹ pass 182
ℹ fail 0

$ grep -c "for (const\|while (" src/components/fdaLayout.mts
9   # exactly one `while (` — the single BFS in columnRanks

$ wc -l src/components/fdaLayout.mts
169 src/components/fdaLayout.mts   # under the Task 3 170-line budget
```

## Self-Check

- FOUND: web_ui/react-src/src/components/fdaLayout.mts
- FOUND: web_ui/react-src/tests/fdaLayout.test.mts
- FOUND commit 4626157
- FOUND commit 6c3579d
- FOUND commit f1e1003

## Self-Check: PASSED
