#!/usr/bin/env python3
"""Restore Privacy status page for Render.

Public surface: product title, beta note, and client download links only.
Does **not** expose a connected-client count or poll a live session metric.
"""

from __future__ import annotations

import json
import mimetypes
import os
import urllib.error
import urllib.request
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

from downloads import download_css, render_download_section_html

# Public page: title + BETA note + download buttons (no live client counter).

# Brand static files (favicon/logo) live next to this module
STATUS_DIR = Path(__file__).resolve().parent
STATIC_DIR = STATUS_DIR / "static"
FAVICON_PATH = "/favicon.ico"
FAVICON_PNG_PATH = "/favicon.png"
APPLE_TOUCH_PATH = "/apple-touch-icon.png"
LOGO_PATH = "/logo.png"

# Map URL path → filename under static/
STATIC_ROUTES: dict[str, str] = {
    FAVICON_PATH: "favicon.ico",
    "/favicon.ico": "favicon.ico",
    FAVICON_PNG_PATH: "favicon.png",
    APPLE_TOUCH_PATH: "apple-touch-icon.png",
    LOGO_PATH: "logo.png",
    "/static/favicon.ico": "favicon.ico",
    "/static/favicon.png": "favicon.png",
    "/static/logo.png": "logo.png",
    "/static/apple-touch-icon.png": "apple-touch-icon.png",
}


def static_file_path(url_path: str) -> Path | None:
    """Resolve a public static URL to a file under status_page/static/."""
    name = STATIC_ROUTES.get(url_path)
    if not name:
        return None
    path = (STATIC_DIR / name).resolve()
    try:
        path.relative_to(STATIC_DIR.resolve())
    except ValueError:
        return None
    return path if path.is_file() else None


def read_static_bytes(url_path: str) -> tuple[bytes, str] | None:
    path = static_file_path(url_path)
    if path is None:
        return None
    data = path.read_bytes()
    ctype, _ = mimetypes.guess_type(str(path))
    if not ctype:
        if path.suffix.lower() == ".ico":
            ctype = "image/x-icon"
        elif path.suffix.lower() == ".png":
            ctype = "image/png"
        else:
            ctype = "application/octet-stream"
    return data, ctype

# Public legal / audit document links (stable GitHub blob URLs).
GITHUB_BLOB_MAIN = "https://github.com/rgsneddon/restore-privacy/blob/main"
LICENCE_URL = f"{GITHUB_BLOB_MAIN}/LICENSE"
PRIVACY_POLICY_URL = f"{GITHUB_BLOB_MAIN}/PRIVACY_POLICY.md"
SECURITY_AUDIT_URL = f"{GITHUB_BLOB_MAIN}/audit.md"

# Labels shown under the product title (terms of use / privacy / audit).
LICENCE_LABEL = "LICENCE"
PRIVACY_POLICY_LABEL = "PRIVACY POLICY"
SECURITY_AUDIT_LABEL = "SECURITY AUDIT"

# New Rust rewrite repository (footer link).
RUST_REPO_URL = "https://github.com/rgsneddon/restore-privacy-rust"
RUST_REPO_LABEL = "Rust rewrite (work in progress)"

# Kept for older imports/tests that still reference the constant name.
BETA_NOTE_TEXT = ""
BETA_NOTE_URL = "https://x.com/rgsneddon"


def render_legal_links_html() -> str:
    """Links immediately below the RESTORE PRIVACY headline (licence / privacy / audit)."""
    items = (
        (LICENCE_LABEL, LICENCE_URL, "licence-link"),
        (PRIVACY_POLICY_LABEL, PRIVACY_POLICY_URL, "privacy-link"),
        (SECURITY_AUDIT_LABEL, SECURITY_AUDIT_URL, "audit-link"),
    )
    anchors = []
    for label, url, el_id in items:
        anchors.append(
            f'<a class="doc-link" id="{el_id}" href="{url}" '
            f'rel="noopener noreferrer" target="_blank">{label}</a>'
        )
    joined = '<span class="doc-sep" aria-hidden="true"> · </span>'.join(anchors)
    return (
        f'  <nav class="doc-links" id="doc-links" aria-label="Legal and audit documents">'
        f"{joined}</nav>"
    )


def render_beta_note_html() -> str:
    """Deprecated: under-title strip is now legal/audit links (kept for import compat)."""
    return render_legal_links_html()


# Upstream VPN node status (override via env on Render) — used only for health/title
DEFAULT_UPSTREAM = "http://82.221.101.241:8080/api/status"
UPSTREAM_STATUS_URL = os.environ.get("RPT_STATUS_UPSTREAM", DEFAULT_UPSTREAM).strip()
FETCH_TIMEOUT_SEC = float(os.environ.get("RPT_STATUS_TIMEOUT", "4"))

