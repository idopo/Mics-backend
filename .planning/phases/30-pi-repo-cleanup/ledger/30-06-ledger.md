# Plan 30-06 Ledger — HYG-11 comment sweep, HYG-14 set-removal, HYG-12 boundary

**Executed:** 2026-08-10
**Tree:** `/home/ido/pi-mirror` (no version control; no git command was run there)
**Guard:** `python3 tools/check_tree_integrity.py --strict` — exit 0 before Task 1, after Task 1,
and after Task 2.

> Plan 08 merges this fragment into `30-HARDWARE-VALIDATION.md`. This plan deliberately did not
> edit that file (plan 07 runs in parallel).

---

## §0. Deferred by the user — NOT removed, NOT restored

Both HYG-14 restorations were deferred by the user on 2026-08-10. This plan restores nothing.
What survives is two blocks of commented-out code that had to be carved out of a ~244-line
sweep of superficially identical commented-out code in the same two files.

### D-1. `core/pilot.py` — the NTP / clock-freeze block (HOLD 0)

Final location `pilot.py:1071-1082` (was `:1137-1148`; shifted by the removals above it, text
unchanged). All four lines byte-identical to their pre-phase text:

| line | text |
|---|---|
| 1071 | `        # ---- CLOCK SETUP ----` |
| 1072 | `        # self.enable_ntp_and_wait()` |
| 1081 | `        # Freeze wall clock so it never jumps during the task` |
| 1082 | `        # self.disable_ntp()` |

Neither call site was uncommented (`^\s*self\.enable_ntp_and_wait\(\)` and
`^\s*self\.disable_ntp\(\)` both match **zero** lines). The methods remain live and defined at
`pilot.py:497` / `:513`. **Status: deferred by the user, not Removed, not Restored.**

### D-2. `networking/station.py` — `_handshake_watchdog` logging (HOLD 1)

Pre-sweep location `station.py:1330-1346`. All five commented `logger` lines plus the live bare
`print("")` are on the sweep exemption list and are asserted present after the sweep. Final
line numbers and the swept-vs-exempted table are recorded in §B.9 (Task 2).

```
1333|        # logger = getattr(self, "logger", None)
1340|                # if logger:
1341|                #     logger.warning("No PING from orchestrator for >21s, retrying HANDSHAKE")
1342|                self._handshake_callback()          <-- live, uncommented, unchanged
1343|            except Exception:
1344|                print("")                            <-- live, preserved
1345|                # if logger:
1346|                #     logger.exception("Handshake retry failed")
```

`^\s*logger\.(warning|exception)\(` matches **zero** lines in the file — nothing was uncommented.
**Status: deferred by the user, not Removed, not Restored.**

`station.py` is deliberately **not** byte-identical at the end of this plan. The watchdog block is
a carve-out inside a file that is otherwise swept normally — see §B.9.

---

## §A. Task 1 — HYG-14 set-removal and the plan-05 `'child'` handoff

`core/pilot.py`: **1284 → 1199 lines (−85)**, md5 `a9da42e7…` → see §A.5.
`difflib` against the pre-edit copy reports **exactly 9 opcode groups, 0 unintended inserts** —
the 9 edits below and nothing else. Nothing was reformatted or reordered.

### A.1 The HDF5 subsystem — removed as one set, four sites (−81 lines)

| # | site | pre-edit lines | removed |
|---|---|---|---|
| a | `def open_file(self)` — whole method + its trailing whitespace line | `999`–`1055` | 57 |
| b | the `self.h5f` cleanup in `l_stop`, incl. its `# TODO: Cohere here before closing file` and the trailing blank | `639`–`642` | 4 |
| c1 | `# Open local file for saving` / `# h5f, table, row = self.open_file()` + blank | `1174`–`1176` | 3 |
| c2 | the commented local-copy block (`# if trial_data:` … `#     table.flush()`) | `1212`–`1222` | 11 |
| c3 | `#row.append()` / `#table.flush()` in the `finally:` block | `1250`–`1251` | 2 |
| c4 | `#h5f.flush()` / `#h5f.close()` + the blank above | `1259`–`1261` | 3 |
| d | the `run_task` **docstring** line advertising `open_file` | `1125`–`1126` | 1 (2→1) |

