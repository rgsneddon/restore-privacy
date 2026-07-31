"""Stripe Custom domains + Dashboard branding guide (shipped docs + helpers).

Drives payments.stripe_checkout_branding_guide and the operator doc artifact.
"""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "status_page"))


class TestStripeBrandingGuide(unittest.TestCase):
    def test_guide_explains_custom_domains_and_limits(self):
        from payments import (
            STRIPE_BRAND_PRIMARY_COLOR,
            STRIPE_BRAND_SECONDARY_COLOR,
            STRIPE_CUSTOM_DOMAIN_RECOMMENDED,
            stripe_checkout_branding_guide,
        )

        g = stripe_checkout_branding_guide()
        cd = g["custom_domains"]
        self.assertIn("subdomain", cd["what_it_does"].lower())
        self.assertIn("dns", cd["what_it_does"].lower())
        self.assertIn("css", cd["what_it_does_not"].lower())
        self.assertFalse(cd["seamless"]["full_site_css_on_stripe_page"])
        self.assertTrue(cd["seamless"]["url_brand_trust"])
        self.assertEqual(cd["recommended_subdomain"], STRIPE_CUSTOM_DOMAIN_RECOMMENDED)
        self.assertIn("custom-domains", cd["dashboard_url"])

        brand = g["branding"]
        self.assertEqual(brand["primary_color"], STRIPE_BRAND_PRIMARY_COLOR)
        self.assertEqual(brand["primary_color"], "#2694e8")
        self.assertEqual(brand["secondary_color"], STRIPE_BRAND_SECONDARY_COLOR)
        self.assertEqual(brand["secondary_color"], "#0a1628")
        self.assertFalse(brand["full_site_css_on_checkout"])
        self.assertFalse(brand["account_api_self_update"])
        self.assertTrue(brand["logo_exists"], "stripe_brand_logo.png must ship")
        self.assertTrue(brand["icon_exists"])
        self.assertIn("stripe_brand_logo.png", brand["logo_relpath"])
        self.assertIn("stripe_brand_icon.png", brand["icon_relpath"])
        self.assertTrue(brand.get("logo_constraints_ok"))
        self.assertTrue(brand.get("icon_constraints_ok"))
        self.assertIn("public_chrome", brand["source_theme"])

    def test_logo_file_on_disk(self):
        logo = ROOT / "status_page" / "static" / "logo.png"
        self.assertTrue(logo.is_file())
        self.assertGreater(logo.stat().st_size, 100)


class TestOperatorDocCustomDomains(unittest.TestCase):
    def test_doc_answers_custom_domains_and_branding(self):
        doc = ROOT / "docs" / "STRIPE_CUSTOM_DOMAINS_AND_BRANDING.md"
        self.assertTrue(doc.is_file())
        text = doc.read_text(encoding="utf-8")
        low = text.lower()
        self.assertIn("custom domains", low)
        self.assertIn("cname", low)
        self.assertIn("subdomain", low)
        # Markdown may bold "not" as **not** (breaks contiguous "does not")
        self.assertTrue(
            "does not" in low
            or "do **not**" in low
            or "does **not**" in low
            or "not** load" in low,
            "doc must state CSS is not injected",
        )
        self.assertIn("css", low)
        self.assertIn("paid", low)
        self.assertIn("pay.restoreprivacy.online", text)
        self.assertIn("#2694e8", text)
        self.assertIn("#0a1628", text)
        self.assertIn("stripe_brand_logo.png", text)
        self.assertIn("stripe_brand_icon.png", text)
        self.assertIn("settings/branding", low)
        self.assertIn("settings/custom-domains", low)
        # Seamless answer: URL yes, full CSS no
        self.assertIn("url trust", low)
        self.assertIn("full site css", low)
        self.assertIn("stripe_checkout_branding_guide", text)

    def test_public_chrome_palette_matches_guide(self):
        """Branding hexes must match shipped public theme tokens."""
        chrome = (ROOT / "status_page" / "public_chrome.py").read_text(encoding="utf-8")
        from payments import STRIPE_BRAND_PRIMARY_COLOR, STRIPE_BRAND_SECONDARY_COLOR

        self.assertIn(STRIPE_BRAND_PRIMARY_COLOR, chrome)
        self.assertIn(STRIPE_BRAND_SECONDARY_COLOR, chrome)
        self.assertIn("--rb-btn", chrome)
        self.assertIn("--rb-navy", chrome)

    def test_customer_note_mentions_limits(self):
        from downloads import STRIPE_CHECKOUT_BRANDING_NOTE

        low = STRIPE_CHECKOUT_BRANDING_NOTE.lower()
        self.assertIn("cannot load this website", low)
        self.assertIn("full css", low)
        self.assertIn("logo", low)


class TestCheckoutFlowStillSubscription(unittest.TestCase):
    def test_buy_form_and_subscription_bodies_unchanged(self):
        from downloads import render_download_section_html
        from payments import (
            build_subscription_checkout_form_body,
            stripe_subscription_price_id_for_interval,
        )
        from urllib.parse import unquote

        html = render_download_section_html(
            coming_soon=False, currency="GBP", country="GB"
        )
        self.assertIn("Buy now", html)
        self.assertIn("/pay/checkout", html)
        mid = stripe_subscription_price_id_for_interval("month")
        yid = stripe_subscription_price_id_for_interval("year")
        self.assertNotEqual(mid, yid)
        body = build_subscription_checkout_form_body(
            "linux",
            "x.tar.gz",
            interval="year",
            success_url="https://x/s",
            cancel_url="https://x/c",
        ).decode()
        self.assertIn("mode=subscription", body)
        self.assertIn(yid, unquote(body))
        self.assertIn("subscription_data%5Btrial_period_days%5D=3", body)


if __name__ == "__main__":
    unittest.main()
