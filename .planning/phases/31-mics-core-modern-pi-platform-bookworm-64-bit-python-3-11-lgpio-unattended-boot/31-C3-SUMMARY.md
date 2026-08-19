---
phase: 31-mics-core-modern-pi-platform-bookworm-64-bit-python-3-11-lgpio-unattended-boot
plan: C3
subsystem: platform
tags: [pigpio, stock-client, clock, ntp, chrony, tree-integrity, tdd, plat-20, plat-22, plat-28, plat-33]

# Dependency graph
requires:
  - phase: 31-01
    provides: "tests/fakes/fake_pigpio.py (models the STOCK surface) + the conftest fixture; tools/pytest_delta.py"
  - phase: 31-03
    provides: "pigpio==1.78 pinned -- the stock upstream client this plan cuts the run path over to"
  - phase: 31-05
    provides: "deploy/chrony-mics.conf -- the PLAT-20 time source this plan asserts"
  - phase: 31-C1
    provides: "autopilot/utils/clock.py get_clock()/attach()/stop() and clock_guard.py's PatchedClientError"
  - phase: 31-C2
    provides: "the clock wired into both event paths; everything downstream of attach() already live"
provides:
  - "pilot.py's run path working against a STOCK pigpio client: pigpio.pi() with no arguments, no synchronize()"
  - "get_clock().attach(self.pi) -- the one place the MICS clock meets the live client, and PLAT-28's runtime guard"
  - "get_clock().stop() on the teardown path plus a defensive stop() before attach"
  - "tests/test_stock_pigpio_only.py (29 tests) -- the static patch-surface gate AND an executable run-path proof"
  - "tests/test_clock_block_removed.py (25 tests) -- the PLAT-22 deletion and the F3 retirement, with behavioural collateral-damage cases"
  - "a --final that exits 0 for the first time in Phase 31: F1-F6 all PASS"
affects: [31-C4, 31-08, 31-09]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Gate on CALL and KEYWORD forms, never bare tokens, when the forbidden vocabulary must legitimately survive as prose in the guard that forbids it"
    - "Count only UNCOMMENTED occurrences: a dead-comment sweep leaves the substring intact, so str.count cannot tell a live call from a disabled one"
    - "Extract and exec the production source under test rather than re-typing it -- a re-typed copy keeps passing after the original regresses"
    - "Pin a non-vacuity check to a NAMED commit, not to HEAD: a HEAD-relative check inverts its own meaning the moment the task commits"
    - "Assemble guard-triggering literals through .format() inside test fixtures, because the tree-wide guard scans the test file too"

key-files:
  created:
    - /home/ido/mics_core/tests/test_stock_pigpio_only.py
    - /home/ido/mics_core/tests/test_clock_block_removed.py
  modified:
    - /home/ido/mics_core/autopilot/autopilot/core/pilot.py
    - /home/ido/mics_core/tools/tree_integrity/final_checks.py
    - /home/ido/mics_core/tests/test_tree_integrity.py

key-decisions:
  - "The static gate checks CALL/KEYWORD forms plus a bare-name tier scoped to three documented owner files. The plan's <behavior> lists bare tokens; taken literally it forbids clock_guard.py from naming the patch surface it exists to refuse, and forbids gpio.py's C2 warning against reinstalling the fork. Corrected."
  - "`synchronize` is deliberately NOT in the bare-name tier: it is an ordinary English word (stim/sound/jackclient.py:101). Its patch forms are gated precisely as `synchronize(` and `.synchronize`."
  - "The kill_proc assertion is scoped to start_pigpiod's own AST body. The plan asks for a file-wide count, but start_jackd registers an identical hook, so a file-wide count stays GREEN after start_pigpiod's hook is stripped entirely. Verified by mutation M4."
  - "Added a defensive get_clock().stop() BEFORE attach(). attach() raises RuntimeError on an already-attached clock, so a run whose predecessor died before its teardown would be killed for a reason that is not its own -- and this plan's acceptance bar is the run path working."
  - "Folded the redundant inline `import pigpio` in run_task into the module-level import at :16 (which is unconditional, so the inline one was pure redundancy). Dropped `import subprocess`, orphaned by the NTP method deletion; left `import warnings`, which was already unused before this plan."
  - "tests/test_tree_integrity.py was edited although it is not in the plan's files_modified: it carried the retired guard's own unit test, which could only fail once the clause was gone. Rule 3."
  - "DEFERRED_CLOCK_BLOCK renamed NEUTRAL_PILOT and stripped: it held the tree's LAST copy of the clock-freeze block, kept only to satisfy the now-retired inverted assertion."

patterns-established:
  - "A behavioural collateral-damage test beside the textual one: mutations N3/N4 (dropping a TOGGLE_FORMS regex) were caught ONLY behaviourally, because the removed names survived in unrelated error-message strings"

