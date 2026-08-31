---
phase: 35-deeplabcut-keypoint-likelihood-integration
plan: 06
subsystem: hardware-libs
tags: [deeplabcut, extlink, hardware-lib, fda-editor, runbook, documentation]

# Dependency graph
requires:
  - phase: 35-deeplabcut-keypoint-likelihood-integration (plan 02)
    provides: "the clock-consistent liveness_hook snippet this fixture's lib generates verbatim"
  - phase: 35-deeplabcut-keypoint-likelihood-integration (plan 03)
    provides: "dlc-link-generate / dlc_link.config_read, run against the real project's transcribed config.yaml"
  - phase: 35-deeplabcut-keypoint-likelihood-integration (plan 04)
    provides: "dlc_link.signal_map/processor/live — the adapter plan 35-07 will point at this fixture's uploaded lib"
provides:
  - "A standing DLC hardware-lib fixture (lib 243, module 73, toolkit 157, pilot 3 config row 41, task definition 626) travelling the ordinary hardware-lib pipeline with no new backend endpoint"
  - "35-FIXTURE-INVENTORY.md: every created id, exact payload, the five live-verified substrate citations proving dlc_cam1.alive is pure inbound liveness, and a reverse-order teardown procedure"
  - "The picker payload proven verbatim (GET /api/toolkits/by-name/dlc_demo) before any human opens a browser, plus the D-36 empty-picker mechanism demonstrated live and the save-gate 422 exercised for this module"
  - "dlc_link/RUNBOOK.md: the researcher-facing path from a working DeepLabCut model to an FDA transition authored in the browser, naming the six-step ordering obstacle explicitly"
affects: [35-07, 35-08, 35-09]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "New toolkit for a new external-hardware module, never linked onto a toolkit any real task definition already dispatches on — config rows are matched by module NAME against a toolkit's module set, so a shared toolkit would put a socket-binding module on every existing definition's path"
    - "Content-based stale-bundle check (grep the served bundle for the feature string) instead of a raw file-mtime comparison, when a fresh rebuild is out of scope for the plan"

key-files:
  created:
    - .planning/phases/35-deeplabcut-keypoint-likelihood-integration/35-FIXTURE-INVENTORY.md
    - .planning/phases/35-deeplabcut-keypoint-likelihood-integration/fixtures/dlc_cam1_lib.py
    - .planning/phases/35-deeplabcut-keypoint-likelihood-integration/fixtures/dlc_cam1_signals.py
    - dlc_link/RUNBOOK.md
  modified:
    - dlc_link/README.md

key-decisions:
  - "Cloned toolkit 100's SHAPE (states=[], locked_state_source=null, no flags/params_schema) rather than its hardware_module_ids: the demo task's FDA has no entry_actions and references no hardware method, so hardware_module_ids for the new toolkit 157 is just [the new dlc_cam1 module] — the endpoint's own attach_compute_defaults then auto-added module 24 (ComputeOps), which is standard for every backend-authored toolkit and not something this plan requested or could opt out of."
  - "Generated the lib from plan 35-03's transcribed config.yaml fixture (dlc_link/tests/fixtures/dlc3_multianimal_config.yaml), not the real project file — the real config.yaml lives on the Windows vision box and is unreachable from this dev host (confirmed this session: no SMB mount resolves). Recorded the transcription's own sha256 in the inventory rather than presenting it as the real file's hash."
  - "Verified D-36's ordering constraint by running derive_extlink_keys inside the mics_api Docker container (which has sqlalchemy installed) rather than stubbing sqlalchemy on the dev host, since this check specifically needed the REAL function against a REAL fetched config row, not merely an importable module."
  - "Ruled out the stale-React-bundle hazard by grepping the LIVE served bundle for the extlink_signals feature string, rather than a raw file-mtime diff or a fresh npm install/build — node_modules is not installed in this worktree and installing it is out of this plan's scope (same posture as the sqlalchemy-install exclusion in plan 35-03)."

requirements-completed: [DLC-01, DLC-08, DLC-13]

# Metrics
duration: ~40min
completed: 2026-08-31
---

# Phase 35 Plan 06: DLC Fixture Stand-Up and Researcher Runbook Summary

**Stood up a standing DLC hardware-lib fixture (lib 243 / module 73 / toolkit 157 / task
definition 626) through the ordinary hardware-lib pipeline with the gated FDA transition
deliberately absent, proved the FDA editor's picker has real `dlc_cam1.*` signals to offer
before any browser opens, and wrote `dlc_link/RUNBOOK.md` naming the six-step backend ordering
obstacle explicitly rather than hiding it.**

## Performance

- **Duration:** ~40 min
- **Completed:** 2026-08-31T12:42:01Z
- **Tasks:** 3/3 completed
- **Files modified:** 4 created, 1 modified

## Accomplishments

- Generated the demo lib with the real `dlc-link-generate` CLI against plan 35-03's transcribed
  `config.yaml` fixture: `LED_on`/`LED_off` (both `uniquebodyparts`, coordinates enabled on
  `LED_on` only) → exactly 4 signals (`led_on_likelihood`, `led_on_x`, `led_on_y`,
  `led_off_likelihood`), 40 msg/s against the ~60 msg/s envelope, `POSE_ORDER_SOURCE =
  'config-declared-UNVERIFIED'` recorded and flagged PROVISIONAL on plan 35-07's D-42 probe.
