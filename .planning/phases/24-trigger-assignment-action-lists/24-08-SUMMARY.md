---
phase: 24-trigger-assignment-action-lists
plan: 08
subsystem: api
tags: [fastapi, react, typescript, ast, fda-validation, hardware-introspection]

# Dependency graph
requires:
  - phase: 24-02
    provides: "api/fda_validation.py hard-422 gate, reject_if_hard_errors wired into POST/PUT /api/task-definitions"
  - phase: 24-03
    provides: "ActionEditor/ArgInput view action, output capture, allowTriggerContext arg mode"
  - phase: 24-05
    provides: "VariablesPanel + TriggerAssignmentPanel hosting the shared ActionEditor per trigger assignment"
provides:
  - "api/hw_introspect.py — AST class introspection (resolve_class_methods, class_capabilities, toolkit_hw_capabilities)"
  - "trigger_sources / detector_refs on every GET /api/toolkits* response"
  - "Hard 422 on a hardware/timer action with no method, in triggers and state entry_actions alike"
  - "{device_name} runtime token + source_ref accepted on view actions"
  - "trigger_name grouped dropdown in the UI, degrading to free text on an un-redeployed toolkit"
  - "Variables joining the condition operand pickers (flag/view option lists)"
  - "DetectorWriteWidget — constrained one-pick detector write UI macro"
affects: [24-07, 25-detector-derived-view-keys]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "AST base-class resolution reports closed=False whenever any ancestor is unresolvable in-file (imported base or a cycle) — callers only reject an unknown method when the set is provably closed"
    - "_validate_action gained method_only + context_label params instead of forking a second validator, so the trigger and state-body method rules can never drift apart"
    - "UI macro pattern: DetectorWriteWidget recognises the canonical action-list shape structurally (never JSON-string equality) and emits ordinary FDA JSON through the panel's existing update()/onVariablesChange funnel — no new action type, no second save path"

key-files:
  created:
    - api/hw_introspect.py
    - api/tests/test_hw_introspect.py
    - web_ui/react-src/src/components/DetectorWriteWidget.tsx
  modified:
    - api/routers/hardware_modules.py
    - api/routers/toolkits.py
    - api/fda_validation.py
    - api/tests/test_task_definitions_validation.py
    - web_ui/react-src/src/types/index.ts
    - web_ui/react-src/src/components/ConditionBuilder.tsx
    - web_ui/react-src/src/components/ConditionGroupsEditor.tsx
    - web_ui/react-src/src/components/TriggerAssignmentPanel.tsx
    - web_ui/react-src/src/pages/task-editor/TaskEditor.tsx

key-decisions:
  - "module_methods is dict[name -> (resolved method set, closed bool)], not the {name: [str]} shape sketched in the plan's toolkit_hw_capabilities docstring — the closed flag is load-bearing for _validate_action_method and has to travel with the set, not be inferred separately"
  - "trigger_sources/detector_refs wired at only the three READ call sites of _build_toolkit_row (list/by-name/get), per the plan's explicit scope; set-canonical/create/patch call sites keep the caps=None default (empty lists) to stay inside the 15-line toolkits.py growth budget — a client refetches via GET immediately after any of those anyway"
  - "validate_state_actions reuses _validate_action via a new method_only flag rather than forking a second function, generalising trigger_label to context_label so 'Trigger '...'' and 'State '...'' share one code path with zero vocabulary drift risk"
  - "FdaAction gained a source_ref field (not in this plan's file list) — required for the {device_name} token and the DetectorWriteWidget's structural match; a Rule 3 blocking-issue fix, not scope creep"
  - "DetectorWriteWidget exports buildDetectorWrite/detectorCaptureCollisions beyond the plan's two-export sketch (matchesDetectorWrite + default) so the '+ Read detector' entry button and the widget's own device-change handler share one canonical-shape/variable-declaration implementation instead of duplicating it"

requirements-completed: [TRIGA-14, TRIGA-15, TRIGA-16, TRIGA-17]

# Metrics
duration: 30min
completed: 2026-07-27
---

# Phase 24 Plan 08: Trigger-Source Dropdown, Method Validation, and the Constrained Detector Write Summary

**AST-derived `trigger_sources`/`detector_refs` on every toolkit read, a hard 422 on any hardware/timer action with no method (triggers and state bodies alike), and a one-pick detector-write UI macro that cannot cross-wire an electrode to the wrong tracker.**

## Performance

- **Duration:** ~30 min
- **Started:** 2026-07-27T16:12:00Z
- **Completed:** 2026-07-27T16:42:21Z
- **Tasks:** 4
- **Files modified:** 12 (3 created, 9 modified)

