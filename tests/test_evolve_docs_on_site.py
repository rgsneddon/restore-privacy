"""Evolve docs served on the status host from the real evolve README."""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "status_page"))

EVOLVE_GITHUB_README = "https://github.com/rgsneddon/evolve/blob/main/README.md"


class TestEvolveDocsOnSite(unittest.TestCase):
    def test_public_evolve_md_mirrors_readme_content(self) -> None:
        from public_docs import (
            EVOLVE_DOCS_PATH,
            EVOLVE_README_GITHUB_URL,
            load_public_document_bytes,
            public_doc_by_path,
        )

        self.assertEqual(EVOLVE_README_GITHUB_URL, EVOLVE_GITHUB_README)
        doc = public_doc_by_path(EVOLVE_DOCS_PATH)
        self.assertIsNotNone(doc)
        assert doc is not None
        self.assertEqual(doc.filename, "EVOLVE.md")
        self.assertEqual(doc.path, "/EVOLVE.md")
        # Aliases
        self.assertIsNotNone(public_doc_by_path("/evolve"))
        self.assertIsNotNone(public_doc_by_path("/evolve-docs"))

        raw = load_public_document_bytes("EVOLVE.md", min_size=200)
        self.assertIsInstance(raw, (bytes, bytearray))
        assert raw is not None
        text = raw.decode("utf-8")
        # Material from the real evolve README
        self.assertIn("Chronoflux", text)
        self.assertIn("Evolve", text)
        self.assertIn(EVOLVE_GITHUB_README, text)
        # Local mirror file exists
        pack = ROOT / "status_page" / "public" / "EVOLVE.md"
        self.assertTrue(pack.is_file())
        pack_text = pack.read_text(encoding="utf-8")
        self.assertIn("Chronoflux", pack_text)
        self.assertIn("Social Science", pack_text)

    def test_suite_evolve_docs_link_is_same_origin(self) -> None:
        from downloads import (
            SUITE_EVOLVE_DOCS_HREF,
            SUITE_EVOLVE_PAGES_HREF,
            render_suite_storefront_html,
            suite_product_submenu_links,
        )

        self.assertEqual(SUITE_EVOLVE_DOCS_HREF, "/EVOLVE.md")
        self.assertEqual(SUITE_EVOLVE_PAGES_HREF, "/EVOLVE.md")
        # Primary evolve-docs entry is not only external GH Pages
        hrefs = {h for h, _, k in suite_product_submenu_links() if k == "evolve-docs"}
        self.assertEqual(hrefs, {"/EVOLVE.md"})
        suite = render_suite_storefront_html()
        self.assertIn('data-suite-sub="evolve-docs"', suite)
        self.assertIn('href="/EVOLVE.md"', suite)
        # Must not use GH Pages as the evolve-docs primary href in submenu
        self.assertNotIn(
            'data-suite-sub="evolve-docs" href="https://rgsneddon.github.io/evolve/"',
            suite.replace("\n", " "),
        )
        # White paper / source can remain external
        self.assertIn("fcg_white_paper.html", suite)
        self.assertIn("github.com/rgsneddon/evolve", suite)


if __name__ == "__main__":
    unittest.main()
