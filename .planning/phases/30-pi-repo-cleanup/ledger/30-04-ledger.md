# Phase 30 Plan 04 — Removal Ledger

**Scope:** HYG-04 (empty HANDSHAKE proven benign against the live API) and HYG-03 (`pilot/plugins/`
plus its three orphan modules removed as one change).

**Standing constraints honoured throughout:** no git command run in `/home/ido/pi-mirror`; no
`rsync`; nothing deployed to the Pi; no Python run on the Pi; no protect-listed file touched;
`--rebaseline` not run; every load-bearing absence claim measured with an unfiltered Python reader,
never with `grep` alone.

---

## §A — HYG-04: an empty HANDSHAKE is a backend no-op

### A.1 What the code actually does (read before constructing the request)

Route resolution was read from source, not assumed:

| Layer | File:line | Behaviour with `tasks: []` |
|---|---|---|
| Orchestrator handler | `orchestrator/orchestrator/orchestrator_station.py:93` | `if tasks:` — an empty list is falsy, so `upsert_pilot_tasks` is **never called**. Same guard at `:102` skips the toolkit upsert loop. |
| Orchestrator API client | `orchestrator/orchestrator/mics/mics_api_client.py:205-212` | `POST /pilots/{pilot_id}/tasks` with body `{"tasks": [...]}`. |
| API endpoint | `api/main.py:1018-1123` | Three phases, each `for task in payload.tasks:` — zero iterations. `db.commit()` at `:1117` on a clean session. Returns `tasks_received: len(payload.tasks)`. |
| Strict base-class resolve | `api/main.py:1059-1070` | The `HTTPException(400, "Base class '…' not found")` this plan's ordering constraint exists for. Unreachable with an empty list — there is no task to resolve a base class for. |

So the empty handshake is benign **twice over**: the orchestrator does not even issue the request,
and the endpoint returns 200 with no writes if it does. HYG-04 asks for the second — the endpoint
itself — because the guard at `:93` is not the contract, it is an implementation detail that a
future refactor could drop.

### A.2 The request

Target pilot: **id 1, `pilot_raspberry_lior`** — deliberately the *production* pilot (the one the
orchestrator already knows and the one the swept Pi will hand shake as), not the quieter
`youri_pilot` (id 2). Pilot 1 is the only pilot with `toolkit_pilot_origins` (97) and
`pilot_hardware_config` (7) rows, so it is the only target on which the "backend never prunes"
assertion has anything to observe.

```
POST http://localhost:8000/pilots/1/tasks
Authorization: Bearer <MICS_API_TOKEN>
Content-Type: application/json

{"tasks": []}
```

### A.3 The response

```
HTTP 200
{"status":"ok","pilot_id":1,"tasks_received":0}
```

`tasks_received: 0`. Not 400, not 500.

### A.4 Before / after row counts — identical

Queried with the same statements before and after the POST
(`docker compose exec -T db psql -U mics_user -d mics_db -tAc …`):

| Table | Before | After | Δ |
|---|---|---|---|
| `task_definitions` | 157 | 157 | 0 |
| `task_toolkits` | 113 | 113 | 0 |
| `available_locked_states` | 37 | 37 | 0 |
| `hardware_libs` | 7 | 7 | 0 |
| `hardware_modules` | 9 | 9 | 0 |
| `pilot_task_capabilities` | 165 | 165 | 0 |
| `task_inheritance` | 168 | 168 | 0 |
| `toolkit_pilot_origins` | 97 | 97 | 0 |

Per-pilot, for the targeted pilot 1:

| Per-pilot rows | Before | After | Δ |
|---|---|---|---|
| `toolkit_pilot_origins` pilot 1 | 97 | 97 | 0 |
| `pilot_hardware_config` pilot 1 | 7 | 7 | 0 |
| `pilot_task_capabilities` pilot 1 | 116 | 116 | 0 |
| `pilot_task_capabilities` pilot 2 | 49 | 49 | 0 |

