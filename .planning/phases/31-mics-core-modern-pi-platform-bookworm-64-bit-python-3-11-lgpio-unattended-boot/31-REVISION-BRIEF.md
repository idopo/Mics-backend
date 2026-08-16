# Phase 31 — Revision Brief (feed this to the planner)

> ## ⚠ READ THIS FIRST — state of the revision at handoff (2026-08-16)
>
> A `gsd-planner` revision pass was dispatched against these blockers and **was killed mid-run**.
> It had partially edited **5 of 16 plans** (`31-06`, `31-08`, `31-10`, `31-15`, `31-16`) without
> committing, and its last action was "rewriting the validation contract to match the new waves".
>
> **The working tree was deliberately reset to the clean `a052651` plan set.** The abandoned diff is
> preserved at `31-partial-revision-ABANDONED.patch` (148 lines) purely as a reference — **do not
> `git apply` it.** A half-applied revision is more dangerous than none: e.g. `31-16` may carry B7's
> `PYTHONPATH` fix without B8's `RuntimeDirectory` fix, which *looks* done but still deletes the
> running pilot's FIFO. Skim it for ideas if useful, then redo the revision properly from this brief.
>
> **So: every blocker below is OUTSTANDING. The plans on disk are the unrevised originals.**

**Status as of 2026-08-16:** 16 plans exist at commit `a052651`. The plan-checker ran and found
**8 blockers, 10 warnings, 3 info**. A revision pass was dispatched but **had not committed** when
the session ended — assume the plans on disk are still the *unrevised* originals and verify with
`git log --oneline .planning/phases/31-*/` before doing anything.

**One extra blocker (B9) was found after the checker ran** — see below and CONTEXT.md §13.

**How to resume:** hand this file, `CONTEXT.md` (especially §11 locked decisions, §12 corrections,
§13 the single-clock invariant), `31-RESEARCH.md` and `31-VALIDATION.md` to `gsd-planner` in
revision mode. Do **not** replan from scratch — the checker confirmed the structure is sound.

---

## What the checker verified as CORRECT (do not re-litigate)

- **Requirement coverage complete** — PLAT-01..26 all appear in some plan's `requirements`.
  PLAT-26 (planner-added, dev-host pytest harness) is properly recorded in REQUIREMENTS.md at
  line 523 and the phase-mapping row at line 268.
- **`--rebaseline` appears 17 times, every one a prohibition.** Zero instructions to run it.
- **All three expected hand-edits have a real, named task** — `PORT_CALIBRATION` (02-T1 step 3;
  the approach is correct — `f2_prefs` at `final_checks.py:107-109` is an *absence* assertion),
  prefs rename (04-T1 steps 3-4), `Event_Dispatcher.py` sha256 (14-T2).
- **Locked decisions §11 honored literally** — plan 13 T2 asserts the literal
  `tx_pulse(h, pin, 8000, 8000, 0, 0)` and explicitly forbids recomputing from a frequency.
- **§12 corrections all propagated** — `/boot/firmware/`, `pinctrl-bcm2711`, `LG_WD`/
  `RuntimeDirectory`, `StartLimitIntervalSec=0`, SCHED_FIFO-as-hypothesis.
- **Hard rules honored** — deploy uses `git archive | ssh … tar -x` (git stays on the dev host);
  no `rsync --delete`; no agent-executed Python on the Pi; journald-vs-pilot-logs distinction
  guarded in plan 05; `Message`/`hardware_state` carved out in 02, 03, 11, 12, 13, 15.
- **No scope creep** — every CONTEXT §7 out-of-scope item is absent from all 16 plans.
- **Dependency graph acyclic**, wave = max(dep)+1 holds everywhere except B1.
- **Plan 09's provisioning-only pass condition** is stated as an expected outcome, not
  green-washing. **Plan 03 does require an evidence-based dependency audit** and refuses to
  hardcode 7.

---

## BLOCKERS

### B1 — Plan 05 missing a dependency on plan 04; the wave-4 parallel pair cannot both run
`31-05-PLAN.md` declares `depends_on: ["31-03"]`, wave 4 — same wave as plan 04. But 05-T1 requires
every `ExecStart` path in `deploy/*.service` to exist, and `mics-prefs.service`'s `ExecStart` is
`/opt/mics/deploy/render-prefs.sh`, which **plan 04 T2 creates**. 05-T2/T3 verify with `shellcheck`,
which plan 04 T2 installs — and `shellcheck` is **not currently installed on this dev host**
(verified live). 05's verification globs `shellcheck deploy/*.sh`, including plan 04's file.

