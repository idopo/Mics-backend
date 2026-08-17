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
requirements: [PLAT-20, PLAT-22, PLAT-28, PLAT-33]
must_haves:
  truths:
    - "The pilot connects to a STOCK pigpio client and would refuse to run against a patched one"
    - "The two patch-only call sites that RAISE on stock pigpio are gone, so the run path works again"
    - "Nothing in the tree monkey-patches pigpio, and no patched pigpio.py is vendored anywhere"
    - "The pilot no longer spawns pigpiod; the daemon's lifetime is systemd's (PLAT-33)"
    - "The deferred clock-freeze block is gone AND the inverted --final F3 guard that required it is retired in the same change"
    - "NTP is allowed to run normally, because timestamps no longer come from an estimated tick-to-wall-clock mapping"
    - "The MICS clock is attached to the live client at run start, so both event paths have a clock to read"
  artifacts:
    - path: "/home/ido/mics_core/tests/test_stock_pigpio_only.py"
      provides: "Static gate: no Autopilot pigpio patch, no vendored client, no monkey-patching, no pigpiod spawn"
      min_lines: 40
      contains: "sync_ticks"
    - path: "/home/ido/mics_core/tests/test_clock_block_removed.py"
      provides: "Static gate: the clock-freeze block, its orphaned methods and its inverted guard are all gone, and the REST of f3_toggles survives"
      min_lines: 30
    - path: "/home/ido/mics_core/autopilot/autopilot/core/pilot.py"
      provides: "Stock pigpio.pi() plus MicsClock.attach(); no sync_ticks, no synchronize(), no start_pigpiod, no clock-freeze block"
      contains: "attach"
  key_links:
    - from: "pilot.py's run-start client init"
      to: "autopilot.utils.clock.get_clock().attach(self.pi)"
      via: "the one place the clock meets the live client, which is also the PLAT-28 runtime guard"
      pattern: "attach"
    - from: "mics-pilot.service"
      to: "pigpiod.service"
      via: "systemd After= + Requires= (plan 05), replacing pilot.py:949 external.start_pigpiod()"
      pattern: "pigpiod"
    - from: "the deleted clock-freeze block"
      to: "final_checks.py f3_toggles"
      via: "the _ntp_violations machinery retired in the same commit, or --final fails loudly"
      pattern: "_ntp_violations"
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

**Three of the four things here are deletions, and one of them is currently a landmine.** Verified
2026-08-17 by direct read of the 1198-line `pilot.py`:

- `:1073 self.pi = pigpio.pi(sync_ticks=True)` and `:1079 self.pi.synchronize()` are **patch-only**.
  Stock pigpio has neither, so `pi(sync_ticks=True)` raises `TypeError`. That is a **live break** on
  the run path from the moment plan 03's stock pin is installed — bounded (it fires only when a task
  starts, which plan 09 never exercises) but real, and `31-REVISED-SCOPE.md` names it. **This plan is
  what closes it.**
- `:949 external.start_pigpiod()` is PLAT-33's other half. Plan 05 wrote the supervised `pigpiod`
  unit; this plan stops the pilot spawning its own.
- `:1069-1084` interleaves the live client init with the **commented** clock-freeze block
  (`# ---- CLOCK SETUP ----` at `:1071`, `# self.enable_ntp_and_wait()` at `:1072`,
  `# Freeze wall clock so it never jumps during the task` at `:1081`, `# self.disable_ntp()` at
  `:1082`). PLAT-22's deletion.

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

Output: a stock-only tree, a working run path, a supervised daemon, the clock attached at run start,
and two static gates that stop all of it coming back.
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
| `self.init_pigpio()` | `:206` | **DELETE** (the method becomes empty — see below) |
| `def enable_ntp_and_wait(self, timeout=30)` | `:497` | **DELETE the definition** if nothing calls it |
| `def disable_ntp(self)` | `:513` | **DELETE the definition** if nothing calls it |
| `def init_pigpio(self)` | `:947-953` | Its body is **only** `self.pigpiod = external.start_pigpiod()` (`:949`), a debug log and an `except ImportError`. It does **not** create the client. With PLAT-33 removing the spawn, the method is empty -> **DELETE the method and its call** |
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
and therefore **takes the clock-freeze block with it**. So by the time Task 2 runs, its `pilot.py`
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

**`external/__init__.py` — decide on evidence, not on the module's name.** It carries ~10 pigpio
references including `:33`'s `raise ImportError('the pigpiod daemon was not found! ...')`. Remove
`start_pigpiod` **only if** a counted scan proves nothing else calls it, and record the evidence. If
other things in `external/` are live, leave them: this plan removes a spawn, not a module. Either
way, state the verdict in the summary.

