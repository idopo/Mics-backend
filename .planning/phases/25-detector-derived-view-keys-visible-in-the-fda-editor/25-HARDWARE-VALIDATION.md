# Phase 25 — Hardware Validation Log

**Date:** 2026-07-29
**Pilot:** `pilot_raspberry_lior` (pilot_id 1) · **Toolkit:** 100 · **Task def:** 186 (`source_less_toolkit FDA_tes_interuuppt`)
**Status:** Phase 25's own requirements PROVEN on the rig. Plan 06 checkpoint still OPEN —
several manual steps not taken. The interrupt defect that surfaced mid-validation was
**root-caused and fixed later the same day** (§4): a pre-existing regression from the
2026-01-25 → 2026-03-10 shared-pigpio work, not from phase 24 or 25. Idle path verified fixed
on hardware; the in-run path (§4g) remains open.

**Scope:** what was proven on hardware, the interrupt defect found by running the system —
mechanism, regression window, fix, and rig verification — the hypotheses refuted along the way,
the exact system state at handoff, and what to do next.

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

## 4. THE INTERRUPT DEFECT — ROOT-CAUSED AND FIXED

**Status: idle path RESOLVED** — i2c hardware lib v2 (version id 26), marked `stable`
2026-07-29 and verified on the rig. The in-run path (§4g) is untouched and still open.

### 4a. Mechanism

The MPR121 IRQ is a **level** signal. It asserts on any change of the touch-status register and
is deasserted by exactly one thing: an I2C read of that register (`touched_pins`). `TOUCH_INT` is
a `Digital_In` with `trigger: "D"` — **falling edge**. A single assertion that nobody reads is
therefore terminal: the line stays low, no further falling edge can exist, no callback can ever
fire again, and only an external register read (`i2cdetect -y 1`) recovers the rig.

That is the entire defect. **"pigpio delivered nothing" is the predicted observation once
latched, not evidence of a delivery failure** — which is where the previous revision went wrong.

Enabling or disabling electrodes is itself a touch-status change, so **every ECR (0x5E) write can
assert the IRQ.** Two code paths ended on an ECR write with no read after it:

| path | last operation | consequence |
|---|---|---|
| `MPR121.__init__` → `set_cdc_manual(0x08)` | `ECR = 0x0C` | constructor could return with the line already latched — rescued only by `mics_task.check_for_detectors()` happening to call `read()` afterwards (a different file, and only when a detector is registered) |
| `MPR121.release()` → `reset()` | `ECR = 0x8F` | **chip left SENSING** after teardown, when its pigpio callbacks and its only reader are already gone |

### 4b. The idle window — measured, not inferred

`run_task`'s `finally` calls `self.pi.stop()` **unconditionally, outside the guard** around
`task.end()` (`pilot.py:1244-1256`). That closes the single shared pigpio client and cancels every
callback regardless of how teardown went. Between runs the pilot is deaf — while `release()` left
the chip sensing. First touch at idle → IRQ asserted → nothing reads it → latched.

Measured 2026-07-29, pilot idle, hours after run 520:

```
pigs r 14 = 0        ← INT asserted, no reader anywhere in the process
```

### 4c. What changed, and when — NOT phase 24 or 25

Regression window: **2026-01-25 → 2026-03-10**, the shared-pigpio / clock-unification work.

| | `96f6fe8` (Jan 25) | `5704cb5` (Mar 10) → today |
|---|---|---|
| pigpio client | `GPIO.init_pigpio()` → `pigpio.pi()` **per hardware object** | one shared client, `pigpio.pi(sync_ticks=True)`, created **per run** by the pilot |
| `GPIO.release()` | `self.pig.stop()` — live | `# self.pig.stop()` — commented out (`gpio.py:322`) |
| `run_task` teardown | guarded `task.end()`, then `gpio.clear_scripts()` — **no pilot-level `pi.stop()`** | guarded `task.end()`, then **`self.pi.stop()` unconditionally** |

Before that change, whether the pilot went deaf at idle depended entirely on `Task.end()`'s release
loop — which has **no per-object error handling** (`task.py:448-450`) and iterates `I2C` before
`GPIO` (`learning_cage.HARDWARE`). One raise inside the I2C group — e.g. `Motor_Shield_Hat.release()`
touching `self.kit`, which its constructor may never assign because it swallows failure with a bare
`except: pass` — aborted the loop before `TOUCH_INT`, leaving its callback armed, its own pigpio
client connected, and (because `event_queue.put('END')` sits *after* the loop) its worker thread
alive. The task stayed reachable via `partial(self.handle_trigger, hardware=hw)`, so **the chip kept
being read while the pilot was idle**. Never designed — an emergent property of an unguarded
teardown, and exactly the behaviour remembered as "the interrupt was always live".

Phases 24 and 25 remain exonerated as *causes*. But the previous revision's §4a claim that the legacy
path was "structurally identical" was wrong on two counts: the **lifetime** is not identical (above),
and the **ACK ordering** is not identical (§4g).

### 4d. The fix — i2c lib v2

Invariant, now pinned by test: **every code path that writes ECR must end with a status read.**

