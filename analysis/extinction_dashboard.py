#!/usr/bin/env python3
"""Interactive dashboard for the extinction trial-by-trial decay.

One self-contained offline HTML (Plotly embedded, no server) in which the viewer
can, entirely in-browser:
  * pick the metric (on-cue poke rate / on-cue lick rate),
  * change the BIN SIZE N (trials per block) live — each session is split into
    ~equal N-trial blocks and the block's response rate is plotted,
  * switch display between per-mouse lines and the group mean ± std band.

Both sessions are laid end-to-end on one trial-number axis (session 2 offset by
session_len) with a dashed divider at each session boundary. The raw per-trial 0/1
response sequences are embedded and (re)binned in JS on every control change, so N
is fully interactive.

Called by extinction_analysis.write outputs; not run directly.
"""
from __future__ import annotations

import json
import os

from plotly.offline import get_plotlyjs


def _rgb255(color) -> list[int]:
    return [int(round(255 * c)) for c in color[:3]]


def _payload(raw: dict, colors: dict, metrics: list, session_len: int,
             default_bin: int, min_band: int) -> dict:
    mice = list(raw)
    max_session = max((int(s) for sess in raw.values() for s in sess), default=1)
    return {
        "mice": mice,
        "colors": {m: _rgb255(colors[m]) for m in mice},
        "metrics": metrics,
        "session_len": session_len,
        "max_session": max_session,
        "default_bin": default_bin,
        "min_band": min_band,
        "data": {m: {str(s): rates for s, rates in sess.items()} for m, sess in raw.items()},
    }


def write_dashboard(raw: dict, colors: dict, metrics: list, session_len: int,
                    default_bin: int, min_band: int, out_dir: str) -> str:
    """Write the single interactive extinction dashboard HTML; return its path."""
    payload = _payload(raw, colors, metrics, session_len, default_bin, min_band)
    html = (_TEMPLATE
            .replace("__PLOTLYJS__", get_plotlyjs())
            .replace("__DATA__", json.dumps(payload)))
    path = os.path.join(out_dir, "extinction_decay_dashboard.html")
    with open(path, "w") as f:
        f.write(html)
    return path


