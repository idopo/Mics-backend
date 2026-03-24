---
name: pi-deploy
description: >
  Deploy code changes to the Pi (pilot device) and manage the pilot process.
  Use this skill whenever the user wants to sync local pi-mirror changes to the Pi,
  stop/start/restart the pilot process, or do a full deploy cycle (sync + restart).
  Triggers: "update the pi", "deploy to pi", "sync pi", "push to pi", "sync and restart",
  "restart the pilot", "restart pilot process", "restart the pi service", "stop the pilot",
  "kill the pilot", "start the pilot", "is pi live", "is the pilot live", "is pi connected",
  "pilot status", "check pilot".
---

# Pi Deploy Skill

## HARD RULES: No Git Operations on the Pi, No --delete in rsync, Never Start/Stop Pilot

**Never run any git command on the Pi.** No `git commit`, `git merge`, `git checkout`, `git push`, `git add`, or any other git operation via SSH.

**Never use `--delete` in rsync to the Pi.** The Pi's `~/Apps/mice_interactive_home_cage/` is a live git repo (remote: https://github.com/liorse/mice_interactive_home_cage). Using `--delete` removes files that exist on the Pi but not in pi-mirror, corrupting the Pi's git state. Only push files — never delete.

The Pi receives code via rsync (push only). All version control for MICS backend happens in the `mics-backend` repo on this machine. Pi-side git history is managed independently via its own remote.

**Never start or stop the pilot process.** This includes `run_pilot.sh`, `pkill -f pilot.py`, or any SSH command that starts/stops the pilot. Always tell the user "Please restart the pilot on the Pi." and wait for them to do it.

---

## Connection Details

| Item | Value |
|---|---|
| SSH alias | `pi-mics` (defined in `~/.ssh/config`) |
| Pi host | `132.77.72.28` |
| Pi user | `pi` |
| SSH key | `~/.ssh/pi_mics` |
| Pi code root | `~/Apps/mice_interactive_home_cage/` |
| Local mirror | `/home/ido/pi-mirror/` |
| Start script | `~/Apps/mice_interactive_home_cage/run_pilot.sh` |
| Process pattern | `pilot.py` |
| Pilot log (when started via deploy) | `/tmp/pilot.log` |

**SSH ControlMaster** is configured (`~/.ssh/config`, `ControlPersist=300s`). First connection
takes ~2s; subsequent connections within 5 minutes reuse the socket and are nearly instant.
Always use `ssh pi-mics` — never the raw `ssh pi-mics` form.

---

## Deploy Scripts (Preferred)

Shell scripts in `~/pi-mirror/tools/` provide the canonical deploy workflow:

```bash
# Sync only (safe while pilot is running)
~/pi-mirror/tools/sync_pi.sh

# Sync + restart pilot
~/pi-mirror/tools/deploy_pi.sh

# Sync only (no restart)
~/pi-mirror/tools/deploy_pi.sh --sync-only

# Restart only (no sync)
~/pi-mirror/tools/deploy_pi.sh --restart-only

# Dry-run (shows what would be synced, no transfer)
~/pi-mirror/tools/sync_pi.sh --dry-run
~/pi-mirror/tools/deploy_pi.sh --dry-run
```

Both scripts accept env var overrides: `PI_HOST`, `PI_USER`, `PI_SSH_KEY`, `PI_APP_DIR`.

---

## Commands

## Check if Pi is live (orchestrator view)

One-liner — checks `pilot_raspberry_lior` (Pi at `132.77.72.28`) specifically:

```bash
curl -s http://localhost:9000/pilots/live | python3 -c "import sys,json; d=json.load(sys.stdin); p=d.get('pilot_raspberry_lior',{}); print('connected:', p.get('connected')); print('state:', p.get('state')); print('updated_at:', p.get('updated_at'))"
```

`connected: True` means a heartbeat arrived within the last 15 seconds. `False` = pilot is down or unreachable.

---

## Always Check Status First

**Before any stop/start/restart action, always check if the pilot is running.** Report the
current state to the user before acting. Never blindly start a pilot that's already running
or stop one that's already stopped.

### Check status

```bash
ssh pi-mics 'ps aux | grep "pilot.py" | grep -v grep || echo "NOT_RUNNING"'
```

### Sync pi-mirror → Pi (push local changes)

```bash
rsync -avz \
  -e "ssh -i ~/.ssh/pi_mics" \
  /home/ido/pi-mirror/ \
  pi@132.77.72.28:~/Apps/mice_interactive_home_cage/
```

Use `--dry-run` first if unsure what will change.

### Stop the pilot

Kill the pilot processes and release ZMQ ports (5565 and 556) so a subsequent start is clean:

```bash
ssh pi-mics 'pkill -f "pilot.py" 2>/dev/null; sudo kill -9 $(sudo lsof -t -i:5565) $(sudo lsof -t -i:556) 2>/dev/null; true'
```

