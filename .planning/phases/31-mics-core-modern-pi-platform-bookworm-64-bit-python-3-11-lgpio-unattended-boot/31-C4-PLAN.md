---
phase: 31-mics-core-modern-pi-platform-bookworm-64-bit-python-3-11-lgpio-unattended-boot
plan: C4
type: execute
wave: 8
depends_on: ["31-C3", "31-09"]
files_modified:
  - /home/ido/mics_core/tools/pulse_timing/clock_soak.py
  - /home/ido/mics_core/tests/test_clock_soak.py
  - /home/ido/mics_core/tools/pulse_timing/README.md
  - /home/ido/mics_core/tools/pulse_timing/captures/
  - /home/ido/mics-backend/.planning/phases/31-mics-core-modern-pi-platform-bookworm-64-bit-python-3-11-lgpio-unattended-boot/31-HARDWARE-VALIDATION.md
autonomous: false
requirements: [PLAT-17, PLAT-24, PLAT-25, PLAT-32]
must_haves:
  truths:
    - "The 71.6-minute backward jump is proven GONE by the same tool that proved it PRESENT in plan 08, across at least three real wraps under load"
    - "A wall-clock step, forwards and backwards, moves the derived UTC by exactly the step and moves no interval"
    - "Both event paths agree on the same physical edge after hours of continuous operation, not just in a dev-host unit test"
    - "Every event in the soak carries a provenance flag and the flags are correct"
    - "Dropped samples are counted rather than silent, and the count is zero"
    - "The pulse path was not broken by the clock refactor, measured against plan 08's Buster baseline"
    - "PLAT-17's SCHED_FIFO choice is decided by a measurement rather than by a belief"
  artifacts:
    - path: "/home/ido/mics_core/tools/pulse_timing/clock_soak.py"
      provides: "USER-RUN long soak driving edges through the REAL assign_cb/MicsClock path, emitting plan 06's witness JSONL plus route, counters and trailer records"
      min_lines: 120
      contains: "get_clock"
    - path: "/home/ido/mics_core/tests/test_clock_soak.py"
      provides: "Dev-host proof that the soak emits a valid artifact and that --check-wrap fires in BOTH directions on it, before any hardware time is spent"
      min_lines: 60
    - path: "/home/ido/mics-backend/.planning/phases/31-mics-core-modern-pi-platform-bookworm-64-bit-python-3-11-lgpio-unattended-boot/31-HARDWARE-VALIDATION.md"
      provides: "The phase evidence log, 'after arm' section filled: soak verdict, clock-step verdicts, paired comparison with its confound, drop accounting, chrt table, fail-safe results, and a real NOT PROVEN section"
      contains: "NOT PROVEN"
    - path: "/home/ido/mics_core/tools/pulse_timing/captures/"
      provides: "Committed soak artifact, four clock-step captures and twenty paired 'after' captures"
  key_links:
    - from: "tools/pulse_timing/clock_soak.py"
      to: "autopilot.utils.clock.get_clock()"
      via: "the SAME shared clock object the pilot uses, so the soak measures the deployed code path and not a reimplementation"
      pattern: "get_clock"
    - from: "the soak artifact"
      to: "analyse.py --check-wrap (DEFAULT direction)"
      via: "plan 06's witness JSONL contract; plan 08 already proved the same tool fires in --expect-defect mode, so the assertion is known not to be vacuous"
      pattern: "check-wrap"
    - from: "the twenty 'after' captures"
      to: "analyse.py --gate before after"
      via: "PLAT-24's G1 comparative gate against plan 08's committed Buster baseline"
      pattern: "--gate"
    - from: "the soak's route records"
      to: "the two dispatch routes C2 wired"
      via: "logging_utils.py:97 and task.py:283 payloads captured for sampled edges and asserted equal"
      pattern: "route"
---

<objective>
The acceptance gate. Prove the clock is fixed on real hardware, over real time, under real load — and
be explicit about what that proves and what it does not.

Purpose: every other plan in this phase produces code or configuration. This one produces
**evidence**. `31-REVISED-SCOPE.md` §8 sets a bar that deliberately cannot be cleared by assertion:

1. **>= 3 tick wraps (> 3.6 hours) under deliberate CPU load**, with a forced wall-clock step
   **forwards and backwards** mid-run.
2. **Zero backward jumps** in the delivered timestamp series — `analyse.py --check-wrap` in its
   **default** direction. Plan 08 already ran the same tool in `--expect-defect` mode against the
   deployed patched client and it fired, so this assertion is **known not to be vacuous**. That
   pairing is the single most valuable property of the whole instrument: the same code proving the
   defect present before and absent after.
3. **Both event paths agree on the same physical edge**, after hours — not just in C2's dev-host
   unit test with an injected tick.
4. **Provenance flags present and correct** on every event (PLAT-31, closed by C2, evidenced here).
5. **Zero undetected dropped samples** (PLAT-32).
6. **Paired before/after pulse-timing capture** versus plan 08's Buster baseline (PLAT-24).
7. **PLAT-17's `SCHED_FIFO` headroom measured**, which plan 05 explicitly deferred to this plan.

**State the honest weighting up front and keep stating it, because the paired capture is the part a
reader will over-value.** C1-C3 changed the **timestamping**, not the pulse path: pulses are still
generated by pigpio daemon scripts (`store_script`/`run_script`), which this phase never touched. So
a "no regression" result on the paired capture mostly proves **the pulse path was not accidentally
broken**. That is worth measuring — an accidental break there is a data-quality defect no functional
test would catch — but it is a **guard**, not the clock evidence. The clock evidence is
`--check-wrap` and this soak. Plan 06's README already says the equivalent about G1 carrying the
weight over the absolute thresholds; say this one just as plainly.

Output: a soak runner, a committed soak artifact, twenty paired captures, four clock-step captures, a
scheduling measurement, and the completed phase evidence log with a real NOT PROVEN section.
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
@.planning/phases/31-mics-core-modern-pi-platform-bookworm-64-bit-python-3-11-lgpio-unattended-boot/31-VALIDATION.md
@.planning/phases/31-mics-core-modern-pi-platform-bookworm-64-bit-python-3-11-lgpio-unattended-boot/31-06-SUMMARY.md
@.planning/phases/31-mics-core-modern-pi-platform-bookworm-64-bit-python-3-11-lgpio-unattended-boot/31-08-SUMMARY.md
@.planning/phases/31-mics-core-modern-pi-platform-bookworm-64-bit-python-3-11-lgpio-unattended-boot/31-09-SUMMARY.md
@.planning/phases/31-mics-core-modern-pi-platform-bookworm-64-bit-python-3-11-lgpio-unattended-boot/31-C1-SUMMARY.md
@.planning/phases/31-mics-core-modern-pi-platform-bookworm-64-bit-python-3-11-lgpio-unattended-boot/31-C2-SUMMARY.md
@.planning/phases/31-mics-core-modern-pi-platform-bookworm-64-bit-python-3-11-lgpio-unattended-boot/31-C3-SUMMARY.md
@.planning/phases/31-mics-core-modern-pi-platform-bookworm-64-bit-python-3-11-lgpio-unattended-boot/31-HARDWARE-VALIDATION.md

**Read `31-08-SUMMARY.md` and the existing `31-HARDWARE-VALIDATION.md` first.** They carry the
"before" arm, the measured backward-jump magnitude and the calibration verdict this plan compares
against. **If plan 08 recorded that the wrap defect did NOT reproduce, stop and escalate before
running anything** — PLAT-29 and PLAT-30 were written on the assumption that it does.

**Read `31-06-SUMMARY.md`** for the JSONL contract and the per-capture copy-paste blocks, and
**`31-C1-SUMMARY.md`** for the clock's `counters()` key set — this plan's PLAT-32 accounting reads it.

<repo_boundary>
ALL code changes land in `/home/ido/mics_core` on branch **`phase-31-modern-pi-platform`**.

<branch_guard>
**Assert the branch before committing anything.** All Phase 31 code lands on
`phase-31-modern-pi-platform` in `/home/ido/mics_core`, published to `origin` by plan 01. Before the
first commit of this plan, run `git branch --show-current` and confirm it is that branch — if it is
not, STOP and do not commit. Never `git checkout main`, never merge into `main`, never force-push,
and never push `main`. Integration to `main` is the user's decision after the C4 acceptance gate.
</branch_guard>

