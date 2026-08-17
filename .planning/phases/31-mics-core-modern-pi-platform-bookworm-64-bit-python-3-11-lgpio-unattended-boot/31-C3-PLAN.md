---
phase: 31-mics-core-modern-pi-platform-bookworm-64-bit-python-3-11-lgpio-unattended-boot
plan: C3
type: execute
wave: 6
depends_on: ["31-C2", "31-05"]
files_modified:
  - /home/ido/mics_core/autopilot/autopilot/core/pilot.py
  - /home/ido/mics_core/autopilot/autopilot/external/__init__.py
  - /home/ido/mics_core/tools/tree_integrity/final_checks.py
  - /home/ido/mics_core/tests/test_stock_pigpio_only.py
  - /home/ido/mics_core/tests/test_clock_block_removed.py
autonomous: true
requirements: [PLAT-20, PLAT-22, PLAT-28]
must_haves:
  truths:
    - "The pilot connects to a STOCK pigpio client and would refuse to run against a patched one"
    - "The two patch-only call sites that RAISE on stock pigpio are gone, so the run path works again"
    - "Nothing in the tree monkey-patches pigpio, and no patched pigpio.py is vendored anywhere"
    - "The pilot STILL spawns pigpiod, deliberately — PLAT-33 was withdrawn, and start_pigpiod()'s kill_proc hook is the rig's output fail-safe"
    - "The deferred clock-freeze block is gone AND the inverted --final F3 guard that required it is retired in the same change"
    - "NTP is allowed to run normally, because timestamps no longer come from an estimated tick-to-wall-clock mapping"
    - "The MICS clock is attached to the live client at run start, so both event paths have a clock to read"
  artifacts:
    - path: "/home/ido/mics_core/tests/test_stock_pigpio_only.py"
      provides: "Static gate: no Autopilot pigpio patch, no vendored client, no monkey-patching — and the pigpiod spawn provably PRESERVED"
      min_lines: 40
      contains: "sync_ticks"
    - path: "/home/ido/mics_core/tests/test_clock_block_removed.py"
      provides: "Static gate: the clock-freeze block, its orphaned methods and its inverted guard are all gone, and the REST of f3_toggles survives"
      min_lines: 30
    - path: "/home/ido/mics_core/autopilot/autopilot/core/pilot.py"
      provides: "Stock pigpio.pi() plus MicsClock.attach(); no sync_ticks, no synchronize(), no clock-freeze block — start_pigpiod and init_pigpio survive intact"
      contains: "attach"
  key_links:
    - from: "pilot.py's run-start client init"
      to: "autopilot.utils.clock.get_clock().attach(self.pi)"
      via: "the one place the clock meets the live client, which is also the PLAT-28 runtime guard"
      pattern: "attach"
    - from: "the deleted clock-freeze block"
      to: "final_checks.py f3_toggles"
      via: "the _ntp_violations machinery retired in the same commit, or --final fails loudly"
      pattern: "def _ntp_violations"
---

<objective>
Stage 3, part 3. Cut over to stock pigpio and close the Phase 30 clock deferral by making it
unnecessary.

Purpose: `31-REVISED-SCOPE.md` §2 established that `sync_ticks`, `synchronize()` and both
`ticks_to_timestamp` implementations are **Autopilot patches, not upstream**, and that 100% of the
clock defects live in those ~50 patched lines. The `pigpiod` C daemon — the DMA sampler, the
genuinely hard part — is stock and is not implicated. C1 and C2 replaced what the patch did. This
plan removes the patch's remaining footprint from the tree and makes the run path work against a
stock client again.

**Two of the three things here are deletions, and one of them is currently a landmine.** Verified
2026-08-17 by direct read of the 1198-line `pilot.py`:

- `:1073 self.pi = pigpio.pi(sync_ticks=True)` and `:1079 self.pi.synchronize()` are **patch-only**.
  Stock pigpio has neither, so `pi(sync_ticks=True)` raises `TypeError`. That is a **live break** on
  the run path from the moment plan 03's stock pin is installed — bounded (it fires only when a task
  starts, which plan 09 never exercises) but real, and `31-REVISED-SCOPE.md` names it. **This plan is
  what closes it.**
- `:1069-1084` interleaves the live client init with the **commented** clock-freeze block
  (`# ---- CLOCK SETUP ----` at `:1071`, `# self.enable_ntp_and_wait()` at `:1072`,
  `# Freeze wall clock so it never jumps during the task` at `:1081`, `# self.disable_ntp()` at
  `:1082`). PLAT-22's deletion.

**PLAT-33 WAS WITHDRAWN 2026-08-17 — `external.start_pigpiod()` STAYS. Read this before you touch
`pilot.py`.** An earlier draft of this plan deleted `:206 self.init_pigpio()`, the `init_pigpio`
method at `:947-953`, and `:949 external.start_pigpiod()`, on the grounds that plan 05's supervised
`pigpiod` unit replaced them. **The user reviewed that and reversed it.** `start_pigpiod()` registers
a `kill_proc` hook on `atexit` and `SIGTERM` (`external/__init__.py:54-59`) that **kills the daemon
when the session ends** — and because `pigpiod` is what actually drives the pins, killing it is what
**drops every output**. A systemd-supervised daemon would **outlive** a crashed pilot, leaving
`VALVE1-4` / `AIR_PUF` / `ODOR1-5` energised with nothing left to close them. The current design
fails safe; the supervised one would not, absent extra fail-safe work outside this phase.

So: **`:206` stays, `init_pigpio()` stays, `:949` stays, `init_pigpio()` is NOT emptied, and
`:947-953` survives intact.** Plan 05 ships no `pigpiod` drop-in and plan 07 enables no unit, so
there is nothing for this plan to assert about `deploy/` on that front either. A static gate in
Task 1 asserts the spawn is **present**, because the failure mode now is an executor deleting it
from a stale reading of PLAT-33.

