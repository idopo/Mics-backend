---
phase: 18-extlink-pi-transport
plan: 10
subsystem: pi-hardware
tags: [zmq, tornado, decorators, hardware-base-class, egress, liveness, autopilot]

# Dependency graph
requires:
  - phase: 18-extlink-pi-transport
    provides: "external_hardware_wire.py (18-05, codec/dtype/stale/liveness/role pure logic) + external_hardware_runtime.py (18-06, EgressWorker/LifecycleRunner/LivenessPoller/bind_steps/readiness-gate concurrency primitives), both autopilot-free"
provides:
  - "external_hardware.py — the author-facing ExternalHardware base class + @signal/@event/@command/@decoder decorators, importing the two Wave-1 siblings and never the reverse"
  - "external_hardware_ingress.py — the ingress firewall (_on_recv body), split out to hold the main file under its 300-line budget"
  - "external_hardware_binding.py — the five per-bind-step wiring helpers (socket/trackers/liveness/egress/lifecycle), split out for the same reason"
affects: [18-11, 18-12, 26-10]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "A plain function stored as a class attribute (cls._extlink_decoder = the @decoder method) is auto-bound via Python's function descriptor protocol when read off an INSTANCE (owner._extlink_decoder) — so run_decoder(owner._extlink_decoder, frames, ...) correctly receives self=owner without a manual types.MethodType/lambda wrapper. Verified by direct reproduction (see Issues Encountered) since no agent-runnable test can import this Hardware-coupled file."
    - "alive has exactly one writer, recompute_alive() (external_hardware_binding.py) — both EgressWorker.on_alive_change and LivenessPoller.on_change land on the same private function, composing (liveness AND NOT egress_failed) and writing the Tracker only on a net change."
    - "Liveness predicate work (stale-sweep + the actual liveness read) is folded entirely into LivenessPoller's own daemon-thread callback (bind_liveness's _liveness_tick) rather than a PeriodicCallback on the shared IOLoop — sidesteps PeriodicCallback.start()/stop() not being thread-safe entirely, per the plan's own 'simpler option' escape hatch."
    - "3-way file split (external_hardware.py / _ingress.py / _binding.py) instead of the plan's explicitly authorized 2-way split (main + ingress only) — kept the author-facing surface (decorators, __init_subclass__, __init__, bind() dispatch, send(), release()) in the main file at 239 lines, well under the 300-line budget, with the per-bind-step wiring and the ingress firewall each in their own Hardware-coupled sibling."

key-files:
  created: []
  modified: []
  # No files were newly created or modified by THIS session — all three files already existed,
  # complete and correct, on disk from the interrupted prior session. See Issues Encountered.

key-decisions:
  - "No code changes were made in this session. The interrupted agent's on-disk deliverable was read in full, ast-parsed, and independently verified against every must_haves/key_links/verify assertion in the plan via a stub-module harness (autopilot.hardware.Hardware, HardwareState, autopilot.utils.Events.Event, zmq, zmq.eventloop.zmqstream all faked, since none of the four are importable on this dev host) that actually instantiates ExternalHardware subclasses, calls bind()/release()/send()/is_ready(), and exercises the role=none construction-time ValueError, the bare/called decorator forms, the dtype-resolution TypeError, and the decoder-binding path end to end. 19/19 checks passed; the file was found complete, not merely syntactically valid."
  - "The extra external_hardware_binding.py split goes beyond the plan's literal escape-hatch text (which authorized splitting only the ingress firewall), but is not treated as a Rule 4 architectural question: it is a same-directory, same-plan, non-schema, non-service code-organization choice that keeps the deliverable's own <verify> greps and all <done> criteria passing against the main file (confirmed literally, including the LivenessPoller/bind_steps/validate_role_liveness/_egress grep lines), and it left the main file at 239 lines — well inside the 300-line budget with headroom to spare. Documented here per the plan's own 'record the split in the SUMMARY' instruction rather than escalated."

patterns-established:
  - "Hardware-coupled Pi-mirror files that cannot be imported on the dev host (missing npyscreen/zmq/tornado) can still be verified pre-rig by constructing a minimal stub-module harness (types.ModuleType + sys.modules injection) that fakes just the base class's contract (Hardware.__init__'s bare kwargs['type'] access, .logger, .get_state()) and the two native-dependency modules (zmq, zmq.eventloop.zmqstream) — this proved the decorator/binding/lifecycle logic end to end without a real rig, closing the gap the plan itself says has 'no agent-runnable proof'."

requirements-completed: [EXTLINK-01, EXTLINK-02, EXTLINK-04, EXTLINK-05, EXTLINK-07, EXTLINK-08, EXTLINK-12, EXTLINK-14, EXTLINK-15, EXTLINK-16, EXTLINK-18]

