# ToolKit + FDA Plan

Redesign of the Pi task system to separate primitive operations (ToolKit, Python)
from experimental flow (Task Definition, JSON/DB/GUI).

Status: PLANNED — not yet started.

---

## The Problem with the Current Model

Each task (e.g. `AppetitiveTaskReal`) is a single Python class that hardcodes both
what it can do (state methods, hardware, flags) and how it flows (FDA transitions in
`__init__`). Changing the flow requires editing Python on the Pi. There is no visual
representation of the state machine and no way to share flows between tasks.

---

## Core Concepts

### ToolKit (Python, on Pi)

A Python class (subclass of `mics_task`) that declares:
- `HARDWARE` — which hardware objects are used
- `FLAGS` — Tracker instances (hits, misses, lick count, etc.)
- `PARAMS` — tunable parameters (ITI, open_duration, etc.)
- State methods — the primitive operations (`trial_onset`, `stimulus`, `state_lick`, etc.)

**It does NOT wire the FDA in `__init__`.** That is the key difference from the current model.
The toolkit is a library. Multiple different task definitions can be assembled from one toolkit.

Currently `mics_task` subclasses ARE toolkits — they just also hardcode their own FDA.
Stripping the FDA wiring out of `__init__` turns them into proper toolkits.

### Task Definition (JSON, in DB, built in GUI)

A user-assembled state machine built from a toolkit's building blocks:
- Which states to include
- Which transitions connect them
- What conditions guard each transition
- Default param values

Stored in the DB. Built visually in the web UI. One toolkit → many task definitions.
Task definitions are what protocol steps reference (as they currently reference task_type).

### Protocol Step

Unchanged concept: references a task definition + sets param overrides.

### The Flow

```
ToolKit (Python on Pi)
    ↓  discovered via HANDSHAKE
task_toolkits table (DB)
    ↓  user assembles in GUI
task_definitions table (DB)  ← has fda_json + default_params
    ↓  referenced by
protocol_step_templates
    ↓  params overridden at
session_runs
```

---

## FDA JSON Schema

### Condition format

```json
{ "view": "current_lick", "op": ">=", "rhs": { "literal": 3 } }
{ "view": "current_lick", "op": ">=", "rhs": { "param": "lick_threshold" } }
{ "view": "IR2",          "op": "==", "rhs": { "literal": true } }
{ "view": "TIMER_TO_NOSEPOKE", "op": "==", "rhs": { "literal": false } }
```

Supported ops: `==`, `!=`, `>`, `>=`, `<`, `<=`

`rhs` is either:
- `{ "literal": <value> }` — hardcoded value
- `{ "param": "<param_name>" }` — resolved from task params at runtime

Condition list on a transition is AND (all must be true) — matches current FDA behavior.
Empty list `[]` = unconditional transition (always fires immediately).

### Full schema

