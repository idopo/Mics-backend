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
  // Inject minimal CSS for graduation pill (safe, small)
  // --------------------------------------------------
  (function injectGraduationCSS() {
    if (document.getElementById("__pilot_graduation_css")) return;
    const css = `
      /* Graduation pill */
      .graduation-pill {
        display: inline-flex;
        align-items: center;
        gap: 8px;
        background: rgba(102, 84, 255, 0.06);
        border: 1px solid rgba(102, 84, 255, 0.12);
        padding: 6px 10px;
        border-radius: 12px;
        font-size: 13px;
        color: #2b2b2b;
        max-width: 100%;
        box-sizing: border-box;
      }
      .graduation-pill .grad-icon {
        display: inline-flex;
        align-items: center;
        justify-content: center;
        width: 20px;
        height: 20px;
        border-radius: 50%;
        background: rgba(102,84,255,0.12);
        color: #664eff;
        font-weight: 700;
        font-size: 12px;
        flex: 0 0 20px;
      }
      .graduation-pill .graduation-detail {
        font-size: 12px;
        color: #444;
        opacity: 0.95;
        white-space: nowrap;
        overflow: hidden;
        text-overflow: ellipsis;
        max-width: 380px;
      }
      .step-section[data-grad-slot="1"] { margin-bottom: 8px; }
      .step-section-title { font-weight: 600; margin-bottom: 6px; }
    `;
    const s = document.createElement("style");
    s.id = "__pilot_graduation_css";
    s.appendChild(document.createTextNode(css));
    document.head && document.head.appendChild(s);
  })();

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
  const MAX_LABEL_CHARS = 15;
  // In-flight dedupe
  const SESSION_DETAILS_INFLIGHT = {};
  const PROTOCOL_INFLIGHT = {};
  const LATEST_INFLIGHT = {};

  // per sessionId: { steps: { "0": {...}, "1": {...} } }
  const OVERRIDES_DRAFT = {};

  const OVERRIDES_LAST = {};
  const OVERRIDES_DIRTY = {};
  window.OVERRIDES_LAST = OVERRIDES_LAST;
  window.OVERRIDES_DIRTY = OVERRIDES_DIRTY;


  let FIRST_RENDER = true;

  /* =========================================================
   Session Overrides Modal (editable)
   - Opens from session title click
   - Shows ALL params per step (from task schema union protocol params)
   - Writes into OVERRIDES_DRAFT[sessionId].steps[stepIndex]
   - Uses parseByType(spec.type) for typed overrides
   ========================================================= */
