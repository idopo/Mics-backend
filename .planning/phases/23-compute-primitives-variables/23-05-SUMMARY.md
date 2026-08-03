---
phase: 23-compute-primitives-variables
plan: 05
subsystem: api, orchestrator
tags: [hardware-libs, version-resolution, dispatch, orchestrator, compute-lib]
requires:
  - 23-02-SUMMARY.md (kind column, stable/active version substrate)
provides:
  - api/lib_version_resolution.py::resolve_lib_version_id / resolve_lib_versions
  - "GET /toolkits/{id}/hardware-libs?task_def_id=N resolved_* fields"
affects:
  - api/routers/toolkit_dispatch.py::get_dispatch_spec
  - api/hw_introspect.py::toolkit_hw_capabilities
  - orchestrator/orchestrator/orchestrator_station.py::_send_hardware_libs_if_needed
tech-stack:
  added: []
  patterns:
    - "single resolver, three consumers (dispatch / introspection / orchestrator route), no
      site re-derives its own pin -> version chain"
key-files:
  created:
    - api/lib_version_resolution.py
  modified:
    - api/routers/toolkit_dispatch.py
    - api/hw_introspect.py
    - api/routers/hardware_libs.py
    - orchestrator/orchestrator/orchestrator_station.py
    - orchestrator/orchestrator/mics/mics_api_client.py
    - api/tests/test_toolkit_dispatch.py
    - api/tests/test_view_key_preflight.py
decisions:
  - "Added a FOURTH resolution rung (active version, gated on state in {beta, stable}) not
    named by CONTEXT's literal pin -> toolkit_default -> stable -> nothing-deployable chain --
    required to avoid breaking every existing backend-authored toolkit on the rig, none of
    which have a promoted stable version yet (see Deviations)."
  - "One LOAD_HARDWARE_LIBS message per lib (not batched) so test_import's
    HARDWARE_LIB_TEST_RESULT can carry the Pi's existing TOP-LEVEL version_id with zero
    Pi-side change."
  - "get_hw_lib_version() (mics_api_client.py) deleted outright -- its one caller was the
    orchestrator branch this plan replaced, and grep confirmed no other caller."
metrics:
  duration: "~90 minutes"
  completed: 2026-08-03
  tasks: 3
  files_modified: 7
---

# Phase 23 Plan 05: Single Lib-Version Resolution Chain Summary

Unified three independently-wrong hardware-lib version chains (dispatch, orchestrator, AST
introspection) onto one resolver (`api/lib_version_resolution.py`), and activated the
`HARDWARE_LIB_TEST_RESULT` round-trip that has existed on the Pi, unused, since Phase 09.

## What Changed

**`api/lib_version_resolution.py` (new, 89 lines).** `resolve_lib_version_id(db, lib_id,
toolkit_id=None, pinned_version_id=None) -> (id, reason)` implements pin -> toolkit_default ->
stable -> active (only if that version's own `state` is `beta`/`stable`) -> none, returning
`(None, "none")` rather than raising or silently skipping. `resolve_lib_versions` batches it
per lib_id. Both take a caller-owned `db` and issue their own `sqlalchemy.text()` queries — same
no-connection posture as `api/hw_introspect.py`.

**`api/routers/toolkit_dispatch.py::get_dispatch_spec`.** The inline pin -> `active_version_id`
chain (lines 62-81) is replaced by a call to `resolve_lib_version_id`. The task-def pin lookup
moved outside the per-module loop (previously re-queried once per module — a free fix while
touching this code). A module that resolves to nothing is no longer a silent `continue`: it is
recorded in a new `unresolved_libs: [{module_name, lib_id, reason}]` response key, still omitted
from `hardware` (nothing to send) but now surfaced. Net growth: 8 lines (within the 20-line
budget).

**`api/hw_introspect.py::toolkit_hw_capabilities`.** Replaced the
`LEFT JOIN ... ON hlv.id = hl.active_version_id` with a two-step: select module rows + their
`hardware_lib_id`s, resolve every distinct lib id via `resolve_lib_versions` (no `toolkit_id`
argument here — this function's callers pass module ids, not a toolkit id, so the
`toolkit_default` rung never fires for introspection; stable/active still do), then batch-fetch
just the resolved `source_code`s. Both existing guarantees preserved exactly: `module_names` is
still present on the early-return path (98/112 module-less `task_toolkits` rows), and an
unresolvable module is still skipped silently, never a 500. File: 208 lines (was 194), well
under 300.

**`api/routers/hardware_libs.py::list_toolkit_hardware_libs`.** Gains an optional
`?task_def_id=` query param. Each lib entry now carries `resolved_version_id`, `resolved_state`,
`resolved_source_code`, `resolution_reason` — computed the same way as the dispatch route, using
the task def's `hw_lib_versions` pin (raw `sa_text` read, same pattern as every other
`hw_lib_versions` consumer in this codebase) when `task_def_id` is supplied. Existing keys
(`id`, `filename`, `source_code`, `active_state`, `default_version_id`, `kind`) are unchanged.

