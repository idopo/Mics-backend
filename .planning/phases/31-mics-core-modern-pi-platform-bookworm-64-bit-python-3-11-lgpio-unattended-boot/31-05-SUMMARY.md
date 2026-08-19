---
phase: 31-mics-core-modern-pi-platform-bookworm-64-bit-python-3-11-lgpio-unattended-boot
plan: 05
subsystem: platform
tags: [systemd, unattended-boot, chrony, journald, provisioning, shellcheck]

# Dependency graph
requires:
  - phase: 31-04
    provides: "deploy/render-prefs.sh (the every-boot prefs renderer) and its fixed ExecStart contract (/opt/mics/deploy/render-prefs.sh -> /opt/mics/pilot/prefs.json)"
  - phase: 31-03
    provides: "the measured requirements.txt with pigpio==1.78 pinned as the stock upstream client, and the 187-failed/253-passed pytest baseline"
provides:
  - "deploy/mics-pilot.service -- unattended, crash-loop-proof (StartLimitIntervalSec=0), RT-scheduled (CPUSchedulingPolicy=fifo, priority=10, hypothesis pending C4), User=pi, no hardening directives that would hide GPIO/I2C devices"
  - "deploy/mics-prefs.service -- every-boot prefs render, Before=mics-pilot.service"
  - "deploy/mics-firstboot-once.service + deploy/firstboot-once.sh -- stamp-guarded one-time hostname/hosts/SSH-keys/machine-id/filesystem-expansion/device-file provisioning"
  - "deploy/chrony-mics.conf -- lab NTP sources drop-in, restates none of Debian's stock step-then-slew policy"
  - "deploy/journald-mics.conf -- Storage=volatile with a size cap, so 24/7 operation writes nothing to the SD card"
  - "tests/test_unit_files.py (29 tests) + tests/test_firstboot_once.py (10 tests) -- permanent parsing/behaviour gates on every load-bearing directive and script behaviour"
affects: [31-07, 31-09, 31-C4]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Counted-absence regression guards for withdrawn designs: raw full-text substring counts (not comment-stripped) for banned tokens (pigpiod, LG_WD, lgpio, PrivateDevices/ProtectSystem/DevicePolicy/DynamicUser, makestep/driftfile), printed before asserting zero -- and unit-file comments are themselves written to avoid the literal banned substrings while still explaining the withdrawn design by paraphrase, so the explanatory comment and the counted guard do not fight each other"
    - "Unit-split provisioning: a stamp-guarded once-only unit (mics-firstboot-once.service, DefaultDependencies=no, sysinit.target) plus a separate every-boot unit (mics-prefs.service, multi-user.target) so a later mics.conf edit takes effect on the next boot, not never"
    - "--skip-destructive flag on firstboot-once.sh: the two genuinely destructive, non-fixturable steps (SSH host key regen, machine-id regen) plus filesystem expansion live behind one flag no production invocation ever passes, so the rest of the script is still subprocess-testable end-to-end against tmp_path fixtures"

key-files:
  created:
    - /home/ido/mics_core/deploy/mics-pilot.service
    - /home/ido/mics_core/deploy/mics-prefs.service
    - /home/ido/mics_core/deploy/mics-firstboot-once.service
    - /home/ido/mics_core/deploy/firstboot-once.sh
    - /home/ido/mics_core/deploy/chrony-mics.conf
    - /home/ido/mics_core/deploy/journald-mics.conf
    - /home/ido/mics_core/tests/test_unit_files.py
    - /home/ido/mics_core/tests/test_firstboot_once.py

