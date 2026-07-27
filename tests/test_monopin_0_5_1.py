"""Monopin 0.5.1 pin files and handoff breadcrumbs."""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "status_page"))

PIN = "0.5.1"


class TestMonopin051(unittest.TestCase):
    def test_client_version_file(self):
        ver = (ROOT / "client" / "VERSION").read_text(encoding="utf-8").strip()
        self.assertEqual(ver, PIN)

    def test_downloads_release_version(self):
        from downloads import RELEASE_VERSION, RELEASE_TAG, current_catalog_version

        self.assertEqual(RELEASE_VERSION, PIN)
        self.assertEqual(RELEASE_TAG, PIN)
        self.assertEqual(current_catalog_version(), PIN)

    def test_flutter_product_version(self):
        cfg = (ROOT / "client_app" / "lib" / "rpt_config.dart").read_text(
            encoding="utf-8"
        )
        self.assertIn(f"productVersion = '{PIN}'", cfg)
        pub = (ROOT / "client_app" / "pubspec.yaml").read_text(encoding="utf-8")
        self.assertIn(f"version: {PIN}+", pub)

    def test_release_script_and_notes(self):
        script = ROOT / "scripts" / f"build_release_{PIN}.py"
        self.assertTrue(script.is_file(), msg=str(script))
        src = script.read_text(encoding="utf-8")
        self.assertIn(f'VERSION = "{PIN}"', src)
        notes = ROOT / "scripts" / f"RELEASE_NOTES_{PIN}.md"
        self.assertTrue(notes.is_file())
        self.assertIn(PIN, notes.read_text(encoding="utf-8"))

    def test_apple_and_windows_handoffs(self):
        apple = ROOT / "client_app" / f"APPLE_HANDOFF_{PIN}.md"
        win = ROOT / "client" / "windows" / f"WINDOWS_HANDOFF_{PIN}.md"
        self.assertTrue(apple.is_file())
        self.assertTrue(win.is_file())
        a = apple.read_text(encoding="utf-8")
        w = win.read_text(encoding="utf-8")
        self.assertIn(PIN, a)
        self.assertIn("Quit", a)
        self.assertIn(PIN, w)
        self.assertIn("build_release_0.5.1.py", w)
        self.assertIn("windows-x64-setup.exe", w)

    def test_quit_sources_present_for_apple_ship(self):
        self.assertTrue((ROOT / "client_app" / "lib" / "app_quit.dart").is_file())
        main = (ROOT / "client_app" / "lib" / "main.dart").read_text(encoding="utf-8")
        self.assertIn("performQuitSequence", main)


if __name__ == "__main__":
    unittest.main()
