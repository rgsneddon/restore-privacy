"""Processor env persist: blank does not wipe; set badge follows store."""

from __future__ import annotations

import os
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "status_page"))


class TestProcessorPersistSet(unittest.TestCase):
    def setUp(self):
        self._td = tempfile.TemporaryDirectory()
        os.environ["RPT_PAYMENT_DATA_DIR"] = self._td.name
        # Clear process secrets so store is source of truth
        for k in (
            "STRIPE_SECRET_KEY",
            "STRIPE_WEBHOOK_SECRET",
            "STRIPE_CHECKOUT_PRICE_ID",
            "RPT_ASSET_FETCH_TOKEN",
            "RPT_PUBLIC_BASE_URL",
        ):
            os.environ.pop(k, None)
        import processor_plugins as pp

        self.pp = pp
        # reload module paths use env
        for k in list(sys.modules):
            if "processor" in k or k == "payments":
                del sys.modules[k]
        import processor_plugins as pp2
        import payments as pay

        self.pp = pp2
        self.pay = pay

    def tearDown(self):
        self._td.cleanup()
        os.environ.pop("RPT_PAYMENT_DATA_DIR", None)

    def test_save_then_blank_keeps_secret(self):
        fake_sk = "sk_test_FAKE_NOT_A_REAL_KEY_FOR_UNIT_TEST_ONLY_xx"
        fake_wh = "whsec_FAKE_NOT_A_REAL_WEBHOOK_SECRET_FOR_UNIT_TEST"
        r1 = self.pp.apply_processor_entry(
            "stripe",
            {
                "STRIPE_SECRET_KEY": fake_sk,
                "STRIPE_WEBHOOK_SECRET": fake_wh,
                "RPT_PUBLIC_BASE_URL": "https://restoreprivacy.online",
            },
            persist=True,
        )
        self.assertTrue(r1["ok"], r1.get("errors"))
        self.assertIn("STRIPE_SECRET_KEY", r1["applied_keys"])
        # Blank submit must not clear
        r2 = self.pp.apply_processor_entry(
            "stripe",
            {
                "STRIPE_SECRET_KEY": "",
                "STRIPE_WEBHOOK_SECRET": "",
                "RPT_PUBLIC_BASE_URL": "https://restoreprivacy.online",
            },
            persist=True,
        )
        self.assertTrue(r2["ok"], r2.get("errors"))
        stored = self.pp.load_stored_processor_env()
        self.assertEqual(stored.get("STRIPE_SECRET_KEY"), fake_sk)
        self.assertEqual(stored.get("STRIPE_WEBHOOK_SECRET"), fake_wh)
        # Readers see store even if we clear env
        os.environ.pop("STRIPE_SECRET_KEY", None)
        os.environ.pop("STRIPE_WEBHOOK_SECRET", None)
        self.assertEqual(self.pay.stripe_secret_key(), fake_sk)
        self.assertEqual(self.pay.stripe_webhook_secret(), fake_wh)
        # Badges / views
        views = self.pp.processor_plugin_views()
        stripe = next(v for v in views if v["id"] == "stripe")
        by_key = {x["key"]: x for x in stripe["variables"]}
        self.assertTrue(by_key["STRIPE_SECRET_KEY"]["configured"])
        self.assertEqual(by_key["STRIPE_SECRET_KEY"]["status_kind"], "set")
        self.assertTrue(by_key["STRIPE_WEBHOOK_SECRET"]["configured"])
        # Optional price id
        self.assertEqual(by_key["STRIPE_CHECKOUT_PRICE_ID"]["status_kind"], "optional_ok")

    def test_vps_token_persist_and_set(self):
        tok = "rpt_asset_test_token_not_real_ABCDEFGH"
        r = self.pp.apply_processor_entry(
            "vps_assets",
            {"RPT_ASSET_FETCH_TOKEN": tok},
            persist=True,
        )
        self.assertTrue(r["ok"], r.get("errors"))
        os.environ.pop("RPT_ASSET_FETCH_TOKEN", None)
        self.assertEqual(self.pay.vps_asset_fetch_token(), tok)
        views = self.pp.processor_plugin_views()
        vps = next(v for v in views if v["id"] == "vps_assets")
        by_key = {x["key"]: x for x in vps["variables"]}
        self.assertTrue(by_key["RPT_ASSET_FETCH_TOKEN"]["configured"])

    def test_admin_html_has_key_howto_no_real_secrets(self):
        from admin_panel import render_admin_html

        page = render_admin_html().decode("utf-8")
        self.assertIn("admin-key-howto", page)
        self.assertIn("STRIPE_SECRET_KEY", page)
        self.assertIn("STRIPE_WEBHOOK_SECRET", page)
        self.assertIn("STRIPE_CHECKOUT_PRICE_ID", page)
        self.assertIn("RPT_ASSET_FETCH_TOKEN", page)
        # Guide may show prefix + ellipsis (sk_live_…); block real-looking values only
        self.assertNotIn("sk_test_FAKE", page)
        self.assertNotIn("sk_test_HTML", page)
        self.assertNotRegex(page, r"sk_(?:live|test)_[A-Za-z0-9]{10,}")
        self.assertNotRegex(page, r"whsec_[A-Za-z0-9]{10,}")
        self.assertIn("optional (unit_amount)", page)


if __name__ == "__main__":
    unittest.main()
