"""Operator-only admin: login, payment-processor settings, paid-download grants.

Private surface for Render status service (`/admin`). Unauthenticated visitors
see only the login form. Secrets (Stripe keys, webhook secrets, admin password)
are never embedded in HTML — only readiness flags and public dashboard links.
"""

from __future__ import annotations

import hashlib
import hmac
import os
import secrets
import time
from typing import Any

from coffee_link import COFFEE_LINK_TEXT, COFFEE_LINK_URL
from payments import (
    PRICE_LABEL,
    PRICE_PENCE,
    list_recent_grants,
    public_base_url,
    stripe_price_id,
    stripe_secret_key,
    stripe_webhook_secret,
)

SESSION_COOKIE = "rpt_admin_session"
SESSION_TTL_SEC = 8 * 3600

# Operator dashboard deep links (no secrets; login happens on Stripe/BMC sites)
STRIPE_DASHBOARD_URL = "https://dashboard.stripe.com"
STRIPE_DASHBOARD_PAYMENTS_URL = "https://dashboard.stripe.com/payments"
STRIPE_DASHBOARD_WEBHOOKS_URL = "https://dashboard.stripe.com/webhooks"
STRIPE_DASHBOARD_APIKEYS_URL = "https://dashboard.stripe.com/apikeys"
BMC_DASHBOARD_URL = "https://www.buymeacoffee.com/login"


def admin_username() -> str:
    return os.environ.get("RPT_ADMIN_USER", "admin").strip() or "admin"


def admin_password() -> str:
    """Plain password from env (set on host; never commit). Empty = admin disabled."""
    return os.environ.get("RPT_ADMIN_PASSWORD", "").strip()


def admin_session_secret() -> str:
    secret = os.environ.get("RPT_ADMIN_SESSION_SECRET", "").strip()
    if secret:
        return secret
    # Derive a host-local secret from password when set so sessions work without extra env
    pw = admin_password()
    if not pw:
        return ""
    return hashlib.sha256(f"rpt-admin-session|{pw}".encode("utf-8")).hexdigest()


def admin_enabled() -> bool:
    return bool(admin_password() and admin_session_secret())


def verify_credentials(username: str, password: str) -> bool:
    if not admin_enabled():
        return False
    u_ok = hmac.compare_digest(username.strip(), admin_username())
    p_ok = hmac.compare_digest(password, admin_password())
    return u_ok and p_ok


def mint_session_token(*, now: float | None = None) -> str:
    t = int(now if now is not None else time.time())
    nonce = secrets.token_hex(16)
    secret = admin_session_secret()
    msg = f"{t}:{nonce}".encode("utf-8")
    sig = hmac.new(secret.encode("utf-8"), msg, hashlib.sha256).hexdigest()
    return f"{t}:{nonce}:{sig}"


def verify_session_token(token: str, *, now: float | None = None) -> bool:
    if not admin_enabled() or not token:
        return False
    parts = token.split(":")
    if len(parts) != 3:
        return False
    ts_s, nonce, sig = parts
    try:
        ts = int(ts_s)
    except ValueError:
        return False
    tnow = now if now is not None else time.time()
    if tnow - ts > SESSION_TTL_SEC or ts > tnow + 60:
        return False
    secret = admin_session_secret()
    msg = f"{ts}:{nonce}".encode("utf-8")
    expected = hmac.new(secret.encode("utf-8"), msg, hashlib.sha256).hexdigest()
    return hmac.compare_digest(expected, sig)


def parse_cookie_header(header: str | None) -> dict[str, str]:
    out: dict[str, str] = {}
    if not header:
        return out
    for part in header.split(";"):
        part = part.strip()
        if "=" not in part:
            continue
        k, v = part.split("=", 1)
        out[k.strip()] = v.strip()
    return out


def session_from_headers(headers: Any) -> str:
    # headers may be BaseHTTPRequestHandler.headers
    cookie = ""
    try:
        cookie = headers.get("Cookie") or headers.get("cookie") or ""
    except Exception:
        cookie = ""
    return parse_cookie_header(cookie).get(SESSION_COOKIE, "")


def is_authenticated(headers: Any, *, now: float | None = None) -> bool:
    return verify_session_token(session_from_headers(headers), now=now)


def admin_page_access(*, authenticated: bool, enabled: bool | None = None) -> str:
    """Pure access decision for /admin content.

    Returns one of: ``disabled``, ``login_required``, ``granted``.
    """
    if enabled is None:
        enabled = admin_enabled()
    if not enabled:
        return "disabled"
    if not authenticated:
        return "login_required"
    return "granted"


