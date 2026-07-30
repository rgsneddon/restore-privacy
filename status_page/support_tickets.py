"""Public customer support tickets — form, durable store, email to rus@.

Minimal ticket architecture:
  - Ticket id: RPT-SUP-… (public reference)
  - Fields: contact email, subject, message; optional platform, app version, keygen
  - Persist under status data dir (SQLite)
  - Notify SUPPORT_EMAIL via fulfilment SMTP path
"""

from __future__ import annotations

import html
import json
import os
import re
import secrets
import sqlite3
import time
from pathlib import Path
from typing import Any, Callable, Optional

# Fixed product support inbox (objective).
SUPPORT_INBOX = "rus@restoreprivacy.online"
SUPPORT_PATH = "/support"
SUPPORT_LINK_ID = "support-link"

# Optional public reply address on the ticket email (same as fulfilment from).
DEFAULT_FROM_FALLBACK = "noreply@restoreprivacy.online"

_EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


def support_data_dir() -> Path:
    """Directory for support_tickets.sqlite (alongside other status data)."""
    env = (os.environ.get("RPT_SUPPORT_DATA_DIR") or "").strip()
    if env:
        return Path(env)
    # Prefer payment data dir sibling when present
    try:
        from payments import payment_data_dir

        return payment_data_dir()
    except Exception:  # noqa: BLE001
        pass
    here = Path(__file__).resolve().parent
    d = here / "data"
    d.mkdir(parents=True, exist_ok=True)
    return d


def support_db_path() -> Path:
    return support_data_dir() / "support_tickets.sqlite"


def new_ticket_id(*, now: float | None = None) -> str:
    """Public ticket reference: RPT-SUP-<hex> (unique, not sequential)."""
    t = int(now if now is not None else time.time())
    return f"RPT-SUP-{t:x}-{secrets.token_hex(4)}".upper()


def validate_support_form(
    *,
    email: str,
    subject: str,
    message: str,
    platform: str = "",
    app_version: str = "",
    keygen: str = "",
) -> tuple[bool, str, dict[str, str]]:
    """Return (ok, error, cleaned_fields). Pure — no I/O."""
    em = (email or "").strip()
    sub = (subject or "").strip()
    msg = (message or "").strip()
    plat = (platform or "").strip()[:40]
    ver = (app_version or "").strip()[:32]
    kg = (keygen or "").strip().upper()[:80]
    if not em or not _EMAIL_RE.match(em):
        return False, "Please enter a valid email address.", {}
    if len(sub) < 3:
        return False, "Please enter a short subject (at least 3 characters).", {}
    if len(msg) < 10:
        return False, "Please describe the issue (at least 10 characters).", {}
    if len(sub) > 200:
        return False, "Subject is too long.", {}
    if len(msg) > 8000:
        return False, "Message is too long (8000 character max).", {}
    return True, "", {
        "email": em,
        "subject": sub,
        "message": msg,
        "platform": plat,
        "app_version": ver,
        "keygen": kg,
    }


def build_support_email(
    *,
    ticket_id: str,
    email: str,
    subject: str,
    message: str,
    platform: str = "",
    app_version: str = "",
    keygen: str = "",
    created_at: float | None = None,
) -> dict[str, str]:
    """Build outbound mail fields for rus@ (pure; no SMTP)."""
    tid = (ticket_id or "").strip()
    ts = time.strftime(
        "%Y-%m-%d %H:%M:%S UTC",
        time.gmtime(created_at if created_at is not None else time.time()),
    )
    lines = [
        f"Support ticket: {tid}",
        f"Created (UTC): {ts}",
        f"From: {email}",
        f"Subject: {subject}",
        "",
        "--- Message ---",
        message,
        "",
        "--- Optional context ---",
        f"Platform: {platform or '(not given)'}",
        f"App version: {app_version or '(not given)'}",
        f"Keygen: {keygen or '(not given)'}",
        "",
        "— Restore Privacy support form",
        "https://restoreprivacy.online/support",
    ]
    body = "\n".join(lines)
    mail_subject = f"[RPT Support {tid}] {subject}"[:200]
    return {
        "to": SUPPORT_INBOX,
        "subject": mail_subject,
        "body": body,
        "reply_to": email,
        "ticket_id": tid,
    }


