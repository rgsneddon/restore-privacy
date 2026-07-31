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
        # Homepage-style shell + shared brand header (no BUY NOW — use Home nav)
        self.assertIn("--rb-navy", html)
        self.assertIn("panel-card", html)
        self.assertIn("page-shell", html)
        self.assertIn('id="brand-panel"', html)
        self.assertIn('id="home-link"', html)
        self.assertIn('href="/"', html)
        self.assertNotIn('id="settings-explainer-buy-now"', html)
        self.assertNotIn("BUY NOW", html)
        self.assertIn('id="theme-mode-control"', html)
        # Top brand box and first panel: no tagline subtitles
        brand_start = html.index('id="brand-panel"')
        brand_end = html.index("</header>", brand_start)
        brand_box = html[brand_start:brand_end]
        self.assertNotIn("brand-tagline", brand_box)
        self.assertNotIn('class="tagline"', brand_box)
        self.assertNotIn("lightweight vpn to restore", brand_box.lower())
        exp_start = html.index('id="settings-explainers-box"')
        exp_end = html.index("</section>", exp_start)
        explainers_box = html[exp_start:exp_end]
        self.assertNotIn('class="tagline"', explainers_box)
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


class TestHomepageSettingsGuideNav(unittest.TestCase):
    def test_homepage_settings_guide_in_nav_not_banner(self) -> None:
        """Settings Guide is main-nav only — dedicated homepage banner removed."""
        from app import render_html
        from settings_explainer import SETTINGS_EXPLAINER_PATH

        html = render_html({"title": "RESTORE PRIVACY"}).decode("utf-8")
        self.assertIn('id="brand-panel"', html)
        self.assertIn('id="settings-guide-link"', html)
        self.assertIn(f'href="{SETTINGS_EXPLAINER_PATH}"', html)
        self.assertIn("SETTINGS GUIDE", html)
        # Settings Guide sits immediately after Home in main nav
        i_home = html.index('id="home-link"')
        i_sg = html.index('id="settings-guide-link"')
        i_lic = html.index('id="licence-link"')
        self.assertLess(i_home, i_sg)
        self.assertLess(i_sg, i_lic)
        # Dedicated homepage banner box must not appear
        self.assertNotIn("settings-explainer-banner", html)
        self.assertNotIn("settings-explainer-banner-link", html)
        self.assertNotIn('class="panel-card settings-banner"', html)

    def test_route_paths_include_settings_explainer(self) -> None:
        src = (ROOT / "status_page" / "app.py").read_text(encoding="utf-8")
        self.assertIn("settings_explainer_paths", src)
        self.assertIn("render_settings_explainer_page_html", src)
        # Banner helper may still exist for legacy callers; homepage must not inject it
        self.assertNotIn("render_settings_explainer_banner_html()", src)
        from settings_explainer import settings_explainer_paths

        paths = settings_explainer_paths()
        self.assertIn("/settings-explainer", paths)
        self.assertIn("/settings", paths)


if __name__ == "__main__":
    unittest.main()