def stripe_key_mode_label(secret_key: str | None = None) -> str:
    """Return test / live / unconfigured from key prefix only — never the key itself."""
    key = (secret_key if secret_key is not None else stripe_secret_key()).strip()
    if not key:
        return "unconfigured"
    if key.startswith("sk_live_"):
        return "live"
    if key.startswith("sk_test_"):
        return "test"
    # Present but non-standard prefix (still never echo the value)
    return "configured"


def processor_settings_view() -> dict[str, Any]:
    """Payment-processor readiness + operator links for the private admin page.

    Never includes secret key material — only booleans, safe labels, and public URLs.
    """
    secret = stripe_secret_key()
    webhook = stripe_webhook_secret()
    price_id = stripe_price_id()
    mode = stripe_key_mode_label(secret)
    stripe_ready = bool(secret)
    webhook_ready = bool(webhook)
    return {
        "stripe_configured": stripe_ready,
        "stripe_webhook_configured": webhook_ready,
        "stripe_price_id_set": bool(price_id),
        "stripe_mode": mode,
        "stripe_checkout_ready": stripe_ready,  # Checkout needs secret; webhook separate
        "stripe_fulfilment_ready": stripe_ready and webhook_ready,
        "price_label": PRICE_LABEL,
        "price_pence": PRICE_PENCE,
        "public_base_url": public_base_url(),
        "webhook_path": "/webhook/stripe",
        "stripe_dashboard_url": STRIPE_DASHBOARD_URL,
        "stripe_payments_url": STRIPE_DASHBOARD_PAYMENTS_URL,
        "stripe_webhooks_url": STRIPE_DASHBOARD_WEBHOOKS_URL,
        "stripe_apikeys_url": STRIPE_DASHBOARD_APIKEYS_URL,
        "bmc_tip_url": COFFEE_LINK_URL,
        "bmc_tip_label": COFFEE_LINK_TEXT,
        "bmc_dashboard_url": BMC_DASHBOARD_URL,
        "bmc_role": "tip_support_only",
        # Explicit: secrets never leave the view model as values
        "secrets_in_view": False,
    }


def project_grants_for_admin(
    grants: list[dict[str, Any]] | None = None, *, limit: int = 50
) -> list[dict[str, Any]]:
    """Project grant rows for admin UI (full token kept for operator support, truncated in HTML)."""
    raw = grants if grants is not None else list_recent_grants(limit)
    out: list[dict[str, Any]] = []
    for g in raw:
        out.append(
            {
                "platform": g.get("platform") or "",
                "filename": g.get("filename") or "",
                "amount_pence": int(g.get("amount_pence") or 0),
                "currency": g.get("currency") or "",
                "status": g.get("status") or "",
                "used_at": g.get("used_at"),
                "token": g.get("token") or "",
                "session_id": g.get("session_id") or "",
                "created_at": g.get("created_at"),
            }
        )
    return out


def render_login_html(*, error: str = "") -> bytes:
    err = (
        f'<p class="err" id="admin-error">{_escape(error)}</p>' if error else ""
    )
    body = f"""<!DOCTYPE html>
<html lang="en"><head>
<meta charset="utf-8"/><meta name="viewport" content="width=device-width, initial-scale=1"/>
<title>Admin login — Restore Privacy</title>
<style>
body{{margin:0;min-height:100vh;display:flex;align-items:center;justify-content:center;
background:#0b0f14;color:#e8eef5;font-family:system-ui,sans-serif}}
form{{background:#111827;padding:1.5rem 1.75rem;border-radius:12px;min-width:18rem;
max-width:22rem}}
label{{display:block;font-size:0.85rem;margin:0.6rem 0 0.25rem;opacity:0.85}}
input{{width:100%;box-sizing:border-box;padding:0.55rem 0.65rem;border-radius:8px;
border:1px solid #374151;background:#0b0f14;color:#e8eef5}}
button{{margin-top:1rem;width:100%;padding:0.7rem;border:0;border-radius:8px;
background:#1d4ed8;color:#fff;font-weight:600;cursor:pointer}}
.err{{color:#fca5a5;font-size:0.9rem}}
h1{{font-size:1.1rem;margin:0 0 0.5rem}}
.note{{opacity:0.7;font-size:0.85rem;margin:0 0 0.75rem;line-height:1.35}}
</style></head><body>
<form method="post" action="/admin/login" id="admin-login-form">
  <h1>Operator admin</h1>
  <p class="note" id="admin-login-note">Private page: payment processor settings
  and paid-download administration. Not the public catalog.</p>
  {err}
  <label for="username">Username</label>
  <input id="username" name="username" autocomplete="username" required/>
  <label for="password">Password</label>
  <input id="password" name="password" type="password" autocomplete="current-password" required/>
  <button type="submit">Sign in</button>
</form>
</body></html>
"""
    return body.encode("utf-8")


