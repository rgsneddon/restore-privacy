"""Restore Privacy Suite storefront + Stripe product_line + entitlement inheritance."""

from __future__ import annotations

import os
import sys
import tempfile
import time
import unittest
import urllib.parse
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "status_page"))
sys.path.insert(0, str(ROOT / "client"))


class TestSuiteStorefrontOrder(unittest.TestCase):
    def test_suite_section_precedes_vpn_downloads_in_render_html(self):
        from app import render_html
        from downloads import (
            DOWNLOADS_SECTION_ID,
            SUITE_SECTION_ID,
            SUITE_PRODUCT_TITLE,
            SUITE_FREE_DOWNLOAD_PATH,
        )

        html = render_html({"title": "RESTORE PRIVACY VPN"}).decode("utf-8")
        suite_at = html.find(f'id="{SUITE_SECTION_ID}"')
        vpn_at = html.find(f'id="{DOWNLOADS_SECTION_ID}"')
        self.assertGreaterEqual(suite_at, 0, "suite-storefront missing")
        self.assertGreaterEqual(vpn_at, 0, "downloads section missing")
        self.assertLess(suite_at, vpn_at, "Suite must appear above VPN downloads")
        self.assertIn(SUITE_PRODUCT_TITLE, html)
        self.assertIn('data-free-download="1"', html)
        self.assertIn(SUITE_FREE_DOWNLOAD_PATH, html)
        self.assertIn("Get KEYGEN", html)
        self.assertIn('name="product" value="suite"', html)
        self.assertIn('name="interval" value="month"', html)
        self.assertIn("/pay/checkout", html)
        # VPN shop section id/role preserved
        self.assertIn('id="downloads"', html)
        self.assertIn("Download Suite client", html)

    def test_suite_storefront_helper_emits_free_download_and_keygen(self):
        from downloads import (
            PRICE_LABEL,
            render_suite_storefront_html,
            SUITE_PRODUCT_TITLE,
            SUITE_FREE_DOWNLOAD_PATH,
        )

        block = render_suite_storefront_html(default_platform="windows")
        self.assertIn(SUITE_PRODUCT_TITLE, block)
        self.assertIn(PRICE_LABEL, block)
        self.assertIn('data-product="suite"', block)
        self.assertIn('data-free-download="1"', block)
        self.assertIn(SUITE_FREE_DOWNLOAD_PATH, block)
        self.assertIn("KEYGEN", block)
        self.assertIn("Evolve", block)
        self.assertNotIn("coming soon", block.lower())
        # Monthly licence only on Suite KEYGEN CTA
        self.assertIn('value="month"', block)
        self.assertNotIn("suite-plan-year", block)


