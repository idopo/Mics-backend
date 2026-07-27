#!/usr/bin/env python3
"""Per-bin lick-BOUT bar chart, per task (Gili).

A lick bout = a run of licks that almost touch (consecutive gap <= LICK_BOUT_GAP,
default 1.0s = one bout; reused from learning_trajectories_analysis). Each bout is
assigned to the bin its FIRST lick falls in. Per bin we then look at:

    licks_per_bout   mean bout size (licks per bout) — is it different across bins?
    pct_bouts        % of the mouse's lick-bouts that fall in this bin (out of total)
    bouts_per_trial  lick-bouts per trial in the bin

Bars, grouped by mouse (or by session when one mouse is selected). On-cue bar shaded
blue, added-ITI (punishment) bar shaded red. Bins reuse bin_trial_analysis.

Usage:
    python3 bin_barplot.py --task appetitive
    python3 bin_barplot.py --task both
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
import learning_trajectories_analysis as LT  # noqa: E402  LICK_BOUT_GAP, colours
import bin_trial_analysis as B  # noqa: E402  bins + nominal ITI

_RESULTS_ROOT = Path(__file__).resolve().parent.parent / "results"
_TASK_AREA = {"appetitive": "appetitive", "generalization": "generalization", "both": "cross_task"}

METRICS = [
    ["licks_per_bout", "licks per bout  (mean bout size)"],
    ["pct_bouts", "% of lick-bouts in the bin  (out of the mouse's total)"],
    ["bouts_per_trial", "lick-bouts per trial"],
]

# trial-type filter. "catch" uses the project-canonical definition from
# action_sequence_analysis (cue_poke_lick_no_reward): an on-cue poke + a
# RESPONSE-WINDOW lick (in [0, iti_start), not a stray impulsive ITI lick) + no reward.
TYPES = [
    ["all", "all trials"],
    ["catch", "catch (on-cue poke + response lick, no reward)"],
    ["hit", "rewarded (HIT)"],
]


def classify(trial: dict) -> set[str]:
    """Which trial types a trial belongs to (a trial is 'all' plus at most one of the
    rest). Catch matches action_sequence_analysis._classify: engaged + response-window
    lick + unrewarded."""
    cue = trial["cue_dur"]
    on_cue = [p for p in trial["nose_pokes"] if 0 <= p <= cue]
    types = {"all"}
    if trial["rewarded"]:
        types.add("hit")
    elif on_cue and any(0 <= lk < trial["iti_start"] for lk in trial["licks"]):
        types.add("catch")   # canonical cue_poke_lick_no_reward
    return types


def lick_bouts(licks: list[float]) -> list[tuple[float, int]]:
    """(onset, size) for each lick bout; a gap > LICK_BOUT_GAP starts a new bout."""
    ordered = sorted(licks)
    if not ordered:
        return []
    bouts, onset, size = [], ordered[0], 1
    for prev, cur in zip(ordered, ordered[1:]):
        if cur - prev > LT.LICK_BOUT_GAP:
            bouts.append((onset, size))
            onset, size = cur, 1
        else:
            size += 1
    bouts.append((onset, size))
    return bouts


def aggregate_bouts(trials: list[dict], nominal_iti: float) -> list[dict]:
    """Per bin-index raw bout sums across trials (derived metrics are computed in the
    browser so session/thirds combines stay exact)."""
    acc: dict[int, dict] = {}
    for t in trials:
        bouts = lick_bouts(t["licks"])
        for idx, (lo, hi, kind) in enumerate(B.trial_bins(t, nominal_iti)):
            a = acc.setdefault(idx, {"n_bouts": 0, "bout_licks": 0, "n": 0, "kind": kind})
            a["n"] += 1
            for onset, size in bouts:
                if lo <= onset < hi:
                    a["n_bouts"] += 1
                    a["bout_licks"] += size
    rows = []
    for idx in sorted(acc):
        a = acc[idx]
        if a["n"] < B.MIN_BIN_TRIALS:
            break
        rows.append({"bin": idx, "kind": a["kind"], "n_trials": a["n"],
                     "n_bouts": a["n_bouts"], "bout_licks": a["bout_licks"]})
    return rows


def _rgb255(color) -> list[int]:
    return [int(round(255 * c)) for c in color[:3]]


def _bin_label(idx: int, overflow_bin: int) -> str:
    if idx == 0:
        return "on-cue"
    if idx == overflow_bin:
        return "added ITI<br>(punishment)"
    return str(idx)


def build_payload(task: str, records: list[dict], mcolors: dict) -> dict:
    by_mouse: dict[str, list[dict]] = {}
    for r in records:
        by_mouse.setdefault(r["mouse"], []).extend(r["trials"])
    mice = LT._sorted_mice(by_mouse)
    all_trials = [t for ts in by_mouse.values() for t in ts]
    nominal_iti = B.compute_nominal_iti(all_trials)
    for t in all_trials:
        t["_types"] = classify(t)   # same dict objects are reused in records/by_mouse

    def agg(trials, ty):
        return aggregate_bouts([t for t in trials if ty in t["_types"]], nominal_iti)

    data: dict[str, dict] = {}
    sessions: dict[str, dict] = {}
    for ty, _ in TYPES:
        data[ty] = {m: agg(by_mouse[m], ty) for m in mice}
        data[ty]["ALL"] = agg(all_trials, ty)
        sess: dict[str, list[dict]] = {}
        for r in records:
            sess.setdefault(r["mouse"], []).append(
                {"session": r["training_day"], "rows": agg(r["trials"], ty)})
        for m in sess:
            sess[m].sort(key=lambda s: s["session"])
        sessions[ty] = sess
    colors = {m: _rgb255(mcolors[m]) for m in mice}
    colors["ALL"] = [20, 20, 20]
    overflow_bin = B.N_ITI_BINS + 1
    max_bin = max((r["bin"] for tyd in data.values() for rows in tyd.values() for r in rows),
                  default=0)
    bins = [{"bin": b, "label": _bin_label(b, overflow_bin)} for b in range(max_bin + 1)]
    has_overflow = any(r["kind"] == "overflow" for r in data["all"]["ALL"])
    return {
        "task_label": TH.TASK_LABELS.get(task, task),
        "mice": mice,
        "colors": colors,
        "bins": bins,
        "metrics": METRICS,
        "default_metric": "licks_per_bout",
        "types": TYPES,
        "default_type": "catch",
        "overflow_bin": overflow_bin,
        "has_overflow": has_overflow,
        "data": data,
        "sessions": sessions,
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
        path = os.path.join(out_dir, f"bin_bouts_barplot{suffix}.html")
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
    print(f"\nWrote {len(paths)} bout bar-plot(s) under '{out_dir}/':")
    for p in paths:
        print(f"  {p}")
    return 0


_TEMPLATE = r"""<!doctype html>
<html><head><meta charset="utf-8"><title>__TITLE__ — lick-bout bar plot</title>
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
  <label>Trials <select id="ttype"></select></label>
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
  <span class="hint">on-cue bar = blue, added-ITI bar = red · bout = licks within 1s of each other</span>
