---
phase: 02-db-api
verified: 2026-03-22T18:00:00Z
status: passed
score: 12/12 must-haves verified
re_verification: false
human_verification:
  - test: "Trigger enriched HANDSHAKE from a real Pi and query task_toolkits in Postgres"
    expected: "Row with states, flags, semantic_hardware, callable_methods, required_packages populated"
    why_human: "Requires live Pi with Phase 1 HANDSHAKE enrichment (Phase 1 Pi changes not yet deployed)"
  - test: "POST /api/task-definitions/{id}/push?pilot=T with a running pilot"
    expected: "Orchestrator logs show UPDATE_FDA sent; Pi logs show HOT_RELOAD_ACK within 2s"
    why_human: "Pi-side HOT_RELOAD_ACK handling not yet deployed (Phase 1 Pi task), and requires live connected pilot"
---

# Phase 2: DB + API Verification Report

**Phase Goal:** Extend the backend DB and API so toolkit metadata (from HANDSHAKE) is persisted, task definitions can store fda_json, and the push-to-pilot flow (UPDATE_FDA) is wired end-to-end.
**Verified:** 2026-03-22T18:00:00Z
**Status:** passed
**Re-verification:** No — initial verification

## Goal Achievement

### Observable Truths

| # | Truth | Status | Evidence |
|---|-------|--------|----------|
| 1 | task_toolkits and toolkit_pilot_origins tables created with UniqueConstraints | VERIFIED | `api/models.py` lines 584-616: both SQLAlchemy classes with `__table_args__` UniqueConstraints |
| 2 | task_definitions extended with toolkit_name, display_name, fda_json via IF NOT EXISTS migration | VERIFIED | `api/db.py` lines 60-72: `run_toolkit_migrations()` with three `ALTER TABLE ... ADD COLUMN IF NOT EXISTS` |
| 3 | API startup runs all migrations idempotently | VERIFIED | `api/main.py` line 124: `run_toolkit_migrations(engine)` called in `startup()` after existing migrations |
| 4 | POST /pilots/{pilot_id}/toolkits upserts toolkit on (name, hw_hash) | VERIFIED | `api/main.py` lines 1084-1165: endpoint queries by (name, hw_hash), creates if absent, updates mutable fields if found |
| 5 | toolkit_pilot_origins upserted per HANDSHAKE (first_seen_at preserved, last_seen_at updated) | VERIFIED | `api/main.py` lines 1143-1157: separate origin upsert in same transaction |
| 6 | Enriched HANDSHAKE in orchestrator routes to toolkit upsert; legacy HANDSHAKE unchanged | VERIFIED | `orchestrator/orchestrator/orchestrator_station.py` lines 94-131: detection via SEMANTIC_HARDWARE/FLAGS key presence; legacy `upsert_pilot_tasks` path runs unconditionally when tasks present |
| 7 | GET /api/toolkits returns list with pilot_origins and fda_count; GET by-name, GET by-id, GET diff endpoints all exist | VERIFIED | `api/routers/toolkits.py` lines 59-193: four `@router.get` endpoints; by-name registered before /{id} to avoid routing ambiguity; fda_count uses raw SQL for migrated column |
| 8 | Task-definition CRUD: POST, GET list, GET/:id, PUT, DELETE all exist | VERIFIED | `api/routers/toolkits.py` lines 195-340: five endpoints with raw SQL for migrated columns (display_name, toolkit_name, fda_json) |
| 9 | POST /api/task-definitions/{id}/push validates fda_json against toolkit, forwards to orchestrator | VERIFIED | `api/routers/toolkits.py` lines 345-402: validates state names and hardware entry_action refs; calls orchestrator via stdlib urllib to `/push-fda` |
| 10 | Orchestrator POST /push-fda calls push_hot_reload(); push_hot_reload() sends UPDATE_FDA via ZMQ | VERIFIED | `orchestrator/orchestrator/api.py` lines 94-109; `orchestrator/orchestrator/orchestrator_station.py` lines 703-718: `gateway.send(pilot_key, "UPDATE_FDA", fda_json)` |
| 11 | _build_step_task() and _build_first_step_task() inject state_machine from fda_json when task_definition_id present | VERIFIED | `orchestrator/orchestrator/orchestrator_station.py` lines 613-628 and 671-686: both functions read `step["params"]["task_definition_id"]`, call `api.get_task_definition()`, set `task["state_machine"]` |
| 12 | MicsApiClient has upsert_pilot_toolkit() and get_task_definition() | VERIFIED | `orchestrator/orchestrator/mics/mics_api_client.py` lines 207-224: both methods present |

**Score:** 12/12 truths verified

### Required Artifacts

