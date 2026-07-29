#!/usr/bin/env python3
"""Restore Privacy VPN APP Shop for Render.

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
    format_session_cookie,
    is_authenticated,
    mint_session_token,
    render_2fa_setup_html,
    render_2fa_verify_html,
    render_admin_html,
    render_login_html,
    verify_credentials,
)
from admin_2fa import (
    PENDING_COOKIE,
    PENDING_TTL_SEC,
    begin_login_after_password,
    complete_setup,
    complete_verify,
    get_enrolled_secret,
    is_totp_enrolled,
    otpauth_uri,
    pending_from_headers,
    verify_pending_token,
    verify_totp,
)
from downloads import download_css, render_bmc_tip_html, render_download_section_html
from settings_explainer import (
    homepage_settings_banner_css,
    render_settings_explainer_banner_html,
    render_settings_explainer_page_html,
    settings_explainer_paths,
)
from payments import (
    PRICE_LABEL,
    PRICE_PENCE,
    activate_connect_entitlement,
    check_fulfilment_ready,
    consume_download_token,
    create_checkout_session,
    create_subscription_checkout_session,
    find_grant_by_session,
    get_connect_entitlement,
    handle_stripe_webhook,
    init_db,
    lookup_download_token,
    open_release_asset,
    platform_filename,
    render_pay_plan_page_html,
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
# Transparent-background site header logo (left of RESTORE PRIVACY VPN)
LOGO_TRANSPARENT_PATH = "/logo_transparent.png"

# Map URL path → filename under static/
STATIC_ROUTES: dict[str, str] = {
    FAVICON_PATH: "favicon.ico",
    "/favicon.ico": "favicon.ico",
    FAVICON_PNG_PATH: "favicon.png",
    APPLE_TOUCH_PATH: "apple-touch-icon.png",
    LOGO_PATH: "logo.png",
    LOGO_TRANSPARENT_PATH: "logo_transparent.png",
    "/static/favicon.ico": "favicon.ico",
    "/static/favicon.png": "favicon.png",
    "/static/logo.png": "logo.png",
    "/static/logo_transparent.png": "logo_transparent.png",
    "/static/apple-touch-icon.png": "apple-touch-icon.png",
    # Stripe Dashboard Branding exports (PNG ≥128px, <512KB)
    "/stripe_brand_icon.png": "stripe_brand_icon.png",
    "/stripe_brand_logo.png": "stripe_brand_logo.png",
    "/static/stripe_brand_icon.png": "stripe_brand_icon.png",
    "/static/stripe_brand_logo.png": "stripe_brand_logo.png",
    # Same-origin JS for CSP script-src 'self' (no inline scripts)
    "/static/public_theme.js": "public_theme.js",
    "/static/admin_theme.js": "admin_theme.js",
    "/static/admin_sidebar.js": "admin_sidebar.js",
    "/static/audit_countdown.js": "audit_countdown.js",
    "/static/audit_page_ticker.js": "audit_page_ticker.js",
    # Written by scripts/run_security_audit.py --write; public Audit page + countdown
    "/static/security_audit_latest.json": "security_audit_latest.json",
    "/static/node_wipe_countdown.js": "node_wipe_countdown.js",
    "/static/thankyou_keygen_copy.js": "thankyou_keygen_copy.js",
    "/static/thankyou_entitlement.js": "thankyou_entitlement.js",
    "/static/admin_fleet_usage.js": "admin_fleet_usage.js",
    "/static/admin_link_generation.js": "admin_link_generation.js",
}

# Customer device-licence renew host (Stripe Checkout custom domain).
# Never emit public_base_url() localhost (127.0.0.1:10000) in renew_url JSON.
DEVICE_LICENCE_PAY_HOST = "https://pay.restoreprivacy.online"


def _device_licence_renew_url(platform: str = "", *, interval: str = "month") -> str:
    """Production renew link for EXPIRED / invalid licence client copy."""
    plat = (platform or "").strip().lower() or "windows"
    iv = (interval or "month").strip().lower()
    if iv in ("year", "yearly", "annual", "annually"):
        iv = "year"
    else:
        iv = "month"
    q = urllib.parse.urlencode({"platform": plat, "interval": iv})
    return f"{DEVICE_LICENCE_PAY_HOST}?{q}"


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
    if path.suffix.lower() == ".js":
        ctype = "application/javascript; charset=utf-8"
    elif not ctype:
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
    try:
        from public_chrome import PUBLIC_BRAND_TITLE, public_display_title
    except ImportError:  # pragma: no cover
        from status_page.public_chrome import (  # type: ignore
            PUBLIC_BRAND_TITLE,
            public_display_title,
        )

    return {
        "title": public_display_title(
            str(data.get("title", PUBLIC_BRAND_TITLE) or PUBLIC_BRAND_TITLE)
        ),
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
            try:
                from public_chrome import PUBLIC_BRAND_TITLE
            except ImportError:  # pragma: no cover
                from status_page.public_chrome import PUBLIC_BRAND_TITLE  # type: ignore

            return {"title": PUBLIC_BRAND_TITLE, "upstream_ok": False}
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
        try:
            from public_chrome import PUBLIC_BRAND_TITLE
        except ImportError:  # pragma: no cover
            from status_page.public_chrome import PUBLIC_BRAND_TITLE  # type: ignore

        return {"title": PUBLIC_BRAND_TITLE, "upstream_ok": False}


def render_html(
    status: dict,
    poll_ms: int | None = None,
    *,
    accept_language: str = "",
    country: str = "",
    currency: str = "",
    default_platform: str = "",
    default_interval: str = "month",
    pay_error: str = "",
) -> bytes:
    """HTML: shared brand header + downloads + audit countdown (no client count).

    *accept_language* / *country* / *currency* drive local-currency price display
    (GBP anchors £2.45 / £27.93 → visitor currency; Stripe-unsupported → USD).
    """
    _ = poll_ms  # retained for call-site compat; public page does not poll a count
    try:
        from public_chrome import (
            PUBLIC_BRAND_TITLE,
            public_brand_header_html,
            public_display_title,
            public_head_open,
            public_page_close,
        )
    except ImportError:  # pragma: no cover
        from status_page.public_chrome import (  # type: ignore
            PUBLIC_BRAND_TITLE,
            public_brand_header_html,
            public_display_title,
            public_head_open,
            public_page_close,
        )

    title = public_display_title(
        str(status.get("title", PUBLIC_BRAND_TITLE) or PUBLIC_BRAND_TITLE)
    )

    downloads_html = render_download_section_html(
        accept_language=accept_language,
        country=country,
        currency=currency,
        default_platform=default_platform,
        default_interval=default_interval,
    )
    if (pay_error or "").strip():
        err = (
            pay_error.replace("&", "&amp;")
            .replace("<", "&lt;")
            .replace(">", "&gt;")
        )
        downloads_html = downloads_html.replace(
            '<div class="dl-buttons"',
            f'<p class="dl-pay-error" id="dl-pay-error" role="alert">{err}</p>\n    <div class="dl-buttons"',
            1,
        )
    dl_css = download_css()
    try:
        from audit_countdown import render_audit_countdown_html
    except ImportError:  # package-style import when status_page is on path
        from status_page.audit_countdown import render_audit_countdown_html  # type: ignore
    try:
        from node_wipe_countdown import render_node_wipe_countdown_html
    except ImportError:
        from status_page.node_wipe_countdown import (  # type: ignore
            render_node_wipe_countdown_html,
        )
    countdown_html = render_audit_countdown_html()
    node_wipe_html = render_node_wipe_countdown_html()
    bmc_tip_html = render_bmc_tip_html()
    # public_head_open already injects public_site_css — only page-specific extras here
    page_css = (
        dl_css
        + homepage_settings_banner_css()
        + """
    .audit-countdown { text-align: center; letter-spacing: 0.02em; width: 100%; }
    .audit-countdown-row {
      font-size: 0.95rem; color: var(--rb-soft, var(--rb-muted));
      display: flex; flex-wrap: wrap; justify-content: center; align-items: baseline;
      gap: 0.45rem 0.75rem;
    }
    .audit-countdown-label { color: var(--rb-muted); text-transform: lowercase; }
    .audit-countdown-value {
      font-variant-numeric: tabular-nums; font-weight: 700;
      color: var(--rb-cream); font-size: 1.15rem;
      background: var(--rb-code-bg, rgba(10, 22, 40, 0.45));
      border: 1px solid var(--rb-card-border);
      border-radius: 12px; padding: 0.35rem 0.75rem;
    }
    .audit-last-run {
      margin: 0.55rem 0 0; font-size: 0.82rem; color: var(--rb-muted);
      text-align: center; width: 100%;
    }
    .audit-last-run time { color: var(--rb-cream); font-weight: 600; }
    .audit-countdown-blurb {
      margin: 0.65rem 0 0; font-size: 0.78rem; line-height: 1.45;
      color: var(--rb-muted); font-weight: 400;
    }
    .node-wipe-countdown { text-align: center; width: 100%; }
    .node-wipe-row {
      display: flex; flex-direction: column; align-items: center; gap: 0.55rem;
      margin: 0.75rem 0 1rem;
    }
    .node-wipe-label {
      color: var(--rb-accent-sky, var(--rb-btn)); font-weight: 700; letter-spacing: 0.03em;
      font-size: clamp(0.72rem, 2.1vw, 0.84rem); line-height: 1.4;
      max-width: 100%; padding: 0 0.25rem;
    }
    .nw-units {
      display: flex; flex-wrap: wrap; justify-content: center; gap: 0.45rem;
    }
    .nw-unit {
      min-width: 3.35rem; padding: 0.45rem 0.5rem 0.4rem;
      border-radius: 12px;
      background: var(--rb-code-bg, rgba(10, 22, 40, 0.55));
      border: 1px solid var(--rb-card-border);
      box-shadow: inset 0 1px 0 rgba(255,255,255,0.06);
      display: flex; flex-direction: column; align-items: center; gap: 0.15rem;
    }
    .nw-unit-value {
      font-variant-numeric: tabular-nums; font-weight: 800;
      font-size: clamp(1.05rem, 3.2vw, 1.35rem); color: var(--rb-cream);
      line-height: 1.1;
    }
    .nw-unit-label {
      font-size: 0.62rem; letter-spacing: 0.08em; font-weight: 700;
      color: var(--rb-muted);
    }
    .node-wipe-blurb {
      margin: 0.25rem auto 0; font-size: 0.72rem; line-height: 1.45;
      color: var(--rb-muted); max-width: 40rem;
    }
    @media (max-width: 520px) {
      .nw-unit { min-width: 3rem; }
    }
