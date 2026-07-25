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

# Operator-facing architecture blurb (must stay current; grepped by tests).
ADMIN_ARCHITECTURE_BLURB = (
    "Residual catalog peers: Iceland (IS, default entry), Romania (RO), "
    "Germany (DE) — user-selectable entry; multi-hop opt-in uses a random "
    "non-entry peer. Weekly fleet wipe is sequential IS → RO → DE (exclusive "
    "lock; never concurrent multi-node wipe). Paid Stripe Checkout "
    f"(Monthly {PRICE_LABEL} / Yearly {PRICE_YEARLY_LABEL} GBP) + keygen unlock; "
    "no free permanent GitHub installers. Public status is title-only (no live "
    "client count). Licence database and paid download grants live in the "
    "durable payment store and are retained across residual node wipeclean/"
    "rebuild — they are not residual-runtime scratch."
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


def render_admin_licences_section_html(
    licences: list[dict[str, Any]] | None = None,
) -> str:
    """Read-only licence database: email, KEYGEN, PPI, OK|EXPIRED. No amend controls."""
    try:
        rows_src = licences if licences is not None else list_licences_for_admin()
    except Exception:  # noqa: BLE001
        rows_src = []
    body_rows: list[str] = []
    for row in rows_src:
        st = str(row.get("licence_status") or "EXPIRED")
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
            "</tr>"
        )
    table = (
        "\n".join(body_rows)
        if body_rows
        else '<tr><td colspan="5">No licences yet</td></tr>'
    )
    return f"""
<section id="admin-licences" class="card">
  <h2 id="admin-licences-heading">Licence database</h2>
  <p class="muted" id="admin-licences-blurb">
  Customer licences (email, KEYGEN, PPI, status) from the <strong>durable
  payment store</strong> (<code>RPT_PAYMENT_DATA_DIR</code> / status_page data).
  <strong>Retained across residual fleet wipe/rebuild</strong> — not cleared by
  node wipeclean. <strong>Read-only</strong> here: no edit, revoke, or amend
  controls. Status is <code>OK</code> (active subscription) or
  <code>EXPIRED</code> (revoked, failed, or period ended). Keygen unlocks
  residual Connect on any catalog peer (IS / RO / DE), not a single-node product.
  </p>
  <table id="admin-licences-table" data-readonly="1">
    <thead><tr>
      <th>Email</th><th>KEYGEN</th><th>PPI</th><th>Status</th><th>Platform</th>
    </tr></thead>
    <tbody>
{table}
    </tbody>
  </table>
</section>
"""


