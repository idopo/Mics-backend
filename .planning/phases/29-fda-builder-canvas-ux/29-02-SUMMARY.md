---
phase: 29-fda-builder-canvas-ux
plan: 02
subsystem: ui
tags: [react-flow, svg-paths, bezier, edge-routing, node-test]

# Dependency graph
requires: []
provides:
  - "edgeGeometry.mts: assignEdgeGeometry(transitions, ranks?) — parallel-group offsets, sign-flip-safe bidirectional bow, self-loop classification, back-edge classification (CANVAS-13)"
  - "quadraticControlPoint/quadraticPath/pointOnQuadratic/pointOnCubic/selfLoopPath/backEdgePath — pure curve maths consumed by plan 29-05's TransitionEdge.tsx"
affects: [29-05]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Pure geometry module with zero imports, taking BFS ranks as a parameter rather than importing the layout module — keeps Wave-1 plans (29-02/29-03) file-independent"
    - "Canonical-pair sign-flip: bucket by unordered [min,max] key, compute one canonical offset ordered by index, negate only for the from>to member — prevents the hourglass bug rather than reproducing it"

key-files:
  created:
    - web_ui/react-src/src/components/edgeGeometry.mts
    - web_ui/react-src/tests/edgeGeometry.test.mts
  modified: []

key-decisions:
  - "backSpan is 0 on every non-back EdgeGeometry entry (per the pinned interface docstring), even for the classification-boundary case (span=1, single column) — the plan's own closing rule overrides an earlier, more literal bullet describing the intermediate computed span"
  - "Normalised -0 to +0 in the sign-flip (`(reversed ? -canonical : canonical) || 0`) so a reversed singleton member's emitted offset compares strictly equal to 0 under assert.strictEqual/Object.is"

patterns-established:
  - "Curve maths (quadratic + cubic Bezier point/path helpers) centralised in one dependency-free .mts module so TaskEditor.tsx never carries edge-offset arithmetic (CANVAS-11)"

requirements-completed: [CANVAS-01, CANVAS-02, CANVAS-04, CANVAS-13]

# Metrics
duration: 45min
completed: 2026-08-05
---

# Phase 29 Plan 02: Edge Geometry Summary

**Pure, dependency-free `edgeGeometry.mts` proving the CANVAS-01 bidirectional sign-flip trap and CANVAS-13 back-edge routing by assertion, ready for plan 29-05's `TransitionEdge.tsx` to consume.**

## Performance

- **Duration:** 45 min
- **Started:** 2026-08-05T14:13:00Z
- **Completed:** 2026-08-05T14:58:50Z
- **Tasks:** 3
- **Files modified:** 2 (both new)

## Accomplishments
- `assignEdgeGeometry` groups transitions by unordered pair (or by node for self-loops), assigning each member a canonical offset that is sign-flipped only for the `from > to` member — proven by assertion that a bidirectional pair bows to opposite physical sides while sharing an equal own-frame offset (the trap the plan named)
- Self-transitions classified separately with distinct non-negative offsets; N self-loops on one node stack without collision
- Curve maths (`quadraticControlPoint`, `quadraticPath`, `pointOnQuadratic`, `pointOnCubic`) and `selfLoopPath` implemented against a pinned normal convention, with a degenerate-chord guard against NaN/divide-by-zero
- CANVAS-13 back-edge classification: a transition spanning >= 2 BFS columns (both endpoints ranked) is `back`, partitioned into its own group before bucketing so it never perturbs a `pair` group between the same nodes; a 1-column span stays `pair` (locked boundary)
- `backEdgePath` routes a back-edge below the chord with an apex at exactly `0.75 * controlOffset`, re-entering the target's left handle heading rightward; definition 186's literal transition list is asserted to keep the `play_led ⇄ rand` pair's offsets byte-identical with and without back-edge support, while `rand→trial_onset` is classified `back` and clears the node band

## Task Commits

Each task was committed atomically (TDD: RED confirmed via a fresh failing run before each GREEN commit):

1. **Task 1: assignEdgeGeometry — grouping, offsets, label stagger, self-loop classification** - `7f380ae` (feat)
2. **Task 2: Curve maths and self-loop path** - `f57fd9e` (feat)
3. **Task 3: Back-edge classification and return-path routing (CANVAS-13)** - `225cc95` (feat)

_Test-then-implement order followed per task; no separate REFACTOR commit was needed (module stayed under budget without a cleanup pass)._

