"""Homepage corporate deposit banner: FREE DOWNLOAD chrome + £3000 Checkout."""

from __future__ import annotations

import sys
import unittest
import urllib.parse
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "status_page"))


def _main_html(page: str) -> str:
    i = page.find('id="page-shell"')
    if i < 0:
        i = page.find("<body")
    return page[i:] if i >= 0 else page


class TestHomepageCorporateDepositCta(unittest.TestCase):
    def test_render_html_order_label_and_visual_family(self) -> None:
        from app import render_html
        from downloads import (
            CORPORATE_DEPOSIT_CTA_ID,
            CORPORATE_DEPOSIT_CTA_LABEL,
            CORPORATE_DEPOSIT_CTA_WRAP_ID,
            FREE_DOWNLOAD_CTA_ID,
            FREE_DOWNLOAD_CTA_LABEL,
        )
        from payments import (
            COMMERCIAL_SUITE_CHECKOUT_PATH,
            COMMERCIAL_SUITE_NODE_PRICE_PENCE,
            COMMERCIAL_SUITE_PRODUCT_KEY,
        )

        page = render_html({"title": "RESTORE PRIVACY"}).decode("utf-8")
        main = _main_html(page)

        self.assertIn(CORPORATE_DEPOSIT_CTA_LABEL, main)
        self.assertIn(f'id="{CORPORATE_DEPOSIT_CTA_WRAP_ID}"', main)
        self.assertIn(f'id="{CORPORATE_DEPOSIT_CTA_ID}"', main)
        self.assertIn('data-cta-shape="rectangle"', main)
        self.assertIn('data-cta-face="typewriter-logo-flanks"', main)
        self.assertIn("corporate-deposit-cta-label", main)
        self.assertEqual(main.count("data-corporate-deposit-logo=\"left\""), 1)
        self.assertEqual(main.count("data-corporate-deposit-logo=\"right\""), 1)
        i_left = main.index('data-corporate-deposit-logo="left"')
        i_lab = main.index("corporate-deposit-cta-label")
        i_right = main.index('data-corporate-deposit-logo="right"')
        self.assertLess(i_left, i_lab)
        self.assertLess(i_lab, i_right)

        i_corp = main.index('id="corporate-clients"')
        i_banner = main.index(f'id="{CORPORATE_DEPOSIT_CTA_WRAP_ID}"')
        i_nw = main.index("node-wipe")
        self.assertLess(i_corp, i_banner)
        self.assertLess(i_banner, i_nw)

        # FREE DOWNLOAD banner is unchanged and still above the shop row.
        self.assertIn(FREE_DOWNLOAD_CTA_LABEL, main)
        self.assertIn(f'id="{FREE_DOWNLOAD_CTA_ID}"', main)
        i_free = main.index(f'id="{FREE_DOWNLOAD_CTA_ID}"')
        i_shop = main.index('id="home-shop-row"')
        self.assertLess(i_free, i_shop)
        self.assertLess(i_shop, i_corp)

        # Existing full business-package box stays off the homepage.
        self.assertNotIn('id="download-node-preference"', main)
        self.assertNotIn("Full business package?", main)
        self.assertNotIn("data-home-business-package", main)
        self.assertNotIn("node-pref-deposit-btn", main)
        self.assertNotIn('data-business-package="1"', main)

        # Same neon / wrap family as FREE DOWNLOAD.
        self.assertIn(".free-download-cta-wrap", page)
        self.assertIn(".corporate-deposit-cta-wrap", page)
        self.assertIn("free-download-cta-logo-left", main)
        self.assertIn("Courier New", page)

        # Posts into existing £3000 one-time commercial Checkout — not KEYGEN.
        i_form = main.index('id="corporate-deposit-cta-form"')
        form = main[i_form : i_form + 900]
        self.assertIn(f'action="{COMMERCIAL_SUITE_CHECKOUT_PATH}"', form)
        self.assertIn(f'value="{COMMERCIAL_SUITE_NODE_PRICE_PENCE}"', form)
        self.assertIn(f'value="{COMMERCIAL_SUITE_PRODUCT_KEY}"', form)
        self.assertIn('name="amount_pence"', form)
        self.assertIn('name="billing" value="one_time"', form)
        self.assertIn('data-pay-via="commercial-suite"', form)
        self.assertNotIn('action="/pay"', form)
        self.assertNotIn('value="300"', form)
        self.assertNotIn('value="3000"', form)
        self.assertEqual(COMMERCIAL_SUITE_NODE_PRICE_PENCE, 300_000)
        self.assertNotEqual(COMMERCIAL_SUITE_CHECKOUT_PATH, "/pay")

        note = main[main.index("corporate-deposit-cta-note") :][:240].lower()
        self.assertIn("deposit", note)
        self.assertNotIn("checkout session", note)
        self.assertNotIn("unit_amount", note)
        self.assertNotIn("product_line", note)

    def test_pure_helper_matches_shipped_constants(self) -> None:
        from downloads import (
            CORPORATE_DEPOSIT_CTA_LABEL,
            render_corporate_deposit_cta_html,
        )
        from payments import (
            COMMERCIAL_SUITE_CHECKOUT_PATH,
            COMMERCIAL_SUITE_NODE_PRICE_PENCE,
            COMMERCIAL_SUITE_PRODUCT_KEY,
            COMMERCIAL_SUITE_PRODUCT_LINE,
        )

        self.assertEqual(CORPORATE_DEPOSIT_CTA_LABEL, "pay corporate deposit £3000")
        frag = render_corporate_deposit_cta_html()
        self.assertIn(CORPORATE_DEPOSIT_CTA_LABEL, frag)
        self.assertIn(f'action="{COMMERCIAL_SUITE_CHECKOUT_PATH}"', frag)
        self.assertIn(f'value="{COMMERCIAL_SUITE_NODE_PRICE_PENCE}"', frag)
        self.assertIn(f'value="{COMMERCIAL_SUITE_PRODUCT_KEY}"', frag)
        self.assertIn(f'value="{COMMERCIAL_SUITE_PRODUCT_LINE}"', frag)
        self.assertIn("logo_transparent.png", frag)
        self.assertIn('data-cta-face="typewriter-logo-flanks"', frag)