```json
{
  "toolkit": "AppetitveTaskReal",
  "version": 1,
  "initial_state": "prepare_session",
  "states": [
    "prepare_session",
    "trial_onset",
    "stimulus",
    "state_start_time_window_to_nosepoke",
    "state_wait_time_window",
    "state_start_time_window_to_reward",
    "state_nose_poke",
    "state_lick",
    "state_un_nosepoke",
    "start_timer_ITI",
    "state_ITI",
    "state_ITI_nose_poke",
    "state_miss",
    "state_end_trial"
  ],
  "transitions": [
    {
      "from": "prepare_session",
      "to": "trial_onset",
      "conditions": [],
      "description": "unconditional"
    },
    {
      "from": "trial_onset",
      "to": "stimulus",
      "conditions": [],
      "description": "unconditional"
    },
    {
      "from": "stimulus",
      "to": "state_start_time_window_to_nosepoke",
      "conditions": [],
      "description": "unconditional"
    },
    {
      "from": "state_start_time_window_to_nosepoke",
      "to": "state_wait_time_window",
      "conditions": [],
      "description": "unconditional"
    },
    {
      "from": "state_wait_time_window",
      "to": "state_start_time_window_to_reward",
      "conditions": [
        { "view": "IR2", "op": "==", "rhs": { "literal": true } }
      ],
      "description": "mouse performed nose poke — open time window to achieve reward"
    },
    {
      "from": "state_wait_time_window",
      "to": "state_miss",
      "conditions": [
        { "view": "TIMER_TO_NOSEPOKE", "op": "==", "rhs": { "literal": false } }
      ],
      "description": "mouse didn't perform nose poke during the time window"
    },
    {
      "from": "state_start_time_window_to_reward",
      "to": "state_nose_poke",
      "conditions": [],
      "description": "unconditional"
    },
    {
      "from": "state_nose_poke",
      "to": "state_lick",
      "conditions": [
        { "view": "LICKER1", "op": "==", "rhs": { "literal": true } }
      ],
      "description": "mouse licked the reward"
    },
    {
      "from": "state_lick",
      "to": "state_nose_poke",
      "conditions": [
        { "view": "LICKER1", "op": "==", "rhs": { "literal": false } }
      ],
      "description": "mouse stopped licking"
    },
    {
      "from": "state_nose_poke",
      "to": "state_un_nosepoke",
      "conditions": [
        { "view": "IR2", "op": "==", "rhs": { "literal": false } }
      ],
      "description": "mouse got out of nose poke"
    },
    {
      "from": "state_un_nosepoke",
      "to": "state_nose_poke",
      "conditions": [
        { "view": "IR2", "op": "==", "rhs": { "literal": true } }
      ],
      "description": "mouse performed nose poke again"
    },
    {
      "from": "state_un_nosepoke",
      "to": "start_timer_ITI",
      "conditions": [
        { "view": "TIMER_TO_REWARD", "op": "==", "rhs": { "literal": false } },
        { "view": "hit_trial",        "op": "==", "rhs": { "literal": true } }
      ],
      "description": "reward window expired and mouse got the reward — start ITI"
    },
    {
      "from": "state_un_nosepoke",
      "to": "state_miss",
      "conditions": [
        { "view": "TIMER_TO_REWARD", "op": "==", "rhs": { "literal": false } },
        { "view": "hit_trial",        "op": "==", "rhs": { "literal": false } }
      ],
      "description": "reward window expired and mouse didn't claim reward — miss"
    },
    {
      "from": "start_timer_ITI",
      "to": "state_ITI",
      "conditions": [],
      "description": "unconditional"
    },
    {
      "from": "state_ITI",
      "to": "state_ITI_nose_poke",
      "conditions": [
        { "view": "IR2", "op": "==", "rhs": { "literal": true } }
      ],
      "description": "false alarm — mouse nose-poked during ITI"
    },
    {
      "from": "state_ITI_nose_poke",
      "to": "start_timer_ITI",
      "conditions": [
        { "view": "IR2", "op": "==", "rhs": { "literal": false } }
      ],
      "description": "mouse released nose poke — restart ITI"
    },
    {
      "from": "state_ITI",
      "to": "state_end_trial",
      "conditions": [
        { "view": "TIMER_TO_NEW_TRIAL", "op": "==", "rhs": { "literal": false } }
      ],
      "description": "ITI timer expired — end trial"
    },
    {
      "from": "state_end_trial",
      "to": "trial_onset",
      "conditions": [],
      "description": "start new trial"
    },
    {
      "from": "state_miss",
      "to": "start_timer_ITI",
      "conditions": [],
      "description": "after miss — wait ITI"
    }
  ]
}
```

---

## Implementation Phases

### Phase 1 — Foundation (Pi + no UI changes, fully backward compatible)

**Use `/new-pi-task` skill** when writing any new ToolKit class in this phase — it provides the correct FDA scaffolding, PARAMS/HARDWARE/FLAGS structure, and critical INC_TRIAL_COUNTER placement.

**Files to change:**

`~/pi-mirror/autopilot/autopilot/tasks/mics_task.py`
- Add `load_fda_from_json(self, definition: dict)` method:
  - Resolves state names → `getattr(self, name)` (raises clearly if missing)
  - Converts condition dicts → lambdas over `self.view` and `self.params`
  - Handles `rhs.literal` and `rhs.param` (looks up `self.params[key]` at lambda call time)
  - Calls `add_method` / `set_initial_method` / `add_transition`
- In `__init__`: if `state_machine` in kwargs → call `load_fda_from_json`; else → existing code

`~/pi-mirror/autopilot/autopilot/core/pilot.py`
- `extract_task_metadata()`: add FLAGS to the returned dict
  - FLAGS is a class-level dict, same pattern as PARAMS
- Add `STAGE_NAMES` to returned dict (already a class attribute)

New file: `~/pi-mirror/pilot/protocols/AppetitiveTaskReal.fda.json`
- The FDA JSON above (AppetitiveTaskReal state machine as reference)