// DROP-IN REPLACEMENT
// Replaces ONLY: window.showSessionOverridesModal = function showSessionOverridesModal(sessionId, protocolId) { ... }
// Fixes:
// 1) "Cannot access 'label' before initialization" (no use-before-declare)
// 2) graduation UI: shows CURRENT number in the LABEL (current: N), NOT inside the input
// 3) graduation input: if override exists, show just the number; otherwise empty
// 4) typing works (stopPropagation guards preserved)
// 5) case-insensitive override keys (iti vs ITI) preserved
// ==========================================================
// PATCH 3: FULL showSessionOverridesModal(sessionId, protocolId)
// ==========================================================
// Drop-in replacement for window.showSessionOverridesModal
// Changes:
// - Marks OVERRIDES_DIRTY[sessionId] = true whenever user edits/removes any override
// - Graduation remains: current N shown in label, input never filled with JSON
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

    const isPopulatedValue = (v) => {
      if (v === undefined || v === null) return false;
      if (typeof v === "string" && v.trim() === "") return false;
      if (typeof v === "object" && !Array.isArray(v) && Object.keys(v).length === 0) return false;
      return true;
    };

    // Ensure draft exists
    if (!OVERRIDES_DRAFT[sessionId]) OVERRIDES_DRAFT[sessionId] = { steps: {} };
    if (!OVERRIDES_DRAFT[sessionId].steps) OVERRIDES_DRAFT[sessionId].steps = {};

    // Ensure dirty flag exists
    if (typeof window.OVERRIDES_DIRTY !== "undefined") {
      if (window.OVERRIDES_DIRTY[sessionId] == null) window.OVERRIDES_DIRTY[sessionId] = false;
    }

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
        <div style="min-width:0;">
          <div class="modal-title" id="ovModalTitle">Session Overrides</div>
        </div>
        <div style="display:flex; gap:8px; align-items:center;">
          <button class="modal-close" type="button" aria-label="Close">✕</button>
        </div>
      </div>

      <div class="modal-body" style="padding: 12px 14px;">
        <div id="ovModalStatus" class="modal-muted">Loading…</div>
        <div id="ovModalSteps" style="margin-top: 10px; max-height: 72vh; overflow:auto;"></div>
        <div class="modal-actions ov-actions" style="margin-top:12px; display:flex; justify-content:flex-end; gap:8px;">
          <button class="button-primary" type="button" id="ovDone">Apply overrides</button>
        </div>
      </div>
    `;

    overlay.appendChild(modal);
    document.body.appendChild(overlay);

    modal.querySelector(".modal-close").onclick = finish;
    modal.querySelector("#ovDone").onclick = finish;
    overlay.addEventListener("mousedown", (e) => { if (e.target === overlay) finish(); });
    document.addEventListener("keydown", onKeyDown, true);

    modal.addEventListener("keydown", (e) => e.stopPropagation(), true);
    modal.addEventListener("keypress", (e) => e.stopPropagation(), true);
    modal.addEventListener("keyup", (e) => e.stopPropagation(), true);

    // helpers
    const buildStepTitle = (step, idx) => sanitizeStepTitle(step.step_name, idx, step.task_type);

    const getDraftStepObj = (stepIdx) => {
      const s = String(stepIdx);
      OVERRIDES_DRAFT[sessionId].steps[s] = OVERRIDES_DRAFT[sessionId].steps[s] || {};
      return OVERRIDES_DRAFT[sessionId].steps[s];
    };

    const deleteKeyCI = (obj, key) => {
      const nk = norm(key);
      for (const k of Object.keys(obj || {})) {
        if (norm(k) === nk) delete obj[k];
      }
    };

    const markDirty = () => {
      if (typeof window.OVERRIDES_DIRTY !== "undefined") {
        window.OVERRIDES_DIRTY[sessionId] = true;
      }
    };

    const setDraftValue = (stepIdx, key, specType, rawStr) => {
      const draft = getDraftStepObj(stepIdx);

      // any interaction counts as intent to override
      markDirty();

      if (rawStr.trim() === "") {
        deleteKeyCI(draft, key);
        return { ok: true, removed: true };
      }

      const parsed = parseByType(rawStr, specType);
      if (parsed && parsed.__invalid) return { ok: false };

      deleteKeyCI(draft, key);
      draft[key] = parsed.value;
      return { ok: true };
    };

    const getEffectiveValue = ({ protocolParams, spec, key }) => {
      const protocolVal = getValCI(protocolParams, key);
      const hasProtocol = isPopulatedValue(protocolVal);

      const defaultVal = getSpecDefaultValue(spec);
      const hasDefault = isPopulatedValue(defaultVal);

      if (hasProtocol) return { val: protocolVal, source: "protocol" };
      if (hasDefault) return { val: defaultVal, source: "default" };
      return { val: "", source: "missing" };
    };

    const getGraduationN = (gr) => {
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
    };

    const formatGraduationOverrideForInput = (draftVal) => {
      const n = getGraduationN(draftVal);
      return n == null ? "" : String(n);
    };

    (async () => {
      const statusEl = modal.querySelector("#ovModalStatus");
      const stepsEl = modal.querySelector("#ovModalSteps");
      const titleEl = modal.querySelector("#ovModalTitle");

      try {
        titleEl.textContent = `Session ${sessionId} Overrides`;

        if (!TASKS_BY_NAME) await loadTasksOnce();

        const protocol = await fetchProtocolCached(protocolId);
        if (!protocol) throw new Error("Failed to load protocol");

        const steps = protocol?.steps || [];
        if (!steps.length) {
          statusEl.textContent = "";
          stepsEl.innerHTML = `<div class="muted">No steps</div>`;
          return;
        }

        statusEl.textContent = "";
        stepsEl.innerHTML = "";

        steps.forEach((step, idx) => {
          const task = TASKS_BY_NAME?.get(norm(step.task_type));
          const specObj = pickParamSpec(task) || {};
          const protocolParams = step.params || {};

          // Union keys
          const keyNormToKey = new Map();
          Object.keys(specObj || {}).forEach((k) => {
            const nk = norm(k);
            if (!keyNormToKey.has(nk)) keyNormToKey.set(nk, k);
          });
          Object.keys(protocolParams || {}).forEach((k) => {
            const nk = norm(k);
            keyNormToKey.set(nk, k);
          });

          let keys = Array.from(keyNormToKey.values())
            .filter(k => !["step_name", "task_type"].includes(norm(k)))
            .sort((a, b) => a.localeCompare(b));

          const stepIdxStr = String(idx);
          const draftStep = getDraftStepObj(stepIdxStr);

          const box = document.createElement("div");
          box.className = "step-box";

          box.innerHTML = `
            <div class="step-head" style="cursor:pointer;">
              <div style="min-width:0;">
                <div class="step-name">${escapeHtml(buildStepTitle(step, idx))}</div>
              </div>
              <button class="button-secondary" type="button" data-toggle="1">▸</button>
            </div>

            <div data-body="1" style="margin-top:10px; display:none;">
              <div class="step-section">
                <div class="params-grid params-grid-2col" data-params-grid="1"></div>
              </div>
            </div>
          `;

          const toggleBtn = box.querySelector('[data-toggle="1"]');
          const body = box.querySelector('[data-body="1"]');
          let open = false;
          const setOpen = (v) => {
            open = v;
            body.style.display = open ? "block" : "none";
            toggleBtn.textContent = open ? "▾" : "▸";
          };
          setOpen(idx === 0);

          box.querySelector(".step-head").addEventListener("click", (e) => {
            if (e.target === toggleBtn) return;
            if (e.target?.getAttribute && e.target.getAttribute("data-clear-step") === "1") return;
            setOpen(!open);
          });

          toggleBtn.addEventListener("click", (e) => {
            e.stopPropagation();
            setOpen(!open);
          });

          const grid = box.querySelector('[data-params-grid="1"]');
          if (!keys.length) {
            grid.innerHTML = `<div class="muted small">No params</div>`;
            stepsEl.appendChild(box);
            return;
          }

          keys.forEach((key) => {
            const spec = getSpecCI(specObj, key) || {};
            const typeHint = spec.type ? ` – ${spec.type}` : "";
            const tag = spec.tag ?? key;

            const eff = getEffectiveValue({ protocolParams, spec, key });

            const draftVal = getValCI(draftStep, key);
            const hasDraft = isPopulatedValue(draftVal);

            const isGrad = norm(key) === "graduation";
            const gradCurrent = isGrad ? getGraduationN(eff.val) : null;

            const effText = (() => {
              if (isGrad) return (gradCurrent == null ? "" : String(gradCurrent));
              return (eff.val === "" ? "" : formatAny(eff.val));
            })();

            const field = document.createElement("div");
            field.className = "param-field";

            const labelEl = document.createElement("label");
            labelEl.textContent = "";

            const name = document.createElement("span");
            name.className = `param-name param-name-${eff.source}`;
            name.title = key;
            name.textContent =
              key.length > MAX_LABEL_CHARS
                ? key.slice(0, MAX_LABEL_CHARS - 1) + "…"
                : key;

            labelEl.appendChild(name);

            if (isGrad && gradCurrent != null) {
              const cur = document.createElement("span");
              cur.className = "param-current";
              cur.style.marginLeft = "8px";
              cur.style.fontSize = "12px";
              cur.style.opacity = "0.85";
              cur.textContent = `current: ${gradCurrent}`;
              labelEl.appendChild(cur);
            }

            const input = document.createElement("input");
            input.type = "text";
            input.disabled = false;
            input.setAttribute("data-step-idx", stepIdxStr);
            input.setAttribute("data-param-key", key);

            input.placeholder = `${String(tag)}${typeHint}${effText ? `  |  effective: ${effText}` : ""}`;

            if (isGrad) {
              input.value = hasDraft ? formatGraduationOverrideForInput(draftVal) : "";
            } else {
              input.value = hasDraft ? formatAny(draftVal) : "";
            }

            input.addEventListener("keydown", (e) => e.stopPropagation(), true);

            input.addEventListener("input", (e) => {
              e.stopPropagation();

              const raw = input.value;
              const stepIdx = stepIdxStr;

              if (isGrad) {
                const s = raw.trim();

                // empty => remove override
                if (s === "") {
                  markDirty();
                  setDraftValue(stepIdx, key, spec.type, raw);
                  input.classList.remove("is-invalid");
                  input.removeAttribute("title");
                  return;
                }

                // numeric => build NTrials graduation object
                if (/^\d+$/.test(s)) {
                  const n = Number(s);
                  const g = buildNTrialsGraduation(n);
                  if (!g) {
                    input.classList.add("is-invalid");
                    input.title = "Graduation must be a positive integer";
                    return;
                  }

                  markDirty();
                  const draft = getDraftStepObj(stepIdx);
                  deleteKeyCI(draft, key);
                  draft[key] = g;

                  input.classList.remove("is-invalid");
                  input.removeAttribute("title");
                  return;
                }

                // allow JSON
                const parsed = parseByType(raw, "json");
                if (!parsed.__invalid && parsed.value && typeof parsed.value === "object") {
                  markDirty();
                  const draft = getDraftStepObj(stepIdx);
                  deleteKeyCI(draft, key);
                  draft[key] = parsed.value;

                  input.classList.remove("is-invalid");
                  input.removeAttribute("title");
                  return;
                }

                input.classList.add("is-invalid");
                input.title = "Enter an integer N (or paste JSON like {type,value})";
                return;
              }

              const res = setDraftValue(stepIdxStr, key, spec.type, raw);
              if (!res.ok) {
                input.classList.add("is-invalid");
                input.title = "Invalid value for type";
              } else {
                input.classList.remove("is-invalid");
                input.removeAttribute("title");
              }
            });

            field.appendChild(labelEl);
            field.appendChild(input);
            grid.appendChild(field);
          });

          stepsEl.appendChild(box);
        });
      } catch (e) {
        console.error(e);
        statusEl.textContent = `Failed to load overrides UI: ${e.message || e}`;
      }
    })();
  });
};


  // --------------------------------------------------
  // Small utils
  // --------------------------------------------------
  /* =========================================================
   Protocol Details Modal (overlay, no new HTML)
   Paste into session_launcher_lazy_hydrate.js
   1) Add the modal function (Section A)
   2) Patch hydrateCard title click (Section B)
   ========================================================= */

  /* -----------------------------
     Section A: Add this ONCE
     Put it near showStartModeModal
  ------------------------------ */
  window.showProtocolDetailsModal = function showProtocolDetailsModal(protocolId) {
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

      const norm = (s) => String(s || "").trim().toLowerCase();

      const escapeHtml = (s) =>
        String(s).replace(/[&<>"']/g, (c) => ({
          "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;"
        }[c]));

      const formatAny = (v) => {
        if (v == null) return "";
        if (typeof v === "string") return v;
        if (typeof v === "number" || typeof v === "boolean") return String(v);
        try { return JSON.stringify(v); } catch { return String(v); }
      };

      const sanitizeStepTitle = (stepName, idx, taskType) => {
        const stepNum = idx + 1;
        let s = String(stepName || "").trim();
        s = s.replace(/^step\s*\d+\s*[:\-–]?\s*/i, "").trim();
        const label = s || String(taskType || "").trim() || "Unnamed step";
        const tt = String(taskType || "").trim();
        const clean = tt && label.toLowerCase() === tt.toLowerCase() ? tt : label;
        return `Step ${stepNum}: ${clean}`.trim();
      };

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

      const getValCI = (obj, key) => {
        if (!obj) return undefined;
        const nk = norm(key);
        for (const k of Object.keys(obj)) {
          if (norm(k) === nk) return obj[k];
        }
        return undefined;
      };

      // Treat undefined/null/""/{} as not populated
      const isPopulatedValue = (v) => {
        if (v === undefined || v === null) return false;
        if (typeof v === "string" && v.trim() === "") return false;
        if (typeof v === "object" && !Array.isArray(v) && Object.keys(v).length === 0) return false;
        return true;
      };

      // Create overlay/modal (reuses your .modal CSS)
      const overlay = document.createElement("div");
      overlay.className = "modal-overlay";
      overlay.setAttribute("role", "dialog");
      overlay.setAttribute("aria-modal", "true");

      const modal = document.createElement("div");
      modal.className = "modal overrides-modal";

      modal.style.maxWidth = "980px";
      modal.style.width = "min(980px, calc(100vw - 24px))";

      modal.innerHTML = `
      <div class="modal-header">
        <div style="min-width:0;">
          <div class="modal-title" id="protoModalTitle">Protocol</div>
          <div class="modal-muted" id="protoModalDesc" style="margin:4px 0 0 0;"></div>
        </div>
        <button class="modal-close" type="button" aria-label="Close">✕</button>
      </div>

      <div class="modal-body" style="padding: 12px 14px;">
        <div id="protoModalStatus" class="modal-muted">Loading…</div>
        <div id="protoModalSteps" style="margin-top: 10px; max-height: 72vh; overflow:auto;"></div>
      </div>
    `;



      overlay.appendChild(modal);
      document.body.appendChild(overlay);

      // Close handlers
      modal.querySelector(".modal-close").onclick = finish;
      overlay.addEventListener("mousedown", (e) => { if (e.target === overlay) finish(); });
      document.addEventListener("keydown", onKeyDown, true);

      // Render helpers (create-protocol-like, read-only)
      function renderParamsGridReadOnly({ specObj, stepParams }) {
        const keys = Object.keys(specObj || {}).sort((a, b) => a.localeCompare(b));
        if (!keys.length) return `<div class="muted small">No params schema</div>`;

        const html = keys.map((key) => {
          const spec = specObj[key] || {};
          const tag = spec.tag ?? key;
          const type = spec.type ? ` – ${spec.type}` : "";

          const v = getValCI(stepParams, key);
          const populated = isPopulatedValue(v);

          // show concrete protocol value (from ProtocolStepTemplate.params)
          const valueText = populated ? formatAny(v) : "";

          // mark missing with a class (CSS optional)
          const missingClass = populated ? "" : "is-missing";

          return `
            <div class="param-field">
              <label>${escapeHtml(key)}</label>
              <input
                type="text"
                disabled
                class="${missingClass}"
                placeholder="${escapeHtml(String(tag) + type)}"
                value="${escapeHtml(valueText)}"
              />
            </div>
          `;
        }).join("");

        return `<div class="params-grid">${html}</div>`;
      }

      function computeMissingList({ specObj, stepParams }) {
        const keys = Object.keys(specObj || {});
        const missing = [];
        for (const k of keys) {
          const v = getValCI(stepParams, k);
          if (!isPopulatedValue(v)) missing.push(k);
        }
        return missing.sort((a, b) => a.localeCompare(b));
      }

      function computeExtras({ specObj, stepParams }) {
        const specNorm = new Set(Object.keys(specObj || {}).map(norm));
        const extras = [];
        for (const k of Object.keys(stepParams || {})) {
          if (!specNorm.has(norm(k))) extras.push(k);
        }
        return extras.sort((a, b) => a.localeCompare(b));
      }

      // Fetch + render
      (async () => {
        const titleEl = modal.querySelector("#protoModalTitle");
        const descEl = modal.querySelector("#protoModalDesc");
        const statusEl = modal.querySelector("#protoModalStatus");
        const stepsEl = modal.querySelector("#protoModalSteps");

        try {
          const [protocol, tasks] = await Promise.all([
            fetch(`/api/protocols/${protocolId}`).then((r) => {
              if (!r.ok) throw new Error("Failed to load protocol");
              return r.json();
            }),
            fetch(`/api/tasks/leaf`).then((r) => {
              if (!r.ok) throw new Error("Failed to load tasks");
              return r.json();
            }),
          ]);

          const tasksByName = new Map((tasks || []).map((t) => [norm(t.task_name), t]));

          titleEl.textContent = protocol?.name || `Protocol ${protocolId}`;
          descEl.textContent = protocol?.description || "";

          const steps = protocol?.steps || [];
          if (!steps.length) {
            statusEl.textContent = "";
            stepsEl.innerHTML = `<div class="muted">No steps</div>`;
            return;
          }

          statusEl.textContent = "";
          stepsEl.innerHTML = "";

          steps.forEach((step, idx) => {
            const task = tasksByName.get(norm(step.task_type));
            const specObj = pickParamSpec(task) || {};
            const stepParams = step.params || {}; // ✅ ProtocolStepTemplate.params (concrete)

            const missingKeys = computeMissingList({ specObj, stepParams });
            const extras = computeExtras({ specObj, stepParams });

            const displayName = sanitizeStepTitle(step.step_name, idx, step.task_type);

            const box = document.createElement("div");
            box.className = "step-box";

            box.innerHTML = `
              <div class="step-head" style="cursor:pointer;">
                <div style="min-width:0;">
                  <div class="step-name">${escapeHtml(displayName)}</div>
                  <div class="muted small">Task: <strong>${escapeHtml(step.task_type || "")}</strong></div>
                </div>
                <button class="button-secondary" type="button" data-toggle="1">▸</button>

              </div>

              <div data-body="1" style="margin-top:10px; display:none;">
                <div class="step-section" data-grad-slot="1">
                  <div class="step-section-title">Graduation</div>
                </div>

                <div class="step-section">
                  <div class="step-section-title">Params (read-only)</div>
                  ${renderParamsGridReadOnly({ specObj, stepParams })}
                </div>

                <div class="step-section">
                  <div class="step-section-title">Not populated</div>
                  ${
                    missingKeys.length
                      ? `<div class="muted small">${missingKeys.map(escapeHtml).join(", ")}</div>`
                      : `<div class="muted small">None</div>`
                  }
                </div>

              </div>
            `;

            // Insert graduation pill (uses global renderGraduation if present)
            const gradSlot = box.querySelector('[data-grad-slot="1"]');
            if (gradSlot) {
              const gradObj = stepParams.graduation ?? null;
              let gradNode = null;

              // Prefer global renderGraduation helper if available
              try {
                if (typeof window.renderGraduation === "function") {
                  gradNode = window.renderGraduation(gradObj);
                }
              } catch (e) {
                gradNode = null;
              }

              // Fallback: build a compact read-only display
              if (!gradNode) {
                const wrap = document.createElement("div");
                wrap.className = "graduation-pill";
                const icon = document.createElement("span");
                icon.className = "grad-icon";
                icon.textContent = "★";
                const txt = document.createElement("div");
                txt.style.lineHeight = "1";
                const titleText = (gradObj && gradObj.type) ? gradObj.type : (gradObj ? "Graduation" : "None defined");
                const valuePreview = gradObj ? (typeof gradObj === "object" ? JSON.stringify(gradObj.value ?? gradObj) : String(gradObj)) : "";
                const short = valuePreview.length > 120 ? valuePreview.slice(0, 116) + "…" : valuePreview;
                txt.innerHTML = `<div style="font-weight:600;font-size:13px;">${escapeHtml(titleText)}</div>
                                 <div class="graduation-detail">${escapeHtml(short)}</div>`;
                wrap.appendChild(icon);
                wrap.appendChild(txt);
                gradNode = wrap;
                gradNode.title = valuePreview;
              }

              // If no graduation at all, show "No graduation defined"
              if (!gradObj && gradNode && (!gradNode.textContent || gradNode.textContent.trim() === "")) {
                gradSlot.innerHTML = `<div class="muted small">No graduation defined</div>`;
              } else {
                gradSlot.appendChild(gradNode);
              }
            }

            // collapse behavior
            const toggleBtn = box.querySelector('[data-toggle="1"]');
            const body = box.querySelector('[data-body="1"]');
            let open = false;

            const setOpen = (v) => {
              open = v;
              body.style.display = open ? "block" : "none";
              toggleBtn.textContent = open ? "▾" : "▸";
            };

            setOpen(false);


            toggleBtn.addEventListener("click", (e) => {
              e.stopPropagation();
              setOpen(!open);
            });

            stepsEl.appendChild(box);
          });
        } catch (e) {
          console.error(e);
          statusEl.textContent = `Failed to load protocol details: ${e.message || e}`;
        }
      })();
    });
  };


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

  function renderGraduation(gr) {
    if (!gr) return null;
  
    const obj = typeof gr === "object" ? gr : {};
    const value =
      obj && typeof obj.value === "object" && obj.value ? obj.value : obj;
  
    const n = value.current_trial ?? value.n_trials ?? value.n ?? null;

  
    const wrap = document.createElement("div");
    wrap.className = "graduation-pill";
  
    wrap.innerHTML = `
      <span class="grad-icon">⟳</span>
      <span class="grad-value">${n != null ? n : ""}</span>
    `;
  
    return wrap;
  }
  

  
  
  
window.renderGraduation = renderGraduation;


  function buildNTrialsGraduation(n) {
    const nn = Number(n);
    if (!Number.isFinite(nn) || nn <= 0) return null;
    return { type: "NTrials", value: { current_trial: Math.trunc(nn) } };
  }

  
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

  // =========================================
// PATCH 2: FULL refreshActionButtonsOnly()
// =========================================
// Drop-in replacement for your existing refreshActionButtonsOnly()
// Changes:
// - On NEW runs, only send overrides if user actually edited (DIRTY)
// - Keeps your STOP logic + busy logic
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

    const isRunningHere = !!(activeRun && activeRun.session_id === sessionId);
    const isPilotBusy   = !!(activeRun && activeRun.session_id !== sessionId);

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
      return;
    }

    // START state
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

        // ✅ ONLY send overrides for NEW runs if user actually edited them
        const dirty = (typeof window.OVERRIDES_DIRTY !== "undefined")
          ? !!window.OVERRIDES_DIRTY[sessionId]
          : false;

        const overridesToSend =
          (mode === "new" && dirty && hasOverrides) ? overrides : null;

        const r = await fetch(`/api/sessions/${sessionId}/start-on-pilot`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            pilot_id: pilotId,
            mode,
            overrides: overridesToSend,
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
  // --------------------------------------------------
// Pilot card right-panel: READ-ONLY params
// - shows protocol step.params if populated
// - else shows task-spec defaults
// - no overrides UI here (overrides only via title modal)
// --------------------------------------------------
function renderParamsPanel(li, protocol, sessionId) {
  const panel = li.querySelector(".session-right .right-body");
  if (!panel) return;

  const steps = protocol?.steps || [];
  if (!steps.length) {
    panel.innerHTML = `<div class="muted small">No steps</div>`;
    return;
  }

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

  // Treat undefined/null/""/{} as NOT populated
  const isPopulatedValue = (v) => {
    if (v === undefined || v === null) return false;
    if (typeof v === "string" && v.trim() === "") return false;
    if (typeof v === "object" && !Array.isArray(v) && Object.keys(v).length === 0) return false;
    return true;
  };

  steps.forEach((step, idx) => {
    const task = TASKS_BY_NAME?.get(norm(step.task_type));
    const paramSpec = pickParamSpec(task) || {};
    const protocolParams = step.params || {}; // ✅ concrete values from create-protocol

    // Union of keys from:
    // - spec keys (defines what exists)
    // - protocolParams keys (in case protocol has extra keys)
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
      .filter(k => !["graduation", "step_name", "task_type"].includes(norm(k)))
      .sort((a, b) => a.localeCompare(b));

    const row = document.createElement("div");
    row.className = "step-box";

    const displayName = sanitizeStepTitle(step.step_name, idx, step.task_type);

    row.innerHTML = `
      <div class="step-head">
        <div class="step-name">${escapeHtml(displayName)}</div>
      </div>

      <div class="step-section">
        <div class="step-section-title">Params</div>
        <div class="params-grid params-grid-2col" data-params-grid="1"></div>
      </div>
    `;

    const grid = row.querySelector('[data-params-grid="1"]');

    if (!keys.length) {
      grid.innerHTML = `<div class="muted small">No params</div>`;
      panel.appendChild(row);
      return;
    }

    keys.forEach((key) => {
      const spec = getSpecCI(paramSpec, key) || {};
      const typeHint = spec.type ? ` – ${spec.type}` : "";
      const tag = spec.tag ?? key;

      const protocolVal = getValCI(protocolParams, key);
      const hasProtocol = isPopulatedValue(protocolVal);

      const defaultVal = getSpecDefaultValue(spec);
      const hasDefault = isPopulatedValue(defaultVal);

      // What we display:
      // - prefer protocol populated value
      // - else spec default if exists
      // - else empty (missing)
      const displayVal = hasProtocol ? protocolVal : (hasDefault ? defaultVal : "");
      const isMissing = !hasProtocol && !hasDefault;

      const sourceLabel = hasProtocol ? "protocol" : (hasDefault ? "default" : "missing");

      const field = document.createElement("div");
      field.className = "param-field";

      const label = document.createElement("label");
      label.textContent = ""; // clear (and avoids mixed text node + spans)

      // name span (gets ellipsis via CSS)
      const name = document.createElement("span");
      name.className = `param-name param-name-${sourceLabel}`;
      name.title = key;

      name.textContent =
        key.length > MAX_LABEL_CHARS
          ? key.slice(0, MAX_LABEL_CHARS - 1) + "…"
          : key;

      label.appendChild(name);




      const input = document.createElement("input");
      input.type = "text";
      input.disabled = true;

      input.placeholder = `${String(tag)}${typeHint}`;
      input.value = displayVal === "" ? "" : formatAny(displayVal);

      if (isMissing) input.classList.add("is-missing");

      field.appendChild(label);
      field.appendChild(input);
      grid.appendChild(field);
    });

    panel.appendChild(row);
  });
}

  // ================================
// PATCH 1: FULL hydrateCard(li)
// ================================
// Drop-in replacement for your existing hydrateCard(li)
// Changes:
// - NEVER auto-seed OVERRIDES_DRAFT from latest run overrides
// - Stores latest DB overrides in OVERRIDES_LAST instead
// - Initializes OVERRIDES_DIRTY[sessionId] once
async function hydrateCard(li) {
  if (!li || li.getAttribute("data-hydrated") === "1") return;

  const sessionId = Number(li.getAttribute("data-session-id"));
  if (!sessionId) return;

  if (!CURRENT_PILOT_STATE?.connected) return;

  li.classList.add("is-loading");

  try {
    const detail = await fetchSessionDetailCached(sessionId);
    if (!detail) {
      const t = li.querySelector(".session-title");
      if (t) t.textContent = "Failed to load";
      return;
    }

    // Subject filtering
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
      const t = li.querySelector(".session-title");
      if (t) t.textContent = "Failed to load";
      return;
    }

    const latest = await fetchLatestForSession(sessionId);
    const run = latest?.run;

    // -------------------------------
    // ✅ NEW OVERRIDES BEHAVIOR
    // -------------------------------
    // Keep last-run overrides separate from draft overrides.
    // Draft starts empty unless user edits during this page load.
    if (typeof window.OVERRIDES_LAST !== "undefined") {
      const dbOverrides = run?.overrides;
      window.OVERRIDES_LAST[sessionId] =
        (dbOverrides && typeof dbOverrides === "object")
          ? JSON.parse(JSON.stringify(dbOverrides))
          : null;
    }

    if (!OVERRIDES_DRAFT[sessionId] || typeof OVERRIDES_DRAFT[sessionId] !== "object") {
      OVERRIDES_DRAFT[sessionId] = { steps: {} };
    }
    if (!OVERRIDES_DRAFT[sessionId].steps || typeof OVERRIDES_DRAFT[sessionId].steps !== "object") {
      OVERRIDES_DRAFT[sessionId].steps = {};
    }

    if (typeof window.OVERRIDES_DIRTY !== "undefined") {
      if (window.OVERRIDES_DIRTY[sessionId] == null) window.OVERRIDES_DIRTY[sessionId] = false;
    }

    const prog = latest?.progress;

    const statusText = run?.status ? String(run.status) : "never run";
    const modeText = run?.mode ? `mode: ${run.mode}` : "";
    const started = run?.started_at ? formatDateDMY(run.started_at) : "";
    const ended = run?.ended_at ? formatDateDMY(run.ended_at) : "";
    const progText =
      (prog?.current_step != null || prog?.current_trial != null)
        ? `step ${prog.current_step ?? "?"}, trial ${prog.current_trial ?? "?"}`
        : "";

    // -------------------------------
    // title clickable => overrides modal
    // -------------------------------
    const titleEl = li.querySelector(".session-title");
    if (titleEl) {
      titleEl.innerHTML = "";

      const link = document.createElement("a");
      link.href = "#";
      link.textContent = protocol.name;
      link.style.color = "var(--lavender)";
      link.style.textDecoration = "none";
      link.style.cursor = "pointer";

      link.addEventListener("click", async (e) => {
        e.preventDefault();
        e.stopPropagation();
        if (typeof window.showSessionOverridesModal === "function") {
          await window.showSessionOverridesModal(sessionId, protocolId);
        }
      });

      link.addEventListener("mouseenter", () => { link.style.textDecoration = "underline"; });
      link.addEventListener("mouseleave", () => { link.style.textDecoration = "none"; });

      titleEl.appendChild(link);
    }

    // Subjects
    const subjectsWrap = li.querySelector(".subject-tags");
    if (subjectsWrap) {
      subjectsWrap.innerHTML = "";
      runs.forEach((r) => {
        const pill = document.createElement("span");
        pill.className = "subject-tag";
        pill.textContent = r.subject_name;
        subjectsWrap.appendChild(pill);
      });
    }

    // Right side params (read-only)
    renderParamsPanel(li, protocol, sessionId);

    // Meta
    const meta = li.querySelector(".session-meta");
    if (meta) {
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
    }

    li.setAttribute("data-hydrated", "1");
    refreshActionButtonsOnly();
  } catch (err) {
    console.error("hydrateCard error:", err);
    const t = li.querySelector(".session-title");
    if (t) t.textContent = "Failed to load";
  } finally {
    li.classList.remove("is-loading");
  }
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
