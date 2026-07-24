"""Keygen subscription unlock: homepage copy, mint, email, revoke, client gate.

Drives shipped status_page.payments + client.payment_entitlement / licence_gate
paths — not re-implemented oracles.
"""

from __future__ import annotations

import json
import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "status_page"))


class TestHomepageTrialSentence(unittest.TestCase):
    def test_price_block_order(self):
        from downloads import (
            ONLY_PRICE_BANNER,
            PACKAGE_IDENTITY,
            PAY_AND_KEYGEN_CLAUSE,
            PRICE_LABEL,
            TRIAL_SUBSCRIPTION_SENTENCE,
            download_css,
            render_download_section_html,
        )

        html = render_download_section_html(coming_soon=False)
        # Nested box inside #downloads
        self.assertIn('id="downloads"', html)
        # Large white bold monthly callout under Download client heading
        self.assertIn("Download client v", html)
        self.assertIn('id="dl-only-price"', html)
        self.assertIn('class="dl-only-price"', html)
        self.assertIn(ONLY_PRICE_BANNER, html)
        self.assertIn("ONLY £2.45 per month", ONLY_PRICE_BANNER)
        self.assertTrue(
            "yearly" in ONLY_PRICE_BANNER.lower()
            or "annual" in ONLY_PRICE_BANNER.lower()
        )
        heading_i = html.find("Download client v")
        banner_i = html.find('id="dl-only-price"')
        box_start = html.find('id="dl-price-box"')
        self.assertGreater(banner_i, heading_i)
        self.assertGreater(box_start, banner_i)
        self.assertIn('class="dl-price-box"', html)
        self.assertIn('id="dl-price-box"', html)
        price_start = html.find('id="dl-price"', box_start)
        self.assertGreater(price_start, box_start)
        # Extract the price paragraph content from the real renderer
        p_open = html.find(">", price_start) + 1
        p_close = html.find("</p>", p_open)
        snippet = html[p_open:p_close]
        sub_sentence = TRIAL_SUBSCRIPTION_SENTENCE
        package = PACKAGE_IDENTITY
        self.assertIn(f"{PRICE_LABEL} GBP", snippet)
        self.assertIn(package, snippet)
        self.assertIn("one device licence", snippet)
        self.assertIn(sub_sentence, snippet)
        self.assertTrue(
            "Monthly or Annual" in snippet or "Monthly or Yearly" in snippet
        )
        self.assertIn("subscription starts when you pay", snippet)
        self.assertNotIn("7 day trial", snippet.lower())
        self.assertNotIn("7-day trial", snippet.lower())
        self.assertTrue(
            "Stripe" in snippet or "Buy now" in snippet or "secure" in snippet.lower()
        )
        self.assertIn("download starts automatically", snippet)
        self.assertIn(
            "licence key and download links are emailed to you separately",
            snippet,
        )
        # Old keygen-email clause and 7-day trial copy must not remain
        self.assertNotIn("keygen is emailed to you directly", snippet)
        self.assertNotIn("keygen is emailed to you directly", html)
        self.assertNotIn(
            "Your monthly subscription (£2.45 per month) begins after your 7 day trial",
            snippet,
        )
        self.assertNotIn(
            "Your monthly subscription (£2.45 per month) begins after your 7 day trial",
            html,
        )
        self.assertNotIn(
            "your monthly subscription begins after your 7 day trial",
            html.lower(),
        )
        # Old sole identity without subscription/licence language must not remain
        self.assertNotEqual(
            snippet.strip(),
            f"{PRICE_LABEL} GBP per package — pay on Stripe, then download starts automatically",
        )
        # Order: price → package identity → subscription sentence → checkout → email clause
        i_price = snippet.find(f"{PRICE_LABEL} GBP")
        i_pkg = snippet.find(package)
        i_sub = snippet.find(sub_sentence)
        i_pay = snippet.find("checkout") if "checkout" in snippet else snippet.find("Stripe")
        i_links = snippet.find(
            "licence key and download links are emailed to you separately"
        )
        self.assertLess(i_price, i_pkg)
        self.assertLess(i_pkg, i_sub)
        self.assertLess(i_sub, i_pay)
        self.assertLess(i_pay, i_links)
        self.assertIn(PAY_AND_KEYGEN_CLAUSE, snippet)
        # Box width ~2/3 + fluid narrow rule on real CSS from shipped download_css()
        css = download_css()
        self.assertIn(".dl-price-box", css)
        self.assertTrue(
            "width: 66.67%" in css or "max-width: 66.67%" in css,
            "price box must target ~2/3 width of downloads panel",
        )
        self.assertIn("max-width: 66.67%", css)
        self.assertIn("@media (max-width: 640px)", css)
        # Narrow viewport reflow to full panel width
        self.assertRegex(
            css,
            r"@media \(max-width:\s*640px\)[\s\S]*?\.dl-price-box[\s\S]*?width:\s*100%",
        )
        # ONLY £2.45 banner: large, white, standout serif font stack
        self.assertIn(".dl-only-price", css)
        self.assertIn("#ffffff", css)
        self.assertIn("font-size:", css)
        self.assertRegex(css, r"\.dl-only-price[\s\S]*?color:\s*#ffffff")
        self.assertNotRegex(css, r"\.dl-only-price[\s\S]*?color:\s*#22c55e")
        self.assertRegex(
            css,
            r"\.dl-only-price[\s\S]*?font-family:[\s\S]*?(Georgia|Palatino|cursive|serif)",
        )
        self.assertRegex(
            css,
            r"\.dl-only-price[\s\S]*?font-size:\s*clamp\(",
        )
        # Nested GBP line is also white bold
        self.assertRegex(css, r"\.dl-price[\s\S]*?color:\s*#ffffff")


