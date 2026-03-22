# Pi Code Editor Plan

Browser-based code review and editing for Pi task files.
This is a **power-user / developer feature** that runs alongside the no-code FDA editor.

Status: PLANNED — not yet started.

Companion document: `toolkit_fda_plan.md` (the no-code state logic builder).

---

## GSD Framework

### Why

**Problem:** Developers extending ToolKit classes must SSH into each Pi individually,
edit Python files with nano/vim, restart the pilot process, watch logs via SSH, and
repeat — with no browser-accessible UI and no way for non-SSH users to review code.
This slows down toolkit development and creates a barrier for lab members who need to
review task logic but don't have SSH access.

**Impact:**
- ToolKit iterations require at minimum: SSH + edit + restart + verify (5–10 min cycle)
- Multiple Pis require repeating the full cycle per device
- Lab members cannot review what a task actually does without asking a developer
- No integrated path from "edit code" → "validate FDA" → "restart" → "see logs"

**What this feature adds:**
1. **Read-only code review** — Browse Pi task files in the browser with syntax highlighting
2. **Edit + push** — Modify a ToolKit's Python source, write to Pi via SSH, restart pilot
3. **Live terminal** — Run arbitrary commands on the Pi (pip install, validate_fda.py, log tail)
4. **Package management UI** — Check and install required packages per toolkit

**Non-goal:** This does NOT replace the no-code FDA editor for researchers. It is the
escape hatch for developers who need to extend toolkits or debug at the Python level.

---

### What (Deliverables + Acceptance Criteria)

**Phase A — Read-Only Viewer**

| Deliverable | Acceptance Criteria |
|---|---|
| `GET /api/pi/files?path=<dir>` | Returns `[{name, type, size, mtime}]`; filters out `__pycache__`, `.pyc`, `.git`; returns 403 if path is outside `PI_EDITOR_ROOTS` |
| `GET /api/pi/file?path=<file>` | Returns `{content: string, language: "python"}`; returns 404 if file not found on Pi; 403 if outside roots |
| `GET /api/pi/status` | Returns `{"connected": true/false, "pilot_state": "..."}` within 2s; connected=false if SSH unreachable |
| React page `/react/pi-editor` | Loads file tree for `autopilot/tasks/` and `pilot/plugins/`; click file shows content in Monaco read-only; no console errors |
| `PiFileBrowser` component | Renders expandable tree; lazy-loads subdirectory contents on expand; shows file type icons |
| `PiStatusBar` component | Shows Pi hostname, SSH connection status; shows pilot running/idle state from existing `/api/pilots/live` |

**Phase B — Terminal**

| Deliverable | Acceptance Criteria |
|---|---|
| `POST /api/pi/exec` | Runs command on Pi via SSH; returns `{stdout, stderr, exit_code}`; disabled (403) unless `ALLOW_PI_EXEC=true` env var is set |
| `WS /ws/pi/exec` | Streams stdout/stderr in real-time as `{stdout: line}` / `{stderr: line}` / `{exit_code: n}`; WebSocket closes after command completes |
| `PiTerminal` component | xterm.js renders streamed output; input bar accepts `!command`; shows exit code; ANSI colors rendered correctly |
| Phase B only enabled with env var | All exec endpoints return 403 when `ALLOW_PI_EXEC` is not set; feature appears grayed out in UI with "Developer mode not enabled" tooltip |

**Phase C — Edit + Restart**

| Deliverable | Acceptance Criteria |
|---|---|
| `PUT /api/pi/file` | Writes `{path, content}` to Pi via SSH; returns 200 on success; rejects paths outside roots with 403; requires `ALLOW_PI_EXEC=true` |
| `POST /api/pi/restart` | Restarts pilot process on Pi; returns 200 immediately; actual restart visible in terminal output and pilot status |
| Monaco edit mode | Monaco switches to editable when "Edit" button clicked; dirty flag shows `●` in tab; "Save" writes via `PUT /api/pi/file`; "Discard" reverts to fetched content |
| Unsaved changes guard | Navigating away from dirty editor shows browser confirm dialog |
| After restart, HANDSHAKE fires | After pilot restarts, orchestrator receives HANDSHAKE, `task_toolkits` table is updated; confirmed via postgres MCP |

**Phase D — Sync + Package Management**

