---
phase: 34-mics-link-sdk-client-package
plan: 03
subsystem: sdk
tags: [heartbeat, reconnect, state-machine, pure-functions, tdd]

# Dependency graph
requires: ["34-01"]
provides:
  - "mics_link.heartbeat — pure heartbeat scheduling (heartbeat_due, HeartbeatSchedule, DEFAULT_HEARTBEAT_S=1.0) over an injected clock"
  - "mics_link.reconnect — pure connect/disconnect state machine (next_state, ConnectionState, STATE_CONNECTED/STATE_DISCONNECTED) over synthetic monitor events"
affects: [34-06]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Pure function + injected clock/callback, mirroring external_hardware_runtime.py's ready_gate_decision style — zero sockets, zero threads, testable with synthetic input"
    - "Docstrings must avoid the literal substrings 'zmq'/'sleep'/'threading' even in prose describing their absence — the plan's own hygiene grep is substring-based, not semantic (recurs from 34-01's wire.py fix)"

key-files:
  created:
    - sdk/src/mics_link/heartbeat.py
    - sdk/src/mics_link/reconnect.py
    - sdk/tests/test_heartbeat_scheduling.py
    - sdk/tests/test_reconnect_state_machine.py
  modified: []

key-decisions:
  - "MONITOR_CONNECTED/MONITOR_DISCONNECTED/MONITOR_RETRIED defined locally in reconnect.py with a TODO(34-06) reconciliation comment — plan 34-02's transport.py had not landed in this worktree at execution time, per the plan's own fallback instruction."
  - "reconnect.py's decision-6 guarantee (never reference a sequence counter) is enforced by a tokenize-based test, not a naive line-grep — a per-line startswith check false-failed on the module's own multi-line docstring explaining the decision, fixed during GREEN before committing."

requirements-completed: [SDK-05, SDK-07]

# Metrics
duration: ~20min
completed: 2026-08-30
---

# Phase 34 Plan 03: Heartbeat scheduling + reconnect state machine Summary

**Two pure state machines — `heartbeat_due`/`HeartbeatSchedule` (1.0s default, traffic-suppressed) and `next_state`/`ConnectionState` (edge-only `on_state_change(bool)`, exception-contained, `seq`-blind) — built with zero sockets, zero threads, and injected clocks/events throughout.**

## Performance

- **Duration:** ~20 min
- **Started:** 2026-08-30 (after worktree base correction to `abb0229f`)
- **Completed:** 2026-08-30T08:32:42Z
- **Tasks:** 2/2 completed, both TDD (RED then GREEN)
- **Files modified:** 4 created, 0 modified

## Accomplishments

