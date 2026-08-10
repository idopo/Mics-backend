---
phase: 30-pi-repo-cleanup
plan: 02
subsystem: pi-mirror
tags: [cleanup, vendored-bulk, reachability, gitignore, hyg-08, wave-1]

# Dependency graph
requires:
  - "30-01 — tools/check_tree_integrity.py --strict, tree_protect_list.json, 30-PYTEST-BASELINE.json"
provides:
  - "A pi-mirror tree with no vendored installer, no pre-built Sphinx output, no uninitialised submodule and no build artifact"
  - "Hardened /home/ido/pi-mirror/.gitignore (__pycache__/, .pytest_cache/, *.egg-info/, *.deb)"
  - "ledger/30-02-ledger.md — 28 four-criteria removal rows + scan_skip retirement + 3 size numbers + plan-08 cache hand-off"
  - "All three Wave-1 scan_skip directories deleted, retiring the guard's blind spot inside its own wave"
affects: [30-03, 30-04, 30-05, 30-06, 30-07, 30-08, 30-09]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Assert-before-remove: every deletion asserted path type (and size 0 for the zero-byte files) before removal and non-existence after"
    - "Keep-list asserted present both before and after the removal script, so a mis-scoped rmtree fails loudly instead of silently"
    - "Every 'unreferenced' claim proven by an unfiltered Python full-text scan, never by grep"
    - "Byte-identity (md5) required before deleting any apparent duplicate asset"

key-files:
  created:
    - .planning/phases/30-pi-repo-cleanup/ledger/30-02-ledger.md
  modified:
    - /home/ido/pi-mirror/.gitignore
  deleted:
    - /home/ido/pi-mirror/autopilot/code_2023.deb
    - /home/ido/pi-mirror/autopilot/docs/
    - /home/ido/pi-mirror/autopilot/examples/
    - /home/ido/pi-mirror/autopilot/tests/
    - /home/ido/pi-mirror/autopilot/src/
    - /home/ido/pi-mirror/autopilot/.gitmodules
    - /home/ido/pi-mirror/autopilot/home/
    - /home/ido/pi-mirror/autopilot/~/
    - /home/ido/pi-mirror/autopilot/auto_pi_lot.egg-info/
    - /home/ido/pi-mirror/autopilot/Cow.wav
    - "/home/ido/pi-mirror/autopilot/Dying Light Bulb-SoundBible.com-742005847.wav"
    - /home/ido/pi-mirror/autopilot/Testing_stepper_motor_Hat/
    - /home/ido/pi-mirror/autopilot/.travis.yml
    - /home/ido/pi-mirror/autopilot/.coveralls.yml
    - /home/ido/pi-mirror/autopilot/.readthedocs.yml
    - /home/ido/pi-mirror/autopilot/CNAME
    - /home/ido/pi-mirror/autopilot/hardware.gpio
    - /home/ido/pi-mirror/autopilot/networking.node
    - /home/ido/pi-mirror/autopilot/networking.station_02
    - /home/ido/pi-mirror/autopilot/.pilot
    - /home/ido/pi-mirror/autopilot/plugins
    - /home/ido/pi-mirror/autopilot/plugins.YoShiTask
    - /home/ido/pi-mirror/autopilot/registry
    - /home/ido/pi-mirror/output.txt
    - /home/ido/pi-mirror/environment.yml.save
    - /home/ido/pi-mirror/blip.wav
    - /home/ido/pi-mirror/alt_blip8.wav

key-decisions:
  - "Removed Testing_stepper_motor_Hat/ (unenumerated) after all four criteria passed, but transcribed its adafruit-circuitpython-motorkit install note into the ledger because surviving i2c.py:890 imports that package and requirements.txt does not list it"
  - "Did NOT purge __pycache__/.pyc/.pytest_cache — deferred to plan 08 per the plan, because plan 03's compileall runs in the same wave"
  - "Left the scan_skip entries in tree_protect_list.json rather than editing the protect-list mid-phase; the three directories are gone, so the exemption now covers nothing, and plan 08 F1 proves it"
  - "Task 1 carries no commit: its deliverables live entirely in pi-mirror, which is not agent-managed version control (same precedent as 30-01 Task 1)"

patterns-established:
  - "Concurrent-wave size attribution: report per-path totals measured before removal, not tree-level deltas, when a sibling plan is deleting in the same window"

requirements-completed: [HYG-08]

# Metrics
duration: 22min
completed: 2026-08-10
---