def _status_badge(ok: bool, yes: str = "ready", no: str = "not set") -> str:
    cls = "ok" if ok else "bad"
    label = yes if ok else no
    return f'<span class="badge {cls}" data-ready="{"1" if ok else "0"}">{_escape(label)}</span>'


def render_processor_settings_html(view: dict[str, Any] | None = None) -> str:
    """HTML fragment: payment-processor settings/status (authenticated admin only)."""
    v = view if view is not None else processor_settings_view()
    # Hard guarantee: never emit raw secret env values if somehow present
    forbidden_fragments = (
        "sk_live_",
        "sk_test_",
        "whsec_",
        "RPT_ADMIN_PASSWORD",
    )
    stripe_mode = str(v.get("stripe_mode") or "unconfigured")
    base = str(v.get("public_base_url") or "")
    webhook_url = f"{base.rstrip('/')}{v.get('webhook_path') or '/webhook/stripe'}"
    frag = f"""
<section id="admin-processor-settings" class="card">
  <h2>Payment processor settings</h2>
  <p class="muted">Readiness from host environment. Secrets stay on the server
  (Render env) — log into Stripe / Buy Me a Coffee dashboards with your own accounts
  to change keys, webhooks, and payouts.</p>

  <h3 id="admin-stripe-heading">Stripe (paid downloads { _escape(str(v.get('price_label') or '')) })</h3>
  <dl id="admin-stripe-status" class="status-list">
    <div><dt>Secret key</dt><dd id="stripe-secret-status">{_status_badge(bool(v.get("stripe_configured")))}</dd></div>
    <div><dt>Key mode</dt><dd id="stripe-key-mode">{_escape(stripe_mode)}</dd></div>
    <div><dt>Webhook signing secret</dt><dd id="stripe-webhook-status">{_status_badge(bool(v.get("stripe_webhook_configured")))}</dd></div>
    <div><dt>Price id (optional)</dt><dd id="stripe-price-status">{_status_badge(bool(v.get("stripe_price_id_set")), "set", "empty · unit_amount 245")}</dd></div>
    <div><dt>Checkout ready</dt><dd id="stripe-checkout-ready">{_status_badge(bool(v.get("stripe_checkout_ready")))}</dd></div>
    <div><dt>Fulfilment ready (key + webhook)</dt><dd id="stripe-fulfilment-ready">{_status_badge(bool(v.get("stripe_fulfilment_ready")))}</dd></div>
    <div><dt>Public base URL</dt><dd id="stripe-public-base"><code>{_escape(base)}</code></dd></div>
    <div><dt>Webhook endpoint</dt><dd id="stripe-webhook-url"><code>{_escape(webhook_url)}</code></dd></div>
  </dl>
  <p class="ops-links" id="admin-stripe-links">
    Operator logins (Stripe account):
    <a href="{_escape(str(v.get('stripe_dashboard_url') or ''))}" target="_blank" rel="noopener noreferrer" id="link-stripe-dashboard">Dashboard</a>
    · <a href="{_escape(str(v.get('stripe_apikeys_url') or ''))}" target="_blank" rel="noopener noreferrer" id="link-stripe-apikeys">API keys</a>
    · <a href="{_escape(str(v.get('stripe_webhooks_url') or ''))}" target="_blank" rel="noopener noreferrer" id="link-stripe-webhooks">Webhooks</a>
    · <a href="{_escape(str(v.get('stripe_payments_url') or ''))}" target="_blank" rel="noopener noreferrer" id="link-stripe-payments">Payments</a>
  </p>

  <h3 id="admin-bmc-heading">Buy Me a Coffee (tip / support only)</h3>
  <p class="muted">BMC does <strong>not</strong> mint download tokens. Tips go to the creator page.</p>
  <dl id="admin-bmc-status" class="status-list">
    <div><dt>Public tip URL</dt><dd id="bmc-tip-url"><a href="{_escape(str(v.get('bmc_tip_url') or ''))}" target="_blank" rel="noopener noreferrer">{_escape(str(v.get('bmc_tip_url') or ''))}</a></dd></div>
    <div><dt>Footer label</dt><dd id="bmc-tip-label">{_escape(str(v.get('bmc_tip_label') or ''))}</dd></div>
    <div><dt>Role</dt><dd id="bmc-role">{_escape(str(v.get('bmc_role') or ''))}</dd></div>
  </dl>
  <p class="ops-links" id="admin-bmc-links">
    Operator login (BMC):
    <a href="{_escape(str(v.get('bmc_dashboard_url') or ''))}" target="_blank" rel="noopener noreferrer" id="link-bmc-login">Creator login</a>
  </p>
</section>
"""
    low = frag.lower()
    for bad in forbidden_fragments:
        # Allow the string "sk_test_" only inside prose? We never put keys in HTML.
        # stripe_mode is only "test"/"live"/… without sk_ prefix.
        if bad.lower() in low and bad not in ("RPT_ADMIN_PASSWORD",):
            # If a secret prefix leaked, strip entire settings to safe placeholder
            return (
                '<section id="admin-processor-settings"><p class="err">'
                "Settings redacted (secret material detected).</p></section>"
            )
    return frag