**One thing this withdrawal deletes for free:** the `PIGPIOARGS`/`PIGPIOMASK` two-sources-of-truth
item plan 05 used to hand here. With no drop-in, `prefs.json` is the only copy. There is nothing to
decide and nothing to reconcile — the handoff is struck.

**PLAT-22 has a correction you must not skip.** An earlier framing said the clock-freeze deletion
happens "as a side effect of removing the pigpio lifecycle" under PLAT-16. **PLAT-16 is DEFERRED**
(`31-REVISED-SCOPE.md` §5) — the pigpio lifecycle is *not* being removed, pigpio stays. So this
deletion is **no longer a side effect of anything**. C3 must delete `pilot.py:1069-1082` explicitly
and on purpose, retire the `--final` F3 guard in the same change, and record why.

**And the reason is good, which is the part worth writing down.** The clock-freeze block exists
because a wall-clock jump corrupted the *estimated* tick-to-timestamp mapping. C1 and C2 replaced
that estimate with a monotonic-derived timeline, so freezing the wall clock is no longer necessary —
and NTP running normally is now the *point* (PLAT-20), because the derived UTC field is the only
thing chrony's discipline touches and it makes that field better. This is not a deferral being
quietly dropped; it is a deferral being **resolved by being made unnecessary**. Say it in those terms
in the code comment and in the summary. Phase 30 deliberately inverted the guard to protect this
block from a comment sweep; retiring that guard is a deliberate act with a named reason, not a
cleanup.

Output: a stock-only tree, a working run path, the clock attached at run start, and two static
gates — one that stops the patch surface coming back, one that stops the `pigpiod` spawn being
removed.
</objective>

<execution_context>
@/home/ido/.claude/get-shit-done/workflows/execute-plan.md
@/home/ido/.claude/get-shit-done/templates/summary.md
</execution_context>

<context>
@.planning/PROJECT.md
@.planning/ROADMAP.md
@.planning/STATE.md
@.planning/phases/31-mics-core-modern-pi-platform-bookworm-64-bit-python-3-11-lgpio-unattended-boot/31-REVISED-SCOPE.md
@.planning/phases/31-mics-core-modern-pi-platform-bookworm-64-bit-python-3-11-lgpio-unattended-boot/CONTEXT.md
@.planning/phases/31-mics-core-modern-pi-platform-bookworm-64-bit-python-3-11-lgpio-unattended-boot/31-C1-SUMMARY.md
@.planning/phases/31-mics-core-modern-pi-platform-bookworm-64-bit-python-3-11-lgpio-unattended-boot/31-C2-SUMMARY.md
@.planning/phases/31-mics-core-modern-pi-platform-bookworm-64-bit-python-3-11-lgpio-unattended-boot/31-05-SUMMARY.md
@.planning/phases/30-pi-repo-cleanup/30-HARDWARE-VALIDATION.md

**Read `31-REVISED-SCOPE.md` §2 and §5 first**, then `REQUIREMENTS.md`'s PLAT-22 in full — it carries
two dated corrections (the `:1071-1082` line range, and the "no longer a side effect" note) that
every earlier draft of this phase got wrong.

<repo_boundary>
ALL code changes land in `/home/ido/mics_core` on branch **`phase-31-modern-pi-platform`**.

<branch_guard>
**Assert the branch before committing anything.** All Phase 31 code lands on
`phase-31-modern-pi-platform` in `/home/ido/mics_core`, published to `origin` by plan 01. Before the
first commit of this plan, run `git branch --show-current` and confirm it is that branch — if it is
not, STOP and do not commit. Never `git checkout main`, never merge into `main`, never force-push,
and never push `main`. Integration to `main` is the user's decision after the C4 acceptance gate.
</branch_guard>

NEVER modify `/home/ido/mics-backend` source — only its `.planning/` documents.
</repo_boundary>

<pi_rules>
ABSOLUTE. These override anything else in this plan:
- **NEVER run git on the Pi. NEVER start or stop the pilot. NEVER run any Python file on the Pi.**
  Every hardware-side confirmation in this plan is a **read-only** SSH command handed to the user,
  or is deferred to C4. The agent runs nothing on any Pi.
- Pi log files are 0 bytes **by design**.
- **`Message` and `hardware_state` are OFF LIMITS**, including inside `pilot.py`.
- RTK-proxied grep can render a matching line blank. Every absence claim in this plan is a counted
  `python3 -c` printing `text.count(...)`, never a silent grep. This plan is almost entirely absence
  claims, so this rule is load-bearing here.
- **Do NOT `pip install pigpio` on the dev host.** Plan 01 kept it out of `requirements-dev.txt`
  deliberately.
</pi_rules>

<integrity_gate>
`cd /home/ido/mics_core && python3 tools/check_tree_integrity.py --strict` must exit 0 after EVERY
task. **NEVER `--rebaseline`.**

**None of this plan's five files is in the protected manifest** — verified 2026-08-17 against
`tools/tree_protect_list.json`. So no manifest edit is needed or permitted here; if `--strict` flags
a protected file, the task went outside its file list.

**`--final` is the other gate, and this plan is what makes it meaningful again.**
`python3 tools/check_tree_integrity.py --final` adds F1-F6. It has been expected to fail throughout
Phase 31 because F3's NTP assertion is **deliberately inverted** — it currently requires the
clock-freeze block to be present *in commented form*, so a comment sweep could not eat it
(`30-HARDWARE-VALIDATION.md` §6.7, HYG-14). Task 1 deletes the block, at which point `--final` fails
**loudly** — that is the guard working, not a bug. Task 2 retires it. Run `--final`, record the
per-F-check verdict, and do not chase failures that belong to Phase 30's exit criteria: name them
instead.
</integrity_gate>

<verified_deletion_map>
Verified by direct read on 2026-08-17 against the 1198-line `pilot.py`. **Plans 02 and 03 edit
`pilot.py` before this plan runs, so line numbers will have shifted — re-grep for the anchors, do
not trust the numbers.** Several of these were wrong in every pre-2026-08-17 draft; these are the
corrected ones.

