---
phase: 02-db-api
plan: "02"
subsystem: api
tags: [fastapi, sqlalchemy, zmq, handshake, toolkit, orchestrator]

# Dependency graph
requires:
  - phase: 02-db-api/02-01
    provides: task_toolkits and toolkit_pilot_origins DB tables + SQLAlchemy models

provides:
  - POST /pilots/{pilot_id}/toolkits endpoint upserts TaskToolkit on (name, hw_hash)
  - toolkit_pilot_origins upserted with first_seen_at/last_seen_at tracking
  - orchestrator on_handshake() routes enriched HANDSHAKE to toolkit upsert
  - MicsApiClient.upsert_pilot_toolkit() HTTP method

affects:
  - 02-db-api/02-03
  - 02-db-api/02-04

# Tech tracking
tech-stack:
  added: [hashlib (stdlib — hw_hash computation)]
  patterns:
    - upsert by (name, hw_hash) composite key
    - enriched HANDSHAKE detection via SEMANTIC_HARDWARE/FLAGS key presence
    - legacy HANDSHAKE fallthrough unchanged

key-files:
  created: []
  modified:
    - api/main.py
    - orchestrator/orchestrator/orchestrator_station.py
    - orchestrator/orchestrator/mics/mics_api_client.py

key-decisions:
  - "hw_hash computed by orchestrator as SHA256(json.dumps(sem_hw, sort_keys=True)) — caller pre-computes, API trusts it"
  - "Enriched HANDSHAKE detected by key presence (SEMANTIC_HARDWARE or FLAGS), not schema version field"
  - "Missing task_name in enriched payload logs warning but does not crash HANDSHAKE processing"

patterns-established:
  - "Toolkit upsert: find by (name, hw_hash), create if missing, update mutable fields if found"
  - "Origin upsert: find by (toolkit_id, pilot_id), create with first_seen_at, update last_seen_at"

requirements-completed: [DB-01, HOT-02, VAR-01, VAR-02, VAR-03]

# Metrics
duration: 2min
completed: 2026-03-22
---

# Phase 02 Plan 02: HANDSHAKE Toolkit Upsert Summary

**POST /pilots/{id}/toolkits endpoint + orchestrator enriched HANDSHAKE routing that upserts TaskToolkit rows keyed on (name, hw_hash) with pilot origin tracking**

## Performance

- **Duration:** ~2 min
- **Started:** 2026-03-22T15:56:29Z
- **Completed:** 2026-03-22T15:58:17Z
- **Tasks:** 2
- **Files modified:** 3

## Accomplishments
- New `POST /pilots/{pilot_id}/toolkits` endpoint upserts TaskToolkit and ToolkitPilotOrigin in a single transaction
- Same (name, hw_hash) pair updates mutable fields only — no duplicate rows created
- Different hw_hash creates a new toolkit row, enabling tracking of hardware configuration changes
- `on_handshake()` detects enriched HANDSHAKE via SEMANTIC_HARDWARE/FLAGS key presence; legacy path untouched
- hw_hash computed as SHA256 of sorted-key JSON of SEMANTIC_HARDWARE dict

## Task Commits

Each task was committed atomically:

1. **Task 1: Add POST /pilots/{pilot_id}/toolkits endpoint** - `17fd253` (feat)
2. **Task 2: Extend MicsApiClient and on_handshake()** - `67ab10c` (feat)

## Files Created/Modified
- `api/main.py` - added `hashlib` import + `upsert_pilot_toolkit` endpoint (~84 lines)
- `orchestrator/orchestrator/orchestrator_station.py` - added `hashlib` import, extended `on_handshake()` with enriched HANDSHAKE branch
- `orchestrator/orchestrator/mics/mics_api_client.py` - added `upsert_pilot_toolkit()` method

## Decisions Made
- hw_hash is pre-computed by the orchestrator (caller) and sent to the API as an opaque string. The API trusts the hash rather than recomputing it, keeping the endpoint generic.
- Enriched HANDSHAKE is detected by key presence (`SEMANTIC_HARDWARE` or `FLAGS`) rather than a schema version field, ensuring backward compatibility without protocol changes.
- When `task_name` is absent from an enriched payload, the toolkit upsert is skipped with a warning log — this prevents silent data corruption without crashing HANDSHAKE processing.

## Deviations from Plan

None - plan executed exactly as written.

## Issues Encountered
None.

## User Setup Required
None - no external service configuration required.

## Next Phase Readiness
- `POST /pilots/{id}/toolkits` is live and ready to receive enriched HANDSHAKE data from Phase 1 Pi changes
- toolkit_id is returned in response, available for use in Phase 2-03 task_definitions FK linking
- Legacy task upsert path (`POST /pilots/{id}/tasks`) remains fully operational

---
*Phase: 02-db-api*
*Completed: 2026-03-22*
