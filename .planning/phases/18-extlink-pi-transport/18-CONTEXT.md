# Phase 18: MICS-Link — Pi Transport + ExternalHardware — Context

**Gathered:** 2026-05-31
**Revised:** 2026-08-03 — generalized so OpenEphys is the first consumer (see `<revision_2026_08_03>`)
**Status:** Ready for planning — **existing 18-01/18-02 plans are SUPERSEDED and must be re-planned**
**Source:** Master plan `/home/ido/.claude/plans/as-you-are-already-effervescent-hearth.md`, narrowed 2026-05-31; refinement session 2026-08-03 driven by `docs/open_ephys_integration.pdf`.

<domain>
## Phase Boundary

Pi gains a structured, crash-safe channel that lets external software running on other computers (OpenEphys, DeepLabCut, photometry rigs, …) participate in the existing View / FDA framework as **versioned, per-toolkit hardware modules**. **The flow uses the existing Phase 09–13 + Phase 17 plumbing end-to-end.** No new DB tables for the transport itself. No new top-level dispatch kwarg. No new prefs.json block. The `ExternalHardware` subclass IS a hardware library; an instance of it IS a hardware module; its per-pilot network params live in the existing `pilot_hardware_config.config` JSON.

**In scope (Phase 18):**
- New `ExternalHardware` Python base class with `@signal` / `@event` / `@command` decorators (Pi-side, in `~/pi-mirror/autopilot/autopilot/hardware/`).
- **Two transport roles** — `router_bind` (MICS-native SDK dials in) and `sub_connect` (Pi dials out to a foreign publisher), with a per-lib `@decoder` hook for foreign wire formats.
- View Tracker auto-registration per signal + `<source_id>.alive` boolean tracker.
- Per-signal stale policy (`hold_last` / `return_default` / `return_none`).
- **Lib-supplied liveness hook** with a data-arrival default.
- **Egress path** — ordered, non-blocking outbound queue with a bounded buffer and drop accounting.
- **Run lifecycle hooks** — `on_run_start(run_ctx)` / `on_run_stop()`, plus a backend safety net.
- **Device lease** — backend-side arbitration for a device shared across pilots, surfaced as a preflight issue.
- Ingress validation that drops unknown messages without raising into the IOLoop.
- Small AST extractor extension in `api/routers/hardware_libs.py` so the decorators land in `ast_metadata`.
- `mics_task.init_hardware()` post-pass that calls `.bind(ioloop, view)` on every `ExternalHardware` instance.
- Standalone smoke-test DEALER script (`~/pi-mirror/scripts/dev/extlink_smoke.py`).

**Out of scope (deferred):**
- The `mics-link` Python SDK package.
- Stub generation + bootstrap-zip endpoints + "Download SDK" GUI.
- Per-pilot external-sources health dashboard + orchestrator WS forwarding.
- **The OpenEphys hardware lib itself** — Phase E1 (control/recording/folder) and E2 (firing rate over ZMQ). Phase 18 delivers only the substrate they stand on.
- DeepLabCut reference integration.
- **No `EXTLINK` block in `pilot/prefs.json`** — explicitly rejected. Network config lives only in `pilot_hardware_config.config`.
- **No singleton `ExternalLink` class** on the Pi — explicitly rejected. Each `ExternalHardware` instance owns its own socket.

</domain>

<revision_2026_08_03>
## Why this phase was revised

Phase 18 as originally locked assumed **one** consumer shape: our own SDK, speaking our MessagePack envelope, **dialing into** the Pi's ROUTER. OpenEphys — now confirmed as the first real consumer — breaks three of those assumptions, and DeepLabCut will break the same ones later. Refining the base class now avoids writing it twice.

**What OpenEphys needs that the original design does not provide:**

