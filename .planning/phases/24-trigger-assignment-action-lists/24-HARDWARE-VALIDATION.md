# Phase 24 — Hardware Validation Log (waves 1–2)

**Date:** 2026-07-27
**Status:** waves 1–2 executed, deployed, and validated on the real rig
**Scope of this document:** what was proven on hardware, the defects found by running the
system (none were catchable by unit tests or typecheck), and the exact system state at handoff.

---

## 1. Execution status

| Plan | Wave | Status | Verified by |
|---|---|---|---|
| 24-01 Pi value-capture substrate | 1 | ✅ done | 18/18 stdlib tests, `py_compile`, `i2c.py` byte-identical to Pi |
| 24-02 backend hard-422 validation | 1 | ✅ done | 60 pytest, 8 live API cases |
| 24-03 shared action editor vocabulary | 1 | ✅ done | `tsc --noEmit`, `ActionEditor.tsx` 419 lines (< 500) |
| 24-04 handler-free trigger runtime | 2 | ✅ done | `py_compile`, 5 grep gates, `i2c.py`/`task.py` untouched |
| 24-05 trigger panel hosts shared editor | 2 | ✅ done | `tsc --noEmit`, `HANDLERS` = 0, bundle served |
| 24-06 / 24-07 / 24-08 | 3–4 | ⛔ **needs re-plan** | see `24-REPLAN-BRIEF.md` |

**41 Pi tests have never been executed anywhere.** `autopilot` cannot be imported on the dev
host (`npyscreen` missing), so `tests/test_load_fda_from_json.py` and
`tests/test_trigger_assignments.py` are USER-RUN on the Pi:

```bash
cd ~/Apps/mice_interactive_home_cage && python3 -m pytest tests/ -q
```

Waves 1–2 are therefore **runtime-proven for the trigger path** (section 2) but
**not unit-test-proven** on the Pi.

---

## 2. Rig proof — run 475

Trigger action list assembled entirely in the task editor, on a **backend-authored
("sourceless") toolkit**, with no `learning_cage` and no Python callback anywhere:

| # | type | ref | method | args |
|---|---|---|---|---|
| 0 | hardware | `MPR121` | `detect_change` | — |
| 1 | hardware | `Mid_LED` | `set` | `{trigger: "level"}` |

### Results

| Metric | run 473 | run 474 | **run 475** |
|---|---|---|---|
| `TOUCH_INT` firings | 1 | 1 | **47** |
| Levels observed | `0` only | `0` only | **alternating `0` / `1`** |
| `Mid_LED` calls | 1 | 1 | 140 |

ES: `event_log_v2` on `132.77.73.217:9200`, query `run_id:475`.

### Requirements demonstrated on hardware

- **TRIGA-01** — a trigger runs an ordered `actions` list through the same
  `_build_action_callable` a state body uses.
- **TRIGA-02** — `{trigger: "level"}` resolves from the invocation context **and varies**
  (0 on contact, 1 on release). Runs 473/474 could not establish this because only one
  edge ever fired.
- **TRIGA-06** — no `handler` enum, no `_build_touch_detector_callback`, no
  hardware-specific code in the trigger runtime.
- Full chain: UI → 422 gate → DB → orchestrator dispatch spec → `apply_trigger_assignments`
  → `_build_trigger_action_list` → `handle_trigger` (GPIO 8 → BOARD → `pin_id` → `TOUCH_INT`)
  → module method call. Trigger→action latency 1–3 ms.

### Why 473/474 showed only one firing (resolved, not a defect)

The MPR121 holds its IRQ line asserted until the touch-status register is read. With no
`detect_change` in the action list nothing performed that read, so the line never returned
high and no further edges could fire. Changing `trigger` `D`→`B` (EITHER_EDGE) made no
difference for the same reason. Adding `MPR121.detect_change` as action[0] — which reads
`self.mpr121.touched_pins` (`i2c.py:833`) — released the latch. **Configuration was never
at fault.**

### Open observations (not blocking, worth understanding)

