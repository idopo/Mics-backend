---
phase: 34-mics-link-sdk-client-package
plan: 04
subsystem: sdk
tags: [wire-protocol, threading, command-dispatch, pytest]

# Dependency graph
requires: ["34-01"]
provides:
  - "mics_link.commands — CommandRegistry, dispatch(), CommandWorker, ACK_OK/ACK_ERROR"
  - "Synthetic-frame proof that a CMD decoded off the Pi's own encoder reaches a handler and produces a matching-cmd_id ACK"
affects: ["34-06"]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "CommandWorker's loop shape mirrors EgressWorker._run (external_hardware_runtime.py): queue.get(timeout=0.1) + threading.Event stop flag"
    - "dispatch() keeps ACK-encoding inside the recoverable path so an unencodable handler return produces an error ACK, not an IO-thread exception"

key-files:
  created:
    - sdk/src/mics_link/commands.py
    - sdk/tests/test_command_dispatch.py
  modified: []

key-decisions:
  - "MicsLinkError imported from mics_link.selfcheck (its current sole definition) rather than a new errors.py — no plan's files_modified lists errors.py, and this plan's own files_modified is limited to commands.py + its test file."
  - "commands.py stayed a single 197-line file — the plan's own size-trigger (300 lines) for splitting CommandWorker into command_worker.py was not reached, so no split and no interfaces-note update was needed."
  - "Both tasks (registry+dispatch, then CommandWorker) share the same two files, so they were developed and committed as one RED test commit covering both tasks' behavior followed by one GREEN implementation commit, rather than four separate task-scoped commits — splitting the shared files into task-specific diffs after the fact would have added risk without adding evidence."

requirements-completed: [SDK-08]

# Metrics
duration: ~20min
completed: 2026-08-30
---

# Phase 34 Plan 04: Command dispatch (CMD -> handler -> ACK) Summary

