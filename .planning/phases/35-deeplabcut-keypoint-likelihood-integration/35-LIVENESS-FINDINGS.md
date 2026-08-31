# Liveness Findings — DLC-06, the OFFLINE half of the Phase 34 liveness debt

Plan 35-02 (autonomous, no rig access). Everything here is authored offline; nothing is uploaded,
repinned or run on the rig by this plan. Plan **35-09** owns every write and fills in the empty
results table at the end of this document.

## 1. Phase 34 observation B — verdict, verbatim, and why it blocks DLC-06

From `34-HARDWARE-VALIDATION.md` §3d ("B — Quiet: INCONCLUSIVE, and not fixable at the rig"):

> `demo.alive` was emitted exactly **twice, both at t=0.06s**, and never again across 210 seconds.
> It is logged on change only, so silence is consistent with "stayed true" — but the evidence is
> worthless here, because hardware lib 177 v2 hardcodes it:
>
> ```python
> def liveness_hook(self, last_msg_ts_ms, now_ms, stale_ms):
>     """DIAGNOSTIC OVERRIDE (v2). ... Returning True unconditionally isolates the fault"""
>     return True
> ```
>
> `alive` would read true with the sender switched off entirely, so this proves nothing about the
> SDK's heartbeat. **SDK-05 is unproven on hardware.**

`demo.alive`'s value is disconnected from every input while the override is in place. **DLC-06
cannot be satisfied on top of an unproven SDK-05** — there is no way to distinguish "the sender's
heartbeat is really being tracked" from "the hook always answers `True` regardless of input" until
the override is gone and a correct hook stands in its place.

## 2. The TIMELINE — verified this session, re-confirmed against live sources

| When (UTC) | What | Source | Verified |
|---|---|---|---|
| **2026-08-09 10:09:02.928679** | `hardware_lib_versions` id **132** — lib 177 **v1**, no `def liveness_hook` at all | `GET /api/hardware-libs/177/versions`, this session | `created_at` field read directly from the live API response |
| **2026-08-09 11:12:07.166434** | `hardware_lib_versions` id **137** — lib 177 **v2**, carries `DIAGNOSTIC OVERRIDE` and `def liveness_hook`. **1h 3m after v1.** | same endpoint | same |
| **2026-08-09 11:15:24 2026** | `egress_listener.py`, PID **3086567**, started on `132.77.73.125` (this host, `ido-server`) | `ps -o lstart= -p 3086567` on `ido-server`, this session | Process is CURRENTLY RUNNING, started at this exact timestamp — **3m17s after v2 was created** |
| **2026-08-19 08:42:45 +0000** | `cf1a0229dd39f8fb5a8c8e761acf7a2cd1a2aaf5` — the `mics_core` repo's **FIRST commit** (`feat(31-05...`) | `git log --reverse` in `/home/ido/mics_core`, this session | Read-only local repo, not the Pi |
| **2026-08-24 09:14:00 +0000** | `1f35782cd704d8f7ce3efa9bd4d5aaa950f1b1cd feat(31-10): every remaining record timestamp onto the one clock (Task 2)` — **this is when the cross-clock subtraction was created** | `git show -s` on `1f35782` in `/home/ido/mics_core`, this session | same |
| 2026-08-30 | Phase 34 runs 582/583/584; observation B INCONCLUSIVE | `34-HARDWARE-VALIDATION.md` §3d | already on file |

**All five readings hold as claimed.** The conclusion this forces: **the override (11:12:07 on
2026-08-09) predates the cross-clock subtraction (`1f35782`, 2026-08-24) by 15 days, and predates
the entire `mics_core` tree (first commit 2026-08-19) by 10 days.** The override's docstring
therefore **cannot** be evidence for the clock diagnosis — whatever the override was written to
hide, it was hidden before the `mics_core` tree, and the code the clock bug lives in, existed at
all. Wherever the override's docstring is quoted below, this is restated: **it is never used as
evidence for Defect B.**

