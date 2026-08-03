# Deferred Items — Phase 23

Out-of-scope discoveries logged here per the executor's SCOPE BOUNDARY rule: found during a
task's changes, but not caused by them, so not auto-fixed.

## Plan 23-04

### 1. `_build_state_method`'s entry_actions validate loop never learned about `type:"view"`

**Found during:** Task 3, while tracing whether `_build_state_method`'s pre-validation loop
(`autopilot/autopilot/tasks/mics_task.py`, ~line 868) would accept a `compute` action inside a
state's `entry_actions`.

**Issue:** The loop has an explicit branch per action type (`method`, `hardware`, `flag`,
`special`) plus a catch-all that silently passes `timer` and `if` through unchecked, and raises
`ValueError: unknown action type '<atype>'` for anything else. `view` (added in Phase 24,
TRIGA-18) was never added to this loop — a `type:"view"` action placed directly in a state's
`entry_actions` would raise here before ever reaching `_build_action_callable`, which fully
supports it. (Trigger actions bypass this loop entirely via `apply_trigger_assignments` →
`_build_trigger_action_list` → `_build_action_callable`, which is presumably why this has never
surfaced — every existing `view` action test exercises it through a trigger, not a state body.)

**Not fixed here:** `compute` (this plan's own action type) WAS added to this same loop — see
"Deviations from Plan" in `23-04-SUMMARY.md` — because leaving it out would have silently broken
this plan's own CMP-03 must-have. `view`'s pre-existing gap is unrelated to that change and out
of this plan's scope per the SCOPE BOUNDARY rule.

**Suggested owner:** Whichever future plan next touches `_build_state_method` or does a Phase-24
cleanup pass. One-line fix: add `"view"` to the trailing `elif atype not in (...)` tuple (or give
it its own branch calling `_build_action_callable`'s existing key_template/source_ref checks
early, for a load-time error instead of relying on `_build_action_callable` to raise later).