| Anchor | Line (2026-08-17) | Disposition |
|---|---|---|
| `import pigpio` (module level) | `:16` | **KEEP.** PLAT-16 is deferred; pigpio stays. |
| `self.init_pigpio()` | `:206` | **KEEP.** PLAT-33 withdrawn 2026-08-17; the pilot still spawns its own daemon |
| `def enable_ntp_and_wait(self, timeout=30)` | `:497` | **DELETE the definition** if nothing calls it |
| `def disable_ntp(self)` | `:513` | **DELETE the definition** if nothing calls it |
| `def init_pigpio(self)` | `:947-953` | **KEEP, byte-identical.** Its body is `self.pigpiod = external.start_pigpiod()` (`:949`), a debug log and an `except ImportError`. It does **not** create the client, so nothing here conflicts with the stock-client cutover. PLAT-33 is withdrawn: the method is **not** emptied and the spawn is the rig's output fail-safe. A Task 1 gate asserts it is still present |
| `import pigpio` (inline, inside `run_task` at `:1056`) | `:1069` | KEEP or fold into the module-level import — say which |
| `# ---- CLOCK SETUP ----` | `:1071` | **DELETE** (PLAT-22 anchor) |
| `# self.enable_ntp_and_wait()` | `:1072` | **DELETE** (PLAT-22) |
| `self.pi = pigpio.pi(sync_ticks=True)` | `:1073` | **CHANGE to `pigpio.pi()`** — `sync_ticks=` is patch-only and raises `TypeError` on stock |
| the connect check | `:1075-1076` | **KEEP** |
| `self.pi.synchronize()` | `:1079` | **DELETE** — patch-only, `AttributeError` on stock |
| `# Freeze wall clock so it never jumps during the task` | `:1081` | **DELETE** (PLAT-22 anchor) |
| `# self.disable_ntp()` | `:1082` | **DELETE** (PLAT-22) |
| `self.logger.info("Global pigpio clock initialized and synchronized")` | `:1084` | **REPLACE** with a line describing what actually happened: stock client connected, MICS clock attached |
| `gpio.clear_scripts(self.pi)` | `:1089`, `:1171` | **KEEP — both.** Plan 13 was dropped, so the pigpio script machinery stays. Deleting these would break the pulse path. |
| `# gpio.clear_scripts()` (commented) | `:1189` | **LEAVE** — not this plan's business |

**Note the structural consequence, and be honest about it in the summary.** The clock-freeze comments
are *interleaved* with the live client init: `:1071` comment, `:1072` comment, `:1073` live,
`:1075-1076` live, `:1079` live, `:1081` comment, `:1082` comment. Task 1 edits that region as a unit
and therefore **takes the clock-freeze block with it**. Note that this region is ~120 lines below
`init_pigpio()` at `:947-953`, so nothing about it touches the spawn. So by the time Task 2 runs, its `pilot.py`
absence assertions are trivially green — they assert something Task 1 already did. That is fine and
it is not a reason to reorder: the assertions are still worth having as a regression guard, and
splitting a 16-line region across two tasks would be worse. **Task 2's remaining real work is not a
second deletion.** It is (a) retiring the F3 `_ntp_violations` machinery, (b) writing the
collateral-damage assertions proving the rest of `f3_toggles` survived, and (c) recording the
"resolved, not dropped" rationale. Task 2 must report it that way rather than claiming a deletion
Task 1 performed. The `:497`/`:513` method definitions are **570 lines away** from the block and are
**not** taken by Task 1 — they are Task 1's own explicit item.

**The positive work, which is easy to lose among the deletions.** Replacing `synchronize()` with
nothing would leave the pilot with a stock client and no clock at all. The replacement is one line:

```python
from autopilot.utils.clock import get_clock
...
self.pi = pigpio.pi()
# (connect check stays)
get_clock().attach(self.pi)   # starts the PLAT-29 heartbeat; refuses a patched client (PLAT-28)
```

`attach()` is C1's PLAT-28 runtime guard: it raises `PatchedClientError` if the loaded client carries
`synchronize` / `ticks_to_timestamp` / accepts `sync_ticks=`. That is what makes "stock pigpio" a
property the running system enforces rather than a claim in a requirements file. Add the matching
`get_clock().stop()` wherever the run tears down, and make it idempotent-safe (C1's `stop()` already
is).

**`external/__init__.py` — nothing is removed from it.** *(Rewritten 2026-08-17 with PLAT-33's
withdrawal; the earlier text asked you to decide whether `start_pigpiod` could be deleted.)* It stays
whole: `start_pigpiod` (`:31`), its `shutil.which('pigpiod')` gate (`:15`), and above all the
`kill_proc` hook on `atexit` and `SIGTERM` (`:54-59`) that kills the daemon at session end and
thereby **drops every output**. That hook is the rig's fail-safe and the reason the requirement was
withdrawn. Task 1 asserts all of it is present rather than deciding anything, and the expected diff
for this file is **zero lines**.

**`requirements.txt` is NOT edited here.** Plan 03 pinned the stock pigpio **client** (a pure-Python
`py3-none-any` wheel, on the wheel-check allow-list alongside `Adafruit-PureIO`). This plan
**asserts** that pin survives; it does not touch the file, which is also what keeps it out of plan
09's way.

**`deploy/` is NOT edited here.** Plan 05 wrote `chrony-mics.conf` and `journald-mics.conf`; plan 07
installs them; plan 09 proves them on hardware. This plan **asserts** the chrony drop-in exists and
says what PLAT-20 needs it to say. There is **no** `deploy/pigpiod-mics.conf` to assert — PLAT-33
was withdrawn, and a gate here asserts it is **absent**, because an executor re-adding it is the
concrete way this decision gets quietly undone.

