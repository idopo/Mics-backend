# Requirements: MICS Backend

**Defined:** 2026-03-15
**Core Value:** Researchers can define, modify, and deploy behavioral task logic without writing Python or restarting the Pi.

---

## v1 Requirements

### FDA Foundation (Pi)

- [ ] **FDA-01**: Pi can start a task with `state_machine` kwarg containing v2 FDA JSON, producing identical behavior to the hardcoded version
- [ ] **FDA-02**: `load_fda_from_json()` in `mics_task` handles both v1 (states list) and v2 (states object with entry_actions) formats
- [ ] **FDA-03**: State entry_actions are executed in order: hardware calls via semantic ref, flag updates, timer calls, special actions (INC_TRIAL_COUNTER), custom toolkit method calls
- [ ] **FDA-04**: SEMANTIC_HARDWARE dict maps friendly names to (group, id) tuples; entry actions use `ref` not `hardware['group']['id']`
- [ ] **FDA-05**: Arg values in entry_actions resolve correctly: literal, `{"param": "name"}`, and `{"flag": "name"}` forms
- [ ] **FDA-06**: `blocking: "stage_block"` causes state to call `wait_for_condition()` (yield loop); `blocking: null` returns immediately
- [ ] **FDA-07**: `return_data` dict is collected after entry_actions and sent as DATA event; supports flag/param/now() value forms
- [x] **FDA-08**: `validate_fda.py` CLI tool exits 0 on valid JSON, exits 1 with specific error for unknown state names / unknown refs / unknown params / unknown callable_method refs
- [x] **FDA-09**: `tools/sync_pi.sh` rsyncs autopilot/ to Pi; `tools/deploy_pi.sh` syncs and restarts pilot
- [ ] **FDA-10**: A state with no `entry_actions` in JSON uses the existing Python toolkit method of that name as a passthrough; `_build_state_method` returns `getattr(self, name)` directly
- [ ] **FDA-11**: `type: "method"` entry_action calls `getattr(self, ref)(*args)` where `ref` must be in toolkit's `CALLABLE_METHODS` list; raises descriptive error at load time if not
- [x] **FDA-12**: `CALLABLE_METHODS` class attr on toolkit declares Python methods usable as entry_action building blocks; included in HANDSHAKE payload and stored in `task_toolkits.callable_methods`
- [x] **FDA-13**: `SEMANTIC_HARDWARE_RENAMES` class attr maps deprecated semantic names to their current replacement; `load_fda_from_json()` resolves old refs transparently via this map; HANDSHAKE includes the map so Phase 2 can detect stale refs in stored task_definitions
- [x] **FDA-14**: `validate_fda.py rename-hw-ref <old> <new> --toolkit <ClassName>` command performs a SQL UPDATE on all `task_definitions.fda_json` rows that reference old name, prints count of updated rows, exits 0 on success
- [ ] **FDA-15**: `load_fda_from_json()` sets `self.<param_name> = resolved_value` for every param after resolution, so toolkit Python methods can use `self.open_duration` directly
- [ ] **FDA-16**: `_build_state_method()` handles `type: "if"` action recursively — evaluates condition at state entry, executes `then` or `else` branch; `then`/`else` can themselves contain nested `if` actions
- [x] **FDA-17**: `validate_fda.py` traverses `if` action blocks recursively; validates `condition.left` and `condition.right` refs against known FLAGS/PARAMS/SEMANTIC_HARDWARE; exits 1 with specific error for unknown ref

### Trigger Assignments (Pi)

- [ ] **TRIG-01**: `apply_trigger_assignments()` reads `trigger_assignments` from FDA JSON and appends handlers to `self.triggers[pin]`
- [ ] **TRIG-02**: `touch_detector` handler calls `hw.detect_change()`, updates `view[LICKER{n}]`, optionally emits CONTINUOUS — does NOT replace the existing `handle_trigger` path
- [ ] **TRIG-03**: `digital_input` handler updates `view[view_key]` with current GPIO level — logging still fires unconditionally via `execute_trigger()`
- [ ] **TRIG-04**: If `trigger_assignments` is absent from FDA JSON, `self.triggers` is unchanged (backward compatible)
- [ ] **TRIG-05**: All trigger hardware continues to dispatch `Hardware_Event` via `execute_trigger()` regardless of trigger_assignments configuration

### Hot-Reload (Pi + Orchestrator)

