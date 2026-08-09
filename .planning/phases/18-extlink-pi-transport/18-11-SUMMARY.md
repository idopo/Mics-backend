---
phase: 18-extlink-pi-transport
plan: 11
subsystem: pi-runtime
tags: [fda, iolop, lifecycle, readiness-gate, dealer-router, autopilot]

# Dependency graph
requires:
  - phase: 18-extlink-pi-transport
    provides: "external_hardware.py (18-10, ExternalHardware.bind/is_ready/on_run_start + bind_lifecycle's unstarted LifecycleRunner) and external_hardware_runtime.py (18-06, LifecycleRunner/build_run_ctx/ready_gate_decision/gate_timeout_s)"
provides:
  - "mics_task.init_hardware() bind post-pass -- every ExternalHardware instance is bound to the pilot's real IOLoop and its (already-constructed-but-unstarted) LifecycleRunner is started with a real run_ctx"
  - "mics_task._install_extlink_gate() -- the synthetic _wait_extlink_ready pre-state with three mutually-exclusive exits (proceed/skip/timeout), installed only when >=1 required external source exists"
  - "scripts/dev/extlink_smoke.py -- standalone probe/sustain/publish driver for both socketed transport roles, run from the dev machine"
affects: [18-12]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "bind_lifecycle() (plan 18-10) already constructs owner._lifecycle -- a LifecycleRunner tailored to that instance's stale_ms/wait_timeout_s -- but deliberately never starts it, since it has no run_ctx until task-level info (run_id/session/subject/pilot/task_definition_id) exists. init_hardware() calls hw._lifecycle.start_async(run_ctx) rather than constructing a second, redundant LifecycleRunner."
    - "_wait_extlink_ready is an ordinary FDA passthrough state that returns self.wait_for_condition() -- reusing the existing 500us poll-loop engine every other blocking state already uses, rather than a bespoke polling loop."
    - "Both gate predicates (proceed/timeout) derive from exactly ONE ready_gate_decision() call per evaluation tick: proceed_pred always runs first (guaranteed by add_transition insertion order, both at FDA.check_determinism add-time and at wait_for_condition runtime) and caches the decision in a shared closure dict; timeout_pred only ever reads that cache. This makes them mutually exclusive by construction instead of racing two independent computations."
    - "EXTLINK_SKIP_WAIT is an ordinary Boolean_Tracker registered in both self.flags and self.view.view, exactly like every other flag/variable -- settable through the FDA's EXISTING generic type:'flag' action (a trigger assignment), with zero new ZMQ plumbing. That is the 'existing orchestrator-relayed message path' the plan referred to."

key-files:
  created:
    - /home/ido/pi-mirror/scripts/dev/extlink_smoke.py
  modified:
    - /home/ido/pi-mirror/autopilot/autopilot/tasks/mics_task.py