1. **Opposite direction, foreign format.** The OE ZMQ Interface plugin is a **PUB socket publishing its own JSON-header + binary format** (carrying an OE sample number). It will never dial into us and never speak MessagePack. → transport `role` + `@decoder`.
2. **Egress.** Phase 18 was input-only. OE needs `PUT /api/status {"mode":"RECORD"}`, a per-session save path, and event markers pushed mid-task. → egress queue + lifecycle hooks.
3. **Session lifecycle.** Recording must start and stop with the run, and the resulting path must be recorded in MICS. → `on_run_start` / `on_run_stop` + backend safety net.

**Plus a constraint from the rig:** the OE machine may be shared across pilots (sequentially, not simultaneously). One OE box has one record node, so two pilots issuing RECORD would clobber each other. → backend device lease.

**User decisions driving the scope (2026-08-03 session):**
- **Pi owns both channels** (HTTP control + ZMQ data) — chosen to minimise overhead and keep one clock domain, one versioned lib, one toolkit story. The backend owns *only* the lease, because the Pi cannot know about other pilots.
- **v1 OE scope is firing rate + recording + save-folder naming**, with the folder path logged into MICS. This makes the ZMQ data path a v1 requirement, not a deferral.
- **The OE machine is never used by two rigs simultaneously** — the lease is a safety net, not a scheduling system. No queue/notify UX.
- **The TTL cable stays**; network markers run alongside it and the cutover happens later on measured evidence.

**Consequence for planning:** `18-01-PLAN.md` and `18-02-PLAN.md` were written against the pre-revision context. 18-01 *is* the `external_hardware.py` base-class plan, so roles/decoder/liveness/egress/lifecycle invalidate it outright. 18-02's AST extractor must additionally emit the new metadata. **Both need re-planning.** Neither has been executed, so nothing is lost but planning time.

</revision_2026_08_03>

<decisions>
## Implementation Decisions

### Mental model (locked, unchanged)
External sources are **virtual hardware modules** that flow through the existing Phase 9 / 10 / 11 / 13 / 17 pipeline like any GPIO module:
- `ExternalHardware` subclass → uploaded via existing `/api/hardware-libs` (Phase 9), AST-validated.
- A row in `hardware_modules` declares one instance (Phase 10) — `name`, `class_name`, pinned `hw_lib_version`.
- Per-pilot params live in `pilot_hardware_config.config` (Phase 17 — name-keyed, free-form JSON).
- Selected by a toolkit via existing `hardware_module_ids` (Phase 11).
- Dispatched on the existing `HARDWARE` + `PREFS_HARDWARE` channel via `toolkit_dispatch.py` (Phase 11). No new kwarg.
- Preflight-validated (Phase 13) by `class_name` like any other module.

### Transport roles (NEW — 2026-08-03; THIRD ROLE ADDED 2026-08-03 after Phase 26 planning)