Planning documents stay in `/home/ido/mics-backend/.planning/`.
</repo_boundary>

<pi_rules>
ABSOLUTE, and this plan is built entirely around them:
- **NEVER run git on the Pi.** No commit/merge/push/pull/checkout/reset. No `rsync --delete`.
- **NEVER start or stop the pilot process. NEVER run any Python file on the Pi.**
  Every capture here is **USER-RUN**: the agent supplies the exact command, the user runs it, the
  user copies the artifact back, the agent analyses it locally. Phase 30 HYG-01/HYG-02 precedent.
- SSH for **reading and grepping** is fine: `ssh -i ~/.ssh/pi_mics pi@<SPARE_IP>`. The agent may use
  it to confirm what landed. It may not use it to run anything.
- Pi log files are 0 bytes **by design**. The soak's evidence comes from the JSONL artifact, from
  `journalctl` and from the clock's counters — never from a pilot log file, and nobody "fixes" the
  empty ones.
- **The live rig at `132.77.72.28` is NOT the target.** All work happens on the spare hardware
  provisioned in plan 09. The ROADMAP is explicit: the live rig is not touched.
- RTK-proxied grep can render a matching line blank. Every absence claim is a counted `python3 -c`
  printing a count, never a silent grep.
</pi_rules>

<agent_vs_user>
**Agent:** writes `clock_soak.py` and its tests; runs the pre-flight gate; writes every copy-paste
block; verifies read-only over SSH what landed; analyses every returned artifact with
`tools/pulse_timing/analyse.py`; completes `31-HARDWARE-VALIDATION.md`.

**User:** provides the spare Pi provisioned by plan 09, wires the loopback jumper, copies the harness
onto the card, runs every command, forces the clock steps, holds the meter, and copies the artifacts
back.

Present the user's steps as a **single numbered checklist with literal commands**, then **stop and
wait**. Do not interleave agent work between user steps. Say the time cost **before** the user
starts: a campaign discovered to be long half way through is a campaign abandoned half way through.
</agent_vs_user>

<integrity_gate>
`cd /home/ido/mics_core && python3 tools/check_tree_integrity.py --strict` must exit 0 after every
autonomous task. **NEVER `--rebaseline`.** None of this plan's files is in the protected manifest.

`--final` is also run and recorded — C3 made it meaningful again, and this is the phase's exit.

`tools/tree_integrity/scan.py` reads `.py`, `.sh` and `.json`; the `.jsonl` capture artifacts are
outside the scanned suffix set, but `clock_soak.py` **is** scanned, so keep its `autopilot.*` imports
real.
</integrity_gate>

<hardware_prerequisites>
Confirm ALL of these with the user before issuing any command. If any is missing, stop and say so —
do not start a partial acceptance campaign.

- [ ] **Task 0 passed.** This one is the agent's, it is an exit code rather than judgement, and it
      comes first.
- [ ] The **spare Pi 4B provisioned by plan 09**: Bookworm 64-bit, Python 3.11, `install.sh` run,
      `mics-pilot.service` enabled and chrony active. **Not** the live rig. There is **no**
      `pigpiod.service` to check — PLAT-33 was withdrawn 2026-08-17 and the pilot spawns the
      daemon itself; confirm instead that `command -v pigpiod` resolves and that
      `ps -o ppid= -C pigpiod` shows it parented to the pilot once a run starts.
- [ ] **A stock pigpio client in `/home/pi/.venv/mics`.** Confirm read-only with C3's command; both
      patch attributes must report `False`. A patched client measures the wrong thing, and
      `get_clock().attach()` would refuse to run against it anyway — better to find out before a
      jumper is wired.
- [ ] **The same two jumpered GPIO pins plan 08 used**, or a documented reason they changed. Pairing
      is what makes G1 meaningful without arbitrary absolute numbers; a changed pin weakens it and
      must be recorded rather than glossed.
- [ ] `stress-ng` installed on the card (`sudo apt install stress-ng`).
- [ ] A **multimeter** for the per-device fail-safe check (two arms per device — a clean stop and a
      `SIGKILL` — see Task 2 Step 4).
- [ ] The user has **~4.5 hours mostly unattended** (the soak, with two moments they must be present
      for, at roughly T+60 and T+120 minutes) and **~2.5 hours attended** (twenty paired captures,
      four clock-step captures, the `chrt` read-out and the fail-safe check).
- [ ] Plan 08's "before" table and `wrap_witness` evidence are committed and readable in
      `31-HARDWARE-VALIDATION.md`.
</hardware_prerequisites>

<soak_design>
## What the soak runs, and why it is not just a longer `wrap_witness`

`wrap_witness.py` (plan 06) records what **the installed pigpio client** hands a callback. That was
exactly right for plan 08, where the finding *was* the client's behaviour. It is the wrong instrument
now: after C1-C3 the client is stock and hands over a **raw tick**, and the conversion lives in
`assign_cb`. Pointing `wrap_witness` at the new system would faithfully record a raw 32-bit tick
wrapping — true, and irrelevant.

So C4 ships `tools/pulse_timing/clock_soak.py`, which drives edges through the **real** code path: the
production `Digital_Out`/`Digital_In` classes, the real `assign_cb` adapter, and
`autopilot.utils.clock.get_clock()` — **the same shared object the pilot uses**, not a private
instance. A soak that constructed its own clock would be measuring a copy of the design rather than
the deployed one.

**It emits plan 06's `witness` record shape unchanged**, so `analyse.py --check-wrap` works on it with
**no modification to `analyse.py`** (which is plan 06's file and stays plan 06's):

```
{"kind":"witness","i":<int>,"level":0|1|2,"tick":<raw 32-bit int>,
 "delivered":<the MICS clock's t_mono_ns>,"delivered_type":"int",
 "t_mono_ns":<independent CLOCK_MONOTONIC read in the callback>,
 "t_utc_ns":<int>,"ts_source":"hardware"|"software"}
```

`delivered` is our clock's output — the series `--check-wrap` scans for backward jumps. `t_mono_ns` is
the independent reference that proves any jump is in the *delivered* value and not in reality.
Keeping both, labelled, is what made plan 08's finding falsifiable and it is what makes this one
falsifiable too.

**Three additions to the contract, all documented in `tools/pulse_timing/README.md`:**

1. `{"kind":"route", ...}` — for a sampled subset of edges, **both** dispatch routes' payloads
   (`logging_utils.py:97` and `task.py:283`) are captured, each with its `t_mono_ns` and `ts_source`.
   This is C2's dev-host two-route assertion, re-taken **on hardware, over hours**, which is precisely
   what a unit test with an injected tick cannot tell you — the current design fails by *decaying over
   runtime*, not by being wrong at startup.

   **The literal key set, because a prose description here and a strict gate in Task 3 is how you
   discover a shape mismatch after 4.5 hours of the user's hardware time.** Task 3's analysis pins
   these names exactly; Task 0's pre-flight asserts them by name on synthetic output:

   ```
   {"kind":"route","i":<int>,"tick":<raw 32-bit int>,
    "a_route":"logging_utils:97","a_t_mono_ns":<int>,"a_ts_source":"hardware"|"software",
    "b_route":"task:283",        "b_t_mono_ns":<int>,"b_ts_source":"hardware"|"software"}
   ```

   Flat `a_*` / `b_*`, not nested — `a` is the `@log_action` route, `b` is the `execute_trigger`
   route, and the `*_route` strings are what let the analysis identify a payload **by route rather
   than by arrival order**, which `<soak_design>`'s own assertion 2 requires. Eight keys, all
   present on every record. If you change any name, change it in `<soak_design>`, in Task 0's test
   and in Task 3's gate **in the same edit**.

   **How the runner actually obtains route b, since this is the part that is easy to fake and
   worthless if faked.** Route a arrives for free: `Digital_Out(record=True)` self-registers
   `record_event` at `gpio.py:359` and `@auto_log` dispatches at `logging_utils.py:97`. Route b needs
   a real `Task`: construct the smallest concrete `Task` subclass the tree allows and register
   `partial(task.handle_trigger, hardware=hw)` on the same `Digital_Out`, **exactly the form
   `task.py:199` uses**. `Task.__init__` (`task.py:127-139`) requires `node`, `pilot`, `session`,
   `task_type` and a non-`None` `pi` (it raises `RuntimeError` without one), and it builds its own
   `Event_Dispatcher` and `View` from them — so pass the **same** `pigpio.pi()` client the soak
   attached the clock to, and let the `Event_Dispatcher` be the real one. Capture payloads by wrapping
   the dispatcher's send, not by replacing `dispatch_event`. **Do not call `dispatch_event` directly
   and do not stub `execute_trigger`** — either turns route b into a simulation of itself, and the
   two-route agreement then proves nothing. Record in the summary exactly which objects were
   constructed and which (if any) were stubbed.