# Fields that must never appear on the public surface (counts, identities, lists,
# or even node-wide aggregates — public page stays title + downloads only).
FORBIDDEN_STATUS_KEYS = frozenset(
    {
        "clients_connected",
        "current_clients",
        "active_sessions",
        "live_clients",
        "connected_clients",
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
        "client_ip",
        "client_ips",
        "clients",
        "sessions",
        "session_ids",
        "session_list",
        "per_client",
        "per_session",
        "by_client",
        "by_session",
        "client_id",
        "client_ids",
        "user",
        "users",
        "username",
        "identity",
        "identities",
        "bandwidth_per_client",
        "bytes_per_client",
        "client_bandwidth",
        "session_bandwidth",
        # Aggregates stay off the public page (internal node monitoring only)
        "total_bytes_in",
        "total_bytes_out",
        "total_bytes_relayed",
        "total_datagrams_in",
        "total_datagrams_out",
        "process_uptime_sec",
        "bandwidth",
        "bytes",
    }
)

# Only these keys may appear in public status JSON (upstream_ok is transport meta).
ALLOWED_PUBLIC_STATUS_KEYS = frozenset({"title"})


def normalize_status(data: dict | None) -> dict:
    """Map upstream JSON to public title only — never counts, lists, or aggregates."""
    data = data or {}
    # Explicitly drop forbidden keys even if an allow-list miss occurs later
    for key in list(data.keys()):
        if str(key).lower() in FORBIDDEN_STATUS_KEYS or str(key) in FORBIDDEN_STATUS_KEYS:
            continue
    return {
        "title": str(data.get("title", "RESTORE PRIVACY")),
    }


def public_status_payload(status: dict) -> dict:
    """Strict public JSON: product title only (no clients_connected / aggregates)."""
    safe = normalize_status(status)
    # Hard allow-list — never pass through unexpected fields
    out = {"title": safe["title"]}
    for k in list(out.keys()):
        if k not in ALLOWED_PUBLIC_STATUS_KEYS:
            del out[k]
    return out


def fetch_upstream_status() -> dict:
    """Pull optional title from the node; never expose a session count."""
    try:
        req = urllib.request.Request(
            UPSTREAM_STATUS_URL,
            headers={
                "User-Agent": "restore-privacy-status-page/1.2",
                "Accept": "application/json",
            },
            method="GET",
        )
        with urllib.request.urlopen(req, timeout=FETCH_TIMEOUT_SEC) as resp:
            raw = resp.read().decode("utf-8", errors="replace")
        data = json.loads(raw)
        if not isinstance(data, dict):
            return {"title": "RESTORE PRIVACY", "upstream_ok": False}
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
        return {"title": "RESTORE PRIVACY", "upstream_ok": False}


def render_html(status: dict, poll_ms: int | None = None) -> bytes:
    """HTML: title + legal/audit links + downloads + Rust repo footer (no client count)."""
    _ = poll_ms  # retained for call-site compat; public page does not poll a count
    title = status.get("title", "RESTORE PRIVACY")
    # Escape for embedding in HTML text (title is product constant; still sanitize)
    title_safe = (
        str(title)
        .replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
    )
    downloads_html = render_download_section_html()
    dl_css = download_css()
    body = f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="utf-8"/>
  <meta name="viewport" content="width=device-width, initial-scale=1"/>
  <title>{title_safe}</title>
  <link rel="icon" href="/favicon.ico" type="image/x-icon"/>
  <link rel="icon" href="/favicon.png" type="image/png" sizes="32x32"/>
  <link rel="apple-touch-icon" href="/apple-touch-icon.png"/>
  <style>
    body {{ margin:0; min-height:100vh; display:flex; flex-direction:column;
           align-items:center; justify-content:center; background:#0b0f14; color:#e8eef5;
           font-family: system-ui, sans-serif; padding: 2rem 0; box-sizing: border-box; }}
    .brand-logo {{ width:96px; height:96px; border-radius:18px; margin:0 0 1rem;
                   object-fit:cover; box-shadow:0 4px 24px rgba(0,0,0,0.35); }}
    h1 {{ letter-spacing:0.12em; font-weight:600; font-size:clamp(1.6rem, 4vw, 2.2rem); margin:0 0 0.65rem; }}
    .doc-links {{ margin:0 0 1.5rem; max-width:32rem; text-align:center; padding:0 1rem;
                  font-size:0.9rem; line-height:1.5; }}
    .doc-links a.doc-link {{ color:#93c5fd; text-decoration:underline; font-weight:600;
                             letter-spacing:0.04em; }}
    .doc-links a.doc-link:hover {{ color:#bfdbfe; }}
    .doc-sep {{ color:#6b7280; margin:0 0.15rem; }}
{dl_css}
  </style>
</head>
<body>
  <img class="brand-logo" src="/logo.png" width="96" height="96" alt="Restore Privacy logo"/>
  <h1>{title_safe}</h1>
{render_legal_links_html()}
{downloads_html}
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
        static = read_static_bytes(path)
        if static is not None:
            data, ctype = static
            # Favicon/logo can be cached lightly; still no user data
            self.send_response(200)
            self.send_header("Content-Type", ctype)
            self.send_header("Content-Length", str(len(data)))
            self.send_header("Cache-Control", "public, max-age=3600")
            self.end_headers()
            self.wfile.write(data)
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
