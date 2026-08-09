---
phase: 18-extlink-pi-transport
plan: 07
subsystem: api
tags: [ast, hardware-libs, fastapi, extlink]

# Dependency graph
requires:
  - phase: 18-03
    provides: api/tests/test_hardware_libs_extlink.py contract (9 cases, importorskip/xfail-guarded)
provides:
  - api/extlink_ast.py — extract_extlink_metadata(source_or_tree), pure ast, no DB/FastAPI imports
  - extract_ast_metadata (api/routers/hardware_libs.py) now emits an `extlink` block for
    ExternalHardware subclasses, absent for every other lib
affects: [18-10, fda-editor-extlink-operands, hand-driver-plans]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "AST extraction never imports the target module; decorator kwargs are read via ast.Constant
      (.value) / ast.Dict (zip keys/values, ast.unparse each value) / else ast.unparse -- never
      ast.literal_eval, which raises on bare type names like `str`/`float` used as payload values"
    - "A class is only present in extract_extlink_metadata's result if it declares >=1 of
      signal/event/command/decoder; a class with the decorators present but zero @signal still
      appears with signals: {} (EXTLINK-18 control-only legality)"
    - "New metadata extractors called from an existing hot path are wrapped in a narrow
      try/except Exception + logger.warning so an unusual decorator can never turn an upload into
      a 500 -- same defensive posture Phase 25 established for preflight steps"

key-files:
  created:
    - api/extlink_ast.py
  modified:
    - api/routers/hardware_libs.py
    - api/tests/test_hardware_libs_extlink.py

key-decisions:
  - "Signal/event kwarg dicts are built directly from the decorator's ast.Call keywords (no
    intermediate 'kwargs' nesting) -- e.g. a @signal's stored dict is
    {dtype, default, stale_after_ms, stale_policy} as sibling keys, not {dtype, kwargs: {...}} --
    matching test_hardware_libs_extlink.py's exact-equality assertions"
  - "dtype resolves return-annotation-first, then type(default).__name__, else None -- and never
    raises. The extractor's job is description; the TypeError for an unresolvable dtype belongs
    at class-build time on the Pi, per plan text (EXTLINK-12)"
  - "extract_ast_metadata reuses the tree it already parsed (passes tree, not source_code, into
    extract_extlink_metadata) rather than re-parsing -- extract_extlink_metadata accepts either
    a str or an ast.AST for this reason"
  - "hardware_libs.py grew +11/-1 lines (net +10), exceeding the plan's own '<=6 lines' target --
    documented under Deviations. The try/except + logger.warning + import logging import + the
    reused-tree call together needed more lines than the budget allowed; correctness (never 500 on
    an unusual decorator, matching Phase 25's posture) took priority over the line-count target
    per this project's coding-standards priority order (Correctness > Maintainability > ... >
    Brevity)"
  - "Added one test beyond the plan's explicit list --
    test_extlink_signal_splat_kwargs_does_not_block_upload -- covering the @signal(**kwargs) splat
    case the plan's Task 2 action text calls out by name ('a source with @signal(**kwargs) ...
    must still upload 200 with the classes block intact') but that wasn't yet a concrete test row
    in 18-03's contract file"

requirements-completed: [EXTLINK-09]

# Metrics
duration: 25min
completed: 2026-08-09
---

# Phase 18 Plan 07: Hardware-libs extlink AST extractor Summary

**New `api/extlink_ast.py` (116 lines) extracts `@signal`/`@event`/`@command`/`@decoder` metadata from source text without importing the target module or `ast.literal_eval`-ing bare type payloads, wired into `extract_ast_metadata` behind a narrow try/except so an unusual decorator can never 500 a hardware-lib upload.**

## Performance

- **Duration:** ~25 min
- **Started:** 2026-08-09T07:30:00Z (approx.)
- **Completed:** 2026-08-09T07:36:30Z
- **Tasks:** 2
- **Files modified:** 3 (1 created, 2 modified)

