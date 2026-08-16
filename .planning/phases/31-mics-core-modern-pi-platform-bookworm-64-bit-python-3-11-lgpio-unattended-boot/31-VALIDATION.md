---
phase: 31
slug: mics-core-modern-pi-platform-bookworm-64-bit-python-3-11-lgpio-unattended-boot
status: planned
nyquist_compliant: true
wave_0_complete: false
created: 2026-08-16
updated: 2026-08-16
---

# Phase 31 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.
>
> **Source of truth for design:** `31-RESEARCH.md` → `## Validation Architecture`.
> **Hard constraint:** every hardware capture is **USER-RUN**. The agent supplies the exact
> command, the user runs it on the Pi, the agent analyses the committed artifact. Never start or
> stop the pilot process, never run a Python file on the Pi, never run git on the Pi.

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
| **Phase exit command** | the above, plus `python3 tools/check_tree_integrity.py --final`, plus `shellcheck deploy/*.sh`, plus `analyse.py --gate` |
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

- **After every task commit:** `tools/pytest_delta.py` **and** `check_tree_integrity.py --strict`
- **After every plan wave:** full suite + `--strict`, plus `shellcheck deploy/*.sh` from wave 4 on
- **Before `/gsd:verify-work`:** full suite green, `--final` green with F3's NTP guard deliberately
  retired (plan 15), and `analyse.py --gate` exiting 0 on every profile x load pair (plan 16)