| Deliverable | Acceptance Criteria |
|---|---|
| `POST /api/pi/sync` | Runs `tools/sync_pi.sh` on web_ui server; streams output via WebSocket; completes with rsync exit code |
| `GET /api/pi/packages` | Returns `[{name, version, installed: bool}]` — installed packages from `pip list` on Pi, cross-referenced with `required_packages` from all toolkits in `task_toolkits` table |
| `POST /api/pi/packages` | Installs `{package: string}` via `pip install` on Pi; streams output |
| Packages tab UI | Shows "Required by Toolkits" section with installed/missing status; "Install Missing" button; manual install input |

---

### How (Step-by-Step Execution)

#### Phase A Implementation

**Step 1: New module `web_ui/pi_ssh.py`**

```python
import asyncssh
import os

PI_HOST = os.environ.get("PI_HOST", "132.77.72.28")
PI_USER = os.environ.get("PI_USER", "pi")
PI_KEY  = os.environ.get("PI_KEY",  os.path.expanduser("~/.ssh/pi_mics"))
PI_CODE_ROOT = os.environ.get("PI_CODE_ROOT",
                               "~/Apps/mice_interactive_home_cage")

PI_EDITOR_ROOTS = [
    f"{PI_CODE_ROOT}/autopilot",
    f"{PI_CODE_ROOT}/pilot/plugins",
    f"{PI_CODE_ROOT}/pilot/protocols",
]

_ssh_conn = None  # module-level cached connection

async def get_ssh_conn() -> asyncssh.SSHClientConnection:
    global _ssh_conn
    if _ssh_conn is None or _ssh_conn.is_closed():
        _ssh_conn = await asyncssh.connect(
            PI_HOST, username=PI_USER,
            client_keys=[PI_KEY],
            known_hosts=None,      # lab network, acceptable
            keepalive_interval=30,
        )
    return _ssh_conn

async def is_connected() -> bool:
    try:
        conn = await get_ssh_conn()
        return not conn.is_closed()
    except Exception:
        return False
```

**Step 2: API endpoints in `web_ui/app.py`**

Insert after the existing WebSocket handler block (around line 250).

Path validation helper (prevents directory traversal):
```python
def _validate_pi_path(path: str) -> bool:
    """Return True if path is inside one of PI_EDITOR_ROOTS."""
    abs_path = os.path.normpath(path)
    return any(abs_path.startswith(root) for root in PI_EDITOR_ROOTS)
```

New endpoints to add:

```
GET  /api/pi/status        → {"connected": bool, "pilot_state": str|null}
GET  /api/pi/files         → [{name, type, size, mtime}]  (query: path=)
GET  /api/pi/file          → {content: str, language: str} (query: path=)
```

For `GET /api/pi/files`: run `ls -la --time-style=+%Y-%m-%d <path>` via SSH, parse output.
Filter entries where name starts with `.` or ends with `.pyc` or is `__pycache__`.

For `GET /api/pi/file`: run `cat <path>` via SSH, return content.
Detect language from extension (`.py` → `python`, `.json` → `json`, `.sh` → `shell`).

**Step 3: React page `web_ui/react-src/src/pages/pi-editor/index.tsx`**

New route in `App.tsx`: `<Route path="/react/pi-editor" element={<PiEditor />} />`
New Nav entry: "Pi Editor" (show conditionally based on `SHOW_PI_EDITOR` env var passed via
a `/api/config` endpoint, or always show and disable if disconnected).

Layout:
```tsx
<div className="container split">
  <PiFileBrowser onFileSelect={setSelectedPath} />
  <div>
    <PiStatusBar />
    <MonacoEditorPanel path={selectedPath} readOnly={true} />
  </div>
</div>
```

**Step 4: `PiFileBrowser` component**

```
src/components/PiFileBrowser.tsx
```
- Props: `onFileSelect: (path: string) => void`
- State: `tree: Map<string, FileEntry[]>`, `expanded: Set<string>`
- On mount: fetch `/api/pi/files?path=<PI_CODE_ROOT>/autopilot/tasks` and
  `/api/pi/files?path=<PI_CODE_ROOT>/pilot/plugins`
- On directory expand: fetch `/api/pi/files?path=<dir>` lazily
- Filter: hide `__pycache__`, `*.pyc`, `.git`
- Render: `<ul>` with `<li>` per entry; folder icon for dirs, file icon for `.py`

**Step 5: `MonacoEditorPanel` component**

