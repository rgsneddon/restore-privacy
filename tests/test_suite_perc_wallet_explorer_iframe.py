"""Suite homepage embeds Perccent explorer iframe with public /perc/ src."""

from __future__ import annotations

import sys
import unittest
from pathlib import Path
from urllib.parse import urlparse

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "status_page"))


class TestSuitePercWalletExplorerEmbedded(unittest.TestCase):
    def test_storefront_and_homepage_have_explorer_iframe(self) -> None:
        from downloads import (
            SUITE_PERC_EXPLORER_HREF,
            SUITE_PERC_WALLET_EXPLORER_IFRAME_SRC,
            render_suite_perc_wallet_explorer_iframe_html,
            render_suite_storefront_html,
        )

        src = SUITE_PERC_WALLET_EXPLORER_IFRAME_SRC
        self.assertTrue(src.endswith("/"), msg="trailing slash required for /perc/")
        self.assertIn("/perc", src)
        self.assertEqual(src, SUITE_PERC_EXPLORER_HREF)

        frag = render_suite_perc_wallet_explorer_iframe_html()
        self.assertIn("<iframe", frag)
        self.assertIn('data-explorer-iframe="1"', frag)
        self.assertIn("suite-perc-wallet-explorer", frag)
        self.assertIn(f'src="{src}"', frag)
        self.assertIn('loading="eager"', frag)
        self.assertIn('data-src-path="/perc/"', frag)
        # Not lazy-only connect-after-external-click
        self.assertNotIn('loading="lazy"', frag)

        suite = render_suite_storefront_html()
        self.assertIn("<iframe", suite)
        self.assertIn("data-explorer-iframe", suite)
        self.assertIn("suite-perc-wallet-explorer", suite)
        self.assertIn(f'src="{src}"', suite)
        self.assertIn("KEYGEN", suite)
        self.assertIn('id="suite-storefront"', suite)

    def test_csp_frame_src_allows_public_explorer_origin(self) -> None:
        import security_headers as sh
        from downloads import SUITE_PERC_EXPLORER_HREF

        host = urlparse(SUITE_PERC_EXPLORER_HREF).netloc
        self.assertIn("frame-src", sh.CONTENT_SECURITY_POLICY)
        self.assertIn(sh.FRAME_SRC_DIRECTIVE, sh.CONTENT_SECURITY_POLICY)
        self.assertIn(host, sh.FRAME_SRC_DIRECTIVE)
        self.assertIn(host, sh.CONTENT_SECURITY_POLICY)
        pairs = dict(sh.security_headers())
        self.assertIn(host, pairs["Content-Security-Policy"])

    def test_homepage_html_builder_mounts_explorer_embed(self) -> None:
        from app import render_html
        from downloads import SUITE_PERC_EXPLORER_HREF

        page = render_html({"title": "RESTORE PRIVACY"}).decode("utf-8")
        main = page[page.index('id="page-shell"') :]
        self.assertIn("suite-perc-wallet-explorer", main)
        self.assertIn("data-explorer-iframe", main)
        self.assertIn(f'src="{SUITE_PERC_EXPLORER_HREF}"', main)
        # Between storefront markers
        storefront = main.split('id="suite-storefront"')[1].split(
            'id="download-vpn"', 1
        )[0] if 'id="download-vpn"' in main else main.split('id="suite-storefront"')[1]
        self.assertIn("<iframe", storefront)
        self.assertIn("data-explorer-iframe", storefront)


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
        self.assertIn("explorerApiUrl('api/network')", html)
        self.assertIn("explorerApiUrl('api/blocks", html)
        # Connect path uses explorerApiUrl, not bare /api/network alone for fetch
        self.assertIn("fetch(explorerApiUrl('api/network'))", html)


if __name__ == "__main__":
    unittest.main()
