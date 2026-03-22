# Roadmap: MICS Backend

**Milestone:** M1 — ToolKit + FDA Redesign + Pi Code Editor
**Status:** Planning complete — not started
**Requirements:** 49 v1 requirements across 8 phases

---

## Phase Summary

| # | Phase | Goal | Requirements | Status |
|---|---|---|---|---|
| 1 | 3/6 | In Progress|  | ○ Pending |
| 2 | 4/4 | Complete   | 2026-03-22 | ○ Pending |
| 3 | Visual FDA Editor | react-flow editor, state body panel, trigger panel, push button | UI-01–12, VAR-06 | ○ Pending |
| 4 | Protocol Integration | Protocol steps reference task definitions | PROTO-01–03, VAR-07 | ○ Pending |
| 5 | Pi Editor: Viewer | Read-only file browser + Monaco + SSH status | EDIT-01–06 | ○ Pending |
| 6 | Pi Editor: Terminal | xterm.js terminal, /ws/pi/exec, ALLOW_PI_EXEC gate | EDIT-07–10 | ○ Pending |
| 7 | Pi Editor: Edit+Restart | PUT /api/pi/file, POST /api/pi/restart, Monaco edit mode | EDIT-11–14 | ○ Pending |
| 8 | Pi Editor: Packages | Package diff, install endpoint, packages tab UI | EDIT-15–17 | ○ Pending |

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

**Requirements:** UI-01 through UI-12, VAR-06

**Success criteria:**
1. Open `/react/task-editor/:id` → canvas shows nodes and edges matching stored fda_json; no console errors
2. Drag a new state node → drag between handles → edge created → click edge → right panel shows condition builder → save → fda_json updated in DB
3. Click state node → state body panel shows entry_actions → add a hardware action with param-ref arg → save → fda_json includes new action with `{"param": "..."}` form
4. Trigger assignment panel shows all trigger hardware → change TOUCH_INT to `touch_detector` → save → fda_json.trigger_assignments updated
5. "Push to Pilot" button enabled (pilot is running this task def) → click → toast appears → within 2s Pi logs show `HOT_RELOAD_ACK`

**New files:**
- `web_ui/react-src/src/pages/task-editor/index.tsx`
- `web_ui/react-src/src/components/TaskEditorCanvas.tsx`
- `web_ui/react-src/src/components/StateBodyPanel.tsx`
- `web_ui/react-src/src/components/TriggerAssignmentPanel.tsx`
- `web_ui/react-src/src/components/ActionEditor.tsx`
- `web_ui/react-src/src/components/ArgInput.tsx`
- `web_ui/react-src/src/api/toolkits.ts`
- `web_ui/react-src/src/api/taskDefinitions.ts`

**npm additions:** `@xyflow/react`

**Dependencies:** Phase 2 (toolkits and task-definitions API)

---

### Phase 4: Protocol Integration
**Goal:** Protocol steps reference task definitions; FDA JSON flows end-to-end from DB to Pi

**Requirements:** PROTO-01 through PROTO-03, VAR-07

**Success criteria:**
1. Open `/react/protocols-create` → task palette shows named task definitions, not raw task_type strings
2. Create protocol with a task-definition step → start session → orchestrator logs show `state_machine` key in START; Pi runs JSON-driven FDA
3. `GET /api/tasks/leaf` deprecated; `GET /api/task-definitions` returns equivalent data; no 404s on existing protocol UI flows

**Files changed:**
- `web_ui/react-src/src/pages/protocols-create/index.tsx`
- `api/models.py` — `ProtocolStepTemplate.task_definition_id` field
- `api/main.py` — `create_session_run()` resolves fda_json from task definition

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
```

**Phase 1 can start today.** Phase 5 can also start in parallel with Phase 1 — they are fully independent.

---
*Created: 2026-03-15*
*Last updated: 2026-03-16 — Phase 2 plans added (4 plans, 3 waves)*
