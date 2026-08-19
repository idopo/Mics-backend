---
phase: 31-mics-core-modern-pi-platform-bookworm-64-bit-python-3-11-lgpio-unattended-boot
plan: 01
subsystem: testing
tags: [pytest, pigpio, gpio, dev-tooling, ci-gate, shellcheck]

# Dependency graph
requires: []
provides:
  - "Feature branch `phase-31-modern-pi-platform` in ~/mics_core, published to origin with upstream set; local main untouched"
  - "Dev-host venv (/home/ido/.venvs/mics_core_dev) that can import and run the tree's pytest suite"
  - "tools/pytest_delta.py — baseline-relative pass/fail gate, stdlib-only, exits non-zero only on NEW failures, reports fixed: nodes"
  - "31-PYTEST-BASELINE.json — frozen 179-failing-node-id set in the planning repo, the reference every later delta compares to"
  - "tests/fakes/fake_pigpio.py — recording fake of stock pigpio's notification stream with fire_edge()/simulate_wrap()/set_tick()/advance_tick()/registration_count()"
  - "conftest.py fake_pigpio fixture — installs the fake at sys.modules['pigpio'] before the module under test imports it"
  - "shellcheck 0.9.0 static binary at ~/.local/bin/shellcheck (no apt/sudo on this dev host)"
affects: [31-02, 31-03, 31-C1, 31-C2, 31-C3, 31-C4]

# Tech tracking
tech-stack:
  added: [npyscreen, tzlocal, tornado, pandas, tables, scipy, blosc, pyzmq (dev-host only, requirements-dev.txt)]
  patterns:
    - "Dev-host test closure kept strictly separate from rig requirements.txt, in a header-commented requirements-dev.txt"
    - "pigpio deliberately excluded from requirements-dev.txt; tests needing it opt into the fake_pigpio fixture instead of a real client"
    - "pytest_delta.py: baseline-relative CI gate, ported from a Phase 30 heredoc into a reviewable, unit-tested script"

key-files:
  created:
    - /home/ido/mics_core/requirements-dev.txt
    - /home/ido/mics_core/tools/pytest_delta.py
    - /home/ido/mics_core/tests/test_pytest_delta.py
    - /home/ido/mics_core/tests/fakes/__init__.py
    - /home/ido/mics_core/tests/fakes/fake_pigpio.py
    - /home/ido/mics_core/tests/test_fake_pigpio_contract.py
    - /home/ido/mics-backend/.planning/phases/31-mics-core-modern-pi-platform-bookworm-64-bit-python-3-11-lgpio-unattended-boot/31-PYTEST-BASELINE.json
  modified:
    - /home/ido/mics_core/README.md
    - /home/ido/mics_core/conftest.py

key-decisions:
  - "pigpio is the true terminal blocker for all 179 pre-existing failures, not npyscreen/tzlocal as the phase's original audit assumed — discovered empirically and documented in the baseline's note field rather than silently overwriting the phase record"
  - "shellcheck installed as a static binary to ~/.local/bin rather than via apt, because this dev host has no passwordless sudo"
  - "Did not un-ignore tests/test_compute_ops.py even though npyscreen is now resolved for it, because it is still pigpio-blocked for 8 of its 12 tests and un-ignoring would raise the failure count, not lower it"

patterns-established:
  - "TDD RED/GREEN commits for both tools/pytest_delta.py and tests/fakes/fake_pigpio.py"
  - "Baseline JSON's `note` field is where empirical corrections to the phase's planning assumptions get recorded, quoted against the original numbers, so the discrepancy is auditable rather than silently absorbed"

requirements-completed: [PLAT-26]

# Metrics
duration: 40min
completed: 2026-08-19
---

# Phase 31 Plan 01: Dev-Host Test Instrument + Recording pigpio Fake Summary

**Cut the Phase 31 feature branch, gave the dev host a real pytest run via `requirements-dev.txt`, froze a 179-failing-node-id baseline with a committed stdlib-only delta gate (`tools/pytest_delta.py`), and built a recording fake of stock pigpio's notification stream (`tests/fakes/fake_pigpio.py`) with edge and 71.6-minute wrap injection for the clean-room clock layer plans C1/C2 develop against.**

## Performance

- **Duration:** ~40 min
- **Started:** 2026-08-19T06:13:00Z (approx.)
- **Completed:** 2026-08-19T06:48:36Z
- **Tasks:** 3 completed
- **Files modified:** 9 (7 created, 2 modified) across mics_core + 1 created in the planning repo

## Accomplishments

