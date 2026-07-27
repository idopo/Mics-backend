#!/usr/bin/env python3
"""Self-contained interactive dashboard for the hit / false-alarm trajectory.

Builds ONE offline HTML file per task (plotly embedded, no server needed) in which
the viewer can, entirely in-browser:
  * pick ANY metric for the X and Y axis (drop-downs), not just accuracy vs success,
  * restrict to a subset of each mouse's sessions (all / first & last / first N /
    last N / ordinal range / early-mid-late thirds / an explicit ordinal list),
  * click a mouse in the legend to toggle it, double-click to isolate it,
  * hover a dot to read that session's numbers.

Every metric is precomputed per session from the SAME raw trials the static figures
use (so the definitions stay consistent with the rest of the project) and embedded
as JSON; a small vanilla-JS panel re-plots via Plotly.react() on any change.

Metrics offered (all per session, per mouse):
  accuracy          = hit bouts / (hit bouts + FA bouts)   (temporal precision)
  success rate      = hit bouts / trials                   (how often it scored)
  engagement (any)  = % trials with >=1 nose poke          (gross participation)
  on-cue engagement = % trials with a poke inside the cue window
  hit rate          = % trials rewarded (is_hit)
  competence        = hit rate among on-cue-engaged trials
  false-alarm rate  = FA bouts / trials
  off-cue pokes     = mean nose pokes outside the cue window per trial
  latency to engage = median cue -> first on-cue poke (s)
  session length    = n trials
"""
from __future__ import annotations

import json
import os
from statistics import median

from plotly.offline import get_plotlyjs

import trial_history_analysis as TH  # task labels
import learning_trajectories_analysis as LT  # lick-bout + colour helpers

# (key, human label). The first two are the default axes.
METRICS = [
    ["accuracy", "accuracy = hits / (hits + false alarms)  (%)"],
    ["success_rate", "success rate = hits / trials  (%)"],
    ["engagement_any", "engagement (any poke)  (%)"],
    ["engagement_oncue", "on-cue engagement  (%)"],
    ["hit_rate", "hit rate  (%)"],
    ["competence", "competence (accuracy | engaged)  (%)"],
    ["fa_rate", "false-alarm rate = FA / trials  (%)"],
    ["offcue", "off-cue pokes / trial"],
    ["latency", "latency to engage  (s)"],
    ["n_trials", "session length (n trials)"],
]


def _pct(num: float, den: float) -> float | None:
    return 100.0 * num / den if den else None


def session_row(record: dict) -> dict:
    """All dashboard metrics for one session, computed from its raw trials."""
    dur_key = record["dur_key"]
    trials = record["trials"]
    n = len(trials)
    hits = fa = 0
    n_anypoke = n_oncue = n_oncue_hit = n_hit = offcue_total = 0
    latencies: list[float] = []
    for t in trials:
        dur, iti0, iti1 = t[dur_key], t["iti_start"], t["iti_end"]
        for onset in LT._lick_bout_onsets(t["licks"]):
            if 0 <= onset < iti0:
                hits += 1
            elif iti0 <= onset <= iti1:
                fa += 1
        pokes = t["nose_pokes"]
        n_anypoke += 1 if pokes else 0
        oncue_pokes = [p for p in pokes if 0 <= p <= dur]
        on_cue = bool(oncue_pokes)
        n_oncue += on_cue
        n_hit += t["is_hit"]
        n_oncue_hit += on_cue and t["is_hit"]
        offcue_total += sum(1 for p in pokes if p < 0 or p > dur)
        if on_cue:
            latencies.append(min(oncue_pokes))
    return {
        "session": record["session"],
        "hits": hits,
        "false_alarms": fa,
        "accuracy": _pct(hits, hits + fa),
        "success_rate": _pct(hits, n),
        "engagement_any": _pct(n_anypoke, n),
        "engagement_oncue": _pct(n_oncue, n),
        "hit_rate": _pct(n_hit, n),
        "competence": _pct(n_oncue_hit, n_oncue),
        "fa_rate": _pct(fa, n),
        "offcue": (offcue_total / n) if n else None,
        "latency": float(median(latencies)) if latencies else None,
        "n_trials": n,
    }


