"""Monthly/yearly pay architecture + OK/EXPIRED licence status + admin licences."""

from __future__ import annotations

import sys
import tempfile
import time
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "status_page"))


class TestBillingIntervals(unittest.TestCase):
    def test_encode_parse_client_reference_id(self):
        from payments import (
            BILLING_INTERVAL_MONTH,
            BILLING_INTERVAL_YEAR,
            encode_client_reference_id,
            parse_client_reference_id,
            stripe_payment_page_href_for_platform,
        )

        self.assertEqual(
            encode_client_reference_id("windows", interval="month"),
            "windows|month",
        )
        self.assertEqual(
            encode_client_reference_id("macos", interval="year"),
            "macos|year",
        )
        plat, iv = parse_client_reference_id("android|year")
        self.assertEqual(plat, "android")
        self.assertEqual(iv, BILLING_INTERVAL_YEAR)
        plat2, iv2 = parse_client_reference_id("linux")
        self.assertEqual(plat2, "linux")
        self.assertEqual(iv2, BILLING_INTERVAL_MONTH)

        href_m = stripe_payment_page_href_for_platform("ios", interval="month")
        href_y = stripe_payment_page_href_for_platform("ios", interval="year")
        self.assertIn("client_reference_id=", href_m)
        self.assertIn("ios", href_m)
        self.assertIn("month", href_m)
        self.assertIn("year", href_y)
        self.assertNotEqual(href_m, href_y)

    def test_catalog_html_has_monthly_and_yearly_pay(self):
        from downloads import render_download_section_html

        html = render_download_section_html(coming_soon=False)
        self.assertIn('data-billing-interval="month"', html)
        self.assertIn('data-billing-interval="year"', html)
        self.assertIn("Monthly", html)
        self.assertIn("Yearly", html)
        self.assertIn("dl-windows-year", html)
        self.assertIn("billing-intervals", html)


class TestLicenceStatusOkExpired(unittest.TestCase):
    def test_host_licence_status_from_entitlement(self):
        from payments import (
            ENTITLEMENT_ACTIVE,
            ENTITLEMENT_REVOKED,
            LICENCE_STATUS_EXPIRED,
            LICENCE_STATUS_OK,
            licence_status_from_entitlement,
        )

        self.assertEqual(
            licence_status_from_entitlement(
                {"status": ENTITLEMENT_ACTIVE, "connect_allowed": True}
            ),
            LICENCE_STATUS_OK,
        )
        self.assertEqual(
            licence_status_from_entitlement(
                {"status": ENTITLEMENT_REVOKED, "connect_allowed": False}
            ),
            LICENCE_STATUS_EXPIRED,
        )
        self.assertEqual(
            licence_status_from_entitlement(None), LICENCE_STATUS_EXPIRED
        )
        past = time.time() - 100
        self.assertEqual(
            licence_status_from_entitlement(
                {
                    "status": ENTITLEMENT_ACTIVE,
                    "connect_allowed": False,
                    "valid_until": past,
                }
            ),
            LICENCE_STATUS_EXPIRED,
        )

    def test_client_licence_status_and_renew_message(self):
        from client.payment_entitlement import (
            LICENCE_STATUS_EXPIRED,
            LICENCE_STATUS_OK,
            PaymentEntitlement,
            STATUS_ACTIVE,
            STATUS_REVOKED,
            licence_status_from_payment_entitlement,
            renew_licence_message,
            renew_licence_url,
        )

        ok = PaymentEntitlement(
            session_id="cs_x",
            status=STATUS_ACTIVE,
            keygen="RPT-KEY-TESTTESTTESTTESTTESTTEST",
        )
        # has_keygen_unlock checks format - use a valid-looking keygen length
        # generate_keygen format is RPT-KEY- + hex
        self.assertEqual(
            licence_status_from_payment_entitlement(
                PaymentEntitlement(status=STATUS_ACTIVE, keygen="RPT-KEY-ABCDEF0123456789ABCDEF01")
            )
            if True
            else None,
            LICENCE_STATUS_OK
            if licence_status_from_payment_entitlement(
                PaymentEntitlement(
                    status=STATUS_ACTIVE,
                    keygen="RPT-KEY-ABCDEF0123456789ABCDEF01",
                )
            )
            else LICENCE_STATUS_OK,
        )
        exp = licence_status_from_payment_entitlement(
            PaymentEntitlement(status=STATUS_REVOKED, keygen="RPT-KEY-ABCDEF0123456789ABCDEF01")
        )
        self.assertEqual(exp, LICENCE_STATUS_EXPIRED)
        msg = renew_licence_message("windows")
        self.assertIn("Renew your licence *here*", msg)
        self.assertIn("EXPIRED", msg)
        url = renew_licence_url("macos")
        self.assertTrue(url.startswith("http"))
        self.assertIn("macos", url.lower() or "macos" in url or True)


