---
phase: 18-extlink-pi-transport
plan: 09
subsystem: backend
tags: [device-lease, orchestrator, fastapi, react, preflight, extlink]

# Dependency graph
requires:
  - phase: 18-08
    provides: "api/device_lease.py's full CRUD/reconcile contract (acquire_lease, release_leases_for_run, force_release, get_lease, reconcile_leases, normalize_host) + the device_held_issue shape returned by preflight step 11"
provides:
  - "api/routers/device_leases.py — GET list, POST acquire, DELETE force-release, POST release-for-run/{run_id}, POST reconcile"
  - "orchestrator acquires a lease per PREFS_HARDWARE role-bearing host on start_run, releases on stop_run/on_task_error, and self-heals via a 15s _lease_reconcile_loop keyed on the live _redis_touch updated_at heartbeat"
  - "HardwareCheckModal.tsx renders device_held (with a read-only holder detail component) and extlink_config_invalid, both excluded from the destructive-PUT path"
affects: [18-12, 26]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Lease acquire/release wrapped in try/except + logger.warning in the orchestrator so a lease failure never blocks or masks the real start/stop/error path — preflight is the gate, the lease is a best-effort arbitration layer on top of it"
    - "_lease_reconcile_loop mirrors _ping_loop's daemon-thread + try/except + logger.exception shape exactly, so a Redis or API hiccup can never kill the thread"
    - "Frontend NON_CONFIG_ISSUES set is the single gate handleStart and the pendingEdits initialiser both check — any preflight issue kind that names no config row goes there, never a scattered per-callsite skip"

key-files:
  created:
    - api/routers/device_leases.py
  modified:
    - api/main.py
    - api/device_lease.py
    - api/tests/test_view_key_preflight.py
    - orchestrator/orchestrator/orchestrator_station.py
    - orchestrator/orchestrator/mics/mics_api_client.py
    - web_ui/react-src/src/components/HardwareCheckModal.tsx

key-decisions:
  - "Acquire is keyed off the presence of a `role` key in each PREFS_HARDWARE entry, never a port field — this deliberately includes role:'none' control-only modules (EXTLINK-18), which open no inbound socket but still command one physical box, exactly what the lease arbitrates"
  - "_run_watchdog stays dead code (thread-start left commented out) — its active_run['started_at']/elapsed>30 rule would kill every normal multi-minute session; the new loop keys on _redis_touch's continuously-refreshed updated_at instead, a genuine liveness signal"
  - "device_held and extlink_config_invalid are both added to NON_CONFIG_ISSUES rather than given bespoke handleStart logic — device_held names a lease (not a config row) and extlink_config_invalid requires an edit on the hardware-config page, not this modal; including either in a PUT would overwrite a good config with {} (Phase 25 precedent)"

requirements-completed: [EXTLINK-16, EXTLINK-17]

