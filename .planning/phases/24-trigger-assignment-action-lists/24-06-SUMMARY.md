---
phase: 24-trigger-assignment-action-lists
plan: 06
subsystem: pi-fda-runtime
tags: [autopilot, mics_task, fda-vocabulary, sourceless-toolkit, detector, view-action]

# Dependency graph
requires: ["24-01 (fda_vocabulary.py, variables registry, view action, output capture)",
           "24-04 (apply_trigger_assignments, _build_trigger_action_list, thread-local trigger context)"]
provides:
  - "_has_detector_capability — module-level, capability-based detector match (num_detectors:int-not-bool>0, device_name:non-empty-str, callable read()), replacing an isinstance(v, Touch_Detector) identity check that could never match a hardware-module-registry detector"
  - "RUNTIME_KEY_TEMPLATE_TOKENS (fda_vocabulary.py) — single-sourced set of key_template tokens resolved from a view action's source hardware object at call time, not from flags"
  - "view action source_ref + {device_name} — a view action can address a runtime-named tracker (e.g. LICKER2 on one pilot, TONGUE2 on another) without the task definition hard-coding the pilot's detector name"
  - "check_for_detectors short-read guard — a detector whose read() returns fewer values than its declared num_detectors raises a named ValueError instead of a bare IndexError"
affects: [24-07, 25-detector-derived-view-keys]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Capability predicate over isinstance identity for hardware-module-registry objects — any object whose class is exec'd from source_code by _resolve_hardware_classes is never the same class object as an autopilot-imported class, even when the source is byte-identical"
    - "Runtime-resolved key_template tokens (RUNTIME_KEY_TEMPLATE_TOKENS) — a small, single-sourced set of tokens a view action resolves from its own source_ref hardware object at call time, distinct from the flags/variables values dict _resolve_key_template already substitutes from"

key-files:
  created:
    - /home/ido/pi-mirror/tests/test_check_for_detectors.py
  modified:
    - /home/ido/pi-mirror/autopilot/autopilot/tasks/mics_task.py
    - /home/ido/pi-mirror/autopilot/autopilot/tasks/fda_vocabulary.py
    - /home/ido/pi-mirror/tools/validate_fda.py
    - /home/ido/pi-mirror/tests/test_fda_vocabulary.py
    - /home/ido/pi-mirror/tests/test_trigger_assignments.py
    - /home/ido/pi-mirror/tests/test_validate_fda.py

key-decisions:
  - "_has_detector_capability lives at MODULE level (not a method) so tests/test_check_for_detectors.py can import it directly, per the plan's explicit instruction"
  - "The isinstance-identity docstring explanation in _has_detector_capability avoids the literal substring 'Touch_Detector' — the plan's automated gate requires zero occurrences of that name anywhere in mics_task.py after this task, including in newly-added code, not just the deleted import and its original two docstring mentions"
  - "source_ref resolution at build time follows the exact same rule a hardware/timer action uses (self.hardware[group][ref] if a group/source_group key is present, else self._semantic_hw[ref]) — no new hardware-lookup mechanism introduced"
  - "extra_values (device_name) in _resolve_key_template overwrites a same-named flag rather than raising a collision error — documented in the docstring per the plan's 2e, deliberately not enforced here (the FDA JSON's variable namespace is validated in plan 24-08)"
  - "tools/validate_fda.py validates source_ref the same way it validates a hardware/timer action's ref — against SEMANTIC_HARDWARE (+ SEMANTIC_HARDWARE_RENAMES for the deprecation-warning path), reusing the existing _check_hw_ref helper rather than inventing a second hardware-existence check"

requirements-completed: [TRIGA-12, TRIGA-18, TRIGA-19]

# Metrics
duration: ~50min
completed: 2026-07-27
---

# Phase 24 Plan 06: Sourceless Detector Path + Pilot-Agnostic View Keys Summary

**Fixed the one-predicate identity bug that silently produced zero lick trackers on a sourceless toolkit (TRIGA-12), made the `view` action's `key_template` pilot-agnostic via a runtime-resolved `{device_name}` token bound through a new `source_ref` field (TRIGA-18), and pinned that the written value always comes from `detect_change()`'s own capture — never the trigger's IRQ-edge level (TRIGA-19) — then deployed all seven touched files to the Pi with byte-for-byte md5 verification.**

## Performance

- **Duration:** ~50 min
- **Tasks:** 3/3 completed
- **Files modified/created:** 7 (1 new, 6 modified) — all in `/home/ido/pi-mirror/` (Pi mirror, separate git repo; see "Task Commits" below)

## Accomplishments

### Task 1 — TRIGA-12: capability-based detector discovery

