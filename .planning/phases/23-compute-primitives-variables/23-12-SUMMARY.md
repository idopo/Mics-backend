---
phase: 23-compute-primitives-variables
plan: 12
subsystem: backend+pi
tags: [fda-validation, mics_task, operand-namespace, rig-signoff]

# Dependency graph
requires:
  - phase: 23-compute-primitives-variables (plan 11)
    provides: "one read namespace (view) across every FDA-editor operand picker
      (CMP-20/21/22/23), frontend only"
provides:
  - "CMP-25: semantic hardware accepted as a condition-operand READ on a semantic
    toolkit, still rejected as a flag-action WRITE ref"
  - "CMP-24 (narrowed to 24b): _resolve_arg's view branch reads get_state() instead
    of .value, so a {\"view\": <hardware>} argument resolves instead of AttributeError-ing"
  - "Consolidated rig sign-off for CMP-20..25 recorded in 23-HARDWARE-VALIDATION.md"
affects: []

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Union at the call site, not inside the shared helper: CMP-25 widens
      valid_names at validate_compute_variables's own call site rather than
      inside _valid_flag_names, because that helper also gates three write-side
      rules (flag-action ref, output slot, key_template token) that must keep
      rejecting hardware names"
    - "Shipped != exercised: a deployed fix with no rig run that exercises its
      exact code path is recorded as 'deployed but not exercised', never as
      verified, in both SUMMARY.md and HARDWARE-VALIDATION.md"

key-files:
  created: []
  modified:
    - api/fda_validation.py
    - api/tests/test_task_definitions_validation.py
    - /home/ido/pi-mirror/autopilot/autopilot/tasks/mics_task.py
    - .planning/phases/23-compute-primitives-variables/23-HARDWARE-VALIDATION.md
    - .planning/phases/23-compute-primitives-variables/deferred-items.md
    - .planning/REQUIREMENTS.md

key-decisions:
  - "CMP-24 narrowed from three Pi edits to one (24b only) after Task 2 built and
    tested all three: 24a (trial_counter view-mirror) and 24c (type:\"view\" in a
    state body) were reverted before deployment at the user's direction — neither
    is required by the read-namespace change (CMP-20-23), and keeping the live-rig
    diff to the one edit CMP-23 actually depends on was preferred over bundling
    unrelated fixes into one deploy. Both are fully designed, tested, and captured
    as a pending GSD todo for a future one-line Pi-hygiene plan."
  - "CMP-24b and CMP-25 are DEPLOYED but NOT EXERCISED on the rig — task definition
    186 (the only one available for sign-off) never routes a {\"view\": hardware}
    value through _resolve_arg (its view actions never reach that branch as an
    argument), and its toolkit is backend-authored with semantic_hardware=null, so
    CMP-25's 422 path was never live. Recorded explicitly rather than inferred as
    proven from a green agent-side test suite."

# Metrics
duration: "~10min (bookkeeping only; tasks 1/2 previously executed, task 3 previously signed off)"
completed: 2026-08-05
---

# Phase 23 Plan 12: Pi + Backend `view` Invariants + Consolidated Sign-off Summary

**Semantic hardware is now a valid condition-operand read on the backend (CMP-25) and `_resolve_arg`'s view branch reads `get_state()` instead of `.value` on the Pi (CMP-24b), both deployed and merged — but neither has been exercised on the rig, and CMP-24a/24c were built, tested, then reverted before deployment per user direction.**

## Performance

- **Duration:** ~10 min (this bookkeeping pass only — Tasks 1 and 2 were executed and committed in an earlier session; Task 3's rig checkpoint was signed off separately on 2026-08-05)
- **Completed:** 2026-08-05
- **Tasks:** 3 (all previously done: 2 auto tasks committed, 1 checkpoint signed off)

## Accomplishments

- **CMP-25** (`e2e09ce`): `validate_compute_variables`'s `valid_names` now unions `toolkit.semantic_hardware` keys at the call site (`fda_validation.py:245`) — a semantic toolkit's hardware is a valid `view` condition operand, and the regression guard (`test_semantic_hardware_is_still_not_a_valid_flag_action_ref`) pins that `_valid_flag_names` itself is untouched, so the same hardware name still 422s as a `flag`-action write ref. Four TDD cases plus a fifth backend-authored regression case. Full backend suite green (352 passed, 1 skipped); `fda_validation.py` 449 lines (budget ≤460); `api/main.py` untouched.
- **CMP-24, narrowed to 24b** (`8f7a17c` build, `630d5b5` scope narrowing): `_resolve_arg`'s view branch in `/home/ido/pi-mirror/autopilot/autopilot/tasks/mics_task.py` now calls `self.view.view[key].get_state()` instead of reading `.value` — the one edit CMP-23's new `~ View` argument mode depends on, since a `Hardware` object has no `.value` and would `AttributeError` the moment a researcher passed semantic hardware through the new argument picker.
- **CMP-24a/24c descoped**: built with passing tests (AST invariants + behavioural cases in `test_load_fda_from_json.py`), then reverted before any Pi deploy at the user's explicit direction — neither is required by the read-namespace change. Both fully described with their fix and tests in `deferred-items.md`, and captured as the pending GSD todo `2026-08-05-reinstate-cmp-24a-and-cmp-24c-pi-view-mirror-fixes.md`.
- **Rig sign-off recorded** in `23-HARDWARE-VALIDATION.md` § "Plan 23-12 — operand-namespace sign-off (2026-08-05)": session run 551 (`completed`, no `error_type`), 92 ES docs under `subject: bp_s113_r551`, 20 state transitions, 5 trials.

## Task Commits

| Task | Name | Commit |
|---|---|---|
| 1 | CMP-25 — semantic hardware is a valid condition-operand read | `e2e09ce` (feat) |
| 2 | CMP-24 — Pi edits so `view` mirrors `flags` (built all three) | `8f7a17c` (fix) |
| — | Scope narrowing: revert 24a/24c before deploy, defer both | `630d5b5` (fix) |
| 3 | Rig checkpoint — deploy, USER-RUN Pi suite, editor sign-off | signed off 2026-08-05, appended to `23-HARDWARE-VALIDATION.md` (this commit) |
| — | Two GSD todos captured (Pi view-mirror fixes, stale bundle trap) | `e8e72c2` (docs) |

**This commit:** `docs(23-12): complete Pi + backend view-invariants plan` — SUMMARY.md, STATE.md, ROADMAP.md, REQUIREMENTS.md, and the already-modified `23-HARDWARE-VALIDATION.md`.

## Verified on the rig — session run 551

Task definition 186 (`source_less_toolkit FDA_tes_interuuppt`, toolkit 100, `is_backend_authored=true`, `semantic_hardware=null`). Pilot restarted by the user at ~12:21 UTC, after the 12:19 rsync.

| Requirement | Evidence |
|---|---|
| CMP-20 (read via `view`) | `{"view":"my_rand"}` drove transitions [3]/[4]: **7/7 draws routed to the matching branch** — 3 × `<0.5` → `play_led`, 4 × `>=0.5` → `trial_onset`. Both branches exercised. |
| CMP-20 (legacy escape, runtime) | Stored `{"flag":"pin_number"}` (if-condition) and `{"flag":"level"}` (argument) inside `trigger_assignments[0].actions[1]` survived a GUI resave **byte-identical** and executed correctly. |
| CMP-21 / CMP-22 / CMP-23 | Editor-verified (variables under "Flags & variables" in a state-body `if` condition; flag write ref and `~ View` argument mode both render correctly). |

## Deployed but NOT exercised on hardware — state this plainly

- **CMP-24b** (`_resolve_arg` → `get_state()`): on the Pi and live, but task 186 uses `view` only in transition conditions, which resolve through `_build_condition_operand`, and **never reach `_resolve_arg`**. No run has yet passed a `{"view": <hardware>}` operand as an *argument* — the exact case this fix exists for. This is not verified, not proven, and not exercised — it is deployed source only.
- **CMP-25** (semantic hardware in condition `valid_names`): backend deployed and unit-tested, but toolkit 100 is backend-authored with `semantic_hardware = null`, so the 422 path CMP-25 fixes was never on the code path this run took. Needs a semantic (non-backend-authored) toolkit to exercise on the rig.

Both gaps, and their smallest closing tests, are recorded verbatim in `23-HARDWARE-VALIDATION.md`'s sign-off section — this summary does not duplicate or soften that record.

## Descoped before deployment (user decision)

**CMP-24a** (mirror auto-created `trial_counter` into `self.view.view`) and **CMP-24c** (accept `type:"view"` in `_build_state_method`'s pre-validation loop) were built with passing tests, then reverted before deployment: neither is required by the read-namespace change, and the live-rig diff was kept to the single edit CMP-23 depends on. `REQUIREMENTS.md` CMP-24 and `deferred-items.md` reflect this, and both are captured as the pending GSD todo `2026-08-05-reinstate-cmp-24a-and-cmp-24c-pi-view-mirror-fixes.md`.

## Defect found during sign-off (environmental, not a phase defect)

`web_ui/static/react/` accumulated a full set of stale May 3 unhashed build artifacts (`main.js`, `TaskEditor.js`, ...). Vite's newer output is content-hashed, so a rebuild overwrites `main.js` but leaves old chunks servable (HTTP 200). Because `main.js` is unhashed and served with no `cache-control`, a cached `main.js` silently loaded months-old editor code — this is what made CMP-21 appear un-delivered until a hard refresh. Directory is gitignored build residue; filed as the pending GSD todo `2026-08-05-fix-stale-react-bundle-trap-in-web-ui-static-output.md`, not fixed here.

## Files Created/Modified

- `api/fda_validation.py` — CMP-25: `semantic_hw` hoisted and unioned into `valid_names` at the condition-operand call site only; `_valid_flag_names` untouched
- `api/tests/test_task_definitions_validation.py` — 4 `-k semantic_hardware` cases + 1 backend-authored regression case
- `/home/ido/pi-mirror/autopilot/autopilot/tasks/mics_task.py` — CMP-24b: `_resolve_arg`'s view branch calls `get_state()`; CMP-24a/24c reverted before deploy (nothing pushed to the Pi for those two)
- `.planning/phases/23-compute-primitives-variables/23-HARDWARE-VALIDATION.md` — sign-off section appended, authoritative rig evidence (this commit)
- `.planning/phases/23-compute-primitives-variables/deferred-items.md` — CMP-24a/24c descope recorded with fix + tests fully described
- `.planning/REQUIREMENTS.md` — CMP-24 requirement text narrowed to the one deployed edit (done in `630d5b5`); Traceability table CMP-24/CMP-25 rows updated (this commit)

## Decisions Made

- CMP-25 unions semantic hardware at the `validate_compute_variables` call site, not inside `_valid_flag_names` — that helper also gates three write-side rules (`flag`-action `ref`, output capture slot, `key_template` token) that all resolve against `self.flags` on the Pi; widening it would let a hardware name save cleanly as a write target and `KeyError` at FDA load.
- CMP-24 narrowed to one Pi edit (24b) after building and testing all three — 24a/24c reverted before deployment, per the user's explicit direction, to keep the live-rig diff to exactly what CMP-23 depends on. Confirmed by `difflib` against the running Pi: mirror vs live differed by exactly one hunk before deploy.
- The shipped-vs-exercised distinction for CMP-24b and CMP-25 is recorded explicitly rather than left implicit — a later reader of a green Pi suite or a passing backend test run must not infer rig coverage that does not exist.

## Deviations from Plan

None in this bookkeeping pass — Tasks 1 and 2 executed exactly as planned in an earlier session (see their commits above), and Task 3's checkpoint was signed off per the plan's own `<how-to-verify>` steps. This SUMMARY and the STATE.md/ROADMAP.md/REQUIREMENTS.md updates are pure bookkeeping closing out the plan; no production code was written or touched in this pass.

## Issues Encountered

None beyond what is already documented above (the stale-bundle defect, filed as a todo, not a phase defect).

## User Setup Required

None further. The Pi file was deployed **by the user** via the two rsync commands specified in the plan's Task 3 `<how-to-verify>` (the `mics_task.py` push and the two test-file pushes to `~/Apps/mice_interactive_home_cage/tests/`), and the pilot was restarted by the user at ~12:21 UTC — both already done before this summary was written.

## Next Phase Readiness

Phase 23 is now **12/12 plans done**. Two pending GSD todos carry forward real, described work: reinstating CMP-24a/24c (one rig deploy, fixes and tests already designed) and fixing the stale React bundle trap (unhashed `main.js`, no `cache-control`). Neither blocks any other phase. CMP-24b and CMP-25 remain **deployed but rig-unexercised** — the smallest closing tests for each are named in `23-HARDWARE-VALIDATION.md`'s sign-off section for whoever next touches a semantic toolkit or an argument-mode `view` action on task 186.

---
*Phase: 23-compute-primitives-variables*
*Completed: 2026-08-05*

## Self-Check: PASSED

All three referenced commits (`e2e09ce`, `8f7a17c`, `630d5b5`) and the two todo files
(`2026-08-05-reinstate-cmp-24a-and-cmp-24c-pi-view-mirror-fixes.md`,
`2026-08-05-fix-stale-react-bundle-trap-in-web-ui-static-output.md`) found on disk/in git log.
