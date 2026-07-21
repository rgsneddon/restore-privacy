"""Operator admin panel for paid-download grants (env-configured credentials)."""

from __future__ import annotations

import hashlib
import hmac
import os
import secrets
import time
from typing import Any

from payments import list_recent_grants

SESSION_COOKIE = "rpt_admin_session"
SESSION_TTL_SEC = 8 * 3600


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
form{{background:#111827;padding:1.5rem 1.75rem;border-radius:12px;min-width:18rem}}
label{{display:block;font-size:0.85rem;margin:0.6rem 0 0.25rem;opacity:0.85}}
input{{width:100%;box-sizing:border-box;padding:0.55rem 0.65rem;border-radius:8px;
border:1px solid #374151;background:#0b0f14;color:#e8eef5}}
button{{margin-top:1rem;width:100%;padding:0.7rem;border:0;border-radius:8px;
background:#1d4ed8;color:#fff;font-weight:600;cursor:pointer}}
.err{{color:#fca5a5;font-size:0.9rem}}
h1{{font-size:1.1rem;margin:0 0 0.5rem}}
</style></head><body>
<form method="post" action="/admin/login" id="admin-login-form">
  <h1>Operator admin</h1>
  <p style="opacity:0.7;font-size:0.85rem;margin:0 0 0.75rem">Paid download grants</p>
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


def render_admin_html(grants: list[dict[str, Any]] | None = None) -> bytes:
    grants = grants if grants is not None else list_recent_grants(50)
    rows = []
    for g in grants:
        tok = str(g.get("token") or "")
        tok_short = (tok[:10] + "…") if len(tok) > 12 else tok
        used = g.get("used_at")
        used_s = "used" if used else str(g.get("status") or "")
        rows.append(
            "<tr>"
            f"<td>{_escape(str(g.get('platform') or ''))}</td>"
            f"<td>{_escape(str(g.get('filename') or ''))}</td>"
            f"<td>{int(g.get('amount_pence') or 0)} { _escape(str(g.get('currency') or ''))}</td>"
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
    body = f"""<!DOCTYPE html>
<html lang="en"><head>
<meta charset="utf-8"/><meta name="viewport" content="width=device-width, initial-scale=1"/>
<title>Admin — paid downloads</title>
<style>
body{{margin:0;padding:1.5rem;background:#0b0f14;color:#e8eef5;font-family:system-ui,sans-serif}}
h1{{font-size:1.25rem}} a{{color:#93c5fd}}
table{{border-collapse:collapse;width:100%;max-width:56rem;font-size:0.9rem}}
th,td{{border-bottom:1px solid #1f2937;padding:0.45rem 0.5rem;text-align:left}}
th{{opacity:0.75;font-weight:600}}
.top{{display:flex;gap:1rem;align-items:center;margin-bottom:1rem;flex-wrap:wrap}}
</style></head><body>
<div class="top">
  <h1 id="admin-heading">Paid download grants</h1>
  <a href="/admin/logout" id="admin-logout">Log out</a>
  <a href="/">Status page</a>
</div>
<p style="opacity:0.75">Recent Stripe-verified download tokens (£2.45 GBP each). Secrets never shown.</p>
<table id="admin-grants-table">
  <thead><tr>
    <th>Platform</th><th>Filename</th><th>Amount</th><th>Status</th><th>Token</th><th>Session</th>
  </tr></thead>
  <tbody>
{table}
  </tbody>
</table>
</body></html>
"""
    return body.encode("utf-8")


def _escape(s: str) -> str:
    return (
        s.replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
    )