def init_support_db(path: Path | None = None) -> Path:
    p = path or support_db_path()
    p.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(p))
    try:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS support_tickets (
                ticket_id TEXT PRIMARY KEY,
                created_at REAL NOT NULL,
                email TEXT NOT NULL,
                subject TEXT NOT NULL,
                message TEXT NOT NULL,
                platform TEXT NOT NULL DEFAULT '',
                app_version TEXT NOT NULL DEFAULT '',
                keygen TEXT NOT NULL DEFAULT '',
                mail_status TEXT NOT NULL DEFAULT 'pending',
                mail_detail TEXT NOT NULL DEFAULT ''
            )
            """
        )
        conn.commit()
    finally:
        conn.close()
    return p


def persist_support_ticket(
    fields: dict[str, str],
    *,
    ticket_id: str | None = None,
    now: float | None = None,
    path: Path | None = None,
    mail_status: str = "pending",
    mail_detail: str = "",
) -> dict[str, Any]:
    """Insert ticket row; returns stored record dict."""
    p = init_support_db(path)
    tid = (ticket_id or new_ticket_id(now=now)).strip()
    t = float(now if now is not None else time.time())
    row = {
        "ticket_id": tid,
        "created_at": t,
        "email": fields.get("email") or "",
        "subject": fields.get("subject") or "",
        "message": fields.get("message") or "",
        "platform": fields.get("platform") or "",
        "app_version": fields.get("app_version") or "",
        "keygen": fields.get("keygen") or "",
        "mail_status": mail_status,
        "mail_detail": mail_detail[:500],
    }
    conn = sqlite3.connect(str(p))
    try:
        conn.execute(
            """
            INSERT INTO support_tickets(
                ticket_id, created_at, email, subject, message,
                platform, app_version, keygen, mail_status, mail_detail
            ) VALUES (?,?,?,?,?,?,?,?,?,?)
            """,
            (
                row["ticket_id"],
                row["created_at"],
                row["email"],
                row["subject"],
                row["message"],
                row["platform"],
                row["app_version"],
                row["keygen"],
                row["mail_status"],
                row["mail_detail"],
            ),
        )
        conn.commit()
    finally:
        conn.close()
    return row


def update_ticket_mail_status(
    ticket_id: str,
    *,
    mail_status: str,
    mail_detail: str = "",
    path: Path | None = None,
) -> None:
    p = path or support_db_path()
    if not p.is_file():
        return
    conn = sqlite3.connect(str(p))
    try:
        conn.execute(
            "UPDATE support_tickets SET mail_status=?, mail_detail=? WHERE ticket_id=?",
            (mail_status, (mail_detail or "")[:500], ticket_id),
        )
        conn.commit()
    finally:
        conn.close()


def send_support_ticket_email(
    mail: dict[str, str],
    *,
    transport: Callable[[dict[str, Any]], dict[str, Any]] | None = None,
) -> dict[str, Any]:
    """Send support notification using fulfilment SMTP config.

    *transport* injects a fake sender for tests: (payload) -> {ok, error?}.
    """
    payload = {
        "to": mail.get("to") or SUPPORT_INBOX,
        "subject": mail.get("subject") or "",
        "body_text": mail.get("body") or "",
        "reply_to": mail.get("reply_to") or "",
        "ticket_id": mail.get("ticket_id") or "",
    }
    if transport is not None:
        return transport(payload)
    try:
        from payments import fulfilment_smtp_config
    except Exception as exc:  # noqa: BLE001
        return {"ok": False, "error": f"smtp_config:{exc}"}
    cfg = fulfilment_smtp_config()
    host = str(cfg.get("host") or "").strip()
    if not host:
        return {"ok": False, "error": "smtp_not_configured"}
    try:
        import smtplib
        from email.message import EmailMessage

        msg = EmailMessage()
        msg["Subject"] = payload["subject"]
        msg["From"] = str(cfg.get("from_addr") or DEFAULT_FROM_FALLBACK)
        msg["To"] = payload["to"]
        if payload["reply_to"]:
            msg["Reply-To"] = payload["reply_to"]
        msg.set_content(payload["body_text"])
        port = int(cfg.get("port") or 587)
        user = str(cfg.get("user") or "")
        password = str(cfg.get("password") or "")
        with smtplib.SMTP(host, port, timeout=30) as smtp:
            smtp.ehlo()
            if cfg.get("use_tls"):
                smtp.starttls()
                smtp.ehlo()
            if user:
                smtp.login(user, password)
            smtp.send_message(msg)
        return {"ok": True, "error": None}
    except Exception as exc:  # noqa: BLE001
        return {"ok": False, "error": f"{type(exc).__name__}:{str(exc)[:200]}"}


def create_support_ticket(
    *,
    email: str,
    subject: str,
    message: str,
    platform: str = "",
    app_version: str = "",
    keygen: str = "",
    now: float | None = None,
    path: Path | None = None,
    transport: Callable[[dict[str, Any]], dict[str, Any]] | None = None,
    send_mail: bool = True,
) -> dict[str, Any]:
    """Validate, persist, optionally email. Returns ticket result dict."""
    ok, err, fields = validate_support_form(
        email=email,
        subject=subject,
        message=message,
        platform=platform,
        app_version=app_version,
        keygen=keygen,
    )
    if not ok:
        return {"ok": False, "error": err, "ticket_id": ""}
    t = float(now if now is not None else time.time())
    tid = new_ticket_id(now=t)
    row = persist_support_ticket(
        fields, ticket_id=tid, now=t, path=path, mail_status="pending"
    )
    mail = build_support_email(
        ticket_id=tid,
        email=fields["email"],
        subject=fields["subject"],
        message=fields["message"],
        platform=fields["platform"],
        app_version=fields["app_version"],
        keygen=fields["keygen"],
        created_at=t,
    )
    mail_result: dict[str, Any] = {"ok": True, "error": None, "skipped": True}
    if send_mail:
        mail_result = send_support_ticket_email(mail, transport=transport)
        st = "sent" if mail_result.get("ok") else "failed"
        update_ticket_mail_status(
            tid,
            mail_status=st,
            mail_detail=str(mail_result.get("error") or "ok")[:500],
            path=path,
        )
        row["mail_status"] = st
        row["mail_detail"] = str(mail_result.get("error") or "")[:500]
    return {
        "ok": True,
        "ticket_id": tid,
        "error": "",
        "mail": mail_result,
        "email_payload": mail,
        "record": row,
    }


def render_support_page_html(
    *,
    error: str = "",
    success_ticket_id: str = "",
    prefill: dict[str, str] | None = None,
) -> str:
    """Full HTML page for /support (public chrome + form)."""
    try:
        from public_chrome import (
            PUBLIC_BRAND_TITLE,
            public_brand_header_html,
            public_head_open,
            public_page_close,
        )
    except ImportError:  # pragma: no cover
        from status_page.public_chrome import (  # type: ignore
            PUBLIC_BRAND_TITLE,
            public_brand_header_html,
            public_head_open,
            public_page_close,
        )
    pre = prefill or {}
    err_html = (
        f'<p class="support-err" role="alert">{html.escape(error)}</p>'
        if error
        else ""
    )
    ok_html = ""
    if success_ticket_id:
        tid = html.escape(success_ticket_id)
        ok_html = (
            f'<div class="support-ok" role="status">'
            f"<p><strong>Ticket received.</strong> Your reference is "
            f"<code id=\"support-ticket-id\">{tid}</code>.</p>"
            f"<p>We emailed the team at {html.escape(SUPPORT_INBOX)}. "
            f"Keep this reference if you write again.</p></div>"
        )
    fields = {
        "email": html.escape(pre.get("email") or ""),
        "subject": html.escape(pre.get("subject") or ""),
        "message": html.escape(pre.get("message") or ""),
        "platform": html.escape(pre.get("platform") or ""),
        "app_version": html.escape(pre.get("app_version") or ""),
        "keygen": html.escape(pre.get("keygen") or ""),
    }
    # Support form chrome lives in public_site_css (theme-aware inputs / CTAs).
    head = public_head_open(
        title=f"Support — {PUBLIC_BRAND_TITLE}",
        extra_css="",
    )
    header = public_brand_header_html(active="support")
    close = public_page_close()
    return f"""{head}
  <div class="page-shell" id="support-page-shell" data-page="support">
{header}
<main class="support-wrap panel-card" id="support-main" data-chrome="pro">
  <h2>Customer support</h2>
  <p class="support-lead">
    Tell us what went wrong. We open a ticket and email
    <strong>{html.escape(SUPPORT_INBOX)}</strong>. You get a reference number to quote later.
  </p>
  {ok_html}
  {err_html}
  <form class="support-form" method="post" action="{SUPPORT_PATH}" id="support-form">
    <label for="support-email">Your email *</label>
    <input id="support-email" name="email" type="email" required
      autocomplete="email" value="{fields['email']}"
      placeholder="you@example.com"/>

    <label for="support-subject">Subject *</label>
    <input id="support-subject" name="subject" type="text" required
      maxlength="200" value="{fields['subject']}"
      placeholder="Short summary"/>

    <label for="support-message">Message *</label>
    <textarea id="support-message" name="message" required
      maxlength="8000" placeholder="What happened? Steps to reproduce help.">{fields['message']}</textarea>

    <label for="support-platform">Device / platform <span class="hint">(optional)</span></label>
    <select id="support-platform" name="platform">
      <option value="">— select —</option>
      {''.join(
        f'<option value="{p}"' + (' selected' if fields['platform']==p else '') + f'>{p}</option>'
        for p in ('windows','macos','ios','android','linux','other')
      )}
    </select>

    <label for="support-version">App version <span class="hint">(optional, e.g. 0.5.8)</span></label>
    <input id="support-version" name="app_version" type="text" maxlength="32"
      value="{fields['app_version']}" placeholder="0.5.8"/>

    <label for="support-keygen">Keygen <span class="hint">(optional — only if relevant)</span></label>
    <input id="support-keygen" name="keygen" type="text" maxlength="80"
      value="{fields['keygen']}" placeholder="RPT-KEY-…"/>
    <p class="hint">We never ask for passwords. Do not paste card details.</p>

    <button type="submit" id="support-submit">Send support ticket</button>
  </form>
</main>
  </div>
{close}
"""
