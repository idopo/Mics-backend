# Phase 30 Plan 04 — Removal Ledger

**Scope:** HYG-04 (empty HANDSHAKE proven benign against the live API) and HYG-03 (`pilot/plugins/`
plus its three orphan modules removed as one change).

**Standing constraints honoured throughout:** no git command run in `/home/ido/pi-mirror`; no
`rsync`; nothing deployed to the Pi; no Python run on the Pi; no protect-listed file touched;
`--rebaseline` not run; every load-bearing absence claim measured with an unfiltered Python reader,
never with `grep` alone.

---

## §A — HYG-04: an empty HANDSHAKE is a backend no-op

### A.1 What the code actually does (read before constructing the request)

Route resolution was read from source, not assumed:

| Layer | File:line | Behaviour with `tasks: []` |
|---|---|---|
| Orchestrator handler | `orchestrator/orchestrator/orchestrator_station.py:93` | `if tasks:` — an empty list is falsy, so `upsert_pilot_tasks` is **never called**. Same guard at `:102` skips the toolkit upsert loop. |
| Orchestrator API client | `orchestrator/orchestrator/mics/mics_api_client.py:205-212` | `POST /pilots/{pilot_id}/tasks` with body `{"tasks": [...]}`. |
| API endpoint | `api/main.py:1018-1123` | Three phases, each `for task in payload.tasks:` — zero iterations. `db.commit()` at `:1117` on a clean session. Returns `tasks_received: len(payload.tasks)`. |
| Strict base-class resolve | `api/main.py:1059-1070` | The `HTTPException(400, "Base class '…' not found")` this plan's ordering constraint exists for. Unreachable with an empty list — there is no task to resolve a base class for. |

So the empty handshake is benign **twice over**: the orchestrator does not even issue the request,
and the endpoint returns 200 with no writes if it does. HYG-04 asks for the second — the endpoint
itself — because the guard at `:93` is not the contract, it is an implementation detail that a
future refactor could drop.

### A.2 The request

Target pilot: **id 1, `pilot_raspberry_lior`** — deliberately the *production* pilot (the one the
orchestrator already knows and the one the swept Pi will hand shake as), not the quieter
`youri_pilot` (id 2). Pilot 1 is the only pilot with `toolkit_pilot_origins` (97) and
`pilot_hardware_config` (7) rows, so it is the only target on which the "backend never prunes"
assertion has anything to observe.

```
POST http://localhost:8000/pilots/1/tasks
Authorization: Bearer <MICS_API_TOKEN>
Content-Type: application/json

{"tasks": []}
```

### A.3 The response

```
HTTP 200
{"status":"ok","pilot_id":1,"tasks_received":0}
```

`tasks_received: 0`. Not 400, not 500.

### A.4 Before / after row counts — identical

Queried with the same statements before and after the POST
(`docker compose exec -T db psql -U mics_user -d mics_db -tAc …`):

| Table | Before | After | Δ |
|---|---|---|---|
| `task_definitions` | 157 | 157 | 0 |
| `task_toolkits` | 113 | 113 | 0 |
| `available_locked_states` | 37 | 37 | 0 |
| `hardware_libs` | 7 | 7 | 0 |
| `hardware_modules` | 9 | 9 | 0 |
| `pilot_task_capabilities` | 165 | 165 | 0 |
| `task_inheritance` | 168 | 168 | 0 |
| `toolkit_pilot_origins` | 97 | 97 | 0 |

Per-pilot, for the targeted pilot 1:

| Per-pilot rows | Before | After | Δ |
|---|---|---|---|
| `toolkit_pilot_origins` pilot 1 | 97 | 97 | 0 |
| `pilot_hardware_config` pilot 1 | 7 | 7 | 0 |
| `pilot_task_capabilities` pilot 1 | 116 | 116 | 0 |
| `pilot_task_capabilities` pilot 2 | 49 | 49 | 0 |

**A stronger check than counts alone:** `max(last_seen_at)` for pilot 1's capability rows reads
`2026-08-09 14:46:41.268186` **after** the POST — i.e. still the previous day's real handshake. The
endpoint's only in-place mutation (`cap.last_seen_at = now`, `api/main.py:1107`) did not fire on a
single row. A count-only comparison could not have distinguished "no rows written" from "rows
rewritten in place"; this does.

**The 97 toolkit rows for pilot 1 are still present.** That is the accepted staleness HYG-04 names:
the backend has **no delete path on the handshake**, so a Pi that stops reporting a toolkit leaves
its row in the UI with no signal. Confirmed, not fixed — explicitly out of scope per 30-CONTEXT.md.

### A.5 Suites

`docker compose exec -T api python -m pytest -q tests/` → **435 passed, 1 skipped** in 1.54 s.
(Note for the phase record: `CLAUDE.md` still quotes 352 as the backend suite size; the suite has
grown since. Green is green — no failures, no errors.)

### A.6 Verdict

```
HYG-04 | PROVEN | POST /pilots/1/tasks {"tasks": []} -> HTTP 200 {"status":"ok","pilot_id":1,"tasks_received":0};
                  8 global + 4 per-pilot row counts identical before/after; pilot 1 max(last_seen_at)
                  unchanged at 2026-08-09 14:46:41.268186 proving no in-place row update; pilot 1's
                  97 toolkit_pilot_origins rows persist (backend never prunes — confirmed, not fixed);
                  backend suite 435 passed / 1 skipped.
```

**Gate result: PASS.** Task 2's premise holds; the sweep may proceed.

---