**`orchestrator/orchestrator/orchestrator_station.py::_send_hardware_libs_if_needed`.** No
longer re-derives the chain: it calls `get_toolkit_hardware_libs(toolkit_id, task_def_id=...)`
and reads each lib's `resolved_version_id`/`resolved_source_code`/`resolution_reason` directly.
A lib with `reason == "none"` (or no `resolved_version_id`) is logged at WARNING naming the
filename and reason — no silent drop. Sends **one `LOAD_HARDWARE_LIBS` message per lib**, each
carrying `test_import: True` and the top-level `version_id` the Pi's `l_load_hardware_libs`
already reads (see Deviations for why one-per-lib was the only option). `start_run()`'s call
site now threads `task_def_id` through (it already had it in scope for
`_inject_backend_toolkit_spec`).

**`orchestrator/orchestrator/mics/mics_api_client.py`.** `get_toolkit_hardware_libs` gained an
optional `task_def_id` param appended as a query string. `get_hw_lib_version` — the per-version
fetch the old orchestrator chain used — deleted outright; grep confirmed its only caller was the
branch this plan replaced.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 - blocking] `test_view_key_preflight.py`'s two `toolkit_hw_capabilities` tests used
the OLD single-join query shape.**
- **Found during:** Task 1 verification (`test_view_key_preflight.py` is not in this plan's
  `files_modified` but is named in `<verify>` as must-still-pass).
- **Issue:** Both tests' fake `db.execute()` stubs returned canned rows shaped `(id, name,
  class_name, source_code)` from a single `fetchall()` regardless of query text. The new
  two-step implementation issues a module-row query (needs `hardware_lib_id`, not
  `source_code`), then the resolver's own `fetchone()`-based queries, then a batch
  `fetchall()` for sources — none of which the old stub could answer.
- **Fix:** Replaced both tests' inline fake-db classes with a shared `_FakeIntrospectDb` that
  dispatches on SQL-text prefix (module rows / resolver's toolkit_default / resolver's
  stable+active / resolver's active-state / final source batch), matching the
  `FakeDispatchDb` pattern already used in `test_toolkit_dispatch.py`.
- **Files modified:** `api/tests/test_view_key_preflight.py`
- **Commit:** `9edca37`

**2. [Rule 3 - blocking] Plan 23-01's pre-written `test_toolkit_hardware_libs_carries_resolution_fields_per_lib`
fixture predated Plan 23-02's `kind`/`declared_imports` fields on `_lib_dict`.**
- **Found during:** Task 2 verification — the route 500'd with `AttributeError:
  'types.SimpleNamespace' object has no attribute 'kind'`, then (after adding `kind`)
  `... 'declared_imports'`.
- **Issue:** The test's `lib`/`active_version` `SimpleNamespace` fixtures were written in Wave 0
  (before Plan 23-02 added `kind` to `HardwareLib` and `declared_imports` to
  `HardwareLibVersion`, both now read unconditionally by `_lib_dict`).
- **Fix:** Added `kind="compute"` to the `lib` fixture and `declared_imports=None` to the
  `active_version` fixture. No production code change.
- **Files modified:** `api/tests/test_toolkit_dispatch.py`
- **Commit:** `5df12d6`

### Design Deviation (per plan's explicit instruction — not a Rule 1-3 auto-fix)

**The fourth resolution rung.** CONTEXT's literal chain was pin -> toolkit_default -> stable ->
*nothing deployable*. Implemented literally, any lib with no promoted `stable_version_id` would
stop dispatching entirely — which is every existing backend-authored toolkit on the rig today
(MPR121, TOUCH_INT, and every task def using them; none have been promoted to stable). This plan
therefore implements a fourth rung before giving up: the active version, **only if its own
`state` is `beta` or `stable`**. Verified live: `GET /toolkits/100/dispatch-spec?pilot_id=1`
still returns `Modules: [Left_LED, Mid_LED, TIMER, MPR121, TOUCH_INT]` with `unresolved_libs: []`
— the fourth-rung guarantee holds. This is strictly better than today (adds the missing stable
rung; turns a silent drop into a reported `"none"` reason) and is zero regression versus current
behavior. Documented in `api/lib_version_resolution.py`'s module docstring so a future reader
does not "correct" it back to the three-rung chain.

**One-message-per-lib for `test_import`.** The Pi's `l_load_hardware_libs` (already implemented,
never triggered until now) reads a single TOP-LEVEL `version_id` and reports ONE
`HARDWARE_LIB_TEST_RESULT` for it. Sending one `LOAD_HARDWARE_LIBS` per lib — each with its own
`libs: [<one lib>]`, `test_import: True`, `version_id: <that lib's resolved id>` — is the only
shape that attributes a test-import failure to the correct version with **no Pi-side change**.
A single batched message (all libs, one `version_id`) would misattribute every lib but the first.

