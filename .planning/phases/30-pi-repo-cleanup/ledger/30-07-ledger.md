# Phase 30 Plan 07 — Removal Ledger

**Scope:** HYG-10 — strip every rig-specific value out of the repo and ship `pilot/prefs.json` as a
template, with the four runtime directories emptied behind `.gitkeep`.

**Standing constraints honoured throughout:** no git command run in `/home/ido/pi-mirror`; no
`rsync`; nothing deployed to the Pi; no Python run on the Pi; no protect-listed file touched;
`--rebaseline` not run; `30-HARDWARE-VALIDATION.md` not edited (plan 06 runs in parallel, plan 08
merges); every load-bearing absence claim measured with an **unfiltered Python reader**, never with
`grep` alone.

**Execution note.** The destructive half of this plan was refused by the permission classifier and
was **executed by the coordinator in the main session**, not by the executor agent — a deliberate
change from waves 1–3, where plans 03 and 04 routed around the same refusal with Python
`shutil`/`os.remove`. Every number the coordinator reported was **re-measured independently** here
before being written down; each cross-check is noted inline.

---

## §A — HYG-10: `pilot/prefs.json` as a template

### A.1 Method — a values-only diff, established before editing

`json.dumps(d, indent=4)` **with no trailing newline** reproduces the original file byte-for-byte.
That was verified against the untouched file *first*, so the edit could go through `json` (deleting
keys cleanly, disposing of the `NaN` literals with them) while still producing a values-only diff
rather than a whole-file reformat.

| | Bytes | md5 | Top-level keys |
|---|---:|---|---:|
| Before | 16,966 | `e196deb142058b7e2256f20b91d04835` | 41 |
| After | 12,668 | `87f94d2ee191a455a1dfb92fafb5bba2` | 39 |

A reference copy of the pre-edit file is at
`/tmp/claude-1000/-home-ido-mics-backend/f7f15fc1-3bc1-4ae9-bb38-cff93181739b/scratchpad/prefs.before.json`.
Nothing is lost regardless: `tools/sync_pi.sh` never touches `pilot/` (§C.2), so the rig's real
prefs on the device are untouched by this phase.

### A.2 The diff

| Key | Before | After |
|---|---|---|
| `TERMINALIP` | `"132.77.73.125"` | `"CHANGE_ME_terminal_ip"` |
| `NAME` | `"pilot_raspberry_lior"` | `"CHANGE_ME_pilot_name"` |
| `PARENTIP` | `""` | **unchanged** — already empty; the plan templates it only if non-empty |
| `SUBJECT` | `"bp_s107_r471"` | **key deleted** |
| `PORT_CALIBRATION` | `{L,C,R} → {intercept: NaN, slope: NaN}` | **key deleted** |
| `HARDWARE.UNREAL` | 17 entries | **group deleted** |

The 17 deleted `UNREAL` entries: `AIR_PUFF`, `DOOR1`, `DOOR2`, `LED1`, `LED2`, `LED3`, `ODOR1–4`,
`VALVE1–4`, `AUDIO`, `MOTORIZED_REWARD`, `SERVER`. They carried two further non-lab IPs —
`10.0.0.4` (16 entries) and `172.18.75.238` (the `OSCSERVER`) — which went with the group. Plan 04
proved this block inert by reading `Task.init_hardware` (`tasks/task.py:175-187`), which iterates
the *task class's* `self.HARDWARE` and uses `prefs['HARDWARE']` only as a pin-argument lookup table;
a prefs group no surviving task class declares is never resolved and never imported.

**The `NaN` question is now moot.** `PORT_CALIBRATION` held the file's only `NaN` literals, which is
why the file was not strict JSON. Deleting the key removed them; the file is now strict-parseable.
No `NaN` was converted to `null`, so `prefs.py`'s `json.load` sees no change in form for any
surviving key.