- **Max feedback latency:** **< 10 seconds** for every autonomous task. USER-RUN hardware tasks have
  a human-scale latency by construction; that is why there are only five of them and why each is
  batched into a single session.

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|-----------|-------------------|-------------|--------|
| 31-01-01 | 01 | 1 | PLAT-26 | integration | `git branch --show-current` + `pytest tests/ --tb=no` | ✅ | ⬜ pending |
| 31-01-02 | 01 | 1 | PLAT-26 | unit | `pytest -q tests/test_pytest_delta.py` then `tools/pytest_delta.py` | ❌ W0 | ⬜ pending |
| 31-01-03 | 01 | 1 | PLAT-26 | unit | `pytest -q tests/test_fake_lgpio_contract.py` | ❌ W0 | ⬜ pending |
| 31-02-01 | 02 | 2 | PLAT-01 | static | `pytest -q tests/test_shed_absences.py` + `--strict` | ❌ W0 | ⬜ pending |
| 31-02-02 | 02 | 2 | PLAT-01 | static+smoke | `pytest -q tests/test_shed_absences.py` + `python -c "import autopilot"` | ❌ W0 | ⬜ pending |
| 31-02-03 | 02 | 2 | PLAT-01 | integration | `tools/pytest_delta.py` + baseline `superseded` assertion | ✅ (after 01) | ⬜ pending |
| 31-03-01 | 03 | 3 | PLAT-02 | static | `pytest -q tests/test_python311_compat.py` | ❌ W0 | ⬜ pending |
| 31-03-02 | 03 | 3 | PLAT-03 | integration | `pytest -q tests/test_requirements_wheels.py` (skips offline) | ❌ W0 | ⬜ pending |
| 31-04-01 | 04 | 4 | PLAT-08 | integration | `--strict` + `git ls-files --error-unmatch pilot/prefs.json` must fail | ✅ | ⬜ pending |
| 31-04-02 | 04 | 4 | PLAT-08 | unit | `shellcheck deploy/render-prefs.sh` + `pytest -q tests/test_prefs_render.py` | ❌ W0 | ⬜ pending |
| 31-05-01 | 05 | 4 | PLAT-06,09,10,11,21 | unit | `pytest -q tests/test_unit_files.py` | ❌ W0 | ⬜ pending |
| 31-05-02 | 05 | 4 | PLAT-07 | unit | `shellcheck deploy/firstboot-once.sh` + `pytest -q tests/ -k firstboot` | ❌ W0 | ⬜ pending |
| 31-05-03 | 05 | 4 | PLAT-20 | unit | `pytest -q tests/ -k unit_files` + drop-in grep assertions | ❌ W0 | ⬜ pending |
| 31-06-01 | 06 | 4 | PLAT-23 | static | `ast.parse(..., feature_version=(3,7))` + `capture.py --help` | ❌ W0 | ⬜ pending |
| 31-06-02 | 06 | 4 | PLAT-23 | unit | `pytest -q tests/test_pulse_timing_analyse.py` | ❌ W0 | ⬜ pending |
| 31-07-01 | 07 | 5 | PLAT-04, PLAT-05 | static | `bash -n` + `shellcheck` + `pytest -q tests/test_installer_paths.py` | ❌ W0 | ⬜ pending |
| 31-07-02 | 07 | 5 | PLAT-04 | static | `shellcheck deploy/uninstall.sh` + unit-set equality test | ❌ W0 | ⬜ pending |
| 31-08-01 | 08 | 5 | PLAT-24 | **manual-only (capture)** | USER-RUN; see Manual-Only table | n/a | ⬜ pending |
| 31-08-02 | 08 | 5 | PLAT-24 | **manual-only (capture)** | USER-RUN logic-analyser calibration | n/a | ⬜ pending |
| 31-08-03 | 08 | 5 | PLAT-24 | integration | `analyse.py` over every `pigpio_*.jsonl` + log grep | ✅ (after 06) | ⬜ pending |
| 31-09-01 | 09 | 6 | PLAT-04..11,20,21 | **manual-only (capture)** | USER-RUN flash/install/reboot | n/a | ⬜ pending |
| 31-09-02 | 09 | 6 | PLAT-04..11,20,21 | static | `shellcheck deploy/*.sh` + the three deploy test modules | ✅ (after 05,07) | ⬜ pending |
| 31-09-03 | 09 | 6 | PLAT-04..11,20,21 | integration | evidence-log grep for all ten PLAT ids | ✅ | ⬜ pending |
| 31-10-01 | 10 | 7 | PLAT-12, PLAT-17 | static | `ast.parse` + no-`gpiochip_open(0)` grep | ✅ | ⬜ pending |
| 31-10-02 | 10 | 7 | PLAT-12, PLAT-17 | **manual-only (capture)** | USER-RUN spike on hardware | n/a | ⬜ pending |
| 31-10-03 | 10 | 7 | PLAT-12, PLAT-17 | integration | `analyse.py` over `spike_*.jsonl` + `31-SPIKE.md` grep | ✅ (after 06) | ⬜ pending |
| 31-11-01 | 11 | 8 | PLAT-12 | unit | `pytest -q tests/test_lgchip.py` (fake, 3 chip layouts + decoy) | ❌ W0 | ⬜ pending |
| 31-11-02 | 11 | 8 | PLAT-13 | unit | `pytest -q tests/test_i2c_port.py tests/test_mpr121_irq_hygiene.py` | ❌ W0 | ⬜ pending |
| 31-12-01 | 12 | 9 | PLAT-14 | static | `grep -c pigpio gpio.py` + classification completeness | ✅ | ⬜ pending |
| 31-12-02 | 12 | 9 | PLAT-14 | unit | `pytest -q tests/test_digital_in_alerts.py` + 3 protected tests | ❌ W0 | ⬜ pending |
| 31-13-01 | 13 | 10 | PLAT-15 | unit | `pytest -q tests/test_digital_out_tx.py` + script-machinery grep | ❌ W0 | ⬜ pending |
| 31-13-02 | 13 | 10 | PLAT-15 | unit | `pytest -q tests/test_pulse_train_frequency.py` (8000/8000/0 literal) | ❌ W0 | ⬜ pending |
| 31-14-01 | 14 | 10 | PLAT-18, PLAT-19 | unit | `pytest -q tests/test_event_dispatcher_clock.py` | ❌ W0 | ⬜ pending |
| 31-14-02 | 14 | 10 | PLAT-18, PLAT-19 | integration | `--strict` + one-line `git diff` on the manifest | ✅ | ⬜ pending |
| 31-15-01 | 15 | 11 | PLAT-16 | static | `pytest -q tests/test_no_pigpio.py` + tree-wide pigpio grep | ❌ W0 | ⬜ pending |
| 31-15-02 | 15 | 11 | PLAT-22 | static | `pytest -q tests/test_clock_block_removed.py` + `--final` | ❌ W0 | ⬜ pending |
| 31-16-01 | 16 | 12 | PLAT-24 | **manual-only (capture)** | USER-RUN lgpio capture campaign | n/a | ⬜ pending |
| 31-16-02 | 16 | 12 | PLAT-17, PLAT-25 | **manual-only (capture)** | USER-RUN V1/V3/V4 | n/a | ⬜ pending |
| 31-16-03 | 16 | 12 | PLAT-17,24,25 | integration | `analyse.py --gate` x10 + `--check-step` + full suite + `--strict` | ✅ (after 06) | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*
*"File Exists" ❌ W0 = the test file is created by that task itself, TDD-style (write it, watch it
fail, then implement). The shared infrastructure it depends on is created in plan 01.*

