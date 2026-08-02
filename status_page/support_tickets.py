"""Public customer support tickets — form, durable store, email to rus@.

Minimal ticket architecture:
  - Ticket id: short sequential ``RPS-###`` (public reference)
  - Fields: contact email, subject, message; optional platform, app version
  - Keygen is **not** collected on the public form
  - Persist under status data dir (SQLite)
  - Notify SUPPORT_EMAIL via fulfilment SMTP path
  - Admin: one-way close + confirm-gated clear-all
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

# Admin management surface (authenticated).
ADMIN_SUPPORT_TICKETS_PATH = "/admin/support-tickets"
ADMIN_SUPPORT_CLOSE_PATH = "/admin/support-tickets/close"
ADMIN_SUPPORT_CLEAR_PATH = "/admin/support-tickets/clear"
ADMIN_NAV_SUPPORT_TICKETS_ID = "admin-nav-support-tickets"

# Explicit confirm token for clear_all_support_tickets (no silent wipe).
CLEAR_ALL_SUPPORT_TICKETS_CONFIRM = "CLEAR_ALL_SUPPORT_TICKETS"

# Ticket lifecycle (one-way: open → closed only).
TICKET_STATUS_OPEN = "open"
TICKET_STATUS_CLOSED = "closed"

# Short public ticket references: RPS-001, RPS-002, …
TICKET_ID_PREFIX = "RPS"
TICKET_ID_RE = re.compile(r"^RPS-(\d+)$", re.IGNORECASE)

# Fallback From when SMTP user/from unset — must be a real mailbox owner (not noreply).
DEFAULT_FROM_FALLBACK = "rus@restoreprivacy.online"

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


def format_ticket_id(n: int) -> str:
    """Format sequence number as ``RPS-001`` (at least 3 digits)."""
    n = max(1, int(n))
    return f"{TICKET_ID_PREFIX}-{n:03d}"


def parse_ticket_seq(ticket_id: str) -> int | None:
    """Return sequence int from ``RPS-###``, or None if not that shape."""
    m = TICKET_ID_RE.match((ticket_id or "").strip())
    if not m:
        return None
    try:
        return int(m.group(1))
    except ValueError:
        return None


def next_ticket_seq(*, path: Path | None = None) -> int:
    """Next free sequence for ``RPS-###`` from the ticket store (max+1)."""
    p = init_support_db(path)
    conn = sqlite3.connect(str(p))
    try:
        cur = conn.execute(
            "SELECT ticket_id FROM support_tickets WHERE ticket_id LIKE 'RPS-%'"
        )
        max_n = 0
        for (tid,) in cur.fetchall():
            n = parse_ticket_seq(str(tid or ""))
            if n is not None and n > max_n:
                max_n = n
        return max_n + 1
    finally:
        conn.close()


def new_ticket_id(
    *,
    now: float | None = None,
    path: Path | None = None,
    seq: int | None = None,
) -> str:
    """Public ticket reference: short sequential ``RPS-001``, ``RPS-002``, …

    *seq* forces a number (tests). Otherwise allocates from the store max+1.
    *now* is ignored (kept for call-site compat).
    """
    _ = now
    if seq is not None:
        return format_ticket_id(seq)
    return format_ticket_id(next_ticket_seq(path=path))


def validate_support_form(
    *,
    email: str,
    subject: str,
    message: str,
    platform: str = "",
    app_version: str = "",
    keygen: str = "",  # accepted but ignored (field removed from public form)
) -> tuple[bool, str, dict[str, str]]:
    """Return (ok, error, cleaned_fields). Pure — no I/O. Keygen is not collected."""
    _ = keygen
    em = (email or "").strip()
    sub = (subject or "").strip()
    msg = (message or "").strip()
    plat = (platform or "").strip()[:40]
    ver = (app_version or "").strip()[:32]
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
        "keygen": "",  # no longer collected on the public form
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
    _ = keygen  # not presented for new tickets
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
        "kind": "staff_notify",
    }


