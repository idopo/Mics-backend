# Roadmap: MICS Backend

**Milestone:** M1 — ToolKit + FDA Redesign + Pi Code Editor + Hardware Centralization
**Status:** Phases 1–8 planning complete; Phases 9–13 planned
**Requirements:** 86 v1 requirements across 13 phases

---

## Phase Summary

| # | Phase | Goal | Requirements | Status |
|---|---|---|---|---|
| 1 | 3/6 | In Progress|  | ○ Pending |
| 2 | 4/4 | Complete   | 2026-03-22 | ○ Pending |
| 3 | Visual FDA Editor | react-flow editor, state body panel, trigger panel, push button | UI-01–12, VAR-06 | ○ Pending |
| 4 | 3/3 | Complete   | 2026-03-24 | ○ Pending |
| 5 | Pi Editor: Viewer | Read-only file browser + Monaco + SSH status | EDIT-01–06 | ○ Pending |
| 6 | Pi Editor: Terminal | xterm.js terminal, /ws/pi/exec, ALLOW_PI_EXEC gate | EDIT-07–10 | ○ Pending |
| 7 | Pi Editor: Edit+Restart | PUT /api/pi/file, POST /api/pi/restart, Monaco edit mode | EDIT-11–14 | ○ Pending |
| 8 | Pi Editor: Packages | Package diff, install endpoint, packages tab UI | EDIT-15–17 | ○ Pending |
| 9 | HardwareLib Storage | hardware_libs DB + API, AST validation, Pi override dir, E2E proof with gpio.py | HW-01–05 | ○ Pending |
| 10 | Hardware Modules + Pilot Config | hardware_modules + pilot_hardware_config DB + API + UI, prefs.json migration seeder | HW-06–11 | ○ Pending |
| 11 | 2/3 | In Progress|  | ○ Pending |
| 12 | Hardware-Aware FDA Builder | hardware method picker in StateBodyPanel, lib-change validation, broken-definition warnings | HW-17–20 | ○ Pending |
| 13 | Pre-Run Cross-Check | validate-for-pilot endpoint, start flow gate, Pi dynamic hardware init from received config | HW-21–24 | ○ Pending |

---

## Phase Details

### Phase 1: Pi Foundation
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

**Files changed:**
- `api/routers/toolkits.py` (validate-for-pilot endpoint)
- `web_ui/react-src/src/pages/subject-sessions/SubjectSessions.tsx` (pre-run check gate)
- `orchestrator/orchestrator/orchestrator_station.py` (START handler: send hardware config dict to Pi)
- `~/pi-mirror/autopilot/autopilot/tasks/mics_task.py` (dynamic init_hardware from received_hw_config)

**Dependencies:** Phase 12 (task definitions have validation_status; hardware modules fully wired)

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
```

**Phase 1 can start today.** Phase 5 can also start in parallel with Phase 1 — they are fully independent. **Phase 9 can start after Phase 4 is complete** — it is independent of Phases 5–8.

---
*Created: 2026-03-15*
*Last updated: 2026-04-20 — Phases 9–13 added: Hardware Libs Centralization + Hardware Modules + Toolkit Redesign (HW-01–24)*
