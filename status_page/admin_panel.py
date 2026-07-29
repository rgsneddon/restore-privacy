"""Operator-only admin: login, payment-processor settings, paid-download grants.

Private surface for Render status service (`/admin`). Unauthenticated visitors
see only the login form. Secrets (Stripe keys, webhook secrets, admin password)
are never embedded in HTML — only readiness flags and public dashboard links.
"""

from __future__ import annotations

import hashlib
import hmac
import json
import os
import re
import secrets
import time
from typing import Any

from coffee_link import COFFEE_LINK_TEXT, coffee_tip_url
from payments import (
    PRICE_LABEL,
    PRICE_PENCE,
    PRICE_YEARLY_LABEL,
    list_all_grants,
    list_licences_for_admin,
    list_recent_grants,
    payment_data_dir,
    public_base_url,
    reissue_download_for_purchase_id,
    seed_test_purchase_enabled,
    stripe_payment_link_id,
    stripe_payment_page_url,
    stripe_price_id,
    stripe_remaining_required_keys,
    stripe_secret_key,
    stripe_webhook_endpoint_url,
    stripe_webhook_operator_guidance,
    stripe_webhook_secret,
    STRIPE_WEBHOOK_EVENTS,
    STRIPE_WEBHOOK_PATH,
)

# Page-top return target (h1 on authenticated admin HTML).
ADMIN_TOP_ANCHOR_ID = "admin-heading"
ADMIN_TOP_LINK_LABEL = "^top"

# Link Generation: external script for copy + post-mint scroll (CSP script-src self).
ADMIN_LINK_GENERATION_SCRIPT = "/static/admin_link_generation.js"


def admin_copy_control_html(target_id: str, *, label: str = "Copy") -> str:
    """One-click copy control bound to element *target_id* (data-copy-target)."""
    tid = _escape(target_id)
    lab = _escape(label)
    return (
        f'<span class="admin-copy-row" data-admin-copy-row="1">'
        f'<button type="button" class="admin-copy-btn" '
        f'data-copy-target="{tid}" id="{tid}-copy-btn">{lab}</button>'
        f'<span class="admin-copy-status" data-copy-status-for="{tid}" '
        f'aria-live="polite"></span></span>'
    )


def admin_section_top_link_html() -> str:
    """End-of-section link back to the top of the authenticated admin page."""
    return (
        f'<p class="admin-top-link">'
        f'<a href="#{ADMIN_TOP_ANCHOR_ID}" class="admin-top-link-a">'
        f"{ADMIN_TOP_LINK_LABEL}</a></p>\n"
    )


# Operator-facing architecture blurb (must stay current; grepped by tests).
# Short form kept for greps; full home copy is ADMIN_ARCHITECTURE_FULL.
ADMIN_ARCHITECTURE_BLURB = (
    "Residual catalog peers: Germany (DE, default entry), Iceland (IS), "
    "United States (US) — user-selectable entry; multi-hop opt-in uses a random "
    "non-entry peer. Weekly fleet wipe is sequential IS → DE → US (exclusive "
    "lock; never concurrent multi-node wipe). Paid Stripe Checkout "
    f"(Monthly {PRICE_LABEL} / Yearly {PRICE_YEARLY_LABEL} GBP) + keygen unlock; "
    "no free permanent GitHub installers. Public status is title-only (no live "
    "client count). Licence database and paid download grants live in the "
    "durable payment store and are retained across residual node wipeclean/"
    "rebuild — they are not residual-runtime scratch."
)

# Human-cadence product architecture copy for the admin home main pane.
ADMIN_ARCHITECTURE_FULL = (
    "Restore Privacy is a paid residual VPN product. Customers pick a platform, "
    "pay on Stripe (monthly or yearly), then unlock Connect with the keygen from "
    "their fulfilment email. Installers are never free permanent GitHub downloads — "
    "each package is handed out through a time-limited paid link on the status host "
    "(default 1 hour, reusable until it expires).\n\n"
    "Where residual traffic lands: the live catalog has three peers — Germany "
    "(default entry), Iceland, and United States. Users choose their entry country "
    "in the app. Multi-hop is optional: when turned on, exit is another catalog "
    "peer, not a second product they buy. The old Romania (RO) residual peer is "
    "deprecated and must not reappear as a live pin.\n\n"
    "How the fleet is kept honest: about once a week the operator path wipes and "
    "rebuilds residual peers one at a time (Iceland → Germany → United States), never "
    "all three at once. Clients can hop to a healthy peer while one is rebuilding. "
    "Public status pages stay title-only — we do not publish a live client count.\n\n"
    "What you manage here: payment processor readiness, one-off download and keygen "
    "tools under Link Generation, and the durable licence + grant history under "
    "Active Licences. That payment database survives residual node wipe and Render "
    "redeploys when it sits on the attached disk path — it is not residual scratch.\n\n"
    f"Catalog prices on this pin: Monthly {PRICE_LABEL} GBP and Yearly "
    f"{PRICE_YEARLY_LABEL} GBP. Connect stays allowed only while a licence is OK "
    "(paid period still open and keygen activated). When a period ends or a "
    "subscription is revoked, rows stay visible as ENDED so operators can still "
    "audit history."
)

# Catalog device packages for admin failsafe dropdown (current ship pin).
_ADMIN_CATALOG_PLATFORMS: tuple[str, ...] = (
    "windows",
    "linux",
    "macos",
    "ios",
    "android",
)
from processor_plugins import (
    list_processor_plugins,
    processor_plugin_views,
)

SESSION_COOKIE = "rpt_admin_session"
SESSION_TTL_SEC = 8 * 3600

# Honest operator guidance: authenticator is strong, not absolute immunity.
ADMIN_2FA_SECURITY_BLURB = (
    "Authenticator apps (TOTP, e.g. Google Authenticator, Authy, 1Password) are a "
    "standard, strong second factor for admin panels: an attacker needs your password "
    "and a fresh code from your device. This is not absolute immunity — protect the "
    "phone/app, avoid phishing of live codes, use a long unique password, and keep "
    "the host/account secrets private. Lost device: an operator with Render access "
    "must clear the durable 2FA store or rotate credentials before re-enrollment."
)

# Extra practical controls (advice only — not all implemented in-product).
ADMIN_SECURITY_EXTRA_ADVICE = (
    "Further harden admin access: (1) long unique password in a password manager, "
    "rotated if ever shared; (2) keep RPT_ADMIN_PASSWORD / session secrets only in "
    "Render env (never git or screenshots); (3) complete authenticator enrollment "
    "promptly and do not leave the setup secret on disk; (4) sign out when done; "
    "avoid shared browsers; (5) treat live 6-digit codes as passwords — never paste "
    "them into chat/email; (6) optional host-side controls (Render IP allowlist, "
    "VPN/SSH tunnel only, separate operator device) reduce exposure further; "
    "(7) WebAuthn/hardware keys are stronger than TOTP if you add them later. "
    "TOTP + strong password is industry-standard for panels like this; nothing "
    "gives zero risk if the server or phone is fully compromised."
)

# Public media kit (brand logos / favicons) — no auth required.
MEDIA_KIT_PUBLIC_PATH = "/media-kit/restore-privacy-media-kit.zip"
MEDIA_KIT_FILENAME = "restore-privacy-media-kit.zip"

# Appearance: follow device/OS colour scheme by default; operator may pick light/dark.
THEME_STORAGE_KEY = "rpt_admin_theme"
THEME_MODES = frozenset({"system", "light", "dark"})
DEFAULT_THEME_MODE = "system"

# Operator dashboard deep links (no secrets; login happens on Stripe/BMC sites)
STRIPE_DASHBOARD_URL = "https://dashboard.stripe.com"
STRIPE_DASHBOARD_PAYMENTS_URL = "https://dashboard.stripe.com/payments"
STRIPE_DASHBOARD_WEBHOOKS_URL = "https://dashboard.stripe.com/webhooks"
STRIPE_DASHBOARD_APIKEYS_URL = "https://dashboard.stripe.com/apikeys"
BMC_DASHBOARD_URL = "https://www.buymeacoffee.com/login"


def normalize_theme_mode(mode: str | None) -> str:
    """Pure: accept light / dark / system only; invalid → system (device colours)."""
    m = (mode or "").strip().lower()
    if m in THEME_MODES:
        return m
    return DEFAULT_THEME_MODE


def admin_theme_css() -> str:
    """Shared light/dark tokens; default tracks prefers-color-scheme (device settings)."""
    return """
:root, [data-theme="light"] {
  color-scheme: light;
  --bg: #f4f6f9;
  --bg-elevated: #ffffff;
  --fg: #0f172a;
  --fg-muted: #475569;
  --border: #d1d9e6;
  --input-bg: #ffffff;
  --input-border: #cbd5e1;
  --link: #1d4ed8;
  --btn-bg: #1d4ed8;
  --btn-fg: #ffffff;
  --err: #b91c1c;
  --badge-ok-bg: #d1fae5;
  --badge-ok-fg: #065f46;
  --badge-bad-bg: #fee2e2;
  --badge-bad-fg: #991b1b;
  --table-border: #e2e8f0;
  --theme-active: #1d4ed8;
}
@media (prefers-color-scheme: dark) {
  :root:not([data-theme="light"]) {
    color-scheme: dark;
    --bg: #0b0f14;
    --bg-elevated: #111827;
    --fg: #e8eef5;
    --fg-muted: #94a3b8;
    --border: #1f2937;
    --input-bg: #0b0f14;
    --input-border: #374151;
    --link: #93c5fd;
    --btn-bg: #1d4ed8;
    --btn-fg: #ffffff;
    --err: #fca5a5;
    --badge-ok-bg: #064e3b;
    --badge-ok-fg: #6ee7b7;
    --badge-bad-bg: #450a0a;
    --badge-bad-fg: #fca5a5;
    --table-border: #1f2937;
    --theme-active: #93c5fd;
  }
}
[data-theme="dark"] {
  color-scheme: dark;
  --bg: #0b0f14;
  --bg-elevated: #111827;
  --fg: #e8eef5;
  --fg-muted: #94a3b8;
  --border: #1f2937;
  --input-bg: #0b0f14;
  --input-border: #374151;
  --link: #93c5fd;
  --btn-bg: #1d4ed8;
  --btn-fg: #ffffff;
  --err: #fca5a5;
  --badge-ok-bg: #064e3b;
  --badge-ok-fg: #6ee7b7;
  --badge-bad-bg: #450a0a;
  --badge-bad-fg: #fca5a5;
  --table-border: #1f2937;
  --theme-active: #93c5fd;
}
html, body {
  background: var(--bg);
  color: var(--fg);
  font-family: system-ui, -apple-system, Segoe UI, sans-serif;
}
a { color: var(--link); }
.theme-bar {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 0.5rem 0.75rem;
  font-size: 0.85rem;
  margin: 0 0 1rem;
}
.theme-bar .theme-ask {
  color: var(--fg-muted);
  margin: 0;
}
.theme-bar fieldset {
  border: 1px solid var(--border);
  border-radius: 10px;
  margin: 0;
  padding: 0.35rem 0.55rem;
  display: inline-flex;
  gap: 0.35rem;
  background: var(--bg-elevated);
}
.theme-bar legend {
  font-size: 0.75rem;
  color: var(--fg-muted);
  padding: 0 0.25rem;
}
.theme-bar label {
  display: inline-flex;
  align-items: center;
  gap: 0.25rem;
  cursor: pointer;
  padding: 0.2rem 0.4rem;
  border-radius: 6px;
  margin: 0;
  font-size: 0.85rem;
}
.theme-bar input { accent-color: var(--theme-active); margin: 0; }
.theme-bar label:has(input:checked) {
  outline: 1px solid var(--theme-active);
  background: color-mix(in srgb, var(--theme-active) 12%, transparent);
}
"""


def admin_theme_picker_html() -> str:
    """Ask light / dark / device (system) preference — shipped on login + admin."""
    return f"""
<div class="theme-bar" id="admin-theme-bar" role="group" aria-label="Colour mode">
  <p class="theme-ask" id="admin-theme-ask">Prefer light or dark mode?
  Default follows your device colour settings.</p>
  <fieldset id="admin-theme-fieldset">
    <legend>Appearance</legend>
    <label><input type="radio" name="admin-theme" id="theme-system" value="system" checked/> Device</label>
    <label><input type="radio" name="admin-theme" id="theme-light" value="light"/> Light</label>
    <label><input type="radio" name="admin-theme" id="theme-dark" value="dark"/> Dark</label>
  </fieldset>
</div>
"""


def admin_theme_boot_script() -> str:
    """Same-origin theme script tag (CSP script-src 'self'; logic in static JS)."""
    key = THEME_STORAGE_KEY
    return (
        f'<script id="admin-theme-script" src="/static/admin_theme.js" '
        f'data-storage-key="{key}"></script>\n'
    )


def json_dumps_str(s: str) -> str:
    """JSON-encode a string for safe embedding in a script tag."""
    return json.dumps(s)


def admin_username() -> str:
    return os.environ.get("RPT_ADMIN_USER", "admin").strip() or "admin"