---

## 2a. DEFECT A — the original liveness fault. UNDIAGNOSED. No cause is claimed.

**When:** 2026-08-09, Phase 18, **pilot 1 (`132.77.72.28`), the `pi-mirror` stack.**

**Symptom, quoted from the override's own docstring** (`hardware_lib_versions` id 137,
`liveness_hook`): *"default_liveness reported not-alive while `on_recv` was demonstrably stamping
`_last_msg_ts_ms`, stranding the readiness gate in 2 of 4 rig runs."*

Phase 18's demo ran on `pilot 1 / pi-mirror`, where `external_hardware_ingress.py` stamps
`int(time.time() * 1000)` (verified: `/home/ido/pi-mirror/autopilot/autopilot/hardware/
external_hardware_ingress.py:15`) — the **same** clock source `external_hardware_binding.py`'s
`_now_ms()` uses. Both sides of the liveness subtraction are `time.time()` there, so **Defect B is
structurally impossible on that run** — see the discriminator in §3. This symptom is Defect A, and
the dates in §2 refute using Defect B's mechanism to explain it.

### Ranked candidates

**A1 — the egress probe, not liveness at all. CONFIRMED BY DESIGN DOCUMENTATION AND TIMELINE.
NOT REPRODUCED EXPERIMENTALLY** — corroborated, not demonstrated, and that distinction is not
collapsed anywhere in this document.

