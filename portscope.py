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
import os
import re
import subprocess
import time

from persistence import SnapshotStore
from server import serve_local_dashboard
from ui import HTML

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
    now = time.time()
    listeners = parse_lsof(run("lsof -nP -iTCP -sTCP:LISTEN"), "LISTEN")
    established = parse_lsof(run("lsof -nP -iTCP -sTCP:ESTABLISHED"), "ESTABLISHED")
    netstat_rows = parse_netstat_listen(run("netstat -anv -p tcp"))

    # Cross-check: listening ports netstat sees that lsof doesn't.
    lsof_ports = {r["port"] for r in listeners}
    discrepancies = sorted(
        {f'{r["addr"]}:{r["port"]}' for r in netstat_rows if r["port"] not in lsof_ports}
    )

    return {
        "ts": time.strftime("%H:%M:%S", time.localtime(now)),
        "epoch": int(now),
        "root": os.geteuid() == 0 if hasattr(os, "geteuid") else True,
        "listeners": listeners,
        "established": established,
        "netstat_count": len(netstat_rows),
        "discrepancies": discrepancies,
    }


# --------------------------------------------------------------------------
# Main
# --------------------------------------------------------------------------


def main():
    ap = argparse.ArgumentParser(description="PortScope — local port & connection map")
    ap.add_argument("--port", type=int, default=8765, help="dashboard port (default 8765)")
    ap.add_argument("--no-browser", action="store_true", help="don't auto-open the browser")
    ap.add_argument(
        "--data-dir",
        default=None,
        help="storage directory for persistent scan history (platform default if omitted)",
    )
    ap.add_argument(
        "--history-limit",
        type=int,
        default=2000,
        help="max persisted snapshots to keep (default 2000)",
    )
    ap.add_argument(
        "--no-persist",
        action="store_true",
        help="disable persistent scan history",
    )
    args = ap.parse_args()

    if hasattr(os, "geteuid") and os.geteuid() != 0:
        print("⚠  Not running as root — processes owned by other users will be invisible.")
        print("   For the full picture run:  sudo python3 portscope.py\n")

    store = None
    if not args.no_persist:
        store = SnapshotStore.from_data_dir(
            data_dir=args.data_dir,
            max_rows=args.history_limit,
        )
        print(f"Persisting scan history at {store.db_path}")

    def snapshot_with_persistence():
        snap = snapshot()
        if store is not None:
            store.save(snap)
        return snap

    def history_reader(limit):
        if store is None:
            return []
        return store.recent(limit)

    serve_local_dashboard(args.port, args.no_browser, snapshot_with_persistence, HTML, history_reader)


if __name__ == "__main__":
    main()
