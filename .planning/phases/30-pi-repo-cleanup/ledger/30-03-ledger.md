# Removal Ledger — Plan 30-03 (HYG-07, the Terminal-era tree)

**Scope:** `/home/ido/pi-mirror` only. No git command was run in that directory at any point.
**Instrument:** `tools/check_tree_integrity.py --strict` (plan 30-01), run after every deletion task.
**Method note:** every "N hits / absent / unused" claim below comes from an **unfiltered Python
reader** over the tree, never from `grep` alone — filtered `grep` on this host passes through a
compressing proxy that can render a matching line blank (the near-miss that almost deleted
`Camera`, the base class of `MLX90640`).

## The four criteria

1. Not in the static import closure of `python3 -m autopilot.core.pilot`.
2. Not reachable dynamically (`PLUGINDIR` sweep, `autopilot/tasks/` AST sweep, `importlib`,
   string-keyed dispatch).
3. Not named by the backend — no literal filename, module path or class-name string in
   `mics-backend`, and no `hardware_libs` / `hardware_modules` / `task_toolkits` /
   `available_locked_states` row resolving to it.
4. Not reserved by a pending phase.

---

## Task 1 — the top-level Terminal deployment

**Removed:** 108 files, 17,857,905 bytes.

| Path | Files | Bytes | C1 | C2 | C3 | C4 | Verdict |
|---|---:|---:|:--:|:--:|:--:|:--:|---|
| `terminal/` (entire) | 106 | 17,855,490 | ✅ | ✅ | ✅ | ✅ | REMOVE |
| `run_terminal.sh` | 1 | 325 | ✅ | ✅ | ✅ | ✅ | REMOVE |
| `.vscode/` | 1 | 2,090 | ✅ | ✅ | ✅ | ✅ | REMOVE |

`terminal/` composition at removal time (largest first): `logs/` 16,468,250 B (12 files — rotated
log spew, 92% of the tree), `data/` 962,793 B, `plugins/` 259,319 B (19 `.py`), `pilot_db.json`
43,840 B, `pilot_db3.json` 36,404 B, `~/` 26,327 B (9 files — the tilde-literal directory HYG-08
names), `protocols/` 17,689 B (50 files), `pilot_db1.json` 17,475 B, `pilot_db2.json` 16,630 B,
four `prefs*.json`, `terminal.conf`, `test.py`, `pwm_test.py`, `launch_autopilot.sh`, `batch.sh`,
`log.txt`, and a zero-byte `prefs_wsl.json:Zone.Identifier`.

### Criterion 1 — static closure

The guard's closure from `core/pilot.py` is 40 members and contains no path under `terminal/`.
`--strict` exit 0 before and after removal, closure member count unchanged at 40 — i.e. nothing
in the pilot's import closure lived here.

### Criterion 2 — dynamic reachability

`pilot/prefs.json:533` sets `"PLUGINDIR": "/home/pi/Apps/mice_interactive_home_cage/pilot/plugins"`.
The dynamic plugin sweep (`autopilot/utils/plugins.py:44`, `Path(prefs.get('PLUGINDIR'))`)
therefore resolves to **`pilot/plugins/`**, never `terminal/plugins/`. The `autopilot/tasks/` AST
sweep is rooted at `autopilot/autopilot/tasks/`, also disjoint. No `importlib` or string-keyed
dispatch path in the surviving tree names a `terminal/` path.

### Criterion 3 — not named by the backend

Unfiltered scan of 178 backend source files (`api/`, `orchestrator/`, `web_ui/` sources,
`backup/`, `.claude/`, `docker-compose.yml`, `CLAUDE.md`):

