---
phase: 01-pi-foundation
plan: 06
type: execute
wave: 1
title: "sync_pi.sh and deploy_pi.sh scripts"
depends_on: []
files_modified: []
files_created:
  - ~/pi-mirror/tools/sync_pi.sh
  - ~/pi-mirror/tools/deploy_pi.sh
autonomous: true
requirements:
  - FDA-09
must_haves:
  truths:
    - "sync_pi.sh rsyncs autopilot/ to Pi and exits 0 on success"
    - "deploy_pi.sh calls sync_pi.sh then restarts pilot process and exits 0"
  artifacts:
    - path: "~/pi-mirror/tools/sync_pi.sh"
      contains: "rsync"
    - path: "~/pi-mirror/tools/deploy_pi.sh"
      contains: "sync_pi.sh"
---

# Plan 06: sync_pi.sh and deploy_pi.sh

## Goal

Create two shell scripts in `~/pi-mirror/tools/`: `sync_pi.sh` to rsync the autopilot codebase to the Pi, and `deploy_pi.sh` to sync and then restart the pilot process.

## Context

Pi code lives in `~/pi-mirror/` (a local rsync mirror of `pi@132.77.72.28:~/Apps/mice_interactive_home_cage/`). Changes made to files in `~/pi-mirror/` are pushed to the Pi via rsync. The SSH key is at `~/.ssh/pi_mics`.

After rsync, the pilot process (`pilot.py`) must be restarted to pick up the new code. The restart command depends on how the process is managed on the Pi — a `pkill`+restart approach is used since the Pi may not have systemd managing the pilot process (the repo shows a `run_pilot.sh` script at the root of the mirror, suggesting manual launch).

The tools must be idempotent and produce useful output on success and failure. They should print what they are doing (rsync progress) and confirm the pilot restarted.

### Key paths

- Local mirror root: `~/pi-mirror/`
- Pi user/host: `pi@132.77.72.28`
- SSH key: `~/.ssh/pi_mics`
- Pi app directory: `~/Apps/mice_interactive_home_cage/`
- Pi pilot script: `~/Apps/mice_interactive_home_cage/run_pilot.sh`
- rsync source: `~/pi-mirror/autopilot/` (just the autopilot package — not the full mirror)
- rsync destination: `pi@132.77.72.28:~/Apps/mice_interactive_home_cage/autopilot/`

Note: The `validate_fda.py` tool and other `tools/` scripts are NOT synced to the Pi (they are developer tools that run locally against the pi-mirror). Only `autopilot/` is rsynced.

### Restart strategy

The pilot process on the Pi is started by `run_pilot.sh`. To restart:
1. Kill the existing `pilot.py` process: `pkill -f pilot.py`
2. Wait briefly for it to die
3. Launch `run_pilot.sh` in the background via nohup so the SSH session can exit
4. Wait a few seconds and confirm the process is running

If `systemctl` is available and a pilot service is defined, use `systemctl restart pilot` instead. The script checks for systemd service first and falls back to pkill+nohup.

## Tasks

<task id="06-1" title="Create tools/ directory and sync_pi.sh">

Create `~/pi-mirror/tools/` directory if it does not exist.

Create `~/pi-mirror/tools/sync_pi.sh` with the following content:

```bash
#!/usr/bin/env bash
# sync_pi.sh — Rsync autopilot/ to the Pi.
#
# Usage:
#   ./tools/sync_pi.sh [--dry-run]
#
# Options:
#   --dry-run    Show what would be synced without making changes.
#
# Environment:
#   PI_HOST      Pi hostname or IP (default: 132.77.72.28)
#   PI_USER      Pi username (default: pi)
#   PI_SSH_KEY   Path to SSH private key (default: ~/.ssh/pi_mics)
#   PI_APP_DIR   Target directory on Pi (default: ~/Apps/mice_interactive_home_cage)

set -euo pipefail

PI_HOST="${PI_HOST:-132.77.72.28}"
PI_USER="${PI_USER:-pi}"
PI_SSH_KEY="${PI_SSH_KEY:-$HOME/.ssh/pi_mics}"
PI_APP_DIR="${PI_APP_DIR:-~/Apps/mice_interactive_home_cage}"

# Resolve script directory → project root (tools/ is one level below root)
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
MIRROR_ROOT="$(dirname "$SCRIPT_DIR")"
SOURCE_DIR="$MIRROR_ROOT/autopilot/"

DRY_RUN=""
if [[ "${1:-}" == "--dry-run" ]]; then
    DRY_RUN="--dry-run"
    echo "[sync_pi] DRY RUN — no files will be transferred"
fi

if [[ ! -f "$PI_SSH_KEY" ]]; then
    echo "ERROR: SSH key not found at $PI_SSH_KEY" >&2
    echo "  Set PI_SSH_KEY env var to the correct path." >&2
    exit 1
fi

if [[ ! -d "$SOURCE_DIR" ]]; then
    echo "ERROR: Source directory not found: $SOURCE_DIR" >&2
    exit 1
fi

echo "[sync_pi] Syncing $SOURCE_DIR → $PI_USER@$PI_HOST:$PI_APP_DIR/autopilot/"
echo "[sync_pi] SSH key: $PI_SSH_KEY"
echo

rsync \
    -avz \
    --progress \
    --exclude '__pycache__' \
    --exclude '*.pyc' \
    --exclude '*.pyo' \
    --exclude '.git' \
    --exclude '*.egg-info' \
    --exclude 'dist/' \
    --exclude 'build/' \
    $DRY_RUN \
    -e "ssh -i $PI_SSH_KEY -o StrictHostKeyChecking=no" \
    "$SOURCE_DIR" \
    "$PI_USER@$PI_HOST:$PI_APP_DIR/autopilot/"

RSYNC_EXIT=$?
if [[ $RSYNC_EXIT -eq 0 ]]; then
    echo
    echo "[sync_pi] Sync complete."
else
    echo
    echo "[sync_pi] rsync exited with code $RSYNC_EXIT" >&2
    exit $RSYNC_EXIT
fi
```

Make it executable: `chmod +x ~/pi-mirror/tools/sync_pi.sh`
</task>

<task id="06-2" title="Create deploy_pi.sh" depends_on="06-1">

Create `~/pi-mirror/tools/deploy_pi.sh` with the following content:

```bash
#!/usr/bin/env bash
# deploy_pi.sh — Sync autopilot/ to the Pi and restart the pilot process.
#
# Usage:
#   ./tools/deploy_pi.sh [--sync-only] [--restart-only] [--dry-run]
#
# Options:
#   --sync-only     Only rsync, skip restart
#   --restart-only  Only restart, skip rsync
#   --dry-run       Pass --dry-run to sync_pi.sh (implies --sync-only)
#
# Environment (same as sync_pi.sh, plus):
#   PI_APP_DIR      Pi app root (default: ~/Apps/mice_interactive_home_cage)
#   PI_PILOT_SCRIPT Path to pilot launch script on Pi relative to PI_APP_DIR
#                   (default: run_pilot.sh)

set -euo pipefail

PI_HOST="${PI_HOST:-132.77.72.28}"
PI_USER="${PI_USER:-pi}"
PI_SSH_KEY="${PI_SSH_KEY:-$HOME/.ssh/pi_mics}"
PI_APP_DIR="${PI_APP_DIR:-~/Apps/mice_interactive_home_cage}"
PI_PILOT_SCRIPT="${PI_PILOT_SCRIPT:-run_pilot.sh}"

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

SYNC=true
RESTART=true
DRY_RUN_FLAG=""

for arg in "$@"; do
    case "$arg" in
        --sync-only)    RESTART=false ;;
        --restart-only) SYNC=false ;;
        --dry-run)      DRY_RUN_FLAG="--dry-run"; RESTART=false ;;
    esac
done

SSH_CMD="ssh -i $PI_SSH_KEY -o StrictHostKeyChecking=no $PI_USER@$PI_HOST"

# ── Step 1: Sync ─────────────────────────────────────────────────────────────────────
if [[ "$SYNC" == true ]]; then
    echo "[deploy_pi] === SYNC ==="
    "$SCRIPT_DIR/sync_pi.sh" $DRY_RUN_FLAG
    echo
fi

# ── Step 2: Restart pilot process ────────────────────────────────────────────────────
if [[ "$RESTART" == true ]]; then
    echo "[deploy_pi] === RESTART PILOT ==="

    # Try systemd first
    echo "[deploy_pi] Checking for systemd pilot service..."
    SYSTEMD_RESULT=$($SSH_CMD "systemctl is-active pilot 2>/dev/null || echo 'not-found'" 2>/dev/null || echo "ssh-error")

    if [[ "$SYSTEMD_RESULT" == "active" || "$SYSTEMD_RESULT" == "inactive" || "$SYSTEMD_RESULT" == "failed" ]]; then
        echo "[deploy_pi] systemd service 'pilot' found. Restarting via systemctl..."
        $SSH_CMD "systemctl restart pilot"
        sleep 3
        STATUS=$($SSH_CMD "systemctl is-active pilot" 2>/dev/null || echo "unknown")
        if [[ "$STATUS" == "active" ]]; then
            echo "[deploy_pi] pilot service is active. Restart successful."
        else
            echo "[deploy_pi] WARNING: pilot service status is '$STATUS' after restart." >&2
        fi
    else
        # Fall back to pkill + nohup
        echo "[deploy_pi] No systemd service. Using pkill + nohup restart..."

        # Kill existing pilot.py process (ignore error if not running)
        $SSH_CMD "pkill -f 'pilot.py' 2>/dev/null || true"
        echo "[deploy_pi] Killed existing pilot.py process (if any)."
        sleep 2

        # Launch pilot in background via nohup
        PILOT_LOG="$PI_APP_DIR/logs/pilot_restart.log"
        LAUNCH_CMD="cd $PI_APP_DIR && nohup bash $PI_PILOT_SCRIPT >> $PILOT_LOG 2>&1 &"
        $SSH_CMD "$LAUNCH_CMD"
        echo "[deploy_pi] Launched pilot process."
        sleep 3

        # Confirm it's running
        PILOT_PID=$($SSH_CMD "pgrep -f 'pilot.py' 2>/dev/null || echo ''" )
        if [[ -n "$PILOT_PID" ]]; then
            echo "[deploy_pi] pilot.py is running (PID: $PILOT_PID). Deploy complete."
        else
            echo "[deploy_pi] WARNING: pilot.py process not detected after restart." >&2
            echo "[deploy_pi] Check $PILOT_LOG on the Pi for errors." >&2
            exit 1
        fi
    fi
    echo
fi

echo "[deploy_pi] Done."
```

Make it executable: `chmod +x ~/pi-mirror/tools/deploy_pi.sh`
</task>

## Verification

1. Test SSH connectivity: `ssh -i ~/.ssh/pi_mics pi@132.77.72.28 "echo ok"` → prints `ok`, exit 0.

2. Run dry-run sync: `~/pi-mirror/tools/sync_pi.sh --dry-run` → prints rsync output with list of files that would be transferred, exit 0.

3. Run actual sync (when Pi is available): `~/pi-mirror/tools/sync_pi.sh` → rsync completes, exit 0.

4. Run deploy: `~/pi-mirror/tools/deploy_pi.sh` → syncs and restarts, final line is `[deploy_pi] Done.`, exit 0.

5. Verify restart: after `deploy_pi.sh`, run `ssh -i ~/.ssh/pi_mics pi@132.77.72.28 "pgrep -a -f pilot.py"` → shows the pilot.py process.

6. Run `deploy_pi.sh --sync-only` → rsync runs but no restart attempt.

7. Run `deploy_pi.sh --restart-only` → no rsync, only restart.

8. Test with wrong SSH key path: `PI_SSH_KEY=/nonexistent ./tools/sync_pi.sh` → exit 1 with "SSH key not found" message.

## must_haves
- [ ] `sync_pi.sh` exits 0 on successful rsync
- [ ] `sync_pi.sh --dry-run` exits 0 without transferring files
- [ ] `sync_pi.sh` excludes `__pycache__`, `.pyc`, `.git`
- [ ] `deploy_pi.sh` calls `sync_pi.sh` then restarts pilot
- [ ] `deploy_pi.sh` tries systemd first, falls back to pkill+nohup
- [ ] `deploy_pi.sh --sync-only` does not restart
- [ ] `deploy_pi.sh --restart-only` does not sync
- [ ] Both scripts are executable (`chmod +x`)
- [ ] Missing SSH key → exit 1 with clear error message
- [ ] Both scripts use `set -euo pipefail` for safety
