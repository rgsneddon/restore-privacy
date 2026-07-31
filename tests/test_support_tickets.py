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

        tid = new_ticket_id(seq=1)
        self.assertEqual(tid, "RPS-001")
        self.assertRegex(tid, r"^RPS-\d{3}$")
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
        self.assertNotIn("Keygen:", mail["body"])
        self.assertEqual(mail["reply_to"], "user@example.com")
        self.assertEqual(fields.get("keygen"), "")

        sent = []

        def transport(payload):
            sent.append(payload)
            return {"ok": True, "error": None}

        with tempfile.TemporaryDirectory() as td:
            db = Path(td) / "support_tickets.sqlite"
            result = create_support_ticket(
                email="user@example.com",
                subject="Cannot connect",
                message="Tunnel stays Connecting after unlock.",
                platform="macos",
                app_version="0.5.8",
                path=db,
                transport=transport,
                send_mail=True,
            )
            self.assertTrue(result["ok"])
            self.assertEqual(result["ticket_id"], "RPS-001")
            second = create_support_ticket(
                email="two@example.com",
                subject="Second issue here",
                message="Need help with a second distinct issue.",
                path=db,
                send_mail=False,
            )
            self.assertEqual(second["ticket_id"], "RPS-002")
        self.assertEqual(len(sent), 1)
        self.assertEqual(sent[0]["to"], "rus@restoreprivacy.online")
        self.assertIn("RPS-001", sent[0]["subject"])

    def test_render_page_has_form_and_action(self):
        from support_tickets import SUPPORT_PATH, render_support_page_html

        page = render_support_page_html()
        self.assertIn('action="/support"', page)
        self.assertIn('id="support-form"', page)
        self.assertIn("support-email", page)
        self.assertIn(SUPPORT_PATH, page)
        # Keygen field removed from public form
        self.assertNotIn('name="keygen"', page)
        self.assertNotIn("support-keygen", page)
        self.assertIn("RPS-001", page)

    def test_nav_includes_support(self):
        from public_chrome import public_nav_links_html

        nav = public_nav_links_html(active="support")
        self.assertIn('href="/support"', nav)
        self.assertIn("SUPPORT", nav)
        self.assertIn("support-link", nav)


class TestRoDeprecationCatalog(unittest.TestCase):
    def test_catalog_peers_is_de_only(self):
        from client.multihop import (
            PRODUCT_COUNTRY_CATALOG,
            normalize_entry_country,
            product_country_catalog,
        )

        codes = {n.code for n in product_country_catalog()}
        self.assertEqual(codes, {"IS", "DE"})
        self.assertNotIn("RO", codes)
        self.assertNotIn("US", codes)
        for n in PRODUCT_COUNTRY_CATALOG:
            self.assertNotEqual(n.host, "185.146.232.107")
        self.assertEqual(normalize_entry_country("RO"), "DE")
        self.assertEqual(normalize_entry_country("Romania"), "DE")
        self.assertEqual(normalize_entry_country("US"), "DE")
        self.assertEqual(normalize_entry_country("DE"), "DE")

    def test_flag_catalog_live_codes(self):
        from client.flag_images import CATALOG_FLAG_CODES

        self.assertEqual(set(CATALOG_FLAG_CODES), {"IS", "DE"})
        self.assertNotIn("RO", CATALOG_FLAG_CODES)
        self.assertNotIn("US", CATALOG_FLAG_CODES)

    def test_private_capacity_no_live_ro(self):
        from node.private_capacity import (
            PRODUCT_SESSION_SOFT_MAX,
            PRODUCT_UNLIMITED_BANDWIDTH_CODES,
            PRODUCT_UNLIMITED_BANDWIDTH_HOSTS,
            resolve_peer_identity,
        )

        self.assertNotIn("RO", PRODUCT_UNLIMITED_BANDWIDTH_CODES)
        self.assertNotIn("185.146.232.107", PRODUCT_UNLIMITED_BANDWIDTH_HOSTS)
        self.assertNotIn("RO", PRODUCT_SESSION_SOFT_MAX)
        self.assertNotIn("185.146.232.107", PRODUCT_SESSION_SOFT_MAX)
        code, host = resolve_peer_identity(code="RO", host="")
        self.assertEqual(code, "DE")
        code2, host2 = resolve_peer_identity(code="", host="185.146.232.107")
        self.assertEqual(code2, "DE")
        self.assertEqual(host2, "178.105.187.178")

    def test_audit_md_monopin_current(self):
        from pathlib import Path

        root = Path(__file__).resolve().parents[1]
        for rel in ("AUDIT.md", "status_page/public/AUDIT.md"):
            path = root / rel
            if not path.is_file():
                continue
            text = path.read_text(encoding="utf-8")
            self.assertIn("**0.5.9**", text)
            self.assertIn("restore-privacy-client-0.5.9-", text)
            # Current-catalog pin must not still claim older monopin
            self.assertNotIn("**Public catalog version** | **0.5.7**", text)
            self.assertNotIn("**Public catalog version** | **0.5.8**", text)
            self.assertNotIn("catalog v0.5.7", text)
            self.assertNotIn("Code baseline | Catalog **0.5.7**", text)


if __name__ == "__main__":
    unittest.main()
