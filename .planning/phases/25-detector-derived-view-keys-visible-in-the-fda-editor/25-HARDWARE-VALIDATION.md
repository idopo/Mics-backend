# Phase 25 — Hardware Validation Log

**Date:** 2026-07-29
**Pilot:** `pilot_raspberry_lior` (pilot_id 1) · **Toolkit:** 100 · **Task def:** 186 (`source_less_toolkit FDA_tes_interuuppt`)
**Status:** Phase 25's own requirements PROVEN on the rig. Plan 06 checkpoint still OPEN —
several manual steps not taken, and an unrelated pre-existing rig defect surfaced mid-validation
and is UNRESOLVED.

**Scope:** what was proven on hardware, the pre-existing defect found by running the system, the
seven hypotheses tested against it (six refuted by measurement), the exact system state at
handoff, and what to do next.

> ⚠️ **ES lives on `132.77.73.217:9200`, index `event_log_v2`.** `.125` is historical
> (`restored-*`) only — its own `event_log_v2` is a stale 308-doc stub frozen at 2025-11-30.
> `docker-compose.yml` says `ES_URL: http://host.docker.internal:9200` (i.e. `.125`), which
> **contradicts** where data actually lands. Unresolved, and a live trap.
>
> **A run is isolated in ES by `subject` == Postgres `session_runs.subject_key`**, e.g.
> `{"term": {"subject": "bp_s113_r494"}}`. There is no `run_id` field.

---

## 1. Execution status

| Plan | Wave | Status | Verified by |
|---|---|---|---|
| 25-01 backend derivation core | 1 | ✅ done | 163 pytest, live `module_detector_channels` call |
| 25-02 Pi runtime (first_channel, view_detector, trigger guard) | 1 | ✅ done | 64 dev-host tests, `py_compile`, mirror↔Pi byte-identical |
| 25-03 preflight + dispatch routes | 2 | ✅ done | 219 pytest, live `/api/toolkits/*` |
| 25-04 editor detector picker | 3 | ✅ done | 24 `node:test`, `tsc --noEmit`, bundle served |
| 25-05 preflight rendering + `first_channel` affordance | 4 | ✅ done | `tsc --noEmit`, bundle served |
| 25-06 deploy + rig proof | 5 | ⚠️ **PARTIAL** | task 1 done; tasks 2–3 partly done, checkpoint open |

Served bundles confirmed in `mics_web_ui`: `TaskEditor-B6-dKcPk.js`,
`HardwareCheckModal-DKJUfoGY.js`, `PilotHardwareConfig-B09He_Dl.js`.

---

## 2. Rig proof — what Phase 25 demonstrably delivers

### 2a. DVK-09 — channel 4's writes now land (runs 482 → 483)

Same session, same task, ~3 minutes apart. The **only** difference is
`first_channel: 1` on the MPR121 config.

| | run 482 (before) | run 483 (after) |
|---|---|---|
| `LICKER1` writes | 16 | 14 |
| `LICKER2` writes | 7 | 8 |
| `LICKER3` writes | 5 | 5 |
| **`LICKER4` writes** | **0** | **6** ✅ |
| `LICKER0` writes | 0 (dead tracker) | — (no longer built) |
| **`TRIGGER_ACTION_ERROR`** | **6** | **0** ✅ |
| touch events (`pin_number`) | 68 | 66 |

**Exact 6↔6 correspondence.** Every channel-4 touch that raised `KeyError: LICKER4` in run 482
lands as a `LICKER4` tracker write in run 483. This is the event class silently discarded in
runs 480/481 (Phase 24 Finding A).

`LICKER0` was never written in either run — confirming it was always a dead tracker.

### 2b. DVK-10 — a failing trigger action is now loud

Before Phase 25 this logged `No valid trigger for TOUCH_INT` at DEBUG and vanished. It is now a
first-class indexed ES event:

```json
{"event_type": "TRIGGER_ACTION_ERROR",
 "event_data": {"trigger": "TOUCH_INT", "callback": "trigger_actions_TOUCH_INT",
                "error_type": "KeyError",
                "error": "view action: key 'LICKER4' (from template '{device_name}{pin_number}')
                          not found in self.view.view. Available: ['LICKER0'..'LICKER3', ...]"}}
```

Run 482 contains 6. Run 483 contains 0. The worker thread survived all 6 and the run ended
normally via `end()` (`mics_task.py:1453` prints `task terminated`) — satisfying the
"one raising callback does not kill the worker" requirement.

### 2c. DVK-11 — a stored detector REFERENCE, resolved per pilot (runs 492/493/494)

Stored definition (task def 186), verbatim:

```json
"condition_tree": {
  "op": "==",
  "left": { "view_detector": { "ref": "MPR121", "channel": 1 } },
  "right": 1
}
```

`SELECT (fda_json::text LIKE '%LICKER%')` → **false**. The string `LICKER` appears **nowhere** in
the definition. The Pi resolved the reference to its own `LICKER1` tracker at task load.

**12 of 12** `play_led → trial_onset` firings across runs 492–494 were immediately preceded by
`LICKER1 → 1`, typically within 1–4 ms:

| run | firings | preceded by `LICKER1 = 1` | LICKER channels written |
|---|---|---|---|
| 492 | 4 | 4/4 | L1=45, L2=2, L3=3 |
| 493 | 4 | 4/4 | L1=75 only |
| 494 | 4 | 4/4 | L1=58 only |

**Built-in negative control (run 487).** Between 15:52:35.255 and 15:52:39.122 the spout was
touched four more times (`LICKER1` = 1 at 36.357, 37.096, 38.938) and **no transition fired** —
the FDA was in `trial_onset` awaiting the timer, not in `play_led`. The condition acts only from
its declared source state. Not coincidence, not a spurious trigger.

