"""Every public shell ends with copyright left + downloads-map link right."""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "status_page"))


class TestSiteFooterAllPages(unittest.TestCase):
    def test_public_page_close_includes_copyright_and_map(self) -> None:
        from coffee_link import (
            SITE_COPYRIGHT_TEXT,
            SITE_FOOTER_MAP_HREF,
            SITE_FOOTER_MAP_LABEL,
            coffee_link_css,
        )
        from public_chrome import public_page_close, public_site_css

        close = public_page_close()
        self.assertIn('id="site-footer"', close)
        self.assertIn("site-footer-copyright", close)
        self.assertIn("data-downloads-map-link", close)
        self.assertIn(SITE_FOOTER_MAP_HREF, close)
        self.assertIn(SITE_FOOTER_MAP_LABEL, close)
        self.assertIn("Raskul", close)
        self.assertIn("all rights reserved", close)
        css = coffee_link_css()
        self.assertIn("space-between", css)
        self.assertIn("text-align: right", css)
        # Single-row layout on all widths (no column stack on small screens)
        self.assertIn("flex-direction: row", css)
        self.assertIn("flex-wrap: nowrap", css)
        self.assertIn("max-width: 420px", css)
        narrow = css[css.index("@media (max-width: 420px)") :]
        self.assertIn("flex-direction: row", narrow)
        self.assertNotIn("flex-direction: column", narrow)
        self.assertIn("space-between", narrow)
        # Copyright left, map right — not centered stack
        self.assertIn("text-align: left", narrow)
        self.assertIn("text-align: right", narrow)
        self.assertNotIn("text-align: center", narrow)
        self.assertIn("white-space: nowrap", narrow)
        # Site-wide CSS pulls footer styles so docs shells style the line
        self.assertIn("site-footer", public_site_css())

    def test_home_map_docs_have_footer_pair(self) -> None:
        from app import render_html
        from downloads import render_downloads_map_page_html
        from public_docs import document_bytes_for_path

        samples = {
            "home": render_html({"title": "RESTORE PRIVACY"}).decode("utf-8"),
            "downloads-map": render_downloads_map_page_html().decode("utf-8"),
        }
        for path in ("/README.md", "/EVOLVE.md", "/RPOS.md", "/RX.md", "/LICENSE"):
            r = document_bytes_for_path(path)
            self.assertIsNotNone(r, path)
            assert r is not None
            samples[path] = r[0].decode("utf-8")

        for name, html in samples.items():
            with self.subTest(page=name):
                self.assertIn("site-footer", html)
                self.assertIn("data-downloads-map-link", html)
                self.assertIn("/downloads-map", html)
                self.assertIn("download map", html)
                self.assertNotIn("Downloadables Mapped Here", html)
                self.assertIn("Raskul", html)
                # Single footer (no double-render from bmc_tip + close)
                self.assertEqual(html.count('id="site-footer"'), 1)

    def test_public_site_export_footers(self) -> None:
        pub = ROOT / "public_site"
        for p in sorted(pub.glob("*.html")):
            t = p.read_text(encoding="utf-8")
            with self.subTest(file=p.name):
                self.assertIn("data-downloads-map-link", t)
                self.assertIn("download map", t)
                self.assertNotIn("Downloadables Mapped Here", t)
                self.assertIn("Raskul", t)
                self.assertIn("site-foot", t)
                self.assertIn("text-align: right", (ROOT / "public_site" / "assets" / "site.css").read_text())


if __name__ == "__main__":
    unittest.main()
