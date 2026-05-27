---
phase: 12-hardware-fda-builder
verified: 2026-05-24T06:49:04Z
status: gaps_found
score: 44/46 must-haves verified
re_verification:
  previous_status: gaps_found
  previous_score: 34/38
  gaps_closed: []
  gaps_remaining:
    - "Hardware action output: UI does not emit group:Modules key (Pi resolves correctly via _semantic_hw fallback — plan truth overstated)"
    - "Plan 12-04 frontmatter requirement HW-21 is mismatched to REQUIREMENTS.md definition (traceability only, no functional impact)"
  new_truths_verified:
    - "New task def auto-pins to stable/active hw lib version at creation (12-05 Fix 1)"
    - "_validate_task_definition reads pinned version AST when task_def_id provided (12-05 Fix 2)"
    - "Pin set/delete immediately re-validates task def via _revalidate_task_def (12-05 Fix 3)"
    - "Restore this version button removed from HardwareLibDetail (12-05 Fix 4)"
    - "HwLibVersionModal refactored to accept pins:HwLibPin[] for multi-lib display"
    - "ActionEditor defaultArgForTrackerType + useEffect auto-injects arg for existing flag actions loaded from DB"
    - "fda_utils.py scan_fda_for_refs guarded against non-dict states value"
    - "hardware_modules DELETE now cascades to PilotHardwareConfig rows"
  regressions: []
gaps:
  - truth: "Hardware action output uses direct refs: {type:hardware,group:Modules,ref:Left_LED,method:on} — NOT semantic alias keys"
    status: partial
    reason: "UI (ActionEditor) does not add group:Modules to hardware actions — zero occurrences in ActionEditor.tsx. FdaAction interface has no group field. Pi works correctly because mics_task.py:762-764 registers all hardware[Modules] entries into _semantic_hw by module name; direct-ref format resolves via the semantic fallback. Plan truth overstated the requirement — the Pi does not need the group key to resolve correctly."
    artifacts:
      - path: "web_ui/react-src/src/components/ActionEditor.tsx"
        issue: "Zero occurrences of 'group' string; hardware actions serialize as {type,ref,method,args} only"
      - path: "web_ui/react-src/src/types/index.ts"
        issue: "FdaAction interface has no group field — type system does not model it"
    missing:
      - "Either: add group:Modules to hardware/timer actions in ActionEditor for plan-compliance, OR close this gap by documenting that Pi fallback registration is the intended mechanism"
  - truth: "Plan 12-04 claim: HW-21 addresses initial state selection for sourceless toolkits"
    status: failed
    reason: "REQUIREMENTS.md maps HW-21 to Phase 13 (POST /api/task-definitions/{id}/validate-for-pilot/{pilot_id}). Plan 12-04 implements initial state selection (correct feature, correct phase) but claims HW-21 in its frontmatter. The feature is implemented correctly. The validate-for-pilot endpoint (actual HW-21) is correctly deferred to Phase 13."
    artifacts:
      - path: ".planning/phases/12-hardware-fda-builder/12-04-PLAN.md"
        issue: "frontmatter requirements: [HW-21] — but HW-21 per REQUIREMENTS.md is the validate-for-pilot endpoint (Phase 13)"
    missing:
      - "Traceability fix only: Plan 12-04 should reference an unnamed requirement or HW-17 (already covers StateBodyPanel UI) rather than HW-21"
human_verification:
  - test: "Open task editor for a backend-authored toolkit, add a hardware action — verify method dropdown populates immediately without manual re-selection of module"
    expected: "Methods list appears for first hw module as soon as Add Action is clicked"
    why_human: "First-render timing of hwModules + addAction interaction requires browser testing"
  - test: "Open task editor, add a flag action for a Boolean_Tracker, switch method to set, save, reload page"
    expected: "Bool select shows false (not blank) after reload; the useEffect auto-inject fires on load"
    why_human: "Auto-inject useEffect for existing flag actions from DB requires live browser testing"
  - test: "Create a new task definition for a toolkit that has hardware libs — then GET /api/task-definitions/{id}/hw-lib-pins"
    expected: "Response includes pins for all hw libs linked to the toolkit pointing to stable/active version"
    why_human: "Auto-pin at creation requires live API call with actual DB data"
  - test: "Right-click a non-initial state in the FDA canvas, select Set as Initial State"
    expected: "INIT badge moves to selected state; previous initial loses badge; auto-save fires within 1.5s"
    why_human: "ReactFlow context menu positioning and event wiring requires browser testing"
  - test: "On PilotHardwareConfig page, click Delete on a hardware module that has a config entry"
    expected: "Module itself is deleted (not just its config); list refreshes; hardware-modules query also invalidated"
    why_human: "Behavioral change from deletePilotHardwareConfig to deleteHardwareModule requires UI testing to confirm cascade"
