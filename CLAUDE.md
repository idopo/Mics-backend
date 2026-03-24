# MICS Backend

Behavioral research experiment management system for running tasks on Raspberry Pi pilot devices (subjects are lab animals). Researchers configure protocols and sessions via the web UI; the orchestrator dispatches tasks to pilots over ZMQ and streams data to ElasticSearch.

## Commands

| Command | Purpose |
|---|---|
| `docker compose up --build` | Start all services (api:8000, web_ui:8080, orchestrator:9000) |
| `docker compose up --build api` | Rebuild and restart api only |
| `docker compose up --build web_ui` | Rebuild and restart web_ui (React + proxy) |
| `cd web_ui/react-src && npm run build` | Rebuild React SPA only (faster than full compose rebuild) |

Health check: `GET http://localhost:8000/health`
No automated test suite — verify manually by calling relevant endpoints after changes.

## Services

| Service | Port | Responsibility |
|---|---|---|
| `api/` | 8000 | PostgreSQL-backed REST API, JWT auth |
| `orchestrator/` | 9000 | ZMQ gateway to pilots, Redis state, ES ingestion |
| `web_ui/` | 8080 | FastAPI proxy + React SPA (+ legacy Jinja2) |
| `backup/` | — | supercronic: nightly pg_dump + ES snapshot to SMB share |

## Key Directories

```
api/
  main.py          # all API routes (~2097 lines) — split before adding more
  models.py        # SQLModel (subjects/protocols) + SQLAlchemy (pilots/sessions/runs)
  auth.py          # JWT verification (HS256, audience/issuer enforced)
  db.py            # engine + session factories

orchestrator/orchestrator/
  main.py          # wires ZMQ message keys to handler methods (line 71-80)
  orchestrator_station.py  # runtime engine: message handlers, worker threads, Redis writes
  RouterGateway.py # threaded ZMQ ROUTER, Tornado IOLoop
  api.py           # orchestrator REST API (run start/stop, /pilots/live)
  state.py         # thread-safe in-memory pilot state (OrchestratorState)
  mics/mics_api_client.py  # synchronous HTTP client to api service

web_ui/
  app.py           # FastAPI proxy + WebSocket server (404 lines)
  react-src/       # React + TypeScript SPA (Vite build → static/react/)
    src/
      pages/       # index/, subjects/, protocols/, protocols-create/,
                   # pilot-sessions/, subject-sessions/
      components/  # Nav, Layout, Skeleton, StatusBadge, ProtocolInfoModal
      api/         # typed fetch helpers per domain (pilots, sessions, subjects, protocols, tasks)
      hooks/       # useWebSocket, useConcurrentFetch
      types/       # index.ts — shared TypeScript types
  static/
    react/         # Vite output (served at /static/react/)
    pilot_sessions.js            # legacy Jinja2 frontend (still in use for some views)
    session_overrides_modal.js   # legacy override modal
  templates/       # Jinja2 HTML templates (legacy)

backup/
  backup.sh        # pg_dump + ES snapshot, SMB upload

.claude/
  docs/            # architectural_patterns.md, toolkit_fda_plan.md, subject_project_experiment_plan.md
  skills/          # custom Claude Code slash commands
  backlog/         # persistent task backlog (BACKLOG.md index + per-task files)
```

## Environment Variables

- `DATABASE_URL` — PostgreSQL DSN (api)
- `JWT_SECRET`, `JWT_ALGORITHM`, `JWT_AUDIENCE`, `JWT_ISSUER` — token validation (api)
- `MICS_API_TOKEN` — pre-issued JWT used by web_ui and orchestrator to call the api
- `REDIS_URL` — Redis DSN (orchestrator, web_ui)
- Orchestrator config: `orchestrator/orchestrator/prefs.json` (MICS_API_URL, MICS_API_TOKEN, NAME, MSGPORT)

## React SPA

Served at `/react/*`. Vite builds to `web_ui/static/react/`. FastAPI catchall: `@app.get("/react/{path:path}")` → `templates/react/index.html`.

**Critical vite.config.ts:** `base: '/static/react/'`, `outDir: 'dist'`, `entryFileNames: 'main.js'`

**Dockerfile:** two-stage build, Node stage uses `npm install` (no lockfile), copies from `dist/`.

**Routes:**
- `/react/` — pilot grid, live WS updates
- `/react/subjects-ui` — subject list + create
- `/react/protocols-ui` — protocol list + assign
- `/react/protocols-create` — task palette + protocol builder
- `/react/pilots/:pilot/sessions-ui` — session cards, lazy hydration, filter, overrides
- `/react/subjects/:subject/sessions-ui` — session list + pilot select + start
- `/react/projects-ui` — projects list + create
- `/react/projects/:projectId` — project detail + experiments
- `/react/experiments/:experimentId` — experiment detail + protocol assign
- `/react/researchers-ui` — researchers list + inline edit/remove
- `/react/iacuc-ui` — IACUC protocols list + add/remove

