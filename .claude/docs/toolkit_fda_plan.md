# ToolKit + FDA Plan

Redesign of the Pi task system to separate primitive operations (ToolKit, Python)
from experimental flow (Task Definition, JSON/DB/GUI).

Status: PLANNED — not yet started.

---

## GSD Framework

### Why

**Problem:** Each task (e.g. `AppetitiveTaskReal`) is a single Python class that hardcodes
both *what it can do* (state methods, hardware, flags) and *how it flows* (FDA transitions in
`__init__`). Changing the flow requires editing Python on the Pi, SSHing in, restarting the
pilot process, and hoping nothing breaks. There is no visual representation of the state machine
and no way to reuse flow logic across tasks.

**Impact:**
- Researchers are blocked from experimenting with task variants without developer help
- Every protocol change is a code change with risk of regression
- No audit trail of flow logic changes — Git history is the only record
- Onboarding new lab members to task code takes days

**What we're adding beyond the original plan:**
- State *body* actions are also defined in JSON (not just transitions/conditions)
- Trigger callback assignment (beyond `handle_trigger`) is configurable via JSON/GUI
- Semantic hardware references enable the same FDA JSON to run on different hardware configs
- Hot-reload: updated FDA JSON (stored in DB) is included in every START message — takes effect at the next task run, no Pi restart required

---

### What (Deliverables + Acceptance Criteria)

**Phase 1 — Foundation (Pi, backward compatible)**

| Deliverable | Acceptance Criteria |
|---|---|
| `load_fda_from_json()` in `mics_task` | `AppetitiveTaskReal` started with `state_machine=<v2_json>` kwarg produces identical behavior to hardcoded version; confirmed by identical CONTINUOUS event stream in ES |
| `apply_trigger_assignments()` in `mics_task` | `touch_detector` handler wires TOUCH_INT → `detect_change()` → view update; `digital_input` handler wires IR1 → view[IR1] update; both verified by reading view state after GPIO edge in a test run |
| Fresh `state_machine` in every START | Orchestrator's `_build_step_task()` includes `fda_json` from DB in START payload; Pi calls `load_fda_from_json()` at task start; confirmed by identical CONTINUOUS event stream in ES |
| `validate_fda.py` CLI tool | Rejects JSON with unknown state names, unknown `ref` values, unknown param keys; exits 0 on valid JSON; exits 1 with specific error on invalid |
| `tools/sync_pi.sh` + `tools/deploy_pi.sh` | `sync_pi.sh` rsyncs `~/pi-mirror/autopilot/` to Pi and exits 0; `deploy_pi.sh` syncs and restarts pilot process via SSH |
| FLAGS included in HANDSHAKE payload | `task_toolkits` table (Phase 2) can be populated with flags; `SEMANTIC_HARDWARE` and `STAGE_NAMES` also present in payload |

**Phase 2 — DB + API**

| Deliverable | Acceptance Criteria |
|---|---|
| `task_toolkits` table | HANDSHAKE populates it; `GET /api/toolkits` returns toolkit with `states`, `flags`, `params_schema`, `semantic_hardware`; verified via postgres MCP |
| Repurposed `task_definitions` | Has `toolkit_name`, `fda_json`, `default_params`; `POST /api/task-definitions` creates a record; `GET /api/task-definitions/:id` returns it with full fda_json |
| `POST /api/task-definitions/:id/push` | Returns 200 + `{"status": "pushed"}`; orchestrator forwards `UPDATE_FDA` to named pilot; Pi responds with `HOT_RELOAD_ACK` visible in orchestrator logs |
| Orchestrator sends `state_machine` in START payload | `_build_step_task()` includes `state_machine` from task definition; confirmed by docker MCP reading orchestrator logs during session start |

**Phase 3 — Visual FDA Editor**

| Deliverable | Acceptance Criteria |
|---|---|
| `/react/task-editor/:id` page | Loads state graph from DB; react-flow canvas shows states as nodes, transitions as edges; clicking a node shows state body panel |
| State body editor panel | Add/remove entry actions; add/remove return_data keys; set blocking; saved JSON round-trips through `load_fda_from_json()` without error |
| Trigger assignment panel | Configure TOUCH_INT handler type; configure view_key; save persists to `fda_json.trigger_assignments` in DB |
| "Push to Pilot" button | Only enabled when a pilot is running this task definition (checked via `/api/pilots/live`); on click calls `POST /api/task-definitions/:id/push`; shows toast |

**Phase 4 — Protocol Step Selects Task Definition**

| Deliverable | Acceptance Criteria |
|---|---|
| `protocols-create` uses task definitions | Step picker shows named task definitions instead of raw task types; saved protocol has `task_definition_id` in step; session start resolves `fda_json` from that ID |

---

### How (Step-by-Step Execution)

#### Phase 1 — Pi Foundation

**Step 1: Extend `mics_task.py`**

File: `~/pi-mirror/autopilot/autopilot/tasks/mics_task.py`

1. Add class attrs:
   ```python
   SEMANTIC_HARDWARE = {}   # {friendly_name: (group, id)}
   REQUIRED_PACKAGES = []   # [package_specifier]
   CALLABLE_METHODS  = []   # method names callable as entry_actions from JSON/GUI
   ```

2. Add `__init__` hook at the end of `mics_task.__init__` (after `self.stages = ...`):
   ```python
   state_machine_def = kwargs.get('state_machine')
   if state_machine_def:
       self.load_fda_from_json(state_machine_def)
   ```

3. Add `load_fda_from_json(self, definition: dict)`:
   - Detect v1 vs v2 by `definition.get('version', 1)`
   - v1: states is a list of strings, build trivial entry_actions from method names
   - v2: states is a dict with `entry_actions`, `blocking`, `return_data`
   - Build `_semantic_hw` map: for each entry in `SEMANTIC_HARDWARE`, resolve to actual
     `self.hardware[group][id]` object; apply `semantic_hardware_overrides` from JSON
   - For each state: call `_build_state_method(name, state_def)`, call `add_method()`
   - Call `set_initial_method()` for `definition['initial_state']`
   - For each transition in `definition['transitions']`: call `_build_transition_lambda()`,
     call `add_transition()`
   - Call `apply_trigger_assignments(definition)`
   - Store `self._state_method_registry = {name: method}` for hot-reload

