# Phase 18: MICS-Link — Pi Transport + ExternalHardware — Context

**Gathered:** 2026-05-31 (rewritten 2026-05-31 after alignment with Phases 09–13 flow)
**Status:** Ready for planning
**Source:** Master plan `/home/ido/.claude/plans/as-you-are-already-effervescent-hearth.md`, narrowed and re-aligned during this session.

<domain>
## Phase Boundary

Pi gains a structured, crash-safe input channel that lets external software running on other computers (DeepLabCut, OpenEphys, photometry rigs, …) push data into the existing View / FDA framework. **The flow uses the existing Phase 09–13 + Phase 17 plumbing end-to-end.** No new DB tables. No new top-level dispatch kwarg. No new prefs.json block. The `ExternalHardware` subclass IS a hardware library; an instance of it IS a hardware module; its per-pilot network params live in the existing `pilot_hardware_config.config` JSON.

**In scope (Phase 18):**
- New `ExternalHardware` Python base class with `@signal` / `@event` / `@command` decorators (Pi-side, in `~/pi-mirror/autopilot/autopilot/hardware/`).
- Each instance owns its own ZMQ ROUTER socket bound to the `listen_port` from per-pilot config.
- View Tracker auto-registration per signal + `<source_id>.alive` boolean tracker.
- Per-signal stale policy (`hold_last` / `return_default` / `return_none`).
- Heartbeat-driven liveness with `stale_ms` from per-pilot config.
- Ingress validation that drops unknown messages without raising into the IOLoop.
- Small AST extractor extension in `api/routers/hardware_libs.py` so the three decorators land in `ast_metadata` (otherwise Phase 9 plumbing is untouched).
- `mics_task.init_hardware()` post-pass that calls `.bind(ioloop, view)` on every `ExternalHardware` instance.
- Standalone smoke-test DEALER script (`~/pi-mirror/scripts/dev/extlink_smoke.py`).

**Out of scope (deferred to later MICS-Link phases):**
- The `mics-link` Python SDK package (Phase 19).
- Stub generation + bootstrap-zip endpoints + "Download SDK" GUI (Phase 20).
- Per-pilot external-sources health dashboard + orchestrator WS forwarding (Phase 21).
- DeepLabCut reference integration (Phase 22).
- OpenEphys / photometry recipes (Phase 23).
- **No `EXTLINK` block in `pilot/prefs.json`** — explicitly rejected. Network config lives only in `pilot_hardware_config.config`.
- **No singleton `ExternalLink` class** on the Pi — explicitly rejected. Each `ExternalHardware` instance owns its own socket.

</domain>

<decisions>
## Implementation Decisions

### Mental model (locked)
External sources are **virtual hardware modules** that flow through the existing Phase 9 / 10 / 11 / 13 / 17 pipeline like any GPIO module:
- `ExternalHardware` subclass → uploaded via existing `/api/hardware-libs` (Phase 9), AST-validated.
- A row in `hardware_modules` declares one instance (Phase 10) — `name` (e.g. `dlc_cam1`), `class_name` (e.g. `DLC_Cam1`), pinned `hw_lib_version`.
- Per-pilot params live in `pilot_hardware_config.config` (Phase 17 — name-keyed, free-form JSON).
- Selected by a toolkit via existing `hardware_module_ids` (Phase 11).
- Dispatched on the existing `HARDWARE` + `PREFS_HARDWARE` channel via `toolkit_dispatch.py` (Phase 11). No new kwarg.
- Preflight-validated (Phase 13) by `class_name` like any other module.

### Topology (locked)
**External connects to Pi, ONE port per instance.** Each `ExternalHardware` instance binds its own ROUTER on its own `listen_port`. The external SDK DEALER dials in with `identity = source_id`. The ROUTER rejects any DEALER frame whose identity ≠ the configured `source_id`.

Two external modules on the same pilot = two ROUTER sockets on two ports. The first one might be `listen_port=5571`, the second `listen_port=5572`, etc. The user picks the ports when filling in `pilot_hardware_config.config`.