> **GAP FIX — `role: "none"` (control-only, no inbound transport).** Phase 26 planning exposed that
> two roles are not enough. Both `router_bind` and `sub_connect` open a socket, so a device whose
> entire inbound story is an outbound poll — OpenEphys, whose liveness is an HTTP `GET /api/status` —
> would be forced to declare a role, pick a port, and bind a socket nothing ever connects to. That
> contradicts EXTLINK-18, which the original wording only half-covered (it addressed zero `@signal`,
> not zero transport).
>
> **Resolution: a third role value, `"none"`.**
> - `socket_plan` returns a plan with **no socket** — it must not invent a port or a default role.
> - `identity_ok` and the `@decoder` path are **inapplicable** in this role.
> - Config validation must **not** require `listen_port` or `connect_port`. `host` may still be
>   required, for **egress**.
> - `.bind()` still does everything else: registers the `<source_id>.alive` tracker, starts the
>   liveness poll (a lib overrides the default predicate — EXTLINK-07), starts the egress worker
>   (EXTLINK-15), and fires the lifecycle hooks (EXTLINK-16). **A control-only module participates
>   fully in the readiness gate.**
> - Rejected: making `role` optional/absent to mean "no transport". An explicit value is
>   self-documenting, validates cleanly at the config boundary, and lets preflight distinguish
>   "deliberately control-only" from "someone forgot to set a role".
>
> **Side benefit:** this makes EXTLINK-18 partly **agent-testable**. `socket_plan(role="none")`
> returning no socket is a pure-function assertion, where the validation map previously had only a
> rig row for EXTLINK-18.
>
> **Consequence found during plan revision — `role: "none"` REQUIRES a liveness override.**
> The default liveness predicate is "a message arrived within `stale_ms`". A module with no inbound
> socket never receives one, so it would sit permanently `alive=False` and, if `required`, hang the
> readiness gate until timeout with no useful diagnosis. Resolution: **raise at construction** when
> `role == "none"` and no liveness override is present.
> - Consistent with EXTLINK-12, which already raises `TypeError` at class-build time when a
>   `@signal` has no resolvable dtype. Same philosophy: loud, immediate, before any data flows.
> - **Rejected: silently defaulting to `alive=True` for this role.** Inventing liveness for a device
>   we never poll is exactly the "device is off but we think it's fine" failure that OpenEphys's HTTP
>   status check exists to catch. A control-only lib that genuinely cannot check liveness must say so
>   explicitly with a trivial always-true override — one visible line, not an invisible default.

Three roles, selected per instance by `role` in `pilot_hardware_config.config`:

- **`router_bind`** (original design, default) — the instance binds its own ROUTER on `listen_port`. A MICS-native SDK DEALER dials in with `identity = source_id`; frames whose identity ≠ `source_id` are dropped at the socket layer.
- **`sub_connect`** (new) — the instance **dials out** to a foreign publisher at `host:connect_port` with a SUB socket. There is no DEALER identity to check, so the identity check does not apply in this role; `source_id` is retained purely as the **tracker-name prefix** (`oe.spike_rate`), which keeps view-key naming identical across both roles.

- **`none`** (control-only) — **no inbound socket at all.** For devices we only command, whose
  liveness comes from an outbound poll rather than inbound traffic. `source_id` still serves as the
  tracker-name prefix so `<source_id>.alive` works identically. This is what OpenEphys's HTTP control
  side uses (Phase 26).

The `@decoder` hook translates a foreign frame into declared signal/event updates. **It lives in the versioned hardware lib, not in platform code** — that is the whole point: the OE wire format becomes a versioned, promotable, per-toolkit artifact that a researcher can fix without a platform release. `sub_connect` sources still declare `@signal` / `@event` normally, so view keys, typed FDA reads, and the editor's pickers work identically for both roles.

**Claude's discretion:** the exact `@decoder` signature and how it emits multiple updates from one frame.

### Liveness (AMENDED — supersedes the original heartbeat-only rule)
The original design assumed every source sends MICS `HB` frames. Foreign publishers don't. Resolution:

- **Liveness is a lib-supplied hook** with a base-class default of "any successfully decoded message within `stale_ms` ⇒ alive". A lib may override it — OE will override to poll its HTTP status endpoint, which is the only signal that distinguishes *rig is off* from *rig is quiet*.
- **`alive` means reachable/operational — NOT data-fresh.** A recording OE with no spikes for 30s is alive with stale signals. Signal freshness stays entirely with the existing per-signal stale policy (EXTLINK-06). The original design conflated these two; splitting them costs nothing because both mechanisms already exist.
  - Rationale for rejecting "silence = stale": for a low-firing unit, a `stale_ms` generous enough to cover normal quiet periods would be minutes, making `alive` useless as a failure detector.
- **Mid-run loss is logged, never automatically fatal.** Flip the `<source_id>.alive` tracker and emit the CONTINUOUS event (EXTLINK-07). The FDA author gates transitions on `not view.get_value("oe.alive")` if the experiment cares. MICS does not kill a behavioural session because an accessory went quiet.