**Untouched and verified still present after the edit:** `AUDIOSERVER` (still `false` — `stim/managers.py:17`
tests `AUDIOSERVER is not None`, and `False is not None` is True, which is why `sounds.py`/`base.py`
load at all), `CONFIG` (`""`), `AUTOPLUGIN`, `PLUGINDIR`, `PLUGIN_DB`, `MSGPORT`, `PUSHPORT`,
`PING_INTERVAL`, `HASH`, and all seven directory prefs (`DATADIR`, `LOGDIR`, `SOUNDDIR`, `VIZDIR`,
`PLUGINDIR`, `PROTOCOLDIR`, `CALIBRATIONDIR`). Surviving `HARDWARE` groups: `I2C`, `Mixer`,
`Timers`, `GPIO`, `Modules`.

### A.3 `BASEDIR` / `REPODIR` / `VENV` — kept, recorded as an install-path assumption

```
BASEDIR = /home/pi/Apps/mice_interactive_home_cage/pilot
REPODIR = /home/pi/Apps/mice_interactive_home_cage
VENV    = /home/pi/.venv/autopilot
```

Kept as-is. These encode the **deploy convention**, not this rig's identity — `tools/sync_pi.sh:21`
and `tools/deploy_pi.sh:22` both default `PI_APP_DIR` to the same `~/Apps/mice_interactive_home_cage`
path, so the convention is already asserted in two other places. **A new unit must match it**, or
must edit these three values plus the seven directory prefs derived from `BASEDIR`. Recorded here
rather than placeholdered, because `REPODIR` feeds `git_version()` at `prefs.py:599-606` and
`BASEDIR` feeds the boot-time `mkdir` of every `Scopes.DIRECTORY` pref — a `CHANGE_ME` in either
turns a working default into a guaranteed first-boot failure with no offsetting safety gain.

### A.4 Pin-value judgement call — **every pin value kept**, on evidence

HYG-10 says "no rig-specific pin values", and the plan draws the line at *cage wiring* (rig-specific
→ placeholder) versus *HAT-fixed* (not rig-specific → keep), with "if you cannot tell, keep it and
record it as undecided".

Rather than leave it undecided, the question was **measured** — using the two files this task was
about to delete, before deleting them. Every `pin` value in `HARDWARE` was diffed across all three
independently authored prefs files (`prefs.json`, `prefs_wsl.json`, `prefs_wsl_office.json`):

| Comparison | Differing pin values | Entries only in `prefs.json` | Entries only in the other file |
|---|---:|---|---|
| `prefs.json` vs `prefs_wsl.json` | **0** | `GPIO.AIR_PUF_S`, `GPIO.OG_TRIGGER`, `GPIO.TTL1`, `Modules.{Left_LED,Mid_LED,Right_LED,Solenoid}` | `GPIO.{DOOR1_MOTOR,DOOR2_MOTOR,MOTOR}` |
| `prefs.json` vs `prefs_wsl_office.json` | **0** | same 7 | same 3 |

**Zero differing pin values on every shared entry, across three separately maintained files.** That
is positive evidence the pin map is a property of the cage/HAT wiring convention rather than of this
individual unit. The membership differences are capability differences (this rig has an opto trigger
and a TTL line; the WSL rigs have door motors), not wiring differences.

**Decision: keep all 24 `GPIO` pin values and all 4 `Modules` pin values verbatim.** A placeholder
here would be a silent wrong-GPIO-fires bug on the rig — the exact failure class this phase exists
to prevent — with no offsetting benefit, since a new unit that *does* differ must edit the pin map
regardless of whether it starts from a real number or a placeholder.

**Nothing recorded as undecided.** `I2C` carries no pin numbers at all — its `id: 1/2/3` values are
Motor-Shield channel ids, fixed by the HAT. `Mixer` and `Timers` carry no pins.

Two `Modules` entries reuse `GPIO` pins (`Left_LED`/`Right_LED` → pin 11 = `GPIO.LED2`;
`Solenoid`/`Mid_LED` → pin 12 = `GPIO.LED3`). This looks like legacy duplication from the upstream
Autopilot `Modules` concept, but it is **pre-existing, identical in all three files, and outside
HYG-10's scope** — flagged, not changed.

### A.5 `IR1` and `OG_TRIGGER` survive by design — a finding for plan 08 §6

Both are **live pin declarations** and are present in the templated file:

```
HARDWARE.GPIO.OG_TRIGGER  group=TRIGGERS  pin=33  type=gpio.Digital_Out
HARDWARE.GPIO.IR1         group=IR        pin=15  type=gpio.Digital_In  trigger=B
```

HYG-14 retires the commented-out **toggles** that used them — `self.triggers['IR1']` and
`pulse_and_notify(…OG_TRIGGER…)`, both zero tree-wide since plan 04 — never the pins. The beam-breaks
still exist in the cage, and a `Digital_In` level change is still auto-logged as a `Hardware_Event`
by `@log_action`; that is precisely the user's stated rationale for deleting the dedicated
`detectedIR` callback rather than the hardware.

This plan's Task 1 gate therefore **asserts both are still present**, deliberately, rather than
merely leaving them alone.

**Finding for plan 08 §6:** 30-CONTEXT.md's claim that "no orphan `OG_TRIGGER` declaration survives"
is wrong in a third place. Plan 04 recorded the `RecordingBox.py` half (`:53`/`:54`, `:62`/`:63`);
this is the `prefs.json` half, and unlike `RecordingBox.py` it is **permanent, not pending** — no
plan in this phase or any later one should remove it. 30-CONTEXT.md already carries the CORRECTION
block; plan 08 should carry this concrete pair into §6 alongside plan 04's and plan 05's halves.

### A.6 Verdict

```
HYG-10 | PROVEN | pilot/prefs.json: TERMINALIP and NAME templated to CHANGE_ME_*; SUBJECT,
       | PORT_CALIBRATION and HARDWARE.UNREAL (17 entries incl. 10.0.0.4 / 172.18.75.238)
       | deleted; 16,966 B md5 e196deb1 -> 12,668 B md5 87f94d2e; file parses as strict JSON
       | (the NaN literals went with PORT_CALIBRATION). AUDIOSERVER still false, all 7 directory
       | prefs present, GPIO/I2C/Mixer/Timers/Modules intact incl. the live IR1 (pin 15) and
       | OG_TRIGGER (pin 33) declarations. prefs_wsl.json, prefs_wsl_office.json,
       | port_calibration.json and port_calibration_fit.json removed (27,624 B). Runtime dirs
       | pilot/{data,logs,viz,calibration} emptied (182 files, 79,487,931 B) behind .gitkeep and
       | gitignored. Tree-wide 132.77.* scan hits exactly the 4 allowlisted files (§C.1).
       | Guard --strict exit 0; Pi pytest delta 0 new failures.
```

---

## §B — Removals

### B.1 Files removed (criterion-3 checked first)

| File | Bytes | Criterion-3 result |
|---|---:|---|
| `pilot/prefs_wsl.json` | 13,522 | **0 references** to `prefs_wsl` anywhere in `pi-mirror` or `mics-backend` |
| `pilot/prefs_wsl_office.json` | 13,655 | **0 references** to `prefs_wsl_office`; also the last non-allowlisted carrier of `132.77.` (18 lines) |
| `pilot/port_calibration.json` | 330 | 4 references, all guarded or Terminal-owned — see B.2 |
| `pilot/port_calibration_fit.json` | 117 | 3 references, same — see B.2 |
| **Total** | **27,624** | |

Both WSL files were dev-host prefs for a Terminal workflow that no longer exists (`terminal/` went
in plan 03). They were read for the pin diff in §A.4 before removal — their last useful act.

### B.2 The calibration files ARE named by the surviving tree — why removal is still correct

The plan says: *"Confirm nothing in the surviving tree loads them by name before removing; if
something does, keep the file and replace its contents with a neutral template instead."* Something
does. The check therefore went further than "is it named" to "what happens when it is absent",
reading each consumer:

| Consumer | Line | Behaviour with the file absent |
|---|---|---|
| `autopilot/autopilot/prefs.py:611-612` | boot | Both reads guarded by `os.path.exists` (`:614` fit, `:622` raw). Neither branch is taken; `prefs['PORT_CALIBRATION']` is simply **never set**. This is the only path that runs at pilot boot. |
| `autopilot/autopilot/core/pilot.py:768` (`l_cal_result`) | Terminal msg | Guarded by `os.path.exists` at `:770`, falls back to `calibration = {}`, then **writes** the file with `w+` at `:786`. Self-healing; and its message source is the Terminal, removed in plan 03. |
| `autopilot/autopilot/prefs.py:720` (`compute_calibration`) | Terminal flow | Unguarded read, but only of a path the caller supplies or of `/usr/autopilot/port_calibration.json` — never of `pilot/`. Also imports `pandas`/`scipy` at call time. |
| `autopilot/autopilot/core/pilot.py:928` (`calibration_curve`) | Terminal flow | Unguarded read, reached only after `l_cal_result` has written the raw file. |

So **absence is the graceful branch on every path that runs**, and the two unguarded readers belong
to the Terminal-driven calibration workflow whose driver no longer exists. Templating the contents
instead — the plan's fallback — would have been strictly worse: a neutral template is a *lie* about
this cage's water ports, and `prefs.py:614` would load it in preference to nothing.

**What the files actually contained.** `port_calibration.json` held a **single** sample per port,
dated 2024-11-20 (`vol: 2.0, n_clicks: 1000, dur: 20`). `linregress` over one point is undefined,
which is exactly why `port_calibration_fit.json` read `{"intercept": NaN, "slope": NaN}` for all
three ports. **The calibration was already degenerate and could never have produced a valid
duration.**

### B.3 Removing `PORT_CALIBRATION` strictly improves `Solenoid.dur_from_vol`

The one consumer of the *key* (as opposed to the files) is
`autopilot/autopilot/hardware/gpio.py:1603-1612`, inside `Solenoid.dur_from_vol`
(`Solenoid_mics(Solenoid)` at `:1640`; call sites `tasks/task.py:238`, `:248`, `gpio.py:1560`):

```python
if self.calibration is None:
    try:
        self.calibration = prefs.get('PORT_CALIBRATION')[self.name]
    except KeyError:
        self.calibration = prefs.get('PORT_CALIBRATION')[self.name.replace('PORTS_', '')]
    except Exception as e:
        self.logger.exception(f'couldnt get calibration, using default LUT y = 3.5 + 2. got error {e}')
        self.calibration = {'slope': 3.5, 'intercept': 2}
duration = round(float(self.calibration['intercept']) + (float(self.calibration['slope']) * float(vol)))
```

**Before this change:** the calibration was keyed `L`/`C`/`R` while the hardware is named
`VALVE1`–`VALVE4`, so `[self.name]` raised `KeyError`; the handler at `:1607` then re-raised the same
`KeyError` at `:1609`, and an exception raised *inside* an `except` block does not fall through to
the sibling `except Exception`. The `KeyError` escaped. Had it not, `round(NaN)` would have raised
`ValueError` at `:1614`.

**After this change:** `prefs.get('PORT_CALIBRATION')` returns `None`, `None[self.name]` raises
`TypeError`, `except Exception` at `:1610` catches it, logs, and installs the documented default LUT
`y = 3.5x + 2`.

An escaping `KeyError` becomes a logged fallback to a documented default. **Recorded as a behaviour
change, and it is an improvement** — but it is a behaviour change, so it is stated plainly rather
than buried.

### B.4 Runtime directories — emptied, not deleted

All four keep the directory and gain a 0-byte `.gitkeep`. `CALIBRATIONDIR`, `DATADIR`, `LOGDIR` and
`VIZDIR` are `Scopes.DIRECTORY` prefs, and `prefs.py:479-485` lazily `mkdir`s each on first
`prefs.get()`. The `.gitkeep` exists so a fresh clone does **not depend on that mkdir succeeding** —
`prefs.py:485` swallows a failed mkdir into a `warnings.warn`, so the dependency would fail
*silently*. `CALIBRATIONDIR` matters most: `hardware/__init__.py:251` and `:278` read and write
`Path(prefs.get('CALIBRATIONDIR')) / cal_name` at runtime.