**No `PIGPIOARGS`/`PIGPIOMASK` decision is owed here.** An earlier draft of plan 05 handed C3 a
two-sources-of-truth problem: with the pilot no longer spawning the daemon, `PIGPIOARGS` /
`PIGPIOMASK` in `prefs.json` would be inert while `deploy/pigpiod-mics.conf` was authoritative.
**PLAT-33's withdrawal deletes that problem.** There is no drop-in, the pilot still assembles the
daemon's arguments from `prefs.json` at `autopilot/external/__init__.py:39-50`, and `prefs.json` is
the only copy. Nothing to decide, nothing to reconcile, no comment to write. Say so in one line of
the summary so a reader of plan 05's older text does not go looking for the decision.

</verified_deletion_map>

<the_f3_guard>
## The `--final` F3 guard, and exactly how much of it to remove

In `tools/tree_integrity/final_checks.py`:

- `NTP_CALLS = ("self.enable_ntp_and_wait()", "self.disable_ntp()")` (~line 42)
- `CLOCK_COMMENTS = ("# ---- CLOCK SETUP ----", "# Freeze wall clock ...")` (~line 44)
- `def _ntp_violations(text)` at **`:49`**, and its call site `violations += _ntp_violations(text)`
  at **`:141`** inside `f3_toggles`

Delete the `_ntp_violations` machinery and its call. It is a whole-file substring search with no line
number, which is why it kept working after Phase 30 shifted the block from `:1137-1148` to
`:1071-1082`.

**There is a THIRD occurrence of the string `_ntp_violations`, and it is not part of the machinery.**
Verified 2026-08-17 by a counted read: `final_checks.py` contains **3** occurrences —
`:49` (the def), `:141` (the call) and **`:150`**, which is prose inside the comment on the
still-live **HOLD 1** `_handshake_watchdog` block: *"...so the assertion is INVERTED, exactly like
`_ntp_violations` above."* `<the_f3_guard>` says to leave that block alone, and it stays live.

So **the gate counts the two specific forms, never the bare string.** Assert
`fc.count('def _ntp_violations') == 0` and `fc.count('+= _ntp_violations(') == 0`. A bare
`fc.count('_ntp_violations') == 0` would be wrong twice over: it fails on `:150`'s cross-reference,
and it would also forbid the deletion-site comment this plan **requires** (which may well name the
retired function while explaining what was removed).

**One bounded comment edit is required at `:150`**, and it is the only line of the HOLD 1 block you
may touch: reword the cross-reference so it no longer points at a function that no longer exists —
e.g. *"the assertion is INVERTED, as the retired PLAT-22 NTP check once was."* The HOLD 1 assertion
itself, its `_uncommented(body)` logic and everything else in that block stay byte-identical, and
Task 2's collateral-damage assertions prove it.

**Leave the rest of `f3_toggles` alone.** It also asserts the `open_file` absence, the
`_handshake_watchdog` logging state, its bare `print("")`, and three toggle forms
(`set_cdc_manual(0x3f)`, `self.triggers["IR1"]`, `pulse_and_notify(...OG_TRIGGER)`). Those are
unrelated Phase 30 assertions and removing them would be collateral damage that nothing would catch
until a later phase wondered why a gate went quiet. `git diff` the file and read it before
committing; the collateral-damage test in Task 2 is what makes that reviewable rather than trusted.

At the deletion site, leave a comment recording: the assertion was inverted on 2026-08-10 because the
user deferred the NTP restoration; Phase 31 plans C1/C2 replaced the estimated tick-to-timestamp
mapping with a monotonic-derived timeline, so freezing the wall clock is no longer necessary and NTP
running normally is now wanted (PLAT-20); the deferral is therefore **resolved, not dropped**.

Cross-reference `30-HARDWARE-VALIDATION.md` §6.7, which documents the inversion. Cite it from
`31-C3-SUMMARY.md` so the two records connect.
</the_f3_guard>
</context>

<tasks>

