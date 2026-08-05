---
gsd_state_version: 1.0
milestone: v1.0
milestone_name: milestone
status: unknown
last_updated: "2026-08-05T11:29:28.700Z"
progress:
  total_phases: 23
  completed_phases: 6
  total_plans: 72
  completed_plans: 41
  percent: 60
---

# STATE: MICS Backend

## Project Reference

See: `.planning/PROJECT.md` (updated 2026-03-15)

**Core value:** Researchers can define, modify, and deploy behavioral task logic without writing Python or restarting the Pi.
**Current focus:** Planning complete — ready to begin Phase 1

---

## Current Position

**Milestone:** M1 — ToolKit + FDA Redesign + Pi Code Editor
**Phase:** 23 — Compute Primitives + Variables — **11/12 plans done** (Wave 0 + Wave 2 plans 02/03/04 + Wave 3 plans 05/06 + Wave 4 plans 07/08 + Wave 5 plan 09 + Wave 7 plan 11 — CMP-20-23 operand-namespace consistency, frontend half). Plan 12 (Pi-side CMP-24/25 + consolidated rig checkpoint) is the last plan in the phase.
**Also outstanding:** Phase 25 plan 06 (last plan in that phase, not yet executed).
**Progress:** [██████░░░░] 60%

### Phase 26 status (2026-08-03) — PLANNED, 13 plans, verification passed

**Planning complete 2026-08-03.** Discuss → research → validation strategy → 13 plans in 4 waves →
plan-checker **VERIFICATION PASSED**. Not executed. **Blocked on Phase 18**, which it consumes.

**Waves:** W1 = 26-01/02 test contracts + **26-03 early USER-RUN OE REST-surface probe** ·
W2 = 26-04 path resolver, 26-05 artifact table+API, 26-06/07 OE clients ·
W3 = 26-08 force-stop registry, 26-09 preflight kinds, 26-10 seeded lib, 26-11 orchestrator, 26-12 React ·
W4 = 26-13 consolidated rig checkpoint.

**Defining constraint — the artifact layer is device-agnostic** (user directive: DeepLabCut and later
modules need the same file/dir handling). Three shared modules with **zero** Open Ephys knowledge, OE
as a thin adapter:

| Device-neutral | OE adapter |
|---|---|
| `api/artifact_paths.py` — tokens, 422 on unknown token, many-to-many ambiguity rule | `api/openephys_client.py` + Pi twin |
| `api/artifacts.py` + `run_artifacts` table + `api/routers/artifacts.py` — keyed `(run_id, device_name)`, `device_fields` JSONB, no OE column | `api/seed_libs/openephys.py` + `api/seed_openephys.py` |
| `api/device_stop_registry.py` — "run ended uncleanly → stop" trigger | `api/openephys_stop.py` (~20 lines) |
| `api/preflight_external_devices.py` — `external_device_unreachable` / `external_device_busy` / `artifact_path_collision`, each carrying a device name | one `DEVICE_PROBES` dict entry |

Neutrality is enforced **mechanically, not by review**: `test_device_neutral_layer` runs the whole
layer for a fabricated `FakeVideoRecorder` and greps the shared sources for `openephys` /
`Record Node` / `37497` / `experiment_number` / `recording_number`.

**Research findings that changed the design:**
1. **No disk-space endpoint exists in the OE REST API** — the user's decision was conditional ("yes
   *if* the API exposes it"), so the precheck is **dropped**, not substituted with SSH or a mount.
   The underlying risk (session dies when the disk fills) is accepted and unmitigated.
2. **OE does not return a ready-made path.** It imposes `Record Node <id>/experiment<N>/recording<M>/`
   beneath whatever directory MICS sets, so the resolved path must be **read back** via a follow-up
   `GET /api/recording`. Always read back; never predict.
3. **The collision check has no OE-side path** — no directory-listing endpoint. It becomes a MICS-side
   uniqueness check against the artifact table. **Accepted residual gap:** a folder created by hand in
   the OE GUI is invisible to it.
