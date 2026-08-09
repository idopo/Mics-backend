---
phase: 18-extlink-pi-transport
plan: 06
subsystem: pi-runtime
tags: [threading, queue, egress-worker, lifecycle-runner, liveness-poller, readiness-gate, bind-steps]

# Dependency graph
requires:
  - phase: 18-extlink-pi-transport
    provides: "18-02's locked, character-for-character public-name contract (EgressWorker/LifecycleRunner/LivenessPoller/build_run_ctx/bind_steps/ready_gate_decision/validate_wait_timeout/gate_timeout_s) and its three autopilot-free pytest files pinning EXTLINK-13/15/16/18"
provides:
  - "external_hardware_runtime.py — EgressWorker, LifecycleRunner, LivenessPoller, build_run_ctx, ready_gate_decision, gate_timeout_s, validate_wait_timeout, bind_steps, all BIND_STEP_*/GATE_* constants — implemented, autopilot-free, 298 lines"
  - "All 35 of plan 18-02's tests flipped from SKIPPED to PASSED with zero renaming"
affects: [18-10, 18-11, 18-12]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "queue.Queue(maxsize=N).put_nowait for drop-newest overflow semantics — no custom ring buffer"
    - "queue.Queue.unfinished_tasks + task_done() for a bounded, pollable drain() (Queue.join() has no timeout param in stdlib)"
    - "threading.Event.wait(interval_s) as an interruptible sleep for both EgressWorker's 0.1s poll-for-stop and LivenessPoller's interval — bounded stop() latency without busy-waiting"
    - "Zero-arg-callable egress item model: EgressWorker only ever calls send_fn(item); production wiring is send_fn=lambda fn: fn(), matching 26-10-PLAN.md's self-invoking closures verbatim"
    - "Edge-triggered alive/on_change flip via an explicit '== fail_threshold' (not '>=') comparison in EgressWorker, and a 'result != cached' comparison in LivenessPoller — both fire exactly once per transition, never once per failure/poll"
    - "LivenessPoller's stop() flag is checked strictly AFTER the predicate call returns, inside poll_once, so a blocking predicate that outlives stop()'s bounded join can never fire a late on_change"

key-files:
  created:
    - /home/ido/pi-mirror/autopilot/autopilot/hardware/external_hardware_runtime.py

key-decisions:
  - "EgressWorker._run polls self._queue.get(timeout=0.1) in a loop rather than pushing a None sentinel through put() on stop() — a sentinel put() could block indefinitely if the queue was already full and the worker thread were wedged inside a long-running send_fn, defeating the plan's own 'wedged item cannot hang Task.end()' requirement. The 0.1s poll bounds stop() latency instead."
  - "drain(timeout) is a custom poll loop over queue.Queue.unfinished_tasks (public, undocumented-but-standard stdlib attribute used internally by Queue.join()) rather than Queue.join(), because stdlib Queue.join() takes no timeout argument at all."
  - "validate_wait_timeout rejects bool explicitly (isinstance(value, bool) check before the int check) even though no test exercises this — bool is a subclass of int in Python and True/False silently passing as 1/0 would be a confusing bug for a field the plan calls out as user-config-facing."
  - "The module was trimmed from an initial 348 lines (over the plan's <=300 soft cap after a full first draft) down to 298 by shortening every class/function docstring to its one-line rationale core, per the plan's own escape hatch ('TRIM PROSE AND DOCSTRINGS... DO NOT SPLIT'). No behavior or public name changed during the trim; each edit was re-verified against the full 35-test suite."

patterns-established:
  - "The file's public surface (constructor kwargs, method names, constant values) was taken verbatim from what plan 18-02's tests exercise, not from independent judgment — every kwarg name, string constant, and exception type was reverse-derived from an assertion in test_extlink_egress.py / test_extlink_lifecycle.py / test_wait_extlink_ready_transitions.py."

requirements-completed: [EXTLINK-13, EXTLINK-15, EXTLINK-16, EXTLINK-18]

# Metrics
duration: 25min
completed: 2026-08-09
---

# Phase 18 Plan 06: EgressWorker + LifecycleRunner + LivenessPoller + readiness-gate runtime Summary

**`external_hardware_runtime.py` (298 lines, autopilot-free, stdlib-only) implements the whole
concurrency-risk concentration of Phase 18 — the FIFO/bounded/no-retry egress worker, the
retry-until-ready lifecycle runner, the off-IOLoop liveness poller, the pure readiness-gate
decision, and the structural control-only `bind_steps` ordering — flipping all 35 of plan
18-02's tests from SKIPPED to PASSED with zero renaming.**

## Performance