```
src/components/MonacoEditorPanel.tsx
```
- Props: `path: string | null`, `readOnly: boolean`
- On `path` change: fetch `/api/pi/file?path=<path>`, set Monaco content + language
- Monaco config: `theme: 'vs-dark'`, `readOnly: readOnly`, `minimap: {enabled: false}`
- Use `@monaco-editor/react` (npm package — add to `web_ui/react-src/package.json`)

**Step 6: npm packages to add**

In `web_ui/react-src/package.json`:
```json
"@monaco-editor/react": "^4.6.0"
```

Phase B adds:
```json
"@xterm/xterm": "^5.3.0",
"@xterm/addon-fit": "^0.8.0"
```

Python packages in `web_ui/requirements.txt`:
```
asyncssh>=2.14.0
```

#### Phase B Implementation

**Step 1: Exec endpoints**

Guard all exec endpoints with:
```python
ALLOW_PI_EXEC = os.environ.get("ALLOW_PI_EXEC", "").lower() == "true"
if not ALLOW_PI_EXEC:
    raise HTTPException(status_code=403, detail="Developer exec mode not enabled")
```

`POST /api/pi/exec`:
```python
@app.post("/api/pi/exec")
async def pi_exec(body: dict):
    conn = await get_ssh_conn()
    result = await conn.run(body["command"], check=False)
    return {"stdout": result.stdout, "stderr": result.stderr, "exit_code": result.exit_status}
```

`WS /ws/pi/exec`:
```python
@app.websocket("/ws/pi/exec")
async def ws_pi_exec(ws: WebSocket, token: str = Query(...)):
    # Verify token
    await ws.accept()
    msg = await ws.receive_json()
    command = msg.get("command", "")
    async with asyncssh.connect(PI_HOST, username=PI_USER, client_keys=[PI_KEY]) as conn:
        async with conn.create_process(command) as process:
            async for line in process.stdout:
                await ws.send_json({"stdout": line})
            await ws.send_json({"exit_code": process.returncode})
```

**Step 2: `PiTerminal` component**

```
src/components/PiTerminal.tsx
```
- Uses `xterm.js` Terminal + FitAddon
- Input bar at bottom: text input + "Run" button
- On submit: open `/ws/pi/exec` WebSocket, send `{command: input}`, pipe stdout/stderr to terminal
- Color stderr lines red via `\x1b[31m...\x1b[0m`
- Show exit code on completion

#### Phase C Implementation

**Step 1: Write + restart endpoints**

```python
@app.put("/api/pi/file")
async def pi_write_file(body: dict):
    if not _validate_pi_path(body["path"]):
        raise HTTPException(status_code=403, detail="Path outside editor roots")
    conn = await get_ssh_conn()
    async with conn.start_sftp_client() as sftp:
        async with sftp.open(body["path"], 'w') as f:
            await f.write(body["content"])
    return {"status": "ok"}

@app.post("/api/pi/restart")
async def pi_restart():
    conn = await get_ssh_conn()
    # Adjust command to match actual Pi process management
    await conn.run("systemctl restart pilot || pkill -f pilot.py", check=False)
    return {"status": "restarting"}
```

**Step 2: Monaco edit mode**

Add "Edit" button to `MonacoEditorPanel`. On click:
- Set `readOnly=false` in Monaco options
- Show dirty indicator when content differs from fetched content
- "Save" button: `PUT /api/pi/file` → toast on success
- "Discard" button: reset to fetched content, readOnly=true

**Step 3: Unsaved changes guard**

```tsx
useEffect(() => {
    const handler = (e: BeforeUnloadEvent) => {
        if (isDirty) e.preventDefault();
    };
    window.addEventListener('beforeunload', handler);
    return () => window.removeEventListener('beforeunload', handler);
}, [isDirty]);
```

#### Phase D Implementation

**Step 1: Packages endpoint**

```python
@app.get("/api/pi/packages")
async def pi_packages():
    conn = await get_ssh_conn()
    result = await conn.run("pip list --format=json", check=False)
    installed = {pkg["name"].lower(): pkg["version"]
                 for pkg in json.loads(result.stdout)}
    # Get required packages from DB
    required = await get_all_required_packages()  # queries task_toolkits table
    return [
        {"name": pkg, "version": installed.get(pkg.lower()),
         "installed": pkg.lower() in installed}
        for pkg in required
    ]
```

**Step 2: Packages tab UI**

