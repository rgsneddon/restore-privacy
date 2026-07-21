"""Stripe payment page URL + remaining required keys for paid-download readiness."""

from __future__ import annotations

import os
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "status_page"))

import admin_panel  # noqa: E402
import payments  # noqa: E402
import processor_plugins as plugins  # noqa: E402

OPERATOR_PAYMENT_PAGE = "https://donate.stripe.com/cNi7sM4uOeWQ9TBe0q7kc00"


class TestStripePaymentPageUrl(unittest.TestCase):
    def setUp(self):
        for k in (
            "STRIPE_PAYMENT_PAGE_URL",
            "RPT_STRIPE_PAYMENT_PAGE_URL",
            "STRIPE_SECRET_KEY",
            "STRIPE_WEBHOOK_SECRET",
            "RPT_PUBLIC_BASE_URL",
        ):
            os.environ.pop(k, None)

    def test_default_is_operator_donate_url(self):
        url = payments.stripe_payment_page_url()
        self.assertEqual(url, OPERATOR_PAYMENT_PAGE)
        self.assertEqual(payments.DEFAULT_STRIPE_PAYMENT_PAGE_URL, OPERATOR_PAYMENT_PAGE)

    def test_env_override(self):
        os.environ["STRIPE_PAYMENT_PAGE_URL"] = "https://donate.stripe.com/custom_test"
        self.assertEqual(
            payments.stripe_payment_page_url(),
            "https://donate.stripe.com/custom_test",
        )


class TestStripeWhatsNext(unittest.TestCase):
    def setUp(self):
        for k in (
            "STRIPE_SECRET_KEY",
            "STRIPE_WEBHOOK_SECRET",
            "RPT_PUBLIC_BASE_URL",
            "STRIPE_PAYMENT_PAGE_URL",
            "RPT_STRIPE_PAYMENT_PAGE_URL",
        ):
            os.environ.pop(k, None)

    def test_payment_page_alone_not_fulfilment_ready(self):
        # Payment page is set by default; secrets cleared
        self.assertEqual(payments.stripe_payment_page_url(), OPERATOR_PAYMENT_PAGE)
        remaining = payments.stripe_remaining_required_keys()
        self.assertIn("STRIPE_SECRET_KEY", remaining)
        self.assertIn("STRIPE_WEBHOOK_SECRET", remaining)
        ready = plugins._stripe_readiness()
        self.assertTrue(ready.get("payment_page_ready"))
        self.assertEqual(ready.get("payment_page_url"), OPERATOR_PAYMENT_PAGE)
        self.assertFalse(ready.get("checkout_ready"))
        self.assertFalse(ready.get("fulfilment_ready"))
        self.assertFalse(ready.get("ready"))
        self.assertIn("STRIPE_SECRET_KEY", ready.get("remaining_required") or [])
        self.assertIn("STRIPE_WEBHOOK_SECRET", ready.get("whats_next") or [])

    def test_secrets_clear_remaining(self):
        os.environ["STRIPE_SECRET_KEY"] = "sk_test_FAKE_FOR_UNIT"
        os.environ["STRIPE_WEBHOOK_SECRET"] = "whsec_FAKE_FOR_UNIT"
        os.environ["RPT_PUBLIC_BASE_URL"] = "https://restore-privacy-status.onrender.com"
        remaining = payments.stripe_remaining_required_keys()
        self.assertEqual(remaining, [])
        ready = plugins._stripe_readiness()
        self.assertTrue(ready.get("fulfilment_ready"))
        self.assertEqual(ready.get("whats_next") or [], [])


class TestPaymentPageInAdminHtml(unittest.TestCase):
    def setUp(self):
        for k in (
            "STRIPE_SECRET_KEY",
            "STRIPE_WEBHOOK_SECRET",
            "STRIPE_PAYMENT_PAGE_URL",
            "RPT_STRIPE_PAYMENT_PAGE_URL",
        ):
            os.environ.pop(k, None)

    def test_admin_shows_payment_page_and_whats_next_no_secrets(self):
        os.environ["STRIPE_SECRET_KEY"] = "sk_test_MUST_NOT_APPEAR_IN_HTML_xyz"
        html = admin_panel.render_processor_settings_html()
        self.assertIn("admin-processor-settings", html)
        self.assertIn(OPERATOR_PAYMENT_PAGE, html)
        self.assertIn("stripe-payment-page", html)
        self.assertIn("link-stripe-payment-page", html)
        self.assertIn("stripe-whats-next", html)
        # with secret set, webhook still missing → what's next mentions webhook
        os.environ.pop("STRIPE_SECRET_KEY", None)
        html2 = admin_panel.render_processor_settings_html()
        self.assertIn("STRIPE_SECRET_KEY", html2)
        self.assertIn("stripe-remaining-required", html2)
        self.assertNotIn("sk_test_MUST_NOT_APPEAR", html2)
        self.assertNotIn("whsec_", html2)

    def test_public_footer_has_payment_page_link(self):
        from downloads import render_rust_footer_html

        foot = render_rust_footer_html()
        self.assertIn("stripe-payment-page-link", foot)
        self.assertIn(OPERATOR_PAYMENT_PAGE, foot)
        self.assertNotIn("/admin/processors/apply", foot)


if __name__ == "__main__":
    unittest.main()
