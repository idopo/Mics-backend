---
phase: 18-extlink-pi-transport
plan: 13
subsystem: api
tags: [extlink, fda-validation, preflight, toolkits, fastapi]

# Dependency graph
requires:
  - phase: 18-07
    provides: "ast_metadata.extlink shape: {ClassName: {signals, events, commands, decoder}}, one
      entry per class declaring >=1 of signal/event/command/decoder"
provides:
  - "api/extlink_keys.py — extlink_signals_from_ast, has_extlink_block, derive_extlink_keys,
    module_extlink_signals (cross-pilot union+conflict, mirrors module_detector_channels),
    pilot_extlink_keys (single-pilot resolution off an already-resolved lib version)"
  - "toolkit read (list/by-name/by-id) carries extlink_signals: [{module_name, source_ids,
    signals, keys, conflict, by_pilot}]"
  - "save-time gate (collect_hard_errors/validate_compute_variables) accepts an extlink
    {\"view\": \"<source_id>.<signal>\"} operand as a real view key"
  - "preflight (toolkit_dispatch.py step 8) unions THIS pilot's extlink keys into valid_keys —
    a key naming another pilot's source_id surfaces as the existing view_key_unresolved issue"
affects: [18-14, fda-editor-extlink-operands]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "module_extlink_signals mirrors module_detector_channels' contract byte-for-byte
      (conflict = len({frozenset(p['keys']) for p in by_pilot}) > 1), including the ADVISORY-ONLY
      docstring posture and the same-name-dedupe-across-hardware_modules-rows rule"
    - "A module qualifies as external if EITHER its resolved lib version's ast_metadata has an
      extlink block OR its per-pilot config carries both role and source_id — the second clause
      covers a control-only lib whose only decorator is a class-level liveness_hook override,
      which 18-07 emits no extlink key for at all"
    - "derive_extlink_keys always appends f'{source_id}.alive' even when signal_names is empty
      (EXTLINK-18 control-only legality) and never duplicates a signal literally named 'alive'"
    - "Per-pilot preflight resolution (pilot_extlink_keys) is a separate, narrower helper from the
      cross-toolkit aggregation (module_extlink_signals) — the step-6 loop already has version_id
      and cfg for ONE pilot and must not re-run the cross-pilot query just to resolve one row"
    - "New metadata reads inside an existing hot loop (preflight step 6, save-gate
      reject_if_hard_errors) are wrapped in narrow try/except + logger.warning, matching the
      defensive posture 18-07/18-08 already established"

key-files:
  created: []
  modified:
    - api/extlink_keys.py
    - api/tests/test_extlink_keys.py
    - api/routers/toolkits.py
    - api/fda_validation.py
    - api/routers/toolkit_dispatch.py

key-decisions:
  - "pilot_extlink_keys(db, version_id, config) added beyond the plan's originally pinned
    interfaces list, as the file-size escape hatch the plan's own Task 3 action text names
    ('move the per-pilot collection body into a named helper in api/extlink_keys.py') — used
    proactively since toolkit_dispatch.py was already at the 500-line hard limit"
  - "A variable-name collision with an extlink key gets a distinct error message
    ('collides with an external-signal view key') rather than being folded into the
    detector-derived-key message, so a researcher is never sent hunting a detector that
    doesn't exist"
  - "No new PREFLIGHT_ISSUE_KINDS member — a cross-pilot extlink key mismatch reuses the
    existing view_key_unresolved issue, per the plan's explicit no-new-issue-kind constraint"

requirements-completed: [EXTLINK-19]

# Metrics
duration: ~15min (interrupted-agent recovery + verification)
completed: 2026-08-09
---

# Phase 18 Plan 13: Extlink signal aggregation + save/preflight wiring Summary

**New `api/extlink_keys.py` (167 lines) aggregates `ast_metadata.extlink` against per-pilot hardware config into `<source_id>.<signal>` view keys, surfaced on every toolkit read and accepted by both the save-time 422 gate and preflight's view-key resolution — closing the last gap that made `view.get_value("dlc_cam1.left_paw_x")` unreachable through any supported path.**

## Recovery Context

