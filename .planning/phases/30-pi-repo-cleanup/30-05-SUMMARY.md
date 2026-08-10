---
phase: 30-pi-repo-cleanup
plan: 05
subsystem: pi-tree
tags: [hygiene, dead-code-removal, ast-surgery, hardware-libs, registry, i2c, mpr121, reachability]

# Dependency graph
requires:
  - "30-01 — tools/check_tree_integrity.py (--strict gate), tree_protect_list.json, 30-PYTEST-BASELINE.json delta command"
  - "30-04 — pilot/plugins/ emptied; the corrected OG_TRIGGER/IR1/0x3f toggle inventory handed forward"
provides:
  - "A lean autopilot/tasks/ holding only __init__.py, task.py, mics_task.py, graduation.py, fda_vocabulary.py — and it compiles"
  - "No camera code anywhere: cameras.py, usb.py, setup_mlx90640.sh and the MLX90640 class gone from the Pi copy AND from hardware_libs"
  - "hardware_libs id 9 active version 144, byte-identical (sha256-proven) to the edited disk i2c.py"
  - "HYG-14 complete on its DELETE half — all three toggles retired tree-wide"
  - "ledger/30-05-ledger.md — four-criteria verdicts, the i2c cut-boundary correction, and the drift characterisation"
affects: [30-06, 30-07, 30-08, 30-09]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Excise a class by AST span with both ends asserted, never by hardcoded line number and never 'to the line before the next class'"
    - "Prove a surgical edit with difflib opcodes: N deletes, 0 inserts, 0 replaces beats eyeballing a diff"
    - "Prove DB/disk identity with sha256, not with matching lengths"
    - "Compare octet_length against file bytes, never length() — length() counts characters"
    - "Assert an inheritance chain by AST after cutting near it; py_compile cannot see a lost sibling class"

key-files:
  created:
    - .planning/phases/30-pi-repo-cleanup/ledger/30-05-ledger.md
    - .planning/phases/30-pi-repo-cleanup/30-05-SUMMARY.md
  modified:
    - /home/ido/pi-mirror/autopilot/autopilot/hardware/i2c.py
    - /home/ido/pi-mirror/autopilot/autopilot/utils/registry.py
    - "hardware_libs id 9 (DB) — active_version_id 26 -> 144"
  deleted:
    - /home/ido/pi-mirror/autopilot/autopilot/tasks/children.py
    - /home/ido/pi-mirror/autopilot/autopilot/tasks/nafc.py
    - /home/ido/pi-mirror/autopilot/autopilot/tasks/gonogo.py
    - /home/ido/pi-mirror/autopilot/autopilot/tasks/free_water.py
    - /home/ido/pi-mirror/autopilot/autopilot/tasks/test.py
    - /home/ido/pi-mirror/autopilot/autopilot/tasks/RecordingBox.py
    - /home/ido/pi-mirror/autopilot/autopilot/tasks/protocol_scripts.py
    - /home/ido/pi-mirror/autopilot/autopilot/hardware/cameras.py
    - /home/ido/pi-mirror/autopilot/autopilot/hardware/usb.py
    - /home/ido/pi-mirror/autopilot/autopilot/setup/setup_mlx90640.sh

key-decisions:
  - "Cut MLX90640 to its AST end_lineno, NOT to the line before class MPR121 as the plan literally said — lines 792-796 between them are import board / busio / adafruit_mpr121, which MPR121 needs"
  - "Left the 3 newly-unused imports (threading, product, griddata) in i2c.py: TRIGA-12 scopes the edit, and dropping griddata would change what the module demands of the rig's environment"
  - "Left hardware/__init__.py:54's META_CLASS_NAMES alone — it names removed classes but nothing reads it, and it is outside this plan's <files> block"
  - "Recorded the 6 stale available_locked_states rows as a failed-and-overridden criterion 3 rather than reporting the sweep as four-criteria clean"
  - "Characterised the hardware_libs drift before reconciling: it was length()-chars vs disk-bytes, and the copies were byte-identical"

patterns-established:
  - "When a plan's literal cut boundary would take a survivor with it, cut by AST and record the deviation — the plan is evidence, not authority"
  - "A reconciliation records what it would have overwritten before it overwrites anything"

requirements-completed: [HYG-05, HYG-06]