class TestSuiteStripeCheckout(unittest.TestCase):
    def test_encode_parse_suite_client_reference(self):
        from payments import (
            encode_client_reference_id,
            parse_client_reference_id,
            parse_product_line_from_client_reference,
            PRODUCT_LINE_SUITE,
            PRODUCT_LINE_VPN,
        )

        ref = encode_client_reference_id(
            "windows", interval="month", product_line=PRODUCT_LINE_SUITE
        )
        self.assertEqual(ref, "windows|month|suite")
        plat, iv = parse_client_reference_id(ref)
        self.assertEqual(plat, "windows")
        self.assertEqual(iv, "month")
        self.assertEqual(
            parse_product_line_from_client_reference(ref), PRODUCT_LINE_SUITE
        )
        vpn_ref = encode_client_reference_id("android", interval="year")
        self.assertEqual(vpn_ref, "android|year")
        self.assertEqual(
            parse_product_line_from_client_reference(vpn_ref), PRODUCT_LINE_VPN
        )
        # year|suite must not collapse interval to month
        yref = encode_client_reference_id(
            "ios", interval="year", product_line="suite"
        )
        self.assertEqual(parse_client_reference_id(yref), ("ios", "year"))

    def test_build_subscription_body_marks_suite(self):
        from payments import (
            build_subscription_checkout_form_body,
            PRODUCT_LINE_SUITE,
            STRIPE_PRODUCT_NAME_SUITE_MONTHLY,
        )

        body = build_subscription_checkout_form_body(
            "windows",
            "restore-privacy-client-1.0.0-windows-x64-setup.exe",
            interval="month",
            success_url="https://example.test/ok",
            cancel_url="https://example.test/cancel",
            product_line=PRODUCT_LINE_SUITE,
        )
        fields = urllib.parse.parse_qs(body.decode("utf-8"))
        self.assertEqual(fields["metadata[product_line]"], ["suite"])
        self.assertEqual(fields["metadata[product]"], ["suite"])
        self.assertEqual(fields["client_reference_id"], ["windows|month|suite"])
        self.assertEqual(
            fields["metadata[product_name]"], [STRIPE_PRODUCT_NAME_SUITE_MONTHLY]
        )
        self.assertEqual(
            fields["subscription_data[metadata][product_line]"], ["suite"]
        )

    def test_vpn_body_unchanged_default(self):
        from payments import (
            build_subscription_checkout_form_body,
            STRIPE_PRODUCT_NAME_MONTHLY,
        )

        body = build_subscription_checkout_form_body(
            "linux",
            "restore-privacy-client-1.0.0-linux-x64.tar.gz",
            interval="month",
            success_url="https://example.test/ok",
            cancel_url="https://example.test/cancel",
        )
        fields = urllib.parse.parse_qs(body.decode("utf-8"))
        self.assertEqual(fields["metadata[product_line]"], ["vpn"])
        self.assertEqual(fields["client_reference_id"], ["linux|month"])
        self.assertEqual(
            fields["metadata[product_name]"], [STRIPE_PRODUCT_NAME_MONTHLY]
        )

    def test_create_subscription_session_passes_product_line(self):
        from payments import create_subscription_checkout_session

        captured: list[bytes] = []

        def fake_post(url, headers, body):  # noqa: ARG001
            captured.append(body)
            return 200, b'{"id":"cs_test_suite","url":"https://checkout.stripe.com/c/pay/cs_test"}'

        with mock.patch.dict(
            os.environ, {"STRIPE_SECRET_KEY": "sk_test_suite_unit"}, clear=False
        ):
            sess = create_subscription_checkout_session(
                "macos",
                interval="year",
                product_line="suite",
                http_post=fake_post,
                base_url="https://restoreprivacy.online",
            )
        self.assertEqual(sess["product_line"], "suite")
        self.assertIn("Suite", sess["product_name"])
        self.assertTrue(captured)
        fields = urllib.parse.parse_qs(captured[0].decode("utf-8"))
        self.assertEqual(fields["metadata[product_line]"], ["suite"])
        self.assertIn("suite-storefront", fields["cancel_url"][0])

    def test_product_line_from_checkout_object(self):
        from payments import product_line_from_checkout_object

        self.assertEqual(
            product_line_from_checkout_object(
                {"metadata": {"product_line": "suite"}}
            ),
            "suite",
        )
        self.assertEqual(
            product_line_from_checkout_object(
                {"client_reference_id": "windows|month|suite"}
            ),
            "suite",
        )
        self.assertEqual(
            product_line_from_checkout_object(
                {"client_reference_id": "windows|month"}
            ),
            "vpn",
        )


