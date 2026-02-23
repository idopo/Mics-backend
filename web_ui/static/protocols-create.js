// ======================================================
// DOM
// ======================================================

const tasksList = document.getElementById("tasks-list");
const stepsList = document.getElementById("steps-list");
const statusLine = document.getElementById("status-line");
const saveBtn = document.getElementById("save-protocol-btn");


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

function clearLoading(container) {
  container.classList.remove("is-loading");
  container.innerHTML = "";
}

function makeAnimatedLi(text, delayMs = 0) {
  const li = document.createElement("li");
  li.textContent = text;
  li.classList.add("fade-in-item");
  li.style.animationDelay = `${delayMs}ms`;
  return li;
}

// ======================================================
// STATE
// ======================================================

let availableTasks = [];
let steps = [];

// ======================================================
// API HELPERS
// ======================================================

async function apiGet(url) {
  const resp = await fetch(url);
  if (!resp.ok) throw new Error(`GET ${url} failed`);
  return resp.json();
}

async function apiPost(url, payload) {
  const resp = await fetch(url, {
    method: "POST",
    headers: {"Content-Type": "application/json"},
    body: JSON.stringify(payload),
  });
  if (!resp.ok) throw new Error(`POST ${url} failed`);
  return resp.json();
}

async function loadTasks() {
  const rawTasks = await apiGet("/api/tasks/leaf");
  availableTasks = rawTasks;

  const byName = new Map();

  const asTime = (v) => {
    const t = Date.parse(v);
    return Number.isFinite(t) ? t : null;
  };

  const isNewer = (a, b) => {
    // return true if a is newer than b
    // 1) higher id wins (best for "last added")
    const aid = Number(a?.id ?? NaN);
    const bid = Number(b?.id ?? NaN);
    if (Number.isFinite(aid) && Number.isFinite(bid) && aid !== bid) return aid > bid;
    if (Number.isFinite(aid) && !Number.isFinite(bid)) return true;
    if (!Number.isFinite(aid) && Number.isFinite(bid)) return false;

    // 2) fall back to created_at / updated_at if present
    const aCreated = asTime(a?.created_at);
    const bCreated = asTime(b?.created_at);
    if (aCreated != null && bCreated != null && aCreated !== bCreated) return aCreated > bCreated;

    const aUpdated = asTime(a?.updated_at);
    const bUpdated = asTime(b?.updated_at);
    if (aUpdated != null && bUpdated != null && aUpdated !== bUpdated) return aUpdated > bUpdated;

    // 3) last resort: keep existing
    return false;
  };

  for (const t of rawTasks) {
    const name = t.task_name;
    const prev = byName.get(name);
    if (!prev || isNewer(t, prev)) byName.set(name, t);
  }

  const displayTasks = Array.from(byName.values()).sort((a, b) =>
    a.task_name.localeCompare(b.task_name)
  );

  tasksList.innerHTML = "";
  displayTasks.forEach((task) => {
    const li = document.createElement("li");
    li.className = "task-item";
    li.textContent = task.task_name;
    li.onclick = () => addStep(task);
    tasksList.appendChild(li);
  });
}


function setStatus(msg, isError = false) {
  statusLine.textContent = msg;
  statusLine.style.color = isError ? "crimson" : "";
}

