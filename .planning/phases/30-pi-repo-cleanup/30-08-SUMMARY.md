---
phase: 30-pi-repo-cleanup
plan: 08
subsystem: pi-tree
tags: [exit-gate, manifest-diff, evidence-log, publication, cache-purge, hyg-13, wave-5]

# Dependency graph
requires:
  - "30-01 — tools/check_tree_integrity.py --final, tree_protect_list.json baseline, 30-PYTEST-BASELINE.json, /home/ido/.hyg01-probe.txt"
  - "30-02 — deferred cache purge, HYG-08 ledger, scan_skip retirement"
  - "30-03 — HYG-07 ledger"
  - "30-04 — HYG-03/HYG-04 ledger, the corrected OG_TRIGGER/IR1 inventory"
  - "30-05 — HYG-05/HYG-06 ledger, the drift characterisation"
  - "30-06 — HYG-11/HYG-12/HYG-14 ledger, both user-deferred holds"
  - "30-07 — HYG-10 ledger, the pilot/protocols/.gitkeep handoff, the /usr/bin/grep rule"
provides:
  - "check_tree_integrity.py --final exits 0 with F1-F6 each at 0 violations, none weakened"
  - "HYG-13 proven: zero drift over all 30 protected paths on md5 AND sha256"
  - "A cache-clean tree: 0 __pycache__, 0 *.pyc, no .pytest_cache outside .git"
  - "30-HARDWARE-VALIDATION.md — consolidated: 14-row verdict table, merged §4 ledger, §6 with 21 findings, §7 exit-gate table, §8 deferred list"
  - "30-PUBLISH.md — the user's 5-step publication procedure + Known consequences + Known defects"
  - "pi-mirror/README.md — the new repo's front door"
  - "requirements.txt declares the two adafruit runtime deps of hardware/i2c.py"
  - "pilot/protocols/.gitkeep — the fifth and last Scopes.DIRECTORY pref covered"
affects: [30-09]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Purge caches AFTER the gate that shells out to compileall, never before — F4 regenerates what an earlier purge removed"
    - "Invoke /usr/bin/find and /usr/bin/grep explicitly; the shell's are rewritten to a proxy that refuses compound predicates and mutates path prefixes"
    - "Take every load-bearing count from an unfiltered python3 reader, never from grep"
    - "A merged evidence log records the criteria a removal FAILS (OVERRIDE) as prominently as the ones it passes"
    - "Re-measure a figure at the gate rather than transcribing a sibling wave's number"

key-files:
  created:
    - .planning/phases/30-pi-repo-cleanup/30-PUBLISH.md
    - .planning/phases/30-pi-repo-cleanup/30-08-SUMMARY.md
    - /home/ido/pi-mirror/pilot/protocols/.gitkeep
  modified:
    - .planning/phases/30-pi-repo-cleanup/30-HARDWARE-VALIDATION.md
    - /home/ido/pi-mirror/README.md
    - /home/ido/pi-mirror/requirements.txt
    - /home/ido/pi-mirror/.gitignore
  deleted:
    - /home/ido/pi-mirror/**/__pycache__/ (18 directories, 234 cache entries)
    - /home/ido/pi-mirror/.pytest_cache/

key-decisions:
  - "Ran the cache purge twice and named the second authoritative, because --final's F4 shells out to compileall and would otherwise regenerate tasks/__pycache__ after an 'authoritative' purge"
  - "Corrected two propagated bookkeeping errors rather than transcribing them: plan 02's '28 paths' (27 paths + a note row) and plan 05's '150,687 B' (per-path tables sum to 141,145 B)"
  - "Recorded the 0c orphaned-toolkit finding in 30-PUBLISH.md under Known consequences with the failure mode stated, and made zero DB writes"
  - "Documented the README's real launcher (run_pilot.sh, direct path) rather than transcribing the plan's `-m autopilot.core.pilot` form, which does not resolve from the repo root"
  - "Left the OG_TRIGGER inventory correction OPEN against 30-CONTEXT.md rather than patching it, so the context file stays the record of what was decided, not of what was later measured"

