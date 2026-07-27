#!/usr/bin/env python3
"""Interactive engagement x competence map (self-contained offline HTML).

One HTML per task, no server. In the browser you can:
  * pick ANY metric for the X and Y axis (defaults: participation vs accuracy),
  * drag the X and Y *criterion* splits to redraw the phenotype quadrants,
  * restrict to a subset of each mouse's sessions,
  * toggle / isolate individual mice,
  * follow each mouse SESSION BY SESSION: one dot per session, shaded faint
    (earliest shown) -> solid (latest), joined by an arrow (direction of travel).

Axis definitions (all per session, per mouse). HIT / FA use LICK timing relative
to the FSM's own ITI boundary -- the SAME definition as poke_lick_dashboard.py and
hit_fa_trajectory_analysis.py, so numbers stay consistent across dashboards. A
trial's response window is [0, iti_start); the ITI is [iti_start, iti_end]. Using
lick BOUTS (a run of licks; a gap > LICK_BOUT_GAP ends one):

    HIT (per trial) : a lick-bout onset BEFORE the ITI starts (a valid response).
    FA  (per trial) : a lick-bout onset DURING the ITI (an impulsive / late lick).

HIT and FA are scored independently, so each trial contributes 0, 1, or 2 to the
HIT+FA total. Then per session:

    participation = % of trials with ANY nose poke        (default X = engagement)
    accuracy      = HIT trials / (HIT trials + FA trials)  (default Y = competence)

Other selectable metrics (d', criterion, vigor, latencies, ...) are in METRICS.

Usage:
    python3 engagement_vs_competence_dashboard.py --task appetitive
    python3 engagement_vs_competence_dashboard.py --task both
"""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
from statistics import NormalDist, median

from plotly.offline import get_plotlyjs

import trial_history_analysis as TH  # loaders + task labels (read-only)
import learning_trajectories_analysis as LT  # lick-bout + colour/order helpers

_Z = NormalDist()  # standard normal for signal-detection d' / criterion

# (key, human label). The first two are the default axes (engagement vs competence).
METRICS = [
    ["participation", "participation = % trials with any nose poke  (%)  [engagement]"],
    ["accuracy", "accuracy = HITs / (HITs + FAs)  (%)  [competence]"],
    ["dprime", "d' sensitivity = Z(HIT rate) - Z(FA rate)  [competence]"],
    ["criterion_c", "criterion c = -0.5*(Z(HIT)+Z(FA))  (bias; <0 = liberal)"],
    ["hit_trial_rate", "HIT-trial rate = trials with a lick before ITI / trials  (%)"],
    ["fa_trial_rate", "FA-trial rate = trials with a lick during ITI / trials  (%)"],
    ["oncue_engagement", "response-window engagement = % trials with a poke before ITI  (%)"],
    ["reward_rate_engaged", "reward rate | engaged = % of participated trials rewarded  (%)"],
    ["hit_rate", "hit rate = % trials rewarded  (%)"],
    ["offcue_pokes", "off-cue pokes / trial (pre-cue or in ITI)"],
    ["pokes_per_trial", "poke vigor = nose pokes / trial"],
    ["licks_per_trial", "lick vigor = licks / trial"],
    ["latency", "latency to engage = median cue->first response-window poke  (s)"],
    ["lick_latency", "lick latency = median cue->first response-window lick  (s)"],
    ["n_trials", "session length (n trials)"],
]

# Phenotype quadrants (same thresholds as learner_criterion_analysis:
# ENGAGE_THRESH=50 participation, ACC_STRONG=70 accuracy). Each corner ->
# (label, colour). The splits are the user-adjustable X/Y criteria in the UI.
QUADRANTS = {
    "x_thresh": 50.0,
    "y_thresh": 70.0,
    "corners": {
        "tr": ["strong learners", "#2ca02c"],                    # high both
        "tl": ["knows rule,<br>low participation", "#1f77b4"],   # low x, high y
        "bl": ["non-learners", "#d62728"],                       # low both
        "br": ["impulsive /<br>engaged, inaccurate", "#ff7f0e"], # high x, low y
    },
}

_RESULTS_ROOT = Path(__file__).resolve().parent / "results"
_TASK_AREA = {"appetitive": "appetitive", "generalization": "generalization", "both": "cross_task"}


def _pct(num: float, den: float) -> float | None:
    return 100.0 * num / den if den else None