This plan was previously executed by an agent that was interrupted mid-Task-3 by a host disk-full
(ENOSPC) condition. On resuming: `git show --stat` on the two existing commits
(`5924812` test, `5610026` feat) confirmed Tasks 1–2 were fully committed and clean. `git diff` on
the four uncommitted working-tree files (`api/extlink_keys.py`, `api/fda_validation.py`,
`api/routers/toolkit_dispatch.py`, `api/tests/test_extlink_keys.py`) showed Task 3's implementation
was **already complete and syntactically valid** (`ast.parse` succeeded on all four; no truncation)
— `collect_hard_errors`/`validate_compute_variables` both already carried the `extlink_keys`
parameter, `toolkit_dispatch.py`'s step-6/step-8 wiring was in place, and the three new tests were
present. The reported RED state (`TypeError: collect_hard_errors() got an unexpected keyword
argument 'extlink_keys'`) was stale: the interrupted agent had written all the code but the running
`api` container predates it (no bind mount) and had never been rebuilt to pick up the change. A
`docker compose up --build -d api` rebuild immediately turned the suite GREEN — no code was
missing or broken; only a container rebuild + commit were outstanding.

## Performance

- **Duration:** ~15 min (verification-heavy: live round-trip proofs, cleanup)
- **Tasks:** 3 (1 and 2 already committed by the interrupted agent; 3 verified complete and committed here)
- **Files modified:** 4 (this session's commit) + 1 (Task 2, already committed)

## Accomplishments
- Confirmed Tasks 1 and 2 (extlink_keys.py aggregator + toolkit-read surfacing) were already correctly committed, with no truncation or corruption from the ENOSPC interrupt.
- Verified Task 3's already-written implementation with a full container rebuild: `435 passed, 1 skipped` (full backend suite), `94 passed` (test_extlink_keys.py + test_detector_keys.py combined), `100 passed` (test_view_key_preflight.py).
- **Live-verified the exact 422→200 round trip the plan's own design_decision demands**, using `git stash` to temporarily revert Task 3's two production files and rebuild the container: `PUT /api/task-definitions/{id}` with a transition reading `{"view": "dlc_cam1.left_paw_x"}` returned `422 {"errors": ["transitions[0].condition_tree.left: references unknown variable/flag 'dlc_cam1.left_paw_x'"]}` on the unfixed code, then `200 {"status":"ok","validation_status":"ok"}` after `git stash pop` + rebuild.
- **Live-verified the exact `extlink_signals` toolkit-read shape** plan 18-14 must match field-for-field (see below) using a real uploaded `ExternalHardware` lib, hardware module, backend-authored toolkit, and two pilots configured with different `source_id`s — `conflict: true`, correct `keys` union, correct `by_pilot` breakdown.
- Committed the previously-uncommitted Task 3 work; all temporary live-verification artifacts (task definition, pilot hardware config rows, hardware module, hardware lib, toolkit) deleted from the dev DB afterward.

## Task Commits

Each task was committed atomically (Tasks 1–2 by the interrupted prior agent; Task 3 in this session):

1. **Task 1: `api/extlink_keys.py` — signal aggregation with cross-pilot conflict** - `5924812` (test) — from interrupted prior session, verified intact
2. **Task 2: Surface `extlink_signals` on the toolkit read** - `5610026` (feat) — from interrupted prior session, verified intact
3. **Task 3: Teach the save gate and preflight that an extlink key is a real view key** - `3fca80b` (feat) — this session

## Files Created/Modified
- `api/extlink_keys.py` (167 lines) — `extlink_signals_from_ast`, `has_extlink_block`, `derive_extlink_keys`, `module_extlink_signals` (Task 1, prior session); `pilot_extlink_keys` (Task 3, this session) — single-pilot resolution off an already-resolved `version_id`/`config` pair, avoiding a second cross-pilot query in the preflight per-pilot loop.
- `api/tests/test_extlink_keys.py` (317 lines) — full aggregator coverage (Task 1) plus 3 `collect_hard_errors` cases (Task 3): known extlink key passes, unknown key still 422s, variable-collision message says "external-signal" not "detector".
- `api/routers/toolkits.py` (Task 2, prior session, unchanged this session) — `extlink_signals` param/key on `_build_toolkit_row`, fed at `list_toolkits` (batched), `get_toolkits_by_name`, `get_toolkit`.
- `api/fda_validation.py` — `validate_compute_variables`/`collect_hard_errors` gain optional `extlink_keys: set[str] | None = None`; `reject_if_hard_errors` computes the pilot-agnostic union via `module_extlink_signals`, same split as `detector_keys`.
- `api/routers/toolkit_dispatch.py` (500 lines, at the plan's `<=500` gate) — step-6 loop collects `module_extlink_keys` via `pilot_extlink_keys` in its own narrow try/except; step 8 unions the flattened keys into `valid_keys`. `PREFLIGHT_ISSUE_KINDS` unchanged (11 members, verified via grep).

## The `extlink_signals` JSON shape (pinned for plan 18-14)

Live-verified against `GET /api/toolkits/by-name/{name}` for a toolkit with one external module
configured by two pilots at different `source_id`s:

```json
"extlink_signals": [
  {
    "module_name": "dlc_cam_verify1813",
    "source_ids": ["dlc_cam1", "dlc_cam2"],
    "signals": [{"name": "left_paw_x", "dtype": "float"}],
    "keys": ["dlc_cam1.alive", "dlc_cam1.left_paw_x", "dlc_cam2.alive", "dlc_cam2.left_paw_x"],
    "conflict": true,
    "by_pilot": [
      {"pilot_id": 1, "pilot_name": "pilot_raspberry_lior", "source_id": "dlc_cam1",
       "keys": ["dlc_cam1.alive", "dlc_cam1.left_paw_x"]},
      {"pilot_id": 2, "pilot_name": "youri_pilot", "source_id": "dlc_cam2",
       "keys": ["dlc_cam2.alive", "dlc_cam2.left_paw_x"]}
    ]
  }
]
```

For a toolkit with no external modules, `extlink_signals` is always `[]` (never `null`, never absent).

**`ast_metadata.extlink` accessor path used:** `ast_metadata["extlink"][class_name]["signals"]` —
matches 18-07-SUMMARY.md's pinned shape exactly (`{ClassName: {signals: {name: {dtype, ...}}, ...}}`);
`extlink_signals_from_ast` iterates every class entry's `signals` dict, so a lib with multiple
`ExternalHardware` subclasses in one file contributes signals from all of them.

## Decisions Made
- `pilot_extlink_keys` (a new function beyond the plan's originally pinned `<interfaces>` list) was kept — it is the file-size escape hatch the plan's own Task 3 text names explicitly ("move the per-pilot collection body into a named helper in `api/extlink_keys.py`... that extraction is the designated escape hatch, not a deviation"), applied proactively since `toolkit_dispatch.py` was already at the 500-line hard limit before this task's edits.
- A declared `variables` entry colliding with an extlink key raises a message naming "external-signal view key", never "detector-derived view key" — verified by its own test so the two error paths can never silently merge.
- No new `PREFLIGHT_ISSUE_KINDS` member — confirmed via `grep -c "PREFLIGHT_ISSUE_KINDS = frozenset"` and manual inspection: still exactly 11 kinds, `device_held`/`extlink_config_invalid` (18-08's additions) unchanged.

## Deviations from Plan

None from this session's work — Task 3's implementation, written by the interrupted prior agent, matched the plan's action text and interfaces exactly (plus the explicitly-sanctioned `pilot_extlink_keys` escape-hatch helper). This session's only substantive action was verification (container rebuild, live round-trip proofs, full-suite re-run) and the commit that had been blocked by the ENOSPC interrupt.

### Auto-fixed Issues
None — no bugs, missing functionality, or blocking issues were found; the prior agent's uncommitted work was already correct.

## Issues Encountered
- **Stale RED report.** The task brief reported 3 failing tests with `TypeError: collect_hard_errors() got an unexpected keyword argument 'extlink_keys'`. Investigation showed this was accurate only against the *running, unrebuilt* `api` container — the working-tree files on disk already had the parameter. Root cause: `docker compose exec` runs against the container's baked-in copy of the source (no bind mount, per the plan's own verification block: "no bind mount — a running container cannot see new files"), and no rebuild had occurred since the ENOSPC interrupt. Resolved by `docker compose up --build -d api`.

## User Setup Required
None - no external service configuration required.

## Next Phase Readiness
- Plan 18-14 (FDA-editor extlink operands) can now consume `extlink_signals` from any of the three toolkit-read routes using the exact shape pinned above.
- `gsd-tools requirements mark-complete EXTLINK-19` — attempted; see below (same known traceability gap as every prior EXTLINK plan).
- No blockers for plans 18-09 (device-lease orchestrator wiring, ran concurrently in the same checkout, touches `device_leases.py`/`main.py`/`test_view_key_preflight.py`/`HardwareCheckModal.tsx` — none of which this plan's commit touched).

---
*Phase: 18-extlink-pi-transport*
*Completed: 2026-08-09*

## Self-Check: PASSED

- FOUND: .planning/phases/18-extlink-pi-transport/18-13-SUMMARY.md
- FOUND: 5924812 (task 1 commit, prior session)
- FOUND: 5610026 (task 2 commit, prior session)
- FOUND: 3fca80b (task 3 commit, this session)
- FOUND: api/extlink_keys.py
