---
phase: 18-extlink-pi-transport
plan: 14
subsystem: ui
tags: [react, typescript, fda-editor, extlink, condition-builder, arg-input]

# Dependency graph
requires:
  - phase: 18-13
    provides: "extlink_signals JSON shape on ToolkitRead: {module_name, source_ids, signals,
      keys, conflict, by_pilot}, always [] never null/absent"
provides:
  - "buildViewOptions(hwNames, flagNames, detectors, extlink=[]) — 4th parameter, one option
    group per external module appended after detector groups, item value is the resolved
    <source_id>.<signal> key (or <source_id>.alive), title notes pilot-specific"
  - "ConditionBuilder.tsx and ArgInput.tsx both read toolkit.extlink_signals into the same
    picker — an ExternalHardware signal is now authorable as a condition operand or an action
    argument entirely through the FDA editor UI"
affects: [18-12]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "extlink groups reuse the existing dedupeItems/ViewOptionGroup.warning machinery — no
      parallel mechanism; group order (Hardware -> Flags -> detectors -> extlink) IS dedupe
      precedence, extlink last so it never displaces a same-named hardware/flag entry"
    - "extlink item value IS the stored key (a plain string), unlike a detector channel's opaque
      @detector/... token — the resolved-key decision from 18-14-PLAN.md's design_decision,
      because the key is the literal Tracker name the Pi registers, not a per-pilot prediction"

key-files:
  created: []
  modified:
    - web_ui/react-src/src/types/index.ts
    - web_ui/react-src/src/components/detectorOptions.mts
    - web_ui/react-src/tests/detectorOptions.test.mts
    - web_ui/react-src/src/components/ConditionBuilder.tsx
    - web_ui/react-src/src/components/ArgInput.tsx

key-decisions:
  - "Operand shape is a resolved key ({\"view\": \"<source_id>.<signal>\"}), not a ref — the
    plan's design_decision, restated here because it is load-bearing for this plan's tests: a
    ref shape would need a new Pi-side resolver branch in _build_transition_lambda AND
    _resolve_arg, which EXTLINK-05 forbids and no Phase 18 plan touches"
  - "Extlink group label is \"<source_id> signals\" when exactly one source_id is configured,
    falling back to \"<module_name> signals\" when pilots disagree on source_id (conflict case) —
    a single canonical source_id reads better than the module's internal name"
  - "The <source_id>.alive item is labelled \"alive (device online)\", deliberately NOT
    containing the word \"signal\", so it reads as device health rather than a data signal —
    the EXTLINK-18 control-only case renders as exactly one item per module"

requirements-completed: [EXTLINK-19]

# Metrics
duration: ~20min
completed: 2026-08-09
---

# Phase 18 Plan 14: FDA-editor extlink operands Summary

**`buildViewOptions` gains a 4th `extlink` parameter so an `ExternalHardware` signal (or its `<source_id>.alive` liveness key) is now pickable in both the condition builder and the action-argument input — closing the UI half of EXTLINK-19 that 18-13 opened on the backend.**

## Performance

- **Duration:** ~20 min
- **Tasks:** 2 (TDD Task 1 + Task 2)
- **Files modified:** 5

## Accomplishments
- `ExtlinkSignalGroup` + `ToolkitRead.extlink_signals?` added to `types/index.ts`, matching 18-13's pinned JSON shape field for field (`module_name`, `source_ids`, `signals: {name, dtype}[]`, `keys`, `conflict`, `by_pilot`).
- `buildViewOptions`'s new optional 4th parameter (`extlink: ExtlinkSignalGroup[] = []`) builds one option group per external module, appended after detector groups, reusing the existing `dedupeItems`/`ViewOptionGroup.warning` machinery rather than inventing a parallel one.
- 11 new `node --test` cases added to `detectorOptions.test.mts` (the omitted-4th-arg regression pin, group labelling with the single-vs-multi source_id fallback, the resolved-key item shape, the control-only single-`.alive`-item case, the cross-pilot conflict warning, dedupe precedence, `isKnownViewOption`, and the operand round trip) — suite went from the 182-test baseline to **193/193 passing**.
- Both consumers wired: `ConditionBuilder.tsx:50` and `ArgInput.tsx:36` now pass `toolkit?.extlink_signals ?? []` as the 4th argument, reading it off the `toolkit` prop both already receive — no new prop, `TaskEditor.tsx` untouched (still 806 lines).
- The DVK-05 keep-current-value escape in `ConditionBuilder.tsx` (`:76-80`) preserved verbatim; its comment extended to note that an ExternalHardware signal is now offered directly and no longer needs the escape, while the other three round-trip cases (Python-only tracker, hand-authored definition, a key from an unassigned lib version) still do.
- `web_ui` container rebuilt (`docker compose up --build -d web_ui`); `main.js` mtime fresh, `/` and `/react/` both return 200 — a servable bundle is ready for plan 18-12's checkpoint.

## Task Commits

Each task was committed atomically:

1. **Task 1: `ExtlinkSignalGroup` type + `buildViewOptions`'s fourth parameter** - `028b6d5` (feat, TDD RED/GREEN in one commit — no separate test-only commit was needed since the RED run was verified in-session before implementing)
2. **Task 2: Wire both consumers — condition operands and action arguments** - `3a41458` (feat)

