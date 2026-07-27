---
phase: 24-trigger-assignment-action-lists
plan: 03
subsystem: react-fda-editor
tags: [react, typescript, fda-editor, action-vocabulary]
dependency_graph:
  requires: []
  provides:
    - "FdaAction.view type with output/key_template/value/kwargs"
    - "FdaOperand trigger context (level|tick)"
    - "FdaJson.variables registry"
    - "ArgInput 4th mode (trigger context), variableNames-merged flag options"
    - "HardwareActionFields component (extracted from ActionEditor)"
    - "ViewActionFields component"
    - "OutputCapture component"
  affects:
    - "web_ui/react-src/src/components/TriggerAssignmentPanel.tsx (Plan 05 rewrites)"
    - "web_ui/react-src/src/components/IfActionEditor.tsx"
    - "web_ui/react-src/src/components/StateBodyPanel.tsx"
tech_stack:
  added: []
  patterns:
    - "Pure-move component extraction to enforce the 500-line file limit"
    - "Circular value export (labelStyle, isTimerModule) between ActionEditor and its extracted child"
    - "Prop-drilled variableNames/allowTriggerContext through two recursion hops (IfActionEditor -> ActionEditor -> IfActionEditor)"
key_files:
  created:
    - web_ui/react-src/src/components/HardwareActionFields.tsx
    - web_ui/react-src/src/components/ViewActionFields.tsx
    - web_ui/react-src/src/components/OutputCapture.tsx
  modified:
    - web_ui/react-src/src/types/index.ts
    - web_ui/react-src/src/components/ArgInput.tsx
    - web_ui/react-src/src/components/ActionEditor.tsx
    - web_ui/react-src/src/components/IfActionEditor.tsx
    - web_ui/react-src/src/components/StateBodyPanel.tsx
    - web_ui/react-src/src/components/TriggerAssignmentPanel.tsx
decisions:
  - "TriggerAssignmentPanel.add() patched with actions:[] (one line) to keep the codebase compiling after FdaTriggerAssignment.actions became required — Plan 05 fully rewrites this file, so no further redesign happens here."
  - "isTimerModule and TrackerMethod duplicated/exported (not threaded as props) between ActionEditor and HardwareActionFields, matching the plan's explicit labelStyle precedent — both are pure, render-time-only reads, so the circular value export is safe under Vite/esbuild."
  - "OutputCapture and the view-type dropdown option render at consistent JSX positions (after all per-type fields) rather than duplicated per action type, since a single shared boolean condition already covers hardware/timer/method."
metrics:
  duration_minutes: 45
  completed: 2026-07-27
  tasks_completed: 3
  tasks_total: 3
  files_changed: 8
---

# Phase 24 Plan 03: Shared Action Editor Vocabulary Extension Summary

Extended the shared `ActionEditor`/`ArgInput` React components with the three new vocabulary items a trigger's action list needs — a `view` action type, `output` return-value capture, and a trigger-context (`level`/`tick`) arg mode — while extracting the hardware/timer form into its own component to bring `ActionEditor.tsx` back under the 500-line hard limit.

## What Was Built

**Task 1 — Schema types + ArgInput trigger-context mode.** `types/index.ts` gained `FdaAction.view/output/key_template/value/kwargs`, `FdaOperand.trigger`, `FdaVariable`, and `FdaJson.variables`; `FdaTriggerAssignment.actions` became required with `handler`/`config` marked `@deprecated`-optional for backward-compatible parsing. `ArgInput.tsx` gained a 4th mode (`trigger`, gated by a new `allowTriggerContext` prop, defensively still rendered if the stored value is already a trigger operand) and a `variableNames` prop that merges declared variables into the flag-mode option list.

Because `FdaTriggerAssignment.actions` became required, `TriggerAssignmentPanel.tsx` (out of scope for this plan — Plan 05 rewrites it) failed to compile; a one-line fix (`actions: []` in its `add()` seed) restored a clean `tsc --noEmit` without touching the rest of that file.

