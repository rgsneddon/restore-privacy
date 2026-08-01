"""Homepage VPN ecosystem control opens same-origin monorepo README page."""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "status_page"))

README_GITHUB = (
    "https://github.com/rgsneddon/restore-privacy/blob/main/README.md"
)


class TestVpnDocsOnSite(unittest.TestCase):
    def test_public_readme_mirrors_monorepo_readme(self) -> None:
        from public_docs import (
            README_GITHUB_URL,
            README_PATH,
            load_public_document_bytes,
            public_doc_by_path,
        )

        self.assertEqual(README_GITHUB_URL, README_GITHUB)
        self.assertEqual(README_PATH, "/README.md")
        doc = public_doc_by_path(README_PATH)
        self.assertIsNotNone(doc)
        assert doc is not None
        self.assertEqual(doc.filename, "README.md")
        self.assertEqual(doc.path, "/README.md")
        self.assertIsNotNone(public_doc_by_path("/readme.md"))
        self.assertIsNotNone(public_doc_by_path("/docs/README.md"))

        raw = load_public_document_bytes("README.md", min_size=200)
        self.assertIsInstance(raw, (bytes, bytearray))
        assert raw is not None
        text = raw.decode("utf-8")
        # Defining monorepo README material (residual Suite / Connect / KEYGEN)
        self.assertIn("Restore Privacy", text)
        self.assertIn("KEYGEN", text)
        self.assertIn("Connect", text)
        self.assertTrue(
            "Suite" in text or "residual" in text.lower() or "VPN" in text
        )

        pack = ROOT / "status_page" / "public" / "README.md"
        monorepo = ROOT / "README.md"
        self.assertTrue(pack.is_file())
        self.assertTrue(monorepo.is_file())
        self.assertEqual(
            pack.read_text(encoding="utf-8"),
            monorepo.read_text(encoding="utf-8"),
        )

    def test_suite_vpn_homepage_href_is_same_origin(self) -> None:
        from downloads import (
            SUITE_ECOSYSTEM_VPN_HREF,
            SUITE_ECOSYSTEM_VPN_KEY,
            SUITE_ECOSYSTEM_VPN_LABEL,
            render_suite_storefront_html,
            suite_product_submenu_links,
        )

        self.assertEqual(SUITE_ECOSYSTEM_VPN_HREF, "/README.md")
        self.assertTrue(SUITE_ECOSYSTEM_VPN_HREF.startswith("/"))
        self.assertNotEqual(SUITE_ECOSYSTEM_VPN_HREF, "#suite-vpn")
        self.assertNotIn("github.com", SUITE_ECOSYSTEM_VPN_HREF)

        hrefs = {
            h
            for h, _, k, *_rest in suite_product_submenu_links()
            if k == SUITE_ECOSYSTEM_VPN_KEY
        }
        self.assertEqual(hrefs, {"/README.md"})

        suite = render_suite_storefront_html()
        self.assertIn(f'data-suite-sub="{SUITE_ECOSYSTEM_VPN_KEY}"', suite)
        self.assertIn(f'href="{SUITE_ECOSYSTEM_VPN_HREF}"', suite)
        self.assertIn(SUITE_ECOSYSTEM_VPN_LABEL, suite)
        self.assertNotIn(
            'data-suite-sub="suite-vpn" href="#suite-vpn"',
            suite.replace("\n", " "),
        )
        self.assertNotRegex(
            suite.replace("\n", " "),
            r'data-suite-sub="suite-vpn"\s+href="https://github\.com/'
            r"rgsneddon/restore-privacy",
        )

    def test_vpn_readme_rendered_as_public_site_page(self) -> None:
        """Drive the shipped public-doc path loader — HTML page, not admin-gated."""
        from public_docs import (
            README_PATH,
            document_bytes_for_path,
            public_docs_catalog,
        )

        result = document_bytes_for_path(README_PATH)
        self.assertIsNotNone(result)
        assert result is not None
        raw, content_type, title = result
        self.assertIsInstance(raw, (bytes, bytearray))
        self.assertIn("html", content_type.lower())
        html = raw.decode("utf-8")
        self.assertIn("Restore Privacy", html)
        self.assertIn("KEYGEN", html)
        self.assertIn("Connect", html)
        self.assertTrue(
            'id="page-shell"' in html
            or "data-page=" in html
            or "brand-panel" in html
            or "doc-body" in html
            or "site-nav" in html
            or "doc-links" in html,
            msg="expected public site chrome around monorepo README",
        )
        self.assertGreater(len(html), 500)
        self.assertIn("README", title)

        paths = {row["path"] for row in public_docs_catalog()}
        self.assertIn("/README.md", paths)


if __name__ == "__main__":
    unittest.main()
