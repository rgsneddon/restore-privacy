"""Settings explainer public page + homepage banner (shipped status_page helpers)."""

from __future__ import annotations

import re
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "status_page"))


class TestSettingsExplainerPage(unittest.TestCase):
    def test_page_has_shell_buy_now_explainers_and_howto(self) -> None:
        from settings_explainer import (
            catalog_ids,
            render_settings_explainer_page_html,
            settings_parts_catalog,
        )

        html = render_settings_explainer_page_html().decode("utf-8")
        # Homepage-style shell
        self.assertIn("--rb-navy", html)
        self.assertIn("panel-card", html)
        self.assertIn("page-shell", html)
        # BUY NOW → home
        self.assertIn('id="settings-explainer-buy-now"', html)
        self.assertIn('href="/"', html)
        self.assertIn("BUY NOW", html)
        # Explainers box + required Settings parts
        self.assertIn('id="settings-explainers-box"', html)
        ids = catalog_ids()
        for need in (
            "run-at-startup",
            "autoconnect-on-launch",
            "traffic-shaping",
            "outer-obfuscation",
            "multihop",
            "ping-statistics",
            "licence",
            "keygen",
            "connection-log",
            "leak-test",
            "docs-links",
            "core-vpn",
        ):
            self.assertIn(need, ids)
            self.assertIn(f'id="setting-{need}"', html)
        # Titles present
        low = html.lower()
        self.assertIn("run at device startup", low)
        self.assertIn("autoconnect on launch", low)
        self.assertIn("traffic shaping", low)
        self.assertIn("outer obfuscation", low)
        self.assertIn("multi-hop", low)
        self.assertIn("ping statistics", low)
        self.assertIn("keygen", low)
        self.assertIn("licence", low)
        # Second box: install how-to after explainers
        self.assertIn('id="install-run-howto-box"', html)
        i_exp = html.index('id="settings-explainers-box"')
        i_how = html.index('id="install-run-howto-box"')
        self.assertLess(i_exp, i_how)
        self.assertIn("How to install and run", html)
        self.assertIn("install-howto-steps", html)
        self.assertIn("Accept the end-user licence", html)
        self.assertIn("keygen", html.lower())
        self.assertIn("Press Connect", html)
        # Product-policy explainers wired (or fallback) — privacy scale honesty
        parts = settings_parts_catalog()
        shape = next(p for p in parts if p["id"] == "traffic-shaping")
        self.assertIn("ON", shape["body"].upper() or "on")

    def test_banner_html_targets_explainer_path(self) -> None:
        from settings_explainer import (
            HOMEPAGE_SETTINGS_BANNER_ID,
            SETTINGS_EXPLAINER_PATH,
            render_settings_explainer_banner_html,
        )

        b = render_settings_explainer_banner_html()
        self.assertIn(HOMEPAGE_SETTINGS_BANNER_ID, b)
        self.assertIn(SETTINGS_EXPLAINER_PATH, b)
        self.assertIn("settings-explainer-banner-link", b)
        self.assertIn("Browse Settings guide", b)


class TestHomepageBannerPlacement(unittest.TestCase):
    def test_render_html_brand_then_banner_then_downloads(self) -> None:
        from app import render_html
        from settings_explainer import (
            HOMEPAGE_SETTINGS_BANNER_ID,
            SETTINGS_EXPLAINER_PATH,
        )

        html = render_html({"title": "RESTORE PRIVACY"}).decode("utf-8")
        # Brand panel
        self.assertIn('id="brand-panel"', html)
        # Banner between brand and downloads
        self.assertIn(HOMEPAGE_SETTINGS_BANNER_ID, html)
        self.assertIn(SETTINGS_EXPLAINER_PATH, html)
        self.assertIn("settings-explainer-banner-link", html)
        # Downloads section marker from downloads.py
        i_brand = html.index('id="brand-panel"')
        i_banner = html.index(HOMEPAGE_SETTINGS_BANNER_ID)
        # download section usually has download or platform buttons
        m = re.search(
            r'id="(downloads|download-section|catalog|paid-downloads)[^"]*"',
            html,
            re.I,
        )
        if m:
            i_dl = m.start()
        else:
            # fallback: first occurrence of pay/download section language
            for needle in (
                "Download client",
                "ONLY £2.45",
                "platform-card",
                "download-section",
                "paid-download",
            ):
                if needle in html:
                    i_dl = html.index(needle)
                    break
            else:
                self.fail("downloads section marker not found in homepage HTML")
        self.assertLess(i_brand, i_banner, "banner must follow brand panel")
        self.assertLess(i_banner, i_dl, "banner must precede downloads section")
        # Banner CSS present
        self.assertIn("settings-banner", html)

    def test_route_paths_include_settings_explainer(self) -> None:
        src = (ROOT / "status_page" / "app.py").read_text(encoding="utf-8")
        self.assertIn("settings_explainer_paths", src)
        self.assertIn("render_settings_explainer_page_html", src)
        self.assertIn("render_settings_explainer_banner_html", src)
        from settings_explainer import settings_explainer_paths

        paths = settings_explainer_paths()
        self.assertIn("/settings-explainer", paths)
        self.assertIn("/settings", paths)


if __name__ == "__main__":
    unittest.main()
