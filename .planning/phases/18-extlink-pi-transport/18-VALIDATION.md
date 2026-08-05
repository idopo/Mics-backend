---
phase: 18
slug: extlink-pi-transport
status: approved
nyquist_compliant: true
wave_0_complete: false
created: 2026-08-03
revised: 2026-08-05
---

# Phase 18 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.
> Derived from `18-RESEARCH.md` § Validation Architecture. Read that section for rationale.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework (backend)** | pytest, inside the `api` docker container |
| **Framework (Pi mirror, agent-runnable)** | pytest — **only for test files with ZERO `autopilot.*` imports** (see the hard constraint below) |
| **Framework (Pi, USER-RUN)** | pytest on the rig, for anything importing `autopilot.*` |
| **Config file** | none — Wave 0 installs `msgpack` on the agent side |
| **Quick run command (backend)** | `docker compose exec api python -m pytest -q api/tests/test_view_key_preflight.py -k lease` |
| **Quick run command (Pi mirror)** | `cd ~/pi-mirror && python3 -m pytest -q tests/test_extlink_*.py` |
| **Full suite (backend)** | `docker compose exec api python -m pytest -q` |
| **Full suite (Pi)** | **USER-RUN**: `cd ~/Apps/mice_interactive_home_cage && python3 -m pytest tests/ -q` |
| **Estimated runtime** | backend ~30s; Pi-mirror unit files ~2s |

### Hard constraint that shapes the whole plan