`fda_json` md5 at time of proof: **`7335c9bb57aeb0b6c24f14c54944a0e9`**
(earlier value `c6f3719889d743967762b75af387b720` superseded by the user's timer edit.)

### 2d. Timer-gated FDA — timing verified to the millisecond (run 487)

With `trial_onset → play_led` gated on `TIMER == 0` and `play_led` entry setting `TIMER(5)`:

| time | state | gap | cause |
|---|---|---|---|
| 29.373 | `play_led` | — | TIMER set 5 s → expires 34.373 |
| 33.043 | `trial_onset` | 3.67 s | touch |
| 34.375 | `play_led` | 1.33 s | **2 ms after timer expiry** |
| 39.376 | `play_led` | 4.49 s | **1 ms after expiry** |
| 44.377 | `play_led` | 4.33 s | **1 ms after expiry** |

Three independent timer expiries landing within 1–2 ms of prediction.

---

## 3. Requirements status

| Req | Status | Evidence |
|---|---|---|
| DVK-01 | ✅ | one derivation helper; Pi + backend agree (`derive_view_keys` / `detector_view_keys`) |
| DVK-02 | ✅ | `detector_channels` on all toolkit reads incl. `/by-name/` |
| DVK-03/04/05 | ⚠️ **not manually verified** | implemented + unit-tested; plan 06 task 3 step 2 NOT performed |
| DVK-06 | ⚠️ **not manually verified** | preflight negatives (channel 5, literal `LICKER0`) NOT run |
| DVK-07 | ✅ | flag picker excludes detector keys (unit-tested) |
| DVK-08 | ✅ | editor → save → preflight → transition fires on rig |
| DVK-09 | ✅ | §2a — 6 writes that were previously discarded |
| DVK-10 | ✅ | §2b — `TRIGGER_ACTION_ERROR` indexed |
| DVK-11 | ✅ storage + positive · ⚠️ rename half NOT done | §2c; `device_name` → `TONGUE` rename proof NOT performed |

---

## 4. THE OPEN DEFECT — intermittent lost GPIO interrupt (PRE-EXISTING, UNRESOLVED)

**Symptom.** Some runs hang forever in `play_led`. Fingerprint is exact and repeatable:

```
~15–20 ES events · TOUCH_INT count = 0 · zero Tracker writes
last state_transition = play_led · run never ends
```

Working runs log 100–194 `TOUCH_INT` events. Stuck runs log **zero** — not few, zero.

| run | 496 | 497 | 498 | 499 | 500 | 501 | 518 | 519 | 520 |
|---|---|---|---|---|---|---|---|---|---|
| status | ok | **stuck** | ok | **stuck** | ok | **stuck** | ok | ok | **stuck** |
| TOUCH_INT | 184 | **0** | 154 | **0** | 194 | **0** | — | — | **0** |

Intermittent. Not deterministic alternation (492/493/494 and 518/519 ran clean back-to-back).
Cleared by restarting the pilot. Unaffected by every config and FDA change made.

### 4a. NOT caused by Phase 24 or Phase 25 — proven

`TOUCH_INT` "Modules" events are emitted by `execute_trigger`'s **unconditional**
`Hardware_Event` dispatch (`task.py:272-283`), *before* `self.triggers[pin]` is even looked up.
Phase 24's assignment machinery and Phase 25's guard both live **downstream** of that line.
Stuck runs have zero such events → `execute_trigger` was never entered. Nothing either phase
added can suppress an event emitted before their code runs.

The legacy lick path is **structurally identical** to the current one:

| | legacy | now |
|---|---|---|
| registration | `self.triggers['TOUCH_INT'] = [self.detectedLick]` (`learning_cage.py:139`) | `apply_trigger_assignments` → same dict |
| pigpio arming | `Task.__init__` → `hw.assign_cb(...)` | **same code**, `task.py:199` |
| chip read | `MPR121.detect_change()` — 0x5A | **same method** |

**What changed is dependence, not mechanism.** Legacy tasks advanced on timers; a dropped
interrupt cost a lick event and the run still completed normally. The FDA now *requires* the
touch to advance, so the same fault became a visible hang.

> **A dropped interrupt and an untouched spout produce byte-identical data.** There is no record
> of a touch that was never delivered. That indistinguishability is why this survived unnoticed,
> and it is a standing data-integrity concern for lick counts.

### 4b. Measured facts (all confirmed, none disputed)

- `[TRIG-SETUP] TOUCH_INT pin=8 bcm=14 cb_assigned=1 current_level=1` on **every** stuck run
  → callback IS registered; INT line IS idle-high at task start; chip is NOT latched at start
- `pigs r 14` = **0** mid-stall → the line **does** transition high→low when touched
- zero `TOUCH_INT` events → pigpio delivers **nothing** for that transition
- `i2cdetect -y 1` (which probes 0x5A) **released the line and revived the rig** — an external
  register read is the only escape once latched
- `[DETECTORS]` prints correctly on stuck runs → I2C healthy, `detector.read()` works
- `pi id` differs every run → a genuinely fresh `pigpio.pi()` object each time

### 4c. Hypotheses TESTED AND REFUTED — do not re-litigate these

| # | Hypothesis | Refuted by |
|---|---|---|
| 1 | dead pigpio handle / stale dispatcher (clock path) | run 491: fresh `pi id`, `connected=True`, **zero** clock-guard drops |
| 2 | Phase 24/25 error handling introduced it | `TOUCH_INT` events are emitted upstream of all phase code; legacy path identical |
| 3 | MPR121 in STOP mode (`ECR=0x00`) | `pigs r 14` = 0 → chip **did** assert INT; it is sensing |
| 4 | second MPR121 at 0x5B wired-OR on the IRQ | user confirms only 0x5A drives TOUCH_INT (0x5B/0x60 unrelated hardware) |
| 5 | 500 µs `set_glitch_filter` (`gpio.py`, `Digital_In.__init__`) | present in legacy too, which worked for years |
| 6 | `trigger: "B"` vs legacy `"D"` | changed to `"D"` (verified active — run 519 shows single `level=0` callbacks); **run 520 still stuck** |
| 7 | `polarity` inverting edge/pull | `polarity` setter only assigns `self.on`/`self.off`; the `Digital_In` docstring claiming "pull=low, trigger=high" is **wrong**. `pull:1` → `PUD_UP` ✓, `trigger:"D"` → FALLING ✓ |

**Config now matches legacy field-for-field:** `pin 8`, `pull 1`, `polarity 1`, `trigger D`,
`record false`. No configuration difference remains.

### 4d. LEADING HYPOTHESIS (untested) — pigpio's notification socket

`pigpio.pi()` opens **two** connections to pigpiod:

```python
self.sl.s    = socket.create_connection(...)   # CONTROL socket
self._notify = _callback_thread(...)           # NOTIFICATION socket + thread
```

Edge callbacks are delivered **only** over the notification socket. Everything we probed all day
— `connected`, `get_current_tick()`, `pig.read()`, `set_mode`, `set_glitch_filter`, and the
`pi.callback()` return object — is either the control socket or client-side state.

```
pilot.py:1141:  if not self.pi.connected: raise    # ← control socket ONLY
```

So if the notification half fails to come up on a given run, **every probe reports healthy while
edges are never delivered**. This is per-connection, so a fresh `pigpio.pi()` each run gives a
fresh chance to fail — intermittent, not cumulative, cleared by a pilot restart, immune to config.
It is the only layer never measured.

**Next probe (2 lines, into the existing `[TRIG-SETUP]` print):**

```python
hw.pig._notify                # None, or thread object
hw.pig._notify.is_alive()     # False on a broken run?
hw.pig._notify.handle         # pigpiod slot number — climbing = leak
```

**External test (no deploy), run during a stuck task:**

```bash
~/.venv/autopilot/bin/python -c "
import pigpio, time
pi = pigpio.pi()
c = pi.callback(14, pigpio.EITHER_EDGE, lambda g,l,t: print('EDGE',g,l,t,flush=True))
print('watching 20s — touch a spout', flush=True)
time.sleep(20); c.cancel(); pi.stop()"
```

`EDGE` prints while the task sees nothing → the task's connection is the broken half.
Nothing prints → pigpiod isn't reporting BCM 14 at all.

### 4e. Recommended fixes (none implemented)

| # | Fix | Where | Why |
|---|---|---|---|
| 1 | **Persistent pigpio connection + persistent MPR121 interrupt**, routed to the *current* task (must look up, never capture) | `pilot.py` lifetime | removes the per-run open/close cycle entirely; restores the legacy always-on shape; **bonus: one continuous tick domain across runs**, which serves the unified-clock requirement better than re-`synchronize()` per run |
| 2 | **Poll fallback** — every ~100 ms, if INT reads low, call `detect_change` anyway | detector layer | self-heals *any* missed edge; costs 100 ms instead of a session; correct regardless of root cause |
| 3 | **Watchdog** — INT low >200 ms with no trigger → log loudly | detector layer | makes "no licks" distinguishable from "lost the interrupt", now and forever |
| 4 | **Return all changes**, not `changes[0]` | `i2c.py:842` | **separate silent-loss bug**: `detect_change` discards every electrode change but the first — same class as the `LICKER4` defect this phase fixed |

(2) and (3) are contained to the detector layer — no lifetime or clock changes.
(1) is architectural and deserves its own plan + a ten-consecutive-run verification.

---

## 5. Other defects found by running the system

### 5a. `/react/pilots/:pilot/hardware-config` crashes — UNRESOLVED

Backend fully verified healthy: route exists (`App.tsx:46`), `GET /pilots/by-name/...` 200,
`/api/pilots/1/hardware-config` 200, `/api/hardware-modules/7/methods` 200 with
`is_detector: true`, all four chunks `PilotHardwareConfig-B09He_Dl.js` imports present on disk.

**Suspected cause (unconfirmed):** stale cached `main.js`. Its filename never changes, it is
served with **no `Cache-Control`** header (only `etag`/`last-modified`), and it hard-codes
content-hashed chunk names. A non-existent hashed chunk returns **404** (verified). A cached
`main.js` would therefore fail the dynamic import → route crash. Hard-reload was never confirmed.

Consequence: **plan 06 task 3 step 1 is undischarged** — `first_channel: 1` was set via psql, not
through the new UI field, so the DVK-09 affordance itself is unproven.

Worth fixing regardless: add `Cache-Control` for `main.js` in `web_ui/app.py`.

### 5b. Editor shows no warning for non-State validation messages — PRE-EXISTING (Phase 14)

Task def 186 has `validation_status: broken`,
`validation_message: "Trigger 'TOUCH_INT': MPR121.detect_change not found in lib (class Touch_Detector)"`.

`TaskDefinitions.tsx:329` shows the `!` badge from `validation_status`. The editor uses
`parseStateWarnings` (`TaskEditor.tsx:131-141`), which only matches `^State '(...)': (.+)$`.
**Trigger-scoped warnings parse to nothing** → badge in the list, silence in the editor.
Code dates to `8c62f48` (Phase 14). Untouched by Phase 25.

### 5c. Pin collisions in `pilot_hardware_config`

`Left_LED` and `Right_LED` were both board pin 11 (BCM 17) — identical configs, `Right_LED`
lacked a `name` key. **User deleted `Right_LED`; hang persisted, confirming it was unrelated.**

**STILL PRESENT:** `Solenoid` (pin 12) and `Mid_LED` (pin 12) — **BCM 18, two different device
classes on one GPIO.** Setting one sets the other. Not deleted because only the user knows which
has the wrong pin. **Needs wiring check.**

Also: `Left_LED`/`Mid_LED` carry `"trigger": "U"`, so outputs register interrupt callbacks
(`cb_assigned=2`). Suspect on its own.

### 5d. `pigpiod` launch flags

```
/usr/local/bin/pigpiod -t 0 -l -x 1111110000111111111111110000
```

`Can't lock /var/run/pigpio.pid` / `Can't initialise pigpio library` printed at every pilot
start — the C library failing to claim hardware the daemon already owns. Believed benign; the
Python client connects fine. Not investigated.

### 5e. FDA runaway when the timer gate is removed (task design, not a defect)

Removing `TIMER == 0` from `trial_onset → play_led` restored a free-running loop: run 509 logged
**35 trials from a single touch** (2 LICKER1 writes, 35 `trial_counter` increments in 177 ms),
because `LICKER1` stays `1` for the whole hold and `play_led` re-arms instantly.

**Recommended fix — release gate, no timer needed:**

| from | to | condition |
|---|---|---|
| `trial_onset` | `play_led` | **`LICKER1 == 0`** ← add |
| `play_led` | `trial_onset` | `LICKER1 == 1` |

Requires a full touch→release cycle per trial. One trial per lick, pure edge semantics in the FDA.

### 5f. `Event_Dispatcher.dispatch_event` is not total

`self.pi.get_current_tick()` at `Event_Dispatcher.py:61` runs **unguarded in the calling thread**.
A hardware/tracker callback that raises there unwinds before its remaining writes. Observed as
23 dead `Thread-13…35` after run 485's runaway (each loop iteration scheduled an LED-off timer
that came due post-teardown).

