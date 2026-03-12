# MICS Backend — Requirements

Current functional requirements and constraints. Update this when scope changes.

## Core Requirements

### Protocol Execution
- A protocol is an ordered list of steps; each step has a task type, params, and graduation criteria
- Graduation criteria are evaluated per-trial by the orchestrator (not the Pi)
- Steps advance automatically when graduation is met; researchers can also force-advance
- Run modes: `new` (fresh), `resume` (continue from stopped), `restart` (new attempt, same index)

### Overrides
- Researchers can override any protocol param for a single run without changing the template
- Override structure: `{ "global": { param: val }, "steps": { "0": { param: val } } }`
- Global overrides apply first; step-specific overrides win

### Pilot / Pi Communication
- Pi connects to orchestrator via ZMQ DEALER socket (identity = pilot name)
- On startup, Pi sends HANDSHAKE with task discovery payload (task_name, params, hardware, file_hash)
- Tasks send INC_TRIAL_COUNTER explicitly; orchestrator handles graduation logic
- All hardware/tracker actions auto-logged via `@log_action` decorator → ES

### Web UI
- React SPA is the primary interface (served at `/react/*`)
- Legacy Jinja2 views still exist; migration is ongoing
- Web UI never holds API tokens — server-side proxy pattern only

### Data
- All behavioral events stream to ElasticSearch via orchestrator's data/trial workers
- PostgreSQL holds config (subjects, protocols, sessions, runs)
- Redis holds live pilot state (surveilled every 1s by web UI WebSocket)

## Constraints

- No breaking changes to existing ZMQ message protocol (Pi code is deployed on physical hardware)
- Dual ORM must be maintained until a full migration is done (not currently planned)
- No test suite — changes must be verified manually
- Docker Compose is the only supported deployment method

## Out of Scope (currently)

- Multi-user auth (single-user system, JWT token is static)
- Cloud deployment
- Real-time collaboration
