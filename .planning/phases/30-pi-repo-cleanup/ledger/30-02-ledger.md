# Removal Ledger Fragment — Phase 30 Plan 02 (HYG-08)

**Scope:** vendored and generated bulk under `/home/ido/pi-mirror`.
**Executed:** 2026-08-10.
**Merge target:** §4 of `30-HARDWARE-VALIDATION.md` — merged by plan 08 at the phase gate.
This fragment is deliberately a separate file: plan 03 runs in the same wave and writes its own
fragment, so neither edits the shared validation log directly.

**No git command was run in `/home/ido/pi-mirror`.** All removals were plain `os.remove` /
`shutil.rmtree` through a Python script that asserted the path type (and, for the zero-byte
files, the size) before removing and asserted non-existence after.

---

## A. Criteria evidence (established once, cited per row)

The four criteria from `30-CONTEXT.md`. Each was proven with **unfiltered** output — on this host
`grep` passes through a compressing proxy that can render a matching line blank, so no
"unreferenced" claim below rests on grep.

### C1 — static import closure of `python3 -m autopilot.core.pilot`

Computed by driving the plan-01 guard's own `compute_closure()` directly
(`tools/check_tree_integrity.py`, entry `autopilot/autopilot/core/pilot.py`).

- **40 members, 0 closure violations.** Every member lives under `autopilot/autopilot/`.
- **Zero members fall under any path this plan removed.** Verified by prefix-matching all 40
  relative paths against the removal set: result `NONE`.

### C2 — dynamic reachability

- `PLUGINDIR = /home/pi/Apps/mice_interactive_home_cage/pilot/plugins` (`pilot/prefs.json`).
  No removed path is under `pilot/plugins/`.
- The unguarded `autopilot/tasks/` AST sweep reads `autopilot/autopilot/tasks/`. No removed path
  is under it. (`autopilot/examples/tasks/` is **not** that directory.)
- `SOUNDDIR = /home/pi/Apps/mice_interactive_home_cage/pilot/sounds`, read at
  `autopilot/autopilot/hardware/mixer.py:18` — `self.dir_path = prefs.get("SOUNDDIR")`. Bare
  filenames therefore resolve into `pilot/sounds/`, never into the repo root.
  > **Bookkeeping correction.** The plan's `must_haves.key_links` records this call site as
  > `autopilot/autopilot/stim/sounds/mixer.py`. The real path is
  > `autopilot/autopilot/hardware/mixer.py:18`. The mechanism (`SOUNDDIR` bare-filename
  > resolution) is exactly as described; only the file path in the frontmatter was wrong.
- `importlib` / string-keyed dispatch: no removed path is named by any string literal in the
  surviving tree — see C3.

### C3 — not named by the surviving tree or by the backend

Full-text scan of every file (≤4 MB, text-decoded, `__pycache__`/`.git`/`node_modules` skipped)
in **(a)** the surviving `pi-mirror` tree with the removal set excluded, and **(b)**
`/home/ido/mics-backend` excluding `.planning/` (the planning docs name these paths by design).

Terms scanned: `code_2023.deb`, `code_2023`, `auto_pi_lot.egg-info`, `egg-info`, `Cow.wav`,
`Dying Light Bulb`, `742005847`, `Testing_stepper_motor_Hat`, `testing_motors`,
`adafruit_motorkit`, `MotorKit`, `output.txt`, `environment.yml.save`, `.travis.yml`,
`coveralls`, `.readthedocs`, `CNAME`, `.gitmodules`, `plugins.YoShiTask`, `YoShiTask`,
`networking.station_02`, `networking.node`, `hardware.gpio`, `mlx90640-library`,
`src/pigpio`, `src/mlx90640`, `external/mlx90640`, `autopilot/docs`, `autopilot/examples`,
`autopilot/tests`, `alt_blip8.wav`, `blip.wav`, `lick.wav`.

**Database.** Queried live Postgres (`mics_db`) directly:

| Table | Rows | Any row resolving to a removed path? |
|---|---|---|
| `hardware_libs` | 7 | **No.** `__init__.py`, `gpio.py`, `i2c.py`, `mixer.py`, `timer.py`, `compute_ops.py`, `extlink_demo.py` |
| `hardware_modules` | 9 | **No.** `Left_LED`, `Solenoid`, `Right_LED`, `Mid_LED`, `TIMER`, `MPR121`, `TOUCH_INT`, `COMPUTE`, `ExtlinkDemo` |
| `task_toolkits` | 113 | **No.** No `filename`/`class` field resolves into any removed path |
| `available_locked_states` | 37 | **No.** All 37 `task_filename` values are `pilot/plugins/*.py` modules (plans 04/05), none is an `autopilot/`-root path |

> **Trap avoided:** `available_locked_states` does contain `YoShiTask.py :: YoShiTask`. That row
> resolves to `pilot/plugins/YoShiTask.py`, which is **plan 04's** target and is untouched here.
> The file this plan removed is `autopilot/plugins.YoShiTask` — a **zero-byte logger output
> file** named `<logger>.<child>`, produced by a `FileHandler` that fell back to the process CWD.
> Same string, unrelated artifacts.

### C4 — not reserved by a pending phase

Phase 26 reserves `hardware/openephys_client.py`, `tests/test_openephys_client.py`,
`tests/test_openephys_markers.py`. Verified: **no file matching `openephys` exists anywhere under
`autopilot/tests/`**, and the two reserved test names belong to `/home/ido/pi-mirror/tests/`
(the lab's root suite, HYG-13-protected, reserved-absent in the protect-list) — a different
directory that this plan did not touch. No other removed path is reserved by any pending phase.

---

## B. Removal ledger — one row per path

Verdict key: **PASS** = criterion holds, i.e. the path is removable on that criterion.
All 28 paths passed all four. Sizes are bytes, measured immediately before removal.

| # | Path | Bytes | C1 not in static closure | C2 not dynamically reached | C3 not named by backend | C4 not reserved | Evidence |
|---|---|---|---|---|---|---|---|
| 1 | `autopilot/code_2023.deb` | 87,013,118 | PASS — not a `.py`, absent from the 40-member closure | PASS — not under `pilot/plugins/` or `autopilot/autopilot/tasks/`; a Debian package is not importable | PASS — `code_2023.deb` and `code_2023`: **0 hits** in surviving tree, **0** in `mics-backend` | PASS | Vendored VS Code installer, 83 MB, zero references |
| 2 | `autopilot/docs/` | 9,095,683 | PASS — no member under it | PASS — not a sweep directory | PASS — `autopilot/docs`: 2 hits, **both are the guard's own assertion literals** (`tools/tree_protect_list.json:51` `scan_skip`, `tools/tree_integrity/final_checks.py:23` `MUST_BE_GONE`), excluded by the guard's `SELF_PATHS` | PASS | Sphinx tree. **Finding:** it is mixed source+output — it holds `conf.py`, `index.rst`, `*.rst` **and** built artifacts (`searchindex.js`, `objects.inv`, `.buildinfo`, `_images/`, `_static/`). There is **no `docs/source/`**. Removed regardless per plan step A: nothing builds it (no CI survives) and nothing links it |
| 3 | `autopilot/examples/` | 24,886 | PASS | PASS — `examples/tasks/` is not `autopilot/autopilot/tasks/`, the swept path | PASS — 2 hits, both guard self-literals (as row 2) | PASS | Upstream examples. `examples/tasks/blink.py:64` names `autopilot.core.subject` **inside a class docstring** — Sphinx prose, which the guard's 2(b) skips by docstring node identity, not a reference |
| 4 | `autopilot/tests/` | 37,775 | PASS | PASS | PASS — 4 hits: 2 guard self-literals + 2 inside the guard's **own synthetic-tree unit test** (`tests/test_tree_integrity.py:245,248`), which builds a fake `autopilot/tests/test_terminal.py` in a tmpdir | PASS — contains **no** `openephys` file | Upstream suite, needs PySide2, unmaintained here. **Not** `/home/ido/pi-mirror/tests/` — that has 22 modules and is untouched (see §C) |
| 5 | `autopilot/src/` | 0 | PASS | PASS | PASS — `src/pigpio` **0 hits**, `src/mlx90640` **0 hits** | PASS | Two **uninitialised** submodule mount points (`pigpio`, `mlx90640-library`), 0 bytes of content. The only surviving reference to a build of that library is `autopilot/autopilot/setup/setup_mlx90640.sh:19,21`, which points at `autopilot/external/mlx90640-library` — a **different** path (`autopilot/autopilot/external/` exists and holds only `__init__.py`). Removing `src/` therefore cannot break anything that was not already broken |
| 6 | `autopilot/.gitmodules` | 221 | PASS | PASS | PASS — `.gitmodules`: **0 hits** in surviving tree and in `mics-backend` | PASS | Declared exactly the two `src/` submodules removed in row 5. Deleted as a **plain file**; no git operation |
| 7 | `autopilot/home/` | 120,740 | PASS | PASS | PASS — the full path `home/pi/Apps/mice_interactive_home_cage/lick.wav`: **0 hits** | PASS | An unexpanded `~` written literally as `home/`. Its **sole** file is `home/pi/Apps/mice_interactive_home_cage/lick.wav`, md5 `86e87279f1e7d52eed52c4ef84193f3e`, **byte-identical** to the reachable `pilot/sounds/lick.wav` (same md5, both 120,740 B). No unique asset lost |
| 8 | `autopilot/~/` | 13,791 | PASS | PASS | PASS | PASS | The same accident with the tilde left literal. Contains only 6 stale `pilot/logs/*.log` files |
| 9 | `autopilot/auto_pi_lot.egg-info/` | 15,567 | PASS | PASS | PASS — `auto_pi_lot`: 1 hit, a **Twitter badge URL** in `autopilot/README.md:6`, not a path reference. `egg-info`: 2 hits, both **exclusion rules** (`tools/sync_pi.sh:56 --exclude '*.egg-info'`, `autopilot/.gitignore:24`) | PASS | `setuptools` build artifact |
| 10 | `autopilot/Cow.wav` | 465,808 | PASS | PASS | PASS — `Cow.wav`: **0 hits** | PASS | Unreferenced audio |
| 11 | `autopilot/Dying Light Bulb-SoundBible.com-742005847.wav` | 131,532 | PASS | PASS | PASS — `Dying Light Bulb` **0 hits**, `742005847` **0 hits** | PASS | Third-party (SoundBible) audio, unreferenced |
| 12 | `autopilot/Testing_stepper_motor_Hat/` | 753 | PASS | PASS | PASS — `Testing_stepper_motor_Hat` **0 hits**, `testing_motors` **0 hits**, in both trees | PASS | **Unenumerated residue — full verdict in §D below** |
| 13 | `autopilot/.travis.yml` | 2,597 | PASS | PASS | PASS — `.travis.yml`: **0 hits** | PASS | Upstream CI config for a CI this repo does not run |
| 14 | `autopilot/.coveralls.yml` | 0 | PASS | PASS | PASS — `coveralls`: 2 hits, neither naming the file: a **README badge URL** (`autopilot/README.md:13`) and the **pip package name** in `autopilot/requirements/requirements_tests.txt:22` | PASS | Zero-byte upstream CI config. Distinct from `autopilot/.coveragerc`, which plan 01 removed |
| 15 | `autopilot/.readthedocs.yml` | 576 | PASS | PASS | PASS — `.readthedocs`: 2 hits, both **`picamera` documentation URLs** in `autopilot/autopilot/hardware/cameras.py:599,633`, not references to this file | PASS | RTD build config; nothing builds the docs (row 2) |
| 16 | `autopilot/CNAME` | 20 | PASS | PASS | PASS — `CNAME`: **0 hits** in the surviving pi tree; the `mics-backend` hits are all `…FUNCNAME` substrings inside vendored `numpy`/`pygments` under `mics_post_analysis/.pylibs/` | PASS | GitHub Pages domain file for the upstream docs site |
| 17 | `autopilot/hardware.gpio` | 0 | PASS | PASS | PASS — see the logger-name note below | PASS | Zero-byte logger output file (asserted `isfile` + size 0 before removal) |
| 18 | `autopilot/networking.node` | 0 | PASS | PASS | PASS — see below | PASS | idem |
| 19 | `autopilot/networking.station_02` | 0 | PASS | PASS | PASS — see below | PASS | idem |
| 20 | `autopilot/.pilot` | 0 | PASS | PASS | PASS | PASS | idem |
| 21 | `autopilot/plugins` | 0 | PASS | PASS | PASS | PASS | Zero-byte **FILE**, confirmed `os.path.isfile` + size 0. **Unrelated to `pilot/plugins/`** (plan 04's target directory), which is untouched |
| 22 | `autopilot/plugins.YoShiTask` | 0 | PASS | PASS | PASS — see the `available_locked_states` trap note in §A/C3 | PASS | idem |
| 23 | `autopilot/registry` | 0 | PASS | PASS | PASS | PASS | idem |
| 24 | `output.txt` (repo root) | 16,612 | PASS | PASS | PASS — `output.txt`: **0 hits** | PASS | Stray captured stdout |
| 25 | `environment.yml.save` | 1,583 | PASS | PASS | PASS — `environment.yml.save`: **0 hits** | PASS | nano emergency save — **diff verdict in §E**. `environment.yml` kept |
| 26 | `blip.wav` (repo root) | 88,244 | PASS | PASS — resolves through `SOUNDDIR` to `pilot/sounds/`, never the root | PASS — all 4 hits are bare-filename or absolute-`pilot/sounds/` references, listed in §F | PASS | **Byte-identical duplicate — md5 in §F** |
| 27 | `alt_blip8.wav` (repo root) | 661,814 | PASS | PASS — as row 26 | PASS — all 7 pi-tree hits are bare-filename references in `pilot/plugins/*` and `terminal/plugins/*`; the `mics-backend` hits are **ES event payloads** (`'audio_file': 'alt_blip8.wav'`) in analysis notebooks, i.e. recorded data, not path references | PASS | **Byte-identical duplicate — md5 in §F** |
| 28 | `autopilot/docs`, `examples`, `tests` — see §G | — | — | — | — | — | `scan_skip` retirement |

**Total removed by this plan: 97,691,320 bytes across 28 paths** (20 files + 8 directories).

> **The zero-byte logger-name files (rows 17–23).** Strings like `hardware.gpio`,
> `networking.node`, `networking.station_02` **do** occur in surviving code — e.g.
> `autopilot/autopilot/core/loggers.py:28,56` (which derives `hardware.gpio` as a *logger name*
> from `autopilot.hardware.gpio.Digital_In`) and `autopilot/autopilot/tasks/free_water.py:7` etc.
> (which import the *module* `autopilot.hardware.gpio`). **Neither is a reference to these
> files.** These seven are zero-byte **outputs** written by a `FileHandler` whose directory
> fell back to the process CWD; they carry no extension, so `.gitignore`'s `*.log` never caught
> them. They are written, never read. Removing them is safe by construction: if the fallback
> path is ever hit again they are simply recreated, and nothing loads them.

---

## C. Explicitly kept — verified present after removal

Asserted present **before** the removal script ran and **again after** it completed:

`autopilot/LICENSE` (MPL-2.0, mandatory), `autopilot/setup.py`, `autopilot/requirements.txt`,
`autopilot/requirements/`, `autopilot/pyproject.toml`, `autopilot/README.md`,
`autopilot/CITATION.cff`, `autopilot/MANIFEST.in`, `autopilot/CODE_OF_CONDUCT.md`,
`autopilot/CONTRIBUTING.md`, `autopilot/.gitattributes`, `autopilot/.gitignore`,
`environment.yml`, `requirements.txt`, `run_pilot.sh`, `scripts/dev/extlink_smoke.py`,
`pilot/sounds/`, `tests/`.

- `/home/ido/pi-mirror/tests/` holds **22** `*.py` modules (21 pre-existing + plan 01's
  `test_tree_integrity.py`), ≥ the 21 the plan requires. Untouched.
- `pilot/sounds/` is **byte-for-byte unchanged**: 2,326,388 B before and after.
- After removal, `autopilot/` root contains **exactly** the keep-list plus the `autopilot/`
  package and `__pycache__` — **no unenumerated path remains** at that level.

---

## D. Unenumerated residue — four-criteria verdict

### `autopilot/Testing_stepper_motor_Hat/` — REMOVED (753 B, 2 files)

HYG-08 does not name it. Contents: `README.md` (223 B) and `testing_motors.py` (530 B).

| Criterion | Verdict | Evidence |
|---|---|---|
| C1 not in static closure | **PASS** | Not among the 40 closure members. The directory has no `__init__.py` and is not importable as an `autopilot` submodule |
| C2 not dynamically reached | **PASS** | Not under `PLUGINDIR` (`pilot/plugins`) nor under `autopilot/autopilot/tasks/`. `testing_motors.py` defines **no class and no function** — a bare top-level script — so neither the `PLUGINDIR` sweep nor the `autopilot/tasks/` AST class sweep can discover anything in it |
| C3 not named by backend | **PASS** | `Testing_stepper_motor_Hat`: **0 hits**; `testing_motors`: **0 hits** — in the surviving pi tree *and* in `mics-backend`. No `hardware_libs.filename`, `hardware_modules.class_name`, `task_toolkits` or `available_locked_states` row resolves to it |
| C4 not reserved | **PASS** | Not among Phase 26's three reserved paths; named by no pending phase |

All four hold → removed. Two supporting observations:

- **The script is already broken.** `testing_motors.py:9` assigns `kit.motor1.throttle` but `kit`
  is never bound (the `MotorKit(...)` construction line is absent) — it raises `NameError` on the
  first loop iteration. It is bench scratch, not a working tool.
- **Deferred, not silently dropped:** the `README.md` was the only place recording that
  `pip install adafruit-circuitpython-motorkit` is required. That package **is** a live runtime
  dependency of a **surviving** file — `autopilot/autopilot/hardware/i2c.py:890`
  (`from adafruit_motorkit import MotorKit`) and `:906` (`self.kit = MotorKit(address=0x60)`) —
  and it is **not listed in `requirements.txt`**. The dependency note is preserved here verbatim
  so it is not lost with the directory:
  > `pip install adafruit-circuitpython-motorkit` — docs:
  > `https://learn.adafruit.com/adafruit-dc-and-stepper-motor-hat-for-raspberry-pi/installing-software`
  >
  > Address note from `testing_motors.py:1` / `i2c.py:906`: the hat answers at `0x60`
  > (`i2cdetect` shows 60 and 70; 70 errors).

  **This plan did not edit `requirements.txt`** — it is on the explicit KEEP list and outside this
  plan's `<files>` block. Recorded as a deferred item for the phase gate.

### Other unenumerated paths at `autopilot/` root

**None.** After removal the directory listing is exactly the keep-list; every path that was there
and is not on the keep-list is accounted for by a row in §B.

---

## E. `environment.yml` vs `environment.yml.save`

```
$ diff environment.yml environment.yml.save
1c1
< name: autopilot
---
> 	name: autopilot
```

Exit 1, **one line differs**: the `.save` copy has a leading **tab** before `name:`, which makes
it invalid YAML (a mapping key cannot be indented at the document root). It is a nano emergency
save of a mid-edit buffer. `environment.yml` — the valid copy — is **kept**; `environment.yml.save`
removed. Confirms the plan's expectation exactly.

---

## F. Byte-identity proof for the root wavs

| File | Size | md5 |
|---|---|---|
| `blip.wav` (repo root, **removed**) | 88,244 | `5946f59e857afd17f2a97c090ddca784` |
| `pilot/sounds/blip.wav` (**kept**) | 88,244 | `5946f59e857afd17f2a97c090ddca784` |
| `alt_blip8.wav` (repo root, **removed**) | 661,814 | `0bdf7c99b612ac20e983307ca035f534` |
| `pilot/sounds/alt_blip8.wav` (**kept**) | 661,814 | `0bdf7c99b612ac20e983307ca035f534` |

**Identical in both pairs.** The root copies carried no distinct asset.

**Why only the `pilot/sounds/` copies are reachable.** `autopilot/autopilot/hardware/mixer.py:18`
reads `self.dir_path = prefs.get("SOUNDDIR")`, and `pilot/prefs.json` sets
`SOUNDDIR = /home/pi/Apps/mice_interactive_home_cage/pilot/sounds`. Every reference found is
either a bare filename resolved through that directory or an absolute `pilot/sounds/` path:

- `pilot/plugins/StochasticReward.py:209`, `pilot/plugins/AssociationCueReward.py:154` — `file_name = "blip.wav"`
- `pilot/plugins/YoShiTask.py:432,522` — `mixer.Sound('/home/pi/Apps/mice_interactive_home_cage/pilot/sounds/blip.wav')` (absolute, and it points at `pilot/sounds/`)
- `pilot/plugins/PreLrn_youri.py:194,216`, `pilot/plugins/AppetitiveTaskReal.py:233`, `pilot/plugins/ExtinctionAUDIO.py:231` — `file_name = "alt_blip8.wav"`
- `terminal/plugins/{Generalzation,ExtinctionAUDIO,ExtinctionLED}.py:215` — commented out

**Not one reference resolves to the repo root.** `pilot/sounds/` is untouched by this phase.

---

## G. `scan_skip` retirement — the guard's Wave-1 blind spot is now closed

Plan 01 added a `scan_skip` list to `tools/tree_protect_list.json` for one reason: three
directories contained **genuine** imports of modules that plans 02/03/05 delete, and whichever
plan landed second would have turned the guard red for no real defect.

**The two references the skip was covering:**

| Reference | Imports | Deleted by |
|---|---|---|
| `autopilot/tests/test_terminal.py:9` | `import autopilot.core.terminal` | plan 03 |
| `autopilot/tests/test_registry.py:14-16` | `autopilot.hardware.cameras` | plan 05 |

**This plan makes the skip moot.** All three Wave-1 `scan_skip` directories —
`autopilot/tests/`, `autopilot/examples/`, `autopilot/docs/` — **no longer exist** (rows 2–4).
The exemption can therefore never harden into a blind spot: it now covers nothing.

**The skip is deliberately left in `tree_protect_list.json`.** Removing the entries would be
editing the protect-list mid-phase, which the phase forbids; and the fourth prefix (`terminal/`)
belongs to plan 03, still in flight in this same wave.

**Plan 08 closes the loop.** `--final` check **F1** (`tools/tree_integrity/final_checks.py:23`,
`MUST_BE_GONE = ("autopilot/tests", "autopilot/examples", "autopilot/docs", "terminal")`) asserts
all four are gone at the phase exit gate. Plan 08 should verify F1 passes on the first three
without any further work from this plan.

---

## H. Size measurements — three numbers, before and after

Measured with `du -sb` from `/home/ido/pi-mirror`.

| Measurement | §1 baseline (plan 01) | Before this plan | After this plan |
|---|---|---|---|
| `du -sb --exclude=.git .` | 202,630,324 | 202,644,728 | 87,598,564 |
| `du -sb .git` | ~197,550,529 | 197,550,529 | 197,550,529 (untouched) |
| `du -sb pilot/sounds` | 2,326,388 | 2,326,388 | **2,326,388 (unchanged)** |

**Attribution — read this before computing the budget.** The tree-level drop of **115,046,164 B**
is **larger** than this plan's own removals because **plan 03 executed concurrently in the same
wave** and removed `terminal/`, `.vscode/` and `run_terminal.sh` during the same window.

- **This plan's own contribution is 97,691,320 B**, measured per-path immediately before each
  removal and itemised in §B. That alone clears the plan's ≥ 90 MB success criterion.
- The remainder (**17,354,844 B**) belongs to plan 03 and is accounted for in **its** fragment.
  Plan 08 must not double-count it.

**Budget position.** HYG-08's exit budget is **≤ 8 MB excluding `.git` AND excluding
`pilot/sounds/`**. Current standing:

```
87,598,564 (excl .git) − 2,326,388 (pilot/sounds) = 85,272,176 B  ≈ 81.3 MiB
```

Still far above 8 MB, **as expected at Wave 1** — plans 04–07 have not run yet, and the largest
remaining item is `pilot/` (plugins, logs, data). Plan 08 recomputes this after the deferred
cache purge; **this is not a HYG-08 failure**, it is the wave-1 waypoint.

---

## I. Deferred to plan 08 — cache purge hand-off

**The `__pycache__` / `*.pyc` / `.pytest_cache` purge was deliberately NOT performed here.**

Plan 03 runs `compileall` in this same wave and would regenerate every cache directory this plan
deleted, so a purge-then-assert in plan 02 is a race against a sibling. The purge belongs in
**plan 08 Task 1**, immediately **before** the manifest diff and the final size measurement,
where nothing runs `compileall` afterwards.

`.gitignore` (§J) already keeps all four patterns out of the new repository in the meantime, so
nothing leaks into publication regardless of when the on-disk purge happens.

**Deleting the caches later costs nothing.** Per `30-CONTEXT.md`, the Pi's `.cpython-37` bytecode
was used by the audit as evidence of *what actually loads on the device* (it is what settled the
`jackclient.py` / `pyoserver.py` vs `sounds.py` / `base.py` question). **That evidence has already
been extracted into `30-CONTEXT.md`**, so the caches are now redundant and their removal destroys
no reasoning this phase depends on.

---

## J. `.gitignore` hardening

`/home/ido/pi-mirror/.gitignore` before (6 lines):

```
pilot/logs/.pilot.log.*
*.log
*.log.*
*.pyc
*.csv
*.h5
```

Appended (existing lines untouched):

```
__pycache__/
.pytest_cache/
*.egg-info/
*.deb
```

`pilot/data/` and `pilot/logs/` content exclusions are **plan 07's** job (HYG-10) and were left
alone.

---

## K. Verification recorded

| Check | Result |
|---|---|
| `python3 tools/check_tree_integrity.py --strict` | **exit 0** — `OK: 40 closure members, 30 protected files, 1 known-dangling exemptions held, 0 violations`. No assertion weakened, no protect-list entry edited, `--rebaseline` never run |
| `python3 -m compileall -q autopilot/autopilot tools tests` | **exit 0** |
| Pi suite, plan 01 `delta_command` (never a bare `pytest`) | **exit 0** — `now failing: 179, baseline: 179, new failures: 0` |
| `autopilot/LICENSE` present | yes |
| `/home/ido/pi-mirror/tests/` module count | 22 `*.py` (≥ 21 required) |
| `pilot/sounds/` size | 2,326,388 B, unchanged |
| `blip.wav` / `alt_blip8.wav` gone from root, present in `pilot/sounds/` | yes |
| Git commands run in `/home/ido/pi-mirror` | **none** — deletions were `os.remove` / `shutil.rmtree` |

---

## L. Proposed verdict — plan 08 transcribes into §4

```
HYG-08 | PROVEN | 28 paths / 97,691,320 B of vendored and generated bulk removed from
/home/ido/pi-mirror: the 83 MB code_2023.deb installer, the 9.1 MB Sphinx docs/ tree, the
upstream tests/ and examples/ suites, two uninitialised submodule mounts plus .gitmodules, the
tilde-literal home/ and ~/ directories, the egg-info build artifact, two unreferenced wavs, four
upstream CI dotfiles, seven zero-byte logger-output files, output.txt, the invalid
environment.yml.save, and the two byte-identical root wav duplicates (md5s in §F). Every path
carries a four-criteria verdict in §B; all 28 passed all four, with C1 proven against the
40-member static closure, C3 against unfiltered full-text scans of both trees plus four live DB
tables, and C4 against Phase 26's three reserved paths. LICENSE, pilot/sounds/ (2,326,388 B
unchanged) and the 22-module root tests/ suite are intact. check_tree_integrity.py --strict exits
0 with no assertion weakened; compileall exits 0; the pytest delta is 0 new failures against the
179-node baseline. All three Wave-1 scan_skip directories are gone, retiring the guard's blind
spot — plan 08 F1 asserts they stay gone. .gitignore hardened with __pycache__/, .pytest_cache/,
*.egg-info/, *.deb; the on-disk cache purge is deferred to plan 08 Task 1 (§I).
```

---

*Phase: 30-pi-repo-cleanup · Plan: 02 · Requirement: HYG-08*
