---
phase: 18-extlink-pi-transport
plan: 12
subsystem: hardware-validation
tags: [extlink, external-hardware, rig-checkpoint, zmq, router-bind, egress, readiness-gate, fda-editor]

# Dependency graph
requires:
  - phase: 18-extlink-pi-transport (plans 01-11, 13-15)
    provides: the full ExternalHardware substrate (wire codec, decoders, stale/liveness policy,
      egress worker, lifecycle hooks, readiness gate, device lease, AST extractor, save-gate/
      preflight wiring, FDA-editor operand picker, cross-platform hand driver)
provides:
  - "The single consolidated rig checkpoint for Phase 18 — six real runs (552-556) on pilot 1"
  - "18-HARDWARE-VALIDATION.md: final PROVEN/UNPROVEN/DEFERRED verdict per EXTLINK requirement"
  - "Root-cause diagnosis of the EXTLINK_GATE_TIMEOUT failures (553/555) as a fixture-config gap,
    not a Phase 18 defect, with live proof (run 556) of the exact 3.0s threshold-trip and
    same-second recovery"
  - "Retraction of two earlier wrong coordinator claims (float truncation, genuine liveness bug)"
  - "Direct (non-inferred) proof of the readiness gate's proceed exit via a run-556 log trace"
affects: [26-openephys-device-control, 27-openephys-firing-rate, 28-ttl-vs-network-sync]

tech-stack:
  added: []
  patterns:
    - "Rig checkpoint verdicts distinguish 'PROVEN', 'UNPROVEN (not exercised)', 'UNPROVEN
      (deliberate scope decision)', and 'DEFERRED' rather than collapsing to pass/fail"
    - "Split verdicts for requirements with two independent halves (EXTLINK-19: runtime vs
      browser-authoring; EXTLINK-20: hand-driving vs 60Hz soak) rather than one blended status"

key-files:
  created: []
  modified:
    - .planning/phases/18-extlink-pi-transport/18-HARDWARE-VALIDATION.md

key-decisions:
  - "TEARDOWN (checkpoint step 11) deliberately NOT run — the user chose to keep the single
    curated ExtlinkDemo fixture on pilot 1/toolkit 100 rather than remove it; exact reversing
    commands are recorded and ready whenever that decision changes"
  - "The 553/555 EXTLINK_GATE_TIMEOUT failures are recorded as NOT a Phase 18 code defect — the
    egress-probe-driven alive flip is correct-by-design behavior against a fixture whose egress
    target had no listener; proven by the exact 3.0s failure timer and same-second recovery
    observed live in run 556 with no restart"
  - "EXTLINK-19 and EXTLINK-20 given split verdicts rather than a single PROVEN/UNPROVEN: the
    parts that were directly exercised (runtime transition firing; hand-driving from a real Mac)
    are PROVEN, while the parts that were not (browser-authored picker; ~60Hz soak) stay UNPROVEN"
  - "Two earlier claims in this document (float truncation, 'genuine liveness bug') are formally
    retracted rather than silently corrected, so a future reader does not act on them"

requirements-completed: [EXTLINK-01, EXTLINK-02, EXTLINK-05, EXTLINK-06, EXTLINK-09, EXTLINK-10, EXTLINK-11, EXTLINK-13, EXTLINK-15, EXTLINK-16, EXTLINK-19, EXTLINK-20]

# Metrics
duration: 45min
completed: 2026-08-09
---

# Phase 18 Plan 12: Consolidated Rig Checkpoint — Final Validation Record Summary

**Six real runs on pilot 1 root-caused both failures to a fixture egress-probe timing race (not
a Phase 18 defect), directly proved the readiness gate and egress failure/recovery on hardware,
and left teardown deliberately deferred per the user's decision to keep the demo lib.**

## Performance

- **Duration:** ~45 min (this final recording session; the plan's Tasks 1-3 spanned prior
  sessions across 2026-08-09, including three earlier revisions of this same document)