# Metrics
duration: 16min
completed: 2026-08-10
---

# Phase 30 Plan 05: Registry Sweep Collateral and the Camera Subtree Summary

**Ten files and 219 lines of `i2c.py` removed across both sides of the DB boundary — with the
`MLX90640` class cut by AST span rather than by the plan's literal boundary, which would have taken
MPR121's `board`/`busio`/`adafruit_mpr121` imports with it and killed the licker silently — plus the
discovery that the phase's recorded "6-byte `hardware_libs` drift" never existed.**

## Performance

- **Duration:** 16 min (16:31:38Z → 16:47:51Z)
- **Tasks:** 3
- **Files removed:** 10 (150,687 bytes); 2 modified; 1 DB version created
- **Guard runs:** 4, all exit 0 with 0 violations

## Accomplishments

- **HYG-06: the seven registry-sweep collateral modules are gone** (60,505 B) and
  `compileall` over `autopilot/tasks/` exits 0 — the gate that matters, because `common.py:47-67`'s
  `list_classes` has no per-file guard, so one broken file there ships `tasks: []` in every
  handshake with no error anywhere.
- **The one string-keyed dangler the AST guard is structurally unable to see was removed**:
  `REGISTRIES.CHILDREN = "autopilot.tasks.children.Child"` at `utils/registry.py:42`. The
  criterion-2 evidence — **zero** `'child'` keys anywhere in `mics-backend/api` or
  `mics-backend/orchestrator` — was re-run and recorded, not taken on trust, because it is what
  makes `pilot.py:591` dead code and licenses plan 06's branch removal.
- **HYG-05 executed as three parts on the Pi copy** — `cameras.py` (69,302 B), `usb.py` (10,546 B),
  the `i2c.py:8` import, the `mlx_cam` guard and the whole `MLX90640` class body.
  `i2c.py`: 35,934 → 28,423 bytes, and `difflib` reports **exactly 3 delete opcodes and 0
  insert/replace opcodes** against the pre-edit copy. Nothing was reformatted or reordered.
- **The lick path is provably intact.** AST assertion after the cut: `I2C_9DOF`, `MPR121`,
  `Motor_Shield_Hat`, `Motor_Shield_Hat_extend` and `Touch_Detector(MPR121)` all present with their
  inheritance chains; `MLX90640` and `Camera` absent; **zero** residue for `Camera`, `MLX90640`,
  `mlx_cam`, `MLX90640_LIB` and `autopilot.hardware.cameras`, prose included.
- **HYG-05 on the DB copy**: `PUT /api/hardware-libs/9` → HTTP 200, active version **26 → 144**,
  `impact.affected_definition_ids` **empty**, `impact.removed_methods` naming exactly `MLX90640`'s
  11 methods and no survivor's. The active version's `octet_length` (28,423) **and its stored
  `sha256_hash`** both equal the disk file's — identical, not merely same-length. Versions 15 and
  26 are preserved, so the camera code stays recoverable.
- **HYG-14's DELETE half is complete.** `RecordingBox.py` held the last `set_cdc_manual(0x3f)`;
  after Task 1 both `set_cdc_manual(0x3f)` and `OG_TRIGGER` are **zero across every surviving
  `.py`**, while `pilot/prefs.json`'s live pin declarations at `:241`/`:243` (and `IR1` at
  `:278`/`:282`) are untouched. Asserted as **call forms, never bare tokens** — the distinction
  30-CONTEXT.md's CORRECTION block exists to protect.
- **Gates:** guard `--strict` exit 0 (`40 closure members, 30 protected files, 1 known-dangling
  exemptions held, 0 violations`) after every deletion task; `compileall` over `autopilot/autopilot`
  exit 0; Pi pytest delta **179 → 179, 0 new failures** with `test_mpr121_irq_hygiene` at 0 failing
  and `test_check_for_detectors` still contributing its baseline 17; backend suite **435 passed, 1
  skipped**.

## The two things that mattered most

**1. The plan's own cut boundary would have killed the licker.**

The plan says to delete `MLX90640` *"through the last line before `class MPR121(Hardware):`"*.
Applied literally, that eats `i2c.py:792-796`:

```
792| import board
793| import busio
796| import adafruit_mpr121
```