**Task 2 — Extracted `HardwareActionFields`.** Moved the entire hardware/timer JSX block (device/method dropdowns, AST/timer/legacy arg rows), its method-fetch state (`methods`, `methodsLoading`, module-level `METHOD_CACHE`), the fetch effect, and `handleModuleChange` out of `ActionEditor.tsx` into a new `HardwareActionFields.tsx`. `labelStyle`, `isTimerModule`, and `TrackerMethod` are exported from `ActionEditor` and imported back (the same pattern the plan uses for `labelStyle`) since `ActionEditor`'s own `handleTypeChange` still needs them. Zero behavioral change — confirmed via clean `tsc --noEmit` and successful `npm run build` before and after. `ActionEditor.tsx` dropped from 533 to 362 lines at this checkpoint.

**Task 3 — `view` action + `output` capture + prop threading.** Added `view` to the type dropdown (seeds `key_template`/`value`/`kwargs`, strips the previous type's fields for free since every `handleTypeChange` branch already constructs a fresh action object rather than spreading the old one). New `ViewActionFields.tsx` renders the target-key template input (with clickable variable chips that append `{name}`) and a Value `ArgInput` — deliberately no `pi_timestamp` control, per the 2026-07-27 decision that the Pi injects it silently from the trigger tick; any pre-existing `kwargs` render read-only so a hand-edited definition's data is never silently dropped. New `OutputCapture.tsx` renders a collapsed "capture return value" toggle for hardware/timer/method actions, supporting both single-name and positional tuple-unpack (`output: ['a','b']`) forms, with a disabled/hint state when no variables are declared. `variableNames`/`allowTriggerContext` were threaded into every `ArgInput` call site across `ActionEditor`, into `HardwareActionFields`, `ViewActionFields`, `OutputCapture`, and both `IfActionEditor` recursion hops (then AND else). The `view` colour chip (`#ec4899`) was added to both `ActionEditor` and `StateBodyPanel`'s `TYPE_COLORS`/`TYPE_LABELS`.

## Verification

```
$ cd web_ui/react-src && npx tsc --noEmit
TypeScript compilation completed

$ npm run build
...
dist/main.js                          204.09 kB │ gzip:  65.33 kB
dist/TaskEditor-CYLmUjzA.js           243.79 kB │ gzip:  75.59 kB
✓ built in 1.67s

$ wc -l src/components/ActionEditor.tsx
419 src/components/ActionEditor.tsx   # < 500, hard limit satisfied

$ grep -rn "\bany\b" src/components/{ViewActionFields,OutputCapture,HardwareActionFields}.tsx
(no matches)

$ test $(grep -c "allowTriggerContext" components/IfActionEditor.tsx) -ge 4 \
  && test $(grep -c "variableNames" components/IfActionEditor.tsx) -ge 4 && echo IF_RECURSION_WIRED
IF_RECURSION_WIRED

$ test $(grep -c "allowTriggerContext={allowTriggerContext}" components/IfActionEditor.tsx) -ge 2 && echo IF_BOTH_BRANCHES_FORWARDED
IF_BOTH_BRANCHES_FORWARDED

$ grep -n "view" components/StateBodyPanel.tsx | grep -i "ec4899" && echo VIEW_CHIP_PRESENT
     9:  view: '#ec4899',
VIEW_CHIP_PRESENT
```

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 - Blocking issue] `TriggerAssignmentPanel.tsx` broken by `FdaTriggerAssignment.actions` becoming required**
- **Found during:** Task 1
- **Issue:** Making `actions` a required field on `FdaTriggerAssignment` (per the plan's explicit schema and the 2026-07-26 "handler enum dropped" decision) broke `TriggerAssignmentPanel.tsx`'s `add()` function, which constructed `{ trigger_name: '', handler: 'touch_detector' }` with no `actions` key.
- **Fix:** Added `actions: []` to that one object literal — the minimal change to keep `tsc --noEmit` clean. `TriggerAssignmentPanel.tsx` is out of scope for this plan (Plan 05 hosts the shared `ActionEditor` there and rewrites the file), so no further changes were made.
- **Files modified:** `web_ui/react-src/src/components/TriggerAssignmentPanel.tsx`
- **Commit:** f5e4650

No other deviations — Tasks 2 and 3 matched the plan's specified component contracts, extraction scope, and prop-threading requirements exactly.

## Self-Check: PASSED

- FOUND: web_ui/react-src/src/components/HardwareActionFields.tsx
- FOUND: web_ui/react-src/src/components/ViewActionFields.tsx
- FOUND: web_ui/react-src/src/components/OutputCapture.tsx
- FOUND commit f5e4650
- FOUND commit 2f3d575
- FOUND commit ed763ef
