"""Admin support tickets: nav, table fields, one-way close, close email."""

from __future__ import annotations

import re
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "status_page"))

# Inline handlers blocked by CSP script-src 'self'
_INLINE_HANDLER_RE = re.compile(
    r"\s+on(?:change|click|submit|load|error|input|focus|blur)\s*=",
    re.IGNORECASE,
)


def _field_cell_text(page: str, field: str) -> str:
    """Extract text content of the first data-field cell for *field*."""
    m = re.search(
        rf'<td[^>]*data-field="{re.escape(field)}"[^>]*>(.*?)</td>',
        page,
        re.IGNORECASE | re.DOTALL,
    )
    if not m:
        return ""
    text = re.sub(r"<[^>]+>", " ", m.group(1))
    return re.sub(r"\s+", " ", text).strip()


class TestAdminSupportNav(unittest.TestCase):
    def test_sidebar_has_support_tickets_link(self) -> None:
        from admin_panel import _admin_sidebar_html
        from support_tickets import (
            ADMIN_NAV_SUPPORT_TICKETS_ID,
            ADMIN_SUPPORT_TICKETS_PATH,
        )

        html = _admin_sidebar_html(active="support-tickets")
        self.assertIn(f'id="{ADMIN_NAV_SUPPORT_TICKETS_ID}"', html)
        self.assertIn(f'href="{ADMIN_SUPPORT_TICKETS_PATH}"', html)
        self.assertIn("Support tickets", html)
        self.assertIn("active", html)
        bare = _admin_sidebar_html(active="home")
        self.assertIn(ADMIN_NAV_SUPPORT_TICKETS_ID, bare)
        self.assertIn(ADMIN_SUPPORT_TICKETS_PATH, bare)


