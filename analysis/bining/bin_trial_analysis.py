#!/usr/bin/env python3
"""Within-trial temporal binning of pokes / licks, per task (Gili).

Bin 0 is the ON-CUE window [0, cue_dur) — how long the tone/LED actually played
(shorter when a HIT stopped the cue early). The ITI is then binned FIXED-WIDTH:
N_ITI_BINS bins each nominal_iti/N_ITI_BINS seconds wide tile the nominal ITI
[iti_start, iti_start + nominal_iti], where nominal_iti is the median UNPUNISHED
ITI length. Anything past the nominal end — the time added by punishment (ITI pokes
resetting the timer) — falls in a single OVERFLOW bin [nominal_end, iti_end], drawn
as a red band. Trials whose ITI was not extended have no overflow bin.

For every bin we score, per trial, whether an event happened (1) or not (0), then
average across all of a mouse's trials (pooled over sessions). The interactive
figure puts the on-cue bin at the left and the off-cue bins along x as a function
of time (or bin index) since cue onset. Selectable Y metrics:

    lick_rate      = % of trials with >=1 lick in the bin
    poke_rate      = % of trials with >=1 nose poke in the bin
    licks_per_poke = Sum(licks) / Sum(nose pokes) in the bin
    mean_licks     = mean licks per trial in the bin
    mean_pokes     = mean nose pokes per trial in the bin

Usage:
    python3 bin_trial_analysis.py --task appetitive
    python3 bin_trial_analysis.py --task generalization
    python3 bin_trial_analysis.py --task both
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

import numpy as np
from plotly.offline import get_plotlyjs

# the analysis modules live one level up (flat package); make them importable
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import trial_history_analysis as TH  # noqa: E402  loaders + task labels
import learning_trajectories_analysis as LT  # noqa: E402  colour/order helpers

# The ITI [iti_start, iti_end] is split into this many equal bins (+1 on-cue bin).
# Drop bins with too few contributing trials. Env-overridable.
N_ITI_BINS = int(os.environ.get("MICS_BIN_N_ITI", "4"))
MIN_BIN_TRIALS = int(os.environ.get("MICS_BIN_MIN_TRIALS", "10"))

Y_METRICS = [
    ["lick_rate", "lick rate = % trials with a lick in the bin  (%)"],
    ["poke_rate", "nose-poke rate = % trials with a poke in the bin  (%)"],
    ["licks_per_poke", "licks per nose poke  (Σ licks / Σ pokes in bin)"],
    ["mean_licks", "mean licks per trial in the bin"],
    ["mean_pokes", "mean nose pokes per trial in the bin"],
]

_RESULTS_ROOT = Path(__file__).resolve().parent.parent / "results"
_TASK_AREA = {"appetitive": "appetitive", "generalization": "generalization", "both": "cross_task"}


def trial_bins(trial: dict, nominal_iti: float) -> list[tuple[float, float, str]]:
    """(lo, hi, kind) edges for one trial. kind in {oncue, iti, overflow}: on-cue
    [0, cue); N_ITI_BINS fixed-width bins over the nominal ITI [iti_start,
    iti_start+nominal_iti]; then one overflow bin to iti_end if punishment extended
    the ITI past the nominal end."""
    cue = trial["cue_dur"]
    iti0 = trial["iti_start"]
    end = trial["iti_end"]
    if cue <= 0:
        return []
    bins = [(0.0, cue, "oncue")]
    if end > iti0 and nominal_iti > 0:
        w = nominal_iti / N_ITI_BINS
        for k in range(N_ITI_BINS):
            bins.append((iti0 + k * w, iti0 + (k + 1) * w, "iti"))
        nominal_end = iti0 + nominal_iti
        if end > nominal_end:
            bins.append((nominal_end, end, "overflow"))
    return bins


def _count_in(times: list[float], lo: float, hi: float) -> int:
    return sum(1 for x in times if lo <= x < hi)


def compute_nominal_iti(trials: list[dict]) -> float:
    """Median ITI length of unpunished trials — the fixed span the ITI bins tile."""
    unp = [t["iti_end"] - t["iti_start"] for t in trials
           if t["cue_dur"] > 0 and t["iti_end"] > t["iti_start"] and t["n_false_alarms"] == 0]
    return float(np.median(unp)) if unp else 0.0


def aggregate(trials: list[dict], nominal_iti: float) -> list[dict]:
    """Per bin-index aggregation across trials (bin counts fall monotonically with
    index, so we stop at the first bin with < MIN_BIN_TRIALS contributors)."""
    acc: dict[int, dict] = {}
    for t in trials:
        for idx, (lo, hi, kind) in enumerate(trial_bins(t, nominal_iti)):
            n_poke = _count_in(t["nose_pokes"], lo, hi)
            n_lick = _count_in(t["licks"], lo, hi)
            a = acc.setdefault(idx, {"poke_occ": [], "lick_occ": [], "pokes": [],
                                     "licks": [], "center": [], "kind": kind})
            a["poke_occ"].append(1 if n_poke else 0)
            a["lick_occ"].append(1 if n_lick else 0)
            a["pokes"].append(n_poke)
            a["licks"].append(n_lick)
            a["center"].append((lo + hi) / 2.0)
    rows = []
    for idx in sorted(acc):
        a = acc[idx]
        n = len(a["poke_occ"])
        if n < MIN_BIN_TRIALS:
            break  # ragged tail — too few trials reach this far
        sum_pokes = sum(a["pokes"])
        rows.append({
            "bin": idx,
            "kind": a["kind"],
            "n_trials": n,
            "time": float(np.mean(a["center"])),
            "lick_rate": 100.0 * float(np.mean(a["lick_occ"])),
            "poke_rate": 100.0 * float(np.mean(a["poke_occ"])),
            "licks_per_poke": (sum(a["licks"]) / sum_pokes) if sum_pokes else None,
            "mean_licks": float(np.mean(a["licks"])),
            "mean_pokes": float(np.mean(a["pokes"])),
        })
    return rows


def _rgb255(color) -> list[int]:
    return [int(round(255 * c)) for c in color[:3]]


def build_payload(task: str, records: list[dict], mcolors: dict) -> dict:
    by_mouse: dict[str, list[dict]] = {}
    for r in records:
        by_mouse.setdefault(r["mouse"], []).extend(r["trials"])
    mice = LT._sorted_mice(by_mouse)
    all_trials = [t for ts in by_mouse.values() for t in ts]
    nominal_iti = compute_nominal_iti(all_trials)
    data = {m: aggregate(by_mouse[m], nominal_iti) for m in mice}
    data["ALL"] = aggregate(all_trials, nominal_iti)
    # per-mouse, per-session profiles (session = training_day ordinal) for the
    # single-mouse "across sessions" view
    sessions: dict[str, list[dict]] = {}
    for r in records:
        sessions.setdefault(r["mouse"], []).append(
            {"session": r["training_day"], "rows": aggregate(r["trials"], nominal_iti)})
    for m in sessions:
        sessions[m].sort(key=lambda s: s["session"])
    colors = {m: _rgb255(mcolors[m]) for m in mice}
    colors["ALL"] = [20, 20, 20]

    def _band_meta(trials: list[dict]) -> dict:
        """On-cue band edge (mean cue_dur) and added-ITI band (nominal end -> mean
        iti_end) for a set of trials — used for per-mouse reference bands in time mode."""
        tv = [t for t in trials if t["cue_dur"] > 0]
        if not tv:
            return {"mean_cue": 0.0, "band": [0.0, 0.0]}
        mc = float(np.mean([t["cue_dur"] for t in tv]))
        bs = float(np.mean([t["iti_start"] for t in tv])) + nominal_iti
        be = float(np.mean([t["iti_end"] for t in tv]))
        return {"mean_cue": mc, "band": [bs, max(bs, be)]}

    band_meta = {m: _band_meta(by_mouse[m]) for m in mice}
    band_meta["ALL"] = _band_meta(all_trials)
    max_bin = max((row["bin"] for rows in data.values() for row in rows), default=0)
    has_overflow = any(row["kind"] == "overflow" for row in data["ALL"])
    return {
        "task_label": TH.TASK_LABELS.get(task, task),
        "mice": mice,
        "colors": colors,
        "y_metrics": Y_METRICS,
        "default_y": "lick_rate",
        "nominal_iti": nominal_iti,
        "band_meta": band_meta,
        "overflow_bin": N_ITI_BINS + 1,
        "has_overflow": has_overflow,
        "max_bin": max_bin,
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
        path = os.path.join(out_dir, f"bin_profile_dashboard{suffix}.html")
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
        print("No sessions found — nothing to do.")
        return 1

    out_dir = str(_RESULTS_ROOT / "bining" / _TASK_AREA[args.task])
    paths = write_dashboard(records, out_dir)
    print(f"\nWrote {len(paths)} dashboard(s) under '{out_dir}/':")
    for p in paths:
        print(f"  {p}")
    return 0


_TEMPLATE = r"""<!doctype html>
<html><head><meta charset="utf-8"><title>__TITLE__ — trial bin profile</title>
<style>
  body{font-family:system-ui,Arial,sans-serif;margin:0;padding:14px;color:#222}
  #controls{display:flex;flex-wrap:wrap;gap:14px;align-items:center;
    padding:10px 12px;background:#f6f7f9;border:1px solid #e2e4e8;border-radius:8px;margin-bottom:8px}
  #controls label{font-size:13px;display:flex;gap:6px;align-items:center}
  select{font-size:13px;padding:2px 4px}
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
  <label>X axis
    <select id="xmode">
      <option value="bin">bin index (0 = on-cue)</option>
      <option value="time">time since cue onset (s, mean)</option>
    </select>
  </label>
  <label><input id="showall" type="checkbox" checked> pooled mean</label>
  <span class="hint">on-cue = blue, added ITI = red · legend: click to toggle, double-click to isolate</span>
</div>
<div id="plot"></div>
<script>
const DATA = __DATA__;
const $ = id => document.getElementById(id);
const MSEL=$('msel'), YSEL=$('ysel'), XMODE=$('xmode'), SHOWALL=$('showall');
const SMODE=$('smode'), SNIN=$('snin'), SRFROM=$('srfrom'), SRTO=$('srto'), SCUSTOM=$('scustom');
const PLOT=$('plot');

DATA.y_metrics.forEach(([k,l])=>{const o=document.createElement('option');
  o.value=k;o.textContent=l;YSEL.appendChild(o);});
YSEL.value=DATA.default_y;

// "Show" selector: all mice (pooled per mouse) or one mouse across its sessions
[['__ALL__','All mice']].concat(DATA.mice.map(m=>[m,m])).forEach(([v,t])=>{
  const o=document.createElement('option'); o.value=v; o.textContent=t; MSEL.appendChild(o);});
MSEL.value='__ALL__';

const label = k => (DATA.y_metrics.find(e=>e[0]===k)||[k,k])[1];
const rgb = c => `rgb(${c[0]},${c[1]},${c[2]})`;

// shades of a mouse's own base colour: early sessions light -> late sessions dark
function shade(base, t){
  t=Math.max(0,Math.min(1,t));
  const light=base.map(c=>Math.round(c+(255-c)*0.62)); // early: tint toward white
  const dark =base.map(c=>Math.round(c*0.45));          // late: toward black
  return [0,1,2].map(j=>Math.round(light[j]+t*(dark[j]-light[j])));
}

// combine several per-session row sets into one profile (weighted by trial count)
function combineRows(rowsList){
  const byBin={};
  rowsList.forEach(rows=>rows.forEach(r=>{
    const b=byBin[r.bin]||(byBin[r.bin]={bin:r.bin,kind:r.kind,n:0,
      wl:0,wp:0,wml:0,wmp:0,wt:0,sl:0,sp:0});
    const n=r.n_trials; b.n+=n;
    b.wl+=r.lick_rate*n; b.wp+=r.poke_rate*n; b.wml+=r.mean_licks*n;
    b.wmp+=r.mean_pokes*n; b.wt+=r.time*n; b.sl+=r.mean_licks*n; b.sp+=r.mean_pokes*n;
  }));
  return Object.values(byBin).sort((a,b)=>a.bin-b.bin).map(b=>({
    bin:b.bin, kind:b.kind, n_trials:b.n, time:b.wt/b.n,
    lick_rate:b.wl/b.n, poke_rate:b.wp/b.n, mean_licks:b.wml/b.n,
    mean_pokes:b.wmp/b.n, licks_per_poke: b.sp>0 ? b.sl/b.sp : null }));
}

// pick/group a mouse's sessions per the session-filter mode; colour = shades of the
// mouse's base colour (early light -> late dark)
function selectSessions(sess, base){
  const mode=SMODE.value, N=sess.length;
  if(!N) return [];
  if(mode==='thirds'){
    const size=N/3, names=['early','mid','late'], out=[];
    for(let g=0;g<3;g++){
      const chunk=sess.slice(Math.floor(g*size), g===2?N:Math.floor((g+1)*size));
      if(chunk.length) out.push({name:names[g]+' ('+chunk.length+')',
        color:shade(base, g/2), rows:combineRows(chunk.map(s=>s.rows))});
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
  return idxs.map(i=>({name:'s'+sess[i].session, color:shade(base, N>1?i/(N-1):1),
    rows:sess[i].rows}));
}

function seriesX(rows){
  return XMODE.value==='time' ? rows.map(r=>r.time) : rows.map(r=>r.bin);
}

// build one line for a set of aggregated bin rows
function pushSeries(traces, rowsRaw, name, c, bold, yk){
  const rows=(rowsRaw||[]).filter(r=>r[yk]!=null);
  if(!rows.length) return;
  traces.push({
    type:'scatter', mode:'lines+markers', name:name, legendgroup:name,
    x:seriesX(rows), y:rows.map(r=>r[yk]),
    line:{color:rgb(c), width:bold?4:1.5}, opacity:bold?1:0.8,
    marker:{size:rows.map(r=>r.kind==='oncue'?13:(r.kind==='overflow'?11:6)),
            symbol:rows.map(r=>r.kind==='oncue'?'star':(r.kind==='overflow'?'diamond':'circle')),
            color:rgb(c)},
    customdata:rows.map(r=>[r.bin,r.n_trials,r.time,
      r.kind==='oncue'?'on-cue':(r.kind==='overflow'?'added ITI (punishment)':'ITI')]),
    hovertemplate:'<b>'+name+'</b> %{customdata[3]} bin %{customdata[0]}'+
      ' (~%{customdata[2]:.1f}s, n=%{customdata[1]})<br>'+
      label(yk)+': %{y:.2f}<extra></extra>'
  });
}


function redraw(){
  const yk=YSEL.value, sel=MSEL.value, single=sel!=='__ALL__', traces=[];
  $('sfilter').style.display = single ? '' : 'none';
  if(single){
    const sm=SMODE.value;
    $('snwrap').style.display=(sm==='firstN'||sm==='lastN')?'':'none';
    $('srwrap').style.display=(sm==='range')?'':'none';
    $('scwrap').style.display=(sm==='custom')?'':'none';
  }
  if(!single){
    // all mice: one pooled line per mouse (+ optional cohort mean)
    DATA.mice.forEach(m=>pushSeries(traces, DATA.data[m], m, DATA.colors[m], false, yk));
    if(SHOWALL.checked) pushSeries(traces, DATA.data.ALL, 'ALL', DATA.colors.ALL, true, yk);
  } else {
    // one mouse: its sessions (filtered/grouped), shaded light->dark in its colour
    const sess=DATA.sessions[sel]||[];
    selectSessions(sess, DATA.colors[sel]).forEach(s=>
      pushSeries(traces, s.rows, s.name, s.color, false, yk));
    if(SHOWALL.checked) pushSeries(traces, DATA.data[sel], sel+' (all sessions)',
      DATA.colors.ALL, true, yk);
  }
  // bands track the shown mouse (or cohort in all-mice mode) in time mode
  const bm = (single ? DATA.band_meta[sel] : DATA.band_meta.ALL) || DATA.band_meta.ALL;
  // shade the on-cue bin: [-0.5,0.5] in index mode, [0, mean_cue] in time mode
  const band = XMODE.value==='time'
      ? {x0:0, x1:bm.mean_cue} : {x0:-0.5, x1:0.5};
  const shapes=[{type:'rect', xref:'x', yref:'paper', x0:band.x0, x1:band.x1,
    y0:0, y1:1, fillcolor:'rgba(70,130,180,0.10)', line:{width:0}, layer:'below'}];
  const annos=[{xref:'x', yref:'paper', x:(band.x0+band.x1)/2, y:1.015,
    yanchor:'bottom', text:'on-cue', showarrow:false,
    font:{size:11, color:'#3a7ca5'}}];
  // red band = the added-ITI (punishment) bin: nominal end -> actual iti_end in time
  // mode, the added-ITI bin in bin mode.
  if(DATA.has_overflow){
    const r = XMODE.value==='time'
        ? {x0:bm.band[0], x1:bm.band[1]}
        : {x0:DATA.overflow_bin-0.5, x1:DATA.overflow_bin+0.5};
    shapes.push({type:'rect', xref:'x', yref:'paper', x0:r.x0, x1:r.x1, y0:0, y1:1,
      fillcolor:'rgba(192,57,43,0.13)', line:{width:0}, layer:'below'});
    annos.push({xref:'x', yref:'paper', x:(r.x0+r.x1)/2, y:1.015, yanchor:'bottom',
      xanchor:'center', text:'added ITI (punishment)', showarrow:false,
      font:{size:11, color:'#c0392b'}});
  }
  const isBin = XMODE.value==='bin';
  const xtitle = isBin
      ? 'bin  (on-cue, 4 fixed-width nominal-ITI bins, then added ITI / punishment)'
      : 'time since cue onset (s, bin-center mean)';
  const xaxis = {title:{text:xtitle}, zeroline:false, showline:true,
                 linecolor:'#444', gridcolor:'#eee'};
  if(isBin){  // integer ticks only: on-cue, 1..4, added ITI — no half-value labels
    const vals=[], txt=[];
    for(let b=0;b<=DATA.max_bin;b++){ vals.push(b);
      txt.push(b===0?'on-cue':(b===DATA.overflow_bin?'added ITI<br>(punishment)':String(b))); }
    xaxis.tickmode='array'; xaxis.tickvals=vals; xaxis.ticktext=txt; xaxis.dtick=1;
  }
  const scope = single ? sel+' — across its sessions' : 'all mice, all sessions pooled';
  Plotly.react('plot', traces, {
    title:{text:DATA.task_label+' — within-trial poke / lick bin profile'+
      '<br><sup>on-cue = cue window · 4 fixed-width nominal-ITI bins + red added-ITI (punishment) bin · '+
      '1/0 = event happened in the bin · '+scope+'</sup>'},
    xaxis:xaxis,
    yaxis:{title:{text:label(yk)}, zeroline:false, showline:true, linecolor:'#444',
           gridcolor:'#eee', rangemode:'tozero'},
    shapes:shapes, annotations:annos,
    hovermode:'closest', legend:{title:{text:single?'session':'mouse'}},
    plot_bgcolor:'white', paper_bgcolor:'white', margin:{t:95}
  }, {responsive:true});
}

// on mouse switch, reset the ordinal-range bounds to that mouse's session span
MSEL.addEventListener('change',()=>{
  const sess=DATA.sessions[MSEL.value]||[];
  if(sess.length){ const last=sess[sess.length-1].session;
    SRFROM.value=1; SRTO.value=last; SRFROM.max=SRTO.max=last; SNIN.max=sess.length; }
});
[MSEL,YSEL,XMODE,SHOWALL,SMODE,SNIN,SRFROM,SRTO,SCUSTOM].forEach(el=>{
  el.addEventListener('change',redraw); el.addEventListener('input',redraw);
});
redraw();
</script>
</body></html>"""


if __name__ == "__main__":
    raise SystemExit(main())
