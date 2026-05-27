---
phase: 12-hardware-fda-builder
plan: "01"
subsystem: ui, api
tags: [toolkits, flags, typescript, fda, action-editor, pi, backward-compat]

requires:
  - phase: 11-toolkit-redesign
    provides: backend-authored toolkit CRUD, EditModal, flags/params schema, hardware_module_ids
  - phase: 10-hardware-libs
    provides: GET /api/hardware-modules/{id}/methods endpoint, HardwareModule type

provides:
  - _normalize_flags() in api/routers/toolkits.py — unified flags shape for all toolkit origins
  - ToolkitFlag TypeScript interface; ToolkitRead.flags typed as Record<string, ToolkitFlag>
  - TaskDefinitionFull.validation_status and validation_message fields
  - Full FDA state builder UI: hardware / trial counter / flag / method / if action types
  - "Add State" button on canvas toolbar — create custom states not pre-defined in toolkit source
  - lib_filename on GET /api/hardware-modules — timer detection by lib filename, not class name
  - Timer modules folded into hardware type — detected by lib_filename=timer.py, no separate type
  - Trial counter as separate action type — Trial_Tracker flags split from regular flags, sky-blue accent
  - Backward compat: legacy toolkits use semantic_hardware dropdown; backend-authored use module picker
  - Broken definition warnings: badge in TaskDefinitions list + red banner in TaskEditor
  - Pi mics_task.py: direct-ref branch for hardware/timer actions and condition operands
  - Pi mics_task.py: GUI-built states unconditionally call wait_for_condition()
  - Pi Tracker.py: Trial_Tracker.increment() dispatches INC_TRIAL_COUNTER to orchestrator

affects:
  - 12-hardware-fda-builder (plan 12-02 adds backend validation columns this UI already renders)
  - 13-prerun-cross-check

tech-stack:
  added: []
  patterns:
    - "Normalize at read time: flags stored in two shapes, normalized to one in _build_toolkit_row"
    - "METHOD_CACHE: module-level JS object caches hardware method fetches within a session"
    - "Direct-ref vs semantic-ref: Pi disambiguates via presence of 'group' key in action/operand"
    - "GUI-built states always block: entry_actions present → unconditional wait_for_condition()"
    - "Timer = hardware subtype: lib_filename=timer.py → fixed start/stop/reset/set methods; serializes as type:timer in FDA"
    - "Trial counter = separate UI type that serializes to type:flag in FDA JSON (Pi compat, no new type)"
    - "hwModules in useEffect deps: fetch re-triggers if modules finish loading after initial render"

key-files:
  created: []
  modified:
    - api/routers/toolkits.py
    - api/routers/hardware_modules.py
    - web_ui/react-src/src/types/index.ts
    - web_ui/react-src/src/pages/toolkits/EditModal.tsx
    - web_ui/react-src/src/components/ActionEditor.tsx
    - web_ui/react-src/src/components/ArgInput.tsx
    - web_ui/react-src/src/components/ConditionBuilder.tsx
    - web_ui/react-src/src/components/StateBodyPanel.tsx
    - web_ui/react-src/src/components/IfActionEditor.tsx
    - web_ui/react-src/src/pages/task-editor/TaskEditor.tsx
    - web_ui/react-src/src/pages/task-definitions/TaskDefinitions.tsx
    - ~/pi-mirror/autopilot/autopilot/tasks/mics_task.py
    - ~/pi-mirror/autopilot/autopilot/utils/Tracker.py

key-decisions:
  - "Normalize flags in _build_toolkit_row (read layer), not in DB migration — avoids touching 95 rows"
  - "ToolkitFlag interface added separately from FlagDefinition (write payload) to keep concerns separate"
  - "Direct-ref format uses 'group' key presence as discriminator — backward compat, no version bump needed"
  - "GUI-built states block unconditionally — 'blocking' field in FDA JSON is ignored for Modes 2 & 3"
  - "Trial_Tracker.increment() dispatches INC_TRIAL_COUNTER (was DATA) — orchestrator now receives trial counts from flag-based actions"
  - "special action type removed from state builder UI; legacy FDA JSONs with special still render a read-only warning chip"
  - "Timer modules not separated from hardware in dropdown — lib_filename suffix '(timer)' labels them; UI type stays 'hardware'"
  - "Trial counter type in UI serializes to type:flag in FDA JSON — no Pi change required; Pi already handles type:flag for Trial_Tracker"
  - "Add State button adds to fdaJson.states + React Flow nodes immediately; no modal needed — inline name input in canvas toolbar"
  - "lib_filename added to hardware-modules API response via JOIN with hardware_libs — avoids class_name heuristics for timer detection"
  - "hwModules added to useEffect deps for method fetch — fixes first-render bug where modules finish loading after ActionEditor mounts"

