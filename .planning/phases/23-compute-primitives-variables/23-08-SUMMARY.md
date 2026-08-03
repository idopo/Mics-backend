---
phase: 23-compute-primitives-variables
plan: 08
subsystem: ui
tags: [react, typescript, fda-editor, task-editor, react-query, compute]

# Dependency graph
requires:
  - phase: 23-compute-primitives-variables
    provides: "plan 23-06's HardwareModule.lib_kind ('hardware'|'compute') on the joined
      hardware_modules row, plan 23-02's seeded COMPUTE hardware_modules row + compute_ops
      lib, plan 24-08's variableNames threading into ConditionBuilder's operand picker"
provides:
  - "One new 'compute' entry in the FDA editor's action-type <select> (state bodies only)"
  - "ComputeActionFields.tsx: a compact `[output] = [op ▾] ( [args] )` row with ops grouped
    by compute lib in a single flattened <select>, and a mandatory output combobox that
    auto-declares a new FdaJson.variables entry the moment a new name is typed"
  - "isComputeModule predicate exported from ActionEditor beside isTimerModule"
  - "onDeclareVariable callback threaded TaskEditor -> StateBodyPanel -> ActionEditor ->
    ComputeActionFields, so a freshly typed output name is a selectable ConditionBuilder
    operand in the same render pass, no save round-trip"
affects: [23-10, "trigger-assignment compute (deferred)"]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "useQueries (react-query v5) fans out getHardwareModuleMethods across N compute
      modules using the SAME ['hardware-module-methods', id] key PilotHardwareConfig.tsx
      already uses — no second cache/fetch path introduced"
    - "allowTriggerContext gate pattern (ArgInput.tsx:76's `allowTriggerContext || mode ===
      X ? ALL : filter(...)`) reused verbatim to hide the compute <option> from
      TriggerAssignmentPanel's action lists while keeping an already-set value readable"

key-files:
  created:
    - web_ui/react-src/src/components/ComputeActionFields.tsx
  modified:
    - web_ui/react-src/src/types/index.ts
    - web_ui/react-src/src/components/ActionEditor.tsx
    - web_ui/react-src/src/components/StateBodyPanel.tsx
    - web_ui/react-src/src/pages/task-editor/TaskEditor.tsx

key-decisions:
  - "ActionEditor's own local TYPE_COLORS (separate from StateBodyPanel's) also got a
    compute:'#8b5cf6' entry, even though only StateBodyPanel's was named in Task 1 — the
    header chip inside the open ActionEditor card would otherwise fall back to gray"
  - "onDeclareVariable added to ActionEditor's Props in Task 1 (needed to compile
    ComputeActionFields's render call), not deferred to Task 3 as the plan's literal
    per-task file list implied — Task 3 only had to add it to StateBodyPanel/TaskEditor"
  - "Reject (not silently reuse) a typed 'new variable' name that already matches an
    existing variable or toolkit flag — forces the researcher back to the select instead
    of typing an ambiguous duplicate"

patterns-established:
  - "A compute lib's ops render as one flattened <optgroup>-grouped <select>, not a
    two-step module-then-method picker like hardware actions get — reusable if a second
    compute-shaped lib category appears"

requirements-completed: [CMP-13, CMP-14]

duration: ~25min
completed: 2026-08-03
---

# Phase 23 Plan 08: Compute Action in the FDA Editor Summary

**One new 'compute' entry in the action-type list renders `[output] = [op ▾] ( [args] )` with ops grouped by lib in a single dropdown, and typing a new output name declares it into `fdaJson.variables` immediately — reachable as a transition operand with no save round-trip.**

## Performance

- **Duration:** ~25 min
- **Completed:** 2026-08-03
- **Tasks:** 3/3
- **Files modified:** 4 (+ 1 created)

## Accomplishments
- The action-type `<select>` gained exactly one new option, `compute`, gated off trigger-assignment action lists (verified: only 1 new `<option>` line across the whole plan's diff)
- `ComputeActionFields.tsx` (177 lines) delivers the compact row: one flattened op picker grouped by compute lib via `<optgroup>`, args driven by the selected op's AST signature, and a mandatory output combobox with a "declare new variable" affordance
- A freshly typed output name writes into `fdaJson.variables` on blur and is immediately selectable in `ConditionBuilder`'s operand dropdown — no save required (CMP-14 reach, verify-only per plan)

## Task Commits

Each task was committed atomically:

1. **Task 1: the compute action type and its wiring seams** - `8b908ad` (feat)
2. **Task 2: ComputeActionFields — grouped op picker + mandatory output combobox** - `42d9f1a` (feat)
3. **Task 3: thread onDeclareVariable from TaskEditor** - `3eacd67` (feat)

**Plan metadata:** pending (this commit)

## Files Created/Modified
- `web_ui/react-src/src/types/index.ts` - `FdaAction['type']` gains `'compute'`; `output` doc comment notes it's mandatory for compute
- `web_ui/react-src/src/components/ActionEditor.tsx` - `isComputeModule` predicate exported beside `isTimerModule`; `TYPE_LABELS`/both `TYPE_COLORS` maps gain `compute`; one gated `<option value="compute">`; `handleTypeChange`'s compute branch; renders `ComputeActionFields`; `onDeclareVariable` added to Props and forwarded
- `web_ui/react-src/src/components/StateBodyPanel.tsx` - `TYPE_COLORS` gains `compute: '#8b5cf6'`; `actionSummary` renders `${output} = ${ref}.${method}(…)`; `onDeclareVariable` threaded through to `ActionEditor`
- `web_ui/react-src/src/components/ComputeActionFields.tsx` (new, 177 lines) - the compute row component: `useQueries`-backed grouped op picker, AST-driven `ArgInput` args, mandatory output combobox with auto-declare, muted hint when no compute lib is linked
- `web_ui/react-src/src/pages/task-editor/TaskEditor.tsx` - new `declareVariable` callback (9-line diff, budget 12), passed to `StateBodyPanel`

## Decisions Made
- `ActionEditor`'s own (separate, unexported) `TYPE_COLORS` const also got a `compute` entry alongside `StateBodyPanel`'s, so the chip inside the open action card is visually distinct rather than falling back to the default gray.
- `onDeclareVariable` was added to `ActionEditor`'s Props in Task 1 rather than Task 3, since Task 1 needed it to compile the `ComputeActionFields` render call and keep that task's own `tsc` green. Task 3 correspondingly needed no `ActionEditor.tsx` diff — see Deviations.
- A typed "new variable" name that collides with an existing variable or toolkit flag is rejected with an inline message rather than silently treated as a re-selection, keeping the sentinel-input path unambiguous.
- The op-fetch reuses the exact `['hardware-module-methods', id]` react-query key `PilotHardwareConfig.tsx` already uses (via `useQueries` for the N-module fan-out), so no second cache/fetch path was introduced for compute.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 - ordering, plan-documented precedent] `onDeclareVariable` added to ActionEditor's Props one task early**
- **Found during:** Task 1 (compile-time requirement to render `<ComputeActionFields onDeclareVariable={onDeclareVariable} .../>`)
- **Issue:** The plan's Task 3 action text says "Add `onDeclareVariable?:` to StateBodyPanel's and ActionEditor's Props," implying both are new in Task 3 — but Task 1 already needs to pass `onDeclareVariable` down to the stub/real `ComputeActionFields`, so the prop had to exist on `ActionEditor`'s Props from Task 1 to keep that task's own `tsc --noEmit` green (the plan's own stated precedent: "plan 25-04's documented ordering deviation exists precisely because each task's own tsc must stay green").
- **Fix:** Added `onDeclareVariable?: (name: string) => void` to `ActionEditor`'s Props in Task 1, forwarded to `ComputeActionFields`. Task 3 then only needed to add the prop to `StateBodyPanel`'s Props and wire `TaskEditor`'s `declareVariable` callback through — `git diff --stat` on `ActionEditor.tsx` for Task 3's commit is empty by design.
- **Files modified:** `web_ui/react-src/src/components/ActionEditor.tsx` (Task 1 commit only)
- **Verification:** `tsc --noEmit` green after every task; Task 3's own diff only touches `StateBodyPanel.tsx` and `TaskEditor.tsx`.
- **Committed in:** `8b908ad` (Task 1 commit)

**2. [Rule 2 - missing critical, visual consistency] compute entry added to ActionEditor's own local TYPE_COLORS too**
- **Found during:** Task 1
- **Issue:** The plan's interfaces note says "TYPE_COLORS lives in StateBodyPanel.tsx" and only Task 1's StateBodyPanel bullet mentions adding `compute`, but `ActionEditor.tsx` has its own separate, unexported `TYPE_COLORS` const (used by its own `cardStyle`/`typeChipStyle` for the open action card's header chip). Without an entry there, the compute action's own editor card would render its type chip in the default gray fallback instead of a distinguishable color — the plan's own must-have ("chips are distinguishable") would fail for the one place the researcher looks at while actually editing a compute action.
- **Fix:** Added `compute: '#8b5cf6'` to `ActionEditor.tsx`'s local `TYPE_COLORS`, same hex as `StateBodyPanel`'s, so the collapsed-row chip and the open-card chip match.
- **Files modified:** `web_ui/react-src/src/components/ActionEditor.tsx`
- **Verification:** Visual only (no automated check); color value matches the plan's explicit `#8b5cf6` instruction for the (singular, as the plan assumed) `TYPE_COLORS`.
- **Committed in:** `8b908ad` (Task 1 commit)