---

## Wave 0 Requirements

Plan 01 owns all of these. Nothing downstream is trustworthy until they are done.

- [ ] Dev-host import closure fixed so the 23 `tests/` modules actually run
      (measured start point: 179 failed / 203 passed, all import-chain failures)
- [ ] `requirements-dev.txt` + `/home/ido/.venvs/mics_core_dev`
- [ ] `31-PYTEST-BASELINE.json` — frozen failing-node-id set, re-baselined by plan 02 with a
      `superseded` block
- [ ] `tools/pytest_delta.py` — the committed delta gate, with its own tests
- [ ] `tests/fakes/fake_lgpio.py` — recording fake with an injectable chip table, arm-to-raise
      support, and a `.calls` log
- [ ] `tests/test_fake_lgpio_contract.py` — signature guard so the fake cannot drift from lgpio 0.2.2
- [ ] `fake_lgpio` fixture in the root `conftest.py`, installed at `sys.modules['lgpio']` before
      import

Additional Wave-0-adjacent prerequisites, owned by the plans that first need them:

- [ ] `shellcheck` installed on the dev host (plan 04, first shell script)
- [ ] `tools/pulse_timing/` capture + analyse + three synthetic fixtures (plan 06)
- [ ] Spare Pi 4B on the **pre-migration** image, spare SD card, two jumpered GPIO pins (plan 08)
- [ ] A logic analyser or scope, borrowed **once**, for the loopback calibration (plan 08)
- [ ] A multimeter for the per-device fail-safe check (plan 16 V4)

---

## Manual-Only Verifications

Every row is manual because it needs physical hardware the dev host does not have, **or** because
the standing hard rules forbid the agent from taking the action (running Python on the Pi, starting
or stopping the pilot). In each case the **capture is manual and the analysis is fully automated**
against a committed artifact, so the evidence is reproducible and reviewable even though its
production is not. This is the Phase 30 HYG-01/HYG-02 precedent.