1. **140 `Mid_LED` calls for 47 triggers** (~3×). Some are `record_event` / `None`-func
   entries from `Digital_Out`'s internal callback bookkeeping, but there appear to be
   genuine duplicate `set` calls per trigger pair. Understand before this pattern is used
   for real data collection.
2. **Logs do not record positional call arguments.** `@log_action` captures kwargs, so
   `hardware.set(x)` never records `x`. The envelope `level` on a `set` event is the
   hardware state *after* the call, not the argument. Consequence: **you cannot verify from
   ES which value an action passed.** Only `Tracker.set` records a `value`.
3. `Digital_Out.is_trigger = True` (gpio.py:343) — not just `Digital_In`. Every LED
   registers a trigger callback. Affects TRIGA-15's `trigger_sources` list.

---

## 3. Defects found by running the system

Seven fixes, none of which unit tests or `tsc` could have caught. **All were in the seam
between individually-correct plans.**

| # | Commit | Defect | Seam |
|---|---|---|---|
| 1 | `b7e6c2b` | Unknown hardware ref saved with 201 instead of 422. `known_hw` was built from `semantic_hardware` only; plan 24-02 specified "plus module names when `is_backend_authored`" and that half was never implemented. A backend-authored toolkit has no `SEMANTIC_HARDWARE`, so `known_hw` was empty and the lenient posture accepted **every** ref. | 24-02 spec vs implementation |
| 2 | `87a04ca` | Editor autosaves 1.5 s after any change and adds a new assignment as `{trigger_name:'', actions:[]}` — exactly the shape the hard gate rejects. Every intermediate state 422'd. | 24-02 gate vs 24-05 UI |
| 3 | `e133641` | `apiFetch` assigned `json.detail` straight to `new Error()`. The gate returns `{errors:[...]}`, so the UI showed `[object Object]`, hiding the message the 422 exists to deliver. | 24-02 detail shape vs pre-existing client |
| 4 | `0400028` | Legacy rows carry `{handler, trigger_name}` with **no `actions` key**; 24-05 made `actions` required and renders `a.actions.length` unguarded → editor crashed on mount for task def 181. | 24-05 schema vs live data |
| 5 | `47b03d4` | Completeness filter required actions to *exist* but not be configured, so `{type:'hardware', ref:''}` was sent and rejected. | 24-02 gate vs 24-05 UI (deeper) |
| 6 | `9218644` | Same filter accepted a hardware action with a `ref` but no `method`; a half-built action autosaved and **overwrote the working action list**. | as above |
| 7 | `7cd2734` + `4ac5a18` | **Two-part data-loss bug.** (a) Filtering incomplete assignments out of the payload *deleted* an already-saved incomplete assignment on the next autosave. (b) The editor re-seeded `fdaJson` from the server on **every** React Query refetch (window focus, post-save), discarding in-progress edits. Once (a) was fixed so incomplete work correctly stopped saving, (b) became visible — the assignment "disappeared" repeatedly. | 24-05 save model vs pre-existing editor refetch behaviour |

## 2b. Rig proof — TRIGA-11a (runs 478 / 480 / 481, 2026-07-27)

Sourceless toolkit 100, task definition 186, action list assembled in the task editor via the
one-pick **Read detector** widget. No `learning_cage`, no `handler` enum, no Python callback.

### Aggregate correctness — 144 triggers, 63 writes, ZERO errors

| Check | 478 | 480 | 481 |
|---|---|---|---|
| `TOUCH_INT` (assert / deassert) | 19 / 19 | 41 / 41 | 12 / 12 |
| licker writes | 19 | 34 | 10 |
| guard leaks (`pin_number is None` → wrote) | 0 | 0 | 0 |
| wrong `LICKER` index | 0 | 0 | 0 |
| written value ≠ captured `level` | 0 | 0 | 0 |
| `pi_timestamp` ≠ triggering tick | 0 | 0 | 0 |

**Requirements demonstrated on hardware:**
- **TRIGA-12** — `LICKER*` trackers exist for a registry-declared detector. Capability matching
  works; the `isinstance` identity bug is gone.