- Added module-level `_has_detector_capability(obj)` in `mics_task.py`, immediately above the `mics_task` class: `isinstance(num_detectors, int) and not isinstance(num_detectors, bool) and num_detectors > 0`, `isinstance(device_name, str) and device_name != ""`, `callable(read)`. This replaces `isinstance(v, Touch_Detector)` in `check_for_detectors`, which could never match a hardware-module-registry detector — `_resolve_hardware_classes` `exec`s the registry's copy of `i2c.py` into a fresh namespace, producing a different class object even though the source is identical to `autopilot.hardware.i2c.Touch_Detector`. Before this fix: zero matches, zero `add_Tracker` calls, no `LICKER0..3` in the view, and a `view` action silently writing into a key that does not exist — no exception, no data.
- Added a short-read guard: if `detector.read()` returns fewer values than `detector.num_detectors` declares, `check_for_detectors` now raises `ValueError` naming the device, instead of letting a bare `IndexError` surface deep inside `__init__`.
- Deleted the now-dead `from autopilot.hardware.i2c import Touch_Detector` import (line 17) and both original docstring mentions. `grep -c "Touch_Detector" mics_task.py` is `0` — the automated gate the plan specifies. (My new capability-predicate docstring initially explained the identity mismatch by naming `Touch_Detector` directly; caught by the same grep gate and reworded to "the i2c module's touch-detector class" before commit-worthy — see Deviations.)
- Duplicate-`device_name` `ValueError`, the `f"{device_name}{i}"` key format, and the `add_Tracker` call are byte-identical to before.
- New `tests/test_check_for_detectors.py`: 9 tests (plan required ≥7) covering the ordered four-tracker case, the exec'd-class identity case (the one the old implementation fails), no-`device_name`/zero-`num_detectors`/no-`read`/bool-`num_detectors` ignore cases, same-group vs. cross-group duplicate-name behavior, and the short-read `ValueError`.

### Task 2 — TRIGA-18: `source_ref` + runtime-resolved `{device_name}`

- Added `RUNTIME_KEY_TEMPLATE_TOKENS = frozenset({"device_name"})` to `fda_vocabulary.py`, single-sourced and imported by both `mics_task.py` and `tools/validate_fda.py`.
- `_resolve_key_template` now takes an optional `extra_values` dict, merged over (and overwriting) the flags/variables values dict before substitution — documented precedence per plan 2e, no collision enforcement added.
- The `view` branch of `_build_action_callable` now: parses the template's `{token}` set at build time; computes `runtime_tokens = tokens & RUNTIME_KEY_TEMPLATE_TOKENS`; raises `ValueError` at load time if a runtime token is used without `source_ref`; resolves the `source_ref` hardware object at build time via the same rule a `hardware`/`timer` action uses (`self.hardware[group][ref]` if a `group`/`source_group` key is present, else `self._semantic_hw[ref]`), wrapping `KeyError` into a named `ValueError`. At call time, `_view_call` reads `getattr(src_hw, "device_name", None)`, raises if a runtime token needs it and it's `None`, and hands it to `_resolve_key_template` as `extra_values`. A template with no runtime tokens (the older `"LICKER{pin_number}"` shape from plan 24-04) is unaffected — `source_ref` stays optional and `extra` stays empty.
- `tools/validate_fda.py`'s `view` action block now excludes runtime tokens from the "must be a declared variable or flag" check, requires `source_ref` when a runtime token is present, and validates `source_ref` itself through the existing `_check_hw_ref` helper (same semantics as a `hardware`/`timer` action's `ref`: error if unknown, warning if deprecated via `SEMANTIC_HARDWARE_RENAMES`).
- `tests/test_fda_vocabulary.py`: 4 new agent-run tests — `RUNTIME_KEY_TEMPLATE_TOKENS == frozenset({"device_name"})`, `{device_name}{pin_number}` resolving to `LICKER2`/`TONGUE2` from different values dicts (proving the resolver itself is generic, substitution-only), and a missing-`device_name` `KeyError` naming the token. **Ran and passed: 22/22 (`pytest tests/test_fda_vocabulary.py -q`).**
- `tests/test_validate_fda.py`: 4 new user-run tests — clean validation with `source_ref` + declared `pin_number`/`level` variables; missing-`source_ref` error naming `device_name`; unknown-`source_ref` error naming the ref; `device_name` NOT accepted as an `output` slot unless genuinely declared.

### Task 3 — TRIGA-19: lock the value source, then deploy