Site (d) is the one the original scope missed. `1125-1126` read

```
        Opens a file with :meth:`~.autopilot.open_file` , then
        continually calls `task.stages.next` to process stages.
```

and became the single line `        Continually calls \`task.stages.next\` to process stages.` —
the sentence fix-up, so the docstring still reads correctly. Without it
`! grep -q 'open_file' pilot.py` is unsatisfiable and the pressure lands on the deferred blocks.

**No surviving caller.** Unfiltered tree-wide reader (not `grep` alone) over every
`.py/.sh/.json/.md/.txt/.cfg/.ini` in `/home/ido/pi-mirror`: 11 `open_file` hits pre-edit, of which
2 are the guard's own assertion literals in `tools/tree_integrity/final_checks.py:142-143`, 5 are
the sites removed above, and **4 are an unrelated local variable** in `station.py:998/1000/1259/1260`
(`with open(full_path, 'rb') as open_file:`). Zero calls to `Pilot.open_file`. Its only call site
was already commented out (site c1).

Post-edit: `open_file`, `h5f` and `liors` all match **zero** lines in `pilot.py`.

### A.2 `pilot.py:49` — the hardcoded other-person home directory (−1, HYG-11)

Removed: `#os.chdir('/home/liors/Apps/mice_interactive_home_cage/autopilot')`
Kept: `print(os.getcwd())` on the line above — live code, not commented, outside HYG-11.
Recorded as a candidate for a later cleanup, not this one.

### A.3 The `'child'` dispatch branch — plan 05's handoff (−3 net)

`l_start` lines `590`–`593` collapsed from

```python
            if 'child' in value.keys():
                task_class = autopilot.get('children', value['task_type'])
            else:
                task_class = autopilot.get_task(value['task_type'])
```

to the unconditional `            task_class = autopilot.get_task(value['task_type'])`. The `else`
body was byte-for-byte the unconditional form, so the non-child path is preserved exactly.
Located by the `if` statement, not by line number. Nothing else in `l_start` changed — the
surrounding `try:` / `except Exception`, `self.state = 'RUNNING'` and `self.running.set()` are
untouched (confirmed by the difflib opcodes).

**Guard condition re-verified before deleting**, with an unfiltered Python reader over
`mics-backend/orchestrator` and `mics-backend/api`, matching both `'child'` and `"child"`:

```
child-key hits in orchestrator+api: 0
```

No MICS START message carries a `child` key, which is what makes the branch unreachable. The
`REGISTRIES.CHILDREN` member it dispatched into was removed by plan 05 (`cb84444`).

**This is the only behavioural change to the START path in the phase, and the only change in this
plan with a proof scoped to it: plan 09's live rig session exercises START end-to-end.**

### A.4 Explicitly NOT touched in `pilot.py`

- **`pilot.py:189-193`** — `if prefs.get('LINEAGE') == "CHILD": self.child = True / else: self.child = False`.
  A different mechanism with a different spelling. Asserted present post-edit (`LINEAGE` in source,
  both `self.child = True` and `self.child = False` present).
- **`import tables` (`:24`) and `warnings.simplefilter('ignore', category=tables.NaturalNameWarning)` (`:34`).**
  The plan says to remove `import tables` only if now-unused. It is **not** unused — `:34` still
  references `tables.NaturalNameWarning`, so removing the import would raise `NameError` at
  module-import time and kill the pilot. Both kept. See Finding F-1.
- **`trial_data` (`:1169-1172` pre-edit)** — live code, now assigned but never read. See Finding F-2.
- **`# inside class Pilot` (`:1056` pre-edit)** — prose orientation comment, not commented-out
  code. Kept under the discrimination rule.

### A.5 Task 1 gate

```
HOLD 0 OK: clock block present, still commented, not swept
pilot.py HDF5 set fully removed, docstring included; child branch collapsed; LINEAGE intact
HOLD 1 OK: 5 commented logger lines + bare print("") present, nothing uncommented
OK: 40 closure members, 30 protected files, 1 known-dangling exemptions held, 0 violations
EXIT=0
```

