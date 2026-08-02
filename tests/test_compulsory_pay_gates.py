"""Compulsory KEYGEN trial for brand assets + compulsory £3000 Business deposit.

Drives the shipped gate functions (brand_asset_gate) and payment helpers —
not re-implementations. Unpaid brand delivery deny; entitled/token allow;
Business-Class without £3000 deposit deny.
"""

from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "status_page"))
sys.path.insert(0, str(ROOT))


class TestBrandPackageKeygenGate(unittest.TestCase):
    def test_pure_deny_without_proof_redirects_to_pay(self) -> None:
        from brand_asset_gate import (
            brand_package_access_decision,
            keygen_pay_redirect_url,
        )

        d = brand_package_access_decision(
            next_path="/suite/download?platform=macos",
            platform="macos",
        )
        self.assertFalse(d["allow"])
        self.assertEqual(d["reason"], "keygen_trial_required")
        self.assertEqual(d["http_status"], 302)
        self.assertIsNotNone(d["redirect"])
        assert d["redirect"] is not None
        self.assertTrue(d["redirect"].startswith("/pay"))
        self.assertIn("product=suite", d["redirect"])
        self.assertIn("next=", d["redirect"])
        # Redirect helper itself
        redir = keygen_pay_redirect_url(
            next_path="/suite/download?platform=windows", platform="windows"
        )
        self.assertIn("/pay?", redir)
        self.assertIn("platform=windows", redir)

    def test_allow_with_session_or_keygen_or_token_flags(self) -> None:
        from brand_asset_gate import brand_package_access_decision

        for kwargs, reason in (
            ({"has_valid_download_token": True}, "download_token"),
            ({"session_entitlement_allows": True}, "session_entitlement"),
            ({"keygen_entitlement_allows": True}, "keygen_entitlement"),
        ):
            d = brand_package_access_decision(**kwargs)
            self.assertTrue(d["allow"], msg=kwargs)
            self.assertEqual(d["reason"], reason)
            self.assertIsNone(d["redirect"])

    def test_evaluate_uses_real_lookup_download_token(self) -> None:
        from brand_asset_gate import evaluate_brand_package_request
        import payments

        with tempfile.TemporaryDirectory() as td:
            db = Path(td) / "pay.db"
            with mock.patch.object(payments, "db_path", return_value=db):
                payments.init_db()
                # No token / session → deny
                deny = evaluate_brand_package_request(
                    next_path="/suite/download?platform=linux",
                    platform="linux",
                )
                self.assertFalse(deny["allow"])
                self.assertEqual(deny["reason"], "keygen_trial_required")

                # Mint real grant via shipped mint_download_token
                tok = payments.mint_download_token(
                    filename=payments.platform_filename("linux") or "",
                    platform="linux",
                    session_id="cs_test_gate_1",
                )
                allow = evaluate_brand_package_request(
                    token=tok,
                    platform="linux",
                    next_path="/suite/download?platform=linux",
                )
                self.assertTrue(allow["allow"], allow)
                self.assertEqual(allow["reason"], "download_token")

                # Active session entitlement (shipped activate_connect_entitlement)
                import time as _time

                payments.activate_connect_entitlement(
                    "cs_test_gate_sess",
                    platform="macos",
                    valid_until=_time.time() + 86400 * 3,
                    billing_interval="month",
                    product_line="suite",
                )
                self.assertTrue(
                    payments.connect_entitlement_allows("cs_test_gate_sess"),
                    payments.get_connect_entitlement("cs_test_gate_sess"),
                )
                sess_allow = evaluate_brand_package_request(
                    session_id="cs_test_gate_sess",
                    platform="macos",
                )
                self.assertTrue(sess_allow["allow"], sess_allow)
                self.assertEqual(sess_allow["reason"], "session_entitlement")

    def test_is_brand_asset_delivery_path(self) -> None:
        from brand_asset_gate import is_brand_asset_delivery_path

        self.assertTrue(is_brand_asset_delivery_path("/suite/download"))
        self.assertTrue(is_brand_asset_delivery_path("/suite/download/"))
        self.assertTrue(
            is_brand_asset_delivery_path("/assets/1.0.2/restore-privacy-rx-browser-1.0.2.zip")
        )
        self.assertFalse(is_brand_asset_delivery_path("/pay"))
        self.assertFalse(is_brand_asset_delivery_path("/"))


