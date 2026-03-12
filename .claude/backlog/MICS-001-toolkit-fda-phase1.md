---
id: MICS-001
title: ToolKit + FDA redesign — Phase 1 (load_fda_from_json + FLAGS in HANDSHAKE)
status: todo
priority: high
area: pi, orchestrator, api
created: 2026-03-12
---

## Goal

Decouple the FDA (Finite Deterministic Automaton) state machine from hardcoded task code on the Pi. Phase 1 adds the infrastructure: the Pi task can load an FDA from a JSON definition, and the HANDSHAKE payload includes a `FLAGS` field so the orchestrator knows which dynamic capabilities the task supports.

## Context

Full plan: `.claude/docs/toolkit_fda_plan.md`

**Pi side:**
- Task hierarchy: `Task → mics_task → learning_cage → ConcreteTask`
- Pi mirror: `~/pi-mirror/` (rsync from `pi@132.77.72.28:~/Apps/mice_interactive_home_cage/`)
- State machine lives in `FiniteDeterministicAutomaton` used as `self.stages` in every mics_task
- Each state is a method; transitions are `(from, to, [lambda_list])` — lambdas over `self.view`
- `self.view.get_value(name)` reads hardware/tracker state
- `mics_task.py` is the base to modify for `load_fda_from_json()`

**Orchestrator side:**
- HANDSHAKE handler: `orchestrator/orchestrator/orchestrator_station.py` `on_handshake()` (~line 69-95)
- HANDSHAKE forwarded to API via `mics_api_client.upsert_pilot_tasks()`
- Current HANDSHAKE payload per task: `{task_name, base_class, module, params, hardware, file_hash}`
- Need to add `flags: List[str]` to this payload

**API side:**
- `task_definitions` table (SQLAlchemy, not SQLModel) — `api/models.py`
- `upsert_pilot_tasks` endpoint in `api/main.py`
- Need to add `flags` column to `task_definitions` table

## Acceptance Criteria

- [ ] `mics_task` has a `load_fda_from_json(fda_dict)` method that replaces `self.stages` with an FDA built from JSON
- [ ] JSON FDA format documented with at least one working example
- [ ] Pi `handshake()` in `pilot.py` includes `flags` field per task (e.g., `["DYNAMIC_FDA"]`)
- [ ] Orchestrator `on_handshake` passes `flags` through to API without dropping them
- [ ] `task_definitions` table has `flags` column (JSON array), populated on upsert
- [ ] Existing tasks continue to work unchanged (no FDA JSON = use hardcoded FDA as before)

## Implementation Notes

- `load_fda_from_json` should be additive — if not called, task behaves identically to today
- Conditions in FDA JSON: `{"param": "name"}` as rhs means compare to current param value (not literal)
- The ToolKit concept (Python class with state/hardware/flags but NO hardcoded FDA) is Phase 2 — don't conflate
- Sync scripts to push updated Pi code: check `~/pi-mirror/` for existing rsync workflow

## Related Tasks

- MICS-002 (Phase 2: DB split + new API endpoints) depends on this
- MICS-003 (Phase 3: visual editor) depends on MICS-002