## Files Created/Modified
- `web_ui/react-src/src/components/edgeGeometry.mts` (202 lines) - `assignEdgeGeometry`, `quadraticControlPoint`, `quadraticPath`, `pointOnQuadratic`, `pointOnCubic`, `selfLoopPath`, `backEdgePath`, `XY`/`EdgeKind`/`EdgeGeometry` types. Zero imports.
- `web_ui/react-src/tests/edgeGeometry.test.mts` (35 `node:test` cases) - full coverage of the grouping/sign-flip/self-loop/back-edge/curve-maths behavior list.

## Decisions Made
- **`backSpan` field is 0 for every non-`back` kind, always.** The plan's Task 3 behavior list contained one bullet describing the classification-deciding computed span as "backSpan 1" for a 1-column reversed pair, directly contradicted by its own closing bullet ("backSpan is 0 on every non-back entry, for every case above") and by the pinned `<interfaces>` docstring. Implemented per the interface + closing rule; documented inline in the test to prevent a future "fix" reintroducing the earlier wording.
- **Normalised `-0` to `+0`** in the sign-flip output (`(reversed ? -canonical : canonical) || 0`), since `node:assert/strict`'s `Object.is`-based equality distinguishes `-0` from `0` and a reversed singleton member's canonical offset is exactly `0`.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] `-0` vs `0` in the pair sign-flip**
- **Found during:** Task 1 GREEN verification (definition-186-style test case, `trial_onset→play_led` singleton reversed pair)
- **Issue:** `-canonical` on a zero canonical produced `-0`; `assert.strictEqual(offset, 0)` failed because `Object.is(-0, 0)` is `false`
- **Fix:** `offset = (m.reversed ? -canonical : canonical) || 0`
- **Files modified:** `web_ui/react-src/src/components/edgeGeometry.mts`
- **Verification:** `npm run test:unit` — all cases pass
- **Committed in:** `7f380ae` (Task 1 commit)

**2. [Rule 1 - Bug] Ambiguous plan wording for `backSpan` on the CANVAS-13 boundary case**
- **Found during:** Task 3 RED/GREEN cycle
- **Issue:** Plan's own behavior list gave two contradictory expectations for `backSpan` on a 1-column reversed pair (`1` vs the closing rule's `0`)
- **Fix:** Implemented and tested against the pinned interface docstring + the more specific closing rule; test comment records the resolution
- **Files modified:** `web_ui/react-src/tests/edgeGeometry.test.mts`
- **Verification:** `npm run test:unit` — 35/35 new cases pass
- **Committed in:** `225cc95` (Task 3 commit)

---

**Total deviations:** 2 auto-fixed (2 bugs, both Rule 1)
**Impact on plan:** Both fixes necessary for correctness of the pinned contract; no scope creep, no architectural change.

## Issues Encountered
- The repo had concurrent, uncommitted work from parallel Wave-1 plans (29-03's `fdaLayout.mts`, 29-04's `TaskDefinitionFull`/`ui_layout` changes) actively landing in the same working tree during this plan's execution, causing transient full-suite test-count/pass fluctuations unrelated to this plan's files. Verified via isolated `node --test tests/edgeGeometry.test.mts` runs (35/35 passing throughout) and confirmed `git diff --stat` for this plan's commits touches only the two `files_modified` paths. Logged in `deferred-items.md`, not fixed (out of scope).

## User Setup Required
None - no external service configuration required. This plan renders nothing; `TaskEditor.tsx` is untouched.

## Next Phase Readiness
- Plan 29-05's `TransitionEdge.tsx` can consume `assignEdgeGeometry`/`quadraticPath`/`selfLoopPath`/`backEdgePath` directly against the pinned interface — no changes anticipated.
- Final tuned constants for 29-05 to consume or re-tune at default zoom: `PAIR_SPACING = 46`, `SELF_LOOP_SPACING = 26`, `LABEL_STAGGER = 0.14`, `BASE_LOOP_RADIUS = 40`, `BACK_EDGE_BASE = 150`, `BACK_EDGE_PER_COLUMN = 90`, `BACK_EDGE_MEMBER_STEP = 60`.
- Normal convention (pinned, must not vary): `n = normalize({x: -(b.y-a.y), y: b.x-a.x})` — screen-down for a horizontal chord pointing +x.
- Achieved apex clearance for definition 186's 2-column back-edge (`rand→trial_onset`): 112.5px below the chord (`0.75 * BACK_EDGE_BASE`), well above the ~35px `StateNode` half-height floor.
- No blockers for 29-05.

---
*Phase: 29-fda-builder-canvas-ux*
*Completed: 2026-08-05*

## Self-Check: PASSED
- FOUND: web_ui/react-src/src/components/edgeGeometry.mts
- FOUND: web_ui/react-src/tests/edgeGeometry.test.mts
- FOUND: .planning/phases/29-fda-builder-canvas-ux/29-02-SUMMARY.md
- FOUND: 7f380ae, f57fd9e, 225cc95