patterns-established:
  - "_normalize_flags(): HANDSHAKE {type:{class_name}} and backend-authored {tracker_type} both normalize to {tracker_type, initial_value}"
  - "ActionEditor: backward compat switch on toolkit.is_backend_authored before rendering hardware picker"
  - "getParamKeys(): handles both array [{name}] and dict {name:{}} params_schema shapes — shared helper in ArgInput.tsx"
  - "ArgInput: annotationToInputKind() maps Python annotation strings to number/bool/text input kinds"
  - "effectiveUiType(): normalise type:timer → hardware and type:flag+Trial_Tracker → trial for display, store original in FDA"

requirements-completed: [HW-17, HW-18, HW-19, HW-20]

duration: ~2h (across two sessions)
completed: 2026-05-13
---

# Phase 12-01: Full FDA State Builder UI (Hardware + Flag + Param + Conditional)

**Complete FDA entry_action editor: hardware/trial/flag/method/if action types, Add State button, timer folded into hardware, trial counter separated, Pi direct-ref dispatch, unconditional wait_for_condition for GUI states**

## Performance

- **Duration:** ~2h (across two sessions)
- **Completed:** 2026-05-13
- **Files modified:** 13

## Accomplishments

- `_normalize_flags()` added to `api/routers/toolkits.py` — all 95 toolkits return flags as `{flag_name: {tracker_type, initial_value}}` regardless of HANDSHAKE vs backend-authored origin
- `lib_filename` added to `GET /api/hardware-modules` and `GET /api/hardware-modules/{id}` responses via JOIN with `hardware_libs` — reliable timer detection without class name heuristics
- Full FDA action editor in `ActionEditor.tsx` with type redesign:
  - **hardware**: module picker (backend-authored) or semantic dropdown (legacy); timer modules detected by `lib_filename=timer.py` and given fixed start/stop/reset/set methods + duration arg; non-timer modules use AST methods from `/api/hardware-modules/{id}/methods`
  - **trial counter**: separate type (sky-blue accent) — only Trial_Tracker flags; serializes as `type:flag` in FDA JSON for Pi compatibility
  - **flag**: Counter_Tracker / Boolean_Tracker / base Tracker only (Trial_Tracker excluded)
  - **method**: callable method picker or text fallback
  - **if**: nested ConditionBuilder + then/else branches
