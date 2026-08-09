---
phase: 18-extlink-pi-transport
plan: 05
subsystem: pi-hardware
tags: [msgpack, wire-codec, decoder, liveness, transport-roles, autopilot-free]

# Dependency graph
requires: [18-01]
provides:
  - "external_hardware_wire.py — the autopilot-free half of the ExternalHardware substrate: codec, dtype contract, stale policy, liveness, decoder dispatch, role plan, role/liveness validation"
  - "All 57 tests across test_extlink_wire.py/test_extlink_decoder.py/test_extlink_liveness.py flipped from SKIPPED to PASSED"
affects: [18-06, 18-10, 18-02, 18-03]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Shared private helpers (_resolve_signal/_resolve_event) factor the declared-name-check + dtype-coercion gate so apply_envelope (wire ingress) and run_decoder (foreign @decoder ingress) enforce identically — a foreign source gets no special dispensation."
    - "make_liveness(predicate) returns default_liveness itself when predicate is None (not a wrapper) — REPLACE semantics fall out of returning the callable directly rather than composing it."
    - "socket_plan/requires_liveness_override both raise ValueError naming the offending role for any value outside the three known roles — no role can silently fall through as 'socketed, no override needed'."

key-files:
  created: []
  modified:
    - /home/ido/pi-mirror/autopilot/autopilot/hardware/external_hardware_wire.py

key-decisions:
  - "The plan's own overall <verification> block runs a literal `grep -n \"autopilot\"` on the file expecting NOTHING — stricter than the hygiene test's AST-only check (which only inspects module-scope import statements). The module docstring originally used the prose word \"autopilot\" descriptively; reworded to \"the Pi runtime package\" / \"runtime-framework-free\" throughout so the literal grep is clean, not just the AST guard."
  - "First draft of the file was 358 lines (over the plan's own <=300 budget after Task 2, though still well under the project's 500-line hard limit). Trimmed prose/docstrings only — multi-line rationale paragraphs collapsed to single-line 'why' comments, banner comments shortened, no logic changed, no split into a sibling module. Landed at 290 lines. Verified with a full pytest re-run after trimming — all 57 tests still pass, confirming the trim was textual only."
  - "ALLOWED_DTYPES = {float, int, bool, str} — inferred from the tested cases (float dtype throughout wire/decoder tests, bool via the int-subclass trap test); int/str were not directly exercised by a test but are declared in EXTLINK-12's own requirement text as allowed primitives, so both are included for completeness of the type contract."
  - "apply_envelope also handles an EVT-kind envelope (declared-event check, no coercion) even though no test in test_extlink_wire.py exercises it directly — required by the WIRE_KINDS envelope shapes documented in the plan's <interfaces> block (EXTLINK-03) and exercised indirectly by run_decoder's own declared-event test via the shared _resolve_event helper."
  - "CMD-kind envelopes are intentionally NOT handled by apply_envelope (falls through to the malformed branch if ever passed in) — CMD is Pi-outbound only per EXTLINK-03's envelope table (SDK receives SIG/EVT/HB/ACK, never sends/receives CMD on this ingress path)."

patterns-established:
  - "Pattern: autopilot-free Pi-mirror implementation modules pair 1:1 with their Wave-0 test-contract files, loaded by the same importlib.util.spec_from_file_location path used by the tests — this file is the first IMPLEMENTATION (not just test) in that family to land."

requirements-completed: [EXTLINK-03, EXTLINK-06, EXTLINK-07, EXTLINK-08, EXTLINK-12, EXTLINK-14, EXTLINK-18]

# Metrics
duration: 12min
completed: 2026-08-09
---

# Phase 18 Plan 05: `external_hardware_wire.py` — the autopilot-free wire/decoder/liveness/role substrate Summary

**One new 290-line, autopilot-free Pi-mirror module (`external_hardware_wire.py`) implements the wire codec, dtype contract, stale policy, liveness-vs-staleness split, `@decoder` dispatch, and three-role transport-plan selection pinned by plan 18-01 — flipping all 57 of that plan's tests from SKIPPED to PASSED with zero renaming.**

## Performance

- **Duration:** 12 min
- **Started:** 2026-08-09T07:25:00Z (approx, from prior STATE.md timestamp continuity)
- **Completed:** 2026-08-09T07:37:42Z
- **Tasks:** 2 (both `type="auto" tdd="true"`)
- **Files modified:** 1 (newly created, outside the `mics-backend` git repo)

## Accomplishments

