function norm(s) {
  return String(s || "").trim().toLowerCase();
}

function escapeHtml(s) {
  return String(s || "").replace(/[&<>"']/g, (c) => ({
    "&": "&amp;",
    "<": "&lt;",
    ">": "&gt;",
    '"': "&quot;",
    "'": "&#39;"
  }[c]));
}


function getGraduationN(gr) {
  if (!gr) return null;

  if (typeof gr === "number") return Number.isFinite(gr) ? gr : null;

  if (typeof gr === "string") {
    const s = gr.trim();
    if (/^\d+$/.test(s)) return Number(s);
    return null;
  }

  if (typeof gr !== "object") return null;

  const v = gr.value ?? gr;
  const n = v?.current_trial ?? v?.n_trials ?? v?.n ?? null;
  if (n == null) return null;

  const nn = Number(n);
  return Number.isFinite(nn) ? nn : null;
}

// must exist before showSessionOverridesModal runs
async function loadTasksOnce() {
  if (TASKS_BY_NAME) return;
  const r = await fetch("/api/tasks/leaf");
  if (!r.ok) throw new Error("Failed to load tasks");
  const tasks = await r.json();
  TASKS_BY_NAME = new Map(tasks.map(t => [norm(t.task_name), t]));
}

const PROTOCOL_CACHE = {};
async function fetchProtocolCached(protocolId) {
  if (PROTOCOL_CACHE[protocolId]) return PROTOCOL_CACHE[protocolId];
  const r = await fetch(`/api/protocols/${protocolId}`);
  if (!r.ok) return null;
  const data = await r.json();
  PROTOCOL_CACHE[protocolId] = data;
  return data;
}

// ===== EXPOSE HELPERS FOR MODAL =====
window.fetchProtocolCached = fetchProtocolCached;
window.loadTasksOnce = loadTasksOnce;



function getValCI(obj, key) {
  if (!obj) return undefined;
  const nk = norm(key);
  for (const k of Object.keys(obj)) {
    if (norm(k) === nk) return obj[k];
  }
  return undefined;
}

function getSpecCI(specObj, key) {
  if (!specObj) return {};
  const nk = norm(key);
  for (const k of Object.keys(specObj)) {
    if (norm(k) === nk) return specObj[k] || {};
  }
  return {};
}

function getSpecDefaultValue(spec) {
  if (!spec || typeof spec !== "object") return undefined;
  return spec.value ?? spec.default ?? spec.default_value;
}

function isPopulatedValue(v) {
  if (v === undefined || v === null) return false;
  if (typeof v === "string" && v.trim() === "") return false;
  if (typeof v === "object" && !Array.isArray(v) && Object.keys(v).length === 0) return false;
  return true;
}

function sanitizeStepTitle(stepName, idx, taskType) {
  const stepNum = idx + 1;
  let s = String(stepName || "").trim();
  s = s.replace(/^step\s*\d+\s*[:\-–]?\s*/i, "").trim();
  const label = s || String(taskType || "").trim() || "Unnamed step";
  const tt = String(taskType || "").trim();
  const clean = tt && label.toLowerCase() === tt.toLowerCase() ? tt : label;
  return `Step ${stepNum}: ${clean}`.trim();
}

function formatAny(v) {
  if (v == null) return "";
  if (typeof v === "string") return v;
  if (typeof v === "number" || typeof v === "boolean") return String(v);
  try { return JSON.stringify(v); } catch { return String(v); }
}

function pickParamSpec(task) {
  if (!task || typeof task !== "object") return {};
  return (
    task.default_params ||
    task.defaultParams ||
    task.params ||
    task.parameters ||
    task.param_specs ||
    task.paramSpecs ||
    task.param_spec ||
    task.paramSpec ||
    task.schema ||
    {}
  );
}