| Behavior | Requirement | Plan | Why Manual | Test Instructions |
|----------|-------------|------|------------|-------------------|
| pigpio baseline pulse widths, 5 profiles x 2 loads | PLAT-24 | 08 | Needs the pre-migration image and a loopback jumper; agent may not run Python on the Pi | `capture.py --backend pigpio --profile <P> --out-pin <O> --in-pin <I> --out /tmp/pigpio_<P>_<load>.jsonl`, x10. Analysis: `analyse.py <file>` |
| 32-bit tick wraparound (V2) | PLAT-25 | 08 | Needs a 75-minute run on the old image; the wrap is at 71.58 min | `capture.py --backend pigpio --profile train --duration-s 4560 --out /tmp/pigpio_wrap_75min.jsonl` |
| Loopback vs external-observer calibration | PLAT-23, PLAT-24 | 08 | Needs a logic analyser or scope on the physical pin | `sigrok-cli --driver fx2lafw --config samplerate=24m --channels D0 --time 30s --output-file /tmp/la_valve.sr` alongside a `valve` capture |
| Unattended boot: flash → install → reboot → pilot up | PLAT-04,05,07,08,09,11 | 09 | Needs a real reboot of physical hardware; the clone and the reboot are the user's actions | `sudo bash deploy/install.sh` twice, edit `/boot/firmware/mics.conf`, `sudo reboot`, then the evidence command block in 31-09-PLAN Task 1 Step 7 |
| chrony replaced timesyncd and disciplines the clock | PLAT-20, PLAT-21 | 09 | Needs the provisioned card | `chronyc tracking; grep -R makestep /etc/chrony/; systemctl is-enabled systemd-timesyncd \|\| echo absent` |
| Units load on the target | PLAT-07..11 | 09 | `systemd-analyze verify` is only authoritative on the target | `systemd-analyze verify /etc/systemd/system/mics-*.service` |
| `SCHED_FIFO` actually reaches lgpio's threads | PLAT-17 | 10 | Needs a live process on the Pi | `for t in /proc/$(pgrep -f lgpio_probe)/task/*; do chrt -p ${t##*/}; done` |
| lgpio notification FIFO lands writable | PLAT-10 | 10, 16 | Needs a live process under systemd with `RuntimeDirectory` | `ls -la /run/mics/` — a `.lgd-nfy*` file must be present while the pilot runs |
| Real gpiochip label and line count | PLAT-12 | 09, 10 | Board-specific; only the hardware knows | `gpiodetect; gpioinfo \| head -5` and `lgpio_probe.py chips` |
| lgpio tx jitter, 4 arms | PLAT-17, PLAT-24 | 10 | Physical loopback measurement | `lgpio_probe.py tx ...` under and without `systemd-run -p CPUSchedulingPolicy=fifo` |
| Kernel event-FIFO headroom | PLAT-17 | 10 | Needs real edge rates | `lgpio_probe.py fifo --burst --seconds 60` |
| lgpio arm pulse widths, 5 profiles x 2 loads x 2 sched | PLAT-24 | 16 | Same as the baseline | `capture.py --backend lgpio ...` x20. Gate: `analyse.py --gate before after` |
| Forced clock step, ±1 h (V1) | PLAT-25 | 16 | Requires stepping a real system clock mid-capture | `sudo timedatectl set-ntp false; sudo date -s '+1 hour'; ...` during a `train` capture. Analysis: `analyse.py --check-step +3600` |
| Overnight soak, 8–12 h (V3) | PLAT-24, PLAT-09 | 16 | The only experiment that genuinely needs wall-clock time | `systemd-run --unit=mics-soak ... capture.py --duration-s 36000`; next morning `systemctl show mics-pilot -p NRestarts`, RSS, `journalctl --disk-usage` |
| Restart/reboot resilience (V4) | PLAT-09 | 16 | Requires killing and rebooting real hardware | 10x `systemctl kill -s SIGKILL mics-pilot` in 30 s, then `systemctl is-failed`; then `sudo reboot` and `systemctl is-active` |
| Physical fail-safe output level after SIGKILL | PLAT-15 | 16 | Requires a meter across an energised solenoid, per device | Meter across each output device, then `sudo systemctl kill -s SIGKILL mics-pilot`; report open/closed/chatter per device |

---

## Validation Sign-Off

- [x] All tasks have an `<automated>` verify command, or are `checkpoint:human-action` whose
      artifact is analysed by an automated command in the following task
- [x] Sampling continuity: no 3 consecutive tasks without an automated verify. Every autonomous
      task ends in `pytest_delta.py` + `check_tree_integrity.py --strict`; the longest USER-RUN run
      is 2 consecutive checkpoint tasks (plan 08 T1–T2, plan 16 T1–T2), each immediately followed by
      an automated analysis task
- [x] Wave 0 covers all MISSING references — every ❌ W0 row above is a test file created TDD-style
      by its own task, on infrastructure plan 01 provides
- [x] No watch-mode flags anywhere; every command terminates
- [x] Feedback latency < 10 s for all autonomous tasks (measured: pytest 4.96 s, `--strict` ~2 s)
- [x] `nyquist_compliant: true` set in frontmatter

**Basis for `nyquist_compliant: true`:** every one of the 39 tasks in the 16 plans carries an
automated verify. The five USER-RUN capture tasks are the only exceptions to *agent* execution, and
each is paired with an automated analysis task in the same plan that gates on the returned artifact
— so the sampling rate is preserved even across the human-in-the-loop steps. The Wave 0 instrument
(`pytest_delta.py`) exists specifically so that the pre-existing 179-failure debt cannot mask a new
regression.

**Approval:** pending execution
