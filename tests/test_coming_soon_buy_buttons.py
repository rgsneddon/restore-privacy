"""Temporary Coming soon homepage buy-buttons + switch-back to Stripe pay."""

from __future__ import annotations

import os
import sys
import unittest
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "status_page"))

from downloads import (  # noqa: E402
    CATALOG_BUY_BUTTONS_COMING_SOON,
    COMING_SOON_PUBLIC_HREF,
    RELEASE_VERSION,
    available_downloads,
    catalog_buy_buttons_coming_soon,
    render_download_section_html,
    _render_platform_pay_link,
)


class TestComingSoonBuyButtons(unittest.TestCase):
    def test_default_switch_is_live_stripe_pay(self):
        # Product default: live Stripe Payment Link buttons (Coming soon off)
        self.assertFalse(CATALOG_BUY_BUTTONS_COMING_SOON)
        env = {
            k: v
            for k, v in os.environ.items()
            if k not in ("RPT_CATALOG_BUY_LIVE", "RPT_CATALOG_BUY_COMING_SOON")
        }
        with mock.patch.dict(os.environ, env, clear=True):
            self.assertFalse(catalog_buy_buttons_coming_soon())

    def test_render_coming_soon_labels_and_redundant_href(self):
        html = render_download_section_html(coming_soon=True)
        self.assertIn(COMING_SOON_PUBLIC_HREF, html)
        self.assertIn('data-buy-mode="coming-soon"', html)
        self.assertIn('data-pay-via="coming-soon"', html)
        self.assertIn('data-coming-soon="1"', html)
        # Simple BUY - version label even in coming-soon mode
        self.assertIn(f"BUY - {RELEASE_VERSION}", html)
        self.assertNotIn("Pay £2.45", html)
        # No live Stripe checkout destinations on temporary buttons
        self.assertNotIn("donate.stripe.com", html)
        self.assertNotIn("buy.stripe.com", html)
        self.assertNotIn("checkout.stripe.com", html)
        self.assertNotIn("client_reference_id=", html)
        # No free permanent GitHub installer hrefs
        self.assertNotIn("releases/download/", html)
        self.assertNotIn("github.com/rgsneddon/restore-privacy/releases/download", html)
        for a in available_downloads():
            self.assertIn(f'id="dl-{a.platform}"', html)
            self.assertIn(f'data-platform="{a.platform}"', html)
            self.assertIn(f'href="{COMING_SOON_PUBLIC_HREF}"', html)
            # Must not free-link the release asset URL
            self.assertNotIn(f'href="{a.url}"', html)

    def test_switch_off_restores_stripe_pay_architecture(self):
        html = render_download_section_html(coming_soon=False)
        self.assertIn('data-buy-mode="stripe-live"', html)
        self.assertIn('data-pay-via="stripe-payment-page"', html)
        self.assertNotIn('data-coming-soon="1"', html)
        self.assertNotIn('data-buy-mode="coming-soon"', html)
        # Live tiles: monthly + yearly (no single BUY face)
        self.assertIn("dl-interval-month", html)
        self.assertIn("dl-interval-year", html)
        for a in available_downloads():
            self.assertIn(f'id="dl-{a.platform}"', html)
            self.assertIn(f'id="dl-{a.platform}-year"', html)
            self.assertIn(f"platform={a.platform}", html)
            self.assertNotIn(f'href="{a.url}"', html)
        # Still no free GitHub installer buttons
        self.assertNotIn("releases/download/", html)

    def test_env_live_forces_paid_mode(self):
        with mock.patch.dict(os.environ, {"RPT_CATALOG_BUY_LIVE": "1"}, clear=False):
            self.assertFalse(catalog_buy_buttons_coming_soon())
            html = render_download_section_html()
            self.assertIn('data-buy-mode="stripe-live"', html)
            self.assertIn("dl-interval-month", html)

    def test_single_link_helper_branches(self):
        a = available_downloads()[0]
        soon = _render_platform_pay_link(a, coming_soon=True)
        self.assertIn(f"BUY - {RELEASE_VERSION}", soon)
        self.assertIn(COMING_SOON_PUBLIC_HREF, soon)
        self.assertIn('data-pay-via="coming-soon"', soon)
        self.assertIn('data-coming-soon="1"', soon)
        live = _render_platform_pay_link(a, coming_soon=False)
        self.assertIn("dl-interval-month", live)
        self.assertIn("dl-interval-year", live)
        self.assertIn('data-pay-via="stripe-payment-page"', live)
        self.assertIn(f'data-platform="{a.platform}"', live)
        self.assertIn(f"client_reference_id={a.platform}", live)

    def test_platform_colors_cover_month_and_year(self):
        """Monthly and yearly buy tiles share platform colour rules."""
        from downloads import download_css

        css = download_css()
        for plat in ("windows", "android", "macos", "ios", "linux"):
            self.assertIn(f'.dl-platform-cell[data-platform="{plat}"] a.dl', css)
            self.assertIn(f"a.dl#dl-{plat}-year", css)


if __name__ == "__main__":
    unittest.main()