def _dprime_criterion(n_hit: int, n_fa: int, n: int) -> tuple[float | None, float | None]:
    """Signal-detection d' and criterion c from trial-level HIT/FA counts.

    Loglinear correction (Hautus 1995) keeps rates off 0/1 so Z stays finite:
    H = (hits + 0.5)/(n + 1), FA = (fa + 0.5)/(n + 1).
    """
    if not n:
        return None, None
    zh = _Z.inv_cdf((n_hit + 0.5) / (n + 1))
    zf = _Z.inv_cdf((n_fa + 0.5) / (n + 1))
    return zh - zf, -0.5 * (zh + zf)


def session_row(record: dict) -> dict:
    """All map metrics for one session, from its raw trials (lick-timing HIT/FA)."""
    trials = record["trials"]
    n = len(trials)
    n_hit = n_fa = n_anypoke = n_oncue = n_reward = 0
    n_engaged_reward = offcue_total = poke_total = lick_total = 0
    poke_latencies: list[float] = []
    lick_latencies: list[float] = []
    for t in trials:
        iti0, iti1 = t["iti_start"], t["iti_end"]
        pokes = t["nose_pokes"]
        licks = t["licks"]
        on_cue = [p for p in pokes if 0 <= p < iti0]        # poke in the response window
        off_cue = [p for p in pokes if p < 0 or p >= iti0]  # pre-cue or during ITI
        on_cue_licks = [lk for lk in licks if 0 <= lk < iti0]
        bouts = LT._lick_bout_onsets(licks)
        n_hit += any(0 <= o < iti0 for o in bouts)          # lick bout before ITI -> HIT
        n_fa += any(iti0 <= o <= iti1 for o in bouts)       # lick bout during ITI -> FA
        has_poke = bool(pokes)
        n_anypoke += 1 if has_poke else 0
        n_oncue += 1 if on_cue else 0
        n_reward += 1 if t["rewarded"] else 0
        n_engaged_reward += 1 if (has_poke and t["rewarded"]) else 0
        offcue_total += len(off_cue)
        poke_total += len(pokes)
        lick_total += len(licks)
        if on_cue:
            poke_latencies.append(min(on_cue))
        if on_cue_licks:
            lick_latencies.append(min(on_cue_licks))
    dprime, criterion_c = _dprime_criterion(n_hit, n_fa, n)
    return {
        "session": record["training_day"],
        "hits": n_hit,
        "false_alarms": n_fa,
        "n_trials": n,
        "accuracy": _pct(n_hit, n_hit + n_fa),
        "participation": _pct(n_anypoke, n),
        "dprime": dprime,
        "criterion_c": criterion_c,
        "hit_trial_rate": _pct(n_hit, n),
        "fa_trial_rate": _pct(n_fa, n),
        "oncue_engagement": _pct(n_oncue, n),
        "reward_rate_engaged": _pct(n_engaged_reward, n_anypoke),
        "hit_rate": _pct(n_reward, n),
        "offcue_pokes": (offcue_total / n) if n else None,
        "pokes_per_trial": (poke_total / n) if n else None,
        "licks_per_trial": (lick_total / n) if n else None,
        "latency": float(median(poke_latencies)) if poke_latencies else None,
        "lick_latency": float(median(lick_latencies)) if lick_latencies else None,
    }


def _rgb255(color) -> list[int]:
    return [int(round(255 * c)) for c in color[:3]]


def _payload(task: str, by_mouse: dict, mcolors: dict) -> dict:
    mice = LT._sorted_mice(by_mouse)
    data: dict[str, list[dict]] = {}
    max_sessions = 0
    for m in mice:
        recs = sorted(by_mouse[m], key=lambda r: r["training_day"])
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
        "default_x": "participation",
        "default_y": "accuracy",
        "quadrants": QUADRANTS,
        "max_sessions": max_sessions,
        "data": data,
    }


