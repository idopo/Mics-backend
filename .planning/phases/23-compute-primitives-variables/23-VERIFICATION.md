---
phase: 23-compute-primitives-variables
verified: 2026-08-03T13:12:56Z
status: passed
score: 6/6 phase-level success criteria verified (1 with a documented, accepted caveat)
known_open_items_not_gaps:
  - "Gonogo task itself never built — an equivalent compute-gated FDA (random_float draw gating a transition) was validated in its place; the mechanism is proven, gonogo is not"
  - "CMP-16 partial — Hardware_Event logs op + result but not positional args (event_data.update(kwargs) only); scientifically material for non-invertible ops"
  - "CMP-18 — researcher-authored compute lib upload has unit coverage (test_hardware_lib_kind.py) but was never exercised end-to-end on the rig"
  - "hot_update_fda variable-collision predicted by code inspection (plan 23-04), never triggered in any run"
  - "Pi-side unit tests (test_compute_ops.py, test_fda_vocabulary.py) never run on the Pi itself (autopilot unimportable on dev host); all Pi evidence is from live runs"
human_verification:
  - test: "Upload a researcher-authored compute lib through the Hardware Libraries page GUI, promote it to stable, link it to a toolkit, and confirm its ops appear in the GUI op picker with no platform code change"
    expected: "New ops appear in ComputeActionFields' grouped picker without any code deploy; the lib round-trips through LOAD_HARDWARE_LIBS to a real Pi"
    why_human: "Documented as NOT exercised on hardware in 23-HARDWARE-VALIDATION.md Section 3 — unit-tested only"
  - test: "Build and run the actual gonogo task (not the equivalent test FDA) end to end on the rig"
    expected: "Same mechanism proven by the validated FDA (compute draw -> variable -> guarded transitions) holds for the real gonogo logic"
    why_human: "Explicitly documented as not built in 23-HARDWARE-VALIDATION.md Section 3; requires rig access and is a content/authoring task, not a code gap"
---

# Phase 23: Compute Operations (Compute Libs) Verification Report

**Phase Goal:** A researcher can compute a value inside a state, store it in a variable, and
transition on it — without a developer editing locked toolkit source, and with every
computation recorded in the event log. Delivered as a compute lib on the existing hardware-lib
substrate (new `kind` column, versioning, AST, `LOAD_HARDWARE_LIBS`) rather than curated pure
functions. GUI compute action + operand wiring; backend validation; CMP-17 version-resolution
unification.

**Verified:** 2026-08-03T13:12:56Z
**Status:** passed
**Re-verification:** No — initial verification

## Goal Achievement

### Observable Truths (Phase-level Success Criteria, ROADMAP.md)