Add "Packages" tab to the Pi Editor page (alongside File Browser).
Render two sections: "Required by Toolkits" (computed diff) and "Install Package" (manual input).

---

### Who / When (Phase Order and Dependencies)

```
Phase A (Read-Only)  ──────────────────────────────────────► safe to deploy immediately
   ↓ ALLOW_PI_EXEC=true env var required to activate
Phase B (Terminal) ─────────────────────────────────────────► depends on Phase A SSH module
   ↓ same env var gate, same SSH module
Phase C (Edit + Restart) ───────────────────────────────────► depends on Phase A + B
   ↓ requires task_toolkits table from toolkit_fda_plan Phase 2
Phase D (Package Management) ───────────────────────────────► depends on Phase C + toolkit Phase 2
```

Phase A has zero risk and can be deployed to production immediately.
Phases B–D require `ALLOW_PI_EXEC=true` to be set explicitly in `docker-compose.yml`.

**Cross-dependency:** Phase D's "Required by Toolkits" section requires `task_toolkits`
table from `toolkit_fda_plan.md` Phase 2. Can be stubbed to return empty list until then.

---

### Risks

| Risk | Likelihood | Mitigation |
|---|---|---|
| SSH connection drops during file write (Phase C) | Medium | Use `asyncssh` SFTP for writes (atomic at filesystem level); check connection health before write; return 503 if disconnected so UI can retry |
| Path traversal attack on `/api/pi/file` | Low | `_validate_pi_path()` uses `os.path.normpath` + `startswith`; symlinks could bypass this — add `realpath` resolution via `ssh conn.run("realpath <path>")` before serving |
| `conn.run()` hangs if Pi command never exits | Medium | Set `timeout=30` on `conn.run()` calls; WebSocket exec uses `process.kill()` on WebSocket disconnect |
| Concurrent edits from two browser windows | Low | Last-write-wins is acceptable for now; document limitation; future: file lock via SSH lock file |
| Pilot restart command varies per Pi setup | Medium | Make restart command configurable via `PI_RESTART_CMD` env var; default: `pkill -f pilot.py` |
| Monaco bundle size impact on initial load | Medium | Monaco is ~2MB gzipped; use dynamic `import()` / React.lazy for the pi-editor page so it doesn't load for non-developer users |
| `asyncssh` not in current `web_ui/requirements.txt` | Certain | Add `asyncssh>=2.14.0` to `web_ui/requirements.txt` and rebuild Docker image |
| xterm.js WebSocket auth — token in query param | Low | Token in query param is acceptable for WebSocket (cookie alternative is complex); document this limitation |

---

## Architecture Decision: Monaco Editor + SSH Proxy API

### Option A: JupyterLab on Pi (rejected)

Run Jupyter server on the Pi, proxy via web_ui at `/pi-editor/`.

**Verdict: Rejected.** Too heavy for Pi (1GB+ RAM), wrong paradigm for .py files,
complex proxy auth.

### Option B: code-server (VS Code in browser) on Pi (rejected)

**Verdict: Rejected.** Very heavy, hard to integrate, not viable on Pi.

### Option C: Monaco Editor + SSH Proxy API (chosen)

- React page with Monaco Editor (VS Code engine, tree-shakeable)
- FastAPI endpoints in `web_ui/app.py` proxy to Pi via `asyncssh`
- File browser sidebar for Pi code directories
- Terminal panel using `xterm.js` for live command output
- Pi only needs SSH access — no extra software on Pi
- Full control over auth (reuses existing JWT)

---

## Two-Layer Command Execution

### Layer 1: Direct SSH (developer)

Raw SSH command execution via `WS /ws/pi/exec`. Developer types a command, it runs on the Pi,
output streams back via xterm.js terminal.

Examples:
```
!pip install adafruit-circuitpython-mpr121
!python ~/Apps/mice_interactive_home_cage/tools/validate_fda.py AppetitiveTaskReal fda.json
!ls ~/Apps/mice_interactive_home_cage/autopilot/tasks/
!tail -100 ~/Apps/mice_interactive_home_cage/logs/pilot.log
```

### Layer 2: Structured Actions (buttons)

Pre-built buttons for common operations:
- **Sync from local** — runs `tools/sync_pi.sh` (rsync pi-mirror to Pi), streams output
- **Restart pilot** — runs `POST /api/pi/restart`
- **Validate FDA** — runs `validate_fda.py` with selected file, shows results inline
- **Check packages** — runs `pip list` and compares against `REQUIRED_PACKAGES`
- **Tail logs** — streams last N lines of pilot log via terminal

