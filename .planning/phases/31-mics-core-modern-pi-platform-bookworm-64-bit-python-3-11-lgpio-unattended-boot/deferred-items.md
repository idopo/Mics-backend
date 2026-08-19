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
