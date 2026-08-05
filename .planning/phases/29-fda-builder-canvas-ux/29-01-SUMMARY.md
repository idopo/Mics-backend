---
phase: 29-fda-builder-canvas-ux
plan: 01
subsystem: react-frontend / task-editor
tags: [refactor, tdd, fda-editor, condition-labels, legacy-migration]
requires: []
provides:
  - condLabel + renderTreeLabel as a pure, importable, tested module (transitionLabel.mts)
  - normaliseFda / normaliseTransition / normaliseTriggerAssignment / parseStateWarnings as a
    pure, importable, tested module (fdaNormalise.mts)
  - CanvasContextMenu.tsx, a reusable items-driven right-click menu component
affects:
  - web_ui/react-src/src/pages/task-editor/TaskEditor.tsx (shrunk 873 -> 745 lines)
tech-stack:
  added: []
  patterns:
    - ".mts pure-module extraction (7th+8th instance of the repo's existing pattern)"
key-files:
  created:
    - web_ui/react-src/src/components/transitionLabel.mts
    - web_ui/react-src/tests/transitionLabel.test.mts
    - web_ui/react-src/src/components/fdaNormalise.mts
    - web_ui/react-src/tests/fdaNormalise.test.mts
    - web_ui/react-src/src/pages/task-editor/CanvasContextMenu.tsx
  modified:
    - web_ui/react-src/src/pages/task-editor/TaskEditor.tsx
decisions:
  - "TaskEditor.tsx line count: 873 before this plan -> 745 after (128-line reduction), leaving
    plenty of headroom under the 790-line ceiling this plan's must_haves required for the
    29-05/06/07 wiring plans that follow."
metrics:
  duration: "~15 minutes"
  completed: "2026-08-05"
---

# Phase 29 Plan 01: Freeze condition-label text and legacy FDA normalisation, shrink TaskEditor.tsx Summary

Extracted two zero-test pure functions out of `TaskEditor.tsx` into tested `.mts` modules
(`transitionLabel.mts`, `fdaNormalise.mts`) and lifted the inline node context menu into a reusable
`CanvasContextMenu.tsx` component — a pure, behaviour-preserving refactor with no user-visible
change, done ahead of the CANVAS feature plans so they have line-count headroom and cannot silently
drift the frozen condition-label text or the legacy FDA migration paths.

## What Was Built

**Task 1 — `transitionLabel.mts`.** `condLabel`/`renderTreeLabel` moved character-for-character out
of `TaskEditor.tsx`. 10 new `node:test` cases pin the exact rendered strings: leaf conditions,
`(unconditional)`, AND/OR joins with the correct Unicode separators (` ∧ `/` ∨ `), same-op nesting
staying flat, opposite-op nesting gaining parens, a three-level (AND > OR > AND) nest parenthesising
at both switch points, and the `?`/`?` fallback for null/undefined operands via `operandLabel`.

**Task 2 — `fdaNormalise.mts`.** `normaliseTransition`, `normaliseTriggerAssignment`, `normaliseFda`,
and `parseStateWarnings` moved character-for-character. 17 new `node:test` cases cover every legacy
migration branch for the first time: `condition_tree` passthrough, `from_state`/`next_state` key
migration, all three `condition_groups` DNF shapes (single leaf, single AND, multi-group OR-of-AND,
empty-group filtering, and the `condition_groups: []` fallthrough), the legacy flat `conditions[]`
and singular `condition` shapes (both the bare-object and already-has-`left` forms), the
handler/config-stripping trigger-assignment healer (the task-definition-181/185 crash fix), and
`parseStateWarnings`'s null/single-line/joined-lines/non-matching-line cases. `fdaNormalise.mts` is
90 lines (well under the plan's 130-line ceiling).

**Task 3 — `CanvasContextMenu.tsx` + TaskEditor rewire.** New component takes `x`/`y`/`items`/
`onClose`; each item renders a button whose `onClick` runs the item's own handler then closes the
menu, matching the pairing the inline JSX used to do at each call site. Styling (position, panel/
border colors, border-radius, box-shadow, per-button padding/color) copied verbatim from the block
it replaces — `danger: true` selects the same `#f87171` red the "Delete State" button used inline.
`TaskEditor.tsx` now imports `condLabel` from `transitionLabel.mts` and `normaliseFda`/
`parseStateWarnings` from `fdaNormalise.mts`; the `ctxMenu &&` JSX block became a single
`<CanvasContextMenu ... items={[...]} />` call. `tsc -b`'s `noUnusedLocals` confirmed
`isConditionBranch` and `ConditionNode` are both still needed by `conditionSummary` and the
condition-tree state, so those imports were kept.

## Verification

- `npm run test:unit` — all 27 of this plan's own new tests pass (10 + 17); `tsc -b` clean;
  `npm run build` succeeds (bundle `TaskEditor-CdmH-PGv.js`).
- `wc -l src/pages/task-editor/TaskEditor.tsx` → 745 (≤ 790 required).
- `grep -nE "function (condLabel|normaliseFda|parseStateWarnings|normaliseTransition)" TaskEditor.tsx`
  → no matches (fully removed, only imported).
- `grep -c "position: 'fixed'" TaskEditor.tsx` → 0 (inline menu markup fully replaced).
- `docker compose up --build web_ui` deliberately NOT run — this plan ships no user-visible change
  and the rebuilt SPA belongs to the 29-08 checkpoint, per the plan's own verification note.

## Deviations from Plan

### Auto-fixed Issues

None — plan executed exactly as written; Blocks A/B/C were copied verbatim as instructed.

### Out-of-scope discoveries (not fixed, logged)

**1. Pre-existing failing tests in `tests/edgeGeometry.test.mts` (untracked, unrelated files).**
Found during Task 3's `npm run test:unit` run: 2 failing assertions (`-0` vs `0` mismatches) in a
file that is not part of this plan's scope. The working tree already contained untracked
CANVAS-13/14 back-edge-routing work (`edgeGeometry.mts`, `fdaLayout.mts`, their tests) from a
separate, still-in-progress session. Verified via `git stash` (removing every 29-01 diff) that the
same 2 failures reproduce identically against the pre-29-01 tree — not a regression this plan
introduced. Not fixed, per the scope-boundary rule; logged in
`.planning/phases/29-fda-builder-canvas-ux/deferred-items.md`. All 27 of this plan's own tests pass.

## TaskEditor.tsx line count (plan's requested record)

- **Before this plan:** 873 lines
- **After this plan:** 745 lines
- **Reduction:** 128 lines (plan required ≥ 83)

## Commits

- `04a97ff` — test(29-01): extract condLabel/renderTreeLabel into tested pure module
- `97cd6b7` — test(29-01): extract FDA legacy normalisation helpers into tested pure module
- `0221072` — refactor(29-01): extract canvas context menu, rewire TaskEditor to the new pure modules

## Self-Check: PASSED

- FOUND: web_ui/react-src/src/components/transitionLabel.mts
- FOUND: web_ui/react-src/tests/transitionLabel.test.mts
- FOUND: web_ui/react-src/src/components/fdaNormalise.mts
- FOUND: web_ui/react-src/tests/fdaNormalise.test.mts
- FOUND: web_ui/react-src/src/pages/task-editor/CanvasContextMenu.tsx
- FOUND: commit 04a97ff
- FOUND: commit 97cd6b7
- FOUND: commit 0221072
