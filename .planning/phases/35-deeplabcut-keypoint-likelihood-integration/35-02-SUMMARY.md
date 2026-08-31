---
phase: 35-deeplabcut-keypoint-likelihood-integration
plan: 02
subsystem: hardware-libs
tags: [liveness, extlink, mics-link-sdk, clock-domain, hardware-lib, phase-31-defect]

# Dependency graph
requires:
  - phase: 34-mics-link-sdk-client-package
    provides: "Phase 34 observation B (INCONCLUSIVE) — hardware lib 177 v2's DIAGNOSTIC OVERRIDE liveness_hook hardcoded True, so SDK-05 is unproven on hardware"
provides:
  - "35-LIVENESS-FINDINGS.md separating the 2026-08-09 undiagnosed liveness fault (Defect A, pi-mirror) from the 2026-08-24 cross-clock subtraction (Defect B, mics_core-only)"
  - "A canonical, reviewable liveness_hook (fixtures/liveness_hook_snippet.py) that compares like-for-like against the ingress clock source"
  - "A candidate hardware lib 177 version 3 (fixtures/extlink_demo_v3.py) with mechanically-proven parity to version 2, plus a byte-identical version 2 rollback copy"
  - "Ready-to-copy PUT/rollback API calls for plan 35-09 to upload v3 and repin task definition 434"
affects: [35-03-generator, 35-09-rig-liveness-fix]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "liveness_hook clock-consistency workaround: read current time from the same clock source ingress stamped from, not the caller-supplied wall-clock now_ms"
    - "extlink metadata parity proof via ast-based extract_extlink_metadata equality, not source-diff inspection"

key-files:
  created:
    - .planning/phases/35-deeplabcut-keypoint-likelihood-integration/35-LIVENESS-FINDINGS.md
    - .planning/phases/35-deeplabcut-keypoint-likelihood-integration/fixtures/liveness_hook_snippet.py
    - .planning/phases/35-deeplabcut-keypoint-likelihood-integration/fixtures/extlink_demo_v3.py
    - .planning/phases/35-deeplabcut-keypoint-likelihood-integration/fixtures/extlink_demo_v2_rollback.py
  modified: []

key-decisions:
  - "The override predates the cross-clock subtraction by 15 days and the mics_core tree by 10 days (verified this session against live hardware_lib_versions timestamps and mics_core git history), so Defect A and Defect B are recorded as unrelated and neither is used as evidence for the other."
  - "Defect A (the original 2026-08-09 liveness fault) is left explicitly UNDIAGNOSED with A1 (egress probe) recorded as confirmed-by-documentation-and-timeline but not experimentally reproduced; no cause is claimed."
  - "Defect B (the cross-clock subtraction) is framed as a Phase 31 violation of the one-clock invariant, owned by Phase 31/18 — not a sanctioned F7 exemption. The in-source comment's exemption claim is disproved against final_checks.py itself."
  - "The liveness_hook fix is a lib-level workaround for Defect B only; it is explicitly documented as possibly not fixing Defect A, so a failing quiet test in plan 35-09 is not treated as a plan failure."

requirements-completed: [DLC-06]

# Metrics
duration: ~40min
completed: 2026-08-31
---

# Phase 35 Plan 02: Liveness Defect Separation and Candidate Lib 177 v3 Summary

**Separated an undiagnosed 2026-08-09 liveness fault from an unrelated 2026-08-24 cross-clock bug by verified timeline, authored a clock-consistent `liveness_hook` workaround, and produced a candidate hardware lib 177 v3 with mechanically-proven parity to v2 — all offline, no rig or API writes.**

## Performance

- **Duration:** ~40 min
- **Completed:** 2026-08-31T11:20:08Z
- **Tasks:** 2 completed
- **Files modified:** 4 created, 0 modified

## Accomplishments

- Re-verified all five dated claims in the timeline live against the running API
  (`hardware_lib_versions` `created_at` for lib 177 v1/v2), the actual `egress_listener.py`
  process on this host (PID 3086567, still running, started `Sun Aug 9 11:15:24 2026`), and
  `mics_core`'s git history (first commit and commit `1f35782`) — all five held exactly as the
  plan described, closing the causal-confusion error from the plan's first pass.
- Disproved the in-source `"Phase 31 Plan 10's F7 exempts this site by name"` claim directly
  against `final_checks.py`'s `F7_CLOSURE` (nine files, `external_hardware_binding.py` absent),
  `F7_EXEMPTIONS` (one entry, the ingress fallback), and the `f7_one_clock` checker body (which
  never opens a file outside the closure) — with exact `path:line` citations.
- Authored `liveness_hook_snippet.py`: a class-level hook that reads current time from
  `external_hardware_ingress.now_ms()` (the same clock ingress stamped from) instead of the
  caller-supplied wall-clock `now_ms`, wrapped in `try`/`except` falling back to the substrate
  default, with a one-shot diagnostic log and an explicit comment that it fixes Defect B and
  does not address Defect A.