4. **Project/experiment resolution is ambiguous** — `Subject`↔`Project` and `Experiment`↔`Protocol`
   are both many-to-many. Decided: `LIMIT 1` (matching `preflight_validate`'s existing shortcut) +
   **warn on ambiguity** + surface the chosen pair in the API and session view. Rejected refusing to
   start (would block legitimately multi-project subjects).
5. **No new dependencies** — `requests` already pinned on the Pi, `httpx` already in `api/`. Unlike
   Phase 18, no user-run pip step.

**Rig-ordering decision:** 26-03 probes the real OE REST surface in Wave 1 and writes
`26-REST-SURFACE.md`, because every OE field name in the research came from official docs and was
never probed against this lab's instance. 26-06/07/10 depend on it; the generic layer (26-04/05) does
not and runs in parallel.

**Two planner judgement calls:** `external_device_busy` replaces an OE-specific "already recording"
kind (it generalizes, so DLC gets it free); the per-run ephys opt-out rides
`overrides.global.disabled_hardware: [names]` on the existing start-on-pilot transport — no schema
change, device-neutral, and deliberately non-sticky so a forgotten toggle can't silently cost a
recording.

**Scope added beyond the roadmap:** Phase 26 closes the orphaned-recording gap Phase 18 could only
document — reconciliation detecting an unclean run end now also commands the device to stop.

**Cross-phase gap flagged, NOT resolved here:** Phase 18's `socket_plan` has no "no transport" mode,
but EXTLINK-18 requires zero-signal control-only modules — exactly OE's control side. **Resolve during
Phase 18 execution**; Phase 26 must not fork the transport design.

### Phase 26 planning history (2026-08-03)

`26-CONTEXT.md` written. Five areas discussed and locked:

1. **Folder naming** — **project/experiment hierarchy** (user's choice over mirroring the ES run
   key). Template = lib default + per-pilot override. Collision → **refuse to start**, never suffix
   or let OE auto-increment. Researcher-editable with **token validation** at save.
   ⚠ **Coupled decision:** the hierarchy embeds mutable metadata in the path, so it is only safe
   because MICS persists the **resolved** path (below). Do not implement one without the other.
2. **Recording record** — resolved absolute path + OE start/stop timestamps + host, in a **small
   dedicated table keyed `(run_id, device_name)`** (chosen so DeepLabCut can reuse it; rejected
   columns-on-`session_runs` and the `overrides` JSON). Project/experiment names **snapshotted**.
   **Incomplete-coverage flag** when OE wasn't recording for the run's full duration. Surfaced in
   the React session/run view, not just the API.
3. **Markers** — MICS always brackets with run-start/stop; everything else author-placed. Auto trial
   markers **rejected** (would couple to `INC_TRIAL_COUNTER`, which tasks must send explicitly, so a
   task omitting it would look like an ephys bug). Free text + same-toolkit autocomplete. Payload
   carries `label|run|trial`. **Every send dual-logged to ES** — that diff against what landed in the
   recording *is* Phase 28's measurement, making the validation phase nearly free.
4. **Bad state** — already-RECORDING → **fail the gate, never take over** (the lease cannot see
   manual GUI use, so it may be a colleague's session). Disk precheck **only if the OE REST API
   exposes free space** — research must confirm, don't invent it. Mid-run stop → log, flip `alive`,
   surface prominently.
5. **Delivery + opt-out** — `OpenEphys` ships as a **seeded first-party lib**
   (`api/seed_libs/openephys.py`, following Phase 23's `compute_ops.py` pattern) so ephys works after
   a deploy with no manual upload. A **per-run override** lets a researcher run without ephys without
   editing the toolkit.

**Scope added beyond the roadmap's success criteria:** Phase 26 now **closes the orphaned-recording
gap** Phase 18 could only document — when backend reconciliation detects an unclean run end, it also
issues the REST call returning OE to IDLE, not just the lease release. This puts device-specific REST
logic in the backend for the first time; it must live in a small dedicated module (`api/main.py` and
`toolkit_dispatch.py` are both near their size limits).

### Phase 18 status (2026-08-05) — RE-PLANNED, 12 plans · ✅ RE-VERIFICATION PASSED

**The stale-verdict warning is cleared.** The plan-checker was re-run on 2026-08-05 against the
post-`64bbd2d` plans. Iteration 1 returned **ISSUES FOUND** (3 blockers, 3 warnings, 3 info);
a planner revision closed them; iteration 2 returned **VERIFICATION PASSED**. Phase 18 is approved
for `/gsd:execute-phase 18`.

**All three blockers were follow-through gaps left by the `role: "none"` revision** — the revision
added the role but did not carry it into the test contracts or the two paths a socketless device
forces:

1. **The `108190e` liveness-override rule was implemented but verified nowhere.** "`role: "none"`
   requires an explicit liveness override, raise at construction" existed only as prose in
   `18-10-PLAN.md`, with no test row in 18-01/18-02 and no row in `18-VALIDATION.md` — the rule
   landed *after* `64bbd2d` rewrote the plans. It was also unreachable by the agent, sitting in
   `external_hardware.py`, which imports `autopilot`. **Fixed:** the predicate is now two pure
   functions in the `autopilot`-free wire module — `requires_liveness_override(role)` and
   `validate_role_liveness(role, has_override, class_name="")` — pinned in 18-01's `<interfaces>`,
   tested by five `test_role_none_*` cases, implemented in 18-05, **called** (not re-implemented)
   by 18-10, and given a rig-side deliberate-breakage step 6b in 18-12.
2. **The egress seam would have forked Phase 26.** `18-02` pinned `EgressWorker(send_fn, …)` with
   item-model tests, while `26-10-PLAN.md:90,169-171` already writes
   `self._egress.enqueue(lambda: …)` — a zero-arg callable that the item model would store as data
   and never invoke. **Fixed by adopting Phase 26's model**, which is the only one that works for a
   socketless device: the base class has no transport-specific `send_fn` to supply, so "how to send"
   belongs in each call site's closure. Pinned verbatim in 18-02/18-06/18-10 as
   `EgressWorker(send_fn=lambda fn: fn(), …)`, attribute spelled **`_egress`**.
3. **The now-mandatory liveness override would have blocked the shared IOLoop.** 18-10 put liveness
   on a `PeriodicCallback` on the pilot's `Net_Node` loop — the same loop `18-06` already keeps
   egress *off* because "a blocking HTTP PUT there freezes the STOP channel." Blocker 1 made this
   certain rather than possible: every control-only module must carry an override, and a
   control-only device's only liveness signal is an outbound call (OE polls `GET /api/status`).
   **Fixed:** new `LivenessPoller` in `external_hardware_runtime.py` (daemon thread, cached `alive`,
   edge-triggered `on_change`, never-raising `poll_once`), six contract cases in 18-02 including one
   asserting the predicate runs on a different thread ident. The IOLoop keeps only a cached read.

**Warnings also closed:** the ≤300-line "split the wire module" escape hatch was **removed** in
18-05/18-06 — a path-loaded module (`spec_from_file_location`) has no package, so a split would have
broken re-export and silently killed the agent-side test loop, the exact property `18-VALIDATION.md`
exists to defend; trim prose instead. `18-VALIDATION.md` frontmatter is now `approved` /
`nyquist_compliant: true` (`wave_0_complete` correctly still false). Git-rule wording unified across
the seven Pi-touching plans: no git that **mutates** `/home/ido/pi-mirror`, no git on the Pi at all,
read-only inspection of the local mirror permitted.

**Advisories folded in after the PASS** (iteration-2 A1–A7, applied directly to the plans):
- **`alive` now has exactly one writer, `_recompute_alive()`.** Liveness and the egress
  failure-threshold both flip device health, and EXTLINK-15 requires *one* signal regardless of
  direction — separate writers meant a liveness tick could silently overwrite the `False` the egress
  counter had just written.
- **`PeriodicCallback.start()/stop()` must go through `ioloop.add_callback`** — they use
  `call_later`/`remove_timeout`, which are not thread-safe, and both `BIND_STEP_LIVENESS` and
  `release()` run on the task thread. Same reason socket creation was already routed that way.
- `LivenessPoller.stop()` must not fire `on_change` after stop is requested (bounded join means an
  in-flight HTTP GET can outlive `release()` and touch a torn-down View) — new
  `test_liveness_poller_no_on_change_after_stop`.
- `-k drop_newest` was timing-dependent (the worker could free a slot mid-enqueue); now pinned
  deterministic via a `started` Event.
- `on_drop` must name the lost item by `__qualname__`, not log a bare `<lambda>` — otherwise
  EXTLINK-15's "the loss is *recorded*" is not actually satisfied under the callable model.
- `liveness_hook` must be declared at **class level**; an instance-level assignment is invisible to
  `validate_role_liveness` and raises at construction (fails closed, but confusingly).

**Downstream obligation created for Phase 26 — CLOSED 2026-08-05.** Phase 18's new construction rule
meant a `role: "none"` module without a class-level `liveness_hook` would fail at construction, and
no Phase 26 plan mentioned the hook at all. Fixed in 26-10 / 26-13 / 26-VALIDATION.md:

- **26-10 `<interfaces>`** — corrected `bind(ioloop)` → **`bind(ioloop, view)`**, added
  `liveness_hook = None` to the consumed surface, and spelled out the construction rule plus the
  class-level-vs-instance trap (`validate_role_liveness` reads `type(self)`, so a hook assigned in
  `__init__` is invisible and raises confusingly). Also pinned that `alive` has one writer in the
  base (`_recompute_alive`) — this lib must never write the Tracker directly.
- **26-10 Task 1** — `liveness_hook(self, last_msg_ts_ms, now_ms, stale_ms)` is now a specified,
  mandatory class-level method: one `oc.get_status(...)` call, True on a status dict, False on any
  error, never raises, all three timestamp args deliberately ignored (they exist for the
  data-arrival default a socketless device can't use). **Requires a bounded client timeout** —
  `LivenessPoller.stop()` uses a bounded join, so an untimed GET against an unreachable host
  outlives `release()` and stacks at the `stale_ms / 2` poll rate. The vague "the readiness hook
  (whatever the shipped base class names it)" line now states explicitly that readiness ≠ liveness:
  `liveness_hook` answers *is the box reachable*, readiness answers *has recording started*.
- **26-10 Task 1 verify** — AST check extended to require `liveness_hook` **in the class body**.
- **26-10 Task 2** — documents the hand-entered `pilot_hardware_config.config` shape in the seeded
  lib's module docstring (the hardware-libs UI renders it), including that `role: "none"` is
  mandatory with no default, and why `host` is still required with no inbound socket (egress target
  + device-lease key). New fifth seeding test asserting the class-level hook on the **stored**
  source, so a drifted seed is caught in CI rather than on the rig.
- **26-13 step 4a** (new rig check, count 9 → 10) — proves on real hardware that liveness and
  readiness are distinct (box on but IDLE ⇒ `alive=true`, not ready), that the outbound poll flips
  `alive` when the box is powered off while the behavioural session keeps running (EXTLINK-07: loss
  of liveness is never automatically fatal), that **STOP stays responsive while the poll hits an
  unreachable host** — the check that actually proves the poll is off the shared IOLoop — and that
  the construction rule holds, with an explicit repin-to-good-version afterward.

**Phase 26 re-verified 2026-08-05 after those edits.** The checker returned ISSUES FOUND — **2
blockers, both introduced by the `c1d5629` edit itself**, which is exactly what a re-verification is
for:

1. **The new `liveness_hook` spec contradicted a locked CONTEXT decision.** `c1d5629` specified the
   hook as "True if `get_status` returns a dict" — pure reachability. But `26-CONTEXT.md` locks
   *"Recording stops mid-run → log, flip `alive`, and surface prominently"*, and after the edit
   `liveness_hook` was the ONLY base-class mechanism a lib had for that. A box that answers but has
   dropped out of RECORD would have read `alive=true` forever, silently dropping a locked decision
   with no test failing. **Fixed:** the predicate is composite — reachable AND, while a run is
   active, still in `RECORD`.
2. **The mandated bounded HTTP timeout had nowhere to live.** `c1d5629` required a client timeout
   "comfortably under the poll interval", but neither client plan shipped a factory taking one —
   `DEFAULT_TIMEOUT_S = 5.0` is the only knob, and at the canonical `stale_ms: 3000` the poll is
   every 1.5 s, so the default is 3.3× the interval: the exact stacking the new text warned about.
   Worse, the plan that would have to supply it (26-07) executes a wave *earlier* than 26-10, so the
   executor's only outs were a private helper or a hand-rolled transport. **Fixed:** `make_client(timeout_s)`
   added to 26-07/26-06 (mirrored in the 26-01/26-02 contracts), and `stale_ms` + `liveness_timeout_s`
   are now documented as a **pair** with a stated invariant (`liveness_timeout_s < stale_ms / 2000`),
   defaulting to `6000` / `2.0` rather than inheriting Phase 18's canonical `3000`.

**The composite predicate lives in `oc.liveness_ok(status, run_active)`, not in the seeded lib** —
`api/seed_libs/openephys.py` imports `ExternalHardware` and therefore `autopilot`, so nothing in it
is unit-testable on the dev host. Factoring the decision into the `autopilot`-free client (same
family as `decide_start` / `is_already_recording`) is what makes the locked mid-run rule provable by
an agent instead of only at the rig. 26-02 pins four cases (`-k liveness_ok`); a validation row was
added, since before this the decision was proven by nothing.

Also fixed: 26-13's resume-signal still said "nine checks" while the gate needs ten (a blocking
human gate that under-counts can be satisfied with step 4a never run); the new AST guard matched the
*first* class in the file rather than `OpenEphys` by name; `26-11`'s device-neutrality check used
`grep -c`, which exits 1 on zero matches — the desired result — aborting its `&&` chain before
`docker compose up`; `is_ready()` is now named directly and added to 18-10-SUMMARY's mandatory
contract list, so 26-10's pointer to it resolves.

**Iterations 3–6 (2026-08-05).** The checker ran four more times. Iterations 3–5 found issues my own
fixes had introduced (a default timeout colliding with Phase 18's canonical `stale_ms`; a single
teardown flag doing two jobs, which stranded a box in RECORD after a failed IDLE; a stale sentence
contradicting the fix three sections below it). **Iteration 4's was the serious one:** `on_run_stop`
gated the IDLE only on "did the IDLE succeed yet", not on "is this recording ours" — so attempting a
run against a box a colleague was already recording on would deterministically truncate their data
at teardown, violating `26-CONTEXT.md`'s locked *"never take over"*. Now gated on `_record_issued`,
with the same ownership check added to the backend force-stop (compare the box's `parent_directory`
against the artifact row's `target_path`).

Iteration 5 exposed that the relative-vs-absolute contract for `target_path` was **never pinned** —
`26-04` said relative, `26-08` compared against an absolute, `26-10` said only "derived from". The
ownership check would have silently never matched, making the force-stop a permanent no-op while
still closing the artifact row. `target_path` is now ABSOLUTE via a required `artifact_root` config
key, pinned identically in 26-01/26-04/26-08/26-10/26-13 and asserted by two new Wave-0 tests.

Iteration 6's findings were **original Phase 26 gaps**, not fallout from the edits: `coverage_complete`
was set True unconditionally on every clean stop (wrong for exactly the runs the flag exists to
catch — `required: false` against a busy box, a failed `on_run_start`, the opt-out); the per-run
opt-out still created a phantom artifact row, making 26-13 check 9 unachievable; and the ownership
test was `xfail` with no plan ever retiring the marker, so it carried zero signal.

### Phase 19 created — the mid-run alarm had no home

Iteration 6 also surfaced that `26-CONTEXT.md`'s locked *"surface prominently in pilot status"* is
implemented by **nothing**, and cannot be: `OrchestratorState` carries no tracker values, so
`WS /ws/pilots` cannot carry `openephys.alive`, and the React app has no device-health surface
(`grep -rn "alive" web_ui/react-src/src` → nothing). The cause is a scope-boundary mistake, not a
forgotten task — `alive` is EXTLINK-07's, and **Phase 18's NOT-in-scope list explicitly excludes**
*"Per-pilot health dashboard React page + WS forwarding via orchestrator"*. Phase 26 locked a
decision that depends on infrastructure Phase 18 deliberately deferred and nothing picked up.

Resolved as **new Phase 19** (placed right after 18, its true home) (device-neutral, matched on the `.alive` suffix so any
`ExternalHardware` device lights it). Building it inside 26 would put Phase 18 substrate in the
OpenEphys phase; reopening 18 would invalidate a verdict earned over six iterations. **Phase 19 is NOT a
blocker for 26** — detection ships in 26 (the `alive` flip, its CONTINUOUS event, the loud log
line), presentation ships in Phase 19. `26-CONTEXT.md` now records the deferral and its cost explicitly,
rather than shipping the reduced scope by omission.

⚠ **Phase 26 has NOT been re-checked since the iteration-6 fixes** — the checker ran against the
pre-fix state, and the `26-CONTEXT.md` amendment is newer still. Re-run it before
`/gsd:execute-phase 26`. Phase 26 is blocked on Phase 18 regardless.

**Gap fixed 2026-08-03 — `role: "none"` (control-only, no inbound transport).** Phase 26 planning
exposed that two transport roles were not enough. The plans already handled a class with zero
`@signal`, but `socket_plan` returned only `router_bind` or `sub_connect` — both open a socket. A
device whose entire inbound story is an *outbound poll* (OpenEphys: liveness via HTTP
`GET /api/status`) was being forced to declare a role, pick a port, and bind a socket nothing ever
connects to. Evidence it was already biting: plan 18-12 had made its control-only demo lib
`sub_connect` because no better option existed.

Resolution (EXTLINK-18 amended; `18-CONTEXT.md` § Transport roles carries the full block):
- Third role value `"none"` — `socket_plan` returns a plan with **no socket**, invents no port, and
  does not fall back to a default. `identity_ok` and the `@decoder` path are inapplicable.
- Config validation must not require `listen_port`/`connect_port` for this role; `host` **is** still
  required, for egress, and is still the lease key.
- `.bind()` does everything else — `.alive` tracker, liveness poll, egress worker, lifecycle hooks —
  so a control-only module participates fully in the readiness gate. Explicitly **not** a reduced
  path.
- **`role: "none"` requires an explicit liveness override, enforced by raising at construction.** The
  default predicate is "a message arrived within `stale_ms`", which a socketless module never
  satisfies — it would sit permanently `alive=False` and hang the gate with no diagnosis. Consistent
  with EXTLINK-12's import-time `TypeError` for an unresolvable `@signal` dtype. Silently defaulting
  to `alive=True` was rejected: that is exactly the "device is off but we think it's fine" failure OE's
  HTTP check exists to catch.
- Rejected: making `role` optional/absent to mean "no transport" — an explicit value validates cleanly
  and distinguishes deliberate control-only from a forgotten field.

**Side effect: EXTLINK-18 is no longer rig-only.** Three new agent-runnable validation rows
(`-k role_none` on both sides, `-k control_only` on the Pi); the rig row survives but now proves only
end-to-end wiring, not the mechanism.



**Planning complete 2026-08-03.** Research → validation strategy → 12 plans in 5 waves →
plan-checker **VERIFICATION PASSED** (all 18 EXTLINK IDs covered, no same-wave file collisions,
every Pi rule honoured). Not executed. Next action is `/gsd:execute-phase 18`, but note the
execution order still puts 23 and 25 ahead of it.

**Wave structure:** W1 = 18-01/02/03 (test contracts, agent) + 18-04 (msgpack pin, USER-RUN) ·
W2 = 18-05/06/07/08 · W3 = 18-09/10 · W4 = 18-11 · W5 = 18-12 (single consolidated rig checkpoint).

**Three research findings that changed the design** (all contradicted the pre-research context):
1. **`msgpack` is NOT on the Pi** — verified by SSH into `~/.venv/autopilot`; nothing in the codebase
   uses it (wire format is JSON). Genuine new dependency, pin needed for **Python 3.7.3**. Plan 18-04
   is a USER-RUN step that resolves the pin by real `pip install` rather than guessing.
2. **The backend reconciliation the lease depends on does not exist.** `orchestrator_station.py::_run_watchdog`
   is dead code (thread-start commented out) with a broken staleness rule (wall-clock since
   `started_at`, never refreshed — would kill every normal multi-minute session). Built in 18-09,
   keyed on `_redis_touch`'s `updated_at`.
3. **IOLoop thread hazard:** `init_hardware()` runs in the Pilot's `run_task` thread, not the thread
   driving the IOLoop. `IOLoop.current()` inside `.bind()` would silently create a loop nothing polls.
   Must pass `self.node.loop` and register via `add_callback()`.

**Load-bearing design constraint discovered during validation planning:** `import autopilot.*` fails
on the dev host (npyscreen missing). So all pure logic — wire codec, `@decoder` dispatch, stale-policy
resolver, liveness predicate, egress worker, ready-gate decision — lives in **`autopilot`-free sibling
modules** (`external_hardware_wire.py`, `external_hardware_runtime.py`), loaded by the Wave-0 tests via
`importlib.util.spec_from_file_location` (by path, never a dotted import). Without this split every Pi
test in the phase becomes USER-RUN and the agent-side feedback loop disappears.

**Cross-phase coupling with Phase 23 plan 07** (which executed concurrently in another session on
2026-08-03): 23-07 added `PREFLIGHT_ISSUE_KINDS` (frozenset) to `api/routers/toolkit_dispatch.py` —
now the single registry of preflight issue kinds — plus a reserved-issue-shape helper precedent.
Phase 18 adds **two** kinds (`device_held`, `extlink_config_invalid`), both registered there and both
mirrored into `HardwareCheckModal.tsx`'s `PreflightIssue` union (a frontend file the roadmap's
original file list omitted). Lease preflight tests go in `api/tests/test_view_key_preflight.py`, not
`test_toolkit_dispatch.py`.

**Known acceptance-criterion trap, recorded so it is not re-introduced:** do NOT assert that
`on_run_stop()` emits a CONTINUOUS event visible in ES. `event_dispatcher.stop()` runs before
`task.end()`/`release()` in `pilot.py`'s teardown, so the event provably races. Verify stop by
effect — device idle, lease released.

**Residual risk accepted and documented in 18-08/18-09/18-12:** Phase 18's safety net releases the
lease row and marks the run errored, but does **not** command the foreign device to stop — the
backend has no channel to one, by design. A crashed pilot can leave an external recorder running.
Closing that belongs to Phase 26, which owns the OE control channel.

---

*Superseded planning note (kept for provenance):* `18-CONTEXT.md` was **revised** in a discussion session driven by
`docs/open_ephys_integration.pdf`, to generalize the phase so **OpenEphys is its first consumer**.
`18-01-PLAN.md` and `18-02-PLAN.md` were written against the pre-revision context and are now
**superseded** — moved to `.planning/phases/18-extlink-pi-transport/superseded/` (Phase 23
precedent). Neither had been executed, so nothing is lost but planning time.

**Five additions to the `ExternalHardware` substrate** (all new, none previously specified):
1. **Transport roles** — `router_bind` (original: MICS SDK dials in) + `sub_connect` (new: Pi dials
   out to a foreign PUB), with a per-lib `@decoder` hook. Required because the OE ZMQ Interface
   plugin is a PUB in its own JSON+binary format and will never speak our MessagePack envelope.
2. **Liveness split from staleness** — `alive` now means *reachable*, via a lib-supplied liveness
   hook (default: data-within-`stale_ms`; OE overrides to poll HTTP status). Signal freshness stays
   with the per-signal stale policy. **Amends EXTLINK-07**, which assumed every source sends `HB`.
3. **Egress path** — FIFO one-worker-per-device outbound queue, fire-and-forget with **no retry**
   (a late marker corrupts alignment worse than a missing one), bounded with drop-newest +
   recorded loss, N consecutive failures flip `alive`.
4. **Run lifecycle hooks** — `on_run_start(run_ctx)` async + retried inside the wait window,
   `on_run_stop()` on all Pi paths plus a backend safety net for the Pi-crash case (otherwise OE
   records forever). **Amends EXTLINK-13**: the readiness gate now keys on "all required *ready*"
   (lib-defined, defaults to `alive`) rather than "all required alive".
5. **Device lease** — backend-side arbitration keyed on normalized `host`, hard-blocking as a new
   preflight issue kind naming the holder. Needed because the OE box is shared across pilots
   (sequentially). Auto-released by the same reconciliation that stops orphaned recordings, plus a
   manual force-release.

**User decisions locked this session:** Pi owns both OE channels (HTTP control + ZMQ data) for one
clock domain and one versioned lib — backend owns *only* the lease. v1 OE scope is firing rate +
recording + save-folder naming, with the folder path logged into MICS (so the ZMQ data path is v1,
not deferred). The OE machine is never used by two rigs simultaneously, so the lease is a safety
net with no queue/notify UX. **The TTL cable stays**; network markers run alongside it and any
cutover happens later on measured evidence.

**Correction recorded:** the OE ZMQ plugin transfers **spikes, not firing rate** — rate is derived
by windowed counting, which in this design runs on the Pi. Consequences (both belong to Phase E2,
not 18): the OE signal chain needs a spike detector/sorter upstream of the plugin or there are no
spikes on the wire at all, and sorted unit IDs only exist if sorting is configured, so units of
interest must be declared in `pilot_hardware_config.config`.

**Follow-on phases ADDED to ROADMAP.md 2026-08-03** as Phases 26–28 (the "OpenEphys arc", with its
own preamble section in the roadmap): **26** OpenEphys Device Control (REST RECORD/IDLE, save-path
template, `/api/message` markers as Phase-24 hardware actions, path persisted to MICS, preflight
reachability + lease) → **27** Firing Rate over ZMQ (`sub_connect` + `@decoder`, declared units +
windowed estimator, `(ts_pi_recv, oe_sample)` sync-pair logging, keys via Phase 25's
`detector_keys`) → **28** TTL-vs-Network Sync Validation (both paths in one recording, jitter as a
distribution, **no cutover** — evidence gate only). DeepLabCut stays reserved and inherits
`sub_connect` for free.

**REQUIREMENTS.md amended 2026-08-03** — this is now resolved, not outstanding:
- **EXTLINK-07 amended** — liveness split from signal staleness; lib-supplied hook replaces the
  heartbeat-only rule that assumed every source sends MICS `HB`.
- **EXTLINK-13 amended** — readiness gate keys on "all required *ready*" (lib-defined, defaults to
  `alive`) rather than "all required alive".
- **EXTLINK-14–18 added** — transport roles + `@decoder`, egress queue, run lifecycle hooks, device
  lease, control-only zero-signal modules.
- **EPHYS-01–12 added** — new requirements section covering Phases 26/27/28.

**Still outstanding before planning 18:** nothing in the planning docs. The one open *external*
question belongs to Phase 27, not 18 — whether the OE signal chain will have a spike detector/sorter
upstream of the ZMQ plugin with sorting configured. Without it there are no spikes on the wire and
no unit IDs to declare, which makes 27 unplannable as scoped. Rig configuration, not MICS work.

### Phase 23 status (2026-08-03)

**Plan 11 executed (2026-08-05):** CMP-20/21/22/23 delivered — the frontend half of the
operand-namespace consistency pass (CMP-24/25, the Pi-side and backend halves, are plan 23-12).
Task 1 extracted the decision logic behind every operand picker into three new tested `.mts`
modules (`operandTypes.mts`, `argModes.mts`, `trackerMethods.mts`), pinning today's behaviour
with 21 `node --test` cases before anything changed — a pure, behaviour-preserving refactor that
shrank `ConditionBuilder.tsx` 243→186 and `ArgInput.tsx` 224→177 and `ActionEditor.tsx` 457→425.
Task 2 (CMP-20) narrowed `visibleOperandTypes` so a fresh condition operand offers only
view/literal/param, with `flag`/`hardware` surfacing as a same-shape `(legacy)` escape — never
both together — proven by round-trip assertion rather than inspection; (CMP-21) fixed the actual
bug: `IfActionEditor.tsx:82-87` dropped `hwModuleNames`/`variableNames` when rendering its own
`ConditionBuilder`, so a declared variable or semantic-hardware key was invisible inside an
`if`/`else` condition in the state builder even though the same component already forwarded
`variableNames` into its then/else `ActionEditor`s — a one-line wiring fix (`hwModuleNames`
derived from the `hwModules` prop already in scope, matching `TaskEditor.tsx:202`'s own
derivation, per the plan's explicit discretion grant to avoid four-file prop plumbing). Task 3
(CMP-22) made declared variables selectable as a `type:"flag"` action's write `ref`: all three
`?? 'Counter_Tracker'` tracker-type resolutions replaced by `trackerTypeForRef` so a variable
resolves to the `Tracker` method set (increment/set), and a new `FlagActionFields.tsx` (143
lines) extracted the trial-counter/flag JSX out of `ActionEditor.tsx` to hold it at 327 lines;
`decrement`/`reset` removed from `TRACKER_METHODS.Counter_Tracker` after re-running the plan's
preflight DB query live (0/153 task definitions reference either, matching the 2026-08-05
finding) — neither exists on any `Tracker.py` class. (CMP-23) `ArgInput` gained a `~ View` mode
reading the same namespace the condition pickers use (grouped select over toolkit flags +
variables + semantic hardware, deliberately no detector channels — the Pi's `_resolve_arg` has
no `view_detector` branch — and no `hwModuleNames`, the plan's own recorded scope decision);
`! Flag` relabelled `! Flag (legacy)` and a `switchMode` re-click no-op guard added (mandatory
once the flag pill is the only thing keeping a legacy stored key alive). `npm run test:unit`
(84 pass, up from the 53 baseline), `tsc --noEmit`, and `npm run build` all clean after every
task; `App.tsx`/`Layout.tsx`/`api/`/`orchestrator/`/pi-mirror diffs confirmed empty (frontend
only, per plan). `docker compose up --build web_ui` deliberately NOT run — the rebuilt SPA and
the behavioural click-through both belong to 23-12's consolidated rig checkpoint, after the
Pi-side CMP-24 lands. No deviations from the plan. See `23-11-SUMMARY.md`.

**Plan 09 executed (2026-08-03):** CMP-14/15 delivered — the user-facing half of the compute
preflight work closes out. `HardwareCheckModal.tsx`'s `PreflightIssue` union gained
`variable_never_written`/`lib_version_unresolved`/`compute_lib_import_failed` (mirroring
`toolkit_dispatch.py::PREFLIGHT_ISSUE_KINDS`), each rendered read-only by a new
`ComputeIssueDetail` component — extracted to its own file (not inlined) because the inline
version measured 545 lines against the plan's 500-line hard cap, exactly the fallback the plan
itself named. `NON_CONFIG_ISSUES`, a single `Set<PreflightIssue['issue']>`, replaces the
single-kind `!==` check Phase 25 introduced at both `handleStart`'s PUT loop and the
`pendingEdits` initialiser — now gating all four issue kinds (the three new ones plus
`view_key_unresolved`) that name no `pilot_hardware_config` row, so none of them can trigger a
destructive PUT. New `VariableUsagePanel.tsx` (`useQuery` over plan 07's
`GET /api/task-definitions/{id}/variable-usage`) renders one collapsed row per variable with a
`never_written` badge and expandable writer/reader location lists — mechanically confirmed
read-only (`grep` for `onChange|mutation|button-danger` finds nothing) — rendered inside
`VariablesPanel.tsx` behind a collapsed `<details>`, which gained a `taskDefId?: number` prop
threaded from `TaskEditor.tsx` via a 1-line diff (that file isn't in this plan's
`files_modified`, but the plan explicitly anticipated the change). Used `refetchOnMount:
'always'` rather than the existing `versionStamp` cache-bust key, since that stamp tracks
hardware-lib version pins, not `fda_json` saves — again the plan's own documented fallback.
`tsc --noEmit` and `npm run build` clean after every task; `App.tsx`/`Layout.tsx` diffs both
empty (no new page, no new nav entry). Behavioural sign-off (live `variable_never_written`
payload rendering, Start not PUTting for it) explicitly deferred to plan 23-10's checkpoint,
per this plan's own `<verification>` note. See `23-09-SUMMARY.md`.

**Plan 08 executed (2026-08-03):** CMP-13/14 delivered — the compute action in the FDA editor.
The action-type `<select>` gained exactly one new entry, `compute` (verified: 1 new `<option>`
line across the whole plan's diff), gated off `TriggerAssignmentPanel`'s action lists via
`ArgInput.tsx:76`'s `allowTriggerContext` pattern (`TriggerAssignmentPanel.tsx` diff confirmed
empty). New `ComputeActionFields.tsx` (177 lines) renders the compact row
`[output] = [op ▾] ( [args] )`: one flattened op `<select>` with an `<optgroup>` per compute
module (fetched via `useQueries` on the same `['hardware-module-methods', id]` key
`PilotHardwareConfig.tsx` already uses — no second fetch path), args driven by the selected
op's AST signature via the existing `ArgInput`, and a mandatory output combobox with a
"— new variable… —" sentinel that auto-declares into `fdaJson.variables` on blur (rejecting
empty names and collisions with an existing variable or toolkit flag). `onDeclareVariable`
threaded `TaskEditor` → `StateBodyPanel` → `ActionEditor` → `ComputeActionFields`; since
`variableNames` is derived from `fdaJson.variables` on every render and `ConditionBuilder`
already consumes it (plan 24-08), a freshly typed output name is a selectable transition
operand in the same render pass — no save round-trip (CMP-14, verify-only). `tsc --noEmit`
and `npm run build` clean after every task; bundle `dist/TaskEditor-zd-oW4B_.js`. **One
ordering deviation** (plan's own documented precedent, à la 25-04): `onDeclareVariable` was
added to `ActionEditor`'s Props in Task 1 rather than Task 3, since Task 1 needed it to render
`ComputeActionFields` and keep that task's own `tsc` green — Task 3 then had zero
`ActionEditor.tsx` diff. Behavioural click-through (pick compute → grouped ops → type new
output → appears in ConditionBuilder → save round-trips) is explicitly DEFERRED to plan
23-10's checkpoint, per this plan's own `<verification>` note. See `23-08-SUMMARY.md`.

**Plan 07 executed (2026-08-03):** CMP-15/17/19 delivered — preflight tells the truth about
compute and gains the two issue kinds this phase promised. `preflight_validate` step 6 is now
compute-aware: gated on `compute_module_names(db, module_ids)`, a compute module's
`{"class_name": ...}`-only config no longer trips `incomplete_config` (a hardware module with
the identical shape still does), `class_mismatch` is now reachable for compute modules (the
old branch's early `continue` made it unreachable), and a pilot missing its compute config row
self-heals via `provision_compute_configs` before the loop runs, non-blocking. New step 9
(`variable_never_written`, CMP-15) reports a transition reading a variable nothing writes
anywhere in the FDA, via `variable_scan.variable_never_written_issues`, nested in the same
`fda_json` guard as step 8 and in its own try/except. New step-6 `lib_version_unresolved`
(CMP-17 rung 5) resolves each module's hardware lib version via `resolve_lib_version_id` and
names the module + lib filename when no beta/stable version is deployable — replacing
`get_dispatch_spec`'s silent skip, checked independently of whether the config row itself is
present. A new `PREFLIGHT_ISSUE_KINDS` frozenset documents all eight issue kinds (mirrored by
`HardwareCheckModal.tsx::PreflightIssue` in plan 23-09); `compute_lib_import_failed_issue` is a
registered-but-unused constructor reserving CMP-19c's shape. New
`GET /api/task-definitions/{id}/variable-usage` (`api/routers/task_def_inspect.py`, 63 lines,
following `toolkit_dispatch.py`'s own `Depends(get_sa_session)` shape rather than
`pilot_hardware_config.py`'s bare with-block, for testability) is a thin composition over
`variable_scan`'s writer/reader scanners for the FDA editor's read-only inspector; wired into
`api/main.py` via a 2-line diff. Full backend suite green throughout: **332 passed**. Live-
verified: `GET /api/task-definitions/186/variable-usage` returns populated writers/readers,
187 returns empty, unknown id 404s; `POST /api/sessions/113/preflight-validate/1` (real
backend-authored session/pilot) still returns `{"ok": true, "issues": []}` — no regression.
`wc -l`: `toolkit_dispatch.py` 459 (under the 470 helper-extraction threshold and the 500 hard
limit), `task_def_inspect.py` 63. `api/main.py` diff exactly 2 lines. No deviations. See
`23-07-SUMMARY.md`.

**Plan 01 executed:** Wave 0 — the three ❌ contract-test targets from `23-VALIDATION.md` now
exist on disk, all failing/skipping/xfailing today for the right reason (missing feature, not a
typo), per the phase's re-scoped compute-as-hardware-lib plan (see the four `docs(23):` commits
immediately preceding this one — re-scope, re-plan as 10 plans/6 waves, defer-and-gate the
trigger-assignment compute option). `api/tests/test_hardware_lib_kind.py` (9 tests: 2 real-DB
migration-idempotency + 2 real-DB `seed_compute_ops_lib`/allowlist tests, 5 xfail route tests)
pins CMP-12/19 — the `hardware_libs.kind`/`hardware_lib_versions.declared_imports` columns,
`run_hardware_lib_kind_migration`'s idempotency, and `POST /api/hardware-libs`'s
`kind='compute'`/`declared_imports=[...]` validation, none of which exist until plan 23-02.
`api/tests/test_toolkit_dispatch.py` (11 tests, module-level `pytest.importorskip` since
`api/lib_version_resolution.py` doesn't exist until plan 23-05) pins CMP-17's
`resolve_lib_version_id` pin → toolkit_default → stable → active → none chain (every reason
string covered) plus the `get_dispatch_spec` stable-over-active regression and the
`resolved_version_id`/`resolved_state`/`resolution_reason` fields `list_toolkit_hardware_libs`
must gain. `/home/ido/pi-mirror/tests/test_compute_ops.py` (8 tests, USER-RUN, not deployed)
pins CMP-03/04/05 — a `Hardware` subclass needs `type=` supplied explicitly (Pitfall 7) and must
override `release()` or `Task.end()` raises on every run (Pitfall 3), plus the compute action's
build-time-required `output`, its `group`-present/absent dual resolution form, and last-write-
wins re-invocation. Full backend suite green throughout: **231 passed, 5 skipped, 5 xfailed**
(verified before AND after `docker compose up --build api`, since that service has no bind mount
— new test files are invisible to a running, un-rebuilt container). No pi-mirror files other
than the one new test file touched; no git commands run there. See `23-01-SUMMARY.md`.

**Plan 06 executed (2026-08-03):** CMP-12/18 delivered — the kind-aware Hardware Libraries GUI.
`types/index.ts` gained `LibKind`, `HardwareLib.kind`, `HardwareLibVersion.declared_imports`,
`HardwareModule.lib_kind` (the last comment-pinned to plan 23-08's compute op picker);
`uploadHardwareLib` sends `kind`/`declared_imports` FormData fields, defaulting to
`'hardware'`/`[]`. `HardwareLibs.tsx` gained one `All (n) / Hardware (n) / Compute (n)` filter
chip row (client-side filter over the already-fetched list, no new endpoint) plus a `meta-pill`
"compute" badge on compute rows only, and the upload form gained a `kind` select plus a
comma-separated `declared_imports` input shown only for `compute` with stdlib-only helper text.
`HardwareLibDetail.tsx` shows the `kind` pill and the selected version's `declared_imports`,
read-only. Confirmed by reading `api/client.ts` that `apiFetch`'s existing `formatDetail` already
renders a plain-string 422 `detail` verbatim — no change needed there. `tsc --noEmit` and
`npm run build` both clean (`dist/HardwareLibs-DPUByP4B.js`, `dist/HardwareLibDetail-CKGnbh6y.js`);
`git diff --stat` on `App.tsx`/`Layout.tsx` both empty — no new page, no new route, no
`NAV_LINKS` change. `HardwareLibs.tsx` 172 lines (budget 200). No deviations. Manual click-through
deferred to plan 23-10's checkpoint, per this plan's own `<verification>` note. See
`23-06-SUMMARY.md`.

**Plan 05 executed (2026-08-03):** CMP-17/19 delivered — the single lib-version resolution
chain. New `api/lib_version_resolution.py::resolve_lib_version_id`/`resolve_lib_versions`
implement pin → toolkit_default → stable → active (only if that version's own `state` is
beta/stable) → none, replacing THREE independently-wrong chains: `get_dispatch_spec` (what
gets exec'd), `toolkit_hw_capabilities` (AST introspection), and the orchestrator's
`_send_hardware_libs_if_needed` (what gets shipped to the Pi) — none of which previously
consulted `stable_version_id` at all. **Deviation (per plan's explicit instruction):** a fourth
"active" rung was added beyond CONTEXT's literal 3-rung chain, gated on the active version's own
state being beta/stable — implemented literally (stop at stable-or-nothing), every existing
backend-authored toolkit on the rig (MPR121, TOUCH_INT, all their task defs) would stop
dispatching, since none has a promoted stable version yet. Verified live:
`GET /toolkits/100/dispatch-spec?pilot_id=1` still returns `Modules` with `MPR121`/`TOUCH_INT`
populated, `unresolved_libs: []`. `GET /toolkits/{id}/hardware-libs?task_def_id=N` now carries
`resolved_version_id`/`resolved_state`/`resolved_source_code`/`resolution_reason` per lib
(verified live against all 112 toolkits' libs). Orchestrator's `_send_hardware_libs_if_needed`
rewritten to read those resolved fields instead of re-deriving the chain, and now sends ONE
`LOAD_HARDWARE_LIBS` per lib with `test_import: True` + the Pi's expected top-level
`version_id` — activating `HARDWARE_LIB_TEST_RESULT`, dead since Phase 09, with **zero
Pi-side change** (verified: pi-mirror `pilot.py` byte-identical via diff against the live Pi).
Two Rule-3 fixes to pre-existing tests whose fixtures/query-shape assumptions predated this
plan's changes (`test_view_key_preflight.py`'s two `toolkit_hw_capabilities` tests;
`test_toolkit_dispatch.py`'s `kind`/`declared_imports` fixture gap from plan 23-02). Full backend
suite green throughout: **314 passed**. `wc -l`: `hw_introspect.py` 208, `lib_version_resolution.py`
89, `toolkit_dispatch.py` 376 (all under budget). No pi-mirror commits. See `23-05-SUMMARY.md`.

**Plan 02 executed (2026-08-03):** CMP-04/12/19 delivered — the compute-lib storage substrate.
`hardware_libs.kind` ('hardware'|'compute') + `hardware_lib_versions.declared_imports` (JSONB),
migrated via `run_hardware_lib_kind_migration` (idempotent, verified twice-in-a-row). New
`_validate_compute_lib` (`hardware_libs.py`) gates `kind='compute'` uploads/updates: a class with
an in-file base lacking `release()` is rejected 422 naming `release()`/`Task.end()` (Pitfall 3);
a `declared_imports` entry outside `seed_compute.COMPUTE_STDLIB_ALLOWLIST` is rejected 422 naming
the offender + allowlist. `api/seed_libs/compute_ops.py` (the 13 CONTEXT-locked stdlib ops as a
`Hardware` subclass) + `api/seed_compute.py::seed_compute_ops_lib` seed that source idempotently
at API startup as a stable `hardware_libs` row (both `active_version_id`/`stable_version_id` set)
plus a `COMPUTE` `hardware_modules` row. New `api/compute_provisioning.py::provision_compute_configs`
auto-provisions the trivial `{"class_name": ...}` `pilot_hardware_config` row a compute module
needs before `init_hardware()` will instantiate it (Research's "high-risk finding" — a compute
module needs the full hardware-module ceremony, not just `toolkit_hardware_libs`), wired into
`create_hardware_module`; verified live against the real dev DB — one config row created per
pilot (2/2), re-provisioning created nothing new, an existing row is never touched. Full backend
suite green throughout: 296 → 302 passed, 1 skipped, 0 failed. File budgets all held (`db.py` 290,
`seed_compute.py` 105, `compute_provisioning.py` 72 lines; `hardware_libs.py` +68 lines against an
80-line budget; `main.py`'s cumulative diff 4 insertions/1 deletion). **Concurrency note:** this
plan executed alongside sibling agents on plans 23-03/23-04 in the same non-worktree-isolated
working directory (see their own `23-0x-SUMMARY.md` concurrency notes for the mirror image of
this account) — verified before every `git add` that only this plan's own hunks were staged,
including one `git apply --cached` reconstruction of a clean patch to strip a foreign hunk that
had landed in the same file (`hardware_libs.py::_flag_broken_task_defs`) I was editing for Task 1.
One of my own working-tree edits (`_lib_dict`'s `declared_imports` field) was itself swept into a
sibling agent's `docs(23-04)` commit before I could commit Task 2 separately — confirmed
byte-identical to what this plan needed via `git show`, left as-is. See `23-02-SUMMARY.md`.

**Plan 04 executed (2026-08-03):** CMP-03/04/05/06 delivered on the Pi runtime, in
`/home/ido/pi-mirror`. `fda_vocabulary.py` gained `"compute"` in `VALID_ACTION_TYPES` (single-
sourced comment pointing at `api/fda_validation.py`'s backend twin). `mics_task.py`'s
`_build_action_callable` gained the `compute` branch — byte-for-byte the `hardware`/`timer`
branch's dual ref-resolution (`group` present → `self.hardware[group][ref]`, absent →
`self._semantic_hw[ref]`), with `output` made mandatory at BUILD time (`ValueError` naming
`ref.method`). `tools/validate_fda.py` gained the matching CLI-side `compute` branch, message-
worded identically to the runtime's. `tests/test_compute_ops.py` (plan 23-01's pre-written Wave 0
tests, unchanged) plus 4 new Task 3 regression tests for CMP-01/02/05/06 (verify-only — pinning
that Phase 24's variables registry holds for compute-written variables). `tests/test_fda_vocabulary.py`
extended with a `compute`-membership assertion: **23 passed** (agent-verified). **One bug found
and fixed in-task (Rule 3 — blocking):** `_build_state_method`'s separate entry_actions
pre-validation loop had no branch for `compute` and would have raised "unknown action type"
before ever reaching the new `_build_action_callable` branch — widened its existing `hardware`
check to `("hardware", "compute")`. **One bug found and NOT fixed, per the plan's explicit
instruction:** `load_fda_from_json`'s variables-collision guard (`if var_name in self.flags:
raise`) does not exempt a variable name the mechanism itself declared on a prior load, so
`hot_update_fda` re-declaring the SAME variable name (the normal hot-reload case) appears, by
code inspection, to raise instead of recreating the tracker — CMP-06's "hot-reload re-creates
variables" promise. Not confirmed by execution (autopilot unimportable here); flagged as a
predicted Phase-24 defect for plan 23-10 to confirm via `test_hot_update_fda_recreates_variables_
before_rebuilding_transitions`. No pi-mirror git commits (pi-mirror is user-owned git, same as
plan 25-02). See `23-04-SUMMARY.md` and its "Next Phase Readiness" for the exact rsync file list.

**Plan 03 executed (2026-08-03):** CMP-10/11/15 delivered on the backend save-time gate.
`fda_utils.py::scan_fda_for_refs` now emits `compute` entries (`ref`/`method`/`output`),
feeding both the soft drift-badge path and the hw-lib-update impact scan —
`hardware_libs.py::_flag_broken_task_defs` needed its OWN action_type filter widened too (not
listed in the plan's files_modified, but required for its own must_haves truth to hold; see
`23-03-SUMMARY.md` Deviations). `fda_validation.py` gained a `compute` action branch (ref/method
rule + mandatory-output rule) and `validate_compute_variables` (variable-name collision against
semantic hardware/module names/detector keys, plus a reference-half check over every condition
operand); both wired into the existing `collect_hard_errors` → `reject_if_hard_errors` 422 path.
New `api/variable_scan.py` (172 lines) delivers `scan_variable_writers`/`scan_variable_readers`/
`variable_never_written_issues` — an explicit v1 "existence, not reachability" analysis, not yet
wired into preflight (plan 23-07's job). Full backend suite green: **302 passed, 1 skipped**
(rebuilt api container first — no bind mount). Live 422 proof against the running stack matches
the plan's `<verification>` section exactly. **Concurrency note:** a separate agent process was
executing plans 23-02/23-04 in this same non-worktree-isolated working directory during this
plan's execution (see `23-03-SUMMARY.md` for full detail) — at one point its own `git add`/commit
swept this plan's already-staged Task 1 files into its `docs(23-04)` commit before I could commit
them separately; content is correct and verified (full suite green, `routers/toolkits.py` 1-line
diff confirmed via `git show --stat`), only that one commit's attribution is shared with plan
23-04's work. No file belonging to plans 23-02/23-04 was touched, edited, or reverted by this
plan's execution. See `23-03-SUMMARY.md`.

### Phase 25 status (2026-07-29)

**Plan 01 executed:** DVK-01/02/07/09/11 delivered on the backend. `api/detector_keys.py`
single-sources `derive_channels`/`derive_view_keys` (the `f"{device_name}{i}"` format, now
declarable via `first_channel` for DVK-09's channel-1-4 wiring) and `module_detector_channels`
(the advisory cross-pilot union with surfaced `conflict` + `by_pilot` provenance — verified
live: `MPR121` → `channels [0,1,2,3]`, `keys LICKER0…LICKER3`, `conflict: false`). New
`scan_fda_condition_operands` in `api/fda_utils.py` is the ONE condition-operand walker shared
by this plan's save-time gate and plan 03's preflight resolver. New
`validate_condition_operands` in `api/fda_validation.py` is the DVK-11 save-time 422: a
`view_detector` operand must name a real detector and carry a non-negative int `channel` — range
checking stays with preflight (plan 03). DVK-07 pinned by 4 regression tests verified passing
against pre-plan code first. Full backend suite: 163 passed. No route changes yet (plan 03).
See `25-01-SUMMARY.md`.

**Plan 02 executed (2026-07-29):** DVK-09/10/11 delivered on the Pi runtime, in
`/home/ido/pi-mirror`. `fda_vocabulary.py` gained `detector_channel_range` /
`detector_view_keys` / `detector_channel_key` (the Pi's half of plan 01's shared golden-table
derivation) and `parse_view_detector_operand` (DVK-11's shape parser). `check_for_detectors`
now honours `first_channel` read from `prefs.HARDWARE[group][module_name]` — the exact fix for
the channel-4 data loss in runs 480/481 (`LICKER1..LICKER4` correctly seeded from
`curr_vals[1..4]`, never shifted). `execute_trigger`'s `except KeyError` is narrowed to the
`self.triggers[pin]` lookup alone; a raising callback now reports via a new
`_report_trigger_error` helper (error log naming the exception + `TRIGGER_ACTION_ERROR` event)
whose entire body is exception-contained so a dead `event_dispatcher` can't kill the worker
thread. `_build_condition_operand` gained a `view_detector` branch resolving
`{"ref": ..., "channel": ...}` to a pilot's real view key ONCE at build time — the same stored
JSON reads `LICKER2` on one pilot and `TONGUE2` on another. Mirror-Pi identity proved via diff
before any edit (all four target files byte-identical); diff re-confirmed after editing that
only the intended methods/import lines changed and `i2c.py` stayed untouched. Dev-host
agent-runnable suite: 64 passed (`test_detector_view_keys.py` + `test_fda_vocabulary.py`).
Three new/extended test files (`test_check_for_detectors.py` DVK-09 cases,
`test_execute_trigger_guard.py`, `test_view_detector_operand.py`) are USER-RUN on the Pi —
plan 06 owns running them plus the deploy and rig proof. **No pi-mirror git commits made**
(pi-mirror is its own user-owned git repo; pi_rules forbid any git command there). See
`25-02-SUMMARY.md`.

**Plan 03 executed (2026-07-29):** DVK-02/06/11 wired into the two routes the rest of the
system reads from. `scan_fda_view_keys` + `resolve_view_key_issues` (new
`api/detector_keys_scan.py`, re-exported from `detector_keys.py` — the combined file would
have exceeded its 300-line budget) compose plan 01's `scan_fda_condition_operands` with a new
`key_template` action walker, then classify every scanned entry against ONE pilot's declared
`pilot_hardware_config` wiring. `preflight_validate` gained step 8 — nested inside step 7's
`fda_json` guard (not after it, to avoid a swallowed `NameError` on a fda_json-less task def)
and wrapped in its own `try/except` + `logger.warning` — resolving detector channels (DVK-11
range check) and literal/`key_template` view keys (DVK-06) against the target pilot, emitting
`view_key_unresolved` issues with an optional `detector`/`available_channels` field pair (R1).
`detector_channels` now rides every toolkit read route including
`GET /api/toolkits/by-name/{name}` (the route `TaskEditor.tsx` actually calls) — required
fixing `toolkit_hw_capabilities` to return `module_names` on its early-return path too, since
98 of 112 `task_toolkits` rows are module-less and previously would have 500'd
`GET /api/toolkits` once a caller relied on that key. `is_detector` added to
`GET /api/hardware-modules/{id}/methods`. Full backend suite: 219 passed. Live-verified from
`mics_web_ui`: both toolkit routes carry the MPR121 `detector_channels` group,
`GET /api/toolkits` 200s across all 112 rows, module 7 `is_detector: true` / module 8
`is_detector: false`. `api/main.py` and `api/fda_validation.py` diffs both empty. See
`25-03-SUMMARY.md`.

**Plan 04 executed (2026-07-29):** DVK-03/04/05/07/11 delivered on the FDA editor. New
`web_ui/react-src/src/components/detectorOptions.mts` (pure, tested via `node --test`, zero
new npm dependencies) is the single option-assembly + operand-encoding module behind every
view-operand picker: `buildViewOptions` groups options into Hardware / one-group-per-detector
labelled by `device_name` / Flags & variables; `viewOperandToOptionValue` /
`optionValueToViewOperand` round-trip a `view_detector` operand through an opaque
`"@detector/MPR121#2"` select token, resolved by scanning the backend's own
`detector_channels`, never by parsing the token. `ConditionBuilder.tsx`'s `OperandEditor` now
renders that grouped `<optgroup>` picker and emits `{"view_detector": {"ref","channel"}}` for a
picked channel — never a resolved per-pilot key (DVK-11). The keep-current-value escape
survives verbatim, now flagged `(unknown)` (DVK-05, scoped to keys the backend cannot model,
per 25-CONTEXT S6 — there is no legacy detector key to migrate). `detectorChannels` threaded
end to end (`TaskEditor` → `StateBodyPanel`/`TriggerAssignmentPanel`/`ConditionGroupsEditor` →
`ActionEditor` → `IfActionEditor` → `ConditionRow`/`ViewActionFields`). `ViewActionFields`'
`key_template` field now offers `{device_name}` + variable + derived-key completions from the
same builder while staying free text (DVK-04/DVK-05); `DetectorWriteWidget.tsx` (trigger `view`
action, 25-CONTEXT D5) untouched. 24 unit tests green, `tsc --noEmit` clean, `vite build`
succeeds — bundle `dist/TaskEditor-B6-dKcPk.js`. Two Rule-3 ordering deviations (types added a
task early; `ViewActionFields` wiring deferred a task late) documented in `25-04-SUMMARY.md`,
both to keep each task's own `tsc` green — no scope change from the plan. Behavioural
verification of the rendered pickers is manual, deferred to plan 06's checkpoint. See
`25-04-SUMMARY.md`.

**Plan 05 executed (2026-07-29):** DVK-06/09/11 delivered on the FDA editor's two preflight-facing
surfaces. `HardwareCheckModal.tsx`'s `PreflightIssue` union gained `view_key_unresolved` plus the
optional `location`/`key`/`available_keys`/`detector`/`available_channels` fields from plan 03's
two issue shapes; a new `ViewKeyIssueDetail` read-only component renders both (leading with
`MPR121 — channel 5` + an `available_channels` pill row for the DVK-11 shape, the offending `key`
for the literal shape, `detail` alone when only that field is present) — the issue that previously
rendered as `null` and left the researcher unable to tell why start was gated. `handleStart` and
the `pendingEdits` initialiser both skip `view_key_unresolved` — it names no config row, so it can
no longer trigger a destructive PUT (overwriting a good config with `{}`, or hitting an empty path
segment). The `issues.map` React key, previously `module_name` alone, is now
`${issue.issue}:${issue.module_name}:${issue.location ?? i}` — fixes a real duplicate-key
collision (two bad channels on one MPR121 previously shared a key). No start gate added; preflight
stays advisory per Phase 13. Separately, `PilotHardwareConfig.tsx` now offers a `first_channel`
number input (empty = key absent, via new `setJsonKey` helper) plus a live derived-key preview
(new `DetectorChannelFields.tsx`, comment-pinned to `api/detector_keys.py::derive_view_keys` as the
real authority) on a detector module's **edit** row — resolved by module **name** against
`listHardwareModules` since `PilotHardwareConfigRow` carries no `module_id` (Phase 17).
`handleModulePick`'s existing template fetch was rerouted through `qc.fetchQuery` on the same
`['hardware-module-methods', id]` key the new `is_detector` `useQuery` hooks use, so the add and
edit flows share one fetch, not two. `HardwareModuleMethods` gained `is_detector: boolean`
(already shipped on the backend response by plan 03). `tsc --noEmit` clean; `npm run build`
succeeds (bundles `dist/HardwareCheckModal-DKJUfoGY.js`, `dist/PilotHardwareConfig-B09He_Dl.js` —
`npx vite build` itself failed in this environment with `npm error Missing script: "vite"`,
apparently the rtk command-rewriting hook misinterpreting `npx <bin>`; `npm run build`, the
project's own script, produced the identical build unaffected). No deviations from plan. No
hardcoded `LICKER` in any rendered string — verified by grep. Behavioural verification (both issue
shapes against the rig pilot, the edit-flow `first_channel` round-trip) is plan 06's, per this
plan's own note not to claim DVK-06/09/11 proven here. See `25-05-SUMMARY.md`.

### Phase 24 status (2026-07-27)

Plans 01–05 executed, deployed, and **proven on the real rig** (run 475: 47 `TOUCH_INT`
firings with alternating `level` 0/1, action list assembled in the UI, no `learning_cage`,
no `handler` enum). TRIGA-01/02/06 demonstrated on hardware.

**Plan 06 executed (2026-07-27):** TRIGA-12/18/19 delivered — capability-based
`check_for_detectors` (fixes the isinstance-identity bug that made sourceless lick detection
silently produce zero trackers), `source_ref` + runtime-resolved `{device_name}` on the `view`
action (task definitions stay pilot-agnostic), and the value-source lock (level always from
`detect_change()`'s own capture, never the trigger's IRQ-edge level). Deployed to the Pi,
md5-verified. **Not yet USER-verified** — awaiting pilot restart + full test-suite run (below).
See `24-06-SUMMARY.md`.

**Plan 08 executed (2026-07-27):** TRIGA-14/15/16/17 delivered — `api/hw_introspect.py` derives
`trigger_sources`/`detector_refs` from the lib AST (verified live on toolkit 100/module 7); a
hardware/timer action with no `method` is now a hard 422 in triggers AND state `entry_actions`;
the `view` action accepts the runtime `{device_name}` token when paired with a resolvable
`source_ref`; `trigger_name` is a grouped dropdown; declared `variables` join the condition
operand pickers; new `DetectorWriteWidget.tsx` is the constrained one-pick detector write UI
macro (emits ordinary FDA JSON, no Pi-side change). `api`/`web_ui` rebuilt and verified live.
Blast-radius re-confirmed unchanged: task defs 181/185(Gili's)/187 blocked from re-save by the
method rule, none edited. See `24-08-SUMMARY.md`.

**Read these two files first when resuming:**
- `.planning/phases/24-trigger-assignment-action-lists/24-HARDWARE-VALIDATION.md` — what is
  proven, the 7 post-execution defects and their commits, infrastructure incidents, and the
  exact deployed/registry/DB state.
- `.planning/phases/24-trigger-assignment-action-lists/24-REPLAN-BRIEF.md` — what changes in
  plans 06/07/08 for the sourceless-only decision, requirement by requirement.

**Re-plan discussion COMPLETE (2026-07-27).** Decisions R1–R11 are in `24-CONTEXT.md`
§ `<replan_2026_07_27>`; REQUIREMENTS.md and ROADMAP.md are updated to match. Headlines:
- **Constrained one-pick detector write** in the editor, emitting ordinary FDA JSON (UI macro).
  The researcher cannot read electrode 2 and write `LICKER0`. No detector code on the Pi.
- **`{device_name}` token** in `key_template` + `source_ref` on the `view` action, resolved at
  runtime — task definitions stay pilot-agnostic.
- **Level comes from `detect_change`'s return, never `{"trigger":"level"}`** — the trigger's level
  is IRQ assert/deassert, not electrode state. Run 475's alternating 0/1 was that handshake.
- **TRIGA-11 dropped** (vacuous on a sourceless toolkit) → **TRIGA-11a** rig proof.
- **TRIGA-13 moved to Phase 25**, which now runs **immediately after 24, before 23**.
- **New: TRIGA-16** (validate hardware action `method` — `method:""` currently 200s and silently
  no-ops), **TRIGA-17/18/19**.

**Plan 07 executed (2026-07-27) — PHASE 24 IS FUNCTIONALLY COMPLETE, 8/8 plans.**
TRIGA-11a proven on hardware across runs 478/480/481: **144 trigger firings, 63 licker writes,
zero correctness errors** — every write hit the tracker matching the electrode `detect_change`
reported, carried that call's own level (never the IRQ edge), and carried the triggering
`TOUCH_INT` tick as `pi_timestamp`. The `pin_number != null` guard blocked all 72 no-change
edges. Save-time negative suite: **8/8** (canonical 201, seven invalid payloads 422 with
specific messages, including TRIGA-16's method gate). See `24-07-SUMMARY.md` and
`24-HARDWARE-VALIDATION.md` §2b.

**Outstanding:**
1. **Pi tests STILL never run anywhere** (`autopilot` unimportable on dev host) — the one real
   gap in phase 24. ~60 tests now, including `test_check_for_detectors.py`,
   `test_log_action_values.py` and additions to three existing files. USER-RUN:
   `cd ~/Apps/mice_interactive_home_cage && python3 -m pytest tests/ -q`
2. **Phase 25 is next** (agreed order: 24 → 25 → 23). It now carries **DVK-09**, added from rig
   evidence: the rig's four spouts sit on MPR121 channels **1–4**, so `range(0, num_detectors)`
   builds a dead `LICKER0` and **silently discards channel 4** (9 real events lost in runs
   480/481). Names cannot be offset — the key is `{device_name}{pin_number}` where `pin_number`
   is the raw hardware index — so the channel range itself must become declarable.
   **Decided 2026-07-29 (user):** `first_channel` (default `0`) + existing `num_detectors`, i.e.
   `range(first_channel, first_channel + num_detectors)`. **Not** an explicit channel list — the
   extra editor UI is not justified by contiguous 1–4 wiring. Non-contiguous channels are
   consciously out of scope.
3. **DVK-10 (new, 2026-07-29)** — traced *why* DVK-09 was silent: `mics_task.py:717-721` **does**
   raise `KeyError` for the unknown `LICKER4`, `_run_trigger_actions` (`mics_task.py:1323-1328`)
   has no `except`, and `execute_trigger`'s `except KeyError` (`task.py:285-298`) — intended for a
   missing `self.triggers[pin]` lookup — swallows it and logs `"No valid trigger for {pin}"` at
   DEBUG. Wrong handler, wrong message, no mention of the key. Narrow that guard to the lookup
   alone. Hides every action-list key error DVK-06 preflight does not catch first.
4. `process_queue` (`task.py:262-266`) has no exception handler: any trigger-callback exception
   permanently disables all trigger processing with no operator-visible signal. Found via defect
   8. User deferred it; not scoped. Distinct from DVK-10 — the LICKER4 `KeyError` never reached
   `process_queue`, which is why the worker survived and the other 63 writes succeeded.
5. Optional: clear legacy `trigger_assignments` rows in task defs 181 and 185 (185 is Gili's).
   Note task defs 181/185/187 also hold state-body hardware actions with an empty `method` and
   cannot be re-saved until fixed (TRIGA-16 blast radius).
6. `detect_change` reports only `changes[0]`, so simultaneous multi-electrode transitions are
   lost unrecoverably (`i2c.py`, off-limits, pre-existing). Bounds what concurrent multi-spout
   licking can measure.

---

## Decisions Made

| Decision | Made | Rationale |
|---|---|---|
| Hardware_Event logging is unconditional | 2026-03-15 | execute_trigger() always dispatches Hardware_Event; trigger_assignments only adds semantic layer |
| FDA v2 JSON with entry_actions | 2026-03-15 | Declarative state bodies; no exec() or pickle needed |
| SEMANTIC_HARDWARE defined in code by developer | 2026-03-15 | Friendly names are toolkit public API; developer writes them in Python, HANDSHAKE ships them to DB, GUI consumes them as read-only dropdowns; researchers cannot rename hardware from UI |
| Three-layer abstraction: prefs.json → HARDWARE dict → SEMANTIC_HARDWARE → FDA JSON | 2026-03-15 | prefs.json changes (pins) never reach FDA JSON; HARDWARE key renames require one SEMANTIC_HARDWARE update; semantic name renames require DB migration — avoid |
| Hot-reload scope: between task runs, not mid-execution | 2026-03-15 | Orchestrator includes latest fda_json from DB in every START payload; Pi calls load_fda_from_json() at task start; pilot process never restarts; mid-execution UPDATE_FDA deferred to v2 |
| Three state modes: passthrough / GUI-built / hybrid | 2026-03-15 | Passthrough = existing Python method used as-is (no entry_actions); GUI-built = full entry_actions in JSON; hybrid = GUI-built state calling CALLABLE_METHODS as building blocks |
| CALLABLE_METHODS is developer-defined, not UI-created | 2026-03-15 | Developer marks Python methods as callable from JSON by listing in CALLABLE_METHODS; GUI consumes from task_toolkits.callable_methods; researchers cannot create callable methods from UI |
| Monaco + asyncssh for Pi editor | 2026-03-15 | Jupyter/code-server too heavy for Pi |
| Phase 5 independent of Phases 1-4 | 2026-03-15 | Pi editor viewer has no dependency on toolkit/FDA work |

---
- [Phase 01-pi-foundation]: nohup launch uses < /dev/null to prevent SSH stdin hang (required for pilot restart)
- [Phase 01-pi-foundation]: Deploy scripts in ~/pi-mirror/tools/ (not mics-backend repo) — operational tools outside codebase
- [Phase 01-pi-foundation]: serialize_flags and _serialize_semantic_hardware added as private Pilot helpers for testability; all six enriched fields default to empty collections for backward compat
- [Phase 01-pi-foundation]: validate() takes (definition, cls) order — definition first, class second — consistent with test signatures
- [Phase 01-pi-foundation]: if-action recursion shares _validate_actions_list() for state loop and then/else branches
- [Phase 02-db-api]: Toolkit schema in task_toolkits separate from task_definitions — multiple FDAs per toolkit possible
- [Phase 02-db-api]: fda_json stored as JSONB in task_definitions, toolkit_name as FK ref by name
- [Phase 02-db-api]: hw_hash pre-computed by orchestrator as SHA256(json.dumps(sem_hw, sort_keys=True)); API trusts caller hash
- [Phase 02-db-api]: Enriched HANDSHAKE detected by key presence (SEMANTIC_HARDWARE or FLAGS), not schema version field
- [Phase 02-db-api]: All new API endpoints go in api/routers/ package — api/main.py change is only include_router call
- [Phase 02-db-api]: Migrated columns (toolkit_name, display_name, fda_json) not in ORM class — use raw sa_text SQL for all queries touching them
- [Phase 02-db-api]: Used stdlib urllib.request instead of requests in api push endpoint — requests not in api/requirements.txt
- [Phase 02-db-api]: state_machine injection in _build_step_task is non-fatal — failure logs and continues without state_machine key
- [Phase 04-protocol-integration]: task_definition_id uses bare Optional[int] (no SQLModel FK) in ProtocolStepTemplate — task_definitions is SQLAlchemy-owned; SQLModel FK resolution fails at startup. DB constraint enforced by run_protocol_migrations().
- [Phase 04-protocol-integration]: ProtocolStep type extended with task_definition_id; palette filtered to fda_json != null definitions; getLeafTasks kept as fallback in OverridesModal for legacy protocol backward compat
- [Phase 04-protocol-integration]: set-canonical conservatively flags all task_definitions for toolkit name as needs_migration=True — no toolkit_id FK on task_definitions so cannot distinguish per-variant
- [Phase 11]: Legacy HANDSHAKE filename reconstructed from task class name (AppetitiveTaskReal.py) with is_legacy_filename=True; detected by uppercase in stem
- [Phase 11]: HwLibVersionModal scans all hw/timer FDA refs (not filtered per-lib) since module→lib resolution would need extra API calls
- [Phase 11-02]: class_name stored in available_locked_states; new HANDSHAKE format carries it per-entry, legacy format derives it from task_type
- [Phase 11-02]: Dispatch endpoint in api/routers/toolkit_dispatch.py (toolkits.py already >500 lines — router-per-domain split)
- [Phase 11-02]: task_type override placed after _build_*_task in start_run and _advance_run_step to respect re-assertion at lines 686/745
- [Phase 11-03]: task_type left to dispatch-class override — _inject_backend_toolkit_spec does not set task_type
- [Phase 11-03]: pilot_hardware_config table name is singular (plan had wrong plural name)
- [Phase 11-04]: _resolve_flags() reads 'tracker_type' key (DB format) with 'type' fallback; pops key and sets 'type' = Tracker class for init_flags() compatibility
- [Phase 11-05]: EditModal extracted to separate file to keep Toolkits.tsx under 500-line limit
- [Phase 12-hardware-fda-builder]: Direct-ref format uses 'group' key as discriminator for hardware actions in Pi — backward compat, no version bump
- [Phase 12-hardware-fda-builder]: GUI-built states unconditionally call wait_for_condition() — entry_actions present is sufficient signal, blocking field ignored
- [Phase 12-hardware-fda-builder]: Trial_Tracker.increment() dispatches INC_TRIAL_COUNTER (was DATA) — orchestrator now counts trials from flag-based actions
- [Phase 12-hardware-fda-builder]: trial_counter injection is server-side in _normalize_flags() — every toolkit GET response always has it, UI never needs to handle 0-trial-flags case
- [Phase 12-hardware-fda-builder]: auto-save depends on fdaJson only (not editName) — name changes excluded from debounce since user may still be typing
- [Phase 12]: Context menu renders as fixed-positioned div outside ReactFlow canvas — avoids transform coordinate issues
- [Phase 11-06]: CreationModal extracted to separate file to keep Toolkits.tsx under 300-line limit
- [Phase 12-hardware-fda-builder]: scan_fda_for_refs in api/fda_utils.py shared between hardware_libs and toolkits routers
- [Phase 12-hardware-fda-builder]: Pinned task definitions insulated from active-version lib changes (skip in impact scan); classic toolkits skip hardware ref validation (no hardware_module_ids)
- [Phase 12-hardware-fda-builder]: Lazy import _validate_task_definition in _revalidate_task_def to avoid circular import between router modules
- [Phase 12-hardware-fda-builder]: Auto-pin uses stable_version_id falling back to active_version_id at task def creation
- [Phase 14]: CSS :hover tooltip chosen over React state tooltip to survive ReactFlow re-renders without JS overhead
- [Phase 14-bug-backlog]: BUG-07: explicit proxy routes for toolkit/{id}/hardware-libs needed — catch-all strips /api/ prefix when forwarding
- [Phase 14-bug-backlog]: BUG-06: auto-link all hw-libs at toolkit creation; per-lib version pinning is task-definition concern, not toolkit concern
- [Phase 14-bug-backlog]: BUG-05: skip step 2 (locked-states) when no file selected by jumping step 1→3→1 in handleNext/handleBack
- [Phase 15-compound-transition-conditions]: Pi DNF uses single _dnf callable with default arg capture to avoid late-binding closures in loop
- [Phase 15-compound-transition-conditions]: normaliseTransition drops legacy conditions field from in-memory state; Pi still reads it from stored JSON via legacy fallback
- [Phase 15-compound-transition-conditions]: Empty condition_groups [] = unconditional (not [{conditions:[]}]) so ConditionGroupsEditor shows hint instead of empty group card
- [Phase 15-compound-transition-conditions]: ConditionRow delete button placed inline alongside Right operand to avoid layout shifts
- [Phase 15-compound-transition-conditions]: ConditionGroupsEditor is fully controlled (no internal state); mutations go through onChange prop
- [Phase 16-recursive-condition-tree]: Leaf node detection in _build_tree_lambda uses op not in (AND,OR) — handles both unified and legacy leaf formats transparently
- [Phase 16-recursive-condition-tree]: Three-way fallback chain in transition registration: condition_tree (Phase 16+) → condition_groups (Phase 15 DNF) → conditions[] (legacy)
- [Phase 16-recursive-condition-tree]: TaskEditor callsite bridged with groupsToTree/treeToGroups adapters — full migration is Plan 02 scope
- [Phase 16-recursive-condition-tree]: ConditionNode leaf = raw FdaCondition discriminated by absence of children key; branch = op AND|OR plus children array
- [Phase 16-recursive-condition-tree]: normaliseTransition accepts Record<string,unknown>; callsite casts FdaTransition via 'as unknown as' to handle legacy stored data
- [Phase 14-bug-backlog]: refetchOnMount: 'always' for PilotSessions sessions query — no cross-page cache coordination needed
- [Phase 14-bug-backlog]: ORDER BY session_id ASC in /subjects/{name}/runs — deterministic sort at DB level for SubjectSessions .reverse()
- [Phase 13]: class_name injected by PUT endpoint from DB record (authoritative) — class_mismatch check skipped for legacy rows without class_name
- [Phase 13]: preflight network failure is non-blocking — error caught silently so broken preflight endpoint never blocks session start
- [Phase 13]: stable promotion fires after graduation check and wrapped in try/except — trial increment never fails due to promotion error
- [Phase 17]: PilotHardwareConfig row identity switched from (pilot_id, hardware_module_id) to (pilot_id, name) — hardware_module_id retained as nullable FK for backward compat
- [Phase 17]: Seed maps Pi 'class' key -> config['class_name'] without module registry lookup — free-form naming mirrors Pi prefs.json HARDWARE dict
- [Phase 17-free-form-pilot-hardware-config]: HardwareCheckModal pendingEdits keyed by module_name (string) — was module_id (number); class_name not stripped before PUT
- [Phase 17-free-form-pilot-hardware-config]: PilotHardwareConfig rewritten to show pilot_hardware_config rows directly; cascade delete removed from hardware modules router
- [Phase 24-02]: New api/fda_validation.py is the hard-422 enforcement point for trigger_assignments/variables, kept fully separate from the soft _validate_task_definition drift-badge path; wired into POST/PUT /api/task-definitions via a 2-line reject_if_hard_errors(db, fda, toolkit_id) helper (routers/toolkits.py net growth 6 lines, budget 15)
- [Phase 24-02]: known_hw for hardware/timer trigger-action refs is semantic_hardware keys only; actions carrying an explicit "group" key (direct-ref/GUI-built) skip the ref check since fda_validation.py has no DB access to join hardware_module_ids to friendly names
- [Phase 24-02]: unknown trigger_name is enforced against toolkit.trigger_sources only via getattr(toolkit, "trigger_sources", None) or [] — a no-op on toolkits predating Plan 08's column
- [Phase 24-02]: view action key_template validated for shape only (non-empty string, every {token} names a declared variable/flag); key resolution deferred to Phase 13 preflight per 24-CONTEXT.md
- [Phase 24-03]: TriggerAssignmentPanel.add() patched with actions:[] to keep the codebase compiling after FdaTriggerAssignment.actions became required — Plan 05 fully rewrites this file
- [Phase 24-03]: isTimerModule/TrackerMethod exported from ActionEditor (not threaded as props) into HardwareActionFields, matching the labelStyle precedent — pure render-time reads, safe under a circular value export
- [Phase 24]: Plan 24-01: variables registry built now (shared with Phase 23); thread-local _trigger_ctx (not plain attrs); pi_timestamp injected implicitly by view action
- [Phase 24-05]: TriggerAssignmentPanel rewritten — handler enum and all config fields deleted; an assignment is now exactly (trigger_name, actions), with each action list hosted by the SAME ActionEditor StateBodyPanel uses (allowTriggerContext passed only here). add() seeds non-colliding trigger1/trigger2/... placeholders instead of an empty trigger_name, matching VariablesPanel's variable1/variable2 pattern — a required field is never produced empty by construction
- [Phase 24-05]: VariablesPanel rename commits onBlur (uncontrolled defaultValue input), not per-keystroke, to avoid remounting the row when its React key (the variable name) changes mid-edit; collision-checked against both existing variable names and toolkit.flags
- [Phase 24-04]: apply_trigger_assignments is handler-free — (trigger_name, actions) only; both hard-coded handler builders (_build_touch_detector_callback, _build_digital_input_callback) deleted outright, not corrected, along with the mock-only test that encoded detect_change()'s wrong per-channel-array contract
- [Phase 24-04]: _build_trigger_action_list is a thin composition over _build_action_callable with zero action-dispatch logic of its own — the trigger mechanism and the hardware-specific action list (licker) are now provably separate, verified by a detectedLick-equivalence test with no lick-specific runtime code
- [Phase 24-04]: Idempotent hot-reload tracked via self._fda_trigger_callbacks (trigger_name -> callbacks appended by the last apply_trigger_assignments call), diffed/removed at the top of every call, placed after the absent/empty backward-compat guard
- [Phase 24-04]: tools/validate_fda.py single-sourced against autopilot.tasks.fda_vocabulary (VALID_ACTION_TYPES/VALID_SPECIALS/VALID_TRIGGER_CONTEXT_KEYS); VALID_HANDLERS deleted outright; _validate_actions_list gained context_kind/allow_trigger_context params so ONE helper validates both state entry_actions and trigger actions
- [Phase 24-04]: _resolve_renamed_trigger_refs left as a harmless legacy no-op (docstring corrected) rather than deleted — trigger_assignments no longer carry a config key for it to rewrite, but deleting it was out of this plan's scope
- [Phase 24-04]: cmd_rename_hw_ref's TRIGGER_ASSIGNMENTS_SQL is now a no-op against current-format rows (no config.hardware_ref) — logged in deferred-items.md, not fixed (separate code path from validate(), out of Task 3 scope)
- [Phase 24-06]: check_for_detectors matches by capability (num_detectors:int-not-bool>0, device_name:non-empty-str, callable read()), not isinstance(v, Touch_Detector) — a hardware-module-registry detector's class is exec'd fresh by _resolve_hardware_classes and can never satisfy the identity check, so detection silently found zero LICKER trackers before this fix
- [Phase 24-06]: view action gains source_ref + runtime-resolved {device_name} key_template token (RUNTIME_KEY_TEMPLATE_TOKENS, single-sourced in fda_vocabulary.py) — resolved from the source hardware object's own device_name attribute at call time, so one task definition writes LICKER2 on one pilot and TONGUE2 on another without hard-coding either name
- [Phase 24-06]: the sourceless-lick canonical payload captures both pin_number and level from detect_change()'s own output — never {"trigger": "level"} — since execute_trigger's level is the TOUCH_INT IRQ edge (assert/deassert), not electrode state; wiring the trigger level would write interrupt polarity into whichever LICKER changed
- [Phase 24]: Plan 08: trigger_sources/detector_refs derived from lib AST; hard-422 on method-less hardware/timer actions in triggers and state bodies; constrained one-pick DetectorWriteWidget UI macro
- [Phase 25]: Plan 25-01: derive_channels/derive_view_keys single-source the detector key format; module_detector_channels surfaces cross-pilot conflict instead of merging
- [Phase 25]: Plan 02: Pi-side DVK-09/10/11 fixes (check_for_detectors first_channel, execute_trigger error containment, view_detector build-time resolution) landed in pi-mirror; no git commits made there per pi_rules
- [Phase 25]: Plan 25-03: preflight step 8 nested inside step 7's fda_json guard (not after) to reuse already_flagged as skip_modules without risking a swallowed NameError; key_template device_name resolution does not consult skip_modules per the plan's literal resolution-rules table
- [Phase 25]: Plan 25-05: view_key_unresolved is excluded from HardwareCheckModal's PUT loop and pendingEdits initialiser (it names no config row); is_detector resolved by module NAME (not module_id, which pilot_hardware_config rows don't carry) at both the PilotHardwareConfig add and edit entry points, sharing one ['hardware-module-methods', id] query key so no second fetch is introduced
- [Phase 23]: Wave 0 contract tests use per-test skip/xfail guards (not module-level) when a file mixes already-real integration tests with not-yet-real route tests; module-level importorskip only when every test shares one dependency
- [Phase 23-03]: hardware_libs.py::_flag_broken_task_defs carries its own action_type filter separate from fda_utils.py's scanner — widening a shared action vocabulary (adding "compute") requires checking every consumer's own filter, not just the scanner; fda_validation.py::_module_names deleted in favor of hw_introspect's already-computed caps['module_names'] (one fewer DB round trip)
- [Phase 23]: Phase 23 Plan 02: compute-lib storage substrate (kind column, upload gate, seed lib, auto-provisioning) landed and verified against real Postgres dev DB
- [Phase 23]: Plan 23-05: single lib-version resolver (pin->toolkit_default->stable->active->none) delivered; fourth active rung added beyond CONTEXT's literal chain to avoid breaking existing rig toolkits
- [Phase 23-compute-primitives-variables]: [Phase 23-07]: lib_version_unresolved checked independently of missing/incomplete_config in step 6's loop (before the cfg_row fetch), since CMP-17's undeployable-lib check is orthogonal to whether the pilot has configured the module at all
- [Phase 23-08]: onDeclareVariable added to ActionEditor's Props one task early (Task 1, not Task 3) to keep that task's own tsc green rendering ComputeActionFields; ActionEditor's own separate TYPE_COLORS const also gained a compute entry alongside StateBodyPanel's so the open action card's own chip isn't gray by fallback; a typed "new variable" name colliding with an existing variable/flag is rejected (inline message) rather than silently reused
- [Phase 23-compute-primitives-variables]: [Phase 23-07]: task_def_inspect.py uses a Depends(get_sa_session) generator matching toolkit_dispatch.py's shape (not pilot_hardware_config.py's bare with-block) so the mocked-db.execute TestClient pattern already used in test_view_key_preflight.py works
- [Phase 23]: 23-09: NON_CONFIG_ISSUES Set replaces per-kind checks for which preflight issues may never trigger a config PUT; VariableUsagePanel refetches via refetchOnMount:'always' rather than versionStamp (which tracks hw-lib pins, not fda_json saves)
- [Phase 23-11]: IfActionEditor derives hwModuleNames from its already-received hwModules prop (one-line fix) instead of threading a new prop through 4 components — provably the same array TaskEditor.tsx:202 already derives its own hwModuleNames from
- [Phase 23-11]: visibleOperandTypes(stored, hasToolkit) / visibleArgModes(mode, allowTriggerContext) are functions of what's ALREADY stored in a slot, not static lists — the legacy-operand escape (flag/hardware in conditions, flag in ArgInput) is offered only when the stored value already has that shape, and vanishes once edited; re-ran the decrement/reset preflight DB query live before deleting (0/153 task defs) rather than trusting the plan's stated result
- [Phase 23-11]: ArgInput's new view mode offers plain view keys only — no detector channels (Pi's _resolve_arg has no view_detector branch) and no hwModuleNames (would require prop-threading through 5 components; free-text fallback covers it) — recorded scope decision for 23-12's checkpoint

## Accumulated Context

### Roadmap Evolution

- Phases 1–4 archived (2026-07-26): moved to `.planning/archive/`. Superseded and re-planned inside phases 9–17 — the system is well past them. **Ignore when reviewing GSD phases.** Phases 5–8 (Pi Code Editor) marked Deferred: never started, not in the current plan.
- Phase 24 added (2026-07-26): Trigger Assignment Action Lists — triggers run the same action vocabulary as state `entry_actions`, assigned from the UI. Sequenced **before** Phase 23 per stabilization plan.
- Execution order agreed 2026-07-26: **24 → 23 → review → 18 → Open Ephys**. Rationale and full scope in `.planning/STABILIZATION_PLAN.md`.
- Phases 12–17 were validated manually on the live system; the "Human Verification Required" lists in their VERIFICATION.md files are stale bookkeeping, not open work.
- Phase 25 added (2026-07-27): Detector-Derived View Keys (DVK-01–08) — backend derives `LICKER0…LICKER3` from `device_name` × `num_detectors` and the FDA editor offers them as view operands / `key_template` values; per-pilot resolution lands in Phase 13's `preflight_validate`. Runs **after** Phase 24, which it depends on.
- TRIGA-12 added to Phase 24 (2026-07-27) and folded into plan 24-06: `check_for_detectors` matches detectors by capability instead of `isinstance(v, Touch_Detector)`. Identity matching silently yields zero `LICKER` trackers for a detector declared through the hardware-module registry, because `_resolve_hardware_classes` `exec`s the class from `source_code` into a fresh class object. `hardware/i2c.py` stays off-limits, so the fix lives in `check_for_detectors`. Plan 06's "do not touch `mics_task.py`" constraint is now scoped to that one method — safe because 06 is the only wave-3 plan and runs after 01 and 04.

- **Scope change (2026-07-27): sourceless toolkits only.** All future work targets
  backend-authored ("sourceless") toolkits; the legacy `learning_cage`-backed toolkit is no
  longer run. Detector/lick functionality must still exist — via registered hardware modules
  on the sourceless path, not the `learning_cage` Python class. Invalidates plans 06/07/08 as
  written; see `24-REPLAN-BRIEF.md`. Plans 01–05 unaffected.
- **Constraint discovered (2026-07-27): a sourceless task receives ONLY the `Modules` group.**
  `mics_task.py:94` replaces `self.HARDWARE` wholesale and `get_dispatch_spec` emits only
  `hardware["Modules"]`, so there is no `GPIO`/`I2C`/`Timers` group. Everything a sourceless
  task touches must be a registered hardware module. This makes Pi-class `SEMANTIC_HARDWARE`
  irrelevant on that path, including the `learning_cage` entry added by plan 24-01.
- **Correction (2026-07-27): TRIGA-06's DB claim is wrong.** It records task def 185 as the
  only row with non-empty `trigger_assignments`. Task def **181** has one too, and it caused
  three of the seven post-execution defects. Re-run the query; do not trust the recorded finding.
- **Registry additions (2026-07-27):** hardware modules 7 (`MPR121`→`Touch_Detector`, i2c.py)
  and 8 (`TOUCH_INT`→`Digital_In`, gpio.py) created with pilot-1 configs and attached to
  toolkit 100. These were prerequisites for any sourceless detector work.
- **Phase 18 context REVISED (2026-08-03)** — generalized from a DLC-shaped transport into the
  general external-device substrate, so OpenEphys can be its first consumer. Five additions
  (transport roles + `@decoder`, liveness/staleness split, egress queue, run lifecycle hooks,
  device lease). `18-01`/`18-02` plans superseded → `superseded/`; **Phase 18 must be re-planned.**
  EXTLINK-07 and EXTLINK-13 amended; EXTLINK-14–18 added.
- **Phases 26, 27, 28 added (2026-08-03): the OpenEphys arc.** 26 OpenEphys Device Control
  (EPHYS-01–05) → 27 OpenEphys Firing Rate over ZMQ (EPHYS-06–10) → 28 TTL vs Network Sync
  Validation (EPHYS-11–12). All three depend on Phase 18. Roadmap gains an arc preamble section
  documenting the locked scope decisions; `REQUIREMENTS.md` gains an EPHYS section.
- **Execution order amended (2026-08-03):** **24 → 25 → 23 → review → 18 → 26 → 27 → 28.**
  Supersedes the 2026-07-26 order, which ended with a generic "Open Ephys".
- **Scope decisions locked (2026-08-03):** the Pi owns both OE channels (HTTP control + ZMQ data),
  backend owns only the lease; the OE box is shared across rigs but never concurrently, so the
  lease is a safety net with no scheduling UX; **the TTL cable stays** and Phase 28 measures the
  network path against it rather than replacing it.
- **External prerequisite flagged for Phase 27 (2026-08-03):** the OE signal chain needs a spike
  detector/sorter upstream of the ZMQ plugin, with sorting configured — the plugin transfers
  **spikes, not firing rate**, and sorted unit IDs do not exist without it. Rig configuration, not
  MICS work, but 27 is unplannable as scoped until confirmed.

## Blockers

None currently.

---

## Open Questions

- OR conditions between FDA transitions — deferred to v2; AND-only is sufficient
- Multi-Pi Pi editor support — deferred to v2; single Pi host for now
- Audit log for Pi exec actions — deferred to v2

---

## Pi Development Workflow

Authoritative rules live in `.claude/skills/pi-deploy/SKILL.md`. They **override** any
conflicting instruction inside a PLAN file.

1. **Verify sync first** (Pi is source of truth). Read-only:
   `rsync -avzi --dry-run --exclude='__pycache__' --exclude='.git' -e "ssh -i ~/.ssh/pi_mics" pi@132.77.72.28:~/Apps/mice_interactive_home_cage/ /home/ido/pi-mirror/`
   Do **not** pull while an agent is mid-edit — it clobbers in-flight work.
2. **Edit** in `/home/ido/pi-mirror/` only. Never edit on the Pi.
3. **Syntax check**: `cd /home/ido/pi-mirror && python3 -m py_compile <file>`.
   `autopilot` **cannot be imported** on this host (`npyscreen` missing), so only
   stdlib-only tests (`tests/test_fda_vocabulary.py`) are agent-runnable.
4. **Deploy only session-edited files**, never the whole mirror, never `--delete`:
   `rsync -avz --relative -e "ssh -i ~/.ssh/pi_mics" /home/ido/pi-mirror/./<path> … pi@132.77.72.28:~/Apps/mice_interactive_home_cage/`
5. **NO git in `/home/ido/pi-mirror`** — not even `status`. To prove a file is untouched:
   `diff <(ssh -i ~/.ssh/pi_mics pi@132.77.72.28 'cat ~/Apps/.../f.py') /home/ido/pi-mirror/.../f.py`
6. **Never start/stop the pilot; never run Python on the Pi.** Hand the user the command.
7. Pi tests are USER-RUN, from `~/Apps/mice_interactive_home_cage` **on the Pi** — not from
   `~/pi-mirror`, which is the dev host.

> Plans 06/07/08 still contain the forbidden `git -C /home/ido/pi-mirror status` check and a
> `cd ~/pi-mirror && pytest` step. Fix both during the re-plan.

## Next Actions

1. **Confirm Phase 23 Plan 02** landed cleanly (kind-column migration + `seed_compute.py` +
   declared-imports allowlist — commits `feat(23-02): kind column...` and `feat(23-02): seed
   Compute Ops lib...` are on disk from a concurrent execution observed during plan 03's run, but
   no `23-02-SUMMARY.md` existed as of this note) and write its summary if missing.
   See `23-02-PLAN.md` and `23-01-SUMMARY.md` "Next Phase Readiness".
   (Plans 03 and 04, both Wave 2, are now also done — see "Phase 23 status" above,
   `23-03-SUMMARY.md`, and `23-04-SUMMARY.md`. Plan 04's 4 pi-mirror files are staged for deploy
   at plan 23-10, uncommitted in the pi-mirror working tree, same as plan 02's Phase 25 files
   below. Plan 03's `variable_never_written_issues` is not yet wired into preflight — that is
   plan 23-07's job.)
2. **Execute Phase 25 Plan 06** (last plan in phase 25, still outstanding — deferred while phase
   23 Wave 0 was picked up) — **deploy** plan 02's seven pi-mirror files (`fda_vocabulary.py`,
   `mics_task.py`, `task.py`, and four `tests/` files — see `25-02-SUMMARY.md` "Next Phase
   Readiness" for the exact rsync list) AND the plan 04/05 React rebuild (confirm the deployed
   bundles are `dist/TaskEditor-B6-dKcPk.js`, `dist/HardwareCheckModal-DKJUfoGY.js`,
   `dist/PilotHardwareConfig-B09He_Dl.js` — see `25-04-SUMMARY.md` and `25-05-SUMMARY.md` "Next
   Phase Readiness" for the exact operand JSON / config round-trip to look for), run the three
   new USER-RUN Pi test files plus the pre-existing suite, and rig-prove DVK-09 (channel 4 lands
   in `LICKER4`) and DVK-11 (a transition on "MPR121 — channel 2" fires, then re-fires unchanged
   after a `device_name` rename). Also owns the manual/behavioural verification of plan 04's
   editor pickers (grouped `<optgroup>`s, the "(unknown)" flag, the S3 type-switch guard) and
   plan 05's `HardwareCheckModal`/`PilotHardwareConfig` rendering (both `view_key_unresolved`
   shapes, the edit-flow `first_channel` round-trip) — both deferred per their own
   `<verification>` notes.
3. **Run the full Pi test suite** (USER-RUN — `autopilot` unimportable on the dev host), still
   outstanding from phase 24 and now larger after plan 02's additions, plus the new
   `test_compute_ops.py` once plan 23-04 lands:
   `cd ~/Apps/mice_interactive_home_cage && python3 -m pytest tests/ -q`

Note: Phase 23 was re-planned 2026-08-03 as 10 plans in 6 waves against a "compute-as-hardware-lib"
reframe (see the `docs(23):` commits immediately before `test(23-01):` in git log) — the prior
"plans are stale" note above no longer applies. Plan 01 (Wave 0 contract tests), Plan 03
(backend compute validation + variable-scan), Plan 04 (Wave 2, Pi-runtime compute action), and
Plan 05 (Wave 3, single lib-version resolution chain, CMP-17/19), and Plan 06 (Wave 3, kind-aware
Hardware Libraries GUI, CMP-12/18) are done; see "Phase 23 status" above and
`23-01-SUMMARY.md`/`23-03-SUMMARY.md`/`23-04-SUMMARY.md`/`23-05-SUMMARY.md`/`23-06-SUMMARY.md`.
6/10 plans done. Remaining outstanding in phase 23: plans 07-10 (later waves) and Phase 25 plan 06
(separate phase, still not executed).

Note: `gsd-tools requirements mark-complete` found no checkbox/traceability rows for
CMP-03/04/05/06/10/11/12/15/17/19 in `REQUIREMENTS.md` (same gap previously found for
DVK-02/06/07/11) —
completion is tracked via the ROADMAP.md phase-23 status line instead, updated via
`gsd-tools roadmap update-plan-progress 23`. `gsd-tools state advance-plan` still errors
("Cannot parse Current Plan or Total Plans in Phase from STATE.md" — this file predates that
command's expected conventions); `state update-progress` DOES work and was used to update the
frontmatter above (51 total / 37 completed / 73%). `record-metric`/`record-session` remain no-ops
on this STATE.md; position is tracked via the prose "Phase NN status" sections above, per this
file's established pattern.

---
*Last updated: 2026-08-03 — phase 23 plan 06 executed (Wave 3): kind-aware Hardware Libraries GUI
(CMP-12/18). `types/index.ts` gained `LibKind`/`HardwareLib.kind`/
`HardwareLibVersion.declared_imports`/`HardwareModule.lib_kind`; `uploadHardwareLib` sends
`kind`/`declared_imports`. `HardwareLibs.tsx` gained an All/Hardware/Compute filter chip row with
counts (client-side filter, no new endpoint) and a kind-aware upload form (compute-only
`declared_imports` input, stdlib-only helper text); `HardwareLibDetail.tsx` shows `kind` +
`declared_imports` read-only. `apiFetch` already surfaced 422 `detail` verbatim — confirmed by
reading `api/client.ts`, no change needed. `tsc --noEmit` and `npm run build` both clean
(`dist/HardwareLibs-DPUByP4B.js`, `dist/HardwareLibDetail-CKGnbh6y.js`); `App.tsx`/`Layout.tsx`
diffs both empty — no new page, no new route, no `NAV_LINKS` change. No deviations. See
`23-06-SUMMARY.md`. Phase 23 now 6/10 plans done. Phase 25 plan 06 (last plan in that phase)
remains outstanding. Next: phase 23 plans 07-10 (later waves) or phase 25 plan 06, per Next
Actions above.*