`recompute_alive` (`external_hardware_binding.py:136-143`) is
`liveness_alive and not owner._egress_failed` — a failing OUTBOUND probe drags `alive` false with
inbound traffic arriving normally. `bind_egress` (`external_hardware_binding.py:102-110`) always
builds an `EgressWorker`; `_on_egress_alive_change` (`:131-133`) is the sole writer of
`_egress_failed`. `ExtlinkDemo`'s `_egress_probe` targets `self.host:_EGRESS_PORT` —
`132.77.73.125:5597` for pilot 3's config row (verified live: `GET
/api/pilots/3/hardware-config`, config `id=33`, `host: "132.77.73.125"`, `egress_fail_threshold:
3`, `stale_ms: 3000`). With that TCP listener down, three consecutive failures trip
`egress_fail_threshold: 3` and `alive` flips false a few seconds into a run. `is_ready()` defaults
to `self._alive`, so the same conjunction gates run start — precisely the *"stranding the
readiness gate"* half of the docstring. "2 of 4 runs" matches an intermittently-available listener
better than a code defect, which would be all four.

**The two pieces of evidence that raise this from "strongest candidate" to "confirmed by
documentation":**

1. **Lib 177's own module docstring documents this exact failure mode as expected behaviour**,
   read live from the current `hardware_lib_versions` source (`GET /api/hardware-libs/177`):
   *"`on_run_start`/`on_run_stop`/`_egress_probe` exist so outbound traffic (EXTLINK-15) has
   something to observe — nothing else here ever calls `self.send()`. Every 1s for the run's
   duration one zero-arg callable is enqueued that opens a TCP connection to
   `self.host:_EGRESS_PORT` and waits up to 5s for a byte back.... point it at a closed port to
   make it fail fast (**quick `alive` flip**, no queue buildup)."* The author documented "point it
   at a closed port -> quick `alive` flip" as a KNOWN behaviour of this fixture — the same file
   that carries the override describes the symptom in advance.
2. **The timeline closes it.** `egress_listener.py`, PID 3086567, on `132.77.73.125` (this host,
   confirmed by `hostname -I` this session), is **STILL RUNNING**, started `Sun Aug 9 11:15:24
   2026` — **3m17s after** lib 177 v2 (the override) was created at 11:12:07.166434, and 66 minutes
   after v1 at 10:09:02.928679. The sequence reads without gaps: the fixture probed a closed
   `.125:5597` -> the documented "quick `alive` flip" -> not-alive with data demonstrably arriving
   -> `liveness_hook` hardcoded `True` at 11:12 -> the listener started at 11:15 to satisfy the
   probe -> up ever since (22 days as of this session), **which is why the fault never recurred.**

**What this means for the override:** it was never masking a substrate bug. It was masking a
dependency on a throwaway script that had not been started yet. Removing it is therefore expected
to be safe **as long as 5597 is up** — which is exactly why plan 35-09 checks that first.

**The direct test — would move A1 from corroborated to demonstrated. NOT SCHEDULED BY THIS PHASE.
Needs no DLC, no vision box and no model:**

1. Confirm `132.77.73.125:5597` is UP and start a run on the `extlink_demo` fixture with a sender
   streaming. Confirm `demo.alive` is true.
2. **Deliberately stop the listener on 5597** while the sender keeps streaming.
3. Observe whether `demo.alive` goes false within roughly `egress_fail_threshold` (3) probe
   intervals while `left_paw_x` documents keep arriving in Elasticsearch — i.e. `on_recv` is
   demonstrably still stamping.
4. Restart the listener and observe whether `demo.alive` recovers (`_on_egress_alive_change`
   clears the failure state and fires the change back).

If step 3 reproduces "not-alive while `on_recv` is demonstrably stamping", A1 moves from
documented-and-corroborated to **demonstrated**, and Defect A is closed. If it does NOT reproduce,
that is a genuine surprise given the docstring and the timeline, and A2/A3 return.

This test is **not scheduled by this phase** — stopping the listener affects every run on every
pilot whose `demo` row is on the path (this session's live check shows **two** pilots share the
`demo` source_id: pilot 3 `RecordingBox` and pilot 1 `pilot_raspberry_lior`, per
`GET /api/toolkits/100`'s `extlink_signals.by_pilot`), so it is not something to do casually
mid-session. Plan 35-09's checkpoint requires only that 5597 is confirmed UP before any
observation — the defensive half.

**The demo fixture's dependency on `.125:5597` is DELIBERATE AND CORRECT — it is not a defect to
fix.** Its stated purpose is to give EXTLINK-15's outbound path something to observe, and it does
that job. Two pilots' `demo` rows depend on that listener staying up. **The only defect here is the
un-removed override**, which turned a working fixture into a silent liar about liveness. Do not
"fix" the probe, do not repoint `host`, and do not stop the listener as a cleanup.

**Until then: confirm 5597 is open before drawing any conclusion from any run in this plan or in
35-09.**

- **A2 — poller cadence.** `bind_liveness` (`external_hardware_binding.py:73-83`) sets
  `interval_s = (stale_ms / 2) / 1000`, so with `stale_ms: 3000` (pilot 3's demo config, confirmed
  live) the predicate is evaluated every 1.5s and a false reading can persist that long after the
  fact. This affects the TIMING of an observation, not its truth value — it can explain a gate
  that looked stranded briefly, not one that stayed stranded.
- **A3 — something not yet enumerated.** Held open deliberately. Two of four runs failing is a
  race, a startup ordering or an environment difference, and the honest position is that we have
  not found it. **Do not close A by elimination.**

---

## 2b. DEFECT B — the cross-clock subtraction. VERIFIED IN SOURCE. Not the reason the override exists.

**When:** 2026-08-24, Phase 31 Plan 10, `mics_core` only. **Current on pilot 3.**

Five readings, each re-confirmed against the file this session:

1. `mics_core/autopilot/autopilot/hardware/external_hardware_binding.py:19` `_now_ms()` returns
   `int(time.time() * 1000)` (`:25`), and its comment (`:20-23`) says it is *"deliberately NOT
   converted through the one clock"* and claims *"Phase 31 Plan 10's F7 exempts this site by
   name"* (`:22`).

   **That claim is FALSE (D-49), verified against the shipped guard,
   `mics_core/tools/tree_integrity/final_checks.py`:**
   - `F7_CLOSURE` (`final_checks.py:227-236`) is **nine files** —
     `autopilot/autopilot/tasks/mics_task.py`, `.../tasks/task.py`, `.../hardware/gpio.py`,
     `.../hardware/i2c.py`, `.../hardware/timer.py`, `.../hardware/external_hardware_ingress.py`,
     `.../utils/logging_utils.py`, `.../utils/common.py`, `.../networking/Event_Dispatcher.py` —
     and **`external_hardware_binding.py` is NOT among them.**
   - `F7_EXEMPTIONS` (`final_checks.py:246-256`) has **exactly one** entry: `path` =
     `autopilot/autopilot/hardware/external_hardware_ingress.py`, `forms` = `("time.time(",)` —
     the **ingress** `ClockNotReady`/`ClockFault` fallback, **not** binding's `_now_ms()`.
   - The checker itself, `f7_one_clock` (`final_checks.py:294-323`), only walks files IN
     `F7_CLOSURE`: `for rel in F7_CLOSURE: ... for node in ast.walk(tree): if not
     isinstance(node, ast.Call): continue` (`:303-313`) — a file outside the closure is never
     opened by this function at all.

   **Being OUTSIDE a closure is not the same as being EXEMPTED BY NAME**: the first means
   unexamined, the second means examined and permitted. **This claim is cited here as a claim that
   was checked and found inaccurate — never as design rationale.**
2. `_liveness_tick(owner, pred)` (`external_hardware_binding.py:85-90`) calls
   `pred(owner._last_msg_ts_ms, now_ms, owner.stale_ms)` with that `time.time()`-derived `now_ms`
   (line 88: `now_ms = _now_ms()`).
3. `mics_core/autopilot/autopilot/hardware/external_hardware_wire.py:163-167`
   `default_liveness(last_msg_ts_ms, now_ms, stale_ms)` returns
   `(now_ms - last_msg_ts_ms) < stale_ms` — a bare subtraction of the two.
4. `mics_core/autopilot/autopilot/hardware/external_hardware_ingress.py` `on_recv` (`:76-101`) sets
   `owner._last_msg_ts_ms = ts_ms` (`:81`) where `ts_ms` comes from `_now_ms_and_mono_ns()`
   (`:38-58`): `clock.now_from_tick()` (`clock.py:336`, the pigpio-tick fitted mapping) converted by
   `clock.to_utc_ns()` (`clock.py:390-391`: `int(t_mono_ns) + self._epoch_offset_ns()`). That is the
   ONE CLOCK, not `time.time()`.
5. `/home/ido/pi-mirror/autopilot/autopilot/hardware/external_hardware_ingress.py:15` stamps
   `int(time.time() * 1000)` instead — confirmed this session by direct read of that file.

So on the `mics_core` stack, `now_ms` (system wall clock, `_now_ms()`) is subtracted from
`last_msg_ts_ms` (pigpio-tick-derived, the one clock), and the difference includes whatever offset
the fitted tick mapping carries at that moment (`clock.py:401-404`, `_epoch_offset_ns` is
recomputed per call, never cached). If that offset exceeds `stale_ms` (3000ms for the demo
fixture, confirmed live) the device reads dead forever while frames are arriving; if it is
negative and large it reads alive forever. On `pi-mirror` both sides are `time.time()` and **B
cannot occur.**

**Caveat on B's own mechanism:** `_now_ms_and_mono_ns` (`external_hardware_ingress.py:38-58`) falls
back to `int(time.time() * 1000)` on `ClockNotReady`/`ClockFault` (and any other exception) and
counts the fallback via `_INGRESS_CLOCK_FALLBACKS`. A pilot in permanent fallback has both sides on
`time.time()` again, so B predicts **NO failure** there — check the fallback counter
(`ingress_clock_fallbacks()`) before concluding B is or is not active on a given run.

---

## 3. THE DISCRIMINATOR — which stack does the fault reproduce on?

Defect B is `mics_core`-ONLY. So:
- **Fault reproduces on a `pi-mirror` pilot -> it is Defect A.** B is structurally impossible there
  (both sides of the subtraction are `time.time()`).
- **Fault appears only on `mics_core` -> consistent with B** (not proof, but consistent).

**Pilot 1 (`132.77.72.28`) is the `pi-mirror` reference and therefore the cheap A-versus-B
discriminator.** This is the second time pilot 1 has surfaced as a cross-stack probe — see D-43's
recorded-and-declined alternative (cross-talk proof ran two `source_id`s on ONE pilot instead of
provisioning a second pilot, for the same reason: setup cost). Live confirmation this session
(`GET /api/toolkits/100`, `extlink_signals.by_pilot`) shows pilot 1 is named
`pilot_raspberry_lior` and already carries a `demo` row. Note this here as **available and not
currently planned** — if Defect A resurfaces on pilot 3 and the cause is unclear, this is the next
move and it is cheaper than guessing.

---

## 4. THE FIX — lib-level, a workaround, and it addresses B, not necessarily A

**The permitted fix here is lib-level, never substrate-level — and it is a WORKAROUND, not a
resolution.** A `liveness_hook` override that reads the CURRENT time from the same source the
ingress stamp came from (`external_hardware_ingress.now_ms()`) restores a like-for-like comparison
without touching a single Pi file. `make_liveness` (`external_hardware_wire.py:170-173`) REPLACES
the default with the override, so the hook owns the decision completely. DLC-01 forbids this phase
from editing the substrate, so a workaround is the correct move — but it must be labelled one, with
Defect B left open and OWNED BY PHASE 31/18, not absorbed as normal.

**It fixes B. It may not fix A.** A hook that compares like-for-like removes the clock-domain
mismatch and nothing else. If Defect A is the egress probe (A1), a startup race (A2/A3), or
something not yet enumerated, this hook does not touch it. **So the quiet test in plan 35-09
passing is NOT guaranteed, and its failing is not a failure of this plan** — it is Defect A
resurfacing, which is the single most valuable thing this phase could learn about the substrate.

The canonical hook is authored at `fixtures/liveness_hook_snippet.py` (this plan, Task 1) and
carried into the candidate lib 177 v3 at `fixtures/extlink_demo_v3.py` (this plan, Task 2). Plan
35-03's generator emits the same hook text verbatim under `--liveness-hook clock-consistent`.

---

## 5. Results table — EMPTY. Plan 35-09 fills this in at the rig.

| Rig observation | Result | Notes |
|---|---|---|
| `alive` true while streaming | `pending` | plan 35-09 |
| `alive` false after sender stop | `pending` | plan 35-09 |
| `alive` true while a signal goes stale (stale-vs-alive split, per Phase 34 §3d) | `pending` | plan 35-09 |
| readiness gate not stranded (2/4-run symptom does not recur) | `pending` | plan 35-09 |

**Plan 35-09 fills in this table.** A `pending` row resolving to FAIL is not automatically a
regression — see §4: it may be Defect A, which this plan's fix was never expected to touch.

---

## 6. Phase 31 defect: a violation of the one-clock invariant, owned by Phase 31/18

**The cross-clock subtraction and where its two sides come from:** `external_hardware_binding.py`'s
`_now_ms()` (`:19-25`, wall-clock, `time.time()`-derived) is subtracted, inside
`default_liveness` (`external_hardware_wire.py:163-167`), from `_last_msg_ts_ms`
(`external_hardware_ingress.py:on_recv`, one-clock-derived on `mics_core` via
`_now_ms_and_mono_ns()` / `clock.to_utc_ns(clock.now_from_tick())`).

**This VIOLATES the one-clock invariant rather than being an exception to it.** The invariant WAS
the intent — that is exactly why a cross-clock subtraction is a violation of it rather than a
carve-out from it. Recording this as "a documented exemption" would make a bug look like a design.

**Phase 31 Plan 10 introduced it (D-50).** Commit `1f35782 feat(31-10): every remaining record
timestamp onto the one clock (Task 2)` (2026-08-24 09:14:00 +0000) moved **ingress** onto the one
clock. The same plan's Task 2 item 7 said of binding: *"change nothing... it is liveness
bookkeeping, not a record timestamp."* That reasoning is **true of the value in isolation and
false in composition**: binding's wall-clock `_now_ms()` is subtracted from `_last_msg_ts_ms`,
which that very plan had just moved onto the one clock. One plan converted one side of a
subtraction and deliberately left the other. Neither decision is wrong alone; together they are the
bug.

**The in-source comment overstating its own authority (D-49):** `external_hardware_binding.py:22`
says *"Phase 31 Plan 10's F7 exempts this site by name"* — **this is FALSE**, verified against
`final_checks.py:227-256,294-323` above (`F7_CLOSURE` does not list this file; `F7_EXEMPTIONS`'
single entry is the ingress fallback; the checker never opens a file outside the closure). Being
outside a closure is not the same as being exempted by name.

**F7 structurally cannot catch this class of defect (D-51), for TWO independent reasons:**
`binding.py` is outside `F7_CLOSURE` so the file is never scanned; and `f7_one_clock`
(`final_checks.py:294-323`) walks `ast.Call` nodes matching forbidden call FORMS
(`_forbidden_call_label`, `:275-292`), which has no notion of two values being differenced. A guard
that asks *"does this file read the wall clock?"* cannot see *"these two clocks meet."* **So adding
`binding.py` to `F7_CLOSURE` would catch the call and still not catch the composition** — say this
explicitly, because it is the obvious fix and it is insufficient on its own.

**The fix is explicitly NOT made here (DLC-01) and is owned by Phase 31/18.** This plan authors a
lib-level workaround (§4) and stops there.

**How both errors were surfaced:** the user challenged the "F7 exempts it by name" claim after it
appeared in this plan's first pass and in the coordinator's report, and it did not survive the
check against the guard itself. Separately, the user's challenge to the causal story (override
"caused by" the clock bug) led to the dated timeline in §2, which refuted it. Neither survived
contact with the evidence. Record both, because they are why this finding is trustworthy now — and
a standing reminder that an in-source comment asserting its own authority is a claim, not a
citation, and that a plausible mechanism is not a cause until the timeline agrees.

---

## 7. Task 2 — candidate lib 177 version 3: parity proof and rig-write plan for 35-09

**Fixtures produced (this plan, no API write issued):**
- `fixtures/extlink_demo_v2_rollback.py` — lib 177's CURRENT active source (`hardware_lib_versions`
  id 137, `active_version_id` on lib 177), fetched read-only via
  `GET /api/hardware-libs/177` and saved byte-for-byte (3301 bytes, confirmed identical to the API
  response's `source_code` field this session).
- `fixtures/extlink_demo_v3.py` — v2 with the `DIAGNOSTIC OVERRIDE (v2)` `liveness_hook` replaced
  by the canonical hook from `fixtures/liveness_hook_snippet.py`, plus a version-comment header.
  Nothing else changed: same class name `ExtlinkDemo`, same two signals, same event, same command,
  same egress behaviour.

**Parity proven mechanically**, not by inspection: both files were run through
`api.extlink_ast.extract_extlink_metadata` this session. `liveness_hook` is not decorated with
`@signal`/`@event`/`@command`/`@decoder`, so the extractor does not see it at all — the two
extracted structures are **IDENTICAL**:

```
extract_extlink_metadata(v2) == extract_extlink_metadata(v3)  ->  True
signals (both): {'left_paw_x': {...}, 'right_paw_x': {...}}
```

Recorded here so plan 35-09 can re-assert this against what the API actually stores after upload —
if the API's own `ast_metadata` for the newly-created version does not match this, something in the
upload path changed more than the hook, and 35-09 should stop before repinning.

### Backend confirmation (for 35-09 to act on, verified live this session)

- The `ExtlinkDemo` pilot config row (pilot 3, `RecordingBox`, config id 33) has `host:
  "132.77.73.125"` — the dev host (`ido-server`) this plan ran on — confirming the local stack is
  the backend the rig uses. `orchestrator/orchestrator/prefs.json` names `MICS_API_URL` as
  `http://127.0.0.1:8000`, consistent with this.
