"""Customer support portal: tickets, email builder, nav, RO-free catalog peers."""

from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "status_page"))


class TestSupportSmtpPath(unittest.TestCase):
    """Support mail reuses fulfilment SMTP config (Render RPT_FULFILMENT_SMTP_*)."""

    def test_from_address_coerced_to_smtp_auth_user(self) -> None:
        """PrivateEmail 553: From noreply@ while auth is rus@ must not be used."""
        from payments import smtp_from_address_for_auth, _bare_email_address

        # Mismatch → use authenticated user
        coerced = smtp_from_address_for_auth(
            {
                "user": "rus@restoreprivacy.online",
                "from_addr": "noreply@restoreprivacy.online",
            }
        )
        self.assertEqual(
            _bare_email_address(coerced).lower(),
            "rus@restoreprivacy.online",
        )
        # Match → keep configured from
        same = smtp_from_address_for_auth(
            {
                "user": "rus@restoreprivacy.online",
                "from_addr": "rus@restoreprivacy.online",
            }
        )
        self.assertEqual(
            _bare_email_address(same).lower(),
            "rus@restoreprivacy.online",
        )
        # Display name preserved when swapping address
        named = smtp_from_address_for_auth(
            {
                "user": "rus@restoreprivacy.online",
                "from_addr": "Restore Privacy <noreply@restoreprivacy.online>",
            }
        )
        self.assertIn("rus@restoreprivacy.online", named)
        self.assertIn("Restore Privacy", named)

        # send_support_ticket_email real SMTP path uses coerced From (capture via mock)
        from support_tickets import build_support_email, send_support_ticket_email
        from unittest import mock
        from email.message import EmailMessage

        open_mail = build_support_email(
            ticket_id="RPS-553",
            email="customer@example.com",
            subject="From ownership",
            message="Ensure From is the SMTP mailbox owner.",
        )
        captured: dict = {}

        class _FakeSMTP:
            def __init__(self, *a, **k):
                pass

            def __enter__(self):
                return self

            def __exit__(self, *a):
                return False

            def ehlo(self):
                return None

            def starttls(self):
                return None

            def login(self, user, password):
                captured["login_user"] = user
                return None

            def send_message(self, msg: EmailMessage):
                captured["from"] = str(msg["From"])
                captured["to"] = str(msg["To"])
                return {}

        with mock.patch("smtplib.SMTP", _FakeSMTP):
            result = send_support_ticket_email(
                open_mail,
                smtp_config={
                    "host": "mail.privateemail.com",
                    "port": 587,
                    "user": "rus@restoreprivacy.online",
                    "password": "x",
                    "from_addr": "noreply@restoreprivacy.online",
                    "use_tls": True,
                    "configured": True,
                },
            )
        self.assertTrue(result.get("ok"), result)
        self.assertIn("rus@restoreprivacy.online", (captured.get("from") or "").lower())
        self.assertNotIn("noreply@", (captured.get("from") or "").lower())
        self.assertEqual(
            (result.get("from") or "").lower(),
            "rus@restoreprivacy.online",
        )

    def test_send_path_payload_and_config_keys(self) -> None:
        from payments import FULFILMENT_SMTP_ENV_KEYS, fulfilment_smtp_env_keys
        from support_tickets import (
            SUPPORT_INBOX,
            assess_support_smtp_readiness,
            build_support_email,
            build_ticket_closed_email,
            create_support_ticket,
            send_support_ticket_email,
            support_smtp_config,
            support_smtp_env_keys,
        )

        # Same env keys as fulfilment (no second secret store)
        self.assertEqual(support_smtp_env_keys(), fulfilment_smtp_env_keys())
        self.assertEqual(set(support_smtp_env_keys()), set(FULFILMENT_SMTP_ENV_KEYS))

        cfg = support_smtp_config()
        self.assertIn("host", cfg)
        self.assertIn("env_keys", cfg)
        self.assertEqual(cfg.get("purpose"), "support_tickets")
        for k in FULFILMENT_SMTP_ENV_KEYS:
            self.assertIn(k, cfg["env_keys"])

        ready = assess_support_smtp_readiness()
        self.assertTrue(ready.get("uses_fulfilment_smtp"))
        self.assertIn("status", ready)
        self.assertIn("email_flow_enabled", ready)

        from support_tickets import build_support_requester_confirmation_email

        open_mail = build_support_email(
            ticket_id="RPS-001",
            email="user@example.com",
            subject="Cannot connect",
            message="Tunnel stays Connecting after keygen unlock path.",
            platform="macos",
            app_version="1.0.0",
        )
        self.assertEqual(open_mail["to"], SUPPORT_INBOX)
        self.assertEqual(open_mail["reply_to"], "user@example.com")
        self.assertIn("RPS-001", open_mail["subject"])

        confirm = build_support_requester_confirmation_email(
            ticket_id="RPS-001",
            email="user@example.com",
            subject="Cannot connect",
            message="Tunnel stays Connecting after keygen unlock path.",
            platform="macos",
            app_version="1.0.0",
        )
        self.assertEqual(confirm["to"], "user@example.com")
        self.assertEqual(confirm["reply_to"], SUPPORT_INBOX)
        self.assertIn("RPS-001", confirm["subject"])
        self.assertIn("Tunnel stays Connecting", confirm["body"])
        self.assertIn("We received your", confirm["body"])

        captured: list[dict] = []

        def transport(payload: dict) -> dict:
            captured.append(dict(payload))
            return {"ok": True, "error": None}

        sent = send_support_ticket_email(open_mail, transport=transport)
        self.assertTrue(sent["ok"])
        self.assertEqual(captured[0]["to"], SUPPORT_INBOX)
        self.assertEqual(captured[0]["reply_to"], "user@example.com")
        self.assertIn("RPS-001", captured[0]["subject"])

        close_mail = build_ticket_closed_email(
            ticket_id="RPS-001",
            email="user@example.com",
            subject="Cannot connect",
        )
        self.assertEqual(close_mail["to"], "user@example.com")
        self.assertEqual(close_mail["reply_to"], SUPPORT_INBOX)
        closed_send = send_support_ticket_email(close_mail, transport=transport)
        self.assertTrue(closed_send["ok"])
        self.assertEqual(captured[1]["to"], "user@example.com")

        # Real config reader path when host empty → smtp_not_configured
        empty = send_support_ticket_email(
            open_mail,
            smtp_config={
                "host": "",
                "port": 587,
                "user": "",
                "password": "",
                "from_addr": "noreply@restoreprivacy.online",
                "use_tls": True,
            },
        )
        self.assertFalse(empty["ok"])
        self.assertEqual(empty.get("error"), "smtp_not_configured")

    def test_ticket_persists_when_smtp_fails(self) -> None:
        from support_tickets import create_support_ticket, get_support_ticket

        def boom(_payload: dict) -> dict:
            return {"ok": False, "error": "SMTPAuthenticationError:test"}

        with tempfile.TemporaryDirectory() as td:
            db = Path(td) / "support_tickets.sqlite"
            result = create_support_ticket(
                email="user@example.com",
                subject="Cannot connect after unlock",
                message="Tunnel stays Connecting after unlock on macOS.",
                path=db,
                transport=boom,
                send_mail=True,
            )
            self.assertTrue(result["ok"], result)
            tid = result["ticket_id"]
            self.assertTrue(tid.startswith("RPS-"))
            self.assertFalse(result.get("mail_sent"))
            rec = get_support_ticket(tid, path=db)
            assert rec is not None
            self.assertEqual(rec["mail_status"], "failed")
            self.assertIn("SMTPAuthenticationError", rec["mail_detail"])
            # Ticket fields intact
            self.assertEqual(rec["email"], "user@example.com")
            self.assertIn("Connecting", rec["message"])

    def test_ticket_mail_sent_status_when_transport_ok(self) -> None:
        from support_tickets import create_support_ticket, get_support_ticket

        captured: list[dict] = []

        def transport(payload: dict) -> dict:
            captured.append(dict(payload))
            return {"ok": True, "error": None}

        with tempfile.TemporaryDirectory() as td:
            db = Path(td) / "support_tickets.sqlite"
            result = create_support_ticket(
                email="ok@example.com",
                subject="Works when mail works",
                message="Just confirming support path sends when SMTP is ok.",
                path=db,
                transport=transport,
            )
            self.assertTrue(result["ok"])
            self.assertTrue(result.get("mail_sent"))
            self.assertTrue(result.get("customer_mail_sent"))
            rec = get_support_ticket(result["ticket_id"], path=db)
            assert rec is not None
            self.assertEqual(rec["mail_status"], "sent")
            self.assertIn("staff=ok", rec["mail_detail"])
            self.assertIn("customer=ok", rec["mail_detail"])
            # Staff notify + requester confirmation
            self.assertEqual(len(captured), 2)
            tos = {c["to"] for c in captured}
            self.assertEqual(tos, {"rus@restoreprivacy.online", "ok@example.com"})
            staff = next(c for c in captured if c["to"] == "rus@restoreprivacy.online")
            cust = next(c for c in captured if c["to"] == "ok@example.com")
            self.assertEqual(staff["reply_to"], "ok@example.com")
            self.assertIn("RPT Support", staff["subject"])
            self.assertIn("received your ticket", cust["subject"].lower())
            self.assertIn("Just confirming support path", cust["body_text"])

    def test_customer_confirm_fail_still_staff_sent(self) -> None:
        """Staff notify can succeed while customer copy fails (partial mail_detail)."""
        from support_tickets import create_support_ticket, get_support_ticket

        def transport(payload: dict) -> dict:
            if payload.get("to") == "user@example.com":
                return {"ok": False, "error": "SMTPRecipientsRefused:test"}
            return {"ok": True, "error": None}

        with tempfile.TemporaryDirectory() as td:
            db = Path(td) / "support_tickets.sqlite"
            result = create_support_ticket(
                email="user@example.com",
                subject="Partial mail path",
                message="Staff should get this even if my copy fails SMTP.",
                path=db,
                transport=transport,
            )
            self.assertTrue(result["ok"])
            self.assertTrue(result.get("mail_sent"))  # staff ok
            self.assertFalse(result.get("customer_mail_sent"))
            rec = get_support_ticket(result["ticket_id"], path=db)
            assert rec is not None
            self.assertEqual(rec["mail_status"], "partial")
            self.assertIn("staff=ok", rec["mail_detail"])
            self.assertIn("customer=", rec["mail_detail"])


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
        # Staff notify + requester confirmation
        self.assertEqual(len(sent), 2)
        self.assertEqual(sent[0]["to"], "rus@restoreprivacy.online")
        self.assertIn("RPS-001", sent[0]["subject"])
        self.assertEqual(sent[1]["to"], "user@example.com")
        self.assertIn("RPS-001", sent[1]["subject"])

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
        self.assertIn("confirmation email", page.lower())

        ok_page = render_support_page_html(
            success_ticket_id="RPS-042",
            mail_sent=True,
            customer_mail_sent=True,
        )
        self.assertIn("RPS-042", ok_page)
        self.assertIn("confirmation", ok_page.lower())
        fail_page = render_support_page_html(
            success_ticket_id="RPS-043",
            mail_sent=False,
        )
        self.assertIn("could not send email", fail_page.lower())
        partial = render_support_page_html(
            success_ticket_id="RPS-044",
            mail_sent=True,
            customer_mail_sent=False,
        )
        self.assertIn("confirmation copy", partial.lower())

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
