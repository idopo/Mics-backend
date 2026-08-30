---
phase: 34-mics-link-sdk-client-package
plan: 05
subsystem: sdk
tags: [cleanup, deletion, documentation, sender-parity]

# Dependency graph
requires:
  - phase: 34-01
    provides: "sdk/src/mics_link/wire.py, sdk/tests/test_wire_parity.py, sdk/tests/test_import_hygiene.py"
  - phase: 34-02
    provides: "sdk/src/mics_link/values.py (coerce_token, bool-before-int ordering)"
provides:
  - "Exactly one sender-side wire implementation in the repo: sdk/src/mics_link/wire.py (SDK-10 satisfied by removal, not cutover)"
  - "tools/extlink_driver/README.md rewritten as a redirect to the SDK, with every rig fact (task def 434, toolkit 100, module 62, hw lib 177, pilot_hardware_config row 21, pilot 1, port 5599, source_id demo) preserved for plans 34-08/34-09 to @-reference"
  - "tools/extlink_driver/extlink_demo_fda.json untouched — still the 34-09 rig checkpoint fixture"
affects: [34-06, 34-07, 34-08, 34-09]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Docstring provenance references to a deleted module are reworded to avoid the literal deleted-file substring, not just deleted outright — preserves the historical 'lifted from' context while satisfying a hygiene-style grep guard (same pattern as 34-01/34-02's docstring substring fixes)"

key-files:
  created: []
  modified:
    - tools/extlink_driver/README.md
    - sdk/src/mics_link/values.py
    - sdk/tests/pi_reference.py
    - sdk/tests/test_import_hygiene.py
    - .planning/phases/34-mics-link-sdk-client-package/34-RESEARCH.md

key-decisions:
  - "Task 2's target files (34-06/07/08/09-PLAN.md, 34-VALIDATION.md) already carried the correct absence-assertion pattern at execution time — no edits were needed there. Verified with the plan's own exact grep regex before concluding this, per the plan's own admonition ('grep to confirm the list is complete rather than trusting it')."
  - "34-RESEARCH.md's SDK-10 row was NOT in Task 2's files_modified list but did contain a live 'python3 -m pytest -q tools/extlink_driver/' reference describing the driver as retargeted rather than deleted — corrected it to match the actual outcome (deletion, per this plan's own decisions section), since the outer execution success_criteria explicitly required zero such references anywhere under .planning/phases/34-*/."
  - "Three sdk/ docstrings (values.py x2, tests/pi_reference.py, tests/test_import_hygiene.py) named the deleted extlink_wire.py by literal path. Reworded to 'the retired POC driver's coerce_value (tools/extlink_driver/, deleted in plan 34-05)' etc., preserving the provenance information while satisfying Task 1's own verify command, which greps the whole repo's .py files for the substring 'extlink_wire' with no exception carved out for sdk/ files that merely mention it in prose."

requirements-completed: [SDK-10]

# Metrics
duration: ~20min
completed: 2026-08-30
---

# Phase 34 Plan 05: Retire the POC extlink driver Summary

**Deleted `tools/extlink_driver/extlink_wire.py`, `extlink_driver.py` and `test_extlink_wire.py` outright (SDK-10 satisfied by removal, not cutover), rewrote `README.md` as an SDK redirect that still carries every rig fact downstream plans need, and swept the repo clean of the literal deleted-module name so a hygiene-style grep guard has nothing left to catch.**

## Performance

- **Duration:** ~20 min
- **Started:** 2026-08-30T08:30:00Z (approx, after worktree base correction)
- **Completed:** 2026-08-30T08:49:45Z
- **Tasks:** 2/2 completed (Task 2 required no file edits — its target state was already correct)
- **Files modified:** 5 (1 deletion-heavy commit + 1 docs correction commit); 3 files deleted

## Accomplishments

- Exactly one sender-side wire implementation now exists in the repo: `sdk/src/mics_link/wire.py`.
  `tools/extlink_driver/extlink_wire.py`, `extlink_driver.py` and `test_extlink_wire.py` are gone
  from the working tree and from git.
- `tools/extlink_driver/README.md` rewritten as a short redirect: names `mics_link` as the
  supported sender, points at `sdk/README.md`/`sdk/examples/`, and still contains every rig fact
  plans 34-08 and 34-09 cite by @-reference — task def 434, toolkit 100, hardware module 62, hw
  lib 177, `pilot_hardware_config` row 21, pilot 1 at `132.77.72.28`, port 5599, `source_id: demo`,
  the standing TCP-echo-listener dependency, and the "why there is no latency readout" reasoning
  34-08 explicitly carries forward.
- `tools/extlink_driver/extlink_demo_fda.json` verified byte-identical (`git diff --stat` against
  the prior commit showed zero change) — the 34-09 rig checkpoint fixture is untouched.
- Verified (not edited) that `34-06-PLAN.md`, `34-07-PLAN.md`, `34-08-PLAN.md`, `34-09-PLAN.md` and
  `34-VALIDATION.md` all already use the `test ! -f tools/extlink_driver/extlink_wire.py && test
  ! -f tools/extlink_driver/extlink_driver.py` absence-assertion pattern instead of running the
  deleted test suite — no sibling PLAN.md needed correcting.
- Found and corrected one live reference Task 2's file list didn't cover:
  `34-RESEARCH.md`'s SDK-10 row still read "existing driver tests still pass unchanged" /
  `python3 -m pytest -q tools/extlink_driver/`, which now collects zero tests and exits 5.
  Corrected to record SDK-10 as superseded by deletion.
- `sdk/` test suite unaffected: 156 tests green, both before and after this plan's edits.

## Task Commits

1. **Task 1: Delete the POC driver code, preserving the fixture and the rig facts** - `144bbe2` (feat)
2. **Task 2: Correct downstream verify steps** - no file changes required (already correct); the
   one out-of-scope stale reference found in `34-RESEARCH.md` was fixed separately - `f7c6a2d` (docs)

## Files Created/Modified

- `tools/extlink_driver/README.md` - rewritten: redirect header naming `mics_link`/`sdk/README.md`,
  "what still lives here" (the demo FDA fixture), full rig-prerequisites section with all IDs,
  the latency-readout rationale, and a note that `extlink_driver_mac.zip` is now stale
- `sdk/src/mics_link/values.py` - reworded two docstring provenance references and one usage note
  that named `extlink_wire.py` by literal path
- `sdk/tests/pi_reference.py` - reworded one docstring reference to the deleted driver's test suite
- `sdk/tests/test_import_hygiene.py` - reworded the module docstring's reference to the deleted
  driver's original hygiene test
- `.planning/phases/34-mics-link-sdk-client-package/34-RESEARCH.md` - corrected the SDK-10 row from
  "existing driver tests still pass unchanged" / a live pytest command to a deletion-assertion,
  matching the outcome this plan actually implements

## Files deleted

- `tools/extlink_driver/extlink_wire.py`
- `tools/extlink_driver/extlink_driver.py`
- `tools/extlink_driver/test_extlink_wire.py`

These deletions are the entire point of this plan (SDK-10: exactly one sender-side wire
implementation must exist when the phase ends). `tools/extlink_driver/extlink_demo_fda.json` and
`tools/extlink_driver/README.md` were explicitly preserved (the fixture and the rig-facts
document) — see must_haves in `34-05-PLAN.md`.

## Decisions Made

See `key-decisions` in the frontmatter. Summary: Task 2's target files were already correct at
execution time (no edits needed); the one genuinely stale reference was in a file outside Task 2's
stated scope (`34-RESEARCH.md`) but squarely inside this execution's own success criteria, so it
was fixed as a Rule 2/3-style deviation rather than left dangling.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Docstrings in `sdk/` named the deleted `extlink_wire.py` by literal path,
which would fail Task 1's own repo-wide grep guard**
- **Found during:** Task 1, running the precondition/verify sweep before deleting anything
- **Issue:** Task 1's `<behavior>` and `<verify>` require `grep -rl "extlink_wire" --include=*.py .`
  to return nothing repo-wide after deletion — not just inside `tools/extlink_driver/`. Three
  already-committed `sdk/` files (`values.py` x2 occurrences, `tests/pi_reference.py`,
  `tests/test_import_hygiene.py`) contain the literal substring `extlink_wire` in docstrings
  describing where behavior was lifted from (from prior waves 34-01/34-02). Deleting the driver
  files alone would leave the grep guard failing.
- **Fix:** Reworded each occurrence to describe the provenance without the literal deleted
  filename — e.g. "the retired POC driver's `coerce_value` (`tools/extlink_driver/`, deleted in
  plan 34-05)" — preserving the historical context the docstring existed to record.