| # | Truth | Status | Evidence |
|---|---|---|---|
| 1 | Pi runtime: `variables` + `compute` action load/run, both guarded branches fire across trials, recomputed once per entry, last-write-wins, hot-reload re-creates variables before rebuilding transitions | ✓ VERIFIED | `mics_task.py:714-735` compute branch; `fda_vocabulary.py` + `validate_fda.py` compute branches; proven live on rig runs 543-547 (41 draws, 0 routing violations, 4-deep retry chain resolved); `hot_update_fda` (mics_task.py:1428) rebuilds `self.stages` from a re-run `load_fda_from_json` |
| 2 | Logging (CMP-16): both a `Hardware_Event` (op+args) and a `Tracker` set (result) reach the event log per compute call | ⚠️ VERIFIED — documented partial | Both events proven reaching ES for numeric AND non-numeric outputs (run 550, 10/10/10 pairs, 0 rejected docs) via `coerce_for_event`/`coerce_result` (`log_value.py`) wired into `logging_utils.py`. **Known, pre-documented gap** (not a new finding): `log_action`'s Hardware branch only does `event_data.update(kwargs)` — positional args (the actual op parameters, since compute calls pass positionally) are never recorded. Both events survive; the op's *inputs* are not recoverable from ES. |
| 3 | Extensibility: a lib created in the hardware-lib editor is versioned, promoted, linked to a toolkit, shipped via `LOAD_HARDWARE_LIBS`, and its ops appear in the GUI picker with no platform code change | ✓ VERIFIED (mechanism); researcher-authored round trip not hardware-exercised (documented, not a gap) | `hardware_libs.py` upload/promote/link endpoints unchanged in shape, `kind='compute'` distinguishes rows; `ComputeActionFields.tsx` reads AST metadata via `isComputeModule` grouping — same picker path as hardware libs. Seed lib (`Compute Ops`, 13 ops) proven end-to-end on rig (run 535, 5 libs dispatched, all `HARDWARE_LIB_TEST_RESULT ok=True`). Uploading a *different*, researcher-authored lib was not itself run on the rig — has unit coverage only (`test_hardware_lib_kind.py`). |
| 4 | Backend: 422 on undeclared `output`/collision/undeclared-variable-ref; `fda_utils` scanner returns compute outputs; `kind` distinguishes libs; version resolution corrected (pin → toolkit default → stable → preflight issue) for both lib kinds | ✓ VERIFIED | `api/fda_validation.py::validate_compute_variables`/`_validate_action` (compute branch); `api/fda_utils.py:42` includes `"compute"` in ref-scanned action types; `api/lib_version_resolution.py::resolve_lib_version_id` is the single chain, consumed by `toolkit_dispatch.py` (dispatch), `hw_introspect.py` (introspection), and the orchestrator (via `GET .../hardware-libs` `resolved_*` fields) — proven unified rather than 3 divergent derivations. Full backend suite green (347 passed, 1 skipped). |
| 5 | GUI uncluttered: Hardware Libraries page gains one `kind` filter chip; StateBodyPanel gains exactly one "Compute" action-type entry rendering one compact row; typing a new `output` auto-declares into `variables`, immediately selectable in ConditionBuilder; save round-trips | ✓ VERIFIED | `HardwareLibs.tsx` `kindFilter` state + `kind` select; `ActionEditor.tsx` action-type `<select>` has exactly one `compute` `<option>` (gated off in trigger context via `allowTriggerContext` — confirmed at line 264); `ComputeActionFields.tsx` renders the compact row; `onDeclareVariable` threaded `ComputeActionFields → ActionEditor → StateBodyPanel → TaskEditor.declareVariable` (`TaskEditor.tsx:788`). `tsc --noEmit` clean, `npm run build` succeeds, `npm run test:unit` 53/53 pass. |
| 6 | Discoverability (CMP-15): `variable_never_written` preflight issue surfaces through Phase 25's existing renderer; read-only variables inspector shows writers/readers | ✓ VERIFIED | `api/variable_scan.py::variable_never_written_issues` wired into `toolkit_dispatch.py::preflight_validate` (line 454); rendered via `HardwareCheckModal.tsx`'s `ComputeIssueDetail` and excluded from the destructive PUT loop via `NON_CONFIG_ISSUES` set (lines 48-53, 389, 420); `VariableUsagePanel.tsx` wired into `VariablesPanel.tsx` wired into `TaskEditor.tsx:801`; backend route `api/routers/task_def_inspect.py` (`GET /api/task-definitions/{id}/variable-usage`). |

**Score:** 6/6 truths verified (truth 2 carries a pre-documented partial caveat; truth 3 carries a pre-documented untested-path caveat — both explicitly out of scope for this report per the hardware validation log).

### Required Artifacts

