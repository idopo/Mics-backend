# Phase 30 Plan 05 — Removal Ledger

**Scope:** HYG-06 (registry sweep collateral in `autopilot/tasks/`) + HYG-05 (camera subtree, both
sides of the DB boundary) + the closure of HYG-14's third DELETE toggle.

**Executed:** 2026-08-10
**Tree:** `/home/ido/pi-mirror` (no git command was run there at any point)

---

## A. Task 1 — Registry sweep collateral (HYG-06)

### A.1 Removed paths

| # | Path | Bytes | md5 (pre-removal) | Top-level classes |
|---|---|---|---|---|
| 1 | `autopilot/autopilot/tasks/children.py` | 11,245 | `2a4cd01fb47bae14c2187b3ba875506e` | `Child`, `Wheel_Child`, `Video_Child`, `Transformer` |
| 2 | `autopilot/autopilot/tasks/nafc.py` | 16,768 | `3fd0fd66c54fd0013e9eaa49684db0fb` | `Nafc` |
| 3 | `autopilot/autopilot/tasks/gonogo.py` | 8,110 | `3ca98a8975180634e57cd8b847cf451a` | `GoNoGo` |
| 4 | `autopilot/autopilot/tasks/free_water.py` | 5,916 | `342d6549bfccebae240cbea35148a670` | `Free_Water` |
| 5 | `autopilot/autopilot/tasks/test.py` | 14,814 | `1c97ca4217651dabd4f550d44ed4fd30` | `DLC_Latency`, `DLC_Hand` |
| 6 | `autopilot/autopilot/tasks/RecordingBox.py` | 3,542 | `b33fbc87c591f1b9a239e6eb5228bf40` | `RecordingBox` |
| 7 | `autopilot/autopilot/tasks/protocol_scripts.py` | 110 | `642726f3fdca0082fed85ec9bf1bb8a2` | *(none)* |

**Total: 7 files, 60,505 bytes.** Deleted in the plan's stated order (importers first —
`children.py` is the module that drags in `cameras.py` and `usb.py`), via Python `os.remove`.

**Survivors in `autopilot/autopilot/tasks/`, confirmed present after the deletions:**
`__init__.py`, `fda_vocabulary.py`, `graduation.py`, `mics_task.py`, `task.py`
(plus `__pycache__/`, whose purge belongs to plan 08 Task 1).

### A.2 Four-criteria verdicts

**C1 — not in the pilot's static import closure.** PASS for all 7.
Evidence: `check_tree_integrity.py --strict` reports **40 closure members** both before and after
the deletion — an unchanged count. Had any of the 7 been a closure member, its removal would have
produced a dangling-import violation and moved the count.

**C2 — not reachable through a dynamic path.** PARTIAL, and this is the requirement's whole point.
- `PLUGINDIR` sweep: N/A — `pilot/plugins/` holds only `.gitkeep` after plan 04.
- **`autopilot/tasks/` AST sweep: these files ARE reached by it.** That is precisely why HYG-06
  removes them: `registry.get_task()` AST-sweeps this directory on every boot and imports each
  match, dragging in `cameras.py`, `usb.py` and the `transform/` + `stim/` trees. Being swept is
  not the same as being dispatched — see C3 — and the sweep is the cost HYG-06 eliminates.
- `importlib`: no hits.
- **String-keyed dispatch table: ONE hit, `utils/registry.py:42`** — handled in §A.3 below.

**C3 — not named by the backend.** MIXED. Recorded honestly, per the standard plan 04 set.
- **Source literals in `mics-backend`: ZERO.** Unfiltered Python scan over
  `/home/ido/mics-backend/api` and `/home/ido/mics-backend/orchestrator` for
  `Nafc`, `GoNoGo`, `Free_Water`, `Wheel_Child`, `Video_Child`, `Transformer`, `DLC_Latency`,
  `DLC_Hand`, `RecordingBox`, `protocol_scripts`, `free_water`, `gonogo`, `tasks.children`,
  `tasks.nafc`, `tasks.test` → **0 hits for every pattern.**
- **`task_toolkits.locked_state_source`: ZERO.** Counted query over all 12 candidate filenames
  (`Nafc.py`, `GoNoGo.py`, `Free_Water.py`, `DLC_Hand.py`, `DLC_Latency.py`, `RecordingBox.py`,
  `children.py`, `nafc.py`, `gonogo.py`, `free_water.py`, `test.py`, `protocol_scripts.py`)
  → `count = 0`. The only non-NULL `locked_state_source` value in the table remains
  `elastic_test.py` × 8, already recorded by plan 04 Finding 1. **No toolkit dispatches to
  anything removed here.**