### Per-pilot config schema (locked)
A `pilot_hardware_config` row for an external module:
```json
{
  "pilot_id": 1,
  "name": "dlc_cam1",
  "config": {
    "class_name": "DLC_Cam1",
    "listen_port": 5571,
    "source_id": "dlc_cam1",
    "stale_ms": 3000,

    "required": true,
    "wait_timeout_s": 60
  }
}
```
Six fields total. `class_name` is the Phase-17 contract field (mirrors physical modules). `listen_port`, `source_id`, `stale_ms` are the network communication essentials. `required` + `wait_timeout_s` drive the readiness gate (see decision below). No port lives in `prefs.json`; the Pi knows nothing about external modules until the toolkit dispatches.

`wait_timeout_s` MUST be an int in `[5, 600]`. `null`/`None` is rejected at the Phase-17 save endpoint and at the Pi-side `ExternalHardware.__init__`. Default `60` is applied when the key is absent.

### Transport + wire (locked)
- One ZMQ ROUTER per `ExternalHardware` instance, bound on a task-local IOLoop via `ZMQStream` (same pattern Net_Node uses for its own ROUTER at `node.py:147-151`).
- MessagePack envelope; kind discriminator `k`:
  - `SIG` — `{k, ts_src, seq, sig, v}` — signal update (latest-value semantics).
  - `EVT` — `{k, ts_src, seq, evt, p}` — event with payload.
  - `HB`  — `{k, ts_src, seq}` — heartbeat.
  - `ACK` — `{k, ts_src, cmd_id, result}` — command result.
  - Pi → SDK only: `CMD` — `{k, ts_pi, cmd_id, name, args}`.
- Pi stamps `ts_pi_recv` on every inbound message; **`ts_pi_recv` is canonical** for FDA reads and CONTINUOUS logging (avoids NTP skew).

### Author-facing API (locked)

```python
from autopilot.hardware.external_hardware import ExternalHardware, signal, event, command

class DLC_Cam1(ExternalHardware):
    # No SOURCE_ID class attribute. source_id comes from pilot_hardware_config.config.

    @signal(default=0.0, stale_after_ms=200, stale_policy="hold_last")
    def left_paw_x(self) -> float: ...

    @signal(default=0.0, stale_after_ms=200, stale_policy="return_default")
    def left_paw_y(self) -> float: ...

    @event(payload={"object": str, "confidence": float})
    def object_detected(self): ...

    @command
    def reset_tracker(self) -> None: ...
```

Free outcomes from this declaration alone:
- The AST extractor records the three sets `{signals, events, commands}` in `ast_metadata`.
- The hw_libs upload path stores the lib like any other.
- A `hardware_modules` row gets created via the existing UI/API for `DLC_Cam1`.
- A `pilot_hardware_config` row holds the per-pilot network params.
- On task dispatch, the resolved class lands in `self.HARDWARE` like any module.
- After `super().init_hardware()`, the instance is in `self.hardware`; `mics_task.init_hardware` post-pass calls `.bind(ioloop, view)` which binds the ROUTER + registers trackers + starts heartbeat scan.
- FDA reads work via `view.get_value("dlc_cam1.left_paw_x") > 0.5`.
- `EVT object_detected` rides `Event_Dispatcher` CONTINUOUS pipe to ES.

### `ExternalHardware.__init__` signature (locked)
Must absorb the kwargs that the base `init_hardware` (in `task.py`) passes to every hardware constructor (`event_dispatcher=`, `pi=`, `run_id=`, `name=`) plus the per-pilot config fields (`listen_port`, `source_id`, `stale_ms`). The constructor stores them; it does NOT bind a socket yet. `.bind(ioloop, view)` later does the heavy lifting. Has `is_trigger = False` class attribute so the base `init_hardware` skips trigger callback assignment. Defines a `.get_state()` returning `None` to satisfy the `View.get_value` contract used at `task.py:204`.

### Type contract (locked)
A signal/command without a declared value type is a foot-gun: the FDA author writes `view.get_value("dlc_cam1.left_paw_x") > 0.5`, and the state-builder UI must render typed inputs for commands like `reset_tracker(level: int) -> bool`. Both need to know the type **before** the rig sends its first byte.

