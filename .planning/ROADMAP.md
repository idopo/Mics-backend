# Roadmap: MICS Backend

**Milestone:** M1 — ToolKit + FDA Redesign + Pi Code Editor + Hardware Centralization
**Status:** Phases 9–17 complete. Active scope is **24 → 23 → review → 18**. Phase 25 added 2026-07-27, depends on 24; **agreed 2026-07-27 to run immediately after 24, before 23** — phase 24 deliberately does not derive detector view keys, so transitions on `LICKER2` are unavailable until 25 lands. Phases 1–4 archived, 5–8 deferred.
**Requirements:** 86 v1 requirements across 13 phases

---

## Phase Summary

> **Phases 1–4 are ARCHIVED** (moved to `.planning/archive/` on 2026-07-26). They were
> superseded and re-planned inside phases 9–17; the system is well past them. **Skip them
> when reviewing GSD phases** — they are history, not work.
>
> **Phases 5–8 (Pi Code Editor) are DEFERRED** — never started, not in the current plan.
> Design doc retained at `.claude/docs/pi_code_editor_plan.md`.

| # | Phase | Goal | Requirements | Status |
|---|---|---|---|---|
| 1–4 | *(archived)* | Pi foundation, DB+API, visual editor, protocol integration — superseded by phases 9–17 | — | ▣ Archived |
| 5–8 | *(deferred)* | Pi Code Editor arc — Monaco viewer, terminal, edit+restart, packages | EDIT-01–17 | ◌ Deferred |
| 9 | HardwareLib Storage | hardware_libs DB + API, AST validation, Pi override dir, E2E proof with gpio.py | HW-01–05 | ✓ Complete |
| 10 | Hardware Modules + Pilot Config | hardware_modules + pilot_hardware_config DB + API + UI, prefs.json migration seeder | HW-06–11 | ✓ Complete |
| 11 | 6/6 | Complete    | 2026-05-14 | ✓ Complete 2026-05-04 |
| 12 | 5/5 | Complete   | 2026-05-24 | ○ Pending |
| 13 | 1/1 | Complete   | 2026-05-28 | ○ Pending |
| 14 | 3/3 | Complete   | 2026-05-28 | ✓ Complete 2026-05-27 |
| 15 | Compound Transition Conditions | ConditionGroup DNF types, normaliseTransition migration, ConditionGroupsEditor UI, Pi DNF evaluator | COND-01–05 | ✓ Complete 2026-05-27 |
| 16 | 3/3 | Complete    | 2026-05-27 | ○ Pending |
| 17 | Free-Form Pilot Hardware Config | Name-keyed pilot_hardware_config CRUD + free-form React table + HardwareCheckModal fix | HW-08, HW-11 | ✓ Complete 2026-05-29 |
| 18 | MICS-Link: Pi Transport + ExternalHardware | ZMQ ROUTER socket on Pi IOLoop + ExternalHardware base class with @signal/@event/@command + View Tracker auto-registration + stale policy + smoke test | EXTLINK-01–11 | ○ Pending |
| 23 | Compute Primitives + Variables | FDA-JSON-v2 `variables` registry → Trackers in flags+view; `compute` entry-action + curated stdlib primitives (last-write-wins, hot-reload); backend variables/collision validation + compute-library storage via Phase-9 hw-lib infra; GUI compute state-builder + transition operand wiring. 3 plans. (expr escape-hatch decoupled/deferred) | CMP-01–06, CMP-10–15 | ○ Pending |
| 24 | Trigger Assignment Action Lists | Triggers run the same action vocabulary as state `entry_actions` (+ new `view` action, return-value capture, `{trigger: level/tick}` args); backend validation for `trigger_assignments`; on a **sourceless** toolkit a constrained one-pick detector write drives the licker trackers with no way to cross pin and tracker; `trigger_name` picked from the toolkit's trigger-capable hardware | TRIGA-01–10, 11a, 12, 14–19 | ✓ **8/8 plans executed 2026-07-27** — rig-proven (runs 478/480/481: 144 triggers, 63 licker writes, 0 correctness errors); 8/8 save-time negative cases 422. ⚠ Pi test suite still never run (user-run) |
| 25 | Detector-Derived View Keys | `LICKER*` keys derived by the backend, offered in the FDA editor's view-operand and `key_template` pickers, resolved per-pilot in Phase 13 preflight. **Absorbs TRIGA-13.** **DVK-09 added from rig evidence** — channels must be declarable, not assumed 0-based (a live spout is currently discarded); resolved 2026-07-29 to `first_channel` + count, no channel list. **DVK-11 added 2026-07-29** — operands store a detector ref + channel index, never the resolved per-pilot key. **DVK-10 added 2026-07-29** — `execute_trigger`'s over-broad `except KeyError` swallowed that discard as `"No valid trigger"`. Transitions on a licker key are unavailable until this lands | DVK-01–11 | ◐ **3/6 plans executed 2026-07-29** — plan 01 landed the backend derivation core (DVK-01/02/07/09/11); plan 02 landed the Pi runtime half (DVK-09/10/11: `first_channel` in `check_for_detectors`, `execute_trigger` error containment, `view_detector` build-time resolution); plan 03 wired preflight resolution (DVK-06/11: out-of-range channel / unreachable literal key / unresolvable `{device_name}` template all fail preflight with the pilot's actual wiring) and `detector_channels` onto every toolkit read route including `by-name` |

**Execution order (amended 2026-07-27):** Phase 24 → **Phase 25** → Phase 23 → review → Phase 18 → Open Ephys. Phase 25 moved ahead of 23 because phase 24 deliberately does not derive detector view keys for the editor. See `.planning/STABILIZATION_PLAN.md`.

---

## Phase Details

### Phase 1: Pi Foundation

**▣ ARCHIVED 2026-07-26** — superseded and re-planned inside phases 9–17. Docs moved to `.planning/archive/`. Skip when reviewing GSD phases.
**Goal:** Pi can load and hot-reload a complete FDA state machine from JSON without restart

**Requirements:** FDA-01 through FDA-17, TRIG-01 through TRIG-05, HOT-02

**Success criteria:**
1. `AppetitiveTaskReal` started with `state_machine=<v2_json>` produces identical CONTINUOUS event stream in ES as hardcoded version
2. `validate_fda.py AppetitiveTaskReal fda.json` exits 0 on valid JSON, exits 1 with specific error on unknown state name / unknown ref / unknown param / unknown callable_method
3. Toolkit has `SEMANTIC_HARDWARE_RENAMES = {"old_name": "new_name"}`; FDA JSON with `"ref": "old_name"` runs without error; `validate_fda.py` emits deprecation warning not error
4. `validate_fda.py rename-hw-ref old_name new_name --toolkit AppetitiveTaskReal` prints "Updated N task_definitions" and exits 0; DB rows confirmed via postgres MCP
5. Touch detector `TOUCH_INT` wired via `trigger_assignments` with `touch_detector` handler → `view[LICKER{n}]` updated correctly; `Hardware_Event` still dispatched for all GPIO edges
6. `tools/deploy_pi.sh` rsyncs autopilot/ to Pi and restarts pilot process; exit 0

**Pi files changed:**
- `autopilot/autopilot/tasks/mics_task.py` — `load_fda_from_json`, `apply_trigger_assignments`, `_build_state_method`, `_resolve_arg`, `_build_transition_lambda`
- `autopilot/autopilot/core/pilot.py` — enriched HANDSHAKE payload (FLAGS, SEMANTIC_HARDWARE, SEMANTIC_HARDWARE_RENAMES, STAGE_NAMES, CALLABLE_METHODS, REQUIRED_PACKAGES)

**New files:**
- `tools/validate_fda.py` (includes `rename-hw-ref` subcommand)
- `tools/sync_pi.sh`, `tools/deploy_pi.sh`

**Dependencies:** None — can start today

---

### Phase 2: DB + API

**▣ ARCHIVED 2026-07-26** — superseded and re-planned inside phases 9–17. Docs moved to `.planning/archive/`. Skip when reviewing GSD phases.
**Goal:** Toolkit metadata stored from HANDSHAKE; task definitions created/edited/pushed via REST API

**Requirements:** DB-01 through DB-08, VAR-01 through VAR-05

**Plans:** 4/4 plans complete

Plans:
- [ ] 02-01-PLAN.md — DB schema: task_toolkits, toolkit_pilot_origins, task_definitions extensions
- [ ] 02-02-PLAN.md — HANDSHAKE processor: upsert toolkit metadata on enriched HANDSHAKE
- [ ] 02-03-PLAN.md — Toolkit + TaskDefinition CRUD API endpoints
- [ ] 02-04-PLAN.md — Push-to-pilot (UPDATE_FDA) and state_machine injection in START payload

**Success criteria:**
1. After Pi reconnects, `GET /api/toolkits` returns toolkit with states, flags, params_schema, semantic_hardware, required_packages — verified via postgres MCP
2. `POST /api/task-definitions` creates a record with fda_json; `GET /api/task-definitions/:id` returns it; round-trip confirms JSON integrity
3. `POST /api/task-definitions/:id/push?pilot=T` → orchestrator logs show `UPDATE_FDA` sent to Pi; Pi logs show `HOT_RELOAD_ACK`; confirmed via docker MCP
4. Session start with a task-definition-backed protocol step → orchestrator logs show `state_machine` key in START payload

**Files changed:**
- `api/models.py` — `TaskToolkit` SQLAlchemy model
- `api/db.py` — migration for task_definitions new columns
- `api/main.py` — 7 new endpoints
- `orchestrator/orchestrator/orchestrator_station.py` — HANDSHAKE writes to task_toolkits; `_build_step_task()` includes fda_json; `push_hot_reload()`
- `orchestrator/orchestrator/api.py` — `POST /push-fda` endpoint

**Dependencies:** Phase 1 (FLAGS in HANDSHAKE payload)

---

### Phase 3: Visual FDA Editor

**▣ ARCHIVED 2026-07-26** — superseded and re-planned inside phases 9–17. Docs moved to `.planning/archive/`. Skip when reviewing GSD phases.
**Goal:** Non-technical researchers can build task state machines visually in the browser

**Requirements:** UI-01 through UI-07, UI-05a, UI-10, UI-11, UI-12, VAR-06 (UI-08 removed, UI-09 deferred)

**Plans:** 5 plans (00–04)

Plans:
- [x] 03-00-PLAN.md — Pi: unified condition eval, SEMANTIC_HARDWARE fallback, elastic_test guard
- [x] 03-01-PLAN.md — Foundation: npm dep, types, API helpers, routing, nav link, task definitions list page (VAR-06)
- [x] 03-02-PLAN.md — FDA Canvas: react-flow canvas with StateNode, ConditionBuilder, drag-connect
- [ ] 03-03-PLAN.md — Toolkits page: list toolkits, "New Task Definition" creation flow, route + nav
- [ ] 03-04-PLAN.md — State body editing: TriggerAssignmentPanel, IfActionEditor, wire panels, Save button

**Success criteria:**
1. Open `/react/toolkits-ui` → all registered toolkits listed; "New Task Definition" button creates record and navigates to editor
2. Open `/react/task-editor/:id` → canvas shows nodes and edges matching stored fda_json; no console errors
3. Click edge → right panel shows ConditionBuilder with condition fields pre-filled; edits update local state
4. Click state node → state body panel shows entry_actions → add a hardware action with param-ref arg → save → fda_json includes new action with `{"param": "..."}` form
5. Passthrough states (no entry_actions, backed by Python method) show lock icon and `{py}` badge; body panel is read-only
6. TriggerAssignmentPanel shows when nothing selected; add trigger → save → persists on reload
7. Save button calls PUT /api/task-definitions/:id; "Saved ✓" shown for 2 seconds on success

**New files:**
- `web_ui/react-src/src/pages/task-definitions/TaskDefinitions.tsx`
- `web_ui/react-src/src/pages/task-editor/TaskEditor.tsx`
- `web_ui/react-src/src/pages/toolkits/Toolkits.tsx`
- `web_ui/react-src/src/components/StateNode.tsx`
- `web_ui/react-src/src/components/ConditionBuilder.tsx`
- `web_ui/react-src/src/components/StateBodyPanel.tsx`
- `web_ui/react-src/src/components/ActionEditor.tsx`
- `web_ui/react-src/src/components/ArgInput.tsx`
- `web_ui/react-src/src/components/TriggerAssignmentPanel.tsx`
- `web_ui/react-src/src/components/IfActionEditor.tsx`
- `web_ui/react-src/src/api/toolkits.ts`
- `web_ui/react-src/src/api/task-definitions.ts`

**npm additions:** `@xyflow/react`

**Dependencies:** Phase 2 (toolkits and task-definitions API)

---

### Phase 4: Protocol Integration

**▣ ARCHIVED 2026-07-26** — superseded and re-planned inside phases 9–17. Docs moved to `.planning/archive/`. Skip when reviewing GSD phases.
**Goal:** Protocol steps reference task definitions; FDA JSON flows end-to-end from DB to Pi

**Requirements:** PROTO-01 through PROTO-04, VAR-07

**Success criteria:**
1. Open `/react/protocols-create` → task palette shows named task definitions, not raw task_type strings
2. Create protocol with a task-definition step → start session → orchestrator logs show `state_machine` key in START; Pi runs JSON-driven FDA
3. `GET /api/tasks/leaf` deprecated; `GET /api/task-definitions` returns equivalent data; no 404s on existing protocol UI flows

**Plans:** 3/3 plans complete

Plans:
- [x] 04-01-PLAN.md — DB migration + API: task_definition_id FK column, model extension, round-trip
- [ ] 04-02-PLAN.md — Frontend: protocols-create palette swap + overrides modal toolkit params
- [ ] 04-03-PLAN.md — Orchestrator FDA injection: fix step field lookup + VAR-07 canonical variant

**Files changed:**
- `web_ui/react-src/src/pages/protocols-create/ProtocolsCreate.tsx`
- `web_ui/react-src/src/pages/pilot-sessions/OverridesModal.tsx`
- `api/models.py` — `ProtocolStepTemplate.task_definition_id` field; TaskToolkit.is_canonical; TaskDefinition.needs_migration
- `api/db.py` — run_canonical_migrations()
- `api/routers/toolkits.py` — PATCH /toolkits/{id}/set-canonical
- `orchestrator/orchestrator/orchestrator_station.py` — fix task_definition_id lookup in _build_step_task/_build_first_step_task

**Dependencies:** Phase 3 (task definitions exist in DB with valid fda_json)

---

### Phase 5: Pi Editor — Viewer

**◌ DEFERRED** — never started, not in the current plan. Design doc: `.claude/docs/pi_code_editor_plan.md`.
**Goal:** Any lab member can browse Pi task source files in the browser without SSH access

**Requirements:** EDIT-01 through EDIT-06

**Success criteria:**
1. `GET /api/pi/status` returns `{"connected": true}` when Pi is reachable; returns within 2s
2. `GET /api/pi/files?path=<autopilot/tasks/>` returns file list; `__pycache__` entries absent
3. `GET /api/pi/file?path=<outside_root>` returns 403
4. Open `/react/pi-editor` → file tree loads for autopilot/tasks/ and pilot/plugins/ → click `mics_task.py` → Monaco shows Python content with syntax highlighting; read-only; no console errors
5. `@monaco-editor/react` loads lazily (React.lazy); does not affect initial bundle load time for other pages

**New files:**
- `web_ui/pi_ssh.py`
- `web_ui/react-src/src/pages/pi-editor/index.tsx`
- `web_ui/react-src/src/components/PiFileBrowser.tsx`
- `web_ui/react-src/src/components/MonacoEditorPanel.tsx`
- `web_ui/react-src/src/components/PiStatusBar.tsx`

**Dependencies:** None — safe to deploy in production immediately (read-only, no exec risk)

---

### Phase 6: Pi Editor — Terminal

**◌ DEFERRED** — never started, not in the current plan. Design doc: `.claude/docs/pi_code_editor_plan.md`.
**Goal:** Developers can run commands on the Pi from the browser terminal

**Requirements:** EDIT-07 through EDIT-10

**Success criteria:**
1. With `ALLOW_PI_EXEC=false` (default): `POST /api/pi/exec` returns 403; terminal shows "Developer mode not enabled"
2. With `ALLOW_PI_EXEC=true`: type `!pip list` in terminal → output streams in real-time via xterm.js; exit code shown on completion
3. Disconnect Pi mid-command → WebSocket closes gracefully; terminal shows disconnect message
4. `!tail -100 ~/Apps/mice_interactive_home_cage/logs/pilot.log` → log lines stream correctly; ANSI colors rendered

**New files:**
- `web_ui/react-src/src/components/PiTerminal.tsx`

**Dependencies:** Phase 5 (pi_ssh.py module, page scaffold)

---

### Phase 7: Pi Editor — Edit + Restart

**◌ DEFERRED** — never started, not in the current plan. Design doc: `.claude/docs/pi_code_editor_plan.md`.
**Goal:** Developers can edit toolkit Python files and restart the pilot without SSH

**Requirements:** EDIT-11 through EDIT-14

**Success criteria:**
1. Click "Edit" → Monaco switches to editable; dirty indicator appears on change
2. Edit `mics_task.py` → "Save" → `PUT /api/pi/file` → SSH SFTP writes file → `cat <file>` on Pi shows change
3. "Restart Pilot" → pilot process restarts → orchestrator receives new HANDSHAKE within 10s → task_toolkits updated
4. Navigate away from dirty editor → browser shows unsaved changes confirm dialog
5. `PUT /api/pi/file` with path outside PI_EDITOR_ROOTS → 403

**Dependencies:** Phase 6 (terminal for viewing restart output, ALLOW_PI_EXEC gate established)

---

### Phase 8: Pi Editor — Sync + Packages

**◌ DEFERRED** — never started, not in the current plan. Design doc: `.claude/docs/pi_code_editor_plan.md`.
**Goal:** Developers can sync code and manage Pi dependencies from the browser

**Requirements:** EDIT-15 through EDIT-17

**Success criteria:**
1. `GET /api/pi/packages` returns list with `installed: true/false` for each package in task_toolkits.required_packages
2. Missing package shown in UI → "Install Missing Packages" → `POST /api/pi/packages` → pip output streams in terminal → package appears as installed on next GET
3. `POST /api/pi/sync` triggers rsync; output streams; completes with exit code 0

**Dependencies:** Phase 7 (exec infrastructure) + Phase 2 (task_toolkits.required_packages)

---

### Phase 9: HardwareLib Storage + End-to-End Proof
**Goal:** Backend can store, validate, and serve hardware driver files. Pi receives them on task START, writes to override dir, and imports them. Does not break any running tasks.

**Requirements:** HW-01 through HW-05

**Success criteria:**
1. `POST /api/hardware-libs` with gpio.py source → 200 + AST metadata in response (classes: Digital_Out, Solenoid, Pulse20Hz... with methods and args)
2. `POST /api/hardware-libs` with intentionally broken Python → 422 with line number in error
3. Start a test task on connected Pi → verify `~/apps/hardware_overrides/gpio.py` exists on Pi after START
4. Existing tasks on Pi still run without change (backward compat: no lib override sent = Pi uses autopilot package)

**New files:**
- `api/routers/hardware_libs.py`

**Files changed:**
- `api/main.py` (register new router)
- `orchestrator/orchestrator/orchestrator_station.py` (LOAD_HARDWARE_LIBS before START)
- `orchestrator/orchestrator/main.py` (handler key mapping)
- `~/pi-mirror/autopilot/autopilot/tasks/mics_task.py` (receive_hardware_libs)

**Dependencies:** Independent — can start after Phase 4

---

### Phase 10: Hardware Modules + Pilot Hardware Config
**Goal:** Global HardwareModule records exist in DB and UI. Per-pilot hardware config (pin bindings) stored in backend. prefs.json HARDWARE section migrated via HANDSHAKE seeder.

**Requirements:** HW-06 through HW-11

**Success criteria:**
1. Create a hardware module `Left_LED → gpio.Digital_Out` via API → validated that `Digital_Out` exists in gpio.py AST
2. `PUT /api/pilots/{id}/hardware-config/{module_id}` with `{pin: 7, polarity: 1}` → `GET /api/pilots/{id}/hardware-config` returns correct binding
3. Boot Pi → HANDSHAKE → pilot_hardware_config seeded from prefs.json HARDWARE section (one-time)
4. `/react/hardware-modules-ui` shows module list + create form; class dropdown populated from AST metadata
5. Pilot hardware config editor shows modules with editable config fields derived from class constructor args

**New files:**
- `api/routers/hardware_modules.py`
- `api/routers/pilot_hardware_config.py`
- `web_ui/react-src/src/pages/hardware-modules/HardwareModules.tsx`

**Files changed:**
- `api/main.py` (register new routers)
- `orchestrator/orchestrator/orchestrator_station.py` (HANDSHAKE: config seeder)

**Dependencies:** Phase 9 (hardware_libs must exist for class validation)

---

### Phase 11: Toolkit Redesign (Backend-Authored)
**Goal:** Toolkits are now fully backend-defined. HANDSHAKE populates available_locked_states per task file. User assembles a toolkit from locked states + hardware modules + flags + params via a 5-step UI.

**Requirements:** HW-12 through HW-16

**Success criteria:**
1. Boot Pi → HANDSHAKE → `GET /api/locked-states` returns state names for that task file
2. Create backend-authored toolkit in UI: pick states + modules + flags + params → `GET /api/toolkits` shows `is_backend_authored: true`
3. Existing HANDSHAKE-auto-registered toolkits still appear and work; show "legacy" badge in UI
4. `POST /api/toolkits` with unknown state name → 422 (validation: state must be in available_locked_states)
5. `POST /api/toolkits` with unknown hardware_module_id → 422

**New files:**
- `web_ui/react-src/src/pages/toolkits/ToolkitsRedesign.tsx` (or extend Toolkits.tsx)

**Files changed:**
- `api/routers/toolkits.py` (extend with authoring endpoints)
- `api/models.py` (task_toolkits extension, available_locked_states table)
- `orchestrator/orchestrator/orchestrator_station.py` (HANDSHAKE: populate available_locked_states, accept new format)

**Dependencies:** Phase 10 (hardware modules must exist for toolkit assembly)

---

### Phase 12: Hardware-Aware FDA State Builder
**Goal:** FDA state builder knows hardware module methods via AST. Entry actions can pick a hardware module → method → args with type hints. Lib-change impact detection flags broken task definitions.

**Requirements:** HW-17 through HW-20

**Success criteria:**
1. In task editor, add a hardware entry action → dropdown shows modules from toolkit's hardware_module_ids
2. Select a module → method dropdown shows methods from that module's AST (via `GET /api/hardware-modules/{id}/methods`)
3. Select a method → arg inputs appear with type annotations and defaults pre-filled
4. Update gpio.py source (remove a method) → affected task definitions gain `validation_status: 'broken'`
5. TaskDefinitions list shows warning badge on broken definitions; TaskEditor shows banner listing broken state + method

**Files changed:**
- `api/routers/hardware_libs.py` (lib-update: AST diff + task definition validation)
- `web_ui/react-src/src/pages/task-editor/TaskEditor.tsx` (hardware method picker in StateBodyPanel)
- `web_ui/react-src/src/pages/task-definitions/TaskDefinitions.tsx` (broken badge)

**Dependencies:** Phase 11 (toolkits have hardware_module_ids; modules have AST-linked libs)

---

### Phase 13: Pre-Run Cross-Check + End-to-End
**Goal:** Before starting a task, backend verifies pilot has all required hardware configured. Full end-to-end: toolkit authoring → task definition → start → Pi receives libs + config → runs using override hardware.

**Requirements:** HW-21 through HW-24

**Success criteria:**
1. `POST /api/task-definitions/{id}/validate-for-pilot/{pilot_id}` with pilot missing required module → returns `{ok: false, issues: [{module_name, issue: 'missing', ...}]}`
2. Session start UI with missing hardware → modal blocks with issue list and link to pilot hardware config editor
3. Full end-to-end: backend-authored toolkit → task definition → start on pilot → Pi logs show `hardware_overrides/gpio.py` written, hardware instances created from received config → task runs
4. Pilot with no backend hardware config → falls back to `self.HARDWARE` class constant; no crash; backward compat confirmed
5. HANDSHAKE from a backend-authored toolkit → orchestrator overwrites `task_definitions.default_params` with the toolkit's `params_schema` instead of the Pi-sent PARAMS dict → protocol builder UI shows backend-defined params without requiring Pi-side `PARAMS` declaration
   - **Until this is implemented:** Pi-side `PARAMS` class declaration must not be removed from backend-authored tasks — removing it causes `task_definitions` to register empty params, breaking protocol step configuration in the UI
   - Legacy (non-backend-authored) toolkits: HANDSHAKE registration unchanged (Pi PARAMS used as-is)

**Files changed:**
- `api/routers/toolkits.py` (validate-for-pilot endpoint)
- `web_ui/react-src/src/pages/subject-sessions/SubjectSessions.tsx` (pre-run check gate)
- `orchestrator/orchestrator/orchestrator_station.py` (START handler: send hardware config dict to Pi; HANDSHAKE processor: override task_definitions.default_params from toolkit params_schema when is_backend_authored)
- `~/pi-mirror/autopilot/autopilot/tasks/mics_task.py` (dynamic init_hardware from received_hw_config)

**Dependencies:** Phase 12 (task definitions have validation_status; hardware modules fully wired)

---

### Phase 16: Recursive Condition Tree (Kibana-Style)
**Goal:** Replace flat DNF `condition_groups` with a recursive `condition_tree` model that supports arbitrary AND/OR nesting. Per-row +AND/+OR buttons (Kibana FiltersBuilder model), depth-based background shading for visual nesting, backward-compat migration of existing `condition_groups` and `conditions[]` data, parenthesized edge label rendering, and Pi recursive lambda evaluator.

**Requirements:** COND-06, COND-07, COND-08, COND-09, COND-10

**Plans:** 1/1 plans complete

Plans:
- [ ] 16-01-PLAN.md — Types (ConditionNode, FdaTransition.condition_tree) + ConditionGroupsEditor rewrite as recursive tree editor
- [ ] 16-02-PLAN.md — TaskEditor.tsx: normaliseTransition migration, condLabel with parens, updateTransitionTree wiring
- [ ] 16-03-PLAN.md — Pi: _build_tree_lambda recursive evaluator + three-way fallback chain

**Success criteria:**
1. Clicking +AND at a row adds a sibling within the AND-context; +OR adds a sibling at the OR level — matching Kibana FiltersBuilder
2. `(A OR B) AND C` is expressible, stored as `condition_tree`, and evaluated correctly on Pi
3. Edge label renders `(A ∨ B) ∧ C` with parentheses when OR is nested inside AND
4. Opening a task def with legacy `condition_groups` auto-migrates to `condition_tree` on load; re-save writes `condition_tree`
5. `IfActionEditor` (single `ConditionBuilder` row) is unaffected

**Files to change:**
- `web_ui/react-src/src/types/index.ts` (ConditionNode type; FdaTransition.condition_tree field)
- `web_ui/react-src/src/pages/task-editor/TaskEditor.tsx` (normaliseTransition migration, condLabel with parens, updateTransitionTree)
- `web_ui/react-src/src/components/ConditionGroupsEditor.tsx` (replace with ConditionTreeEditor or rewrite in-place)
- `~/pi-mirror/autopilot/autopilot/tasks/mics_task.py` (_build_tree_lambda + updated transition registration)

**Dependencies:** Phase 15 (condition_groups types + updateTransitionGroups + ConditionGroupsEditor exist — this phase supersedes them)

---

### Phase 17: Free-Form Pilot Hardware Config
**Goal:** Decouple `pilot_hardware_config` from the `hardware_modules` FK. Make pilot hardware config a free-form named dict that mirrors the Pi's `prefs.json` HARDWARE section. Full CRUD: add/remove/rename entries by name, edit params via JSON textarea, optional module registry picker to pre-fill defaults (class_name + __init__ params). Preflight check (Phase 13) becomes the sole alignment mechanism — no FK link required.

**Requirements:** HW-08 (update), HW-11 (update)

**Plans:** 2/2 plans complete

Plans:
- [ ] 17-01-PLAN.md — DB migration + model update + name-keyed API router rewrite
- [ ] 17-02-PLAN.md — Dispatch/preflight SQL fix + cascade delete removal + frontend (types, API client, HardwareCheckModal, React page)

**Success criteria:**
1. `pilot_hardware_config` rows are identified by `(pilot_id, name)` — no FK to `hardware_modules`
2. Adding an entry with a free-form name (not in module registry) works; name is the only identity key
3. Module registry picker pre-fills class_name + default params but does not create a persistent link
4. Renaming = delete + re-add (name is identity); confirmed in UI
5. Preflight check (Phase 13 `/preflight-validate`) uses `name` matching, not `hardware_module_id`
6. `HardwareCheckModal` inline-fix writes to the new name-keyed endpoint without stripping class_name
7. Deleting a hardware module does NOT cascade-delete pilot hardware configs

**Files to change:**
- `api/db.py` (migration: add name col, backfill, drop old FK constraint, add uq_pilot_hw_config_pilot_name)
- `api/models.py` (PilotHardwareConfig: name col, hardware_module_id nullable, swap UNIQUE constraint)
- `api/routers/pilot_hardware_config.py` (rewrite: name-keyed PUT/DELETE, GET returns name, seed stores class_name)
- `api/routers/toolkit_dispatch.py` (get_dispatch_spec + preflight_validate: WHERE name=:name instead of hardware_module_id)
- `api/routers/hardware_modules.py` (remove cascade-delete of pilot configs on module delete)
- `web_ui/react-src/src/types/index.ts` (PilotHardwareConfigRow: hardware_module_id → name)
- `web_ui/react-src/src/api/hardware_modules.ts` (upsertPilotHardwareConfig + deletePilotHardwareConfig: name-keyed URLs)
- `web_ui/react-src/src/components/HardwareCheckModal.tsx` (name-keyed PUT URL; do NOT strip class_name)
- `web_ui/react-src/src/pages/hardware-modules/PilotHardwareConfig.tsx` (rewrite: free-form CRUD table + add entry form with optional module picker)

**Dependencies:** Phase 13 (pilot_hardware_config schema exists; preflight-validate endpoint live)

---

### Phase 18: MICS-Link — Pi Transport + ExternalHardware
**Goal:** Pi gains a structured, crash-safe input channel that lets external software (DeepLabCut, OpenEphys, photometry, …) push data into the existing View / FDA framework. Author writes one `ExternalHardware` subclass with `@signal` / `@event` / `@command` decorators and uploads it as a regular hardware library (Phase 9). It is registered as a hardware module (Phase 10), its per-pilot network config (`{class_name, listen_port, source_id, stale_ms}`) lives in `pilot_hardware_config.config` (Phase 17 — free-form, no schema change), selected by a toolkit (Phase 11), dispatched on the existing `HARDWARE` + `PREFS_HARDWARE` channel (Phase 11), preflight-validated (Phase 13). On the Pi, each instance binds its own ROUTER on its `listen_port` and accepts only the configured `source_id` DEALER identity. FDA transitions read external data via the same `view.get_value(...)` API used for GPIO/I2C — zero new call sites, zero new dispatch shapes.

**Requirements:** EXTLINK-01 through EXTLINK-11

**Plans:** 2/2 plans

Plans:
- [ ] 18-01-PLAN.md — `external_hardware.py` only: `ExternalHardware` base class + `@signal` / `@event` / `@command` decorators + per-instance ROUTER socket helper (private composition) + View Tracker auto-registration + stale-policy reads + heartbeat-driven liveness
- [ ] 18-02-PLAN.md — Small AST extractor extension in `api/routers/hardware_libs.py` so the three decorators land in `ast_metadata` (Phase 9 plumbing extended; same upload, same `/hardware-libs` API) + `mics_task.init_hardware()` post-pass that calls `hw.bind(ioloop, view)` on `ExternalHardware` instances + standalone smoke-test DEALER script

**Success criteria:**
1. A standalone DEALER script (`~/pi-mirror/scripts/dev/extlink_smoke.py`) connects to the per-instance `listen_port` with the configured `source_id`, pushes `dlc_cam1.left_paw_x = 0.7`, and an FDA transition gated on `view.get_value("dlc_cam1.left_paw_x") > 0.5` fires within 50 ms.
2. `<source_id>.alive` flips false on the Pi within `stale_ms` (from per-pilot config) after the SDK stops sending heartbeats; flip emits a CONTINUOUS event visible in ES.
3. Per-signal stale policy probe: stop pushing a `return_default` signal; `view.get_value(...)` returns the declared default after `stale_after_ms`.
4. Two `ExternalHardware` subclasses uploaded as hardware libs, each registered as a `hardware_module`, each given its own `pilot_hardware_config` row with a distinct `listen_port`, and both used in one toolkit on one task — both Trackers visible in View, two ROUTER sockets up, no cross-talk.
5. A malformed inbound message (unknown signal name, bad MessagePack) is dropped + logged; pilot keeps running; no traceback in pilot logs.
6. `pilot.py` LOAD_HARDWARE_LIBS path (unchanged from Phase 9) accepts an `ExternalHardware` subclass; instantiation happens through the standard hw_libs → hw_modules → toolkit-dispatch path with NO new Pi-side ingress.
7. AST extractor (`api/routers/hardware_libs.py`) emits the declared signal/event/command metadata so the UI (Phase 19+) can render the per-source schema; no schema change to any DB table.

**Files to change:**
- `mics-backend/api/routers/hardware_libs.py` (extend — AST extractor recognises `@signal` / `@event` / `@command`; metadata flows through the existing `ast_metadata` field)
- `~/pi-mirror/autopilot/autopilot/hardware/external_hardware.py` (new — base class, decorators, private `_ExternalSocket` helper for ROUTER + codec + heartbeat, View Tracker auto-registration, stale policy)
- `~/pi-mirror/autopilot/autopilot/tasks/mics_task.py` (extend — `init_hardware()` post-pass: after `super().init_hardware()`, walk `self.hardware`, for any `ExternalHardware` instance call `hw.bind(ioloop=self._task_ioloop, view=self.view)`)
- `~/pi-mirror/scripts/dev/extlink_smoke.py` (new — standalone DEALER smoke test runnable from the dev machine; takes `--listen-port` and `--source-id`)

**NOT in scope (left to later MICS-Link phases):**
- `mics-link` Python SDK package (Phase 19)
- Stub generation + bootstrap-zip endpoints + "Download SDK" GUI button (Phase 20)
- Per-pilot health dashboard React page + WS forwarding via orchestrator (Phase 21)
- DeepLabCut reference hw_lib + template + rig demo (Phase 22)
- OpenEphys / photometry recipes (Phase 23)
- No prefs.json EXTLINK block — explicitly rejected. Everything network-related lives in `pilot_hardware_config.config` (Phase 17 schema).

**Dependencies:** Phase 9 (hardware_libs + AST extractor — this phase extends the extractor), Phase 10 (hardware_modules + pilot_hardware_config), Phase 11 (toolkit_dispatch.py spec emits HARDWARE + PREFS_HARDWARE), Phase 13 (preflight-validate by class_name), Phase 17 (pilot_hardware_config free-form name-keyed schema).

**Verification posture:** Backend file edits are agent-driven (api/ is in the docker compose stack). Pi-side `<verify>` blocks return commands for the user to run themselves (sync `~/pi-mirror/` → Pi, restart pilot, run smoke script). The agent does not run git on the Pi, does not start/stop the pilot process, and does not run any Python on the Pi.

---

### Phase 23: Compute Primitives + Variables
**Goal:** GUI-assembled FDA-JSON-v2 tasks can produce computed values (random draws, derived numbers/booleans) into named variables at state entry, and route on them via existing transitions — without writing Python or editing locked toolkit source. Delivers the library-backed computed-value loop end-to-end: Pi runtime (`variables` registry + `compute` action + curated stdlib primitives), backend validation + compute-library storage, and the GUI state-builder/transition wiring.

**Requirements:** CMP-01–06, CMP-10–15

**Design context:** `~/.claude/plans/i-realized-something-the-ancient-pnueli.md` (locked decisions: curated primitives + first-class `variables` registry; branching stays in FDA transitions; stdlib `random`/`math` only; per-Pi packages explicitly deferred).

> **Renumbered from Phases 19–22 → single Phase 23** (three plans) to clear the MICS-Link SDK arc's reserved numbers (19–22), and structured as multiple plans under one phase per the established 09–13 pattern.
>
> **Decoupled:** the `expr` escape-hatch (former CMP-07–09 — a sandboxed restricted-AST evaluator + `type:"expr"` action) was pulled out of this phase. The library-backed `compute` path covers current needs; `expr` is deferred (documented in the design spec, can become its own phase later). `compute` is fully self-sufficient — it rides on the same `variables`/`output` plumbing built in 23-01.

**Plans (waves):**
- **23-01-PLAN.md** (wave 1) — *Pi runtime: variables + compute + primitives* (CMP-01–06). `~/pi-mirror/.../tasks/mics_task.py` `load_fda_from_json()` (~683): parse top-level `variables`, instantiate as generic Trackers in `self.flags` + `self.view.view` (init_flags pattern), carry through `UPDATE_FDA` hot-reload store; `_build_action_callable()` (~525): add `compute` branch resolving args via `_resolve_arg` and `.set()`-ing `output`. New `~/pi-mirror/.../tasks/compute_primitives.py` — pure functions: random/copy (`random_choice`, `random_int`, `random_float`, `random_bool`, `assign`) + numeric/util (`add`, `subtract`, `multiply`, `divide`, `modulo`, `minimum`, `maximum`, `clamp`); numeric value-production only (no boolean-logic ops — branching stays in transitions). `_resolve_arg` gains a `{"view": name}` branch so a variable read back as an arg resolves (counter pattern `add(counter,1)→counter`). Confirm generic `Tracker` (utils/Tracker.py) is the untyped base.
- **23-02-PLAN.md** (wave 2, depends 23-01; also Phase 9) — *Backend validation + compute-library storage* (CMP-10–12). `api/routers/toolkits.py` `_validate_task_definition()` (~661) delegates to a new `api/fda_validation.py` `_validate_variables(...)`: variables-registry + collision + reference validation (hard 422s, distinct from the soft hardware-drift path). `api/fda_utils.py`: extend recursive ref scanner for `compute` `output` names. `api/routers/hardware_libs.py`: AST extractor also emits module-level `functions`. Store the shared compute library as a (non-hardware) `hardware_libs` row reusing Phase-9 storage/versioning/AST — no new table.
- **23-03-PLAN.md** (wave 3, depends 23-02; also Phase 3/12) — *GUI: compute state builder + variable wiring* (CMP-13–15). `web_ui/react-src/src/components/StateBodyPanel.tsx` + `ActionEditor.tsx`: `compute` editor (primitive picker from compute-lib AST + per-arg `ArgInput` + `output`), inline variable auto-declare. `ConditionBuilder.tsx`: operand dropdown from toolkit `FLAGS` + task `variables`. `pages/task-editor/TaskEditor.tsx`: `variables` serialize/deserialize + reachability warning. `types/index.ts`: FDA-JSON-v2 `variables` + `compute` types. `src/api/computeLibrary.ts`: fetch compute-library primitive signatures.

**Success criteria (phase-level — see plans for per-slice detail):**
1. *(23-01)* FDA-JSON-v2 with `"variables": { "target": {} }` + a `trial_onset` state `entry_actions` including `{ "type": "compute", "op": "random_bool", "args": [0.5], "output": "target" }` loads without error; `self.flags["target"]` and `self.view.view["target"]` are the same generic Tracker after load. Two guarded transitions on `{"view":"target","op":"==","rhs":{"literal":true}}`/`false` both fire across trials (recomputed once per entry, last-write-wins). All thirteen primitives resolve args via `_resolve_arg` (including a variable read back as an arg). `check_determinism()` stays safe (pure reads). Hot-reload instantiates a newly-added variable before rebuilding transitions.
2. *(23-02)* `POST/PUT /api/task-definitions` returns 422 for: undeclared `output`, variable-name collision with FLAGS/SEMANTIC_HARDWARE/view key, transition referencing an undeclared variable. `fda_utils` scanner returns `compute` outputs. Compute library stored as a `hardware_libs` row; GET returns AST metadata (name + args per primitive).
3. *(23-03)* StateBodyPanel offers a `compute` action; typing a new `output` auto-declares it into `variables` and makes it selectable in the ConditionBuilder operand dropdown; save serializes `variables` + the compute action to FDA-JSON-v2 and round-trips on reload. (Nice-to-have) editor warns on a transition reading a variable no reachable upstream state writes.

**Verification posture:** The Pi-side plan (23-01) is spec/edit-in-mirror only — `<verify>` blocks return commands for the user to run (sync `~/pi-mirror/` → Pi, restart pilot, run the gonogo-translation task); the agent does not run git, start/stop the pilot, or run Python on the Pi. Backend (23-02) and GUI (23-03) are agent-driven in the docker compose stack (call endpoints / verify DB via postgres MCP / rebuild web_ui).

**Dependencies:** Phase 1 (`load_fda_from_json`, `_resolve_arg`, `_build_transition_lambda`, `init_flags` pattern), Phase 2 (`UPDATE_FDA` hot-reload path), Phase 9 (hardware_libs storage + AST extractor — for 23-02), Phase 3/12 (StateBodyPanel, ActionEditor, ConditionBuilder, TaskEditor — for 23-03).

---

## Dependency Graph

```
Phase 1 (Pi Foundation)
    ↓ FLAGS/SEMANTIC_HARDWARE in HANDSHAKE
Phase 2 (DB + API)
    ↓ toolkits + task-definitions endpoints
Phase 3 (Visual Editor)
    ↓ task definitions with valid fda_json
Phase 4 (Protocol Integration)

Phase 5 (Pi Editor: Viewer)         ← independent, deploy anytime
    ↓ pi_ssh.py + page scaffold
Phase 6 (Pi Editor: Terminal)
    ↓ exec infrastructure + ALLOW_PI_EXEC gate
Phase 7 (Pi Editor: Edit+Restart)
    ↓ exec infrastructure + Phase 2 (required_packages)
Phase 8 (Pi Editor: Packages)

Phase 9 (HardwareLib Storage)       ← independent, can start after Phase 4
    ↓ hardware_libs table + AST metadata
Phase 10 (Hardware Modules + Pilot Config)
    ↓ hardware modules wired to libs
Phase 11 (Toolkit Redesign: Backend-Authored)
    ↓ toolkits with hardware_module_ids
Phase 12 (Hardware-Aware FDA Builder)
    ↓ task definitions validated against live AST
Phase 13 (Pre-Run Cross-Check + End-to-End)
    ↓ pilot_hardware_config schema + preflight-validate endpoint
Phase 17 (Free-Form Pilot Hardware Config)

Phase 1 (Pi Foundation) + Phase 2 (UPDATE_FDA hot-reload)
    ↓ load_fda_from_json, _resolve_arg, init_flags pattern
Phase 23 (Compute Primitives + Variables) — 3 plans:
    23-01 Pi runtime: variables + compute + primitives   (wave 1)
        ↓ variables registry + compute branch + output binding
    23-02 Backend validation + compute-library storage   (wave 2 ← also Phase 9)
        ↓ shapes accepted + compute-lib AST served
    23-03 GUI: compute state builder + var wiring         (wave 3 ← also Phase 3/12)
    (expr escape hatch decoupled/deferred — see Phase 23 note)
```

**Phase 1 can start today.** Phase 5 can also start in parallel with Phase 1 — they are fully independent. **Phase 9 can start after Phase 4 is complete** — it is independent of Phases 5–8.

### Phase 24: Trigger Assignment Action Lists

**Goal:** A hardware trigger fires the *same action vocabulary* a state's `entry_actions` uses (hardware / flag / timer / view / special / method / if), assigned from the task-editor UI instead of hard-coded in Python. Reference case to replicate and prove on the rig: `learning_cage.detectedLick`. Plus the missing backend validation layer for `trigger_assignments`.

**Requirements**: TRIGA-01 through TRIGA-10 (done), TRIGA-11a, TRIGA-12, TRIGA-14 through TRIGA-19. *TRIGA-11 dropped; TRIGA-13 moved to Phase 25.*
**Remaining for plans 06/07/08:** TRIGA-11a, TRIGA-12, TRIGA-14, TRIGA-15, TRIGA-16, TRIGA-17, TRIGA-18, TRIGA-19
**Depends on:** Phase 1 (`load_fda_from_json`, `_build_action_callable`, `_resolve_arg`), Phase 12 (StateBodyPanel / ActionEditor — the action editor UI to reuse). *Not* dependent on Phase 23; the two share the `output` value-capture idea and should be kept consistent.
**Plans:** 7/8 plans executed

Plans:
- [x] 24-01-PLAN.md — Pi runtime: variables registry, `output` capture, `view` action, `{"trigger"}` arg form, shared `fda_vocabulary` module (wave 1)
- [x] 24-02-PLAN.md — Backend: trigger ref scanning + new `api/fda_validation.py` hard-422 on save (wave 1)
- [x] 24-03-PLAN.md — React: schema types, ArgInput trigger mode, ActionEditor `view`/`output` support (wave 1)
- [x] 24-04-PLAN.md — Pi: `_build_trigger_action_list`, `actions`-only branch (handler enum deleted), single-sourced `validate_fda.py` (wave 2)
- [x] 24-05-PLAN.md — React: VariablesPanel + TriggerAssignmentPanel hosting the shared ActionEditor (wave 2)
- [x] 24-06-PLAN.md — Pi: TRIGA-12 capability-based `check_for_detectors` (load-bearing — the one predicate between now and working lick detection), TRIGA-18 `source_ref` + runtime-resolved `{device_name}`, TRIGA-19 value-source lock tests, then a scoped deploy (wave 3, 3 tasks). Deployed + md5-verified; user pytest run pending.
- [x] 24-08-PLAN.md — **RE-PLANNED 2026-07-27.** Backend + UI: TRIGA-15 `trigger_sources` derived from the lib AST (`is_trigger`, grouped inputs/outputs) + dropdown, TRIGA-16 hard-422 on a method-less hardware action, TRIGA-14 variables in the operand pickers, TRIGA-17 constrained one-pick detector write (wave 3, 4 tasks — runs in parallel with 24-06, disjoint files)
- [x] 24-07-PLAN.md — **RE-PLANNED 2026-07-27.** Rig proof TRIGA-11a, `autonomous: false`: UI round-trip checkpoint **first**, then the 422 negative suite, then four electrodes → `LICKER0..3` with `pi_timestamp` and the cross-talk negative (wave 4, gates on 06 + 08)

> **Scope change 2026-07-27 — sourceless toolkits only.** The reference case in the Goal above
> (`learning_cage.detectedLick`) is no longer the acceptance target; the same *pattern* must be
> reproduced via registered hardware modules on a backend-authored toolkit. Waves 1–2 are
> unaffected and were proven on the rig (run 475: 47 `TOUCH_INT` firings, alternating levels).
> Full analysis: `.planning/phases/24-trigger-assignment-action-lists/24-REPLAN-BRIEF.md`.
> Hardware evidence and 7 post-execution defect fixes: `24-HARDWARE-VALIDATION.md`.
>
> **Re-plan decisions taken 2026-07-27** (`24-CONTEXT.md` § `<replan_2026_07_27>`, R1–R11):
> the researcher gets a **constrained one-pick detector write** that emits ordinary FDA JSON
> (UI macro, no new Pi concept); `key_template` gains a runtime-resolved `{device_name}` token so
> definitions stay pilot-agnostic; both `pin_number` **and** `level` come from `detect_change`'s
> return, never from the trigger's GPIO edge; detector-key derivation for the editor's pickers
> stays in **Phase 25, which runs immediately after 24**.

**Design decisions settled during planning (24-CONTEXT.md Open Decisions):**
1. Dynamic tracker naming → **option (a)**: return-value capture (`output`) + new `view` action + `{name}` key templating. Option (b) ruled out by the user; option (c) rejected because it stands on the latent `_build_touch_detector_callback` bug.
2. ~~**Additive**, not replacement.~~ **Reversed and executed as REPLACEMENT** (TRIGA-06, plan 24-04): the `handler` enum is deleted, `actions` is the only vocabulary. Proven on the rig, run 475.
3. `level`/`tick` → composed callable declares them as named params; per-invocation stash on `self`, already serialized by `trigger_lock`.
4. Validation → **new** `api/fda_validation.py` with a hard-422 posture called from POST/PUT. The soft `_validate_task_definition` path is untouched.
5. Value capture → build Phase 23's `variables` registry **now**; Phase 23's `compute` writes into the same slots via the same `output` field.

**Current state (verified 2026-07-26):**
- UI panel exists — `web_ui/react-src/src/components/TriggerAssignmentPanel.tsx` (161 lines), wired into `TaskEditor.tsx:739`.
- Pi runtime exists — `apply_trigger_assignments()` (`mics_task.py:1037`) plus `_build_touch_detector_callback` / `_build_digital_input_callback`; unit tests in `~/pi-mirror/tests/test_trigger_assignments.py` (12 KB).
- Backend validation does **not** exist — `grep -rn "trigger" api/` returns nothing. `trigger_assignments` is the only FDA-JSON section the API never validates; a bad handler or `hardware_ref` raises `ValueError` on the Pi at session start.
- Feature has never been exercised end-to-end on the rig.

**Legacy behaviour to preserve/replace:**
- `execute_trigger()` (`task.py:286`) normalises `self.triggers[pin]` to a list and calls each callback with `level=` / `tick=` **if the signature declares them** (`inspect.signature`).
- `detectedLick` (`learning_cage.py:162`): `pin_number, level = MPR121.detect_change()` → `device_str = f"{device_name}{pin_number}"` → `self.view.view[device_str].set(level, pi_timestamp=tick)`.

**Pi-side gaps to resolve during planning:**
1. **No `view` action type.** `_build_action_callable` (`mics_task.py:524`) handles hardware/flag/timer/special/method/if. Touch-channel trackers are created by `check_for_detectors` via `view.add_Tracker` (`mics_task.py:266`) and live **only** in `self.view.view` — `init_flags` is what writes both `self.flags` and `self.view.view`, so no existing action can write a licker tracker.
2. **Hardware actions discard return values.** `_hw_call` calls `getattr(hw, method)(*args)` and drops the result; `detect_change()`'s return *is* the payload. Needs an `output` capture (keep consistent with Phase 23 `variables`).
3. **No trigger context in `_resolve_arg`.** Supports `{param}` / `{flag}` / `{now}` only — needs `{"trigger": "level"|"tick"}`, and the built callable must declare those parameters so `execute_trigger` passes them.
4. **Dynamic tracker naming.** `device_str` is derived from the returned channel index — a flat declarative list cannot express "index into the return value to pick the tracker". Main open design decision (see 24-CONTEXT.md).

**Also in scope:**
- `api/fda_utils.py` reference scanner must cover trigger `hardware_ref`s so hw-lib version changes flag affected task definitions.
- UI and Pi handler lists are two independently hard-coded arrays (`default`, `log_only`, `touch_detector`, `digital_input`) that can silently diverge — serve from backend or cross-check.
- Migration posture for existing `handler`-based assignments (additive vs replacement) — decide in discuss-phase.

**Success gate:** the lick-detection path runs on the rig driven by a UI-assigned action list, with **no Python callback registered for `TOUCH_INT`** (`learning_cage` no longer assigns `self.triggers['TOUCH_INT']`). The `detectedLick` method is retained as reference + one-line rollback — registration is the property under test, not existence.

### Phase 25: Detector-derived view keys visible in the FDA editor

**Goal:** Once a detector-bearing hardware module (MPR121) is attached to a toolkit, its per-electrode view keys — `LICKER0…LICKER3`, i.e. `device_name` × `num_detectors` — are derived by the backend and offered as **first-class pickable options in the FDA editor**: transition-condition view operands, state-body operands, and the trigger `view` action's `key_template`. The same derivation resolves keys against a *specific* pilot at preflight, so a wrong key fails before START instead of writing into a view that has no such tracker.

**Requirements**: DVK-01 through DVK-10 (**DVK-09 added 2026-07-27 from rig evidence** — the rig's four spouts sit on MPR121 channels 1–4, so `range(0, num_detectors)` builds a dead `LICKER0` and silently discards channel 4; see `24-HARDWARE-VALIDATION.md` §2b Finding A. Resolved 2026-07-29 to `first_channel` + `num_detectors`, **not** a channel list. **DVK-10 added 2026-07-29** — the reason that discard was invisible: `execute_trigger`'s `except KeyError` (`task.py:285-298`) swallows the unknown-key `KeyError` raised at `mics_task.py:717-721` and logs `"No valid trigger for {pin}"` at DEBUG)
**Depends on:** Phase 24 (TRIGA-12 capability-based `check_for_detectors`; the `view` action + `key_template`), Phase 10 + 17 (hardware modules, name-keyed `pilot_hardware_config`), Phase 13 (`preflight_validate` — named by 24-02 as the home for view-key resolution).
**Plans:** 3/6 plans executed

Plans:
- [x] 25-01-PLAN.md — backend derivation core: one key helper + the cross-pilot union with surfaced disagreement (DVK-01/02/07)
- [x] 25-02-PLAN.md — Pi runtime: `first_channel` in `check_for_detectors`, narrowed `execute_trigger` guard, `view_detector` build-time resolution (DVK-01/09/10/11)
- [x] 25-03-PLAN.md — backend wiring: `detector_channels` on the toolkit read, per-pilot key resolution in `preflight_validate` (DVK-02/06/11)
- [ ] 25-04-PLAN.md — editor pickers: grouped view operands, `key_template` suggestions, unknown-key degradation (DVK-03/04/05/07)
- [ ] 25-05-PLAN.md — preflight issue rendering + the `first_channel` config affordance (DVK-06/09)
- [ ] 25-06-PLAN.md — deploy, user-run Pi suite, rig proof (DVK-08/09/10) — **checkpoint plan**

Waves: 1 = [01, 02] · 2 = [03] · 3 = [04, 05] · 4 = [06]

**DVK-02 decided at plan time (no discuss-phase pass):** the design-time key source is the
**union across pilots that have a `pilot_hardware_config` row named for that module**, with
per-pilot provenance and a `conflict` flag. A `hardware_modules` default and a per-toolkit
declaration were both rejected: each would be a second store of `device_name`/`num_detectors`
that the Pi never reads, since the Pi receives its config from `pilot_hardware_config` via
`get_dispatch_spec`'s `prefs_hardware`. One table, one helper, two scopes — design-time union,
run-time single pilot. Full rationale in `25-01-PLAN.md` `<decisions>`.

**SCOPE RESTORED 2026-07-27 (supersedes the "SCOPE REDUCED" note of the same day)** — the reduction
assumed Phase 24 would deliver the HANDSHAKE-derived path via TRIGA-13. That mechanism is
**structurally impossible**: a registry-declared detector never appears in `prefs.HARDWARE` (its
config arrives per-run via `PREFS_HARDWARE` in the START payload, after HANDSHAKE), so the Pi cannot
derive these keys for a sourceless toolkit at all. TRIGA-13 is retired into DVK-01/02/03 and **all of
DVK-01…10 belongs to this phase**, which now runs immediately after 24.

Phase 24 still delivers TRIGA-14 (variables in operand pickers) and, crucially, does **not** need
detector keys itself: the constrained one-pick detector affordance (TRIGA-17) removes the need on the
trigger path, and the runtime-resolved `{device_name}` token (TRIGA-18) removes the need for
`device_name` — so this phase never has to solve `device_name` for the trigger path, only for the
editor's pickers. **Transitions on `LICKER2` are unavailable until this phase lands.**

Original notes on what this phase must solve, still accurate:
1. **The registry-declared source (DVK-01/02).** HANDSHAKE reads `prefs.HARDWARE` at pilot startup; a
   detector declared as a backend hardware module gets its config merged only at task start
   (`_merge_prefs_hardware`), so its keys never reach HANDSHAKE. The backend holds that config in
   `pilot_hardware_config` and must derive from it — then merge both sources without duplicating the
   key format.
2. **Per-pilot truth (DVK-02/06).** HANDSHAKE writes a per-toolkit row, so two pilots running the
   same toolkit with different `num_detectors` are last-handshake-wins. Phase 25 surfaces the
   disagreement and resolves keys per pilot in `preflight_validate`.
3. **DVK-05/07** (unknown keys degrade; detector keys never leak into flag validation) and **DVK-08**
   for the registry path — 24-07 proves only the prefs path.
DVK-03/04 are partially delivered by 24-08; Phase 25 extends the same pickers to the second source
rather than building them.

**Current state (verified 2026-07-27, before 24-08):**
- **The backend and the UI know nothing about detectors.** `grep -rn "Touch_Detector|num_detectors|device_name" api/ web_ui/react-src/src` → **0 hits**. Every `LICKER` key in the system today exists only at Pi runtime, created by `check_for_detectors` (`mics_task.py:241-266`) from `prefs.HARDWARE`.
- **The editor cannot even express a licker transition.** `ConditionBuilder.tsx:64-67` builds `viewOpts` as `semantic_hardware` keys + hardware-module names + toolkit flags; lines 79-87 render a `<select>` whenever that list is non-empty, so free text is unreachable. Adding MPR121 to a toolkit therefore surfaces `MPR121` — and never `LICKER0…LICKER3`. An already-stored unknown key survives only via the line-81 "keep current value" escape.
- `hwModuleNames` comes from `toolkit.hardware_module_ids` → `getHardwareModule(id).name` (`TaskEditor.tsx:176-182`) and is passed to `ConditionRow` / `ConditionGroupsEditor` (`TaskEditor.tsx:766`).
- **The numbers live per-pilot.** `hardware_modules` stores only `name` / `class_name` / `hardware_lib_id` / `description` — no default config. `device_name` and `num_detectors` live in `pilot_hardware_config.config` (free-form JSON, name-keyed since Phase 17).
- 24-02 deliberately keeps view-key *resolution* out of save-time validation (task definitions are pilot-agnostic) and names Phase 13's `preflight_validate` as the future home — nothing has been added there yet; preflight only checks that a config row exists per module.

**Central design tension to settle in planning:** task definitions are pilot-agnostic, but `device_name` × `num_detectors` is per-pilot data. The editor needs keys *before* a pilot is chosen. Candidate sources — union across pilots that have the module configured (surfacing disagreement rather than silently merging), a declared default on `hardware_modules`, or an explicit per-toolkit declaration. Pick one; do not invent a second source of truth for the key format — it must stay `f"{device_name}{i}"`, identical to `check_for_detectors`.

**Success gate:** attach MPR121 to a toolkit, open the FDA editor, and pick `LICKER2` from the view-operand dropdown when declaring a transition; the definition saves, preflights clean against the configured pilot, and the transition fires on the rig.

---
*Created: 2026-03-15*
*Last updated: 2026-05-28 — Phase 17 added: free-form pilot hardware config CRUD (HW-08, HW-11)*
