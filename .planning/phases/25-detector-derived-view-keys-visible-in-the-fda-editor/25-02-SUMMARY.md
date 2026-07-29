---
phase: 25-detector-derived-view-keys-visible-in-the-fda-editor
plan: 02
subsystem: pi-runtime
tags: [autopilot, fda, detector, trigger, mics_task, task-py, fda_vocabulary]

# Dependency graph
requires:
  - phase: 24-trigger-assignment-action-lists
    provides: "check_for_detectors capability matching (TRIGA-12), view action source_ref/{device_name} resolution (TRIGA-18), fda_vocabulary.py as the Pi's single-source vocabulary module"
provides:
  - "detector_view_keys / detector_channel_range / detector_channel_key in fda_vocabulary.py — the Pi's half of the shared golden-table derivation (byte-identical to the backend's api/detector_keys.py, plan 01)"
  - "check_for_detectors honouring a configurable first_channel, fixing the silent channel-4 data loss from runs 480/481 (DVK-09)"
  - "execute_trigger's except KeyError narrowed to the self.triggers[pin] lookup, with a total per-callback error path (_report_trigger_error: error log + TRIGGER_ACTION_ERROR event) (DVK-10)"
  - "parse_view_detector_operand + a view_detector branch in _build_condition_operand, resolving {\"view_detector\": {\"ref\": ..., \"channel\": ...}} to a pilot's real view key ONCE at build time (DVK-11)"
affects: ["25-06-deploy-and-rig-proof (owns rsync + user-run pytest + rig checkpoint for these files)"]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Shared pure-function vocabulary in fda_vocabulary.py (stdlib-only) so dev-host pytest can exercise Pi logic that autopilot.tasks.mics_task/task cannot import here"
    - "Build-time resolution over per-evaluation resolution for anything whose inputs cannot change within a run (view_detector channel is fixed; contrast with the view action's per-call {pin_number})"
    - "Two-phase error containment: a pure parser (parse_view_detector_operand) raises for shape errors agent-testable on the dev host; the branch that resolves against live hardware/view state raises separately, USER-RUN only"

key-files:
  created:
    - /home/ido/pi-mirror/tests/test_detector_view_keys.py
    - /home/ido/pi-mirror/tests/test_execute_trigger_guard.py
    - /home/ido/pi-mirror/tests/test_view_detector_operand.py
  modified:
    - /home/ido/pi-mirror/autopilot/autopilot/tasks/fda_vocabulary.py
    - /home/ido/pi-mirror/autopilot/autopilot/tasks/mics_task.py
    - /home/ido/pi-mirror/autopilot/autopilot/tasks/task.py
    - /home/ido/pi-mirror/tests/test_check_for_detectors.py

key-decisions:
  - "No git commit was made for any pi-mirror file. pi-mirror is its own git repository owned exclusively by the user (pi_rules #1: 'NEVER run git in /home/ido/pi-mirror — not status, not anything'), so this plan's per-task commit protocol applies only to files inside the mics-backend repo. All seven pi-mirror edits are local, uncommitted working-tree changes; the user commits pi-mirror on their own terms."
  - "Task 1's fda_vocabulary.py additions and Task 4's parse_view_detector_operand were written in the same file but landed as logically separate task steps (matching the plan's task boundaries) even though there is no git history to separate them by — recorded here since 'per-task commit' has no git artifact to point to in this plan."
  - "check_for_detectors: kept int(raw_first) wrapped in a broad except (TypeError, ValueError) that funnels into the same first<0 ValueError branch, rather than a bespoke coercion helper — mirrors the existing _coerce_hw_value tolerance elsewhere in the file without duplicating it (first_channel is read once per detector, not hot-path)."

patterns-established:
  - "detector_channel_key(device_name, channel) is the single construction site both check_for_detectors (Task 2) and _build_condition_operand's view_detector branch (Task 4) call — the tracker name and the operand's resolved key can never drift apart because they share one function."