### Egress (NEW — 2026-08-03)
Outbound calls (HTTP PUT, ZMQ send) must never execute on the FDA thread — that would inject exactly the jitter this integration exists to remove.

- **One FIFO worker per device.** Event markers are a sequence; `cue_on` must reach the recording before `reward`. Single worker preserves order; latency cost is bounded by one in-flight call.
- **Fire-and-forget, NO retry.** A retried marker arrives at the *wrong* timestamp — for alignment, a late marker is strictly worse than a missing one, because it silently corrupts co-registration instead of leaving a visible gap. On failure: log a CONTINUOUS event so post-hoc analysis knows a marker is missing, and continue. The TTL cable remains as the parallel path in v1.
- **Bounded queue; on overflow drop the NEWEST**, increment a counter, and emit a CONTINUOUS event naming what was lost. The critical property is that **the loss is recorded** — silent truncation would make the event log look complete when it isn't. Mirrors the ingress bound (256 messages) already locked.
  - Dropping oldest was rejected: the oldest entries are already sequenced and nearest delivery, so dropping them tears a hole mid-sequence.
- **N consecutive egress failures flip `alive` false** (threshold in config, sane default). Reuses the tracker the FDA author already gates on, so "device is broken" has exactly one signal regardless of which direction broke.

### Run lifecycle hooks (NEW — 2026-08-03)
- `on_run_start(run_ctx)` fires **after** `.bind()`, **asynchronously** — it returns immediately and the existing `_wait_extlink_ready` pre-state polls until the lib reports ready or the timeout fires. Blocking was rejected: the pilot would be unresponsive with no visible state and STOP would not work, which is precisely why the synthetic pre-state exists.
- **The hook is retried on an interval inside the wait window.** This turns a hard failure into a recoverable one — the researcher can start the session, notice OE isn't recording, fix it, and have the run proceed rather than losing the session.
- `run_ctx` is a **single dict**: `run_id`, `session_id`, `subject_key`, `pilot` name, task-definition id, start timestamp. Explicit named args were rejected because every added field would break every `ExternalHardware` subclass ever written, including researcher-authored libs already promoted to stable.
- `on_run_stop()` must run on **all Pi paths** — normal completion, STOP button, and task exception — **plus a backend safety net**: when a run ends without a clean stop (pilot crashed, lost power, network died), the backend releases the lease and issues the stop itself. Without the net, a Pi crash leaves OE recording indefinitely and the device permanently leased.

  **CORRECTED 2026-08-03 by research — two findings change how this is built, not whether:**
  1. **The Pi-side chokepoint already exists and needs no new wiring.** `Hardware.release()` is called unconditionally by `Task.end()` for every hardware object, which `pilot.py::run_task`'s `finally` calls on all three exit paths. `on_run_stop()` hangs off that single point rather than being wired into three.
  2. **The backend reconciliation this decision assumed already existed does NOT.** `orchestrator_station.py::_run_watchdog` is defined but its thread-start is **commented out**, and its staleness check (wall-clock since `started_at`, never refreshed) would kill every normal multi-minute session if naively re-enabled. **The safety net must be BUILT, not reused** — plan for it as real work. The usable live signal is `_redis_touch`'s `updated_at` heartbeat (already firing via `on_state`/`on_ping`), not `started_at`.
  3. **`event_dispatcher.stop()` fires BEFORE `task.end()`** in that same `finally` block, so a CONTINUOUS event emitted from inside `on_run_stop()` may never reach ES. **Do not write "the stop emits a CONTINUOUS event visible in ES" as an acceptance criterion** — verify stop behaviour by its effect (device returned to idle, lease released), not by an ES record.

### Readiness gate (AMENDED — generalizes EXTLINK-13)
The gate's success condition changes from **"all required sources alive"** to **"all required sources *ready*"**, where readiness is lib-defined and defaults to `alive`.