- [x] **HOT-01**: Orchestrator `_build_step_task()` includes `state_machine` from task definition's `fda_json` in every START payload (Phase 2); Pi calls `load_fda_from_json()` at task start — changes take effect on next run without Pi restart
- [x] **HOT-02**: HANDSHAKE payload from Pi includes FLAGS, SEMANTIC_HARDWARE, STAGE_NAMES, CALLABLE_METHODS, REQUIRED_PACKAGES in addition to existing fields; stored in `task_toolkits` table

### Variant Tracking (VAR)

| ID | Requirement | Phase |
|---|---|---|
| VAR-01 | Toolkit identity is `(name, hw_hash)` — same name + same SEMANTIC_HARDWARE = same record; same name + different hardware = separate record | 2 |
| VAR-02 | HANDSHAKE with a new hw_hash for an existing toolkit name creates a new `task_toolkits` row (never overwrites) | 2 |
| VAR-03 | `toolkit_pilot_origins` table tracks `(toolkit_id, pilot_id, first_seen_at, last_seen_at)` — upserted on every HANDSHAKE | 2 |
| VAR-04 | `GET /api/toolkits` returns toolkits grouped by name; each variant includes hw_hash, pilot_origins, fda_count | 2 |
| VAR-05 | `GET /api/toolkits/{id}/diff/{other_id}` returns added/removed/changed keys in SEMANTIC_HARDWARE | 2 |
| VAR-06 | FDA creation GUI shows explicit variant picker (with hw diff) when 2+ variants exist for a toolkit name | 3 |
| VAR-07 | `PATCH /api/toolkits/{id}/set-canonical` marks one variant canonical; FDAs bound to others flagged `needs_migration=true` | 4 |

### DB + API (Backend)

- [x] **DB-01**: `task_toolkits` table created; HANDSHAKE handler writes toolkit metadata (states, flags, params_schema, semantic_hardware, callable_methods, required_packages, file_hash)
- [x] **DB-02**: `task_definitions` table extended with `toolkit_name`, `fda_json` (JSONB), `display_name` columns; migration uses IF NOT EXISTS
- [x] **DB-03**: `GET /api/toolkits` returns list of toolkits per pilot with all metadata needed by GUI
- [x] **DB-04**: `GET /api/toolkits/:name` returns full toolkit detail
- [x] **DB-05**: `POST /api/task-definitions` creates task definition from toolkit + FDA JSON + default_params
- [x] **DB-06**: `GET/PUT/DELETE /api/task-definitions/:id` CRUD with full fda_json
- [x] **DB-07**: `POST /api/task-definitions/:id/push?pilot=name` forwards UPDATE_FDA to named pilot via orchestrator; returns HOT_RELOAD_ACK status
- [x] **DB-08**: Orchestrator `_build_step_task()` includes `state_machine` from task definition's fda_json in START payload

### Visual FDA Editor (Web UI)

- [ ] **UI-01**: `/react/task-editor/:id` page loads toolkit metadata and task definition from API
- [ ] **UI-02**: react-flow canvas shows states as nodes, transitions as directed edges; drag-to-connect creates transitions
- [ ] **UI-03**: Clicking a transition edge shows condition builder in right panel: view key dropdown + op dropdown + literal/param/flag value input
- [ ] **UI-04**: Clicking a state node shows state body editor: entry_actions list with add/remove/reorder, blocking toggle, return_data list
- [ ] **UI-05**: "Add action" picker: hardware (semantic ref dropdown + method + args), flag, timer, special (INC_TRIAL_COUNTER), custom method (callable_methods dropdown + optional args)
- [ ] **UI-05a**: Passthrough state nodes (no entry_actions, backed by Python method) shown with lock icon and `{py}` badge; state body panel is read-only for these
- [ ] **UI-06**: Arg inputs are smart: toggle between literal / param-ref / flag-ref modes
- [ ] **UI-07**: Trigger assignment panel (separate tab): shows all trigger hardware, dropdown for handler type (default/touch_detector/digital_input), config fields; note that logging is always automatic
- [ ] **UI-08**: Semantic hardware overrides panel: optional per-task-definition overrides of toolkit's SEMANTIC_HARDWARE
- [ ] **UI-09**: "Push to Pilot" button only enabled when a pilot is running this task definition; calls push endpoint; shows toast on success
- [ ] **UI-10**: Save button serializes canvas + state body + trigger assignments to FDA JSON v2 and calls PUT /api/task-definitions/:id
- [ ] **UI-11**: State body panel "Add action" picker includes "If Condition" option; creates an `if` block with empty `then`/`else` lanes; lanes accept any action type including nested ifs
- [ ] **UI-12**: Condition builder widget: left-side dropdown (tracker/flag/param/hardware), op dropdown (`==` `!=` `>=` `<=` `>` `<`), right-side (literal input OR ref picker matching left types)

