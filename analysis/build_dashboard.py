"""Generate an interactive single-file HTML index of every analysis output.

Walks analysis/results/, classifies each figure / interactive dashboard / table
by module, task-context, mouse and granularity, and emits results/index.html with
an embedded manifest. Re-run after producing new results:

    python analysis/build_dashboard.py
"""

from __future__ import annotations

import json
import re
from pathlib import Path

RESULTS = Path(__file__).resolve().parent / "results"

# Human labels + one-line descriptions for each analysis module (result type).
MODULES = {
    "overview": ("Overview", "Learning curves, engagement, participation vs competence"),
    "learning_curves": ("Learning curves", "Per-session hit-rate / d-prime trajectories"),
    "learning_trajectories": ("Learning trajectories", "Poke vs on-cue lick evolution across sessions"),
    "learner_criterion": ("Learner criterion", "Sessions-to-criterion and learner classification"),
    "hit_fa_trajectory": ("Hit / FA trajectory", "Hit-rate and false-alarm evolution"),
    "engagement_bouts": ("Engagement bouts", "Bout structure, rasters, hit-by-context"),
    "trial_engagement_licks": ("Trial engagement (licks)", "Lick engagement per trial"),
    "on_off_cue": ("On / off cue", "Reward vs off-cue and ITI licking timing"),
    "action_sequence": ("Action sequence", "Poke->lick->reward chains and transitions"),
    "trial_history": ("Trial history", "Win-stay / lose-shift and sequential effects"),
    "poke_lick_trajectory": ("Poke / lick trajectory", "Poke and lick trajectories over sessions"),
    "punishment": ("Punishment", "ITI punishment effects on behaviour"),
    "catch_vs_complete": ("Catch vs complete", "Catch versus completed-trial comparison"),
    "extinction": ("Extinction", "Within-session extinction decay"),
    "bining": ("Session binning", "Time-binned profiles, ROC and bout barplots"),
    "level1_characterization": ("Level-1 characterization", "Per-mouse trial rasters at level 1"),
    "cross_task_transition": ("Cross-task transition", "Appetitive -> generalization transfer"),
}

# Canonical task-context labels.
CONTEXTS = {
    "appetitive": "Appetitive",
    "generalization": "Generalization",
    "cross_task": "Cross-task",
    "within_session": "Within-session",
    "appetitive_to_generalization": "Appetitive -> Generalization",
    "trial_rasters_by_mouse": "Appetitive",  # level-1 rasters are appetitive
}

KIND_BY_EXT = {".png": "figure", ".svg": "figure", ".html": "dashboard",
               ".csv": "table", ".txt": "note"}


def classify_granularity(rel: str, name: str) -> str:
    low = (rel + "/" + name).lower()
    if "raster" in low:
        return "raster"
    if "by_mouse" in low or "_grid" in low or "by_subject" in low:
        return "by-mouse"
    if "by_session" in low:
        return "by-session"
    if "roc" in low:
        return "roc"
    if "summary" in low or "group" in low:
        return "group"
    return "group"


def find_mouse(rel: str, name: str) -> str | None:
    m = re.search(r"m(\d+)", name) or re.search(r"m(\d+)", rel)
    return f"m{m.group(1)}" if m else None


def prettify(name: str) -> str:
    stem = re.sub(r"\.(png|svg|html|csv|txt)$", "", name)
    stem = stem.replace("_", " ").strip()
    return stem[:1].upper() + stem[1:] if stem else name