requirements-completed: [PLAT-20, PLAT-22, PLAT-28]

# Metrics
duration: ~50min
completed: 2026-08-19
---

# Phase 31 Plan C3: Stock pigpio Cut-Over + PLAT-22 Resolution Summary

**The run path now works against a stock pigpio client, and that is proven by execution rather
than by assertion: `pilot.py`'s own run-start statements are extracted by AST and executed against
`tests/fakes/fake_pigpio.py` (which models the stock surface), and restoring either deleted call
site reproduces the exact live break — `TypeError: pi.__init__() got an unexpected keyword argument
'sync_ticks'` and `AttributeError: 'pi' object has no attribute 'synchronize'`. The Phase 30
clock-freeze deferral is resolved by being made unnecessary, its deliberately-inverted `--final` F3
guard is retired in the same change, and `--final` exits 0 for the first time in the phase. The
`pigpiod` spawn is preserved intact, PLAT-33 having been withdrawn.**

## Performance

- **Duration:** ~50 min
- **Tasks:** 2 completed (both TDD)
- **Commits:** 5 in `~/mics_core`
- **Tests added:** 54 (29 + 25), all green
- **Mutations run:** 20 (12 on Task 1, 8 on Task 2) — 20/20 caught after two test fixes
- **Files:** 2 created, 3 modified

## Task Commits

| # | Commit | What |
|---|---|---|
| 1 | `f01407a` | test(31-C3): the failing STOCK-pigpio static gate — **RED, 14 failed / 11 passed** |
| 1 | `3cf878b` | feat(31-C3): cut the run path over to a stock pigpio client — **GREEN, 28 passed** |
| 2 | `45b4e76` | test(31-C3): the failing proofs for retiring the F3 guard — **RED, 9 failed / 16 passed** |
| 2 | `63202e2` | feat(31-C3): retire the inverted `--final` F3 NTP guard |
| — | `b8b8fae` | fix(31-C3): rename the run-start comment header off the retired PLAT-22 anchor |

All on `phase-31-modern-pi-platform` in `/home/ido/mics_core`. Branch asserted before the first
commit. `main` untouched, nothing force-pushed, tag `phase-31-buster-before-arm` untouched.

**Plan 31-07 was executing concurrently on the same branch** (`deploy/install.sh`,
`deploy/uninstall.sh`, `tests/test_installer_paths.py`, `README.md`, `pilot/prefs.template.json`).
Every commit here staged files individually; no `git add .`. Plan 07's two in-flight RED tests
briefly showed in `pytest_delta.py`, so the delta was recomputed with
`--ignore=tests/test_installer_paths.py` to isolate C3's own contribution (**0 new failures**).
Plan 07 has since landed and the **unfiltered** `pytest_delta.py` also reports `new failures: 0`.

---

## The violation list, before and after

`tests/test_stock_pigpio_only.py` reports `FILE:LINE` for every hit. This is the before/after
evidence the plan asked for.

### Before (at C2's tip, `79bd267`)

**Patch call/keyword forms in use:**

```
autopilot/autopilot/core/pilot.py:943: [sync_ticks=]  self.pi = pigpio.pi(sync_ticks=True)
autopilot/autopilot/core/pilot.py:949: [synchronize(] self.pi.synchronize()
autopilot/autopilot/core/pilot.py:949: [.synchronize] self.pi.synchronize()
```

**Bare patch vocabulary outside the three documented owner files:**

```
autopilot/autopilot/core/pilot.py:503: raise RuntimeError("NTP did not synchronize in time")
autopilot/autopilot/core/pilot.py:943: self.pi = pigpio.pi(sync_ticks=True)
autopilot/autopilot/core/pilot.py:949: self.pi.synchronize()
autopilot/autopilot/core/pilot.py:954: self.logger.info("Global pigpio clock initialized and synchronized")
autopilot/autopilot/stim/sound/jackclient.py:101: * multiprocessing.Event objects are used to synchronize state within the client,
```

**A file re-enabling `systemd-timesyncd` (PLAT-20):**

```
autopilot/autopilot/core/pilot.py:491: subprocess.run(["timedatectl", "set-ntp", "true"], check=True)
```

**`pilot.py` forbidden-token counts:** `sync_ticks: 1, synchronize: 2, enable_ntp_and_wait: 2,
disable_ntp: 2, '# ---- CLOCK SETUP ----': 1, 'Freeze wall clock…': 1`

RED: **14 failed, 11 passed.**

### After

Every list above is **empty**. Counted, printed by the verify:

```
pilot.py forbidden-token counts: {'sync_ticks': 0, 'synchronize': 0, 'enable_ntp_and_wait': 0,
                                  'disable_ntp': 0, 'CLOCK SETUP': 0, 'Freeze wall clock': 0}
pigpio.pi() call sites and their args: ['']
get_clock().attach( occurrences: 1
gpio.clear_scripts(self.pi) occurrences: 2
files named pigpio.py in the repo: []
pigpio pins in requirements.txt: ['pigpio==1.78']
```

### Two corrections to the plan's gate specification

1. **The plan's `<behavior>` lists bare tokens** (`sync_ticks`, `synchronize(`, `.synchronize`,
   `ticks_to_timestamp`). Taken literally that gate cannot pass on a correct tree: `clock_guard.py`
   holds `PATCHED_ATTRIBUTES = ("synchronize", "ticks_to_timestamp")` and `PATCHED_KWARG =
   "sync_ticks"` — refusing a patched client is its entire job — and `gpio.py:13-14` carries C2's
   standing warning against reinstalling the fork. Implemented as **call/keyword forms** (C2's own
   precedent) plus a **second tier** asserting the bare vocabulary appears only in three documented
   owner files, each with a written reason.
2. **`synchronize` is excluded from the bare-name tier.** It is an ordinary English word:
   `autopilot/autopilot/stim/sound/jackclient.py:101` says "used to synchronize state within the
   client". A bare-token scan for it carries no signal. `sync_ticks` and `ticks_to_timestamp` have
   no such ambiguity and stay in the tier.

---

## Does the run path work against a STOCK pigpio client? Yes — and here is why that is not a claim

The success criteria ask this explicitly. **Yes**, with one bounded caveat named below.

`tests/test_stock_pigpio_only.py::test_pilot_run_start_executes_against_a_stock_pigpio_client`
locates `run_task` by AST, slices its statements from `self.pi = pigpio.pi(...)` through
`get_clock().attach(...)`, and **executes pilot.py's own source** against `fake_pigpio`, which
plan 01 built to model the **stock** client (its contract test asserts the patched names are absent
from it). The clock's heartbeat then reads the tick **through that client**:

```
stub.pi.connected           -> True
counters['heartbeat_missed'] -> 0
counters['last_bracket_ns']  -> > 0     (the heartbeat really read a tick, it did not no-op)
```

The mutation pass makes it non-vacuous. Restoring either deleted call site reproduces the live
break `31-REVISED-SCOPE.md` named:

| Mutation | Result |
|---|---|
| `pigpio.pi()` → `pigpio.pi(sync_ticks=True)` | `TypeError: pi.__init__() got an unexpected keyword argument 'sync_ticks'` |
| re-add `self.pi.synchronize()` | `AttributeError: 'pi' object has no attribute 'synchronize'` |

Extraction rather than re-typing matters: a re-typed copy of those lines would keep passing after
`pilot.py` regressed, which is the exact failure mode the module exists to catch.

### The remaining reason it would still not run, and it is not this plan's

**The only thing between here and a working rig is hardware provisioning, not code.** Specifically:

1. **Not executed on a Pi.** `pilot.py` cannot even be imported on the dev host (`import pigpio` at
   `:16` is unconditional and pigpio is deliberately not installed — plan 01 kept it out of
   `requirements-dev.txt`). The fake reproduces the **client API**; it does not reproduce `pigpiod`,
   DMA sampling, or a real 1 MHz counter. **C4's soak is what closes this**, and C2 already listed
   the four things it must establish (tick wrap in situ, heartbeat across a quiet stretch, re-fit
   ppm against a real counter, `edge_clock_fallbacks()` plateauing).
2. **A pre-calibration window is expected and is correct.** `attach()` starts the heartbeat, but
   `TickMapping` needs `min_span_s = 60 s` **on the tick axis** before it will fit. Until then
   `observe()` raises `ClockNotReady`, every edge is honestly marked `"software"`, and
   `gpio.edge_clock_fallbacks()` counts them. That is designed behaviour, not a break — but C4 must
   read the counter as *plateauing*, not as *zero*.
3. **The venv on the card must actually carry the stock client.** `requirements.txt` pins
   `pigpio==1.78`, and this plan asserts the pin survives, but nothing here can see the deployed
   `site-packages`. If someone reinstalls the fork, `get_clock().attach()` raises
   `PatchedClientError` **loudly at run start** — which is the point of PLAT-28 — rather than
   silently producing wrong timestamps. The read-only SSH commands below confirm it.

Nothing on that list is a defect introduced or left by this plan.

---

## PLAT-33 was WITHDRAWN 2026-08-17 — the `pigpiod` spawn is PRESERVED

`self.init_pigpio()`, the `init_pigpio()` method and `external.start_pigpiod()` are **byte-identical
to their state at C2's tip**. Counted evidence, printed by the verify:

```
pilot.py pigpiod-spawn preservation counts:
  {'self.init_pigpio()': 1, 'def init_pigpio(': 1, 'external.start_pigpiod()': 1}
external/__init__.py fail-safe hook counts:
  {'def start_pigpiod': 1, 'atexit.register': 2, 'signal.signal(signal.SIGTERM': 2, 'proc.kill()': 2}
```

**`autopilot/autopilot/external/__init__.py` has a ZERO-LINE DIFF, and that is the intended
outcome, not an omission.** `git diff 79bd267..HEAD -- autopilot/autopilot/external/__init__.py` is
empty. The file is in this plan's `files_modified` only so the gate can read it and assert it is
intact.

The gate's assertion is **stronger than the plan asked for, deliberately**. The plan specifies a
file-wide count of `atexit.register` / `signal.signal(signal.SIGTERM` / `proc.kill()`. Those each
appear **twice** — `start_jackd` registers an identical hook — so a file-wide count stays GREEN
after `start_pigpiod`'s hook is stripped **entirely**. The test extracts `start_pigpiod`'s own AST
body and asserts the hook is inside it. **Mutation M4 confirms this**: removing the hook from
`start_pigpiod` alone, leaving `start_jackd`'s, is caught.

The gate also asserts **no** `deploy/pigpiod-mics.conf` and no `deploy/*.{service,conf}` mentioning
`pigpiod`, scoped to unit and drop-in files so plan 07's `deploy/install.sh` may legitimately
apt-install the `pigpio` package.

### The stated reason for the withdrawal does not hold, and the code says so instead of repeating it

The plan's prose describes `start_pigpiod()`'s `kill_proc` hook as the rig's **output fail-safe** —
"it kills the daemon when the session ends, and killing it drops every output". **Verified false on
2026-08-19 by direct read of `external/__init__.py:52-60`**, for three independent reasons:

1. `subprocess.Popen('sudo ' + launch_pigpiod, shell=True)` — `proc` is the **shell wrapper**, not
   `pigpiod`. Killing the shell does not kill its child.
2. `pigpiod` **daemonises** (no `-g` flag), detaches, and is reparented to init. Even the correct
   PID would be the wrong process by the time the hook runs.
3. It runs under `sudo`, so an unprivileged `proc.kill()` could not signal it anyway.

The daemon therefore already outlives the pilot today — which is precisely the failure mode a
systemd unit was said to introduce. **This is PRE-EXISTING and OUT OF SCOPE**; per the plan it was
not fixed and `start_pigpiod` was not deleted over it. **The withdrawal stands by user instruction**
and the code is preserved unchanged. The discrepancy is recorded here rather than propagated: the
test's failure message says *"preserve it whether or not it fires"*, and the full analysis plus a
suggested real fail-safe is logged in `deferred-items.md`.

### The `PIGPIOARGS` / `PIGPIOMASK` item no longer exists

An earlier draft of plan 05 handed C3 a two-sources-of-truth problem. **PLAT-33's withdrawal
deleted it:** there is no `pigpiod` drop-in, the pilot still assembles the daemon's arguments from
`prefs.json` at `external/__init__.py:39-50`, and `prefs.json` is the only copy. Nothing to decide,
nothing to reconcile. A reader of plan 05's older text should stop looking.

---

## PLAT-22: the deferral is RESOLVED, not dropped

Phase 30 deliberately **inverted** F3's NTP assertion on 2026-08-10
(`30-HARDWARE-VALIDATION.md` §6.7, HYG-14). Inverted, it required the clock-freeze block to be
present *in commented form*, so HYG-11's dead-comment sweep could not eat something the user had
deferred rather than abandoned. That guard did its job: the moment Task 1 deleted the block,
`--final` failed **loudly** with exactly the four violations it was written to raise.

```
VIOLATION: F3 (HYG-14): core/pilot.py no longer carries the commented self.enable_ntp_and_wait()
VIOLATION: F3 (HYG-14): core/pilot.py no longer carries the commented self.disable_ntp()
VIOLATION: F3 (HYG-14): core/pilot.py lost the clock-block comment '# ---- CLOCK SETUP ----'
VIOLATION: F3 (HYG-14): core/pilot.py lost the clock-block comment '# Freeze wall clock…'
FAILED: 4 violation(s)
```

**The block existed for a good reason, and that reason is gone.** A wall-clock jump corrupted the
patched client's *estimated* tick-to-wall-clock mapping, so the pilot froze the wall clock for the
duration of a task. C1 and C2 replaced that estimate with a `CLOCK_MONOTONIC`-derived timeline: a
clock step can no longer move an interval, and chrony's discipline now touches only the derived UTC
field, which it **improves**. NTP running normally is the *point* (PLAT-20), not a risk. So the
deferral is resolved **by being made unnecessary** — and because the guard and the thing it guarded
must go together or `--final` fails forever, both went in one change.

