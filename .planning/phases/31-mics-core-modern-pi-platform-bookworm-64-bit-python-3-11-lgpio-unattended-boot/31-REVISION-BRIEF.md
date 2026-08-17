# Phase 31 — Revision Brief (feed this to the planner)

> ## ⚠ STATUS CORRECTED 2026-08-17 — re-audited against the files on disk
>
> The previous version of this brief said a revision pass had been "abandoned uncommitted" and that
> **all 9 blockers were outstanding**. **That was wrong.** A direct audit of the plan files at
> `HEAD` (`bf57140`) shows commit **`4f3c38f`** — whose message reads "record the single-clock
> invariant as a phase requirement" — actually carried **474 insertions across 15 of the 16 plan
> files**. It committed the revision under a misleading message. `bf57140` reverted nothing; it only
> added this brief and the `.patch` file.
>
> **Eight of the nine blockers are already fixed in the plans.** The audit below is evidence-based
> (literal string counts, not RTK-proxied grep, which can blank a matching line). Do **not**
> re-litigate the FIXED items — re-doing them risks churning correct work.
>
> **`31-partial-revision-ABANDONED.patch` is stale and misleading. Ignore it; do not `git apply` it.**

**What is actually left:** one substantive blocker (**B9**, the single-clock invariant — genuinely
unowned by every plan), plus **one B1 residual** and **six mechanical warning/info items**.

---

## VERIFIED FIXED — do not re-open

| ID | Fix | Evidence on disk |
|---|---|---|
| **B1** *(plans only)* | plan 05 depends on 04 | `31-05` `depends_on: ["31-03","31-04"]`, wave 5; waves now `1,2,3,4,5,4,6,5,7,8,9,10,11,11,12,13` (13 waves) |
| **B2** | `logging_utils.py` bridge owned | `31-14-PLAN.md:9` lists it in `files_modified`; Task 2 owns it; `external_hardware_*` scope stated (15 mentions) |
| **B3** | plan 15 T2 verify can fail | zero occurrences of `echo "final exit=$?"` or `; echo` in `31-15-PLAN.md` |
| **B4** | plan 16 T3 verify can fail | `FAIL=1` accumulator + `test "$FAIL" -eq 0 && …` `&&`-chain; bare `grep -c "PLAT-"` gone; replaced by a Python assertion that **all 26 PLAT ids** carry a verdict |
| **B5** | delta gate swept | of all `<automated>` blocks, **only `31-01`** omits `pytest_delta.py` (it is the task that *creates* the baseline — correct); **zero** omit `--strict`; plan 02 T3 carries the `subset` assertion + allow-list |
| **B6** | spike verdict machine-gated | `31-11`, `31-12`, `31-13` — **both** real verify blocks in each carry the `SPIKE VERDICT IS ESCALATE` exit-non-zero check |
| **B7** | `systemd-run` PYTHONPATH | `31-16`: 2 `systemd-run` blocks, 4 × `PYTHONPATH=/opt/mics` |
| **B8** | transient-unit RuntimeDirectory | `31-16`: 5 × `RuntimeDirectory=micscap`, **0** bare `RuntimeDirectory=mics` |
| **W1** | plan 08 cwd | `pulse_timing_root` occurrences = 0 |
| **W3** | manifest section named right | `31-04:166-177` states `runtime_generated`, **not** `known_dangling`, and names the correct dangling-scan code rather than `check_known_dangling` |
| **W4** | plan 09 pigpio friction | `31-09:49-53,140-141,153` reworded — the intermediate pigpio state is now explained as deliberate |
| **W10** | plan 09 `must_haves` | "no human action" gone; phrased around `mics-pilot.service` + restart-without-latching |
| **I1** | `--baseline` documented | 2 mentions in `31-01-PLAN.md` |

Also still true from the original checker pass (unchanged): requirement coverage complete,
`--rebaseline` appears only as a prohibition, all three hand-edits have named tasks, §11 locked
decisions honored literally (`tx_pulse(h, pin, 8000, 8000, 0, 0)`), §12 corrections propagated,
hard rules honored, no scope creep, dependency graph acyclic.

---

## OUTSTANDING — this is the whole remaining job

