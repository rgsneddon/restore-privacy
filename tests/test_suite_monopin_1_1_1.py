"""Suite monopin 1.1.1 catalog + handoff pins (shipped sources)."""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "status_page"))

VERSION = (ROOT / "client" / "VERSION").read_text(encoding="utf-8").strip()


class TestSuiteMonopin111(unittest.TestCase):
    def test_version_file_is_1_1_1(self) -> None:
        self.assertEqual(VERSION, "1.1.1")

    def test_downloads_catalog_pin(self) -> None:
        from downloads import (
            RELEASE_VERSION,
            RELEASE_TAG,
            assure_current_catalog_packages,
            list_catalog_platform_packages,
        )

        self.assertEqual(RELEASE_VERSION, "1.1.1")
        self.assertEqual(RELEASE_TAG, "1.1.1")
        result = assure_current_catalog_packages()
        self.assertTrue(result["ok"], result.get("errors"))
        pkgs = list_catalog_platform_packages()
        self.assertEqual(len(pkgs), 5)
        for p in pkgs:
            self.assertEqual(p["version"], "1.1.1")
            self.assertIn("1.1.1", p["filename"])
            self.assertTrue(
                p["filename"].startswith("restore-privacy-client-1.1.1-")
            )

    def test_suite_version_dart_pin(self) -> None:
        dart = (ROOT / "client_app" / "lib" / "suite_version.dart").read_text(
            encoding="utf-8"
        )
        self.assertIn("kSuiteVersion = '1.1.1'", dart)
        self.assertIn("Restore Privacy Suite v 1.1.1", dart)

    def test_pubspec_pin(self) -> None:
        pub = (ROOT / "client_app" / "pubspec.yaml").read_text(encoding="utf-8")
        self.assertIn("version: 1.1.1+1", pub)

    def test_windows_handoff_1_1_1_exists(self) -> None:
        h = ROOT / "client" / "windows" / "WINDOWS_HANDOFF_1.1.1.md"
        self.assertTrue(h.is_file(), f"missing {h}")
        text = h.read_text(encoding="utf-8")
        self.assertIn("1.1.1", text)
        self.assertIn(
            "restore-privacy-client-1.1.1-windows-x64-setup.exe", text
        )
        self.assertIn("account → 12-word recovery seed → licence", text)
        self.assertIn("oracle_master", text)
        self.assertIn("Ned", text)


if __name__ == "__main__":
    unittest.main()
