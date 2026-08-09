---
phase: 18-extlink-pi-transport
plan: 02
subsystem: testing
tags: [pytest, ast, autopilot, egress-queue, lifecycle-hooks, readiness-gate, liveness-poller, importlib]

# Dependency graph
requires:
  - phase: 18-extlink-pi-transport
    provides: "18-01's autopilot-free test-contract pattern (spec_from_file_location path loader, per-file deliberate-duplication convention)"
provides:
  - "Three autopilot-free, agent-runnable Wave-0 test files pinning EXTLINK-13/15/16/18 against a not-yet-built external_hardware_runtime.py"
  - "Locked public-name contract for EgressWorker/LifecycleRunner/LivenessPoller/build_run_ctx/bind_steps/ready_gate_decision/validate_wait_timeout/gate_timeout_s, character-for-character, for plan 18-06 to implement"
  - "A passing regression pin on mics_task.end() -> super().end(), the chokepoint on_run_stop() (plan 18-10) depends on"
affects: [18-06, 18-10, 18-11, 18-12]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "importlib.util.spec_from_file_location loader for autopilot-free sibling modules (same family as 18-01's test_extlink_wire.py)"
    - "Per-file duplicated _load_runtime() helper (deliberate — same-wave plans 18-01/18-03 must not share a file with this one)"
    - "Zero-arg-callable egress item model: every EgressWorker in this suite is wired send_fn=lambda fn: fn(), matching 26-10-PLAN.md's production usage"
    - "Deterministic queue-full test via a 'started' Event pinning the worker inside item 1, rather than a race-prone 'enqueue N items fast' assumption"
    - "Thread-capture via a wrapped thread_factory to assert on background-thread lifecycle (.is_alive()) without the runtime module exposing its Thread object"
    - "Fake clock/sleep pair (mutable closure) injected into LifecycleRunner so retries never advance a real second; thread_factory stays real since concurrency itself is the thing under test"
    - "AST-based regression pin on SOURCE TEXT (ast.parse of mics_task.py), never a dotted autopilot import, so the check runs on the dev host"

key-files:
  created:
    - /home/ido/pi-mirror/tests/test_extlink_egress.py
    - /home/ido/pi-mirror/tests/test_extlink_lifecycle.py
    - /home/ido/pi-mirror/tests/test_wait_extlink_ready_transitions.py
  modified:
    - /home/ido/pi-mirror/tests/test_mics_task_attrs.py

key-decisions:
  - "gate_timeout_s's config-dict schema assumed a `required` bool key (not specified verbatim in the plan's <interfaces> block) — chosen as the natural, minimal shape consistent with other per-source config dicts already documented in 18-CONTEXT.md (EXTLINK-13's `required`/`wait_timeout_s` pair). Plan 18-06 must match this key name."
  - "LivenessPoller tests do not inject a fake clock/sleep (only LifecycleRunner tests do, per the plan's own instruction) — real small interval_s values (0.01-10.0) plus bounded Event.wait()/Thread.join() calls keep every test deterministic and sub-second without violating the 'no real clock sleep' rule, since no test body calls time.sleep()."
  - "Followed 18-01's precedent: no per-task git commits were made in /home/ido/pi-mirror. All four files live entirely outside the mics-backend git repository this executor operates in, and the plan's own <verification> block forbids any git command that mutates /home/ido/pi-mirror (user-owned repo)."

patterns-established:
  - "Pattern: a plan's <interfaces> block is a binding, character-for-character contract even before the module it describes exists — every public name (EgressWorker, LifecycleRunner, LivenessPoller, RUN_CTX_KEYS, build_run_ctx, GATE_*, ready_gate_decision, validate_wait_timeout, gate_timeout_s, BIND_STEP_*, bind_steps) was used verbatim, no renaming judgment calls."

requirements-completed: [EXTLINK-13, EXTLINK-15, EXTLINK-16, EXTLINK-18]

# Metrics
duration: 12min
completed: 2026-08-09
---

# Phase 18 Plan 02: Wave-0 egress/lifecycle/readiness-gate Pi test contracts Summary

**Three new autopilot-free pytest files (35 tests, all collecting/skipping cleanly) plus one AST-based regression pin pin the egress-queue, run-lifecycle-hook, control-only bind-order, off-IOLoop liveness-poller, and readiness-gate-decision contracts plan 18-06 must implement verbatim.**

## Performance

- **Duration:** 12 min
- **Started:** 2026-08-09T07:13:00Z
- **Completed:** 2026-08-09T07:23:08Z
- **Tasks:** 3 (all `type="auto" tdd="true"`)
- **Files modified:** 4 (3 newly created, 1 extended — all outside the `mics-backend` git repo)