async function onSaveProtocol() {
  try {
    // ---- gather name/description from DOM (adjust IDs to your HTML) ----
    const nameEl = document.getElementById("protocol-name");
    const descEl = document.getElementById("protocol-desc");

    const name = (nameEl?.value || "").trim();
    const description = (descEl?.value || "").trim() || null;

    if (!name) {
      setStatus("Protocol name is required.", true);
      return;
    }
    if (steps.length === 0) {
      setStatus("Add at least one step before saving.", true);
      return;
    }

    // ---- build steps payload ----
    const stepsPayload = steps.map((s, idx) => {
      // merge user-entered params with graduation block (if set)
      const params = { ...(s.params || {}) };

      if (s.graduation_ntrials != null && Number.isFinite(s.graduation_ntrials)) {
        params.graduation = {
          type: "NTrials",
          value: { current_trial: Number(s.graduation_ntrials) },
        };
      }

      return {
        order_index: idx,
        step_name: `${idx + 1}. ${s.task_type}`, // or let user edit a name later
        task_type: s.task_type,
        params: params,
      };
    });

    const payload = {
      name,
      description,
      steps: stepsPayload,
    };

    setStatus("Saving...");
    saveBtn.disabled = true;

    // IMPORTANT: your backend route is /protocols (not /api/protocols) in the code you pasted.
    // If you have a reverse proxy that prefixes /api, change this to "/api/protocols".
    const created = await apiPost("api/protocols", payload);

    setStatus(`✅ Saved protocol "${created.name}" (id=${created.id})`);
    // optional: clear editor
    // steps = [];
    // renderSteps();
  } catch (err) {
    console.error(err);
    setStatus(`❌ Save failed: ${err?.message || err}`, true);
  } finally {
    saveBtn.disabled = false;
  }
}


// ======================================================
// STEPS
// ======================================================

function addStep(task) {
  const step = {
    task_type: task.task_name,

    // Schema only (tag + type)
    paramSpec: structuredClone(task.default_params || {}),

    // User-entered values only
    params: {},

    graduation_ntrials: null,
    collapsed: false,
  };

  steps.push(step);
  renderSteps();
}