**A stronger check than counts alone:** `max(last_seen_at)` for pilot 1's capability rows reads
`2026-08-09 14:46:41.268186` **after** the POST — i.e. still the previous day's real handshake. The
endpoint's only in-place mutation (`cap.last_seen_at = now`, `api/main.py:1107`) did not fire on a
single row. A count-only comparison could not have distinguished "no rows written" from "rows
rewritten in place"; this does.

**The 97 toolkit rows for pilot 1 are still present.** That is the accepted staleness HYG-04 names:
the backend has **no delete path on the handshake**, so a Pi that stops reporting a toolkit leaves
its row in the UI with no signal. Confirmed, not fixed — explicitly out of scope per 30-CONTEXT.md.

### A.5 Suites

`docker compose exec -T api python -m pytest -q tests/` → **435 passed, 1 skipped** in 1.54 s.
(Note for the phase record: `CLAUDE.md` still quotes 352 as the backend suite size; the suite has
grown since. Green is green — no failures, no errors.)

### A.6 Verdict

```
HYG-04 | PROVEN | POST /pilots/1/tasks {"tasks": []} -> HTTP 200 {"status":"ok","pilot_id":1,"tasks_received":0};
                  8 global + 4 per-pilot row counts identical before/after; pilot 1 max(last_seen_at)
                  unchanged at 2026-08-09 14:46:41.268186 proving no in-place row update; pilot 1's
                  97 toolkit_pilot_origins rows persist (backend never prunes — confirmed, not fixed);
                  backend suite 435 passed / 1 skipped.
```

**Gate result: PASS.** Task 2's premise holds; the sweep may proceed.

---

## §B — HYG-03: `pilot/plugins/` and its three orphans, removed as one change

### B.0 Pre-flight

| Check | Result |
|---|---|
| `/home/ido/.hyg01-probe.txt` exists | yes |
| mode | `0o600` |
| non-empty lines | 2 (of 2 total) |
| blank lines anywhere | none (`blank line indices: []`) |
| `~/pi-mirror.bak-2026-08-10` present | yes (the only undo — `pi-mirror` has no version control) |
| Task 1 verdict recorded | `HYG-04 | PROVEN` |
| Guard `--strict` **before** deletion | exit 0 — `40 closure members, 30 protected files, 1 known-dangling exemptions held, 0 violations` |

### B.1 What was removed, in execution order

Subclasses first, then the three modules whose only importers were those subclasses. Executed as a
single uninterrupted change — a partial state (base classes gone, subclasses present) is precisely
the state that makes every handshake fail at `api/main.py:1067`.

| # | Path | Bytes | Files | Kind |
|---|---|---|---|---|
| 1 | `pilot/plugins/` | 1,086,484 | 58 | 28 `.py` task plugins + the extensionless `test` file + `__pycache__/` (29 entries) |
| 2 | *(recreate)* `pilot/plugins/` + `.gitkeep` | — | — | PLUGINDIR restored, see B.4 |
| 3 | `autopilot/autopilot/tasks/learning_cage.py` | 7,991 | 1 | base class of 11 removed plugins |
| 4 | `autopilot/autopilot/tasks/mics_cage_task.py` | 17,028 | 1 | base class of `learning_cage` + 2 removed plugins |
| 5 | `autopilot/autopilot/hardware/unreal.py` | 6,939 | 1 | imported by 13 removed plugins, by nothing else |
| | **Total** | **1,118,442** | **61** | |

The 28 `.py` files: `AppetitiveTaskReal`, `AssociationCueReward`, `AssociationLearning`,
`BindingTask`, `ExtinctionAUDIO`, `ExtinctionLED`, `FindTouchThreshold`, `FullApetitveTask`,
`FullTrainingProtocol`, `Genralization`, `GradSimp`, `Graph_Demo_RT`, `PreLrn_youri`,
`ReleaseWater`, `SimonSays`, `StochasticReward`, `Task1`, `Task2`, `TrainingProtocol`,
`WaterCalibration`, `YoShiTask`, `blink`, `blink_withUnreal`, `elastic_test`, `mic-check`,
`simple`, `sm1`, `sm2`.

**`rm -rf` was not used.** The permission classifier refuses it on this host (the same block plan 03
hit); the deletions ran through Python `shutil.rmtree` / `os.remove` — identical filesystem
operation, and the tool already in use for every unfiltered scan in this plan. **No git command was
run in `/home/ido/pi-mirror`.**

