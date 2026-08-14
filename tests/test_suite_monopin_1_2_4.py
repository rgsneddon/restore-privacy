"""Suite monopin 1.2.4 catalog + handoff pins (shipped sources)."""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "status_page"))

VERSION = (ROOT / "client" / "VERSION").read_text(encoding="utf-8").strip()


class TestSuiteMonopin124(unittest.TestCase):
    def test_version_file_is_1_2_4(self) -> None:
        self.assertEqual(VERSION, "1.2.4")

    def test_downloads_catalog_pin(self) -> None:
        from downloads import (
            RELEASE_VERSION,
            RELEASE_TAG,
            list_catalog_platform_packages,
        )

        self.assertEqual(RELEASE_VERSION, "1.2.4")
        self.assertEqual(RELEASE_TAG, "1.2.4")
        pkgs = list_catalog_platform_packages()
        self.assertEqual(len(pkgs), 5)
        for p in pkgs:
            self.assertEqual(p["version"], "1.2.4")
            self.assertIn("1.2.4", p["filename"])
            self.assertTrue(
                p["filename"].startswith("restore-privacy-client-1.2.4-")
            )

    def test_suite_version_dart_pin(self) -> None:
        dart = (ROOT / "client_app" / "lib" / "suite_version.dart").read_text(
            encoding="utf-8"
        )
        self.assertIn("kSuiteVersion = '1.2.4'", dart)

    def test_pubspec_pin(self) -> None:
        pub = (ROOT / "client_app" / "pubspec.yaml").read_text(encoding="utf-8")
        self.assertIn("version: 1.2.4+", pub)

    def test_rpt_config_product_version(self) -> None:
        cfg = (ROOT / "client_app" / "lib" / "rpt_config.dart").read_text(
            encoding="utf-8"
        )
        self.assertIn("productVersion = '1.2.4'", cfg)

    def test_windows_handoff_1_2_4_exists(self) -> None:
        h = ROOT / "client" / "windows" / "WINDOWS_HANDOFF_1.2.4.md"
        self.assertTrue(h.is_file(), f"missing {h}")
        text = h.read_text(encoding="utf-8")
        self.assertIn("1.2.4", text)
        self.assertIn(
            "restore-privacy-client-1.2.4-windows-x64-setup.exe", text
        )
        self.assertTrue(
            "native-rebuild" in text.lower()
            or "native rebuild" in text.lower()
            or "must native-rebuild" in text.lower()
        )
        self.assertIn("internal error", text.lower())

    def test_build_suite_1_2_4_exists(self) -> None:
        script = ROOT / "scripts" / "build_suite_1.2.4.py"
        self.assertTrue(script.is_file())
        text = script.read_text(encoding="utf-8")
        self.assertIn('VERSION = "1.2.4"', text)
        self.assertIn("1.2.3", text)  # carry-forward prior
        self.assertIn("ios_sideload_package", text)
        self.assertIn("embedded.mobileprovision", text)
        # Darwin never stages Windows PE
        self.assertIn("Windows: never staged on this Mac host", text)

    def test_macos_internal_error_recreate_in_tree(self) -> None:
        """1.2.4: recreate VPN profile when NE wraps upgrade as internal error."""
        swift = (
            ROOT / "client_app" / "macos" / "NativePrep" / "RptVpnChannel.swift"
        ).read_text(encoding="utf-8")
        self.assertIn("shouldRecreateVpnProfileAfterStartFailure", swift)
        self.assertIn("internal error", swift)
        self.assertIn("nevpnconnectionerrordomain", swift)
        self.assertIn("maxAttempts: 72", swift)


if __name__ == "__main__":
    unittest.main()
