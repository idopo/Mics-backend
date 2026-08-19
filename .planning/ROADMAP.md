# Roadmap: MICS Backend

**Milestone:** M1 — ToolKit + FDA Redesign + Pi Code Editor + Hardware Centralization
**Status:** Phases 9–17 complete. Active scope is **24 → 25 → 23 → review → 18 → 26 → 27 → 28**. Phase 25 added 2026-07-27, depends on 24; **agreed 2026-07-27 to run immediately after 24, before 23** — phase 24 deliberately does not derive detector view keys, so transitions on `LICKER2` are unavailable until 25 lands. **Phases 26–28 (the OpenEphys arc) added 2026-08-03**, all depending on Phase 18, whose context was revised the same day to carry them — Phase 18's existing plans are superseded and it must be re-planned. Phases 1–4 archived, 5–8 deferred.
**Requirements:** 103 v1 requirements across 16 phases *(+17 on 2026-08-03: EXTLINK-14–18 for the revised Phase 18 substrate, EPHYS-01–12 for Phases 26–28; EXTLINK-07 and EXTLINK-13 amended in place)*

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
| 18 | 15/15 | Complete   | 2026-08-09 | EXTLINK-01–18 | ○ Pending — **context revised 2026-08-03, must be re-planned** (old plans in `superseded/`) |
| 23 | 12/12 | Complete    | 2026-08-05 | ✓ **Complete 2026-08-05** — 12/12 plans, all waves closed including the operand-namespace consistency pass (CMP-20–25). Rig-proven across runs 535–550 and 551: compute action dispatches, executes, writes a variable and gates a transition through both branches; 41 draws with zero routing violations; CMP-16 pair intact 10/10 for a non-numeric output with zero rejected documents; the one read namespace (`view`) drives real transitions with the legacy `flag`/`hardware` escape surviving a GUI resave byte-identical. See `23-HARDWARE-VALIDATION.md`. ⚠ Open: gonogo task never built (equivalent FDA validated instead); compute op **args** absent from the event log (CMP-16 partial); CMP-18 researcher-authored lib upload unproven on hardware; CMP-24b/CMP-25 deployed but not rig-exercised; CMP-24a/24c reverted before deploy (pending GSD todo); Pi unit tests still unrun on the Pi |
| 24 | Trigger Assignment Action Lists | Triggers run the same action vocabulary as state `entry_actions` (+ new `view` action, return-value capture, `{trigger: level/tick}` args); backend validation for `trigger_assignments`; on a **sourceless** toolkit a constrained one-pick detector write drives the licker trackers with no way to cross pin and tracker; `trigger_name` picked from the toolkit's trigger-capable hardware | TRIGA-01–10, 11a, 12, 14–19 | ✓ **8/8 plans executed 2026-07-27** — rig-proven (runs 478/480/481: 144 triggers, 63 licker writes, 0 correctness errors); 8/8 save-time negative cases 422. ⚠ Pi test suite still never run (user-run) |
| 25 | Detector-Derived View Keys | `LICKER*` keys derived by the backend, offered in the FDA editor's view-operand and `key_template` pickers, resolved per-pilot in Phase 13 preflight. **Absorbs TRIGA-13.** **DVK-09 added from rig evidence** — channels must be declarable, not assumed 0-based (a live spout is currently discarded); resolved 2026-07-29 to `first_channel` + count, no channel list. **DVK-11 added 2026-07-29** — operands store a detector ref + channel index, never the resolved per-pilot key. **DVK-10 added 2026-07-29** — `execute_trigger`'s over-broad `except KeyError` swallowed that discard as `"No valid trigger"`. Transitions on a licker key are unavailable until this lands | DVK-01–11 | ◐ **5/6 plans executed 2026-07-29** — plan 01 landed the backend derivation core (DVK-01/02/07/09/11); plan 02 landed the Pi runtime half (DVK-09/10/11: `first_channel` in `check_for_detectors`, `execute_trigger` error containment, `view_detector` build-time resolution); plan 03 wired preflight resolution (DVK-06/11: out-of-range channel / unreachable literal key / unresolvable `{device_name}` template all fail preflight with the pilot's actual wiring) and `detector_channels` onto every toolkit read route including `by-name`; plan 04 made detector channels first-class pickable view operands in the FDA editor (DVK-03/04/05/07/11: grouped `<optgroup>` picker emitting `{"view_detector": {"ref","channel"}}`, `key_template` suggestions, unknown-key preservation); plan 05 renders `view_key_unresolved` preflight issues in `HardwareCheckModal` (both shapes, no start gate, PUT loop provably skipped) and adds the `first_channel` config affordance with a live key preview (DVK-06/09) — only plan 06 (deploy + rig proof) remains |

| 26 | OpenEphys Device Control | MICS starts/stops the OE recording itself, names the save folder per subject/session, writes labelled markers into the recording, and records the path back into MICS. Control only — no neural data into the task | EPHYS-01–05 | ○ Pending |
| 27 | OpenEphys Firing Rate over ZMQ | Pi SUBs to the OE ZMQ plugin, decodes spikes in a versioned lib's `@decoder`, maintains a windowed rate per declared unit as an ordinary view key, logs `(ts_pi_recv, oe_sample)` pairs for clock co-registration | EPHYS-06–10 | ○ Pending |
| 28 | TTL vs Network Sync Validation | Run both paths into one recording, quantify offset/jitter over a real session, report whether network-only alignment meets experimental tolerance. **No cutover** — evidence only | EPHYS-11–12 | ○ Pending |
| 29 | FDA Builder Canvas UX | Edge readability (bowed arcs, per-edge labels, arrowheads, self-loops, back-edge routing), layered auto-layout, position persistence in a dedicated `ui_layout` column kept out of `fda_json`'s hash. **Zero Pi impact** | CANVAS-01–14 | ◐ 7/8 executed 2026-08-05 — only 29-08 (gate sweep + human proof) remains |
| 30 | 8/9 | In Progress|  | ○ Exit gate green 2026-08-10 (`--final` 0, zero manifest drift); publication + rig proof are USER-RUN (plan 09) |

**Execution order (amended 2026-08-03):** Phase 24 → **Phase 25** → Phase 23 → review → Phase 18 → **26 → 27 → 28** (the OpenEphys arc). Phase 25 moved ahead of 23 because phase 24 deliberately does not derive detector view keys for the editor. Phases 26–28 are the first consumer of Phase 18's `ExternalHardware` substrate, which was revised on 2026-08-03 to carry them. See `.planning/STABILIZATION_PLAN.md`.

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

**Requirements**: EXTLINK-01, EXTLINK-02, EXTLINK-03, EXTLINK-04, EXTLINK-05, EXTLINK-06, EXTLINK-07, EXTLINK-08, EXTLINK-09, EXTLINK-10, EXTLINK-11, EXTLINK-12, EXTLINK-13, EXTLINK-14, EXTLINK-15, EXTLINK-16, EXTLINK-17, EXTLINK-18, EXTLINK-19, EXTLINK-20 *(EXTLINK-07 and EXTLINK-13 amended 2026-08-03; EXTLINK-14–18 added the same day; EXTLINK-19–20 added 2026-08-09 — see the authoring-gap note under Plans)*

> **⚠ CONTEXT REVISED 2026-08-03 — this phase must be RE-PLANNED.** The original design assumed one
> consumer shape: our own SDK, speaking our MessagePack envelope, **dialing into** the Pi's ROUTER.
> OpenEphys (Phases 26–28) breaks that, and DeepLabCut will break it the same way. `18-CONTEXT.md`
> § `<revision_2026_08_03>` carries the full rationale. **The previous `18-01`/`18-02` plans were
> written against the pre-revision context and are archived in `superseded/`** — neither was
> executed. Five additions to the substrate: transport roles + `@decoder`, liveness split from
> signal staleness, egress queue, run lifecycle hooks, device lease.

**Plans:** 15/15 plans complete
and 18-12 amended 2026-08-09) — **✅ RE-VERIFICATION PASSED 2026-08-05.** Ten of the twelve were revised on 2026-08-03 (commit `64bbd2d`) to add transport
`role: "none"` for control-only devices, after Phase 26 planning exposed the gap. The plan-checker was
re-run against the revised plans: iteration 1 found 3 blockers (the `role: "none"` liveness-override
rule was implemented but tested nowhere; the `EgressWorker` seam would have forked Phase 26; the
now-mandatory liveness override ran a blocking network call on the shared IOLoop), a planner revision
closed them, and iteration 2 passed. See `.planning/STATE.md` § Phase 18 status for the full record.
Unchanged throughout: 18-04, 18-07. **Approved for `/gsd:execute-phase 18`.**

