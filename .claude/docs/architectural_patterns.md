# Architectural Patterns

Patterns that appear in multiple files or cross service boundaries.

---

## 1. Dual ORM on a shared engine

**Where:** `api/models.py` (whole file), `api/main.py:96-102`, `api/main.py:44-45`

SQLModel manages newer tables (`subjects`, `protocol_templates`, `protocol_step_templates`, `subject_protocol_runs`). Plain SQLAlchemy (`declarative_base`) manages older tables (`pilots`, `sessions`, `session_runs`, `run_progress`, `task_definitions`). Both have `metadata.create_all()` called at startup. Routes use the matching session type: `SQLModelSession` via `Depends(get_session)` for SQLModel tables, `SA_SessionLocal()` directly for SQLAlchemy tables.

**Why:** SQLModel was introduced for the subjects/protocols domain without migrating the existing pilot/session schema. Mixing them avoids a risky all-at-once migration. Contributors must know which ORM owns each table.

---

## 2. Authenticated reverse proxy in web_ui

**Where:** `web_ui/app.py:17,22-28` (token loading), `web_ui/app.py:99` (httpx client), `web_ui/app.py:273` (orchestrator, unauthenticated)

Every web_ui route constructs an `httpx.AsyncClient` with a static Bearer token from `MICS_API_TOKEN`. The UI itself does not handle user login — it relies on this server-side credential. Two downstream targets: `http://host.docker.internal:8000` (api, authenticated) and `http://host.docker.internal:9000` (orchestrator, unauthenticated).

**Why:** Browser clients should not hold API tokens. The web_ui acts as a trusted intermediary so the token never leaves the server-side container.

---

## 3. ZMQ message handler registration

**Where:** `orchestrator/orchestrator/main.py:71-80`, `orchestrator/orchestrator/RouterGateway.py:43-44`

`RouterGateway` holds a `listens` dict mapping string message keys (`"HANDSHAKE"`, `"STATE"`, `"DATA"`, etc.) to callables. At startup, `main.py` populates this dict with methods from `OrchestratorStation`. `"CONTINUOUS"` and `"STREAM"` share the same `on_data` handler.

**Why:** Decouples transport (RouterGateway) from business logic (OrchestratorStation). New message types require only one line in `main.py`.

---

## 4. Bounded queues with dedicated worker threads for high-volume events

**Where:** `orchestrator/orchestrator/orchestrator_station.py:49-55`, `:400-431`

`OrchestratorStation.__init__` creates two `queue.Queue(maxsize=50_000)` instances (`data_queue`, `trial_queue`). Four daemon threads consume `data_queue` (`_data_worker`); one thread consumes `trial_queue` (`_trial_worker`). ZMQ message handlers put items into queues and return immediately.

**Why:** ZMQ messages arrive on the IOLoop thread. Blocking it with ES writes or API calls would stall all incoming messages. The queue decouples receipt from processing; a full queue raises `queue.Full` rather than silently consuming memory. A single trial worker serialises increments to prevent races.

---

## 5. Redis as the live pilot state bus

**Where:** `orchestrator/orchestrator/orchestrator_station.py:99-140` (`_redis_set_active_run`), `:682-693` (`_redis_touch`), `orchestrator/orchestrator/api.py:24-57` (`list_live_pilots`), `web_ui/app.py:48-92` (WebSocket loop)

Every significant pilot event writes a hash to Redis under `pilot:{pilot_key}` (fields: `state`, `active_run` JSON, `updated_at`). The orchestrator REST endpoint `/pilots/live` reads exclusively from Redis. The web_ui WebSocket polls this endpoint every 1 second and pushes the result to the browser.

**Why:** Redis acts as a shared state store that survives orchestrator restarts. The 15-second staleness check (`orchestrator/orchestrator/api.py:6,39`) converts a timestamp into a `connected` boolean, hiding clock-skew from callers.

---

## 6. JS module-level cache + in-flight deduplication

**Where:** `web_ui/static/pilot_sessions.js:753-797`, `web_ui/static/session_overrides_modal.js:46-54`

For each resource type (session detail, protocol, latest run), a plain-object or Map cache is keyed by ID, with a parallel `*_INFLIGHT` Map holding the in-progress Promise. Fetch helpers follow: return from cache → return in-flight Promise → create new fetch, store in INFLIGHT, populate cache on resolve, delete from INFLIGHT in `.finally()`.

**Why:** Without deduplication, scrolling quickly could launch dozens of concurrent fetches for the same protocol. The INFLIGHT map means the second caller joins the existing Promise. This pairs with the concurrency limiter (pattern 7).

---

## 7. Concurrency limiter for outbound fetches

**Where:** `web_ui/static/pilot_sessions.js:693-713`, `:757,772,788`

`createLimiter(max)` returns a function that wraps async `fn` in a queue bounded to `max` (4) concurrent executions. All cached fetch helpers use this limiter.

**Why:** Without a limiter, hydrating 50 session cards simultaneously would queue hundreds of requests and potentially time out the web_ui proxy.

---

## 8. Lazy hydration via IntersectionObserver

**Where:** `web_ui/static/pilot_sessions.js:1152-1232`

`renderShellList` renders all session cards as lightweight skeleton `<li>` elements (no API calls) and registers each with an `IntersectionObserver` (`rootMargin: "600px 0px"`). When a card enters the lookahead zone, `hydrateCard` fires API calls and populates it. The observer is unregistered after first hydration (`io.unobserve(li)`, line 1158).

**Why:** A pilot may have hundreds of sessions. Skeleton rendering gives immediate visual feedback. The 600px lookahead means cards are ready before the user scrolls to them.

---

## 9. Override layering: global + per-step