2. `{"kind":"counters", ...}` — the clock's `counters()` dict plus the dispatcher's
   `_dropped_no_clock` / `_dropped_on_send`, snapshotted on the heartbeat cadence, so a counter that
   moves can be located in time rather than only totalled.
3. `{"kind":"trailer", ...}` — one final record with `n_commanded`, `n_observed`, `n_missing`, the
   final `counters()`, the wall-clock steps applied and the run environment. **`n_missing` is
   PLAT-32's primary number.**

**Python version:** `clock_soak.py` runs on the card's Python **3.11** and must **NOT** enter
`py37_gate.py`'s closure. That gate exists so plan 08's `before` capture could run on Buster's 3.7; a
3.11-only tool joining the closure would either fail the gate or, worse, constrain a module that has
no reason to be constrained. Task 0 asserts the closure did not gain it.

**It must never raise out of the callback.** An exception in pigpio's notify thread kills every
subsequent event for every GPIO. Catch, count, record — the rule `wrap_witness.py` already follows.

## PLAT-32: what "zero undetected dropped samples" can and cannot mean

Be precise here, because the requirement is easy to claim and hard to earn.

`pigpiod` samples the GPIO block by DMA every 5 µs (no `-s`, so the default) and buffers `-b 120` ms
(plan 05 made today's implicit default explicit). Starvation beyond that buffer **drops samples**.
But **`pigpiod` exposes no dropped-sample counter to the Python client** — there is no socket command
that returns one. A claim of "zero drops" therefore cannot rest on reading a daemon counter, because
there is none to read. Do not pretend otherwise anywhere in the evidence log.

What IS observable, and what the accounting therefore is:

| Signal | Source | What it catches |
|---|---|---|
| `n_missing` = commanded - observed edges | the soak's own trailer | a dropped edge, directly. **The primary number.** |
| `ambiguous_gap`, `monotonic_violation`, `convert_failed` | C1's `counters()` | **FAULTS — asserted zero.** A gap the extender could not disambiguate (Case D), a value that went backwards without the out-of-order flag, or a conversion that failed |
| `wraps`, `out_of_order`, `duplicates`, `refits` | C1's `counters()` | **ACTIVITY — printed, never asserted.** `out_of_order` is Case C firing, which is normal under a heartbeat thread; `duplicates` is Case A; together with `wraps` these reconstruct C1's A/B/C/D accounting |
| `heartbeat_missed` | C1's `counters()` | **FAULT — asserted zero.** The calibration path being starved |
| `bracket_rejected`, `fit_rejected` | C1's `counters()` | **REPORTED, not asserted** (C1 `:699`). A re-fit declining a bad sample is correct behaviour |
| `_dropped_no_clock`, `_dropped_on_send` | C2's dispatcher | an event that reached dispatch and was dropped there |
| daemon warnings | `journalctl -u mics-pilot -b` over the soak window | anything `pigpiod` itself chose to say. **It has no journal of its own:** PLAT-33 was withdrawn, so the daemon is a `subprocess.Popen` child of the pilot (`external/__init__.py:52`) and inherits the pilot unit's stdout/stderr. `journalctl -u pigpiod` returns nothing and its emptiness proves nothing |

**Criterion: `n_missing == 0` and every counter above zero, with the `journalctl` window inspected and
quoted.** If any is non-zero, that is a **finding reported with its count**, not a number to average
away — PLAT-32's requirement is "never as silence", so a reported non-zero count *satisfies PLAT-32*
while *failing the acceptance gate*. Those are two different verdicts and the log must say which
happened.

## PLAT-17: making the SCHED_FIFO choice a measurement

Plan 05 shipped `CPUSchedulingPolicy=fifo` / `CPUSchedulingPriority=10` with a comment saying it is a
**hypothesis pending this plan's measurement**, on the revised justification of
**notification-drain headroom** (not lgpio tx jitter — that backend is gone). Two parts:

1. **Does the policy reach the threads that matter?** `chrt -p` on **every** thread of the pilot
   process, and on `pigpiod`'s for comparison. POSIX threads inherit policy by default, but "should"
   is not a measurement. Produce a table: TID, comm, policy, priority.
2. **Does it buy anything?** The paired `after-other` (default scheduling) and `after-fifo10` arms,
   idle and loaded, compared on `err_p99`, `err_sd` and `n_missing`. **If `after-fifo10` is not
   measurably better, say so and recommend dropping the directive.** A max-priority CPython process
   can make the box unreachable and the kernel RT throttle is a safety net, not a justification. Let
   the measurement decide — that is what PLAT-17 asks for, and quietly keeping an unjustified RT
   directive is the outcome to avoid.

## The confound in the paired comparison, which must be stated and not buried

Plan 08's `before` arm was captured on **Buster / armhf / Python 3.7.3 / kernel 5.10**. This plan's
`after` arms are captured on **Bookworm / aarch64 / Python 3.11 / a current kernel**. So a G1 result
does **not** isolate the clock refactor — it compares two whole platforms, of which the clock layer is
one difference among several. This is an unavoidable consequence of doing the OS bump and the clock
work in one phase. It does **not** invalidate the gate (a regression is still a regression, which is
what the gate is for), and it does mean **G1 cannot be quoted as "the clock refactor cost nothing"**.
Put that in the evidence log directly beneath the G1 table, in those words.
</soak_design>
</context>

<tasks>

<task type="auto" tdd="true">
  <name>Task 0: Build the soak runner and machine-check the campaign before a single command goes to the user</name>
  <files>
    /home/ido/mics_core/tools/pulse_timing/clock_soak.py
    /home/ido/mics_core/tests/test_clock_soak.py
    /home/ido/mics_core/tools/pulse_timing/README.md
  </files>
  <behavior>
    `tests/test_clock_soak.py` drives `clock_soak.py` against plan 01's `fake_pigpio` on the dev host
    — no Pi, no `pigpiod`, no real `pigpio`. It asserts:

    - A short synthetic run emits a `header`, N `witness` records, at least one `counters` record and
      exactly one `trailer`, and every line parses as JSON.
    - `delivered` is the value the **shared** clock produced: the test perturbs `get_clock()`'s
      mapping and asserts `delivered` moves with it. A soak that built its own clock would not move,
      and would be measuring a copy of the design.
    - `t_mono_ns` is non-decreasing across the file, and `delivered` is non-decreasing across a
      **simulated wrap** injected with `fake_pigpio.simulate_wrap()`.
    - **`analyse.py --check-wrap` (default mode) exits 0 on the emitted file, and
      `--check-wrap --expect-defect` exits non-zero on it.** Both directions, on this tool's own
      output, proven on the dev host **before** 4.5 hours of hardware time are spent relying on it.
    - The `trailer` carries `n_commanded`, `n_observed`, `n_missing` and the full `counters()` key set
      recorded in `31-C1-SUMMARY.md`. A deliberately suppressed edge yields `n_missing == 1`.
    - **`route` records carry the exact key set from `<soak_design>`, asserted BY NAME.** Every
      `route` record's keys are exactly
      `{"kind","i","tick","a_route","a_t_mono_ns","a_ts_source","b_route","b_t_mono_ns","b_ts_source"}`
      — assert **set equality**, not a subset, so a renamed or missing key fails here on the dev host
      in seconds rather than after Task 1's 4.5-hour soak and Task 2's 2.5-hour campaign. That is the
      cost this pre-flight exists to prevent. Then assert the substance: `a_t_mono_ns ==
      b_t_mono_ns`, both `ts_source` values `"hardware"`, and `a_route`/`b_route` equal to
      `"logging_utils:97"` and `"task:283"`.
    - **Run Task 3's own route check here, verbatim, against the synthetic file.** A pre-flight that
      checks a *different* shape from the analysis does not prevent the mismatch it exists to
      prevent.
    - An exception raised inside a registered callback is **caught, counted and recorded**, and does
      not propagate — `fake_pigpio.fire_edge` propagates exceptions by design (plan 01), so this test
      fails if the runner leaks one.
    - Records are **flushed per line**: a run read part-way still parses. Assert by reading the file
      mid-run.
    - The header records `git_sha`, `kernel`, `board`, `python`, the client path and sha256, and
      `client_patched` (`hasattr(pi, 'synchronize')`), so the artifact is self-describing and cannot
      be confused with a run from a different tree six months later.
  </behavior>
  <action>
    1. Write `tests/test_clock_soak.py` first.

    2. Write `tools/pulse_timing/clock_soak.py` per `<soak_design>`, including its literal `route`
       key set and its instruction on how route b is obtained (a real `Task` with a real
       `Event_Dispatcher`, registered the way `task.py:199` registers it — not a direct
       `dispatch_event` call). Flags: `--out-pin`, `--in-pin`,
       `--interval-s`, `--duration-s`, `--out PATH`, `--route-sample-every N`, `--arm` (a **label**
       recorded in the header, never a code path). It imports the production classes and
       `autopilot.utils.clock.get_clock()` — no reimplementation of the adapter, no private clock.
       Restore outputs to a safe level and release handles on exit, including on SIGINT, and **always
       write the `trailer`, even on interrupt**.

    3. Extend `tools/pulse_timing/README.md` with: the three new record kinds; the PLAT-32 accounting
       table from `<soak_design>` including the honest note that `pigpiod` exposes no dropped-sample
       counter; and **copy-paste blocks for every command in Tasks 1 and 2**. The README is what the
       user actually works from; leaving it theoretical guarantees the campaign hits friction plan 08
       already paid for once.

       Both invocation forms must be in the README, because both are used here and the difference is
       invisible until it fails (plan 08 Task 3 recorded them):
       - the **interactive** form: `cd /opt/mics`, `export PYTHONPATH=/opt/mics`,
         `python3 -m tools.pulse_timing....`;
       - the **`systemd-run`** form used for the long soak, where `WorkingDirectory=` overrides any
         `cd`, so `PYTHONPATH` must be passed as a unit property (`-p Environment=PYTHONPATH=/opt/mics`),
         and the transient unit must use its **own** `RuntimeDirectory` (e.g. `micscap`) — **never**
         `mics`, which `mics-pilot.service` owns and which systemd **deletes** when the borrowing unit
         stops.

    4. **The pre-flight gate — all agent work, on the dev host, run before any checklist goes out.**
       Assert, as exit codes:
       - C1, C2 and C3 all landed: `tests/test_tick_extender.py`, `tests/test_mics_clock.py`,
         `tests/test_single_clock_invariant.py`, `tests/test_event_dispatcher_clock.py`,
         `tests/test_edge_timestamp_end_to_end.py`, `tests/test_stock_pigpio_only.py` and
         `tests/test_clock_block_removed.py` all pass;
       - `--final` runs, produces output, and reports no F3 NTP/clock-block violation (C3's
         retirement held);
       - `py37_gate.py` exits 0 and its closure **did not gain `clock_soak.py`**;
       - plan 08's baseline is present: at least ten `before_*.jsonl` and one
         `wrap_witness_patched.jsonl` under `tools/pulse_timing/captures/`;
       - `31-HARDWARE-VALIDATION.md` exists and has an "after arm" section for this plan to fill.

       **If any of these fails: STOP.** Do not issue Task 1's checklist. The cost of skipping this is
       4.5 hours of the user's hardware time.
  </action>
  <verify>
    <automated>cd /home/ido/mics_core && /home/ido/.venvs/mics_core_dev/bin/python -m pytest -q tests/test_clock_soak.py tests/test_tick_extender.py tests/test_mics_clock.py tests/test_single_clock_invariant.py tests/test_event_dispatcher_clock.py tests/test_edge_timestamp_end_to_end.py tests/test_stock_pigpio_only.py tests/test_clock_block_removed.py --tb=short && /home/ido/.venvs/mics_core_dev/bin/python tools/pulse_timing/py37_gate.py && /home/ido/.venvs/mics_core_dev/bin/python -c "
import glob, pathlib, subprocess, sys
r = subprocess.run([sys.executable, 'tools/pulse_timing/py37_gate.py', '--list'], capture_output=True, text=True)
if r.returncode != 0:
    sys.exit('py37_gate --list failed: %s' % (r.stdout + r.stderr)[:400])
print('clock_soak.py in the py37 closure:', 'clock_soak.py' in r.stdout)
if 'clock_soak.py' in r.stdout:
    sys.exit('clock_soak.py entered the Python 3.7 closure; it is a 3.11-only tool and must stay out')
before = sorted(glob.glob('tools/pulse_timing/captures/before_*.jsonl'))
witness = sorted(glob.glob('tools/pulse_timing/captures/wrap_witness_*.jsonl'))
print('plan 08 baseline captures:', len(before), '| wrap-witness artifacts:', len(witness))
if len(before) < 10 or len(witness) < 1:
    sys.exit('plan 08 baseline is incomplete; the paired comparison and the before/after wrap evidence both depend on it')
LOG = '/home/ido/mics-backend/.planning/phases/31-mics-core-modern-pi-platform-bookworm-64-bit-python-3-11-lgpio-unattended-boot/31-HARDWARE-VALIDATION.md'
t = pathlib.Path(LOG).read_text()
print('after arm occurrences in the evidence log:', t.count('after arm'))
if t.count('after arm') == 0:
    sys.exit('31-HARDWARE-VALIDATION.md has no after-arm section for this plan to fill')
f = subprocess.run(['python3', 'tools/check_tree_integrity.py', '--final'], capture_output=True, text=True)
out = f.stdout + f.stderr
pathlib.Path('/tmp/final31_c4_preflight.txt').write_text(out)
if not out.strip():
    sys.exit('--final produced NO output - it crashed rather than reporting; nothing was verified')
ntp = [l for l in out.splitlines() if l.startswith('VIOLATION') and ('NTP' in l or 'clock' in l.lower())]
if ntp:
    sys.exit('C3 F3 retirement did not hold: %r' % ntp)
print('pre-flight OK: C1-C3 green, --final free of F3 clock violations, py37 closure clean, plan 08 baseline present, evidence log ready')
" && /home/ido/.venvs/mics_core_dev/bin/python tools/pytest_delta.py && python3 tools/check_tree_integrity.py --strict</automated>
  </verify>
  <done>`clock_soak.py` drives the production `assign_cb`/`MicsClock` path and emits plan 06's `witness` shape plus `route`, `counters` and `trailer` records; every `route` record carries exactly the nine-key set fixed in `<soak_design>` with `a_route`/`b_route` naming the two real dispatch routes, asserted by set equality with the same check Task 3 will run; `analyse.py --check-wrap` exits 0 on its output and `--expect-defect` exits non-zero, both proven on the dev host before any hardware time; the README carries both invocation forms with the `RuntimeDirectory=micscap` warning and the PLAT-32 accounting table; the pre-flight gate confirms C1-C3 green, `--final` free of F3 clock violations, `clock_soak.py` outside the py37 closure, plan 08's baseline present and the evidence log ready; delta gate `new failures: 0`; `--strict` exit 0. **Only now may Task 1's checklist be issued.**</done>
</task>

<task type="checkpoint:human-action" gate="blocking">
  <name>Task 1: USER-RUN — the >= 3-wrap soak under load, with a forced clock step in both directions</name>
  <what-built>
    `tools/pulse_timing/clock_soak.py` (Task 0): drives edges on a loopback jumper through the real
    `Digital_Out`/`assign_cb` path, converts every tick through the **same shared `MicsClock` the
    pilot uses**, and records per edge the raw 32-bit tick, the clock's `t_mono_ns`, an independent
    `CLOCK_MONOTONIC` reference, the derived UTC, the provenance flag, both dispatch routes for
    sampled edges, and the clock's counters on every heartbeat.
  </what-built>
  <action>
    AGENT: do not execute anything on the Pi. **Task 0 must have passed** — if it did not run, run it
    before anything else. Then confirm `<hardware_prerequisites>` with the user; if any is missing,
    stop and say so rather than starting a partial run.

    Then present `<how-to-verify>` as a single numbered checklist with literal commands, substituting
    real values for every `<PLACEHOLDER>`, and **say the time cost first**: ~4.5 hours, of which the
    user must be present at roughly T+60 min and T+120 min for the two clock steps. State that
    **nothing here is destructive** — no card is reflashed, every artifact is a new file, and the two
    `date -s` steps are reverted by re-enabling NTP at the end.

    Then STOP and wait. Do not interleave agent work between the user's steps. When the user replies,
    read back over SSH (read-only) to confirm what landed.

    **Why this task cannot be shortened.** The wrap period is 71.58 minutes and PLAT-29 requires
    **>= 3** wraps proven, so > 3.6 hours is arithmetic, not padding. The defect is a
    once-per-71.6-minutes event; a one-hour run can miss it entirely and prove nothing.
  </action>
  <how-to-verify>
    Run these **on the spare Pi provisioned in plan 09**. Substitute `<SPARE_IP>`, `<OUT_PIN>` and
    `<IN_PIN>` once at the top. Use the **same pins plan 08 used**, or tell the agent they changed.

    **Step 1 — confirm you are about to measure a STOCK client (on the spare Pi):**
    ```bash
    /home/pi/.venv/mics/bin/python -c "import pigpio,hashlib;print(pigpio.__file__);print(hashlib.sha256(open(pigpio.__file__,'rb').read()).hexdigest());print('synchronize',hasattr(pigpio.pi,'synchronize'));print('ticks_to_timestamp',hasattr(pigpio.pi,'ticks_to_timestamp'))"
    systemctl is-active chronyd; command -v pigpiod; pigpiod -v
    systemctl is-active mics-pilot; ps -o pid=,ppid=,args= -C pigpiod
    chronyc tracking | head -5
    ```
    Both `hasattr` lines must print `False`. Paste all of it — the sha256 goes into the evidence log
    so the artifact is attributable to an exact client.

    **Step 2 — get the harness onto the card (run on your laptop):**
    ```bash
    rsync -avz --exclude captures/ -e "ssh -i ~/.ssh/pi_mics" \
      /home/ido/mics_core/tools/pulse_timing/ \
      pi@<SPARE_IP>:/opt/mics/tools/pulse_timing/
    ```
    No `--delete`. No git on the Pi. `--exclude captures/` keeps the committed JSONL off the card —
    they are megabytes and they are not inputs.

    **Step 3 — start the load and the soak (on the spare Pi).** The soak runs as a transient systemd
    unit so it survives your SSH session and gets a sane environment:
    ```bash
    sudo systemd-run --unit=mics-stress --collect \
      /usr/bin/stress-ng --cpu 4 --io 2 --vm 1 --vm-bytes 128M --timeout 16200s

    sudo systemd-run --unit=mics-soak --collect \
      -p Environment=PYTHONPATH=/opt/mics \
      -p RuntimeDirectory=micscap \
      -p WorkingDirectory=/run/micscap \
      /home/pi/.venv/mics/bin/python -m tools.pulse_timing.clock_soak \
        --out-pin <OUT_PIN> --in-pin <IN_PIN> \
        --interval-s 1 --duration-s 15600 \
        --route-sample-every 100 \
        --arm soak-fifo10 \
        --out /tmp/soak_after.jsonl

    date; echo "soak started; >= 3 wraps needs 3.6 h, this runs 4.33 h"
    ```
    **`RuntimeDirectory=micscap`, never `mics`** — `mics` belongs to `mics-pilot.service` and systemd
    **deletes** it when the borrowing unit stops, which would break the pilot.

    **Step 4 — force the clock steps. Be present for these two.**
    At roughly **T+60 minutes**:
    ```bash
    date; sudo timedatectl set-ntp false; sudo date -s '+1 hour'; date
    ```
    At roughly **T+120 minutes**:
    ```bash
    date; sudo date -s '-1 hour'; date
    ```
    **Record the exact `date` output of all six lines.** The agent needs the applied amounts and the
    moments to line them up against the artifact. Leave NTP off until Step 6.

    **Step 5 — after it finishes (~4.5 h), sanity-check locally:**
    ```bash
    systemctl is-active mics-soak; echo "(inactive means it finished)"
    wc -l /tmp/soak_after.jsonl
    tail -3 /tmp/soak_after.jsonl
    journalctl -u mics-soak -b --no-pager | tail -20
    # pigpiod is a CHILD of mics-pilot (PLAT-33 withdrawn), so its output lands in the pilot's journal.
    journalctl -u mics-pilot -b --no-pager > /tmp/pigpiod_soak.log; wc -l /tmp/pigpiod_soak.log
    ps -o pid=,ppid=,args= -C pigpiod
    sudo systemctl stop mics-stress
    ```

    **Step 6 — put the clock back:**
    ```bash
    sudo timedatectl set-ntp true; sleep 20; chronyc tracking | head -5; date
    ```

    **Step 7 — copy everything back (run on your laptop):**
    ```bash
    rsync -avz -e "ssh -i ~/.ssh/pi_mics" \
      pi@<SPARE_IP>:/tmp/soak_after.jsonl pi@<SPARE_IP>:/tmp/pigpiod_soak.log \
      /home/ido/mics_core/tools/pulse_timing/captures/
    ```

    **If the file contains fewer than 3 wraps** — the run was cut short, or `pigpiod` was restarted
    mid-run and the tick reset — **say so** rather than letting a short file be analysed as a pass. A
    daemon restart resets the tick and looks like a wrap without being one. Re-run for longer.

    **Correct these commands against `tools/pulse_timing/README.md` if it says otherwise.** The README
    is the authority; these are written from the design and flag names may differ.
  </how-to-verify>
  <resume-signal>Reply "soak done" with the client path and sha256, the two `hasattr` results, the six `date` lines from the two steps, the soak line count, and the tails of both journals — or paste any error.</resume-signal>
</task>

<task type="checkpoint:human-action" gate="blocking">
  <name>Task 2: USER-RUN — the paired "after" campaign, the clock-step captures, chrt and the fail-safe check</name>
  <what-built>
    `tools/pulse_timing/capture.py` (plan 06), unchanged since plan 08 took the "before" arm — same
    program, same format, same profiles, same board, same jumper. Plus `analyse.py --check-step`,
    which asserts a clock step moves the derived UTC by exactly the applied amount and moves no
    interval.
  </what-built>
  <action>
    AGENT: do not execute anything on the Pi. Present `<how-to-verify>` as a numbered checklist with
    literal commands, **correcting every flag name against `tools/pulse_timing/README.md`** — the
    README is the authority and this plan is written from the design. Say the time cost first
    (~2.5 hours attended). Then STOP and wait.

    **Say plainly to the user, as well as in the log, why this arm exists.** C1-C3 changed the
    timestamping, not the pulse generation, so this is a **guard against having accidentally broken
    the pulse path** — not the clock evidence. It is worth 2.5 hours because an accidental break there
    is a data-quality defect no functional test would catch. It must not be reported as proof that the
    clock work cost nothing.
  </action>
  <how-to-verify>
    Same `<SPARE_IP>`, `<OUT_PIN>`, `<IN_PIN>` as Task 1, and the same jumper.

    **Step 1 — the twenty "after" captures.** Five profiles x two loads x two scheduling arms.
    ```bash
    cd /opt/mics && export PYTHONPATH=/opt/mics

    # --- arm: after-other (pilot unit at DEFAULT scheduling) ---
    sudo systemctl set-property mics-pilot.service CPUSchedulingPolicy=other
    sudo systemctl restart mics-pilot
    for L in idle loaded; do
      if [ "$L" = loaded ]; then
        sudo systemd-run --unit=mics-stress --collect /usr/bin/stress-ng --cpu 4 --io 2 --vm 1 --vm-bytes 128M --timeout 1800s
      fi
      for P in valve valve_short ttl train mixed; do
        /home/pi/.venv/mics/bin/python -m tools.pulse_timing.capture --profile $P --arm after-other \
          --out-pin <OUT_PIN> --in-pin <IN_PIN> --load-label $L \
          --out /tmp/after-other_${P}_${L}.jsonl
      done
      sudo systemctl stop mics-stress
    done

    # --- arm: after-fifo10 (the directive plan 05 shipped) ---
    sudo systemctl revert mics-pilot.service
    sudo systemctl restart mics-pilot
    for L in idle loaded; do
      if [ "$L" = loaded ]; then
        sudo systemd-run --unit=mics-stress --collect /usr/bin/stress-ng --cpu 4 --io 2 --vm 1 --vm-bytes 128M --timeout 1800s
      fi
      for P in valve valve_short ttl train mixed; do
        /home/pi/.venv/mics/bin/python -m tools.pulse_timing.capture --profile $P --arm after-fifo10 \
          --out-pin <OUT_PIN> --in-pin <IN_PIN> --load-label $L \
          --out /tmp/after-fifo10_${P}_${L}.jsonl
      done
      sudo systemctl stop mics-stress
    done
    ```

    **Step 2 — PLAT-17: does the policy reach the threads that matter?** With the pilot running under
    the shipped `fifo10` unit:
    ```bash
    PID=$(systemctl show -p MainPID --value mics-pilot)
    echo "pilot MainPID=$PID"
    for t in /proc/$PID/task/*; do
      TID=${t##*/}
      printf '%s %s ' "$TID" "$(cat $t/comm)"
      chrt -p "$TID"
    done
    echo '--- pigpiod, for comparison ---'
    PGD=$(pgrep -x pigpiod | head -1)
    for t in /proc/$PGD/task/*; do TID=${t##*/}; printf '%s %s ' "$TID" "$(cat $t/comm)"; chrt -p "$TID"; done
    ```
    Paste the whole table.

    **Step 3 — the clock-step captures (PLAT-25), four short runs.** One `train` capture straddling
    one step each, so `--check-step` has an unambiguous single amount per file.
    ```bash
    cd /opt/mics && export PYTHONPATH=/opt/mics
    sudo timedatectl set-ntp false

    /home/pi/.venv/mics/bin/python -m tools.pulse_timing.capture --profile train --arm after-fifo10 \
      --out-pin <OUT_PIN> --in-pin <IN_PIN> --load-label idle --duration-s 120 \
      --out /tmp/step_fwd_idle.jsonl &
    sleep 45; date; sudo date -s '+1 hour'; date; wait

    /home/pi/.venv/mics/bin/python -m tools.pulse_timing.capture --profile train --arm after-fifo10 \
      --out-pin <OUT_PIN> --in-pin <IN_PIN> --load-label idle --duration-s 120 \
      --out /tmp/step_bwd_idle.jsonl &
    sleep 45; date; sudo date -s '-1 hour'; date; wait

    sudo systemd-run --unit=mics-stress --collect /usr/bin/stress-ng --cpu 4 --io 2 --timeout 400s
    /home/pi/.venv/mics/bin/python -m tools.pulse_timing.capture --profile train --arm after-fifo10 \
      --out-pin <OUT_PIN> --in-pin <IN_PIN> --load-label loaded --duration-s 120 \
      --out /tmp/step_fwd_loaded.jsonl &
    sleep 45; date; sudo date -s '+1 hour'; date; wait
    /home/pi/.venv/mics/bin/python -m tools.pulse_timing.capture --profile train --arm after-fifo10 \
      --out-pin <OUT_PIN> --in-pin <IN_PIN> --load-label loaded --duration-s 120 \
      --out /tmp/step_bwd_loaded.jsonl &
    sleep 45; date; sudo date -s '-1 hour'; date; wait
    sudo systemctl stop mics-stress

    sudo timedatectl set-ntp true; sleep 20; chronyc tracking | head -5; date
    ```
    **Record the `date` output either side of every step.**

    **Step 4 — the physical fail-safe check.** Put the meter across each output device in turn, then:
    ```bash
    sudo systemctl stop mics-pilot        # ARM 1 -- clean stop: SIGTERM, so kill_proc's handler CAN run
    ps -o pid=,ppid=,args= -C pigpiod || echo "pigpiod: not running"
    # ... then restart the pilot and repeat with:
    sudo systemctl kill -s SIGKILL mics-pilot   # ARM 2 -- no handler runs at all
    ```
    Report **open / closed / chatter, per device**. Expect the pigpio behaviour: the **daemon outlives
    the client and keeps driving the pin**, so a solenoid energised at the moment of the kill may stay
    energised. That is the pre-existing risk, not one this phase introduced — record what actually
    happens per device rather than what is expected.
    ```bash
    sudo systemctl start mics-pilot; systemctl is-active mics-pilot
    ```

    **Step 5 — copy everything back (run on your laptop):**
    ```bash
    rsync -avz -e "ssh -i ~/.ssh/pi_mics" \
      pi@<SPARE_IP>:/tmp/after-*.jsonl pi@<SPARE_IP>:/tmp/step_*.jsonl \
      /home/ido/mics_core/tools/pulse_timing/captures/
    ```
  </how-to-verify>
  <resume-signal>Reply "after arm done" with the full `chrt` table, the `date` output either side of all four steps, the per-device fail-safe result for BOTH arms (clean stop and `SIGKILL`) plus whether `pigpiod` survived each, and confirmation that all 24 files copied — or paste any error.</resume-signal>
</task>

<task type="auto">
  <name>Task 3: Analyse everything, judge the gates, and complete the phase evidence log</name>
  <files>
    /home/ido/mics-backend/.planning/phases/31-mics-core-modern-pi-platform-bookworm-64-bit-python-3-11-lgpio-unattended-boot/31-HARDWARE-VALIDATION.md
    /home/ido/mics_core/tools/pulse_timing/README.md
  </files>
  <action>
    All agent work, on the dev machine. No SSH except read-only confirmation of what landed.

    1. **The soak — the phase's central claim (PLAT-25/29/30).** Run `analyse.py --check-wrap` in its
       **DEFAULT** direction over `captures/soak_after.jsonl`. It must exit **0**. Report:
       - the number of wraps observed in the **raw** `tick` series and the interval between them,
         derived from the file's own `t_mono_ns`, quoted against the predicted **71.58 min**. Fewer
         than 3 is a **fail on duration** — say so and stop rather than reporting a pass;
       - that `t_mono_ns` is non-decreasing across the whole file, which is the reference that makes
         any claim about `delivered` meaningful;
       - **zero backward jumps in `delivered`**, quoted beside plan 08's measured magnitude
         (~4294.97 s): the same tool, the same assertion, the opposite verdict, before and after.
         **This pairing is the headline result of the phase.**
       If `--check-wrap` exits non-zero, report the index, the magnitude and the raw ticks either
       side, and do **not** proceed to call anything else a pass.

    2. **The two-route agreement, on hardware, over hours.** From the `route` records: every sampled
       edge produced **two** payloads with **equal** `t_mono_ns` and `ts_source == "hardware"` on
       both. Report the sample count and the disagreement count (must be 0). Then state the
       complement C2's summary handed forward: the dev-host test proves the mechanism, this proves it
       **survives continuous operation**, and neither substitutes for the other — the design being
       replaced fails precisely by decaying over runtime.

    3. **Provenance completeness (PLAT-31).** Every `witness` and `route` record carries a valid
       `ts_source`. Count records by source and report the split. A record with no provenance is a
       fail.

    4. **PLAT-32 drop accounting.** From the trailer: `n_commanded`, `n_observed`, `n_missing`, and
       every counter in `<soak_design>`'s table. Then inspect `captures/pigpiod_soak.log` — which is
       the **pilot unit's** journal, because PLAT-33 was withdrawn and `pigpiod` is a child process
       with no journal of its own — for the daemon's own warnings, and quote the window. State that
       provenance in the log: "no warnings in `journalctl -u pigpiod`" would be a meaningless claim
       here, since that unit does not exist. **Criterion: `n_missing == 0` and every counter
       zero.** If any is non-zero, report it **with its count and its position in time**, and say
       plainly whether **PLAT-32 passed** (the loss was detected and counted) while the **acceptance
       gate failed** (the loss occurred). Those are two different verdicts and conflating them is how
       a soft pass gets recorded. State the instrument's limit explicitly: **`pigpiod` exposes no
       dropped-sample counter to the client**, so this accounting is commanded-vs-observed plus our
       own counters plus the daemon's log — not a daemon-reported figure.

    5. **The clock steps (PLAT-25).** `analyse.py --check-step +3600` on the two forward captures and
       `--check-step -3600` on the two backward ones. All four must pass: `t_mono_ns` continuous with
       no discontinuity at the step, and `t_utc_ns` stepping by **exactly** the applied amount and by
       nothing else. Report the applied amounts from the user's `date` output beside the measured
       ones. Say explicitly that the UTC step **is correct behaviour** — that sentence is what keeps
       the claim honest.

    6. **The paired comparison (PLAT-24).** `analyse.py --gate before after` for every profile x load,
       for **both** after arms, against plan 08's committed baseline. Report G1 (`err_p99` and
       `err_sd` <= 1.25x, `n_missing == 0`) and the absolute thresholds separately.
       **Immediately beneath the table, and in these words, record the confound:** the `before` arm is
       Buster / armhf / Python 3.7.3 / kernel 5.10 and the `after` arms are Bookworm / aarch64 /
       Python 3.11, so G1 compares two whole platforms and **cannot be quoted as "the clock refactor
       cost nothing"**. It remains a valid regression gate. Also restate that the pulse path itself
       was never modified by this phase, so a pass here mostly means nothing was accidentally broken.

    7. **PLAT-17, decided by measurement.** Tabulate the user's `chrt` output — TID, comm, policy,
       priority — for the pilot and, for comparison, `pigpiod`. Then compare `after-other` against
       `after-fifo10` on `err_p99`, `err_sd` and `n_missing`, idle and loaded. **Give a verdict:**
       keep the directive, or recommend dropping it. If `fifo10` is not measurably better, recommend
       dropping it — plan 05 shipped it explicitly as a hypothesis and named this task as the
       measurement.

    8. **Complete `31-HARDWARE-VALIDATION.md`'s "after arm" section**, with numbers rather than
       adjectives: hardware inventory (board revision, serial, OS, kernel, Python, `pigpiod -v`,
       client path + sha256, both `hasattr` results, pin pair); the soak verdict with wrap count,
       intervals and backward-jump count; the before/after wrap comparison as the headline; the
       two-route agreement; the provenance split; the PLAT-32 accounting; the four clock-step verdicts
       with applied vs measured; the G1 table with the confound paragraph; the `chrt` table and the
       PLAT-17 verdict; the per-device fail-safe results. Give every returned capture an md5 so each
       artifact is re-identifiable.

    9. **Write a real "NOT PROVEN HERE" section.** It is a deliverable, not a disclaimer. At minimum:
       - the phase never ran on the **live rig** — all evidence is from spare hardware (ROADMAP);
       - the soak drives a **loopback jumper**, not real solenoids, odour valves or an animal;
       - a loopback cannot distinguish "the output edge was late" from "the input edge was sampled or
         reported late", which is why plan 08's one-time logic-analyser calibration exists — cite its
         numeric verdict here;
       - the G1 confound from step 6;
       - `pigpiod` is **unmaintained**, an accepted standing risk (ROADMAP), mitigated by the clock
         layer being library-independent;
       - **PLAT-12 through PLAT-16 are deferred**, so Pi 5 is not supported and pigpio is not removed;
       - the fail-safe behaviour is pigpio's: the daemon outlives the client and keeps driving the
         pin, so this is a pre-existing risk that this phase did not remove;
       - whatever else the run actually surfaced.

    10. Update `tools/pulse_timing/README.md` with the commands **as actually run**, corrected against
        what the user reported. The README is what the next campaign works from; leaving it
        theoretical guarantees the friction is paid a third time.
  </action>
  <verify>
    <automated>cd /home/ido/mics_core && /home/ido/.venvs/mics_core_dev/bin/python -m tools.pulse_timing.analyse --check-wrap tools/pulse_timing/captures/soak_after.jsonl && /home/ido/.venvs/mics_core_dev/bin/python -m tools.pulse_timing.analyse --check-step +3600 tools/pulse_timing/captures/step_fwd_idle.jsonl && /home/ido/.venvs/mics_core_dev/bin/python -m tools.pulse_timing.analyse --check-step -3600 tools/pulse_timing/captures/step_bwd_idle.jsonl && /home/ido/.venvs/mics_core_dev/bin/python -m tools.pulse_timing.analyse --check-step +3600 tools/pulse_timing/captures/step_fwd_loaded.jsonl && /home/ido/.venvs/mics_core_dev/bin/python -m tools.pulse_timing.analyse --check-step -3600 tools/pulse_timing/captures/step_bwd_loaded.jsonl && /home/ido/.venvs/mics_core_dev/bin/python -c "
