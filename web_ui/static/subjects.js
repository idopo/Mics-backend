const list = document.getElementById("subjects-list");
const form = document.getElementById("create-form");
const input = document.getElementById("subject-name");
const errorBox = document.getElementById("error");

async function loadSubjects() {
  list.innerHTML = "";
  const resp = await fetch("/api/subjects");
  const subjects = await resp.json();

  subjects.forEach((s) => {
    const li = document.createElement("li");
    li.textContent = s.name;
    list.appendChild(li);
  });
}

form.addEventListener("submit", async (e) => {
  e.preventDefault();
  errorBox.textContent = "";

  const name = input.value.trim();
  if (!name) return;

  const resp = await fetch("/api/subjects", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ name }),
  });

  if (!resp.ok) {
    const text = await resp.text();
    errorBox.textContent = text;
    return;
  }

  input.value = "";
  await loadSubjects();
});

loadSubjects();
