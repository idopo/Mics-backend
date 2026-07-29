---
phase: 25-detector-derived-view-keys-visible-in-the-fda-editor
plan: 03
subsystem: api
tags: [fastapi, sqlalchemy, fda-validation, hw-introspect, detector-keys, preflight]

# Dependency graph
requires:
  - phase: 25-detector-derived-view-keys-visible-in-the-fda-editor
    provides: "api/detector_keys.py (derive_channels/derive_view_keys/module_detector_channels), api/fda_utils.py::scan_fda_condition_operands (25-01)"
provides:
  - "scan_fda_view_keys / resolve_view_key_issues — the pilot-agnostic FDA scan and the per-pilot preflight resolver (api/detector_keys_scan.py, re-exported from detector_keys.py)"
  - "preflight_validate step 8 — DVK-06/11 view-key/channel resolution against ONE pilot's declared wiring, nested inside step 7's fda_json guard, wrapped in try/except"
  - "detector_channels on every toolkit read route (list/by-id/by-name), fed from module_detector_channels via toolkit_hw_capabilities' module_names"
  - "is_detector on GET /api/hardware-modules/{id}/methods, reusing hw_introspect.class_capabilities"
  - "toolkit_hw_capabilities returns module_names on BOTH return paths (the early return included) — the fix for a 500 that would have hit 98 of 112 task_toolkits rows"
affects: [25-04-react-editor-picker, 25-05-hardware-check-modal, 25-06-pi-deploy-and-rig-proof]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "api/detector_keys_scan.py split out of api/detector_keys.py to respect its 300-line budget; detector_keys.py re-exports both public functions via a bottom-of-file import, and the scan module imports detector_keys._key_sort lazily (function-local) to avoid a circular-import deadlock regardless of which module a caller imports first"
    - "resolve_view_key_issues' 'available_keys' is scoped differently per issue kind: a detector-channel issue shows only that module's derived keys; a literal-key/key_template issue shows the pilot-wide flat list — a mistyped key has no module context to scope the suggestion to"
    - "detector_channels is derived at the toolkit-route CALL SITE, not inside _build_toolkit_row — db is not a parameter of that function; list_toolkits hoists to ONE module_detector_channels call across every toolkit's module names combined, not one per toolkit"

key-files:
  created:
    - api/detector_keys_scan.py
  modified:
    - api/detector_keys.py
    - api/routers/toolkit_dispatch.py
    - api/routers/toolkits.py
    - api/routers/hardware_modules.py
    - api/hw_introspect.py
    - api/tests/test_view_key_preflight.py

key-decisions:
  - "R1 (from plan): an out-of-range detector channel reuses the view_key_unresolved issue kind with an optional detector/available_channels field pair, rather than a separate issue kind — implemented exactly as specified, verified by both a route-level and a pure-resolver test asserting the field's presence/absence"
  - "The key_template branch of resolve_view_key_issues does NOT consult skip_modules (only the detector branch does) — pinned literally from the plan's <interfaces> resolution-rules table, which lists no skip_modules exception for key_template. The route-level test for 'device_name unresolvable' therefore uses a pilot_hardware_config row that EXISTS but lacks device_name (not an absent row), so it produces exactly one issue without colliding with step 6's separate 'missing' issue — a deliberately more precise scenario than 'a pilot that does not have an MPR121 config' would produce if read as 'no config row at all'"
  - "list_toolkits hoists module_detector_channels to one call across the union of every toolkit's module names, then slices per toolkit — get_toolkits_by_name and get_toolkit call it per-toolkit-row directly since those routes touch O(1) toolkits, not O(112)"
  - "The three caps-less toolkit write-path sites (set-canonical/create/patch) are deliberately left un-fed with detector_channels (default [] applies) — verified against EditModal.tsx that none of their response bodies are consumed as a channel source"

patterns-established:
  - "Two action walkers over one FDA shape for two different targets: fda_utils._scan_actions returns hardware refs, detector_keys_scan._walk_view_actions returns view-action key_templates — documented explicitly in both docstrings so a future reader knows why two exist"

requirements-completed: [DVK-02, DVK-06, DVK-11]

# Metrics
duration: 20min
completed: 2026-07-29
---

# Phase 25 Plan 03: Preflight Resolution + Detector Channels on the Toolkit Read Summary

**Wires plan 01's pilot-agnostic derivation into the two places the rest of the system reads from: `preflight_validate` now fails a session start with the exact ref/channel/resolved-key when a pilot's wiring cannot produce a definition's view key, and every toolkit read route (including the one route `TaskEditor.tsx` actually calls) now carries `detector_channels`.**

## Performance

- **Duration:** ~20 min
- **Started:** 2026-07-29T11:17:37Z (from prior commit)
- **Completed:** 2026-07-29T11:34:03Z
- **Tasks:** 3/3
- **Files modified:** 7 (1 created, 6 modified)