4. Add `_build_state_method(self, name: str, state_def: dict) -> callable`:
   - **Passthrough check first:** if `state_def` has no `entry_actions` (empty or absent)
     AND `hasattr(self, name)`, return `getattr(self, name)` directly — the existing Python
     method is used as-is with no wrapping
   - Otherwise: returns a new bound method that executes `entry_actions` then returns
     `self.wait_for_condition()` if `blocking == "stage_block"` else `None`
   - `entry_actions` interpreter (see Entry Action Types table below); supports `type: "method"`
     which calls `getattr(self, action["ref"])(*resolved_args)` — method must be in `CALLABLE_METHODS`
   - `return_data` collector runs after actions, dispatches DATA event if non-empty

5. Add `_resolve_arg(self, arg)` for arg value resolution:
   - `isinstance(arg, dict)` and `"param" in arg` → `self.params[arg["param"]]`
   - `isinstance(arg, dict)` and `"flag" in arg` → `self.flags[arg["flag"]].value`
   - else → literal

6. Add `_build_transition_lambda(self, cond: dict) -> callable`:
   - Returns `lambda: getattr(operator, op_map[cond["op"]])(self.view.get_value(cond["view"]), self._resolve_arg(cond["rhs"]))`

7. Add `apply_trigger_assignments(self, definition: dict)`:
   - If `"trigger_assignments"` not in definition: return (backward compat)
   - For each assignment: dispatch to handler builder by `assignment["handler"]`
   - `"touch_detector"`: build callback that calls `self._semantic_hw[config["hardware_ref"]].detect_change()`, updates view, optionally emits CONTINUOUS
   - `"digital_input"`: build callback that updates `self.view.view[config["view_key"]] = level`
   - `"log_only"`: no-op callback (logging already done by `execute_trigger`)
   - `"default"`: no callback registered (default `handle_trigger` path already fires)
   - **Important:** All handler types ONLY add to `self.triggers[trigger_name]` list.
     The Hardware_Event logging in `execute_trigger()` already fires for ALL trigger hardware
     unconditionally — these callbacks add semantic view updates on top.

**Step 2: No changes to `FiniteDeterministicAutomaton.py` in Phase 1**

The FDA class is unchanged. Hot-reload is achieved by always sending the latest `fda_json`
from the DB in the START message, so `load_fda_from_json()` rebuilds the FDA fresh at every
task start. Mid-execution method replacement (`replace_method_ref`, `replace_transitions`)
is deferred to v2.

**Step 3: Extend `pilot.py`**

File: `~/pi-mirror/autopilot/autopilot/core/pilot.py`

1. In `extract_task_metadata()` (line ~394): add to returned dict:
   - `"flags"`: `{name: {type: ..., initial_value: ...}}` from `cls.FLAGS`
   - `"semantic_hardware"`: `cls.SEMANTIC_HARDWARE`
   - `"stage_names"`: `cls.STAGE_NAMES`
   - `"required_packages"`: `cls.REQUIRED_PACKAGES`
   - `"callable_methods"`: `cls.CALLABLE_METHODS`

2. No `UPDATE_FDA` handler needed in Phase 1 — hot-reload happens by sending a fresh
   `state_machine` key in the next START message (see Phase 2, Step 5). The Pi re-calls
   `load_fda_from_json()` at task start, which rebuilds the FDA from the updated JSON.
   `UPDATE_FDA` mid-execution is a v2 feature.

**Step 4: Validation tool**

New file: `~/pi-mirror/tools/validate_fda.py`

CLI: `python validate_fda.py <toolkit_module> <fda_json_file>`
- Imports toolkit class, loads JSON
- Checks: all state names are methods on toolkit, all `ref` in actions exist in
  `SEMANTIC_HARDWARE`, all `param` refs exist in `PARAMS`, all `flag` refs exist in `FLAGS`
- Prints errors with line numbers (state name, action index), exits 1 if any found

**Step 5: Sync/Deploy scripts**

New files: `~/pi-mirror/tools/sync_pi.sh`, `~/pi-mirror/tools/deploy_pi.sh`

```bash
# sync_pi.sh
rsync -avz --exclude __pycache__ \
  ~/pi-mirror/autopilot/ \
  pi@132.77.72.28:~/Apps/mice_interactive_home_cage/autopilot/ \
  -e "ssh -i ~/.ssh/pi_mics"
```

```bash
# deploy_pi.sh
./sync_pi.sh && \
  ssh -i ~/.ssh/pi_mics pi@132.77.72.28 \
    "systemctl restart pilot || pkill -f pilot.py && sleep 1 && python ~/Apps/.../pilot.py &"
```

**Step 6: Test Phase 1**

1. Start `AppetitiveTaskReal` via normal session start (no `state_machine` kwarg) → confirm identical behavior
2. Create `appetitive_real_v2.json` mirroring `AppetitiveTaskReal.__init__` FDA
3. Start task with `state_machine=json.loads(appetitive_real_v2.json)` in kwargs
4. Compare CONTINUOUS event streams in ES via `/es-query` skill
5. Run `validate_fda.py AppetitiveTaskReal appetitive_real_v2.json` — expect exit 0
6. Modify `entry_actions` on one state in the JSON, restart the task (no Pi restart, just new session run)
7. Confirm new action fires on state entry — old action does not

#### Phase 2 — DB + API

**Step 1: Create `task_toolkits` table**

File: `api/models.py` — add SQLAlchemy model (not SQLModel — consistent with existing pilot/session schema):
```python
class TaskToolkit(Base):
    __tablename__ = "task_toolkits"
    name = Column(String, primary_key=True)
    pilot_id = Column(Integer, ForeignKey("pilots.id"))
    states = Column(JSON)            # list of state method names (passthrough-capable)
    flags = Column(JSON)             # {name: {type, initial_value}}
    params_schema = Column(JSON)     # {name: {tag, type, default}}
    hardware = Column(JSON)          # HARDWARE dict
    semantic_hardware = Column(JSON) # SEMANTIC_HARDWARE dict
    semantic_hardware_renames = Column(JSON) # SEMANTIC_HARDWARE_RENAMES dict: old_name → new_name
    callable_methods = Column(JSON)  # CALLABLE_METHODS list — methods usable as entry_action building blocks
    required_packages = Column(JSON)
    file_hash = Column(String)
    updated_at = Column(DateTime)
```

**Step 2: Extend `task_definitions` table**

Add migration in `api/db.py` `run_lab_column_migrations()`:
```sql
ALTER TABLE task_definitions ADD COLUMN IF NOT EXISTS toolkit_name VARCHAR;
ALTER TABLE task_definitions ADD COLUMN IF NOT EXISTS fda_json JSONB;
ALTER TABLE task_definitions ADD COLUMN IF NOT EXISTS display_name VARCHAR;
```