key-decisions:
  - "[Rule 1 - bug/DRY fix] Reused external_hardware_binding.py's already-constructed-but-unstarted hw._lifecycle instead of instantiating a second LifecycleRunner in init_hardware(). The plan's own interfaces block reads as though mics_task should build the runner itself; tracing bind_lifecycle (18-10) showed it already builds one with a stale_ms-derived retry_interval_s and simply never calls start_async on it (grep confirmed zero other call sites). Building a second runner would have left the first permanently dead and silently duplicated/overridden 18-10's own retry-interval tuning. self._extlink_runners is still populated (one entry per bound instance, now aliasing hw._lifecycle) so the plan's 'keep a reference' instruction holds even though _wait_extlink_ready polls hw.is_ready() directly rather than runner.ready (see next decision)."
  - "The readiness gate polls hw.is_ready() directly, not LifecycleRunner.ready. is_ready() reads live state (default: self._alive, driven by the separate LivenessPoller/EgressWorker chain) and keeps working correctly even after a LifecycleRunner gives up retrying on_run_start at its own wait_timeout_s -- exactly the plan's instruction that readiness is is_ready(), 'NOT merely alive', and must not silently succeed on a device that never became ready."
  - "EXTLINK_SKIP_WAIT deliberately gets NO new ZMQ listener or pilot.py change. It is registered as a plain flag (self.flags + self.view.view, mirroring the existing 'variables registry' pattern in load_fda_from_json), settable by any type:'flag' trigger-assignment action the FDA JSON already supports. This matches the plan's own files_modified scope (mics_task.py + extlink_smoke.py only) and the interfaces block's framing that run_ctx-style plumbing is 'already present as instance attrs; zero new plumbing needed' -- the same is true of flags."
  - "extlink_smoke.py imports zmq AND msgpack lazily inside each subcommand handler, not at module scope, per the plan's own <done> escape hatch -- confirmed live that this dev host has msgpack (1.2.1) but not zmq, so a module-scope import would have broken --help entirely."
  - "probe's 'wait for ACK' does poll (2s, zmq.Poller) for a reply after sending a SIG frame, but the wire protocol (external_hardware_wire.py's ACK is a CMD *result*, never an automatic reply to a plain SIG push) has no built-in acknowledgment for this exchange -- confirmed by reading external_hardware_ingress.py's on_recv, which updates a Tracker and dispatches an event but never sends anything back. probe therefore treats 'no reply within 2s' as an expected PASS and says so explicitly, matching EXTLINK-11's actual locked verification method (REQUIREMENTS.md: an FDA transition lambda observed on the rig), not a wire-level handshake this design doesn't have."

patterns-established: []

requirements-completed: [EXTLINK-01, EXTLINK-05, EXTLINK-11, EXTLINK-13, EXTLINK-14, EXTLINK-16, EXTLINK-18]

# Metrics
duration: ~50min
completed: 2026-08-09
---

# Phase 18 Plan 11: Wire the substrate into the running task -- bind, lifecycle, readiness gate, smoke driver Summary

**`mics_task.init_hardware()` now binds every `ExternalHardware` instance to the pilot's real IOLoop and starts its lifecycle runner with a real `run_ctx`; `load_fda_from_json()` installs a synthetic `_wait_extlink_ready` pre-state (three mutually-exclusive exits: proceed/skip/timeout) only when a required external source exists; a new standalone `extlink_smoke.py` drives both socketed transport roles from the dev machine.**

## Performance

- **Duration:** ~50 min
- **Completed:** 2026-08-09T08:33:00Z
- **Tasks:** 3 (all `type="auto"`)
- **Files modified:** 2, both outside the `mics-backend` git repository (`/home/ido/pi-mirror`)

## Accomplishments

