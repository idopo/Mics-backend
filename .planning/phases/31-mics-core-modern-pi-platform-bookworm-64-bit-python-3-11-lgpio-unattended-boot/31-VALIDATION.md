---
phase: 31
slug: mics-core-modern-pi-platform-bookworm-64-bit-python-3-11-lgpio-unattended-boot
status: planned
nyquist_compliant: true
wave_0_complete: false
created: 2026-08-16
updated: 2026-08-17 (fourth pass — clean-room clock plans C1-C4 written; requirement coverage now COMPLETE)
---

# Phase 31 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.
>
> **Source of truth for scope:** `31-REVISED-SCOPE.md`. It supersedes the lgpio parts of
> `31-RESEARCH.md`; `31-RESEARCH.md` remains authoritative for systemd, chrony, journald, PEP 668
> and the Bookworm boot layout, and for `## Validation Architecture` (the loopback method, the
> profiles and the statistics, none of which depended on which library drives the pin).
> **Source of truth for waves and dependencies:** the `31-NN-PLAN.md` frontmatter. This table is
> derived from it, never the other way round. Re-derive it whenever a plan is re-waved.
> **Hard constraint:** every hardware capture is **USER-RUN**. The agent supplies the exact
> command, the user runs it, the agent analyses the committed artifact. Never start or
> stop the pilot process, never run a Python file on the Pi, never run git on the Pi.

---

## Scope of this document (read this first)

The phase was revised on **2026-08-17**. The lgpio migration was removed; **pigpio stays** and the
**clock layer** is replaced by a clean-room MICS-owned module. Consequences for this contract:

- Plans **31-10 through 31-16 no longer exist** — they are archived under `superseded-lgpio/`.
  Every row for them has been deleted, along with the `31-SPIKE.md` verdict-gate machinery that
  came from the dropped plan 10.
- Plans **31-01 through 31-09 survive, retargeted** (pass 1 of the revision). This document covers
  them completely.
- The four clean-room clock plans **C1-C4** were written in pass 2 (2026-08-17) and are covered in
  full below. They close what pass 1 left open: **PLAT-17, 18, 19, 22, 27, 28, 29, 30, 31 and 32
  now each have an owning plan.** The pass-1 note recording them as unowned is retired — see the
  sign-off. `31-C1`/`31-C2`/`31-C3`/`31-C4` are non-numeric plan ids matching the ROADMAP entry;
  the GSD frontmatter schema checks presence, not numeric type, and all plan discovery is
  `endsWith('-PLAN.md')`, so the naming is safe and validated.
- **PLAT-12 through PLAT-16 are DEFERRED** (⛔ in `REQUIREMENTS.md`) to a future lgpio/Pi-5 phase.
  They are correctly absent from this contract.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest (`/home/ido/mics_core/pytest.ini` + root `conftest.py`, both exist) |
| **Config file** | `/home/ido/mics_core/pytest.ini` (`testpaths = tests`, `addopts = -q`) |
| **Test runner** | `/home/ido/.venvs/mics_core_dev/bin/python` (created in plan 01 from `requirements-dev.txt`) |
| **Quick run command** | `cd /home/ido/mics_core && /home/ido/.venvs/mics_core_dev/bin/python -m pytest -q tests/ --tb=short` |
| **Delta gate (the one tasks actually use)** | `cd /home/ido/mics_core && /home/ido/.venvs/mics_core_dev/bin/python tools/pytest_delta.py` |
| **Full suite command** | `cd /home/ido/mics_core && /home/ido/.venvs/mics_core_dev/bin/python -m pytest tests/ --tb=no && python3 tools/check_tree_integrity.py --strict` |
| **Phase exit command** | the above, plus `python3 tools/check_tree_integrity.py --final`, plus `shellcheck deploy/*.sh`, plus `analyse.py --gate` and `analyse.py --check-wrap` |
| **Estimated runtime** | pytest ~5 s (measured, 381 tests in 4.96 s); `--strict` ~2 s; combined **< 10 s** |

### Why a delta gate rather than a bare exit code

Measured on the dev host 2026-08-16 with the system interpreter:
**179 failed / 203 passed / 381 collected**. Every one of the 179 is a third-party
`ModuleNotFoundError` chain (`npyscreen`, then `tzlocal`), not a code defect. Chaining
`pytest && next-thing` therefore fails for reasons unrelated to whatever it is gating.