<task type="auto" tdd="true">
  <name>Task 1: Stock client, MICS clock attached, clock-freeze block deleted — pigpiod spawn PRESERVED</name>
  <files>
    /home/ido/mics_core/autopilot/autopilot/core/pilot.py
    /home/ido/mics_core/autopilot/autopilot/external/__init__.py
    /home/ido/mics_core/tests/test_stock_pigpio_only.py
  </files>
  <behavior>
    `tests/test_stock_pigpio_only.py` is a **static** gate over the tree. It scans every `.py` under
    `autopilot/` and `pilot/`, excluding `tests/fakes/` (the fake deliberately models the stock
    surface and asserts the patch names are absent — that is plan 01's contract test, not a
    violation) and the tree-integrity guard's own `SELF_PATHS`. It reports `FILE:LINE` for every hit
    and fails on any of:

    - `sync_ticks` — the patch-only constructor keyword that raises `TypeError` on stock pigpio
    - `synchronize(` and `.synchronize` — the patch-only method
    - `ticks_to_timestamp` — both patch implementations
    - `get_current_tick` **outside** `autopilot/utils/clock.py` — the heartbeat is the only legitimate
      caller, and C1 owns it

    **`start_pigpiod` is NOT on that list, and its absence is deliberate.** PLAT-33 was withdrawn
    2026-08-17; the spawn is the rig's output fail-safe. The gate asserts the **opposite**: see the
    preservation cases below.

    **The preservation cases — these exist because the risk now runs the other way.** An earlier
    draft of this plan deleted the spawn under PLAT-33, so an executor working from a stale reading
    is the concrete failure mode. Assert, as separate cases:
    - `pilot.py` contains **exactly one** `self.init_pigpio()` call and **exactly one**
      `def init_pigpio(` definition.
    - `pilot.py` contains **exactly one** `external.start_pigpiod()` call, inside `init_pigpio`.
    - `autopilot/autopilot/external/__init__.py` still defines `start_pigpiod` and still registers
      the `kill_proc` hook: `atexit.register`, `signal.signal(signal.SIGTERM` and `proc.kill()` each
      appear at least once. **That hook is why PLAT-33 was withdrawn** — it is what closes the
      solenoids at session end — so a test that only checked the call site would miss the thing
      actually being protected.
    - There is **no** `deploy/pigpiod-mics.conf`, and no file under `deploy/` with suffix
      `.service` or `.conf` mentions `pigpiod`. (Scope it to unit and drop-in files:
      `deploy/install.sh` legitimately apt-installs the `pigpio` package.)

    It also asserts, as separate cases:
    - **No vendored client.** There is **no file named `pigpio.py`** anywhere in the repo. Count it.
      PLAT-28's headline is that no untracked venv file may carry behaviour; the repo-side half is
      that we do not vendor one either.
    - **No monkey-patching.** No production module assigns onto the pigpio module
      (`pigpio.<name> = `) and none writes `sys.modules['pigpio']`. `tests/` and `conftest.py` are
      exempt — plan 01's fixture does exactly that, on purpose, in the test environment only.
    - **The pin survives.** `requirements.txt` contains exactly one `pigpio` requirement line and it
      is not commented out. This plan does not edit the file; it proves plan 03's work was not lost.
    - **chrony, not timesyncd (PLAT-20).** `deploy/chrony-mics.conf` exists and contains no
      `makestep` (Debian ships it; restating it is how it silently diverges), and no MICS file
      re-enables `systemd-timesyncd`.

    And on `pilot.py` specifically:
    - zero occurrences of `sync_ticks`, `synchronize`, `enable_ntp_and_wait`, `disable_ntp`,
      `# ---- CLOCK SETUP ----`, `Freeze wall clock so it never jumps during the task`.
      **`init_pigpio` and `start_pigpiod` are NOT in this list** — they stay
    - **exactly one** `pigpio.pi(` call, with **no arguments**
    - **at least one** `get_clock().attach(` call
    - `gpio.clear_scripts(self.pi)` still appears **twice** — the pulse path is not being removed and
      a sweep that took these would break it silently
    - the file is **shorter** than it was before the task
  </behavior>
  <action>
    1. Write `tests/test_stock_pigpio_only.py` FIRST and watch it enumerate every current violation.
       That enumeration is the work list; paste it into the summary so the before/after is auditable.

    2. Apply `<verified_deletion_map>` to `pilot.py`, re-grepping every anchor rather than trusting a
       line number. In order:
       - **leave `self.init_pigpio()` (`:206`) and the `init_pigpio` method (`:947-953`)
         byte-identical.** PLAT-33 is withdrawn; the spawn stays. Do not empty the method, do not
         "tidy" its `except ImportError`, do not move it;
       - change `pigpio.pi(sync_ticks=True)` to `pigpio.pi()`, keep the connect check, delete
         `self.pi.synchronize()`;
       - delete the four clock-freeze lines;
       - add `get_clock().attach(self.pi)` immediately after the connect check, and a matching
         `get_clock().stop()` on the teardown path;
       - replace the `"Global pigpio clock initialized and synchronized"` log line with one that
         describes what now happens, naming the stock client and the MICS clock;
       - delete the `enable_ntp_and_wait` (`:497`) and `disable_ntp` (`:513`) definitions **after** a
         counted scan proves nothing calls them. If something does, stop and say so — that is a
         finding, not a blocker to route around.
       - **Do not touch** `gpio.clear_scripts(self.pi)` at `:1089`/`:1171`, the commented
         `# gpio.clear_scripts()` at `:1189`, or anything `hardware_state`-related.

    3. **`autopilot/external/__init__.py` is listed in this plan's files, but only so the gate can
       read it — expect a zero-line diff.** PLAT-33's withdrawal means `start_pigpiod` and its
       `kill_proc` hook stay exactly as they are. If you find yourself editing this file, stop and
       re-read the objective. (It remains in `files_modified` because C3 owns the assertion that it
       is intact; if you end the task with no change to it, say so in the summary — that is the
       expected outcome, not an omission.)

    4. There is **no** `PIGPIOARGS`/`PIGPIOMASK` decision to make. Plan 05's older text handed one
       here; the withdrawal deleted it. `prefs.json` is the only copy. Record that in one line of
       the summary so a reader of the old text does not go hunting.

    5. Report the before/after line count of `pilot.py`. It should shrink — by the four clock-freeze
       lines, `synchronize()`, and the two orphaned NTP method definitions, offset slightly by the
       `get_clock()` import, `attach()`, `stop()` and the replaced log line.

    6. Do **not** edit `requirements.txt`, `deploy/*`, `tools/tree_integrity/final_checks.py`,
       `Event_Dispatcher.py`, `gpio.py`, `task.py` or `logging_utils.py`. The first two belong to
       plans 03/05/07; the third is Task 2; the rest are C2's and are already correct.
  </action>
  <verify>
    <automated>cd /home/ido/mics_core && /home/ido/.venvs/mics_core_dev/bin/python -m pytest -q tests/test_stock_pigpio_only.py --tb=short && /home/ido/.venvs/mics_core_dev/bin/python -c "
import pathlib, re, sys
p = pathlib.Path('autopilot/autopilot/core/pilot.py').read_text()
counts = {k: p.count(k) for k in ('sync_ticks', 'synchronize',
                                  'enable_ntp_and_wait', 'disable_ntp',
                                  '# ---- CLOCK SETUP ----',
                                  'Freeze wall clock so it never jumps during the task')}
print('pilot.py forbidden-token counts:', counts)
bad = {k: v for k, v in counts.items() if v}
if bad:
    sys.exit('pilot.py still carries the patched-client / clock-freeze surface: %r' % bad)