Rationale: for OE, what must be true before trial 1 is *"recording has started"*, not *"a packet arrived"*. A rig that is reachable but failed to enter RECORD would pass a liveness gate and then silently record nothing — the generalization catches that. For `router_bind` sources with no lifecycle hook, readiness == alive and behaviour is unchanged.

Everything else about the gate is unchanged and still locked:
- `required: bool` (default `true`) and `wait_timeout_s: int` (default `60`, range `[5, 600]`, `null` REJECTED at config save and at Pi-side init).
- Synthetic `_wait_extlink_ready` FDA pre-state, injected **only** when ≥1 required external source exists (zero overhead otherwise).
- Three exits in priority order: all required ready → user's initial state; manual skip via `EXTLINK_SKIP_WAIT` → user's initial state (warning + CONTINUOUS event); timeout at `max(wait_timeout_s)` → terminal `_extlink_timeout`, clean abort with a CONTINUOUS event listing sources that never became ready.
- Three escape paths guarantee no hang: timeout (finite, always fires), manual skip, STOP button.

### Device lease / arbitration (NEW — 2026-08-03)
Needed because one OE box has one record node and may be pointed at by several pilots' configs.

- **Lease key is derived from the normalized `host`** field in config. One physical box = one lease regardless of how many ports or modules target it — which matches the real constraint. `host:port` was rejected: the same OE machine would take separate leases for its HTTP and ZMQ modules and happily admit a second pilot.
- **Hard-blocks the run, surfaced as a NEW preflight issue kind** alongside `missing` / `incomplete_config` / `class_mismatch` / `fda_ref_unresolved` in `api/routers/toolkit_dispatch.py`. Existing machinery, existing UI. Caught before the animal is in the box.
- **The issue names the holder** — which pilot, subject, and run hold the device, and since when. In a shared lab this turns "it's broken" into "that run on pilot 2 is still going", actionable without a terminal.
- **Released by the same backend reconciliation that stops orphaned recordings** (run no longer active ⇒ lease released) — one mechanism for both problems — **plus a manual force-release** for the case where reconciliation itself is wedged, so nobody is ever hard-stuck. **Note (research 2026-08-03): that reconciliation does not exist yet** — `_run_watchdog` is dead code with a broken staleness rule. Building it is in scope for this phase; base it on `_redis_touch`'s `updated_at` heartbeat, never on `started_at`.
- Scope note: because the OE machine is never used by two rigs *simultaneously*, this is a safety net. **No queue/notify/scheduling UX.**

### Per-pilot config schema (AMENDED)
```json
{
  "pilot_id": 1,
  "name": "oe",
  "config": {
    "class_name": "OpenEphys",
    "role": "sub_connect",
    "host": "132.77.x.x",
    "connect_port": 5556,
    "source_id": "oe",
    "stale_ms": 3000,
    "required": true,
    "wait_timeout_s": 60,
    "egress_fail_threshold": 3
  }
}
```
`listen_port` applies to `role: "router_bind"`; `connect_port` + `host` apply to `role: "sub_connect"`. **`role: "none"` (control-only) requires NEITHER port** — validation must not demand one — though `host` may still be required for egress. `host` is also the lease key. `class_name` remains the Phase-17 contract field. Still **no schema change** — `api/routers/pilot_hardware_config.py:41` stores config as-is and explicitly delegates validation to the caller, so the new fields need no endpoint change. Validation of the new fields belongs in preflight.

### Transport + wire (locked, unchanged for `router_bind`)
- One ZMQ socket per `ExternalHardware` instance, bound/connected on a task-local IOLoop via `ZMQStream` (same pattern Net_Node uses at `node.py:147-151`).
- MessagePack envelope; kind discriminator `k`:
  - `SIG` — `{k, ts_src, seq, sig, v}` — signal update (latest-value semantics).
  - `EVT` — `{k, ts_src, seq, evt, p}` — event with payload.
  - `HB`  — `{k, ts_src, seq}` — heartbeat.
  - `ACK` — `{k, ts_src, cmd_id, result}` — command result.
  - Pi → SDK only: `CMD` — `{k, ts_pi, cmd_id, name, args}`.
