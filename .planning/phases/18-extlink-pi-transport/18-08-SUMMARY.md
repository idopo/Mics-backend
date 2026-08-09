---
phase: 18-extlink-pi-transport
plan: 08
subsystem: backend
tags: [preflight, device-lease, extlink, postgres, sqlalchemy]

# Dependency graph
requires:
  - phase: 18-03
    provides: "19 importorskip/xfail-guarded pytest cases in api/tests/test_view_key_preflight.py pinning device_lease.py's exact contract (device_held/extlink_config_invalid shapes, normalize_host collapsing, role:'none' handling)"
provides:
  - "api/device_lease.py — normalize_host, is_extlink_config, validate_extlink_config, device_held_issue, get_lease/acquire_lease/release_leases_for_run/force_release, reconcile_leases, preflight_device_lease_issues, preflight_lease_and_config_issues"
  - "device_leases Postgres table (host UNIQUE) + idempotent run_device_lease_migration, wired at api startup"
  - "preflight_validate step 11: device lease arbitration + extlink config-field validation, top-level (not FDA-gated)"
affects: [18-09]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Lease arbitration enforced by a real Postgres UNIQUE(host) constraint via INSERT ... ON CONFLICT (host) DO NOTHING, never a single-holder check in application code"
    - "reconcile_leases is pure over an injected heartbeat map (never reads Redis itself) — the orchestrator (plan 18-09) is the only Redis reader; this is what makes staleness unit-testable with a fabricated timestamp"
    - "Router call-site extraction: preflight_validate's step 11 is a 4-line try/except calling device_lease.preflight_lease_and_config_issues, keeping toolkit_dispatch.py at exactly the plan's 480-line budget while all lease/config logic lives in device_lease.py"

key-files:
  created:
    - api/device_lease.py
  modified:
    - api/models.py
    - api/db.py
    - api/main.py
    - api/routers/toolkit_dispatch.py
    - api/tests/test_view_key_preflight.py

key-decisions:
  - "acquire_lease is atomic via INSERT ... ON CONFLICT (host) DO NOTHING followed by a read-back, not a SELECT-then-INSERT check-then-act — the real arbitration primitive is the Postgres UNIQUE constraint, matching the plan's explicit instruction not to enforce single-holder in Python"
  - "preflight_lease_and_config_issues (new, not in 18-03's pinned interface) is the step-11 call site's single entry point — introduced specifically to hit the file's 480-line budget without weakening the try/except-per-check non-blocking posture every other preflight step already uses"
  - "Fixed a pre-existing step-numbering bug: CMP-15b's unsatisfiable_wait_issues block (added by an earlier phase) was already labelled '# 10.' inside the FDA guard, so this plan's new block is correctly '# 11.', not a duplicate '# 10.' — a Rule-1 auto-fix, not a deviation from this plan's own scope"
  - "validate_extlink_config short-circuits per-role port checks when role itself is invalid/unknown (e.g. role: 'banana'), then still runs the role-independent field checks (source_id, wait_timeout_s, stale_ms, egress_fail_threshold) — this is what keeps every single-field-invalid test case at exactly one issue"

requirements-completed: [EXTLINK-10, EXTLINK-17, EXTLINK-18]

# Metrics
duration: 45min
completed: 2026-08-09
---

# Phase 18 Plan 08: Device-lease storage + preflight gate Summary

**`api/device_lease.py` (286 lines) implements the device lease's full contract — Postgres `UNIQUE(host)`-enforced arbitration, `validate_extlink_config`'s per-role field checks (including the `role: "none"` port-free path), and pure `reconcile_leases` over an injected heartbeat map — wired into `preflight_validate` as a new top-level step 11 that turns 18-03's 19 pinned lease tests from skip/xfail to 19/19 green.**

## Performance

- **Duration:** ~45 min
- **Started:** 2026-08-09T07:30:00Z (approx.)
- **Completed:** 2026-08-09T08:15:00Z
- **Tasks:** 2
- **Files modified:** 6 (1 created, 5 modified)

## Accomplishments