Those are module-level imports **MPR121 depends on** — `busio.I2C(board.SCL, board.SDA)` and
`adafruit_mpr121.MPR121(self.i2c)`. Losing them leaves `MPR121.__init__` raising `NameError` on
every instantiation: the lick sensor dead on the live rig, presenting — with no `TASK_ERROR`
emitter on the Pi — as a run stuck `running` for ever rather than as an error. **`py_compile` would
not have caught it**, because the module still parses and compiles fine.

The class was therefore cut to its AST `end_lineno` (789) plus trailing blanks, with an explicit
assertion that the first surviving line with content is `import board`, and a post-write assertion
that all three imports are present. The surviving `.py` file is 774 lines; the seam reads cleanly.

**2. The "6-byte `hardware_libs` drift" is a measurement artifact.**

30-CONTEXT.md, the phase brief and plan 05's own `<verified_db_state>` all record `i2c.py` as
"already drifted 6 bytes — 35,934 on disk vs 35,928 in the DB". Measured properly:

| | value |
|---|---|
| `length(source_code)` — **characters** | 35,928 |
| `octet_length(source_code)` — **bytes** | **35,934** |
| disk `i2c.py` — bytes | **35,934** |

The 6 is exactly `3 × (3−1)`: `i2c.py` holds three em-dashes (U+2014), 1 character and 3 UTF-8
bytes each. The comparison was characters against bytes. Proof of identity rather than of equal
size: stripping the single newline psql appends to its dump gives 35,934 bytes with md5
`3c933d65eeac795d2bcabd8d5cc3c08f` on **both** sides, and zero `difflib` opcodes.

So the reconciliation discarded nothing. The **general** deferred concern stands — there is still
no process keeping the exec'd DB copy in sync, and this plan had to make the same edit twice by
hand, which is the concern demonstrating itself — but the specific instance cited as its evidence
was never real. Plan 08 should restate that deferred item without the number.

## Task Commits

All *tree* changes live in `/home/ido/pi-mirror`, which is not agent-managed version control.
The commits below carry the evidence in `mics-backend`.

1. **Task 1: Remove registry sweep collateral from `autopilot/tasks/` (HYG-06) and close the 0x3f toggle** — `cb84444` (chore)
2. **Task 2: Remove `cameras.py`, `usb.py`, `setup_mlx90640.sh`, the i2c import and the `MLX90640` class (HYG-05, Pi copy)** — `21f37aa` (chore)
3. **Task 3: Reconcile the `hardware_libs` copy of `i2c.py` (HYG-05, DB copy)** — `56b217a` (chore)

## Files Created/Modified

**In `/home/ido/pi-mirror` (not version-controlled by the agent):**

*Deleted — 10 files, 150,687 bytes:*

| Path | Bytes |
|---|---|
| `autopilot/autopilot/tasks/children.py` | 11,245 |
| `autopilot/autopilot/tasks/nafc.py` | 16,768 |
| `autopilot/autopilot/tasks/gonogo.py` | 8,110 |
| `autopilot/autopilot/tasks/free_water.py` | 5,916 |
| `autopilot/autopilot/tasks/test.py` | 14,814 |
| `autopilot/autopilot/tasks/RecordingBox.py` | 3,542 |
| `autopilot/autopilot/tasks/protocol_scripts.py` | 110 |
| `autopilot/autopilot/hardware/cameras.py` | 69,302 |
| `autopilot/autopilot/hardware/usb.py` | 10,546 |
| `autopilot/autopilot/setup/setup_mlx90640.sh` | 792 |

*Modified:*
- `autopilot/autopilot/hardware/i2c.py` — 35,934 → 28,423 B, 993 → 774 lines
  (md5 `3c933d65…` → `58c6a426…`)
- `autopilot/autopilot/utils/registry.py` — one enum member removed

*Untouched by design:* `tasks/__init__.py` (names only the surviving `task.py`),
`pilot/prefs.json`, `hardware/__init__.py`, `core/pilot.py`, every protect-listed file.

**In the database:** `hardware_libs` id 9 — `active_version_id` 26 → **144** (version_number 3,
state `beta`, sha256 `649d4f31…483e`).

**In `mics-backend` (committed):** `ledger/30-05-ledger.md`, this summary.

## Decisions Made