# PLAT-33 WITHDRAWN 2026-08-17: the pigpiod spawn is the rig's output fail-safe and must SURVIVE.
keep = {k: p.count(k) for k in ('self.init_pigpio()', 'def init_pigpio(', 'external.start_pigpiod()')}
print('pilot.py pigpiod-spawn preservation counts:', keep)
if keep != {'self.init_pigpio()': 1, 'def init_pigpio(': 1, 'external.start_pigpiod()': 1}:
    sys.exit('the pigpiod spawn was altered; PLAT-33 was WITHDRAWN and start_pigpiod()\'s kill_proc hook is what closes the solenoids at session end: %r' % keep)
ext = pathlib.Path('autopilot/autopilot/external/__init__.py').read_text()
hook = {k: ext.count(k) for k in ('def start_pigpiod', 'atexit.register', 'signal.signal(signal.SIGTERM', 'proc.kill()')}
print('external/__init__.py fail-safe hook counts:', hook)
if not all(hook.values()):
    sys.exit('external/__init__.py lost part of the kill_proc fail-safe hook: %r' % hook)
pi_calls = re.findall(r'pigpio\.pi\(([^)]*)\)', p)
print('pigpio.pi() call sites and their args:', pi_calls)
if len(pi_calls) != 1 or pi_calls[0].strip():
    sys.exit('expected exactly one argument-free pigpio.pi() call; found %r' % (pi_calls,))
print('get_clock().attach( occurrences:', p.count('get_clock().attach('))
if p.count('get_clock().attach(') < 1:
    sys.exit('the MICS clock is never attached to the live client - the pilot would run with no clock at all')
print('gpio.clear_scripts(self.pi) occurrences:', p.count('gpio.clear_scripts(self.pi)'))
if p.count('gpio.clear_scripts(self.pi)') != 2:
    sys.exit('the two live clear_scripts calls must survive; the pigpio script pulse path is NOT being removed')
vend = [str(f) for f in pathlib.Path('.').rglob('pigpio.py')]
print('files named pigpio.py in the repo:', vend)
if vend:
    sys.exit('a pigpio.py is vendored in the repo; PLAT-28 forbids any local copy carrying behaviour')
req = pathlib.Path('requirements.txt').read_text()
pins = [l for l in req.splitlines() if l.strip() and not l.strip().startswith('#') and 'pigpio' in l]
print('pigpio pins in requirements.txt:', pins)
if len(pins) != 1:
    sys.exit('expected exactly one uncommented pigpio pin (plan 03 put it there); found %r' % (pins,))
dep = {f.name: f.read_text().count('pigpiod')
       for f in sorted(pathlib.Path('deploy').iterdir())
       if f.is_file() and f.suffix in ('.service', '.conf')}
print('pigpiod occurrences per deploy/ unit or drop-in:', dep)
if any(dep.values()) or pathlib.Path('deploy/pigpiod-mics.conf').exists():
    sys.exit('a pigpiod systemd unit or drop-in exists; PLAT-33 was WITHDRAWN and a supervised daemon would outlive a crashed pilot with solenoids energised: %r' % dep)
ch = pathlib.Path('deploy/chrony-mics.conf')
print('chrony drop-in exists:', ch.exists(), '| makestep occurrences:', ch.read_text().count('makestep') if ch.exists() else 'n/a')
if not ch.exists() or ch.read_text().count('makestep'):
    sys.exit('PLAT-20 chrony drop-in missing, or it restates Debian default makestep')
" && /home/ido/.venvs/mics_core_dev/bin/python tools/pytest_delta.py && python3 tools/check_tree_integrity.py --strict</automated>
  </verify>
  <done>`tests/test_stock_pigpio_only.py` passes; `pilot.py` carries zero occurrences of `sync_ticks`, `synchronize`, `enable_ntp_and_wait`, `disable_ntp` and both clock-freeze anchors, by counted assertion; `self.init_pigpio()`, `def init_pigpio(` and `external.start_pigpiod()` each still appear exactly once and `external/__init__.py`'s `kill_proc` fail-safe hook is intact (PLAT-33 withdrawn); there is exactly one argument-free `pigpio.pi()` call and at least one `get_clock().attach(`; both `gpio.clear_scripts(self.pi)` calls survive; no `pigpio.py` is vendored anywhere and nothing monkey-patches the module; the single `requirements.txt` pin and the chrony drop-in are asserted present and no `pigpiod` unit or drop-in exists; `pilot.py` is shorter; delta gate `new failures: 0`; `--strict` exit 0.</done>
</task>

