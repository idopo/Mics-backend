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

### B.1 The three-part edit, and why it is three parts

The correction recorded in REQUIREMENTS.md HYG-05 and 30-CONTEXT.md is **confirmed by direct
inspection of the tree before the edit**, not taken on trust:

```
autopilot/autopilot/hardware/i2c.py:8    from autopilot.hardware.cameras import Camera
autopilot/autopilot/hardware/i2c.py:580  class MLX90640(Camera):
autopilot/autopilot/hardware/i2c.py:632      super(MLX90640, self).__init__(fps, **kwargs)
autopilot/autopilot/hardware/i2c.py:789      super(MLX90640, self).release()   <- AST end_lineno
autopilot/autopilot/hardware/i2c.py:799  class MPR121(Hardware):
```

`Camera` is `MLX90640`'s **base class**, not a dead import. Removing only the import would leave
`class MLX90640(Camera):` evaluating an undefined name at module-import time → `NameError` at
`mics_task.py:4` → the pilot dies at import, reported by nothing (`pilot.py:609`).

### B.2 Removed paths

| Path | Bytes | md5 (pre-removal) |
|---|---|---|
| `autopilot/autopilot/hardware/cameras.py` | 69,302 | `9b46485058c5b4c9758660e126c4fcf6` |
| `autopilot/autopilot/hardware/usb.py` | 10,546 | `99c65394baff2b285e0fe369a099f5d7` |
| `autopilot/autopilot/setup/setup_mlx90640.sh` | 792 | `0065a57b9a9164392fffb50fdc562ce9` |

**Importer counts, measured by unfiltered Python scan immediately before the removal:**
- `cameras.py`: exactly **one** live importer left — `i2c.py:8`. (The other two hits,
  `tests/test_tree_integrity.py:89` and `:94`, are string literals inside the guard's own
  synthetic-tree fixture — a `SELF_PATHS` entry, correctly not a reference. Plans 02/03 had
  already retired `core/gui.py`, `core/terminal.py` and `autopilot/tests/`; Task 1 of this plan
  retired `tasks/children.py` and `tasks/test.py`, which is why Task 1 had to land first.)
- `usb.py`: **zero** importers tree-wide. Its last one, `tasks/children.py`, went in Task 1.

### B.3 `i2c.py` — before / after

| | md5 | bytes | lines |
|---|---|---|---|
| before | `3c933d65eeac795d2bcabd8d5cc3c08f` | 35,934 | 993 |
| after | `58c6a426021ce8aab3a7ad3502cf6c9a` | 28,423 | 774 |

Delta: **−7,511 bytes, −219 lines.** The pre-edit copy is preserved at `/tmp/i2c.before.py` for
the Task 3 reconciliation.

### B.4 The surgery, and the one place the plan's literal instruction was unsafe

The class was located **by AST span**, never by hardcoded line number, and the cut was asserted at
both ends before it was applied (`lines[start] == "class MLX90640(Camera):"`,
`"super(MLX90640, self).release()" in lines[end-1]`).

> **Deviation, Rule 1 — the plan's stated cut boundary would have broken the licker.**
> The plan says to cut *"through the last line before `class MPR121(Hardware):`"*. Applied
> literally that eats lines 792–796:
>
> ```
> 792| import board
> 793| import busio
> 795| # Import MPR121 module.
> 796| import adafruit_mpr121
> ```
>
> These are **module-level imports MPR121 depends on** — `busio.I2C(board.SCL, board.SDA)` at the
> old `:809` and `adafruit_mpr121.MPR121(self.i2c)` at the old `:816`. Cutting them would leave
> `MPR121.__init__` raising `NameError` on every instantiation, i.e. **the lick sensor dead on the
> live rig**, and — with no `TASK_ERROR` emitter on the Pi — presenting as a run stuck `running`
> for ever rather than as an error. `py_compile` would **not** have caught it.
>
> The cut was therefore made to the class's AST `end_lineno` plus its trailing blank lines only,
> with an explicit assertion that the first surviving line with content is `import board`. The
> three imports are asserted present in the written file.

Three edits applied, verified by `difflib.SequenceMatcher` against `/tmp/i2c.before.py` — the diff
contains **exactly three `delete` opcodes and zero `insert`/`replace` opcodes**, i.e. nothing was
reformatted, reordered or rewritten:

| # | Span (before-file lines) | Lines | What |
|---|---|---|---|
| a | 8 | 1 | `from autopilot.hardware.cameras import Camera` |
| b | 30–36 | 7 | the `try: import MLX90640 as mlx_cam / MLX90640_LIB = True / except ImportError: MLX90640_LIB = False` guard and its two leading blanks |
| c | 580–790 | 211 | `class MLX90640(Camera):` (580–789) plus one trailing blank |