# Phase 30 Plan 02: Vendored and Generated Bulk Summary

**28 paths / 97,691,320 bytes of installer, pre-built Sphinx output, upstream test suite, uninitialised submodules, tilde-literal directories, build artifacts and byte-identical wav duplicates removed from `pi-mirror` — every one carrying a four-criteria verdict, with the guard green, `compileall` clean, and zero new pytest failures.**

## Performance

- **Duration:** 22 min
- **Started:** 2026-08-10T13:12:11Z
- **Completed:** 2026-08-10T13:34Z
- **Tasks:** 2
- **Paths removed:** 28 (20 files, 8 directories); 1 file modified; 1 doc created

## Accomplishments

- **97,691,320 B removed across 28 paths**, itemised per path in `ledger/30-02-ledger.md` §B. Largest: `code_2023.deb` (87,013,118), `docs/` (9,095,683), `alt_blip8.wav` (661,814), `Cow.wav` (465,808).
- **All four removal criteria proven per path, none on grep.** C1 against the guard's own 40-member static closure (result: zero closure members under any removal target); C2 against `PLUGINDIR` / the `autopilot/autopilot/tasks/` sweep / `SOUNDDIR` resolution; C3 against unfiltered full-text scans of both trees **plus four live Postgres tables**; C4 against Phase 26's three reserved paths.
- **The guard's Wave-1 blind spot is retired inside its own wave.** All three `scan_skip` directories (`autopilot/{tests,examples,docs}/`) are gone, so the exemption plan 01 added now covers nothing. The two references it existed for — `autopilot/tests/test_terminal.py:9` (`import autopilot.core.terminal`) and `autopilot/tests/test_registry.py:14-16` (`autopilot.hardware.cameras`) — are recorded in ledger §G with a pointer to plan 08's F1.
- **Byte-identity proven before deleting any duplicate.** Root `blip.wav` and `alt_blip8.wav` match the `pilot/sounds/` copies md5-for-md5 (`5946f59e…a784`, `0bdf7c99…f534`). `pilot/sounds/` is **2,326,388 B before and after — unchanged**.
- **`.gitignore` hardened** with `__pycache__/`, `.pytest_cache/`, `*.egg-info/`, `*.deb`; all six original lines verified preserved.
- **Every gate green:** `check_tree_integrity.py --strict` exit 0 (`40 closure members, 30 protected files, 1 known-dangling exemptions held, 0 violations`), `compileall` exit 0, pytest delta **0 new failures** against the 179-node baseline.
- **No git command was run in `/home/ido/pi-mirror`.** Removals were `os.remove` / `shutil.rmtree` from a Python script whose working directory was set with `os.chdir`, never a shell `cd` that a later compound command could inherit.

## Task Commits

Task 1's deliverables are **entirely inside `/home/ido/pi-mirror`**, which is not agent-managed
version control — the standing Pi rule forbids any git command there. It therefore has no commit;
its evidence is the recorded verification output below and ledger §B/§K. This follows the
precedent set by 30-01 Task 1.

1. **Task 1: Remove vendored, generated and duplicate bulk** — no commit (pi-mirror is not git-managed by the agent); verified by the automated chain below
2. **Task 2: Harden .gitignore and record the ledger** — `d222d44` (chore), plus `90554d5` (docs) correcting the size-attribution note

## Files Created/Modified

**In `/home/ido/pi-mirror` (not version-controlled by the agent):**
- **Deleted:** the 28 paths listed in the frontmatter
- **Modified:** `.gitignore` — 6 lines → 10 lines, existing lines untouched

**In `mics-backend` (committed):**
- `.planning/phases/30-pi-repo-cleanup/ledger/30-02-ledger.md` — sections A (criteria evidence), B (28 removal rows), C (keep-list verification), D (unenumerated residue verdict), E (`environment.yml` diff), F (md5 identity proof), G (`scan_skip` retirement), H (three size numbers), I (plan-08 cache hand-off), J (`.gitignore`), K (verification), L (proposed `HYG-08 | PROVEN`)

## Decisions Made

