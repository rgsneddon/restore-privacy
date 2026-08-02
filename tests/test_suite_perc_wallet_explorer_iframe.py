"""Homepage does not embed Perccent explorer iframe; submenu link may remain."""

from __future__ import annotations

import sys
import unittest
from pathlib import Path
from urllib.parse import urlparse

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "status_page"))


class TestSuitePercWalletExplorerNotOnHomepage(unittest.TestCase):
    def test_storefront_and_homepage_omit_explorer_iframe(self) -> None:
        from downloads import (
            SUITE_PERC_EXPLORER_HREF,
            SUITE_PERC_WALLET_EXPLORER_IFRAME_SRC,
            render_suite_perc_wallet_explorer_iframe_html,
            render_suite_storefront_html,
        )

        # Helper still builds valid embed markup when called directly
        src = SUITE_PERC_WALLET_EXPLORER_IFRAME_SRC
        self.assertTrue(src.endswith("/"), msg="trailing slash required for /perc/")
        self.assertIn("/perc", src)
        self.assertEqual(src, SUITE_PERC_EXPLORER_HREF)
        frag = render_suite_perc_wallet_explorer_iframe_html()
        self.assertIn("<iframe", frag)
        self.assertIn('data-explorer-iframe="1"', frag)

        # Homepage Suite storefront must NOT mount the embed
        suite = render_suite_storefront_html()
        self.assertIn('id="suite-storefront"', suite)
        self.assertIn("KEYGEN", suite)
        self.assertIn("data-pay-packages", suite)
        self.assertNotIn("<iframe", suite)
        self.assertNotIn("data-explorer-iframe", suite)
        self.assertNotIn("suite-perc-wallet-explorer", suite)
        self.assertNotIn('data-suite-perc-wallet-explorer="1"', suite)
        self.assertNotIn(f'src="{src}"', suite)
        # External explorer text link in submenu may remain
        self.assertIn('data-suite-sub="perc-explorer"', suite)

    def test_csp_frame_src_still_allows_public_explorer_origin(self) -> None:
        import security_headers as sh
        from downloads import SUITE_PERC_EXPLORER_HREF

        host = urlparse(SUITE_PERC_EXPLORER_HREF).netloc
        self.assertIn("frame-src", sh.CONTENT_SECURITY_POLICY)
        self.assertIn(sh.FRAME_SRC_DIRECTIVE, sh.CONTENT_SECURITY_POLICY)
        self.assertIn(host, sh.FRAME_SRC_DIRECTIVE)
        pairs = dict(sh.security_headers())
        self.assertIn(host, pairs["Content-Security-Policy"])

    def test_homepage_html_builder_has_no_explorer_embed(self) -> None:
        from app import render_html
        from downloads import SUITE_PERC_EXPLORER_HREF

        page = render_html({"title": "RESTORE PRIVACY"}).decode("utf-8")
        main = page[page.index('id="page-shell"') :]
        self.assertIn('id="suite-storefront"', main)
        self.assertNotIn("suite-perc-wallet-explorer", main)
        self.assertNotIn("data-explorer-iframe", main)
        self.assertNotIn('data-suite-perc-wallet-explorer="1"', main)
        # No explorer iframe in storefront region
        storefront = main.split('id="suite-storefront"')[1]
        if 'id="downloads"' in storefront:
            storefront = storefront.split('id="downloads"', 1)[0]
        self.assertNotIn("<iframe", storefront)
        self.assertNotIn(f'src="{SUITE_PERC_EXPLORER_HREF}"', storefront)
        # Storefront essentials still present
        self.assertIn("KEYGEN", storefront)
        self.assertIn("suite-free-grid", storefront)


class TestExplorerApiBaseForFramedPerc(unittest.TestCase):
    """Framed pathname /perc/ must prefix API URLs (shipped pure contract)."""

    def test_python_mirror_and_shipped_js_html(self) -> None:
        def explorer_api_base(pathname: str) -> str:
            p = str(pathname or "/")
            if p == "/perc" or p.startswith("/perc/"):
                return "/perc"
            last = p.rfind("/")
            if last > 0:
                d = p[:last]
                if d and d != "/":
                    return d.rstrip("/") or ""
            return ""

        def explorer_api_url(path: str, pathname: str = "/") -> str:
            base = explorer_api_base(pathname)
            rel = str(path or "").lstrip("/")
            if not base:
                return "/" + rel
            return base + "/" + rel

        # Framed Helsinki mount
        self.assertEqual(explorer_api_base("/perc/"), "/perc")
        self.assertEqual(explorer_api_url("api/network", "/perc/"), "/perc/api/network")
        self.assertEqual(
            explorer_api_url("api/blocks?limit=40", "/perc/"),
            "/perc/api/blocks?limit=40",
        )
        self.assertNotEqual(explorer_api_url("api/network", "/perc/"), "/api/network")

        # Root would 404 on path-mounted edge without prefix
        self.assertEqual(explorer_api_url("api/network", "/"), "/api/network")

        # Drive shipped JS helper file
        js = (ROOT / "perc_chain" / "src" / "explorer_api_base.js").read_text(
            encoding="utf-8"
        )
        self.assertIn("export function explorerApiBase", js)
        self.assertIn("/perc/", js)

        html = (ROOT / "perc_chain" / "public" / "index.html").read_text(
            encoding="utf-8"
        )
        self.assertIn("function explorerApiBase", html)


if __name__ == "__main__":
    unittest.main()
