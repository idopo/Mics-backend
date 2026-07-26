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

## Bug Fix Requirements

### Toolkit Creation Modal (Phase 14-03)

| ID | Requirement | Phase |
|---|---|---|
| BUG-05 | Toolkit creation wizard skips the locked-states step (step 2) when no source file is selected — the user lands directly on the hw-modules step | 14 |
| BUG-06 | Toolkit creation auto-links all existing hardware libraries with their default version (stable if set, latest active otherwise); no manual selection step required | 14 |
| BUG-07 | `POST /api/toolkits/{id}/hardware-libs` returns 200 through the web_ui proxy (`:8080`); route was missing from `web_ui/app.py` causing 404 | 14 |

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
| BUG-01 through BUG-02 | Phase 14, Plan 1 (Small Bug Fixes Batch 1) | Complete |
| BUG-03 through BUG-04 | Phase 14, Plan 2 (Hw-lib Warning Badge Fixes) | Complete |
| BUG-05 through BUG-07 | Phase 14, Plan 3 (Toolkit Creation Modal UX Fixes) | Pending |

### Compound Transition Conditions

| ID | Requirement | Phase |
|---|---|---|
| COND-01 | Transition edges support compound boolean conditions expressed as DNF (OR of AND-groups); empty condition_groups = unconditional | 15 |
| COND-02 | UI: Kibana-style filter builder in edge panel — condition rows with left-operand/op/right-operand selectors, +AND within group, +OR adds new group | 15 |
| COND-03 | Legacy transitions using flat `conditions[]` auto-migrate to `condition_groups` on editor open; re-save always writes `condition_groups` | 15 |
| COND-04 | Pi evaluates `condition_groups` as `any(all(c() for c in g) for g in groups)`; falls back to legacy `conditions[]` if `condition_groups` absent | 15 |
| COND-05 | Edge label renders compound expressions as human-readable `a ∧ b ∨ c` notation | 15 |
| COND-06 | `FdaTransition` gains `condition_tree?` field: recursive `ConditionNode` (leaf = `FdaCondition`; branch = `{op:'AND'|'OR', children:ConditionNode[]}`); `condition_groups` and `conditions[]` are legacy fallbacks | 16 |
| COND-07 | Migration chain in `normaliseTransition()`: `conditions[]` → single AND-leaf; `condition_groups` → OR-of-AND-nodes tree; `condition_tree` used as-is; re-save always writes `condition_tree` | 16 |
| COND-08 | Per-row +AND and +OR buttons (Kibana FiltersBuilder model): +AND appends sibling in same AND-context; +OR appends at OR level; depth-based background shading distinguishes nesting levels | 16 |
| COND-09 | Pi `_build_tree_lambda(node)` evaluates `condition_tree` recursively: leaf → `_build_transition_lambda`; AND-node → `all()`; OR-node → `any()`; fallback chain: `condition_tree` → `condition_groups` → `conditions[]` | 16 |
| COND-10 | `condLabel()` renders tree with parentheses where needed: `(A ∨ B) ∧ C` when OR is child of AND; omits parens for flat structures | 16 |

### External Software Integration (MICS-Link)