## Accomplishments
- `extract_extlink_metadata` extracts all four decorator kinds purely via `ast`, resolving `@signal` dtype from the return annotation first and `type(default)` second (never raising), and rendering `@event` payload dict values (bare type names like `str`/`float`) via `ast.unparse` instead of the `ast.literal_eval` that would crash on them (Pitfall 5).
- `extract_ast_metadata` in `api/routers/hardware_libs.py` now calls `extract_extlink_metadata` on the tree it already parsed and merges an `extlink` key into the result only when the extraction found at least one decorated method — every existing (non-extlink) lib's `ast_metadata` shape is unchanged.
- The call is wrapped in a narrow `try/except Exception` + `logger.warning`, matching Phase 25's defensive posture for new preflight steps: a lib upload must never 500 because a new metadata extractor tripped on an unusual decorator. Added a new test (`test_extlink_signal_splat_kwargs_does_not_block_upload`) proving a `@signal(**kwargs)` splat still uploads 200 with the `classes` block intact.
- `test_hardware_libs_extlink.py` went from 8 skipped + 1 xfail to 9/9 passing (the `xfail` marker on the round-trip test was removed, and the one new splat test was added). Full backend suite: **368 passed, 20 skipped** (up from the 18-03 baseline of 359 passed / 28 skipped — the delta is exactly the 9 tests in this file that now run).
- Live-verified against the running stack: `POST /api/hardware-libs` with an `ExternalHardware` subclass returns `ast_metadata.extlink.OpenEphysProbeLive.signals.firing_rate.dtype == "float"` and `commands.start_recording.returns == "bool"`, with `classes` unaffected; the test lib was deleted afterward (`DELETE /api/hardware-libs/71` → `{"deleted": 71}`).

## Task Commits

Each task was committed atomically:

1. **Task 1: `api/extlink_ast.py` — decorator metadata extraction** - `1e37e23` (test)
2. **Task 2: Wire the extlink block into `extract_ast_metadata`** - `aec06e3` (feat)

## Files Created/Modified
- `api/extlink_ast.py` (new, 116 lines) — `EXTLINK_DECORATORS` tuple + `extract_extlink_metadata(source_or_tree)`, plus four small private helpers (`_kwarg_value`, `_decorator_call`, `_signal_dtype`, `_command_args`). Pure `ast`; no DB, no FastAPI, no import from `routers/`.
- `api/routers/hardware_libs.py` — `extract_ast_metadata` now builds a `result` dict, calls `extract_extlink_metadata(tree)` inside a narrow `try/except Exception` (`logger.warning` on failure, via `logging.getLogger(__name__)`), and adds `result["extlink"]` only when non-empty. Added `import logging`. Net diff: +11/-1.
- `api/tests/test_hardware_libs_extlink.py` — removed the `xfail` marker from `test_extlink_upload_round_trip` (now a plain passing test); added `SIGNAL_SPLAT_SOURCE` fixture and `test_extlink_signal_splat_kwargs_does_not_block_upload`.

## The `extlink` block shape (pinned for plan 18-10)

`extract_extlink_metadata(source)` returns `{ClassName: {signals, events, commands, decoder}}`, one entry per class that declares at least one of the four decorators (a plain hardware class with none of them is omitted entirely):

```json
{
  "OpenEphysProbe": {
    "signals": {
      "firing_rate": {"dtype": "float", "default": 0.0, "stale_after_ms": 200, "stale_policy": "hold_last"}
    },
    "events": {
      "object_seen": {"payload": {"object": "str", "confidence": "float"}}
    },
    "commands": {
      "set_gain": {"args": [{"name": "gain", "dtype": "float"}, {"name": "unit", "dtype": "str"}], "returns": "bool"}
    },
    "decoder": "decode"
  }
}
```

