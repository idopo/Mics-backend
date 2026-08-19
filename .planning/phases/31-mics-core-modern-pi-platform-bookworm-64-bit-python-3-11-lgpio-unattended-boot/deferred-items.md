# Phase 31 — Deferred Items

Out-of-scope discoveries logged during execution, not fixed (per plan executor scope boundary:
only auto-fix issues directly caused by the current task's changes).

## From Plan 01 (2026-08-19)

1. **`REQUIREMENTS.md`'s PLAT-26 row description is stale.** It reads "a recording fake `lgpio`
   with a signature-contract test" — a holdover from before the 2026-08-17 scope revision
   (`31-REVISED-SCOPE.md`) withdrew the lgpio migration. Plan 01 actually delivers a recording fake
   of **pigpio**'s notification stream (`tests/fakes/fake_pigpio.py`), matching the plan file
   itself and every other PLAT-2x row in the same table, all of which were already updated for the
   revision. `REQUIREMENTS.md` also has no checkbox column on this table (same structural gap noted
   throughout `STATE.md` for CMP-*/DVK-*/HYG-*), so `gsd-tools requirements mark-complete PLAT-26`
   reports `not_found` rather than a false completion — not a regression, but worth fixing in one
   pass whenever `REQUIREMENTS.md` next gets a general edit.

2. **`tests/test_compute_ops.py` and `tests/test_log_action_values.py` stay in `conftest.py`'s
   `collect_ignore`, but their inline comments ("for exactly the npyscreen reason") are now
   half-stale.** `npyscreen` itself is resolved by `requirements-dev.txt`; both files are still
   blocked, but by the pigpio chain (`Event_Dispatcher.py:3`), not npyscreen. Plan 01 Task 3's own
   instructions reserve editing this block for plan 02 ("leave the existing `collect_ignore` block
   and its explanatory comment intact — plan 02 revisits it"), so the comment was left as written.