- **TRIGA-17** — pin → tracker selection correct on every one of 63 writes, with three different
  electrodes interleaved. The cross-talk negative is earned from real interleaving rather than a
  staged phase.
- **TRIGA-18** — `{device_name}` resolved at run time to `LICKER` from the device object. No
  pilot-specific string in the stored JSON.
- **TRIGA-19** — the written level always came from `detect_change`'s own reply, never the IRQ edge.
- The `pin_number != null` guard blocked **all 72** no-change edges across the three runs.

**The 50/50 assert/deassert split is now visible in data** and confirms the IRQ handshake: reading
the touch-status register is itself what deasserts the line, so every touch yields one real change
edge and one `(None, None)` edge. This is why the guard's `right` must be JSON `null` and not `0` —
half of all interrupts depend on it, and `0` is a valid electrode.

### Save-time negative suite — 8/8 (live API, 2026-07-27)

Canonical payload → **201**. All seven invalid payloads → **422** with a specific message naming the
offending element: empty `trigger_name`; unknown `trigger_name` (lists valid sources); hardware
action with no `method` (**TRIGA-16**); unknown hardware ref; undeclared `output` slot; unknown
action type; `{device_name}` without `source_ref`.

### Finding A — one live electrode is silently discarded

`pin_number` distribution over runs 480/481: **`{1, 2, 3, 4}` — never `0`.** The four spouts are
wired to MPR121 channels **1–4**; channel 0 is unwired.

`check_for_detectors` builds `f"{device_name}{i}" for i in range(num_detectors)`, so
`num_detectors: 4` creates `LICKER0…LICKER3`: `LICKER0` can never fire, and **channel 4's writes go
nowhere** — 9 events lost across the two runs, with no visible exception and no event.

**Root cause of the silence, traced 2026-07-29 (corrects "no exception" above — one *was* raised):**
the unknown-key guard fires as designed. `mics_task.py:717-721` raises
`KeyError("view action: key 'LICKER4' (from template '{device_name}{pin_number}') not found in
self.view.view. Available: [...]")`. `_run_trigger_actions` (`mics_task.py:1323-1328`) is
`try`/`finally` with no `except`, so it propagates into `execute_trigger`
(`task.py:285-298`), whose `except KeyError: self.logger.debug(f"No valid trigger for {pin}")`
is meant for a missing `self.triggers[pin]` lookup but wraps the callback invocation as well.
The error was therefore caught by the wrong handler and logged at DEBUG as an unrelated message
naming neither the key nor the cause. This also explains why the worker thread survived and the
other 63 writes succeeded: the exception never reached `process_queue`. Raised as **DVK-10**.

Not noise: channel 4 produced clean `1,0` pairs in its own dedicated ~0.6 s window matching the
sequential touching order, in both runs. Not a dead electrode either — a dead electrode would leave
three channels responding; four responded.

**This is the phase's own failure class arriving through an out-of-range index rather than a wrong
name, and it is the strongest existing argument for Phase 25's DVK-06 preflight key resolution.**

Naming cannot simply be offset: the key is `{device_name}{pin_number}` where `pin_number` is the raw
hardware index, so a tracker's name **must** equal its channel index. The fix is to create trackers
only for the wired channels while keeping true-index names (`LICKER1…LICKER4`). Deferred to Phase 25
as **DVK-09** — it is a derivation-format question, which is DVK-01's remit.

### Finding B — `detect_change` reports only one electrode per interrupt

`i2c.py:843` ends `return changes[0] if changes else (None, None)`, then updates `self.prev` to the
full current state. When two electrodes change between reads the higher-index transition is
**silently swallowed and unrecoverable**.

Observed directly: in run 478 (electrodes touched together) `LICKER2` logged five `0`s and never a
`1` — its rises were lost while `LICKER1` was changing. In runs 480/481 (one electrode at a time)
every channel produced clean alternating `1,0` pairs.