- `signals[name]` = `{"dtype": <str|null>, **all decorator kwargs as-is}` — kwargs are sibling keys next to `dtype`, not nested.
- `events[name]` = decorator kwargs as-is (e.g. `{"payload": {...}}`); dict-valued kwargs have their VALUES `ast.unparse`'d into strings (never `ast.literal_eval`'d), so `str`/`float` bare-type payload declarations survive.
- `commands[name]` = `{"args": [{"name", "dtype"}, ...], "returns": <str|null>}` — no default values recorded for command args (unlike the router's pre-existing `extract_ast_metadata`, which does include `default`).
- `decoder` = the decorated method's name, or `None` if the class has extlink decorators but no `@decoder`.
- Everything is string-typed (`dtype`/`returns`/`annotation` values), since the backend cannot import `autopilot` or resolve real Python `type` objects.
- `extract_ast_metadata`'s top-level `ast_metadata` gains an `extlink` key with this exact shape, present only when non-empty; the pre-existing `classes` key is untouched.

## Decisions Made
- Signal/event metadata dicts store decorator kwargs as sibling keys (not nested under a `kwargs` key) — matches the plan's pinned test assertions exactly.
- `extract_extlink_metadata` accepts either a source string or an already-parsed tree so `hardware_libs.py` can reuse the tree it already built, avoiding a second `ast.parse`.
- A class with zero extlink decorators of any kind is omitted from the result entirely (not included with all-empty fields) — this is what makes `"Valve" not in meta` true for `PLAIN_HARDWARE_SOURCE` and keeps the non-extlink-lib `ast_metadata` shape byte-identical (no stray `extlink` key ever appears for them).
- See frontmatter `key-decisions` for the `hardware_libs.py` line-budget deviation and dtype-resolution-never-raises rationale.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 - Blocking/defensive-completeness] `hardware_libs.py` exceeded the plan's "<=6 changed lines" target**
- **Found during:** Task 2
- **Issue:** The plan's own done-criteria asked for `git diff --stat api/routers/hardware_libs.py` to show `<=6 changed lines`, but the task's own action text mandates a narrow `try/except Exception` with `logger.warning`, reusing the already-parsed `tree`, and conditionally adding the `extlink` key only when non-empty. Fitting all of that (plus the required `import logging`) into 6 lines was not achievable without sacrificing the defensive posture the same task explicitly requires.
- **Fix:** Implemented the full defensive version: `import logging` (+1), and the `return {"classes": classes}` one-liner replaced by an 8-line `result = ...` / `try` / call / conditional-assign / `except ... logger.warning` / `return result` block. Net diff: **+11/-1 (12 changed lines)**, verified via `git diff --stat`.
- **Files modified:** `api/routers/hardware_libs.py`
- **Verification:** Full backend suite green (368 passed, 20 skipped, 0 errors); the new splat test proves the try/except actually protects the upload path.
- **Committed in:** `aec06e3` (Task 2 commit)

**2. [Rule 2 - Missing critical] Added a test not itemized in 18-03's pinned contract, per this plan's own Task 2 action text**
- **Found during:** Task 2
- **Issue:** Task 2's action text says "Assert this in a test — a source with `@signal(**kwargs)` (a splat, which nothing sensible can extract) must still upload 200 with the classes block intact," but 18-03's `test_hardware_libs_extlink.py` (the pinned contract) has no such test row — only the round-trip test with its `xfail` marker.
- **Fix:** Added `SIGNAL_SPLAT_SOURCE` fixture and `test_extlink_signal_splat_kwargs_does_not_block_upload`, asserting a 200 response with `classes` present in `ast_metadata`.
- **Files modified:** `api/tests/test_hardware_libs_extlink.py`
- **Verification:** New test passes (`9 passed` in the file's full run).
- **Committed in:** `aec06e3` (Task 2 commit)

---

**Total deviations:** 2 auto-fixed (1 line-budget overage necessitated by correctness, 1 missing test explicitly called for in the plan's own prose but absent from the pinned contract)
**Impact on plan:** No scope creep — both deviations were required by the plan's own Task 2 action text; neither is architectural.

## Issues Encountered
None.

## User Setup Required
None - no external service configuration required.

## Next Phase Readiness
- Plan 18-10 (FDA-editor extlink operands, per STATE.md's phase-18 plan list) can now read `ast_metadata.extlink` for any `ExternalHardware` subclass through the existing `GET /api/hardware-libs/{lib_id}` / `GET /api/toolkits/{id}/hardware-libs` surfaces — the shape is pinned above verbatim.
- `gsd-tools requirements mark-complete EXTLINK-09` — attempted; see below.
- No blockers introduced for 18-08 (device-lease, `api/device_lease.py`/`api/models.py`/`api/db.py`/`api/routers/toolkit_dispatch.py`/`api/tests/test_view_key_preflight.py`), which was running in parallel and touches none of this plan's three files.

---
*Phase: 18-extlink-pi-transport*
*Completed: 2026-08-09*

## Self-Check: PASSED

- FOUND: api/extlink_ast.py
- FOUND: .planning/phases/18-extlink-pi-transport/18-07-SUMMARY.md
- FOUND: 1e37e23 (task 1 commit)
- FOUND: aec06e3 (task 2 commit)