**Step 3: Update orchestrator HANDSHAKE handler**

File: `orchestrator/orchestrator/orchestrator_station.py`

In `on_handshake()` (line ~69): after calling `upsert_pilot_tasks()`, also call
`upsert_pilot_toolkits()` which POSTs to new `POST /api/toolkits` endpoint with
enriched payload (flags, semantic_hardware, semantic_hardware_renames, required_packages).

After upserting, run a broken-ref check: query `task_definitions` for rows whose `fda_json`
references `ref` values no longer present in `semantic_hardware` (also not in
`semantic_hardware_renames` keys). Log a WARNING with the affected task_definition IDs and
the suggested `validate_fda.py rename-hw-ref` command. This surfaces broken refs at deploy
time rather than silently at task start.

**Step 4: New API endpoints**

File: `api/main.py`

- `GET /api/toolkits` — list all, optionally `?pilot=name`
- `GET /api/toolkits/{name}` — full detail with all fields
- `POST /api/task-definitions` — body: `{toolkit_name, display_name, fda_json, default_params}`
- `GET /api/task-definitions/{id}` — full detail
- `PUT /api/task-definitions/{id}` — update fda_json/params
- `DELETE /api/task-definitions/{id}`
- `POST /api/task-definitions/{id}/push` — body/query: `?pilot=name`

File: `orchestrator/orchestrator/api.py` — new endpoint:
- `POST /push-fda` — body: `{pilot_name, fda_update}` → calls `push_hot_reload()`

**Step 5: Orchestrator sends `state_machine` in START**

File: `orchestrator/orchestrator/orchestrator_station.py`

In `_build_step_task()`: if the session run's task definition has `fda_json`, include
`state_machine=fda_json` in the kwargs dict sent in the START ZMQ message.

#### Phase 3 — Visual Editor

New page: `web_ui/react-src/src/pages/task-editor/index.tsx`

Sub-components:
- `TaskEditorCanvas.tsx` — react-flow with state nodes + transition edges
- `StateBodyPanel.tsx` — entry_actions list, blocking toggle, return_data list
- `TriggerAssignmentPanel.tsx` — table of trigger_name → handler type → config
- `SemanticHardwarePanel.tsx` — override table
- `ActionEditor.tsx` — modal/inline for add action (hardware/flag/timer/special)
- `ArgInput.tsx` — smart input: literal / param-ref / flag-ref toggle

API additions (typed fetch helpers):
- `api/toolkits.ts` — `getToolkits()`, `getToolkit(name)`
- `api/taskDefinitions.ts` — CRUD + `pushToRun(id, pilotName)`

#### Phase 4 — Protocol Step References Task Definition

File: `web_ui/react-src/src/pages/protocols-create/index.tsx`

- Task palette changes from `GET /api/tasks/leaf` to `GET /api/task-definitions`
- Step object stores `task_definition_id` alongside/replacing `task_type`
- `POST /api/protocols` receives steps with `task_definition_id`

File: `api/models.py` — `ProtocolStepTemplate` gains `task_definition_id` field

File: `api/main.py` — `create_session_run()` resolves `fda_json` from task definition
and includes it in START payload.

---

### Who / When (Phase Order and Dependencies)

```
Phase 1 (Pi)  ──────────────────────────────────────────────────────► testable immediately
                  ↓ depends on Phase 1 FLAGS in HANDSHAKE
Phase 2 (DB/API) ──────────────────────────────────────────────────► depends on Phase 1
                        ↓ depends on Phase 2 toolkits endpoint
Phase 3 (Visual Editor) ───────────────────────────────────────────► depends on Phase 2
                                    ↓ depends on Phase 3 task definitions in DB
Phase 4 (Protocol Step) ───────────────────────────────────────────► depends on Phase 3
```

Each phase is independently testable. Phase 1 produces a working JSON-driven task.
Phase 2 makes it DB-backed. Phase 3 adds the GUI. Phase 4 integrates with the protocol system.

**Phase 1 can start today.** Pi mirror is available at `~/pi-mirror/`. Use `/new-pi-task`
skill for any new ToolKit scaffolding. Use `/mics-debug` if task hangs during Phase 1 testing.

---

### Risks

| Risk | Likelihood | Mitigation |
|---|---|---|
| `_build_state_method` closes over wrong variable in loop | Medium | Use `functools.partial` or default-arg capture in lambda; unit test every state method in isolation before integration test |
| `SEMANTIC_HARDWARE` missing entry at runtime | High (first run) | `validate_fda.py` catches this at validate time; `load_fda_from_json` should raise `KeyError` with descriptive message, not silent None |
| Phase 2 migration breaks existing `task_definitions` rows | Medium | Migration adds columns `IF NOT EXISTS`; existing rows get `NULL` for new columns; API handles `fda_json=NULL` as "legacy task definition" and falls back to old behavior |
| FDA v2 JSON stored in DB but Pi runs v1 code | Medium | Check `definition.get('version')` in `load_fda_from_json`; if v2 but `_build_state_method` not implemented, raise `NotImplementedError` rather than silently degrading |
| Developer renames a semantic hardware key after FDA JSON exists | Low | Use `SEMANTIC_HARDWARE_RENAMES` for zero-downtime backward compat; run `validate_fda.py rename-hw-ref` to update stored JSON; HANDSHAKE processor warns if refs are broken |
| `type: "method"` calls a method not in `CALLABLE_METHODS` | Medium | `validate_fda.py` checks all `method` action refs against `CALLABLE_METHODS`; `load_fda_from_json` raises descriptive error at load time, not silently at state entry |
| Passthrough state name matches a method that no longer exists | Low | `validate_fda.py` checks all passthrough state names against `cls.STAGE_NAMES + dir(cls)`; missing method raises at validate time |

---

## Core Concepts

### ToolKit (Python, on Pi)

A Python class (subclass of `mics_task`) that declares:
- `HARDWARE` — which hardware objects are used (group → id → class)
- `SEMANTIC_HARDWARE` — named aliases for hardware objects (`"reward_port"` → `("GPIO", "SOLENOID1")`)
- `FLAGS` — Tracker instances (hits, misses, lick count, etc.)
- `PARAMS` — tunable parameters (ITI, open_duration, etc.)
- `CALLABLE_METHODS` — Python methods that can be called as building blocks from GUI-built states
- State methods — Python methods that can be used directly as FDA states (passthrough)

