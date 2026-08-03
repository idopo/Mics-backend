---
phase: 23-compute-primitives-variables
plan: 10
subsystem: infra
tags: [raspberry-pi, elasticsearch, fda, compute, hardware-validation]

requires:
  - phase: 23-04
    provides: Pi runtime `compute` action type in _build_action_callable
  - phase: 23-05
    provides: single lib-version resolution chain + LOAD_HARDWARE_LIBS test_import
  - phase: 23-07
    provides: compute-aware preflight and auto-provisioning self-heal
  - phase: 23-08
    provides: compute action authoring in the FDA editor
provides:
  - Hardware proof that a compute action executes on the rig, writes a variable, and gates a transition through both branches
  - 23-HARDWARE-VALIDATION.md recording what is proven, what is not, and the exact deployed state
  - preflight `state_wait_unsatisfiable` check (CMP-15b) closing the deadlock class found on the rig
  - `event_data.value_raw` float field + Pi emitter, closing silent float truncation in the event log
affects: [phase-24, phase-25, analysis, kibana-dashboards]

tech-stack:
  added: []
  patterns:
    - "Static wait-deadlock analysis over the FDA transition graph (wait_analysis.py)"
    - "Additive ES field for a type the legacy mapping cannot hold, rather than a reindex"

key-files:
  created:
    - .planning/phases/23-compute-primitives-variables/23-HARDWARE-VALIDATION.md
    - api/wait_analysis.py
    - api/tests/test_wait_analysis.py
    - web_ui/react-src/src/components/NumericInput.tsx
    - web_ui/react-src/src/components/numericDraft.mts
    - web_ui/react-src/src/components/computeArgs.mts
    - web_ui/react-src/src/components/internalVariables.mts
  modified:
    - /home/ido/pi-mirror/autopilot/autopilot/utils/logging_utils.py
    - api/routers/toolkit_dispatch.py
    - api/fda_validation.py
    - api/compute_provisioning.py
    - web_ui/react-src/src/components/ComputeActionFields.tsx

key-decisions:
  - "Validated an equivalent compute-gated FDA rather than the planned gonogo task — the mechanism is proven, gonogo is not"
  - "Added ES field `value_raw` (float) instead of retyping `value` — retyping needs a reindex of 2.9M docs"
  - "Kept `value` int-coerced for backward compatibility; the coercion is load-bearing because raw bools are rejected by a long field"
  - "Deadlock check fires only when EVERY exit is blockable and exempts complementary pairs, so a correct probabilistic branch is never flagged"
  - "Did not patch the user's task definition FDA unprompted — an open editor tab would autosave over it"

patterns-established:
  - "Preflight issue kinds are pinned by a test so a new kind cannot be added without surfacing it in the UI"
  - "Pi deploys diff the Pi's copy against the mirror BEFORE pushing, to prove no foreign change is overwritten"

requirements-completed: [CMP-01, CMP-02, CMP-03, CMP-04, CMP-05, CMP-06, CMP-13, CMP-14, CMP-18]

duration: 95min
completed: 2026-08-03
---

# Phase 23 Plan 10: Hardware Validation Summary

**Compute primitives proven end to end on the real rig across 7 runs — and seven defects found and fixed in the process, every one of which had already reached the rig or the GUI.**

## Performance

- **Duration:** ~95 min
- **Completed:** 2026-08-03
- **Tasks:** 3/3 (deploy, validate, record)
- **Runs on hardware:** 535, 541, 543, 544, 545, 546, 547

## Accomplishments

- **Compute mechanism proven on hardware.** 41 draws across runs 543–547 with **zero routing violations**: every `< 0.5` draw retried, every `>= 0.5` advanced, trial counter correct in all runs.
- **CMP-17 proven live.** `HARDWARE_LIB_TEST_RESULT ... ok=True` for all 5 libs; `Compute Ops` resolves to v41 `stable` via `toolkit_default`.
- **Silent float truncation closed.** `int(0.656)` = `0` plus a `long`-mapped field meant every captured float was recorded as `0`. `value_raw` (float) added additively — 21/21 draws now match their `COMPUTE` result, and the field aggregates.
- **A whole defect class closed.** The rig hang became the `state_wait_unsatisfiable` preflight check, verified to flag the pre-fix FDA and stay silent on the fixed one.
- **No regression to existing hardware.** The touch-detector task ran clean post-deploy; detector/IRQ/trigger processing continued normally even while the FDA was deadlocked.

## Task Commits

1. **Deploy Pi runtime** — `fda_vocabulary.py`, `mics_task.py`, `validate_fda.py` verified byte-identical on the Pi
2. **Validate + fix on rig** — `59345f7`, `e8f0cdb`, `1d2f521` (compute defaults), float/args/variables fixes, `state_wait_unsatisfiable` preflight
3. **Record** — `fd4604c` (docs: 23-HARDWARE-VALIDATION.md)

## Files Created/Modified

- `23-HARDWARE-VALIDATION.md` — 206-line evidence log (proven / not proven / deployed state)
- `api/wait_analysis.py` — static wait-deadlock analysis, 9 tests
- `web_ui/react-src/src/components/numericDraft.mts` + `computeArgs.mts` + `internalVariables.mts` — pure logic with `node:test` coverage (45 frontend tests total)
- `pi-mirror .../logging_utils.py` — emits `value_raw` for float captures

## Deviations

- **The gonogo task was never built.** An equivalent compute-gated FDA (random draw gating a transition, with a retry loop) was validated instead. It exercises the same machinery, but gonogo itself remains unvalidated. Recorded prominently in the validation log.
- **Scope grew with seven defect fixes.** All were blocking discoveries made while validating, auto-fixed per deviation rules rather than deferred, since each prevented the phase's own must_haves from being demonstrable.
- **ES mapping change required user authorisation.** The first attempt was blocked by the permission classifier; it was applied only after the user explicitly approved.

## Known Gaps (carried forward)

1. **CMP-16 partial** — the `Hardware_Event` omits positional args (`log_action` merges only `kwargs`), so an op's *inputs* are not recoverable from the event log.
2. **Non-numeric compute outputs would be silently dropped** — `value` is `long`; ES rejects `"left"`/`true`/`["a","b"]` and the handler swallows the failure. Latent: `random_choice`/`assign` are unused today. Fix mirrors `value_raw` (a `value_str` keyword field).
3. **CMP-18 upload path unproven on hardware** — all runs used the seeded lib; a researcher-authored compute lib was never uploaded through the GUI.
4. **`hot_update_fda` variable collision** — predicted by 23-04, still untriggered.
5. **Pi-side unit tests never executed** — `test_compute_ops.py` / `test_fda_vocabulary.py` were never copied to or run on the Pi.