| Artifact | Expected | Status | Details |
|----------|----------|--------|---------|
| `api/models.py` | TaskToolkit, ToolkitPilotOrigin, Pydantic schemas | VERIFIED | Lines 584-660: all four models present |
| `api/db.py` | run_toolkit_migrations() | VERIFIED | Line 60: function exists |
| `api/main.py` | startup wiring + POST /pilots/{id}/toolkits | VERIFIED | Lines 14, 65, 124 (imports + include_router + call); lines 1084-1165 (endpoint) |
| `api/routers/__init__.py` | package init | VERIFIED | File exists (empty init) |
| `api/routers/toolkits.py` | 9 endpoints + _validate_fda_against_toolkit | VERIFIED | 438 lines; all 10 route functions confirmed |
| `api/tests/test_toolkits_router.py` | TDD smoke tests | VERIFIED | 4 tests present |
| `orchestrator/orchestrator/orchestrator_station.py` | on_handshake() enriched path, _build_*_step_task() injection, push_hot_reload() | VERIFIED | All three additions present |
| `orchestrator/orchestrator/api.py` | POST /push-fda | VERIFIED | Lines 94-109 |
| `orchestrator/orchestrator/mics/mics_api_client.py` | upsert_pilot_toolkit(), get_task_definition() | VERIFIED | Lines 207-224 |
| `orchestrator/tests/test_push_fda.py` | push_hot_reload unit tests | VERIFIED | 2 tests present |

### Key Link Verification

| From | To | Via | Status | Details |
|------|----|-----|--------|---------|
| api/main.py startup | task_toolkits table | Base.metadata.create_all(engine) | WIRED | Line 110; TaskToolkit inherits from Base |
| api/main.py startup | task_definitions new columns | run_toolkit_migrations(engine) | WIRED | Line 124 |
| orchestrator on_handshake() | api POST /pilots/{id}/toolkits | self.api.upsert_pilot_toolkit() | WIRED | Line 122: called when SEMANTIC_HARDWARE or FLAGS present |
| api POST /pilots/{id}/toolkits | task_toolkits table | db.query(TaskToolkit).filter(name, hw_hash) | WIRED | Lines 1109-1113 |
| GET /toolkits | task_toolkits + origins + definitions tables | ORM query + raw SQL join | WIRED | Lines 63-84 |
| GET /toolkits/by-name/{name} | task_toolkits table | TaskToolkit.name == name | WIRED | Lines 90-123 |
| DELETE /task-definitions/{id} | task_definitions table | db.delete(defn) | WIRED | Lines 325-340 |
| POST /task-definitions/{id}/push | orchestrator POST /push-fda | urllib.request to ORCHESTRATOR_URL | WIRED | Lines 384-397 |
| orchestrator POST /push-fda | Pi via ZMQ | station.push_hot_reload() → gateway.send("UPDATE_FDA") | WIRED | api.py line 105; station line 717 |
| _build_step_task() | task_definitions.fda_json | self.api.get_task_definition(id) | WIRED | Lines 675-677: state_machine set from fda_json |

### Requirements Coverage

| Requirement | Source Plan | Description | Status | Evidence |
|-------------|------------|-------------|--------|----------|
| DB-01 | 02-01, 02-02 | task_toolkits table; HANDSHAKE handler writes toolkit metadata | SATISFIED | TaskToolkit model + on_handshake() enriched path |
| DB-02 | 02-01 | task_definitions extended with toolkit_name, fda_json, display_name; IF NOT EXISTS | SATISFIED | run_toolkit_migrations() with IF NOT EXISTS |
| DB-03 | 02-03 | GET /api/toolkits returns list with all metadata needed by GUI | SATISFIED | list_toolkits() with pilot_origins and fda_count |
| DB-04 | 02-03 | GET /api/toolkits/:name returns full toolkit detail | SATISFIED | get_toolkits_by_name() at /toolkits/by-name/{name} — note: path uses /by-name/ prefix, not /:name directly |
| DB-05 | 02-03 | POST /api/task-definitions creates task definition from toolkit + FDA JSON | SATISFIED | create_task_definition() at status_code=201 |
| DB-06 | 02-03 | GET/PUT/DELETE /api/task-definitions/:id CRUD with full fda_json | SATISFIED | Three endpoints confirmed in toolkits.py |
| DB-07 | 02-04 | POST /api/task-definitions/:id/push?pilot=name forwards UPDATE_FDA; returns HOT_RELOAD_ACK status | SATISFIED (partial) | Endpoint fires UPDATE_FDA; returns `{"status":"pushed"}` (fire-and-forget). HOT_RELOAD_ACK from Pi requires Phase 1 Pi changes — not a Phase 2 obligation. Architectural spec confirms `{"status":"pushed"}` is the correct Phase 2 return value |
| DB-08 | 02-04 | Orchestrator _build_step_task() includes state_machine from fda_json in START payload | SATISFIED | Both _build_first_step_task() and _build_step_task() inject state_machine |
| HOT-01 | 02-04 | _build_step_task() includes state_machine from task definition's fda_json in START payload | SATISFIED | Same as DB-08 — confirmed in orchestrator_station.py lines 613-628, 671-686 |
| VAR-01 | 02-01, 02-02 | Toolkit identity is (name, hw_hash); same hw_hash = same record | SATISFIED | UniqueConstraint on (name, hw_hash) + upsert logic |
| VAR-02 | 02-02 | Different hw_hash for same name creates new row | SATISFIED | POST /pilots/{id}/toolkits creates new row when hw_hash differs |
| VAR-03 | 02-02 | toolkit_pilot_origins tracks (toolkit_id, pilot_id, first_seen_at, last_seen_at) | SATISFIED | ToolkitPilotOrigin model + upsert logic in endpoint |
| VAR-04 | 02-03 | GET /api/toolkits returns toolkits with hw_hash, pilot_origins, fda_count | SATISFIED | list_toolkits() response shape confirmed |
| VAR-05 | 02-03 | GET /api/toolkits/{id}/diff/{other_id} returns added/removed/changed in SEMANTIC_HARDWARE | SATISFIED | diff_toolkits() returns {added, removed, changed, identical} |