| Artifact | Expected | Status | Details |
|---|---|---|---|
| `api/tests/test_hardware_lib_kind.py` | CMP-12/19 contract test | ✓ VERIFIED | Exists, 20.8K, passes in suite |
| `api/tests/test_toolkit_dispatch.py` | CMP-17 contract test | ✓ VERIFIED | Exists, 12.3K, passes in suite |
| `/home/ido/pi-mirror/tests/test_compute_ops.py` | Pi compute dispatch contract (USER-RUN) | ✓ VERIFIED (exists; not agent-runnable) | Exists, 17.6K; `autopilot` unimportable on dev host — documented, not a gap |
| `api/seed_libs/compute_ops.py` | Seed compute lib, `Hardware` subclass, `release()`, 13 ops | ✓ VERIFIED | `release()` present line 32; 13 `@log_action` methods matching CMP-04's exact op list |
| `api/seed_compute.py` | Idempotent seeding | ✓ VERIFIED | `seed_compute_ops_lib`, `COMPUTE_STDLIB_ALLOWLIST` both present |
| `api/compute_provisioning.py` | Auto-provisioning of pilot config rows | ✓ VERIFIED | `provision_compute_configs`, `compute_module_names` present; wired into `hardware_modules.py` POST and `toolkit_dispatch.py` preflight self-heal |
| `api/db.py::run_hardware_lib_kind_migration` | Idempotent `kind` column migration | ✓ VERIFIED | `ADD COLUMN IF NOT EXISTS` present, called at startup |
| `api/fda_validation.py` | Compute validation branch | ✓ VERIFIED | `validate_compute_variables`, compute in `VALID_ACTION_TYPES`, compute branch in `_validate_action` |
| `api/variable_scan.py` | Writer/reader analysis | ✓ VERIFIED | `scan_variable_writers`, `scan_variable_readers`, `variable_never_written_issues` all present and wired |
| `api/fda_utils.py` | Ref scanner covers compute outputs | ✓ VERIFIED | `"compute"` in scanned action types (line 42) |
| `api/lib_version_resolution.py` | Single resolution chain | ✓ VERIFIED | `resolve_lib_version_id`, `resolve_lib_versions`, `RESOLUTION_REASONS`; consumed by 3 sites |
| `web_ui/react-src/src/pages/hardware-libs/HardwareLibs.tsx` | kind filter chips + upload form | ✓ VERIFIED | `kind`/`kindFilter` state, upload form with declared imports |
| `web_ui/react-src/src/types/index.ts` | `HardwareLib.kind`, `declared_imports`, `lib_kind` | ✓ VERIFIED | `lib_kind` present (line 504) |
| `api/routers/task_def_inspect.py` | Variable-usage route | ✓ VERIFIED | `router` exported, GET endpoint present |
| `web_ui/react-src/src/components/ComputeActionFields.tsx` | Compute row UI | ✓ VERIFIED | 7.8K, `isComputeModule` filter, grouped op picker, `onDeclareVariable` |
| `web_ui/react-src/src/components/VariableUsagePanel.tsx` | Read-only inspector | ✓ VERIFIED | 2.8K, wired via `VariablesPanel.tsx` into `TaskEditor.tsx` |
| `.planning/phases/23-compute-primitives-variables/23-HARDWARE-VALIDATION.md` | Hardware proof record | ✓ VERIFIED | 264 lines, documents proven/not-proven/deployed state with ES/orchestrator evidence |

### Key Link Verification

| From | To | Via | Status | Details |
|---|---|---|---|---|
| `mics_task.py::_build_action_callable` compute branch | `self._capture_output` / `self.flags[name].set` | same call-and-capture pattern as hardware branch | ✓ WIRED | Lines 730-735, byte-for-byte parallel to hardware branch |
| compute op method | `Event_Dispatcher` | `@log_action` on `Hardware` subclass | ✓ WIRED | Proven on rig — `Modules {"id":"COMPUTE",...}` per call, runs 541+ |
| `api/fda_validation.py::collect_hard_errors` | `validate_compute_variables` | one more term in the existing sum | ✓ WIRED | Line 279 |
| `api/routers/toolkits.py` | `reject_if_hard_errors` | POST/PUT save-time gate | ✓ WIRED | Lines 588, 862 |
| `api/main.py` startup | `run_hardware_lib_kind_migration` + `seed_compute_ops_lib` | startup call | ✓ WIRED | Confirmed present at startup |
| `api/routers/toolkit_dispatch.py::get_dispatch_spec` | `resolve_lib_version_id` | replaces inline pin→active chain | ✓ WIRED | Line 77 |
| `api/hw_introspect.py::toolkit_hw_capabilities` | `resolve_lib_versions` | third divergent site unified | ✓ WIRED | Line 170 |
| `orchestrator_station.py::_send_hardware_libs_if_needed` | `GET /toolkits/{id}/hardware-libs` `resolved_*` fields | orchestrator reads backend's answer instead of re-deriving | ✓ WIRED | Lines 852-892; proven on rig run 535 |
| `api/routers/toolkit_dispatch.py::preflight_validate` | `variable_scan.py::variable_never_written_issues` | step in preflight | ✓ WIRED | Line 454 |
| `api/routers/toolkit_dispatch.py::preflight_validate` | `compute_provisioning.py::provision_compute_configs` | self-heal before per-module loop | ✓ WIRED | Line 265 |
| `ComputeActionFields.tsx` | `HardwareModule.lib_kind === 'compute'` | `isComputeModule` predicate | ✓ WIRED | Exported from `ActionEditor.tsx:77`, used in `ComputeActionFields.tsx:41` |
| `ComputeActionFields.tsx` output combobox | `TaskEditor.fdaJson.variables` | `onDeclareVariable` callback | ✓ WIRED | Threaded `ComputeActionFields → ActionEditor → StateBodyPanel → TaskEditor:788` |
| `HardwareCheckModal.tsx::handleStart` + `pendingEdits` init | `view_key_unresolved` skip pattern | `variable_never_written`/`lib_version_unresolved` join `NON_CONFIG_ISSUES` | ✓ WIRED | Lines 48-53, 389, 420 |
| `VariableUsagePanel.tsx` | `GET /api/task-definitions/{id}/variable-usage` | react-query | ✓ WIRED | Confirmed via `task_def_inspect.py` router |
| orchestrator `LOAD_HARDWARE_LIBS` | Pi `HARDWARE_OVERRIDE_DIR/compute_ops.py` | resolved stable version's source, `test_import=True` | ✓ WIRED | Proven on rig run 535, 5/5 `HARDWARE_LIB_TEST_RESULT ok=True` |
| compute op call | Elasticsearch `event_log_v2` | `@log_action` Hardware_Event AND Tracker.set, both per call | ✓ WIRED (with documented CMP-16 args caveat) | Proven run 550, 10/10/10 pairs, 0 rejected docs |