def _rgb255(color) -> list[int]:
    return [int(round(255 * c)) for c in color[:3]]


def _payload(task: str, by_mouse: dict, mcolors: dict) -> dict:
    mice = LT._sorted_mice(by_mouse)
    data: dict[str, list[dict]] = {}
    max_sessions = 0
    for m in mice:
        recs = sorted(by_mouse[m], key=lambda r: r["session"])
        rows = []
        for ordinal, rec in enumerate(recs, 1):
            row = session_row(rec)
            row["ord"] = ordinal
            rows.append(row)
        data[m] = rows
        max_sessions = max(max_sessions, len(rows))
    return {
        "task_label": TH.TASK_LABELS.get(task, task),
        "mice": mice,
        "colors": {m: _rgb255(mcolors[m]) for m in mice},
        "metrics": METRICS,
        "default_x": "accuracy",
        "default_y": "success_rate",
        "max_sessions": max_sessions,
        "data": data,
    }


def write_dashboard(records: list[dict], out_dir: str) -> list[str]:
    """Write one interactive dashboard HTML per task. Returns the paths written."""
    grouping: dict[str, dict[str, list[dict]]] = {}
    for r in records:
        grouping.setdefault(r["task"], {}).setdefault(r["mouse"], []).append(r)
    mcolors, _ = LT._mouse_colors(grouping)
    plotlyjs = get_plotlyjs()
    written = []
    for task, by_mouse in grouping.items():
        payload = _payload(task, by_mouse, mcolors)
        html = (_TEMPLATE
                .replace("__PLOTLYJS__", plotlyjs)
                .replace("__DATA__", json.dumps(payload))
                .replace("__TITLE__", payload["task_label"]))
        suffix = "" if len(grouping) == 1 else f"_{task}"
        path = os.path.join(out_dir, f"hit_fa_trajectory_dashboard{suffix}.html")
        with open(path, "w") as f:
            f.write(html)
        written.append(path)
    return written