---

**Total deviations:** 2 auto-fixed (1 ordering/Rule 3, 1 missing-critical/Rule 2)
**Impact on plan:** Both are scope-neutral — no new files, no new endpoints, no behavior beyond what the plan specified. No scope creep.

## Issues Encountered
None.

## User Setup Required
None - no external service configuration required.

## Next Phase Readiness

- `tsc --noEmit` and `npm run build` both clean after every task and at plan completion. Bundle hashes: `dist/TaskEditor-CFENcHjp.js` (after Task 2), `dist/TaskEditor-zd-oW4B_.js` (after Task 3, final).
- `git diff --stat` confirmed empty on `App.tsx`, `Layout.tsx`, and `TriggerAssignmentPanel.tsx` across the whole plan — no new page, no new nav entry, and compute in trigger assignments stays deferred and untouched.
- Exactly one new `<option>` in the action-type `<select>`, confirmed via `git diff` across all three task commits against the pre-plan baseline.
- **Behavioural click-through is explicitly DEFERRED to plan 23-10's checkpoint**, per this plan's own `<verification>` note — picking compute, seeing ops grouped, typing a new output name, seeing it in the ConditionBuilder operand dropdown, and a save round-trip have NOT been manually exercised in a browser this plan. Do not treat CMP-13/14 as behaviourally proven from this summary alone.
- `ComputeActionFields.tsx` is 177 lines (budget 120-180, hard cap 300); no `any` types; no `className` usage (matches the sibling components' inline-style-only precedent, so the "only classes present in style.css" check is vacuously satisfied).

---
*Phase: 23-compute-primitives-variables*
*Completed: 2026-08-03*

## Self-Check: PASSED

All created/modified files exist on disk; all three task commits (`8b908ad`, `42d9f1a`, `3eacd67`) confirmed present in `git log --all`.