- `phase-31-modern-pi-platform` branch cut in `~/mics_core`, published to `origin` with upstream tracking; local `main` verified identical to `origin/main`
- `/home/ido/.venvs/mics_core_dev` created; `requirements-dev.txt` gives it an empirically-determined import closure (iterated `ModuleNotFoundError` → install → repeat) so `pytest` collects and runs the tree instead of dying on a missing third-party import
- `tools/pytest_delta.py`: TDD'd baseline-relative pass/fail gate (5/5 unit tests green), ported from Phase 30's inline heredoc into a reviewable, stdlib-only script with the `fixed:` reporting the heredoc lacked
- `31-PYTEST-BASELINE.json` frozen in the planning repo at Task 2 time: 179 failed / 208 passed / 387 collected, `failing_node_ids` populated via the delta tool's own parser (so the gate and the baseline agree byte-for-byte on node-id format). After Task 3 added its own 25-test contract suite, the full-tree count is 179 failed / 233 passed / 412 collected — same 179 failing node ids, `pytest_delta.py` confirms `new failures: 0`.
- `tests/fakes/fake_pigpio.py`: TDD'd recording fake of stock pigpio's notification stream (25/25 contract tests green) — `fire_edge()` dispatches to every live matching registration sequentially in registration order with pigpio's exact 3 positional args; `simulate_wrap()`/`set_tick()`/`advance_tick()` reproduce the 32-bit tick wrap structurally via `struct.pack('HHII', ...)`; no `sync_ticks=`/`synchronize()`/`ticks_to_timestamp()` (the Autopilot patches this phase deletes)
- `conftest.py` `fake_pigpio` fixture installs the fake at `sys.modules['pigpio']` before the module under test imports it, and tears it down after
- shellcheck 0.9.0 installed (static binary, no apt available) — Wave 0 tooling for plans 04/05/07/09

## Task Commits

Each task was committed atomically:

1. **Task 1: Cut the feature branch and make the dev host able to import the tree** - `a0e3d10` (chore)
2. **Task 2: Freeze the Phase 31 pytest baseline and commit the delta gate** - TDD: `a50de02` (test, RED) → `981fb0f` (feat, GREEN) → `1b244b2` (plan, baseline JSON, mics-backend repo)
3. **Task 3: Recording fake pigpio notification stream and its contract test** - TDD: `df56f2d` (test, RED) → `a535b39` (feat, GREEN)

All commits above are in `~/mics_core` on `phase-31-modern-pi-platform`, except `1b244b2` which is in `mics-backend` (the planning repo) since `31-PYTEST-BASELINE.json` is a planning artifact per the repo boundary rule.

## Files Created/Modified