- **Wrote a separate ledger fragment instead of editing `30-HARDWARE-VALIDATION.md`.** Plan 03 is executing in the same wave against the same shared file; plan 08 merges every fragment at the phase gate.
- **Deferred the cache purge to plan 08, as instructed.** Plan 03's `compileall` regenerates `__pycache__` in this same wave, so a purge-then-assert here would have been a race against a sibling. `.gitignore` already keeps all four patterns out of the publication repo in the meantime, and ledger §I records that the Pi's `.cpython-37` bytecode evidence was already extracted into `30-CONTEXT.md`, so deleting the caches later destroys no reasoning.
- **Left the `scan_skip` entries in `tree_protect_list.json`.** Removing them would be editing the protect-list mid-phase, which the phase forbids, and the fourth prefix (`terminal/`) belongs to plan 03, still in flight. The entries are now inert; plan 08's F1 asserts the directories stay gone.
- **Removed `autopilot/Testing_stepper_motor_Hat/` but preserved its dependency note.** See Finding 2.

## Deviations from Plan

### Findings (recorded, not silently patched)

**Finding 1. [Rule 1 — plan frontmatter error] `must_haves.key_links` names the wrong `mixer.py`.**
- **Found during:** Task 1, proving C2 for the two root wavs
- **Issue:** The plan's frontmatter records the `SOUNDDIR` call site as `autopilot/autopilot/stim/sounds/mixer.py`. **That path does not exist.** The real one is `autopilot/autopilot/hardware/mixer.py:18` — `self.dir_path = prefs.get("SOUNDDIR")`.
- **Why it mattered:** this is the single link that proves the root wavs are unreachable while the `pilot/sounds/` copies are reachable. Had I asserted the frontmatter path, the check would have silently found nothing and I would have deleted two files on a link I never verified.
- **Fix:** located and verified the real call site, then recorded the correction in ledger §A/C2. The mechanism the frontmatter describes is exactly right; only the file path was wrong. Nothing was weakened.
- **Verification:** `SOUNDDIR = /home/pi/Apps/mice_interactive_home_cage/pilot/sounds` in `pilot/prefs.json`; all 11 surviving `blip.wav`/`alt_blip8.wav` references resolve by bare filename or by an absolute `pilot/sounds/` path (`pilot/plugins/YoShiTask.py:432,522`), none to the repo root.

**Finding 2. [Rule 2 — knowledge that would have been lost] `adafruit-circuitpython-motorkit` is a live dependency of a surviving file and is not in `requirements.txt`.**
- **Found during:** Task 1 step B, running the four criteria on the unenumerated `autopilot/Testing_stepper_motor_Hat/`
- **Issue:** All four criteria passed (`Testing_stepper_motor_Hat` and `testing_motors`: **0 hits** in both trees; no DB row; not reserved), and `testing_motors.py` is in fact already broken — it assigns `kit.motor1.throttle` at line 9 with `kit` never bound, so it raises `NameError` immediately. But its `README.md` was the **only** record that `pip install adafruit-circuitpython-motorkit` is required, and **surviving** `autopilot/autopilot/hardware/i2c.py:890` does `from adafruit_motorkit import MotorKit` (`:906` constructs `MotorKit(address=0x60)`). `requirements.txt` does not list the package.
- **Fix:** removed the directory (the criteria are the criteria), but transcribed the install command, the docs URL and the `0x60` address note verbatim into ledger §D so a fresh-image install does not silently lose an i2c dependency. **Did not edit `requirements.txt`** — it is on this plan's explicit KEEP list and outside the `<files>` block. Flagged as a deferred item.
- **Impact:** none on this plan. Real risk to the "new unit, fresh image" path in the phase's rollout topology, since that unit installs from `requirements.txt`.

**Finding 3. [Bookkeeping] `autopilot/docs/` is mixed source + build output, not pure output.**
- **Found during:** Task 1 step A, honouring the plan's "confirm there is no `docs/source/`" instruction
- **Issue:** The plan describes `docs/` as "pre-built Sphinx *output*". It is actually both: `conf.py`, `index.rst` and a full `*.rst` tree sit alongside `searchindex.js`, `objects.inv`, `.buildinfo`, `_images/` and `_static/`. There is **no `docs/source/`** subdirectory.
- **Fix:** removed regardless, exactly as the plan's own escape clause directs ("if there is, still remove: nothing builds it and nothing links it"). Corroborated: the only surviving references to `autopilot/docs` are the guard's own assertion literals, and every CI/RTD config that could build it was removed in the same task.
- **Recorded in:** ledger §B row 2. Not a scope change.

### Bookkeeping