**Pre-existing and out of scope** — `i2c.py` is off-limits and unchanged, and legacy `detectedLick`
had identical behaviour. Recorded because it presents as "that electrode is flaky" rather than as a
software constraint, and because it bounds what simultaneous multi-spout licking can measure.

### Operational note — runs end after ~20 s

Every run of task definition 186 lasts **20.1 s** (5 trials × ~4 s), then stops. Runs 476/477/479
logged zero touch events purely because touching began after the task had ended; the GPIO callbacks
remain assigned afterwards, which is why run 476 produced a terminal traceback with no matching
events. No hardware fault and nothing intermittent. Raise the protocol step's trial limit for longer
test sessions.

---

### Defect 8 — found on hardware, run 476 (2026-07-27, wave 3)

**`int(None)` in `log_action` permanently killed the trigger worker thread.**

```
mics_task.py:506  _capture_output   -> self.flags[name].set(value)
logging_utils.py:32  wrapper        -> value = int(args[0]) if args else self.value
TypeError: int() argument must be ... not 'NoneType'
```

Chain: `detect_change()` returns `(None, None)` when the IRQ fired but no electrode changed →
`unpack_output` writes `pin_number=None` → `Tracker.set(None)` → `@log_action` coerces with a bare
`int()` → TypeError.

**Severity is the thread death, not the exception.** `Task.process_queue` (`task.py:262-266`) is a
bare `for ... in iter(queue.get, 'END')` loop with **no exception handler**, so the raise escapes
the loop and the worker dies. Every subsequent trigger is silently dropped for the rest of the
session. Run 476 produced **zero** `LICKER` events and zero touch events in 39 documents — just a
clean 5-second `trial_onset → play_led` loop.

With `EITHER_EDGE` this is not an edge case but **half of all interrupts**: reading the touch-status
register is itself what deasserts the IRQ line, so every real touch yields one change edge and one
no-change edge.

**Why no test caught it.** `test_trigger_assignments.py` stubs flags with `_FlagTracker`, which
exists specifically to avoid the `@log_action` path ("requires a working event_dispatcher"). The
decorator was therefore never exercised on a captured value. New `tests/test_log_action_values.py`
tests the real decorator on a real `Tracker`, including the `None` sentinel and electrode 0.

**Fix** (`logging_utils.py`, deployed + md5-verified): coerce inside `try/except (TypeError,
ValueError)` and log the raw value when coercion fails. Preserves int coercion for existing
consumers, and also covers the wider class opened by FDA `output` capture — a float or string
return value would have raised identically.

**Not fixed, recommended:** `process_queue` has no exception handler at all. Any exception in any
trigger callback permanently disables all trigger processing with no operator-visible signal. That
is a systemic fragility in `task.py`, outside this phase's scope — flagged for a decision.

---

### Design decision recorded (reversal)

Fix 7 **reversed** an earlier decision. When first asked how the editor should handle a
half-built assignment, the chosen option was *"filter incomplete out of the save payload"*.
That option's stated cost was "a partial assignment is lost on reload". The unforeseen and
materially worse cost was that it **deleted already-saved incomplete assignments**. The
rejected option — *hold the save entirely while anything is incomplete* — is what now ships.

**Current semantics:** while any trigger assignment lacks a `trigger_name`, an action, or a
configured `ref`+`method`, the editor performs **no PUT at all** and the status line reads
`Not saved — finish or remove trigger '<name>'`. Unrelated edits pause too; that is the
accepted cost, because it cannot destroy work.

### Backend gap not yet fixed

`fda_validation` does **not** validate a `hardware` action's `method` — `CALLABLE_METHODS`
is only checked for `type:"method"`. So `method: ""` returns 200 and becomes a silent no-op
on the Pi, the exact failure class TRIGA-07 exists to prevent. The UI is currently the only
guard. AST metadata for hardware libs already exists, so the data is available. **Add to
the re-plan.**

---

## 4. Infrastructure incidents (unrelated to phase 24 code)