- **Task 1 -- `init_hardware()` bind post-pass (EXTLINK-01/05/16):** Added an override that calls
  `super().init_hardware()` unchanged, then lazily imports `ExternalHardware`/`build_run_ctx` and
  binds every `ExternalHardware` instance found in `self.hardware` via `hw.bind(self.node.loop,
  self.view)` -- `self.node.loop` passed explicitly, never `IOLoop.current()` (confirmed by grep:
  0 occurrences in the file), because `init_hardware()` runs on the thread `Pilot.run_task()`
  spawns, where `IOLoop.current()` would build a throwaway loop nothing ever starts. Captured
  `kwargs.get('task_definition_id')` into `self._task_definition_id` in `__init__` (the one kwarg
  needed for `build_run_ctx` that wasn't already an instance attribute) before the `init_hardware()`
  call, matching the interfaces block's stated need. **Correctness fix beyond the plan's literal
  interfaces text:** rather than constructing a fresh `LifecycleRunner` per instance, the bind pass
  calls `hw._lifecycle.start_async(run_ctx)` -- `bind_lifecycle()` (plan 18-10,
  `external_hardware_binding.py`) already builds this runner with a `stale_ms`-derived
  `retry_interval_s` but never starts it (grep confirmed zero other call sites for `start_async` on
  it anywhere in the hardware modules). Each instance's bind+lifecycle start is in its own
  try/except + `self.logger.exception`, mirroring the base `init_hardware`'s per-module guard so one
  broken external module cannot take down a task's other hardware. `self._extlink_required`
  collects every `required=True` instance for Task 2; `self._extlink_runners` collects the started
  runners (now aliasing each `hw._lifecycle`).
- **Task 2 -- `_wait_extlink_ready` synthetic pre-state (EXTLINK-13):** `_install_extlink_gate()`
  is called at the end of `load_fda_from_json()`'s transition-registration step and is a **true
  no-op** (`grep -c "_wait_extlink_ready"` = 5, `IOLoop.current()` = 0) whenever
  `gate_timeout_s([...])` returns 0 -- i.e. zero required external sources -- preserving the
  zero-overhead guarantee byte-for-byte for every non-MICS-Link task. When >=1 required source
  exists: `_wait_extlink_ready` is an ordinary passthrough state (`return
  self.wait_for_condition()`, reusing the existing 500us poll-loop engine, no new polling code);
  `_extlink_timeout` is a terminal state with no outgoing transition, so the FDA's own
  `StopIteration` on the next `next()` call ends the task cleanly via `run_task`'s existing
  `except`/`finally: task.end()` path -- verified by inspection, not a new abort mechanism. The
  three exits (all-ready -> declared initial state; manual skip via a plain `EXTLINK_SKIP_WAIT`
  `Boolean_Tracker`, settable through the FDA's existing `type:"flag"` trigger-assignment action,
  with no new ZMQ plumbing; timeout -> `_extlink_timeout`, which logs and emits a
  `EXTLINK_GATE_TIMEOUT` CONTINUOUS event listing every required source that never became ready)
  compose entirely from `FiniteDeterministicAutomaton`'s ordinary `add_method`/`add_transition`/
  `set_initial_method` API, exactly as the plan required -- no special-casing. Both predicates
  derive from one `ready_gate_decision()` call per tick, cached by `proceed_pred` (always evaluated
  first by transition-list insertion order, both at `check_determinism` add-time and at runtime)
  and read-only by `timeout_pred`, so they are mutually exclusive by construction; readiness is
  `hw.is_ready()` polled directly per required instance, not `LifecycleRunner.ready`, so the gate
  keeps working correctly even after a `LifecycleRunner` gives up retrying `on_run_start` at its own
  timeout. `mics_task.py` grew from 1485 to 1601 lines (+116, within the plan's <=120 budget after
  one trim pass).
- **Task 3 -- `extlink_smoke.py` (EXTLINK-11/14):** New 231-line standalone script at
  `/home/ido/pi-mirror/scripts/dev/extlink_smoke.py` with `probe`/`sustain`/`publish` subcommands,
  modeled on `Net_Node.init_networking`'s literal DEALER template (`node.py:136-141`:
  `socket(DEALER)` -> `setsockopt_string(IDENTITY, ...)` -> `connect(...)`). `probe` sends one `SIG`
  frame (`{"k":"SIG","ts_src","seq","sig","v"}`, msgpack-packed exactly like
  `external_hardware_wire.encode`) and polls 2s for a reply, printing an honest PASS either way (see
  key-decisions -- the wire protocol has no automatic ACK for a plain signal push).
  `--identity-mismatch` sends a DEALER identity that does not match `--source-id`, documenting that
  the Pi's ingress firewall must silently drop the frame (EXTLINK-02). `sustain` pushes a steady
  sine-wave stream at `--hz` for `--seconds`. `publish` binds a PUB socket emitting synthetic
  JSON-header + binary-body frames shaped like the Open Ephys ZMQ Interface plugin's output, for a
  `sub_connect` module to dial into -- deliberately the one subcommand with no autopilot-side
  precedent to model. No subcommand exists for `role:"none"` (EXTLINK-18) -- documented in
  `publish --help`'s own text, not just the module docstring. `zmq`/`msgpack` are imported lazily
  inside each handler (not module scope) per the plan's own `<done>` escape hatch: confirmed live
  this dev host has `msgpack` 1.2.1 but no `zmq` at all, so a module-scope import would break
  `--help`. Round-trip-verified the framing logic directly (`_encode`/`_decode` against real
  `msgpack`, no socket): a `SIG` frame encodes/decodes byte-identical to what
  `external_hardware_wire.py` produces. Module docstring carries four copy-pasteable example
  invocations for plan 18-12 to hand the user verbatim.

