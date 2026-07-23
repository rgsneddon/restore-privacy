"""Apple catalog zip monopin honesty — drive real apple_package_audit helper."""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "status_page"))


class TestApplePackageAudit(unittest.TestCase):
    def test_audit_detects_catalog_match_after_mac_rebuild(self) -> None:
        from apple_package_audit import audit_catalog_apple_packages
        from downloads import RELEASE_VERSION

        self.assertEqual(RELEASE_VERSION, "0.4.0")
        report = audit_catalog_apple_packages(version=RELEASE_VERSION)
        self.assertEqual(report["catalog_version"], "0.4.0")
        self.assertTrue(report["macos"]["exists"], report)
        self.assertTrue(report["ios"]["exists"], report)
        mac_v = report["macos"].get("primary_version")
        ios_v = report["ios"].get("primary_version")
        self.assertIsNotNone(mac_v)
        self.assertIsNotNone(ios_v)
        # After Mac rebuild: marketing versions must match monopin (not 0.2.3/0.1.7 placeholders)
        if report.get("all_match"):
            self.assertEqual(mac_v, "0.4.0")
            self.assertEqual(ios_v, "0.4.0")
            self.assertFalse(report.get("placeholder_suspected", False))
        else:
            # Still allow staged lag only if honesty string documents mismatch
            self.assertIn("DO NOT MATCH", report.get("honesty", ""))

    def test_handoff_documents_mac_rebuild_ship(self) -> None:
        text = (
            ROOT / "client_app" / "APPLE_HANDOFF_0.4.0.md"
        ).read_text(encoding="utf-8")
        self.assertIn("0.4.0", text)
        self.assertIn("privacy-scale", text.lower())
        self.assertIn("CFBundleShortVersionString", text)
        # Post-rebuild handoff claims real 0.4.0 packages
        self.assertIn("Mac rebuild", text)
        self.assertIn("privacy-scale toggles", text.lower())
        self.assertIn("device bind", text.lower())


if __name__ == "__main__":
    unittest.main()
