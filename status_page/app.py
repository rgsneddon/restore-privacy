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
import urllib.parse
import urllib.request
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

from admin_panel import (
    SESSION_COOKIE,
    admin_enabled,
    is_authenticated,
    mint_session_token,
    render_admin_html,
    render_login_html,
    verify_credentials,
)
from downloads import download_css, render_download_section_html
from payments import (
    PRICE_LABEL,
    PRICE_PENCE,
    activate_connect_entitlement,
    check_fulfilment_ready,
    consume_download_token,
    create_checkout_session,
    find_grant_by_session,
    get_connect_entitlement,
    handle_stripe_webhook,
    init_db,
    lookup_download_token,
    open_release_asset,
    platform_filename,
    render_post_payment_thankyou_html,
    stripe_configured,
    wait_for_grant_by_session,
)
from processor_plugins import apply_processor_entry, apply_stored_env_to_process

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

# Public legal / audit: same-origin on this Render host (GitHub optional secondary).
from public_docs import (  # noqa: E402
    AUDIT_PATH,
    HOW_TO_BUY_PATH,
    LICENSE_PATH,
    PRIVACY_PATH,
    README_PATH,
    document_bytes_for_path,
    load_public_document_bytes,
    production_status_origin,
    public_doc_absolute_url,
    public_docs_catalog,
    render_how_to_buy_html,
    render_public_nav_links_html,
)

# Absolute URLs for operators / external quote (status origin + path).
LICENCE_URL = public_doc_absolute_url(LICENSE_PATH)
PRIVACY_POLICY_URL = public_doc_absolute_url(PRIVACY_PATH)
SECURITY_AUDIT_URL = public_doc_absolute_url(AUDIT_PATH)
README_URL = public_doc_absolute_url(README_PATH)
HOW_TO_BUY_URL = public_doc_absolute_url(HOW_TO_BUY_PATH)
# Same-origin paths (also used as hrefs on the public page).
SECURITY_AUDIT_LOCAL_PATH = AUDIT_PATH
SECURITY_AUDIT_LOCAL_PATH_LOWER = "/audit.md"
LICENCE_LOCAL_PATH = LICENSE_PATH
PRIVACY_LOCAL_PATH = PRIVACY_PATH

# Labels shown under the product title (terms of use / privacy / audit).
LICENCE_LABEL = "LICENCE"
PRIVACY_POLICY_LABEL = "PRIVACY POLICY"
SECURITY_AUDIT_LABEL = "SECURITY AUDIT"

# Public product repository (footer link) — pre-RUST restore-privacy monorepo.
PRODUCT_REPO_URL = "https://github.com/rgsneddon/restore-privacy"
PRODUCT_REPO_LABEL = "Package source - restore-privacy (signed releases)"
# Back-compat aliases (historical RUST_REPO_* names).
RUST_REPO_URL = PRODUCT_REPO_URL
RUST_REPO_LABEL = PRODUCT_REPO_LABEL

# Kept for older imports/tests that still reference the constant name.
BETA_NOTE_TEXT = ""
BETA_NOTE_URL = "https://x.com/rgsneddon"
GITHUB_BLOB_MAIN = "https://github.com/rgsneddon/restore-privacy/blob/main"


def audit_document_bytes() -> bytes | None:
    """Load AUDIT.md (status public pack, status_page, repo root, install root)."""
    data = load_public_document_bytes("AUDIT.md", min_size=200)
    if data is not None:
        return data
    # Back-compat: RPT_AUDIT_PATH override
    extra = Path(os.environ.get("RPT_AUDIT_PATH", ""))
    try:
        if extra.is_file() and extra.stat().st_size > 200:
            return extra.read_bytes()
    except OSError:
        pass
    return None