**`mics_link.commands` decodes a Pi-encoded CMD, runs its registered handler on one dedicated worker thread (never the IO thread, never the caller's), and replies with a byte-valid ACK carrying the matching `cmd_id` — proven entirely with synthetic frames built by the Pi's own encoder, since no Pi-side CMD sender exists anywhere in this codebase.**

## Performance

- **Duration:** ~20 min
- **Started:** 2026-08-30 (after worktree base correction to `abb0229`)
- **Completed:** 2026-08-30
- **Tasks:** 2/2 completed (registry+dispatch, CommandWorker)
- **Files modified:** 2 created, 0 modified

## Accomplishments

- `CommandRegistry` (`register`/`decorator`/`get`/`names`) with `MicsLinkError` on duplicate
  registration (decision 6).
- `dispatch(registry, cmd, ts_fn=wire.now_ms) -> bytes`: pure apart from calling the handler,
  never raises except `KeyboardInterrupt`/`SystemExit` (decision 2), and produces the locked
  ACK `result` shape (decision 1) across four cases — success, handler raised, unknown
  command, unencodable return value — as three explicit code branches (not one broad
  `except`) so a rig log can tell the failure modes apart.
- Encoding the ACK is itself inside the recoverable path (decision 3): a handler returning
  a numpy array or socket object still produces a valid `{"ok": False, "error":
  "unencodable result: ..."}` ACK rather than an unhandled exception.
- `CommandWorker`: one dedicated daemon thread draining a bounded `queue.Queue`, loop shape
  copied from `EgressWorker._run` (`external_hardware_runtime.py`) rather than invented —
  `queue.get(timeout=0.1)` + a `threading.Event` stop flag. `submit()` never blocks or
  raises; a full inbox (decision 5, default `maxsize=32`) drops the newest command and
  increments `dropped`. `stop(timeout=...)` is idempotent and safe on a never-started worker.
  The `ack_sink` call is wrapped in its own `try/except Exception` so a future non-`BoundedSender`
  sink that raises still cannot kill the worker.
- 18 new tests, all built against CMD frames from the Pi's real encoder
  (`pi_reference.load_pi_wire`, skip-if-absent) — including a direct assertion that the
  handler's recording thread name differs from the submitting thread's name (decision 4,
  asserted rather than assumed), and a `threading.Event`-based bounded wait instead of any
  `time.sleep` polling loop, keeping the whole suite at well under a second.

## Task Commits

Both tasks share `commands.py` and `test_command_dispatch.py`; they were developed and
committed as one RED/GREEN pair covering both tasks' behavior together, not four separate
task-scoped commits (see key-decisions above):

1. **RED — failing test suite for registry, dispatch, and worker** - `a43840b` (test)
2. **GREEN — mics_link.commands implementation** - `c37fc84` (feat)

## Files Created/Modified

- `sdk/src/mics_link/commands.py` (197 lines) — `ACK_OK`/`ACK_ERROR` key-name constants,
  `CommandRegistry`, `dispatch()`, `CommandWorker`. No `zmq` import (verified by grep, part
  of the plan's own `<verification>` block). No import of `transport.py`.
- `sdk/tests/test_command_dispatch.py` (314 lines) — 18 tests covering both tasks' `<behavior>`
  bullets, each CMD frame built with the Pi's own `encode()`.

## ACK `result` shape (locked, restated verbatim for plan 34-09's validation log)

- success: `{"ok": True, "value": <handler return>}` — a handler returning `None` is a
  success with `"value": None` (the normal shape for a fire-and-forget command).
- handler raised: `{"ok": False, "error": "<ExcType>: <message>"}`
- no handler registered: `{"ok": False, "error": "unknown command: <name>"}`
- handler returned something msgpack cannot pack:
  `{"ok": False, "error": "unencodable result: <ExcType>: <message>"}`
- `ACK_OK = "ok"` and `ACK_ERROR = "error"` are the key-name constants used to build these
  dicts, not the values themselves.

## CommandWorker: did NOT move to its own module

`commands.py` is 197 lines, under the plan's 300-line split trigger — `CommandWorker` stayed
in `commands.py`. No `<interfaces>` update is needed for plan 34-06: it should still
`from mics_link.commands import CommandRegistry, dispatch, CommandWorker, ACK_OK, ACK_ERROR`.

## Decisions Made

- `MicsLinkError` is imported from `mics_link.selfcheck` (`from .selfcheck import
  MicsLinkError`) — that module is the only place it is currently defined (checked: no plan's
  `files_modified` lists an `errors.py`, and this plan's own scope is limited to
  `commands.py` + its test file). If a later plan (34-06 or beyond) relocates
  `MicsLinkError` to a dedicated `errors.py`, this import line is the one call site in this
  file that will need updating.
- Verified independently (not just trusting the plan's stated fact) that `cmd_id` and the
  literal `"CMD"` appear nowhere in either `~/mics_core/autopilot/` or `~/pi-mirror/autopilot/`
  outside `external_hardware_wire.py` (and its `.pyc` cache) — `grep -rln cmd_id` against both
  trees returns exactly one source file each. This fact is restated in `commands.py`'s module
  docstring per the plan's `<action>` instruction.

## Deviations from Plan

None — plan executed as written. The only deliberate departure from the literal task
structure is the shared-file RED/GREEN commit grouping described above, which is a commit-
sequencing choice, not a scope or behavior deviation.

## Evidence Limitation (restate verbatim for plan 34-09's validation log)

**SDK-08 is proven this phase by synthetic frames only.** There is ZERO Pi-side
implementation of sending `CMD` or receiving `ACK` anywhere in either autopilot tree —
verified by grep across `~/mics_core/autopilot/` and `~/pi-mirror/autopilot/`, both returning
matches only inside `external_hardware_wire.py` itself. There is therefore no live round trip
to test against, on the rig or anywhere else. Every CMD frame in `test_command_dispatch.py`
is built with the Pi's real encoder (`pi_reference.load_pi_wire`), so the codec side is not
self-referential — but the dispatch/ACK side has never been exercised by an actual Pi. Do not
report SDK-08 as rig-proven.

## Issues Encountered

The worktree's initial `HEAD` was on the same unrelated ancient commit noted in plan 34-01's
summary (`b4831f7`, "able to stop and start task"). Per the mandatory
`<worktree_branch_check>` setup step, `git reset --hard abb0229f6657ab77bd57cf1e7c72a46557fdb0bf`
was run before any other work, after confirming the working tree was clean and the target
commit was a legitimate, already-existing commit in this repo's history.

## User Setup Required

None.

## Next Phase Readiness

`mics_link.commands` is ready for plan 34-06 to wire `CommandWorker`'s `ack_sink` to
`BoundedSender.enqueue` and feed it CMD dicts decoded from the transport's inbound path. No
blockers.

---
*Phase: 34-mics-link-sdk-client-package*
*Completed: 2026-08-30*

## Self-Check: PASSED

All 3 claimed files verified present on disk (`sdk/src/mics_link/commands.py`,
`sdk/tests/test_command_dispatch.py`, this SUMMARY). Both task commits (`a43840b`, `c37fc84`)
verified present in `git log`.