**Fix:** `depends_on: ["31-03", "31-04"]`, wave 5. Plan 06 stays wave 4; plan 07 → wave 6;
shift everything downstream by one. Update `31-VALIDATION.md`'s wave column to match.

### B2 — PLAT-18/19's wiring is owned by no plan; the phase's headline claim has no deliverer
Plan 14's `key_links` claim `edge callback ts_ns → ZMQ payload t_mono_ns`, and T1 step 6 says
"update the callers" — but plan 14's `files_modified` is only `Event_Dispatcher.py`,
`tree_protect_list.json`, and its test. The real bridge is the `@log_action` wrapper at
`autopilot/autopilot/utils/logging_utils.py:55` and `:97`, **in no plan's `files_modified`**.
Other `dispatch_event` call sites: `Tracker.py:91`, `FiniteDeterministicAutomaton.py:18`,
`mics_task.py:386,392,408,455`, `task.py:283,325`, `pilot.py:1100`, plus the two **protected**
files `external_hardware_binding.py:118` / `external_hardware_ingress.py:45`.

Consequences: (a) `ts_mono_ns` never reaches the wire — plan 12 threads it to the class boundary,
plan 14 stops at the dispatcher signature, nothing joins them; (b) wiring the two
`external_hardware_*` files means **two more protected digests**, contradicting plan 14 T2's
"exactly one entry changed" assertion and its "if more than one file is flagged, stop".

**Fix:** add `logging_utils.py` (and any other genuine bridging caller) to plan 14's
`files_modified`; add a test asserting an injected `ts_ns` survives `@log_action` →
`dispatch_event` → payload `t_mono_ns` **unchanged**; state explicitly whether the two protected
`external_hardware_*` files are in or out of scope, and if in, budget the extra manifest edits and
relax the one-line-diff assertion.

### B3 — Plan 15 Task 2's `<automated>` verify can never fail
`… && --strict && --final; echo "final exit=$?"` — the list's exit status is `echo`'s, always 0.
`test_clock_block_removed.py`, the `_handshake_watchdog`/`OG_TRIGGER` collateral greps, and
`--strict` are all discarded. This is the task retiring the deliberately-inverted F3 guard.

**Fix:** `&&`-chain everything that must pass; capture `--final` separately
(`… && --strict && { --final || true; }`) with the per-F-check verdict in the summary.

### B4 — Plan 16 Task 3's `<automated>` verify can never fail — and it is the phase acceptance task
`;`-separated throughout; exit status is a trailing `grep -c "PLAT-"`, which returns 0 whenever one
`PLAT-` string exists. Ten `analyse.py --gate` exit codes, `--check-step +3600`, the full pytest run
and `--strict` are all thrown away. Contradicts PLAT-24 ("pass/fail is a process exit code").

**Fix:** accumulate failures (`for …; do … --gate || FAIL=1; done`), exit non-zero on `FAIL`;
`&&`-chain `--check-step`, pytest and `--strict`; replace the bare `grep -c` with an assertion that
**all 26 distinct PLAT ids** carry a verdict.

### B5 — The delta gate can absorb a real regression at plan 02 (the exact masking it exists to prevent)
Plan 02 T2 deletes `autopilot/setup/` **and** un-`collect_ignore`s `tests/test_compute_ops.py` and
`tests/test_log_action_values.py` — two protected modules never executed anywhere — yet its verify
omits `tools/pytest_delta.py`. Plan 02 T3 then rewrites `31-PYTEST-BASELINE.json` wholesale and
verifies with `pytest_delta.py` **against the freshly written baseline** (trivially green). The only
guard is prose. Not a one-off: **15 of 33 autonomous tasks omit the delta gate; 2 omit `--strict`**
(worst: 02-T2, 14-T1 which has neither, 14-T2, 15-T2, 16-T3).

**Fix:** (a) add `pytest_delta.py` to plan 02 T2's verify; (b) make 02 T3 **machine-assert** the new
`failing_node_ids` is a **subset** of the previous set, any addition requiring an explicit
allow-list entry naming node id + reason, refusing to write otherwise; (c) add the delta gate to
both plan 14 tasks; (d) sweep remaining omissions.