class TestCommercialCheckoutStillOneTimeDeposit(unittest.TestCase):
    def test_shipped_builder_stays_payment_300000_gbp(self) -> None:
        from payments import (
            COMMERCIAL_SUITE_NODE_PRICE_PENCE,
            COMMERCIAL_SUITE_PRODUCT_NAME,
            PRICE_PENCE,
            PRICE_YEARLY_PENCE,
            build_commercial_suite_checkout_form_body,
        )

        self.assertEqual(COMMERCIAL_SUITE_NODE_PRICE_PENCE, 300_000)
        self.assertNotEqual(COMMERCIAL_SUITE_NODE_PRICE_PENCE, PRICE_PENCE)
        self.assertNotEqual(COMMERCIAL_SUITE_NODE_PRICE_PENCE, PRICE_YEARLY_PENCE)
        body = build_commercial_suite_checkout_form_body(
            success_url="https://example.test/service?paid=1",
            cancel_url="https://example.test/service?pay_error=cancelled",
        )
        fields = urllib.parse.parse_qs(body.decode("utf-8"))
        self.assertEqual(fields["mode"], ["payment"])
        self.assertEqual(
            fields["line_items[0][price_data][unit_amount]"],
            ["300000"],
        )
        self.assertEqual(fields["line_items[0][price_data][currency]"], ["gbp"])
        self.assertEqual(fields["metadata[billing]"], ["one_time"])
        self.assertNotIn("recurring", body.decode("utf-8"))
        self.assertNotIn("subscription_data", body.decode("utf-8"))
        self.assertIn("deposit", COMMERCIAL_SUITE_PRODUCT_NAME.lower())
        desc = fields["line_items[0][price_data][product_data][description]"][0]
        self.assertIn("deposit", desc.lower())
        self.assertIn("3000", desc)


if __name__ == "__main__":
    unittest.main()
