---
created: 2026-08-05T12:39:26.069Z
title: Reinstate CMP-24a and CMP-24c Pi view-mirror fixes
area: pi
files:
  - ~/pi-mirror/autopilot/autopilot/tasks/mics_task.py:1042 (CMP-24a)
  - ~/pi-mirror/autopilot/autopilot/tasks/mics_task.py:901 (CMP-24c)
  - .planning/phases/23-compute-primitives-variables/deferred-items.md
---

## Problem

Two one-line holes in the Pi's `flag` ↔ `view` namespace mirror. **Do them together — it is one
rig deploy for both.**

**CMP-24a — auto-created `trial_counter` is not mirrored into the view.**
`load_fda_from_json` (~line 1042) auto-creates a `Trial_Tracker` for backward compat when a
toolkit's `FLAGS` omits one, and registers it in `self.flags` **only**. Every other registration
puts the same object in both dicts — `init_flags` (:339-340) and the variables loop
(:1060-1061). This is the single remaining hole in the mirror, and the whole read-namespace
equivalence (`{"view": X}` ≡ `{"flag": X}`, delivered in phase 23 as CMP-20) rests on that
mirror being total.

Impact is narrow but real: the backend's `_valid_flag_names` (`api/fda_validation.py`)
explicitly whitelists `trial_counter`, so `{"view":"trial_counter"}` passes save-time validation
and then raises `KeyError` inside the transition lambda mid-run. Only reachable via hand-authored
JSON or an already-stored definition — the auto-create branch fires exactly when the toolkit does
*not* declare `trial_counter`, in which case it is absent from `toolkit.flags` and the GUI never
offers it in the view picker either.

**CMP-24c — `_build_state_method` rejects `type:"view"` actions.**
The pre-validation loop's catch-all (`elif atype not in ("timer", "if")`, ~line 901) raises
`ValueError: unknown action type 'view'`. So a `view` action works *inside an `if` branch* (that
path does not recurse through this loop) but raises at FDA load when placed directly in a state
body. `_build_action_callable` supports `view` fully — this loop is the only thing rejecting it.
Originally logged as an unowned deferral by plan 23-04.

**Both were built with passing tests during phase 23-12, then deliberately reverted before
deployment** (user decision, 2026-08-05): neither is required by the read-namespace UI change
(CMP-20–23), and the live-rig diff was kept to the single edit CMP-23 actually depends on
(CMP-24b). Nothing was ever pushed to the Pi for either.

## Solution

Both fixes, their rationale, and the test designs are preserved in full in
`.planning/phases/23-compute-primitives-variables/deferred-items.md` (items 1 and 2). Summary:

- **CMP-24a:** assign the auto-created tracker to a local, then register it in both dicts,
  mirroring `init_flags`. Tests that existed and passed: two AST checks in
  `tests/test_view_namespace_invariants.py` (including an equivalence pin that both dicts get the
  *same* object, not two that can drift) plus two behavioural cases in
  `tests/test_load_fda_from_json.py`. Note two pre-existing tests
  (`test_variables_key_absent_no_change`, `test_variables_empty_dict_no_change`) assert
  `view.view == {}` and must be updated in place — the fix changes exactly that invariant.
- **CMP-24c:** add `"view"` to the `elif atype not in (...)` tuple and update the error message's
  expected-types list. Tests: one AST check plus a behavioural `test_view_action_in_state_body_loads`.
  Keep `test_unknown_action_type_in_state_body_still_raises` — the catch-all is widened, not removed.

**Pi rules apply (ABSOLUTE):** edit `~/pi-mirror/` only. Never run `git`, never start/stop the
pilot, never run Python on the Pi, no `rsync --delete`, no whole-mirror sync. End at handing the
user the rsync + restart commands. Pi log files are empty by design.

Useful gotcha from phase 23: `diff` in this shell is intercepted and rewritten, which made a
1-line change render as a 761-line rewrite. Use `python3` + `difflib` to compare mirror vs live Pi.
