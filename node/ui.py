"""Minimal status UI: RESTORE PRIVACY + connected client count only."""

from __future__ import annotations

import json
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Callable


def make_handler(get_status: Callable[[], dict]):
    class Handler(BaseHTTPRequestHandler):
        def log_message(self, format, *args):  # noqa: A003
            # No access logs of any means
            return

        def do_GET(self):  # noqa: N802
            if self.path in ("/", "/index.html"):
                status = get_status()
                title = status.get("title", "RESTORE PRIVACY")
                n = int(status.get("clients_connected", 0))
                body = f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="utf-8"/>
  <meta http-equiv="refresh" content="3"/>
  <title>{title}</title>
  <style>
    body {{ margin:0; min-height:100vh; display:flex; flex-direction:column;
           align-items:center; justify-content:center; background:#0b0f14; color:#e8eef5;
           font-family: system-ui, sans-serif; }}
    h1 {{ letter-spacing:0.12em; font-weight:600; font-size:2.2rem; margin:0 0 1.5rem; }}
    .count {{ font-size:1.25rem; opacity:0.9; }}
    .num {{ font-size:3rem; font-weight:700; margin-top:0.4rem; color:#6ee7b7; }}
  </style>
</head>
<body>
  <h1>{title}</h1>
  <div class="count">Clients connected</div>
  <div class="num" id="n">{n}</div>
</body>
</html>
"""
                data = body.encode("utf-8")
                self.send_response(200)
                self.send_header("Content-Type", "text/html; charset=utf-8")
                self.send_header("Content-Length", str(len(data)))
                self.send_header("Cache-Control", "no-store")
                self.end_headers()
                self.wfile.write(data)
                return
            if self.path in ("/api/status", "/status"):
                payload = get_status()
                # hard filter: only allowed keys
                safe = {
                    "title": str(payload.get("title", "RESTORE PRIVACY")),
                    "clients_connected": int(payload.get("clients_connected", 0)),
                }
                data = json.dumps(safe).encode("utf-8")
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(data)))
                self.send_header("Cache-Control", "no-store")
                self.end_headers()
                self.wfile.write(data)
                return
            self.send_response(404)
            self.end_headers()

    return Handler


def start_ui_server(host: str, port: int, get_status: Callable[[], dict]) -> ThreadingHTTPServer:
    httpd = ThreadingHTTPServer((host, port), make_handler(get_status))
    t = threading.Thread(target=httpd.serve_forever, name="rpt-ui", daemon=True)
    t.start()
    return httpd
