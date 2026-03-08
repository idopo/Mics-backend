# MICS Backend

Behavioral research experiment management system for running tasks on Raspberry Pi pilot devices (subjects are lab animals). Researchers configure protocols and sessions via the web UI; the orchestrator dispatches tasks to pilots over ZMQ and streams data to ElasticSearch.

## Services

| Service | Port | Responsibility |
|---|---|---|
| `api/` | 8000 | PostgreSQL-backed REST API, JWT auth |
| `orchestrator/` | 9000 | ZMQ gateway to pilots, Redis state, ES ingestion |
| `web_ui/` | 8080 | Jinja2 UI, authenticated reverse proxy to api + orchestrator |
| `backup/` | — | supercronic: nightly pg_dump + ES snapshot to SMB share |

All services run as Docker containers. Start everything with:

```
docker compose up --build
```

There is no test suite at this time. Health check: `GET http://localhost:8000/health`.

## Key Directories

```
api/
  main.py          # all API routes (1631 lines)
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
  static/pilot_sessions.js  # main frontend module (1578 lines)
  static/session_overrides_modal.js  # step-level override modal (407 lines)
  templates/       # Jinja2 HTML templates

backup/
  backup.sh        # pg_dump + ES snapshot, SMB upload
  entrypoint.sh    # supercronic scheduler
```

## Environment Variables

Critical variables (see `docker-compose.yml`):

- `DATABASE_URL` — PostgreSQL DSN (api)
- `JWT_SECRET`, `JWT_ALGORITHM`, `JWT_AUDIENCE`, `JWT_ISSUER` — token validation (api)
- `MICS_API_TOKEN` — pre-issued JWT used by web_ui and orchestrator to call the api
- `REDIS_URL` — Redis DSN (orchestrator, web_ui)
- Orchestrator config: `orchestrator/orchestrator/prefs.json` (MICS_API_URL, MICS_API_TOKEN, NAME, MSGPORT)

## Additional Documentation

- `.claude/docs/architectural_patterns.md` — recurring patterns with file:line references and rationale