def admin_password() -> str:
    """Plain password from env (set on host; never commit). Empty = use digest path."""
    return os.environ.get("RPT_ADMIN_PASSWORD", "").strip()


# PBKDF2 digest so /admin can enable without plaintext secret in Render env or git.
# Format: pbkdf2_sha256$iterations$salt_hex$digest_hex
# Override with RPT_ADMIN_PASSWORD_DIGEST or prefer live RPT_ADMIN_PASSWORD env.
# Plaintext operator password is intentionally never stored in the repository.
_DEFAULT_ADMIN_PASSWORD_DIGEST = (
    "pbkdf2_sha256$200000$f089cfac23eb426ac209efa3570e7aa3$25dbddb2e18658db"
    "9211a5480a3da123792e9135d02542b5a1b92a8bc76b60e5"
)


def admin_password_digest() -> str:
    """Password digest for bootstrap enablement (env override or shipped default).

    Set ``RPT_ADMIN_DISABLE_BOOTSTRAP=1`` to force env-password-only mode.
    Set ``RPT_ADMIN_PASSWORD_DIGEST`` (even empty) to override the shipped digest.
    """
    if os.environ.get("RPT_ADMIN_DISABLE_BOOTSTRAP", "").strip().lower() in (
        "1",
        "true",
        "yes",
    ):
        return ""
    if "RPT_ADMIN_PASSWORD_DIGEST" in os.environ:
        return os.environ.get("RPT_ADMIN_PASSWORD_DIGEST", "").strip()
    return _DEFAULT_ADMIN_PASSWORD_DIGEST


def make_password_digest(password: str, *, iterations: int = 200_000, salt: bytes | None = None) -> str:
    """Build a pbkdf2_sha256 digest string for a password (tests / rotation)."""
    if salt is None:
        salt = secrets.token_bytes(16)
    dig = hashlib.pbkdf2_hmac(
        "sha256", password.encode("utf-8"), salt, int(iterations)
    )
    return f"pbkdf2_sha256${int(iterations)}${salt.hex()}${dig.hex()}"


def verify_password_digest(password: str, digest: str) -> bool:
    """Constant-time-ish verify of password against pbkdf2_sha256$… digest."""
    try:
        scheme, iters_s, salt_hex, want_hex = digest.split("$", 3)
    except ValueError:
        return False
    if scheme != "pbkdf2_sha256":
        return False
    try:
        iterations = int(iters_s)
        salt = bytes.fromhex(salt_hex)
        want = bytes.fromhex(want_hex)
    except ValueError:
        return False
    if iterations < 10_000 or not salt or not want:
        return False
    got = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, iterations)
    return hmac.compare_digest(got, want)


def verify_admin_password(password: str) -> bool:
    """Env plaintext wins when set; otherwise bootstrap digest."""
    env_pw = admin_password()
    if env_pw:
        return hmac.compare_digest(password, env_pw)
    dig = admin_password_digest()
    if not dig:
        return False
    return verify_password_digest(password, dig)


def admin_session_secret() -> str:
    secret = os.environ.get("RPT_ADMIN_SESSION_SECRET", "").strip()
    if secret:
        return secret
    # Derive a host-local secret from password when set so sessions work without extra env
    pw = admin_password()
    if pw:
        return hashlib.sha256(f"rpt-admin-session|{pw}".encode("utf-8")).hexdigest()
    dig = admin_password_digest()
    if dig:
        return hashlib.sha256(f"rpt-admin-session|digest|{dig}".encode("utf-8")).hexdigest()
    return ""


def admin_enabled() -> bool:
    """Enabled when plaintext env password or bootstrap digest is available."""
    if not admin_session_secret():
        return False
    return bool(admin_password() or admin_password_digest())


def verify_credentials(username: str, password: str) -> bool:
    if not admin_enabled():
        return False
    u_ok = hmac.compare_digest(username.strip(), admin_username())
    p_ok = verify_admin_password(password)
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
    """True only for a full admin session (password + completed 2FA/setup)."""
    return verify_session_token(session_from_headers(headers), now=now)


def admin_cookie_secure() -> bool:
    """Set Secure on session cookies when public origin is HTTPS (or forced)."""
    force = os.environ.get("RPT_ADMIN_COOKIE_SECURE", "").strip().lower()
    if force in ("1", "true", "yes"):
        return True
    if force in ("0", "false", "no"):
        return False
    base = (os.environ.get("RPT_PUBLIC_BASE_URL", "") or "").strip().lower()
    return base.startswith("https://")


def format_session_cookie(
    token: str,
    *,
    max_age: int = SESSION_TTL_SEC,
    clear: bool = False,
    cookie_name: str | None = None,
) -> str:
    """Build Set-Cookie value: HttpOnly, SameSite=Strict, Secure when HTTPS."""
    name = cookie_name or SESSION_COOKIE
    if clear:
        parts = [f"{name}=", "Path=/", "HttpOnly", "SameSite=Strict", "Max-Age=0"]
    else:
        parts = [
            f"{name}={token}",
            "Path=/",
            "HttpOnly",
            "SameSite=Strict",
            f"Max-Age={int(max_age)}",
        ]
    if admin_cookie_secure():
        parts.append("Secure")
    return "; ".join(parts)


def admin_page_access(*, authenticated: bool, enabled: bool | None = None) -> str:
    """Pure access decision for /admin content.

    Returns one of: ``disabled``, ``login_required``, ``granted``.
    Full session only — pending 2FA cookies must not set authenticated=True.
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
    remaining = stripe_remaining_required_keys()
    return {
        "stripe_configured": stripe_ready,
        "stripe_webhook_configured": webhook_ready,
        "stripe_price_id_set": bool(price_id),
        "stripe_mode": mode,
        "stripe_checkout_ready": stripe_ready,  # Checkout needs secret; webhook separate
        "stripe_fulfilment_ready": stripe_ready and webhook_ready,
        "stripe_payment_page_url": stripe_payment_page_url(),
        "stripe_payment_link_id": stripe_payment_link_id(),
        "stripe_remaining_required": remaining,
        "stripe_whats_next": remaining,
        "price_label": PRICE_LABEL,
        "price_pence": PRICE_PENCE,
        "public_base_url": public_base_url(),
        "webhook_path": STRIPE_WEBHOOK_PATH,
        "webhook_endpoint_url": stripe_webhook_endpoint_url(production=True),
        "webhook_events": list(STRIPE_WEBHOOK_EVENTS),
        "webhook_guidance": stripe_webhook_operator_guidance(),
        "stripe_dashboard_url": STRIPE_DASHBOARD_URL,
        "stripe_payments_url": STRIPE_DASHBOARD_PAYMENTS_URL,
        "stripe_webhooks_url": STRIPE_DASHBOARD_WEBHOOKS_URL,
        "stripe_apikeys_url": STRIPE_DASHBOARD_APIKEYS_URL,
        "bmc_tip_url": coffee_tip_url(),
        "bmc_tip_label": os.environ.get("RPT_BMC_TIP_LABEL", "").strip()
        or COFFEE_LINK_TEXT,
        "bmc_dashboard_url": BMC_DASHBOARD_URL,
        "bmc_role": "tip_support_only",
        # Explicit: secrets never leave the view model as values
        "secrets_in_view": False,
    }


def render_admin_licences_section_html(
    licences: list[dict[str, Any]] | None = None,
    *,
    clear_message: str = "",
    clear_error: str = "",
) -> str:
    """Licence database: email, KEYGEN, PPI, OK|ENDED, dates + confirmed clear-all."""
    try:
        from payments import CLEAR_ALL_LICENCES_CONFIRM  # type: ignore
    except Exception:  # noqa: BLE001
        try:
            from status_page.payments import CLEAR_ALL_LICENCES_CONFIRM  # type: ignore
        except Exception:  # noqa: BLE001
            CLEAR_ALL_LICENCES_CONFIRM = "CLEAR_ALL_LICENCES"
    try:
        rows_src = licences if licences is not None else list_licences_for_admin()
    except Exception:  # noqa: BLE001
        rows_src = []
    body_rows: list[str] = []
    for row in rows_src:
        st = str(row.get("licence_status") or "ENDED")
        badge = "ok" if st == "OK" else "bad"
        body_rows.append(
            "<tr>"
            f"<td>{_escape(str(row.get('email') or ''))}</td>"
            f"<td><code>{_escape(str(row.get('keygen') or ''))}</code></td>"
            f"<td><code>{_escape(str(row.get('purchase_id') or row.get('ppi') or ''))}</code></td>"
            f'<td><span class="badge {badge}" '
            f'id="licence-status-{_escape(str(row.get("session_id") or "")[:12])}">'
            f"{_escape(st)}</span></td>"
            f"<td>{_escape(str(row.get('platform') or ''))}</td>"
            f"<td class=\"licence-initiated\">{_escape(str(row.get('initiated_date') or ''))}</td>"
            f"<td class=\"licence-expiry\">{_escape(str(row.get('expiry_date') or ''))}</td>"
            "</tr>"
        )
    table = (
        "\n".join(body_rows)
        if body_rows
        else '<tr><td colspan="7">No licences yet</td></tr>'
    )
    msg_html = (
        f'<p class="ok-msg" id="admin-licences-clear-ok">{_escape(clear_message)}</p>'
        if clear_message
        else ""
    )
    err_html = (
        f'<p class="err" id="admin-licences-clear-error">{_escape(clear_error)}</p>'
        if clear_error
        else ""
    )
    confirm_token = _escape(str(CLEAR_ALL_LICENCES_CONFIRM))
    n = len(rows_src)
    return f"""
<section id="admin-licences" class="card">
  <h2 id="admin-licences-heading">Licence database</h2>
  <p class="muted" id="admin-licences-blurb">
  Customer licences from the <strong>durable payment store</strong>.
  <strong>Retained across residual fleet wipe/rebuild</strong>.
  Status is <code>OK</code> while Connect is allowed, or <code>ENDED</code> when the
  period finished or the licence was revoked (rows stay listed). Columns
  <strong>Initiated</strong> and <strong>Expiry</strong> are UTC calendar dates.
  Rows: <strong id="admin-licences-count">{n}</strong>.
  </p>
  <table id="admin-licences-table">
    <thead><tr>
      <th>Email</th><th>KEYGEN</th><th>PPI</th><th>Status</th><th>Platform</th>
      <th>Initiated</th><th>Expiry</th>
    </tr></thead>
    <tbody>
{table}
    </tbody>
  </table>
  {msg_html}
  {err_html}
  <form method="post" action="/admin/clear-licences" id="admin-clear-licences-form"
        data-admin-clear-licences="1"
        onsubmit="return confirm('Delete ALL licence rows? This cannot be undone.');">
    <p class="muted" id="admin-clear-licences-blurb">
      <strong>Clear all licences</strong> (BETA cleanup): permanently deletes every
      Connect entitlement and device binding so this table is empty. Does not erase
      paid download grants. Type <code id="admin-clear-licences-token">{confirm_token}</code>
      to confirm.
    </p>
    <label class="field" for="clear_licences_confirm">
      <span class="field-label">Confirm phrase</span>
      <input id="clear_licences_confirm" name="confirm" type="text" autocomplete="off"
             maxlength="64" required placeholder="{confirm_token}">
    </label>
    <button type="submit" id="admin-clear-licences-submit">Clear all licences</button>
  </form>
{admin_section_top_link_html()}</section>
"""


def project_grants_for_admin(
    grants: list[dict[str, Any]] | None = None, *, limit: int | None = None
) -> list[dict[str, Any]]:
    """Project grant rows for admin UI (includes initiated/expiry + ENDED)."""
    if grants is not None:
        raw = grants
    elif limit is None:
        raw = list_all_grants()
    else:
        raw = list_recent_grants(limit)
    out: list[dict[str, Any]] = []
    for g in raw:
        st = str(g.get("display_status") or g.get("status") or "")
        out.append(
            {
                "platform": g.get("platform") or "",
                "filename": g.get("filename") or "",
                "amount_pence": int(g.get("amount_pence") or 0),
                "currency": g.get("currency") or "",
                "status": st,
                "used_at": g.get("used_at"),
                "token": g.get("token") or "",
                "session_id": g.get("session_id") or "",
                "purchase_id": g.get("purchase_id") or "",
                "created_at": g.get("created_at"),
                "initiated_at": g.get("initiated_at"),
                "initiated_date": g.get("initiated_date") or "",
                "expiry_at": g.get("expiry_at") or g.get("valid_until"),
                "expiry_date": g.get("expiry_date") or "",
                "valid_until": g.get("valid_until"),
            }
        )
    return out


def render_purchase_reissue_section_html(
    *,
    result: dict[str, Any] | None = None,
    error: str = "",
    form_value: str = "",
) -> str:
    """Top-of-admin pathway: enter product purchase identifier → secondary download link.

    Fail-closed: unknown IDs show *error* without inventing a download URL.
    """
    err = (
        f'<p class="err" id="reissue-error" data-admin-focus-result="1">'
        f"{_escape(error)}</p>"
        if error
        else ""
    )
    ok = ""
    if result and result.get("download_url"):
        url = _escape(str(result["download_url"]))
        path = _escape(str(result.get("download_path") or ""))
        pid = _escape(str(result.get("purchase_id") or ""))
        plat = _escape(str(result.get("platform") or ""))
        fname = _escape(str(result.get("filename") or ""))
        copy_pid = admin_copy_control_html(
            "reissue-result-purchase-id", label="Copy purchase ID"
        )
        copy_url = admin_copy_control_html(
            "reissue-download-link", label="Copy download link"
        )
        ok = f"""
  <div class="ok-msg" id="reissue-result" role="status" data-admin-focus-result="1" tabindex="-1">
    <p><strong>Secondary download link minted</strong> for purchase
    <code id="reissue-result-purchase-id">{pid}</code> {copy_pid}
    ({plat} — <code>{fname}</code>).</p>
    <p>Pass this <strong>1-hour reusable</strong> link to the buyer (not a free GitHub URL):</p>
    <p><a id="reissue-download-link" href="{url}" rel="noopener noreferrer">{url}</a>
      {copy_url}</p>
    <p class="muted">Path only: <code id="reissue-download-path">{path}</code></p>
  </div>"""
    val = _escape(form_value)
    return f"""
