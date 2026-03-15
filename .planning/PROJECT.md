# MICS Backend

## What This Is

MICS (Mice Interactive Cage System) is a behavioral research experiment management system for running tasks on Raspberry Pi pilot devices. Lab animals (mice) perform behavioral tasks controlled by the Pi; researchers configure protocols and sessions via a web UI; an orchestrator dispatches tasks to pilots over ZMQ and streams behavioral data to ElasticSearch.

The current work adds two major capabilities: (1) a no-code visual editor for building task state machines without Python editing or Pi restarts, and (2) a browser-based Pi code editor for developers who need to extend the system.

## Core Value

Researchers can define, modify, and deploy behavioral task logic — including state machine flows, hardware actions, and trigger callbacks — without writing Python or restarting the Pi.

## Requirements

### Validated

- ✓ Pilot grid with live WebSocket status — existing
- ✓ Protocol creation and assignment — existing
- ✓ Session management and run tracking — existing
- ✓ ZMQ-based task dispatch to Pi — existing
- ✓ ElasticSearch continuous data ingestion — existing
- ✓ JWT auth and PostgreSQL persistence — existing
- ✓ Subject/Project/Experiment hierarchy — existing
- ✓ FiniteDeterministicAutomaton state machine on Pi — existing
- ✓ Hardware abstraction with @log_action auto-logging — existing

### Active

**Feature 1 — ToolKit + FDA Redesign**
- [ ] Pi can load an FDA state machine from JSON without restart (Phase 1)
- [ ] State body actions (entry_actions) are declared in JSON, not Python (Phase 1)
- [ ] SEMANTIC_HARDWARE maps friendly names to physical hardware (Phase 1)
- [ ] GPIO trigger callbacks are unconditional for logging; semantic view updates are JSON-configurable (Phase 1)
- [ ] Hot-reload: push updated state logic to running Pi via UPDATE_FDA ZMQ without restart (Phase 1)
- [ ] task_toolkits table populated from HANDSHAKE; task_definitions table stores FDA JSON (Phase 2)
- [ ] REST API for CRUD on task definitions + push-to-pilot endpoint (Phase 2)
- [ ] Visual react-flow FDA editor: state nodes, transition edges, condition builder (Phase 3)
- [ ] State body editor panel: entry actions, blocking toggle, return data (Phase 3)
- [ ] Trigger assignment panel: configures semantic view-update callbacks (Phase 3)
- [ ] Protocol step references task definition instead of raw task_type (Phase 4)

**Feature 2 — Pi Code Editor**
- [ ] Browser-based read-only file viewer for Pi task files with syntax highlighting (Phase A)
- [ ] SSH health status endpoint for Pi connection (Phase A)
- [ ] Live terminal for running commands on Pi via xterm.js websocket (Phase B)
- [ ] Edit Pi files in-browser + restart pilot process (Phase C)
- [ ] Sync pi-mirror to Pi + package management UI (Phase D)

### Out of Scope

- OR conditions between FDA transitions — AND-only for now; keeps UI simple
- Toolkit composition (combining two toolkits' methods) — hardware conflict resolution needed first
- Parallel sub-states or hierarchical state machines — not needed for current experiments
- Action sequences with conditional branching inside a state body — use FDA transitions for branching
- Mobile app — web-first always
- Multi-Pi Pi editor UI — single Pi for now; env var list planned for future

## Context

- **Services**: FastAPI (api/:8000), Orchestrator ZMQ gateway (orchestrator/:9000), React SPA + FastAPI proxy (web_ui/:8080), backup
- **Pi**: Raspberry Pi 4 at `pi@132.77.72.28`, SSH key `~/.ssh/pi_mics`; Pi code at `~/Apps/mice_interactive_home_cage/`; local mirror at `~/pi-mirror/`
- **Pi task hierarchy**: `Task → mics_task → ConcreteToolKit (pilot/plugins/)`; FDA wired in `__init__`, `next(self.stages)` drives the stage loop
- **Hardware auto-logging**: `@log_action` / `@auto_log` on all hardware/tracker methods dispatches `Hardware_Event` → `Event_Dispatcher` → `node.send('T', 'CONTINUOUS', data)` unconditionally
- **Trigger flow**: `hw.assign_cb(handle_trigger)` → `event_queue` → `execute_trigger()` dispatches `Hardware_Event` FIRST, then calls `self.triggers[pin]` for semantic view updates
- **ZMQ messages**: CONTINUOUS, INC_TRIAL_COUNTER, DATA, HANDSHAKE, START, STOP; new: UPDATE_FDA, HOT_RELOAD_ACK
- **DB**: Dual ORM — SQLModel owns subjects/protocols; SQLAlchemy owns pilots/sessions/runs/task_definitions
- **Detailed plans**: `.claude/docs/toolkit_fda_plan.md` (GSD sections: Why/What/How) and `.claude/docs/pi_code_editor_plan.md`

## Constraints

- **Pi resources**: Raspberry Pi 4 — no Jupyter/code-server (too heavy); asyncssh + Monaco is the right weight
- **No Pi restart for state logic changes**: hot-reload via ZMQ must work while task is running
- **Backward compatibility**: tasks with hardcoded FDA must continue to work; `state_machine` kwarg is optional
- **Exec gate**: Pi write/exec endpoints require `ALLOW_PI_EXEC=true` env var; read-only viewer is always safe
- **Method registry by name**: Python bound method identity is fragile; `_state_method_registry` keyed by `state_name: str`
- **No npm/npx in shell PATH by default**: nvm required; install path `/home/ido/.nvm/`

## Key Decisions

| Decision | Rationale | Outcome |
|---|---|---|
| Hardware_Event logging is unconditional | `execute_trigger()` always dispatches Hardware_Event before calling `self.triggers[pin]`; logging cannot be disabled via JSON | — Pending |
| trigger_assignments configures only semantic view-update layer | Logging path (`handle_trigger → execute_trigger`) is not configurable; `trigger_assignments` only adds callbacks to `self.triggers[pin]` | — Pending |
| FDA v2 JSON with entry_actions per state | State body actions (hardware calls, tracker updates) are declarative JSON, interpreted at runtime; no exec() or pickle | — Pending |
| SEMANTIC_HARDWARE dict in toolkit | Friendly names decouple FDA JSON from physical wiring; same JSON runs on different rigs | — Pending |
| Hot-reload is next-entry safe | Method refs replaced between `next()` calls; currently-executing state is never interrupted | — Pending |
| Monaco + asyncssh for Pi editor | Jupyter/code-server too heavy for Pi; Monaco tree-shakeable; asyncssh keeps web_ui non-blocking | — Pending |
| _state_method_registry keyed by name string | Python bound method `is` identity is fragile after rebuild; string key is stable | — Pending |

---
*Last updated: 2026-03-15 after GSD initialization*