requirements-completed: [DVK-01, DVK-09, DVK-10, DVK-11]

# Metrics
duration: 20min
completed: 2026-07-29
---

# Phase 25 Plan 02: Detector-Derived View Keys — Pi Runtime (DVK-09/10/11) Summary

**Three Pi-side fixes landed together in `/home/ido/pi-mirror`: `check_for_detectors` now honours a declarable `first_channel` (stopping the channel-4 data loss that cost runs 480/481 nine real lick events), `execute_trigger`'s `except KeyError` is narrowed so a genuine action-list failure surfaces as a named error instead of "No valid trigger", and a new `{"view_detector": {"ref": ..., "channel": ...}}` condition operand resolves to a pilot's real tracker key at task-build time — keeping stored FDA JSON pilot-agnostic.**

## Performance

- **Duration:** 20 min
- **Started:** 2026-07-29T10:51:00Z
- **Completed:** 2026-07-29T11:11:36Z
- **Tasks:** 4
- **Files modified:** 7 (all in `/home/ido/pi-mirror`; none in the mics-backend git repo)

## Accomplishments
- `fda_vocabulary.py` gained `detector_channel_range`, `detector_view_keys`, `detector_channel_key` (the Pi's half of the one shared golden-table derivation, DVK-01) and `parse_view_detector_operand` (the shape parser for DVK-11's condition operand) — all stdlib-only, so they run under `pytest` on this dev host even though `autopilot` itself cannot be imported here.
- `check_for_detectors` reads `first_channel` from `prefs.HARDWARE[group][module_name]` (the same dict `_merge_prefs_hardware` writes from the backend's `prefs_hardware`), defaults to `0` when absent (byte-identical to today's behaviour for every existing config), and seeds each tracker from `curr_vals[raw_channel_index]` — never a shifted index. A rig wired `first_channel: 1` now produces `LICKER1…LICKER4` with `LICKER4` correctly seeded from `curr_vals[4]`.
- `execute_trigger`'s `try/except KeyError` now wraps only `self.triggers[pin]`. Each callback runs in its own `try/except Exception`, reported via a new `_report_trigger_error` helper (error log naming the exception + a `TRIGGER_ACTION_ERROR` event) whose own body is wrapped in `try/except Exception: pass` so a dead `event_dispatcher` or a raising `dispatch_event` can never escape into `process_queue`.
- `_build_condition_operand` gained a `view_detector` branch, tested before the plain `view` branch, that resolves `{"ref": ..., "channel": ...}` against `self._semantic_hw` (or `self.hardware[group][ref]` when `group` is present) exactly the way the `view` **action**'s `source_ref` already does, turning an unknown ref, a hardware object with no `device_name`, or a channel absent from `self.view.view` into a `ValueError` at task load — never a bare `KeyError` mid-session, never a silent no-op.

## Task Commits

No git commits were made — see "Deviations from Plan" below. All work is uncommitted in the pi-mirror working tree, per pi_rules #1 (git in `/home/ido/pi-mirror` is forbidden, including `status`). The tasks below were executed and verified in order, each gated on `py_compile` + the dev-host `pytest` suite passing before moving to the next:

1. **Task 1: `detector_view_keys` + `detector_channel_key` in `fda_vocabulary.py`** — no commit (pi-mirror is user-owned git)
2. **Task 2: `check_for_detectors` honours `first_channel` (DVK-09)** — no commit
3. **Task 3: narrow `execute_trigger`'s `except KeyError` (DVK-10)** — no commit
4. **Task 4: `_build_condition_operand` resolves `view_detector` at build time (DVK-11)** — no commit

**Plan metadata:** this SUMMARY.md, STATE.md, and ROADMAP.md are committed in the mics-backend repo (final commit below) — the only git activity this plan performs.

## Files Created/Modified

All paths under `/home/ido/pi-mirror` (outside the mics-backend git repo):