- **Files modified:** `sdk/src/mics_link/values.py`, `sdk/tests/pi_reference.py`,
  `sdk/tests/test_import_hygiene.py`
- **Verification:** `grep -rl "extlink_wire" --include=*.py .` returns nothing; `cd sdk &&
  python3 -m pytest -q` — 156 tests still pass
- **Committed in:** `144bbe2`

**2. [Rule 2 - Missing critical functionality] `34-RESEARCH.md`'s SDK-10 row was not in Task 2's
files_modified list but was a live, now-failing verify command**
- **Found during:** Task 2, sweeping `.planning/phases/34-*/` broadly (beyond the plan's named
  5 files) per this execution's own success criteria ("No remaining `pytest ...
  tools/extlink_driver` reference anywhere in .planning/phases/34-*/")
- **Issue:** `34-RESEARCH.md` line 565 described SDK-10 as "`extlink_wire.py` deleted;
  `extlink_driver.py` imports SDK; existing driver tests still pass unchanged" with verify command
  `python3 -m pytest -q tools/extlink_driver/` — describing a retarget-not-delete outcome that
  this plan's decisions section explicitly supersedes, and a command that now collects zero tests
  and exits 5.
- **Fix:** Corrected the row to record SDK-10 as superseded by deletion, with a deletion-assertion
  verify command matching the pattern already used in the five files Task 2 did check.
- **Files modified:** `.planning/phases/34-mics-link-sdk-client-package/34-RESEARCH.md`
- **Verification:** `grep -rnE "pytest [^&|]*tools/extlink_driver" .planning/phases/34-*/` now
  returns only prose inside `34-05-PLAN.md` itself (this plan, excluded by its own verify command,
  describing the problem it fixes) — zero live/actionable references remain
- **Committed in:** `f7c6a2d`

---

**Total deviations:** 2 auto-fixed (1x Rule 1 bug — grep-guard-breaking docstrings, 1x Rule 2
missing correction — stale research-doc reference outside the plan's stated file list but inside
this execution's stated success criteria).
**Impact on plan:** Both fixes were necessary to satisfy this plan's own verify commands and the
outer execution's explicit success criteria. No scope creep beyond what those two things required.

## Issues Encountered

Task 2, as written, expected active edits to five files based on a "known occurrences" list with
approximate line numbers. At execution time all five were already correct (most plausibly amended
in an earlier phase-34 documentation sync — the git log shows a prior "docs(34,35): amend phase 34
..." commit). Rather than trust the plan's list, ran its own exact verify regex first per its
explicit instruction ("grep to confirm the list is complete rather than trusting it") — confirmed
zero matches, so no edit was made to those five files. This is not a plan bug: Task 2's own
`<verify>` block is the authority, and it passed without modification.

## User Setup Required

None — no external service configuration required.

## Next Phase Readiness

`sdk/src/mics_link/wire.py` remains the repo's single sender-side wire implementation. Plans
34-06 through 34-09 can proceed without any change to their own PLAN.md files — their verify
steps already assert the driver's absence rather than running its (now-deleted) test suite.
`tools/extlink_driver/README.md` is ready for 34-08 to use as the tone/structure precedent and
the ES-guidance/latency-rationale source it @-references, and for 34-09 to use as the rig
prerequisites reference for its checkpoint. No blockers.

---
*Phase: 34-mics-link-sdk-client-package*
*Completed: 2026-08-30*