New file: `tools/validate_fda.py` (in this repo, runs locally)
- Loads a toolkit class + an FDA JSON
- Checks: all state names exist as methods, all view keys exist in FLAGS or HARDWARE, all param refs exist in PARAMS
- Use development sanity check before deploying to Pi

New files: `tools/sync_pi.sh` + `tools/deploy_pi.sh`
- sync_pi.sh: rsync ~/pi-mirror/autopilot/ → Pi
- deploy_pi.sh: sync + ssh restart of pilot process

**How to test Phase 1:**
- Run `AppetitiveTaskReal` with `state_machine=<loaded JSON>` in kwargs
- Confirm behavior identical to current hardcoded version
- Run `validate_fda.py` on the JSON
- Use **docker MCP**: "show last 50 lines of mics_orchestrator logs" — verify `state_machine` key appears in the START payload sent to Pi
- Use **`/mics-debug`** skill if the task hangs after loading from JSON

---

### Phase 2 — DB + API

**Before starting:** Use **postgres MCP** to inspect the current `task_definitions` table: "show all columns in task_definitions and a sample row" — confirm what HANDSHAKE currently populates so the migration is accurate.

**Concept rename in DB:**

New table `task_toolkits`:
- Populated from HANDSHAKE (replaces current `task_definitions` for Pi-discovered tasks)
- Columns: `name`, `pilot_id`, `states` (JSON list), `flags` (JSON), `params_schema` (JSON), `hardware` (JSON), `file_hash`

Repurposed `task_definitions` (now user-created):
- `toolkit_name` (FK to task_toolkits)
- `name` (user-given label)
- `fda_json` (the state machine definition)
- `default_params` (JSON)
- `created_at`

**Migration note:** `task_definitions` currently exists and is populated by HANDSHAKE (`orchestrator_station.py`). The migration must:
1. Create `task_toolkits` and copy existing `task_definitions` rows into it
2. Alter `task_definitions` to add `toolkit_name`, `fda_json` columns
3. Update orchestrator HANDSHAKE handler to write to `task_toolkits` instead

Use **postgres MCP** after migration: "count rows in task_toolkits and task_definitions" to verify data integrity.

New API endpoints:
- `GET /api/toolkits` — list available toolkits per pilot
- `POST /api/task-definitions` — create named task from toolkit + FDA JSON
- `GET /api/task-definitions/{id}`
- `PUT /api/task-definitions/{id}`
- `DELETE /api/task-definitions/{id}`

Protocol steps continue referencing `task_definitions.id` — no change to session/run flow.

Orchestrator change: `_build_step_task()` includes `state_machine` from the task definition in the START payload.

---

### Phase 3 — Visual FDA Editor (Web UI)

**Use `/frontend-design` skill** when building this page. Provide it: the 3-panel layout below, existing CSS classes from `style.css` (see MEMORY.md), and real API responses from `GET /api/toolkits/:name`.

New page: `/react/task-editor/:toolkitName` (or `/react/task-editor/:taskDefinitionId` for editing existing)

**Layout:**
```
┌─────────────────┬──────────────────────────┬──────────────────┐
│  LEFT PANEL     │  CANVAS (react-flow)      │  RIGHT PANEL     │
│                 │                           │                  │
│  States         │  [prepare_session] ──────▶│  Transition:     │
│  (from toolkit) │       │                   │  from: state_A   │
│                 │       ▼                   │  to:   state_B   │
│  View Keys      │  [trial_onset]            │                  │
│  - IR2 (bool)   │       │                   │  Conditions:     │
│  - LICKER1(bool)│       ▼                   │  + Add condition │
│  - hits (int)   │  [stimulus] ─────────────▶│                  │
│  - ...          │                           │  [view] [op] [v] │
│                 │                           │                  │
│  Params         │                           │  Save transition │
│  - lick_thresh  │                           │                  │
└─────────────────┴──────────────────────────┴──────────────────┘
```

**Library:** `reactflow` (npm: `@xyflow/react`)

**Interaction:**
- Drag state from left panel → canvas node
- Drag between node handles → creates edge
- Click edge → right panel shows condition builder
- Condition builder: dropdown (view keys) + dropdown (op) + input (literal) or dropdown (param name)
- Save button → POST/PUT to `/api/task-definitions`

**Data flow:**
- On load: fetch toolkit metadata from `/api/toolkits/:name` (states, flags, hardware, params)
- On save: serialize canvas to FDA JSON → POST to `/api/task-definitions`

---