"""
    )
    header = public_brand_header_html(
        title=str(title),
        active="home",
        logo_size=112,
        product_active="vpn",
    )
    body = f"""{public_head_open(title=str(title), extra_css=page_css)}
  <div class="page-shell" id="page-shell">
{header}
{render_settings_explainer_banner_html()}
{downloads_html}
{node_wipe_html}
    <section class="panel-card" id="audit-panel" aria-label="Security audit countdown">
{countdown_html}
    </section>
{bmc_tip_html}
  </div>
{public_page_close()}
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
.thankyou h1{{letter-spacing:0.08em;margin:0 0 0.75rem;color:#ffffff}}
.pkg{{font-size:1.05rem;margin:0.5rem 0 1rem;color:#e8eef5}}
.admin-run{{color:#fde68a;font-weight:500}}
.purchase-id-box{{max-width:32rem;margin:1rem auto;padding:0.85rem 1rem;text-align:left;
background:rgba(127,29,29,0.28);border:1px solid #b91c1c;border-radius:10px}}
.purchase-id-value{{font-size:1.15rem;margin:0.4rem 0}}
.purchase-id-value code{{font-size:1.05rem;letter-spacing:0.04em;color:#fecaca}}
.purchase-id-advice{{font-size:0.88rem;line-height:1.45;color:#fecaca;margin:0.5rem 0 0}}
/* KEYGEN: large bold bright white, under ready lines */
.keygen-box{{max-width:36rem;margin:1.1rem auto 1.25rem;padding:1.1rem 1.2rem;text-align:center;
background:rgba(15,40,80,0.55);border:1px solid rgba(174,208,234,0.4);border-radius:14px;
box-shadow:inset 0 1px 0 rgba(255,255,255,0.08)}}
.keygen-heading-label{{margin:0 0 0.65rem;color:#ffffff;font-size:0.95rem}}
.keygen-value{{margin:0.5rem 0 0.85rem}}
.product-keygen-display,#product-keygen{{
  display:inline-block;font-size:clamp(1.35rem,4.5vw,1.95rem);font-weight:800;
  letter-spacing:0.06em;line-height:1.3;color:#ffffff!important;
  background:rgba(0,0,0,0.25);padding:0.45rem 0.75rem;border-radius:10px;
  word-break:break-all;text-shadow:0 1px 0 rgba(0,0,0,0.35)}}
.keygen-copy-row{{margin:0.35rem 0 0.65rem;display:flex;flex-wrap:wrap;gap:0.5rem;
justify-content:center;align-items:center}}
.keygen-copy-btn{{cursor:pointer;border:0;border-radius:10px;padding:0.55rem 1.1rem;
font-weight:700;font-size:0.95rem;background:#2563eb;color:#fff;font-family:inherit}}
.keygen-copy-btn:hover{{background:#3b82f6}}
.keygen-copy-status{{font-size:0.88rem;color:#86efac;font-weight:600;min-height:1.2em}}
.keygen-advice{{font-size:0.88rem;line-height:1.45;color:#dbeafe;margin:0.5rem 0 0;text-align:left}}
a.dl{{display:inline-block;margin:0.75rem 0;padding:0.85rem 1.4rem;background:#1d4ed8;
color:#fff;text-decoration:none;border-radius:10px;font-weight:700;font-size:1rem}}
a.dl:hover{{background:#2563eb}}
.muted{{opacity:0.85;font-size:0.9rem;color:#e8eef5}}
</style></head><body>
{body_inner}
</body></html>
""".encode("utf-8")


class Handler(BaseHTTPRequestHandler):
    def log_message(self, format, *args):  # noqa: A003
        # No access / user-info logs
        return

    def _security_headers(self, *, allow_framing: bool = False) -> None:
        try:
            from security_headers import apply_security_headers
        except ImportError:  # pragma: no cover
            from status_page.security_headers import (  # type: ignore
                apply_security_headers,
            )
        apply_security_headers(self, allow_framing=allow_framing)

    def _send(
        self,
        code: int,
        content_type: str,
        data: bytes,
        *,
        extra_headers: list[tuple[str, str]] | None = None,
        allow_framing: bool = False,
    ) -> None:
        self.send_response(code)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(data)))
        self.send_header("Cache-Control", "no-store")
        self._security_headers(allow_framing=allow_framing)
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
        self._security_headers()
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
        # Product family: paths /browser /vault; optional Host browser.* / vault.*
        try:
            from product_family import (
                product_key_from_host,
                render_browser_page_html,
                render_vault_page_html,
            )
        except ImportError:  # pragma: no cover
            from status_page.product_family import (  # type: ignore
                product_key_from_host,
                render_browser_page_html,
                render_vault_page_html,
            )
        host_product = product_key_from_host((self.headers.get("Host") or "").strip())
        if host_product == "browser" and path in (
            "/",
            "/index.html",
            "/browser",
            "/browser/",
        ):
            self._send(200, "text/html; charset=utf-8", render_browser_page_html())
            return
        if host_product == "vault" and path in (
            "/",
            "/index.html",
            "/vault",
            "/vault/",
        ):
            self._send(200, "text/html; charset=utf-8", render_vault_page_html())
            return
        if path in ("/browser", "/browser/"):
            self._send(200, "text/html; charset=utf-8", render_browser_page_html())
            return
        if path in ("/vault", "/vault/"):
            self._send(200, "text/html; charset=utf-8", render_vault_page_html())
            return
        if path in ("/", "/index.html"):
            try:
                from local_currency import (
                    accept_language_from_request,
                    country_headers_from_request,
                )
            except ImportError:  # pragma: no cover
                from status_page.local_currency import (  # type: ignore
                    accept_language_from_request,
                    country_headers_from_request,
                )

            hdrs = {k: v for k, v in self.headers.items()}
            # Optional ?currency=EUR override for testing presentment display
            q_ccy = (query.get("currency") or "").strip()
            q_plat = (query.get("platform") or "").strip()
            q_iv = (query.get("interval") or "month").strip()
            q_err = (query.get("pay_error") or query.get("error") or "").strip()
            self._send(
                200,
                "text/html; charset=utf-8",
                render_html(
                    fetch_upstream_status(),
                    accept_language=accept_language_from_request(hdrs),
                    country=country_headers_from_request(hdrs),
                    currency=q_ccy,
                    default_platform=q_plat,
                    default_interval=q_iv,
                    pay_error=q_err,
                ),
            )
            return
        if path in ("/pay/start", "/pay/usd"):
            # USD presentment start: USD Payment Link or Checkout Session in USD
            from payments import (
                BILLING_INTERVAL_MONTH,
                BILLING_INTERVAL_YEAR,
                public_base_url,
                resolve_usd_pay_redirect_url,
                stripe_payment_page_href_for_platform,
            )

            plat = (query.get("platform") or "windows").strip().lower()
            iv = (query.get("interval") or BILLING_INTERVAL_MONTH).strip().lower()
            if iv in ("year", "yearly", "annual", "annually"):
                iv = BILLING_INTERVAL_YEAR
            else:
                iv = BILLING_INTERVAL_MONTH
            ccy = (query.get("currency") or "usd").strip().lower()
            if ccy != "usd":
                # Non-USD: Adaptive Pricing path on GBP Payment Link
                self._redirect(
                    stripe_payment_page_href_for_platform(
                        plat, interval=iv, currency=ccy
                    )
                )
                return
            try:
                dest = resolve_usd_pay_redirect_url(
                    plat,
                    interval=iv,
                    base_url=public_base_url(),
                )
            except ValueError as exc:
                # No USD Payment Link and Checkout create failed (missing secret).
                # Do not silently send visitors to the GBP Payment Link as "USD".
                msg = (
                    "USD pay unavailable: set STRIPE_PAYMENT_PAGE_URL_USD "
                    f"(and yearly USD if needed) or STRIPE_SECRET_KEY. ({exc})"
                ).encode("utf-8")
                self._send(503, "text/plain; charset=utf-8", msg)
                return
            self._redirect(dest)
            return
        if path in settings_explainer_paths():
            self._send(
                200,
                "text/html; charset=utf-8",
                render_settings_explainer_page_html(),
            )
            return
        # Public media kit (logos/favicons) — no admin auth
        if path in (
            "/media-kit/restore-privacy-media-kit.zip",
            "/media-kit/",
            "/media-kit",
        ):
            try:
                from media_kit import (  # type: ignore
                    KIT_FILENAME,
                    media_kit_file_path,
                )
            except ImportError:  # pragma: no cover
                from status_page.media_kit import (  # type: ignore
                    KIT_FILENAME,
                    media_kit_file_path,
                )
            if path in ("/media-kit", "/media-kit/"):
                self._redirect("/media-kit/restore-privacy-media-kit.zip")
                return
            kit_path = media_kit_file_path()
            data = kit_path.read_bytes()
            self.send_response(200)
            self.send_header("Content-Type", "application/zip")
            self.send_header("Content-Length", str(len(data)))
            self.send_header(
                "Content-Disposition",
                f'attachment; filename="{KIT_FILENAME}"',
            )
            self.send_header("Cache-Control", "public, max-age=3600")
            self._security_headers()
            self.end_headers()
            self.wfile.write(data)
            return
        static = read_static_bytes(path)
        if static is not None:
            data, ctype = static
            self.send_response(200)
            self.send_header("Content-Type", ctype)
            self.send_header("Content-Length", str(len(data)))
            self.send_header("Cache-Control", "public, max-age=3600")
            self._security_headers()
            self.end_headers()
            self.wfile.write(data)
            return
        if path in ("/api/status", "/status"):
            status = fetch_upstream_status()
            safe = public_status_payload(status)
            self._send(200, "application/json", json.dumps(safe).encode("utf-8"))
            return
        if path in ("/api/catalog-version", "/catalog-version"):
            # Public monopin for in-app "new version available" (not a client count).
            try:
                from downloads import current_catalog_version
            except ImportError:  # pragma: no cover
                from status_page.downloads import current_catalog_version  # type: ignore
            try:
                from payments import DEFAULT_PRODUCTION_PUBLIC_BASE_URL
            except ImportError:  # pragma: no cover
                DEFAULT_PRODUCTION_PUBLIC_BASE_URL = "https://restoreprivacy.online"
            ver = current_catalog_version()
            payload = {
                "catalog_version": ver,
                "downloads_url": f"{DEFAULT_PRODUCTION_PUBLIC_BASE_URL.rstrip('/')}/#downloads",
            }
            self._send(
                200,
                "application/json; charset=utf-8",
                json.dumps(payload).encode("utf-8"),
                extra_headers=[("Cache-Control", "public, max-age=300")],
            )
            return
        if path in ("/health", "/healthz"):
            self._send(200, "application/json", b'{"ok":true}')
            return
        if path in ("/health/fulfilment", "/api/fulfilment-ready"):
            # Production readiness: can the host open a catalog installer?
            # Optional ?platform=macos pins the live-test package probe.
            # Optional ?smtp_probe=1 attempts SMTP login (no message sent).
            plat = (query.get("platform") or "").strip() or None
            smtp_probe = (query.get("smtp_probe") or "").strip().lower() in (
                "1",
                "true",
                "yes",
                "on",
            )
            payload = check_fulfilment_ready(platform=plat, smtp_probe=smtp_probe)
            code = 200 if payload.get("ok") else 503
            self._send(
                code,
                "application/json",
                json.dumps(payload).encode("utf-8"),
            )
            return

        if path in ("/api/connect-entitlement", "/connect-entitlement"):
            # Payment entitlement for Connect gate (session_id and/or keygen)
            session_id = (query.get("session_id") or "").strip()
            keygen = (query.get("keygen") or "").strip()
            ent = None
            if keygen:
                from payments import get_connect_entitlement_by_keygen

                ent = get_connect_entitlement_by_keygen(keygen)
            elif session_id:
                ent = get_connect_entitlement(session_id)
            else:
                self._send(
                    400,
                    "application/json",
                    json.dumps(
                        {
                            "status": "unknown",
                            "connect_allowed": False,
                            "error": "missing_session_id_or_keygen",
                        }
                    ).encode("utf-8"),
                )
                return
            if not ent:
                payload = {
                    "session_id": session_id or "",
                    "keygen": keygen or "",
                    "status": "unknown",
                    "connect_allowed": False,
                    "reason": "no_entitlement",
                }
            else:
                from payments import licence_status_from_entitlement

                lic = str(
                    ent.get("licence_status")
                    or licence_status_from_entitlement(ent)
                )
                plat = str(ent.get("platform") or "")
                payload = {
                    "session_id": ent["session_id"],
                    "status": ent["status"],
                    "licence_status": lic,
                    "platform": plat,
                    "reason": ent.get("reason") or "",
                    "connect_allowed": bool(ent.get("connect_allowed")),
                    "valid_until": ent.get("valid_until"),
                    "keygen": ent.get("keygen") or "",
                    "customer_email": ent.get("customer_email") or "",
                    "billing_interval": ent.get("billing_interval") or "month",
                    # Device-licence pay host (never localhost public_base_url).
                    "renew_url": _device_licence_renew_url(
                        plat or "windows", interval="month"
                    ),
                    "renew_url_monthly": _device_licence_renew_url(
                        plat or "windows", interval="month"
                    ),
                    "renew_url_yearly": _device_licence_renew_url(
                        plat or "windows", interval="year"
                    ),
                }
            self._send(
                200,
                "application/json",
                json.dumps(payload).encode("utf-8"),
            )
            return

        if path in ("/api/device-entitlement", "/device-entitlement"):
            # Node residual HELLO gate — device Ed25519 pub must be bound to paid session
            from payments import get_device_entitlement

            device_pub = (query.get("device_pub") or query.get("device_pub_hex") or "").strip()
            payload = get_device_entitlement(device_pub)
            code = 200 if not payload.get("error") else 400
            self._send(code, "application/json", json.dumps(payload).encode("utf-8"))
            return

        if path in (
            "/api/connect-entitlement-file",
            "/connect-entitlement-file",
        ):
            # Downloadable payment_entitlement.json for the desktop/mobile app
            from payments import client_entitlement_file_payload

            session_id = (query.get("session_id") or "").strip()
            if not session_id:
                self._send(
                    400,
                    "application/json",
                    json.dumps({"error": "missing_session_id"}).encode("utf-8"),
                )
                return
            payload = client_entitlement_file_payload(session_id)
            if not payload:
                self._send(
                    404,
                    "application/json",
                    json.dumps(
                        {
                            "error": "no_entitlement",
                            "session_id": session_id,
                        }
                    ).encode("utf-8"),
                )
                return
            body = (json.dumps(payload, indent=2) + "\n").encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header(
                "Content-Disposition",
                'attachment; filename="payment_entitlement.json"',
            )
            self.send_header("Content-Length", str(len(body)))
            self.send_header("Cache-Control", "no-store")
            # Same-origin iframe on thank-you must be allowed to load this file.
            self._security_headers(allow_framing=True)
            self.end_headers()
            self.wfile.write(body)
            return

        # --- Paid download flow: site-hosted Select your plan page ---
        if path == "/pay":
            platform = (query.get("platform") or "").strip().lower()
            interval = (query.get("interval") or "month").strip().lower()
            err = (query.get("error") or "").strip()
            # Allow empty platform (picker on page); invalid platform still shows page
            if platform and not platform_filename(platform):
                self._send(
                    200,
                    "text/html; charset=utf-8",
                    render_pay_plan_page_html(
                        "",
                        interval=interval,
                        error="Unknown package — choose a platform below.",
                    ),
                )
                return
            self._send(
                200,
                "text/html; charset=utf-8",
                render_pay_plan_page_html(
                    platform, interval=interval, error=err
                ),
            )
            return

        if path == "/download":
            token = (query.get("token") or "").strip()
            # Lookup without consuming so proxy failure does not burn the grant.
            # Filename is taken only from the paid grant row — never from query string.
            grant = lookup_download_token(token) if token else None
            # Always current-catalog filename (lookup rebinds platform → live pin)
            fname = None
            if grant:
                from payments import grant_delivery_filename, _safe_catalog_filename

                fname = grant_delivery_filename(
                    platform=str(grant.get("platform") or ""),
                    stored_filename=str(
                        grant.get("filename") or grant.get("stored_filename") or ""
                    ),
                )
                fname = _safe_catalog_filename(str(fname or "")) or None
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
            # Prefer browser→Helsinki host delivery (short-lived signed URL) so
            # multi-MB installers are not double-proxied through Render.
            # Probe Helsinki first; on failure fall through to open_release_asset.
            #
            # **Do not consume the grant on 302.** Thank-you loads the same
            # ``/download?token=`` in a hidden iframe and a manual fallback; the
            # contract is consume only after a successful full stream (proxy path)
            # so a blocked iframe / mid-transfer drop leaves the manual link usable.
            # Host 302 is not a completed transfer — grant stays for retry until TTL.
            try:
                from host_delivery import host_delivery_plan  # type: ignore
            except Exception:  # noqa: BLE001
                try:
                    from status_page.host_delivery import host_delivery_plan  # type: ignore
                except Exception:  # noqa: BLE001
                    host_delivery_plan = None  # type: ignore
            if host_delivery_plan is not None:
                plan = host_delivery_plan(str(fname), probe=True)
                if plan and plan.get("url"):
                    # Still unused at redirect time (no consume yet)
                    if lookup_download_token(token) is None:
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
                    self.send_response(302)
                    self.send_header("Location", str(plan["url"]))
                    self.send_header("Cache-Control", "no-store")
                    self.send_header(
                        "X-RPT-Fulfilment",
                        str(plan.get("source") or "helsinki_host"),
                    )
                    self.send_header("Content-Length", "0")
                    # Framing OK for thank-you auto-download iframe → redirect.
                    self._security_headers(allow_framing=True)
                    self.end_headers()
                    return
            # Paid proxy: stream installer from local/API (works when repo is private).
            # Do NOT redirect unpaid browsers to free public github.com/releases/download.
            # open_release_asset must never be called without a validated paid grant.
            #
            # **Consume only after a successful full stream to the client.**
            # Burning the grant when the source merely opens (old behaviour) left
            # users with 403 on the manual thank-you link when: the auto-download
            # iframe opened then failed mid-transfer (VPS ConnectionReset / proxy
            # timeout), or the browser blocked the iframe attachment and the user
            # clicked the fallback once.
            asset = open_release_asset(str(fname))
            if asset is None:
                self._send(
                    502,
                    "text/html; charset=utf-8",
                    _html_page(
                        "Fulfilment error",
                        '<p class="msg" id="download-fulfil-failed">Paid download could not be fetched. '
                        "Operators: confirm Helsinki paid-assets (RPT_ASSET_FETCH_TOKEN match + "
                        "rpt-paid-assets.service) or stage status_page/assets/{version}/.</p>"
                        '<p><a href="/">Home</a></p>',
                    ),
                )
                return
            # Still valid + unused at send time (no consume yet)
            if lookup_download_token(token) is None:
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
            stream_ok = False
            try:
                self.send_response(200)
                self.send_header("Content-Type", ctype)
                self.send_header("Content-Disposition", disp)
                self.send_header("Cache-Control", "no-store")
                self.send_header("X-RPT-Fulfilment", str(asset.get("source") or "proxy"))
                if length is not None:
                    self.send_header("Content-Length", str(int(length)))
                # Omit X-Frame-Options DENY so thank-you auto-download iframe works.
                self._security_headers(allow_framing=True)
                self.end_headers()
                # Larger chunks + early flush so browsers show progress sooner
                # (avoids feeling "stuck" on multi‑MB installers).
                _chunk = 256 * 1024
                if isinstance(body, (bytes, bytearray)):
                    self.wfile.write(body)
                    try:
                        self.wfile.flush()
                    except Exception:  # noqa: BLE001
                        pass
                    stream_ok = True
                else:
                    try:
                        first = True
                        while True:
                            chunk = body.read(_chunk)
                            if not chunk:
                                break
                            self.wfile.write(chunk)
                            if first:
                                first = False
                                try:
                                    self.wfile.flush()
                                except Exception:  # noqa: BLE001
                                    pass
                        stream_ok = True
                    finally:
                        try:
                            body.close()
                        except Exception:  # noqa: BLE001
                            pass
            except (BrokenPipeError, ConnectionResetError, ConnectionAbortedError):
                # Client/proxy dropped mid-transfer — leave grant unused for retry.
                try:
                    if hasattr(body, "close"):
                        body.close()
                except Exception:  # noqa: BLE001
                    pass
                stream_ok = False
            except Exception:  # noqa: BLE001
                try:
                    if hasattr(body, "close"):
                        body.close()
                except Exception:  # noqa: BLE001
                    pass
                raise
            if stream_ok:
                # Single-use starts only after the browser received the full body.
                consume_download_token(token)
            return

        if path in ("/download/success", "/pay/success"):
            token = (query.get("token") or "").strip()
            platform = (query.get("platform") or "").strip().lower()
            session_id = (query.get("session_id") or "").strip()
            # Stripe Payment Link after_completion only expands {CHECKOUT_SESSION_ID}.
            # It cannot fill platform= — that comes from client_reference_id on the
            # BUY tile URL. If the operator left empty &platform= on the redirect
            # template, resolve platform from Stripe and canonicalise the URL.
            if session_id and not platform and not token:
                try:
                    from payments import resolve_platform_from_checkout_session

                    resolved = resolve_platform_from_checkout_session(session_id)
                except Exception:  # noqa: BLE001
                    resolved = ""
                if resolved and platform_filename(resolved):
                    q = urllib.parse.urlencode(
                        {"session_id": session_id, "platform": resolved}
                    )
                    self._redirect(f"/download/success?{q}")
                    return
            # Stripe success_url supplies session_id={CHECKOUT_SESSION_ID}; webhook
            # may still be in-flight — poll briefly for the minted grant.
            # Security: never invent a download link for an unverified token —
            # only a DB grant (paid webhook **or** Stripe-verified recovery mint)
            # may unlock the thank-you download UI.
            grant = None
            if token:
                grant = lookup_download_token(token)
            elif session_id:
                # Payment Link after_payment redirect lands here; webhook may lag
                # on free-tier cold start — wait longer than a local unit test.
                # Short poll for webhook, then Stripe recovery (avoid long blank wait).
                grant = wait_for_grant_by_session(session_id, timeout_sec=3.0)
                if grant is None:
                    grant = find_grant_by_session(session_id)
                # Recovery: verify payment with Stripe API and mint if webhook missed
                if grant is None:
                    try:
                        from payments import ensure_download_grant_for_paid_session

                        grant = ensure_download_grant_for_paid_session(
                            session_id, platform_hint=platform
                        )
                    except Exception:  # noqa: BLE001
                        grant = None
            if grant and grant.get("token"):
                tok = str(grant["token"])
                link = grant.get("download_path") or (
                    f"/download?token={urllib.parse.quote(tok)}"
                )
                # Never trust client-supplied filename — use grant / catalog only
                fname = (
                    grant.get("filename")
                    or platform_filename(str(grant.get("platform") or platform))
                    or platform
                    or "package"
                )
                plat = str(grant.get("platform") or platform or "")
                # Ensure Connect entitlement + keygen for this paid session
                thankyou_keygen = ""
                ent_sid = session_id or str(grant.get("session_id") or "")
                if ent_sid:
                    thankyou_keygen = (
                        activate_connect_entitlement(ent_sid, platform=plat) or ""
                    )
                purchase_id = str(grant.get("purchase_id") or "")
                if not purchase_id and grant.get("token"):
                    try:
                        from payments import purchase_id_for_token

                        purchase_id = purchase_id_for_token(str(grant["token"])) or ""
                    except Exception:  # noqa: BLE001
                        purchase_id = ""
                # Canonical browser URL: include platform when grant has it but query did not
                if session_id and plat and not platform:
                    q = urllib.parse.urlencode(
                        {"session_id": session_id, "platform": plat}
                    )
                    self._redirect(f"/download/success?{q}")
                    return
                inner = render_post_payment_thankyou_html(
                    download_path=str(link),
                    filename=str(fname),
                    platform=plat,
                    session_id=session_id or str(grant.get("session_id") or ""),
                    purchase_id=purchase_id,
                    keygen=thankyou_keygen,
                )
            else:
                # Meta-refresh so a late webhook can still unlock the page
                refresh = ""
                if session_id:
                    q = urllib.parse.urlencode(
                        {"session_id": session_id, "platform": platform}
                    )
                    refresh = (
                        f'<meta http-equiv="refresh" content="4;url=/download/success?{q}"/>'
                    )
                deny_note = ""
                if token and not session_id:
                    deny_note = (
                        '<p class="msg" id="pay-success-invalid-token">'
                        "That download link is invalid, expired, or already used. "
                        "Complete payment again to get a new link.</p>"
                    )
                # Paid session but no platform on Payment Link → pick package once
                picker = ""
                if session_id and not platform:
                    try:
                        from payments import paid_session_needs_platform_picker
                        from downloads import CATALOG_PLATFORMS

                        if paid_session_needs_platform_picker(session_id):
                            _titles = {
                                "windows": "Windows",
                                "android": "Android",
                                "macos": "macOS",
                                "ios": "iOS",
                                "linux": "Linux",
                            }
                            opts = "".join(
                                f'<option value="{_escape_html(p)}">'
                                f"{_escape_html(_titles.get(p, p))}"
                                f"</option>"
                                for p in CATALOG_PLATFORMS
                            )
                            picker = (
                                '<div class="msg" id="pay-success-platform-picker">'
                                "<p><strong>Payment received.</strong> Choose your device "
                                "package to finish the download:</p>"
                                f'<form method="get" action="/download/success" '
                                f'id="platform-pick-form">'
                                f'<input type="hidden" name="session_id" '
                                f'value="{_escape_html(session_id)}"/>'
                                f'<select name="platform" id="platform-pick" required>'
                                f'<option value="" disabled selected>Select platform…'
                                f"</option>{opts}</select> "
                                f'<button type="submit" id="platform-pick-submit">'
                                f"Get installer</button></form></div>"
                            )
                            refresh = ""  # stop spinning refresh while picker is shown
                    except Exception:  # noqa: BLE001
                        picker = ""
                plat_bit = (
                    f" for {_escape_html(platform)}" if platform else ""
                )
                inner = (
                    f"{refresh}"
                    f"{deny_note}"
                    f"{picker}"
                    f'<p class="msg" id="pay-success-pending">Payment submitted{plat_bit}.</p>'
                    f'<p class="msg" id="pay-success-packaging">'
                    f"please wait for your download.. packaging...</p>"
                    f'<p class="msg muted" id="pay-success-wait-hint">'
                    f"Preparing your installer — this page refreshes automatically.</p>"
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
            from admin_panel import render_admin_home_html

            self._send(200, "text/html; charset=utf-8", render_admin_home_html())
            return
        if path in ("/admin/link-generation", "/admin/link-generation/"):
            if not admin_enabled():
                self._send(503, "text/plain; charset=utf-8", b"admin disabled")
                return
            if not is_authenticated(self.headers):
                self._send(200, "text/html; charset=utf-8", render_login_html())
                return
            from admin_panel import render_admin_link_generation_html

            self._send(
                200, "text/html; charset=utf-8", render_admin_link_generation_html()
            )
            return
        if path in ("/admin/licences", "/admin/licences/", "/admin/active-licences", "/admin/active-licences/"):
            if not admin_enabled():
                self._send(503, "text/plain; charset=utf-8", b"admin disabled")
                return
            if not is_authenticated(self.headers):
                self._send(200, "text/html; charset=utf-8", render_login_html())
                return
            from admin_panel import render_admin_licences_page_html

            self._send(
                200, "text/html; charset=utf-8", render_admin_licences_page_html()
            )
            return
        if path in ("/admin/processors", "/admin/processors/"):
            if not admin_enabled():
                self._send(503, "text/plain; charset=utf-8", b"admin disabled")
                return
            if not is_authenticated(self.headers):
                self._send(200, "text/html; charset=utf-8", render_login_html())
                return
            from admin_panel import render_admin_processors_page_html

            self._send(
                200, "text/html; charset=utf-8", render_admin_processors_page_html()
            )
            return
        if path in ("/admin/accounting", "/admin/accounting/"):
            if not admin_enabled():
                self._send(503, "text/plain; charset=utf-8", b"admin disabled")
                return
            if not is_authenticated(self.headers):
                self._send(200, "text/html; charset=utf-8", render_login_html())
                return
            from admin_panel import render_admin_accounting_page_html

            self._send(
                200,
                "text/html; charset=utf-8",
                render_admin_accounting_page_html(),
            )
            return
        if path in ("/admin/accounting/export", "/admin/accounting/export/"):
            if not admin_enabled():
                self._send(503, "text/plain; charset=utf-8", b"admin disabled")
                return
            if not is_authenticated(self.headers):
                self._send(200, "text/html; charset=utf-8", render_login_html())
                return
            from accounting import (
                build_ledger_from_payment_store,
                export_ledger,
                filter_ledger_by_period,
                parse_export_period,
            )

            q = urllib.parse.parse_qs(parsed.query)
            form = {k: (v[0] if v else "") for k, v in q.items()}
            period = parse_export_period(form)
            fmt = (form.get("format") or "xlsx").strip().lower()
            full = build_ledger_from_payment_store()
            filtered = filter_ledger_by_period(full, **period["filter"])
            body, content_type, ext = export_ledger(filtered, fmt=fmt)
            fname = f"raskul_ltd_accounts_{period['stem']}.{ext}"
            self.send_response(200)
            self.send_header("Content-Type", content_type)
            self.send_header(
                "Content-Disposition", f'attachment; filename="{fname}"'
            )
            self.send_header("Content-Length", str(len(body)))
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            self.wfile.write(body)
            return
        if path in ("/admin/fleet", "/admin/fleet/"):
            if not admin_enabled():
                self._send(503, "text/plain; charset=utf-8", b"admin disabled")
                return
            if not is_authenticated(self.headers):
                self._send(200, "text/html; charset=utf-8", render_login_html())
                return
            from admin_panel import render_admin_fleet_page_html

            self._send(200, "text/html; charset=utf-8", render_admin_fleet_page_html())
            return
        if path in ("/admin/api/fleet-usage", "/admin/api/fleet-usage/"):
            # Authenticated JSON for live fleet usage table refresh (admin only).
            if not admin_enabled():
                self._send(
                    503,
                    "application/json; charset=utf-8",
                    b'{"error":"admin disabled"}',
                )
                return
            if not is_authenticated(self.headers):
                self._send(
                    401,
                    "application/json; charset=utf-8",
                    b'{"error":"unauthorized"}',
                )
                return
            try:
                from admin_node_usage import fleet_usage_json_payload
            except ImportError:
                from status_page.admin_node_usage import (  # type: ignore
                    fleet_usage_json_payload,
                )
            try:
                payload = fleet_usage_json_payload(live=True)
            except Exception as exc:  # noqa: BLE001
                payload = {
                    "error": str(exc)[:200],
                    "refreshed_at": None,
                    "rows": [],
                }
            body = json.dumps(payload, separators=(",", ":")).encode("utf-8")
            self._send(
                200,
                "application/json; charset=utf-8",
                body,
                extra_headers=[
                    ("Cache-Control", "no-store"),
                ],
            )
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
                        format_session_cookie("", clear=True),
                    ),
                    (
                        "Set-Cookie",
                        format_session_cookie(
                            "", clear=True, cookie_name=PENDING_COOKIE
                        ),
                    ),
                    ("Location", "/admin/login"),
                ],
            )
            return
        if path in ("/admin/2fa/setup", "/admin/2fa/setup/"):
            # GET: show enrollment when pending setup cookie present
            if not admin_enabled():
                self._send(503, "text/plain; charset=utf-8", b"admin disabled")
                return
            if is_authenticated(self.headers):
                self._redirect("/admin")
                return
            pending = pending_from_headers(self.headers)
            info = verify_pending_token(pending, expect_stage="setup")
            if not info or not info.get("secret_b32"):
                self._send(
                    200,
                    "text/html; charset=utf-8",
                    render_login_html(
                        error="Authenticator setup expired — sign in with password again."
                    ),
                )
                return
            secret = str(info["secret_b32"])
            self._send(
                200,
                "text/html; charset=utf-8",
                render_2fa_setup_html(
                    secret_b32=secret,
                    otpauth=otpauth_uri(secret),
                ),
            )
            return
        if path in ("/admin/2fa/verify", "/admin/2fa/verify/"):
            if not admin_enabled():
                self._send(503, "text/plain; charset=utf-8", b"admin disabled")
                return
            if is_authenticated(self.headers):
                self._redirect("/admin")
                return
            pending = pending_from_headers(self.headers)
            info = verify_pending_token(pending, expect_stage="verify")
            if not info:
                self._send(
                    200,
                    "text/html; charset=utf-8",
                    render_login_html(
                        error="Authenticator step expired — sign in with password again."
                    ),
                )
                return
            self._send(200, "text/html; charset=utf-8", render_2fa_verify_html())
            return

        self._send(404, "text/plain; charset=utf-8", b"not found")

    def do_POST(self):  # noqa: N802
        path, _query = _parse_query(self.path)
        body = self._read_body()

        if path == "/pay/checkout":
            # Site plan form: platform + interval + auto_renew → subscription Checkout
            ctype = (self.headers.get("Content-Type") or "").lower()
            platform = ""
            interval = "month"
            auto_renew = True
            if "application/json" in ctype:
                try:
                    data = json.loads(body.decode("utf-8") or "{}")
                except json.JSONDecodeError:
                    data = {}
                if isinstance(data, dict):
                    platform = str(data.get("platform") or "").strip()
                    interval = str(data.get("interval") or "month").strip()
                    if "auto_renew" in data:
                        from payments import parse_auto_renew_choice

                        auto_renew = parse_auto_renew_choice(data.get("auto_renew"))
            else:
                form = urllib.parse.parse_qs(body.decode("utf-8", errors="replace"))
                platform = (form.get("platform") or [""])[0].strip()
                interval = (form.get("interval") or ["month"])[0].strip()
                from payments import parse_auto_renew_form_values

                auto_renew = parse_auto_renew_form_values(form.get("auto_renew"))
            if not platform or not platform_filename(platform):
                q = urllib.parse.urlencode(
                    {
                        "pay_error": "Please select your device platform.",
                        "interval": interval or "month",
                    }
                )
                self._redirect(f"/?{q}#downloads")
                return
            if not stripe_configured():
                q = urllib.parse.urlencode(
                    {
                        "platform": platform,
                        "interval": interval or "month",
                        "pay_error": (
                            "Checkout is temporarily unavailable "
                            "(payments not configured)."
                        ),
                    }
                )
                self._redirect(f"/?{q}#downloads")
                return
            try:
                session = create_subscription_checkout_session(
                    platform, interval=interval, auto_renew=auto_renew
                )
            except ValueError as e:
                q = urllib.parse.urlencode(
                    {
                        "platform": platform,
                        "interval": interval or "month",
                        "pay_error": f"Could not start checkout: {e}",
                    }
                )
                self._redirect(f"/?{q}#downloads")
                return
            self._redirect(str(session["url"]))
            return

        if path == "/api/checkout":
            try:
                data = json.loads(body.decode("utf-8") or "{}")
            except json.JSONDecodeError:
                self._send(400, "application/json", b'{"error":"bad_json"}')
                return
            platform = str(data.get("platform") or "").strip()
            interval = str(data.get("interval") or "month").strip()
            from payments import parse_auto_renew_choice

            auto_renew = parse_auto_renew_choice(
                data.get("auto_renew") if isinstance(data, dict) else True
            )
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
                session = create_checkout_session(
                    platform, interval=interval, auto_renew=auto_renew
                )
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
                        "billing_interval": session.get("billing_interval"),
                        "product_name": session.get("product_name"),
                        "auto_renew": session.get("auto_renew", auto_renew),
                    }
                ).encode("utf-8"),
            )
            return

        if path in ("/api/bind-device-entitlement", "/bind-device-entitlement"):
            # Client auto-bind after pay: JSON {session_id, device_pub}
            from payments import bind_device_entitlement

            try:
                data = json.loads(body.decode("utf-8") or "{}")
            except json.JSONDecodeError:
                self._send(
                    400,
                    "application/json",
                    json.dumps({"ok": False, "error": "bad_json"}).encode("utf-8"),
                )
                return
            if not isinstance(data, dict):
                data = {}
            result = bind_device_entitlement(
                str(data.get("session_id") or ""),
                str(data.get("device_pub") or data.get("device_pub_hex") or ""),
            )
            code = 200 if result.get("ok") else 403
            self._send(code, "application/json", json.dumps(result).encode("utf-8"))
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
            totp_code = (form.get("totp_code") or form.get("code") or "").strip()
            if not verify_credentials(user, password):
                self._send(
                    401,
                    "text/html; charset=utf-8",
                    render_login_html(error="Invalid credentials"),
                )
                return
            # Enrolled: password + 6-digit TOTP on this same form → full session
            if is_totp_enrolled():
                secret = get_enrolled_secret()
                if not secret or not verify_totp(secret, totp_code):
                    self._send(
                        401,
                        "text/html; charset=utf-8",
                        render_login_html(error="Invalid credentials"),
                    )
                    return
                token = mint_session_token()
                self.send_response(302)
                self.send_header("Location", "/admin")
                self.send_header("Set-Cookie", format_session_cookie(token))
                self.send_header(
                    "Set-Cookie",
                    format_session_cookie(
                        "", clear=True, cookie_name=PENDING_COOKIE
                    ),
                )
                self.send_header("Content-Length", "0")
                self.send_header("Cache-Control", "no-store")
                self._security_headers()
                self.end_headers()
                return
            # Not enrolled yet: after password only → bare setup (QR + code)
            step = begin_login_after_password()
            pending = str(step["pending_token"])
            secret = str(step.get("secret_b32") or "")
            self._send(
                200,
                "text/html; charset=utf-8",
                render_2fa_setup_html(
                    secret_b32=secret,
                    otpauth=otpauth_uri(secret) if secret else "",
                ),
                extra_headers=[
                    (
                        "Set-Cookie",
                        format_session_cookie(
                            pending,
                            max_age=PENDING_TTL_SEC,
                            cookie_name=PENDING_COOKIE,
                        ),
                    ),
                    (
                        "Set-Cookie",
                        format_session_cookie("", clear=True),
                    ),
                ],
            )
            return

        if path in ("/admin/2fa/setup", "/admin/2fa/setup/"):
            if not admin_enabled():
                self._send(503, "text/plain; charset=utf-8", b"admin disabled")
                return
            pending = pending_from_headers(self.headers)
            form = dict(urllib.parse.parse_qsl(body.decode("utf-8", "replace")))
            code = (form.get("totp_code") or form.get("code") or "").strip()
            info = verify_pending_token(pending, expect_stage="setup")
            secret_for_retry = (
                str(info.get("secret_b32") or "") if info else ""
            )
            try:
                complete_setup(pending, code)
            except ValueError as exc:
                if secret_for_retry:
                    self._send(
                        401,
                        "text/html; charset=utf-8",
                        render_2fa_setup_html(
                            secret_b32=secret_for_retry,
                            otpauth=otpauth_uri(secret_for_retry),
                            error=str(exc),
                        ),
                    )
                else:
                    self._send(
                        401,
                        "text/html; charset=utf-8",
                        render_login_html(error=str(exc)),
                    )
                return
            token = mint_session_token()
            self.send_response(302)
            self.send_header("Location", "/admin")
            self.send_header(
                "Set-Cookie",
                format_session_cookie(token),
            )
            self.send_header(
                "Set-Cookie",
                format_session_cookie(
                    "", clear=True, cookie_name=PENDING_COOKIE
                ),
            )
            self.send_header("Content-Length", "0")
            self.send_header("Cache-Control", "no-store")
            self._security_headers()
            self.end_headers()
            return

        if path in ("/admin/2fa/verify", "/admin/2fa/verify/"):
            if not admin_enabled():
                self._send(503, "text/plain; charset=utf-8", b"admin disabled")
                return
            pending = pending_from_headers(self.headers)
            form = dict(urllib.parse.parse_qsl(body.decode("utf-8", "replace")))
            code = (form.get("totp_code") or form.get("code") or "").strip()
            try:
                complete_verify(pending, code)
            except ValueError as exc:
                self._send(
                    401,
                    "text/html; charset=utf-8",
                    render_2fa_verify_html(error=str(exc)),
                )
                return
            token = mint_session_token()
            self.send_response(302)
            self.send_header("Location", "/admin")
            self.send_header(
                "Set-Cookie",
                format_session_cookie(token),
            )
            self.send_header(
                "Set-Cookie",
                format_session_cookie(
                    "", clear=True, cookie_name=PENDING_COOKIE
                ),
            )
            self.send_header("Content-Length", "0")
            self.send_header("Cache-Control", "no-store")
            self._security_headers()
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

        if path in ("/admin/reissue-download", "/admin/reissue-download/"):
            if not admin_enabled():
                self._send(503, "text/plain; charset=utf-8", b"admin disabled")
                return
            if not is_authenticated(self.headers):
                self._send(200, "text/html; charset=utf-8", render_login_html())
                return
            from payments import reissue_download_for_purchase_id

            form = dict(urllib.parse.parse_qsl(body.decode("utf-8", "replace")))
            pid_in = (form.get("purchase_id") or "").strip()
            issued = reissue_download_for_purchase_id(pid_in)
            if issued and issued.get("download_url"):
                # Never emit free GitHub installer URLs from reissue
                url = str(issued["download_url"])
                if "github.com" in url.lower() and "releases/download" in url.lower():
                    self._send(
                        500,
                        "text/html; charset=utf-8",
                        render_admin_html(
                            reissue_error="Internal error: refusing free release URL",
                            reissue_form_value=pid_in,
                        ),
                    )
                    return
                self._send(
                    200,
                    "text/html; charset=utf-8",
                    render_admin_html(
                        reissue_result=issued,
                        reissue_form_value=str(issued.get("purchase_id") or pid_in),
                    ),
                )
            else:
                self._send(
                    400,
                    "text/html; charset=utf-8",
                    render_admin_html(
                        reissue_error=(
                            "No paid purchase found for that product purchase identifier. "
                            "Check the RPT-XXXX-XXXX-XXXX value the buyer saved on the thank-you page."
                        ),
                        reissue_form_value=pid_in,
                    ),
                )
            return

        if path in ("/admin/mint-download", "/admin/mint-download/"):
            # Admin failsafe: live download by platform — no RPT-PPI required
            if not admin_enabled():
                self._send(503, "text/plain; charset=utf-8", b"admin disabled")
                return
            if not is_authenticated(self.headers):
                self._send(200, "text/html; charset=utf-8", render_login_html())
                return
            from payments import admin_mint_download_for_platform

            form = dict(urllib.parse.parse_qsl(body.decode("utf-8", "replace")))
            plat = (form.get("platform") or "windows").strip().lower()
            try:
                minted = admin_mint_download_for_platform(plat)
            except ValueError as exc:
                self._send(
                    400,
                    "text/html; charset=utf-8",
                    render_admin_html(
                        ondemand_error=str(exc),
                        ondemand_platform=plat,
                    ),
                )
                return
            url = str(minted.get("download_url") or "")
            if "github.com" in url.lower() and "releases/download" in url.lower():
                self._send(
                    500,
                    "text/html; charset=utf-8",
                    render_admin_html(
                        ondemand_error="Internal error: refusing free release URL",
                        ondemand_platform=plat,
                    ),
                )
                return
            # No durable customer-recovery log for this failsafe path
            self._send(
                200,
                "text/html; charset=utf-8",
                render_admin_html(
                    ondemand_result=minted,
                    ondemand_platform=str(minted.get("platform") or plat),
                ),
            )
            return

        if path in ("/admin/resend-fulfilment-email", "/admin/resend-fulfilment-email/"):
            # Operator: re-send keygen + download email via real SMTP path
            if not admin_enabled():
                self._send(503, "text/plain; charset=utf-8", b"admin disabled")
                return
            if not is_authenticated(self.headers):
                self._send(200, "text/html; charset=utf-8", render_login_html())
                return
            from payments import admin_resend_fulfilment_email

            form = dict(urllib.parse.parse_qsl(body.decode("utf-8", "replace")))
            to_email = (form.get("to_email") or form.get("email") or "").strip()
            sid = (form.get("session_id") or "").strip()
            pid = (form.get("purchase_id") or "").strip()
            plat = (form.get("platform") or "windows").strip().lower()
            result = admin_resend_fulfilment_email(
                to_email=to_email,
                session_id=sid,
                purchase_id=pid,
                platform=plat,
            )
            code = 200 if result.get("sent") else 400
            self._send(
                code,
                "application/json",
                json.dumps(result).encode("utf-8"),
            )
            return

        if path in ("/admin/mint-keygen", "/admin/mint-keygen/"):
            # Admin failsafe: mint active KEYGEN for lost licence unlock codes
            if not admin_enabled():
                self._send(503, "text/plain; charset=utf-8", b"admin disabled")
                return
            if not is_authenticated(self.headers):
                self._send(200, "text/html; charset=utf-8", render_login_html())
                return
            from payments import admin_mint_keygen_failsafe

            form = dict(urllib.parse.parse_qsl(body.decode("utf-8", "replace")))
            plat = (form.get("platform") or "").strip().lower()
            note = (form.get("note") or "").strip()
            try:
                minted = admin_mint_keygen_failsafe(platform=plat, note=note)
            except ValueError as exc:
                self._send(
                    400,
                    "text/html; charset=utf-8",
                    render_admin_html(
                        keygen_error=str(exc),
                        keygen_note=note,
                        keygen_platform=plat,
                    ),
                )
                return
            except RuntimeError as exc:
                self._send(
                    500,
                    "text/html; charset=utf-8",
                    render_admin_html(
                        keygen_error=str(exc),
                        keygen_note=note,
                        keygen_platform=plat,
                    ),
                )
                return
            self._send(
                200,
                "text/html; charset=utf-8",
                render_admin_html(
                    keygen_result=minted,
                    keygen_note=note,
                    keygen_platform=str(minted.get("platform") or plat),
                ),
            )
            return

        if path in ("/admin/clear-licences", "/admin/clear-licences/"):
            # Operator BETA cleanup: empty connect_entitlements (+ device bindings)
            if not admin_enabled():
                self._send(503, "text/plain; charset=utf-8", b"admin disabled")
                return
            if not is_authenticated(self.headers):
                self._send(200, "text/html; charset=utf-8", render_login_html())
                return
            from payments import clear_all_licences_for_admin
            from admin_panel import render_admin_licences_page_html

            form = dict(urllib.parse.parse_qsl(body.decode("utf-8", "replace")))
            confirm = (form.get("confirm") or "").strip()
            try:
                cleared = clear_all_licences_for_admin(confirm=confirm)
            except ValueError as exc:
                self._send(
                    400,
                    "text/html; charset=utf-8",
                    render_admin_licences_page_html(licence_clear_error=str(exc)),
                )
                return
            except Exception as exc:  # noqa: BLE001
                self._send(
                    500,
                    "text/html; charset=utf-8",
                    render_admin_licences_page_html(
                        licence_clear_error=f"clear failed: {exc}"[:240]
                    ),
                )
                return
            n = int(cleared.get("deleted_connect_entitlements") or 0)
            nd = int(cleared.get("deleted_device_entitlements") or 0)
            self._send(
                200,
                "text/html; charset=utf-8",
                render_admin_licences_page_html(
                    licence_clear_message=(
                        f"Cleared licence table: deleted {n} connect entitlement(s) "
                        f"and {nd} device binding(s). Paid download grants kept."
                    ),
                ),
            )
            return

        if path in ("/admin/clear-grants", "/admin/clear-grants/"):
            # Operator BETA cleanup: empty paid download grants only
            if not admin_enabled():
                self._send(503, "text/plain; charset=utf-8", b"admin disabled")
                return
            if not is_authenticated(self.headers):
                self._send(200, "text/html; charset=utf-8", render_login_html())
                return
            from payments import clear_all_grants_for_admin
            from admin_panel import render_admin_licences_page_html

            form = dict(urllib.parse.parse_qsl(body.decode("utf-8", "replace")))
            confirm = (form.get("confirm") or "").strip()
            try:
                cleared = clear_all_grants_for_admin(confirm=confirm)
            except ValueError as exc:
                self._send(
                    400,
                    "text/html; charset=utf-8",
                    render_admin_licences_page_html(grant_clear_error=str(exc)),
                )
                return
            except Exception as exc:  # noqa: BLE001
                self._send(
                    500,
                    "text/html; charset=utf-8",
                    render_admin_licences_page_html(
                        grant_clear_error=f"clear failed: {exc}"[:240]
                    ),
                )
                return
            n = int(cleared.get("deleted_grants") or 0)
            self._send(
                200,
                "text/html; charset=utf-8",
                render_admin_licences_page_html(
                    grant_clear_message=(
                        f"Cleared paid download grants: deleted {n} grant row(s). "
                        f"Licence entitlements kept."
                    ),
                ),
            )
            return

        if path in ("/admin/mint-tester-month", "/admin/mint-tester-month/"):
            # Admin: one-month free tester sub (download + keygen, PPI TESTER)
            if not admin_enabled():
                self._send(503, "text/plain; charset=utf-8", b"admin disabled")
                return
            if not is_authenticated(self.headers):
                self._send(200, "text/html; charset=utf-8", render_login_html())
                return
            from payments import admin_mint_one_month_tester

            form = dict(urllib.parse.parse_qsl(body.decode("utf-8", "replace")))
            plat = (form.get("platform") or "windows").strip().lower()
            try:
                minted = admin_mint_one_month_tester(plat)
            except ValueError as exc:
                self._send(
                    400,
                    "text/html; charset=utf-8",
                    render_admin_html(
                        tester_error=str(exc),
                        tester_platform=plat,
                    ),
                )
                return
            except RuntimeError as exc:
                self._send(
                    500,
                    "text/html; charset=utf-8",
                    render_admin_html(
                        tester_error=str(exc),
                        tester_platform=plat,
                    ),
                )
                return
            url = str(minted.get("download_url") or "")
            if "github.com" in url.lower() and "releases/download" in url.lower():
                self._send(
                    500,
                    "text/html; charset=utf-8",
                    render_admin_html(
                        tester_error="Internal error: refusing free release URL",
                        tester_platform=plat,
                    ),
                )
                return
            self._send(
                200,
                "text/html; charset=utf-8",
                render_admin_html(
                    tester_result=minted,
                    tester_platform=str(minted.get("platform") or plat),
                ),
            )
            return

        if path in ("/admin/seed-test-purchase", "/admin/seed-test-purchase/"):
            if not admin_enabled():
                self._send(503, "text/plain; charset=utf-8", b"admin disabled")
                return
            if not is_authenticated(self.headers):
                self._send(200, "text/html; charset=utf-8", render_login_html())
                return
            from payments import seed_test_purchase, seed_test_purchase_enabled

            if not seed_test_purchase_enabled():
                self._send(
                    403,
                    "text/html; charset=utf-8",
                    render_admin_html(
                        seed_error=(
                            "Seed test purchase is disabled. "
                            "Set RPT_ADMIN_SEED_PURCHASE=1 for local/staging only."
                        ),
                    ),
                )
                return
            form = dict(urllib.parse.parse_qsl(body.decode("utf-8", "replace")))
            plat = (form.get("platform") or "windows").strip().lower()
            try:
                seeded = seed_test_purchase(plat)
            except ValueError as exc:
                self._send(
                    400,
                    "text/html; charset=utf-8",
                    render_admin_html(seed_error=str(exc), seed_platform=plat),
                )
                return
            url = str(seeded.get("download_url") or "")
            if "github.com" in url.lower() and "releases/download" in url.lower():
                self._send(
                    500,
                    "text/html; charset=utf-8",
                    render_admin_html(
                        seed_error="Internal error: refusing free release URL",
                        seed_platform=plat,
                    ),
                )
                return
            # Pre-fill reissue form with the new purchase id for convenience
            self._send(
                200,
                "text/html; charset=utf-8",
                render_admin_html(
                    seed_result=seeded,
                    seed_platform=str(seeded.get("platform") or plat),
                    reissue_form_value=str(seeded.get("purchase_id") or ""),
                ),
            )
            return

        if path in (
            "/admin/accounting/manual-entry",
            "/admin/accounting/manual-entry/",
        ):
            # Durable manual ledger line on RASKUL LTD accounting page
            if not admin_enabled():
                self._send(503, "text/plain; charset=utf-8", b"admin disabled")
                return
            if not is_authenticated(self.headers):
                self._send(200, "text/html; charset=utf-8", render_login_html())
                return
            from accounting import (
                add_manual_entry,
                parse_money_to_pence,
                resolve_manual_gross_pence,
            )
            from admin_panel import render_admin_accounting_page_html

            form = dict(urllib.parse.parse_qsl(body.decode("utf-8", "replace")))
            try:
                # Net is never taken from the form — always gross ± fees
                gross = resolve_manual_gross_pence(
                    form.get("gross") or "0",
                    sign=(form.get("gross_sign") or "+").strip(),
                )
                fee_raw = (form.get("fee") or "").strip()
                fee = parse_money_to_pence(fee_raw) if fee_raw else 0
                added = add_manual_entry(
                    date_iso=(form.get("date_iso") or "").strip(),
                    description=(form.get("description") or "").strip(),
                    gross_pence=gross,
                    fee_pence=fee,
                    purchase_id=(form.get("purchase_id") or "").strip(),
                    platform=(form.get("platform") or "").strip(),
                )
            except ValueError as exc:
                self._send(
                    400,
                    "text/html; charset=utf-8",
                    render_admin_accounting_page_html(error=str(exc)),
                )
                return
            except Exception as exc:  # noqa: BLE001
                self._send(
                    500,
                    "text/html; charset=utf-8",
                    render_admin_accounting_page_html(
                        error=f"manual entry failed: {exc}"[:240]
                    ),
                )
                return
            self._send(
                200,
                "text/html; charset=utf-8",
                render_admin_accounting_page_html(
                    message=(
                        f"Added manual entry {added.get('id')}: "
                        f"{added.get('description')}"
                    ),
                ),
            )
            return

        if path in ("/admin/accounting/delete", "/admin/accounting/delete/"):
            # Delete manual row or hide auto setup/sale; balances recompute
            if not admin_enabled():
                self._send(503, "text/plain; charset=utf-8", b"admin disabled")
                return
            if not is_authenticated(self.headers):
                self._send(200, "text/html; charset=utf-8", render_login_html())
                return
            from accounting import delete_ledger_row
            from admin_panel import render_admin_accounting_page_html

            form = dict(urllib.parse.parse_qsl(body.decode("utf-8", "replace")))
            row_id = (form.get("row_id") or "").strip()
            try:
                result = delete_ledger_row(row_id)
            except ValueError as exc:
                self._send(
                    400,
                    "text/html; charset=utf-8",
                    render_admin_accounting_page_html(error=str(exc)),
                )
                return
            except Exception as exc:  # noqa: BLE001
                self._send(
                    500,
                    "text/html; charset=utf-8",
                    render_admin_accounting_page_html(
                        error=f"delete failed: {exc}"[:240]
                    ),
                )
                return
            action = str(result.get("action") or "removed")
            self._send(
                200,
                "text/html; charset=utf-8",
                render_admin_accounting_page_html(
                    message=f"Ledger row {row_id} {action}.",
                ),
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
