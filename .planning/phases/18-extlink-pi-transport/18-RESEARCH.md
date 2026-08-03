# Phase 18: MICS-Link — Pi Transport + ExternalHardware — Research

**Researched:** 2026-08-03
**Domain:** ZMQ/Tornado async networking on a resource-constrained Pi (Python 3.7.3), integrated into an existing hardware-lib/toolkit-dispatch/preflight substrate
**Confidence:** HIGH for architecture/integration points (verified by direct code + live-SSH reads this session); MEDIUM for exact library version pins (verified against the actual rig, but msgpack's compatible version range needed a general web check); LOW/flagged explicitly where noted

## Summary

Phase 18 has almost no "pick a library" research surface — the wire format, decorators, roles,
egress, and lifecycle hooks are already fully decided in `18-CONTEXT.md`. What this phase actually
needs from research is **integration truth**: does the existing Pi threading/IOLoop model actually
support what the context assumes, and are the "existing mechanisms" the context points to (a
reconciliation loop, a transitive msgpack dependency, a single teardown chokepoint) real or
aspirational? This session verified each of those by reading the actual code and SSHing into the
rig read-only, and found **three corrections that materially change how the plan should be
written**, plus one architecture question (IOLoop thread-safety) that has a concrete, verified
answer.

**Correction 1 — msgpack is NOT installed on the Pi and is NOT a transitive dependency of anything
already there.** `18-CONTEXT.md`'s "Codec: msgpack (already transitive through the pyzmq/tornado
stack)" is wrong. Live SSH check: `ModuleNotFoundError: No module named 'msgpack'` in the exact venv
(`~/.venv/autopilot`) the pilot process runs from. Every existing wire format in this codebase
(`autopilot/networking/message.py`) is **JSON**, not msgpack. This is a genuine new dependency the
plan must add (Wave 0 gap), pinned for **Python 3.7.3** (the Pi's actual interpreter — current
msgpack requires 3.9+; an older pin is needed).

**Correction 2 — the "backend reconciliation that stops orphaned recordings" the context assumes
already exists (for the device-lease safety net) is dead code with a design flaw.**
`orchestrator_station.py::_run_watchdog` exists but its thread-start call is commented out
(`orchestrator_station.py:57`), and as written it would false-positive on every normal multi-minute
behavioral session (it flags ANY run whose in-memory `started_at` is >30s old and whose `status` is
still `"running"` — a status that is set once at start and never updated). This cannot simply be
re-enabled; Phase 18's backend safety net needs either a rewritten reconciliation loop or a
narrower one scoped specifically to the device lease.

**Correction 3 — the single teardown chokepoint the context needs for `on_run_stop()` already
exists and is airtight, but it fires AFTER the event dispatcher's sender thread has already been
told to stop.** `pilot.py::run_task`'s `finally` block calls `self.task.event_dispatcher.stop()`
**before** `self.task.end()` (which calls `.release()` on every hardware object, unconditionally,
on all three exit paths: normal completion, STOP, and exception). This means `on_run_stop()` is
correctly guaranteed to fire exactly once on every path — a real, verified answer to one of the
posed research questions — but any CONTINUOUS event it tries to log during teardown will be
silently dropped, because the sender thread has already exited. This is an open design point for
the plan, not a blocker.

