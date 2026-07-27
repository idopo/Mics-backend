#!/usr/bin/env python3
"""Per-mouse bin dot-plot (Gili).

One dot per (mouse, bin). Dot SIZE = the mouse's poke probability in that bin (how
often it is active there); dot COLOUR = licks per nose poke in that bin. Reading a
mouse's row left→right shows whether it licks more per poke during the ON-CUE window
or during the different ITI bins. Bins and the per-mouse aggregation (on-cue, 4
fixed-width nominal-ITI bins, added-ITI/punishment bin) are reused from
bin_trial_analysis.

Usage:
    python3 bin_dotplot.py --task appetitive
    python3 bin_dotplot.py --task both
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

from plotly.offline import get_plotlyjs

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import trial_history_analysis as TH  # noqa: E402  loaders + task labels
import bin_trial_analysis as B  # noqa: E402  bin aggregation + nominal ITI

_RESULTS_ROOT = Path(__file__).resolve().parent.parent / "results"
_TASK_AREA = {"appetitive": "appetitive", "generalization": "generalization", "both": "cross_task"}

# (key, label). First entry is the default.
COLOR_METRICS = [
    ["licks_per_poke", "licks per nose poke (Σ licks / Σ pokes)"],
    ["lick_rate", "lick rate (% trials with a lick)"],
    ["mean_licks", "mean licks per trial"],
]
SIZE_METRICS = [
    ["poke_rate", "poke probability (% trials with a poke)"],
    ["lick_rate", "lick probability (% trials with a lick)"],
    ["n_trials", "n trials in bin"],
]


def _sorted_mice(names) -> list[str]:
    return sorted(names, key=lambda m: int(m[1:]))


def _bin_label(idx: int, overflow_bin: int) -> str:
    if idx == 0:
        return "on-cue"
    if idx == overflow_bin:
        return "added ITI<br>(punishment)"
    return str(idx)


def build_payload(task: str, records: list[dict]) -> dict:
    by_mouse: dict[str, list[dict]] = {}
    for r in records:
        by_mouse.setdefault(r["mouse"], []).extend(r["trials"])
    mice = _sorted_mice(by_mouse)
    all_trials = [t for ts in by_mouse.values() for t in ts]
    nominal_iti = B.compute_nominal_iti(all_trials)
    cells = {m: B.aggregate(by_mouse[m], nominal_iti) for m in mice}
    cells["ALL"] = B.aggregate(all_trials, nominal_iti)
    # per-mouse, per-session rows for the single-mouse "across sessions" view
    sessions: dict[str, list[dict]] = {}
    for r in records:
        sessions.setdefault(r["mouse"], []).append(
            {"session": r["training_day"], "rows": B.aggregate(r["trials"], nominal_iti)})
    for m in sessions:
        sessions[m].sort(key=lambda s: s["session"])
    overflow_bin = B.N_ITI_BINS + 1
    max_bin = max((r["bin"] for rows in cells.values() for r in rows), default=0)
    bins = [{"bin": b, "label": _bin_label(b, overflow_bin)} for b in range(max_bin + 1)]
    return {
        "task_label": TH.TASK_LABELS.get(task, task),
        "mice": mice,
        "rows": mice + ["ALL"],   # default (all-mice) y axis, cohort on top
        "bins": bins,             # x axis
        "cells": cells,
        "sessions": sessions,
        "color_metrics": COLOR_METRICS,
        "size_metrics": SIZE_METRICS,
        "default_color": "licks_per_poke",
        "default_size": "poke_rate",
    }


def write_dashboard(records: list[dict], out_dir: str) -> list[str]:
    plotlyjs = get_plotlyjs()
    os.makedirs(out_dir, exist_ok=True)
    by_task: dict[str, list[dict]] = {}
    for r in records:
        by_task.setdefault(r["task"], []).append(r)
    written = []
    for task, recs in by_task.items():
        payload = build_payload(task, recs)
        html = (_TEMPLATE
                .replace("__PLOTLYJS__", plotlyjs)
                .replace("__DATA__", json.dumps(payload))
                .replace("__TITLE__", payload["task_label"]))
        suffix = "" if len(by_task) == 1 else f"_{task}"
        path = os.path.join(out_dir, f"bin_dotplot{suffix}.html")
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
    print(f"\nWrote {len(paths)} dot-plot(s) under '{out_dir}/':")
    for p in paths:
        print(f"  {p}")
    return 0


_TEMPLATE = r"""<!doctype html>
<html><head><meta charset="utf-8"><title>__TITLE__ — bin dot plot</title>
<style>
  body{font-family:system-ui,Arial,sans-serif;margin:0;padding:14px;color:#222}
  #controls{display:flex;flex-wrap:wrap;gap:14px;align-items:center;
    padding:10px 12px;background:#f6f7f9;border:1px solid #e2e4e8;border-radius:8px;margin-bottom:8px}
  #controls label{font-size:13px;display:flex;gap:6px;align-items:center}
  select{font-size:13px;padding:2px 4px}
  #plot{width:100%}
  .hint{color:#777;font-size:12px}
</style>
<script>__PLOTLYJS__</script>
</head><body>
<div id="controls">
  <label>Show <select id="msel"></select></label>
  <label>Dot colour <select id="csel"></select></label>
  <label>Dot size <select id="ssel"></select></label>
  <span class="hint">column = bin · bigger dot = more likely to poke there · hover for numbers</span>
</div>
<div id="plot"></div>
<script>
const DATA = __DATA__;
const $ = id => document.getElementById(id);
const MSEL=$('msel'), CSEL=$('csel'), SSEL=$('ssel'), PLOT=$('plot');

[['__ALL__','All mice']].concat(DATA.mice.map(m=>[m,m])).forEach(([v,t])=>{
  const o=document.createElement('option'); o.value=v; o.textContent=t; MSEL.appendChild(o);});
MSEL.value='__ALL__';
DATA.color_metrics.forEach(([k,l])=>{const o=document.createElement('option');
  o.value=k;o.textContent=l;CSEL.appendChild(o);});
DATA.size_metrics.forEach(([k,l])=>{const o=document.createElement('option');
  o.value=k;o.textContent=l;SSEL.appendChild(o);});
CSEL.value=DATA.default_color; SSEL.value=DATA.default_size;

const clabel = k => (DATA.color_metrics.find(e=>e[0]===k)||[k,k])[1];
const slabel = k => (DATA.size_metrics.find(e=>e[0]===k)||[k,k])[1];
const dotSize = (v,smax) => 6 + 30*(smax>0 ? Math.sqrt(Math.max(0,v||0)/smax) : 0);

// current y rows + a cell lookup, depending on the mouse selector
function currentView(){
  const sel=MSEL.value, single=sel!=='__ALL__';
  if(!single) return {labels:DATA.rows, yname:'mouse',
    get:lab=>DATA.cells[lab], scope:'all mice, all sessions pooled'};
  const sess=DATA.sessions[sel]||[], map={};
  const labels=sess.map(s=>{const L='s'+s.session; map[L]=s.rows; return L;});
  const allLab=sel+' (all)'; map[allLab]=DATA.cells[sel]; labels.push(allLab);
  return {labels, yname:'session', get:lab=>map[lab], scope:sel+' — across its sessions'};
}

function redraw(){
  const ck=CSEL.value, sk=SSEL.value, bins=DATA.bins, view=currentView(), rows=view.labels;
  let smax=0;
  rows.forEach(m=>(view.get(m)||[]).forEach(r=>{ if(r[sk]!=null) smax=Math.max(smax,r[sk]); }));
  const xs=[], ys=[], size=[], color=[], text=[];
  rows.forEach((m,yi)=>{
    (view.get(m)||[]).forEach(r=>{
      if(r[ck]==null) return;               // no colour value (e.g. no pokes) -> skip dot
      xs.push(r.bin); ys.push(yi); size.push(dotSize(r[sk],smax)); color.push(r[ck]);
      const blab=((bins.find(b=>b.bin===r.bin)||{}).label||(''+r.bin)).replace('<br>',' ');
      text.push('<b>'+m+'</b> · '+blab+'<br>'+clabel(ck)+': '+r[ck].toFixed(2)+'<br>'+
        slabel(sk)+': '+(r[sk]!=null?r[sk].toFixed(2):'—')+'<br>n = '+r.n_trials);
    });
  });
  const dots={type:'scatter', mode:'markers', x:xs, y:ys, text:text,
    marker:{size:size, color:color, colorscale:'Viridis', showscale:true,
      colorbar:{title:{text:clabel(ck), side:'right'}, thickness:14, len:0.85, y:0.42},
      line:{color:'#444', width:0.6}}, hovertemplate:'%{text}<extra></extra>'};
  // size-reference legend: 3 grey dots above the plot at 25/50/100% of the max
  const legY=rows.length+0.35, fr=[0.25,0.5,1.0];
  const legend={type:'scatter', mode:'markers+text', x:fr.map((f,i)=>i*1.15+0.3),
    y:fr.map(()=>legY), text:fr.map(f=>(smax*f).toFixed(0)), textposition:'top center',
    textfont:{size:10,color:'#555'}, hoverinfo:'skip', showlegend:false,
    marker:{size:fr.map(f=>dotSize(smax*f,smax)), color:'#c9c9c9', line:{color:'#666',width:0.6}}};
  Plotly.react('plot',[dots,legend],{
    title:{text:DATA.task_label+' — bin dot plot &nbsp;('+view.scope+')'+
      '<br><sup>dot size = '+slabel(sk)+' · colour = '+clabel(ck)+
      ' · read a row left→right: where is licks-per-poke highest?</sup>'},
    annotations:[{xref:'x',yref:'y',x:-0.5,y:legY,xanchor:'right',showarrow:false,
      text:'size = '+slabel(sk).split(' (')[0]+':', font:{size:10,color:'#555'}}],
    xaxis:{tickmode:'array', tickvals:bins.map(b=>b.bin), ticktext:bins.map(b=>b.label),
      range:[-0.6, bins.length-0.4], title:{text:'bin'}, showgrid:true, gridcolor:'#eee',
      zeroline:false},
    yaxis:{tickmode:'array', tickvals:rows.map((m,i)=>i), ticktext:rows,
      range:[-0.6, rows.length+1.0], title:{text:view.yname}, gridcolor:'#eee', zeroline:false},
    height: Math.max(360, 42*(rows.length+1)+150),
    plot_bgcolor:'white', paper_bgcolor:'white', margin:{t:80,l:90}
  },{responsive:true});
}

[MSEL,CSEL,SSEL].forEach(el=>el.addEventListener('change',redraw));
redraw();
</script>
</body></html>"""


if __name__ == "__main__":
    raise SystemExit(main())