---

# Phase 12: Hardware-Aware FDA Builder Verification Report (Re-verification)

**Phase Goal:** FDA state builder knows hardware module methods via AST. Entry actions can pick a hardware module, method, and args with type hints. Lib-change impact detection flags broken task definitions.
**Verified:** 2026-05-24T06:49:04Z
**Status:** gaps_found
**Re-verification:** Yes — after Plan 12-05 additions and ActionEditor bug fixes

## Goal Achievement

### Observable Truths

| # | Truth | Plan | Status | Evidence |
|---|-------|------|--------|----------|
| 1 | ToolkitRead has hardware_module_ids + typed flags (ToolkitFlag with tracker_type) | 12-01 | VERIFIED | `types/index.ts:275-297` |
| 2 | TaskDefinitionFull has optional validation_status and validation_message | 12-01 | VERIFIED | `types/index.ts:340-350` |
| 3 | StateBodyPanel covers 5 action types; type:special renders read-only legacy chip | 12-01 | VERIFIED | `ActionEditor.tsx:279-288` |
| 4 | Hardware module picker for backend-authored toolkits; legacy semantic dropdown unchanged | 12-01 | VERIFIED | `ActionEditor.tsx:315-349` |
| 5 | Timer modules identified by lib_filename = 'timer.py' | 12-01 | VERIFIED | `ActionEditor.tsx:74-76` |
| 6 | Broken definition warning banner in TaskEditor when validation_status = "broken" | 12-01 | VERIFIED | `TaskEditor.tsx:422-429` |
| 7 | Warning badge in TaskDefinitions list for broken definitions | 12-01 | VERIFIED | `TaskDefinitions.tsx:329-339` |
| 8 | Hardware action output uses {group:Modules} discriminator key | 12-01 | PARTIAL | UI omits group key; Pi resolves via _semantic_hw fallback (`mics_task.py:762-764`) |
| 9 | Pi _build_action_callable() handles both group-key format and legacy semantic format | 12-01 | VERIFIED | `mics_task.py:534-545` |
| 10 | Pi _build_state_method() unconditionally appends wait_for_condition() for GUI states | 12-01 | VERIFIED | `mics_task.py:665-668` |
| 11 | Pi _build_condition_operand() handles hardware operand via direct-ref and semantic path | 12-01 | VERIFIED | `mics_task.py:460-471` |
| 12 | ConditionBuilder uses getParamKeys(toolkit) helper for param dropdown | 12-01 | VERIFIED | `ConditionBuilder.tsx:2,66` |
| 13 | ConditionBuilder shows populated dropdowns for flag/param/literal operands | 12-01 | VERIFIED (structural) | `ConditionBuilder.tsx:66` — browser test needed |
| 14 | Each action card has colored left-border accent per type | 12-01 | VERIFIED | `ActionEditor.tsx:5-28` |
| 15 | ArgInput mode buttons are colored pills: # Literal (grey), $ Param (green), ! Flag (amber) | 12-01 | VERIFIED | `ArgInput.tsx:38+` |
| 16 | ArgInput literal input is a text field (not number) | 12-01 | VERIFIED | `ArgInput.tsx` — annotationToInputKind() |
| 17 | ArgInput getParamKeys() handles both array and dict params_schema shapes | 12-01 | VERIFIED | `ArgInput.tsx:6` |
| 18 | Hardware module methods cached in module-level METHOD_CACHE object | 12-01 | VERIFIED | `ActionEditor.tsx:8` |
| 19 | All field labels carry title= tooltip with plain-English explanation | 12-01 | VERIFIED | `ActionEditor.tsx:317,353` |
| 20 | On type change, first valid option auto-selected for all new fields | 12-01 | VERIFIED | `ActionEditor.tsx:207-225` |
| 21 | StateBodyPanel shows colored type chip + up/down reorder buttons per action row | 12-01 | VERIFIED | `StateBodyPanel.tsx:5,71,107,114,122` |
| 22 | StateBodyPanel and IfActionEditor thread hwModules: HardwareModule[] prop | 12-01 | VERIFIED | `StateBodyPanel.tsx:47`, `IfActionEditor.tsx:97,167` |
| 23 | Right panel width is 380px | 12-01 | VERIFIED | `TaskEditor.tsx:575` |
| 24 | validation_status + validation_message columns added to task_definitions | 12-02 | VERIFIED | `models.py:527-528` |
| 25 | run_task_definition_validation_migrations() called at API startup | 12-02 | VERIFIED | `main.py:14,144` |
| 26 | scan_fda_for_refs() walks all entry_actions including type:if branches; guarded against non-dict states | 12-02 | VERIFIED | `fda_utils.py:13-14,35-37` |
| 27 | HardwareLib PUT diffs AST and flags broken task definitions | 12-02 | VERIFIED | `hardware_libs.py:335-363` |
| 28 | Toolkit PATCH flags broken task definitions on flag/module removal | 12-02 | VERIFIED | `toolkits.py:456-496` |
| 29 | TaskDefinition PUT re-validates and resets status | 12-02 | VERIFIED | `toolkits.py:696-743` |
| 30 | addAction() initializes ref to first hw module (methods fetch on first render) | 12-03 | VERIFIED | `StateBodyPanel.tsx:61-68` |
| 31 | Bool arg select normalized with value ? 'true' : 'false' | 12-03 | VERIFIED | `ArgInput.tsx:118` |
| 32 | _normalize_flags() injects trial_counter Trial_Tracker if none exists | 12-03 | VERIFIED | `toolkits.py:56-58` |
| 33 | ActionEditor trial section shows static label when only one trial flag | 12-03 | VERIFIED | `ActionEditor.tsx:421-423` |
| 34 | load_fda_from_json() auto-creates trial_counter Trial_Tracker if missing | 12-03 | VERIFIED | `mics_task.py:773-775` |
| 35 | TaskEditor auto-saves fdaJson changes after 1500ms debounce | 12-03 | VERIFIED | `TaskEditor.tsx:211-221` |
| 36 | First state added to empty FDA auto-set as initial_state | 12-04 | VERIFIED | `TaskEditor.tsx:289,295` |
| 37 | Right-click shows Set as Initial State context menu; setInitialState() updates fdaJson | 12-04 | VERIFIED | `TaskEditor.tsx:133,312,526,552` |
| 38 | Deleting initial state clears fdaJson.initial_state; save blocked when initial_state unset | 12-04 | VERIFIED | `TaskEditor.tsx:327,341,344` |
| 39 | New task def auto-pins to stable/active hw lib version at creation | 12-05 | VERIFIED | `toolkits.py:597-617` |
| 40 | _validate_task_definition reads pinned version AST when task_def_id provided | 12-05 | VERIFIED | `toolkits.py:700-721` |
| 41 | Setting or deleting a hw lib pin immediately re-validates the task def | 12-05 | VERIFIED | `hardware_libs.py:773,810` |
| 42 | Restore this version button removed from HardwareLibDetail | 12-05 | VERIFIED | `HardwareLibDetail.tsx` — zero matches for rollback/restore |
| 43 | ActionEditor auto-injects correct default arg for flag actions loaded from DB with empty args | 12-05 | VERIFIED | `ActionEditor.tsx:270-277` |
| 44 | defaultArgForTrackerType returns false for Boolean_Tracker, 0 for others | 12-05 | VERIFIED | `ActionEditor.tsx:70-72` |
| 45 | HwLibVersionModal accepts pins:HwLibPin[] (multi-lib) and manages all pin selections in one modal | 12-05 | VERIFIED | `HwLibVersionModal.tsx:6-11` |
| 46 | Hardware module delete cascades to PilotHardwareConfig rows | 12-05 | VERIFIED | `hardware_modules.py:133-134` |