**Primary recommendation:** Treat `ExternalHardware.bind()`'s socket setup as the one place needing
real engineering care — it must schedule ZMQ/Tornado registration via `IOLoop.add_callback()`
(verified thread-safe by Tornado's own docs) because `init_hardware()` runs in the Pilot's
`run_task` thread, not the thread actually running the IOLoop (`self.node`'s `loop_thread`).
Everything else — roles, decorator metadata, egress, lifecycle firing points — has a concrete,
already-existing Pi-side or backend-side integration point identified below.

## Phase Requirements

| ID | Description | Research Support |
|----|-------------|-----------------|
| EXTLINK-01 | Each instance binds its own ROUTER on `listen_port`, on the task's IOLoop, no new thread | Verified: `self.node.loop` (owned by the Pilot's own `Net_Node`, already running via `loop_thread`) is the correct handle; registration must go through `IOLoop.add_callback()` — see Architecture Patterns |
| EXTLINK-02 | `router_bind` DEALER identity check | `Net_Node`'s own ROUTER precedent (`node.py:147-151`) shows the pattern; identity-mismatch drop is new logic, not a library feature |
| EXTLINK-03 | MessagePack envelope, kind discriminator | msgpack is a **new dependency** — not installed on the Pi, not used anywhere in the codebase (JSON is the existing wire format). See Correction 1 |
| EXTLINK-04 | `@signal`/`@event`/`@command` decorators | New code; no existing decorator-metadata precedent in `hardware/__init__.py` to build on beyond the plain-method AST extractor |
| EXTLINK-05 | Auto-registered View Tracker per signal | `View.add_Tracker()` / `Tracker` verified read in full — trivial, already-generic mechanism |
| EXTLINK-06 | Per-signal stale policy | New logic; no existing precedent (per-signal staleness doesn't exist elsewhere) |
| EXTLINK-07 (amended) | Liveness split from staleness, lib-supplied hook | New logic; `Event_Dispatcher.dispatch_event()`'s pigpio-tick requirement (see Pitfalls) applies to every CONTINUOUS event this hook emits |
| EXTLINK-08 | Ingress validation never raises into IOLoop | Existing precedent: `_report_trigger_error` (Phase 25) is the model for "log, dispatch an error event, never let it escape" |
| EXTLINK-09 | AST extractor recognises new decorators | Verified: `extract_ast_metadata()` (`hardware_libs.py:52`) currently ignores `decorator_list` entirely — needs new code, and decorator args like `payload={"object": str}` are **not** `ast.literal_eval`-safe (bare type names are `ast.Name`, not literals) — see Pitfalls |
| EXTLINK-10 | Config lives in `pilot_hardware_config.config`, no schema change | Verified: `pilot_hardware_config.py:41` truly stores config as-is; zero endpoint change needed |
| EXTLINK-11 | Standalone DEALER smoke test | `Net_Node`'s DEALER pattern (`node.py:129-136`) is the literal template |
| EXTLINK-12 | Type contract, dtype coercion | New logic; bool-special-case rationale independently verified (Python `bool` is an `int` subclass) |
| EXTLINK-13 (amended) | Readiness gate keyed on "ready", three exits | `FiniteDeterministicAutomaton` verified in full — synthetic pre-state is a normal `add_method`/`add_transition`/`set_initial_method` composition, no special-casing needed in the FDA engine itself |
| EXTLINK-14 | Transport roles + `@decoder` | New logic; `router_bind` reuses `Net_Node`'s ROUTER precedent, `sub_connect` has no existing precedent anywhere in this codebase (verified: no SUB socket usage found in `autopilot/`) |
| EXTLINK-15 | Egress path, FIFO, no retry, bounded, drop-newest | Must NOT be a Tornado periodic callback if it does blocking HTTP/ZMQ send — see Architecture Patterns (the shared IOLoop also serves the pilot's own orchestrator DEALER; blocking it freezes ingress for every module) |
| EXTLINK-16 | Lifecycle hooks, backend safety net | **`on_run_stop()`'s single chokepoint verified**: `Hardware.release()`, called unconditionally by `Task.end()` for every hardware object, called unconditionally by `pilot.py::run_task`'s `finally` on all three exit paths — see Correction 3 for the CONTINUOUS-logging caveat. Backend safety net: see Correction 2 |
| EXTLINK-17 | Device lease, backend arbitration | No existing lease/arbitration mechanism found anywhere in `api/`; `toolkit_dispatch.py`'s preflight issue list (`missing`/`incomplete_config`/`class_mismatch`/`fda_ref_unresolved`) verified as the exact extension point |
| EXTLINK-18 | Zero-signal control-only modules legal | Verified: nothing in `View`, `Tracker`, or `check_for_detectors` assumes a hardware module has signals; the pattern is naturally supported |

## Architecture Patterns

### The already-running IOLoop, and why `.bind()` cannot just call `IOLoop.current()`

Every task-level `ExternalHardware` instance is created inside `mics_task.__init__()` →
`init_hardware()`, which runs in the **thread `Pilot.run_task()` spawns**
(`pilot.py:1160`: `threading.Thread(target=self.run_task, ...)`). Tornado's `IOLoop.current()`
resolves to a **thread-local** IOLoop — calling it from the `run_task` thread would silently
construct a brand-new IOLoop that nothing ever calls `.start()` on, so any `ZMQStream.on_recv`
registered against it would simply never fire. No exception, no log — permanent silent ingress
failure.

The IOLoop that is actually running lives on the Pilot's own `Net_Node` (`self.node`), constructed
once at Pilot startup and driven by its own dedicated `loop_thread`
(`node.py:141-152`: `self.loop = IOLoop.current()` at construction time, then
`threading.Thread(target=self.threaded_loop).start()` which calls `self.loop.start()`). This same
`Net_Node` object is handed into every `Task` (including `mics_task`) as `kwargs['node']`
(`task.py:119`: `self.node = kwargs['node']`) — confirmed by tracing `l_start()`
(`pilot.py:600`: `value['node'] = self.node`) forward into `run_task` (`pilot.py:1160`). So
`self.node.loop` **is** the correct, already-running IOLoop object to hand to every
`ExternalHardware.bind(ioloop, view)` call — it is the same loop the orchestrator DEALER already
uses, matching EXTLINK-01's "runs on the task's Tornado IOLoop alongside the orchestrator DEALER
(no new thread)" almost literally.

**The remaining risk:** even with the right `ioloop` object, creating a `zmq.Context().socket()`,
wrapping it in `ZMQStream(sock, ioloop)`, and calling `.on_recv()`/`.bind()`/`.connect()` are all
calls that touch the IOLoop's underlying poller registration. Tornado's own documentation states
`IOLoop.add_callback()` is the **only** method safe to call from a different thread than the one
running the loop; pyzmq's own eventloop docs describe the same pattern (schedule via
`add_callback`, then do all `ZMQStream` setup on the loop's own thread). Verified via direct search
of Tornado's documentation this session (not assumed from training data) — see Sources.

**Concrete pattern for `.bind(ioloop, view)`:**
```python
def bind(self, ioloop, view):
    ready = threading.Event()
    def _do_bind():
        self._sock = self._context.socket(self._zmq_socket_type())  # ROUTER or SUB
        self._sock.setsockopt_string(zmq.IDENTITY, self.source_id)  # router_bind only
        if self.role == "router_bind":
            self._sock.bind(f"tcp://0.0.0.0:{self.listen_port}")
        else:
            self._sock.connect(f"tcp://{self.host}:{self.connect_port}")
            self._sock.setsockopt_string(zmq.SUBSCRIBE, "")
        self._stream = ZMQStream(self._sock, ioloop)
        self._stream.on_recv(self._on_recv)
        ready.set()
    ioloop.add_callback(_do_bind)
    ready.wait(timeout=5.0)   # init_hardware() is synchronous; bind must complete before it returns
```
This generalizes identically for `router_bind` and `sub_connect` — the only difference is
`socket(zmq.ROUTER)` + `.bind()` + identity-filtering-on-recv vs. `socket(zmq.SUB)` + `.connect()`
+ `@decoder`-on-recv. Answers the posed question directly: **the pattern generalizes; the two roles
differ only in socket type and bind-vs-connect, not in threading model.**

### Egress must be a plain thread, not a Tornado callback

The shared IOLoop above also services **every** `ExternalHardware` instance's ingress on this
pilot, plus the orchestrator DEALER. A blocking HTTP `PUT` (OE's REST control, Phase 26) or a
blocking ZMQ send executed as a Tornado callback would freeze that entire IOLoop — not just its own
module's traffic, but every other module's ingress and the pilot's own orchestrator heartbeat/STOP
channel — for the duration of the call. This directly contradicts EXTLINK-15's "never execute on
the FDA thread" intent generalized correctly: it must also never execute on the shared IOLoop
thread.

**Recommended pattern — one plain `threading.Thread` + one `queue.Queue` per device**, mirroring
the existing `Event_Dispatcher._sender_loop` pattern almost exactly (verified read,
`Event_Dispatcher.py:35-52`): a daemon thread blocked on `queue.get()`, doing the actual blocking
I/O synchronously per item, with a sentinel value for clean shutdown. This is the established idiom
in this codebase for "don't block the caller, but preserve strict ordering" — reuse it rather than
inventing a new one.

```python
class _EgressWorker:
    def __init__(self, send_fn, maxsize=64):
        self._q = queue.Queue(maxsize=maxsize)
        self._send_fn = send_fn
        self._dropped = 0
        self._thread = threading.Thread(target=self._loop, daemon=True)
        self._thread.start()

    def enqueue(self, item):
        try:
            self._q.put_nowait(item)
        except queue.Full:
            self._dropped += 1
            # caller logs a CONTINUOUS event naming what was dropped (EXTLINK-15)

    def _loop(self):
        for item in iter(self._q.get, None):   # sentinel shutdown, same idiom as Event_Dispatcher
            try:
                self._send_fn(item)             # fire-and-forget: no retry, no re-queue on failure
            except Exception:
                pass                             # caller's on-failure logging happens around send_fn
    def stop(self):
        self._q.put(None)
        self._thread.join(timeout=2.0)
```
"Drop the newest" (locked decision) is exactly `queue.Full` on `put_nowait` — Python's stdlib
`queue.Queue` already refuses new items over `maxsize` rather than evicting old ones, so this is a
zero-effort match for the locked policy; no custom ring-buffer needed.

### `on_run_start` / `on_run_stop` firing points — both verified against real code

`mics_task.__init__()` (`mics_task.py:104-163`) calls, in this exact order: `super().__init__()`
(sets `self.node`, `self.event_dispatcher`, `self.view`) → `self.init_hardware()` → `check_for_detectors()`
→ `init_flags()` → constructs `self.stages = FiniteDeterministicAutomaton(...)` → `load_fda_from_json()`
**only if** a `state_machine` kwarg was passed.

- **`init_hardware()` override** (new, per the file list) is where the `.bind(ioloop, view)`
  post-pass belongs — call `super().init_hardware()` first (unchanged base behavior for every other
  hardware type), then iterate the resolved `self.hardware["Modules"]` dict for instances that are
  `ExternalHardware` and call `.bind()` on each.
- **`on_run_start(run_ctx)` fires immediately after that bind post-pass**, inside the same override,
  fired asynchronously (each instance's own thread or the egress worker's thread — do not block
  `init_hardware()`'s return on it, since `_wait_extlink_ready`, not `init_hardware()`, is what
  polls for readiness).
- **`_wait_extlink_ready` pre-state injection belongs inside (or immediately after)
  `load_fda_from_json()`**, since that is the only place `self.stages.add_method()` /
  `set_initial_method()` are called to build the FDA from JSON. `FiniteDeterministicAutomaton`
  (verified read in full, `utils/FiniteDeterministicAutomaton.py`) needs **no special-casing** for
  this — a synthetic pre-state is just one more `add_method` + `add_transition` (gated on a readiness
  poll function) + `set_initial_method()` override of whatever the JSON declared. This ordering
  (`init_hardware()` → bind → `load_fda_from_json()` → pre-state) already matches EXTLINK-13's "fires
  after `.bind()`" requirement without any reordering inside `mics_task.__init__()`.
- **`run_ctx` needs zero new plumbing.** Every field EXTLINK-16 lists (`run_id`, `session_id`,
  `subject_key`, `pilot`, task-definition id, start timestamp) is already present as a kwarg
  `mics_task.__init__` receives today: `self.run_id`, `self.session` (note: the kwarg key is
  literally `"session"`, not `"session_id"` — traced end-to-end from
  `orchestrator_station.py:721/753/783/814: task["session"] = session_id` through
  `task.py:130: self.session = kwargs['session']`), `self.subject`, `self.pilot`,
  `kwargs.get('task_definition_id')` (confirmed present in the START payload at
  `orchestrator_station.py:743/805`), and `self.t_start` (already set at `mics_task.py:123`).
- **`on_run_stop()`'s chokepoint is `Hardware.release()`.** `Task.end()` (`task.py:434-442`,
  verified read in full) calls `obj.release()` on **every** object in `self.hardware`, for every
  group, unconditionally. `mics_task.end()` already overrides `end()` and calls `super().end()`
  (`mics_task.py:1477-1483`). `pilot.py::run_task`'s `finally` block (verified read in full,
  `pilot.py:1237-1258`) calls `self.task.end()` unconditionally on **all three** exit paths: normal
  completion (the `while True` loop breaks when `self.running.is_set()` goes false, which happens
  both on graceful FDA completion via `l_stop` and on the STOP button), and inside its own
  `except Exception` handler for a task exception. **This directly answers the posed question**:
  there is exactly ONE chokepoint, already wired, requiring zero new code to guarantee firing —
  `ExternalHardware.release()` simply needs to call `on_run_stop()` (plus close its socket, stop its
  egress worker) as part of its own `.release()` body, the same pattern `timer.py`'s
  `TIMER.release()` already uses (`cancel()` then return).

  **The one real caveat (Correction 3):** `pilot.py:1240-1241` calls
  `self.task.event_dispatcher.stop()` **before** `self.task.end()` in the same `finally` block.
  `Event_Dispatcher.stop()` (verified read, `Event_Dispatcher.py:59-62`) enqueues a `None` sentinel
  and the sender thread's `for msg in iter(self._send_queue.get, None)` loop exits the instant it
  dequeues that sentinel — so any `dispatch_event()` call made from inside `on_run_stop()` /
  `release()` (which runs strictly after `event_dispatcher.stop()`, since `end()` is called next)
  races a sender thread that may already have exited, and there is no code path that flushes
  messages queued after the sentinel. **A CONTINUOUS event logged from inside `on_run_stop()` is not
  guaranteed to reach ES** — flagged as an Open Question for the plan (see below), since neither
  `pilot.py` nor `task.py` are in scope to reorder.

### Backend safety net — reuse the shape of `_run_watchdog`, not its body (Correction 2)

`orchestrator_station.py::_run_watchdog` (defined at line 926, thread-start commented out at line
57) is the closest existing thing to "reconciliation of stale/active runs" and answers the posed
question honestly: **the mechanism exists in skeleton form, is disabled, and has a bug that
disqualifies it from being merely re-enabled.** It reads `run.get("started_at")` — set once,
literally, at `start_run()` time (`orchestrator_station.py:385`) — and never refreshed anywhere; its
`status` field is likewise set to `"running"` exactly once and never updated
(`orchestrator_station.py:386`, confirmed by grepping every write site). Its `elapsed > 30` check
would therefore fire for **every** run lasting more than 30 seconds, which is every real behavioral
session. This is why it is commented out — it cannot be the model to copy literally.

What DOES already exist and IS live: `_redis_touch(pilot_key)` (`orchestrator_station.py:983-994`)
writes an `updated_at` timestamp to Redis on every `on_state`/`on_ping` message from the Pi — a
genuine per-pilot liveness heartbat, already wired, already firing continuously during a running
task. **This — not `started_at` — is the right staleness signal** for a Phase-18 reconciliation
loop: "pilot `X` holds the lease for device `D`, and Redis's `updated_at` for pilot `X` is stale by
more than N seconds" is a correct "run ended uncleanly" signal; "started_at is old" is not.

`stop_run()` (`orchestrator_station.py:401-448`, verified read in full) is the existing model for
"the three things a clean stop must do" — send `STOP` over ZMQ, mark the backend run stopped, clear
`active_run` state — and is the template the lease-release reconciliation should structurally
mirror, minus the parts that require an already-connected pilot.

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Binary wire serialization | A hand-rolled struct/binary format | `msgpack` (new dependency — see Pitfalls for the version pin) | Locked decision in CONTEXT; also avoids inventing a schema-evolution story for the envelope |
| Cross-thread socket registration | Manual locks/condition variables around `ZMQStream` setup | `IOLoop.add_callback()` | The one Tornado-documented thread-safe entry point; anything else risks a race on the poller's fd table |
| FIFO ordered outbound queue | A custom ring buffer / linked-list queue | stdlib `queue.Queue(maxsize=N)` | `put_nowait` + `queue.Full` already implements "bounded, drop-newest, never block the producer" exactly as locked |
| Bounded ingress buffer, drop-oldest | Custom deque bookkeeping | `collections.deque(maxlen=256)` | Stdlib deque already drops the oldest item automatically once `maxlen` is exceeded — matches EXTLINK crash-isolation's "overflow drops oldest" rule for free |
| Reachable/operational detection ("is this device alive") | A new heartbeat subsystem | The existing `Event_Dispatcher` + Tracker + CONTINUOUS event plumbing, wrapped in a lib-supplied predicate | Every piece needed (timestamped events, a boolean Tracker, ES visibility) already exists; only the predicate function is new |
| Preflight blocking issue for a shared resource | A new validation framework / endpoint | The existing typed-issue list in `toolkit_dispatch.py`'s `preflight_validate` (`missing`/`incomplete_config`/`class_mismatch`/`fda_ref_unresolved`) | Same response shape, same React renderer (`HardwareCheckModal`), zero new UI surface — literally the pattern Phase 25's `view_key_unresolved` already added |

**Key insight:** almost nothing in this phase should introduce a genuinely new mechanism — it should
compose four already-proven ones (Net_Node's ZMQStream pattern, Event_Dispatcher's queue+thread
pattern, Tracker/View, and the preflight issue list). The one place that IS genuinely new
territory for this codebase is `sub_connect` (dialing out with SUB) — there is no existing
precedent anywhere in `autopilot/` for a Pi-initiated outbound ZMQ connection; every existing
socket in this codebase either binds (ROUTER) or is a DEALER connecting to the orchestrator. Treat
`sub_connect` as the one component that needs an actual smoke test, not just code-review confidence.

## Common Pitfalls

### Pitfall 1: Assuming msgpack is available
**What goes wrong:** `import msgpack` raises `ModuleNotFoundError` on the Pi's actual pilot venv.
**Why it happens:** `18-CONTEXT.md`'s "already transitive through the pyzmq/tornado stack" claim is
incorrect — verified live via SSH (`~/.venv/autopilot`, the exact venv `run_pilot.sh` activates)
that `msgpack` is not installed, and neither `pyzmq` nor `tornado` depend on it.
**How to avoid:** Wave 0 task: add `msgpack` to `~/pi-mirror/autopilot/requirements.txt` (and the
top-level `~/pi-mirror/requirements.txt`, which mirrors the environment.yml pins) pinned to a
version compatible with the Pi's **Python 3.7.3** — current msgpack (1.1.x) requires Python ≥3.9;
an earlier 1.0.x release is needed. This is a `<verify>`-block, USER-RUN pip install per the Pi
operational rules — the agent cannot install packages on the Pi.
**Warning signs:** Any plan task that writes `import msgpack` into `external_hardware.py` without a
preceding Wave 0 task to install it on the rig.

### Pitfall 2: Calling `IOLoop.current()` inside `.bind()`
**What goes wrong:** Silent, permanent ingress failure — no exception, no log line, sockets appear
created but `on_recv` callbacks never fire because nothing ever calls `.start()` on the loop that
was actually created.
**Why it happens:** `IOLoop.current()` is thread-local; `init_hardware()` runs in the `run_task`
thread, not the thread that actually drives the Pilot's `Net_Node` IOLoop.
**How to avoid:** `.bind(ioloop, view)` must receive the already-running loop object explicitly
(`self.node.loop`, threaded through from `mics_task`) and must register the socket via
`ioloop.add_callback(...)`, never by touching the socket directly from the calling thread.
**Warning signs:** A smoke test that appears to connect (TCP handshake succeeds) but no `SIG`/`EVT`
frame ever reaches a Tracker — the classic signature of a registered-but-never-polled fd.

### Pitfall 3: CONTINUOUS events emitted from `on_run_stop()` silently vanish
**What goes wrong:** Any `dispatch_event()` call made from inside `on_run_stop()`/`release()` may
never reach ES.
**Why it happens:** `pilot.py::run_task`'s teardown calls `event_dispatcher.stop()` (which tells the
sender thread to exit on the next sentinel it dequeues) strictly BEFORE `task.end()` (which is what
calls `.release()` → `on_run_stop()`). By the time `on_run_stop()` runs, the sender thread may
already have exited.
**How to avoid:** Do not make any EXTLINK-16 requirement depend on a CONTINUOUS event surviving from
inside `on_run_stop()`. If the plan needs proof that stop fired, prefer a Python `logger` call
(always reaches the Pi's local log file, independent of the event dispatcher) plus, if ES visibility
of the stop itself is truly required, log it as an ordinary event **during the run** immediately
before teardown begins (e.g., have the STOP-button/exception path emit a "stopping" CONTINUOUS event
before `event_dispatcher.stop()` is reached) rather than from inside `release()`.
**Warning signs:** A Wave-0 test asserting "an ES CONTINUOUS event exists for on_run_stop" — this is
untestable as literally stated given the current teardown order, and `pilot.py`/`task.py` are out of
scope to reorder.

### Pitfall 4: Treating `_run_watchdog` as a working reconciliation loop
**What goes wrong:** Enabling it as-is (uncommenting the thread-start) would kill every session
longer than 30 seconds.
**Why it happens:** Its threshold checks wall-clock time since `active_run["started_at"]`, a field
set once and never refreshed — not "time since last heartbeat."
**How to avoid:** Build the lease-release reconciliation as its own narrow loop keyed on the
already-live `_redis_touch`/`on_state`/`on_ping` heartbeat staleness, not on `_run_watchdog`'s
`started_at` field. Do not simply uncomment line 57.
**Warning signs:** A plan task titled "re-enable `_run_watchdog`" without also rewriting its
staleness check.

### Pitfall 5: `ast.literal_eval` on decorator arguments
**What goes wrong:** `@signal(default=0.0, stale_after_ms=200)` — fine, all literals. But
`@event(payload={"object": str, "confidence": float})` is **not** literal-eval-safe: `str` and
`float` are bare names (`ast.Name` nodes referencing builtins), not literal values, so
`ast.literal_eval` raises `ValueError: malformed node or string`.
**Why it happens:** `extract_ast_metadata()` (`hardware_libs.py:52-78`, verified read) currently
never inspects `decorator_list` at all — this is genuinely new code, not an extension of an
existing decorator-parsing path.
**How to avoid:** Walk the decorator's `ast.Call` node manually: for each keyword argument, if the
value is an `ast.Dict`, walk its `keys`/`values` pairs and for each value that is an `ast.Name`
whose `id` matches a known builtin type name (`str`, `int`, `float`, `bool`), store the string
`"str"`/`"int"`/etc. — exactly the "string-typed... the extractor cannot import the lib" contract
EXTLINK-09 already specifies. Do not attempt `ast.literal_eval` on the whole decorator call.
**Warning signs:** A 422/500 the moment a real hw-lib upload includes an `@event(payload={...})`
with a type reference instead of a literal default.

### Pitfall 6: Assuming `sub_connect` has a working precedent to copy
**What goes wrong:** Treating `sub_connect` as "the same as `router_bind` but with `.connect()`
instead of `.bind()`" and skipping a dedicated smoke test.
**Why it happens:** Every existing ZMQ socket in `autopilot/` either binds (ROUTER, e.g.
`node.py:147-151`) or is a DEALER connecting outbound to the orchestrator — there is no existing SUB
socket anywhere in the codebase to model after or regression-test against.
**How to avoid:** Budget an explicit `sub_connect` + `@decoder` smoke test (a standalone PUB script
publishing a foreign-format frame) as its own Wave-0/verification item, separate from the
`router_bind` smoke test EXTLINK-11 already specifies.
**Warning signs:** A plan that only tests `router_bind` and assumes `sub_connect` "should just work"
by symmetry.

### Pitfall 7: Forgetting the base `Hardware.release()` contract
**What goes wrong:** `release()` is `@abstractmethod`-style enforced by convention (base
`Hardware.release()` raises `Exception('The release method was not overridden...')` if not
redefined) — if `ExternalHardware` doesn't override it, EVERY run's teardown raises inside
`Task.end()`'s per-object loop.
**Why it happens:** Easy to focus on `.bind()`/lifecycle hooks and forget the mandatory
`release()` override every `Hardware` subclass carries.
**How to avoid:** `ExternalHardware.release()` must (a) call `on_run_stop()`, (b) stop the egress
worker thread, (c) close the ZMQ socket/stream — mirroring `timer.py`'s `TIMER.release()` shape
exactly (verified read, `timer.py:31-34`).
**Warning signs:** `Task.end()`'s per-hardware-object loop (`task.py:439-441`) has no
try/except around `obj.release()` — an unhandled exception there propagates up into
`pilot.py`'s own `try/except Exception as e:` around `self.task.end()`, which is caught and
logged, so it fails loud in the log but silently from the researcher's point of view (no ES event).

## Code Examples

### AST extractor decorator-arg extraction (pattern, not literal diff)
```python
# Extends hardware_libs.py::extract_ast_metadata — walk item.decorator_list per FunctionDef.
def _extract_decorator_meta(decorator_list: list[ast.expr]) -> dict | None:
    for dec in decorator_list:
        if not isinstance(dec, ast.Call):
            continue
        name = getattr(dec.func, "id", None)
        if name not in ("signal", "event", "command", "decoder"):
            continue
        kwargs = {}
        for kw in dec.keywords:
            if isinstance(kw.value, ast.Constant):
                kwargs[kw.arg] = kw.value.value
            elif isinstance(kw.value, ast.Dict):
                # payload={"object": str, "confidence": float} -- values are bare type names,
                # NOT literal-eval-safe. Stringify each value node instead.
                kwargs[kw.arg] = {
                    k.value: ast.unparse(v) for k, v in zip(kw.value.keys, kw.value.values)
                }
            else:
                kwargs[kw.arg] = ast.unparse(kw.value)
        return {"kind": name, **kwargs}
    return None
```

### `.bind()` thread-safe registration (see Architecture Patterns for full context)
```python
def bind(self, ioloop, view):
    ready = threading.Event()
    def _do_bind():
        # ... socket creation per role ...
        ready.set()
    ioloop.add_callback(_do_bind)
    if not ready.wait(timeout=5.0):
        raise RuntimeError(f"{self.name}: bind timed out on shared IOLoop")
```

### `mics_task.init_hardware()` override — bind post-pass (pattern)
```python
def init_hardware(self):
    super().init_hardware()  # unchanged behavior for every non-ExternalHardware type
    for group, entries in self.hardware.items():
        for name, hw in entries.items():
            if isinstance(hw, ExternalHardware):
                hw.bind(self.node.loop, self.view)
                run_ctx = {
                    "run_id": self.run_id, "session_id": self.session,
                    "subject_key": self.subject, "pilot": self.pilot,
                    "task_definition_id": getattr(self, "task_definition_id", None),
                    "started_at": self.t_start,
                }
                threading.Thread(target=hw.on_run_start, args=(run_ctx,), daemon=True).start()
```

### Egress worker (full pattern — see Architecture Patterns for rationale)
```python
# Source: modeled directly on Event_Dispatcher._sender_loop (verified read, Event_Dispatcher.py:35-52)
class _EgressWorker:
    def __init__(self, send_fn, maxsize=64):
        self._q = queue.Queue(maxsize=maxsize)
        self._send_fn = send_fn
        self.dropped = 0
        threading.Thread(target=self._loop, daemon=True).start()

    def enqueue(self, item):
        try:
            self._q.put_nowait(item)
        except queue.Full:
            self.dropped += 1
            raise  # caller emits the CONTINUOUS "dropped" event (EXTLINK-15)

    def _loop(self):
        for item in iter(self._q.get, None):
            try:
                self._send_fn(item)
            except Exception:
                pass  # fire-and-forget, no retry (locked decision)
```

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|---------------|--------|
| N/A — this phase adds a genuinely new capability, not a replacement | `ExternalHardware` as a first-class hardware-lib type | Phase 18 | First non-GPIO/i2c hardware category in the Pi's hardware substrate |
| `_run_watchdog`'s wall-clock-since-start staleness check | Redis `updated_at` heartbeat staleness (`_redis_touch`, already live via `on_state`/`on_ping`) | This research session's finding, not yet implemented | Corrects the planner's assumption about what "already exists" for the backend safety net |

**Deprecated/outdated:**
- `18-CONTEXT.md`'s "msgpack already transitive" claim — corrected this session; treat as false
  going forward.
- `_run_watchdog` as currently written — not deprecated exactly, but disabled and unsound; do not
  re-enable literally.

## Open Questions

1. **Can `on_run_stop()`'s status ever reach ES, given the `event_dispatcher.stop()` ordering?**
   - What we know: `pilot.py`'s teardown order (`event_dispatcher.stop()` then `task.end()`) is
     fixed and out of this phase's file-change scope.
   - What's unclear: whether any EXTLINK-16/EPHYS-01 success criterion actually requires an ES
     event fired FROM INSIDE on_run_stop (vs. requiring only that the OE REST call itself
     happened, verifiable via OE's own state or the persisted recording path).
   - Recommendation: the plan should not test "CONTINUOUS event visible in ES for on_run_stop" as a
     literal acceptance criterion. If stop-time ES visibility genuinely matters for a later phase,
     it needs to be logged as a normal in-run event BEFORE `l_stop`/exception unwinding begins, not
     from inside `release()`.

2. **What, concretely, can "the backend releases the lease and issues the stop itself" mean when
   Phase 18 has zero OE-specific (or any device-specific) code?**
   - What we know: Phase 18 is the generic substrate; "OpenEphys" doesn't exist as a concept here.
     The device lease is a DB row keyed on normalized `host`. The backend has no channel to speak
     to an arbitrary foreign device's control API — "the Pi owns both channels" is a locked
     decision specifically to avoid the backend needing one.
   - What's unclear: whether Phase 18's safety net can only ever (a) release the lease row in the
     DB and mark the run errored — leaving actual device-side cleanup (e.g., OE still recording) as
     a documented residual risk until a human notices — or whether Phase 18 needs to define an
     extension point (e.g., a stored per-lease "how to force-stop" descriptor) that Phase 26 fills
     in with OE-specific behavior.
   - Recommendation: scope Phase 18's safety net to (a) alone — release the lease + mark the run
     errored — and let Phase 26 decide whether OE needs its own additional reconciliation (e.g., a
     periodic "is this OE box's active session someone we still recognize" check called from
     wherever Phase 26's own code runs). Document the residual risk explicitly rather than inventing
     a generic force-stop mechanism Phase 18 has no way to test.

3. **Exact msgpack version pin for Python 3.7.3.**
   - What we know: current msgpack (1.1.x per PyPI) requires Python ≥3.9; the Pi runs 3.7.3.
   - What's unclear: the exact last msgpack release supporting 3.7 without a live `pip install`
     against the actual rig venv (which the agent cannot run — Pi package installs are user-run).
   - Recommendation: Wave 0 `<verify>` block should have the user run
     `pip install msgpack` inside `~/.venv/autopilot` on the Pi and record the resolved version,
     rather than the plan hardcoding a guessed pin that may not resolve.

4. **Is a single shared egress worker thread per pilot preferable to one thread per
   `ExternalHardware` instance?**
   - What we know: the locked decision is "one FIFO worker per device" — unambiguous that ordering
     is per-device, not global.
   - What's unclear: whether "per device" should be implemented as literally one OS thread per
     `ExternalHardware` instance (simple, matches the locked language exactly, but N threads for N
     modules) vs. one shared thread pool with per-device FIFO sub-queues (marginally more efficient,
     more code).
   - Recommendation: one thread per instance — this rig will have at most a handful of external
     modules per pilot (OE control + OE data + maybe DLC later), so thread-count is a non-issue, and
     "one thread per device" is both the simplest reading of the locked decision and the easiest to
     reason about for ordering guarantees.

## Validation Architecture

### Test Framework

| Property | Value |
|---|---|
| Framework (backend) | pytest, run inside the `api` docker container (`docker compose exec api pytest`) |
| Framework (Pi, agent-runnable) | pytest, but `import autopilot` **fails on the dev host** — verified this session: `autopilot/autopilot/__init__.py:4` unconditionally does `from autopilot.setup import setup_autopilot`, which does `import npyscreen`, not installed here (`ModuleNotFoundError: No module named 'npyscreen'`). This reproduces Phase 23's documented finding exactly. **Any test file that does `from autopilot.hardware import ...` or `from autopilot.tasks import ...` is USER-RUN on the Pi, not agent-runnable**, regardless of whether the logic under test needs real hardware. `msgpack` and `zmq` are also both absent from the dev host's Python (verified: `ModuleNotFoundError` for both) — a further reason to isolate anything msgpack/zmq-touching into a pure-stdlib-shape module (see Design-for-Testability below). |
| Framework (React) | N/A this phase — no React changes in scope |
| Quick run command (backend) | `docker compose exec api python -m pytest -q api/tests/test_toolkit_dispatch.py -k lease` (once written) |
| Quick run command (Pi, agent-runnable, no `autopilot` import) | `cd ~/pi-mirror && python3 -m pytest -q tests/test_extlink_decoder.py tests/test_extlink_egress.py tests/test_extlink_wire.py` (proposed new files — see below; these must not import `autopilot.*`) |
| Full suite command (backend) | `docker compose exec api python -m pytest -q` |
| Full suite command (Pi) | **USER-RUN**: `cd ~/Apps/mice_interactive_home_cage && python3 -m pytest tests/ -q` |

### Design-for-testability requirement (this is a plan-shaping finding, not a footnote)

Because `import autopilot.hardware.external_hardware` always executes `autopilot/__init__.py` (Python
runs every parent package's `__init__.py` on any dotted import, with no way around it short of
editing that file, which is out of scope), **the only way to get agent-side unit coverage on this
dev host is to keep the msgpack codec, the `@decoder` dispatch logic, the stale-policy calculator,
and the egress-queue mechanics in a small module (or a set of functions/classes within
`external_hardware.py`) that has zero `autopilot.*` imports at module level** — pure stdlib plus
`msgpack` (installable in the agent's own test environment; NOT the Pi). `ExternalHardware` itself
(the `Hardware` subclass, needing `autopilot.hardware.Hardware`) stays USER-RUN, but the pure logic
it delegates to can be imported directly and unit-tested by the agent. Concretely: put the wire
codec (`encode_sig`/`decode_frame`), the decoder-dispatch loop, the stale-policy resolver, and the
`_EgressWorker` class in importable, `autopilot`-free shape (even if they end up as
`@staticmethod`s or module-level functions inside `external_hardware.py` — Python only executes the
*package* `__init__.py` chain when the import statement reaches into the package; a test file that
does `importlib.util.spec_from_file_location(...)` directly against `external_hardware.py`'s path
**still triggers `autopilot/__init__.py`** the moment `external_hardware.py` itself contains
`from autopilot.hardware import Hardware` at module scope — so the pure pieces must be extractable
into helpers that do NOT require that import to be evaluated, e.g. by deferring the `Hardware`
import to be local to the class definition it's needed for, or by keeping the pure logic in a
separate sibling module `external_hardware_wire.py` with zero autopilot imports, imported BY
`external_hardware.py` but requiring no reverse dependency. **Recommend the sibling-module split**
— it is the only approach that reliably survives whatever import ordering the class ends up with.

### Per-subsystem validation strategy

#### 1. `sub_connect` + `@decoder`
- **(A) Agent-verifiable, no live publisher needed.** The `@decoder` contract is "translate one
  foreign frame (bytes) into a list of declared signal/event updates" — a pure function over bytes
  in, structured updates out. Write `tests/test_extlink_decoder.py` (new, `autopilot`-free) with
  **synthetic captured frames** as literal byte strings/dicts (no real OE process needed): decode a
  well-formed frame → asserts the exact `(signal_name, value)` tuples produced; decode a truncated
  frame → asserts a `None`/empty-list return (never a raised exception, per EXTLINK-08); decode a
  frame with an unknown field → asserts the unknown-field is dropped, known fields still applied.
  This is the single highest-value test in the whole phase, since it's the one component with zero
  existing precedent to lean on (see Don't Hand-Roll) — write it FIRST, before any Pi-side wiring.
- **(A) The SUB socket's connect-vs-bind role selection** (does `role: "sub_connect"` correctly
  choose `zmq.SUB` + `.connect()` and skip the DEALER-identity check) is verifiable with a **fake
  socket factory**: inject a stub object in place of `zmq.Context().socket(...)` in a unit test and
  assert `.connect()` was called with the configured `host:connect_port` and `.bind()` was not,
  without ever opening a real network socket.
- **(B) USER-RUN, single checkpoint:** an actual `sub_connect` end-to-end proof needs a real PUB
  publisher. Reuse `extlink_smoke.py`'s shape but add a `publish` subcommand (or a tiny standalone
  script) that PUBs a synthetic foreign-format frame from the dev machine; the user runs it against
  the deployed Pi and confirms the resulting view key updates. This is NOT verifiable from the
  mirror because it requires a live, bound Tornado IOLoop on the actual Pi process.

#### 2. Egress queue
- **(A) Fully agent-verifiable with a fake failing sink — no network, no Pi.** `tests/test_extlink_egress.py`
  (new, `autopilot`-free — the `_EgressWorker` class from Code Examples takes a `send_fn` callable,
  which is trivially replaceable with a test double):
  - `test_fifo_order`: enqueue items `[1,2,3]` with a `send_fn` that appends to a list; assert the
    list ends up `[1,2,3]` (ordering preserved under a single worker thread).
  - `test_drop_newest_on_overflow`: construct with `maxsize=2`, enqueue 3 items faster than
    `send_fn` can drain (block `send_fn` with a `threading.Event`); assert the 3rd `enqueue()` call
    raises/reports `queue.Full` and `dropped == 1`, and that items 1 and 2 (not 3) are the ones
    actually sent — proving "drop the newest," not the oldest.
  - `test_no_retry_on_failure`: `send_fn` raises on the first call; assert the worker thread
    continues (doesn't crash) and the *next* enqueued item is still attempted — proving fire-and-
    forget, no retry of the failed item.
  - `test_alive_flips_after_n_consecutive_failures`: wrap `send_fn` to always raise; assert an
    `alive`-flip callback fires exactly once after the configured `egress_fail_threshold`
    consecutive failures, and does not re-fire on every subsequent failure (edge-triggered, not
    level-triggered).
  All four are pure `threading`/`queue` mechanics with a fake `send_fn` — zero dependency on ZMQ,
  HTTP, or the Pi.
- **(B) USER-RUN:** proving the egress worker never blocks the FDA thread under REAL network
  latency (e.g., OE's REST endpoint hanging) can only be observed on the rig or against a real
  networked stub service — not meaningfully fakeable in a unit test, since the property being
  proven is "the calling thread's timing is unaffected," which requires a real OS thread scheduler
  under real I/O latency to be convincing. Budget this as one rig checkpoint per Phase 26, not
  Phase 18 (Phase 18 only needs to prove the *mechanism*, i.e. tests above).

#### 3. Run lifecycle hooks (`on_run_start`/`on_run_stop`)
- **(A) Agent-verifiable in the mirror, no Pi required, no autopilot import if built per the
  Design-for-testability note above:** `tests/test_extlink_lifecycle.py` —
  - `test_on_run_start_retried_until_ready`: a fake lib whose readiness hook returns `False` twice
    then `True`; assert the retry loop calls it exactly 3 times within a fake `wait_timeout_s`
    clock (inject a fake clock/sleep function, don't actually sleep in the test).
  - `test_on_run_start_never_blocks_caller`: call the async-dispatch wrapper and assert it returns
    before the fake hook's artificial delay elapses (prove "returns immediately," per EXTLINK-16).
  - `test_on_run_stop_called_exactly_once_per_release`: construct a fake `ExternalHardware`-shaped
    object, call `.release()`, assert `on_run_stop` was invoked exactly once — this is testing the
    NEW code's own contract, not `Task.end()`'s wiring (which is existing, already-verified-by-
    reading code, and does not need a new test — seePitfall 7/Architecture Patterns write-up).
  - `test_run_ctx_shape`: assert the dict passed to `on_run_start` has exactly the six locked keys
    (`run_id`, `session_id`, `subject_key`, `pilot`, `task_definition_id`, `started_at`) and no
    others — a cheap regression guard against accidentally leaking a seventh field that would break
    every existing subclass (the exact risk EXTLINK-16 calls out).
- **(A) Regression-only, not new logic, but worth a one-line pin:** `Task.end()` already calls
  `.release()` unconditionally on every hardware object (verified by reading `task.py:434-442`
  this session) — a plan task should add a **narrow** regression test in `tests/test_mics_task_attrs.py`
  (existing file) asserting `mics_task.end()` still calls `super().end()` (byte-diff-style check,
  guards against a future edit silently dropping the call this whole chokepoint depends on).
- **(B) NOT verifiable before the rig, state plainly:** whether `on_run_stop()`'s own CONTINUOUS
  logging reaches ES. Per Open Question 1 / Pitfall 3, `event_dispatcher.stop()` runs before
  `task.end()`/`release()` in `pilot.py`'s teardown — **do not write an acceptance test asserting
  an ES event exists for the stop itself**; it is provably a race the plan cannot win without
  editing `pilot.py` (out of scope). If Phase 26 needs stop-time ES visibility, log it as an
  in-run event BEFORE the STOP/exception path unwinds, and test THAT instead.
- **(B) USER-RUN, single checkpoint:** the actual `_wait_extlink_ready` pre-state firing on the real
  FDA (does the pilot really block on the synthetic state, does the three-exit priority order hold
  end-to-end) needs the real Pi's `FiniteDeterministicAutomaton` driven by `pilot.py::run_task`'s
  real loop — the mechanics of `add_method`/`set_initial_method`/`add_transition` are stdlib-pure
  and could theoretically be unit-tested against a bare `FiniteDeterministicAutomaton` instance
  (which itself has zero `autopilot.hardware`/`autopilot.tasks` imports — verified: it only imports
  `Event_Dispatcher` and `Event`, and `Event_Dispatcher.py` imports `pigpio`, which IS installable
  without the Pi but talks to nothing real if unused) — **flag as a stretch goal**: a
  `tests/test_wait_extlink_ready_transitions.py` that builds a `FiniteDeterministicAutomaton`
  directly (bypassing `mics_task` entirely) and asserts the three-exit transition table is wired
  correctly, IS agent-runnable if it avoids importing `mics_task`/`Hardware`. The full pre-state
  injection wired through `load_fda_from_json()` is USER-RUN (that function lives inside
  `mics_task.py`, which pulls in the full `autopilot` chain).

#### 4. Device lease
- **(A) Fully agent-verifiable, no Pi at all.** This is the cleanest subsystem in the phase — it is
  100% backend (`api/`), living in `toolkit_dispatch.py`'s `preflight_validate`, the exact pattern
  Phase 25's `view_key_unresolved` already added with zero new machinery. `api/tests/test_toolkit_dispatch.py`
  (existing file) gains:
  - `test_lease_blocks_second_run_same_host`: seed two `pilot_hardware_config` rows on two
    different pilots with the same normalized `host`, simulate an active lease for pilot A, call
    `preflight_validate` for pilot B's session → assert a new `device_held` (or equivalent) issue
    naming pilot A's pilot/subject/run, exactly as EXTLINK-17 specifies.
  - `test_lease_key_is_host_not_host_port`: two configs with the same `host` but different `port`
    fields → assert they still collide on the SAME lease (proving `host:port` was correctly
    rejected as the key, per the locked decision).
  - `test_lease_released_on_manual_force_release`: call whatever force-release endpoint the plan
    adds → assert a subsequent `preflight_validate` no longer reports the issue.
  - `test_lease_released_when_reconciliation_marks_run_ended`: exercise the (rewritten, per
    Correction 2) reconciliation logic directly against a fake/stale Redis `updated_at` timestamp
    → assert the lease row is cleared. Test this against the reconciliation function in isolation
    (call it directly with a fabricated stale timestamp), not by actually waiting out a real
    timeout — direct call keeps the test fast and deterministic, avoiding the reconciliation loop's
    real 5s-poll rhythm.
  All of the above run via `docker compose exec api python -m pytest -q api/tests/test_toolkit_dispatch.py -k lease`
  against the real (or test) Postgres — no Pi, no mocking of `zmq`/`msgpack` needed at all.

#### 5. Liveness hook
- **(A) Agent-verifiable, mirror-only, no Pi.** The hook contract is "a predicate function, default
  = data-within-`stale_ms`, overridable per lib" — pure logic testable with a fake clock:
  `tests/test_extlink_liveness.py` (new, `autopilot`-free if the predicate itself takes
  `last_seen_ts`/`now_ts` as plain floats, not live pigpio ticks):
  - `test_default_liveness_alive_within_window`: `last_seen = now - 1.0`, `stale_ms = 3000` →
    `True`.
  - `test_default_liveness_dead_outside_window`: `last_seen = now - 5.0`, `stale_ms = 3000` →
    `False`.
  - `test_liveness_independent_of_signal_staleness`: construct a signal with `stale_policy:
    return_default` and an old timestamp, and a liveness hook returning `True` independently
    (simulating "reachable but quiet") → assert `alive` stays `True` while the signal's own
    `get_state()`-equivalent returns the declared default — proving EXTLINK-07's core split is
    correctly decoupled in code, not just in the docstring.
  - `test_lib_override_replaces_default`: pass a custom predicate at construction → assert the
    default data-arrival check is never consulted (proving overridability, since OE needs to poll
    HTTP status instead).
- **(B) USER-RUN, single checkpoint:** does the CONTINUOUS event actually reach ES on a real
  `alive` flip during a real run — this is the one place a genuine `Event_Dispatcher`/pigpio-tick
  round-trip (verified this session: `dispatch_event()` requires a real `pigpio.pi` clock, with no
  fallback timebase by design) is unavoidable. Fold into the same rig checkpoint as the
  `sub_connect` end-to-end proof (EXTLINK-11-style smoke test) rather than a separate rig visit.

#### 6. AST-extractor extension (`@signal`/`@event`/`@command`/`@decoder` metadata)
- **(A) Fully agent-verifiable, no Pi, no docker even required for the parsing logic itself**
  (pure `ast` stdlib) **but the endpoint round-trip is backend, dockerized:**
  - `api/tests/test_hardware_libs.py` (existing file — confirm exact name via
    `grep -rl decorator api/tests/` before creating a duplicate) gains
    `test_extract_signal_decorator_literal_kwargs`, `test_extract_event_decorator_payload_dict_with_bare_types`
    (the exact `payload={"object": str, "confidence": float}` case from Pitfall 5 — assert the
    extractor does NOT raise and produces `{"object": "str", "confidence": "float"}`, string-typed),
    `test_extract_command_decorator_args_and_return`, `test_extract_decoder_flag_present`.
  - `test_upload_hardware_lib_with_extlink_decorators_end_to_end`: `POST /api/hardware-libs` with a
    full `ExternalHardware` subclass source string → assert `ast_metadata.extlink` is populated
    with the expected shape, run against the live docker compose `api` service exactly like every
    other `hardware_libs.py` test.
  Zero rig involvement anywhere in this subsystem — it is pure `ast.parse` plus an existing FastAPI
  endpoint, both fully reachable from the agent's own environment.

### What is genuinely NOT verifiable before the rig (single consolidated checkpoint)

Everything below requires a live, bound Tornado IOLoop inside the actual `pilot.py` process, a real
`pigpio` clock, or a real foreign publisher — none of which exist in the mirror. Per the Pi
operational rules, the agent hands the user a single `<verify>` checklist rather than scattering
rig touches across the plan:

1. `router_bind`: a real DEALER (or the extended `extlink_smoke.py`) connects, pushes a signal, an
   FDA transition fires within the target latency (EXTLINK-11, already the locked smoke test).
2. `sub_connect`: a real (or synthetic-but-live) PUB publishes a foreign-format frame, the deployed
   `@decoder` translates it, the resulting view key is readable — proves the IOLoop `add_callback`
   registration actually works on the real Pi process, not just in a mocked unit test.
3. The `_wait_extlink_ready` pre-state's full three-exit behavior wired through a real task start
   (all-ready → proceeds; `EXTLINK_SKIP_WAIT` → proceeds with a warning; timeout → clean abort) —
   the transition-table mechanics are agent-testable in isolation (see subsystem 3 above), but the
   end-to-end wiring through `mics_task.__init__`/`load_fda_from_json` is not.
4. `on_run_start`/`on_run_stop` firing on all three real teardown paths (normal completion, STOP
   button, task exception) against the real `pilot.py::run_task` loop.
5. Liveness flip → CONTINUOUS event → visible in ES (the pigpio-tick dependency, per Pitfall 3's
   sibling finding on `Event_Dispatcher.dispatch_event()`).
6. Egress worker under real network latency not blocking the FDA thread (subsystem 2's (B) item).
7. The device lease's end-to-end trigger from a REAL pilot crash/disconnect (as opposed to the
   fabricated-stale-timestamp unit test in subsystem 4's (A) list) — confirms the rewritten
   reconciliation loop's Redis-staleness signal actually fires from a genuinely dropped
   connection, not just from a hand-constructed test input.

Everything else in this phase — the decoder, the egress queue mechanics, the lifecycle hook
contracts, the entire device lease, the liveness predicate, and the AST extractor — is agent-
verifiable in the docker compose stack or as pure-Python unit tests in the mirror, per the
subsystem breakdown above. This is a real bias toward (A): of the six subsystems, only `sub_connect`
and the lifecycle hooks' full wiring have NO agent-runnable proof at all; the device lease has
NONE that require the rig.

### Phase Requirements → Test Map

| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| EXTLINK-14 | `@decoder` translates a foreign frame into signal/event updates | unit (Pi, agent-runnable) | `cd ~/pi-mirror && python3 -m pytest -q tests/test_extlink_decoder.py` | ❌ Wave 0 |
| EXTLINK-14 | `sub_connect` selects SUB+connect, not ROUTER+bind | unit (Pi, agent-runnable, fake socket) | `cd ~/pi-mirror && python3 -m pytest -q tests/test_extlink_decoder.py -k role_selection` | ❌ Wave 0 |
| EXTLINK-15 | Egress FIFO order, drop-newest, no-retry, alive-flip threshold | unit (Pi, agent-runnable, fake sink) | `cd ~/pi-mirror && python3 -m pytest -q tests/test_extlink_egress.py` | ❌ Wave 0 |
| EXTLINK-16 | `on_run_start` retried, non-blocking; `on_run_stop` fires once per release; `run_ctx` shape pinned | unit (Pi, agent-runnable, fake lib) | `cd ~/pi-mirror && python3 -m pytest -q tests/test_extlink_lifecycle.py` | ❌ Wave 0 |
| EXTLINK-16 | `mics_task.end()` still calls `super().end()` (regression pin on the existing chokepoint) | unit (Pi, agent-runnable) | `cd ~/pi-mirror && python3 -m pytest -q tests/test_mics_task_attrs.py -k end` | ❌ Wave 0 (extend existing file) |
| EXTLINK-17 | Device lease blocks second run, keyed on host not host:port, releases on force/reconciliation | unit (backend) | `docker compose exec api python -m pytest -q api/tests/test_toolkit_dispatch.py -k lease` | ❌ Wave 0 (extend existing file) |
| EXTLINK-07 | Liveness predicate default + override + independence from signal staleness | unit (Pi, agent-runnable) | `cd ~/pi-mirror && python3 -m pytest -q tests/test_extlink_liveness.py` | ❌ Wave 0 |
| EXTLINK-09 | AST extractor emits `ast_metadata.extlink` incl. bare-type payload dicts | unit (backend) | `docker compose exec api python -m pytest -q api/tests/test_hardware_libs.py -k extlink` | ❌ Wave 0 (confirm exact existing filename first) |
| EXTLINK-01/02/11 | `router_bind` end-to-end smoke test | manual + rig | USER-RUN: `python3 ~/pi-mirror/scripts/dev/extlink_smoke.py probe --pi-host ... --listen-port ... --source-id ...` | N/A — manual-only, justified: needs a real bound IOLoop on the Pi |
| EXTLINK-14 | `sub_connect` end-to-end smoke test | manual + rig | USER-RUN: extended smoke script `publish` subcommand against the deployed Pi | N/A — manual-only, justified: no foreign publisher / live IOLoop in the mirror |
| EXTLINK-13 | `_wait_extlink_ready` three-exit behavior end-to-end | manual + rig | USER-RUN: start a real task with a required external source, observe skip/timeout/proceed paths | N/A — manual-only, justified: requires `mics_task.__init__`/`pilot.py::run_task` live |

### Sampling Rate

- **Per task commit:** the specific test file touched, e.g.
  `cd ~/pi-mirror && python3 -m pytest -q tests/test_extlink_egress.py` (agent-runnable, since it
  has no `autopilot.*` import); `docker compose exec api python -m pytest -q api/tests/test_toolkit_dispatch.py -k lease`
  (backend).
- **Per wave merge:** `docker compose exec api python -m pytest -q` (full backend suite, must stay
  green — rebuild the `api` container first, since it has no bind mount, per this project's own
  documented gotcha); `cd ~/pi-mirror && python3 -m pytest -q tests/test_extlink_decoder.py tests/test_extlink_egress.py tests/test_extlink_lifecycle.py tests/test_extlink_liveness.py` (every
  new `autopilot`-free Pi test file, agent-runnable as a batch).
- **Phase gate:** full backend suite green, all agent-runnable Pi-mirror tests green, PLUS the
  single consolidated rig checkpoint above (`router_bind` smoke, `sub_connect` smoke, full
  lifecycle wiring, liveness→ES, egress-under-real-latency, lease-from-real-disconnect) confirmed
  by the user before `/gsd:verify-work`.

### Wave 0 Gaps

- [ ] `~/pi-mirror/tests/test_extlink_decoder.py` — new, `autopilot`-free, covers EXTLINK-14/08.
- [ ] `~/pi-mirror/tests/test_extlink_egress.py` — new, `autopilot`-free, covers EXTLINK-15.
- [ ] `~/pi-mirror/tests/test_extlink_lifecycle.py` — new, `autopilot`-free, covers EXTLINK-16.
- [ ] `~/pi-mirror/tests/test_extlink_liveness.py` — new, `autopilot`-free, covers EXTLINK-07.
- [ ] Extend `~/pi-mirror/tests/test_mics_task_attrs.py` — regression pin on `mics_task.end()` →
      `super().end()`, covers EXTLINK-16's chokepoint dependency.
- [ ] Extend `api/tests/test_toolkit_dispatch.py` — device lease tests, covers EXTLINK-17.
- [ ] Extend (confirm exact filename first — `grep -rl "class HardwareLib\|extract_ast_metadata" api/tests/`)
      the hardware-libs AST test file — covers EXTLINK-09.
- [ ] Framework install (agent-side, dev host only, NOT the Pi): `pip install msgpack` in whatever
      environment runs the new `autopilot`-free `tests/test_extlink_*.py` files — needed so the
      wire-codec tests can call `msgpack.packb`/`unpackb` directly rather than mocking them.
- [ ] Framework install (Pi, USER-RUN): `msgpack` pinned for Python 3.7.3 — see Open Question 3;
      resolve the exact version via a real `pip install` on the rig, don't hardcode a guess.
- [ ] Confirm whether `~/pi-mirror/scripts/dev/extlink_smoke.py` needs a `publish` subcommand added
      for the `sub_connect` rig checkpoint, or whether a separate throwaway script is cleaner —
      plan-time decision, not research.

## Sources

### Primary (HIGH confidence — direct code reads + live SSH, this session)
- `~/pi-mirror/autopilot/autopilot/networking/node.py` — full read, `Net_Node` ZMQStream/IOLoop pattern
- `~/pi-mirror/autopilot/autopilot/tasks/task.py` — full read of `__init__`, `init_hardware`, `execute_trigger`, `end`, `handle_trigger`, `process_queue`
- `~/pi-mirror/autopilot/autopilot/tasks/mics_task.py` (lines 1-330, 947-1485) — `__init__`, `_resolve_hardware_classes`, `_merge_prefs_hardware`, `check_for_detectors`, `end`
- `~/pi-mirror/autopilot/autopilot/core/pilot.py` (lines 565-688, 1121-1280) — `l_start`, `l_stop`, `l_update_fda`, `run_task` full teardown order
- `~/pi-mirror/autopilot/autopilot/core/View.py`, `~/pi-mirror/autopilot/autopilot/utils/Tracker.py` — full reads
- `~/pi-mirror/autopilot/autopilot/hardware/__init__.py` (lines 1-200) — `Hardware` base class, `release()` contract, `get_state()`
- `~/pi-mirror/autopilot/autopilot/hardware/timer.py` — full read, software-only hardware precedent
- `~/pi-mirror/autopilot/autopilot/networking/Event_Dispatcher.py` (lines 1-90) — sender thread/queue pattern, pigpio-tick clock requirement
- `~/pi-mirror/autopilot/autopilot/utils/logging_utils.py` — full read, `log_action` dispatch logic
- `~/pi-mirror/autopilot/autopilot/utils/FiniteDeterministicAutomaton.py` — full read
- `/home/ido/mics-backend/api/routers/toolkit_dispatch.py` (lines 1-360) — preflight issue system, dispatch-spec generation
- `/home/ido/mics-backend/api/routers/pilot_hardware_config.py` — full read
- `/home/ido/mics-backend/api/routers/hardware_libs.py` (lines 52-131) — `extract_ast_metadata`
- `/home/ido/mics-backend/orchestrator/orchestrator/orchestrator_station.py` (lines 231-490, 822-995) — `start_run`, `stop_run`, `on_task_error`, `_inject_backend_toolkit_spec`, `_send_hardware_libs_if_needed`, `_run_watchdog`, `_redis_touch`
- Live SSH (read-only) to the Pi: `~/.venv/autopilot` package check confirming `msgpack` is absent, pyzmq `23.0.0b1`, tornado `6.1`, Python `3.7.3`; `~/Apps/mice_interactive_home_cage/environment.yml` pins (`pyzmq==23.0.0b2`, `tornado==6.1`, `python=3.7.16`); `run_pilot.sh` venv-activation confirmation
- `/home/ido/mics-backend/.planning/phases/23-compute-primitives-variables/23-RESEARCH.md` — format/structure precedent for this document
- Dev-host import check (this session, addendum): `cd ~/pi-mirror/autopilot && python3 -c "import autopilot"` reproduces Phase 23's finding — fails on `ModuleNotFoundError: No module named 'npyscreen'` via `autopilot/__init__.py:4`'s unconditional `from autopilot.setup import setup_autopilot`; `msgpack` and `zmq` also confirmed absent from the dev host's Python — informs the Validation Architecture section's design-for-testability split

### Secondary (MEDIUM confidence)
- Tornado official docs (`tornado.ioloop` module docs, current stable) — `IOLoop.add_callback()` is the only thread-safe cross-thread entry point. Verified via WebSearch this session, cross-referenced against pyzmq's own eventloop-integration docs describing the identical pattern.
- msgpack PyPI page — current release requires Python ≥3.9; exact last-compatible-with-3.7 version not pinned by direct verification (flagged as Open Question 3, not asserted as fact).

### Tertiary (LOW confidence)
- None — every claim above was either verified by direct file read, live SSH, or a WebSearch cross-referenced against official docs.

## Metadata

**Confidence breakdown:**
- Standard stack (msgpack, pyzmq, tornado versions): HIGH — pinned by live SSH into the actual rig venv, not assumed.
- Architecture (IOLoop threading, egress pattern, lifecycle chokepoints): HIGH — every claim traced through actual code with line numbers, not inferred from the context doc's claims alone. Two of the context doc's own assumptions (msgpack transitivity, `_run_watchdog` availability) were found to be incorrect by this verification.
- Pitfalls: HIGH for the ones backed by direct code reads (IOLoop threading, event-dispatcher-stop ordering, `ast.literal_eval`); MEDIUM for the msgpack exact-version pin (needs a user-run `pip install` to confirm).
- Validation Architecture: HIGH — per-subsystem A/B split verified against actual dev-host import behavior (not assumed), the existing `Task.end()`/`release()` chokepoint, and the existing preflight issue-list extension point; the `event_dispatcher.stop()`-before-`release()` ordering is folded in as an explicit non-goal so no plan writes an untestable acceptance criterion.

**Research date:** 2026-08-03
**Valid until:** 30 days for the architecture findings (stable, verified against code that won't drift quickly); re-verify the msgpack version pin at planning time if more than a few days pass, since it depends on an action (Wave 0 pip install) not yet taken.
