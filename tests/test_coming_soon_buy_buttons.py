"""Homepage buy buttons: live form vs temporary Coming soon mode."""

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
    RELEASE_VERSION,
    available_downloads,
    catalog_buy_buttons_coming_soon,
    render_download_section_html,
)


class TestComingSoonBuyButtons(unittest.TestCase):
    def test_default_switch_is_live_buy_form(self):
        self.assertFalse(CATALOG_BUY_BUTTONS_COMING_SOON)
        env = {
            k: v
            for k, v in os.environ.items()
            if k not in ("RPT_CATALOG_BUY_LIVE", "RPT_CATALOG_BUY_COMING_SOON")
        }
        with mock.patch.dict(os.environ, env, clear=True):
            self.assertFalse(catalog_buy_buttons_coming_soon())

    def test_render_coming_soon_mode(self):
        html = render_download_section_html(coming_soon=True)
        self.assertIn('data-buy-mode="coming-soon"', html)
        self.assertNotIn("Pay £3.00", html)
        self.assertNotIn("donate.stripe.com", html)
        self.assertNotIn("buy.stripe.com", html)
        self.assertNotIn("checkout.stripe.com", html)
        self.assertNotIn("releases/download/", html)

    def test_live_mode_homepage_buy_form(self):
        html = render_download_section_html(coming_soon=False)
        self.assertIn('data-buy-mode="homepage-buy-form"', html)
        self.assertIn('action="/pay/checkout"', html)
        self.assertIn("Buy now", html)
        self.assertIn("£3.00", html)
        self.assertIn("£30.00", html)
        self.assertNotIn('data-buy-mode="coming-soon"', html)
        self.assertNotIn("buy.stripe.com", html)
        self.assertNotIn("releases/download/", html)
        for a in available_downloads():
            self.assertIn(f'value="{a.platform}"', html)

    def test_env_live_forces_paid_mode(self):
        with mock.patch.dict(os.environ, {"RPT_CATALOG_BUY_LIVE": "1"}, clear=False):
            self.assertFalse(catalog_buy_buttons_coming_soon())
            html = render_download_section_html()
            self.assertIn('data-buy-mode="homepage-buy-form"', html)
            self.assertIn("£3.00", html)


if __name__ == "__main__":
    unittest.main()