def build_manifest() -> list[dict]:
    items = []
    for path in sorted(RESULTS.rglob("*")):
        if path.is_dir():
            continue
        rel_check = path.relative_to(RESULTS).as_posix()
        if "/" not in rel_check:  # canonical/meta files in results root (index, inventory)
            continue
        ext = path.suffix.lower()
        kind = KIND_BY_EXT.get(ext)
        if kind is None:
            continue
        rel = path.relative_to(RESULTS).as_posix()
        parts = rel.split("/")
        module = parts[0]
        # Skip SVG when a same-named PNG exists (avoid duplicate cards).
        if ext == ".svg" and path.with_suffix(".png").exists():
            continue
        context_key = parts[1] if len(parts) > 1 else ""
        context = CONTEXTS.get(context_key, "")
        if not context:
            # Files sitting directly in a module dir (no context subdir).
            context = "Appetitive" if module == "level1_characterization" else "Other"
        items.append({
            "src": rel,
            "kind": kind,
            "module": module,
            "module_label": MODULES.get(module, (module, ""))[0],
            "context": context,
            "context_key": context_key if context else "",
            "mouse": find_mouse(rel, path.name),
            "gran": classify_granularity(rel, path.name),
            "title": prettify(path.name),
            "size": path.stat().st_size,
        })
    return items


def load_sessions() -> list[dict]:
    """Read the canonical session inventory (session_inventory.csv) if present."""
    path = RESULTS / "session_inventory.csv"
    if not path.exists():
        return []
    import csv
    with open(path, newline="") as f:
        rows = list(csv.DictReader(f))
    for r in rows:
        r["session"] = int(r["session"])
        r["n_trials"] = int(r["n_trials"])
    return rows


def render(manifest: list[dict]) -> str:
    modules_meta = {k: {"label": v[0], "desc": v[1]} for k, v in MODULES.items()}
    data = json.dumps({"items": manifest, "modules": modules_meta,
                       "sessions": load_sessions()}, separators=(",", ":"))
    return HTML_TEMPLATE.replace("/*__DATA__*/null", data)