**It does NOT wire the FDA in `__init__`** when a `state_machine` kwarg is provided.
That is the key difference from the current model.
The toolkit is a library. Multiple different task definitions can be assembled from one toolkit.

Currently `mics_task` subclasses ARE toolkits — they just also hardcode their own FDA.
Stripping the FDA wiring out of `__init__` turns them into proper toolkits.

#### Three Modes of Using Toolkit Methods in FDA

**Mode 1 — Passthrough state**: an existing Python method used directly as an FDA state.
The JSON names the state but provides no `entry_actions`. `_build_state_method` detects
this and returns `getattr(self, name)` — the original method runs unchanged.

```json
"states": {
  "prepare_session": {}
}
```
→ Calls `self.prepare_session()` at state entry. Full Python logic, blocking, return_data
  all handled inside the method as written. Locked/read-only in GUI; shown with Python icon.

**Mode 2 — GUI-constructed state**: all behavior defined in JSON `entry_actions`.
The researcher assembles the state body entirely in the browser using hardware, flag,
timer, special, and method actions.

```json
"states": {
  "custom_reward": {
    "entry_actions": [
      { "type": "hardware", "ref": "reward_port", "method": "pulse",
        "args": [{ "param": "open_duration" }] },
      { "type": "flag", "ref": "hit_count", "method": "increment" }
    ]
  }
}
```

**Mode 3 — GUI-constructed state calling a toolkit method as a building block**:
a `type: "method"` action inside a GUI-built state calls a developer-defined Python method.
The method must appear in the toolkit's `CALLABLE_METHODS` list.

```json
"states": {
  "complex_iti": {
    "entry_actions": [
      { "type": "method", "ref": "randomize_iti_duration" },
      { "type": "hardware", "ref": "reward_port", "method": "set", "args": [false] }
    ]
  }
}
```
→ `randomize_iti_duration` is a Python method on the toolkit; the developer marks it as
  callable (`CALLABLE_METHODS = ["randomize_iti_duration"]`). The GUI shows it in the
  "Custom Methods" action picker alongside hardware/flag/timer/special options.

**Mixing all three in the same FDA JSON is fully supported.**

### Task Definition (JSON, in DB, built in GUI)

A user-assembled state machine built from a toolkit's building blocks:
- **Passthrough states**: existing Python toolkit methods used as-is (no entry_actions in JSON)
- **GUI-constructed states**: behavior fully defined via entry_actions (hardware/flag/timer/special/method)
- **Hybrid states**: GUI-constructed but call one or more Python toolkit methods as building blocks
- Which transitions connect states
- What conditions guard each transition
- How GPIO callbacks are wired beyond the default `handle_trigger`
- Default param values

Stored in the DB. Built visually in the web UI. One toolkit → many task definitions.
Task definitions are what protocol steps reference.

### Semantic Hardware References

#### Where Friendly Names Come From

Friendly names are **developer-defined in code** — not created in the UI.

The toolkit class declares `SEMANTIC_HARDWARE` as a class attribute. This is the
stable set of named hardware references that FDA JSON (built by researchers in the GUI)
is allowed to use.

```python
# pilot/plugins/appetitive_task_real.py  (developer writes this)
class AppetitiveTaskReal(mics_task):
    SEMANTIC_HARDWARE = {
        "reward_port":    ("GPIO", "SOLENOID1"),
        "stimulus_led":   ("GPIO", "LED1"),
        "door":           ("I2C",  "DOOR1"),
        "lick_sensor":    ("I2C",  "MPR121"),
        "reward_motor":   ("I2C",  "MOTORIZED_REWARD"),
        "speaker":        ("MIXER","AUDIO"),
        "timer_nosepoke": ("TIMER","TIMER_TO_NOSEPOKE"),
    }
```

When the Pi sends a HANDSHAKE, `SEMANTIC_HARDWARE` is included in the payload and stored
in the `task_toolkits` table. The GUI reads it from there to populate hardware dropdowns
in the state body editor — researchers pick from a list of `reward_port`, `stimulus_led`,
etc. without ever seeing `SOLENOID1` or pin numbers.

**The flow is one-way:** developer defines → HANDSHAKE ships → DB stores → GUI presents.
Researchers cannot add or rename semantic hardware from the UI.

#### Three-Layer Abstraction

Understanding why FDA JSON stored in the DB survives physical changes:

```
Layer 1 — prefs.json (physical config, per rig):
    "HARDWARE": {
        "GPIO": { "SOLENOID1": { "pin": 18, ... } },
        "I2C":  { "MPR121":    { "address": "0x5A", ... } }
    }
    → Keys: "SOLENOID1", "MPR121" — must match HARDWARE dict exactly

Layer 2 — HARDWARE dict (class-level constants, in task .py):
    HARDWARE = {
        "GPIO": { "SOLENOID1": Solenoid },
        "I2C":  { "MPR121": MPR121 }
    }
    → Keys must match prefs.json keys — they are the stable hardware identifiers

Layer 3 — SEMANTIC_HARDWARE (friendly names, in task .py):
    SEMANTIC_HARDWARE = {
        "reward_port": ("GPIO", "SOLENOID1"),
        "lick_sensor": ("I2C",  "MPR121"),
    }
    → These names are what FDA JSON uses (via "ref" in entry_actions)

Layer 4 — FDA JSON in DB:
    { "ref": "reward_port", ... }
    → Completely immune to changes in layers 1–2
```

**What breaks what:**

| Change | Effect on FDA JSON in DB |
|---|---|
| Change solenoid pin number in `prefs.json` | Nothing — JSON uses `"reward_port"`, not pin numbers |
| Rename `SOLENOID1` → `VALVE1` in both `prefs.json` AND `HARDWARE` dict | Update `SEMANTIC_HARDWARE` one line: `"reward_port": ("GPIO", "VALVE1")` — JSON unchanged |
| Rename `"reward_port"` in `SEMANTIC_HARDWARE` | Old refs in stored FDA JSON break — use the rename escape hatch (below) |

State body actions in the task definition JSON use `ref` (semantic name) instead of
`hardware['I2C']['MPR121']`. This decouples task logic from physical wiring:
- Swap solenoid pin → change `prefs.json` only; FDA JSON untouched
- Rename hardware key → change `prefs.json` + `HARDWARE` dict + one line in `SEMANTIC_HARDWARE`; FDA JSON untouched
- Deploy same FDA JSON to a different rig → update `prefs.json` + `HARDWARE` + `SEMANTIC_HARDWARE` on that rig; JSON file unchanged

