---
name: pi-deploy
description: >
  Deploy specific code changes to the Pi (pilot device).
  Use this skill whenever the user wants to push session-edited files to the Pi,
  pull Pi state into pi-mirror, check pilot status, or tail the pilot log.
  Triggers: "update the pi", "deploy to pi", "sync pi", "push to pi",
  "is pi live", "is the pilot live", "is pi connected", "pilot status", "check pilot",
  "pull from pi", "sync mirror from pi".
---

# Pi Deploy Skill

## HARD RULES — Read Before Anything Else

1. **Pi is the absolute source of truth.** pi-mirror reflects the Pi, not the other way around. Always pull Pi → pi-mirror at the start of a session before editing any Pi code.

2. **Never sync the entire mirror to the Pi.** Only push the specific files that were written or edited in the current session. Never run `rsync /home/ido/pi-mirror/ pi@...` (full mirror push) — this is what caused past incidents where stale working-tree changes overwrote working Pi code.

3. **Never use `--delete` in rsync to the Pi.**

4. **No git operations whatsoever.** No `git commit`, `git checkout`, `git stash`, `git show`, `git merge`, or any other git command — not locally on pi-mirror, not via SSH on the Pi. Zero.

5. **Never start or stop the pilot process.** Always tell the user "Please restart the pilot on the Pi." and wait for them to do it.

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
| Pilot log | `/tmp/pilot.log` |

**SSH ControlMaster** is configured (`ControlPersist=300s`). First connection ~2s; subsequent connections within 5 minutes reuse the socket and are instant.

---

## Workflow: Start of Session — Pull Pi → pi-mirror

**Always do this before editing any Pi code.** Pi is the source of truth.

```bash
rsync -avz \
  -e "ssh -i ~/.ssh/pi_mics" \
  pi@132.77.72.28:~/Apps/mice_interactive_home_cage/ \
  /home/ido/pi-mirror/
```

This overwrites pi-mirror with whatever is on the Pi. After this, edit files in pi-mirror.

---

## Workflow: Deploy — Push Only Session-Edited Files

After editing files in pi-mirror, push **only those specific files** to the Pi.

**Identify which files were written or edited this session**, then rsync each one explicitly:

```bash
# Example: two files were edited this session
rsync -avz \
  -e "ssh -i ~/.ssh/pi_mics" \
  /home/ido/pi-mirror/autopilot/autopilot/core/pilot.py \
  /home/ido/pi-mirror/autopilot/autopilot/tasks/mics_task.py \
  pi@132.77.72.28:~/Apps/mice_interactive_home_cage/autopilot/autopilot/tasks/
```

**Important:** when pushing files from different directories, rsync them in separate commands per destination directory, or use `--relative` with the mirror root as source:

```bash
# Using --relative (preferred for multiple directories)
rsync -avz --relative \
  -e "ssh -i ~/.ssh/pi_mics" \
  /home/ido/pi-mirror/./autopilot/autopilot/core/pilot.py \
  /home/ido/pi-mirror/./autopilot/autopilot/tasks/mics_task.py \
  pi@132.77.72.28:~/Apps/mice_interactive_home_cage/
```

The `/./<path>` syntax tells rsync to preserve the relative path from that point.

After deploying, **report to the user exactly which files were pushed.**

---

## Check Pilot Status

```bash
ssh pi-mics 'ps aux | grep "pilot.py" | grep -v grep || echo "NOT_RUNNING"'
```

Check via orchestrator (confirms ZMQ handshake, not just process existence):

```bash
curl -s http://localhost:9000/pilots/live | python3 -c "
import sys, json
d = json.load(sys.stdin)
p = d.get('pilot_raspberry_lior', {})
print('connected:', p.get('connected'))
print('state:', p.get('state'))
print('updated_at:', p.get('updated_at'))
"
```

`connected: True` = heartbeat received within last 15 seconds.

---

## Tail Pilot Log

```bash
ssh pi-mics 'tail -50 /tmp/pilot.log'
```

---

## Confirming Pilot Reconnected After Restart

After the user restarts the pilot, confirm it reconnected:

```bash
curl -s http://localhost:9000/pilots/live | python3 -m json.tool
```

`pilot_raspberry_lior` should appear with `"connected": true` within ~10 seconds of starting.