class TestBusinessDepositGate(unittest.TestCase):
    def test_exactly_3000_gbp_required(self) -> None:
        from brand_asset_gate import (
            REQUIRED_BUSINESS_DEPOSIT_PENCE,
            commercial_checkout_session_allowed,
            commercial_deposit_amount_ok,
            commercial_deposit_gate,
        )
        from payments import (
            COMMERCIAL_SUITE_NODE_PRICE_PENCE,
            COMMERCIAL_SUITE_PRODUCT_KEY,
            COMMERCIAL_SUITE_PRODUCT_LINE,
        )

        self.assertEqual(REQUIRED_BUSINESS_DEPOSIT_PENCE, 300_000)
        self.assertEqual(COMMERCIAL_SUITE_NODE_PRICE_PENCE, 300_000)
        self.assertTrue(commercial_deposit_amount_ok(300_000))
        self.assertTrue(commercial_deposit_amount_ok("300000"))
        self.assertFalse(commercial_deposit_amount_ok(3000))
        self.assertFalse(commercial_deposit_amount_ok(300))
        self.assertFalse(commercial_deposit_amount_ok(0))
        self.assertFalse(commercial_deposit_amount_ok(None))
        self.assertFalse(commercial_deposit_amount_ok("nope"))

        ok = commercial_deposit_gate(
            amount_pence=COMMERCIAL_SUITE_NODE_PRICE_PENCE,
            product=COMMERCIAL_SUITE_PRODUCT_KEY,
            product_line=COMMERCIAL_SUITE_PRODUCT_LINE,
            mode="payment",
            billing="one_time",
        )
        self.assertTrue(ok["allow"], ok)
        self.assertEqual(ok["required_pence"], 300_000)

        bad_amt = commercial_deposit_gate(
            amount_pence=300,
            product=COMMERCIAL_SUITE_PRODUCT_KEY,
            product_line=COMMERCIAL_SUITE_PRODUCT_LINE,
            mode="payment",
        )
        self.assertFalse(bad_amt["allow"])
        self.assertIn("3000", bad_amt["reason"])

        bad_prod = commercial_deposit_gate(
            amount_pence=300_000,
            product="suite",
            product_line="vpn",
            mode="payment",
        )
        self.assertFalse(bad_prod["allow"])

        bad_mode = commercial_deposit_gate(
            amount_pence=300_000,
            product=COMMERCIAL_SUITE_PRODUCT_KEY,
            product_line=COMMERCIAL_SUITE_PRODUCT_LINE,
            mode="subscription",
        )
        self.assertFalse(bad_mode["allow"])

        sess_ok = commercial_checkout_session_allowed(
            {
                "amount_pence": 300_000,
                "product": COMMERCIAL_SUITE_PRODUCT_KEY,
                "product_line": COMMERCIAL_SUITE_PRODUCT_LINE,
                "mode": "payment",
                "billing": "one_time",
            }
        )
        self.assertTrue(sess_ok["allow"], sess_ok)

        sess_bad = commercial_checkout_session_allowed(
            {
                "amount_pence": 3000,
                "product": "suite",
                "mode": "subscription",
            }
        )
        self.assertFalse(sess_bad["allow"])

    def test_build_commercial_checkout_body_pins_300000(self) -> None:
        from payments import (
            COMMERCIAL_SUITE_NODE_PRICE_PENCE,
            COMMERCIAL_SUITE_PRODUCT_KEY,
            build_commercial_suite_checkout_form_body,
        )
        import urllib.parse

        raw = build_commercial_suite_checkout_form_body(
            success_url="https://example.com/ok",
            cancel_url="https://example.com/cancel",
        )
        fields = urllib.parse.parse_qs(raw.decode("utf-8"))
        self.assertEqual(fields.get("mode"), ["payment"])
        self.assertEqual(
            fields.get("line_items[0][price_data][unit_amount]"),
            [str(COMMERCIAL_SUITE_NODE_PRICE_PENCE)],
        )
        self.assertEqual(fields.get("client_reference_id"), [COMMERCIAL_SUITE_PRODUCT_KEY])
        self.assertEqual(fields.get("metadata[amount_pence]"), ["300000"])
        # Gate the body-equivalent session shape
        from brand_asset_gate import commercial_checkout_session_allowed

        gate = commercial_checkout_session_allowed(
            {
                "amount_pence": int(
                    fields["line_items[0][price_data][unit_amount]"][0]
                ),
                "product": fields["client_reference_id"][0],
                "product_line": fields["metadata[product_line]"][0],
                "mode": fields["mode"][0],
                "billing": fields["metadata[billing]"][0],
            }
        )
        self.assertTrue(gate["allow"], gate)