| Directory | Files removed | Bytes removed | Content |
|---|---:|---:|---|
| `pilot/data/` | 1 | 75,425,210 | `local.h5` — the abandoned HDF5 path; ES is the sole data path |
| `pilot/logs/` | 181 | 4,062,721 | 45 `.log` (45 of them 0-byte by design), 133 rotated `.1`–`.4`, and 3 `.csv` (see B.5) |
| `pilot/viz/` | 0 | 0 | already empty |
| `pilot/calibration/` | 0 | 0 | already empty |
| **Total** | **182** | **79,487,931** (75.8 MiB) | |

Independently re-measured against the coordinator's
`scratchpad/30-07-deletion-inventory.json` — all four rows match exactly, and both match the
executor's own pre-deletion walk.

This is rig data whose only other copies are on the Pi and in `~/pi-mirror.bak-2026-08-10`, and
`sync_pi.sh` never pulls it back (§C.2), so **this ledger is the record that it existed.**

`pilot/sounds/` was re-verified **byte-for-byte untouched**: 7 wavs, 2,326,388 B total, identical to
the pre-deletion measurement. Per-file md5s: `alt_blip8.wav` `0bdf7c99…`, `blip.wav` `5946f59e…`,
`blip8.wav` `fdcff5ba…`, `failedtrial.wav` `d3347759…`, `lick.wav` `86e87279…`, `successtrial.wav`
`f18b57ee…`, `valveopen.wav` `89d7d084…`. An unreferenced-looking wav can still be a live cue —
`mixer.py` resolves by bare filename through `SOUNDDIR`, so static analysis cannot prove one dead.

`pilot/protocols/` untouched (see §C.4). `pilot/plugins/` untouched, still `.gitkeep` only (plan 04).

### B.5 Preserved: three behavioural CSVs, on an explicit user decision

`pilot/logs/` held three files that were **not logs** — 2023-09-28 behavioural data from the
`AssociationLearning` task. They were flagged before deletion and, on the user's decision, copied to
a durable location **before** the purge, md5-verified identical on both sides:

| File | Bytes | md5 |
|---|---:|---|
| `/home/ido/pi-data-preserved/AssociationLearning250_28092023.csv` | 77,006 | `092ee14bac8cc35891e793bbdcdbf536` |
| `/home/ido/pi-data-preserved/AssociationLearningm256_28092023.csv` | 165,052 | `0ae4085d7851918c0dc8192a0334c4ac` |
| `/home/ido/pi-data-preserved/AssociationLearningm258_28092023.csv` | 122,534 | `498456eab824d5889a3e80740d1971ab` |
| **Total** | **364,592** | |

Re-verified independently here: all three present, sizes and md5s as above, and the total matches
the `.csv` subtotal of the pre-deletion `pilot/logs/` walk exactly (364,592 B of 4,062,721 B).

**`/home/ido/pi-data-preserved/` is now the durable copy**, independent of
`~/pi-mirror.bak-2026-08-10` (a working backup that will eventually be discarded) and of the Pi.

### B.6 `.gitignore`

Appended below the existing block (plan 02's `__pycache__/`, `.pytest_cache/`, `*.egg-info/`,
`*.deb`); **no existing line removed**:

```
# Runtime directories: the paths are Scopes.DIRECTORY prefs that prefs.py mkdirs at
# boot, so each directory must exist in a fresh clone but must ship empty.
pilot/data/*
!pilot/data/.gitkeep
pilot/logs/*
!pilot/logs/.gitkeep
pilot/viz/*
!pilot/viz/.gitkeep
pilot/calibration/*
!pilot/calibration/.gitkeep
```

---

## §C — Kept rig-specific values

Four files still carry `132.77.` after this plan. **Each is a recorded decision, not an exemption.**

### C.1 The four, with their decisions

**1–2. `tools/sync_pi.sh` and `tools/deploy_pi.sh` — the `PI_HOST` / `PI_SSH_KEY` defaults.**

```
tools/sync_pi.sh:11    #   PI_HOST      Pi hostname or IP (default: 132.77.72.28)
tools/sync_pi.sh:20    PI_HOST="${PI_HOST:-132.77.72.28}"
tools/sync_pi.sh:22    PI_SSH_KEY="${PI_SSH_KEY:-$HOME/.ssh/pi_mics}"
tools/deploy_pi.sh:21  PI_HOST="${PI_HOST:-132.77.72.28}"
tools/deploy_pi.sh:23  PI_SSH_KEY="${PI_SSH_KEY:-$HOME/.ssh/pi_mics}"
```