import json, sys
soak = 'tools/pulse_timing/captures/soak_after.jsonl'
recs = [json.loads(l) for l in open(soak) if l.strip()]
kinds = {}
for r in recs:
    kinds[r.get('kind')] = kinds.get(r.get('kind'), 0) + 1
print('soak record kinds:', kinds)
tr = [r for r in recs if r.get('kind') == 'trailer']
if len(tr) != 1:
    sys.exit('expected exactly one trailer record, found %d - the run did not finish cleanly' % len(tr))
tr = tr[0]
print('trailer:', {k: tr[k] for k in sorted(tr) if k != 'counters'})
print('counters:', tr['counters'])
if tr['n_missing'] != 0:
    sys.exit('PLAT-32 acceptance FAILED: n_missing=%d of %d commanded edges. The loss WAS detected and counted (PLAT-32 satisfied); the acceptance gate still fails.' % (tr['n_missing'], tr['n_commanded']))
# CORRECTED 2026-08-17. An earlier draft watched 'out_of_order', 'fit_rejected' and
# 'bracket_rejected' too. C1 SS7 classifies those as activity / reported-not-asserted, not faults --
# and 'out_of_order' is the counter Case C exists to move. This soak runs a heartbeat thread against
# a notify thread under deliberate CPU load, i.e. the exact condition that produces it, so the old
# list failed a CORRECT implementation after 4.33 h of hardware time.
fault = ('ambiguous_gap','monotonic_violation','convert_failed','heartbeat_missed')
activity = ('wraps','out_of_order','duplicates','refits')
reported = ('bracket_rejected','fit_rejected')
print('activity counters (expected non-zero):', {k: tr['counters'].get(k) for k in activity})
print('reported, not asserted:', {k: tr['counters'].get(k) for k in reported})
bad = {k: v for k, v in tr['counters'].items() if k in fault and v}
if bad:
    sys.exit('clock FAULT counters non-zero over the soak: %r' % bad)