**`requirements.txt` is NOT edited here.** Plan 03 pinned the stock pigpio **client** (a pure-Python
`py3-none-any` wheel, on the wheel-check allow-list alongside `Adafruit-PureIO`). This plan
**asserts** that pin survives; it does not touch the file, which is also what keeps it out of plan
09's way.

**`deploy/` is NOT edited here.** Plan 05 wrote `pigpiod-mics.conf` and `chrony-mics.conf`; plan 07
installs them; plan 09 proves them on hardware. This plan **asserts** they exist and say what PLAT-20
and PLAT-33 need them to say.

**The two-sources-of-truth item plan 05 flagged and handed here.** Once the pilot stops spawning the
daemon, `PIGPIOARGS` / `PIGPIOMASK` in `prefs.json` are **inert** while `deploy/pigpiod-mics.conf` is
authoritative. Two live copies of an argument set that nobody reconciles is how they diverge. Decide
it here — the options are (a) delete the two prefs keys, (b) have `render-prefs.sh`/`install.sh`
derive the unit's arguments from the prefs, or (c) keep both and add a comment plus a test asserting
they match. **(c) is the cheapest correct answer and the one this plan recommends**, because (a)
touches `prefs.template.json` (plan 04's file) and (b) is real coupling for no operational gain. But
whichever you take, take it explicitly and record it — the failure mode is silence, not the choice.
</verified_deletion_map>

<the_f3_guard>
## The `--final` F3 guard, and exactly how much of it to remove

In `tools/tree_integrity/final_checks.py`:

- `NTP_CALLS = ("self.enable_ntp_and_wait()", "self.disable_ntp()")` (~line 42)
- `CLOCK_COMMENTS = ("# ---- CLOCK SETUP ----", "# Freeze wall clock ...")` (~line 44)
- `_ntp_violations(text)` (~lines 48-67) and its call site inside `f3_toggles`

Delete the `_ntp_violations` machinery and its call. It is a whole-file substring search with no line
number, which is why it kept working after Phase 30 shifted the block from `:1137-1148` to
`:1071-1082`.

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
  <name>Task 1: Stock client, MICS clock attached, pigpiod spawn removed, clock-freeze block deleted</name>
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
    - `start_pigpiod` and `pigpiod` **as a spawn** (an `import`/`subprocess` reference; a comment or
      a docstring naming the systemd unit is fine and must not trip the gate — scope the check so it
      does, and prove the scoping with a fixture)
    - `get_current_tick` **outside** `autopilot/utils/clock.py` — the heartbeat is the only legitimate
      caller, and C1 owns it

    It also asserts, as separate cases:
    - **No vendored client.** There is **no file named `pigpio.py`** anywhere in the repo. Count it.
      PLAT-28's headline is that no untracked venv file may carry behaviour; the repo-side half is
      that we do not vendor one either.
    - **No monkey-patching.** No production module assigns onto the pigpio module
      (`pigpio.<name> = `) and none writes `sys.modules['pigpio']`. `tests/` and `conftest.py` are
      exempt — plan 01's fixture does exactly that, on purpose, in the test environment only.
    - **The pin survives.** `requirements.txt` contains exactly one `pigpio` requirement line and it
      is not commented out. This plan does not edit the file; it proves plan 03's work was not lost.
    - **The unit exists.** `deploy/pigpiod-mics.conf` exists and `deploy/mics-pilot.service` names
      `pigpiod` at least twice (the `After=` and the `Requires=`), i.e. PLAT-33's systemd half is in
      place before the spawn is removed. Removing the spawn without the unit would leave no daemon at
      all.
    - **chrony, not timesyncd (PLAT-20).** `deploy/chrony-mics.conf` exists and contains no
      `makestep` (Debian ships it; restating it is how it silently diverges), and no MICS file
      re-enables `systemd-timesyncd`.

    And on `pilot.py` specifically:
    - zero occurrences of `sync_ticks`, `synchronize`, `init_pigpio`, `start_pigpiod`,
      `enable_ntp_and_wait`, `disable_ntp`, `# ---- CLOCK SETUP ----`,
      `Freeze wall clock so it never jumps during the task`
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
       - delete `self.init_pigpio()` and the now-empty `init_pigpio` method;
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

    3. Decide `external/`'s fate on evidence: `grep -rn "autopilot\.external"` plus the tree-integrity
       closure, both re-verified with counted Python rather than a proxied grep. Remove
       `start_pigpiod` if and only if nothing else calls it; keep the module if anything else in it is
       live. State the verdict and the counts in the summary.

    4. Resolve the `PIGPIOARGS`/`PIGPIOMASK` two-sources-of-truth item per `<verified_deletion_map>`.
       If you take the recommended option (c), the comment goes in `pilot.py` next to the removed
       spawn **and** the assertion goes in this task's test: the `-x` mask in
       `deploy/pigpiod-mics.conf` must equal `PIGPIOMASK` in `pilot/prefs.template.json`, and the
       flags must match `PIGPIOARGS`. That turns two live copies into one checked pair.

    5. Report the before/after line count of `pilot.py`. It should shrink.

    6. Do **not** edit `requirements.txt`, `deploy/*`, `tools/tree_integrity/final_checks.py`,
       `Event_Dispatcher.py`, `gpio.py`, `task.py` or `logging_utils.py`. The first two belong to
       plans 03/05/07; the third is Task 2; the rest are C2's and are already correct.
  </action>
  <verify>
    <automated>cd /home/ido/mics_core && /home/ido/.venvs/mics_core_dev/bin/python -m pytest -q tests/test_stock_pigpio_only.py --tb=short && /home/ido/.venvs/mics_core_dev/bin/python -c "
import pathlib, re, sys
p = pathlib.Path('autopilot/autopilot/core/pilot.py').read_text()
counts = {k: p.count(k) for k in ('sync_ticks', 'synchronize', 'init_pigpio', 'start_pigpiod',
                                  'enable_ntp_and_wait', 'disable_ntp',
                                  '# ---- CLOCK SETUP ----',
                                  'Freeze wall clock so it never jumps during the task')}
print('pilot.py forbidden-token counts:', counts)
bad = {k: v for k, v in counts.items() if v}
if bad:
    sys.exit('pilot.py still carries the patched-client / clock-freeze surface: %r' % bad)
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
unit = pathlib.Path('deploy/mics-pilot.service').read_text()
print('pigpiod occurrences in mics-pilot.service:', unit.count('pigpiod'))
if unit.count('pigpiod') < 2 or not pathlib.Path('deploy/pigpiod-mics.conf').exists():
    sys.exit('PLAT-33 systemd half is missing; removing the spawn would leave no daemon at all')
ch = pathlib.Path('deploy/chrony-mics.conf')
print('chrony drop-in exists:', ch.exists(), '| makestep occurrences:', ch.read_text().count('makestep') if ch.exists() else 'n/a')
if not ch.exists() or ch.read_text().count('makestep'):
    sys.exit('PLAT-20 chrony drop-in missing, or it restates Debian default makestep')
" && /home/ido/.venvs/mics_core_dev/bin/python tools/pytest_delta.py && python3 tools/check_tree_integrity.py --strict</automated>
  </verify>
  <done>`tests/test_stock_pigpio_only.py` passes; `pilot.py` carries zero occurrences of `sync_ticks`, `synchronize`, `init_pigpio`, `start_pigpiod`, `enable_ntp_and_wait`, `disable_ntp` and both clock-freeze anchors, by counted assertion; there is exactly one argument-free `pigpio.pi()` call and at least one `get_clock().attach(`; both `gpio.clear_scripts(self.pi)` calls survive; no `pigpio.py` is vendored anywhere and nothing monkey-patches the module; the single `requirements.txt` pin, the `pigpiod` unit ordering and the chrony drop-in are all asserted present; `external/`'s fate is decided on counted evidence; `pilot.py` is shorter; delta gate `new failures: 0`; `--strict` exit 0.</done>
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
    - `tools/tree_integrity/final_checks.py` contains **no** `NTP_CALLS`, **no** `CLOCK_COMMENTS` and
      **no** `_ntp_violations`. The guard and the thing it guarded go together, in one commit.
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

    A separate case asserts the whole thing is not vacuous: `_ntp_violations` **was** present in the
    file at the start of this task. Record the pre-edit `git show HEAD:tools/tree_integrity/final_checks.py`
    count in the summary, so "the guard is gone" is provably a removal rather than an assertion about
    something that was never there.
  </behavior>
  <action>
    1. Write the test first, including the survival assertions for the rest of `f3_toggles` and the
       non-vacuity record.

    2. In `final_checks.py`, delete `NTP_CALLS`, `CLOCK_COMMENTS`, `_ntp_violations` and the call to
       it inside `f3_toggles`. **Leave every other assertion in that function untouched.** `git diff`
       the file and read it before committing.

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
       ssh -i ~/.ssh/pi_mics pi@<SPARE_IP> "systemctl is-enabled pigpiod; systemctl cat pigpiod.service | head -30"
       ```
       Both must report `False` for the two patch attributes. C4's pre-flight runs them.
  </action>
  <verify>
    <automated>cd /home/ido/mics_core && /home/ido/.venvs/mics_core_dev/bin/python -m pytest -q tests/test_clock_block_removed.py tests/test_stock_pigpio_only.py --tb=short && /home/ido/.venvs/mics_core_dev/bin/python -c "
import pathlib, subprocess, sys
fc = pathlib.Path('tools/tree_integrity/final_checks.py').read_text()
gone = {k: fc.count(k) for k in ('NTP_CALLS', 'CLOCK_COMMENTS', '_ntp_violations')}
print('retired F3 machinery counts:', gone)
if any(gone.values()):
    sys.exit('the inverted F3 NTP guard is still present: %r' % gone)
kept = {k: fc.count(k) for k in ('f3_toggles', 'open_file', '_handshake_watchdog', 'set_cdc_manual', 'IR1', 'OG_TRIGGER')}
print('surviving f3_toggles assertions:', kept)
missing = [k for k, v in kept.items() if v == 0]
if missing:
    sys.exit('collateral damage: these unrelated Phase 30 assertions were removed too: %r' % missing)
if fc.count('PLAT-22') == 0 or fc.count('resolved') == 0:
    sys.exit('the deletion site must carry a comment naming PLAT-22 and saying the deferral is RESOLVED, not dropped')
old = subprocess.run(['git', 'show', 'HEAD:tools/tree_integrity/final_checks.py'], capture_output=True, text=True)
print('_ntp_violations occurrences at HEAD (non-vacuity check):', old.stdout.count('_ntp_violations'))
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
  <done>`NTP_CALLS`, `CLOCK_COMMENTS` and `_ntp_violations` are gone by counted assertion; `f3_toggles` still exists and its five unrelated Phase 30 assertions provably survive; the deletion site carries a comment naming PLAT-22 and stating the deferral is resolved; the non-vacuity check records that `_ntp_violations` was present at HEAD; `--final` runs, produces output, and reports no F3 NTP/clock-block violation; the per-F-check verdict table is in the summary; delta gate `new failures: 0`; `--strict` exit 0.</done>
</task>

</tasks>

<verification>
1. `python3 -c "import pathlib,sys; p=pathlib.Path('/home/ido/mics_core/autopilot/autopilot/core/pilot.py').read_text(); c={k:p.count(k) for k in ('sync_ticks','synchronize','start_pigpiod','init_pigpio','enable_ntp_and_wait','disable_ntp','CLOCK SETUP','Freeze wall clock')}; print(c); sys.exit(0 if not any(c.values()) else 'pilot.py still carries the patched-client or clock-freeze surface')"`
   -> exit 0
2. `python3 -c "import pathlib,sys; v=[str(f) for f in pathlib.Path('/home/ido/mics_core').rglob('pigpio.py')]; print(v); sys.exit(0 if not v else 'a pigpio.py is vendored in the repo')"`
   -> exit 0
3. `/home/ido/.venvs/mics_core_dev/bin/python -m pytest -q tests/test_stock_pigpio_only.py tests/test_clock_block_removed.py` -> pass
4. `python3 tools/check_tree_integrity.py --strict` -> exit 0, `30 protected files`, `0 violations`
5. `python3 tools/check_tree_integrity.py --final` -> runs, produces output, **no F3 NTP/clock-block
   violation**; the remaining failures are named per F-check in the summary
6. `wc -l /home/ido/mics_core/autopilot/autopilot/core/pilot.py` -> fewer lines than before this plan
7. `git -C /home/ido/mics_core diff --name-only` -> touches only this plan's five files
</verification>

<success_criteria>
- The run path works against a **stock** pigpio client: the two patch-only call sites that raise
  `TypeError`/`AttributeError` are gone, and the intermediate break `31-REVISED-SCOPE.md` named is
  closed.
- "Stock pigpio" is enforced at run time by `get_clock().attach()`, not merely asserted in a
  requirements file — a patched client is refused loudly.
- Nothing in the tree monkey-patches pigpio and nothing vendors a client.
- The pilot no longer spawns `pigpiod`; the daemon is systemd's, and the plan asserts the unit exists
  before removing the spawn rather than after.
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
- the `external/` verdict with the counted evidence behind it;
- the `PIGPIOARGS`/`PIGPIOMASK` two-sources-of-truth decision and how it is now enforced;
- the paragraph explaining that the NTP deferral was **resolved, not dropped**, cross-referenced to
  `30-HARDWARE-VALIDATION.md` §6.7 — that paragraph belongs in the record, since Phase 30 deliberately
  guarded against exactly this deletion;
- the read-only SSH commands C4 uses to confirm the stock client on the provisioned card, ready to
  copy-paste.
</output>