**Score:** 44/46 truths verified (1 partial — group key in hardware actions, functional via Pi fallback; 1 traceability label mismatch in Plan 12-04 frontmatter)

### Required Artifacts

| Artifact | Status | Details |
|----------|--------|---------|
| `web_ui/react-src/src/types/index.ts` | VERIFIED | ToolkitFlag, ToolkitRead.flags, TaskDefinitionFull.validation_status |
| `web_ui/react-src/src/pages/task-editor/TaskEditor.tsx` | VERIFIED | Full action editor, broken banner, 380px, auto-save, initial state, HwLibVersionModal with pins prop |
| `web_ui/react-src/src/pages/task-definitions/TaskDefinitions.tsx` | VERIFIED | Warning badge lines 329-339 |
| `web_ui/react-src/src/components/ActionEditor.tsx` | VERIFIED | defaultArgForTrackerType, useEffect auto-inject, METHOD_CACHE, 5 types |
| `web_ui/react-src/src/components/ArgInput.tsx` | VERIFIED | Colored pills, annotationToInputKind, getParamKeys |
| `web_ui/react-src/src/components/ConditionBuilder.tsx` | VERIFIED | getParamKeys usage at lines 2, 66 |
| `web_ui/react-src/src/components/StateBodyPanel.tsx` | VERIFIED | hwModules prop, chips, reorder, addAction with firstMod |
| `web_ui/react-src/src/components/IfActionEditor.tsx` | VERIFIED | hwModules prop threaded |
| `web_ui/react-src/src/pages/task-editor/HwLibVersionModal.tsx` | VERIFIED | Refactored to multi-pin (pins:HwLibPin[]), useQueries per pin |
| `web_ui/react-src/src/pages/hardware-libs/HardwareLibDetail.tsx` | VERIFIED | Restore button absent |
| `api/fda_utils.py` | VERIFIED | isinstance(states, dict) guard added; recursion into if branches |
| `api/models.py` | VERIFIED | validation_status + validation_message columns |
| `api/db.py` | VERIFIED | run_task_definition_validation_migrations() |
| `api/routers/hardware_libs.py` | VERIFIED | _revalidate_task_def helper; called after set/delete pin; cascade delete on module |
| `api/routers/toolkits.py` | VERIFIED | Auto-pin at creation; _validate_task_definition with task_def_id; defn_id at call site |
| `api/routers/hardware_modules.py` | VERIFIED | DELETE cascades to PilotHardwareConfig |
| `~/pi-mirror/autopilot/autopilot/tasks/mics_task.py` | VERIFIED | direct-ref branch, unconditional wait_for_condition, trial_counter auto-create |
| `~/pi-mirror/autopilot/autopilot/utils/Tracker.py` | VERIFIED | Trial_Tracker.increment() dispatches INC_TRIAL_COUNTER |