- **Task 1** — `device_leases` table (`host TEXT UNIQUE`) via a new `DeviceLease` SQLAlchemy model in `api/models.py` and an idempotent `run_device_lease_migration` in `api/db.py`, wired into `api/main.py`'s startup sequence. Verified idempotent by running it three times in a row against the live dev DB with no error (see below). `api/device_lease.py` created with the full 18-03-pinned contract: `normalize_host` (strips scheme/path/port/whitespace, so `"132.77.9.9:37497"` and `"http://132.77.9.9:5556/"` collapse to one key), `is_extlink_config`/`validate_extlink_config` (unknown role, `sub_connect` missing host/connect_port, `router_bind` missing listen_port, `role:"none"` requiring host but neither port, missing `source_id`, `wait_timeout_s` outside `[5,600]`, non-positive `stale_ms`/`egress_fail_threshold`), `device_held_issue`, and the CRUD layer (`get_lease`, `acquire_lease` — atomic via `INSERT ... ON CONFLICT (host) DO NOTHING`, `release_leases_for_run`, `force_release`, `reconcile_leases` — pure over an injected heartbeat map, never touches Redis).
- **Task 2** — `PREFLIGHT_ISSUE_KINDS` extended from 9 to 11 kinds (`device_held`, `extlink_config_invalid`). `preflight_validate` gained step 11 (top-level, outside the `if td_full and td_full.fda_json:` guard — a lease conflict is real with or without an FDA), fed from a `lease_candidates` list collected in the existing step-6 per-module loop rather than a second query pass. Both remaining `xfail` markers in `test_view_key_preflight.py` (`test_lease_blocks_second_run_same_host`, `test_lease_preflight_role_none_module_is_clean`) were removed once step 11 made them pass genuinely, not just XPASS. `-k lease` is 19/19 green with zero skips/xfails. Full backend suite: **387 passed, 1 skipped** (unchanged pre-existing skip; up from the 18-03 baseline of 359 passed/28 skipped, net +28 as all 19 lease tests plus the 8 AST-extractor tests from the concurrently-executing plan 18-07 turned green).

## Task Commits

Each task was committed atomically:

1. **Task 1: `device_leases` table + `api/device_lease.py`** — content landed, but see **Issues Encountered** below: a shared-working-directory git race meant these four files were swept into the concurrently-running plan 18-07's completion commit `44df463` ("docs(18-07): complete hardware-libs extlink AST extractor plan") rather than a dedicated 18-08 commit. The code content is exactly what this plan specifies; only the commit message attribution is affected.
2. **Task 2: Preflight step 11 — `device_held` + `extlink_config_invalid`** - `fc1a103` (feat)

## Files Created/Modified

