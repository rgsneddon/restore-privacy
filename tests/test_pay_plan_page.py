"""Site-hosted Select your plan page + subscription checkout session builders.

Drives shipped payments.render_pay_plan_page_html, yearly_amount_pence,
build_subscription_checkout_form_body, create_subscription_checkout_session.
"""

from __future__ import annotations

import os
import sys
import unittest
from pathlib import Path
from unittest import mock
from urllib.parse import parse_qs, unquote

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "status_page"))


class TestYearlyFivePercentOff(unittest.TestCase):
    def test_yearly_pence_is_five_percent_off_twelve_months(self):
        from payments import (
            PRICE_PENCE,
            PRICE_YEARLY_PENCE,
            YEARLY_DISCOUNT_PERCENT,
            yearly_amount_pence,
        )

        self.assertEqual(PRICE_PENCE, 245)
        self.assertEqual(YEARLY_DISCOUNT_PERCENT, 5)
        expected = int(round(245 * 12 * 0.95))
        self.assertEqual(expected, 2793)
        self.assertEqual(yearly_amount_pence(), expected)
        self.assertEqual(PRICE_YEARLY_PENCE, expected)
        # Not the pre-discount 12× full price
        self.assertNotEqual(PRICE_YEARLY_PENCE, 2940)
        self.assertLess(PRICE_YEARLY_PENCE, PRICE_PENCE * 12)


class TestPayPlanPageHtml(unittest.TestCase):
    def test_select_your_plan_monthly_and_annual(self):
        from payments import (
            PRICE_YEARLY_LABEL,
            STRIPE_PRODUCT_NAME_MONTHLY,
            STRIPE_PRODUCT_NAME_YEARLY,
            render_pay_plan_page_html,
        )

        html = render_pay_plan_page_html("windows", interval="month").decode()
        self.assertIn("Select your plan", html)
        self.assertIn(STRIPE_PRODUCT_NAME_MONTHLY, html)
        self.assertIn(STRIPE_PRODUCT_NAME_YEARLY, html)
        self.assertIn("SAVE 5%", html)
        self.assertIn(PRICE_YEARLY_LABEL, html)
        self.assertIn("£27.93", html)
        self.assertIn('name="interval"', html)
        self.assertIn('value="month"', html)
        self.assertIn('value="year"', html)
        self.assertIn('action="/pay/checkout"', html)
        self.assertIn('name="platform"', html)
        self.assertIn("windows", html)
        self.assertIn("Continue to secure checkout", html)
        # Main-site chrome
        self.assertIn("brand-panel", html)
        self.assertIn("RESTORE PRIVACY", html.upper())

    def test_annual_preselect(self):
        from payments import render_pay_plan_page_html

        html = render_pay_plan_page_html("linux", interval="year").decode()
        # year radio checked
        self.assertRegex(html, r'value="year"[^>]*checked|checked[^>]*value="year"')


