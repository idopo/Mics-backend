---
phase: 25-detector-derived-view-keys-visible-in-the-fda-editor
plan: 05
subsystem: ui
tags: [react, typescript, preflight, hardware-config, detector-keys]

# Dependency graph
requires:
  - phase: 25-detector-derived-view-keys-visible-in-the-fda-editor
    provides: "view_key_unresolved issue shapes from preflight_validate + is_detector on GET /api/hardware-modules/{id}/methods (25-03)"
provides:
  - "HardwareCheckModal renders view_key_unresolved (both DVK-11 detector-channel and literal-key shapes), never PUTs for it, and no longer collides on a duplicate React key"
  - "PilotHardwareConfig offers a first_channel affordance with a live derived-key preview on a detector module's EDIT row, resolved by module name (rows carry no module_id)"
affects: [25-06-pi-deploy-and-rig-proof]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "PilotHardwareConfigRow carries no module_id (free-form, Phase 17) — is_detector is resolved by matching modules.name against the row's current name at both entry points (edit: editName; add: selectedModuleId), sharing one ['hardware-module-methods', id] query key so the add flow's existing template fetch and the display-only useQuery hooks never double-fetch"

key-files:
  created:
    - web_ui/react-src/src/pages/hardware-modules/DetectorChannelFields.tsx
  modified:
    - web_ui/react-src/src/components/HardwareCheckModal.tsx
    - web_ui/react-src/src/pages/hardware-modules/PilotHardwareConfig.tsx
    - web_ui/react-src/src/types/index.ts

key-decisions:
  - "issue.module_name used in the issues.map React key (plus issue.issue + location/index) rather than switching to array index alone — preserves stability for the pre-existing issue kinds while fixing the real collision view_key_unresolved introduces (two bad channels on the same MPR121 previously shared a key)"
  - "handleModulePick's template fetch in PilotHardwareConfig now routes through qc.fetchQuery keyed ['hardware-module-methods', id] instead of a bare getHardwareModuleMethods call, so the add-flow's is_detector useQuery (same key) reads from the already-populated cache instead of firing a second network request"
  - "DetectorChannelFields extracted to a sibling file per the plan's own budget fallback — PilotHardwareConfig.tsx stayed at 378 lines (budget ~400) but the block is shared verbatim between the add and edit flows, which would have meant near-duplicate JSX either way"

requirements-completed: [DVK-06, DVK-09, DVK-11]

# Metrics
duration: 8min
completed: 2026-07-29
---

# Phase 25 Plan 05: HardwareCheckModal Preflight Rendering + first_channel Affordance Summary

**A `view_key_unresolved` preflight issue now renders with the offending channel/key and the pilot's real channels instead of `null`, is provably excluded from the modal's PUT loop, and a detector module's pilot-config editor offers a `first_channel` field with a live derived-key preview.**

## Performance

- **Duration:** ~8 min
- **Started:** 2026-07-29T11:51:38Z
- **Completed:** 2026-07-29T11:59:23Z
- **Tasks:** 2/2
- **Files modified:** 4 (1 created, 3 modified)

## Accomplishments

- `PreflightIssue`'s union gained `'view_key_unresolved'` plus the optional `location` / `key` /
  `available_keys` / `detector` / `available_channels` fields from plan 03's two issue shapes.
- New `ViewKeyIssueDetail` read-only component (in `HardwareCheckModal.tsx`), dispatched from
  `ModuleIssueEditor` before the existing branches: leads with `MPR121 — channel 5` and an
  `available_channels` pill row when `detector` is set (DVK-11 shape — the definition stores a
  channel, not a key), leads with the offending `key` when it's the literal shape, always shows
  `detail` + `location`, and degrades to `detail` alone with no crash when only those two fields
  are present.
- `handleStart` and the `pendingEdits` initialiser both `continue`/skip `view_key_unresolved` —
  it names no config row, so it can no longer trigger a PUT to an empty or wrong path segment
  (the destructive-write regression the plan called out explicitly).
- `issues.map`'s React key changed from `issue.module_name` alone (unsafe once one detector can
  emit several `view_key_unresolved` issues sharing a `module_name`) to
  `` `${issue.issue}:${issue.module_name}:${issue.location ?? i}` ``.
- No start gate added — `handleStart` still always calls `onStart()`; preflight stays advisory
  per Phase 13's decision, as the plan required.
- `HardwareModuleMethods` gained `is_detector: boolean` (already shipped on the backend response
  by plan 03).
- New `DetectorChannelFields.tsx`: a `first_channel` number input (empty input deletes the key
  via a new `setJsonKey` helper — an absent key and an explicit `0` now round-trip distinctly)
  plus a live derived-key preview computed from the config JSON's `device_name` /
  `num_detectors` / `first_channel`, with a comment naming `api/detector_keys.py::derive_view_keys`
  as the single authority for the real derivation and noting this preview shows the pilot's
  resolved names — never a channel index, which is what a task definition stores (DVK-11).
- `PilotHardwareConfig.tsx` resolves `is_detector` by module **name** at both entry points,
  since `PilotHardwareConfigRow` carries no `module_id` (Phase 17): `editingModule` from
  `editName`, `addModule` from `selectedModuleId`. Both use the same
  `['hardware-module-methods', id]` query key; `handleModulePick`'s existing template fetch was
  switched from a bare `getHardwareModuleMethods` call to `qc.fetchQuery` with that same key, so
  the add flow's `is_detector` read never fires a second network request. The field renders on
  the **edit** row (reachable from `startEdit`, the path plan 06 exercises) and on the add form;
  a row whose name matches no module, or a non-detector module, renders unchanged.
