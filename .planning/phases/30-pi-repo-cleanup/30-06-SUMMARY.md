---
phase: 30-pi-repo-cleanup
plan: 06
subsystem: pi-tree
tags: [hygiene, dead-code-removal, comment-sweep, hdf5, ast-surgery, deferred-restorations, protect-list]

# Dependency graph
requires:
  - "30-01 — tools/check_tree_integrity.py (--strict gate), tree_protect_list.json, 30-PYTEST-BASELINE.json delta command"
  - "30-04 — the corrected held-toggle inventory"
  - "30-05 — the 'child' dispatch handoff; REGISTRIES.CHILDREN already removed"
provides:
  - "A Pi tree with 238 dead commented-out lines gone across 14 files, and no half-disabled HDF5 subsystem"
  - "pilot.py with no open_file/h5f/liors residue and an unconditional get_task() START dispatch"
  - "Both user-deferred blocks (HOLD 0 clock, HOLD 1 watchdog) preserved byte-identically through the sweep"
  - "ledger/30-06-ledger.md — swept-vs-exempted recorded separately, 175 kept candidates each with the live symbol that kept it, 5 findings"
affects: [30-07, 30-08, 30-09]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Validate every deletion range in every file BEFORE writing any file, so a miscount cannot leave a tree half-swept"
    - "Assert every line in a delete range is blank-or-# — a live-code line aborts the sweep"
    - "Prove a sweep with difflib opcode kinds: N deletes and zero inserts/replaces beats reading a diff"
    - "Make an ambiguous discrimination rule operational and write the operational form down, rather than adjudicating line by line"
    - "A stale gate in a removal phase is answered by inverting the gate, never by removing the thing it names"

key-files:
  created:
    - .planning/phases/30-pi-repo-cleanup/ledger/30-06-ledger.md
    - .planning/phases/30-pi-repo-cleanup/30-06-SUMMARY.md
  modified:
    - /home/ido/pi-mirror/autopilot/autopilot/core/pilot.py
    - /home/ido/pi-mirror/autopilot/autopilot/networking/station.py
    - /home/ido/pi-mirror/autopilot/autopilot/networking/message.py
    - /home/ido/pi-mirror/autopilot/autopilot/networking/node.py
    - /home/ido/pi-mirror/autopilot/autopilot/hardware/gpio.py
    - /home/ido/pi-mirror/autopilot/autopilot/tasks/task.py
    - /home/ido/pi-mirror/autopilot/autopilot/tasks/mics_task.py
    - /home/ido/pi-mirror/autopilot/autopilot/external/__init__.py
    - /home/ido/pi-mirror/autopilot/autopilot/transform/image.py
    - /home/ido/pi-mirror/autopilot/autopilot/transform/selection.py
    - /home/ido/pi-mirror/autopilot/autopilot/setup/forms.py
    - /home/ido/pi-mirror/autopilot/autopilot/stim/sound/base.py
    - /home/ido/pi-mirror/autopilot/autopilot/stim/managers.py
    - /home/ido/pi-mirror/autopilot/autopilot/core/loggers.py
  deleted: []

key-decisions:
  - "Reported the plan's own Task 1 verify gate as STALE rather than obeying it — two of its predicates demand the user-deferred station.py restoration; ran the inverted form instead"
  - "Made the discrimination rule operational (superseded block OR dead symbol = remove; single disabled statement on a live symbol = keep) and recorded the operational form, because the plan's rule and its exclusion contradict each other"
  - "Kept every hardware_state comment in gpio.py and logging_utils.py: the attribute is read live in two files and written in one, so the commented code is the only record of how it was maintained"
  - "Kept core/pilot.py's 24 remaining commented candidates — HYG-11's named scope for that file is :49 only, and it is the phase's most load-bearing file"
  - "Kept import tables in pilot.py: :34's warnings.simplefilter still references it, so removing it raises NameError at import time"

patterns-established:
  - "Snapshot every file before a sweep and prove the result with difflib opcode kinds, not by inspection"
  - "Record swept-count and exempted-count in separate table rows so a carve-out is never conflated with the sweep"

requirements-completed: [HYG-11, HYG-12, HYG-14]

