const grid = document.getElementById("pilots");

const ws = new WebSocket(`ws://${location.host}/ws/pilots`);

// 🔑 Change-detection cache
let LAST_PILOTS_HASH = null;

ws.onmessage = (event) => {
  let data;

  try {
    data = JSON.parse(event.data);
  } catch (e) {
    console.error("Invalid WS payload", e);
    return;
  }

  // 🔑 Treat empty payload as "all offline"
  if (!data || Object.keys(data).length === 0) {
    data = {};
  }

  // 🔑 Prevent re-render if nothing changed
  const hash = JSON.stringify(data);
  if (hash === LAST_PILOTS_HASH) {
    return;
  }
  LAST_PILOTS_HASH = hash;

  renderPilots(data);
};

ws.onerror = (err) => {
  console.error("WebSocket error:", err);
};

/**
 * Render pilot cards
 * Redis-backed truth:
 *  - connected
 *  - state
 *  - active_run
 */
function renderPilots(pilots) {
  grid.innerHTML = "";

  Object.entries(pilots).forEach(([name, info]) => {
    const connected = info.connected === true;
    const state = info.state ?? "UNKNOWN";
    const run = info.active_run ?? null;

    const card = document.createElement("div");
    card.className = "card pilot-card";

    // -------------------------
    // Connectivity handling
    // -------------------------
    if (!connected) {
      card.classList.add("pilot-offline");
    }

    if (state === "RUNNING") {
      card.classList.add("pilot-running");
    } else {
      card.classList.add("pilot-idle");
    }

    // Prevent navigation if offline
    if (connected) {
      card.onclick = () => {
        window.location.href = `/pilots/${name}/sessions-ui`;
      };
    }

    // -------------------------
    // Header
    // -------------------------
    const title = document.createElement("h2");
    title.textContent = name;

    const status = document.createElement("div");
    status.className = "status";

    if (!connected) {
      status.textContent = "OFFLINE";
      status.classList.add("pilot-offline-badge");
    } else {
      status.textContent = state;
      status.classList.add(
        state === "RUNNING" ? "connected" : "disconnected"
      );
    }

    card.appendChild(title);
    card.appendChild(status);

    // -------------------------
    // Active run (if running)
    // -------------------------
    if (connected && run) {
      const runBox = document.createElement("div");
      runBox.className = "status-line";

      let elapsed = "—";
      if (run.started_at) {
        // 🔑 UTC-safe elapsed time
        const started = Date.parse(run.started_at); // handles +00:00
        if (!isNaN(started)) {
          const sec = Math.max(
            0,
            Math.floor((Date.now() - started) / 1000)
          );
          const min = Math.floor(sec / 60);
          elapsed = `${min}m ${sec % 60}s`;
        }
      }

      runBox.innerHTML = `
        <strong>RUNNING</strong><br/>
        Session: ${run.session_id}<br/>
        Subject: ${run.subject_key ?? "—"}<br/>
        Time: ${elapsed}
      `;

      // -------------------------
      // STOP button
      // -------------------------
      const stopBtn = document.createElement("button");
      stopBtn.textContent = "STOP";
      stopBtn.className = "button-secondary";

      stopBtn.onclick = (e) => {
        e.stopPropagation(); // prevent navigation
        stopBtn.disabled = true;

        fetch(`/api/session-runs/${run.id}/stop`, {
          method: "POST",
        }).catch(() => {
          stopBtn.disabled = false;
        });
      };

      card.appendChild(runBox);
      card.appendChild(stopBtn);
    }

    grid.appendChild(card);
  });
}