- `api/device_lease.py` — new, 286 lines. Full contract per 18-03-PLAN's `<interfaces>` block plus one addition, `preflight_lease_and_config_issues`, not in that original interface list (see Decisions).
- `api/models.py` — `DeviceLease` SQLAlchemy model (`host` UNIQUE, joined conceptually against `pilots`/`session_runs`, both SQLAlchemy-owned tables — matches the codebase's dual-ORM rule).
- `api/db.py` — `run_device_lease_migration(eng)`, idempotent `CREATE TABLE IF NOT EXISTS` + `CREATE UNIQUE INDEX IF NOT EXISTS`.
- `api/main.py` — import + startup call for `run_device_lease_migration` (this file was not in the plan's declared `files_modified`, but the plan's own Task 1 action text explicitly requires "call it at startup alongside the existing migrations" — a 2-import-line, 1-call-line addition, functionally required, not scope creep).
- `api/routers/toolkit_dispatch.py` — `PREFLIGHT_ISSUE_KINDS` +2 kinds; new step 11 (4-line try/except call site); `lease_candidates` collection point inside the existing step-6 loop. Held at exactly **480 lines** (plan's stated budget when extraction is triggered).
- `api/tests/test_view_key_preflight.py` — removed 2 `xfail` markers; `test_preflight_issue_kinds_frozenset_is_complete` updated for the 11-kind set (`== 9` → `== 11`, plus the two new membership assertions) — this was a pre-existing, non-guarded test that would otherwise have started failing the moment the frozenset grew, independent of the lease-specific tests; fixed as part of this plan's own scope (Rule 1). Section-header comment rewritten to describe the current (post-18-08) state instead of the pre-18-08 "both markers pending" state.

## Decisions Made

- **`acquire_lease` uses `INSERT ... ON CONFLICT (host) DO NOTHING` + read-back**, not a SELECT-then-INSERT check — the plan explicitly says "do not enforce single-holder in Python"; the UNIQUE constraint is the only thing that has to be correct under a race.
- **`preflight_lease_and_config_issues` added beyond 18-03's pinned interface** — the plan's own Task 2 action anticipated this exact possibility ("If the file would exceed 480 lines, extract step 10's body into a device_lease.py helper... and call that instead"). `toolkit_dispatch.py` was already at 471 lines before this plan (drifted from the plan-writing-time baseline of 459 due to intervening phase 23/25 work), so the extraction was applied immediately rather than attempted-then-reverted.
- **Step numbering fixed from "10" to "11"**: `unsatisfiable_wait_issues` (CMP-15b, an earlier phase's work, nested inside the FDA guard) already occupies comment label "# 10." in this file. The plan's own text says "Add step 10... AFTER step 9" without accounting for this pre-existing collision; labelling the new block "# 11." instead is the correct fix and does not change behavior, only the comment.
- **`validate_extlink_config`'s per-role port checks are skipped (not further evaluated) when the role itself is invalid**, but the role-independent checks (`source_id`, `wait_timeout_s`, `stale_ms`, `egress_fail_threshold`) always run regardless of role validity — this is required for every 18-03-pinned single-field-invalid parametrized case to produce exactly one issue.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Pre-existing step-numbering collision fixed**
- **Found during:** Task 2
- **Issue:** `preflight_validate` already had a comment-labelled "# 10." step (CMP-15b's `unsatisfiable_wait_issues`, nested inside the FDA guard) before this plan started; the plan's text assumed step 10 was the next free slot.
- **Fix:** Labelled the new lease/config-validation block "# 11." instead.
- **Files modified:** `api/routers/toolkit_dispatch.py`
- **Commit:** `fc1a103`

**2. [Rule 1 - Bug] `test_preflight_issue_kinds_frozenset_is_complete` updated for the new count**
- **Found during:** Task 2
- **Issue:** This pre-existing, non-`importorskip`-guarded test asserted `len(PREFLIGHT_ISSUE_KINDS) == 9`; extending the frozenset to 11 kinds (this plan's own explicit deliverable) would otherwise have broken it immediately.
- **Fix:** Updated the assertion to `== 11` and added membership checks for `device_held`/`extlink_config_invalid`.
- **Files modified:** `api/tests/test_view_key_preflight.py`
- **Commit:** `fc1a103`

**3. [Rule 3 - Blocking] `api/main.py` startup wiring added**
- **Found during:** Task 1
- **Issue:** `api/main.py` was not in the plan's declared `files_modified`, but the migration cannot run without a startup call, and the plan's own Task 1 action text explicitly instructs "call it at startup alongside the existing migrations."
- **Fix:** Added the import and the `run_device_lease_migration(engine)` call (2 lines total) alongside the existing migration calls.
- **Files modified:** `api/main.py`
- **Commit:** landed in `44df463` (see Issues Encountered)

## Issues Encountered

**Shared-working-directory git race (not a code issue).** Plan 18-07 was executing concurrently in the same repository checkout (no git worktrees). Task 1's `git add` staged `api/device_lease.py`, `api/models.py`, `api/db.py`, `api/main.py` successfully, but before this agent's own `git commit` ran, plan 18-07's agent ran its own `git add` + `git commit` in the same shared index — a plain `git commit` with no pathspec commits everything currently staged, so all four Task-1 files landed inside 18-07's completion commit `44df463` ("docs(18-07): complete hardware-libs extlink AST extractor plan") instead of a dedicated 18-08 Task-1 commit. Verified the file *content* is exactly correct and unaltered (`wc -l api/device_lease.py` = 286, matches what was written; `git show --stat 44df463` confirms all four files present with the expected insertion counts). This is an attribution/commit-message issue only — no code was lost, reverted, or corrupted, and Task 2's commit (`fc1a103`) is unaffected and correctly scoped. No corrective git history rewrite was attempted, per the "never amend, never force-push" protocol — the working tree is correct, which is what matters for the phase.

## Verification Evidence

**Migration idempotency** (`run_device_lease_migration` run three times against the live dev DB):
```
migration run #2: OK
migration run #3: OK
```
(Run #1 happened implicitly at container startup with no traceback — `Application startup complete.`)

**`-k lease`:** `19 passed, 74 deselected, 8 warnings in 0.62s` — zero skips, zero xfails.

**Full backend suite:** `387 passed, 1 skipped, 8 warnings in 1.55s`.

**`wc -l`:** `480 api/routers/toolkit_dispatch.py`, `286 api/device_lease.py`.

**Live preflight check against the real dev DB** (per the plan's overall `<verification>` block — confirms zero regression on real rig data, since none of it declares an extlink `role`):
- Session 99, pilot 1: `{"ok": false, "issues": [{"issue": "missing", ...}, {"issue": "missing", ...}]}` — pre-existing, unrelated `Solenoid`/`Right_LED` missing-config gaps, not a lease/extlink issue.
- Session 105, pilot 1: one pre-existing `missing` issue, same pre-existing gap category.
- **Sessions 113, 110, 107 (pilot 1): `{"ok": true, "issues": []}`** — clean, unaffected by this plan's new step.

**Pinned `device_held` issue dict shape** (for plan 18-09's `HardwareCheckModal.tsx` mirror):
```python
{
    "module_id": <int>,
    "module_name": "<str>",
    "issue": "device_held",
    "host": "<normalized host>",
    "holder": {
        "host": "<normalized host>",
        "pilot_id": <int>,
        "pilot_name": "<str|None>",
        "session_id": <int|None>,
        "run_id": <int|None>,
        "subject_key": "<str|None>",
        "acquired_at": <datetime>,
    },
    "detail": "<host> is held by pilot '<pilot_name>' (subject <subject_key>, run <run_id>) since <acquired_at>",
}
```

## User Setup Required

None — no external service configuration required. The migration is idempotent and runs automatically at API startup.

## Next Phase Readiness

- Plan 18-09 can build `api/routers/device_leases.py` directly against the pinned interface (`acquire_lease`, `release_leases_for_run`, `force_release`, `get_lease`, `reconcile_leases`, `normalize_host` — all present and correctly typed in `api/device_lease.py`).
- Plan 18-09's own force-release/reconcile HTTP-route tests are net-new (this plan's file had no route-level tests for those two operations — only the two `device_held`/`role:"none"` route tests existed, and both are now green with markers removed).
- `HardwareCheckModal.tsx` can mirror the `device_held` shape recorded above verbatim.
- `gsd-tools requirements mark-complete EXTLINK-10 EXTLINK-17 EXTLINK-18` found no checkbox/traceability rows in `REQUIREMENTS.md` (same known gap as every prior EXTLINK/CMP/DVK/CANVAS plan this milestone — `REQUIREMENTS.md` uses a flat ID/Requirement/Phase table with no per-plan checkboxes) — completion tracked via this SUMMARY and `roadmap update-plan-progress 18` instead.

---
*Phase: 18-extlink-pi-transport*
*Completed: 2026-08-09*

## Self-Check: PASSED

- FOUND: api/device_lease.py
- FOUND: api/models.py
- FOUND: api/db.py
- FOUND: api/main.py
- FOUND: api/routers/toolkit_dispatch.py
- FOUND: api/tests/test_view_key_preflight.py
- FOUND: .planning/phases/18-extlink-pi-transport/18-08-SUMMARY.md
- FOUND: fc1a103 (task 2 commit)
- FOUND: 44df463 (task 1 files, swept into 18-07's completion commit — see Issues Encountered)