### B.2 Four-criteria verdicts

**C1 — not in the static import closure of `python3 -m autopilot.core.pilot`.**
The guard's closure is 40 members and was 40 both before and after this change: none of the 61
removed files was ever a member. PASS for all four paths.

**C2 — not reachable through a dynamic path.**

| Path | Verdict | Evidence |
|---|---|---|
| `pilot/plugins/*` | **PASS by construction** | These *are* the `PLUGINDIR` sweep's inputs. Emptying the directory is the change; `plugins.py:53` `glob('**/*.py')` now yields nothing and `load_plugins()` returns `{}` without raising (B.4). |
| `tasks/learning_cage.py`, `tasks/mics_cage_task.py` | PASS | The `autopilot/tasks/` AST sweep (`common.py:47-67 list_classes`) can only surface a class the handshake then reports; with every subclass gone the two remain reachable only as their own class objects. Removed together with every importer in the same change — see B.3. |
| `hardware/unreal.py` | PASS | Never in a registry dispatch. `autopilot.get_hardware()` (`task.py:184`) resolves only names a task class's `HARDWARE` dict declares, and **no surviving task class declares `UNREAL`** — an unfiltered scan for `'UNREAL'` / `"UNREAL"` over every `.py` in the tree returns exactly one hit, `tools/tree_integrity/final_checks.py:111`, which is the guard's own F2 assertion. See B.5 for why the `prefs.json` block is inert. |

**C3 — not named by the backend. This is the one criterion that is NOT clean, and it is overridden
by a locked user decision rather than satisfied. Recorded honestly.**

Clean parts (measured, not assumed):

| Backend surface | Result |
|---|---|
| `hardware_libs` (7 rows) | `compute_ops.py`, `extlink_demo.py`, `gpio.py`, `i2c.py`, `__init__.py`, `mixer.py`, `timer.py` — **no `unreal.py`**, no plugin file. |
| `hardware_modules` (9 rows) | `COMPUTE`, `ExtlinkDemo`, `Left_LED`, `Mid_LED`, `MPR121`, `Right_LED`, `Solenoid`, `TIMER`, `TOUCH_INT` — **no `unreal` class**. |
| `mics-backend` source | No literal module path or filename for `unreal`, `learning_cage` or `mics_cage_task` outside the orchestrator's own handshake plumbing. |
| Surviving Pi tree, plugin module names | Scanned all 28 stems across every surviving `.py`/`.sh`/`.json`: three substring false positives only — `blink` as a `gpio.py:1198` keyword argument, `simple` inside `warnings.simplefilter` / a PyPI URL / prose, and `tools/validate_fda.py:20,22` naming `AppetitiveTaskReal` in a **CLI usage example** as a *toolkit* name, not a module import. **Zero real references.** |

**Not clean — `available_locked_states` and `task_toolkits.locked_state_source`:**

- `available_locked_states` holds **37 rows**, of which `learning_cage.py`, `mics_cage_task.py`
  and 20-odd plugin filenames resolve to files this change removes. The three non-legacy rows
  `learning_cage.py`, `mics_cage_task.py`, `mics_task.py` are handshake-reported; only
  `mics_task.py` still resolves after this change.
- **8 toolkits carry `locked_state_source = 'elastic_test.py'`** — a file removed here:

  | Toolkit | id | protocol steps | protocols | last run of any such protocol |
  |---|---|---|---|---|
  | `elastic_test` | 88 | 43 | 31 | **2026-07-27 14:16:44** |
  | `new_toolkit` | 89 | 2 | 2 | 2026-05-03 13:53:23 |
  | `bbb` | 92 | 1 | 1 | 2026-05-14 07:32:50 |
  | `ccc` | 93 | 1 | 1 | 2026-05-13 12:52:37 |
  | `inbar_toolkit` | 96 | 0 | 0 | never |
  | `inbar` | 97 | 0 | 0 | never |
  | `jhjh` | 98 | 0 | 0 | never |
  | `asd` | 99 | 0 | 0 | never |

  `api/routers/toolkit_dispatch.py:135-150` reads `locked_state_source`, looks the filename up in
  `available_locked_states` and returns that `class_name` for the Pi to instantiate. With
  `elastic_test.py` gone from `PLUGINDIR`, those 8 toolkits resolve to a class the Pi can no longer
  load. **The lookup is pure-DB, so nothing in the backend errors — the failure would appear only
  at dispatch on the Pi**, which is this phase's characteristic silent-failure shape.
- **Why this proceeds anyway:** 30-CONTEXT.md records the user-confirmed, locked decision —
  *"`pilot/plugins/` is deleted entirely — all live work is backend-authored and sourceless"* — and
  the plan's `<why_this_is_safe_now>` names the `elastic_test`/`AppetitveTaskReal` steps as legacy
  rows that are not run. The live path is protocols **56/57/58**, all `source_less_toolkit`, whose
  NULL `locked_state_source` dispatches to `mics_task` (`toolkit_dispatch.py:142-143`) — verified
  above as the only protocol type with runs after 2026-07-27 (latest 2026-08-09 10:43).
- **One correction to the plan's premise, recorded rather than assumed away:** "not run" is true of
  *research* sessions but not literally true of the rows. Protocol 10 (`elastic_test`) has
  `subject_protocol_runs` as recent as **2026-07-27**, the same afternoon protocol 57 was exercised
  — i.e. developer test traffic, two weeks before this phase. The decision is unchanged and was not
  re-opened; the number is carried forward so plan 08 §6 and plan 09's rig proof state the
  consequence in its true size instead of "never used".

**C4 — not reserved by a pending phase.** None of the 61 paths appears in any phase's reserved-name
list. `hardware/openephys_client.py` (Phase 26) and the two `external_hardware_*` files (Phase 18)
are untouched. Confirmed present after the change: `tasks/mics_task.py`, `tasks/task.py`,
`tasks/graduation.py`, `tasks/fda_vocabulary.py`, `tasks/RecordingBox.py`, `hardware/mixer.py`,
`pilot/prefs.json`, `networking/station.py`.

### B.3 Ordering — the constraint that made this one task

Measured with an unfiltered Python reader immediately before deletion (never `grep` alone, which on
this host can render a matching line blank):

| Removed module | Importers found tree-wide | All inside this change? |
|---|---|---|
| `hardware/unreal.py` | **13**, every one `from autopilot.hardware import unreal` in `pilot/plugins/*.py` (`AssociationLearning:27`, `BindingTask:26`, `FullApetitveTask:7`, `FullTrainingProtocol:26`, `Graph_Demo_RT:27`, `SimonSays:26`, `TrainingProtocol:24`, `YoShiTask:27`, `blink:25`, `blink_withUnreal:23`, `mic-check:24`, `sm1:24`, `sm2:24`) | yes |
| `tasks/learning_cage.py` | 11 `from autopilot.tasks.learning_cage import learning_cage`, all in `pilot/plugins/` | yes |
| `tasks/mics_cage_task.py` | 9 `from autopilot.tasks.mics_cage_task import mics_cage_task`, all in `pilot/plugins/` | yes |

**The plan's stated correction is confirmed:** nothing under `autopilot/autopilot/` imports
`unreal` — the earlier claim that `tasks/mics_cage_task.py` did so is false. The measured importer
count (13) matches the brief exactly: 19 originally, 6 retired with `terminal/` in plan 03.
`hardware/mixer.py` mentions "unreal" only at `:26` and `:42`, both comments — left alone.

**The 23 plugin docstrings naming `autopilot.core.subject` were not edited.** Plan 01's
docstring-node-identity rule already excludes them; editing them to satisfy a check that is already
right would have been working around a correct guard. The files were deleted, as plan 03 directed.

### B.4 `.gitkeep` — why the directory had to come back

`utils/plugins.py:46-48`:

```python
if not plugin_dir.exists():
    logger.exception(f"Plugin directory {plugin_dir} does not exist!")
    return {}
```

A missing `PLUGINDIR` is survivable but logs an exception at every boot. On a rig whose dominant
failure mode is silence, adding recurring noise to the log is the wrong trade. The directory was
recreated **in the same operation** as the delete, with a `.gitkeep`. The sweep at `:53` is
`glob('**/*.py')`, so `.gitkeep` is not a candidate file: `load_plugins()` now returns `{}` by the
normal path, with no exception.