- Produced `extlink_demo_v3.py` (candidate lib 177 v3) and `extlink_demo_v2_rollback.py`
  (byte-identical to the live v2 source), and mechanically proved
  `extract_extlink_metadata(v2) == extract_extlink_metadata(v3)` — the only difference is the
  undecorated `liveness_hook` method, invisible to the extractor.
- Recorded ready-to-copy `PUT`/rollback API calls for plan 35-09, including task definition
  434's current `hw_lib_versions` JSON and lib 177's current `active_version_id` (137), all
  fetched read-only this session.

## Task Commits

Each task was committed atomically:

1. **Task 1: Confirm the clock-domain analysis and author the canonical liveness hook** - `5f96114` (docs)
2. **Task 2: Author candidate lib 177 version 3 and prove it differs from version 2 in exactly one method** - `4dd6cb1` (feat)

_Note: `35-LIVENESS-FINDINGS.md` was authored complete (sections 1-7, covering both tasks) in
Task 1's commit since both tasks write to the same document; Task 2's commit adds only the two
fixture files it is responsible for (`extlink_demo_v3.py`, `extlink_demo_v2_rollback.py`)._

## Files Created/Modified

- `.planning/phases/35-deeplabcut-keypoint-likelihood-integration/35-LIVENESS-FINDINGS.md` - Timeline, Defect A (undiagnosed), Defect B (verified in source), A-vs-B discriminator, the fix's scope, empty results table for 35-09, the Phase 31/18-owned defect writeup, and Task 2's parity proof + ready-to-copy API calls
- `.planning/phases/35-deeplabcut-keypoint-likelihood-integration/fixtures/liveness_hook_snippet.py` - Canonical clock-consistent `liveness_hook`, plan 35-03's generator emits this verbatim
- `.planning/phases/35-deeplabcut-keypoint-likelihood-integration/fixtures/extlink_demo_v3.py` - Candidate lib 177 v3, ready for plan 35-09 to upload
- `.planning/phases/35-deeplabcut-keypoint-likelihood-integration/fixtures/extlink_demo_v2_rollback.py` - Byte-identical copy of lib 177's live v2 source, for plan 35-09's rollback

## Decisions Made

- The override's docstring is never cited as evidence for the clock diagnosis anywhere in the
  finding — every quotation of it is immediately paired with the timeline that refutes that
  inference.
- The demo fixture's dependency on `.125:5597` is recorded as deliberate and correct (confirmed
  by lib 177's own module docstring, fetched live); the only defect is the un-removed override.
- Pilot 1 (`132.77.72.28`, confirmed live as `pilot_raspberry_lior`, which also carries a `demo`
  hardware row) is recorded as the available, not-currently-planned A-vs-B discriminator,
  cross-referenced to D-43's declined alternative rather than re-litigated.

## Deviations from Plan

None - plan executed exactly as written. All acceptance criteria and automated verification
scripts for both tasks pass; no `PUT`/`POST`/`PATCH`/`DELETE` was issued against the API session-wide.

## Issues Encountered

`git status --porcelain` under `/home/ido/pi-mirror/` is NOT clean — that repository carries
pre-existing local modifications and deletions unrelated to this plan (confirmed: the specific
file this plan read, `external_hardware_ingress.py`, shows as untracked (`??`) in that checkout,
and the broader diff — 625 files, mostly deletions — predates this session entirely). This plan
performed read-only operations (`cat`/`grep`/`sed`) against `pi-mirror` and issued zero writes;
the pre-existing dirty state is out of scope per the deviation rules' scope boundary and is not
attributable to this plan's work.

## User Setup Required

None - no external service configuration required. Nothing in this plan touches the rig, the
database, or any Pi file; plan 35-09 (rig-side, user-performed) is where the artifacts produced
here get uploaded and exercised.

## Next Phase Readiness

Wave 2 (plan 35-03's generator) is unblocked: `fixtures/liveness_hook_snippet.py` is the
verbatim text it emits under `--liveness-hook clock-consistent`. Plan 35-09 has everything it
needs to act at the rig: the candidate v3 source, the v2 rollback copy, task definition 434's
current pin state, and the exact `PUT`/rollback calls with lib 177's live `active_version_id`
(137) and no version_id to guess (35-09 reads the new version's id from the upload response).
No blockers.

---
*Phase: 35-deeplabcut-keypoint-likelihood-integration*
*Completed: 2026-08-31*

## Self-Check: PASSED

- FOUND: `.planning/phases/35-deeplabcut-keypoint-likelihood-integration/35-LIVENESS-FINDINGS.md`
- FOUND: `.planning/phases/35-deeplabcut-keypoint-likelihood-integration/fixtures/liveness_hook_snippet.py`
- FOUND: `.planning/phases/35-deeplabcut-keypoint-likelihood-integration/fixtures/extlink_demo_v3.py`
- FOUND: `.planning/phases/35-deeplabcut-keypoint-likelihood-integration/fixtures/extlink_demo_v2_rollback.py`
- FOUND: commit `5f96114` (Task 1)
- FOUND: commit `4dd6cb1` (Task 2)
