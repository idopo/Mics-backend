---
phase: 19
slug: per-pilot-device-health-surface
created: 2026-08-05
method: direct source verification (the spawned researcher died at a session limit; every
  claim below was read out of the live tree rather than inferred)
---

# Phase 19 — Research

Every fact here was verified by reading the current source on 2026-08-05. Line numbers are from
that read. **Four findings change the obvious implementation** — read those first.

---

## Findings that change the plan

### F1 — `on_data` is the hook point, NOT `_handle_data`. The worker has no pilot identity.

```python
# orchestrator/orchestrator/orchestrator_station.py:239
def on_data(self, msg: Message):
    try:
        self.data_queue.put_nowait(copy.deepcopy(msg.value))   # <-- msg.sender DISCARDED
    except queue.Full:
        logger.warning("DATA queue full, dropping message")
```

`main.py:76` maps `CONTINUOUS` → `station.on_data`, which only enqueues. The draining worker is
`_data_worker` (`:516`) → `_handle_data` (`:526`), which begins:

```python
def _handle_data(self, value: dict):
    subject = value.get("subject")
    if not subject:
        return                      # <-- early return, no pilot anywhere in scope
```

So `_handle_data` sees **only `msg.value`**, whose identity field is `subject` (an ES run key like
`bp_s<session>_r<run_id>`) — **not a pilot name**. `OrchestratorState` is keyed by pilot. Mapping
subject → pilot would need `self.api.get_run_by_subject_key(...)`, an HTTP call, on the hot data
path. Unacceptable.

`Message` **does** carry `.sender` (`~/pi-mirror/autopilot/autopilot/networking/message.py:53`,
listed at `:18` as a required attribute). It is available in `on_data` and thrown away one line
later.

**Therefore: hook in `on_data`, before the enqueue.** It has the sender, it is O(1), and it leaves
the ES ingestion path completely untouched. The alternative — enqueuing `(sender, value)` tuples —
changes the queue contract, forces edits to `_data_worker` and `_handle_data`, and still has to
survive that early return. Reject it.

⚠ `on_data` runs on the **Tornado IOLoop thread** (RouterGateway), while `/pilots/live` is served
from the HTTP thread. This is exactly why HEALTH-01 insists on `self._lock`. Whatever is added to
`on_data` must be pure-memory and non-blocking — the same rule Phase 18 spent an entire blocker on
for its liveness poll.

### F2 — Clear `device_health` inside `set_active_run`, not at its call sites. There are eight.

`self.state.set_active_run(pilot_key, None)` appears at `orchestrator_station.py` lines **369, 429,
442, 477, 486, 611, 976** (plus the non-None set at `:390`). HEALTH-05 phrased as "clear it wherever
`active_run` is cleared" would mean touching seven sites and would silently rot the first time
someone adds an eighth.

**Do it in `state.set_active_run` itself:** when `run is None`, drop the pilot's `device_health` in
the same locked block. One place, all callers covered forever, and it is impossible for the two to
drift out of sync — which is the actual requirement.

### F3 — `web_ui/app.py` needs NO change. Confirmed, not assumed.

```python
# web_ui/app.py:49  @app.websocket("/ws/pilots")
resp = await client.get(f"{ORCHESTRATOR_URL}/pilots/live", timeout=2.0)
resp.raise_for_status()
if not await safe_send(resp.json()):     # <-- forwards VERBATIM, no reshaping
    break
...
await asyncio.sleep(0.5)                 # :89 — poll cadence
```

A new key in `snapshot()` reaches the browser untouched. `GET /api/pilots` (`:39`) forwards the same
response, so it inherits the field too. **Poll cadence is 0.5 s.**

### F4 — `web_ui/react-src/src/style.css` DOES NOT EXIST. CLAUDE.md is wrong on this point.

There is no `.css` file anywhere under `web_ui/react-src/src/`. The React app is styled by
**`web_ui/static/style.css`**, linked from `web_ui/templates/react/index.html:7`:
`<link rel="stylesheet" href="/static/style.css">`.

CLAUDE.md's rule ("Use classes from `web_ui/react-src/src/style.css`. Do not invent new class
names.") is right in spirit, wrong in path. **The rule still binds — just against
`web_ui/static/style.css`.** Worth fixing in CLAUDE.md separately; do not fix it inside this phase.

**Two existing classes are an exact fit and must be reused rather than invented:**

| Class | Why it fits |
|---|---|
| `.state-warning-badge` | already the app's vocabulary for "something is wrong but not fatal" |
| `.state-warning-tooltip` | pairs with it; carries the detail (which device, since when) |

Full relevant inventory, verified present: `.pilot-card`, `.pilot-card-header`, `.pilot-run-info`,
`.pilot-run-grid`, `.pilot-status-dot`, `.pilot-offline`, `.pilot-offline-badge`, `.pilot-idle`,
`.pilot-running`, `.dot-idle`, `.dot-running`, `.dot-offline`, `.status`, `.status-error`,
`.status-running`, `.badge`, `.error`, `.icon-danger`.