#### Renaming Semantic Names (Escape Hatch)

**The "migration" concern is overstated.** Renaming a semantic key does not require an ALTER
TABLE or schema change — it's a JSON value update (SQL UPDATE on `task_definitions.fda_json`),
which is trivial to script and fully reversible. The plan provides two mechanisms to make this
smooth during toolkit development.

**Lifecycle of a semantic name:**

```
Phase 1 — Toolkit development:
    No FDA JSON in the DB yet references your toolkit.
    Rename freely. No consequences.

Phase 2 — First task definitions exist:
    Refs are live in stored FDA JSON.
    Use SEMANTIC_HARDWARE_RENAMES to keep old refs resolving while you migrate.

Phase 3 — Migration complete:
    All FDA JSON updated. Remove old entry from SEMANTIC_HARDWARE_RENAMES.
    Name is now stable.
```

**Mechanism: `SEMANTIC_HARDWARE_RENAMES`**

When a developer renames a semantic key, they add the old name to a companion dict. The Pi's
`load_fda_from_json()` checks this dict when resolving a `ref` that isn't found in
`SEMANTIC_HARDWARE` directly — old FDA JSON keeps working without touching the DB.

```python
class AppetitiveTaskReal(mics_task):
    SEMANTIC_HARDWARE = {
        "water_delivery":  ("GPIO", "SOLENOID1"),   # renamed from "reward_port"
        "lick_sensor":     ("I2C",  "MPR121"),
    }
    # Old refs still resolve transparently — remove once no FDA JSON uses them
    SEMANTIC_HARDWARE_RENAMES = {
        "reward_port": "water_delivery",   # old_name → new_name
    }
```

Old FDA JSON with `"ref": "reward_port"` resolves fine. The GUI marks the ref as deprecated
and prompts the researcher to update (one click). Once all task definitions are updated,
remove the entry from `SEMANTIC_HARDWARE_RENAMES`.

**Mechanism: `validate_fda.py rename-hw-ref` command**

For bulk cleanup, `validate_fda.py` exposes a rename command that updates all stored FDA JSON
in the database in one operation:

```bash
python validate_fda.py rename-hw-ref reward_port water_delivery --toolkit AppetitiveTaskReal
# → SQL UPDATE on task_definitions.fda_json: replaces "ref": "reward_port" → "ref": "water_delivery"
# → Reports how many task_definitions were updated
# → Exits 0 on success, 1 if any ref could not be resolved
```

After running this, `SEMANTIC_HARDWARE_RENAMES` can be cleared.

**Broken ref detection in HANDSHAKE processing**

When the backend receives a HANDSHAKE and the current `SEMANTIC_HARDWARE` no longer contains
a key that existing `task_definitions` reference, it logs a warning:

```
WARNING: toolkit 'AppetitiveTaskReal' HANDSHAKE missing semantic hardware refs
  used by stored task definitions: ['reward_port']
  → 3 task_definitions affected
  → Run: validate_fda.py rename-hw-ref reward_port <new_name> --toolkit AppetitiveTaskReal
```

This makes broken refs visible at deploy time, not silently at task start.

**Summary — what actually needs a migration vs. what doesn't:**

| Change | What's needed |
|---|---|
| Rename during toolkit dev (no FDA JSON exists yet) | Nothing — just edit the code |
| Rename after FDA JSON exists | Add to `SEMANTIC_HARDWARE_RENAMES` (zero-downtime) + run rename command when ready |
| Remove a semantic name entirely | Add to `SEMANTIC_HARDWARE_RENAMES` pointing to `None`; GUI warns; remove once clean |
| Schema changes to `task_toolkits` table | Actual DB migration (rare, same pattern as existing `run_lab_column_migrations()`) |

### Protocol Step

Unchanged concept: references a task definition + sets param overrides.

### The Full Flow

```
ToolKit (Python on Pi)
    ↓  discovered via HANDSHAKE
task_toolkits table (DB)
    ↓  user assembles in GUI
task_definitions table (DB)  ← fda_json + default_params
    ↓  referenced by
protocol_step_templates
    ↓  params overridden at
session_runs
    ↓  state_machine kwarg sent to Pi
Pi: load_fda_from_json() → builds FDA, state methods, trigger callbacks live
```

---

## Extended FDA JSON Schema (v2)

Version 2 adds `states` as an object (not just a name list), `trigger_assignments`,
and `semantic_hardware_overrides`. Version 1 (transitions only, states as list) stays
backward compatible.

```json
{
  "toolkit": "AppetitiveTaskReal",
  "version": 2,
  "initial_state": "prepare_session",

  "semantic_hardware_overrides": {
    "reward_port": ["GPIO", "SOLENOID2"]
  },

  "trigger_assignments": [
    {
      "trigger_name": "TOUCH_INT",
      "handler": "touch_detector",
      "config": {
        "hardware_ref": "lick_sensor",
        "view_key_template": "LICKER{n}",
        "emit_continuous": true
      }
    },
    {
      "trigger_name": "IR1",
      "handler": "digital_input",
      "config": {
        "view_key": "IR1",
        "emit_continuous": true
      }
    }
  ],

  "states": {
    "prepare_session": {
      "entry_actions": [
        { "type": "hardware", "ref": "door",         "method": "set",       "args": [false] },
        { "type": "hardware", "ref": "reward_motor", "method": "set",       "args": [true]  },
        { "type": "flag",     "ref": "hit_trial",    "method": "set",       "args": [false] },
        { "type": "flag",     "ref": "hit_count",    "method": "set",       "args": [0]     }
      ],
      "blocking": null,
      "return_data": null
    },

    "trial_onset": {
      "entry_actions": [
        { "type": "flag",    "ref": "trial_counter", "method": "increment" },
        { "type": "special", "action": "INC_TRIAL_COUNTER"                 }
      ],
      "blocking": null,
      "return_data": {
        "trial_num": { "flag": "trial_counter" },
        "timestamp_on": { "now": true }
      }
    },

    "stimulus": {
      "entry_actions": [
        { "type": "hardware", "ref": "speaker",       "method": "set",     "args": [0, { "param": "audio_volume" }] },
        { "type": "hardware", "ref": "stimulus_led",  "method": "set",     "args": [true] },
        { "type": "hardware", "ref": "timer_nosepoke","method": "set",     "args": [{ "param": "nosepoke_window" }] }
      ],
      "blocking": null,
      "return_data": null
    },

    "state_wait_time_window": {
      "entry_actions": [],
      "blocking": "stage_block",
      "return_data": null
    },

    "state_lick": {
      "entry_actions": [
        { "type": "hardware", "ref": "reward_port", "method": "pulse", "args": [{ "param": "open_duration" }] },
        { "type": "flag",     "ref": "hit_trial",   "method": "set",   "args": [true] },
        { "type": "flag",     "ref": "hit_count",   "method": "increment" }
      ],
      "blocking": null,
      "return_data": null
    },

    "state_end_trial": {
      "entry_actions": [
        { "type": "hardware", "ref": "stimulus_led", "method": "set", "args": [false] },
        { "type": "hardware", "ref": "speaker",      "method": "mute" }
      ],
      "blocking": null,
      "return_data": {
        "timestamp_off": { "now": true },
        "hit_count":     { "flag": "hit_count" }
      }
    }
  },

  "transitions": [
    { "from": "prepare_session",    "to": "trial_onset",   "conditions": [], "description": "unconditional" },
    { "from": "trial_onset",        "to": "stimulus",      "conditions": [], "description": "unconditional" },
    {
      "from": "state_wait_time_window",
      "to":   "state_lick",
      "conditions": [
        { "view": "LICKER1", "op": "==", "rhs": { "literal": true } }
      ],
      "description": "mouse licked the reward port"
    },
    {
      "from": "state_wait_time_window",
      "to":   "state_end_trial",
      "conditions": [
        { "view": "timer_nosepoke", "op": "==", "rhs": { "literal": false } }
      ],
      "description": "time window expired — miss"
    },
    { "from": "state_lick",      "to": "state_end_trial",  "conditions": [], "description": "unconditional" },
    { "from": "state_end_trial", "to": "trial_onset",      "conditions": [], "description": "start new trial" }
  ]
}
```