wit = [r for r in recs if r.get('kind') == 'witness']
ticks = [r['tick'] for r in wit]
wraps = sum(1 for a, b in zip(ticks, ticks[1:]) if b < a)
print('raw-tick wraps observed in the soak:', wraps)
if wraps < 3:
    sys.exit('only %d wraps observed; PLAT-29 requires >= 3 (> 3.6 h). The run was too short to prove anything.' % wraps)
delivered = [r['delivered'] for r in wit]
back = [(i, (delivered[i-1] - delivered[i]) / 1e9) for i in range(1, len(delivered)) if delivered[i] < delivered[i-1]]
print('backward jumps in the delivered series:', len(back))
if back:
    sys.exit('BACKWARD JUMPS PRESENT after the fix (index, seconds): %r' % back[:5])
mono = [r['t_mono_ns'] for r in wit]
if any(b < a for a, b in zip(mono, mono[1:])):
    sys.exit('the independent CLOCK_MONOTONIC reference is not non-decreasing; the artifact cannot support any claim')
nosrc = [r.get('i') for r in wit if r.get('ts_source') not in ('hardware', 'software')]
print('witness records with a missing/invalid ts_source:', len(nosrc))
if nosrc:
    sys.exit('PLAT-31: %d records carry no valid provenance flag' % len(nosrc))