- `autopilot/autopilot/tasks/fda_vocabulary.py` — added `_as_int`, `detector_channel_range`, `detector_view_keys`, `detector_channel_key` (Task 1), `parse_view_detector_operand` (Task 4)
- `autopilot/autopilot/tasks/mics_task.py` — `check_for_detectors` rewritten to honour `first_channel` (Task 2); `_build_condition_operand` gained the `view_detector` branch (Task 4); import line extended both times. Diff confirmed limited to those two methods plus the import — no other method touched.
- `autopilot/autopilot/tasks/task.py` — `execute_trigger`'s guard narrowed, new `_report_trigger_error` helper added, `Event` added to the `Events` import (Task 3). `process_queue` untouched (STATE.md Outstanding item 4 stays open, as instructed).
- `tests/test_detector_view_keys.py` — new. `GOLDEN_CASES` (byte-identical to the backend's `api/tests/test_detector_keys.py`), `detector_channel_key`/`detector_view_keys` cases including the invariant that the two agree over every golden case, and `parse_view_detector_operand`'s shape cases. **Agent-verified**, all green on this host.
- `tests/test_fda_vocabulary.py` — unchanged; re-run as a regression gate each task.
- `tests/test_check_for_detectors.py` — extended with DVK-09 cases (no-`first_channel` byte-identical behaviour, `first_channel: 1` shifted seeding, short-read `ValueError`, `first_channel: 0` explicit, invalid `first_channel` values, module absent from `prefs.HARDWARE`). USER-RUN on the Pi (imports `autopilot.tasks.mics_task`).
- `tests/test_execute_trigger_guard.py` — new. Missing-trigger debug log unchanged, a raising callback reported (not mislabeled), non-`KeyError` exceptions also reported, one raising callback doesn't stop the rest, `execute_trigger` always returns normally, the error path survives both a raising `dispatch_event` and a `None` `event_dispatcher`, and all four signature-dispatch branches unchanged. USER-RUN on the Pi (imports `autopilot.tasks.task`, which pulls in `pigpio`/`tables`).
- `tests/test_view_detector_operand.py` — new. Live-state read, the pilot-agnostic same-operand-different-pilot test (DVK-11's entire point), the four build-time failure modes (missing channel, unknown ref, no `device_name`, malformed shape), "building does not call `get_value`", and regression coverage for the four pre-existing operand forms plus a bare literal. USER-RUN on the Pi.

## Decisions Made

- **No pi-mirror git commits, by design.** pi_rules #1 in the plan and the executor's own critical constraints both forbid any git command in `/home/ido/pi-mirror`, "not even status" — that repo is the user's, not this plan's. The task_commit_protocol's per-task commit requirement is satisfied only for files inside the mics-backend repo (this SUMMARY, STATE.md, ROADMAP.md, REQUIREMENTS.md), committed once at the end.
- **`check_for_detectors`'s `first_channel` coercion mirrors the existing `_coerce_hw_value` tolerance** (accept a numeric string) without extracting a shared helper — it runs once per detector at `check_for_detectors` time, not per-tick, so the minor duplication with `_coerce_hw_value`'s string-to-number logic was judged not worth a new shared function for two call sites with different failure semantics (one silently converts, the other must raise).
- **`Q4` from the plan's decisions section is recorded as-is**: `tools/validate_fda.py` gains no `view_detector` branch. Its `_validate_condition_operand` already has no `view` branch at all and its transition pass never sees GUI-emitted `{left, op, right}` conditions, so `view_detector` is no worse off than `view` was. The real enforcement point remains the backend 422 (phase 25 plan 01, task 4). This is a known limitation of `tools/validate_fda.py`, not a gap introduced by this plan.

## Deviations from Plan

**None affecting code.** One process deviation, required by the plan's own pi_rules and the executor's critical constraints:

**1. [Process — not a Rule 1-4 deviation] No git commit for any pi-mirror file**
- **Found during:** Task 1, before the first edit (Step 0's mirror-identity proof)
- **Issue:** The generic executor task_commit_protocol calls for a git commit after each task. `/home/ido/pi-mirror` is its own git repository, and both the plan's `pi_rules` ("NEVER run git in `/home/ido/pi-mirror` — not status, not anything") and this execution's critical_constraints explicitly forbid any git operation there, including read-only ones.
- **Resolution:** All four tasks were implemented, verified (`py_compile` + dev-host `pytest`), and left as uncommitted working-tree changes in pi-mirror. This SUMMARY documents per-task completion in lieu of commit hashes. The mics-backend repo's own commit (SUMMARY.md/STATE.md/ROADMAP.md/REQUIREMENTS.md) is the only git activity this plan performs.
- **Impact on plan:** None on correctness or scope — plan 06 (deploy) already expects to work from the pi-mirror working tree, not from pi-mirror git history.

## Issues Encountered

None. Step 0's four-file mirror-identity proof (`fda_vocabulary.py`, `mics_task.py`, `task.py`, `i2c.py`, mirror vs Pi) printed no diffs before any edit was made, confirmed again after all edits for `i2c.py` (still byte-identical) and for the full diff scope of `mics_task.py` and `task.py` (limited to exactly the methods/import lines the plan specified).

## User Setup Required

None - no external service configuration required. **No deployment and no pilot restart in this plan** (plan 06 owns that). The pi-mirror edits are local only; nothing was pushed to the Pi.

## Next Phase Readiness

**Files to deploy, when plan 06 runs (rsync from `/home/ido/pi-mirror`, never `--delete`, never the whole mirror):**

```
autopilot/autopilot/tasks/fda_vocabulary.py
autopilot/autopilot/tasks/mics_task.py
autopilot/autopilot/tasks/task.py
tests/test_detector_view_keys.py
tests/test_check_for_detectors.py
tests/test_execute_trigger_guard.py
tests/test_view_detector_operand.py
```

(`tests/test_fda_vocabulary.py` is unchanged and does not need redeploying.)

- Plan 06 must run the USER-RUN suites on the Pi: `tests/test_check_for_detectors.py`, `tests/test_execute_trigger_guard.py`, `tests/test_view_detector_operand.py` (all three import modules that cannot load on this dev host).
- Plan 06's rig checkpoint should specifically assert channel 4 lands in `LICKER4` (DVK-09's regression target) and that a transition declared as "MPR121 — channel 2" fires correctly, then re-fires unchanged after a `device_name` rename (DVK-11's pilot-agnostic proof).
- **Known limitation, recorded per plan instruction:** `tools/validate_fda.py` gains no `view_detector` branch — it already has no `view` branch and never sees GUI-emitted `{left, op, right}` conditions, so this is not a new gap. Enforcement lives in the backend 422 (25-01 task 4).
- Backend counterpart (`api/detector_keys.py`, `api/fda_validation.py::validate_condition_operands`, plan 01) must stay in sync with this file's `GOLDEN_CASES` and `parse_view_detector_operand` shape rules — both are duplicated by design and called out with cross-references in code comments on both sides.

---
*Phase: 25-detector-derived-view-keys-visible-in-the-fda-editor*
*Completed: 2026-07-29*

## Self-Check: PASSED

All 7 pi-mirror files (3 modified, 4 created/extended — `test_check_for_detectors.py` extended,
`test_detector_view_keys.py`/`test_execute_trigger_guard.py`/`test_view_detector_operand.py`
created) confirmed present on disk. This SUMMARY.md confirmed present on disk. No commit
hashes to verify — no git commits were made to `/home/ido/pi-mirror` per pi_rules #1 (see
"Deviations from Plan"). `python3 -m py_compile` and the dev-host `pytest` suite
(`tests/test_detector_view_keys.py tests/test_fda_vocabulary.py`, 64 passed) were re-run
immediately before writing this summary and are the fresh evidence for this plan's claims.