That paragraph is written into `final_checks.py` at the deletion site (naming PLAT-22, citing
`30-HARDWARE-VALIDATION.md` §6.7, and stating *"resolved, not dropped"*), so the rationale lives in
the code and not only in a summary nobody re-reads.

**Retired:** `NTP_CALLS`, `CLOCK_COMMENTS`, `def _ntp_violations` and its
`violations += _ntp_violations(text)` call site. **Untouched:** everything else in `f3_toggles` —
the `open_file` absence, the whole HOLD 1 `_handshake_watchdog` block, its `_uncommented(body)`
assertion, its bare `print("")`, and all three `TOGGLE_FORMS`. The single permitted comment edit
reworded the HOLD 1 cross-reference from *"exactly like `_ntp_violations` above"* to *"as the
retired PLAT-22 NTP check once was"*.

**Non-vacuity, pinned to a commit rather than to HEAD.** `git show 79bd267:…/final_checks.py`
carries `{'def _ntp_violations': 1, '+= _ntp_violations(': 1, 'NTP_CALLS': 2, 'CLOCK_COMMENTS': 2}`.
The plan suggests reading HEAD; that inverts its own meaning the moment this task commits, so the
test pins C2's tip, which is stable forever.

**The bare string `_ntp_violations` deliberately survives** in the deletion-site note and is
deliberately **not** gated — a bare-string gate could not pass on a correct implementation. A
companion test asserts it is still present, so the two-form gate reads as a choice rather than an
oversight.

---

## `--final` per-F-check verdict — clean for the first time in Phase 31

`python3 tools/check_tree_integrity.py --final` → **exit 0**, captured at `/tmp/final31_c3.txt`:
`OK: 39 closure members, 30 protected files, 1 known-dangling exemptions held, 0 violations`.

| Check | Verdict | Note |
|---|---|---|
| **F1** `f1_bulk` | **PASS** | `MUST_BE_GONE` trees absent, tree within the 8 MiB budget. Phase 30 / plan 02 work, already landed |
| **F2** `f2_prefs` | **PASS** | `pilot/prefs.template.json` carries no `SUBJECT`, no top-level `PORT_CALIBRATION`, no `HARDWARE.UNREAL` |
| **F3** `f3_toggles` | **PASS** | Failed with 4 violations after Task 1's deletion, by design. Retired by Task 2. Its five surviving clauses were then re-proven behaviourally |
| **F4** `f4_tasks_compile` | **PASS** | `compileall` over `autopilot/autopilot/tasks` |
| **F5** `f5_cameras` | **PASS** | `cameras.py` gone, no surviving `MLX90640` / `hardware.cameras` reference |
| **F6** `f6_json_parses` | **PASS** | every surviving `.json` parses |

**No remaining failure belongs to Phase 30's exit criteria or to any other phase.** Before this
plan `--final` had failed throughout Phase 31 on F3 alone (the inverted assertion); F1, F2, F4, F5
and F6 were already green from plans 02/03/05/06/07.

**One self-inflicted F3 violation, found and fixed here — worth recording because it is a trap for
the next test author.** `f3_toggles` scans **every** `.py` in the tree and exempts only `SELF_PATHS`.
The behavioural collateral-damage test writes a synthetic `station.py` containing all three toggle
forms, so writing them as **literals** made `--final` report *this test file* as a surviving toggle:

```
VIOLATION: F3 (HYG-14): touch constant toggle survives in tests/test_clock_block_removed.py: set_cdc_manual(0x3f)
VIOLATION: F3 (HYG-14): opto pulse toggle survives in tests/test_clock_block_removed.py: pulse_and_notify(self.OG_TRIGGER
```

Fixed by assembling the fixture through `.format()` so the names never appear in call position. A
first attempt using string concatenation still tripped the opto regex, whose `[^)]*` spans the
concatenation — noted in a comment so the next person does not repeat it.

---

## Line counts

| File | Before (`79bd267`) | After | Δ |
|---|---|---|---|
| `autopilot/autopilot/core/pilot.py` | 1062 | **1056** | **−6** |
| `tools/tree_integrity/final_checks.py` | 240 | 225 | −15 |
| `tests/test_tree_integrity.py` | 584 | 551 | −33 |
| `tests/test_stock_pigpio_only.py` | — | 484 | new |
| `tests/test_clock_block_removed.py` | — | 219 | new |

`pilot.py` shrank by 6 net: **−20** for the two orphaned NTP method definitions, **−4** for the
clock-freeze comments, **−1** for `synchronize()`, **−1** for the redundant inline `import pigpio`,
**−1** for the orphaned `import subprocess`, offset by **+21** for the `get_clock` import, the
`attach()`/`stop()` calls, the reworded log line and the rationale comments. The net figure is small
because the deletions were replaced with an explanation of why they were deleted — which is the
right trade at a site three separate plans have now misread.

