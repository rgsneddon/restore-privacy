#!/usr/bin/env python3
"""Restore Privacy status page for Render.

Proxies live **current** session count from the Vultr node. The page updates the
count dynamically via client-side fetch of /api/status (no full-page refresh).
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
# Client-side poll interval (ms) for live count updates without page reload
POLL_INTERVAL_MS = int(os.environ.get("RPT_STATUS_POLL_MS", "3000"))

# Fields that must never appear (totals / lifetime / identity)
FORBIDDEN_STATUS_KEYS = frozenset(
    {
        "total",
        "total_clients",
        "clients_total",
        "lifetime",
        "lifetime_clients",
        "cumulative",
        "peak",
        "history",
        "ip",
        "ips",
        "clients",
        "sessions",
    }
)


def normalize_status(data: dict | None) -> dict:
    """Map upstream JSON to current-session count only (not a cumulative total)."""
    data = data or {}
    # Prefer explicit current-session fields; never lifetime/total counters
    raw = data.get("clients_connected")
    if raw is None:
        raw = data.get("current_clients")
    if raw is None:
        raw = data.get("active_sessions")
    try:
        n = int(raw if raw is not None else 0)
    except (TypeError, ValueError):
        n = 0
    if n < 0:
        n = 0
    return {
        "title": str(data.get("title", "RESTORE PRIVACY")),
        # Name emphasizes current live sessions, not a running total
        "clients_connected": n,
    }


def public_status_payload(status: dict) -> dict:
    """Strict public JSON: title + current count only."""
    safe = normalize_status(status)
    # Drop anything else that may have been attached
    return {
        "title": safe["title"],
        "clients_connected": int(safe["clients_connected"]),
    }


def fetch_upstream_status() -> dict:
    """Pull live current count from the node; never store it. Fallback to 0 on failure."""
    try:
        req = urllib.request.Request(
            UPSTREAM_STATUS_URL,
            headers={
                "User-Agent": "restore-privacy-status-page/1.1",
                "Accept": "application/json",
            },
            method="GET",
        )
        with urllib.request.urlopen(req, timeout=FETCH_TIMEOUT_SEC) as resp:
            raw = resp.read().decode("utf-8", errors="replace")
        data = json.loads(raw)
        if not isinstance(data, dict):
            return {"title": "RESTORE PRIVACY", "clients_connected": 0, "upstream_ok": False}
        out = public_status_payload(data)
        out["upstream_ok"] = True
        return out
    except (
        urllib.error.URLError,
        urllib.error.HTTPError,
        TimeoutError,
        ValueError,
        TypeError,
        OSError,
        json.JSONDecodeError,
    ):
        return {"title": "RESTORE PRIVACY", "clients_connected": 0, "upstream_ok": False}


def render_html(status: dict, poll_ms: int | None = None) -> bytes:
    """HTML with live JS poll of /api/status — no full-page meta refresh."""
    title = status.get("title", "RESTORE PRIVACY")
    n = int(status.get("clients_connected", 0))
    interval = int(poll_ms if poll_ms is not None else POLL_INTERVAL_MS)
    if interval < 500:
        interval = 500
    # Escape for embedding in HTML text (title is product constant; still sanitize)
    title_safe = (
        str(title)
        .replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
    )
    body = f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="utf-8"/>
  <meta name="viewport" content="width=device-width, initial-scale=1"/>
  <title>{title_safe}</title>
  <style>
    body {{ margin:0; min-height:100vh; display:flex; flex-direction:column;
           align-items:center; justify-content:center; background:#0b0f14; color:#e8eef5;
           font-family: system-ui, sans-serif; }}
    h1 {{ letter-spacing:0.12em; font-weight:600; font-size:clamp(1.6rem, 4vw, 2.2rem); margin:0 0 1.5rem; }}
    .count {{ font-size:1.25rem; opacity:0.9; }}
    .num {{ font-size:3rem; font-weight:700; margin-top:0.4rem; color:#6ee7b7; }}
    .hint {{ margin-top:1rem; font-size:0.85rem; opacity:0.55; }}
  </style>
</head>
<body>
  <h1>{title_safe}</h1>
  <div class="count">Currently connected clients</div>
  <div class="num" id="clients-connected" data-metric="current">{n}</div>
  <div class="hint">Live count · updates automatically</div>
  <script>
(function () {{
  var el = document.getElementById('clients-connected');
  var pollMs = {interval};
  function applyCount(n) {{
    if (typeof n !== 'number' || !isFinite(n) || n < 0) n = 0;
    el.textContent = String(Math.floor(n));
  }}
  function poll() {{
    fetch('/api/status', {{ cache: 'no-store', credentials: 'same-origin' }})
      .then(function (r) {{ return r.json(); }})
      .then(function (data) {{
        // Only live session count (clients_connected)
        if (data && Object.prototype.hasOwnProperty.call(data, 'clients_connected')) {{
          applyCount(Number(data.clients_connected));
        }}
      }})
      .catch(function () {{ /* keep last shown value */ }});
  }}
  setInterval(poll, pollMs);
  // Immediate refresh after load so first paint can correct without reload
  setTimeout(poll, 200);
}})();
  </script>
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
            self._send(
                200,
                "text/html; charset=utf-8",
                render_html(fetch_upstream_status()),
            )
            return
        if path in ("/api/status", "/status"):
            status = fetch_upstream_status()
            safe = public_status_payload(status)
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
