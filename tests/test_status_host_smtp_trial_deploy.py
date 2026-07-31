"""Deploy config: SMTP env keys, render.yaml blueprint, trial field helpers.

Drives shipped `payments.fulfilment_smtp_*` and `desired_payment_link_trial_fields`
— not re-implemented oracles.
"""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "status_page"))


class TestFulfilmentSmtpEnvKeys(unittest.TestCase):
    def test_keys_match_config_reader_and_render_yaml(self):
        from payments import fulfilment_smtp_config, fulfilment_smtp_env_keys

        keys = fulfilment_smtp_env_keys()
        self.assertEqual(
            keys,
            [
                "RPT_FULFILMENT_SMTP_HOST",
                "RPT_FULFILMENT_SMTP_PORT",
                "RPT_FULFILMENT_SMTP_USER",
                "RPT_FULFILMENT_SMTP_PASSWORD",
                "RPT_FULFILMENT_FROM_EMAIL",
                "RPT_FULFILMENT_SMTP_TLS",
            ],
        )
        cfg = fulfilment_smtp_config()
        self.assertEqual(cfg["env_keys"], keys)
        # Defaults without host → not configured
        self.assertFalse(cfg["configured"])
        self.assertEqual(cfg["port"], 587)
        self.assertTrue(cfg["use_tls"])

        ry = (ROOT / "render.yaml").read_text(encoding="utf-8")
        for k in keys:
            self.assertIn(k, ry, f"{k} missing from render.yaml")
        self.assertIn("sync: false", ry)
        self.assertIn("noreply@restoreprivacy.online", ry)

    def test_processor_plugin_lists_smtp_vars(self):
        from processor_plugins import STRIPE_PLUGIN

        var_keys = {v.key for v in STRIPE_PLUGIN.variables}
        for k in (
            "RPT_FULFILMENT_SMTP_HOST",
            "RPT_FULFILMENT_SMTP_PASSWORD",
            "RPT_FULFILMENT_FROM_EMAIL",
        ):
            self.assertIn(k, var_keys)


class TestPaymentLinkTrialHelpers(unittest.TestCase):
    def test_desired_fields_300_monthly_with_3day_trial(self):
        from payments import (
            DEFAULT_STRIPE_PAYMENT_LINK_ID,
            DEFAULT_STRIPE_PAYMENT_PAGE_URL_YEARLY,
            PRICE_PENCE,
            desired_payment_link_trial_fields,
            payment_link_matches_trial_subscription,
        )

        d = desired_payment_link_trial_fields()
        self.assertEqual(d["unit_amount_pence"], PRICE_PENCE)
        self.assertEqual(d["unit_amount_pence"], 300)
        self.assertEqual(d["currency"], "gbp")
        self.assertEqual(d["recurring_interval"], "month")
        self.assertEqual(d["trial_period_days"], 3)
        self.assertNotEqual(d["trial_period_days"], 0)
        self.assertNotEqual(d["trial_period_days"], 7)
        self.assertEqual(d["mode"], "subscription")
        self.assertEqual(d["payment_link_id"], DEFAULT_STRIPE_PAYMENT_LINK_ID)
        self.assertEqual(d["unit_amount_yearly_pence"], 3000)
        self.assertIn("/pay", d["payment_page_url"])
        self.assertIn("3-day free trial", d["homepage_trial_sentence"].lower())
        self.assertIn("no money is taken until after the trial ends", d["homepage_trial_sentence"].lower())
        self.assertNotIn("7 day trial", d["homepage_trial_sentence"].lower())
        self.assertNotIn("subscription starts when you pay", d["homepage_trial_sentence"].lower())

        # Trial=3 on payment_link_trial_period_days matches
        ok_three = payment_link_matches_trial_subscription(
            {
                "id": "price_test",
                "currency": "gbp",
                "unit_amount": 300,
                "type": "recurring",
                "recurring": {"interval": "month"},
                "payment_link_trial_period_days": 3,
            }
        )
        self.assertTrue(ok_three["ok"], ok_three)
        # Missing trial mismatches when want=3
        missing = payment_link_matches_trial_subscription(
            {
                "currency": "gbp",
                "unit_amount": 300,
                "recurring": {"interval": "month"},
            }
        )
        self.assertFalse(missing["ok"])
        # 7-day trial is explicitly rejected
        bad = payment_link_matches_trial_subscription(
            {
                "currency": "gbp",
                "unit_amount": 300,
                "recurring": {"interval": "month"},
                "payment_link_trial_period_days": 7,
            }
        )
        self.assertFalse(bad["ok"])
        self.assertTrue(any("trial" in m for m in bad["mismatches"]))

    def test_configure_script_exists_and_imports_helpers(self):
        script = ROOT / "scripts" / "configure_stripe_payment_link_trial.py"
        self.assertTrue(script.is_file())
        src = script.read_text(encoding="utf-8")
        self.assertIn("desired_payment_link_trial_fields", src)
        self.assertIn("trial_period_days", src)
        self.assertIn("PRICE_PENCE", src)
        self.assertIn("unit_amount_pence", src)
        self.assertIn("3-day trial", src.lower())
        self.assertIn("trial_period_days", src)
        self.assertIn("year", src.lower())
        # Live catalog policy is trial=3 — must not ship dual "no trial" operator steps
        self.assertNotIn("charges with no free trial", src.lower())
        self.assertNotIn("confirm checkout charges with no free trial", src.lower())
        # Nicknames / dashboard_steps may mention "3-day trial via Checkout"; ban bare no-trial policy
        for banned in (
            "no free trial",
            "set trial period = none",
            "trial period = none / 0 days",
            "clears free-trial",
        ):
            self.assertNotIn(banned, src.lower(), msg=f"configure script still has {banned!r}")
        smtp_script = ROOT / "scripts" / "set_render_fulfilment_smtp.ps1"
        self.assertTrue(smtp_script.is_file())
        ps = smtp_script.read_text(encoding="utf-8")
        self.assertIn("RPT_FULFILMENT_SMTP_HOST", ps)
        self.assertIn("RENDER_API_KEY", ps)


class TestDeployDocs(unittest.TestCase):
    def test_operator_doc_present(self):
        doc = ROOT / "docs" / "STATUS_HOST_SMTP_AND_TRIAL.md"
        self.assertTrue(doc.is_file())
        text = doc.read_text(encoding="utf-8")
        self.assertIn("RPT_FULFILMENT_SMTP_HOST", text)
        self.assertIn("Monthly VPN plan", text)
        self.assertIn("Yearly VPN plan", text)
        self.assertIn("3000", text)
        self.assertIn("£30.00", text)
        self.assertIn("/pay", text)
        self.assertIn("set_render_fulfilment_smtp.ps1", text)
        self.assertNotIn("£29.40", text)
        self.assertNotIn("unit_amount: 2940", text)
        self.assertIn("3-day free trial", text.lower())
        self.assertIn("trial_period_days", text)


if __name__ == "__main__":
    unittest.main()
