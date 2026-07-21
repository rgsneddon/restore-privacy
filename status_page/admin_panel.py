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
import secrets
import time
from typing import Any

from coffee_link import COFFEE_LINK_TEXT, coffee_tip_url
from payments import (
    PRICE_LABEL,
    PRICE_PENCE,
    list_recent_grants,
    public_base_url,
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
from processor_plugins import (
    list_processor_plugins,
    processor_plugin_views,
)

SESSION_COOKIE = "rpt_admin_session"
SESSION_TTL_SEC = 8 * 3600

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
    """Apply stored or system theme before paint; wire radio controls."""
    key = THEME_STORAGE_KEY
    return f"""
<script id="admin-theme-script">
(function () {{
  var KEY = {json_dumps_str(key)};
  var root = document.documentElement;
  function normalize(m) {{
    m = (m || "").toLowerCase();
    if (m === "light" || m === "dark" || m === "system") return m;
    return "system";
  }}
  function apply(mode) {{
    mode = normalize(mode);
    if (mode === "system") {{
      root.removeAttribute("data-theme");
    }} else {{
      root.setAttribute("data-theme", mode);
    }}
    try {{ localStorage.setItem(KEY, mode); }} catch (e) {{}}
    var radios = document.querySelectorAll('input[name="admin-theme"]');
    for (var i = 0; i < radios.length; i++) {{
      radios[i].checked = (radios[i].value === mode);
    }}
  }}
  var saved = "system";
  try {{ saved = normalize(localStorage.getItem(KEY)); }} catch (e) {{}}
  apply(saved);
  document.addEventListener("DOMContentLoaded", function () {{
    apply(saved);
    var radios = document.querySelectorAll('input[name="admin-theme"]');
    for (var i = 0; i < radios.length; i++) {{
      radios[i].addEventListener("change", function (ev) {{
        if (ev.target && ev.target.checked) apply(ev.target.value);
      }});
    }}
  }});
}})();
</script>
"""


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
    "pbkdf2_sha256$200000$ab3f30efe29d52b0b7d5946ccb7f6266$"
    "d3a85f8d6cc2c2124766b1ba0a942551955f0aad0becf1aff82aff7c3b889cf5"
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
<meta name="color-scheme" content="light dark"/>
<title>Admin login — Restore Privacy</title>
<style>
{admin_theme_css()}
body{{margin:0;min-height:100vh;display:flex;flex-direction:column;align-items:center;
justify-content:center;padding:1rem;box-sizing:border-box}}
.login-wrap{{width:100%;max-width:22rem}}
form#admin-login-form{{background:var(--bg-elevated);padding:1.5rem 1.75rem;border-radius:12px;
border:1px solid var(--border);width:100%;box-sizing:border-box}}
form#admin-login-form > label{{display:block;font-size:0.85rem;margin:0.6rem 0 0.25rem;
color:var(--fg-muted)}}
form#admin-login-form input[type="text"],
form#admin-login-form input[type="password"],
form#admin-login-form input:not([type]){{width:100%;box-sizing:border-box;padding:0.55rem 0.65rem;
border-radius:8px;border:1px solid var(--input-border);background:var(--input-bg);color:var(--fg)}}
button{{margin-top:1rem;width:100%;padding:0.7rem;border:0;border-radius:8px;
background:var(--btn-bg);color:var(--btn-fg);font-weight:600;cursor:pointer}}
.err{{color:var(--err);font-size:0.9rem}}
h1{{font-size:1.1rem;margin:0 0 0.5rem;color:var(--fg)}}
.note{{color:var(--fg-muted);font-size:0.85rem;margin:0 0 0.75rem;line-height:1.35}}
</style>
{admin_theme_boot_script()}
</head><body>
<div class="login-wrap">
{admin_theme_picker_html()}
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
</div>
</body></html>
"""
    return body.encode("utf-8")


def _status_badge(ok: bool, yes: str = "ready", no: str = "not set") -> str:
    cls = "ok" if ok else "bad"
    label = yes if ok else no
    return f'<span class="badge {cls}" data-ready="{"1" if ok else "0"}">{_escape(label)}</span>'


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
    forbidden_fragments = (
        "sk_live_",
        "sk_test_",
        "whsec_",
        "RPT_ADMIN_PASSWORD",
    )
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
        badge = _status_badge(ready_flag, "connection ready", "needs variables")
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
            rows.append(
                "<tr>"
                f"<td><code class=\"var-key\">{_escape(key)}</code></td>"
                f"<td>{_escape(str(var.get('label') or ''))}</td>"
                f"<td>{'required' if var.get('required') else 'optional'}</td>"
                f"<td>{_status_badge(configured, 'set', 'not set')}</td>"
                f"<td class=\"muted\">{_escape(str(var.get('purpose') or ''))}</td>"
                "</tr>"
            )
            itype = str(var.get("input_type") or "text")
            if var.get("secret"):
                itype = "password"
            ph = _escape(str(var.get("placeholder") or ""))
            autocomplete = "off" if var.get("secret") else "on"
            form_fields.append(
                f'<label class="field" for="fld-{pid}-{_escape(key)}">'
                f'<span class="field-label">{_escape(str(var.get("label") or key))}'
                f'{" *" if var.get("required") else ""}</span>'
                f'<span class="field-key"><code>{_escape(key)}</code></span>'
                f'<input id="fld-{pid}-{_escape(key)}" name="{_escape(key)}" type="{_escape(itype)}" '
                f'placeholder="{ph}" autocomplete="{autocomplete}" '
                f'{"value=\"\" " if var.get("secret") else ""}'
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
                    f"<p class=\"muted\">Payment Link / Donate page alone does not enable "
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
    <span id="{pid}-connection-badge">{badge}</span>
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
    <p class="muted field-note">Secret fields are write-only — leave blank to keep the existing value.
    Values apply to this process and local data store (not committed to git).</p>
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
  variables to enter for that payment path. Secrets stay on the server — never shown after save.
  Prefer host/Render env for production permanence; local apply wires the running process.</p>
  <nav class="plugin-nav" id="processor-plugin-nav" aria-label="Processor plugins">{option_links}</nav>
  {msg_html}{err_html}
{plugins_html}
</section>
"""
    low = frag.lower()
    for bad in forbidden_fragments:
        if bad.lower() in low and bad not in ("RPT_ADMIN_PASSWORD",):
            return (
                '<section id="admin-processor-settings"><p class="err">'
                "Settings redacted (secret material detected).</p></section>"
            )
    return frag