- **Tree-level size deltas are unusable this wave.** `du -sb --exclude=.git .` fell 202,644,728 → 87,598,564 → 87,291,648 within minutes, because plan 03 was concurrently removing `terminal/`, `.vscode/` and `run_terminal.sh`. This plan's own contribution is the stable **97,691,320 B** measured per path immediately before each removal; the remaining ~17.4 MB belongs to plan 03's fragment. Ledger §H states the attribution explicitly so plan 08 does not double-count, and flags the excl-`.git` row for re-measurement at the gate.
- `autopilot/.coveralls.yml` (this plan) is a different file from `autopilot/.coveragerc` (removed by plan 01). No overlap.
- The guard's `note: unparseable json (skipped for path check): .vscode/launch.json`, present at plan 01's close, no longer appears — plan 03 removed `.vscode/` during this window.

---

**Total deviations:** 3 findings recorded (1 plan frontmatter error caught before it could mislead a deletion, 1 dependency-knowledge preservation, 1 bookkeeping correction), 0 assertions weakened, 0 protect-list edits, 0 extra paths deleted.
**Impact on plan:** None on scope. All 28 removals are exactly the plan's `<files>` block plus the one unenumerated path the plan explicitly told me to adjudicate.

## Issues Encountered

- **The `autopilot/plugins` trap is real and would have been easy to get wrong.** It is a zero-byte **file** at `autopilot/` root, entirely unrelated to `pilot/plugins/` (plan 04's directory). The removal script asserted `os.path.isfile` **and** `size == 0` on all seven logger-name files before touching any of them.
- **`available_locked_states` contains a row `YoShiTask.py :: YoShiTask`.** That resolves to `pilot/plugins/YoShiTask.py` (plan 04), not to the zero-byte `autopilot/plugins.YoShiTask` this plan removed. A C3 check done on the bare token `YoShiTask` would have wrongly blocked the removal; the ledger records the distinction.
- **`setup_mlx90640.sh` points at `autopilot/external/`, not `autopilot/src/`.** The uninitialised submodule mounts under `src/` were never the path the setup script builds, so removing them cannot break anything that was not already broken. `autopilot/autopilot/external/` survives (it holds `__init__.py`, a closure member).

## User Setup Required

Nothing new from this plan. The two human actions opened by plan 01 remain open and unchanged: **revoke the Gmail app password at Google** before publication, and **clear `ExtlinkDemo` off pilot 1** before the HYG-02 rig session.

One item added to the phase's deferred list: **`adafruit-circuitpython-motorkit` should be added to `requirements.txt`** (see Finding 2) — a decision for the phase gate, not for this plan.

## Next Phase Readiness

**Wave 2 is unblocked from this plan's side.** Plan 03 is the other half of Wave 1 and was still executing at close.

- `python3 /home/ido/pi-mirror/tools/check_tree_integrity.py --strict` → exit 0, `OK: 40 closure members, 30 protected files, 1 known-dangling exemptions held, 0 violations`.
- **`--rebaseline` was not run and must never be run again.**
- **Plan 08 must:** (a) purge `__pycache__` / `*.pyc` / `.pytest_cache` in Task 1 before the manifest diff (ledger §I); (b) **re-measure** `du -sb --exclude=.git .` rather than carrying forward this plan's figure (ledger §H); (c) confirm F1 passes for `autopilot/{tests,examples,docs}` with no further work; (d) transcribe the `HYG-08 | PROVEN` line from ledger §L; (e) decide the `requirements.txt` question from Finding 2.
- `pilot/sounds/` (2,326,388 B) and `/home/ido/pi-mirror/tests/` (22 modules) are intact and remain off-limits to this phase.

## Self-Check: PASSED

- **Removed paths confirmed absent:** all 28 asserted non-existent by the removal script immediately after deletion; `test ! -e` re-confirmed for `code_2023.deb`, `docs`, `tests`, `examples`, `blip.wav` in the Task 1 verification chain.
- **Kept paths confirmed present:** all 18 keep-list entries asserted present both before and after the removal script; `autopilot/LICENSE` re-confirmed at summary time; `autopilot/` root listing contains exactly the keep-list plus the package and `__pycache__`.
- **Created file confirmed:** `.planning/phases/30-pi-repo-cleanup/ledger/30-02-ledger.md` exists.
- **Commits confirmed:** `d222d44` and `90554d5` present in git log.
- **Gates re-run at summary time:** `check_tree_integrity.py --strict` exit 0; `compileall -q autopilot/autopilot tools tests` exit 0; `pilot/sounds` still 2,326,388 B.

---
*Phase: 30-pi-repo-cleanup*
*Completed: 2026-08-10*
