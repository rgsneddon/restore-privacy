"""Local currency display: GBP anchors → visitor currency; USD fallback."""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "status_page"))


class TestGbpAnchorsAndConvert(unittest.TestCase):
    def test_anchors(self):
        from local_currency import (
            PRICE_MONTHLY_GBP,
            PRICE_YEARLY_GBP,
            PRICE_MONTHLY_PENCE,
            PRICE_YEARLY_PENCE,
        )

        self.assertEqual(PRICE_MONTHLY_GBP, 3.00)
        self.assertEqual(PRICE_YEARLY_GBP, 30.00)
        self.assertEqual(PRICE_MONTHLY_PENCE, 300)
        self.assertEqual(PRICE_YEARLY_PENCE, 3000)
        # Fixed yearly catalog (£30), not 5% of 12× monthly
        self.assertEqual(PRICE_YEARLY_GBP, 30.00)
        self.assertLess(PRICE_YEARLY_GBP, 12 * PRICE_MONTHLY_GBP)

    def test_convert_eur_and_jpy(self):
        from local_currency import (
            convert_gbp_to_currency,
            format_money,
            resolve_local_price_display,
        )

        # Fixed table: EUR 1.17 per GBP
        eur_m = convert_gbp_to_currency(3.00, "EUR")
        self.assertAlmostEqual(eur_m, 3.00 * 1.17, places=4)
        eur_y = convert_gbp_to_currency(30.00, "EUR")
        self.assertAlmostEqual(eur_y, 30.00 * 1.17, places=4)
        self.assertIn("EUR", format_money(eur_m, "EUR"))

        jpy = convert_gbp_to_currency(3.00, "JPY")
        self.assertAlmostEqual(jpy, 3.00 * 190.0, places=2)
        # Zero-decimal display
        self.assertRegex(format_money(jpy, "JPY"), r"^JPY \d")

        fr = resolve_local_price_display(accept_language="fr-FR,fr;q=0.9")
        self.assertEqual(fr.currency, "EUR")
        self.assertIn("EUR", fr.monthly_label)
        self.assertIn("EUR", fr.yearly_label)
        self.assertEqual(fr.accept_notice, "we accept *EUR*")
        self.assertFalse(fr.used_fallback_usd)

        jp = resolve_local_price_display(accept_language="ja-JP")
        self.assertEqual(jp.currency, "JPY")
        self.assertIn("JPY", jp.monthly_label)


class TestUsdFallback(unittest.TestCase):
    def test_unsupported_currency_falls_back_to_usd(self):
        from local_currency import (
            FALLBACK_CURRENCY,
            is_stripe_presentment_currency,
            resolve_local_price_display,
            stripe_presentment_or_usd,
        )

        self.assertFalse(is_stripe_presentment_currency("XYZ"))
        self.assertEqual(stripe_presentment_or_usd("XYZ"), FALLBACK_CURRENCY)
        self.assertEqual(stripe_presentment_or_usd("rub"), "USD")

        # Explicit unsupported → USD display
        d = resolve_local_price_display(explicit_currency="XYZ")
        self.assertEqual(d.currency, "USD")
        self.assertEqual(d.stripe_presentment_currency, "USD")
        self.assertTrue(d.used_fallback_usd)
        self.assertEqual(d.accept_notice, "we accept *USD*")
        self.assertIn("USD", d.monthly_label)
        self.assertIn("USD", d.yearly_label)

    def test_country_and_header_resolution(self):
        from local_currency import (
            accept_language_from_request,
            country_headers_from_request,
            resolve_preferred_currency,
        )

        self.assertEqual(resolve_preferred_currency(country="DE"), "EUR")
        self.assertEqual(resolve_preferred_currency(country="US"), "USD")
        self.assertEqual(resolve_preferred_currency(country="GB"), "GBP")
        self.assertEqual(
            resolve_preferred_currency(accept_language="de-DE,de;q=0.8"),
            "EUR",
        )
        hdrs = {
            "Accept-Language": "fr-FR,fr;q=0.9,en;q=0.8",
            "CF-IPCountry": "FR",
        }
        self.assertEqual(accept_language_from_request(hdrs), "fr-FR,fr;q=0.9,en;q=0.8")
        self.assertEqual(country_headers_from_request(hdrs), "FR")


