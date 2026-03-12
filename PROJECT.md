# MICS Backend — Project Overview

Behavioral research experiment management system for running tasks on Raspberry Pi pilot devices (lab animal subjects). Researchers configure protocols and sessions via the web UI; the orchestrator dispatches tasks to pilots over ZMQ and streams data to ElasticSearch.

## What it does

- Researchers define **protocols** (ordered steps, each referencing a task type with params)
- Subjects (animals) are assigned protocols, creating **sessions**
- Sessions are started on a **pilot** (Raspberry Pi) via the web UI
- The **orchestrator** sends task definitions + params to the Pi over ZMQ
- The Pi runs the behavioral task and streams event data back
- Data lands in **ElasticSearch**; graduation logic is checked per trial

## Stack

| Layer | Tech |
|---|---|
| API | FastAPI + PostgreSQL (SQLModel + SQLAlchemy dual ORM) |
| Orchestrator | Python + ZMQ + Redis |
| Web UI | FastAPI proxy + React/TypeScript SPA (Vite) |
| Pi tasks | Python, pigpio, ZMQ DEALER socket |
| Storage | PostgreSQL + ElasticSearch + Redis |
| Infra | Docker Compose |

## Active Work Areas

See `ROADMAP.md` for priorities and `.claude/backlog/BACKLOG.md` for task details.

1. **ToolKit + FDA redesign** — decouple Pi state machine from hardcoded task code
2. **Subject/Project/Experiment hierarchy** — organize data beyond flat subject list
3. **React SPA** — primary UI, replacing legacy Jinja2 frontend

## Key People / Context

- Pi mirror at `~/pi-mirror/` (rsync from `pi@132.77.72.28`)
- No test suite — manual testing via the UI and `GET /health`
- Dual ORM is intentional (SQLModel for newer tables, SQLAlchemy for older ones)