<section id="admin-reissue" class="card" aria-labelledby="admin-reissue-heading">
  <h2 id="admin-reissue-heading">Re-issue download by purchase identifier</h2>
  <p class="muted" id="admin-reissue-note">
    <strong>Customer recovery (RPT-PPI).</strong> When a buyer loses their installer,
    they should quote the <strong>product purchase identifier</strong> from the thank-you
    page (format <code>RPT-XXXX-XXXX-XXXX</code>). Enter it below to mint a
    <strong>secondary time-limited download link</strong> for the same package they paid for.
    Tell the buyer: open the link on a trusted device within 1 hour (re-download if
    interrupted), save the installer, and keep their RPT-… ID for any future recovery.
    This is the preferred recovery path when the customer still has their purchase identifier.
  </p>
  <p class="muted" id="admin-reissue-elaborate">
    Steps for the buyer after you send the link: (1) open the 1-hour download URL
    (retry if the connection drops — same link works until it expires),
    (2) download starts or use the on-page button, (3) run/install the package,
    (4) for Connect, use payment entitlement as on the original thank-you page if needed.
    Do <strong>not</strong> post free GitHub release URLs — only the paid
    <code>/download?token=…</code> link from this form.
  </p>
  {err}
  {ok}
  <form method="post" action="/admin/reissue-download#admin-reissue" id="admin-reissue-form">
    <label class="field" for="purchase_id">
      <span class="field-label">Product purchase identifier (RPT-PPI)</span>
      <input id="purchase_id" name="purchase_id" type="text"
             autocomplete="off" required
             placeholder="RPT-A1B2-C3D4-E5F6"
             value="{val}"
             pattern="[Rr][Pp][Tt][-A-Za-z0-9]+"
             title="RPT-XXXX-XXXX-XXXX"/>
    </label>
    <button type="submit" id="admin-reissue-submit">Create secondary download link</button>
  </form>
{admin_section_top_link_html()}</section>
"""


def render_admin_ondemand_mint_section_html(
    *,
    result: dict[str, Any] | None = None,
    error: str = "",
    platform: str = "windows",
) -> str:
    """Admin failsafe: mint live download by platform dropdown — no RPT-PPI required.

    Always shown on authenticated admin page (unlike seed-test, which is env-gated).
    Does not write a customer-recovery audit log; short failsafe copy only.
    """
    err = (
        f'<p class="err" id="ondemand-error" data-admin-focus-result="1">'
        f"{_escape(error)}</p>"
        if error
        else ""
    )
    ok = ""
    if result and result.get("download_url"):
        url = _escape(str(result["download_url"]))
        path = _escape(str(result.get("download_path") or ""))
        plat = _escape(str(result.get("platform") or ""))
        fname = _escape(str(result.get("filename") or ""))
        copy_url = admin_copy_control_html(
            "ondemand-download-link", label="Copy download link"
        )
        ok = f"""
  <div class="ok-msg" id="ondemand-result" role="status" data-admin-focus-result="1" tabindex="-1">
    <p><strong>Admin failsafe link minted</strong> for <strong id="ondemand-result-platform">{plat}</strong>
      (<code id="ondemand-result-filename">{fname}</code>).</p>
    <p>1-hour reusable paid download (not free GitHub; retry if connection drops):</p>
    <p><a id="ondemand-download-link" href="{url}" rel="noopener noreferrer">{url}</a>
      {copy_url}</p>
    <p class="muted">Path: <code id="ondemand-download-path">{path}</code>
      — valid for 1 hour; not written as a customer RPT-PPI recovery event.</p>
  </div>"""
    plat_sel = (platform or "windows").strip().lower()
    options = []
    labels = {
        "windows": "Windows (x64) installer",
        "linux": "Linux (x64) installer",
        "macos": "macOS app package",
        "ios": "iOS app package",
        "android": "Android APK",
    }
    for p in _ADMIN_CATALOG_PLATFORMS:
        sel = " selected" if p == plat_sel else ""
        lab = labels.get(p, p)
        options.append(f'<option value="{p}"{sel}>{_escape(lab)}</option>')
    opts = "\n      ".join(options)
    return f"""
<section id="admin-ondemand-mint" class="card" aria-labelledby="admin-ondemand-heading"
         data-admin-failsafe="1">
  <h2 id="admin-ondemand-heading">Generate download link (admin failsafe)</h2>
  <p class="muted" id="admin-ondemand-note">
    Mint a <strong>live time-limited</strong> download for the current catalog package
    <strong>without</strong> a customer RPT purchase identifier. Use when you need an
    on-demand installer link. Prefer <a href="#admin-reissue">RPT-PPI re-issue</a> when
    the buyer still has their purchase ID. Not a free public unlock.
  </p>
  {err}
  {ok}
  <form method="post" action="/admin/mint-download#admin-ondemand-mint" id="admin-ondemand-mint-form">
    <label class="field" for="ondemand_platform">
      <span class="field-label">Package / device</span>
      <select id="ondemand_platform" name="platform" required>
      {opts}
      </select>
    </label>
    <button type="submit" id="admin-ondemand-mint-submit">Generate live download link</button>
  </form>
{admin_section_top_link_html()}</section>
"""


def render_admin_keygen_failsafe_section_html(
    *,
    result: dict[str, Any] | None = None,
    error: str = "",
    note: str = "",
    platform: str = "",
) -> str:
    """Admin failsafe: mint a fresh KEYGEN for lost licence unlock codes.

    Always shown on authenticated admin page. Operator-only; not a public free unlock.
    """
    err = (
        f'<p class="err" id="keygen-failsafe-error" data-admin-focus-result="1">'
        f"{_escape(error)}</p>"
        if error
        else ""
    )
    ok = ""
    if result and result.get("keygen"):
        kg = _escape(str(result["keygen"]))
        sid = _escape(str(result.get("session_id") or ""))
        plat = _escape(str(result.get("platform") or "") or "—")
        instr = _escape(str(result.get("unlock_instruction") or "USE THIS KEYGEN TO UNLOCK"))
        copy_kg = admin_copy_control_html("admin-minted-keygen", label="Copy keygen")
        ok = f"""
  <div class="ok-msg" id="keygen-failsafe-result" role="status" data-admin-focus-result="1" tabindex="-1">
    <p><strong>Admin failsafe KEYGEN minted</strong> (active Connect unlock).</p>
    <p id="keygen-failsafe-instruction">{instr}</p>
    <p>Keygen: <code id="admin-minted-keygen">{kg}</code> {copy_kg}</p>
    <p class="muted">Session: <code id="keygen-failsafe-session">{sid}</code>
      — platform: <strong id="keygen-failsafe-platform">{plat}</strong>
      — give the customer this code only; not a free public unlock.</p>
  </div>"""
    note_val = _escape(note or "")
    plat_sel = (platform or "").strip().lower()
    options = ['<option value=""' + (" selected" if not plat_sel else "") + ">(optional) any</option>"]
    labels = {
        "windows": "Windows",
        "linux": "Linux",
        "macos": "macOS",
        "ios": "iOS",
        "android": "Android",
    }
    for p in _ADMIN_CATALOG_PLATFORMS:
        sel = " selected" if p == plat_sel else ""
        lab = labels.get(p, p)
        options.append(f'<option value="{p}"{sel}>{_escape(lab)}</option>')
    opts = "\n      ".join(options)
    return f"""
<section id="admin-keygen-failsafe" class="card" aria-labelledby="admin-keygen-failsafe-heading"
         data-admin-keygen-failsafe="1">
  <h2 id="admin-keygen-failsafe-heading">Generate KEYGEN (admin failsafe)</h2>
  <p class="muted" id="admin-keygen-failsafe-note">
    Mint a <strong>new active licence unlock keygen</strong> for a customer who can
    still be validated manually but <strong>lost their emailed KEYGEN</strong>.
    Creates an operator-only entitlement (not Stripe checkout, not free GitHub).
    Revoke later if the recovery was wrong.
  </p>
  {err}
  {ok}
  <form method="post" action="/admin/mint-keygen#admin-keygen-failsafe" id="admin-keygen-failsafe-form">
    <label class="field" for="keygen_failsafe_platform">
      <span class="field-label">Platform (optional)</span>
      <select id="keygen_failsafe_platform" name="platform">
      {opts}
      </select>
    </label>
    <label class="field" for="keygen_failsafe_note">
      <span class="field-label">Operator note (optional)</span>
      <input id="keygen_failsafe_note" name="note" type="text" maxlength="200"
             placeholder="e.g. ticket #123 lost email" value="{note_val}"/>
    </label>
    <button type="submit" id="admin-keygen-failsafe-submit">Generate KEYGEN</button>
  </form>
{admin_section_top_link_html()}</section>
"""


def render_admin_tester_month_section_html(
    *,
    result: dict[str, Any] | None = None,
    error: str = "",
    platform: str = "windows",
) -> str:
    """Admin: mint one-month free tester subscription (download + keygen).

    PPI is always the literal label ``TESTER - one month``. Not listed in Paid
    download grants; Licence database shows the row only after keygen activation.
    """
    err = (
        f'<p class="err" id="tester-month-error" data-admin-focus-result="1">'
        f"{_escape(error)}</p>"
        if error
        else ""
    )
    ok = ""
    if result and (result.get("download_url") or result.get("keygen")):
        url = _escape(str(result.get("download_url") or ""))
        path = _escape(str(result.get("download_path") or ""))
        plat = _escape(str(result.get("platform") or ""))
        fname = _escape(str(result.get("filename") or ""))
        kg = _escape(str(result.get("keygen") or ""))
        ppi = _escape(str(result.get("ppi") or result.get("purchase_id") or "TESTER - one month"))
        vu = result.get("valid_until")
        try:
            vu_s = _escape(str(float(vu))) if vu is not None else ""
        except (TypeError, ValueError):
            vu_s = ""
        copy_kg = admin_copy_control_html("tester-month-keygen", label="Copy keygen")
        copy_url = admin_copy_control_html(
            "tester-month-download-link", label="Copy download link"
        )
        copy_ppi = admin_copy_control_html("tester-month-ppi", label="Copy PPI")
        ok = f"""
  <div class="ok-msg" id="tester-month-result" role="status" data-admin-focus-result="1" tabindex="-1">
    <p><strong>One-month tester subscription minted</strong> for
      <strong id="tester-month-result-platform">{plat}</strong>
      (<code id="tester-month-result-filename">{fname}</code>).</p>
    <p>PPI: <code id="tester-month-ppi">{ppi}</code> {copy_ppi}
      — expires after one month (valid_until
      <code id="tester-month-valid-until">{vu_s}</code>).</p>
    <p>Keygen: <code id="tester-month-keygen">{kg}</code> {copy_kg}</p>
    <p>Download (1-hour status-host token, reusable until expiry; not free GitHub):</p>
    <p><a id="tester-month-download-link" href="{url}" rel="noopener noreferrer">{url}</a>
      {copy_url}</p>
    <p class="muted">Path: <code id="tester-month-download-path">{path}</code>
      — not listed under Paid download grants; Licence database lists this key
      only after the tester activates it in the app.</p>
  </div>"""
    plat_sel = (platform or "windows").strip().lower()
    options = []
    labels = {
        "windows": "Windows (x64) installer",
        "linux": "Linux (x64) installer",
        "macos": "macOS app package",
        "ios": "iOS app package",
        "android": "Android APK",
    }
    for p in _ADMIN_CATALOG_PLATFORMS:
        sel = " selected" if p == plat_sel else ""
        lab = labels.get(p, p)
        options.append(f'<option value="{p}"{sel}>{_escape(lab)}</option>')
    opts = "\n      ".join(options)
    return f"""