**Where:** `web_ui/static/session_overrides_modal.js` (draft UI), `web_ui/app.py:252,260` (forwarded in payload), `api/models.py:222,250` (`SessionRun.overrides`, `SessionRunCreate.overrides`), `orchestrator/orchestrator/orchestrator_station.py:372-381` (`_apply_overrides`)

`overrides` is structured as `{ "global": { param: value }, "steps": { "0": { param: value } } }`, stored as JSON on the `SessionRun` row. The orchestrator applies global overrides first, then step-specific ones (step values win).

**Why:** Researchers adjust parameters for a single run without changing the protocol template. Storing overrides on the run row makes configuration auditable.

---

## 10. Run mode semantics (NEW / RESUME / RESTART)

**Where:** `api/main.py:634-730` (`create_session_run`), `api/models.py:221,245-250`

`SessionRunCreate.mode` accepts `"new"`, `"resume"`, or `"restart"`. `"new"` creates a fresh row at progress zero. `"resume"` reactivates the most recent STOPPED/ERROR row in place, preserving its progress. `"restart"` creates a new row but copies the `session_run_index`, recording a new attempt at the same logical position.

**Why:** Hardware experiments fail mid-run. Resume continues from the stopped point. Restart records a fresh attempt without losing prior run history. New is unambiguous: no prior state consulted.

---

## 11. Pi task state machine (FDA + View + wait_for_condition)

**Where:** `~/pi-mirror/autopilot/autopilot/utils/FiniteDeterministicAutomaton.py`, `autopilot/core/View.py`, `autopilot/tasks/mics_task.py`, `autopilot/tasks/task.py`

Every Pi task (`mics_task` subclass) uses a `FiniteDeterministicAutomaton` as `self.stages`. States are task methods. Transitions are `(from, to, [lambda_list])` where all lambdas must be true to fire. Empty lambda list = unconditional. `wait_for_condition()` is a generator that keeps yielding until one of the current state's transitions fires; stage methods return it so `pilot.py`'s `run_task` loop blocks until the hardware condition is met.

`self.view` is the observable state surface: `view.get_value(name)` reads hardware or tracker state. All FDA transition lambdas use `self.view`. Hardware objects and Trackers are both registered in `view.view[name]`.

**Why:** Separates state machine structure (declared in `__init__`) from logic (state methods). Transition conditions are pure boolean expressions on view state, making the flow readable as a graph. `wait_for_condition()` lets stage methods block without spinning — the generator yields on each loop iteration until a transition guard is true.

---

## 12. Auto-logging via @log_action decorator

**Where:** `~/pi-mirror/autopilot/autopilot/utils/logging_utils.py`, all `Hardware` and `Mics_Tracker` subclasses

`@log_action` wraps any `Hardware` or `Tracker` method. For Hardware: computes new `hardware_state` → runs method → dispatches `Hardware_Event`. For Trackers: runs method → dispatches `Event`. All go through `Event_Dispatcher.dispatch_event()` → `node.send('T', 'CONTINUOUS', data)` → orchestrator's `on_data` handler → ElasticSearch.

Every event envelope includes: `{pilot, subject, session, run_id, task_type, timestamp, continuous, session_progress_index, subjects, event: {event_type, event_data, [level]}}`. Timestamp is from `pi.ticks_to_timestamp(pi.get_current_tick())` — hardware-accurate pigpio ticks.

`INC_TRIAL_COUNTER` is NOT sent automatically. Tasks must call `self.event_dispatcher.dispatch_event(event, key="INC_TRIAL_COUNTER")` explicitly. This triggers `_handle_inc_trial` in orchestrator → API trial increment → possible graduation/step advance.

**Why:** Every hardware action is recorded in ES without task code needing explicit logging calls. The decorator pattern keeps task logic clean while ensuring full auditability of every valve open, lick, IR beam, timer, and tracker change.

---

## 13. HANDSHAKE task discovery

**Where:** `~/pi-mirror/autopilot/autopilot/core/pilot.py:394-431` (`discover_tasks_metadata`, `handshake`), `orchestrator/orchestrator/orchestrator_station.py:69-95` (`on_handshake`), `api/main.py` (`upsert_pilot_tasks`)

On startup (and reconnect), `Pilot.handshake()` scans all plugin classes via `autopilot.get_task()`, extracts `PARAMS` dict + `__init__` signature defaults, and sends the full list in the `HANDSHAKE` payload. The orchestrator forwards this to the API via `upsert_pilot_tasks()`, which populates the `task_definitions` table — powering the task palette in the web UI.

Each task entry: `{task_name, base_class, module, params: {key: {tag, type, default}}, hardware, file_hash}`.

**Why:** Task discovery is code-driven — adding a plugin file on the Pi automatically registers the task in the DB on next handshake. No manual registration needed.

---

## 14. Soft-delete via `is_hidden` flag

**Where:** `api/models.py` (`Researcher.is_hidden`, `IACUCProtocol.is_hidden`), `api/main.py` (`GET /researchers`, `GET /iacuc`, `PATCH /researchers/{id}/hide`, `PATCH /iacuc/{id}/hide`), `api/db.py` (`run_lab_column_migrations`)

Records are never hard-deleted from the DB. `PATCH /{resource}/{id}/hide` sets `is_hidden = True`. List endpoints filter `WHERE is_hidden = FALSE` by default; pass `?include_hidden=true` to see all. The column is added to existing DBs by `run_lab_column_migrations` (called at startup, `ALTER TABLE … ADD COLUMN IF NOT EXISTS … DEFAULT FALSE`).

**Why:** Researchers and IACUC protocols may be foreign-keyed from subjects and projects. Hard deletion would break referential integrity. Soft-hiding removes them from UI dropdowns and lists while preserving the linked historical records. `DEFAULT FALSE` in the DDL ensures no backfill UPDATE is needed for pre-existing rows.