- **Duration:** ~25 min
- **Completed:** 2026-08-09T07:39:00Z
- **Tasks:** 2 (both `type="auto" tdd="true"`)
- **Files modified:** 1 (created, outside the `mics-backend` git repo)

## Accomplishments

- **`EgressWorker`** (Task 1, EXTLINK-15): one background daemon thread per instance, draining a
  `queue.Queue(maxsize=64)` via `send_fn(item)` where every item is a zero-arg callable. No
  retry — an exception from either `send_fn` itself or the item callable it invokes is caught
  and dropped, never re-queued. Overflow drops the NEWEST item via stdlib `put_nowait` (no
  custom ring buffer) and records the loss via `dropped` (int) + `on_drop(item)`. `alive`
  tracking is edge-triggered: `on_alive_change` fires exactly once when
  `consecutive_failures == fail_threshold` (not `>=`, so it never re-fires on the 4th, 5th, ...
  failure) and once on the first success after a failing streak. `enqueue()` never blocks/raises;
  `stop()` is idempotent with a bounded `Thread.join(timeout=...)`.
- **`LifecycleRunner`** (Task 2, EXTLINK-16): `start_async(run_ctx)` spawns a daemon thread and
  returns immediately — `on_run_start` is never called inline. The thread retries
  `on_run_start` + `is_ready()` every `retry_interval_s` (on the injected `clock`/`sleep` pair)
  until `is_ready()` returns True (`ready=True`) or the injected clock shows `timeout_s` elapsed
  (`ready=False`). A raising `on_run_start` is caught, stored in `last_error`, and retried rather
  than treated as fatal.
- **`build_run_ctx`** returns exactly the 6 `RUN_CTX_KEYS` (asserted internally) and
  **`validate_wait_timeout`** rejects `None` explicitly (distinct `ValueError` message
  containing `"wait_timeout_s"`), rejects non-`int` (including `bool`, a deliberate extra guard
  beyond what any test exercises), and enforces the `[5, 600]` inclusive range.
- **Readiness gate** (EXTLINK-13): `GATE_PROCEED`/`GATE_SKIP`/`GATE_TIMEOUT`/`GATE_WAIT` plus a
  pure `ready_gate_decision(all_ready, skip_requested, elapsed_s, timeout_s)` implementing the
  locked priority order proceed > skip > timeout > wait, with an inclusive timeout boundary
  (`elapsed_s >= timeout_s`). `gate_timeout_s(configs)` takes the max `wait_timeout_s` across
  only `required: True` sources and returns `0` (zero-overhead, install-no-pre-state signal)
  when the list is empty or nothing is required.
- **`bind_steps(socket_plan)`** (EXTLINK-18): returns the 4-step control-only tuple
  `(BIND_STEP_TRACKERS, BIND_STEP_LIVENESS, BIND_STEP_EGRESS, BIND_STEP_LIFECYCLE)` when
  `socket_plan["socket_type"] is None`, and prepends `BIND_STEP_SOCKET` for any other
  `socket_type` (`"ROUTER"`, `"SUB"`, ...) — a structural guarantee, not an `if` branch plan
  18-10 could get wrong. `socket_plan` is taken as a plain dict parameter; this module never
  imports the wire module.
- **`LivenessPoller`** (Task 2, EXTLINK-07): one daemon thread per instance evaluating a
  zero-arg `predicate` every `interval_s`, caching the result in a plain `alive` attribute
  (cheap read, never touches the predicate). `poll_once()` never raises — a raising predicate
  counts as not-alive and is swallowed — and `on_change(new_value)` fires only on a transition.
  Proven off the shared IOLoop by construction: `start()` spawns its own thread and returns
  immediately even if the predicate blocks; `stop()` sets a stop flag and does a bounded join,
  and the stop flag is checked strictly *after* the predicate call returns inside `poll_once`,
  so an in-flight blocking predicate that outlives `stop()`'s bounded join can never fire a late
  `on_change` against a torn-down `View`.

## Task Commits

No commits were made to `/home/ido/pi-mirror` — that repo is user-owned and the plan's own
`<verification>` block forbids any git command that mutates it, matching plans 18-01 through
18-04's precedent (same phase). `external_hardware_runtime.py` is the plan's sole deliverable
file and lives entirely outside the `mics-backend` git repository this executor operates in, so
there is nothing to `git add`/commit per task in that repo either.

**Plan metadata:** committed separately in `mics-backend` (this SUMMARY.md + STATE.md +
ROADMAP.md).

## Files Created/Modified

