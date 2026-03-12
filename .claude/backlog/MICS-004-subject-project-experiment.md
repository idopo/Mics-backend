---
id: MICS-004
title: Subject / Project / Experiment hierarchy implementation
status: in-progress
priority: medium
area: api, react
created: 2026-03-12
---

## Goal

Introduce a three-level hierarchy above sessions: Subject → Project → Experiment. This allows researchers to organize behavioral data into logical groupings beyond the flat subject list.

## Context

Full plan: `.claude/docs/subject_project_experiment_plan.md`

**Current data model (SQLModel tables in `api/models.py`):**
- `Subject` — name, species, metadata
- `ProtocolTemplate` + `ProtocolStepTemplate` — protocol definitions
- `SubjectProtocolRun` — links subject to protocol, tracks progress

**Current React routes:**
- `/react/subjects-ui` — flat list, create subject (Subjects.tsx)
- `/react/subjects/:subject/sessions-ui` — SubjectSessions.tsx

**API:**
- `GET /api/subjects` — returns flat list
- `GET/POST /api/subjects/{name}` — subject CRUD

**What needs to be added:**
- `projects` table: id, name, description, created_at
- `experiments` table: id, project_id, name, protocol_id, start_date, end_date
- `experiment_subjects` join table: experiment_id, subject_name
- New API endpoints: `/api/projects`, `/api/experiments`
- React: Projects page, Experiment page, breadcrumb navigation

## Acceptance Criteria

- [ ] Projects can be created, listed, and viewed
- [ ] Experiments belong to a project and reference a protocol
- [ ] Subjects can be assigned to experiments
- [ ] Sessions are filterable by experiment in the pilot-sessions view
- [ ] React routes for project/experiment pages
- [ ] Navigation updated in Nav.tsx

## Implementation Notes

- New tables should use SQLModel (not SQLAlchemy) — consistent with subject/protocol domain
- Don't break existing `/api/subjects` or session endpoints
- Dual ORM pattern (architectural_patterns.md #1): SQLModel for new tables, call `SQLModel.metadata.create_all()`
- Sessions can remain flat — experiment is a query/filter layer, not a required FK on sessions
