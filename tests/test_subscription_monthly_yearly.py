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
        # Primary path is site-hosted plan page
        self.assertIn("/pay", href_m)
        self.assertIn("ios", href_m)
        self.assertIn("month", href_m)
        self.assertIn("year", href_y)
        self.assertNotEqual(href_m, href_y)

    def test_month_year_checkout_use_distinct_price_ids(self):
        """Subscription Checkout binds month vs year to distinct Stripe Price ids."""
        from urllib.parse import parse_qs

        from payments import (
            DEFAULT_STRIPE_PRICE_ID_MONTHLY,
            DEFAULT_STRIPE_PRICE_ID_YEARLY,
            PRICE_PENCE,
            PRICE_YEARLY_PENCE,
            build_subscription_checkout_form_body,
            stripe_subscription_price_id_for_interval,
        )

        mid = stripe_subscription_price_id_for_interval("month")
        yid = stripe_subscription_price_id_for_interval("year")
        self.assertEqual(mid, DEFAULT_STRIPE_PRICE_ID_MONTHLY)
        self.assertEqual(yid, DEFAULT_STRIPE_PRICE_ID_YEARLY)
        self.assertNotEqual(mid, yid)
        self.assertEqual(PRICE_PENCE, 300)
        self.assertEqual(PRICE_YEARLY_PENCE, 3000)
        bm = build_subscription_checkout_form_body(
            "windows", "f.exe", interval="month",
            success_url="https://x/s", cancel_url="https://x/c",
        ).decode()
        by = build_subscription_checkout_form_body(
            "windows", "f.exe", interval="year",
            success_url="https://x/s", cancel_url="https://x/c",
        ).decode()
        pm = parse_qs(bm)
        py = parse_qs(by)
        self.assertEqual(pm["line_items[0][price]"], [mid])
        self.assertEqual(py["line_items[0][price]"], [yid])

    def test_catalog_html_routes_to_site_pay_plan(self):
        from downloads import render_download_section_html

        html = render_download_section_html(
            coming_soon=False, currency="GBP", country="GB"
        )
        self.assertIn('action="/pay/checkout"', html)
        self.assertIn('data-buy-mode="homepage-buy-form"', html)
        self.assertIn("billing-intervals", html)
        self.assertIn("Buy now", html)
        self.assertIn("£30.00", html)
        self.assertNotIn("buy.stripe.com", html)
        self.assertNotIn("7 day trial", html.lower())
        self.assertNotIn("begins after your 7 day trial", html.lower())

        html_usd = render_download_section_html(
            coming_soon=False, currency="USD", country="US"
        )
        self.assertIn("/pay/checkout", html_usd)
        self.assertIn("homepage-buy-form", html_usd)


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
            build_local_platform_renew_url,
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
        self.assertIn("pay.restoreprivacy.online", msg)
        self.assertNotIn("127.0.0.1", msg)
        url = renew_licence_url("macos")
        self.assertTrue(url.startswith("http"))
        self.assertIn("macos", url.lower())
        self.assertIn("pay.restoreprivacy.online", url)
        # Pure local builder always embeds platform (no payments import)
        local = build_local_platform_renew_url("macos", interval="month")
        self.assertIn("pay.restoreprivacy.online", local)
        self.assertIn("macos", local.lower())
        self.assertIn("platform=macos", local)


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


