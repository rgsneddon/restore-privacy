"""Buy button size/Stripe host, platform note, thank-you KEYGEN UX."""

from __future__ import annotations

import os
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "status_page"))


class TestBuyButtonsAndStripeHost(unittest.TestCase):
    def test_live_catalog_buy_stripe_not_donate(self):
        from downloads import PLATFORM_SELECT_NOTE, download_css, render_download_section_html
        from payments import (
            DEFAULT_STRIPE_PAYMENT_PAGE_URL,
            stripe_payment_page_href_for_platform,
            stripe_payment_page_url,
        )

        html = render_download_section_html(coming_soon=False)
        css = download_css()
        self.assertIn("buy.stripe.com", html)
        self.assertNotIn("donate.stripe.com", html)
        self.assertIn("7.25rem", css)
        self.assertIn("min-width: 7.25rem", css)
        self.assertIn(PLATFORM_SELECT_NOTE, html)
        self.assertIn('id="dl-platform-note-box"', html)
        self.assertIn("dl-platform-note", css)
        self.assertIn("buy.stripe.com", DEFAULT_STRIPE_PAYMENT_PAGE_URL)
        self.assertIn("buy.stripe.com", stripe_payment_page_url())
        href = stripe_payment_page_href_for_platform("windows")
        self.assertIn("buy.stripe.com", href)
        self.assertIn("client_reference_id=windows", href)

    def test_donate_env_normalized_to_buy(self):
        from payments import stripe_payment_page_url

        os.environ["STRIPE_PAYMENT_PAGE_URL"] = (
            "https://donate.stripe.com/cNi7sM4uOeWQ9TBe0q7kc00"
        )
        try:
            u = stripe_payment_page_url()
            self.assertIn("buy.stripe.com", u)
            self.assertNotIn("donate.stripe.com", u)
        finally:
            os.environ.pop("STRIPE_PAYMENT_PAGE_URL", None)


class TestThankYouKeygenProminent(unittest.TestCase):
    def test_keygen_box_copy_and_no_page_timeout(self):
        from payments import render_post_payment_thankyou_html

        html = render_post_payment_thankyou_html(
            download_path="/download?token=tok_ui_test",
            filename="restore-privacy-client-0.3.9-linux-x64.tar.gz",
            platform="linux",
            session_id="cs_ui_test",
            purchase_id="RPT-AAAA-BBBB-CCCC",
            keygen="RPT-KEY-1111-2222-3333",
        )
        self.assertIn("Thank you", html)
        self.assertIn("installer is ready", html)
        self.assertIn("RPT-KEY-1111-2222-3333", html)
        self.assertIn('id="product-keygen"', html)
        self.assertIn("product-keygen-display", html)
        self.assertIn('id="keygen-copy-btn"', html)
        self.assertIn("navigator.clipboard", html)
        self.assertIn('id="success-download-link"', html)
        self.assertIn("until you close the tab", html.lower())
        self.assertNotIn('http-equiv="refresh"', html.lower())
        # No JS that clears href of success-download-link on a timer
        self.assertNotIn(
            'getElementById("success-download-link").removeAttribute',
            html,
        )
        # Styles for large white keygen live on the success page wrapper
        page_css = (ROOT / "status_page" / "app.py").read_text(encoding="utf-8")
        self.assertIn("product-keygen-display", page_css)
        self.assertIn("#ffffff", page_css)


if __name__ == "__main__":
    unittest.main()