class TestCatalogHtmlLocalCurrency(unittest.TestCase):
    def test_downloads_section_shows_local_and_accept(self):
        from downloads import render_download_section_html

        html = render_download_section_html(
            coming_soon=False, accept_language="de-DE", country="DE"
        )
        self.assertIn("we accept *EUR*", html)
        self.assertIn('id="dl-local-price"', html)
        self.assertIn('id="dl-accept-currency"', html)
        self.assertIn("EUR", html)
        self.assertIn("£3.00", html)
        self.assertIn("£30.00", html)
        self.assertIn("data-display-currency=\"EUR\"", html)
        # Local line sits under title; upper explainer boxes gone
        self.assertNotIn('id="dl-only-price"', html)
        self.assertNotIn('id="dl-price-box"', html)
        heading_i = html.find("Download Suite client v")
        local_i = html.find('id="dl-local-price"')
        self.assertGreater(local_i, heading_i)
        # Catalog embeds buy form (local amounts on plan radio labels)
        self.assertIn("/pay/checkout", html)
        self.assertIn("homepage-buy-form", html)
        self.assertIn("EUR", html)

    def test_usd_fallback_html(self):
        from downloads import render_download_section_html

        html = render_download_section_html(
            coming_soon=False, currency="NOTACURRENCY"
        )
        self.assertIn("we accept *USD*", html)
        self.assertIn("USD", html)
        self.assertIn("/pay/checkout", html)
        self.assertIn("homepage-buy-form", html)

    def test_pay_href_uses_site_plan_page(self):
        from payments import (
            stripe_payment_page_href_for_platform,
            usd_pay_start_path,
        )

        href = stripe_payment_page_href_for_platform(
            "windows", interval="month", currency="EUR"
        )
        self.assertIn("/pay", href)
        self.assertIn("windows", href)
        self.assertIn("month", href)
        # Primary path is site plan page (not buy.stripe.com)
        self.assertNotIn("buy.stripe.com", href)

        href_usd = stripe_payment_page_href_for_platform(
            "linux", interval="year", currency="XYZ", base_url=""
        )
        href_eur = stripe_payment_page_href_for_platform(
            "linux", interval="year", currency="EUR"
        )
        # Both intervals still reach site /pay with platform
        self.assertIn("/pay", href_usd)
        self.assertIn("linux", href_usd)
        self.assertIn("year", href_usd)
        self.assertIn("/pay", href_eur)
        self.assertEqual(
            usd_pay_start_path("linux", interval="year"),
            "/pay/start?platform=linux&interval=year&currency=usd",
        )

    def test_direct_stripe_usd_link_env_when_requested(self):
        import os
        from payments import stripe_payment_page_href_for_platform

        os.environ["STRIPE_PAYMENT_PAGE_URL_USD"] = (
            "https://buy.stripe.com/test_usd_monthly_link"
        )
        try:
            href = stripe_payment_page_href_for_platform(
                "windows",
                interval="month",
                currency="XYZ",
                direct_stripe=True,
            )
            self.assertIn("buy.stripe.com/test_usd_monthly_link", href)
            self.assertIn("client_reference_id=", href)
            self.assertIn("locale=en", href)
            self.assertNotIn("/pay/start", href)
            # Default (no direct_stripe) stays on site plan page
            href_site = stripe_payment_page_href_for_platform(
                "windows", interval="month", currency="EUR"
            )
            self.assertNotIn("test_usd_monthly_link", href_site)
            self.assertIn("/pay", href_site)
        finally:
            os.environ.pop("STRIPE_PAYMENT_PAGE_URL_USD", None)

    def test_build_checkout_form_body_usd_is_usd(self):
        from payments import CheckoutRequest, build_checkout_form_body_usd

        import urllib.parse

        body = build_checkout_form_body_usd(
            CheckoutRequest(
                platform="windows",
                filename="pkg.exe",
                success_url="https://example.com/ok",
                cancel_url="https://example.com/cancel",
            ),
            amount_gbp=3.00,
            interval="month",
        ).decode("utf-8")
        decoded = urllib.parse.unquote(body)
        self.assertIn("currency]=usd", decoded)  # price_data[currency]=usd
        self.assertIn("unit_amount]=381", decoded)  # 3.00 * 1.27 * 100
        self.assertIn("presentment]=usd", decoded)
        self.assertNotIn("currency]=gbp", decoded)


class TestStripePresentmentSet(unittest.TestCase):
    def test_major_currencies_allowed(self):
        from local_currency import is_stripe_presentment_currency

        for c in ("USD", "EUR", "GBP", "JPY", "AUD", "CAD", "BRL", "INR"):
            self.assertTrue(is_stripe_presentment_currency(c), c)


if __name__ == "__main__":
    unittest.main()