The guard block was safe to remove: `mlx_cam` was referenced **only** at the old `:703` and
`MLX90640_LIB` **only** at the old `:629`, both inside the removed class.

### B.5 Residue check — zero code hits, zero prose hits

Over the written file:

| Token | Occurrences |
|---|---|
| `Camera` | 0 |
| `MLX90640` | 0 |
| `mlx_cam` | 0 |
| `MLX90640_LIB` | 0 |
| `autopilot.hardware.cameras` | 0 |

Not merely "no *code* hits" — the docstring prose went with the class too, so the count is zero
outright.

### B.6 AST assertion on the survivors (the check `py_compile` cannot make)

```
top-level defs: ['I2C_9DOF', 'MPR121', 'Motor_Shield_Hat',
                 'Motor_Shield_Hat_extend', 'Touch_Detector']
  class I2C_9DOF                 bases=['Hardware']
  class MPR121                   bases=['Hardware']
  class Motor_Shield_Hat         bases=['Hardware', 'Effector']
  class Motor_Shield_Hat_extend  bases=['Motor_Shield_Hat']
  class Touch_Detector           bases=['MPR121']
```

**Five survivors intact with their inheritance chains, `MLX90640` and `Camera` gone.**
`Touch_Detector(MPR121)` — the lick path — is untouched.
MPR121's module-level dependencies asserted present: `import board`, `import busio`,
`import adafruit_mpr121`.

**The deferred defect stays broken, as required:** `except(e):` survives at the new `i2c.py:600`
(was `:819`). It was not "fixed" — 30-CONTEXT.md defers it by name and plan 01's manifest holds an
inverted assertion over it.

### B.7 `setup/setup_mlx90640.sh` — four criteria, all satisfied, removed

It provisions the third-party MLX90640 library for the class removed above.

1. **C1 — static closure.** PASS. A shell script; never imported, cannot be a closure member.
2. **C2 — dynamic reachability.** PASS. After edit (c), a content scan of the **entire** surviving
   tree (all file types, `__pycache__` excluded) for `setup_mlx90640` returns **0 hits**. Its only
   two in-tree mentions were `i2c.py:606` (docstring) and `i2c.py:630` (the `ImportError` message),
   both inside the removed class. A case-insensitive scan for `mlx90640` excluding the script
   itself returns exactly **2** hits, neither a reference:
   - `tools/tree_integrity/final_checks.py:35` — `re.compile(r"class MLX90640")`, the guard's own
     F-check literal asserting the class is *gone* (a `SELF_PATHS` entry).
   - `autopilot/README.md:129` — upstream changelog prose.
3. **C3 — named by the backend.** PASS. `setup_mlx90640` and `MLX` → **0 hits** across
   `mics-backend/api` and `mics-backend/orchestrator`.
   `select count(*) from hardware_libs where filename ilike '%mlx%' or name ilike '%mlx%'` → **0**.
   `select count(*) from hardware_modules where name ilike '%mlx%' or class_name ilike '%mlx%'`
   → **0**. No `pilot/prefs.json` `MLX` key.
4. **C4 — reserved by a pending phase.** PASS. The reserved names are the three Phase 26 OpenEphys
   files; this is not one.

**Corroborating evidence:** the script builds `autopilot/external/mlx90640-library`, and
`autopilot/autopilot/external/` contains only `__init__.py` — the submodule it depends on is not
present in the tree, so the script could not run even if something called it.

**Verdict: residue, not a dangling reference. Removed.** (Same standard plan 02 applied to
`Testing_stepper_motor_Hat/`; plan 03 removed the sibling `install_pyspin.sh` because that one
genuinely dangled.)

### B.8 Findings recorded, not acted on

**Finding B-1. `hardware/__init__.py:54` names three classes that `cameras.py` defined, in a
constant nothing reads.**

```
autopilot/autopilot/hardware/__init__.py:52 # FIXME: Hardcoding names of metaclasses, should have some better system ...
autopilot/autopilot/hardware/__init__.py:54 META_CLASS_NAMES = ['Hardware', 'Camera', 'GPIO', 'Directory_Writer', 'Video_Writer']
```

`Camera`, `Directory_Writer` and `Video_Writer` all lived in the removed `cameras.py`.
**`META_CLASS_NAMES` is read nowhere** — a tree-wide scan returns exactly **1** hit, its own
definition; `Directory_Writer` and `Video_Writer` likewise return exactly that one line each. So it
is an inert constant, **not** a second string-keyed dispatch table, and the guard correctly leaves
it alone (bare tokens in a list literal carry no invocation form).