HTML_TEMPLATE = r"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>MICS Analysis Dashboard</title>
<style>
  :root{
    --bg:#f6f7f9; --panel:#ffffff; --ink:#1a1c22; --muted:#6b7280;
    --line:#e4e7ec; --accent:#3b6cff; --accent-soft:#e8eeff; --chip:#eef1f5;
    --shadow:0 1px 3px rgba(16,24,40,.06),0 1px 2px rgba(16,24,40,.04);
  }
  @media (prefers-color-scheme:dark){
    :root{--bg:#0f1115;--panel:#171a21;--ink:#e7e9ee;--muted:#9aa2b1;
      --line:#262b34;--accent:#5b82ff;--accent-soft:#1c2740;--chip:#20242d;
      --shadow:0 1px 3px rgba(0,0,0,.4);}
  }
  *{box-sizing:border-box}
  body{margin:0;font:15px/1.5 -apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,Helvetica,Arial,sans-serif;
    background:var(--bg);color:var(--ink);-webkit-font-smoothing:antialiased}
  header{position:sticky;top:0;z-index:20;background:var(--panel);border-bottom:1px solid var(--line);
    padding:14px 20px 0}
  .htop{display:flex;align-items:baseline;gap:12px;flex-wrap:wrap;margin-bottom:10px}
  h1{font-size:19px;margin:0;font-weight:650;letter-spacing:-.01em}
  .count{color:var(--muted);font-size:13px}
  .search{margin-left:auto;display:flex;gap:8px;align-items:center}
  .search input{background:var(--bg);border:1px solid var(--line);border-radius:8px;
    padding:7px 11px;color:var(--ink);font-size:14px;width:230px}
  .search input:focus{outline:2px solid var(--accent-soft);border-color:var(--accent)}
  .filters{display:flex;flex-direction:column;gap:8px;padding-bottom:12px}
  .frow{display:flex;gap:6px;align-items:center;flex-wrap:wrap}
  .flabel{font-size:11px;text-transform:uppercase;letter-spacing:.06em;color:var(--muted);
    width:78px;flex:none;font-weight:600}
  .chip{border:1px solid var(--line);background:var(--chip);color:var(--ink);border-radius:20px;
    padding:4px 12px;font-size:13px;cursor:pointer;transition:.12s;user-select:none;white-space:nowrap}
  .chip:hover{border-color:var(--accent)}
  .chip.on{background:var(--accent);border-color:var(--accent);color:#fff}
  .chip .n{opacity:.6;font-size:11px;margin-left:4px}
  .chip.on .n{opacity:.85}
  main{padding:20px;max-width:1600px;margin:0 auto}
  .grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(300px,1fr));gap:16px}
  .card{background:var(--panel);border:1px solid var(--line);border-radius:12px;overflow:hidden;
    box-shadow:var(--shadow);display:flex;flex-direction:column;transition:.12s}
  .card:hover{border-color:var(--accent);transform:translateY(-1px)}
  .thumb{background:#fff;aspect-ratio:4/3;display:flex;align-items:center;justify-content:center;
    overflow:hidden;cursor:zoom-in;position:relative}
  .thumb img{width:100%;height:100%;object-fit:contain;display:block}
  .thumb.doc{cursor:pointer;background:var(--accent-soft);color:var(--accent);
    flex-direction:column;gap:6px;font-weight:600}
  .thumb.doc .big{font-size:30px}
  .cbody{padding:10px 12px;display:flex;flex-direction:column;gap:7px}
  .ctitle{font-size:13.5px;font-weight:600;line-height:1.3}
  .tags{display:flex;gap:5px;flex-wrap:wrap}
  .tag{font-size:10.5px;padding:2px 7px;border-radius:5px;background:var(--chip);color:var(--muted);
    text-transform:uppercase;letter-spacing:.03em;font-weight:600}
  .tag.mod{background:var(--accent-soft);color:var(--accent)}
  .tag.mouse{background:#ffe9d6;color:#b5540e}
  @media (prefers-color-scheme:dark){.tag.mouse{background:#3a2410;color:#f0a35e}}
  .empty{text-align:center;color:var(--muted);padding:60px 20px;font-size:15px}
  /* lightbox */
  .lb{position:fixed;inset:0;background:rgba(10,12,16,.86);z-index:100;display:none;
    align-items:center;justify-content:center;padding:24px;backdrop-filter:blur(3px)}
  .lb.open{display:flex}
  .lb-inner{max-width:96vw;max-height:94vh;display:flex;flex-direction:column;gap:10px}
  .lb-inner img{max-width:96vw;max-height:86vh;object-fit:contain;border-radius:8px;background:#fff}
  .lb-inner iframe{width:92vw;height:86vh;border:0;border-radius:8px;background:#fff}
  .lb-bar{display:flex;gap:12px;align-items:center;color:#e7e9ee;font-size:14px}
  .lb-bar a{color:#9db8ff;text-decoration:none}
  .lb-bar a:hover{text-decoration:underline}
  .lb-close{margin-left:auto;cursor:pointer;font-size:22px;line-height:1;color:#cfd4dd;
    background:none;border:0}
  .reset{font-size:12px;color:var(--accent);cursor:pointer;background:none;border:0;padding:4px}
  /* view tabs */
  .tabs{display:flex;gap:4px;margin-right:6px}
  .tab{border:1px solid var(--line);background:var(--chip);color:var(--ink);border-radius:8px;
    padding:5px 14px;font-size:13.5px;font-weight:600;cursor:pointer}
  .tab.on{background:var(--accent);border-color:var(--accent);color:#fff}
  .hide{display:none !important}
  /* sessions view */
  .swrap{padding:20px;max-width:1500px;margin:0 auto}
  .snote{color:var(--muted);font-size:13px;margin:0 0 14px;line-height:1.5}
  .snote a{color:var(--accent)}
  .smatrix,.stable{border-collapse:collapse;font-size:13px;width:100%;
    background:var(--panel);border:1px solid var(--line);border-radius:10px;overflow:hidden}
  .smatrix{margin-bottom:24px;max-width:560px}
  .smatrix th,.smatrix td,.stable th,.stable td{padding:7px 12px;text-align:left;
    border-bottom:1px solid var(--line)}
  .smatrix th,.stable th{background:var(--chip);font-weight:600;position:sticky;top:0;
    text-transform:uppercase;font-size:11px;letter-spacing:.04em;color:var(--muted)}
  .smatrix td:not(:first-child),.smatrix th:not(:first-child){text-align:center}
  .stable td.num{text-align:right;font-variant-numeric:tabular-nums}
  .stable tr.oob td{background:rgba(214,138,14,.10);color:#a35a05}
  @media (prefers-color-scheme:dark){.stable tr.oob td{background:rgba(240,163,94,.10);color:#f0a35e}}
  .badge{font-size:11px;padding:1px 7px;border-radius:5px;font-weight:600}
  .badge.ok{background:#e5f6ec;color:#1a7f43}
  .badge.no{background:#fce9d2;color:#a35a05}
  @media (prefers-color-scheme:dark){.badge.ok{background:#12331f;color:#5fce8a}
    .badge.no{background:#3a2410;color:#f0a35e}}
  .sh{font-size:15px;font-weight:650;margin:0 0 10px}
</style>
</head>
<body>
<header>
  <div class="htop">
    <h1>MICS Analysis Dashboard</h1>
    <div class="tabs">
      <button class="tab on" data-view="figures">Figures</button>
      <button class="tab" data-view="sessions">Sessions</button>
    </div>
    <span class="count" id="count"></span>
    <div class="search">
      <input id="q" type="search" placeholder="Search titles...">
      <button class="reset" id="reset">Reset</button>
    </div>
  </div>
  <div class="filters" id="fig-filters">
    <div class="frow" data-dim="module"><span class="flabel">Analysis</span></div>
    <div class="frow" data-dim="context"><span class="flabel">Task</span></div>
    <div class="frow" data-dim="mouse"><span class="flabel">Mouse</span></div>
    <div class="frow" data-dim="gran"><span class="flabel">View</span></div>
  </div>
  <div class="filters hide" id="sess-filters">
    <div class="frow" data-sdim="task"><span class="flabel">Task</span></div>
    <div class="frow" data-sdim="mouse"><span class="flabel">Mouse</span></div>
  </div>
</header>
<main id="figures-view">
  <div class="grid" id="grid"></div>
  <div class="empty" id="empty" style="display:none">No results match these filters.</div>
</main>
<div class="swrap hide" id="sessions-view">
  <p class="snote">
    <strong>Canonical session list for this dataset.</strong>
    A session = one mouse + one lab-local calendar day; same-day files are merged.
    Days outside the 50-72 trial band are flagged <span class="badge no">out of band</span>
    and excluded from analyses. Source of truth: <a href="session_inventory.csv">session_inventory.csv</a>
    &middot; <a href="SESSIONS.md">SESSIONS.md</a>.
  </p>
  <h2 class="sh">Sessions per mouse &times; task <span class="count" style="font-weight:400">(valid / total)</span></h2>
  <div style="overflow-x:auto"><table class="smatrix" id="smatrix"></table></div>
  <h2 class="sh" id="sdetail-h">Session detail</h2>
  <div style="overflow-x:auto"><table class="stable" id="stable"></table></div>
</div>
<div class="lb" id="lb">
  <div class="lb-inner">
    <div class="lb-bar">
      <span id="lb-title"></span>
      <a id="lb-open" target="_blank" rel="noopener">Open file &#8599;</a>
      <button class="lb-close" id="lb-close">&times;</button>
    </div>
    <div id="lb-media"></div>
  </div>
</div>
<script>
const DATA = /*__DATA__*/null;
const ITEMS = DATA.items;
const GRAN_LABEL = {group:"Group",  "by-mouse":"By mouse", "by-session":"By session",
                    raster:"Raster", roc:"ROC"};
const KIND_ICON = {dashboard:["◰","Interactive"], table:["▦","CSV table"], note:["≡","Notes"]};
const sel = {module:new Set(), context:new Set(), mouse:new Set(), gran:new Set()};
let query = "";

function uniq(dim){
  const m = new Map();
  for(const it of ITEMS){
    const v = it[dim]; if(!v) continue;
    m.set(v, (m.get(v)||0)+1);
  }
  return [...m.entries()].sort((a,b)=>{
    if(dim==="mouse") return (+a[0].slice(1))-(+b[0].slice(1));
    return b[1]-a[1];
  });
}
function labelFor(dim,v){
  if(dim==="module") return (DATA.modules[v]||{}).label || v;
  if(dim==="gran") return GRAN_LABEL[v]||v;
  return v;
}
function buildChips(){
  for(const dim of ["module","context","mouse","gran"]){
    const row = document.querySelector(`.frow[data-dim="${dim}"]`);
    for(const [v,n] of uniq(dim)){
      const c = document.createElement("span");
      c.className="chip"; c.dataset.v=v;
      c.innerHTML = `${labelFor(dim,v)}<span class="n">${n}</span>`;
      c.onclick=()=>{ sel[dim].has(v)?sel[dim].delete(v):sel[dim].add(v);
        c.classList.toggle("on"); render(); };
      row.appendChild(c);
    }
  }
}
function match(it){
  for(const dim of ["module","context","mouse","gran"]){
    if(sel[dim].size && !sel[dim].has(it[dim])) return false;
  }
  if(query && !it.title.toLowerCase().includes(query) &&
     !it.module.toLowerCase().includes(query)) return false;
  return true;
}
function render(){
  const grid=document.getElementById("grid"); grid.innerHTML="";
  const rows = ITEMS.filter(match);
  document.getElementById("empty").style.display = rows.length?"none":"block";
  document.getElementById("count").textContent =
     `${rows.length} of ${ITEMS.length} outputs`;
  const frag=document.createDocumentFragment();
  for(const it of rows){
    const card=document.createElement("div"); card.className="card";
    let thumb;
    if(it.kind==="figure"){
      thumb=`<div class="thumb" data-src="${it.src}"><img loading="lazy" src="${it.src}" alt=""></div>`;
    }else{
      const [icon,txt]=KIND_ICON[it.kind]||["□","File"];
      thumb=`<div class="thumb doc" data-src="${it.src}" data-kind="${it.kind}">
               <span class="big">${icon}</span><span>${txt}</span></div>`;
    }
    const tags=[`<span class="tag mod">${it.module_label}</span>`];
    if(it.context) tags.push(`<span class="tag">${it.context}</span>`);
    if(it.mouse) tags.push(`<span class="tag mouse">${it.mouse}</span>`);
    if(it.gran && it.gran!=="group") tags.push(`<span class="tag">${GRAN_LABEL[it.gran]||it.gran}</span>`);
    card.innerHTML=thumb+`<div class="cbody"><div class="ctitle">${it.title}</div>
        <div class="tags">${tags.join("")}</div></div>`;
    frag.appendChild(card);
  }
  grid.appendChild(frag);
}
// lightbox
const lb=document.getElementById("lb"), lbMedia=document.getElementById("lb-media");
function openLb(src,kind,title){
  document.getElementById("lb-title").textContent=title||src;
  document.getElementById("lb-open").href=src;
  if(kind==="dashboard"){
    lbMedia.innerHTML=`<iframe src="${src}"></iframe>`;
  }else if(kind==="figure"||!kind){
    lbMedia.innerHTML=`<img src="${src}" alt="">`;
  }else{ // csv / note -> just open in new tab
    window.open(src,"_blank"); return;
  }
  lb.classList.add("open");
}
document.getElementById("grid").addEventListener("click",e=>{
  const t=e.target.closest(".thumb"); if(!t) return;
  const card=t.closest(".card");
  openLb(t.dataset.src, t.dataset.kind || "figure",
         card.querySelector(".ctitle").textContent);
});
function closeLb(){lb.classList.remove("open");lbMedia.innerHTML="";}
document.getElementById("lb-close").onclick=closeLb;
lb.onclick=e=>{if(e.target===lb)closeLb();};
document.addEventListener("keydown",e=>{if(e.key==="Escape")closeLb();});
// search + reset
document.getElementById("q").addEventListener("input",e=>{query=e.target.value.toLowerCase().trim();render();});
document.getElementById("reset").onclick=()=>{
  for(const d in sel)sel[d].clear();
  document.querySelectorAll(".chip.on").forEach(c=>c.classList.remove("on"));
  document.getElementById("q").value=""; query=""; render();
};
// ---- sessions view ----
const SESSIONS = DATA.sessions || [];
const TASK_ORDER = ["appetitive","generalization","extinction"];
const ssel = {task:new Set(), mouse:new Set()};
const sTasks = TASK_ORDER.filter(t=>SESSIONS.some(s=>s.task===t))
   .concat([...new Set(SESSIONS.map(s=>s.task))].filter(t=>!TASK_ORDER.includes(t)));
const sMice = [...new Set(SESSIONS.map(s=>s.mouse))].sort((a,b)=>+a.slice(1)-+b.slice(1));

function buildSessionChips(){
  const rowT=document.querySelector('.frow[data-sdim="task"]');
  for(const t of sTasks){
    const c=document.createElement("span"); c.className="chip"; c.textContent=t;
    c.onclick=()=>{ssel.task.has(t)?ssel.task.delete(t):ssel.task.add(t);
      c.classList.toggle("on"); renderSessions();}; rowT.appendChild(c);
  }
  const rowM=document.querySelector('.frow[data-sdim="mouse"]');
  for(const m of sMice){
    const c=document.createElement("span"); c.className="chip"; c.textContent=m;
    c.onclick=()=>{ssel.mouse.has(m)?ssel.mouse.delete(m):ssel.mouse.add(m);
      c.classList.toggle("on"); renderSessions();}; rowM.appendChild(c);
  }
}
function renderMatrix(){
  const el=document.getElementById("smatrix");
  let h=`<tr><th>mouse</th>${sTasks.map(t=>`<th>${t}</th>`).join("")}</tr>`;
  for(const m of sMice){
    h+=`<tr><td><strong>${m}</strong></td>`;
    for(const t of sTasks){
      const rs=SESSIONS.filter(s=>s.mouse===m&&s.task===t);
      const v=rs.filter(s=>s.valid==="yes").length;
      h+=`<td>${rs.length?`${v} / ${rs.length}`:"&ndash;"}</td>`;
    }
    h+="</tr>";
  }
  el.innerHTML=h;
}
function renderSessions(){
  const rows=SESSIONS.filter(s=>
    (!ssel.task.size||ssel.task.has(s.task)) &&
    (!ssel.mouse.size||ssel.mouse.has(s.mouse)));
  const t=document.getElementById("stable");
  let h=`<tr><th>task</th><th>mouse</th><th>session</th><th>date</th>
         <th>trials</th><th>status</th></tr>`;
  for(const s of rows){
    const oob=s.valid!=="yes";
    h+=`<tr class="${oob?"oob":""}"><td>${s.task}</td><td>${s.mouse}</td>
        <td class="num">${s.session}</td><td>${s.date}</td>
        <td class="num">${s.n_trials}</td>
        <td><span class="badge ${oob?"no":"ok"}">${oob?"out of band":"valid"}</span></td></tr>`;
  }
  t.innerHTML=h;
  document.getElementById("sdetail-h").textContent=
     `Session detail (${rows.length} of ${SESSIONS.length})`;
}
// ---- view switching ----
let view="figures";
function setView(v){
  view=v;
  document.querySelectorAll(".tab").forEach(b=>b.classList.toggle("on",b.dataset.view===v));
  const fig=v==="figures";
  document.getElementById("figures-view").classList.toggle("hide",!fig);
  document.getElementById("fig-filters").classList.toggle("hide",!fig);
  document.getElementById("sessions-view").classList.toggle("hide",fig);
  document.getElementById("sess-filters").classList.toggle("hide",fig);
  document.querySelector(".search").classList.toggle("hide",!fig);
  document.getElementById("count").classList.toggle("hide",!fig);
}
document.querySelectorAll(".tab").forEach(b=>b.onclick=()=>setView(b.dataset.view));

buildChips(); render();
if(SESSIONS.length){ buildSessionChips(); renderMatrix(); renderSessions(); }
else{ document.querySelector('.tab[data-view="sessions"]').classList.add("hide"); }
</script>
</body>
</html>
"""


def main() -> None:
    manifest = build_manifest()
    out = RESULTS / "index.html"
    out.write_text(render(manifest), encoding="utf-8")
    kinds = {}
    for it in manifest:
        kinds[it["kind"]] = kinds.get(it["kind"], 0) + 1
    print(f"Wrote {out} with {len(manifest)} items: {kinds}")


if __name__ == "__main__":
    main()