- Bug fixed: `hwModules` added to `useEffect` deps for method fetch — was silently failing on first render when modules hadn't loaded yet, requiring manual module reselect to trigger the fetch
- Backward compat: legacy toolkits (`is_backend_authored=false`) use semantic_hardware dropdown; backend-authored use module picker from `hardware_module_ids`
- `ArgInput.tsx`: colored mode pills (# Literal / $ Param / ! Flag), `annotationToInputKind()` maps Python annotations to number/bool/text inputs, `getParamKeys()` handles both array and dict params_schema shapes
- `ConditionBuilder.tsx`: uses `getParamKeys()` for param dropdown (was broken for array-shaped params_schema)
- `StateBodyPanel.tsx`: colored type chips per action row, up/down reorder buttons, `hwModules` prop threading
- `IfActionEditor.tsx`: `hwModules` prop added and threaded to nested `ActionEditor`
- `TaskEditor.tsx`: 380px right panel, broken-definition red banner with dismiss, `hwModules` threading, **"+ Add State" button** in canvas toolbar — inline name input, adds state to `fdaJson.states` + React Flow canvas immediately
- `TaskDefinitions.tsx`: warning badge (⚠) on rows with `validation_status === 'broken'`
- Pi `mics_task.py`: direct-ref branch for hardware/timer actions (`"group"` key → `self.hardware[group][ref]`) and for condition operands; GUI-built states now unconditionally call `wait_for_condition()` (removed gate on "blocking" field)
- Pi `Tracker.py`: `Trial_Tracker.increment()` dispatches `key='INC_TRIAL_COUNTER'` instead of `key='DATA'`; base `Tracker` and `Counter_Tracker` are unchanged

## Commits

| Hash | Description |
|------|-------------|
| `26bb2ce` | feat(12-01): normalize flags format in GET /api/toolkits endpoint |
| `1bfa77f` | feat(12-01): update TypeScript types for typed flags and validation fields |
| `f6479a8` | feat(12-01): full action editor — 5 action types, backward compat, UI design system |
| `35b90df` | feat(12-01): broken-def warnings, UI panel width, hwModules threading, getParamKeys fix |
| `47d0514` | fix(12-01): remove unused import + Pi mics_task.py changes |
| `502de80` | docs(12-01): complete full FDA state builder UI plan — steps 0-5 + Pi |
| `20c451d` | feat(12-01): add 'Add State' button to FDA canvas toolbar |
| `83b5b84` | fix(action-editor): bug fixes + action type redesign (timer→hw, trial separate, lib_filename) |

## Files Created/Modified

- `api/routers/toolkits.py` — `_normalize_flags()`, called in `_build_toolkit_row`
- `api/routers/hardware_modules.py` — `lib_filename` in list + get responses (JOIN with hardware_libs); `_module_row()` helper
- `web_ui/react-src/src/types/index.ts` — `ToolkitFlag`, `ToolkitRead.flags`, `TaskDefinitionFull` validation fields, `HardwareModule.lib_filename`
- `web_ui/react-src/src/pages/toolkits/EditModal.tsx` — fixed flags rendering to use `ToolkitFlag`
- `web_ui/react-src/src/components/ActionEditor.tsx` — full rewrite: hardware+timer merged, trial counter separated, METHOD_CACHE, legacy backward compat, hwModules dep bug fix
- `web_ui/react-src/src/components/ArgInput.tsx` — colored mode pills, `annotationToInputKind`, `getParamKeys`
- `web_ui/react-src/src/components/ConditionBuilder.tsx` — `getParamKeys()` for param dropdown
- `web_ui/react-src/src/components/StateBodyPanel.tsx` — `hwModules` prop, colored type chips, reorder buttons
- `web_ui/react-src/src/components/IfActionEditor.tsx` — `hwModules` prop threaded to nested ActionEditor
- `web_ui/react-src/src/pages/task-editor/TaskEditor.tsx` — 380px panel, broken-def banner, `hwModules` threading, "Add State" button
- `web_ui/react-src/src/pages/task-definitions/TaskDefinitions.tsx` — ⚠ badge on broken definitions
- `~/pi-mirror/autopilot/autopilot/tasks/mics_task.py` — direct-ref branch in `_build_action_callable` + `_build_condition_operand`; unconditional `wait_for_condition` in `_build_state_method`
- `~/pi-mirror/autopilot/autopilot/utils/Tracker.py` — `Trial_Tracker.increment()` dispatches `INC_TRIAL_COUNTER`

## Decisions Made

- Normalize flags in read layer (`_build_toolkit_row`) rather than DB migration — no data mutation needed
- `getParamKeys()` as shared helper in ArgInput.tsx — single source of truth for params_schema shape handling
- Direct-ref uses `"group"` key as discriminator between GUI-built and legacy semantic actions — backward compat, no version bump
- GUI-built states always call `wait_for_condition()` — the "blocking" field was misleading; entry_actions present is sufficient signal
- `Trial_Tracker.increment()` dispatches `INC_TRIAL_COUNTER` not `DATA` — orchestrator only processes trial counts via this key
- Timer folded into hardware UI type — serializes as `type:timer` in FDA JSON so Pi handles it without change; `(timer)` suffix in module dropdown labels them
- Trial counter as separate UI action type but serializes to `type:flag` in FDA JSON — Pi already handles `type:flag` for Trial_Tracker, no Pi changes needed
- `lib_filename` added to hardware module API response instead of relying on class name heuristics for timer detection

## Known Pending

- Plan 12-02 (backend validation columns + impact detection) not yet implemented — `validation_status`/`validation_message` always null until 12-02 runs
- Plan 12-03 (FDA builder bug fixes) not yet implemented — see `12-03-PLAN.md`:
  - Bug 1: "Add Action" button doesn't pre-fill module ref → method dropdown stays blank until user manually reselects module
  - Bug 2: `bool` arg stored as `0`/`1` renders blank in select (normalize with `value ? 'true' : 'false'`)
  - Bug 3: Trial counter requires dropdown selection — should be implicit `trial_counter` per toolkit (API + UI + Pi)
  - Bug 4: No auto-save — states added then browser-refreshed are lost

## Pi Deploy Status

Pi files edited in `~/pi-mirror/` and deployed via rsync this session:
- `autopilot/autopilot/tasks/mics_task.py` ✓ deployed
- `autopilot/autopilot/utils/Tracker.py` ✓ deployed

---
*Phase: 12-hardware-fda-builder*
*Completed: 2026-05-13*