def project_grants_for_admin(
    grants: list[dict[str, Any]] | None = None, *, limit: int | None = None
) -> list[dict[str, Any]]:
    """Project grant rows for admin UI.

    Default loads the **full** completed-payment grant history from the shipped
    store (no silent drop past a short window). Pass *limit* only when a caller
    intentionally wants a truncated sample. Full token is kept for operator
    support; HTML truncates the display value only.
    """
    if grants is not None:
        raw = grants
    elif limit is None:
        raw = list_all_grants()
    else:
        raw = list_recent_grants(limit)
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
                "purchase_id": g.get("purchase_id") or "",
                "created_at": g.get("created_at"),
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
        f'<p class="err" id="reissue-error">{_escape(error)}</p>' if error else ""
    )
    ok = ""
    if result and result.get("download_url"):
        url = _escape(str(result["download_url"]))
        path = _escape(str(result.get("download_path") or ""))
        pid = _escape(str(result.get("purchase_id") or ""))
        plat = _escape(str(result.get("platform") or ""))
        fname = _escape(str(result.get("filename") or ""))
        ok = f"""
  <div class="ok-msg" id="reissue-result" role="status">
    <p><strong>Secondary download link minted</strong> for purchase
    <code id="reissue-result-purchase-id">{pid}</code>
    ({plat} — <code>{fname}</code>).</p>
    <p>Pass this <strong>one-time</strong> link to the buyer (not a free GitHub URL):</p>
    <p><a id="reissue-download-link" href="{url}" rel="noopener noreferrer">{url}</a></p>
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
    <strong>secondary single-use download link</strong> for the same package they paid for.
    Tell the buyer: open the link once on a trusted device, save the installer, and keep
    their RPT-… ID for any future recovery. This is the preferred recovery path when the
    customer still has their purchase identifier.
  </p>
  <p class="muted" id="admin-reissue-elaborate">
    Steps for the buyer after you send the link: (1) open the one-time URL,
    (2) download starts or use the on-page button, (3) run/install the package,
    (4) for Connect, use payment entitlement as on the original thank-you page if needed.
    Do <strong>not</strong> post free GitHub release URLs — only the paid
    <code>/download?token=…</code> link from this form.
  </p>
  {err}
  {ok}
  <form method="post" action="/admin/reissue-download" id="admin-reissue-form">
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
</section>
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
        f'<p class="err" id="ondemand-error">{_escape(error)}</p>' if error else ""
    )
    ok = ""
    if result and result.get("download_url"):
        url = _escape(str(result["download_url"]))
        path = _escape(str(result.get("download_path") or ""))
        plat = _escape(str(result.get("platform") or ""))
        fname = _escape(str(result.get("filename") or ""))
        ok = f"""
  <div class="ok-msg" id="ondemand-result" role="status">
    <p><strong>Admin failsafe link minted</strong> for <strong id="ondemand-result-platform">{plat}</strong>
      (<code id="ondemand-result-filename">{fname}</code>).</p>
    <p>One-time paid download (not free GitHub):</p>
    <p><a id="ondemand-download-link" href="{url}" rel="noopener noreferrer">{url}</a></p>
    <p class="muted">Path: <code id="ondemand-download-path">{path}</code>
      — single-use; not written as a customer RPT-PPI recovery event.</p>
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
    Mint a <strong>live single-use</strong> download for the current catalog package
    <strong>without</strong> a customer RPT purchase identifier. Use when you need an
    on-demand installer link. Prefer <a href="#admin-reissue">RPT-PPI re-issue</a> when
    the buyer still has their purchase ID. Not a free public unlock.
  </p>
  {err}
  {ok}
  <form method="post" action="/admin/mint-download" id="admin-ondemand-mint-form">
    <label class="field" for="ondemand_platform">
      <span class="field-label">Package / device</span>
      <select id="ondemand_platform" name="platform" required>
      {opts}
      </select>
    </label>
    <button type="submit" id="admin-ondemand-mint-submit">Generate live download link</button>
  </form>
</section>
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
        f'<p class="err" id="keygen-failsafe-error">{_escape(error)}</p>' if error else ""
    )
    ok = ""
    if result and result.get("keygen"):
        kg = _escape(str(result["keygen"]))
        sid = _escape(str(result.get("session_id") or ""))
        plat = _escape(str(result.get("platform") or "") or "—")
        instr = _escape(str(result.get("unlock_instruction") or "USE THIS KEYGEN TO UNLOCK"))
        ok = f"""
  <div class="ok-msg" id="keygen-failsafe-result" role="status">
    <p><strong>Admin failsafe KEYGEN minted</strong> (active Connect unlock).</p>
    <p id="keygen-failsafe-instruction">{instr}</p>
    <p>Keygen: <code id="admin-minted-keygen">{kg}</code></p>
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
  <form method="post" action="/admin/mint-keygen" id="admin-keygen-failsafe-form">
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
</section>
"""