def render_admin_html(
    grants: list[dict[str, Any]] | None = None,
    *,
    message: str = "",
    error: str = "",
) -> bytes:
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
    settings_html = render_processor_settings_html(message=message, error=error)
    body = f"""<!DOCTYPE html>
<html lang="en"><head>
<meta charset="utf-8"/><meta name="viewport" content="width=device-width, initial-scale=1"/>
<meta name="color-scheme" content="light dark"/>
<title>Admin — payments &amp; processors</title>
<style>
{admin_theme_css()}
body{{margin:0;padding:1.5rem}}
h1{{font-size:1.25rem;margin:0}} h2{{font-size:1.05rem;margin:0 0 0.5rem}}
h3{{font-size:0.95rem;margin:1rem 0 0.4rem}} h4{{font-size:0.9rem;margin:0.75rem 0 0.35rem}}
table{{border-collapse:collapse;width:100%;max-width:56rem;font-size:0.9rem}}
th,td{{border-bottom:1px solid var(--table-border);padding:0.45rem 0.5rem;text-align:left}}
th{{color:var(--fg-muted);font-weight:600}}
.top{{display:flex;gap:1rem;align-items:center;margin-bottom:0.75rem;flex-wrap:wrap}}
.card{{background:var(--bg-elevated);border:1px solid var(--border);border-radius:12px;
padding:1rem 1.15rem;margin:1rem 0;max-width:56rem}}
.muted{{color:var(--fg-muted);font-size:0.9rem;line-height:1.4}}
.status-list{{margin:0.5rem 0}}
.status-list > div{{display:grid;grid-template-columns:12rem 1fr;gap:0.35rem 0.75rem;
padding:0.25rem 0;font-size:0.9rem}}
.status-list dt{{color:var(--fg-muted)}}
.badge{{display:inline-block;padding:0.15rem 0.5rem;border-radius:6px;font-size:0.8rem;
font-weight:600}}
.badge.ok{{background:var(--badge-ok-bg);color:var(--badge-ok-fg)}}
.badge.bad{{background:var(--badge-bad-bg);color:var(--badge-bad-fg)}}
.ops-links{{font-size:0.9rem;margin:0.75rem 0 0.25rem}}
.nav-local a{{margin-right:0.75rem;font-size:0.9rem}}
code{{font-size:0.85rem;word-break:break-all}}
.processor-plugin{{border-top:1px solid var(--border);margin-top:1.25rem;padding-top:1rem}}
.plugin-head{{display:flex;flex-wrap:wrap;gap:0.5rem 0.75rem;align-items:center}}
.plugin-role{{font-size:0.8rem;color:var(--fg-muted)}}
.var-table{{margin:0.5rem 0 1rem;font-size:0.85rem}}
.processor-form label.field{{display:block;margin:0.65rem 0}}
.processor-form .field-label{{display:block;font-weight:600;font-size:0.9rem}}
.processor-form .field-key{{display:block;font-size:0.8rem;margin:0.15rem 0}}
.processor-form input{{width:100%;max-width:28rem;box-sizing:border-box;padding:0.5rem 0.6rem;
border-radius:8px;border:1px solid var(--input-border);background:var(--input-bg);color:var(--fg)}}
.processor-form button{{margin-top:0.75rem;padding:0.55rem 1rem;border:0;border-radius:8px;
background:var(--btn-bg);color:var(--btn-fg);font-weight:600;cursor:pointer}}
.ok-msg{{color:var(--badge-ok-fg);background:var(--badge-ok-bg);padding:0.5rem 0.75rem;border-radius:8px}}
.err{{color:var(--err)}}
.plugin-nav{{margin:0.5rem 0 1rem;font-size:0.9rem}}
</style>
{admin_theme_boot_script()}
</head><body>
{admin_theme_picker_html()}
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
