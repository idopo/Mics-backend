#!/usr/bin/env python3
"""Interactive ROC / AUC dashboard, per task (Gili).

An ROC (Receiver Operating Characteristic) curve asks: can a chosen behavioural
PROPERTY separate one class of trials from another? Sweeping a threshold on the
property gives (false-alarm rate, hit rate) points; the curve's AUC (0.5 = chance,
1 = perfect) is how well the property discriminates the two classes.

Everything is computed in the browser from per-trial values, so you can switch:
  - CONTRAST  — the two classes (reward vs catch, reward vs all non-reward, engaged vs not)
  - PROPERTY  — the decision variable (response licks, biggest lick bout, total licks,
                on-cue pokes, ITI licks)
  - SHOW      — all mice (one ROC each + cohort) or one mouse across its sessions

Catch uses the canonical action_sequence_analysis definition (on-cue poke +
response-window lick + no reward).

Usage:
    python3 bin_roc.py --task appetitive
    python3 bin_roc.py --task both
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
import learning_trajectories_analysis as LT  # noqa: E402  colours/order, LICK_BOUT_GAP

_RESULTS_ROOT = Path(__file__).resolve().parent.parent / "results"
_TASK_AREA = {"appetitive": "appetitive", "generalization": "generalization", "both": "cross_task"}

# decision variables (all oriented so higher = more responsive)
PROPERTIES = [
    ["rlicks", "response-window licks (0 → iti_start)"],
    ["max_bout", "biggest response lick-bout (licks)"],
    ["tlicks", "total licks in trial"],
    ["opokes", "on-cue pokes"],
    ["iti_licks", "ITI licks (iti_start → end)"],
]
CONTRASTS = [
    ["reward_vs_catch", "reward (HIT) vs catch"],
    ["reward_vs_nonreward", "reward vs all non-reward"],
    ["engaged_vs_not", "engaged (on-cue poke) vs not engaged"],
]


def _max_bout(licks: list[float]) -> int:
    """Largest lick-bout size (a gap > LICK_BOUT_GAP ends a bout)."""
    ordered = sorted(licks)
    if not ordered:
        return 0
    best = size = 1
    for prev, cur in zip(ordered, ordered[1:]):
        size = 1 if cur - prev > LT.LICK_BOUT_GAP else size + 1
        best = max(best, size)
    return best


def trial_record(t: dict, session: int) -> dict:
    """Per-trial flags (class membership) + decision properties for the ROC."""
    cue, i0, i1 = t["cue_dur"], t["iti_start"], t["iti_end"]
    on_cue = [p for p in t["nose_pokes"] if 0 <= p <= cue]
    resp_licks = [lk for lk in t["licks"] if 0 <= lk < i0]
    eng = 1 if on_cue else 0
    rew = 1 if t["rewarded"] else 0
    catch = 1 if (eng and resp_licks and not rew) else 0
    return {
        "s": session,
        "eng": eng, "rew": rew, "catch": catch,
        "rlicks": len(resp_licks),
        "max_bout": _max_bout(resp_licks),
        "tlicks": len(t["licks"]),
        "opokes": len(on_cue),
        "iti_licks": sum(1 for lk in t["licks"] if i0 <= lk <= i1),
    }


def build_payload(task: str, records: list[dict], mcolors: dict) -> dict:
    trials: dict[str, list[dict]] = {}
    for r in records:
        trials.setdefault(r["mouse"], []).extend(
            trial_record(t, r["training_day"]) for t in r["trials"])
    mice = LT._sorted_mice(trials)
    colors = {m: [int(round(255 * c)) for c in mcolors[m][:3]] for m in mice}
    colors["ALL"] = [20, 20, 20]
    return {
        "task_label": TH.TASK_LABELS.get(task, task),
        "mice": mice,
        "colors": colors,
        "properties": PROPERTIES,
        "contrasts": CONTRASTS,
        "default_property": "max_bout",
        # reward_vs_catch is too sparse per-session for per-mouse curves (catch is
        # rare), so default to a contrast that populates every mouse.
        "default_contrast": "reward_vs_nonreward",
        "trials": trials,
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
        path = os.path.join(out_dir, f"roc_curves{suffix}.html")
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
    print(f"\nWrote {len(paths)} ROC dashboard(s) under '{out_dir}/':")
    for p in paths:
        print(f"  {p}")
    return 0


_TEMPLATE = r"""<!doctype html>
<html><head><meta charset="utf-8"><title>__TITLE__ — ROC</title>
<style>
  body{font-family:system-ui,Arial,sans-serif;margin:0;padding:14px;color:#222}
  #controls{display:flex;flex-wrap:wrap;gap:14px;align-items:center;
    padding:10px 12px;background:#f6f7f9;border:1px solid #e2e4e8;border-radius:8px;margin-bottom:8px}
  #controls label{font-size:13px;display:flex;gap:6px;align-items:center}
  select{font-size:13px;padding:2px 4px}
  #plot{width:100%;height:80vh}
  .hint{color:#777;font-size:12px}
</style>
<script>__PLOTLYJS__</script>
</head><body>
<div id="controls">
  <label>View <select id="vsel">
    <option value="roc">ROC curves</option>
    <option value="auc">AUC across sessions</option>
  </select></label>
  <label>Show <select id="msel"></select></label>
  <label>Contrast <select id="csel"></select></label>
  <label>Property <select id="psel"></select></label>
  <label id="mtwrap" style="display:none">Metric <select id="mtsel">
    <option value="auc">AUC</option>
    <option value="dprime">d′ (sensitivity)</option>
  </select></label>
  <span class="hint">AUC 0.5 / d′ 0 = chance · needs ≥5 trials per class · "reward vs catch" is cohort-only (catch too rare per session)</span>
</div>
<div id="plot"></div>
<script>
const DATA = __DATA__;
const $ = id => document.getElementById(id);
const VSEL=$('vsel'), MSEL=$('msel'), CSEL=$('csel'), PSEL=$('psel'), MTSEL=$('mtsel'), PLOT=$('plot');
const MINCLASS = 5;

const CONTRAST_FN = {
  reward_vs_catch:     {pos:t=>t.rew===1, neg:t=>t.catch===1},
  reward_vs_nonreward: {pos:t=>t.rew===1, neg:t=>t.rew===0},
  engaged_vs_not:      {pos:t=>t.eng===1, neg:t=>t.eng===0},
};

[['__ALL__','All mice']].concat(DATA.mice.map(m=>[m,m])).forEach(([v,t])=>{
  const o=document.createElement('option'); o.value=v; o.textContent=t; MSEL.appendChild(o);});
MSEL.value='__ALL__';
DATA.contrasts.forEach(([k,l])=>{const o=document.createElement('option');o.value=k;o.textContent=l;CSEL.appendChild(o);});
CSEL.value=DATA.default_contrast;
DATA.properties.forEach(([k,l])=>{const o=document.createElement('option');o.value=k;o.textContent=l;PSEL.appendChild(o);});
PSEL.value=DATA.default_property;

const rgb = c => `rgb(${c[0]},${c[1]},${c[2]})`;
const clabel = k => (DATA.contrasts.find(e=>e[0]===k)||[k,k])[1];
const plabel = k => (DATA.properties.find(e=>e[0]===k)||[k,k])[1];

// ROC points + AUC for a set of trials, given property + contrast predicates
function roc(trials, pk, con){
  const vals=[], labs=[];
  trials.forEach(t=>{
    const pos=con.pos(t), neg=con.neg(t);
    if(pos===neg) return;                 // not in either class (or both) -> skip
    const v=t[pk]; if(v==null||isNaN(v)) return;
    vals.push(v); labs.push(pos?1:0);
  });
  const P=labs.reduce((s,l)=>s+l,0), N=labs.length-P;
  if(P<MINCLASS||N<MINCLASS) return null;
  const pairs=vals.map((v,i)=>[v,labs[i]]).sort((a,b)=>b[0]-a[0]);
  let tp=0, fp=0, i=0; const pts=[[0,0]];
  while(i<pairs.length){ const v=pairs[i][0];
    while(i<pairs.length && pairs[i][0]===v){ pairs[i][1]?tp++:fp++; i++; }
    pts.push([fp/N, tp/P]);
  }
  let auc=0; for(let k=1;k<pts.length;k++) auc+=(pts[k][0]-pts[k-1][0])*(pts[k][1]+pts[k-1][1])/2;
  return {pts, auc, P, N};
}
function shade(base, t){
  t=Math.max(0,Math.min(1,t));
  const light=base.map(c=>Math.round(c+(255-c)*0.62)), dark=base.map(c=>Math.round(c*0.45));
  return [0,1,2].map(j=>Math.round(light[j]+t*(dark[j]-light[j])));
}
function curveTrace(r, name, c, bold, dp){
  const dt = (dp!=null && !isNaN(dp)) ? ', d′ '+dp.toFixed(2) : '';
  return {type:'scatter', mode:'lines', name:name+' (AUC '+r.auc.toFixed(2)+dt+')',
    x:r.pts.map(p=>p[0]), y:r.pts.map(p=>p[1]),
    line:{color:rgb(c), width:bold?3.5:1.5, shape:'hv'}, opacity:bold?1:0.85,
    hovertemplate:name+'<br>FA %{x:.2f} · hit %{y:.2f}<br>AUC '+r.auc.toFixed(3)+dt+
      ' (P='+r.P+', N='+r.N+')<extra></extra>'};
}

const sessionsOf = tr => [...new Set(tr.map(t=>t.s))].sort((a,b)=>a-b);
const aucOrNull = (trials, pk, con) => { const r=roc(trials, pk, con); return r?r.auc:null; };

// d' (sensitivity) = standardized mean difference of the property between classes:
// (mean_pos - mean_neg) / sqrt((var_pos + var_neg)/2). Equal-variance signal detection.
function dprime(trials, pk, con){
  const pos=[], neg=[];
  trials.forEach(t=>{ const p=con.pos(t), n=con.neg(t); if(p===n) return;
    const v=t[pk]; if(v==null||isNaN(v)) return; (p?pos:neg).push(v); });
  if(pos.length<MINCLASS||neg.length<MINCLASS) return null;
  const mean=a=>a.reduce((s,x)=>s+x,0)/a.length;
  const mp=mean(pos), mn=mean(neg);
  const vr=(a,m)=>a.reduce((s,x)=>s+(x-m)*(x-m),0)/a.length;
  const sd=Math.sqrt((vr(pos,mp)+vr(neg,mn))/2);
  return sd>0 ? (mp-mn)/sd : null;
}
const statOf = (trials,pk,con,metric) => metric==='dprime' ? dprime(trials,pk,con) : aucOrNull(trials,pk,con);

// per-session stat (AUC or d') for a set of trials -> {x:[session], y:[stat]}
function statSeries(tr, pk, con, metric){
  const xs=[], ys=[];
  sessionsOf(tr).forEach(s=>{ const v=statOf(tr.filter(t=>t.s===s), pk, con, metric);
    if(v!=null){ xs.push(s); ys.push(v); } });
  return {xs, ys};
}

function drawAUC(){
  const pk=PSEL.value, ck=CSEL.value, con=CONTRAST_FN[ck], sel=MSEL.value, metric=MTSEL.value;
  const single=sel!=='__ALL__', traces=[], isD=metric==='dprime';
  const mice = single ? [sel] : DATA.mice;
  const label2 = isD ? "d′" : "AUC";
  let maxS=1;
  const addLine=(se,name,c,w,ms)=>{ if(!se.xs.length) return; maxS=Math.max(maxS, ...se.xs);
    traces.push({type:'scatter', mode:'lines+markers', name:name, x:se.xs, y:se.ys,
      line:{color:rgb(c), width:w}, marker:{size:ms}, connectgaps:false,
      hovertemplate:'<b>'+name+'</b> session %{x}<br>'+label2+' %{y:.3f}<extra></extra>'}); };
  mice.forEach(m=>addLine(statSeries(DATA.trials[m]||[], pk, con, metric), m, DATA.colors[m], single?3:1.8, 6));
  if(!single){
    const all=[]; DATA.mice.forEach(m=>all.push(...(DATA.trials[m]||[])));
    addLine(statSeries(all, pk, con, metric), 'ALL', DATA.colors.ALL, 4, 7);
  }
  const chance = isD ? 0 : 0.5;
  traces.push({type:'scatter', mode:'lines', name:'chance', x:[1,maxS], y:[chance,chance],
    line:{color:'#bbb', dash:'dash', width:1}, hoverinfo:'skip', showlegend:false});
  Plotly.react('plot', traces, {
    title:{text:DATA.task_label+' — '+label2+' across sessions: '+clabel(ck)+
      '<br><sup>decision property = '+plabel(pk)+' · does discrimination improve with training?'+
      ' · '+(isD?'0 = chance':'0.5 = chance')+'</sup>'},
    xaxis:{title:{text:'session (training day)'}, dtick:1, zeroline:false, showline:true,
           linecolor:'#444', gridcolor:'#eee'},
    yaxis:{title:{text:label2}, range:isD?null:[0.35,1.0], autorange:isD?true:false,
           zeroline:isD, showline:true, linecolor:'#444', gridcolor:'#eee'},
    hovermode:'closest', legend:{title:{text:'mouse'}},
    plot_bgcolor:'white', paper_bgcolor:'white', margin:{t:70}
  }, {responsive:true});
}

function redraw(){
  $('mtwrap').style.display = VSEL.value==='auc' ? '' : 'none';
  if(VSEL.value==='auc') return drawAUC();
  const pk=PSEL.value, ck=CSEL.value, con=CONTRAST_FN[ck], sel=MSEL.value;
  const single=sel!=='__ALL__', traces=[];
  const add=(tr,name,c,bold)=>{ const r=roc(tr, pk, con);
    if(r) traces.push(curveTrace(r, name, c, bold, dprime(tr, pk, con))); };
  if(!single){
    DATA.mice.forEach(m=>add(DATA.trials[m]||[], m, DATA.colors[m], false));
    const all=[]; DATA.mice.forEach(m=>all.push(...(DATA.trials[m]||[])));
    add(all, 'ALL', DATA.colors.ALL, true);
  } else {
    const tr=DATA.trials[sel]||[], sessions=[...new Set(tr.map(t=>t.s))].sort((a,b)=>a-b);
    sessions.forEach((s,idx)=>add(tr.filter(t=>t.s===s), 's'+s,
      shade(DATA.colors[sel], sessions.length>1?idx/(sessions.length-1):1), false));
    add(tr, sel+' (all)', DATA.colors.ALL, true);
  }
  traces.push({type:'scatter', mode:'lines', name:'chance', x:[0,1], y:[0,1],
    line:{color:'#bbb', dash:'dash', width:1}, hoverinfo:'skip', showlegend:false});
  const scope = single ? sel+' — one ROC per session' : 'one ROC per mouse + cohort';
  Plotly.react('plot', traces, {
    title:{text:DATA.task_label+' — ROC: '+clabel(ck)+
      '<br><sup>decision property = '+plabel(pk)+' · '+scope+
      ' · curve up-left = better discrimination</sup>'},
    xaxis:{title:{text:'false-alarm rate  (negative class)'}, range:[0,1], constrain:'domain',
           zeroline:false, showline:true, linecolor:'#444', gridcolor:'#eee'},
    yaxis:{title:{text:'hit rate  (positive class)'}, range:[0,1], scaleanchor:'x',
           zeroline:false, showline:true, linecolor:'#444', gridcolor:'#eee'},
    hovermode:'closest', legend:{title:{text:single?'session':'mouse'}},
    plot_bgcolor:'white', paper_bgcolor:'white', margin:{t:70}
  }, {responsive:true});
}

[VSEL,MSEL,CSEL,PSEL,MTSEL].forEach(el=>el.addEventListener('change',redraw));
redraw();
</script>
</body></html>"""


if __name__ == "__main__":
    raise SystemExit(main())
