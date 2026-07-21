"""Processor connection plugins: catalog, admin detail, validate/apply."""

from __future__ import annotations

import os
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "status_page"))

import admin_panel  # noqa: E402
import payments  # noqa: E402
import processor_plugins as plugins  # noqa: E402


class TestProcessorPluginCatalog(unittest.TestCase):
    def test_registry_lists_stripe_and_bmc_with_correct_keys(self):
        reg = plugins.list_processor_plugins()
        ids = [p.id for p in reg]
        self.assertEqual(ids, ["stripe", "bmc"])
        catalog = plugins.plugin_variable_catalog()
        stripe_keys = {v["key"] for v in catalog["stripe"]}
        self.assertIn("STRIPE_SECRET_KEY", stripe_keys)
        self.assertIn("STRIPE_WEBHOOK_SECRET", stripe_keys)
        self.assertIn("STRIPE_CHECKOUT_PRICE_ID", stripe_keys)
        self.assertIn("RPT_PUBLIC_BASE_URL", stripe_keys)
        # Required keys match what payments helpers actually read
        self.assertTrue(
            any(v["key"] == "STRIPE_SECRET_KEY" and v["required"] for v in catalog["stripe"])
        )
        self.assertTrue(
            any(
                v["key"] == "STRIPE_WEBHOOK_SECRET" and v["required"]
                for v in catalog["stripe"]
            )
        )
        bmc_keys = {v["key"] for v in catalog["bmc"]}
        self.assertIn("RPT_BMC_TIP_URL", bmc_keys)
        # Drive real payments readers' env names
        self.assertEqual(
            set(plugins.get_processor_plugin("stripe").required_keys()),
            {"STRIPE_SECRET_KEY", "STRIPE_WEBHOOK_SECRET", "RPT_PUBLIC_BASE_URL"},
        )


class TestProcessorValidateApply(unittest.TestCase):
    def setUp(self):
        self._td = tempfile.TemporaryDirectory(ignore_cleanup_errors=True)
        self.addCleanup(self._td.cleanup)
        os.environ["RPT_PAYMENT_DATA_DIR"] = self._td.name
        for k in (
            "STRIPE_SECRET_KEY",
            "STRIPE_WEBHOOK_SECRET",
            "STRIPE_PRICE_ID",
            "RPT_PUBLIC_BASE_URL",
            "RPT_BMC_TIP_URL",
            "RPT_BMC_TIP_LABEL",
        ):
            os.environ.pop(k, None)

    def test_empty_required_rejected(self):
        r = plugins.validate_processor_entry("stripe", {})
        self.assertFalse(r["ok"])
        self.assertTrue(any("STRIPE_SECRET_KEY" in e for e in r["errors"]))

    def test_apply_stripe_sets_process_env_and_readiness(self):
        submitted = {
            "STRIPE_SECRET_KEY": "sk_test_UNIT_FAKE_NOT_REAL_aaaaaaaa",
            "STRIPE_WEBHOOK_SECRET": "whsec_UNIT_FAKE_NOT_REAL_bbbbbbbb",
            "RPT_PUBLIC_BASE_URL": "https://example-status.test",
        }
        out = plugins.apply_processor_entry("stripe", submitted, persist=True)
        self.assertTrue(out["ok"], out)
        self.assertFalse(out.get("secrets_echoed"))
        self.assertIn("STRIPE_SECRET_KEY", out["applied_keys"])
        self.assertTrue(payments.stripe_configured())
        self.assertTrue(out["readiness"].get("checkout_ready"))
        self.assertTrue(out["readiness"].get("fulfilment_ready"))
        # Store exists and does not get committed path into repo
        store = plugins.processor_env_store_path()
        self.assertTrue(store.is_file())
        text = store.read_text(encoding="utf-8")
        self.assertIn("STRIPE_SECRET_KEY", text)
        # HTML must not embed the secret when rendering settings
        html = admin_panel.render_processor_settings_html()
        self.assertNotIn("sk_test_UNIT_FAKE", html)
        self.assertNotIn("whsec_UNIT_FAKE", html)
        self.assertIn("admin-processor-settings", html)
        self.assertIn("processor-plugin-stripe", html)
        self.assertIn("STRIPE_SECRET_KEY", html)

    def test_apply_bmc_tip_url(self):
        out = plugins.apply_processor_entry(
            "bmc",
            {"RPT_BMC_TIP_URL": "https://buymeacoffee.com/example-creator"},
            persist=True,
        )
        self.assertTrue(out["ok"], out)
        from coffee_link import coffee_tip_url

        self.assertEqual(coffee_tip_url(), "https://buymeacoffee.com/example-creator")
        self.assertTrue(out["readiness"].get("ready"))

    def test_unknown_plugin(self):
        r = plugins.validate_processor_entry("paypal", {})
        self.assertFalse(r["ok"])


class TestAdminProcessorSettingsHtml(unittest.TestCase):
    def test_section_detail_and_forms_no_secrets(self):
        os.environ["STRIPE_SECRET_KEY"] = "sk_test_HTML_MUST_NOT_SHOW_THIS_KEY"
        os.environ["STRIPE_WEBHOOK_SECRET"] = "whsec_HTML_MUST_NOT_SHOW_THIS"
        try:
            html = admin_panel.render_admin_html(grants=[]).decode("utf-8")
            self.assertIn('id="admin-processor-settings"', html)
            self.assertIn("processor-plugin-stripe", html)
            self.assertIn("processor-plugin-bmc", html)
            self.assertIn('action="/admin/processors/apply"', html)
            self.assertIn("form-processor-stripe", html)
            self.assertIn("form-processor-bmc", html)
            self.assertIn("STRIPE_SECRET_KEY", html)
            self.assertIn("RPT_BMC_TIP_URL", html)
            self.assertIn("stripe-variables-table", html)
            self.assertNotIn("sk_test_HTML_MUST_NOT_SHOW", html)
            self.assertNotIn("whsec_HTML_MUST_NOT_SHOW", html)
            self.assertIn("admin-grants-table", html)
        finally:
            os.environ.pop("STRIPE_SECRET_KEY", None)
            os.environ.pop("STRIPE_WEBHOOK_SECRET", None)

    def test_public_page_has_no_processor_forms(self):
        import app as status_app

        html = status_app.render_html({"title": "RESTORE PRIVACY"}).decode("utf-8")
        self.assertNotIn("admin-processor-settings", html)
        self.assertNotIn("/admin/processors/apply", html)
        self.assertNotIn("form-processor-stripe", html)


if __name__ == "__main__":
    unittest.main()