def render_seed_test_purchase_section_html(
    *,
    result: dict[str, Any] | None = None,
    error: str = "",
    platform: str = "windows",
) -> str:
    """Dev/staging-only card: seed a paid test grant (RPT-… + platform).

    Hidden unless :func:`seed_test_purchase_enabled` (``RPT_ADMIN_SEED_PURCHASE=1``).
    Still creates a full-price paid grant + single-use token — never a free public unlock.
    """
    if not seed_test_purchase_enabled():
        return ""
    err = (
        f'<p class="err" id="seed-purchase-error">{_escape(error)}</p>' if error else ""
    )
    ok = ""
    if result and result.get("purchase_id"):
        pid = _escape(str(result["purchase_id"]))
        plat = _escape(str(result.get("platform") or ""))
        fname = _escape(str(result.get("filename") or ""))
        url = _escape(str(result.get("download_url") or ""))
        path = _escape(str(result.get("download_path") or ""))
        ok = f"""
  <div class="ok-msg" id="seed-purchase-result" role="status">
    <p><strong>Test purchase seeded</strong> (local/staging only).</p>
    <p>Product purchase identifier:
      <code id="seed-purchase-id">{pid}</code></p>
    <p>Platform: <strong id="seed-purchase-platform">{plat}</strong>
      — <code id="seed-purchase-filename">{fname}</code></p>
    <p>One-time paid download (not free GitHub):
      <a id="seed-download-link" href="{url}" rel="noopener noreferrer">{url}</a></p>
    <p class="muted">Path: <code id="seed-download-path">{path}</code>
      — use the purchase ID above in the re-issue form after consuming the token.</p>
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
    Does <strong>not</strong> open free public unlocks — download still needs the single-use token.
  </p>
  {err}
  {ok}
  <form method="post" action="/admin/seed-test-purchase" id="admin-seed-purchase-form">
    <label class="field" for="seed_platform">
      <span class="field-label">Platform</span>
      <select id="seed_platform" name="platform" required>
      {opts}
      </select>
    </label>
    <button type="submit" id="admin-seed-purchase-submit">Seed test purchase (RPT-…)</button>
  </form>
</section>
"""


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
  <p class="note" id="admin-login-note">Private page: Stripe processor settings,
  licence database, and paid-download grants for the multi-peer residual catalog
  (IS / RO / DE). Not the public shop.</p>
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
</section>
"""
    # Block only real-looking secret values, not doc prefixes (sk_test_… / whsec_…).
    if _html_contains_secret_material(frag):
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
    seed_result: dict[str, Any] | None = None,
    seed_error: str = "",
    seed_platform: str = "windows",
) -> bytes:
    """Full private admin page: reissue by purchase id, processor settings, grants."""
    projected = project_grants_for_admin(grants)
    rows = []
    for g in projected:
        tok = str(g.get("token") or "")
        tok_short = (tok[:10] + "…") if len(tok) > 12 else tok
        used = g.get("used_at")
        used_s = "used" if used else str(g.get("status") or "")
        pid = str(g.get("purchase_id") or "")
        rows.append(
            "<tr>"
            f"<td><code>{_escape(pid)}</code></td>"
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
        else '<tr><td colspan="7">No grants yet</td></tr>'
    )
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
    seed_html = render_seed_test_purchase_section_html(
        result=seed_result,
        error=seed_error,
        platform=seed_platform,
    )
    settings_html = render_processor_settings_html(message=message, error=error)
    try:
        store_hint = str(payment_data_dir())
    except Exception:  # noqa: BLE001
        store_hint = "status_page/data (or RPT_PAYMENT_DATA_DIR)"
    arch = _escape(ADMIN_ARCHITECTURE_BLURB)
    store_esc = _escape(store_hint)
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
#admin-reissue-form label.field,#admin-seed-purchase-form label.field,#admin-ondemand-mint-form label.field,#admin-keygen-failsafe-form label.field{{display:block;margin:0.65rem 0}}
#admin-reissue-form .field-label,#admin-seed-purchase-form .field-label,#admin-ondemand-mint-form .field-label,#admin-keygen-failsafe-form .field-label{{display:block;font-weight:600;font-size:0.9rem;margin-bottom:0.25rem}}
#admin-reissue-form input,#admin-seed-purchase-form select,#admin-ondemand-mint-form select,#admin-keygen-failsafe-form select,#admin-keygen-failsafe-form input{{width:100%;max-width:28rem;box-sizing:border-box;padding:0.5rem 0.6rem;
border-radius:8px;border:1px solid var(--input-border);background:var(--input-bg);color:var(--fg)}}
#admin-reissue-form button,#admin-seed-purchase-form button,#admin-ondemand-mint-form button,#admin-keygen-failsafe-form button{{margin-top:0.75rem;padding:0.55rem 1rem;border:0;border-radius:8px;
background:var(--btn-bg);color:var(--btn-fg);font-weight:600;cursor:pointer}}
.ok-msg{{color:var(--badge-ok-fg);background:var(--badge-ok-bg);padding:0.5rem 0.75rem;border-radius:8px}}
.err{{color:var(--err)}}
.plugin-nav{{margin:0.5rem 0 1rem;font-size:0.9rem}}
.purchase-id-box,.purchase-id-advice{{/* reserved for public thank-you if mirrored */}}
</style>
{admin_theme_boot_script()}
</head><body>
{admin_theme_picker_html()}
<div class="top">
  <h1 id="admin-heading">Payment administration</h1>
  <a href="/admin/logout" id="admin-logout">Log out</a>
  <a href="/">VPN APP Shop</a>
</div>
<nav class="nav-local" id="admin-nav" aria-label="Admin sections">
  <a href="#admin-architecture">Architecture</a>
  <a href="#admin-reissue">Re-issue by RPT-PPI</a>
  <a href="#admin-ondemand-mint">Generate download (failsafe)</a>
  <a href="#admin-keygen-failsafe">Generate KEYGEN (failsafe)</a>
  {('<a href="#admin-seed-purchase">Seed test purchase</a>' if seed_test_purchase_enabled() else '')}
  <a href="#admin-processor-settings">Processor settings</a>
  <a href="#admin-licences">Licence database</a>
  <a href="#admin-grants">Paid download grants</a>
</nav>
<section id="admin-architecture" class="card" aria-labelledby="admin-architecture-heading">
  <h2 id="admin-architecture-heading">Product architecture (operator)</h2>
  <p class="muted" id="admin-architecture-blurb">{arch}</p>
  <p class="muted" id="admin-durable-store-note">Durable licence + grant DB path:
  <code id="admin-payment-data-dir">{store_esc}</code>
  (<code>paid_downloads.sqlite3</code>). Residual wipeclean targets runtime/secrets only —
  not this store.</p>
</section>
{reissue_html}
{ondemand_html}
{keygen_html}
{seed_html}
{settings_html}
{render_admin_licences_section_html()}
<section id="admin-grants" class="card">
  <h2 id="admin-grants-heading">Paid download grants</h2>
  <p class="muted" id="admin-grants-blurb">Full history of Stripe-verified download grants
  (Monthly {_escape(PRICE_LABEL)} / Yearly {_escape(PRICE_YEARLY_LABEL)} GBP by plan) —
  every completed payment grant in the durable store. <strong>Retained across residual
  fleet wipe/rebuild</strong> (IS → RO → DE sequential). Used single-use tokens stay
  listed (status <code>used</code>); purchase identifier (RPT-PPI) is durable.
  Catalog installers are multi-platform residual clients, not free GitHub assets.
  Secrets never shown.</p>
  <table id="admin-grants-table">
    <thead><tr>
      <th>Purchase ID</th><th>Platform</th><th>Filename</th><th>Amount</th><th>Status</th><th>Token</th><th>Session</th>
    </tr></thead>
    <tbody>
{table}
    </tbody>
  </table>
</section>
</body></html>
"""
    # Final secret scan on full page (real values only; keep guide prefixes)
    body = _redact_secret_material(body)
    return body.encode("utf-8")


def _escape(s: str) -> str:
    return (
        s.replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
    )
