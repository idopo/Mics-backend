---
phase: 23-compute-primitives-variables
verified: 2026-08-05T12:49:06Z
status: passed
score: 7/7 phase-level success criteria verified (2 carry documented, accepted caveats)
re_verification:
  previous_status: passed
  previous_score: 6/6
  gaps_closed: []
  gaps_remaining: []
  regressions: []
  note: >
    Extension pass, not a re-verification of a failed report. The prior VERIFICATION.md (2026-08-03)
    covered plans 23-01 through 23-10 and scored passed. Plans 23-11 and 23-12 (the operand-namespace
    consistency pass, CMP-20-25) are new since that pass and are verified here for the first time;
    all of plans 01-10's prior findings are carried forward unchanged below.
known_open_items_not_gaps:
  - "Gonogo task itself never built — an equivalent compute-gated FDA (random_float draw gating a transition) was validated in its place; the mechanism is proven, gonogo is not"
  - "CMP-16 partial — Hardware_Event logs op + result but not positional args (event_data.update(kwargs) only); scientifically material for non-invertible ops"
  - "CMP-18 — researcher-authored compute lib upload has unit coverage (test_hardware_lib_kind.py) but was never exercised end-to-end on the rig"
  - "hot_update_fda variable-collision predicted by code inspection (plan 23-04), never triggered in any run"
  - "Pi-side unit tests (test_compute_ops.py, test_fda_vocabulary.py) never run on the Pi itself (autopilot unimportable on dev host); all Pi evidence is from live runs"
  - "CMP-24b — deployed and live on the Pi, but no run has yet passed a {\"view\": <hardware>} operand as an ARGUMENT (task 186 uses view only in transition conditions, which resolve through _build_condition_operand and never reach _resolve_arg). Deployed-but-unexercised by explicit, documented decision — not a gap."
  - "CMP-25 — backend deployed and unit-tested, but the only rig-available task definition (186) is backend-authored with semantic_hardware=null, so the 422 path CMP-25 fixes was never live on that run. Deployed-but-unexercised by explicit, documented decision — not a gap."
  - "CMP-24a (mirror auto-created trial_counter into self.view.view) and CMP-24c (accept type:\"view\" in a state body) were built with passing tests, then reverted before Pi deployment by explicit user decision on 2026-08-05 — narrower than the original three-edit CMP-24 text. Both captured in deferred-items.md and as pending GSD todos. Not gaps against the current (narrowed) REQUIREMENTS.md spec."
human_verification:
  - test: "Upload a researcher-authored compute lib through the Hardware Libraries page GUI, promote it to stable, link it to a toolkit, and confirm its ops appear in the GUI op picker with no platform code change"
    expected: "New ops appear in ComputeActionFields' grouped picker without any code deploy; the lib round-trips through LOAD_HARDWARE_LIBS to a real Pi"
    why_human: "Documented as NOT exercised on hardware in 23-HARDWARE-VALIDATION.md Section 3 — unit-tested only"
  - test: "Build and run the actual gonogo task (not the equivalent test FDA) end to end on the rig"
    expected: "Same mechanism proven by the validated FDA (compute draw -> variable -> guarded transitions) holds for the real gonogo logic"
    why_human: "Explicitly documented as not built in 23-HARDWARE-VALIDATION.md Section 3; requires rig access and is a content/authoring task, not a code gap"
  - test: "On a semantic (non-backend-authored) toolkit, pass a {\"view\": <hardware>} operand as an action ARGUMENT (not a condition) and run it on the rig"
    expected: "The value resolves via get_state() instead of AttributeError-ing — exercises CMP-24b's actual deployed code path, which no run has hit yet"
    why_human: "Requires rig access and a semantic toolkit; 23-HARDWARE-VALIDATION.md's Plan 23-12 sign-off explicitly records this as deployed-but-unexercised"
  - test: "On a semantic (non-backend-authored) toolkit, build a transition condition reading a semantic-hardware name via view, save, and confirm 200 (not 422)"
    expected: "Saves cleanly — exercises CMP-25's deployed backend fix, which task 186 (backend-authored, semantic_hardware=null) could not exercise"
    why_human: "Requires a semantic toolkit on the rig; recorded as deployed-but-unexercised in 23-HARDWARE-VALIDATION.md"
---

# Phase 23: Compute Operations (Compute Libs) Verification Report