---

## Component Architecture

### Backend: `web_ui/pi_ssh.py` (new module)

Module-level cached `asyncssh` connection. Auto-reconnects if dropped.
All Pi API endpoints import from this module.

### Backend: New endpoints in `web_ui/app.py`

```
GET  /api/pi/status        → SSH health + pilot state
GET  /api/pi/files         → directory listing
GET  /api/pi/file          → file content
PUT  /api/pi/file          → write file (requires ALLOW_PI_EXEC)
POST /api/pi/exec          → run command, return output (requires ALLOW_PI_EXEC)
WS   /ws/pi/exec           → stream command output (requires ALLOW_PI_EXEC)
POST /api/pi/restart       → restart pilot (requires ALLOW_PI_EXEC)
GET  /api/pi/packages      → installed vs required packages
POST /api/pi/packages      → install package (requires ALLOW_PI_EXEC)
```

**Security model:**
- All `/api/pi/*` endpoints require JWT auth (same as rest of API)
- Write/exec endpoints additionally require `ALLOW_PI_EXEC=true` env var
- Path validation prevents directory traversal attacks
- Command execution is restricted to Pi-side only (not the web_ui server)
- Future: command allowlist for dangerous operations

### Frontend: React page `/react/pi-editor`

**Layout:**
```
┌──────────────────────────────────────────────────────────────────┐
│  Pi Code Editor                          [Pi: 132.77.72.28 ✓]   │
├───────────────┬──────────────────────────────────────────────────┤
│               │                                                  │
│  FILE BROWSER │  EDITOR (Monaco)                                 │
│               │                                                  │
│  autopilot/   │  1  import pytz                                  │
│   tasks/      │  2  from autopilot.tasks.task import Task        │
│    mics_      │  ...                                             │
│    learni_    │                                                  │
│   hardware/   │  [modified indicator]                            │
│   utils/      │                                                  │
│  pilot/       │                                                  │
│   plugins/    │  ┌──────── TERMINAL ──────────────────────────┐  │
│               │  │ $ !pip install adafruit-mpr121             │  │
│  [Sync]       │  │ Collecting adafruit-mpr121...              │  │
│  [Restart]    │  │ Successfully installed.                    │  │
│  [Validate]   │  │ $                                          │  │
│               │  └────────────────────────────────────────────┘  │
└───────────────┴──────────────────────────────────────────────────┘
```

**Components:**
- `PiFileBrowser` — tree view of Pi directories, click to open in editor
- `MonacoEditorPanel` — Monaco Editor with Python syntax highlighting
- `PiTerminal` — xterm.js terminal connected to `/ws/pi/exec` websocket
- `PiStatusBar` — shows Pi SSH connection status, pilot running state
- `PiActionBar` — Sync, Restart, Validate buttons with progress/output

### Monaco Integration

```typescript
import Editor from '@monaco-editor/react'

<Editor
  language={language}
  value={fileContent}
  onChange={setFileContent}
  options={{
    readOnly: !editMode,
    minimap: { enabled: false },
    fontSize: 13,
    theme: 'vs-dark',
    scrollBeyondLastLine: false,
  }}
/>
```

### Save + Deploy Flow (Phase C)

1. User edits file in Monaco → local state tracks dirty flag
2. "Save" button → `PUT /api/pi/file` → writes file content to Pi via SSH SFTP
3. "Restart Pilot" button → `POST /api/pi/restart` → pilot process restarts
4. Terminal shows restart output stream
5. After restart, pilot reconnects to orchestrator via HANDSHAKE → toolkits table updated

**Sync vs Save distinction:**
- "Save" writes a single file directly to Pi (SFTP) — fast, immediate
- "Sync" runs `tools/sync_pi.sh` — rsync entire pi-mirror to Pi — full copy
- "Sync from Pi" (reverse) — rsync from Pi to pi-mirror — useful if Pi has diverged

---

## Terminal Implementation

```typescript
import { Terminal } from '@xterm/xterm'
import { FitAddon } from '@xterm/addon-fit'

// WebSocket to /ws/pi/exec
// Send:    { command: string }
// Receive: { stdout: string } | { stderr: string } | { exit_code: number }
```

