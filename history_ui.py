"""Dedicated history page for PortScope."""

HISTORY_HTML = r"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>PortScope History</title>
<style>
  :root{
    --bg:#0F1117; --panel:#171B25; --line:#262C3B;
    --text:#D8DEE9; --muted:#5C6678;
    --amber:#FFB454; --steel:#7FB4D9; --rose:#FF6B7A;
    --mono:ui-monospace,'SF Mono',SFMono-Regular,Menlo,Consolas,monospace;
  }
  *{box-sizing:border-box;margin:0;padding:0}
  body{background:var(--bg);color:var(--text);font-family:var(--mono);font-size:13px;min-height:100vh}
  header{display:flex;align-items:center;gap:14px;padding:14px 18px;border-bottom:1px solid var(--line);flex-wrap:wrap}
  .mark{letter-spacing:.35em;font-weight:700;font-size:14px}
  .mark b{color:var(--amber)}
  .muted{color:var(--muted)}
  .controls{margin-left:auto;display:flex;gap:8px;align-items:center}
  button,a.btn{background:var(--panel);color:var(--text);border:1px solid var(--line);border-radius:6px;
    padding:6px 10px;font-family:var(--mono);font-size:12px;cursor:pointer;text-decoration:none}
  button:hover,a.btn:hover{border-color:var(--amber)}
  button:focus-visible,a.btn:focus-visible{outline:2px solid var(--amber);outline-offset:1px}
  main{display:grid;grid-template-columns:380px minmax(0,1fr);height:calc(100vh - 58px)}
  @media(max-width:980px){ main{grid-template-columns:1fr;height:auto} #list{max-height:45vh} }
  #list{border-right:1px solid var(--line);overflow:auto;background:var(--panel)}
  #detail{overflow:auto;padding:16px 18px}
  .head{padding:10px 14px;border-bottom:1px solid var(--line);color:var(--muted);letter-spacing:.1em;font-size:11px;text-transform:uppercase}
  .row{padding:10px 14px;border-bottom:1px solid var(--line);cursor:pointer}
  .row:hover,.row.sel{background:#1D2330}
  .row:focus-visible{outline:2px solid var(--amber);outline-offset:-2px;background:#1D2330}
  .row .time{font-weight:600}
  .row .meta{font-size:11px;color:var(--muted);margin-top:3px}
  .card{background:#131722;border:1px solid var(--line);border-radius:8px;padding:12px 14px;margin-bottom:12px}
  .card h3{font-size:12px;letter-spacing:.08em;color:var(--muted);text-transform:uppercase;margin-bottom:8px}
  .kv{display:flex;gap:14px;flex-wrap:wrap}
  .kv span{color:var(--muted)}
  .kv b{color:var(--text)}
  .mini{width:100%;height:120px;display:block}
  .err{padding:12px;color:var(--rose)}
</style>
</head>
<body>
<header>
  <span class="mark">PORT<b>SCOPE</b></span>
  <span class="muted">History</span>
  <div class="controls">
    <button id="refresh">Refresh</button>
    <a class="btn" href="/">Live map</a>
  </div>
</header>
<main>
  <section id="list">
    <div class="head">Snapshots</div>
    <div id="rows"></div>
  </section>
  <section id="detail">
    <div class="card">
      <h3>Selected Snapshot</h3>
      <div id="summary" class="kv"></div>
    </div>
    <div class="card">
      <h3>Exposure Trend</h3>
      <svg id="trend" class="mini" viewBox="0 0 500 120" role="img" aria-label="Exposure trend"></svg>
    </div>
    <div class="card">
      <h3>Top Listening Processes</h3>
      <div id="top"></div>
    </div>
  </section>
</main>
<script>
"use strict";
const $=id=>document.getElementById(id);
let items=[], selectedEpoch=null;

function exposedCount(snap){
  return (snap.listeners||[]).filter(l=>l.scope==="exposed"||l.scope==="lan").length;
}

function bindActivate(node, action){
  node.addEventListener("click", action);
  node.addEventListener("keydown", e=>{
    if(e.key === "Enter" || e.key === " "){
      e.preventDefault();
      action();
    }
  });
}

async function loadHistory(){
  const r=await fetch("/api/history?limit=200");
  if(!r.ok)throw new Error("history status "+r.status);
  const body=await r.json();
  items=(body&&Array.isArray(body.items)?body.items:[]);
  if(selectedEpoch&&!items.some(i=>i.epoch===selectedEpoch))selectedEpoch=null;
  if(!selectedEpoch&&items.length)selectedEpoch=items[0].epoch;
  render();
}

function render(){
  const rows=$("rows");
  rows.innerHTML="";
  if(!items.length){
    rows.innerHTML='<div class="err">No history yet. Generate snapshots from the live map.</div>';
    $("summary").innerHTML="";
    $("top").innerHTML="";
    $("trend").innerHTML="";
    return;
  }

  for(const snap of items){
    const d=document.createElement("div");
    const sel=snap.epoch===selectedEpoch;
    d.className="row"+(sel?" sel":"");
    d.setAttribute("tabindex","0");
    d.setAttribute("role","button");
    d.setAttribute("aria-label",`History snapshot ${snap.ts||"unknown"}`);
    d.innerHTML=`<div class="time">${esc(snap.ts||"--:--:--")}</div>
      <div class="meta">listen ${snap.listeners?snap.listeners.length:0} · exposed ${exposedCount(snap)} · conn ${snap.established?snap.established.length:0}</div>`;
    bindActivate(d,()=>{selectedEpoch=snap.epoch;render();});
    rows.appendChild(d);
  }

  const chosen=items.find(i=>i.epoch===selectedEpoch)||items[0];
  selectedEpoch=chosen.epoch;
  $("summary").innerHTML=`
    <span>time <b>${esc(chosen.ts||"--:--:--")}</b></span>
    <span>listeners <b>${chosen.listeners?chosen.listeners.length:0}</b></span>
    <span>exposed <b>${exposedCount(chosen)}</b></span>
    <span>connections <b>${chosen.established?chosen.established.length:0}</b></span>
  `;

  const procCounts=new Map();
  for(const l of (chosen.listeners||[])){
    const key=l.cmd+"|"+l.pid;
    procCounts.set(key,(procCounts.get(key)||{cmd:l.cmd,pid:l.pid,count:0}));
    procCounts.get(key).count++;
  }
  const top=[...procCounts.values()].sort((a,b)=>b.count-a.count||a.cmd.localeCompare(b.cmd)).slice(0,10);
  $("top").innerHTML=top.length?top.map(p=>`<div>${esc(p.cmd)} <span class="muted">pid ${p.pid} · ${p.count} listen</span></div>`).join(""):'<div class="muted">No listeners in selected snapshot.</div>';

  renderTrend();
}

function renderTrend(){
  const svg=$("trend");
  const W=500,H=120,P=16;
  const pts=items.slice().reverse();
  const vals=pts.map(s=>exposedCount(s));
  const vmax=Math.max(1,...vals);
  let line="";
  vals.forEach((v,i)=>{
    const x=P + (i*(W-2*P))/Math.max(1,vals.length-1);
    const y=H-P - (v*(H-2*P))/vmax;
    line+=(i?" L":"M")+x+" "+y;
  });
  const selIndex=pts.findIndex(s=>s.epoch===selectedEpoch);
  const sx=selIndex<0?null:P + (selIndex*(W-2*P))/Math.max(1,vals.length-1);
  const sy=selIndex<0?null:H-P - (vals[selIndex]*(H-2*P))/vmax;
  svg.innerHTML=`
    <line x1="${P}" y1="${H-P}" x2="${W-P}" y2="${H-P}" stroke="var(--line)" />
    <path d="${line}" fill="none" stroke="var(--amber)" stroke-width="2" />
    ${sx===null?"":`<circle cx="${sx}" cy="${sy}" r="4" fill="var(--rose)" />`}
  `;
}

function esc(s){return String(s).replace(/[&<>"]/g,c=>({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;"}[c]))}
$("refresh").addEventListener("click",()=>loadHistory().catch(showErr));
document.addEventListener("keydown",e=>{if(e.key==="r"&&!(e.metaKey||e.ctrlKey||e.altKey))loadHistory().catch(showErr);});

function showErr(err){
  $("rows").innerHTML='<div class="err">Failed to load history: '+esc(err&&err.message?err.message:"unknown")+'</div>';
}

loadHistory().catch(showErr);
</script>
</body>
</html>
"""