| Token | Hits | Disposition |
|---|---:|---|
| `terminal/` | 0 | — |
| `terminal.conf` | 0 | — |
| `run_terminal` | 0 | — |
| `launch_autopilot` | 0 | — |
| `autopilot.core.terminal` | 0 | — |
| `.vscode` | 0 | — |
| `pilot_db` | 5 | **Not a reference.** All five are the `pilot_db_id` local/parameter in `orchestrator/orchestrator/orchestrator_station.py` (:356, :357, :860, :869, :881) — a database primary key, unrelated to `terminal/pilot_db*.json`. |
| 14 `terminal/plugins/` class names | 0 | `AppetitveTaskReal`, `AssociationCueReward`, `AssociationLearning`, `Blink`, `ExtinctionAUDIO`, `ExtinctionLED`, `Generalization`, `GradSimp`, `Graph_Demo_RT`, `SerialComTask`, `SerialStreamFlushTask`, `StochasticReward`, `WaterCalibration`, `YoShiTask` — all 0 hits in backend source. |
| `Simple` | 129 | **Not a reference.** Every hit is `SimpleNamespace` (test scaffolding). The Terminal plugin class `Simple` is never named. |

**DB check (live dev Postgres, `mics_db`).** The decisive question is not whether a row names a
class defined under `terminal/plugins/`, but whether any row **resolves to a file that exists only
there**. It does not:

- `hardware_libs` — 7 rows (`mixer.py`, `timer.py`, `extlink_demo.py`, `compute_ops.py`,
  `__init__.py`, `gpio.py`, `i2c.py`). None under `terminal/`.
- `hardware_modules` — 9 rows (`Digital_Out` ×3, `Solenoid`, `TIMER`, `Touch_Detector`,
  `Digital_In`, `ComputeOps`, `ExtlinkDemo`). None under `terminal/`.
- `task_toolkits` — no row resolving to a `terminal/` path.
- `available_locked_states` — 37 rows, all `pilot_id = 1`. Set-differenced against disk:
  **`(DB filenames ∩ terminal/plugins) − pilot/plugins = ∅`.** Every DB row naming a file that
  also exists in `terminal/plugins/` resolves to the pilot's own copy in `pilot/plugins/` (plan
  04's scope) or to `autopilot/tasks/` (`RecordingBox.py`, `learning_cage.py`,
  `mics_cage_task.py`, `mics_task.py`). Deleting `terminal/` therefore removed **no file any DB
  row resolves to**.

Two files exist **only** in `terminal/plugins/` and nowhere else — `SerialComTask.py` and
`SerialStreamFlushTask.py`. Both have 0 backend hits and 0 DB rows. They are the only genuinely
unique code in the removed tree, and they are unreferenced.

> **Incidental finding, not acted on (belongs to plan 04 / backend hygiene, not here).** Several
> `available_locked_states` rows are already stale against disk through spelling drift and resolve
> to nothing at all: DB `AppetitveTaskReal.py` vs disk `AppetitiveTaskReal.py`; DB
> `Generalization.py` vs disk `Genralization.py` (pilot) / `Generalzation.py` (terminal); DB
> `Blink.py`/`Blink1.py`/`Blink2.py`/`Simple.py` vs disk lowercase `blink.py`/`simple.py`. The
> backend never prunes handshake rows (30-CONTEXT.md, Integration Points), so this staleness
> predates the phase and is unaffected by it. Recorded so plan 04 is not surprised by it.

### Criterion 4 — not reserved by a pending phase

Scanned all 106 removed `terminal/` paths for the Phase 26 / Phase 18 reserved names
(`openephys`, `extlink`, `external_hardware`, `fda_vocabulary`): **zero hits**. No pending phase
reserves anything under `terminal/`, `run_terminal.sh` or `.vscode/`.

### Verification

```
cd /home/ido/pi-mirror && test ! -e terminal && test ! -e run_terminal.sh \
  && test ! -e .vscode && test -f run_pilot.sh \
  && python3 tools/check_tree_integrity.py --strict
OK: 40 closure members, 30 protected files, 1 known-dangling exemptions held, 0 violations
EXIT=0
```

The pre-removal `note: unparseable json (skipped for path check): .vscode/launch.json` is **gone**
from the guard's output — this task removed one of the three unparseable `.json` files plan 01's
F6 gate waits on (`.vscode/launch.json`), and `terminal/pilot_db1.json` + `terminal/pilot_db2.json`
went with `terminal/`. All three are now clear.