Plans:
- [ ] 18-01-PLAN.md — Wave 0: Pi wire/decoder/liveness contract tests + agent msgpack install
- [ ] 18-02-PLAN.md — Wave 0: Pi egress/lifecycle/ready-gate contract tests + `super().end()` pin
- [ ] 18-03-PLAN.md — Wave 0: backend contract tests (device lease + AST extlink)
- [ ] 18-04-PLAN.md — msgpack version pin resolved on the rig's Python 3.7.3 (user checkpoint)
- [ ] 18-05-PLAN.md — `external_hardware_wire.py`: codec, dtypes, stale policy, liveness, `@decoder`, roles
- [ ] 18-06-PLAN.md — `external_hardware_runtime.py`: egress worker, lifecycle runner, readiness-gate decision
- [ ] 18-07-PLAN.md — backend AST extractor: `api/extlink_ast.py` → `ast_metadata.extlink`
- [ ] 18-08-PLAN.md — device lease core: table, host normalization, preflight step 10, two new issue kinds
- [ ] 18-09-PLAN.md — lease endpoints, reconciliation loop on the Redis heartbeat, orchestrator + HardwareCheckModal
- [ ] 18-10-PLAN.md — `ExternalHardware` base class + the four decorators
- [ ] 18-11-PLAN.md — `mics_task` bind post-pass, `_wait_extlink_ready` pre-state, `extlink_smoke.py`
- [ ] 18-12-PLAN.md — the single consolidated rig checkpoint + `18-HARDWARE-VALIDATION.md` *(amended 2026-08-09: +3 checkpoint steps — author in the editor, hand-drive + soak, and a mandatory teardown)*
- [ ] 18-13-PLAN.md — backend extlink signal aggregator + save-gate and preflight wiring
- [ ] 18-14-PLAN.md — FDA editor: extlink signals in the view-operand picker
- [ ] 18-15-PLAN.md — cross-platform hand driver (`tools/extlink_driver/`) + `extlink_demo` FDA

> **Authoring gap found and closed 2026-08-09 (EXTLINK-19/20).** The original twelve plans built the
> whole transport but left the feature unreachable from the product: `buildViewOptions`
> (`detectorOptions.mts:90`) enumerates only `semantic_hardware` names and detector channels, and
> `ConditionBuilder.tsx:95` offers a free-text view key ONLY when the picker is empty — so an
> extlink key could survive a round trip (the escape at `ConditionBuilder.tsx:76` names
> `ExternalHardware` signals explicitly) but could never be *created*. Worse, verified during
> planning: `api/fda_validation.py:207-265` hard-**422s** any `{"view": …}` outside a known name
> set, so criterion 1 was unreachable even by hand-PUTing `fda_json`. EXTLINK-09 had always
> anticipated the picker ("so FDA-editor and state-builder UIs (Phase 19+) can render typed forms")
> — that forward reference was stale, since Phase 19 is now the device-health surface. 18-13/14
> close both halves; 18-15 supplies the external program that drives it.

**Success criteria:**
1. A standalone DEALER script (`~/pi-mirror/scripts/dev/extlink_smoke.py`) connects to the per-instance `listen_port` with the configured `source_id`, pushes `dlc_cam1.left_paw_x = 0.7`, and an FDA transition gated on `view.get_value("dlc_cam1.left_paw_x") > 0.5` fires — **observed as a state change, with no latency bound asserted.** *(The original "within 50 ms" was dropped 2026-08-09: nobody can eyeball 50 ms, and comparing a sender's timestamp against the Pi's `ts_pi_recv` measures clock skew — those machines are not NTP-synced to each other. Latency and jitter belong to **Phase 28** (TTL vs Network Sync Validation), which owns clock-domain comparison and measures both paths inside one recording. Phase 18 verifies transport behaviour under load as a **soak** instead — EXTLINK-20, plan 18-12 step 8b: at ~60 Hz for ~30 s the pilot stays up, the FDA keeps transitioning, bounded-queue drops are reported rather than silent, and ES ingestion keeps up.)*
2. **Both transport roles work.** `router_bind` behaves as above. A `sub_connect` instance dials out to a foreign publisher, its lib's `@decoder` translates the foreign frame into declared signals, and the resulting view keys are indistinguishable from a `router_bind` source's at the `view.get_value(...)` call site.
3. **Liveness is separate from signal staleness.** A source that is reachable but sending no signal updates stays `alive == true` while its signals go stale per their declared policy. A lib-supplied liveness hook overrides the data-arrival default. Every flip emits a CONTINUOUS event visible in ES.
4. Per-signal stale policy probe: stop pushing a `return_default` signal; `view.get_value(...)` returns the declared default after `stale_after_ms`.
5. Two `ExternalHardware` subclasses uploaded as hardware libs, each registered as a `hardware_module`, each given its own `pilot_hardware_config` row, and both used in one toolkit on one task — both Trackers visible in View, no cross-talk.
6. A malformed inbound message (unknown signal name, bad MessagePack, undecodable foreign frame) is dropped + logged; pilot keeps running; no traceback in pilot logs.
7. `pilot.py` LOAD_HARDWARE_LIBS path (unchanged from Phase 9) accepts an `ExternalHardware` subclass; instantiation happens through the standard hw_libs → hw_modules → toolkit-dispatch path with NO new Pi-side ingress.
8. AST extractor (`api/routers/hardware_libs.py`) emits the declared signal/event/command/decoder metadata; no schema change to any DB table.
9. **Egress works and never blocks the FDA thread.** Outbound calls to one device are FIFO-ordered; a failed send is logged as a CONTINUOUS event and never retried; queue overflow drops the newest and records the loss; N consecutive failures flip `alive`.
10. **Lifecycle hooks fire correctly.** `on_run_start(run_ctx)` runs async after `.bind()` and is retried inside the wait window; the readiness gate releases on *ready*, not merely *alive*. `on_run_stop()` runs on normal completion, STOP, and task exception — and the backend safety net fires when the Pi never reports back.
11. **A control-only module with zero declared signals** instantiates, binds, participates in the readiness gate, and uses the egress path.
12. **The device lease hard-blocks** a second run targeting a held device, surfaced as a preflight issue naming the holding pilot/subject/run; it is released by backend reconciliation when the run ends uncleanly, and by manual force-release.
13. **An external signal is authorable in the FDA editor** (EXTLINK-19). A transition gated on `dlc_cam1.left_paw_x` is created entirely through the editor's view-operand picker — no hand-edited `fda_json` — saves without a 422, and round-trips without rendering as "(unknown)". The stored operand is the resolved key `{"view": "<source_id>.<signal>"}`.
14. **A researcher drives the mechanism from a non-Pi machine** (EXTLINK-20). A cross-platform driver in `tools/extlink_driver/` (macOS now, Windows later, `pyzmq` + `msgpack` only) pushes signal values by hand from a laptop over `role: router_bind`, and the FDA's state changes respond — plus a `--sweep` and a `--rate` soak against the throwaway `extlink_demo` task definition.