Plan 01 fixes the dev-host import closure and freezes the remaining failures into
`31-PYTEST-BASELINE.json`. Plan 02 (the shed) deletes `autopilot/setup/`, removing the npyscreen
import chain, and re-baselines. From plan 01 onward, **every task verifies with
`tools/pytest_delta.py`**, which exits non-zero only on a NEW failure and reports `fixed:` lines for
recoveries. This is the same mechanism Phase 30 used (`30-PYTEST-BASELINE.json`'s `delta_command`),
promoted from an inline heredoc to a committed, tested script.

---

## Sampling Rate

- **After every task commit:** `tools/pytest_delta.py` **and** `check_tree_integrity.py --strict`.
  One documented exception: **plan 01 Task 1**, which runs before `31-PYTEST-BASELINE.json` and
  `tools/pytest_delta.py` exist — it is the task that creates them. It still runs `--strict`.
- **After every plan wave:** full suite + `--strict`, plus `shellcheck deploy/*.sh` from wave 4 on
- **Before `/gsd:verify-work`:** full suite green, `--final` green with F3's NTP guard deliberately
  retired (plan C3), `analyse.py --gate` exiting 0 on every profile x load pair and
  `analyse.py --check-wrap` exiting 0 (no backward jumps) on the C4 soak
- **Max feedback latency:** **< 10 seconds** for every autonomous task, with one measured exception
  (plan 03 Task 2 — see the sign-off note). USER-RUN hardware tasks have a human-scale latency by
  construction; that is why there are only **three** of them in this pass and why each is batched
  into a single session.

---

## Per-Task Verification Map

Waves below are copied from the plan frontmatter and re-derived 2026-08-17 (third pass).
**`wave == max(wave of every depends_on) + 1` holds for all thirteen plans**, and no two plans
sharing a wave name the same code file in `files_modified`:

- wave 4 = plans 04 (`pilot/prefs*`, `deploy/render-prefs.sh`, `tools/tree_*`), 06
  (`tools/pulse_timing/*`) and **C1** (`autopilot/utils/{tick_extender,clock}.py`,
  `tests/test_{tick_extender,mics_clock}.py`) — disjoint.
- wave 5 = plans 05 (`deploy/*.service`, `deploy/*.conf`, `tests/test_unit_files.py`), 08
  (planning-repo evidence log, `tools/pulse_timing/captures/`, `tools/pulse_timing/README.md`) and
  **C2** (`gpio.py`, `hardware/__init__.py`, `utils/common.py`, `task.py`, `logging_utils.py`,
  `Event_Dispatcher.py`, `tools/tree_protect_list.json`, three test modules) — disjoint. Note plan 06
  (wave 4) also writes `tools/pulse_timing/README.md`, and plan 04 (wave 4) also writes
  `tools/tree_protect_list.json`; different waves, so the edit order is strictly sequential.
  **C2's `depends_on` gained `31-06` on 2026-08-17** so it can run `tools/pulse_timing/py37_gate.py`:
  C2's `from autopilot.utils.clock import ...` in `gpio.py` is what pulls C1's two modules into that
  gate's closure, and plan 08 takes the Buster baseline on Python 3.7.3. **The wave is unchanged** —
  `max(C1=4, 03=3, 06=4) + 1 = 5` — and 06 is read-only from C2's point of view (C2 runs the script,
  it does not write to `tools/pulse_timing/`), so no file-ownership conflict is introduced. C1 could
  not take this dependency: plan 06 is in C1's own wave, and at that point nothing imports the clock,
  so the closure would not reach it — C1 gates the 3.7 constraint inline instead.
- wave 6 = plans 07 (`deploy/install.sh`, `deploy/uninstall.sh`, `tests/test_installer_paths.py`,
  `README.md`) and **C3** (`core/pilot.py`, `external/__init__.py`,
  `tools/tree_integrity/final_checks.py`, two test modules) — disjoint. Plan 02 (wave 2) and plan 04
  (wave 4) also write `final_checks.py`; different waves.
- wave 7 = plan 09 alone. wave 8 = **C4** alone (`tools/pulse_timing/clock_soak.py`,
  `tests/test_clock_soak.py`, `tools/pulse_timing/README.md`, `captures/`, the evidence log).

**13 plans, 8 waves, 35 tasks.**