---

## Task 2 — the Pi-side Terminal modules, `install_pyspin.sh`, and the launcher string

**Removed:** 16 files, 285,348 bytes.

| Path | Bytes | C1 | C2 | C3 | C4 | Importers (measured) | Verdict |
|---|---:|:--:|:--:|:--:|:--:|---|---|
| `core/terminal.py` | 39,821 | ✅ | ✅ | ✅ | ✅ | none (the agent entry point itself) | REMOVE |
| `core/gui.py` | 125,147 | ✅ | ✅ | ✅ | ✅ | `core/terminal.py:51` | REMOVE |
| `core/plots.py` | 34,701 | ✅ | ✅ | ✅ | ✅ | `core/terminal.py:48`, `core/gui.py:50` | REMOVE |
| `core/subject.py` | 56,872 | ✅ | ✅ | ✅ | ✅ | `core/terminal.py:46`, `core/gui.py:43`, `viz/psychometric.py:4`, `viz/trial_viewer.py:26` | REMOVE |
| `core/styles.py` | 911 | ✅ | ✅ | ✅ | ✅ | `core/terminal.py:23`, `core/plots.py:36`, `core/gui.py:49` | REMOVE |
| `core/utils.py` | 0 | ✅ | ✅ | ✅ | ✅ | **none** (0-byte file) | REMOVE |
| `core/reward.py` | 1,800 | ✅ | ✅ | ✅ | ✅ | **none, tree-wide** | REMOVE |
| `viz/` (3 files) | 11,490 | ✅ | ✅ | ✅ | ✅ | `core/terminal.py:59`; internally `viz/__init__.py:1` | REMOVE |
| `data_handlers/` (2 files) | 3,197 | ✅ | ✅ | ✅ | ✅ | `core/terminal.py:47`; internally `ElasticSearchDataHandler.py:1` | REMOVE |
| `utils/invoker.py` | 1,341 | ✅ | ✅ | ✅ | ✅ | `core/terminal.py:50`, `core/plots.py:37`, `core/gui.py:48` | REMOVE |
| `utils/Event.py` (**singular**) | 1,254 | ✅ | ✅ | ✅ | ✅ | **zero Python importers** | REMOVE |
| `setup/request_helpers.py` | 4,375 | ✅ | ✅ | ✅ | ✅ | `setup/install_pyspin.sh:64,65` only — removed in this same task | REMOVE |
| `setup/install_pyspin.sh` | 4,439 | ✅ | ✅ | ✅ | ✅ | none (shell script, never imported) | REMOVE |

Every importer of every module above is itself in this table. The cluster is closed — that is what
makes it a clean cut rather than a sweep.

### Criterion 1 — static closure (all rows)

The guard's closure from `core/pilot.py` is **40 members before and after** this task, and
assertion 1 (closure completeness) resolves every member. Had any removed path been a closure
member, `--strict` would have failed on an unresolvable member rather than reporting 0 violations.
`compileall` over `autopilot/autopilot`, `tools` and `tests` exits 0, so no surviving module lost
an import target.

### Criterion 2 — dynamic reachability (all rows)

`PLUGINDIR` resolves to `pilot/plugins/` (`pilot/prefs.json:533`), and the `autopilot/tasks/` AST
sweep is rooted at `autopilot/autopilot/tasks/`. Every removed path lives under `core/`, `viz/`,
`data_handlers/`, `utils/` or `setup/` — disjoint from both sweep roots. A whole-tree scan for
non-import (string-literal / `importlib` / dispatch-key) references to any removed module returned
**0 non-docstring hits** outside the guard's own `SELF_PATHS` (see the table under B below).

### Criterion 3 — not named by the backend (all rows)