**Note on orphaned requirements:** HOT-02 is referenced in plan 02-02 frontmatter as a completed requirement. HOT-02 describes the enriched HANDSHAKE payload shape from the Pi. This is actually a Phase 1 Pi Foundation requirement (Pi sends the enriched payload). Phase 2 is the consumer side. The orchestrator correctly handles the enriched payload — this is appropriate coverage for the consumer side of HOT-02.

### Anti-Patterns Found

None detected. Scan of all modified files shows:
- No TODO/FIXME/PLACEHOLDER/HACK comments in new code
- No empty handlers (`return {}`, `return []`, `return null`)
- No stub API responses
- No orphaned artifacts (all new files are imported/registered)

One design note (informational, not a blocker): `toolkits.py` is 438 lines — within the 500-line hard limit but approaching it. Phase 3 additions should go in a separate router file.

### Human Verification Required

#### 1. Live Pi HANDSHAKE round-trip

**Test:** Trigger a Pi reconnect with a Phase 1-enriched HANDSHAKE (FLAGS + SEMANTIC_HARDWARE + STAGE_NAMES in payload). Then `GET /api/toolkits`.
**Expected:** New row in task_toolkits table with states, flags, semantic_hardware, callable_methods, required_packages populated. toolkit_pilot_origins row created.
**Why human:** Requires live Pi with Phase 1 Python changes deployed; Phase 1 Pi Foundation plans not yet executed.

#### 2. UPDATE_FDA end-to-end push

**Test:** With a pilot connected and a task_definition row in DB, call `POST /api/task-definitions/{id}/push?pilot=T`.
**Expected:** Orchestrator logs: "UPDATE_FDA sent to pilot T". Pi logs: "HOT_RELOAD_ACK" within 2 seconds.
**Why human:** Requires live connected pilot and Phase 1 Pi-side hot-reload handler. HOT_RELOAD_ACK handler not registered in orchestrator gateway (expected — Pi sends it, orchestrator doesn't need to handle it for Phase 2).

#### 3. state_machine injection verification during session start

**Test:** Create a protocol step with `params.task_definition_id = {some_id}`. Start a session. Check orchestrator logs.
**Expected:** Log line: "Injected state_machine from task_definition {id} into START payload for run {run_id} step {step_idx}". Pi receives START with `state_machine` key.
**Why human:** Requires live session start; task_definition_id FK on protocol_step_templates not yet wired (Phase 4 work) — must set via direct DB or manual param injection to test.

### Gaps Summary

No automated gaps found. All 12 must-have truths are VERIFIED. All 14 phase requirements (DB-01 through DB-08, HOT-01, VAR-01 through VAR-05) have implementation evidence.

The three human verification items are integration tests requiring live infrastructure and Phase 1 Pi changes. They do not represent missing Phase 2 code — the wiring exists and is complete on the backend side.

**Implementation quality notes:**
- Router correctly separates from main.py (only 2-line include_router change to main.py)
- Raw SQL pattern used correctly for migrated columns (toolkit_name, display_name, fda_json) that are absent from the ORM class
- stdlib urllib used instead of requests (requests not in api/requirements.txt) — correct dependency management
- KeyError caught and re-raised as ValueError in push_hot_reload() — correct behavior per actual state.py implementation
- state_machine injection is non-fatal: exceptions caught, session start continues — correct for resilience

---

_Verified: 2026-03-22T18:00:00Z_
_Verifier: Claude (gsd-verifier)_