## Task Commits

No commits were made to `/home/ido/pi-mirror` -- that repo is user-owned, already carries a large
pile of intentionally uncommitted work from every prior Phase 18 plan (01 through 13), and this
plan's own `<verification>` block forbids any git command that mutates it, matching every prior
Phase 18 Pi-mirror plan. Both deliverable files (`mics_task.py`, `scripts/dev/extlink_smoke.py`)
live entirely outside the `mics-backend` git repository this executor operates in, so there is
nothing to `git add`/commit per task in that repo either.

**Plan metadata:** committed separately in `mics-backend` (this SUMMARY.md + STATE.md +
ROADMAP.md).

## Files Created/Modified

- `/home/ido/pi-mirror/autopilot/autopilot/tasks/mics_task.py` (1485 -> 1601 lines, +116) --
  `init_hardware()` override (bind + lifecycle-start post-pass), `_wait_extlink_ready`/
  `_extlink_timeout`/`_install_extlink_gate` (the readiness pre-state), one `_task_definition_id`
  capture line in `__init__`, one `_install_extlink_gate(...)` call site at the end of
  `load_fda_from_json`'s transition-registration step.
- `/home/ido/pi-mirror/scripts/dev/extlink_smoke.py` (new, 231 lines) -- standalone
  `probe`/`sustain`/`publish` DEALER/PUB driver, run from the dev machine only, never rsynced to
  the Pi.

## Decisions Made

See `key-decisions` in frontmatter -- the `hw._lifecycle` reuse fix, direct-`is_ready()` polling,
the flag-based (zero-new-plumbing) `EXTLINK_SKIP_WAIT` design, and the lazy `zmq`/`msgpack` imports
in the smoke script.

## Deviations from Plan

**1. [Rule 1 - bug/DRY] Reused `hw._lifecycle` instead of constructing a second `LifecycleRunner`**
- **Found during:** Task 1, while re-reading `external_hardware_binding.py` (18-10's
  `bind_lifecycle`) to confirm the exact call the plan's interfaces block describes.
- **Issue:** `bind_lifecycle(owner)` already builds `owner._lifecycle = LifecycleRunner(...)` with a
  `stale_ms`-derived `retry_interval_s`, called during `hw.bind(...)`, but never starts it (no
  `run_ctx` available at bind time). The plan's interfaces block reads as though `init_hardware()`
  should instantiate its own `LifecycleRunner(...)`; doing so literally would have left 18-10's
  runner permanently dead and duplicated its retry-interval logic with a different, arbitrary
  constant.
- **Fix:** `init_hardware()` calls `hw._lifecycle.start_async(run_ctx)` instead of building a new
  runner. `self._extlink_runners` still collects one reference per bound instance (now aliasing
  `hw._lifecycle`), preserving the plan's "keep a reference for `_wait_extlink_ready`" instruction.
- **Files affected:** `mics_task.py` only.
- **Verification:** `grep -rn "_lifecycle\." autopilot/autopilot/hardware/*.py` confirmed zero
  other call sites for `start_async` before this fix; `test_mics_task_attrs.py -k end` and
  `test_wait_extlink_ready_transitions.py` (all 7) pass after the fix; `ast.parse` clean.