### B6 — Plan 13 does not refuse to run on an "escalate" verdict; it only says so in prose
`<spike_inputs>` says "if the verdict was 'escalate', do not execute this plan" with **no machine
check**. Plans 11 and 12 (also downstream of plan 10) have none at all, while plan 16's
`<preconditions>` treats it as a hard gate. The two ends disagree.

**Fix:** give plans 11, 12, 13 a verify prefix that greps `31-SPIKE.md` for the verdict and exits
non-zero on `escalate`. The "Go / no-go" heading is fixed and already grepped by plan 10 T3.

### B7 — Plan 16's lgpio capture campaign does not run as written
Task 1 Steps 3-4 and Task 2's V3 soak invoke `python -m tools.pulse_timing.capture` under
`systemd-run … -p WorkingDirectory=/run/mics`. The preceding `cd /opt/mics` is overridden, and
`LG_WD` additionally `chdir()`s the process. `-m tools.pulse_timing.capture` fails with
`No module named tools`.

**Fix:** add `-p Environment=PYTHONPATH=/opt/mics` to every `systemd-run` block in plan 16, and
mirror into the `tools/pulse_timing/README.md` blocks plan 08 T3 corrects.

### B8 — Plan 16's V3 soak reintroduces the PLAT-10 landmine it exists to validate
V3 starts `mics-pilot`, then launches a transient unit with `-p RuntimeDirectory=mics` — the same
directory `mics-pilot.service` owns. systemd removes a `RuntimeDirectory` when the owning unit
stops, so when `mics-soak` exits it deletes `/run/mics` from under the running pilot, destroying its
`.lgd-nfy` FIFO and silently killing every edge callback. Same pattern in Task 1 Step 3.

**Fix:** distinct directory for transient units (`-p RuntimeDirectory=micscap -p
WorkingDirectory=/run/micscap -p Environment=LG_WD=/run/micscap`), as plan 10 already does with
`micsspike`.

### B9 — NEW (found after the checker ran): the single-clock invariant is unowned
**See CONTEXT.md §13 for the full verified analysis.** All 16 plans mention `assign_cb`,
`pi_timestamp`, `localize_tz`, `execute_trigger`, `handle_trigger` **zero times**. This is a second
unowned path, distinct from B2. Breaks three ways: callback arity (pigpio 3-arg vs lgpio 4-arg),
`localize_tz` receiving an int and raising in `strptime`, and the tick→timestamp conversion site
moving out of pigpio's notification thread into `assign_cb`.

**Fix:** add **PLAT-27** — `assign_cb` keeps its signature (it is the seam `task.py:199` uses for
every trigger); an adapter inside it absorbs lgpio's 4-arg callback; **both** event paths read one
epoch offset computed once (no snapshot copies — that is the existing defect); mandatory regression
test that one injected edge yields a `pi_timestamp` and a dispatcher timestamp referring to the
same instant; `localize_tz`'s input contract updated deliberately and tested.

---

## WARNINGS

- **W1** Plan 08's USER-RUN checklist has a broken literal command: Step 0 rsyncs to
  `~/pulse_timing/` but Steps 2-3 `cd ~/pulse_timing_root`, never created. For
  `python3 -m pulse_timing.capture` to resolve, cwd must be `~`. Fix both. The user copy-pastes these.
- **W2** The Python-3.7 AST gate covers only `capture.py`/`profiles.py`, but `capture.py` imports
  `Digital_Out`/`Solenoid`/`TTL`/`Pulse20Hz` from `hardware/gpio.py`, which plans 02/03 edit before
  plan 08 captures on Buster. A 3.8+ construct in that closure is discovered at the one-way door.
  Extend the gate to `gpio.py` + transitive imports, or assert closure verification in plan 08.
- **W3** Plan 04 T1 steps 4-5 name the wrong manifest section: the `pilot/prefs.json (PLUGIN_DB)`
  exemption is under **`runtime_generated`**, not `known_dangling` (which holds exactly one entry,
  the `autopilot.autopilot.core.pilot` deferral). `check_known_dangling` is the wrong function too.