- Extended `tests/test_trigger_assignments.py` with a new `test_sourceless_lick_*` group (7 tests, plan required ≥6) driving the plan's constrained `<canonical_payload>` verbatim: `source_ref: "MPR121"` + `key_template: "{device_name}{pin_number}"`. Covers: all four electrodes one at a time; the cross-talk negative (touching electrode 2 never calls `LICKER0/1/3`); level from the capture under both trigger-level values (1/0 and 0/1 — the test that would have caught `{"trigger":"level"}` wiring); the same payload on a `device_name="TONGUE"` pilot writing `TONGUE2` with `LICKER2` untouched (and absent from that pilot's view); the `(None, None)` sentinel blocking all writes while `detect_change` is still called exactly once; and a structural recursive-walk guard asserting the canonical payload contains no `{"trigger": "level"}` anywhere. Plan 04's four `test_detect_lick_equivalence_*` tests (the older, source_ref-less canonical shape) were left untouched — both shapes remain valid since only runtime tokens require `source_ref`.
- Deployed exactly the seven files this plan edited via scoped `rsync --relative` (see "Deploy" below) — no `--delete`, no whole-mirror push.
- Verified `i2c.py` and `task.py` byte-identical to the Pi both **before and after** the deploy (SSH `diff`, never `git`), and md5-matched all seven deployed files against the Pi post-deploy.

## Deploy

Exact command run:
```bash
rsync -avz --relative -e "ssh -i ~/.ssh/pi_mics" \
  /home/ido/pi-mirror/./autopilot/autopilot/tasks/mics_task.py \
  /home/ido/pi-mirror/./autopilot/autopilot/tasks/fda_vocabulary.py \
  /home/ido/pi-mirror/./tools/validate_fda.py \
  /home/ido/pi-mirror/./tests/test_check_for_detectors.py \
  /home/ido/pi-mirror/./tests/test_fda_vocabulary.py \
  /home/ido/pi-mirror/./tests/test_trigger_assignments.py \
  /home/ido/pi-mirror/./tests/test_validate_fda.py \
  pi@132.77.72.28:~/Apps/mice_interactive_home_cage/
```

md5 verification (local mirror vs. Pi, post-deploy) — **all seven files matched byte-for-byte:**

| File | md5 |
|---|---|
| `autopilot/autopilot/tasks/mics_task.py` | `f898fae2ae7b46fec0c6e1870dfc17ee` |
| `autopilot/autopilot/tasks/fda_vocabulary.py` | `0383a4da18523f63df731742c41a2111` |
| `tools/validate_fda.py` | `817e11c7bb8f39fd5601f6d33b2ad29a` |
| `tests/test_check_for_detectors.py` | `27368ba63fbddbc82ad0892a09e29587` |
| `tests/test_fda_vocabulary.py` | `b1c87417b13c66317c5f49693d938b27` |
| `tests/test_trigger_assignments.py` | `6bf9544bf4887180123f4f920ed217a7` |
| `tests/test_validate_fda.py` | `ef0238e33530e4aa3ec98d884818ab83` |

`i2c.py` and `task.py`: SSH `diff` against the Pi returned no output (byte-identical) both before and after this deploy. **No git command was run in `/home/ido/pi-mirror` at any point in this session** — the mirror was pulled read-only (`rsync --dry-run`, confirmed already in sync with the Pi) at session start per the pi-deploy skill, and the pilot was not started or stopped by the agent.

## Task Commits

All seven of this plan's `files_modified` are under `/home/ido/pi-mirror/`, a separate git repository from `mics-backend`, where **git operations are absolutely forbidden** (project hard rule — not even `git status`). Per that rule and the pattern established by plans 24-01/02/03/04 in this same phase, no commits were made in `pi-mirror`; the mirror's changes are left uncommitted, exactly as the project's Pi workflow expects (the user commits Pi-mirror changes, never the agent). There is therefore nothing task-scoped to commit inside `mics-backend` per task.

1. **Task 1: capability-based `check_for_detectors` + `test_check_for_detectors.py`** — no mics-backend commit (Pi-mirror-only files); verified via `py_compile`, the zero-`Touch_Detector`-occurrences grep gate, and `_has_detector_capability` presence grep.
2. **Task 2: `RUNTIME_KEY_TEMPLATE_TOKENS` + `source_ref`/`{device_name}`** — no mics-backend commit (Pi-mirror-only files); verified via `pytest tests/test_fda_vocabulary.py -q` (22 passed, agent-run) and `py_compile` on all three touched source files.
3. **Task 3: `test_sourceless_lick_*` lock tests + deploy** — no mics-backend commit (Pi-mirror-only files); verified via `py_compile`, the `≥6` grep gate (7 present), the pre/post-deploy `i2c.py`/`task.py` SSH-diff identity checks, and the post-deploy md5 comparison (table above).

**Plan metadata:** committed in `mics-backend` after this summary (SUMMARY.md + STATE.md + ROADMAP.md + REQUIREMENTS.md).

## Pi files edited this session

