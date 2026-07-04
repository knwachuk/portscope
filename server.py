"""HTTP server utilities for PortScope."""

import json
import threading
import webbrowser
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, urlparse


def _build_handler(html, snapshot_func, history_func=None):
    class Handler(BaseHTTPRequestHandler):
        def do_GET(self):
            parsed = urlparse(self.path)
            if parsed.path == "/":
                body = html.encode()
                self.send_response(200)
                self.send_header("Content-Type", "text/html; charset=utf-8")
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)
            elif parsed.path == "/api/snapshot":
                body = json.dumps(snapshot_func()).encode()
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)
            elif parsed.path == "/api/history":
                query = parse_qs(parsed.query)
                try:
                    limit = int(query.get("limit", ["50"])[0])
                except ValueError:
                    limit = 50
                if history_func is None:
                    items = []
                else:
                    items = history_func(limit)
                body = json.dumps({"items": items}).encode()
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)
            else:
                self.send_error(404)

        def log_message(self, *a):
            pass  # keep the terminal quiet

    return Handler


def serve_local_dashboard(port, no_browser, snapshot_func, html, history_func=None):
    """Start and run the local dashboard server."""
    addr = ("127.0.0.1", port)
    handler = _build_handler(html, snapshot_func, history_func)
    srv = ThreadingHTTPServer(addr, handler)
    url = f"http://127.0.0.1:{port}"
    print(f"PortScope running at {url}  (Ctrl-C to stop)")
    if not no_browser:
        threading.Timer(0.6, lambda: webbrowser.open(url)).start()
    try:
        srv.serve_forever()
    except KeyboardInterrupt:
        print("\nStopped.")
