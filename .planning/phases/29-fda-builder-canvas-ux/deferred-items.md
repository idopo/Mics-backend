# Deferred Items — Phase 29

Out-of-scope discoveries logged during plan execution, per the executor's scope-boundary rule.
Not fixed here; recorded so they are not mistaken for regressions introduced by this plan's work.

## 29-01 — Pre-existing failing tests in `tests/edgeGeometry.test.mts` (untracked, unrelated files)

**Found during:** Task 3 verification (`npm run test:unit`).

**Observation:** The working tree already contains untracked files unrelated to 29-01's scope
(`src/components/edgeGeometry.mts`, `src/components/fdaLayout.mts`,
`tests/edgeGeometry.test.mts`, `api/tests/test_ui_layout.py`, plus a modified
`api/routers/toolkits.py`) — apparently in-progress work toward CANVAS-13/14 (back-edge routing /
orphan packing) from a different session, never committed.

`tests/edgeGeometry.test.mts` has 2 failing assertions:
- `a single-column back-span (adjacent columns) stays pair, not back — locked CANVAS-13 boundary`
- `definition 186: play_led/rand pair keeps identical offsets with and without ranks; rand->trial_onset is back`

Both fail on a `-0` vs `0` `assert.strictEqual` mismatch (`edgeGeometry.test.mts:337`).

**Verified pre-existing, not caused by 29-01:** confirmed via `git stash` (which removes every
29-01 diff) — the same 2 failures reproduce identically against the stashed (pre-29-01) tree.

**Action:** None taken — out of scope for 29-01 (`files_modified` for this plan is limited to
`transitionLabel.mts`, `fdaNormalise.mts`, `CanvasContextMenu.tsx`, `TaskEditor.tsx` and their
tests). Whichever plan owns `edgeGeometry.mts`/CANVAS-13 should fix the `-0`/`0` assertion before
that work is committed.

**Net test count:** 146 total (144 pass, 2 fail) after 29-01's 27 new tests (10 in
`transitionLabel.test.mts`, 17 in `fdaNormalise.test.mts`) are added. All 27 of 29-01's own tests
pass; the 2 failures are entirely within the pre-existing, unrelated `edgeGeometry.test.mts`.

## 29-04: pre-existing frontend test failure (out of scope)

Found during 29-04 Task 3 verification (`npm run test:unit`, 2026-08-05).

- `web_ui/react-src/tests/fdaLayout.test.mts` — 1 failing case, `-0 !== 0` in a back-edge offset
  calc — plus `tests/edgeGeometry.test.mts` — 1 failing case, a single-column back-span
  classification.
- Both files (and their `src/components/fdaLayout.mts` / `edgeGeometry.mts` counterparts, plus
  `TaskEditor.tsx` / `CanvasContextMenu.tsx`) were already present, uncommitted, and unrelated to
  this plan's `files_modified` before 29-04 execution started — CANVAS-13/14 back-edge-routing
  work from a separate, still-in-progress session.
- Not fixed here per the scope boundary rule (only auto-fix issues directly caused by the current
  task's changes). 84 pre-existing baseline tests (the ones this plan actually touches indirectly
  via `TaskDefinitionFull`) plus every other suite pass; 146/147 total pass.