### Protocol Integration (Web UI + Backend)

- [x] **PROTO-01**: Protocol step picker in `/react/protocols-create` shows named task definitions instead of raw task_type strings; params come from linked toolkit's `params_schema`
- [x] **PROTO-02**: Protocol step stores `task_definition_id`; session start resolves `fda_json` from that ID and includes it in START payload
- [x] **PROTO-03**: `GET /api/tasks/leaf` deprecated; `GET /api/task-definitions` used instead
- [x] **PROTO-04**: Overrides modal in pilot sessions uses toolkit `params_schema` (via task definition) as param spec, falling back to existing `task.default_params` when `task_definition_id` is absent

### Pi Code Editor — Viewer (Phase A)

- [ ] **EDIT-01**: `GET /api/pi/status` returns `{connected: bool, pilot_state: str|null}` within 2s; JWT required
- [ ] **EDIT-02**: `GET /api/pi/files?path=...` returns `[{name, type, size, mtime}]`; filters __pycache__/.pyc/.git; returns 403 if path outside PI_EDITOR_ROOTS
- [ ] **EDIT-03**: `GET /api/pi/file?path=...` returns `{content, language}`; 404 if not found; 403 if outside roots
- [ ] **EDIT-04**: `web_ui/pi_ssh.py` module with asyncssh cached connection pool; auto-reconnects on next request
- [ ] **EDIT-05**: `/react/pi-editor` page with `PiFileBrowser` (tree, lazy expand), `MonacoEditorPanel` (read-only), `PiStatusBar`
- [ ] **EDIT-06**: `@monaco-editor/react` added to package.json; dynamically imported (React.lazy) to avoid bundle bloat

### Pi Code Editor — Terminal (Phase B)

- [ ] **EDIT-07**: `POST /api/pi/exec` runs command on Pi; returns stdout/stderr/exit_code; 403 unless ALLOW_PI_EXEC=true
- [ ] **EDIT-08**: `WS /ws/pi/exec` streams stdout/stderr lines in real-time; sends `{exit_code: n}` on completion; 403 unless ALLOW_PI_EXEC=true
- [ ] **EDIT-09**: `PiTerminal` component using xterm.js renders streamed output; input bar accepts `!command`; ANSI colors rendered
- [ ] **EDIT-10**: All exec endpoints return 403 when ALLOW_PI_EXEC not set; UI shows "Developer mode not enabled" tooltip

### Pi Code Editor — Edit + Restart (Phase C)

- [ ] **EDIT-11**: `PUT /api/pi/file` writes `{path, content}` to Pi via SFTP; 403 if outside roots or ALLOW_PI_EXEC not set
- [ ] **EDIT-12**: `POST /api/pi/restart` restarts pilot process via SSH; restart command configurable via PI_RESTART_CMD env var
- [ ] **EDIT-13**: Monaco editor switches to editable mode on "Edit" button; dirty indicator; "Save" writes via PUT; "Discard" reverts
- [ ] **EDIT-14**: Unsaved changes trigger `beforeunload` browser guard

### Pi Code Editor — Sync + Packages (Phase D)

- [ ] **EDIT-15**: `GET /api/pi/packages` returns installed vs required packages (cross-references task_toolkits.required_packages)
- [ ] **EDIT-16**: `POST /api/pi/packages` installs package on Pi via pip; streams output
- [ ] **EDIT-17**: Packages tab UI shows required-by-toolkits diff and manual install input

### Hardware Libs (Backend)

| ID | Requirement | Phase |
|---|---|---|
| HW-01 | `hardware_libs` table: `id, name, filename, source_code TEXT, ast_metadata JSONB, version INT, validated BOOL, created_at, updated_at`; `ast_metadata` shape: `{classes: [{name, methods: [{name, args: [{name, annotation, default}]}]}]}` | 9 |
| HW-02 | `POST /api/hardware-libs` validates Python source via `ast.parse()` + `py_compile.compile()` server-side; rejects with 422 + error location if invalid; extracts AST metadata on success | 9 |
| HW-03 | `GET /api/hardware-libs`, `GET /api/hardware-libs/{id}`, `PUT /api/hardware-libs/{id}`, `DELETE /api/hardware-libs/{id}` standard CRUD in `api/routers/hardware_libs.py` | 9 |
| HW-04 | Orchestrator sends `LOAD_HARDWARE_LIBS` ZMQ message before `START` when toolkit has associated libs; payload: `{libs: [{filename, source_code}]}` | 9 |
| HW-05 | Pi `receive_hardware_libs(libs)` in `mics_task.py`: writes each lib to `~/apps/hardware_overrides/`, prepends dir to `sys.path`, calls `importlib.reload()` if module already cached; backward compat: no-op if no message received | 9 |

