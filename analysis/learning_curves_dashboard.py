#!/usr/bin/env python3
"""Traditional learning curves: a chosen metric vs SESSION NUMBER, per task.

Answers the plain question "did they get better session to session?" for the
appetitive (tone) and generalization (light) tasks. Every metric is computed per
session from the SAME raw trials the rest of the project uses (via
``hit_fa_dashboard.session_row``), so definitions stay consistent.

Interactive dashboard (results/learning_curves/<area>/learning_curves_<task>.html):
  * pick the Y-axis metric (hit rate, accuracy = hits/(hits+FA), engagement,
    competence, latency, ...); X is always session ordinal 1..N,
  * switch display mode:
        per mouse   — one coloured line per mouse (click legend to isolate one),
        mean ± std  — bold group mean with a ±1 std band across mice, individual
                      mice drawn faint behind it; the band is dropped where fewer
                      than MIN_BAND mice contribute (a 2-mouse std is meaningless),
  * hover a point for that session's numbers.

Static poster figures (one per task, headline metrics only):
  learning_curve_<metric>_<task>.png   per-mouse faint lines + bold mean ± std band.

Usage:
  python3 learning_curves_dashboard.py --task both
  python3 learning_curves_dashboard.py --task appetitive
"""
from __future__ import annotations

import argparse
import csv
import json
import os
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.ticker import MaxNLocator
import numpy as np
from plotly.offline import get_plotlyjs

import trial_history_analysis as TH  # task labels
import trial_engagement_licks_analysis as TEL  # raw-trial loaders (keep ITI times)
import learning_trajectories_analysis as LT  # stable per-mouse colours
import hit_fa_dashboard as HD  # per-session metric computation (session_row)
import extinction_analysis as EXT  # extinction loader (LED, reward withheld)

MIN_BAND = 3  # need >= this many mice at an ordinal to draw a std band there
_RESULTS_ROOT = Path(__file__).resolve().parent / "results"
_TASK_AREA = {"appetitive": "appetitive", "generalization": "generalization",
              "extinction": "extinction", "both": "cross_task", "all": "cross_task"}
_ENV_OUT = os.environ.get("MICS_LC_OUT")

# Task display labels + overlay colours. Extinction reuses the ExtinctionLED task_type.
EXT_TASK = "ExtinctionLED"
_TASK_LABELS = {**TH.TASK_LABELS, EXT_TASK: "Extinction (light)"}
_TASK_COLORS = {**TH.TASK_COLORS, EXT_TASK: "#2ca02c"}
# Response metrics defined + meaningful in ALL three tasks (reward metrics are ~0
# under extinction, so the cross-task overlay only compares response measures).
CROSS_METRICS = ["engagement_oncue", "engagement_any"]
# Reward-based metrics: for extinction (no water) these are ~0/degenerate, so the
# static learning-curve panels plot on-cue response there instead.
_REWARD_METRICS = {"hit_rate", "accuracy", "success_rate", "competence", "fa_rate"}
_EXT_RESPONSE = "oncue_lick_rate"  # extinction response measure: licks during cue / trials


def _task_label(task: str) -> str:
    return _TASK_LABELS.get(task, task)


def _panel_metric(task: str, key: str) -> str:
    """Metric actually plotted for a task panel: extinction swaps reward → response."""
    return _EXT_RESPONSE if (task == EXT_TASK and key in _REWARD_METRICS) else key

# Y-axis metrics offered, headline ones first. Keys match hit_fa_dashboard.session_row.
METRICS = [
    ["hit_rate", "hit rate = rewarded / trials  (%)"],
    ["accuracy", "accuracy = hits / (hits + false alarms)  (%)"],
    ["success_rate", "success rate = hit bouts / trials  (%)"],
    ["competence", "competence (accuracy | on-cue engaged)  (%)"],
    ["engagement_oncue", "on-cue engagement  (%)"],
    ["engagement_any", "engagement (any poke)  (%)"],
    ["oncue_lick_rate", "on-cue lick rate = lick during cue / trials  (%)"],
    ["fa_rate", "false-alarm rate = FA / trials  (%)"],
    ["offcue", "off-cue pokes / trial"],
    ["latency", "latency to engage  (s)"],
    ["n_trials", "session length (n trials)"],
]
HEADLINE = ["hit_rate", "accuracy"]  # metrics also rendered as static PNGs