**Not touched.** `hardware/__init__.py` is not in this plan's `<files>` block, and editing outside
the block is exactly the improvisation the plan forbids. Handed to plan 06 (dead-code sweep) or
plan 08 for a decision. It cannot break anything in the meantime — nothing reads it.

**Finding B-2. Three imports in `i2c.py` become unused, and were deliberately left in place.**

Computed by AST binding-vs-`Name`-use diff over the before/after pair:

- Already unused before this edit (8): `os`, `sys`, `prefs`, `Net_Node`, `log_action`, `struct`,
  `Queue`, `Empty`.
- **Newly unused as a result of removing `MLX90640` (3):** `threading` (`:12`),
  `product` (`:17`, `from itertools import product`), `griddata` (`:18`,
  `from scipy.interpolate import griddata`).

Left in place on purpose. The plan scopes this edit to *"exactly the import line, the `MLX90640`
class and its `mlx_cam` guard"* and says *"leave everything else byte-identical"*; `i2c.py` is
otherwise off-limits under TRIGA-12. Removing `griddata` would additionally change what the module
requires of the rig's environment at import time, which is not a change worth making without a rig
proof. Recorded for plan 08 §6.

### B.9 Task 2 gates

| Gate | Result |
|---|---|
| `cameras.py`, `usb.py`, `setup_mlx90640.sh` absent | confirmed |
| `python3 -m py_compile autopilot/autopilot/hardware/i2c.py` | exit 0 |
| `python3 -m compileall -q autopilot/autopilot` | exit 0 |
| AST survivor assertion (5 present, 2 gone, MPR121 deps intact) | PASSED |
| `python3 tools/check_tree_integrity.py --strict` | exit 0 — `40 closure members, 30 protected files, 1 known-dangling exemptions held, 0 violations` |
| Pi pytest delta vs baseline | 179 → 179, **0 new failures**; `test_mpr121_irq_hygiene` **0 failing**, `test_check_for_detectors` **17** (unchanged baseline contribution) |
| Plan's full Task 2 `<automated>` verify chain | exit 0 |

---

## C. Task 3 — `hardware_libs` reconciliation (HYG-05, DB copy)

### C.1 The "6-byte drift" is a measurement artifact. The two copies were byte-identical.

This is the first time the drift has been *characterised* rather than measured, and characterising
it dissolves it.

Measured DB-side, on version 26, with both length functions:

```sql
select length(source_code)       as chars,   -- 35928
       octet_length(source_code) as bytes    -- 35934
from hardware_lib_versions where id = 26;
```

| | value |
|---|---|
| `length(source_code)` — **characters** | 35,928 |
| `octet_length(source_code)` — **bytes** | **35,934** |
| disk `i2c.py` before the edit — bytes | **35,934** |

**The 6 is exactly 3 × (3 − 1).** `i2c.py` contains three em-dash characters (`—`, U+2014) at
character offsets 31264, 31925 and 32329; each is 1 character but 3 UTF-8 bytes. 30-CONTEXT.md and
plan 05's `<verified_db_state>` both compared `length()` (characters) against the disk file's
**byte** size, so the "drift" was a units mismatch, not a divergence.

**Proof of identity, not just of equal size.** The psql `-tAc` dump of version 26 came to 35,935
bytes — the 35,934 payload plus the single trailing newline psql appends. Stripping exactly that
one byte:

```
db   bytes: 35934  md5: 3c933d65eeac795d2bcabd8d5cc3c08f
disk bytes: 35934  md5: 3c933d65eeac795d2bcabd8d5cc3c08f
IDENTICAL: True
```

