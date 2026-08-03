---
phase: 23-compute-primitives-variables
plan: 09
subsystem: ui
tags: [react, typescript, react-query, preflight, fda-editor]

# Dependency graph
requires:
  - phase: 23-compute-primitives-variables (plan 07)
    provides: variable_never_written / lib_version_unresolved / compute_lib_import_failed preflight
      issue shapes and GET /api/task-definitions/{id}/variable-usage
  - phase: 25-detector-derived-view-keys-visible-in-the-fda-editor (plan 05)
    provides: the view_key_unresolved read-only issue-detail + exclusion pattern this plan extends
provides:
  - HardwareCheckModal renders all three of this phase's new preflight issue kinds as readable
    text, never as null
  - NON_CONFIG_ISSUES set — the single source of truth for which preflight issues may never
    trigger a hardware-config PUT
  - Read-only VariableUsagePanel showing per-variable writers/readers inside the task editor
affects: [23-10 (behavioural checkpoint), any future preflight issue kind]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "NON_CONFIG_ISSUES Set<PreflightIssue['issue']> replaces per-kind !== checks at both
      handleStart and the pendingEdits initialiser — adding a new non-config issue kind is a
      one-line Set addition, not two duplicated conditionals"
    - "Read-only issue-detail components (ViewKeyIssueDetail, ComputeIssueDetail) extracted to
      their own files once the host component nears the 500-line hard cap"

key-files:
  created:
    - web_ui/react-src/src/components/ComputeIssueDetail.tsx
    - web_ui/react-src/src/components/VariableUsagePanel.tsx
  modified:
    - web_ui/react-src/src/components/HardwareCheckModal.tsx
    - web_ui/react-src/src/components/VariablesPanel.tsx
    - web_ui/react-src/src/api/task-definitions.ts
    - web_ui/react-src/src/types/index.ts
    - web_ui/react-src/src/pages/task-editor/TaskEditor.tsx

key-decisions:
  - "Extracted ComputeIssueDetail into its own file (not inlined in HardwareCheckModal) — the
    plan's own stated fallback, triggered because the inline version pushed the file to 545
    lines against the 500 hard cap"
  - "VariableUsagePanel uses refetchOnMount: 'always' rather than keying off versionStamp (which
    tracks hardware-lib pins, not fda_json saves) — the plan's own documented fallback when no
    existing save-invalidation key fits"
  - "taskDefId threaded into VariablesPanel via a 1-line TaskEditor.tsx diff, per the plan's own
    instruction (file not listed in this plan's files_modified, but required for the prop to
    reach the panel)"

patterns-established:
  - "Set-based exclusion for cross-cutting issue-kind gating, extending Phase 25's single-kind
    precedent to N kinds without duplicating the check"

requirements-completed: [CMP-14, CMP-15]

# Metrics
duration: 25min
completed: 2026-08-03
---

# Phase 23 Plan 09: Compute Preflight Issue Rendering + Variables Inspector Summary

**HardwareCheckModal renders all three new compute preflight issue kinds as readable text via a
new ComputeIssueDetail component, and a read-only VariableUsagePanel (per-variable writers/readers,
via the plan 07 backend route) sits behind a collapsed disclosure inside VariablesPanel.**

## Performance

- **Duration:** 25 min
- **Started:** 2026-08-03T10:50:00Z
- **Completed:** 2026-08-03T10:57:40Z
- **Tasks:** 2
- **Files modified/created:** 7

## Accomplishments
- `PreflightIssue` union extended with `variable_never_written`, `lib_version_unresolved`,
  `compute_lib_import_failed` (mirroring `toolkit_dispatch.py::PREFLIGHT_ISSUE_KINDS`), each
  rendered as readable text by a new `ComputeIssueDetail` component — no issue kind falls through
  to `null`.