## Accomplishments
- `tests/test_extlink_egress.py` (7 tests) pins `EgressWorker`'s FIFO ordering + actual-invocation proof, deterministic drop-newest-on-full-queue behavior (via a `started` Event pinning the worker mid-item before the queue is filled), no-retry-on-exception on both sides of the `send_fn(item)` seam, edge-triggered `on_alive_change` at the exact `fail_threshold`'th failure and on first recovery, idempotent double-`stop()`, and an AST hygiene guard for zero module-scope `autopilot` imports.
- `tests/test_extlink_lifecycle.py` (21 tests) pins `LifecycleRunner`'s retry-until-ready and retry-through-hard-failure semantics (via an injected fake clock/sleep pair, real `thread_factory`), timeout-driven retry cessation (proven via a captured real `Thread.is_alive()` after `join()`, not the `join()` return value), `start_async()`'s never-blocks guarantee, `on_run_stop`-via-`release()` idempotency, `build_run_ctx`'s exact-six-key shape, `validate_wait_timeout`'s bounds, the EXTLINK-18 control-only `bind_steps` ordering (exact-tuple assertions, both directions: no-socket omits only `BIND_STEP_SOCKET`, socketed prepends it), a control-only device's still-working egress path, and seven `LivenessPoller` cases (off-thread evaluation, cached cheap reads, swallowed raising predicates, edge-triggered `on_change`, idempotent `stop()`, no late `on_change` after `stop()` — proven via thread-capture + `join()`, not a fixed sleep — and a blocking predicate never blocking `start()`/`stop()`).
- `tests/test_wait_extlink_ready_transitions.py` (7 tests) pins `ready_gate_decision`'s three-exit priority order (all-ready beats skip beats timeout, inclusive timeout boundary) and `gate_timeout_s`'s zero-overhead-when-nothing-required rule, max-across-required-only rule, and `ValueError` propagation — with zero `autopilot` import anywhere, resolving the "stretch" classification 18-VALIDATION.md gave this row.
- `tests/test_mics_task_attrs.py` gained exactly one new test, `test_mics_task_end_calls_super_end`, which `ast.parse`s the source text of `mics_task.py`, locates the `end` method inside the `mics_task` class, and asserts its body contains a `Call` to `super().end` — the chokepoint `on_run_stop()` (plan 18-10) depends on. It PASSES today against the existing, unmodified `mics_task.py`. `-k end` selects exactly this one test with the other 6 deselected.
- All 35 new/extended tests exit 0 with every test SKIPPED (reason: `"external_hardware_runtime.py not built yet — plan 18-06"`), except the one AST regression pin, which runs against real, already-existing source and PASSES today.

## Task Commits

No commits were made to `/home/ido/pi-mirror` for any task — the plan's own `<verification>` block states "No git command that MUTATES `/home/ido/pi-mirror` is ever run — that repo is user-owned," matching plan 18-01's precedent (same wave). All four files live entirely outside the `mics-backend` git repository this executor operates in, so there was nothing to `git add`/commit per task in that repo either.

**Plan metadata:** committed separately in `mics-backend` (this SUMMARY.md + STATE.md + ROADMAP.md + `deferred-items.md`).

## Files Created/Modified
- `/home/ido/pi-mirror/tests/test_extlink_egress.py` - EXTLINK-15 FIFO/drop-newest/no-retry/alive-flip contract for `EgressWorker`, 7 tests
- `/home/ido/pi-mirror/tests/test_extlink_lifecycle.py` - EXTLINK-16 lifecycle-hook contract + EXTLINK-18 control-only `bind_steps` + EXTLINK-07 off-IOLoop `LivenessPoller` contract, 21 tests
- `/home/ido/pi-mirror/tests/test_wait_extlink_ready_transitions.py` - EXTLINK-13 three-exit readiness-gate decision contract, 7 tests, no `FiniteDeterministicAutomaton`/`autopilot` import anywhere
- `/home/ido/pi-mirror/tests/test_mics_task_attrs.py` - extended with `import ast` (module level, nothing else) + one new passing regression test pinning `mics_task.end() -> super().end()`

