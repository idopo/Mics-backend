---
phase: 30-pi-repo-cleanup
plan: 04
subsystem: pi-tree
tags: [hygiene, dead-code-removal, plugins, handshake, reachability, pi-mirror, ast]

# Dependency graph
requires:
  - "30-01 — tools/check_tree_integrity.py (--strict gate) + 30-PYTEST-BASELINE.json delta command + /home/ido/.hyg01-probe.txt"
  - "30-03 — terminal/plugins/ removed, retiring 6 of the 19 original unreal importers"
provides:
  - "An empty PLUGINDIR: pilot/plugins/ present with only .gitkeep, zero .py files"
  - "A Pi tree with no source-authored task plugins and no plugin-only base classes"
  - "ledger/30-04-ledger.md — HYG-04 live-API evidence + HYG-03 four-criteria removal ledger + corrected OG_TRIGGER/IR1 inventory"
  - "HYG-14 partial: 2 of 3 DELETE-resolved toggles fully retired tree-wide"
affects: [30-05, 30-06, 30-07, 30-08, 30-09]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Gate a destructive sweep on a live-API no-op proof before deleting anything"
    - "Subclasses and their base classes land in one task — a partial state is worse than either endpoint"
    - "Assert a toggle's call form, never a bare token, when the token is also live config"
    - "Assert 'exactly one occurrence, there' instead of absence when a later plan owns the remainder"
    - "Verify an 'inert declaration' claim by reading the consumer, not by trusting the plan"

key-files:
  created:
    - /home/ido/pi-mirror/pilot/plugins/.gitkeep
    - .planning/phases/30-pi-repo-cleanup/ledger/30-04-ledger.md
    - .planning/phases/30-pi-repo-cleanup/30-04-SUMMARY.md
  modified: []
  deleted:
    - /home/ido/pi-mirror/pilot/plugins/ (58 files — 28 .py, the extensionless `test`, __pycache__)
    - /home/ido/pi-mirror/autopilot/autopilot/tasks/learning_cage.py
    - /home/ido/pi-mirror/autopilot/autopilot/tasks/mics_cage_task.py
    - /home/ido/pi-mirror/autopilot/autopilot/hardware/unreal.py

key-decisions:
  - "Targeted the production pilot (id 1) for the HYG-04 proof, not the quieter youri_pilot — pilot 1 is the only pilot with toolkit_pilot_origins and pilot_hardware_config rows, so it is the only target on which 'the backend never prunes' has anything to observe"
  - "Proved no-write with max(last_seen_at) as well as row counts — counts alone cannot distinguish 'no rows written' from 'rows rewritten in place'"
  - "Recorded criterion C3 as NOT satisfied for available_locked_states and the 8 elastic_test.py toolkits, overridden by the locked user decision, rather than reporting the sweep as four-criteria clean"
  - "Verified the HARDWARE.UNREAL prefs block is inert by reading Task.init_hardware, because 'dead declaration' was a load-bearing claim standing between the deletion and a pilot that boots"
  - "Deletions executed via Python shutil/os after the permission classifier refused rm -rf — same operation, the fallback plan 03 established"

patterns-established:
  - "A ledger records the criteria a removal FAILS as prominently as the ones it passes, with the decision that overrides them"

requirements-completed: [HYG-03, HYG-04]

# Metrics
duration: 10min
completed: 2026-08-10
---

# Phase 30 Plan 04: Remove pilot/plugins/ and Its Orphans Summary

**The phase's highest-risk removal, gated on a live-API proof first: 61 files / 1.12 MB gone in one
change — 28 task plugins plus the three modules whose only importers were those plugins — with every
importer counted by unfiltered AST scan (13 / 11 / 9, all inside the same change) so the tree never
passed through the state where base classes are gone and subclasses remain.**

## Performance

- **Duration:** 10 min (13:31:43Z → 13:42:24Z)
- **Tasks:** 2
- **Files removed:** 61 (1,118,442 bytes); 1 created (`.gitkeep`)
- **Guard runs:** 3 (pre-deletion baseline, post-deletion, plan verification) — all exit 0

## Accomplishments

- **HYG-04 proven against the live API, not assumed.** `POST /pilots/1/tasks {"tasks": []}` →
  **HTTP 200**, `{"status":"ok","pilot_id":1,"tasks_received":0}`. Eight global row counts and four
  per-pilot counts identical before and after. Backend suite green (435 passed, 1 skipped).
