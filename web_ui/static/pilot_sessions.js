// pilot_sessions.js
// Pilot-centric session launcher (Redis-backed, FINAL with full details)

let pilotId = null;
let CURRENT_PILOT_STATE = null;
let ws = null;

let renderSessionsCache = null;
let LAST_PILOT_STATE_KEY = null;

// Caches to avoid refetching
const SESSION_DETAILS_CACHE = {};
const PROTOCOL_CACHE = {};

// --------------------------------------------------
// WebSocket: live pilot state (Redis → orchestrator)
// --------------------------------------------------
function initPilotWebSocket() {
  ws = new WebSocket(`ws://${location.host}/ws/pilots`);

  ws.onmessage = (event) => {
    const data = JSON.parse(event.data);
    const pilotInfo = data[PILOT_NAME];
    if (!pilotInfo) return;

    const newKey = JSON.stringify({
      connected: pilotInfo.connected,
      state: pilotInfo.state,
      runId: pilotInfo.active_run?.id ?? null,
    });

    if (newKey === LAST_PILOT_STATE_KEY) return;

    LAST_PILOT_STATE_KEY = newKey;
    CURRENT_PILOT_STATE = pilotInfo;

    if (renderSessionsCache) {
      renderSessions(renderSessionsCache);
    }
  };

  ws.onerror = (err) => {
    console.error("Pilot WS error:", err);
  };
}

// --------------------------------------------------
// Load sessions once
// --------------------------------------------------
async function loadSessions() {
  const res = await fetch("/api/sessions");
  if (!res.ok) throw new Error("Failed to load sessions");

  const sessions = await res.json();
  renderSessionsCache = sessions;
  renderSessions(sessions);
}

// --------------------------------------------------
// Load pilot ID (DB)
// --------------------------------------------------
async function loadPilotId() {
  const res = await fetch("/api/backend/pilots");
  if (!res.ok) throw new Error("Failed to load backend pilots");

  const pilots = await res.json();
  const pilot = pilots.find(p => p.name === PILOT_NAME);

  if (!pilot) {
    throw new Error(`Pilot not found in backend DB: ${PILOT_NAME}`);
  }

  pilotId = pilot.id;
}

// --------------------------------------------------
// Render sessions with protocol + subjects + Start/Stop
// --------------------------------------------------
async function renderSessions(sessions) {
  const ul = document.getElementById("sessions");
  const status = document.getElementById("status");

  ul.innerHTML = "";

  // Pilot offline → block execution
  if (!CURRENT_PILOT_STATE?.connected) {
    ul.innerHTML = `<li class="muted">Pilot is offline</li>`;
    return;
  }

  if (!Array.isArray(sessions) || sessions.length === 0) {
    ul.innerHTML = `<li class="muted">No sessions available</li>`;
    return;
  }

  const activeRun = CURRENT_PILOT_STATE.active_run || null;

  for (const s of sessions) {
    try {
      // -------------------------
      // Session details (cached)
      // -------------------------
      let sessionDetail = SESSION_DETAILS_CACHE[s.session_id];
      if (!sessionDetail) {
        const resp = await fetch(`/api/sessions/${s.session_id}`);
        if (!resp.ok) continue;
        sessionDetail = await resp.json();
        SESSION_DETAILS_CACHE[s.session_id] = sessionDetail;
      }

      const runs = sessionDetail.runs || [];
      if (runs.length === 0) continue;

      const protocolId = runs[0].protocol_id;

      // -------------------------
      // Protocol (cached)
      // -------------------------
      let protocol = PROTOCOL_CACHE[protocolId];
      if (!protocol) {
        const resp = await fetch(`/api/protocols/${protocolId}`);
        if (!resp.ok) continue;
        protocol = await resp.json();
        PROTOCOL_CACHE[protocolId] = protocol;
      }

      // -------------------------
      // Session card
      // -------------------------
      const li = document.createElement("li");
      li.className = "session-card";

      // Header
      const header = document.createElement("div");
      header.className = "session-header";

      const title = document.createElement("div");
      title.className = "session-title";
      title.textContent = protocol.name;

      header.appendChild(title);
      li.appendChild(header);

      // Subjects
      const subjectsWrap = document.createElement("div");
      subjectsWrap.className = "subject-tags";

      runs.forEach(r => {
        const pill = document.createElement("span");
        pill.className = "subject-tag";
        pill.textContent = r.subject_name;
        subjectsWrap.appendChild(pill);
      });

      li.appendChild(subjectsWrap);

      // -------------------------
      // Action (START / STOP)
      // -------------------------
      const actions = document.createElement("div");
      actions.className = "session-actions";

      const btn = document.createElement("button");

      const isRunningHere =
        activeRun && activeRun.session_id === s.session_id;

      const isPilotBusy =
        activeRun && activeRun.session_id !== s.session_id;

      // -------- STOP --------
      if (isRunningHere) {
        btn.className = "button-danger";
        btn.textContent = "STOP";

        btn.onclick = async () => {
          btn.disabled = true;
          status.textContent = "Stopping run…";

          try {
            await fetch(`/api/session-runs/${activeRun.id}/stop`, {
              method: "POST",
            });
          } catch (err) {
            console.error(err);
            btn.disabled = false;
          }
        };

      // -------- START --------
      } else {
        btn.className = "button-primary";
        btn.textContent = "START";

        if (isPilotBusy) {
          btn.disabled = true;
          btn.title = "Another session is running on this pilot";
        }

        btn.onclick = async () => {
          if (isPilotBusy) return;

          btn.disabled = true;
          status.textContent = "Starting session…";

          try {
            const r = await fetch(
              `/api/sessions/${s.session_id}/start-on-pilot`,
              {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({ pilot_id: pilotId }),
              }
            );

            if (!r.ok) throw new Error(await r.text());

            // 🔑 Go back to pilot overview
            window.location.href = "/";
          } catch (err) {
            console.error(err);
            btn.disabled = false;
            status.textContent = "Failed to start session";
          }
        };
      }

      actions.appendChild(btn);
      li.appendChild(actions);
      ul.appendChild(li);

    } catch (err) {
      console.error("Failed to render session", s, err);
    }
  }
}

// --------------------------------------------------
// Init
// --------------------------------------------------
(async function init() {
  try {
    await loadPilotId();
    await loadSessions();
    initPilotWebSocket();
  } catch (err) {
    console.error(err);
    document.getElementById("status").textContent = err.message;
  }
})();