- Lib 177's current `active_version_id` is **137** (version_number 2, the override). `id`=177,
  `name`="extlink_demo".
- Task definition 434's current `hw_lib_versions` row for lib 177, fetched from
  `GET /api/task-definitions/434/hw-lib-versions` this session:
  ```json
  {
    "hardware_lib_id": 177,
    "lib_name": "extlink_demo",
    "lib_filename": "extlink_demo.py",
    "selected_version_id": null,
    "selected_version_number": null,
    "selected_version_state": null,
    "active_version_id": 137,
    "active_version_number": 2,
    "active_version_state": "beta"
  }
  ```
  `selected_version_id: null` means task def 434 currently tracks lib 177's ACTIVE version
  (137, v2) rather than a pin — there is no explicit `hw_lib_versions` JSON key for lib 177 yet on
  this task definition. If 35-09 pins it to the new v3 version_id, that pin becomes explicit and
  survives lib 177 gaining a future v4.

### Exact write calls for plan 35-09, ready to copy, with their reverse

**1. Upload v3 as a new version of lib 177** (creates a new `hardware_lib_versions` row and makes
it lib 177's `active_version_id` — does NOT touch task definition 434's pin):

```bash
curl -s -X PUT "$MICS_API_URL/api/hardware-libs/177" \
  -H "Authorization: Bearer $MICS_API_TOKEN" \
  -H "Content-Type: application/json" \
  -d "$(python3 -c "
import json
print(json.dumps({
    'source_code': open('.planning/phases/35-deeplabcut-keypoint-likelihood-integration/fixtures/extlink_demo_v3.py').read(),
    'declared_imports': [],
}))
")"
```
Read `active_version_id` from the JSON response — that is v3's new `version_id`, call it
`$V3_ID`. It cannot be predicted ahead of upload (DB auto-increment).