## Decisions Made
- Followed the plan's `<interfaces>` block character-for-character for every public name (`EgressWorker`, `LifecycleRunner`, `LivenessPoller`, `RUN_CTX_KEYS`, `build_run_ctx`, `GATE_PROCEED`/`GATE_SKIP`/`GATE_TIMEOUT`/`GATE_WAIT`, `ready_gate_decision`, `validate_wait_timeout`, `gate_timeout_s`, `BIND_STEP_SOCKET`/`_TRACKERS`/`_LIVENESS`/`_EGRESS`/`_LIFECYCLE`, `bind_steps`) — plan 18-06 must match these exactly, so no naming judgment calls were made here.
- `gate_timeout_s`'s config-dict shape (a `required: bool` key alongside `wait_timeout_s`) was inferred from 18-CONTEXT.md's EXTLINK-13 description, since the plan's `<interfaces>` block specifies the function's *behavior* but not the dict's literal key names — recorded here so plan 18-06 and any later plan reading this config dict agree on `required`, not e.g. `is_required`.
- Deliberately did NOT inject a fake clock into `LivenessPoller` tests (only `LifecycleRunner`'s retry loop needed one per the plan's own instruction); real bounded `interval_s` + `Event.wait()`/`Thread.join()` timeouts keep every liveness test deterministic and sub-second.
- Used a wrapped `thread_factory` (captures the real `threading.Thread` instance) in three tests (`LifecycleRunner`'s timeout-cessation test and `LivenessPoller`'s no-late-fire test) to assert on background-thread lifecycle without requiring the runtime module to expose its thread object — a black-box proof that avoids over-specifying internals.

## Deviations from Plan

None — plan executed exactly as written. One pre-existing, out-of-scope issue was discovered and logged rather than fixed (see below).

### Deferred (not fixed — out of scope)

**1. `tests/test_mics_task_attrs.py`'s original 6 tests fail when the file is run standalone on this dev host, independent of this plan's edit**
- **Found during:** Task 3 (verifying the full-file run named in the plan's overall `<verification>` block: `python3 -m pytest -q tests/test_mics_task_attrs.py  # all 7 pass, none skipped`)
- **Issue:** the 6 pre-existing tests use `patch("autopilot.tasks.mics_task....")` / `from autopilot.tasks.mics_task import mics_task` — dotted imports that execute `autopilot/__init__.py`, which imports `npyscreen`, not installed on this dev host. This is the exact, already-documented Phase 18 constraint from STATE.md ("`import autopilot.*` fails on the dev host — npyscreen missing"). The file predates Phase 18 (its own docstring says "Plan 01", an earlier phase).
- **Verified pre-existing:** reproduced the identical 6 failures against a temporary copy containing ONLY the original 6 tests, with no `import ast` and no new test added — confirms this plan's edit did not cause or worsen it.
- **Not fixed:** installing `npyscreen` on the dev host is exactly the environment change Phase 18's autopilot-free-sibling-module design exists to avoid needing; out of scope for a Wave-0 test-contract plan. Logged in `.planning/phases/18-extlink-pi-transport/deferred-items.md`.
- **Impact on this plan's own acceptance gate:** none — Task 3's own `<verify>`/`<done>` only require `pytest tests/test_mics_task_attrs.py -k end` (1 passed, 6 deselected), which passes cleanly.

## Issues Encountered
None beyond the deferred item above.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness
- Plan 18-06 (`external_hardware_runtime.py`) can now be implemented against a locked, agent-verifiable contract spanning this plan and 18-01: running the three new/extended files after 18-06 lands should flip all 34 currently-skipped tests from SKIPPED to PASSED with zero renaming, alongside 18-01's 57 wire/decoder/liveness tests.
- Plan 18-10 (`.bind()` / `ExternalHardware`) can implement the control-only `bind_steps` ordering and the readiness-gate decision by calling — never re-implementing — `ready_gate_decision`, `gate_timeout_s`, `validate_wait_timeout`, and `bind_steps` from `external_hardware_runtime.py`.
- 18-VALIDATION.md's "stretch" classification for the readiness-gate transitions row is resolved: the gate's DECISION is now a pure, agent-runnable function; only the FDA `add_method`/`add_transition`/`set_initial_method` wiring remains USER-RUN (plans 18-11 + 18-12).
- No blockers.

---
*Phase: 18-extlink-pi-transport*
*Completed: 2026-08-09*

## Self-Check: PASSED

All four claimed test files, this SUMMARY.md, and `deferred-items.md` verified present on disk.
No commit hashes are claimed by this plan (no git mutations were made to `/home/ido/pi-mirror`,
per the plan's own constraint, matching plan 18-01's precedent) — nothing to verify via
`git log` for those files. Fresh test runs (`pytest -q tests/test_extlink_egress.py`,
`tests/test_extlink_lifecycle.py`, `tests/test_wait_extlink_ready_transitions.py`,
`tests/test_mics_task_attrs.py -k end`) confirmed live above, all passing per the plan's
own `<done>` criteria.