<section id="admin-tester-month" class="card" aria-labelledby="admin-tester-month-heading"
         data-admin-tester-month="1">
  <h2 id="admin-tester-month-heading">One-month tester subscription</h2>
  <p class="muted" id="admin-tester-month-note">
    Mint a <strong>one-month free</strong> Connect subscription for build testing:
    platform installer download + keygen with PPI
    <code>TESTER - one month</code>. Expires after one calendar month.
    Does <strong>not</strong> appear in Paid download grants (paid customers only).
    Appears in Licence database only after the keygen is activated.
  </p>
  {err}
  {ok}
  <form method="post" action="/admin/mint-tester-month#admin-tester-month" id="admin-tester-month-form">
    <label class="field" for="tester_month_platform">
      <span class="field-label">Package / device</span>
      <select id="tester_month_platform" name="platform" required>
      {opts}
      </select>
    </label>
    <button type="submit" id="admin-tester-month-submit">Generate one-month tester</button>
  </form>
{admin_section_top_link_html()}</section>
"""


def render_seed_test_purchase_section_html(
    *,
    result: dict[str, Any] | None = None,
    error: str = "",
    platform: str = "windows",
) -> str:
    """Dev/staging-only card: seed a paid test grant (RPT-… + platform).

    Hidden unless :func:`seed_test_purchase_enabled` (``RPT_ADMIN_SEED_PURCHASE=1``).
    Still creates a full-price paid grant + 1-hour download token — never a free public unlock.
    """
    if not seed_test_purchase_enabled():
        return ""
    err = (
        f'<p class="err" id="seed-purchase-error" data-admin-focus-result="1">'
        f"{_escape(error)}</p>"
        if error
        else ""
    )
    ok = ""
    if result and result.get("purchase_id"):
        pid = _escape(str(result["purchase_id"]))
        plat = _escape(str(result.get("platform") or ""))
        fname = _escape(str(result.get("filename") or ""))
        url = _escape(str(result.get("download_url") or ""))
        path = _escape(str(result.get("download_path") or ""))
        copy_pid = admin_copy_control_html("seed-purchase-id", label="Copy purchase ID")
        copy_url = admin_copy_control_html(
            "seed-download-link", label="Copy download link"
        )
        ok = f"""
  <div class="ok-msg" id="seed-purchase-result" role="status" data-admin-focus-result="1" tabindex="-1">
    <p><strong>Test purchase seeded</strong> (local/staging only).</p>
    <p>Product purchase identifier:
      <code id="seed-purchase-id">{pid}</code> {copy_pid}</p>
    <p>Platform: <strong id="seed-purchase-platform">{plat}</strong>
      — <code id="seed-purchase-filename">{fname}</code></p>
    <p>1-hour reusable paid download (not free GitHub):
      <a id="seed-download-link" href="{url}" rel="noopener noreferrer">{url}</a>
      {copy_url}</p>
    <p class="muted">Path: <code id="seed-download-path">{path}</code>
      — valid for 1 hour (audit stamp does not burn the link). Use the purchase ID
      above in the re-issue form after the window expires or if a new token is needed.</p>
  </div>"""
    plat_sel = (platform or "windows").strip().lower()
    options = []
    for p in ("windows", "linux", "macos", "ios", "android"):
        sel = " selected" if p == plat_sel else ""
        options.append(f'<option value="{p}"{sel}>{p}</option>')
    opts = "\n      ".join(options)
    return f"""
<section id="admin-seed-purchase" class="card" aria-labelledby="admin-seed-purchase-heading"
         data-dev-only="1">
  <h2 id="admin-seed-purchase-heading">Seed test purchase (dev / staging)</h2>
  <p class="muted" id="admin-seed-purchase-note">
    <strong>Dev-only.</strong> Creates a full-price paid grant with a unique
    <code>RPT-…</code> product purchase identifier for testing re-issue.
    Enabled only when <code>RPT_ADMIN_SEED_PURCHASE=1</code>.
    Does <strong>not</strong> open free public unlocks — download still needs the time-limited token.
  </p>
  {err}
  {ok}
  <form method="post" action="/admin/seed-test-purchase#admin-seed-purchase" id="admin-seed-purchase-form">
    <label class="field" for="seed_platform">
      <span class="field-label">Platform</span>
      <select id="seed_platform" name="platform" required>
      {opts}
      </select>
    </label>
    <button type="submit" id="admin-seed-purchase-submit">Seed test purchase (RPT-…)</button>
  </form>
{admin_section_top_link_html()}</section>
"""


def _admin_auth_shell_css() -> str:
    return f"""
{admin_theme_css()}
body{{margin:0;min-height:100vh;display:flex;flex-direction:column;align-items:center;
justify-content:center;padding:1rem;box-sizing:border-box}}
.login-wrap{{width:100%;max-width:26rem}}
form.admin-auth-form{{background:var(--bg-elevated);padding:1.5rem 1.75rem;border-radius:12px;
border:1px solid var(--border);width:100%;box-sizing:border-box}}
form.admin-auth-form > label{{display:block;font-size:0.85rem;margin:0.6rem 0 0.25rem;
color:var(--fg-muted)}}
form.admin-auth-form input[type="text"],
form.admin-auth-form input[type="password"],
form.admin-auth-form input:not([type]){{width:100%;box-sizing:border-box;padding:0.55rem 0.65rem;
border-radius:8px;border:1px solid var(--input-border);background:var(--input-bg);color:var(--fg)}}
button{{margin-top:1rem;width:100%;padding:0.7rem;border:0;border-radius:8px;
background:var(--btn-bg);color:var(--btn-fg);font-weight:600;cursor:pointer}}
.err{{color:var(--err);font-size:0.9rem}}
.ok-msg{{color:var(--badge-ok-fg);background:var(--badge-ok-bg);padding:0.5rem 0.65rem;
border-radius:8px;font-size:0.88rem;line-height:1.4}}
h1{{font-size:1.1rem;margin:0 0 0.5rem;color:var(--fg)}}
.note{{color:var(--fg-muted);font-size:0.85rem;margin:0 0 0.75rem;line-height:1.35}}
.secret-box{{font-family:ui-monospace,Consolas,monospace;font-size:0.95rem;word-break:break-all;
background:var(--input-bg);border:1px solid var(--input-border);padding:0.65rem;border-radius:8px;
margin:0.5rem 0;user-select:all}}
.uri-box{{font-size:0.72rem;word-break:break-all;color:var(--fg-muted);margin:0.35rem 0 0.75rem}}
.qr-wrap{{text-align:center;margin:0.75rem 0}}
.qr-wrap img{{max-width:14rem;height:auto;background:#fff;padding:0.5rem;border-radius:8px;
border:1px solid var(--border)}}
"""


def render_login_html(*, error: str = "") -> bytes:
    """Login: heading + username + password + 6-digit TOTP (when enrolled)."""
    err = (
        f'<p class="err" id="admin-error">{_escape(error)}</p>' if error else ""
    )
    body = f"""<!DOCTYPE html>
<html lang="en"><head>
<meta charset="utf-8"/><meta name="viewport" content="width=device-width, initial-scale=1"/>
<meta name="color-scheme" content="light dark"/>
<title>OPERATOR ADMIN PAGES</title>
<style>
{_admin_auth_shell_css()}
</style>
{admin_theme_boot_script()}
</head><body>
<div class="login-wrap">
{admin_theme_picker_html()}
<form method="post" action="/admin/login" id="admin-login-form" class="admin-auth-form"
      data-admin-login="1">
  <h1 id="admin-login-heading">OPERATOR ADMIN PAGES</h1>
  {err}
  <label for="username">Username</label>
  <input id="username" name="username" autocomplete="username" required/>
  <label for="password">Password</label>
  <input id="password" name="password" type="password" autocomplete="current-password" required/>
  <label for="totp_code">Authenticator code</label>
  <input id="totp_code" name="totp_code" type="text" inputmode="numeric"
         pattern="[0-9]{{6}}" maxlength="8" autocomplete="one-time-code"
         placeholder="123456" data-admin-login-totp="1"/>
  <button type="submit" id="admin-login-submit">Sign in</button>
</form>
</div>
</body></html>
"""
    return body.encode("utf-8")


def render_2fa_setup_html(
    *,
    secret_b32: str,
    otpauth: str = "",
    account: str = "admin",
    error: str = "",
    message: str = "",
) -> bytes:
    """Bare enrollment: QR + secret + 6-digit code (no prose blurbs)."""
    try:
        from admin_2fa import otpauth_uri  # type: ignore
    except Exception:  # noqa: BLE001
        from status_page.admin_2fa import otpauth_uri  # type: ignore
    try:
        from qr_encode import qr_data_url_svg  # type: ignore
    except Exception:  # noqa: BLE001
        from status_page.qr_encode import qr_data_url_svg  # type: ignore

    uri = otpauth or otpauth_uri(secret_b32, account=account)
    qr_src = qr_data_url_svg(uri)
    err = f'<p class="err" id="admin-2fa-setup-error">{_escape(error)}</p>' if error else ""
    msg = (
        f'<p class="ok-msg" id="admin-2fa-setup-message">{_escape(message)}</p>'
        if message
        else ""
    )
    body = f"""<!DOCTYPE html>
<html lang="en"><head>
<meta charset="utf-8"/><meta name="viewport" content="width=device-width, initial-scale=1"/>
<meta name="color-scheme" content="light dark"/>
<title>Set up authenticator</title>
<style>
{_admin_auth_shell_css()}
</style>
{admin_theme_boot_script()}
</head><body>
<div class="login-wrap">
{admin_theme_picker_html()}
<form method="post" action="/admin/2fa/setup" id="admin-2fa-setup-form" class="admin-auth-form"
      data-admin-2fa-setup="1">
  <h1 id="admin-2fa-setup-heading">Set up authenticator</h1>
  {msg}{err}
  <div class="qr-wrap" id="admin-2fa-qr-wrap">
    <img id="admin-2fa-qr" alt="Authenticator QR code" width="220" height="220"
         src="{qr_src}" data-otpauth-qr="1"/>
  </div>
  <div class="secret-box" id="admin-2fa-secret" data-totp-secret="1">{_escape(secret_b32)}</div>
  <p class="uri-box" id="admin-2fa-otpauth" data-otpauth-uri="1" hidden>{_escape(uri)}</p>
  <label for="totp_code">Code</label>
  <input id="totp_code" name="totp_code" type="text" inputmode="numeric"
         pattern="[0-9]{{6}}" maxlength="8" autocomplete="one-time-code" required
         placeholder="123456"/>
  <button type="submit" id="admin-2fa-setup-submit">Confirm</button>
</form>
</div>
</body></html>
"""
    return body.encode("utf-8")


def render_2fa_verify_html(*, error: str = "") -> bytes:
    """Legacy bare TOTP-only form (enrolled users use login with password+code)."""
    err = f'<p class="err" id="admin-2fa-verify-error">{_escape(error)}</p>' if error else ""
    body = f"""<!DOCTYPE html>
<html lang="en"><head>
<meta charset="utf-8"/><meta name="viewport" content="width=device-width, initial-scale=1"/>
<meta name="color-scheme" content="light dark"/>
<title>Authenticator code</title>
<style>
{_admin_auth_shell_css()}
</style>
{admin_theme_boot_script()}
</head><body>
<div class="login-wrap">
{admin_theme_picker_html()}
<form method="post" action="/admin/2fa/verify" id="admin-2fa-verify-form" class="admin-auth-form"
      data-admin-2fa-verify="1">
  <h1 id="admin-2fa-verify-heading">Authenticator code</h1>
  {err}
  <label for="totp_code">Code</label>
  <input id="totp_code" name="totp_code" type="text" inputmode="numeric"
         pattern="[0-9]{{6}}" maxlength="8" autocomplete="one-time-code" required
         placeholder="123456" autofocus/>
  <button type="submit" id="admin-2fa-verify-submit">Verify</button>