patterns-established:
  - "The exit gate re-measures every number it publishes; a figure carried forward from a concurrent wave is treated as stale by default"

requirements-completed: [HYG-13, HYG-07, HYG-08, HYG-11]

# Metrics
duration: 17min
completed: 2026-08-10
---

# Phase 30 Plan 08: Exit Gate and Publication Handover Summary

**`check_tree_integrity.py --final` exits 0 with all six completion checks at zero violations and
none weakened, the 30-path survival manifest shows zero drift on md5 *and* sha256, and the tree
that started at 202,630,324 bytes now sits at a 1,102,638-byte HYG-08 budget against an 8 MiB
limit — with every removal in the phase merged into one path-sorted ledger and the four things the
agent may not do written out as commands for the user.**

## Performance

- **Duration:** 17 min (17:36:10Z → 17:53:34Z)
- **Tasks:** 2 (plus steps 0, 0b–0g)
- **Commits:** 2
- **Gate runs:** `--final` 3× (all exit 0), `--strict` 2× (all exit 0), cache purge 3×

## Accomplishments

- **`--final` exits 0, and each check was verified individually rather than trusting the summary
  line.** `f1_bulk`, `f2_prefs`, `f3_toggles`, `f4_tasks_compile`, `f5_cameras`, `f6_json_parses`
  → **0 violations each**. F3 still asserts the three **call forms**
  (`set_cdc_manual(0x3f)`, `self.triggers['IR1']`, `pulse_and_notify(…OG_TRIGGER…)`) and both
  **inverted** holds; F1 still asserts `autopilot/{tests,examples,docs}` and `terminal/` absent.
  **No assertion was weakened and no live code was deleted to satisfy one.**
- **HYG-13 proven with zero drift.** All 30 protected paths re-hashed and diffed against the §1
  pre-sweep manifest: **0 drift on md5, 0 on sha256, 0 missing.** The md5 table and
  `tree_protect_list.json`'s `baseline_sha256` were confirmed to cover the *same* 30-path set
  before the comparison, so the diff is over the intended corpus. All three Phase 26
  `reserved_absent` names still absent and never reported as strays.
- **The tree is cache-clean and stays that way.** 0 `__pycache__` directories, 0 `*.pyc`, no
  `.pytest_cache` outside `.git` — measured by unfiltered `os.walk`, not by `find`.
- **HYG-08 re-measured at the gate, not carried forward.** `du -sb --exclude=.git` **3,429,026**;
  `pilot/sounds` **2,326,388** (byte-for-byte unchanged all phase); **budget 1,102,638 B — 13.1%
  of the 8,388,608 B limit.** Against the pre-sweep 202,630,324 that is **−98.31%**.
- **Every suite green or at baseline.** `compileall` exit 0; backend **435 passed / 1 skipped**;
  Pi suite **179 failed / 203 passed / 382 collected — 0 new failing node ids** against the
  Wave 0 baseline, and 0 newly passing; the guard's own **22 unit tests** pass.
- **`30-HARDWARE-VALIDATION.md` consolidated**: 14-row verdict table (**12 PROVEN**, HYG-01 and
  HYG-02 deliberately UNPROVEN), §1b post-sweep measurements with a per-plan size reconciliation,
  §4 merging all six ledger fragments into one path-sorted removal table carrying each row's four
  criterion verdicts and owning plan, §6 with 21 findings, §7 a 24-row exit-gate table, §8 a
  19-row deferred list.
- **`30-PUBLISH.md` written**: revoke → fresh `git init` → HYG-01 history proof → `.28` branch
  cut → the plan-09 blocker, every command copy-pasteable, plus a verified-vs-remaining table,
  `Known consequences` and `Known defects, deliberately not fixed`.
- **Steps 0b–0g all landed.** The two adafruit deps declared (root file only, deliberately
  unpinned); the orphaned toolkits documented with **zero DB writes**;
  `pilot/protocols/.gitkeep` added so all five `Scopes.DIRECTORY` prefs are covered;
  `Message`/`hardware_state` untouched with their two defects recorded; `/usr/bin/grep` and
  `/usr/bin/find` used in every gate; the mid-flight guard correction recorded as §6.12.

