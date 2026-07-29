---
phase: 25-detector-derived-view-keys-visible-in-the-fda-editor
plan: 04
subsystem: ui
tags: [react, typescript, fda-editor, detector-keys, node-test, condition-builder]

# Dependency graph
requires:
  - phase: 25-detector-derived-view-keys-visible-in-the-fda-editor
    provides: "detector_channels on GET /api/toolkits/by-name/{name} (25-03) — the exact grouped shape this plan's picker renders"
provides:
  - "web_ui/react-src/src/components/detectorOptions.mts — the single option-assembly/operand-encoding module behind every view-operand picker (buildViewOptions/viewOperandToOptionValue/optionValueToViewOperand/isKnownViewOption/detectorOperandLabel/buildKeyTemplateSuggestions)"
  - "ConditionBuilder's OperandEditor renders a grouped, optgroup-labelled view-operand <select> emitting {\"view_detector\": {\"ref\", \"channel\"}} for a picked channel — never a resolved per-pilot key (DVK-11)"
  - "detectorChannels?: DetectorChannelGroup[] threaded end to end: TaskEditor -> {StateBodyPanel, TriggerAssignmentPanel, ConditionGroupsEditor} -> ActionEditor -> IfActionEditor -> ConditionRow/ViewActionFields"
  - "ViewActionFields' key_template field offers device-prefix + derived-key completions from the same shared builder (DVK-04), while staying free text (DVK-05)"
affects: [25-05-hardware-check-modal, 25-06-pi-deploy-and-rig-proof]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "detectorOptions.mts is a pure .mts module (no React import) tested with node:test over node --test \"tests/**/*.test.mts\" — zero new npm dependencies, zero Vitest/jsdom setup"
    - "A detector channel is represented in the operand <select> only as an opaque \"@detector/<module>#<channel>\" token; optionValueToViewOperand resolves it by scanning the backend's own detector_channels for a matching (module_name, channel) pair, never by parsing the token string"

key-files:
  created:
    - web_ui/react-src/src/components/detectorOptions.mts
    - web_ui/react-src/tests/detectorOptions.test.mts
  modified:
    - web_ui/react-src/src/types/index.ts
    - web_ui/react-src/src/components/ConditionBuilder.tsx
    - web_ui/react-src/src/components/ConditionGroupsEditor.tsx
    - web_ui/react-src/src/components/StateBodyPanel.tsx
    - web_ui/react-src/src/components/ActionEditor.tsx
    - web_ui/react-src/src/components/IfActionEditor.tsx
    - web_ui/react-src/src/components/TriggerAssignmentPanel.tsx
    - web_ui/react-src/src/components/ViewActionFields.tsx
    - web_ui/react-src/src/pages/task-editor/TaskEditor.tsx
    - web_ui/react-src/package.json

key-decisions:
  - "getOperandKey delegates to getOperandType(op) === 'view' rather than repeating a literal 'view_detector' in op check — keeps view/tracker/view_detector shape-awareness concentrated in getOperandType alone instead of duplicated across two functions"
  - "S3's display-name resolution (resolveDetectorDisplayName) stays a private helper in ConditionBuilder.tsx, not an export of detectorOptions.mts — it is a one-off UI concern (what to show when switching operand type away from a detector channel), not general operand encoding, and the plan's exports list for the module does not include it"
  - "ViewActionFields' detectorChannels prop and its wiring from ActionEditor were deferred from task 2 to task 3 — passing the JSX prop before the component declared it would have failed tsc's excess-property check; task 3 adds the Props field and the forward together"

patterns-established:
  - "One shared option builder (detectorOptions.mts) feeds all three picker call sites — transition conditions, state-body if-conditions, and trigger action lists — so DVK-03/04/05/11 cannot drift apart between components"

requirements-completed: [DVK-03, DVK-04, DVK-05, DVK-07, DVK-11]

# Metrics
duration: 12min
completed: 2026-07-29
---

# Phase 25 Plan 04: Detector Channels as First-Class Pickable FDA Operands Summary