## Verification Evidence

- Full backend suite: **314 passed**, 0 failed (verified after `docker compose up --build -d
  api`, no bind mount on this service).
- `wc -l api/hw_introspect.py api/lib_version_resolution.py` → 208, 89 (both < 300).
- `wc -l api/routers/toolkit_dispatch.py` → 376 (< 420 budget for Plan 23-07's headroom).
- Live: `GET /api/toolkits/100/hardware-libs` — every lib carries `resolved_version_id` +
  `resolution_reason` (`toolkit_default` observed for i2c.py/gpio.py/timer.py/mixer.py/
  __init__.py against the real dev DB).
- Live: `GET /api/toolkits/100/dispatch-spec?pilot_id=1` — `Modules` still populated with
  `MPR121`/`TOUCH_INT`, `unresolved_libs: []` (fourth-rung guarantee).
- Live: `GET /api/toolkits` — 200, 112 rows (module-less early-return contract intact).
- `docker compose exec orchestrator python -c "import orchestrator.orchestrator_station"` —
  clean, no traceback; `docker compose logs orchestrator | grep -iE "error|traceback"` — empty.
- `grep -n "test_import" orchestrator_station.py` — flag is SET (`"test_import": True`) in the
  rewritten `_send_hardware_libs_if_needed`.
- `diff <(ssh ... cat .../autopilot/core/pilot.py) /home/ido/pi-mirror/.../pilot.py` — identical.
  No pi-mirror file was read, edited, or committed this session.

## Next Phase Readiness

- The `unresolved_libs` key on `get_dispatch_spec`'s response is new and not yet consumed by
  any UI — a future plan (or plan 23-10's rig validation) should decide whether/how to surface
  it to researchers, parallel to how `preflight_validate`'s `issues` list is already rendered.
- End-to-end proof of the `test_import` round-trip (a real `START` that ships libs and returns
  `HARDWARE_LIB_TEST_RESULT`, verified against `patch_hardware_lib_version`) is explicitly
  USER-RUN on the rig, deferred to plan 23-10 per this plan's own `<verify>` note.
- `orchestrator_station.py`'s `handle_hardware_lib_test_result` was read but not modified — it
  already routes correctly and needed no change.

## Self-Check: PASSED

- `api/lib_version_resolution.py` — FOUND
- `api/routers/toolkit_dispatch.py` — FOUND (modified)
- `api/hw_introspect.py` — FOUND (modified)
- `api/routers/hardware_libs.py` — FOUND (modified)
- `orchestrator/orchestrator/orchestrator_station.py` — FOUND (modified)
- `orchestrator/orchestrator/mics/mics_api_client.py` — FOUND (modified)
- Commit `9edca37` — FOUND in `git log`
- Commit `5df12d6` — FOUND in `git log`
- Commit `de320d2` — FOUND in `git log`