- `set_cdc_manual()` ends with `self.prev = self.mpr121.touched_pins` — clears the IRQ, and seeds
  `detect_change`'s baseline from the *post*-configuration status instead of a stale pre-CDC read.
- `__init__` no longer reads separately; `set_cdc_manual()` does it.
- `release()` writes `ECR = 0x00` (stop mode) **then** reads. Order matters: the stop write itself
  zeroes the touch status and asserts IRQ, so reading first would leave a window for a touch to
  re-latch. Deliberately **not** `reset()`, whose final write re-enables all 12 electrodes;
  recalibration is not lost, because the next run's constructor calls `reset()`.

Tests: `pi-mirror/tests/test_mpr121_irq_hygiene.py` — 3 tests, red before / green after. They run on
the dev host (the class is extracted from the lib text and exec'd against a recording stub, so no
`autopilot` import) and therefore assert against the exact source deployed to the Pi. Deployed bytes
verified md5-identical (`3c933d65…`, `~/apps/hardware_overrides/i2c.py`).

Impact diff on publish was clean: `removed_methods: {}`, `affected_definition_ids: []`.

### 4e. Rig verification

| run | local time | `TOUCH_INT` events | trials | verdict |
|---|---|---|---|---|
| 520 | 17:35 | **0** | 1 | dead (pre-fix) |
| 521 | 18:44 | **0** | 1 | dead (pre-fix) |
| 523–525 | 18:45–18:46 | 8 each | 5 each | completed |
| 526 | 18:46 | 24 | 5 | completed |

And the acceptance test, which is the one that actually discriminates — **touch the spout after the
task terminates**:

```
pigs r 14 = 1        ← was 0 in the identical condition before the fix
```

A run starting clean proves nothing on its own: the constructor's `reset()` clears an inherited
latch regardless of version. Only the idle-touch check tests the defect.

Run 522 produced no ES events at all — unexplained, low priority.

### 4f. Hypotheses tested and refuted — do not re-litigate these

| # | Hypothesis | Refuted by |
|---|---|---|
| 1 | dead pigpio handle / stale dispatcher (clock path) | run 491: fresh `pi id`, `connected=True`, **zero** clock-guard drops |
| 2 | Phase 24/25 error handling introduced it | `TOUCH_INT` events are emitted upstream of all phase code |
| 3 | MPR121 in STOP mode (`ECR=0x00`) | `pigs r 14` = 0 → chip **did** assert INT; it is sensing |
| 4 | second MPR121 at 0x5B wired-OR on the IRQ | user confirms only 0x5A drives TOUCH_INT |
| 5 | 500 µs `set_glitch_filter` (`Digital_In.__init__`) | present in legacy too, which worked for years |
| 6 | `trigger: "B"` vs legacy `"D"` | changed to `"D"` (verified active); **run 520 still stuck** |
| 7 | `polarity` inverting edge/pull | `polarity` setter only assigns `self.on`/`self.off`; `pull:1` → `PUD_UP` ✓, `trigger:"D"` → FALLING ✓ |

**The previous revision's §4d (pigpio notification socket) is superseded.** It became the leading
hypothesis because every probe that day queried the control path — but it is not needed to explain
anything: once the line is latched there are no edges to deliver. It was never measured and no
longer needs to be.

### 4g. Still open — the in-run path

The fix covers the idle window and the constructor. It does **not** cover an interrupt delivered
mid-run and never serviced. None of the four clean runs exercised this.