</div>
<div id="plot"></div>
<script>
const DATA = __DATA__;
const $ = id => document.getElementById(id);
const TTYPE=$('ttype'), MSEL=$('msel'), YSEL=$('ysel');
const SMODE=$('smode'), SNIN=$('snin'), SRFROM=$('srfrom'), SRTO=$('srto'), SCUSTOM=$('scustom');
const PLOT=$('plot');

DATA.types.forEach(([k,l])=>{const o=document.createElement('option');
  o.value=k;o.textContent=l;TTYPE.appendChild(o);});
TTYPE.value=DATA.default_type;
DATA.metrics.forEach(([k,l])=>{const o=document.createElement('option');
  o.value=k;o.textContent=l;YSEL.appendChild(o);});
YSEL.value=DATA.default_metric;
const tlabel = k => (DATA.types.find(e=>e[0]===k)||[k,k])[1];
[['__ALL__','All mice']].concat(DATA.mice.map(m=>[m,m])).forEach(([v,t])=>{
  const o=document.createElement('option'); o.value=v; o.textContent=t; MSEL.appendChild(o);});
MSEL.value='__ALL__';

const mlabel = k => (DATA.metrics.find(e=>e[0]===k)||[k,k])[1];
const rgb = c => `rgb(${c[0]},${c[1]},${c[2]})`;
const binLabel = b => ((DATA.bins.find(x=>x.bin===b)||{}).label||(''+b));
const CATS = DATA.bins.map(b=>b.label);   // fixed x category order