| ID | Requirement | Phase |
|---|---|---|
| EXTLINK-01 | Each `ExternalHardware` instance binds its OWN ZMQ ROUTER socket on the `listen_port` declared in its `pilot_hardware_config.config` row; runs on the task's Tornado IOLoop alongside the orchestrator DEALER (no new thread). One module = one socket = one port. | 18 |
| EXTLINK-02 | The external SDK on the remote computer connects with ZMQ DEALER using `identity = source_id` (also from `pilot_hardware_config.config`). The Pi rejects any DEALER frame whose identity ≠ the configured `source_id` for that socket. | 18 |
| EXTLINK-03 | Wire protocol uses MessagePack envelope with kind discriminator: `SIG` (signal update), `EVT` (event with payload), `HB` (heartbeat), `ACK` (command result); Pi-outbound `CMD` (command invocation) | 18 |
| EXTLINK-04 | `ExternalHardware` base class supports `@signal(default, stale_after_ms, stale_policy)`, `@event(payload)`, `@command` decorators that declare the wire contract once per class | 18 |
| EXTLINK-05 | Each `@signal` auto-registers a View Tracker named `<source_id>.<signal_name>`; FDA reads via existing `view.get_value(...)` API with zero new call sites | 18 |
| EXTLINK-06 | Per-signal stale policy enforced on every read: `hold_last` returns cached value, `return_default` returns the declared default, `return_none` returns None | 18 |
| EXTLINK-07 | Per-source liveness: heartbeat-driven `<source_id>.alive` boolean tracker flips false after `stale_ms` (from per-pilot config) since last HB; flip emits a CONTINUOUS event for ES | 18 |
| EXTLINK-08 | Ingress validation: messages whose `sig`/`evt`/`cmd` name is not declared in the corresponding `ExternalHardware` subclass are dropped + logged; no exception ever propagates into the Tornado IOLoop | 18 |
| EXTLINK-09 | The hardware-libs AST extractor (`api/routers/hardware_libs.py` — Phase 9 plumbing) recognises `@signal` / `@event` / `@command` decorators and includes them in the lib's `ast_metadata`; downstream toolkit dispatch (Phase 11) treats `ExternalHardware` subclasses no differently — same `HARDWARE` + `PREFS_HARDWARE` dispatch shape, the `config` values differ but the wire is unchanged. The `extlink` block carries per-signal `dtype` (string name) and per-command `{args:[{name,dtype}], returns}` so FDA-editor and state-builder UIs (Phase 19+) can render typed forms without importing the lib | 18 |
| EXTLINK-10 | A `pilot_hardware_config` row for an external module carries `{class_name, listen_port, source_id, stale_ms}` in its `config` JSON (Phase 17 free-form schema — no new column, no new endpoint); preflight (Phase 13) validates `class_name` like any other module | 18 |
| EXTLINK-11 | Smoke test (`~/pi-mirror/scripts/dev/extlink_smoke.py`) demonstrates end-to-end: standalone DEALER script connects to the configured `listen_port` with the configured `source_id`, pushes `dlc_cam1.left_paw_x = 0.7`, an FDA transition lambda gated on `view.get_value("dlc_cam1.left_paw_x") > 0.5` advances the state machine | 18 |
| EXTLINK-12 | **Type contract.** Every `@signal` declares a value dtype (resolved at class-build time from the method's return annotation, with `type(default)` as fallback); allowed primitives: `int`, `float`, `bool`, `str`. The decorator raises `TypeError` at import time if neither annotation nor default provides a usable type. Every `@command` captures its parameter annotations + return annotation. At wire ingest, `_dispatch_sig` coerces incoming `v` via `spec.dtype(v)`; on `TypeError` / `ValueError` it increments `type_mismatch_count`, drops with a rate-limited log, and NEVER raises into the IOLoop. `bool` is special-cased — only `isinstance(raw, bool)` is accepted (no silent `float(True)` coercion). Same metadata is mirrored in `ast_metadata.extlink` for UI consumption (see EXTLINK-09) | 18 |
| EXTLINK-13 | **Readiness gate.** Per-source `required: bool` (default `true`) and `wait_timeout_s: int` (default `60`, range `[5, 600]`, `null` REJECTED at config save and Pi-side init) live in `pilot_hardware_config.config`. When a task starts on a pilot with one or more required external sources, `mics_task` injects a synthetic `_wait_extlink_ready` FDA pre-state ahead of the user-declared initial state. The pre-state has THREE exits, in priority order: (a) **all required alive** → user's initial state (normal path); (b) **manual skip** via orchestrator-relayed `EXTLINK_SKIP_WAIT` ZMQ message → user's initial state (with a warning logged + CONTINUOUS event); (c) **timeout** at `max(wait_timeout_s)` across required sources → terminal `_extlink_timeout` state, session aborts cleanly with a `CONTINUOUS ExtlinkTimeout` event listing offline sources. The pre-state is NEVER installed when zero required sources exist (zero overhead for non-MICS-Link tasks). Three escape paths guarantee a task can never hang indefinitely: timeout (always, finite default), manual skip (operator override), and STOP button (existing path, always available). | 18 |

### Compute Primitives + Variables (CMP)

GUI-assembled FDA-JSON-v2 tasks gain value-producing computation (random draws, derived
numbers/booleans) that bridges state-entry → transition, without writing Python or editing
locked toolkit source. Design spec: `~/.claude/plans/i-realized-something-the-ancient-pnueli.md`.

| ID | Requirement | Phase |
|---|---|---|
| CMP-01 | FDA-JSON-v2 gains a top-level `variables` registry alongside `states`/`transitions`: `"variables": { "<name>": {} }`. Untyped generic scratch slots — a name is enough. | 23 |
| CMP-02 | At `load_fda_from_json()` each declared variable is instantiated as a generic `Tracker` (initial value `None`) and registered in BOTH `self.flags` and `self.view.view` — identical to `init_flags()` (mics_task.py:268-280). Transitions then read variables via the existing `{"view": name}` / `{"flag": name}` operand path with zero new read code. | 23 |
| CMP-03 | New entry-action `type: "compute"`: `{ "type": "compute", "op": "<primitive>", "args": [...], "output": "<var>" }`. `_build_action_callable()` resolves args via the existing `_resolve_arg` forms (literal / `{param}` / `{flag}` / variable), calls the named primitive, and `.set()`s the result into the `output` variable's Tracker. | 23 |
| CMP-04 | Curated compute primitive set (stdlib `random`/`math` + builtins only — always present on Pi, no package dependency): random/copy — `random_choice(list)`, `random_int(min,max)`, `random_float(min,max)`, `random_bool(p)`, `assign(value)`; numeric/util — `add(a,b)`, `subtract(a,b)`, `multiply(a,b)`, `divide(a,b)` (raise on /0), `modulo(a,b)` (raise on /0), `minimum(a,b)`, `maximum(a,b)`, `clamp(value,lo,hi)`. Numeric value-production only — no comparison/boolean-logic ops (branching stays in transitions; Phase 15 DNF composes booleans). A variable read back as an arg (`add(counter,1)→counter`) is the supported counter pattern (one reused slot). Implemented as pure functions in a new shared compute-primitives module on the Pi. | 23 |
| CMP-05 | Last-write-wins on re-entry: re-entering a state re-runs its compute action and overwrites the same variable slot (matches old instance-attribute behavior across trials). No reset between trials. | 23 |
| CMP-06 | Hot-reload path: new `variables` and `compute` actions flow through the existing `UPDATE_FDA` store; newly-added variables are instantiated as Trackers on reload before transitions referencing them are rebuilt. | 23 |
| CMP-10 | Backend `_validate_task_definition()` (api/routers/toolkits.py ~661) validates the `variables` registry: every `compute` `output` is declared in `variables`; every transition/condition reference to a variable resolves; rejects name collisions with toolkit `FLAGS`, `SEMANTIC_HARDWARE`, and view keys. | 23 |
| CMP-11 | `api/fda_utils.py` recursive ref scanner extended to cover `compute` `output` names (so lib/ref impact detection sees them). | 23 |
| CMP-12 | Shared compute library stored & versioned via the existing Phase-9 hardware-lib DB infra (a non-hardware library entry); AST extraction reused so the GUI knows each primitive's signature (name + args). No new table. | 23 |
| CMP-13 | GUI state-builder (Phase-12 `StateBodyPanel`): `compute` action editor (primitive picker from compute library + per-arg `ArgInput` + `output` field). Typing a new `output` name auto-declares it into the task's `variables` registry inline. | 23 |
| CMP-14 | GUI transition-condition builder: operand dropdown is populated from toolkit `FLAGS` + the task's `variables` registry, so a freshly-declared variable is immediately selectable as a condition operand. | 23 |
| CMP-15 | GUI validation surfacing (nice-to-have): warn in the editor when a transition reads a variable not written by any reachable upstream state's compute action. | 23 |

> **Deferred (not tracked):** the `expr` escape-hatch (former CMP-07–09 — a sandboxed restricted-AST expression evaluator with a `type:"expr"` action) was decoupled from Phase 23. With arithmetic/min/max/clamp now in the curated `compute` set, the library-backed primitives cover current needs; `expr` would only address the remaining long tail (multi-term expressions / boolean logic). It is documented in the design spec (`~/.claude/plans/i-realized-something-the-ancient-pnueli.md`) and can be re-added as its own phase if a concrete need arises.

### Trigger Assignment Action Lists (TRIGA)

A hardware trigger runs the same action vocabulary a state's `entry_actions` uses, assembled in
the task-editor UI instead of hard-coded as a Python method. Reference case: `learning_cage.detectedLick`.
Context: `.planning/phases/24-trigger-assignment-action-lists/24-CONTEXT.md`.

| ID | Requirement | Phase |
|---|---|---|
| TRIGA-01 | A `trigger_assignments` entry carries an ordered `actions` list using the **same action schema as state `entry_actions`**; each action is built through the existing `_build_action_callable` (`mics_task.py:524`) so `hardware` / `flag` / `timer` / `special` / `method` / `if` all work identically in a trigger and in a state body. Load-time `ValueError` on unknown type/ref is preserved. | 24 |
| TRIGA-02 | The composed trigger callable declares `level` / `tick` parameters so `execute_trigger`'s `inspect.signature` check (`task.py:286`) passes them, while the underlying action callables stay zero-arg. `_resolve_arg` (`mics_task.py:401`) gains a `{"trigger": "level"\|"tick"}` form so an action can consume the trigger invocation context. | 24 |
| TRIGA-03 | A `view` action type can write `self.view.view[key]` — the trackers created by `check_for_detectors` via `view.add_Tracker` live only in `self.view.view`, never in `self.flags`, so no existing action type can reach them. Supports passing `pi_timestamp`. | 24 |
| TRIGA-04 | A hardware/method action's **return value** can be captured into a named slot instead of being discarded (`_hw_call` currently drops it). The capture mechanism is shape-compatible with Phase 23's `variables` / `compute` `output` design — one mechanism, not two. | 24 |
| TRIGA-05 | The `detectedLick` pattern — choosing the target tracker from a value **returned** by the hardware call (`device_str = f"{device_name}{pin_number}"`) — is expressible from the UI. Approach selected and justified during planning (see 24-CONTEXT.md Open Decision 1). | 24 |
| TRIGA-06 | Backward compatibility: task definitions already stored in the DB keep loading and running. Absent/empty `trigger_assignments` leaves `self.triggers` untouched (existing documented contract). Existing `handler`-based entries keep working or are migrated losslessly. `~/pi-mirror/tests/test_trigger_assignments.py` still passes. | 24 |
| TRIGA-07 | Backend validates `trigger_assignments` on save and returns **422** — handler/action type in the allowed set, `hardware_ref` resolves against the toolkit's `SEMANTIC_HARDWARE`, required config keys present, `method` refs in `CALLABLE_METHODS`, referenced view/flag keys exist. Today there is **zero** trigger validation in `api/`; a bad ref surfaces only as a Pi `ValueError` at session start. | 24 |
| TRIGA-08 | `api/fda_utils.py`'s recursive reference scanner covers hardware refs inside `trigger_assignments`, so a hardware-lib version change flags the task definitions whose triggers use it. | 24 |
| TRIGA-09 | The trigger panel hosts the **same action editor** the state body panel uses (`ActionEditor.tsx` / `ArgInput`), not a parallel implementation. | 24 |
| TRIGA-10 | The allowed handler/action list is single-sourced. Today it is hard-coded twice — `HANDLERS` in `TriggerAssignmentPanel.tsx` and the `if/elif` chain in `apply_trigger_assignments` — with nothing keeping them in sync. | 24 |
| TRIGA-11 | **Rig proof:** lick detection runs on the real pilot driven entirely by a UI-assigned action list, with no `detectedLick` method on the task class. Negative case: an invalid assignment is rejected at save time, not at session start. | 24 |

---

**Coverage:**
- v1 requirements: 86 total (HW-01–24 added for Hardware Libs Centralization + Hardware Modules + Toolkit Redesign)
- Bug requirements: 7 (BUG-01–07)
- Compound condition requirements: 10 (COND-01–10)
- External integration requirements: 13 (EXTLINK-01–13)
- Compute primitives + variables requirements: 12 (CMP-01–06, CMP-10–15); expr escape hatch (CMP-07–09) deferred — see note above
- Mapped to phases: 128
- Unmapped: 0 ✓

---
*Requirements defined: 2026-03-15*
*Last updated: 2026-05-31 — External integration (MICS-Link) requirements added (EXTLINK-01–13) for Phase 18; EXTLINK-12 covers the signal/command type contract (build-time declaration + wire-time coercion + AST emission); EXTLINK-13 covers the per-source readiness gate with three guaranteed escape paths (timeout, manual skip, STOP)*
*Last updated: 2026-06-01 — Compute primitives + variables requirements added, then consolidated into single Phase 23 (3 plans): Pi runtime variables+compute (CMP-01–06), backend validation + compute-library storage (CMP-10–12), GUI state-builder + variable/transition wiring (CMP-13–15). The `expr` escape-hatch (CMP-07–09) was decoupled/deferred. Phases 19–22 left free for the MICS-Link SDK arc.*