- **Completed:** 2026-08-09T11:33:35Z
- **Tasks:** 1 (Task 4 — recording the final result; Tasks 1-3 were already committed/executed
  in prior sessions per `git log`: `b4c87cf`, `a2a9a80`, `84612af`, `6af706b`, `69483c6`)
- **Files modified:** 1

## Accomplishments

- Rewrote `18-HARDWARE-VALIDATION.md` end to end against all six checkpoint runs (552-556),
  replacing the prior partial revision that only accounted for run 552.
- Root-caused the two `EXTLINK_GATE_TIMEOUT` failures (runs 553, 555): `recompute_alive`
  (`external_hardware_binding.py:131`) correctly flips `demo.alive` to `false` after three
  consecutive egress-probe failures at 1/s (`egress_fail_threshold: 3`) because nothing was
  listening on `132.77.73.125:5597` — a fixture configuration gap the coordinator introduced
  when consolidating three demo libs into one, not a Phase 18 code defect. Proven live in run
  556 with no restart: `alive` flipped `false` exactly 3.0s after `true`, and flipped back to
  `true` the same second a TCP echo listener was started.
- Recorded EXTLINK-13's readiness-gate proceed exit as **directly observed** (a three-line log
  trace in run 556: `alive=1` at `.019`, `_wait_extlink_ready` at `.026`, `wait` at `.028`) —
  upgrading it from an earlier revision's inference ("the run could not have started otherwise").
- Recorded EXTLINK-15 (egress under real conditions) as PROVEN more thoroughly than the plan's
  own test called for: failure detection, the exact threshold trip, AND recovery were all
  observed on the real rig, with FDA timing visibly unaffected throughout.
- Retracted two earlier, wrong claims: "float values are truncated" (false — `value_raw` carries
  full precision) and "Phase 18 has a genuine liveness bug" (false — see the root-cause above).
- Gave split verdicts for EXTLINK-19 (runtime execution PROVEN across three runs; browser-picker
  authoring UNPROVEN — the transitions were authored via the API, not the editor) and EXTLINK-20
  (hand-driving from a real Mac over Wi-Fi PROVEN in runs 554/556; the mandated ~60Hz soak
  UNPROVEN — not run).
- Recorded TEARDOWN as deliberately DEFERRED, with the exact reversing commands and a new
  standing-dependency note: a TCP echo listener (`scratchpad/egress_listener.py`) must keep
  running on the dev host, or the demo lib's egress probe will re-trigger the same alive-flip
  pattern documented in §0d.
- Added a findings/defects table (§6, 10 items) distinguishing FIXED (commits `84612af`,
  `7dbdf3d`), REPOINTED, NOT FIXED (known defects), and documented-not-a-defect items — including
  a newly found second save-gate trap (the runtime `condition_tree` shape uses a bare literal,
  not `{"const": ...}`, and the save gate accepts the wrong shape silently too).

## Task Commits

Tasks 1-3 of this plan were committed in prior sessions (visible in `git log`, not re-done here
per the objective — the rig session had already happened before this agent was spawned):

1. **Task 1: Register fixtures** - `b4c87cf` (chore)
2. **Task 2: Deploy manifest + checkpoint sheet** - `a2a9a80` (docs)
   - Rule 3 auto-fix during Task 1/2 execution: **`84612af`** (fix) — hardware-lib test leak
     polluting the dev database, found while preparing fixtures
