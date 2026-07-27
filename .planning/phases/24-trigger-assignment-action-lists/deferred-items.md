# Deferred Items — Phase 24

## From Plan 04 (2026-07-27)

### `tools/validate_fda.py` `cmd_rename_hw_ref` still targets the legacy `config.hardware_ref` shape

**Found during:** Task 3 (single-sourcing the action vocabulary in `validate_fda.py`).

**Issue:** `cmd_rename_hw_ref`'s `TRIGGER_ASSIGNMENTS_SQL` bulk-rename statement still does
`assignment->'config'->>'hardware_ref'`. Since Plan 04 drops the `handler`/`config` shape
entirely (a trigger assignment is now `(trigger_name, actions)` only), this statement is a
silent no-op against any current-format `trigger_assignments` row — it will simply never
match, because `config` no longer exists on those rows. It still works correctly against
any lingering pre-Phase-24 rows that literally have `config.hardware_ref` (there was exactly
one such orphan row, id 185, referenced by no protocol per 24-CONTEXT.md).

**Why out of scope for Plan 04:** The plan's Task 3 action items (3a–3f) and `<files_modified>`
scope only the `validate()` function and its `_validate_*` helpers — not the separate
`cmd_rename_hw_ref` bulk-rename subcommand, which has its own SQL and is not part of the
validation path this plan retires the handler enum from.

**Consequence if left unaddressed:** A researcher renaming a semantic hardware ref via
`validate_fda.py rename-hw-ref` will NOT have that rename propagated into any
`actions[*].ref` inside a `trigger_assignments` entry — only `entry_actions[*].ref` (state
bodies) get renamed by the existing `ENTRY_ACTIONS_SQL` statement, which was never scoped to
walk `trigger_assignments[*].actions` in the first place.

**Suggested fix (future plan):** Extend `ENTRY_ACTIONS_SQL` (or add a third statement) to walk
`fda_json->'trigger_assignments'->*->'actions'` the same way it walks
`states->*->'entry_actions'`, and drop the now-dead `TRIGGER_ASSIGNMENTS_SQL` config-based
statement. Low urgency: no current toolkit uses trigger-assignment hardware refs in production
yet (TRIGA-11's rig proof, Plan 07, is the first real usage).