- `/home/ido/pi-mirror/autopilot/autopilot/hardware/external_hardware_runtime.py` (298 lines) —
  `EgressWorker`, `LifecycleRunner`, `LivenessPoller`, `RUN_CTX_KEYS`, `build_run_ctx`,
  `validate_wait_timeout`, `GATE_PROCEED`/`GATE_SKIP`/`GATE_TIMEOUT`/`GATE_WAIT`,
  `ready_gate_decision`, `gate_timeout_s`, `BIND_STEP_SOCKET`/`_TRACKERS`/`_LIVENESS`/`_EGRESS`/
  `_LIFECYCLE`, `bind_steps`. Zero `autopilot` references (`grep -n autopilot` on the file
  returns nothing), stdlib-only imports (`queue`, `threading`, `time`), Python 3.7-compatible
  syntax (no walrus, no `X | Y` runtime annotations, no subscripted builtin generics).

## Decisions Made

- **`EgressWorker`/`LivenessPoller` stop mechanism:** both use a `threading.Event` checked via a
  bounded `get(timeout=0.1)` / `Event.wait(interval_s)` inside the worker loop, rather than a
  `None` sentinel pushed through the queue. A sentinel `put()` could itself block indefinitely
  against a full queue with a wedged consumer — exactly the hang the plan's "bounded join so a
  wedged item cannot hang `Task.end()`" requirement exists to prevent.
- **`drain(timeout)`** is a hand-rolled poll loop over `queue.Queue.unfinished_tasks` (the same
  counter `Queue.join()` uses internally) because stdlib `Queue.join()` accepts no `timeout`
  argument at all in any supported Python version.
- **`gate_timeout_s`'s config-dict shape** (`required: bool` + `wait_timeout_s: int`) matches
  18-02-SUMMARY.md's recorded inference from `18-CONTEXT.md`; no renaming judgment call was made
  here — it was pinned by plan 18-02's tests before this plan started.
- **298-line final size:** the first complete draft was 348 lines (auto-fixed via docstring
  trimming, not a code-structure change) after the initial banner comments, module docstring,
  and class docstrings were written at full explanatory length. Per the plan's own instruction
  ("TRIM PROSE AND DOCSTRINGS to their one-line core instead" of splitting), every class and
  function docstring was condensed to its rationale core across four edit passes, each
  re-verified against the full 35-test suite before proceeding, landing at 298 — under the
  plan's own <=300 soft cap and well under the project's 500-line hard ceiling.

## Deviations from Plan

None — plan executed exactly as written. Both tasks passed their `<verify>`/`<done>` blocks on
the first implementation attempt; the only rework was the post-hoc line-count trim described
above, which changed no behavior (re-verified green after every edit).

## Issues Encountered

None. Plan 18-05's sibling file (`external_hardware_wire.py`) already existed on disk at
execution time (built by the parallel in-flight plan) with some of its own tests failing — out
of scope per this plan's explicit instruction not to create, edit, or block on that file; left
untouched.

## User Setup Required

None — no external service configuration required. No git command was run against
`/home/ido/pi-mirror` (user-owned repo) and no git command was run on the Pi.

## Next Phase Readiness

- Plan 18-10 (`.bind()` / `ExternalHardware`) can now construct `EgressWorker`, `LifecycleRunner`,
  and `LivenessPoller`, and call — never re-implement — `bind_steps`, `ready_gate_decision`,
  `gate_timeout_s`, `validate_wait_timeout`, and `build_run_ctx` from this module.
- All three of plan 18-02's contract files (`test_extlink_egress.py`,
  `test_extlink_lifecycle.py`, `test_wait_extlink_ready_transitions.py`; 35 tests) now PASS with
  zero skips, confirmed via a fresh full-suite run completing in 2.78s (well under the plan's
  15s / no-hang requirement).
- No blockers for 18-10/18-11/18-12.

---
*Phase: 18-extlink-pi-transport*
*Completed: 2026-08-09*

## Self-Check: PASSED

`/home/ido/pi-mirror/autopilot/autopilot/hardware/external_hardware_runtime.py` verified present
on disk (298 lines). No commit hashes are claimed by this plan (no git mutations were made to
`/home/ido/pi-mirror`, per the plan's own constraint, matching plans 18-01 through 18-04's
precedent) — nothing to verify via `git log` for that file. Fresh test runs confirmed live above:
`pytest -q tests/test_extlink_egress.py` (7 passed), `tests/test_extlink_lifecycle.py
tests/test_wait_extlink_ready_transitions.py` (28 passed), `-k control_only` (4 passed, 17
deselected), `-k liveness_poller` (7 passed, 14 deselected), and the combined 3-file run (35
passed in 2.78s). `grep -n autopilot` on the deliverable file returns nothing.
