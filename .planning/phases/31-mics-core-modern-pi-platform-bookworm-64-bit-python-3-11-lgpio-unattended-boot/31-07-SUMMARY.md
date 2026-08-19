---
phase: 31-mics-core-modern-pi-platform-bookworm-64-bit-python-3-11-lgpio-unattended-boot
plan: 07
subsystem: platform
tags: [provisioning, bash, shellcheck, systemd, pigpio, bookworm]

# Dependency graph
requires:
  - phase: 31-04
    provides: "deploy/render-prefs.sh, pilot/prefs.template.json, /boot/firmware/mics.conf contract"
  - phase: 31-05
    provides: "the three MICS systemd units + chrony/journald drop-ins this installer installs and enables"
provides:
  - "deploy/install.sh -- the single idempotent provisioner: preflight, apt packages, I2C, boot config, venv, units, drop-ins, groups, mics.conf seed"
  - "deploy/uninstall.sh -- reverses install.sh: stops/disables the same unit set, removes drop-ins, restores .mics.bak files"
  - "tests/test_installer_paths.py -- 27 static tests: installer_contract paths, pigpio disposition (counted absences), cross-file artifact/unit-set checks, bash -n/shellcheck subprocess gates"
  - "README.md '## Deploying to a Pi' section"
  - "pilot/prefs.template.json re-pointed at /opt/mics + /home/pi/.venv/mics (was still /home/pi/Apps/mice_interactive_home_cage + /home/pi/.venv/autopilot from plan 04)"
affects: [31-09, 31-C4]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Counted-absence regression guards printed before asserting zero, applied a third time to pigpio (apt-installed daemon, never purged, never python3-pigpio, never a managed unit) -- this phase has stated the opposite twice already (31-REVISED-SCOPE.md Sec3, Sec5), and a silent grep is the likeliest way to repeat it"
    - "Explanatory comments about a withdrawn/banned design written to paraphrase rather than name the literal banned substring, because the counted-absence tests read raw file text including comments -- same discipline plan 05 established, caught twice here (--system-site-packages inside a comment, 'purged'/'python3-pigpio' inside comments) before either task's commit"
    - "Cross-file set-equality: install.sh and uninstall.sh each carry a literal UNITS=(...) bash array; the test regex-extracts both and asserts set equality, so adding a unit to one script and not the other fails the build rather than drifting silently"

key-files:
  created:
    - /home/ido/mics_core/deploy/install.sh
    - /home/ido/mics_core/deploy/uninstall.sh
    - /home/ido/mics_core/tests/test_installer_paths.py
  modified:
    - /home/ido/mics_core/pilot/prefs.template.json
    - /home/ido/mics_core/README.md

key-decisions:
  - "/opt/mics is a SYMLINK to the researcher's own clone, not a copy -- keeps `git pull` in the clone working as the deployed tree with no second sync step to forget, at the cost of the deployed tree only existing while the clone does (acceptable for a dedicated rig Pi)."
  - "pilot/prefs.template.json's REPODIR/BASEDIR/VENV and eight other path-valued keys were still /home/pi/Apps/mice_interactive_home_cage + /home/pi/.venv/autopilot (plan 04's values, predating this plan's /opt/mics + /home/pi/.venv/mics contract) -- re-pointed all 11 keys so the template and the installer agree, per the plan's own explicit instruction not to let them disagree. README's 'First boot' paragraph, which quoted the old paths as an example, was corrected in the same commit for the same reason."
  - "pigpio disposition (stated once, precisely, in install.sh's own apt-install comment because this phase has said the opposite twice before): the DAEMON package is apt-installed (external/__init__.py's shutil.which('pigpiod') gates the pilot's own spawn -- a hard runtime dependency, not tidiness); nothing pigpio-related is ever removed outright; the apt Python binding is deliberately not installed; no drop-in and no systemctl enable for any pigpio-named unit (PLAT-33 stays withdrawn). install.sh also records `pigpiod -v` and flags a shadowing /usr/local/bin/pigpiod rather than silently running whichever binary PATH resolves first."
  - "Testing methodology is entirely static (raw-text assertions + bash -n + shellcheck subprocess calls), matching both tasks' own <verify> blocks exactly -- no dynamic/subprocess run of install.sh or uninstall.sh against a sandboxed root, since install.sh's preflight hard-fails on this non-aarch64/non-bookworm dev host by design and a live run would touch the real system (apt, systemctl, usermod). 'Idempotent, exits 0 on a machine where nothing was installed' is therefore a design property proven by every mutating step being presence-guarded (readable in the diff), not by a live invocation -- real dynamic idempotence is plan 09's rig checkpoint."
  - "uninstall.sh restores *.mics.bak files by globbing /boot/firmware and /etc rather than a hardcoded per-file list, so a future install.sh backup site is reversed automatically without a matching edit to uninstall.sh."