## The three things that mattered most

### 1. Purge ordering was the difference between a true and a false completion criterion

`--final`'s F4 (HYG-06) shells out to `python3 -m compileall -q autopilot/autopilot/tasks`, which
**creates** `autopilot/autopilot/tasks/__pycache__`. A purge that ran before `--final` — the
obvious reading of "purge first" — leaves a cache directory behind and makes the plan's own
`<done>` false at the moment it finishes. Verified empirically: after the plan-level verification
re-ran `--final`, `/usr/bin/find` reported exactly two regenerated directories,
`tools/tree_integrity/__pycache__` and `autopilot/autopilot/tasks/__pycache__`.

The executed chain was therefore
`compileall → backend pytest → Pi delta → tree-absence tests → --final → purge → assert clean → du`,
and the purge was re-run after every subsequent `--final`. The cost is that F1's *internal* size
measurement counts bytecode — harmless at 1.05 MiB against 8 MiB.

### 2. Two propagated numbers were wrong and were corrected rather than transcribed

The exit gate's job is to publish figures, so it re-derived them:

- **Plan 02's "28 paths".** Its ledger §B has 28 **rows**, but row 28 is the `scan_skip`
  retirement *note*, not a path. The 27 real paths sum to exactly the stated **97,691,320 B**, so
  the byte figure was right and only the count was off by one.
- **Plan 05's "10 files (150,687 bytes)".** The md5-backed per-path tables in its own ledger sum
  to **141,145 B** (60,505 + 80,640). The 150,687 figure does not reconcile against them and is
  superseded by the per-path total.

Both are recorded in §1b as bookkeeping corrections with the arithmetic shown, so the next reader
does not have to re-derive them a third time.

### 3. The exit gate is where a stale assertion does the most damage — and this phase had four

§6.12 records the pattern in one place. Four separate assertions in this phase had "undo a user
decision" as their cheapest path to green: the bare-token `OG_TRIGGER` form, the two-file
`132.77.` allowlist, plan 06's stale `station.py` Task 1 gate, and the built guard's own
pre-deferral F3 (fixed in the main session at the end of Wave 4). All four arrived at or near a
gate, and three of them would have fired *after* every destructive plan had landed and *before*
any rig proof.

Nothing in this plan hit a red gate — but the guard's `f3_toggles` was read in full before
`--final` was trusted, precisely to confirm the F6.12 fix was in the artifact and not only in the
plan text.

## Task Commits

Tree changes in `/home/ido/pi-mirror` (requirements.txt, .gitignore, README.md,
`pilot/protocols/.gitkeep`, the cache purge) live in a tree that is **not agent-managed version
control** — the standing Pi rule forbids any git command there. The commits below carry the
evidence in `mics-backend`.

1. **Task 1: Run the full gate and prove the survival manifest** — `c71a544` (docs)
2. **Task 2: Write the publication handover (HYG-01 repo-hygiene half)** — `727cf7d` (docs)

## Files Created/Modified

**In `/home/ido/pi-mirror` (not version-controlled by the agent):**

| Path | Change |
|---|---|
| `requirements.txt` | 39 → 46 lines: the two adafruit deps + a 5-line comment stating why they are unpinned |
| `.gitignore` | +2 lines: `pilot/protocols/*` / `!pilot/protocols/.gitkeep` |
| `pilot/protocols/.gitkeep` | created (0 B) — the fifth and last `Scopes.DIRECTORY` pref covered |
| `README.md` | 116 B → 5,249 B — the new repo's front door |
| `**/__pycache__/`, `*.pyc`, `.pytest_cache/` | purged (18 directories, 234 entries at first count) |