May exit with code 255 — expected, processes are stopped regardless.

Verify it stopped:
```bash
ssh pi-mics 'ps aux | grep "pilot.py" | grep -v grep || echo "stopped"'
```

### Start the pilot

`run_pilot.sh` uses relative paths, so you MUST `cd` into the code root first.
`nohup` + `< /dev/null` fully detaches the process so SSH returns immediately
(without `< /dev/null`, SSH waits on the inherited stdin file descriptor).

Launch in a subshell `(...)` so the process is fully detached from the SSH session (prevents
SSH from waiting on the background job). Then poll separately with a second fast SSH call
(ControlMaster makes it nearly instant):

```bash
# 1. Fire-and-forget launch (SSH returns in <1s)
ssh pi-mics '(cd ~/Apps/mice_interactive_home_cage && nohup bash run_pilot.sh > /tmp/pilot.log 2>&1 < /dev/null &)'

# 2. Verify via orchestrator live endpoint — checks the specific pilot for this Pi
PILOT_NAME="pilot_raspberry_lior"  # pilot at 132.77.72.28
for i in $(seq 1 30); do
  sleep 1
  curl -s http://localhost:9000/pilots/live | \
    python3 -c "import sys,json; d=json.load(sys.stdin); exit(0 if d.get('${PILOT_NAME}',{}).get('connected') else 1)" \
    && echo "Pilot ${PILOT_NAME} connected to orchestrator!" && break
done
```

Why orchestrator check: `connected: true` on the specific pilot key means that Pi sent its
HANDSHAKE over ZMQ — the definitive signal it's fully up and communicating. Checks by pilot
name (which maps 1:1 to `132.77.72.28`) rather than any pilot in the response.

### Tail pilot log

```bash
ssh pi-mics 'tail -50 /tmp/pilot.log'
```

---

## Common Workflows

### Full deploy cycle (sync → stop → start)

Run these steps in order:

```bash
# 1. Sync local changes to Pi
rsync -avz \
  -e "ssh -i ~/.ssh/pi_mics" \
  /home/ido/pi-mirror/ \
  pi@132.77.72.28:~/Apps/mice_interactive_home_cage/

# 2. Stop pilot + release ZMQ ports (exit 255 expected)
ssh pi-mics 'pkill -f "pilot.py" 2>/dev/null; sudo kill -9 $(sudo lsof -t -i:5565) $(sudo lsof -t -i:556) 2>/dev/null; true'

# 3. Verify stopped before starting (prevents double-instance)
ssh pi-mics 'ps aux | grep "pilot.py" | grep -v grep || echo "STOPPED"'

# 4. Start (fire-and-forget — subshell detaches, SSH returns in <1s)
ssh pi-mics '(cd ~/Apps/mice_interactive_home_cage && nohup bash run_pilot.sh > /tmp/pilot.log 2>&1 < /dev/null &)'
```

### Sync only (don't restart)

Use when the pilot is running a session and shouldn't be interrupted:

```bash
rsync -avz \
  -e "ssh -i ~/.ssh/pi_mics" \
  /home/ido/pi-mirror/ \
  pi@132.77.72.28:~/Apps/mice_interactive_home_cage/
```

### Restart only (no sync)

Use when you haven't changed files but need a clean restart:

```bash
# 1. Stop + release ZMQ ports (exit 255 is expected — pkill kills its own shell)
ssh pi-mics 'pkill -f "pilot.py" 2>/dev/null; sudo kill -9 $(sudo lsof -t -i:5565) $(sudo lsof -t -i:556) 2>/dev/null; true'

# 2. Verify fully stopped before starting (prevents double-instance)
ssh pi-mics 'ps aux | grep "pilot.py" | grep -v grep || echo "STOPPED"'
# Must see "STOPPED". If processes still listed, wait 2s and check again.

# 3. Start
ssh pi-mics '(cd ~/Apps/mice_interactive_home_cage && nohup bash run_pilot.sh > /tmp/pilot.log 2>&1 < /dev/null &)'

# 4. Confirm connected to orchestrator
PILOT_NAME="pilot_raspberry_lior"
for i in $(seq 1 30); do sleep 1; curl -s http://localhost:9000/pilots/live | python3 -c "import sys,json; d=json.load(sys.stdin); exit(0 if d.get('${PILOT_NAME}',{}).get('connected') else 1)" && echo "Pilot connected!" && break; done
```

---

## Confirming Pilot Reconnected to Orchestrator

After restart, the pilot sends a HANDSHAKE to the orchestrator. Confirm via the API:

```bash
curl -s http://localhost:9000/pilots/live | python3 -m json.tool
```

Or check the orchestrator logs:
```bash
docker compose logs --tail=30 orchestrator
```

The pilot `pilot_raspberry_lior` (Pi at `132.77.72.28`) should appear with `"connected": true`
within ~10 seconds of starting.