## Accomplishments

- `scan_fda_view_keys` (api/detector_keys_scan.py) composes plan 01's `scan_fda_condition_operands`
  (condition operands, delegated verbatim — `grep -c "condition_tree" api/detector_keys.py` is 0)
  with a new `_walk_view_actions` (view-action `key_template`s, including `if`-branch nesting and
  `trigger_assignments`) into one classified scan: `operand` / `detector` / `key_template`.
- `resolve_view_key_issues` classifies that scan against ONE pilot's declared channels/keys,
  producing `view_key_unresolved` issues in the exact documented shape — `detector` +
  `available_channels` present only for a channel-range miss (R1/R2), absent for a literal-key
  miss. Precision rules from the plan's `<interfaces>` table implemented literally, including the
  `{device_name}{pin_number}` "report nothing, unresolvable statically" case and the
  `skip_modules` suppression scoped to the `detector` branch only.
- `preflight_validate` step 8 (api/routers/toolkit_dispatch.py) resolves every scanned entry
  against the target pilot's `pilot_hardware_config` rows, nested inside step 7's
  `if td_full and td_full.fda_json:` guard (not after it) so `already_flagged` is always defined
  when step 8 runs, and wrapped in its own `try`/`except Exception` + `logger.warning` so a broken
  check degrades to "no new issue" rather than 500ing a session start.
- `detector_channels` now on every toolkit read route: `GET /api/toolkits`,
  `GET /api/toolkits/{id}`, and — the route `TaskEditor.tsx:176-183` actually calls —
  `GET /api/toolkits/by-name/{name}`. `toolkit_hw_capabilities` fixed to return `module_names` on
  BOTH return paths; the early-return path (98 of 112 `task_toolkits` rows) was the one that
  mattered — verified live that `GET /api/toolkits` now returns 200 across all 112 rows instead of
  500ing on the module-less majority.
- `is_detector` added to `GET /api/hardware-modules/{id}/methods`, reusing
  `hw_introspect.class_capabilities` (no second predicate) — verified live: module 7 (MPR121)
  `true`, module 8 (TOUCH_INT) `false`.

## Task Commits

Each task was committed atomically:

1. **Task 1: scan_fda_view_keys + resolve_view_key_issues (pure)** - `f6dfd21` (feat)
2. **Task 2: preflight_validate resolves keys and channels against the chosen pilot** - `b79fec8` (feat)
3. **Task 3: expose detector_channels on the toolkit read and is_detector on the module read** - `4cded0f` (feat)

**Plan metadata:** (this commit)

## Files Created/Modified

- `api/detector_keys_scan.py` (created, 234 lines) - `scan_fda_view_keys`, `resolve_view_key_issues`,
  `_walk_view_actions`, `_detector_issue`, `_literal_issue`
- `api/detector_keys.py` (modified, 153 lines) - re-exports `scan_fda_view_keys`/
  `resolve_view_key_issues` from the sibling module (300-line budget would otherwise be exceeded)
- `api/routers/toolkit_dispatch.py` (modified) - step 5 SQL extended to select `flags`; step 6's
  loop collects `module_channels`/`module_keys`/`device_names` from the cfg_row it already fetches;
  step 8 added, nested inside step 7, wrapped in try/except
- `api/routers/toolkits.py` (modified) - `_build_toolkit_row` gains a `detector_channels` kwarg;
  `list_toolkits`/`get_toolkits_by_name`/`get_toolkit` feed it via `module_detector_channels`
- `api/routers/hardware_modules.py` (modified) - `is_detector` on the methods endpoint response
- `api/hw_introspect.py` (modified) - `toolkit_hw_capabilities` returns `module_names` on both
  the early-return and full-computation paths
- `api/tests/test_view_key_preflight.py` (created in plan 03 task 1, extended tasks 2/3) - scanner
  coverage, resolver coverage (DVK-11 in/out-of-range, DVK-09 literal + channel-0 regressions,
  `{device_name}` resolution rules, malformed-input safety), route-level `preflight_validate`
  coverage (mocked-db.execute, SQL-text-dispatching `FakeDb`), and 3 hw_introspect/toolkits tests

## Decisions Made

- `key_template` device-name resolution does not consult `skip_modules` — pinned literally from
  the plan's resolution-rules table, which scopes `skip_modules` to the `detector` kind only. The
  route-level test for this case uses a pilot config row that exists but lacks `device_name`
  (rather than an absent row) so it produces exactly one issue, matching the plan's "→ one issue"
  wording without colliding with step 6's separate `missing` issue for a genuinely absent config.
- `list_toolkits` hoists `module_detector_channels` to one call across the union of every
  toolkit's module names (not one call per toolkit); `get_toolkits_by_name`/`get_toolkit` call it
  per-row since those routes touch O(1) toolkits.