**User decision, 2026-08-10: KEEP.** *Reviewed and kept during Phase 30 planning; overridable via
env var.* Rationale, stated so a reader can disagree with it on the evidence:

- Both are `${PI_HOST:-…}` **overridable defaults**, not hardcoded constants. A new unit sets
  `PI_HOST=…` in its environment and never edits the file.
- Both are **developer tooling that runs on the developer's machine**, targeting a Pi over SSH.
  Neither is read by the pilot at runtime; neither ships to the device. A wrong value here fails
  loudly at `ssh`, not silently on the rig — unlike a wrong `TERMINALIP` in `prefs.json`, which is
  exactly the trap HYG-10 exists to prevent.
- `PI_SSH_KEY`'s `$HOME/.ssh/pi_mics` default is the same category and gets the same treatment.
- Blanking them to `CHANGE_ME` would break `sync_pi.sh` for the current user with no benefit to a
  future one, who must set the variable either way.

Per the plan, a one-line comment was added above each `PI_HOST=` default so the next reader does not
have to rediscover this:

```
# Lab default for the current rig, kept deliberately (Phase 30 / HYG-10 decision).
# Override for any other unit with e.g. PI_HOST=1.2.3.4 ./tools/sync_pi.sh
```

**Line-number drift caused by those comments** (a two-line insertion in each file): `sync_pi.sh`
`132.77.` lines moved 11, 18 → **11, 20**; `deploy_pi.sh` moved 19 → **21**. The plan's
`<verification>` prose still quotes the pre-comment numbers — see §C.3.

**3. `scripts/dev/extlink_smoke.py:21, 26, 30`** — `132.77.72.28` inside a usage docstring of a
developer smoke tool. **Plan 02 Task 1 §C explicitly orders this file KEPT.** Not a runtime value;
not read by anything.

