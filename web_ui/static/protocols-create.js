// ======================================================
// DOM
// ======================================================

const tasksList = document.getElementById("tasks-list");
const stepsList = document.getElementById("steps-list");
const statusLine = document.getElementById("status-line");
const saveBtn = document.getElementById("save-protocol-btn");

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

// ======================================================
// LOAD TASK PALETTE
// ======================================================

async function loadTasks() {
  availableTasks = await apiGet("/api/tasks/leaf");

  tasksList.innerHTML = "";
  availableTasks.forEach(task => {
    const li = document.createElement("li");
    li.className = "task-item";
    li.textContent = task.task_name;
    li.onclick = () => addStep(task);
    tasksList.appendChild(li);
  });
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

    // Collapse toggle
    const toggleBtn = document.createElement("button");
    toggleBtn.className = "icon-btn";
    toggleBtn.textContent = step.collapsed ? "▸" : "▾";
    toggleBtn.onclick = () => {
      step.collapsed = !step.collapsed;
      renderSteps();
    };

    // Remove button
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

      const input = document.createElement("input");
      input.type = "text";

      // 🔑 Tag + type inside placeholder
      const tag = spec.tag ?? key;
      const type = spec.type ? ` – ${spec.type}` : "";
      input.placeholder = `${tag}${type}`;

      input.value = step.params[key] ?? "";

      input.oninput = () => {
        if (input.value.trim() === "") {
          delete step.params[key];
        } else {
          step.params[key] = input.value;
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
      step.graduation_ntrials = gradInput.value
        ? parseInt(gradInput.value, 10)
        : null;
    };

    gradRow.appendChild(gradLabel);
    gradRow.appendChild(gradInput);
    body.appendChild(gradRow);

    li.appendChild(header);
    li.appendChild(body);
    stepsList.appendChild(li);
  });
}

// ======================================================
// SAVE PROTOCOL
// ======================================================

saveBtn.onclick = async () => {
  try {
    const nameInput = document.getElementById("protocol-name");
    const descInput = document.getElementById("protocol-desc");

    const name = nameInput?.value.trim();
    const description = descInput?.value.trim() || null;

    if (!name) {
      statusLine.textContent = "Protocol name is required.";
      return;
    }

    if (steps.length === 0) {
      statusLine.textContent = "Add at least one step.";
      return;
    }

    statusLine.textContent = "Saving protocol…";

    // 🔑 Build payload EXACTLY matching ProtocolCreate
    const payload = {
      name,
      description,
      steps: steps.map((step, idx) => {
        const params = { ...step.params };

        // 🔑 Graduation lives INSIDE params
        if (step.graduation_ntrials) {
          params.graduation = {
            type: "NTrials",
            value: {
              current_trial: step.graduation_ntrials,
            },
          };
        }

        return {
          order_index: idx,
          step_name: `Step ${idx + 1}: ${step.task_type}`,
          task_type: step.task_type,
          params: Object.keys(params).length > 0 ? params : null,
        };
      }),
    };

    await apiPost("/api/protocols", payload);

    statusLine.textContent = "Protocol saved successfully ✔";
    
    window.location.assign("/protocols-ui");
    return;
    
    // Reset UI
    steps = [];
    renderSteps();
    nameInput.value = "";
    descInput.value = "";

  } catch (err) {
    console.error(err);
    statusLine.textContent = "Failed to save protocol.";
  }
};



// ======================================================
// INIT
// ======================================================

loadTasks();