- The three caps-less toolkit write-path sites (`set_canonical_toolkit`, `create_backend_toolkit`,
  `patch_backend_toolkit`) are deliberately left un-fed — their responses default to
  `detector_channels: []` via `_build_toolkit_row`'s existing fallback, and none of their response
  bodies are read as a channel source (`EditModal.tsx`'s PATCH mutation discards the body and
  invalidates the `list_toolkits` query, which IS fed).

## Deviations from Plan

None — plan executed exactly as written. One structural addition not explicitly mandated but
required by the plan's own 300-line constraint on `api/detector_keys.py`: the scanner/resolver
were split into `api/detector_keys_scan.py` per the plan's own fallback instruction ("split the
scanner into `api/detector_keys_scan.py` rather than growing the file"), with a lazy
function-local import to avoid a circular-import deadlock between the two modules regardless of
which one a caller imports first.

## Issues Encountered

- Initial single-file implementation of `detector_keys.py` reached 367 lines, over the plan's
  300-line budget. Resolved via the plan's own documented fallback (split into
  `api/detector_keys_scan.py`), which introduced a circular-import risk (`detector_keys.py`
  re-exports from `detector_keys_scan.py`, which needs `detector_keys._key_sort`) — resolved by
  making that one import lazy (function-local) rather than module-level.
- Route-level `FakeDb` test fixture initially modeled `pilot_hardware_config`'s "existing_configs"
  rows as dicts; the real code indexes them positionally (`row[0]`, `row[1]`), which only surfaced
  once tests ran against the actual route — fixed to tuples, caught before commit.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness

- Plan 04 (React editor picker) can now read `detector_channels` from
  `GET /api/toolkits/by-name/{name}` — the exact route `TaskEditor.tsx` calls — with the shape
  pasted below, live from toolkit 100 / `source_less_toolkit`.
- Plan 05 (HardwareCheckModal) can render `preflight_validate`'s `view_key_unresolved` issues:
  both shapes (with and without `detector`) are pasted below, live.
- `is_detector` on the hardware-module methods endpoint is ready for plan 05's constrained
  detector-write affordance.
- `api/main.py` and `api/fda_validation.py` diffs are both empty — confirmed via `git diff --stat`
  before every commit. Save-time validation (plan 01) is untouched and its DVK-07 regression
  suite still passes in the same full-suite run (219 passed).

### `detector_channels` (live, `GET /api/toolkits/by-name/source_less_toolkit`)

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

Identical on `GET /api/toolkits/100` — verified both routes return byte-identical
`detector_channels` for the same underlying toolkit.

### `view_key_unresolved` issue shapes (from `resolve_view_key_issues`, both forms exercised
live via the route-level test suite)

Detector-channel form (with `detector`/`available_channels`):

```json
{
  "module_id": null,
  "module_name": "MPR121",
  "issue": "view_key_unresolved",
  "detail": "transitions[0].condition_tree.left: references MPR121 channel 5, which would be 'LICKER5' on this pilot. This pilot's MPR121 has channels 1, 2, 3, 4 (LICKER1, LICKER2, LICKER3, LICKER4).",
  "location": "transitions[0].condition_tree.left",
  "key": "LICKER5",
  "available_keys": ["LICKER1", "LICKER2", "LICKER3", "LICKER4"],
  "detector": {"ref": "MPR121", "channel": 5},
  "available_channels": [1, 2, 3, 4]
}
```

Literal-key form (no `detector`/`available_channels`):

```json
{
  "module_id": null,
  "module_name": "",
  "issue": "view_key_unresolved",
  "detail": "transitions[0].condition_tree.left: names view key 'LICKER0', which this pilot does not have. This pilot's detector channels: LICKER1, LICKER2, LICKER3, LICKER4.",
  "location": "transitions[0].condition_tree.left",
  "key": "LICKER0",
  "available_keys": ["LICKER1", "LICKER2", "LICKER3", "LICKER4"]
}
```

---
*Phase: 25-detector-derived-view-keys-visible-in-the-fda-editor*
*Completed: 2026-07-29*

## Self-Check: PASSED

- FOUND: `api/detector_keys_scan.py`
- FOUND: `api/tests/test_view_key_preflight.py`
- FOUND: commit `f6dfd21`
- FOUND: commit `b79fec8`
- FOUND: commit `4cded0f`
- Full backend suite: 219 passed (fresh run, `docker exec mics_api python3 -m pytest /app/tests/ -q`)
- Live verification: `GET /api/toolkits/100`, `GET /api/toolkits/by-name/source_less_toolkit`,
  `GET /api/toolkits` (112 toolkits, 98 module-less), `GET /api/hardware-modules/7/methods`,
  `GET /api/hardware-modules/8/methods` — all run from `mics_web_ui`, all matched expected shape
