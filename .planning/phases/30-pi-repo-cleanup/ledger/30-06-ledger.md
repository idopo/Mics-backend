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