**The FDA editor's view-operand `<select>` now offers detector channels as their own labelled group (e.g. "LICKER channels") and picking one emits `{"view_detector": {"ref": "MPR121", "channel": 2}}` — a detector reference, never a resolved per-pilot key — via a single tested `.mts` module shared by every picker in the editor.**

## Performance

- **Duration:** ~12 min
- **Started:** 2026-07-29T11:37:40Z (from prior plan's completion)
- **Completed:** 2026-07-29T11:49:40Z
- **Tasks:** 3/3
- **Files modified:** 11 (2 created, 9 modified)

## Accomplishments

- `detectorOptions.mts` (185 lines) is the one place that decides which view-operand options
  appear, how they're grouped/labelled, what a selection encodes, and whether a stored value is
  unknown — `buildViewOptions`, `viewOperandToOptionValue`, `optionValueToViewOperand`,
  `isKnownViewOption`, `detectorOperandLabel`, `buildKeyTemplateSuggestions`. 24 `node:test`
  cases cover grouping (including the "TONGUE not LICKER" regression from phase 24's two prior
  hardcoding bugs), the DVK-11 round trip (channel comes back as a `number`, not `"2"`), the
  DVK-05 unknown-key escape, and DVK-04's suggestion ordering — all green via
  `node --test "tests/**/*.test.mts"`, zero new npm dependencies.
- `ConditionBuilder.tsx`'s `OperandEditor` renders `buildViewOptions`' groups as
  `<optgroup>`-labelled `<option>`s: a "Hardware" group for the devices themselves, one group
  per detector labelled by its `device_name` (e.g. "LICKER channels"), and "Flags & variables" —
  detector channels are never mixed into the Hardware group they come from, and never leak into
  the flag picker (DVK-07). Picking a channel option emits `{"view_detector": {"ref": "MPR121",
  "channel": 2}}` through `optionValueToViewOperand`.
- The keep-current-value escape (`ConditionBuilder.tsx` line 85 pre-plan) survives verbatim and
  now renders `{key} (unknown)` when `isKnownViewOption` returns false — for keys the backend
  cannot model (a Python-only tracker, a hand-authored definition), not for migrating legacy
  detector keys, of which the DB has none (25-03 SUMMARY / CONTEXT S6).
- S3 fix: switching a detector-channel operand's type away from `view` resolves the display name
  (e.g. `"LICKER2"`) first, so the opaque `"@detector/MPR121#2"` select token never leaks into
  `{"flag": "@detector/MPR121#2"}`.
- `detectorChannels?: DetectorChannelGroup[]` threaded through the full component chain
  (`TaskEditor` → `StateBodyPanel`/`TriggerAssignmentPanel`/`ConditionGroupsEditor` →
  `ActionEditor` → `IfActionEditor` → `ConditionRow`/`ViewActionFields`), exactly alongside the
  existing `variableNames` prop, with zero new context or store.
- `ViewActionFields`' `key_template` field now offers `{device_name}` (disabled with a hint when
  no `source_ref` is set — matches `fda_validation.py:302`'s hard-422), one pill per declared
  variable, and one pill per derived detector key (hinted "pilot-specific — prefer
  {device_name}") — all from the same shared builder. The field stays fully free text (DVK-05).
  `DetectorWriteWidget.tsx` (the trigger `view` action's constrained one-pick affordance) is
  untouched — confirmed by an empty `git diff` for that file across all three commits.
- `ActionEditor.tsx` grew by 5 net lines, `TriggerAssignmentPanel.tsx` by 4 — both stayed within
  the "prop declaration + forward only" budget. `ConditionBuilder.tsx` is 239 lines (budget 300),
  `ViewActionFields.tsx` is 103 lines (budget 200).
- `npx tsc --noEmit` clean and `npx vite build` succeeds after every task. Final bundle:
  **`dist/TaskEditor-B6-dKcPk.js`** — this is the deployed-bundle filename plan 06 should confirm
  after the `web_ui` container rebuild (never grep `main.js`; `TaskEditor` is its own code-split
  chunk).

## Task Commits

Each task was committed atomically:

1. **Task 1: detectorOptions.mts + the zero-dependency React test path** - `305dc89` (test)
2. **Task 2: grouped picker emitting view_detector + prop threading** - `b9dd1a3` (feat)
3. **Task 3: key_template is picked, not typed** - `ce53847` (feat)

**Plan metadata:** (this commit)

## Files Created/Modified

- `web_ui/react-src/src/components/detectorOptions.mts` (created, 185 lines) - pure
  option-assembly + operand-encoding module; no React import, explicit return types, no `any`
- `web_ui/react-src/tests/detectorOptions.test.mts` (created) - 24 `node:test` cases
- `web_ui/react-src/src/types/index.ts` (modified) - `DetectorChannelPilot`,
  `DetectorChannelGroup`, `ToolkitRead.detector_channels?`, `FdaOperand`'s new `view_detector`
  member
- `web_ui/react-src/src/components/ConditionBuilder.tsx` (modified, 239 lines) - grouped
  `<optgroup>` picker, `view_detector` branches in `getOperandType`/`operandLabel`, S3 display-key
  resolution on type switch, `detectorChannels` prop threaded through `OperandEditor`/
  `ConditionRow`/`ConditionBuilder`
- `web_ui/react-src/src/components/ConditionGroupsEditor.tsx` (modified) - `detectorChannels`
  prop forwarded to `ConditionRow`
- `web_ui/react-src/src/components/StateBodyPanel.tsx` (modified) - `detectorChannels` prop
  forwarded to `ActionEditor`
- `web_ui/react-src/src/components/ActionEditor.tsx` (modified) - `detectorChannels` prop
  forwarded to `ViewActionFields` and `IfActionEditor`
- `web_ui/react-src/src/components/IfActionEditor.tsx` (modified) - `detectorChannels` prop
  forwarded to the top-level `ConditionBuilder` call and both `then`/`else` recursive
  `ActionEditor` calls
- `web_ui/react-src/src/components/TriggerAssignmentPanel.tsx` (modified) - `detectorChannels`
  prop forwarded to the expanded-action-list `ActionEditor`
- `web_ui/react-src/src/components/ViewActionFields.tsx` (modified, 103 lines) - `key_template`
  suggestions from `buildKeyTemplateSuggestions`, `detectorChannels` prop added
- `web_ui/react-src/src/pages/task-editor/TaskEditor.tsx` (modified) - `detectorChannels`
  derived from `toolkit?.detector_channels ?? []`, passed to all three call sites
- `web_ui/react-src/package.json` (modified) - `test:unit` script only; `dependencies`/
  `devDependencies` byte-identical to before

## Decisions Made

- `getOperandKey` delegates to `getOperandType(op) === 'view'` rather than repeating a literal
  `'view_detector' in op` check, so shape-awareness for the view/tracker/view_detector trio stays
  concentrated in `getOperandType` alone.
- S3's detector-display-name resolution is a private `ConditionBuilder.tsx` helper, not a
  `detectorOptions.mts` export — it's a one-off UI concern for the type-switch case, and the
  plan's export list for the module (`buildViewOptions`, `isKnownViewOption`,
  `viewOperandToOptionValue`, `optionValueToViewOperand`, `detectorOperandLabel`,
  `buildKeyTemplateSuggestions`) does not include it.
- `ViewActionFields`' `detectorChannels` prop and `ActionEditor`'s forward to it were moved from
  task 2 to task 3 — adding the JSX attribute before `ViewActionFields.tsx` declared the prop
  would have failed `tsc`'s excess-property check on the JSX element.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 - Blocking] Added the detector-channel types to `types/index.ts` during task 1, not task 2**
- **Found during:** Task 1 (`detectorOptions.mts` + test path)
- **Issue:** The module's `import type { DetectorChannelGroup, FdaOperand } from '../types/index.ts'`
  requires those exports to exist for `npx tsc --noEmit` to pass — but the plan's task 1 file list
  did not include `types/index.ts` (that was task 2's file), so a clean tsc for task 1 alone was
  impossible without adding them first.
- **Fix:** Added `DetectorChannelPilot`, `DetectorChannelGroup`, `ToolkitRead.detector_channels?`,
  and the `FdaOperand` `view_detector` member during task 1, exactly per the plan's own
  `<interfaces>` shape. Task 2 reused them without re-adding.
- **Files modified:** `web_ui/react-src/src/types/index.ts`
- **Verification:** `npx tsc --noEmit` clean and `npm run test:unit` green after task 1's commit.
- **Committed in:** `305dc89` (Task 1 commit)

**2. [Rule 3 - Blocking] Deferred `ViewActionFields`' `detectorChannels` wiring from task 2 to task 3**
- **Found during:** Task 2 (grouped picker + prop threading)
- **Issue:** The plan's threading instructions say to forward `detectorChannels` "exactly where
  `variableNames` already forwards" — which includes `ActionEditor`'s `ViewActionFields` call.
  But `ViewActionFields.tsx`'s `Props` interface (task 3's file) did not yet declare that prop;
  passing it in JSX would fail `tsc`'s excess-property check on the element.
- **Fix:** Left `ActionEditor`'s `ViewActionFields` call unchanged in task 2; added both the
  `Props` field and the forward together in task 3, matching task 3's own action text ("take it
  from ActionEditor (threaded in task 2)" — read as "the value flows through task 2's chain",
  not "the JSX attribute is written in task 2").
- **Files modified:** `web_ui/react-src/src/components/ActionEditor.tsx`,
  `web_ui/react-src/src/components/ViewActionFields.tsx`
- **Verification:** `npx tsc --noEmit` clean, `npx vite build` succeeds, after both task 2 and
  task 3's commits.
- **Committed in:** `b9dd1a3` (task 2, unchanged call site), `ce53847` (task 3, prop + wire added)

---

**Total deviations:** 2 auto-fixed (both Rule 3 - blocking issues, both about keeping each
task's own `tsc --noEmit` verification green given the plan's task/file split).
**Impact on plan:** Both deviations are ordering-only — the final shipped code matches the
plan's `<interfaces>` and threading routes exactly. No scope creep, no behavior change from what
was specified.

## Issues Encountered

None beyond the two deviations above.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness

- Plan 05 (HardwareCheckModal) can proceed independently — it renders `preflight_validate`'s
  `view_key_unresolved` issues (25-03) and does not depend on this plan's editor changes.
- Plan 06 (deploy + rig proof) should confirm the deployed bundle is
  **`dist/TaskEditor-B6-dKcPk.js`** after rebuilding the `web_ui` container, and can use this
  real emitted operand as the exact shape to look for in `GET /api/task-definitions/<id>`:

```json
{"view_detector": {"ref": "MPR121", "channel": 2}}
```

  (Produced live via `optionValueToViewOperand('@detector/MPR121#2', detectors)` against a
  toolkit-100-shaped `detector_channels` fixture — the same function the running editor calls.)
- Behavioural verification of the rendered pickers (grouped `<optgroup>`s, the "(unknown)" flag,
  the S3 type-switch guard, the `key_template` pill row) is manual and belongs to plan 06's
  checkpoint, per this plan's own `<verification>` note — a green `tsc`/build proves the wiring
  compiles and the pure logic is correct, not that the UI renders as intended.

---
*Phase: 25-detector-derived-view-keys-visible-in-the-fda-editor*
*Completed: 2026-07-29*

## Self-Check: PASSED

- FOUND: `web_ui/react-src/src/components/detectorOptions.mts`
- FOUND: `web_ui/react-src/tests/detectorOptions.test.mts`
- FOUND: `web_ui/react-src/src/components/ConditionBuilder.tsx`
- FOUND: `web_ui/react-src/src/components/ViewActionFields.tsx`
- FOUND: commit `305dc89`
- FOUND: commit `b9dd1a3`
- FOUND: commit `ce53847`
- Fresh run: `npm run test:unit` — 24/24 passed
- Fresh run: `npx tsc --noEmit` — clean
- Fresh run: `npx vite build` — succeeds, `dist/TaskEditor-B6-dKcPk.js`
- `git diff` `DetectorWriteWidget.tsx` and `normaliseTransition`/`normaliseFda` in
  `TaskEditor.tsx` across all three commits — both empty, as required