**API shapes (verified):**
- `GET /api/sessions` → `{ session_id, started_at, n_runs }[]`
- `GET /api/sessions/{id}` → `{ session_id, runs: [{ run_id, subject_name, protocol_id, ... }] }`
- `GET /api/protocols` → steps have `task_type`, `step_name`, `params` (graduation inside `params.graduation`)
- `GET /api/tasks/leaf` → `{ task_name, default_params: { key: { tag, type } } }`
- `WS /ws/pilots` → `{ pilotName: { connected, state, active_run: { id, session_id, subject_key } } }`
- `POST /api/sessions/{id}/start-on-pilot` → `{ pilot_id, mode?, overrides? }`
- `POST /api/session-runs/{run_id}/stop` — stop endpoint (not `/api/pilots/.../stop`)
- `POST /api/assign-protocol` → `{ status, assigned, session: { status, session_id, runs_started } }`

**CSS:** Use classes from `web_ui/react-src/src/style.css`. Do not invent new class names.

## Pi / Orchestrator Integration

- Pi mirror: `~/pi-mirror/` (rsync from `pi@132.77.72.28:~/Apps/mice_interactive_home_cage/`)
- ZMQ: Pi DEALER identity=`NAME`, connects to orchestrator at `TERMINALIP:PUSHPORT` (5560); orchestrator NAME=`"T"`
- `INC_TRIAL_COUNTER` must be sent **explicitly** by the task; triggers graduation check in orchestrator
- HANDSHAKE auto-registers task params from Pi plugins into `task_definitions` table

## Dual ORM Pattern

SQLModel owns: `subjects`, `protocol_templates`, `protocol_step_templates`, `subject_protocol_runs`
SQLAlchemy owns: `pilots`, `sessions`, `session_runs`, `run_progress`, `task_definitions`
Both `metadata.create_all()` called at startup. Use matching session type per table.

## Patterns to Follow

- **New API endpoint**: See `api/main.py` lines 1-50 for imports/setup; follow existing endpoint structure. Use SQLModel session for subject-domain tables, SQLAlchemy session for pilot/session-domain tables.
- **New React page**: Copy structure from `web_ui/react-src/src/pages/researchers/` (simplest page). Register route in `App.tsx`.
- **ZMQ handler**: See `orchestrator/orchestrator/orchestrator_station.py` — add key→method mapping in `main.py` lines 71-80.
- **Soft-delete**: Use `is_hidden: bool = False` pattern (see Researcher, IACUCProtocol models).

## Avoid

- **Don't add to `api/main.py` without checking size** — already at ~2097 lines (hard limit is 500 per coding standards). Extract to a new router module first.
- **Don't use Jinja2 templates for new features** — legacy only. New UI goes in React SPA.
- **Don't mix ORM session types** — SQLModel sessions for `subjects`/`protocol_templates`/`subject_protocol_runs`; SQLAlchemy sessions for everything else. Mixing causes silent failures.
- **Don't hardcode ZMQ addresses/ports** — use `orchestrator/orchestrator/prefs.json`.

## Additional Documentation

- `.claude/docs/architectural_patterns.md` — 13 recurring patterns with file:line references
- `.claude/docs/toolkit_fda_plan.md` — ToolKit + FDA redesign plan (PLANNED, not started); includes state body actions, trigger assignment, semantic hardware abstraction, hot-reload via ZMQ
- `.claude/docs/pi_code_editor_plan.md` — Monaco Editor + SSH proxy for browsing/editing Pi code from browser (PLANNED, not started)
- `.claude/docs/subject_project_experiment_plan.md` — subject/project/experiment hierarchy plan
- `.claude/backlog/BACKLOG.md` — persistent task backlog

## Planning Workflow

**Always use GSD for planning** — never use built-in plan mode (EnterPlanMode) for feature work.

| Situation | GSD Skill |
|---|---|
| New ToolKit / FDA feature | `gsd-toolkit-fda` |
| New phase / general feature | `gsd:plan-phase` |
| Add phase to roadmap | `gsd:add-phase` |
| Quick atomic task | `gsd:quick` |
| Check progress | `gsd:progress` |

## Skills (Slash Commands)

Custom skills live in `.claude/skills/`. Invoke with `/skill-name`.

| Skill | Trigger | Purpose |
|---|---|---|
| `/backlog` | manual | Add, list, update backlog tasks with full context |
| `/plan-implement` | manual | Plan → sub-agent review → implement workflow |
| `mics-debug` | auto | Debug stuck/unresponsive MICS pilot |
| `new-api-endpoint` | auto | Scaffold a new FastAPI endpoint |
| `es-query` | auto | Query Elasticsearch for behavioral data |
| `new-pi-task` | auto | Scaffold a new behavioral task for the Pi |
| `pi-deploy` | auto | Sync pi-mirror → Pi and stop/start the pilot process |
| `protocol-debug` | auto | Debug protocol graduation issues |
| `/gsd-toolkit-fda` | manual | Plan any ToolKit/FDA feature via GSD (requirements → roadmap → plan-phase) |
| `optoblueberry` | auto | OptoBlueBerry BLE optogenetics integration: Pi-native BlueHub replacement, stimulation param encoding, BLE debugging, MICS task wiring |
