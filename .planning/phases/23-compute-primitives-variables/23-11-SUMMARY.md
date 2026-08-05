---
phase: 23-compute-primitives-variables
plan: 11
subsystem: ui
tags: [react, typescript, fda-editor, operand-namespace, node-test]

# Dependency graph
requires:
  - phase: 23-compute-primitives-variables (plans 08/09/10)
    provides: compute action + variables panel + preflight issue rendering in the FDA editor
provides:
  - "operandTypes.mts / argModes.mts / trackerMethods.mts — pure, tested decision logic behind
    every operand picker in the FDA editor"
  - "CMP-20/21: condition pickers (transition + if/else) offer view/literal/param on a fresh
    operand; flag/hardware survive only as a same-shape legacy escape"
  - "CMP-22: declared variables are selectable as a flag write action's ref, resolving to the
    Tracker method set (never Counter_Tracker's now-removed decrement/reset)"
  - "CMP-23: ArgInput gains a ~ View mode reading toolkit flags/variables/hardware; ! Flag
    demoted to a legacy escape"
affects: [23-12 (Pi-side compute + trigger-assignment wiring, consolidated rig checkpoint)]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Legacy-operand escape: a retired read form (flag/hardware) is offered in a type <select>
      only when the operand ALREADY stored in that slot has that shape, labelled '(legacy)',
      and disappears the moment the researcher edits it — never a data migration"
    - "Pure decision-logic .mts modules co-located with the .tsx components that consume them,
      each with a node --test contract (operandTypes.mts, argModes.mts, trackerMethods.mts join
      detectorOptions.mts/computeArgs.mts/internalVariables.mts/numericDraft.mts)"

key-files:
  created:
    - web_ui/react-src/src/components/operandTypes.mts
    - web_ui/react-src/src/components/argModes.mts
    - web_ui/react-src/src/components/trackerMethods.mts
    - web_ui/react-src/src/components/FlagActionFields.tsx
    - web_ui/react-src/tests/operandTypes.test.mts
    - web_ui/react-src/tests/argModes.test.mts
    - web_ui/react-src/tests/trackerMethods.test.mts
  modified:
    - web_ui/react-src/src/components/ConditionBuilder.tsx
    - web_ui/react-src/src/components/ArgInput.tsx
    - web_ui/react-src/src/components/ActionEditor.tsx
    - web_ui/react-src/src/components/HardwareActionFields.tsx
    - web_ui/react-src/src/components/StateBodyPanel.tsx
    - web_ui/react-src/src/components/IfActionEditor.tsx
    - web_ui/react-src/src/pages/task-editor/TaskEditor.tsx

key-decisions:
  - "IfActionEditor derives hwModuleNames from its existing hwModules prop (one-line fix)
    instead of threading a new prop through TaskEditor -> StateBodyPanel -> ActionEditor ->
    IfActionEditor — provably equivalent to TaskEditor's own hwModuleNames derivation over the
    same array, per the plan's explicit discretion grant"
  - "Preflight DB query for decrement/reset usage re-run before deletion: 0/153 task definitions
    reference either method on 2026-08-05, matching the plan's prior finding — proceeded with
    deletion rather than the deferred-items.md fallback"
  - "ArgInput's view mode offers plain view keys only (Hardware + Flags & variables groups,
    empty detectors array) — no detector channels (Pi's _resolve_arg has no view_detector
    branch) and no hwModuleNames (would require prop-threading through 5 components for a case
    the free-text fallback already covers) — the scope_decision the plan asked to be recorded
    explicitly so 23-12's checkpoint doesn't test for it"

patterns-established:
  - "visibleOperandTypes(stored, hasToolkit) / visibleArgModes(mode, allowTriggerContext) as the
    single source of truth for which operand/arg spellings a slot offers — legacy types are a
    function of what's ALREADY stored, never a static list"

requirements-completed: [CMP-20, CMP-21, CMP-22, CMP-23]

# Metrics
duration: ~25min
completed: 2026-08-05
---