function renderSteps() {
  // ---------- Tooltip (single floating element, fixed) ----------
  let tip = document.getElementById("ui-tooltip");
  if (!tip) {
    tip = document.createElement("div");
    tip.id = "ui-tooltip";
    tip.className = "ui-tooltip";
    tip.style.display = "none";
    document.body.appendChild(tip);
  }

  const showTip = (text, x, y) => {
    if (!text) return;
    tip.textContent = text;
    tip.style.display = "block";

    const pad = 12;

    // temp position
    tip.style.left = `${x + 12}px`;
    tip.style.top = `${y + 14}px`;

    const r = tip.getBoundingClientRect();
    let left = x + 12;
    let top = y + 14;

    if (left + r.width > window.innerWidth - pad) left = window.innerWidth - r.width - pad;
    if (top + r.height > window.innerHeight - pad) top = y - r.height - 14;

    tip.style.left = `${Math.max(pad, left)}px`;
    tip.style.top = `${Math.max(pad, top)}px`;
  };

  const hideTip = () => {
    tip.style.display = "none";
  };

  // ---------- Helpers ----------
  const normType = (t) => String(t || "").trim().toLowerCase();

  const formatAny = (v) => {
    if (v == null) return "";
    if (typeof v === "string") return v;
    if (typeof v === "number" || typeof v === "boolean") return String(v);
    try { return JSON.stringify(v); } catch { return String(v); }
  };

  const parseByType = (raw, type) => {
    const t = normType(type);
    if (!t) return { value: raw };
    const s = String(raw).trim();

    if (t.includes("int")) {
      const n = Number(s);
      if (!Number.isFinite(n) || !Number.isInteger(n)) return { __invalid: true };
      return { value: n };
    }

    if (t.includes("float") || t.includes("number") || t.includes("double")) {
      const n = Number(s);
      if (!Number.isFinite(n)) return { __invalid: true };
      return { value: n };
    }

    if (t.includes("bool")) {
      const v = s.toLowerCase();
      if (["true", "1", "yes", "y"].includes(v)) return { value: true };
      if (["false", "0", "no", "n"].includes(v)) return { value: false };
      return { __invalid: true };
    }

    if (t.includes("json") || t.includes("dict") || t.includes("list") || t.includes("object")) {
      try { return { value: JSON.parse(s) }; } catch { return { __invalid: true }; }
    }

    return { value: s };
  };

  // ---------- Render ----------
  stepsList.innerHTML = "";

  steps.forEach((step, idx) => {
    const li = document.createElement("li");
    li.className = "step-card";

    // ================= Header =================
    const header = document.createElement("div");
    header.className = "step-header";

    const title = document.createElement("strong");
    title.textContent = `${idx + 1}. ${step.task_type}`;

    const headerActions = document.createElement("div");
    headerActions.style.display = "flex";
    headerActions.style.gap = "6px";

    const toggleBtn = document.createElement("button");
    toggleBtn.className = "icon-btn";
    toggleBtn.textContent = step.collapsed ? "▸" : "▾";
    toggleBtn.onclick = () => {
      step.collapsed = !step.collapsed;
      renderSteps();
    };

    const removeBtn = document.createElement("button");
    removeBtn.className = "icon-btn icon-danger";
    removeBtn.textContent = "🗑️";
    removeBtn.onclick = () => {
      steps.splice(idx, 1);
      renderSteps();
    };

    headerActions.appendChild(toggleBtn);
    headerActions.appendChild(removeBtn);
    header.appendChild(title);
    header.appendChild(headerActions);

    // ================= Body =================
    const body = document.createElement("div");
    body.className = "step-body";
    body.style.display = step.collapsed ? "none" : "block";

    // ================= Params =================
    const paramsGrid = document.createElement("div");
    paramsGrid.className = "params-grid";

    Object.entries(step.paramSpec || {}).forEach(([key, spec]) => {
      const field = document.createElement("div");
      field.className = "param-field";

      const label = document.createElement("label");
      label.textContent = key;

      // Tooltip text (ONLY stored here, no CSS selectors, no title)
      const tag = spec?.tag ?? key;
      const typeStr = spec?.type ? ` – ${spec.type}` : "";
      label.dataset.tip = `${tag}${typeStr}`;

      // Single tooltip system (JS)
      label.addEventListener("mouseenter", (e) => showTip(label.dataset.tip, e.clientX, e.clientY));
      label.addEventListener("mousemove", (e) => showTip(label.dataset.tip, e.clientX, e.clientY));
      label.addEventListener("mouseleave", hideTip);

      const input = document.createElement("input");
      input.type = "text";
      input.autocomplete = "off";
      input.spellcheck = false;

      const defVal =
        spec?.default !== undefined && spec?.default !== null
          ? formatAny(spec.default)
          : "";
      input.placeholder = defVal;

      input.value = step.params[key] === undefined ? "" : formatAny(step.params[key]);

      input.oninput = () => {
        const v = input.value.trim();
        if (v === "") {
          delete step.params[key];
          input.classList.remove("is-invalid");
          return;
        }

        if (spec?.type) {
          const parsed = parseByType(v, spec.type);
          if (parsed.__invalid) {
            input.classList.add("is-invalid");
            return;
          }
          input.classList.remove("is-invalid");
          step.params[key] = parsed.value;
        } else {
          input.classList.remove("is-invalid");
          step.params[key] = v;
        }
      };

      field.appendChild(label);
      field.appendChild(input);
      paramsGrid.appendChild(field);
    });

    body.appendChild(paramsGrid);

    // ================= Graduation =================
    const gradRow = document.createElement("div");
    gradRow.className = "graduation-row";

    const gradLabel = document.createElement("label");
    gradLabel.textContent = "NTrials graduation";

    const gradInput = document.createElement("input");
    gradInput.type = "number";
    gradInput.min = 1;
    gradInput.placeholder = "e.g. 5";
    gradInput.value = step.graduation_ntrials ?? "";

    gradInput.oninput = () => {
      step.graduation_ntrials = gradInput.value ? parseInt(gradInput.value, 10) : null;
    };

    gradRow.appendChild(gradLabel);
    gradRow.appendChild(gradInput);
    body.appendChild(gradRow);

    li.appendChild(header);
    li.appendChild(body);
    stepsList.appendChild(li);
  });

  // Hide tooltip in common “stuck” cases
  stepsList.onmouseleave = hideTip;
  window.addEventListener("scroll", hideTip, { passive: true });
  window.addEventListener("blur", hideTip);
  saveBtn.addEventListener("click", onSaveProtocol);
  
}


// ======================================================
// INIT
// ======================================================

loadTasks();