Resolution order at class-build time (inside the `@signal` decorator):
1. Method return annotation (e.g. `def left_paw_x(self) -> float: ...`).
2. `type(default)` (e.g. `default=0.0` → `float`).
3. If neither resolves to one of `{int, float, bool, str}`, the decorator raises `TypeError` at import time. Loud, immediate, before any data flows.

Allowed dtypes are restricted to MessagePack primitives for v1: `int`, `float`, `bool`, `str`. Richer payloads go through `@event(payload={...})`.

Runtime contract on inbound SIG (`_dispatch_sig`):
- Call `spec.dtype(raw_value)`.
- `bool` is special-cased — require `isinstance(raw, bool)` (Python's `bool` is an `int` subclass, so `float(True)` would silently pass as `1.0` — we reject that).
- On `TypeError` / `ValueError`: increment `type_mismatch_count`, log rate-limited (1/sec per signal), drop. Never raise into the Tornado IOLoop.

`@command` captures parameter names + annotations + return annotation. The state-builder UI consumes this to render a typed call form before issuing `send_command`. AST extractor mirrors all of the above into `ast_metadata.extlink` (string-typed, since the extractor cannot import the lib): `signals[i].dtype` and `commands[i] = {name, args: [{name, dtype}], returns}`.

### Readiness gate (locked)
Reverse start order (external rig boots before Pi) is already solved by ZMQ DEALER local queueing — no design needed. Forward start order (Pi up first, external rig coming online later) needs a gate; today's plan would let the FDA enter its initial state immediately and read defaults until HBs arrive.

Resolution:
- Two new fields in `pilot_hardware_config.config` (Phase 17 free-form, no schema change):
  - `required: bool` — default `true`. Strict default by design: cost of a forgotten opt-in is "experiment ran on defaults"; cost of an unwanted gate is "flip a checkbox."
  - `wait_timeout_s: int` — default `60`. Range `[5, 600]`. `null` / `None` is REJECTED at both the Phase-17 save endpoint and the Pi-side `ExternalHardware.__init__` — tasks can never silently wait forever.
- `mics_task` injects a synthetic `_wait_extlink_ready` FDA pre-state in front of the user-declared initial state **only when at least one required external source exists**. Tasks with zero required externals pay zero overhead and have no behavior change.
- Three exits from the pre-state, in priority order:
  1. **All required alive** → user's initial state (normal path).
  2. **Manual skip** via orchestrator-relayed `EXTLINK_SKIP_WAIT` ZMQ message → user's initial state (warning logged + CONTINUOUS event recording the skip).
  3. **Timeout** at `max(wait_timeout_s)` across required sources → terminal `_extlink_timeout` state. Session aborts cleanly with a `CONTINUOUS ExtlinkTimeout` event carrying the list of sources that never reached alive.
- Three escape paths combined guarantee no task can hang:
  - Timeout (finite, default 60s, max 600s — always fires).
  - Manual skip (operator override via API → ZMQ → Pi).
  - STOP button (existing path, always available — aborts the session including the wait state).

Rationale for the synthetic state (vs a wait-loop before FSM start): the pre-state rides the existing FDA + status WebSocket machinery. The pilot's reported state is `_wait_extlink_ready` instead of mysteriously frozen; dashboards (Phase 21) get the state name for free; STOP is just another transition in the existing FDA, not a separate code path.

Skip-wait transport:
- Orchestrator API endpoint: `POST /api/run/{run_id}/extlink-skip-wait` → orchestrator forwards `EXTLINK_SKIP_WAIT` ZMQ message to the target pilot via the existing Net_Node channel.
- Pi-side handler in `mics_task` sets `self._extlink_skip_wait = True`. The pre-state's transition guard re-evaluates on the next FDA tick.
- The skip command is idempotent — sending it after the gate has already released is a no-op.

### Stale policy (locked, per-signal)
- `hold_last` — return last cached value regardless of age (default).
- `return_default` — push declared default into the tracker when age > `stale_after_ms` (so `view.get_value(...)` returns it without per-call age math).
- `return_none` — push `None` into the tracker on stale.
- Universal safety hatch: `<source_id>.alive` boolean tracker — FDA author can gate any transition on `not view.get_value("dlc_cam1.alive")` to force a safe state.

### Liveness (locked)
- SDK sends `HB` at its own cadence (recommendation: 1 Hz; not enforced).
- Pi marks source alive while `now - last_seen_ms < stale_ms` (per-pilot config).
- A Tornado `PeriodicCallback` runs at `stale_ms / 2` to detect transitions.
- alive↔stale transition flips the `<source_id>.alive` Boolean_Tracker and dispatches a CONTINUOUS event.

### Crash isolation (locked)
- All inbound dispatch wrapped in try/except. Last-ditch firewall logs + drops; **never** raises into the IOLoop.
- Per-source incoming buffer bounded (256 messages); overflow drops oldest with a counter increment.
- A non-matching DEALER identity is dropped at the socket layer (one ROUTER per source means the identity check is a single string compare per inbound frame).
- Source crash = no more HBs = `alive=False` after `stale_ms`. No active recovery.

### Multi-source (locked)
- N external modules on one pilot = N `pilot_hardware_config` rows = N sockets = N ports.
- Each instance independently bound; ports must be unique per pilot. UI / preflight should warn on duplicates (deferred to Phase 19+).

### Hooks into existing Pi systems (locked)
- **View / Tracker** (`autopilot/core/View.py`, `autopilot/utils/Tracker.py`) — each `@signal` registers a Tracker via `add_Tracker()`; each instance registers a `Boolean_Tracker` for `.alive`.
- **Event_Dispatcher** (`autopilot/networking/Event_Dispatcher.py`) — `@event` messages dispatch through the existing CONTINUOUS pipeline to ES.
- **mics_task.init_hardware** (`autopilot/tasks/mics_task.py` — newly overridden) — post-pass `.bind(ioloop, view)` on each `ExternalHardware` instance after `super().init_hardware()`.
- **base task.py init_hardware** (`autopilot/tasks/task.py:162-217`) — UNCHANGED. Instantiates `ExternalHardware` like any other module because the subclass absorbs the standard kwargs and exposes `is_trigger = False` + `get_state()`.
- **toolkit_dispatch.py** (`api/routers/toolkit_dispatch.py:28-112`) — UNCHANGED. Dispatched `HARDWARE` + `PREFS_HARDWARE` shape carries external modules transparently.
- **api/routers/hardware_libs.py** AST extractor — EXTENDED to recognise `@signal` / `@event` / `@command` and emit the corresponding metadata. No new endpoint.

### Security posture (v1, locked)
- ROUTER binds `0.0.0.0` unauthenticated. Identity check rejects wrong DEALER ids. Acceptable on private LAN/VLAN. Documented.
- CurveZMQ auth is a Phase 19+ follow-up.

### Pi operational rules (locked, MUST follow)
Per [[feedback_pi_no_git]] and [[feedback_pi_start_stop]]:
- **NEVER** run git on the Pi.
- **NEVER** start/stop the Pi pilot process.
- **NEVER** run any Python file on the Pi.
- All file edits go to `~/pi-mirror/`. `<verify>` blocks for Pi files return commands for the user to run themselves.
- Backend edits (`api/`) are agent-driven — that's docker compose, not Pi.
- Reading from the Pi via SSH (grep, cat for verification) is fine.

</decisions>

<specifics>
## Specific Ideas

### Codec
Use `msgpack` (already a transitive dep through the existing pyzmq/tornado stack). Decoder must catch `msgpack.UnpackException` and return None; the receiver must drop None decodes silently with a counter increment.

### Heartbeat tick
Use Tornado `PeriodicCallback` at `stale_ms / 2` (default 1500 ms when `stale_ms=3000`). Checks `now - last_seen` per instance, flips `.alive` Tracker on transitions, emits CONTINUOUS event on the flip.

### Validation
- At class build time (in the `ExternalHardware` metaclass): collect declared signal/event/command names into `_declared_signals`, `_declared_events`, `_declared_commands`.
- At message receive: if `sig` (or `evt`, `cmd`) not in the declared set, drop + log with rate-limit (1/sec per instance).
- DEALER identity check: the ROUTER frame's first part is the identity. If it ≠ the configured `source_id`, drop without dispatch.

### Smoke test
- Lives at `~/pi-mirror/scripts/dev/extlink_smoke.py`.
- Uses pyzmq + msgpack on the dev machine (NOT on the Pi).
- Takes `--pi-host`, `--listen-port`, `--source-id` (the latter two come from the row the user created in `pilot_hardware_config` for the test module).
- DEALER `identity = source_id` connects to `tcp://<PI_IP>:<listen_port>`.
- Subcommands: `probe` (single SIG+EVT+HB+malformed frame) and `sustain` (10 Hz SIG + 1 Hz HB for N seconds).

### Tracker naming
`f"{source_id}.{signal_method_name}"` — e.g. `dlc_cam1.left_paw_x`. Plus `f"{source_id}.alive"` boolean.

### Files to read (planner context)
Backend side:
- `mics-backend/api/routers/hardware_libs.py:1-100` — AST extractor (extended in this phase to recognise `@signal` / `@event` / `@command`).
- `mics-backend/api/routers/hardware_modules.py` — module registry (NO change in this phase; classes auto-fit).
- `mics-backend/api/routers/pilot_hardware_config.py` — Phase-17 free-form CRUD (NO change; config carries the four fields).
- `mics-backend/api/routers/toolkit_dispatch.py:28-112` — dispatch spec (NO change; existing shape carries external modules).

Pi side:
- `~/pi-mirror/autopilot/autopilot/core/View.py:5-44` — Tracker registration + `get_value`.
- `~/pi-mirror/autopilot/autopilot/utils/Tracker.py:5-48` — Tracker / Boolean_Tracker / `@log_action`.
- `~/pi-mirror/autopilot/autopilot/networking/Event_Dispatcher.py:34-46` — CONTINUOUS payload format.
- `~/pi-mirror/autopilot/autopilot/networking/node.py:136-157` — ZMQStream + Tornado IOLoop precedent (the new ROUTER mirrors `node.py:147-151`).
- `~/pi-mirror/autopilot/autopilot/tasks/task.py:162-217` — base `init_hardware` (DO NOT modify; `ExternalHardware` constructor accommodates this path).
- `~/pi-mirror/autopilot/autopilot/tasks/mics_task.py:83-142, 146-192` — `__init__` + `_resolve_hardware_classes` + `_merge_prefs_hardware` (override `init_hardware` here to add the bind post-pass).
- `~/pi-mirror/autopilot/autopilot/hardware/timer.py:8-38` — precedent for software-only hardware with no physical pin (carries the `is_trigger = False` pattern).

</specifics>

<deferred>
## Deferred Ideas

Explicitly out-of-scope for Phase 18 (handled in later MICS-Link phases):
- Python SDK package `mics-link` — Phase 19.
- Stub-generation endpoint, bootstrap-zip endpoint, "Download SDK starter" UI button — Phase 20.
- React health dashboard `/react/pilots/:pilot/external-sources`, orchestrator `EXTLINK_STATUS` forwarding, WS broadcast — Phase 21.
- DeepLabCut reference hw_lib + template + end-to-end rig test — Phase 22.
- OpenEphys / photometry recipes — Phase 23.
- UI port-conflict warning for two external modules on the same pilot — Phase 19+.
- CurveZMQ auth / TLS / token-based access control — future hardening phase.
- Bulk-stream tier (high-rate continuous data piped through CONTINUOUS without going through FDA) — not in MICS-Link v1 at all.

</deferred>

---

*Phase: 18-extlink-pi-transport*
*Context rewritten: 2026-05-31 — aligned with Phase 09–13 + 17 flow; dropped prefs.json EXTLINK and singleton ExternalLink*