class TestStorefrontCopyCompulsory(unittest.TestCase):
    def test_suite_and_service_copy_require_trial_and_deposit(self) -> None:
        from downloads import (
            NODE_PREFERENCE_DEPOSIT_LABEL,
            NODE_PREFERENCE_HEADING,
            SUITE_KEYGEN_HINT,
            SUITE_PRODUCT_SUBTITLE,
            render_node_preference_html,
            render_suite_storefront_html,
        )
        from service_commercial import render_service_page_html

        # Retired suite-keygen-line copy is empty / not rendered
        self.assertEqual(SUITE_KEYGEN_HINT, "")
        self.assertIn("trial", SUITE_PRODUCT_SUBTITLE.lower())
        self.assertIn("KEYGEN", SUITE_PRODUCT_SUBTITLE)
        self.assertIn("3000", NODE_PREFERENCE_DEPOSIT_LABEL)
        self.assertIn("deposit", NODE_PREFERENCE_HEADING.lower())

        suite = render_suite_storefront_html()
        self.assertIn("KEYGEN", suite)
        self.assertIn("trial", suite.lower())
        self.assertIn("suite-keygen-buy", suite)
        self.assertIn("free trial", suite.lower())
        self.assertIn('id="suite-storefront"', suite)
        # Retired KEYGEN licence/trial hint line removed from left box
        self.assertNotIn("Brand installers require a KEYGEN licence first", suite)
        self.assertNotIn('id="suite-keygen-line"', suite)
        self.assertNotIn("suite-keygen-line", suite)
        # Left-box pay-hint: new trial/checkout copy (no Business-Class £3000 line)
        i_hint = suite.index('id="suite-pay-hint"')
        hint = suite[i_hint : i_hint + 700]
        self.assertIn("To start your 3-day free trial", hint)
        self.assertIn("payment details and email address", hint)
        self.assertIn("no money is deducted from your card", hint)
        self.assertIn("download links which you receive via email", hint)
        self.assertIn("Yearly plans available (17% discount)", hint)
        self.assertNotIn("installers refuse anonymous download", hint)
        self.assertNotIn("session_id / token from thank-you", hint)
        self.assertNotIn("client box below", hint)
        self.assertNotIn("£3000", hint)
        self.assertNotIn("Business-Class", hint)
        self.assertNotIn("3000", suite)  # deposit no longer in storefront hint
        # Distinctive retired mid-phrase must not appear in storefront either
        self.assertNotIn(
            "no money is taken until after the trial ends", suite.lower()
        )
        # Pure helper still builds commercial deposit markup (not on homepage)
        home_biz = render_node_preference_html()
        self.assertIn("£3000", home_biz)
        self.assertIn("deposit", home_biz.lower())
        self.assertIn("data-commercial-deposit", home_biz)

        svc = render_service_page_html().decode("utf-8")
        self.assertIn("£3000", svc)
        self.assertIn("deposit", svc.lower())
        self.assertIn("300000", svc)  # pence in form
        self.assertIn("required", svc.lower())
    def test_handler_wires_brand_package_gate(self) -> None:
        """Structural: suite download + assets + commercial use brand_asset_gate."""
        app_src = (ROOT / "status_page" / "app.py").read_text(encoding="utf-8")
        self.assertIn("_brand_package_gate", app_src)
        self.assertIn("evaluate_brand_package_request", app_src)
        self.assertIn("commercial_deposit_gate", app_src)
        self.assertIn("commercial_checkout_session_allowed", app_src)
        self.assertIn("X-RPT-Brand-Gate", app_src)
        gate_src = (ROOT / "status_page" / "brand_asset_gate.py").read_text(
            encoding="utf-8"
        )
        self.assertIn("keygen_trial_required", gate_src)
        self.assertIn("300_000", gate_src)
        self.assertIn("REQUIRED_BUSINESS_DEPOSIT_PENCE", gate_src)


class TestClientLicenceMentionsCompulsory(unittest.TestCase):
    def test_short_licence_summary_mentions_trial_and_deposit(self) -> None:
        sys.path.insert(0, str(ROOT))
        from client.licence_gate import short_licence_summary

        text = short_licence_summary()
        self.assertIn("KEYGEN", text.upper() or text)
        self.assertIn("3-day", text)
        self.assertIn("3000", text)


if __name__ == "__main__":
    unittest.main()