- `mics_link.heartbeat` implements SDK-05's scheduling half: `heartbeat_due(now, last_send_at,
  interval_s)` is a pure boundary check (`>=`, inclusive), `HeartbeatSchedule` wraps it with an
  injected clock, `DEFAULT_HEARTBEAT_S = 1.0` is documented against the `ExtlinkDemo` fixture's
  `stale_ms: 3000` (1:3 keepalive ratio) and against Windows' pre-3.11 wait-timer granularity
  (SDK-14). `note_sent()` on every outbound frame suppresses the heartbeat while real traffic
  flows (decision 2), verified with a simulated 120-frame 60Hz burst.
- `mics_link.reconnect` implements SDK-07's decision half: `next_state` is a plain dict-lookup
  pure function; `ConnectionState` fires `on_state_change(bool)` on edges only, contains a
  raising callback (logged at WARNING, never propagates), counts `MONITOR_RETRIED` without
  treating it as an edge (decision 4), and structurally never touches a sequence counter
  (decision 6) — enforced by a tokenize-based test that only flags `seq` as a NAME/OP code
  token, not as prose.
- Both modules verified `zmq`/`sleep`/`threading`-substring-free and well under the 300-line
  soft limit (65 and 95 lines respectively).
- Full `sdk/` suite (53 tests, including 34-01's wire/selfcheck/hygiene suites) is green with
  both new modules in place; the package-wide import-hygiene AST walk (auto-discovers new
  modules, no per-file registration needed) passed without modification.

## Task Commits

Each task followed RED (failing test) → GREEN (implementation) TDD:

1. **Task 1 RED: failing heartbeat scheduling tests** - `f54b85d` (test)
2. **Task 1 GREEN: mics_link.heartbeat implementation** - `f77db58` (feat)
3. **Task 2 RED: failing reconnect state machine tests** - `9bae12d` (test)
4. **Task 2 GREEN: mics_link.reconnect implementation + test self-fix** - `69e9d67` (feat)

_No refactor commit was needed for either task — GREEN implementations satisfied the RED tests
without a subsequent cleanup pass._

## Files Created/Modified

- `sdk/src/mics_link/heartbeat.py` - `DEFAULT_HEARTBEAT_S`, `heartbeat_due()`,
  `HeartbeatSchedule` (`.due()`, `.note_sent()`, `.interval_s`); stdlib-only, no clock waits,
  no socket import
- `sdk/src/mics_link/reconnect.py` - `MONITOR_CONNECTED`/`MONITOR_DISCONNECTED`/
  `MONITOR_RETRIED` (defined locally, TODO(34-06) reconciliation), `STATE_CONNECTED`/
  `STATE_DISCONNECTED`, `next_state()`, `ConnectionState` (`.apply()`, `.apply_all()`,
  `.state`, `.connected`, `.retries`)
- `sdk/tests/test_heartbeat_scheduling.py` - boundary cases, `FakeClock`-driven schedule
  tests, 60Hz burst suppression, interval override, explicit-`now` argument
- `sdk/tests/test_reconnect_state_machine.py` - transition table cases, the 7-event
  Pi-restart sequence asserting exactly 3 callback invocations, `None`-callback safety,
  raising-callback containment, retries counter, tokenize-based `seq`-absence guard

## Decisions Made

- `MONITOR_*` event-name constants are defined locally in `reconnect.py` rather than imported
  from `transport.py`, because plan 34-02 (parallel wave) had not landed `transport.py` in this
  worktree at execution time — exactly the fallback the plan's own `<interfaces>` section
  anticipated. Flagging for plan 34-06: reconcile so there is exactly one definition, not two
  independently-maintained copies of the same three strings.
- Kept the docstring hygiene lesson from 34-01 in mind proactively but still tripped it twice
  (heartbeat.py's own literal "sleep"/"threading" in prose, reconnect.py's "libzmq" containing
  the substring "zmq") — both caught by re-running the plan's exact verify greps before
  committing, not by the test suite itself (the hygiene AST guard only checks real imports/
  identifiers, not docstring prose; the plan's `<verification>` block's grep is a separate,
  stricter, substring-based check).

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] `heartbeat.py`'s own docstring failed the plan's substring hygiene grep**
- **Found during:** Task 1, immediately after GREEN, while running the plan's own
  `<verification>` grep commands proactively (not part of the pytest suite)
- **Issue:** The module docstring's prose describing "no `time.sleep`... no threading"
  contained the literal substrings `sleep` and `threading`, which the plan's own
  `grep -rn "sleep\|threading" sdk/src/mics_link/heartbeat.py` verification step checks for
  and would fail on — the same class of self-inflicted failure 34-01 hit with `wire.py` and
  the word "zmq".
- **Fix:** Reworded the docstring to describe the guarantee ("no concurrency primitives, no
  blocking wait of any kind", "never waits or pauses execution") without the forbidden
  substrings.
- **Files modified:** `sdk/src/mics_link/heartbeat.py`
- **Verification:** `grep -rn "sleep\|threading" sdk/src/mics_link/heartbeat.py` — 0 matches;
  `cd sdk && python3 -m pytest -q tests/test_heartbeat_scheduling.py` — still 11/11 pass
- **Committed in:** `f77db58`

**2. [Rule 1 - Bug] `reconnect.py`'s docstring/comments contained "libzmq", tripping the "zmq" substring grep**
- **Found during:** Task 2, immediately after GREEN, same proactive verification pass
- **Issue:** Prose explaining the messaging-library origin of the retry event used the word
  "libzmq" twice, which contains the literal substring "zmq" — fails
  `grep -rn "zmq" sdk/src/mics_link/reconnect.py`.
- **Fix:** Reworded both occurrences to "the underlying messaging library" without naming it.
- **Files modified:** `sdk/src/mics_link/reconnect.py`
- **Verification:** `grep -rn "zmq" sdk/src/mics_link/reconnect.py` — 0 matches;
  `cd sdk && python3 -m pytest -q tests/test_reconnect_state_machine.py` — still 12/12 pass
- **Committed in:** `69e9d67`

**3. [Rule 1 - Bug, self-caught] RED-phase test's own `seq`-absence guard false-failed on a valid docstring**
- **Found during:** Task 2, GREEN phase — first run of the new test against the real
  `reconnect.py` implementation
- **Issue:** `test_module_never_references_a_sequence_counter`'s original implementation
  checked each source line individually for `line.strip().startswith("#"/'"""')`, which
  cannot recognize a line that is INSIDE a multi-line docstring but does not itself start
  with the triple-quote delimiter — it failed on `reconnect.py`'s own decision-6 docstring
  paragraph explaining why no sequence counter exists, which is exactly the prose the test
  is supposed to permit.
- **Fix:** Rewrote the check using `tokenize.generate_tokens` to inspect only `NAME`/`OP`
  token types (real code identifiers/operators), ignoring `STRING` and `COMMENT` tokens
  entirely — so prose anywhere (docstring or `#` comment) is always permitted, and only an
  actual `seq`-named identifier or attribute access in code would fail it.