Now guarded (see §6) — **event dropped, never stamped from another clock**, per the user's
requirement that the pigpio tick remain the single clock for the entire log system.

---

## 6. System state at handoff

### 6a. Debug instrumentation deployed to the Pi — **MUST BE STRIPPED**

Uncommitted in `/home/ido/pi-mirror` (user-owned repo; agent never runs git there).
All deployed and verified byte-identical to the Pi.

| File | Change |
|---|---|
| `autopilot/autopilot/networking/Event_Dispatcher.py` | `[DISPATCH]` prints (dispatcher built / clock unreadable / send failed); guarded tick read; `_dropped_no_clock` + `_dropped_on_send` counters; `except Exception: pass` in `_sender_loop` replaced with a counted drop |
| `autopilot/autopilot/tasks/mics_task.py` | `[DETECTORS]` channel→tracker map; `[VIEW] KEY <- value` on every tracker write |
| `autopilot/autopilot/tasks/task.py` | `[TRIG-SETUP]` at `assign_cb`; `[TRIG] execute_trigger pin=... level=... registered=...` |

`i2c.py` verified byte-identical throughout. Clock behaviour unchanged — no fallback timebase,
no reconnect, no re-`synchronize()`.

### 6b. Live rig config changes made this session

| What | Before | Now | How |
|---|---|---|---|
| MPR121 `first_channel` | absent | `1` | **psql** (UI crashed — §5a). Original saved to scratchpad `mpr121_original_config.json`: `{"name":"MPR121","num_detectors":4,"device_name":"LICKER","address":true}` |
| `TOUCH_INT.trigger` | `"B"` | `"D"` | UI — matches legacy; **did not fix the hang** |
| `Right_LED` | present | **deleted** | UI — did not fix the hang |
| task def 186 FDA | timer-gated | user-edited repeatedly | UI |