### Phase 4 — Protocol step selects Task Definition

Protocol creation UI change: instead of selecting a raw `task_type`, researcher selects a saved task definition by name. The FDA is already embedded. Researcher only sets param overrides.

This is mostly a UI change — backend already supports it after Phase 2.

**New entity context (from `subject_project_experiment_plan.md`):**
The entity hierarchy is now: `Project → Experiment → ProtocolTemplate → ProtocolStep → TaskDefinition`.
Phase 4 affects the **Experiment detail page** (`/react/experiments/:id`) and the **protocol builder** (`/react/protocols-create`). Both will need updating to show task definitions instead of raw task_type strings.

- `ExperimentDetail` page: protocol palette shows task definitions (from `GET /api/task-definitions`), not raw toolkits
- `ProtocolsCreate` page: step task picker switches from `task_type` dropdown → task definition picker (name + embedded FDA preview)
- `GET /api/tasks/leaf` (current endpoint returning raw task types) may be deprecated in favour of `GET /api/task-definitions`

**Use `/frontend-design` skill** when updating these pages.

---

## MCP-Assisted Development Workflow

These MCP servers (all configured in `~/.claude.json`) accelerate implementation:

| MCP | How it helps in this plan |
|---|---|
| **postgres** | Query `task_definitions` / `task_toolkits` live — verify HANDSHAKE populated correctly, inspect FDA JSON stored in DB, check schema before and after Phase 2 migration |
| **filesystem** | Read Pi mirror files at `/home/ido/pi-mirror/` directly — inspect FiniteDeterministicAutomaton.py, mics_task.py, existing task classes without switching context |
| **docker** | Read orchestrator logs during Phase 1 testing — verify `state_machine` kwarg is forwarded in START payload, inspect HANDSHAKE messages in real time |
| **git** | Trace when Pi task files last changed — useful for verifying rsync completed correctly |

**Postgres MCP usage examples for this plan:**
- "Show me all rows in task_definitions" — verify HANDSHAKE populated correctly
- "What columns does task_definitions have?" — before Phase 2 schema change
- "Show the fda_json for task definition id 3" — inspect stored state machine

---

## Custom Skills Relevant to This Plan

| Skill | When to use |
|---|---|
| `/new-pi-task` | When writing a new ToolKit class in Phase 1 — gives FDA scaffolding, PARAMS/HARDWARE/FLAGS structure, INC_TRIAL_COUNTER reminder |
| `/mics-debug` | During Phase 1 testing — diagnose if Pi task is hanging in wait_for_condition() after FDA JSON loading |
| `/es-query` | After Phase 1 — verify CONTINUOUS events are flowing correctly from the new FDA-loaded task |
| `/protocol-debug` | During Phase 4 — trace graduation when task definitions reference protocol steps |

---

## Pi Code Workflow (from this machine)

```bash
# Edit Pi files in ~/pi-mirror/
# Then sync to Pi:
tools/sync_pi.sh                        # rsync only
tools/deploy_pi.sh pi@132.77.72.28      # rsync + restart

# SSH key: ~/.ssh/pi_mics
# Pi address: pi@132.77.72.28 (password was mIc100, now key auth)
# Pi code root: ~/Apps/mice_interactive_home_cage/
```

All Pi edits happen in `~/pi-mirror/` on this machine. Claude can read Pi files via the
**filesystem MCP** (`/home/ido/pi-mirror/` is an allowed root) and propose edits directly
without needing separate context.

Multiple Pis in future: parameterize deploy_pi.sh with host argument,
loop in `tools/deploy_all_pis.sh` over a `tools/pi_hosts.txt` file.

---

## Key Design Decisions (already settled)

- **Conditions are AND-only** (all lambdas must be true) — matches current FDA behavior, keeps UI simple
- **rhs can be literal or param reference** — enables param-driven thresholds without changing flow
- **Backward compatible** — tasks with hardcoded FDA continue to work; `state_machine` kwarg is optional
- **State machine lives on task definition, not protocol** — one task definition = one fixed flow; protocol step only sets params
- **ToolKit discovery is automatic** — HANDSHAKE populates toolkits table; no manual registration

## Open Questions (deferred)

- OR conditions between transitions (not needed yet, AND is sufficient)
- Compound conditions within a single transition (A AND B AND C — already supported by list)
- Toolkit composition (combining two toolkits' methods) — future, needs hardware conflict resolution
- Hardware abstraction layer (run same task definition on different hardware configurations) — future
