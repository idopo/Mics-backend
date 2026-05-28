---
phase: 17-free-form-pilot-hardware-config
plan: "01"
subsystem: api
tags: [db-migration, orm, api, pilot-hardware-config]
dependency_graph:
  requires: []
  provides: [name-keyed pilot hardware config CRUD API]
  affects: [api/routers/pilot_hardware_config.py, api/models.py, api/db.py]
tech_stack:
  added: []
  patterns: [idempotent DB migration, name-keyed upsert, SA sessionmaker]
key_files:
  created: []
  modified:
    - api/db.py
    - api/models.py
    - api/main.py
    - api/routers/pilot_hardware_config.py
decisions:
  - "PilotHardwareConfig row identity switched from (pilot_id, hardware_module_id) to (pilot_id, name) — hardware_module_id retained as nullable FK for backward compat but no longer used as identity"
  - "Config stored as-is from caller (caller includes class_name) — no DB lookup for class_name injection at PUT time"
  - "Seed maps Pi 'class' key -> config['class_name'] directly without module registry lookup"
metrics:
  duration_minutes: 2
  completed_date: "2026-05-28"
  tasks_completed: 3
  tasks_total: 3
  files_modified: 4
---

# Phase 17 Plan 01: Free-Form Pilot Hardware Config Summary

**One-liner:** Name-keyed pilot hardware config CRUD replacing module-ID-based identity with free-form named rows mirroring Pi prefs.json HARDWARE dict.

## Tasks Completed

| Task | Name | Commit | Files |
|------|------|--------|-------|
| 1 | DB migration — add name col, swap constraint, nullable FK | 0201210 | api/db.py |
| 2 | Update PilotHardwareConfig ORM model and wire migration into startup | 06b0cbc | api/models.py, api/main.py |
| 3 | Rewrite pilot_hardware_config router — name-keyed PUT/DELETE, updated seed and list | e50863d | api/routers/pilot_hardware_config.py |

## What Was Built

Decoupled `pilot_hardware_config` from the `hardware_modules` FK by switching row identity from `(pilot_id, hardware_module_id)` to `(pilot_id, name)`. The name mirrors the key in Pi's `prefs.json` HARDWARE dict, making entries free-form with no persistent link to the module registry.

**DB migration** (`run_pilot_hw_config_name_migration`):
- Adds `name VARCHAR` column (nullable for backfill safety)
- Backfills `name` from `hardware_modules.name` for existing rows using their `hardware_module_id`
- Drops the old `pilot_id+hardware_module_id` unique constraint
- Makes `hardware_module_id` nullable
- Adds new `uq_pilot_hw_config_pilot_name` constraint on `(pilot_id, name)`
- All steps idempotent via `IF NOT EXISTS` / `DO $$...$$` blocks

**ORM model** (`PilotHardwareConfig`):
- `hardware_module_id` made `nullable=True`
- `name = Column(String, nullable=True)` added
- `__table_args__` updated to `UniqueConstraint("pilot_id", "name", name="uq_pilot_hw_config_pilot_name")`

**Router rewrite** — full rewrite, 89 lines (under 150-line limit):
- `GET /api/pilots/{id}/hardware-config` — returns `[{id, pilot_id, name, config}]`
- `PUT /api/pilots/{id}/hardware-config/{name}` — upsert by name; config stored as-is
- `DELETE /api/pilots/{id}/hardware-config/{name}` — delete by name
- `POST /api/pilots/{id}/hardware-config/seed` — maps Pi `class` → `config["class_name"]`; skips existing pilots

## Verification Results

```
# Migration idempotency
migration OK (run 2)

# Column/constraint state
name column: YES
uq_pilot_hw_config_pilot_name constraint: YES
hardware_module_id nullable: YES

# Endpoint responses
PUT Left_LED  → {"id":2,"pilot_id":1,"name":"Left_LED","config":{"class_name":"Digital_Out","pin":7}}
GET list      → [{name: "Solenoid", ...}, {name: "Right_LED", ...}, {name: "Left_LED", ...}]
DELETE        → {"deleted":true}
health        → {"status":"ok"}
```

## Deviations from Plan

None — plan executed exactly as written.

## Self-Check: PASSED

- api/db.py modified and contains `run_pilot_hw_config_name_migration` — FOUND
- api/models.py modified and contains `uq_pilot_hw_config_pilot_name` — FOUND
- api/routers/pilot_hardware_config.py rewritten to name-keyed API — FOUND
- api/main.py wired migration at startup — FOUND
- Commits 0201210, 06b0cbc, e50863d exist — VERIFIED
