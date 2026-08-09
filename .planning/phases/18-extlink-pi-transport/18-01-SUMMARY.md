---
phase: 18-extlink-pi-transport
plan: 01
subsystem: testing
tags: [msgpack, pytest, ast, autopilot, wire-codec, decoder, liveness, importlib]

# Dependency graph
requires: []
provides:
  - "Three autopilot-free, agent-runnable Wave-0 test files pinning EXTLINK-03/06/07/08/12/14/18"
  - "msgpack importable on the dev host (system Python 3.12, --break-system-packages)"
  - "Locked public-name contract for external_hardware_wire.py, character-for-character, for plan 18-05 to implement"
affects: [18-05, 18-06, 18-10, 18-02, 18-03]

# Tech tracking
tech-stack:
  added: [msgpack==1.2.1 (dev host only, --break-system-packages)]
  patterns:
    - "importlib.util.spec_from_file_location loader for autopilot-free sibling modules (matches tests/test_fda_vocabulary.py, tests/test_detector_view_keys.py precedent)"
    - "Per-file duplicated _load_wire() helper (deliberate — same-wave plans 18-02/18-03 must not share a file with 18-01)"
    - "AST-based module-scope-only import hygiene guard (ast.parse + tree.body, not ast.walk, so nested/function-local imports don't false-positive)"

key-files:
  created:
    - /home/ido/pi-mirror/tests/test_extlink_wire.py
    - /home/ido/pi-mirror/tests/test_extlink_decoder.py
    - /home/ido/pi-mirror/tests/test_extlink_liveness.py
  modified: []

key-decisions:
  - "msgpack installed via `python3 -m pip install --break-system-packages msgpack` — plain and --user both failed with PEP 668 externally-managed-environment; --break-system-packages was the first (and only) one that worked, landing msgpack 1.2.1 in the user site-packages."
  - "Hygiene guard walks only tree.body (module scope), not ast.walk, so a hypothetical function-local `import autopilot` inside a lazy-loaded helper would NOT trip it — matches the plan's literal wording ('ZERO module-scope import autopilot... statements')."
  - "coerce_value coverage for bool used raw int 1 (not True) to hit the int-subclass trap per the plan's own example; a separate case proves real True passes."

patterns-established:
  - "Pattern: autopilot-free Pi-mirror test contract lives in tests/test_extlink_*.py, loaded by path, never a dotted autopilot import — this is now the fourth file family following that shape (fda_vocabulary, detector_view_keys, now wire/decoder/liveness)."

requirements-completed: [EXTLINK-03, EXTLINK-06, EXTLINK-07, EXTLINK-08, EXTLINK-12, EXTLINK-14, EXTLINK-18]

# Metrics
duration: 3min
completed: 2026-08-09
---

# Phase 18 Plan 01: Wave-0 autopilot-free Pi test contracts Summary

**Three autopilot-free pytest files (57 tests total, all collecting/skipping cleanly) pin the wire codec, `@decoder`/transport-role, and liveness-vs-staleness contracts that plan 18-05 must implement verbatim — plus a working `msgpack` on the dev host via `pip install --break-system-packages`.**

## Performance

- **Duration:** 3 min
- **Started:** 2026-08-09T07:15:32Z
- **Completed:** 2026-08-09T07:18:07Z
- **Tasks:** 3 (all `type="auto" tdd="true"`)
- **Files modified:** 3 (all newly created, all outside the `mics-backend` git repo)

