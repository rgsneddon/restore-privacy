"""Catalog monopin 1.2.1 Android package naming (shipped suite build path)."""

from __future__ import annotations

import re
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


class TestSuiteAndroid121StageName(unittest.TestCase):
    def test_version_pin_and_android_filename(self) -> None:
        pin = (ROOT / "client" / "VERSION").read_text(encoding="utf-8").strip()
        self.assertEqual(pin, "1.2.1")
        suite = (ROOT / "scripts" / "build_suite_1.2.1.py").read_text(encoding="utf-8")
        m = re.search(r'^VERSION = "([^"]+)"', suite, re.M)
        self.assertIsNotNone(m)
        self.assertEqual(m.group(1), pin)
        expected = f"restore-privacy-client-{pin}-android.apk"
        self.assertIn(
            f'"android": f"restore-privacy-client-{{VERSION}}-android.apk"', suite
        )
        self.assertIn("def build_android", suite)
        self.assertIn("flutter-apk", suite)
        self.assertIn("app-release.apk", suite)
        self.assertIn('OUT / NAMES["android"]', suite)
        staged = ROOT / "releases" / pin / expected
        if staged.is_file():
            self.assertEqual(staged.name, expected)
            self.assertGreater(staged.stat().st_size, 1_000_000)


if __name__ == "__main__":
    unittest.main()