## Verification (all fresh, this run)

| Gate | Result |
|---|---|
| `pytest tests/test_stock_pigpio_only.py` | **29 passed** |
| `pytest tests/test_clock_block_removed.py` | **25 passed** |
| `pytest tests/test_tree_integrity.py` | **29 passed** (was 30; one retired with its guard) |
| `tools/pytest_delta.py` (unfiltered) | **`new failures: 0`**, exit 0 |
| delta isolated from concurrent plan 07 | 152 failures, **NEW: [] , fixed: []** |
| `tools/check_tree_integrity.py --strict` | `39 closure members, 30 protected, 0 violations`, exit 0 |
| `tools/check_tree_integrity.py --final` | **exit 0, 0 violations** — first clean `--final` of the phase |
| `tools/pulse_timing/py37_gate.py` | exit 0 on **34** closure members (unchanged — no import lost) |
| plan `<verification>` steps 1, 1b, 2, 3, 4, 5, 6, 7 | all pass |
| `git diff 79bd267..HEAD -- autopilot/autopilot/external/__init__.py` | **empty** (expected) |
| `pigpio` installed on the dev host | **no**, and not in `requirements-dev.txt` |

### Mutation pass — 20 mutations, 20 caught (after fixing two real gaps)

**Task 1 (12):**

| # | Mutation | Caught by |
|---|---|---|
| M1 | restore `pigpio.pi(sync_ticks=True)` | 4 cases, incl. the executed run-path proof |
| M2 | delete `get_clock().attach(...)` | `test_pilot_attaches_the_mics_clock_to_the_live_client` |
| M3 | delete `self.init_pigpio()` (stale PLAT-33) | `test_pilot_still_calls_init_pigpio_exactly_once` |
| M4 | strip `kill_proc` from **`start_pigpiod` only** | `test_start_pigpiod_still_registers_its_kill_proc_hook` |
| M5 | delete a `gpio.clear_scripts` call | `test_both_live_clear_scripts_calls_survive` |
| M5b | **comment out** a `clear_scripts` call | same — after the fix below |
| M6 | monkey-patch `pigpio` from a production module | `test_no_production_module_monkey_patches_...` |
| M7b | delete **only the teardown** `get_clock().stop()` | `test_the_heartbeat_is_stopped_on_the_teardown_path_specifically` |
| M8 | re-add `deploy/pigpiod-mics.conf` | `test_no_pigpiod_systemd_unit_or_dropin_exists` |
| M9 | vendor a `pigpio.py` | `test_no_pigpio_py_is_vendored_anywhere_in_the_repo` |
| M10 | **comment out** `get_clock().attach(...)` | `test_pilot_attaches_the_mics_clock_to_the_live_client` |
| M11/M12 | restore either patch call site | the executed run-path proof, with the real exception text |

**Two mutations ESCAPED on the first pass, and both were real defects in my test:**

- **M5 escaped** because `str.count("gpio.clear_scripts(self.pi)")` cannot tell a live call from
  one that a sweep merely prefixed with `#` — the substring survives. Added `_live_count()`, which
  counts only uncommented lines. This is exactly the failure mode Phase 30's HYG-11 sweep created.
- **M7 escaped** because the gate asserted `get_clock().stop() >= 1` and there are **two**, doing
  different jobs. Replaced with an AST assertion that a `stop()` exists inside `run_task`'s
  `try/finally` **finalbody** specifically.

**Task 2 (8), all caught:**

| # | Mutation | Caught by |
|---|---|---|
| N1 | drop the unrelated `open_file` clause | textual **and** behavioural |
| N2 | drop the touch-constant `TOGGLE_FORMS` regex | textual **and** behavioural |
| N3 | drop the opto-pulse regex | **behavioural only** |
| N4 | drop the IR-beam regex | **behavioural only** |
| N5 | damage HOLD 1's `_uncommented(body)` | `test_the_hold_1_assertion_itself_is_intact` |
| N6 | delete the "resolved, not dropped" rationale | `test_the_deletion_site_records_why_...` |
| N7 | point HOLD 1's cross-reference back at the deleted function | `test_the_hold_1_cross_reference_...` |
| N8 | reintroduce `_ntp_violations` | `test_the_inverted_f3_ntp_machinery_is_gone` |

**N3 and N4 justify the behavioural test's existence.** The textual survivor check
(`count("OG_TRIGGER") >= 1`) stayed **green** after the regex was deleted, because the name still
appears in an unrelated error-message string. Only building a synthetic tree that trips each clause
and asserting each still fires can distinguish a live assertion from a dead constant.

---

## Deviations from Plan

### Auto-fixed