key-decisions:
  - "PLAT-33 stays withdrawn (2026-08-17, user decision). No deploy/pigpiod-mics.conf, no pigpiod unit, and zero occurrences of the literal string 'pigpiod' anywhere in deploy/mics-pilot.service or any other deploy/*.service or *.conf -- enforced by a counted test, not a grep. The pilot still spawns its own daemon from prefs.json's PIGPIOARGS/PIGPIOMASK."
  - "The plan's own <objective> text (2026-08-17) supersedes its earlier framing: the daemon-launch helper's cleanup hook does NOT reliably kill the daemon under the current spawn (`sudo ... shell=True` with no `-g`, so the daemon forks away and outlives the shell object the hook holds). mics-pilot.service's KillSignal=SIGINT/TimeoutStopSec=20 comment says exactly this -- 'this rig currently has no output fail-safe, clean stop or not' -- rather than the stronger, now-false claim an earlier draft would have made. Recorded as UNVERIFIED under systemd specifically, handed to plan 09 Step 12."
  - "Comments explaining two withdrawn/superseded designs (the abandoned alternate-GPIO-library port, and PLAT-33) were written to paraphrase rather than name the banned literal tokens (lgpio/LG_WD, pigpiod), because Task 1/3's own counted-absence tests apply to raw file text, not comment-stripped text -- matching the plan's own verify block, which does the same raw count. The explanatory intent survives; the literal regression-guard tokens do not appear."
  - "test_unit_files.py's ConditionFirstBoot absence check was corrected from a total-text ban to an active-directive-line check (comment lines excluded): mics-firstboot-once.service's own header comment is required to name ConditionFirstBoot while explaining why it is not used, which a total-text ban would have made impossible to satisfy."
  - "ExecStart cross-file path checking (catches a plan-04 rename breaking a plan-05 unit) is scoped to units whose target already exists at each task's checkpoint: mics-prefs.service+mics-pilot.service in Task 1 (render-prefs.sh already existed from plan 04), extended to mics-firstboot-once.service in Task 2 once firstboot-once.sh landed -- so no task's own test suite is red against work assigned to a later task in the same plan."
  - "chrony-mics.conf ships with the lab NTP address commented out and a TODO naming plan 09, per the plan's own explicit escape hatch: no lab NTP server address is documented anywhere in the phase's planning corpus, and the plan forbids inventing one."
  - "firstboot-once.sh's --stamp flag writes the stamp itself (redundant with mics-firstboot-once.service's own ExecStartPost) -- the plan's own <behavior> section lists --stamp among the flags every destructive path must be overridable through, which only makes sense if the script itself manages that file."

requirements-completed: [PLAT-06, PLAT-07, PLAT-09, PLAT-10, PLAT-11, PLAT-20, PLAT-21]

# Metrics
duration: ~60min
completed: 2026-08-19
---

# Phase 31 Plan 05: Unattended-Boot systemd Units and Clock/Journal Drop-ins Summary

**Three systemd units (crash-loop-proof pilot service, every-boot prefs render, stamp-guarded once-only device provisioning) plus chrony/journald drop-ins turn `run_pilot.sh` into an unattended 24/7 rig, with PLAT-33 (a supervised pigpio daemon) staying withdrawn and its fail-safe premise recorded as verified false rather than restored as an oversight.**

## Performance

- **Duration:** ~60 min
- **Started:** 2026-08-19T07:55Z (continuing directly from plan 04)
- **Completed:** 2026-08-19T08:48Z
- **Tasks:** 3 completed
- **Files modified:** 8 (all new)

## Accomplishments