def build_support_requester_confirmation_email(
    *,
    ticket_id: str,
    email: str,
    subject: str,
    message: str,
    platform: str = "",
    app_version: str = "",
    created_at: float | None = None,
) -> dict[str, str]:
    """Build confirmation mail **to the requester** with a copy of their ticket.

    Pure helper (no SMTP). Sent on successful open alongside staff notify so
    the customer keeps a reference and content copy in their inbox.
    """
    tid = (ticket_id or "").strip()
    to = (email or "").strip()
    sub = (subject or "").strip()
    ts = time.strftime(
        "%Y-%m-%d %H:%M:%S UTC",
        time.gmtime(created_at if created_at is not None else time.time()),
    )
    lines = [
        f"We received your Restore Privacy support ticket {tid}.",
        "",
        "This is a confirmation copy for your records. Our team was also notified.",
        f"Created (UTC): {ts}",
        f"Your email: {to}",
        f"Subject: {sub}",
        "",
        "--- Your message ---",
        message or "(empty)",
        "",
        "--- Optional context ---",
        f"Platform: {platform or '(not given)'}",
        f"App version: {app_version or '(not given)'}",
        "",
        "Quote this ticket reference if you write again:",
        f"  {tid}",
        "",
        "Open a new ticket anytime at:",
        "https://restoreprivacy.online/support",
        "",
        "— Restore Privacy Support",
        f"{SUPPORT_INBOX}",
        "https://restoreprivacy.online/",
    ]
    return {
        "to": to,
        "subject": f"[RPT Support {tid}] We received your ticket"[:200],
        "body": "\n".join(lines),
        "reply_to": SUPPORT_INBOX,
        "ticket_id": tid,
        "kind": "requester_confirmation",
    }