</form>
</div>
</body></html>
"""
    return body.encode("utf-8")


def _status_badge(ok: bool, yes: str = "ready", no: str = "not set") -> str:
    cls = "ok" if ok else "bad"
    label = yes if ok else no
    return f'<span class="badge {cls}" data-ready="{"1" if ok else "0"}">{_escape(label)}</span>'


# Real-looking secret material only (not docs prefixes like sk_test_… / whsec_…).
_SECRET_LEAK_RE = re.compile(
    r"(?:sk_live_|sk_test_|rk_live_|rk_test_)[A-Za-z0-9]{10,}"
    r"|whsec_[A-Za-z0-9]{10,}"
    r"|RPT_ADMIN_PASSWORD\s*=\s*\S+",
    re.IGNORECASE,
)


def _html_contains_secret_material(html: str) -> bool:
    """True when body looks like it embeds a real Stripe/admin secret value."""
    return bool(_SECRET_LEAK_RE.search(html or ""))


def _redact_secret_material(html: str) -> str:
    """Replace real-looking secret values; leave doc placeholders (ellipsis) alone."""
    if not html:
        return html
    return _SECRET_LEAK_RE.sub("[redacted]", html)


def render_processor_settings_html(
    view: dict[str, Any] | None = None,
    *,
    message: str = "",
    error: str = "",
    plugin_views: list[dict[str, Any]] | None = None,
) -> str:
    """HTML fragment: plugin-driven processor detail + variable entry forms.

    Authenticated admin only. Secret fields are write-only (never prefilled).
    """
    v = view if view is not None else processor_settings_view()
    plugins = plugin_views if plugin_views is not None else processor_plugin_views()
    stripe_mode = str(v.get("stripe_mode") or "unconfigured")
    base = str(v.get("public_base_url") or "")
    webhook_url = str(
        v.get("webhook_endpoint_url") or stripe_webhook_endpoint_url(production=True)
    )
    webhook_events = v.get("webhook_events") or list(STRIPE_WEBHOOK_EVENTS)
    events_csv = ", ".join(str(e) for e in webhook_events)
    msg_html = (
        f'<p class="ok-msg" id="processor-apply-ok">{_escape(message)}</p>' if message else ""
    )
    err_html = (
        f'<p class="err" id="processor-apply-error">{_escape(error)}</p>' if error else ""
    )

    plugin_blocks: list[str] = []
    for pv in plugins:
        pid = _escape(str(pv.get("id") or ""))
        name = _escape(str(pv.get("display_name") or ""))
        role = _escape(str(pv.get("role") or ""))
        desc = _escape(str(pv.get("description") or ""))
        ready = pv.get("readiness") or {}
        ready_flag = bool(ready.get("ready") or ready.get("fulfilment_ready") or ready.get("checkout_ready"))
        conn_badge = _status_badge(ready_flag, "connection ready", "needs variables")
        links = []
        for ln in pv.get("dashboard_links") or []:
            links.append(
                f'<a href="{_escape(str(ln.get("url") or ""))}" target="_blank" '
                f'rel="noopener noreferrer" id="link-{pid}-{_escape(str(ln.get("label") or "").lower().replace(" ", "-"))}">'
                f'{_escape(str(ln.get("label") or ""))}</a>'
            )
        links_html = " · ".join(links) if links else ""
        # Variable checklist + form fields
        rows = []
        form_fields = []
        for var in pv.get("variables") or []:
            key = str(var.get("key") or "")
            configured = bool(var.get("configured"))
            kind = str(var.get("status_kind") or ("set" if configured else "not_set"))
            if kind == "optional_ok":
                row_badge = _status_badge(True, "optional (unit_amount)", "not set")
            elif kind == "set" or configured:
                row_badge = _status_badge(True, "set", "not set")
            else:
                row_badge = _status_badge(False, "set", "not set")
            rows.append(
                "<tr>"
                f"<td><code class=\"var-key\">{_escape(key)}</code></td>"
                f"<td>{_escape(str(var.get('label') or ''))}</td>"
                f"<td>{'required' if var.get('required') else 'optional'}</td>"
                f"<td>{row_badge}</td>"
                f"<td class=\"muted\">{_escape(str(var.get('purpose') or ''))}</td>"
                "</tr>"
            )
            itype = str(var.get("input_type") or "text")
            if var.get("secret"):
                itype = "password"
            ph = _escape(str(var.get("placeholder") or ""))
            autocomplete = "off" if var.get("secret") else "on"
            value_attr = 'value="" ' if var.get("secret") else ""
            req_mark = " *" if var.get("required") else ""
            form_fields.append(
                f'<label class="field" for="fld-{pid}-{_escape(key)}">'
                f'<span class="field-label">{_escape(str(var.get("label") or key))}'
                f"{req_mark}</span>"
                f'<span class="field-key"><code>{_escape(key)}</code></span>'
                f'<input id="fld-{pid}-{_escape(key)}" name="{_escape(key)}" type="{_escape(itype)}" '
                f'placeholder="{ph}" autocomplete="{autocomplete}" '
                f"{value_attr}"
                f'/>'
                f'<span class="field-purpose muted">{_escape(str(var.get("purpose") or ""))}</span>'
                f"</label>"
            )
        table = "\n".join(rows) if rows else "<tr><td colspan=5>No variables</td></tr>"
        fields_html = "\n".join(form_fields)
        extra_status = ""
        if pid == "stripe":
            pay_page = str(v.get("stripe_payment_page_url") or stripe_payment_page_url())
            plink = str(v.get("stripe_payment_link_id") or stripe_payment_link_id())
            remaining = v.get("stripe_whats_next")
            if remaining is None:
                remaining = stripe_remaining_required_keys()
            remaining_list = list(remaining or [])
            if remaining_list:
                next_items = "".join(
                    f"<li><code>{_escape(str(k))}</code></li>" for k in remaining_list
                )
                next_html = (
                    f'<div id="stripe-whats-next" class="whats-next">'
                    f"<strong>What&apos;s next for paid downloads:</strong>"
                    f"<ul id=\"stripe-remaining-required\">{next_items}</ul>"
                    f"<p class=\"muted\">Subscription Payment Link alone does not enable "
                    f"Checkout token fulfilment — enter the secret key and webhook signing "
                    f"secret from Stripe Dashboard → Developers.</p></div>"
                )
            else:
                next_html = (
                    '<div id="stripe-whats-next" class="whats-next">'
                    "<p><strong>Paid-download connection complete</strong> "
                    "(secret + webhook present).</p></div>"
                )
            extra_status = f"""
  <dl id="admin-stripe-status" class="status-list">
    <div><dt>Payment page</dt><dd id="stripe-payment-page"><a href="{_escape(pay_page)}" target="_blank" rel="noopener noreferrer" id="link-stripe-payment-page">{_escape(pay_page)}</a></dd></div>
    <div><dt>Payment Link id</dt><dd id="stripe-payment-link-id"><code>{_escape(plink)}</code></dd></div>
    <div><dt>Secret key</dt><dd id="stripe-secret-status">{_status_badge(bool(v.get("stripe_configured")))}</dd></div>
    <div><dt>Key mode</dt><dd id="stripe-key-mode">{_escape(stripe_mode)}</dd></div>
    <div><dt>Webhook signing secret</dt><dd id="stripe-webhook-status">{_status_badge(bool(v.get("stripe_webhook_configured")))}</dd></div>
    <div><dt>Price id (optional)</dt><dd id="stripe-price-status">{_status_badge(bool(v.get("stripe_price_id_set")), "set", "empty · unit_amount 245")}</dd></div>
    <div><dt>Checkout ready</dt><dd id="stripe-checkout-ready">{_status_badge(bool(v.get("stripe_checkout_ready")))}</dd></div>
    <div><dt>Fulfilment ready (key + webhook)</dt><dd id="stripe-fulfilment-ready">{_status_badge(bool(v.get("stripe_fulfilment_ready")))}</dd></div>
    <div><dt>Public base URL</dt><dd id="stripe-public-base"><code>{_escape(base)}</code></dd></div>
    <div><dt>Webhook endpoint (paste into Stripe)</dt>
      <dd id="stripe-webhook-url"><code id="stripe-webhook-endpoint-url">{_escape(webhook_url)}</code></dd></div>
    <div><dt>Webhook events</dt>
      <dd id="stripe-webhook-events"><code>{_escape(events_csv)}</code></dd></div>
  </dl>
  <p class="muted" id="stripe-webhook-paste-help">
    Stripe Dashboard → Developers → Webhooks → Add endpoint → Endpoint URL =
    <strong id="stripe-webhook-url-strong">{_escape(webhook_url)}</strong>
    · Events to send: <strong>{_escape(events_csv)}</strong>.
    After create, paste the signing secret into <code>STRIPE_WEBHOOK_SECRET</code>
    (Render Environment or Save Stripe connection below).
  </p>
  {next_html}"""
        if pid == "bmc":
            extra_status = f"""
  <dl id="admin-bmc-status" class="status-list">
    <div><dt>Public tip URL</dt><dd id="bmc-tip-url"><a href="{_escape(str(v.get('bmc_tip_url') or ''))}" target="_blank" rel="noopener noreferrer">{_escape(str(v.get('bmc_tip_url') or ''))}</a></dd></div>
    <div><dt>Footer label</dt><dd id="bmc-tip-label">{_escape(str(v.get('bmc_tip_label') or ''))}</dd></div>
    <div><dt>Role</dt><dd id="bmc-role">{_escape(str(v.get('bmc_role') or ''))}</dd></div>
  </dl>"""
        plugin_blocks.append(
            f"""
<article class="processor-plugin" id="processor-plugin-{pid}" data-processor="{pid}">
  <header class="plugin-head">
    <h3 id="admin-{pid}-heading">{name}</h3>
    <span class="plugin-role">{role}</span>
    <span id="{pid}-connection-badge">{conn_badge}</span>
  </header>
  <p class="muted plugin-desc">{desc}</p>
  {extra_status}
  <p class="ops-links" id="admin-{pid}-links">Operator dashboards: {links_html}</p>
  <h4>Variables to enter</h4>
  <table class="var-table" id="{pid}-variables-table">
    <thead><tr><th>Env key</th><th>Label</th><th>Need</th><th>Status</th><th>Purpose</th></tr></thead>
    <tbody>
{table}
    </tbody>
  </table>
  <form method="post" action="/admin/processors/apply" class="processor-form"
        id="form-processor-{pid}" data-processor="{pid}">
    <input type="hidden" name="plugin_id" value="{pid}"/>
    {fields_html}
    <button type="submit" id="btn-apply-{pid}">Save {name} connection</button>
    <p class="muted field-note">Secret fields are <strong>write-only</strong> (always empty on purpose).
    Leave blank to keep a value already on the server. After Save, the table badge
    <strong>set</strong> is the truth — not the empty box. Values persist to the
    server data store and process env (never git). For production permanence also
    set the same keys in the Render dashboard Environment.</p>
  </form>
</article>
"""
        )

    plugins_html = "\n".join(plugin_blocks)
    # Plugin option list for selector navigation
    option_links = " · ".join(
        f'<a href="#processor-plugin-{_escape(str(p.get("id") or ""))}">'
        f'{_escape(str(p.get("display_name") or ""))}</a>'
        for p in plugins
    )
    frag = f"""
<section id="admin-processor-settings" class="card">
  <h2>Payment processor settings</h2>
  <p class="muted">Each connection option is a <strong>processor plugin</strong> with the correct
  variables for that payment path. Secrets stay on the server — never shown after save.
  Prefer host/Render env for production permanence (survives redeploy); local apply
  wires the running process. Licence/grant SQLite is separate durable state — residual
  peer wipe does not erase it.</p>
  <div class="muted" id="admin-key-howto" style="margin:0.75rem 0 1rem;padding:0.75rem 0.9rem;border:1px solid var(--border);border-radius:10px">
    <p style="margin:0 0 0.5rem"><strong>Where to find keys (one at a time)</strong> — never commit secrets to git.</p>
    <ol style="margin:0;padding-left:1.25rem;line-height:1.45">
      <li><code>STRIPE_SECRET_KEY</code> — Stripe Dashboard → Developers →
        <a href="https://dashboard.stripe.com/apikeys" target="_blank" rel="noopener noreferrer">API keys</a>
        → Secret key (<code>sk_live_…</code> or <code>sk_test_…</code>). Paste → Save Stripe.</li>
      <li><code>STRIPE_WEBHOOK_SECRET</code> — Developers →
        <a href="https://dashboard.stripe.com/webhooks" target="_blank" rel="noopener noreferrer">Webhooks</a>
        → your endpoint (or add one to <code>…/webhook/stripe</code>) → Signing secret
        (<code>whsec_…</code>). Paste → Save Stripe.</li>
      <li><code>STRIPE_CHECKOUT_PRICE_ID</code> — <strong>optional</strong>. Leave empty to use
        built-in Monthly {_escape(PRICE_LABEL)} / Yearly {_escape(PRICE_YEARLY_LABEL)} Checkout
        unit amounts. Only set a Dashboard Price id if you deliberately override catalog pricing.</li>
      <li><code>RPT_ASSET_FETCH_TOKEN</code> — shared secret you choose (long random string).
        Set the <strong>same</strong> value on residual paid-asset hosts (e.g. IS VPS
        <code>host_paid_assets</code>) and on this status host (or Render env). Not from Stripe.
        Generate with a password manager if you do not have one yet.</li>
      <li><code>RPT_PAYMENT_DATA_DIR</code> — optional path for the durable licence + grant
        SQLite store. Prefer a persistent disk so admin history survives host redeploy;
        residual fleet wipe never targets this DB.</li>
    </ol>
    <p style="margin:0.5rem 0 0">After each Save, confirm the table badge flips to
    <strong>set</strong> (secret boxes stay empty on purpose). Also set the same keys on
    <strong>Render → Environment</strong> so redeploys keep them.</p>
  </div>
  <nav class="plugin-nav" id="processor-plugin-nav" aria-label="Processor plugins">{option_links}</nav>
  {msg_html}{err_html}
{plugins_html}
{admin_section_top_link_html()}</section>
"""
    # Block only real-looking secret values, not doc prefixes (sk_test_… / whsec_…).
    if _html_contains_secret_material(frag):
        return (
            '<section id="admin-processor-settings" class="card"><p class="err">'
            "Settings redacted (secret material detected).</p>"
            f"{admin_section_top_link_html()}</section>"
        )
    return frag


def _render_node_usage_section(
    node_usage_rows: list[Any] | None = None,
    *,
    live: bool = True,
) -> str:
    """Fleet bandwidth panel (below nav). Injected rows skip live HTTP probes."""
    try:
        from admin_node_usage import render_admin_node_usage_section_html
    except Exception:  # noqa: BLE001
        try:
            from status_page.admin_node_usage import (  # type: ignore
                render_admin_node_usage_section_html,
            )
        except Exception as exc:  # noqa: BLE001
            return (
                f'<section id="admin-node-usage" class="card">'
                f"<p class=\"err\">Node usage panel unavailable: "
                f"{_escape(str(exc)[:120])}</p>"
                f"{admin_section_top_link_html()}</section>"
            )
    return render_admin_node_usage_section_html(
        node_usage_rows,
        live=live if node_usage_rows is None else False,
        top_link_html=admin_section_top_link_html(),
    )



def _admin_shared_css() -> str:
    """Shared admin layout CSS (sidebar + cards + forms)."""
    return f"""
{admin_theme_css()}
*{{box-sizing:border-box}}
body{{margin:0;font-family:system-ui,-apple-system,Segoe UI,Roboto,sans-serif;
  background:var(--bg);color:var(--fg);min-height:100vh}}