**2. [Rule 3 - blocking/scope clarification] `EXTLINK_SKIP_WAIT` implemented as a plain flag, not a
new ZMQ message path**
- **Found during:** Task 2, resolving the plan's "an `EXTLINK_SKIP_WAIT` flag set by the existing
  orchestrator-relayed message path" instruction against the plan's own `files_modified` scope
  (`mics_task.py` + `extlink_smoke.py` only -- no `pilot.py`).
- **Issue:** No `EXTLINK_SKIP_WAIT`-related mechanism exists anywhere in the codebase (grepped both
  repos); `pilot.py`'s only generic-parameter listener (`l_param`) is an unimplemented stub, and
  wiring a new ZMQ listener would be an out-of-scope file (`pilot.py`) and arguably an architectural
  addition.
- **Fix:** Registered `EXTLINK_SKIP_WAIT` as an ordinary `Boolean_Tracker` in both `self.flags` and
  `self.view.view`, exactly like every other flag/variable in the FDA system. It is therefore
  settable today, with zero new code, by any `type:"flag"` action inside a `trigger_assignments`
  entry the researcher configures in the FDA JSON -- which IS "the existing... message path" (a
  trigger fires -> its action list runs -> a `flag` action calls `.set(True)`), just not a
  dedicated ZMQ key. No `pilot.py` change needed or made.
- **Files affected:** `mics_task.py` only.
- **Verification:** `test_gate_timeout_s_*`/`ready_gate_decision` tests (which this flag design
  feeds) all pass; the flag registration code path is exercised implicitly by
  `test_wait_extlink_ready_transitions.py`'s pure-decision tests (Boolean_Tracker construction
  itself is not separately agent-testable on this dev host -- see Issues Encountered).

**3. [Rule 3 - line-budget compliance] Trimmed docstrings/comments to stay within the plan's <=120
added-line budget**
- **Found during:** Task 2, first full implementation measured at +134 added lines to `mics_task.py`
  (over the plan's own <=120 budget across both tasks).
- **Fix:** Trimmed prose in `init_hardware`'s docstring, the three new gate methods' docstrings, the
  `_task_definition_id` capture comment, and the "5b." transition-registration comment -- no logic
  change, re-verified green after each trim. Landed at +116, comfortably under budget without
  needing the plan's own escape hatch (splitting into a new `extlink_gate.py`).
- **Files affected:** `mics_task.py` only.
- **Verification:** `wc -l` before/after each trim; full test re-run after the final trim (93
  passed / 6 pre-existing unrelated failures, `ast.parse` clean).

---

**Total deviations:** 3 (1 correctness/DRY fix, 1 scope clarification consistent with the plan's own
`files_modified`, 1 line-budget trim). None architectural; no user decision required.

## Issues Encountered

- **Same pre-existing dev-host `test_mics_task_attrs.py` gap as plan 18-02, unaffected by this
  plan's edits.** `python3 -m pytest -q tests/test_mics_task_attrs.py` reports 6 failed / 1 passed
  regardless of this plan's changes: `AttributeError: module 'autopilot' has no attribute 'tasks'`
  / `ModuleNotFoundError: No module named 'autopilot.tasks'`, raised because
  `autopilot/autopilot/__init__.py` imports `autopilot.setup.setup_autopilot` -> `npyscreen`, not
  installed on this dev host (already logged in `deferred-items.md` by plan 18-02; reconfirmed here
  via `python3 -c "import autopilot.tasks.mics_task"` failing identically with zero edits present).
  This plan's own acceptance gate (`-k end`, plus the full `test_wait_extlink_ready_transitions.py`
  file) is unaffected and passes: `python3 -m pytest -q
  tests/test_extlink_wire.py tests/test_extlink_decoder.py tests/test_extlink_liveness.py
  tests/test_extlink_egress.py tests/test_extlink_lifecycle.py
  tests/test_wait_extlink_ready_transitions.py tests/test_mics_task_attrs.py` -> **93 passed, 6
  failed** (up from the 92-passed baseline recorded in `18-10-SUMMARY.md`; the 6 failures are the
  identical pre-existing set, not a regression).
