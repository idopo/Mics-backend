---
phase: 12-hardware-fda-builder
plan: "01"
subsystem: api, ui
tags: [toolkits, flags, typescript, normalization]

requires:
  - phase: 11-toolkit-redesign
    provides: backend-authored toolkit CRUD, EditModal, flags/params schema

provides:
  - _normalize_flags() in api/routers/toolkits.py — unified flags shape for all toolkit origins
  - ToolkitFlag TypeScript interface
  - ToolkitRead.flags typed as Record<string, ToolkitFlag>
  - TaskDefinitionFull.validation_status and validation_message fields

affects:
  - 12-hardware-fda-builder (steps 2-5 remaining)
  - 13-prerun-cross-check

tech-stack:
  added: []
  patterns:
    - "Normalize at read time: flags stored in two shapes, normalized to one in _build_toolkit_row"

key-files:
  created: []
  modified:
    - api/routers/toolkits.py
    - web_ui/react-src/src/types/index.ts
    - web_ui/react-src/src/pages/toolkits/EditModal.tsx

key-decisions:
  - "Normalize flags in _build_toolkit_row (read layer), not in DB migration — avoids touching 95 rows"
  - "ToolkitFlag interface added separately from FlagDefinition (write payload) to keep concerns separate"

patterns-established:
  - "_normalize_flags(): HANDSHAKE {type:{class_name}} and backend-authored {tracker_type} both normalize to {tracker_type, initial_value}"

requirements-completed: [HW-17, HW-18, HW-19, HW-20]

duration: 5min
completed: 2026-05-13
---

# Phase 12-01: Hardware-Aware FDA Builder (partial — steps 0–1 only)

**Flags normalization in GET /api/toolkits and typed ToolkitFlag/TaskDefinitionFull TypeScript interfaces**

> **PARTIAL SUMMARY** — Steps 2–5 (backward compat, StateBodyPanel action editor, broken-def warnings, UI design system) are NOT yet implemented. This summary exists so GSD skips steps 0–1 on next execution. The executor must start from Step 2.

## Performance

- **Duration:** ~5 min
- **Completed:** 2026-05-13
- **Tasks:** 2
- **Files modified:** 3

## Accomplishments
- `_normalize_flags()` added to `api/routers/toolkits.py` — all 95 toolkits now return flags as `{flag_name: {tracker_type, initial_value}}` regardless of origin
- `ToolkitFlag` interface added to `types/index.ts`; `ToolkitRead.flags` is now `Record<string, ToolkitFlag>` (was `Record<string, unknown> | null`)
- `TaskDefinitionFull` extended with `validation_status: "ok" | "broken"` and `validation_message: string | null`
- `EditModal.tsx` fixed: was unsafely casting flags values as `Record<string, unknown>`, now uses `ToolkitFlag` directly

## Task Commits

1. **Step 0: Normalize flags format** - `26bb2ce` (feat)
2. **Step 1: Update TypeScript types** - `1bfa77f` (feat)

## Files Created/Modified
- `api/routers/toolkits.py` — added `_normalize_flags()`, called in `_build_toolkit_row`
- `web_ui/react-src/src/types/index.ts` — `ToolkitFlag` interface, updated `ToolkitRead.flags`, extended `TaskDefinitionFull`
- `web_ui/react-src/src/pages/toolkits/EditModal.tsx` — fixed flags rendering to use `ToolkitFlag` directly

## Decisions Made
Normalization in read layer (`_build_toolkit_row`) rather than a DB migration — no data mutation needed, works transparently across all 95 existing toolkits.

## Deviations from Plan
None — steps 0 and 1 executed exactly as specified.

## Issues Encountered
None.

## Next Phase Readiness
Steps 2–5 of this plan remain:
- Step 2: Backward compat (legacy vs backend-authored toolkit path in ActionEditor)
- Step 3: Full action editor in StateBodyPanel (5 action types)
- Step 4: Broken definition warnings in UI
- Step 5: UI Design System (colors, tooltips, ArgInput)

**Executor instruction for continuation:** Start at Step 2 in 12-01-PLAN.md. Steps 0 and 1 are complete and committed.

---
*Phase: 12-hardware-fda-builder*
*Completed: 2026-05-13 (partial)*