1. **Orchestrator ran a stale image with an expired JWT.** `prefs.json` is baked in at build
   time (`build:` with no volume mount), so a token updated on the host on 2026-07-26 never
   reached the container; the baked token expired 2026-07-15. Every `HANDSHAKE` backend sync
   and every run start returned 401 for ~12 days. Fixed by `docker compose up --build -d
   orchestrator`. **`docker compose up -d` silently reuses the old image — credential
   rotation requires `--build`.** Consider bind-mounting `prefs.json`.

2. **`mics_api` has no bind mount either.** `docker exec mics_api pytest` runs the *image's*
   copy of the tests, not the working tree. Test edits require `docker compose up --build -d
   api` first or results are meaningless.

3. `KeyError: 'Modules'` on a legacy plugin (`elastic_test`) — pre-existing and unrelated.
   `_inject_backend_toolkit_spec` returns early when `is_backend_authored` is false
   (`orchestrator_station.py:833`), so source-based toolkits never receive `HARDWARE`.

4. `TypeError: 1 << None` — `pilot_hardware_config` row for `Mid_LED` had `"pin": null`.
   Data, not code. Nothing validates a null pin before dispatch (Phase 13 `preflight_validate`
   territory).

---

## 5. System state at handoff

**Deployed to Pi** (`~/Apps/mice_interactive_home_cage`, md5-verified, pilot restarted 16:57):
```
autopilot/autopilot/tasks/fda_vocabulary.py     (new)
autopilot/autopilot/tasks/mics_task.py
autopilot/autopilot/tasks/learning_cage.py
tools/validate_fda.py
tests/test_fda_vocabulary.py                    (new)
tests/test_load_fda_from_json.py
tests/test_trigger_assignments.py
tests/test_validate_fda.py
```
`hardware/i2c.py` and `tasks/task.py` verified **byte-identical** to the mirror (non-git
SSH diff — the `pi-deploy` skill forbids git in `pi-mirror`).

**Containers:** all rebuilt and current (`api`, `web_ui`, `orchestrator`).

**Registry additions (new this session):**

| id | module | class | lib | pilot-1 config |
|---|---|---|---|---|
| 7 | `MPR121` | `Touch_Detector` | i2c.py | `{num_detectors:4, device_name:"LICKER", address:true}` |
| 8 | `TOUCH_INT` | `Digital_In` | gpio.py | `{pin:8, pull:1, trigger:"B", polarity:1, record:false}` |

Both attached to toolkit 100 (`source_less_toolkit`, `hardware_module_ids = [1,2,3,5,6,7,8]`).

**Known config collisions on pilot 1:** `Left_LED` and `Right_LED` both pin 11;
`Mid_LED` and `Solenoid` both pin 12.

**Legacy DB rows still present** (both are inert `handler`-format assignments that 422 the
save gate and crashed the editor before fix 4):

| id | display_name | owner | content |
|---|---|---|---|
| 181 | source_less_toolkit FDA | — | 1 × `digital_input` |
| 185 | GILI FDA | Gili | 3 × `touch_detector` |

Cleanup (not run — 185 belongs to another user):
```sql
UPDATE task_definitions SET fda_json = jsonb_set(fda_json::jsonb, '{trigger_assignments}', '[]')
WHERE id IN (181, 185);
```

> **TRIGA-06 asserted task def 185 was the only row with non-empty `trigger_assignments`,
> based on a live DB check on 2026-07-26. That was wrong — 181 has one too, and it caused
> three of the seven defects above. Re-run the query rather than trusting the recorded
> finding.**

---

## 6. Immediate next steps

1. **Run the 41 Pi tests** (user-only; `autopilot` unimportable on dev host).
2. **Re-plan 06/07/08** — see `24-REPLAN-BRIEF.md`. Use `/gsd:discuss-phase 24`, not
   `--gaps`: two requirements need rewording and one needs a new home, which is
   requirement-level drift that `--gaps` does not handle.
3. Optionally clear legacy rows 181/185.
4. Decide on the duplicate-`set` observation (§2) before real data collection.