1. **ACK ordering.** Phase 24 moved the register read out of the driver into a researcher-ordered FDA
   action list. In task def 186 the `MPR121.detect_change` action is **last**, behind a conditional
   `view` write, so any raise in an earlier action skips the ACK for that interrupt → permanent latch
   (Phase 25's `_report_trigger_error` makes it silent-but-alive rather than fatal). Already visible
   in the data: in run 519 every `LICKER1` write carries the **previous** edge's value stamped with
   the **current** edge's tick (~123 ms late), and the final release of each run is never written.
   Fix: put `detect_change` first in the action list.
2. **No self-healing.** A missed edge is unrecoverable by construction. `pig.set_watchdog(pin_bcm, 200)`
   yields `level=2` callbacks with no edges; on timeout, if the pin reads low, call `detect_change()`.
   `Digital_In.assign_cb`'s docstring already documents level 2 for exactly this case.
3. **Unguarded release loop** (`task.py:448-450`) — `release()` can still be skipped wholesale if an
   earlier object in the group raises, silently disabling the §4d fix. One `try/except`.
4. **`except(e):` in `MPR121.__init__`** — `e` is undefined, so a genuine init failure raises
   `NameError`, masks the cause, and leaves a half-built object.
5. **`detect_change` returns `changes[0]`** (`i2c.py`) — discards every electrode change but the
   first. Separate silent-loss bug, unchanged by v2.

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

### 6a. Debug instrumentation deployed to the Pi — partially stripped

Uncommitted in `/home/ido/pi-mirror` (user-owned repo; agent never runs git there).

| File | Change | State |
|---|---|---|
| `autopilot/autopilot/tasks/task.py` | `[TRIG] execute_trigger pin=... level=... registered=...` | **removed** 2026-07-29 |
| `autopilot/autopilot/tasks/mics_task.py` | `[VIEW] KEY <- value` on every tracker write | **removed** 2026-07-29 |
| `autopilot/autopilot/tasks/task.py` | `[TRIG-SETUP]` at `assign_cb` | still present |
| `autopilot/autopilot/tasks/mics_task.py` | `[DETECTORS]` channel→tracker map | still present |
| `autopilot/autopilot/networking/Event_Dispatcher.py` | `[DISPATCH]` prints (dispatcher built / clock unreadable / send failed) | still present |

⚠️ The `Event_Dispatcher.py` change is **not only prints** — it also contains the guarded tick read
(§5f), the `_dropped_no_clock` / `_dropped_on_send` counters, and the `except Exception: pass` in
`_sender_loop` replaced with a counted drop. Those are fixes and must survive any print stripping.

`i2c.py` **is no longer byte-identical to v1** — see §4d (lib v2, id 26, `stable`). Clock behaviour
unchanged — no fallback timebase, no reconnect, no re-`synchronize()`.

### 6b. Live rig config changes made this session

| What | Before | Now | How |
|---|---|---|---|
| MPR121 `first_channel` | absent | `1` | **psql** (UI crashed — §5a). Original saved to scratchpad `mpr121_original_config.json`: `{"name":"MPR121","num_detectors":4,"device_name":"LICKER","address":true}` |
| `TOUCH_INT.trigger` | `"B"` | `"D"` | UI — matches legacy; **did not fix the hang** |
| `Right_LED` | present | **deleted** | UI — did not fix the hang |
| task def 186 FDA | timer-gated | user-edited repeatedly | UI |
| i2c hardware lib (id 9) | v1 (id 15) `stable` | **v2 (id 26) `stable`** — §4d | `PUT /api/hardware-libs/9`, then toolkit 100 re-pinned to v2 in the editor, then `PATCH .../mark-stable`. v1 retained for rollback |

⚠️ **`device_name` is still `LICKER`** — the DVK-11 rename proof was never performed, so no
restore is pending on that field. `first_channel` must remain `1` (the intended new value).

### 6c. Repo state

Phase 25 plans 01–05 committed on branch `claude`. `25-06-SUMMARY.md` **not written** — plan 06
is incomplete.

---

## 7. Immediate next steps

1. **Reorder the TOUCH_INT action list** so `MPR121.detect_change` runs **first** (§4g.1). Removes
   the ACK's dependence on preceding actions and fixes the ~123 ms `LICKER` timestamp lag and the
   lost final release in one edit. Highest value per unit of risk.
2. **Add the INT watchdog** (§4g.2) — `set_watchdog(pin_bcm, 200)`, and on `level=2` read the chip
   if the pin is low. Makes any missed edge self-healing and the failure self-announcing.
3. **Guard the release loop** (§4g.3) — one `try/except` in `Task.end()`, without which the §4d fix
   can be silently skipped.
4. **Fix §5a** (hard-reload / `Cache-Control`), then set `first_channel` through the UI to
   discharge plan 06 task 3 step 1.
5. **Finish the open plan-06 manual steps:** DVK-03/04/05 editor round trip, DVK-06 preflight
   negatives, the DVK-11 `device_name` → `TONGUE` rename proof (baseline md5
   `7335c9bb57aeb0b6c24f14c54944a0e9`), and a deliberate one-spout-at-a-time cross-talk run.
6. **Strip the remaining §6a debug prints** — keeping the Event_Dispatcher *fixes*.
7. **Resolve the `Solenoid`/`Mid_LED` BCM 18 collision** (§5c) — needs a wiring check.
8. **Fix §4g.5** — `detect_change` returning only `changes[0]`.

---

## 8. Honest assessment

Phase 25's own requirements are proven on hardware, with the DVK-09 6↔6 correspondence and the
DVK-11 12/12 firing correlation being unusually clean evidence.

The interrupt defect is **pre-existing, not introduced by this phase**, and Phase 25 is the reason
it is now visible at all — DVK-10 turned a silent DEBUG line into a named error, and the FDA's
dependence on the detector turned a lost lick into an obvious hang.

Seven hypotheses were tested and refuted, several after being stated with more confidence than the
evidence supported. The pattern of error was consistent: **reasoning about layers instead of
measuring them.** The eighth — pigpio's notification socket — was proposed on exactly that basis
and was also wrong; it survived only because it was the one layer nobody had probed, which is a
reason to measure a hypothesis, not to believe it.

What broke the deadlock was one read-only measurement taken in the failure state rather than in a
run: `pigs r 14` with the pilot idle. It returned `0`, and the level-vs-edge mechanism (§4a)
follows from that in one step. Every earlier probe had been taken *during* a run, where a healthy
chip and a latched chip are indistinguishable until a touch arrives.

Two further corrections to this document's earlier revision: the legacy path was **not**
"structurally identical" — neither the hardware lifetime nor the ACK ordering matches — and the
user's recollection that the interrupt stayed live while the Pi was idle was **correct** and turned
out to be the decisive clue, despite being dismissed as inconsistent with the code as written.
