"""Stripe Checkout custom domain DNS helpers + session host checks.

Drives payments.stripe_custom_domain_dns_expected and related pure helpers.
"""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "status_page"))


class TestCustomDomainDnsExpected(unittest.TestCase):
    def test_expected_records_for_pay_subdomain(self):
        from payments import (
            STRIPE_CUSTOM_DOMAIN,
            STRIPE_CUSTOM_DOMAIN_CNAME_TARGET,
            stripe_custom_domain_dns_expected,
        )

        exp = stripe_custom_domain_dns_expected()
        self.assertEqual(exp["domain"], "pay.restoreprivacy.online")
        self.assertEqual(exp["domain"], STRIPE_CUSTOM_DOMAIN)
        self.assertEqual(exp["cname"]["host"], "pay")
        self.assertEqual(exp["cname"]["value"], STRIPE_CUSTOM_DOMAIN_CNAME_TARGET)
        self.assertEqual(exp["cname"]["value"], "hosted-checkout.stripecdn.com")
        self.assertEqual(exp["txt"]["host"], "_acme-challenge.pay")
        self.assertEqual(
            exp["txt"]["fqdn"], "_acme-challenge.pay.restoreprivacy.online"
        )
        self.assertIsNone(exp["txt"]["value"])  # Dashboard-only
        self.assertTrue(exp["paid_feature"])
        self.assertEqual(exp["approx_monthly_usd"], 10)

    def test_session_url_host_helpers(self):
        from payments import (
            checkout_session_url_host,
            checkout_session_uses_custom_domain,
        )

        self.assertEqual(
            checkout_session_url_host(
                "https://pay.restoreprivacy.online/c/pay/cs_test_x"
            ),
            "pay.restoreprivacy.online",
        )
        self.assertTrue(
            checkout_session_uses_custom_domain(
                "https://pay.restoreprivacy.online/c/pay/cs_live_abc"
            )
        )
        self.assertFalse(
            checkout_session_uses_custom_domain(
                "https://checkout.stripe.com/c/pay/cs_live_abc"
            )
        )
        self.assertEqual(checkout_session_url_host(""), "")

    def test_verify_dns_with_injected_dig(self):
        from payments import verify_stripe_custom_domain_dns

        def fake_dig(args: list[str]) -> str:
            if "TXT" in args:
                return '"abcdef0123456789tokenvaluefromstripe"'
            return "hosted-checkout.stripecdn.com."

        ok = verify_stripe_custom_domain_dns(dig_runner=fake_dig)
        self.assertTrue(ok["ok"], ok)
        self.assertTrue(ok["cname_ok"])
        self.assertTrue(ok["txt_ok"])

        def empty_dig(args: list[str]) -> str:
            return ""

        bad = verify_stripe_custom_domain_dns(dig_runner=empty_dig)
        self.assertFalse(bad["ok"])
        self.assertTrue(any("cname" in m for m in bad["mismatches"]))

    def test_guide_includes_dns_expected(self):
        from payments import stripe_checkout_branding_guide

        g = stripe_checkout_branding_guide()
        cd = g["custom_domains"]
        self.assertEqual(cd["domain"], "pay.restoreprivacy.online")
        self.assertEqual(cd["cname_target"], "hosted-checkout.stripecdn.com")
        self.assertIn("dns_expected", cd)
        self.assertTrue(cd["server_side_redirect_required"])

    def test_verify_script_exists(self):
        script = ROOT / "scripts" / "verify_stripe_custom_domain.py"
        self.assertTrue(script.is_file())
        src = script.read_text(encoding="utf-8")
        self.assertIn("verify_stripe_custom_domain_dns", src)
        self.assertIn("create_subscription_checkout_session", src)
        self.assertIn("pay.restoreprivacy.online", src)

    def test_operator_doc_has_namecheap_table(self):
        doc = ROOT / "docs" / "STRIPE_CUSTOM_DOMAINS_AND_BRANDING.md"
        text = doc.read_text(encoding="utf-8")
        self.assertIn("hosted-checkout.stripecdn.com", text)
        self.assertIn("_acme-challenge.pay", text)
        self.assertIn("Namecheap", text)
        self.assertIn("verify_stripe_custom_domain.py", text)


if __name__ == "__main__":
    unittest.main()