# --- data ------------------------------------------------------------------
def _oncue_lick_rate(rec: dict) -> float | None:
    """% of trials with >=1 lick during the cue window [0, cue_dur] (session_row has
    no lick-in-cue metric, so it's computed here from the same raw trials)."""
    dur_key, trials = rec["dur_key"], rec["trials"]
    n = len(trials)
    if not n:
        return None
    licked = sum(1 for t in trials if any(0 <= lk <= t[dur_key] for lk in t["licks"]))
    return 100.0 * licked / n


def load_extinction(only_mouse: str | None) -> list[dict]:
    """Extinction sessions in the TEL record shape (dur_key + raw trials) so the
    same per-session metrics (session_row) apply. Reward metrics come out ~0 — the
    task has no water — which is why the cross-task overlay uses response metrics."""
    return [{"task": EXT_TASK, "mouse": r["mouse"], "session": r["session"],
             "dur_key": "led_dur", "trials": r["trials"]}
            for r in EXT.load_extinction(only_mouse)]


def build_rows(records: list[dict]) -> dict[str, dict[str, list[dict]]]:
    """{task: {mouse: [session_row(+ord) ordered by session]}}."""
    grouped: dict[str, dict[str, list[dict]]] = {}
    for r in records:
        grouped.setdefault(r["task"], {}).setdefault(r["mouse"], []).append(r)
    out: dict[str, dict[str, list[dict]]] = {}
    for task, by_mouse in grouped.items():
        out[task] = {}
        for m, recs in by_mouse.items():
            rows = []
            for ordinal, rec in enumerate(sorted(recs, key=lambda r: r["session"]), 1):
                row = HD.session_row(rec)
                row["oncue_lick_rate"] = _oncue_lick_rate(rec)
                row["ord"] = ordinal
                rows.append(row)
            out[task][m] = rows
    return out


def _mean_std_by_ord(by_mouse: dict[str, list[dict]], key: str) -> dict[int, tuple]:
    """{ordinal: (mean, std, n)} across mice for one metric (NaN-safe)."""
    per_ord: dict[int, list[float]] = {}
    for rows in by_mouse.values():
        for r in rows:
            v = r.get(key)
            if v is not None and not (isinstance(v, float) and np.isnan(v)):
                per_ord.setdefault(r["ord"], []).append(float(v))
    return {o: (float(np.mean(vs)), float(np.std(vs, ddof=1)) if len(vs) > 1 else 0.0, len(vs))
            for o, vs in per_ord.items()}


# --- static figure ---------------------------------------------------------
def fig_mean_std(by_task: dict, mcolors: dict, key: str, label: str, out_path: str) -> None:
    """Per-mouse faint lines + bold group mean with a ±1 std band, one panel/task."""
    tasks = list(by_task)
    fig, axes = plt.subplots(1, len(tasks), figsize=(6.6 * len(tasks), 5.4), squeeze=False)
    for ax, task in zip(axes[0], tasks):
        by_mouse = by_task[task]
        pkey = _panel_metric(task, key)  # extinction: reward metric -> on-cue response
        for m in LT._sorted_mice(by_mouse):
            pts = [(r["ord"], r[pkey]) for r in by_mouse[m]
                   if r.get(pkey) is not None and not np.isnan(r[pkey])]
            if pts:
                xs, ys = zip(*pts)
                ax.plot(xs, ys, color=mcolors[m], lw=1.0, alpha=0.35, zorder=2)
        stats = _mean_std_by_ord(by_mouse, pkey)
        ords = sorted(stats)
        means = np.array([stats[o][0] for o in ords])
        stds = np.array([stats[o][1] if stats[o][2] >= MIN_BAND else np.nan for o in ords])
        ax.plot(ords, means, color="black", lw=2.6, zorder=5, label="group mean")
        band = ~np.isnan(stds)
        if band.any():
            xo = np.array(ords)
            ax.fill_between(xo[band], (means - stds)[band], (means + stds)[band],
                            color="black", alpha=0.15, zorder=1, label="±1 std")
        if pkey != key:  # extinction shows a different (response) metric than the panel key
            ax.set_title(f"{_task_label(task)}\n(on-cue licking — no reward)")
            ax.set_ylabel(dict((k, lb) for k, lb in METRICS)[pkey])
        else:
            ax.set_title(_task_label(task))
        ax.set_xlabel("session number")
        ax.xaxis.set_major_locator(MaxNLocator(integer=True))
        ax.grid(alpha=0.3)
        ax.margins(x=0.02)
    axes[0][0].set_ylabel(label)
    axes[0][0].legend(loc="best", fontsize=9, frameon=False)
    fig.suptitle(f"Learning curve — {label}\nfaint = individual mice · bold = group mean "
                 f"± std (band shown where n≥{MIN_BAND} mice)", fontsize=12)
    fig.tight_layout(rect=(0, 0, 1, 0.92))
    fig.savefig(out_path, dpi=150)
    plt.close(fig)


