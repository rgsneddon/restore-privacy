"""Suite left-box sub-menu: Perc explorer + Evolve + Perccent wallet docs."""

from __future__ import annotations

import re
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "status_page"))


class TestSuiteBoxSubmenu(unittest.TestCase):
    def test_explorer_and_ecosystem_links_in_suite_storefront(self) -> None:
        from downloads import (
            SUITE_EVOLVE_PAGES_HREF,
            SUITE_EVOLVE_SOURCE_HREF,
            SUITE_EVOLVE_WHITEPAPER_HREF,
            SUITE_PERC_EXPLORER_HREF,
            SUITE_PERC_EXPLORER_LABEL,
            SUITE_PERCCENT_WALLET_HREF,
            SUITE_PERCCENT_WALLET_README_HREF,
            SUITE_SUBMENU_ID,
            render_suite_product_submenu_html,
            render_suite_storefront_html,
            suite_product_submenu_links,
        )

        links = suite_product_submenu_links()
        hrefs = {h for h, _, _ in links}
        self.assertIn(SUITE_PERC_EXPLORER_HREF, hrefs)
        self.assertTrue(
            SUITE_PERC_EXPLORER_HREF.startswith("https://135.181.152.10.sslip.io/perc")
        )
        self.assertIn(SUITE_EVOLVE_PAGES_HREF, hrefs)
        self.assertIn(SUITE_EVOLVE_WHITEPAPER_HREF, hrefs)
        self.assertIn(SUITE_EVOLVE_SOURCE_HREF, hrefs)
        self.assertIn(SUITE_PERCCENT_WALLET_HREF, hrefs)
        self.assertIn(SUITE_PERCCENT_WALLET_README_HREF, hrefs)

        sub = render_suite_product_submenu_html()
        self.assertIn(f'id="{SUITE_SUBMENU_ID}"', sub)
        self.assertIn('data-suite-product-submenu="1"', sub)
        self.assertIn(SUITE_PERC_EXPLORER_HREF, sub)
        self.assertIn(SUITE_PERC_EXPLORER_LABEL, sub)
        self.assertIn('data-suite-sub="perc-explorer"', sub)
        self.assertIn("Evolve", sub)
        self.assertIn("Perccent", sub)
        self.assertIn("explorer", sub.lower())

        suite = render_suite_storefront_html()
        self.assertIn(SUITE_SUBMENU_ID, suite)
        self.assertIn(SUITE_PERC_EXPLORER_HREF, suite)
        self.assertIn(SUITE_EVOLVE_PAGES_HREF, suite)
        self.assertIn(SUITE_EVOLVE_WHITEPAPER_HREF, suite)
        self.assertIn(SUITE_PERCCENT_WALLET_HREF, suite)
        # Sub-menu lives inside suite-storefront section
        m = re.search(
            r'id="suite-storefront"[\s\S]*?id="suite-product-submenu"[\s\S]*?'
            r'data-suite-sub="perc-explorer"[\s\S]*?</section>',
            suite,
        )
        self.assertIsNotNone(m, "submenu must be inside #suite-storefront")

    def test_suite_free_downloads_and_keygen_still_present(self) -> None:
        from downloads import render_suite_storefront_html, suite_free_download_href

        suite = render_suite_storefront_html()
        for plat in ("windows", "android", "macos", "ios", "linux"):
            self.assertIn(suite_free_download_href(plat), suite)
        self.assertIn("suite-free-grid", suite)
        self.assertIn("KEYGEN", suite)
        self.assertIn("/pay/checkout", suite)
        self.assertIn("suite-keygen-buy", suite)


if __name__ == "__main__":
    unittest.main()
