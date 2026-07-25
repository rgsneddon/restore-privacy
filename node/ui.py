"""Minimal node status UI: product title only (no public client count).

Optional **private** capacity endpoint (token-gated) for residual load probes —
never mixed into public HTML/JSON status.
"""

from __future__ import annotations

import json
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Callable, Optional
from urllib.parse import parse_qs, urlparse

from node.aggregate_metrics import filter_public_status


def public_status_from_payload(payload: dict) -> dict:
    """Strip counts/sessions/IPs/aggregates from a status callback for public HTTP."""
    return filter_public_status(payload or {})


def make_handler(
    get_status: Callable[[], dict],
    *,
    get_private_capacity: Optional[Callable[[], dict]] = None,
):
    class Handler(BaseHTTPRequestHandler):
        def log_message(self, format, *args):  # noqa: A003
            # No access logs of any means
            return

        def do_GET(self):  # noqa: N802
            parsed = urlparse(self.path)
            path = parsed.path or self.path

            if path in ("/", "/index.html"):
                status = public_status_from_payload(get_status())
                title = status.get("title", "RESTORE PRIVACY")
                body = f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="utf-8"/>
  <title>{title}</title>
  <style>
    body {{ margin:0; min-height:100vh; display:flex; flex-direction:column;
           align-items:center; justify-content:center; background:#0b0f14; color:#e8eef5;
           font-family: system-ui, sans-serif; }}
    h1 {{ letter-spacing:0.12em; font-weight:600; font-size:2.2rem; margin:0 0 1.5rem; }}
    .tag {{ font-size:1rem; opacity:0.75; max-width:22rem; text-align:center; }}
  </style>
</head>
<body>
  <h1>{title}</h1>
  <div class="tag">Node online. No public live session counter.</div>
</body>
</html>
"""
                data = body.encode("utf-8")
                self.send_response(200)
                self.send_header("Content-Type", "text/html; charset=utf-8")
                self.send_header("Content-Length", str(data.__len__()))
                self.send_header("Cache-Control", "no-store")
                self.end_headers()
                self.wfile.write(data)
                return
            if path in ("/api/status", "/status"):
                safe = public_status_from_payload(get_status())
                data = json.dumps(safe).encode("utf-8")
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(data)))
                self.send_header("Cache-Control", "no-store")
                self.end_headers()
                self.wfile.write(data)
                return
            if path in ("/api/private/capacity", "/private/capacity"):
                # Private residual load hint — requires RPT_CAPACITY_TOKEN
                from node.private_capacity import authorize_capacity_request

                qs = parse_qs(parsed.query or "")
                q_token = ""
                if "token" in qs and qs["token"]:
                    q_token = str(qs["token"][0] or "")
                ok, _reason = authorize_capacity_request(
                    authorization_header=self.headers.get("Authorization", "") or "",
                    x_token_header=self.headers.get("X-RPT-Capacity-Token", "") or "",
                    query_token=q_token,
                )
                if not ok:
                    self.send_response(401)
                    self.send_header("Content-Type", "application/json")
                    self.send_header("Cache-Control", "no-store")
                    body = b'{"error":"unauthorized"}'
                    self.send_header("Content-Length", str(len(body)))
                    self.end_headers()
                    self.wfile.write(body)
                    return
                if get_private_capacity is None:
                    self.send_response(503)
                    self.send_header("Content-Type", "application/json")
                    body = b'{"error":"capacity unavailable"}'
                    self.send_header("Content-Length", str(len(body)))
                    self.end_headers()
                    self.wfile.write(body)
                    return
                try:
                    payload = get_private_capacity() or {}
                except Exception:  # noqa: BLE001
                    self.send_response(500)
                    self.end_headers()
                    return
                # Never route through public filter (that strips capacity fields)
                data = json.dumps(payload).encode("utf-8")
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


def start_ui_server(
    host: str,
    port: int,
    get_status: Callable[[], dict],
    *,
    get_private_capacity: Optional[Callable[[], dict]] = None,
) -> ThreadingHTTPServer:
    httpd = ThreadingHTTPServer(
        (host, port),
        make_handler(get_status, get_private_capacity=get_private_capacity),
    )
    t = threading.Thread(target=httpd.serve_forever, name="rpt-ui", daemon=True)
    t.start()
    return httpd
