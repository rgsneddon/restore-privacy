"""Apple catalog zip monopin honesty — drive real apple_package_audit helper."""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "status_page"))


class TestApplePackageAudit(unittest.TestCase):
    def test_audit_detects_catalog_match_after_mac_rebuild(self) -> None:
        """Drive real audit helper against catalog monopin.

        ``status_page/assets/*`` is gitignored — packages may be absent on a
        fresh clone. When present, marketing versions must match monopin;
        when absent/mismatched, honesty string must document the gap.
        """
        from apple_package_audit import audit_catalog_apple_packages
        from downloads import RELEASE_VERSION

        self.assertEqual(RELEASE_VERSION, "0.4.1")
        report = audit_catalog_apple_packages(version=RELEASE_VERSION)
        self.assertEqual(report["catalog_version"], "0.4.1")
        mac_exists = bool(report["macos"].get("exists"))
        ios_exists = bool(report["ios"].get("exists"))
        if not (mac_exists and ios_exists):
            # Gitignored assets not staged on this host — honesty must still fire
            self.assertTrue(report.get("placeholder_suspected"), report)
            honesty = report.get("honesty") or ""
            self.assertTrue(
                "DO NOT MATCH" in honesty or "missing" in honesty.lower()
                or "Re-build on Mac" in honesty
                or "APPLE_HANDOFF" in honesty,
                honesty,
            )
            return
        mac_v = report["macos"].get("primary_version")
        ios_v = report["ios"].get("primary_version")
        self.assertIsNotNone(mac_v)
        self.assertIsNotNone(ios_v)
        # After Mac rebuild: marketing versions must match monopin (not placeholders)
        if report.get("all_match"):
            self.assertEqual(mac_v, "0.4.1")
            self.assertEqual(ios_v, "0.4.1")
            self.assertFalse(report.get("placeholder_suspected", False))
        else:
            self.assertIn("DO NOT MATCH", report.get("honesty", ""))

    def test_handoff_documents_mac_rebuild_ship(self) -> None:
        text = (
            ROOT / "client_app" / "APPLE_HANDOFF_0.4.1.md"
        ).read_text(encoding="utf-8")
        self.assertIn("0.4.1", text)
        self.assertIn("privacy-scale", text.lower())
        self.assertIn("CFBundleShortVersionString", text)
        # Post-rebuild handoff claims real 0.4.1 packages
        self.assertIn("Mac rebuild", text)
        self.assertIn("privacy-scale toggles", text.lower())
        self.assertIn("device bind", text.lower())


if __name__ == "__main__":
    unittest.main()
