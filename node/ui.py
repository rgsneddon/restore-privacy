"""Minimal node status UI: human observe → app-testers; public JSON title-only.

When a browser opens the residual node status surface (``/`` / ``/index.html``),
viewers are sent to the product app-testers page on the public status host.
Machine-facing ``/api/status`` and ``/status`` stay **title-only** JSON (no live
session counters). Optional **private** capacity endpoint remains token-gated.
"""

from __future__ import annotations

import json
import os
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Callable, Optional
from urllib.parse import parse_qs, urlparse

from node.aggregate_metrics import filter_public_status

# Default human observe destination (status host app-testers gate).
DEFAULT_OBSERVE_REDIRECT_URL = "https://restoreprivacy.online/app-testers"
# Env override for lab / alternate status origins (must still land on /app-testers
# when using the public product host).
_ENV_OBSERVE_URL = "RPT_NODE_OBSERVE_URL"


def observe_redirect_url() -> str:
    """Absolute URL browsers hit when opening the node status UI."""
    raw = (os.environ.get(_ENV_OBSERVE_URL) or "").strip()
    if raw:
        return raw.rstrip("/") or DEFAULT_OBSERVE_REDIRECT_URL
    return DEFAULT_OBSERVE_REDIRECT_URL


def public_status_from_payload(payload: dict) -> dict:
    """Strip counts/sessions/IPs/aggregates from a status callback for public HTTP."""
    return filter_public_status(payload or {})


def make_handler(
    get_status: Callable[[], dict],
    *,
    get_private_capacity: Optional[Callable[[], dict]] = None,
    observe_url: Optional[str] = None,
):
    dest = (observe_url or "").strip() or observe_redirect_url()

    class Handler(BaseHTTPRequestHandler):
        def log_message(self, format, *args):  # noqa: A003
            # No access logs of any means
            return

        def do_GET(self):  # noqa: N802
            parsed = urlparse(self.path)
            path = parsed.path or self.path

            if path in ("/", "/index.html", "/observe", "/observe/"):
                # Human browser observe → product app-testers (not local title HTML).
                self.send_response(302)
                self.send_header("Location", dest)
                self.send_header("Cache-Control", "no-store")
                # Small HTML fallback if a client ignores Location
                body = (
                    "<!DOCTYPE html><html lang=\"en\"><head>"
                    f'<meta charset="utf-8"/>'
                    f'<meta http-equiv="refresh" content="0;url={dest}"/>'
                    f'<script>location.replace({json.dumps(dest)});</script>'
                    f"<title>Redirect</title></head><body>"
                    f'<p><a href="{dest}">Continue to app testers</a></p>'
                    "</body></html>"
                ).encode("utf-8")
                self.send_header("Content-Type", "text/html; charset=utf-8")
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)
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
            if path in ("/api/private/node-state", "/private/node-state"):
                # Wipe drain/ready for residual hop-off/rejoin (no client counts)
                try:
                    from node.wipe_status import current_wipe_state

                    payload = current_wipe_state()
                except Exception:  # noqa: BLE001
                    payload = {"state": "ready", "host": "", "role": "", "private": True}
                data = json.dumps(payload).encode("utf-8")
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(data)))
                self.send_header("Cache-Control", "no-store")
                self.end_headers()
                self.wfile.write(data)
                return
            if path in (
                "/api/private/cojoined",
                "/private/cojoined",
                "/api/private/rpai",
                "/private/rpai",
                "/api/private/perc",
                "/private/perc",
            ):
                # Co-joined role snapshot (VPN + rpAI + Perccent) — private only.
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
                    body = b'{"error":"unauthorized"}'
                    self.send_header("Content-Length", str(len(body)))
                    self.end_headers()
                    self.wfile.write(body)
                    return
                try:
                    from node.cojoined_roles import cojoined_private_payload

                    payload = cojoined_private_payload()
                except Exception:  # noqa: BLE001
                    payload = {"cojoined": False, "error": "unavailable"}
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
