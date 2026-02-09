// subjects.js (self-contained) - FIXED skeleton cleanup

let SUBJECTS_CACHE = null;

const subjectsList = document.getElementById("subjects-list");
const form = document.getElementById("create-form");
const input = document.getElementById("subject-name");
const errorBox = document.getElementById("error");

// ---------------------------
// Helpers
// ---------------------------
function escapeHtml(s) {
  return String(s ?? "").replace(/[&<>"']/g, (c) => ({
    "&": "&amp;",
    "<": "&lt;",
    ">": "&gt;",
    '"': "&quot;",
    "'": "&#39;",
  }[c]));
}

function showSkeleton(container, rows = 8) {
  container.classList.add("is-loading");
  container.innerHTML = `
    <li class="skeleton-wrap" style="list-style:none; padding:0; margin:0;">
      <div class="skeleton-list">
        ${Array.from({ length: rows })
          .map(() => `<div class="skeleton-row"></div>`)
          .join("")}
      </div>
    </li>
  `;
}

// IMPORTANT: also removes skeleton markup
function clearLoading(container) {
  container.classList.remove("is-loading");
  // remove skeleton if present
  const sk = container.querySelector(".skeleton-wrap, .skeleton-list");
  if (sk) {
    container.innerHTML = "";
  }
}

function makeAnimatedLi(text, delayMs = 0) {
  const li = document.createElement("li");
  li.className = "fade-in-item";
  li.style.animationDelay = `${delayMs}ms`;
  li.textContent = text ?? "";
  return li;
}

async function apiGet(url) {
  const r = await fetch(url, { headers: { Accept: "application/json" } });
  if (!r.ok) throw new Error(`${r.status} ${r.statusText}`);
  return r.json();
}

// ---------------------------
// Main logic
// ---------------------------
async function loadSubjects({ force = false } = {}) {
  try {
    if (!subjectsList) throw new Error("Missing #subjects-list element");

    // Always clear list before rendering to avoid skeleton sticking around
    subjectsList.innerHTML = "";

    if (force) SUBJECTS_CACHE = null;

    if (!SUBJECTS_CACHE) {
      showSkeleton(subjectsList, 12);
      SUBJECTS_CACHE = await apiGet("/api/subjects");
    }

    const subjects = Array.isArray(SUBJECTS_CACHE) ? SUBJECTS_CACHE : [];

    // Remove skeleton + empty list
    clearLoading(subjectsList);
    subjectsList.innerHTML = "";

    if (!subjects.length) {
      const li = document.createElement("li");
      li.className = "muted";
      li.textContent = "No subjects yet";
      subjectsList.appendChild(li);
      return;
    }

    subjects.forEach((subject, idx) => {
      const name = subject?.name ?? "";
      const li = makeAnimatedLi(name, Math.min(idx * 14, 180));
      li.classList.add("subject-item");
      li.addEventListener("click", () => li.classList.toggle("selected"));
      subjectsList.appendChild(li);
    });
  } catch (e) {
    console.error("loadSubjects failed:", e);
    if (errorBox) errorBox.textContent = `Failed to load subjects: ${e.message || e}`;
    if (subjectsList) {
      subjectsList.classList.remove("is-loading");
      // keep page usable even on error
      if (!subjectsList.children.length) {
        const li = document.createElement("li");
        li.className = "muted";
        li.textContent = "Failed to load";
        subjectsList.appendChild(li);
      }
    }
  }
}

form?.addEventListener("submit", async (e) => {
  e.preventDefault();
  if (errorBox) errorBox.textContent = "";

  const name = input?.value?.trim();
  if (!name) return;

  try {
    const resp = await fetch("/api/subjects", {
      method: "POST",
      headers: { "Content-Type": "application/json", Accept: "application/json" },
      body: JSON.stringify({ name }),
    });

    if (!resp.ok) {
      const text = await resp.text();
      if (errorBox) errorBox.textContent = text;
      return;
    }

    if (input) input.value = "";

    // refresh list from server
    await loadSubjects({ force: true });
  } catch (err) {
    console.error(err);
    if (errorBox) errorBox.textContent = `Create failed: ${err.message || err}`;
  }
});

loadSubjects();