# Metrics
duration: 35min
completed: 2026-08-09
---

# Phase 18 Plan 10: `external_hardware.py` — the ExternalHardware base class + four decorators Summary

**Verified (not rewritten) the interrupted prior session's `external_hardware.py` (239 lines) + two newly-discovered Hardware-coupled sibling files (`external_hardware_ingress.py`, `external_hardware_binding.py`) that together implement the full author-facing MICS-Link API — decorators, `__init_subclass__` type contract, `.bind()`'s `bind_steps`-dispatched socket/Tracker/liveness/egress/lifecycle wiring, and a `release()` that can never raise — against every must_have in the plan via a stub-module harness, since the file cannot be imported on this dev host.**

## Performance

- **Duration:** 35 min (this resumption session; original interrupted session's duration unknown — no commit/timestamp trail since no git mutation ever touches `/home/ido/pi-mirror`)
- **Started:** 2026-08-09T07:48:00Z (approx, continuing from STATE.md's last-recorded session boundary)
- **Completed:** 2026-08-09T08:22:00Z
- **Tasks:** 2 planned (both found already complete on disk)
- **Files modified:** 0 (all three deliverable files were already complete and correct)

## Accomplishments

- **Confirmed `external_hardware.py` (239 lines) survived the ENOSPC interrupt intact and complete.** `ast.parse` succeeds; both plan tasks' full scope is present: the four decorators (`signal`/`event`/`command`/`decoder`, both bare and called forms), `__init_subclass__` collecting `_extlink_signals`/`_extlink_events`/`_extlink_commands`/`_extlink_decoder` with dtype resolved at class-build time via `resolve_dtype` (raising `TypeError` at import time on an unresolvable signal, verified live), `ExternalHardware.__init__` (the `kwargs.setdefault("type", ...)` trap avoided, `validate_wait_timeout` called, `socket_plan(kwargs)` computed, `validate_role_liveness` **called** — not re-implemented — against `getattr(type(self), "liveness_hook", None) is not None`), `bind(ioloop, view)` dispatching on `bind_steps(self._plan)`, `send(item)` as a one-line `_egress.enqueue` delegate, `get_state()` returning `None`, and `release()` as the mandatory idempotent, never-raising override.
- **Discovered and verified two Hardware-coupled sibling files** (`external_hardware_ingress.py`, 63 lines; `external_hardware_binding.py`, 150 lines) that the interrupted session had already split out — beyond what the plan's own escape hatch literally authorized (ingress-only) — to hold the main file under its 300-line budget. Confirmed both are 3.7-compatible, `ast.parse`-clean, and correctly wired (`external_hardware.py` imports both, never the reverse of the wire/runtime siblings).
- **Built and ran a stub-module test harness** (`autopilot`, `autopilot.hardware.Hardware`/`HardwareState`, `autopilot.utils.Events.Event`, `zmq`, `zmq.eventloop.zmqstream.ZMQStream` all faked) that actually imports and instantiates `ExternalHardware` subclasses on this dev host — something the plan itself states has "no agent-runnable proof." 19 targeted checks all passed: zero-signal class instantiates and binds cleanly; `role: "none"` opens no socket yet registers `.alive`, starts egress/liveness/lifecycle; `role: "none"` **without** a class-level `liveness_hook` raises `ValueError` at construction (the plan's central, previously-unverified rule); bare `@command` and called `@command()` both collect; a `@signal()` with no default/annotation raises `TypeError` at class-build time; Tracker naming produces exactly `<source_id>.<signal>` and `<source_id>.alive`; `send()`/`_egress.enqueue` accepts a zero-arg callable; `release()` is idempotent and never raises, with or without a socket; `is_ready()` defaults to `_alive`.
- **Ran the full six-file agent-runnable test suite** (`test_extlink_wire.py`, `test_extlink_decoder.py`, `test_extlink_liveness.py`, `test_extlink_egress.py`, `test_extlink_lifecycle.py`, `test_wait_extlink_ready_transitions.py`): **92 passed, 0 failed** — confirms this plan's file did not disturb the two Wave-1 sibling modules. `python3 -m pytest -q tests/test_extlink*.py` (the plan's own named success-criterion command): **85 passed**.
- **Live-reproduced and closed the one real open question**: whether `owner._extlink_decoder(frames)` (a plain function fetched from `vars(klass)` in `__init_subclass__`, then stored as a class attribute) would call the `@decoder` method unbound (missing `self`). Confirmed via direct reproduction that Python's function-descriptor protocol auto-binds it when read off an instance — `owner._extlink_decoder` IS a bound method, not the raw function — so the wire module's `run_decoder(decoder_fn, frames, ...)` → `decoder_fn(frames)` call correctly receives `self=owner`. No fix needed; documented as a load-bearing, easy-to-doubt pattern in the frontmatter.

## Task Commits

No commits were made to `/home/ido/pi-mirror` — that repo is user-owned and the plan's own `<verification>` block forbids any git command that mutates it, matching every prior Phase 18 Pi-mirror plan (05/06/01-04). All three deliverable files (`external_hardware.py`, `external_hardware_ingress.py`, `external_hardware_binding.py`) were already present, complete, and untouched by this session — there is nothing to `git add`/commit in `/home/ido/pi-mirror` either way, and no code edit occurred in this session to commit anywhere.

**Plan metadata:** committed separately in `mics-backend` (this SUMMARY.md + STATE.md + ROADMAP.md).

## Files Created/Modified

None by this session. Pre-existing, verified complete (all outside the `mics-backend` git repository):
- `/home/ido/pi-mirror/autopilot/autopilot/hardware/external_hardware.py` (239 lines) — `ExternalHardware` base class, `signal`/`event`/`command`/`decoder` decorators, `__init_subclass__`, `__init__`, `bind(ioloop, view)`, `send(item)`, `on_run_start`/`on_run_stop`/`is_ready()`, `release()`.
- `/home/ido/pi-mirror/autopilot/autopilot/hardware/external_hardware_ingress.py` (63 lines) — `_on_recv`'s body (`on_recv(owner, frames)`), rate-limited decode-issue logging.
- `/home/ido/pi-mirror/autopilot/autopilot/hardware/external_hardware_binding.py` (150 lines) — the five `bind_*(owner, ...)` step helpers, `recompute_alive` (the single `alive` writer), `_on_egress_drop`/`_on_egress_alive_change`, `sweep_stale`.

## Decisions Made

See `key-decisions` in frontmatter: no code changes were needed (interrupted work verified complete via a stub-module harness that actually exercises the class, not just `ast.parse`); the 3-way file split is documented rather than re-litigated, since it satisfies every literal `<verify>`/`<done>` check in the plan and stays well under the line budget.

## Deviations from Plan

**None requiring a code change.** One pre-existing deviation from the interrupted session, evaluated and accepted rather than reworked:

**1. [Rule 3 - Blocking/organizational, already applied by the interrupted session] Three-way file split instead of the plan's authorized two-way split**
- **Found during:** Initial read-and-verify pass (before any task execution began in this session).
- **Issue:** Task 2's action text says: "If it would exceed [300 lines], split the ingress firewall into `external_hardware_ingress.py` ... rather than letting the file grow" — authorizing exactly one split target. The interrupted session also split the five `bind_*` step helpers into a third file, `external_hardware_binding.py`.
- **Fix:** None applied — evaluated in place. The main file is 239 lines (comfortably under the 300-line budget even before considering the split), all of the plan's own `<verify>` grep assertions pass against the main file specifically (confirmed literally: `IOLoop.current()` absent, `bind_steps`/`validate_role_liveness`/`_egress`/`LivenessPoller` all present), and the split touches no schema, service boundary, or tested public contract — it is a same-plan, same-directory code-organization call. Treated as within the spirit of the plan's own escape hatch rather than an architectural question requiring a stop.
- **Files affected:** `external_hardware_binding.py` (pre-existing, unmodified by this session).
- **Verification:** `wc -l` on all three files; full grep suite from the plan's own `<verify>` block re-run against `external_hardware.py` alone; stub-harness instantiation/bind/release exercised across all three files together.

---

**Total deviations:** 1 accepted-as-is (organizational, pre-existing from the interrupted session)
**Impact on plan:** None on correctness or the tested contract. No scope creep — no new files beyond the three already on disk, no rework performed.

## Issues Encountered

- **ENOSPC interruption recovery, per this task's own brief:** the deliverable file was read in full and `ast.parse`d first, per instructions, and found NOT truncated — the interrupted session had completed both of the plan's tasks before the host ran out of disk. A discovery search turned up two undocumented sibling files (`external_hardware_ingress.py`, `external_hardware_binding.py`) that `external_hardware.py` imports; both were read in full and verified equally complete.
- **Neither `zmq` nor `tornado` nor `autopilot` (transitively, via `npyscreen`) is importable on this dev host**, so none of the three deliverable files can be imported directly — matching the plan's own explicit statement that "this file itself cannot be IMPORTED on the dev host" and "there is no agent-runnable proof for a `Hardware` subclass on this host." To close this gap as far as possible without a rig, a disposable stub-module harness (`/tmp/.../scratchpad/harness.py` + two test scripts, not committed anywhere) faked the four missing dependencies (`autopilot.hardware.Hardware`/`HardwareState`, `autopilot.utils.Events.Event`, `zmq`, `zmq.eventloop.zmqstream.ZMQStream`) well enough to actually import all three real files and run 19 behavioral checks against them, including the one genuinely uncertain question in the whole file — whether the `@decoder` method is correctly bound to `self` when invoked through `run_decoder`. All 19 passed. This harness is throwaway scratch work, not a committed test — the plan's own scope explicitly defers real proof to plan 18-12's rig checkpoint.

## User Setup Required

None — no external service configuration required. No git command was run against `/home/ido/pi-mirror` (user-owned repo) and no git command or Python execution was run on the Pi itself.

## Next Phase Readiness

**Downstream contract, verbatim (Phase 26's `26-10-PLAN.md` reads this file before writing a line):**
- **`bind()` signature:** `bind(self, ioloop, view)` — exactly two arguments, dispatching on `bind_steps(self._plan)`.
- **Readiness hook:** `is_ready(self)`, defaulting to `return self._alive`. Overridable per-subclass (e.g. Phase 26's OpenEphys "recording has started" check).
- **Egress attribute:** `self._egress` (an `EgressWorker` instance), constructed in `bind_egress` as `EgressWorker(send_fn=lambda fn: fn(), maxsize=64, fail_threshold=self.egress_fail_threshold, on_drop=..., on_alive_change=...)`. Items enqueued are **zero-arg callables**. Public delegate: `def send(self, item): return self._egress.enqueue(item)`.
- **Liveness-override hook:** `liveness_hook(self, last_msg_ts_ms, now_ms, stale_ms) -> bool`, base class value `None`, **must be declared at class level** (an instance-level assignment in `__init__` is invisible to `validate_role_liveness`'s `type(self)` check and raises at construction).
- **`@decoder` signature:** `def decode(self, frames): ...` — a normal instance method; `owner._extlink_decoder` (set from `__init_subclass__`'s `vars(klass)` scan) is auto-bound via Python's function-descriptor protocol when read off an instance, so it is called downstream as `decoder_fn(frames)` (see `external_hardware_wire.run_decoder`) with `self` already bound.
- **Tracker naming:** `<source_id>.<signal_name>` per declared `@signal`, plus `<source_id>.alive` (a `Boolean_Tracker`) always — including on a zero-signal, `role: "none"` control-only class.
- **`role: "none"` dispatch:** `bind_steps(self._plan)` (18-06) structurally omits only `BIND_STEP_SOCKET`; `bind()`'s dispatch loop calls `bind_trackers`/`bind_liveness`/`bind_egress`/`bind_lifecycle` unconditionally for every remaining step — there is no `if not socket_type: return` shortcut anywhere. `validate_role_liveness` (18-05) is **called**, not re-implemented, in `__init__`.
- **Liveness location:** the predicate runs on its own `LivenessPoller` daemon thread (`bind_liveness`, `external_hardware_binding.py`) — the stale-sweep and the liveness read are both folded into the poller's own callback (`_liveness_tick`), not a `PeriodicCallback` on the shared IOLoop. The IOLoop only ever runs `_do_bind` (socket creation via `add_callback`) for this class; there is no periodic liveness work on it at all.
- **File list plan 18-12 must rsync to the rig:** `external_hardware.py`, `external_hardware_wire.py`, `external_hardware_runtime.py`, `external_hardware_ingress.py`, `external_hardware_binding.py` — all five under `autopilot/autopilot/hardware/`.

**Not claimed by this plan:** that any of this works at runtime against a real ZMQ socket or a real Tornado IOLoop. The stub-harness verification in this session goes further than a syntax check but is still not a rig proof; that remains plan 18-12's job.

`gsd-tools requirements mark-complete` found no checkbox/traceability rows for the eleven EXTLINK IDs in `REQUIREMENTS.md` (same known gap as every prior EXTLINK/CMP/DVK plan this phase) — completion tracked via this SUMMARY, STATE.md, and `roadmap update-plan-progress 18` instead.

No blockers for 18-11/18-12.

---
*Phase: 18-extlink-pi-transport*
*Completed: 2026-08-09*

## Self-Check: PASSED

All five deliverable files verified present on disk under
`/home/ido/pi-mirror/autopilot/autopilot/hardware/`: `external_hardware.py` (239 lines),
`external_hardware_ingress.py` (63 lines), `external_hardware_binding.py` (150 lines),
`external_hardware_wire.py` (18-05), `external_hardware_runtime.py` (18-06). This SUMMARY.md
verified present at `.planning/phases/18-extlink-pi-transport/18-10-SUMMARY.md`. Fresh test run:
`python3 -m pytest -q tests/test_extlink*.py tests/test_wait_extlink_ready_transitions.py` →
**92 passed, 0 failed**. No commit hashes are claimed by this plan (no git mutations were made
to `/home/ido/pi-mirror`, per the plan's own constraint, and no code edits occurred in this
session) — nothing to verify via `git log` for the deliverable files.