### Key Link Verification

| From | To | Via | Status | Details |
|------|----|-----|--------|---------|
| GET /api/hardware-modules/{id}/methods | ActionEditor | fetchMethods() + METHOD_CACHE | VERIFIED | `ActionEditor.tsx:165-173` |
| GET /api/task-definitions | UI | validation_status in response | VERIFIED | `toolkits.py:527-528` |
| PUT /api/hardware-libs/{id} | task_definitions.validation_status | _flag_broken_task_defs | VERIFIED | `hardware_libs.py:355-363` |
| PUT /api/toolkits/{id} | task_definitions.validation_status | _flag_broken_defs_for_toolkit | VERIFIED | `toolkits.py:474-496` |
| PUT /api/task-definitions/{id} | validation_status | _validate_task_definition(defn_id) | VERIFIED | `toolkits.py:780` |
| POST task-definitions | TaskDefinitionHwLibPin rows | stable_version_id or active_version_id | VERIFIED | `toolkits.py:597-617` |
| PUT /hw-lib-pins/{lib_id} | task_definitions.validation_status | _revalidate_task_def after commit | VERIFIED | `hardware_libs.py:773` |
| DELETE /hw-lib-pins/{lib_id} | task_definitions.validation_status | _revalidate_task_def after delete | VERIFIED | `hardware_libs.py:810` |
| _validate_task_definition | pinned version AST | TaskDefinitionHwLibPin → HardwareLibVersion.ast_metadata | VERIFIED | `toolkits.py:700-709` |

### Requirements Coverage

| Requirement | Source Plan | Description | Status | Evidence |
|-------------|-------------|-------------|--------|----------|
| HW-17 | 12-01, 12-02, 12-03 | StateBodyPanel hardware module picker; methods from GET /api/hardware-modules/{id}/methods; arg inputs with type annotations | SATISFIED | ActionEditor.tsx full hw module picker with METHOD_CACHE, auto-inject args |
| HW-18 | 12-02 | PUT /api/hardware-libs/{id}: re-extracts AST, diffs methods, scans task_definitions, sets validation_status='broken' | SATISFIED | hardware_libs.py:335-363 |
| HW-19 | 12-02 | task_definitions gains validation_status TEXT DEFAULT 'ok' and validation_message TEXT | SATISFIED | models.py:527-528 + db.py migration |
| HW-20 | 12-01, 12-02 | Warning badge on broken definitions; red banner in TaskEditor | SATISFIED | TaskDefinitions.tsx:329-339, TaskEditor.tsx:422-429 |
| HW-21 | 12-04 (mislabeled) | REQUIREMENTS.md: POST /api/task-definitions/{id}/validate-for-pilot/{pilot_id} — Phase 13 endpoint. Plan 12-04 implements initial state selection instead. | MISLABELED | Plan 12-04 feature is implemented and correct for Phase 12. Actual HW-21 (validate-for-pilot) is correctly deferred to Phase 13. |

