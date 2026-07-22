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
    def test_desired_fields_245_monthly_7day(self):
        from payments import (
            DEFAULT_STRIPE_PAYMENT_LINK_ID,
            PRICE_PENCE,
            desired_payment_link_trial_fields,
            payment_link_matches_trial_subscription,
        )

        d = desired_payment_link_trial_fields()
        self.assertEqual(d["unit_amount_pence"], PRICE_PENCE)
        self.assertEqual(d["unit_amount_pence"], 245)
        self.assertEqual(d["currency"], "gbp")
        self.assertEqual(d["recurring_interval"], "month")
        self.assertEqual(d["trial_period_days"], 7)
        self.assertEqual(d["mode"], "subscription")
        self.assertEqual(d["payment_link_id"], DEFAULT_STRIPE_PAYMENT_LINK_ID)
        self.assertIn("7 day trial", d["homepage_trial_sentence"])

        ok = payment_link_matches_trial_subscription(
            {
                "id": "price_test",
                "currency": "gbp",
                "unit_amount": 245,
                "type": "recurring",
                "recurring": {"interval": "month"},
                "payment_link_trial_period_days": 7,
            }
        )
        self.assertTrue(ok["ok"], ok)
        bad = payment_link_matches_trial_subscription(
            {
                "currency": "gbp",
                "unit_amount": 245,
                "recurring": {"interval": "month"},
                # no trial
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
        self.assertIn("7 day", text.lower().replace("-", " "))
        self.assertIn("plink_1TvTu6JDavQ2TJW6FeL0dIh9", text)
        self.assertIn("set_render_fulfilment_smtp.ps1", text)


if __name__ == "__main__":
    unittest.main()