*Untouched by design:* `autopilot/requirements.txt` (upstream's), `pilot/prefs.json`,
`networking/message.py`, `hardware/gpio.py`, `utils/logging_utils.py`, every protect-listed file,
`tools/tree_protect_list.json`.

**In `mics-backend` (committed):** `30-HARDWARE-VALIDATION.md` (rewritten, 81 → 628 net lines
added), `30-PUBLISH.md` (new), this summary.

**In the database:** nothing. The 0c investigation was read-only.

## Decisions Made

- **Ran the purge twice and named the second authoritative.** See above.
- **Documented the README's real launcher.** The plan says to document
  `python3 -m autopilot.core.pilot -f pilot/prefs.json`. That form does not resolve from the repo
  root — the package sits at `autopilot/autopilot/`, and `run_pilot.sh` invokes
  `python3 autopilot/autopilot/core/pilot.py -f $REPODIR/pilot/prefs.json` after sourcing the venv.
  The README documents `./run_pilot.sh` as the entry point and gives the module form with the cwd
  it requires. A README whose start command does not work is worse than no README.
- **Left the `OG_TRIGGER` inventory correction OPEN against 30-CONTEXT.md.** 30-CONTEXT.md already
  carries the general CORRECTION block — the one that forced F3 to assert call forms — but not the
  full site table. The table lives in §6.9 instead, so the context file stays the record of what
  was *decided* rather than of what was later *measured*.
- **Recorded the orphaned toolkits with the failure mode, not just the fact.** The lookup is
  pure-DB so nothing errors in the backend; the class fails to load at dispatch on the Pi; and the
  Pi has no `TASK_ERROR` emitter, so a failed START leaves the run `running` for ever. Stating
  "8 rows are stale" without that chain would understate it to the point of being useless.
- **Re-verified every 0c DB fact live rather than transcribing the plan's numbers.** Worth it: the
  plan says `available_locked_states` maps the filename via a `file_name` column; the column is
  actually **`task_filename`**. The row exists (id 24, pilot 1, `class_name='elastic_test'`) and
  the finding is unchanged, but a query against the plan's column name returns empty — and **an
  empty result set and a wrong-column query are indistinguishable at a glance**, which is exactly
  how plan 04 nearly produced a false "clean" verdict on the same table.

## Deviations from Plan

### Auto-fixed

**1. [Rule 3 — blocking] `find` is intercepted by the same proxy as `grep`, and refused the purge.**
- **Found during:** step 0, the preliminary cache purge.
- **Issue:** the plan's literal `find … -not -path … -prune -exec rm -rf {} +` returned
  `rtk: rtk find does not support compound predicates or actions (e.g. -not, -exec). Use find directly.`
  and deleted **nothing**, while the surrounding `rm -rf .pytest_cache` succeeded — so the chain
  reported `exit=0` on a purge that had not happened. A silent no-op inside a passing gate.
- **Fix:** invoked **`/usr/bin/find`** explicitly, in the same command shape, and verified the
  result with an unfiltered `os.walk` rather than with the tool that had just lied. This is the
  same class of failure as step 0f's `grep` rule and is now recorded alongside it in §6.20 as the
  proxy's **fourth** corrupted measurement in this phase.
- **Not a permission refusal.** `rm -rf` itself was never blocked in this plan, so the
  stop-and-report rule did not apply.

### Findings (recorded, not acted on)

**2. Plan 02's path count and plan 05's byte total do not reconcile.** Corrected in §1b with the
arithmetic shown. Neither affects a verdict: plan 02's byte figure was already right, and plan
05's per-path tables are md5-backed.

**3. `available_locked_states`'s column is `task_filename`, not `file_name`.** The plan's step 0c
quotes the wrong name. Finding unchanged once queried correctly; recorded because the wrong query
returns an empty set that reads exactly like "clean".

**4. The README rewrite is the only thing that touched the tree after the authoritative purge**,
adding 5,133 B and moving the budget 1,097,505 → 1,102,638 B. Both figures are recorded in §1b and
§7 with the reason, rather than silently publishing whichever was measured last.

**5. `CLAUDE.md` still quotes the backend suite as "352 pass".** It is **435 passed / 1 skipped**
and has been since at least plan 04, which flagged the same thing. Not this plan's file.

**Total deviations:** 1 auto-fix (the intercepted `find`), 5 findings recorded.
**0 assertions weakened, 0 protect-listed files touched, `tree_protect_list.json` unedited,
`--rebaseline` not run, 0 live code deleted to satisfy a gate, 0 DB writes.**

## Issues Encountered

- **A passing gate that had done nothing.** The intercepted `find` is the sharpest instance this
  phase has produced of its own recurring lesson: the shell chain reported success because `rm -rf`
  (the last command) succeeded, while the two `find` invocations before it had been rejected and
  removed nothing. The only reason it surfaced is that the purge was verified with an independent
  reader instead of by exit code.
- **`docker compose exec db psql -U postgres` fails** — the role is `mics_user` and the database
  `mics_db` (`docker-compose.yml:9-11`). Worth knowing for any future read-only DB check.
- **`from tree_integrity.scan import load_config` does not exist** — the function is `load_cfg`.
  Only relevant if you import the guard's modules directly to get a per-check breakdown, which is
  the only way to see F1–F6 individually; the CLI prints one aggregate line.

## User Setup Required

**Everything from here is yours. `30-PUBLISH.md` is the procedure.** In order:

1. **Revoke the Gmail app password at Google — before publication, not after.** The working tree
   is clean of both literals (0 hits, verified), but `.git` is not and cannot be made so.
2. **Publish as a fresh `git init`** over the pruned tree. Never a clone, never `filter-repo` /
   `filter-branch`.
3. **Run the two HYG-01 proofs** (`grep -c -F -f` over the full history → 0; `git log --oneline |
   wc -l` → 1) and paste the numbers into `30-HARDWARE-VALIDATION.md` §3.
4. **Cut the `phase30-cleaned` branch** on the old repo for `.28`.
5. **Clear `ExtlinkDemo` off pilot 1** (module 62, lib 177, pilot config 21, task def 434) before
   the plan-09 rig session.
6. **Resolve the two adafruit pins** on the first fresh image and write them back to
   `requirements.txt`.

## Next Phase Readiness

**Plan 09 is unblocked from this plan's side**, and inherits:

- **The rig proof's watch-list — the phase's only three behavioural changes**, in §5 of the
  validation log and in `30-PUBLISH.md`: the `l_start` START dispatch collapse, `Solenoid.dur_from_vol`
  falling back to the default LUT, and the licker after the `i2c.py` surgery. `py_compile` cannot
  prove the third; only a real lick can.
- **HYG-01 and HYG-02 both still UNPROVEN**, deliberately. Neither may be flipped from this side.
- **The Pi picks up `hardware_libs` version 144** on its next `LOAD_HARDWARE_LIBS`, which the user
  triggers by starting a run.
- `--rebaseline` was **not** run and must never be run again.

**Standing-rule compliance:** no git command was run in `/home/ido/pi-mirror` at any point in this
plan — every invocation used `git -C /home/ido/mics-backend …`, which is cwd-independent, and no
command combined a `cd` into `pi-mirror` with a git call. Nothing was deployed to the Pi, no
`rsync` ran, the pilot was not started or stopped, no Python was executed on the Pi, and no row in
any database was written.

## Self-Check: PASSED

- **Created files exist:** `30-PUBLISH.md`, `30-08-SUMMARY.md`,
  `/home/ido/pi-mirror/pilot/protocols/.gitkeep`.
- **Modified files exist and carry the change:** `30-HARDWARE-VALIDATION.md` (18 `PROVEN`
  occurrences, `MLX90640` present, `known_dangling` present), `pi-mirror/README.md`
  (`CHANGE_ME` present), `requirements.txt` (46 lines, both adafruit entries),
  `.gitignore` (`pilot/protocols` pair).
- **Both commits present in git:** `c71a544`, `727cf7d`.
- **Gates re-run at summary time:** `--final` exit 0; `--strict` exit 0; manifest diff 0 drift;
  cache-clean 0/0/absent after the final purge; HYG-08 budget 1,102,638 B; `prefs.json` still
  carries the live `IR1` / `OG_TRIGGER` pin declarations.

---
*Phase: 30-pi-repo-cleanup*
*Completed: 2026-08-10*