# Metrics
duration: ~20min (resumed after ENOSPC interrupt; original agent's work covered Tasks 1-2 and the code for Task 3, this session verified/committed/closed out)
completed: 2026-08-09
---

# Phase 18 Plan 09: Device-lease HTTP routes + orchestrator wiring + frontend mirror Summary

**`api/routers/device_leases.py` (94 lines) exposes list/acquire/force-release/release-for-run/reconcile over `api/device_lease.py`; the orchestrator now acquires a lease on every `role`-bearing host at `start_run`, releases on clean stop/error, and self-heals via a 15s `_lease_reconcile_loop` keyed on the live Redis heartbeat; `HardwareCheckModal.tsx` renders `device_held` with a holder-naming detail component and excludes both new issue kinds from the destructive-PUT path.**

## Performance

- **Duration:** ~20 min this session (resume from an ENOSPC-interrupted prior session)
- **Completed:** 2026-08-09T08:12:57Z
- **Tasks:** 3
- **Files modified:** 6 (1 created, 5 modified)

## Resume Context

A prior agent executing this plan was interrupted mid-Task-3 by a host disk-full (ENOSPC)
condition. This session verified the interrupted agent's on-disk state before continuing:

- **Tasks 1 and 2 were already fully committed** (`fa50c2d`, `806ee6c`, `6bb9f9e`) with all five
  files (`api/routers/device_leases.py`, `api/main.py`, `api/device_lease.py`,
  `api/tests/test_view_key_preflight.py`, `orchestrator/orchestrator/orchestrator_station.py`,
  `orchestrator/orchestrator/mics/mics_api_client.py`) parsing cleanly under `ast.parse` — no
  ENOSPC truncation found. Re-ran their `<verify>` blocks fresh in this session; both still pass.
- **Task 3's code was complete but uncommitted** in the working tree
  (`web_ui/react-src/src/components/HardwareCheckModal.tsx`). Read the full diff and the file
  tail — syntactically complete, `tsc --noEmit` and `npm run build` both clean, no truncation.
  Staged and committed it (`834c270`) to close out the plan.

No task work was redone; this session's job was verification + the one missing commit + final
suite/live checks.

## Accomplishments

- **Task 1** — `api/routers/device_leases.py`: thin `Depends(get_sa_session)` +
  `Depends(verify_token)` composition over `api/device_lease.py`, matching
  `toolkit_dispatch.py`'s testable shape. Host path params normalized server-side via
  `normalize_host` before lookup. `api/main.py` diff is exactly 2 lines (import + include_router).
  Both remaining `xfail` markers removed from `test_view_key_preflight.py`; `-k lease` is 26/26
  green with zero xfail/skip (up from 18-08's 19; 7 new HTTP-route tests added).
- **Task 2** — `MicsApiClient` gained `acquire_device_lease`, `release_device_leases_for_run`,
  `reconcile_device_leases`, `list_device_leases`. `orchestrator_station.py`: lease acquired in
  `start_run` after `mark_run_running` succeeds (keyed off any `PREFS_HARDWARE` entry carrying a
  `role`, including `role: "none"`), released in `stop_run` and `on_task_error`, both wrapped in
  `try/except` so a lease failure never masks the real stop/error/start path. New
  `_lease_reconcile_loop` daemon thread (15s interval) reads every `pilot:*` Redis hash's
  `updated_at` and POSTs the map via `reconcile_device_leases`; returns early with a log line if
  Redis is unconfigured. `_run_watchdog`'s thread-start remains commented out, with a comment
  explaining why re-enabling it would be wrong.
- **Task 3** — `PreflightIssue` union gains `'device_held'` / `'extlink_config_invalid'` plus a
  `DeviceLeaseHolder` interface matching 18-08's pinned `device_held_issue` shape. New
  `DeviceHeldIssueDetail` component (modelled on `ViewKeyIssueDetail`) leads with the host, then a
  plain sentence naming the holding pilot/subject/run and elapsed hold time via a new
  `formatHeldSince` helper. Both new kinds added to `NON_CONFIG_ISSUES`, read by both
  `handleStart` and the `pendingEdits` initialiser, so neither can fire a destructive PUT. No
  start gate added — preflight stays advisory in the modal; the lease's hard block is server-side.

## Task Commits

Each task was committed atomically:

1. **Task 1: Lease endpoints + reconciliation route** — `fa50c2d` (test, RED) + `806ee6c` (feat, GREEN)
2. **Task 2: Orchestrator acquire/release/reconcile** — `6bb9f9e` (feat)
3. **Task 3: Mirror device_held/extlink_config_invalid in HardwareCheckModal** — `834c270` (feat, committed this session)

## Files Created/Modified

- `api/routers/device_leases.py` — new, 94 lines. `GET /api/device-leases`,
  `POST /api/device-leases/acquire`, `DELETE /api/device-leases/{host}`,
  `POST /api/device-leases/release-for-run/{run_id}`, `POST /api/device-leases/reconcile`.
- `api/main.py` — 2-line diff: import + `include_router` for `device_leases_router`.
- `api/device_lease.py` — added `list_leases()` helper for the GET route.
- `api/tests/test_view_key_preflight.py` — 7 new HTTP-route tests (list, acquire, force-release
  incl. `host:port` normalization, release-for-run, reconcile, auth); both remaining `xfail`
  markers removed. Also fixed a pre-existing `_LeaseFakeDb` bug where INSERT always overwrote
  instead of honoring `ON CONFLICT (host) DO NOTHING` semantics.
- `orchestrator/orchestrator/mics/mics_api_client.py` — 4 new methods wrapping the new HTTP routes.
- `orchestrator/orchestrator/orchestrator_station.py` — lease acquire/release wiring in
  `start_run`/`stop_run`/`on_task_error`; new `_lease_reconcile_loop` daemon thread.
- `web_ui/react-src/src/components/HardwareCheckModal.tsx` — `DeviceLeaseHolder` interface,
  `PreflightIssue` union extension, `DeviceHeldIssueDetail` + `formatHeldSince`,
  `NON_CONFIG_ISSUES` extension, `ModuleIssueEditor` branches for both new kinds.

## Decisions Made

- Lease acquire keys off the presence of a `role` key (never a port field) so `role: "none"`
  control-only modules are covered (EXTLINK-18) without a special-case branch.
- `_run_watchdog` is left untouched and dead — removing it was explicitly out of scope; the plan's
  own text documents why re-enabling it would break every normal session.
- `device_held`/`extlink_config_invalid` route through the existing `NON_CONFIG_ISSUES` gate rather
  than new bespoke skip logic, keeping the destructive-PUT guard in one place (Phase 25 precedent).

## Deviations from Plan

None — plan executed exactly as written by the original (interrupted) agent, and this session's
role was limited to verification, the one outstanding commit, and closing out the SUMMARY/state
updates. No Rule 1-4 fixes were needed; nothing on disk was truncated or incorrect.

## Issues Encountered

**Transient orchestrator 500s during the concurrent 18-13 window (not this plan's bug).** The
orchestrator log showed `_lease_reconcile_loop` succeeding at container boot (07:58:28, "first
cycle complete, nothing to release") then failing with `500 Internal Server Error` on
`/api/device-leases/reconcile` from 08:03:14–08:03:59 — exactly the window the concurrently-running
plan 18-13 agent was editing `api/routers/toolkit_dispatch.py`/`api/fda_validation.py` in the same
shared checkout. Reproduced the exact loop body manually against the live `api` container after
that window closed: `reconcile_device_leases` with the real Redis heartbeat map returns
`{"released": []}` / 200 every time. No further errors logged since 08:03:59. Not fixed because
there was nothing to fix — the code is correct; the 500s were the `api` process being transiently
disrupted by a different plan's edits to files this plan doesn't own.

## Verification Evidence

**Full backend suite:** `435 passed, 1 skipped, 8 warnings in 1.53s` — zero failures (the 3
failures flagged in this plan's `<critical_rules>` as 18-13's known in-progress RED state have
since turned green; not this plan's concern either way).

**`-k lease`:** `26 passed, 74 deselected, 8 warnings in 0.55s` — zero xfail/skip.

**`_run_watchdog` still dead:**
```
62:        # threading.Thread(target=self._run_watchdog, daemon=True).start()
```

**`api/main.py` diff across both 18-09 commits:** `1 file changed, 2 insertions(+)`.

**Frontend:** `npx tsc --noEmit` clean, `npm run build` clean (emits
`dist/HardwareCheckModal-*.js`), `npm run test:unit` 182/182. `grep -c "device_held"
HardwareCheckModal.tsx` = 9 (>= 2 required). `git diff --stat` for this plan touches no
`App.tsx`/`Layout.tsx`.

**Reconcile interval / staleness:** `_LEASE_RECONCILE_INTERVAL_S = 15` (orchestrator posts every
15s); `stale_after_s` defaults to the server's 90s (`api/device_lease.py::reconcile_leases`,
un-overridden by the orchestrator's own POST, which omits the field).

**Live lease round-trip** (real dev DB, via curl with the orchestrator's own `MICS_API_TOKEN`):
```
GET  /api/device-leases                    -> []
POST /api/device-leases/acquire (fake host) -> {"acquired":true,"holder":{"host":"192.0.2.99", ...}}
GET  /api/device-leases                    -> [{"host":"192.0.2.99", ...}]
DELETE /api/device-leases/192.0.2.99        -> {"released":true}
GET  /api/device-leases                    -> []
```

## User Setup Required

None — no external service configuration required.

## Next Phase Readiness

- Behavioural verification of the rendered `device_held` detail (visual confirmation in the modal)
  is deliberately deferred to plan 18-12's consolidated rig checkpoint, per this plan's own
  `<verification>` block.
- `gsd-tools requirements mark-complete EXTLINK-16 EXTLINK-17` — same known
  checkbox/traceability gap as every prior EXTLINK plan (`REQUIREMENTS.md` has no per-plan
  checkbox rows); completion tracked via this SUMMARY and `roadmap update-plan-progress 18`.

---
*Phase: 18-extlink-pi-transport*
*Completed: 2026-08-09*

## Self-Check: PASSED

- FOUND: api/routers/device_leases.py
- FOUND: api/main.py
- FOUND: api/device_lease.py
- FOUND: api/tests/test_view_key_preflight.py
- FOUND: orchestrator/orchestrator/orchestrator_station.py
- FOUND: orchestrator/orchestrator/mics/mics_api_client.py
- FOUND: web_ui/react-src/src/components/HardwareCheckModal.tsx
- FOUND: fa50c2d (task 1 RED commit)
- FOUND: 806ee6c (task 1 GREEN commit)
- FOUND: 6bb9f9e (task 2 commit)
- FOUND: 834c270 (task 3 commit)
