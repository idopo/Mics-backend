# Phase 23 — Hardware Validation Log

**Date:** 2026-08-03
**Rig:** `pilot_raspberry_lior` (132.77.72.28), session 113, pilot 1
**Task definition:** 186 `source_less_toolkit FDA_tes_interuuppt` (toolkit 100)
**Runs:** 535, 541, 543, 544, 545, 546, 547
**Operator:** user (all pilot starts/stops and Pi-side execution — per hard rules)

Records what phase 23 **proved on the real rig**, what it **did not**, and the exact deployed
state at close. Evidence is ES documents and orchestrator logs, not assertion.

---

## 1. Deployed state at close

### Pi (`~/Apps/mice_interactive_home_cage`) — verified byte-identical to `~/pi-mirror`

| File | sha256 (12) | Change |
|---|---|---|
| `autopilot/autopilot/tasks/fda_vocabulary.py` | `c28d086110cb` | `"compute"` added to `VALID_ACTION_TYPES` |
| `autopilot/autopilot/tasks/mics_task.py` | `ccb4e3a56262` | `compute` branch in `_build_action_callable` + `_build_state_method` |
| `tools/validate_fda.py` | `723941b12bac` | `compute` branch in `_validate_actions_list` |
| `autopilot/autopilot/utils/logging_utils.py` | `1fd9ff0967ed` | `value_raw` emitted for float captures |

Each file was diffed against the Pi's copy **before** pushing; the only differences were this
phase's own edits. No `--delete`, no full-mirror sync, no git anywhere near the Pi.

### Database

```
hardware_libs        45  "Compute Ops"  kind=compute
hardware_lib_versions 41  v1  state=stable  declared_imports=["random"]
hardware_modules     24  COMPUTE  class_name=ComputeOps
toolkit_hardware_libs      38 toolkits link lib 45
task_toolkits 100    hardware_module_ids=[1, 5, 6, 7, 8, 24]
pilot_hardware_config 15  pilot 1  COMPUTE  {"class_name": "ComputeOps"}
```

### Elasticsearch (`132.77.73.217:9200`, `event_log_v2`)

`event.event_data.value_raw` added as `float` (additive mapping update; no reindex, 2,918,951
documents untouched). `value` remains `long`, `result` remains `float`.

---

## 2. PROVEN on hardware

### CMP-01/02/05 — compute action executes on the Pi

Run 541 onward: `Modules {"id": "COMPUTE", "func_name": "random_float", "result": <float>}`
appears once per entry to the `rand` state. The action loads, resolves through
`self._semantic_hw`, and calls the op. FDA-JSON-v2 with a `compute` action runs on the rig with
no platform code change.

### CMP-06 — variable written and read across the FDA

`Tracker {"id": "my_rand", ...}` follows every compute call, and the transition
`my_rand >= 0.5` gates on it. Run 541 is the clean proof that the *value used* is the real
float, before the logging fix existed: draws `0.656` and `0.504` advanced, `0.327` did not.

### Both guarded branches fire; recomputed once per state entry

Runs 543–547, **41 draws total, 0 routing violations**:

| Run | Trials | Draws | Retries (<0.5) | Advances (≥0.5) | Violations |
|---|---|---|---|---|---|
| 543 | 5 | 7 | 3 | 4 | 0 |
| 544 | 5 | 8 | 4 | 4 | 0 |
| 545 | 5 | 5 | 1 | 4 | 0 |
| 546 | 5 | 9 | — | — | 0 |
| 547 | 5 | 12 | — | — | 0 |

Every draw `< 0.5` was followed by `rand → play_led`, every draw `>= 0.5` by
`rand → trial_onset`. Run 544 contains a 4-deep retry chain
(`0.188, 0.308, 0.318, 0.022` then `0.619`) — the exact case that previously hung the task.
Re-entering `rand` redraws, confirming entry_actions re-run per entry. Trial counter reached 5
in every run: retries loop through `play_led` without touching `trial_onset`, so they do not
inflate trial counts.

Draw range across runs 546–547: min `0.115`, max `0.939`, mean `0.498` (n=21) — consistent with
uniform `random_float(0, 1)`.

### CMP-17 — version resolution and `test_import` round trip

Run 535 orchestrator log, 5 libs dispatched, all clean:

```
HARDWARE_LIB_TEST_RESULT from pilot_raspberry_lior: version_id=13 ok=True error=None
                                                    version_id=26 ok=True error=None
                                                    version_id=16 ok=True error=None
                                                    version_id=25 ok=True error=None
                                                    version_id=17 ok=True error=None
```

`GET /api/toolkits/100/hardware-libs` resolves `Compute Ops → version 41, state=stable,
reason=toolkit_default`, alongside the five hardware libs.

### CMP-04 — auto-provisioning

`pilot_hardware_config` row for COMPUTE did not exist after linking. Preflight created it
(`id 15`, `{"class_name": "ComputeOps"}`) and returned `{"ok": true, "issues": []}` — the
self-heal path works against a real session/pilot.

### No regression to existing hardware