## Accomplishments
- `msgpack` importable by the agent on this dev host (`msgpack.version == (1, 2, 1)`), resolved with `--break-system-packages` after plain and `--user` both hit PEP 668's externally-managed-environment guard, exactly as the plan anticipated trying in sequence.
- `tests/test_extlink_wire.py` (25 tests) pins `encode`/`decode_envelope`/`resolve_dtype`/`coerce_value`/`apply_envelope`/`resolve_stale_value`, plus an AST-based hygiene guard that fails loudly if `external_hardware_wire.py` ever gains a module-scope `autopilot` import.
- `tests/test_extlink_decoder.py` (26 tests) pins `run_decoder` (dict-return, list-of-pairs-return, `None`-return, raising-decoder-never-propagates, partial-application on unknown-name/dtype-mismatch, declared-event routing), `socket_plan`/`identity_ok` role selection for `router_bind`/`sub_connect`, and the new `role: "none"` (EXTLINK-18) contract — all-six-fields-explicit, no-port-invented, no-silent-fallback, absent-role-is-an-error — plus `requires_liveness_override`/`validate_role_liveness` (EXTLINK-18+EXTLINK-07).
- `tests/test_extlink_liveness.py` (6 tests) pins `default_liveness`, the liveness-vs-staleness independence proof (both directions asserted explicitly, per the plan's anti-docstring-only instruction), `make_liveness`'s override-replaces-not-ORs-with-default behavior, and the `make_liveness(None)` passthrough.
- All 57 tests SKIP with the required reason string (`"external_hardware_wire.py not built yet — plan 18-05"`); zero collection errors; zero `autopilot` imports anywhere (verified by the plan's own `grep -rn` gate, which returned nothing).

## Task Commits

No commits were made to `/home/ido/pi-mirror` for any task — the plan's own `<verification>` block states "No git command that MUTATES `/home/ido/pi-mirror` is ever run — that repo is user-owned." All three task files live entirely outside the `mics-backend` git repository this executor operates in, so there was nothing to `git add`/commit per task in that repo either. Read-only inspection (`git -C /home/ido/pi-mirror status --short`) confirmed all three files exist as untracked, uncommitted additions — exactly the expected state for a user-owned repo.

**Plan metadata:** committed separately in `mics-backend` (this SUMMARY.md + STATE.md + ROADMAP.md).

## Files Created/Modified
- `/home/ido/pi-mirror/tests/test_extlink_wire.py` - EXTLINK-03/12 wire-codec + dtype-coercion contract, 25 tests, plus the autopilot-free hygiene guard
- `/home/ido/pi-mirror/tests/test_extlink_decoder.py` - EXTLINK-14/08 `@decoder` + role-selection contract, 26 tests, including the EXTLINK-18 `role: "none"` no-socket contract and its mandatory liveness-override pairing
- `/home/ido/pi-mirror/tests/test_extlink_liveness.py` - EXTLINK-07 liveness-vs-staleness split contract, 6 tests

## Decisions Made
- `--break-system-packages` was required for `pip install msgpack` on this Ubuntu/system-Python-3.12 host; recorded here per the plan's explicit instruction so plan 18-04 (the Pi-side pin, separate host/Python version) doesn't assume the same flag is needed there.
- Followed the plan's `<interfaces>` block character-for-character for every public name (`WIRE_KINDS`, `ALLOWED_DTYPES`, `ROLE_ROUTER_BIND`/`ROLE_SUB_CONNECT`/`ROLE_NONE`, `SignalSpec`, `DecodeStats`, `resolve_dtype`, `encode`, `decode_envelope`, `coerce_value`, `apply_envelope`, `resolve_stale_value`, `default_liveness`, `make_liveness`, `socket_plan`, `requires_liveness_override`, `validate_role_liveness`, `identity_ok`, `run_decoder`) — plan 18-05 must match these exactly, so no naming judgment calls were made here.

## Deviations from Plan

None - plan executed exactly as written.

## Issues Encountered
None.

## User Setup Required

None - no external service configuration required. `msgpack` is installed in the current user's site-packages on this dev host only; it does not need to be (and per the plan, must not be) installed on the Pi by this plan — that is plan 18-04's job.

## Next Phase Readiness
- Plan 18-05 (`external_hardware_wire.py`) can now be implemented against a locked, agent-verifiable contract: running `pytest tests/test_extlink_wire.py tests/test_extlink_decoder.py tests/test_extlink_liveness.py` after 18-05 lands should flip all 57 tests from SKIPPED to PASSED with zero renaming.
- Plans 18-02 and 18-03 (same wave) must still write their own `_load_wire()` copies per the plan's deliberate-duplication instruction — this plan does not create a shared loader module.
- No blockers.

---
*Phase: 18-extlink-pi-transport*
*Completed: 2026-08-09*

## Self-Check: PASSED

All three claimed test files and this SUMMARY.md verified present on disk. No commit hashes
are claimed by this plan (no git mutations were made to `/home/ido/pi-mirror`, per the plan's
own constraint), so there is nothing to verify via `git log`. `msgpack` import verified live.