- **Files modified:** `sdk/tests/test_reconnect_state_machine.py`
- **Verification:** `cd sdk && python3 -m pytest -q tests/test_reconnect_state_machine.py` —
  12/12 pass
- **Committed in:** `69e9d67` (same commit as the GREEN implementation, since the test itself
  was still in its RED-to-GREEN transition when the bug was found)

---

**Total deviations:** 3 auto-fixed (all Rule 1 — 2 self-inflicted docstring-hygiene bugs
matching 34-01's precedent, 1 self-caught test-logic bug). No scope creep: all three fixes
were required to satisfy this plan's own stated verification bar, discovered and fixed before
any commit landed with the bug present.
**Impact on plan:** None beyond the fixes themselves — final commits are clean of both issues.

## Issues Encountered

The worktree's `HEAD` did not match the mandated base at the start of this plan
(`merge-base HEAD abb0229f...` returned an unrelated ancient commit, not `abb0229f` itself).
Per the `<worktree_branch_check>` setup step, verified the working tree was clean, confirmed
`abb0229f6657ab77bd57cf1e7c72a46557fdb0bf` was a legitimate existing commit (`docs(phase-34):
update tracking after wave 1`) with proper phase-34 ancestry, then ran
`git reset --hard abb0229f6657ab77bd57cf1e7c72a46557fdb0bf` before any other work.

## User Setup Required

None — no external service configuration required. Both modules are pure and importable
with zero optional dependencies.

## Next Phase Readiness

`sdk/src/mics_link/heartbeat.py` and `sdk/src/mics_link/reconnect.py` are ready for plan
34-06 to wire against a real ZMQ monitor and IO thread. Plan 34-06 must additionally
reconcile the `MONITOR_*` constants once `transport.py` (34-02) is confirmed landed —
currently two potential definitions exist (this plan's local one, and whatever 34-02
produced in its own worktree) and only one should survive. No other blockers.

---
*Phase: 34-mics-link-sdk-client-package*
*Completed: 2026-08-30*

## Self-Check: PASSED

All 5 claimed files verified present on disk (`heartbeat.py`, `reconnect.py`,
`test_heartbeat_scheduling.py`, `test_reconnect_state_machine.py`, this SUMMARY). All 4 task
commits (`f54b85d`, `f77db58`, `9bae12d`, `69e9d67`) verified present in `git log`.