routes = [r for r in recs if r.get('kind') == 'route']
print('route sample pairs:', len(routes))
WANT = {'kind', 'i', 'tick', 'a_route', 'a_t_mono_ns', 'a_ts_source', 'b_route', 'b_t_mono_ns', 'b_ts_source'}
badkeys = [r.get('i') for r in routes if set(r) != WANT]
print('route records with the wrong key set:', len(badkeys))
if badkeys:
    sys.exit('route records do not carry the key set fixed in <soak_design>; Task 0 was supposed to catch this BEFORE the hardware time: first offenders %r' % badkeys[:5])
badroute = [r.get('i') for r in routes if (r.get('a_route'), r.get('b_route')) != ('logging_utils:97', 'task:283')]
print('route records with unexpected route labels:', len(badroute))
if badroute:
    sys.exit('route records are not labelled by the two real dispatch routes, so agreement cannot be attributed to them: %r' % badroute[:5])
dis = [r for r in routes if r.get('a_t_mono_ns') != r.get('b_t_mono_ns') or r.get('a_ts_source') != 'hardware' or r.get('b_ts_source') != 'hardware']
print('two-route disagreements:', len(dis))
if not routes:
    sys.exit('no route records were sampled; the on-hardware two-route agreement was never measured')
if dis:
    sys.exit('the two dispatch routes disagreed on %d of %d sampled edges' % (len(dis), len(routes)))