def write_dashboard(records: list[dict], out_dir: str) -> list[str]:
    """Write one interactive engagement x competence map HTML per task."""
    grouping: dict[str, dict[str, list[dict]]] = {}
    for r in records:
        grouping.setdefault(r["task"], {}).setdefault(r["mouse"], []).append(r)
    mcolors, _ = LT._mouse_colors(grouping)
    plotlyjs = get_plotlyjs()
    os.makedirs(out_dir, exist_ok=True)
    written = []
    for task, by_mouse in grouping.items():
        payload = _payload(task, by_mouse, mcolors)
        html = (_TEMPLATE
                .replace("__PLOTLYJS__", plotlyjs)
                .replace("__DATA__", json.dumps(payload))
                .replace("__TITLE__", payload["task_label"]))
        suffix = "" if len(grouping) == 1 else f"_{task}"
        path = os.path.join(out_dir, f"engagement_vs_competence_map{suffix}.html")
        with open(path, "w") as f:
            f.write(html)
        written.append(path)
    return written


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--task", choices=["appetitive", "generalization", "both"], default="both")
    parser.add_argument("--mouse", default=None, help="restrict to one mouse, e.g. m102")
    args = parser.parse_args()

    records: list[dict] = []
    if args.task in ("appetitive", "both"):
        print("Loading appetitive (tone) task ...")
        records += TH.load_appetitive(args.mouse)
    if args.task in ("generalization", "both"):
        print("Loading generalization (light) task ...")
        records += TH.load_generalization(args.mouse)
    if not records:
        print("No sessions found - nothing to do.")
        return 1

    out_dir = str(_RESULTS_ROOT / "engagement_vs_competence" / _TASK_AREA[args.task])
    paths = write_dashboard(records, out_dir)
    print(f"\nWrote {len(paths)} map(s) under '{out_dir}/' ({len(records)} sessions):")
    for p in paths:
        print(f"  {p}")
    return 0


