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

        self.assertEqual(PRICE_MONTHLY_GBP, 2.45)
        self.assertEqual(PRICE_YEARLY_GBP, 29.40)
        self.assertEqual(PRICE_MONTHLY_PENCE, 245)
        self.assertEqual(PRICE_YEARLY_PENCE, 2940)
        self.assertAlmostEqual(PRICE_YEARLY_GBP, 12 * PRICE_MONTHLY_GBP, places=2)

    def test_convert_eur_and_jpy(self):
        from local_currency import (
            convert_gbp_to_currency,
            format_money,
            resolve_local_price_display,
        )

        # Fixed table: EUR 1.17 per GBP
        eur_m = convert_gbp_to_currency(2.45, "EUR")
        self.assertAlmostEqual(eur_m, 2.45 * 1.17, places=4)
        eur_y = convert_gbp_to_currency(29.40, "EUR")
        self.assertAlmostEqual(eur_y, 29.40 * 1.17, places=4)
        self.assertIn("EUR", format_money(eur_m, "EUR"))

        jpy = convert_gbp_to_currency(2.45, "JPY")
        self.assertAlmostEqual(jpy, 2.45 * 190.0, places=2)
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
        self.assertIn("£2.45", html)
        self.assertIn("£29.40", html)
        self.assertIn("data-display-currency=\"EUR\"", html)
        # Monthly/Yearly tiles carry local amounts
        self.assertIn("Monthly EUR", html)
        self.assertIn("Yearly EUR", html)
        self.assertIn("client_reference_id=", html)
        self.assertIn("locale=", html)

    def test_usd_fallback_html(self):
        from downloads import render_download_section_html

        html = render_download_section_html(
            coming_soon=False, currency="NOTACURRENCY"
        )
        self.assertIn("we accept *USD*", html)
        self.assertIn("Monthly USD", html)
        self.assertIn("Yearly USD", html)

    def test_pay_href_uses_locale_for_presentment(self):
        from payments import stripe_payment_page_href_for_platform

        href = stripe_payment_page_href_for_platform(
            "windows", interval="month", currency="EUR"
        )
        self.assertIn("client_reference_id=", href)
        self.assertIn("windows", href)
        self.assertIn("month", href)
        self.assertIn("locale=", href)
        # Currency must not corrupt platform|interval ref
        self.assertNotIn("windows%7Cmonth%7Ceur", href.lower())
        href_usd = stripe_payment_page_href_for_platform(
            "linux", interval="year", currency="XYZ"
        )
        self.assertIn("locale=", href_usd)


class TestStripePresentmentSet(unittest.TestCase):
    def test_major_currencies_allowed(self):
        from local_currency import is_stripe_presentment_currency

        for c in ("USD", "EUR", "GBP", "JPY", "AUD", "CAD", "BRL", "INR"):
            self.assertTrue(is_stripe_presentment_currency(c), c)


if __name__ == "__main__":
    unittest.main()