- `/home/ido/mics_core/requirements-dev.txt` - dev-host-only pytest import closure; deliberately excludes pigpio; full `pip freeze` recorded with a header explaining scope
- `/home/ido/mics_core/tools/pytest_delta.py` - baseline-relative CI gate: `run_pytest`, `parse_failed_node_ids`, `is_collection_error`, `compute_delta`, `main`
- `/home/ido/mics_core/tests/test_pytest_delta.py` - 5 unit tests driving the gate with a stubbed `subprocess.run`, never a real nested pytest run
- `/home/ido/mics_core/tests/fakes/__init__.py` - empty, makes `tests/fakes` a package
- `/home/ido/mics_core/tests/fakes/fake_pigpio.py` - the recording fake; public control API documented verbatim below
- `/home/ido/mics_core/tests/test_fake_pigpio_contract.py` - 25 tests covering the ten documented behavior groups plus injection-only names and the fixture's install/teardown contract
- `/home/ido/mics_core/conftest.py` - added `sys.path` entry for `tests/`, `_install_fake_pigpio()` generator, `fake_pigpio` fixture; existing `collect_ignore` block and comment left untouched (plan 02's job)
- `/home/ido/mics_core/README.md` - new "Running the tests" section (venv path, delta command, `--strict`, cross-repo baseline default note)
- `/home/ido/mics-backend/.planning/phases/.../31-PYTEST-BASELINE.json` - the frozen baseline

## The fake's public control API (verbatim — plans C1/C2 are written against this)

```
fire_edge(gpio, level, tick=None) -> int
    Invokes every LIVE registration whose user_gpio matches `gpio` and whose
    edge mask admits `level`, sequentially, in registration order, with
    pigpio's exact 3 positional args (gpio, decoded_level, decoded_tick).
    Returns the count invoked; 0 and no exception if none match. A tick that
    doesn't fit struct's 'I' (>= 2**32) raises struct.error structurally.

simulate_wrap(pre_us=1000)
    Positions the fake tick at 2**32 - pre_us, so the next advance_tick past
    pre_us restarts it near zero.

set_tick(t)
    Sets the value pi.get_current_tick() returns (modulo 2**32).

advance_tick(us)
    Advances the fake tick by `us` microseconds, modulo 2**32.

registration_count(gpio=None) -> int
    Count of live registrations, or the count for one pin if `gpio` is given.

reset()
    Clears all module-level state (registrations, tick, calls). Call between
    tests — the state is global, mirroring one simulated pigpiod connection.
```

`pi(host='localhost', port=8888, show_errors=True)` exposes `.connected`, `.callback(user_gpio, edge=EITHER_EDGE, func=None)` → object with `.cancel()`/`.tally()`/`.reset_tally()`, `.get_current_tick()`, `.read(gpio)`, `.write(gpio, level)`, `.set_watchdog(user_gpio, wdog_timeout)`, `.stop()`, and `.calls` (shared `(name, args, kwargs)` log). `.arm_error(method_name)` (test-only, no upstream counterpart) makes the named method raise `fake_pigpio.error` once. Module constants: `RISING_EDGE=0`, `FALLING_EDGE=1`, `EITHER_EDGE=2`, `MSG_SIZ=12`. `pulse(gpio_on, gpio_off, delay)` record type. `class error(Exception)`.

## Resolved `requirements-dev.txt` contents

```
annotated-types==0.8.0, anyio==4.14.2, blosc==1.11.4, blosc2==4.11.0,
certifi==2026.7.22, charset-normalizer==3.5.1, h11==0.16.0, h2==4.4.1,
hpack==4.2.0, httpcore==1.0.9, httpx==0.28.1, hyperframe==6.1.0, idna==3.19,
iniconfig==2.3.0, markdown-it-py==4.2.0, mdurl==0.1.2, msgpack==1.2.1,
ndindex==1.10.1, npyscreen==5.0.4, numexpr==2.14.2, numpy==2.5.2,
packaging==26.3, pandas==3.0.5, pluggy==1.6.0, py-cpuinfo==9.0.0,
pydantic==2.13.4, pydantic_core==2.46.4, Pygments==2.21.0, pytest==9.1.1,
python-dateutil==2.9.0.post0, pytz==2026.3.post1, pyzmq==27.1.0,
requests==2.34.2, rich==15.0.0, scipy==1.18.0, six==1.17.0, tables==3.11.1,
threadpoolctl==3.6.0, tornado==6.5.8, typing-inspection==0.4.4,
typing_extensions==4.16.0, tzlocal==5.4.4, urllib3==2.7.0
```

`httpx`/`pydantic`/`rich`/`anyio`/`h2`/etc. are transitive deps of `blosc2` (pulled in by `blosc`), not imported directly by this tree — kept per the plan's own instruction to record what `pip freeze` actually resolved rather than hand-pruning.

## Module that stays in `collect_ignore` (unchanged from pre-plan state)

- `tests/test_compute_ops.py` — `from autopilot.hardware import Hardware` (now resolves), but 8 of its 12 tests transitively import `autopilot.tasks.mics_task` → `Event_Dispatcher.py:3` → `import pigpio`, still unresolved by design. Verified: un-ignoring would raise the failure count from 179 to 187 (+8 new fails, +4 new passes), so it stays ignored. Its original comment ("for exactly the npyscreen reason") is now half-stale — left untouched per Task 3's explicit instruction that plan 02 revisits this block.
- `tests/test_log_action_values.py` — `from autopilot.utils.Tracker import Tracker` → `logging_utils.py:2` → `Event_Dispatcher.py:3` → `import pigpio`. Same reasoning, unchanged.

## Decisions Made

- **pigpio, not npyscreen/tzlocal, is the actual last blocker for all 179 pre-existing failures.** Verified empirically: with the system interpreter, every one of the 179 failures reports `ModuleNotFoundError: No module named 'npyscreen'` as its first (and only observed) missing-module error, because `autopilot/__init__.py:4` imports `setup_autopilot` unconditionally before anything else. Installing `npyscreen` + `tzlocal` (this plan's dependency fix) makes `import autopilot` succeed, but every one of the same 179 tests then hits the *next* unconditional import in its chain — `autopilot/networking/Event_Dispatcher.py:3: import pigpio` (a protected file, not editable here) — reached via `autopilot.core.pilot`, `autopilot.tasks.task`, or `autopilot.utils.Tracker`. The plan's own hard rule ("Do NOT add pigpio to requirements-dev.txt") is honored, so this plan cannot and does not reduce the failure count below 179; it correctly identifies *why* and freezes that as the baseline's `note`, quoting the pre-fix numbers as instructed. Resolving it is out of this plan's stated scope (`fake_pigpio` is a fixture for opt-in use by later clock-layer tests, not wired into production code here).
- shellcheck installed as a static binary (`~/.local/bin/shellcheck`) rather than via `apt install` — this dev host has no passwordless `sudo`. `~/.local/bin` was already on `$PATH`, so the plan's verify command (`shellcheck --version`) resolves it exactly as if apt had installed it system-wide.
- `board`/`busio`/`zmq` (the bare PyPI package, not `pyzmq`) were briefly pip-installed during empirical iteration and then removed: `board` (PyPI) is an unrelated "Dojo tasks" package, not `adafruit-blinka`'s `board` module — installing it would have silently made `i2c.py`'s `import board` "succeed" against the wrong library. `busio` has no PyPI package at all (confirms it as genuinely Pi-only, `adafruit-blinka`). Neither is currently reachable by any collectible test (masked behind the same pigpio blocker), so no `collect_ignore` entry was added for either — added only what's empirically reachable, not hypothetically.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 - Blocking] shellcheck has no apt/sudo path on this dev host**
- **Found during:** Task 1
- **Issue:** `sudo apt install shellcheck` requires a password; no passwordless sudo configured
- **Fix:** Downloaded the official static binary release (v0.9.0, matching the apt candidate version) to `~/.local/bin/shellcheck`, already on `$PATH`
- **Files modified:** none tracked (binary outside the repo)
- **Verification:** `shellcheck --version` resolves it via `$PATH`
- **Committed in:** N/A (not a repo file)

**2. [Rule 1 - Bug in plan's own premise] Corrected which import blocks all 179 failures**
- **Found during:** Task 1 verification, deepened in Task 2
- **Issue:** The plan's `<measured_facts>` (and its Task 1 `<done>` prose, "the failure count is strictly below the 179 measured with the system interpreter") assumed fixing `npyscreen`/`tzlocal` would reduce the failure count. Empirically it does not — the count stays at exactly 179, because `pigpio` (explicitly excluded from `requirements-dev.txt` by this same plan) is the actual next link in the same import chain for all 179 tests.
- **Fix:** No code change — this is a documentation correction. Verified rigorously (diffed the 179 failing node IDs before/after the dependency fix: identical set; traced tracebacks directly to `Event_Dispatcher.py:3`). Recorded in `31-PYTEST-BASELINE.json`'s `note` field with the full chain and the pre-fix 179/203 numbers quoted, and here.
- **Files modified:** `31-PYTEST-BASELINE.json` (note field), this SUMMARY
- **Verification:** `tools/pytest_delta.py` confirms `new failures: 0` against this corrected baseline; `--strict` unchanged at 0 violations
- **Committed in:** `1b244b2`

---

**Total deviations:** 2 auto-fixed (1 blocking, 1 corrected premise)
**Impact on plan:** No scope creep. The corrected premise does not change any task's deliverables — it changes what the reader should expect the `<done>` prose's "strictly below 179" claim to mean (it doesn't hold, for a documented, verified reason, and the plan's own hard rule against installing pigpio is exactly why). All three tasks' own `<verify>` blocks pass as written; the automated verify chains do not hard-assert on the failure count (piped through `tail`, which swallows pytest's exit code), so no gate was bypassed to reach green.

## Issues Encountered

- `git push -u origin phase-31-modern-pi-platform` reported success but left no local tracking config (`branch.<name>.remote`/`.merge` unset) — an apparent proxy quirk in this environment. Re-ran `git push -u` a second time (branch already existed on the remote, `Everything up-to-date`) and the tracking config landed correctly. No force-push, no history rewrite, no `main` touched at any point.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness

- The branch, dev venv, delta gate and frozen baseline are in place for every subsequent Phase 31 plan to build on.
- `fake_pigpio` is ready for plans C1/C2's clean-room clock module tests — its public API (`fire_edge`, `simulate_wrap`, `set_tick`, `advance_tick`, `registration_count`) is documented verbatim above.
- **Carried-forward gap, not this plan's to close:** the 179 pre-existing failures remain pigpio-blocked and un-shrunk. They will not move until a later plan either wires `fake_pigpio` into production code paths (explicitly out of scope here — "the clock module does not exist yet") or replaces `Event_Dispatcher`'s pigpio usage outright. Plan 02 (npyscreen/setup-wizard removal) and later plans should not assume this count drops as a side effect of unrelated dependency work — it won't, for the reason documented above.
- `board`/`busio` (adafruit-blinka) remain genuinely unresolvable on this dev host and are currently invisible to `--strict`/pytest because they're masked behind the same pigpio chain; whichever later plan first unblocks that chain (partially or via the fixture) should expect `i2c.py`'s `MPR121` class to surface a *new* `ModuleNotFoundError: board` at that point, and will need to extend `collect_ignore` then, not now.

---
*Phase: 31-mics-core-modern-pi-platform-bookworm-64-bit-python-3-11-lgpio-unattended-boot*
*Completed: 2026-08-19*

## Self-Check: PASSED

All 10 files-created/modified paths verified present on disk; all 6 commit hashes
(`a0e3d10`, `a50de02`, `981fb0f`, `df56f2d`, `a535b39` in `mics_core`; `1b244b2` in
`mics-backend`) verified present via `git log --oneline --all`.
