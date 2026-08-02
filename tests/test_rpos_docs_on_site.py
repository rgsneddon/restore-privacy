"""rpOS docs served on the status host from the monorepo / GitHub README."""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "status_page"))

RPOS_GITHUB_README = "https://github.com/rgsneddon/rpOS/blob/main/README.md"


class TestRposDocsOnSite(unittest.TestCase):
    def test_public_rpos_md_mirrors_readme_content(self) -> None:
        from public_docs import (
            RPOS_DOCS_PATH,
            RPOS_README_GITHUB_URL,
            load_public_document_bytes,
            public_doc_by_path,
        )

        self.assertEqual(RPOS_README_GITHUB_URL, RPOS_GITHUB_README)
        self.assertEqual(RPOS_DOCS_PATH, "/RPOS.md")
        doc = public_doc_by_path(RPOS_DOCS_PATH)
        self.assertIsNotNone(doc)
        assert doc is not None
        self.assertEqual(doc.filename, "RPOS.md")
        self.assertEqual(doc.path, "/RPOS.md")
        self.assertIsNotNone(public_doc_by_path("/rpos"))
        self.assertIsNotNone(public_doc_by_path("/rpos-docs"))
        self.assertIsNotNone(public_doc_by_path("/docs/rpos"))

        raw = load_public_document_bytes("RPOS.md", min_size=200)
        self.assertIsInstance(raw, (bytes, bytearray))
        assert raw is not None
        text = raw.decode("utf-8")
        # Defining material from monorepo rpos/README.md / GitHub rpOS README
        self.assertIn("Restore Privacy Operating System", text)
        self.assertIn("rpOS", text)
        self.assertIn("RxShell", text)
        self.assertIn(RPOS_GITHUB_README, text)

        pack = ROOT / "status_page" / "public" / "RPOS.md"
        self.assertTrue(pack.is_file())
        monorepo = (ROOT / "rpos" / "README.md").read_text(encoding="utf-8")
        pack_text = pack.read_text(encoding="utf-8")
        # Pack is monorepo README body plus attribution header
        self.assertIn("Restore Privacy Operating System", pack_text)
        self.assertIn("RxShell", pack_text)
        self.assertIn(monorepo.strip().splitlines()[0], pack_text)

        # Current monopin from shipped package script — docs must not lag.
        import importlib.util

        spec = importlib.util.spec_from_file_location(
            "package_rpos", ROOT / "scripts" / "package_rpos.py"
        )
        assert spec and spec.loader
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        pin = str(mod.RPOS_VERSION).strip()
        self.assertTrue(pin)
        self.assertIn(f"Monopin {pin}", pack_text)
        self.assertIn(f"Monopin {pin}", monorepo)
        self.assertIn(f"releases/rpos/{pin}/", pack_text)
        self.assertIn(f"rpos-{pin}-windows-x64.zip", pack_text)
        self.assertNotIn("Monopin 0.2.0", pack_text)
        self.assertNotIn("rpos-0.2.0-", pack_text)
        self.assertNotIn("Monopin 0.2.0", monorepo)
        self.assertNotIn("rpos-0.2.0-", monorepo)

        # Admin how-to install story follows the same pin.
        import admin_rpos

        howto = admin_rpos.render_admin_rpos_deploy_howto_html()
        self.assertEqual(admin_rpos.current_rpos_monopin(), pin)
        self.assertIn(f"releases/rpos/{pin}/", howto)
        self.assertIn(f"rpos-{pin}-windows-x64.zip", howto)
        self.assertNotIn("rpos-0.2.0-", howto)

    def test_suite_rpos_homepage_href_is_same_origin(self) -> None:
        from downloads import (
            SUITE_RPOS_HREF,
            SUITE_RPOS_KEY,
            SUITE_RPOS_LABEL,
            render_suite_storefront_html,
            suite_product_submenu_links,
        )

        self.assertEqual(SUITE_RPOS_HREF, "/RPOS.md")
        self.assertTrue(SUITE_RPOS_HREF.startswith("/"))
        self.assertNotEqual(SUITE_RPOS_HREF, "#suite-rpos")
        self.assertNotIn("github.com", SUITE_RPOS_HREF)

        hrefs = {
            h for h, _, k, *_rest in suite_product_submenu_links() if k == SUITE_RPOS_KEY
        }
        self.assertEqual(hrefs, {"/RPOS.md"})

        suite = render_suite_storefront_html()
        self.assertIn(f'data-suite-sub="{SUITE_RPOS_KEY}"', suite)
        self.assertIn(f'href="{SUITE_RPOS_HREF}"', suite)
        self.assertIn(SUITE_RPOS_LABEL, suite)
        # Must not be placeholder-only or GitHub-only as the control href
        self.assertNotIn('data-suite-sub="rpos" href="#suite-rpos"', suite.replace("\n", " "))
        self.assertNotRegex(
            suite.replace("\n", " "),
            r'data-suite-sub="rpos"\s+href="https://github\.com/rgsneddon/rpOS',
        )

    def test_rpos_docs_rendered_as_public_site_page(self) -> None:
        """Drive the shipped public-doc path loader — HTML page, not admin-gated."""
        from public_docs import RPOS_DOCS_PATH, document_bytes_for_path, public_docs_catalog

        result = document_bytes_for_path(RPOS_DOCS_PATH)
        self.assertIsNotNone(result)
        assert result is not None
        raw, content_type, title = result
        self.assertIsInstance(raw, (bytes, bytearray))
        self.assertIn("html", content_type.lower())
        html = raw.decode("utf-8")
        self.assertIn("Restore Privacy Operating System", html)
        self.assertIn("rpOS", html)
        self.assertIn("RxShell", html)
        self.assertTrue(
            'id="page-shell"' in html
            or "data-page=" in html
            or "brand-panel" in html
            or "doc-body" in html
            or "site-nav" in html
            or "doc-links" in html,
            msg="expected public site chrome around rpOS docs",
        )
        self.assertGreater(len(html), 500)
        self.assertIn("rpOS", title)

        # Catalog lists public path (not /admin/rpos)
        paths = {row["path"] for row in public_docs_catalog()}
        self.assertIn("/RPOS.md", paths)
        self.assertNotIn("/admin/rpos", paths)


if __name__ == "__main__":
    unittest.main()
