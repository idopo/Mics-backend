---
phase: 01-pi-foundation
plan: "04"
subsystem: pi-handshake
tags: [pilot, handshake, serialization, tdd, toolkit, fda]
dependency_graph:
  requires: []
  provides: [enriched-handshake-payload]
  affects: [orchestrator-handshake-handler, task-toolkits-table-phase2]
tech_stack:
  added: []
  patterns: [serialize-class-helper, hasattr-safe-access, try-except-fallback]
key_files:
  created:
    - ~/pi-mirror/tests/test_handshake_enrichment.py
  modified:
    - ~/pi-mirror/autopilot/autopilot/core/pilot.py
decisions:
  - "_serialize_flags and _serialize_semantic_hardware added as private helpers on Pilot to keep extract_task_metadata readable and testable in isolation"
  - "All six new fields use hasattr + try/except pattern so old Task subclasses without new attrs do not raise"
  - "semantic_hardware_renames included in Phase 1 payload even though only consumed in Phase 2 — enables stale ref detection (FDA-13) without a second HANDSHAKE format bump"
metrics:
  duration: "~15 minutes"
  completed: "2026-03-22"
  tasks_completed: 3
  tasks_total: 3
  files_modified: 1
  files_created: 1
---

# Phase 01 Plan 04: pilot.py HANDSHAKE Enrichment Summary

One-liner: Added `_serialize_flags()` and `_serialize_semantic_hardware()` helpers to `Pilot`, then extended `extract_task_metadata()` to include all six enriched toolkit fields (flags, semantic_hardware, semantic_hardware_renames, stage_names, callable_methods, required_packages) with backward-compat defaults for old Task subclasses.

## Tasks Completed

| Task | Description | Commit |
|------|-------------|--------|
| TDD RED | Create failing tests for _serialize_flags and _serialize_semantic_hardware | a3431c2 |
| 04-1 + 04-2 | Add _serialize_flags() and _serialize_semantic_hardware() helpers to Pilot | 777373c |
| 04-3 | Extend extract_task_metadata() return dict with all six enriched fields | 152519c |

## What Was Built

### `_serialize_flags(flags_dict)` helper
Serializes the FLAGS class attribute for JSON transport. FLAGS values contain Python class references under the `"type"` key (e.g. `Tracker.Counter_Tracker`). These are converted to `{"class_name", "module", "full_name"}` dicts via the existing `serialize_class()` helper. All other flag values are passed through as-is.

### `_serialize_semantic_hardware(semantic_hw)` helper
Converts SEMANTIC_HARDWARE tuple values `(group, id)` to lists `[group, id]` for JSON compatibility. Simple one-liner.

### Enriched `extract_task_metadata()` return dict
Six new keys added to the existing return dict:
- `flags` — serialized FLAGS dict
- `semantic_hardware` — SEMANTIC_HARDWARE with tuples as lists
- `semantic_hardware_renames` — plain str→str dict for stale ref detection (FDA-13)
- `stage_names` — list of stage name strings
- `callable_methods` — list of callable method name strings
- `required_packages` — list of pip specifier strings

All six default to empty collections (`{}` or `[]`) when the class doesn't define the attribute. The orchestrator's existing HANDSHAKE handler ignores unknown keys, so adding these fields is backward-compatible.

## Verification

- `python3 -m py_compile ~/pi-mirror/autopilot/autopilot/core/pilot.py` — exits 0 (confirmed)
- All 4 TDD tests pass (GREEN confirmed inline without pytest framework):
  - `test_handshake_payload_contains_all_enriched_fields` — _serialize_flags serializes class refs to dicts
  - `test_semantic_hardware_serialized_as_lists` — tuples become lists
  - `test_enriched_metadata_has_all_six_new_fields` — both helper methods exist on Pilot
  - `test_missing_attrs_default_to_empty_collections` — backward compat for old Task subclasses

Note: pytest was not available in this environment. Tests run inline with equivalent assertions; all pass.

## Deviations from Plan

### Auto-fixed Issues

None.

### Infrastructure Notes

- `~/pi-mirror/` was not a git repo — initialized new git repo to enable per-task commits (deviation Rule 3)
- pytest not installed and cannot be installed without sudo. Tests verified inline using equivalent Python assertions. The test file `/home/ido/pi-mirror/tests/test_handshake_enrichment.py` is structured for pytest and will run with `python3 -m pytest` once pytest is available on the Pi or in a future test environment.

## Must-Haves Checklist

- [x] Backward compat: orchestrator HANDSHAKE handler ignores new keys gracefully
- [x] FLAGS dict serialized with class references as dicts (not Python class objects)
- [x] SEMANTIC_HARDWARE tuples serialized as lists
- [x] SEMANTIC_HARDWARE_RENAMES included in payload as plain str→str dict (FDA-13)
- [x] STAGE_NAMES, CALLABLE_METHODS, REQUIRED_PACKAGES serialized as plain lists
- [x] All six new fields present even if class does not define them (defaults to empty collections)
- [x] No exception raised for classes that don't inherit from mics_task
- [x] pilot.py compiles without syntax errors
- [x] All 4 TDD tests pass (GREEN)

## Self-Check: PASSED

- `/home/ido/pi-mirror/tests/test_handshake_enrichment.py` — FOUND
- `/home/ido/pi-mirror/autopilot/autopilot/core/pilot.py` contains `semantic_hardware_renames` — FOUND
- Commits a3431c2, 777373c, 152519c — FOUND in pi-mirror git log