- `sub_connect` sources use their own foreign format; the `@decoder` normalizes into the same internal signal/event updates.
- Pi stamps `ts_pi_recv` on every inbound message; **`ts_pi_recv` is canonical** for FDA reads and CONTINUOUS logging (avoids NTP skew).

### Author-facing API (locked, unchanged)
```python
from autopilot.hardware.external_hardware import ExternalHardware, signal, event, command

class DLC_Cam1(ExternalHardware):
    # No SOURCE_ID class attribute. source_id comes from pilot_hardware_config.config.

    @signal(default=0.0, stale_after_ms=200, stale_policy="hold_last")
    def left_paw_x(self) -> float: ...

    @event(payload={"object": str, "confidence": float})
    def object_detected(self): ...

    @command
    def reset_tracker(self) -> None: ...
```

### `ExternalHardware.__init__` signature (locked, unchanged)
Absorbs the kwargs the base `init_hardware` (`task.py`) passes to every hardware constructor (`event_dispatcher=`, `pi=`, `run_id=`, `name=`) plus the per-pilot config fields. Stores them; does NOT bind a socket. `.bind(ioloop, view)` does the heavy lifting. `is_trigger = False` class attribute so the base skips trigger callback assignment. Defines `.get_state()` returning `None` to satisfy the `View.get_value` contract at `task.py:204`.