# Metrics
duration: 18min
completed: 2026-08-10
---

# Phase 30 Plan 06: Dead-Comment Sweep and the HDF5 Set-Removal Summary

**238 dead commented-out lines removed across 14 Pi files and the half-disabled local-HDF5
subsystem taken out whole — while the two blocks the user deferred on 2026-08-10 survived
byte-identically inside the very files being swept, including one that had to be carved out of
`station.py` after it lost 58 of its own commented lines.**

## Performance

- **Duration:** 18 min (17:00:54Z → 17:19:25Z)
- **Tasks:** 2
- **Files modified:** 14 in `pi-mirror`; 2 created in `mics-backend`
- **Lines removed:** 322 total (238 comment lines + 57 lines of live `open_file()` + blanks)
- **Guard runs:** 3, all exit 0 with 0 violations

## Accomplishments

- **HYG-14's set-removal landed across all four sites**, including the one the original scope
  missed: `open_file()` (57 lines), the `self.h5f` cleanup, the ~23 commented lines, **and the
  `run_task` docstring line that still advertised the subsystem**, with the following sentence
  fixed up so the docstring still reads correctly. `open_file`, `h5f` and `liors` now match
  **zero** lines in `pilot.py`. No caller existed anywhere — verified by an unfiltered tree-wide
  reader that found 11 `open_file` hits, of which 2 were the guard's own assertion literals and
  **4 were an unrelated local variable in `station.py`**.
