let PROTOCOLS_CACHE = null;
let SUBJECTS_CACHE = null;


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


document.addEventListener("DOMContentLoaded", () => {
  // ======================================================
  // DOM
  // ======================================================

  const protocolsList = document.getElementById("protocols-list");
  const subjectsList = document.getElementById("subjects-list");
  const assignBtn = document.getElementById("assign-btn");
  const statusLine = document.getElementById("assign-status");

  // Guard: page mismatch
  if (!protocolsList || !subjectsList || !assignBtn) {
    console.warn("protocols.js loaded on non-protocols page");
    return;
  }

  // ======================================================
  // STATE
  // ======================================================

  let selectedProtocolId = null;

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
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });
    if (!resp.ok) throw new Error(`POST ${url} failed`);
    return resp.json();
  }

  // ======================================================
  // LOAD PROTOCOLS
  // ======================================================

  async function loadProtocols() {
    if (!PROTOCOLS_CACHE) {
      showSkeleton(protocolsList, 10);
      PROTOCOLS_CACHE = await apiGet("/api/protocols");
    } else {
      // If cached, no need to skeleton/flicker
      protocolsList.innerHTML = "";
    }
  
    const protocols = PROTOCOLS_CACHE;
    clearLoading(protocolsList);
  
    selectedProtocolId = null;
  
    protocols.forEach((protocol, idx) => {
      const li = makeAnimatedLi(protocol.name, Math.min(idx * 18, 180));
      li.dataset.protocolId = protocol.id;
  
      li.onclick = () => {
        selectedProtocolId = protocol.id;
        [...protocolsList.children].forEach(el => el.classList.remove("selected"));
        li.classList.add("selected");
      };
  
      protocolsList.appendChild(li);
    });
  }
  

  // ======================================================
  // LOAD SUBJECTS
  // ======================================================

  async function loadSubjects() {
    if (!SUBJECTS_CACHE) {
      SUBJECTS_CACHE = await apiGet("/api/subjects");
    }
  
    const subjects = SUBJECTS_CACHE;
  
    if (subjectsList.children.length === 0) {
      subjectsList.innerHTML = "";
    }
  
    subjects.forEach(subject => {
      const li = document.createElement("li");
      li.classList.add("subject-item");
      li.textContent = subject.name;
  
      li.onclick = () => {
        li.classList.toggle("selected");
      };
  
      subjectsList.appendChild(li);
    });
  }
  
  
    


  // ======================================================
  // ASSIGN + CREATE SESSION
  // ======================================================

  assignBtn.onclick = async () => {
    try {
      if (!selectedProtocolId) {
        statusLine.textContent = "Select a protocol first.";
        return;
      }

      const selectedSubjects = [
        ...subjectsList.querySelectorAll(".subject-item.selected"),
      ].map(li => li.textContent);
      

      if (selectedSubjects.length === 0) {
        statusLine.textContent = "Select at least one subject.";
        return;
      }

      statusLine.textContent = "Assigning and creating session…";

      const resp = await apiPost("/api/assign-protocol", {
        protocol_id: selectedProtocolId,
        subjects: selectedSubjects,
      });

      statusLine.textContent =
        `Session ${resp.session.session_id} created. Go to a pilot to start it.`;

    } catch (err) {
      console.error(err);
      statusLine.textContent = "Assignment failed.";
    }
  };

  // ======================================================
  // INIT
  // ======================================================

  (async function init() {
    try {
      await Promise.all([
        loadProtocols(),
        loadSubjects(),
      ]);
    } catch (err) {
      console.error("Init failed", err);
      statusLine.textContent = "Failed to load data.";
    }
  })();
});
