let selectedSession = null;

async function loadSessions() {
  const res = await fetch(`/api/subjects/${SUBJECT}/sessions`);
  const runs = await res.json();

  const ul = document.getElementById("sessions");
  ul.innerHTML = "";

  runs.forEach(r => {
    const li = document.createElement("li");
    li.textContent = `Session ${r.session_id} (protocol ${r.protocol_id})`;
    li.onclick = () => {
      selectedSession = r.session_id;
      [...ul.children].forEach(x => x.classList.remove("selected"));
      li.classList.add("selected");
    };
    ul.appendChild(li);
  });
}

async function loadPilots() {
  const res = await fetch("/api/pilots");
  const pilots = await res.json();

  const sel = document.getElementById("pilot-select");
  pilots.forEach(p => {
    const o = document.createElement("option");
    o.value = p.id;
    o.textContent = p.name;
    sel.appendChild(o);
  });
}

document.getElementById("start-btn").onclick = async () => {
  if (!selectedSession) return;

  const pilotId = document.getElementById("pilot-select").value;
  const status = document.getElementById("status");

  status.textContent = "Starting...";

  const res = await fetch(`/api/sessions/${selectedSession}/start`, {
    method: "POST",
    headers: {"Content-Type": "application/json"},
    body: JSON.stringify({ pilot_id: pilotId })
  });

  status.textContent = res.ok ? "Session started" : "Failed";
};

loadSessions();
loadPilots();