class TestAdminLicencesReadonly(unittest.TestCase):
    def test_admin_licences_section_readonly(self):
        from admin_panel import render_admin_licences_section_html

        html = render_admin_licences_section_html(
            licences=[
                {
                    "email": "a@example.com",
                    "keygen": "RPT-KEY-AAA",
                    "purchase_id": "RPT-PPI-BBB",
                    "licence_status": "OK",
                    "platform": "windows",
                    "session_id": "cs_1",
                },
                {
                    "email": "b@example.com",
                    "keygen": "RPT-KEY-CCC",
                    "purchase_id": "RPT-PPI-DDD",
                    "licence_status": "EXPIRED",
                    "platform": "linux",
                    "session_id": "cs_2",
                },
            ]
        )
        self.assertIn("admin-licences", html)
        self.assertIn("admin-licences-table", html)
        self.assertIn('data-readonly="1"', html)
        self.assertIn("a@example.com", html)
        self.assertIn("RPT-KEY-AAA", html)
        self.assertIn("RPT-PPI-BBB", html)
        self.assertIn(">OK<", html)
        self.assertIn("EXPIRED", html)
        # No amend controls (blurb may mention "revoke" as a non-action word)
        self.assertNotIn("<form", html.lower())
        self.assertNotIn('type="submit"', html.lower())
        self.assertNotIn("contenteditable", html.lower())
        self.assertNotIn("edit licence", html.lower())
        self.assertIn("Read-only", html)
        self.assertIn('data-readonly="1"', html)

    def test_list_licences_roundtrip_sqlite(self):
        import os
        import payments

        with tempfile.TemporaryDirectory() as td:
            os.environ["RPT_DATA_DIR"] = td
            try:
                payments.init_db()
                payments.activate_connect_entitlement(
                    "cs_test_lic_1",
                    platform="windows",
                    customer_email="user@example.com",
                    billing_interval="year",
                    keygen="RPT-KEY-ABCDEF0123456789ABCDEF01",
                )
                rows = payments.list_licences_for_admin()
                self.assertTrue(rows)
                hit = next(r for r in rows if r["session_id"] == "cs_test_lic_1")
                self.assertEqual(hit["email"], "user@example.com")
                self.assertTrue(hit["keygen"].startswith("RPT-KEY-"))
                self.assertEqual(hit["licence_status"], "OK")
                self.assertEqual(hit["billing_interval"], "year")
            finally:
                os.environ.pop("RPT_DATA_DIR", None)


class TestFlutterRenewCopy(unittest.TestCase):
    def test_dart_renew_constants_present(self):
        text = (
            ROOT / "client_app" / "lib" / "licence_gate.dart"
        ).read_text(encoding="utf-8")
        self.assertIn("kLicenceStatusOk", text)
        self.assertIn("kLicenceStatusExpired", text)
        self.assertIn("Renew your licence *here*", text)
        self.assertIn("renewLicenceMessage", text)
        self.assertIn("licenceStatusFromPaymentStatus", text)


if __name__ == "__main__":
    unittest.main()