print('soak verdict OK: >=3 wraps, zero backward jumps, monotonic reference intact, provenance complete, routes agree, n_missing=0')
" && /home/ido/.venvs/mics_core_dev/bin/python -c "
import glob, os, subprocess, sys
after = sorted(glob.glob('tools/pulse_timing/captures/after-*.jsonl'))
print('after-arm captures present:', len(after))
if len(after) < 20:
    sys.exit('expected 20 after-arm captures (5 profiles x 2 loads x 2 sched arms), found %d' % len(after))
fails = []
for a in after:
    b = os.path.basename(a).replace('after-fifo10_', 'before_').replace('after-other_', 'before_')
    b = os.path.join('tools/pulse_timing/captures', b)
    if not os.path.exists(b):
        sys.exit('no matching baseline for %s (expected %s) - the pairing is broken' % (a, b))
    r = subprocess.run([sys.executable, '-m', 'tools.pulse_timing.analyse', '--gate', b, a], capture_output=True, text=True)
    if r.returncode != 0:
        fails.append((os.path.basename(a), (r.stdout + r.stderr).strip().splitlines()[-1:]))
print('G1/absolute gate failures:', len(fails))
for f in fails:
    print('  ', f)
if fails:
    sys.exit('PLAT-24 paired gate failed for %d captures' % len(fails))