- **Task 1 (codec, dtype contract, ingress validation):** `WIRE_KINDS`, `ALLOWED_DTYPES`, `SignalSpec` (namedtuple), `DecodeStats`, `resolve_dtype`, `encode`, `decode_envelope`, `coerce_value`, `apply_envelope`, `resolve_stale_value` — all 25 tests in `tests/test_extlink_wire.py` PASS, including the AST-based hygiene guard. `decode_envelope` and `coerce_value` catch broad `Exception` on the ingress path (msgpack raises different exception types across versions; a foreign/corrupt frame must never propagate into the caller's IOLoop) while `resolve_dtype`/`encode` are the only two functions that raise, and only at class-build/programmer-error time. `bool` coercion is special-cased to `isinstance(raw, bool)` to dodge the `float(True) == 1.0` int-subclass trap.
- **Task 2 (liveness, transport roles, `@decoder` dispatch):** `default_liveness`, `make_liveness`, `ROLE_ROUTER_BIND`/`ROLE_SUB_CONNECT`/`ROLE_NONE`, `socket_plan`, `requires_liveness_override`, `validate_role_liveness`, `identity_ok`, `run_decoder` — all tests in `tests/test_extlink_liveness.py` (6) and `tests/test_extlink_decoder.py` (26) PASS. `default_liveness`/`make_liveness` share no state with `resolve_stale_value` (proven bidirectionally by `test_liveness_independent_of_signal_staleness`). `socket_plan` returns a plain dict for all three roles including the socketless `role: "none"` (all six fields explicitly `None`/`False`, no port invented, absent `role` key raises naming `role`). `validate_role_liveness` is the single, pure, agent-callable definition of "role none requires an explicit liveness override" that plan 18-10 must call rather than re-implement. `run_decoder` normalizes a dict/list/`None` decoder return and routes every produced pair through the SAME `_resolve_signal`/`_resolve_event` helpers `apply_envelope` uses — a raising decoder is caught, counted `malformed`, and returns `[]`, never propagating.
- `-k role_selection` → 9 passed; `-k role_none` → 10 passed (exceeds the plan's "at least 9" bar).
- Full three-file suite: **57 passed, 0 skipped, 0 errors.**

## Task Commits

No commits were made to `/home/ido/pi-mirror` for either task — that repo is user-owned and the plan's own `<verification>` block states no git command that MUTATES it is ever run. The single deliverable file lives entirely outside the `mics-backend` git repository this executor operates in, so there is nothing to `git add`/commit per task in that repo either. Read-only inspection (`git -C /home/ido/pi-mirror status --short`) confirmed `external_hardware_wire.py` exists as an untracked, uncommitted addition — the expected state for a user-owned repo.

**Plan metadata:** committed separately in `mics-backend` (this SUMMARY.md + STATE.md + ROADMAP.md).

## Files Created/Modified

- `/home/ido/pi-mirror/autopilot/autopilot/hardware/external_hardware_wire.py` (290 lines) - wire codec (`encode`/`decode_envelope`), dtype contract (`resolve_dtype`/`coerce_value`/`ALLOWED_DTYPES`), ingress dispatch (`apply_envelope`, shared `_resolve_signal`/`_resolve_event`), per-signal stale policy (`resolve_stale_value`), liveness (`default_liveness`/`make_liveness`), three transport roles (`ROLE_ROUTER_BIND`/`ROLE_SUB_CONNECT`/`ROLE_NONE`, `socket_plan`, `identity_ok`), the mandatory liveness-override rule (`requires_liveness_override`/`validate_role_liveness`), and foreign `@decoder` dispatch (`run_decoder`)

## Decisions Made

- See `key-decisions` in frontmatter: the literal `grep "autopilot"` wording rewrite, the 358→290 line prose trim (no logic change, no split), `ALLOWED_DTYPES` scope, EVT-kind support in `apply_envelope`, and CMD's deliberate absence from the ingress dispatch.
- Followed `18-01-PLAN.md`'s `<interfaces>` block character-for-character for every public name — no naming judgment calls were needed, matching plan 18-01's own note that this plan "must match these exactly."

## Deviations from Plan

None — plan executed exactly as written. The only adjustment was a documentation wording change (removing the literal string "autopilot" from the module's own docstring/comments) to satisfy the plan's own stricter whole-file `grep` verification step, alongside the required prose trim to stay under the 300-line budget — both are text-only changes with zero effect on any tested behavior (verified by re-running the full 57-test suite after each).

## Issues Encountered

None. A pre-existing, untouched `external_hardware_runtime.py` (332 lines, untracked) was found alongside this plan's file in the same directory — it belongs to plan 18-06's scope, was not created or modified by this plan, and was left exactly as found.

## User Setup Required

None — no external service configuration required. All work was local to the two repos already checked out on this host.

## Next Phase Readiness

- Plan 18-10 (`external_hardware.py`, the `autopilot`-importing half) can now import this module and call `socket_plan`/`identity_ok`/`run_decoder`/`validate_role_liveness` rather than re-implementing any of their logic.
- **Discovery, out of this plan's scope:** `external_hardware_runtime.py` (plan 18-06's deliverable, 332 lines) and both `.planning/phases/18-extlink-pi-transport/18-06-SUMMARY.md` and `18-07-SUMMARY.md` already exist on disk from a prior session. `18-07`'s `mics-backend` work is fully committed (`44df463`); `18-06-SUMMARY.md` is present but **uncommitted** (`git status` shows it `??`, untracked), and its deliverable file in `/home/ido/pi-mirror` is likewise untracked/uncommitted there per the phase's own git rule. This plan did not touch, verify, or commit either — flagging it here so the orchestrator can dispatch a finishing pass for 18-06's own commit if that session was genuinely interrupted mid-protocol.
- `gsd-tools requirements mark-complete` found no checkbox/traceability rows for EXTLINK-03/06/07/08/12/14/18 in `REQUIREMENTS.md` (same known gap as every prior EXTLINK/CMP/DVK plan this phase) — completion tracked via this SUMMARY, STATE.md, and `roadmap update-plan-progress 18` instead.
- No blockers.

---
*Phase: 18-extlink-pi-transport*
*Completed: 2026-08-09*

## Self-Check: PASSED

Both claimed files verified present on disk (`external_hardware_wire.py` in `/home/ido/pi-mirror`,
this SUMMARY.md in `mics-backend`). Full 57-test suite re-run fresh: 57 passed, 0 skipped, 0
errors. No commit hashes are claimed by this plan (no git mutations were made to
`/home/ido/pi-mirror`, per the plan's own constraint), so there is nothing to verify via
`git log`.