class TestLocalPlatformRenewUrlWithoutPayments(unittest.TestCase):
    """Shipped desktop renew URL must be platform-specific without status_page on path."""

    def test_build_local_platform_renew_url_no_payments_import(self):
        from client.payment_entitlement import (
            DEFAULT_SITE_PAY_PLAN_BASE,
            build_local_platform_renew_url,
            renew_licence_message,
            renew_licence_url,
        )

        for plat in ("windows", "macos", "ios", "android", "linux"):
            url = build_local_platform_renew_url(plat, interval="month")
            self.assertTrue(url.startswith(DEFAULT_SITE_PAY_PLAN_BASE), plat)
            self.assertIn("pay.restoreprivacy.online", url)
            self.assertIn(f"platform={plat}", url)
            self.assertIn("interval=month", url)
            year = build_local_platform_renew_url(plat, interval="year")
            self.assertIn("interval=year", year)
            self.assertNotEqual(url, year)

        # Force renew_licence_url through local path (block payments import)
        with mock.patch.dict(sys.modules, {"payments": None}):
            # Also ensure status_page cannot be imported as payments
            real_import = __import__

            def _block_payments(name, *a, **kw):
                if name == "payments" or name.endswith(".payments"):
                    raise ImportError("blocked for unit test")
                return real_import(name, *a, **kw)

            with mock.patch("builtins.__import__", side_effect=_block_payments):
                # Clear any cached import
                sys.modules.pop("payments", None)
                url = renew_licence_url("macos")
                msg = renew_licence_message("macos")
        self.assertIn("macos", url.lower())
        self.assertIn("pay.restoreprivacy.online", url)
        self.assertNotIn("127.0.0.1", url)
        self.assertNotIn(":10000", url)
        self.assertNotEqual(url.rstrip("/"), "https://restoreprivacy.online")
        self.assertNotEqual(url.rstrip("/"), "https://restoreprivacy.online/")
        self.assertIn("Renew your licence *here*", msg)
        self.assertIn(url, msg)

    def test_refresh_stores_host_renew_url(self):
        from client.payment_entitlement import (
            load_payment_entitlement,
            record_payment_success,
            refresh_entitlement_from_remote,
        )

        with tempfile.TemporaryDirectory() as td:
            pay = Path(td) / "payment_entitlement.json"
            record_payment_success(
                "cs_renew",
                path=pay,
                keygen="RPT-KEY-ABCDEF0123456789ABCDEF01",
                platform="ios",
            )

            def fake_fetch(sid, keygen=""):
                return {
                    "session_id": sid,
                    "status": "revoked",
                    "reason": "charge.refunded",
                    "connect_allowed": False,
                    "platform": "ios",
                    "keygen": keygen,
                    "licence_status": "EXPIRED",
                    "renew_url": (
                        "https://buy.stripe.com/cNi7sM4uOeWQ9TBe0q7kc00"
                        "?client_reference_id=ios%7Cmonth"
                    ),
                }

            ent = refresh_entitlement_from_remote(path=pay, fetch=fake_fetch)
            self.assertEqual(ent.status, "revoked")
            self.assertIn("ios", ent.renew_url.lower())
            self.assertIn("buy.stripe.com", ent.renew_url)
            loaded = load_payment_entitlement(pay)
            self.assertEqual(loaded.renew_url, ent.renew_url)
            from client.payment_entitlement import renew_licence_url

            # Cached host renew_url preferred (Stripe Payment Link is customer-safe)
            self.assertEqual(
                renew_licence_url("ios", path=pay),
                loaded.renew_url,
            )

    def test_localhost_renew_url_rewritten_to_device_pay_host(self) -> None:
        """Dev status-host URLs must never appear in EXPIRED / invalid-licence copy."""
        from client.payment_entitlement import (
            DEVICE_LICENCE_PAY_HOST,
            is_customer_safe_renew_url,
            renew_licence_message,
            renew_licence_url,
        )

        bad = "http://127.0.0.1:10000/pay?platform=windows&interval=month"
        self.assertFalse(is_customer_safe_renew_url(bad))
        url = renew_licence_url("windows", renew_url=bad)
        self.assertIn("pay.restoreprivacy.online", url)
        self.assertNotIn("127.0.0.1", url)
        self.assertNotIn(":10000", url)
        self.assertTrue(url.startswith(DEVICE_LICENCE_PAY_HOST))
        self.assertIn("platform=windows", url)
        msg = renew_licence_message("windows", renew_url=bad)
        self.assertIn("pay.restoreprivacy.online", msg)
        self.assertNotIn("127.0.0.1", msg)


def urllib_parse_unquote(s: str) -> str:
    import urllib.parse

    return urllib.parse.unquote(s)


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