- **`available_locked_states`: SIX rows resolve to classes removed here — C3 FAILS for these.**

  | task_filename | class_name | pilot_id | is_legacy_filename | updated_at |
  |---|---|---|---|---|
  | `RecordingBox.py` | `RecordingBox` | 1 | `t` | 2026-08-09 14:46:41.695153 |
  | `Free_Water.py` | `Free_Water` | 1 | `t` | 2026-08-09 14:46:41.701148 |
  | `GoNoGo.py` | `GoNoGo` | 1 | `t` | 2026-08-09 14:46:41.706787 |
  | `Nafc.py` | `Nafc` | 1 | `t` | 2026-08-09 14:46:41.731722 |
  | `DLC_Hand.py` | `DLC_Hand` | 1 | `t` | 2026-08-09 14:46:41.738655 |
  | `DLC_Latency.py` | `DLC_Latency` | 1 | `t` | 2026-08-09 14:46:41.744687 |

  All six are `is_legacy_filename = true`, all on pilot 1, all last written by the
  2026-08-09 14:46 handshake. **They will go stale**, because the backend has no prune path —
  exactly the staleness HYG-04 proved benign and explicitly accepted. `children.py`'s four classes
  and `protocol_scripts.py` have **no** rows at all.

  **This is materially weaker than plan 04's Finding 1.** There, 8 live toolkit rows resolved to a
  removed file, so a dispatch would fail on the Pi. Here **zero toolkits reference these six**;
  the rows are UI-visible inventory only, with nothing downstream that resolves them.
- `hardware_libs` / `hardware_modules`: N/A — no task module is a hardware lib.

**C4 — not reserved by a pending phase.** PASS. The reserved names in 30-CONTEXT.md are the three
Phase 26 OpenEphys files; none of the 7 appears in any pending phase's `files_modified`.

**Verdict: removed, with C3 recorded as failed-for-six-legacy-inventory-rows and overridden by the
locked user decision that all live work is backend-authored and sourceless.**

### A.3 `utils/registry.py:42` — the string-keyed reference the guard cannot see

**Removed:** the single enum member `CHILDREN = "autopilot.tasks.children.Child"` from
`class REGISTRIES`. Nothing else in the file changed; `registry.py` survives the phase.

Post-edit `REGISTRIES` members, read back by AST (not by grep):

```
('HARDWARE',   'autopilot.hardware.Hardware')
('TASK',       'autopilot.tasks.Task')
('GRADUATION', 'autopilot.tasks.graduation.Graduation')
('TRANSFORM',  'autopilot.transform.transforms.Transform')
('SOUND',      'autopilot.stim.sound.sounds.BASE_CLASS')
```

`TRANSFORM` and `SOUND` stay: `transform/` and `stim/` are not removed by this phase, so those
two values are not danglers. Only `CHILDREN` named a deleted module.

`python3 -m py_compile autopilot/autopilot/utils/registry.py` → exit 0.

**Four-criteria verdict on the `CHILDREN` enum member:**

1. **C1 — static closure.** Not a closure member itself; `registry.py` survives, but the enum
   *value* is a string naming `tasks/children.py`, deleted above. Removing the member removes the
   only in-tree dangler.
2. **C2 — dynamic reachability.** Reached only via `autopilot.get('children', …)` at
   `core/pilot.py:591`, inside `l_start`, guarded by `if 'child' in value.keys():`.
   **Re-run and recorded verbatim, as the plan required:**

   ```
   $ grep -rn "'child'" /home/ido/mics-backend/orchestrator /home/ido/mics-backend/api
   (no output; exit status 1)
   ```

   Corroborated by an unfiltered Python scan (grep on this host passes through a compressing
   proxy and cannot carry a load-bearing absence claim on its own): `'child'` → 0 hits and
   `"child"` → 0 hits, across both `orchestrator/` and `api/`. **No MICS START message ever
   carries a `child` key.**
3. **C3 — named by the backend.** Same scan; zero.
4. **C4 — reserved by a pending phase.** No.

**Hand-off to plan 06 (Task 1 owns it):** the now-orphaned branch at `core/pilot.py:589-592`

```python
if 'child' in value.keys():
    task_class = autopilot.get('children', value['task_type'])
else:
    task_class = autopilot.get_task(value['task_type'])
```

collapses to the unconditional `task_class = autopilot.get_task(value['task_type'])`.
`pilot.py` is plan 06's file and was **not touched here**. The decision and its rationale are in
plan 05's `<the_string_keyed_reference_the_guard_cannot_see>` block; the criterion-2 evidence
above is what it rests on. Plan 09's live rig session exercises START end-to-end, which is the
proof scoped to this one behavioural change.

### A.4 `tasks/__init__.py` — checked, unchanged

Full contents (37 bytes, one line):

```python
from autopilot.tasks.task import Task
```

