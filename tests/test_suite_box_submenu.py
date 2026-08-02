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
        # (href, label, key, title) — title optional expanded meaning
        hrefs = {row[0] for row in links}
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

        from downloads import SUITE_PRODUCT_SUBMENU_LABEL

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
        # Title includes (wip); bare "Suite ecosystem" alone is not the label
        self.assertEqual(SUITE_PRODUCT_SUBMENU_LABEL, "Suite ecosystem (wip)")
        self.assertIn("(wip)", suite)
        self.assertIn("suite-product-submenu-wip", suite)
        # Bottom of box: KEYGEN + pay-hint before submenu in document order
        i_buy = suite.index('id="suite-keygen-buy"')
        i_hint = suite.index('id="suite-pay-hint"')
        i_sub = suite.index('id="suite-product-submenu"')
        self.assertLess(i_buy, i_hint)
        self.assertLess(i_hint, i_sub)
        # Submenu is the last major block before section close
        after_sub = suite[i_sub:]
        self.assertNotIn('id="suite-keygen-buy"', after_sub)
        self.assertNotIn('id="suite-pay-hint"', after_sub)

    def test_suite_keygen_still_present_without_device_grid(self) -> None:
        from downloads import render_suite_storefront_html

        suite = render_suite_storefront_html()
        self.assertNotIn('id="suite-free-grid"', suite)
        self.assertNotIn("Device for KEYGEN", suite)
        self.assertNotIn("Get Suite", suite)
        self.assertIn("KEYGEN", suite)
        self.assertIn("/pay", suite)
        self.assertIn("suite-keygen-buy", suite)


if __name__ == "__main__":
    unittest.main()