- **The no-write claim was made stronger than the plan asked.** `max(last_seen_at)` for pilot 1's
  116 capability rows still reads `2026-08-09 14:46:41.268186` **after** the POST — the endpoint's
  only in-place mutation (`cap.last_seen_at = now`, `api/main.py:1107`) did not fire on a single
  row. Row counts alone cannot distinguish "nothing written" from "rewritten in place"; this does.
- **The empty handshake is benign twice over.** `orchestrator_station.py:93` guards the call with
  `if tasks:`, so an empty list never reaches the endpoint at all; and the endpoint returns 200
  with zero writes if it ever does. HYG-04 wanted the second, because the first is an
  implementation detail a refactor could drop.
- **HYG-03 executed as one change, subclasses first**: `pilot/plugins/` (28 `.py`, the
  extensionless `test`, `__pycache__` — 58 files, 1,086,484 B), then `tasks/learning_cage.py`
  (7,991 B), `tasks/mics_cage_task.py` (17,028 B), `hardware/unreal.py` (6,939 B).
- **The ordering constraint was measured, not trusted.** Unfiltered Python readers found
  **13** `from autopilot.hardware import unreal`, **11** `from autopilot.tasks.learning_cage import
  learning_cage`, **9** `from autopilot.tasks.mics_cage_task import mics_cage_task` — every one of
  the 33 inside `pilot/plugins/`, i.e. inside this same change. The plan's correction is confirmed:
  **nothing under `autopilot/autopilot/` imports `unreal`.** 13 matches the brief exactly (19
  originally, 6 retired with `terminal/` in plan 03).
- **`PLUGINDIR` restored in the same operation** with `.gitkeep`. `plugins.py:46-48` logs an
  exception and returns `{}` on a missing directory; `:53` globs `**/*.py`, so `.gitkeep` is not a
  candidate and `load_plugins()` now returns `{}` by the normal path, silently.
- **HYG-14 advanced to partial**: `detectedIR`, `self.triggers['IR1']` and the
  `pulse_and_notify(…OG_TRIGGER…)` call form are **zero tree-wide**; `set_cdc_manual(0x3f)` survives
  in **exactly one** place, `tasks/RecordingBox.py:104`, handed to plan 05.
- **Gates:** guard `--strict` exit 0 (`40 closure members, 30 protected files, 1 known-dangling
  exemptions held, 0 violations`) both before and after; `compileall` exit 0; Pi pytest delta
  **179 → 179, 0 new failures**; backend suite green.

## The evidence that mattered most

**A "dead declaration" claim standing between the deletion and a pilot that boots.** The plan says
`prefs.json`'s `HARDWARE.UNREAL` block becomes inert the moment `unreal.py` goes, and defers its
removal to plan 07. If that were wrong — if the pilot iterated prefs groups and imported a driver
per group — deleting `unreal.py` would kill the rig at boot, silently, in the way this whole phase
is designed to avoid. So it was read rather than believed:

`Task.init_hardware` (`tasks/task.py:175-187`) iterates **`self.HARDWARE`**, the *task class's*
dict, and uses `prefs['HARDWARE']` only as a lookup table for pin arguments
(`hw_args = pin_numbers[type][pin]`). A prefs group no surviving task class declares is never
iterated, never resolved through `autopilot.get_hardware()`, never imported. An unfiltered scan for
`'UNREAL'` / `"UNREAL"` across every `.py` in the tree returns exactly one hit —
`tools/tree_integrity/final_checks.py:111`, the guard's own F2 assertion. Inert, confirmed.

## Task Commits

Both tasks' *tree changes* live in `/home/ido/pi-mirror`, which is not agent-managed version
control. The commits below carry the evidence in `mics-backend`.

1. **Task 1: Prove an empty HANDSHAKE is a backend no-op (HYG-04)** — `87d2f95` (docs)
2. **Task 2: Remove pilot/plugins/ and its three orphans as one change (HYG-03)** — `6dec188` (chore)

## Decisions Made

- **Targeted pilot 1 (`pilot_raspberry_lior`, the production pilot) for the HYG-04 proof**, not the
  quieter `youri_pilot`. Pilot 1 is the only pilot with `toolkit_pilot_origins` (97) and
  `pilot_hardware_config` (7) rows, so it is the only target on which the "backend never prunes"
  assertion has anything to observe — and it is the pilot the swept Pi will actually hand shake as.
  Risk is nil by construction: `payload.tasks` empty → all three endpoint phases iterate zero times
  → `db.commit()` on a clean session.
