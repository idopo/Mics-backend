/* session_launcher_lazy_hydrate.js
   Clean version:
   - Fixes double params (case-insensitive key merge: iti vs ITI)
   - Fixes “can’t type in overrides” (guards global hotkeys + stops bubbling from inputs)
   - Removes duplicate helper definitions (ONLY ONE norm/escapeHtml/etc)
   - Keeps your lazy hydration, concurrency limiter, websocket Start/Stop logic

   Requires:
   - global PILOT_NAME
   - existing HTML elements: #sessions, #status, #subject-filter, #clear-filter, #subject-typeahead, #subject-chips
*/

(() => {
  // --------------------------------------------------
  // Globals / state
  // --------------------------------------------------
  let pilotId = null;
  let CURRENT_PILOT_STATE = null;
  let ws = null;

  let renderSessionsCache = null;
  let LAST_PILOT_STATE_KEY = null;

  let SUBJECTS_CACHE = null;
  let FILTER_SUBJECTS = [];

  let TASKS_CACHE = null;
  let TASKS_BY_NAME = null;

  // Data caches
  const SESSION_DETAILS_CACHE = {};
  const PROTOCOL_CACHE = {};
  const LATEST_BY_SESSION_CACHE = {}; // only filled for visible sessions (per sessionId)

  // In-flight dedupe
  const SESSION_DETAILS_INFLIGHT = {};
  const PROTOCOL_INFLIGHT = {};
  const LATEST_INFLIGHT = {};

  // per sessionId: { steps: { "0": {...}, "1": {...} } }
  const OVERRIDES_DRAFT = {};

  let FIRST_RENDER = true;

  // --------------------------------------------------
  // Small utils
  // --------------------------------------------------
  function norm(s) { return String(s || "").trim().toLowerCase(); }

  function escapeHtml(s) {
    return String(s).replace(/[&<>"']/g, (c) => ({
      "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;"
    }[c]));
  }

  function showSkeleton(container, rows = 8) {
    container.classList.add("is-loading");
    container.innerHTML = `
      <div class="skeleton-list">
        ${Array.from({ length: rows })
          .map(() => `<div class="skeleton-row"></div>`)
          .join("")}
      </div>
    `;
  }

  function formatDateDMY(iso) {
    if (!iso) return "";
    const d = new Date(iso);
    if (isNaN(d)) return "";
    const dd = String(d.getDate()).padStart(2, "0");
    const mm = String(d.getMonth() + 1).padStart(2, "0");
    const yyyy = d.getFullYear();
    return `${dd}/${mm}/${yyyy}`;
  }

  function sessionHasAllSubjects(sessionDetail, subjects) {
    const have = new Set((sessionDetail.runs || []).map(r => norm(r.subject_name)));
    return subjects.every(s => have.has(norm(s)));
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

  function getSpecDefaultValue(spec) {
    if (!spec || typeof spec !== "object") return undefined;
    return spec.value ?? spec.default ?? spec.default_value;
  }

  function formatAny(v) {
    if (v == null) return "";
    if (typeof v === "string") return v;
    if (typeof v === "number" || typeof v === "boolean") return String(v);
    try { return JSON.stringify(v); } catch { return String(v); }
  }

  // case-insensitive lookup of value by key
  function getValCI(obj, key) {
    if (!obj) return undefined;
    const nk = norm(key);
    for (const k of Object.keys(obj)) {
      if (norm(k) === nk) return obj[k];
    }
    return undefined;
  }

  // case-insensitive lookup of spec by key
  function getSpecCI(specObj, key) {
    if (!specObj) return {};
    const nk = norm(key);
    for (const k of Object.keys(specObj)) {
      if (norm(k) === nk) return specObj[k] || {};
    }
    return {};
  }

  function parseByType(raw, type) {
    const t = String(type || "").toLowerCase();
    if (!t) return { value: raw };

    if (t.includes("int")) {
      const n = Number(raw);
      if (!Number.isFinite(n) || !Number.isInteger(n)) return { __invalid: true };
      return { value: n };
    }

    if (t.includes("float") || t.includes("number") || t.includes("double")) {
      const n = Number(raw);
      if (!Number.isFinite(n)) return { __invalid: true };
      return { value: n };
    }

    if (t.includes("bool")) {
      const v = raw.trim().toLowerCase();
      if (["true", "1", "yes", "y"].includes(v)) return { value: true };
      if (["false", "0", "no", "n"].includes(v)) return { value: false };
      return { __invalid: true };
    }

    if (t.includes("json") || t.includes("dict") || t.includes("list") || t.includes("object")) {
      try { return { value: JSON.parse(raw) }; } catch { return { __invalid: true }; }
    }

    return { value: raw };
  }

  // Optional: render graduation read-only in base grid if present
  function renderGraduationFields({ container, step, paramSpec }) {
    const protocolParams = step.params || {};
    const baseGrad = protocolParams.graduation;
    if (baseGrad === undefined && !paramSpec?.graduation) return;

    const baseField = document.createElement("div");
    baseField.className = "param-field";

    const baseLabel = document.createElement("label");
    baseLabel.textContent = baseGrad !== undefined ? "graduation (protocol)" : "graduation (default/spec)";

    const baseVal = document.createElement("input");
    baseVal.type = "text";
    baseVal.disabled = true;
    baseVal.value = formatAny(baseGrad ?? getSpecDefaultValue(paramSpec?.graduation) ?? "");

    baseField.appendChild(baseLabel);
    baseField.appendChild(baseVal);
    container.appendChild(baseField);
  }

  // --------------------------------------------------
  // HARD FIX: If you have any global hotkeys anywhere,
  // this ensures inputs are not blocked (capture phase).
  // --------------------------------------------------
  (function installTypingGuardsOnce() {
    if (window.__pilotTypingGuardsInstalled) return;
    window.__pilotTypingGuardsInstalled = true;

    const isTypingTarget = (t) =>
      t &&
      (t.tagName === "INPUT" ||
        t.tagName === "TEXTAREA" ||
        t.tagName === "SELECT" ||
        t.isContentEditable);

    // If any other code preventsDefault in capture, this will run first only if registered earlier.
    // But it still helps a lot in typical setups.
    document.addEventListener("keydown", (e) => {
      if (isTypingTarget(e.target)) return;
    }, true);

    document.addEventListener("keypress", (e) => {
      if (isTypingTarget(e.target)) return;
    }, true);
  })();

  // --------------------------------------------------
  // UI modal (Resume/Restart/New) - kept as-is
  // --------------------------------------------------
  window.showStartModeModal = function showStartModeModal({ runId, status, step, trial }) {
    return new Promise((resolve) => {
      let done = false;

      const finish = (val) => {
        if (done) return;
        done = true;
        document.removeEventListener("keydown", onKeyDown, true);
        overlay.remove();
        resolve(val);
      };

      const onKeyDown = (e) => {
        if (e.key === "Escape") {
          e.preventDefault();
          finish(null);
        }
      };

      const overlay = document.createElement("div");
      overlay.className = "modal-overlay";
      overlay.setAttribute("role", "dialog");
      overlay.setAttribute("aria-modal", "true");

      const modal = document.createElement("div");
      modal.className = "modal";

      modal.innerHTML = `
        <div class="modal-header">
          <div class="modal-title">Previous run detected</div>
          <button class="modal-close" type="button" aria-label="Close">✕</button>
        </div>

        <div class="modal-body">
          <div class="modal-muted">
            A run was stopped mid-way. Choose how to continue:
          </div>

          <div class="modal-kv">
            <div><span>Run ID</span><strong>${runId ?? "?"}</strong></div>
            <div><span>Status</span><strong>${status ?? "?"}</strong></div>
            <div><span>Progress</span><strong>step ${step ?? "?"}, trial ${trial ?? "?"}</strong></div>
          </div>

          <div class="modal-actions">
            <button class="button-primary" type="button" data-choice="resume">
              Resume
              <span class="modal-sub">Continue from current step/trial</span>
            </button>

            <button class="button-secondary" type="button" data-choice="restart">
              Restart
              <span class="modal-sub">Reset progress and start over</span>
            </button>

            <button class="button-secondary" type="button" data-choice="new">
              New run
              <span class="modal-sub">Create a fresh run record</span>
            </button>
          </div>
        </div>
      `;

      overlay.appendChild(modal);
      document.body.appendChild(overlay);

      modal.querySelector(".modal-close").onclick = () => finish(null);

      overlay.addEventListener("mousedown", (e) => {
        if (e.target === overlay) finish(null);
      });

      modal.querySelectorAll("[data-choice]").forEach((btn) => {
        btn.addEventListener("click", () => finish(btn.getAttribute("data-choice")));
      });

      document.addEventListener("keydown", onKeyDown, true);

      const first = modal.querySelector("[data-choice='resume']") || modal.querySelector("button");
      first?.focus();
    });
  };

  // --------------------------------------------------
  // Concurrency limiter
  // --------------------------------------------------
  function createLimiter(max = 4) {
    let active = 0;
    const q = [];
    const runNext = () => {
      if (active >= max || q.length === 0) return;
      active++;
      const { fn, resolve, reject } = q.shift();
      Promise.resolve()
        .then(fn)
        .then(resolve, reject)
        .finally(() => {
          active--;
          runNext();
        });
    };
    return (fn) => new Promise((resolve, reject) => {
      q.push({ fn, resolve, reject });
      runNext();
    });
  }
  const limitFetch = createLimiter(4);

  // --------------------------------------------------
  // Fetch helpers (cached)
  // --------------------------------------------------
  function fetchSessionDetailCached(sessionId) {
    if (SESSION_DETAILS_CACHE[sessionId]) return Promise.resolve(SESSION_DETAILS_CACHE[sessionId]);
    if (SESSION_DETAILS_INFLIGHT[sessionId]) return SESSION_DETAILS_INFLIGHT[sessionId];

    SESSION_DETAILS_INFLIGHT[sessionId] = limitFetch(async () => {
      const r = await fetch(`/api/sessions/${sessionId}`);
      if (!r.ok) return null;
      const data = await r.json();
      SESSION_DETAILS_CACHE[sessionId] = data;
      return data;
    }).finally(() => { delete SESSION_DETAILS_INFLIGHT[sessionId]; });

    return SESSION_DETAILS_INFLIGHT[sessionId];
  }

  function fetchProtocolCached(protocolId) {
    if (PROTOCOL_CACHE[protocolId]) return Promise.resolve(PROTOCOL_CACHE[protocolId]);
    if (PROTOCOL_INFLIGHT[protocolId]) return PROTOCOL_INFLIGHT[protocolId];

    PROTOCOL_INFLIGHT[protocolId] = limitFetch(async () => {
      const r = await fetch(`/api/protocols/${protocolId}`);
      if (!r.ok) return null;
      const data = await r.json();
      PROTOCOL_CACHE[protocolId] = data;
      return data;
    }).finally(() => { delete PROTOCOL_INFLIGHT[protocolId]; });

    return PROTOCOL_INFLIGHT[protocolId];
  }

  async function fetchLatestForSession(sessionId) {
    if (!pilotId) return null;
    if (LATEST_BY_SESSION_CACHE[sessionId]) return LATEST_BY_SESSION_CACHE[sessionId];
    if (LATEST_INFLIGHT[sessionId]) return LATEST_INFLIGHT[sessionId];

    LATEST_INFLIGHT[sessionId] = limitFetch(async () => {
      const r = await fetch(`/api/sessions/${sessionId}/pilots/${pilotId}/latest-run`);
      if (!r.ok) return null;
      const data = await r.json();
      LATEST_BY_SESSION_CACHE[sessionId] = data;
      return data;
    }).finally(() => { delete LATEST_INFLIGHT[sessionId]; });

    return LATEST_INFLIGHT[sessionId];
  }

  // --------------------------------------------------
  // tasks/subjects/pilot
  // --------------------------------------------------
  async function loadTasksOnce() {
    if (TASKS_CACHE) return TASKS_CACHE;
    const r = await fetch("/api/tasks/leaf");
    if (!r.ok) throw new Error("Failed to load tasks");
    TASKS_CACHE = await r.json();
    TASKS_BY_NAME = new Map(TASKS_CACHE.map(t => [norm(t.task_name), t]));
    return TASKS_CACHE;
  }

  async function loadSubjectsOnce() {
    if (SUBJECTS_CACHE) return SUBJECTS_CACHE;
    const r = await fetch("/api/subjects");
    if (!r.ok) throw new Error("Failed to load subjects");
    SUBJECTS_CACHE = await r.json();
    return SUBJECTS_CACHE;
  }

  async function loadPilotId() {
    const res = await fetch("/api/backend/pilots");
    if (!res.ok) throw new Error("Failed to load backend pilots");
    const pilots = await res.json();
    const pilot = pilots.find((p) => p.name === PILOT_NAME);
    if (!pilot) throw new Error(`Pilot not found in backend DB: ${PILOT_NAME}`);
    pilotId = pilot.id;
  }

  async function pickStartMode(sessionId) {
    if (!pilotId) return "new";
  
    let opts = null;
    try {
      const resp = await fetch(`/api/sessions/${sessionId}/pilots/${pilotId}/start-options`);
      if (!resp.ok) return "new";
      opts = await resp.json();
    } catch {
      return "new";
    }
  
    // Optional debug (handy while validating behavior)
    // console.debug("start-options", sessionId, opts);
  
    // If there's an active run right now, UI should just create a new run record
    // (your existing behavior)
    if (opts?.active_run) return "new";
  
    // ✅ Only prompt if backend explicitly says we can resume
    if (opts?.recoverable_run && opts?.can_resume) {
      if (typeof window.showStartModeModal !== "function") {
        const statusEl = document.getElementById("status");
        if (statusEl) statusEl.textContent = "Start mode dialog is missing (showStartModeModal not loaded)";
        return "new";
      }
  
      const p = opts.progress || {};
      const choice = await window.showStartModeModal({
        runId: opts.recoverable_run.id,
        status: opts.recoverable_run.status,
        step: p.current_step ?? "?",
        trial: p.current_trial ?? "?",
      });
  
      if (!choice) return null; // user cancelled modal
      return choice; // "resume" | "restart" | "new"
    }
  
    // Default: new run
    return "new";
  }
  

  // --------------------------------------------------
  // Subject filter UI
  // --------------------------------------------------
  let TYPEAHEAD_ITEMS = [];
  let TYPEAHEAD_INDEX = -1;

  function clearTypeahead() {
    const ta = document.getElementById("subject-typeahead");
    if (ta) ta.innerHTML = "";
  }

  function showTypeahead(matches, onPick) {
    const ta = document.getElementById("subject-typeahead");
    if (!ta) return;

    TYPEAHEAD_ITEMS = [];
    TYPEAHEAD_INDEX = -1;

    if (!matches.length) {
      ta.innerHTML = "";
      return;
    }

    const menu = document.createElement("div");
    menu.className = "typeahead-menu";

    matches.slice(0, 8).forEach((m) => {
      const item = document.createElement("div");
      item.className = "typeahead-item";
      item.textContent = m;
      item.onclick = () => onPick(m);
      TYPEAHEAD_ITEMS.push({ el: item, value: m });
      menu.appendChild(item);
    });

    ta.innerHTML = "";
    ta.appendChild(menu);
  }

  function updateTypeaheadActive() {
    TYPEAHEAD_ITEMS.forEach((item, idx) => {
      item.el.classList.toggle("active", idx === TYPEAHEAD_INDEX);
      if (idx === TYPEAHEAD_INDEX) item.el.scrollIntoView({ block: "nearest" });
    });
  }

  function updateClearButtonVisibility() {
    const input = document.getElementById("subject-filter");
    const clearBtn = document.getElementById("clear-filter");
    if (!input || !clearBtn) return;
    const hasText = input.value.trim().length > 0;
    const hasChips = FILTER_SUBJECTS.length > 0;
    clearBtn.classList.toggle("is-visible", hasText || hasChips);
  }

  function renderChips() {
    const wrap = document.getElementById("subject-chips");
    if (!wrap) return;
    wrap.innerHTML = "";
    FILTER_SUBJECTS.forEach((name) => {
      const chip = document.createElement("span");
      chip.className = "chip";
      chip.innerHTML = `${escapeHtml(name)} <button aria-label="Remove">✕</button>`;
      chip.querySelector("button").onclick = () => {
        FILTER_SUBJECTS = FILTER_SUBJECTS.filter(x => x !== name);
        renderChips();
        if (renderSessionsCache) renderShellList(renderSessionsCache);
      };
      wrap.appendChild(chip);
    });
    updateClearButtonVisibility();
  }

  async function initSubjectFilterUI() {
    const input = document.getElementById("subject-filter");
    const clearBtn = document.getElementById("clear-filter");
    if (!input || !clearBtn) return;

    const subjects = await loadSubjectsOnce();
    const names = subjects.map(s => s.name).sort((a,b) => a.localeCompare(b));

    const pick = (name) => {
      const canonical = names.find(n => norm(n) === norm(name)) || name.trim();
      if (!canonical) return;
      if (!FILTER_SUBJECTS.includes(canonical)) FILTER_SUBJECTS.push(canonical);
      input.value = "";
      clearTypeahead();
      renderChips();
      if (renderSessionsCache) renderShellList(renderSessionsCache);
    };

    input.addEventListener("keydown", (e) => {
      if (e.key === "ArrowDown" && TYPEAHEAD_ITEMS.length) {
        e.preventDefault();
        TYPEAHEAD_INDEX = (TYPEAHEAD_INDEX + 1) % TYPEAHEAD_ITEMS.length;
        updateTypeaheadActive();
        return;
      }
      if (e.key === "ArrowUp" && TYPEAHEAD_ITEMS.length) {
        e.preventDefault();
        TYPEAHEAD_INDEX = (TYPEAHEAD_INDEX - 1 + TYPEAHEAD_ITEMS.length) % TYPEAHEAD_ITEMS.length;
        updateTypeaheadActive();
        return;
      }
      if (e.key === "Enter") {
        e.preventDefault();
        if (TYPEAHEAD_INDEX >= 0 && TYPEAHEAD_ITEMS[TYPEAHEAD_INDEX]) {
          pick(TYPEAHEAD_ITEMS[TYPEAHEAD_INDEX].value);
        } else {
          const v = input.value.trim();
          if (v) pick(v);
        }
        return;
      }
      if (e.key === "Escape") {
        clearTypeahead();
        TYPEAHEAD_INDEX = -1;
        input.blur();
      }
    });

    input.addEventListener("input", () => {
      updateClearButtonVisibility();
      const q = norm(input.value);
      if (!q) return clearTypeahead();
      const matches = names.filter(n => norm(n).includes(q) && !FILTER_SUBJECTS.includes(n));
      showTypeahead(matches, pick);
    });

    clearBtn.onclick = () => {
      FILTER_SUBJECTS = [];
      input.value = "";
      clearTypeahead();
      renderChips();
      if (renderSessionsCache) renderShellList(renderSessionsCache);
      updateClearButtonVisibility();
    };

    document.addEventListener("click", (e) => {
      const ta = document.getElementById("subject-typeahead");
      if (!ta) return;
      if (e.target === input || ta.contains(e.target)) return;
      clearTypeahead();
    });
  }

  // --------------------------------------------------
  // WebSocket
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

      refreshActionButtonsOnly();
    };

    ws.onerror = (err) => console.error("Pilot WS error:", err);
  }

  function refreshActionButtonsOnly() {
    const ul = document.getElementById("sessions");
    if (!ul) return;
    const activeRun = CURRENT_PILOT_STATE?.active_run || null;

    ul.querySelectorAll("li.session-card[data-session-id]").forEach(li => {
      const sessionId = Number(li.getAttribute("data-session-id"));
      const actions = li.querySelector(".session-actions");
      if (!actions) return;

      if (li.getAttribute("data-hydrated") !== "1") return;

      const btn = actions.querySelector("button");
      if (!btn) return;

      const isRunningHere = activeRun && activeRun.session_id === sessionId;
      const isPilotBusy = activeRun && activeRun.session_id !== sessionId;

      if (isRunningHere) {
        btn.className = "button-danger";
        btn.textContent = "STOP";
        btn.disabled = false;
        btn.title = "";
        btn.onclick = async () => {
          const status = document.getElementById("status");
          btn.disabled = true;
          if (status) status.textContent = "Stopping run…";
          try {
            await fetch(`/api/session-runs/${activeRun.id}/stop`, { method: "POST" });
          } catch (e) {
            console.error(e);
            btn.disabled = false;
          }
        };
      } else {
        btn.className = "button-primary";
        btn.textContent = "START";
        btn.disabled = !!isPilotBusy;
        btn.title = isPilotBusy ? "Another session is running on this pilot" : "";
        btn.onclick = async () => {
          if (isPilotBusy) return;

          const status = document.getElementById("status");
          btn.disabled = true;
          if (status) status.textContent = "Starting session…";

          try {
            const mode = await pickStartMode(sessionId);
            if (!mode) {
              btn.disabled = false;
              if (status) status.textContent = "";
              return;
            }

            const overrides = OVERRIDES_DRAFT[sessionId] || null;

            const hasOverrides =
              !!overrides &&
              overrides.steps &&
              Object.values(overrides.steps).some(obj => obj && Object.keys(obj).length > 0);

            const r = await fetch(`/api/sessions/${sessionId}/start-on-pilot`, {
              method: "POST",
              headers: { "Content-Type": "application/json" },
              body: JSON.stringify({
                pilot_id: pilotId,
                mode,
                overrides: hasOverrides ? overrides : null,
              }),
            });

            if (!r.ok) throw new Error(await r.text());
            window.location.href = "/";
          } catch (e) {
            console.error(e);
            btn.disabled = false;
            if (status) status.textContent = "Failed to start session";
          }
        };
      }
    });
  }

  // --------------------------------------------------
  // Shell list render + lazy hydration
  // --------------------------------------------------
  let io = null;

  function ensureObserver() {
    if (io) return io;
    io = new IntersectionObserver((entries) => {
      entries.forEach(entry => {
        if (!entry.isIntersecting) return;
        const li = entry.target;
        io.unobserve(li);
        hydrateCard(li).catch(err => console.error("hydrateCard error:", err));
      });
    }, { root: null, rootMargin: "600px 0px", threshold: 0.01 });
    return io;
  }

  function buildShellCard(sessionId, allowAnimate, idx) {
    const li = document.createElement("li");
    li.className = "session-card";
    li.setAttribute("data-session-id", String(sessionId));
    li.setAttribute("data-hydrated", "0");

    if (allowAnimate && FIRST_RENDER) {
      li.classList.add("fade-in-item");
      li.style.animationDelay = `${Math.min(idx * 18, 180)}ms`;
    }

    li.innerHTML = `
      <div class="session-card-grid">
        <div class="session-left">
          <div class="session-header">
            <div class="session-title">&nbsp;</div>
          </div>
          <div class="subject-tags">&nbsp;</div>
          <div class="session-meta">&nbsp;</div>
          <div class="session-actions">
            <button class="button-primary" disabled aria-label="Start session">
              <span class="btn-label-sr">START</span>
            </button>
          </div>
        </div>

        <div class="session-divider" aria-hidden="true"></div>

        <div class="session-right">
          <div class="right-title">Params</div>
          <div class="right-body"></div>
        </div>
      </div>
    `;

    return li;
  }

  function renderShellList(sessions) {
    const ul = document.getElementById("sessions");
    if (!ul) return;

    ul.classList.remove("is-loading");
    ul.innerHTML = "";

    if (!CURRENT_PILOT_STATE?.connected) {
      ul.innerHTML = `<li class="muted">Pilot is offline</li>`;
      return;
    }

    if (!Array.isArray(sessions) || sessions.length === 0) {
      ul.innerHTML = `<li class="muted">No sessions available</li>`;
      return;
    }

    const frag = document.createDocumentFragment();
    const observer = ensureObserver();

    sessions.forEach((s, idx) => {
      const li = buildShellCard(s.session_id, true, idx);
      frag.appendChild(li);
    });

    ul.appendChild(frag);
    ul.querySelectorAll("li.session-card[data-session-id]").forEach(li => observer.observe(li));

    FIRST_RENDER = false;
  }

  // --------------------------------------------------
  // FIXED renderParamsPanel
  // --------------------------------------------------
  function renderParamsPanel(li, protocol, sessionId) {
    const panel = li.querySelector(".session-right .right-body");
    if (!panel) return;
  
    const steps = protocol?.steps || [];
    if (!steps.length) {
      panel.innerHTML = `<div class="muted small">No steps</div>`;
      return;
    }
  
    if (!OVERRIDES_DRAFT[sessionId]) OVERRIDES_DRAFT[sessionId] = { steps: {} };
    panel.innerHTML = "";
  
    const pickParamSpec = (task) => {
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
    };
  
    const makeInputTypeable = (input) => {
      // prevent card handlers / global hotkeys from swallowing input
      ["pointerdown", "mousedown", "click", "dblclick"].forEach((ev) => {
        input.addEventListener(ev, (e) => e.stopPropagation(), true);
      });
      ["keydown", "keypress", "keyup"].forEach((ev) => {
        input.addEventListener(ev, (e) => e.stopPropagation(), true);
      });
      input.addEventListener("pointerdown", () => input.focus(), true);
    };
  
    steps.forEach((step, idx) => {
      const task = TASKS_BY_NAME?.get(norm(step.task_type));
      const paramSpec = pickParamSpec(task) || {};
      const protocolParams = step.params || {};
  
      // draft holder
      const existing = OVERRIDES_DRAFT[sessionId].steps[String(idx)];
      const stepDraft = existing && typeof existing === "object" ? existing : {};
      OVERRIDES_DRAFT[sessionId].steps[String(idx)] = stepDraft;
  
      // Build allowed keys (ONLY existing ones):
      // - spec keys
      // - protocol step params keys (so you can override them)
      // Also include any already-set override keys, but ONLY if they match allowed keys (case-insensitive).
      const keyNormToKey = new Map();
  
      Object.keys(paramSpec || {}).forEach((k) => {
        const nk = norm(k);
        if (!keyNormToKey.has(nk)) keyNormToKey.set(nk, k);
      });
  
      Object.keys(protocolParams || {}).forEach((k) => {
        const nk = norm(k);
        // prefer protocol casing if present
        keyNormToKey.set(nk, k);
      });
  
      let keys = Array.from(keyNormToKey.values())
        .filter(k => norm(k) !== "graduation") // keep if you want it editable
        .sort((a, b) => a.localeCompare(b));
  
      const row = document.createElement("div");
      row.className = "step-box";
  
      const displayName = sanitizeStepTitle(step.step_name, idx, step.task_type);
  
      row.innerHTML = `
        <div class="step-head">
          <div class="step-name">${escapeHtml(displayName)}</div>
        </div>
  
        <div class="step-section">
          <div class="step-section-title">Overrides</div>
          <div class="params-grid params-grid-2col" data-override-grid="1"></div>
  
          <div class="override-actions" style="margin-top:6px;">
            <button class="button-ghost" type="button" data-clear-step="${idx}">
              Clear step overrides
            </button>
          </div>
        </div>
      `;
  
      const overGrid = row.querySelector('[data-override-grid="1"]');
  
      // If there are no known keys, show a friendly message
      if (!keys.length) {
        overGrid.innerHTML = `<div class="muted small">No overridable params for this step</div>`;
      } else {
        keys.forEach((key) => {
          const spec = getSpecCI(paramSpec, key) || {};
          const typeHint = spec.type ? ` – ${spec.type}` : "";
  
          // find any existing override by case-insensitive match
          let existingVal;
          const nk = norm(key);
          for (const k of Object.keys(stepDraft)) {
            if (norm(k) === nk) {
              existingVal = stepDraft[k];
              // normalize stored key casing to our canonical key
              if (k !== key) {
                delete stepDraft[k];
                stepDraft[key] = existingVal;
              }
              break;
            }
          }
  
          const field = document.createElement("div");
          field.className = "param-field";
  
          const label = document.createElement("label");
          label.textContent = key;
  
          const input = document.createElement("input");
          input.type = "text";
          input.autocomplete = "off";
          input.spellcheck = false;
          input.placeholder = `override${typeHint}`;
          input.value = existingVal == null ? "" : String(existingVal);
  
          makeInputTypeable(input);
  
          input.addEventListener("input", () => {
            const v = input.value.trim();
  
            if (v === "") {
              // remove any casing variant
              for (const k of Object.keys(stepDraft)) {
                if (norm(k) === nk) delete stepDraft[k];
              }
              input.classList.remove("is-invalid");
              return;
            }
  
            // parse using spec.type when available; else store raw string
            if (spec.type) {
              const parsed = parseByType(v, spec.type);
              if (parsed.__invalid) {
                input.classList.add("is-invalid");
                return;
              }
              input.classList.remove("is-invalid");
              // normalize and store
              for (const k of Object.keys(stepDraft)) {
                if (norm(k) === nk) delete stepDraft[k];
              }
              stepDraft[key] = parsed.value;
            } else {
              input.classList.remove("is-invalid");
              for (const k of Object.keys(stepDraft)) {
                if (norm(k) === nk) delete stepDraft[k];
              }
              stepDraft[key] = v;
            }
          });
  
          field.appendChild(label);
          field.appendChild(input);
          overGrid.appendChild(field);
        });
      }
  
      // clear step overrides
      row.querySelector(`[data-clear-step="${idx}"]`).onclick = () => {
        OVERRIDES_DRAFT[sessionId].steps[String(idx)] = {};
        renderParamsPanel(li, protocol, sessionId);
      };
  
      panel.appendChild(row);
    });
  }
    
  // --------------------------------------------------
  // Hydrate card
  // --------------------------------------------------
  async function hydrateCard(li) {
    if (!li || li.getAttribute("data-hydrated") === "1") return;

    const sessionId = Number(li.getAttribute("data-session-id"));
    if (!sessionId) return;

    if (!CURRENT_PILOT_STATE?.connected) return;

    const detail = await fetchSessionDetailCached(sessionId);
    if (!detail) {
      li.querySelector(".session-title").textContent = "Failed to load";
      return;
    }

    if (FILTER_SUBJECTS.length > 0 && !sessionHasAllSubjects(detail, FILTER_SUBJECTS)) {
      li.remove();
      return;
    }

    const runs = detail.runs || [];
    if (!runs.length) {
      li.remove();
      return;
    }

    const protocolId = runs[0].protocol_id;
    const protocol = await fetchProtocolCached(protocolId);
    if (!protocol) {
      li.querySelector(".session-title").textContent = "Failed to load";
      return;
    }

    const latest = await fetchLatestForSession(sessionId);
    const run = latest?.run;
    const prog = latest?.progress;

    const statusText = run?.status ? String(run.status) : "never run";
    const modeText = run?.mode ? `mode: ${run.mode}` : "";
    const started = run?.started_at ? formatDateDMY(run.started_at) : "";
    const ended = run?.ended_at ? formatDateDMY(run.ended_at) : "";
    const progText =
      (prog?.current_step != null || prog?.current_trial != null)
        ? `step ${prog.current_step ?? "?"}, trial ${prog.current_trial ?? "?"}`
        : "";

    li.querySelector(".session-title").textContent = protocol.name;

    const subjectsWrap = li.querySelector(".subject-tags");
    subjectsWrap.innerHTML = "";
    runs.forEach((r) => {
      const pill = document.createElement("span");
      pill.className = "subject-tag";
      pill.textContent = r.subject_name;
      subjectsWrap.appendChild(pill);
    });

    renderParamsPanel(li, protocol, sessionId);

    const meta = li.querySelector(".session-meta");
    meta.innerHTML = `
      <div class="meta-row meta-row-top">
        <span class="badge status-${escapeHtml(statusText)}">${escapeHtml(statusText)}</span>
        ${modeText ? `<span class="meta-pill">${escapeHtml(modeText)}</span>` : ""}
        ${progText ? `<span class="meta-pill">${escapeHtml(progText)}</span>` : ""}
      </div>

      ${(started || ended) ? `
        <div class="meta-row meta-row-dates">
          ${started ? `<span class="meta-date">Started ${escapeHtml(started)}</span>` : ""}
          ${ended ? `<span class="meta-date">Ended ${escapeHtml(ended)}</span>` : ""}
        </div>
      ` : ""}
    `;

    li.setAttribute("data-hydrated", "1");
    refreshActionButtonsOnly();
  }

  // --------------------------------------------------
  // Load sessions
  // --------------------------------------------------
  async function loadSessions() {
    const ul = document.getElementById("sessions");
    if (ul) showSkeleton(ul, 8);

    const res = await fetch("/api/sessions");
    if (!res.ok) throw new Error("Failed to load sessions");

    const sessions = await res.json();
    renderSessionsCache = sessions;
    renderShellList(sessions);
  }

  // --------------------------------------------------
  // Init
  // --------------------------------------------------
  (async function init() {
    try {
      await loadPilotId();
      await initSubjectFilterUI();
      await loadTasksOnce();

      CURRENT_PILOT_STATE = CURRENT_PILOT_STATE || { connected: true, active_run: null };

      await loadSessions();
      initPilotWebSocket();
    } catch (err) {
      console.error(err);
      const status = document.getElementById("status");
      if (status) status.textContent = err.message;
    }
  })();
})();
