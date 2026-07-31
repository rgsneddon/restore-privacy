"""Admin support tickets: nav, table fields, one-way close, close email."""

from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "status_page"))


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
        )

        with tempfile.TemporaryDirectory() as td:
            db = Path(td) / "support_tickets.sqlite"
            sent: list[dict] = []

            def transport(payload: dict) -> dict:
                sent.append(dict(payload))
                return {"ok": True, "error": None}

            created = create_support_ticket(
                email="user@example.com",
                subject="Cannot connect after keygen",
                message="Tunnel stays Connecting after unlock on macOS.",
                platform="macos",
                app_version="0.5.8",
                keygen="RPT-KEY-TEST",
                path=db,
                send_mail=False,
            )
            self.assertTrue(created["ok"])
            tid = created["ticket_id"]
            rec = get_support_ticket(tid, path=db)
            assert rec is not None
            self.assertEqual(rec["status"], TICKET_STATUS_OPEN)

            listed = list_support_tickets(path=db)
            self.assertEqual(len(listed), 1)
            self.assertEqual(listed[0]["ticket_id"], tid)

            page = render_admin_support_tickets_page_html(
                tickets=list_support_tickets(path=db)
            ).decode("utf-8")
            self.assertIn("admin-support-table", page)
            self.assertIn(tid, page)
            self.assertIn("user@example.com", page)
            self.assertIn("Cannot connect after keygen", page)
            self.assertIn("Tunnel stays Connecting", page)
            self.assertIn("macos", page)
            self.assertIn("0.5.8", page)
            self.assertIn("RPT-KEY-TEST", page)
            self.assertIn("admin-nav-support-tickets", page)
            self.assertIn("/admin/support-tickets/close", page)
            self.assertIn(f'ticket-close-{tid}', page)
            self.assertIn("open", page.lower())

            # Pure close-email builder
            mail = build_ticket_closed_email(
                ticket_id=tid,
                email="user@example.com",
                subject="Cannot connect after keygen",
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
            self.assertIn("ticket-status-locked", page2)
            self.assertNotIn(f'ticket-close-{tid}"', page2)

    def test_app_routes_mention_support_tickets(self) -> None:
        src = (ROOT / "status_page" / "app.py").read_text(encoding="utf-8")
        self.assertIn("/admin/support-tickets", src)
        self.assertIn("render_admin_support_tickets_page_html", src)
        self.assertIn("close_support_ticket", src)
        self.assertIn("/admin/support-tickets/close", src)


if __name__ == "__main__":
    unittest.main()
