---
phase: 25-detector-derived-view-keys-visible-in-the-fda-editor
plan: 01
subsystem: api
tags: [fastapi, sqlalchemy, fda-validation, hw-introspect, detector-keys]

# Dependency graph
requires:
  - phase: 24-trigger-assignment-action-lists
    provides: "api/fda_validation.py hard-422 enforcement point, hw_introspect.toolkit_hw_capabilities (detector_refs), pilot_hardware_config name-keyed identity (Phase 17)"
provides:
  - "derive_channels / derive_view_keys — the single backend key-derivation helper (DVK-01)"
  - "module_detector_channels — advisory cross-pilot union with per-pilot provenance and conflict flag (DVK-02, DVK-09)"
  - "scan_fda_condition_operands — the ONE condition-operand walker shared by save-time validation and preflight"
  - "validate_condition_operands — DVK-11 save-time 422 on a malformed or non-detector view_detector operand"
affects: [25-02-pi-fda-vocabulary, 25-03-preflight-and-dispatch-route, 25-04-react-editor-picker]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Numeric-string coercion mirrors the Pi's mics_task._coerce_hw_value (_as_int rejects bool, accepts int and numeric str)"
    - "Advisory cross-pilot union with by_pilot provenance + conflict flag, never merged silently (CONTEXT D4)"
    - "Condition-operand walker as an independent sibling of scan_fda_for_refs in fda_utils.py, shared by two consumers via one function"
    - "Detector-keys module import boundary: fda_validation.py never imports detector_keys.py — pinned behaviourally via _valid_flag_names equality, not by grep"

key-files:
  created:
    - api/detector_keys.py
    - api/tests/test_detector_keys.py
  modified:
    - api/fda_utils.py
    - api/fda_validation.py
    - api/tests/test_task_definitions_validation.py

key-decisions:
  - "module_detector_channels sorts by_pilot by pilot_name inside the function itself (not relying solely on the SQL ORDER BY) so the sort contract holds for any caller, including the FakeDb-backed unit tests"
  - "conflict is computed from frozenset(keys) equality across by_pilot entries, not tuple equality, so key-set disagreement is detected independent of incidental ordering"
  - "validate_condition_operands treats detector_refs=set() identically to None (both skip rule 4) since Python treats an empty set as falsy — matches the plan's 'None or empty' spec without a separate branch"

patterns-established:
  - "P1-P7 rationale (rejected alternatives for DVK-02's source of truth, the operand-walker boundary, the derivation duplication across Pi/API) is captured in api/detector_keys.py and api/fda_utils.py module docstrings for future plans to read before extending"

requirements-completed: [DVK-01, DVK-02, DVK-07, DVK-09, DVK-11]

# Metrics
duration: 45min
completed: 2026-07-29
---

# Phase 25 Plan 01: Detector-Derived View Keys — Backend Derivation + Save-Time Gate Summary

**Single backend derivation helper (`f"{device_name}{i}"`) plus a cross-pilot advisory union with surfaced conflicts, a shared condition-operand walker, and a save-time 422 gate that rejects a `view_detector` operand naming a non-detector module or a malformed channel — while deliberately leaving per-pilot channel-range checking to preflight.**

## Performance

- **Duration:** 45 min
- **Started:** 2026-07-29T00:00:00Z (approx, from git log)
- **Completed:** 2026-07-29
- **Tasks:** 4/4
- **Files modified:** 5 (2 created, 3 modified)

## Accomplishments

- `api/detector_keys.py` (143 lines): `derive_channels`/`derive_view_keys` implement the ONE key
  format from `device_name` × `num_detectors` × `first_channel`, matching the Pi's
  `_coerce_hw_value` numeric-string coercion exactly, byte-identical to `range(0, n)` when
  `first_channel` is absent, and never raising on malformed input (DVK-01, DVK-09).
