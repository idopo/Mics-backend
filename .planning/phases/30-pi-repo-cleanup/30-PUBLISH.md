# Phase 30 — Publication Procedure

**Written:** 2026-08-10 (plan 30-08, the phase exit gate)
**Audience:** the user. **Every command below is run by you, not by an agent.**
**Source tree:** `/home/ido/pi-mirror` — verified clean by
`tools/check_tree_integrity.py --final` (exit 0) at the exit gate. Evidence:
`30-HARDWARE-VALIDATION.md`.

The agent's job ended at "a verified-clean tree plus the exact commands". Four things in this
phase are yours by rule, not by convenience:

1. **Revoking the Gmail app password** — an action in a third-party account.
2. **Creating the new repository** — the standing Pi rule forbids the agent running any git
   command in `pi-mirror`, including `status`.
3. **Cutting the `.28` branch** on the old repo — that repo lives on your machine.
4. **Running the Pi test suite and the live session** (plan 09).

---

## What the agent verified vs what remains

| Req | What it asserts | Status | Proven by |
|---|---|---|---|
| HYG-01 | Credential revoked and absent from the new repo's history | **YOURS — step 1 + step 3** | the revocation is an account action; the history proof needs a repo that does not exist yet |
| HYG-02 | The pilot starts and a real session completes on the rig | **YOURS — plan 09** | additionally blocked on clearing `ExtlinkDemo` off pilot 1 |
| HYG-03 | Plugin cluster removed, subclasses-before-base-classes | PROVEN | 61 files removed as one change; 13/11/9 importers all inside it |
| HYG-04 | An empty HANDSHAKE is a backend no-op | PROVEN | live `POST /pilots/1/tasks {"tasks": []}` → 200, zero writes |
| HYG-05 | Camera subtree gone from the Pi **and** from `hardware_libs` | PROVEN | guard F5; `hardware_libs` 9 → version 144, sha256-identical to disk |
| HYG-06 | Registry sweep collateral gone, `tasks/` compiles | PROVEN | guard F4 (`compileall`) |
| HYG-07 | Terminal-era tree gone | PROVEN | guard F1; AST import-graph closure proof |
| HYG-08 | Vendored/generated bulk gone | PROVEN | **1,097,505 B** excluding `.git` and `pilot/sounds/`, against an 8 MiB limit |
| HYG-09 | Root pytest config replaces `autopilot/pytest.ini` | PROVEN | collection produces no error; 382 tests collect |
| HYG-10 | No rig-specific config in `prefs.json` | PROVEN | guard F2 |
| HYG-11 | Dead commented-out code removed | PROVEN | 238 lines; `difflib` 33 deletes / 0 inserts / 0 replaces |
| HYG-12 | `Event_Dispatcher.py` drop counters survive | PROVEN | sha256 identical to the Wave 0 baseline |
| HYG-13 | Survival manifest intact | PROVEN | **zero drift** over all 30 protected paths (md5 **and** sha256) |
| HYG-14 | Toggles retired, both holds preserved | PROVEN | guard F3, with **inverted** assertions on both user-deferred blocks |

**12 PROVEN by automated evidence. 2 depend on you.**

---

## Step 1 — Revoke the credential. Do this FIRST.

`pilot/plugins/AssociationLearning.py:1323-1324` hardcoded a Gmail address and a 16-character
Google app password, used by `send_email()` over `smtplib`. The file is gone from the working
tree, and a full scan of the surviving tree (excluding `.git`) returns **0 hits** for either
literal.

**That is not remediation.** Deleting a file revokes nothing, and the credential is still live
inside `/home/ido/pi-mirror/.git` — 193 MB of history that no `git rm` can reach. Order matters:
if you publish first and revoke later, there is a window in which a working credential sits in a
repository you just pushed.

1. Google account → **Security** → **2-Step Verification** → **App passwords**.
2. Revoke the app password used by that script.
3. Record the date here and in `30-HARDWARE-VALIDATION.md` §3:

```
App password revoked at Google: ____________ (date)
```

---

## Step 2 — Create the new repository as a fresh `git init`

**Copy the cleaned tree to a new directory, excluding `.git`:**

```bash
NEW=/home/ido/mics-pilot          # pick your own name/path
rsync -a --exclude='.git' /home/ido/pi-mirror/ "$NEW"/
```

This is a **local copy on your machine**. It does not touch the Pi, and it carries **no
`--delete`**.

**Then initialise, commit and push:**

```bash
cd "$NEW"
git init
git add -A
git status                        # sanity: no .git/, no __pycache__, no *.pyc, no .pytest_cache
git commit -m "Initial commit: MICS pilot agent (Phase 30 cleaned tree)"
git remote add origin <same git account, new repo>
git branch -M main
git push -u origin main
```

