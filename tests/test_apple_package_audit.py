"""Apple catalog zip monopin honesty — drive real apple_package_audit helper."""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "status_page"))


class TestApplePackageAudit(unittest.TestCase):
    def test_audit_detects_catalog_mismatch_on_staged_0_3_9(self) -> None:
        from apple_package_audit import audit_catalog_apple_packages
        from downloads import RELEASE_VERSION

        self.assertEqual(RELEASE_VERSION, "0.3.9")
        report = audit_catalog_apple_packages(version=RELEASE_VERSION)
        self.assertEqual(report["catalog_version"], "0.3.9")
        # Files must exist (staged for VPS) but bundle version may lag monopin
        self.assertTrue(report["macos"]["exists"], report)
        self.assertTrue(report["ios"]["exists"], report)
        mac_v = report["macos"].get("primary_version")
        ios_v = report["ios"].get("primary_version")
        self.assertIsNotNone(mac_v)
        self.assertIsNotNone(ios_v)
        # Document current honesty: staged zips are placeholders until Mac rebuild
        if not report["all_match"]:
            self.assertTrue(report["placeholder_suspected"])
            self.assertNotEqual(mac_v, "0.3.9")
            self.assertIn("DO NOT MATCH", report["honesty"])
            self.assertIn("APPLE_HANDOFF", report["honesty"])
        else:
            self.assertEqual(mac_v, "0.3.9")
            self.assertEqual(ios_v, "0.3.9")

    def test_handoff_documents_placeholder_honesty(self) -> None:
        text = (
            ROOT / "client_app" / "APPLE_HANDOFF_0.3.9.md"
        ).read_text(encoding="utf-8")
        self.assertIn("0.3.9", text)
        self.assertIn("privacy-scale", text.lower())
        self.assertIn("placeholder", text.lower())
        self.assertIn("CFBundleShortVersionString", text)
        self.assertIn("0.2.3", text)
        self.assertIn("0.1.7", text)


if __name__ == "__main__":
    unittest.main()
