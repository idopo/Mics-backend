# Phase 31 — Deferred Items

Out-of-scope discoveries logged during execution, not fixed (per plan executor scope boundary:
only auto-fix issues directly caused by the current task's changes).

## From Plan 01 (2026-08-19)

1. **`REQUIREMENTS.md`'s PLAT-26 row description is stale.** It reads "a recording fake `lgpio`
   with a signature-contract test" — a holdover from before the 2026-08-17 scope revision
   (`31-REVISED-SCOPE.md`) withdrew the lgpio migration. Plan 01 actually delivers a recording fake
   of **pigpio**'s notification stream (`tests/fakes/fake_pigpio.py`), matching the plan file
   itself and every other PLAT-2x row in the same table, all of which were already updated for the
   revision. `REQUIREMENTS.md` also has no checkbox column on this table (same structural gap noted
   throughout `STATE.md` for CMP-*/DVK-*/HYG-*), so `gsd-tools requirements mark-complete PLAT-26`
   reports `not_found` rather than a false completion — not a regression, but worth fixing in one
   pass whenever `REQUIREMENTS.md` next gets a general edit.

2. **`tests/test_compute_ops.py` and `tests/test_log_action_values.py` stay in `conftest.py`'s
   `collect_ignore`, but their inline comments ("for exactly the npyscreen reason") are now
   half-stale.** `npyscreen` itself is resolved by `requirements-dev.txt`; both files are still
   blocked, but by the pigpio chain (`Event_Dispatcher.py:3`), not npyscreen. Plan 01 Task 3's own
   instructions reserve editing this block for plan 02 ("leave the existing `collect_ignore` block
   and its explanatory comment intact — plan 02 revisits it"), so the comment was left as written.

## From plan 31-C2 (2026-08-19)

**`tests/test_log_action_values.py::test_set_non_numeric_logs_raw_instead_of_raising`
contradicts `autopilot/utils/log_value.py`. Both are PROTECTED. Rule 4 — user decision.**

- **Found during:** C2 Task 2, immediately after removing `Event_Dispatcher.py`'s
  unconditional `import pigpio`. That import was a *collection error*, so
  `conftest.py`'s `collect_ignore` had kept this whole module dark since Phase 25. It
  now collects: 9 of its 10 tests pass.
- **The contradiction:** the test asserts `event_data["value"] == "baseline"` for a
  non-numeric `Tracker.set`. That was the Phase 25 contract. Phase 26 (CMP-16) then
  deliberately changed it — `log_value.coerce_for_event` diverts non-numbers to
  `value_str` and leaves `value` `None`, because `event.event_data.value` is mapped
  `long` in `event_log_v2` and a bare non-numeric string makes Elasticsearch reject the
  **whole document** (proven live, run 549).
- **Why C2 did not fix it:** both files are protected, and the plan explicitly forbids
  editing `test_log_action_values.py`. Resolving it means changing one of them, which is
  an architectural/ownership decision. No C2 code is implicated: `logging_utils`'
  `Mics_Tracker` branch is byte-identical.
- **Recorded** in `31-PYTEST-BASELINE.json` under `accepted_new_failures` with the full
  reason, via `tools/rebaseline_pytest.py` (the only sanctioned path).
- **Suggested resolution:** update the Phase 25 test to assert `value is None` and
  `value_str == "baseline"`, since `log_value.py` is the later, deliberate,
  hardware-proven design. Needs the user's sign-off because the test is protected.

**`tests/test_load_fda_from_json.py` and `tests/test_trigger_assignments.py` now fail on
`ModuleNotFoundError: No module named 'board'`.**

- Same node ids as before (they were pigpio-blocked in the 187 baseline), so not new
  failures — they simply fail one link further down the import chain now.
- Exactly what 31-01-SUMMARY predicted: "whichever later plan first unblocks that chain
  should expect `i2c.py`'s `MPR121` class to surface a *new* `ModuleNotFoundError:
  board`". `board`/`busio` are `adafruit-blinka`, genuinely Pi-only and not installable
  on this dev host. Out of C2's fence; a later plan may want a `collect_ignore` entry or
  a stub.

---

## From plan C3 (2026-08-19)

**`start_pigpiod()`'s `kill_proc` hook cannot actually kill `pigpiod`. PRE-EXISTING, NOT FIXED
HERE, and it undermines the stated premise of PLAT-33's withdrawal.**

`autopilot/autopilot/external/__init__.py:52-60`:

```python
proc = subprocess.Popen('sudo ' + launch_pigpiod, shell=True)
...
def kill_proc(*args):
    proc.kill()
    sys.exit(1)
atexit.register(kill_proc)
signal.signal(signal.SIGTERM, kill_proc)
```

Three independent reasons the hook never reaches the daemon:

1. `shell=True` means `proc` is the **shell wrapper**, not `pigpiod`. Killing the shell does not
   kill its child.
2. `pigpiod` **daemonises** (it is not launched with `-g`), so it detaches and is reparented to
   init. Even the correct PID would be the wrong process by the time the hook runs.
3. It runs under `sudo`, so `proc.kill()` from the unprivileged pilot could not signal it anyway.

PLAT-33 was withdrawn on the belief that this hook "closes the solenoids at session end". It does
not: the daemon already outlives the pilot today, which is the exact failure mode a systemd unit
was said to introduce. **The withdrawal stands by user instruction and C3 changed nothing here** —
`external/__init__.py` has a zero-line diff and C3's gate asserts the hook is intact.

- **Why C3 did not fix it:** out of C3's fence (the plan explicitly names it as pre-existing and
  out of scope), and the correct fix is a design decision, not a bug fix.
- **Suggested resolution, for the user:** if solenoid-safe shutdown is actually wanted, it needs a
  real fail-safe, not this hook — e.g. `pigpiod -g` under a systemd unit with a `pigs`-based
  `ExecStopPost` that de-energises `VALVE1-4` / `AIR_PUF` / `ODOR1-5`, or a hardware pull-down. A
  decision either way should be made on the evidence above rather than on the hook.

---

## From plan C4 Task 0 (2026-08-19)

**Task 0's pre-flight gate contains a clause that is unsatisfiable by construction: plan 08's
baseline captures. Deviated deliberately, not waived silently.**

- **The clause:** `at least ten before_*.jsonl and one wrap_witness_patched.jsonl under
  tools/pulse_timing/captures/`. Measured: **0 and 0** — the directory is empty.
- **Why it cannot be met:** **plan 31-08 was skipped by user decision.** The `before` capture it
  owned was never taken, so there is nothing for the glob to find. No amount of C4 work produces
  it; only a Buster card and a re-run of plan 08 would.
- **What it costs:** PLAT-24's paired regression has **no before arm**. Any G1-style comparison
  reported as if a baseline existed would be false. §0 and §8 of `31-HARDWARE-VALIDATION.md`
  state this in those terms, and `tools/pulse_timing/README.md`'s campaign section repeats it at
  the point of use so the person running the campaign meets it there too.
- **Mitigation, unchanged:** tag `phase-31-buster-before-arm` @ `9fc8837` preserves the pre-C2
  tree, keeping a `before` capture re-derivable. **Do not move or delete that tag.**
- **Every other clause of the gate passes:** C1–C4 tests green (14/14 on `test_clock_soak.py`,
  the whole C1–C3 set green), `--final` exit 0 with zero VIOLATION lines so C3's F3 retirement
  holds, `clock_soak.py` outside the py37 closure, `pytest_delta` `new failures: 0`, `--strict`
  exit 0.

**`31-HARDWARE-VALIDATION.md` did not exist and was created by Task 0.**

The gate's last clause asserts the evidence log exists with an "after arm" section for the plan
to fill. It had never been created for this phase (phases 23 and 30 have theirs). Task 0 created
it as a scaffold: every row reads **NOT RUN**, and §8 is a mandatory NOT PROVEN section, so an
unfilled log states its own emptiness rather than implying completeness.

---

## From the run 580 soak / C6 forced step (2026-08-26)

**C5's independence claim is false: its ground truth is the Pi's own wall clock, so C5 cannot
detect a whole-machine clock error. Found by direct observation, not by inspection.**

- **What C5 claims.** `es_clock_check.py:34-43` and the comment at
  `clock_check_accumulator.py:203-207` both assert the window is independent of the value under
  test: "Window ground truth is @timestamp (ES's own ingest-time clock), independent of the
  pi_timestamp field under test -- this check never uses the value it validates as its own ground
  truth." The bounds are deliberately taken from SOFTWARE documents only, because a hardware
  document's `timestamp` IS the rendered `pi_timestamp` and would let a corrupt clock vouch for
  itself.
- **What actually happened.** During run 580's forced +1 h step (C6, 2026-08-26 11:55:07 UTC),
  C5 reported `window_end: 2026-08-26T15:56:26.938728+03:00` — 12:56 UTC — while real UTC was
  11:55. The window moved WITH the rig. Since only software documents set the bounds, software
  `timestamp` is Pi-rendered, not ingest-assigned.
- **Confirmed against the index.** A run 580 document carries exactly three time fields —
  `timestamp`, `t_utc_ns`, `t_mono_ns` — and no `@timestamp`, no ingest-pipeline field. The first
  two are both `t_mono_ns + _epoch_offset_ns()` renderings (`utils/clock.py:395-406`), so both
  track CLOCK_REALTIME. **Nothing on the document originates off the Pi.** There is no independent
  clock in this index for C5 to have used.
- **What it costs.** For the full hour the rig ran +3599 s ahead, C5 reported `implausible: 0`
  over 466 then 518 documents. A whole-machine wall-clock error — NTP stepping the rig, an RTC
  restored wrong at boot, a manual `date -s` nobody logged — moves the value under test and its
  ground truth together and C5 passes. The check is one-sided by construction.
- **What it still catches, and this is not small.** C5 was rebuilt to catch run 576, where the
  HARDWARE route was 38 h from the SOFTWARE route. That is a mapping defect: it moves one side
  only, so the comparison stays meaningful and C5 correctly reported FAIL 253/253. The same holds
  for the two per-value corruptions it names (monotonic-as-epoch, microsecond-as-nanosecond) —
  both produce values wildly outside any window. **C5 is a cross-route check that has been
  described as an absolute-time check.** Its coverage is real; only the claim is wrong.
- **Why this is not the C6 result.** C6 PASSED on this same run, twice and in both directions
  (+3599.515 s at 11:55:07 UTC, -3600.162 s at 12:58:52 rig-clock), `intervals_disturbed: 0`,
  the 5 s pulse straddling each step measuring 4.998 s and 4.997 s. PLAT-25 holds. This entry is
  about what C5 proves, not about the rig's timing.
- **Fix options, cheapest first.**
  1. **Restate the contract.** Correct the docstring and the comment to say cross-route, drop the
     independence claim, and note in `PI_213_DEPLOY_CLOCK_FIX.txt`'s C5 row that a green C5 is not
     evidence the rig's absolute time is right. Costs nothing, removes the false assurance.
  2. **Bound against the verifier's own clock.** `es_clock_check.py` runs on an NTP-synced
     workstation; compare the window against query time. Independent and free, but only valid
     while the run is recent — it cannot check an archived run, so it must be a separate check
     (C11) that skips loudly rather than a change to C5.
  3. **Add a real ingest timestamp.** An ES ingest pipeline setting `ingest_time` from
     `_ingest.timestamp` gives C5 the independent ground truth it was written to have, for every
     future run. Index-side change, outside Phase 31's scope, and worthless for runs already
     written.
- **A related claim made in this session was WRONG and is retracted here.** `chronyc tracking` on
  RecordingBox was read 30 s after a `systemctl start chrony` and reported `Reference ID
  00000000` / `Ref time 1970` / `Not synchronised`; that was written up as "the rig has no NTP
  source and free-runs at 9.656 ppm (~0.83 s/day)". **False.** `chronyc sources -v` on the same
  rig shows four reachable servers, Reach 377, a selected `^*` il-central stratum-2 source at
  **+19 us**, from the stock `pool 2.debian.pool.ntp.org iburst` line, with `makestep 1 3` set.
  The tracking output was the normal post-restart transient before source selection, and the
  `Frequency` line is the crystal error chrony CORRECTS, not drift suffered. RecordingBox's
  absolute time is disciplined and accurate to microseconds.
- **What that does to this entry: nothing.** C5's defect was established by direct observation —
  `window_end` moved with the rig during the forced step, and the index carries no non-Pi time
  field — not by any argument about NTP. What changes is only the *exposure*: a whole-machine
  clock error is now an unlikely event on this rig rather than an ongoing one. The check still
  cannot see that class, so fix option 1 (restate the contract) remains worth doing; options 2
  and 3 are lower priority than they looked.
