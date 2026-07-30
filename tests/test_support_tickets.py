"""Customer support portal: tickets, email builder, nav, RO-free catalog peers."""

from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "status_page"))


class TestSupportTicketPure(unittest.TestCase):
    def test_validate_and_build_email_to_rus(self):
        from support_tickets import (
            SUPPORT_INBOX,
            build_support_email,
            create_support_ticket,
            new_ticket_id,
            validate_support_form,
        )

        self.assertEqual(SUPPORT_INBOX, "rus@restoreprivacy.online")
        ok, err, fields = validate_support_form(
            email="user@example.com",
            subject="Cannot connect",
            message="Tunnel stays Connecting after keygen.",
            platform="macos",
            app_version="0.5.8",
        )
        self.assertTrue(ok, err)
        self.assertEqual(fields["email"], "user@example.com")

        bad, _, _ = validate_support_form(
            email="not-an-email", subject="x", message="too short"
        )
        self.assertFalse(bad)

        tid = new_ticket_id(now=1_700_000_000)
        self.assertTrue(tid.startswith("RPT-SUP-"))
        mail = build_support_email(
            ticket_id=tid,
            email=fields["email"],
            subject=fields["subject"],
            message=fields["message"],
            platform="macos",
            app_version="0.5.8",
            created_at=1_700_000_000,
        )
        self.assertEqual(mail["to"], "rus@restoreprivacy.online")
        self.assertIn(tid, mail["subject"])
        self.assertIn("Cannot connect", mail["subject"])
        self.assertIn(fields["message"], mail["body"])
        self.assertEqual(mail["reply_to"], "user@example.com")

        sent = []

        def transport(payload):
            sent.append(payload)
            return {"ok": True, "error": None}

        with tempfile.TemporaryDirectory() as td:
            db = Path(td) / "support_tickets.sqlite"
            result = create_support_ticket(
                email="user@example.com",
                subject="Cannot connect",
                message="Tunnel stays Connecting after keygen.",
                platform="macos",
                app_version="0.5.8",
                path=db,
                transport=transport,
                send_mail=True,
            )
        self.assertTrue(result["ok"])
        self.assertTrue(result["ticket_id"].startswith("RPT-SUP-"))
        self.assertEqual(len(sent), 1)
        self.assertEqual(sent[0]["to"], "rus@restoreprivacy.online")
        self.assertIn(result["ticket_id"], sent[0]["subject"])

    def test_render_page_has_form_and_action(self):
        from support_tickets import SUPPORT_PATH, render_support_page_html

        page = render_support_page_html()
        self.assertIn('action="/support"', page)
        self.assertIn('id="support-form"', page)
        self.assertIn("support-email", page)
        self.assertIn(SUPPORT_PATH, page)

    def test_nav_includes_support(self):
        from public_chrome import public_nav_links_html

        nav = public_nav_links_html(active="support")
        self.assertIn('href="/support"', nav)
        self.assertIn("SUPPORT", nav)
        self.assertIn("support-link", nav)


class TestRoDeprecationCatalog(unittest.TestCase):
    def test_catalog_peers_is_de_us_only(self):
        from client.multihop import (
            PRODUCT_COUNTRY_CATALOG,
            normalize_entry_country,
            product_country_catalog,
        )

        codes = {n.code for n in product_country_catalog()}
        self.assertEqual(codes, {"IS", "DE", "US"})
        self.assertNotIn("RO", codes)
        for n in PRODUCT_COUNTRY_CATALOG:
            self.assertNotEqual(n.host, "185.146.232.107")
        self.assertEqual(normalize_entry_country("RO"), "DE")
        self.assertEqual(normalize_entry_country("Romania"), "DE")
        self.assertEqual(normalize_entry_country("DE"), "DE")

    def test_flag_catalog_live_codes(self):
        from client.flag_images import CATALOG_FLAG_CODES

        self.assertEqual(set(CATALOG_FLAG_CODES), {"IS", "DE", "US"})
        self.assertNotIn("RO", CATALOG_FLAG_CODES)


if __name__ == "__main__":
    unittest.main()