- **Both user-deferred blocks survived the sweep verbatim.** HOLD 0 (`pilot.py`'s
  `# ---- CLOCK SETUP ----` / `# self.enable_ntp_and_wait()` / freeze-wall-clock comment /
  `# self.disable_ntp()`) sits at `:1071-1082`, still commented, never uncommented. HOLD 1
  (`station.py`'s five commented `logger` lines **plus the bare `print("")`**) sits at
  `:1270-1283`, byte-identical, in a file that lost 58 other commented lines around it.
- **HYG-11: 238 lines removed across 14 files** against the audit's 244 — a 2.5% shortfall, and
  every line of it itemised as a deliberate keep with the live symbol that kept it. Two per-file
  counts land on the audit exactly: `task.py` **28** and `mics_task.py` **11** — the latter being
  the plan's own stated sanity check.
- **The plan-05 handoff is done and re-proven.** `l_start`'s `if 'child' in value.keys():` branch
  collapsed to the unconditional `autopilot.get_task(value['task_type'])`; the `else` body was
  byte-for-byte the unconditional form, so the surviving path is exact. The guard condition —
  **zero** `'child'`/`"child"` keys anywhere in `mics-backend/orchestrator` or `api` — was re-run
  here, not taken on trust. `pilot.py:189-193`'s unrelated `LINEAGE`/`self.child` mechanism was
  asserted present afterwards.
- **HYG-12 held exactly.** `Event_Dispatcher.py`'s sha256 is
  `1bfadc3313f3552f1d69057a91ce403ca8f2306c7fc874c0369fad9600adac68` — identical to the Wave 0
  baseline — and both `_dropped_no_clock` and `_dropped_on_send` are present. It was excluded by
  name from the sweep's target list *and* re-checked against `tree_protect_list.json` before any
  write, as were all 13 other targets. **Zero protect-listed files edited.**
- **Gates:** `compileall` over `autopilot/autopilot`, `tools`, `tests` exit 0; guard `--strict`
  exit 0 (`40 closure members, 30 protected files, 1 known-dangling exemptions held, 0 violations`)
  before Task 1, after Task 1 and after Task 2; Pi pytest **179 → 179, 0 new failing node ids**,
  with `test_trigger_assignments.py` still at exactly **51** and `test_execute_trigger_guard.py`
  still at exactly **11** — the "still 51 and 11, not 0" signal the plan asked for after the
  `task.py` trigger-dispatch removal.
- **The sweep is provably subtractive:** `difflib` across all 13 swept files reports **33 `delete`
  opcode groups, 0 `insert`, 0 `replace`**; `pilot.py`'s 9 Task-1 edits likewise show 0 unintended
  inserts.

## The three things that mattered most

### 1. The plan's own Task 1 gate was stale, and obeying it would have undone the deferral

The plan predicted two traps and asked to be told about a third. There was one:

```
grep -Eq '^\s*logger\.(warning|exception)\(' station.py     # demands the restoration
! grep -Eq '^\s*print\(""\)\s*$'            station.py     # demands deleting the deferred print("")
```

Measured against the real file: the first predicate matches **zero** lines, the second matches
**one** (`station.py:1344`). Chained with `&&`, the gate is red — and in a removal phase the
obvious way to turn it green is to uncomment the five `logger` lines and delete the `print("")`,
which is precisely the pair of edits the user deferred on 2026-08-10. **Reported, not obeyed.**
The gate was replaced with its inverted form — assert the five commented lines *and* the bare
`print("")` are present, and that `^\s*logger\.(warning|exception)\(` still matches nothing —
matching plan 01's already-inverted F3. Every other predicate in the block ran verbatim.

### 2. The plan's discrimination rule contradicts its own exclusion, so it had to be made operational

The rule says a commented block is removable only if it is a *superseded implementation*; the
exclusion says to keep "any commented line naming a symbol that still exists in the tree". Almost
every commented-out line names *some* live symbol, so applied literally the exclusion swallows the
rule and the sweep removes nothing. The operational form used, and recorded in the ledger:

> **REMOVE** a multi-line commented block that is a complete superseded implementation — a live
> replacement performs its job, or its symbols are dead tree-wide — **plus** a single commented
> line whose named symbol exists nowhere else in the tree.
> **KEEP and record** every single disabled statement naming a still-live symbol, all prose /
> `TODO` / `FIXME` / banners, and the two user-deferred blocks.

It validates against the audit independently: `mics_task.py` comes out at exactly **11**, and
`task.py` at exactly **28**.

### 3. `hardware_state` is read live in two files and written in one — its maintainer is commented out

The single largest kept group. `self.hardware_state` is read at `gpio.py:439`
(`self.set(self.hardware_state)`) and at `logging_utils.py:95`
(`level=int(self.hardware_state)` — every logged hardware event), but written live only at
`gpio.py:877`. The code that used to maintain it is the commented `state_changing_methods` block
at `logging_utils.py:59-77` and eight sites in `gpio.py`. Sweeping those away would have deleted
the only surviving description of how a live, read-every-event attribute was supposed to be
maintained. **Kept, and raised as a defect that deserves its own decision rather than a sweep.**

## Task Commits

All *tree* changes live in `/home/ido/pi-mirror`, which is not agent-managed version control.
The commits below carry the evidence in `mics-backend`.

1. **Task 1: HYG-14 set-removal + the `'child'` dispatch collapse** — `f7ab2a4` (chore)
2. **Task 2: sweep 237 dead commented-out lines across 13 files (HYG-11)** — `5883a3c` (chore)

## Files Created/Modified

**In `/home/ido/pi-mirror` (not version-controlled by the agent):**

| file | before | after | comment lines removed |
|---|---|---|---|
| `core/pilot.py` | 1284 | 1199 | 1 (HYG-11) + 24 (HYG-14 comments) + 57 live lines |
| `networking/station.py` | 1363 | 1300 | **58** |
| `networking/message.py` | 270 | 220 | **47** |
| `external/__init__.py` | 158 | 127 | **31** |
| `tasks/task.py` | 460 | 428 | **28** |
| `hardware/gpio.py` | 1717 | 1693 | **24** |
| `transform/image.py` | 338 | 325 | **12** |
| `tasks/mics_task.py` | 1602 | 1589 | **11** |
| `networking/node.py` | 644 | 637 | **7** |
| `transform/selection.py` | 94 | 86 | **6** |
| `setup/forms.py` | 478 | 474 | **4** |
| `stim/sound/base.py` | 635 | 631 | **4** |
| `stim/managers.py` | 616 | 613 | **3** |
| `core/loggers.py` | 184 | 182 | **2** |

The nine files below `task.py` in the plan's `files_modified` are the **after-the-fact
`files_modified`** — plan 08 reads §B.4 of the ledger when it diffs the manifest. The plan
anticipated "11 smaller files"; the scan surfaced **9** with removable superseded blocks.

*Untouched by design:* every protect-listed file (`Event_Dispatcher.py`, `log_value.py`,
`fda_vocabulary.py`, the five `external_hardware*.py`, `LICENSE`, all 21 modules under `tests/`),
`hardware/i2c.py` (off-limits under TRIGA-12), `tools/check_tree_integrity.py`,
`tools/tree_protect_list.json`.

**In `mics-backend` (committed):** `ledger/30-06-ledger.md`, this summary.

## Decisions Made

- **Reported the stale Task 1 gate instead of satisfying it.** See above. In a removal phase the
  cheapest way to make a gate green is to remove something, and the nearest removable things were
  the two deferred blocks.
- **Made the discrimination rule operational and wrote the operational form down.** Adjudicating
  328 candidates one at a time against a self-contradicting rule is not reproducible; a stated rule
  plus a per-line exception list is.
- **Kept `gpio.py:1017/1021`** (`_clean_value`, `set_PWM_dutycycle` → `set_servo_pulsewidth`).
  Formally a directly-superseded single, but the supersession is a hardware behaviour change on a
  rig this phase does not exercise, and `_clean_value` is still live at `:1035`.
- **Kept `core/pilot.py`'s 24 remaining commented candidates.** HYG-11's named scope for that file
  is `:49` only; the rest is the old terminal-DATA-return path in `run_task`, whose symbols
  (`self.node.send`, `self.logger.debug`, `self.stage_block`) are all live. Handed to plan 08.
- **Kept `import tables` and the PyTables warning filter in `pilot.py`.** The plan says to remove
  the import only if now-unused; `:34` still references `tables.NaturalNameWarning`, so removing
  it would raise `NameError` at module-import time and kill the pilot.

## Deviations from Plan

### Reported, not routed around

**1. [Stale gate — the exact trap the plan warned about] Task 1's automated verify demands the
user-deferred `station.py` restoration.**

- **Found during:** Task 1, before running the gate.
- **Issue:** `grep -Eq '^\s*logger\.(warning|exception)\('` matches 0 lines and
  `! grep -Eq '^\s*print\(""\)\s*$'` matches 1 (`:1344`), so the chained gate fails unless the
  five commented `logger` lines are uncommented and the bare `print("")` deleted — both deferred
  by the user on 2026-08-10, and both explicitly on this plan's exemption list.
- **Action:** **Reported and inverted, not obeyed.** Ran the assertion in the form plan 01's F3
  already uses: five commented lines present, `print("")` present, zero uncommented
  `logger.warning(`/`logger.exception(`. Every other predicate ran verbatim.
- **Committed in:** `f7ab2a4`

### Auto-fixed

**2. [Rule 1 — arithmetic error in my own sweep spec] `task.py:375-402` counted as 25 comment
lines; it is 24 (line 392 is blank).**

- **Found during:** Task 2, first sweep attempt.
- **Issue:** The per-range comment-line assertion fired mid-run, after `station.py` and
  `message.py` had already been written.
- **Fix:** Restored both files byte-identically from the pre-sweep snapshot (md5 verified),
  corrected the count, and **restructured the sweep into two passes — validate every range in
  every file, then write** — so a miscount can no longer leave the tree half-swept. Re-ran clean.
- **Committed in:** `5883a3c`

### Findings (recorded, not acted on)

**3. `import tables` and `warnings.simplefilter(..., tables.NaturalNameWarning)` are vestigial in
`pilot.py`** now that the HDF5 subsystem is gone, but load-bearing for each other. Ledger F-1.

**4. `trial_data` in `run_task` is now assigned and never read** — it existed only to gate the
HDF5 row write. Live code, so outside HYG-11. Ledger F-2.

**5. The `NOLOG` message flag is sent but no longer honoured.** `pilot.py` sends
`flags={'NOLOG':True}`; `station.py:315` logs unconditionally because the `log_this` gate is
commented out. Kept as K-3. Ledger F-3.

**6. `Message.__setitem__` does not invalidate the serialization cache.** `self.changed = True` is
commented at `message.py:111` while `serialize()` short-circuits on
`if not self.changed and self.serialized`, so mutating a Message after one serialization can send
stale bytes. Kept as K-5. Ledger F-4.

**7. `external/__init__.py:40` carried a `git pu` typo inside the removed block**, which is why
the strict parse-based scanner never saw that 22-line block — a reminder that a parse-based scan
alone is not sufficient. Ledger F-5.

**Total deviations:** 1 stale gate reported and inverted, 1 auto-fix, 5 findings recorded.
**0 assertions weakened, 0 protect-listed files touched, `tree_protect_list.json` unedited,
`--rebaseline` not run, neither deferred block deleted or uncommented.**

## Issues Encountered

- **The strict AST-based comment scanner is a lower bound, not an inventory.** It cannot see
  fragments that do not parse standalone — `# try:` without its `except`, `# if x:` without a
  body. `task.py:383-395` (13 lines) and `external/__init__.py:27-48` (22 lines) were both invisible
  to it and were only found by a second, looser regex pass reviewed by hand. Anyone re-running this
  sweep with the strict scanner alone will under-count by ~35 lines.
- **Every load-bearing absence claim came from an unfiltered Python reader**, never `grep` alone —
  the standing rule on this host. `grep` was used only to corroborate results the readers had
  already produced; the two agreed everywhere. This is what established that `DETECTED_MINPRINT`,
  `_check_enc`, `_check_dec`, `json_tricks`, `n_gets`, `JACKD_MODULE` and `send_plot` occur **only
  inside comments** tree-wide, and that `station.py`'s four `open_file` hits are an unrelated local
  variable rather than callers of `Pilot.open_file`.
- **`autopilot/autopilot/external/` contains only `__init__.py`**, which is what makes its 22-line
  `from autopilot.external import jack as autopilot_jack` block dead rather than merely disabled.
  Checked before deleting.

## Next Phase Readiness

**Plans 07 and 08 are unblocked.** Handoffs:

- **Plan 08** merges `ledger/30-06-ledger.md` into `30-HARDWARE-VALIDATION.md` (this plan
  deliberately did not edit that file — plan 07 runs in parallel), transcribes the
  `HYG-11 | PROVEN`, `HYG-14 | PROVEN` and `HYG-12 | PROVEN` verdict lines from §D, and records
  **both HYG-14 restorations under `Deferred by the user`, never under `Removed`.**
- **Plan 08** also inherits six candidates from §E: F-1 (`import tables`), F-2 (`trial_data`),
  F-3 (`NOLOG` unhonoured), F-4 (`Message.__setitem__` cache), K-1 (`hardware_state`), K-11
  (`core/pilot.py`'s 24 remaining commented candidates).
- **Plan 09**'s live rig session is the proof for this plan's one behavioural change: the START
  dispatch collapse in `l_start`. Everything else here is subtractive.
- `--rebaseline` was not run and must never be run again.
- **No git command was run in `/home/ido/pi-mirror` at any point.** Every git invocation used
  `git -C /home/ido/mics-backend …`. Nothing was deployed to the Pi, no `rsync` ran, the pilot was
  not started or stopped, and no Python was executed on the Pi.

## Self-Check: PASSED

- **HOLD 0** — all four lines present and commented at `pilot.py:1071-1082`; zero uncommented
  `self.enable_ntp_and_wait()` / `self.disable_ntp()`.
- **HOLD 1** — all five commented `logger` lines and the bare `print("")` present at
  `station.py:1270-1283`; zero uncommented `logger.warning(` / `logger.exception(`.
- **`open_file`, `h5f`, `liors`** — 0 hits in `pilot.py`; `liors` 0 hits over every `.py` in the tree.
- **`LINEAGE`** present, with both `self.child = True` and `self.child = False`.
- **`Event_Dispatcher.py`** sha256 matches the Wave 0 baseline exactly.
- **`compileall`** exit 0; **guard `--strict`** exit 0; **pytest delta** 179 → 179, 0 new.
- **Both task commits present in git**: `f7ab2a4`, `5883a3c`.
- **Both `mics-backend` artifacts exist**: `ledger/30-06-ledger.md`, `30-06-SUMMARY.md`.

---
*Phase: 30-pi-repo-cleanup*
*Completed: 2026-08-10*