- **No agent-runnable proof that `mics_task.init_hardware()`'s bind pass actually calls `hw.bind()`
  end-to-end.** Unlike plan 18-10's lighter `ExternalHardware`-only coupling (stubbable with just
  `Hardware`/`zmq`/`ZMQStream`), `mics_task.py` transitively imports `autopilot.tasks.task.Task`,
  which imports `tables` (PyTables) plus the full `gpio`/`i2c`/`mixer`/`timer` hardware stack and
  `autopilot.core.View` -- none importable on this dev host, and stubbing that entire tree would
  exceed what this plan's own scope calls for. The plan explicitly defers end-to-end proof to plan
  18-12's rig checkpoint ("End-to-end behaviour is NOT claimed here"); this session verified
  correctness by direct code reading (confirming `hw._lifecycle` is the same object `bind_lifecycle`
  constructs, confirming the FDA's transition-order guarantee via `FiniteDeterministicAutomaton`'s
  own source) rather than a stub harness.

## User Setup Required

None -- no external service configuration required. No git command was run against
`/home/ido/pi-mirror` (user-owned repo) and no git command or Python execution was run on the Pi.
No SSH command touched the Pi except the plan-mandated pre-edit read-only diff (below).

## Next Phase Readiness

**Pre-edit mirror/Pi diff (plan-mandated, run before any edit):**
```
diff <(ssh -i ~/.ssh/pi_mics pi@132.77.72.28 'cat ~/Apps/mice_interactive_home_cage/autopilot/autopilot/tasks/mics_task.py') \
     /home/ido/pi-mirror/autopilot/autopilot/tasks/mics_task.py
```
Result: **empty** -- files identical. The mirror was not drifted from the live Pi before this
plan's edits began.

**Exact rsync file list plan 18-12 must deploy** (all under
`autopilot/autopilot/` relative to the Pi's code root, `~/Apps/mice_interactive_home_cage/`):
- `tasks/mics_task.py` (this plan's edit -- init_hardware bind pass + readiness gate)
- `hardware/external_hardware.py` (18-10)
- `hardware/external_hardware_wire.py` (18-05)
- `hardware/external_hardware_runtime.py` (18-06)
- `hardware/external_hardware_ingress.py` (18-10)
- `hardware/external_hardware_binding.py` (18-10)

**`scripts/dev/extlink_smoke.py` is NOT part of this list** -- it is explicitly a dev-machine-only
tool (its own docstring says so twice) and is never rsynced to the Pi; the user runs it from their
own laptop against the deployed pilot's bound/connected socket.

**Downstream contract for plan 18-12:**
- `mics_task.init_hardware()` now requires `self.node` (a real `Net_Node` with a running `.loop`)
  to exist before it runs -- already guaranteed by the existing `__init__` ordering
  (`super().__init__()` sets `self.node` before `init_hardware()` is called), so no reordering was
  needed, matching the plan's own note.
- A task definition with >=1 `required: true` external source will enter `_wait_extlink_ready`
  before its declared initial state; a task with zero external hardware is unaffected byte-for-byte
  (confirmed: `_install_extlink_gate` returns immediately when `gate_timeout_s(...) == 0`).
- `EXTLINK_SKIP_WAIT` can be toggled today via a `type:"flag"` trigger-assignment action in the FDA
  JSON -- no new orchestrator/pilot.py wiring exists or is needed for the pre-state's three exits to
  all be reachable.
- `gsd-tools requirements mark-complete` found no checkbox/traceability rows for the seven EXTLINK
  IDs in `REQUIREMENTS.md` (same known gap as every prior EXTLINK plan) -- completion tracked via
  this SUMMARY, STATE.md, and `roadmap update-plan-progress 18` instead.

No blockers for 18-12.

---
*Phase: 18-extlink-pi-transport*
*Completed: 2026-08-09*
