"""Embedded UI for PortScope."""

HTML = r"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>PortScope</title>
<style>
  :root{
    --bg:#0F1117; --panel:#171B25; --line:#262C3B;
    --text:#D8DEE9; --muted:#5C6678;
    --amber:#FFB454; --steel:#7FB4D9; --rose:#FF6B7A; --green:#9ECE8C;
    --mono:ui-monospace,'SF Mono',SFMono-Regular,Menlo,Consolas,monospace;
  }
  *{box-sizing:border-box;margin:0;padding:0}
  body{background:var(--bg);color:var(--text);font-family:var(--mono);font-size:13px;min-height:100vh}
  header{display:flex;align-items:center;gap:18px;padding:14px 20px;border-bottom:1px solid var(--line);flex-wrap:wrap}
  .mark{letter-spacing:.35em;font-weight:700;font-size:14px}
  .mark b{color:var(--amber)}
  .pulse{width:8px;height:8px;border-radius:50%;background:var(--green);display:inline-block;margin-right:6px}
  .pulse.stale{background:var(--muted)}
  @media (prefers-reduced-motion:no-preference){ .pulse.live{animation:blink 2s infinite} }
  @keyframes blink{50%{opacity:.25}}
  header .stat{color:var(--muted)} header .stat b{color:var(--text);font-weight:600}
  header .stat b.warn{color:var(--rose)}
  .controls{margin-left:auto;display:flex;align-items:center;gap:10px}
  select,button{background:var(--panel);color:var(--text);border:1px solid var(--line);
    border-radius:6px;padding:6px 10px;font-family:var(--mono);font-size:12px;cursor:pointer}
  select:focus-visible,button:focus-visible{outline:2px solid var(--amber);outline-offset:1px}
  button:hover{border-color:var(--amber)}
  main{display:grid;grid-template-columns:minmax(0,1fr) 380px;gap:0;height:calc(100vh - 58px)}
  @media(max-width:980px){ main{grid-template-columns:1fr;height:auto} #side{max-height:50vh} }
  #map{position:relative;overflow:hidden}
  #map svg{width:100%;height:100%;display:block}
  #side{border-left:1px solid var(--line);overflow-y:auto;background:var(--panel)}
  .sideheader{padding:12px 16px;border-bottom:1px solid var(--line);color:var(--muted);
    letter-spacing:.15em;font-size:11px;text-transform:uppercase}
  .row{padding:10px 16px;border-bottom:1px solid var(--line);cursor:pointer}
  .row:hover,.row.sel{background:#1D2330}
  .row:focus-visible{outline:2px solid var(--amber);outline-offset:-2px;background:#1D2330}
  .row .cmd{font-weight:600}
  .row .meta{color:var(--muted);font-size:12px;margin-top:2px}
  .tag{display:inline-block;border-radius:4px;padding:1px 6px;font-size:11px;margin-left:6px}
  .tag.exposed{background:rgba(255,107,122,.15);color:var(--rose)}
  .tag.lan{background:rgba(255,180,84,.15);color:var(--amber)}
  .tag.loopback{background:rgba(127,180,217,.13);color:var(--steel)}
  .tag.linklocal{background:rgba(156,206,140,.13);color:var(--green)}
  #detail{padding:14px 16px;border-bottom:1px solid var(--line);display:none;background:#131722}
  #detail h3{font-size:13px;margin-bottom:8px}
  #detail table{width:100%;border-collapse:collapse;font-size:12px}
  #detail td{padding:3px 6px 3px 0;color:var(--muted);vertical-align:top}
  #detail td:first-child{color:var(--text);white-space:nowrap}
  .remote-detail{position:absolute;left:16px;top:14px;max-width:360px;max-height:52%;overflow:auto;
    color:var(--text);font-size:12px;line-height:1.45;background:rgba(15,17,23,.92);
    border:1px solid var(--line);border-radius:8px;padding:10px 12px;display:none;z-index:4}
  .remote-detail h4{font-size:12px;letter-spacing:.08em;margin-bottom:6px;text-transform:uppercase;color:var(--muted)}
  .remote-detail .host{font-size:13px;font-weight:600;color:var(--amber)}
  .remote-detail .meta{color:var(--muted);margin-top:2px}
  .remote-detail .section{margin-top:8px;color:var(--muted);letter-spacing:.08em;text-transform:uppercase;font-size:10px}
  .remote-detail ul{margin-top:6px;padding-left:16px}
  .remote-detail li{margin:2px 0}
  .legend{position:absolute;left:16px;bottom:14px;color:var(--muted);font-size:11px;line-height:1.8;
    background:rgba(15,17,23,.8);padding:8px 12px;border:1px solid var(--line);border-radius:8px}
  .legend i{display:inline-block;width:9px;height:9px;border-radius:50%;margin-right:7px}
  .err{padding:12px 16px;color:var(--rose)}
  #tip{position:absolute;pointer-events:none;background:#1D2330;border:1px solid var(--line);
    border-radius:6px;padding:7px 10px;font-size:12px;display:none;max-width:280px;z-index:5}
  #tip .t{color:var(--muted)}
  .focus-node:focus-visible{stroke:var(--text)!important;stroke-width:2.5!important;
    filter:drop-shadow(0 0 3px rgba(255,180,84,.7))}
</style>
</head>
<body>
<header>
  <span class="mark">PORT<b>SCOPE</b></span>
  <span class="stat"><span id="pulse" class="pulse live"></span><span id="ts">—</span></span>
  <span class="stat">listeners <b id="nL">0</b></span>
  <span class="stat">exposed <b id="nE" class="warn">0</b></span>
  <span class="stat">connections <b id="nC">0</b></span>
  <div class="controls">
    <label for="ivl" style="color:var(--muted)">check every</label>
    <select id="ivl" aria-label="Refresh interval">
      <option value="0">manually</option>
      <option value="5000">5 s</option>
      <option value="15000" selected>15 s</option>
      <option value="30000">30 s</option>
      <option value="60000">60 s</option>
      <option value="300000">5 min</option>
    </select>
    <button id="refresh">Refresh now</button>
    <button id="openHistory">History</button>
  </div>
</header>
<main>
  <div id="map">
    <svg id="svg" role="img" aria-label="Network diagram of listening ports and connections"></svg>
    <div id="remoteDetail" class="remote-detail"></div>
    <div class="legend">
      <i style="background:var(--steel)"></i>loopback only (this Mac)<br>
      <i style="background:var(--green)"></i>link-local (same network segment)<br>
      <i style="background:var(--rose)"></i>all interfaces (network-reachable)<br>
      <i style="background:var(--amber)"></i>remote host (established, click for details)
    </div>
    <div id="tip"></div>
  </div>
  <div id="side">
    <div id="detail"></div>
    <div class="sideheader">Processes</div>
    <div id="rows"></div>
    <div id="notice"></div>
  </div>
</main>
<script>
"use strict";
let timer=null, data=null, selected=null, selectedRemote=null;
const $=id=>document.getElementById(id);
const SC={loopback:"var(--steel)",linklocal:"var(--green)",lan:"var(--amber)",exposed:"var(--rose)"};
const RANK={loopback:0,linklocal:1,lan:2,exposed:3};

async function fetchSnap(){
  $("pulse").classList.remove("stale");
  try{
    const r=await fetch("/api/snapshot");
    if(!r.ok)throw new Error("snapshot status "+r.status);
    data=await r.json();
    render();
  }catch(e){
    $("pulse").classList.add("stale");
    $("notice").innerHTML='<div class="err">Lost contact with portscope.py — is it still running? '+esc(e.message||"")+'</div>';
  }
}

function schedule(){
  if(timer)clearInterval(timer); timer=null;
  const ms=+$("ivl").value;
  if(ms>0)timer=setInterval(fetchSnap,ms);
}
$("ivl").addEventListener("change",schedule);
$("refresh").addEventListener("click",fetchSnap);
$("openHistory").addEventListener("click",()=>{window.location.href="/history";});

function bindActivate(node, action){
  node.addEventListener("click", action);
  node.addEventListener("keydown", e=>{
    if(e.key === "Enter" || e.key === " "){
      e.preventDefault();
      action();
    }
  });
}

function groupProcesses(){
  // one node per (cmd,pid); collect its listeners + established connections
  const m=new Map();
  for(const l of data.listeners){
    const k=l.cmd+"|"+l.pid;
    if(!m.has(k))m.set(k,{cmd:l.cmd,pid:l.pid,user:l.user,listen:[],conns:[],scope:"loopback"});
    const p=m.get(k); p.listen.push(l);
    if(RANK[l.scope]>RANK[p.scope])p.scope=l.scope;
  }
  for(const c of data.established){
    const k=c.cmd+"|"+c.pid;
    if(!m.has(k))m.set(k,{cmd:c.cmd,pid:c.pid,user:c.user,listen:[],conns:[],scope:"loopback",clientOnly:true});
    m.get(k).conns.push(c);
  }
  return [...m.values()].sort((a,b)=>RANK[b.scope]-RANK[a.scope]||a.cmd.localeCompare(b.cmd));
}
function remoteHosts(){
  const m=new Map();
  for(const c of data.established){
    if(c.raddr.startsWith("127.")||c.raddr==="::1")continue; // local loop traffic stays in rings
    if(!m.has(c.raddr))m.set(c.raddr,{
      addr:c.raddr,conns:[],
      procs:new Map(),localPorts:new Set(),remotePorts:new Set(),protos:new Set()
    });
    const host=m.get(c.raddr);
    host.conns.push(c);
    host.localPorts.add(c.lport);
    host.remotePorts.add(c.rport);
    host.protos.add(c.proto);
    const pk=c.cmd+"|"+c.pid;
    if(!host.procs.has(pk))host.procs.set(pk,{cmd:c.cmd,pid:c.pid,count:0});
    host.procs.get(pk).count++;
  }
  return [...m.values()].map(h=>({
    addr:h.addr,
    conns:h.conns,
    processes:[...h.procs.values()].sort((a,b)=>b.count-a.count),
    localPorts:[...h.localPorts].sort((a,b)=>(+a||0)-(+b||0)),
    remotePorts:[...h.remotePorts].sort((a,b)=>(+a||0)-(+b||0)),
    protos:[...h.protos].sort(),
  })).sort((a,b)=>b.conns.length-a.conns.length||a.addr.localeCompare(b.addr));
}

function remoteReachability(addr){
  if(addr.startsWith("10.")||addr.startsWith("192.168."))return "private LAN";
  if(/^172\.(1[6-9]|2\d|3[0-1])\./.test(addr))return "private LAN";
  if(addr.toLowerCase().startsWith("fe80:"))return "link-local IPv6";
  if(addr.toLowerCase().startsWith("fc")||addr.toLowerCase().startsWith("fd"))return "private ULA IPv6";
  return "public or routed";
}

function render(){
  $("ts").textContent="checked "+data.ts;
  const procs=groupProcesses(), remotes=remoteHosts();
  if(selectedRemote&&!remotes.some(r=>r.addr===selectedRemote))selectedRemote=null;
  const exposed=procs.filter(p=>p.scope==="exposed"||p.scope==="lan");
  $("nL").textContent=data.listeners.length;
  $("nE").textContent=exposed.length;
  $("nE").className=exposed.length?"warn":"";
  $("nC").textContent=data.established.length;

  // ---- side list ----
  const rows=$("rows"); rows.innerHTML="";
  for(const p of procs){
    const d=document.createElement("div");
    d.className="row"+(selected===p.cmd+"|"+p.pid?" sel":"");
    d.setAttribute("role","button");
    d.setAttribute("tabindex","0");
    d.setAttribute("aria-label",`Process ${p.cmd} pid ${p.pid}`);
    const ports=p.listen.map(l=>l.port).filter((v,i,a)=>a.indexOf(v)===i).slice(0,6).join(", ");
    d.innerHTML=`<span class="cmd">${esc(p.cmd)}</span><span class="tag ${p.scope}">${p.clientOnly?"client":p.scope}</span>
      <div class="meta">pid ${p.pid} · ${esc(p.user)} · ${p.listen.length?("listening "+ports):""} ${p.conns.length?(" · "+p.conns.length+" conn"):""}</div>`;
    bindActivate(d,()=>{selected=p.cmd+"|"+p.pid;showDetail(p);render();});
    rows.appendChild(d);
  }
  let notice="";
  if(!data.root)notice+='<div class="err">Not running as root — some processes are hidden. Re-run with sudo.</div>';
  if(data.discrepancies.length)
    notice+='<div class="err">netstat sees listeners lsof missed: '+data.discrepancies.map(esc).join(", ")+'</div>';
  $("notice").innerHTML=notice;

  renderRemoteDetail(remotes);
  drawMap(procs,remotes);
}

function renderRemoteDetail(remotes){
  const box=$("remoteDetail");
  if(!selectedRemote){
    box.style.display="none";
    box.innerHTML="";
    return;
  }
  const host=remotes.find(r=>r.addr===selectedRemote);
  if(!host){
    box.style.display="none";
    box.innerHTML="";
    return;
  }
  const topProc=host.processes.slice(0,6).map(p=>
    `<li>${esc(p.cmd)} <span style="color:var(--muted)">pid ${p.pid} · ${p.count} conn</span></li>`
  ).join("");
  const samples=host.conns.slice(0,8).map(c=>
    `<li>${esc(c.cmd)} <span style="color:var(--muted)">${esc(c.laddr)}:${c.lport} → ${esc(c.raddr)}:${c.rport}</span></li>`
  ).join("");
  box.innerHTML=`
    <h4>External Node</h4>
    <div class="host">${esc(host.addr)}</div>
    <div class="meta">${host.conns.length} active connection(s) · ${esc(remoteReachability(host.addr))}</div>
    <div class="section">Protocols</div>
    <div>${host.protos.map(esc).join(", ")||"unknown"}</div>
    <div class="section">Remote Ports</div>
    <div>${host.remotePorts.map(esc).join(", ")||"none"}</div>
    <div class="section">Local Ports Used</div>
    <div>${host.localPorts.map(esc).join(", ")||"none"}</div>
    <div class="section">Top Local Processes</div>
    <ul>${topProc||"<li>none</li>"}</ul>
    <div class="section">Sample Flows</div>
    <ul>${samples||"<li>none</li>"}</ul>
  `;
  box.style.display="block";
}

function showDetail(p){
  const det=$("detail"); det.style.display="block";
  let t=`<h3>${esc(p.cmd)} <span style="color:var(--muted)">pid ${p.pid}</span></h3><table>`;
  for(const l of p.listen)
    t+=`<tr><td>${esc(l.addr)}:${l.port}</td><td>LISTEN · ${l.proto} <span class="tag ${l.scope}">${l.scope}</span></td></tr>`;
  for(const c of p.conns)
    t+=`<tr><td>${esc(c.laddr)}:${c.lport}</td><td>→ ${esc(c.raddr)}:${c.rport}</td></tr>`;
  det.innerHTML=t+"</table>";
}

function drawMap(procs,remotes){
  const svg=$("svg"), box=$("map").getBoundingClientRect();
  const W=Math.max(box.width,420), H=Math.max(box.height,420);
  const cx=W*0.42, cy=H/2, R1=Math.min(W,H)*0.21, R2=Math.min(W,H)*0.36;
  svg.setAttribute("viewBox",`0 0 ${W} ${H}`); svg.innerHTML="";
  const NS="http://www.w3.org/2000/svg";
  const el=(n,a)=>{const e=document.createElementNS(NS,n);for(const k in a)e.setAttribute(k,a[k]);svg.appendChild(e);return e};

  // rings
  for(const[r,label]of[[R1,"loopback"],[R2,"network-reachable"]]){
    el("circle",{cx,cy,r,fill:"none",stroke:"var(--line)","stroke-dasharray":"3 5"});
    el("text",{x:cx,y:cy-r-7,fill:"var(--muted)","font-size":"10px","text-anchor":"middle",
      "letter-spacing":"2"}).textContent=label.toUpperCase();
  }
  // core
  el("circle",{cx,cy,r:26,fill:"#1D2330",stroke:"var(--line)"});
  el("text",{x:cx,y:cy+4,fill:"var(--text)","font-size":"11px","text-anchor":"middle"}).textContent="this Mac";

  // position process nodes: inner ring = loopback/link-local, outer = lan/exposed
  const inner=procs.filter(p=>RANK[p.scope]<2), outer=procs.filter(p=>RANK[p.scope]>=2);
  const pos=new Map();
  placeRing(inner,R1); placeRing(outer,R2);
  function placeRing(list,r){
    list.forEach((p,i)=>{
      const a=-Math.PI/2+(2*Math.PI*i)/Math.max(list.length,1);
      pos.set(p.cmd+"|"+p.pid,{x:cx+r*Math.cos(a),y:cy+r*Math.sin(a),p});
    });
  }
  // remote hosts column on the right
  const rs=remotes.slice(0,18);
  rs.forEach((h,i)=>{
    h.x=W*0.88; h.y=H*0.12+(H*0.76)*(rs.length>1?i/(rs.length-1):0.5);
  });

  // connection lines: process -> remote host
  for(const h of rs)for(const c of h.conns){
    const from=pos.get(c.cmd+"|"+c.pid); if(!from)continue;
    el("path",{d:`M${from.x},${from.y} C${(from.x+h.x)/2},${from.y} ${(from.x+h.x)/2},${h.y} ${h.x},${h.y}`,
      fill:"none",stroke:"var(--amber)","stroke-opacity":".35","stroke-width":"1"});
  }
  // spokes core -> listeners
  for(const{x,y,p}of pos.values())
    el("line",{x1:cx,y1:cy,x2:x,y2:y,stroke:SC[p.scope],"stroke-opacity":p.clientOnly?".12":".3","stroke-width":"1"});

  // remote nodes
  for(const h of rs){
    const isSel=selectedRemote===h.addr;
    const g=el("circle",{cx:h.x,cy:h.y,r:isSel?6.5:5,fill:"var(--amber)","fill-opacity":".9",
      stroke:isSel?"var(--text)":"none","stroke-width":isSel?"2":"0",tabindex:0,
      role:"button",class:"focus-node","aria-label":`Remote host ${h.addr}`,style:"cursor:pointer"});
    bindActivate(g,()=>{selectedRemote=(selectedRemote===h.addr?null:h.addr);render();});
    hover(g,()=>`<b>${esc(h.addr)}</b><div class="t">${h.conns.length} connection(s): ${
      h.conns.slice(0,5).map(c=>esc(c.cmd)+":"+c.rport).join(", ")}<br>click to pin details</div>`);
    el("text",{x:h.x+10,y:h.y+4,fill:"var(--muted)","font-size":"10px"}).textContent=h.addr;
  }
  // process nodes
  for(const{x,y,p}of pos.values()){
    const r=6+Math.min(p.listen.length,8);
    const c=el("circle",{cx:x,cy:y,r,fill:SC[p.scope],"fill-opacity":p.clientOnly?".35":".9",
      stroke:"var(--bg)","stroke-width":"2",tabindex:0,role:"button",
      class:"focus-node","aria-label":`Process ${p.cmd} pid ${p.pid}`,style:"cursor:pointer"});
    bindActivate(c,()=>{selected=p.cmd+"|"+p.pid;showDetail(p);render();});
    hover(c,()=>`<b>${esc(p.cmd)}</b> pid ${p.pid}<div class="t">${
      p.listen.map(l=>esc(l.addr)+":"+l.port).join("<br>")||"client connections only"}</div>`);
    const label=p.cmd.length>14?p.cmd.slice(0,13)+"…":p.cmd;
    el("text",{x,y:y-r-6,fill:"var(--text)","font-size":"10px","text-anchor":"middle"}).textContent=label;
  }
}
function hover(node,html){
  const tip=$("tip");
  node.addEventListener("mousemove",e=>{
    tip.style.display="block"; tip.innerHTML=html();
    const b=$("map").getBoundingClientRect();
    tip.style.left=Math.min(e.clientX-b.left+14,b.width-290)+"px";
    tip.style.top=(e.clientY-b.top+10)+"px";
  });
  node.addEventListener("mouseleave",()=>tip.style.display="none");
}
function esc(s){return String(s).replace(/[&<>"]/g,c=>({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;"}[c]))}
document.addEventListener("keydown",e=>{
  if(e.key === "Escape" && selectedRemote){
    selectedRemote=null;
    render();
  }
});
window.addEventListener("resize",()=>data&&render());
fetchSnap(); schedule();
</script>
</body>
</html>
"""
