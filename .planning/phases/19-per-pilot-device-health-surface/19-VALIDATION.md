---
phase: 19
slug: per-pilot-device-health-surface
status: approved
nyquist_compliant: true
wave_0_complete: false
created: 2026-08-05
---

# Phase 19 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.
> Derived from `19-RESEARCH.md` § Validation Architecture. Read that section for rationale.

---

## Test Infrastructure

| Property | Value |
|---|---|
| **Framework (orchestrator)** | plain `assert` script + host `python3` — `orchestrator/tests/` already exists and is run by **host** pytest 3.12 |
| **Framework (frontend)** | `node --test` for the pure module; `npx tsc --noEmit` + `npm run build` for the rest |
| **Runner (orchestrator logic)** | **HOST**, not the container — `orchestrator/Dockerfile:8` copies only the package, so `orchestrator/tests/` is **not in the image**. `state.py` imports only `time`/`threading`/`typing`, so it needs none of the orchestrator's deps |
| **Runner (integration)** | `docker compose exec -T orchestrator` / `curl` against the live stack |
| **Feedback latency** | ~2 s host logic · ~40 s orchestrator rebuild · ~60 s Vite build |

**No automated test suite exists for `api/` or `web_ui/`** (CLAUDE.md). Inline `python -c` assertions
in `<automated>` blocks are the established pattern — Phases 18 and 26 both do this.

---

## Per-Requirement Verification Map

| Req | What is proven | Type | Command | File exists |
|---|---|---|---|---|
| HEALTH-01 | `device_health` under the existing `RLock`; `snapshot()` and `get_device_health` default to `{}` **never `None`**; the HTTP thread can serialise while the IOLoop writes | unit (host) | `python3 -m orchestrator.tests.test_device_health` | ❌ 19-01 |
| HEALTH-02 | a `*.alive` CONTINUOUS write lands in state **and** the value still reaches `data_queue` (ES path unbroken); a non-`.alive` tracker does not touch health; the value parses as **int `0`/`1`**, not bool | unit + integration | same, plus `docker compose exec -T orchestrator python -c ...` | ❌ 19-01 |
| HEALTH-02 (neutrality) | a never-before-seen device (`dlc_cam1.alive`) records identically, **and** `inspect.getsource` over `parse_alive_event` + `on_data` contains no device class name — matching is `str.endswith(ALIVE_TRACKER_SUFFIX)` only | source guard | `-k` grep inside the same `python -c` | ❌ 19-01 |
| HEALTH-03 | `/pilots/live` carries the key (**merged in `api.py`, not `snapshot()` — see the F3 correction**), and `web_ui/app.py` still forwards verbatim | integration + source guard | `curl localhost:9000/pilots/live`, `curl localhost:8080/api/pilots` | ❌ 19-01 / 19-02 |
| HEALTH-04 | `PilotLive.device_health` typechecks; the badge renders; only **existing** classes `.state-warning-badge` / `.state-warning-tooltip` from `web_ui/static/style.css` are used | typecheck + build + browser | `npx tsc --noEmit`, `npm run build`, then USER | ❌ 19-02 |
| HEALTH-05 | `set_active_run` drops health in the same locked block — asserted **through the method**, never by counting its eight call sites | unit (host) | `python3 -m orchestrator.tests.test_device_health` | ❌ 19-01 |
| HEALTH-06 | **absence**: nothing added calls a stop/abort path — grep guards over the two orchestrator functions, over `deviceHealth.mts`, and `grep -cE '/stop\|abort' Index.tsx -eq 1` (exactly 1 today: the pre-existing STOP button, so the guard is live not vacuous) | source guard | inline greps | ❌ 19-01 / 19-02 |
| End-to-end | probe DEALER → `on_data` → state → `/pilots/live` → proxy → WS → card, **with no Pi and no device** | integration + browser | `19-03` `dev_health_probe` | ❌ 19-03 |
| Real device | a genuine `<source_id>.alive` flip from real hardware | **USER-RUN / rig** | folds into Phase 18's `18-12` kill-the-source step | N/A |

*Status: ⬜ pending · ✅ green · ❌ red (not yet written) · ⚠️ flaky*

---

## Sampling Notes

**The rig is off the critical path.** Roadmap criterion 6 does not need a booked session. The inbound
wire format is one JSON frame from a `zmq.DEALER` with `IDENTITY = <pilot_key>`, and `/pilots/live`'s
notion of a connected pilot is one Redis hash — so `19-03`'s probe drives the entire chain and cleans
up its own Redis key on exit. The real-device confirmation becomes a five-second addition to the next
device-bearing run, hosted by Phase 18's `18-12`.

**Phase 18 is planned and verified but NOT executed.** No plan here may assume its code is on disk.

**Two environmental caveats, so a red result is diagnosed rather than chased:**
- The `redis` service has **no volume**. Any `docker compose down` empties it, after which the
  `/pilots/live` assertions fail until a pilot pings or `19-03`'s probe seeds its own key.
- `Boolean_Tracker.set` is `@log_action`-decorated *and* calls an `@log_action`-decorated
  `super().set`, so one flip emits the same event **twice**. Idempotent (the second write is a no-op)
  but expect it in the logs.

---

## Sign-off

- [x] Every ❌ row has a Wave-0-or-earlier creator plan
- [x] Every manual row is justified and hosted by an existing checkpoint
- [x] Feedback latency stated honestly (rebuild cost not hidden)
- [x] Device-neutrality proven mechanically, not by review
- [x] `nyquist_compliant: true` set in frontmatter
- [ ] `wave_0_complete` — cannot be ticked; nothing has executed

**Approval:** approved 2026-08-05, after plan-checker VERIFICATION PASSED and the advisory fixes in
`21053a6`.