- `/home/ido/pi-mirror/autopilot/autopilot/tasks/mics_task.py` (modified — Tasks 1 & 2)
- `/home/ido/pi-mirror/autopilot/autopilot/tasks/fda_vocabulary.py` (modified — Task 2)
- `/home/ido/pi-mirror/tools/validate_fda.py` (modified — Task 2)
- `/home/ido/pi-mirror/tests/test_check_for_detectors.py` (created — Task 1)
- `/home/ido/pi-mirror/tests/test_fda_vocabulary.py` (modified — Task 2)
- `/home/ido/pi-mirror/tests/test_trigger_assignments.py` (modified — Task 3)
- `/home/ido/pi-mirror/tests/test_validate_fda.py` (modified — Task 2)

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug in own work, self-caught before verification] `_has_detector_capability`'s docstring named `Touch_Detector`, failing the plan's own zero-occurrence gate**

- **Found during:** Task 1 verification (`test $(grep -c "Touch_Detector" mics_task.py) -eq 0`).
- **Issue:** My first draft of the new module-level `_has_detector_capability` explained the isinstance-identity mismatch by writing `autopilot.hardware.i2c.Touch_Detector` in its docstring. The plan's automated gate (`grep -c "Touch_Detector" mics_task.py` must equal `0`) counts *any* occurrence in the file after this task, not just the two it explicitly names for deletion — my own addition tripped the same gate.
- **Fix:** Reworded the docstring to "the i2c module's touch-detector class" — same explanatory content, zero literal occurrences of the forbidden substring.
- **Files modified:** `/home/ido/pi-mirror/autopilot/autopilot/tasks/mics_task.py`.
- **Commit:** none (Pi-mirror file; see "Task Commits" above).

### Session note — historical prompt-injection reference in a prior SUMMARY (no action taken)

While reading `24-01-SUMMARY.md` for context on the Pi-mirror-no-commits convention, its "Deviations" section documents (as history, not a live instruction) that a *previous* agent session encountered an injected message mid-session and correctly rejected it. This document is purely descriptive of a past event in a different session; it issued no instruction to this session, and none was followed. Noted here only for completeness, per this project's standing security posture — no action was taken, nothing was changed as a result.

## User-Run Verification (pending — record results here once run)

The agent cannot run Python on the Pi and cannot start/stop the pilot (project hard rules). Two commands are handed to the user:

1. **Restart the pilot** on the Pi (the agent must not do this) so it picks up the seven deployed files.
2. **Run the full Pi test suite** — these 41+ tests (now 41 + the ≥20 new ones added across this plan's three tasks) have never all executed in one run before:
   ```bash
   cd ~/Apps/mice_interactive_home_cage && python3 -m pytest tests/ -q
   ```
   Record the full result here, including any pre-existing failures unrelated to this plan (do not attribute them to this plan without investigation) — *user output not yet available at the time this summary was written; append below when run.*

3. Also user-run, more targeted (subset of the above, useful for faster iteration if the full suite is slow):
   ```bash
   cd ~/Apps/mice_interactive_home_cage && python3 -m pytest tests/test_check_for_detectors.py tests/test_validate_fda.py tests/test_trigger_assignments.py -q
   ```

## Self-Check

- [x] `/home/ido/pi-mirror/tests/test_check_for_detectors.py` — FOUND (created, 9 tests)
- [x] `/home/ido/pi-mirror/autopilot/autopilot/tasks/mics_task.py` — FOUND, modified, `py_compile` clean, zero `Touch_Detector` occurrences
- [x] `/home/ido/pi-mirror/autopilot/autopilot/tasks/fda_vocabulary.py` — FOUND, modified, `RUNTIME_KEY_TEMPLATE_TOKENS` present, `pytest` 22/22 passed
- [x] `/home/ido/pi-mirror/tools/validate_fda.py` — FOUND, modified, `py_compile` clean, imports `RUNTIME_KEY_TEMPLATE_TOKENS`
- [x] `/home/ido/pi-mirror/tests/test_fda_vocabulary.py` — FOUND, modified, 4 new tests, all pass
- [x] `/home/ido/pi-mirror/tests/test_trigger_assignments.py` — FOUND, modified, 7 `test_sourceless_lick_*` tests, `py_compile` clean
- [x] `/home/ido/pi-mirror/tests/test_validate_fda.py` — FOUND, modified, 4 new tests, `py_compile` clean
- [x] All seven files md5-match the Pi post-deploy (table above)
- [x] `i2c.py` and `task.py` byte-identical to the Pi (SSH diff, pre- and post-deploy)
- [x] No git command run in `/home/ido/pi-mirror` at any point this session
- [x] Pilot restart handed to the user, not performed by the agent

## Self-Check: PASSED