Run 535 (the pre-compute touch-detector task) completed with 5 trials and 53 ES documents after
all Pi changes were deployed. During the run-541 hang, the pilot continued logging LICKER1 and
TOUCH_INT events — compute never interfered with detector, IRQ, or trigger processing.

### `value_raw` closes the float record (runs 546–547)

21/21 compute draws carry a `value_raw` matching their `COMPUTE` result exactly. Aggregation
over the field returns `count=21, min=0.1148, max=0.9391, avg=0.4978`, proving it is indexed
and queryable, not merely stored. `_source` retains full double precision; only the indexed
value is float32 (~7 significant digits).

---

## 3. NOT proven — open

### The planned gonogo task was never built

This plan's must_haves name "the gonogo random-target logic". What was actually validated is an
equivalent but **different** FDA: a `random_float` draw gating a transition, with a retry loop.
It exercises the same machinery (compute action → variable → transition → both branches) but
gonogo itself was not built or run. **Treat the mechanism as proven and gonogo as unvalidated.**

### CMP-16 is only partially met — the Hardware_Event omits its args

The must_have requires "a Hardware_Event with the op **and its args**". Actual payload:

```json
{"id": "COMPUTE", "result": 0.15942958353171488, "func_name": "random_float"}
```

`log_action`'s Hardware branch does `event_data.update(kwargs)` and never records positional
args; compute calls pass positionally, so `random_float(0, 1)` logs no `0, 1`. Both events do
reach the log per call, and the result is now faithful — but the *inputs* to each op are not
recoverable from the event log. Scientifically material for any op whose output cannot be
inverted from its result.

### CMP-18 — researcher-authored compute lib upload not exercised

All runs used the seeded `Compute Ops` lib. Uploading a *researcher-authored* compute lib
through the GUI and seeing its ops in the picker was never performed. The upload path has unit
coverage (`test_hardware_lib_kind.py`) but no hardware proof.

### Non-numeric compute outputs would be silently dropped by ES (latent)

`event_data.value` is `long`. Probed directly against ES (throwaway index, deleted):

| Sent | Result |
|---|---|
| `123`, `null`, `[1,2]`, `"456"` | indexed |
| `0.75` | indexed, truncated to `0` |
| `true`, `"left"`, `["a","b"]` | **rejected, HTTP 400** |

`ElasticSearchDateHandler._index` swallows the failure (`except Exception: print(...)`), so a
rejected document is **lost with no surfaced error**. Two seeded ops can produce non-numeric
values: `random_choice` (e.g. `["left","right"]`) and `assign`. **Latent** — no task uses them
yet. Bool is safe *because* of the existing `int()` coercion: raw `true` is rejected by ES,
`int(True)=1` is not, so that coercion is load-bearing. Fix mirrors `value_raw`: emit a
`value_str` keyword field and put `null` in `value`.

### `hot_update_fda` variable collision (predicted, unconfirmed)

Plan 23-04 predicted by inspection that `load_fda_from_json`'s collision guard breaks
`hot_update_fda` re-declaring an existing variable name. Not triggered in any run today.

### Pi-side unit tests still unrun

`/home/ido/pi-mirror/tests/test_compute_ops.py` and `test_fda_vocabulary.py` were never copied
to the Pi or executed (`autopilot` is unimportable on the dev host). All Pi evidence here is
from live runs, not unit tests.

---

## 4. Defects found and fixed during validation

Seven, every one of which reached the rig or the GUI before anything complained:

| # | Defect | Fix |
|---|---|---|
| 1 | `ComputeActionFields` linked `/react/hardware-libs-ui` under `basename="/react"` → `/react/react/...` | path corrected |
| 2 | Autosave fired mid-authoring; a just-added action hard-422'd (rule from 24-08) | hold save while any state action is half-built |
| 3 | Numeric inputs coerced per keystroke; `Number("0.")`→`0` ate the decimal — float args and literals were int-only | `NumericInput` + `numericDraft.mts`, 7 tests |
| 4 | Editing arg[1] before arg[0] made a sparse array → `[null, 1]` → `random_float(None, 1)` TypeError on the rig | `withArgAt` rebuilds dense, 8 tests |
| 5 | Null compute arg passed all validation and failed only at run time | hard 422 naming the position, 4 tests |
| 6 | `rand` deadlocked: only exit gated on a variable its own entry_actions froze | preflight `state_wait_unsatisfiable`, 9 tests |
| 7 | `int(0.656)=0` + `value` mapped `long` — every captured float recorded as `0` | `value_raw` float field, Pi emits it |

Also: `test_seed_compute_ops_lib_idempotent` deletes the compute lib and module from the live DB
and re-seeds, minting new ids. With compute now linked to 38 toolkits that would leave real
toolkits pointing at dangling ids; it now skips when any toolkit references the lib.

---

## 5. Judgement

The **mechanism** is proven end to end on hardware: a compute action dispatches, executes,
writes a variable, gates a transition through both branches, and is recorded faithfully in
Elasticsearch. Phase 23's core claim holds.

Three caveats belong on the record: the gonogo task itself was never built, compute op **args**
are absent from the event log (CMP-16 partial), and non-numeric compute outputs would be
silently dropped by ES if any task starts using `random_choice` or `assign` with strings.