- **Cut `MLX90640` by AST span, deviating from the plan's literal boundary.** See above. The plan
  is evidence, not authority, when following it literally would delete a survivor's dependencies.
- **Left `threading`, `product` and `griddata` in `i2c.py` although the edit orphaned them.**
  TRIGA-12 puts `i2c.py` off-limits beyond this plan's stated scope, and dropping
  `from scipy.interpolate import griddata` would change what the module demands of the rig's
  Python environment at import time — not a change worth making without a rig proof. (8 other
  imports there were already unused before this plan; recorded, not touched.)
- **Left `hardware/__init__.py:54`'s `META_CLASS_NAMES` alone.** It names `Camera`,
  `Directory_Writer` and `Video_Writer`, all defined in the removed `cameras.py` — but a tree-wide
  scan finds the constant read **nowhere** (1 hit: its own definition). It is an inert constant,
  not a second dispatch table, and it is outside this plan's `<files>` block. Handed to plan 06/08.
- **Recorded criterion 3 as failed-and-overridden** for the six `available_locked_states` rows,
  rather than reporting the sweep as four-criteria clean — the standard plan 04 set.
- **Characterised the drift before reconciling**, per the plan's own instruction that HYG-05
  "does not permit reconciling without knowing what you overwrote". It turned out there was
  nothing to overwrite, which is only knowable because the check ran.

## Deviations from Plan

### Auto-fixed

**1. [Rule 1 — Bug in the plan's instruction] The stated `MLX90640` cut boundary would have removed
MPR121's dependencies.**

- **Found during:** Task 2, reading the class boundary before cutting.
- **Issue:** *"delete … through the last line before `class MPR121(Hardware):`"* spans
  `i2c.py:790-798`, which contains `import board`, `import busio` and `import adafruit_mpr121` —
  used by `MPR121.__init__` at the old `:809` and `:816`. The result compiles and passes
  `py_compile`; it fails at runtime on the rig, silently.
- **Fix:** cut `[cls.lineno, cls.end_lineno]` plus trailing blank lines only, with an assertion
  that the first surviving content line is `import board`, plus post-write assertions that all
  three imports are present and that the five survivor classes are intact by AST.
- **Files modified:** `/home/ido/pi-mirror/autopilot/autopilot/hardware/i2c.py`
- **Committed in:** `21f37aa`

### Findings (recorded, not acted on)

**2. The 6-byte `hardware_libs` drift does not exist** — `length()`-characters vs disk-bytes, with
three em-dashes accounting for the difference exactly. The copies were byte-identical (md5 match,
zero difflib opcodes). Documented in ledger §C.1 with a request that plan 08 restate the deferred
item without the number. **Nothing was "fixed"** — the general no-sync-process concern stands.

**3. `hardware/__init__.py:54`'s `META_CLASS_NAMES` names three classes that went with
`cameras.py`.** Read nowhere; inert; outside this plan's `<files>`. Ledger §B.8 Finding B-1.

**4. Three imports in `i2c.py` are newly unused** (`threading`, `product`, `griddata`), on top of
eight that already were. Left in place under TRIGA-12. Ledger §B.8 Finding B-2.

**5. Six `available_locked_states` rows go stale** — `RecordingBox`, `Free_Water`, `GoNoGo`,
`Nafc`, `DLC_Hand`, `DLC_Latency`, all on pilot 1, all `is_legacy_filename = true`. **Zero
toolkits reference them** (`task_toolkits.locked_state_source` count = 0), so this is materially
weaker than plan 04's Finding 1, where 8 live toolkit rows resolved to a removed file. Accepted
staleness under HYG-04, which proved the backend has no prune path and never writes on an empty
handshake. Ledger §A.2.

**Total deviations:** 1 auto-fix (the cut boundary), 4 findings recorded.
**0 assertions weakened, 0 protect-listed files touched, `tree_protect_list.json` unedited,
`--rebaseline` not run, 0 extra files deleted.**

## Issues Encountered

- **Every load-bearing absence claim was measured with an unfiltered Python reader**, never `grep`
  alone. This is not ceremony: the HYG-05 correction this plan executes exists *because* a prior
  session read filtered `grep` output that rendered `i2c.py:580` blank, concluded `Camera` was a
  dead import, and nearly deleted `MLX90640`'s base class out from under it. `grep` was used only
  to corroborate results the Python scanners had already produced; both agreed everywhere.
- **`psql -tAc` needed verification before it could be trusted.** Its dump was 35,935 bytes against
  an expected 35,928 — a mismatch that looks like corruption and is actually two separate,
  individually harmless facts (character-vs-byte counting, plus the trailing newline psql appends).
  The plan's fallback to `GET /api/hardware-libs/9` was not needed once both were accounted for.
- **`compute_closure` never included `cameras.py`**, so the guard's "40 closure members" is
  unchanged across every deletion here. That is correct, not a blind spot: the closure walks from
  `core/pilot.py`, which does not statically reach `tasks/mics_task.py` (tasks load dynamically),
  so `i2c.py` and everything under it sits outside the closure. What caught `i2c.py:8` was the
  dangling-reference check, exactly as plan 01 calibrated (5 violations on a simulated
  `rm cameras.py`).

## Next Phase Readiness

**Plan 06 is unblocked**, and this plan hands it one explicit, evidenced piece of work:

- **Remove the `if 'child' in value.keys():` / `else:` branch at `core/pilot.py:589-592`**,
  collapsing to the unconditional `task_class = autopilot.get_task(value['task_type'])`. The
  `REGISTRIES.CHILDREN` member it dispatches into is gone as of `cb84444`; the criterion-2 proof
  (zero `'child'` keys in `mics-backend`) is in ledger §A.3. `pilot.py` was **not** touched here.
- Plan 06 also still owns HYG-14's RESTORE half (`station.py:1333-1346`), untouched by this plan.

Also carried forward:
- **Plan 07** owns `prefs_wsl*.json`, which still carry `OG_TRIGGER`/`IR1`; `pilot/prefs.json`'s
  live declarations survive the phase by design and plan 07 asserts they do.
- **Plan 08** merges the ledger fragments into `30-HARDWARE-VALIDATION.md` (this plan deliberately
  did not edit it), transcribes the `HYG-05 | PROVEN` and `HYG-06 | PROVEN` verdict lines, records
  the HYG-05 three-part correction as **closed**, restates the drift deferred item without the
  "6 bytes" claim, and owns the tree-wide `__pycache__` purge —
  `utils/__pycache__/registry.cpython-{312,37}.pyc` still carry the old `REGISTRIES` table.
- **Plan 09**'s rig session is the proof for the one behavioural change in this arc (the START
  dispatch collapse) and for the licker surviving the `i2c.py` surgery.