⚠️ **`device_name` is still `LICKER`** — the DVK-11 rename proof was never performed, so no
restore is pending on that field. `first_channel` must remain `1` (the intended new value).

### 6c. Repo state

Phase 25 plans 01–05 committed on branch `claude`. `25-06-SUMMARY.md` **not written** — plan 06
is incomplete.

---

## 7. Immediate next steps

1. **Run the §4d notification-socket probe.** It is the only unmeasured layer and the one
   remaining hypothesis. Two lines into an already-deployed print, or the zero-deploy external
   test. **Do this before writing any fix.**
2. **Implement §4e (2)+(3)** — poll fallback + watchdog. Correct regardless of root cause; makes
   the rig usable and the failure self-announcing.
3. **Fix §5a** (hard-reload / `Cache-Control`), then set `first_channel` through the UI to
   discharge plan 06 task 3 step 1.
4. **Finish the open plan-06 manual steps:** DVK-03/04/05 editor round trip, DVK-06 preflight
   negatives, the DVK-11 `device_name` → `TONGUE` rename proof (baseline md5
   `7335c9bb57aeb0b6c24f14c54944a0e9`), and a deliberate one-spout-at-a-time cross-talk run.
5. **Strip the §6a debug prints** once the defect is understood.
6. **Resolve the `Solenoid`/`Mid_LED` BCM 18 collision** (§5c) — needs a wiring check.
7. **Fix §4e (4)** — `detect_change` returning only `changes[0]`.

---

## 8. Honest assessment

Phase 25's own requirements are proven on hardware, with the DVK-09 6↔6 correspondence and the
DVK-11 12/12 firing correlation being unusually clean evidence.

The interrupt defect is **pre-existing, not introduced by this phase**, and Phase 25 is the reason
it is now visible at all — DVK-10 turned a silent DEBUG line into a named error, and the FDA's
dependence on the detector turned a lost lick into an obvious hang.

Seven hypotheses were tested; six were refuted by measurement, several after being stated with
more confidence than the evidence supported. The pattern of error was consistent: reasoning about
layers instead of measuring them. The one layer never measured — pigpio's notification socket — is
the leading candidate precisely because every probe written today queried the control path
instead.