**1. [Rule 1 — Plan gate unimplementable as written] the bare-token patch scan**
- **Found during:** Task 1, writing the test.
- **Issue:** the plan's `<behavior>` gates the bare tokens `sync_ticks`, `synchronize(`,
  `.synchronize`, `ticks_to_timestamp`. That forbids `clock_guard.py` from naming the surface it
  exists to refuse (`PATCHED_ATTRIBUTES`, `PATCHED_KWARG`) and forbids `gpio.py`'s C2 warning
  against reinstalling the fork. It also false-positives on the English word "synchronize" at
  `stim/sound/jackclient.py:101`.
- **Fix:** call/keyword-form tier + a bare-name tier scoped to three documented owner files, each
  with a written reason; `synchronize` excluded from the bare tier and gated precisely instead.
- **Committed in:** `f01407a`

**2. [Rule 2 — Missing critical correctness] the `kill_proc` assertion was scoped too widely**
- **Issue:** `start_jackd` registers an identical hook, so the plan's file-wide count stays green
  after `start_pigpiod`'s hook is removed entirely — a gate that cannot fail for the reason it
  exists.
- **Fix:** scoped to `start_pigpiod`'s own AST body. Verified by mutation M4.
- **Committed in:** `f01407a`

**3. [Rule 2 — Missing critical correctness] a defensive `get_clock().stop()` before `attach()`**
- **Issue:** `MicsClock.attach()` raises `RuntimeError("this clock is already attached")`. A run
  whose predecessor died before reaching its `finally` would be killed at start for a reason that
  is not its own — on the very code path this plan exists to make work.
- **Fix:** an idempotent `get_clock().stop()` immediately before `attach()`, with the reason in a
  comment.
- **Committed in:** `3cf878b`

**4. [Rule 3 — Blocking] `tests/test_tree_integrity.py` carried the retired guard's own unit test**
- **Found during:** Task 2, immediately after retiring `_ntp_violations`.
- **Issue:** `test_f3_ntp_assertion_is_inverted_and_guards_the_clock_comments` asserts
  `f3_toggles` returns 2 and 4 violations for uncommented / swept fixtures. With the clause retired
  it returns 0, so the test could only fail. **The file is not in this plan's `files_modified`**,
  but it is not protected, and the guard and its test must be retired together or `pytest_delta.py`
  reports a new failure.
- **Fix:** deleted the test, leaving a comment naming C3, PLAT-22 and the replacement
  (`tests/test_clock_block_removed.py`). Also renamed its `DEFERRED_CLOCK_BLOCK` fixture to
  `NEUTRAL_PILOT` and stripped it: it was a verbatim copy carried **only** to satisfy the retired
  inverted assertion, and it held the tree's **last** copy of the clock-freeze block.
- **Committed in:** `63202e2`

**5. [Rule 1 — my own test defects, found by mutation] two escaped mutations**
- `str.count` could not see a `clear_scripts` call that a sweep merely commented out → added
  `_live_count()`.
- `get_clock().stop() >= 1` stayed green when only the **teardown** stop was deleted → replaced
  with an AST assertion scoped to `run_task`'s `finally` body.
- Neither invariant was claimed proven until the mutation failed deterministically.

**6. [Rule 1 — self-inflicted, caught by the guard] the toggle literals in the new test file**
- Writing the three `TOGGLE_FORMS` strings as literals made `--final` report
  `tests/test_clock_block_removed.py` itself as a surviving toggle. Rebuilt via `.format()`. A
  concatenation-based first attempt still tripped the opto regex (`[^)]*` spans the concatenation);
  noted in a comment.

**7. [Rule 1 — self-inflicted] the replacement comment header still matched `CLOCK SETUP`**
- The plan's Task 1 verify checks the exact anchor `# ---- CLOCK SETUP ----` (0), but its final
  `<verification>` step 1 checks the looser `CLOCK SETUP`, which my new header
  `# ---- CLOCK SETUP (Phase 31 plans C1/C2/C3) ----` still matched. Renamed to
  `# ---- STOCK pigpio CLIENT + MICS CLOCK ----` and the gate now counts the loose form too. A
  header that merely *resembles* the retired anchor would read, to the next person grepping for it,
  as if the block were still there.
- **Committed in:** `b8b8fae`

**8. [Housekeeping] orphaned import removed**
- `import subprocess` became unused when the two NTP methods went (verified by counted read: 1
  occurrence, its own import). Removed. **`import warnings` was already unused before this plan** —
  pre-existing, left alone per the scope boundary.
- The inline `import pigpio` inside `run_task` was **folded** into the unconditional module-level
  import at `:16`, per the plan's "keep or fold — say which".

### Recorded, not fixed

