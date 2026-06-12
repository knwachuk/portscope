#!/usr/bin/env python3
"""
PortScope — live map of listening ports and established TCP connections on macOS.

Runs:
  sudo lsof -nP -iTCP -sTCP:LISTEN
  sudo lsof -nP -iTCP -sTCP:ESTABLISHED
  netstat -anv -p tcp | grep LISTEN     (cross-check)

Serves a local dashboard at http://127.0.0.1:8765 with a radial network
diagram. Ring position encodes exposure: inner ring = loopback-only,
outer ring = listening on all interfaces / LAN-reachable.

Usage:
  sudo python3 portscope.py [--port 8765]

No dependencies. Binds to 127.0.0.1 only.
"""

import argparse
import json
import os
import re
import subprocess
import sys
import threading
import time
import webbrowser
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

# --------------------------------------------------------------------------
# Data collection
# --------------------------------------------------------------------------

def run(cmd):
    try:
        out = subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=20)
        return out.stdout
    except Exception as e:
        return ""


def split_addr_port(s):
    """'127.0.0.1:5432' / '[::1]:42050' / '*:7000' -> (addr, port)."""
    if s.startswith("["):
        m = re.match(r"^\[(.*)\]:(\d+|\*)$", s)
        if m:
            return m.group(1), m.group(2)
    i = s.rfind(":")
    if i == -1:
        return s, ""
    return s[:i], s[i + 1:]


def classify(addr):
    """Exposure scope of a bound address."""
    if addr in ("*", "0.0.0.0", "::"):
        return "exposed"          # all interfaces — reachable from the network
    if addr.startswith("127.") or addr in ("::1",):
        return "loopback"         # this machine only
    if addr.lower().startswith("fe80"):
        return "linklocal"        # link-local IPv6 (same physical segment)
    return "lan"                  # bound to a specific routable IP


def parse_lsof(text, want_state):
    """Parse `lsof -nP -iTCP -sTCP:<state>` output."""
    rows = []
    for line in text.splitlines():
        if not line or line.startswith("COMMAND"):
            continue
        parts = line.split()
        if len(parts) < 9:
            continue
        cmd, pid, user = parts[0], parts[1], parts[2]
        proto = parts[4]  # IPv4 / IPv6
        name = parts[8]
        state = parts[9].strip("()") if len(parts) > 9 else ""
        cmd = cmd.replace("\\x20", " ")
        if want_state == "LISTEN":
            addr, port = split_addr_port(name)
            rows.append({
                "cmd": cmd, "pid": pid, "user": user, "proto": proto,
                "addr": addr, "port": port, "scope": classify(addr),
            })
        else:  # ESTABLISHED: local->remote
            if "->" not in name:
                continue
            local, remote = name.split("->", 1)
            laddr, lport = split_addr_port(local)
            raddr, rport = split_addr_port(remote)
            rows.append({
                "cmd": cmd, "pid": pid, "user": user, "proto": proto,
                "laddr": laddr, "lport": lport,
                "raddr": raddr, "rport": rport,
            })
    return rows


def parse_netstat_listen(text):
    """Parse `netstat -anv -p tcp` LISTEN lines (macOS format) for cross-check.
    Local address looks like 127.0.0.1.50377 or *.5432; pid follows the state."""
    rows = []
    for line in text.splitlines():
        if "LISTEN" not in line:
            continue
        parts = line.split()
        if len(parts) < 4 or not parts[0].startswith("tcp"):
            continue
        local = parts[3]
        i = local.rfind(".")
        if i == -1:
            continue
        addr, port = local[:i], local[i + 1:]
        if addr == "*":
            pass
        pid = ""
        # macOS netstat -anv: ... (state) rhiwat shiwat pid epid ...
        try:
            si = parts.index("LISTEN")
            if len(parts) > si + 3 and parts[si + 3].isdigit():
                pid = parts[si + 3]
        except ValueError:
            pass
        rows.append({"addr": addr, "port": port, "pid": pid, "scope": classify(addr)})
    return rows


def snapshot():
    listeners = parse_lsof(run("lsof -nP -iTCP -sTCP:LISTEN"), "LISTEN")
    established = parse_lsof(run("lsof -nP -iTCP -sTCP:ESTABLISHED"), "ESTABLISHED")
    netstat_rows = parse_netstat_listen(run("netstat -anv -p tcp"))

    # Cross-check: listening ports netstat sees that lsof doesn't.
    lsof_ports = {r["port"] for r in listeners}
    discrepancies = sorted(
        {f'{r["addr"]}:{r["port"]}' for r in netstat_rows if r["port"] not in lsof_ports}
    )

    return {
        "ts": time.strftime("%H:%M:%S"),
        "root": os.geteuid() == 0 if hasattr(os, "geteuid") else True,
        "listeners": listeners,
        "established": established,
        "netstat_count": len(netstat_rows),
        "discrepancies": discrepancies,
    }


# --------------------------------------------------------------------------
# Embedded UI
# --------------------------------------------------------------------------

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
  .legend{position:absolute;left:16px;bottom:14px;color:var(--muted);font-size:11px;line-height:1.8;
    background:rgba(15,17,23,.8);padding:8px 12px;border:1px solid var(--line);border-radius:8px}
  .legend i{display:inline-block;width:9px;height:9px;border-radius:50%;margin-right:7px}
  .err{padding:12px 16px;color:var(--rose)}
  #tip{position:absolute;pointer-events:none;background:#1D2330;border:1px solid var(--line);
    border-radius:6px;padding:7px 10px;font-size:12px;display:none;max-width:280px;z-index:5}
  #tip .t{color:var(--muted)}
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
  </div>