def _migrate_support_schema(conn: sqlite3.Connection) -> None:
    """Add open/closed lifecycle columns when missing (ALTER-safe)."""
    cols = {str(r[1]) for r in conn.execute("PRAGMA table_info(support_tickets)")}
    if "status" not in cols:
        conn.execute(
            "ALTER TABLE support_tickets ADD COLUMN status TEXT NOT NULL DEFAULT 'open'"
        )
    if "closed_at" not in cols:
        conn.execute("ALTER TABLE support_tickets ADD COLUMN closed_at REAL")
    if "close_mail_status" not in cols:
        conn.execute(
            "ALTER TABLE support_tickets ADD COLUMN close_mail_status "
            "TEXT NOT NULL DEFAULT ''"
        )
    if "close_mail_detail" not in cols:
        conn.execute(
            "ALTER TABLE support_tickets ADD COLUMN close_mail_detail "
            "TEXT NOT NULL DEFAULT ''"
        )


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
                mail_detail TEXT NOT NULL DEFAULT '',
                status TEXT NOT NULL DEFAULT 'open',
                closed_at REAL,
                close_mail_status TEXT NOT NULL DEFAULT '',
                close_mail_detail TEXT NOT NULL DEFAULT ''
            )
            """
        )
        _migrate_support_schema(conn)
        conn.commit()
    finally:
        conn.close()
    return p


def _row_to_ticket(row: sqlite3.Row | tuple) -> dict[str, Any]:
    """Normalize a DB row to a ticket dict (handles optional lifecycle cols)."""
    if isinstance(row, sqlite3.Row):
        d = {k: row[k] for k in row.keys()}
    else:
        # Fallback positional (should not hit with row_factory)
        keys = (
            "ticket_id",
            "created_at",
            "email",
            "subject",
            "message",
            "platform",
            "app_version",
            "keygen",
            "mail_status",
            "mail_detail",
            "status",
            "closed_at",
            "close_mail_status",
            "close_mail_detail",
        )
        d = {keys[i]: row[i] if i < len(row) else None for i in range(len(keys))}
    status = str(d.get("status") or TICKET_STATUS_OPEN).strip().lower()
    if status not in (TICKET_STATUS_OPEN, TICKET_STATUS_CLOSED):
        status = TICKET_STATUS_OPEN
    return {
        "ticket_id": str(d.get("ticket_id") or ""),
        "created_at": float(d.get("created_at") or 0),
        "email": str(d.get("email") or ""),
        "subject": str(d.get("subject") or ""),
        "message": str(d.get("message") or ""),
        "platform": str(d.get("platform") or ""),
        "app_version": str(d.get("app_version") or ""),
        "keygen": str(d.get("keygen") or ""),
        "mail_status": str(d.get("mail_status") or ""),
        "mail_detail": str(d.get("mail_detail") or ""),
        "status": status,
        "closed_at": d.get("closed_at"),
        "close_mail_status": str(d.get("close_mail_status") or ""),
        "close_mail_detail": str(d.get("close_mail_detail") or ""),
    }


def list_support_tickets(
    *,
    path: Path | None = None,
    limit: int = 500,
) -> list[dict[str, Any]]:
    """Return tickets newest-first (open first within same second is not guaranteed)."""
    p = init_support_db(path)
    conn = sqlite3.connect(str(p))
    conn.row_factory = sqlite3.Row
    try:
        cur = conn.execute(
            """
            SELECT ticket_id, created_at, email, subject, message,
                   platform, app_version, keygen, mail_status, mail_detail,
                   status, closed_at, close_mail_status, close_mail_detail
            FROM support_tickets
            ORDER BY
              CASE WHEN lower(COALESCE(status,'')) = 'closed' THEN 1 ELSE 0 END,
              created_at DESC
            LIMIT ?
            """,
            (max(1, int(limit)),),
        )
        return [_row_to_ticket(r) for r in cur.fetchall()]
    finally:
        conn.close()


def count_support_tickets(*, path: Path | None = None) -> int:
    """Return number of rows in the support ticket store."""
    p = init_support_db(path)
    conn = sqlite3.connect(str(p))
    try:
        return int(conn.execute("SELECT COUNT(*) FROM support_tickets").fetchone()[0])
    finally:
        conn.close()


def clear_all_support_tickets(
    *,
    confirm: str,
    path: Path | None = None,
    now: float | None = None,
) -> dict[str, Any]:
    """Delete every support ticket so the admin table is empty.

    Requires ``confirm == CLEAR_ALL_SUPPORT_TICKETS_CONFIRM`` — refuses otherwise
    (no silent wipe). After a successful clear, the next create starts at
    ``RPS-001`` again (sequence from empty store).
    """
    if (confirm or "").strip() != CLEAR_ALL_SUPPORT_TICKETS_CONFIRM:
        raise ValueError(
            "clear_all_support_tickets refused: confirm must be "
            f"{CLEAR_ALL_SUPPORT_TICKETS_CONFIRM!r} (got {confirm!r})"
        )
    p = init_support_db(path)
    t = float(now if now is not None else time.time())
    conn = sqlite3.connect(str(p))
    try:
        n = int(conn.execute("SELECT COUNT(*) FROM support_tickets").fetchone()[0])
        conn.execute("DELETE FROM support_tickets")
        conn.commit()
        remaining = int(
            conn.execute("SELECT COUNT(*) FROM support_tickets").fetchone()[0]
        )
    finally:
        conn.close()
    return {
        "ok": True,
        "confirm": CLEAR_ALL_SUPPORT_TICKETS_CONFIRM,
        "db_path": str(p),
        "deleted": n,
        "remaining": remaining,
        "cleared_at": t,
    }


def get_support_ticket(
    ticket_id: str,
    *,
    path: Path | None = None,
) -> dict[str, Any] | None:
    """Fetch one ticket by id, or None."""
    tid = (ticket_id or "").strip()
    if not tid:
        return None
    p = init_support_db(path)
    conn = sqlite3.connect(str(p))
    conn.row_factory = sqlite3.Row
    try:
        cur = conn.execute(
            """
            SELECT ticket_id, created_at, email, subject, message,
                   platform, app_version, keygen, mail_status, mail_detail,
                   status, closed_at, close_mail_status, close_mail_detail
            FROM support_tickets WHERE ticket_id=?
            """,
            (tid,),
        )
        r = cur.fetchone()
        return _row_to_ticket(r) if r else None
    finally:
        conn.close()


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
        "status": TICKET_STATUS_OPEN,
        "closed_at": None,
        "close_mail_status": "",
        "close_mail_detail": "",
    }
    conn = sqlite3.connect(str(p))
    try:
        conn.execute(
            """
            INSERT INTO support_tickets(
                ticket_id, created_at, email, subject, message,
                platform, app_version, keygen, mail_status, mail_detail,
                status, closed_at, close_mail_status, close_mail_detail
            ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)
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
                row["status"],
                row["closed_at"],
                row["close_mail_status"],
                row["close_mail_detail"],
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


