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

**STILL OPEN — descoped from Plan 23-12 (2026-08-05).** Was briefly fixed as CMP-24c, then
reverted before deployment at the user's direction: the read-namespace change (CMP-20–23) is a
UI-layer change, and this is an unrelated pre-existing bug about `view` *actions*, not `view`
*operands*. Bundling it would have widened a live-rig deploy for a bug nobody was asking about.

The fix is still the one described above (add `"view"` to the `elif atype not in (...)` tuple).
It was verified to work — source edit, an AST test, and a behavioural test all existed and passed
before being reverted. Reinstating it is a one-line source change plus re-adding those two tests.
Nothing on the Pi was ever touched.

**Suggested owner (unchanged):** whichever future plan next touches `_build_state_method`, or a
dedicated small Pi-hygiene plan alongside item 2 below.

## Plan 23-12 (descoped 2026-08-05)

### 2. Auto-created `trial_counter` is registered in `self.flags` but not `self.view.view`

**Found during:** Phase 23 plan 23-11/23-12 design discussion, while establishing whether
`{"view": X}` is a total mirror of `{"flag": X}`.

**Issue:** `mics_task.py` `load_fda_from_json` (~line 1042) auto-creates a `Trial_Tracker` for
backward compat when a toolkit's `FLAGS` omits one, and registers it in `self.flags` **only** —
unlike `init_flags` (`:339-340`) and the variables loop (`:1060-1061`), which both register the
same object in `self.flags` AND `self.view.view`. It is the single hole in the flags↔view mirror.

**Impact (narrow).** The backend's `_valid_flag_names` (`api/fda_validation.py`) explicitly
whitelists `trial_counter`, so `{"view": "trial_counter"}` saves cleanly and then raises
`KeyError` inside the transition lambda mid-run. Only reachable via hand-authored JSON or an
already-stored definition: the auto-create branch fires exactly when the toolkit does *not*
declare `trial_counter`, in which case it is absent from `toolkit.flags` and the GUI never offers
it in the view picker either.

**Why not fixed in 23-12:** not required by the read-namespace UI change (CMP-20–23). Fixed and
then reverted before deployment at the user's direction, to keep the live-rig diff to the single
edit CMP-23 actually depends on. Nothing was ever pushed to the Pi.

**Fix:** assign the auto-created tracker to a local, then register it in both dicts — mirroring
`init_flags`. Tests existed and passed (`test_view_namespace_invariants.py` AST checks plus two
behavioural cases in `test_load_fda_from_json.py`); all were removed with the revert.

**Suggested owner:** a small Pi-hygiene plan together with item 1 above — both are one-line
`mics_task.py` fixes with tests already designed, and doing them together means one rig deploy.