# Phase 23 Plan 11: Operand-Namespace Consistency Pass Summary

**One read namespace (`view`) across every FDA-editor operand picker, with `flag`/`hardware` retired to a same-shape legacy escape and `decrement`/`reset` removed from the tracker method tables — three new tested `.mts` modules, one extracted component, zero data migration.**

## Performance

- **Duration:** ~25 min (commit span 11:22:02Z – 11:27:28Z, plus initial context load)
- **Started:** 2026-08-05 (session start)
- **Completed:** 2026-08-05T11:28:07Z
- **Tasks:** 3
- **Files modified:** 13 (4 created, 9 modified — HardwareActionFields.tsx counted once across Task 1)

## Accomplishments

- Extracted `operandTypes.mts`, `argModes.mts`, `trackerMethods.mts` out of `ConditionBuilder.tsx`/`ArgInput.tsx`/`ActionEditor.tsx` — behaviour-preserving, pinned by 21 new `node --test` cases before any behaviour changed (Task 1)
- CMP-20: `visibleOperandTypes` narrows a fresh operand's type list to `view`/`literal`/`param`; `flag`/`hardware` are offered only as a same-shape `(legacy)` escape, never both at once, and the round-trip is proven by assertion, not inspection
- CMP-21: `IfActionEditor` now forwards `hwModuleNames` and `variableNames` into its `ConditionBuilder` — the missing wiring that made declared variables and semantic hardware invisible inside `if`/`else` conditions in the state builder (a one-line bug, not a design gap)
- CMP-22: declared variables are selectable as a flag write action's `ref`; all three `?? 'Counter_Tracker'` tracker-type resolutions replaced by `trackerTypeForRef`, so a variable resolves to the `Tracker` method set (increment/set) rather than the wrong Counter_Tracker set; `FlagActionFields.tsx` extracted to keep `ActionEditor.tsx` under budget
- CMP-23: `ArgInput` gains a `~ View` mode (grouped select over toolkit flags + variables + semantic hardware, empty-detectors by design) reading through the same namespace the condition pickers use; `! Flag` demoted to `! Flag (legacy)`, offered only when the stored value is already a flag operand; a re-click-active-pill no-op guard added (mandatory once the flag pill is the only thing keeping a legacy key alive)
- `decrement`/`reset` removed from `TRACKER_METHODS.Counter_Tracker` after a re-run preflight DB query confirmed 0 of 153 task definitions reference either (neither exists on any `Tracker.py` class — picking one saved cleanly and raised `AttributeError` on the rig)

## Task Commits

Each task was committed atomically:

1. **Task 1: Extract operand/arg-mode/tracker-method decision logic into tested .mts modules** - `ecb06cd` (refactor)
2. **Task 2: CMP-20 one read namespace in condition pickers + CMP-21 if-condition wiring** - `7a4ad40` (feat)
3. **Task 3: CMP-22 variables as a write target + CMP-23 the view argument mode** - `4b66001` (feat)

**Plan metadata:** (this commit) `docs(23-11): complete operand-namespace consistency plan`