| Task ID | Plan | Wave | Requirement | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|-----------|-------------------|-------------|--------|
| 31-01-01 | 01 | 1 | PLAT-26 | integration | `git branch --show-current` + `pytest tests/ --tb=no` | ✅ | ⬜ pending |
| 31-01-02 | 01 | 1 | PLAT-26 | unit | `pytest -q tests/test_pytest_delta.py` then `tools/pytest_delta.py` | ❌ W0 | ⬜ pending |
| 31-01-03 | 01 | 1 | PLAT-26 | unit | `pytest -q tests/test_fake_pigpio_contract.py` + the inline 3-arg / 32-bit-tick / wrap / stock-surface assertions | ❌ W0 | ⬜ pending |
| 31-02-01 | 02 | 2 | PLAT-01 | static | `pytest -q tests/test_shed_absences.py` + `--strict` | ❌ W0 | ⬜ pending |
| 31-02-02 | 02 | 2 | PLAT-01 | static+smoke | `pytest -q tests/test_shed_absences.py` + `python -c "import autopilot"` | ❌ W0 | ⬜ pending |
| 31-02-03 | 02 | 2 | PLAT-01 | integration | `tools/pytest_delta.py` + baseline `superseded` assertion | ✅ (after 01) | ⬜ pending |
| 31-03-01 | 03 | 3 | PLAT-02 | static | `pytest -q tests/test_python311_compat.py` | ❌ W0 | ⬜ pending |
| 31-03-02 | 03 | 3 | PLAT-03 | integration | `pytest -q tests/test_requirements_wheels.py` (skips offline) + the pigpio-pin / no-lgpio counted assertions | ❌ W0 | ⬜ pending |
| 31-04-01 | 04 | 4 | PLAT-08 | integration | `--strict` + `git ls-files --error-unmatch pilot/prefs.json` must fail | ✅ | ⬜ pending |
| 31-04-02 | 04 | 4 | PLAT-08 | unit | `shellcheck deploy/render-prefs.sh` + `pytest -q tests/test_prefs_render.py` | ❌ W0 | ⬜ pending |
| 31-06-01 | 06 | 4 | PLAT-23 | static+unit | `pytest -q tests/test_py37_gate.py` (7 cases incl. positive control) + `py37_gate.py` (closure incl. `gpio.py` **and** `wrap_witness.py`) + both `--help`s | ❌ W0 | ⬜ pending |
| 31-06-02 | 06 | 4 | PLAT-23, PLAT-25 | unit | `pytest -q tests/test_pulse_timing_analyse.py` + `--check-wrap` in BOTH directions (`--expect-defect` passes on the defective fixture, default mode fails on it) | ❌ W0 | ⬜ pending |
| 31-C1-01 | C1 | 4 | PLAT-29 | unit | `pytest -q tests/test_tick_extender.py` + the inline identity / single-wrap-`+1500 µs` / Case-C-out-of-order-is-not-a-wrap / **Case-D forward-gap asserted four ways (step size, `ambiguous=True`, non-latching, `out_of_order` untouched)** / **discriminator both sides of `MAX_OUT_OF_ORDER_US`** / `duplicates` increments / `(int, bool)` return shape / range-`ValueError` / two-thread-`wraps==1` assertions | ❌ W0 | ⬜ pending |
| 31-C1-02 | C1 | 4 | PLAT-30 | unit | `pytest -q tests/test_mics_clock.py` + the single-`CLOCK_REALTIME`-site scan, the PLAT-29 heartbeat-bound `ValueError`, the `PatchedClientError` guard, `ClockNotReady` before calibration, the complete `counters()` key set with only the **fault** class asserted zero, and the **inline `ast.parse(feature_version=(3,7))` + PEP-585/604/dataclass-slots/f-string-`=` check on both modules** (they enter plan 06's 3.7 closure at C2) | ❌ W0 | ⬜ pending |
| 31-05-01 | 05 | 5 | PLAT-06,09,10,11,21 | unit | `pytest -q tests/test_unit_files.py` + counted `LG_WD`/`lgpio` absence in `deploy/` + **counted `pigpiod`-absence in `mics-pilot.service` and absence of `deploy/pigpiod-mics.conf`** (PLAT-33 withdrawn 2026-08-17) | ❌ W0 | ⬜ pending |
| 31-05-02 | 05 | 5 | PLAT-07 | unit | `shellcheck deploy/firstboot-once.sh` + `pytest -q tests/ -k firstboot` | ❌ W0 | ⬜ pending |
| 31-05-03 | 05 | 5 | PLAT-20 | unit | `pytest -q tests/ -k unit_files` + the chrony/journald drop-in assertions (no `makestep`, no `driftfile`, `Storage=volatile`) + the counted absence of any `pigpiod` unit or drop-in | ❌ W0 | ⬜ pending |
| 31-08-00 | 08 | 5 | PLAT-24 | static | `py37_gate.py` + `--list` reaches `gpio.py` and `wrap_witness.py` + closure not shrunk vs `31-06-SUMMARY.md` — **the machine-checked pre-capture gate, runs before any user command** | ✅ (after 06) | ⬜ pending |
| 31-08-01 | 08 | 5 | PLAT-24 | **manual-only (capture)** | USER-RUN "before" campaign + LA calibration; gated by task `31-08-00` — see Manual-Only table | n/a | ⬜ pending |
| 31-08-02 | 08 | 5 | PLAT-25 | **manual-only (capture)** | USER-RUN 90-minute wrap-witness run with the DEPLOYED patched client | n/a | ⬜ pending |
| 31-08-03 | 08 | 5 | PLAT-24, PLAT-25 | integration | `analyse.py` over every `before_*.jsonl` + `analyse.py --check-wrap --expect-defect` + evidence-log section assertions | ✅ (after 06) | ⬜ pending |
| 31-C2-01 | C2 | 5 | PLAT-27, PLAT-31 | unit | `pytest -q tests/test_single_clock_invariant.py` + 3 protected tests + the counted `task.py:199`-seam / `hardware_state` / single-`CLOCK_REALTIME` / `assign_cb`-signature / `localize_tz(str)`-`TypeError` / **zero-`isoformat`-in-`gpio.py`** assertions + **`py37_gate.py` passing with both clock modules provably inside its closure** | ❌ W0 | ⬜ pending |
| 31-C2-02 | C2 | 5 | PLAT-18, PLAT-19, PLAT-31 | unit | `pytest -q tests/test_event_dispatcher_clock.py` + the counted `import pigpio`/`get_current_tick`/`ticks_to_timestamp` absence, drop-counter survival, `logging_utils.py:95` immutability, and the one-manifest-entry diff check | ❌ W0 | ⬜ pending |
| 31-C2-03 | C2 | 5 | PLAT-27, PLAT-31 | integration | `pytest -q tests/test_edge_timestamp_end_to_end.py` — **the mandatory two-route assertion**: one edge, `fire_edge` returns 2, both payloads carry the same `t_mono_ns` and both are hardware-stamped — plus the **two-thread slot-concurrency invariant**, the corrected `@auto_log`-count guard (`@auto_log == 1`, `auto_log == 2`) and all five protected tests unmodified | ❌ W0 | ⬜ pending |
| 31-07-01 | 07 | 6 | PLAT-04, PLAT-05 | static | `bash -n` + `shellcheck` + `pytest -q tests/test_installer_paths.py` + counted "no pigpio purge / no `python3-pigpio` / **no `enable pigpiod`** / **no `pigpiod.service.d`** / `pigpio` package IS installed" (PLAT-33 withdrawn) | ❌ W0 | ⬜ pending |
| 31-07-02 | 07 | 6 | PLAT-04 | static | `shellcheck deploy/uninstall.sh` + unit-set equality test | ❌ W0 | ⬜ pending |
| 31-C3-01 | C3 | 6 | PLAT-20, PLAT-28 | static | `pytest -q tests/test_stock_pigpio_only.py` + the counted `pilot.py` forbidden-token scan, the exactly-one-argument-free `pigpio.pi()` check, `get_clock().attach(` presence, both `clear_scripts` survivors, no vendored `pigpio.py`, the single `requirements.txt` pin, the chrony drop-in precondition, **the `init_pigpio`/`start_pigpiod`/`kill_proc` PRESERVATION counts** and **the counted absence of any `pigpiod` unit or drop-in** (PLAT-33 withdrawn 2026-08-17) | ❌ W0 | ⬜ pending |
| 31-C3-02 | C3 | 6 | PLAT-22 | static | `pytest -q tests/test_clock_block_removed.py` + the counted retirement of `NTP_CALLS`/`CLOCK_COMMENTS`/**`def _ntp_violations`**/**`+= _ntp_violations(`** (the definition and call forms, **never** the bare string, which survives as prose at `final_checks.py:150` inside the still-live HOLD 1 block), the five surviving `f3_toggles` assertions, the `PLAT-22`/`resolved` comment, the `git show HEAD` non-vacuity check, and **`--final` reporting no F3 NTP/clock-block violation** | ❌ W0 | ⬜ pending |
| 31-09-01 | 09 | 7 | PLAT-04..11,20,21 | **manual-only (capture)** | USER-RUN flash/install/reboot/**kill-storm (mandatory, the only PLAT-09 evidence before C4)** + the daemon-dies-with-the-pilot observation | n/a | ⬜ pending |
| 31-09-02 | 09 | 7 | PLAT-04..11,20,21 | static | `shellcheck deploy/*.sh` + the three deploy test modules + the requirements pigpio-pin survival check | ✅ (after 05,07) | ⬜ pending |
| 31-09-03 | 09 | 7 | PLAT-04..11,20,21 | integration | evidence-log assertion for all ten PLAT ids + `NRestarts` + "not proven here" | ✅ | ⬜ pending |
| 31-C4-00 | C4 | 8 | PLAT-24, PLAT-25, PLAT-32 | unit+static | `pytest -q tests/test_clock_soak.py` (incl. `--check-wrap` in BOTH directions on the soak's own output **and the `route` nine-key set asserted by set-equality, the same check Task 3 runs**) + the pre-flight gate: C1-C3 suites green, `--final` free of F3 clock violations, `clock_soak.py` NOT in the py37 closure, plan 08 baseline present, evidence log ready | ❌ W0 | ⬜ pending |
| 31-C4-01 | C4 | 8 | PLAT-25, PLAT-32 | **manual-only (capture)** | USER-RUN >= 3-wrap soak (4.33 h) under `stress-ng`, with a forced ±1 h wall-clock step mid-run; gated by `31-C4-00` — see Manual-Only table | n/a | ⬜ pending |
| 31-C4-02 | C4 | 8 | PLAT-17, PLAT-24, PLAT-25 | **manual-only (capture)** | USER-RUN 20 paired "after" captures across two scheduling arms, four clock-step captures, the `chrt -p` per-thread read-out and the per-device fail-safe check | n/a | ⬜ pending |
| 31-C4-03 | C4 | 8 | PLAT-17, PLAT-24, PLAT-25, PLAT-32 | integration | `analyse.py --check-wrap` (**default direction, exit 0**) + four `--check-step ±3600` + `--gate` over all 20 pairs + the trailer/counter/route/provenance assertions + evidence-log content assertions | ✅ (after 06, 08) | ⬜ pending |

### Requirement coverage — complete

Every active PLAT id (**PLAT-01–11, 17–32**) appears in at least one plan's `requirements`
frontmatter. PLAT-12–16 appear in none, which is correct — they are ⛔ DEFERRED. **PLAT-33 appears in
none, which is also correct — it was ⛔ WITHDRAWN 2026-08-17** by user decision: the `pigpiod` spawn
stays in the pilot, because `external.start_pigpiod()`'s `kill_proc` hook is what closes the
solenoids at session end, and a supervised daemon would outlive a crashed pilot with `VALVE1-4` /
`AIR_PUF` / `ODOR1-5` energised. It was removed from plans 05, 07, 09 and C3 in the same pass.
Verified 2026-08-17 by parsing all thirteen plan frontmatters. The pass-1 gap (PLAT-17, 18, 19, 22,
27, 28, 29, 30, 31, 32 unowned) is **closed**.

| Plan | Requirements claimed |
|------|----------------------|
| C1 | PLAT-29, PLAT-30 |
| C2 | PLAT-18, PLAT-19, PLAT-27, PLAT-31 |
| C3 | PLAT-20, PLAT-22, PLAT-28 |
| C4 | PLAT-17, PLAT-24, PLAT-25, PLAT-32 |

**One honest note on PLAT-32.** The requirement text ("loss is detected and reported ... surface a
count") is *claimed* by C4, but the counters it reads are *built* in C1 (`counters()`) and C2
(`_dropped_no_clock` / `_dropped_on_send`). C4 owns the accounting and the criterion; C1 and C2 own
the instrument. That split is deliberate and is stated in C4's `<soak_design>`, along with the harder
limitation: **`pigpiod` exposes no dropped-sample counter to the Python client**, so "zero dropped
samples" is evidenced by commanded-vs-observed edge counts plus our own counters plus the daemon's
journal — never by a daemon-reported figure.

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*
*"File Exists" ❌ W0 = the test file is created by that task itself, TDD-style (write it, watch it
fail, then implement). The shared infrastructure it depends on is created in plan 01.*
*Rows are ordered by wave, then by plan, so the parallel sets are visible: waves 4 and 5 each carry
more than one plan.*

---

## Wave 0 Requirements

Plan 01 owns all of these. Nothing downstream is trustworthy until they are done.

- [ ] Dev-host import closure fixed so the 23 `tests/` modules actually run
      (measured start point: 179 failed / 203 passed, all import-chain failures)
- [ ] `requirements-dev.txt` + `/home/ido/.venvs/mics_core_dev` — **without** a real `pigpio`, so a
      test cannot accidentally import the library instead of the fake
- [ ] `31-PYTEST-BASELINE.json` — frozen failing-node-id set, re-baselined by plan 02 with a
      `superseded` block
- [ ] `tools/pytest_delta.py` — the committed delta gate, with its own tests
- [ ] `tests/fakes/fake_pigpio.py` — recording fake of the **stock** pigpio client, with a `.calls`
      log and arm-to-raise support
- [ ] `tests/fakes/fake_pigpio.py` — **`fire_edge(gpio, level, tick)`**, plus the single ordered
      registration list `pi.callback()` writes and `.cancel()` unregisters. This is the load-bearing
      one: every clock assertion in C1/C2 is "inject a tick, read a known monotonic value back", and
      none of them is writable without it. `fire_edge` invokes each matching live registration with
      pigpio's **3 positional** args `(gpio, level, tick)`, **sequentially, in registration order,
      from the single simulated notify thread**, and returns how many it invoked — C2 relies on that
      count, because `Digital_Out.is_trigger = True` means one edge legitimately fires **two**
      registrations
- [ ] `tests/fakes/fake_pigpio.py` — **`simulate_wrap()` / `set_tick()` / `advance_tick()`**, so the
      71.6-minute defect is reproducible in microseconds. C1 exists to survive that wrap; a fake
      that cannot produce one makes PLAT-29 untestable
- [ ] The 32-bit tick is **structural**: `fire_edge` round-trips through
      `struct.pack('HHII', ...)`, so a `2**32` tick raises from `struct` rather than from a
      hand-written bounds check, and `MSG_SIZ == 12 == struct.calcsize('HHII')`
- [ ] `tests/test_fake_pigpio_contract.py` — signature guard so the fake cannot drift from the real
      client, **plus** the delivery-shape assertions (3 positional args, no kwargs, tick unchanged,
      registration-order dispatch, `.cancel()` unregisters one entry), **plus the PLAT-28 guard**:
      `pi(sync_ticks=True)` raises `TypeError` and the fake has no `synchronize` /
      `ticks_to_timestamp`. Without that last one the clock module could be written against the very
      patch the phase deletes
- [ ] `fake_pigpio` fixture in the root `conftest.py`, installed at `sys.modules['pigpio']` before
      import

Additional Wave-0-adjacent prerequisites, owned by the plans that first need them:

- [ ] `shellcheck` installed on the dev host (plan 01 Task 1, ahead of plan 04's first shell script)
- [ ] `tools/pulse_timing/` capture + wrap_witness + analyse + `py37_gate.py` + four synthetic
      fixtures (plan 06)
- [ ] Spare Pi 4B on the **pre-migration** image, **carrying the DEPLOYED patched `pigpio.py`**,
      spare SD card, two jumpered GPIO pins (plan 08)
- [ ] A logic analyser or scope, borrowed **once**, for the loopback calibration (plan 08)
- [ ] A multimeter for the per-device fail-safe check (plan C4)

---

## Manual-Only Verifications

Every row is manual because it needs physical hardware the dev host does not have, **or** because
the standing hard rules forbid the agent from taking the action (running Python on the Pi, starting
or stopping the pilot). In each case the **capture is manual and the analysis is fully automated**
against a committed artifact, so the evidence is reproducible and reviewable even though its
production is not. This is the Phase 30 HYG-01/HYG-02 precedent.

| Behavior | Requirement | Plan | Why Manual | Test Instructions |
|----------|-------------|------|------------|-------------------|
| "before" pulse widths, 5 profiles x 2 loads | PLAT-24 | 08 | Needs the pre-migration image and a loopback jumper; agent may not run Python on the Pi | `capture.py --profile <P> --arm before --out-pin <O> --in-pin <I> --out /tmp/before_<P>_<load>.jsonl`, x10. Analysis: `analyse.py <file>`. **Agent precondition:** task `31-08-00`, an `auto` task whose `<automated>` block runs `py37_gate.py`, asserts `hardware/gpio.py` and `wrap_witness.py` are in the closure, and asserts the closure did not shrink versus `31-06-SUMMARY.md`. It runs before the checklist is issued and it is an exit code, not agent discipline |
| Loopback vs external-observer calibration | PLAT-23, PLAT-24 | 08 | Needs a logic analyser or scope on the physical pin | `sigrok-cli --driver fx2lafw --config samplerate=24m --channels D0 --time 30s --output-file /tmp/la_valve.sr` alongside a `valve` capture. Batched into the same session as the "before" campaign so the analyser is borrowed once |
| **71.6-minute backward jump, in the wild** | PLAT-25 (evidence for PLAT-29/30) | 08 | Needs a >= 80-minute run against the DEPLOYED patched client on the pre-migration image | `wrap_witness.py --in-pin <I> --out-pin <O> --interval-s 1 --duration-s 5400 --out /tmp/wrap_witness_patched.jsonl`. Analysis: `analyse.py --check-wrap --expect-defect <file>` must exit 0, and the measured jump magnitude is reported against the predicted 4294.967296 s. Precondition: `grep -c 'def synchronize'` on the spare's `pigpio.py` is non-zero, or the run measures a stock client and proves nothing |
| Unattended boot: flash → install → reboot → pilot up | PLAT-04,05,07,08,10,11,33 | 09 | Needs a real reboot of physical hardware; the clone and the reboot are the user's actions | `sudo bash deploy/install.sh` twice, `systemctl cat pigpiod.service`, edit `/boot/firmware/mics.conf`, `sudo reboot`, then the evidence command block in 31-09-PLAN Task 1 Step 8 |
| **Restart limit provoked (kill storm)** | PLAT-09 | 09 | Requires killing real hardware repeatedly | 10x `sudo systemctl kill -s SIGKILL mics-pilot` inside 30 s, then `systemctl is-failed mics-pilot` (must not be `failed`) and `systemctl show mics-pilot -p NRestarts`. **Mandatory in plan 09** — the pilot no longer crash-loops by itself now that pigpio is installed rather than purged, so the property must be provoked or it goes untested until C4 |
| chrony replaced timesyncd and disciplines the clock | PLAT-20, PLAT-21 | 09 | Needs the provisioned card | `chronyc tracking; grep -R makestep /etc/chrony/; systemctl is-enabled systemd-timesyncd \|\| echo absent` |
| Units load on the target | PLAT-07..11 | 09 | `systemd-analyze verify` is only authoritative on the target | `systemd-analyze verify /etc/systemd/system/mics-*.service` |
| The pilot's own `pigpiod` spawn works under systemd | PLAT-04 | 09 | first time `sudo pigpiod ...` runs from a service cgroup rather than a login shell; passwordless sudo, `KillMode` reaping and whether the daemon dies on a clean stop are all unobservable off-target | `ps -o pid=,ppid=,args= -C pigpiod` before and after `systemctl stop mics-pilot` |
| Real gpiochip label and line count | *(deferred Pi-5/RP1 phase)* | 09 | Board-specific; only the hardware knows | `gpiodetect; gpioinfo \| head -5`. Captured opportunistically while the card is in hand; **no plan in this phase consumes it** |
| ≥3 wraps under load with zero backward jumps | PLAT-25, PLAT-29, PLAT-30 | C4 | Needs > 3.6 h of real time on real hardware | `analyse.py --check-wrap` (default mode — must exit 0) over the soak artifact. **Known not to be vacuous:** plan 08 ran the same tool in `--expect-defect` mode against the deployed patched client and it fired |
| **Both event paths agree on the same edge AFTER HOURS** | PLAT-27 | C4 | The dev-host test proves the mechanism; only real time proves it does not decay — which is exactly how the design being replaced fails | The soak's `route` records: every sampled edge yields two payloads with equal `t_mono_ns`, both hardware-stamped. Zero disagreements |
| Forced clock step, ±1 h | PLAT-25 | C4 | Requires stepping a real system clock mid-capture | `sudo timedatectl set-ntp false; sudo date -s '+1 hour'` during a `train` capture. Analysis: `analyse.py --check-step +3600` |
| "after" pulse widths, 5 profiles x 2 loads x 2 sched arms | PLAT-17, PLAT-24 | C4 | Same as the baseline | `capture.py --arm after-other` / `--arm after-fifo10` x20. Gate: `analyse.py --gate before after` |
| `SCHED_FIFO` actually reaches the notify thread | PLAT-17 | C4 | Needs a live process on the Pi | `for t in /proc/$(pgrep -f mics)/task/*; do chrt -p ${t##*/}; done` |
| Dropped-sample / notification-loss accounting | PLAT-32 | C4 | Needs a starved real daemon | soak under load with the drop counters read out; zero **undetected** drops is the criterion |
| Physical fail-safe output level after SIGKILL | PLAT-32-adjacent (reward-path safety) | C4 | Requires a meter across an energised solenoid, per device | Meter across each output device, then `sudo systemctl kill -s SIGKILL mics-pilot`; report open/closed/chatter per device. **Note the behaviour is pigpio's: the daemon outlives the client and keeps driving the pin**, so this is the pre-existing risk, not a new one |

**PLAT-27 is deliberately absent from this table.** The single-clock invariant is proven by test on
the dev host against the plan-01 fake — one edge injected via `fake_pigpio.fire_edge(gpio, level,
tick)`, which reports it invoked **two** registrations because `Digital_Out.is_trigger = True` and
`record=True` is the default, and **both** dispatched payloads (the `logging_utils.py:97` route and
the `task.py:283` route) asserted to carry the same derived `t_mono_ns` and both marked
hardware-stamped. That test is **task `31-C2-03`**, `tests/test_edge_timestamp_end_to_end.py`. Its honest limit is
carried forward deliberately: a dev-host test with an injected tick says nothing about whether the
two paths are still aligned after hours of continuous operation, which is precisely the way the
current design fails. **C4 closes that half on hardware** via the soak's `route` records, and both
C2's summary and C4's NOT PROVEN section must say that neither piece of evidence substitutes for the
other.

---

## Validation Sign-Off

- [x] All tasks in this pass have an `<automated>` verify command, or are
      `checkpoint:human-action` whose artifact is analysed by an automated command in the following
      task
- [x] Sampling continuity: no 3 consecutive tasks without an automated verify. Every autonomous
      task ends in `pytest_delta.py` + `check_tree_integrity.py --strict` — **with exactly one
      carve-out, plan 01 Task 1**, which runs before the baseline and the delta script exist because
      it is the task that creates them (it still runs `--strict`). Re-verified 2026-08-17 (third
      pass) by scanning every `<automated>` block in the nine surviving plans: **21** autonomous
      verifies, 20 carry both gates, 1 carries `--strict` only. The longest USER-RUN run is **2**
      consecutive checkpoint tasks (plan 08 T1–T2), immediately followed by the automated analysis
      task 31-08-03, and plan 08's pair is **preceded** by the auto task 31-08-00. Plan 09's single
      checkpoint is followed by two automated tasks.
      *This is why plan 08's logic-analyser calibration was merged into the "before" campaign
      checklist rather than kept as a third checkpoint: adding the new wrap-witness task as a
      separate checkpoint would otherwise have produced three consecutive human-in-the-loop tasks.
      Same hardware, same jumper, same session — nothing was lost by batching them.*
- [x] **Exit-code integrity swept, 2026-08-17 (fourth pass).** Every `<automated>` block in all
      **thirteen** plans was re-scanned for constructs that convert a failure into exit 0. The
      corpus now uses exactly two shapes: an unbroken `&&` chain, and a `python3 -c` that inspects
      state and calls `sys.exit(<message>)` on failure. Specifically confirmed absent:
      **(a)** no `;` sequencing that would drop a non-zero status;
      **(b)** no `||` that converts a failure into success — the only `||` in the corpus is
      `|| exit 1` inside the `for` loop in plan 08 T3, which makes a loop-iteration failure
      **fatal** and therefore strengthens the exit code;
      **(c)** no `! tool | grep -q "^VIOLATION"` idiom anywhere — that form passes when the tool
      crashes and prints nothing, and it was removed with the plans that used it;
      **(d)** no trailing `echo`/`grep -c` as the last element of a chain (a `grep -c` printing `0`
      exits 1, and an `echo` always exits 0 — both were replaced by explicit Python checks that
      print the count **and** set the exit code);
      **(e)** every absence claim is proven with an explicit count printed by Python
      (`text.count(...)`), never with a bare grep — an RTK-proxied grep can render a matching line
      blank, so a silent grep is not evidence.
      No plan instructs `--rebaseline`; re-confirmed by full-corpus scan across all thirteen plans.
      Re-verified mechanically for C1-C4 on 2026-08-17: **9 autonomous `<automated>` blocks, every
      one an unbroken `&&` chain, every one containing `tools/pytest_delta.py` and ending in
      `python3 tools/check_tree_integrity.py --strict`, zero `||`, zero shell-level `;`, zero
      trailing `echo`/`grep -c`, zero `! tool | grep` idioms, zero `--rebaseline`.**
- [x] Wave 0 covers all MISSING references — every ❌ W0 row above is a test file created TDD-style
      by its own task, on infrastructure plan 01 provides
- [x] No watch-mode flags anywhere; every command terminates
- [x] Feedback latency < 10 s for all autonomous tasks (measured: pytest 4.96 s, `--strict` ~2 s),
      **except plan 03 Task 2**, `tests/test_requirements_wheels.py`, which makes a PyPI round trip
      per pin to prove every dependency resolves to a prebuilt aarch64 cp311 wheel (or an
      allow-listed pure-Python `py3-none-any` wheel — `pigpio` and `Adafruit-PureIO` are the two
      documented entries). That is network time, it is the point of the test, and the test **skips
      cleanly when offline** — so the gate never becomes a hang or a false failure on a disconnected
      dev host. No other task leaves the machine
- [x] `nyquist_compliant: true` **re-asserted 2026-08-17 for the full thirteen-plan set**, C1-C4
      included
- [x] **Requirement coverage is COMPLETE.** All **27** active ids (PLAT-01–11, 17–32) are claimed by
      at least one plan; PLAT-12–16 are claimed by none (⛔ DEFERRED) and **PLAT-33 by none
      (⛔ WITHDRAWN 2026-08-17, user decision — the `pigpiod` spawn stays in the pilot as the output
      fail-safe)**, both correct. Machine-verified by parsing all thirteen `requirements:` frontmatter
      fields. **The pass-1 sign-off item recording PLAT-17/18/19/22/27/28/29/30/31/32 as unowned is
      hereby cleared.**
- [x] **Wave derivation re-checked mechanically, 2026-08-17 (and again after the revision pass).**
      `wave == max(wave of every depends_on) + 1` holds for all thirteen plans, and no two plans
      sharing a wave name the same file in `files_modified`. Waves 1-3 and 7 carry one plan each;
      wave 4 = {04, 06, C1}, wave 5 = {05, 08, C2}, wave 6 = {07, C3}, wave 8 = {C4}. **The one
      `depends_on` change in the revision pass — C2 gaining `31-06` so it can run `py37_gate.py`
      against the closure its own `gpio.py` import creates — leaves every wave unchanged**
      (`max(C1=4, 03=3, 06=4) + 1 = 5`) and introduces no shared-file conflict, since C2 only
      executes plan 06's script and writes nothing under `tools/pulse_timing/`.

**Basis for `nyquist_compliant: true`:** every one of the **35** tasks in the thirteen plans carries
an automated verify or is a `checkpoint:human-action` whose artifact is gated by an automated task in
the same plan. The **five** USER-RUN capture tasks — `31-08-01`, `31-08-02`, `31-09-01`, `31-C4-01`,
`31-C4-02`, matching the Manual-Only table exactly — are the only exceptions to *agent* execution.
The longest run of consecutive human-in-the-loop tasks is **2** (plan 08 T1–T2, and C4 T1–T2); each
pair is **preceded** by an `auto` gate task (`31-08-00`, `31-C4-00`) and **followed** by an automated
analysis task (`31-08-03`, `31-C4-03`), so the sampling rate is preserved across the human steps and
no three consecutive tasks lack an automated verify. C4's pre-flight gate exists for the same reason
plan 08's does: 4.5 hours of the user's hardware time is too expensive to spend on a harness nobody
machine-checked. The Wave 0 instrument (`pytest_delta.py`) exists specifically so that the
pre-existing 179-failure debt cannot mask a new regression.

**Approval:** planning complete (13 plans, 8 waves, 35 tasks, full requirement coverage); pending
execution