### Entry Action Types

| `type`      | Required fields                                 | Description                                        |
|-------------|------------------------------------------------|----------------------------------------------------|
| `hardware`  | `ref`, `method`, optional `args`               | Calls `semantic_hw[ref].method(*args)` via notify helpers |
| `flag`      | `ref`, `method`, optional `args`               | Calls `self.flags[ref].method(*args)` with dispatch |
| `timer`     | `ref`, `method`, optional `args`               | Same as hardware but uses `set_timmer_and_notify` / `cancel_timer_and_notify` |
| `special`   | `action`                                       | `INC_TRIAL_COUNTER` or `STAGE_BLOCK_SET` |
| `method`    | `ref`, optional `args`                         | Calls `self.<ref>(*resolved_args)` — `ref` must be in toolkit's `CALLABLE_METHODS` list |

### Arg Value Types (inside `args` array)

| Form                        | Resolved to                            |
|-----------------------------|----------------------------------------|
| `42`, `true`, `"cue_1.wav"` | Literal value                          |
| `{ "param": "open_dur" }`   | `self.params["open_dur"]` at call time |
| `{ "flag": "hit_count" }`   | `self.flags["hit_count"].value`        |

### Blocking Types

| `blocking` value | Behavior                                         |
|------------------|--------------------------------------------------|
| `null`           | State returns immediately, FDA evaluates next    |
| `"stage_block"`  | State calls `wait_for_condition()` (yield loop)  |

### Return Data Value Types

| Form                | Resolved to                            |
|---------------------|----------------------------------------|
| `{ "flag": "x" }`  | `self.flags["x"].value`                |
| `{ "param": "x" }` | `self.params["x"]`                     |
| `{ "now": true }`  | `datetime.now(jerusalem_tz).isoformat()` |

### Condition Format (unchanged from v1)

```json
{ "view": "current_lick", "op": ">=", "rhs": { "literal": 3 } }
{ "view": "current_lick", "op": ">=", "rhs": { "param": "lick_threshold" } }
{ "view": "IR2",          "op": "==", "rhs": { "literal": true } }
{ "view": "timer_nosepoke", "op": "==", "rhs": { "literal": false } }
```

Supported ops: `==`, `!=`, `>`, `>=`, `<`, `<=`

Condition list on a transition is AND (all must be true). Empty list = unconditional.

---

## Trigger Assignment System

### Architectural Basis

The trigger flow in the current codebase (verified against `task.py`):

1. GPIO edge fires → `hw.assign_cb(partial(self.handle_trigger, hardware=hw))` callback is called
2. `handle_trigger()` puts `(pin, level, tick, hardware)` into `self.event_queue`
3. Worker thread (`process_queue`) picks it up → calls `execute_trigger(pin, level, tick, hardware)`
4. `execute_trigger()` **always** dispatches `Hardware_Event` via `event_dispatcher` first
   (this is the auto-logging path — `@log_action` on hardware ALSO fires, providing a separate
    CONTINUOUS dispatch from the hardware object itself)
5. Then `execute_trigger()` checks `self.triggers[pin]` and calls any registered callables there

**Key insight:** `self.triggers[pin]` is a secondary callback layer that runs AFTER automatic
logging. It exists for semantic view updates — telling the view what the GPIO event *means*
(e.g., mapping TOUCH_INT → which specific LICKER was touched). It does NOT control whether
logging happens. Logging always happens.

Therefore `trigger_assignments` in the task definition JSON configures ONLY the semantic
callback layer (`self.triggers[pin]`). The `handle_trigger` → `execute_trigger` → `Hardware_Event`
chain is never modified or replaced.

### Standard Trigger Handlers

The toolkit base class (`mics_task`) will provide built-in handler types:

| `handler` key      | What it does                                                                 |
|--------------------|------------------------------------------------------------------------------|
| `default`          | No entry in `self.triggers[name]` — the base logging path is sufficient     |
| `touch_detector`   | Adds callback: calls `hw.detect_change()`, updates `view[LICKER{n}]`       |
| `digital_input`    | Adds callback: updates `view[view_key]` with current level                  |
| `log_only`         | Adds a no-op callback (useful as explicit documentation that pin is monitored) |

Custom handlers (beyond these four) still require Python in the toolkit. The GUI exposes
only the standard types. This covers ~95% of real use cases.

### Trigger Assignment in JSON

```json
"trigger_assignments": [
  {
    "trigger_name": "TOUCH_INT",
    "handler": "touch_detector",
    "config": {
      "hardware_ref": "lick_sensor",
      "view_key_template": "LICKER{n}",
      "emit_continuous": true
    }
  }
]
```

The `apply_trigger_assignments(json_def)` method in `mics_task` reads this and appends
to `self.triggers[trigger_name]` with the appropriate built-in handler closure.