`python3 -m py_compile` on both `pilot.py` and `station.py`: exit 0.

---

## §B. Task 2 — the HYG-11 sweep

### B.1 The discrimination rule actually applied

The plan's rule ("removable only if it is a *superseded implementation*") and its exclusion
("any commented line naming a symbol that still exists — the ~72-line excluded set") pull in
opposite directions, because almost every commented-out line names *some* live symbol. The rule
was therefore made operational and applied uniformly:

> **REMOVE** a multi-line commented block that is a complete superseded implementation — a live
> replacement performs its job, or its symbols are dead tree-wide — **plus** a single commented
> line whose named symbol exists nowhere else in the tree.
>
> **KEEP and record** every single disabled statement that names a still-live symbol (that is the
> excluded set: a disabled *behaviour*, not a superseded implementation), all prose / `TODO` /
> `FIXME` / `NOTE` / banners, and the two user-deferred blocks.

Deliberately conservative in the two places where a wrong deletion is unrecoverable:
`hardware_state` (§B.7 K-1) and PWM duty-cycle vs servo pulse-width (§B.7 K-2) both stayed.

### B.2 Candidate enumeration, before any deletion

An AST-based scanner grouped contiguous comment-only runs, stripped the `#`, dedented, and kept
only runs that **parse as Python** and contain at least one non-string statement. Prose, `TODO`,
`NOTE` and banners fail that test by construction.

| | value |
|---|---|
| candidate commented-code lines, whole `autopilot/autopilot` tree, pre-sweep | **328** |
| of which in **protect-listed** files (`Event_Dispatcher.py` 12, `external_hardware_runtime.py` 2) | 14 — **not touched** |
| candidates after the sweep | **175** |

The scanner is a *lower* bound: it cannot see fragments that do not parse standalone
(`# try:` without its `except`, `# if x:` without a body). Those were found by a second, looser
regex pass over the four named files and reviewed by hand — `task.py:383-395` and
`external/__init__.py:27-48` are two blocks the strict scanner missed entirely.

Per-file pre-sweep candidate counts (non-protected, ≥5 lines):

| file | candidates |
|---|---|
| `hardware/gpio.py` | 58 |
| `networking/message.py` | 44 |
| `networking/station.py` | 29 |
| `tasks/task.py` | 25 |
| `core/pilot.py` | 24 |
| `networking/node.py` | 19 |
| `tasks/mics_task.py` | 14 |
| `transform/image.py` | 14 |
| `setup/forms.py` | 12 |
| `external/__init__.py` | 11 |
| `utils/logging_utils.py` | 9 |
| `hardware/i2c.py` | 9 |
| `transform/selection.py` | 7 |
| `stim/sound/jackclient.py` | 6 |
| `stim/sound/base.py` | 5 |

### B.3 Removed — per file, against the 244 target

| file | lines before | lines after | **comment lines removed** | audit's figure |
|---|---|---|---|---|
| `networking/station.py` | 1363 | 1300 | **58** | ~52 |
| `networking/message.py` | 270 | 220 | **47** | ~50 |
| `external/__init__.py` | 158 | 127 | **31** | — |
| `tasks/task.py` | 460 | 428 | **28** | ~28 |
| `hardware/gpio.py` | 1717 | 1693 | **24** | ~28 |
| `transform/image.py` | 338 | 325 | **12** | — |
| `tasks/mics_task.py` | 1602 | 1589 | **11** | ~11 |
| `networking/node.py` | 644 | 637 | **7** | — |
| `transform/selection.py` | 94 | 86 | **6** | — |
| `setup/forms.py` | 478 | 474 | **4** | — |
| `stim/sound/base.py` | 635 | 631 | **4** | — |
| `stim/managers.py` | 616 | 613 | **3** | — |
| `core/loggers.py` | 184 | 182 | **2** | — |
| **Task 2 subtotal** | | | **237** | |
| `core/pilot.py:49` (Task 1) | 1284 | 1199 | **1** | 1 |
| **PHASE TOTAL (HYG-11)** | | | **238** | **244** |

