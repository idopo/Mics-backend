---
phase: 24-trigger-assignment-action-lists
plan: 05
subsystem: ui
tags: [react, typescript, fda-editor, trigger-assignments]

requires:
  - phase: 24-03
    provides: "ActionEditor/ArgInput/IfActionEditor with view action, output capture, allowTriggerContext arg mode; HardwareActionFields/ViewActionFields/OutputCapture extraction"
provides:
  - "VariablesPanel — declare/rename/remove FdaJson.variables with collision guards"
  - "TriggerAssignmentPanel rewritten to host the shared ActionEditor per trigger assignment"
  - "typeChipStyle/actionSummary exported from StateBodyPanel for reuse"
  - "TaskEditor variableNames derivation threaded into both panels"
affects:
  - "24-07 (manual checkpoints exercising the trigger panel)"
  - "24-08 (trigger_name dropdown replaces the free-text input added here)"

tech-stack:
  added: []
  patterns:
    - "Placeholder-name seeding on add() (variable1/trigger1, avoiding collisions) instead of writing an empty required field — same pattern used for both VariablesPanel and TriggerAssignmentPanel"
    - "Per-assignment collapsed action-list expander keyed by index (useState<Record<number, boolean>>) so a full action list never pushes the always-visible trigger panel off screen"

key-files:
  created:
    - web_ui/react-src/src/components/VariablesPanel.tsx
  modified:
    - web_ui/react-src/src/components/TriggerAssignmentPanel.tsx
    - web_ui/react-src/src/components/StateBodyPanel.tsx
    - web_ui/react-src/src/pages/task-editor/TaskEditor.tsx

key-decisions:
  - "TriggerAssignmentPanel.add() seeds a non-colliding trigger1/trigger2/... placeholder rather than an empty string, mirroring VariablesPanel's variable1/variable2 pattern — trigger_name is required and the panel must never produce an empty one by construction"
  - "VariablesPanel rename is committed onBlur (uncontrolled input with defaultValue) rather than on every keystroke, to avoid the React key/remount churn that would come from rebuilding the record (and therefore the map key) on each character typed"
  - "Renaming a variable to a name already used by another variable OR by a toolkit.flags key is rejected inline — this mirrors the Pi's load-time ValueError and the backend's 422, catching the collision in the UI first"

requirements-completed: [TRIGA-09]

duration: 6min
completed: 2026-07-27
---

# Phase 24 Plan 05: Trigger Panel Hosts the Shared Action Editor Summary

Rewrote `TriggerAssignmentPanel.tsx` to delete the `handler` enum and `config` fields entirely and host the exact same `ActionEditor` the state-body panel uses per assignment's `actions` list, and added a new `VariablesPanel.tsx` so researchers can declare named `output`/`{token}` slots — both wired into `TaskEditor.tsx`'s existing auto-save path with zero new save mechanism.

## Performance

- **Duration:** 6 min
- **Started:** 2026-07-27T13:18:54Z
- **Completed:** 2026-07-27T13:25:19Z
- **Tasks:** 2 completed
- **Files modified:** 4 (1 created, 3 modified)

## Accomplishments
- A trigger assignment is now exactly `(trigger_name, actions)` — the `handler` enum, `HANDLERS` array, and every `config` field (`hardware_ref`, `view_key`) are gone from `TriggerAssignmentPanel.tsx`. A licker is reached by picking MPR121 as an ordinary hardware action inside the list, same as a valve or an LED.
- Each trigger's action list is edited by the SAME `ActionEditor` component the state body panel uses (imported directly, not reimplemented), with `allowTriggerContext` passed only inside the trigger panel so the `@ Trigger` (`level`/`tick`) arg mode appears there and nowhere else.
- `VariablesPanel.tsx` lets a researcher declare/rename/remove named variables; renaming rejects collisions against existing variable names and `toolkit.flags` inline, before the Pi/backend would reject them.
- `StateBodyPanel` now forwards `variableNames` into its own `ActionEditor` calls too, so state-body actions can capture `output` through the identical mechanism — no trigger-only special case.
- `trigger_name` is a required field; the panel can no longer produce an empty one (`add()` seeds `trigger1`, `trigger2`, ... instead of `''`), with an inline red hint if a user manually clears it.

## Task Commits

Each task was committed atomically:

1. **Task 1: VariablesPanel + TaskEditor variables state** - `ff49d8d` (feat)
2. **Task 2: TriggerAssignmentPanel hosts the shared ActionEditor** - `f81c561` (feat)

**Plan metadata:** (this commit)

## Files Created/Modified
- `web_ui/react-src/src/components/VariablesPanel.tsx` - New: declare/rename/remove `FdaJson.variables`, with an empty-state hint and an inline "Named value slots..." explainer
- `web_ui/react-src/src/components/TriggerAssignmentPanel.tsx` - Rewritten: `trigger_name` + collapsible per-assignment `Actions (N)` list hosting `ActionEditor`; `HANDLERS` array and all `config` fields deleted
- `web_ui/react-src/src/components/StateBodyPanel.tsx` - Added `variableNames?: string[]` prop, forwarded to `ActionEditor`; exported `typeChipStyle`/`actionSummary`; `actionSummary` gained a `view` case
- `web_ui/react-src/src/pages/task-editor/TaskEditor.tsx` - `normaliseFda`/`bootstrapFromToolkit` default `variables: {}`; derived `variableNames`; renders `VariablesPanel` above the trigger panel; threads `hwModules`/`taskDefId`/`versionStamp`/`variableNames` into `TriggerAssignmentPanel` (net diff across both tasks: +25/-1 lines)

## Decisions Made
See `key-decisions` in frontmatter above.

## Deviations from Plan

None — plan executed as written. One documentation note, not a code deviation: the plan's own `<verification>` step 4 (`grep -c "handler\|touch_detector\|digital_input\|config" ... → 0`) initially failed against my first draft because the file's own explanatory comment used the words "handler" and "config" (and "configured") while describing their *absence*. Reworded the comment/empty-state copy to avoid those substrings so the grep is a clean 0, per the plan's literal verification command.

## Issues Encountered

TaskEditor.tsx pre-existed this plan at 792 lines (already over the project's 500-line hard limit, called out in the plan's own hard_constraints as an accepted pre-existing condition with a ≤30-line growth budget rather than a fix-it target). This plan's total contribution was +25/-1 lines across both tasks, well inside that budget. Refactoring TaskEditor.tsx down under 500 lines is out of scope for TRIGA-09 and not attempted here.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness

- TRIGA-09 (trigger panel hosts the shared ActionEditor) is complete and manually verifiable: `docker compose up --build -d web_ui` rebuilt and served (`GET /static/react/main.js` → 200).
- Plan 07's manual checkpoint (add a trigger assignment with 2+ actions, save, reload, confirm identical) can now be exercised against this build.
- Plan 08 (TRIGA-15) will replace the free-text `trigger_name` input added here with a dropdown over `toolkit.trigger_sources`, per 24-CONTEXT.md's explicit note that this plan's free-text input is an intentional intermediate step.

---
*Phase: 24-trigger-assignment-action-lists*
*Completed: 2026-07-27*

## Self-Check: PASSED

- FOUND: web_ui/react-src/src/components/VariablesPanel.tsx
- FOUND: web_ui/react-src/src/components/TriggerAssignmentPanel.tsx
- FOUND: web_ui/react-src/src/components/StateBodyPanel.tsx
- FOUND: web_ui/react-src/src/pages/task-editor/TaskEditor.tsx
- FOUND commit ff49d8d
- FOUND commit f81c561