3. **Task 2 revision (config repatch fold-in)** - `6af706b`, `69483c6` (docs)
4. **Task 3: The consolidated rig checkpoint** - human-verify checkpoint, six runs (552-556),
   no file changes (per the plan's own `<files>` spec for this task)
5. **Task 4: Record the result** - `b98b6f1` (docs) — this session

## Files Created/Modified

- `.planning/phases/18-extlink-pi-transport/18-HARDWARE-VALIDATION.md` - full rewrite: run
  table for all six checkpoint runs, root-cause section (§0d), claim retractions (§0e), type
  coverage (§0f), directly-observed readiness gate trace (§0g), final manual-checklist results
  (§2), final per-requirement verdict table (§5), findings/defects table (§6)

## Decisions Made

- **TEARDOWN deliberately not run.** The user chose to keep `ExtlinkDemo` (module 62 / lib 177 /
  pilot config 21 / task def 434) configured on pilot 1 rather than remove it, so this document
  records the decision explicitly (per the plan's own instruction) rather than treating it as an
  incomplete step. Exact reversing commands remain ready in §3.
- **The two rig failures are attributed to the fixture, not the code.** `recompute_alive`'s
  `liveness_alive and not owner._egress_failed` behavior is correct-by-design; the defect was an
  egress probe target with no listener. This distinction matters for anyone reading the run log
  later and assuming Phase 18's liveness logic is unreliable.
- **Split verdicts over blended ones.** EXTLINK-19 and EXTLINK-20 each have two genuinely
  independent halves (data/runtime proof vs. UI/soak proof); recording one blended status for
  either would either overclaim or underclaim what was actually exercised.
- **EXTLINK-13 upgraded from inferred to directly observed**, using run 556's log trace rather
  than the earlier revision's reasoning-only proof — a stronger form of evidence for the same
  requirement, recorded as such rather than silently swapped in.

## Deviations from Plan

None beyond what Rules 1-3 already covered in the prior sessions (the hardware-lib test leak fix,
`84612af`, and the driver README stale source-id fix, `7dbdf3d` — both already committed before
this session started). This session's own work (Task 4) was scoped exactly as the plan specifies:
recording verdicts from checkpoint output already gathered by the coordinator, with no rig
actions, no DB/API mutation, and no teardown performed.

## Issues Encountered

None this session. The prior partial revision of `18-HARDWARE-VALIDATION.md` (uncommitted,
accounting for run 552 only) was superseded by this session's full rewrite covering all six runs
and the coordinator's complete root-cause/type-coverage/retraction evidence.

## User Setup Required

None - no external service configuration required. The two standing dependencies noted in the
document (the demo fixture left on pilot 1, and the dev-host egress listener keeping its probe
satisfied) are operational notes for whoever next uses pilot 1, not setup steps for this plan.

## Next Phase Readiness

- Phase 18's `ExternalHardware` substrate is now the most rig-proven surface in the phase:
  `router_bind` transport, both stale policies, the readiness gate's proceed exit, and egress
  failure/recovery are all directly observed on real hardware, not just unit-tested.
- **Phase 26 (OpenEphys Device Control) depends on this phase and should note three residual
  gaps before it assumes full coverage:** `role: "none"` control-only modules (EXTLINK-18,
  exactly OpenEphys's control shape) are UNPROVEN end-to-end on hardware — only unit-tested;
  `sub_connect` (EXTLINK-14) is likewise UNPROVEN on hardware; and the device-lease-from-a-real-
  disconnect path (EXTLINK-17) was not exercised this session.
- The residual risk already on record stands: Phase 18's lease safety net releases the lease row
  but does not command the foreign device to stop. Phase 26 must decide whether OpenEphys needs
  its own reconciliation on top of this.
- Two backend defects are documented but NOT fixed and remain open for whoever picks them up:
  `delete_hardware_lib`'s 500-instead-of-409 on a dangling `hardware_modules` reference, and the
  transition-condition save-gate gap (both the unknown-key case and the bare-literal
  `condition_tree` shape trap).
- Full backend suite reconfirmed green this session: **435 passed, 1 skipped** — no regression
  from six runs' worth of live rig traffic against the deployed substrate.

---
*Phase: 18-extlink-pi-transport*
*Completed: 2026-08-09*

## Self-Check: PASSED

- FOUND: `.planning/phases/18-extlink-pi-transport/18-HARDWARE-VALIDATION.md`
- FOUND: `.planning/phases/18-extlink-pi-transport/18-12-SUMMARY.md`
- FOUND commits: `b98b6f1`, `b4c87cf`, `a2a9a80`, `84612af`, `6af706b`, `69483c6`, `7dbdf3d`
