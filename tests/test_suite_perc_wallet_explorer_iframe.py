"""Suite storefront must NOT embed the Perccent block explorer iframe."""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "status_page"))

EXPLORER_HOST = "evolve-perc-internet.onrender.com"
EXPLORER_SRC = f"https://{EXPLORER_HOST}"


class TestSuitePercWalletExplorerNotEmbedded(unittest.TestCase):
    def test_storefront_and_homepage_have_no_explorer_iframe(self) -> None:
        from downloads import (
            render_suite_perc_wallet_explorer_iframe_html,
            render_suite_storefront_html,
        )

        # Helper is a no-op (kept import-safe)
        frag = render_suite_perc_wallet_explorer_iframe_html()
        self.assertEqual(frag.strip(), "")
        self.assertNotIn("<iframe", frag)
        self.assertNotIn(EXPLORER_HOST, frag)

        suite = render_suite_storefront_html()
        self.assertNotIn("<iframe", suite)
        self.assertNotIn("data-explorer-iframe", suite)
        self.assertNotIn("suite-perc-wallet-explorer", suite)
        self.assertNotIn(EXPLORER_SRC, suite)
        self.assertNotIn(EXPLORER_HOST, suite)
        # Suite surface still ships KEYGEN / free download chrome
        self.assertIn("KEYGEN", suite)
        self.assertIn("data-free-download", suite)
        self.assertIn('id="suite-storefront"', suite)

        from downloads import render_download_section_html

        dl = render_download_section_html()
        self.assertNotIn("suite-perc-wallet-explorer", dl)
        self.assertNotIn(EXPLORER_HOST, dl)

    def test_csp_frame_src_no_longer_allows_external_explorer(self) -> None:
        import security_headers as sh

        self.assertIn("frame-src", sh.CONTENT_SECURITY_POLICY)
        self.assertIn(sh.FRAME_SRC_DIRECTIVE, sh.CONTENT_SECURITY_POLICY)
        self.assertNotIn(EXPLORER_HOST, sh.FRAME_SRC_DIRECTIVE)
        self.assertNotIn(EXPLORER_SRC, sh.CONTENT_SECURITY_POLICY)
        self.assertNotIn(EXPLORER_HOST, sh.CONTENT_SECURITY_POLICY)
        pairs = dict(sh.security_headers())
        self.assertNotIn(EXPLORER_HOST, pairs["Content-Security-Policy"])

    def test_homepage_html_builder_omits_explorer_embed(self) -> None:
        from app import render_html

        page = render_html({"title": "RESTORE PRIVACY"}).decode("utf-8")
        main = page[page.index('id="page-shell"') :]
        self.assertNotIn("suite-perc-wallet-explorer", main)
        self.assertNotIn("data-explorer-iframe", main)
        # No framed load of the explorer host on the main shell
        self.assertNotIn(f'src="{EXPLORER_SRC}', main)
        self.assertNotIn(f"src='{EXPLORER_SRC}", main)
        # External submenu link to explorer is still allowed (not an embed)
        # — only iframe embeds are forbidden on this surface.
        self.assertNotIn("<iframe", main.split('id="suite-storefront"')[1].split('id="download-vpn"')[0] if 'id="download-vpn"' in main else main)


if __name__ == "__main__":
    unittest.main()
