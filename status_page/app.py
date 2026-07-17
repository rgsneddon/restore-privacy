#!/usr/bin/env python3
"""Restore Privacy status page for Render.

Serves the same UI as the node (:8080) and proxies /api/status to the Vultr
node so the public page never holds user-info logs — only title + count.
"""

from __future__ import annotations

import json
import os
import urllib.error
import urllib.request
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

# Upstream VPN node status (override via env on Render)
DEFAULT_UPSTREAM = "http://104.156.224.47:8080/api/status"
UPSTREAM_STATUS_URL = os.environ.get("RPT_STATUS_UPSTREAM", DEFAULT_UPSTREAM).strip()
FETCH_TIMEOUT_SEC = float(os.environ.get("RPT_STATUS_TIMEOUT", "4"))


def fetch_upstream_status() -> dict:
    """Pull live count from the node; never store it. Fallback to 0 on failure."""
    try:
        req = urllib.request.Request(
            UPSTREAM_STATUS_URL,
            headers={"User-Agent": "restore-privacy-status-page/1.0", "Accept": "application/json"},
            method="GET",
        )
        with urllib.request.urlopen(req, timeout=FETCH_TIMEOUT_SEC) as resp:
            raw = resp.read().decode("utf-8", errors="replace")
        data = json.loads(raw)
        return {
            "title": str(data.get("title", "RESTORE PRIVACY")),
            "clients_connected": int(data.get("clients_connected", 0)),
        }
    except (urllib.error.URLError, urllib.error.HTTPError, TimeoutError, ValueError, TypeError, OSError):
        return {"title": "RESTORE PRIVACY", "clients_connected": 0, "upstream_ok": False}


def render_html(status: dict) -> bytes:
    title = status.get("title", "RESTORE PRIVACY")
    n = int(status.get("clients_connected", 0))
    body = f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="utf-8"/>
  <meta http-equiv="refresh" content="5"/>
  <meta name="viewport" content="width=device-width, initial-scale=1"/>
  <title>{title}</title>
  <style>
    body {{ margin:0; min-height:100vh; display:flex; flex-direction:column;
           align-items:center; justify-content:center; background:#0b0f14; color:#e8eef5;
           font-family: system-ui, sans-serif; }}
    h1 {{ letter-spacing:0.12em; font-weight:600; font-size:clamp(1.6rem, 4vw, 2.2rem); margin:0 0 1.5rem; }}
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
    return body.encode("utf-8")


class Handler(BaseHTTPRequestHandler):
    def log_message(self, format, *args):  # noqa: A003
        # No access / user-info logs
        return

    def _send(self, code: int, content_type: str, data: bytes) -> None:
        self.send_response(code)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(data)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(data)

    def do_GET(self):  # noqa: N802
        path = self.path.split("?", 1)[0]
        if path in ("/", "/index.html"):
            self._send(200, "text/html; charset=utf-8", render_html(fetch_upstream_status()))
            return
        if path in ("/api/status", "/status"):
            status = fetch_upstream_status()
            safe = {
                "title": str(status.get("title", "RESTORE PRIVACY")),
                "clients_connected": int(status.get("clients_connected", 0)),
            }
            self._send(200, "application/json", json.dumps(safe).encode("utf-8"))
            return
        if path in ("/health", "/healthz"):
            self._send(200, "application/json", b'{"ok":true}')
            return
        self._send(404, "text/plain; charset=utf-8", b"not found")


def main() -> int:
    host = os.environ.get("HOST", "0.0.0.0")
    port = int(os.environ.get("PORT", "10000"))
    httpd = ThreadingHTTPServer((host, port), Handler)
    httpd.serve_forever()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