<task type="auto" tdd="true">
  <name>Task 2: Retire the inverted --final F3 guard, and prove the rest of f3_toggles survived</name>
  <files>
    /home/ido/mics_core/tools/tree_integrity/final_checks.py
    /home/ido/mics_core/tests/test_clock_block_removed.py
  </files>
  <behavior>
    `tests/test_clock_block_removed.py` asserts, all by counted reads of text it loaded itself:

    - `pilot.py` contains none of `enable_ntp_and_wait`, `disable_ntp`, `# ---- CLOCK SETUP ----`,
      `Freeze wall clock so it never jumps during the task`. **These are trivially green because Task
      1 already did it** — see `<verified_deletion_map>`. They are kept as a regression guard, and
      the summary must describe them as such rather than as this task's deletion.
    - `tools/tree_integrity/final_checks.py` contains **no** `NTP_CALLS`, **no** `CLOCK_COMMENTS`,
      **no** `def _ntp_violations` and **no** `+= _ntp_violations(`. The guard and the thing it
      guarded go together, in one commit. **Count those exact forms, not the bare string
      `_ntp_violations`** — see `<the_f3_guard>`: the string legitimately survives in prose, and a
      bare-string gate cannot pass on a correct implementation.
    - The HOLD 1 cross-reference at `final_checks.py:150` was reworded so it no longer points at a
      deleted function, and the rest of that comment block plus its `_uncommented(body)` assertion
      are byte-identical. Assert the block's assertion is still present by name.
    - **The collateral-damage assertion, which is why this test exists rather than a bare grep:** the
      REST of `f3_toggles` survives. `open_file`, `_handshake_watchdog`, `set_cdc_manual`, `IR1` and
      `OG_TRIGGER` are all still referenced in `final_checks.py`. Those are unrelated Phase 30
      assertions; removing them would be silent damage that nothing else would catch.
    - `final_checks.py` still defines `f3_toggles` — the whole check is retired *of one clause*, not
      deleted.
    - The deletion site carries a comment containing `PLAT-22` and the word `resolved`, so the
      rationale lives in the code and not only in a summary nobody re-reads.
    - `python3 tools/check_tree_integrity.py --final` produces output (it did not crash) and reports
      **no** F3 NTP / clock-block violation.

    A separate case asserts the whole thing is not vacuous: `def _ntp_violations` **was** present in
    the file at the start of this task. Record the pre-edit `git show HEAD:tools/tree_integrity/final_checks.py`
    count in the summary, so "the guard is gone" is provably a removal rather than an assertion about
    something that was never there.
  </behavior>
  <action>
    1. Write the test first, including the survival assertions for the rest of `f3_toggles` and the
       non-vacuity record.

    2. In `final_checks.py`, delete `NTP_CALLS` (~`:42`), `CLOCK_COMMENTS` (~`:44`), the
       `def _ntp_violations` at `:49` and the `violations += _ntp_violations(text)` call at `:141`.
       Then reword the **one** cross-reference at `:150` per `<the_f3_guard>` so it does not name a
       deleted function. **Leave every other assertion in `f3_toggles` untouched, and leave the rest
       of the HOLD 1 block byte-identical.** `git diff` the file and read it before committing.

    3. Add the deletion-site comment from `<the_f3_guard>`: inverted 2026-08-10 because the user
       deferred the NTP restoration; C1/C2 replaced the estimated tick-to-timestamp mapping with a
       monotonic-derived timeline; freezing the wall clock is therefore unnecessary and NTP running
       normally is now wanted (PLAT-20); the deferral is **resolved, not dropped**.

    4. Run `--final` and record, **per F-check**, pass/fail and the reason, into the summary as a
       table. Do not chase failures that belong to Phase 30's exit criteria — name them and say which
       phase owns them. This is the first point in Phase 31 at which `--final` is meaningful again,
       so the table is the deliverable, not a footnote.

    5. Hand the user, in the summary, the **read-only** SSH commands that confirm the stock-client
       property on real hardware once C4's card is provisioned. The agent must not run them:
       ```bash
       ssh -i ~/.ssh/pi_mics pi@<SPARE_IP> "/home/pi/.venv/mics/bin/python -c \"import pigpio,hashlib;print(pigpio.__file__);print(hashlib.sha256(open(pigpio.__file__,'rb').read()).hexdigest());print('synchronize' , hasattr(pigpio.pi,'synchronize'));print('ticks_to_timestamp', hasattr(pigpio.pi,'ticks_to_timestamp'))\""
       ssh -i ~/.ssh/pi_mics pi@<SPARE_IP> "command -v pigpiod; pigpiod -v; systemctl is-enabled pigpiod; ps -o pid=,ppid=,args= -C pigpiod"
       ```
       Both must report `False` for the two patch attributes. C4's pre-flight runs them.
  </action>
  <verify>
    <automated>cd /home/ido/mics_core && /home/ido/.venvs/mics_core_dev/bin/python -m pytest -q tests/test_clock_block_removed.py tests/test_stock_pigpio_only.py --tb=short && /home/ido/.venvs/mics_core_dev/bin/python -c "
import pathlib, subprocess, sys
fc = pathlib.Path('tools/tree_integrity/final_checks.py').read_text()
# Count the DEFINITION and CALL forms, never the bare string: '_ntp_violations' also appears at :150
# as prose inside the still-live HOLD 1 comment, and may appear in this plan's own deletion-site note.
gone = {k: fc.count(k) for k in ('NTP_CALLS', 'CLOCK_COMMENTS', 'def _ntp_violations', '+= _ntp_violations(')}
print('retired F3 machinery counts (definition/call forms):', gone)
if any(gone.values()):
    sys.exit('the inverted F3 NTP guard is still present: %r' % gone)
print('bare _ntp_violations occurrences remaining (prose only, not gated):', fc.count('_ntp_violations'))
if fc.count('_uncommented(body)') != 1:
    sys.exit('the HOLD 1 _handshake_watchdog assertion was damaged; only its :150 cross-reference comment may change')
kept = {k: fc.count(k) for k in ('f3_toggles', 'open_file', '_handshake_watchdog', 'set_cdc_manual', 'IR1', 'OG_TRIGGER')}
print('surviving f3_toggles assertions:', kept)
missing = [k for k, v in kept.items() if v == 0]
if missing:
    sys.exit('collateral damage: these unrelated Phase 30 assertions were removed too: %r' % missing)
if fc.count('PLAT-22') == 0 or fc.count('resolved') == 0:
    sys.exit('the deletion site must carry a comment naming PLAT-22 and saying the deferral is RESOLVED, not dropped')
old = subprocess.run(['git', 'show', 'HEAD:tools/tree_integrity/final_checks.py'], capture_output=True, text=True)
print('def _ntp_violations occurrences at HEAD (non-vacuity check):', old.stdout.count('def _ntp_violations'))
if old.stdout.count('def _ntp_violations') != 1:
    sys.exit('non-vacuity check failed: the guard was not present at HEAD, so nothing was retired')
r = subprocess.run(['python3', 'tools/check_tree_integrity.py', '--final'], capture_output=True, text=True)
out = r.stdout + r.stderr
pathlib.Path('/tmp/final31_c3.txt').write_text(out)
if not out.strip():
    sys.exit('--final produced NO output - it crashed rather than reporting; nothing was verified')
ntp = [l for l in out.splitlines() if l.startswith('VIOLATION') and ('NTP' in l or 'clock' in l.lower() or 'CLOCK SETUP' in l)]
if ntp:
    sys.exit('F3 still reports an NTP/clock-block violation - the guard was not retired: %r' % ntp)