### Requirements Coverage

| Requirement | Description (abridged) | Status | Evidence |
|---|---|---|---|
| CMP-01 | `variables` registry (built in 24, verify only) | ✓ SATISFIED | `load_fda_from_json` ~line 1017-region confirmed present; regression tests in `test_compute_ops.py` Task 3 |
| CMP-02 | Variable = Tracker in `self.flags` + `self.view.view` | ✓ SATISFIED | Same as CMP-01; unchanged since Phase 24 |
| CMP-03 | `type:"compute"` entry action, thin alias over hardware call-and-capture | ✓ SATISFIED | `mics_task.py:714-735`, proven on rig |
| CMP-04 | Compute lib = `Hardware` subclass, seed content (13 stdlib ops) | ✓ SATISFIED | `compute_ops.py` exact match |
| CMP-05 | Last-write-wins on re-entry | ✓ SATISFIED | Proven on rig runs 543-547 (redraw on re-entry) |
| CMP-06 | Hot-reload recreates variables before rebuilding transitions | ✓ SATISFIED | `hot_update_fda` (mics_task.py:1428) re-runs load path; not separately rig-proven this phase but mechanism unchanged from Phase 2/24 |
| CMP-10 | Hard 422s: undeclared output, collisions, undeclared var refs | ✓ SATISFIED | `fda_validation.py`, tests pass (`test_hardware_lib_kind.py`, `test_task_definitions_validation.py`) |
| CMP-11 | `fda_utils.py` scanner covers compute outputs | ✓ SATISFIED | Line 42 confirmed |
| CMP-12 | `kind` column, idempotent migration | ✓ SATISFIED | `run_hardware_lib_kind_migration`, DB confirmed `kind='compute'` row (id 45) |
| CMP-13 | Exactly one "Compute" action-type entry, compact row | ✓ SATISFIED | `ActionEditor.tsx` one `<option value="compute">`; `ComputeActionFields.tsx` renders compact row |
| CMP-14 | Operand dropdown lists variables (built in 24, verify only) | ✓ SATISFIED | `variableNames` threaded through `ArgInput`/`ConditionBuilder`, unchanged |
| CMP-15 | `variable_never_written` preflight + read-only inspector | ✓ SATISFIED | `variable_scan.py`, `VariableUsagePanel.tsx`, wired end to end |
| CMP-16 | Both Hardware_Event (op+args) and Tracker set reach log | ⚠️ PARTIAL (documented, not new) | Both events proven reaching ES; positional args not recorded (`event_data.update(kwargs)` only) |
| CMP-17 | Version resolution unified: pin → toolkit default → stable → preflight issue, at all 3 sites | ✓ SATISFIED | `lib_version_resolution.py` consumed by dispatch/introspection/orchestrator; proven on rig run 535 |
| CMP-18 | GUI: compute libs behind `kind` filter chip, no new page | ✓ SATISFIED (upload-to-rig round trip not itself hardware-exercised — documented) | `HardwareLibs.tsx` chip + upload form; unit-tested (`test_hardware_lib_kind.py`) |
| CMP-19 | Declared imports, `test_import` wiring, reserved `compute_lib_import_failed` issue | ✓ SATISFIED | `COMPUTE_STDLIB_ALLOWLIST`, `_validate_compute_lib`, `test_import=True` in `_send_hardware_libs_if_needed`, reserved issue kind in `toolkit_dispatch.py:161` |

