"""Current-ship monopin: VERSION, catalog list, and download HTML stay aligned.

Drives shipped status_page.downloads helpers so a pin bump that forgets
filenames or leaves older basenames in the public download section fails.
"""

from __future__ import annotations

import re
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


class TestCatalogMonopinCurrentShip(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        import sys

        sp = str(ROOT / "status_page")
        if sp not in sys.path:
            sys.path.insert(0, sp)
        import downloads as d

        cls.d = d
        cls.pin = (ROOT / "client" / "VERSION").read_text(encoding="utf-8").strip()

    def test_version_file_matches_release_and_current_catalog(self):
        self.assertTrue(self.pin)
        self.assertEqual(self.d.RELEASE_VERSION, self.pin)
        self.assertEqual(self.d.current_catalog_version(), self.pin)
        self.assertEqual(self.d.RELEASE_TAG, self.pin)

    def test_five_platform_basenames_embed_monopin(self):
        pkgs = self.d.list_catalog_platform_packages(version=self.pin)
        self.assertEqual(len(pkgs), 5)
        platforms = {p["platform"] for p in pkgs}
        self.assertEqual(
            platforms, {"windows", "android", "macos", "ios", "linux"}
        )
        for p in pkgs:
            self.assertEqual(p["version"], self.pin)
            self.assertTrue(
                p["filename"].startswith(f"restore-privacy-client-{self.pin}-"),
                p["filename"],
            )
            self.assertEqual(p["relative_path"], f"{self.pin}/{p['filename']}")

    def test_download_section_html_only_current_monopin_packages(self):
        html = self.d.render_download_section_html()
        # All current basenames present
        for p in self.d.list_catalog_platform_packages(version=self.pin):
            self.assertIn(p["filename"], html)
        # No older monopin package basenames advertised
        found = re.findall(
            r"restore-privacy-client-([0-9.]+)-[A-Za-z0-9._-]+", html
        )
        for ver in found:
            self.assertEqual(
                ver,
                self.pin,
                f"download section cites non-current monopin package {ver}; pin={self.pin}",
            )
        # Paid path — not free permanent GH installer URLs
        self.assertNotIn("releases/download/", html)


if __name__ == "__main__":
    unittest.main()