def build_ticket_closed_email(
    *,
    ticket_id: str,
    email: str,
    subject: str = "",
    closed_at: float | None = None,
) -> dict[str, str]:
    """Build close-notification mail **to the requester** (pure; no SMTP).

    Body states the ticket is closed and thanks them for getting in touch.
    """
    tid = (ticket_id or "").strip()
    to = (email or "").strip()
    sub = (subject or "").strip()
    ts = time.strftime(
        "%Y-%m-%d %H:%M:%S UTC",
        time.gmtime(closed_at if closed_at is not None else time.time()),
    )
    lines = [
        f"Your Restore Privacy support ticket {tid} is now closed.",
        "",
        f"Original subject: {sub or '(none)'}",
        f"Closed (UTC): {ts}",
        "",
        "Thank you for getting in touch. We appreciate you contacting us,",
        "and we hope the issue is resolved. If you need further help, please",
        "open a new support ticket at:",
        "https://restoreprivacy.online/support",
        "",
        "— Restore Privacy Support",
        "https://restoreprivacy.online/",
    ]
    return {
        "to": to,
        "subject": f"[RPT Support {tid}] Ticket closed — thank you"[:200],
        "body": "\n".join(lines),
        "reply_to": SUPPORT_INBOX,
        "ticket_id": tid,
    }


def close_support_ticket(
    ticket_id: str,
    *,
    path: Path | None = None,
    now: float | None = None,
    transport: Callable[[dict[str, Any]], dict[str, Any]] | None = None,
    send_mail: bool = True,
) -> dict[str, Any]:
    """One-way close: open → closed only. Sends close email to requester.

    Refuses reopen and double-close (status stays closed; returns ok=False).
    """
    tid = (ticket_id or "").strip()
    if not tid:
        return {"ok": False, "error": "missing_ticket_id", "ticket": None}
    ticket = get_support_ticket(tid, path=path)
    if not ticket:
        return {"ok": False, "error": "not_found", "ticket": None}
    if ticket.get("status") == TICKET_STATUS_CLOSED:
        return {
            "ok": False,
            "error": "already_closed",
            "ticket": ticket,
        }
    t = float(now if now is not None else time.time())
    p = init_support_db(path)
    conn = sqlite3.connect(str(p))
    try:
        cur = conn.execute(
            """
            UPDATE support_tickets
            SET status=?, closed_at=?
            WHERE ticket_id=? AND lower(COALESCE(status,'open')) != 'closed'
            """,
            (TICKET_STATUS_CLOSED, t, tid),
        )
        if cur.rowcount < 1:
            conn.commit()
            again = get_support_ticket(tid, path=path)
            return {
                "ok": False,
                "error": "already_closed" if again and again.get("status") == TICKET_STATUS_CLOSED else "update_failed",
                "ticket": again,
            }
        conn.commit()
    finally:
        conn.close()

    closed = get_support_ticket(tid, path=path) or ticket
    closed["status"] = TICKET_STATUS_CLOSED
    closed["closed_at"] = t

    mail = build_ticket_closed_email(
        ticket_id=tid,
        email=str(closed.get("email") or ""),
        subject=str(closed.get("subject") or ""),
        closed_at=t,
    )
    mail_result: dict[str, Any] = {"ok": True, "error": None, "skipped": True}
    if send_mail:
        mail_result = send_support_ticket_email(mail, transport=transport)
        st = "sent" if mail_result.get("ok") else "failed"
        detail = str(mail_result.get("error") or "ok")[:500]
        conn = sqlite3.connect(str(p))
        try:
            conn.execute(
                """
                UPDATE support_tickets
                SET close_mail_status=?, close_mail_detail=?
                WHERE ticket_id=?
                """,
                (st, detail, tid),
            )
            conn.commit()
        finally:
            conn.close()
        closed["close_mail_status"] = st
        closed["close_mail_detail"] = detail

    return {
        "ok": True,
        "error": "",
        "ticket": closed,
        "mail": mail_result,
        "email_payload": mail,
    }