# --- writers ---------------------------------------------------------------
def write_csv(by_task: dict, path: str) -> None:
    keys = [k for k, _ in METRICS]
    with open(path, "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["task", "mouse", "session_ordinal", "raw_session"] + keys)
        for task in by_task:
            for m in LT._sorted_mice(by_task[task]):
                for r in by_task[task][m]:
                    w.writerow([task, m, r["ord"], r["session"]]
                               + ["" if r.get(k) is None or (isinstance(r.get(k), float)
                                  and np.isnan(r[k])) else f"{r[k]:.3f}" for k in keys])


def fig_cross_task(by_task: dict, key: str, label: str, out_path: str) -> None:
    """Overlay the three tasks' group mean ± std for one response metric vs session,
    so learning (appetitive/generalization rise) can be compared with extinction."""
    fig, ax = plt.subplots(figsize=(8.0, 5.4))
    for task in by_task:
        stats = _mean_std_by_ord(by_task[task], key)
        ords = sorted(stats)
        if not ords:
            continue
        means = np.array([stats[o][0] for o in ords])
        stds = np.array([stats[o][1] if stats[o][2] >= MIN_BAND else np.nan for o in ords])
        c = _TASK_COLORS.get(task, "#555")
        ax.plot(ords, means, color=c, lw=2.4, marker="o", ms=5, zorder=5, label=_task_label(task))
        band = ~np.isnan(stds)
        if band.any():
            xo = np.array(ords)
            ax.fill_between(xo[band], (means - stds)[band], (means + stds)[band],
                            color=c, alpha=0.13, zorder=1)
    ax.set_xlabel("session number")
    ax.set_ylabel(label)
    ax.xaxis.set_major_locator(MaxNLocator(integer=True))
    ax.set_ylim(bottom=0)
    ax.grid(alpha=0.3)
    ax.legend(loc="best", fontsize=9, frameon=False, title="task")
    fig.suptitle(f"Cross-task comparison — {label}\ngroup mean ± std per session · "
                 "extinction session-means hide the steep within-session decay", fontsize=11)
    fig.tight_layout(rect=(0, 0, 1, 0.92))
    fig.savefig(out_path, dpi=150)
    plt.close(fig)


def _payload(task: str, by_mouse: dict, mcolors: dict) -> dict:
    mice = LT._sorted_mice(by_mouse)
    max_sessions = max((len(rows) for rows in by_mouse.values()), default=0)
    return {
        "task_label": _task_label(task),
        "mice": mice,
        "colors": {m: [int(round(255 * c)) for c in mcolors[m][:3]] for m in mice},
        "metrics": METRICS,
        # reward metrics are ~0 under extinction, so open it on a response metric
        "default_y": "engagement_oncue" if task == EXT_TASK else "hit_rate",
        "min_band": MIN_BAND,
        "max_sessions": max_sessions,
        "data": {m: by_mouse[m] for m in mice},
    }


def write_dashboard(by_task: dict, mcolors: dict, out_dir: str) -> list[str]:
    plotlyjs = get_plotlyjs()
    written = []
    for task, by_mouse in by_task.items():
        html = (_TEMPLATE
                .replace("__PLOTLYJS__", plotlyjs)
                .replace("__DATA__", json.dumps(_payload(task, by_mouse, mcolors)))
                .replace("__TITLE__", _task_label(task)))
        suffix = "" if len(by_task) == 1 else f"_{task}"
        path = os.path.join(out_dir, f"learning_curves{suffix}.html")
        with open(path, "w") as f:
            f.write(html)
        written.append(path)
    return written


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--task", choices=["appetitive", "generalization", "extinction",
                                            "both", "all"], default="all")
    parser.add_argument("--mouse", default=None, help="restrict to one mouse, e.g. m102")
    args = parser.parse_args()

    out_root = _ENV_OUT or str(_RESULTS_ROOT / "learning_curves" / _TASK_AREA[args.task])

    records: list[dict] = []
    if args.task in ("appetitive", "both", "all"):
        print("Loading appetitive (tone) task ...")
        records += TEL.load_appetitive(args.mouse)
    if args.task in ("generalization", "both", "all"):
        print("Loading generalization (light) task ...")
        records += TEL.load_generalization(args.mouse)
    if args.task in ("extinction", "all"):
        print("Loading extinction (light, reward withheld) task ...")
        records += load_extinction(args.mouse)
    if not records:
        print("No sessions found — nothing to do.")
        return 1

    by_task = build_rows(records)
    mcolors, _ = LT._mouse_colors(by_task)
    os.makedirs(out_root, exist_ok=True)

    html_paths = write_dashboard(by_task, mcolors, out_root)
    png = 0
    for key, label in METRICS:
        if key in HEADLINE:
            suffix = "" if len(by_task) == 1 else "_cross"
            fig_mean_std(by_task, mcolors, key, label,
                         os.path.join(out_root, f"learning_curve_{key}{suffix}.png"))
            png += 1
    if len(by_task) >= 2:  # cross-task overlay only makes sense with >=2 tasks
        for key in CROSS_METRICS:
            label = dict((k, lb) for k, lb in METRICS)[key]
            fig_cross_task(by_task, key, label,
                           os.path.join(out_root, f"learning_curve_crosstask_{key}.png"))
            png += 1
    write_csv(by_task, os.path.join(out_root, "learning_curves_by_session.csv"))

    n_sess = sum(len(s) for by_mouse in by_task.values() for s in by_mouse.values())
    print(f"\nWrote {len(html_paths)} interactive dashboard(s), {png} PNG(s), and 1 CSV "
          f"under '{out_root}/' ({n_sess} sessions).")
    return 0