window.showSessionOverridesModal = function showSessionOverridesModal(sessionId, protocolId) {
  return new Promise((resolve) => {
    let done = false;

    const finish = () => {
      if (done) return;
      done = true;
      document.removeEventListener("keydown", onKeyDown, true);
      overlay.remove();
      resolve();
    };

    const onKeyDown = (e) => {
      if (e.key === "Escape") {
        e.preventDefault();
        finish();
      }
    };

    if (!OVERRIDES_DRAFT[sessionId]) OVERRIDES_DRAFT[sessionId] = { steps: {} };
    if (!OVERRIDES_DRAFT[sessionId].steps) OVERRIDES_DRAFT[sessionId].steps = {};

    const overlay = document.createElement("div");
    overlay.className = "modal-overlay";
    overlay.setAttribute("role", "dialog");
    overlay.setAttribute("aria-modal", "true");

    const modal = document.createElement("div");
    modal.className = "modal overrides-modal";
    modal.style.maxWidth = "1080px";
    modal.style.width = "min(1080px, calc(100vw - 24px))";

    modal.innerHTML = `
      <div class="modal-header">
        <div class="modal-title">Session ${sessionId}</div>
        <button class="modal-close" type="button">✕</button>
      </div>

      <div class="modal-tabs">
        <button class="modal-tab active" data-tab="overrides">Overrides</button>
        <button class="modal-tab" data-tab="history">Run History</button>
      </div>

      <div class="modal-body">
        <div id="tab-overrides"></div>
        <div id="tab-history" hidden></div>
      </div>

      <div class="modal-actions ov-actions">
        <button class="button-primary" type="button" id="ovDone">Apply overrides</button>
      </div>
    `;

    overlay.appendChild(modal);
    document.body.appendChild(overlay);

    modal.querySelector(".modal-close").onclick = finish;
    modal.querySelector("#ovDone").onclick = finish;
    overlay.addEventListener("mousedown", (e) => { if (e.target === overlay) finish(); });
    document.addEventListener("keydown", onKeyDown, true);

    const overridesContainer = modal.querySelector("#tab-overrides");
    const historyContainer = modal.querySelector("#tab-history");

    // ===============================
    // TAB SWITCHING
    // ===============================
    const actionsBar = modal.querySelector(".modal-actions");

    modal.querySelectorAll(".modal-tab").forEach(btn => {
      btn.addEventListener("click", () => {
        modal.querySelectorAll(".modal-tab").forEach(b => b.classList.remove("active"));
        btn.classList.add("active");

        if (btn.dataset.tab === "overrides") {
          overridesContainer.hidden = false;
          historyContainer.hidden = true;
          actionsBar.hidden = false;   // ✅ show action bar
        } else {
          overridesContainer.hidden = true;
          historyContainer.hidden = false;
          actionsBar.hidden = true;    // ✅ hide entire action bar
          renderRunHistory();
        }
      });
    });



    async function renderRunHistory() {
      try {
        const r = await fetch(
          `/api/sessions/${sessionId}/pilots/${window.pilotId}/runs`
        );
    
        if (!r.ok) throw new Error(`HTTP ${r.status}`);
        const runs = await r.json();
    
        if (!runs.length) {
          historyContainer.innerHTML = "<div class='muted'>No runs yet</div>";
          return;
        }
    
        historyContainer.innerHTML = `
          <table class="runs-table">
            <tr>
              <th>ID</th>
              <th>Index</th>
              <th>Status</th>
              <th>Mode</th>
              <th>Started</th>
              <th>Ended</th>
            </tr>
            ${runs.map(r => `
              <tr>
                <td>${r.id}</td>
                <td>${r.session_run_index}</td>
                <td><span class="run-status run-status-${r.status}">${r.status}</span></td>
                <td>${r.mode}</td>
                <td>${r.started_at || ""}</td>
                <td>${r.ended_at || ""}</td>
              </tr>
            `).join("")}
          </table>
        `;
      } catch (err) {
        console.error("Run history error:", err);
        historyContainer.innerHTML =
          "<div class='muted'>Failed to load run history</div>";
      }
    }
    
    // ===============================
    // EXISTING OVERRIDES RENDERING
    // ===============================
    (async () => {
      try {
        if (!TASKS_BY_NAME) await loadTasksOnce();
        const protocol = await fetchProtocolCached(protocolId);
        const steps = protocol?.steps || [];

        overridesContainer.innerHTML = "";

        // --- Replace the existing steps.forEach(...) block with this ---
steps.forEach((step, idx) => {
  const task = TASKS_BY_NAME?.get(norm(step.task_type));
  const specObj = pickParamSpec(task) || {};
  const protocolParams = step.params || {};

  const keyNormToKey = new Map();
  Object.keys(specObj || {}).forEach(k => keyNormToKey.set(norm(k), k));
  Object.keys(protocolParams || {}).forEach(k => keyNormToKey.set(norm(k), k));

  const keys = Array.from(keyNormToKey.values())
    .filter(k => !["step_name", "task_type"].includes(norm(k)))
    .sort((a,b)=>a.localeCompare(b));

  // create box
  const box = document.createElement("div");
  box.className = "step-box";

  // initial open state: first step open, others closed
  const isOpenByDefault = idx === 0;

  box.innerHTML = `
    <div class="step-head" role="button" aria-expanded="${isOpenByDefault}" style="cursor:pointer;">
      <div style="min-width:0;">
        <div class="step-name">
          ${escapeHtml(sanitizeStepTitle(step.step_name, idx, step.task_type))}
        </div>
      </div>
      <button class="button-secondary step-toggle-btn" type="button" aria-label="Toggle step">
        ${isOpenByDefault ? "▾" : "▸"}
      </button>
    </div>

    <div class="step-section" style="display:${isOpenByDefault ? "block" : "none"};">
      <div class="params-grid params-grid-2col"></div>
    </div>
  `;

  const section = box.querySelector(".step-section");
  const grid = box.querySelector(".params-grid");
  const toggleBtn = box.querySelector(".step-toggle-btn");
  const head = box.querySelector(".step-head");

    // populate params into the grid
    keys.forEach((key) => {
      const spec = getSpecCI(specObj, key) || {};
      const protocolVal = getValCI(protocolParams, key);
      const defaultVal = getSpecDefaultValue(spec);
      const displayVal = isPopulatedValue(protocolVal) ? protocolVal : defaultVal;

      const field = document.createElement("div");
      field.className = "param-field";

      const label = document.createElement("label");
      // wrap the name in a span to keep truncation behavior consistent with CSS
      label.innerHTML = `<span class="param-name">${escapeHtml(String(key))}</span><span class="param-src param-src-default" aria-hidden="true"></span>`;

      const input = document.createElement("input");
      input.type = "text";

      const stepIdxStr = String(idx);

      if (norm(key) === "graduation") {
        const n = getGraduationN(displayVal);
        input.value = n == null ? "" : String(n);
      } else {
        input.value = formatAny(displayVal ?? "");
      }

      // 🔥 THIS WAS MISSING — write overrides
      input.addEventListener("input", (e) => {
        const raw = input.value;
        const draft = OVERRIDES_DRAFT[sessionId].steps;

        draft[stepIdxStr] = draft[stepIdxStr] || {};

        // mark dirty
        if (window.OVERRIDES_DIRTY) {
          window.OVERRIDES_DIRTY[sessionId] = true;
        }

        if (raw.trim() === "") {
          delete draft[stepIdxStr][key];
          return;
        }

        if (norm(key) === "graduation") {
          if (/^\d+$/.test(raw.trim())) {
            draft[stepIdxStr][key] = {
              type: "NTrials",
              value: { current_trial: Number(raw.trim()) }
            };
          }
          return;
        }

        draft[stepIdxStr][key] = raw;
      });


      field.appendChild(label);
      field.appendChild(input);
      grid.appendChild(field);
    });

    // toggle helper
    let open = isOpenByDefault;
    function setOpen(v) {
      open = !!v;
      section.style.display = open ? "block" : "none";
      toggleBtn.textContent = open ? "▾" : "▸";
      // keep accessible state
      head.setAttribute("aria-expanded", String(open));
    }

    // wire toggle button and header click (both toggle)
    toggleBtn.addEventListener("click", (e) => {
      e.stopPropagation();
      setOpen(!open);
    });

    head.addEventListener("click", (e) => {
      // if the user clicked the actual input inside the header, ignore
      if (e.target && (e.target.tagName === "INPUT" || e.target.tagName === "BUTTON")) return;
      setOpen(!open);
    });

    // finally append box to container (this was missing before)
    overridesContainer.appendChild(box);
  });


      } catch (e) {
        overridesContainer.innerHTML =
          `<div class="muted">Failed to load overrides UI</div>`;
      }
    })();
  });
};