_TEMPLATE = r"""<!doctype html>
<html><head><meta charset="utf-8"><title>__TITLE__ &mdash; engagement x competence map</title>
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
  <label><input id="quad" type="checkbox" checked> phenotype quadrants</label>
  <label id="qxwrap">X criterion <input id="qx" type="number" step="any" style="width:4.5em"></label>
  <label id="qywrap">Y criterion <input id="qy" type="number" step="any" style="width:4.5em"></label>
  <span class="hint">double-click a mouse in the legend to isolate it</span>
</div>
<div id="plot"></div>
<script>
const DATA = __DATA__;
const $ = id => document.getElementById(id);
const XSEL=$('xsel'), YSEL=$('ysel'), MODE=$('mode'),
      NIN=$('nin'), RFROM=$('rfrom'), RTO=$('rto'), CUSTOM=$('custom'),
      QUAD=$('quad'), QX=$('qx'), QY=$('qy');

DATA.metrics.forEach(([k,l])=>{
  [XSEL,YSEL].forEach(sel=>{const o=document.createElement('option');o.value=k;o.textContent=l;sel.appendChild(o);});
});
XSEL.value=DATA.default_x; YSEL.value=DATA.default_y;
RFROM.value=1; RTO.value=DATA.max_sessions;
RFROM.max=DATA.max_sessions; RTO.max=DATA.max_sessions;
NIN.value=Math.min(3,DATA.max_sessions);
QX.value=DATA.quadrants.x_thresh; QY.value=DATA.quadrants.y_thresh;

const label = k => (DATA.metrics.find(e=>e[0]===k)||[k,k])[1];
const rgb = c => `rgb(${c[0]},${c[1]},${c[2]})`;
const rgba = (c,a) => `rgba(${c[0]},${c[1]},${c[2]},${a})`;
const PLOT=$('plot');
let ANNOS=[], QUAD_ANNOS=[], HOOKED=false;

const hexRgba=(hex,a)=>{const n=parseInt(hex.slice(1),16);
  return `rgba(${(n>>16)&255},${(n>>8)&255},${n&255},${a})`;};

// 4 phenotype areas: faint shaded quadrants + dashed split lines (shapes) and a
// label per corner (annotations), split at the user's X/Y criteria.
function quadrants(xmin,xmax,ymin,ymax){
  const C=DATA.quadrants.corners, xt=+QX.value, yt=+QY.value;
  const rect=(x0,x1,y0,y1,hex)=>({type:'rect',xref:'x',yref:'y',x0,x1,y0,y1,
    fillcolor:hexRgba(hex,0.07),line:{width:0},layer:'below'});
  const line=(x0,x1,y0,y1)=>({type:'line',xref:'x',yref:'y',x0,x1,y0,y1,
    line:{color:'#888',dash:'dash',width:1},layer:'below'});
  const shapes=[rect(xt,xmax,yt,ymax,C.tr[1]), rect(xmin,xt,yt,ymax,C.tl[1]),
    rect(xmin,xt,ymin,yt,C.bl[1]), rect(xt,xmax,ymin,yt,C.br[1]),
    line(xt,xt,ymin,ymax), line(xmin,xmax,yt,yt)];
  const corner=(fx,fy,xa,ya,c)=>({xref:'x domain',yref:'y domain',x:fx,y:fy,
    xanchor:xa,yanchor:ya,text:c[0],showarrow:false,align:'center',
    font:{size:10,color:c[1]}});
  const annos=[corner(0.985,0.985,'right','top',C.tr),
    corner(0.015,0.985,'left','top',C.tl), corner(0.015,0.015,'left','bottom',C.bl),
    corner(0.985,0.015,'right','bottom',C.br)];
  return {shapes,annos};
}

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
  Plotly.relayout(PLOT,{annotations:ANNOS.concat(QUAD_ANNOS)});
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
        'HIT trials %{customdata[2]} &middot; FA trials %{customdata[3]} &middot; trials %{customdata[4]}<extra></extra>'
    });
    if(k>=2){ // arrowhead on the last hop -> direction of travel
      const p0=shown[k-2], p1=shown[k-1];
      ANNOS.push({x:p1.x,y:p1.y,ax:p0.x,ay:p0.y,xref:'x',yref:'y',axref:'x',ayref:'y',
        showarrow:true,arrowhead:2,arrowsize:1.3,arrowwidth:2,arrowcolor:rgb(c),
        standoff:4,text:'',_mouse:m,visible:!hiddenM});
    }
  });
  const showQuad=QUAD.checked;
  $('qxwrap').style.display=showQuad?'':'none';
  $('qywrap').style.display=showQuad?'':'none';
  const ax=t=>({title:{text:t},autorange:true,zeroline:false,showline:true,
                linecolor:'#444',gridcolor:'#eee'});
  const layout={
    title:{text:DATA.task_label+' &mdash; engagement x competence map'+
      '<br><sup>faint = earliest shown session &rarr; solid = latest &middot; arrow = last hop &middot; '+
      'click a mouse to toggle, double-click to isolate</sup>'},
    xaxis:ax(label(xk)), yaxis:ax(label(yk)),
    hovermode:'closest', legend:{title:{text:'mouse'}},
    plot_bgcolor:'white', paper_bgcolor:'white', margin:{t:70}};
  QUAD_ANNOS=[]; let shapes=[];
  const xs=[], ys=[]; traces.forEach(t=>{xs.push(...t.x); ys.push(...t.y);});
  if(showQuad && xs.length){
    // fix the axes to the data span (incl. the criteria) so the quadrant
    // rectangles fill the panel; autorange would ignore the shapes.
    const xt=+QX.value, yt=+QY.value;
    let x0=Math.min(...xs,xt), x1=Math.max(...xs,xt),
        y0=Math.min(...ys,yt), y1=Math.max(...ys,yt);
    const px=(x1-x0)*0.06||1, py=(y1-y0)*0.06||1;
    x0-=px; x1+=px; y0-=py; y1+=py;
    const q=quadrants(x0,x1,y0,y1);
    shapes=q.shapes; QUAD_ANNOS=q.annos;
    layout.xaxis.range=[x0,x1]; layout.xaxis.autorange=false;
    layout.yaxis.range=[y0,y1]; layout.yaxis.autorange=false;
  }
  layout.shapes=shapes; layout.annotations=ANNOS.concat(QUAD_ANNOS);
  const config={responsive:true, modeBarButtonsToRemove:['toImage'],
    modeBarButtonsToAdd:[{name:'Download PNG (named)', icon:Plotly.Icons.camera,
      click:gd=>Plotly.downloadImage(gd,{format:'png',width:1200,height:820,scale:2,filename:fileName()})}]};
  Plotly.react('plot', traces, layout, config).then(()=>{
    if(!HOOKED){ PLOT.on('plotly_restyle',syncArrows); HOOKED=true; }
  });
}

[XSEL,YSEL,MODE,NIN,RFROM,RTO,CUSTOM,QUAD,QX,QY].forEach(el=>{
  el.addEventListener('change',redraw); el.addEventListener('input',redraw);
});
redraw();
</script>
</body></html>"""


if __name__ == "__main__":
    raise SystemExit(main())
