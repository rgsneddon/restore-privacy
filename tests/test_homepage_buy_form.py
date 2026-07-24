"""Homepage Download client box: platform + plan + Buy now → checkout.

Drives shipped downloads.render_download_section_html and payments checkout builders.
"""

from __future__ import annotations

import sys
import unittest
from pathlib import Path
from urllib.parse import unquote

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "status_page"))


class TestHomepageBuyFormInDownloadsBox(unittest.TestCase):
    def test_downloads_section_has_platform_plan_and_buy_now(self):
        from downloads import (
            BUY_NOW_LABEL,
            STRIPE_CHECKOUT_BRANDING_NOTE,
            available_downloads,
            render_download_section_html,
        )

        html = render_download_section_html(
            coming_soon=False, currency="GBP", country="GB"
        )
        self.assertIn('id="downloads"', html)
        self.assertIn('id="dl-buy-form"', html)
        self.assertIn('action="/pay/checkout"', html)
        self.assertIn('method="post"', html)
        self.assertIn('id="dl-platform"', html)
        self.assertIn('name="platform"', html)
        self.assertIn('name="interval"', html)
        self.assertIn('value="month"', html)
        self.assertIn('value="year"', html)
        self.assertIn('id="dl-buy-now"', html)
        self.assertIn(BUY_NOW_LABEL, html)
        self.assertIn("Monthly VPN plan", html)
        self.assertIn("Yearly VPN plan", html)
        self.assertIn("SAVE 5%", html)
        self.assertIn(STRIPE_CHECKOUT_BRANDING_NOTE, html)
        # Branding honesty: no claim Stripe-hosted page uses full site CSS
        low = STRIPE_CHECKOUT_BRANDING_NOTE.lower()
        self.assertIn("cannot load this website", low)
        self.assertNotIn("full css parity on stripe", low)
        for a in available_downloads():
            self.assertIn(f'value="{a.platform}"', html)

    def test_old_multi_tile_pay_grid_removed(self):
        from downloads import render_download_section_html

        html = render_download_section_html(
            coming_soon=False, currency="GBP", country="GB"
        )
        self.assertNotIn('id="dl-row-1"', html)
        self.assertNotIn('id="dl-row-2"', html)
        self.assertNotIn("dl-windows-year", html)
        self.assertNotIn("dl-interval-windows", html)
        self.assertNotIn('data-buy-mode="site-pay-plan"', html)
        self.assertNotIn("buy.stripe.com", html)
        self.assertIn('data-buy-mode="homepage-buy-form"', html)
        self.assertIn('data-pay-via="homepage-buy-form"', html)


class TestCheckoutIntervalDistinct(unittest.TestCase):
    def test_month_year_distinct_price_ids_no_trial(self):
        from payments import (
            PRICE_PENCE,
            PRICE_YEARLY_PENCE,
            build_subscription_checkout_form_body,
            stripe_subscription_price_id_for_interval,
            yearly_amount_pence,
        )

        self.assertEqual(PRICE_YEARLY_PENCE, yearly_amount_pence())
        self.assertEqual(PRICE_YEARLY_PENCE, 2793)
        mid = stripe_subscription_price_id_for_interval("month")
        yid = stripe_subscription_price_id_for_interval("year")
        self.assertNotEqual(mid, yid)
        bm = build_subscription_checkout_form_body(
            "windows",
            "pkg.exe",
            interval="month",
            success_url="https://x/s",
            cancel_url="https://x/c",
        ).decode()
        by = build_subscription_checkout_form_body(
            "windows",
            "pkg.exe",
            interval="year",
            success_url="https://x/s",
            cancel_url="https://x/c",
        ).decode()
        self.assertIn("mode=subscription", bm)
        self.assertIn(mid, unquote(bm))
        self.assertIn(yid, unquote(by))
        self.assertNotIn(yid, unquote(bm))
        self.assertNotIn("trial_period_days", bm)
        self.assertNotIn("trial_period_days", by)
        self.assertEqual(PRICE_PENCE, 245)


if __name__ == "__main__":
    unittest.main()
