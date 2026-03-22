---
status: testing
phase: 00-toolkit-variant-plan-all-phases
source: [REQUIREMENTS.md, ROADMAP.md, Phase 1 plans 01-04-05]
started: 2026-03-16T00:00:00Z
updated: 2026-03-16T00:00:00Z
---

## Current Test

number: 1
name: Phase 1 Plan 04 exposes semantic_hardware in HANDSHAKE payload
expected: |
  Plan 04 (pilot.py HANDSHAKE enrichment) includes semantic_hardware and
  semantic_hardware_renames as serialized fields in the HANDSHAKE task metadata.
  Phase 2's VAR-01/02 hw_hash computation will consume this data.
awaiting: user response

## Tests

### 1. Phase 1 Plan 04 exposes semantic_hardware in HANDSHAKE payload
expected: Plan 04 includes semantic_hardware and semantic_hardware_renames as serialized fields in the HANDSHAKE task metadata — the foundation Phase 2 VAR-01/02 hw_hash computation depends on
result: [pending]

### 2. hw_hash sort_keys consistency (Phase 1 → Phase 2 handoff)
expected: Phase 2 implementation note — Plan 04 serializes SEMANTIC_HARDWARE without explicit sort_keys. VAR-01's hw_hash formula specifies sort_keys=True. Phase 2 must apply sort_keys=True when hashing the stored semantic_hardware dict (not the raw wire payload) to ensure hash stability across Pi reboots.
result: [pending]

### 3. Phase 2 VAR-01–05 requirements correctly scoped
expected: VAR-01 (identity = name+hw_hash), VAR-02 (new hw_hash → new row), VAR-03 (toolkit_pilot_origins table), VAR-04 (GET /api/toolkits grouped), VAR-05 (diff endpoint) are all assigned Phase 2 in REQUIREMENTS.md and appear in ROADMAP.md Phase 2 row
result: [pending]

### 4. Phase 3 VAR-06 correctly scoped
expected: VAR-06 (explicit variant picker in FDA creation GUI) is assigned Phase 3 in REQUIREMENTS.md and appears in ROADMAP.md Phase 3 row — correct because the GUI is Phase 3 work
result: [pending]

### 5. Phase 4 VAR-07 correctly scoped
expected: VAR-07 (PATCH set-canonical + needs_migration flag) is assigned Phase 4 in REQUIREMENTS.md and appears in ROADMAP.md Phase 4 row — correct as a post-GUI merge workflow
result: [pending]

### 6. No VAR requirements affect Phase 1
expected: Phase 1 plans (01–06) have zero VAR requirement references — Phase 1 only needs to emit semantic_hardware in HANDSHAKE (covered by HOT-02), which it already does. No Phase 1 plan changes needed.
result: [pending]

### 7. task_definitions FK change is captured
expected: The plan specifies that task_definitions.toolkit_name VARCHAR changes to toolkit_id INTEGER FK in Phase 2 — this is a breaking schema change that Phase 2 plans must handle with IF NOT EXISTS / column migration, not a new table creation
result: [pending]

## Summary

total: 7
passed: 0
issues: 0
pending: 7
skipped: 0

## Gaps

[none yet]