class TestAdminSupportTableAndClose(unittest.TestCase):
    def test_list_table_and_one_way_close_with_email(self) -> None:
        from admin_panel import render_admin_support_tickets_page_html
        from support_tickets import (
            TICKET_STATUS_CLOSED,
            TICKET_STATUS_OPEN,
            build_ticket_closed_email,
            close_support_ticket,
            create_support_ticket,
            get_support_ticket,
            list_support_tickets,
            update_ticket_mail_status,
        )

        with tempfile.TemporaryDirectory() as td:
            db = Path(td) / "support_tickets.sqlite"
            sent: list[dict] = []

            def transport(payload: dict) -> dict:
                sent.append(dict(payload))
                return {"ok": True, "error": None}

            created = create_support_ticket(
                email="user@example.com",
                subject="Cannot connect after unlock",
                message="Tunnel stays Connecting after unlock on macOS.",
                platform="macos",
                app_version="0.5.8",
                path=db,
                send_mail=False,
            )
            self.assertTrue(created["ok"])
            tid = created["ticket_id"]
            self.assertEqual(tid, "RPS-001")
            self.assertRegex(tid, r"^RPS-\d{3}$")
            rec = get_support_ticket(tid, path=db)
            assert rec is not None
            self.assertEqual(rec["status"], TICKET_STATUS_OPEN)
            self.assertEqual(rec.get("keygen") or "", "")

            # Honest staff-mail failure must not replace ticket field values
            update_ticket_mail_status(
                tid,
                mail_status="failed",
                mail_detail="smtp not configured",
                path=db,
            )

            listed = list_support_tickets(path=db)
            self.assertEqual(len(listed), 1)
            self.assertEqual(listed[0]["ticket_id"], tid)
            self.assertEqual(listed[0]["mail_status"], "failed")
            self.assertEqual(listed[0]["email"], "user@example.com")

            page = render_admin_support_tickets_page_html(
                tickets=list_support_tickets(path=db)
            ).decode("utf-8")
            self.assertIn("admin-support-table", page)
            # Bound field cells (ticket store values, not admin chrome)
            self.assertEqual(_field_cell_text(page, "ticket_id"), tid)
            self.assertEqual(_field_cell_text(page, "email"), "user@example.com")
            self.assertEqual(
                _field_cell_text(page, "subject"), "Cannot connect after unlock"
            )
            self.assertIn("Tunnel stays Connecting", _field_cell_text(page, "message"))
            self.assertEqual(_field_cell_text(page, "platform"), "macos")
            self.assertEqual(_field_cell_text(page, "app_version"), "0.5.8")
            self.assertIn("failed", _field_cell_text(page, "mail_status"))
            self.assertIn("smtp not configured", _field_cell_text(page, "mail_status"))
            self.assertIn("open", _field_cell_text(page, "status").lower())
            # Staff mail "failed" must not bleed into identity fields
            self.assertNotIn("failed", _field_cell_text(page, "email"))
            self.assertNotIn("failed", _field_cell_text(page, "subject"))
            self.assertNotIn("staff admin", page.lower())
            # Keygen column removed from admin presentation
            self.assertNotIn(">Keygen<", page)
            self.assertNotIn("RPT-KEY-TEST", page)
            self.assertIn("admin-nav-support-tickets", page)
            self.assertIn("/admin/support-tickets/close", page)
            # Textless green open switch as native submit (CSP-safe)
            self.assertIn("ticket-toggle-open", page)
            self.assertIn("ticket-toggle-submit", page)
            self.assertIn(f'id="ticket-toggle-{tid}"', page)
            self.assertIn('type="submit"', page)
            self.assertIn("ticket-toggle-track", page)
            self.assertIn("ticket-toggle-knob", page)
            self.assertNotIn("Open → Closed", page)
            self.assertNotIn("ticket-close-label", page)
            self.assertNotIn("ticket-close-checkbox", page)
            self.assertNotIn("ticket-toggle-input", page)
            # No CSP-blocked inline event handlers on the support table control
            self.assertIsNone(_INLINE_HANDLER_RE.search(page))
            self.assertNotIn("onchange=", page.lower())
            # External script allowed by script-src 'self'
            self.assertIn('src="/static/admin_support_tickets.js"', page)
            self.assertIn("open", page.lower())

            # Pure close-email builder
            mail = build_ticket_closed_email(
                ticket_id=tid,
                email="user@example.com",
                subject="Cannot connect after unlock",
                closed_at=1_700_000_000,
            )
            self.assertEqual(mail["to"], "user@example.com")
            self.assertIn(tid, mail["subject"])
            self.assertIn("closed", mail["subject"].lower())
            self.assertIn("closed", mail["body"].lower())
            self.assertIn("thank", mail["body"].lower())
            self.assertIn(tid, mail["body"])

            # Close succeeds + emails requester
            result = close_support_ticket(
                tid, path=db, transport=transport, send_mail=True
            )
            self.assertTrue(result["ok"], result)
            self.assertEqual(result["ticket"]["status"], TICKET_STATUS_CLOSED)
            self.assertEqual(len(sent), 1)
            self.assertEqual(sent[0]["to"], "user@example.com")
            self.assertIn(tid, sent[0]["subject"])
            self.assertIn("thank", (sent[0].get("body_text") or "").lower())

            closed = get_support_ticket(tid, path=db)
            assert closed is not None
            self.assertEqual(closed["status"], TICKET_STATUS_CLOSED)
            self.assertIsNotNone(closed.get("closed_at"))
            self.assertEqual(closed.get("close_mail_status"), "sent")

            # Second close refused — stays closed
            again = close_support_ticket(
                tid, path=db, transport=transport, send_mail=True
            )
            self.assertFalse(again["ok"])
            self.assertEqual(again["error"], "already_closed")
            self.assertEqual(again["ticket"]["status"], TICKET_STATUS_CLOSED)
            self.assertEqual(len(sent), 1)  # no second email

            page2 = render_admin_support_tickets_page_html(
                tickets=list_support_tickets(path=db)
            ).decode("utf-8")
            self.assertIn("closed", page2.lower())
            self.assertIn("ticket-toggle-closed", page2)
            self.assertIn("#ef4444", page2)  # red closed switch
            self.assertIn("#22c55e", page)  # green open switch styles
            self.assertEqual(_field_cell_text(page2, "status").lower(), "closed")
            self.assertIn("sent", _field_cell_text(page2, "close_mail_status").lower())
            # Closed: no submit control for this ticket
            self.assertIsNone(
                re.search(
                    rf'id="ticket-toggle-{re.escape(tid)}"[^>]*type="submit"',
                    page2,
                )
            )
            self.assertIsNone(_INLINE_HANDLER_RE.search(page2))

    def test_csp_safe_static_script_exists(self) -> None:
        script = ROOT / "status_page" / "static" / "admin_support_tickets.js"
        self.assertTrue(script.is_file(), f"missing {script}")
        text = script.read_text(encoding="utf-8")
        self.assertIn("admin-support-close-form", text)
        self.assertIn("admin-support-table", text)
        # Must not suggest inline handlers
        self.assertNotIn("onclick=", text)
        self.assertNotIn("onchange=", text)

    def test_app_routes_mention_support_tickets(self) -> None:
        src = (ROOT / "status_page" / "app.py").read_text(encoding="utf-8")
        self.assertIn("/admin/support-tickets", src)
        self.assertIn("render_admin_support_tickets_page_html", src)
        self.assertIn("close_support_ticket", src)
        self.assertIn("/admin/support-tickets/close", src)
        self.assertIn("clear_all_support_tickets", src)
        self.assertIn("/admin/support-tickets/clear", src)
        # CSP-safe static must be in the serve map (not only on disk)
        self.assertIn("/static/admin_support_tickets.js", src)
        from app import STATIC_ROUTES, static_file_path

        self.assertEqual(
            STATIC_ROUTES.get("/static/admin_support_tickets.js"),
            "admin_support_tickets.js",
        )
        resolved = static_file_path("/static/admin_support_tickets.js")
        self.assertIsNotNone(resolved)
        assert resolved is not None
        self.assertTrue(resolved.is_file())