_TEMPLATE = r"""<!doctype html>
<html><head><meta charset="utf-8"><title>Extinction decay — dashboard</title>
<style>
  body{font-family:system-ui,Arial,sans-serif;margin:0;padding:14px;color:#222}
  #controls{display:flex;flex-wrap:wrap;gap:16px;align-items:center;
    padding:10px 12px;background:#f6f7f9;border:1px solid #e2e4e8;border-radius:8px;margin-bottom:8px}
  #controls label{font-size:13px;display:flex;gap:6px;align-items:center}
  select,input{font-size:13px;padding:2px 4px}
  #plot{width:100%;height:78vh}
  .hint{color:#777;font-size:12px}
</style>
<script>__PLOTLYJS__</script>
</head><body>
<div id="controls">
  <label>Metric <select id="ysel"></select></label>
  <label>Bin size N <input id="binN" type="number" min="1" step="1" style="width:4.5em"> trials</label>
  <label>Display
    <select id="mode">
      <option value="permouse">per mouse</option>
      <option value="meanstd">mean ± std</option>
      <option value="overlay">overlay (mice + mean)</option>
    </select>
  </label>
  <span class="hint">each session is its own panel (trials 1–N) · split into ~equal N-trial blocks</span>
</div>
<div id="plot"></div>
<script>
const DATA = __DATA__;
const $ = id => document.getElementById(id);
const YSEL=$('ysel'), BINN=$('binN'), MODE=$('mode'), PLOT=$('plot');
const L=DATA.session_len, P=DATA.max_session;

DATA.metrics.forEach(([k,l])=>{const o=document.createElement('option');o.value=k;o.textContent=l;YSEL.appendChild(o);});
YSEL.value=DATA.metrics[0][0];
BINN.value=DATA.default_bin; BINN.max=L;
const label = k => (DATA.metrics.find(e=>e[0]===k)||[k,k])[1];
const rgb = c => `rgb(${c[0]},${c[1]},${c[2]})`;

// ~equal blocks: split L items into round(L/N) blocks (sizes differ by <=1, no tiny tail)
function blocks(N){
  const b=Math.max(1,Math.round(L/N)), out=[]; let start=0;
  for(let i=0;i<b;i++){
    const size=Math.floor(L/b)+(i<L%b?1:0);
    out.push({start:start, end:start+size, center:start+(size+1)/2}); // center 1-based
    start+=size;
  }
  return out;
}
function blockRates(seq,bl){
  return bl.map(b=>{
    const s=seq.slice(b.start,Math.min(b.end,seq.length));
    return s.length? 100*s.reduce((a,v)=>a+v,0)/s.length : null;
  });
}
// one x-axis per session, laid side by side; session s -> 'x'(s==1) / 'x'+s
function panelDomains(){const g=0.08,w=(1-g*(P-1))/P,out=[];for(let i=0;i<P;i++){const s=i*(w+g);out.push([s,s+w]);}return out;}
const xref = s => s===1?'x':'x'+s;

function meanTracesForSession(s,bl,yk){
  const xs=[],mean=[],lo=[],hi=[];
  bl.forEach((b,i)=>{
    const vals=[];
    DATA.mice.forEach(m=>{const mseq=(DATA.data[m]||{})[s]; if(mseq&&mseq[yk]){const r=blockRates(mseq[yk],bl)[i]; if(r!=null)vals.push(r);}});
    if(!vals.length) return;
    const mu=vals.reduce((a,v)=>a+v,0)/vals.length;
    const sd=vals.length>1?Math.sqrt(vals.reduce((a,v)=>a+(v-mu)*(v-mu),0)/(vals.length-1)):0;
    xs.push(b.center); mean.push(mu);
    lo.push(vals.length>=DATA.min_band?mu-sd:null); hi.push(vals.length>=DATA.min_band?mu+sd:null);
  });
  const out=[];
  if(!xs.length) return out;
  const bx=[],blo=[],bhi=[];
  xs.forEach((x,i)=>{ if(lo[i]!=null){bx.push(x);blo.push(lo[i]);bhi.push(hi[i]);} });
  if(bx.length){
    out.push({type:'scatter',mode:'lines',xaxis:xref(s),yaxis:'y',x:bx,y:bhi,line:{width:0},showlegend:false,hoverinfo:'skip'});
    out.push({type:'scatter',mode:'lines',xaxis:xref(s),yaxis:'y',x:bx,y:blo,line:{width:0},fill:'tonexty',
      fillcolor:'rgba(0,0,0,0.13)',name:'±1 std',legendgroup:'std',showlegend:s===1,hoverinfo:'skip'});
  }
  out.push({type:'scatter',mode:'lines+markers',xaxis:xref(s),yaxis:'y',x:xs,y:mean,
    line:{color:'black',width:2.8},marker:{size:6,color:'black'},
    name:'group mean',legendgroup:'mean',showlegend:s===1,
    hovertemplate:'session '+s+'<br>trial ~%{x:.0f}<br>'+label(yk)+': %{y:.1f}<extra></extra>'});
  return out;
}

function redraw(){
  const yk=YSEL.value, mode=MODE.value;
  const N=Math.max(1,Math.min(L,parseInt(BINN.value)||DATA.default_bin));
  const bl=blocks(N), traces=[];
  const prevVis={}; (PLOT.data||[]).forEach(t=>{if(DATA.mice.includes(t.name))prevVis[t.name]=t.visible;});
  const showMice = (mode==='permouse'||mode==='overlay');
  const showMean = (mode==='meanstd'||mode==='overlay');
  const faint = mode==='overlay';

  if(showMice){
    DATA.mice.forEach(m=>{
      let first=true;
      for(let s=1;s<=P;s++){
        const mseq=(DATA.data[m]||{})[s]; if(!mseq||!mseq[yk]) continue;
        const rates=blockRates(mseq[yk],bl), c=DATA.colors[m], xs=[],ys=[];
        bl.forEach((b,i)=>{ if(rates[i]!=null){xs.push(b.center);ys.push(rates[i]);} });
        if(!xs.length) continue;
        traces.push({type:'scatter',mode:'lines+markers',name:m,legendgroup:m,
          showlegend:first, visible: prevVis[m]===undefined?true:prevVis[m],
          xaxis:xref(s),yaxis:'y',x:xs,y:ys,
          line:{color:rgb(c),width:faint?1.2:1.8}, opacity:faint?0.45:1,
          marker:{size:faint?4:6,color:rgb(c)},
          hovertemplate:'<b>'+m+'</b> session '+s+'<br>trial ~%{x:.0f}<br>'+label(yk)+': %{y:.1f}<extra></extra>'});
        first=false;
      }
    });
  }
  if(showMean){
    for(let s=1;s<=P;s++) meanTracesForSession(s,bl,yk).forEach(t=>traces.push(t));
  }

  const doms=panelDomains(), layout={
    title:{text:'Extinction decay by trial — '+label(yk)+
      '<br><sup>bin = '+N+' trials · each session on its own trial-1…N axis · '+
      ({permouse:'one line per mouse',meanstd:'group mean ± std (band where n≥'+DATA.min_band+' mice)',
        overlay:'individual mice + group mean ± std'}[mode])+'</sup>'},
    yaxis:{title:{text:label(yk)},domain:[0,1],zeroline:false,showline:true,
      linecolor:'#444',gridcolor:'#eee',rangemode:'tozero'},
    hovermode:'closest', legend:{title:{text:'mouse'}},
    plot_bgcolor:'white', paper_bgcolor:'white', margin:{t:70}, annotations:[]
  };
  doms.forEach((d,i)=>{
    layout[i===0?'xaxis':'xaxis'+(i+1)]={domain:d,anchor:'y',range:[0,L+1],
      title:{text:'trial number'},zeroline:false,showline:true,linecolor:'#444',gridcolor:'#eee'};
    layout.annotations.push({x:(d[0]+d[1])/2,y:1.0,xref:'paper',yref:'paper',yanchor:'bottom',
      text:'session '+(i+1),showarrow:false,font:{size:13,color:'#333'}});
  });
  const config={responsive:true,
    modeBarButtonsToAdd:[{name:'Download PNG',icon:Plotly.Icons.camera,
      click:gd=>Plotly.downloadImage(gd,{format:'png',width:1300,height:720,scale:2,
        filename:'extinction_'+yk+'_bin'+N+'_'+mode})}]};
  Plotly.react('plot', traces, layout, config);
}

[YSEL,MODE].forEach(el=>el.addEventListener('change',redraw));
[BINN].forEach(el=>{el.addEventListener('change',redraw);el.addEventListener('input',redraw);});
redraw();
</script>
</body></html>"""