> ### ✅ ADDRESSED 2026-08-17 by the planner revision pass — verify, do not re-do
>
> Every item below was worked in one pass. **PLAT-27 landed in plan 12 (new Task 3) and closes in
> plan 14 Task 2**; the four knock-on edits are done (`REQUIREMENTS.md`, `ROADMAP.md`,
> `31-16-PLAN.md`'s `range(1,28)` + the three "26" strings, `31-VALIDATION.md`). B1-residual,
> W2, W6, W7, W8, W9 and I2 are done. I3 was skipped as advisory.
>
> **One thing the brief did not catch, now fixed:** plans 13 and 14 were both wave 11 and both edit
> `autopilot/autopilot/hardware/gpio.py` — a parallel-edit hazard on a 1692-line file. Plan 14 now
> depends on 31-13, so **the layout is 14 waves, not 13**: 05→5, 06→4, 07→6, 08→5, 09→7, 10→8,
> 11→9, 12→10, 13→11, **14→12, 15→13, 16→14**. `31-VALIDATION.md` is derived from that.
>
> **A second correction, inside plan 14:** its `dispatch_event` call-site inventory classified
> `tasks/task.py:283` as having no edge timestamp. It is the dispatch inside `execute_trigger`, on
> the `assign_cb` path, with the edge `tick` in scope — exactly the split PLAT-27 exists to prevent.
> Corrected, and it is now where the mandatory same-instant assertion is anchored.
>
> Re-verify against the files rather than against this banner.

### B9 — the single-clock invariant is unowned *(the only substantive item)*

**Verified 2026-08-17, unchanged:** across all 16 plans, `assign_cb` = **0**, `pi_timestamp` = **0**,
`localize_tz` = **0**, `handle_trigger` = **0**, `PLAT-27` = **0**. (`execute_trigger` appears twice
in `31-14` only.) `REQUIREMENTS.md` has **no** PLAT-27. Distinct from B2, which is fixed.

**The full verified analysis is `CONTEXT.md` §13 — read it; do not re-derive it.** Summary of what
breaks if this stays unowned: (1) callback arity — pigpio `(gpio, level, tick)` 3-arg vs lgpio
`(chip, gpio, level, timestamp)` 4-arg, hitting `Digital_In.record_event` (`gpio.py:940`) and
`Task.handle_trigger` (`task.py:199`); (2) `localize_tz` (`utils/common.py:329-334`) receives an int
and raises in `strptime`; (3) the tick→timestamp conversion site moves out of pigpio's notification
thread — `assign_cb` itself must own the adapter.

**Fix — add PLAT-27, and give it an owning task:**
- `assign_cb` **keeps its signature** (it is the seam `task.py:199` uses for every trigger); an
  adapter *inside* it absorbs lgpio's 4-arg callback down to the existing 3-arg contract.
- **Both** paths (`execute_trigger`'s `pi_timestamp` and `Event_Dispatcher`'s `t_mono_ns`) read
  **one** epoch offset computed once. No second offset, and **no scalar snapshot copies** — the
  snapshot is precisely the existing defect that makes today's alignment decay after each 71.6-min
  wrap (~20×/day under 24/7).
- **Mandatory regression test:** one injected edge yields a `pi_timestamp` and a dispatcher
  timestamp referring to the **same instant**.
- `localize_tz`'s input contract updated **deliberately and tested**, not incidentally.
- Consider a test that the invariant survives a simulated long run (today's design does not).

**Ownership guidance (planner's call, but state the reasoning):** the natural homes are plan **12**
(`Digital_In` / callback port) and plan **14** (dispatcher timebase). The offset must be *one*
value read by both, so whichever plan creates it must precede the other, or a new plan owns the
shared clock source and both depend on it. Do not split the offset across two plans.

**Knock-on edits PLAT-27 forces — all mandatory, easy to miss:**
1. `REQUIREMENTS.md` — add the PLAT-27 row and update the phase-mapping row (currently PLAT-01..26).
2. `ROADMAP.md` Phase 31 — `**Requirements**: PLAT-01 through PLAT-26` → **27**.
3. `31-16-PLAN.md` acceptance verify — the Python assertion builds `want={'PLAT-%02d'%i for i in
   range(1,27)}`; must become `range(1,28)`. Also `31-16:402` ("all 26 PLAT ids") and `31-16:413`
   ("PLAT-01 through PLAT-26").
4. `31-VALIDATION.md` — add the PLAT-27 task row(s) and its wave.

### B1 residual — `31-VALIDATION.md`'s wave column is stale

The plans were re-waved; **the validation contract was not**. Its table still carries the old
12-wave layout — e.g. `31-05` wave 4 (plans say 5), `31-07` wave 5 (says 6), `31-09` wave 6 (says
7), `31-16` wave 12 (says 13). Every row from `31-05` down is wrong.

**Fix:** rewrite the `Wave` column from the plan frontmatter — the plan files are the source of
truth — and re-check every `depends_on` against it.

### W2 — the Python-3.7 AST gate is too narrow

`31-06-PLAN.md:229,251,310` gates `ast.parse(..., feature_version=(3,7))` on **`capture.py` and
`profiles.py` only**. But `capture.py` imports `Digital_Out`/`Solenoid`/`TTL`/`Pulse20Hz` from
`hardware/gpio.py`, which plans **02/03 edit before plan 08 captures on Buster**. A 3.8+ construct
in that import closure is discovered at the one-way door (plan 08 must precede plan 09's reflash,
and the patched `pigpio.py` is unobtainable afterwards).

**Fix:** extend the gate to `gpio.py` and its transitive import closure, or make plan 08 assert
closure verification before the capture run.

### W6 residual — one wrong cross-plan reference left

`31-09-PLAN.md:277` — "Do not fix pigpio; **plan 14** deletes it." Plan 14 is dual-timebase
dispatch; pigpio removal completes in plan **15** (`test_no_pigpio`, `external/` deletion).
Fix to 15 (or "plans 11–15").

*(The other "plan 14" references are correct as written: `31-12:55` and `31-12:167` genuinely point
at plan 14's dispatcher work; `31-14:358` is a self-reference; `31-15:235` correctly credits plan 14
with replacing the estimated tick→timestamp mapping. The 02 and 05 off-by-ones are already fixed.)*

### W7 — `31-VALIDATION.md`'s sign-off still overstates

`31-VALIDATION.md:183` still reads "**The five USER-RUN capture tasks**". There are **six**:
`08-T1`, `08-T2`, `09-T1`, `10-T2`, `16-T1`, `16-T2` — as its own Manual-Only table lists correctly.
The delta-gate claim can now be stated truthfully (it *is* on every autonomous task except plan 01,
which creates the baseline) — state it with that carve-out rather than absolutely.
The sampling-continuity conclusion is independently correct; only the supporting counts are wrong.

### W8 — latency claim needs one carve-out

`31-VALIDATION.md:179` claims "< 10 s for all autonomous tasks". Plan 03 T2
(`test_requirements_wheels.py`) makes a PyPI round trip per pin. It skips cleanly offline — say so
rather than leaving the blanket claim.

### W9 — plan 16 step 7's record-update instructions are stale

`31-16-PLAN.md:377-379` instructs replacing ROADMAP's `TBD` requirements line and adding the `PLAT-`
block to `REQUIREMENTS.md` — **both already exist** (REQUIREMENTS.md lines 489-523 plus the mapping
row at 268). As written it invites a duplicate block. Reword to *verify/update* rather than *add*,
and fold in the PLAT-27 renumbering from B9.

### I2 — plan 10 rsync ships committed captures

`31-10-PLAN.md:216` and `:283` rsync `tools/pulse_timing/` to the Pi including the committed
`captures/` JSONL files. Add `--exclude captures/` to both.

### I3 — advisory only

Plan 15 T1 touches 7 files and folds in the open `external/` scoping decision. Splitting that
decision into its own task is optional; skip it unless the re-waving makes it convenient.

---

## Instructions to the planner

1. **Do not replan from scratch and do not touch the FIXED table's items.** The structure is sound
   and the previous revision was largely correct — it was only mislabeled.
2. **B9 first** — it is the only item requiring design judgment, and it changes requirement counts
   that four other files assert against. Do its four knock-on edits in the same pass or the plan 16
   acceptance gate will fail on a count mismatch.
3. Then B1-residual (`31-VALIDATION.md` waves), then W2, then the mechanical W6/W7/W8/W9/I2 edits.
4. When re-waving, re-check **every** `depends_on` against the plan frontmatter **and** the
   validation contract's wave column — they are currently out of sync, which is how B1 survived
   looking fixed.
5. Re-run `gsd-plan-checker` afterwards, re-verifying rather than trusting this brief.

## Planner's own findings worth preserving

1. **The shed is a Wave 0 unblocker, not cleanup.** Deleting `autopilot/setup/` removes the
   `npyscreen` import poisoning 179 of 381 tests. Measured: **179 failed / 203 passed / 381
   collected in 4.96 s**; all 179 are one third-party import chain
   (`autopilot/__init__.py:4` → `setup_autopilot.py:6` → `npyscreen`, then `utils/common.py:18`
   → `tzlocal`).
2. **A third mandatory manifest edit** — `Event_Dispatcher.py` carries a `baseline_sha256` in
   `tools/tree_protect_list.json`. `manifest.py check_event_dispatcher()` independently requires
   `_dropped_no_clock` / `_dropped_on_send` to survive **by name**.
3. **The pigpio baseline is a one-way door.** The patched `pigpio.py` exists **only** in the live
   rig's site-packages, not in the repo, and becomes unobtainable once the spare card is reflashed.
   Hence plan 08 before plan 09, and `capture.py` constrained to Python 3.7 grammar.
4. **The "7 direct dependencies" figure is optimistic** — a direct import scan finds `pytz`
   (`mics_task.py:1`, on the pilot path), `tzlocal` (`utils/common.py:18`, **absent from
   `requirements.txt` entirely**), plus `packaging`, `requests`, `validators`, `pygame`, `psychopy`.
5. **Plan 10 is a real decision gate.** If the spike measures lgpio tx jitter failing thresholds
   **even at `SCHED_FIFO:10`**, plans 11-16 must not run as written — options are a PREEMPT_RT
   kernel, CPU isolation, or hardware PWM, all much larger. Plan 10 instructs stopping to ask the user.