def support_smtp_env_keys() -> list[str]:
    """Same env keys as fulfilment — support reuses Render SMTP settings."""
    try:
        from payments import fulfilment_smtp_env_keys

        return list(fulfilment_smtp_env_keys())
    except Exception:  # noqa: BLE001
        return [
            "RPT_FULFILMENT_SMTP_HOST",
            "RPT_FULFILMENT_SMTP_PORT",
            "RPT_FULFILMENT_SMTP_USER",
            "RPT_FULFILMENT_SMTP_PASSWORD",
            "RPT_FULFILMENT_FROM_EMAIL",
            "RPT_FULFILMENT_SMTP_TLS",
        ]


def support_smtp_config() -> dict[str, Any]:
    """Read SMTP for support tickets — identical source as fulfilment.

    Render ``RPT_FULFILMENT_SMTP_*`` (+ admin processor_env) drives both
    keygen fulfilment mail and support ticket notify/close mail.
    """
    try:
        from payments import fulfilment_smtp_config

        cfg = dict(fulfilment_smtp_config())
        cfg["purpose"] = "support_tickets"
        cfg["env_keys"] = support_smtp_env_keys()
        return cfg
    except Exception as exc:  # noqa: BLE001
        return {
            "host": "",
            "port": 587,
            "user": "",
            "password": "",
            "from_addr": DEFAULT_FROM_FALLBACK,
            "use_tls": True,
            "configured": False,
            "purpose": "support_tickets",
            "env_keys": support_smtp_env_keys(),
            "error": str(exc)[:200],
        }