**9. `start_pigpiod()`'s `kill_proc` hook cannot kill `pigpiod`.** Pre-existing, out of scope,
named as such by the plan. Full three-reason analysis and a suggested real fail-safe logged in
`deferred-items.md`. Nothing in this plan changed the code; the plan's prose describing it as a
working fail-safe is corrected above rather than propagated.

### Plan line numbers had shifted again (as C2 also found)

| Anchor | Plan says | Actually |
|---|---|---|
| `pilot.py` total | 1198 lines | **1062** (plans 02/03 ran first) |
| `pigpio.pi(sync_ticks=True)` | `:1073` | `:943` |
| `self.pi.synchronize()` | `:1079` | `:949` |
| `def enable_ntp_and_wait` | `:497` | `:490` |
| `def disable_ntp` | `:513` | `:506` |
| `def init_pigpio` | `:947-953` | `:814-820` |
| `violations += _ntp_violations(text)` | `:141` | `:150` |
| HOLD 1 cross-reference | `:150` | `:159` |

Every anchor was found by content, as the plan instructed. The plan's structural claim was correct:
Task 1 edited the interleaved region as a unit and took the clock-freeze comments with it, so Task
2's `pilot.py` assertions were trivially green and are documented as a **regression guard**, not as
that task's work.

---

## Read-only SSH commands for C4's pre-flight

**The agent did not and must not run these.** They confirm the stock-client property on the
provisioned card. Both must report `False` for the two patch attributes.

```bash
ssh -i ~/.ssh/pi_mics pi@<SPARE_IP> "/home/pi/.venv/mics/bin/python -c \"import pigpio,hashlib;print(pigpio.__file__);print(hashlib.sha256(open(pigpio.__file__,'rb').read()).hexdigest());print('synchronize' , hasattr(pigpio.pi,'synchronize'));print('ticks_to_timestamp', hasattr(pigpio.pi,'ticks_to_timestamp'))\""
ssh -i ~/.ssh/pi_mics pi@<SPARE_IP> "command -v pigpiod; pigpiod -v; systemctl is-enabled pigpiod; ps -o pid=,ppid=,args= -C pigpiod"
```

The second command's `systemctl is-enabled pigpiod` should report **not enabled / not found**:
PLAT-33 was withdrawn, so the pilot spawns the daemon and systemd does not supervise it. Its
`ps` output is also the direct check on the `deferred-items.md` finding — if `pigpiod`'s PPID is
`1` while no pilot is running, the daemon outlived the pilot and the `kill_proc` hook did not fire.

## Issues Encountered

- Two of my own test defects, both surfaced by mutation rather than by review (see Deviations 5).
- One self-inflicted `--final` violation from the new test file's fixture literals (Deviation 6) —
  which is itself evidence that F3 is live and scanning the whole tree.
- Concurrent plan 07 briefly polluted the delta gate; isolated, then confirmed clean unfiltered
  once 07 landed.

## User Setup Required

None.

## Next Phase Readiness

- **C4** can now run its acceptance gate against a tree whose `--final` is clean, and should read
  `get_clock().counters()` (fault counters only, per C1) plus `gpio.edge_clock_fallbacks()`. The
  four soak gaps C2 listed are unchanged and still open — this plan added the *attach*, not the
  hardware evidence.
- **Expect a non-zero `edge_clock_fallbacks()` early in any run.** The mapping needs `min_span_s`
  = 60 s on the tick axis before it will fit; edges before that are honestly software-stamped. C4
  must assert the counter **plateaus**, not that it is zero.
- **Plan 08** takes the Buster baseline on Python 3.7.3; the closure is still 34 members and
  `py37_gate.py` exits 0, so nothing was lost by `pilot.py` gaining the clock import.
- **Carried forward:** the `kill_proc` finding (new), plus C2's `board`/`adafruit-blinka` blocker
  and the `test_log_action_values.py` vs `log_value.py` contradiction — all in `deferred-items.md`.

---
*Phase: 31-mics-core-modern-pi-platform-bookworm-64-bit-python-3-11-lgpio-unattended-boot*
*Completed: 2026-08-19*

## Self-Check: PASSED

Both created and all three modified paths verified present on disk; `31-C3-SUMMARY.md` and the
appended `deferred-items.md` verified present; all 5 `~/mics_core` commit hashes (`f01407a`,
`3cf878b`, `45b4e76`, `63202e2`, `b8b8fae`) verified present via `git log --oneline --all`; branch
re-asserted as `phase-31-modern-pi-platform`; tag `phase-31-buster-before-arm` intact; working tree
clean. All counts re-measured this run: 29 + 25 = 54 passed, `test_tree_integrity.py` 29 passed,
`pytest_delta.py` `new failures: 0`, `--strict` 0 violations, `--final` **exit 0 / 0 violations**,
`py37_gate.py` exit 0 on 34 members.
