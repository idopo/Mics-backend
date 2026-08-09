---
phase: 18-extlink-pi-transport
plan: 04
subsystem: infra
tags: [msgpack, pip, pi-mirror, dependency-pin, python3.7]

# Dependency graph
requires: []
provides:
  - Verified, exact `msgpack==1.0.5` pin in both pi-mirror requirements files, resolved by a real
    `pip install` against the rig's Python 3.7.3 venv (never guessed)
affects: [18-05, 18-06, 18-12]

# Tech tracking
tech-stack:
  added: [msgpack==1.0.5 (rig, Python 3.7.3, piwheels armv7l cp37 wheel)]
  patterns:
    - "USER-RUN pin resolution: agent stages a `==TBD` placeholder + exact instructions, user
      runs the real pip install on the target device, agent records the reported version
      verbatim — never guesses a pin for a cross-arch/cross-Python-version dependency"

key-files:
  created: []
  modified:
    - /home/ido/pi-mirror/requirements.txt
    - /home/ido/pi-mirror/autopilot/requirements.txt

key-decisions:
  - "Resolved version is msgpack==1.0.5, not msgpack==1.1.x — the rig's Python 3.7.3 rejected the
    unconstrained `pip install msgpack` (msgpack>=1.1 requires Python>=3.9); the user re-ran with
    `pip install \"msgpack<1.1\"`, which piwheels resolved to 1.0.5 (cp37, armv7l wheel)."
  - "Dev host (this machine) has msgpack 1.2.1 installed (from plan 18-01's Task 1) — a genuine
    version skew from the rig's 1.0.5, expected and harmless since the dev host never runs the
    autopilot-free wire codec against the real Pi venv; recorded here so a future plan doesn't
    mistake it for an inconsistency."

requirements-completed: [EXTLINK-03]

# Metrics
duration: 6min
completed: 2026-08-09
---

# Phase 18 Plan 04: msgpack version pin resolution Summary

**Both pi-mirror requirements files now pin `msgpack==1.0.5`, the exact version a real `pip install "msgpack<1.1"` resolved against the rig's live Python 3.7.3 venv (`~/.venv/autopilot`) — no version was guessed.**

## Performance

- **Duration:** ~6 min (Task 3 only; Tasks 1-2 executed in a prior session)
- **Started:** 2026-08-09 (Task 3, this session)
- **Completed:** 2026-08-09
- **Tasks:** 3 (1 auto, 1 checkpoint:human-action, 1 auto)
- **Files modified:** 2

## Accomplishments
- Staged and then resolved an exact, rig-verified `msgpack==1.0.5` pin in both pi-mirror
  `requirements.txt` files — the version pip's own resolver picked for Python 3.7.3, not a guess.
- Confirmed the `msgpack>=1.1 requires Python>=3.9` constraint is real: the plain
  `pip install msgpack` command failed on the rig exactly as the plan predicted, and the
  `msgpack<1.1` fallback succeeded with the piwheels armv7l/cp37 wheel for 1.0.5.
- Recorded the dev-host/rig version skew (1.2.1 vs 1.0.5) explicitly so plan 18-05/18-06 (which
  build/test the wire codec on the dev host) don't misread it as a bug.

## Task Commits

Each task was committed atomically, except where the target files live outside this repo:

1. **Task 1: Stage the dependency entry with a TBD marker** — no commit (files live in
   `/home/ido/pi-mirror`, a separate user-owned repo; no git command that mutates that repo is
   ever run per project rule). Executed in the prior session.
2. **Task 2: USER resolves the msgpack pin on the rig** — checkpoint, no file change; resolved by
   the user running `pip install "msgpack<1.1"` on the rig and reporting `Version: 1.0.5`.
3. **Task 3: Record the resolved pin** — no commit (same reason as Task 1; files live in
   `/home/ido/pi-mirror`). Executed this session.

_No commits land in the `mics-backend` repo from this plan's task work — all three deliverable
edits are to files entirely outside its `files_modified` scope. The final metadata commit below
is the only commit this plan makes in `mics-backend`._

## Files Created/Modified
- `/home/ido/pi-mirror/requirements.txt` - `msgpack==TBD` → `msgpack==1.0.5`, comment extended with
  the resolution date and rig Python version.
- `/home/ido/pi-mirror/autopilot/requirements.txt` - same edit, kept in exact sync with the
  top-level file per the plan's formatting requirement.

## Decisions Made
- **Used the `msgpack<1.1` fallback path the plan anticipated**, since the plain install failed on
  Python 3.7.3 exactly as `18-RESEARCH.md` predicted. No pin was invented — 1.0.5 came from pip's
  resolver on the real target device.
- **Left the dev-host msgpack version (1.2.1, installed in plan 18-01) untouched** — it is not a
  requirements-file pin, just a local dev-host package for running the autopilot-free test suite,
  and a version mismatch there is expected, not a defect to fix.

## Deviations from Plan

None — plan executed exactly as written. Task 3's automated verify
(`grep -h "msgpack" ... | grep -v "^#"`) confirms both lines read `msgpack==1.0.5` with no `TBD`
remaining.

## Issues Encountered
None. The `pip install msgpack` → Python-version-rejection → `pip install "msgpack<1.1"` fallback
happened exactly as the plan's `<how-to-verify>` block anticipated; no unplanned troubleshooting
was needed.

## User Setup Required

None — the one manual step this plan required (the rig `pip install`) is already complete; see
Task 2 above.

## Next Phase Readiness
- Plan 18-05 (`external_hardware_wire.py`) and plan 18-06 (`external_hardware_runtime.py`) can now
  add `import msgpack` without an unresolved dependency question — the pin is exact and verified.
- Plan 18-12's rig deploy step can install from `requirements.txt` and reproduce the exact same
  `msgpack==1.0.5` build that was proven to work on this rig's venv, rather than re-resolving.
- No blockers created for downstream plans.

---
*Phase: 18-extlink-pi-transport*
*Completed: 2026-08-09*

## Self-Check: PASSED

- FOUND: /home/ido/pi-mirror/requirements.txt (contains `msgpack==1.0.5`)
- FOUND: /home/ido/pi-mirror/autopilot/requirements.txt (contains `msgpack==1.0.5`)
- FOUND: .planning/phases/18-extlink-pi-transport/18-04-SUMMARY.md
