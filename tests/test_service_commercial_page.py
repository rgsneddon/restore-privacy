"""Service main-nav page: commercial Suite licence + one-time £3000 Stripe."""

from __future__ import annotations

import json
import sys
import unittest
import urllib.parse
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "status_page"))


class TestServiceNav(unittest.TestCase):
    def test_main_nav_includes_service_control(self) -> None:
        from public_chrome import (
            SERVICE_LINK_ID,
            SERVICE_PATH,
            public_brand_header_html,
            public_nav_links_html,
        )

        nav = public_nav_links_html()
        self.assertIn('data-site-nav="1"', nav)
        self.assertIn(f'id="{SERVICE_LINK_ID}"', nav)
        self.assertIn(f'href="{SERVICE_PATH}"', nav)
        self.assertIn("SERVICE", nav)
        # Active marker when on service page header
        header = public_brand_header_html(active="service")
        self.assertIn(f'id="{SERVICE_LINK_ID}"', header)
        self.assertIn("is-active", header)
        # Relative order: Home then Settings then Service
        i_home = nav.index("home-link")
        i_settings = nav.index("settings-guide-link")
        i_service = nav.index(SERVICE_LINK_ID)
        self.assertLess(i_home, i_settings)
        self.assertLess(i_settings, i_service)


class TestServicePageLayoutAndCopy(unittest.TestCase):
    def test_service_page_intro_dual_box_and_commercial_substance(self) -> None:
        from payments import (
            COMMERCIAL_SUITE_CHECKOUT_PATH,
            COMMERCIAL_SUITE_NODE_PRICE_LABEL,
            COMMERCIAL_SUITE_NODE_PRICE_PENCE,
            COMMERCIAL_SUITE_PRODUCT_KEY,
        )
        from service_commercial import (
            SERVICE_COMMERCIAL_BOX_ID,
            SERVICE_COMPANION_BOX_ID,
            SERVICE_INTRO_HEADING,
            SERVICE_PAGE_ID,
            SERVICE_PAY_BUTTON_ID,
            SERVICE_PAY_FORM_ID,
            SERVICE_PATH,
            SERVICE_SHOP_ROW_ID,
            render_service_page_html,
        )

        raw = render_service_page_html()
        html = raw.decode("utf-8")
        self.assertIsInstance(raw, (bytes, bytearray))
        self.assertIn(f'data-page="service"', html)
        self.assertIn(f'id="{SERVICE_PAGE_ID}"', html)
        # Intro heading matches homepage phrase
        self.assertEqual(SERVICE_INTRO_HEADING, "Privacy you can actually use")
        self.assertIn(SERVICE_INTRO_HEADING, html)
        self.assertIn("Privacy you can actually use", html)
        # Dual half-width shop row (homepage pattern)
        self.assertIn(f'id="{SERVICE_SHOP_ROW_ID}"', html)
        self.assertIn('data-home-shop-row="1"', html)
        self.assertIn('data-layout="two-halves"', html)
        self.assertIn("grid-template-columns: 1fr 1fr", html)
        # Left commercial box
        self.assertIn(f'id="{SERVICE_COMMERCIAL_BOX_ID}"', html)
        self.assertIn('data-service-commercial="1"', html)
        self.assertIn(f'data-price-pence="{COMMERCIAL_SUITE_NODE_PRICE_PENCE}"', html)
        self.assertIn('data-billing="one_time"', html)
        body_low = html.lower()
        # Commercial substance + deposit framing (not KEYGEN-only)
        for needle in (
            "deposit",
            "business package",
            "sdk",
            "branding",
            "accounting",
            "residual node",
            "raskul",
            "rpos",
            "audit",
            "evolve",
            "costs may be higher",
            "3000",
        ):
            self.assertIn(needle, body_low, msg=needle)
        self.assertIn(COMMERCIAL_SUITE_NODE_PRICE_LABEL, html)
        self.assertIn(f"{COMMERCIAL_SUITE_NODE_PRICE_LABEL} deposit", html)
        self.assertIn("data-commercial-deposit", html)
        # Pay control in left box
        i_left = html.index(f'id="{SERVICE_COMMERCIAL_BOX_ID}"')
        i_right = html.index(f'id="{SERVICE_COMPANION_BOX_ID}"')
        i_form = html.index(f'id="{SERVICE_PAY_FORM_ID}"')
        i_btn = html.index(f'id="{SERVICE_PAY_BUTTON_ID}"')
        self.assertLess(i_left, i_form)
        self.assertLess(i_form, i_right)
        self.assertLess(i_btn, i_right)
        self.assertIn(f'action="{COMMERCIAL_SUITE_CHECKOUT_PATH}"', html)
        self.assertIn(f'value="{COMMERCIAL_SUITE_PRODUCT_KEY}"', html)
        self.assertIn(f'value="{COMMERCIAL_SUITE_NODE_PRICE_PENCE}"', html)
        # Monthly KEYGEN is companion only — not the sole left-box offer
        self.assertIn("Monthly KEYGEN", html)
        self.assertIn(f'id="{SERVICE_COMPANION_BOX_ID}"', html)
        # Service path constant
        self.assertEqual(SERVICE_PATH, "/service")

    def test_service_path_constant_matches_nav(self) -> None:
        from public_chrome import SERVICE_PATH as NAV_PATH
        from service_commercial import SERVICE_PATH as PAGE_PATH

        self.assertEqual(NAV_PATH, PAGE_PATH)
        self.assertEqual(PAGE_PATH, "/service")


