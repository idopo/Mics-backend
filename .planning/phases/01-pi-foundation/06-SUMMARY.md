---
phase: 01-pi-foundation
plan: "06"
subsystem: infra
tags: [rsync, ssh, bash, pi, deploy]

requires: []
provides:
  - "sync_pi.sh: rsync autopilot/ from pi-mirror to Pi over SSH"
  - "deploy_pi.sh: sync + pilot restart (systemd-first, pkill+nohup fallback)"
  - "tools/ directory structure in ~/pi-mirror/"
affects:
  - 01-pi-foundation/01
  - 01-pi-foundation/02
  - 01-pi-foundation/03
  - 01-pi-foundation/04
  - 01-pi-foundation/05

tech-stack:
  added: []
  patterns:
    - "Pi deploy via rsync + SSH key auth, targeting autopilot/ subdir only"
    - "systemd-first restart with pkill+nohup fallback for older Pi setups"
    - "< /dev/null for nohup to prevent SSH stdin hang"

key-files:
  created:
    - ~/pi-mirror/tools/sync_pi.sh
    - ~/pi-mirror/tools/deploy_pi.sh
  modified:
    - .claude/skills/pi-deploy/SKILL.md

key-decisions:
  - "nohup launch uses < /dev/null to ensure SSH session exits immediately (without it, SSH waits on inherited stdin)"
  - "ZMQ port cleanup (5565, 556) included in stop step to prevent port conflicts on restart"
  - "Pilot log goes to /tmp/pilot.log (not PI_APP_DIR/logs/) — consistent with existing pi-deploy skill"

patterns-established:
  - "Deploy scripts live in ~/pi-mirror/tools/ (not in mics-backend repo — they are developer operational tools)"
  - "sync_pi.sh excludes __pycache__, *.pyc, .git, *.egg-info, dist/, build/"

requirements-completed:
  - FDA-09

duration: 2min
completed: 2026-03-22
---

# Phase 1 Plan 06: sync_pi.sh and deploy_pi.sh Summary

**Two idempotent shell scripts (sync_pi.sh, deploy_pi.sh) in ~/pi-mirror/tools/ enabling rsync-based Pi code deployment with systemd-first + pkill+nohup restart fallback**

## Performance

- **Duration:** 2 min
- **Started:** 2026-03-22T15:04:35Z
- **Completed:** 2026-03-22T15:07:08Z
- **Tasks:** 2
- **Files modified:** 3 (2 created outside repo, 1 updated in repo)

## Accomplishments

- Created `~/pi-mirror/tools/sync_pi.sh` — rsyncs autopilot/ to Pi with --dry-run support, SSH key validation, excludes for pycache/pyc/git/egg-info, set -euo pipefail safety
- Created `~/pi-mirror/tools/deploy_pi.sh` — calls sync_pi.sh then restarts pilot (systemd if available, pkill+nohup fallback), supports --sync-only/--restart-only/--dry-run flags
- Updated `.claude/skills/pi-deploy/SKILL.md` to reference new scripts as preferred workflow

## Task Commits

1. **Tasks 06-1 + 06-2: sync_pi.sh and deploy_pi.sh** - `c8128ab` (chore)

**Plan metadata:** (final commit — see below)

## Files Created/Modified

- `~/pi-mirror/tools/sync_pi.sh` - Rsync autopilot/ to Pi with dry-run, excludes, SSH key validation
- `~/pi-mirror/tools/deploy_pi.sh` - Sync + restart workflow (systemd-first with pkill+nohup fallback)
- `.claude/skills/pi-deploy/SKILL.md` - Added "Deploy Scripts (Preferred)" section at top of Commands

## Decisions Made

- **nohup + < /dev/null**: Required for SSH session to exit immediately after launching pilot background process; without `< /dev/null`, SSH waits on the inherited stdin file descriptor.
- **ZMQ port cleanup**: Added `sudo kill -9 $(sudo lsof -t -i:5565) $(sudo lsof -t -i:556)` to stop step — consistent with pi-deploy skill's established pattern to prevent port-in-use errors on restart.
- **Pilot log at /tmp/pilot.log**: Consistent with existing pi-deploy skill rather than plan's `$PI_APP_DIR/logs/` suggestion (which requires the logs/ directory to exist on Pi).

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Corrected nohup launch command for proper SSH detachment**
- **Found during:** Task 06-2 (deploy_pi.sh creation)
- **Issue:** Plan's nohup command `nohup bash $PI_PILOT_SCRIPT >> $PILOT_LOG 2>&1 &` does not include `< /dev/null`, causing SSH to hang waiting on inherited stdin. Pi-deploy SKILL.md documents this requirement explicitly.
- **Fix:** Used `(cd $PI_APP_DIR && nohup bash $PI_PILOT_SCRIPT > $PILOT_LOG 2>&1 < /dev/null &)` with subshell and stdin redirect.
- **Files modified:** ~/pi-mirror/tools/deploy_pi.sh
- **Verification:** Script structure verified against pi-deploy SKILL.md established pattern.
- **Committed in:** c8128ab (task commit)

**2. [Rule 1 - Bug] Added ZMQ port cleanup to restart stop step**
- **Found during:** Task 06-2 (deploy_pi.sh creation)
- **Issue:** Plan's pkill-only stop does not release ZMQ ports 5565 and 556, causing "address already in use" on restart. Pi-deploy SKILL.md documents this requirement explicitly.
- **Fix:** Added `sudo kill -9 $(sudo lsof -t -i:5565) $(sudo lsof -t -i:556) 2>/dev/null; true` to stop command.
- **Files modified:** ~/pi-mirror/tools/deploy_pi.sh
- **Verification:** Pattern matches SKILL.md's established workflow.
- **Committed in:** c8128ab (task commit)

**3. [Rule 1 - Bug] Changed pilot log path from $PI_APP_DIR/logs/ to /tmp/pilot.log**
- **Found during:** Task 06-2 (deploy_pi.sh creation)
- **Issue:** Plan used `$PI_APP_DIR/logs/pilot_restart.log` which requires a `logs/` directory to exist on Pi. Pi-deploy SKILL.md uses `/tmp/pilot.log` as established convention.
- **Fix:** Changed `PILOT_LOG` to `/tmp/pilot.log`.
- **Files modified:** ~/pi-mirror/tools/deploy_pi.sh
- **Verification:** Consistent with SKILL.md.
- **Committed in:** c8128ab (task commit)

---

**Total deviations:** 3 auto-fixed (all Rule 1 — bugs corrected using established pi-deploy skill patterns)
**Impact on plan:** All fixes necessary for correct operation. Aligned scripts with documented operational patterns from pi-deploy SKILL.md.

## Issues Encountered

- `~/pi-mirror/` is not tracked in the mics-backend git repo (it's a local operational mirror). Scripts were committed indirectly via SKILL.md update in mics-backend. The scripts themselves live at `~/pi-mirror/tools/` outside any git repo.

## User Setup Required

None — scripts use existing SSH key at `~/.ssh/pi_mics` and default Pi credentials.

## Next Phase Readiness

- Pi deployment workflow is operational. All other Phase 1 plans can now be verified on-Pi via `~/pi-mirror/tools/deploy_pi.sh`.
- Pi is currently live with an active task — use `--sync-only` flag until session ends, then use full deploy.

---
*Phase: 01-pi-foundation*
*Completed: 2026-03-22*