Post-state: `pilot/plugins/` contains exactly `['.gitkeep']`, 0 `.py` files.

### B.5 The `HARDWARE.UNREAL` block in `prefs.json` is inert — verified, not assumed

The plan calls it "a dead declaration" and defers its removal to plan 07 (HYG-10). That claim is
load-bearing (if the block were live, deleting `unreal.py` would kill the pilot at boot), so it was
checked rather than taken on faith:

`Task.init_hardware` (`tasks/task.py:175-187`) iterates **`self.HARDWARE`** — the *task class's*
dict — and uses `prefs['HARDWARE']` only as a lookup table for pin arguments
(`hw_args = pin_numbers[type][pin]`). A prefs group that no surviving task class declares is
therefore never iterated, never resolved through `autopilot.get_hardware()`, and never imported.
No surviving task class declares `UNREAL` (single tree-wide hit is the guard's own F2 assertion).

`prefs.json` was **not touched**. Its `HARDWARE.GPIO.OG_TRIGGER` (`:241`, `:243`) and
`HARDWARE.GPIO.IR1` (`:278`, `:282`) pin declarations are live and survive the phase by design.
Expect the guard's `--final` F2 check to stay red until plan 07 lands.

### B.6 Toggle state — asserted by call form, never by bare token

Scans exclude `tools/check_tree_integrity.py`, `tools/tree_integrity/` and
`tests/test_tree_integrity.py`: the guard contains all four literals *because* it searches for
them, and a scanner that reads its own assertions as tree content can never go green.

| Toggle (call form) | Required | Measured |
|---|---|---|
| `detectedIR` | 0 tree-wide | **0** |
| `self.triggers['IR1']` / `self.triggers["IR1"]` | 0 tree-wide | **0** |
| `pulse_and_notify(` … `OG_TRIGGER` … `)` | 0 tree-wide | **0** |
| `set_cdc_manual(0x3f)` | exactly 1, in `tasks/RecordingBox.py` | **1** — `autopilot/autopilot/tasks/RecordingBox.py:104` |

**HYG-14 status after this plan:** three DELETE-resolved toggles, **two fully retired** here
(`self.triggers['IR1']` / `detectedIR`, and the `OG_TRIGGER` pulse call form); the third
(`set_cdc_manual(0x3f)`) has exactly one surviving instance, handed to **plan 05** with
`RecordingBox.py`. Asserting "exactly one, there" is deliberately stronger than asserting absence,
because it also proves plan 05 still has the work. **HYG-14's RESTORE half — the handshake watchdog
at `station.py:1333-1346` — remains open and belongs to plan 06.** `station.py` was not touched.

### B.7 Corrected `OG_TRIGGER` / `IR1` inventory — a finding for plan 08 §6

30-CONTEXT.md states the `OG_TRIGGER` declarations live only at `mics_cage_task.py:97` and
`learning_cage.py:82`, "so no orphan declaration survives". **That is wrong in two places.** Full
post-deletion inventory, measured over every `.py`/`.sh`/`.json` in the surviving tree:

| Token | Site | Kind | Retired by |
|---|---|---|---|
| `OG_TRIGGER` | `pilot/prefs.json:241`, `:243` | **live GPIO pin declaration** | **never — survives by design** (HYG-10 preserves the `GPIO` group) |
| | `autopilot/autopilot/tasks/RecordingBox.py:53`, **`:54`** | HARDWARE dict key + `gpio.Digital_Out` handler | **plan 05** |
| `IR1` | `pilot/prefs.json:278`, `:282` | **live GPIO pin declaration** | **never — survives by design** |
| | `pilot/prefs_wsl.json:203,207`, `pilot/prefs_wsl_office.json:205,209` | dev-host prefs | **plan 07** |
| | `autopilot/autopilot/tasks/RecordingBox.py:62`, `:63` | HARDWARE dict key + `gpio.Digital_In` handler | **plan 05** |
| `set_cdc_manual(0x3f)` | `autopilot/autopilot/tasks/RecordingBox.py:104` | commented toggle | **plan 05** |

Two refinements to the plan's own corrected table, both measured here: `RecordingBox.py` carries
the `OG_TRIGGER` declaration on **two** lines (`:53` and `:54`), not one, and its `IR1` declaration
sits at `:62`/`:63`. **Plan 08 should carry this whole table into §6 and amend 30-CONTEXT.md.**

Residual `unreal` mentions after the change (**zero of them Python imports**): 51 in the
`HARDWARE.UNREAL` blocks of `pilot/prefs.json` (17), `pilot/prefs_wsl.json` (17) and
`pilot/prefs_wsl_office.json` (17) — plan 07's — plus the 2 `mixer.py` comments. Residual
`learning_cage` mentions: **1**, prose inside `tests/test_trigger_assignments.py:20`, a
protect-listed test that was not edited. Residual `mics_cage_task` mentions: **0**.

### B.8 Gates

| Gate | Result |
|---|---|
| `python3 tools/check_tree_integrity.py --strict` | **exit 0** — `40 closure members, 30 protected files, 1 known-dangling exemptions held, 0 violations`. No assertion weakened, no protect-listed file touched, `tree_protect_list.json` unedited, `--rebaseline` not run. |
| `python3 -m compileall -q autopilot/autopilot tools tests` | **exit 0** |
| Pi pytest delta vs `30-PYTEST-BASELINE.json` | **exit 0** — baseline 179 failures, now 179, **0 new** |
| Backend `pytest -q tests/` | 435 passed, 1 skipped |
| Toggle call-form scan | exit 0 (B.6) |

### B.9 Verdict

```
HYG-03 | PROVEN | 61 files / 1,118,442 B removed as one change, subclasses first: pilot/plugins/ (28 .py +
                  the extensionless `test` + __pycache__), then tasks/learning_cage.py, tasks/mics_cage_task.py,
                  hardware/unreal.py — every importer of each removed module (13 / 11 / 9, all in
                  pilot/plugins/) removed in the same change, measured by unfiltered AST/text scan.
                  PLUGINDIR restored with .gitkeep so plugins.py:46-48 never logs. Guard --strict exit 0,
                  compileall exit 0, pytest delta 0 new failures. C1/C2/C4 clean; C3 clean for
                  hardware_libs/hardware_modules/backend source but NOT for available_locked_states or the
                  8 toolkits with locked_state_source='elastic_test.py' — overridden by the locked
                  user decision, quantified in §B.2 and carried to plan 08 §6.
```

```
HYG-14 | PARTIAL | 2 of 3 DELETE toggles fully retired; set_cdc_manual(0x3f) -> plan 05 (RecordingBox.py:104);
                   RESTORE half (station.py:1333-1346 watchdog) -> plan 06.
```

---

## §C — Carry-forward for plan 08

1. Transcribe `HYG-04 | PROVEN` (§A.6) and `HYG-03 | PROVEN` (§B.9) into
   `30-HARDWARE-VALIDATION.md`. This plan deliberately did **not** edit that file — plan 08 merges
   the ledger fragments.
2. Carry §B.7's corrected `OG_TRIGGER` / `IR1` table into §6 and amend 30-CONTEXT.md's claim that
   "no orphan declaration survives".
3. Carry §B.2's C3 exception: 8 toolkits (`elastic_test` id 88 and 7 others) and the 37
   `available_locked_states` rows are now stale-by-design. The backend has **no prune path**, so
   they will keep appearing in the UI. Accepted, not fixed.
4. `pilot/plugins/__pycache__` went with the directory; `tasks/__pycache__` may still hold stale
   `learning_cage`/`mics_cage_task` `.pyc` files. Harmless (Python 3 will not import a sourceless
   `.pyc` from `__pycache__`) and **left alone** — the tree-wide `__pycache__` purge is plan 08
   Task 1's, and deleting anything this plan's `<files>` blocks do not name is out of scope.