class TestClearAllSupportTickets(unittest.TestCase):
    def test_clear_requires_confirm_and_wipes_store(self) -> None:
        from support_tickets import (
            CLEAR_ALL_SUPPORT_TICKETS_CONFIRM,
            clear_all_support_tickets,
            count_support_tickets,
            create_support_ticket,
            get_support_ticket,
            list_support_tickets,
        )

        with tempfile.TemporaryDirectory() as td:
            db = Path(td) / "support_tickets.sqlite"
            a = create_support_ticket(
                email="a@example.com",
                subject="First ticket subject",
                message="First ticket body text long enough.",
                platform="macos",
                app_version="0.5.9",
                path=db,
                send_mail=False,
            )
            b = create_support_ticket(
                email="b@example.com",
                subject="Second ticket subject",
                message="Second ticket body text long enough.",
                platform="linux",
                app_version="0.5.9",
                path=db,
                send_mail=False,
            )
            self.assertTrue(a["ok"])
            self.assertTrue(b["ok"])
            self.assertEqual(a["ticket_id"], "RPS-001")
            self.assertEqual(b["ticket_id"], "RPS-002")
            self.assertEqual(count_support_tickets(path=db), 2)
            self.assertEqual(len(list_support_tickets(path=db)), 2)

            # Wrong / missing confirm must not wipe
            with self.assertRaises(ValueError):
                clear_all_support_tickets(confirm="", path=db)
            with self.assertRaises(ValueError):
                clear_all_support_tickets(confirm="yes", path=db)
            with self.assertRaises(ValueError):
                clear_all_support_tickets(confirm="CLEAR_ALL_LICENCES", path=db)
            self.assertEqual(count_support_tickets(path=db), 2)
            self.assertIsNotNone(get_support_ticket("RPS-001", path=db))

            cleared = clear_all_support_tickets(
                confirm=CLEAR_ALL_SUPPORT_TICKETS_CONFIRM, path=db
            )
            self.assertTrue(cleared["ok"])
            self.assertEqual(cleared["deleted"], 2)
            self.assertEqual(cleared["remaining"], 0)
            self.assertEqual(count_support_tickets(path=db), 0)
            self.assertEqual(list_support_tickets(path=db), [])
            self.assertIsNone(get_support_ticket("RPS-001", path=db))
            self.assertIsNone(get_support_ticket("RPS-002", path=db))

            # After clear, ids restart at RPS-001 (new parameters path)
            again = create_support_ticket(
                email="fresh@example.com",
                subject="After clear subject",
                message="After clear message body text.",
                platform="android",
                app_version="0.5.9",
                path=db,
                send_mail=False,
            )
            self.assertTrue(again["ok"])
            self.assertEqual(again["ticket_id"], "RPS-001")
            self.assertEqual(again["record"].get("keygen") or "", "")

    def test_admin_page_has_clear_form_and_new_params_after_clear(self) -> None:
        from admin_panel import render_admin_support_tickets_page_html
        from support_tickets import (
            ADMIN_SUPPORT_CLEAR_PATH,
            CLEAR_ALL_SUPPORT_TICKETS_CONFIRM,
            TICKET_STATUS_CLOSED,
            clear_all_support_tickets,
            close_support_ticket,
            create_support_ticket,
            list_support_tickets,
            render_support_page_html,
        )

        # Public form: current params, no keygen field
        public = render_support_page_html()
        self.assertIn('name="email"', public)
        self.assertIn('name="subject"', public)
        self.assertIn('name="message"', public)
        self.assertIn('name="platform"', public)
        self.assertIn('name="app_version"', public)
        self.assertNotIn('name="keygen"', public)
        self.assertNotIn("support-keygen", public)

        with tempfile.TemporaryDirectory() as td:
            db = Path(td) / "support_tickets.sqlite"
            create_support_ticket(
                email="old@example.com",
                subject="Stale ticket subject",
                message="Stale ticket message body here.",
                path=db,
                send_mail=False,
            )
            clear_all_support_tickets(
                confirm=CLEAR_ALL_SUPPORT_TICKETS_CONFIRM, path=db
            )
            created = create_support_ticket(
                email="user@example.com",
                subject="Cannot connect after unlock",
                message="Tunnel stays Connecting after unlock on macOS.",
                platform="macos",
                app_version="0.5.9",
                path=db,
                send_mail=False,
            )
            self.assertEqual(created["ticket_id"], "RPS-001")
            self.assertEqual(created["record"].get("keygen") or "", "")

            page = render_admin_support_tickets_page_html(
                tickets=list_support_tickets(path=db)
            ).decode("utf-8")
            self.assertIn('id="admin-clear-support-tickets-form"', page)
            self.assertIn(f'action="{ADMIN_SUPPORT_CLEAR_PATH}"', page)
            self.assertIn(CLEAR_ALL_SUPPORT_TICKETS_CONFIRM, page)
            self.assertIn('id="admin-clear-support-tickets-submit"', page)
            self.assertIn('name="confirm"', page)
            # No inline onsubmit (CSP)
            self.assertNotIn("onsubmit=", page.lower())
            self.assertEqual(_field_cell_text(page, "ticket_id"), "RPS-001")
            self.assertEqual(_field_cell_text(page, "email"), "user@example.com")
            self.assertEqual(
                _field_cell_text(page, "subject"), "Cannot connect after unlock"
            )
            self.assertIn(
                "Tunnel stays Connecting", _field_cell_text(page, "message")
            )
            self.assertEqual(_field_cell_text(page, "platform"), "macos")
            self.assertEqual(_field_cell_text(page, "app_version"), "0.5.9")
            self.assertNotIn(">Keygen<", page)
            self.assertNotIn("RPT-KEY-", page)

            closed = close_support_ticket(
                "RPS-001", path=db, send_mail=False
            )
            self.assertTrue(closed["ok"])
            self.assertEqual(closed["ticket"]["status"], TICKET_STATUS_CLOSED)
            page2 = render_admin_support_tickets_page_html(
                tickets=list_support_tickets(path=db)
            ).decode("utf-8")
            self.assertEqual(_field_cell_text(page2, "status").lower(), "closed")
            self.assertIn("ticket-toggle-closed", page2)


if __name__ == "__main__":
    unittest.main()
