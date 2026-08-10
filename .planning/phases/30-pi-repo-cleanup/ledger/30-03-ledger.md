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
