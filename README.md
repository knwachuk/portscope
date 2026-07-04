# PortScope

A zero-dependency local dashboard that maps every listening TCP port and established connection on your Mac, and visualizes them in a live network diagram where **distance from the center encodes network exposure**.

![status](https://img.shields.io/badge/platform-macOS-lightgrey) ![deps](https://img.shields.io/badge/dependencies-none-brightgreen) ![python](https://img.shields.io/badge/python-3.8%2B-blue)

---

## Quick start

```bash
sudo python3 portscope.py
```

Your browser opens `http://127.0.0.1:8765` automatically. Press `Ctrl-C` in the terminal to stop.

### Options

| Flag | Default | Purpose |
|---|---|---|
| `--port N` | `8765` | Dashboard port |
| `--no-browser` | off | Don't auto-open the browser |

### Why sudo?

`lsof` can only see sockets belonging to processes you own. Without root, listeners owned by `root` (e.g. `remoted`) or service users (e.g. `postgres`) are invisible. PortScope still runs without sudo, but shows a warning banner and a partial view.

---

## What it runs

On every check, PortScope executes three commands and merges the results:

```bash
lsof -nP -iTCP -sTCP:LISTEN        # what's accepting connections
lsof -nP -iTCP -sTCP:ESTABLISHED   # what's actively talking
netstat -anv -p tcp                # independent cross-check of listeners
```

Flag meanings: `-n` skips DNS lookups (raw IPs), `-P` shows numeric ports instead of service names, `-iTCP` restricts to TCP sockets, `-sTCP:<state>` filters by socket state.

**The netstat cross-check matters.** If `netstat` reports a listening port that `lsof` cannot see, PortScope flags the discrepancy in red. The two tools use different kernel interfaces, and a mismatch between them is a classic indicator of a process hiding itself (rootkit behavior). On a healthy machine this list is always empty.

---

## Reading the diagram

```
            NETWORK-REACHABLE ring
          ·  ·  ·  ·  ·  ·  ·  ·
        ·       LOOPBACK ring      ·
      ·       ·  ·  ·  ·  ·         ·          remote
     ·      ·               ·        ·   ~~~~~  hosts
     ·     ·    this Mac     ·       ·   ~~~~~  (established
     ·      ·               ·        ·   ~~~~~   connections)
      ·       ·  ·  ·  ·  ·         ·
        ·                          ·
          ·  ·  ·  ·  ·  ·  ·  ·
```

- **Center** — your machine.
- **Inner ring (steel blue / green)** — processes whose listeners are bound only to `127.0.0.1`, `::1`, or link-local addresses. Nothing outside this Mac (or its network segment, for link-local) can reach them.
- **Outer ring (red / amber)** — processes bound to `*`, `0.0.0.0`, `::`, or a specific LAN IP. **Any device on your network can attempt to connect to these.** This ring should be as empty as you can make it.
- **Amber dots on the right** — remote hosts with established connections, with curved lines back to the local process talking to them. Click a remote host to pin an external-node detail card on the left of the map (ports, protocols, top local processes, and sample flows). Loopback-to-loopback traffic is omitted to keep the picture clean.
- **Node size** — scales with how many ports the process holds.
- **Faded nodes** — client-only processes (outbound connections, no listeners).

Hover any node for its full address:port list; click it (or its row in the side panel) for a detailed socket table.

### Exposure scopes

| Tag | Bound to | Reachable from |
|---|---|---|
| `loopback` | `127.0.0.1`, `::1` | This Mac only |
| `linklocal` | `fe80::...` | Same physical network segment (no routing) |
| `lan` | A specific routable IP | Your network |
| `exposed` | `*`, `0.0.0.0`, `::` | Every interface — Wi-Fi, Ethernet, VPN, all of it |

---

## Controls

- **check every** — polling interval: manually, 5 s, 15 s, 30 s, 60 s, or 5 min. Each check re-runs the commands fresh; nothing is cached or written to disk.
- **Refresh now** — immediate one-off check, regardless of interval.
- **External nodes** — click an amber remote host dot to pin details in the left map card; click again to clear.
- Header counters show total listeners, network-reachable processes, and established connections at a glance.

### Keyboard controls

- `Tab` / `Shift+Tab` moves focus through process rows, process nodes, and remote host nodes.
- `Enter` or `Space` activates the focused item (same as clicking).
- `Escape` clears a pinned external-node card.

---

## Interpreting common findings on macOS

These show up on nearly every Mac and are normal:

| Process | Typical binding | What it is |
|---|---|---|
| `remoted` | link-local IPv6, ports 49xxx | Apple device-management daemon |
| `rapportd` | `*:high port` | Handoff / Continuity between your Apple devices |
| `ControlCe` (ControlCenter) | `*:5000`, `*:7000` | AirPlay Receiver — disable in System Settings → General → AirDrop & Handoff if unused |
| `Code H` (Code Helper) | `127.0.0.1` | VS Code internals — loopback only, fine |
| `sharingd`, `identityservicesd` | varies | iCloud / sharing services |

Worth a second look when they appear on the **outer ring**:

- **Databases** (`postgres`, `mongod`, `mysqld`, `redis-server`) bound to `*` — for local development, bind them to localhost. For PostgreSQL: set `listen_addresses = 'localhost'` in `postgresql.conf` and restart. Verify the fix by refreshing PortScope: the node should drop to the inner ring.
- **Anything you don't recognize** — note the PID, then `ps -p <PID> -o command=` to see the full launch command and path.

---

## Security & privacy notes

- The dashboard server binds to `127.0.0.1` only — PortScope never adds itself to your exposed surface.
- No data leaves your machine. No logging, no telemetry, no disk writes.
- Stdlib only — easy to audit and run anywhere Python 3.8+ is available.

---

## Troubleshooting

**"Not running as root" banner** — re-run with `sudo`. The view works either way, but is incomplete without it.

**Port 8765 already in use** — `sudo python3 portscope.py --port 9000`.

**"Lost contact with portscope.py"** in the header — the Python process stopped (terminal closed, Ctrl-C). Restart it and refresh the page.

**Diagram is crowded** — developer machines with many VS Code helpers get busy inner rings. The side panel list is sorted most-exposed-first, so the things that matter are always at the top.

**Linux?** — The parsers target macOS `lsof`/`netstat` output. `lsof` parsing mostly carries over, but the `netstat -anv -p tcp` cross-check is macOS-specific and will simply report zero on Linux.

---

## Ideas for next steps

- Diff between checks: highlight listeners that appeared or vanished since the last poll
- History timeline of exposure count over a session
- Reverse-DNS / GeoIP labels on remote hosts (opt-in, since it generates lookups)
- `launchd` plist to run at login

## License

Do whatever you want with it. (Public domain / Unlicense.)
