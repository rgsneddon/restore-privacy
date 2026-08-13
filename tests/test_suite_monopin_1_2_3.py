"""Suite monopin 1.2.3 catalog + handoff pins (shipped sources)."""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "status_page"))

VERSION = (ROOT / "client" / "VERSION").read_text(encoding="utf-8").strip()


class TestSuiteMonopin123(unittest.TestCase):
    def test_version_file_is_1_2_3(self) -> None:
        self.assertEqual(VERSION, "1.2.3")

    def test_downloads_catalog_pin(self) -> None:
        from downloads import (
            RELEASE_VERSION,
            RELEASE_TAG,
            list_catalog_platform_packages,
        )

        self.assertEqual(RELEASE_VERSION, "1.2.3")
        self.assertEqual(RELEASE_TAG, "1.2.3")
        pkgs = list_catalog_platform_packages()
        self.assertEqual(len(pkgs), 5)
        for p in pkgs:
            self.assertEqual(p["version"], "1.2.3")
            self.assertIn("1.2.3", p["filename"])
            self.assertTrue(
                p["filename"].startswith("restore-privacy-client-1.2.3-")
            )

    def test_suite_version_dart_pin(self) -> None:
        dart = (ROOT / "client_app" / "lib" / "suite_version.dart").read_text(
            encoding="utf-8"
        )
        self.assertIn("kSuiteVersion = '1.2.3'", dart)

    def test_pubspec_pin(self) -> None:
        pub = (ROOT / "client_app" / "pubspec.yaml").read_text(encoding="utf-8")
        self.assertIn("version: 1.2.3+", pub)

    def test_rpt_config_product_version(self) -> None:
        cfg = (ROOT / "client_app" / "lib" / "rpt_config.dart").read_text(
            encoding="utf-8"
        )
        self.assertIn("productVersion = '1.2.3'", cfg)

    def test_windows_handoff_1_2_3_exists(self) -> None:
        h = ROOT / "client" / "windows" / "WINDOWS_HANDOFF_1.2.3.md"
        self.assertTrue(h.is_file(), f"missing {h}")
        text = h.read_text(encoding="utf-8")
        self.assertIn("1.2.3", text)
        self.assertIn(
            "restore-privacy-client-1.2.3-windows-x64-setup.exe", text
        )
        self.assertIn("native-rebuild", text.lower().replace(" ", "-") or "native")
        self.assertTrue(
            "native-rebuild" in text.lower()
            or "native rebuild" in text.lower()
            or "must native-rebuild" in text.lower()
        )

    def test_build_suite_1_2_3_exists(self) -> None:
        script = ROOT / "scripts" / "build_suite_1.2.3.py"
        self.assertTrue(script.is_file())
        text = script.read_text(encoding="utf-8")
        self.assertIn('VERSION = "1.2.3"', text)
        self.assertIn("1.2.2", text)  # carry-forward prior
        self.assertIn("ios_sideload_package", text)
        self.assertIn("embedded.mobileprovision", text)

    def test_android_lock_recovery_in_tree(self) -> None:
        """1.2.3 product path includes residual lock/desired re-HELLO honesty."""
        svc = (
            ROOT
            / "client_app/android/app/src/main/kotlin/com/restoreprivacy/"
            "restore_privacy_client/RptVpnService.kt"
        ).read_text(encoding="utf-8")
        self.assertIn("wantsDesiredSessionRecovery", svc)
        self.assertIn("PARTIAL_WAKE_LOCK", svc)
        self.assertIn("scheduleIdleReconnect", svc)


if __name__ == "__main__":
    unittest.main()