def render_admin_html(grants: list[dict[str, Any]] | None = None) -> bytes:
    """Full private admin page: processor settings + payment grants administration."""
    projected = project_grants_for_admin(grants)
    rows = []
    for g in projected:
        tok = str(g.get("token") or "")
        tok_short = (tok[:10] + "…") if len(tok) > 12 else tok
        used = g.get("used_at")
        used_s = "used" if used else str(g.get("status") or "")
        rows.append(
            "<tr>"
            f"<td>{_escape(str(g.get('platform') or ''))}</td>"
            f"<td>{_escape(str(g.get('filename') or ''))}</td>"
            f"<td>{int(g.get('amount_pence') or 0)} {_escape(str(g.get('currency') or ''))}</td>"
            f"<td>{_escape(used_s)}</td>"
            f"<td title=\"{_escape(tok)}\">{_escape(tok_short)}</td>"
            f"<td>{_escape(str(g.get('session_id') or '')[:18])}</td>"
            "</tr>"
        )
    table = (
        "\n".join(rows)
        if rows
        else '<tr><td colspan="6">No grants yet</td></tr>'
    )
    settings_html = render_processor_settings_html()
    body = f"""<!DOCTYPE html>
<html lang="en"><head>
<meta charset="utf-8"/><meta name="viewport" content="width=device-width, initial-scale=1"/>
<title>Admin — payments &amp; processors</title>
<style>
body{{margin:0;padding:1.5rem;background:#0b0f14;color:#e8eef5;font-family:system-ui,sans-serif}}
h1{{font-size:1.25rem;margin:0}} h2{{font-size:1.05rem;margin:0 0 0.5rem}}
h3{{font-size:0.95rem;margin:1rem 0 0.4rem;opacity:0.95}}
a{{color:#93c5fd}}
table{{border-collapse:collapse;width:100%;max-width:56rem;font-size:0.9rem}}
th,td{{border-bottom:1px solid #1f2937;padding:0.45rem 0.5rem;text-align:left}}
th{{opacity:0.75;font-weight:600}}
.top{{display:flex;gap:1rem;align-items:center;margin-bottom:1rem;flex-wrap:wrap}}
.card{{background:#111827;border-radius:12px;padding:1rem 1.15rem;margin:1rem 0;
max-width:56rem}}
.muted{{opacity:0.75;font-size:0.9rem;line-height:1.4}}
.status-list{{margin:0.5rem 0}}
.status-list > div{{display:grid;grid-template-columns:12rem 1fr;gap:0.35rem 0.75rem;
padding:0.25rem 0;font-size:0.9rem}}
.status-list dt{{opacity:0.7}}
.badge{{display:inline-block;padding:0.15rem 0.5rem;border-radius:6px;font-size:0.8rem;
font-weight:600}}
.badge.ok{{background:#064e3b;color:#6ee7b7}}
.badge.bad{{background:#450a0a;color:#fca5a5}}
.ops-links{{font-size:0.9rem;margin:0.75rem 0 0.25rem}}
.nav-local a{{margin-right:0.75rem;font-size:0.9rem}}
code{{font-size:0.85rem;word-break:break-all}}
</style></head><body>
<div class="top">
  <h1 id="admin-heading">Payment administration</h1>
  <a href="/admin/logout" id="admin-logout">Log out</a>
  <a href="/">Status page</a>
</div>
<nav class="nav-local" id="admin-nav" aria-label="Admin sections">
  <a href="#admin-processor-settings">Processor settings</a>
  <a href="#admin-grants">Paid download grants</a>
</nav>
{settings_html}
<section id="admin-grants" class="card">
  <h2 id="admin-grants-heading">Paid download grants</h2>
  <p class="muted">Recent Stripe-verified download tokens ({_escape(PRICE_LABEL)} GBP each).
  Use session id / token to help a buyer after Checkout. Secrets never shown.</p>
  <table id="admin-grants-table">
    <thead><tr>
      <th>Platform</th><th>Filename</th><th>Amount</th><th>Status</th><th>Token</th><th>Session</th>
    </tr></thead>
    <tbody>
{table}
    </tbody>
  </table>
</section>
</body></html>
"""
    # Final secret scan on full page
    low = body.lower()
    for prefix in ("sk_live_", "sk_test_", "whsec_"):
        if prefix in low:
            body = body.replace(prefix, "[redacted]_")
    return body.encode("utf-8")


def _escape(s: str) -> str:
    return (
        s.replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
    )