- Created every row through existing endpoints, in order: hardware lib 243/version 184 →
  hardware module 73 (`dlc_cam1`) → toolkit 157 (`dlc_demo`, a NEW toolkit so toolkit 100's real
  task definitions 186/434 keep an unchanged dispatch path — verified before and after: linked
  lib set `{7,8,9,10,11,45,177}` unchanged) → pilot 3's `dlc_cam1` config row (port 5601,
  `required: false`, no port/source_id collision with row 33's `demo`/5599) → task definition
  626 with `wait`/`armed`/`fired` states and only the unconditional `fired -> wait` transition —
  no `dlc_cam1.*` view key anywhere, no `INC_TRIAL_COUNTER` — → pinned the lib version via
  `PUT /api/task-definitions/626/hw-lib-versions/243`.
- Verified all five substrate citations live against `/home/ido/mics_core/` this session
  (`external_hardware_binding.py:141`'s `recompute_alive` conjunction, `bind_egress` always
  building an inert `EgressWorker`, `send()` as the only enqueue path, `_egress_failed` starting
  `False`, and `host` being read by nothing outside `sub_connect`), and grepped the uploaded
  lib's stored source for zero egress markers — `dlc_cam1.alive` is pure inbound liveness by
  construction, recorded in the inventory with the exact citations.
- Proved the picker's data path end to end BEFORE any browser opens: recorded
  `GET /api/toolkits/by-name/dlc_demo`'s `extlink_signals` block verbatim (all 5 keys, pilot-3
  provenance, no conflict), demonstrated `derive_extlink_keys` returning `[]` with `source_id`
  removed and the full list with it present (run inside `mics_api`, against the real fetched
  config, no stub), exercised the save gate's 422 for an undeclared `dlc_cam1.made_up_signal`
  view key and restored the task definition byte-identical, and ruled out the stale-bundle
  hazard by finding `extlink_signals` present in the LIVE container's served
  `TaskEditor-BQgUsRGT.js`.
- Wrote `dlc_link/RUNBOOK.md`: 17 numbered steps (the 3-step read-only-copy procedure, the
  8-step vision-box workflow, the 6-step backend path) each carrying a write-footprint
  annotation (21 total), a section stating `<source_id>.alive` is a conjunction and why the DLC
  lib specifically collapses it to inbound-only, a section on what can/cannot be declared
  (per-individual signals technically unavailable live, given `identity: false` +
  `stitch_tracklets`, not a preference), and "The obstacle, named" section stating the
  silently-empty-picker mechanism and both deferred fixes without implementing either. Zero
  occurrences of the word "latency" in any form; every rig instruction phrased as an
  instruction, no claimed rig result.

## Task Commits

Each task was committed atomically:

1. **Task 1: Generate the demo lib and create every row the pipeline needs** - `728edf4` (feat)
2. **Task 2: Prove the editor picker has real signals to offer** - `7bb10fa` (docs)
3. **Task 3: Write the runbook, and name the obstacle** - `d3296d2` (docs)

**Plan metadata:** (this commit, docs)

## Files Created/Modified

- `.planning/phases/35-deeplabcut-keypoint-likelihood-integration/35-FIXTURE-INVENTORY.md` -
  every created id/payload, the 5 live substrate citations, the picker payload, the D-36/422
  demonstrations, teardown procedure
- `.planning/phases/35-deeplabcut-keypoint-likelihood-integration/fixtures/dlc_cam1_lib.py` -
  the exact generated lib source uploaded as hardware lib 243/version 184
- `.planning/phases/35-deeplabcut-keypoint-likelihood-integration/fixtures/dlc_cam1_signals.py` -
  the paired signal map (`POSE_ORDER`, `POSE_ORDER_SOURCE`, `LIB_SHA256`, etc.)
- `dlc_link/RUNBOOK.md` - the full researcher-facing runbook (new)
- `dlc_link/README.md` - links the runbook, states the PyPI-published half's one-line install

## Decisions Made

See `key-decisions` in the frontmatter above (toolkit cloning shape, transcribed-config
provenance, running `derive_extlink_keys` inside the API container, and the content-based
stale-bundle check).

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] The task definition's own description text defeated the plan's own `INC_TRIAL_COUNTER` substring check**
- **Found during:** Task 1's automated verification
- **Issue:** The first-drafted `fda_json.description` field stated, in prose, that the file
  does not use `INC_TRIAL_COUNTER` — which itself contains the literal substring the plan's
  acceptance criterion greps for (`fda_json` must contain zero occurrences of
  `INC_TRIAL_COUNTER`), the same class of self-referential bug plan 35-03 hit with `@command`
  in a comment.
- **Fix:** Reworded to "no trial-graduation special action" — same meaning, no longer matching.
- **Files modified:** none on disk (task_definitions row 626, via `PUT
  /api/task-definitions/626`)