`difflib` opcodes between them: **none**. The psql dump was verified rather than trusted, exactly
as the plan required; it turned out to be faithful, and the plan's fallback (`GET
/api/hardware-libs/9`) was not needed.

**Reconciliation decision: branch (a), "adopt the disk copy as canonical" — and it discards
nothing.** There were no drift hunks to weigh, because there was no drift. Nothing was overwritten
that the ledger cannot account for.

> **This retires a deferred item's only evidence.** 30-CONTEXT.md's Deferred list carries
> *"`hardware_libs` ↔ disk drift — no process keeps the exec'd DB copy in sync with the Pi file.
> Already 6 bytes apart for `i2c.py`."* The **general** concern stands untouched — there is still
> no sync process, and this plan had to make the same edit twice by hand, which is the concern
> demonstrating itself. But the specific 6-byte instance cited as proof was never real. Plan 08 §6
> should restate the deferred item without that number.

### C.2 The reconciliation

`PUT /api/hardware-libs/9` with `{"source_code": <edited disk file>, "declared_imports": []}`
(matching `SourceUpdateBody` at `api/routers/hardware_libs.py`; `declared_imports` is optional and
version 26 carried `[]`, so `[]` was sent to preserve it).

`lib.kind` is `hardware`, so the `_validate_compute_lib` gate at `:421-422` did not run, as the
plan predicted.

**Response: HTTP 200.**

```json
"impact": {
  "removed_methods": {
    "MLX90640": ["__init__", "_grab", "_threaded_capture", "_timestamp",
                 "capture_init", "fps", "init_cam", "integrate_frames",
                 "interpolate", "interpolate_frame", "release"]
  },
  "affected_definition_ids": []
}
```

- `removed_methods` names **exactly one class, `MLX90640`, and its 11 methods** — no survivor's
  method was touched, which is an independent confirmation of the B.6 AST assertion from the
  backend's own extractor.
- **`affected_definition_ids` is empty**, as asserted. No task definition references an `MLX90640`
  method, so `_flag_broken_task_defs` flagged nothing and no `task_definitions` row moved to
  `validation_status = 'broken'`. This corroborates removal criterion 3 from the backend side.

### C.3 Confirmation query

```sql
select l.active_version_id, v.version_number, v.state,
       length(v.source_code), octet_length(v.source_code),
       position('class MLX90640' in v.source_code),
       position('autopilot.hardware.cameras' in v.source_code),
       position('class MPR121' in v.source_code),
       position('class Touch_Detector' in v.source_code),
       v.sha256_hash
from hardware_libs l join hardware_lib_versions v on v.id = l.active_version_id
where l.id = 9;
```

| field | value |
|---|---|
| `active_version_id` | **144** (> 26 ✓) |
| `version_number` | 3 |
| `state` | `beta` (version 26 was also `beta` — no regression) |
| `length` (chars) | 28,417 — equals the disk file's 28,417 chars |
| `octet_length` (bytes) | **28,423 — equals the disk file's 28,423 bytes** |
| `position('class MLX90640')` | **0** |
| `position('autopilot.hardware.cameras')` | **0** |
| `position('class MPR121')` | 21,269 (present) |
| `position('class Touch_Detector')` | 28,011 (present) |
| `sha256_hash` | `649d4f31d1cc4b71e32a528a13e264eb1d0e6d657cf261eb4436d07a5203483e` |

**The DB's stored `sha256_hash` equals `sha256` of the disk file's bytes**
(`649d4f31…483e`) — the two copies are provably identical, not merely the same length.

**History preserved.** The PUT created a new row rather than mutating version 26:

| version id | version_number | state | chars | `position('class MLX90640')` |
|---|---|---|---|---|
| 15 | 1 | `stable` | 34,593 | 21,345 |
| 26 | 2 | `beta` | 35,928 | 21,345 |
| **144** | **3** | `beta` | **28,417** | **0** |

The camera code is still recoverable from versions 15 and 26, which is what makes this
reconciliation auditable and reversible.

### C.4 Backend suite

`docker compose exec -T api python -m pytest -q tests/` → **435 passed, 1 skipped**, exit 0.
This is the only requirement in Phase 30 that writes to `mics-backend`, so it is the only one that
could regress the backend; it did not. (435/1 confirms plan 04 Finding 4 — `CLAUDE.md`'s quoted
"352 pass" is stale.)

**Nothing was deployed to the Pi. The pilot was not restarted. No Python was run on the Pi.**
The Pi picks up version 144 on its next `LOAD_HARDWARE_LIBS`, which the user triggers by starting
a run.

### C.5 The HYG-05 three-part correction — CLOSED

Recorded as a **closed** finding for plan 08 §6, not an open action item.

The amendment had already landed before this plan executed: REQUIREMENTS.md HYG-05 carries the row
text *"Corrected 2026-08-10 during planning … the edit is therefore three-part"*, and
30-CONTEXT.md carries the inline `> **CORRECTION, 2026-08-10 (planning).**` block under the
`cameras.py` conflict. Neither file still carries the false *"`Camera` is never used in `i2c.py`
… it is a dead import"* text. **No documentation edit was needed or made.**

What this plan adds is the **execution-time confirmation** that the correction was right:
`Camera` was read at `i2c.py:580` as `class MLX90640(Camera):` before the edit, and removing only
the import — the pre-correction plan — would have left an undefined name evaluated at module-import
time, killing the pilot at `mics_task.py:4` with nothing reporting it.

**Root cause, worth carrying forward verbatim:** the false claim came from filtered `grep` output
on this host, where a compressing proxy rendered line 580 blank. Every load-bearing absence claim
in this plan — the `'child'` key, the `cameras.py`/`usb.py` importer counts, `setup_mlx90640`,
the toggle scans, the newly-unused imports — was made with an unfiltered Python reader, with
`grep` used only to corroborate a result already obtained.

### C.6 Task 3 gates

| Gate | Result |
|---|---|
| `PUT /api/hardware-libs/9` | HTTP 200, new version 144 > 26, `active_version_id` = 144 |
| `impact.affected_definition_ids` | **empty** |
| active version `position('class MLX90640')` | 0 |
| active version `position('autopilot.hardware.cameras')` | 0 |
| active version `octet_length` vs disk bytes | 28,423 = 28,423 |
| active version `sha256_hash` vs disk sha256 | identical |
| `docker compose exec -T api python -m pytest -q tests/` | **435 passed, 1 skipped**, exit 0 |
| Plan's full Task 3 `<automated>` verify chain | exit 0 |

### C.7 Proposed verdict line

```
HYG-05 | PROVEN | Camera subtree removed on BOTH sides of the DB boundary. Pi copy:
                  hardware/cameras.py (69,302 B) + hardware/usb.py (10,546 B) +
                  setup/setup_mlx90640.sh (792 B) deleted; i2c.py three-part edit
                  35,934 -> 28,423 B with exactly 3 delete opcodes and 0 insert/replace,
                  MLX90640 class cut by AST span so MPR121's board/busio/adafruit_mpr121
                  imports survive; AST assertion proves I2C_9DOF, MPR121,
                  Motor_Shield_Hat, Motor_Shield_Hat_extend and Touch_Detector(MPR121)
                  intact and MLX90640/Camera absent with zero residue tokens.
                  DB copy: hardware_libs 9 active version 26 -> 144, octet_length and
                  sha256 both equal to the disk file, impact.affected_definition_ids
                  empty, versions 15/26 preserved. The recorded 6-byte drift was a
                  length()-chars vs disk-bytes artifact (3 em-dashes); the copies were
                  byte-identical beforehand. Backend suite 435 passed / 1 skipped.