class TestKeygenMintAndEmail(unittest.TestCase):
    def setUp(self):
        self._td = tempfile.TemporaryDirectory()
        self.data = Path(self._td.name)
        self.env = mock.patch.dict(
            os.environ,
            {"RPT_PAYMENT_DATA_DIR": str(self.data)},
            clear=False,
        )
        self.env.start()
        # Fresh module DB path
        import payments as pay

        pay.init_db()

    def tearDown(self):
        self.env.stop()
        self._td.cleanup()

    def test_checkout_mints_unique_keygen_and_email_payload(self):
        import payments as pay

        sent: list[dict] = []

        def capture_transport(payload: dict):
            sent.append(payload)
            return {"ok": True, "sent": True}

        event = {
            "type": "checkout.session.completed",
            "data": {
                "object": {
                    "id": "cs_test_keygen_1",
                    "payment_status": "paid",
                    "amount_total": 245,
                    "currency": "gbp",
                    "client_reference_id": "windows",
                    "customer_email": "buyer@example.com",
                    "metadata": {
                        "platform": "windows",
                        "amount_pence": "245",
                        "currency": "gbp",
                    },
                }
            },
        }
        token = pay.process_checkout_completed_event(
            event, email_transport=capture_transport
        )
        self.assertTrue(token)
        ent = pay.get_connect_entitlement("cs_test_keygen_1")
        self.assertIsNotNone(ent)
        assert ent is not None
        self.assertEqual(ent["status"], "active")
        self.assertTrue(ent["connect_allowed"])
        kg = ent.get("keygen") or ""
        self.assertTrue(kg.startswith("RPT-KEY-"))
        self.assertGreaterEqual(len(kg), 16)

        # Lookup by keygen
        by_kg = pay.get_connect_entitlement_by_keygen(kg)
        self.assertIsNotNone(by_kg)
        assert by_kg is not None
        self.assertEqual(by_kg["session_id"], "cs_test_keygen_1")
        self.assertTrue(by_kg["connect_allowed"])

        # Email captured (or built via fulfil path)
        self.assertTrue(sent, "fulfilment email transport should receive payload")
        body = sent[0]["body"]
        self.assertIn(pay.KEYGEN_UNLOCK_INSTRUCTION, body)
        self.assertIn(kg, body)
        self.assertIn("buyer@example.com", sent[0]["to"])
        self.assertIn("download", body.lower())
        # PPI present
        self.assertTrue(
            "RPT-" in body or "purchase" in body.lower() or "PPI" in body,
            body,
        )
        # Unlock sentence exact
        self.assertIn(
            "USE THIS KEYGEN TO UNLOCK RESTORE PRIVACY", body
        )

        # Second grant same session keeps same keygen
        kg2 = pay.activate_connect_entitlement("cs_test_keygen_1", platform="windows")
        self.assertEqual(kg2, kg)

    def test_build_fulfilment_email_payload_contents(self):
        import payments as pay

        payload = pay.build_fulfilment_email_payload(
            to_email="a@b.co",
            keygen="RPT-KEY-AAAA-BBBB-CCCC",
            purchase_id="RPT-1111-2222-3333",
            download_url="https://restoreprivacy.online/download?token=abc",
            platform="linux",
            session_id="cs_x",
            filename="pkg.tar.gz",
        )
        self.assertEqual(payload["to"], "a@b.co")
        self.assertEqual(payload["keygen"], "RPT-KEY-AAAA-BBBB-CCCC")
        self.assertEqual(payload["purchase_id"], "RPT-1111-2222-3333")
        self.assertIn(payload["download_url"], payload["body"])
        self.assertIn(pay.KEYGEN_UNLOCK_INSTRUCTION, payload["body"])
        self.assertIn("RPT-KEY-AAAA-BBBB-CCCC", payload["body"])
        self.assertIn("RPT-1111-2222-3333", payload["body"])

    def test_revoke_makes_keygen_useless(self):
        import payments as pay

        pay.activate_connect_entitlement("cs_rev", platform="android")
        ent = pay.get_connect_entitlement("cs_rev")
        assert ent is not None
        kg = ent["keygen"]
        self.assertTrue(pay.connect_entitlement_allows("cs_rev"))
        pay.revoke_connect_entitlement(
            "cs_rev", reason="charge.refunded", status=pay.ENTITLEMENT_REVOKED
        )
        ent2 = pay.get_connect_entitlement_by_keygen(kg)
        assert ent2 is not None
        self.assertFalse(ent2["connect_allowed"])
        self.assertIn(ent2["status"], ("revoked", "failed"))