0 hits across 178 backend source files for `core.subject`, `core.gui`, `core.plots`,
`core.styles`, `core.reward`, `autopilot.viz`, `invoker`, `request_helpers`, `install_pyspin` and
`PySpin`. No `hardware_libs` row (7 rows: `mixer.py`, `timer.py`, `extlink_demo.py`,
`compute_ops.py`, `__init__.py`, `gpio.py`, `i2c.py`), no `hardware_modules` row (9) and no
`task_toolkits` row resolves to any of them.

> **One hit that looks alarming and is not.** `data_handlers` returns 5 backend hits, all in
> `orchestrator/orchestrator/orchestrator_station.py` (:11, :52, :569, :573) plus
> `orchestrator/orchestrator/data_handlers/ElasticSearchDateHandler.py:1`. These name the
> **orchestrator's own** `data_handlers` package, which lives in `mics-backend` and is untouched
> by this phase — note even the filename differs (`ElasticSearchDa**te**Handler.py` there vs
> `ElasticSearchDa**ta**Handler.py` on the Pi). The Pi copy was the *Terminal's* ES writer. The
> pilot's ES path is `Event_Dispatcher` → orchestrator → ES and is unaffected; `Event_Dispatcher.py`
> imports `autopilot.utils.Events` (plural), which survives.

### Criterion 4 — not reserved by a pending phase (all rows)

None of the 16 removed files matches a Phase 26 / Phase 18 reserved name (`openephys`, `extlink`,
`external_hardware`, `fda_vocabulary`).

### The `Event.py` / `Events.py` discrimination — checked, not assumed

Two files one character apart, one live and one dead. Verified by reading both rather than by
pattern-matching the name:

| | `utils/Event.py` (**removed**) | `utils/Events.py` (**survives**) |
|---|---|---|
| Size | 1,254 B | 2,039 B |
| Classes | `Event` only | `Event`, `Hardware_Event` |
| `Event.__init__` | `(event_type, level, event_data)` | `(event_type, event_data)` |
| Python importers | **0** | **12** |

The 12 live importers of the plural module: `core/pilot.py:25`, `tasks/task.py:21`,
`tasks/mics_task.py:14`, `tasks/mics_cage_task.py:14`, `tasks/learning_cage.py:14`,
`tasks/RecordingBox.py:14`, `networking/Event_Dispatcher.py:1`,
`hardware/external_hardware_binding.py:113`, `hardware/external_hardware_ingress.py:8`,
`utils/FiniteDeterministicAutomaton.py:2`, `utils/Tracker.py:3`, `utils/logging_utils.py:3`
(plus 6 `pilot/plugins/*.py`). The one remaining `from threading import Event` at the former
`core/plots.py:27` was stdlib and went with that file.

### `install_pyspin.sh` — the four-criteria verdict in full

The plan required this removal to be justified explicitly, because it is the one path in the task
whose justification is *"it references a module this task deletes"* rather than *"nothing
references it"*.

1. **Static closure — not a member.** It is a shell script; nothing imports it, and it appears in
   no import graph.