- **W4** Plan 09's `<expected_friction>` expects `pigpiod` running, but plan 07's installer purges
  `pigpio pigpiod python3-pigpio` and plan 03's requirements contain no pigpio. The pilot dies on
  `import pigpio` immediately. Reword — the note will send the executor chasing a non-bug.
- **W6** Systematic off-by-one in cross-plan references — fix all: 02 `<integrity_gate>`
  "plan 14 retires F3"→15; 02 `<verified_deletion_map>` "`external/` deleted in plan 14"→15;
  05 `<verified_directives>` "handler is plan 14's work"→15; 12 `<scope_fence>` "`test_no_pigpio`
  arrives in plan 14"→15; 12 `<objective>`/`<verified_port_facts>` "plan 15 connects it to the
  dispatcher"→14 (swapped); 13 `<verified_port_facts>`/`<output>` "plan 14's SIGINT handler"→15.
- **W7** `31-VALIDATION.md`'s sign-off overstates two claims: (a) "five USER-RUN capture tasks" —
  there are **six** (08-T1, 08-T2, 09-T1, 10-T2, 16-T1, 16-T2), as its own table lists correctly;
  (b) "every autonomous task ends in `pytest_delta.py` + `--strict`" — 15 of 33 omit the delta gate.
  The sampling-continuity conclusion is independently correct, but `nyquist_compliant: true`
  currently rests partly on false supporting claims.
- **W8** The "<10 s latency for every autonomous task" claim excludes plan 03 T2
  (`test_requirements_wheels.py` makes a PyPI round trip per pin; skips cleanly offline).
- **W9** Plan 16 T3 step 7's record-update instructions are stale — ROADMAP already reads
  `**Requirements**: PLAT-01 through PLAT-26` and REQUIREMENTS.md already has the block
  (lines 489-523) plus the mapping row (line 268). As written it invites a duplicate.
- **W10** Plan 09's first `must_haves.truth` ("yields a Pi that boots into the pilot with no human
  action") is stronger than its own stated gate ("gate is PROVISIONING, not a working pilot").
  A verifier grading on `must_haves` alone marks plan 09 failed for behaving as designed. Reword to
  "…boots into `mics-pilot.service` unattended and systemd restarts it indefinitely without latching".

## INFO

1. `tools/pytest_delta.py` defaults to a cross-repo baseline path, so the gate is unusable from a
   clean `mics_core` clone (deliberate, mirrors Phase 30). Mention `--baseline` in plan 01 T1's README.
2. Plan 10 Step 0 rsyncs `tools/pulse_timing/` including committed `captures/` JSONL files — add
   `--exclude captures/`.
3. Plan 15 T1 touches 7 files and folds in the open `external/` scoping decision — consider
   splitting that decision into its own task.

---

## Planner's own findings worth preserving

1. **The shed is a Wave 0 unblocker, not cleanup.** Deleting `autopilot/setup/` removes the
   `npyscreen` import poisoning 179 of 381 tests. Measured: **179 failed / 203 passed / 381
   collected in 4.96 s**; all 179 are one third-party import chain
   (`autopilot/__init__.py:4` → `setup_autopilot.py:6` → `npyscreen`, then `utils/common.py:18`
   → `tzlocal`).
2. **A third mandatory manifest edit the brief did not name** — `Event_Dispatcher.py` carries a
   `baseline_sha256` in `tools/tree_protect_list.json`. `manifest.py check_event_dispatcher()`
   independently requires `_dropped_no_clock` / `_dropped_on_send` to survive **by name**.
3. **The pigpio baseline is a one-way door.** The patched `pigpio.py` exists **only** in the live
   rig's site-packages, not in the repo, and becomes unobtainable once the spare card is reflashed.
   Hence plan 08 before plan 09, and `capture.py` constrained to Python 3.7 grammar.
4. **The "7 direct dependencies" figure is optimistic** — a direct import scan finds `pytz`
   (`mics_task.py:1`, on the pilot path), `tzlocal` (`utils/common.py:18`, **absent from
   `requirements.txt` entirely**), plus `packaging`, `requests`, `validators`, `pygame`, `psychopy`.
5. **Plan 10 is a real decision gate.** If the spike measures lgpio tx jitter failing thresholds
   **even at `SCHED_FIFO:10`**, plans 11-16 must not run as written — options are a PREEMPT_RT
   kernel, CPU isolation, or hardware PWM, all much larger. Plan 10 instructs stopping to ask the user.