- No hardcoded `LICKER` in any rendered string — `deviceName` falls back to a neutral `DEVICE`
  placeholder when absent from the config JSON.

## Task Commits

Each task was committed atomically:

1. **Task 1: render view_key_unresolved (both shapes) and keep it out of the save loop** - `ac2414d` (feat)
2. **Task 2: first_channel is declarable from the pilot hardware config editor** - `7289b10` (feat)

**Plan metadata:** (this commit)

## Files Created/Modified

- `web_ui/react-src/src/components/HardwareCheckModal.tsx` (458 lines) - `PreflightIssue` type
  extension, `ViewKeyIssueDetail` component, `handleStart`/`pendingEdits` skip, unique
  `issues.map` key
- `web_ui/react-src/src/pages/hardware-modules/PilotHardwareConfig.tsx` (378 lines) -
  `editingModule`/`addModule` resolution by name, two `useQuery` hooks reading `is_detector`,
  `handleModulePick` routed through `qc.fetchQuery`, `DetectorChannelFields` rendered on both
  the edit row and the add form
- `web_ui/react-src/src/pages/hardware-modules/DetectorChannelFields.tsx` (created, 113 lines) -
  `setJsonKey`, `deriveKeysPreview` (cosmetic, comment-pinned to the backend authority), the
  `first_channel` input + live key-preview component
- `web_ui/react-src/src/types/index.ts` - `HardwareModuleMethods.is_detector: boolean`

## Decisions Made

- The `issues.map` key change keeps `module_name` in the composite key (not a pure index) to
  stay stable for the four pre-existing issue kinds while fixing the real collision
  `view_key_unresolved` introduces.
- `handleModulePick`'s template fetch was rerouted through `qc.fetchQuery` (same query key as
  the new `is_detector` `useQuery` hooks) specifically to avoid a second network fetch pattern —
  not just to share code, but because the plan called this out as a requirement ("one shared
  `is_detector` value, two entry points, no second fetch pattern").
- `DetectorChannelFields` was extracted to a sibling file rather than inlined, per the plan's own
  budget-fallback instruction — both `PilotHardwareConfig.tsx` (378 lines) and the new file
  (113 lines) stay comfortably under their respective budgets, and the block is shared verbatim
  between the add and edit flows.

## Deviations from Plan

None — plan executed exactly as written.

## Issues Encountered

- `npx vite build` failed with `npm error Missing script: "vite"` in this environment (the rtk
  command-rewriting hook appears to intercept `npx <binary> <args>` and reinterpret it as an
  `npm run` invocation). Worked around by running the project's own `npm run build` script
  (`tsc -b && vite build`), which produces the identical build the plan's verification command
  targets. Both task verifications used `npm run build` for this reason; `npx tsc --noEmit`
  worked normally and was used unchanged.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness

- Plan 06 can now deploy plan 02's Pi-side files, rebuild the `web_ui` container, and rig-prove
  DVK-06/09/11: confirm the deployed bundle contains the new `HardwareCheckModal` chunk
  (**`dist/HardwareCheckModal-DKJUfoGY.js`**, this session) and the new `PilotHardwareConfig`
  chunk (**`dist/PilotHardwareConfig-B09He_Dl.js`**, this session) — never grep `main.js`, both
  are code-split.
- Plan 06 task 3 step 1 opens the existing MPR121 row on `PilotHardwareConfig`'s edit path and
  sets `first_channel: 1` through the new affordance, then reads the row back from the DB to
  confirm the JSON written — this plan's edit-flow resolution (`editingModule` by name) is the
  exact path exercised.
- Plan 06's checkpoint 2 runs both `view_key_unresolved` shapes against the rig pilot (an
  out-of-range detector channel and a literal unknown key) and confirms cancelling the modal
  leaves the MPR121 config intact — behavioural verification this plan deliberately deferred
  (no React render test framework per 25-VALIDATION.md).
- Do not claim DVK-06, DVK-09, or DVK-11 proven from this plan alone — `tsc`/build green proves
  the wiring compiles and the pure logic (key round-trip, preview derivation) is correct, not
  that the UI renders as intended on real data. That proof is plan 06's.

---
*Phase: 25-detector-derived-view-keys-visible-in-the-fda-editor*
*Completed: 2026-07-29*

## Self-Check: PASSED

- FOUND: `web_ui/react-src/src/components/HardwareCheckModal.tsx`
- FOUND: `web_ui/react-src/src/pages/hardware-modules/PilotHardwareConfig.tsx`
- FOUND: `web_ui/react-src/src/pages/hardware-modules/DetectorChannelFields.tsx`
- FOUND: commit `ac2414d`
- FOUND: commit `7289b10`
- Fresh run: `npx tsc --noEmit` — clean
- Fresh run: `npm run build` — succeeds, `dist/HardwareCheckModal-DKJUfoGY.js`,
  `dist/PilotHardwareConfig-B09He_Dl.js`
- `grep -rn "LICKER" web_ui/react-src/src/pages/hardware-modules/ web_ui/react-src/src/components/HardwareCheckModal.tsx` — no matches