def render_legal_links_html() -> str:
    """Links immediately below the headline: licence / privacy / audit / README."""
    return render_public_nav_links_html()


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
    """HTML: title + legal/audit links + audit countdown + downloads (no client count)."""
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
    try:
        from audit_countdown import render_audit_countdown_html
    except ImportError:  # package-style import when status_page is on path
        from status_page.audit_countdown import render_audit_countdown_html  # type: ignore
    countdown_html = render_audit_countdown_html()
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
    .audit-countdown {{ margin:0 0 1.25rem; text-align:center; max-width:28rem;
                        padding:0 1rem; letter-spacing:0.02em; }}
    .audit-countdown-row {{ font-size:0.95rem; color:#a7f3d0; }}
    .audit-countdown-label {{ color:#9ca3af; margin-right:0.5rem; text-transform:lowercase; }}
    .audit-countdown-value {{ font-variant-numeric:tabular-nums; font-weight:700;
                              color:#6ee7b7; font-size:1.05rem; }}
    .audit-countdown-blurb {{ margin:0.4rem 0 0; font-size:0.78rem; line-height:1.4;
                              color:#9ca3af; font-weight:400; letter-spacing:0.01em; }}
{dl_css}
  </style>
</head>
<body>
  <img class="brand-logo" src="/logo.png" width="96" height="96" alt="Restore Privacy logo"/>
  <h1>{title_safe}</h1>
{render_legal_links_html()}
{countdown_html}
{downloads_html}
</body>
</html>
"""
    return body.encode("utf-8")

def _parse_query(path_with_q: str) -> tuple[str, dict[str, str]]:
    if "?" not in path_with_q:
        return path_with_q, {}
    path, q = path_with_q.split("?", 1)
    return path, dict(urllib.parse.parse_qsl(q, keep_blank_values=True))


def _escape_html(s: str) -> str:
    return (
        s.replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
    )


def _html_page(title: str, body_inner: str) -> bytes:
    title_safe = _escape_html(title)
    return f"""<!DOCTYPE html>
<html lang="en"><head>
<meta charset="utf-8"/><meta name="viewport" content="width=device-width, initial-scale=1"/>
<title>{title_safe}</title>
<style>
body{{margin:0;min-height:100vh;display:flex;flex-direction:column;align-items:center;
justify-content:center;background:#0b0f14;color:#e8eef5;font-family:system-ui,sans-serif;
padding:2rem;text-align:center}}
a{{color:#93c5fd}} .msg{{max-width:28rem;line-height:1.5;margin:0.65rem auto}}
.thankyou h1{{letter-spacing:0.08em;margin:0 0 0.75rem}}
.pkg{{font-size:1.05rem;margin:0.5rem 0 1rem}}
.admin-run{{color:#fde68a;font-weight:500}}
a.dl{{display:inline-block;margin:0.75rem 0;padding:0.75rem 1.25rem;background:#1d4ed8;
color:#fff;text-decoration:none;border-radius:8px;font-weight:600}}
a.dl:hover{{background:#2563eb}}
.muted{{opacity:0.8;font-size:0.9rem}}
</style></head><body>
{body_inner}
</body></html>
""".encode("utf-8")


class Handler(BaseHTTPRequestHandler):
    def log_message(self, format, *args):  # noqa: A003
        # No access / user-info logs
        return

    def _send(
        self,
        code: int,
        content_type: str,
        data: bytes,
        *,
        extra_headers: list[tuple[str, str]] | None = None,
    ) -> None:
        self.send_response(code)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(data)))
        self.send_header("Cache-Control", "no-store")
        if extra_headers:
            for k, v in extra_headers:
                self.send_header(k, v)
        self.end_headers()
        self.wfile.write(data)

    def _redirect(self, location: str, code: int = 302) -> None:
        self.send_response(code)
        self.send_header("Location", location)
        self.send_header("Content-Length", "0")
        self.send_header("Cache-Control", "no-store")
        self.end_headers()

    def _read_body(self) -> bytes:
        try:
            n = int(self.headers.get("Content-Length") or "0")
        except ValueError:
            n = 0
        if n <= 0:
            return b""
        return self.rfile.read(n)

    def do_GET(self):  # noqa: N802
        path, query = _parse_query(self.path)
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
        if path in ("/health/fulfilment", "/api/fulfilment-ready"):
            # Production readiness: can the host open a catalog installer?
            payload = check_fulfilment_ready()
            code = 200 if payload.get("ok") else 503
            self._send(
                code,
                "application/json",
                json.dumps(payload).encode("utf-8"),
            )
            return

        if path in ("/api/connect-entitlement", "/connect-entitlement"):
            # Payment entitlement for Connect gate (no PII; session_id only)
            session_id = (query.get("session_id") or "").strip()
            if not session_id:
                self._send(
                    400,
                    "application/json",
                    json.dumps(
                        {
                            "status": "unknown",
                            "connect_allowed": False,
                            "error": "missing_session_id",
                        }
                    ).encode("utf-8"),
                )
                return
            ent = get_connect_entitlement(session_id)
            if not ent:
                payload = {
                    "session_id": session_id,
                    "status": "unknown",
                    "connect_allowed": False,
                    "reason": "no_entitlement",
                }
            else:
                payload = {
                    "session_id": ent["session_id"],
                    "status": ent["status"],
                    "platform": ent.get("platform") or "",
                    "reason": ent.get("reason") or "",
                    "connect_allowed": bool(ent.get("connect_allowed")),
                }
            self._send(
                200,
                "application/json",
                json.dumps(payload).encode("utf-8"),
            )
            return

        # --- Paid download flow ---
        if path == "/pay":
            # Legacy path: same Stripe payment page as the download buttons.
            from payments import stripe_payment_page_href_for_platform

            platform = (query.get("platform") or "").strip()
            if not platform or not platform_filename(platform):
                self._send(
                    400,
                    "text/html; charset=utf-8",
                    _html_page("Pay", '<p class="msg">Unknown package.</p><p><a href="/">Back</a></p>'),
                )
                return
            self._redirect(stripe_payment_page_href_for_platform(platform))
            return

        if path == "/download":
            token = (query.get("token") or "").strip()
            # Lookup without consuming so proxy failure does not burn the grant.
            grant = lookup_download_token(token) if token else None
            fname = (grant or {}).get("filename") if grant else None
            if not grant or not fname:
                self._send(
                    403,
                    "text/html; charset=utf-8",
                    _html_page(
                        "Download unavailable",
                        '<p class="msg" id="download-denied">Invalid, expired, or already-used download link.</p>'
                        '<p><a href="/">Get a new download</a></p>',
                    ),
                )
                return
            # Paid proxy: stream installer from local/API (works when repo is private).
            # Do NOT redirect unpaid browsers to free public github.com/releases/download.
            asset = open_release_asset(str(fname))
            if asset is None:
                self._send(
                    502,
                    "text/html; charset=utf-8",
                    _html_page(
                        "Fulfilment error",
                        '<p class="msg" id="download-fulfil-failed">Paid download could not be fetched. '
                        "Operators: set RPT_GITHUB_TOKEN (or GITHUB_TOKEN) with contents:read, "
                        "or stage packages under status_page/assets/.</p>"
                        '<p><a href="/">Home</a></p>',
                    ),
                )
                return
            # Consume only after the installer source is open (single-use starts here).
            if not consume_download_token(token):
                try:
                    body_fail = asset.get("body")
                    if hasattr(body_fail, "close"):
                        body_fail.close()
                except Exception:  # noqa: BLE001
                    pass
                self._send(
                    403,
                    "text/html; charset=utf-8",
                    _html_page(
                        "Download unavailable",
                        '<p class="msg" id="download-denied">Invalid, expired, or already-used download link.</p>'
                        '<p><a href="/">Get a new download</a></p>',
                    ),
                )
                return
            body = asset["body"]
            ctype = str(asset.get("content_type") or "application/octet-stream")
            length = asset.get("content_length")
            disp = f'attachment; filename="{fname}"'
            try:
                self.send_response(200)
                self.send_header("Content-Type", ctype)
                self.send_header("Content-Disposition", disp)
                self.send_header("Cache-Control", "no-store")
                self.send_header("X-RPT-Fulfilment", str(asset.get("source") or "proxy"))
                if length is not None:
                    self.send_header("Content-Length", str(int(length)))
                self.end_headers()
                if isinstance(body, (bytes, bytearray)):
                    self.wfile.write(body)
                else:
                    try:
                        while True:
                            chunk = body.read(65536)
                            if not chunk:
                                break
                            self.wfile.write(chunk)
                    finally:
                        try:
                            body.close()
                        except Exception:  # noqa: BLE001
                            pass
            except Exception:  # noqa: BLE001
                try:
                    if hasattr(body, "close"):
                        body.close()
                except Exception:  # noqa: BLE001
                    pass
                raise
            return

        if path in ("/download/success", "/pay/success"):
            token = (query.get("token") or "").strip()
            platform = (query.get("platform") or "").strip()
            session_id = (query.get("session_id") or "").strip()
            # Stripe success_url supplies session_id={CHECKOUT_SESSION_ID}; webhook
            # may still be in-flight — poll briefly for the minted grant.
            grant = None
            if token:
                # Prefer grant row (filename) without consuming; fallback token-only.
                grant = lookup_download_token(token)
                if grant is None:
                    grant = {
                        "token": token,
                        "filename": platform_filename(platform) or "package",
                        "platform": platform,
                        "download_path": (
                            f"/download?token={urllib.parse.quote(token)}"
                        ),
                    }
            elif session_id:
                # Payment Link after_payment redirect lands here; webhook may lag
                # on free-tier cold start — wait longer than a local unit test.
                grant = wait_for_grant_by_session(session_id, timeout_sec=20.0)
                if grant is None:
                    grant = find_grant_by_session(session_id)
            if grant and grant.get("token"):
                tok = str(grant["token"])
                link = grant.get("download_path") or (
                    f"/download?token={urllib.parse.quote(tok)}"
                )
                fname = (
                    grant.get("filename")
                    or platform_filename(platform)
                    or platform
                    or "package"
                )
                plat = str(grant.get("platform") or platform or "")
                # Ensure Connect entitlement is active for this paid session
                if session_id:
                    activate_connect_entitlement(session_id, platform=plat)
                inner = render_post_payment_thankyou_html(
                    download_path=str(link),
                    filename=str(fname),
                    platform=plat,
                    session_id=session_id,
                )
            else:
                # Meta-refresh so a late webhook can still unlock the page
                refresh = ""
                if session_id:
                    q = urllib.parse.urlencode(
                        {"session_id": session_id, "platform": platform}
                    )
                    refresh = (
                        f'<meta http-equiv="refresh" content="3;url=/download/success?{q}"/>'
                    )
                inner = (
                    f"{refresh}"
                    f'<p class="msg" id="pay-success-pending">Payment submitted'
                    f'{(" for " + _escape_html(platform)) if platform else ""}. '
                    f"Confirming with Stripe… this page refreshes automatically.</p>"
                    f'<p class="msg">If nothing appears after ~30s, contact support with session id '
                    f"<code id=\"pending-session-id\">{_escape_html(session_id)}</code>.</p>"
                    f'<p><a href="/">Home</a></p>'
                )
            self._send(200, "text/html; charset=utf-8", _html_page("Thank you", inner))
            return

        if path in ("/download/cancel", "/pay/cancel"):
            self._send(
                200,
                "text/html; charset=utf-8",
                _html_page(
                    "Cancelled",
                    '<p class="msg" id="pay-cancel">Checkout cancelled — no charge.</p>'
                    '<p><a href="/">Back to downloads</a></p>',
                ),
            )
            return

        # Public how-to-buy page
        if path in (HOW_TO_BUY_PATH, "/how-to-buy/", "/howtobuy", "/buy"):
            self._send(
                200,
                "text/html; charset=utf-8",
                render_how_to_buy_html(),
            )
            return

        # Public documents (README, LICENSE, privacy, audit, credits) — same-origin
        doc = document_bytes_for_path(path)
        if doc is not None:
            data, ctype, _title = doc
            self._send(200, ctype, data)
            return
        # Back-compat audit-only aliases if registry miss
        if path in (
            SECURITY_AUDIT_LOCAL_PATH,
            SECURITY_AUDIT_LOCAL_PATH_LOWER,
            "/docs/AUDIT.md",
            "/docs/audit.md",
        ):
            data = audit_document_bytes()
            if data is None:
                self._send(404, "text/plain; charset=utf-8", b"audit not found")
                return
            from public_docs import render_document_html

            html = render_document_html(
                title="Security audit — Restore Privacy",
                raw=data,
                plain=False,
            )
            self._send(200, "text/html; charset=utf-8", html)
            return

        # --- Admin ---
        if path == "/admin" or path == "/admin/":
            if not admin_enabled():
                self._send(
                    503,
                    "text/plain; charset=utf-8",
                    b"admin disabled (set RPT_ADMIN_PASSWORD)",
                )
                return
            if not is_authenticated(self.headers):
                self._send(200, "text/html; charset=utf-8", render_login_html())
                return
            self._send(200, "text/html; charset=utf-8", render_admin_html())
            return
        if path == "/admin/login":
            # GET shows login form
            if not admin_enabled():
                self._send(503, "text/plain; charset=utf-8", b"admin disabled")
                return
            self._send(200, "text/html; charset=utf-8", render_login_html())
            return
        if path == "/admin/logout":
            self._send(
                302,
                "text/plain; charset=utf-8",
                b"",
                extra_headers=[
                    (
                        "Set-Cookie",
                        f"{SESSION_COOKIE}=; Path=/; HttpOnly; SameSite=Lax; Max-Age=0",
                    ),
                    ("Location", "/admin/login"),
                ],
            )
            return

        self._send(404, "text/plain; charset=utf-8", b"not found")

    def do_POST(self):  # noqa: N802
        path, _query = _parse_query(self.path)
        body = self._read_body()

        if path == "/api/checkout":
            try:
                data = json.loads(body.decode("utf-8") or "{}")
            except json.JSONDecodeError:
                self._send(400, "application/json", b'{"error":"bad_json"}')
                return
            platform = str(data.get("platform") or "").strip()
            if not stripe_configured():
                self._send(
                    503,
                    "application/json",
                    json.dumps(
                        {
                            "error": "stripe_unconfigured",
                            "amount_pence": PRICE_PENCE,
                            "price_label": PRICE_LABEL,
                        }
                    ).encode("utf-8"),
                )
                return
            try:
                session = create_checkout_session(platform)
            except ValueError as e:
                self._send(
                    400,
                    "application/json",
                    json.dumps({"error": str(e)}).encode("utf-8"),
                )
                return
            self._send(
                200,
                "application/json",
                json.dumps(
                    {
                        "id": session["id"],
                        "url": session["url"],
                        "amount_pence": session["amount_pence"],
                        "currency": session["currency"],
                        "platform": session["platform"],
                        "filename": session["filename"],
                    }
                ).encode("utf-8"),
            )
            return

        if path == "/webhook/stripe":
            sig = self.headers.get("Stripe-Signature") or ""
            result = handle_stripe_webhook(body, sig)
            if not result.get("ok"):
                self._send(
                    400,
                    "application/json",
                    json.dumps(result).encode("utf-8"),
                )
                return
            # Attach download URL for success page when granted
            if result.get("granted") and result.get("token"):
                result = dict(result)
                result["download_path"] = f"/download?token={result['token']}"
            self._send(200, "application/json", json.dumps(result).encode("utf-8"))
            return

        if path == "/admin/login":
            if not admin_enabled():
                self._send(503, "text/plain; charset=utf-8", b"admin disabled")
                return
            form = dict(urllib.parse.parse_qsl(body.decode("utf-8", "replace")))
            user = form.get("username") or ""
            password = form.get("password") or ""
            if not verify_credentials(user, password):
                self._send(
                    401,
                    "text/html; charset=utf-8",
                    render_login_html(error="Invalid username or password"),
                )
                return
            token = mint_session_token()
            self.send_response(302)
            self.send_header("Location", "/admin")
            self.send_header(
                "Set-Cookie",
                f"{SESSION_COOKIE}={token}; Path=/; HttpOnly; SameSite=Lax; Max-Age=28800",
            )
            self.send_header("Content-Length", "0")
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            return

        if path == "/admin/processors/apply":
            if not admin_enabled():
                self._send(503, "text/plain; charset=utf-8", b"admin disabled")
                return
            if not is_authenticated(self.headers):
                self._send(200, "text/html; charset=utf-8", render_login_html())
                return
            form = dict(urllib.parse.parse_qsl(body.decode("utf-8", "replace")))
            plugin_id = (form.get("plugin_id") or "").strip()
            result = apply_processor_entry(plugin_id, form, persist=True)
            if result.get("ok"):
                keys = ", ".join(result.get("applied_keys") or []) or "(no new values)"
                msg = f"Saved {plugin_id} connection variables: {keys}."
                self._send(
                    200,
                    "text/html; charset=utf-8",
                    render_admin_html(message=msg),
                )
            else:
                err = "; ".join(result.get("errors") or ["apply failed"])
                self._send(
                    400,
                    "text/html; charset=utf-8",
                    render_admin_html(error=err),
                )
            return

        self._send(404, "text/plain; charset=utf-8", b"not found")


def main() -> int:
    apply_stored_env_to_process()
    init_db()
    host = os.environ.get("HOST", "0.0.0.0")
    port = int(os.environ.get("PORT", "10000"))
    httpd = ThreadingHTTPServer((host, port), Handler)
    httpd.serve_forever()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
