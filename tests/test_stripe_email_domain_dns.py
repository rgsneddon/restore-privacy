"""Stripe custom email domain + DMARC helpers (structure, parse, verify)."""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "status_page"))


class TestDmarcPolicy(unittest.TestCase):
    def test_shipped_policy_shape(self):
        from payments import (
            DMARC_POLICY_VALUE,
            dmarc_policy_expected,
            parse_dmarc_policy,
        )

        exp = dmarc_policy_expected()
        self.assertEqual(exp["host"], "_dmarc")
        self.assertEqual(exp["fqdn"], "_dmarc.restoreprivacy.online")
        self.assertEqual(exp["value"], DMARC_POLICY_VALUE)
        self.assertTrue(DMARC_POLICY_VALUE.startswith("v=DMARC1"))
        self.assertIn("p=none", DMARC_POLICY_VALUE)
        self.assertNotIn("aspf=s", DMARC_POLICY_VALUE.lower())

        parsed = parse_dmarc_policy(DMARC_POLICY_VALUE)
        self.assertTrue(parsed["ok"], parsed)
        self.assertTrue(parsed["v_ok"])
        self.assertTrue(parsed["p_ok"])
        self.assertEqual(parsed["p"], "none")
        self.assertFalse(parsed["aspf_strict"])

    def test_parse_rejects_aspf_strict(self):
        from payments import parse_dmarc_policy

        bad = parse_dmarc_policy("v=DMARC1; p=none; aspf=s")
        self.assertFalse(bad["ok"])
        self.assertTrue(bad["aspf_strict"])

    def test_parse_requires_p(self):
        from payments import parse_dmarc_policy

        bad = parse_dmarc_policy("v=DMARC1")
        self.assertFalse(bad["ok"])
        self.assertFalse(bad["p_ok"])


class TestEmailDomainExpected(unittest.TestCase):
    def test_categories_without_inventing_secrets(self):
        from payments import stripe_email_domain_dns_expected

        exp = stripe_email_domain_dns_expected()
        self.assertEqual(exp["zone"], "restoreprivacy.online")
        cats = {c["category"] for c in exp["categories"]}
        self.assertEqual(cats, {"ownership", "mail_from", "dkim"})
        for c in exp["categories"]:
            self.assertIsNone(c["value"])  # Dashboard-only
            self.assertIsNone(c["host"])
        self.assertTrue(exp["secrets_not_in_repo"])
        self.assertIn("privateemail", exp["existing_mail"]["spf"])
        self.assertIn("dns1.registrar-servers.com", exp["namecheap_ns"])
        # Checkout pay rows still in structure
        cd = exp["checkout_custom_domain"]
        self.assertEqual(cd["cname"]["host"], "pay")
        self.assertEqual(cd["txt"]["host"], "_acme-challenge.pay")

    def test_dashboard_records_pass_through(self):
        from payments import stripe_email_domain_dns_expected

        rows = [
            {
                "category": "ownership",
                "type": "TXT",
                "host": "stripe-verify",
                "value": "not-a-real-token",
            }
        ]
        exp = stripe_email_domain_dns_expected(dashboard_records=rows)
        self.assertEqual(len(exp["dashboard_records"]), 1)
        self.assertEqual(exp["dashboard_records"][0]["host"], "stripe-verify")


class TestVerifyWithInjectedDig(unittest.TestCase):
    def test_verify_dmarc_ok_and_missing(self):
        from payments import DMARC_POLICY_VALUE, verify_dmarc_dns

        def dig_ok(args: list[str]) -> str:
            if "TXT" in args and "_dmarc" in " ".join(args):
                return f'"{DMARC_POLICY_VALUE}"'
            return ""

        ok = verify_dmarc_dns(dig_runner=dig_ok)
        self.assertTrue(ok["ok"], ok)
        self.assertTrue(ok["published"])

        def dig_empty(args: list[str]) -> str:
            return ""

        bad = verify_dmarc_dns(dig_runner=dig_empty)
        self.assertFalse(bad["ok"])
        self.assertFalse(bad["published"])
        self.assertTrue(any("dmarc_missing" in m for m in bad["mismatches"]))

    def test_verify_email_domain_spf_and_dmarc(self):
        from payments import (
            DMARC_POLICY_VALUE,
            STRIPE_EMAIL_EXISTING_SPF,
            verify_stripe_email_domain_dns,
        )

        def dig(args: list[str]) -> str:
            joined = " ".join(args)
            if "_dmarc" in joined:
                return f'"{DMARC_POLICY_VALUE}"'
            if "TXT" in args and "restoreprivacy.online" in joined:
                return f'"{STRIPE_EMAIL_EXISTING_SPF}"'
            return ""

        rep = verify_stripe_email_domain_dns(dig_runner=dig)
        self.assertTrue(rep["dmarc"]["ok"], rep)
        self.assertTrue(rep["spf"]["ok"], rep)
        self.assertTrue(rep["ok"], rep)
        self.assertFalse(rep["stripe_verified_claim"])

    def test_verify_email_with_dashboard_cname_row(self):
        from payments import (
            DMARC_POLICY_VALUE,
            STRIPE_EMAIL_EXISTING_SPF,
            verify_stripe_email_domain_dns,
        )

        def dig(args: list[str]) -> str:
            joined = " ".join(args)
            if "CNAME" in args and "bounce" in joined:
                return "custom.stripe.com."
            if "_dmarc" in joined:
                return f'"{DMARC_POLICY_VALUE}"'
            if "TXT" in args and "restoreprivacy.online" in joined and "_dmarc" not in joined:
                return f'"{STRIPE_EMAIL_EXISTING_SPF}"'
            return ""

        rows = [
            {
                "category": "mail_from",
                "type": "CNAME",
                "host": "bounce",
                "value": "custom.stripe.com",
            }
        ]
        rep = verify_stripe_email_domain_dns(
            dig_runner=dig, dashboard_records=rows
        )
        self.assertTrue(rep["dashboard_record_checks"][0]["ok"], rep)
        self.assertTrue(rep["ok"], rep)


class TestScriptAndDocs(unittest.TestCase):
    def test_verify_script_exists(self):
        script = ROOT / "scripts" / "verify_stripe_email_domain_dns.py"
        self.assertTrue(script.is_file())
        src = script.read_text(encoding="utf-8")
        self.assertIn("verify_stripe_email_domain_dns", src)
        self.assertIn("DMARC_POLICY_VALUE", src)
        self.assertIn("_dmarc", src)

    def test_operator_doc_covers_email_dmarc_pay(self):
        doc = ROOT / "docs" / "STRIPE_CUSTOM_DOMAINS_AND_BRANDING.md"
        text = doc.read_text(encoding="utf-8")
        self.assertIn("_dmarc", text)
        self.assertIn("v=DMARC1", text)
        self.assertIn("p=none", text)
        self.assertIn("Customer emails", text)
        self.assertIn("ownership", text.lower())
        self.assertIn("DKIM", text)
        self.assertIn("Mail From", text)
        self.assertIn("pay", text)
        self.assertIn("_acme-challenge.pay", text)
        self.assertIn("registrar-servers.com", text)
        self.assertIn("Namecheap", text)
        self.assertIn("aspf=s", text)
        self.assertIn("verify_stripe_email_domain_dns.py", text)


if __name__ == "__main__":
    unittest.main()