class TestSubscriptionCheckoutBody(unittest.TestCase):
    def test_month_and_year_use_distinct_price_ids(self):
        from payments import (
            DEFAULT_STRIPE_PRICE_ID_MONTHLY,
            DEFAULT_STRIPE_PRICE_ID_YEARLY,
            STRIPE_PRODUCT_NAME_MONTHLY,
            STRIPE_PRODUCT_NAME_YEARLY,
            build_subscription_checkout_form_body,
            stripe_subscription_price_id_for_interval,
        )

        bm = build_subscription_checkout_form_body(
            "windows",
            "pkg.exe",
            interval="month",
            success_url="https://ex/s",
            cancel_url="https://ex/c",
        ).decode()
        by = build_subscription_checkout_form_body(
            "windows",
            "pkg.exe",
            interval="year",
            success_url="https://ex/s",
            cancel_url="https://ex/c",
        ).decode()
        self.assertIn("mode=subscription", bm)
        self.assertIn("mode=subscription", by)
        mid = stripe_subscription_price_id_for_interval("month")
        yid = stripe_subscription_price_id_for_interval("year")
        self.assertEqual(mid, DEFAULT_STRIPE_PRICE_ID_MONTHLY)
        self.assertEqual(yid, DEFAULT_STRIPE_PRICE_ID_YEARLY)
        self.assertNotEqual(mid, yid)
        self.assertIn(mid, unquote(bm))
        self.assertIn(yid, unquote(by))
        self.assertNotIn(yid, unquote(bm))
        self.assertNotIn(mid, unquote(by))
        # No free trial fields
        self.assertNotIn("trial_period_days", bm)
        self.assertNotIn("trial_period_days", by)
        self.assertIn("windows%7Cmonth", bm.replace("|", "%7C"))
        self.assertIn("windows%7Cyear", by.replace("|", "%7C"))
        self.assertIn(STRIPE_PRODUCT_NAME_MONTHLY.replace(" ", "+"), bm)
        self.assertIn(STRIPE_PRODUCT_NAME_YEARLY.replace(" ", "+"), by)

    def test_create_session_posts_subscription_and_returns_url(self):
        from payments import (
            PRICE_YEARLY_PENCE,
            create_subscription_checkout_session,
        )

        captured: list[tuple] = []

        def fake_post(url, headers, body):
            captured.append((url, headers, body.decode()))
            return (
                200,
                b'{"id":"cs_test_plan_1","url":"https://checkout.stripe.com/c/pay/cs_test_plan_1"}',
            )

        with mock.patch.dict(
            os.environ, {"STRIPE_SECRET_KEY": "sk_test_fake_key_for_unit"}, clear=False
        ):
            # Clear processor store path noise — secret from env
            out = create_subscription_checkout_session(
                "macos",
                interval="year",
                base_url="https://restoreprivacy.online",
                http_post=fake_post,
            )
        self.assertEqual(out["id"], "cs_test_plan_1")
        self.assertIn("checkout.stripe.com", out["url"])
        self.assertEqual(out["billing_interval"], "year")
        self.assertEqual(out["amount_pence"], PRICE_YEARLY_PENCE)
        self.assertEqual(out["product_name"], "Yearly VPN plan")
        self.assertEqual(out["mode"], "subscription")
        self.assertTrue(captured)
        body = captured[0][2]
        self.assertIn("mode=subscription", body)
        self.assertIn("price_1TwjimJDavQ2TJW6wEKr4upj", unquote(body))


class TestCatalogRoutesToSitePayPlan(unittest.TestCase):
    def test_catalog_homepage_buy_form(self):
        from downloads import available_downloads, render_download_section_html
        from payments import site_pay_plan_path

        html = render_download_section_html(
            coming_soon=False, currency="GBP", country="GB"
        )
        self.assertIn('data-buy-mode="homepage-buy-form"', html)
        self.assertIn('action="/pay/checkout"', html)
        self.assertIn("Buy now", html)
        self.assertNotIn("buy.stripe.com", html)
        self.assertNotIn("dl-windows-year", html)
        self.assertIn("Monthly VPN plan", html)
        self.assertIn("£27.93", html)
        self.assertIn("5%", html)
        for a in available_downloads():
            self.assertEqual(a.pay_path, site_pay_plan_path(a.platform, interval="month"))
            self.assertIn(f'value="{a.platform}"', html)


class TestDesiredCatalogShape(unittest.TestCase):
    def test_desired_products_and_no_trial(self):
        from payments import (
            STRIPE_PRODUCT_NAME_MONTHLY,
            STRIPE_PRODUCT_NAME_YEARLY,
            desired_payment_link_trial_fields,
        )

        d = desired_payment_link_trial_fields()
        self.assertEqual(d["trial_period_days"], 0)
        self.assertEqual(d["unit_amount_yearly_pence"], 2793)
        self.assertEqual(d["yearly_discount_percent"], 5)
        self.assertEqual(d["product_name_monthly"], STRIPE_PRODUCT_NAME_MONTHLY)
        self.assertEqual(d["product_name_yearly"], STRIPE_PRODUCT_NAME_YEARLY)
        self.assertEqual(d["catalog_entry"], "/pay")
        self.assertIn("/pay", d["payment_page_url"])


if __name__ == "__main__":
    unittest.main()