It names only `task.py`, which survives. **No edit was needed.** This mattered: `autopilot/tasks/`
is the one directory with no per-file guard (`utils/common.py:47-67`'s `list_classes`), so a broken
`__init__.py` here would make `discover_tasks_metadata`'s blanket handler ship `tasks: []` in every
handshake with no error anywhere.

`python3 -m compileall -q autopilot/autopilot/tasks` → **exit 0** (the HYG-06 gate).

### A.5 Protocol-string / surviving-tree scan

`pilot/protocols/` is **empty** (no files). A `.json`-wide scan of the whole tree for `Nafc`,
`GoNoGo`, `Free_Water`, `Children`, `DLC_Hand`, `DLC_Latency`, `RecordingBox` → **0 hits.**
So there is no legacy protocol row to record, and no protocol file was touched.

Post-deletion scan over every surviving `.py` (excluding the guard's own `SELF` prefixes —
`tools/check_tree_integrity.py`, `tools/tree_integrity/`, `tests/test_tree_integrity.py` — and
`__pycache__`):

| Pattern | Hits |
|---|---|
| `tasks.children` | 0 |
| `tasks.nafc` | 0 |
| `tasks.gonogo` | 0 |
| `tasks.free_water` | 0 |
| `tasks.RecordingBox` | 0 |
| `tasks.protocol_scripts` | 0 |
| `Nafc` | 0 |
| `GoNoGo` | 0 |
| `Free_Water` | 0 |
| `Children` | 0 |
| `DLC_Latency` | 0 |
| `DLC_Hand` | 0 |
| `RecordingBox` | 0 |

**Zero danglers in survivors.** No `mics-backend` hit, so nothing to stop and report.

Pre-deletion the same scan found exactly the one known hit, `utils/registry.py:42`, plus two
stale bytecode files (`utils/__pycache__/registry.cpython-312.pyc` and `.cpython-37.pyc`) that
still carry the old enum table. Bytecode is **plan 08 Task 1's** tree-wide `__pycache__` purge and
was left alone here — Python 3 will not import a sourceless `.pyc` from `__pycache__`.

### A.6 HYG-14 third DELETE toggle — CLOSED

`tasks/RecordingBox.py` carried the last sites plan 04 handed over. Read from the file before
deletion, confirming plan 04's correction over 30-CONTEXT.md's table:

```
RecordingBox.py:53 |             'OG_TRIGGER': {
RecordingBox.py:54 |                 'OG_TRIGGER': gpio.Digital_Out
RecordingBox.py:62 |             'IR1': {
RecordingBox.py:63 |                 'IR1': gpio.Digital_In
RecordingBox.py:104|         # self.hardware['I2C']['MPR121'].set_cdc_manual(0x3f)
```

Both `OG_TRIGGER` and `IR1` are **two-line** declarations (dict key + `gpio.*` handler), not one —
five sites, not three.

**Post-deletion, over every surviving `.py` with the guard's `SELF` prefixes excluded:**

| Assertion | Result |
|---|---|
| `set_cdc_manual(0x3f)` | **0 occurrences tree-wide** |
| `OG_TRIGGER` | **0 occurrences in any `.py`** |

**HYG-14's third DELETE toggle (`0x3f`) is complete.** With plan 04's `detectedIR`,
`self.triggers['IR1']` and `pulse_and_notify(…OG_TRIGGER…)` all already at zero, **all three
DELETE-resolved toggles are now fully retired tree-wide.** Only HYG-14's RESTORE half
(`station.py:1333-1346`, plan 06) remains.

**The live pin declarations survive, untouched, by design:**

```
pilot/prefs.json:241|             "OG_TRIGGER": {
pilot/prefs.json:243|                 "name": "OG_TRIGGER",
pilot/prefs.json:278|             "IR1": {
pilot/prefs.json:282|                 "name": "IR1",
```

Per 30-CONTEXT.md's CORRECTION block, HYG-10 leaves the `GPIO`, `I2C`, `Mixer`, `Timers` and
`Modules` groups intact and plan 07 asserts these *survive*. The assertions above are **call
forms, never bare tokens** — a bare-token assertion would be guaranteed to fail at the phase exit
gate and would force stripping live GPIO entries out of `prefs.json` with no rig proof.
`prefs_wsl*.json` still carry their copies until plan 07.

### A.7 Task 1 gates

| Gate | Result |
|---|---|
| `python3 -m compileall -q autopilot/autopilot/tasks` | exit 0 |
| `python3 -m py_compile autopilot/autopilot/utils/registry.py` | exit 0 |
| `python3 tools/check_tree_integrity.py --strict` | exit 0 — `40 closure members, 30 protected files, 1 known-dangling exemptions held, 0 violations` |
| Pi pytest delta vs `30-PYTEST-BASELINE.json` | 179 → 179, **0 new failures** |
| Plan's full Task 1 `<automated>` verify chain | exit 0 |

### A.8 Proposed verdict line

```
HYG-06 | PROVEN | 7 registry-sweep collateral modules (60,505 B) removed from autopilot/tasks/;
                  compileall over the surviving directory exits 0 (the unguarded-sweep gate);
                  the one string-keyed dangler the AST guard cannot see (REGISTRIES.CHILDREN,
                  utils/registry.py:42) removed with a four-criteria verdict and the 'child'-key
                  grep over mics-backend returning zero; tasks/__init__.py names only the
                  surviving task.py; zero danglers in survivors; guard --strict exit 0;
                  Pi pytest delta 179 -> 179, 0 new failures.
```

---

## B. Task 2 — Camera subtree, Pi copy (HYG-05)

*(filled in by Task 2)*

---

## C. Task 3 — `hardware_libs` reconciliation (HYG-05, DB copy)

*(filled in by Task 3)*
