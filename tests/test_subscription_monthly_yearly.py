"""Monthly/yearly pay architecture + OK/EXPIRED licence status + admin licences."""

from __future__ import annotations

import sys
import tempfile
import time
import unittest
from pathlib import Path
from unittest import mock

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

        kg = "RPT-KEY-ABCDEF0123456789ABCDEF01"
        ok_ent = PaymentEntitlement(
            session_id="cs_x",
            status=STATUS_ACTIVE,
            keygen=kg,
        )
        self.assertEqual(
            licence_status_from_payment_entitlement(ok_ent),
            LICENCE_STATUS_OK,
        )
        exp = licence_status_from_payment_entitlement(
            PaymentEntitlement(status=STATUS_REVOKED, keygen=kg)
        )
        self.assertEqual(exp, LICENCE_STATUS_EXPIRED)
        msg = renew_licence_message("windows")
        self.assertIn("Renew your licence *here*", msg)
        self.assertIn("EXPIRED", msg)
        url = renew_licence_url("macos")
        self.assertTrue(url.startswith("http"))
        self.assertIn("macos", url.lower())


class TestExpiredVsKeygenUiGate(unittest.TestCase):
    """EXPIRED must not open keygen surface; needs_keygen_unlock is false."""

    def test_revoked_needs_renewal_not_keygen(self):
        from client.licence_gate import (
            accept_licence,
            needs_keygen_unlock,
            needs_licence_renewal,
        )
        from client.payment_entitlement import record_payment_failure, record_payment_success

        with tempfile.TemporaryDirectory() as td:
            lic = Path(td) / "licence_acceptance.json"
            pay = Path(td) / "payment_entitlement.json"
            accept_licence(lic)
            record_payment_success(
                "cs_ok",
                path=pay,
                keygen="RPT-KEY-ABCDEF0123456789ABCDEF01",
                platform="windows",
            )
            with mock.patch(
                "client.payment_entitlement.default_entitlement_path",
                return_value=pay,
            ):
                self.assertFalse(needs_licence_renewal(lic))
                self.assertFalse(needs_keygen_unlock(lic))

                record_payment_failure(
                    "cs_ok", reason="charge.refunded", status="revoked", path=pay
                )
                self.assertTrue(needs_licence_renewal(lic))
                self.assertFalse(
                    needs_keygen_unlock(lic),
                    "EXPIRED/revoked must not route to keygen modal",
                )

    def test_active_without_keygen_needs_keygen_not_renewal(self):
        from client.licence_gate import (
            accept_licence,
            needs_keygen_unlock,
            needs_licence_renewal,
        )
        from client.payment_entitlement import record_payment_success

        with tempfile.TemporaryDirectory() as td:
            lic = Path(td) / "licence_acceptance.json"
            pay = Path(td) / "payment_entitlement.json"
            accept_licence(lic)
            # Session-only thank-you — no keygen
            record_payment_success("cs_session_only", path=pay, platform="linux")
            with mock.patch(
                "client.payment_entitlement.default_entitlement_path",
                return_value=pay,
            ):
                self.assertFalse(needs_licence_renewal(lic))
                self.assertTrue(needs_keygen_unlock(lic))

    def test_windows_linux_ship_renew_prompt_before_keygen(self):
        win = (ROOT / "client" / "windows" / "app.py").read_text(encoding="utf-8")
        linux = (ROOT / "client" / "linux" / "app.py").read_text(encoding="utf-8")
        flutter = (ROOT / "client_app" / "lib" / "main.dart").read_text(
            encoding="utf-8"
        )
        for src, name in ((win, "windows"), (linux, "linux")):
            self.assertIn("_show_renew_licence_prompt", src, name)
            self.assertIn("needs_licence_renewal", src, name)
            self.assertIn("Renew your licence", src, name)
            self.assertIn("Open payment portal", src, name)
            # fail_gate: renew before keygen (contiguous elif chain)
            gate = "elif needs_licence_renewal():"
            self.assertIn(gate, src, name)
            i = src.find(gate)
            window = src[i : i + 280]
            self.assertIn("_show_renew_licence_prompt", window, name)
            self.assertIn("needs_keygen_unlock", window, name)
            self.assertLess(
                window.find("_show_renew_licence_prompt"),
                window.find("_show_keygen_prompt"),
                f"{name}: fail_gate must open renew before keygen",
            )
            # Keygen prompt itself redirects EXPIRED → renew
            kg_i = src.find("def _show_keygen_prompt")
            self.assertGreater(kg_i, 0, name)
            kg_head = src[kg_i : kg_i + 400]
            self.assertIn("needs_licence_renewal", kg_head, name)
            self.assertIn("_show_renew_licence_prompt", kg_head, name)
        self.assertIn("_showRenewLicenceSheet", flutter)
        self.assertIn("needsLicenceRenewal", flutter)
        self.assertIn("Renew your licence *here*", flutter)
        self.assertIn("Open payment portal", flutter)
        # assertMayConnect routes EXPIRED to renew sheet
        amc = flutter.find("Future<bool> assertMayConnect()")
        self.assertGreater(amc, 0)
        amc_body = flutter[amc : amc + 600]
        self.assertIn("needsLicenceRenewal", amc_body)
        self.assertIn("_showRenewLicenceSheet", amc_body)
        self.assertLess(
            amc_body.find("needsLicenceRenewal"),
            amc_body.find("needsKeygenUnlock"),
        )


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
        self.assertIn(">EXPIRED<", html)
        self.assertIn("Read-only", html)
        # No amend/edit forms in the licences section
        section_start = html.find('id="admin-licences"')
        self.assertGreater(section_start, -1)
        section = html[section_start:]
        self.assertNotIn("<form", section.lower())
        self.assertNotIn('type="submit"', section.lower())


if __name__ == "__main__":
    unittest.main()