a{{color:var(--link)}}
.admin-shell{{display:flex;min-height:100vh}}
.admin-sidebar{{width:16.5rem;flex-shrink:0;background:var(--bg-elevated);
  border-right:1px solid var(--border);padding:1rem 0.75rem;display:flex;flex-direction:column;gap:0.35rem}}
.admin-sidebar.collapsed{{width:3.25rem}}
.admin-sidebar.collapsed .sb-label,.admin-sidebar.collapsed .sb-sub,
.admin-sidebar.collapsed .sb-group-title{{display:none}}
.admin-sidebar.collapsed .sb-btn{{justify-content:center;padding:0.55rem}}
.sb-brand{{font-weight:700;font-size:0.95rem;padding:0.35rem 0.5rem 0.75rem;color:var(--fg)}}
.sb-toggle{{border:1px solid var(--border);background:var(--input-bg);color:var(--fg);
  border-radius:8px;padding:0.4rem 0.55rem;cursor:pointer;font-size:0.8rem;margin-bottom:0.5rem}}
.sb-btn{{display:flex;align-items:center;gap:0.5rem;width:100%;text-align:left;
  border:1px solid transparent;background:transparent;color:var(--fg);border-radius:10px;
  padding:0.55rem 0.65rem;cursor:pointer;font-size:0.9rem;font-weight:600;text-decoration:none}}
.sb-btn:hover{{background:var(--badge-ok-bg);border-color:var(--border)}}
.sb-btn.active{{background:var(--btn-bg);color:var(--btn-fg);border-color:var(--btn-bg)}}
.sb-btn .sb-ico{{width:1.25rem;text-align:center;opacity:0.9}}
.sb-group{{border:1px solid var(--border);border-radius:12px;margin:0.25rem 0;overflow:hidden;
  background:var(--bg)}}
.sb-group > summary{{list-style:none;cursor:pointer}}
.sb-group > summary::-webkit-details-marker{{display:none}}
.sb-group-title{{display:flex;align-items:center;gap:0.5rem;padding:0.55rem 0.65rem;
  font-weight:700;font-size:0.88rem}}
.sb-sub{{display:flex;flex-direction:column;padding:0.25rem 0.4rem 0.5rem;gap:0.2rem}}
.sb-sub a{{display:block;padding:0.4rem 0.55rem;border-radius:8px;font-size:0.82rem;
  text-decoration:none;color:var(--fg);border:1px solid transparent}}
.sb-sub a:hover{{background:var(--badge-ok-bg);border-color:var(--border)}}
.admin-main{{flex:1;padding:1.25rem 1.5rem 2.5rem;min-width:0}}
.top{{display:flex;gap:1rem;align-items:center;margin-bottom:1rem;flex-wrap:wrap}}
h1{{font-size:1.25rem;margin:0}} h2{{font-size:1.05rem;margin:0 0 0.5rem}}
table{{border-collapse:collapse;width:100%;max-width:64rem;font-size:0.9rem}}
th,td{{border-bottom:1px solid var(--table-border);padding:0.45rem 0.5rem;text-align:left}}
th{{color:var(--fg-muted);font-weight:600}}
.card{{background:var(--bg-elevated);border:1px solid var(--border);border-radius:12px;
padding:1rem 1.15rem;margin:1rem 0;max-width:64rem}}
.muted{{color:var(--fg-muted);font-size:0.95rem;line-height:1.55}}
.badge{{display:inline-block;padding:0.15rem 0.5rem;border-radius:6px;font-size:0.8rem;font-weight:600}}
.badge.ok{{background:var(--badge-ok-bg);color:var(--badge-ok-fg)}}
.badge.bad{{background:var(--badge-bad-bg);color:var(--badge-bad-fg)}}
.warn{{color:var(--badge-bad-fg);background:var(--badge-bad-bg);padding:0.6rem 0.75rem;
border-radius:8px;font-size:0.9rem;line-height:1.4;margin:0.5rem 0}}
code{{font-size:0.85rem;word-break:break-all}}
.ok-msg{{color:var(--badge-ok-fg);background:var(--badge-ok-bg);padding:0.5rem 0.75rem;border-radius:8px}}
.err{{color:var(--err)}}
.admin-copy-row{{display:inline-flex;align-items:center;gap:0.4rem;flex-wrap:wrap;
margin-left:0.35rem;vertical-align:middle}}
.admin-copy-btn{{cursor:pointer;border:0;border-radius:8px;padding:0.3rem 0.65rem;
font-size:0.8rem;font-weight:600;background:var(--btn-bg);color:var(--btn-fg)}}
.admin-copy-btn:hover{{filter:brightness(1.08)}}
.admin-copy-status{{font-size:0.8rem;font-weight:600;color:var(--badge-ok-fg);min-height:1em}}
.admin-top-link{{margin:0.85rem 0 0;font-size:0.85rem}}
.admin-arch-body p{{margin:0 0 0.85rem;line-height:1.55}}
#admin-reissue-form label.field,#admin-seed-purchase-form label.field,#admin-ondemand-mint-form label.field,
#admin-keygen-failsafe-form label.field,#admin-tester-month-form label.field{{display:block;margin:0.65rem 0}}
#admin-reissue-form .field-label,#admin-seed-purchase-form .field-label,#admin-ondemand-mint-form .field-label,
#admin-keygen-failsafe-form .field-label,#admin-tester-month-form .field-label{{display:block;font-weight:600;font-size:0.9rem;margin-bottom:0.25rem}}
#admin-reissue-form input,#admin-seed-purchase-form select,#admin-ondemand-mint-form select,
#admin-keygen-failsafe-form select,#admin-keygen-failsafe-form input,#admin-tester-month-form select
{{width:100%;max-width:28rem;box-sizing:border-box;padding:0.5rem 0.6rem;border-radius:8px;
border:1px solid var(--input-border);background:var(--input-bg);color:var(--fg)}}
#admin-reissue-form button,#admin-seed-purchase-form button,#admin-ondemand-mint-form button,
#admin-keygen-failsafe-form button,#admin-tester-month-form button{{margin-top:0.75rem;padding:0.55rem 1rem;
border:0;border-radius:8px;background:var(--btn-bg);color:var(--btn-fg);font-weight:600;cursor:pointer}}
.processor-form label.field{{display:block;margin:0.65rem 0}}
.processor-form input{{width:100%;max-width:28rem;box-sizing:border-box;padding:0.5rem 0.6rem;
border-radius:8px;border:1px solid var(--input-border);background:var(--input-bg);color:var(--fg)}}
.processor-form button{{margin-top:0.75rem;padding:0.55rem 1rem;border:0;border-radius:8px;
background:var(--btn-bg);color:var(--btn-fg);font-weight:600;cursor:pointer}}
@media (max-width:800px){{.admin-shell{{flex-direction:column}}.admin-sidebar{{width:100%}}}}
"""


def _admin_sidebar_html(*, active: str = "home") -> str:
    """Left collapsible sidebar with button-style expandable nav groups."""
    home_cls = "sb-btn active" if active == "home" else "sb-btn"
    link_open = " open" if active == "link-generation" else ""
    lic_open = " open" if active == "licences" else ""
    proc_cls = "sb-btn active" if active == "processors" else "sb-btn"
    fleet_cls = "sb-btn active" if active == "fleet" else "sb-btn"
    acct_cls = "sb-btn active" if active == "accounting" else "sb-btn"
    seed = ""
    if seed_test_purchase_enabled():
        seed = (
            '<a href="/admin/link-generation#admin-seed-purchase">'
            "Seed test purchase</a>"
        )
    return f"""
<aside class="admin-sidebar" id="admin-sidebar" data-admin-sidebar="1">
  <div class="sb-brand" id="admin-sidebar-brand">Admin</div>
  <button type="button" class="sb-toggle" id="admin-sidebar-toggle" aria-expanded="true"
    aria-controls="admin-sidebar">Collapse</button>
  <a class="{home_cls}" id="admin-nav-home" href="/admin"><span class="sb-ico">&#8962;</span>
    <span class="sb-label">Architecture</span></a>
  <details class="sb-group" id="admin-nav-link-generation"{link_open}>
    <summary class="sb-group-title"><span class="sb-ico">&#128279;</span>
      <span class="sb-label">Link Generation</span></summary>
    <div class="sb-sub">
      <a href="/admin/link-generation">Open Link Generation</a>
      <a href="/admin/link-generation#admin-reissue">Re-issue by purchase ID</a>
      <a href="/admin/link-generation#admin-ondemand-mint">Generate download (failsafe)</a>
      <a href="/admin/link-generation#admin-keygen-failsafe">Generate KEYGEN (failsafe)</a>
      <a href="/admin/link-generation#admin-tester-month">One-month tester</a>
      {seed}
    </div>
  </details>
  <details class="sb-group" id="admin-nav-active-licences"{lic_open}>
    <summary class="sb-group-title"><span class="sb-ico">&#9638;</span>
      <span class="sb-label">Active Licences</span></summary>
    <div class="sb-sub">
      <a href="/admin/licences">Open Active Licences</a>
      <a href="/admin/licences#admin-licences">Licence database</a>
      <a href="/admin/licences#admin-grants">Paid download grants</a>
    </div>
  </details>
  <a class="{fleet_cls}" id="admin-nav-fleet" href="/admin/fleet"><span class="sb-ico">&#9678;</span>
    <span class="sb-label">Fleet usage</span></a>
  <a class="{acct_cls}" id="admin-nav-accounting" href="/admin/accounting"><span class="sb-ico">&#163;</span>
    <span class="sb-label">RASKUL LTD accounts</span></a>
  <a class="{proc_cls}" id="admin-nav-processors" href="/admin/processors"><span class="sb-ico">&#9881;</span>
    <span class="sb-label">Processor settings</span></a>
  <a class="sb-btn" href="/admin/logout" id="admin-logout"><span class="sb-ico">&#9099;</span>
    <span class="sb-label">Log out</span></a>
  <a class="sb-btn" href="/"><span class="sb-ico">&#8599;</span>
    <span class="sb-label">VPN APP Shop</span></a>
</aside>
<script id="admin-sidebar-script" src="/static/admin_sidebar.js"></script>
"""


def _admin_page_shell(
    *,
    title: str,
    active: str,
    main_html: str,
) -> bytes:
    """Full HTML document with left sidebar + main pane."""
    body = f"""<!DOCTYPE html>
<html lang="en"><head>
<meta charset="utf-8"/><meta name="viewport" content="width=device-width, initial-scale=1"/>
<meta name="color-scheme" content="light dark"/>
<title>{_escape(title)}</title>
<style>
{_admin_shared_css()}
</style>
{admin_theme_boot_script()}
</head><body>
{admin_theme_picker_html()}
<div class="admin-shell" id="admin-shell">
{_admin_sidebar_html(active=active)}
<main class="admin-main" id="admin-main">
<div class="top">
  <h1 id="admin-heading">{_escape(title)}</h1>