" && /home/ido/.venvs/mics_core_dev/bin/python -c "
import pathlib, sys
LOG = '/home/ido/mics-backend/.planning/phases/31-mics-core-modern-pi-platform-bookworm-64-bit-python-3-11-lgpio-unattended-boot/31-HARDWARE-VALIDATION.md'
t = pathlib.Path(LOG).read_text()
need = ['after arm', 'NOT PROVEN', 'chrt', 'PLAT-17', 'PLAT-24', 'PLAT-25', 'PLAT-32', 'backward jump', 'confound', 'fail-safe', 'sha256']
for n in need:
    print('%r occurrences: %d' % (n, t.count(n)))
missing = [n for n in need if t.count(n) == 0]
if missing:
    sys.exit('31-HARDWARE-VALIDATION.md is missing required content: %r' % missing)
print('evidence log complete')
" && /home/ido/.venvs/mics_core_dev/bin/python tools/pytest_delta.py && python3 tools/check_tree_integrity.py --strict</automated>
  </verify>
  <done>`--check-wrap` exits 0 in its DEFAULT direction over a soak containing >= 3 real wraps with zero backward jumps, and the result is recorded beside plan 08's measured ~4294.97 s jump from the same tool; all four `--check-step` runs pass with the UTC moving by exactly the applied amount and no interval moving; every sampled edge's two dispatch routes agree on `t_mono_ns` and both are hardware-stamped; every record carries a valid provenance flag; `n_missing == 0` and every clock/dispatcher FAULT counter is zero (activity counters are printed, not asserted -- see C1 SS7's three classes), with the `pigpiod` journal window inspected and the instrument's limit stated; all twenty paired captures pass G1 and the absolute thresholds, with the platform confound recorded beneath the table; the `chrt` table and a PLAT-17 keep-or-drop verdict are recorded; `31-HARDWARE-VALIDATION.md` carries the full "after arm" section, per-capture md5s and a substantive NOT PROVEN section; delta gate `new failures: 0`; `--strict` exit 0.</done>
</task>

</tasks>

<verification>
1. `/home/ido/.venvs/mics_core_dev/bin/python -m tools.pulse_timing.analyse --check-wrap tools/pulse_timing/captures/soak_after.jsonl`
   -> exit 0 (default direction, zero backward jumps)
2. `/home/ido/.venvs/mics_core_dev/bin/python -m tools.pulse_timing.analyse --check-step +3600 tools/pulse_timing/captures/step_fwd_idle.jsonl`
   and the other three -> exit 0
3. `ls tools/pulse_timing/captures/after-*.jsonl | wc -l` -> 20
4. `python3 -c "import json,sys; recs=[json.loads(l) for l in open('/home/ido/mics_core/tools/pulse_timing/captures/soak_after.jsonl') if l.strip()]; tr=[r for r in recs if r.get('kind')=='trailer'][0]; print(tr['n_commanded'], tr['n_observed'], tr['n_missing']); sys.exit(0 if tr['n_missing']==0 else 'dropped samples: %d' % tr['n_missing'])"`
   -> exit 0
5. `python3 tools/check_tree_integrity.py --strict` -> exit 0, `30 protected files`, `0 violations`
6. `python3 tools/check_tree_integrity.py --final` -> runs, produces output, no F3 NTP/clock-block
   violation; remaining failures named per F-check in the summary
7. `31-HARDWARE-VALIDATION.md` contains the after-arm section, the `chrt` table, the PLAT-17 verdict,
   the G1 confound paragraph and a substantive NOT PROVEN section
</verification>

<success_criteria>
- The 71.6-minute backward jump is proven **gone** across >= 3 real wraps under load, by the same
  tool and the same assertion that proved it **present** in plan 08. That before/after pairing is the
  phase's headline evidence, and it is not vacuous.
- A wall-clock step in both directions moves the derived UTC by exactly the step and moves no
  interval, measured four times, idle and loaded.
- Both event paths agree on the same physical edge after hours of continuous operation — the property
  the current design loses by decaying, now measured over the decay window.
- Every event carries a correct provenance flag, and dropped samples are counted rather than silent,
  with the instrument's real limits stated rather than implied.
- The pulse path is proven not to have been broken, against plan 08's baseline, **with the platform
  confound recorded** so the result is not over-claimed.
- PLAT-17 is settled by a measurement with a keep-or-drop verdict, not by a belief carried forward.
- The phase evidence log ends with a NOT PROVEN section a reviewer can act on.
</success_criteria>

<output>
After completion, create
`.planning/phases/31-mics-core-modern-pi-platform-bookworm-64-bit-python-3-11-lgpio-unattended-boot/31-C4-SUMMARY.md`.

State plainly, and first:
- whether `--check-wrap` passed in its default direction, the wrap count, and the measured
  backward-jump count quoted against plan 08's measured magnitude — **if it did NOT pass, that fact
  goes first and in bold**, because PLAT-29/30 and the phase's central claim rest on it;
- the four `--check-step` verdicts with applied vs measured amounts;
- the two-route agreement count and the provenance split;
- the PLAT-32 accounting, with an explicit statement of which verdict applies if any counter moved
  (PLAT-32 satisfied but gate failed, versus both passed);
- the G1 table verdict **with the platform confound in the same paragraph**;
- the `chrt` table and the PLAT-17 keep-or-drop recommendation, with the numbers behind it;
- the per-device fail-safe results;
- the `--final` per-F-check verdict at phase exit;
- the NOT PROVEN list, verbatim, so it survives outside the evidence log.
</output>