_TDD tasks: each task's `<behavior>` cases were written and confirmed red before the corresponding implementation edit, per the plan's task-level `tdd="true"` flag — visible in the intermediate red-then-green runs during execution (not separate commits, since the plan's own task boundaries — not RED/GREEN/REFACTOR — are the atomic commit unit here)._

## Files Created/Modified

- `web_ui/react-src/src/components/operandTypes.mts` - Pure operand type/key/build logic + `visibleOperandTypes` legacy-escape rule (`OperandType`, `getOperandType`, `getOperandKey`, `buildOperand`, `operandLabel`, `visibleOperandTypes`, `LEGACY_OPERAND_TYPES`, `resolveDetectorDisplayName`)
- `web_ui/react-src/src/components/argModes.mts` - Pure `ArgInput` mode logic + `visibleArgModes` legacy-escape rule (`ArgMode` now includes `view`; `MODE_COLORS`/`MODE_LABELS`/`MODE_TOOLTIPS` gain `view`, `flag` relabelled legacy)
- `web_ui/react-src/src/components/trackerMethods.mts` - Tracker method tables (`Counter_Tracker` losing decrement/reset) + `trackerTypeForRef` (variables resolve to `'Tracker'`, never `'Counter_Tracker'`)
- `web_ui/react-src/src/components/FlagActionFields.tsx` - Trial-counter + flag write-action branches extracted out of `ActionEditor.tsx` (143 lines)
- `web_ui/react-src/tests/operandTypes.test.mts` - 11 cases: type classification, round-trip identity, the legacy-escape list at every stored shape
- `web_ui/react-src/tests/argModes.test.mts` - 10 cases: mode detection incl. `view`, the trigger + flag legacy escapes, label/color/tooltip completeness
- `web_ui/react-src/tests/trackerMethods.test.mts` - 10 cases: method-set-per-type, no decrement/reset anywhere, variable-to-Tracker resolution
- `web_ui/react-src/src/components/ConditionBuilder.tsx` (243→196 lines) - Imports moved logic; `OperandEditor`'s type `<select>` uses `visibleOperandTypes` and labels legacy entries; `flag`/`hardware` render branches untouched
- `web_ui/react-src/src/components/ArgInput.tsx` (224→217 lines) - Imports moved logic; new `view` mode + render branch; `switchMode` re-click guard
- `web_ui/react-src/src/components/ActionEditor.tsx` (457→327 lines) - Imports moved logic; `regularFlagKeys` unions declared variables; renders `<FlagActionFields>` in place of the two removed JSX branches
- `web_ui/react-src/src/components/HardwareActionFields.tsx` - `TrackerMethod` type repointed to `trackerMethods.mts`
- `web_ui/react-src/src/components/StateBodyPanel.tsx` / `pages/task-editor/TaskEditor.tsx` - `operandLabel` repointed to `operandTypes.mts` (no re-export shim)
- `web_ui/react-src/src/components/IfActionEditor.tsx` - Passes `hwModuleNames`/`variableNames` into its `ConditionBuilder`

## Decisions Made

- `IfActionEditor` derives `hwModuleNames` from its existing `hwModules` prop rather than threading a new prop through four components — provably the same array `TaskEditor.tsx:202` already derives its own `hwModuleNames` from (planner-discretion option explicitly offered by the plan)
- Re-ran the `decrement`/`reset` preflight DB query live before deleting the table entries (0/153 task definitions, matching the plan's 2026-08-05 finding) rather than trusting the plan's stated result blind
- `ArgInput`'s new `view` mode deliberately excludes detector channels and backend-authored module names (`hwModuleNames`) — recorded as the plan's own `<scope_decision>`, restated here so 23-12's checkpoint click-through does not test for something intentionally out of scope

## Deviations from Plan

None — plan executed exactly as written, including the task ordering (extraction before behaviour change) and the preflight-gated deletion.

## Issues Encountered

None.

## User Setup Required

None - no external service configuration required. Explicit reminder from the plan's own `<verification>`: `docker compose up --build web_ui` was NOT run in this plan — the rebuilt SPA reaches a researcher only after 23-12 lands the Pi-side half of the same rule (CMP-24) and its consolidated rig checkpoint.

## Next Phase Readiness

Ready for 23-12 (Pi-side CMP-24/25 + trigger-assignment compute gating + the consolidated rig checkpoint that performs the actual behavioural click-through and `docker compose up --build web_ui`). Nothing in this plan blocks it: `visibleOperandTypes`/`visibleArgModes`/`trackerTypeForRef` are stable exported contracts 23-12 can build on without further React changes.

---
*Phase: 23-compute-primitives-variables*
*Completed: 2026-08-05*

## Self-Check: PASSED

All 7 claimed created/tested files found on disk; all 3 task commit hashes (`ecb06cd`, `7a4ad40`, `4b66001`) found in git log.
