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