```

---

## D. Hand-offs

| To | Item |
|---|---|
| **plan 06 Task 1** | Remove the now-orphaned `if 'child' in value.keys():` / `else:` branch at `core/pilot.py:589-592`, collapsing to the unconditional `task_class = autopilot.get_task(value['task_type'])`. Four-criteria verdict in §A.3; the `'child'`-key scan over `mics-backend` returned zero. `pilot.py` was **not** touched here. |
| **plan 06 or 08** | `hardware/__init__.py:54`'s `META_CLASS_NAMES` still names `Camera`, `Directory_Writer` and `Video_Writer`, all defined in the removed `cameras.py`. The constant is read nowhere (§B.8 Finding B-1). Inert; out of this plan's `<files>` scope. |
| **plan 08 §6** | `i2c.py` now carries 3 newly-unused imports — `threading`, `product`, `griddata` (§B.8 Finding B-2) — left in place under TRIGA-12. |
| **plan 08 §6** | Restate the deferred `hardware_libs` ↔ disk drift item **without** the "6 bytes apart for `i2c.py`" claim (§C.1). The general concern stands; the cited instance was a measurement artifact. |
| **plan 08 §6** | 6 `available_locked_states` rows on pilot 1 (`RecordingBox`, `Free_Water`, `GoNoGo`, `Nafc`, `DLC_Hand`, `DLC_Latency`) are now stale (§A.2 C3). Zero toolkits reference them. Accepted staleness under HYG-04. |
| **plan 08 Task 1** | `__pycache__` purge — `utils/__pycache__/registry.cpython-{312,37}.pyc` still carry the old `REGISTRIES` table including `autopilot.tasks.children.Child`. |

## E. Standing-rule compliance

- **No git command was run in `/home/ido/pi-mirror` at any point.** Every git invocation used
  `git -C /home/ido/mics-backend …`, which is cwd-independent; no command combined a `cd` into
  `pi-mirror` with a git call.
- No `rsync`, no deploy, no pilot start/stop, no Python executed on the Pi.
- `--rebaseline` was **not** run. `tools/tree_protect_list.json` was **not** edited.
  No assertion was weakened; no extra file was deleted to reach a zero count.
- No HYG-13 protect-listed file was touched — all 12 candidate paths were checked against the
  protect list before any deletion and none was listed.
- Deletions used Python `os.remove`, the fallback plan 03 established after the permission
  classifier refused `rm -rf`.
- `~/pi-mirror.bak-2026-08-10` confirmed present before the first deletion.
