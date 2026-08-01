"""Suite perc-wallet area embeds live block explorer via iframe."""

from __future__ import annotations

import re
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "status_page"))

EXPLORER_HOST = "evolve-perc-internet.onrender.com"
EXPLORER_SRC = f"https://{EXPLORER_HOST}"


class TestSuitePercWalletExplorerIframe(unittest.TestCase):
    def test_iframe_constants_and_render(self) -> None:
        from downloads import (
            SUITE_PERC_WALLET_EXPLORER_ID,
            SUITE_PERC_WALLET_EXPLORER_IFRAME_ID,
            SUITE_PERC_WALLET_EXPLORER_IFRAME_SRC,
            render_suite_perc_wallet_explorer_iframe_html,
            render_suite_storefront_html,
        )

        self.assertEqual(SUITE_PERC_WALLET_EXPLORER_IFRAME_SRC, EXPLORER_SRC)
        frag = render_suite_perc_wallet_explorer_iframe_html()
        self.assertIn(f'id="{SUITE_PERC_WALLET_EXPLORER_ID}"', frag)
        self.assertIn(f'id="{SUITE_PERC_WALLET_EXPLORER_IFRAME_ID}"', frag)
        self.assertIn('data-suite-perc-wallet-explorer="1"', frag)
        self.assertIn('data-product="perccent-wallet"', frag)
        self.assertIn("<iframe", frag)
        self.assertIn(f'src="{EXPLORER_SRC}/"', frag)
        self.assertIn('data-explorer-iframe="1"', frag)
        self.assertIn(EXPLORER_HOST, frag)

        suite = render_suite_storefront_html()
        self.assertIn(SUITE_PERC_WALLET_EXPLORER_ID, suite)
        self.assertIn("<iframe", suite)
        self.assertIn(EXPLORER_SRC, suite)
        # Iframe sits inside suite-storefront, after ecosystem submenu (wallet area)
        m = re.search(
            r'id="suite-storefront"[\s\S]*?'
            r'id="suite-product-submenu"[\s\S]*?'
            r'id="suite-perc-wallet-explorer"[\s\S]*?'
            r'<iframe[\s\S]*?evolve-perc-internet\.onrender\.com[\s\S]*?</iframe>',
            suite,
        )
        self.assertIsNotNone(m, "iframe must be in Suite storefront after submenu")
        # Free download / KEYGEN preserved
        self.assertIn("KEYGEN", suite)
        self.assertIn("data-free-download", suite)
        # Not only on the right-hand downloads box
        from downloads import render_download_section_html

        dl = render_download_section_html()
        self.assertNotIn("suite-perc-wallet-explorer", dl)

    def test_csp_allows_explorer_frame_src(self) -> None:
        import security_headers as sh

        self.assertIn("frame-src", sh.CONTENT_SECURITY_POLICY)
        self.assertIn(EXPLORER_SRC, sh.CONTENT_SECURITY_POLICY)
        self.assertIn(EXPLORER_SRC, sh.FRAME_SRC_DIRECTIVE)
        self.assertIn(sh.FRAME_SRC_DIRECTIVE, sh.CONTENT_SECURITY_POLICY)
        self.assertIn(sh.FRAME_SRC_DIRECTIVE, sh.CONTENT_SECURITY_POLICY_FRAMEABLE)
        pairs = dict(sh.security_headers())
        self.assertIn(EXPLORER_SRC, pairs["Content-Security-Policy"])

    def test_homepage_includes_iframe_and_csp(self) -> None:
        from app import render_html
        import security_headers as sh

        page = render_html({"title": "RESTORE PRIVACY"}).decode("utf-8")
        main = page[page.index('id="page-shell"') :]
        self.assertIn('id="suite-perc-wallet-explorer"', main)
        self.assertIn('id="suite-perc-wallet-explorer-frame"', main)
        self.assertIn(f'src="{EXPLORER_SRC}/"', main)
        # CSP constant used by handler includes frame-src host
        self.assertIn(EXPLORER_HOST, sh.CONTENT_SECURITY_POLICY)


if __name__ == "__main__":
    unittest.main()
