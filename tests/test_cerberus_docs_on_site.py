"""CERBERUS docs served on the status host; Suite ecosystem menu link."""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "status_page"))

CERBERUS_GITHUB_README = "https://github.com/rgsneddon/CERBERUS/blob/main/README.md"


class TestCerberusDocsOnSite(unittest.TestCase):
    def test_public_cerberus_md_mirrors_readme_content(self) -> None:
        from public_docs import (
            CERBERUS_DOCS_PATH,
            CERBERUS_README_GITHUB_URL,
            load_public_document_bytes,
            public_doc_by_path,
        )

        self.assertEqual(CERBERUS_README_GITHUB_URL, CERBERUS_GITHUB_README)
        self.assertEqual(CERBERUS_DOCS_PATH, "/CERBERUS.md")
        doc = public_doc_by_path(CERBERUS_DOCS_PATH)
        self.assertIsNotNone(doc)
        assert doc is not None
        self.assertEqual(doc.filename, "CERBERUS.md")
        self.assertEqual(doc.path, "/CERBERUS.md")
        # Aliases
        self.assertIsNotNone(public_doc_by_path("/cerberus"))
        self.assertIsNotNone(public_doc_by_path("/CERBERUS"))
        self.assertIsNotNone(public_doc_by_path("/cerberus-docs"))

        raw = load_public_document_bytes("CERBERUS.md", min_size=200)
        self.assertIsInstance(raw, (bytes, bytearray))
        assert raw is not None
        text = raw.decode("utf-8")
        self.assertIn("CERBERUS", text)
        self.assertIn("residual-fleet", text.lower() or text)
        self.assertIn("strip_user_data", text)
        self.assertIn(CERBERUS_GITHUB_README, text)
        pack = ROOT / "status_page" / "public" / "CERBERUS.md"
        self.assertTrue(pack.is_file())
        pack_text = pack.read_text(encoding="utf-8")
        self.assertIn("On this site:", pack_text)
        self.assertIn(CERBERUS_GITHUB_README, pack_text)
        self.assertNotIn("<!-- Source", pack_text)
        self.assertGreater(len(pack_text), 400)

    def test_suite_cerberus_submenu_is_same_origin(self) -> None:
        from downloads import (
            SUITE_CERBERUS_HREF,
            SUITE_CERBERUS_KEY,
            SUITE_CERBERUS_LABEL,
            render_suite_product_submenu_html,
            render_suite_storefront_html,
            suite_product_submenu_links,
        )

        self.assertEqual(SUITE_CERBERUS_HREF, "/CERBERUS.md")
        self.assertEqual(SUITE_CERBERUS_LABEL, "CERBERUS")
        self.assertEqual(SUITE_CERBERUS_KEY, "cerberus")
        # Same-origin only (not bare github as sole href)
        hrefs = {
            h
            for h, label, k, *_rest in suite_product_submenu_links()
            if k == "cerberus" or "CERBERUS" in label
        }
        self.assertEqual(hrefs, {"/CERBERUS.md"})
        for h in hrefs:
            self.assertTrue(h.startswith("/"), h)
            self.assertNotIn("github.com", h)

        sub = render_suite_product_submenu_html()
        self.assertIn("CERBERUS", sub)
        self.assertIn('href="/CERBERUS.md"', sub)
        self.assertIn('data-suite-sub="cerberus"', sub)
        self.assertIn('id="suite-sub-cerberus"', sub)

        suite = render_suite_storefront_html()
        self.assertIn("CERBERUS", suite)
        self.assertIn('href="/CERBERUS.md"', suite)
        self.assertIn('data-suite-sub="cerberus"', suite)

    def test_cerberus_docs_rendered_as_public_site_page(self) -> None:
        from public_docs import CERBERUS_DOCS_PATH, document_bytes_for_path

        result = document_bytes_for_path(CERBERUS_DOCS_PATH)
        self.assertIsNotNone(result)
        assert result is not None
        raw, content_type, title = result
        self.assertIsInstance(raw, (bytes, bytearray))
        self.assertIn("html", content_type.lower())
        html = raw.decode("utf-8")
        self.assertIn("CERBERUS", html)
        self.assertIn(CERBERUS_GITHUB_README, html)
        self.assertIn("strip_user_data", html)
        self.assertTrue(
            'id="page-shell"' in html
            or "data-page=" in html
            or "brand-panel" in html
            or "doc-body" in html
            or "site-nav" in html
            or "doc-links" in html,
            msg="expected public site chrome around CERBERUS docs",
        )
        self.assertGreater(len(html), 800)
        self.assertIn("CERBERUS", title)


if __name__ == "__main__":
    unittest.main()