### Never a clone. Never a filtered history.

- **`never git clone`** the mirror into the new repo. A clone carries the whole 193 MB history,
  credential included, which is the exact thing this procedure exists to avoid.
- **`never git filter-repo`, and never `git filter-branch`.** A history rewrite *looks* like it
  removes the credential and does not: it leaves reflogs, packed objects and unreachable-but-present
  blobs behind, and any fork or mirror taken before the rewrite keeps the original. The mirror's
  history has no other value here — nothing in it is worth the risk of carrying a live secret.

A fresh `git init` has exactly one commit and no ancestry. That is the property step 3 verifies.

---

## Step 3 — Prove HYG-01

```bash
git -C "$NEW" log -p --all | grep -c -F -f /home/ido/.hyg01-probe.txt
```

**Expect `0`.**

`/home/ido/.hyg01-probe.txt` holds the two literal strings — the address and the password — one per
line, no quotes, no blank lines. It was captured in Wave 0 **before** plan 04 deleted the file that
carried them, and it lives **outside every repository** deliberately, mode `600`. Its sha256 is
recorded in `30-HARDWARE-VALIDATION.md` §3; its contents are not recorded anywhere under
`.planning/`. Do not move or edit it — a blank line in that file would make `grep -F -f` match
every line and silently invert the assertion.

**Second, cheaper check:**

```bash
git -C "$NEW" log --oneline | wc -l
```

**Expect `1`.** A fresh `init` has exactly one commit, which is by itself the strongest available
evidence that no old history came along — stronger than the grep, because it cannot be defeated by
an encoding difference.

Paste both numbers into `30-HARDWARE-VALIDATION.md` §3 and flip **HYG-01 → PROVEN**:

```
git log -p --all | grep -c -F -f probe : ____   (expect 0)
git log --oneline | wc -l                : ____   (expect 1)
```

---

## Step 4 — Cut the `.28` branch on the old repo

On **your machine**, in the **old** repository, create a branch that holds the cleaned tree so the
current rig can check it out later.

```bash
cd /home/ido/pi-mirror
git checkout -b phase30-cleaned
git add -A
git commit -m "Phase 30: Pi repo cleanup (cleaned tree for .28)"
```

Then check that branch out on `132.77.72.28` when you are ready.

**Scope, stated so nobody assumes otherwise:**

- **`.28` is not migrated by this phase and is not reimaged.** It stays on the old repo and
  receives the cleaned code as a branch.
- **Converting `.28` to the new repo in place** — stripping git and users from that unit and
  enforcing the new repo there — is explicitly *deferred* ("not for now"). The OS configuration on
  that unit is worth preserving and a reimage would lose it.
- **New units get a fresh OS image plus the new repo. You handle imaging — it is not scripted here
  and must not be.**
- **There is no rsync-based reconciliation step, deliberately.** `tools/sync_pi.sh` syncs only
  `autopilot/` and passes no `--delete`, so rsync could never remove the deleted files from `.28`.
  That is precisely why the topology is "branch checkout on `.28`, fresh image on new units".

### Before the first fresh image

`requirements.txt` ends with two **deliberately unpinned** entries:

```
adafruit-circuitpython-mpr121
adafruit-circuitpython-motorkit
```

They are live runtime deps of `hardware/i2c.py` (`import adafruit_mpr121` at `:577`,
`from adafruit_motorkit import MotorKit` at `:671`) that were undeclared until this phase —
**MPR121 is the licker sensor**, not an optional extra. Every other entry in that file is pinned to
a version resolved on the rig's Python 3.7.3, so pinning these from the dev host would be a guess.
**Resolve them during the first fresh-image install and write the versions back.** Until then the
repo is not provisioning-complete.

---

## Step 5 — Before the rig proof (plan 09 blocker)

**HYG-02 cannot pass until `ExtlinkDemo` is off pilot 1.**

The Phase 18 demo fixture (module 62, `role: router_bind`, `required: true`) is still assigned to
toolkit 100 and configured on pilot 1, so every real session there either preflight-fails or hangs
the full 30 s timeout — for reasons that have nothing to do with this phase. A TCP echo listener on
the dev host at `132.77.73.125:5597` is a second standing dependency.

Teardown procedure: `18-HARDWARE-VALIDATION.md` §3. Rows to remove: module 62, lib 177, pilot
config 21, task def 434.

---

## Known consequences

Things that are now true because of this phase, that nobody will be warned about at runtime.

### 1. Eight toolkits dispatch to a class the Pi can no longer load