- **Task 1:** Wrote `tests/test_unit_files.py` (RED-verified against absent unit files: 10/13 tests failed for the expected reason), then the three MICS units. `mics-pilot.service` carries every directive `<verified_directives>` requires: `StartLimitIntervalSec=0` in `[Unit]` (the crash-loop-latch fix), `Restart=always`/`RestartSec=5`, `RuntimeDirectory=mics`/`WorkingDirectory=/run/mics` (the ordinary cwd reason, with a comment explaining the withdrawn alternate-GPIO-library design that used to need more here), `Environment=PYTHONNOUSERSITE=1`, `CPUSchedulingPolicy=fifo`/`CPUSchedulingPriority=10` (explicitly commented as an unmeasured hypothesis pending C4), `KillSignal=SIGINT`/`TimeoutStopSec=20`, `User=pi` with no dynamically-allocated-user directive, `After=network-online.target chrony-wait.service mics-prefs.service` without `Requires=chrony-wait.service` (PLAT-21 relaxed), `Requires=mics-prefs.service`, and `ExecStart=/home/pi/.venv/mics/bin/python -m autopilot.core.pilot -f /opt/mics/pilot/prefs.json` (matching `pilot/launch_autopilot.sh`'s existing module-invocation form, read from the repo rather than invented). `mics-prefs.service` and `mics-firstboot-once.service` match their `<behavior>` specs exactly (oneshot/RemainAfterExit=yes, `Before=mics-pilot.service`, stamp-guarded `ConditionPathExists=!/var/lib/mics/.firstboot-done`, no `ConditionFirstBoot`). A counted test enforces zero `pigpiod` occurrences in `mics-pilot.service` and zero `LG_WD`/`lgpio` occurrences across all of `deploy/` -- which required writing the unit comments themselves without those literal tokens, since the test reads raw file text, not comment-stripped text, matching the plan's own verify block precisely.
- **Task 2:** Wrote `deploy/firstboot-once.sh` (shellcheck 0.9.0 clean after one fix: an `A && B || C` construct flagged SC2015, rewritten as an explicit `if`). Hostname is always `mics-<serial8>` -- the LOW 8 hex digits of `/proc/cpuinfo`'s `Serial` line, proven by a test asserting two different high halves with the same low half produce the identical hostname. Rewrites both `/etc/hostname` and the `127.0.1.1` line in `/etc/hosts` (both the replace-existing-line and append-if-missing cases tested), writes `/boot/firmware/mics-device.txt` with MAC + serial, and is idempotent (a second run leaves all three files byte-identical, verified live via manual smoke test and then via `tests/test_firstboot_once.py`). The two genuinely destructive, non-fixturable steps (SSH host key regeneration, machine-id regeneration) plus filesystem expansion sit behind a `--skip-destructive` flag no production invocation passes -- every test uses it, and no test ever regenerates this machine's real SSH host keys or machine-id. `tests/test_firstboot_once.py` (new, 10 subprocess-driven tests) plus `tests/test_unit_files.py`'s cross-file ExecStart-path check extended to cover `mics-firstboot-once.service` now that its script exists.
- **Task 3:** Wrote `deploy/chrony-mics.conf` (a `/etc/chrony/conf.d/` drop-in) and `deploy/journald-mics.conf` (a `/etc/systemd/journald.conf.d/` drop-in). The chrony drop-in adds no NTP source (none is documented anywhere in the phase's planning corpus, and the plan forbids inventing one) -- shipped with a commented-out `server` line and a TODO naming plan 09, and its header comment explains Debian's stock step-then-slew policy and why `systemd-timesyncd` cannot express it, entirely by paraphrase (no literal `makestep`/`driftfile` substrings, matching the plan's own counted verify check). The journald drop-in sets `Storage=volatile`/`RuntimeMaxUse=64M`/`RuntimeMaxFileSize=8M`/`Compress=yes`, with a comment distinguishing it from the pilot's own log files (0 bytes by design, untouched). 8 new tests cover both files' presence, content, the `pigpiod`/`makestep`/`driftfile` absences, and that neither file mentions the pilot's own log keys (`LOGDIR`/`LOGSIZE`/`LOGNUM`/`pilot.log`).

Across all three tasks: `systemd-analyze verify` run locally on all three units shows only the expected off-target warnings (missing venv binary at `/home/pi/.venv/mics/bin/python`, missing `/opt/mics/deploy/render-prefs.sh` and `/opt/mics/deploy/firstboot-once.sh` -- none of which exist on this dev host, only on the eventual Pi at `/opt/mics`); no syntax or structural errors. `check_tree_integrity.py --strict` and `tools/pytest_delta.py` (0 new failures against the 187/253 baseline) held after every task.

### `systemd-analyze verify` output (local, off-target)

```
$ systemd-analyze verify ./deploy/mics-pilot.service ./deploy/mics-prefs.service ./deploy/mics-firstboot-once.service
mics-pilot.service: Command /home/pi/.venv/mics/bin/python is not executable: No such file or directory
mics-prefs.service: Command /opt/mics/deploy/render-prefs.sh is not executable: No such file or directory
mics-firstboot-once.service: Command /opt/mics/deploy/firstboot-once.sh is not executable: No such file or directory
```

All three are exactly the expected class of warning: paths that only exist once the venv is built (plan 07) and the repo is deployed to `/opt/mics` on the Pi (plan 07/09). No warning fired about `chrony-wait.service` being unresolvable, and no directive-syntax warnings fired at all. The authoritative run is plan 09's, on the Pi.

### `mics-pilot.service`, verbatim

```ini
[Unit]
Description=MICS pilot -- behavioral task runner (unattended, 24/7)

# systemd's default start-rate limit is 5 starts in 10s. Once tripped, the unit
# latches into `failed` PERMANENTLY and Restart=always stops meaning "always" -- the
# exact failure this phase exists to eliminate. Must live in [Unit], not [Service].
StartLimitIntervalSec=0

# After= without Requires=: a network-free rig still boots the pilot, just late.
# chrony-wait.service ships in Debian bookworm's chrony package (runs
# `chronyc waitsync 0 0.1 0.0 1`, caps at TimeoutStartSec=180).
# PLAT-21 is RELAXED (2026-08-17, see 31-05-PLAN.md): timestamps are now derived
# from a monotonic counter rather than an estimated tick->wall-clock mapping, so
# waiting for clock convergence is no longer required for correctness -- a
# late-converging clock no longer corrupts event timestamps or intervals. This
# ordering is kept because it is free and makes the first session's derived UTC
# fields sane from the start -- a convenience, not a safety property. Do not
# "harden" it into a Requires=.
After=network-online.target chrony-wait.service mics-prefs.service
Wants=network-online.target
Requires=mics-prefs.service

[Service]
Type=simple
User=pi
# No dynamically-allocated-user directive: raspberrypi-sys-mods' 99-com.rules
# grants SUBSYSTEM=="gpio" GROUP="gpio" MODE="0660" and SUBSYSTEM=="i2c-dev"
# GROUP="i2c" MODE="0660", so the running user must be a REAL, persistent member of
# both groups (PLAT-11) -- an ephemeral allocated user would not be.

# systemd's default working directory is `/`, which a long-lived service should not
# inherit. RuntimeDirectory=mics gives a tmpfs-backed, correctly owned,
# automatically cleaned directory to own instead. NOTE, so the next reader neither
# re-adds nor deletes these: an earlier design (the alternate-GPIO-library port,
# withdrawn 2026-08-17 -- see 31-REVISED-SCOPE.md Sec5) needed an extra environment
# variable here to redirect a relative-path notification socket file; that whole
# design is gone, and the current GPIO client (pigpio) has no such file. These two
# directives stay purely for the ordinary cwd reason above.
RuntimeDirectory=mics
RuntimeDirectoryMode=0755
WorkingDirectory=/run/mics

# Belt-and-braces (PLAT-06): the venv is built WITHOUT --system-site-packages
# (plan 07), but this stops a stray `pip install --user` from shadowing a pinned
# rig dependency.
Environment=PYTHONNOUSERSITE=1

ExecStart=/home/pi/.venv/mics/bin/python -m autopilot.core.pilot -f /opt/mics/pilot/prefs.json

# Crash-loop must recover forever, not latch into `failed` -- see StartLimitIntervalSec above.
Restart=always
RestartSec=5

# CPUSchedulingPriority=10, NOT 99. The justification is notification-drain
# headroom, not a software-timed transmit path (the alternate-GPIO-library design
# that would have needed that is gone -- PLAT-17 revised). The GPIO client's C
# counterpart samples the GPIO block by DMA every 5us and pushes notifications over
# a socket; this process's notify thread must drain that socket faster than the
# daemon fills it, or notifications back up and -- beyond the daemon's sample
# buffer (120ms default) -- samples are DROPPED, which PLAT-32 requires to be
# detected, not silently lost. A max-priority CPython process can make the box
# unreachable; the kernel RT throttle (sched_rt_runtime_us 950000/1000000) is the
# safety net.
#
# THIS IS A HYPOTHESIS, not yet measured: pending C4's `chrt -p` + dropped-
# notification-count soak. The measurement decides whether it stays. Note the GPIO
# daemon itself already runs its whole process at SCHED_FIFO max regardless of
# anything set here -- that is the daemon, not this client, and this unit does not
# change it.
CPUSchedulingPolicy=fifo
CPUSchedulingPriority=10

# No GPIO-daemon ordering, and no GPIO-daemon unit reference at all. PLAT-33 was
# WITHDRAWN 2026-08-17 (user decision, see 31-05-PLAN.md <objective>): the pilot
# still spawns its own daemon from prefs.json's PIGPIOARGS/PIGPIOMASK
# (autopilot/external/__init__.py), so there is no separate unit for this one to
# order against. An After=/Requires= on a unit that does not exist would keep the
# pilot from starting at all. Do not re-add it -- see 31-REVISED-SCOPE.md Sec5. A
# counted test (tests/test_unit_files.py) enforces this file names that daemon
# nowhere, including in comments -- which is also why this comment does not.
#
# Fail-safe note (verified 2026-08-17, see 31-05-PLAN.md <objective>): the daemon-
# launch helper's cleanup hook is registered on atexit and SIGTERM, so SIGINT
# reaches it via atexit during a CLEAN interpreter exit -- the fail-safe (such as it
# is) holds only if the pilot exits cleanly WITHIN TimeoutStopSec below. Past that,
# systemd escalates to SIGKILL and no handler runs at all. Separately, and this
# matters more: that cleanup hook was found NOT to reach the daemon process at all
# under the current spawn (a `sudo ... shell=True` launch with no `-g` flag lets the
# daemon fork away and outlive the shell object the hook actually holds a reference
# to) -- so THIS RIG CURRENTLY HAS NO OUTPUT FAIL-SAFE, clean stop or not. Fail-safe
# behaviour under systemd specifically is UNVERIFIED -- see plan 09 Step 12. The
# handler that drives outputs to a documented safe level on SIGINT is plan C3's work.
KillSignal=SIGINT
TimeoutStopSec=20

# Do NOT add unit hardening that isolates the device namespace or restricts device
# access (the kind of directive that hides /dev/gpiochip*, /dev/i2c-*): it would
# produce a unit that starts and does nothing. Do not copy chrony-wait.service's
# hardening block onto this unit.

[Install]
WantedBy=multi-user.target
```

### PLAT-33 withdrawal -- restated for the record

**PLAT-33 was withdrawn on 2026-08-17 by user decision.** No `pigpiod` unit or drop-in was written
by this plan (`deploy/pigpiod-mics.conf` does not exist; `mics-pilot.service` carries zero
occurrences of the literal string `pigpiod`, enforced by a counted test over every `deploy/*.service`
and `*.conf`). The reason is the daemon-launch cleanup hook the pilot already registers on
`atexit`/`SIGTERM` (`autopilot/external/__init__.py`) -- the user's stated intent in withdrawing
PLAT-33 was to preserve that hook as the rig's output fail-safe rather than replace it with an
independently supervised daemon unit.

**That premise is void, and this plan's comments say so rather than repeating it as fact.** The
hook's `subprocess.Popen('sudo ' + launch_pigpiod, shell=True)` call means the object the hook holds
is the shell process, not the daemon; the daemon's launch arguments carry no `-g` flag, so it
daemonises, forks away, and outlives the shell by the time the hook runs. The daemon also runs as
root (via `sudo`), so a `User=pi` pilot process could not signal it even with the correct PID. **The
daemon already outlives the pilot today, under `run_pilot.sh`, with no unit involved at all.**
Neither the current design nor a hypothetical supervised unit is a fail-safe; building one is
separate, unscheduled work. This unit's `KillSignal=SIGINT`/`TimeoutStopSec=20` comment states this
plainly rather than implying a guarantee that does not exist.

**One question handed to plan 09:** whether the pilot's own `sudo pigpiod ...` spawn behaves the same
under systemd as it does under `run_pilot.sh` -- it now runs as a service-owned child (spawned from
inside `mics-pilot.service`'s cgroup) rather than a login-shell child, which could change how it is
reaped, how `sudo` behaves without a TTY, or how the daemon's lifetime interacts with the unit's own
`TimeoutStopSec=20`/`KillMode=` (left at systemd's default, `control-group`, which is the correct
choice for a `Type=simple` unit whose child spawns further children).

## Task Commits

Each task committed as TDD pairs:

1. **Task 1: the three MICS units** -- TDD: `5d7f8a4` (test, RED-verified: 10/13 fail against absent unit files) -> `cf1a022` (feat, GREEN; also fixed the test's own `ConditionFirstBoot` absence check to look at active directive lines rather than raw text)
2. **Task 2: firstboot-once.sh** -- `31eed5a` (feat + tests together; script validated by manual subprocess smoke test before the pytest suite was written, then 10/10 green on first pytest run)
3. **Task 3: chrony/journald drop-ins** -- `1e4d928` (feat + 8 new tests, green on first run)

All four commits are in `~/mics_core` on `phase-31-modern-pi-platform`.

## Files Created/Modified

- `/home/ido/mics_core/deploy/mics-pilot.service` -- new, the unattended pilot unit (verbatim above)
- `/home/ido/mics_core/deploy/mics-prefs.service` -- new, every-boot prefs render, `Before=mics-pilot.service`
- `/home/ido/mics_core/deploy/mics-firstboot-once.service` -- new, stamp-guarded oneshot provisioning
- `/home/ido/mics_core/deploy/firstboot-once.sh` -- new, shellcheck-clean (135 lines), hostname/hosts/SSH-keys/machine-id/filesystem-expand/device-file/avahi, `--skip-destructive` for testability
- `/home/ido/mics_core/deploy/chrony-mics.conf` -- new, `/etc/chrony/conf.d/` drop-in, lab NTP source deferred to plan 09
- `/home/ido/mics_core/deploy/journald-mics.conf` -- new, `/etc/systemd/journald.conf.d/` drop-in, `Storage=volatile`
- `/home/ido/mics_core/tests/test_unit_files.py` -- new, 29 tests across all three units, both drop-ins, and the cross-file ExecStart-path check
- `/home/ido/mics_core/tests/test_firstboot_once.py` -- new, 10 subprocess-driven tests

## Decisions Made

See `key-decisions` in the frontmatter. In short: PLAT-33 stays withdrawn with its premise corrected
in the unit comment rather than repeated; the counted-absence tests for withdrawn designs (`pigpiod`,
`LG_WD`/`lgpio`, `makestep`/`driftfile`, the hardening-directive names) all read raw file text, which
meant writing every explanatory comment about those withdrawn designs by paraphrase rather than by
naming the literal banned token -- caught once by my own test failing on `DynamicUser` appearing
inside an explanatory comment, and once on `ConditionFirstBoot`, both fixed before the task's commit.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug in my own first draft] `DynamicUser` appeared inside an explanatory comment**
- **Found during:** Task 1, running the absence-of-hardening-directives test against my own first
  draft of `mics-pilot.service`
- **Issue:** The comment explaining why no dynamically-allocated user is used wrote the literal
  directive name `DynamicUser`, which is exactly the substring the counted absence test (and the
  plan's own verification item 4) bans.
- **Fix:** Reworded to "no dynamically-allocated-user directive" / "an ephemeral allocated user"
  -- same explanation, no banned literal.
- **Files modified:** `deploy/mics-pilot.service`
- **Verification:** `grep -o DynamicUser deploy/mics-pilot.service | wc -l` -> 0
- **Committed in:** `cf1a022`

**2. [Rule 1 - Bug in my own test] `test_does_not_use_condition_first_boot` was too strict**
- **Found during:** Task 1, running the full suite after writing `mics-firstboot-once.service`'s
  header comment (which the plan's own `<action>` text requires to explain why `ConditionFirstBoot`
  is not used -- necessarily naming it)
- **Issue:** My first version of the test banned the literal string `ConditionFirstBoot` anywhere in
  the raw file text, which made it impossible to satisfy the plan's own instruction to explain the
  choice in a comment.
- **Fix:** Changed the check to look only at active directive lines (comment lines excluded), so the
  explanatory comment can name `ConditionFirstBoot` while the actual `[Unit]`/`[Service]` directives
  never use it as a key.
- **Files modified:** `tests/test_unit_files.py`
- **Verification:** Full suite green afterward; the header comment still names `ConditionFirstBoot`
  in `deploy/mics-firstboot-once.service`.
- **Committed in:** `cf1a022`

**3. [Rule 3 - Blocking] shellcheck SC2015 on `firstboot-once.sh`'s avahi restart**
- **Found during:** Task 2, `shellcheck deploy/firstboot-once.sh`
- **Issue:** `command -v systemctl >/dev/null 2>&1 && systemctl restart avahi-daemon || true` is not
  if-then-else; the `|| true` can also fire if the `&&` chain's first command fails, silently
  masking a real problem.
- **Fix:** Rewrote as an explicit `if command -v systemctl >/dev/null 2>&1; then systemctl restart
  avahi-daemon || true; fi`.
- **Files modified:** `deploy/firstboot-once.sh`
- **Verification:** `shellcheck deploy/firstboot-once.sh` -> clean
- **Committed in:** `31eed5a`

---

**Total deviations:** 3 auto-fixed (2 Rule 1 self-corrections caught by my own tests before the task
commit, 1 Rule 3 shellcheck fix). None required a scope change; all three are exactly the kind of
mistake the plan's own counted-absence-test design and `shellcheck` gate exist to catch.

## Issues Encountered

None beyond the three self-caught items above. The dev host is not a Pi, so `/proc/cpuinfo` has no
`Serial` line and `raspi-config`/real SSH-host-key regeneration/`systemd-machine-id-setup` were never
exercised for real -- exactly why `--skip-destructive` and full path-overridability exist. A manual
smoke test (real bash invocation against `tmp_path`-equivalent fixtures, run before the pytest suite
was written) confirmed the script's core logic (hostname derivation, `/etc/hosts` rewrite, device
file, idempotence) before formalizing it as tests; this is a lighter-weight process than Task 1's
strict RED-then-GREEN pytest cycle, noted for transparency rather than hidden.

## User Setup Required

None -- this plan writes files only. Nothing is installed, enabled or started on any machine here;
plan 07 installs the units, plan 09 proves them on real hardware.

## Next Phase Readiness

- Plan 07 can install all six `deploy/` files verbatim: three units to their systemd unit
  directories, `chrony-mics.conf` to `/etc/chrony/conf.d/`, `journald-mics.conf` to
  `/etc/systemd/journald.conf.d/`, `firstboot-once.sh`/`render-prefs.sh` to `/opt/mics/deploy/`
  (already there from plan 04) -- then `systemctl enable mics-firstboot-once.service
  mics-prefs.service mics-pilot.service`.
- Plan 09's rig checkpoint inherits three concrete, previously-undocumented facts to verify on real
  hardware: (a) the lab NTP server address, currently a TODO in `chrony-mics.conf`; (b) whether the
  pilot's `sudo pigpiod` spawn behaves the same as a systemd service-owned child as it does under
  `run_pilot.sh`; (c) `systemd-analyze verify`'s real (non-off-target) output once the venv and
  `/opt/mics` deployment exist.
- Plan C4's acceptance soak has two concrete measurements this plan flags as unverified rather than
  assumed: `CPUSchedulingPriority=10`'s notification-drain-headroom hypothesis (via `chrt -p` and a
  dropped-notification count), and the rig's output fail-safe behaviour under `SIGKILL`/OOM (this
  plan's `KillSignal=SIGINT`/`TimeoutStopSec=20` comment states plainly that no fail-safe currently
  exists, clean stop or not, superseding the earlier PLAT-33-withdrawal premise).
- `requirements mark-complete PLAT-06 PLAT-07 PLAT-09 PLAT-10 PLAT-11 PLAT-20 PLAT-21` found no
  checkbox/traceability row in `REQUIREMENTS.md` (same structural gap as every prior Phase 31 plan)
  -- completion tracked here and via `gsd-tools roadmap update-plan-progress 31` instead.
- `state advance-plan` and `state record-metric`/`record-session` still error on this file (same
  known gap as plans 01-04/06); `state update-progress` and `add-decision` both worked and were used.

---
*Phase: 31-mics-core-modern-pi-platform-bookworm-64-bit-python-3-11-lgpio-unattended-boot*
*Completed: 2026-08-19*

## Self-Check: PASSED

All 8 created files verified present on disk in `~/mics_core`
(`deploy/mics-pilot.service`, `deploy/mics-prefs.service`,
`deploy/mics-firstboot-once.service`, `deploy/firstboot-once.sh`,
`deploy/chrony-mics.conf`, `deploy/journald-mics.conf`,
`tests/test_unit_files.py`, `tests/test_firstboot_once.py`). All 4 commit hashes
verified present via `git log --oneline --all` in `~/mics_core` (`5d7f8a4`,
`cf1a022`, `31eed5a`, `1e4d928`). This SUMMARY.md itself confirmed present in
`mics-backend`.
