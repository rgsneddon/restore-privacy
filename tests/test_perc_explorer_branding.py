"""Perc explorer public UI includes Restore Privacy logo branding."""

from __future__ import annotations

import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PUBLIC = ROOT / "perc_chain" / "public"


class TestPercExplorerBranding(unittest.TestCase):
    def test_logo_asset_and_index_branding(self) -> None:
        logo = PUBLIC / "restore-privacy-logo.png"
        index = PUBLIC / "index.html"
        self.assertTrue(logo.is_file(), logo)
        self.assertGreater(logo.stat().st_size, 1000)
        # PNG magic
        self.assertEqual(logo.read_bytes()[:8], b"\x89PNG\r\n\x1a\n")

        html = index.read_text(encoding="utf-8")
        self.assertIn("restore-privacy-logo.png", html)
        self.assertIn('data-rpt-logo="1"', html)
        self.assertIn('data-rpt-brand="1"', html)
        self.assertIn("Restore Privacy Suite", html)
        self.assertIn("Restore Privacy logo", html)
        self.assertIn("rpt-logo", html)
        # Title names Suite product
        self.assertIn("Restore Privacy Suite", html.split("<title>")[1].split("</title>")[0])


if __name__ == "__main__":
    unittest.main()