function shade(base, t){
  t=Math.max(0,Math.min(1,t));
  const light=base.map(c=>Math.round(c+(255-c)*0.62)), dark=base.map(c=>Math.round(c*0.45));
  return [0,1,2].map(j=>Math.round(light[j]+t*(dark[j]-light[j])));
}
function combineRows(rowsList){  // sum raw bout counts by bin
  const byBin={};
  rowsList.forEach(rows=>rows.forEach(r=>{
    const b=byBin[r.bin]||(byBin[r.bin]={bin:r.bin,kind:r.kind,n_trials:0,n_bouts:0,bout_licks:0});
    b.n_trials+=r.n_trials; b.n_bouts+=r.n_bouts; b.bout_licks+=r.bout_licks;
  }));
  return Object.values(byBin).sort((a,b)=>a.bin-b.bin);
}
function selectSessions(sess, base){
  const mode=SMODE.value, N=sess.length; if(!N) return [];
  if(mode==='thirds'){
    const size=N/3, names=['early','mid','late'], out=[];
    for(let g=0;g<3;g++){ const chunk=sess.slice(Math.floor(g*size), g===2?N:Math.floor((g+1)*size));
      if(chunk.length) out.push({name:names[g]+' ('+chunk.length+')', color:shade(base,g/2),
        rows:combineRows(chunk.map(s=>s.rows))}); }
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
// derived metric per bin from raw bout sums; pct is out of the series' total bouts
function metricY(rows, mk){
  const tot=rows.reduce((s,r)=>s+(r.n_bouts||0),0);
  const by={}; rows.forEach(r=>{
    by[binLabel(r.bin)] = (mk==='licks_per_bout') ? (r.n_bouts? r.bout_licks/r.n_bouts : null)
      : (mk==='bouts_per_trial') ? (r.n_trials? r.n_bouts/r.n_trials : null)
      : (tot? 100*r.n_bouts/tot : null);
  });
  return CATS.map(c=>by[c]!=null?by[c]:null);
}
function pushBars(traces, rows, name, c, mk){
  if(!rows||!rows.length) return;
  traces.push({type:'bar', name:name, x:CATS, y:metricY(rows,mk), marker:{color:rgb(c)},
    hovertemplate:'<b>'+name+'</b> %{x}<br>'+mlabel(mk).split('  (')[0]+': %{y:.2f}<extra></extra>'});
}

function redraw(){
  const mk=YSEL.value, sel=MSEL.value, single=sel!=='__ALL__', traces=[];
  const D=DATA.data[TTYPE.value], S=DATA.sessions[TTYPE.value];
  $('sfilter').style.display = single ? '' : 'none';
  if(single){ const sm=SMODE.value;
    $('snwrap').style.display=(sm==='firstN'||sm==='lastN')?'':'none';
    $('srwrap').style.display=(sm==='range')?'':'none';
    $('scwrap').style.display=(sm==='custom')?'':'none';
  }
  if(!single){
    DATA.mice.forEach(m=>pushBars(traces, D[m], m, DATA.colors[m], mk));
    pushBars(traces, D.ALL, 'ALL', DATA.colors.ALL, mk);
  } else {
    selectSessions(S[sel]||[], DATA.colors[sel]).forEach(s=>
      pushBars(traces, s.rows, s.name, s.color, mk));
    pushBars(traces, D[sel], sel+' (all)', DATA.colors.ALL, mk);
  }
  // shade the on-cue (blue) and added-ITI (red) bar groups
  const oi=CATS.indexOf(binLabel(0));
  const shapes=[{type:'rect',xref:'x',yref:'paper',x0:oi-0.5,x1:oi+0.5,y0:0,y1:1,
    fillcolor:'rgba(70,130,180,0.10)',line:{width:0},layer:'below'}];
  if(DATA.has_overflow){ const ai=CATS.indexOf(binLabel(DATA.overflow_bin));
    if(ai>=0) shapes.push({type:'rect',xref:'x',yref:'paper',x0:ai-0.5,x1:ai+0.5,y0:0,y1:1,
      fillcolor:'rgba(192,57,43,0.12)',line:{width:0},layer:'below'}); }
  const scope = single ? sel+' — across its sessions' : 'all mice pooled';
  Plotly.react('plot', traces, {
    title:{text:DATA.task_label+' — lick-bout bar plot &nbsp;['+tlabel(TTYPE.value)+']'+
      '<br><sup>'+scope+' · bout = licks within 1s · '+mlabel(mk)+
      ' · is the on-cue bout bigger than the ITI bouts?</sup>'},
    barmode:'group', bargap:0.25, bargroupgap:0.05,
    xaxis:{type:'category', categoryorder:'array', categoryarray:CATS, title:{text:'bin'}},
    yaxis:{title:{text:mlabel(mk).split('  (')[0]}, zeroline:false, showline:true,
           linecolor:'#444', gridcolor:'#eee', rangemode:'tozero'},
    shapes:shapes, legend:{title:{text:single?'session':'mouse'}},
    plot_bgcolor:'white', paper_bgcolor:'white', margin:{t:80}
  }, {responsive:true});
}

MSEL.addEventListener('change',()=>{
  const sess=(DATA.sessions[TTYPE.value]||{})[MSEL.value]||[];
  if(sess.length){ const last=sess[sess.length-1].session;
    SRFROM.value=1; SRTO.value=last; SRFROM.max=SRTO.max=last; SNIN.max=sess.length; }
});
[TTYPE,MSEL,YSEL,SMODE,SNIN,SRFROM,SRTO,SCUSTOM].forEach(el=>{
  el.addEventListener('change',redraw); el.addEventListener('input',redraw);
});
redraw();
</script>
</body></html>"""


if __name__ == "__main__":
    raise SystemExit(main())