- `NON_CONFIG_ISSUES` — a single `Set` — now gates both `handleStart`'s PUT loop and the
  `pendingEdits` initialiser against all four issue kinds that name no `pilot_hardware_config`
  row (`view_key_unresolved` plus this phase's three), replacing the single-kind `!==` check Phase
  25 introduced.
- New `VariableUsagePanel` renders per-variable writer/reader locations and a `never_written`
  badge, read-only, inside a collapsed `<details>` beneath `VariablesPanel`'s existing declaration
  rows — mechanically confirmed to contain no `onChange`/`mutation`/`button-danger`.

## Task Commits

Each task was committed atomically:

1. **Task 1: render the three new preflight issue kinds** - `bf334cc` (feat)
2. **Task 2: the read-only variables inspector** - `a57cd11` (feat)

**Plan metadata:** (this commit)

## Files Created/Modified
- `web_ui/react-src/src/components/HardwareCheckModal.tsx` - extended `PreflightIssue` union +
  `NON_CONFIG_ISSUES` set; wired `ComputeIssueDetail` into `ModuleIssueEditor`
- `web_ui/react-src/src/components/ComputeIssueDetail.tsx` - new, read-only detail renderer for
  the three compute issue kinds (extracted to keep the modal under the 500-line hard cap)
- `web_ui/react-src/src/components/VariableUsagePanel.tsx` - new, `useQuery` over
  `GET /api/task-definitions/{id}/variable-usage`, one collapsed row per variable
- `web_ui/react-src/src/components/VariablesPanel.tsx` - renders `VariableUsagePanel` behind a
  collapsed `<details>`; gained `taskDefId?: number` prop
- `web_ui/react-src/src/api/task-definitions.ts` - `getVariableUsage(taskDefId)`
- `web_ui/react-src/src/types/index.ts` - `VariableUsage` / `VariableUsageResponse`
- `web_ui/react-src/src/pages/task-editor/TaskEditor.tsx` - 1-line diff threading
  `taskDefId={numId}` into the `<VariablesPanel />` call site

## Decisions Made
- Extracted `ComputeIssueDetail` to its own file rather than inlining it in
  `HardwareCheckModal.tsx` — the inline version measured 545 lines against the plan's explicit
  500-line hard cap; the plan itself named this exact fallback ("extract `ComputeIssueDetail`
  into its own file and import it").
- Used `refetchOnMount: 'always'` for `VariableUsagePanel`'s query rather than keying off
  `versionStamp` — that stamp tracks hardware-lib version pins (a different concern), not
  `fda_json` saves, and using it would be a misleading signal. This is the plan's own documented
  fallback ("If no such key exists, `refetchOnMount: 'always'` matches the PilotSessions
  precedent").
- Threaded `taskDefId` through a 1-line `TaskEditor.tsx` edit even though that file isn't listed
  in this plan's `files_modified` — the plan explicitly anticipated and sanctioned this
  ("thread it from `TaskEditor.tsx` — that is a 1-line change there and TaskEditor already has
  it").

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 - Blocking] Extracted ComputeIssueDetail to its own file**
- **Found during:** Task 1
- **Issue:** Inlining `ComputeIssueDetail` in `HardwareCheckModal.tsx` pushed the file to 545
  lines, over the plan's stated 500-line hard cap.
- **Fix:** Moved the component to `ComputeIssueDetail.tsx`, importing `PreflightIssue` as a
  type-only import (erased at compile time, so no runtime circular dependency between the two
  files despite each importing from the other).
- **Files modified:** `web_ui/react-src/src/components/HardwareCheckModal.tsx`,
  `web_ui/react-src/src/components/ComputeIssueDetail.tsx`
- **Verification:** `wc -l HardwareCheckModal.tsx` → 490; `tsc --noEmit` and `npm run build` both
  clean.
- **Committed in:** `bf334cc` (Task 1 commit)

---

**Total deviations:** 1 auto-fixed (1 blocking — file-size hard cap)
**Impact on plan:** Exactly the fallback the plan itself specified for this scenario. No scope
change.

## Issues Encountered
None.

## User Setup Required
None - no external service configuration required.

## Next Phase Readiness
- Every preflight issue kind this phase introduces now renders as readable text; none can trigger
  a destructive config PUT (mechanically verified via `NON_CONFIG_ISSUES` and grep for the four
  excluded kinds at both call sites).
- Per-variable writers/readers are inspectable inside the task editor with no new page and no new
  nav entry (`App.tsx`/`Layout.tsx` diffs both empty).
- Behavioural sign-off (craft a task def reading an unwritten variable, confirm the live
  `variable_never_written` payload renders correctly in the browser and that Start does not PUT
  for it) is explicitly deferred to plan 23-10's checkpoint, per this plan's own `<verification>`
  note.

---
*Phase: 23-compute-primitives-variables*
*Completed: 2026-08-03*

## Self-Check: PASSED

All 7 created/modified files found on disk; both task commits (`bf334cc`, `a57cd11`) found in
`git log --all`.