class TestAdminKeygenFailsafeMint(unittest.TestCase):
    """Admin failsafe KEYGEN mint drives shipped payments helpers."""

    def setUp(self):
        self._td = tempfile.TemporaryDirectory()
        self.data = Path(self._td.name)
        self.env = mock.patch.dict(
            os.environ,
            {"RPT_PAYMENT_DATA_DIR": str(self.data)},
            clear=False,
        )
        self.env.start()
        import payments as pay

        pay.init_db()
        self.pay = pay

    def tearDown(self):
        self.env.stop()
        self._td.cleanup()

    def test_admin_mint_unique_active_keygen_lookup(self):
        a = self.pay.admin_mint_keygen_failsafe(platform="windows", note="ticket-1")
        b = self.pay.admin_mint_keygen_failsafe(platform="linux")
        self.assertTrue(a.get("admin_keygen_failsafe"))
        self.assertTrue(b.get("admin_keygen_failsafe"))
        self.assertTrue(str(a["keygen"]).startswith(self.pay.KEYGEN_PREFIX))
        self.assertTrue(str(b["keygen"]).startswith(self.pay.KEYGEN_PREFIX))
        self.assertNotEqual(a["keygen"], b["keygen"])
        self.assertNotEqual(a["session_id"], b["session_id"])
        self.assertTrue(str(a["session_id"]).startswith("admin_keygen_"))
        ent = self.pay.get_connect_entitlement_by_keygen(a["keygen"])
        self.assertIsNotNone(ent)
        assert ent is not None
        self.assertTrue(ent["connect_allowed"])
        self.assertEqual(ent["status"], self.pay.ENTITLEMENT_ACTIVE)
        self.assertEqual(ent["keygen"], a["keygen"])
        self.assertEqual(ent["session_id"], a["session_id"])

    def test_admin_mint_keygen_revoke_blocks_connect(self):
        out = self.pay.admin_mint_keygen_failsafe()
        kg = out["keygen"]
        sid = out["session_id"]
        ent = self.pay.get_connect_entitlement_by_keygen(kg)
        self.assertIsNotNone(ent)
        assert ent is not None
        self.assertTrue(ent["connect_allowed"])
        self.pay.revoke_connect_entitlement(
            sid, reason="operator_revoke", status=self.pay.ENTITLEMENT_REVOKED
        )
        ent2 = self.pay.get_connect_entitlement_by_keygen(kg)
        self.assertIsNotNone(ent2)
        assert ent2 is not None
        self.assertFalse(ent2["connect_allowed"])


