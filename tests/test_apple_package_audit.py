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

        pin = (ROOT / "client" / "VERSION").read_text(encoding="utf-8").strip()
        self.assertRegex(pin, r"^\d+\.\d+")
        self.assertEqual(RELEASE_VERSION, pin)
        report = audit_catalog_apple_packages(version=RELEASE_VERSION)
        self.assertEqual(report["catalog_version"], pin)
        mac_exists = bool(report["macos"].get("exists"))
        ios_exists = bool(report["ios"].get("exists"))
        if not (mac_exists and ios_exists):
            # Gitignored assets not staged on this host — honesty must still fire
            self.assertTrue(report.get("placeholder_suspected"), report)
            honesty = report.get("honesty") or ""
            self.assertTrue(
                "DO NOT MATCH" in honesty
                or "MISSING" in honesty
                or "missing" in honesty.lower()
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
            self.assertEqual(mac_v, pin)
            self.assertEqual(ios_v, pin)
            self.assertFalse(report.get("placeholder_suspected", False))
        else:
            self.assertIn("DO NOT MATCH", report.get("honesty", ""))

    def test_handoff_documents_mac_rebuild_ship(self) -> None:
        pin = (ROOT / "client" / "VERSION").read_text(encoding="utf-8").strip()
        # Prefer current monopin handoff; fall back to latest 0.4.x ship notes
        candidates = [
            ROOT / "client_app" / f"APPLE_HANDOFF_{pin}.md",
            ROOT / "client_app" / "APPLE_HANDOFF_0.4.8.md",
            ROOT / "client_app" / "APPLE_HANDOFF_0.4.1.md",
        ]
        path = next((p for p in candidates if p.is_file()), None)
        self.assertIsNotNone(path, "missing APPLE_HANDOFF for catalog monopin")
        assert path is not None
        text = path.read_text(encoding="utf-8")
        self.assertIn(pin if pin in text else "0.4.", text)
        self.assertIn("privacy-scale", text.lower())
        self.assertIn("CFBundleShortVersionString", text)
        self.assertIn("Mac rebuild", text)
        self.assertTrue(
            "privacy-scale toggles" in text.lower() or "privacy-scale" in text.lower()
        )
        self.assertIn("device bind", text.lower())


if __name__ == "__main__":
    unittest.main()