`import autopilot.<anything>` executes `autopilot/__init__.py`, which imports `npyscreen` —
**not installed on the dev host** (verified this session; reproduces Phase 23's finding). `msgpack`
and `zmq` are also absent from the dev host. Therefore:

> **Any test importing `autopilot.*` is USER-RUN, regardless of whether the logic under test needs
> hardware.**

**Design requirement (plan-shaping, not a footnote):** keep the wire codec, `@decoder` dispatch,
stale-policy resolver, liveness predicate, and `_EgressWorker` in an **`autopilot`-free sibling
module** (recommended: `external_hardware_wire.py`), imported *by* `external_hardware.py` with no
reverse dependency. This is the only way the agent gets unit coverage on the pure logic. If these
live inside `external_hardware.py` alongside `from autopilot.hardware import Hardware`, **all of
them become USER-RUN and the phase loses its agent-side feedback loop entirely.**

**⚠ Rebuild gotcha:** the `api` container has no bind mount — new test files are invisible to a
running container. `docker compose up --build api` before trusting a backend test result.

---

## Sampling Rate

- **After every task commit:** the specific test file touched — e.g.
  `cd ~/pi-mirror && python3 -m pytest -q tests/test_extlink_egress.py`, or
  `docker compose exec api python -m pytest -q api/tests/test_view_key_preflight.py -k lease`
- **After every plan wave:** `docker compose exec api python -m pytest -q` (rebuild first) **plus**
  `cd ~/pi-mirror && python3 -m pytest -q tests/test_extlink_wire.py tests/test_extlink_decoder.py tests/test_extlink_egress.py tests/test_extlink_lifecycle.py tests/test_extlink_liveness.py tests/test_wait_extlink_ready_transitions.py tests/test_mics_task_attrs.py`
- **Before `/gsd:verify-work`:** full backend suite green + all agent-runnable Pi-mirror tests green
  + the single consolidated rig checkpoint confirmed by the user
- **Max feedback latency:** ~2–4 minutes (backend) — the pytest run itself is ~30s, but the
  `api` container has no bind mount, so **every** backend `<verify>` block in this phase prefixes
  `docker compose up --build -d api` and the rebuild dominates. ~2 seconds (Pi-mirror units),
  which is where the tight loop actually lives and why the `autopilot`-free split matters.

---

## Per-Task Verification Map

Task IDs are assigned at planning. The contract below is **requirement → test**; the planner must
map each task onto a row here, and every row must be claimed by some task.

| Requirement | Behavior | Test Type | Automated Command | File Exists |
|---|---|---|---|---|
| EXTLINK-14 | `@decoder` translates a foreign frame → declared signal/event updates; truncated frame returns empty, never raises; unknown field dropped, known fields still applied | unit (Pi mirror, agent) | `cd ~/pi-mirror && python3 -m pytest -q tests/test_extlink_decoder.py` | ❌ W0 |
| EXTLINK-14 | `role: sub_connect` selects SUB + `.connect()`, skips DEALER-identity check; `router_bind` selects ROUTER + `.bind()` — via injected fake socket factory, no real socket | unit (Pi mirror, agent) | `... -k role_selection` | ❌ W0 |
| EXTLINK-18 | **`role: "none"` returns a plan with NO socket** — `socket_plan` must not invent a port or fall back to a default role. Newly agent-testable (was rig-only before the 2026-08-03 gap fix) | unit (Pi mirror, agent) | `... -k role_none` | ❌ W0 |
| EXTLINK-18 | **`role: "none"` with NO liveness override raises at construction** — `validate_role_liveness(ROLE_NONE, False, "DemoControl")` raises `ValueError` naming BOTH the class and the role; with an override it returns `None`; the two socketed roles never require one. A pure function in the `autopilot`-free wire module, so it has ONE definition (plan 18-10 calls it) and the agent can run it. Silently defaulting to `alive=True` is REJECTED | unit (Pi mirror, agent) | `... -k role_none` | ❌ W0 |
| EXTLINK-18 | **Config validation accepts `role: "none"` with neither `listen_port` nor `connect_port`** and does not 422 on their absence | unit (backend) | `docker compose exec api python -m pytest -q api/tests/test_view_key_preflight.py -k role_none` | ❌ W0 (extend) |
| EXTLINK-18 | A control-only instance still **registers `<source_id>.alive`, starts the liveness poll, starts the egress worker, and fires lifecycle hooks** — i.e. participates fully in the readiness gate despite having no socket | unit (Pi mirror, agent) | `cd ~/pi-mirror && python3 -m pytest -q tests/test_extlink_lifecycle.py -k control_only` | ❌ W0 |
| EXTLINK-15 | **Egress items are ZERO-ARG CALLABLES** — the worker is wired `send_fn=lambda fn: fn()` and every test enqueues a callable whose side effect proves it was invoked. Pins the seam Phase 26 (`26-10-PLAN.md:169-171`) already builds on; a data-item model would store its lambdas and never call them | unit (Pi mirror, agent) | `cd ~/pi-mirror && python3 -m pytest -q tests/test_extlink_egress.py -k fifo` | ❌ W0 |
| EXTLINK-15 | Egress FIFO order preserved under one worker | unit (Pi mirror, agent) | `cd ~/pi-mirror && python3 -m pytest -q tests/test_extlink_egress.py -k fifo` | ❌ W0 |
| EXTLINK-15 | Overflow drops the **newest**, increments `dropped`, and items 1–2 (not 3) are the ones sent | unit (Pi mirror, agent) | `... -k drop_newest` | ❌ W0 |
| EXTLINK-15 | Failure is never retried; worker survives and attempts the next item | unit (Pi mirror, agent) | `... -k no_retry` | ❌ W0 |
| EXTLINK-15 | `alive` flips after exactly N consecutive failures, edge-triggered (fires once, not per failure) | unit (Pi mirror, agent) | `... -k alive_flips` | ❌ W0 |
| EXTLINK-16 | `on_run_start` retried until ready inside the wait window (fake clock, no real sleep) | unit (Pi mirror, agent) | `cd ~/pi-mirror && python3 -m pytest -q tests/test_extlink_lifecycle.py` | ❌ W0 |
| EXTLINK-16 | `on_run_start` returns before the hook's artificial delay elapses (proves non-blocking) | unit (Pi mirror, agent) | `... -k never_blocks` | ❌ W0 |
| EXTLINK-16 | `on_run_stop` invoked exactly once per `.release()` | unit (Pi mirror, agent) | `... -k stop_called_once` | ❌ W0 |
| EXTLINK-16 | `run_ctx` has exactly the six locked keys and no seventh | unit (Pi mirror, agent) | `... -k run_ctx_shape` | ❌ W0 |
| EXTLINK-16 | Regression pin: `mics_task.end()` still calls `super().end()` — the chokepoint everything depends on. **CORRECTED at planning:** must be written as an `ast.parse` over the source text, NOT by importing `mics_task` (that import pulls the full `autopilot` chain and would make the row USER-RUN). Verified agent-runnable as written | unit (Pi mirror, agent) | `cd ~/pi-mirror && python3 -m pytest -q tests/test_mics_task_attrs.py -k end` | ❌ W0 (extend) |
| EXTLINK-07 | Liveness default: alive inside window, dead outside | unit (Pi mirror, agent) | `cd ~/pi-mirror && python3 -m pytest -q tests/test_extlink_liveness.py` | ❌ W0 |
| EXTLINK-07 | **Liveness independent of signal staleness** — reachable-but-quiet stays `alive` while its signal returns the declared default (the core EXTLINK-07 split, decoupled in code not just docstring) | unit (Pi mirror, agent) | `... -k independent` | ❌ W0 |
| EXTLINK-07 | Lib-supplied predicate replaces the default entirely | unit (Pi mirror, agent) | `... -k override` | ❌ W0 |
| EXTLINK-07 | **The liveness predicate is evaluated OFF the shared Tornado IOLoop** — `LivenessPoller` runs it on a device-owned daemon thread, caches the result for a cheap read, swallows a raising predicate, and fires `on_change` edge-triggered. Mandatory now that `role: "none"` must carry an override whose only signal is an outbound call | unit (Pi mirror, agent) | `cd ~/pi-mirror && python3 -m pytest -q tests/test_extlink_lifecycle.py -k liveness_poller` | ❌ W0 |
| EXTLINK-17 | Lease blocks a second run on the same host, issue names the holding pilot/subject/run | unit (backend) | `docker compose exec api python -m pytest -q api/tests/test_view_key_preflight.py -k lease` | ❌ W0 (extend) |
| EXTLINK-17 | Lease key is **host**, not host:port — same host + different ports still collide | unit (backend) | `... -k lease_key_is_host` | ❌ W0 (extend) |
| EXTLINK-17 | Manual force-release clears the issue | unit (backend) | `... -k force_release` | ❌ W0 (extend) |
| EXTLINK-17 | Reconciliation clears the lease given a fabricated stale Redis `updated_at` — called directly, not by waiting out a real timeout | unit (backend) | `... -k reconciliation` | ❌ W0 (extend) |
| EXTLINK-17 | New issue kind is registered in `PREFLIGHT_ISSUE_KINDS` **and** mirrored in `HardwareCheckModal.tsx`'s `PreflightIssue` union | unit (backend) + read | `... -k issue_kind_registered` | ❌ W0 (extend) |
| EXTLINK-09 | AST extractor emits `ast_metadata.extlink` for `@signal`/`@event`/`@command`/`@decoder` | unit (backend) | `docker compose exec api python -m pytest -q api/tests/test_hardware_libs_flag_broken.py -k extlink` *(confirm target file at plan time)* | ❌ W0 (extend) |
| EXTLINK-09 | `@event(payload={"object": str})` — bare type names are `ast.Name`, **not** `literal_eval`-safe; extractor must not raise and must emit string-typed `{"object": "str"}` | unit (backend) | `... -k payload_bare_types` | ❌ W0 (extend) |
| EXTLINK-09 | `POST /api/hardware-libs` round-trip with a full `ExternalHardware` source → `ast_metadata.extlink` populated | integration (backend) | `... -k upload_extlink` | ❌ W0 (extend) |
| EXTLINK-03/12 | Wire codec encode/decode round-trip; malformed bytes → `None`, counter incremented, never raises | unit (Pi mirror, agent) | `cd ~/pi-mirror && python3 -m pytest -q tests/test_extlink_wire.py` | ❌ W0 |
| EXTLINK-13 | **CORRECTED at planning — the original row was wrong.** It proposed building a bare `FiniteDeterministicAutomaton` to keep this agent-runnable, but `from autopilot.utils.FiniteDeterministicAutomaton import …` still executes `autopilot/__init__.py` → npyscreen, so it would have been USER-RUN either way. Replaced by contracting the gate's **decision** as a pure `ready_gate_decision(...)` function in the `autopilot`-free module — fully agent-runnable. The FDA *wiring* remains rig-only (row below) | unit (Pi mirror, agent) | `cd ~/pi-mirror && python3 -m pytest -q tests/test_extlink_lifecycle.py -k ready_gate` | ❌ W0 |
| EXTLINK-01/02/11 | `router_bind` end-to-end: DEALER connects, pushes signal, FDA transition fires | manual + rig | USER-RUN smoke script | N/A |
| EXTLINK-14 | `sub_connect` end-to-end against a live PUB | manual + rig | USER-RUN smoke script `publish` subcommand | N/A |
| EXTLINK-13 | Full three-exit behavior through a real task start | manual + rig | USER-RUN | N/A |
| EXTLINK-16 | Hooks fire on all three real teardown paths | manual + rig | USER-RUN | N/A |
| EXTLINK-18 | Zero-signal control-only module (**`role: "none"`, no socket**) binds and participates in the gate **on the real Pi** — the mechanism itself is now agent-tested above, so this row proves only the end-to-end wiring | manual + rig | USER-RUN | N/A |
| EXTLINK-18 | The SAME control-only lib with its `liveness_hook` REMOVED fails at construction on the real Pi, logged by `init_hardware`'s per-module `except` naming the class and the role — the unhappy path of the rule above (plan 18-12 checkpoint step 6b) | manual + rig | USER-RUN | N/A |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

- [ ] `~/pi-mirror/tests/test_extlink_wire.py` — new, `autopilot`-free — EXTLINK-03/12
- [ ] `~/pi-mirror/tests/test_extlink_decoder.py` — new, `autopilot`-free — EXTLINK-14/08
- [ ] `~/pi-mirror/tests/test_extlink_egress.py` — new, `autopilot`-free — EXTLINK-15
- [ ] `~/pi-mirror/tests/test_extlink_lifecycle.py` — new, `autopilot`-free — EXTLINK-16
- [ ] `~/pi-mirror/tests/test_extlink_liveness.py` — new, `autopilot`-free — EXTLINK-07
- [ ] `~/pi-mirror/tests/test_wait_extlink_ready_transitions.py` — new, `autopilot`-free —
      EXTLINK-13. **Documented deviation from this document's original classification:** the
      readiness-gate row was filed as a "stretch" on the assumption it needed a real
      `FiniteDeterministicAutomaton`. It does not — any dotted `autopilot.*` import pulls
      `autopilot/__init__.py` → npyscreen and would make the file USER-RUN either way — so plan
      18-02 Task 3 contracts the gate's DECISION as a pure `ready_gate_decision(...)` instead,
      making the row fully agent-runnable and leaving only the FDA wiring on the rig
- [ ] Extend `~/pi-mirror/tests/test_mics_task_attrs.py` — `super().end()` regression pin — EXTLINK-16
- [ ] Extend `api/tests/test_view_key_preflight.py` — device lease — EXTLINK-17
      *(NOT `test_toolkit_dispatch.py` — that covers dispatch-spec shape; preflight issue kinds live here)*
- [ ] **RESOLVED at planning:** `grep -rl "extract_ast_metadata" api/tests/` returns nothing, and
      `test_hardware_libs_flag_broken.py` covers something else — so EXTLINK-09 gets a dedicated new
      file `api/tests/test_hardware_libs_extlink.py` rather than extending an existing one
- [ ] **Agent-side install:** `pip install msgpack` in the environment running the `autopilot`-free
      Pi-mirror tests, so the codec tests call real `packb`/`unpackb` instead of mocking
- [ ] **USER-RUN install:** `msgpack` on the rig, pinned for **Python 3.7.3** — resolve the exact
      version with a real `pip install`, do **not** hardcode a guess (Research Open Question 3)
- [ ] Plan-time decision: extend `extlink_smoke.py` with a `publish` subcommand for the
      `sub_connect` rig check, or ship a separate script

---

## Manual-Only Verifications

Consolidated into **one rig checkpoint** — the agent does not scatter Pi touches across the plan.
Per project rules the agent never runs git on the Pi, never starts/stops the pilot, and never runs
Python on the Pi; every item below is a command handed to the **user**.

| Behavior | Requirement | Why Manual | Test Instructions |
|---|---|---|---|
| `router_bind` end-to-end | EXTLINK-01/02/11 | Needs a real bound Tornado IOLoop in the live `pilot.py` process | `extlink_smoke.py probe --pi-host … --listen-port … --source-id …`; confirm the FDA transition fires |
| `sub_connect` end-to-end | EXTLINK-14 | No foreign publisher or live IOLoop exists in the mirror; proves `add_callback` registration works on the real process | Run the PUB-side script against the deployed Pi; confirm the view key updates |
| `_wait_extlink_ready` three exits | EXTLINK-13 | Wiring runs through `mics_task.__init__`/`load_fda_from_json`, which pull the full `autopilot` chain | Start a task with a required external source; exercise proceed / `EXTLINK_SKIP_WAIT` / timeout |
| Lifecycle hooks on all teardown paths | EXTLINK-16 | Requires the real `pilot.py::run_task` loop | Normal completion, STOP button, and an induced task exception |
| Liveness flip → CONTINUOUS → ES | EXTLINK-07 | `dispatch_event()` needs a real `pigpio.pi` clock, no fallback timebase by design | Drop the source mid-run; confirm the event in ES |
| Egress under real network latency | EXTLINK-15 | The property is "the FDA thread's timing is unaffected" — needs a real scheduler under real I/O | Hang the remote endpoint; confirm FDA timing unaffected |
| Control-only lib missing its `liveness_hook` | EXTLINK-18 | The rule is a Pi-side CONSTRUCTION check — preflight is deliberately silent and the AST extractor has no opinion, so only a real task start can observe it | Repin the module to the override-less Lib B version, start the task, read the pilot log for the class+role message, repin back (plan 18-12 step 6b) |
| Lease from a genuine pilot disconnect | EXTLINK-17 | Unit test uses a fabricated stale timestamp; this proves the Redis staleness signal fires from a real dropped connection | Kill the pilot mid-run; confirm the lease releases |

### Explicitly NOT an acceptance criterion

**Do not assert that a CONTINUOUS event exists in ES for `on_run_stop()` itself.**
`event_dispatcher.stop()` runs *before* `task.end()`/`release()` in `pilot.py`'s teardown, so the
event provably races and may never be dispatched. Winning that race requires editing `pilot.py`,
which is out of scope. **Verify stop behaviour by its effect** — device returned to idle, lease
released — not by an ES record. If Phase 26 needs stop-time ES visibility, log it *before* the
STOP/exception path unwinds and test that instead.

---

## Validation Sign-Off

- [x] All tasks have `<automated>` verify or a Wave 0 dependency
- [x] Sampling continuity: no 3 consecutive tasks without automated verify
- [x] Wave 0 covers all ❌ references above
- [x] The `autopilot`-free sibling-module split is honoured — otherwise every Pi test becomes
      USER-RUN. **Reinforced 2026-08-05:** plans 18-05 and 18-06 now FORBID splitting
      `external_hardware_wire.py` / `external_hardware_runtime.py` into sibling modules. The
      agent loads them BY PATH with `spec_from_file_location`, which yields one module object
      with no package — a split would turn every attribute read into an `AttributeError` and
      break ONLY the agent tests, silently, while the rig kept working. Trim prose to stay
      under 300 lines; never split
- [x] Every manual-only row is justified and lands in the single consolidated rig checkpoint
- [x] No watch-mode flags
- [x] Feedback latency: ~2s on the Pi-mirror units (the working loop). The backend's ~2–4 min
      is rebuild-bound and irreducible without a bind mount — accepted, and the reason the
      phase's pure logic was pushed into `autopilot`-free modules
- [x] `nyquist_compliant: true` set in frontmatter
- [ ] `wave_0_complete` — **NOT ticked. Wave 0 has not executed.** Plans 18-01/18-02/18-03/18-04
      create the test files; flip this only once they are on disk and skipping/passing for the
      right reason

**Approval:** approved 2026-08-05 (revised alongside the plan revision that added the
`role: "none"` liveness-override rule, the callable-egress model, and the off-IOLoop
`LivenessPoller`)