2. **Not dynamically reachable.** No `PLUGINDIR` or `autopilot/tasks/` sweep hit (it is under
   `setup/`, neither root). Nothing in the surviving tree shells out to it: the only other
   tree-wide occurrence of the token `install_pyspin` is
   `autopilot/autopilot/hardware/cameras.py:1143`, and that is **inside a docstring**
   (``\`\`install_pyspin.sh\`\` script in \`\`setup\`\```) — prose, not an invocation. `cameras.py`
   is itself removed by plan 05.
3. **Not named by the backend.** `install_pyspin` → 0 hits and `PySpin` → 0 hits across 178
   backend source files. All 50 non-docstring `PySpin` occurrences tree-wide are inside
   `hardware/cameras.py` (plan 05's file) and inside `install_pyspin.sh` itself.
4. **Not reserved by a pending phase.** No pending phase names PySpin/Spinnaker provisioning.

**Rationale recorded for plan 08:** it is Spinnaker/PySpin **camera provisioning for the removed
Terminal workflow**, and its lines 64–65 are
`python -c "from autopilot.setup.request_helpers import download_box; download_box('${…URL}')"` —
i.e. its only live behaviour is invoking a module this same task deletes. Removing
`request_helpers.py` without it would leave a guaranteed 2(c) shell-scan violation; removing it
without `request_helpers.py` would leave an orphan. They are one removal, and were deleted in that
order (consumer first).

### B. The `setup_autopilot.py:198` launcher string — fixed, not deleted

`setup/setup_autopilot.py` **survives** (`autopilot/__init__.py:4` imports it unconditionally;
deleting it breaks `import autopilot` outright). Only its Terminal branch was removed.

`make_launch_script()` had two branches. The `PILOT`/`CHILD` branch (writing
`python3 -m autopilot.core.pilot`) is untouched. The `elif prefs['AGENT'] == 'TERMINAL':` branch
at :193–198, whose last line was

```python
launch_file_open.write("python3 -m autopilot.core.terminal -f " + str(prefs_fn) + "\n")
```

was replaced with an explicit `else: raise ValueError(...)`.

**Why a raise rather than simply dropping the branch** (a deliberate choice, recorded because it
exceeds the plan's literal text): `setup/forms.py:36` still offers `AGENTS = ('TERMINAL', 'PILOT',
'CHILD')`, so `make_launch_script` remains callable with `AGENT='TERMINAL'`. With the branch merely
deleted, control would fall through to `os.chmod(launch_file, permissions)` at :200 against a file
that was never written, surfacing as an opaque `FileNotFoundError` about a path the user never
named. The `else` makes the removed capability say so. `setup_autopilot` can now only ever generate
a pilot launcher, which is the plan's stated requirement. `forms.py` itself was **not** edited — it
is not on this plan's list, and it names only the agent-type string `'TERMINAL'` and
`Scopes.TERMINAL` (defined in `prefs.py`, which survives), never a removed module.

### The remaining references, classified

Whole-tree scan after the deletions, over `.py` / `.sh` / `.json`, with docstring constants
identified by AST node identity:

| Token | CODE | DOC | SELF | Disposition |
|---|---:|---:|---:|---|
| `autopilot.core.terminal` | 0 | 0 | 3 | guard fixtures only |
| `autopilot.core.gui` | 0 | 0 | 0 | clear |
| `autopilot.core.subject` | 0 | **23** | 2 | the plugin Sphinx cross-reference — **not edited** |
| `autopilot.core.plots` | 0 | 0 | 0 | clear |
| `autopilot.core.styles` | 0 | 0 | 0 | clear |
| `autopilot.core.reward` | 0 | 0 | 0 | clear |
| `autopilot.core.utils` | 0 | 0 | 0 | clear |
| `autopilot.viz` | 0 | 0 | 0 | clear |
| `autopilot.data_handlers` | 0 | 0 | 0 | clear |
| `utils.invoker` | 0 | 0 | 0 | clear |
| `request_helpers` | 0 | 0 | **2** | guard fixtures only — see below |
| `install_pyspin` | 0 | **1** | 1 | `cameras.py:1143` docstring (plan 05) |

**Non-docstring, non-SELF references to any removed module: 0.**

The 23 `autopilot.core.subject` docstring lines live in 23 `pilot/plugins/*.py` files
(`AssociationCueReward`, `AssociationLearning`, `BindingTask`, `FindTouchThreshold`,
`FullApetitveTask`, `FullTrainingProtocol`, `GradSimp`, `Graph_Demo_RT`, `ReleaseWater`,
`SimonSays`, `StochasticReward`, `Task1`, `Task2`, `TrainingProtocol`, `WaterCalibration`,
`YoShiTask`, `blink`, `blink_withUnreal`, `elastic_test`, `mic-check`, `simple`, `sm1`, `sm2`).
**Not one was edited.** They are inherited upstream prose, plan 04 removes the files, and the
guard correctly does not flag them — the docstring-node-identity exclusion plan 01 built is doing
exactly the job it was built for.

**The `request_helpers` SELF exclusion is load-bearing, and this task is what made it so.** Before
this task the token had 4 non-self occurrences: `install_pyspin.sh:64`, `:65`, and the guard's own
two fixture lines in `tests/test_tree_integrity.py` (:151 asserting the guard flags a `.sh`
containing `python -c "from autopilot.setup.request_helpers import download_box; download_box()"`,
and :157 asserting the violation message names it). With `install_pyspin.sh` deleted, the guard's
own test file is the **sole remaining match tree-wide** — so a gate greping without
`--exclude=test_tree_integrity.py` would be guaranteed to fail, and the only way to "fix" it would
be to break plan 01's mandated fixture. The exclusion was kept, and the fixture was not touched.

### Verification

```
cd /home/ido/pi-mirror && test ! -e autopilot/autopilot/core/terminal.py \
  && test ! -e autopilot/autopilot/utils/Event.py \
  && test ! -e autopilot/autopilot/setup/request_helpers.py \
  && test ! -e autopilot/autopilot/setup/install_pyspin.sh \
  && test -f autopilot/autopilot/utils/Events.py \
  && test -f autopilot/autopilot/setup/setup_autopilot.py \
  && test -f autopilot/autopilot/core/pilot.py \
  && ! grep -rq 'autopilot\.core\.terminal' --include=*.sh --include=*.json . \
  && ! grep -rq 'request_helpers' --include=*.py --include=*.sh \
       --exclude=test_tree_integrity.py --exclude=check_tree_integrity.py \
       --exclude-dir=tree_integrity . \
  && python3 tools/check_tree_integrity.py --strict \
  && python3 -m compileall -q autopilot/autopilot tools tests
OK: 40 closure members, 30 protected files, 1 known-dangling exemptions held, 0 violations
EXIT=0
```

Pytest delta against `30-PYTEST-BASELINE.json` (never a bare `pytest`, which exits 1 on 179
pre-existing failures): **baseline failing 179 → now failing 179, new failures 0**, exit 0.

Surviving `core/`: `View.py`, `__init__.py`, `loggers.py`, `pilot.py` — one agent, the pilot.
Surviving `setup/`: `__init__.py`, `__main__.py`, `forms.py`, `run_script.py`, `scripts.py`,
`setup_autopilot.py`, `setup_mlx90640.sh` (plan 05 evaluates it with `cameras.py`),
`welcome_msg.txt`.

---

## Totals for this plan

| | Files | Bytes |
|---|---:|---:|
| Task 1 | 108 | 17,857,905 |
| Task 2 | 16 | 285,348 |
| **Plan 30-03 total** | **124** | **18,143,253** |

> **Do not read the whole-tree size delta as this plan's.** The tree measured 202,630,324 bytes at
> plan 01 and 87,291,648 bytes at this plan's exit, but plan 02 executed **concurrently in the same
> tree** during this wave and removed `autopilot/tests/`, `autopilot/examples/` and
> `autopilot/docs/` (all three confirmed absent at exit). This plan's own contribution is the
> 18,143,253 bytes above, measured per-path before each deletion.

## Proposed verdict for plan 08 to transcribe

```
HYG-07 | PROVEN | Terminal-era tree removed in full: terminal/ (106 files, 17.86 MB), run_terminal.sh,
.vscode/, and 16 Pi-side files (core/{terminal,gui,plots,subject,styles,utils,reward}.py, viz/,
data_handlers/, utils/invoker.py, utils/Event.py, setup/request_helpers.py, setup/install_pyspin.sh)
= 124 files / 18,143,253 bytes. Cluster proven self-contained by AST import graph: every importer of
every removed module was itself removed. All four criteria recorded per path. setup_autopilot.py's
autopilot.core.terminal launcher branch replaced by an explicit ValueError; the file survives because
autopilot/__init__.py:4 imports it unconditionally. 0 non-docstring, non-SELF references to any
removed module remain tree-wide; the 23 pilot/plugins docstring cross-references were left untouched
by design. Guard --strict exit 0 (40 closure members, 0 violations), compileall exit 0, pytest delta
0 new failures. No assertion weakened, no protect-listed file touched, no git command run in
/home/ido/pi-mirror.
```