**Phase Goal:** A researcher can compute a value inside a state, store it in a variable, and
transition on it — without a developer editing locked toolkit source, and with every
computation recorded in the event log. Compute operations are delivered as user-extensible,
versioned, auto-logged libraries using the existing hardware-lib substrate. Extended by plans
23-11/23-12 to make the FDA editor's read-namespace consistent (`view` reads everywhere;
`flag`/`hardware` retired to a same-shape legacy escape) so a researcher never encounters a
picker that offers an operand spelling that saves cleanly and raises on the rig.

**Verified:** 2026-08-05T12:49:06Z
**Status:** passed
**Re-verification:** Extension — plans 23-01 through 23-10 previously verified passed
(2026-08-03); this pass adds plans 23-11 and 23-12 (CMP-20–25) and carries all prior findings
forward unchanged.

## Goal Achievement

### Observable Truths (Phase-level Success Criteria, ROADMAP.md)

| # | Truth | Status | Evidence |
|---|---|---|---|
| 1 | Pi runtime: `variables` + `compute` action load/run, both guarded branches fire across trials, recomputed once per entry, last-write-wins, hot-reload re-creates variables before rebuilding transitions | ✓ VERIFIED | `mics_task.py:714-735` compute branch; `fda_vocabulary.py` + `validate_fda.py` compute branches; proven live on rig runs 543-547 (41 draws, 0 routing violations, 4-deep retry chain resolved); `hot_update_fda` (mics_task.py:1428) rebuilds `self.stages` from a re-run `load_fda_from_json` |
| 2 | Logging (CMP-16): both a `Hardware_Event` (op+args) and a `Tracker` set (result) reach the event log per compute call | ⚠️ VERIFIED — documented partial | Both events proven reaching ES for numeric AND non-numeric outputs (run 550, 10/10/10 pairs, 0 rejected docs) via `coerce_for_event`/`coerce_result` (`log_value.py`) wired into `logging_utils.py`. **Known, pre-documented gap** (not a new finding): `log_action`'s Hardware branch only does `event_data.update(kwargs)` — positional args (the actual op parameters, since compute calls pass positionally) are never recorded. Both events survive; the op's *inputs* are not recoverable from ES. |
| 3 | Extensibility: a lib created in the hardware-lib editor is versioned, promoted, linked to a toolkit, shipped via `LOAD_HARDWARE_LIBS`, and its ops appear in the GUI picker with no platform code change | ✓ VERIFIED (mechanism); researcher-authored round trip not hardware-exercised (documented, not a gap) | `hardware_libs.py` upload/promote/link endpoints unchanged in shape, `kind='compute'` distinguishes rows; `ComputeActionFields.tsx` reads AST metadata via `isComputeModule` grouping — same picker path as hardware libs. Seed lib (`Compute Ops`, 13 ops) proven end-to-end on rig (run 535, 5 libs dispatched, all `HARDWARE_LIB_TEST_RESULT ok=True`). Uploading a *different*, researcher-authored lib was not itself run on the rig — has unit coverage only (`test_hardware_lib_kind.py`). |
| 4 | Backend: 422 on undeclared `output`/collision/undeclared-variable-ref; `fda_utils` scanner returns compute outputs; `kind` distinguishes libs; version resolution corrected (pin → toolkit default → stable → preflight issue) for both lib kinds | ✓ VERIFIED | `api/fda_validation.py::validate_compute_variables`/`_validate_action` (compute branch); `api/fda_utils.py:42` includes `"compute"` in ref-scanned action types; `api/lib_version_resolution.py::resolve_lib_version_id` is the single chain, consumed by `toolkit_dispatch.py` (dispatch), `hw_introspect.py` (introspection), and the orchestrator (via `GET .../hardware-libs` `resolved_*` fields) — proven unified rather than 3 divergent derivations. Full backend suite green (352 passed, 1 skipped, re-run 2026-08-05). |
| 5 | GUI uncluttered: Hardware Libraries page gains one `kind` filter chip; StateBodyPanel gains exactly one "Compute" action-type entry rendering one compact row; typing a new `output` auto-declares into `variables`, immediately selectable in ConditionBuilder; save round-trips | ✓ VERIFIED | `HardwareLibs.tsx` `kindFilter` state + `kind` select; `ActionEditor.tsx` action-type `<select>` has exactly one `compute` `<option>` (gated off in trigger context via `allowTriggerContext`); `ComputeActionFields.tsx` renders the compact row; `onDeclareVariable` threaded `ComputeActionFields → ActionEditor → StateBodyPanel → TaskEditor.declareVariable`. `tsc --noEmit` clean (re-run 2026-08-05), `npm run test:unit` 84/84 pass (re-run 2026-08-05, up from 53 pre-23-11). |
| 6 | Discoverability (CMP-15): `variable_never_written` preflight issue surfaces through Phase 25's existing renderer; read-only variables inspector shows writers/readers | ✓ VERIFIED | `api/variable_scan.py::variable_never_written_issues` wired into `toolkit_dispatch.py::preflight_validate`; rendered via `HardwareCheckModal.tsx`'s `ComputeIssueDetail` and excluded from the destructive PUT loop via `NON_CONFIG_ISSUES` set; `VariableUsagePanel.tsx` wired into `VariablesPanel.tsx` wired into `TaskEditor.tsx`; backend route `api/routers/task_def_inspect.py`. |
| 7 | One read namespace (CMP-20–25): every operand picker that reads a value (transition condition, `if`/`else` condition, action argument) offers `view`/`literal`/`param` on a fresh operand; `flag`/`hardware` survive only as a same-shape legacy escape that round-trips unchanged; declared variables are selectable inside `if` conditions, as action arguments, and as a flag write ref (resolving to the `Tracker` method set, never `Counter_Tracker`); the phantom `decrement`/`reset` tracker methods are gone; the Pi and backend counterexamples that made the rule false at run time are closed for the case CMP-23 actually emits | ✓ VERIFIED (mechanism, on rig); two deployed fixes not yet rig-exercised (documented, not a gap) | `operandTypes.mts`/`argModes.mts`/`trackerMethods.mts` (21+ new `node --test` cases, all green); `ConditionBuilder.tsx`'s `visibleOperandTypes`; `IfActionEditor.tsx`'s newly-wired `hwModuleNames`/`variableNames`; `ActionEditor.tsx`'s `regularFlagKeys` unioning `variableNames` through `trackerTypeForRef`; `ArgInput.tsx`'s `~ View` mode. Backend: `fda_validation.py:245` unions `semantic_hw` at the condition-operand call site only (write path unaffected — regression-guarded by `test_semantic_hardware_is_still_not_a_valid_flag_action_ref`). Pi: `_resolve_arg` (`mics_task.py:520`) reads `get_state()` (CMP-24b, confirmed deployed by direct read of the pi-mirror source). **Rig-proven (run 551):** CMP-20's `view` read (7/7 draws routed correctly), CMP-20's legacy escape surviving a byte-identical resave, CMP-21/22/23 editor-verified. **Deployed but not rig-exercised, documented explicitly in 23-HARDWARE-VALIDATION.md:** CMP-24b (no run has passed `{"view": hardware}` as an argument) and CMP-25 (the only available task definition's toolkit is backend-authored with `semantic_hardware=null`, so the 422-fix path was never live). CMP-24a/24c were built, tested green, then reverted before deployment by explicit user decision — narrower scope, not a gap against the current REQUIREMENTS.md text. |

**Score:** 7/7 truths verified (truth 2 carries a pre-documented partial caveat; truth 3 carries a pre-documented untested-path caveat; truth 7 carries two pre-documented deployed-but-unexercised caveats — all explicitly out of scope for this report as gaps, per the hardware validation log and this phase's own accepted judgement).

### Required Artifacts

| Artifact | Expected | Status | Details |
|---|---|---|---|
| `api/tests/test_hardware_lib_kind.py` | CMP-12/19 contract test | ✓ VERIFIED | Exists, passes in suite |
| `api/tests/test_toolkit_dispatch.py` | CMP-17 contract test | ✓ VERIFIED | Exists, passes in suite |
| `/home/ido/pi-mirror/tests/test_compute_ops.py` | Pi compute dispatch contract (USER-RUN) | ✓ VERIFIED (exists; not agent-runnable) | Exists; `autopilot` unimportable on dev host — documented, not a gap |
| `api/seed_libs/compute_ops.py` | Seed compute lib, `Hardware` subclass, `release()`, 13 ops | ✓ VERIFIED | `release()` present; 13 `@log_action` methods matching CMP-04's exact op list |
| `api/seed_compute.py` | Idempotent seeding | ✓ VERIFIED | `seed_compute_ops_lib`, `COMPUTE_STDLIB_ALLOWLIST` both present |
| `api/compute_provisioning.py` | Auto-provisioning of pilot config rows | ✓ VERIFIED | `provision_compute_configs`, `compute_module_names` present; wired into `hardware_modules.py` POST and `toolkit_dispatch.py` preflight self-heal |
| `api/db.py::run_hardware_lib_kind_migration` | Idempotent `kind` column migration | ✓ VERIFIED | `ADD COLUMN IF NOT EXISTS` present, called at startup |
| `api/fda_validation.py` | Compute validation branch + CMP-25 semantic-hw union | ✓ VERIFIED | `validate_compute_variables`, compute in `VALID_ACTION_TYPES`, compute branch in `_validate_action`; `semantic_hw = set((getattr(toolkit, "semantic_hardware", None) or {}).keys())` at line 235, unioned into `valid_names` at line 252; file is 449 lines (budget ≤460); `_valid_flag_names` untouched |
| `api/variable_scan.py` | Writer/reader analysis | ✓ VERIFIED | `scan_variable_writers`, `scan_variable_readers`, `variable_never_written_issues` all present and wired |
| `api/fda_utils.py` | Ref scanner covers compute outputs | ✓ VERIFIED | `"compute"` in scanned action types |
| `api/lib_version_resolution.py` | Single resolution chain | ✓ VERIFIED | `resolve_lib_version_id`, `resolve_lib_versions`, `RESOLUTION_REASONS`; consumed by 3 sites |
| `web_ui/react-src/src/pages/hardware-libs/HardwareLibs.tsx` | kind filter chips + upload form | ✓ VERIFIED | `kind`/`kindFilter` state, upload form with declared imports |
| `web_ui/react-src/src/types/index.ts` | `HardwareLib.kind`, `declared_imports`, `lib_kind` | ✓ VERIFIED | `lib_kind` present |
| `api/routers/task_def_inspect.py` | Variable-usage route | ✓ VERIFIED | `router` exported, GET endpoint present |
| `web_ui/react-src/src/components/ComputeActionFields.tsx` | Compute row UI | ✓ VERIFIED | `isComputeModule` filter, grouped op picker, `onDeclareVariable` |
| `web_ui/react-src/src/components/VariableUsagePanel.tsx` | Read-only inspector | ✓ VERIFIED | Wired via `VariablesPanel.tsx` into `TaskEditor.tsx` |
| `.planning/phases/23-compute-primitives-variables/23-HARDWARE-VALIDATION.md` | Hardware proof record | ✓ VERIFIED | Documents proven/not-proven/deployed state with ES/orchestrator evidence, incl. the Plan 23-12 sign-off section (run 551) |
| `web_ui/react-src/src/components/operandTypes.mts` | Pure operand type/key/build logic + `visibleOperandTypes` legacy-escape rule | ✓ VERIFIED | 81 lines; `OperandType`, `getOperandType`, `getOperandKey`, `buildOperand`, `operandLabel`, `visibleOperandTypes`, `LEGACY_OPERAND_TYPES`, `resolveDetectorDisplayName` all present and exported |
| `web_ui/react-src/src/components/argModes.mts` | Pure `ArgInput` mode logic + `visibleArgModes` legacy-escape rule | ✓ VERIFIED | 74 lines; `ArgMode` (incl. `view`), `visibleArgModes`, `getParamKeys`, `annotationToInputKind`, `MODE_COLORS`/`MODE_LABELS`/`MODE_TOOLTIPS` all present |
| `web_ui/react-src/src/components/trackerMethods.mts` | Tracker method tables + `trackerTypeForRef` | ✓ VERIFIED | 51 lines; `TRACKER_METHODS.Counter_Tracker` has only `increment`/`set` (confirmed by grep — no `decrement`/`reset` anywhere in the file); `trackerTypeForRef` present |
| `web_ui/react-src/src/components/FlagActionFields.tsx` | Trial + flag write-action branches extracted from `ActionEditor` | ✓ VERIFIED | 143 lines (budget ≤200) |
| `web_ui/react-src/tests/operandTypes.test.mts` | `node --test` contract for the legacy-operand escape | ✓ VERIFIED | Present, all cases pass |
| `web_ui/react-src/tests/argModes.test.mts` | `node --test` contract for view mode + legacy flag escape | ✓ VERIFIED | Present, all cases pass |
| `web_ui/react-src/tests/trackerMethods.test.mts` | `node --test` contract for tracker-type resolution and absent decrement/reset | ✓ VERIFIED | Present, all cases pass |

### Key Link Verification

| From | To | Via | Status | Details |
|---|---|---|---|---|
| `mics_task.py::_build_action_callable` compute branch | `self._capture_output` / `self.flags[name].set` | same call-and-capture pattern as hardware branch | ✓ WIRED | Byte-for-byte parallel to hardware branch |
| compute op method | `Event_Dispatcher` | `@log_action` on `Hardware` subclass | ✓ WIRED | Proven on rig — `Modules {"id":"COMPUTE",...}` per call, runs 541+ |
| `api/fda_validation.py::collect_hard_errors` | `validate_compute_variables` | one more term in the existing sum | ✓ WIRED | Confirmed present |
| `api/routers/toolkits.py` | `reject_if_hard_errors` | POST/PUT save-time gate | ✓ WIRED | Confirmed present |
| `api/main.py` startup | `run_hardware_lib_kind_migration` + `seed_compute_ops_lib` | startup call | ✓ WIRED | Confirmed present at startup |
| `api/routers/toolkit_dispatch.py::get_dispatch_spec` | `resolve_lib_version_id` | replaces inline pin→active chain | ✓ WIRED | Confirmed present |
| `api/hw_introspect.py::toolkit_hw_capabilities` | `resolve_lib_versions` | third divergent site unified | ✓ WIRED | Confirmed present |
| `orchestrator_station.py::_send_hardware_libs_if_needed` | `GET /toolkits/{id}/hardware-libs` `resolved_*` fields | orchestrator reads backend's answer instead of re-deriving | ✓ WIRED | Proven on rig run 535 |
| `api/routers/toolkit_dispatch.py::preflight_validate` | `variable_scan.py::variable_never_written_issues` | step in preflight | ✓ WIRED | Confirmed present |
| `api/routers/toolkit_dispatch.py::preflight_validate` | `compute_provisioning.py::provision_compute_configs` | self-heal before per-module loop | ✓ WIRED | Confirmed present |
| `ComputeActionFields.tsx` | `HardwareModule.lib_kind === 'compute'` | `isComputeModule` predicate | ✓ WIRED | Exported from `ActionEditor.tsx`, used in `ComputeActionFields.tsx` |
| `ComputeActionFields.tsx` output combobox | `TaskEditor.fdaJson.variables` | `onDeclareVariable` callback | ✓ WIRED | Threaded through the chain |
| `HardwareCheckModal.tsx::handleStart` + `pendingEdits` init | `view_key_unresolved` skip pattern | `variable_never_written`/`lib_version_unresolved` join `NON_CONFIG_ISSUES` | ✓ WIRED | Confirmed present |
| `VariableUsagePanel.tsx` | `GET /api/task-definitions/{id}/variable-usage` | react-query | ✓ WIRED | Confirmed via `task_def_inspect.py` router |
| orchestrator `LOAD_HARDWARE_LIBS` | Pi `HARDWARE_OVERRIDE_DIR/compute_ops.py` | resolved stable version's source, `test_import=True` | ✓ WIRED | Proven on rig run 535, 5/5 `HARDWARE_LIB_TEST_RESULT ok=True` |
| compute op call | Elasticsearch `event_log_v2` | `@log_action` Hardware_Event AND Tracker.set, both per call | ✓ WIRED (with documented CMP-16 args caveat) | Proven run 550, 10/10/10 pairs, 0 rejected docs |
| `IfActionEditor.tsx` | `ConditionBuilder` | `hwModuleNames={hwModules.map(m => m.name)}` + `variableNames={variableNames}` props | ✓ WIRED | Confirmed at `IfActionEditor.tsx:85-86`; grep for `hwModuleNames` returns the new line |
| `ConditionBuilder.tsx`'s `OperandEditor` type `<select>` | `operandTypes.mts::visibleOperandTypes` | option list computed from the stored operand's type | ✓ WIRED | Confirmed; `flag`/`hardware` render branches (`type === 'flag'`/`'hardware'`) still present, untouched |
| `ArgInput.tsx` `~ View` mode | `detectorOptions.mts::buildViewOptions` | grouped `<select>`, called with an empty detectors array | ✓ WIRED | Confirmed present; `switchMode`'s re-click no-op guard (`if (next === mode) return`) confirmed present |
| `ActionEditor.tsx`'s `regularFlagKeys` | `trackerMethods.mts::trackerTypeForRef` | variable ref resolves to the `Tracker` method set, never `?? 'Counter_Tracker'` | ✓ WIRED | Confirmed: all three former `?? 'Counter_Tracker'` sites replaced |
| `api/fda_validation.py::validate_compute_variables` | `toolkit.semantic_hardware` | union into `valid_names` at the condition-operand call site only, line 252 | ✓ WIRED | Confirmed by direct read; regression-guarded by `test_semantic_hardware_is_still_not_a_valid_flag_action_ref` (passes) |
| `mics_task.py::_resolve_arg` | `Tracker.get_state()` / `Hardware.get_state()` | view branch calling `get_state()` instead of `.value` | ✓ WIRED | Confirmed at `mics_task.py:518-520`; deployed to the Pi per `23-HARDWARE-VALIDATION.md`'s Plan 23-12 sign-off, but not yet exercised as an argument on any run (documented) |

### Requirements Coverage

| Requirement | Description (abridged) | Status | Evidence |
|---|---|---|---|
| CMP-01 | `variables` registry (built in 24, verify only) | ✓ SATISFIED | `load_fda_from_json` confirmed present; regression tests in `test_compute_ops.py` Task 3 |
| CMP-02 | Variable = Tracker in `self.flags` + `self.view.view` | ✓ SATISFIED | Same as CMP-01; unchanged since Phase 24 |
| CMP-03 | `type:"compute"` entry action, thin alias over hardware call-and-capture | ✓ SATISFIED | `mics_task.py:714-735`, proven on rig |
| CMP-04 | Compute lib = `Hardware` subclass, seed content (13 stdlib ops) | ✓ SATISFIED | `compute_ops.py` exact match |
| CMP-05 | Last-write-wins on re-entry | ✓ SATISFIED | Proven on rig runs 543-547 (redraw on re-entry) |
| CMP-06 | Hot-reload recreates variables before rebuilding transitions | ✓ SATISFIED | `hot_update_fda` re-runs load path; not separately rig-proven this phase but mechanism unchanged from Phase 2/24 |
| CMP-10 | Hard 422s: undeclared output, collisions, undeclared var refs | ✓ SATISFIED | `fda_validation.py`, tests pass |
| CMP-11 | `fda_utils.py` scanner covers compute outputs | ✓ SATISFIED | Confirmed present |
| CMP-12 | `kind` column, idempotent migration | ✓ SATISFIED | `run_hardware_lib_kind_migration`, DB confirmed `kind='compute'` row |
| CMP-13 | Exactly one "Compute" action-type entry, compact row | ✓ SATISFIED | Confirmed |
| CMP-14 | Operand dropdown lists variables (built in 24, verify only) | ✓ SATISFIED | Unchanged |
| CMP-15 | `variable_never_written` preflight + read-only inspector | ✓ SATISFIED | Wired end to end |
| CMP-16 | Both Hardware_Event (op+args) and Tracker set reach log | ⚠️ PARTIAL (documented, not new) | Both events proven reaching ES; positional args not recorded |
| CMP-17 | Version resolution unified: pin → toolkit default → stable → preflight issue, at all 3 sites | ✓ SATISFIED | Proven on rig run 535 |
| CMP-18 | GUI: compute libs behind `kind` filter chip, no new page | ✓ SATISFIED (upload-to-rig round trip not itself hardware-exercised — documented) | `HardwareLibs.tsx` chip + upload form; unit-tested |
| CMP-19 | Declared imports, `test_import` wiring, reserved `compute_lib_import_failed` issue | ✓ SATISFIED | Confirmed present |
| CMP-20 | One read namespace (`view`); `flag`/`hardware` are legacy-only escapes in condition pickers, `wait_condition`, `if`-conditions, action arguments | ✓ SATISFIED | `operandTypes.mts::visibleOperandTypes` narrows a fresh operand to `view`/`literal`/`param`, legacy type appended only when already stored; round-trip proven by 5 new assertion cases; rig-proven (run 551: 7/7 correctly-routed draws; a stored `{flag:...}` operand survived a resave byte-identical) |
| CMP-21 | Declared variables selectable inside `if`/`else` conditions | ✓ SATISFIED | `IfActionEditor.tsx` now forwards `hwModuleNames`/`variableNames` to its `ConditionBuilder` (one-line bug fix); editor-verified on rig |
| CMP-22 | Declared variables selectable as a `flag` action `ref`, resolving to `Tracker` (not `Counter_Tracker`); phantom `decrement`/`reset` removed | ✓ SATISFIED | `ActionEditor.tsx`'s `regularFlagKeys` unions `variableNames`; all three `?? 'Counter_Tracker'` sites replaced with `trackerTypeForRef`; `TRACKER_METHODS.Counter_Tracker` confirmed to have only `increment`/`set` (preflight DB query found 0/153 task definitions used either phantom method before deletion); editor-verified on rig |
| CMP-23 | `ArgInput` gains a `view` mode reading toolkit flags/variables/hardware | ✓ SATISFIED | `ArgInput.tsx`'s `~ View` mode confirmed, backed by `buildViewOptions` with empty detectors array (documented scope decision: no detector channels, no hwModuleNames — Pi has no `view_detector` branch); editor-verified on rig |
| CMP-24 | Pi-side prerequisite for CMP-23, **narrowed 2026-08-05 to the single deployed edit (24b)** | ✓ SATISFIED (narrowed scope); deployed-but-rig-unexercised | `_resolve_arg` (`mics_task.py:518-520`) confirmed reading `get_state()` in the pi-mirror source, deployed to the live Pi per the rsync command recorded in `23-12-SUMMARY.md` and `23-HARDWARE-VALIDATION.md`'s sign-off. CMP-24a/24c confirmed absent from the current pi-mirror source (line 1046 registers `trial_counter` in `self.flags` only; line 903's catch-all still excludes `"view"`) — matches the narrowed REQUIREMENTS.md text exactly. Not a gap: this is the current spec, and both descoped halves are tracked as pending GSD todos. |
| CMP-25 | Backend: semantic hardware valid as a condition-operand read, still invalid as a `flag`-action write ref | ✓ SATISFIED (deployed, unit-tested); deployed-but-rig-unexercised | `fda_validation.py:235,252` confirmed; 8/8 `-k semantic_hardware` tests pass fresh (re-run 2026-08-05); full backend suite 352 passed/1 skipped fresh. Not exercised on the rig because the only available task definition's toolkit is backend-authored — documented in `23-HARDWARE-VALIDATION.md`, not a gap. |

No orphaned requirements found — all of CMP-01–06, CMP-10–25 are claimed by at least one plan's
`requirements` frontmatter (23-01 through 23-10 claim CMP-01–19; 23-11 claims CMP-20–23; 23-12
claims CMP-20–25, restating 20–23 as the checkpoint's full closing scope) and cross-referenced
above. `.planning/REQUIREMENTS.md`'s own Traceability table (lines 257-262) independently marks
CMP-20–23 "Complete" and CMP-24/CMP-25 "Deployed, not rig-exercised" — this verification's
findings match that self-assessment exactly, not merely a re-statement of it.

### Anti-Patterns Found

None found as blockers. No `TODO`/`FIXME`/`PLACEHOLDER` markers, no empty stub returns, and no
console-log-only implementations in any file touched by plans 23-11/23-12
(`operandTypes.mts`, `argModes.mts`, `trackerMethods.mts`, `FlagActionFields.tsx`,
`ConditionBuilder.tsx`, `ArgInput.tsx`, `ActionEditor.tsx`, `IfActionEditor.tsx`,
`api/fda_validation.py`) — re-scanned fresh in this pass. Files touched by plans 23-01 through
23-10 were scanned clean in the prior verification pass and are not re-scanned here (no plan
since has touched them).

One item worth noting as **information**, already tracked in `deferred-items.md` and explicitly
out of this phase's scope: `_build_state_method`'s entry_actions pre-validation loop still
doesn't recognize `type:"view"` (a Phase-24-introduced type; `compute` was correctly added to
that same loop in plan 23-04). This was briefly fixed as CMP-24c and confirmed reverted before
deployment (verified directly: `mics_task.py:903` still reads
`elif atype not in ("timer", "if"):`, no `"view"`). Not a phase 23 regression — it predates the
phase and remains open by explicit descope, not oversight.

### Human Verification Required

1. **Researcher-authored compute lib, full round trip on hardware**
   **Test:** Create a new (non-seed) compute lib in the Hardware Libraries editor, promote unvalidated→beta→stable, link to a toolkit, confirm its ops appear in `ComputeActionFields`' grouped picker, then run a task using it on the rig.
   **Expected:** Ops appear via AST metadata with no platform code change; the lib ships through `LOAD_HARDWARE_LIBS` and executes on the Pi.
   **Why human:** Explicitly documented in `23-HARDWARE-VALIDATION.md` §3 as never exercised — only the seed `Compute Ops` lib was rig-tested; this path has unit coverage only.

2. **The actual gonogo task, not its FDA equivalent**
   **Test:** Build and run the real `gonogo` random-target task translated to FDA-JSON-v2, on the rig.
   **Expected:** Same proven mechanism (compute draw → variable → guarded transitions, both branches, recomputed per entry) holds for the actual gonogo content.
   **Why human:** `23-HARDWARE-VALIDATION.md` §3 explicitly states the gonogo task itself was never built; an equivalent test FDA was validated instead. This is a content-authoring gap, not a code gap, and requires rig access.

3. **CMP-24b as an actual argument, on the rig**
   **Test:** On a task using a semantic toolkit, set an action argument's `~ View` mode to a hardware name and run it.
   **Expected:** The value resolves through `get_state()` — no `AttributeError`.
   **Why human:** `23-HARDWARE-VALIDATION.md`'s Plan 23-12 sign-off records that task 186 (the only rig-available definition) never routes a `{"view": hardware}` operand through `_resolve_arg` as an argument — only as a condition, which uses a different builder. The fix is deployed but its exact code path has zero rig proof.

4. **CMP-25's 422→200 flip, on a semantic toolkit, on the rig**
   **Test:** On a semantic (non-backend-authored) toolkit, build a transition condition reading a semantic-hardware name via `view` and save.
   **Expected:** 200, not 422.
   **Why human:** Task 186 is backend-authored with `semantic_hardware=null`, so this exact code path was never live during sign-off. The backend fix is deployed and unit-tested (8/8 passing, confirmed fresh in this verification), but not rig-proven.

### Gaps Summary

No gaps found against this phase's must-haves. All 12 plans (23-01 through 23-12) have artifacts
present, substantive, and wired. Re-run fresh in this pass: full backend test suite (352 passed,
1 skipped), the 8 CMP-25-specific `-k semantic_hardware` cases, TypeScript compile
(`tsc --noEmit` clean), and React unit tests (84/84 pass — 53 pre-23-11, +21 new pure-logic
cases in `operandTypes.test.mts`/`argModes.test.mts`/`trackerMethods.test.mts`, +10 not
previously counted individually). Every requirement ID (CMP-01–06, CMP-10–25) maps to verified
code, and none is orphaned.

Direct source inspection confirms the narrowed CMP-24 scope exactly matches both
`REQUIREMENTS.md`'s current text and `23-HARDWARE-VALIDATION.md`'s sign-off record: `mics_task.py`
carries the CMP-24b `get_state()` edit (deployed, live on the Pi) and does **not** carry the
CMP-24a (`trial_counter` view-mirror) or CMP-24c (`type:"view"` in a state body) edits — both
confirmed absent from the current pi-mirror source, consistent with their documented revert.

Three items carry accepted, pre-documented partial or deployed-but-unexercised status rather
than being reported as gaps here, per this verification's explicit scope: CMP-16 (op args absent
from the event log, carried from the prior pass), and CMP-24b/CMP-25 (both deployed and
unit/backend-test-verified, but neither's exact rig code path has been exercised yet — task 186
is the only rig-available definition and its shape does not reach either). All three are called
out explicitly in `23-HARDWARE-VALIDATION.md` and in `REQUIREMENTS.md`'s own traceability table
as the phase's own closing judgement already accepted — not as newly discovered defects, and not
upgraded to "verified" here since neither has rig evidence.

---

*Verified: 2026-08-05T12:49:06Z*
*Verifier: Claude (gsd-verifier)*