def assess_support_smtp_readiness(
    cfg: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Non-secret readiness for support outbound mail (reuses fulfilment assess)."""
    try:
        from payments import assess_fulfilment_smtp_readiness, fulfilment_smtp_config

        c = cfg if isinstance(cfg, dict) else fulfilment_smtp_config()
        out = dict(assess_fulfilment_smtp_readiness(c))
        out["purpose"] = "support_tickets"
        out["uses_fulfilment_smtp"] = True
        out["env_keys"] = support_smtp_env_keys()
        # Clarify detail for support operators
        if out.get("email_flow_enabled"):
            out["support_detail"] = (
                "Support ticket notify/close will attempt SMTP via the same "
                "RPT_FULFILMENT_SMTP_* settings as keygen fulfilment."
            )
        else:
            out["support_detail"] = (
                "Support mail cannot send until fulfilment SMTP is fully set "
                f"({out.get('status') or 'not ready'})."
            )
        return out
    except Exception as exc:  # noqa: BLE001
        return {
            "status": "error",
            "email_flow_enabled": False,
            "purpose": "support_tickets",
            "uses_fulfilment_smtp": True,
            "env_keys": support_smtp_env_keys(),
            "detail": str(exc)[:200],
            "support_detail": str(exc)[:200],
        }


def send_support_ticket_email(
    mail: dict[str, str],
    *,
    transport: Callable[[dict[str, Any]], dict[str, Any]] | None = None,
    smtp_config: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Send support notification using fulfilment SMTP config (Render settings).

    *transport* injects a fake sender for tests: (payload) -> {ok, error?}.
    Used for both new-ticket staff notify and requester close notify.

    *smtp_config* injects a config dict (tests); default is
    :func:`support_smtp_config` / :func:`payments.fulfilment_smtp_config`.
    """
    to_addr = (mail.get("to") or SUPPORT_INBOX).strip()
    payload = {
        "to": to_addr,
        "subject": mail.get("subject") or "",
        "body_text": mail.get("body") or mail.get("body_text") or "",
        "reply_to": (mail.get("reply_to") or "").strip(),
        "ticket_id": mail.get("ticket_id") or "",
        "from_purpose": "support_tickets",
    }
    if not to_addr or "@" not in to_addr:
        return {"ok": False, "error": "missing_to_email", "sent": False}
    if transport is not None:
        try:
            result = transport(payload)
            if isinstance(result, dict):
                # Normalize transport shape
                if "sent" not in result and result.get("ok"):
                    result = {**result, "sent": True}
                return result
            return {"ok": True, "error": None, "sent": True}
        except Exception as exc:  # noqa: BLE001
            return {
                "ok": False,
                "error": f"{type(exc).__name__}:{str(exc)[:200]}",
                "sent": False,
            }

    cfg = dict(smtp_config) if isinstance(smtp_config, dict) else support_smtp_config()
    host = str(cfg.get("host") or "").strip()
    if not host:
        return {
            "ok": False,
            "error": "smtp_not_configured",
            "sent": False,
            "skipped": True,
            "env_keys": support_smtp_env_keys(),
        }
    try:
        import smtplib
        from email.message import EmailMessage

        # From must be owned by SMTP login mailbox (PrivateEmail 553 otherwise).
        # Prefer cfg from_addr only when it matches auth user; else use user.
        try:
            from payments import (
                _bare_email_address,
                _fulfilment_from_header,
                smtp_from_address_for_auth,
            )

            from_for_send = smtp_from_address_for_auth(cfg)
            from_header = _fulfilment_from_header(from_for_send)
            from_bare = _bare_email_address(from_for_send)
        except Exception:  # noqa: BLE001
            user_fb = str(cfg.get("user") or "").strip()
            from_raw = str(
                cfg.get("from_addr") or user_fb or DEFAULT_FROM_FALLBACK
            ).strip()
            # Prefer auth user over noreply fallback when available
            if user_fb and "@" in user_fb:
                from_header = user_fb
                from_bare = user_fb
            else:
                from_header = from_raw or DEFAULT_FROM_FALLBACK
                from_bare = from_header

        msg = EmailMessage()
        msg["Subject"] = payload["subject"]
        msg["From"] = from_header
        msg["To"] = payload["to"]
        if payload["reply_to"]:
            msg["Reply-To"] = payload["reply_to"]
        msg.set_content(payload["body_text"])
        port = int(cfg.get("port") or 587)
        user = str(cfg.get("user") or "")
        password = str(cfg.get("password") or "")
        # Same path as probe_fulfilment_smtp_login + send_fulfilment_email
        with smtplib.SMTP(host, port, timeout=30) as smtp:
            smtp.ehlo()
            if cfg.get("use_tls"):
                smtp.starttls()
                smtp.ehlo()
            if user:
                smtp.login(user, password)
            smtp.send_message(msg)
        return {
            "ok": True,
            "error": None,
            "sent": True,
            "skipped": False,
            "uses_fulfilment_smtp": True,
            "from": from_bare,
        }
    except Exception as exc:  # noqa: BLE001
        return {
            "ok": False,
            "error": f"{type(exc).__name__}:{str(exc)[:200]}",
            "sent": False,
            "uses_fulfilment_smtp": True,
        }


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
    tid = new_ticket_id(now=t, path=path)
    row = persist_support_ticket(
        fields, ticket_id=tid, now=t, path=path, mail_status="pending"
    )
    staff_mail = build_support_email(
        ticket_id=tid,
        email=fields["email"],
        subject=fields["subject"],
        message=fields["message"],
        platform=fields["platform"],
        app_version=fields["app_version"],
        keygen="",
        created_at=t,
    )
    customer_mail = build_support_requester_confirmation_email(
        ticket_id=tid,
        email=fields["email"],
        subject=fields["subject"],
        message=fields["message"],
        platform=fields["platform"],
        app_version=fields["app_version"],
        created_at=t,
    )
    staff_result: dict[str, Any] = {
        "ok": True,
        "error": None,
        "skipped": True,
        "sent": False,
    }
    customer_result: dict[str, Any] = {
        "ok": True,
        "error": None,
        "skipped": True,
        "sent": False,
    }
    if send_mail:
        # Staff notify first (ticket reaches support), then customer confirmation copy.
        staff_result = send_support_ticket_email(staff_mail, transport=transport)
        customer_result = send_support_ticket_email(
            customer_mail, transport=transport
        )
        staff_ok = bool(staff_result.get("ok"))
        customer_ok = bool(customer_result.get("ok"))
        if staff_ok and customer_ok:
            st = "sent"
        elif staff_ok or customer_ok:
            st = "partial"
        else:
            st = "failed"
        detail = (
            f"staff={'ok' if staff_ok else str(staff_result.get('error') or 'failed')};"
            f"customer={'ok' if customer_ok else str(customer_result.get('error') or 'failed')}"
        )[:500]
        update_ticket_mail_status(
            tid,
            mail_status=st,
            mail_detail=detail,
            path=path,
        )
        row["mail_status"] = st
        row["mail_detail"] = detail
    # Primary mail_sent: staff notified (team received ticket). Customer copy tracked separately.
    staff_sent = bool(staff_result.get("ok") and send_mail)
    customer_sent = bool(customer_result.get("ok") and send_mail)
    return {
        "ok": True,
        "ticket_id": tid,
        "error": "",
        "mail": staff_result,
        "mail_staff": staff_result,
        "mail_customer": customer_result,
        "mail_sent": staff_sent,
        "customer_mail_sent": customer_sent,
        "email_payload": staff_mail,
        "customer_email_payload": customer_mail,
        "record": row,
    }


def render_support_page_html(
    *,
    error: str = "",
    success_ticket_id: str = "",
    mail_sent: bool | None = None,
    customer_mail_sent: bool | None = None,
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
        # Honest mail lines: ticket always stored; staff + customer SMTP may differ
        if mail_sent is False:
            mail_line = (
                f"<p>Your ticket is saved. We could not send email right now "
                f"(site SMTP). Quote <code>{tid}</code> if you write again to "
                f"{html.escape(SUPPORT_INBOX)}.</p>"
            )
        elif customer_mail_sent is False:
            mail_line = (
                f"<p>We notified the team at {html.escape(SUPPORT_INBOX)} via site SMTP. "
                f"We could not email you a confirmation copy right now. "
                f"Keep reference <code>{tid}</code>.</p>"
            )
        else:
            mail_line = (
                f"<p>We notified the team at {html.escape(SUPPORT_INBOX)} via site SMTP "
                f"and emailed you a confirmation with a copy of your ticket. "
                f"Keep this reference if you write again.</p>"
            )
        ok_html = (
            f'<div class="support-ok" role="status" id="support-success">'
            f"<p><strong>Ticket received.</strong> Your reference is "
            f"<code id=\"support-ticket-id\">{tid}</code>.</p>"
            f"{mail_line}</div>"
        )
    fields = {
        "email": html.escape(pre.get("email") or ""),
        "subject": html.escape(pre.get("subject") or ""),
        "message": html.escape(pre.get("message") or ""),
        "platform": html.escape(pre.get("platform") or ""),
        "app_version": html.escape(pre.get("app_version") or ""),
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
  <p class="support-lead" id="support-lead">
    Tell us what went wrong. We will open a ticket and notify
    <strong>{html.escape(SUPPORT_INBOX)}</strong> of your issue. Please allow
    up to 48hrs for responses to your support ticket. You will receive a
    confirmation email with a copy of your message and a short reference
    (e.g. <code>RPS-001</code>). Ensure to fill in all below fields…
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

    <p class="hint">We never ask for passwords or card details. Do not paste secrets.</p>

    <button type="submit" id="support-submit">Send support ticket</button>
  </form>
</main>
  </div>
{close}
"""
