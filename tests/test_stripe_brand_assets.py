"""Stripe Branding icon/logo assets: on-disk constraints + guide wiring.

Drives payments.stripe_brand_asset_constraints_ok on shipped PNG files.
"""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "status_page"))


class TestStripeBrandAssetsOnDisk(unittest.TestCase):
    def test_icon_and_logo_meet_stripe_constraints(self):
        from payments import (
            stripe_brand_asset_constraints_ok,
            stripe_brand_asset_paths,
            stripe_checkout_branding_guide,
        )

        paths = stripe_brand_asset_paths()
        icon = stripe_brand_asset_constraints_ok(
            paths["icon"], require_square=True, require_transparent=True
        )
        logo = stripe_brand_asset_constraints_ok(
            paths["logo"], require_square=False, require_transparent=True
        )
        self.assertTrue(icon["ok"], icon)
        self.assertTrue(logo["ok"], logo)
        self.assertEqual(icon["observed"]["format"], "png")
        self.assertEqual(logo["observed"]["format"], "png")
        self.assertTrue(icon["observed"]["square"])
        self.assertGreaterEqual(icon["observed"]["width"], 128)
        self.assertGreaterEqual(logo["observed"]["width"], 128)
        self.assertLess(icon["observed"]["size_bytes"], 512 * 1024)
        self.assertLess(logo["observed"]["size_bytes"], 512 * 1024)
        # Not favicon-tiny only
        self.assertGreaterEqual(icon["observed"]["width"], 256)
        # True transparent background (not opaque plate)
        self.assertTrue(icon["observed"]["corners_transparent"], icon)
        self.assertTrue(logo["observed"]["corners_transparent"], logo)
        self.assertEqual(icon["observed"]["corner_alphas"], [0, 0, 0, 0])
        self.assertEqual(logo["observed"]["corner_alphas"], [0, 0, 0, 0])
        self.assertGreaterEqual(icon["observed"]["transparent_fraction"], 0.35)
        self.assertGreaterEqual(logo["observed"]["transparent_fraction"], 0.35)
        self.assertGreaterEqual(icon["observed"]["opaque_pixel_count"], 50)

        g = stripe_checkout_branding_guide()
        self.assertTrue(g["branding"]["icon_constraints_ok"])
        self.assertTrue(g["branding"]["logo_constraints_ok"])
        self.assertTrue(g["branding"]["requires_transparent_background"])
        self.assertTrue(g["branding"]["transparent_background"])
        self.assertTrue(str(g["branding"]["stripe_file_id_icon"]).startswith("file_"))
        self.assertTrue(str(g["branding"]["stripe_file_id_logo"]).startswith("file_"))
        self.assertEqual(g["branding"]["primary_color"], "#2694e8")
        self.assertEqual(g["branding"]["secondary_color"], "#0a1628")

    def test_static_copies_match_transparent_masters(self):
        from payments import stripe_brand_asset_paths

        paths = stripe_brand_asset_paths()
        self.assertTrue(paths["icon_static"].is_file())
        self.assertTrue(paths["logo_static"].is_file())
        self.assertEqual(paths["icon"].read_bytes(), paths["icon_static"].read_bytes())
        self.assertEqual(paths["logo"].read_bytes(), paths["logo_static"].read_bytes())
        # Must not be the opaque site logo.png
        site_logo = ROOT / "status_page" / "static" / "logo.png"
        self.assertTrue(site_logo.is_file())
        self.assertNotEqual(paths["icon"].read_bytes(), site_logo.read_bytes())
        self.assertNotEqual(paths["logo"].read_bytes(), site_logo.read_bytes())
        from payments import stripe_brand_asset_constraints_ok

        site = stripe_brand_asset_constraints_ok(
            site_logo, require_square=True, require_transparent=True
        )
        self.assertFalse(
            site["ok"],
            "site logo.png is opaque plate and must not pass transparent Stripe check",
        )

    def test_rejects_missing_transparency(self):
        """Constraint helper must fail when corners are opaque (shipped site logo)."""
        from payments import stripe_brand_asset_constraints_ok

        site_logo = ROOT / "status_page" / "static" / "logo.png"
        bad = stripe_brand_asset_constraints_ok(
            site_logo, require_square=True, require_transparent=True
        )
        self.assertFalse(bad["ok"])
        self.assertTrue(
            any("transparent" in m or "corners" in m for m in bad["mismatches"]),
            bad["mismatches"],
        )

    def test_upload_script_exists(self):
        script = ROOT / "scripts" / "upload_stripe_branding_assets.py"
        self.assertTrue(script.is_file())
        src = script.read_text(encoding="utf-8")
        self.assertIn("business_icon", src)
        self.assertIn("business_logo", src)
        self.assertIn("stripe_brand_asset_paths", src)


class TestGuideStillHonestAboutApi(unittest.TestCase):
    def test_account_api_self_update_false(self):
        from payments import stripe_checkout_branding_guide

        g = stripe_checkout_branding_guide()
        self.assertFalse(g["branding"]["account_api_self_update"])
        self.assertIn("403", g["branding"]["account_api_note"])


if __name__ == "__main__":
    unittest.main()