requirements-completed: [PLAT-04, PLAT-05]

# Metrics
duration: ~45min
completed: 2026-08-19
---

# Phase 31 Plan 07: The MICS Rig Installer (install.sh / uninstall.sh) Summary

**One idempotent, shellcheck-clean `install.sh` that owns a stock Bookworm 64-bit Lite card end to end -- symlinks the clone to `/opt/mics`, apt-installs the pigpio daemon (never the client, never purged, never a managed unit), enables the three plan-05 systemd units, and seeds `/boot/firmware/mics.conf` -- reversed by `deploy/uninstall.sh`, with the prefs template's install-path assumption corrected to match.**

## Performance

- **Duration:** ~45 min
- **Started:** 2026-08-19T09:10Z (continuing directly from plan 05/C1/C2)
- **Completed:** 2026-08-19T09:55Z
- **Tasks:** 2 completed
- **Files modified:** 5 (3 new, 2 modified)

## Accomplishments

- **Task 1:** Wrote `tests/test_installer_paths.py` (27 tests, RED-verified: both scripts and the README section absent, failing for the expected reason), then `deploy/install.sh` (270 lines): `require_bookworm64` (aarch64 / `VERSION_CODENAME=bookworm` / `python3.11.x`, fails loudly and names what it found otherwise), `deploy_repo` (symlinks `/opt/mics` to the clone), `install_apt_packages` (`python3-venv python3-dev i2c-tools chrony pigpio` + `stress-ng` for the acceptance soak, records `pigpiod -v` and flags a shadowing `/usr/local/bin/pigpiod`), `enable_i2c` (`raspi-config nonint do_i2c 0`, backs up `config.txt`/`/etc/modules` first), `configure_boot` (idempotent `dtparam=audio=on`/`dtoverlay=disable-bt`/`enable_uart=0` upserts), `create_venv` (`/home/pi/.venv/mics`, no inherited system site-packages, no PEP-668 override flag, `chown`'d to `pi`), `install_units`/`install_dropins` (the three MICS units + chrony/journald drop-ins, `systemctl enable` for exactly the three units and nothing else), `add_groups` (`pi` into `i2c gpio spi dialout`), `seed_mics_conf` (copies `mics.conf.example` only if absent, never overwrites), `summary` (prints the four post-boot checks and the pigpiod-is-not-a-managed-service note). Every file it edits is backed up to `<file>.mics.bak` before the first edit only. Does not reboot.
- **Task 2:** Wrote `deploy/uninstall.sh` (101 lines): stops/disables exactly the `UNITS` array `install.sh` enables (asserted set-equal by a cross-file test), removes the three unit files and the two drop-ins, restores every `*.mics.bak` found under `/boot/firmware` and `/etc` by glob (not a hardcoded list), and never mentions `/boot/firmware/mics.conf` or `/opt/mics` anywhere in its text -- asserted directly rather than merely "not deleted". README got a `## Deploying to a Pi` section opening with the required "owns the box" sentence, the four-step flow, the four post-boot checks, and the pigpio daemon-vs-client disposition. `tests/test_installer_paths.py` extended with the uninstall-side assertions in the same file written in Task 1.

Both scripts are `bash -n` clean and `shellcheck 0.9.0` clean with zero warnings. `check_tree_integrity.py --strict` (39 closure members, 30 protected files, 1 known-dangling exemption, 0 violations) and `tools/pytest_delta.py` (`new failures: 0`) held after every commit. The plan's own five-item `<verification>` block (shellcheck, pytest, the two `grep -c` decoy-path checks, the standalone pigpio-purge/python3-pigpio/enable-pigpiod script, `--strict`) was re-run verbatim after the final commit and is green.

## Task Commits

1. **Test (covers both tasks):** `507a2b7` (test, RED-verified: both scripts and the README section absent)
2. **Task 1: install.sh** -- `832633f` (feat, GREEN for install.sh's own assertions; also fixed `pilot/prefs.template.json`)
3. **Task 2: uninstall.sh + README** -- `183a5df` (feat, GREEN for the full 27-test suite)

All three commits are in `~/mics_core` on `phase-31-modern-pi-platform`.

## Files Created/Modified

- `/home/ido/mics_core/deploy/install.sh` -- new, 270 lines, the idempotent provisioner
- `/home/ido/mics_core/deploy/uninstall.sh` -- new, 101 lines, reverses it
- `/home/ido/mics_core/tests/test_installer_paths.py` -- new, 236 lines, 27 tests
- `/home/ido/mics_core/pilot/prefs.template.json` -- 11 path-valued keys re-pointed at `/opt/mics`/`/home/pi/.venv/mics`
- `/home/ido/mics_core/README.md` -- new `## Deploying to a Pi` section; corrected the pre-existing "First boot" paragraph's example paths

## Decisions Made

See `key-decisions` in the frontmatter. In short: `/opt/mics` is a symlink to the clone (not a copy), so `git pull` keeps working as the deployed tree; the prefs template's install-path assumption (predating this plan) was corrected to match the installer's own contract rather than left to silently disagree; pigpio's disposition is stated once precisely in the one place that matters (`install.sh`'s own comment) because this phase has stated the opposite twice before; and the test suite is entirely static, matching both tasks' `<verify>` blocks exactly rather than attempting a live sandboxed run that the preflight check would refuse on this dev host anyway.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug in prior plan's own output] `pilot/prefs.template.json` still held pre-installer paths**
- **Found during:** Task 1, following the plan's own `<verified_installer_facts>` instruction to check the template against this plan's `/opt/mics`/`/home/pi/.venv/mics` contract
- **Issue:** Plan 04 shipped the template with `REPODIR=/home/pi/Apps/mice_interactive_home_cage`, `VENV=/home/pi/.venv/autopilot`, and eight other path-valued keys (`BASEDIR`, `CALIBRATIONDIR`, `DATADIR`, `LOGDIR`, `PLUGINDIR`, `PLUGIN_DB`, `PROTOCOLDIR`, `SOUNDDIR`, `VIZDIR`) all still under the old manual-install layout, predating this plan's installer contract.
- **Fix:** Re-pointed all 11 keys at the installer's actual paths via a small `json.load`/`json.dumps(indent=4)` round-trip (verified diff is values-only), and corrected README's "First boot" paragraph, which quoted the old paths as a worked example, in the same commit.
- **Files modified:** `pilot/prefs.template.json`, `README.md`
- **Verification:** `grep` for `/opt/mics`/`/home/pi/.venv/mics` in the template shows all 11 keys; `f2_prefs` (the tree-integrity guard's own prefs check) still passes -- it asserts absence of `132.77.*`/`SUBJECT`/`PORT_CALIBRATION`/`HARDWARE.UNREAL`, none of which this edit touched
- **Committed in:** `832633f`

**2. [Rule 1 - Bug in my own first draft] Explanatory comments named the literal banned substrings they were explaining the absence of**
- **Found during:** Task 1, running `tests/test_installer_paths.py` against my own first draft of `install.sh`
- **Issue:** Three comments explaining withdrawn/forbidden choices used the exact substrings the counted-absence tests ban: `--system-site-packages` and `--break-system-packages` inside prose explaining why neither flag is passed, and `purged`/`python3-pigpio` inside prose explaining that pigpio is never removed outright and its apt Python binding is never installed. The tests read raw file text, comments included -- matching plan 05's own precedent for this exact class of mistake.
- **Fix:** Reworded all three comments to paraphrase rather than name the literal tokens (e.g. "no inherited system site-packages", "the apt-packaged Python binding for this library", "never removed outright" instead of "never purged"), same explanation, no banned literal.
- **Files modified:** `deploy/install.sh`
- **Verification:** `pytest tests/test_installer_paths.py` full suite green afterward; `grep` for each literal substring in `install.sh` returns zero
- **Committed in:** `832633f`

**3. [Rule 1 - Bug in my own first draft] `uninstall.sh`'s own header comment and closing message named the two paths it must never touch**
- **Found during:** Task 2, running the extended test suite against my own first draft of `uninstall.sh`
- **Issue:** The header comment and the final summary line both explained "does not remove `/boot/firmware/mics.conf` or `/opt/mics`" by naming those two literal paths -- exactly the substrings `test_never_removes_mics_conf_or_opt_mics` bans, for the same reason as deviation 2.
- **Fix:** Reworded to "the boot-partition device config" / "the deployed repo location" -- same explanation, no literal path.
- **Files modified:** `deploy/uninstall.sh`
- **Verification:** Full suite green afterward
- **Committed in:** `183a5df`

---

**Total deviations:** 3 auto-fixed (1 correction to a prior plan's shipped output, 2 self-caught comment-wording issues, all caught by my own tests before either task's commit).
**Impact on plan:** No scope creep beyond the plan's own declared scope. Deviation 1 is exactly what the plan's own `<verified_installer_facts>` instructed ("fix the template here and say so -- do not let the installer and the prefs disagree"); deviations 2/3 are the same discipline plan 05 already established for withdrawn-design comments, applied here for the first time to pigpio's own disposition.

## Issues Encountered

None beyond the three self-caught items above. `bash -n`/`shellcheck 0.9.0` were clean on the first pass after each fix; no environment surprises.

## User Setup Required

None -- this plan writes files only. Nothing is installed, enabled, or started on any machine here; `install.sh`'s own preflight check refuses to run on this non-aarch64/non-bookworm dev host by design. Plan 09 is where a real Pi runs it.

## Next Phase Readiness

- Plan 09's rig checkpoint can run `sudo deploy/install.sh` on a fresh Bookworm 64-bit Lite card and get a provisioned rig end to end; `sudo deploy/uninstall.sh` reverses it.
- Plan 09 inherits three concrete open items from this plan to observe on real hardware, all previously unverifiable off-Pi: (a) whether the `pigpio` apt package leaves `pigpiod.service` enabled on its own (install.sh does not disable it if so -- the plan explicitly forbids pre-emptive action here); (b) the real `pigpiod -v` version string against the rig's current v78 source build, and whether `/usr/local/bin/pigpiod` is present and shadowing; (c) genuine two-run idempotence (`install.sh` run twice, exit 0, no diff) -- proven here only by static code-shape guarantees (every mutating step is presence-guarded), not a live invocation.
- `requirements mark-complete PLAT-04 PLAT-05` found no checkbox/traceability row in `REQUIREMENTS.md` (same structural gap as every prior Phase 31 plan) -- completion tracked here and via `gsd-tools roadmap update-plan-progress 31` instead.
- `state advance-plan`, `state record-metric` and `state record-session` remain no-ops on this STATE.md structure (same known gap as every prior Phase 31 plan); `state update-progress` and `add-decision` both worked and were used.
- Executed concurrently with plan 31-C3 in the same repo/branch; C3's own files (`autopilot/autopilot/core/pilot.py`, `tests/test_stock_pigpio_only.py`, and others per the parallel-execution notice) were left untouched and unstaged throughout -- confirmed via `git diff --stat` immediately before each commit.

---
*Phase: 31-mics-core-modern-pi-platform-bookworm-64-bit-python-3-11-lgpio-unattended-boot*
*Completed: 2026-08-19*

## Self-Check: PASSED

All 5 created/modified files verified present on disk in `~/mics_core`
(`deploy/install.sh`, `deploy/uninstall.sh`, `tests/test_installer_paths.py`,
`pilot/prefs.template.json`, `README.md`). All 3 commit hashes verified present
via `git log --oneline --all` in `~/mics_core` (`507a2b7`, `832633f`, `183a5df`).
This SUMMARY.md itself confirmed present in `mics-backend`.
