#!/usr/bin/env python3
"""Within-trial time course (no binning) of pokes / licks, per task (Gili).

Instead of the 6 semantic bins, this walks CONTINUOUS time from cue onset in small
fixed steps (DT). At each step it pools across trials that are still inside the trial
at that time (iti_end > t), so the line naturally thins out at long times. Same
reference areas as the binned figure: the ON-CUE window shaded blue and the
ADDED-ITI (punishment) region shaded red. Same Show / session controls as the
profile dashboard: all mice, or one mouse across its sessions.

Usage:
    python3 bin_timecourse.py --task appetitive
    python3 bin_timecourse.py --task both
"""
from __future__ import annotations

import argparse
import json
import math
import os
import sys
from pathlib import Path

from plotly.offline import get_plotlyjs

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import trial_history_analysis as TH  # noqa: E402  loaders + task labels
import learning_trajectories_analysis as LT  # noqa: E402  colour/order helpers
import bin_trial_analysis as B  # noqa: E402  compute_nominal_iti

DT = float(os.environ.get("MICS_TC_DT", "0.5"))          # time step (s)
TMAX = float(os.environ.get("MICS_TC_TMAX", "60"))       # max time from cue onset (s)
MIN_TRIALS = int(os.environ.get("MICS_TC_MIN_TRIALS", "10"))  # drop sparse tail

Y_METRICS = [
    ["lick_rate", "lick rate = % trials with a lick in the step  (%)"],
    ["poke_rate", "nose-poke rate = % trials with a poke in the step  (%)"],
    ["licks_per_poke", "licks per nose poke  (Σ licks / Σ pokes in step)"],
    ["mean_licks", "mean licks per trial in the step"],
    ["mean_pokes", "mean nose pokes per trial in the step"],
]

_RESULTS_ROOT = Path(__file__).resolve().parent.parent / "results"
_TASK_AREA = {"appetitive": "appetitive", "generalization": "generalization", "both": "cross_task"}