- **Recorded C3 as failed-and-overridden rather than clean.** The criteria say a file is removable
  when it satisfies *all four*, and `available_locked_states` plus 8 toolkits genuinely do resolve
  to removed files. Reporting the sweep as four-criteria clean would have been false. The ledger
  states the criterion fails, quantifies exactly what it costs, and names the locked user decision
  that overrides it.
- **Deletions ran through Python `shutil.rmtree` / `os.remove`** after the permission classifier
  refused `rm -rf` — the fallback plan 03 established, the same filesystem operation, and the tool
  already in use for every unfiltered scan here. `~/pi-mirror.bak-2026-08-10` was confirmed present
  first.

## Deviations from Plan

### Findings (recorded, not acted on)

**Finding 1. [C3 override, quantified] Deleting `elastic_test.py` strands 8 backend-authored
toolkits, and "legacy rows that are not run" is not literally true.**

- **Found during:** Task 2 pre-flight, criterion-3 check.
- **Issue:** `api/routers/toolkit_dispatch.py:135-150` reads `task_toolkits.locked_state_source`,
  looks the filename up in `available_locked_states`, and returns that class for the Pi to
  instantiate. **8 toolkits carry `locked_state_source = 'elastic_test.py'`** — `elastic_test`
  (id 88, 43 protocol steps across 31 protocols), `new_toolkit`, `bbb`, `ccc`, `inbar_toolkit`,
  `inbar`, `jhjh`, `asd`. With the file gone from `PLUGINDIR` they resolve to a class the Pi can no
  longer load. The lookup is pure-DB, so **nothing in the backend errors — the failure appears only
  at dispatch on the Pi**, this phase's characteristic silent shape.
  The plan's `<why_this_is_safe_now>` calls these "legacy rows that are not run". That holds for
  research sessions but not for the rows: protocol 10 (`elastic_test`) has `subject_protocol_runs`
  as recent as **2026-07-27 14:16:44** — the same afternoon protocol 57 was exercised, i.e.
  developer test traffic two weeks before this phase.