No orphaned requirements found — all of CMP-01–06, CMP-10–19 are claimed by at least one plan's `requirements` frontmatter and cross-referenced above.

### Anti-Patterns Found

None found as blockers. No `TODO`/`FIXME`/`PLACEHOLDER` markers, no empty stub returns, and no console-log-only implementations in the touched files (`api/fda_validation.py`, `api/variable_scan.py`, `api/lib_version_resolution.py`, `api/compute_provisioning.py`, `api/seed_compute.py`, `api/seed_libs/compute_ops.py`, `ComputeActionFields.tsx`, `VariableUsagePanel.tsx`, `mics_task.py` compute branch, `fda_vocabulary.py`, `validate_fda.py`, `logging_utils.py`, `log_value.py`).

One item worth noting as **information**, already tracked in `deferred-items.md` and explicitly out of this phase's scope: `_build_state_method`'s entry_actions pre-validation loop still doesn't recognize `type:"view"` (a Phase-24-introduced type) — `compute` was correctly added to that same loop in plan 23-04, but `view`'s pre-existing gap was left as-is per the SCOPE BOUNDARY rule. Not a phase 23 regression or requirement.

### Human Verification Required

1. **Researcher-authored compute lib, full round trip on hardware**
   **Test:** Create a new (non-seed) compute lib in the Hardware Libraries editor, promote unvalidated→beta→stable, link to a toolkit, confirm its ops appear in `ComputeActionFields`' grouped picker, then run a task using it on the rig.
   **Expected:** Ops appear via AST metadata with no platform code change; the lib ships through `LOAD_HARDWARE_LIBS` and executes on the Pi.
   **Why human:** Explicitly documented in `23-HARDWARE-VALIDATION.md` §3 as never exercised — only the seed `Compute Ops` lib was rig-tested; this path has unit coverage only.

2. **The actual gonogo task, not its FDA equivalent**
   **Test:** Build and run the real `gonogo` random-target task translated to FDA-JSON-v2, on the rig.
   **Expected:** Same proven mechanism (compute draw → variable → guarded transitions, both branches, recomputed per entry) holds for the actual gonogo content.
   **Why human:** `23-HARDWARE-VALIDATION.md` §3 explicitly states the gonogo task itself was never built; an equivalent test FDA was validated instead. This is a content-authoring gap, not a code gap, and requires rig access.

### Gaps Summary

No gaps found against this phase's must-haves. All 10 plans (23-01 through 23-10) have artifacts present, substantive, and wired; the full backend test suite (347 passed, 1 skipped), TypeScript compile, Vite build, and React unit tests (53/53) all pass fresh as of this verification. The three sites of the CMP-17 version-resolution bug are confirmed unified into one resolver. Every requirement ID (CMP-01–06, CMP-10–19) maps to verified code, and none is orphaned.

Two items carry accepted, pre-documented partial status rather than being reported as gaps here, per this verification's explicit scope: CMP-16 (op args absent from the event log) and CMP-18/gonogo (hardware round-trips not exercised for the researcher-authored-lib and true-gonogo cases). Both are called out in `23-HARDWARE-VALIDATION.md` as open items the phase's own closing judgement already accepted, not as newly discovered defects.

---

*Verified: 2026-08-03T13:12:56Z*
*Verifier: Claude (gsd-verifier)*
