---
phase: 23-compute-primitives-variables
plan: 06
subsystem: ui
tags: [react, typescript, hardware-libs, compute-lib, vite]

# Dependency graph
requires:
  - phase: 23-compute-primitives-variables (plan 02)
    provides: "backend kind column + declared_imports on hardware_libs/hardware_lib_versions, POST /api/hardware-libs kind/declared_imports fields, 422 validation messages"
provides:
  - "LibKind type + kind/declared_imports/lib_kind fields on HardwareLib/HardwareLibVersion/HardwareModule"
  - "kind filter chip row + kind-aware upload form on the existing Hardware Libraries page"
  - "read-only kind + declared_imports display on the Hardware Lib detail page"
affects: [23-08]

# Tech tracking
tech-stack:
  added: []
  patterns: ["badge + status-* class composition reused for a selected/unselected chip toggle (chipClass), mirroring the existing stateClass helper"]

key-files:
  created: []
  modified:
    - web_ui/react-src/src/types/index.ts
    - web_ui/react-src/src/api/hardware_libs.ts
    - web_ui/react-src/src/pages/hardware-libs/HardwareLibs.tsx
    - web_ui/react-src/src/pages/hardware-libs/HardwareLibDetail.tsx

key-decisions:
  - "Compute kind badge on list rows and the detail top bar reuses the existing meta-pill class (lavender pill) rather than status-* colors, since those are already claimed by active_state/chip-selection semantics"
  - "Filter chip selected state reuses badge + status-completed (like stateClass's stable case); unselected is plain badge — no new CSS added"
  - "apiFetch already surfaces the backend's 422 detail string verbatim (formatDetail in api/client.ts, pre-existing) — no change needed there, confirmed by reading the source"

requirements-completed: [CMP-12, CMP-18]

duration: 10min
completed: 2026-08-03
---

# Phase 23 Plan 06: Kind-Aware Hardware Libraries UI Summary

**Compute libs now surface on the existing Hardware Libraries page behind an All/Hardware/Compute filter chip row and a kind-aware upload form — zero new pages, zero new nav entries.**

## Performance

- **Duration:** ~10 min
- **Started:** 2026-08-03T10:00:00Z
- **Completed:** 2026-08-03T10:10:10Z
- **Tasks:** 2
- **Files modified:** 4

## Accomplishments
- `LibKind = 'hardware' | 'compute'` threaded through `HardwareLib.kind`, `HardwareLibVersion.declared_imports`, `HardwareModule.lib_kind` (with a comment pointing at plan 23-08's compute op picker)
- `uploadHardwareLib` now sends `kind` and JSON-encoded `declared_imports` FormData fields, defaulting to `'hardware'` / `[]` for backward compat
- Hardware Libraries page gained one filter chip row (`All (n) / Hardware (n) / Compute (n)`) filtering the already-fetched list client-side, plus a `meta-pill` "compute" badge on compute rows only
- Upload form gained a `kind` select and, only when `compute` is selected, a comma-separated `declared_imports` text input with stdlib-only helper text
- `HardwareLibDetail.tsx` shows the `kind` pill and the selected version's `declared_imports`, read-only

## Task Commits

1. **Task 1: kind-aware types and upload client** - `3819908` (feat)
2. **Task 2: the kind filter chip and compute upload form (CMP-18)** - `7046c9e` (feat)

## Files Created/Modified
- `web_ui/react-src/src/types/index.ts` - `LibKind`, `HardwareLib.kind`, `HardwareLibVersion.declared_imports`, `HardwareModule.lib_kind`
- `web_ui/react-src/src/api/hardware_libs.ts` - `uploadHardwareLib` gains `kind`/`declaredImports` params, appended to FormData
- `web_ui/react-src/src/pages/hardware-libs/HardwareLibs.tsx` - kind filter chip row + counts, per-row compute badge, kind-aware `UploadForm`
- `web_ui/react-src/src/pages/hardware-libs/HardwareLibDetail.tsx` - kind pill + declared_imports display in the top metadata bar

## Decisions Made
- Reused `meta-pill` (existing lavender pill class) for the "compute" kind badge instead of a `status-*` class, since those colors already carry `active_state`/chip-selection meaning on this page — avoids ambiguity without inventing a new class name.
- Filter chip selected/unselected treatment composes `badge` + `status-completed` (selected) vs bare `badge` (unselected), the same composition pattern `stateClass` already uses for `active_state` — satisfies the plan's "reuse stateClass-style composition, do not add new CSS" instruction.
- Confirmed (by reading `api/client.ts`) that `apiFetch`'s existing `formatDetail` already renders a plain-string 422 `detail` verbatim through `Error.message`, which the upload form's existing `error` badge already displays — no change to `api/client.ts` was needed, so it is not listed in `files_modified`.

## Deviations from Plan

None - plan executed exactly as written. Point 4 of Task 2 (HardwareLibDetail read-only display) was completed rather than skipped — the file had ample budget (249 lines before, 255 after, 5 lines net added for the `kind` pill + `declared_imports` line, both well under any size limit).

## Issues Encountered

`rg` under the project's `rtk` command-rewriting hook mishandled alternation patterns (`grep: Unmatched \{` / silently exiting 1 on plain `find`/`grep` with `-not`) during verification greps. Worked around with `rtk proxy grep -E ...` for regex alternation. Not a code issue, no production files affected.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness

- Plan 23-08 (FDA editor compute op picker) can now rely on `HardwareModule.lib_kind` being present in every API response typed against this file — the TS interface is already extended, nothing further needed from this plan.
- Manual click-through verification (filter chips render correctly, compute upload round-trips through the real backend, a rejected upload shows the backend's message verbatim) is deferred to plan 23-10's checkpoint, per this plan's own `<verification>` section.

---
*Phase: 23-compute-primitives-variables*
*Completed: 2026-08-03*

## Self-Check: PASSED

All 5 claimed files found on disk; both task commits (`3819908`, `7046c9e`) found in `git log --oneline --all`.