**238 vs 244 — a 2.5% shortfall, and every line of it is accounted for in §B.7**, not
unexplained. Two per-file numbers land on the audit exactly (`task.py` 28, `mics_task.py` 11),
which is the strongest evidence the classification matches the auditor's.

`mics_task.py` yielding exactly **11** — the plan's stated sanity check, and the one it warned
would look wrong — reproduces exactly: two commented-out superseded methods, `set_and_notify`
(6 lines) and `set_tracker_and_notify` (5), each sitting directly beneath its live replacement.

### B.4 Files edited beyond this plan's declared `files_modified`

This plan declares `station.py`, `message.py`, `gpio.py`, `task.py` and `core/pilot.py`. The nine
files below are the after-the-fact `files_modified` — **plan 08 reads this list when it diffs the
manifest.** The plan anticipated "11 smaller files"; the scan surfaced **9** with removable
superseded blocks.

| path (repo-relative) | comment lines removed | what went |
|---|---|---|
| `autopilot/autopilot/external/__init__.py` | 31 | vendored `autopilot.external.jack` setup — `external/` holds only `__init__.py`, so the module it imports does not exist; plus the dead `JACKD_MODULE` flag and a superseded second import attempt |
| `autopilot/autopilot/transform/image.py` | 12 | commented `@property deeplabcut`, superseded by the live `self.deeplabcut` assignment at `:99` and `import_dlc` |
| `autopilot/autopilot/tasks/mics_task.py` | 11 | `set_and_notify` / `set_tracker_and_notify`, both duplicated live above |
| `autopilot/autopilot/networking/node.py` | 7 | commented `l_stream`, superseded by the live `l_stream` at `:392` |
| `autopilot/autopilot/transform/selection.py` | 6 | commented `check_slice` — **the live one is at `:61`**, so this was a stale duplicate |
| `autopilot/autopilot/setup/forms.py` | 4 | superseded `self.input = odict({...})`, live version 10 lines below |
| `autopilot/autopilot/stim/sound/base.py` | 4 | `n_gets` debug counter, dead tree-wide |
| `autopilot/autopilot/stim/managers.py` | 3 | commented empty `class Reward_Manager` stub |
| `autopilot/autopilot/core/loggers.py` | 2 | two superseded formatter alternatives; live formatter at `:136` |

### B.5 The named targets, block by block

**`networking/station.py` — 58 lines in 11 ranges**

| range | lines | why removable |
|---|---|---|
| `620-651` | 30 | the author's *"all of the below should be removed but i am paranoid… so i am just commenting for now"* block — **the note is the justification, so it went with the block** |
| `928-938` | 8 | old `l_continuous`, superseded by the live one at `:898` |
| `686`, `688-690`, `692-693` | 6 | `# self.loop.stop()` plus an orphaned `except AttributeError:/pass` fragment whose `try` is gone; superseded by `_check_stop()` at `:695` |
| `950-953` | 4 | state-dedup residue, unreachable as written (it tests a dict created empty on the line above) |
| `320-322` | 3 | resend timers, superseded by the live `send_outbox` at `:319` + `repeat()` at `:396` |
| `393-394` | 2 | same for `push_outbox` |
| `522-523` | 2 | superseded by the live `Message(msg[0])` on the next line |
| `737-738` | 2 | `send_plot` — dead tree-wide (`sent_plot` is the live name) |
| `801` | 1 | `send_plot` again |

**`networking/message.py` — 47 lines**, all Python-2-era residue: the commented
`__setattr__` / `__getattr__` / `_check_enc` / `_check_dec` cluster at `124-155` (31 lines, uses
`basestring` and `json_tricks`), the superseded arg-validation at `69-72`, the `msg = {…}` literal
superseded by `msg = self.__dict__`, and four single lines whose symbols are dead tree-wide.
`DETECTED_MINPRINT`, `_check_enc`, `_check_dec` and `json_tricks` were each confirmed to occur
**only inside comments** by an unfiltered tree-wide reader before deletion.