- `module_detector_channels(db, module_names)` joins `pilot_hardware_config` on `name` across
  every pilot (mirroring `get_dispatch_spec`'s lookup), unions the derived channels/keys per
  module, and surfaces `conflict: true` with full `by_pilot` provenance whenever two pilots
  disagree — verified against live data: `MPR121` → `channels [0,1,2,3]`, `keys
  LICKER0…LICKER3`, `conflict: false` (DVK-02).
- `scan_fda_condition_operands` in `api/fda_utils.py` (new 104-line addition, file now 162
  lines) walks every condition operand across `transitions[*].condition_tree` (recursive
  AND/OR), `condition_groups`, legacy `conditions`, `states[*].wait_condition`, and `if`-action
  conditions nested in both `entry_actions` and `trigger_assignments[*].actions` — a territory
  `scan_fda_for_refs` never touches. Never raises; returns literal operands untouched.
- `validate_condition_operands` in `api/fda_validation.py` is the DVK-11 save-time gate: a
  `view_detector` operand's `ref` must be a real detector on the toolkit (when
  `toolkit_hw_capabilities`'s already-computed `detector_refs` is known and non-empty) and
  `channel` must be a non-negative int (bool explicitly rejected). Wired into
  `collect_hard_errors`/`reject_if_hard_errors` at zero new queries. An out-of-range channel is
  deliberately NOT rejected here (P5 — that is preflight's job in plan 03).
- Four DVK-07 regression tests were written and verified to pass against the pre-plan code
  first, pinning the boundary that `LICKER1` as a flag/output ref is still rejected and
  `_valid_flag_names` returns exactly `toolkit.flags ∪ fda.variables ∪ {"trial_counter"}`.

## Task Commits

Each task was committed atomically:

1. **Task 1: derive_channels + derive_view_keys — the single key format** - `3c10845` (feat)
2. **Task 2: module_detector_channels — advisory cross-pilot union with surfaced disagreement** - `895ab37` (feat)
3. **Task 3: scan_fda_condition_operands — the ONE condition walker (P6)** - `9a6cf98` (feat)
4. **Task 4: DVK-11 save-time gate + the DVK-07 boundary regression** - `8fc305f` (feat)

**Plan metadata:** (this commit)

## Files Created/Modified

- `api/detector_keys.py` (created, 143 lines) - `derive_channels`, `derive_view_keys`,
  `module_detector_channels`, `_as_int`, `_key_sort`
- `api/tests/test_detector_keys.py` (created) - 17-row golden derivation table (parametrized over
  both functions + lockstep-length invariant), union/conflict/ordering coverage via a `FakeDb`
  stub, and the condition-operand walker's nesting/location/malformed-input coverage
- `api/fda_utils.py` (modified, +104 lines → 162 total) - `scan_fda_condition_operands` plus
  private helpers `_scan_condition`, `_scan_condition_node`, `_scan_action_conditions`;
  `scan_fda_for_refs`/`_scan_actions`/`ref_label` untouched
- `api/fda_validation.py` (modified, +48 lines → 370 total) - `validate_condition_operands`;
  `collect_hard_errors` and `reject_if_hard_errors` gained a `detector_refs` parameter threading
  through `toolkit_hw_capabilities()["detector_refs"]`; module docstring records the new
  REF+SHAPE-here / RANGE-at-preflight split
- `api/tests/test_task_definitions_validation.py` (modified) - DVK-07 regression section (4
  tests, verified passing against pre-plan code) and DVK-11 coverage (valid/invalid ref,
  `detector_refs` None/empty leniency, malformed channel/ref shapes, all three operand sites,
  the P5 no-range-check-at-save-time case, and `collect_hard_errors` wiring)

## Decisions Made

- **`by_pilot` is sorted inside `module_detector_channels` itself**, not left to the caller's SQL
  `ORDER BY`. Found during Task 2's TDD RED phase: a `FakeDb`-backed unit test with rows in
  scrambled order failed because the function trusted row order. The SQL `ORDER BY phc.name,
  p.name` is kept (real DB reads already sorted, redundant but harmless) but the function no
  longer depends on it — correctness holds for any caller, not just the real DB path.
- **`conflict` computed via `frozenset(keys)` equality**, not `tuple(keys)` equality, per the
  plan's literal "different key sets" wording — avoids a false negative if two pilots' key lists
  ever differ only in incidental order (they don't today, since both are built in ascending
  channel order, but frozenset is the correct predicate for "sets differ").
- No other deviations — the plan's interfaces, golden table, and decision rationale (P1-P7) were
  followed exactly as written.

## Deviations from Plan

None - plan executed exactly as written. The one implementation adjustment (`by_pilot` sort
location) was a same-task TDD fix within Task 2, not a deviation from the task's `<action>` or
`<behavior>` spec — the interface and observable behavior are unchanged from what the plan
specified.

## Issues Encountered

None.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness

- `module_detector_channels`'s exact JSON shape (pasted below) is what plan 03 puts on the
  toolkit read route and plan 04's React code consumes — verified against live data, not just
  synthetic tests.
- `scan_fda_condition_operands` is ready for plan 03's preflight resolver to reuse verbatim (P6)
  — same function, second caller, no new walker needed.
- `derive_channels`/`derive_view_keys` and the GOLDEN_CASES table are ready for plan 02's Pi twin
  to pin against verbatim (P3).
- No route changes were made in this plan (confirmed: `git diff api/main.py` is empty) — plan 03
  is unblocked to wire `module_detector_channels` and `validate_condition_operands` into an
  actual endpoint.

### `module_detector_channels` JSON shape (live data, `MPR121` + `TOUCH_INT`)

```json
[
  {
    "module_name": "MPR121",
    "device_names": ["LICKER"],
    "channels": [0, 1, 2, 3],
    "keys": ["LICKER0", "LICKER1", "LICKER2", "LICKER3"],
    "conflict": false,
    "by_pilot": [
      {
        "pilot_id": 1,
        "pilot_name": "pilot_raspberry_lior",
        "device_name": "LICKER",
        "channels": [0, 1, 2, 3],
        "keys": ["LICKER0", "LICKER1", "LICKER2", "LICKER3"]
      }
    ]
  }
]
```

(`TOUCH_INT` derives nothing and is correctly omitted.)

---
*Phase: 25-detector-derived-view-keys-visible-in-the-fda-editor*
*Completed: 2026-07-29*

## Self-Check: PASSED

- FOUND: `api/detector_keys.py`
- FOUND: `api/tests/test_detector_keys.py`
- FOUND: commit `3c10845`
- FOUND: commit `895ab37`
- FOUND: commit `9a6cf98`
- FOUND: commit `8fc305f`
- Full backend suite: 163 passed (fresh run, `docker exec mics_api python3 -m pytest /app/tests/ -q`)
