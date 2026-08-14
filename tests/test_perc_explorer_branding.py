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
        self.assertIn("Restore Privacy", html)
        self.assertIn("Restore Privacy logo", html)
        self.assertIn("rpt-logo", html)
        # Title names Suite product
        self.assertIn("Restore Privacy", html.split("<title>")[1].split("</title>")[0])
        self.assertIn("page-top-links", html)
        self.assertIn("justify-content: space-between", html)
        self.assertIn('href="#nodes"', html)
        self.assertIn('href="#explorer"', html)
        self.assertIn("FCG white paper", html)
        self.assertIn("page-downloads", html)
        self.assertIn("--neon-yellow", html)
        self.assertIn("Evolve 4.1.11", html)
        self.assertIn("MY PERC", html)
        self.assertIn(
            "https://github.com/rgsneddon/evolve/releases/download/v4.1.11-macos-ios-android/evolve-v4.1.11-macos-x64.zip",
            html,
        )
        self.assertIn(
            "https://github.com/rgsneddon/evolve/releases/download/v4.1.11-macos-ios-android/evolve-v4.1.11-ios-setup.ipa",
            html,
        )
        self.assertIn(
            "https://github.com/rgsneddon/evolve/releases/download/v4.1.11/evolve-v4.1.11-windows-x64-setup.exe",
            html,
        )
        self.assertIn(
            "https://github.com/rgsneddon/evolve/releases/download/v4.1.11-macos-ios-android/evolve-v4.1.11-android-setup.apk",
            html,
        )
        self.assertIn(
            "https://github.com/rgsneddon/perccent-wallet/releases/download/v1.1.8/perccent-wallet-v1.1.8-macos-setup.zip",
            html,
        )
        self.assertIn(
            "https://github.com/rgsneddon/perccent-wallet/releases/download/v1.1.7/perccent-wallet-v1.1.7-ios-setup.ipa",
            html,
        )
        self.assertIn(
            "https://github.com/rgsneddon/perccent-wallet/releases/download/v1.1.6/perccent-wallet-v1.1.6-android-setup.apk",
            html,
        )

    def test_perc_mine_link_is_first_neon_blue_and_centered(self) -> None:
        html = (PUBLIC / "index.html").read_text(encoding="utf-8")
        body = html.split("<body>", 1)[1]
        self.assertIn("Perc Mine", html)
        self.assertIn('href="https://mineperc.restoreprivacy.online"', html)
        perc_at = body.find("Perc Mine")
        page_top_at = body.find('class="page-top"')
        brand_at = body.find("brand-lockup")
        downloads_at = body.find("page-downloads")
        self.assertGreater(perc_at, 0)
        self.assertLess(perc_at, page_top_at)
        self.assertLess(perc_at, brand_at)
        self.assertLess(perc_at, downloads_at)
        href_at = body.find('href="https://mineperc.restoreprivacy.online"')
        self.assertLess(href_at, perc_at)
        self.assertIn("--neon-blue:", html)
        self.assertIn(".perc-mine-bar", html)
        bar_css = html.split(".perc-mine-bar {", 1)[1].split("}", 1)[0]
        self.assertIn("text-align: center", bar_css)
        self.assertIn("width: 100%", bar_css)
        link_css = html.split(".perc-mine-bar a {", 1)[1].split("}", 1)[0]
        self.assertIn("var(--neon-blue)", link_css)
        self.assertIn("text-align: center", link_css)


if __name__ == "__main__":
    unittest.main()
