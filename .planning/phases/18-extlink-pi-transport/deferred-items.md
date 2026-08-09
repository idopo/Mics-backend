# Phase 18 — Deferred / Out-of-Scope Items

Items discovered during plan execution that are out of scope for the discovering plan
(pre-existing, not caused by the plan's own changes) and therefore logged here rather than
fixed, per the executor's scope-boundary rule.

## 18-02: `tests/test_mics_task_attrs.py`'s original 6 tests fail when the file is run
standalone, on this dev host, independent of plan 18-02's edit

**Found during:** Task 3 (extending `test_mics_task_attrs.py` with the `super().end()` AST pin).

**Symptom:** `cd /home/ido/pi-mirror && python3 -m pytest -q tests/test_mics_task_attrs.py`
reports 6 failed / 1 passed. All 6 failures are `AttributeError: module 'autopilot' has no
attribute 'tasks'` (or `ModuleNotFoundError`), raised from inside `unittest.mock.patch`'s /
`from autopilot.tasks.mics_task import mics_task`'s dotted import path.

**Root cause (pre-existing, confirmed unrelated to 18-02):** `autopilot/autopilot/__init__.py`
imports `autopilot.setup.setup_autopilot`, which imports `npyscreen` — not installed on this
dev host. This is the exact, already-documented Phase 18 constraint ("`import autopilot.*`
fails on the dev host — npyscreen missing", STATE.md). `test_mics_task_attrs.py` predates
Phase 18 (its own docstring says "Plan 01", a different/earlier phase) and its original 6 tests
were written to `patch("autopilot.tasks.mics_task....")` / `from autopilot.tasks.mics_task
import mics_task` — both dotted imports that trip the same `npyscreen` gap.

**Verified pre-existing, not introduced by this plan:** reproduced the identical 6 failures
against a temp copy of the file containing ONLY the original 6 tests (no `import ast`, no new
test added). Confirms plan 18-02's edit (adding `import ast` at module level and one new,
`autopilot`-free, AST-only test) did not cause or worsen this.

**Why not fixed here:** installing `npyscreen` on the dev host is exactly the kind of
environment change Phase 18's whole design (autopilot-free sibling modules, path-loaded by
`importlib.util.spec_from_file_location`) exists to avoid needing. Out of scope for a
Wave-0 test-contract plan; the file's original 6 tests and their fixture are owned by an
earlier phase.

**Impact on plan 18-02:** none on this plan's own acceptance gate — Task 3's `<verify>`/`<done>`
only require `python3 -m pytest -q tests/test_mics_task_attrs.py -k end` (1 passed, 6
deselected), which passes. The phase-level `<verification>` block's aspirational
`# all 7 pass, none skipped` comment does not hold on this dev host for a reason predating this
plan.

**Suggested follow-up (not actioned):** either install `npyscreen` on the dev host (scope
creep for a test-contract plan) or rewrite `make_mock_mics_task()` to avoid the dotted
`autopilot.tasks.mics_task` import (a behavior change to a pre-existing fixture, also out of
this plan's scope).

## 18-12: leftover live-verification DB debris from earlier plans' sessions, not cleaned up
as their own SUMMARY.md files claimed

**Found during:** Task 1, while checking `hardware_modules`/`hardware_libs`/`task_definitions`
for name collisions before registering this plan's own fixtures.

**Symptom:**
- `hardware_modules` id 25, name `DLC_CAM1`, class `BodyTracker`, `hardware_lib_id=104`
  (`plan18-13-bodytracker`/`body_tracker.py`) — not attached to toolkit 100 or any
  `pilot_hardware_config` row, so inert, but still occupying the `DLC_CAM1` name.
- ~25 duplicate `hardware_libs` rows named `oe_probe_extlink`/`weird_splat_signal`
  (ids 66/67/69/70/73/74/75/76/78/79/81/82/84/85/87/88/90/91/93/94/96/97/99/100/102/103/
  132/133/135/136/138/139/142/143/145/146/148/149/151/152/154/155/157/158/160/161) — these are
  `api/tests/test_hardware_libs_extlink.py`'s own fixture uploads
  (`test_extlink_upload_round_trip` / the signal-splat test), which run against the real dev DB
  on every `pytest` invocation and were never cleaned up by any prior plan.
- `task_definitions` id 344 (`Plan1813ExtlinkTaskDef-a7b03f0a`) on toolkit id 118
  (`Plan1813ExtlinkToolkit`) — `18-13-SUMMARY.md` states "All live-verification DB artifacts
  (test lib/module/toolkit/pilot-config/task-definition) deleted afterward," but this row (and
  presumably its toolkit/module/lib) is still present.

**Why not fixed here:** none of these collide with plan 18-12's own fixture names
(`ExtlinkDemoDealer`/`ExtlinkDemoControl`/`ExtlinkDemoSub`, libs `extlink_demo_dealer`/
`extlink_demo_control`/`extlink_demo_sub`, toolkit 100, task definition `extlink_demo`), all are
inert (unattached to any pilot config or toolkit's `hardware_module_ids`, so they cannot affect
a real session's preflight or dispatch), and deleting another plan's test artifacts is outside
this plan's own `files_modified`/scope. Logged so a future cleanup pass has a concrete list
instead of re-discovering it.

**Suggested follow-up (not actioned):** `test_hardware_libs_extlink.py`'s route-level tests
should either run against a transactional/rollback DB fixture or delete their own rows in a
`finally`; 18-13's own "deleted afterward" claim for task definition 344 should be re-verified
and corrected if the deletion never actually ran.