If `trigger_assignments` is absent, `self.triggers` is not modified (backward compat).
Any `self.triggers` assignments already made by the toolkit's `__init__` are preserved.

---

## Hot-Reload: Updating State Logic Without Pi Restart

### The Goal

A researcher can modify a state machine in the GUI and have the change take effect on the
**next task run** — without restarting the Pi's pilot process.

### How It Works (Phase 1 + 2)

The mechanism is straightforward: the orchestrator always includes the latest `fda_json`
from the DB in every START ZMQ message it sends to the Pi.

```
Researcher edits FDA in GUI
        ↓
PUT /api/task-definitions/:id  → updates fda_json in DB
        ↓
Subject completes current run  → orchestrator starts next run
        ↓
_build_step_task() reads fda_json from DB  → includes as state_machine kwarg in START
        ↓
Pi receives START  → task.__init__ calls load_fda_from_json(state_machine_def)
        ↓
FDA rebuilt from new JSON  → new state logic active
```

**Scope:** Hot-reload operates between task runs. The pilot process stays running; the task
object is re-created at each run start. No mid-execution method replacement is needed.

**What "no Pi restart" means:** The `pilot.py` process (and all its ZMQ connections, hardware
state, and Redis links) never restarts. Only the `Task` object is new each run.

### Orchestrator: `_build_step_task()` includes `state_machine`

```python
# orchestrator_station.py — Phase 2 change
def _build_step_task(self, step, overrides):
    kwargs = {**step.params, **overrides}
    if step.task_definition and step.task_definition.fda_json:
        kwargs['state_machine'] = step.task_definition.fda_json
    return {'task': step.task_type, 'kwargs': kwargs}
```

The Pi's `mics_task.__init__` already checks `kwargs.get('state_machine')` and calls
`load_fda_from_json()` if present. Nothing else is needed on the Pi side.

### v2: Mid-Execution Update via `UPDATE_FDA`

For future use (v2): while a task is executing, an `UPDATE_FDA` ZMQ message could replace
state method refs live without stopping the task. This requires `replace_method_ref()` on
the FDA and careful thread-safety analysis. Not part of Phase 1 scope — the between-run
mechanism covers all current lab requirements.

---

## Implementation Phases (Summary)

### Phase 1 — Foundation (Pi + no UI changes, backward compatible)

**Use `/new-pi-task` skill** when writing any new ToolKit class.

Pi files to change:
- `autopilot/autopilot/tasks/mics_task.py` — `load_fda_from_json`, `apply_trigger_assignments`, `_build_state_method`, `_resolve_arg`, `_build_transition_lambda`
- `autopilot/autopilot/core/pilot.py` — enriched HANDSHAKE payload (FLAGS, SEMANTIC_HARDWARE, SEMANTIC_HARDWARE_RENAMES, STAGE_NAMES, REQUIRED_PACKAGES)

New files:
- `tools/validate_fda.py` — JSON validator + `rename-hw-ref` command for bulk ref updates in DB
- `tools/sync_pi.sh`, `tools/deploy_pi.sh`

---

### Phase 2 — DB + API

New table: `task_toolkits`
Extended: `task_definitions` gains `toolkit_name`, `fda_json`, `display_name`

New API endpoints:
- `GET /api/toolkits`, `GET /api/toolkits/:name`
- `POST /api/task-definitions`, `GET/PUT/DELETE /api/task-definitions/:id`
- `POST /api/task-definitions/:id/push`

Orchestrator change: `_build_step_task()` includes `state_machine` from task definition
in START payload. Also registers `UPDATE_FDA` in ZMQ message dispatch.

---

### Phase 3 — Visual FDA + State Body Editor (Web UI)

New page: `/react/task-editor/:taskDefinitionId`

Sub-sections:
- FDA Transition Editor (react-flow canvas)
- State Body Editor (side panel, activated by node click)
- Trigger Assignment Panel (separate tab)
- Semantic Hardware Overrides Panel
- "Push to Pilot" button

---

### Phase 4 — Protocol Step Selects Task Definition

- `/react/protocols-create` step picker → task definition picker
- Protocol steps store `task_definition_id`
- `GET /api/tasks/leaf` deprecated in favour of `GET /api/task-definitions`

---

## Visual FDA Editor (Phase 3 Detail)

### FDA Transition Editor

```
┌──────────────┬───────────────────────────────┬──────────────────┐
│ LEFT PANEL   │ CANVAS (react-flow)            │ RIGHT PANEL      │
│              │                                │                  │
│ States       │  [prepare_session] ──────────▶ │ Transition:      │
│ (from toolkit│       │                        │ from: state_A    │
│  state list) │       ▼                        │ to:   state_B    │
│              │  [trial_onset]                 │                  │
│ View Keys    │       │                        │ Conditions:      │
│  LICKER1     │       ▼                        │ + Add condition  │
│  IR2         │  [stimulus]                    │                  │
│  hit_trial   │       │                        │ [view][op][val]  │
│  timer_np    │       ▼                        │                  │
│              │  [state_wait...]               │ Save transition  │
│ Params       │                                │                  │
│  nosepoke_w  │                                │                  │
└──────────────┴───────────────────────────────┴──────────────────┘
```

### State Body Editor

```
┌─────────────────────────────────────────────────────┐
│ State: trial_onset                                  │
│                                                     │
│ ENTRY ACTIONS                          [+ Add]      │
│ ┌─────────────────────────────────────────────────┐ │
│ │ flag: trial_counter → increment                ✕│ │
│ │ special: INC_TRIAL_COUNTER                     ✕│ │
│ └─────────────────────────────────────────────────┘ │
│                                                     │
│ BLOCKING    ○ None  ○ Wait for condition            │
│                                                     │
│ RETURN DATA                            [+ Add]      │
│ ┌─────────────────────────────────────────────────┐ │
│ │ trial_num  ←  flag: trial_counter              ✕│ │
│ │ timestamp  ←  now()                            ✕│ │
│ └─────────────────────────────────────────────────┘ │
│                                                     │
│ [Save State Body]   [Push to Pilot ▶]               │
└─────────────────────────────────────────────────────┘
```

"Add action" opens a picker:
- Hardware: dropdown (semantic refs from toolkit) + method dropdown + arg inputs
- Flag: dropdown (flags from toolkit) + method dropdown + arg input
- Timer: same as hardware, filtered to TIMER type
- Special: dropdown (INC_TRIAL_COUNTER, etc.)
- Custom Method: dropdown of `CALLABLE_METHODS` from toolkit + optional arg inputs
  (these are developer-written Python methods exposed by the toolkit for GUI use)