## Files Created/Modified
- `web_ui/react-src/src/types/index.ts` — `ExtlinkSignalGroup`, `ExtlinkSignalPilot`, `ToolkitRead.extlink_signals?`.
- `web_ui/react-src/src/components/detectorOptions.mts` (189 → 235 lines) — `buildExtlinkConflictWarning`, `extlinkSignalName`, `buildExtlinkItem`, the extlink group loop in `buildViewOptions`, an S7 doc comment explaining the resolved-key decision in the file's existing S1/S2 register.
- `web_ui/react-src/tests/detectorOptions.test.mts` — `extlink(overrides)` factory + 11 new cases.
- `web_ui/react-src/src/components/ConditionBuilder.tsx` — 4th `buildViewOptions` argument, DVK-05 escape comment extended.
- `web_ui/react-src/src/components/ArgInput.tsx` — 4th `buildViewOptions` argument, comment extended to explain why extlink keys (unlike detector channels) belong in this picker.

## Decisions Made
- Kept the resolved-key operand shape exactly as the plan's `design_decision` mandates — no ref shape, no new Pi-side resolver, no new call sites in `_build_transition_lambda`/`_resolve_arg`. This was pinned by tests, not just prose: `optionValueToViewOperand`/`viewOperandToOptionValue` are unmodified and the round-trip test asserts they still return `{view: "<key>"}` unchanged.
- `<source_id>.alive`'s label ("alive (device online)") deliberately omits the word "signal" so a researcher reads it as device health, not as one of the module's data channels — verified by a dedicated test (`!alive.label.toLowerCase().includes('signal')`).
- Confirmed by inspection (plan's own instruction) the second-order effect on `ArgInput.tsx`'s `viewKeys[0]` seed for `switchMode('view')`: group order puts Hardware first, so the seed is unchanged for any toolkit that has hardware; for a toolkit whose only view options are extlink signals, the seed becomes the first extlink key, which is correct and requires no separate handling.

## Deviations from Plan

None — plan executed exactly as written. Task 1 was TDD as specified: the 11 new test cases were run first and confirmed RED (8 of 11 failing on the pre-implementation code, `193` total tests reported with `8 fail`/`185 pass`), then `buildViewOptions` was extended and the same run went GREEN (`193 pass`, `0 fail`) before committing. Both tasks landed in a single commit each (test+implementation together for Task 1, since the plan's own TDD guidance for this codebase pairs RED and GREEN into one atomic per-task commit when both are verified in the same session — no separate `test(...)` commit was created, consistent with how this repository's prior TDD-tagged tasks in this phase are committed).

### Auto-fixed Issues
None — no bugs, missing functionality, or blocking issues were found.

## Issues Encountered
- `docker compose up --build -d web_ui` also rebuilt and recreated the `api` and `orchestrator` containers (visible in the compose output as `Built`/`Recreated` for all three services), not just `web_ui`. This is default `docker compose` behavior for this project's compose file and was not something this plan's task text anticipated needing to call out; verified afterward that `api`'s `/health` still returns 200 and no plan-18-14-owned files touch either of those services, so no functional impact. Flagged here in case a concurrently-executing plan (18-11 or 18-15) observes an unexpected container restart around this timestamp (2026-08-09T08:22Z) — same category of transient disruption 18-09's SUMMARY already documented for a different rebuild.
- The plan's own `<critical_rules>` verification text says `grep -c "isKnownViewOption" ConditionBuilder.tsx` must stay 1; the literal grep (matching both the import line and the call site) reports 2, unchanged from before this plan's edits — pre-existing, not introduced here. `grep -c "isKnownViewOption("` (call sites only) is 1, which is the property the plan text is actually protecting (exactly one DVK-05 escape usage, no duplication). Confirmed no new call site was added.

## User Setup Required
None - no external service configuration required.

## Next Phase Readiness
- Plan 18-12's consolidated rig checkpoint can now exercise ROADMAP success criterion 1 (author a transition gated on an ExternalHardware signal entirely through the FDA editor) — end-to-end browser authoring is that checkpoint's job, not asserted here, per this plan's own `<verification>` block.
- The exact option `label`/`value`/`title` strings a researcher will see: a regular signal item is labelled `"<signal_name> (<dtype>)"` (e.g. `"left_paw_x (float)"`) with value `"<source_id>.<signal_name>"` (e.g. `"dlc_cam1.left_paw_x"`); the liveness item is labelled `"alive (device online)"` with value `"<source_id>.alive"`; every item's `title` states the key is pilot-specific.
- Additive migration path to a ref shape (if a future phase wants one): a new operand kind (e.g. `{"view_extlink": {...}}`), a Pi-side resolver in `_build_transition_lambda`/`_resolve_arg`, and a `scan_fda_view_keys` branch — nothing in this plan's code blocks that; the current resolved-key shape and the ref shape are not mutually exclusive at the JSON level.

---
*Phase: 18-extlink-pi-transport*
*Completed: 2026-08-09*

## Self-Check: PASSED

- FOUND: .planning/phases/18-extlink-pi-transport/18-14-SUMMARY.md
- FOUND: web_ui/react-src/src/components/detectorOptions.mts
- FOUND: web_ui/react-src/src/types/index.ts
- FOUND: web_ui/react-src/tests/detectorOptions.test.mts
- FOUND: web_ui/react-src/src/components/ConditionBuilder.tsx
- FOUND: web_ui/react-src/src/components/ArgInput.tsx
- FOUND: 028b6d5 (task 1 commit)
- FOUND: 3a41458 (task 2 commit)
