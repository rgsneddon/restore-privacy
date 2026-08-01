"""Rx Privacy Browser docs served on the status host from monorepo / GitHub README."""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "status_page"))

RX_GITHUB_README = (
    "https://github.com/rgsneddon/Rx-Privacy-Browser/blob/master/README.md"
)


class TestRxDocsOnSite(unittest.TestCase):
    def test_public_rx_md_mirrors_readme_content(self) -> None:
        from public_docs import (
            RX_DOCS_PATH,
            RX_README_GITHUB_URL,
            load_public_document_bytes,
            public_doc_by_path,
        )

        self.assertEqual(RX_README_GITHUB_URL, RX_GITHUB_README)
        self.assertEqual(RX_DOCS_PATH, "/RX.md")
        doc = public_doc_by_path(RX_DOCS_PATH)
        self.assertIsNotNone(doc)
        assert doc is not None
        self.assertEqual(doc.filename, "RX.md")
        self.assertEqual(doc.path, "/RX.md")
        self.assertIsNotNone(public_doc_by_path("/rx"))
        self.assertIsNotNone(public_doc_by_path("/rx-browser"))
        self.assertIsNotNone(public_doc_by_path("/rx-privacy-browser"))
        self.assertIsNotNone(public_doc_by_path("/docs/rx"))

        raw = load_public_document_bytes("RX.md", min_size=200)
        self.assertIsInstance(raw, (bytes, bytearray))
        assert raw is not None
        text = raw.decode("utf-8")
        # Defining material from monorepo browser_extension README / GitHub Rx README
        self.assertIn("Rx Privacy Browser", text)
        self.assertIn("Manifest V3", text)
        self.assertIn("browser-scoped", text)
        self.assertIn(RX_GITHUB_README, text)

        pack = ROOT / "status_page" / "public" / "RX.md"
        self.assertTrue(pack.is_file())
        monorepo = (ROOT / "browser_extension" / "README.md").read_text(
            encoding="utf-8"
        )
        pack_text = pack.read_text(encoding="utf-8")
        self.assertIn("Rx Privacy Browser", pack_text)
        self.assertIn("chrome.proxy", pack_text)
        # Monorepo honesty line present in pack
        self.assertIn("Not OS residual", pack_text)
        self.assertIn("browser-scoped", monorepo)

    def test_suite_rx_homepage_href_is_same_origin(self) -> None:
        from downloads import (
            SUITE_RX_BROWSER_HREF,
            SUITE_RX_BROWSER_KEY,
            SUITE_RX_BROWSER_LABEL,
            render_suite_storefront_html,
            suite_product_submenu_links,
        )

        self.assertEqual(SUITE_RX_BROWSER_HREF, "/RX.md")
        self.assertTrue(SUITE_RX_BROWSER_HREF.startswith("/"))
        self.assertNotEqual(SUITE_RX_BROWSER_HREF, "#suite-rx-privacy-browser")
        self.assertNotIn("github.com", SUITE_RX_BROWSER_HREF)

        hrefs = {
            h
            for h, _, k, *_rest in suite_product_submenu_links()
            if k == SUITE_RX_BROWSER_KEY
        }
        self.assertEqual(hrefs, {"/RX.md"})

        suite = render_suite_storefront_html()
        self.assertIn(f'data-suite-sub="{SUITE_RX_BROWSER_KEY}"', suite)
        self.assertIn(f'href="{SUITE_RX_BROWSER_HREF}"', suite)
        self.assertIn(SUITE_RX_BROWSER_LABEL, suite)
        # Must not be placeholder-only or GitHub-only as the control href
        self.assertNotIn(
            'data-suite-sub="rx-privacy-browser" href="#suite-rx-privacy-browser"',
            suite.replace("\n", " "),
        )
        self.assertNotRegex(
            suite.replace("\n", " "),
            r'data-suite-sub="rx-privacy-browser"\s+href="https://github\.com/'
            r"rgsneddon/Rx-Privacy-Browser",
        )

    def test_rx_docs_rendered_as_public_site_page(self) -> None:
        """Drive the shipped public-doc path loader — HTML page, not admin-gated."""
        from public_docs import (
            RX_DOCS_PATH,
            document_bytes_for_path,
            public_docs_catalog,
        )

        result = document_bytes_for_path(RX_DOCS_PATH)
        self.assertIsNotNone(result)
        assert result is not None
        raw, content_type, title = result
        self.assertIsInstance(raw, (bytes, bytearray))
        self.assertIn("html", content_type.lower())
        html = raw.decode("utf-8")
        self.assertIn("Rx Privacy Browser", html)
        self.assertIn("Manifest V3", html)
        self.assertIn("browser-scoped", html)
        self.assertTrue(
            'id="page-shell"' in html
            or "data-page=" in html
            or "brand-panel" in html
            or "doc-body" in html
            or "site-nav" in html
            or "doc-links" in html,
            msg="expected public site chrome around Rx docs",
        )
        self.assertGreater(len(html), 500)
        self.assertIn("Rx", title)

        paths = {row["path"] for row in public_docs_catalog()}
        self.assertIn("/RX.md", paths)


if __name__ == "__main__":
    unittest.main()