Args show smart input: param ref toggle, literal input, or flag ref dropdown.

**State node appearance in canvas:**
- Passthrough state (existing Python method, no entry_actions): shown with lock icon + `{py}` badge; body panel is read-only, shows method name only
- GUI-constructed state: fully editable body panel
- Hybrid state (GUI-constructed + `type:method` actions): editable, custom methods shown with `{py}` tag inline

### Trigger Assignment Panel

```
┌─────────────────────────────────────────────────────┐
│ TRIGGER CALLBACKS                                   │
│                                                     │
│ TOUCH_INT   [Touch Detector ▾]  view: LICKER{n}     │
│ IR1         [Digital Input  ▾]  view: IR1           │
│ IR2         [Default        ▾]                      │
│ SOLENOID1   [Default        ▾]                      │
│                                                     │
│ Note: All triggers log Hardware_Event automatically │
│ (this panel configures semantic view updates only)  │
└─────────────────────────────────────────────────────┘
```

---

## Hardware Abstraction Roadmap

### Current
State bodies reference `self.hardware['GPIO']['SOLENOID1']` directly in Python.

### Phase 1 (this plan)
`SEMANTIC_HARDWARE` maps friendly names to `(group, id)` tuples.
State body JSON uses `"ref": "reward_port"` — works at action-interpreter time.

### Future: Hardware Profiles
A `hardware_profile.json` per rig:
```json
{
  "reward_port":    { "type": "gpio.Solenoid",    "pin": 18, "pulse_width": 50 },
  "stimulus_led":   { "type": "gpio.LED_RGB",     "pin_r": 22, ... }
}
```
Same FDA JSON runs on Rig A and Rig B by swapping the profile.
Enables: multi-rig experiments with one task definition, hardware simulation for testing.

### Future: Hardware Capability Interface
Instead of per-class methods, define a capability interface:
```python
class Pulsable(Protocol):
    def pulse(self, duration_ms: int): ...

class Settable(Protocol):
    def set(self, value: bool): ...
```
Hardware classes implement capabilities. Action JSON validates against capabilities, not classes.

---

## Library Management on Pi

### Solution: Dependency Declaration in Toolkit

```python
class MyToolkit(mics_task):
    REQUIRED_PACKAGES = ["adafruit-circuitpython-mpr121==1.2.0"]
```

### HANDSHAKE Check

`extract_task_metadata()` in `pilot.py` includes `required_packages` in the payload.
The orchestrator HANDSHAKE handler:
1. Compares against a cached `installed_packages` state per pilot
2. If missing: logs a warning
3. Web UI shows a badge on the toolkit card: "Missing deps" with the package list

### Install via SSH (Power User Flow)

New API endpoint `POST /api/pilots/:name/install-package` with `{ "package": "..." }`:
- Orchestrator sends `INSTALL_PACKAGE` ZMQ message to Pi
- Pi runs `pip install <package>` in a subprocess
- Streams output back via `INSTALL_LOG` messages

**Recommended**: Also maintain `~/pi-mirror/pilot/requirements_pi.txt`.
`tools/deploy_pi.sh` runs `pip install -r requirements_pi.txt` during sync.

---

## MCP-Assisted Development Workflow

| MCP | How it helps in this plan |
|---|---|
| **postgres** | Verify HANDSHAKE populated `task_toolkits`, inspect stored `fda_json`, check schema |
| **filesystem** | Read Pi mirror files at `/home/ido/pi-mirror/` directly |
| **docker** | Read orchestrator logs during Phase 1 — verify `state_machine` kwarg in START payload |
| **git** | Trace Pi task file changes, verify rsync completed |

---

## Custom Skills Relevant to This Plan

| Skill | When to use |
|---|---|
| `/new-pi-task` | When writing a new ToolKit class — FDA scaffolding, FLAGS, INC_TRIAL_COUNTER |
| `/mics-debug` | During Phase 1 testing — diagnose Pi task hang after FDA JSON loading |
| `/es-query` | After Phase 1 — verify CONTINUOUS events flow from JSON-loaded task |
| `/protocol-debug` | During Phase 4 — trace graduation with task definitions in protocol steps |

---

## Pi Code Workflow (from this machine)

```bash
# Edit Pi files in ~/pi-mirror/
# Then sync to Pi:
tools/sync_pi.sh                        # rsync only
tools/deploy_pi.sh pi@132.77.72.28      # rsync + restart

# SSH key: ~/.ssh/pi_mics
# Pi address: pi@132.77.72.28
# Pi code root: ~/Apps/mice_interactive_home_cage/
```

---

## Key Design Decisions

- **Conditions are AND-only** — matches current FDA behavior, keeps UI simple
- **rhs can be literal or param reference** — param-driven thresholds without changing flow
- **Backward compatible** — v1 JSON and hardcoded FDA still work; `state_machine` kwarg optional
- **State machine lives on task definition, not protocol** — one task def = one fixed flow
- **ToolKit discovery is automatic** — HANDSHAKE populates toolkits table
- **Semantic refs decouple logic from wiring** — same JSON on different hardware
- **Hot-reload is next-entry safe** — no interrupt of running state, predictable behavior
- **Trigger handlers configure semantic view updates only** — Hardware_Event logging is
  unconditional and not configurable via JSON; `trigger_assignments` only adds semantic
  callbacks to `self.triggers[pin]` which runs after logging in `execute_trigger()`
- **State body actions are interpreted, not compiled** — keeps it serializable, inspectable,
  and GUI-buildable. No `exec()` or pickle needed for standard actions
- **Method registry keyed by name, not object** — Python bound method identity is fragile;
  `_state_method_registry` uses `state_name: str` as key

## Open Questions (deferred)

- OR conditions between transitions (AND sufficient for now)
- Compound conditions within a single transition (already supported by list)
- Toolkit composition (combining two toolkits' methods) — hardware conflict resolution needed
- Parallel states / sub-machines — not needed yet
- Action sequences with conditional branching (`if flag == X: do_action`) — could be added
  as an `"if"` action type in v3; for now use FDA transitions to handle branching
- Undo/redo in the FDA editor
- FDA JSON versioning and migration (v1 → v2 auto-upgrade script)
- Rate-limiting hot-reload pushes (prevent researcher from spamming while task runs)
- `boolean_conflict()` in FDA is evaluated at add-time — during hot-reload,
  `replace_transitions` bypasses this check; consider adding a pre-validation pass