**4. `tests/test_extlink_decoder.py:162, 166, 199, 231, 248, 255, 257`** — `132.77.9.9`, a test
fixture address (RFC-unassigned-looking but in the lab's range). **On the HYG-13 protect-list with a
sha256 baseline**, so no plan in this phase may edit it; doing so would break plan 08's zero-drift
manifest diff.

**Not a kept rig value: `tools/tree_integrity/final_checks.py:106-107`.** This file also matches
`132.77.`, but the match *is the assertion*:

```python
if "132.77." in text:
    violations.append("F2 (HYG-10): pilot/prefs.json still holds a rig-specific 132.77.* address")
```

That is F2 — the check that proves HYG-10. `tools/tree_integrity/` is already in the guard's own
`SELF_PATHS` tuple (`tools/tree_integrity/scan.py`), excluded from every string and path scan,
because a scanner that reads its own assertions as tree content can never go green. It belongs in
the **instrument**, not in this section's inventory of kept rig values.

### C.2 The tree-wide scan, and the correction it forced

Measured two ways, which agree:

```
$ grep -rln '132\.77\.' --include=*.json --include=*.py --include=*.sh \
      --exclude-dir=tree_integrity --exclude=check_tree_integrity.py .
./scripts/dev/extlink_smoke.py
./tests/test_extlink_decoder.py
./tools/deploy_pi.sh
./tools/sync_pi.sh
```

Unfiltered Python reader, same corpus, reporting line numbers and SELF_PATH status:

```
scripts/dev/extlink_smoke.py           lines=[21, 26, 30]
tests/test_extlink_decoder.py          lines=[162, 166, 199, 231, 248, 255, 257]
tools/deploy_pi.sh                     lines=[21]
tools/sync_pi.sh                       lines=[11, 20]
tools/tree_integrity/final_checks.py   lines=[106, 107]   <-- SELF_PATH (instrument, not tree content)
```

`.git` was checked and contains **0** files with those extensions, so it contributes nothing either
way.

**The gate initially failed on this host for a reason that is not a tree fact.** `grep` here is
rewritten to a compressing proxy, and the proxy **strips the `./` path prefix** from `grep -rl … .`
output — non-deterministically, since two runs in the same session rendered the same corpus once
with and once without it. The gate's exact-string equality therefore compared
`scripts/dev/extlink_smoke.py …` against the expected `./scripts/dev/extlink_smoke.py …` and failed
on four missing dot-slashes while the underlying set was already correct.

Re-run against `/usr/bin/grep` directly, bypassing the proxy, the equality is `True` and the whole
Task 2 gate exits 0. **Nothing in the tree was changed to make it pass and the assertion was not
weakened** — the measurement path was corrected, exactly as the standing rule about this host's
compressing proxy requires ("every load-bearing claim must come from unfiltered output"). The
unfiltered Python reader above had already produced the same four-file set independently.

**Practical note for plans 08 and 09:** any gate on this host that string-compares `grep` output
should invoke `/usr/bin/grep` explicitly, or compare sets rather than strings. This is the second
distinct way the proxy has corrupted a Phase 30 measurement — the first was rendering a matching
line blank (30-CONTEXT.md's `Camera` correction).

**The gate had to be corrected a third time.** The plan's `<automated>` gate was a plain `grep -rl`
outside the guard, so it did not inherit `SELF_PATHS` and its exact-set equality against four files
was unsatisfiable — the measured set was five. The only ways to force four would have been to
obfuscate or delete the guard's own `132.77.` literal (weakening F2, the very assertion that proves
HYG-10) or to delete a file plan 02 orders kept. Both forbidden.

**Resolution (coordinator, 2026-08-10):** add `--exclude-dir=tree_integrity
--exclude=check_tree_integrity.py` to the gate, keeping the allowlist an **exact four-file set** and
keeping the assertion about *tree content* rather than about the instrument. This is consistent with
plan 01's `SELF_PATHS` and plan 03's `request_helpers` gate. The alternative considered and
rejected — widening the allowlist to five — would have conflated an instrument with an inventory of
kept rig values.

This is the same failure shape the phase has now corrected three times: **two files → four →
four-with-the-instrument-excluded.** Each time the fix was to assert the allowlist actually intended,
never to weaken the check or delete live code to reach zero.

### C.3 Finding for plan 08 — the `<verification>` prose was not amended with the gate

`30-07-PLAN.md`'s `<automated>` gate (line 395) and the Task 2 action text (lines 366, 370-379) carry
the `--exclude-dir` correction. The `<verification>` block at lines **415-421** does not — it still
shows the unexcluded `grep -rn` form and still quotes the pre-comment line numbers (`sync_pi.sh`
11, 18; `deploy_pi.sh` 19).

Run verbatim today, that command returns **five** files, not four. It is prose, not an executed gate,
so nothing failed — but plan 08 should not transcribe it into the exit gate unamended. Correct form
and current line numbers are in §C.2 and §C.1.

### C.4 `pilot/protocols/` — a `Scopes.DIRECTORY` pref with no `.gitkeep`

`PROTOCOLDIR` is a `Scopes.DIRECTORY` pref, `pilot/protocols/` holds **0 files**, and an unfiltered
scan of every `.py`/`.sh` in the tree finds **no consumer of `PROTOCOLDIR`** other than its
declaration at `autopilot/autopilot/prefs.py:266` — the Terminal owned protocol distribution, and
`terminal/` went in plan 03. So a fresh clone will not carry the directory and will depend on
`prefs.py:479-485`'s lazy boot-time mkdir, the same condition this plan calls out for
`calibration/`.

**Not fixed here** — `pilot/protocols/` is outside this plan's `<files>` block, and the plan says to
leave it alone entirely. **Assigned to plan 08 as step 0d** (`pilot/protocols/.gitkeep` plus the
matching `.gitignore` pair). Safe by construction: nothing globs that directory at all.

### C.5 The `sync_pi.sh` assertion HYG-10 asks for

The plan's premise is that stripping `pilot/` costs nothing operationally because the device keeps
its own prefs. That is **quoted from the script**, not restated:

```
tools/sync_pi.sh:28   SOURCE_DIR="$MIRROR_ROOT/autopilot/"
tools/sync_pi.sh:51   rsync \
tools/sync_pi.sh:52       -avz \
tools/sync_pi.sh:53       --progress \
tools/sync_pi.sh:54-60    --exclude '__pycache__' '*.pyc' '*.pyo' '.git' '*.egg-info' 'dist/' 'build/' \
tools/sync_pi.sh:62       -e "ssh -i $PI_SSH_KEY -o StrictHostKeyChecking=no" \
tools/sync_pi.sh:63       "$SOURCE_DIR" \
tools/sync_pi.sh:64       "$PI_USER@$PI_HOST:$PI_APP_DIR/autopilot/"
```

The source is `autopilot/` **only**, the destination is `.../autopilot/`, and there is **no
`--delete`** in the invocation. So the device's `pilot/` — its real prefs, its real calibration, its
data and logs — is untouched by any sync, before or after this plan.

**Handover note, not work for this phase:** the eventual `.28` cutover (deferred in 30-CONTEXT.md)
delivers the new repo onto a *preserved* OS rather than a fresh image, so it must **assert** this
rather than rely on it — i.e. confirm the device's `pilot/prefs.json` still holds the real
`TERMINALIP`, `NAME` and pin map before the branch checkout, and confirm the checkout does not
replace it with this template.

---

## §D — Gates

| Gate | Result |
|---|---|
| `json.load(pilot/prefs.json)` | parses (strict JSON — no `NaN` left), 39 keys |
| Task 1 `<automated>` gate, verbatim | `prefs OK` + `--strict` exit 0 |
| Task 2 `<automated>` gate, verbatim (amended form) | exit 0 — via `/usr/bin/grep`; see §C.2 for why the proxied `grep` reported a false failure |
| `python3 tools/check_tree_integrity.py --strict` | exit 0 — `40 closure members, 30 protected files, 1 known-dangling exemptions held, 0 violations` |
| Pi pytest delta (30-01-SUMMARY command) | `new failures: 0`, exit 0 |
| `132.77.` tree-wide scan | exactly the 4 allowlisted files (§C.2) |
| `pilot/sounds/` | 7 files, 2,326,388 B — byte-for-byte unchanged |
| Preserved CSVs | 3 files at `/home/ido/pi-data-preserved/`, md5s re-verified |

**0 assertions weakened. 0 protect-listed files touched. `tree_protect_list.json` unedited.
`--rebaseline` not run. `30-HARDWARE-VALIDATION.md` not edited.**

The guard's `--final` **F2** check — which asserts exactly the four conditions §A.2 delivers — goes
from red to green with this plan. It was red from plan 04 onward by design, as plan 04's summary
recorded; that is now discharged.

---

## §E — Carry-forward for plan 08

1. **§6 correction:** `pilot/prefs.json` keeps `HARDWARE.GPIO.IR1` (pin 15) and
   `HARDWARE.GPIO.OG_TRIGGER` (pin 33) **permanently**. Carry alongside plan 04's `RecordingBox.py`
   half and plan 05's. 30-CONTEXT.md's "no orphan `OG_TRIGGER` declaration survives" is wrong in
   three places, of which this is the only *permanent* one.
2. **Step 0d:** add `pilot/protocols/.gitkeep` + the matching `.gitignore` pair (§C.4).
3. **Do not transcribe** `30-07-PLAN.md`'s `<verification>` lines 415-421 into the exit gate — they
   predate the `--exclude-dir` correction and the `PI_HOST` comment insertion (§C.3).
4. **`HYG-10 | PROVEN`** verdict line for `30-HARDWARE-VALIDATION.md` is in §A.6.
5. **Kept rig-specific values** (§C.1) belong in the published repo's README or a `CONFIGURING.md`,
   not only here — a new unit's operator needs to know about `PI_HOST`, `CHANGE_ME_terminal_ip`,
   `CHANGE_ME_pilot_name` and the `/home/pi/Apps/mice_interactive_home_cage` install-path assumption
   (§A.3).
6. **Behaviour change recorded:** `Solenoid.dur_from_vol` now falls back to the default LUT instead
   of raising `KeyError` (§B.3). Worth a line in the rig proof's watch-list even though it is an
   improvement.