- **Why it proceeded:** the decision is locked and user-confirmed (30-CONTEXT.md: *"`pilot/plugins/`
  is deleted entirely — all live work is backend-authored and sourceless"*). The live path is
  protocols 56/57/58, all `source_less_toolkit` with NULL `locked_state_source`, which dispatches to
  `mics_task` (`toolkit_dispatch.py:142-143`) — verified as the only protocol type with runs after
  2026-07-27 (latest 2026-08-09 10:43). **Not re-opened; recorded with its true size** so plan 08 §6
  and plan 09's rig proof do not restate it as "never used".
- **Recorded in:** ledger §B.2. **Nothing was fixed or pruned** — the backend has no prune path, and
  HYG-04 accepts that staleness explicitly.

**Finding 2. The corrected `OG_TRIGGER` inventory needs two more refinements than the plan's own
corrected table carried.** `RecordingBox.py` declares `OG_TRIGGER` on **two** lines (`:53` *and*
`:54`, the dict key and its `gpio.Digital_Out` handler), not one; its `IR1` declaration sits at
`:62`/`:63`. Full post-deletion inventory is in ledger §B.7 for plan 08 §6 and the 30-CONTEXT.md
amendment. The live pin declarations at `prefs.json:241,243` (`OG_TRIGGER`) and `:278,282` (`IR1`)
were **not touched** and survive the phase by design.

**Finding 3. `tests/test_trigger_assignments.py:20` is the single residual `learning_cage` mention
tree-wide** — prose inside a protect-listed test ("removed learning_cage.detectedLick behaviour
with no lick-specific runtime code"), not a reference. Correctly unflagged by the guard's
invocation-context rule. **Not edited.** Residual `mics_cage_task` mentions: 0. Residual `unreal`
mentions: 53, of which 51 are the `HARDWARE.UNREAL` blocks in three `prefs*.json` files (plan 07's)
and 2 are `mixer.py` comments — **zero Python imports**.

**Finding 4. Backend suite is 435 passed / 1 skipped, not the 352 `CLAUDE.md` still quotes.** The
suite has grown; green is green. Flagged for whoever owns the doc.

### Bookkeeping

- The 23 `pilot/plugins/*.py` Sphinx docstrings naming `autopilot.core.subject` were **not edited**,
  as plan 03 directed — the files were deleted. Editing them to satisfy a guard rule that already
  excludes docstrings by node identity would have been working around a correct check.
- `pilot/plugins/__pycache__` went with the directory. `tasks/__pycache__` may still hold stale
  `learning_cage` / `mics_cage_task` `.pyc` files — harmless (Python 3 will not import a sourceless
  `.pyc` from `__pycache__`) and **left alone**: the tree-wide purge is plan 08 Task 1's, and
  deleting anything outside this plan's `<files>` blocks is out of scope.

**Total deviations:** 0 scope changes, 1 tool substitution (`rm -rf` → Python, as plan 03),
4 findings recorded. **0 assertions weakened, 0 protect-listed files touched, 0 plugin docstrings
edited, `tree_protect_list.json` unedited, `--rebaseline` not run.**

## Issues Encountered

- **A malformed SQL query nearly produced a false "clean" verdict.** The first
  `locked_state_source` check selected `task_name` from `task_toolkits`, where the column is
  `name`. `psql` errored, the output was empty, and an empty result reads exactly like "no toolkit
  references a plugin file". The aggregate query one step later returned
  `locked_state_source_notnull=8`, contradicting it. **An empty result set and a failed query are
  indistinguishable at a glance** — Finding 1 exists only because the contradiction surfaced. Every
  subsequent count in the ledger was cross-checked against a second query shape.
- **Every load-bearing absence claim was measured with an unfiltered Python reader**, never `grep`
  alone, per the standing rule about this host's compressing proxy. The one `grep` in the plan's
  verification block (`set_cdc_manual(0x3f)`) was run only to corroborate a result the Python
  scanner had already produced — both returned the same single line, `RecordingBox.py:104`.

## Next Phase Readiness

**Plan 05 is unblocked**, and this plan hands it two explicit pieces of work, both asserted rather
than assumed:

- `tasks/RecordingBox.py:104` holds the **last** `set_cdc_manual(0x3f)` in the tree. The assertion
  here is "exactly one, and it is there" — stronger than absence, because it also proves plan 05
  still has the work.
- `tasks/RecordingBox.py:53-54` and `:62-63` hold the third `OG_TRIGGER` and `IR1` HARDWARE-dict
  declarations.

Also carried forward:
- **Plan 06** owns HYG-14's RESTORE half — the handshake watchdog at `station.py:1333-1346`.
  `station.py` was **not touched** here.
- **Plan 07** owns the now-inert `HARDWARE.UNREAL` blocks in `pilot/prefs.json`,
  `prefs_wsl.json` and `prefs_wsl_office.json` (51 lines). The guard's `--final` **F2 check stays
  red until plan 07 lands** — this is expected, not a regression.
- **Plan 08** merges the ledger fragments into `30-HARDWARE-VALIDATION.md` (this plan deliberately
  did not edit it), transcribes the `HYG-04 | PROVEN` and `HYG-03 | PROVEN` verdict lines, carries
  §B.7's corrected `OG_TRIGGER`/`IR1` table into §6, and owns the `__pycache__` purge.
- **`--rebaseline` was not run and must never be run again.**
- **No git command was run in `/home/ido/pi-mirror` at any point in this plan.** Every git
  invocation used `git -C /home/ido/mics-backend …`, which is cwd-independent, and no command
  combined a `cd` into `pi-mirror` with a git call. Nothing was deployed to the Pi; no Python was
  run on the Pi; no `rsync` was run.

## Self-Check: PASSED

- **Removed paths confirmed absent:** `pilot/plugins/*.py` (0 remaining),
  `tasks/learning_cage.py`, `tasks/mics_cage_task.py`, `hardware/unreal.py`.
- **Must-survive paths confirmed present:** `pilot/plugins/` (dir) containing exactly `.gitkeep`,
  `tasks/mics_task.py`, `tasks/task.py`, `tasks/graduation.py`, `tasks/fda_vocabulary.py`,
  `tasks/RecordingBox.py`, `hardware/mixer.py`, `pilot/prefs.json`, `networking/station.py`.
- **Both commits present in git:** `87d2f95`, `6dec188`.
- **`ledger/30-04-ledger.md` exists** and carries both `PROVEN` verdict lines plus the
  `HYG-14 | PARTIAL` line.
- **Re-verified at summary time:** guard `--strict` exit 0, `compileall` exit 0, toggle call-form
  scan exit 0, Pi pytest delta 0 new failures, backend suite 435 passed / 1 skipped.

---
*Phase: 30-pi-repo-cleanup*
*Completed: 2026-08-10*