**`tasks/task.py` — 28 lines**, the trigger-dispatch archaeology in `handle_trigger`. The live
path is `self.event_queue.put(...)` at `:373` → the worker at `:262-266` (`with self.trigger_lock:`)
→ `execute_trigger` at `:268`. Removed: the `trigger_lock.acquire` guard (superseded by the
worker's `with`), dispatch impl #1 (direct call + `TypeError` fallback), impl #2
(`inspect.signature`-based `level` passing), and the trailing `clear triggers` /
`trigger_lock.release()` / `stage_block.set()` scaffolding.

**`hardware/gpio.py` — 24 lines**, the commented `LED_RGB.__getattr__` channel-dispatch method,
superseded by explicit per-method dispatch over `self.channels`. **Everything else in `gpio.py`
was kept** — see K-1 and K-2.

### B.6 Proof the sweep only deleted

`difflib.SequenceMatcher` against a pre-sweep snapshot of all 13 files:
**33 `delete` opcode groups, 0 `insert`, 0 `replace`.** Nothing was reflowed, reindented or
reordered. Each range additionally asserted (a) an anchor line's exact pre-edit text, (b) that
**every** line in the range is blank or starts with `#` — a live-code line aborts the sweep — and
(c) that the range contains exactly the expected number of comment lines.

The whole sweep validates every range in every file **before writing any file**, so a
miscount cannot leave the tree half-swept. That path was exercised for real: the first attempt
mis-counted `task.py:375-402` as 25 comment lines (line 392 is blank, not a comment), the run
aborted, the two already-written files were restored byte-identically from snapshot
(md5 verified), the count was corrected to 24 and the sweep re-run cleanly.

### B.7 Kept — undecided, with the live symbol that kept it

Every one of these is a *disabled behaviour* on a still-live symbol, not a superseded
implementation. Line numbers are **post-sweep**.

**K-1. `hardware_state` — 8 sites in `gpio.py` + the whole writer in `logging_utils.py`.**
This is the largest kept group and the one worth a decision of its own.
`hardware_state` is **read live** at `gpio.py:439` (`self.set(self.hardware_state)`) and at
`logging_utils.py:95` (`level=int(self.hardware_state)`), but written live only at `gpio.py:877`.
The commented code that used to maintain it is `logging_utils.py:59-77`
(`state_changing_methods` + the `@log_action` state transition) and
`gpio.py:457, 513-515, 1023-1033, 1158, 1309, 1609, 1683, 1689`. Deleting these would erase the
only surviving description of how a live, read-every-log-event attribute was supposed to be
maintained. **Kept. This is a real latent defect and deserves its own decision, not a sweep.**

**K-2. `gpio.py:1017, 1021` — `# value = self._clean_value(value)` and
`# self.pig.set_PWM_dutycycle(self.pin_bcm, value)`.** The live line below `:1021` is
`self.pig.set_servo_pulsewidth(...)`. Formally a directly-superseded single, but the supersession
is a **hardware behaviour change** (PWM duty cycle → servo pulse width) on a rig this phase does
not exercise, and `_clean_value` is still live at `:1035`. Kept under the plan's
"when you cannot tell, keep it".

**K-3. `station.py:309-311` (`# log_this = True` / `# if 'NOLOG' in msg.flags.keys():`) and
`:314` (`#if msg.key != "CONFIRM":`).** `NOLOG` is **still sent by live code** —
`pilot.py` does `flags={'NOLOG':True}` — but `station.py:315` now logs unconditionally, so no
live code honours it. Kept because the flag is live. **Finding F-3.**

**K-4. `station.py:201` `# self.release()`** (disabled cleanup in a `finally:`),
**`:471`** `#self.logger.info('CONFIRMED MESSAGE …')`, **`:843`/`:847`/`:864`** (old positional
`self.send('_T', 'DATA', …)` call forms), **`:988`** `#self.id = prefs.get('NAME').encode('utf-8')`.
All single lines naming live symbols (`self.send`, `self.logger`, `prefs.get`).

**K-5. `message.py:111` `# self.changed=True` inside `__setitem__`.** `self.changed` is live and
read at `:199` (`if not self.changed and self.serialized: return self.serialized`). With this line
commented, `msg['x'] = y` does **not** invalidate the serialization cache. Kept — and see
**Finding F-4**, because this one may be a live bug rather than a dead comment.
Also kept: `:79`, `:92`, `:129`.

**K-6. `task.py:355-358` and `:360-363`** — the `# if pin not in self.triggers.keys(): return`
and `# if pin == 'TIMEUP': return` guards. `self.triggers` is live. These are *guards*, not
dispatch; whether the queue worker still needs them is a behavioural question. Kept.
Also kept `task.py:9` (`# from autopilot.core.networking import Net_Node`).

**K-7. `node.py:384-387`** — `# if value in self.timers.keys(): … cancel()`. `self.timers` is live
(`node.py:118`) and documented at `:67`, but nothing cancels timers any more. Kept.
Also kept `node.py:406-408`.

**K-8. `transform/selection.py:29`** `# self.check_slice(select)` — the method it calls is **live**
at `:61`. A disabled validation call, not dead code. Kept (its stale commented *duplicate
definition* was removed).

**K-9. `mics_task.py:1581-1583`** — `# self.hardware['GPIO']['TTL1'].set(0)` / `# if self.ttl_timer:`.
Hardware toggle. Kept.

**K-10. `hardware/i2c.py` — 9 candidates, none touched.** `i2c.py` is off-limits beyond plan 05's
stated scope under TRIGA-12, and it is the licker's driver.

**K-11. `core/pilot.py` — 24 remaining candidates, none touched by the sweep.** HYG-11's named
scope for `pilot.py` is `:49` only (removed in Task 1); the rest of `pilot.py`'s commented code is
the old terminal-DATA-return path inside `run_task`, whose symbols (`self.node.send`,
`self.logger.debug`, `self.stage_block`) are all live. Sweeping the phase's most load-bearing file
beyond its named scope is not worth the risk. **Handed to plan 08 as a candidate.**

**K-12. Long tail kept in full:** `jackclient.py` (6), `sounds.py` (3), `transforms.py` (3),
`mixer.py` (3), `prefs.py` (2), `visuals.py` (2), `geometry.py` (2), `hardware/__init__.py` (2),
`graduation.py`, `pyoserver.py`, `setup_autopilot.py`, `PeriodicTimer.py`, `plugins.py`,
`timeseries.py` (1 each) — all single disabled statements on live symbols.

### B.8 Findings recorded, not acted on

**F-1. `import tables` survives `pilot.py` although the HDF5 subsystem is gone.**
`pilot.py:34` still runs `warnings.simplefilter('ignore', category=tables.NaturalNameWarning)`, so
the import is load-bearing and removing it would raise `NameError` at module-import time. Both
lines are now vestigial — pilot.py never touches PyTables again — but removing them is a
behavioural change to a global warning filter, outside the plan's four named sites. Candidate for
plan 08.

**F-2. `trial_data` in `run_task` is now assigned and never read.** It existed only to gate the
HDF5 row write. Live code, not a comment, so outside HYG-11. Candidate for plan 08.

**F-3. The `NOLOG` message flag is sent but no longer honoured.** `pilot.py` sends
`flags={'NOLOG':True}`; `station.py:315` logs every message unconditionally because the
`log_this` gate is commented out (K-3). A real behavioural gap, not sweep residue.

**F-4. `Message.__setitem__` does not invalidate the serialization cache.** `self.changed = True`
is commented at `message.py:111` while `serialize()` short-circuits on
`if not self.changed and self.serialized` (`:199`). Mutating a Message via `msg['k'] = v` after it
has been serialized once can therefore send the stale bytes. Kept as K-5; worth its own decision.

**F-5. `external/__init__.py:40` carried a `git pu` typo inside the removed block** — the string
`os.path.join(jackd_path, 'lib')git pu` — which is why the strict parse-based scanner never
flagged that 22-line block. Removed with it; recorded because it shows a parse-based scan alone is
not sufficient.

### B.9 `station.py` — swept vs exempted, recorded separately

| | value |
|---|---|
| lines before | 1363 |
| lines after | **1300** |
| **dead commented lines swept** | **58** |
| **lines exempted (HOLD 1, user-deferred)** | **5 commented `logger` lines + 1 live `print("")`** |

The watchdog moved from `:1330-1346` to `:1267-1283` (shifted by removals above it) and is
**byte-identical**:

```
1270|        # logger = getattr(self, "logger", None)
1277|                # if logger:
1278|                #     logger.warning("No PING from orchestrator for >21s, retrying HANDSHAKE")
1279|                self._handshake_callback()
1280|            except Exception:
1281|                print("")
1282|                # if logger:
1283|                #     logger.exception("Handshake retry failed")
```

`station.py` is **not** byte-identical overall, and must not be. The two facts above are recorded
separately so no later reader conflates the carve-out with the sweep.

---

## §C. Gates

| gate | result |
|---|---|
| `python3 -m compileall -q autopilot/autopilot tools tests` | **exit 0** |
| `python3 tools/check_tree_integrity.py --strict` (before Task 1, after Task 1, after Task 2) | **exit 0** — `40 closure members, 30 protected files, 1 known-dangling exemptions held, 0 violations` |
| `Event_Dispatcher.py` sha256 vs Wave 0 baseline | `1bfadc3313f3552f1d69057a91ce403ca8f2306c7fc874c0369fad9600adac68` — **MATCH** |
| `_dropped_no_clock` / `_dropped_on_send` present | **yes, both** |
| Pi pytest delta vs `30-PYTEST-BASELINE.json` | **179 → 179, 0 new, 0 fixed** |
| `tests/test_trigger_assignments.py` | **51 failing** — unchanged, as required |
| `tests/test_execute_trigger_guard.py` | **11 failing** — unchanged, as required |
| `liors` tree-wide over every `.py` | **0 hits** |
| `open_file` / `h5f` in `pilot.py` | **0 hits each** |
| protect-listed files edited | **0** — all 13 targets checked against `tree_protect_list.json` before any write |
| git commands run in `/home/ido/pi-mirror` | **none**; `--rebaseline` **not run**; nothing deployed to the Pi |

---

## §D. Proposed verdict lines (plan 08 transcribes these)

```
HYG-11 | PROVEN | 238 dead commented-out lines removed across 14 files (237 in Task 2 + pilot.py:49),
         against an audit target of 244; per-file breakdown in §B.3, the 2.5% shortfall itemised in
         §B.7 as 175 deliberately-kept candidates with the live symbol that kept each one.
         difflib: 33 delete opcode groups, 0 insert, 0 replace across all 13 swept files.
         compileall exit 0; pytest delta 179 -> 179 with 0 new failing node ids.

HYG-14 | PROVEN | HDF5 set removed whole across all four sites - open_file() (57 lines), the
         self.h5f cleanup, the ~23 commented lines, and the run_task docstring line that still
         advertised it; open_file/h5f/liors all match 0 lines in pilot.py, and no caller existed
         tree-wide. Both restorations DEFERRED BY THE USER 2026-08-10 and preserved verbatim
         through the sweep: HOLD 0 (4 lines, pilot.py:1071-1082) and HOLD 1 (5 commented logger
         lines + the bare print(""), station.py:1270-1283). Neither uncommented, neither deleted.

HYG-12 | PROVEN | Event_Dispatcher.py sha256 unchanged from the §1 baseline
         (1bfadc3313f3552f1d69057a91ce403ca8f2306c7fc874c0369fad9600adac68);
         _dropped_no_clock and _dropped_on_send present. The file was excluded by name from the
         sweep's target list and re-checked against tree_protect_list.json before any write.
```

## §E. For plan 08

- Add to the deferred/candidate list: **F-1** (`import tables` + the PyTables warning filter in
  `pilot.py`), **F-2** (`trial_data` now write-only), **F-3** (`NOLOG` sent but not honoured),
  **F-4** (`Message.__setitem__` does not invalidate the serialization cache), **K-1**
  (`hardware_state` read live in two files, written in one, its maintainer commented out),
  **K-11** (`core/pilot.py`'s 24 remaining commented candidates, deliberately left).
- **Both HYG-14 restorations belong under `Deferred by the user`, never under `Removed`.**
- This plan did **not** edit `30-HARDWARE-VALIDATION.md` (plan 07 runs in parallel).