**Amended:** must tolerate a **control-only module with zero declared signals** (OE's HTTP side is exactly this). Liveness and the readiness gate must not assume signals exist.

### Type contract (locked, unchanged)
Resolution order at class-build time inside `@signal`:
1. Method return annotation. 2. `type(default)`. 3. Otherwise `TypeError` at import time.

Allowed dtypes for v1: `int`, `float`, `bool`, `str`. Richer payloads go through `@event(payload={...})`.

Runtime contract on inbound SIG (`_dispatch_sig`): call `spec.dtype(raw)`; `bool` special-cased to require `isinstance(raw, bool)` (Python's `bool` is an `int` subclass, so `float(True)` would silently pass as `1.0`). On `TypeError`/`ValueError`: increment `type_mismatch_count`, log rate-limited (1/sec per signal), drop. Never raise into the IOLoop.

`@command` captures parameter names + annotations + return annotation for the state-builder UI. AST extractor mirrors into `ast_metadata.extlink` (string-typed — the extractor cannot import the lib).

### Stale policy (locked, per-signal, unchanged)
- `hold_last` — return last cached value regardless of age (default).
- `return_default` — push declared default into the tracker when age > `stale_after_ms`.
- `return_none` — push `None` into the tracker on stale.
- Universal safety hatch: the `<source_id>.alive` boolean tracker.

### Crash isolation (locked, unchanged)
- All inbound dispatch wrapped in try/except; last-ditch firewall logs + drops, **never** raises into the IOLoop.
- Per-source incoming buffer bounded (256 messages); overflow drops oldest with a counter increment.
- Non-matching DEALER identity dropped at the socket layer (`router_bind` only).
- Source crash = liveness lapses = `alive=False`. No active recovery.

### Multi-source (locked, unchanged)
N external modules on one pilot = N `pilot_hardware_config` rows = N sockets. `listen_port` values must be unique per pilot.

### Security posture (v1, locked)
ROUTER binds `0.0.0.0` unauthenticated; identity check rejects wrong DEALER ids. SUB dials out to a trusted host. Acceptable on private LAN/VLAN. Documented. CurveZMQ auth is a later hardening phase.

### Pi operational rules (locked, MUST follow)
Per [[feedback_pi_no_git]] and [[feedback_pi_start_stop]]:
- **NEVER** run git on the Pi. **NEVER** start/stop the Pi pilot process. **NEVER** run any Python file on the Pi.
- All file edits go to `~/pi-mirror/`. `<verify>` blocks for Pi files return commands for the **user** to run.
- Backend edits (`api/`) are agent-driven — docker compose, not the Pi.
- Reading from the Pi via SSH (grep, cat) is fine.

### Claude's Discretion
- Exact `@decoder` signature and multi-update emission shape.
- Whether `role` is a config string or inferred from which port field is present (config string recommended for explicitness).
- Egress queue depth and default `egress_fail_threshold`.
- Liveness-hook polling interval and how it composes with the `stale_ms / 2` PeriodicCallback.
- Internal representation of the lease (table vs column on an existing table).
- Whether Phase 18 keeps its "MICS-Link" name now that it is the general external-device layer.

</decisions>

<code_context>
## Existing Code Insights

### Reusable Assets
- `api/routers/toolkit_dispatch.py:246-336` — preflight already emits typed issues (`missing`, `incomplete_config`, `class_mismatch`, `fda_ref_unresolved`) with `module_id` so the React client can PUT a fix directly. **The device-lease block and new config validation are new issue kinds in this existing system — no new machinery, no new UI surface.**
- `api/routers/pilot_hardware_config.py:41` — docstring states *"Config stored as-is (caller validates)"*. New config keys (`role`, `host`, `connect_port`, `egress_fail_threshold`) need **no endpoint or schema change**.
- `api/detector_keys.py` — `derive_view_keys()` / `resolve_view_key_issues()` (Phase 25). This is the precedent for deriving view keys from `pilot_hardware_config.config` rather than from static class declarations — the mechanism Phase E2 will reuse for `oe.<unit>.rate` keys.
- `~/pi-mirror/autopilot/autopilot/networking/node.py:136-157` — ZMQStream + Tornado IOLoop precedent; the new sockets mirror `node.py:147-151`.
- `~/pi-mirror/autopilot/autopilot/hardware/timer.py:8-38` — software-only hardware with no physical pin; carries the `is_trigger = False` pattern.

### Established Patterns
- **Hardware-lib substrate as the extensibility mechanism** — Phase 23 established that a non-hardware concept (compute ops) rides `hardware_libs` + a `kind` discriminator to inherit versioning, AST metadata, promotion trail, and `LOAD_HARDWARE_LIBS` transport. `ExternalHardware` follows the same instinct; the `@decoder` living in the lib is the direct analogue.
- **`@log_action` auto-logging** — only dispatches for `Mics_Tracker` / `Hardware` instances, which is why `ExternalHardware` must subclass `Hardware` for its events to reach ES.
- **Preflight-as-gate** — Phase 13 established that cross-checks block at preflight rather than failing at run time on the Pi. The lease follows this.

### Integration Points
- `api/routers/hardware_libs.py` AST extractor — EXTENDED to recognise `@signal` / `@event` / `@command` (and now `@decoder`), emitting `ast_metadata.extlink`. No new endpoint.
- `api/routers/toolkit_dispatch.py` — UNCHANGED for dispatch; EXTENDED for the lease + new-field preflight issues.
- `~/pi-mirror/autopilot/autopilot/tasks/task.py:162-217` base `init_hardware` — UNCHANGED. `ExternalHardware` absorbs the standard kwargs and exposes `is_trigger = False` + `get_state()`.
- `~/pi-mirror/autopilot/autopilot/tasks/mics_task.py` — override `init_hardware()` for the `.bind(ioloop, view)` post-pass; also the host for lifecycle-hook firing and the `_wait_extlink_ready` pre-state.
- `~/pi-mirror/autopilot/autopilot/core/View.py:5-44` + `utils/Tracker.py:5-48` — Tracker registration and `get_value`.
- `~/pi-mirror/autopilot/autopilot/networking/Event_Dispatcher.py:34-46` — CONTINUOUS payload format for `@event`, liveness flips, and egress-failure logging.

</code_context>

<specifics>
## Specific Ideas

- Source document for the OE integration: `docs/open_ephys_integration.pdf` (and its `.md` twin). Confirms two channels — HTTP REST control on **37497**, ZMQ data on **5556 (default, configurable — confirm against the rig's plugin settings)**.
- **The plugin transfers spikes, not firing rate.** Rate is derived by windowed counting, which in this design runs on the Pi. Two consequences that belong to Phase E2, not here: the OE signal chain needs a spike detector/sorter upstream of the ZMQ plugin or there are no spikes on the wire at all; and sorted unit IDs only exist if sorting is configured, so units of interest must be declared in `pilot_hardware_config.config`.
- "Treat Open Ephys as just another piece of hardware in a MICS task" — the PDF's own framing matches the mental model this phase already locked, which is why no new dispatch path is warranted.
- Codec: `msgpack`. **CORRECTED 2026-08-03 by research (verified via SSH into the Pi's `~/.venv/autopilot`): `msgpack` is NOT installed and nothing in the codebase uses it — the existing wire format is JSON.** The earlier claim that it was "already transitive through the pyzmq/tornado stack" was wrong. This is a genuine new dependency requiring a **Wave-0 install with a version pin compatible with the Pi's actual Python 3.7.3** (pyzmq 23.0.0b1, tornado 6.1). Per the Pi rules the agent cannot install it — a `<verify>` block must have the **user** resolve the pin via `pip install` on the rig. Decoder must catch `msgpack.UnpackException`, return None, drop silently with a counter increment.
- Heartbeat/liveness tick: Tornado `PeriodicCallback` at `stale_ms / 2` (1500 ms when `stale_ms=3000`).
- Tracker naming: `f"{source_id}.{signal_method_name}"` plus `f"{source_id}.alive"` — identical in both roles.
- Smoke test at `~/pi-mirror/scripts/dev/extlink_smoke.py`, run from the dev machine (NOT the Pi). Takes `--pi-host`, `--listen-port`, `--source-id`. Subcommands `probe` and `sustain`.

</specifics>

<deferred>
## Deferred Ideas

Explicitly out-of-scope for Phase 18:
- **Phase E1 — OpenEphys Device (control):** REST client (RECORD/IDLE), per-run save-path template, `/api/message` markers, recording path persisted into MICS so the system has its own record of it, preflight reachability. Independently shippable; stops anyone touching the OE GUI.
- **Phase E2 — Firing rate over ZMQ:** spike/event decoder, declared units + windowed rate estimator, `(ts_pi_recv, oe_sample)` sync-pair logging to ES, keys surfaced in the FDA editor via Phase 25's `detector_keys` mechanism.
- **Phase E3 — TTL-vs-network validation:** both paths in one recording, quantify offset and jitter, report. **No cutover** — this is the evidence gate for a later decision to remove the cable.
- DeepLabCut reference hw_lib + template + rig demo — reuses the refined base class and `sub_connect` for free. Paused by user request.
- `mics-link` Python SDK package; stub generation + bootstrap-zip + "Download SDK" GUI.
- React health dashboard for external sources; orchestrator `EXTLINK_STATUS` forwarding + WS broadcast.
- UI port-conflict warning for two external modules on one pilot.
- CurveZMQ auth / TLS / token-based access control.
- Bulk-stream tier (high-rate continuous piped through CONTINUOUS without going through the FDA) — not in MICS-Link v1 at all. Note this is also why raw OE continuous @30 kHz is not a target for E2.
- Device *scheduling* (queue, notify-when-free) — the lease hard-blocks only; the OE box is never used by two rigs simultaneously.

</deferred>

---

*Phase: 18-extlink-pi-transport*
*Context rewritten: 2026-05-31 — aligned with Phase 09–13 + 17 flow; dropped prefs.json EXTLINK and singleton ExternalLink*
*Context revised: 2026-08-03 — transport roles + decoder, liveness split from staleness, egress queue, run lifecycle hooks, device lease; readiness gate generalized to "ready". Existing 18-01/18-02 plans superseded.*