### Hardware Modules (Backend + UI)

| ID | Requirement | Phase |
|---|---|---|
| HW-06 | `hardware_modules` table: `id, name, display_name, hardware_lib_id FK, class_name TEXT, description, created_at`; create/update validates `class_name` exists in linked lib's AST metadata | 10 |
| HW-07 | Standard CRUD at `/api/hardware-modules`; `GET /api/hardware-modules/{id}/methods` returns method list from linked lib's AST for the specific `class_name` | 10 |
| HW-08 | `pilot_hardware_config` table: `id, pilot_id FK, hardware_module_id FK, config JSONB`; `GET /api/pilots/{id}/hardware-config`, `PUT /api/pilots/{id}/hardware-config/{module_id}` | 10 |
| HW-09 | HANDSHAKE handler reads prefs.json HARDWARE section from payload and POSTs to `/api/pilots/{id}/hardware-config/seed` if pilot has no config yet (one-time migration seeder) | 10 |
| HW-10 | New React page `/react/hardware-modules-ui`: list modules with lib + class chip; create module form (name + pick lib + pick class from AST dropdown); nav entry in `Layout.tsx` | 10 |
| HW-11 | Per-pilot hardware config editor (on pilot detail or new page): table of module | class | config fields; config fields are dynamic from class constructor args in AST metadata | 10 |

### Toolkit Redesign (Backend-Authored)

| ID | Requirement | Phase |
|---|---|---|
| HW-12 | `task_toolkits` extended with: `hardware_module_ids INT[]`, `locked_state_source TEXT`, `is_backend_authored BOOL DEFAULT FALSE`; existing HANDSHAKE-registered toolkits remain valid | 11 |
| HW-13 | `available_locked_states` table: `id, pilot_id FK, task_filename TEXT, state_names TEXT[], updated_at`; populated by HANDSHAKE from `{tasks: [{filename, state_names}]}`; `GET /api/locked-states` returns state libraries grouped by task file | 11 |
| HW-14 | `POST /api/toolkits` with `{name, locked_state_source, selected_states, hardware_module_ids, flags, params_schema}` validates states exist in `available_locked_states` and all hardware_module_ids exist; sets `is_backend_authored=TRUE` | 11 |
| HW-15 | HANDSHAKE updated to accept new format `{tasks: [{filename, state_names}]}`; legacy format still accepted (old Pis continue to work) | 11 |
| HW-16 | Toolkit page redesigned: 5-step authoring flow (name+task file, select locked states, add hardware modules, define flags, define params); existing auto-registered toolkits show with "legacy" badge | 11 |

### Hardware-Aware FDA State Builder

| ID | Requirement | Phase |
|---|---|---|
| HW-17 | State builder `StateBodyPanel`: when adding `type: hardware` entry action, dropdown shows hardware modules from toolkit's `hardware_module_ids`; on module select, methods fetched from `GET /api/hardware-modules/{id}/methods`; arg inputs pre-filled with type annotations and defaults | 12 |
| HW-18 | `PUT /api/hardware-libs/{id}`: re-extracts AST, diffs methods vs previous version, scans all `task_definitions.fda_json` for references to removed/renamed methods, sets `validation_status='broken'` + `validation_message` on affected rows; returns diff summary | 12 |
| HW-19 | `task_definitions` gains `validation_status TEXT DEFAULT 'ok'` and `validation_message TEXT` columns | 12 |
| HW-20 | TaskDefinitions list: warning badge on broken definitions; TaskEditor: banner at top listing specific broken state + method name when `validation_status='broken'` | 12 |

### Pre-Run Cross-Check + End-to-End