**Orphaned requirement:** HW-21 is claimed by Plan 12-04 frontmatter but per REQUIREMENTS.md it is a Phase 13 feature. The initial state selection feature Plan 12-04 actually implements has no HW-xx requirement ID. Traceability gap only.

### Anti-Patterns Found

| File | Issue | Severity | Impact |
|------|-------|----------|--------|
| `api/routers/hardware_libs.py` | 819+ lines — exceeds 500-line hard limit | Warning | Pre-existing; _revalidate_task_def added ~20 lines; deferred refactor |
| `api/routers/toolkits.py` | 861+ lines — exceeds 500-line hard limit | Warning | Pre-existing; auto-pin block added ~20 lines; deferred refactor |

No TODO/FIXME/placeholder comments in any Phase 12 files. No stub return patterns. No empty implementations.

### Human Verification Required

#### 1. Method dropdown populates on Add Action

**Test:** Open task editor for a backend-authored toolkit, click Add Action in the state body panel
**Expected:** Method dropdown shows AST methods for first hardware module immediately — no manual re-selection needed
**Why human:** First-render timing of hwModules + addAction depends on React render order; requires live browser

#### 2. Bool arg auto-inject on page reload

**Test:** Create a flag action with Boolean_Tracker and 'set' method, save, reload page
**Expected:** Bool select shows 'false' (not blank) after reload — useEffect fires and injects false as default arg for empty args[]
**Why human:** useEffect([action.method, action.ref, flagMethodNeedsArg]) timing after DB load requires browser testing

#### 3. Auto-pin at task def creation

**Test:** Create a new task definition for a toolkit that has hardware libs; then GET /api/task-definitions/{id}/hw-lib-pins
**Expected:** Response shows pins for all hw libs linked to the toolkit pointing to stable/active version
**Why human:** Requires live API + DB with actual toolkit and hw lib records

#### 4. Initial state context menu

**Test:** Right-click a non-initial state node, select Set as Initial State
**Expected:** INIT badge moves; previous initial loses badge; auto-save fires within 1.5s
**Why human:** ReactFlow context menu behavior requires browser testing

#### 5. Delete hardware module cascade

**Test:** On PilotHardwareConfig page, click Delete on a hardware module that has a config entry
**Expected:** Module itself is deleted (not just its config); list refreshes; no orphan rows in pilot_hardware_config
**Why human:** Behavioral change from deletePilotHardwareConfig to deleteHardwareModule requires UI testing to confirm cascade

### Gaps Summary

**Gap 1 — "group" key plan truth overstated (partial, functionally correct, unchanged from initial verification):**

The plan truth states hardware actions must output `{group:"Modules"}`. The UI never adds this key — `FdaAction` interface has no `group` field and `ActionEditor.tsx` has zero "group" occurrences. The Pi resolves correctly because `mics_task.py:762-764` registers all `hardware["Modules"]` entries into `_semantic_hw` by module name, so `{type, ref, method}` without a group key resolves via the semantic fallback. No code was added to address this in Plans 12-03 through 12-05. Functionally correct but plan truth is inaccurate about the serialization format.

**Gap 2 — HW-21 requirement ID mislabeled in Plan 12-04 (traceability only, unchanged from initial verification):**

Plan 12-04 frontmatter `requirements: [HW-21]` but REQUIREMENTS.md maps HW-21 to Phase 13. Plan 12-04 correctly implements initial state selection — a valid Phase 12 feature with no assigned requirement ID. The validate-for-pilot endpoint (actual HW-21) is correctly deferred to Phase 13. No change to the plan frontmatter was made. No functional impact.

**Plan 12-05 fully verified — all four fixes implemented and wired.** No new gaps introduced.

---

_Verified: 2026-05-24T06:49:04Z_
_Verifier: Claude (gsd-verifier)_
