"""Fulfilment email: absolute download link + 1-hour advice + RASKUL/rus@ support.

Drives shipped payments builders and webhook post-pay send branch.
"""

from __future__ import annotations

import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "status_page"))

import payments as pay  # noqa: E402


class TestFulfilmentEmailDownloadLink(unittest.TestCase):
    def test_builder_includes_url_ttl_advice_and_support(self):
        url = "https://restoreprivacy.online/download?token=abcTOKEN"
        payload = pay.build_fulfilment_email_payload(
            to_email="buyer@example.com",
            keygen="RPT-KEY-AAAA-BBBB-CCCC",
            purchase_id="RPT-1111-2222-3333",
            download_url=url,
            platform="windows",
            session_id="cs_mail_1",
            filename="restore-privacy-client-0.5.7-windows-x64-setup.exe",
        )
        body = payload["body"]
        self.assertEqual(payload["to"], "buyer@example.com")
        self.assertIn(url, body)
        self.assertTrue(payload["has_download_url"])
        self.assertIn(pay.DOWNLOAD_LINK_VALIDITY_ADVICE, body)
        self.assertIn("1 hour", body)
        self.assertIn("connection drops", body.lower())
        self.assertIn(pay.FULFILMENT_SUPPORT_FOOTER, body)
        self.assertIn(pay.SUPPORT_EMAIL, body)
        self.assertIn("rus@restoreprivacy.online", body)
        self.assertIn(pay.PUBLIC_BUSINESS_NAME, body)
        self.assertIn("RASKUL", body)
        self.assertIn(pay.KEYGEN_UNLOCK_INSTRUCTION, body)
        # Stripe receipt note (PDF vs status-host fulfilment)
        self.assertIn("receipt", body.lower())
        self.assertIn("invoice", body.lower())
        self.assertIn("this** email", body)

    def test_relative_download_path_becomes_absolute(self):
        payload = pay.build_fulfilment_email_payload(
            to_email="b@e.com",
            keygen="RPT-KEY-AAAA-BBBB-CCCC",
            purchase_id="RPT-AAAA-BBBB-CCCC",
            download_url="/download?token=relTok99",
        )
        self.assertIn("https://", payload["download_url"])
        self.assertIn("token=relTok99", payload["download_url"])
        self.assertIn(payload["download_url"], payload["body"])

    def test_absolute_download_url_helper(self):
        u = pay.absolute_download_url(
            "tok_x", base_url="https://restoreprivacy.online"
        )
        self.assertEqual(
            u, "https://restoreprivacy.online/download?token=tok_x"
        )
        # Loopback base falls back to production public origin
        u2 = pay.absolute_download_url("tok_y", base_url="http://127.0.0.1:10000")
        self.assertTrue(u2.startswith("https://restoreprivacy.online/"))
        self.assertIn("tok_y", u2)

    def test_fulfil_checkout_invokes_transport_with_download(self):
        with tempfile.TemporaryDirectory() as td:
            os.environ["RPT_PAYMENT_DATA_DIR"] = td
            pay.init_db()
            captured: list[dict] = []

            def transport(payload: dict) -> dict:
                captured.append(payload)
                return {"ok": True, "sent": True}

            out = pay.fulfil_checkout_with_email(
                token="grantTok99",
                session_id="cs_fulfil_mail",
                platform="linux",
                filename="restore-privacy-client-0.5.7-linux-x64.tar.gz",
                customer_email="paid@example.com",
                keygen="RPT-KEY-FFFF-EEEE-DDDD",
                purchase_id="RPT-FFFF-EEEE-DDDD",
                base_url="https://restoreprivacy.online",
                transport=transport,
            )
            self.assertTrue(out["send"].get("sent"))
            self.assertIn("grantTok99", out["download_url"])
            self.assertEqual(len(captured), 1)
            body = captured[0]["body"]
            self.assertIn("grantTok99", body)
            self.assertIn(pay.DOWNLOAD_LINK_VALIDITY_ADVICE, body)
            self.assertIn(pay.SUPPORT_EMAIL, body)
            del os.environ["RPT_PAYMENT_DATA_DIR"]

    def test_no_customer_email_skips_send_explicitly(self):
        """Webhook path: no email → no transport call (explicit skip log path)."""
        with tempfile.TemporaryDirectory() as td:
            os.environ["RPT_PAYMENT_DATA_DIR"] = td
            pay.init_db()
            transport = mock.Mock(return_value={"ok": True, "sent": True})
            # Direct fulfil with empty email still builds but send fails missing_to
            out = pay.fulfil_checkout_with_email(
                token="t1",
                session_id="cs_no_em",
                platform="windows",
                filename="x.exe",
                customer_email="",
                keygen="RPT-KEY-AAAA-BBBB-CCCC",
                base_url="https://restoreprivacy.online",
                transport=transport,
            )
            self.assertFalse(out["send"].get("sent"))
            self.assertEqual(out["send"].get("error"), "missing_to_email")
            transport.assert_not_called()
            del os.environ["RPT_PAYMENT_DATA_DIR"]

    def test_webhook_completed_sends_when_email_present(self):
        with tempfile.TemporaryDirectory() as td:
            os.environ["RPT_PAYMENT_DATA_DIR"] = td
            pay.init_db()
            captured: list[dict] = []

            def transport(payload: dict) -> dict:
                captured.append(payload)
                return {"ok": True, "sent": True}

            event = {
                "type": "checkout.session.completed",
                "data": {
                    "object": {
                        "id": "cs_webhook_mail_1",
                        "payment_status": "paid",
                        "amount_total": pay.PRICE_PENCE,
                        "currency": "gbp",
                        "customer_email": "webhook@example.com",
                        "client_reference_id": "windows",
                        "metadata": {
                            "platform": "windows",
                            "amount_pence": str(pay.PRICE_PENCE),
                            "currency": "gbp",
                        },
                    }
                },
            }
            tok = pay.process_checkout_completed_event(
                event, email_transport=transport
            )
            self.assertTrue(tok)
            self.assertEqual(len(captured), 1)
            body = captured[0]["body"]
            self.assertIn(tok, body)
            self.assertIn("/download?token=", body)
            self.assertIn(pay.DOWNLOAD_LINK_VALIDITY_ADVICE, body)
            self.assertIn("1 hour", body)
            self.assertIn(pay.SUPPORT_EMAIL, body)
            del os.environ["RPT_PAYMENT_DATA_DIR"]

    def test_stripe_public_business_guide_raskul_and_rus(self):
        g = pay.stripe_public_business_guide()
        self.assertEqual(g["public_business_name"], "RASKUL")
        self.assertEqual(g["support_email"], "rus@restoreprivacy.online")
        self.assertIn("RASKUL", g["what_customers_see"])
        self.assertIn("rus@restoreprivacy.online", g["what_customers_see"])
        steps = " ".join(g["dashboard"]["steps"])
        self.assertIn("RASKUL", steps)
        self.assertIn("rus@restoreprivacy.online", steps)
        self.assertIn("download?token", steps)
        # Account API helper with no key
        r = pay.update_stripe_account_public_profile(secret_key="")
        self.assertFalse(r["ok"])
        self.assertIn("not configured", r["error"].lower())

    def test_update_account_profile_posts_fields(self):
        posts: list[tuple] = []

        def fake_post(url, headers, body):
            posts.append((url, body.decode()))
            return 200, b'{"business_profile":{"name":"RASKUL","support_email":"rus@restoreprivacy.online"}}'

        r = pay.update_stripe_account_public_profile(
            secret_key="sk_test_dummy", http_post=fake_post
        )
        self.assertTrue(r["ok"])
        self.assertTrue(r["applied"])
        self.assertEqual(r["observed_name"], "RASKUL")
        body = posts[0][1]
        # urlencode may percent-encode brackets
        self.assertIn("RASKUL", body)
        self.assertIn("rus%40restoreprivacy.online", body)
        self.assertTrue(
            "business_profile[name]" in body
            or "business_profile%5Bname%5D" in body
        )


if __name__ == "__main__":
    unittest.main()