_TEMPLATE = r"""<!doctype html>
<html><head><meta charset="utf-8"><title>__TITLE__ — learning curves</title>
<style>
  body{font-family:system-ui,Arial,sans-serif;margin:0;padding:14px;color:#222}
  #controls{display:flex;flex-wrap:wrap;gap:16px;align-items:center;
    padding:10px 12px;background:#f6f7f9;border:1px solid #e2e4e8;border-radius:8px;margin-bottom:8px}
  #controls label{font-size:13px;display:flex;gap:6px;align-items:center}
  select{font-size:13px;padding:2px 4px}
  #plot{width:100%;height:78vh}
  .hint{color:#777;font-size:12px}
</style>
<script>__PLOTLYJS__</script>
</head><body>
<div id="controls">
  <label>Metric (Y) <select id="ysel"></select></label>
  <label>Display
    <select id="mode">
      <option value="permouse">per mouse</option>
      <option value="meanstd">mean ± std</option>
      <option value="overlay">overlay (mice + mean)</option>
    </select>
  </label>
  <span class="hint">click a mouse in the legend to toggle · double-click to isolate</span>
</div>
<div id="plot"></div>
<script>
const DATA = __DATA__;
const $ = id => document.getElementById(id);
const YSEL=$('ysel'), MODE=$('mode'), PLOT=$('plot');

DATA.metrics.forEach(([k,l])=>{const o=document.createElement('option');o.value=k;o.textContent=l;YSEL.appendChild(o);});
YSEL.value=DATA.default_y;
const label = k => (DATA.metrics.find(e=>e[0]===k)||[k,k])[1];
const rgb = c => `rgb(${c[0]},${c[1]},${c[2]})`;
const rgba = (c,a) => `rgba(${c[0]},${c[1]},${c[2]},${a})`;

function val(r,k){const v=r[k];return (v==null||isNaN(v))?null:v;}

function meanStd(yk){
  const byOrd={};
  DATA.mice.forEach(m=>(DATA.data[m]||[]).forEach(r=>{
    const v=val(r,yk); if(v==null) return;
    (byOrd[r.ord]=byOrd[r.ord]||[]).push(v);
  }));
  const ords=Object.keys(byOrd).map(Number).sort((a,b)=>a-b);
  const mean=[],lo=[],hi=[],n=[];
  ords.forEach(o=>{
    const a=byOrd[o], mu=a.reduce((s,v)=>s+v,0)/a.length;
    const sd=a.length>1?Math.sqrt(a.reduce((s,v)=>s+(v-mu)*(v-mu),0)/(a.length-1)):0;
    mean.push(mu); n.push(a.length);
    lo.push(a.length>=DATA.min_band?mu-sd:null); hi.push(a.length>=DATA.min_band?mu+sd:null);
  });
  return {ords,mean,lo,hi,n};
}

function redraw(){
  const yk=YSEL.value, mode=MODE.value, traces=[];
  const prevVis={}; (PLOT.data||[]).forEach(t=>{if(DATA.mice.includes(t.name))prevVis[t.name]=t.visible;});
  const showMice=(mode==='permouse'||mode==='overlay'), showMean=(mode==='meanstd'||mode==='overlay');
  const ghost=(mode==='meanstd');  // meanstd draws faint non-interactive ghost lines
  if(showMice||ghost){
    DATA.mice.forEach(m=>{
      const pts=(DATA.data[m]||[]).map(r=>({x:r.ord,y:val(r,yk),s:r.session,
        hits:r.hits,fa:r.false_alarms,n:r.n_trials})).filter(p=>p.y!=null);
      if(!pts.length) return;
      const c=DATA.colors[m];
      if(ghost){
        traces.push({type:'scatter',mode:'lines',x:pts.map(p=>p.x),y:pts.map(p=>p.y),
          line:{color:rgba(c,0.28),width:1},name:m,legendgroup:m,showlegend:false,hoverinfo:'skip'});
      } else {
        traces.push({type:'scatter',mode:'lines+markers',name:m,legendgroup:m,
          visible: prevVis[m]===undefined?true:prevVis[m],
          x:pts.map(p=>p.x),y:pts.map(p=>p.y),line:{color:rgb(c),width:2},marker:{size:7,color:rgb(c)},
          customdata:pts.map(p=>[p.s,p.hits,p.fa,p.n]),
          hovertemplate:'<b>'+m+'</b> session %{x} (raw %{customdata[0]})<br>'+
            label(yk)+': %{y:.2f}<br>hits %{customdata[1]} · FA %{customdata[2]} · trials %{customdata[3]}<extra></extra>'});
      }
    });
  }
  if(showMean){
    const s=meanStd(yk);
    // std band as an upper trace then a lower trace filled to it
    const bandX=[],bandLo=[],bandHi=[];
    s.ords.forEach((o,i)=>{ if(s.lo[i]!=null){bandX.push(o);bandLo.push(s.lo[i]);bandHi.push(s.hi[i]);} });
    if(bandX.length){
      traces.push({type:'scatter',mode:'lines',x:bandX,y:bandHi,line:{width:0},
        showlegend:false,hoverinfo:'skip'});
      traces.push({type:'scatter',mode:'lines',x:bandX,y:bandLo,line:{width:0},fill:'tonexty',
        fillcolor:'rgba(0,0,0,0.13)',name:'±1 std',legendgroup:'std',hoverinfo:'skip'});
    }
    traces.push({type:'scatter',mode:'lines+markers',x:s.ords,y:s.mean,
      line:{color:'black',width:3},marker:{size:7,color:'black'},name:'group mean',legendgroup:'mean',
      customdata:s.n,
      hovertemplate:'session %{x}<br>'+label(yk)+': %{y:.2f}<br>n=%{customdata} mice<extra></extra>'});
  }
  const subtitle={permouse:'one line per mouse',
    meanstd:'group mean ± std, band where n≥'+DATA.min_band+' mice',
    overlay:'individual mice + group mean ± std'}[mode];
  const config={responsive:true,
    modeBarButtonsToAdd:[{name:'Download PNG',icon:Plotly.Icons.camera,
      click:gd=>Plotly.downloadImage(gd,{format:'png',width:1200,height:760,scale:2,
        filename:DATA.task_label.replace(/[^A-Za-z0-9]+/g,'_')+'__'+yk+'__'+mode})}]};
  Plotly.react('plot', traces, {
    title:{text:DATA.task_label+' — learning curve<br><sup>'+label(yk)+' vs session · '+subtitle+'</sup>'},
    xaxis:{title:{text:'session number'},dtick:1,zeroline:false,showline:true,linecolor:'#444',gridcolor:'#eee'},
    yaxis:{title:{text:label(yk)},zeroline:false,showline:true,linecolor:'#444',gridcolor:'#eee'},
    hovermode:'closest', legend:{title:{text:'mouse'}},
    plot_bgcolor:'white', paper_bgcolor:'white', margin:{t:70}
  }, config);
}

[YSEL,MODE].forEach(el=>el.addEventListener('change',redraw));
redraw();
</script>
</body></html>"""


if __name__ == "__main__":
    raise SystemExit(main())