</header>
<main>
  <div id="map">
    <svg id="svg" role="img" aria-label="Network diagram of listening ports and connections"></svg>
    <div class="legend">
      <i style="background:var(--steel)"></i>loopback only (this Mac)<br>
      <i style="background:var(--green)"></i>link-local (same network segment)<br>
      <i style="background:var(--rose)"></i>all interfaces (network-reachable)<br>
      <i style="background:var(--amber)"></i>remote host (established)
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
let timer=null, data=null, selected=null;
const $=id=>document.getElementById(id);
const SC={loopback:"var(--steel)",linklocal:"var(--green)",lan:"var(--amber)",exposed:"var(--rose)"};
const RANK={loopback:0,linklocal:1,lan:2,exposed:3};

async function fetchSnap(){
  $("pulse").classList.remove("stale");
  try{
    const r=await fetch("/api/snapshot"); data=await r.json();
    render();
  }catch(e){
    $("pulse").classList.add("stale");
    $("notice").innerHTML='<div class="err">Lost contact with portscope.py — is it still running?</div>';
  }
}
function schedule(){
  if(timer)clearInterval(timer); timer=null;
  const ms=+$("ivl").value;
  if(ms>0)timer=setInterval(fetchSnap,ms);
}
$("ivl").addEventListener("change",schedule);
$("refresh").addEventListener("click",fetchSnap);

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
    if(!m.has(c.raddr))m.set(c.raddr,{addr:c.raddr,conns:[]});
    m.get(c.raddr).conns.push(c);
  }
  return [...m.values()];
}

function render(){
  $("ts").textContent="checked "+data.ts;
  const procs=groupProcesses(), remotes=remoteHosts();
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
    const ports=p.listen.map(l=>l.port).filter((v,i,a)=>a.indexOf(v)===i).slice(0,6).join(", ");
    d.innerHTML=`<span class="cmd">${esc(p.cmd)}</span><span class="tag ${p.scope}">${p.clientOnly?"client":p.scope}</span>
      <div class="meta">pid ${p.pid} · ${esc(p.user)} · ${p.listen.length?("listening "+ports):""} ${p.conns.length?(" · "+p.conns.length+" conn"):""}</div>`;
    d.addEventListener("click",()=>{selected=p.cmd+"|"+p.pid;showDetail(p);render();});
    rows.appendChild(d);
  }
  let notice="";
  if(!data.root)notice+='<div class="err">Not running as root — some processes are hidden. Re-run with sudo.</div>';
  if(data.discrepancies.length)
    notice+='<div class="err">netstat sees listeners lsof missed: '+data.discrepancies.map(esc).join(", ")+'</div>';
  $("notice").innerHTML=notice;

  drawMap(procs,remotes);
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
    const g=el("circle",{cx:h.x,cy:h.y,r:5,fill:"var(--amber)","fill-opacity":".9",tabindex:0});
    hover(g,()=>`<b>${esc(h.addr)}</b><div class="t">${h.conns.length} connection(s): ${
      h.conns.slice(0,5).map(c=>esc(c.cmd)+":"+c.rport).join(", ")}</div>`);
    el("text",{x:h.x+10,y:h.y+4,fill:"var(--muted)","font-size":"10px"}).textContent=h.addr;
  }
  // process nodes
  for(const{x,y,p}of pos.values()){
    const r=6+Math.min(p.listen.length,8);
    const c=el("circle",{cx:x,cy:y,r,fill:SC[p.scope],"fill-opacity":p.clientOnly?".35":".9",
      stroke:"var(--bg)","stroke-width":"2",tabindex:0,style:"cursor:pointer"});
    c.addEventListener("click",()=>{selected=p.cmd+"|"+p.pid;showDetail(p);render();});
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
window.addEventListener("resize",()=>data&&render());
fetchSnap(); schedule();
</script>
</body>
</html>
"""

# --------------------------------------------------------------------------
# Server
# --------------------------------------------------------------------------

class Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        if self.path == "/":
            body = HTML.encode()
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
        elif self.path == "/api/snapshot":
            body = json.dumps(snapshot()).encode()
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
        else:
            self.send_error(404)

    def log_message(self, *a):
        pass  # keep the terminal quiet


def main():
    ap = argparse.ArgumentParser(description="PortScope — local port & connection map")
    ap.add_argument("--port", type=int, default=8765, help="dashboard port (default 8765)")
    ap.add_argument("--no-browser", action="store_true", help="don't auto-open the browser")
    args = ap.parse_args()

    if hasattr(os, "geteuid") and os.geteuid() != 0:
        print("⚠  Not running as root — processes owned by other users will be invisible.")
        print("   For the full picture run:  sudo python3 portscope.py\n")

    addr = ("127.0.0.1", args.port)
    srv = ThreadingHTTPServer(addr, Handler)
    url = f"http://127.0.0.1:{args.port}"
    print(f"PortScope running at {url}  (Ctrl-C to stop)")
    if not args.no_browser:
        threading.Timer(0.6, lambda: webbrowser.open(url)).start()
    try:
        srv.serve_forever()
    except KeyboardInterrupt:
        print("\nStopped.")


if __name__ == "__main__":
    main()