**Files to change:**
- `mics-backend/api/routers/hardware_libs.py` (extend — AST extractor recognises `@signal` / `@event` / `@command` / `@decoder`; metadata flows through the existing `ast_metadata` field)
- `mics-backend/api/routers/toolkit_dispatch.py` (extend — device-lease preflight issue kind + validation of the new config fields; dispatch shape itself UNCHANGED)
- `~/pi-mirror/autopilot/autopilot/hardware/external_hardware.py` (new — base class, decorators, per-role socket helper, `@decoder` hook, View Tracker auto-registration, stale policy, liveness hook, egress queue, lifecycle hooks)
- `~/pi-mirror/autopilot/autopilot/tasks/mics_task.py` (extend — `init_hardware()` bind post-pass, lifecycle-hook firing, `_wait_extlink_ready` pre-state keyed on *ready*)
- `~/pi-mirror/scripts/dev/extlink_smoke.py` (new — standalone DEALER smoke test runnable from the dev machine)
- `~/pi-mirror/autopilot/autopilot/hardware/external_hardware_wire.py` (new — the `autopilot`-free codec/dtype/stale/liveness/decoder/role half; load-bearing for agent-side testability, see `18-VALIDATION.md`)
- `~/pi-mirror/autopilot/autopilot/hardware/external_hardware_runtime.py` (new — the `autopilot`-free egress worker, lifecycle runner and readiness-gate decision)
- `~/pi-mirror/requirements.txt` + `~/pi-mirror/autopilot/requirements.txt` (extend — `msgpack` is a genuine NEW dependency, pinned for Python 3.7.3)
- `mics-backend/api/extlink_ast.py` (new — decorator-metadata extraction; `hardware_libs.py` is 872 lines and gets a call, not a body)
- `mics-backend/api/device_lease.py` (new — lease store, host normalization, extlink config validation, reconciliation)
- `mics-backend/api/routers/device_leases.py` + `api/main.py` (new router — acquire / force-release / reconcile)
- `mics-backend/api/models.py` + `api/db.py` (extend — `device_leases` table + idempotent migration)
- `mics-backend/web_ui/react-src/src/components/HardwareCheckModal.tsx` (extend — the `PreflightIssue` union MUST mirror `PREFLIGHT_ISSUE_KINDS`; omitted from the original file list)
- `mics-backend/orchestrator/orchestrator/orchestrator_station.py` + `mics/mics_api_client.py` (extend — lease acquire/release + a NEW reconciliation loop keyed on `_redis_touch`'s `updated_at`; `_run_watchdog` stays dead code, it keys on `started_at` and would kill every session over 30s)
- `mics-backend/api/extlink_keys.py` (new — extlink signal aggregation: `ast_metadata.extlink` → per-pilot view keys, cross-pilot union with a `conflict` flag, mirroring `detector_keys.module_detector_channels`)
- `mics-backend/api/fda_validation.py` (extend — the save-time hard-error gate must admit extlink keys; today it 422s them)
- `mics-backend/api/routers/toolkits.py` (extend — `extlink_signals` on the toolkit read, at the same three sites `module_detector_channels` is called from)
- `mics-backend/web_ui/react-src/src/components/detectorOptions.mts` + `ConditionBuilder.tsx` + `ArgInput.tsx` (extend — one option group per external module; `TaskEditor.tsx` is NOT touched, `extlink_signals` rides `ToolkitRead` which both consumers already receive)
- `mics-backend/tools/extlink_driver/` (new — the cross-platform hand driver. Deliberately NOT under `~/pi-mirror/`, which is rsynced to the Pi)

**NOT in scope:**
- `mics-link` Python SDK package; stub generation + bootstrap-zip endpoints + "Download SDK" GUI button
- Per-pilot health dashboard React page + WS forwarding via orchestrator
- **The OpenEphys hardware lib itself** — Phases 26 (control) and 27 (firing rate). Phase 18 delivers only the substrate they stand on.
- DeepLabCut reference hw_lib + template + rig demo (reserved; inherits `sub_connect` for free)
- Bulk-stream tier for high-rate continuous data — not in MICS-Link v1 at all
- Device *scheduling* (queue / notify-when-free) — the lease hard-blocks only
- No prefs.json EXTLINK block — explicitly rejected. Everything network-related lives in `pilot_hardware_config.config` (Phase 17 schema).

**Dependencies:** Phase 9 (hardware_libs + AST extractor — this phase extends the extractor), Phase 10 (hardware_modules + pilot_hardware_config), Phase 11 (toolkit_dispatch.py spec emits HARDWARE + PREFS_HARDWARE), Phase 13 (preflight-validate by class_name), Phase 17 (pilot_hardware_config free-form name-keyed schema).

**Verification posture:** Backend file edits are agent-driven (api/ is in the docker compose stack). Pi-side `<verify>` blocks return commands for the user to run themselves (sync `~/pi-mirror/` → Pi, restart pilot, run smoke script). The agent does not run git on the Pi, does not start/stop the pilot process, and does not run any Python on the Pi.

---

### Phase 19: Per-Pilot Device Health Surface

**Goal:** An `ExternalHardware` device going unreachable mid-run becomes visible **while the session
is running**, not at analysis time. Any `<source_id>.alive` tracker flip reaches the live pilot
payload and lights a warning affordance on the pilot card, so a researcher can decide whether to
stop. Device-neutral: OpenEphys is the first consumer, DeepLabCut and photometry light the same
indicator for free.

**Requirements**: HEALTH-01, HEALTH-02, HEALTH-03, HEALTH-04, HEALTH-05, HEALTH-06 *(the surfacing
half of EXTLINK-07, split out of Phase 18 whose scope explicitly excludes it; also closes the
deferral recorded in `26-CONTEXT.md`'s amended mid-run decision)*

**Why this is its own phase.** `alive` is a Phase 18 concept — EXTLINK-07 owns the generic
`<source_id>.alive` tracker — but Phase 18's NOT-in-scope list explicitly excludes *"Per-pilot health
dashboard React page + WS forwarding via orchestrator"*, and EXTLINK-07's surfacing commitment stops
at the ES event. Phase 26 then locked *"surface prominently in pilot status"* without noticing it had
written a decision across that scope boundary. Building it inside 26 would put generic Phase 18
substrate in the OpenEphys phase; reopening Phase 18 would invalidate a verdict earned over six
plan-checker iterations. So it is separated, and `26-CONTEXT.md` now records the deferral and its
cost explicitly.

**Dependencies:** Phase 18, and **only** Phase 18. It supplies the `<source_id>.alive` trackers, the
CONTINUOUS flip event, and — importantly — a device to prove this against: `18-12-PLAN.md` builds
demo libs including `DemoControl` (`role: "none"`), registers `oe_ctl.alive`, and already has a
kill-the-source step confirming `alive` flips to `false`. **So this phase needs no OpenEphys and can
execute immediately after 18.**

**Relationship to Phase 26:** none, in either direction. Phase 26 does not depend on this phase —
detection ships there (the flip, its CONTINUOUS event, the loud log line), presentation ships here —
and this phase does not need Phase 26, per the demo libs above. Phase 26 simply becomes a second
consumer of the indicator when it lands. `26-CONTEXT.md` records the deferral and its accepted cost.

**Plans:** 3 plans in 3 waves (planned 2026-08-05)

Plans:
- [ ] 19-01-PLAN.md — Wave 1: `state.py` health map + `.alive` suffix parser, `on_data` hook, `/pilots/live` merge
- [ ] 19-02-PLAN.md — Wave 2: `deviceHealth.mts` render decision + `PilotLive.device_health` + the pilot-card badge
- [ ] 19-03-PLAN.md — Wave 3: `dev_health_probe` end-to-end injector + the browser checkpoint

> **Planning correction (2026-08-05):** `19-RESEARCH.md` finding F3 is wrong about the orchestrator
> half. `GET /pilots/live` is served from **Redis**, not `state.snapshot()` — the `return
> state.snapshot()` version is commented out at `orchestrator/orchestrator/api.py:14-19` and a
> Redis-scanning implementation is registered at `:24`. So **`orchestrator/orchestrator/api.py` is in
> scope** and is added to the file list below. Device health still stays in `OrchestratorState`
> (in-memory) and is merged at read time: a Redis write from `on_data` would be a blocking network
> call on the shared Tornado IOLoop, and Redis outlives an orchestrator restart, so a stale
> `alive: false` could outlive both the run and the process.
>
> Also load-bearing and absent from the research: the Pi sends `alive` as **int 0/1, not a bool** —
> `log_value.coerce_for_event` int-coerces every tracker value because `event.event_data.value` is
> mapped `long` in `event_log_v2` and a long field rejects a bare bool with an HTTP 400.
>
> Plan 19-03 removes the rig from the critical path: the inbound wire format is one JSON frame from a
> ZMQ DEALER and `/pilots/live`'s notion of a connected pilot is one Redis hash, so the whole chain
> is exercisable with no Pi and no device. Success criterion 6 becomes a five-second addition to the
> next run that already has an external device (Phase 18's `18-12` kill-the-source step is its
> natural host), not a booked session.

**Success criteria:**
1. `OrchestratorState` carries per-pilot device health, written from the CONTINUOUS handler under
   the same lock as every other mutator, and `snapshot()` exposes it — defaulting to `{}`, never
   `None`, so the common no-external-device case needs no null check.
2. The health map is keyed by full tracker name and matched on the **`.alive` suffix**, never on a
   device class name — a second device type lights it with zero orchestrator change.
3. `WS /ws/pilots` carries it to the browser. `web_ui/app.py` forwards the orchestrator's
   `/pilots/live` response verbatim, so this should need no proxy change — confirm before assuming.
4. The React pilot card renders a visible warning when a device is not alive during an active run,
   and shows nothing when there are no external devices.
5. A pilot's health map is cleared wherever `active_run` is cleared, so a stale warning cannot
   outlive the run that produced it.
6. Rig proof: power the OE box off mid-run and see the pilot card change without a page reload.

**NOT in scope:** a full per-pilot health dashboard page; historical health charts; alerting or
notification outside the browser; any automatic run abort on liveness loss (EXTLINK-07 makes
mid-run liveness loss never automatically fatal — the FDA author gates on it if the experiment
requires it).

**Files to change** (verified against the live source, 2026-08-05):
- `orchestrator/orchestrator/state.py` — `OrchestratorState` gains a per-pilot `device_health` dict
  and `snapshot()` exposes it. Take `self._lock` like every other mutator: written from the ZMQ
  handler thread, read by the `/pilots/live` HTTP thread.
- `orchestrator/orchestrator/orchestrator_station.py` — `on_data` also routes `*.alive` CONTINUOUS
  payloads into the state. No new ZMQ key; it rides the existing CONTINUOUS channel.
- `orchestrator/orchestrator/api.py` — **added during planning.** `list_live_pilots` merges
  `state.get_device_health(pilot_key)` into each pilot entry. `/pilots/live` is Redis-backed, so
  `snapshot()` alone never reaches the browser; see the planning correction above.
- `orchestrator/orchestrator/dev_health_probe.py` (new) — dev-only diagnostic that fabricates a
  connected pilot in Redis and pushes a real `<device>.alive` CONTINUOUS frame over the real ZMQ
  socket, so the whole surface is verifiable without a Pi.
- `web_ui/react-src/src/types/index.ts` — `PilotLive` (line 1) gains `device_health`. Its current
  shape is exactly `{ connected, state, active_run, updated_at }`.
- `web_ui/react-src/src/pages/index/Index.tsx` — **`PilotCard` is a function inside this 129-line
  file, not a separate component module.** Extract it only if the file would pass 300 lines; it
  won't for this change.
- `web_ui/react-src/src/pages/index/deviceHealth.mts` (new) — the render decision as a pure,
  node-tested module, following the established `src/components/trackerMethods.mts` pattern.
- `web_ui/app.py` — **confirmed to need NO change.** `/ws/pilots` (`:49-89`) forwards
  `resp.json()` verbatim on a 0.5 s poll and `/api/pilots` (`:39-44`) does the same, so a new
  orchestrator key reaches the browser untouched. Plan 19-02 carries a source-level guard on that
  fact, since a future reshape would break this phase silently.
- **CSS:** `web_ui/react-src/src/style.css` does not exist — CLAUDE.md names the wrong path. The app
  is styled by `web_ui/static/style.css`, where `.state-warning-badge` / `.state-warning-tooltip`
  already exist and are an exact fit. No new class is invented. (Fixing CLAUDE.md is out of scope
  here.)

**Note there is no external-device UI in the React app today** — `grep -rln "extlink|external_device|source_id" web_ui/react-src/src` returns nothing. This phase builds the first live one.

---

---

### Phase 23: Compute Operations (Compute Libs)
**Goal:** A researcher can compute a value inside a state, store it in a variable, and transition on it — without a developer editing locked toolkit source, and with every computation recorded in the event log. Compute operations are delivered as **user-extensible, versioned, auto-logged libraries** using the existing hardware-lib substrate, so a researcher can add a new operation (e.g. weighted choice, sampling without replacement) the same way they add a hardware driver.

**Requirements:** CMP-01–06, CMP-10–25

**Design context:** `~/.claude/plans/i-realized-something-the-ancient-pnueli.md`, **revised 2026-08-03** — see `23-CONTEXT.md` for the locked reframe. The original "curated pure-function primitives" design is superseded.

> **Renumbered from Phases 19–22 → single Phase 23** to clear the MICS-Link SDK arc's reserved numbers (19–22), structured as multiple plans per the established 09–13 pattern.
>
> **Scope correction (2026-08-03):** the `variables` half of this phase **already shipped in Phase 24** (`mics_task.py` `load_fda_from_json` ~1017 — variables are Trackers registered in both `self.flags` and `self.view.view`, with `_validate_output_spec`/`_capture_output` writing any action's return value into them). CMP-01/02/14 are marked *built in 24*. The remaining delta is **the operations, their extensibility mechanism, backend validation, and the GUI.**
>
> **The reframe — a compute lib IS a hardware lib.** Same substrate (rows in `hardware_libs`/`hardware_lib_versions` + a new `kind` column; existing versioning, AST, promotion trail, and `LOAD_HARDWARE_LIBS` transport), deliberately different surface (`type:"compute"` in FDA-JSON and GUI). Runtime is a class subclassing `Hardware` (base is pure metadata, `pin = None`) so `@log_action` records the **operation**, not just the result — `log_action` only dispatches for `Mics_Tracker`/`Hardware` instances, so a module of pure functions would log nothing.
>
> **Decoupled/deferred:** the `expr` escape-hatch (former CMP-07–09) **and** inline Python typed into a state body. Both forfeit versioning and op logging (no object for `@log_action`), so neither can satisfy CMP-16. Python authoring happens in the hardware-lib editor; the state body only selects and wires. Third-party PyPI packages + per-Pi package management also deferred — CMP-19 reserves the hooks.

**Plans:** 12/12 plans complete

Plans (waves):
- [x] 23-01-PLAN.md — **wave 1** — Wave 0: the three missing test files as executable contracts (CMP-04/12/17/19) — done 2026-08-03, see `23-01-SUMMARY.md`
- [x] 23-02-PLAN.md — **wave 2** — DB substrate: `hardware_libs.kind`, declared imports, seed Compute Ops lib + COMPUTE module, auto-provisioned pilot config (CMP-04/12/19) — done 2026-08-03, see `23-02-SUMMARY.md`
- [x] 23-03-PLAN.md — **wave 2** — Backend validation: compute hard-422s in the EXISTING `api/fda_validation.py`, compute-aware ref scanner, new `api/variable_scan.py` (CMP-10/11/15) — done 2026-08-03, see `23-03-SUMMARY.md`
- [x] 23-04-PLAN.md — **wave 2** — Pi runtime: the `compute` branch in `_build_action_callable`, vocabulary, CLI validator (CMP-03/04/05/06) — done 2026-08-03, see `23-04-SUMMARY.md`
- [x] 23-05-PLAN.md — **wave 3** — CMP-17 version resolution unified across dispatch / introspection / orchestrator; `test_import` activated (CMP-17/19) — done 2026-08-03, see `23-05-SUMMARY.md`
- [x] 23-06-PLAN.md — **wave 3** — GUI: `kind` types, filter chip and compute upload on the existing Hardware Libraries page (CMP-12/18) — done 2026-08-03, see `23-06-SUMMARY.md`
- [x] 23-07-PLAN.md — **wave 4** — Preflight: no `incomplete_config` false positive, self-healing compute config, `variable_never_written`, reserved issue kinds, variable-usage route (CMP-15/17/19) — done 2026-08-03, see `23-07-SUMMARY.md`
- [x] 23-08-PLAN.md — **wave 4** — GUI: the ONE "compute" action-type entry, grouped op picker, auto-declaring output field (CMP-13/14) — done 2026-08-03, see `23-08-SUMMARY.md`
- [x] 23-09-PLAN.md — **wave 5** — GUI: new preflight issues rendered (and excluded from the PUT loop), read-only variables inspector (CMP-14/15) — done 2026-08-03, see `23-09-SUMMARY.md`
- [x] 23-10-PLAN.md — **wave 6** — Deploy + single rig-proof checkpoint: Pi suite, gonogo translation, ES evidence for both event types, GUI click-through (CMP-01/02/03/04/05/06/13/14/16/18) — done, see `23-10-SUMMARY.md`
- [x] 23-11-PLAN.md — **wave 7** — Operand pickers: one read namespace (`view`), legacy `flag`/`hardware` escape, variables in `if` conditions and as a write ref, `view` argument mode (CMP-20/21/22/23) — done 2026-08-05, see `23-11-SUMMARY.md`
- [x] 23-12-PLAN.md — **wave 8** — `view` means one thing everywhere: semantic hardware as a condition read (backend), Pi invariant fix (narrowed to CMP-24b), consolidated rig sign-off for CMP-20–25 (CMP-24/25 + sign-off for 20–23) — done 2026-08-05, see `23-12-SUMMARY.md`. CMP-24b/CMP-25 deployed but not rig-exercised; CMP-24a/24c reverted before deploy, tracked as a pending GSD todo.

**Wave structure:** 1 → {02, 03, 04} → {05, 06} → {07, 08} → 09 → 10 → 11 → 12. Wave 2's three plans are
fully parallel (backend substrate / backend validation / Pi mirror — no shared files). All Pi
work is grouped so the user is asked to touch the rig exactly once, in plan 23-10.

**Success criteria (phase-level):**
1. *(Pi runtime)* An FDA-JSON-v2 task with `"variables": {"target": {}}` and a `trial_onset` compute action `random_bool(0.5) → target` loads and runs; two guarded transitions on `{"view":"target","op":"==","rhs":{"literal":true}}`/`false` both fire across trials, recomputed once per entry (last-write-wins). A variable read back as its own arg (`add(counter,1)→counter`) resolves. `check_determinism()` stays safe (guards read stored results only). Hot-reload re-creates variables before rebuilding transitions.
2. *(Logging — CMP-16)* Both events reach the event log for each compute call: a `Hardware_Event` carrying the **op and its args**, and the `Tracker` set event carrying the **result**. Verified on-rig against the gonogo translation.
3. *(Extensibility)* A researcher-authored compute lib created in the hardware-lib editor is versioned, promoted unvalidated→beta→stable, linked to a toolkit, shipped to the Pi by `LOAD_HARDWARE_LIBS`, and its ops appear in the GUI op picker from AST metadata — with no code change to the platform.
4. *(Backend)* `POST/PUT /api/task-definitions` returns 422 for: undeclared `output`, variable-name collision with FLAGS/SEMANTIC_HARDWARE/view keys, transition referencing an undeclared variable. `fda_utils` scanner returns `compute` outputs. `kind` distinguishes compute libs; version resolution follows pin → toolkit default → **latest stable** → preflight issue (correcting the current pin → active chain for both lib kinds).
5. *(GUI — uncluttered)* Hardware Libraries page gains a `kind` filter chip (no new page/nav). StateBodyPanel's action-type list gains **exactly one** entry, "Compute", rendering one compact row `[output var] = [op ▾] ( [args] )`. Typing a new `output` auto-declares it into `variables` and it is immediately selectable in the ConditionBuilder. Save round-trips.
6. *(Discoverability — CMP-15)* A `variable_never_written` preflight issue surfaces through Phase 25's existing issue renderer when a transition reads a variable no reachable upstream state writes. Read-only variables inspector shows writers/readers per variable.

**Verification posture:** Pi-side work is spec/edit-in-mirror only — `<verify>` blocks return commands for the **user** to run (sync `~/pi-mirror/` → Pi, restart pilot, run the gonogo-translation task); the agent does not run git on the Pi, start/stop the pilot, or run Python on the Pi. Backend and GUI work is agent-driven in the docker compose stack (call endpoints / verify DB via postgres MCP / rebuild web_ui).

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
Phase 23 (Compute Operations / Compute Libs) — 12 plans, 8 waves (re-planned 2026-08-03; COMPLETE 2026-08-05, 12/12):
    23-01 Wave 0 test contracts                          (wave 1)
        ↓
    23-02 DB substrate (kind, seed lib, provisioning)  ─┐
    23-03 Backend validation + variable_scan           ─┼ (wave 2, parallel)
    23-04 Pi runtime compute branch                    ─┘
        ↓
    23-05 CMP-17 version resolution + test_import       ─┐ (wave 3, parallel)
    23-06 GUI kind filter chip                          ─┘
        ↓
    23-07 Preflight compute fixes + variable-usage route ─┐ (wave 4, parallel)
    23-08 GUI compute action row                         ─┘
        ↓
    23-09 GUI preflight issues + variables inspector      (wave 5)
        ↓
    23-10 Deploy + rig proof (checkpoint)                 (wave 6)
        ↓
    23-11 Operand pickers: one read namespace (CMP-20/21/22/23)   (wave 7)
        ↓
    23-12 Pi + backend `view` invariants + sign-off (CMP-24/25)   (wave 8, checkpoint — DONE)
    (expr escape hatch + inline Python decoupled/deferred — see Phase 23 note)

Phase 9 (hardware_libs + AST) + Phase 10 (hardware_modules)
  + Phase 11 (toolkit dispatch) + Phase 13 (preflight) + Phase 17 (free-form config)
    ↓ the whole hw-lib → module → pilot-config → dispatch → preflight pipeline
Phase 18 (MICS-Link: ExternalHardware substrate)
    ↓ roles (router_bind | sub_connect) + @decoder
    ↓ egress queue + on_run_start/on_run_stop + device lease
    ├─────────────────────────────┐
    ↓                             ↓
Phase 26 (OpenEphys Control)   [DeepLabCut — reserved, paused]
    ↓ OpenEphys module + config row + lease held
Phase 27 (OpenEphys Firing Rate over ZMQ)
    ↑ also needs Phase 25 (detector_keys → editor-visible derived view keys)
    ↑ also needs Phase 24 (hardware action type — markers need no new vocabulary)
    ↓ network markers in the recording + (ts_pi_recv, oe_sample) pairs
Phase 28 (TTL vs Network Sync Validation — measurement only, no cutover)
```

**Phase 1 can start today.** Phase 5 can also start in parallel with Phase 1 — they are fully independent. **Phase 9 can start after Phase 4 is complete** — it is independent of Phases 5–8.

**Phases 26–28 cannot start before Phase 18**, which is the substrate they consume. Phase 27 additionally carries an external prerequisite outside MICS: a spike detector/sorter must sit upstream of the OE ZMQ plugin, with sorting configured, or there are no spikes on the wire and no unit IDs to declare.

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
**Plans:** 5/6 plans executed

Plans:
- [x] 25-01-PLAN.md — backend derivation core: one key helper + the cross-pilot union with surfaced disagreement (DVK-01/02/07)
- [x] 25-02-PLAN.md — Pi runtime: `first_channel` in `check_for_detectors`, narrowed `execute_trigger` guard, `view_detector` build-time resolution (DVK-01/09/10/11)
- [x] 25-03-PLAN.md — backend wiring: `detector_channels` on the toolkit read, per-pilot key resolution in `preflight_validate` (DVK-02/06/11)
- [x] 25-04-PLAN.md — editor pickers: grouped view operands, `key_template` suggestions, unknown-key degradation (DVK-03/04/05/07/11)
- [x] 25-05-PLAN.md — preflight issue rendering + the `first_channel` config affordance (DVK-06/09)
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

## MICS-Link consumers: the OpenEphys arc (Phases 26–28)

Phases 26–28 are the **first real consumer** of the Phase 18 `ExternalHardware` substrate. Phase 18
was revised on 2026-08-03 specifically so these three could stand on it without bespoke plumbing —
see `18-CONTEXT.md` § `<revision_2026_08_03>`. DeepLabCut is the intended second consumer and
inherits the same substrate (`sub_connect` + `@decoder`) for free; it is deliberately paused.

**Source:** `docs/open_ephys_integration.pdf` (+ `.md` twin). Two independent OE network channels:
HTTP REST control on **37497**, ZMQ data on **5556** (plugin default, configurable — confirm against
the rig's actual plugin settings).

**Locked scope decisions (2026-08-03 session):**
- **The Pi owns both channels.** One clock domain, one versioned lib, one toolkit story. The backend
  owns *only* the device lease, because the Pi cannot know about other pilots.
- **The OE machine is shared across rigs but never used simultaneously.** The lease is a safety net,
  not a scheduler — no queue/notify UX.
- **The TTL cable stays.** Network markers run alongside it. Phase 28 measures the two against each
  other; any cutover is a later decision made on that evidence, not part of this arc.

**Correction carried into planning:** the OE ZMQ plugin transfers **spikes, not firing rate**. Rate
is derived by windowed counting, which here runs on the Pi. Two consequences bind Phase 27: the OE
signal chain needs a **spike detector/sorter upstream of the ZMQ plugin** or there are no spikes on
the wire at all, and **sorted unit IDs only exist if sorting is configured**, so units of interest
must be declared in `pilot_hardware_config.config` rather than discovered at runtime.

---

### Phase 26: OpenEphys Device Control

**Goal:** A MICS session starts and stops an Open Ephys recording by itself, names the save folder
per subject/session, writes labelled event markers into the recording mid-task, and records the
resulting path back into MICS — so a researcher never touches the Open Ephys GUI and the system
knows where its own ephys data landed. Control-only: no neural data flows into the task yet.

**Requirements**: EPHYS-01, EPHYS-02, EPHYS-03, EPHYS-04, EPHYS-05

**Depends on:** Phase 18 (`ExternalHardware` base class, egress queue, `on_run_start`/`on_run_stop`
lifecycle hooks, device lease, control-only zero-signal modules). Phase 24 (`hardware` action type —
markers are dispatched as ordinary state/trigger actions, so no new action vocabulary). Phase 17
(free-form `pilot_hardware_config`). Phase 13 (preflight issue system).

**Plans:** 13 plans in 4 waves — plan-checker PASSED 2026-08-03. ⚠ **26-10, 26-13 and
26-VALIDATION.md were edited 2026-08-05** to meet Phase 18's new `role: "none"` rule (a control-only
module must declare a class-level `liveness_hook` or it raises at construction), so that verdict is
partly stale. The edits are additive and confined to the Phase 18 seam — re-run the checker before
`/gsd:execute-phase 26`, or verify at execute time. Blocked on Phase 18 regardless.

Plans:
- [ ] 26-01-PLAN.md — Wave 0 backend test contracts (artifact path/record, OE client, migration, preflight kinds)
- [ ] 26-02-PLAN.md — Wave 0 Pi-mirror test contracts (autopilot-free OE client + marker contract)
- [ ] 26-03-PLAN.md — EARLY rig checkpoint: confirm the OE REST surface before path code is written
- [ ] 26-04-PLAN.md — device-neutral artifact path resolver + unknown-token 422 at config save
- [ ] 26-05-PLAN.md — device-neutral run_artifacts table, record store, and read-back API
- [ ] 26-06-PLAN.md — backend Open Ephys REST client (mode control, read-back path composition)
- [ ] 26-07-PLAN.md — Pi-side autopilot-free Open Ephys REST client + marker payload builder
- [ ] 26-08-PLAN.md — device-neutral stop registry + backend force-stop on unclean run end
- [ ] 26-09-PLAN.md — device-neutral preflight issue kinds + HardwareCheckModal mirror
- [ ] 26-10-PLAN.md — seeded first-party OpenEphys lib (ExternalHardware subclass + seeder)
- [ ] 26-11-PLAN.md — artifact-target endpoint + orchestrator wiring + per-run device opt-out
- [ ] 26-12-PLAN.md — React: per-device artifact rows, opt-out toggle, marker-label autocomplete
- [ ] 26-13-PLAN.md — the single consolidated rig checkpoint

**Success criteria:**
1. Starting a session on a pilot with an `OpenEphys` module configured drives OE from IDLE to RECORD
   via `PUT /api/status`, with no human interaction, and the FDA's first state is not entered until
   recording has actually started (readiness gate keys on `on_run_start`, not liveness).
2. The save folder is resolved from the run context (subject, session, run, pilot, timestamp) and is
   unambiguous across rigs — two pilots' data can never merge into one folder.
3. The resolved recording path is persisted in MICS and readable back through the API, so post-hoc
   tooling locates the recording without a human recording the path by hand.
4. A state `entry_action` and a trigger action can both emit a labelled marker (`cue_on`, `reward`)
   into the recording as an ordinary Phase-24 `hardware` action — no new action type in the editor.
5. Marker sends never block the FDA thread; a failed marker is logged as a CONTINUOUS event and the
   session continues (the TTL path is still live).
6. Session end — normal completion, STOP button, or task exception — returns OE to IDLE. A pilot
   crash is caught by the backend safety net, which stops the recording and releases the lease.
7. Preflight reports OE unreachable, and separately reports the device already held by another run,
   naming the holding pilot/subject/run. Both block the run before the animal is in the box.

**NOT in scope:** any neural data flowing into the task (Phase 27); TTL removal or comparison
(Phase 28); closed-loop behaviour.

**Verification posture:** Backend/API work is agent-driven (docker compose). The `OpenEphys`
hardware lib is authored in `~/pi-mirror/` and uploaded through the existing `/api/hardware-libs`
path. `<verify>` blocks for anything touching the rig return commands for the **user** to run — the
agent does not run git on the Pi, start/stop the pilot, or run Python on the Pi.

---


### Phase 27: OpenEphys Firing Rate over ZMQ

**Goal:** Live firing rate becomes a first-class task input. The Pi subscribes to the Open Ephys ZMQ
Interface plugin, decodes spikes, maintains a windowed rate per declared unit, and exposes it as an
ordinary view key — so `view.get_value("oe.unit_A001_1.rate")` reads like any other sensor and an FDA
transition can gate on it. Every inbound message's OE sample number is logged against `ts_pi_recv`,
giving software co-registration of the two clocks.

**Requirements**: EPHYS-06, EPHYS-07, EPHYS-08, EPHYS-09, EPHYS-10

**Depends on:** Phase 26 (the `OpenEphys` module, its config row, and the lease). Phase 18
(`sub_connect` role + `@decoder` hook — the mechanism that lets a foreign PUB format be decoded
inside a versioned hardware lib). Phase 25 (`api/detector_keys.py` `derive_view_keys` — the
precedent for deriving editor-visible view keys from `pilot_hardware_config.config` rather than from
static class declarations).

**Plans:** 0 plans (run `/gsd:plan-phase 27`)

**Success criteria:**
1. The Pi SUBs to the OE ZMQ plugin and decodes spike messages inside the versioned hardware lib's
   `@decoder`; no OE-specific parsing exists in platform code.
2. Units of interest and the rate window are declared in `pilot_hardware_config.config`; the
   resulting view keys are static per pilot, validated by preflight, and selectable in the FDA
   editor's operand pickers via the Phase 25 mechanism.
3. An FDA transition gated on a firing-rate threshold fires on the rig against real spiking.
4. `alive` reflects OE being reachable and recording — a genuinely quiet unit leaves `alive` true and
   lets the per-signal stale policy govern its value (the Phase 18 liveness/staleness split).
5. `(ts_pi_recv, oe_sample_number)` pairs are logged to ES at a steady cadence for the run's
   duration, sufficient to fit clock drift post-hoc.
6. Raw continuous data is **not** consumed. What the plugin actually puts on the socket is verified
   in the phase's first task before any estimator work — if continuous cannot be excluded, the
   bandwidth story is settled then rather than assumed now.

**NOT in scope:** raw continuous @30 kHz into the FDA (explicitly rejected — see Phase 18's deferred
bulk-stream tier); spike sorting inside MICS (OE owns sorting); TTL comparison (Phase 28).

**Known external prerequisite — PARTIALLY RESOLVED 2026-08-03.** The user reports that **the OE
pipeline already contains something that computes firing rate / spikes**, so the "there may be no
spikes on the wire at all" risk is substantially reduced. The *exact* nature is **not yet confirmed**
and must be checked on the rig before this phase is planned, because the two possibilities lead to
materially different designs:

- **(a) A spike detector/sorter publishing sorted spikes.** Phase 27 stands as written: the Pi does
  the windowed rate counting, units declared in `pilot_hardware_config` (EPHYS-07/08 as specified).
- **(b) Something computing firing rate directly.** Phase 27 simplifies considerably — the Pi
  consumes rate rather than estimating it, and EPHYS-08's windowed estimator largely disappears.
  **Open sub-question if (b):** is that computed rate actually *published over the ZMQ Interface*, or
  does it only exist inside the OE GUI? A value the GUI displays but never puts on the socket is
  useless to us, and would put us back on (a).

**To check on the rig before `/gsd:plan-phase 27`:** open the OE signal chain and record which
plugins sit upstream of the ZMQ Interface plugin, whether sorting is configured, and which message
types the ZMQ plugin is set to publish.

**Verification posture:** Same as Phase 26 — lib authored in `~/pi-mirror/`, rig commands returned
to the user, backend agent-driven.

---

### Phase 28: TTL vs Network Sync Validation

**Goal:** Quantify what the network path actually costs in timing accuracy, by running it alongside
the TTL cable that is still in place, and produce the evidence needed to decide whether the cable can
ever come out. This phase deliberately **does not remove the TTL** — it measures.

**Requirements**: EPHYS-11, EPHYS-12

**Depends on:** Phase 26 (network markers reaching the recording), Phase 27 (OE sample numbers paired
with Pi timestamps).

**Plans:** 0 plans (run `/gsd:plan-phase 28`)

**Success criteria:**
1. A single recording contains both the existing TTL pulses and the network markers for the same
   behavioural events, so the two are compared within one clock rather than across sessions.
2. Offset and jitter between the two paths are quantified over a real session — distribution, not a
   single number — and reported in a form the lab can act on.
3. The report states plainly whether network-only alignment meets the tolerance of the experiments
   actually being run, and what the residual risk is if the cable is removed.
4. No cutover is performed. Removing the TTL remains a separate, later decision.

**NOT in scope:** removing the TTL; changing the post-hoc analysis pipeline to network-only.

**Verification posture:** Rig session required — commands returned to the user. Analysis is
agent-driven against ES and the OE recording.

### Phase 29: FDA Builder Canvas UX

**Goal:** The task editor canvas is readable at a glance. Bidirectional transitions bow apart instead of crossing into an hourglass; every edge shows its own simplified condition label and an arrowhead; node positions survive a refresh, with a spaced layered auto-layout as the default and a right-click "Restore default layout" escape hatch.

Pure UI/UX. No change to FDA semantics, validation, or anything sent to the Pi.

**Requirements**: CANVAS-01 through CANVAS-14
**Depends on:** Phase 12 (FDA state builder), Phase 16 (recursive condition tree — supplies the edge labels)
**Plans:** 7/8 plans executed

Plans:
- [x] 29-01-PLAN.md — W1 · make room in TaskEditor.tsx: extract condLabel + FDA normalisers to tested .mts modules, extract the context menu — done 2026-08-05, see `29-01-SUMMARY.md`
- [ ] 29-02-PLAN.md — W1 · edgeGeometry.mts: pair grouping, perpendicular offsets, label stagger, self-loops, back-edge return paths (+ tests)
- [ ] 29-03-PLAN.md — W1 · fdaLayout.mts: shared columnRanks BFS, layered layout, orphan grid block, collision-free placement (+ tests)
- [x] 29-04-PLAN.md — W1 · backend task_definitions.ui_layout JSONB + GET/PUT + layout-only fast path (+ pytest) — done 2026-08-05, see `29-04-SUMMARY.md`
- [x] 29-05-PLAN.md — W2 · TransitionEdge.tsx custom edge: bowed arcs, per-edge labels, arrowheads, self-loops — done 2026-08-05, see `29-05-SUMMARY.md`
- [x] 29-06-PLAN.md — W3 · useLayoutPersistence hook: hydrate positions, debounced layout PUT off the FDA autosave path — done 2026-08-05, see `29-06-SUMMARY.md`
- [x] 29-07-PLAN.md — W4 · placement for new states + pane context menu with a persisting "Restore default layout" — done 2026-08-05, see `29-07-SUMMARY.md`
- [ ] 29-08-PLAN.md — W5 · consolidated gate sweep + CANVAS-12 human proof on definitions 186 + 172 (11 checks)

### Phase 30: Pi Repo Cleanup

**Goal:** The Pi tree becomes a repository someone can read. Everything the current
architecture superseded — the replaced Terminal GUI, the 27 legacy task plugins, the hardware
drivers no code path reaches, 190 MB of vendored installers, build output and rotated logs — is
gone, along with 244 lines of dead commented-out code. A leaked Gmail app password is revoked
and absent from history. What remains is published as a new repo that still starts the pilot
unchanged. **Removal is judged by what the current architecture needs, never by git history.**

**Requirements**: HYG-01 through HYG-14

**Depends on:** Phase 18 (supplies the five `external_hardware*` files that must survive the
sweep — two of them appear in no plan manifest), Phase 23 (`log_value.py`, compute libs),
Phase 24 (already deleted the touch-detector callbacks — do not re-delete), Phase 25 (left
uncommitted working-tree edits and deployed debug prints in the mirror). **Not blocked by
Phase 26–28** — no OpenEphys file exists yet, but `openephys_client.py` and its two test
modules are reserved names the sweep must not treat as strays if 26 lands first.

**Plans:** 8/9 plans executed

Plans:
- [x] 30-01-PLAN.md — W0 · the instrument: `tools/check_tree_integrity.py` + its tests, root pytest config (HYG-09), pre-sweep baseline manifest + credential probe
- [x] 30-02-PLAN.md — W1 · vendored/generated bulk: `code_2023.deb`, `docs/`, upstream `tests/`, submodules, tilde dirs, duplicate wavs, caches (HYG-08)
- [x] 30-03-PLAN.md — W1 · the Terminal-era tree: `terminal/`, `core/{gui,terminal,plots,subject,styles,utils,reward}.py`, `viz/`, `data_handlers/`, `utils/{invoker,Event}.py` (HYG-07)
- [x] 30-04-PLAN.md — W2 · prove the empty HANDSHAKE is a no-op, then delete `pilot/plugins/` + `learning_cage.py` + `mics_cage_task.py` + `unreal.py` as ONE change (HYG-03, HYG-04)
- [x] 30-05-PLAN.md — W3 · registry sweep collateral, `cameras.py`/`usb.py`, the `i2c.py` import **and the `MLX90640(Camera)` class**, in both the Pi copy and `hardware_libs` v26 (HYG-05, HYG-06)
- [x] 30-06-PLAN.md — W4 · remove the HDF5 set, collapse the orphaned `'child'` branch, sweep 244 dead commented lines, leave `Event_Dispatcher.py` alone, and **hold BOTH deferred blocks commented and sweep-exempt — the NTP clock block and the station.py watchdog, user-deferred 2026-08-10** (HYG-11, HYG-12, HYG-14)
- [x] 30-07-PLAN.md — W4 · `prefs.json` becomes a template; no lab IP, no SUBJECT, no PORT_CALIBRATION, no dead UNREAL group; runtime dirs empty behind `.gitkeep` (HYG-10)
- [x] 30-08-PLAN.md — W5 · `--final` gate, zero-drift survival manifest diff, merged evidence log, `30-PUBLISH.md` handover (HYG-01 repo half, HYG-13)
- [ ] 30-09-PLAN.md — W6 · clear `ExtlinkDemo` off pilot 1, then the USER-RUN rig checkpoint: revoke, publish, branch, live session (HYG-02, HYG-01)

**Planned 2026-08-10.** Correction found during planning and carried into 30-05: HYG-05's claim
that `Camera` is "never used" in `i2c.py` is wrong — `i2c.py:580` declares
`class MLX90640(Camera)`, so removing only the import leaves an undefined base class and kills
the pilot at import. The requirement text needs amending; the plan already implements the
three-part edit.

**Why this is its own phase.** Every prior phase moved responsibility *off* the Pi — hardware
source into `hardware_libs` (9, 10, 17), toolkits and FDA into `task_definitions` (11, 12, 15,
16, 23, 24, 25). None of them ever removed what they superseded, because each was scoped to
ship a capability, not to reclaim ground. The residue is now the majority of the tree. Folding
this into a feature phase would put a destructive sweep inside a phase verified on behaviour;
it needs its own rollback story and its own hardware checkpoint.

**Audit of record:** completed 2026-08-10 by five independent agents (runtime reachability,
legacy assets, backend contract, GSD phase history, commented-out code), cross-checked against
the live Postgres DB and against which `.cpython-37` bytecode the Pi itself wrote. Conflicting
agent findings on `cameras.py`, `jackclient.py` and `unreal.py` were resolved by direct
verification — see `30-CONTEXT.md`.

> **Decision 2026-08-10 — this phase deliberately departs from the plan of record.** No phase
> document in phases 1–29 authorizes deleting a single Pi *file*; every authorized deletion is
> of a method, constant or import inside a surviving file, and the corpus explicitly retains
> `pilot/plugins/*.py` (they feed `available_locked_states`) and `learning_cage.detectedLick`
> ("the reference implementation and a one-line rollback"). That posture was correct while
> source-authored toolkits were still dispatched. It no longer holds: **all live work is
> backend-authored and sourceless**, confirmed by the user 2026-08-10 and corroborated by the
> DB — protocols 56/57/58 all run `source_less_toolkit`, whose `locked_state_source` is NULL
> and which therefore dispatches to `mics_task`, not to any plugin file. The 43 protocol steps
> naming `elastic_test` and 15 naming `AppetitveTaskReal` are legacy rows that are not run.
> This departure is recorded here so a future reader does not mistake it for an oversight.

**Success criteria:**
1. The pilot still starts: `python3 -m autopilot.core.pilot -f pilot/prefs.json` reaches
   HANDSHAKE on the rig from the cleaned tree, and a real session runs to completion with
   CONTINUOUS events landing in ES exactly as before.
2. The leaked credential is revoked at Google **and** absent from the new repo's history —
   proven by `git log -p | grep` over the full history of the new repo returning nothing.
   The new repo is a fresh `git init`, never a clone or a filtered history.
3. `pilot/plugins/` and its orphans (`learning_cage.py`, `mics_cage_task.py`, `unreal.py`) are
   removed **in a single change**, never base-class-first — `api/main.py:1059-1070` raises 400
   on an unresolvable base class and, because the commit is at `:1117` inside one `try`,
   discards the tasks upsert, the toolkit upsert, the hardware-config seed and the
   locked-states upsert together.
4. A HANDSHAKE from the cleaned Pi reports `tasks: []` and the backend treats it as a no-op —
   `tasks_received: 0`, no row deleted, no 500. Verified against the live API, not assumed.
5. `cameras.py` is removed only together with the dead `from autopilot.hardware.cameras import
   Camera` at `i2c.py:8` — **and the matching edit to `hardware_libs` version 26**, whose
   `source_code` is `exec()`'d on the Pi. The two copies have already drifted 6 bytes; this
   phase reconciles them or records why not.
6. The five `external_hardware*` files, all 23 root test modules, and `fda_vocabulary.py`
   survive the sweep intact, proven by a post-sweep manifest diff.
7. Every removed file is justified in the phase's audit table by *reachability*, not by age or
   git history — the sweep is reproducible from the criteria, not from a hand-list.
8. `pilot/prefs.json` ships as a template with no lab IPs, no `SUBJECT`, no `PORT_CALIBRATION`
   and no rig-specific pin values; the device's real prefs are untouched.
9. Rig proof recorded in `30-HARDWARE-VALIDATION.md` with run numbers and md5 manifests, in
   the house format phases 18/23/24/25 established.

**NOT in scope:** any change on the Pi itself beyond a deliberate, separately-gated deploy
step; deleting anything from the *existing* `pi-mirror` git history; the OpenEphys arc;
resolving the four held behavioural toggles (see below); the backend-side dead code the audit
found (`orchestrator_station._run_watchdog`, the `task_files` branch, `on_task_error`).

**Constraints — each of these has already bitten once, or would:**
- **Never delete a base class before its subclasses.** See success criterion 3.
- **Never key deletion on "named in a PLAN".** `external_hardware_ingress.py` and
  `external_hardware_binding.py` emerged during Phase 18 execution and appear in no plan's
  `files_modified`; `external_hardware.py` imports both, and `_binding.py` is the single writer
  of the `alive` tracker that Phase 19 depends on entirely.
- **Never blanket-strip debug prints from `Event_Dispatcher.py`.** Phase 25 left real fixes
  interleaved with the prints there — a guarded tick read and the `_dropped_no_clock` /
  `_dropped_on_send` counters. Those must survive.
- **A syntactically broken file left in `autopilot/tasks/` is worse than a deleted one.**
  `list_classes` AST-parses that directory with no per-file guard, so one bad file ships
  `tasks: []` in every handshake. (`pilot/plugins/` *is* guarded per file — the asymmetry is
  real and load-bearing.)
- **The Pi rules stand** (`STATE.md:1723-1744`): no git in `/home/ido/pi-mirror`, not even
  `status`; never `rsync --delete`; never start/stop the pilot; never run Python on the Pi;
  Pi tests are USER-RUN.

**Files to change** (verified against live source, 2026-08-10):
- `pilot/plugins/` — all 27 task files removed. Keep the directory with a `.gitkeep`:
  `plugins.py:46-48` logs an exception and returns `{}` on a missing dir, which is survivable
  but noisy.
- `autopilot/autopilot/tasks/` — remove `learning_cage.py`, `mics_cage_task.py`, `children.py`,
  `nafc.py`, `gonogo.py`, `free_water.py`, `test.py`, `RecordingBox.py`, `protocol_scripts.py`.
  Removing the sweep collateral here is ~200 KB of import work saved at every boot.
- `autopilot/autopilot/hardware/` — remove `cameras.py`, `usb.py`, `unreal.py`; edit `i2c.py:8`.
  **`gpio.py`, `i2c.py`, `mixer.py`, `timer.py`, `__init__.py` and all five `external_hardware*`
  files stay** — required by `pilot.py:83`, `mics_task.py:3-6`, and by every DB-stored lib
  source, which imports back into `autopilot.hardware.*`.
- `autopilot/autopilot/core/` — remove `gui.py`, `terminal.py`, `plots.py`, `subject.py`,
  `styles.py`, `utils.py` (0 bytes), `reward.py`. **`pilot.py`, `loggers.py`, `View.py` stay.**
  Separately, `pilot.py` loses `open_file()` and the `self.h5f` cleanup at `:640-641` (ES is
  the sole data path, confirmed 2026-08-10) and the hardcoded `/home/liors/…` at `:49`.
- `autopilot/autopilot/{viz,data_handlers}/`, `utils/invoker.py`, `utils/Event.py` (singular —
  superseded by `Events.py`), `setup/request_helpers.py` — removed. **`setup/` otherwise stays:
  `autopilot/__init__.py:4` imports `setup_autopilot` unconditionally, so deleting it breaks
  `import autopilot` outright.**
- `terminal/`, `run_terminal.sh`, `.vscode/` — removed entirely.
- `autopilot/code_2023.deb` (87 MB), `autopilot/docs/`, `examples/`, `tests/`, `src/`,
  `home/`, `~/`, `auto_pi_lot.egg-info/`, upstream CI dotfiles, `Cow.wav`, the SoundBible wav —
  removed. **`LICENSE` (MPL-2.0) is mandatory and stays.**
- `autopilot/pytest.ini` — removed, **and a root pytest config added in the same change**, or
  the root suite (which currently relies on per-file `sys.path` hacks) has no config at all.
- `pilot/prefs.json` — templated. `pilot/data/`, `pilot/logs/` — contents dropped, paths kept
  (prefs auto-creates them at boot; `.gitkeep` + `.gitignore`).
- **`pilot/sounds/` stays untouched** — `mixer.py:18` resolves by bare filename through
  `SOUNDDIR`, so an unreferenced-looking wav can still be a live cue.
- Commented-out rows: ~244 lines across `station.py` (52), `message.py` (50), `gpio.py` (28),
  `task.py` (28) and 11 smaller files. `mics_task.py` yields only 11 — it is the cleanest large
  file in the tree, contrary to expectation.

**Held pending user decision — do not delete in this phase:** the touch-sensor calibration
constant `0x3f` (vs the live `0x08`, an ~8× lick-sensitivity difference), the IR1–IR7 trigger
registrations, the `OG_TRIGGER` optogenetics pulse, and the silenced handshake-watchdog
warnings. Each encodes hardware knowledge recorded nowhere else.

**Separate defects surfaced by the audit, to be fixed but not silently folded in here:**
- `mics_task.py:1589` imports `autopilot.autopilot.core.pilot`, a path that does not resolve —
  so **`LOAD_HARDWARE_LIBS` silently fails whenever a task is running**, the exception dying
  unhandled in the `Net_Node` listen thread. This undercuts the mechanism the whole
  hardware-centralization arc depends on.
- `pilot.py:1137-1148` — NTP enable and clock-freeze call sites are both commented out while
  the methods stay live. **Confirmed 2026-08-10 as a regression, not a decision: restore, do
  not delete.** Timing integrity on a rig that timestamps behavioural events.
- `i2c.py:819` — `except(e):` references an undefined name, so MPR121 init failures raise
  `NameError`. `i2c.py` is off-limits under TRIGA-12, so this needs its own decision.
- `pilot.py:887` calls `get_hardware_class(...)`, defined nowhere; `STREAM_VIDEO` raises.
- The Pi has **no `TASK_ERROR` emitter at all**, so a failed START is invisible: the run stays
  `running` in the DB forever. This is the phase's dominant risk multiplier and the reason
  criterion 1 is a live-session proof rather than an import check.

**Verification posture:** the agent edits only `/home/ido/pi-mirror`, runs `python3 -m
py_compile` (the `autopilot` package cannot be imported on this host — `npyscreen` is absent),
and runs **no git command inside the mirror**. Deployment to the Pi and the Pi test suite are
**USER-RUN**. The agent does not start or stop the pilot. The rig checkpoint is non-autonomous.

> **Rollout note.** `tools/sync_pi.sh` syncs only `autopilot/` and passes no `--delete`, and
> never touches `pilot/`. Two consequences: nothing removed here can break the live Pi, and —
> more importantly — **the cleaned repo cannot remove stale files from the Pi either.** Deleted
> plugins will linger on the device and keep being swept into every HANDSHAKE until removed by
> hand. Device reconciliation is an explicit, user-run step, not a side effect of deploying.

> **Read before any rig work on pilot 1.** The Phase 18 demo fixture `ExtlinkDemo` (module 62,
> `role: router_bind`, `required: true`) is still assigned to toolkit 100 and configured on
> pilot 1, so every real session there preflight-fails or hangs the full 30 s timeout; a TCP
> echo listener on the dev host at `132.77.73.125:5597` is a second standing dependency.
> Teardown is recorded in `18-HARDWARE-VALIDATION.md` §3. Clear this before criterion 1.

### Phase 31: mics_core Modern Pi Platform - Bookworm 64-bit, Python 3.11, correct clock, unattended boot

> **REVISED 2026-08-17 — the lgpio migration was removed from this phase.** A hardware audit found
> that under lgpio a GPIO line cannot be output-claimed and alert-claimed simultaneously, so every
> `Digital_Out` on the rig would lose its hardware-timestamped edge events. See
> `phases/31-.../31-REVISED-SCOPE.md`, which supersedes the lgpio parts of `31-RESEARCH.md`.

**Goal:** A researcher takes a Pi 4B with a stock Raspberry Pi OS Lite 64-bit (Bookworm) card,
runs one installer script from a `mics_core` clone, reboots, and the pilot comes up on its own
and connects to the backend — no `./run_pilot.sh`, no SSH step, no lab-built SD image. The event
clock becomes correct and safe for 24/7 continuous operation, with hardware-captured GPIO
timestamps preserved exactly as today.

**Requirements**: PLAT-01 through PLAT-11, PLAT-17 through PLAT-32
(PLAT-12 through PLAT-16 deferred — they are the lgpio rewrite; **PLAT-33 WITHDRAWN 2026-08-17** — the
user chose to leave the `pigpiod` spawn in the pilot, because `external.start_pigpiod()`'s `kill_proc`
hook is what closes the solenoids when a session ends, and a supervised daemon would outlive a
crashed pilot with `VALVE1-4`/`AIR_PUF`/`ODOR1-5` still open)
**Depends on:** Phase 30 (published the `mics_core` tree this phase modifies)
**Plans:** 6/13 plans executed

**Repo boundary:** all code changes land in `~/mics_core` on the dedicated feature branch
**`phase-31-modern-pi-platform`**, never in `mics-backend`. Planning docs stay here. Plan 01 cuts
the branch and **publishes it** (`git push -u origin phase-31-modern-pi-platform`) to
`git@github.com:idopo/mics_core.git` (private; default branch `main`), so the whole phase lives on
a remote branch and `main` is never contaminated. Every plan asserts the current branch before it
commits. No pushes to `main`, no merges into `main`, no force-pushes — integration to `main` is the
user's decision after the C4 acceptance gate, and is out of scope here.

**Scope — three stages:**

1. *Shed what is already dead.* Remove the on-device HDF5/`TrialData` path, the unused port
   calibration routine, and the setup-wizard GUI dependencies. Drops 37 pinned packages to a small
   audited set. Runs on the current system; makes stages 2 and 3 materially smaller.
2. *OS + Python bump.* Raspberry Pi OS Lite 64-bit (Bookworm), Python 3.11. Source impact is
   ~10 lines (numpy alias renames, `setDaemon` → `.daemon`). Deliver `install.sh` (apt packages,
   dtparams, groups, venv, deps, stock pigpio), systemd units for unattended start, and
   `/boot`-partition config so a rig is provisioned without SSH.
3. *Clean-room clock layer.* Delete the vendored patched `pigpio.py`, pin stock upstream pigpio,
   and move all timestamping into a MICS-owned module: 64-bit tick extension, one shared calibrated
   mapping read by both event paths, explicit provenance and loud failures. The `pigpiod` daemon is
   still spawned by the pilot (PLAT-33 withdrawn 2026-08-17 — the spawn's `kill_proc` hook is the
   rig's output fail-safe).

**24/7 timing safety (the phase's central goal):** the deployed patched pigpio client is already
broken in production. Its callback thread has its own converter with **no wrap detection**
(`pigpio.py:1206-1207`) and holds the sync offset **by value** (`:5264` → `:1157`), so the
wrap-detecting re-sync on the `pi` object never reaches it. The tick is a 32-bit microsecond field
in the notification protocol, so it wraps every 71.6 minutes — and on each wrap every GPIO event
timestamp **jumps backwards by 4294.97 s**, silently, ~20 times a day. `Event_Dispatcher` goes
through the `pi` object and *does* re-sync, so after the first wrap the two event paths are on
different clocks. That is the defect this phase fixes. Every one of those lines is an Autopilot
patch, not upstream pigpio; the `pigpiod` DMA sampler is stock and not implicated.

**Pi 5 forward-compatibility:** deferred to its own phase, targeting the RP1 **PIO** block (which
can drive *and* timestamp with cycle-exact hardware timing, no wires) rather than lgpio. Accepted
standing risk: pigpio is unmaintained. Mitigated by the clock layer being library-independent.

**Acceptance gate:** a clock soak — ≥3 tick wraps (>3.6 h) under CPU load, with a forced wall-clock
step forwards and backwards mid-run, asserting monotonicity, zero backward jumps, cross-path
agreement on the same edge, correct provenance flags, and zero undetected dropped samples; plus a
paired before/after pulse-timing capture showing no regression. The live rig is not touched; all
work happens on spare hardware.

Plans:
- [ ] 31-01-PLAN.md — Wave 0: feature branch, dev-host test harness, fake pigpio notification stream, pytest baseline
- [ ] 31-02-PLAN.md — Stage 1: shed HDF5/TrialData, port calibration, setup wizard, dead audio
- [ ] 31-03-PLAN.md — Stage 1: Python 3.11 source compat + audited dependency floor (incl. stock pigpio pin)
- [ ] 31-04-PLAN.md — Stage 2: prefs.template.json + /boot/firmware/mics.conf rendering
- [ ] 31-05-PLAN.md — Stage 2: systemd units (no `pigpiod` unit — PLAT-33 withdrawn), chrony drop-in, volatile journald
- [ ] 31-06-PLAN.md — Instrument: pulse-timing capture/analyse harness + gate (proves the clock fix)
- [ ] 31-07-PLAN.md — Stage 2: install.sh / uninstall.sh (owns the box)
- [ ] 31-08-PLAN.md — USER-RUN: Buster timing baseline + 71.58 min wrap demonstration + LA calibration
- [ ] 31-09-PLAN.md — USER-RUN: unattended-boot proof on a stock Bookworm 64-bit card
- [ ] 31-C1-PLAN.md — Stage 3: clock module — 64-bit wrap extension, heartbeat, calibrated mapping, loud failures
- [ ] 31-C2-PLAN.md — Stage 3: assign_cb adapter — one clock on both event paths, localize_tz contract, provenance
- [ ] 31-C3-PLAN.md — Stage 3: cut over to stock pigpio (the `start_pigpiod()` spawn STAYS), chrony on, clock-freeze block deleted + F3 retired
- [ ] 31-C4-PLAN.md — Acceptance: clock soak under load + forced clock step + paired capture (USER-RUN)

**Deferred to a future phase (the lgpio rewrite):** PLAT-12 (gpiochip by label), PLAT-13 (I²C to
lgpio), PLAT-14 (edge detection to `gpio_claim_alert`), PLAT-15 (tx_wave/tx_pulse output port),
PLAT-16 (pigpio lifecycle removal). Old plans 31-10 through 31-16 are superseded; their clock
substance moved into C1-C4.


---
*Created: 2026-03-15*
*Last updated: 2026-05-28 — Phase 17 added: free-form pilot hardware config CRUD (HW-08, HW-11)*