- **`--rebaseline` was not run and must never be run again.**
- **No git command was run in `/home/ido/pi-mirror` at any point.** Every git invocation used
  `git -C /home/ido/mics-backend …`, which is cwd-independent; no command combined a `cd` into
  `pi-mirror` with a git call. Nothing was deployed to the Pi, no `rsync` ran, the pilot was not
  started or stopped, and no Python was executed on the Pi. The Pi picks up `hardware_libs`
  version 144 on its next `LOAD_HARDWARE_LIBS`, which the user triggers by starting a run.

## Self-Check: PASSED

- **All 10 removed paths confirmed absent** on disk.
- **All 10 must-survive paths confirmed present**: `tasks/{__init__,task,mics_task,graduation,fda_vocabulary}.py`,
  `utils/registry.py`, `hardware/i2c.py`, `hardware/__init__.py`, `pilot/prefs.json`,
  `core/pilot.py`.
- **Both `mics-backend` artifacts exist**: `ledger/30-05-ledger.md`, `30-05-SUMMARY.md`.
- **All three task commits present in git**: `cb84444`, `21f37aa`, `56b217a`.
- **Re-verified at summary time:** guard `--strict` exit 0 (`40 closure members, 30 protected
  files, 1 known-dangling exemptions held, 0 violations`); `compileall` over `autopilot/autopilot`
  exit 0; `i2c.py` AST assertion PASS (exactly `I2C_9DOF`, `MPR121`, `Motor_Shield_Hat`,
  `Motor_Shield_Hat_extend`, `Touch_Detector`); toggle call-form scan exit 0; backend suite
  **435 passed, 1 skipped**.

---
*Phase: 30-pi-repo-cleanup*
*Completed: 2026-08-10*