_TEMPLATE = r"""<!doctype html>
<html><head><meta charset="utf-8"><title>__TITLE__ — hit/FA dashboard</title>
<style>
  body{font-family:system-ui,Arial,sans-serif;margin:0;padding:14px;color:#222}
  #controls{display:flex;flex-wrap:wrap;gap:14px;align-items:center;
    padding:10px 12px;background:#f6f7f9;border:1px solid #e2e4e8;border-radius:8px;margin-bottom:8px}
  #controls label{font-size:13px;display:flex;gap:6px;align-items:center}
  select,input{font-size:13px;padding:2px 4px}
  #plot{width:100%;height:76vh}
  .hint{color:#777;font-size:12px}
</style>
<script>__PLOTLYJS__</script>
</head><body>
<div id="controls">
  <label>X axis <select id="xsel"></select></label>
  <label>Y axis <select id="ysel"></select></label>
  <label>Sessions
    <select id="mode">
      <option value="all">all</option>
      <option value="firstlast">first &amp; last</option>
      <option value="firstN">first N</option>
      <option value="lastN">last N</option>
      <option value="range">ordinal range</option>
      <option value="thirds">early / mid / late thirds</option>
      <option value="custom">custom list</option>
    </select>
  </label>
  <label id="nwrap">N <input id="nin" type="number" min="1" value="3" style="width:4em"></label>
  <label id="rwrap">from <input id="rfrom" type="number" min="1" style="width:4em">
    to <input id="rto" type="number" min="1" style="width:4em"></label>
  <label id="cwrap">ordinals <input id="custom" type="text" placeholder="1,4,7,10" style="width:9em"></label>
  <span class="hint">double-click a mouse in the legend to isolate it</span>
</div>
<div id="plot"></div>
<script>
const DATA = __DATA__;
const $ = id => document.getElementById(id);
const XSEL=$('xsel'), YSEL=$('ysel'), MODE=$('mode'),
      NIN=$('nin'), RFROM=$('rfrom'), RTO=$('rto'), CUSTOM=$('custom');

DATA.metrics.forEach(([k,l])=>{
  [XSEL,YSEL].forEach(sel=>{const o=document.createElement('option');o.value=k;o.textContent=l;sel.appendChild(o);});
});
XSEL.value=DATA.default_x; YSEL.value=DATA.default_y;
RFROM.value=1; RTO.value=DATA.max_sessions;
RFROM.max=DATA.max_sessions; RTO.max=DATA.max_sessions;
NIN.value=Math.min(3,DATA.max_sessions);

const label = k => (DATA.metrics.find(e=>e[0]===k)||[k,k])[1];
const rgb = c => `rgb(${c[0]},${c[1]},${c[2]})`;
const rgba = (c,a) => `rgba(${c[0]},${c[1]},${c[2]},${a})`;
const PLOT=$('plot');
let ANNOS=[], HOOKED=false;

function filterRows(rows){
  const mode=MODE.value;
  if(mode==='all') return rows;
  if(mode==='firstlast') return rows.length<=1?rows:[rows[0],rows[rows.length-1]];
  if(mode==='firstN'){const n=Math.max(1,+NIN.value||1);return rows.slice(0,n);}
  if(mode==='lastN'){const n=Math.max(1,+NIN.value||1);return rows.slice(Math.max(0,rows.length-n));}
  if(mode==='range'){const a=+RFROM.value,b=+RTO.value;return rows.filter(r=>r.ord>=a&&r.ord<=b);}
  if(mode==='custom'){
    const set=new Set(CUSTOM.value.split(',').map(s=>parseInt(s.trim())).filter(x=>!isNaN(x)));
    return rows.filter(r=>set.has(r.ord));
  }
  return rows;
}

function thirds(rows,xk,yk){
  const labels=['early','mid','late'], out=[], size=rows.length/3;
  const mean=a=>a.length?a.reduce((s,v)=>s+v,0)/a.length:null;
  const sum=a=>a.reduce((s,v)=>s+(v||0),0);
  for(let b=0;b<3;b++){
    const bucket=rows.slice(Math.floor(b*size), b===2?rows.length:Math.floor((b+1)*size));
    if(!bucket.length) continue;
    out.push({x:mean(bucket.map(r=>r[xk]).filter(v=>v!=null)),
              y:mean(bucket.map(r=>r[yk]).filter(v=>v!=null)),
              session:labels[b]+' ('+bucket.length+')', ord:b+1,
              hits:sum(bucket.map(r=>r.hits)), fa:sum(bucket.map(r=>r.false_alarms)),
              n:sum(bucket.map(r=>r.n_trials))});
  }
  return out;
}

function fileName(){
  const mode=MODE.value; let sess='all_sessions';
  if(mode==='firstlast') sess='first_and_last';
  else if(mode==='firstN') sess='first'+Math.max(1,+NIN.value||1);
  else if(mode==='lastN') sess='last'+Math.max(1,+NIN.value||1);
  else if(mode==='range') sess='sessions'+(+RFROM.value)+'-'+(+RTO.value);
  else if(mode==='thirds') sess='thirds';
  else if(mode==='custom') sess='custom_'+((CUSTOM.value.replace(/[^0-9]+/g,'-').replace(/^-|-$/g,''))||'none');
  const vis=(PLOT.data||[]).filter(t=>t.visible===true||t.visible===undefined).map(t=>t.name);
  const subj=(vis.length===0||vis.length===DATA.mice.length)?'all_subjects':vis.join('-');
  const task=DATA.task_label.replace(/[^A-Za-z0-9]+/g,'_').replace(/^_|_$/g,'');
  return task+'__X-'+XSEL.value+'__Y-'+YSEL.value+'__'+sess+'__'+subj;
}

function syncArrows(){
  const hidden=new Set((PLOT.data||[])
    .filter(t=>t.visible==='legendonly'||t.visible===false).map(t=>t.name));
  ANNOS.forEach(a=>a.visible=!hidden.has(a._mouse));
  Plotly.relayout(PLOT,{annotations:ANNOS});
}

function redraw(){
  const xk=XSEL.value, yk=YSEL.value, mode=MODE.value;
  $('nwrap').style.display=(mode==='firstN'||mode==='lastN')?'':'none';
  $('rwrap').style.display=(mode==='range')?'':'none';
  $('cwrap').style.display=(mode==='custom')?'':'none';
  const prevVis={}; (PLOT.data||[]).forEach(t=>{if(DATA.mice.includes(t.name))prevVis[t.name]=t.visible;});
  const traces=[]; ANNOS=[];
  DATA.mice.forEach(m=>{
    const rows=DATA.data[m]||[];
    let shown = mode==='thirds'
      ? thirds(rows,xk,yk)
      : filterRows(rows).map(r=>({x:r[xk],y:r[yk],session:r.session,ord:r.ord,
                                  hits:r.hits,fa:r.false_alarms,n:r.n_trials}));
    shown=shown.filter(p=>p.x!=null&&p.y!=null&&!isNaN(p.x)&&!isNaN(p.y));
    if(!shown.length) return;
    const c=DATA.colors[m], k=shown.length;
    const hiddenM=(prevVis[m]==='legendonly'||prevVis[m]===false);
    traces.push({
      type:'scatter', mode:'lines+markers', name:m, legendgroup:m,
      visible: prevVis[m]===undefined?true:prevVis[m],
      x:shown.map(p=>p.x), y:shown.map(p=>p.y),
      line:{color:rgb(c),width:2},
      marker:{size:shown.map((p,i)=>i===k-1?15:8),
              color:shown.map((p,i)=>rgba(c,0.35+0.65*(k>1?i/(k-1):1))),
              line:{color:rgb(c),width:1.2}},
      customdata:shown.map(p=>[p.session,p.ord,p.hits,p.fa,p.n]),
      hovertemplate:'<b>'+m+'</b> session %{customdata[0]} (#%{customdata[1]})<br>'+
        label(xk)+': %{x:.2f}<br>'+label(yk)+': %{y:.2f}<br>'+
        'hits %{customdata[2]} · FA %{customdata[3]} · trials %{customdata[4]}<extra></extra>'
    });
    if(k>=2){ // arrowhead on the last hop -> direction of travel
      const p0=shown[k-2], p1=shown[k-1];
      ANNOS.push({x:p1.x,y:p1.y,ax:p0.x,ay:p0.y,xref:'x',yref:'y',axref:'x',ayref:'y',
        showarrow:true,arrowhead:2,arrowsize:1.3,arrowwidth:2,arrowcolor:rgb(c),
        standoff:4,text:'',_mouse:m,visible:!hiddenM});
    }
  });
  const ax=t=>({title:{text:t},autorange:true,zeroline:false,showline:true,
                linecolor:'#444',gridcolor:'#eee'});
  const config={responsive:true, modeBarButtonsToRemove:['toImage'],
    modeBarButtonsToAdd:[{name:'Download PNG (named)', icon:Plotly.Icons.camera,
      click:gd=>Plotly.downloadImage(gd,{format:'png',width:1200,height:820,scale:2,filename:fileName()})}]};
  Plotly.react('plot', traces, {
    title:{text:DATA.task_label+' — hit / false-alarm trajectory'+
      '<br><sup>faint = earliest shown session → solid = latest · arrow = last hop · '+
      'click a mouse to toggle, double-click to isolate</sup>'},
    xaxis:ax(label(xk)), yaxis:ax(label(yk)), annotations:ANNOS,
    hovermode:'closest', legend:{title:{text:'mouse'}},
    plot_bgcolor:'white', paper_bgcolor:'white', margin:{t:70}
  }, config).then(()=>{
    if(!HOOKED){ PLOT.on('plotly_restyle',syncArrows); HOOKED=true; }
  });
}

[XSEL,YSEL,MODE,NIN,RFROM,RTO,CUSTOM].forEach(el=>{
  el.addEventListener('change',redraw); el.addEventListener('input',redraw);
});
redraw();
</script>
</body></html>"""