print('--final captured to /tmp/final31_c3.txt; no F3 NTP/clock-block violation remains')
" && /home/ido/.venvs/mics_core_dev/bin/python tools/pytest_delta.py && python3 tools/check_tree_integrity.py --strict</automated>
  </verify>
  <done>`NTP_CALLS`, `CLOCK_COMMENTS`, `def _ntp_violations` and `+= _ntp_violations(` are gone by counted assertion on those exact forms (the bare string survives as prose at `:150` and is deliberately not gated), and the HOLD 1 block is intact apart from its reworded cross-reference; `f3_toggles` still exists and its five unrelated Phase 30 assertions provably survive; the deletion site carries a comment naming PLAT-22 and stating the deferral is resolved; the non-vacuity check records that `_ntp_violations` was present at HEAD; `--final` runs, produces output, and reports no F3 NTP/clock-block violation; the per-F-check verdict table is in the summary; delta gate `new failures: 0`; `--strict` exit 0.</done>
</task>

</tasks>

<verification>
1. `python3 -c "import pathlib,sys; p=pathlib.Path('/home/ido/mics_core/autopilot/autopilot/core/pilot.py').read_text(); c={k:p.count(k) for k in ('sync_ticks','synchronize','enable_ntp_and_wait','disable_ntp','CLOCK SETUP','Freeze wall clock')}; print(c); sys.exit(0 if not any(c.values()) else 'pilot.py still carries the patched-client or clock-freeze surface')"`
   -> exit 0
1b. `python3 -c "import pathlib,sys; p=pathlib.Path('/home/ido/mics_core/autopilot/autopilot/core/pilot.py').read_text(); k={n:p.count(n) for n in ('self.init_pigpio()','def init_pigpio(','external.start_pigpiod()')}; print(k); sys.exit(0 if k=={'self.init_pigpio()':1,'def init_pigpio(':1,'external.start_pigpiod()':1} else 'the pigpiod spawn was altered - PLAT-33 is WITHDRAWN and the spawn is the output fail-safe')"`
   -> exit 0
2. `python3 -c "import pathlib,sys; v=[str(f) for f in pathlib.Path('/home/ido/mics_core').rglob('pigpio.py')]; print(v); sys.exit(0 if not v else 'a pigpio.py is vendored in the repo')"`
   -> exit 0
3. `/home/ido/.venvs/mics_core_dev/bin/python -m pytest -q tests/test_stock_pigpio_only.py tests/test_clock_block_removed.py` -> pass
4. `python3 tools/check_tree_integrity.py --strict` -> exit 0, `30 protected files`, `0 violations`
5. `python3 tools/check_tree_integrity.py --final` -> runs, produces output, **no F3 NTP/clock-block
   violation**; the remaining failures are named per F-check in the summary
6. `wc -l /home/ido/mics_core/autopilot/autopilot/core/pilot.py` -> fewer lines than before this plan
7. `git -C /home/ido/mics_core diff --name-only` -> touches only this plan's five files, and
   `autopilot/autopilot/external/__init__.py` is expected to show **no** diff
</verification>

<success_criteria>
- The run path works against a **stock** pigpio client: the two patch-only call sites that raise
  `TypeError`/`AttributeError` are gone, and the intermediate break `31-REVISED-SCOPE.md` named is
  closed.
- "Stock pigpio" is enforced at run time by `get_clock().attach()`, not merely asserted in a
  requirements file — a patched client is refused loudly.
- Nothing in the tree monkey-patches pigpio and nothing vendors a client.
- The pilot **still** spawns `pigpiod`, and that is asserted rather than assumed: `init_pigpio()`,
  its call site and `external.start_pigpiod()` each survive exactly once, and the `kill_proc`
  fail-safe hook in `external/__init__.py` is intact. PLAT-33 was withdrawn 2026-08-17 because that
  hook is what closes the solenoids at session end; a supervised daemon would outlive a crashed
  pilot. The gate also asserts **no** `pigpiod` unit or drop-in exists, so the decision cannot be
  quietly undone from `deploy/`.
- The Phase 30 clock-freeze deferral is **resolved by being made unnecessary**, with the reasoning in
  the code, and its deliberately-inverted guard is retired in the same change — with the rest of
  `f3_toggles` provably intact.
- `--final` is meaningful again for the first time in the phase, with a per-F-check verdict recorded.
</success_criteria>

<output>
After completion, create
`.planning/phases/31-mics-core-modern-pi-platform-bookworm-64-bit-python-3-11-lgpio-unattended-boot/31-C3-SUMMARY.md`.

Include:
- the violation list `tests/test_stock_pigpio_only.py` produced **before** the edits, and the empty
  list after — the before/after is the evidence;
- the `--final` per-F-check verdict table, naming which remaining failures belong to Phase 30's exit
  criteria and which (if any) belong here;
- before/after line counts for `pilot.py`;
- an explicit statement that **PLAT-33 was withdrawn 2026-08-17** and therefore that
  `self.init_pigpio()`, `init_pigpio()` and `external.start_pigpiod()` were **preserved**, with the
  counted evidence and the one-sentence reason (the `kill_proc` hook is the rig's output fail-safe);
  say plainly that `external/__init__.py` has a zero-line diff and that this is the intended outcome;
- one line recording that the `PIGPIOARGS`/`PIGPIOMASK` two-sources-of-truth item plan 05's earlier
  text handed here **no longer exists**, because there is no drop-in and `prefs.json` is the only
  copy — so a reader of that older text stops looking;
- the paragraph explaining that the NTP deferral was **resolved, not dropped**, cross-referenced to
  `30-HARDWARE-VALIDATION.md` §6.7 — that paragraph belongs in the record, since Phase 30 deliberately
  guarded against exactly this deletion;
- the read-only SSH commands C4 uses to confirm the stock client on the provisioned card, ready to
  copy-paste.
</output>
