"""Stripe webhook endpoint URL on Render status service."""

from __future__ import annotations

import os
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "status_page"))

import admin_panel  # noqa: E402
import payments  # noqa: E402

PROD_WEBHOOK = "https://restoreprivacy.online/webhook/stripe"


class TestStripeWebhookEndpointUrl(unittest.TestCase):
    def setUp(self):
        os.environ.pop("RPT_PUBLIC_BASE_URL", None)

    def test_production_webhook_url_for_stripe_dashboard(self):
        self.assertEqual(payments.STRIPE_WEBHOOK_PATH, "/webhook/stripe")
        self.assertEqual(
            payments.stripe_webhook_endpoint_url(production=True), PROD_WEBHOOK
        )
        self.assertIn("checkout.session.completed", payments.STRIPE_WEBHOOK_EVENTS)
        guide = payments.stripe_webhook_operator_guidance()
        self.assertEqual(guide["endpoint_url"], PROD_WEBHOOK)
        self.assertEqual(guide["primary_event"], "checkout.session.completed")

    def test_env_base_overrides_production_when_not_localhost(self):
        os.environ["RPT_PUBLIC_BASE_URL"] = "https://custom.example.com"
        try:
            self.assertEqual(
                payments.stripe_webhook_endpoint_url(production=True),
                "https://custom.example.com/webhook/stripe",
            )
        finally:
            os.environ.pop("RPT_PUBLIC_BASE_URL", None)

    def test_admin_html_shows_production_webhook_and_event(self):
        html = admin_panel.render_processor_settings_html()
        self.assertIn("stripe-webhook-url", html)
        self.assertIn(PROD_WEBHOOK, html)
        self.assertIn("checkout.session.completed", html)
        self.assertIn("stripe-webhook-endpoint-url", html)
        self.assertNotIn("whsec_", html)
        self.assertNotIn("sk_live_", html)
        self.assertNotIn("sk_test_", html)

    def test_app_routes_webhook_path(self):
        import app as status_app

        src = Path(status_app.__file__).read_text(encoding="utf-8")
        self.assertIn('"/webhook/stripe"', src)
        self.assertIn("handle_stripe_webhook", src)


if __name__ == "__main__":
    unittest.main()