Plan 04 deleted `pilot/plugins/elastic_test.py` with the rest of the plugin tree. Verified against
the live DB at the exit gate (read-only; **no rows were modified**):

```
task_toolkits with locked_state_source = 'elastic_test.py':
  88 elastic_test · 89 new_toolkit · 92 bbb · 93 ccc
  96 inbar_toolkit · 97 inbar · 98 jhjh · 99 asd

available_locked_states id 24 (pilot 1): task_filename='elastic_test.py' -> class_name='elastic_test'

bound dev protocols: 51 "new_protocol_made_with back" (last run 2026-05-03)
                     52 "dasdad"                      (never run)
                     54 "cccfda"                      (last run 2026-05-13)
                     55 "fffddd"                      (last run 2026-05-14)
```

`GET /toolkits/{id}/dispatch-class` (`api/routers/toolkit_dispatch.py:135-150`) reads
`locked_state_source`, looks the filename up in `available_locked_states`, and returns
`class_name` for the Pi to instantiate. It will keep returning `elastic_test`.

**The failure mode is the point, not the fact.** The lookup is pure-DB, so **nothing errors in the
backend** — the class only fails to load at dispatch, on the Pi. And the Pi has **no `TASK_ERROR`
emitter**: `pilot.py:609` catches a failed START, sets state IDLE and reports nothing. So starting
one of those four protocols leaves the run sitting `running` **for ever**, with no diagnostic
anywhere. Anyone who hits this will experience it as "the session just hangs".

**Two corrections, so the exposure is not over-read:**

- **Protocol 10 `lkjhg` is not evidence.** It has a step named `elastic_test` and it did run on
  2026-07-27 — but its `task_definition_id` is **NULL**, so it dispatches through the legacy
  `task_type`-by-name path, not through `locked_state_source` at all. The most recent run through
  *this* path is **2026-05-14**.
- **The live research protocols are unaffected.** 56 `sourceless`, 57 `test_int` and 58 `ext_demo`
  all use `source_less_toolkit` → NULL `locked_state_source` → `mics_task`. Verified at the exit
  gate.

**Deliberately not fixed.** User decision, 2026-08-10: document, do not do DB surgery. No `UPDATE`,
no soft-delete, no `is_hidden`. This is a repo-cleanup phase and the rows are pre-existing dev
debris. The backend has **no prune path** on the handshake either — HYG-04 proved that and accepts
it — so the stale rows will keep appearing in the UI with no signal the Pi stopped reporting them.

Related, same cause, materially weaker: six further `available_locked_states` rows
(`RecordingBox`, `Free_Water`, `GoNoGo`, `Nafc`, `DLC_Hand`, `DLC_Latency`) went stale with plan
05. **Zero toolkits reference them**, so nothing dispatches through them.

### 2. Three behavioural changes go to the rig unproven

Everything else in the phase is subtractive. These three moved behaviour and are the rig proof's
watch-list:

| Change | Before | After |
|---|---|---|
| `l_start` START dispatch (plan 06) | `if 'child' in value.keys(): … else: …` | unconditional `autopilot.get_task(value['task_type'])`. The `else` body was byte-for-byte the unconditional form, so the surviving path is exact — but it is still a change on the dispatch path. |
| `Solenoid.dur_from_vol` (plan 07) | An **escaping `KeyError`** — the calibration was keyed `L`/`C`/`R` while the hardware is `VALVE1`–`VALVE4`, and the handler re-raised inside its own `except` | A logged `TypeError` → the documented default LUT `y = 3.5x + 2`. An improvement, and still a behaviour change. |
| `i2c.py` after the `MLX90640` surgery (plan 05) | — | `MPR121`'s `board` / `busio` / `adafruit_mpr121` imports survive by AST-span cutting. `py_compile` cannot prove this. **Only a real lick can.** |

### 3. The published repo has no rig configuration

`pilot/prefs.json` ships with `TERMINALIP=CHANGE_ME_terminal_ip` and `NAME=CHANGE_ME_pilot_name`,
no `SUBJECT`, and no `PORT_CALIBRATION`. `pilot/{data,logs,viz,calibration,protocols}/` ship empty
behind `.gitkeep`. A unit that clones this and boots without setting the two placeholders will not
reach the orchestrator. That is intentional — see `README.md`.

The pin map, `BASEDIR`/`REPODIR`/`VENV` and the `PI_HOST` defaults in `tools/*.sh` were **kept on
evidence**, not overlooked; the reasoning is in `30-HARDWARE-VALIDATION.md` §6.10 and §6.11.

---

## Known defects, deliberately not fixed

None of these was introduced by this phase. Each was found or confirmed during it and left, with a
reason.