## Accomplishments
- New `api/hw_introspect.py` walks hardware-lib source with stdlib `ast` only, resolving in-file base classes for `is_trigger`/`direction`/`is_detector`/method sets, honestly reporting `closed=False` whenever any ancestor is unresolvable (the common case, since `Hardware` is always imported) or a cyclic base list is hit.
- `GET /api/toolkits*` now returns `trigger_sources` (grouped input/output, `Digital_Out`'s `is_trigger=True` wart reported truthfully per 24-CONTEXT.md R8) and `detector_refs`, derived live from each toolkit's registered hardware modules — verified against toolkit 100: `TOUCH_INT` (input) + `Left_LED`/`Mid_LED`/`Right_LED`/`Solenoid` (output); `detector_refs == ["MPR121"]`.
- `GET /api/hardware-modules/{id}/methods` now merges AST-inherited methods, so `Touch_Detector` offers `detect_change`/`read` instead of falling back to a free-text method box.
- A hardware/timer action with an empty, missing, whitespace-only, or non-string `method` is now a hard 422 naming the offending ref — in trigger actions AND state `entry_actions` alike, sharing one `_validate_action_method` implementation via a new `method_only` mode so the two paths can never drift apart. An unknown method is only rejected when the resolved AST method set is provably closed.
- The `view` action accepts a runtime `{device_name}` token when paired with a `source_ref` naming known hardware, erroring when `source_ref` is missing or points outside `known_hw` — the exception that lets the detector-write macro's `key_template` validate clean.
- `trigger_name` renders a grouped dropdown over `toolkit.trigger_sources`, degrading to the pre-existing free-text input when the list is empty and preserving an unknown stored value as a leading `(unknown)` option.
- Declared `variables` now join the condition operand pickers' flag/view option lists (one namespace with `toolkit.flags`, since both live in `self.flags` on the Pi).
- New `DetectorWriteWidget.tsx`: the researcher picks ONE device; the target key and written value both derive from that call's own `detect_change()` return, so reading electrode 2 and writing a different tracker is structurally impossible. It is a UI macro — the emitted JSON is the ordinary action vocabulary, matching `<canonical_payload>` field for field, with `pin_number`/`level` auto-declared into `variables` in the same update that writes the actions.

## Task Commits

Each task was committed atomically:

1. **Task 1: derive hardware capability from the lib AST** - `e5eeeeb` (feat)
2. **Task 2: hard-422 a method-less hardware action; accept the macro's JSON** - `11fbcc8` (feat)
3. **Task 3: trigger_name dropdown + variables in the operand pickers** - `9b25187` (feat)
4. **Task 4: the constrained one-pick detector write** - `2271105` (feat)

**Plan metadata:** (this commit)

## Files Created/Modified
- `api/hw_introspect.py` - New: `resolve_class_methods`, `class_capabilities`, `toolkit_hw_capabilities` — stdlib-`ast`-only, no FastAPI/DB imports, `db` passed in by the caller
- `api/tests/test_hw_introspect.py` - New: 9 tests against synthetic gpio/i2c/timer sources (inheritance, cyclic-base termination, unparseable-source safety)
- `api/routers/hardware_modules.py` - `get_hardware_module_methods` merges AST-inherited methods with the class's own
- `api/routers/toolkits.py` - `_build_toolkit_row` gains `caps` param exposing `trigger_sources`/`detector_refs`; wired at the 3 read call sites (net +12 lines, budget 15)
- `api/fda_validation.py` - `_validate_action_method` (shared TRIGA-16 rule), `validate_state_actions` (method_only mode), `{device_name}`/`source_ref` handling in the `view` branch, `reject_if_hard_errors` resolves `module_methods`/`trigger_sources` via `hw_introspect` and passes `trigger_sources` explicitly
- `api/tests/test_task_definitions_validation.py` - CANONICAL_PAYLOAD updated to the `{device_name}`/`source_ref` shape; 21 new tests
- `web_ui/react-src/src/types/index.ts` - `TriggerSource`, `ToolkitRead.trigger_sources`/`detector_refs`, `FdaAction.source_ref`
- `web_ui/react-src/src/components/ConditionBuilder.tsx` - `OperandEditor` gains `variableNames`, merged into flag/view option lists
- `web_ui/react-src/src/components/ConditionGroupsEditor.tsx` - forwards `variableNames` to every `ConditionRow`
- `web_ui/react-src/src/components/TriggerAssignmentPanel.tsx` - grouped `trigger_name` dropdown, required `variables`/`onVariablesChange` props, hosts `DetectorWriteWidget` above the actions expander with a raw-editor fallback always reachable
- `web_ui/react-src/src/pages/task-editor/TaskEditor.tsx` - threads `variableNames` into `ConditionGroupsEditor`; wires `variables`/`onVariablesChange` into `TriggerAssignmentPanel` (cumulative Task 3+4 diff: +5 lines, budget 35)
- `web_ui/react-src/src/components/DetectorWriteWidget.tsx` - New (129 lines, zero `any`): `matchesDetectorWrite`, `buildDetectorWrite`, `detectorCaptureCollisions`, default component

## Decisions Made
See `key-decisions` in frontmatter above.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 - Blocking issue] Added `source_ref` to the `FdaAction` type**
- **Found during:** Task 4
- **Issue:** `types/index.ts` wasn't in Task 4's file list, but `DetectorWriteWidget`'s structural match (`view.source_ref !== hw.ref`) and the emitted action (`source_ref: ref`) cannot type-check without the field existing on `FdaAction`. The backend already accepted `source_ref` (Task 2) since it validates untyped JSON.
- **Fix:** Added `source_ref?: string` to `FdaAction`, documented as the view action's runtime `{device_name}` source.
- **Files modified:** `web_ui/react-src/src/types/index.ts`
- **Commit:** `2271105` (Task 4 commit)