</div>
{main_html}
</main>
</div>
</body></html>
"""
    body = _redact_secret_material(body)
    return body.encode("utf-8")


def _durable_store_banner() -> tuple[str, str]:
    try:
        store_hint = str(payment_data_dir())
    except Exception:  # noqa: BLE001
        store_hint = "status_page/data (or RPT_PAYMENT_DATA_DIR)"
    durable_banner = ""
    try:
        from payments import payment_store_durability_status

        st = payment_store_durability_status()
        g_n = int(st.get("grant_count") or 0)
        l_n = int(st.get("licence_count") or 0)
        path_s = _escape(str(st.get("db_path") or store_hint))
        if st.get("ephemeral_risk"):
            durable_banner = (
                '<p class="warn" id="admin-payment-ephemeral-warn">'
                "<strong>Warning — payment store may be ephemeral.</strong> "
                "Set <code>RPT_PAYMENT_DATA_DIR=/var/data/rpt-payment</code> on a "
                "Render <strong>persistent disk</strong> so licence + grant history survives "
                f"redeploy. Current DB: <code>{path_s}</code> "
                f"(grants={g_n}, licences={l_n}).</p>"
            )
        else:
            durable_banner = (
                f'<p class="muted" id="admin-payment-durable-ok">'
                f"Durable payment store: <code>{path_s}</code> "
                f"(grants={g_n}, licences={l_n}).</p>"
            )
    except Exception:  # noqa: BLE001
        durable_banner = ""
    return durable_banner, _escape(store_hint)


def render_admin_grants_section_html(
    grants: list[dict[str, Any]] | None = None,
    *,
    clear_message: str = "",
    clear_error: str = "",
) -> str:
    """Paid download grants table with initiated/expiry + ENDED + clear-all."""
    try:
        from payments import CLEAR_ALL_GRANTS_CONFIRM  # type: ignore
    except Exception:  # noqa: BLE001
        try:
            from status_page.payments import CLEAR_ALL_GRANTS_CONFIRM  # type: ignore
        except Exception:  # noqa: BLE001
            CLEAR_ALL_GRANTS_CONFIRM = "CLEAR_ALL_GRANTS"
    projected = project_grants_for_admin(grants)
    rows = []
    for g in projected:
        tok = str(g.get("token") or "")
        tok_short = (tok[:10] + "…") if len(tok) > 12 else tok
        st = str(g.get("status") or "")
        badge = "ok" if st in ("granted", "OK", "used") else "bad"
        if st == "ENDED":
            badge = "bad"
        pid = str(g.get("purchase_id") or "")
        rows.append(
            "<tr>"
            f"<td><code>{_escape(pid)}</code></td>"
            f"<td>{_escape(str(g.get('platform') or ''))}</td>"
            f"<td>{_escape(str(g.get('filename') or ''))}</td>"
            f"<td>{int(g.get('amount_pence') or 0)} {_escape(str(g.get('currency') or ''))}</td>"
            f'<td><span class="badge {badge}">{_escape(st)}</span></td>'
            f"<td class=\"grant-initiated\">{_escape(str(g.get('initiated_date') or ''))}</td>"
            f"<td class=\"grant-expiry\">{_escape(str(g.get('expiry_date') or ''))}</td>"
            f"<td title=\"{_escape(tok)}\">{_escape(tok_short)}</td>"
            f"<td>{_escape(str(g.get('session_id') or '')[:18])}</td>"
            "</tr>"
        )
    table = (
        "\n".join(rows)
        if rows
        else '<tr><td colspan="9">No grants yet</td></tr>'
    )
    msg_html = (
        f'<p class="ok-msg" id="admin-grants-clear-ok">{_escape(clear_message)}</p>'
        if clear_message
        else ""
    )
    err_html = (
        f'<p class="err" id="admin-grants-clear-error">{_escape(clear_error)}</p>'
        if clear_error
        else ""
    )
    confirm_token = _escape(str(CLEAR_ALL_GRANTS_CONFIRM))
    n = len(projected)
    return f"""
<section id="admin-grants" class="card">
  <h2 id="admin-grants-heading">Paid download grants</h2>
  <p class="muted" id="admin-grants-blurb">Full history of Stripe-verified download grants from the durable store
  (not a recent-only window). Status <code>ENDED</code> means the linked licence period finished or was revoked
  (still listed). <strong>Initiated</strong> / <strong>Expiry</strong> are UTC dates from the licence period when known.
  Rows: <strong id="admin-grants-count">{n}</strong>.</p>
  <table id="admin-grants-table">
    <thead><tr>
      <th>Purchase ID</th><th>Platform</th><th>Filename</th><th>Amount</th><th>Status</th>
      <th>Initiated</th><th>Expiry</th><th>Token</th><th>Session</th>
    </tr></thead>
    <tbody>
{table}
    </tbody>
  </table>
  {msg_html}
  {err_html}
  <form method="post" action="/admin/clear-grants" id="admin-clear-grants-form"
        data-admin-clear-grants="1"
        onsubmit="return confirm('Delete ALL paid download grants? This cannot be undone.');">
    <p class="muted" id="admin-clear-grants-blurb">
      <strong>Clear all grants</strong> (BETA cleanup): permanently deletes every
      download token/grant row so this table is empty. Does not erase Connect
      licence entitlements. Type
      <code id="admin-clear-grants-token">{confirm_token}</code> to confirm.
    </p>
    <label class="field" for="clear_grants_confirm">
      <span class="field-label">Confirm phrase</span>
      <input id="clear_grants_confirm" name="confirm" type="text" autocomplete="off"
             maxlength="64" required placeholder="{confirm_token}">
    </label>
    <button type="submit" id="admin-clear-grants-submit">Clear all grants</button>
  </form>
{admin_section_top_link_html()}</section>
"""


def render_admin_html(
    grants: list[dict[str, Any]] | None = None,
    *,
    message: str = "",
    error: str = "",
    reissue_result: dict[str, Any] | None = None,
    reissue_error: str = "",
    reissue_form_value: str = "",
    ondemand_result: dict[str, Any] | None = None,
    ondemand_error: str = "",
    ondemand_platform: str = "windows",
    keygen_result: dict[str, Any] | None = None,
    keygen_error: str = "",
    keygen_note: str = "",
    keygen_platform: str = "",
    tester_result: dict[str, Any] | None = None,
    tester_error: str = "",
    tester_platform: str = "windows",
    seed_result: dict[str, Any] | None = None,
    seed_error: str = "",
    seed_platform: str = "windows",
    node_usage_rows: list[Any] | None = None,
    node_usage_live: bool = True,
    page: str | None = None,
) -> bytes:
    """Admin HTML router: home / link-generation / licences / fleet / processors.

    When mint/reissue result kwargs are set, defaults to the Link Generation page
    so POST handlers keep working. Explicit *page* wins.
    """
    minty = any(
        x is not None
        for x in (
            reissue_result,
            ondemand_result,
            keygen_result,
            tester_result,
            seed_result,
        )
    ) or bool(
        reissue_error
        or ondemand_error
        or keygen_error
        or tester_error
        or seed_error
    )
    settings_hit = bool(message or error)
    if page is None:
        if minty:
            page = "link-generation"
        elif settings_hit:
            page = "processors"
        else:
            page = "home"

    if page == "link-generation":
        return render_admin_link_generation_html(
            reissue_result=reissue_result,
            reissue_error=reissue_error,
            reissue_form_value=reissue_form_value,
            ondemand_result=ondemand_result,
            ondemand_error=ondemand_error,
            ondemand_platform=ondemand_platform,
            keygen_result=keygen_result,
            keygen_error=keygen_error,
            keygen_note=keygen_note,
            keygen_platform=keygen_platform,
            tester_result=tester_result,
            tester_error=tester_error,
            tester_platform=tester_platform,
            seed_result=seed_result,
            seed_error=seed_error,
            seed_platform=seed_platform,
        )
    if page == "licences":
        return render_admin_licences_page_html(grants=grants)
    if page == "processors":
        return render_admin_processors_page_html(message=message, error=error)
    if page == "fleet":
        return render_admin_fleet_page_html(
            node_usage_rows=node_usage_rows, node_usage_live=node_usage_live
        )
    return render_admin_home_html()


def render_admin_home_html() -> bytes:
    """Admin home: architecture only (human-cadence) + sidebar."""
    durable_banner, store_esc = _durable_store_banner()
    arch_short = _escape(ADMIN_ARCHITECTURE_BLURB)
    paras = []
    for block in ADMIN_ARCHITECTURE_FULL.strip().split("\n\n"):
        paras.append(f"<p>{_escape(block.strip())}</p>")
    arch_body = "\n".join(paras)
    main = f"""
<section id="admin-architecture" class="card" aria-labelledby="admin-architecture-heading">
  <h2 id="admin-architecture-heading">Product architecture (operator)</h2>
  <div class="admin-arch-body" id="admin-architecture-full">{arch_body}</div>
  <p class="muted" id="admin-architecture-blurb" hidden>{arch_short}</p>
{durable_banner}
  <p class="muted" id="admin-durable-store-note">Payment DB path:
  <code id="admin-payment-data-dir">{store_esc}</code>
  (<code>paid_downloads.sqlite3</code>). Use the sidebar for Link Generation and
  Active Licences tools.</p>
</section>
"""
    return _admin_page_shell(
        title="Payment administration",
        active="home",
        main_html=main,
    )


def render_admin_link_generation_html(
    *,
    reissue_result: dict[str, Any] | None = None,
    reissue_error: str = "",
    reissue_form_value: str = "",
    ondemand_result: dict[str, Any] | None = None,
    ondemand_error: str = "",
    ondemand_platform: str = "windows",
    keygen_result: dict[str, Any] | None = None,
    keygen_error: str = "",
    keygen_note: str = "",
    keygen_platform: str = "",
    tester_result: dict[str, Any] | None = None,
    tester_error: str = "",
    tester_platform: str = "windows",
    seed_result: dict[str, Any] | None = None,
    seed_error: str = "",
    seed_platform: str = "windows",
) -> bytes:
    """Link Generation page: reissue + failsafe download/keygen + tester mint."""
    reissue_html = render_purchase_reissue_section_html(
        result=reissue_result,
        error=reissue_error,
        form_value=reissue_form_value,
    )
    ondemand_html = render_admin_ondemand_mint_section_html(
        result=ondemand_result,
        error=ondemand_error,
        platform=ondemand_platform,
    )
    keygen_html = render_admin_keygen_failsafe_section_html(
        result=keygen_result,
        error=keygen_error,
        note=keygen_note,
        platform=keygen_platform,
    )
    tester_html = render_admin_tester_month_section_html(
        result=tester_result,
        error=tester_error,
        platform=tester_platform,
    )
    seed_html = render_seed_test_purchase_section_html(
        result=seed_result,
        error=seed_error,
        platform=seed_platform,
    )
    main = f"""
<p class="ok-msg" id="admin-media-kit-banner" data-admin-media-kit="1" style="margin:0 0 1rem">
  <strong>Media kit</strong> (public logos, favicons, brand PNGs for press/partners):
  <a id="admin-media-kit-link" href="{MEDIA_KIT_PUBLIC_PATH}" download="{MEDIA_KIT_FILENAME}">
  Download restore-privacy media kit (ZIP)</a>
  — also at <code>{MEDIA_KIT_PUBLIC_PATH}</code> (no admin login required).