class TestSuiteEntitlementInheritance(unittest.TestCase):
    def setUp(self):
        self._td = tempfile.TemporaryDirectory()
        os.environ["RPT_PAYMENT_DATA_DIR"] = self._td.name

    def tearDown(self):
        self._td.cleanup()
        os.environ.pop("RPT_PAYMENT_DATA_DIR", None)

    def test_suite_activate_same_connect_semantics_as_vpn(self):
        from payments import (
            activate_connect_entitlement,
            client_entitlement_file_payload,
            get_connect_entitlement,
            get_connect_entitlement_by_keygen,
            PRODUCT_LINE_SUITE,
            PRODUCT_LINE_VPN,
        )

        now = time.time()
        vu = now + 86400 * 30
        kg_suite = activate_connect_entitlement(
            "cs_suite_inherit_1",
            platform="windows",
            valid_until=vu,
            billing_interval="month",
            product_line=PRODUCT_LINE_SUITE,
            now=now,
        )
        self.assertTrue(kg_suite.startswith("RPT-KEY-"))
        ent = get_connect_entitlement("cs_suite_inherit_1", now=now)
        assert ent is not None
        self.assertEqual(ent["status"], "active")
        self.assertTrue(ent["connect_allowed"])
        self.assertEqual(ent["product_line"], PRODUCT_LINE_SUITE)
        # Keygen unlock path (GUI + residual)
        by_kg = get_connect_entitlement_by_keygen(kg_suite, now=now)
        assert by_kg is not None
        self.assertTrue(by_kg["connect_allowed"])
        self.assertEqual(by_kg["product_line"], PRODUCT_LINE_SUITE)
        payload = client_entitlement_file_payload("cs_suite_inherit_1")
        assert payload is not None
        self.assertEqual(payload["product_line"], "suite")
        self.assertEqual(payload["status"], "active")
        self.assertTrue(payload["connect_allowed"])

        # VPN grant still works (regression)
        kg_vpn = activate_connect_entitlement(
            "cs_vpn_inherit_1",
            platform="android",
            valid_until=vu,
            billing_interval="year",
            product_line=PRODUCT_LINE_VPN,
            now=now,
        )
        ent_vpn = get_connect_entitlement("cs_vpn_inherit_1", now=now)
        assert ent_vpn is not None
        self.assertTrue(ent_vpn["connect_allowed"])
        self.assertEqual(ent_vpn["product_line"], PRODUCT_LINE_VPN)
        self.assertTrue(kg_vpn.startswith("RPT-KEY-"))

    def test_residual_client_accepts_suite_payload(self):
        """Python residual payment_entitlement inherits Suite active grants."""
        from payment_entitlement import (
            PaymentEntitlement,
            STATUS_ACTIVE,
            PRODUCT_LINE_SUITE,
            normalize_product_line,
        )

        ent = PaymentEntitlement.from_dict(
            {
                "session_id": "cs_suite_client",
                "status": STATUS_ACTIVE,
                "platform": "windows",
                "keygen": "RPT-KEY-TEST-SUITE-AAAA",
                "product_line": "suite",
                "valid_until": time.time() + 3600,
            }
        )
        self.assertEqual(ent.product_line, PRODUCT_LINE_SUITE)
        self.assertEqual(ent.status, STATUS_ACTIVE)
        self.assertEqual(normalize_product_line("suite"), PRODUCT_LINE_SUITE)
        d = ent.to_dict()
        self.assertEqual(d["product_line"], "suite")
        # Local status active is the unlock condition (same as VPN)
        self.assertEqual(ent.status, STATUS_ACTIVE)

    def test_admin_list_includes_suite_product_line(self):
        from payments import (
            activate_connect_entitlement,
            list_licences_for_admin,
            PRODUCT_LINE_SUITE,
        )

        now = time.time()
        activate_connect_entitlement(
            "cs_admin_suite",
            platform="linux",
            valid_until=now + 10000,
            product_line=PRODUCT_LINE_SUITE,
            customer_email="suite@example.test",
            now=now,
        )
        rows = list_licences_for_admin()
        suite_rows = [r for r in rows if r.get("session_id") == "cs_admin_suite"]
        self.assertTrue(suite_rows)
        self.assertEqual(suite_rows[0]["product_line"], "suite")


class TestSuiteCheckoutWebhookMint(unittest.TestCase):
    def setUp(self):
        self._td = tempfile.TemporaryDirectory()
        os.environ["RPT_PAYMENT_DATA_DIR"] = self._td.name

    def tearDown(self):
        self._td.cleanup()
        os.environ.pop("RPT_PAYMENT_DATA_DIR", None)

    def test_process_checkout_completed_suite_metadata(self):
        from downloads import RELEASE_VERSION
        from payments import (
            PRICE_PENCE,
            process_checkout_completed_event,
            get_connect_entitlement,
        )

        fname = f"restore-privacy-client-{RELEASE_VERSION}-windows-x64-setup.exe"
        event = {
            "type": "checkout.session.completed",
            "data": {
                "object": {
                    "id": "cs_test_suite_webhook",
                    "payment_status": "paid",
                    "amount_total": PRICE_PENCE,
                    "currency": "gbp",
                    "client_reference_id": "windows|month|suite",
                    "metadata": {
                        "platform": "windows",
                        "filename": fname,
                        "amount_pence": str(PRICE_PENCE),
                        "product_line": "suite",
                        "billing_interval": "month",
                    },
                    "subscription": "sub_suite_1",
                }
            },
        }
        token = process_checkout_completed_event(
            event, email_transport=lambda _p: {"ok": True}
        )
        self.assertTrue(token)
        ent = get_connect_entitlement("cs_test_suite_webhook")
        assert ent is not None
        self.assertEqual(ent["product_line"], "suite")
        self.assertTrue(ent["connect_allowed"])
        self.assertTrue((ent.get("keygen") or "").startswith("RPT-KEY-"))


if __name__ == "__main__":
    unittest.main()