**2. [Rule 3 - Blocking issue] `module_methods` shape corrected from the plan's docstring sketch**
- **Found during:** Task 1
- **Issue:** Task 1's `toolkit_hw_capabilities` docstring sketches `module_methods: {name: [str]}`, but Task 2's `_validate_action_method` needs the `closed` flag per module to decide whether an unknown method is rejectable — a bare list of names loses that information.
- **Fix:** Implemented `module_methods` as `dict[str, tuple[set[str], bool]]` (methods, closed) throughout `hw_introspect.py` and `fda_validation.py`. Fully internal to the two Python modules; no API-response shape is affected.
- **Files modified:** `api/hw_introspect.py`, `api/fda_validation.py`
- **Commit:** `e5eeeeb`, `11fbcc8`

---

**Total deviations:** 2 auto-fixed (both Rule 3 — blocking issues discovered mid-implementation, corrected inline, no scope creep)
**Impact on plan:** Both are internal-shape corrections needed for the plan's own stated behavior (the `{device_name}` match, the closed-method-set rule) to actually work; neither changes the plan's external contract (API response shape, emitted FDA JSON, requirement scope).

## Issues Encountered

- `api/fda_validation.py` grew from 227 to 322 lines — above the project's 300-line soft standard, under the 500-line hard limit. The file is the designated single hard-422 enforcement point for the trigger/state-body vocabulary (24-02's explicit architectural decision); splitting it now would separate `_validate_action`/`_validate_action_method` from the state/trigger callers that share them. Left as-is; flagged for a future look if it grows further (e.g. when Phase 23's `compute` validation lands).
- The plan's own Task 2 negative-probe curl (`<verify>`) omits `toolkit_name`, which `TaskDefinitionCreate` requires — the probe as written returns 422 from Pydantic's own field validation, not from the hard-422 gate under test. Re-ran with `toolkit_name` added to confirm the *actual* validator fires and names `MPR121`; documented here so the distinction isn't lost.

## User Setup Required

None — no external service configuration required.

## Next Phase Readiness

- Live registry verification (toolkit 100, hardware module 7) matches the plan's stated expectations exactly; `docker compose up --build -d api`/`web_ui` both rebuilt and serving.
- **Blast-radius query re-run (2026-07-27), confirmed unchanged from the plan's recorded snapshot:** task definitions **181** (`source_less_toolkit FDA`, `Left_LED`), **185** (`GILI FDA`, `Right_LED` ×2 — **Gili's, not modified**), and **187** (`example_fens`, `Solenoid` + `Left_LED`) carry method-less hardware actions and can no longer be re-saved until the offending action is given a method or removed. No task definition was edited by this plan.
- `TaskEditor-<hash>.js` proof chain (chunk is code-split; `main.js`'s hash never changes and proves nothing): pre-existing `TaskEditor-CYLmUjzA.js` (plan 03) → `TaskEditor-oqJt2sgi.js` (Task 3) → `TaskEditor-Ch8o7POf.js` (Task 4, final) — confirmed present inside the rebuilt `mics_web_ui` container, not just asserted from the build log.
- No `api/tests/` fixture relied on a method-less hardware action being accepted anywhere in the pre-existing suite — all fixtures that used hardware/timer actions already carried a non-empty `method`. `CANONICAL_PAYLOAD`'s shape changed (added `source_ref`/`{device_name}`) but its `method` was already `detect_change`.
- Plan 07's rig proof (Checkpoint 1: UI round-trip; Checkpoint 3: touch each of 4 electrodes, confirm the matching `LICKER{n}` updates and no cross-talk) can now be exercised against this build — the dropdown, method gate, and detector widget are all live in the deployed `web_ui`/`api` images.

---
*Phase: 24-trigger-assignment-action-lists*
*Completed: 2026-07-27*

## Self-Check: PASSED

- FOUND: api/hw_introspect.py
- FOUND: api/tests/test_hw_introspect.py
- FOUND: web_ui/react-src/src/components/DetectorWriteWidget.tsx
- FOUND: .planning/phases/24-trigger-assignment-action-lists/24-08-SUMMARY.md
- FOUND commit e5eeeeb
- FOUND commit 11fbcc8
- FOUND commit 9b25187
- FOUND commit 2271105