class TestClientKeygenGate(unittest.TestCase):
    def test_licence_then_keygen_then_revoke(self):
        from client.licence_gate import (
            accept_licence,
            assert_may_connect,
            may_connect,
        )
        from client.payment_entitlement import (
            import_keygen_and_verify,
            load_payment_entitlement,
            payment_allows_connect,
            record_payment_failure,
        )

        with tempfile.TemporaryDirectory() as td:
            lic = Path(td) / "licence_acceptance.json"
            pay = Path(td) / "payment_entitlement.json"

            # (a) without licence accept, unlock fails
            self.assertFalse(may_connect(lic))
            ok, msg = assert_may_connect(lic)
            self.assertFalse(ok)
            self.assertIn("licence", msg.lower())

            accept_licence(lic)

            # (b) licence accept but wrong/missing keygen
            with mock.patch(
                "client.payment_entitlement.default_entitlement_path",
                return_value=pay,
            ):
                with mock.patch(
                    "client.payment_entitlement.ensure_entitlement_for_connect",
                    side_effect=lambda **kw: load_payment_entitlement(pay),
                ):
                    self.assertFalse(may_connect(lic))
                    ok2, msg2 = assert_may_connect(lic)
                    self.assertFalse(ok2)

                def fake_active(sid, keygen=""):
                    return {
                        "session_id": "cs_from_keygen",
                        "status": "active",
                        "connect_allowed": True,
                        "keygen": keygen or "RPT-KEY-DEAD-BEEF-CAFE",
                        "platform": "windows",
                    }

                # (c) accept + keygen that status reports active
                ent = import_keygen_and_verify(
                    "RPT-KEY-DEAD-BEEF-CAFE",
                    path=pay,
                    fetch=fake_active,
                )
                self.assertEqual(ent.status, "active")
                self.assertEqual(ent.keygen, "RPT-KEY-DEAD-BEEF-CAFE")
                self.assertTrue(payment_allows_connect(path=pay, require=True))

                with mock.patch(
                    "client.payment_entitlement.default_entitlement_path",
                    return_value=pay,
                ):
                    with mock.patch(
                        "client.payment_entitlement.ensure_entitlement_for_connect",
                        side_effect=lambda **kw: load_payment_entitlement(pay),
                    ):
                        self.assertTrue(may_connect(lic))

                # (d) after revoke, unlock fails
                record_payment_failure(
                    "cs_from_keygen",
                    reason="charge.refunded",
                    status="revoked",
                    path=pay,
                )
                self.assertFalse(payment_allows_connect(path=pay, require=True))
                with mock.patch(
                    "client.payment_entitlement.default_entitlement_path",
                    return_value=pay,
                ):
                    with mock.patch(
                        "client.payment_entitlement.ensure_entitlement_for_connect",
                        side_effect=lambda **kw: load_payment_entitlement(pay),
                    ):
                        self.assertFalse(may_connect(lic))
                        ok3, msg3 = assert_may_connect(lic)
                        self.assertFalse(ok3)
                        low3 = msg3.lower()
                        self.assertTrue(
                            "renew your licence" in low3
                            or "expired" in low3
                            or "payment" in low3,
                            msg3,
                        )


class TestKeygenOnlineOnlySecurity(unittest.TestCase):
    def test_no_offline_forever_unlock_helpers(self):
        """Keygen must not unlock Connect offline forever after revoke."""
        pay = (ROOT / "client" / "payment_entitlement.py").read_text(encoding="utf-8")
        self.assertIn("refresh_entitlement_from_remote", pay)
        self.assertIn("STATUS_REVOKED", pay)
        self.assertIn("assert_payment_may_connect", pay)
        low = pay.lower()
        self.assertNotIn("offline forever", low)
        self.assertNotIn("never recheck", low)

    def test_assert_payment_refresh_default_true(self):
        import inspect

        from client.payment_entitlement import assert_payment_may_connect

        sig = inspect.signature(assert_payment_may_connect)
        self.assertEqual(sig.parameters["refresh"].default, True)


if __name__ == "__main__":
    unittest.main()