| Defect | Where | Why it was left |
|---|---|---|
| **`Message.__setitem__` does not invalidate the serialization cache** — `# self.changed=True` is commented at `message.py:111` while `serialize()` short-circuits on `if not self.changed and self.serialized` (`:199`). Mutating a `Message` after one serialization can put **stale bytes on the wire**. | `autopilot/autopilot/networking/message.py` | **`Message` is user-designated do-not-touch (2026-08-10).** Real, and it belongs to its own phase where it can be changed against a rig proof. The sweep removed comments only; the live code is byte-identical. |
| **`hardware_state` is read live and has almost no writer** — read at `gpio.py:439` and at `logging_utils.py:95` (on **every** logged hardware event), but the only live write is `gpio.py:877`; the code that maintained it is the commented `state_changing_methods` block at `logging_utils.py:59-77`. | `hardware/gpio.py`, `utils/logging_utils.py` | **Same directive.** The commented block is the only surviving description of how the attribute was meant to be maintained, so it was kept rather than swept. |
| **NTP enable / clock-freeze call sites are commented out** while the methods stay live. A regression, not a decision — NTP stepping the clock mid-task is material on a rig that timestamps behavioural events to the millisecond. | `core/pilot.py:1071-1082` | **User-deferred 2026-08-10**; you have taken it on separately. The guard's F3 is **inverted** to assert the block stays present *and* commented, so a future sweep cannot eat it. |
| **`_handshake_watchdog` swallows its exception** — `except Exception: print("")`. | `networking/station.py:1270-1283` | **User-deferred 2026-08-10.** The retry is already live and the watchdog re-arms every 10 s, so restoring the commented `logger.*` lines recovers no behaviour — and on this rig log files are 0 bytes by design, so `logger.*` is the wrong channel anyway. F3 is inverted here too. |
| **`LOAD_HARDWARE_LIBS` fails silently during a run** — `mics_task.py:1589` imports `autopilot.autopilot.core.pilot`, which does not resolve, so `receive_hardware_libs()` raises `ModuleNotFoundError` and the exception dies unhandled in the `Net_Node` listen thread. Only the no-task-running path works. | `tasks/mics_task.py:1589` | Deferred **by name** in `30-CONTEXT.md`. The guard holds it as a `known_dangling` exemption with an **inverted** assertion — the reference must still be present *and* still fail to resolve — so this phase cannot silently repair it. Undercuts the mechanism the whole hardware-centralization arc rests on; deserves its own phase. |
| **No `TASK_ERROR` emitter on the Pi** — `pilot.py:609` catches a failed START, sets IDLE, reports nothing. | `core/pilot.py:609` | The single largest silent-failure mode in the system, and the reason HYG-02's acceptance test is a live session rather than an import check. Restoring it is a behavioural change. |
| **`i2c.py:819`'s `except(e):` on an undefined name** — MPR121 init failures raise `NameError`. | `hardware/i2c.py` | `i2c.py` is off-limits under TRIGA-12. |
| **`pilot.py` calls the undefined `get_hardware_class`** — `STREAM_VIDEO` raises. | `core/pilot.py` | Out of scope. |
| **No process keeps `hardware_libs` in sync with the Pi files.** This phase had to make the same `i2c.py` edit twice by hand. | DB ↔ disk | Restated **without** the "already 6 bytes apart" claim that has been repeated through the phase docs: that was `length()`-characters vs disk-bytes, three em-dashes, and the copies were byte-identical. The general concern stands; the cited instance was a measurement artifact. |
| **GUI-only deps still in `requirements.txt`** — `npyscreen`, `PySide2`, `shiboken2`, `pyqtgraph`. Dead weight now that the Terminal is gone, and `npyscreen` is the very package whose absence makes `autopilot` unimportable on the dev host. | `requirements.txt` | Removing them is a real improvement and **out of scope for a cleanup phase**. Logged, not done. |
| **`autopilot/README.md` still links removed modules** — `autopilot.core.terminal`, `.gui`, `.subject`, `viz`. | `autopilot/README.md` | `.md` is not in the guard's scan suffixes; it is upstream's README and belongs to whoever owns that decision. The **root** `README.md` was rewritten by this phase. |
| **`available_locked_states` spelling drift** — DB `AppetitveTaskReal.py` vs disk `AppetitiveTaskReal.py`, `Generalization.py` vs `Genralization.py`, `Blink.py` vs `blink.py`. | DB | Pre-existing: the backend never prunes handshake rows. Unaffected by this phase. |

---

*Phase 30 · `.planning/phases/30-pi-repo-cleanup/` · evidence in `30-HARDWARE-VALIDATION.md`*