class TestCommercialSuiteOneTimeCheckout(unittest.TestCase):
    def test_build_body_is_one_time_3000_gbp(self) -> None:
        from payments import (
            COMMERCIAL_SUITE_NODE_PRICE_PENCE,
            COMMERCIAL_SUITE_PRODUCT_KEY,
            COMMERCIAL_SUITE_PRODUCT_NAME,
            PRICE_PENCE,
            build_commercial_suite_checkout_form_body,
        )

        self.assertEqual(COMMERCIAL_SUITE_NODE_PRICE_PENCE, 300_000)
        self.assertNotEqual(COMMERCIAL_SUITE_NODE_PRICE_PENCE, PRICE_PENCE)
        body = build_commercial_suite_checkout_form_body(
            success_url="https://example.test/service?paid=1",
            cancel_url="https://example.test/service?pay_error=cancelled",
        )
        fields = urllib.parse.parse_qs(body.decode("utf-8"))
        self.assertEqual(fields["mode"], ["payment"])
        self.assertNotIn("subscription", fields.get("mode", []))
        self.assertEqual(
            fields["line_items[0][price_data][unit_amount]"],
            [str(COMMERCIAL_SUITE_NODE_PRICE_PENCE)],
        )
        self.assertEqual(fields["line_items[0][price_data][currency]"], ["gbp"])
        self.assertEqual(fields["metadata[amount_pence]"], ["300000"])
        self.assertEqual(fields["metadata[billing]"], ["one_time"])
        self.assertEqual(fields["metadata[product]"], [COMMERCIAL_SUITE_PRODUCT_KEY])
        self.assertEqual(
            fields["line_items[0][price_data][product_data][name]"],
            [COMMERCIAL_SUITE_PRODUCT_NAME],
        )
        # Stripe line item must frame £3000 as a deposit
        self.assertIn("deposit", COMMERCIAL_SUITE_PRODUCT_NAME.lower())
        desc = fields["line_items[0][price_data][product_data][description]"][0]
        self.assertIn("deposit", desc.lower())
        self.assertIn("3000", desc)
        # Must not look like monthly KEYGEN subscription body
        joined = body.decode("utf-8")
        self.assertNotIn("recurring", joined)
        self.assertNotIn("subscription_data", joined)

    def test_create_session_uses_shipped_builder_and_amount(self) -> None:
        from payments import (
            COMMERCIAL_SUITE_NODE_PRICE_PENCE,
            create_commercial_suite_checkout_session,
        )

        captured: dict = {}

        def fake_post(url: str, headers: dict, body: bytes):
            captured["url"] = url
            captured["body"] = body
            captured["headers"] = headers
            payload = {
                "id": "cs_test_commercial_1",
                "url": "https://checkout.stripe.com/c/pay/cs_test_commercial_1",
            }
            return 200, json.dumps(payload).encode("utf-8")

        with mock.patch.dict(
            "os.environ",
            {"STRIPE_SECRET_KEY": "sk_test_fake_commercial"},
            clear=False,
        ):
            session = create_commercial_suite_checkout_session(
                base_url="https://restoreprivacy.online",
                http_post=fake_post,
            )
        self.assertEqual(session["mode"], "payment")
        self.assertEqual(session["amount_pence"], COMMERCIAL_SUITE_NODE_PRICE_PENCE)
        self.assertEqual(session["currency"], "gbp")
        self.assertEqual(session["billing"], "one_time")
        self.assertIn("checkout.stripe.com", session["url"])
        fields = urllib.parse.parse_qs(captured["body"].decode("utf-8"))
        self.assertEqual(fields["mode"], ["payment"])
        self.assertEqual(
            fields["line_items[0][price_data][unit_amount]"],
            ["300000"],
        )
        self.assertEqual(captured["url"], "https://api.stripe.com/v1/checkout/sessions")

    def test_pay_control_wired_in_left_box_markup(self) -> None:
        """Pay form lives inside commercial left box with correct path + amount."""
        from payments import (
            COMMERCIAL_SUITE_CHECKOUT_PATH,
            COMMERCIAL_SUITE_NODE_PRICE_PENCE,
        )
        from service_commercial import (
            SERVICE_COMMERCIAL_BOX_ID,
            SERVICE_PAY_BUTTON_ID,
            render_service_commercial_box_html,
        )

        box = render_service_commercial_box_html()
        self.assertIn(f'id="{SERVICE_COMMERCIAL_BOX_ID}"', box)
        self.assertIn(f'action="{COMMERCIAL_SUITE_CHECKOUT_PATH}"', box)
        self.assertIn(f'data-price-pence="{COMMERCIAL_SUITE_NODE_PRICE_PENCE}"', box)
        self.assertIn(f'id="{SERVICE_PAY_BUTTON_ID}"', box)
        self.assertIn('data-billing="one_time"', box)
        self.assertIn("one-time", box.lower())


if __name__ == "__main__":
    unittest.main()