def timecourse(trials: list[dict]) -> list[dict]:
    """PSTH across trials: for each DT step [t, t+DT) up to TMAX, the rate of pokes /
    licks over trials still inside the trial at t (iti_end > t)."""
    nb = int(math.ceil(TMAX / DT))
    n = [0] * nb
    poke_occ = [0] * nb
    lick_occ = [0] * nb
    pokes = [0] * nb
    licks = [0] * nb
    for tr in trials:
        if tr["cue_dur"] <= 0:
            continue
        reach = min(nb, int(math.ceil(tr["iti_end"] / DT)))  # steps within this trial
        if reach <= 0:
            continue
        for k in range(reach):
            n[k] += 1
        pb, lb = set(), set()
        for p in tr["nose_pokes"]:
            k = int(p // DT)
            if 0 <= k < reach:
                pokes[k] += 1
                pb.add(k)
        for lk in tr["licks"]:
            k = int(lk // DT)
            if 0 <= k < reach:
                licks[k] += 1
                lb.add(k)
        for k in pb:
            poke_occ[k] += 1
        for k in lb:
            lick_occ[k] += 1
    rows = []
    for k in range(nb):
        if n[k] < MIN_TRIALS:
            break  # trials reaching t only decreases — stop at the sparse tail
        rows.append({
            "t": round((k + 0.5) * DT, 3),
            "n_trials": n[k],
            "lick_rate": 100.0 * lick_occ[k] / n[k],
            "poke_rate": 100.0 * poke_occ[k] / n[k],
            "licks_per_poke": (licks[k] / pokes[k]) if pokes[k] else None,
            "mean_licks": licks[k] / n[k],
            "mean_pokes": pokes[k] / n[k],
        })
    return rows


def _rgb255(color) -> list[int]:
    return [int(round(255 * c)) for c in color[:3]]


def _band_meta(trials: list[dict], nominal_iti: float) -> dict:
    tv = [t for t in trials if t["cue_dur"] > 0]
    if not tv:
        return {"mean_cue": 0.0, "band": [0.0, 0.0]}
    mc = sum(t["cue_dur"] for t in tv) / len(tv)
    bs = sum(t["iti_start"] for t in tv) / len(tv) + nominal_iti
    be = sum(t["iti_end"] for t in tv) / len(tv)
    return {"mean_cue": mc, "band": [bs, max(bs, be)]}


def build_payload(task: str, records: list[dict], mcolors: dict) -> dict:
    by_mouse: dict[str, list[dict]] = {}
    for r in records:
        by_mouse.setdefault(r["mouse"], []).extend(r["trials"])
    mice = LT._sorted_mice(by_mouse)
    all_trials = [t for ts in by_mouse.values() for t in ts]
    nominal_iti = B.compute_nominal_iti(all_trials)
    data = {m: timecourse(by_mouse[m]) for m in mice}
    data["ALL"] = timecourse(all_trials)
    sessions: dict[str, list[dict]] = {}
    for r in records:
        sessions.setdefault(r["mouse"], []).append(
            {"session": r["training_day"], "rows": timecourse(r["trials"])})
    for m in sessions:
        sessions[m].sort(key=lambda s: s["session"])
    colors = {m: _rgb255(mcolors[m]) for m in mice}
    colors["ALL"] = [20, 20, 20]
    band_meta = {m: _band_meta(by_mouse[m], nominal_iti) for m in mice}
    band_meta["ALL"] = _band_meta(all_trials, nominal_iti)
    return {
        "task_label": TH.TASK_LABELS.get(task, task),
        "mice": mice,
        "colors": colors,
        "y_metrics": Y_METRICS,
        "default_y": "lick_rate",
        "band_meta": band_meta,
        "data": data,
        "sessions": sessions,
        "dt": DT,
    }


def write_dashboard(records: list[dict], out_dir: str) -> list[str]:
    grouping: dict[str, dict[str, list[dict]]] = {}
    for r in records:
        grouping.setdefault(r["task"], {}).setdefault(r["mouse"], []).append(r)
    mcolors, _ = LT._mouse_colors(grouping)
    plotlyjs = get_plotlyjs()
    os.makedirs(out_dir, exist_ok=True)
    by_task: dict[str, list[dict]] = {}
    for r in records:
        by_task.setdefault(r["task"], []).append(r)
    written = []
    for task, recs in by_task.items():
        payload = build_payload(task, recs, mcolors)
        html = (_TEMPLATE
                .replace("__PLOTLYJS__", plotlyjs)
                .replace("__DATA__", json.dumps(payload))
                .replace("__TITLE__", payload["task_label"]))
        suffix = "" if len(by_task) == 1 else f"_{task}"
        path = os.path.join(out_dir, f"bin_timecourse{suffix}.html")
        with open(path, "w") as f:
            f.write(html)
        written.append(path)
    return written


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--task", choices=["appetitive", "generalization", "both"], default="both")
    parser.add_argument("--mouse", default=None, help="restrict to one mouse")
    args = parser.parse_args()

    records: list[dict] = []
    if args.task in ("appetitive", "both"):
        print("Loading appetitive (tone) task ...")
        records += TH.load_appetitive(args.mouse)
    if args.task in ("generalization", "both"):
        print("Loading generalization (light) task ...")
        records += TH.load_generalization(args.mouse)
    if not records:
        print("No sessions found — nothing to do.")
        return 1

    out_dir = str(_RESULTS_ROOT / "bining" / _TASK_AREA[args.task])
    paths = write_dashboard(records, out_dir)
    print(f"\nWrote {len(paths)} time-course dashboard(s) under '{out_dir}/':")
    for p in paths:
        print(f"  {p}")
    return 0


_TEMPLATE = r"""<!doctype html>
<html><head><meta charset="utf-8"><title>__TITLE__ — trial time course</title>
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
  <label>Show <select id="msel"></select></label>
  <span id="sfilter" style="display:none">
    <label>Sessions <select id="smode">
      <option value="all">all</option>
      <option value="firstN">first N</option>
      <option value="lastN">last N</option>
      <option value="range">ordinal range</option>
      <option value="thirds">early / mid / late thirds</option>
      <option value="custom">custom list</option>
    </select></label>
    <label id="snwrap">N <input id="snin" type="number" min="1" value="3" style="width:4em"></label>
    <label id="srwrap">from <input id="srfrom" type="number" min="1" style="width:4em">
      to <input id="srto" type="number" min="1" style="width:4em"></label>
    <label id="scwrap">ordinals <input id="scustom" type="text" placeholder="1,4,7" style="width:8em"></label>
  </span>
  <label>Y axis <select id="ysel"></select></label>
  <label><input id="showall" type="checkbox" checked> pooled mean</label>
  <span class="hint">on-cue = blue, added ITI = red · line thins out where fewer trials are still running</span>
</div>
<div id="plot"></div>
<script>
const DATA = __DATA__;
const $ = id => document.getElementById(id);
const MSEL=$('msel'), YSEL=$('ysel'), SHOWALL=$('showall');
const SMODE=$('smode'), SNIN=$('snin'), SRFROM=$('srfrom'), SRTO=$('srto'), SCUSTOM=$('scustom');
const PLOT=$('plot');

DATA.y_metrics.forEach(([k,l])=>{const o=document.createElement('option');
  o.value=k;o.textContent=l;YSEL.appendChild(o);});
YSEL.value=DATA.default_y;
[['__ALL__','All mice']].concat(DATA.mice.map(m=>[m,m])).forEach(([v,t])=>{
  const o=document.createElement('option'); o.value=v; o.textContent=t; MSEL.appendChild(o);});
MSEL.value='__ALL__';

const label = k => (DATA.y_metrics.find(e=>e[0]===k)||[k,k])[1];
const rgb = c => `rgb(${c[0]},${c[1]},${c[2]})`;

function shade(base, t){
  t=Math.max(0,Math.min(1,t));
  const light=base.map(c=>Math.round(c+(255-c)*0.62)), dark=base.map(c=>Math.round(c*0.45));
  return [0,1,2].map(j=>Math.round(light[j]+t*(dark[j]-light[j])));
}
function combineRows(rowsList){
  const byT={};
  rowsList.forEach(rows=>rows.forEach(r=>{
    const b=byT[r.t]||(byT[r.t]={t:r.t,n:0,wl:0,wp:0,wml:0,wmp:0,sl:0,sp:0});
    const n=r.n_trials; b.n+=n; b.wl+=r.lick_rate*n; b.wp+=r.poke_rate*n;
    b.wml+=r.mean_licks*n; b.wmp+=r.mean_pokes*n; b.sl+=r.mean_licks*n; b.sp+=r.mean_pokes*n;
  }));
  return Object.values(byT).sort((a,b)=>a.t-b.t).map(b=>({
    t:b.t, n_trials:b.n, lick_rate:b.wl/b.n, poke_rate:b.wp/b.n, mean_licks:b.wml/b.n,
    mean_pokes:b.wmp/b.n, licks_per_poke: b.sp>0 ? b.sl/b.sp : null }));
}
function selectSessions(sess, base){
  const mode=SMODE.value, N=sess.length;
  if(!N) return [];
  if(mode==='thirds'){
    const size=N/3, names=['early','mid','late'], out=[];
    for(let g=0;g<3;g++){
      const chunk=sess.slice(Math.floor(g*size), g===2?N:Math.floor((g+1)*size));
      if(chunk.length) out.push({name:names[g]+' ('+chunk.length+')',
        color:shade(base,g/2), rows:combineRows(chunk.map(s=>s.rows))});
    }
    return out;
  }
  let idxs=sess.map((s,i)=>i);
  if(mode==='firstN'){ const n=Math.max(1,+SNIN.value||1); idxs=idxs.slice(0,n); }
  else if(mode==='lastN'){ const n=Math.max(1,+SNIN.value||1); idxs=idxs.slice(Math.max(0,N-n)); }
  else if(mode==='range'){ const a=+SRFROM.value,b=+SRTO.value;
    idxs=idxs.filter(i=>sess[i].session>=a&&sess[i].session<=b); }
  else if(mode==='custom'){ const set=new Set((SCUSTOM.value||'').split(',')
    .map(x=>parseInt(x.trim())).filter(x=>!isNaN(x))); idxs=idxs.filter(i=>set.has(sess[i].session)); }
  return idxs.map(i=>({name:'s'+sess[i].session, color:shade(base,N>1?i/(N-1):1), rows:sess[i].rows}));
}
function pushSeries(traces, rowsRaw, name, c, bold, yk){
  const rows=(rowsRaw||[]).filter(r=>r[yk]!=null);
  if(!rows.length) return;
  traces.push({type:'scatter', mode:'lines', name:name, x:rows.map(r=>r.t),
    y:rows.map(r=>r[yk]), line:{color:rgb(c), width:bold?3.5:1.5}, opacity:bold?1:0.85,
    hovertemplate:'<b>'+name+'</b> t=%{x:.1f}s<br>'+label(yk)+': %{y:.2f}<extra></extra>'});
}

function redraw(){
  const yk=YSEL.value, sel=MSEL.value, single=sel!=='__ALL__', traces=[];
  $('sfilter').style.display = single ? '' : 'none';
  if(single){ const sm=SMODE.value;
    $('snwrap').style.display=(sm==='firstN'||sm==='lastN')?'':'none';
    $('srwrap').style.display=(sm==='range')?'':'none';
    $('scwrap').style.display=(sm==='custom')?'':'none';
  }
  if(!single){
    DATA.mice.forEach(m=>pushSeries(traces, DATA.data[m], m, DATA.colors[m], false, yk));
    if(SHOWALL.checked) pushSeries(traces, DATA.data.ALL, 'ALL', DATA.colors.ALL, true, yk);
  } else {
    selectSessions(DATA.sessions[sel]||[], DATA.colors[sel]).forEach(s=>
      pushSeries(traces, s.rows, s.name, s.color, false, yk));
    if(SHOWALL.checked) pushSeries(traces, DATA.data[sel], sel+' (all sessions)',
      DATA.colors.ALL, true, yk);
  }
  const bm=(single ? DATA.band_meta[sel] : DATA.band_meta.ALL) || DATA.band_meta.ALL;
  const shapes=[{type:'rect', xref:'x', yref:'paper', x0:0, x1:bm.mean_cue, y0:0, y1:1,
    fillcolor:'rgba(70,130,180,0.10)', line:{width:0}, layer:'below'},
    {type:'rect', xref:'x', yref:'paper', x0:bm.band[0], x1:bm.band[1], y0:0, y1:1,
    fillcolor:'rgba(192,57,43,0.13)', line:{width:0}, layer:'below'}];
  const annos=[{xref:'x', yref:'paper', x:bm.mean_cue/2, y:1.015, yanchor:'bottom',
    text:'on-cue', showarrow:false, font:{size:11, color:'#3a7ca5'}},
    {xref:'x', yref:'paper', x:(bm.band[0]+bm.band[1])/2, y:1.015, yanchor:'bottom',
    xanchor:'center', text:'added ITI (punishment)', showarrow:false, font:{size:11, color:'#c0392b'}}];
  const scope = single ? sel+' — across its sessions' : 'all mice, all sessions pooled';
  Plotly.react('plot', traces, {
    title:{text:DATA.task_label+' — within-trial time course (no binning)'+
      '<br><sup>'+DATA.dt+'s steps from cue onset · 1/0 = event happened in the step · '+scope+'</sup>'},
    xaxis:{title:{text:'time since cue onset (s)'}, zeroline:false, showline:true,
           linecolor:'#444', gridcolor:'#eee'},
    yaxis:{title:{text:label(yk)}, zeroline:false, showline:true, linecolor:'#444',
           gridcolor:'#eee', rangemode:'tozero'},
    shapes:shapes, annotations:annos, hovermode:'closest',
    legend:{title:{text:single?'session':'mouse'}},
    plot_bgcolor:'white', paper_bgcolor:'white', margin:{t:80}
  }, {responsive:true});
}

MSEL.addEventListener('change',()=>{
  const sess=DATA.sessions[MSEL.value]||[];
  if(sess.length){ const last=sess[sess.length-1].session;
    SRFROM.value=1; SRTO.value=last; SRFROM.max=SRTO.max=last; SNIN.max=sess.length; }
});
[MSEL,YSEL,SHOWALL,SMODE,SNIN,SRFROM,SRTO,SCUSTOM].forEach(el=>{
  el.addEventListener('change',redraw); el.addEventListener('input',redraw);
});
redraw();
</script>
</body></html>"""


if __name__ == "__main__":
    raise SystemExit(main())