- **Verification:** `curl .../api/task-definitions/626` → `fda_json` contains zero occurrences
  of `INC_TRIAL_COUNTER` and zero of `dlc_cam1.`
- **Committed in:** `728edf4` (Task 1 commit)

**2. [Rule 1 - Bug] The runbook's own "no latency claims" sentence defeated its own latency-word check**
- **Found during:** Task 3's automated verification
- **Issue:** The opening paragraph stated "No sentence below claims a latency..." — the word
  "latency" itself trips the acceptance criterion requiring zero occurrences of "latency" in
  any form anywhere in the document, again the identical self-referential-text class of bug.
- **Fix:** Reworded to "No sentence below claims a wire-timing number..." — same meaning, no
  longer matching.
- **Files modified:** `dlc_link/RUNBOOK.md`
- **Verification:** `grep -i latenc dlc_link/RUNBOOK.md` → no matches; full automated verify
  script (17 numbered steps, 21 write-footprint matches, all 24 required substrings present)
  passes.
- **Committed in:** `d3296d2` (Task 3 commit)

---

**Total deviations:** 2 auto-fixed (both Rule 1 — a literal-text requirement and this plan's
own descriptive prose about that requirement collided, the third occurrence of this exact class
of bug across this phase's plans 35-03/35-04/35-06)
**Impact on plan:** No scope creep. Both fixes are narrow rewording changes with no change to
structural content (the fda_json's states/transitions were correct from the first draft; the
runbook's substantive claims were correct from the first draft).

## Issues Encountered

- The plan's literal Task 1 verify snippet (`assert len(sids)==len(set(sids))` over EVERY
  pilot-3 config row) has a pre-existing quirk unrelated to this plan: most rows on pilot 3
  carry no `source_id` key at all, so they all collapse to a shared `None` in the set and the
  literal assertion as written would "fail" on this live system regardless of any change this
  plan made. Verified the REAL invariant by hand instead (no two NON-NULL source_ids collide:
  `{"demo", "dlc_cam1"}`, distinct) and recorded the discrepancy in the inventory rather than
  silently reporting a false pass.
- `git status --porcelain` under `/home/ido/pi-mirror/` was not checked this session (this plan
  never reads or writes anything under `pi-mirror/` — only `mics_core/`, confirmed clean via
  `git -C /home/ido/mics_core status --porcelain`).
- `docker compose exec -T api python -m pytest -q tests/` (the backend 452-pass baseline) was
  not run from this worktree — the `mics_api` container visible via `docker ps` belongs to the
  main checkout's compose project, the same limitation plans 35-01/35-03/35-04 recorded. This
  plan makes zero changes to `api/` (`git status --porcelain api/` is empty), and the live
  `mics_api`/`mics_web_ui` containers WERE queried directly (read-only for verification, plus
  the intentional writes documented in the fixture inventory) via `docker exec`/`curl` against
  `localhost:8000`, which is how every database row and picker payload in this summary was
  actually verified.

## User Setup Required

None - no external service configuration required. This plan performs no install; all backend
rows were created through existing, already-deployed API endpoints.

## Next Phase Readiness

- Plan 35-07 has a standing fixture to point its `dlc-link-live`/`--probe-pose` run at: lib 243,
  module 73, toolkit 157, task definition 626, pilot 3 config row 41 (port 5601, `dlc_cam1`,
  `required: false` — run the pilot's session BEFORE starting the sender).
- The lib is explicitly PROVISIONAL: plan 35-07's `--probe-pose` result is the authority on
  `POSE_ORDER`/`POSE_ORDER_SOURCE` — if it disagrees with `config-declared-UNVERIFIED`,
  regenerate with `--pose-order`/`--pose-order-file` and re-upload before any rig observation
  built on this lib means anything.
- The demo transition's threshold is NOT chosen yet (deliberately) — plan 35-07 measures the
  real likelihood distribution of `led_on_likelihood`/`led_off_likelihood` on a real video
  before any threshold is picked, per D-41.
- The gated `wait -> armed -> fired` transition is NOT authored yet (deliberately) — that is
  plan 35-07's first real human click through the FDA editor's picker, the whole reason this
  plan built everything up to but not including it.
- `dlc_link/RUNBOOK.md` is ready to hand to the researcher performing plan 35-07/35-08's
  rig-side steps.

## Self-Check: PASSED

- FOUND: `.planning/phases/35-deeplabcut-keypoint-likelihood-integration/35-FIXTURE-INVENTORY.md`
- FOUND: `.planning/phases/35-deeplabcut-keypoint-likelihood-integration/fixtures/dlc_cam1_lib.py`
- FOUND: `.planning/phases/35-deeplabcut-keypoint-likelihood-integration/fixtures/dlc_cam1_signals.py`
- FOUND: `dlc_link/RUNBOOK.md`
- FOUND: commit `728edf4` (Task 1)
- FOUND: commit `7bb10fa` (Task 2)
- FOUND: commit `d3296d2` (Task 3)

---
*Phase: 35-deeplabcut-keypoint-likelihood-integration*
*Completed: 2026-08-31*