Backend WebSocket handler streams stdout/stderr as they arrive.
The React terminal can also accept `!command` prefix in a text input bar at the bottom.

---

## File Browser

Files exposed to the browser (configurable via `PI_EDITOR_ROOTS` env var):

```
~/Apps/mice_interactive_home_cage/autopilot/       # core library
~/Apps/mice_interactive_home_cage/pilot/plugins/   # task plugins
~/Apps/mice_interactive_home_cage/pilot/protocols/ # FDA JSON files
```

File tree structure returned by `GET /api/pi/files?path=...`:

```json
[
  { "name": "mics_task.py",    "type": "file", "size": 6240, "mtime": "2025-03-10" },
  { "name": "learning_cage.py","type": "file", "size": 3120, "mtime": "2025-02-28" },
  { "name": "__pycache__",     "type": "dir" }
]
```

Hidden: `__pycache__`, `.pyc` files, `.git`.

---

## Dependency Management UI

A "Packages" tab on the Pi editor page:

```
┌────────────────────────────────────────────────────┐
│  Pi Packages                                       │
│                                                    │
│  REQUIRED BY TOOLKITS                              │
│  ✓ adafruit-circuitpython-mpr121  1.2.0  installed │
│  ✓ pigpio                         1.78   installed │
│  ✗ some-new-library               —      MISSING   │
│                        [Install Missing Packages]  │
│                                                    │
│  INSTALL PACKAGE                                   │
│  [package name input]          [Install]           │
│                                                    │
│  OUTPUT                                            │
│  [terminal output of pip install]                  │
└────────────────────────────────────────────────────┘
```

"Required by Toolkits" is computed by:
1. `GET /api/toolkits` — each toolkit includes `required_packages` from HANDSHAKE
2. `GET /api/pi/packages` — list of installed packages on Pi
3. UI computes the diff and shows missing

Note: "Required by Toolkits" section requires `task_toolkits` table from
`toolkit_fda_plan.md` Phase 2. Return empty list until that phase is complete.

---

## Connection Pooling + Reconnect

The web_ui backend maintains a persistent SSH connection to the Pi via `asyncssh`.
If the connection drops (Pi restart, network issue):
- `GET /api/pi/status` returns `{"connected": false}`
- UI shows "Pi disconnected" banner
- All Pi editor actions are disabled until reconnect
- Reconnect is attempted automatically when the next request comes in (lazy reconnect)
- Background health-check task polls every 30s and updates a module-level `_connected` flag

---

## Design Decisions

- **asyncssh not subprocess** — async SSH keeps web_ui non-blocking
- **Monaco not CodeMirror** — better Python support, familiar VS Code feel
- **xterm.js for terminal** — standard, maintained, works with WebSocket streaming
- **Phase A first** — read-only viewer has zero risk, provides immediate value
- **ALLOW_PI_EXEC flag** — write/exec endpoints gated behind env var, not always on
- **Direct SSH to Pi** — web_ui connects to Pi directly (not through orchestrator);
  simpler, no ZMQ plumbing needed for file operations
- **SFTP for file writes** — `asyncssh.start_sftp_client()` is safer than `echo > file`
  via SSH exec; atomic write at the SFTP level
- **No notebook format** — Pi task files are .py scripts, not .ipynb; Monaco is correct
- **Dynamic import for Monaco** — avoids adding ~2MB to initial bundle for all users;
  use `React.lazy(() => import('./MonacoEditorPanel'))` so Monaco only loads on this page
- **PI_EDITOR_ROOTS configurable** — different Pi setups may have different code locations;
  env var avoids hardcoding

## Open Questions

- **Multi-Pi support:** Pi editor currently assumes one Pi (hardcoded host). Future: pilot
  selector dropdown, `PI_HOSTS` env var list, per-pilot SSH connection pool.
- **Concurrent edits:** if two browser windows edit the same file simultaneously, last save wins.
  Simple for now; consider file locking or conflict detection in future.
- **Audit log:** should we log which user saved/exec'd what on the Pi? Useful for lab accountability.
- **Read-only for non-admin users:** Phase A is always read-only; restrict Phase C/D to users
  with admin JWT claim.
- **Integrated validate:** "Save + Validate" button runs `validate_fda.py` automatically
  after saving a toolkit file and shows results inline as Monaco diagnostics (markers).
- **Restart command variability:** different Pi setups use different process managers;
  `PI_RESTART_CMD` env var handles this; document in README.