| ID | Requirement | Phase |
|---|---|---|
| HW-21 | `POST /api/task-definitions/{id}/validate-for-pilot/{pilot_id}`: checks each hardware module in toolkit has pilot config, class matches, config complete; returns `{ok: bool, issues: [{module_name, issue, detail}]}` | 13 |
| HW-22 | Session start UI calls validate-for-pilot before confirming START; if issues: modal lists problems with links to pilot hardware config editor; if ok: proceed | 13 |
| HW-23 | Orchestrator sends resolved hardware config dict `{module_name: {class_name, pin, polarity, ...}}` to Pi before START; Pi `init_hardware()` uses received config if present, falls back to `self.HARDWARE` class constant if absent | 13 |
| HW-24 | Pi `init_hardware()` accepts `received_hw_config` kwarg: dynamically imports `{lib_module}.{class_name}` from override dir, instantiates with config params, stores in `self.hardware` dict (same structure, no downstream breakage) | 13 |

---

## v2 Requirements

### FDA Extensions

- **FDAV2-01**: OR conditions between transitions (currently AND-only)
- **FDAV2-02**: Conditional branching within a state body (`if` action type)
- **FDAV2-03**: Toolkit composition (combining methods from two toolkits)
- **FDAV2-04**: Hardware profiles JSON per rig (enables same FDA JSON on different hardware layouts)
- **FDAV2-05**: FDA JSON v1→v2 auto-upgrade script

### Editor Extensions

- **UIV2-01**: Undo/redo in the FDA editor
- **UIV2-02**: FDA diff view (before/after hot-reload)
- **UIV2-03**: Rate-limiting hot-reload pushes per session

### Pi Editor Extensions

- **EDITV2-01**: Multi-Pi support (pilot selector dropdown, PI_HOSTS env var list)
- **EDITV2-02**: Audit log of who saved/exec'd what on the Pi
- **EDITV2-03**: "Save + Validate" integrated button (runs validate_fda.py after save, shows Monaco diagnostics)
- **EDITV2-04**: Read-only mode for non-admin JWT claims

---

## Out of Scope

| Feature | Reason |
|---|---|
| Jupyter/JupyterLab on Pi | Too heavy (1GB+ RAM), wrong paradigm for .py task files |
| code-server (VS Code in browser) on Pi | Too heavy, not viable on Pi hardware |
| exec() / cloudpickle for state bodies | Serializable action JSON is sufficient; no arbitrary code execution in hot-reload path |
| Parallel sub-states / hierarchical FSM | Not needed for current experiments; complexity cost too high |
| Real-time collaborative editing | Single editor per session is fine for lab context |
| FDA editor undo/redo | Deferred to v2 |

---

## Traceability

| Requirement | Phase | Status |
|---|---|---|
| FDA-01 through FDA-17 | Phase 1 (Pi Foundation) | Pending |
| TRIG-01 through TRIG-05 | Phase 1 (Pi Foundation) | Pending |
| HOT-01 through HOT-02 | Phase 1–2 (Pi Foundation + DB) | Pending |
| VAR-01 through VAR-05 | Phase 2 (DB + API) | Pending |
| VAR-06 | Phase 3 (Visual Editor) | Pending |
| VAR-07 | Phase 4 (Protocol Integration) | Complete |
| DB-01 through DB-08 | Phase 2 (DB + API) | Pending |
| UI-01 through UI-12 | Phase 3 (Visual Editor) | Pending |
| PROTO-01 through PROTO-04 | Phase 4 (Protocol Integration) | Pending |
| EDIT-01 through EDIT-06 | Phase 5 (Pi Editor: Viewer) | Pending |
| EDIT-07 through EDIT-10 | Phase 6 (Pi Editor: Terminal) | Pending |
| EDIT-11 through EDIT-14 | Phase 7 (Pi Editor: Edit+Restart) | Pending |
| EDIT-15 through EDIT-17 | Phase 8 (Pi Editor: Sync+Packages) | Pending |
| HW-01 through HW-05 | Phase 9 (HardwareLib Storage + E2E Proof) | Pending |
| HW-06 through HW-11 | Phase 10 (Hardware Modules + Pilot Config) | Pending |
| HW-12 through HW-16 | Phase 11 (Toolkit Redesign: Backend-Authored) | Pending |
| HW-17 through HW-20 | Phase 12 (Hardware-Aware FDA State Builder) | Pending |
| HW-21 through HW-24 | Phase 13 (Pre-Run Cross-Check + End-to-End) | Pending |

**Coverage:**
- v1 requirements: 86 total (HW-01–24 added for Hardware Libs Centralization + Hardware Modules + Toolkit Redesign)
- Mapped to phases: 86
- Unmapped: 0 ✓

---
*Requirements defined: 2026-03-15*
*Last updated: 2026-03-15 after GSD initialization*