**2. Repin task definition 434 to that new version** (does NOT touch lib 177's `active_version_id`,
only this task definition's pin):

```bash
curl -s -X PUT "$MICS_API_URL/api/task-definitions/434/hw-lib-versions/177" \
  -H "Authorization: Bearer $MICS_API_TOKEN" \
  -H "Content-Type: application/json" \
  -d "{\"version_id\": $V3_ID}"
```

**Reverse (rollback), in the opposite order — repin task def 434 back to v2 first, then optionally
roll lib 177's active version back:**

```bash
# Repin task definition 434 back to v2 (id 137)
curl -s -X PUT "$MICS_API_URL/api/task-definitions/434/hw-lib-versions/177" \
  -H "Authorization: Bearer $MICS_API_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"version_id": 137}'

# Optional: also roll lib 177's own active_version_id back to v2 (clones id 137's source into a
# NEW version row and makes that active -- does not delete the v3 row, so nothing is destroyed)
curl -s -X POST "$MICS_API_URL/api/hardware-libs/177/rollback" \
  -H "Authorization: Bearer $MICS_API_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"version_id": 137}'
```

`fixtures/extlink_demo_v2_rollback.py` is the file-copy fallback if the API rollback endpoint is
unavailable for any reason: its content is byte-identical to version 137's `source_code`, so
35-09's revert never depends on reconstructing v2 from memory.

**No `PUT`, `POST`, `PATCH` or `DELETE` was issued against the API by this plan.** All curl calls
made during this plan's research were `GET` only. `git status --porcelain` under
`/home/ido/mics_core/` and `/home/ido/pi-mirror/` is empty — nothing under either tree was
modified.