---

## Answers to the remaining questions

**WS hook semantics — replace, not merge.** `hooks/useWebSocket.ts` does
`setLastMessage(JSON.parse(ev.data) as T)` — the whole payload is replaced every message. That is
**fine here and needs no change**, because `alive` is a *level* held in Phase 18's `LivenessPoller`
cache, not an edge. Every 0.5 s poll re-reports the current value, so the warning persists as long
as the condition does. A consumer must not try to reconstruct edges from these snapshots.

**`PilotCard` is a function inside `pages/index/Index.tsx`** (129 lines), not a separate module —
`function PilotCard({ name, info }: { name: string; info: PilotLive })` at `:33`. It already
computes `connected` (`:35`), `isRunning` (`:36`), `run` (`:37`), `cardClass` (`:40`), `dotClass`
(`:45`). Adding the affordance keeps the file well under the 300-line limit; do **not** extract a
new component.

**`PilotLive`** (`types/index.ts:1`) is currently `{ connected, state, active_run, updated_at }`.
Note `snapshot()` also emits `last_seen_sec` and `ip`, which the TS type does not declare — the type
is already a partial view of the payload, so adding one optional field is consistent with existing
practice.

**Existing external-device UI: none.** `grep -rln "extlink|external_device|source_id"
web_ui/react-src/src` returns nothing. This phase builds the first one.

**Phase 18's demo device.** `18-12-PLAN.md` builds `DemoControl` (`role: "none"`), registers
`oe_ctl.alive`, and already contains a step that kills the source and confirms `alive` flips to
`false` (`:291-292`, `:307`). Phase 19's rig check is therefore an *extension of an existing step*,
not a new rig session — but note **Phase 18 is planned and verified, not executed**, so that demo
does not exist yet.

---

## Validation Architecture

The orchestrator runs under docker compose, so the agent can rebuild and `exec` into it — that is
the fast loop and it covers HEALTH-01, HEALTH-02 and HEALTH-05 completely, because
`OrchestratorState` is a plain in-memory class with **no ZMQ, no Redis and no network** in its
constructor. Import it directly and assert.

| Requirement | How | Runner | Loop |
|---|---|---|---|
| HEALTH-01 | Import `OrchestratorState`, set/read `device_health`, assert `snapshot()` defaults to `{}` not `None` | agent, `docker compose exec orchestrator python -c ...` | ~30 s (rebuild) |
| HEALTH-02 | Call `on_data` with a fabricated `Message` carrying `.sender` and a `*.alive` value; assert the state updated AND the value still reached `data_queue` (ES path unbroken). Also assert a **non**-`.alive` tracker does not touch health, and that a **second, non-OE** device name lands — the device-neutrality proof | agent, same | ~30 s |
| HEALTH-03 | `curl` the orchestrator's `/pilots/live` and assert the key is present; read `web_ui/app.py` and assert the forward is still verbatim (a source-level guard, since a future reshape would silently break it) | agent | ~30 s |
| HEALTH-04 | `cd web_ui/react-src && npx tsc --noEmit` for the type change; `npm run build` for the render. Visual confirmation is browser-only | agent (build), USER (visual) | ~60 s |
| HEALTH-05 | Assert `set_active_run(pilot, None)` clears `device_health` in the same call — and assert it via `set_active_run`, never by counting call sites | agent | ~30 s |
| HEALTH-06 | Source-level: assert nothing in the phase's diff calls a stop/abort path. A grep guard, since the requirement is an absence | agent | instant |
| End-to-end | Real pilot, real device going away, card changes without reload | **USER-RUN / rig** | rig session |

**Device-neutrality guard (mirror Phase 26's precedent):** a test asserting the orchestrator changes
contain no device class name — matching is on the `.alive` suffix only. Phase 26 enforces exactly
this with source greps (`test_device_neutral_layer`); reuse the pattern so a future device needs no
orchestrator edit.

**Rig work folds into Phase 18's existing 18-12 kill-the-source step** rather than booking a second
session — but Phase 18 must execute first.

**No automated test suite exists for `api/` or `web_ui/`** (CLAUDE.md). Orchestrator assertions are
therefore inline `python -c` in `<automated>` blocks, which is what Phases 18 and 26 already do.

---

## Constraints carried in

- **Pi rules (CLAUDE.md, hard):** never run git on the Pi, never start/stop the pilot process, never
  run Python on the Pi. Rig steps are USER-RUN checkpoints. This phase touches no Pi code at all.
- **File sizes:** `orchestrator_station.py` is ~1000+ lines already — this phase adds only a few
  lines to `on_data`; put nothing else there. `state.py` is small and is the right home for the
  health map.
- **React:** Nav lives in `Layout.tsx`; `Nav.tsx` is dead code. Not relevant here — no new route.
- **Do not invent CSS class names.** Use `.state-warning-badge` / `.state-warning-tooltip` from
  `web_ui/static/style.css` (see F4 for the corrected path).