</p>
<p class="muted" id="admin-link-generation-intro">Mint and re-issue customer download
links and keygens. These tools write the durable payment store; they are not free public unlocks.</p>
{reissue_html}
{ondemand_html}
{keygen_html}
{tester_html}
{seed_html}
<script id="admin-link-generation-script" src="{ADMIN_LINK_GENERATION_SCRIPT}"></script>
"""
    return _admin_page_shell(
        title="Link Generation",
        active="link-generation",
        main_html=main,
    )


def render_admin_licences_page_html(
    grants: list[dict[str, Any]] | None = None,
    *,
    licence_clear_message: str = "",
    licence_clear_error: str = "",
    grant_clear_message: str = "",
    grant_clear_error: str = "",
) -> bytes:
    """Active Licences page: licence database + paid download grants."""
    main = (
        render_admin_licences_section_html(
            clear_message=licence_clear_message,
            clear_error=licence_clear_error,
        )
        + render_admin_grants_section_html(
            grants,
            clear_message=grant_clear_message,
            clear_error=grant_clear_error,
        )
    )
    return _admin_page_shell(
        title="Active Licences",
        active="licences",
        main_html=main,
    )


def render_admin_processors_page_html(*, message: str = "", error: str = "") -> bytes:
    settings_html = render_processor_settings_html(message=message, error=error)
    return _admin_page_shell(
        title="Processor settings",
        active="processors",
        main_html=settings_html,
    )


def render_admin_accounting_page_html(
    rows: list[Any] | None = None,
    *,
    message: str = "",
    error: str = "",
) -> bytes:
    """RASKUL LTD ledger: setup costs + paid sales + manual entry + export."""
    try:
        from accounting import (  # type: ignore
            ENTITY_NAME,
            OPENING_DATE,
            STRIPE_FEE_POLICY_LABEL,
            build_ledger_from_payment_store,
            ensure_ledger_oldest_first,
            pence_to_pounds_str,
            total_end_balance_pence,
        )
    except Exception:  # noqa: BLE001
        from status_page.accounting import (  # type: ignore
            ENTITY_NAME,
            OPENING_DATE,
            STRIPE_FEE_POLICY_LABEL,
            build_ledger_from_payment_store,
            ensure_ledger_oldest_first,
            pence_to_pounds_str,
            total_end_balance_pence,
        )
    try:
        raw = rows if rows is not None else build_ledger_from_payment_store()
        # Always re-sort + recompute running END BALANCE on render.
        ledger = ensure_ledger_oldest_first(list(raw))
    except Exception as exc:  # noqa: BLE001
        err = _escape(str(exc)[:200])
        main = (
            f'<section class="card" id="admin-accounting">'
            f"<h2>RASKUL LTD accounting</h2>"
            f'<p class="err">Ledger unavailable: {err}</p></section>'
        )
        return _admin_page_shell(
            title="RASKUL LTD accounting", active="accounting", main_html=main
        )

    body_rows: list[str] = []
    # END BALANCE column = cumulative sum of nets through this row (not this row alone).
    for r in ledger:
        rid = _escape(getattr(r, "row_id", "") or "")
        show_money = r.kind in ("sale", "manual")
        net_s = pence_to_pounds_str(r.net_pence)
        bal_s = pence_to_pounds_str(r.balance_pence)
        body_rows.append(
            "<tr data-row-id=\"" + rid + "\" data-date=\"" + _escape(r.date_iso) + "\""
            f' data-net-pence="{int(r.net_pence)}" data-running-balance-pence="{int(r.balance_pence)}">'
            f"<td class='ledger-date'>{_escape(r.date_iso)}</td>"
            f"<td>{_escape(r.description)}</td>"
            f"<td class='num'>{_escape(pence_to_pounds_str(r.gross_pence) if show_money else '—')}</td>"
            f"<td class='num fee'>{_escape(pence_to_pounds_str(r.fee_pence) if show_money else '—')}</td>"
            f"<td class='num ledger-net'>{_escape(net_s)}</td>"
            f"<td>{_escape(r.fee_source)}</td>"
            f"<td><code>{_escape(r.purchase_id)}</code></td>"
            f"<td>{_escape(r.platform)}</td>"
            f"<td class='num bal end-balance' title='Running total of all nets through this row'>"
            f"{_escape(bal_s)}</td>"
            f"<td class='row-actions'>"
            f'<form method="post" action="/admin/accounting/delete" class="admin-accounting-delete-form" '
            f'onsubmit="return confirm(\'Delete this ledger row?\');">'
            f'<input type="hidden" name="row_id" value="{rid}"/>'
            f'<button type="submit" class="btn-delete-row" id="admin-accounting-delete-{rid}">'
            f"Delete row</button></form></td>"
            "</tr>"
        )
    # Join in list order only (oldest first). Do not reverse.
    table_body = (
        "\n".join(body_rows)
        if body_rows
        else '<tr><td colspan="10">No ledger rows</td></tr>'
    )
    # Source of truth: sum of every row's net (matches last running END BALANCE).
    total_pence = total_end_balance_pence(ledger) if ledger else 0
    final_bal = pence_to_pounds_str(total_pence) if ledger else "—"
    if ledger and int(ledger[-1].balance_pence) != int(total_pence):
        # Defensive: last running cell must match full sum
        final_bal = pence_to_pounds_str(total_pence)
    first_date = str(ledger[0].date_iso) if ledger else ""
    last_date = str(ledger[-1].date_iso) if ledger else ""
    footer_html = ""
    if ledger:
        footer_html = (
            '<tfoot id="admin-accounting-tfoot">'
            '<tr id="admin-accounting-total-row" data-total-end-balance="1">'
            '<td colspan="4"><strong>END BALANCE (running total of all rows)</strong></td>'
            f'<td class="num" id="admin-accounting-total-net">'
            f'{_escape(pence_to_pounds_str(total_pence))}</td>'
            '<td colspan="3"></td>'
            f'<td class="num bal end-balance" id="admin-accounting-total-end-balance">'
            f'{_escape(final_bal)}</td>'
            '<td></td>'
            "</tr></tfoot>"
        )
    y0 = OPENING_DATE.year
    m0 = OPENING_DATE.month
    year_opts = "".join(
        f'<option value="{y}"{" selected" if y == y0 else ""}>{y}</option>'
        for y in range(y0, y0 + 6)
    )
    month_opts = "".join(
        f'<option value="{m}"{" selected" if m == m0 else ""}>{m:02d}</option>'
        for m in range(1, 13)
    )
    msg_html = (
        f'<p class="ok-msg" id="admin-accounting-message">{_escape(message)}</p>'
        if message
        else ""
    )
    err_html = (
        f'<p class="err" id="admin-accounting-error">{_escape(error)}</p>'
        if error
        else ""
    )
    today = OPENING_DATE.isoformat()  # default date field to books start
    try:
        from datetime import date as _date

        today = _date.today().isoformat()
    except Exception:  # noqa: BLE001
        pass
    main = f"""
<section class="card" id="admin-accounting" data-admin-accounting="1"
         data-ledger-order="oldest-first"
         data-ledger-first-date="{_escape(first_date)}"
         data-ledger-last-date="{_escape(last_date)}">
  <h2 id="admin-accounting-heading">{_escape(ENTITY_NAME)} — accounting</h2>
  <p class="muted" id="admin-accounting-blurb">
    Business books from <strong>{_escape(OPENING_DATE.isoformat())}</strong>.
    Opening line: <strong>SET UP COSTS −£6,000.00</strong> (starting deficit).
    Paid customer sales load automatically from the durable payment store.
    Each line shows <strong>gross</strong>, <strong>fees</strong> (as a minus), and
    <strong>net</strong> (= this row’s gross ± fees only).
    <strong>END BALANCE</strong> is the <em>running total of all nets so far</em>
    (not this row alone) — last row / footer = sum of every line.
    Stripe card fees on auto sales are named in the description; the Fees
    column is for any fee. Manual lines and deletes are durable.
  </p>
  <p class="muted" id="admin-accounting-fee-policy">{_escape(STRIPE_FEE_POLICY_LABEL)}</p>
  <p id="admin-accounting-balance">Current END BALANCE
    <span class="muted">(sum of all row nets)</span>:
    <strong id="admin-accounting-balance-value"
            data-total-pence="{int(total_pence) if ledger else 0}">{_escape(final_bal)}</strong>
  </p>
  <p class="muted" id="admin-accounting-order-note">
    <strong>Date order:</strong> oldest first → most recent last
    (top = first transaction
    {f'<code id="admin-accounting-first-date">{_escape(first_date)}</code>' if first_date else ''},
    bottom = most recent
    {f'<code id="admin-accounting-last-date">{_escape(last_date)}</code>' if last_date else ''}).
  </p>
  {msg_html}
  {err_html}

  <table id="admin-accounting-table" data-order="asc" data-sort="date-asc"
         data-end-balance-mode="running-total">
    <caption id="admin-accounting-table-caption" class="muted">
      Date order oldest→newest. Net = this row only.
      END BALANCE = running total of all nets through that row.
    </caption>
    <thead><tr>
      <th>Date</th><th>Description</th><th>Gross</th><th>Fees</th>
      <th>Net</th><th>Fee source</th><th>Purchase ID</th><th>Platform</th>
      <th id="admin-accounting-end-balance-col">END BALANCE</th>
      <th>Actions</th>
    </tr></thead>
    <tbody id="admin-accounting-tbody">
{table_body}
    </tbody>
{footer_html}
  </table>

  <div class="accounting-manual-entry" id="admin-accounting-manual-entry">
    <h3 id="admin-accounting-manual-entry-heading">Manual entry</h3>
    <p class="muted" id="admin-accounting-manual-entry-blurb">
      Add a ledger line (date, description, gross, fees). New rows slot in by
      <strong>date</strong> (most recent dates appear at the bottom of the table above).
      <strong>Net</strong> is calculated automatically as <strong>gross ± fees</strong>
      (fees reduce cash). Choose <strong>+</strong> to add gross to END BALANCE or
      <strong>−</strong> to deduct (or type a negative gross). If the fee is a Stripe
      charge, say so in the description — the Fees column is for any fee type.
    </p>
    <form method="post" action="/admin/accounting/manual-entry"
          id="admin-accounting-manual-entry-form" data-admin-accounting-manual="1">
      <label class="field" for="manual_date">Date
        <input id="manual_date" name="date_iso" type="date" required value="{_escape(today)}"/>
      </label>
      <label class="field" for="manual_description">Description
        <input id="manual_description" name="description" type="text" required maxlength="500"
               placeholder="e.g. Bank charge / card fee / adjustment"/>
      </label>
      <label class="field" for="manual_gross_sign">Gross sign
        <select id="manual_gross_sign" name="gross_sign" title="Add or deduct gross">
          <option value="+" selected>+ (add to balance)</option>
          <option value="-">− (deduct from balance)</option>
        </select>
      </label>
      <label class="field" for="manual_gross">Gross (£)
        <input id="manual_gross" name="gross" type="text" inputmode="decimal"
               placeholder="0.00" required/>
      </label>
      <label class="field" for="manual_fee">Fees (£)
        <input id="manual_fee" name="fee" type="text" inputmode="decimal"
               placeholder="0.00 (stored as minus)"/>
      </label>
      <label class="field" for="manual_purchase_id">Purchase ID
        <input id="manual_purchase_id" name="purchase_id" type="text" maxlength="120"/>
      </label>
      <label class="field" for="manual_platform">Platform
        <input id="manual_platform" name="platform" type="text" maxlength="40"
               placeholder="windows / android / …"/>
      </label>
      <button type="submit" id="admin-accounting-manual-entry-submit">Add entry</button>
    </form>
  </div>

  <div class="accounting-export" id="admin-accounting-export">
    <h3 id="admin-accounting-export-heading">Export</h3>
    <form method="get" action="/admin/accounting/export" id="admin-accounting-export-form">
      <label class="field">Period mode
        <select name="period_mode" id="export-period-mode">
          <option value="month" selected>Single month</option>
          <option value="range">Month range (from → to)</option>
        </select>
      </label>
      <label class="field">Year
        <select name="year" id="export-year">{year_opts}</select>
      </label>
      <label class="field">Month (single-month mode)
        <select name="month" id="export-month">{month_opts}</select>
      </label>
      <label class="field">From year
        <select name="from_year" id="export-from-year">{year_opts}</select>
      </label>
      <label class="field">From month
        <select name="from_month" id="export-from-month">{month_opts}</select>
      </label>
      <label class="field">To year
        <select name="to_year" id="export-to-year">{year_opts}</select>
      </label>
      <label class="field">To month
        <select name="to_month" id="export-to-month">
          {"".join(f'<option value="{m}"{" selected" if m == 12 else ""}>{m:02d}</option>' for m in range(1, 13))}
        </select>
      </label>
      <label class="field">Format
        <select name="format" id="export-format">
          <option value="xlsx" selected>Excel (.xlsx)</option>
          <option value="xls">Excel 2003 XML (.xls)</option>
          <option value="csv">CSV</option>
          <option value="pdf">PDF</option>
          <option value="rtf">RTF (Word)</option>
          <option value="html">HTML</option>
          <option value="json">JSON</option>
        </select>
      </label>
      <button type="submit" id="admin-accounting-export-submit">Export accounts</button>
    </form>
  </div>
{admin_section_top_link_html()}</section>
<style>
#admin-accounting-table .num{{text-align:right;font-variant-numeric:tabular-nums}}
#admin-accounting-table .fee{{color:#b45309}}
#admin-accounting-table .end-balance{{font-weight:700}}
#admin-accounting-table caption{{caption-side:top;text-align:left;padding:0.35rem 0 0.65rem;font-size:0.9rem}}
#admin-accounting-tbody{{display:table-row-group}}
#admin-accounting-tfoot td{{border-top:2px solid var(--border,#3333);padding-top:0.55rem;font-weight:600}}
#admin-accounting-total-end-balance{{font-size:1.05rem}}
#admin-accounting-export form,#admin-accounting-manual-entry-form{{display:flex;flex-wrap:wrap;gap:0.75rem;align-items:flex-end;margin:1rem 0}}
#admin-accounting-export .field,#admin-accounting-manual-entry .field{{display:flex;flex-direction:column;font-size:0.85rem;gap:0.25rem}}
#admin-accounting-export select,#admin-accounting-export button,
#admin-accounting-manual-entry input,#admin-accounting-manual-entry select,
#admin-accounting-manual-entry button,
.btn-delete-row{{padding:0.45rem 0.6rem;border-radius:8px}}
#admin-accounting-export button,#admin-accounting-manual-entry-submit{{background:var(--btn-bg);color:var(--btn-fg);border:0;font-weight:600;cursor:pointer}}
.btn-delete-row{{background:#7f1d1d;color:#fff;border:0;cursor:pointer;font-size:0.8rem}}
#admin-accounting-manual-entry,#admin-accounting-export{{margin:1.25rem 0;padding-top:0.5rem;border-top:1px solid var(--border,#3333)}}
.admin-accounting-delete-form{{display:inline;margin:0}}
</style>
"""
    return _admin_page_shell(
        title=f"{ENTITY_NAME} accounting",
        active="accounting",
        main_html=main,
    )


def render_admin_fleet_page_html(
    *,
    node_usage_rows: list[Any] | None = None,
    node_usage_live: bool = True,
) -> bytes:
    node_usage_html = _render_node_usage_section(
        node_usage_rows, live=node_usage_live
    )
    return _admin_page_shell(
        title="Fleet usage",
        active="fleet",
        main_html=node_usage_html,
    )



def _escape(s: str) -> str:
    return (
        s.replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
    )
