"""HTTP server utilities for PortScope."""

import json
import threading
import webbrowser
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer


def _build_handler(html, snapshot_func):
    class Handler(BaseHTTPRequestHandler):
        def do_GET(self):
            if self.path == "/":
                body = html.encode()
                self.send_response(200)
                self.send_header("Content-Type", "text/html; charset=utf-8")
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)
            elif self.path == "/api/snapshot":
                body = json.dumps(snapshot_func()).encode()
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


def serve_local_dashboard(port, no_browser, snapshot_func, html):
    """Start and run the local dashboard server."""
    addr = ("127.0.0.1", port)
    handler = _build_handler(html, snapshot_func)
    srv = ThreadingHTTPServer(addr, handler)
    url = f"http://127.0.0.1:{port}"
    print(f"PortScope running at {url}  (Ctrl-C to stop)")
    if not no_browser:
        threading.Timer(0.6, lambda: webbrowser.open(url)).start()
    try:
        srv.serve_forever()
    except KeyboardInterrupt:
        print("\nStopped.")
